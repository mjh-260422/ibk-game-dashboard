import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1x-_P47B9wl5LZ1Ii_vy1ZxApZSdKOHeN0AN-zo8fHUY"
KEY_FILE = "C:/Users/jihye/.claude/google-sheets-key.json"

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
service = build("sheets", "v4", credentials=creds)
sheets = service.spreadsheets()

# 시트 ID 조회
meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
sheet_map = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
print("시트 목록:", sheet_map)

# 색상 정의
def rgb(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}

COLOR_HEADER_MAIN   = rgb(30, 78, 121)    # 짙은 네이비 - 프로젝트/섹션 헤더
COLOR_HEADER_COL    = rgb(55, 122, 183)   # 파랑 - 컬럼 헤더
COLOR_SECTION       = rgb(197, 217, 241)  # 연한 파랑 - 섹션 구분 행
COLOR_ALT_ROW       = rgb(235, 243, 254)  # 아주 연한 파랑 - 홀수 데이터 행 (선택 시 사용)
COLOR_WHITE         = rgb(255, 255, 255)
COLOR_TEXT_WHITE    = rgb(255, 255, 255)
COLOR_TEXT_DARK     = rgb(30, 30, 30)
COLOR_BORDER        = rgb(180, 199, 231)

def cell_format(bg=None, bold=False, font_size=10, text_color=None,
                h_align="LEFT", v_align="MIDDLE", wrap="WRAP"):
    fmt = {
        "textFormat": {
            "bold": bold,
            "fontSize": font_size,
            "foregroundColor": text_color or COLOR_TEXT_DARK,
        },
        "horizontalAlignment": h_align,
        "verticalAlignment": v_align,
        "wrapStrategy": wrap,
    }
    if bg:
        fmt["backgroundColor"] = bg
    return fmt

def repeat_cell(sheet_id, row, col, end_col, fmt, end_row=None):
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row,
                "endRowIndex": end_row if end_row else row + 1,
                "startColumnIndex": col,
                "endColumnIndex": end_col,
            },
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }
    }

def merge(sheet_id, row, col, end_col, end_row=None):
    return {
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row,
                "endRowIndex": end_row if end_row else row + 1,
                "startColumnIndex": col,
                "endColumnIndex": end_col,
            },
            "mergeType": "MERGE_ALL",
        }
    }

def set_col_width(sheet_id, col, width_px):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": col,
                "endIndex": col + 1,
            },
            "properties": {"pixelSize": width_px},
            "fields": "pixelSize",
        }
    }

def set_row_height(sheet_id, row, height_px):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": row,
                "endIndex": row + 1,
            },
            "properties": {"pixelSize": height_px},
            "fields": "pixelSize",
        }
    }

def freeze(sheet_id, rows, cols=0):
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": rows, "frozenColumnCount": cols},
            },
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }
    }

def border_range(sheet_id, r1, c1, r2, c2):
    b = {"style": "SOLID", "color": COLOR_BORDER}
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": r1, "endRowIndex": r2,
                "startColumnIndex": c1, "endColumnIndex": c2,
            },
            "top": b, "bottom": b, "left": b, "right": b,
            "innerHorizontal": b, "innerVertical": b,
        }
    }

requests = []

# ─────────────────────────────────────────────
# 1) TS-앱(사용자)
# ─────────────────────────────────────────────
sid = sheet_map["TS-앱(사용자)"]
requests += [
    freeze(sid, 5, 0),
    # 컬럼 너비
    set_col_width(sid, 0, 50),   # NO.
    set_col_width(sid, 1, 90),   # 기능
    set_col_width(sid, 2, 240),  # 경로
    set_col_width(sid, 3, 300),  # 테스트 내용
    set_col_width(sid, 4, 350),  # 예상결과
    set_col_width(sid, 5, 90),   # iOS 결과
    set_col_width(sid, 6, 90),   # AOS 결과
    set_col_width(sid, 7, 200),  # 결과 내용
    set_col_width(sid, 8, 150),  # 조치결과
    # 행 높이
    set_row_height(sid, 0, 40),
    set_row_height(sid, 4, 36),
    # 머지
    merge(sid, 0, 1, 9),   # 프로젝트 제목
    merge(sid, 1, 1, 3), merge(sid, 1, 3, 5), merge(sid, 1, 5, 9),
    merge(sid, 2, 1, 3), merge(sid, 2, 3, 5), merge(sid, 2, 5, 9),
    # Row 0: 타이틀
    repeat_cell(sid, 0, 0, 9, cell_format(bg=COLOR_HEADER_MAIN, bold=True, font_size=13,
                                           text_color=COLOR_TEXT_WHITE, h_align="LEFT")),
    set_row_height(sid, 0, 44),
    # Row 1~2: 메타 정보
    repeat_cell(sid, 1, 0, 1, cell_format(bg=COLOR_SECTION, bold=True, font_size=9)),
    repeat_cell(sid, 1, 1, 9, cell_format(bg=rgb(240,245,255), font_size=9)),
    repeat_cell(sid, 2, 0, 1, cell_format(bg=COLOR_SECTION, bold=True, font_size=9)),
    repeat_cell(sid, 2, 1, 9, cell_format(bg=rgb(240,245,255), font_size=9)),
    # Row 4: 컬럼 헤더
    repeat_cell(sid, 4, 0, 9, cell_format(bg=COLOR_HEADER_COL, bold=True, font_size=10,
                                            text_color=COLOR_TEXT_WHITE, h_align="CENTER")),
    set_row_height(sid, 4, 36),
    # 보더
    border_range(sid, 4, 0, 50, 9),
]
# 섹션 행 강조 (row 5=메인, 13=시작모달, 21=종료, 29=Failsafe)
for sec_row in [5, 13, 21, 28]:
    requests.append(
        repeat_cell(sid, sec_row, 0, 9,
                    cell_format(bg=COLOR_SECTION, bold=True, font_size=9, h_align="LEFT"))
    )
    requests.append(set_row_height(sid, sec_row, 24))

