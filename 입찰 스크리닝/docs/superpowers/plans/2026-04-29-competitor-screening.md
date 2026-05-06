# 우리카드 미낙찰 경쟁사 스크리닝 자동화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 우리카드 미낙찰 엑셀 파일을 입력 받아, Claude + Tavily로 경쟁사 쿠폰 공급사·종류·액면가·유효기간을 자동 조사하고 Google Sheets에 기록하는 파이프라인을 구축한다.

**Architecture:** Excel 로딩(Phase 1) → Claude 의미 그룹핑 + 키워드 생성(Phase 2) → Tavily 병렬 검색(Phase 3) → 블로그 스크래핑 + Claude Vision 분석(Phase 4) → Google Sheets 기록(Phase 5). 각 Phase는 독립 모듈로 분리하여 단독 테스트 가능.

**Tech Stack:** Python 3.9+, anthropic SDK, tavily-python, gspread, requests, BeautifulSoup4, Pillow, pandas, openpyxl, pytest

---

## 파일 구조

```
입찰 스크리닝/
├── screening.py       # CLI 진입점 + 파이프라인 오케스트레이터
├── models.py          # 데이터 클래스 (UniqueEvent, EventGroup, SearchResults, ScreeningResult)
├── config.py          # .env 로딩 + SUPPLIERS 상수
├── loader.py          # Phase 1: Excel 로딩 + 중복 제거
├── grouper.py         # Phase 2: Claude 이벤트 그룹핑 + 검색 키워드 생성
├── searcher.py        # Phase 3: Tavily 병렬 검색
├── scraper.py         # Phase 4A: 블로그 텍스트 + 이미지 크롤링
├── parser.py          # Phase 4B: Claude Vision + 텍스트 분석 → 구조화 결과
├── reporter.py        # Phase 5: Google Sheets 기록
├── tests/
│   ├── test_loader.py
│   ├── test_grouper.py
│   ├── test_scraper.py
│   ├── test_parser.py
│   └── test_reporter.py
├── requirements.txt
├── .env               # API 키 (git 제외)
├── .env.example
└── .gitignore
```

> 모든 명령은 `입찰 스크리닝/` 디렉토리 안에서 실행한다. Windows에서 Python 명령은 `py`를 사용한다.

---

## Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `입찰 스크리닝/requirements.txt`
- Create: `입찰 스크리닝/.env.example`
- Create: `입찰 스크리닝/.gitignore`
- Create: `입찰 스크리닝/config.py`

- [ ] **Step 1: requirements.txt 생성**

```
입찰 스크리닝/requirements.txt
```
```
anthropic>=0.40.0
tavily-python>=0.3.0
gspread>=6.0.0
google-auth>=2.0.0
pandas>=2.0.0
openpyxl>=3.1.0
requests>=2.31.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
Pillow>=10.0.0
pytest>=8.0.0
```

- [ ] **Step 2: .env.example 생성**

```
입찰 스크리닝/.env.example
```
```
ANTHROPIC_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
GOOGLE_SHEETS_KEY_PATH=~/.claude/google-sheets-key.json
OUTPUT_SPREADSHEET_ID=your_spreadsheet_id_here
```

- [ ] **Step 3: .gitignore 생성**

```
입찰 스크리닝/.gitignore
```
```
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: config.py 생성**

```python
# 입찰 스크리닝/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# .get() 사용: 테스트 시 모든 API를 mock하므로 실제 값 불필요.
# 실제 실행 시엔 .env 파일에 반드시 값이 있어야 함.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
GOOGLE_SHEETS_KEY_PATH = os.environ.get(
    "GOOGLE_SHEETS_KEY_PATH",
    str(Path.home() / ".claude" / "google-sheets-key.json")
)
OUTPUT_SPREADSHEET_ID = os.environ.get("OUTPUT_SPREADSHEET_ID", "")

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_IMAGES_PER_BLOG = 5
MAX_URLS_PER_GROUP = 25
SEARCH_RESULTS_PER_KEYWORD = 5

