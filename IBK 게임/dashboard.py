import os
import streamlit as st
import pandas as pd
from data_loader import load_all, load_report_sheet, list_snapshot_sheets

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
/* 보고 테이블 헤더 */
[data-testid="stTable"] thead th {
    color: #1e293b !important;
    font-weight: 700 !important;
    background: #f1f5f9;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

# ── 포맷 헬퍼 ──────────────────────────────────────────────────────────────────
INT_COLS = [
    "게임P", "면가", "발행수", "교환수", "사용수", "만료수",
    "정산금액", "교환금액", "수수료금액", "확정수익", "잠재수익",
    "지급금액(액면가)", "총 교환금액",
    "예상 교환수", "예상 사용수", "예상 만료수",
    "예상 정산", "예상 교환금액", "예상 수수료", "예상 수익",
    "경품비", "쿠폰비", "현재수익", "미교환수익", "예상수익",
]
PCT_COLS = [
    "교환율(%)", "미교환율(%)", "사용율(%)", "미사용율(%)", "수수료율",
    "수익률_면가(%)", "수익률(%)", "예상 확정수익률(%)",
    "현재 미교환율(%)", "예상 미교환율(%)",
    "현재 미사용율(%)", "예상 미사용율(%)",
    "현재수익률(%)", "예상수익률(%)",
    "확정수익률(%)", "잠재수익률(%)",
]

def won(n):  return f"{int(n):,}원"
def pct(r):  return f"{r * 100:.1f}%"

def _metric_profit(col, label, amount_str, rate):
    color = "#16a34a" if rate >= 0 else "#dc2626"
    col.markdown(f"""
<div style="border:1px solid #e5e7eb;border-radius:8px;padding:14px 18px;background:#fff;">
  <div style="color:rgba(49,51,63,.6);font-size:13px;margin-bottom:6px;">{label}</div>
  <div style="font-size:22px;font-weight:700;color:rgb(49,51,63);white-space:nowrap;">
    {amount_str}&nbsp;&nbsp;&nbsp;<span style="color:{color};">{rate:+.1f}%</span>
  </div>
</div>
""", unsafe_allow_html=True)

def _fmt(df, skip_fmt=None):
    _skip = set(skip_fmt or [])
    fmt = {}
    for c in df.columns:
        if c in _skip: continue
        if c in INT_COLS:   fmt[c] = "{:,.0f}"
        elif c in PCT_COLS: fmt[c] = "{:.1f}%"
    return df.style.format(fmt, na_rep="-")

def _fmt_highlight(df, rate_col, threshold=1.5, skip_fmt=None):
    """rate_col 기준 통계적 이상값 행 색상 강조"""
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
        if has_stat:
            val = pd.to_numeric(row.get(rate_col, None), errors='coerce')
            if not pd.isna(val):
                if val > mean_r + threshold * std_r:
                    return ['background-color: #fecaca'] * len(row)
                if val < mean_r - threshold * std_r:
                    return ['background-color: #fef9c3'] * len(row)
        return [''] * len(row)

    return styler.apply(highlight_row, axis=1)

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

# ── 보고 시트 렌더러 ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _get_report_rows(sheet_name):
    try:
        return load_report_sheet(sheet_name)
    except Exception:
        return []

def _render_report(rows):
    import re
    _PURE_NUM = re.compile(r'^-?[\d,]+$')  # 순수 정수(콤마 포함) → 헤더 아님

    def clean(row):
        r = list(row[1:]) if len(row) > 1 else []
        while r and str(r[-1]).strip() == '':
            r.pop()
        return [str(c) for c in r]

    def dedup_cols(cols):
        seen: dict = {}
        out = []
        for c in cols:
            if c in seen:
                seen[c] += 1
                out.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                out.append(c)
        return out

    def is_header(row):
        """첫 행에 순수 정수값이 없으면 헤더로 판단"""
        return not any(_PURE_NUM.match(c.strip()) for c in row if c.strip())

    def is_kv_row(row):
        """짝수 개 셀로 홀수 인덱스가 모두 숫자형이면 레이블-값 쌍 행"""
        cells = [c for c in row if c.strip()]
        if len(cells) < 2 or len(cells) % 2 != 0:
            return False
        return all(_PURE_NUM.match(cells[i]) for i in range(1, len(cells), 2))

    def render_kv(data_rows):
        """레이블-값 쌍 형태 행을 metric 카드로 표시"""
        for row in data_rows:
            pairs = [(row[i], row[i + 1] if i + 1 < len(row) else '')
                     for i in range(0, len(row), 2)]
            pairs = [(l, v) for l, v in pairs if l.strip()]
            if pairs:
                cols = st.columns(len(pairs))
                for col, (label, val) in zip(cols, pairs):
                    col.metric(label=label, value=val)

    def render_table(data_rows):
        """첫 행을 헤더로 사용하는 일반 테이블"""
        body = data_rows[1:]
        # 헤더보다 데이터 행이 넓을 수 있으므로 최대 열 수 기준으로 맞춤
        n = max(len(data_rows[0]), max((len(r) for r in body), default=0))
        header = dedup_cols(data_rows[0] + [''] * (n - len(data_rows[0])))
        padded = [(r + [''] * n)[:n] for r in body]
        th = 'style="color:#1e293b;font-weight:700;background:#f1f5f9;padding:8px 14px;border-bottom:2px solid #cbd5e1;text-align:left;font-size:13px;"'
        td = 'style="padding:7px 14px;border-bottom:1px solid #f1f5f9;font-size:13px;"'
        html = '<table style="width:100%;border-collapse:collapse;">'
        html += '<thead><tr>' + ''.join(f'<th {th}>{h}</th>' for h in header) + '</tr></thead>'
        html += '<tbody>'
        for i, row in enumerate(padded):
            bg = '#ffffff' if i % 2 == 0 else '#f8fafc'
            html += f'<tr style="background:{bg}">' + ''.join(f'<td {td}>{c}</td>' for c in row) + '</tr>'
        html += '</tbody></table>'
        st.markdown(html, unsafe_allow_html=True)

    # ── 빈 행 기준으로 블록 분리
    blocks, cur = [], []
    for row in rows:
        c = clean(row)
        if not c:
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(c)
    if cur:
        blocks.append(cur)

    if not blocks:
        st.info("시트 데이터가 없습니다. 먼저 보고를 생성해주세요.")
        return

    # 첫 블록 = 제목/부제
    if blocks[0]:
        st.markdown(f"## {blocks[0][0][0]}")
        if len(blocks[0]) > 1:
            st.caption(blocks[0][1][0])

    st.divider()

    def _render_block_data(dr):
        if not dr:
            return
        if len(dr) == 1:
            if is_kv_row(dr[0]):
                render_kv(dr)
            else:
                st.text('   |   '.join(c for c in dr[0] if c.strip()))
        elif len(dr[0]) == 1:
            st.markdown(f"**{dr[0][0]}**")
            sub = dr[1:]
            if sub:
                if len(sub) == 1:
                    if is_kv_row(sub[0]):
                        render_kv(sub)
                    else:
                        st.text('   |   '.join(c for c in sub[0] if c.strip()))
                elif is_header(sub[0]):
                    render_table(sub)
                else:
                    render_kv(sub)
        elif is_header(dr[0]):
            render_table(dr)
        else:
            render_kv(dr)

    # 차트 섹션 이름 → 인덱스 열 / 차트 종류
    _CHART_SECTIONS = {"월별 집계", "월별 합계", "일별 현황"}
    _CHART_INDEX    = {"월별 집계": "월", "월별 합계": "월", "일별 현황": "날짜"}
    _CHART_TYPE     = {"월별 집계": "bar", "월별 합계": "bar", "일별 현황": "line"}
    _CHART_EXCLUDE  = {"월별 집계": {"월"}, "월별 합계": {"월"}, "일별 현황": {"날짜", "요일"}}

    def _rows_to_df(dr):
        """헤더+데이터 행 → DataFrame (합계 행 제외, 숫자 변환)"""
        if not dr or len(dr) < 2:
            return None
        header = dr[0]
        data   = [r for r in dr[1:] if not any(c == '합계' for c in r)]
        n = len(header)
        padded = [(r + [''] * n)[:n] for r in data]
        df = pd.DataFrame(padded, columns=header)
        for col in df.columns:
            s = df[col].str.replace(',', '', regex=False)
            converted = pd.to_numeric(s, errors='coerce')
            if converted.notna().any():
                df[col] = converted
        return df

    def _render_chart(section_title, dr):
        df = _rows_to_df(dr)
        if df is None or df.empty:
            st.caption("차트 데이터 없음")
            return
        idx_col  = _CHART_INDEX.get(section_title, "")
        excl     = _CHART_EXCLUDE.get(section_title, set())
        num_cols = [c for c in df.columns if c not in excl and pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols:
            st.caption("숫자 데이터 없음")
            return

        # 지표 선택 (월별 합계·일별 현황은 컬럼이 많아 multiselect 제공)
        if len(num_cols) > 2:
            sel = st.multiselect("지표 선택", num_cols, default=num_cols[:2],
                                 key=f"chart_sel_{section_title}")
        else:
            sel = num_cols

        if not sel:
            return

        if idx_col and idx_col in df.columns:
            # 일별 현황은 날짜순 정렬, 월별은 문자열 정렬로도 연월순 보장
            df = df.sort_values(idx_col)
            df_chart = df.set_index(idx_col)[sel]
        else:
            df_chart = df[sel]

        if _CHART_TYPE.get(section_title) == "line":
            st.line_chart(df_chart, use_container_width=True)
        else:
            st.bar_chart(df_chart, use_container_width=True)

    def _section_with_toggle(section_title, data_rows, show_title=True):
        if show_title:
            col_l, col_r = st.columns([6, 2])
            col_l.markdown(f"#### {section_title}")
            radio_col = col_r
        else:
            radio_col = st.container()
        mode = radio_col.radio("보기", ["📋 표", "📊 차트"], horizontal=True,
                               label_visibility="collapsed",
                               key=f"view_mode_{section_title}")
        if mode == "📊 차트":
            _render_chart(section_title, data_rows)
        else:
            _render_block_data(data_rows)

    for block in blocks[1:]:
        if not block:
            continue

        if len(block[0]) == 1:
            section_title = block[0][0]
            data_rows = block[1:]
        else:
            section_title = None
            data_rows = block

        if section_title and "일별" in section_title:
            with st.expander(f"📅 {section_title}", expanded=False):
                _section_with_toggle(section_title, data_rows, show_title=False)
        elif section_title and section_title in _CHART_SECTIONS:
            _section_with_toggle(section_title, data_rows)
        else:
            if section_title:
                st.markdown(f"#### {section_title}")
            _render_block_data(data_rows)

        st.write('')

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
try:
    _required_pw = st.secrets.get("access", {}).get("password", "")
except Exception:
    _required_pw = ""

if "can_generate" not in st.session_state:
    st.session_state.can_generate = not _required_pw  # 비밀번호 미설정 시 전체 허용

with st.sidebar:
    st.markdown("### 🎮 IBK 게임")
    st.caption(f"업데이트: {loaded_at}")
    st.divider()

    if _required_pw and not st.session_state.can_generate:
        with st.expander("🔐 보고 생성 잠금 해제"):
            _pw_input = st.text_input("비밀번호", type="password", key="pw_input")
            if st.button("확인"):
                if _pw_input == _required_pw:
                    st.session_state.can_generate = True
                    st.rerun()
                else:
                    st.error("비밀번호가 틀렸습니다.")

    can_generate = st.session_state.can_generate

    _menu = ["📊 종합", "🎁 경품", "🎟 할인쿠폰", "📐 시뮬레이션"]
    if can_generate:
        _menu.append("📤 보고 생성")
    _menu += ["📋 내부보고", "📄 외부보고", "📸 스냅샷", "❓ 사용 가이드"]

    page = st.radio(
        "메뉴",
        _menu,
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

if not data_ok and page not in ("📤 보고 생성", "📋 내부보고", "📄 외부보고", "📸 스냅샷"):
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

    c4, c5, c6, c7 = st.columns(4)
    c4.metric("확정수익 (만료 확정분만)",    won(tot_확정수익),
              help="정산금액 − (발행수−만료수)×면가 + 수수료")
    c5.metric("확정수익률 (면가기준)",       f"{tot_확정수익률:.1f}%")
    c6.metric("잠재수익 (만료+미교환 포함)", won(tot_잠재수익),
              help="정산금액 − 교환금액 + 수수료")
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
        monthly_df = pd.DataFrame(rows).rename(columns={"수익률_면가(%)": "수익률(%)"})
        st.dataframe(
            _fmt(monthly_df),
            use_container_width=True, hide_index=True,
        )

    st.divider()
    st.subheader("상품별 요약")
    if not cur_prize.empty:
        df_sp = cur_prize[["공급사명", "상품명", "면가", "발행수", "교환수", "만료수",
                            "정산금액", "확정수익", "잠재수익"]].copy()
        df_sp["교환율(%)"] = (df_sp["교환수"] / df_sp["발행수"] * 100).round(1)
        df_sp = df_sp[["공급사명", "상품명", "면가", "발행수", "교환수", "만료수",
                        "교환율(%)", "정산금액", "확정수익", "잠재수익"]]
        df_sp = df_sp.rename(columns={"공급사명": "브랜드명", "상품명": "경품명"})
        st.dataframe(_fmt(df_sp), use_container_width=True, hide_index=True)
    else:
        st.caption("경품 데이터 없음")

    st.subheader("쿠폰별 요약")
    if not cur_coupon.empty:
        df_sc = cur_coupon[["쿠폰명", "면가", "발행수", "사용수", "만료수",
                             "정산금액", "확정수익", "잠재수익"]].copy()
        df_sc["사용율(%)"] = (df_sc["사용수"] / df_sc["발행수"] * 100).round(1)
        df_sc = df_sc[["쿠폰명", "면가", "발행수", "사용수", "만료수",
                        "사용율(%)", "정산금액", "확정수익", "잠재수익"]]
        st.dataframe(_fmt(df_sc), use_container_width=True, hide_index=True)
    else:
        st.caption("쿠폰 데이터 없음")


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
    _metric_profit(c6, "확정수익 (만료분만)",     won(p_확정수익), p_확정수익률)
    _metric_profit(c7, "잠재수익 (만료+미교환)", won(p_잠재수익), p_잠재수익률)

    st.divider()
    st.subheader("상품별 내역")

    rates = df_p["교환율(%)"]
    mean_r = rates.mean()
    std_r  = rates.std() if len(rates) > 1 else 0

    def _prize_note(row):
        parts = []
        a = _anomaly_comment(row["교환율(%)"], mean_r, std_r)
        if a:
            parts.append(a)
        return "  /  ".join(parts)

    df_p["비고"] = df_p.apply(_prize_note, axis=1)
    df_p["확정수익_표시"] = df_p["확정수익"].apply(lambda v: f"{int(v):,}원")
    df_p["잠재수익_표시"] = df_p["잠재수익"].apply(lambda v: f"{int(v):,}원")
    _확정_p_style = [
        "color:#16a34a;font-weight:bold;font-size:15px;white-space:nowrap" if v >= 0
        else "color:#dc2626;font-weight:bold;font-size:15px;white-space:nowrap"
        for v in df_p["확정수익"].values
    ]
    _잠재_p_style = [
        "color:#16a34a;font-weight:bold;font-size:15px;white-space:nowrap" if v >= 0
        else "color:#dc2626;font-weight:bold;font-size:15px;white-space:nowrap"
        for v in df_p["잠재수익"].values
    ]

    cols = ["게임명", "공급사명", "상품명", "면가", "게임P", "발행수", "교환수", "만료수",
            "교환율(%)", "미교환율(%)", "정산금액", "교환금액", "수수료금액",
            "확정수익_표시", "확정수익률(%)", "잠재수익_표시", "잠재수익률(%)", "비고"]

    st.caption("확정수익 = 정산금액 − (발행수−만료수)×면가 + 수수료  |  잠재수익 = 정산금액 − 교환금액 + 수수료")
    _disp_p = df_p[cols].rename(columns={
        "공급사명": "브랜드명", "상품명": "경품명",
        "확정수익_표시": "확정수익", "잠재수익_표시": "잠재수익",
    })
    _sty_p = _fmt(_disp_p, skip_fmt=["확정수익", "잠재수익"])
    _sty_p = _sty_p.apply(lambda _: _확정_p_style, subset=["확정수익"], axis=0)
    _sty_p = _sty_p.apply(lambda _: _잠재_p_style, subset=["잠재수익"], axis=0)
    st.dataframe(_sty_p, use_container_width=True, hide_index=True)


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
    _metric_profit(c6, "확정수익 (만료분만)",     won(c_확정수익), c_확정수익률)
    _metric_profit(c7, "잠재수익 (만료+미교환)", won(c_잠재수익), c_잠재수익률)

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
        return "  /  ".join(parts)

    df_c["비고"] = df_c.apply(_coupon_note, axis=1)
    df_c["확정수익_표시"] = df_c["확정수익"].apply(lambda v: f"{int(v):,}원")
    df_c["잠재수익_표시"] = df_c["잠재수익"].apply(lambda v: f"{int(v):,}원")
    _확정_c_style = [
        "color:#16a34a;font-weight:bold;font-size:15px;white-space:nowrap" if v >= 0
        else "color:#dc2626;font-weight:bold;font-size:15px;white-space:nowrap"
        for v in df_c["확정수익"].values
    ]
    _잠재_c_style = [
        "color:#16a34a;font-weight:bold;font-size:15px;white-space:nowrap" if v >= 0
        else "color:#dc2626;font-weight:bold;font-size:15px;white-space:nowrap"
        for v in df_c["잠재수익"].values
    ]

    cols = ["게임명", "쿠폰", "게임P", "발행수", "사용수", "만료수",
            "사용율(%)", "미사용율(%)", "정산금액", "교환금액",
            "확정수익_표시", "확정수익률(%)", "잠재수익_표시", "잠재수익률(%)", "비고"]

    st.caption("확정수익 = 정산금액 − (발행수−만료수)×면가  |  잠재수익 = 정산금액 − 교환금액")
    _disp_c = df_c[cols].rename(columns={"확정수익_표시": "확정수익", "잠재수익_표시": "잠재수익"})
    _sty_c = _fmt(_disp_c, skip_fmt=["확정수익", "잠재수익"])
    _sty_c = _sty_c.apply(lambda _: _확정_c_style, subset=["확정수익"], axis=0)
    _sty_c = _sty_c.apply(lambda _: _잠재_c_style, subset=["잠재수익"], axis=0)
    st.dataframe(_sty_c, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# 📐 시뮬레이션
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📐 시뮬레이션":
    st.title("📐 미교환율 시뮬레이션")
    st.caption(f"기준: {sel_month}  ·  아래에서 수치 수정 후 [결과 계산] 버튼 클릭")

    sim_prize_df  = cur_prize.copy()  if not cur_prize.empty  else pd.DataFrame()
    sim_coupon_df = cur_coupon.copy() if not cur_coupon.empty else pd.DataFrame()

    if "sim_prize_adj" not in st.session_state:
        st.session_state.sim_prize_adj = {}
    if "sim_coupon_adj" not in st.session_state:
        st.session_state.sim_coupon_adj = {}
    if "sim_result_ready" not in st.session_state:
        st.session_state.sim_result_ready = False

    def _fmt_int(v):
        try: return f"{int(v):,}"
        except: return v

    # ── 예상 결과 요약 (상단) ───────────────────────────────────────────────────
    if st.session_state.sim_result_ready:
        prize_calc = pd.DataFrame()
        coupon_calc = pd.DataFrame()

        if not sim_prize_df.empty:
            calc_p = sim_prize_df[["게임명", "공급사명", "상품명", "게임P", "면가", "발행수", "교환수", "만료수", "수수료율"]].copy()
            calc_p["예상 미교환율(%)"] = calc_p.apply(
                lambda r: st.session_state.sim_prize_adj.get(
                    (r["게임명"], r["상품명"]),
                    (r["발행수"] - r["교환수"]) / r["발행수"] * 100
                ), axis=1
            )
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
            c4.metric("예상 확정수익",  won(s수익), delta=f"만료 {won(s만료)} 포함")
            c5.metric("예상 확정수익률", f"{s수익률:.1f}%")

            st.divider()
            if not prize_calc.empty:
                st.markdown("**경품 상품별 예상 결과**")
                pc = prize_calc[["게임명", "공급사명", "상품명", "면가", "발행수", "예상 교환수", "예상 만료수",
                                  "예상 정산", "예상 교환금액", "예상 수수료", "예상 수익"]].copy()
                pc["상품"] = pc.apply(lambda r: _상품표시(r.get("공급사명", ""), r["상품명"], r["면가"]), axis=1)
                pc["예상 확정수익률(%)"] = (pc["예상 수익"] / (pc["발행수"] * pc["면가"]) * 100).where(pc["예상 정산"] > 0).round(1)
                pc = pc[["게임명", "상품", "발행수", "예상 교환수", "예상 만료수",
                          "예상 정산", "예상 교환금액", "예상 수수료", "예상 수익", "예상 확정수익률(%)"]]
                st.dataframe(_fmt(pc), use_container_width=True, hide_index=True)
            if not coupon_calc.empty:
                st.markdown("**쿠폰별 예상 결과**")
                cc = coupon_calc[["게임명", "쿠폰명", "면가", "발행수", "예상 사용수", "예상 만료수",
                                   "예상 정산", "예상 교환금액", "예상 수익"]].copy()
                cc["쿠폰"] = cc.apply(lambda r: f"{r['쿠폰명']}  ({int(r['면가']):,}원)", axis=1)
                cc["예상 확정수익률(%)"] = (cc["예상 수익"] / (cc["발행수"] * cc["면가"]) * 100).where(cc["예상 정산"] > 0).round(1)
                cc = cc[["게임명", "쿠폰", "발행수", "예상 사용수", "예상 만료수",
                          "예상 정산", "예상 교환금액", "예상 수익", "예상 확정수익률(%)"]]
                st.dataframe(_fmt(cc), use_container_width=True, hide_index=True)
    else:
        st.info("아래에서 수치를 수정한 후 [📊 결과 계산] 버튼을 클릭하세요.")

    # ── 교환율 조정 입력 (하단) ─────────────────────────────────────────────────
    st.divider()

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
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# 📤 보고 생성
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📤 보고 생성":
    if not can_generate:
        st.error("보고 생성 권한이 없습니다.")
        st.stop()
    import tempfile, shutil, sys, io
    from contextlib import redirect_stdout
    import report_generator as rg

    st.title("📤 보고 생성")
    st.caption("파일을 아래에 드래그하면 종류를 자동으로 인식합니다")
    st.divider()

    run_mode = st.radio(
        "실행 모드",
        ["전체 덮어쓰기", "누적 추가"],
        horizontal=True,
        captions=[
            "기존 데이터 전체 삭제 후 업로드 파일로 재처리 (미교환율 갱신 시 사용)",
            "기존 데이터 유지, 새 날짜 데이터만 추가 (일별 업데이트 시 사용)",
        ],
    )
    st.divider()

    uploaded = st.file_uploader(
        "파일 드래그 (로우데이터 · 할인쿠폰 · 매체사경품 동시 가능)",
        accept_multiple_files=True,
        type=["xlsx", "xls", "csv"],
    )

    raw_paths, coupon_paths, prize_paths = [], [], []
    unknown_files = []
    _tmpdir = None

    if uploaded:
        _tmpdir = tempfile.mkdtemp()
        for f in uploaded:
            p = os.path.join(_tmpdir, f.name)
            with open(p, "wb") as fp:
                fp.write(f.read())
            kind = rg.detect_file_type(p)
            if kind == "raw":
                raw_paths.append(p)
            elif kind == "coupon":
                coupon_paths.append(p)
            elif kind == "prize":
                prize_paths.append(p)
            else:
                unknown_files.append(f.name)

        KIND_LABEL = {"raw": "📋 로우데이터", "coupon": "🎟 할인쿠폰", "prize": "🎁 매체사경품"}
        rows = []
        for f in uploaded:
            p = os.path.join(_tmpdir, f.name)
            k = rg.detect_file_type(p)
            rows.append({"파일명": f.name, "인식 결과": KIND_LABEL.get(k, "❓ 인식 불가")})
        st.table(rows)

        if unknown_files:
            st.warning(f"자동 인식 불가 파일: {', '.join(unknown_files)}\n\n해당 파일은 처리에서 제외됩니다.")

    all_ready = bool(raw_paths and coupon_paths and prize_paths)
    if uploaded and not all_ready:
        missing = []
        if not raw_paths:    missing.append("로우데이터")
        if not coupon_paths: missing.append("할인쿠폰")
        if not prize_paths:  missing.append("매체사경품")
        st.info(f"아직 인식되지 않은 파일 종류: {', '.join(missing)}")

    if st.button("📊 보고 생성", type="primary", disabled=not all_ready, use_container_width=True):
        log_box = st.empty()
        log_lines = []

        def log(msg):
            log_lines.append(msg)
            log_box.code("\n".join(log_lines))

        try:
            log(f"  로우데이터 {len(raw_paths)}개 / 할인쿠폰 {len(coupon_paths)}개 / 매체사경품 {len(prize_paths)}개")

            log("📊 데이터 로드 및 필터링 중...")
            buf = io.StringIO()
            with redirect_stdout(buf):
                raw_df,    rcols = rg.load_raw(raw_paths)
                coupon_df_up, ccols = rg.load_coupon(coupon_paths)
                prize_df_up,  pcols = rg.load_prize_csv(prize_paths)
            for line in buf.getvalue().strip().splitlines():
                log(f"  {line.strip()}")

            log("🔑 구글시트 연결 중...")
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build as gbuild
            WRITE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
            try:
                info = dict(st.secrets["gcp_service_account"])
                creds = Credentials.from_service_account_info(info, scopes=WRITE_SCOPES)
            except Exception:
                creds = Credentials.from_service_account_file(
                    r"C:\Users\jihye\.claude\google-sheets-key.json", scopes=WRITE_SCOPES
                )
            svc = gbuild("sheets", "v4", credentials=creds)

            mode_label = "전체 덮어쓰기" if run_mode == "전체 덮어쓰기" else "누적 추가"
            log(f"✍️ 구글시트 업데이트 중... [{mode_label}] (1~2분 소요)")
            buf2 = io.StringIO()
            with redirect_stdout(buf2):
                if run_mode == "전체 덮어쓰기":
                    rg.run_full(raw_df, rcols, coupon_df_up, ccols, prize_df_up, pcols, svc)
                else:
                    rg.run_append(raw_df, rcols, coupon_df_up, ccols, prize_df_up, pcols, svc)
            for line in buf2.getvalue().strip().splitlines():
                log(f"  {line.strip()}")

            shutil.rmtree(_tmpdir, ignore_errors=True)
            log("✅ 완료!")
            st.success("보고 생성 완료! 다른 탭에서 최신 데이터를 확인하세요.")
            st.cache_data.clear()

        except Exception as e:
            shutil.rmtree(_tmpdir, ignore_errors=True)
            log(f"❌ 오류: {e}")
            st.error(f"오류 발생: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ❓ 사용 가이드
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 내부보고":
    st.title("📋 내부보고")
    if st.button("🔄 새로고침", key="refresh_internal"):
        st.cache_data.clear()
        st.rerun()
    rows = _get_report_rows("내부보고")
    _render_report(rows)

elif page == "📄 외부보고":
    st.title("📄 외부보고")
    if st.button("🔄 새로고침", key="refresh_external"):
        st.cache_data.clear()
        st.rerun()
    rows = _get_report_rows("외부보고")
    _render_report(rows)

elif page == "📸 스냅샷":
    st.title("📸 스냅샷")

    @st.cache_data(ttl=60)
    def _get_snapshot_list():
        try:
            return list_snapshot_sheets()
        except Exception:
            return []

    snapshots = _get_snapshot_list()
    if not snapshots:
        st.info("저장된 스냅샷이 없습니다. 보고 생성 시 자동으로 저장됩니다.")
    else:
        def _fmt_snap(name):
            d = name.replace("스냅샷_", "")
            try:
                return f"{d[:4]}.{d[4:6]}.{d[6:]}"
            except Exception:
                return d

        labels = {_fmt_snap(s): s for s in snapshots}
        selected_label = st.selectbox("날짜 선택", list(labels.keys()))
        selected_sheet = labels[selected_label]

        col_r1, col_r2 = st.columns([2, 6])
        if col_r1.button("🔄 새로고침", key="refresh_snap"):
            st.cache_data.clear()
            st.rerun()

        with col_r2.expander("⚠️ 이 스냅샷을 내부보고로 복원"):
            st.warning(f"**{selected_label}** 스냅샷을 내부보고 시트에 덮어씁니다. 현재 내부보고 내용은 사라집니다.")
            if st.button("복원 실행", type="primary", key="restore_snap"):
                try:
                    from google.oauth2.service_account import Credentials
                    from googleapiclient.discovery import build as gbuild
                    WRITE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
                    try:
                        info = dict(st.secrets["gcp_service_account"])
                        creds = Credentials.from_service_account_info(info, scopes=WRITE_SCOPES)
                    except Exception:
                        creds = Credentials.from_service_account_file(
                            r"C:\Users\jihye\.claude\google-sheets-key.json", scopes=WRITE_SCOPES
                        )
                    svc = gbuild("sheets", "v4", credentials=creds)
                    snap_rows = _get_report_rows(selected_sheet)
                    import report_generator as rg_restore
                    rg_restore.write_sheet(svc, '내부보고', snap_rows)
                    rg_restore.format_report_sheet(svc, '내부보고')
                    st.cache_data.clear()
                    st.success("복원 완료! 내부보고 탭에서 확인하세요.")
                except Exception as e:
                    st.error(f"복원 실패: {e}")

        rows = _get_report_rows(selected_sheet)
        _render_report(rows)

elif page == "❓ 사용 가이드":
    st.title("❓ 사용 가이드")
    st.divider()

    st.markdown("## 📋 시트 구성")
    st.markdown("""
| 시트 | 설명 |
|------|------|
| **경품** | 월별 경품 발행·교환·만료·수익 현황 (보고 생성 시 자동 작성) |
| **할인쿠폰** | 월별 할인쿠폰 발행·사용·만료·수익 현황 (보고 생성 시 자동 작성) |
| **종합** | 월별 전체 합산 현황 (보고 생성 시 자동 작성) |
| **예상수익률** | 미교환율별 수익 시뮬레이션 (보고 생성 시 자동 작성) |
| **경품코드 마스터** | 경품별 교환처·면가·수수료율 직접 입력 |
| **외부보고** | 손란대리님께 공유하는 요약 보고 |
| **내부보고** | 팀 내부 공유용 상세 보고 |
| **집계_*** | 날짜별·월별·유저별 원시 집계 데이터 (자동 생성) |
""")

    st.divider()
    st.markdown("## 🚀 보고 생성 순서")
    st.markdown("""
**① 데이터 파일 준비 (3개)**
- 로우데이터 : CP > 게이미피케이션 > 결과 관리 > 엑셀 다운로드
- 할인쿠폰 : CRAS > 이벤트관리 > 기프트샵 할인쿠폰 발행 > 매체사(ibk기업은행) > 엑셀 다운로드
- 매체사 경품 : CRAS > 정산관리 > 매체사(IBK기프트샵) > 엑셀 다운로드

**② 사이드바 [📤 보고 생성] 탭으로 이동**

**③ 실행 모드 선택**
- **전체 덮어쓰기** : 기존 데이터 전체 삭제 후 업로드 파일로 완전 재처리
  → 미교환율이 달라졌을 때 / 전체 재집계 필요할 때 사용
- **누적 추가** : 기존 데이터 유지, 새 날짜 데이터만 추가
  → 전일·주간 업데이트처럼 일부 기간만 추가할 때 사용

**④ 파일 3개 업로드 후 [📊 보고 생성] 클릭**

**⑤ 완료 후 각 탭에서 결과 확인**
""")

    st.divider()
    st.markdown("## ⚠️ 주의사항")
    st.markdown("""
- **누적 추가** 모드에서 이미 처리된 날짜의 파일을 올리면 해당 날짜는 자동으로 건너뜀
- **전체 덮어쓰기** 후에는 이전 누적 데이터가 사라짐 — 항상 전체 기간 파일을 올릴 것
- 서비스 오픈 이전 데이터(2026년 4월 23일 18:00 이전)는 자동 제외됨
- 포인트 차감 실패·취소 행은 자동 제외됨
- 경품코드 마스터에 교환처가 없는 경품은 비고란에 공백으로 표시됨
""")