# ─────────────────────────────────────────────
# 2) TS-관리자(CP)
# ─────────────────────────────────────────────
sid = sheet_map["TS-관리자(CP)"]
requests += [
    freeze(sid, 5, 0),
    set_col_width(sid, 0, 50),
    set_col_width(sid, 1, 100),
    set_col_width(sid, 2, 260),
    set_col_width(sid, 3, 300),
    set_col_width(sid, 4, 380),
    set_col_width(sid, 5, 85),
    set_col_width(sid, 6, 180),
    set_col_width(sid, 7, 140),
    set_row_height(sid, 0, 44),
    set_row_height(sid, 4, 36),
    merge(sid, 0, 1, 8),
    repeat_cell(sid, 0, 0, 8, cell_format(bg=COLOR_HEADER_MAIN, bold=True, font_size=13,
                                           text_color=COLOR_TEXT_WHITE, h_align="LEFT")),
    repeat_cell(sid, 1, 0, 1, cell_format(bg=COLOR_SECTION, bold=True, font_size=9)),
    repeat_cell(sid, 1, 1, 8, cell_format(bg=rgb(240,245,255), font_size=9)),
    repeat_cell(sid, 2, 0, 1, cell_format(bg=COLOR_SECTION, bold=True, font_size=9)),
    repeat_cell(sid, 2, 1, 8, cell_format(bg=rgb(240,245,255), font_size=9)),
    repeat_cell(sid, 4, 0, 8, cell_format(bg=COLOR_HEADER_COL, bold=True, font_size=10,
                                            text_color=COLOR_TEXT_WHITE, h_align="CENTER")),
    border_range(sid, 4, 0, 100, 8),
]
# 섹션 구분 행
for sec_row in [5, 26, 55, 68, 85]:  # 각 섹션 헤더 행
    requests.append(
        repeat_cell(sid, sec_row, 0, 8,
                    cell_format(bg=COLOR_SECTION, bold=True, font_size=9))
    )
    requests.append(set_row_height(sid, sec_row, 24))

# ─────────────────────────────────────────────
# 3) 수정 요청
# ─────────────────────────────────────────────
sid = sheet_map["수정 요청"]
requests += [
    freeze(sid, 3, 0),
    set_col_width(sid, 0, 50),
    set_col_width(sid, 1, 200),
    set_col_width(sid, 2, 420),
    set_col_width(sid, 3, 100),
    set_col_width(sid, 4, 100),
    set_col_width(sid, 5, 140),
    set_row_height(sid, 0, 44),
    set_row_height(sid, 2, 36),
    merge(sid, 0, 0, 6),
    repeat_cell(sid, 0, 0, 6, cell_format(bg=COLOR_HEADER_MAIN, bold=True, font_size=13,
                                           text_color=COLOR_TEXT_WHITE, h_align="LEFT")),
    repeat_cell(sid, 2, 0, 6, cell_format(bg=COLOR_HEADER_COL, bold=True, font_size=10,
                                            text_color=COLOR_TEXT_WHITE, h_align="CENTER")),
    border_range(sid, 2, 0, 30, 6),
]

# ─────────────────────────────────────────────
# 4) 테스트 계정
# ─────────────────────────────────────────────
sid = sheet_map["테스트 계정"]
requests += [
    set_col_width(sid, 0, 120),
    set_col_width(sid, 1, 180),
    set_col_width(sid, 2, 100),
    set_col_width(sid, 3, 180),
    set_col_width(sid, 4, 140),
    set_col_width(sid, 5, 250),
    set_row_height(sid, 0, 44),
    merge(sid, 0, 0, 6),
    repeat_cell(sid, 0, 0, 6, cell_format(bg=COLOR_HEADER_MAIN, bold=True, font_size=13,
                                           text_color=COLOR_TEXT_WHITE, h_align="LEFT")),
    # URL 섹션 헤더
    repeat_cell(sid, 2, 0, 3, cell_format(bg=COLOR_SECTION, bold=True, font_size=9)),
    repeat_cell(sid, 2, 3, 6, cell_format(bg=COLOR_SECTION, bold=True, font_size=9)),
    # CI 계정 헤더
    repeat_cell(sid, 7, 0, 6, cell_format(bg=COLOR_SECTION, bold=True, font_size=9)),
    repeat_cell(sid, 8, 0, 6, cell_format(bg=COLOR_HEADER_COL, bold=True, font_size=10,
                                            text_color=COLOR_TEXT_WHITE, h_align="CENTER")),
    border_range(sid, 2, 0, 19, 6),
    set_row_height(sid, 2, 28),
    set_row_height(sid, 7, 28),
    set_row_height(sid, 8, 32),
]

# 실행
result = sheets.batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={"requests": requests}
).execute()
print(f"서식 적용 완료: {len(result.get('replies', []))}개 요청 처리")
