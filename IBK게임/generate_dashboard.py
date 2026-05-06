import sys
import glob
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

BG     = '#F4F6FB'
WHITE  = '#FFFFFF'
BLUE1  = '#2563EB'
BLUE2  = '#3B82F6'
BLUE3  = '#BFDBFE'
PURPLE = '#7C3AED'
ORANGE = '#F59E0B'
GREEN  = '#10B981'
RED    = '#EF4444'
GRAY1  = '#1E293B'
GRAY2  = '#64748B'
GRAY3  = '#94A3B8'
DIVIDER= '#E2E8F0'

CHART_COLORS = [BLUE2, PURPLE, ORANGE, GREEN, RED, '#06B6D4', '#EC4899', '#84CC16']

# 실행 방법: py generate_dashboard.py [엑셀파일경로]
# 파일 경로 생략 시 같은 폴더의 xlsx 파일 자동 탐색
here = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) > 1:
    INPUT = sys.argv[1]
else:
    xlsx_files = glob.glob(os.path.join(here, '*.xlsx'))
    if not xlsx_files:
        print('오류: 같은 폴더에 xlsx 파일이 없습니다.')
        sys.exit(1)
    # 수정일 기준 가장 최근 파일 선택
    INPUT = max(xlsx_files, key=os.path.getmtime)

OUTPUT = os.path.join(here, 'IBK_게임_대시보드.pdf')
print(f'입력 파일: {INPUT}')

df = pd.read_excel(INPUT)
df['게임 실행일'] = pd.to_datetime(df['게임 실행일'])
df['날짜'] = df['게임 실행일'].dt.date

total        = len(df)
unique_users = df['사용자 ID'].nunique()
total_points = int(df['차감 포인트'].sum())
prize_done   = (df['경품 지급 상태'] == '완료').sum()
prize_fail   = total - prize_done
game_counts  = df.groupby('게임명').size().sort_values(ascending=False)
prize_counts = df.groupby('경품명').size().sort_values(ascending=False)
daily_counts = df.groupby('날짜').size().sort_index()

report_date = datetime.now().strftime('%Y.%m.%d')
data_range  = f"{df['게임 실행일'].min().strftime('%Y-%m-%d %H:%M')} ~ {df['게임 실행일'].max().strftime('%Y-%m-%d %H:%M')}"


def add_card(fig, x, y, w, h, facecolor=WHITE):
    ax = fig.add_axes([x, y, w, h])
    ax.set_facecolor(facecolor)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.6); sp.set_color(DIVIDER)
    return ax


