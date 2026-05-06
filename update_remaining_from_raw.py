import re
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "17qJfmlYUXcI74oOxZqJ6DpjJ9mlBv5aRRr3gnb-fVHI"
KEY_FILE = os.path.expanduser("~/.claude/google-sheets-key.json")

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
service = build("sheets", "v4", credentials=creds)
sheets = service.spreadsheets()

# 로우 시트 읽기 (A=좌수, B=휴대폰번호, C=남은금액, 2행부터 데이터)
raw = sheets.values().get(
    spreadsheetId=SPREADSHEET_ID,
    range="'로우'!A2:C2000",
    valueRenderOption="FORMATTED_VALUE"
).execute().get("values", [])

# 복합키 룩업 빌드: (좌수구간, 전화번호) -> 남은금액
# 로우의 좌수는 "2" → 미선택관리는 "2좌"
lookup = {}
for row in raw:
    if len(row) < 3:
        continue
    zone_num = str(row[0]).strip()
    phone = re.sub(r"\D", "", str(row[1]).strip())
    amount_str = str(row[2]).strip().replace(",", "")
    if not zone_num or not phone:
        continue
    try:
        amount = int(amount_str)
    except ValueError:
        continue
    zone = zone_num + "좌"
    lookup[(zone, phone)] = amount

print(f"로우 데이터 로드: {len(lookup)}건")

# 미선택 관리 시트 읽기 (A2:F2000)
mgmt = sheets.values().get(
    spreadsheetId=SPREADSHEET_ID,
    range="'미선택 관리'!A2:F2000",
    valueRenderOption="FORMATTED_VALUE"
).execute().get("values", [])

print(f"미선택 관리 데이터: {len(mgmt)}행")

updates = []
matched = 0
for i, row in enumerate(mgmt):
    zone = str(row[2]).strip() if len(row) > 2 else ""
    phone_raw = str(row[3]).strip() if len(row) > 3 else ""
    phone = re.sub(r"\D", "", phone_raw)
    key = (zone, phone)
    if key in lookup:
        sheet_row = i + 2  # 헤더 1행 + 0-indexed
        updates.append({
            "range": f"'미선택 관리'!F{sheet_row}",
            "values": [[lookup[key]]]
        })
        matched += 1

print(f"매칭: {matched}건")
if not updates:
    print("업데이트할 내용 없음")
else:
    resp = sheets.values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "RAW", "data": updates}
    ).execute()
    print(f"업데이트 완료: {resp.get('totalUpdatedCells', 0)}셀")
