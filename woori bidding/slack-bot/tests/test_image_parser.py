import pytest
from unittest.mock import patch, MagicMock
from image_parser import parse_bid_image, BidInfo, ProductInfo

def test_parse_returns_bid_info():
    mock_response = MagicMock()
    mock_response.content[0].text = """{
        "bid_number": "1766",
        "event_name": "'26년 5월 WON픽",
        "manager": "임은혜",
        "is_pin_delivery": false,
        "products": [
            {"name": "[스타벅스] 아이스 아메리카노 Tall", "face_value": 4700, "quantity": 1500, "discount_rate": 18.0},
            {"name": "[메가MGC커피] ICE 아메리카노", "face_value": 2000, "quantity": 7910, "discount_rate": 20.0}
        ]
    }"""

    with patch("image_parser.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        result = parse_bid_image(b"fake_image_bytes", "image/jpeg")

    assert result.bid_number == "1766"
    assert result.event_name == "'26년 5월 WON픽"
    assert result.is_pin_delivery is False
    assert len(result.products) == 2
    assert result.products[0].face_value == 4700
    assert result.products[0].discount_rate == 18.0

def test_pin_delivery_detected():
    mock_response = MagicMock()
    mock_response.content[0].text = """{
        "bid_number": "1767",
        "event_name": "'26년 6월 WON픽",
        "manager": "임은혜",
        "is_pin_delivery": true,
        "products": [
            {"name": "[다이소] 모바일금액권 5만원권", "face_value": 50000, "quantity": 30, "discount_rate": 0.0}
        ]
    }"""

    with patch("image_parser.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        result = parse_bid_image(b"fake_image_bytes", "image/png")

    assert result.is_pin_delivery is True
