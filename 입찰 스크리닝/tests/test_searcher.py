from unittest.mock import patch, MagicMock
from searcher import search_group, deduplicate_urls
from models import EventGroup, SearchResults

SAMPLE_GROUP = EventGroup(
    group_name="무실적 마케팅_GS25",
    quote_ids=[1725],
    brands=["GS25"],
    search_keywords=["우리카드 GS25 쿠폰", "우리카드 편의점 혜택"],
)

def test_deduplicate_urls_removes_duplicates():
    results = [
        {"url": "https://blog.naver.com/a", "content": "내용A"},
        {"url": "https://blog.naver.com/b", "content": "내용B"},
        {"url": "https://blog.naver.com/a", "content": "내용A"},
    ]
    urls, snippets = deduplicate_urls(results)
    assert len(urls) == 2
    assert "https://blog.naver.com/a" in snippets

def test_search_group_returns_search_results():
    mock_response = {
        "results": [
            {"url": "https://blog.naver.com/post1", "content": "우리카드 GS25 이벤트"},
            {"url": "https://tistory.com/post2", "content": "GS25 쿠폰 받았어요"},
        ]
    }
    mock_client = MagicMock()
    mock_client.search.return_value = mock_response

    with patch("searcher.TavilyClient", return_value=mock_client):
        result = search_group(SAMPLE_GROUP)

    assert isinstance(result, SearchResults)
    assert result.group_name == "무실적 마케팅_GS25"
    assert len(result.urls) > 0

def test_search_group_handles_api_error_gracefully():
    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("API Error")

    with patch("searcher.TavilyClient", return_value=mock_client):
        result = search_group(SAMPLE_GROUP)

    assert result.urls == []
