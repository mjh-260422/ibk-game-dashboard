import datetime
from image_parser import BidInfo

def build_result_message(bid: BidInfo, write_result: dict) -> str:
    today = datetime.date.today().strftime("%y%m%d")
    lines = [f"✅ *입찰 {bid.bid_number} 처리 완료*\n"]

    draft_lines = [
        f"[{today}_입찰] {bid.event_name}_{bid.manager}_{bid.bid_number}\n",
        "[내용]",
    ]

    for p_result in write_result["products"]:
        name = p_result["name"]
        fee = p_result["supply_fee"]
        product = next((p for p in bid.products if p.name == name), None)
        if product is None:
            raise ValueError(f"write_result에 있는 상품명이 BidInfo에 없음: {name}")

        pg_rate = round(1 - (1 - product.discount_rate / 100) * 0.975, 6) * 100
        shipping_note = "PIN 전달 (발송비 없음)" if bid.is_pin_delivery else f"발송비 {product.quantity * 50:,}원"
        fee_note = f"{fee:.2f}%" if fee is not None else "?"

        lines.append(
            f"• {name} — 할인율 {product.discount_rate:.1f}% (PG포함 {pg_rate:.4f}%), "
            f"수량 {product.quantity:,}건, 공급수수료 {fee_note}, {shipping_note}"
        )

        draft_lines += [
            f"- 상품 : {name}",
            f"- 수량 : {product.quantity:,}건",
            f"- 할인율 : {product.discount_rate:.1f}% (PG포함 {pg_rate:.4f}%) 제안",
            f"- 미교환율 : (확인 필요)",
            f"- 예상 수익 : (시트 확인)",
            f"- 참고사항 : ",
        ]

        if p_result["missing_fee"]:
            lines.append(f"  ⚠️ *{name} 공급수수료 확인 후 시트에 직접 입력해주세요*")

    lines.append("\n*📋 입찰 초안*\n```\n" + "\n".join(draft_lines) + "\n```")
    return "\n".join(lines)
