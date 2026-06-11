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
    "정산금액", "상품대금", "수수료금액", "최종수익",
    "예상 교환수", "예상 사용수", "예상 만료수",
    "예상 정산", "예상 상품대금", "예상 수수료", "예상 수익",
    "경품비", "쿠폰비", "현재수익", "미교환수익", "예상수익",
]
PCT_COLS = [
    "교환율(%)", "미교환율(%)", "사용율(%)", "미사용율(%)", "수수료율",
    "수익률_정산(%)", "수익률_면가(%)", "예상 수익률(%)",
    "현재 미교환율(%)", "예상 미교환율(%)",
    "현재 미사용율(%)", "예상 미사용율(%)",
    "현재수익률(%)", "예상수익률(%)",
]

def won(n):  return f"{int(n):,}원"
def pct(r):  return f"{r * 100:.1f}%"

def _fmt(df):
    fmt = {}
    for c in df.columns:
        if c in INT_COLS:   fmt[c] = "{:,.0f}"
        elif c in PCT_COLS: fmt[c] = "{:.1f}%"
    return df.style.format(fmt, na_rep="-")

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
        "예상 정산": 정산, "예상 상품대금": 상품대금,
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
        "예상 정산": 정산, "예상 상품대금": 상품대금,
        "예상 수익": round(수익),
    })

# ── 데이터 로드 ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_data():
    return load_all()

with st.spinner("Google Sheets에서 데이터 불러오는 중..."):
    try:
        prize_df, coupon_df, monthly_p, monthly_c, months = get_data()
        data_ok = True
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        data_ok = False
        prize_df = coupon_df = pd.DataFrame()
        monthly_p = monthly_c = {}
        months = []

