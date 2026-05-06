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

# 로우 시트: A=좌수(숫자), B=휴대폰번호, C=남은금액
raw = sheets.values().get(
    spreadsheetId=SPREADSHEET_ID,
    range="'로우'!A2:C2000",
    valueRenderOption="FORMATTED_VALUE"
).execute().get("values", [])

# 활성 사용자 set: (좌수구간, 전화번호) → 남은금액
lookup = {}
for row in raw:
    if len(row) < 2:
        continue
    zone = str(row[0]).strip() + "좌"
    phone = re.sub(r"\D", "", str(row[1]).strip())
    amount_str = str(row[2]).strip().replace(",", "") if len(row) > 2 else "0"
    if not zone or not phone:
        continue
    try:
        lookup[(zone, phone)] = int(amount_str)
    except ValueError:
        lookup[(zone, phone)] = 0

print(f"로우 활성 데이터: {len(lookup)}건")

# 미선택 관리 시트: C=좌수구간, D=휴대폰번호, F=남은금액
mgmt = sheets.values().get(
    spreadsheetId=SPREADSHEET_ID,
    range="'미선택 관리'!A2:F2000",
    valueRenderOption="FORMATTED_VALUE"
).execute().get("values", [])

print(f"미선택 관리 데이터: {len(mgmt)}행")

updates = []
matched = 0
zeroed = 0

for i, row in enumerate(mgmt):
    zone = str(row[2]).strip() if len(row) > 2 else ""
    phone = re.sub(r"\D", "", str(row[3]).strip()) if len(row) > 3 else ""
    if not zone or not phone:
        continue

    sheet_row = i + 2
    key = (zone, phone)

    if key in lookup:
        # 로우에 있음 → 남은금액 업데이트
        updates.append({
            "range": f"'미선택 관리'!F{sheet_row}",
            "values": [[lookup[key]]]
        })
        matched += 1
    else:
        # 로우에 없음 → 이미 선택 완료 → 남은금액 0
        updates.append({
            "range": f"'미선택 관리'!F{sheet_row}",
            "values": [[0]]
        })
        zeroed += 1

print(f"남은금액 업데이트: {matched}건 / 0으로 처리: {zeroed}건")

if updates:
    resp = sheets.values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "RAW", "data": updates}
    ).execute()
    print(f"완료: {resp.get('totalUpdatedCells', 0)}셀 업데이트")
