import streamlit as st
import pandas as pd
from data_loader import load_all

st.set_page_config(page_title="IBK 게임 수익 대시보드", page_icon="🎮", layout="wide")

st.markdown("""
<style>
[data-testid="stMetric"] {
    background:#f8fafc; border:1px solid #e2e8f0;
    border-radius:10px; padding:16px 20px;
}
[data-testid="stMetricLabel"] { font-size:13px; color:#64748b; }
[data-testid="stMetricValue"] { font-size:22px; font-weight:700; color:#1e293b; }
[data-testid="stSidebarNavItems"] { display:none; }
div[data-testid="stRadio"] > div { gap:4px; }
div[data-testid="stRadio"] label {
    font-size:15px; padding:8px 12px; border-radius:6px;
    cursor:pointer; width:100%;
}
div[data-testid="stRadio"] label:hover { background:#e2e8f0; }
</style>
""", unsafe_allow_html=True)

# ── 포맷 헬퍼 ──────────────────────────────────────────────────────────────────
INT_COLS = [
    "게임P", "면가", "발행수", "교환수", "사용수", "만료수",
    "정산금액", "교환금액", "수수료금액", "확정수익", "잠재수익",
    "예상 교환수", "예상 사용수", "예상 만료수",
    "예상 정산", "예상 교환금액", "예상 수수료", "예상 수익",
    "경품비", "쿠폰비", "현재수익", "미교환수익", "예상수익",
]
PCT_COLS = [
    "교환율(%)", "미교환율(%)", "사용율(%)", "미사용율(%)", "수수료율",
    "수익률_면가(%)", "예상 수익률(%)",
    "현재 미교환율(%)", "예상 미교환율(%)",
    "현재 미사용율(%)", "예상 미사용율(%)",
    "현재수익률(%)", "예상수익률(%)",
    "확정수익률(%)", "잠재수익률(%)",
]

def won(n):  return f"{int(n):,}원"
def pct(r):  return f"{r * 100:.1f}%"

def _fmt(df):
    fmt = {}
    for c in df.columns:
        if c in INT_COLS:   fmt[c] = "{:,.0f}"
        elif c in PCT_COLS: fmt[c] = "{:.1f}%"
    return df.style.format(fmt, na_rep="-")

def _fmt_highlight(df, rate_col, threshold=1.5, profit_col=None, profit_target=30, skip_fmt=None):
    """rate_col 기준 통계적 이상값 + profit_col 기준 목표 미달 행 색상 강조"""
    _skip = set(skip_fmt or [])
    rates = pd.to_numeric(df[rate_col], errors='coerce').dropna()
    fmt = {}
    for c in df.columns:
        if c in _skip: continue
        if c in INT_COLS:   fmt[c] = "{:,.0f}"
        elif c in PCT_COLS: fmt[c] = "{:.1f}%"
    styler = df.style.format(fmt, na_rep="-")
    mean_r = rates.mean() if len(rates) >= 2 else None
    std_r  = rates.std()  if len(rates) >= 2 else None
    has_stat = mean_r is not None and std_r is not None and std_r > 0

    def highlight_row(row):
        profit_low = False
        if profit_col and profit_col in row.index:
            p = pd.to_numeric(row.get(profit_col), errors='coerce')
            profit_low = (not pd.isna(p)) and (p < profit_target)

        anomaly_high = anomaly_low = False
        if has_stat:
            val = pd.to_numeric(row.get(rate_col, None), errors='coerce')
            if not pd.isna(val):
                anomaly_high = val > mean_r + threshold * std_r
                anomaly_low  = val < mean_r - threshold * std_r

        if profit_low and (anomaly_high or anomaly_low):
            return ['background-color: #fca5a5'] * len(row)  # 진한 빨강: 이중 위협
        if anomaly_high:
            return ['background-color: #fecaca'] * len(row)  # 연빨강: 교환율 높음
        if anomaly_low:
            return ['background-color: #fef9c3'] * len(row)  # 노랑: 교환율 낮음
        if profit_low:
            return ['background-color: #fed7aa'] * len(row)  # 주황: 30% 미달
        return [''] * len(row)

    return styler.apply(highlight_row, axis=1)


