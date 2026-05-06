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
