import json
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = '1G2A_FyERvQOVQBUsu9AHx7FPrE-UAIX4Ohl9UNtalzY'
KEY_FILE = r'C:\Users\jihye\.claude\google-sheets-key.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# 시트 컬럼 인덱스 (0-based, 할인율 제거 후 20컬럼 기준)
# A=게임명 B=공급사명 C=상품명 D=게임P E=면가 F=수수료율
# G=발행수 H=교환수 I=만료수 J~M=금액집계 N=교환율 O=미교환율
# P=상품대금 Q=수수료금액 R=정산금액 S=최종수익 T=수익률


def _get_service():
    try:
        import streamlit as st
        info = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        creds = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)


def _read_sheet_values(service, sheet_name):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_name,
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()
    rows = result.get('values', [])
    if not rows:
        return []
    max_cols = max(len(r) for r in rows)
    return [r + [''] * (max_cols - len(r)) for r in rows]


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _is_data_row(row):
    """게임명(A)이 있고 게임P(D)가 양의 정수인 행"""
    if len(row) < 5:
        return False
    game = str(row[0]).strip()
    if not game or game.startswith('[') or game in ('게임명', '전체 합계') or '합계' in game:
        return False
    try:
        return float(row[3]) > 0
    except (TypeError, ValueError):
        return False


def _prize_record(row):
    """경품 데이터 행 → dict (시트 수식 결과값 직접 사용)"""
    return {
        '게임명':    str(row[0]).strip(),
        '공급사명':  str(row[1]).strip(),
        '상품명':    str(row[2]).strip(),
        '게임P':     _safe_int(row[3]),
        '면가':      _safe_int(row[4]),
        '수수료율':  round(_safe_float(row[5]) * 100, 2),   # 소수 → %
        '발행수':    _safe_int(row[6]),
        '교환수':    _safe_int(row[7]),
        '만료수':    _safe_int(row[8]),
        # 시트 수식 결과 직접 읽기 (P/Q/R/S/T)
        '상품대금':   _safe_int(row[15]),
        '수수료금액': _safe_int(row[16]),
        '정산금액':   _safe_int(row[17]),
        '최종수익':        _safe_int(row[18]),
        '수익률_정산(%)':  round(_safe_float(row[19]) * 100, 1),
        '수익률_면가(%)':  round(_safe_float(row[20]) * 100, 1) if len(row) > 20 else 0,
    }


def _coupon_record(row):
    """쿠폰 데이터 행 → dict (시트 수식 결과값 직접 사용)"""
    return {
        '게임명':   str(row[0]).strip(),
        '쿠폰명':   str(row[2]).strip(),
        '게임P':    _safe_int(row[3]),
        '면가':     _safe_int(row[4]),
        '발행수':   _safe_int(row[6]),
        '사용수':   _safe_int(row[7]),
        '만료수':   _safe_int(row[8]),
        '상품대금':       _safe_int(row[15]),
        '수수료금액':     0,
        '정산금액':       _safe_int(row[17]),
        '최종수익':       _safe_int(row[18]),
        '수익률_정산(%)': round(_safe_float(row[19]) * 100, 1),
        '수익률_면가(%)': round(_safe_float(row[20]) * 100, 1) if len(row) > 20 else 0,
    }


def load_prize_df(service=None):
    """경품 탭 → 전체기간합계 상품별 DataFrame"""
    if service is None:
        service = _get_service()
    rows = _read_sheet_values(service, '경품')

    grand, records = False, []
    for row in rows:
        a = str(row[0]).strip() if row else ''
        if '[전체 기간 합계]' in a:
            grand = True; continue
        if grand and '전체 합계' in a:
            break
        if grand and _is_data_row(row):
            records.append(_prize_record(row))

    cols = ['게임명','공급사명','상품명','게임P','면가','수수료율','발행수','교환수','만료수',
            '상품대금','수수료금액','정산금액','최종수익','수익률_정산(%)','수익률_면가(%)']
    return pd.DataFrame(records) if records else pd.DataFrame(columns=cols)


def load_coupon_df(service=None):
    """할인쿠폰 탭 → 전체기간합계 쿠폰별 DataFrame"""
    if service is None:
        service = _get_service()
    rows = _read_sheet_values(service, '할인쿠폰')

    grand, records = False, []
    for row in rows:
        a = str(row[0]).strip() if row else ''
        if '[전체 기간 합계]' in a:
            grand = True; continue
        if grand and '전체 합계' in a:
            break
        if grand and _is_data_row(row):
            records.append(_coupon_record(row))

    cols = ['게임명','쿠폰명','게임P','면가','발행수','사용수','만료수',
            '상품대금','수수료금액','정산금액','최종수익','수익률_정산(%)','수익률_면가(%)']
    return pd.DataFrame(records) if records else pd.DataFrame(columns=cols)


def load_monthly_prize(service=None):
    """경품 탭 → {월: DataFrame}"""
    if service is None:
        service = _get_service()
    rows = _read_sheet_values(service, '경품')

    monthly, cur = {}, None
    for row in rows:
        a = str(row[0]).strip() if row else ''
        if '[전체 기간 합계]' in a:
            break
        if a.startswith('[') and a.endswith(']'):
            cur = a.strip('[]'); monthly[cur] = []; continue
        if cur and _is_data_row(row):
            monthly[cur].append(_prize_record(row))

    return {mk: pd.DataFrame(v) for mk, v in monthly.items() if v}


def load_monthly_coupon(service=None):
    """할인쿠폰 탭 → {월: DataFrame}"""
    if service is None:
        service = _get_service()
    rows = _read_sheet_values(service, '할인쿠폰')

    monthly, cur = {}, None
    for row in rows:
        a = str(row[0]).strip() if row else ''
        if '[전체 기간 합계]' in a:
            break
        if a.startswith('[') and a.endswith(']'):
            cur = a.strip('[]'); monthly[cur] = []; continue
        if cur and _is_data_row(row):
            monthly[cur].append(_coupon_record(row))

    return {mk: pd.DataFrame(v) for mk, v in monthly.items() if v}


def load_all(service=None):
    from datetime import datetime
    if service is None:
        service = _get_service()
    prize_df  = load_prize_df(service)
    coupon_df = load_coupon_df(service)
    monthly_p = load_monthly_prize(service)
    monthly_c = load_monthly_coupon(service)
    months    = sorted(set(list(monthly_p.keys()) + list(monthly_c.keys())))
    loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return prize_df, coupon_df, monthly_p, monthly_c, months, loaded_at
