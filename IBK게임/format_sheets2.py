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

def rgb(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}

COLOR_MAIN    = rgb(30, 78, 121)
COLOR_COL_HDR = rgb(55, 122, 183)
COLOR_SECTION = rgb(197, 217, 241)
COLOR_ALT     = rgb(235, 243, 254)
COLOR_WHITE   = rgb(255, 255, 255)
COLOR_LIGHT   = rgb(240, 245, 255)

def bold_border():
    return {"style": "SOLID_MEDIUM", "color": rgb(55, 122, 183)}

def thin_border():
    return {"style": "SOLID", "color": rgb(200, 215, 235)}

def repeat_cell(sid, r1, r2, c1, c2, bg=None, bold=False, font_size=10,
                text_color=None, h_align="LEFT", v_align="MIDDLE", wrap="WRAP"):
    fmt = {
        "textFormat": {
            "bold": bold,
            "fontSize": font_size,
            "foregroundColor": text_color or rgb(30, 30, 30),
            "fontFamily": "Arial",
        },
        "horizontalAlignment": h_align,
        "verticalAlignment": v_align,
        "wrapStrategy": wrap,
        "padding": {"top": 4, "bottom": 4, "left": 6, "right": 6},
    }
    if bg:
        fmt["backgroundColor"] = bg
    return {
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                      "startColumnIndex": c1, "endColumnIndex": c2},
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy,padding)",
        }
    }

def set_border(sid, r1, r2, c1, c2, inner=True):
    b_thin = thin_border()
    b_bold = bold_border()
    req = {
        "updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                      "startColumnIndex": c1, "endColumnIndex": c2},
            "top": b_bold, "bottom": b_bold, "left": b_bold, "right": b_bold,
        }
    }
    if inner:
        req["updateBorders"]["innerHorizontal"] = b_thin
        req["updateBorders"]["innerVertical"] = b_thin
    return req

def set_row_h(sid, row, h):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": row, "endIndex": row+1},
        "properties": {"pixelSize": h}, "fields": "pixelSize"}}

def set_rows_h(sid, r1, r2, h):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r1, "endIndex": r2},
        "properties": {"pixelSize": h}, "fields": "pixelSize"}}

def set_col_w(sid, col, w):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": col, "endIndex": col+1},
        "properties": {"pixelSize": w}, "fields": "pixelSize"}}

def merge(sid, r1, r2, c1, c2):
    return {"mergeCells": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "mergeType": "MERGE_ALL"}}

def freeze(sid, rows, cols=0):
    return {"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {
            "frozenRowCount": rows, "frozenColumnCount": cols}},
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}}

# ── 데이터 행 교대 색상 적용 (짝수/홀수 행)
def alt_rows(sid, r1, r2, c1, c2, section_rows=None):
    reqs = []
    section_rows = section_rows or []
    for r in range(r1, r2):
        if r in section_rows:
            continue
        bg = COLOR_ALT if (r - r1) % 2 == 0 else COLOR_WHITE
        reqs.append(repeat_cell(sid, r, r+1, c1, c2, bg=bg, font_size=10, v_align="MIDDLE"))
    return reqs

requests = []

