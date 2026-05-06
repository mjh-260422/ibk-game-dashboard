from unittest.mock import patch, MagicMock
import json
from parser import build_parsing_prompt, analyze_group
from models import EventGroup, SearchResults

def test_prompt_contains_all_suppliers():
    from config import SUPPLIERS
    prompt = build_parsing_prompt("무실적_GS25", "블로그 텍스트")
    for supplier in SUPPLIERS:
        assert supplier in prompt

def test_prompt_requests_json_fields():
    prompt = build_parsing_prompt("무실적_GS25", "블로그 텍스트")
    for field in ["supplier", "coupon_type", "face_value", "validity_days", "confidence"]:
        assert field in prompt

def test_analyze_group_parses_claude_json():
    mock_json = {
        "supplier": "기프티쇼(KT엠하우스)",
        "coupon_type": "GS25 모바일쿠폰",
        "face_value": "3000원",
        "validity_days": "30일",
        "evidence_url": "https://blog.naver.com/test",
        "confidence": "확실",
        "confidence_reason": "이미지에서 기프티쇼 로고 확인",
    }
    group = EventGroup("무실적_GS25", [1725], ["GS25"], ["우리카드 GS25"])
    sr = SearchResults("무실적_GS25", ["https://blog.naver.com/test"], {})

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(mock_json))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("parser.anthropic.Anthropic", return_value=mock_client), \
         patch("parser.scrape_blog", return_value=("블로그 텍스트 내용", [])), \
         patch("parser.collect_images", return_value=[]):
        result = analyze_group(group, sr)

    assert result.supplier == "기프티쇼(KT엠하우스)"
    assert result.face_value == "3000원"
    assert result.confidence == "확실"

def test_analyze_group_returns_미확인_on_empty_results():
    group = EventGroup("미확인 이벤트", [999], [], ["우리카드 알수없음"])
    sr = SearchResults("미확인 이벤트", [], {})

    mock_json = {
        "supplier": None, "coupon_type": None, "face_value": None,
        "validity_days": None, "evidence_url": None,
        "confidence": "미확인", "confidence_reason": "검색 결과 없음",
    }
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(mock_json))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("parser.anthropic.Anthropic", return_value=mock_client), \
         patch("parser.scrape_blog", return_value=("", [])), \
         patch("parser.collect_images", return_value=[]):
        result = analyze_group(group, sr)

    assert result.confidence == "미확인"
    assert result.supplier is None
