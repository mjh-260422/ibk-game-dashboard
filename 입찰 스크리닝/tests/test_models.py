from models import UniqueEvent, EventGroup, SearchResults, ScreeningResult

def test_unique_event_instantiation():
    e = UniqueEvent(quote_id=100, quote_name="테스트", latest_date="2026-04-29", rebid_count=2)
    assert e.quote_id == 100
    assert e.rebid_count == 2

def test_event_group_instantiation():
    g = EventGroup(
        group_name="무실적_GS25",
        quote_ids=[100, 101],
        brands=["GS25"],
        search_keywords=["우리카드 GS25 쿠폰"],
    )
    assert len(g.search_keywords) == 1

def test_search_results_instantiation():
    sr = SearchResults(
        group_name="무실적_GS25",
        urls=["https://example.com"],
        url_snippets={"https://example.com": "블로그 내용"},
    )
    assert sr.urls[0] == "https://example.com"

def test_screening_result_instantiation():
    r = ScreeningResult(
        group_name="무실적_GS25",
        quote_ids=[100],
        event_count=1,
        supplier="기프티쇼(KT엠하우스)",
        coupon_type="GS25 모바일쿠폰",
        face_value="3000원",
        validity_days="30일",
        evidence_url="https://example.com",
        confidence="확실",
        confidence_reason="이미지에서 로고 확인",
        search_date="2026-04-29",
    )
    assert r.confidence == "확실"
