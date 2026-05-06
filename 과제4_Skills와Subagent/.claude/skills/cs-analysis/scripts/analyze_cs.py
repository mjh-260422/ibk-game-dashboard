#!/usr/bin/env python3
"""CS점수 CSV 파일을 분석하여 마크다운 보고서를 생성하는 스크립트."""

import csv
import os
import sys
from pathlib import Path


def parse_csv(filepath):
    """CSV 파일을 파싱하여 딕셔너리 리스트로 반환."""
    rows = []
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed = {"주차": row["주차"]}
            for key in ["상담만족도", "응대친절도", "전체평균"]:
                if key in row:
                    parsed[key] = float(row[key])
            if "문제해결률" in row:
                parsed["문제해결률"] = float(row["문제해결률"].replace("%", ""))
            rows.append(parsed)
    return rows


def extract_month(filepath):
    """파일명에서 월 정보를 추출."""
    name = Path(filepath).stem
    for part in name.split("_"):
        if "월" in part:
            return part
    return name


def analyze_month(rows):
    """한 달치 데이터 분석 결과를 반환."""
    metrics = ["상담만족도", "문제해결률", "응대친절도", "전체평균"]
    result = {}
    for m in metrics:
        values = [r[m] for r in rows if m in r]
        if values:
            result[m] = {
                "평균": round(sum(values) / len(values), 2),
                "최고": max(values),
                "최저": min(values),
                "주차별": [(r["주차"], r[m]) for r in rows if m in r],
            }
    return result


def format_unit(metric, value):
    """지표에 맞는 단위 형식으로 변환."""
    if metric == "문제해결률":
        return f"{value}%"
    return str(value)


def generate_report(all_data, output_path):
    """전체 분석 결과를 마크다운 보고서로 생성."""
    lines = ["# CS점수 분석 보고서\n"]

    for month, rows in all_data.items():
        analysis = analyze_month(rows)
        lines.append(f"## {month} 분석\n")

        lines.append("### 월 평균 점수\n")
        lines.append("| 지표 | 평균 | 최고 | 최저 |")
        lines.append("|------|------|------|------|")
        for metric, stats in analysis.items():
            avg = format_unit(metric, stats["평균"])
            high = format_unit(metric, stats["최고"])
            low = format_unit(metric, stats["최저"])
            lines.append(f"| {metric} | {avg} | {high} | {low} |")
        lines.append("")

        lines.append("### 주차별 추이\n")
        header = "| 주차 | " + " | ".join(analysis.keys()) + " |"
        sep = "|------|" + "|".join(["------"] * len(analysis)) + "|"
        lines.append(header)
        lines.append(sep)
        for i in range(len(rows)):
            week_name = rows[i]["주차"]
            vals = []
            for metric in analysis:
                weekly = analysis[metric]["주차별"]
                if i < len(weekly):
                    vals.append(format_unit(metric, weekly[i][1]))
                else:
                    vals.append("-")
            lines.append(f"| {week_name} | " + " | ".join(vals) + " |")
        lines.append("")

    if len(all_data) >= 2:
        lines.append("## 월간 비교\n")
        lines.append("| 월 | 상담만족도 | 문제해결률 | 응대친절도 | 전체평균 |")
        lines.append("|------|------|------|------|------|")
        for month, rows in all_data.items():
            analysis = analyze_month(rows)
            vals = []
            for metric in ["상담만족도", "문제해결률", "응대친절도", "전체평균"]:
                if metric in analysis:
                    vals.append(format_unit(metric, analysis[metric]["평균"]))
                else:
                    vals.append("-")
            lines.append(f"| {month} | " + " | ".join(vals) + " |")
        lines.append("")

        lines.append("### 추이 요약\n")
        months = list(all_data.keys())
        first_analysis = analyze_month(all_data[months[0]])
        last_analysis = analyze_month(all_data[months[-1]])
        for metric in ["상담만족도", "문제해결률", "응대친절도", "전체평균"]:
            if metric in first_analysis and metric in last_analysis:
                diff = round(last_analysis[metric]["평균"] - first_analysis[metric]["평균"], 2)
                arrow = "상승" if diff > 0 else "하락" if diff < 0 else "유지"
                sign = "+" if diff > 0 else ""
                unit = "%" if metric == "문제해결률" else ""
                lines.append(
                    f"- **{metric}**: {months[0]} {format_unit(metric, first_analysis[metric]['평균'])}"
                    f" -> {months[-1]} {format_unit(metric, last_analysis[metric]['평균'])}"
                    f" ({arrow} {sign}{diff}{unit})"
                )
        lines.append("")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path


def main():
    if len(sys.argv) < 3:
        print("사용법: python analyze_cs.py <출력경로> <CSV파일1> [CSV파일2] ...")
        sys.exit(1)

    output_path = sys.argv[1]
    csv_files = sys.argv[2:]

    all_data = {}
    for filepath in sorted(csv_files):
        month = extract_month(filepath)
        all_data[month] = parse_csv(filepath)

    result = generate_report(all_data, output_path)
    print(f"보고서 생성 완료: {result}")


if __name__ == "__main__":
    main()