def _fmt_profit_only(df, profit_col="수익률_면가(%)", target=30):
    """목표 수익률 미달 행만 주황 강조 (통계 강조 없는 테이블용)"""
    fmt = {}
    for c in df.columns:
        if c in INT_COLS:   fmt[c] = "{:,.0f}"
        elif c in PCT_COLS: fmt[c] = "{:.1f}%"
    styler = df.style.format(fmt, na_rep="-")

    def highlight(row):
        p = pd.to_numeric(row.get(profit_col), errors='coerce')
        if not pd.isna(p) and p < target:
            return ['background-color: #fed7aa'] * len(row)
        return [''] * len(row)

    return styler.apply(highlight, axis=1)

def _anomaly_comment(val, mean_r, std_r, threshold=1.5):
    if pd.isna(val) or std_r == 0:
        return ""
    if val > mean_r + threshold * std_r:
        return "[!] 확률 조정 필요 (높음)"
    if val < mean_r - threshold * std_r:
        return "[!] 확인 필요 (낮음)"
    return ""

def _상품표시(공급사, 상품명, 면가):
    s = str(공급사).strip() if 공급사 else ""
    n = str(상품명).strip()
    f = int(면가) if 면가 else 0
    prefix = f"{s}  " if s else ""
    return f"{prefix}{n}  ({f:,}원)"

def calc_prize_row(row):
    nex      = row["예상 미교환율(%)"] / 100
    exp_ex   = round(row["발행수"] * (1 - nex))
    exp_xp   = row["발행수"] - exp_ex
    정산      = row["발행수"] * row["게임P"]
    상품대금  = exp_ex * row["면가"]
    수수료    = 상품대금 * row["수수료율"] / 100
    수익      = 정산 - 상품대금 + 수수료
    return pd.Series({
        "예상 교환수": exp_ex, "예상 만료수": exp_xp,
        "예상 정산": 정산, "예상 교환금액": 상품대금,
        "예상 수수료": round(수수료), "예상 수익": round(수익),
    })

def calc_coupon_row(row):
    nex      = row["예상 미사용율(%)"] / 100
    exp_us   = round(row["발행수"] * (1 - nex))
    exp_xp   = row["발행수"] - exp_us
    정산      = row["발행수"] * row["게임P"]
    상품대금  = exp_us * row["면가"]
    수익      = 정산 - 상품대금
    return pd.Series({
        "예상 사용수": exp_us, "예상 만료수": exp_xp,
        "예상 정산": 정산, "예상 교환금액": 상품대금,
        "예상 수익": round(수익),
    })

# ── 데이터 로드 ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_data():
    return load_all()

with st.spinner("Google Sheets에서 데이터 불러오는 중..."):
    try:
        prize_df, coupon_df, monthly_p, monthly_c, months, loaded_at = get_data()
        data_ok = True
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        data_ok = False
        prize_df = coupon_df = pd.DataFrame()
        monthly_p = monthly_c = {}
        months = []
        loaded_at = "-"

# ── 사이드바 ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎮 IBK 게임")
    st.caption(f"업데이트: {loaded_at}")
    st.divider()

    page = st.radio(
        "메뉴",
        ["📊 종합", "🎁 경품", "🎟 할인쿠폰", "📐 시뮬레이션"],
        label_visibility="collapsed",
    )

    st.divider()
    month_options = ["전체"] + months
    sel_month = st.selectbox("월 선택", month_options)

    st.divider()
    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("매체사 CSV · IBK 게임P 기준")

if not data_ok:
    st.stop()

# ── 월 필터 ────────────────────────────────────────────────────────────────────
if sel_month == "전체":
    cur_prize  = prize_df
    cur_coupon = coupon_df
else:
    cur_prize  = monthly_p.get(sel_month, pd.DataFrame())
    cur_coupon = monthly_c.get(sel_month, pd.DataFrame())


