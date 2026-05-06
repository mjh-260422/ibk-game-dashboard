from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1x-_P47B9wl5LZ1Ii_vy1ZxApZSdKOHeN0AN-zo8fHUY"
KEY_FILE = "C:/Users/jihye/.claude/google-sheets-key.json"

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
service = build("sheets", "v4", credentials=creds)
sheets = service.spreadsheets()

meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
sheet_map = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

# ── 신한카드 QA 색상 그대로 ──────────────────────────────
def rgb(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}

C_YELLOW     = rgb(255, 229, 153)   # #FFE599  - 프로젝트 헤더 / 섹션행
C_YLIGHT     = rgb(255, 242, 204)   # #FFF2CC  - 메타 라벨
C_GRAY_HDR   = rgb(153, 153, 153)   # #999999  - 컬럼 헤더
C_GRAY_SUB   = rgb(183, 183, 183)   # #B7B7B7  - 서브 헤더
C_WHITE      = rgb(255, 255, 255)
C_BLACK      = rgb(0, 0, 0)
C_DARKGRAY   = rgb(80, 80, 80)

def border_solid(color=None):
    c = color or rgb(180, 180, 180)
    return {"style": "SOLID", "color": c}

def fmt(bg=None, bold=False, size=10, color=None,
        h="LEFT", v="MIDDLE", wrap=True, italic=False):
    f = {
        "textFormat": {
            "bold": bold,
            "italic": italic,
            "fontSize": size,
            "foregroundColor": color or C_BLACK,
            "fontFamily": "Arial",
        },
        "horizontalAlignment": h,
        "verticalAlignment": v,
        "wrapStrategy": "WRAP" if wrap else "OVERFLOW_CELL",
        "padding": {"top": 3, "bottom": 3, "left": 5, "right": 5},
    }
    if bg:
        f["backgroundColor"] = bg
    return f

def repeat(sid, r1, r2, c1, c2, **kw):
    return {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": fmt(**kw)},
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy,padding)",
    }}

def merge(sid, r1, r2, c1, c2):
    return {"mergeCells": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "mergeType": "MERGE_ALL"}}

def col_w(sid, c, w):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c+1},
        "properties": {"pixelSize": w}, "fields": "pixelSize"}}

def row_h(sid, r, h):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r, "endIndex": r+1},
        "properties": {"pixelSize": h}, "fields": "pixelSize"}}

def rows_h(sid, r1, r2, h):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r1, "endIndex": r2},
        "properties": {"pixelSize": h}, "fields": "pixelSize"}}

def freeze(sid, rows, cols=0):
    return {"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {
            "frozenRowCount": rows, "frozenColumnCount": cols}},
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}}

def borders(sid, r1, r2, c1, c2):
    b = border_solid()
    return {"updateBorders": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "top": b, "bottom": b, "left": b, "right": b,
        "innerHorizontal": b, "innerVertical": b,
    }}

def unmerge_all(sid):
    return {"unmergeCells": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 300,
                  "startColumnIndex": 0, "endColumnIndex": 20}}}

requests = []

# ══════════════════════════════════════════════════════
# TS-앱(사용자)
#   Row0: 프로젝트 헤더
#   Row1: 테스트 시행자
#   Row2: OS
#   Row3: (spacer)
#   Row4: 컬럼 헤더 (NO. / 기능 / 경로 / 테스트 내용 / 예상결과 / iOS / AOS / 결과내용 / 조치)
#   Row5~: 섹션행 + 데이터
# ══════════════════════════════════════════════════════
sid = sheet_map["TS-앱(사용자)"]
NC = 9  # 컬럼 수