# ══════════════════════════════════════════════
# TS-앱(사용자)
# ══════════════════════════════════════════════
sid = sheet_map["TS-앱(사용자)"]
NUM_COLS = 9
requests += [
    freeze(sid, 5),
    # 컬럼 너비
    set_col_w(sid, 0, 52),   # NO.
    set_col_w(sid, 1, 95),   # 기능
    set_col_w(sid, 2, 245),  # 경로
    set_col_w(sid, 3, 305),  # 테스트 내용
    set_col_w(sid, 4, 360),  # 예상결과
    set_col_w(sid, 5, 90),   # iOS
    set_col_w(sid, 6, 90),   # AOS
    set_col_w(sid, 7, 200),  # 결과내용
    set_col_w(sid, 8, 150),  # 조치결과
    # 행 높이
    set_row_h(sid, 0, 48),
    set_row_h(sid, 1, 28),
    set_row_h(sid, 2, 28),
    set_row_h(sid, 3, 8),
    set_row_h(sid, 4, 38),
    set_rows_h(sid, 5, 50, 36),
    # Row0: 타이틀
    merge(sid, 0, 1, 0, NUM_COLS),
    repeat_cell(sid, 0, 1, 0, NUM_COLS, bg=COLOR_MAIN, bold=True, font_size=14,
                text_color=COLOR_WHITE, v_align="MIDDLE"),
    # Row1~2: 메타
    repeat_cell(sid, 1, 2, 0, 1, bg=COLOR_SECTION, bold=True, font_size=9, v_align="MIDDLE"),
    repeat_cell(sid, 1, 3, 1, NUM_COLS, bg=COLOR_LIGHT, font_size=9, v_align="MIDDLE"),
    # Row4: 컬럼 헤더
    repeat_cell(sid, 4, 5, 0, NUM_COLS, bg=COLOR_COL_HDR, bold=True, font_size=10,
                text_color=COLOR_WHITE, h_align="CENTER", v_align="MIDDLE"),
    # 테두리
    set_border(sid, 4, 50, 0, NUM_COLS),
]
# 섹션 행 색상
SECTION_ROWS_APP = [5, 13, 20, 27]
for r in SECTION_ROWS_APP:
    requests += [
        repeat_cell(sid, r, r+1, 0, NUM_COLS, bg=COLOR_SECTION, bold=True, font_size=9,
                    h_align="LEFT", v_align="MIDDLE"),
        set_row_h(sid, r, 26),
    ]
# 데이터 행 교대 색상
requests += alt_rows(sid, 6, 50, 0, NUM_COLS, section_rows=SECTION_ROWS_APP)
# NO. 컬럼 중앙 정렬
requests.append(repeat_cell(sid, 5, 50, 0, 1, h_align="CENTER", v_align="MIDDLE", font_size=10))
# iOS/AOS 결과 컬럼 중앙 정렬
for col in [5, 6]:
    requests.append(repeat_cell(sid, 5, 50, col, col+1, h_align="CENTER", v_align="MIDDLE", font_size=10))

# ══════════════════════════════════════════════
# TS-관리자(CP)
# ══════════════════════════════════════════════
sid = sheet_map["TS-관리자(CP)"]
NUM_COLS = 8
requests += [
    freeze(sid, 5),
    set_col_w(sid, 0, 52),
    set_col_w(sid, 1, 105),
    set_col_w(sid, 2, 260),
    set_col_w(sid, 3, 305),
    set_col_w(sid, 4, 385),
    set_col_w(sid, 5, 88),
    set_col_w(sid, 6, 185),
    set_col_w(sid, 7, 145),
    set_row_h(sid, 0, 48),
    set_row_h(sid, 1, 28),
    set_row_h(sid, 2, 28),
    set_row_h(sid, 3, 8),
    set_row_h(sid, 4, 38),
    set_rows_h(sid, 5, 100, 36),
    merge(sid, 0, 1, 0, NUM_COLS),
    repeat_cell(sid, 0, 1, 0, NUM_COLS, bg=COLOR_MAIN, bold=True, font_size=14,
                text_color=COLOR_WHITE, v_align="MIDDLE"),
    repeat_cell(sid, 1, 2, 0, 1, bg=COLOR_SECTION, bold=True, font_size=9, v_align="MIDDLE"),
    repeat_cell(sid, 1, 3, 1, NUM_COLS, bg=COLOR_LIGHT, font_size=9, v_align="MIDDLE"),
    repeat_cell(sid, 4, 5, 0, NUM_COLS, bg=COLOR_COL_HDR, bold=True, font_size=10,
                text_color=COLOR_WHITE, h_align="CENTER", v_align="MIDDLE"),
    set_border(sid, 4, 100, 0, NUM_COLS),
]
SECTION_ROWS_CP = [5, 26, 55, 68, 85]
for r in SECTION_ROWS_CP:
    requests += [
        repeat_cell(sid, r, r+1, 0, NUM_COLS, bg=COLOR_SECTION, bold=True, font_size=9,
                    h_align="LEFT", v_align="MIDDLE"),
        set_row_h(sid, r, 26),
    ]
requests += alt_rows(sid, 6, 100, 0, NUM_COLS, section_rows=SECTION_ROWS_CP)
requests.append(repeat_cell(sid, 5, 100, 0, 1, h_align="CENTER", v_align="MIDDLE", font_size=10))
requests.append(repeat_cell(sid, 5, 100, 5, 6, h_align="CENTER", v_align="MIDDLE", font_size=10))