# ══════════════════════════════════════════════════════════════════════════════
# 📊 종합
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 종합":
    st.title("📊 종합")
    st.caption(f"기준: {sel_month}  ·  데이터 업데이트: {loaded_at}")
    st.divider()

    if cur_prize.empty and cur_coupon.empty:
        st.info("해당 월 데이터 없음")
        st.stop()

    tot_정산     = int(cur_prize["정산금액"].sum()  if not cur_prize.empty  else 0) \
                 + int(cur_coupon["정산금액"].sum() if not cur_coupon.empty else 0)
    tot_교환금액 = int(cur_prize["교환금액"].sum()  if not cur_prize.empty  else 0) \
                 + int(cur_coupon["교환금액"].sum() if not cur_coupon.empty else 0)
    tot_확정수익 = int(cur_prize["확정수익"].sum()  if not cur_prize.empty  else 0) \
                 + int(cur_coupon["확정수익"].sum() if not cur_coupon.empty else 0)
    tot_잠재수익 = int(cur_prize["잠재수익"].sum()  if not cur_prize.empty  else 0) \
                 + int(cur_coupon["잠재수익"].sum() if not cur_coupon.empty else 0)
    tot_면가합   = int((cur_prize["발행수"] * cur_prize["면가"]).sum() if not cur_prize.empty else 0) \
                 + int((cur_coupon["발행수"] * cur_coupon["면가"]).sum() if not cur_coupon.empty else 0)
    tot_확정수익률 = tot_확정수익 / tot_면가합 * 100 if tot_면가합 else 0
    tot_잠재수익률 = tot_잠재수익 / tot_면가합 * 100 if tot_면가합 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("IBK 소진포인트 (정산금액)", won(tot_정산))
    c2.metric("지급금액 합계 (액면가)",    won(tot_면가합))
    c3.metric("총 교환금액",               won(tot_교환금액))

    st.caption(
        "**확정수익** = 정산금액 − (발행수−만료수)×면가 + 수수료  "
        "  |  **잠재수익** = 정산금액 − 교환금액 + 수수료"
    )
    c4, c5, c6, c7 = st.columns(4)
    c4.metric("확정수익 (만료 확정분만)",    won(tot_확정수익))
    c5.metric("확정수익률 (면가기준)",       f"{tot_확정수익률:.1f}%")
    c6.metric("잠재수익 (만료+미교환 포함)", won(tot_잠재수익))
    c7.metric("잠재수익률 (면가기준)",       f"{tot_잠재수익률:.1f}%")

    if sel_month == "전체" and months:
        st.divider()
        st.subheader("월별 현황")
        rows = []
        for mk in months:
            mp = monthly_p.get(mk, pd.DataFrame())
            mc = monthly_c.get(mk, pd.DataFrame())
            정산   = int(mp["정산금액"].sum() if not mp.empty else 0) \
                   + int(mc["정산금액"].sum() if not mc.empty else 0)
            교환   = int(mp["교환금액"].sum() if not mp.empty else 0) \
                   + int(mc["교환금액"].sum() if not mc.empty else 0)
            확정   = int(mp["확정수익"].sum() if not mp.empty else 0) \
                   + int(mc["확정수익"].sum() if not mc.empty else 0)
            잠재   = int(mp["잠재수익"].sum() if not mp.empty else 0) \
                   + int(mc["잠재수익"].sum() if not mc.empty else 0)
            면가합 = int((mp["발행수"] * mp["면가"]).sum() if not mp.empty else 0) \
                   + int((mc["발행수"] * mc["면가"]).sum() if not mc.empty else 0)
            rows.append({
                "월":              mk,
                "정산금액":        정산,
                "지급금액(액면가)": 면가합,
                "총 교환금액":     교환,
                "확정수익":        확정,
                "잠재수익":        잠재,
                "수익률_면가(%)":  round(잠재 / 면가합 * 100, 1) if 면가합 else 0,
            })
        monthly_df = pd.DataFrame(rows)
        _sty_m = _fmt_profit_only(monthly_df, profit_col="수익률_면가(%)", target=30)
        _sty_m = _sty_m.format_index(lambda x: "수익률(%)" if x == "수익률_면가(%)" else x, axis=1)
        st.dataframe(_sty_m, use_container_width=True, hide_index=True)
        below = [r for r in rows if r["수익률_면가(%)"] < 30]
        above = [r for r in rows if r["수익률_면가(%)"] >= 30]
        if below:
            items_txt = "  /  ".join(
                f"{r['월']} {r['수익률_면가(%)']:.1f}% (목표 대비 {r['수익률_면가(%)']-30:+.1f}%p)"
                for r in below
            )
            st.warning(f"**[30% 목표 미달]** {items_txt}\n\n주황 강조 월의 교환율·발행량을 점검하세요.")
        if above and not below:
            st.success("**[30% 목표 분석]** 전체 월 목표 수익률(30%) 달성 중")
        elif above and below:
            ok_txt = ", ".join(r["월"] for r in above)
            st.info(f"**[30% 목표 달성 월]** {ok_txt}")