# ── 사이드바 ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎮 IBK 게임")
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
    st.caption(f"기준: {sel_month}")
    st.divider()

    if cur_prize.empty and cur_coupon.empty:
        st.info("해당 월 데이터 없음")
        st.stop()

    # 시트 수식 결과값 직접 합산 (재계산 없음)
    tot_정산  = int(cur_prize["정산금액"].sum()  if not cur_prize.empty  else 0) \
              + int(cur_coupon["정산금액"].sum() if not cur_coupon.empty else 0)
    tot_수익  = int(cur_prize["최종수익"].sum()  if not cur_prize.empty  else 0) \
              + int(cur_coupon["최종수익"].sum() if not cur_coupon.empty else 0)
    tot_상품  = int(cur_prize["상품대금"].sum()  if not cur_prize.empty  else 0) \
              + int(cur_coupon["상품대금"].sum() if not cur_coupon.empty else 0)
    tot_면가합 = int((cur_prize["발행수"] * cur_prize["면가"]).sum() if not cur_prize.empty else 0) \
               + int((cur_coupon["발행수"] * cur_coupon["면가"]).sum() if not cur_coupon.empty else 0)
    tot_수익률 = tot_수익 / tot_면가합 * 100 if tot_면가합 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("IBK 소진포인트 (정산)",  won(tot_정산))
    c2.metric("경품 + 쿠폰 상품대금",   won(tot_상품))
    c3.metric("최종수익",               won(tot_수익))
    c4.metric("수익률(면가기준)",        f"{tot_수익률:.1f}%")

    if sel_month == "전체" and months:
        st.divider()
        st.subheader("월별 현황")
        rows = []
        for mk in months:
            mp = monthly_p.get(mk, pd.DataFrame())
            mc = monthly_c.get(mk, pd.DataFrame())
            정산 = int(mp["정산금액"].sum() if not mp.empty else 0) \
                 + int(mc["정산금액"].sum() if not mc.empty else 0)
            상품 = int(mp["상품대금"].sum() if not mp.empty else 0) \
                 + int(mc["상품대금"].sum() if not mc.empty else 0)
            수익 = int(mp["최종수익"].sum() if not mp.empty else 0) \
                 + int(mc["최종수익"].sum() if not mc.empty else 0)
            면가합 = int((mp["발행수"] * mp["면가"]).sum() if not mp.empty else 0) \
                   + int((mc["발행수"] * mc["면가"]).sum() if not mc.empty else 0)
            rows.append({
                "월": mk,
                "정산금액":       정산,
                "상품대금":       상품,
                "최종수익":       수익,
                "수익률_면가(%)": round(수익 / 면가합 * 100, 1) if 면가합 else 0,
            })
        st.dataframe(_fmt(pd.DataFrame(rows)), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# 🎁 경품
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎁 경품":
    st.title("🎁 경품")
    st.caption(f"기준: {sel_month}")
    st.divider()

    if cur_prize.empty:
        st.info("해당 월 경품 데이터 없음")
        st.stop()

    df_p = cur_prize.copy()
    df_p["교환율(%)"]  = (df_p["교환수"] / df_p["발행수"] * 100).round(1)
    df_p["미교환율(%)"] = (100 - df_p["교환율(%)"]).round(1)

    p_총정산 = int(df_p["정산금액"].sum())
    p_총수익 = int(df_p["최종수익"].sum())
    p_수익률 = p_총수익 / p_총정산 * 100 if p_총정산 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 발행수",  f"{df_p['발행수'].sum():,}건")
    c2.metric("총 교환수",  f"{df_p['교환수'].sum():,}건")
    c3.metric("총 만료수",  f"{df_p['만료수'].sum():,}건")
    c4.metric("평균 교환율", pct(df_p["교환수"].sum() / df_p["발행수"].sum()))

    c5, c6, c7 = st.columns(3)
    c5.metric("총 정산금액", won(p_총정산))
    c6.metric("총 최종수익", won(p_총수익))
    c7.metric("수익률",      f"{p_수익률:.1f}%")

    st.divider()
    st.subheader("상품별 내역")
    df_p["상품"] = df_p.apply(
        lambda r: _상품표시(r.get("공급사명", ""), r["상품명"], r["면가"]), axis=1
    )
    cols = ["게임명", "상품", "게임P", "발행수", "교환수", "만료수",
            "교환율(%)", "미교환율(%)", "정산금액", "상품대금", "수수료금액", "최종수익", "수익률_면가(%)"]
    st.dataframe(_fmt(df_p[cols]), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# 🎟 할인쿠폰
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎟 할인쿠폰":
    st.title("🎟 할인쿠폰")
    st.caption(f"기준: {sel_month}")
    st.divider()

    if cur_coupon.empty:
        st.info("해당 월 쿠폰 데이터 없음")
        st.stop()

    df_c = cur_coupon.copy()
    df_c["사용율(%)"]   = (df_c["사용수"] / df_c["발행수"] * 100).round(1)
    df_c["미사용율(%)"] = (100 - df_c["사용율(%)"]).round(1)

    c_총정산 = int(df_c["정산금액"].sum())
    c_총수익 = int(df_c["최종수익"].sum())
    c_수익률 = c_총수익 / c_총정산 * 100 if c_총정산 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 발행수",  f"{df_c['발행수'].sum():,}건")
    c2.metric("총 사용수",  f"{df_c['사용수'].sum():,}건")
    c3.metric("총 만료수",  f"{df_c['만료수'].sum():,}건")
    c4.metric("평균 사용률", pct(df_c["사용수"].sum() / df_c["발행수"].sum()))

    c5, c6, c7 = st.columns(3)
    c5.metric("총 정산금액", won(c_총정산))
    c6.metric("총 최종수익", won(c_총수익))
    c7.metric("수익률",      f"{c_수익률:.1f}%")

    st.divider()
    st.subheader("쿠폰별 내역")
    df_c["쿠폰"] = df_c.apply(
        lambda r: f"{r['쿠폰명']}  ({int(r['면가']):,}원)", axis=1
    )
    cols = ["게임명", "쿠폰", "게임P", "발행수", "사용수", "만료수",
            "사용율(%)", "미사용율(%)", "정산금액", "상품대금", "최종수익", "수익률_면가(%)"]
    st.dataframe(_fmt(df_c[cols]), use_container_width=True, hide_index=True)



# ══════════════════════════════════════════════════════════════════════════════
# 📐 시뮬레이션
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📐 시뮬레이션":
    st.title("📐 미교환율 시뮬레이션")
    st.caption(f"기준: {sel_month}  ·  예상 미교환율 수정 → 결과 자동 반영")
    st.divider()

    sim_prize_df  = cur_prize.copy()  if not cur_prize.empty  else pd.DataFrame()
    sim_coupon_df = cur_coupon.copy() if not cur_coupon.empty else pd.DataFrame()

    def _fmt_int(v):
        try: return f"{int(v):,}"
        except: return v

    # ── 경품 편집 테이블 ────────────────────────────────────────────────────────
    prize_calc = pd.DataFrame()
    if not sim_prize_df.empty:
        sim_p = sim_prize_df[["게임명", "공급사명", "상품명", "게임P", "면가", "발행수", "교환수", "만료수", "수수료율"]].copy()
        sim_p["현재 미교환율(%)"] = ((sim_p["발행수"] - sim_p["교환수"]) / sim_p["발행수"] * 100).round(1)
        sim_p["예상 미교환율(%)"] = sim_p["현재 미교환율(%)"]

        disp_p = sim_p.copy()
        disp_p["상품"] = disp_p.apply(
            lambda r: _상품표시(r.get("공급사명", ""), r["상품명"], r["면가"]), axis=1
        )
        for c in ["게임P", "발행수", "교환수", "만료수"]:
            disp_p[c] = disp_p[c].apply(_fmt_int)

        st.subheader("🎁 경품 — 미교환율 조정")
        edited_p = st.data_editor(
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
        calc_p = sim_p.copy()
        calc_p["예상 미교환율(%)"] = edited_p["예상 미교환율(%)"]
        prize_calc = calc_p.join(calc_p.apply(calc_prize_row, axis=1))

    # ── 쿠폰 편집 테이블 ────────────────────────────────────────────────────────
    coupon_calc = pd.DataFrame()
    if not sim_coupon_df.empty:
        sim_c = sim_coupon_df[["게임명", "쿠폰명", "게임P", "면가", "발행수", "사용수", "만료수"]].copy()
        sim_c["현재 미사용율(%)"] = ((sim_c["발행수"] - sim_c["사용수"]) / sim_c["발행수"] * 100).round(1)
        sim_c["예상 미사용율(%)"] = sim_c["현재 미사용율(%)"]

        disp_c = sim_c.copy()
        disp_c["쿠폰"] = disp_c.apply(
            lambda r: f"{r['쿠폰명']}  ({int(r['면가']):,}원)", axis=1
        )
        for c in ["게임P", "발행수", "사용수", "만료수"]:
            disp_c[c] = disp_c[c].apply(_fmt_int)

        st.subheader("🎟 할인쿠폰 — 미사용율 조정")
        edited_c = st.data_editor(
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
        calc_c = sim_c.copy()
        calc_c["예상 미사용율(%)"] = edited_c["예상 미사용율(%)"]
        coupon_calc = calc_c.join(calc_c.apply(calc_coupon_row, axis=1))

    # ── 예상 결과 요약 ──────────────────────────────────────────────────────────
    if not prize_calc.empty or not coupon_calc.empty:
        st.divider()
        st.subheader("📊 예상 수익 결과")

        s정산 = s상품 = s수수료 = s수익 = s만료 = 0
        if not prize_calc.empty:
            s정산   += int(prize_calc["예상 정산"].sum())
            s상품   += int(prize_calc["예상 상품대금"].sum())
            s수수료 += int(prize_calc["예상 수수료"].sum())
            s수익   += int(prize_calc["예상 수익"].sum())
            s만료   += int((prize_calc["예상 만료수"] * prize_calc["면가"]).sum())
        if not coupon_calc.empty:
            s정산  += int(coupon_calc["예상 정산"].sum())
            s상품  += int(coupon_calc["예상 상품대금"].sum())
            s수익  += int(coupon_calc["예상 수익"].sum())
            s만료  += int((coupon_calc["예상 만료수"] * coupon_calc["면가"]).sum())
        s수익률 = s수익 / s정산 * 100 if s정산 else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("예상 정산금액",  won(s정산))
        c2.metric("예상 상품대금",  won(s상품))
        c3.metric("예상 수수료",    won(s수수료))
        c4.metric("예상 최종수익",  won(s수익), delta=f"만료 {won(s만료)} 포함")
        c5.metric("예상 수익률",    f"{s수익률:.1f}%")

        st.divider()
        if not prize_calc.empty:
            st.markdown("**경품 상품별 예상 결과**")
            pc = prize_calc[["게임명", "공급사명", "상품명", "면가", "발행수", "예상 교환수", "예상 만료수",
                              "예상 정산", "예상 상품대금", "예상 수수료", "예상 수익"]].copy()
            pc["상품"] = pc.apply(lambda r: _상품표시(r.get("공급사명", ""), r["상품명"], r["면가"]), axis=1)
            pc["예상 수익률(%)"] = (pc["예상 수익"] / (pc["발행수"] * pc["면가"]) * 100).where(pc["예상 정산"] > 0).round(1)
            pc = pc[["게임명", "상품", "발행수", "예상 교환수", "예상 만료수",
                      "예상 정산", "예상 상품대금", "예상 수수료", "예상 수익", "예상 수익률(%)"]]
            st.dataframe(_fmt(pc), use_container_width=True, hide_index=True)
        if not coupon_calc.empty:
            st.markdown("**쿠폰별 예상 결과**")
            cc = coupon_calc[["게임명", "쿠폰명", "면가", "발행수", "예상 사용수", "예상 만료수",
                               "예상 정산", "예상 상품대금", "예상 수익"]].copy()
            cc["쿠폰"] = cc.apply(lambda r: f"{r['쿠폰명']}  ({int(r['면가']):,}원)", axis=1)
            cc["예상 수익률(%)"] = (cc["예상 수익"] / (cc["발행수"] * cc["면가"]) * 100).where(cc["예상 정산"] > 0).round(1)
            cc = cc[["게임명", "쿠폰", "발행수", "예상 사용수", "예상 만료수",
                      "예상 정산", "예상 상품대금", "예상 수익", "예상 수익률(%)"]]
            st.dataframe(_fmt(cc), use_container_width=True, hide_index=True)