SUPPLIERS = [
    "GS엠비즈", "즐거운", "쿠프마케팅", "네이버파이낸셜", "윈큐브마케팅",
    "기프티쇼(KT엠하우스)", "케이티알파", "다우기술", "엠트웰브(기프트팝)",
    "카카오선물하기", "이지코드", "CJ올리브네트웍스", "모바일리더",
]
```

- [ ] **Step 5: 의존성 설치**

```bash
cd "입찰 스크리닝" && py -m pip install -r requirements.txt
```
Expected: Successfully installed ... (오류 없이 완료)

- [ ] **Step 6: .env 파일 생성 (.env.example 복사 후 실제 키 입력)**

```bash
copy .env.example .env
```
`.env` 파일을 열어 실제 API 키 4개를 입력한다.

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt .env.example .gitignore config.py
git commit -m "feat: project scaffolding for competitor screening"
```

---

## Task 2: 데이터 모델

**Files:**
- Create: `입찰 스크리닝/models.py`
- Create: `입찰 스크리닝/tests/test_models.py` (임시 smoke test)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# 입찰 스크리닝/tests/test_models.py
from models import UniqueEvent, EventGroup, SearchResults, ScreeningResult

def test_unique_event_instantiation():
    e = UniqueEvent(quote_id=100, quote_name="테스트", latest_date="2026-04-29", rebid_count=2)
    assert e.quote_id == 100
    assert e.rebid_count == 2

def test_event_group_instantiation():
    g = EventGroup(
        group_name="무실적_GS25",
        quote_ids=[100, 101],
        brands=["GS25"],
        search_keywords=["우리카드 GS25 쿠폰"],
    )
    assert len(g.search_keywords) == 1

def test_search_results_instantiation():
    sr = SearchResults(
        group_name="무실적_GS25",
        urls=["https://example.com"],
        url_snippets={"https://example.com": "블로그 내용"},
    )
    assert sr.urls[0] == "https://example.com"

def test_screening_result_instantiation():
    r = ScreeningResult(
        group_name="무실적_GS25",
        quote_ids=[100],
        event_count=1,
        supplier="기프티쇼(KT엠하우스)",
        coupon_type="GS25 모바일쿠폰",
        face_value="3000원",
        validity_days="30일",
        evidence_url="https://example.com",
        confidence="확실",
        confidence_reason="이미지에서 로고 확인",
        search_date="2026-04-29",
    )
    assert r.confidence == "확실"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
py -m pytest tests/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: models.py 구현**

```python
# 입찰 스크리닝/models.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class UniqueEvent:
    quote_id: int
    quote_name: str
    latest_date: str
    rebid_count: int

@dataclass
class EventGroup:
    group_name: str
    quote_ids: List[int]
    brands: List[str]
    search_keywords: List[str]

@dataclass
class SearchResults:
    group_name: str
    urls: List[str]
    url_snippets: Dict[str, str]

@dataclass
class ScreeningResult:
    group_name: str
    quote_ids: List[int]
    event_count: int
    supplier: Optional[str]
    coupon_type: Optional[str]
    face_value: Optional[str]
    validity_days: Optional[str]
    evidence_url: Optional[str]
    confidence: str
    confidence_reason: str
    search_date: str
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
py -m pytest tests/test_models.py -v
```
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add models.py tests/test_models.py
git commit -m "feat: add data models"
```

---

## Task 3: Phase 1 — Excel 로더

**Files:**
- Create: `입찰 스크리닝/loader.py`
- Create: `입찰 스크리닝/tests/test_loader.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# 입찰 스크리닝/tests/test_loader.py
import pandas as pd
import pytest
from loader import deduplicate_events
from models import UniqueEvent

COLS = ["순번", "상태", "처리일", "견적번호", "견적명", "담당자명", "시작일시", "마감일시", "낙찰기준"]

def make_df(rows):
    return pd.DataFrame(rows, columns=COLS)

