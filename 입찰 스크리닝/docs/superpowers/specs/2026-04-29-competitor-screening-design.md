# 우리카드 입찰 미낙찰건 경쟁사 스크리닝 자동화 설계

## 개요

우리카드 구매시스템에서 다운로드한 미낙찰건 엑셀 파일을 입력으로 받아,
네이버 블로그/카페/티스토리 등 국내 웹 검색을 통해 쿠폰 공급사·종류·액면가·유효기간을
자동으로 파악하고 Google Sheets에 기록하는 파이프라인.

## 입력 데이터

- **파일 형식:** `.xlsx` (우리카드 구매시스템 다운로드)
- **컬럼 구조:** 순번, 상태, 처리일, 견적번호, 견적명, 담당자명, 시작일시, 마감일시, 낙찰기준
- **현재 샘플:** `공고목록_20260429114148.xlsx` — 852행
- **핵심 컬럼:** `견적명` (검색 키워드 생성 기반), `견적번호` (중복 제거 기준)

## 실행 방법

```bash
py screening.py 공고목록_20260429114148.xlsx
```

---

## 파이프라인 5단계

### Phase 1 — 전처리 & 1차 중복 제거

- `pandas`로 Excel 로드
- `견적번호` 기준 중복 제거 → 동일 이벤트 재입찰 건을 최신 1건으로 통합
- 예상: 852건 → ~150~200건

### Phase 2 — Claude 의미 그룹핑 & 키워드 생성

unique 견적명 목록 전체를 Claude Sonnet 4.6에 전달하여 아래 작업을 단일 API 호출로 처리:

**그룹핑 규칙:**
- 월/차수가 달라도 동일 이벤트 시리즈 → 같은 그룹 (예: `'26년 3월 무실적(GS25)`와 `'26년 4월 무실적(GS25)`)
- 브랜드가 다르면 분리 (예: 무실적(GS25) vs 무실적(배민))
- 성격이 다른 이벤트는 분리 (퀴즈이벤트 vs 이용활성화 캠페인)

**키워드 생성 원칙:**
- 소비자 관점의 마케팅 언어 사용 (행정 용어 제거)
- `우리카드 + 브랜드명` 조합 필수 포함
- 네이버 블로그 검색에 최적화된 자연어
- 그룹당 3~5개 생성

**Claude 출력 형식 (JSON):**
```json
[
  {
    "group_name": "무실적회원 이용조건부 마케팅_GS25",
    "quote_ids": [1725, 1711],
    "brands": ["GS25"],
    "search_keywords": [
      "우리카드 GS25 쿠폰 이벤트",
      "우리카드 편의점 혜택",
      "우리카드 무실적 GS25",
      "우리카드 GS25 모바일쿠폰"
    ]
  }
]
```

### Phase 3 — 웹 검색 (Tavily, 병렬)

- `tavily-python` SDK 사용
- 그룹당 키워드 3~5개를 `concurrent.futures.ThreadPoolExecutor`로 병렬 실행
- 설정: `search_depth="advanced"`, 결과 수 최대 5개/키워드
- 중복 URL 제거 후 Phase 4로 전달
- 예상 처리: 그룹당 최대 25개 URL

### Phase 4 — 블로그 스크래핑 & 이미지 분석

**4-A. 텍스트 추출:**
- `requests` + `BeautifulSoup`으로 블로그 본문 크롤링
- 네이버 블로그, 티스토리, 카페 등 주요 플랫폼 파싱

**4-B. 이미지 URL 추출 및 Claude Vision 분석:**
- `<img>` 태그에서 이미지 URL 추출
- 100×100px 미만 아이콘/배너 제외 → 쿠폰/기프티콘 스크린샷으로 보이는 것만 선별
- 블로그 게시글당 최대 5개 이미지 분석 (비용 제어)
- 이미지를 base64 인코딩하여 Claude Vision API 전달
- 접근 불가(403/차단) 이미지는 건너뜀
- 아래 공급사 식별 요청:

**인식 대상 공급사 목록:**
| 공급사 | 주요 식별 단서 |
|--------|---------------|
| GS엠비즈 | GS25 계열 쿠폰 UI, gsmbiz.co.kr 도메인 |
| 즐거운 | 즐거운e쿠폰 로고/URL, jeulgeoun.com |
| 쿠프마케팅 | COOPON 로고, coopon.co.kr 도메인 |
| 네이버파이낸셜 | 네이버페이 포인트/기프트카드 UI, pay.naver.com |
| 윈큐브마케팅 | wincubemkt 도메인/로고 |
| 기프티쇼(KT엠하우스) | giftishow.com, 기프티쇼 로고 |
| 케이티알파 | KT알파쇼핑, kt-alpha.co.kr 도메인 |
| 다우기술 | daou.co.kr, 다우기술 로고 |
| 엠트웰브 | giftpop.co.kr, 기프트팝 로고 |
| 카카오선물하기 | gift.kakao.com, 카카오 UI |
| 이지코드 | easycode 도메인/로고 |
| CJ올리브네트웍스 | CJ ONE, cjone.com |
| 모바일리더 | mobileleader 도메인 |

**4-C. 텍스트 + 이미지 종합 파싱 프롬프트:**

```
당신은 신용카드 모바일쿠폰 업계 분석가입니다.
아래는 "우리카드 [이벤트명]" 관련 블로그/카페 검색 결과입니다.

[텍스트 본문]
[이미지 분석 결과]

인식 대상 공급사: GS엠비즈, 즐거운, 쿠프마케팅, 네이버파이낸셜, 윈큐브마케팅,
기프티쇼(KT엠하우스), 케이티알파, 다우기술, 엠트웰브(기프트팝),
카카오선물하기, 이지코드, CJ올리브네트웍스, 모바일리더

다음 항목을 JSON으로 추출하세요:
- supplier: 공급사명 (위 목록에서 매칭. 없으면 null)
- coupon_type: 쿠폰 종류
- face_value: 액면가 (예: "3,000원". 불명확하면 null)
- validity_days: 유효기간 (예: "30일". 불명확하면 null)
- evidence_url: 근거 URL
- confidence: "확실" | "추정" | "미확인"
- confidence_reason: 판정 근거 한 줄

공급사를 특정할 수 없으면 반드시 null. 절대 추측 금지.
```

### Phase 5 — Google Sheets 기록

- `gspread` + 서비스 계정 (`~/.claude/google-sheets-key.json`)
- `OUTPUT_SPREADSHEET_ID` 스프레드시트 내에 실행 날짜명 탭 신규 생성 (예: `2026-04-29`)
- 같은 날 재실행 시 기존 탭에 append
- 블로그 스크래핑 실패(403/timeout) 시 해당 URL 건너뛰고 계속 진행, 결과에 "스크래핑 실패" 표기

**출력 컬럼:**
| 그룹명 | 대표 견적번호 | 포함 건수 | 추정 공급사 | 쿠폰 종류 | 액면가 | 유효기간 | 출처 URL | 신뢰도 | 판정 근거 | 검색일 |

---

## 신뢰도 기준

| 등급 | 조건 |
|------|------|
| 확실 | 이미지에서 공급사 로고/URL 명확히 식별, 또는 텍스트에 공급사명 직접 언급 |
| 추정 | 쿠폰 종류/플랫폼 UI는 확인되나 공급사 직접 특정 불가 |
| 미확인 | 관련 게시글 없거나 내용 불충분 |

---

## 기술 스택

| 라이브러리 | 용도 |
|------------|------|
| `pandas`, `openpyxl` | Excel 로드 & 전처리 |
| `anthropic` | Claude Sonnet 4.6 (그룹핑, 파싱, Vision) |
| `tavily-python` | 웹 검색 |
| `requests`, `beautifulsoup4` | 블로그 스크래핑 |
| `gspread` | Google Sheets 기록 |
| `concurrent.futures` | 병렬 검색 |

## 환경 변수 (.env)

```
ANTHROPIC_API_KEY=...
TAVILY_API_KEY=...
GOOGLE_SHEETS_KEY_PATH=~/.claude/google-sheets-key.json
OUTPUT_SPREADSHEET_ID=...   # 결과 저장할 시트 ID
```

## 파일 구조

```
입찰 스크리닝/
├── screening.py          # 메인 실행 파일
├── .env                  # API 키 (git 제외)
├── .gitignore
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-29-competitor-screening-design.md
```