requests += [
    unmerge_all(sid),
    freeze(sid, 5),

    # ── 컬럼 너비 (신한카드 비율 참조) ──
    col_w(sid, 0, 42),   # NO.
    col_w(sid, 1, 80),   # 기능
    col_w(sid, 2, 200),  # 경로
    col_w(sid, 3, 280),  # 테스트 내용
    col_w(sid, 4, 320),  # 예상결과
    col_w(sid, 5, 72),   # iOS
    col_w(sid, 6, 72),   # AOS
    col_w(sid, 7, 180),  # 결과내용
    col_w(sid, 8, 130),  # 조치결과

    # ── 행 높이 ──
    row_h(sid, 0, 36),   # 프로젝트 헤더
    row_h(sid, 1, 22),   # 메타
    row_h(sid, 2, 22),   # 메타
    row_h(sid, 3, 8),    # spacer
    row_h(sid, 4, 32),   # 컬럼 헤더
    rows_h(sid, 5, 200, 20),  # 데이터행 기본

    # ── Row0: 프로젝트 헤더 (노란색, 굵게) ──
    merge(sid, 0, 1, 0, NC),
    repeat(sid, 0, 1, 0, NC, bg=C_YELLOW, bold=True, size=12, h="CENTER"),

    # ── Row1~2: 메타 정보 ──
    # 라벨
    repeat(sid, 1, 2, 0, 1, bg=C_YLIGHT, bold=False, size=9, h="CENTER"),
    repeat(sid, 1, 2, 2, 3, bg=C_YLIGHT, bold=False, size=9, h="CENTER"),
    repeat(sid, 1, 2, 4, 5, bg=C_YLIGHT, bold=False, size=9, h="CENTER"),
    # 값
    repeat(sid, 1, 2, 1, 2, bg=C_WHITE, size=9, h="LEFT"),
    repeat(sid, 1, 2, 3, 4, bg=C_WHITE, size=9, h="LEFT"),
    repeat(sid, 1, 2, 5, 9, bg=C_WHITE, size=9, h="LEFT"),
    repeat(sid, 2, 3, 0, 1, bg=C_YLIGHT, bold=False, size=9, h="CENTER"),
    repeat(sid, 2, 3, 2, 3, bg=C_YLIGHT, bold=False, size=9, h="CENTER"),
    repeat(sid, 2, 3, 4, 5, bg=C_YLIGHT, bold=False, size=9, h="CENTER"),
    repeat(sid, 2, 3, 1, 2, bg=C_WHITE, size=9, h="LEFT"),
    repeat(sid, 2, 3, 3, 4, bg=C_WHITE, size=9, h="LEFT"),
    repeat(sid, 2, 3, 5, 9, bg=C_WHITE, size=9, h="LEFT"),

    # ── Row4: 컬럼 헤더 (회색) ──
    repeat(sid, 4, 5, 0, NC, bg=C_GRAY_HDR, bold=False, size=10, h="CENTER", color=C_BLACK),

    # ── Row5+: 전체 데이터 영역 기본 서식 ──
    repeat(sid, 5, 200, 0, NC, bg=C_WHITE, size=10, h="LEFT"),
    # NO. 컬럼 중앙 정렬
    repeat(sid, 5, 200, 0, 1, bg=C_WHITE, size=10, h="CENTER"),
    # 기능 컬럼 중앙
    repeat(sid, 5, 200, 1, 2, bg=C_WHITE, size=10, h="CENTER"),
    # iOS / AOS 결과 중앙
    repeat(sid, 5, 200, 5, 7, bg=C_WHITE, size=10, h="CENTER"),

    # ── 테두리 ──
    borders(sid, 4, 200, 0, NC),
]

# 섹션 행 (노란색, 굵게) - 내용 기준
SECTION_ROWS_APP = [5, 13, 20, 27]
for r in SECTION_ROWS_APP:
    requests += [
        repeat(sid, r, r+1, 0, NC, bg=C_YELLOW, bold=True, size=9, h="LEFT"),
        row_h(sid, r, 22),
    ]


# ══════════════════════════════════════════════════════
# TS-관리자(CP)
# ══════════════════════════════════════════════════════
sid = sheet_map["TS-관리자(CP)"]
NC = 8

requests += [
    unmerge_all(sid),
    freeze(sid, 5),

    col_w(sid, 0, 42),
    col_w(sid, 1, 90),
    col_w(sid, 2, 210),
    col_w(sid, 3, 270),
    col_w(sid, 4, 340),
    col_w(sid, 5, 75),
    col_w(sid, 6, 160),
    col_w(sid, 7, 130),

    row_h(sid, 0, 36),
    row_h(sid, 1, 22),
    row_h(sid, 2, 22),
    row_h(sid, 3, 8),
    row_h(sid, 4, 32),
    rows_h(sid, 5, 300, 20),

    merge(sid, 0, 1, 0, NC),
    repeat(sid, 0, 1, 0, NC, bg=C_YELLOW, bold=True, size=12, h="CENTER"),

    repeat(sid, 1, 2, 0, 1, bg=C_YLIGHT, size=9, h="CENTER"),
    repeat(sid, 1, 2, 2, 3, bg=C_YLIGHT, size=9, h="CENTER"),
    repeat(sid, 1, 2, 4, 5, bg=C_YLIGHT, size=9, h="CENTER"),
    repeat(sid, 1, 2, 1, 2, bg=C_WHITE, size=9),
    repeat(sid, 1, 2, 3, 4, bg=C_WHITE, size=9),
    repeat(sid, 1, 2, 5, NC, bg=C_WHITE, size=9),
    repeat(sid, 2, 3, 0, 1, bg=C_YLIGHT, size=9, h="CENTER"),
    repeat(sid, 2, 3, 2, 3, bg=C_YLIGHT, size=9, h="CENTER"),
    repeat(sid, 2, 3, 4, 5, bg=C_YLIGHT, size=9, h="CENTER"),
    repeat(sid, 2, 3, 1, 2, bg=C_WHITE, size=9),
    repeat(sid, 2, 3, 3, 4, bg=C_WHITE, size=9),
    repeat(sid, 2, 3, 5, NC, bg=C_WHITE, size=9),

    repeat(sid, 4, 5, 0, NC, bg=C_GRAY_HDR, bold=False, size=10, h="CENTER", color=C_BLACK),

    repeat(sid, 5, 300, 0, NC, bg=C_WHITE, size=10, h="LEFT"),
    repeat(sid, 5, 300, 0, 1, bg=C_WHITE, size=10, h="CENTER"),
    repeat(sid, 5, 300, 5, 6, bg=C_WHITE, size=10, h="CENTER"),

    borders(sid, 4, 300, 0, NC),
]

