import csv
import json
import os
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "17qJfmlYUXcI74oOxZqJ6DpjJ9mlBv5aRRr3gnb-fVHI"
SHEET_NAME = "미선택 관리"
KEY_FILE = os.path.expanduser("~/.claude/google-sheets-key.json")
CSV_DIR = r"C:\Users\jihye\tutorial\업무_우리카드구간포상\0423리마인드"

ZONE_MAP = {
    "mms02": "2좌",
    "mms04": "4좌",
    "mms06": "6좌",
    "mms08": "8좌",
    "mms10": "10좌",
}

def parse_phone(val):
    # ="01012345678" → 01012345678
    val = val.strip()
    m = re.match(r'^="?(\d+)"?$', val)
    if m:
        return m.group(1)
    return re.sub(r'\D', '', val)

def load_csv_files():
    lookup = {}  # (zone, phone) → 남은금액
    for fname in os.listdir(CSV_DIR):
        if not fname.endswith(".csv"):
            continue
        m = re.search(r'mms(\d+)', fname)
        if not m:
            continue
        zone_key = f"mms{m.group(1).zfill(2)}"
        zone = ZONE_MAP.get(zone_key)
        if not zone:
            continue
        fpath = os.path.join(CSV_DIR, fname)
        with open(fpath, encoding="utf-16", newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader, None)  # skip header
            for row in reader:
                if len(row) < 4:
                    continue
                phone = parse_phone(row[0])
                try:
                    amount = int(str(row[3]).strip().replace(",", ""))
                except ValueError:
                    continue
                if phone:
                    lookup[(zone, phone)] = amount
    return lookup

def main():
    lookup = load_csv_files()
    print(f"CSV 로드 완료: {len(lookup)}건")

    creds = service_account.Credentials.from_service_account_file(
        KEY_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)
    sheets = service.spreadsheets()

    # Read C, D, F columns (zone, phone, amount) — rows 2 onwards
    result = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!A2:F2000",
        valueRenderOption="FORMATTED_VALUE"
    ).execute()
    rows = result.get("values", [])
    print(f"시트 데이터: {len(rows)}행")

    updates = []
    matched = 0
    for i, row in enumerate(rows):
        # A=No, B=발송월, C=좌수구간, D=휴대폰번호, E=구간금액, F=남은금액
        if len(row) < 4:
            continue
        zone = str(row[2]).strip() if len(row) > 2 else ""
        phone_raw = str(row[3]).strip() if len(row) > 3 else ""
        phone = re.sub(r'\D', '', phone_raw)
        key = (zone, phone)
        if key in lookup:
            sheet_row = i + 2  # 1-indexed, +1 for header skip
            updates.append({
                "range": f"'{SHEET_NAME}'!F{sheet_row}",
                "values": [[lookup[key]]]
            })
            matched += 1

    print(f"매칭: {matched}건")
    if not updates:
        print("업데이트할 내용 없음")
        return

    body = {"valueInputOption": "RAW", "data": updates}
    resp = sheets.values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body=body
    ).execute()
    print(f"업데이트 완료: {resp.get('totalUpdatedCells', 0)}셀")

if __name__ == "__main__":
    main()
