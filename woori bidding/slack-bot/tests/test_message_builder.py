import datetime
from image_parser import BidInfo, ProductInfo
from message_builder import build_result_message

def _make_bid():
    return BidInfo(
        bid_number="1766",
        event_name="'26년 5월 WON픽",
        manager="임은혜",
        is_pin_delivery=False,
        products=[
            ProductInfo(name="[스타벅스] 아이스 아메리카노 Tall", face_value=4700, quantity=1500, discount_rate=18.0),
        ]
    )

def test_message_contains_bid_number():
    msg = build_result_message(_make_bid(), {"start_row": 285, "products": [{"name": "[스타벅스] 아이스 아메리카노 Tall", "supply_fee": 4.60, "missing_fee": False}]})
    assert "1766" in msg

def test_message_contains_discount_rate():
    msg = build_result_message(_make_bid(), {"start_row": 285, "products": [{"name": "[스타벅스] 아이스 아메리카노 Tall", "supply_fee": 4.60, "missing_fee": False}]})
    assert "18.0%" in msg

def test_message_warns_missing_fee():
    bid = BidInfo(bid_number="1767", event_name="'26년 6월 WON픽", manager="임은혜", is_pin_delivery=True,
                  products=[ProductInfo(name="[다이소] 모바일금액권 5만원권", face_value=50000, quantity=30, discount_rate=0.0)])
    msg = build_result_message(bid, {"start_row": 292, "products": [{"name": "[다이소] 모바일금액권 5만원권", "supply_fee": None, "missing_fee": True}]})
    assert "⚠️" in msg
    assert "공급수수료" in msg

def test_draft_format_contains_sections():
    msg = build_result_message(_make_bid(), {"start_row": 285, "products": [{"name": "[스타벅스] 아이스 아메리카노 Tall", "supply_fee": 4.60, "missing_fee": False}]})
    assert "[내용]" in msg
    assert "할인율" in msg
    assert "수량" in msg
