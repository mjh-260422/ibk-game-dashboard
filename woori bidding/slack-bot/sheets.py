import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build as google_build
from config import SIMULATION_SPREADSHEET_ID, get_google_creds_info
from image_parser import BidInfo

SIM_SHEET = "4"
HISTORY_SHEET = "입찰 히스토리"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
BLOCK_HEADER_ROWS = 4   # date + title + section-header + col-header
BLOCK_FOOTER_ROWS = 1   # 합계
SRC_ROW_OFFSET = 7      # 직전 블록 크기 (1개 품목 기준)

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

def get_last_sim_row(service=None) -> int:
    svc = service or build_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=SIMULATION_SPREADSHEET_ID,
        range=f"'{SIM_SHEET}'!B:B",
        majorDimension="COLUMNS",
    ).execute()
    vals = result.get("values", [[]])[0]
    return len(vals)

def _copy_format(service, sheet_id: int, src_start: int, src_end: int, dst_start: int, dst_end: int) -> None:
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
    sheet_id = next(
        (s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == SIM_SHEET),
        None,
    )
    if sheet_id is None:
        raise ValueError(f"시뮬레이션 시트 탭 '{SIM_SHEET}'을 찾을 수 없습니다.")

    last_row = get_last_sim_row(service)
    start_row = last_row + 1
    write_date = date or datetime.date.today().strftime("%Y-%m-%d")
    n_products = len(bid.products)
    block_rows = BLOCK_HEADER_ROWS + n_products + BLOCK_FOOTER_ROWS

    src_0 = last_row - SRC_ROW_OFFSET  # 0-indexed 직전 블록 시작
    src_1 = last_row
    dst_0 = last_row
    dst_1 = last_row + block_rows
    _copy_format(service, sheet_id, src_0, src_1, dst_0, dst_1)

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
        rows.append([
            "",
            f" {p.name}",
            p.face_value,
            f"{fee:.2f}%" if fee is not None else "",
            p.quantity,
            "",           # F: 거래금액 수식 (기존 서식 복사로 적용)
            shipping,
            p.discount_rate / 100,
            "",           # I: PG포함 할인율 수식
        ])
        product_results.append({"name": p.name, "supply_fee": fee, "missing_fee": fee is None})

    rows.append(["", "합계"])

    service.spreadsheets().values().update(
        spreadsheetId=SIMULATION_SPREADSHEET_ID,
        range=f"'{SIM_SHEET}'!A{start_row}",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    formula_data = [
        {
            "range": f"'{SIM_SHEET}'!I{start_row + BLOCK_HEADER_ROWS + i}",
            "values": [[f"=1-(1-H{start_row + BLOCK_HEADER_ROWS + i})*0.975"]],
        }
        for i in range(n_products)
    ]
    if formula_data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=SIMULATION_SPREADSHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": formula_data},
        ).execute()

    return {"start_row": start_row, "products": product_results}