with PdfPages(OUTPUT) as pdf:

    # 16:9 비율
    fig = plt.figure(figsize=(13.33, 7.5))
    fig.patch.set_facecolor(BG)

    # ── Header ──
    fig.text(0.05, 0.955, 'IBK 카드앱 게이미피케이션 운영 현황',
             fontsize=20, fontweight='bold', color=GRAY1, va='top')
    fig.text(0.05, 0.900, f'기준일: {report_date}   |   데이터 기간: {data_range}',
             fontsize=9.5, color=GRAY2, va='top')

    # ── KPI 카드 5개 (가로 나열) ──
    kpi_list = [
        ('총 게임 실행 수',  f'{total:,}회',         '',                        BLUE2),
        ('유니크 사용자',    f'{unique_users:,}명',   '* 중복 제외 실제 참여자', PURPLE),
        ('총 차감 포인트',   f'{total_points:,}P',   '',                        ORANGE),
        ('경품 지급 완료',   f'{prize_done:,}건',     '완료율 100%',             GREEN),
        ('경품 지급 미완료', f'{prize_fail:,}건',     '',                        GRAY3),
    ]
    kpi_w, kpi_h = 0.164, 0.135
    kpi_gap = 0.011
    kpi_x0 = 0.05
    kpi_y  = 0.715

    for i, (label, value, sub, color) in enumerate(kpi_list):
        x = kpi_x0 + i * (kpi_w + kpi_gap)
        ax = add_card(fig, x, kpi_y, kpi_w, kpi_h)
        bar = fig.add_axes([x, kpi_y, 0.004, kpi_h])
        bar.set_facecolor(color)
        bar.set_xticks([]); bar.set_yticks([])
        for sp in bar.spines.values(): sp.set_visible(False)

        ax.text(0.08, 0.80, label, fontsize=9, color=GRAY2, transform=ax.transAxes)
        ax.text(0.08, 0.44, value, fontsize=17, fontweight='bold', color=GRAY1, transform=ax.transAxes)
        if sub:
            ax.text(0.08, 0.12, sub, fontsize=7.5, color=GRAY3, transform=ax.transAxes, style='italic')

    # ── 차트 영역 (2열) ──
    chart_y, chart_h = 0.09, 0.55

    # 1. 게임별 실행 수 (바 차트) - 더 좁게
    ax1 = fig.add_axes([0.05, chart_y, 0.22, chart_h])
    ax1.set_facecolor(WHITE)
    for sp in ax1.spines.values(): sp.set_linewidth(0.6); sp.set_color(DIVIDER)
    ax1.spines['top'].set_visible(False); ax1.spines['right'].set_visible(False)

    bars = ax1.bar(range(len(game_counts)), game_counts.values,
                   color=[BLUE2, PURPLE, ORANGE], width=0.45, edgecolor='none', zorder=3)
    ax1.set_axisbelow(True)
    ax1.yaxis.grid(True, color='#F1F5F9', linewidth=0.8)
    y_max = game_counts.max() * 1.35
    ax1.set_ylim(0, y_max)
    for bar, val in zip(bars, game_counts.values):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + y_max * 0.015,
                 f'{val:,}회', ha='center', va='bottom', fontsize=10, fontweight='bold', color=GRAY1)
    ax1.set_title('게임별 실행 수', fontsize=13, fontweight='bold', color=GRAY1, pad=10, loc='left')
    ax1.tick_params(labelsize=9, colors=GRAY2)
    ax1.set_ylabel('실행 수 (회)', fontsize=9, color=GRAY2)
    ax1.set_xticks(range(len(game_counts)))
    ax1.set_xticklabels(game_counts.index, fontsize=9, rotation=10)

    # 2. 경품별 당첨 수 (가로 바)
    ax3 = fig.add_axes([0.40, chart_y, 0.55, chart_h])
    ax3.set_facecolor(WHITE)
    for sp in ax3.spines.values(): sp.set_linewidth(0.6); sp.set_color(DIVIDER)
    ax3.spines['top'].set_visible(False); ax3.spines['right'].set_visible(False)

    short = [n.replace('[IBK] ', '').replace('모바일쿠폰샵 ', '') for n in prize_counts.index]
    short = [s if len(s) <= 13 else s[:12] + '…' for s in short]
    ax3.barh(short, prize_counts.values,
             color=CHART_COLORS[:len(prize_counts)], edgecolor='none', height=0.55, zorder=3)
    ax3.set_axisbelow(True)
    ax3.xaxis.grid(True, color='#F1F5F9', linewidth=0.8)
    x_max = prize_counts.max() * 1.5
    ax3.set_xlim(0, x_max)
    for i, val in enumerate(prize_counts.values):
        ax3.text(val + x_max * 0.012, i, f'{val:,}건', va='center', fontsize=10, fontweight='bold', color=GRAY1)
    ax3.set_title('경품별 당첨 수', fontsize=13, fontweight='bold', color=GRAY1, pad=10, loc='left')
    ax3.tick_params(labelsize=9, colors=GRAY2)
    ax3.invert_yaxis()

    pdf.savefig(fig, bbox_inches='tight', facecolor=BG, pad_inches=0.3)
    plt.close()

print(f'완료: {OUTPUT}')
