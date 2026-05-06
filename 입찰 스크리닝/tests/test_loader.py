import pandas as pd
from loader import deduplicate_events

COLS = ["순번", "상태", "처리일", "견적번호", "견적명", "담당자명", "시작일시", "마감일시", "낙찰기준"]

def make_df(rows):
    return pd.DataFrame(rows, columns=COLS)

def test_dedup_removes_duplicate_quote_ids():
    df = make_df([
        [1, "미낙찰", "2026-04-28", 100, "테스트 이벤트", "김", "2026-04-27", "2026-04-27", "총액최저가"],
        [2, "미낙찰", "2026-04-29", 100, "테스트 이벤트", "김", "2026-04-28", "2026-04-28", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert len(result) == 1
    assert result[0].quote_id == 100

def test_dedup_counts_rebids():
    df = make_df([
        [1, "미낙찰", "2026-04-27", 100, "이벤트 A", "김", "2026-04-26", "2026-04-26", "총액최저가"],
        [2, "미낙찰", "2026-04-28", 100, "이벤트 A", "김", "2026-04-27", "2026-04-27", "총액최저가"],
        [3, "미낙찰", "2026-04-29", 100, "이벤트 A", "김", "2026-04-28", "2026-04-28", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert result[0].rebid_count == 3

def test_dedup_keeps_latest_date():
    df = make_df([
        [1, "미낙찰", "2026-04-27", 100, "이벤트 A", "김", "2026-04-26", "2026-04-26", "총액최저가"],
        [2, "미낙찰", "2026-04-29", 100, "이벤트 A", "김", "2026-04-28", "2026-04-28", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert "2026-04-29" in result[0].latest_date

def test_dedup_preserves_distinct_events():
    df = make_df([
        [1, "미낙찰", "2026-04-28", 100, "이벤트 A", "김", "2026-04-27", "2026-04-27", "총액최저가"],
        [2, "미낙찰", "2026-04-28", 200, "이벤트 B", "이", "2026-04-27", "2026-04-27", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert len(result) == 2

def test_dedup_strips_whitespace_from_name():
    df = make_df([
        [1, "미낙찰", "2026-04-28", 100, "  이벤트 A  ", "김", "2026-04-27", "2026-04-27", "총액최저가"],
    ])
    result = deduplicate_events(df)
    assert result[0].quote_name == "이벤트 A"
