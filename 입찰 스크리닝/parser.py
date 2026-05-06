import json
import anthropic
from datetime import date
from models import EventGroup, SearchResults, ScreeningResult
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SUPPLIERS
from scraper import scrape_blog, collect_images

def build_parsing_prompt(group_name: str, text_content: str) -> str:
    suppliers_str = ", ".join(SUPPLIERS)
    return f"""당신은 신용카드 모바일쿠폰 업계 분석가입니다.
아래는 "우리카드 {group_name}" 관련 블로그/카페 검색 결과입니다.

[텍스트 본문 및 검색 스니펫]
{text_content}

인식 대상 공급사 목록: {suppliers_str}

[분석 지침]
- 이미지가 있으면 기프티콘 화면에서 로고/브랜드를 찾으세요. 기프티쇼=KT엠하우스, GS엠비즈=GS25 쿠폰, 즐거운=행복한쿠폰 등
- 텍스트에서 공급사명이 직접 언급되지 않아도 쿠폰 플랫폼명(기프티쇼, 기프티콘, 쿠프마케팅 등)으로 추정 가능
- 쿠폰 액면가와 유효기간은 텍스트에서 "3천원권", "30일", "~2026.01.31" 등 형식으로 나올 수 있음
- 확실: 공급사명이 명시적으로 언급됨 / 추정: 로고·플랫폼명 등 간접 근거 있음 / 미확인: 근거 없음

다음 항목을 JSON으로 추출하세요 (다른 텍스트 없이):
{{
  "supplier": "공급사명 (위 목록에서만 선택. 없으면 null)",
  "coupon_type": "쿠폰 종류 (예: GS25 모바일쿠폰. 없으면 null)",
  "face_value": "액면가 (예: 3000원. 불명확하면 null)",
  "validity_days": "유효기간 (예: 30일. 불명확하면 null)",
  "evidence_url": "근거가 된 URL (없으면 null)",
  "confidence": "확실 또는 추정 또는 미확인",
  "confidence_reason": "판정 근거 한 줄"
}}"""

def analyze_group(group: EventGroup, search_results: SearchResults) -> ScreeningResult:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_text_parts = []
    all_images = []
    best_url = ""

    # Tavily 스니펫 먼저 추가 (이미 필터링된 관련 텍스트)
    for url, snippet in list(search_results.url_snippets.items())[:10]:
        if snippet:
            all_text_parts.append(f"[검색스니펫: {url}]\n{snippet}")

    # 상위 5개 URL 스크래핑 (이미지 포함)
    for url in search_results.urls[:5]:
        text, img_urls = scrape_blog(url)
        if text:
            all_text_parts.append(f"[블로그본문: {url}]\n{text}")
            if not best_url:
                best_url = url
        imgs = collect_images(img_urls)
        all_images.extend(imgs)
        if len(all_images) >= 5:
            break

    combined_text = "\n\n".join(all_text_parts)[:8000]

    content = []
    for b64, media_type in all_images[:5]:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        })
    content.append({"type": "text", "text": build_parsing_prompt(group.group_name, combined_text)})

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}

    return ScreeningResult(
        group_name=group.group_name,
        quote_ids=group.quote_ids,
        event_count=len(group.quote_ids),
        supplier=data.get("supplier"),
        coupon_type=data.get("coupon_type"),
        face_value=data.get("face_value"),
        validity_days=data.get("validity_days"),
        evidence_url=data.get("evidence_url") or best_url or None,
        confidence=data.get("confidence", "미확인"),
        confidence_reason=data.get("confidence_reason", "분석 실패"),
        search_date=date.today().isoformat(),
    )
