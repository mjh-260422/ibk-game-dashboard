import json
import anthropic
from models import UniqueEvent, EventGroup
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

BATCH_SIZE = 50

def build_grouping_prompt(events: list) -> str:
    lines = "\n".join(f"- 견적번호 {e.quote_id}: {e.quote_name}" for e in events)
    n = len(events)
    target = max(3, n // 5)
    return f"""아래는 우리카드 구매시스템의 모바일쿠폰 관련 미낙찰 견적명 목록 ({n}건)입니다.

{lines}

위 목록을 의미 단위로 그룹핑하고, 각 그룹에 소비자 관점 검색 키워드를 생성하세요.

[중요] 그룹핑 원칙:
- 월/차수/년도가 달라도 같은 이벤트 유형이면 반드시 하나의 그룹으로 통합
  예) '26년 1월 무실적(GS25)', '26년 2월 무실적(GS25)', '25년 12월 무실적(GS25)' → 모두 같은 그룹
- 브랜드가 다르면 분리 (GS25 vs 배민 vs 이마트)
- 성격이 다른 이벤트는 분리 (퀴즈이벤트 vs 이용활성화 캠페인)
- 목표 그룹 수: {target}개 이하 (과감하게 통합할 것)

키워드 생성 원칙:
- 키워드 1: 소비자 후기 검색용 — "우리카드 + 브랜드명 + 기프티콘 후기"
- 키워드 2: 공급사 식별용 — "우리카드 + 브랜드명 + 모바일쿠폰 공급사 기프티쇼 OR GS엠비즈 OR 즐거운 OR 쿠프마케팅"
- 키워드 3: 이벤트 정보용 — "우리카드 + 브랜드명 + 쿠폰 액면가 유효기간"
- 그룹당 3개 생성

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
[
  {{
    "group_name": "그룹명",
    "quote_ids": [견적번호 목록],
    "brands": ["브랜드명"],
    "search_keywords": ["키워드1", "키워드2", "키워드3"]
  }}
]"""

def _group_batch(client, events: list) -> list:
    prompt = build_grouping_prompt(events)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)
    return [
        EventGroup(
            group_name=item["group_name"],
            quote_ids=item["quote_ids"],
            brands=item["brands"],
            search_keywords=item["search_keywords"],
        )
        for item in data
    ]

def group_events(events: list) -> list:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    all_groups = []
    batches = [events[i:i + BATCH_SIZE] for i in range(0, len(events), BATCH_SIZE)]
    for idx, batch in enumerate(batches, 1):
        print(f"      배치 [{idx}/{len(batches)}] {len(batch)}건...", flush=True)
        all_groups.extend(_group_batch(client, batch))
    return all_groups