# ══════════════════════════════════════════════════════════════════════════════
# 🎁 경품
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎁 경품":
    st.title("🎁 경품")
    st.caption(f"기준: {sel_month}  ·  데이터 업데이트: {loaded_at}")
    st.divider()

    if cur_prize.empty:
        st.info("해당 월 경품 데이터 없음")
        st.stop()

    df_p = cur_prize.copy()
    df_p["교환율(%)"]  = (df_p["교환수"] / df_p["발행수"] * 100).round(1)
    df_p["미교환율(%)"] = (100 - df_p["교환율(%)"]).round(1)

    p_총정산    = int(df_p["정산금액"].sum())
    p_면가합    = int((df_p["발행수"] * df_p["면가"]).sum())
    p_확정수익  = int(df_p["확정수익"].sum())
    p_잠재수익  = int(df_p["잠재수익"].sum())
    p_확정수익률 = p_확정수익 / p_면가합 * 100 if p_면가합 else 0
    p_잠재수익률 = p_잠재수익 / p_면가합 * 100 if p_면가합 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 발행수",  f"{df_p['발행수'].sum():,}건")
    c2.metric("총 교환수",  f"{df_p['교환수'].sum():,}건")
    c3.metric("총 만료수",  f"{df_p['만료수'].sum():,}건")
    c4.metric("평균 교환율", pct(df_p["교환수"].sum() / df_p["발행수"].sum()))

    c5, c6, c7 = st.columns(3)
    c5.metric("총 정산금액", won(p_총정산))
    c6.metric("확정수익 (만료분만)",     won(p_확정수익), delta=f"수익률 {p_확정수익률:.1f}%")
    c7.metric("잠재수익 (만료+미교환)", won(p_잠재수익), delta=f"수익률 {p_잠재수익률:.1f}%")

    st.divider()
    st.subheader("상품별 내역")

    rates = df_p["교환율(%)"]
    mean_r = rates.mean()
    std_r  = rates.std() if len(rates) > 1 else 0

    df_p["상품"] = df_p.apply(
        lambda r: _상품표시(r.get("공급사명", ""), r["상품명"], r["면가"]), axis=1
    )
    def _prize_note(row):
        parts = []
        a = _anomaly_comment(row["교환율(%)"], mean_r, std_r)
        if a:
            parts.append(a)
        if row["수익률_면가(%)"] < 30:
            parts.append(f"수익률 {row['수익률_면가(%)']:.1f}% (30% 미달)")
        return "  /  ".join(parts)

    df_p["비고"] = df_p.apply(_prize_note, axis=1)
    df_p["확정수익_표시"] = df_p.apply(
        lambda r: f"{int(r['확정수익']):,}원  ({r['확정수익률(%)']:.1f}%)", axis=1
    )
    df_p["잠재수익_표시"] = df_p.apply(
        lambda r: f"{int(r['잠재수익']):,}원  ({r['잠재수익률(%)']:.1f}%)", axis=1
    )

    cols = ["게임명", "상품", "게임P", "발행수", "교환수", "만료수",
            "교환율(%)", "미교환율(%)", "정산금액", "교환금액", "수수료금액",
            "확정수익_표시", "잠재수익_표시", "수익률_면가(%)", "비고"]

    st.caption("확정수익 = 정산금액 − (발행수−만료수)×면가 + 수수료  |  잠재수익 = 정산금액 − 교환금액 + 수수료")
    _sty_p = _fmt(df_p[cols])
    _sty_p = _sty_p.set_properties(
        subset=["확정수익_표시", "잠재수익_표시"], **{"font-size": "16px"}
    )
    _sty_p = _sty_p.format_index(
        lambda x: {"확정수익_표시": "확정수익", "잠재수익_표시": "잠재수익", "수익률_면가(%)": "수익률(%)"}.get(x, x), axis=1
    )
    st.dataframe(_sty_p, use_container_width=True, hide_index=True)

    p_below30 = df_p[df_p["수익률_면가(%)"] < 30]
    if not p_below30.empty:
        items_txt = "  /  ".join(
            f"{r['상품명']} ({r['수익률_면가(%)']:.1f}%)"
            for _, r in p_below30.iterrows()
        )
        st.warning(
            f"**[30% 목표 미달 {len(p_below30)}개 상품]** {items_txt}\n\n"
            f"해당 상품의 교환율이 높거나 게임P 대비 면가가 커서 수익률이 낮습니다. "
            f"발행량 조절 또는 확률 재설계가 필요합니다. (잠재수익 기준)"
        )
    else:
        st.success(f"**[30% 목표 분석]** 전체 경품 상품 목표 수익률(30%) 달성 중  ·  수익률 최저: {df_p['수익률_면가(%)'].min():.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# 🎟 할인쿠폰
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎟 할인쿠폰":
    st.title("🎟 할인쿠폰")
    st.caption(f"기준: {sel_month}  ·  데이터 업데이트: {loaded_at}")
    st.divider()

    if cur_coupon.empty:
        st.info("해당 월 쿠폰 데이터 없음")
        st.stop()

    df_c = cur_coupon.copy()
    df_c["사용율(%)"]   = (df_c["사용수"] / df_c["발행수"] * 100).round(1)
    df_c["미사용율(%)"] = (100 - df_c["사용율(%)"]).round(1)

    c_총정산    = int(df_c["정산금액"].sum())
    c_면가합    = int((df_c["발행수"] * df_c["면가"]).sum())
    c_확정수익  = int(df_c["확정수익"].sum())
    c_잠재수익  = int(df_c["잠재수익"].sum())
    c_확정수익률 = c_확정수익 / c_면가합 * 100 if c_면가합 else 0
    c_잠재수익률 = c_잠재수익 / c_면가합 * 100 if c_면가합 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 발행수",  f"{df_c['발행수'].sum():,}건")
    c2.metric("총 사용수",  f"{df_c['사용수'].sum():,}건")
    c3.metric("총 만료수",  f"{df_c['만료수'].sum():,}건")
    c4.metric("평균 사용률", pct(df_c["사용수"].sum() / df_c["발행수"].sum()))

    c5, c6, c7 = st.columns(3)
    c5.metric("총 정산금액", won(c_총정산))
    c6.metric("확정수익 (만료분만)",     won(c_확정수익), delta=f"수익률 {c_확정수익률:.1f}%")
    c7.metric("잠재수익 (만료+미교환)", won(c_잠재수익), delta=f"수익률 {c_잠재수익률:.1f}%")

    st.divider()
    st.subheader("쿠폰별 내역")

    rates_c = df_c["사용율(%)"]
    mean_c  = rates_c.mean()
    std_c   = rates_c.std() if len(rates_c) > 1 else 0

    df_c["쿠폰"] = df_c.apply(
        lambda r: f"{r['쿠폰명']}  ({int(r['면가']):,}원)", axis=1
    )
    def _coupon_note(row):
        parts = []
        a = _anomaly_comment(row["사용율(%)"], mean_c, std_c)
        if a:
            parts.append(a)
        if row["수익률_면가(%)"] < 30:
            parts.append(f"수익률 {row['수익률_면가(%)']:.1f}% (30% 미달)")
        return "  /  ".join(parts)

    df_c["비고"] = df_c.apply(_coupon_note, axis=1)
    df_c["확정수익_표시"] = df_c.apply(
        lambda r: f"{int(r['확정수익']):,}원  ({r['확정수익률(%)']:.1f}%)", axis=1
    )
    df_c["잠재수익_표시"] = df_c.apply(
        lambda r: f"{int(r['잠재수익']):,}원  ({r['잠재수익률(%)']:.1f}%)", axis=1
    )

    cols = ["게임명", "쿠폰", "게임P", "발행수", "사용수", "만료수",
            "사용율(%)", "미사용율(%)", "정산금액", "교환금액",
            "확정수익_표시", "잠재수익_표시", "수익률_면가(%)", "비고"]

    st.caption("확정수익 = 정산금액 − (발행수−만료수)×면가  |  잠재수익 = 정산금액 − 교환금액")
    _sty_c = _fmt(df_c[cols])
    _sty_c = _sty_c.set_properties(
        subset=["확정수익_표시", "잠재수익_표시"], **{"font-size": "16px"}
    )
    _sty_c = _sty_c.format_index(
        lambda x: {"확정수익_표시": "확정수익", "잠재수익_표시": "잠재수익", "수익률_면가(%)": "수익률(%)"}.get(x, x), axis=1
    )
    st.dataframe(_sty_c, use_container_width=True, hide_index=True)

    c_below30 = df_c[df_c["수익률_면가(%)"] < 30]
    if not c_below30.empty:
        items_txt = "  /  ".join(
            f"{r['쿠폰명']} ({r['수익률_면가(%)']:.1f}%)"
            for _, r in c_below30.iterrows()
        )
        st.warning(
            f"**[30% 목표 미달 {len(c_below30)}개 쿠폰]** {items_txt}\n\n"
            f"해당 쿠폰의 사용율이 높아 교환금액이 정산금액에 근접합니다. "
            f"발행량 또는 쿠폰 면가 조정이 필요합니다. (잠재수익 기준)"
        )
    else:
        st.success(f"**[30% 목표 분석]** 전체 할인쿠폰 목표 수익률(30%) 달성 중  ·  수익률 최저: {df_c['수익률_면가(%)'].min():.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# 📐 시뮬레이션
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📐 시뮬레이션":
    st.title("📐 미교환율 시뮬레이션")
    st.caption(f"기준: {sel_month}  ·  수치 수정 후 [결과 계산] 버튼 클릭")
    st.divider()

    sim_prize_df  = cur_prize.copy()  if not cur_prize.empty  else pd.DataFrame()
    sim_coupon_df = cur_coupon.copy() if not cur_coupon.empty else pd.DataFrame()

    # session_state 초기화
    if "sim_prize_adj" not in st.session_state:
        st.session_state.sim_prize_adj = {}
    if "sim_coupon_adj" not in st.session_state:
        st.session_state.sim_coupon_adj = {}
    if "sim_result_ready" not in st.session_state:
        st.session_state.sim_result_ready = False

    def _fmt_int(v):
        try: return f"{int(v):,}"
        except: return v

    # ── 경품 편집 테이블 ────────────────────────────────────────────────────────
    edited_p_state = None
    sim_p = pd.DataFrame()
    if not sim_prize_df.empty:
        sim_p = sim_prize_df[["게임명", "공급사명", "상품명", "게임P", "면가", "발행수", "교환수", "만료수", "수수료율"]].copy()
        sim_p["현재 미교환율(%)"] = ((sim_p["발행수"] - sim_p["교환수"]) / sim_p["발행수"] * 100).round(1)

        def _get_prize_adj(row):
            key = (row["게임명"], row["상품명"])
            return st.session_state.sim_prize_adj.get(key, row["현재 미교환율(%)"])
        sim_p["예상 미교환율(%)"] = sim_p.apply(_get_prize_adj, axis=1)

        disp_p = sim_p.copy()
        disp_p["상품"] = disp_p.apply(
            lambda r: _상품표시(r.get("공급사명", ""), r["상품명"], r["면가"]), axis=1
        )
        for c in ["게임P", "발행수", "교환수", "만료수"]:
            disp_p[c] = disp_p[c].apply(_fmt_int)

        st.subheader("🎁 경품 — 미교환율 조정")
        edited_p_state = st.data_editor(
            disp_p[["게임명", "상품", "게임P", "발행수", "교환수", "만료수", "수수료율", "현재 미교환율(%)", "예상 미교환율(%)"]],
            use_container_width=True,
            hide_index=True,
            disabled=["게임명", "상품", "게임P", "발행수", "교환수", "만료수", "수수료율", "현재 미교환율(%)"],
            column_config={
                "현재 미교환율(%)": st.column_config.NumberColumn("현재 미교환율(%)", format="%.1f%%"),
                "예상 미교환율(%)": st.column_config.NumberColumn(
                    "예상 미교환율(%)", min_value=0.0, max_value=100.0, step=0.5, format="%.1f%%"
                ),
            },
            key="sim_prize_editor",
        )

    # ── 쿠폰 편집 테이블 ────────────────────────────────────────────────────────
    edited_c_state = None
    sim_c = pd.DataFrame()
    if not sim_coupon_df.empty:
        sim_c = sim_coupon_df[["게임명", "쿠폰명", "게임P", "면가", "발행수", "사용수", "만료수"]].copy()
        sim_c["현재 미사용율(%)"] = ((sim_c["발행수"] - sim_c["사용수"]) / sim_c["발행수"] * 100).round(1)

        def _get_coupon_adj(row):
            key = (row["게임명"], row["쿠폰명"])
            return st.session_state.sim_coupon_adj.get(key, row["현재 미사용율(%)"])
        sim_c["예상 미사용율(%)"] = sim_c.apply(_get_coupon_adj, axis=1)

        disp_c = sim_c.copy()
        disp_c["쿠폰"] = disp_c.apply(
            lambda r: f"{r['쿠폰명']}  ({int(r['면가']):,}원)", axis=1
        )
        for c in ["게임P", "발행수", "사용수", "만료수"]:
            disp_c[c] = disp_c[c].apply(_fmt_int)

        st.subheader("🎟 할인쿠폰 — 미사용율 조정")
        edited_c_state = st.data_editor(
            disp_c[["게임명", "쿠폰", "게임P", "발행수", "사용수", "만료수", "현재 미사용율(%)", "예상 미사용율(%)"]],
            use_container_width=True,
            hide_index=True,
            disabled=["게임명", "쿠폰", "게임P", "발행수", "사용수", "만료수", "현재 미사용율(%)"],
            column_config={
                "현재 미사용율(%)": st.column_config.NumberColumn("현재 미사용율(%)", format="%.1f%%"),
                "예상 미사용율(%)": st.column_config.NumberColumn(
                    "예상 미사용율(%)", min_value=0.0, max_value=100.0, step=0.5, format="%.1f%%"
                ),
            },
            key="sim_coupon_editor",
        )

    # ── 계산 버튼 ───────────────────────────────────────────────────────────────
    st.divider()
    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
    run_calc = col_btn1.button("📊 결과 계산", type="primary", use_container_width=True)
    if col_btn2.button("↺ 초기화", use_container_width=True):
        st.session_state.sim_prize_adj = {}
        st.session_state.sim_coupon_adj = {}
        st.session_state.sim_result_ready = False
        st.rerun()

    if run_calc:
        if edited_p_state is not None:
            for i, erow in edited_p_state.iterrows():
                key = (sim_p.at[i, "게임명"], sim_p.at[i, "상품명"])
                st.session_state.sim_prize_adj[key] = erow["예상 미교환율(%)"]
        if edited_c_state is not None and not sim_c.empty:
            for i, erow in edited_c_state.iterrows():
                key = (sim_c.at[i, "게임명"], sim_c.at[i, "쿠폰명"])
                st.session_state.sim_coupon_adj[key] = erow["예상 미사용율(%)"]
        st.session_state.sim_result_ready = True

    # ── 예상 결과 요약 ──────────────────────────────────────────────────────────
    if st.session_state.sim_result_ready:
        prize_calc = pd.DataFrame()
        coupon_calc = pd.DataFrame()

        if not sim_p.empty and edited_p_state is not None:
            calc_p = sim_p.copy()
            calc_p["예상 미교환율(%)"] = edited_p_state["예상 미교환율(%)"]
            prize_calc = calc_p.join(calc_p.apply(calc_prize_row, axis=1))

        if not sim_coupon_df.empty:
            sim_c2 = sim_coupon_df[["게임명", "쿠폰명", "게임P", "면가", "발행수", "사용수", "만료수"]].copy()
            sim_c2["현재 미사용율(%)"] = ((sim_c2["발행수"] - sim_c2["사용수"]) / sim_c2["발행수"] * 100).round(1)
            sim_c2["예상 미사용율(%)"] = sim_c2.apply(
                lambda r: st.session_state.sim_coupon_adj.get((r["게임명"], r["쿠폰명"]), r["현재 미사용율(%)"]), axis=1
            )
            coupon_calc = sim_c2.join(sim_c2.apply(calc_coupon_row, axis=1))

        if not prize_calc.empty or not coupon_calc.empty:
            st.subheader("📊 예상 수익 결과")

            s정산 = s교환 = s수수료 = s수익 = s만료 = 0
            if not prize_calc.empty:
                s정산   += int(prize_calc["예상 정산"].sum())
                s교환   += int(prize_calc["예상 교환금액"].sum())
                s수수료 += int(prize_calc["예상 수수료"].sum())
                s수익   += int(prize_calc["예상 수익"].sum())
                s만료   += int((prize_calc["예상 만료수"] * prize_calc["면가"]).sum())
            if not coupon_calc.empty:
                s정산  += int(coupon_calc["예상 정산"].sum())
                s교환  += int(coupon_calc["예상 교환금액"].sum())
                s수익  += int(coupon_calc["예상 수익"].sum())
                s만료  += int((coupon_calc["예상 만료수"] * coupon_calc["면가"]).sum())
            s수익률 = s수익 / s정산 * 100 if s정산 else 0

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("예상 정산금액",  won(s정산))
            c2.metric("예상 교환금액",  won(s교환))
            c3.metric("예상 수수료",    won(s수수료))
            c4.metric("예상 잠재수익",  won(s수익), delta=f"만료 {won(s만료)} 포함")
            c5.metric("예상 수익률",    f"{s수익률:.1f}%")

            st.divider()
            if not prize_calc.empty:
                st.markdown("**경품 상품별 예상 결과**")
                pc = prize_calc[["게임명", "공급사명", "상품명", "면가", "발행수", "예상 교환수", "예상 만료수",
                                  "예상 정산", "예상 교환금액", "예상 수수료", "예상 수익"]].copy()
                pc["상품"] = pc.apply(lambda r: _상품표시(r.get("공급사명", ""), r["상품명"], r["면가"]), axis=1)
                pc["예상 수익률(%)"] = (pc["예상 수익"] / (pc["발행수"] * pc["면가"]) * 100).where(pc["예상 정산"] > 0).round(1)
                pc = pc[["게임명", "상품", "발행수", "예상 교환수", "예상 만료수",
                          "예상 정산", "예상 교환금액", "예상 수수료", "예상 수익", "예상 수익률(%)"]]
                st.dataframe(_fmt(pc), use_container_width=True, hide_index=True)
            if not coupon_calc.empty:
                st.markdown("**쿠폰별 예상 결과**")
                cc = coupon_calc[["게임명", "쿠폰명", "면가", "발행수", "예상 사용수", "예상 만료수",
                                   "예상 정산", "예상 교환금액", "예상 수익"]].copy()
                cc["쿠폰"] = cc.apply(lambda r: f"{r['쿠폰명']}  ({int(r['면가']):,}원)", axis=1)
                cc["예상 수익률(%)"] = (cc["예상 수익"] / (cc["발행수"] * cc["면가"]) * 100).where(cc["예상 정산"] > 0).round(1)
                cc = cc[["게임명", "쿠폰", "발행수", "예상 사용수", "예상 만료수",
                          "예상 정산", "예상 교환금액", "예상 수익", "예상 수익률(%)"]]
                st.dataframe(_fmt(cc), use_container_width=True, hide_index=True)
    else:
        st.info("수치를 수정한 후 [📊 결과 계산] 버튼을 클릭하세요.")
