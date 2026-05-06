from unittest.mock import patch, MagicMock
from reporter import write_results, HEADERS, _result_to_row
from models import ScreeningResult

def make_result(confidence="확실"):
    return ScreeningResult(
        group_name="무실적 마케팅_GS25",
        quote_ids=[1725, 1711],
        event_count=2,
        supplier="기프티쇼(KT엠하우스)",
        coupon_type="GS25 모바일쿠폰",
        face_value="3000원",
        validity_days="30일",
        evidence_url="https://blog.naver.com/test",
        confidence=confidence,
        confidence_reason="이미지에서 로고 확인",
        search_date="2026-04-29",
    )

def test_result_to_row_column_count_matches_headers():
    row = _result_to_row(make_result())
    assert len(row) == len(HEADERS)

def test_result_to_row_values():
    row = _result_to_row(make_result())
    assert row[0] == "무실적 마케팅_GS25"
    assert row[1] == 1725
    assert row[2] == 2
    assert row[3] == "기프티쇼(KT엠하우스)"
    assert row[8] == "확실"

def test_result_to_row_handles_none_fields():
    r = make_result()
    r.supplier = None
    r.face_value = None
    row = _result_to_row(r)
    assert row[3] == ""
    assert row[5] == ""

def test_write_results_creates_new_tab_and_writes():
    mock_ws = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.side_effect = Exception("not found")
    mock_spreadsheet.add_worksheet.return_value = mock_ws
    mock_gc = MagicMock()
    mock_gc.open_by_key.return_value = mock_spreadsheet

    with patch("reporter.get_sheet_client", return_value=mock_gc):
        write_results([make_result()])

    mock_ws.append_row.assert_called_once_with(HEADERS)
    mock_ws.append_rows.assert_called_once()
    rows = mock_ws.append_rows.call_args[0][0]
    assert rows[0][0] == "무실적 마케팅_GS25"
