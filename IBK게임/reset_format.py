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

requests = []

for title, sid in sheet_map.items():
    if title == "시트1":
        continue

    # 1) 모든 병합 해제
    requests.append({
        "unmergeCells": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 200,
                      "startColumnIndex": 0, "endColumnIndex": 20}
        }
    })

    # 2) 서식 초기화
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 200,
                      "startColumnIndex": 0, "endColumnIndex": 20},
            "cell": {"userEnteredFormat": {}},
            "fields": "userEnteredFormat",
        }
    })

    # 3) 열 너비 기본값 복원 (100px)
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 20},
            "properties": {"pixelSize": 100},
            "fields": "pixelSize",
        }
    })

    # 4) 행 높이 기본값 복원 (21px)
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS",
                      "startIndex": 0, "endIndex": 200},
            "properties": {"pixelSize": 21},
            "fields": "pixelSize",
        }
    })

    # 5) 고정 해제
    requests.append({
        "updateSheetProperties": {
            "properties": {"sheetId": sid,
                           "gridProperties": {"frozenRowCount": 0, "frozenColumnCount": 0}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }
    })

result = sheets.batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={"requests": requests}
).execute()
print(f"초기화 완료: {len(result.get('replies', []))}개 요청 처리")
