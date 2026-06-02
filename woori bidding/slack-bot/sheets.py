import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build as google_build
from config import SIMULATION_SPREADSHEET_ID, get_google_creds_info
from image_parser import BidInfo

SIM_SHEET = "4"
HISTORY_SHEET = "입찰 히스토리"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DEFAULT_FEES = {
    "스타벅스": 4.60,
    "메가MGC": 2.73,
    "메가커피": 2.73,
}

def build_service():
    info = get_google_creds_info()
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return google_build("sheets", "v4", credentials=creds, cache_discovery=False)

def get_supply_fee(product_name: str) -> float | None:
    for keyword, fee in DEFAULT_FEES.items():
        if keyword in product_name:
            return fee
    return None

def get_last_sim_row() -> int:
    service = build_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SIMULATION_SPREADSHEET_ID,
        range=f"'{SIM_SHEET}'!A:A",
        majorDimension="COLUMNS",
    ).execute()
    vals = result.get("values", [[]])[0]
    return len(vals)

def _copy_format(service, sheet_id: int, src_start: int, src_end: int, dst_start: int, dst_end: int):
    service.spreadsheets().batchUpdate(
        spreadsheetId=SIMULATION_SPREADSHEET_ID,
        body={"requests": [{
            "copyPaste": {
                "source": {"sheetId": sheet_id, "startRowIndex": src_start, "endRowIndex": src_end, "startColumnIndex": 0, "endColumnIndex": 16},
                "destination": {"sheetId": sheet_id, "startRowIndex": dst_start, "endRowIndex": dst_end, "startColumnIndex": 0, "endColumnIndex": 16},
                "pasteType": "PASTE_FORMAT",
                "pasteOrientation": "NORMAL",
            }
        }]}
    ).execute()

def write_sim_block(bid: BidInfo, date: str | None = None) -> dict:
    """
    시뮬 탭에 입찰 1건 블록을 기록한다.
    반환값: {"start_row": int, "products": [{"name", "supply_fee", "missing_fee": bool}]}
    """
    service = build_service()
    meta = service.spreadsheets().get(spreadsheetId=SIMULATION_SPREADSHEET_ID).execute()
    sheet_id = next(s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == SIM_SHEET)

    last_row = get_last_sim_row()
    start_row = last_row + 1
    write_date = date or datetime.date.today().strftime("%Y-%m-%d")
    n_products = len(bid.products)
    block_rows = 4 + n_products + 1  # date + title + section-header + col-header + products + 합계

    # 서식 복사 (직전 블록 → 새 블록)
    src_0 = last_row - 7  # 0-indexed
    src_1 = last_row
    dst_0 = last_row
    dst_1 = last_row + block_rows
    _copy_format(service, sheet_id, src_0, src_1, dst_0, dst_1)

    # 데이터 행 구성
    title = f"\t'{bid.event_name}_{bid.manager}_{bid.bid_number}"
    rows = [
        ["", write_date],
        ["", title],
        ["", "상품정보", "", "", "", "", "", "", "클라이언트 제공 정보", "", "", "예상 수익 정보"],
        ["", "상품명", "권종", "공급수수료\n(vat별도)", "발송량", "거래금액", "발송비",
         "할인율", "할인율(PG포함)", "할인금액", "클라이언트 \n청구금액",
         "예상 공급 수수료 수익", "예상 미교환율 ", " 예상 미교환 수익", " 예상 수익", "예상 수익율"],
    ]

    product_results = []
    for p in bid.products:
        fee = get_supply_fee(p.name)
        shipping = " - " if bid.is_pin_delivery else p.quantity * 50
        row = [
            "",
            f" {p.name}",
            p.face_value,
            f"{fee:.2f}%" if fee is not None else "",
            p.quantity,
            "",  # F: 수식
            shipping,
            p.discount_rate / 100,  # H: 액면가 할인율 (소수)
            "",  # I: 수식
        ]
        rows.append(row)
        product_results.append({"name": p.name, "supply_fee": fee, "missing_fee": fee is None})

    rows.append(["", "합계"])

    # 값 기록
    service.spreadsheets().values().update(
        spreadsheetId=SIMULATION_SPREADSHEET_ID,
        range=f"'{SIM_SHEET}'!A{start_row}",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    # I열 수식 (PG포함 할인율) 적용
    formula_data = []
    for i in range(n_products):
        product_row = start_row + 4 + i
        formula_data.append({
            "range": f"'{SIM_SHEET}'!I{product_row}",
            "values": [[f"=1-(1-H{product_row})*0.975"]],
        })
    if formula_data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=SIMULATION_SPREADSHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": formula_data},
        ).execute()

    return {"start_row": start_row, "products": product_results}