# ══════════════════════════════════════════════
# 수정 요청
# ══════════════════════════════════════════════
sid = sheet_map["수정 요청"]
NUM_COLS = 6
requests += [
    freeze(sid, 3),
    set_col_w(sid, 0, 52),
    set_col_w(sid, 1, 210),
    set_col_w(sid, 2, 430),
    set_col_w(sid, 3, 100),
    set_col_w(sid, 4, 105),
    set_col_w(sid, 5, 150),
    set_row_h(sid, 0, 48),
    set_row_h(sid, 1, 8),
    set_row_h(sid, 2, 38),
    set_rows_h(sid, 3, 40, 36),
    merge(sid, 0, 1, 0, NUM_COLS),
    repeat_cell(sid, 0, 1, 0, NUM_COLS, bg=COLOR_MAIN, bold=True, font_size=14,
                text_color=COLOR_WHITE, v_align="MIDDLE"),
    repeat_cell(sid, 2, 3, 0, NUM_COLS, bg=COLOR_COL_HDR, bold=True, font_size=10,
                text_color=COLOR_WHITE, h_align="CENTER", v_align="MIDDLE"),
    set_border(sid, 2, 40, 0, NUM_COLS),
]
requests += alt_rows(sid, 3, 40, 0, NUM_COLS)
requests.append(repeat_cell(sid, 3, 40, 0, 1, h_align="CENTER", v_align="MIDDLE", font_size=10))
requests.append(repeat_cell(sid, 3, 40, 3, 4, h_align="CENTER", v_align="MIDDLE", font_size=10))

# ══════════════════════════════════════════════
# 테스트 계정
# ══════════════════════════════════════════════
sid = sheet_map["테스트 계정"]
NUM_COLS = 6
requests += [
    set_col_w(sid, 0, 130),
    set_col_w(sid, 1, 185),
    set_col_w(sid, 2, 105),
    set_col_w(sid, 3, 185),
    set_col_w(sid, 4, 145),
    set_col_w(sid, 5, 260),
    set_row_h(sid, 0, 48),
    set_row_h(sid, 1, 8),
    set_row_h(sid, 2, 30),
    set_row_h(sid, 7, 30),
    set_row_h(sid, 8, 36),
    set_rows_h(sid, 9, 20, 30),
    merge(sid, 0, 1, 0, NUM_COLS),
    repeat_cell(sid, 0, 1, 0, NUM_COLS, bg=COLOR_MAIN, bold=True, font_size=14,
                text_color=COLOR_WHITE, v_align="MIDDLE"),
    # URL 섹션
    repeat_cell(sid, 2, 3, 0, 3, bg=COLOR_SECTION, bold=True, font_size=9, h_align="CENTER"),
    repeat_cell(sid, 2, 3, 3, 6, bg=COLOR_SECTION, bold=True, font_size=9, h_align="CENTER"),
    repeat_cell(sid, 3, 7, 0, 3, bg=COLOR_LIGHT, font_size=10),
    repeat_cell(sid, 3, 7, 3, 6, bg=COLOR_LIGHT, font_size=10),
    set_border(sid, 2, 7, 0, 6),
    # CI 섹션
    merge(sid, 7, 8, 0, NUM_COLS),
    repeat_cell(sid, 7, 8, 0, NUM_COLS, bg=COLOR_SECTION, bold=True, font_size=9, h_align="LEFT"),
    repeat_cell(sid, 8, 9, 0, NUM_COLS, bg=COLOR_COL_HDR, bold=True, font_size=10,
                text_color=COLOR_WHITE, h_align="CENTER"),
    set_border(sid, 8, 20, 0, NUM_COLS),
]
requests += alt_rows(sid, 9, 20, 0, NUM_COLS)
# 필요조건 섹션
requests += [
    merge(sid, 14, 15, 0, NUM_COLS),
    repeat_cell(sid, 14, 15, 0, NUM_COLS, bg=COLOR_SECTION, bold=True, font_size=9),
    set_border(sid, 14, 20, 0, NUM_COLS),
]

# 실행
result = sheets.batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={"requests": requests}
).execute()
print(f"서식 적용 완료: {len(result.get('replies', []))}개 요청 처리")
