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

C_YELLOW = rgb(255, 229, 153)
C_WHITE  = rgb(255, 255, 255)
C_BLACK  = rgb(0, 0, 0)

def repeat(sid, r1, r2, c1, c2, bg, bold=False, size=10, h="LEFT"):
    return {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": {
            "backgroundColor": bg,
            "textFormat": {"bold": bold, "fontSize": size,
                           "foregroundColor": C_BLACK, "fontFamily": "Arial"},
            "horizontalAlignment": h,
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP",
            "padding": {"top": 3, "bottom": 3, "left": 5, "right": 5},
        }},
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy,padding)",
    }}

def row_h(sid, r, h):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r, "endIndex": r+1},
        "properties": {"pixelSize": h}, "fields": "pixelSize"}}

sid = sheet_map["TS-앱(사용자)"]
NC = 9

# row 44 (0-indexed: 43) = 섹션 헤더 → 노란색
# rows 45-49 (0-indexed: 44-48) = 데이터 행 → 흰색 (이미 적용됨, 정렬만 보정)
requests = [
    repeat(sid, 43, 44, 0, NC, bg=C_YELLOW, bold=True, size=9, h="LEFT"),
    row_h(sid, 43, 22),
    # NO. 중앙 정렬
    repeat(sid, 44, 49, 0, 1, bg=C_WHITE, bold=False, size=10, h="CENTER"),
    # 기능 중앙
    repeat(sid, 44, 49, 1, 2, bg=C_WHITE, bold=False, size=10, h="CENTER"),
    # iOS/AOS 중앙
    repeat(sid, 44, 49, 5, 7, bg=C_WHITE, bold=False, size=10, h="CENTER"),
]

result = sheets.batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={"requests": requests}
).execute()
print(f"서식 적용 완료: {len(result.get('replies', []))}개 요청 처리")
