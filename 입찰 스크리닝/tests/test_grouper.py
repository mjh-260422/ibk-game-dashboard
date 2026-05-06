from unittest.mock import patch, MagicMock
import json
from grouper import build_grouping_prompt, group_events
from models import UniqueEvent

SAMPLE_EVENTS = [
    UniqueEvent(1725, "'26년 4월 2차 당월무실적 이용조건부 마케팅(GS25)", "2026-04-24", 2),
    UniqueEvent(1726, "기업카드 퀴즈이벤트 쿠폰발송", "2026-04-24", 1),
]

def test_prompt_contains_quote_ids_and_names():
    prompt = build_grouping_prompt(SAMPLE_EVENTS)
    assert "1725" in prompt
    assert "GS25" in prompt
    assert "퀴즈이벤트" in prompt

def test_prompt_requests_json_output():
    prompt = build_grouping_prompt(SAMPLE_EVENTS)
    assert "JSON" in prompt
    assert "search_keywords" in prompt

def test_group_events_returns_event_groups():
    mock_data = [
        {
            "group_name": "무실적 마케팅_GS25",
            "quote_ids": [1725],
            "brands": ["GS25"],
            "search_keywords": ["우리카드 GS25 쿠폰", "우리카드 편의점 혜택"],
        },
        {
            "group_name": "기업카드 퀴즈이벤트",
            "quote_ids": [1726],
            "brands": [],
            "search_keywords": ["우리카드 퀴즈 이벤트 쿠폰"],
        },
    ]
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(mock_data))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("grouper.anthropic.Anthropic", return_value=mock_client):
        result = group_events(SAMPLE_EVENTS)

    assert len(result) == 2
    assert result[0].group_name == "무실적 마케팅_GS25"
    assert result[0].search_keywords == ["우리카드 GS25 쿠폰", "우리카드 편의점 혜택"]
    assert result[1].quote_ids == [1726]
