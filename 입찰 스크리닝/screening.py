import argparse
from loader import load_excel, deduplicate_events
from grouper import group_events
from searcher import search_group
from parser import analyze_group
from reporter import write_results

def run_pipeline(filepath: str):
    print(f"\n[1/5] 엑셀 로딩: {filepath}")
    df = load_excel(filepath)
    events = deduplicate_events(df)
    print(f"      {len(df)}건 → 중복 제거 후 {len(events)}건")

    print("\n[2/5] Claude 이벤트 그룹핑 중...")
    groups = group_events(events)
    print(f"      {len(groups)}개 그룹 생성")
    for g in groups:
        print(f"      - {g.group_name} ({len(g.quote_ids)}건)")

    print("\n[3/5] 웹 검색 중...")
    search_results_map = {}
    for i, group in enumerate(groups, 1):
        print(f"      [{i}/{len(groups)}] {group.group_name}", end=" ", flush=True)
        sr = search_group(group)
        search_results_map[group.group_name] = sr
        print(f"→ {len(sr.urls)}개 URL")

    print("\n[4/5] 블로그 스크래핑 & 이미지 분석 중...")
    screening_results = []
    for i, group in enumerate(groups, 1):
        print(f"      [{i}/{len(groups)}] {group.group_name}", end=" ", flush=True)
        try:
            result = analyze_group(group, search_results_map[group.group_name])
            supplier_str = result.supplier or "미확인"
            print(f"→ {supplier_str} [{result.confidence}]")
        except Exception as e:
            print(f"→ [오류: {e}]")
            from models import ScreeningResult
            from datetime import date
            result = ScreeningResult(
                group_name=group.group_name,
                quote_ids=group.quote_ids,
                event_count=len(group.quote_ids),
                supplier=None,
                coupon_type=None,
                face_value=None,
                validity_days=None,
                evidence_url=None,
                confidence="미확인",
                confidence_reason=f"분석 오류: {e}",
                search_date=date.today().isoformat(),
            )
        screening_results.append(result)

    print("\n[5/5] Google Sheets 기록 중...")
    url = write_results(screening_results)

    confirmed = sum(1 for r in screening_results if r.confidence == "확실")
    estimated = sum(1 for r in screening_results if r.confidence == "추정")
    unknown = sum(1 for r in screening_results if r.confidence == "미확인")

    print(f"\n완료! 총 {len(screening_results)}개 그룹 분석")
    print(f"  확실: {confirmed}건 / 추정: {estimated}건 / 미확인: {unknown}건")
    print(f"  결과 시트: {url}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="우리카드 미낙찰 경쟁사 스크리닝")
    parser.add_argument("filepath", help="미낙찰 엑셀 파일 경로")
    args = parser.parse_args()
    run_pipeline(args.filepath)