SECTION_ROWS_CP = [5, 26, 55, 68, 85]
for r in SECTION_ROWS_CP:
    requests += [
        repeat(sid, r, r+1, 0, NC, bg=C_YELLOW, bold=True, size=9, h="LEFT"),
        row_h(sid, r, 22),
    ]


# ══════════════════════════════════════════════════════
# 수정 요청
# ══════════════════════════════════════════════════════
sid = sheet_map["수정 요청"]
NC = 6

requests += [
    unmerge_all(sid),
    freeze(sid, 3),

    col_w(sid, 0, 42),
    col_w(sid, 1, 200),
    col_w(sid, 2, 380),
    col_w(sid, 3, 85),
    col_w(sid, 4, 85),
    col_w(sid, 5, 130),

    row_h(sid, 0, 36),
    row_h(sid, 1, 8),
    row_h(sid, 2, 32),
    rows_h(sid, 3, 60, 20),

    merge(sid, 0, 1, 0, NC),
    repeat(sid, 0, 1, 0, NC, bg=C_YELLOW, bold=True, size=12, h="CENTER"),
    repeat(sid, 2, 3, 0, NC, bg=C_GRAY_HDR, bold=False, size=10, h="CENTER", color=C_BLACK),
    repeat(sid, 3, 60, 0, NC, bg=C_WHITE, size=10, h="LEFT"),
    repeat(sid, 3, 60, 0, 1, bg=C_WHITE, size=10, h="CENTER"),
    repeat(sid, 3, 60, 3, 5, bg=C_WHITE, size=10, h="CENTER"),

    borders(sid, 2, 60, 0, NC),
]


# ══════════════════════════════════════════════════════
# 테스트 계정
# ══════════════════════════════════════════════════════
sid = sheet_map["테스트 계정"]
NC = 6

requests += [
    unmerge_all(sid),

    col_w(sid, 0, 120),
    col_w(sid, 1, 170),
    col_w(sid, 2, 90),
    col_w(sid, 3, 160),
    col_w(sid, 4, 130),
    col_w(sid, 5, 240),

    row_h(sid, 0, 36),
    row_h(sid, 1, 8),
    row_h(sid, 2, 26),
    row_h(sid, 3, 22),
    row_h(sid, 4, 22),
    row_h(sid, 5, 22),
    row_h(sid, 6, 8),
    row_h(sid, 7, 26),
    row_h(sid, 8, 28),
    rows_h(sid, 9, 22, 22),

    merge(sid, 0, 1, 0, NC),
    repeat(sid, 0, 1, 0, NC, bg=C_YELLOW, bold=True, size=12, h="CENTER"),

    # URL 섹션
    repeat(sid, 2, 3, 0, 3, bg=C_YLIGHT, bold=True, size=9, h="CENTER"),
    repeat(sid, 2, 3, 3, 6, bg=C_YLIGHT, bold=True, size=9, h="CENTER"),
    repeat(sid, 3, 7, 0, 3, bg=C_WHITE, size=10),
    repeat(sid, 3, 7, 3, 6, bg=C_WHITE, size=10),
    borders(sid, 2, 7, 0, 6),

    # CI 계정 섹션
    merge(sid, 7, 8, 0, NC),
    repeat(sid, 7, 8, 0, NC, bg=C_YELLOW, bold=True, size=9, h="LEFT"),
    repeat(sid, 8, 9, 0, NC, bg=C_GRAY_HDR, size=10, h="CENTER", color=C_BLACK),
    repeat(sid, 9, 22, 0, NC, bg=C_WHITE, size=10),
    borders(sid, 7, 22, 0, NC),

    # 필요조건 섹션
    merge(sid, 14, 15, 0, NC),
    repeat(sid, 14, 15, 0, NC, bg=C_YLIGHT, bold=True, size=9),
    borders(sid, 14, 22, 0, NC),
]

# ── 실행 ──
result = sheets.batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={"requests": requests}
).execute()
print(f"서식 적용 완료: {len(result.get('replies', []))}개 요청 처리")