def test_dedup_removes_duplicate_quote_ids():
    df = make_df([
        [1, "미낙찰", "2026-04-28", 100, "테스트 이벤트", "김", "2026-04-27", "2026-04-27", "총액최저가"],
        [2, "미낙찰", "2026-04-29", 100, "테스트 이벤트", "김", "2026-04-28", "2026-04-28", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert len(result) == 1
    assert result[0].quote_id == 100

def test_dedup_counts_rebids():
    df = make_df([
        [1, "미낙찰", "2026-04-27", 100, "이벤트 A", "김", "2026-04-26", "2026-04-26", "총액최저가"],
        [2, "미낙찰", "2026-04-28", 100, "이벤트 A", "김", "2026-04-27", "2026-04-27", "총액최저가"],
        [3, "미낙찰", "2026-04-29", 100, "이벤트 A", "김", "2026-04-28", "2026-04-28", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert result[0].rebid_count == 3

def test_dedup_keeps_latest_date():
    df = make_df([
        [1, "미낙찰", "2026-04-27", 100, "이벤트 A", "김", "2026-04-26", "2026-04-26", "총액최저가"],
        [2, "미낙찰", "2026-04-29", 100, "이벤트 A", "김", "2026-04-28", "2026-04-28", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert "2026-04-29" in result[0].latest_date

def test_dedup_preserves_distinct_events():
    df = make_df([
        [1, "미낙찰", "2026-04-28", 100, "이벤트 A", "김", "2026-04-27", "2026-04-27", "총액최저가"],
        [2, "미낙찰", "2026-04-28", 200, "이벤트 B", "이", "2026-04-27", "2026-04-27", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert len(result) == 2

def test_dedup_strips_whitespace_from_name():
    df = make_df([
        [1, "미낙찰", "2026-04-28", 100, "  이벤트 A  ", "김", "2026-04-27", "2026-04-27", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert result[0].quote_name == "이벤트 A"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
py -m pytest tests/test_loader.py -v
```
Expected: `ModuleNotFoundError: No module named 'loader'`

- [ ] **Step 3: loader.py 구현**

```python
# 입찰 스크리닝/loader.py
import pandas as pd
from models import UniqueEvent

def load_excel(filepath: str) -> pd.DataFrame:
    return pd.read_excel(filepath)

def deduplicate_events(df: pd.DataFrame) -> list:
    df = df.copy()
    df["처리일"] = df["처리일"].astype(str)
    df = df.sort_values("처리일", ascending=False)

    rebid_counts = df.groupby("견적번호").size().to_dict()
    unique_df = df.drop_duplicates(subset="견적번호", keep="first")

    events = []
    for _, row in unique_df.iterrows():
        events.append(UniqueEvent(
            quote_id=int(row["견적번호"]),
            quote_name=str(row["견적명"]).strip(),
            latest_date=str(row["처리일"]),
            rebid_count=int(rebid_counts.get(int(row["견적번호"]), 1)),
        ))
    return events
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
py -m pytest tests/test_loader.py -v
```
Expected: `5 passed`

- [ ] **Step 5: 커밋**

```bash
git add loader.py tests/test_loader.py
git commit -m "feat: add excel loader with deduplication"
```

---

## Task 4: Phase 2 — Claude 이벤트 그룹핑

**Files:**
- Create: `입찰 스크리닝/grouper.py`
- Create: `입찰 스크리닝/tests/test_grouper.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# 입찰 스크리닝/tests/test_grouper.py
from unittest.mock import patch, MagicMock
import json
from grouper import build_grouping_prompt, group_events
from models import UniqueEvent

SAMPLE_EVENTS = [
    UniqueEvent(1725, "'26년 4월 2차 당월무실적 이용조건부 마케팅(GS25)", "2026-04-24", 2),
    UniqueEvent(1726, "기업카드 퀴즈이벤트 쿠폰발송", "2026-04-24", 1),
]

def test_prompt_contains_quote_ids_and_names():
    prompt = build_grouping_prompt(SAMPLE_EVENTS)
    assert "1725" in prompt
    assert "GS25" in prompt
    assert "퀴즈이벤트" in prompt

def test_prompt_requests_json_output():
    prompt = build_grouping_prompt(SAMPLE_EVENTS)
    assert "JSON" in prompt
    assert "search_keywords" in prompt

def test_group_events_returns_event_groups():
    mock_data = [
        {
            "group_name": "무실적 마케팅_GS25",
            "quote_ids": [1725],
            "brands": ["GS25"],
            "search_keywords": ["우리카드 GS25 쿠폰", "우리카드 편의점 혜택"],
        },
        {
            "group_name": "기업카드 퀴즈이벤트",
            "quote_ids": [1726],
            "brands": [],
            "search_keywords": ["우리카드 퀴즈 이벤트 쿠폰"],
        },
    ]
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(mock_data))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("grouper.anthropic.Anthropic", return_value=mock_client):
        result = group_events(SAMPLE_EVENTS)

    assert len(result) == 2
    assert result[0].group_name == "무실적 마케팅_GS25"
    assert result[0].search_keywords == ["우리카드 GS25 쿠폰", "우리카드 편의점 혜택"]
    assert result[1].quote_ids == [1726]
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
py -m pytest tests/test_grouper.py -v
```
Expected: `ModuleNotFoundError: No module named 'grouper'`

- [ ] **Step 3: grouper.py 구현**

```python
# 입찰 스크리닝/grouper.py
import json
import anthropic
from models import UniqueEvent, EventGroup
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

def build_grouping_prompt(events: list) -> str:
    lines = "\n".join(f"- 견적번호 {e.quote_id}: {e.quote_name}" for e in events)
    return f"""아래는 우리카드 구매시스템의 모바일쿠폰 관련 미낙찰 견적명 목록입니다.

{lines}

다음 규칙으로 의미 단위 그룹핑 후 각 그룹에 소비자 관점 검색 키워드를 생성하세요.

그룹핑 규칙:
- 월/차수가 달라도 동일 이벤트 시리즈 → 같은 그룹
- 브랜드가 다르면 분리 (GS25 vs 배민)
- 성격이 다른 이벤트는 분리

키워드 생성 원칙:
- 소비자가 카드사 홈페이지/문자에서 보는 마케팅 언어 사용 (행정 용어 제거)
- "우리카드 + 브랜드명" 조합 필수 포함
- 네이버 블로그 검색에 최적화된 자연어
- 그룹당 3~5개 생성

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
[
  {{
    "group_name": "그룹명",
    "quote_ids": [견적번호 목록],
    "brands": ["브랜드명"],
    "search_keywords": ["키워드1", "키워드2"]
  }}
]"""

def group_events(events: list) -> list:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = build_grouping_prompt(events)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8096,
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
py -m pytest tests/test_grouper.py -v
```
Expected: `3 passed`

- [ ] **Step 5: 커밋**

```bash
git add grouper.py tests/test_grouper.py
git commit -m "feat: add claude event grouper"
```

---

## Task 5: Phase 3 — Tavily 병렬 검색

**Files:**
- Create: `입찰 스크리닝/searcher.py`
- Create: `입찰 스크리닝/tests/test_searcher.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# 입찰 스크리닝/tests/test_searcher.py
from unittest.mock import patch, MagicMock
from searcher import search_group, deduplicate_urls
from models import EventGroup, SearchResults

SAMPLE_GROUP = EventGroup(
    group_name="무실적 마케팅_GS25",
    quote_ids=[1725],
    brands=["GS25"],
    search_keywords=["우리카드 GS25 쿠폰", "우리카드 편의점 혜택"],
)

def test_deduplicate_urls_removes_duplicates():
    results = [
        {"url": "https://blog.naver.com/a", "content": "내용A"},
        {"url": "https://blog.naver.com/b", "content": "내용B"},
        {"url": "https://blog.naver.com/a", "content": "내용A"},
    ]
    urls, snippets = deduplicate_urls(results)
    assert len(urls) == 2
    assert "https://blog.naver.com/a" in snippets

def test_search_group_returns_search_results():
    mock_response = {
        "results": [
            {"url": "https://blog.naver.com/post1", "content": "우리카드 GS25 이벤트"},
            {"url": "https://tistory.com/post2", "content": "GS25 쿠폰 받았어요"},
        ]
    }
    mock_client = MagicMock()
    mock_client.search.return_value = mock_response

    with patch("searcher.TavilyClient", return_value=mock_client):
        result = search_group(SAMPLE_GROUP)

    assert isinstance(result, SearchResults)
    assert result.group_name == "무실적 마케팅_GS25"
    assert len(result.urls) > 0

def test_search_group_handles_api_error_gracefully():
    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("API Error")

    with patch("searcher.TavilyClient", return_value=mock_client):
        result = search_group(SAMPLE_GROUP)

    assert result.urls == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
py -m pytest tests/test_searcher.py -v
```
Expected: `ModuleNotFoundError: No module named 'searcher'`

- [ ] **Step 3: searcher.py 구현**

```python
# 입찰 스크리닝/searcher.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from tavily import TavilyClient
from models import EventGroup, SearchResults
from config import TAVILY_API_KEY, MAX_URLS_PER_GROUP, SEARCH_RESULTS_PER_KEYWORD

def deduplicate_urls(results: list) -> tuple:
    seen = set()
    urls = []
    snippets = {}
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
            snippets[url] = r.get("content", "")
    return urls, snippets

def _search_keyword(client: TavilyClient, keyword: str) -> list:
    try:
        resp = client.search(
            query=keyword,
            search_depth="advanced",
            max_results=SEARCH_RESULTS_PER_KEYWORD,
        )
        return resp.get("results", [])
    except Exception:
        return []

def search_group(group: EventGroup) -> SearchResults:
    client = TavilyClient(api_key=TAVILY_API_KEY)
    all_results = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_search_keyword, client, kw): kw
            for kw in group.search_keywords
        }
        for future in as_completed(futures):
            all_results.extend(future.result())

    urls, snippets = deduplicate_urls(all_results)
    return SearchResults(
        group_name=group.group_name,
        urls=urls[:MAX_URLS_PER_GROUP],
        url_snippets={u: snippets[u] for u in urls[:MAX_URLS_PER_GROUP]},
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
py -m pytest tests/test_searcher.py -v
```
Expected: `3 passed`

- [ ] **Step 5: 커밋**

```bash
git add searcher.py tests/test_searcher.py
git commit -m "feat: add tavily parallel searcher"
```

---

## Task 6: Phase 4A — 블로그 스크래퍼

**Files:**
- Create: `입찰 스크리닝/scraper.py`
- Create: `입찰 스크리닝/tests/test_scraper.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# 입찰 스크리닝/tests/test_scraper.py
from unittest.mock import patch, MagicMock
from scraper import scrape_blog, collect_images

SAMPLE_HTML = """
<html><body>
<nav>Navigation</nav>
<main>
  <p>우리카드 GS25 쿠폰 이벤트를 받았습니다. 기프티쇼 문자로 왔어요!</p>
  <img src="https://example.com/coupon_large.jpg" />
  <img src="https://example.com/icon_tiny.png" />
</main>
<footer>Footer</footer>
</body></html>
"""

def _make_mock_resp(html):
    m = MagicMock()
    m.text = html
    m.raise_for_status.return_value = None
    return m

def test_scrape_blog_extracts_text():
    with patch("scraper.requests.get", return_value=_make_mock_resp(SAMPLE_HTML)):
        text, _ = scrape_blog("https://example.com/blog")
    assert "우리카드 GS25" in text
    assert "기프티쇼" in text

def test_scrape_blog_removes_nav_and_footer():
    with patch("scraper.requests.get", return_value=_make_mock_resp(SAMPLE_HTML)):
        text, _ = scrape_blog("https://example.com/blog")
    assert "Navigation" not in text
    assert "Footer" not in text

def test_scrape_blog_extracts_image_urls():
    with patch("scraper.requests.get", return_value=_make_mock_resp(SAMPLE_HTML)):
        _, images = scrape_blog("https://example.com/blog")
    assert "https://example.com/coupon_large.jpg" in images

def test_scrape_blog_handles_connection_error():
    with patch("scraper.requests.get", side_effect=Exception("timeout")):
        text, images = scrape_blog("https://example.com/bad")
    assert text == ""
    assert images == []

def test_collect_images_skips_unavailable_urls():
    with patch("scraper.download_image_as_base64", return_value=None):
        result = collect_images(["https://example.com/bad.jpg"])
    assert result == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
py -m pytest tests/test_scraper.py -v
```
Expected: `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 3: scraper.py 구현**

```python
# 입찰 스크리닝/scraper.py
import base64
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from config import MAX_IMAGES_PER_BLOG

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def scrape_blog(url: str) -> tuple:
    """Returns (text_content, image_url_list)"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception:
        return "", []

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)[:3000]

    imgs = []
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if src.startswith("//"):
            src = "https:" + src
        if src.startswith("http"):
            imgs.append(src)

    return text, imgs[: MAX_IMAGES_PER_BLOG * 2]

def download_image_as_base64(url: str):
    """Returns (base64_str, media_type) or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        ct = resp.headers.get("content-type", "")
        if not any(t in ct for t in ["jpeg", "jpg", "png", "webp"]):
            return None

        data = resp.content
        if len(data) > 5 * 1024 * 1024:
            return None

        img = Image.open(BytesIO(data))
        w, h = img.size
        if w < 100 or h < 100:
            return None

        if "png" in ct:
            media_type = "image/png"
        elif "webp" in ct:
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"

        return base64.standard_b64encode(data).decode("utf-8"), media_type
    except Exception:
        return None

def collect_images(image_urls: list) -> list:
    """Returns list of (base64_str, media_type) tuples."""
    images = []
    for url in image_urls:
        if len(images) >= MAX_IMAGES_PER_BLOG:
            break
        result = download_image_as_base64(url)
        if result:
            images.append(result)
    return images
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
py -m pytest tests/test_scraper.py -v
```
Expected: `5 passed`

- [ ] **Step 5: 커밋**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add blog scraper with image extraction"
```

---

## Task 7: Phase 4B — Claude Vision 파서

**Files:**
- Create: `입찰 스크리닝/parser.py`
- Create: `입찰 스크리닝/tests/test_parser.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# 입찰 스크리닝/tests/test_parser.py
from unittest.mock import patch, MagicMock
import json
from parser import build_parsing_prompt, analyze_group
from models import EventGroup, SearchResults

def test_prompt_contains_all_suppliers():
    from config import SUPPLIERS
    prompt = build_parsing_prompt("무실적_GS25", "블로그 텍스트")
    for supplier in SUPPLIERS:
        assert supplier in prompt

def test_prompt_requests_json_fields():
    prompt = build_parsing_prompt("무실적_GS25", "블로그 텍스트")
    for field in ["supplier", "coupon_type", "face_value", "validity_days", "confidence"]:
        assert field in prompt

def test_analyze_group_parses_claude_json():
    mock_json = {
        "supplier": "기프티쇼(KT엠하우스)",
        "coupon_type": "GS25 모바일쿠폰",
        "face_value": "3000원",
        "validity_days": "30일",
        "evidence_url": "https://blog.naver.com/test",
        "confidence": "확실",
        "confidence_reason": "이미지에서 기프티쇼 로고 확인",
    }
    group = EventGroup("무실적_GS25", [1725], ["GS25"], ["우리카드 GS25"])
    sr = SearchResults("무실적_GS25", ["https://blog.naver.com/test"], {})

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(mock_json))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("parser.anthropic.Anthropic", return_value=mock_client), \
         patch("parser.scrape_blog", return_value=("블로그 텍스트 내용", [])), \
         patch("parser.collect_images", return_value=[]):
        result = analyze_group(group, sr)

    assert result.supplier == "기프티쇼(KT엠하우스)"
    assert result.face_value == "3000원"
    assert result.confidence == "확실"

def test_analyze_group_returns_미확인_on_empty_results():
    group = EventGroup("미확인 이벤트", [999], [], ["우리카드 알수없음"])
    sr = SearchResults("미확인 이벤트", [], {})

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"supplier": null, "coupon_type": null, "face_value": null, "validity_days": null, "evidence_url": null, "confidence": "미확인", "confidence_reason": "검색 결과 없음"}')]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("parser.anthropic.Anthropic", return_value=mock_client), \
         patch("parser.scrape_blog", return_value=("", [])), \
         patch("parser.collect_images", return_value=[]):
        result = analyze_group(group, sr)

    assert result.confidence == "미확인"
    assert result.supplier is None
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
py -m pytest tests/test_parser.py -v
```
Expected: `ModuleNotFoundError: No module named 'parser'`

- [ ] **Step 3: parser.py 구현**

```python
# 입찰 스크리닝/parser.py
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

[텍스트 본문]
{text_content}

인식 대상 공급사: {suppliers_str}

다음 항목을 JSON으로 추출하세요 (다른 텍스트 없이):
{{
  "supplier": "공급사명 (위 목록에서만 선택. 없으면 null)",
  "coupon_type": "쿠폰 종류 (예: GS25 모바일쿠폰. 없으면 null)",
  "face_value": "액면가 (예: 3000원. 불명확하면 null)",
  "validity_days": "유효기간 (예: 30일. 불명확하면 null)",
  "evidence_url": "근거가 된 URL (없으면 null)",
  "confidence": "확실 또는 추정 또는 미확인",
  "confidence_reason": "판정 근거 한 줄"
}}

공급사를 특정할 수 없으면 반드시 null. 추측 금지."""

def analyze_group(group: EventGroup, search_results: SearchResults) -> ScreeningResult:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_text_parts = []
    all_images = []
    best_url = ""

    for url in search_results.urls[:5]:
        text, img_urls = scrape_blog(url)
        if text:
            all_text_parts.append(f"[출처: {url}]\n{text}")
            if not best_url:
                best_url = url
        imgs = collect_images(img_urls)
        all_images.extend(imgs)
        if len(all_images) >= 5:
            break

    combined_text = "\n\n".join(all_text_parts)[:5000]

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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
py -m pytest tests/test_parser.py -v
```
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add parser.py tests/test_parser.py
git commit -m "feat: add claude vision parser"
```

---

## Task 8: Phase 5 — Google Sheets 리포터

**Files:**
- Create: `입찰 스크리닝/reporter.py`
- Create: `입찰 스크리닝/tests/test_reporter.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# 입찰 스크리닝/tests/test_reporter.py
from unittest.mock import patch, MagicMock, call
from reporter import write_results, HEADERS, _result_to_row
from models import ScreeningResult

def make_result(confidence="확실"):
    return ScreeningResult(
        group_name="무실적 마케팅_GS25",
        quote_ids=[1725, 1711],
        event_count=2,
        supplier="기프티쇼(KT엠하우스)",
        coupon_type="GS25 모바일쿠폰",
        face_value="3000원",
        validity_days="30일",
        evidence_url="https://blog.naver.com/test",
        confidence=confidence,
        confidence_reason="이미지에서 로고 확인",
        search_date="2026-04-29",
    )

def test_result_to_row_column_count_matches_headers():
    row = _result_to_row(make_result())
    assert len(row) == len(HEADERS)

def test_result_to_row_values():
    row = _result_to_row(make_result())
    assert row[0] == "무실적 마케팅_GS25"
    assert row[1] == 1725
    assert row[2] == 2
    assert row[3] == "기프티쇼(KT엠하우스)"
    assert row[8] == "확실"

def test_result_to_row_handles_none_fields():
    r = make_result()
    r.supplier = None
    r.face_value = None
    row = _result_to_row(r)
    assert row[3] == ""
    assert row[5] == ""

def test_write_results_creates_new_tab_and_writes():
    mock_ws = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.side_effect = Exception("not found")
    mock_spreadsheet.add_worksheet.return_value = mock_ws
    mock_gc = MagicMock()
    mock_gc.open_by_key.return_value = mock_spreadsheet

    with patch("reporter.get_sheet_client", return_value=mock_gc):
        write_results([make_result()])

    mock_ws.append_row.assert_called_once_with(HEADERS)
    mock_ws.append_rows.assert_called_once()
    rows = mock_ws.append_rows.call_args[0][0]
    assert rows[0][0] == "무실적 마케팅_GS25"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
py -m pytest tests/test_reporter.py -v
```
Expected: `ModuleNotFoundError: No module named 'reporter'`

- [ ] **Step 3: reporter.py 구현**

```python
# 입찰 스크리닝/reporter.py
import gspread
from google.oauth2.service_account import Credentials
from datetime import date
from models import ScreeningResult
from config import GOOGLE_SHEETS_KEY_PATH, OUTPUT_SPREADSHEET_ID

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADERS = [
    "그룹명", "대표 견적번호", "포함 건수", "추정 공급사",
    "쿠폰 종류", "액면가", "유효기간", "출처 URL",
    "신뢰도", "판정 근거", "검색일",
]

def get_sheet_client():
    creds = Credentials.from_service_account_file(GOOGLE_SHEETS_KEY_PATH, scopes=SCOPES)
    return gspread.authorize(creds)

def _result_to_row(r: ScreeningResult) -> list:
    return [
        r.group_name,
        r.quote_ids[0] if r.quote_ids else "",
        r.event_count,
        r.supplier or "",
        r.coupon_type or "",
        r.face_value or "",
        r.validity_days or "",
        r.evidence_url or "",
        r.confidence,
        r.confidence_reason,
        r.search_date,
    ]

def write_results(results: list) -> str:
    gc = get_sheet_client()
    spreadsheet = gc.open_by_key(OUTPUT_SPREADSHEET_ID)
    tab_name = date.today().isoformat()

    try:
        ws = spreadsheet.worksheet(tab_name)
    except Exception:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=500, cols=len(HEADERS))
        ws.append_row(HEADERS)

    rows = [_result_to_row(r) for r in results]
    if rows:
        ws.append_rows(rows)

    return f"https://docs.google.com/spreadsheets/d/{OUTPUT_SPREADSHEET_ID}"
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
py -m pytest tests/test_reporter.py -v
```
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add reporter.py tests/test_reporter.py
git commit -m "feat: add google sheets reporter"
```

---

## Task 9: 메인 오케스트레이터

**Files:**
- Create: `입찰 스크리닝/screening.py`

- [ ] **Step 1: screening.py 구현**

```python
# 입찰 스크리닝/screening.py
import sys
import argparse
from loader import load_excel, deduplicate_events
from grouper import group_events
from searcher import search_group
from parser import analyze_group
from reporter import write_results

def run_pipeline(filepath: str):
    print(f"\n[1/5] 엑셀 로딩: {filepath}")
    df = load_excel(filepath)
    events = deduplicate_events(df)
    print(f"      {len(df)}건 → 중복 제거 후 {len(events)}건")

    print("\n[2/5] Claude 이벤트 그룹핑 중...")
    groups = group_events(events)
    print(f"      {len(groups)}개 그룹 생성")
    for g in groups:
        print(f"      - {g.group_name} ({len(g.quote_ids)}건)")

    print("\n[3/5] 웹 검색 중...")
    search_results_map = {}
    for i, group in enumerate(groups, 1):
        print(f"      [{i}/{len(groups)}] {group.group_name}", end=" ")
        sr = search_group(group)
        search_results_map[group.group_name] = sr
        print(f"→ {len(sr.urls)}개 URL")

    print("\n[4/5] 블로그 스크래핑 & 이미지 분석 중...")
    screening_results = []
    for i, group in enumerate(groups, 1):
        print(f"      [{i}/{len(groups)}] {group.group_name}", end=" ")
        result = analyze_group(group, search_results_map[group.group_name])
        screening_results.append(result)
        supplier_str = result.supplier or "미확인"
        print(f"→ {supplier_str} [{result.confidence}]")

    print("\n[5/5] Google Sheets 기록 중...")
    url = write_results(screening_results)

    confirmed = sum(1 for r in screening_results if r.confidence == "확실")
    estimated = sum(1 for r in screening_results if r.confidence == "추정")
    unknown = sum(1 for r in screening_results if r.confidence == "미확인")

    print(f"\n완료! 총 {len(screening_results)}개 그룹 분석")
    print(f"  확실: {confirmed}건 / 추정: {estimated}건 / 미확인: {unknown}건")
    print(f"  결과 시트: {url}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="우리카드 미낙찰 경쟁사 스크리닝")
    parser.add_argument("filepath", help="미낙찰 엑셀 파일 경로")
    args = parser.parse_args()
    run_pipeline(args.filepath)
```

- [ ] **Step 2: 전체 테스트 통과 확인**

```bash
py -m pytest tests/ -v
```
Expected: 모든 테스트 통과 (17개 이상)

- [ ] **Step 3: 커밋**

```bash
git add screening.py
git commit -m "feat: add main pipeline orchestrator"
```

---

## Task 10: 스모크 테스트 (실제 실행)

**전제조건:** `.env` 파일에 실제 API 키 4개가 입력되어 있어야 한다.

- [ ] **Step 1: 소규모 테스트 — 엑셀 상위 10건만으로 검증**

```bash
py -c "
import pandas as pd
df = pd.read_excel('공고목록_20260429114148.xlsx')
df.head(10).to_excel('test_10rows.xlsx', index=False)
print('test_10rows.xlsx 생성 완료')
"
```

- [ ] **Step 2: 파이프라인 실행 (10건)**

```bash
py screening.py test_10rows.xlsx
```
Expected 출력 형태:
```
[1/5] 엑셀 로딩: test_10rows.xlsx
      10건 → 중복 제거 후 N건

[2/5] Claude 이벤트 그룹핑 중...
      M개 그룹 생성

[3/5] 웹 검색 중...
      ...

[4/5] 블로그 스크래핑 & 이미지 분석 중...
      ...

[5/5] Google Sheets 기록 중...

완료! 총 M개 그룹 분석
  확실: X건 / 추정: Y건 / 미확인: Z건
  결과 시트: https://docs.google.com/spreadsheets/d/...
```

- [ ] **Step 3: Google Sheets 확인**

브라우저에서 결과 URL을 열어 오늘 날짜 탭에 데이터가 기록됐는지 확인한다.
컬럼 11개(그룹명 ~ 검색일)가 채워져 있어야 한다.

- [ ] **Step 4: 전체 파일로 실행**

```bash
py screening.py "공고목록_20260429114148.xlsx"
```

- [ ] **Step 5: 임시 파일 정리 및 최종 커밋**

```bash
del test_10rows.xlsx
git add .
git commit -m "feat: competitor screening pipeline complete"
```
