import pytest
from unittest.mock import patch, MagicMock
from image_parser import BidInfo, ProductInfo
from sheets import get_last_sim_row, get_supply_fee, write_sim_block, SIM_SHEET

def _make_bid():
    return BidInfo(
        bid_number="1770",
        event_name="'26년 6월 WON픽",
        manager="임은혜",
        is_pin_delivery=False,
        products=[ProductInfo(name="[스타벅스] 아이스 아메리카노 Tall", face_value=4700, quantity=1000, discount_rate=18.0)]
    )

def test_get_supply_fee_known_brand():
    assert get_supply_fee("[스타벅스] 아이스 아메리카노 Tall") == 4.60
    assert get_supply_fee("[메가MGC커피] ICE 아메리카노") == 2.73

def test_get_supply_fee_unknown_brand():
    assert get_supply_fee("[다이소] 모바일금액권 5만원권") is None

def test_get_last_sim_row():
    mock_service = MagicMock()
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [["2026-05-27"]] * 284
    }
    with patch("sheets.build_service", return_value=mock_service):
        row = get_last_sim_row()
    assert row == 284
