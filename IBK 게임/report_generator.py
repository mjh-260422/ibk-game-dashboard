import sys
import re
import os
import time
import unicodedata
from datetime import datetime, date

import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SPREADSHEET_ID = '1G2A_FyERvQOVQBUsu9AHx7FPrE-UAIX4Ohl9UNtalzY'
KEY_FILE = r'C:\Users\jihye\.claude\google-sheets-key.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
LAUNCH_DT = datetime(2026, 4, 23, 18, 0, 0)



def get_service():
    creds = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)


def _batch_update(service, requests, max_retries=5):
    """429 Rate Limit / 네트워크 오류 발생 시 exponential backoff 재시도"""
    delay = 5
    for attempt in range(max_retries):
        try:
            return service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": requests}
            ).execute()
        except HttpError as e:
            if e.resp.status == 429 and attempt < max_retries - 1:
                print(f"  [429] 쿼터 초과, {delay}초 대기 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            if attempt < max_retries - 1:
                print(f"  [연결 오류] {e}, {delay}초 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
            else:
                raise




def read_sheet(service, sheet_name):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_name
    ).execute()
    rows = result.get('values', [])
    if not rows:
        return pd.DataFrame()
    max_cols = max(len(r) for r in rows)
    rows_padded = [r + [''] * (max_cols - len(r)) for r in rows]
    return pd.DataFrame(rows_padded[1:], columns=rows_padded[0])


def ensure_sheet(service, sheet_name):
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    existing = {s['properties']['title']: s['properties']['sheetId'] for s in meta['sheets']}
    if sheet_name not in existing:
        res = _batch_update(service, [{'addSheet': {'properties': {'title': sheet_name}}}])
        return res['replies'][0]['addSheet']['properties']['sheetId']
    return existing[sheet_name]


def reset_sheet(service, sheet_name):
    """시트 삭제 후 재생성 — 기존 서식/값 완전 초기화"""
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    for s in meta['sheets']:
        if s['properties']['title'] == sheet_name:
            _batch_update(service, [{'deleteSheet': {'sheetId': s['properties']['sheetId']}}])
            break
    _batch_update(service, [{'addSheet': {'properties': {'title': sheet_name}}}])


def _values_call(fn, max_retries=5):
    """values().clear() / values().update() 등 단일 write 호출용 재시도 래퍼"""
    delay = 5
    for attempt in range(max_retries):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status == 429 and attempt < max_retries - 1:
                print(f"  [429] 쿼터 초과, {delay}초 대기 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            if attempt < max_retries - 1:
                print(f"  [연결 오류] {e}, {delay}초 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
            else:
                raise


def write_sheet(service, sheet_name, data):
    sheet_id = ensure_sheet(service, sheet_name)
    # 이전 format_sheets가 남긴 셀 병합이 있으면 values().update()가 일부 셀을 무시함 → 먼저 병합 해제
    _batch_update(service, [{'unmergeCells': {'range': {
        'sheetId': sheet_id,
        'startRowIndex': 0, 'endRowIndex': 2000,
        'startColumnIndex': 0, 'endColumnIndex': 30
    }}}])
    _values_call(lambda: service.spreadsheets().values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_name
    ).execute())
    if not data:
        return
    _values_call(lambda: service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{sheet_name}!A1',
        valueInputOption='RAW',
        body={'values': data}
    ).execute())


def format_report_sheet(service, sheet_name):
    """내부보고·외부보고 시트에 동적 서식 적용 (행 타입 자동 감지)"""
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_id = next((s['properties']['sheetId'] for s in meta['sheets']
                     if s['properties']['title'] == sheet_name), None)
    if sheet_id is None:
        return

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=sheet_name,
        valueRenderOption='FORMATTED_VALUE'
    ).execute()
    all_rows = result.get('values', [])
    if not all_rows:
        return

    def rgb(r, g, b): return {"red": r/255, "green": g/255, "blue": b/255}

    # 연한 배경 + 검정 글자 팔레트
    C_TITLE = rgb(197, 217, 241)   # 제목: 소프트 파랑
    C_SECT  = rgb(197, 217, 241)   # 섹션 헤더: 동일
    C_CHDR  = rgb(173, 207, 234)   # 컬럼 헤더: 약간 짙은 파랑
    C_SUMM  = rgb(225, 238, 250)   # 합계 행: 아주 연한 파랑
    C_ALT   = rgb(245, 250, 255)   # 데이터 홀수 행
    C_WHITE = rgb(255, 255, 255)
    C_TD    = rgb(30, 30, 30)      # 모든 텍스트: 검정
    C_SUBT  = rgb(235, 241, 248)   # 부제목

    def rfmt(bg, bold, h_align, font_size=10, wrap="WRAP"):
        return {"backgroundColor": bg,
                "textFormat": {"bold": bold, "fontSize": font_size,
                               "foregroundColor": C_TD, "fontFamily": "Arial"},
                "horizontalAlignment": h_align, "verticalAlignment": "MIDDLE",
                "wrapStrategy": wrap,
                "padding": {"top": 3, "bottom": 3, "left": 6, "right": 6}}

    def rep(r1, c1, c2, fmt):
        return {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": r1, "endRowIndex": r1+1,
                      "startColumnIndex": c1, "endColumnIndex": c2},
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy,padding)"
        }}

    def rowh(row, h):
        return {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS",
                      "startIndex": row, "endIndex": row+1},
            "properties": {"pixelSize": h}, "fields": "pixelSize"}}

    def bdr(r1, r2, c1, c2):
        b = {"style": "SOLID", "color": rgb(196, 215, 234)}
        return {"updateBorders": {
            "range": {"sheetId": sheet_id, "startRowIndex": r1, "endRowIndex": r2,
                      "startColumnIndex": c1, "endColumnIndex": c2},
            "top": b, "bottom": b, "left": b, "right": b,
            "innerHorizontal": b, "innerVertical": b}}

    def clean(row):
        r = row[1:] if row and row[0] == '' else list(row)
        while r and r[-1] == '': r = r[:-1]
        return r

    def is_num(s):
        return bool(re.match(r'^-?[\d,]+(\.\d+)?%?$', str(s).strip()))

    n_cols = max((len(r) for r in all_rows), default=1)
    n_cols = max(n_cols + 1, 10)

    reqs = []
    reqs.append(rep(0, 0, n_cols, rfmt(C_WHITE, False, "LEFT")))

    bdr_groups = []
    cur_block_start = None
    cur_block_max_col = 1

    for i, raw in enumerate(all_rows):
        c = clean(raw)
        if not c:
            if cur_block_start is not None:
                bdr_groups.append((cur_block_start, i, cur_block_max_col))
                cur_block_start = None
            reqs.append(rowh(i, 6))
            continue

        row_max_col = len(raw)
        if cur_block_start is None and i > 1:
            cur_block_start = i
            cur_block_max_col = row_max_col
        elif cur_block_start is not None:
            cur_block_max_col = max(cur_block_max_col, row_max_col)

        if i == 0:
            # 제목: OVERFLOW_CELL (한 줄 표시, 셀 넘침 허용)
            reqs += [rep(i, 0, n_cols, rfmt(C_TITLE, True, "LEFT", 12, "OVERFLOW_CELL")),
                     rowh(i, 38)]
        elif i == 1:
            reqs += [rep(i, 0, n_cols, rfmt(C_SUBT, False, "LEFT", 9, "OVERFLOW_CELL")),
                     rowh(i, 20)]
        elif len(c) == 1:
            reqs += [rep(i, 0, n_cols, rfmt(C_SECT, True, "LEFT")),
                     rowh(i, 26)]
        elif all(not is_num(x) for x in c if x.strip()):
            reqs += [rep(i, 0, n_cols, rfmt(C_CHDR, True, "CENTER", 10, "OVERFLOW_CELL")),
                     rowh(i, 26)]
        elif any(x in ('합계', '소계') for x in c):
            reqs += [rep(i, 0, n_cols, rfmt(C_SUMM, True, "LEFT", 10, "OVERFLOW_CELL")),
                     rep(i, 3, n_cols, rfmt(C_SUMM, True, "RIGHT", 10, "OVERFLOW_CELL")),
                     rowh(i, 24)]
        else:
            alt = i % 2 == 0
            bg = C_ALT if alt else C_WHITE
            reqs += [rep(i, 0, n_cols, rfmt(bg, False, "LEFT", 10, "OVERFLOW_CELL")),
                     rep(i, 3, n_cols, rfmt(bg, False, "RIGHT", 10, "OVERFLOW_CELL")),
                     rowh(i, 24)]

    if cur_block_start is not None:
        bdr_groups.append((cur_block_start, len(all_rows), cur_block_max_col))

    for r1, r2, mc in bdr_groups:
        reqs.append(bdr(r1, r2, 0, mc))

    def _cw(s):
        """글자 너비 계산: Korean/CJK=12px, ASCII=7px"""
        return sum(12 if unicodedata.east_asian_width(ch) in ('W', 'F') else 7
                   for ch in str(s))

    # 열 너비: 제목/부제(i<2)는 OVERFLOW_CELL이므로 제외, 나머지 내용 기준 계산
    col_max_px = {}
    for i, raw in enumerate(all_rows):
        if i < 2:
            continue
        c_row = clean(raw)
        is_bold_row = len(c_row) == 1 or (c_row and all(not is_num(x) for x in c_row if x.strip()))
        for ci, cell in enumerate(raw):
            if str(cell).strip():
                px = _cw(str(cell))
                if is_bold_row:
                    px = int(px * 1.15)
                col_max_px[ci] = max(col_max_px.get(ci, 0), px)

    PAD = 18
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                  "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 16}, "fields": "pixelSize"}})

    for ci in range(1, n_cols):
        raw_px = col_max_px.get(ci, 40)
        w = max(55, min(300, raw_px + PAD))
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": ci, "endIndex": ci+1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})

    for batch_start in range(0, len(reqs), 200):
        _batch_update(service, reqs[batch_start:batch_start+200])
        if batch_start + 200 < len(reqs):
            time.sleep(1)


def read_csv(path):
    for enc in ('cp949', 'euc-kr', 'utf-8-sig'):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str)
        except Exception:
            continue
    raise ValueError(f'CSV 인코딩 실패: {path}')


def find_col(df, keyword):
    for c in df.columns:
        if keyword in str(c):
            return c
    return None


def clean_trid(val):
    s = str(val).strip()
    s = re.sub(r'^=?"?', '', s)
    s = s.rstrip('"')
    return s.strip()


def extract_amount(name):
    m = re.search(r'[\d,]+(?=원)', str(name))
    if m:
        return int(m.group().replace(',', ''))
    return None


def _from_excel_serial(v):
    from datetime import timedelta
    try:
        f = float(v)
        if 30000 < f < 70000:  # 1982~2091 범위
            return datetime(1899, 12, 30) + timedelta(days=f)
    except Exception:
        pass
    return None


def parse_datetime(val):
    if pd.isna(val) or val == '':
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        dt = _from_excel_serial(val)
        if dt:
            return dt
    s = str(val).strip()
    dt = _from_excel_serial(s)
    if dt:
        return dt
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                '%Y/%m/%d %H:%M:%S', '%Y/%m/%d', '%Y%m%d'):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def parse_date_val(val):
    if pd.isna(val) or val == '':
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if hasattr(val, 'date') else val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        dt = _from_excel_serial(val)
        if dt:
            return dt.date()
    s = str(val).strip()
    dt = _from_excel_serial(s)
    if dt:
        return dt.date()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y%m%d'):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except Exception:
            continue
    return None


def day_key(val):
    d = parse_date_val(val)
    if d:
        return d.strftime('%Y-%m-%d')
    return None


def fmt_month(val):
    d = parse_date_val(val)
    if d:
        return f'{d.year}년 {d.month:02d}월'
    return None


def weekday_kr(val):
    d = parse_date_val(val)
    if d:
        return ['월', '화', '수', '목', '금', '토', '일'][d.weekday()]
    return ''


def load_raw(paths):
    if isinstance(paths, str): paths = [paths]
    dfs = []
    for path in paths:
        print(f'  로우데이터 읽기: {os.path.basename(path)}')
        dfs.append(pd.read_excel(path, dtype=str))
    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    print(f'  합계 행수: {len(df)}')
    df.columns = [str(c).strip() for c in df.columns]

    col_userId = find_col(df, '사용자 ID')
    col_gameName = find_col(df, '게임명')
    col_gameDate = find_col(df, '게임 실행일')
    col_points = find_col(df, '차감 포인트')
    col_ptSt = find_col(df, '포인트 차감 상태')
    col_gameResult = find_col(df, '게임 결과')
    col_prizeName = find_col(df, '경품명')
    col_prizeCode = find_col(df, '경품코드')
    col_prizeStatus = find_col(df, '경품 지급 상태')
    col_txId = find_col(df, '거래번호')

    print(f'  원본 행수: {len(df)}')

    mask = pd.Series([True] * len(df))
    if col_gameResult:
        mask &= df[col_gameResult] != '준비'
    if col_ptSt:
        mask &= ~df[col_ptSt].isin(['실패', '취소'])
    if col_gameDate:
        def after_launch(v):
            dt = parse_datetime(v)
            if dt is None:
                return True
            return dt >= LAUNCH_DT
        mask &= df[col_gameDate].apply(after_launch)

    df = df[mask].copy()

    if col_txId:
        df = df.drop_duplicates(subset=[col_txId])

    print(f'  필터 후 행수: {len(df)}')

    cols = {
        'userId': col_userId,
        'gameName': col_gameName,
        'gameDate': col_gameDate,
        'points': col_points,
        'ptSt': col_ptSt,
        'gameResult': col_gameResult,
        'prizeName': col_prizeName,
        'prizeCode': col_prizeCode,
        'prizeStatus': col_prizeStatus,
        'txId': col_txId,
    }
    return df, cols


def read_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(path, dtype=str)
    return read_csv(path)

def load_coupon(paths):
    if isinstance(paths, str): paths = [paths]
    dfs = []
    for path in paths:
        print(f'  할인쿠폰 읽기: {os.path.basename(path)}')
        dfs.append(read_file(path))
    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    df.columns = [str(c).strip() for c in df.columns]

    col_name = find_col(df, '쿠폰명')
    col_code = find_col(df, '상품코드')
    col_pin = find_col(df, '핀번호')
    col_date = find_col(df, '발행일자') or find_col(df, '생성일')
    col_time = find_col(df, '생성시간')
    col_exp  = find_col(df, '유효기간종료일') or find_col(df, '유효기간종료') or find_col(df, '만료일') or find_col(df, '사용기한')

    if col_pin:
        df = df.drop_duplicates(subset=[col_pin])

    if col_date:
        def after_launch_coupon(row):
            date_str = str(row[col_date]).strip()
            if col_time:
                time_str = str(row[col_time]).strip()
                if time_str and time_str not in ('nan', ''):
                    dt = parse_datetime(date_str + ' ' + time_str)
                    if dt is not None:
                        return dt >= LAUNCH_DT
            dt = parse_datetime(date_str)
            if dt is None:
                return True
            # 날짜만 있는 경우 날짜 단위로 비교 (시간 불명 → 당일 전체 포함)
            if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                return dt.date() >= LAUNCH_DT.date()
            return dt >= LAUNCH_DT
        df = df[df.apply(after_launch_coupon, axis=1)].copy()

    print(f'  쿠폰 필터 후 행수: {len(df)}')
    return df, {'name': col_name, 'code': col_code, 'pin': col_pin, 'date': col_date, 'time': col_time, 'exp': col_exp}


def load_prize_csv(paths):
    if isinstance(paths, str): paths = [paths]
    dfs = []
    for path in paths:
        print(f'  매체사경품 읽기: {os.path.basename(path)}')
        dfs.append(read_file(path))
    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    df.columns = [str(c).strip() for c in df.columns]

    col_trid = find_col(df, 'B2B2C_TR_ID')
    col_status = find_col(df, '핀상태')
    col_exp = find_col(df, '유효기간')
    col_pin = find_col(df, '핀번호')
    col_price = find_col(df, '공급가격')
    col_mms = find_col(df, 'MMS발송일')
    col_mms_time = find_col(df, 'MMS발송시간')

    if col_trid:
        df[col_trid] = df[col_trid].apply(clean_trid)
        df = df[df[col_trid].str.startswith('GAME_', na=False)].copy()

    if col_status:
        df = df[~df[col_status].str.contains('취소|환불', na=False)].copy()

    if col_pin:
        df[col_pin] = df[col_pin].apply(clean_trid)
        df = df.drop_duplicates(subset=[col_pin])

    print(f'  경품 GAME_ 필터 후 행수: {len(df)}')
    return df, {
        'trid': col_trid, 'status': col_status, 'exp': col_exp,
        'pin': col_pin, 'price': col_price, 'mms': col_mms, 'mms_time': col_mms_time
    }


def compute_prize_usage(prize_df, pcols, txToGame, txToPrize):
    result = {}
    today = datetime.today()
    for _, row in prize_df.iterrows():
        trid = str(row[pcols['trid']]).strip()
        txId = trid.replace('GAME_', '', 1)
        game = txToGame.get(txId)
        pname = txToPrize.get(txId)
        if not game or not pname:
            continue

        status = str(row.get(pcols['status'], ''))
        if game not in result:
            result[game] = {}
        if pname not in result[game]:
            result[game][pname] = {'issued': 0, 'used': 0, 'expired': 0}

        if '사용' in status or '교환' in status:
            result[game][pname]['used'] += 1
        elif status in ('발행', '반품'):
            exp_val = str(row.get(pcols['exp'], '')).strip() if pcols.get('exp') else ''
            exp_digits = re.sub(r'[^0-9]', '', exp_val)
            if len(exp_digits) == 8:
                try:
                    exp_date = datetime(int(exp_digits[:4]), int(exp_digits[4:6]), int(exp_digits[6:8]))
                    if exp_date < today:
                        result[game][pname]['expired'] += 1
                    else:
                        result[game][pname]['issued'] += 1
                except Exception:
                    result[game][pname]['issued'] += 1
            else:
                result[game][pname]['issued'] += 1
        else:
            result[game][pname]['issued'] += 1

    return result


def compute_coupon_stats(coupon_df, ccols, amountGameMap):
    byType = {}
    for _, row in coupon_df.iterrows():
        name = str(row.get(ccols['name'], '')).strip()
        if not name or name == 'nan':
            continue
        code_val = str(row.get(ccols['code'], '')).strip() if ccols.get('code') else ''
        is_used = 1 if (code_val and code_val != 'nan') else 0
        amt = extract_amount(name)
        game = amountGameMap.get(amt, '-')
        if name not in byType:
            byType[name] = {'issued': 0, 'used': 0, 'game': game}
        byType[name]['issued'] += 1
        byType[name]['used'] += is_used
    return byType


def compute_daily_stats(raw_df, rcols, coupon_df, ccols, prize_df, pcols, txToPrize=None, face_map=None):
    daily = {}

    def get_day(key, dk):
        if dk not in daily:
            daily[dk] = {'points': 0, 'couponCnt': 0, 'couponAmt': 0, 'prizeCnt': 0, 'prizeAmt': 0}

    if rcols['gameDate']:
        for _, row in raw_df.iterrows():
            dk = day_key(row.get(rcols['gameDate'], ''))
            if not dk:
                continue
            get_day('points', dk)
            daily[dk]['points'] += int(float(str(row.get(rcols['points'], '0') or '0').replace(',', ''))) if row.get(rcols['points']) else 0

    if coupon_df is not None and ccols.get('date'):
        for _, row in coupon_df.iterrows():
            dk = day_key(str(row.get(ccols['date'], '')))
            if not dk:
                continue
            name = str(row.get(ccols['name'], ''))
            amt = extract_amount(name) or 0
            get_day('couponCnt', dk)
            daily[dk]['couponCnt'] += 1
            daily[dk]['couponAmt'] += amt

    if rcols.get('prizeStatus') and rcols.get('gameDate'):
        for _, row in raw_df.iterrows():
            if str(row.get(rcols['prizeStatus'], '')) == '완료':
                prize_nm = str(row.get(rcols.get('prizeName',''), '') or '')
                if '할인쿠폰' in prize_nm:
                    continue  # 쿠폰은 couponCnt에서 별도 집계
                dk = day_key(row.get(rcols['gameDate'], ''))
                if not dk:
                    continue
                get_day('prizeCnt', dk)
                daily[dk]['prizeCnt'] += 1

    print(f'  [DEBUG] prize_df={prize_df is not None}, mms={pcols.get("mms")}, price={pcols.get("price")}')
    if prize_df is not None and pcols.get('mms') and pcols.get('price'):
        print(f'  [DEBUG] 경품 rows={len(prize_df)}, mms_col={pcols["mms"]}, price_col={pcols["price"]}')
        if len(prize_df) > 0:
            sample = str(prize_df.iloc[0].get(pcols['mms'], ''))
            print(f'  [DEBUG] MMS발송일 샘플: "{sample}" / parse={parse_datetime(sample)}')
        skip_mms, skip_launch, cnt_ok = 0, 0, 0
        col_mms_time = pcols.get('mms_time', '')
        for _, row in prize_df.iterrows():
            mms_val = row.get(pcols['mms'], '')
            if not mms_val or str(mms_val).strip() in ('', 'nan'):
                skip_mms += 1; continue
            mms_dt = parse_datetime(str(mms_val))
            if mms_dt is not None and col_mms_time:
                mms_time_val = str(row.get(col_mms_time, '')).strip()
                if mms_time_val and mms_time_val not in ('', 'nan'):
                    if mms_dt.hour == 0 and mms_dt.minute == 0 and mms_dt.second == 0:
                        import re as _re
                        m = _re.match(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', mms_time_val)
                        if m:
                            try:
                                mms_dt = mms_dt.replace(
                                    hour=int(m.group(1)),
                                    minute=int(m.group(2)),
                                    second=int(m.group(3) or 0))
                            except Exception:
                                pass
            if mms_dt is None or mms_dt < LAUNCH_DT:
                skip_launch += 1; continue
            cnt_ok += 1
            dk = mms_dt.strftime('%Y-%m-%d') if mms_dt else day_key(str(mms_val))
            if not dk:
                continue
            price = 0
            if face_map is not None and txToPrize is not None and pcols.get('trid'):
                trid2 = str(row.get(pcols['trid'], '')).strip()
                txId2 = trid2.replace('GAME_', '', 1)
                pname2 = txToPrize.get(txId2, '')
                if pname2:
                    price = face_map.get(pname2, 0)
            if not price and pcols.get('price'):
                try: price = float(str(row.get(pcols['price'], '0')).replace(',', ''))
                except: price = 0
            get_day('prizeAmt', dk)
            daily[dk]['prizeAmt'] += price
        print(f'  [DEBUG] MMS없음={skip_mms}, LAUNCH이전={skip_launch}, 처리됨={cnt_ok}')

    return daily


def ask_files(prompt, required=True):
    """여러 파일 경로 입력 (엔터로 구분, 빈 줄에서 종료)"""
    print(prompt)
    print('  (파일을 하나씩 드래그하거나 경로 입력 후 엔터, 완료 시 빈 엔터)')
    paths = []
    while True:
        line = input(f'  파일 {len(paths)+1}: ').strip().strip('"\'')
        if line == '':
            if paths or not required:
                break
            print('  최소 1개 파일이 필요합니다.')
            continue
        if os.path.exists(line):
            paths.append(line)
            print(f'  → 등록됨 ({len(paths)}개)')
        else:
            print(f'  파일을 찾을 수 없습니다: {line}')
    return paths if paths else None


def read_set(service, sheet_name, col=0):
    df = read_sheet(service, sheet_name)
    if df.empty or len(df.columns) <= col:
        return set()
    return set(str(v).strip() for v in df.iloc[:, col].tolist() if str(v).strip())


def append_rows(service, sheet_name, rows):
    if not rows:
        return
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{sheet_name}!A1',
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body={'values': rows}
    ).execute()


def compute_monthly_data(raw_df, rcols, coupon_df, ccols, prize_df, pcols,
                         txToGame, txToPrize, amountGameMap):
    """월별 경품/쿠폰 집계 계산 → (prize_monthly, coupon_monthly)"""
    prize_monthly = {}
    coupon_monthly = {}

    if rcols.get('gameDate') and rcols.get('gameName') and rcols.get('prizeName'):
        for _, row in raw_df.iterrows():
            dv = parse_date_val(row.get(rcols['gameDate'], ''))
            if dv is None: continue
            mk = dv.strftime('%Y.%m')
            g = str(row.get(rcols['gameName'], ''))
            p = str(row.get(rcols['prizeName'], '')).strip()
            if not p or p == 'nan' or '할인쿠폰' in p: continue
            prize_monthly.setdefault(mk, {}).setdefault(g, {}).setdefault(p, {'issued': 0, 'exchanged': 0, 'expired': 0})
            prize_monthly[mk][g][p]['issued'] += 1

    # 로우데이터 최신 날짜 (만료 기준)
    raw_max_date = None
    if rcols.get('gameDate'):
        dates = raw_df[rcols['gameDate']].apply(parse_date_val).dropna()
        if not dates.empty:
            mx = dates.max()
            raw_max_date = mx.date() if hasattr(mx, 'date') and callable(mx.date) else mx

    if prize_df is not None and pcols.get('mms') and pcols.get('trid'):
        col_mms_time = pcols.get('mms_time', '')
        for _, row in prize_df.iterrows():
            trid = str(row.get(pcols['trid'], '')).strip()
            txId = trid.replace('GAME_', '', 1)
            game = txToGame.get(txId)
            pname = txToPrize.get(txId)
            if not game or not pname or '할인쿠폰' in pname: continue
            mms_val = row.get(pcols['mms'], '')
            mms_dt = parse_datetime(str(mms_val))
            if mms_dt is not None and col_mms_time:
                tv = str(row.get(col_mms_time, '')).strip()
                if tv and tv not in ('', 'nan') and mms_dt.hour == 0 and mms_dt.minute == 0 and mms_dt.second == 0:
                    import re as _re2
                    m2 = _re2.match(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', tv)
                    if m2:
                        try: mms_dt = mms_dt.replace(hour=int(m2.group(1)), minute=int(m2.group(2)), second=int(m2.group(3) or 0))
                        except: pass
            if mms_dt is None or mms_dt < LAUNCH_DT: continue
            mk = mms_dt.strftime('%Y.%m')
            status = str(row.get(pcols.get('status', ''), ''))
            prize_monthly.setdefault(mk, {}).setdefault(game, {}).setdefault(pname, {'issued': 0, 'exchanged': 0, 'expired': 0})
            if '폐기' in status:
                d = prize_monthly.get(mk, {}).get(game, {}).get(pname)
                if d: d['issued'] = max(0, d.get('issued', 0) - 1)
                continue
            elif '사용' in status or '교환' in status:
                prize_monthly[mk][game][pname]['exchanged'] += 1
            elif '기간만료' in status or '만료' in status:
                prize_monthly[mk][game][pname]['expired'] += 1
            elif status in ('발행', '반품'):
                exp_val = str(row.get(pcols['exp'], '')).strip() if pcols.get('exp') else ''
                exp_digits = re.sub(r'[^0-9]', '', exp_val)
                if len(exp_digits) >= 8 and raw_max_date:
                    try:
                        exp_date = datetime(int(exp_digits[:4]), int(exp_digits[4:6]), int(exp_digits[6:8])).date()
                        if exp_date < raw_max_date:
                            prize_monthly[mk][game][pname]['expired'] += 1
                    except: pass

    if coupon_df is not None and ccols.get('name') and ccols.get('date'):
        col_cexp = ccols.get('exp', '')
        for _, row in coupon_df.iterrows():
            name = str(row.get(ccols['name'], '')).strip()
            if not name or name == 'nan': continue
            dv = parse_date_val(row.get(ccols['date'], ''))
            if dv is None: continue
            mk = dv.strftime('%Y.%m')
            code_val = str(row.get(ccols.get('code', ''), '')).strip() if ccols.get('code') else ''
            is_used = 1 if (code_val and code_val != 'nan') else 0
            # 미사용이고 유효기간종료일 < 로우데이터 최신날짜 → 만료
            is_expired = 0
            if not is_used and col_cexp and raw_max_date:
                exp_dv = parse_date_val(row.get(col_cexp, ''))
                if exp_dv is not None and (exp_dv.date() if hasattr(exp_dv, 'date') and callable(exp_dv.date) else exp_dv) < raw_max_date:
                    is_expired = 1
            amt = extract_amount(name)
            game = amountGameMap.get(amt, '')
            coupon_monthly.setdefault(mk, {}).setdefault(name, {'game': game, 'issued': 0, 'used': 0, 'expired': 0})
            coupon_monthly[mk][name]['issued'] += 1
            coupon_monthly[mk][name]['used'] += is_used
            coupon_monthly[mk][name]['expired'] += is_expired

    return prize_monthly, coupon_monthly


def save_monthly_raw(service, prize_monthly, coupon_monthly):
    """월별 집계를 중간 시트에 저장 (증분 누적용)"""
    p_rows = [['월', '게임명', '경품명', '발행수', '교환수', '만료수']]
    for mk in sorted(prize_monthly):
        for g, prizes in prize_monthly[mk].items():
            for p, d in prizes.items():
                p_rows.append([mk, g, p, d['issued'], d['exchanged'], d['expired']])
    write_sheet(service, '집계_경품_월별상세', p_rows)

    c_rows = [['월', '쿠폰명', '게임명', '발행수', '사용수', '만료수']]
    for mk in sorted(coupon_monthly):
        for p, d in coupon_monthly[mk].items():
            c_rows.append([mk, p, d.get('game', ''), d['issued'], d.get('used', 0), d.get('expired', 0)])
    write_sheet(service, '집계_쿠폰_월별상세', c_rows)


def load_monthly_raw(service):
    """중간 시트에서 월별 집계 복원 → (prize_monthly, coupon_monthly)"""
    prize_monthly, coupon_monthly = {}, {}

    try:
        p_df = read_sheet(service, '집계_경품_월별상세')
    except Exception:
        print('  [참고] 집계_경품_월별상세 시트 없음 — 전체 처리 후 생성됩니다.')
        p_df = pd.DataFrame()
    if not p_df.empty and '월' in p_df.columns:
        for _, row in p_df.iterrows():
            mk, g, p = str(row.get('월', '')), str(row.get('게임명', '')), str(row.get('경품명', ''))
            if not mk or not g or not p: continue
            prize_monthly.setdefault(mk, {}).setdefault(g, {}).setdefault(p, {'issued': 0, 'exchanged': 0, 'expired': 0})
            d = prize_monthly[mk][g][p]
            d['issued']    += int(str(row.get('발행수', 0) or 0))
            d['exchanged'] += int(str(row.get('교환수', 0) or 0))
            d['expired']   += int(str(row.get('만료수', 0) or 0))

    try:
        c_df = read_sheet(service, '집계_쿠폰_월별상세')
    except Exception:
        c_df = pd.DataFrame()
    if not c_df.empty and '월' in c_df.columns:
        for _, row in c_df.iterrows():
            mk, p = str(row.get('월', '')), str(row.get('쿠폰명', ''))
            if not mk or not p: continue
            coupon_monthly.setdefault(mk, {}).setdefault(p, {'game': '', 'issued': 0, 'used': 0, 'expired': 0})
            d = coupon_monthly[mk][p]
            d['game']    = str(row.get('게임명', d['game']))
            d['issued']  += int(str(row.get('발행수', 0) or 0))
            d['used']    += int(str(row.get('사용수', 0) or 0))
            d['expired'] += int(str(row.get('만료수', 0) or 0))

    return prize_monthly, coupon_monthly


def merge_monthly(hist_pm, hist_cm, new_pm, new_cm):
    """신규 월별 데이터를 기존에 합산"""
    for mk, games in new_pm.items():
        for g, prizes in games.items():
            for p, d in prizes.items():
                hist_pm.setdefault(mk, {}).setdefault(g, {}).setdefault(p, {'issued': 0, 'exchanged': 0, 'expired': 0})
                hist_pm[mk][g][p]['issued']    += d['issued']
                hist_pm[mk][g][p]['exchanged'] += d['exchanged']
                hist_pm[mk][g][p]['expired']   += d['expired']
    for mk, coupons in new_cm.items():
        for p, d in coupons.items():
            hist_cm.setdefault(mk, {}).setdefault(p, {'game': '', 'issued': 0, 'used': 0, 'expired': 0})
            hist_cm[mk][p]['game']    = d.get('game', hist_cm[mk][p]['game'])
            hist_cm[mk][p]['issued']  += d['issued']
            hist_cm[mk][p]['used']    += d.get('used', 0)
            hist_cm[mk][p]['expired'] += d.get('expired', 0)
    return hist_pm, hist_cm


def build_revenue_sheets(service, prize_monthly, coupon_monthly,
                         game_points, face_map, fee_map, vendor_map):
    """경품/할인쿠폰/종합 수익률 탭 작성"""
    months = sorted(set(list(prize_monthly.keys()) + list(coupon_monthly.keys())))

    # ── 전체기간 상품별 합산 (전체기간합계 세부행 + 예상수익률용) ──────────────
    grand_prize = {}   # {(g, p): {'issued','exchanged','expired'}}
    for mk, games in prize_monthly.items():
        for g, prizes in games.items():
            for p, d in prizes.items():
                key = (g, p)
                if key not in grand_prize:
                    grand_prize[key] = {'issued': 0, 'exchanged': 0, 'expired': 0}
                grand_prize[key]['issued']    += d['issued']
                grand_prize[key]['exchanged'] += d['exchanged']
                grand_prize[key]['expired']   += d['expired']

    grand_coupon = {}  # {p: {'game','issued','used','expired'}}
    for mk, coupons in coupon_monthly.items():
        for p, d in coupons.items():
            if p not in grand_coupon:
                grand_coupon[p] = {'game': d.get('game',''), 'issued': 0, 'used': 0, 'expired': 0}
            grand_coupon[p]['issued']  += d['issued']
            grand_coupon[p]['used']    += d.get('used', 0)
            grand_coupon[p]['expired'] += d.get('expired', 0)

    # ── 4월 미교환율 (예상수익률 기준) ──────────────────────────────────────
    APR_MK = next((m for m in months if m.endswith('.04')), months[0] if months else '2026.04')
    apr_prize_rate   = {}  # {p: 미교환율}
    apr_coupon_rate  = {}  # {p: 미교환율}
    for g, prizes in prize_monthly.get(APR_MK, {}).items():
        for p, d in prizes.items():
            if d['issued'] > 0:
                apr_prize_rate[p] = (d['issued'] - d['exchanged']) / d['issued']
    for p, d in coupon_monthly.get(APR_MK, {}).items():
        if d['issued'] > 0:
            apr_coupon_rate[p] = (d['issued'] - d.get('used', 0)) / d['issued']
    # 전체 4월 평균 (fallback)
    _ap_i = sum(d['issued'] for g, ps in prize_monthly.get(APR_MK, {}).items() for d in ps.values())
    _ap_e = sum(d['exchanged'] for g, ps in prize_monthly.get(APR_MK, {}).items() for d in ps.values())
    apr_prize_fallback  = ((_ap_i - _ap_e) / _ap_i) if _ap_i > 0 else 0.10
    _ac_i = sum(d['issued'] for d in coupon_monthly.get(APR_MK, {}).values())
    _ac_u = sum(d.get('used', 0) for d in coupon_monthly.get(APR_MK, {}).values())
    apr_coupon_fallback = ((_ac_i - _ac_u) / _ac_i) if _ac_i > 0 else 0.10

    HDR = ['게임명', '공급사명', '상품명', '게임P', '면가', '공급수수료율(vat제외)',
           '총발행수량', '사용/교환수', '만료수',
           '교환(사용완료)', '만료금액', '미사용 금액', '총액면가 합계',
           '교환율', '미교환율',
           '교환금액', '공급수수료금액', '매체사정산대금(게임P)', '잠재수익',
           '잠재수익률(%)', '수익률(면가기준)', '확정수익', '확정수익률(%)']
    COUPON_HDR = ['게임명', '공급사명', '상품명', '게임P', '면가', '공급수수료율(vat제외)',
                  '총발행수량', '사용/교환수', '만료수',
                  '교환(사용완료)', '만료금액', '미사용 금액', '총액면가 합계',
                  '교환율', '미교환율',
                  '교환금액', '공급수수료금액', '매체사정산대금(게임P)', '잠재수익',
                  '잠재수익률(%)', '수익률(면가기준)', '확정수익', '확정수익률(%)']

    ss_meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    existing_sheets = {s['properties']['title']: s['properties']['sheetId'] for s in ss_meta.get('sheets', [])}

    # 색상 팔레트
    C_HEADER_BG  = {'red': 0.216, 'green': 0.278, 'blue': 0.349}   # #37475A 딥 슬레이트
    C_HEADER_FG  = {'red': 1.0,   'green': 1.0,   'blue': 1.0}
    C_MONTH_BG   = {'red': 0.929, 'green': 0.941, 'blue': 0.953}   # #ECEFF1 연회색
    C_MONTH_FG   = {'red': 0.157, 'green': 0.200, 'blue': 0.255}   # #283341
    C_SUMMARY_BG = {'red': 0.886, 'green': 0.925, 'blue': 0.984}   # #E2ECFB 연파랑
    C_WHITE      = {'red': 1.0,   'green': 1.0,   'blue': 1.0}
    C_BORDER     = {'red': 0.800, 'green': 0.820, 'blue': 0.843}   # #CCDAD7

    NUM_COLS = 23
    # T=잠재수익률(%), U=수익률(면가기준), V=확정수익, W=확정수익률(%)
    PCT_COLS = [5, 13, 14, 19, 20, 22]  # F(수수료율), N(교환율), O(미교환율), T, U, W
    NUM_COLS_IDX = [3, 4, 6, 7, 8, 9, 10, 11, 12, 15, 16, 17, 18, 21]  # D,E,G~M,P~S,V
    COL_WIDTHS = [120, 90, 160, 60, 70, 90, 65, 70, 65, 95, 80, 105, 85, 70, 70, 90, 90, 100, 85, 85, 80, 90, 85]

    def col_letter(idx): return chr(ord('A') + idx) if idx < 26 else 'A' + chr(ord('A') + idx - 26)

    def border_style():
        s = {'style': 'SOLID', 'width': 1, 'color': C_BORDER}
        return {'top': s, 'bottom': s, 'left': s, 'right': s}

    for tab_type in ['경품', '할인쿠폰', '종합']:
        rows = []
        row_meta = []  # 'month_label' | 'header' | 'data' | 'summary' | 'empty' | 'grand_label' | 'grand_summary'
        r = 1
        month_data_ranges = []  # [(data_start, data_end), ...]

        _hdr = COUPON_HDR if tab_type == '할인쿠폰' else HDR
        for mk in months:
            rows.append([f'[{mk}]'] + ['']*20); row_meta.append('month_label'); r += 1
            rows.append(_hdr); row_meta.append('header'); r += 1
            data_start = r

            if tab_type in ('경품', '종합'):
                for g in sorted(prize_monthly.get(mk, {}).keys(), key=lambda x: game_points.get(x, 0)):
                    for p in sorted(prize_monthly[mk][g].keys()):
                        d = prize_monthly[mk][g][p]
                        face = face_map.get(p, 0)
                        fee_r = fee_map.get(p, 0) / 100 if fee_map.get(p, 0) else 0
                        gp = game_points.get(g, 0)
                        rows.append([
                            g, vendor_map.get(p, ''), p, gp, face, fee_r,
                            d['issued'], d['exchanged'], d['expired'],
                            f'=H{r}*E{r}', f'=I{r}*E{r}', f'=(G{r}-H{r}-I{r})*E{r}', f'=J{r}+K{r}+L{r}',
                            f'=IFERROR(J{r}/M{r},"")', f'=IFERROR(1-N{r},"")',
                            f'=H{r}*E{r}', f'=H{r}*E{r}*F{r}', f'=G{r}*D{r}',
                            f'=R{r}-P{r}+Q{r}', f'=IFERROR(S{r}/R{r},"")', f'=IFERROR(S{r}/M{r},"")',
                            f'=R{r}-(G{r}-I{r})*E{r}+Q{r}', f'=IFERROR(V{r}/R{r},"")'
                        ]); row_meta.append('data'); r += 1

            if tab_type in ('할인쿠폰', '종합'):
                for p in sorted(coupon_monthly.get(mk, {}).keys()):
                    d = coupon_monthly[mk][p]
                    g = d.get('game', '')
                    gp = game_points.get(g, 0)
                    face = face_map.get(p, 0) or (extract_amount(p) or 0)
                    rows.append([
                        g, '', p, gp, face, 0,
                        d['issued'], d['used'], d.get('expired', 0),
                        f'=H{r}*E{r}', f'=I{r}*E{r}', f'=(G{r}-H{r}-I{r})*E{r}', f'=J{r}+K{r}+L{r}',
                        f'=IFERROR(J{r}/M{r},"")', f'=IFERROR(1-N{r},"")',
                        f'=H{r}*E{r}', 0, f'=G{r}*D{r}',
                        f'=R{r}-P{r}', f'=IFERROR(S{r}/R{r},"")', f'=IFERROR(S{r}/M{r},"")',
                        f'=R{r}-(G{r}-I{r})*E{r}', f'=IFERROR(V{r}/R{r},"")'
                    ]); row_meta.append('data'); r += 1

            data_end = r - 1
            if data_end >= data_start:
                month_data_ranges.append((data_start, data_end))
                rows.append([
                    f'{mk} 합계', '', '', '', '', '',
                    f'=SUM(G{data_start}:G{data_end})', f'=SUM(H{data_start}:H{data_end})', f'=SUM(I{data_start}:I{data_end})',
                    f'=SUM(J{data_start}:J{data_end})', f'=SUM(K{data_start}:K{data_end})', f'=SUM(L{data_start}:L{data_end})', f'=SUM(M{data_start}:M{data_end})',
                    f'=IFERROR(SUM(J{data_start}:J{data_end})/SUM(M{data_start}:M{data_end}),"")',
                    f'=IFERROR(1-SUM(J{data_start}:J{data_end})/SUM(M{data_start}:M{data_end}),"")',
                    f'=SUM(P{data_start}:P{data_end})', f'=SUM(Q{data_start}:Q{data_end})', f'=SUM(R{data_start}:R{data_end})',
                    f'=SUM(S{data_start}:S{data_end})',
                    f'=IFERROR(SUM(S{data_start}:S{data_end})/SUM(R{data_start}:R{data_end}),"")',
                    f'=IFERROR(SUM(S{data_start}:S{data_end})/SUM(M{data_start}:M{data_end}),"")',
                    f'=SUM(V{data_start}:V{data_end})',
                    f'=IFERROR(SUM(V{data_start}:V{data_end})/SUM(R{data_start}:R{data_end}),"")'
                ]); row_meta.append('summary'); r += 1
            rows.append(['']*23); row_meta.append('empty'); r += 1

        # 전체 기간 합계 섹션 (상품별 세부 + 총합계)
        if month_data_ranges:
            def multi_sum(col):
                return '+'.join(f'SUM({col}{ds}:{col}{de})' for ds, de in month_data_ranges)
            rows.append(['[전체 기간 합계]'] + ['']*20); row_meta.append('grand_label'); r += 1
            rows.append(_hdr); row_meta.append('header'); r += 1
            grand_detail_start = r

            if tab_type in ('경품', '종합'):
                for (g, p) in sorted(grand_prize.keys(), key=lambda k: (game_points.get(k[0], 0), k[1])):
                    d = grand_prize[(g, p)]
                    face = face_map.get(p, 0)
                    fee_r = fee_map.get(p, 0) / 100 if fee_map.get(p, 0) else 0
                    gp = game_points.get(g, 0)
                    rows.append([
                        g, vendor_map.get(p, ''), p, gp, face, fee_r,
                        d['issued'], d['exchanged'], d['expired'],
                        f'=H{r}*E{r}', f'=I{r}*E{r}', f'=(G{r}-H{r}-I{r})*E{r}', f'=J{r}+K{r}+L{r}',
                        f'=IFERROR(J{r}/M{r},"")', f'=IFERROR(1-N{r},"")',
                        f'=H{r}*E{r}', f'=H{r}*E{r}*F{r}', f'=G{r}*D{r}',
                        f'=R{r}-P{r}+Q{r}', f'=IFERROR(S{r}/R{r},"")', f'=IFERROR(S{r}/M{r},"")',
                        f'=R{r}-(G{r}-I{r})*E{r}+Q{r}', f'=IFERROR(V{r}/R{r},"")'
                    ]); row_meta.append('grand_data'); r += 1

            if tab_type in ('할인쿠폰', '종합'):
                for p in sorted(grand_coupon.keys()):
                    d = grand_coupon[p]
                    g = d.get('game', '')
                    gp = game_points.get(g, 0)
                    face = face_map.get(p, 0) or (extract_amount(p) or 0)
                    rows.append([
                        g, '', p, gp, face, 0,
                        d['issued'], d['used'], d.get('expired', 0),
                        f'=H{r}*E{r}', f'=I{r}*E{r}', f'=(G{r}-H{r}-I{r})*E{r}', f'=J{r}+K{r}+L{r}',
                        f'=IFERROR(J{r}/M{r},"")', f'=IFERROR(1-N{r},"")',
                        f'=H{r}*E{r}', 0, f'=G{r}*D{r}',
                        f'=R{r}-P{r}', f'=IFERROR(S{r}/R{r},"")', f'=IFERROR(S{r}/M{r},"")',
                        f'=R{r}-(G{r}-I{r})*E{r}', f'=IFERROR(V{r}/R{r},"")'
                    ]); row_meta.append('grand_data'); r += 1

            grand_detail_end = r - 1
            j_all = multi_sum('J'); m_all = multi_sum('M')
            rows.append([
                '전체 합계', '', '', '', '', '',
                f'={multi_sum("G")}', f'={multi_sum("H")}', f'={multi_sum("I")}',
                f'={multi_sum("J")}', f'={multi_sum("K")}', f'={multi_sum("L")}', f'={multi_sum("M")}',
                f'=IFERROR(({j_all})/({m_all}),"")',
                f'=IFERROR(1-({j_all})/({m_all}),"")',
                f'={multi_sum("P")}', f'={multi_sum("Q")}', f'={multi_sum("R")}',
                f'={multi_sum("S")}',
                f'=IFERROR(({multi_sum("S")})/({multi_sum("R")}),"")',
                f'=IFERROR(({multi_sum("S")})/({multi_sum("M")}),"")',
                f'={multi_sum("V")}',
                f'=IFERROR(({multi_sum("V")})/({multi_sum("R")}),"")'
            ]); row_meta.append('grand_summary'); r += 1

        # 시트 삭제 후 재생성 → 새 sheetId 획득
        reqs = []
        if tab_type in existing_sheets:
            reqs.append({'deleteSheet': {'sheetId': existing_sheets[tab_type]}})
        reqs.append({'addSheet': {'properties': {'title': tab_type}}})
        res = _batch_update(service, reqs)
        new_sid = next(r2['addSheet']['properties']['sheetId'] for r2 in res['replies'] if 'addSheet' in r2)

        _values_call(lambda: service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID, range=f'{tab_type}!A1',
            valueInputOption='USER_ENTERED', body={'values': rows}
        ).execute())

        # 서식 적용
        fmt_reqs = []
        total_rows = len(row_meta)

        # 행별 배경색 + 볼드
        C_GRAND_LABEL_BG = {'red': 0.196, 'green': 0.396, 'blue': 0.329}   # #326554 딥 그린
        C_GRAND_SUM_BG   = {'red': 0.851, 'green': 0.937, 'blue': 0.898}   # #D9EFE5 연그린
        C_GRAND_DATA_BG  = {'red': 0.933, 'green': 0.965, 'blue': 0.949}   # #EEF6F2 연연그린

        for i, mt in enumerate(row_meta):
            if mt == 'empty': continue
            if mt == 'grand_label':
                bg = C_GRAND_LABEL_BG; bold = True; fg = C_HEADER_FG
            elif mt == 'grand_summary':
                bg = C_GRAND_SUM_BG; bold = True; fg = {'red': 0.10, 'green': 0.26, 'blue': 0.21}
            elif mt == 'grand_data':
                bg = C_GRAND_DATA_BG; bold = False; fg = {'red': 0.13, 'green': 0.13, 'blue': 0.13}
            else:
                bg = C_MONTH_BG if mt == 'month_label' else C_HEADER_BG if mt == 'header' else C_SUMMARY_BG if mt == 'summary' else C_WHITE
                bold = mt in ('month_label', 'header', 'summary')
                fg = C_HEADER_FG if mt == 'header' else C_MONTH_FG if mt == 'month_label' else {'red': 0.13, 'green': 0.13, 'blue': 0.13}
            cell_fmt = {
                'backgroundColor': bg,
                'textFormat': {'bold': bold, 'foregroundColor': fg, 'fontSize': 10},
                'verticalAlignment': 'MIDDLE',
                'padding': {'top': 4, 'bottom': 4, 'left': 6, 'right': 6}
            }
            fmt_reqs.append({'repeatCell': {
                'range': {'sheetId': new_sid, 'startRowIndex': i, 'endRowIndex': i+1, 'startColumnIndex': 0, 'endColumnIndex': NUM_COLS},
                'cell': {'userEnteredFormat': cell_fmt},
                'fields': 'userEnteredFormat(backgroundColor,textFormat,verticalAlignment,padding)'
            }})

        # 테두리 (데이터+합계 행)
        data_rows = [i for i, mt in enumerate(row_meta) if mt in ('data', 'summary', 'header', 'grand_summary', 'grand_data')]
        for i in data_rows:
            fmt_reqs.append({'updateBorders': {
                'range': {'sheetId': new_sid, 'startRowIndex': i, 'endRowIndex': i+1, 'startColumnIndex': 0, 'endColumnIndex': NUM_COLS},
                'top': {'style': 'SOLID', 'width': 1, 'color': C_BORDER},
                'bottom': {'style': 'SOLID', 'width': 1, 'color': C_BORDER},
                'innerHorizontal': {'style': 'SOLID', 'width': 1, 'color': C_BORDER},
                'innerVertical': {'style': 'SOLID', 'width': 1, 'color': C_BORDER}
            }})

        # 숫자 서식 — 데이터/합계 행에만
        data_sum_rows = [i for i, mt in enumerate(row_meta) if mt in ('data', 'summary', 'grand_summary', 'grand_data')]
        for i in data_sum_rows:
            for col in PCT_COLS:
                fmt_reqs.append({'repeatCell': {
                    'range': {'sheetId': new_sid, 'startRowIndex': i, 'endRowIndex': i+1, 'startColumnIndex': col, 'endColumnIndex': col+1},
                    'cell': {'userEnteredFormat': {'numberFormat': {'type': 'PERCENT', 'pattern': '0.0%'}}},
                    'fields': 'userEnteredFormat.numberFormat'
                }})
            for col in NUM_COLS_IDX:
                fmt_reqs.append({'repeatCell': {
                    'range': {'sheetId': new_sid, 'startRowIndex': i, 'endRowIndex': i+1, 'startColumnIndex': col, 'endColumnIndex': col+1},
                    'cell': {'userEnteredFormat': {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}}},
                    'fields': 'userEnteredFormat.numberFormat'
                }})

        # 열 너비
        for ci, w in enumerate(COL_WIDTHS):
            fmt_reqs.append({'updateDimensionProperties': {
                'range': {'sheetId': new_sid, 'dimension': 'COLUMNS', 'startIndex': ci, 'endIndex': ci+1},
                'properties': {'pixelSize': w},
                'fields': 'pixelSize'
            }})

        # 행 높이: 헤더 28px, 데이터 24px
        for i, mt in enumerate(row_meta):
            h = 30 if mt == 'header' else 24
            fmt_reqs.append({'updateDimensionProperties': {
                'range': {'sheetId': new_sid, 'dimension': 'ROWS', 'startIndex': i, 'endIndex': i+1},
                'properties': {'pixelSize': h},
                'fields': 'pixelSize'
            }})

        # 전체 합계 행 셀 메모
        GRAND_NOTES = {
            6:  '전체 기간 총 발행 수량',
            7:  '전체 기간 총 사용/교환 수량',
            8:  '전체 기간 총 만료 수량',
            9:  '교환(사용완료) 금액\n= 사용/교환수 × 면가 합계',
            10: '기간만료 금액\n= 만료수 × 면가 합계',
            11: '잔여발행금액\n= (발행수 - 사용수 - 만료수) × 면가 합계',
            12: '총합계\n= 교환금액 + 만료금액 + 잔여금액\n= 총 발행수 × 면가',
            13: '교환율\n= 교환금액 합계 ÷ 총발행금액 합계\n= 교환수 ÷ 발행수',
            14: '미교환율\n= 1 - 교환율\n(만료 + 잔여 수량 포함)',
            15: '교환금액\n= 사용/교환수 × 면가 합계',
            16: '공급수수료금액 (vat포함)\n= 사용수 × 면가 × 공급수수료율 합계',
            17: '매체사정산대금(게임P) (IBK 청구금액)\n= 발행수 × 게임P 합계',
            18: '잠재수익\n경품: 매체사정산 - 교환금액 + 공급수수료\n할인쿠폰: 매체사정산 - 교환금액',
            19: '수익률\n= 잠재수익 ÷ 매체사정산대금',
            21: '확정수익\n경품: 매체사정산 - (발행수-만료수)×면가 + 공급수수료\n할인쿠폰: 매체사정산 - (발행수-만료수)×면가',
        }
        gs_idx = next((i for i, mt in enumerate(row_meta) if mt == 'grand_summary'), None)
        if gs_idx is not None:
            for col, note in GRAND_NOTES.items():
                fmt_reqs.append({'repeatCell': {
                    'range': {'sheetId': new_sid, 'startRowIndex': gs_idx, 'endRowIndex': gs_idx+1, 'startColumnIndex': col, 'endColumnIndex': col+1},
                    'cell': {'note': note},
                    'fields': 'note'
                }})

        # 첫 행 고정 (없음 — 월별 헤더가 반복되므로 skip)
        # 텍스트 래핑: 클립
        fmt_reqs.append({'repeatCell': {
            'range': {'sheetId': new_sid, 'startRowIndex': 0, 'endRowIndex': total_rows, 'startColumnIndex': 0, 'endColumnIndex': NUM_COLS},
            'cell': {'userEnteredFormat': {'wrapStrategy': 'CLIP'}},
            'fields': 'userEnteredFormat.wrapStrategy'
        }})

        # batchUpdate를 200개씩 나눠서 전송 (API 제한)
        chunk = 200
        for start in range(0, len(fmt_reqs), chunk):
            _batch_update(service, fmt_reqs[start:start+chunk])

        print(f'  {tab_type} 탭 완료')

    # ────────────────────────────────────────────────────────────────────────
    # 예상수익률 탭 (4월 미교환율 기준 전체기간 예상치)
    # ────────────────────────────────────────────────────────────────────────
    print('  예상수익률 탭 작성...')
    exp_rows = []
    exp_meta = []
    r = 1

    exp_rows.append([f'[예상수익률 — {APR_MK} 미교환율 기준]'] + ['']*20)
    exp_meta.append('grand_label'); r += 1
    exp_rows.append([
        f'※ 경품 미교환율 기준: {apr_prize_fallback*100:.1f}%  |  '
        f'쿠폰 미교환율 기준: {apr_coupon_fallback*100:.1f}%  (개별 상품은 4월 실적 적용, 없으면 평균 적용)'
    ] + ['']*20)
    exp_meta.append('note'); r += 1
    exp_rows.append(HDR); exp_meta.append('header'); r += 1
    data_start_exp = r

    # 경품 예상
    for (g, p) in sorted(grand_prize.keys(), key=lambda k: (game_points.get(k[0], 0), k[1])):
        d = grand_prize[(g, p)]
        face   = face_map.get(p, 0)
        fee_r  = fee_map.get(p, 0) / 100 if fee_map.get(p, 0) else 0
        gp     = game_points.get(g, 0)
        nex_r  = apr_prize_rate.get(p, apr_prize_fallback)
        exp_ex = round(d['issued'] * (1 - nex_r))
        exp_xp = d['issued'] - exp_ex
        exp_rows.append([
            g, vendor_map.get(p, ''), p, gp, face, fee_r,
            d['issued'], exp_ex, exp_xp,
            f'=H{r}*E{r}', f'=I{r}*E{r}', f'=(G{r}-H{r}-I{r})*E{r}', f'=J{r}+K{r}+L{r}',
            f'=IFERROR(J{r}/M{r},"")', f'=IFERROR(1-N{r},"")',
            f'=H{r}*E{r}', f'=H{r}*E{r}*F{r}', f'=G{r}*D{r}',
            f'=R{r}-P{r}+Q{r}', f'=IFERROR(S{r}/R{r},"")', f'=IFERROR(S{r}/M{r},"")',
            f'=R{r}-(G{r}-I{r})*E{r}+Q{r}', f'=IFERROR(V{r}/R{r},"")'
        ]); exp_meta.append('grand_data'); r += 1

    # 할인쿠폰 예상
    for p in sorted(grand_coupon.keys()):
        d    = grand_coupon[p]
        g    = d.get('game', '')
        gp   = game_points.get(g, 0)
        face = face_map.get(p, 0) or (extract_amount(p) or 0)
        nex_r  = apr_coupon_rate.get(p, apr_coupon_fallback)
        exp_us = round(d['issued'] * (1 - nex_r))
        exp_xp = d['issued'] - exp_us
        exp_rows.append([
            g, '', p, gp, face, 0,
            d['issued'], exp_us, exp_xp,
            f'=H{r}*E{r}', f'=I{r}*E{r}', f'=(G{r}-H{r}-I{r})*E{r}', f'=J{r}+K{r}+L{r}',
            f'=IFERROR(J{r}/M{r},"")', f'=IFERROR(1-N{r},"")',
            f'=H{r}*E{r}', 0, f'=G{r}*D{r}',
            f'=R{r}-P{r}', f'=IFERROR(S{r}/R{r},"")', f'=IFERROR(S{r}/M{r},"")',
            f'=R{r}-(G{r}-I{r})*E{r}', f'=IFERROR(V{r}/R{r},"")'
        ]); exp_meta.append('grand_data'); r += 1

    data_end_exp = r - 1
    exp_rows.append([
        '예상 합계', '', '', '', '', '',
        f'=SUM(G{data_start_exp}:G{data_end_exp})',
        f'=SUM(H{data_start_exp}:H{data_end_exp})',
        f'=SUM(I{data_start_exp}:I{data_end_exp})',
        f'=SUM(J{data_start_exp}:J{data_end_exp})',
        f'=SUM(K{data_start_exp}:K{data_end_exp})',
        f'=SUM(L{data_start_exp}:L{data_end_exp})',
        f'=SUM(M{data_start_exp}:M{data_end_exp})',
        f'=IFERROR(SUM(J{data_start_exp}:J{data_end_exp})/SUM(M{data_start_exp}:M{data_end_exp}),"")',
        f'=IFERROR(1-SUM(J{data_start_exp}:J{data_end_exp})/SUM(M{data_start_exp}:M{data_end_exp}),"")',
        f'=SUM(P{data_start_exp}:P{data_end_exp})',
        f'=SUM(Q{data_start_exp}:Q{data_end_exp})',
        f'=SUM(R{data_start_exp}:R{data_end_exp})',
        f'=SUM(S{data_start_exp}:S{data_end_exp})',
        f'=IFERROR(SUM(S{data_start_exp}:S{data_end_exp})/SUM(R{data_start_exp}:R{data_end_exp}),"")',
        f'=IFERROR(SUM(S{data_start_exp}:S{data_end_exp})/SUM(M{data_start_exp}:M{data_end_exp}),"")',
        f'=SUM(V{data_start_exp}:V{data_end_exp})',
        f'=IFERROR(SUM(V{data_start_exp}:V{data_end_exp})/SUM(R{data_start_exp}:R{data_end_exp}),"")'
    ]); exp_meta.append('grand_summary'); r += 1

    # 시트 생성
    reqs = []
    if '예상수익률' in existing_sheets:
        reqs.append({'deleteSheet': {'sheetId': existing_sheets['예상수익률']}})
    reqs.append({'addSheet': {'properties': {'title': '예상수익률'}}})
    res = _batch_update(service, reqs)
    exp_sid = next(r2['addSheet']['properties']['sheetId'] for r2 in res['replies'] if 'addSheet' in r2)

    _values_call(lambda: service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range='예상수익률!A1',
        valueInputOption='USER_ENTERED', body={'values': exp_rows}
    ).execute())

    # 서식
    C_GRAND_LABEL_BG = {'red': 0.196, 'green': 0.396, 'blue': 0.329}
    C_GRAND_SUM_BG   = {'red': 0.851, 'green': 0.937, 'blue': 0.898}
    C_GRAND_DATA_BG  = {'red': 0.933, 'green': 0.965, 'blue': 0.949}
    C_NOTE_BG        = {'red': 1.0,   'green': 0.976, 'blue': 0.890}  # 연노랑
    efmt = []
    for i, mt in enumerate(exp_meta):
        if mt == 'grand_label':
            bg = C_GRAND_LABEL_BG; bold = True; fg = C_HEADER_FG
        elif mt == 'grand_summary':
            bg = C_GRAND_SUM_BG; bold = True; fg = {'red': 0.10, 'green': 0.26, 'blue': 0.21}
        elif mt == 'grand_data':
            bg = C_GRAND_DATA_BG; bold = False; fg = {'red': 0.13, 'green': 0.13, 'blue': 0.13}
        elif mt == 'header':
            bg = C_HEADER_BG; bold = True; fg = C_HEADER_FG
        elif mt == 'note':
            bg = C_NOTE_BG; bold = False; fg = {'red': 0.35, 'green': 0.27, 'blue': 0.0}
        else:
            continue
        efmt.append({'repeatCell': {
            'range': {'sheetId': exp_sid, 'startRowIndex': i, 'endRowIndex': i+1, 'startColumnIndex': 0, 'endColumnIndex': NUM_COLS},
            'cell': {'userEnteredFormat': {
                'backgroundColor': bg,
                'textFormat': {'bold': bold, 'foregroundColor': fg, 'fontSize': 10},
                'verticalAlignment': 'MIDDLE',
                'padding': {'top': 4, 'bottom': 4, 'left': 6, 'right': 6}
            }},
            'fields': 'userEnteredFormat(backgroundColor,textFormat,verticalAlignment,padding)'
        }})
    for i, mt in enumerate(exp_meta):
        if mt not in ('grand_data', 'grand_summary', 'header'): continue
        efmt.append({'updateBorders': {
            'range': {'sheetId': exp_sid, 'startRowIndex': i, 'endRowIndex': i+1, 'startColumnIndex': 0, 'endColumnIndex': NUM_COLS},
            'top': {'style': 'SOLID', 'width': 1, 'color': C_BORDER},
            'bottom': {'style': 'SOLID', 'width': 1, 'color': C_BORDER},
            'innerHorizontal': {'style': 'SOLID', 'width': 1, 'color': C_BORDER},
            'innerVertical': {'style': 'SOLID', 'width': 1, 'color': C_BORDER}
        }})
    for i, mt in enumerate(exp_meta):
        if mt not in ('grand_data', 'grand_summary'): continue
        for col in PCT_COLS:
            efmt.append({'repeatCell': {
                'range': {'sheetId': exp_sid, 'startRowIndex': i, 'endRowIndex': i+1, 'startColumnIndex': col, 'endColumnIndex': col+1},
                'cell': {'userEnteredFormat': {'numberFormat': {'type': 'PERCENT', 'pattern': '0.0%'}}},
                'fields': 'userEnteredFormat.numberFormat'
            }})
        for col in NUM_COLS_IDX:
            efmt.append({'repeatCell': {
                'range': {'sheetId': exp_sid, 'startRowIndex': i, 'endRowIndex': i+1, 'startColumnIndex': col, 'endColumnIndex': col+1},
                'cell': {'userEnteredFormat': {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}}},
                'fields': 'userEnteredFormat.numberFormat'
            }})
    for ci, w in enumerate(COL_WIDTHS):
        efmt.append({'updateDimensionProperties': {
            'range': {'sheetId': exp_sid, 'dimension': 'COLUMNS', 'startIndex': ci, 'endIndex': ci+1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})
    efmt.append({'repeatCell': {
        'range': {'sheetId': exp_sid, 'startRowIndex': 0, 'endRowIndex': len(exp_meta), 'startColumnIndex': 0, 'endColumnIndex': NUM_COLS},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'CLIP'}},
        'fields': 'userEnteredFormat.wrapStrategy'
    }})
    for start in range(0, len(efmt), 200):
        _batch_update(service, efmt[start:start+200])
    print('  예상수익률 탭 완료')


def write_internal_report(service):
    """내부보고 탭 전체 자동 생성"""
    print('  내부보고 탭 작성...')
    from datetime import date as _date
    today_str = _date.today().strftime('%Y.%m.%d')

    summary_df   = read_sheet(service, '집계_누적')
    games_df     = read_sheet(service, '집계_게임별')
    prize_use_df = read_sheet(service, '집계_경품사용')
    coupons_df   = read_sheet(service, '집계_쿠폰')
    monthly_df   = read_sheet(service, '집계_월별')
    daily_df     = read_sheet(service, '집계_일별')
    gmu_df       = read_sheet(service, '집계_게임_월별')
    master_df_ir = read_sheet(service, '경품코드 마스터')

    total_runs = unique_users = total_pts = prize_done = avg_runs = avg_users = 0
    date_start = date_end = ''
    if not summary_df.empty:
        s = summary_df.iloc[0]
        total_runs   = int(str(s.get('총실행수', 0) or 0))
        unique_users = int(str(s.get('유니크참여자', 0) or 0))
        total_pts    = int(str(s.get('총소진포인트', 0) or 0))
        prize_done   = int(str(s.get('경품완료', 0) or 0))
        date_start   = str(s.get('데이터시작', ''))
        date_end     = str(s.get('데이터종료', ''))
        avg_runs     = int(str(s.get('일평균실행', 0) or 0))
        avg_users    = int(str(s.get('일평균참여자', 0) or 0))
    avg_pts    = round(total_pts / total_runs) if total_runs else 0
    date_range = f'{date_start} ~ {date_end}' if date_start else ''

    rows = []
    def r(*cells): rows.append(list(cells))
    def empty(): rows.append([])

    r('', 'IBK 게임 운영 내부 현황')
    r('', f'기준일: {today_str}   |   데이터 기간: {date_range}')
    empty()

    r('', '종합 현황')
    r('', '총 게임 실행 수(회)', f'{total_runs:,}', '실제 참여자(명)', f'{unique_users:,}')
    r('', '일 평균 게임 실행 수(회)', f'{avg_runs:,}', '일 평균 실제 참여자(명)', f'{avg_users:,}')
    r('', '포인트 사용 합계(P)', f'{total_pts:,}', '게임당 평균(P)', f'{avg_pts:,}')
    r('', '경품 지급 완료(건)', f'{prize_done:,}')
    empty()

    r('', '게임별 실행 수')
    r('', '게임명', '실행 수(회)', '비율')
    total_game_runs = 0
    game_run_list = []
    if not games_df.empty and '게임명' in games_df.columns:
        for _, row in games_df.iterrows():
            g   = str(row.get('게임명', ''))
            cnt = int(str(row.get('실행수', 0) or 0))
            pt  = str(row.get('포인트P', ''))
            label = f'{g} ({pt}P)' if pt and pt not in ('nan', '0', '') else g
            game_run_list.append((label, cnt))
            total_game_runs += cnt
    for label, cnt in sorted(game_run_list, key=lambda x: -x[1]):
        ratio = f'{cnt/total_game_runs*100:.1f}%' if total_game_runs else '0%'
        r('', label, f'{cnt:,}', ratio)
    r('', '합계', f'{total_game_runs:,}', '100%')
    empty()

    r('', '게임별 경품 발행·사용 현황')
    vendor_ir = {}
    if not master_df_ir.empty:
        cmn = find_col(master_df_ir, '경품명'); cmv = find_col(master_df_ir, '교환처')
        if cmn and cmv:
            for _, row in master_df_ir.iterrows():
                pn = str(row.get(cmn, '')).strip(); v = str(row.get(cmv, '')).strip()
                if pn and v and v != 'nan': vendor_ir[pn] = v
    game_prize_ir = {}
    if not prize_use_df.empty and '게임명' in prize_use_df.columns:
        for _, row in prize_use_df.iterrows():
            g = str(row.get('게임명', '')); p = str(row.get('경품명', ''))
            v = str(row.get('교환처', '') or vendor_ir.get(p, ''))
            issued  = int(str(row.get('발행수', 0) or 0))
            used    = int(str(row.get('사용수', 0) or 0))
            expired = int(str(row.get('만료수', 0) or 0))
            if g not in game_prize_ir: game_prize_ir[g] = []
            game_prize_ir[g].append((p, v, issued, used, expired))
    gp_pt_map = {}
    if not games_df.empty and '게임명' in games_df.columns:
        for _, row in games_df.iterrows():
            gp_pt_map[str(row.get('게임명', ''))] = str(row.get('포인트P', ''))
    for g in sorted(game_prize_ir):
        items   = game_prize_ir[g]
        total_i = sum(x[2] for x in items)
        pt      = gp_pt_map.get(g, '')
        label   = f'{g} ({pt}P)  (총 {total_i:,}회)' if pt and pt not in ('nan', '0', '') else f'{g}  (총 {total_i:,}회)'
        r('', label)
        r('', '교환처', '경품명', '발행(건)', '사용(건)', '기간만료(건)', '사용률', '당첨확률')
        for p, v, issued, used, expired in sorted(items, key=lambda x: -x[2]):
            if issued == 0:
                continue
            ur = f'{used/issued*100:.1f}%' if issued else '0%'
            wr = f'{issued/total_i*100:.1f}%' if total_i else '0%'
            r('', v, p, f'{issued:,}', f'{used:,}', f'{expired:,}', ur, wr)
        g_used = sum(x[3] for x in items); g_exp = sum(x[4] for x in items)
        r('', '', '합계', f'{total_i:,}', f'{g_used:,}', f'{g_exp:,}',
          f'{g_used/total_i*100:.1f}%' if total_i else '0%', '100%')
        empty()

    r('', '할인쿠폰 현황')
    r('', '종류별 발행 · 사용 현황')
    r('', '교환처', '쿠폰명', '발행(건)', '사용(건)', '사용률')
    c_ti = c_tu = 0
    game_coupon_ir = {}
    if not coupons_df.empty and '쿠폰명' in coupons_df.columns:
        for _, row in coupons_df.iterrows():
            cn = str(row.get('쿠폰명', '')); gn = str(row.get('게임명', ''))
            ci = int(str(row.get('발행수', 0) or 0)); cu = int(str(row.get('사용수', 0) or 0))
            if ci == 0:
                continue
            _m = re.match(r'\[IBK\]\s+(\S+)', cn)
            cv = _m.group(1) if _m else ''
            r('', cv, cn, f'{ci:,}', f'{cu:,}', f'{cu/ci*100:.1f}%')
            c_ti += ci; c_tu += cu
            if gn not in game_coupon_ir: game_coupon_ir[gn] = []
            game_coupon_ir[gn].append((cn, ci, cu))
    r('', '', '합계', f'{c_ti:,}', f'{c_tu:,}', f'{c_tu/c_ti*100:.1f}%' if c_ti else '0%')
    empty()
    r('', '게임별 쿠폰 발행 · 사용')
    r('', '게임명', '발행(건)', '사용(건)', '사용률')
    for gn in sorted(game_coupon_ir):
        gi = sum(x[1] for x in game_coupon_ir[gn]); gu = sum(x[2] for x in game_coupon_ir[gn])
        if gi == 0:
            continue
        r('', gn, f'{gi:,}', f'{gu:,}', f'{gu/gi*100:.1f}%')
    empty()

    r('', '게임별 월 실행수')
    if not gmu_df.empty and '게임명' in gmu_df.columns:
        months_gmu = sorted(gmu_df['월'].dropna().unique().tolist())
        r('', '게임명', *months_gmu, '합계')
        gmu_run_data = {}
        for _, row in gmu_df.iterrows():
            g = str(row.get('게임명', '')); mk = str(row.get('월', ''))
            cnt = int(str(row.get('실행수', 0) or 0))
            if g and mk:
                if g not in gmu_run_data: gmu_run_data[g] = {}
                gmu_run_data[g][mk] = cnt
        month_sum_run = {mk: 0 for mk in months_gmu}
        for g in sorted(gmu_run_data):
            vals = [gmu_run_data[g].get(mk, 0) for mk in months_gmu]
            for mk, v in zip(months_gmu, vals): month_sum_run[mk] += v
            r('', g, *[f'{v:,}' for v in vals], f'{sum(vals):,}')
        r('', '합계', *[f'{month_sum_run[mk]:,}' for mk in months_gmu], f'{sum(month_sum_run.values()):,}')
    empty()

    r('', '게임별 월 참여자수')
    if not gmu_df.empty and '게임명' in gmu_df.columns:
        months_gmu = sorted(gmu_df['월'].dropna().unique().tolist())
        r('', '게임명', *months_gmu, '합계')
        gmu_data = {}
        for _, row in gmu_df.iterrows():
            g = str(row.get('게임명', '')); mk = str(row.get('월', ''))
            cnt = int(str(row.get('참여자수', 0) or 0))
            if g and mk:
                if g not in gmu_data: gmu_data[g] = {}
                gmu_data[g][mk] = cnt
        month_sum = {mk: 0 for mk in months_gmu}
        for g in sorted(gmu_data):
            vals = [gmu_data[g].get(mk, 0) for mk in months_gmu]
            for mk, v in zip(months_gmu, vals): month_sum[mk] += v
            r('', g, *[f'{v:,}' for v in vals], f'{sum(vals):,}')
        r('', '합계', *[f'{month_sum[mk]:,}' for mk in months_gmu], f'{sum(month_sum.values()):,}')
    empty()

    r('', '월별 집계')
    r('', '월', '총 실행(회)', '참여자(명)')
    if not monthly_df.empty and '월' in monthly_df.columns:
        for _, row in monthly_df.sort_values('월', ascending=False).iterrows():
            mk = str(row.get('월', ''))
            tm = int(str(row.get('실행수', 0) or 0))
            um = int(str(row.get('유니크참여자', 0) or 0))
            try: y, m = mk.split('.'); mk_lbl = f'{y}년 {m}월'
            except: mk_lbl = mk
            r('', mk_lbl, f'{tm:,}', f'{um:,}')
    empty()

    r('', '일별 현황')
    r('', '날짜', '요일', '소진포인트(P)', '총혜택금액(원)', '할인쿠폰 발행', '할인쿠폰 총액', '경품 발행', '경품 총액')
    d_tot = {'pts': 0, 'ben': 0, 'ci': 0, 'ca': 0, 'pi': 0, 'pa': 0}
    m_tot = {}
    if not daily_df.empty and '날짜' in daily_df.columns:
        for _, row in daily_df.iterrows():
            d  = str(row.get('날짜', '')); wd = str(row.get('요일', ''))
            pts = int(str(row.get('소진포인트', 0) or 0))
            ben = int(str(row.get('총혜택금액', 0) or 0))
            ci  = int(str(row.get('할인쿠폰발행', 0) or 0))
            ca  = int(str(row.get('할인쿠폰총액', 0) or 0))
            pi  = int(str(row.get('경품발행', 0) or 0))
            pa  = int(str(row.get('경품총액', 0) or 0))
            if pts == 0 and ben == 0 and ci == 0 and pi == 0:
                continue
            r('', d, wd, f'{pts:,}', f'{ben:,}', f'{ci:,}', f'{ca:,}', f'{pi:,}', f'{pa:,}')
            d_tot['pts'] += pts; d_tot['ben'] += ben; d_tot['ci'] += ci
            d_tot['ca'] += ca;  d_tot['pi'] += pi;   d_tot['pa'] += pa
            try: mk = d[:4] + '.' + d[5:7]
            except: mk = ''
            if mk:
                if mk not in m_tot: m_tot[mk] = {'pts': 0, 'ben': 0, 'ci': 0, 'ca': 0, 'pi': 0, 'pa': 0}
                m_tot[mk]['pts'] += pts; m_tot[mk]['ben'] += ben; m_tot[mk]['ci'] += ci
                m_tot[mk]['ca']  += ca;  m_tot[mk]['pi']  += pi;  m_tot[mk]['pa']  += pa
    r('', '합계', '', f'{d_tot["pts"]:,}', f'{d_tot["ben"]:,}',
      f'{d_tot["ci"]:,}', f'{d_tot["ca"]:,}', f'{d_tot["pi"]:,}', f'{d_tot["pa"]:,}')
    empty()

    r('', '월별 합계')
    r('', '월', '소진포인트(P)', '총혜택금액(원)', '할인쿠폰 발행', '할인쿠폰 총액', '경품 발행', '경품 총액')
    for mk in sorted(m_tot, reverse=True):
        d = m_tot[mk]
        try: y, mo = mk.split('.'); mk_lbl = f'{y}년 {mo}월'
        except: mk_lbl = mk
        r('', mk_lbl, f'{d["pts"]:,}', f'{d["ben"]:,}', f'{d["ci"]:,}', f'{d["ca"]:,}', f'{d["pi"]:,}', f'{d["pa"]:,}')

    write_sheet(service, '내부보고', rows)
    format_report_sheet(service, '내부보고')
    print('  내부보고 완료')
    _save_snapshot(rows)


def write_external_report(service):
    """외부보고 탭 자동 생성 (경영진/외부 공유용 요약)"""
    print('  외부보고 탭 작성...')
    from datetime import date as _date
    today_str = _date.today().strftime('%Y.%m.%d')

    summary_df   = read_sheet(service, '집계_누적')
    games_df     = read_sheet(service, '집계_게임별')
    prize_use_df = read_sheet(service, '집계_경품사용')
    coupons_df   = read_sheet(service, '집계_쿠폰')
    gmu_df       = read_sheet(service, '집계_게임_월별')

    total_runs = unique_users = 0
    date_start = date_end = ''
    if not summary_df.empty:
        s = summary_df.iloc[0]
        total_runs   = int(str(s.get('총실행수', 0) or 0))
        unique_users = int(str(s.get('유니크참여자', 0) or 0))
        date_start   = str(s.get('데이터시작', ''))
        date_end     = str(s.get('데이터종료', ''))
    date_range = f'{date_start} ~ {date_end}' if date_start else ''

    rows = []
    def r(*cells): rows.append(list(cells))
    def empty(): rows.append([])

    r('', 'IBK 카드앱 게이미피케이션 운영 현황')
    r('', f'기준일: {today_str}   |   데이터 기간: {date_range}')
    empty()

    r('', '종합 현황')
    r('', '총 게임 실행 수(회)', f'{total_runs:,}', '실제 참여자(명)', f'{unique_users:,}')
    empty()

    r('', '게임별 실행 수')
    r('', '게임명', '실행 수(회)', '비율')
    total_game_runs = 0
    game_run_list = []
    if not games_df.empty and '게임명' in games_df.columns:
        for _, row in games_df.iterrows():
            g   = str(row.get('게임명', ''))
            cnt = int(str(row.get('실행수', 0) or 0))
            pt  = str(row.get('포인트P', ''))
            label = f'{g} ({int(pt):,}P)' if pt and pt not in ('nan', '0', '') else g
            game_run_list.append((label, cnt))
            total_game_runs += cnt
    for label, cnt in sorted(game_run_list, key=lambda x: -x[1]):
        ratio = f'{cnt/total_game_runs*100:.1f}%' if total_game_runs else '0%'
        r('', label, f'{cnt:,}', ratio)
    r('', '합계', f'{total_game_runs:,}', '100%')
    empty()

    write_sheet(service, '외부보고', rows)
    format_report_sheet(service, '외부보고')
    print('  외부보고 완료')


def _save_snapshot(rows):
    """내부보고 완료 후 JSON 파일로 스냅샷 저장 (snapshots/YYYYMMDD.json)"""
    import json
    today = date.today().strftime('%Y%m%d')
    snap_dir = os.path.join(os.path.dirname(__file__), 'snapshots')
    os.makedirs(snap_dir, exist_ok=True)
    path = os.path.join(snap_dir, f'{today}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f'  스냅샷 저장: {path}')


def run_full(raw_df, rcols, coupon_df, ccols, prize_df, pcols, service):
    print('\n[2/5] 집계 계산...')
    total = len(raw_df)
    users = set(str(v).strip() for v in raw_df[rcols['userId']].dropna().tolist() if str(v).strip()) if rcols['userId'] else set()
    unique_users = len(users)

    total_points = raw_df[rcols['points']].apply(
        lambda v: int(float(str(v).replace(',', ''))) if v and str(v).strip() not in ('', 'nan') else 0
    ).sum() if rcols['points'] else 0

    prize_done = raw_df[raw_df[rcols['prizeStatus']] == '완료'].shape[0] if rcols['prizeStatus'] else 0
    prize_fail = total - prize_done

    dates = raw_df[rcols['gameDate']].apply(parse_date_val).dropna() if rcols['gameDate'] else pd.Series([], dtype=object)
    min_date = dates.min() if len(dates) else None
    max_date = dates.max() if len(dates) else None
    unique_days = dates.nunique() if len(dates) else 0
    avg_daily_runs = round(total / unique_days) if unique_days > 0 else 0
    daily_user_counts = raw_df.groupby(raw_df[rcols['gameDate']].apply(day_key))[rcols['userId']].nunique() if (rcols['gameDate'] and rcols['userId']) else pd.Series([], dtype=int)
    avg_daily_users = round(daily_user_counts.mean()) if len(daily_user_counts) else 0

    game_counts = raw_df[rcols['gameName']].value_counts().to_dict() if rcols['gameName'] else {}
    game_points = {}
    if rcols['gameName'] and rcols['points']:
        for g, grp in raw_df.groupby(rcols['gameName']):
            pts = grp[rcols['points']].apply(lambda v: int(float(str(v).replace(',', ''))) if v and str(v).strip() not in ('', 'nan') else 0)
            game_points[g] = int(pts.iloc[0]) if len(pts) else 0

    game_prize_counts, amountGameMap = {}, {}
    if rcols['gameName'] and rcols['prizeName']:
        for _, row in raw_df.iterrows():
            g = row.get(rcols['gameName'], '')
            p = str(row.get(rcols['prizeName'], '')).strip()
            if not p or p == 'nan': continue
            if g not in game_prize_counts: game_prize_counts[g] = {}
            game_prize_counts[g][p] = game_prize_counts[g].get(p, 0) + 1
            if '할인쿠폰' in p:
                amt = extract_amount(p)
                if amt: amountGameMap[amt] = g

    txToGame, txToPrize = {}, {}
    if rcols['txId'] and rcols['gameName']:
        for _, row in raw_df.iterrows():
            tx = str(row.get(rcols['txId'], '')).strip()
            if tx and tx != 'nan':
                txToGame[tx] = str(row.get(rcols['gameName'], ''))
                txToPrize[tx] = str(row.get(rcols['prizeName'], '') or '')

    monthly = {}
    if rcols['gameDate']:
        for _, row in raw_df.iterrows():
            mk = fmt_month(row.get(rcols['gameDate'], ''))
            if not mk: continue
            if mk not in monthly: monthly[mk] = {'total': 0, 'users': set(), 'points': 0, 'done': 0}
            monthly[mk]['total'] += 1
            uid = str(row.get(rcols['userId'], ''))
            if uid and uid != 'nan': monthly[mk]['users'].add(uid)
            pts = row.get(rcols['points'], 0)
            monthly[mk]['points'] += int(float(str(pts).replace(',', ''))) if pts and str(pts).strip() not in ('', 'nan') else 0
            if rcols['prizeStatus'] and str(row.get(rcols['prizeStatus'], '')) == '완료': monthly[mk]['done'] += 1

    prize_usage = compute_prize_usage(prize_df, pcols, txToGame, txToPrize) if prize_df is not None else {}
    coupon_stats = compute_coupon_stats(coupon_df, ccols, amountGameMap) if coupon_df is not None else {}

    if prize_df is not None and pcols.get('mms') and pcols.get('price'):
        mms_col = pcols['mms']
        price_col = pcols['price']
        mms_filled = prize_df[mms_col].astype(str).str.strip().replace('nan','')
        non_empty = mms_filled[mms_filled != '']
        print(f'  [경품진단] 전체:{len(prize_df)}행 / MMS발송일있음:{len(non_empty)}행 / 없음:{len(prize_df)-len(non_empty)}행')
        if len(non_empty) > 0:
            sample_val = non_empty.iloc[0]
            print(f'  [경품진단] MMS발송일 샘플: "{sample_val}" → parse: {parse_datetime(sample_val)}')
            sample_price = str(prize_df[price_col].iloc[non_empty.index[0]]).replace(',','')
            print(f'  [경품진단] 공급가격 샘플: "{prize_df[price_col].iloc[non_empty.index[0]]}"')
        else:
            print(f'  [경품진단] ⚠️ MMS발송일이 전부 비어있음 → 경품총액 0원 원인')

    print('\n[3/5] 경품코드 마스터 읽기...')
    master_df = read_sheet(service, '경품코드 마스터')
    vendor_map, face_map, fee_map = {}, {}, {}
    if not master_df.empty:
        col_mn = find_col(master_df, '경품명')
        col_mv = find_col(master_df, '교환처')
        col_mf = find_col(master_df, '면가')
        col_mfee = find_col(master_df, '수수료율')
        for _, row in master_df.iterrows():
            pn = str(row.get(col_mn, '')).strip() if col_mn else ''
            if not pn or pn == 'nan': continue
            if col_mv:
                v = str(row.get(col_mv, '')).strip()
                if v and v != 'nan': vendor_map[pn] = v
            if col_mf:
                try: face_map[pn] = float(str(row.get(col_mf, 0)).replace(',', '') or 0)
                except Exception: pass
            if col_mfee:
                try:
                    raw_fee = float(str(row.get(col_mfee, 0)).replace(',', '').replace('%', '') or 0)
                    fee_map[pn] = raw_fee / 1.1  # VAT 제외 환산
                except Exception: pass

    daily_stats = compute_daily_stats(raw_df, rcols, coupon_df, ccols, prize_df, pcols,
                                      txToPrize=txToPrize, face_map=face_map)

    print('\n[4/5] 구글 시트 기록...')

    def fmt_date(d): return d.strftime('%Y-%m-%d') if d and hasattr(d, 'strftime') else str(d or '')

    write_sheet(service, '집계_누적', [
        ['총실행수','유니크참여자','총소진포인트','경품완료','경품실패','데이터시작','데이터종료','일평균실행','일평균참여자'],
        [total, unique_users, int(total_points), prize_done, prize_fail, fmt_date(min_date), fmt_date(max_date), avg_daily_runs, avg_daily_users]
    ])
    print('  집계_누적 완료')

    game_rows = [['게임명','실행수','포인트P']]
    for g, cnt in sorted(game_counts.items(), key=lambda x: -x[1]): game_rows.append([g, cnt, game_points.get(g, '')])
    write_sheet(service, '집계_게임별', game_rows)
    print('  집계_게임별 완료')

    game_daily_cnt = {}
    if rcols['gameName'] and rcols['gameDate']:
        for _, row in raw_df.iterrows():
            dk = day_key(row.get(rcols['gameDate'], ''))
            gn = str(row.get(rcols['gameName'], '')).strip()
            if dk and gn and gn != 'nan':
                game_daily_cnt.setdefault(dk, {})
                game_daily_cnt[dk][gn] = game_daily_cnt[dk].get(gn, 0) + 1
    gd_rows = [['날짜', '게임명', '실행수']]
    for dk in sorted(game_daily_cnt.keys()):
        for gn, cnt in sorted(game_daily_cnt[dk].items()):
            gd_rows.append([dk, gn, cnt])
    write_sheet(service, '집계_게임_일별', gd_rows)
    print('  집계_게임_일별 완료')

    gp_rows = [['게임명','경품명','발행수']]
    for g, prizes in sorted(game_prize_counts.items()):
        for p, cnt in sorted(prizes.items(), key=lambda x: -x[1]): gp_rows.append([g, p, cnt])
    write_sheet(service, '집계_게임경품', gp_rows)
    print('  집계_게임경품 완료')

    pu_rows = [['게임명','경품명','교환처','발행수','사용수','만료수']]
    for g in sorted(prize_usage.keys()):
        for p in sorted(prize_usage[g].keys()):
            d = prize_usage[g][p]
            pu_rows.append([g, p, vendor_map.get(p,''), d['issued'], d['used'], d['expired']])
    write_sheet(service, '집계_경품사용', pu_rows)
    print('  집계_경품사용 완료')

    coupon_rows = [['쿠폰명','게임명','발행수','사용수']]
    for name in sorted(coupon_stats.keys()): coupon_rows.append([name, coupon_stats[name]['game'], coupon_stats[name]['issued'], coupon_stats[name]['used']])
    write_sheet(service, '집계_쿠폰', coupon_rows)
    print('  집계_쿠폰 완료')

    month_rows = [['월','실행수','유니크참여자','소진포인트','경품완료']]
    for mk in sorted(monthly.keys()): month_rows.append([mk, monthly[mk]['total'], len(monthly[mk]['users']), int(monthly[mk]['points']), monthly[mk]['done']])
    write_sheet(service, '집계_월별', month_rows)
    print('  집계_월별 완료')

    day_rows = [['날짜','요일','소진포인트','총혜택금액','할인쿠폰발행','할인쿠폰총액','경품발행','경품총액']]
    for dk in sorted(daily_stats.keys()):
        d = daily_stats[dk]
        ca = d.get('couponAmt', 0); pa = d.get('prizeAmt', 0)
        day_rows.append([dk, weekday_kr(dk), int(d.get('points',0)), int(ca+pa), d.get('couponCnt',0), int(ca), d.get('prizeCnt',0), int(pa)])
    write_sheet(service, '집계_일별', day_rows)
    print('  집계_일별 완료')

    # 유저 목록 저장 (전체 unique 추적용)
    user_rows = [['유저ID']] + [[u] for u in sorted(users)]
    write_sheet(service, '집계_유저', user_rows)
    print('  집계_유저 완료')

    # 월별 유저 저장 (월별 unique 추적용)
    mu_rows = [['월', '유저ID']]
    for mk in sorted(monthly.keys()):
        for uid in sorted(monthly[mk]['users']): mu_rows.append([mk, uid])
    write_sheet(service, '집계_유저_월별', mu_rows)
    print('  집계_유저_월별 완료')

    # 게임별 월별 참여자/실행수 저장
    gm_user_map = {}
    gm_run_map = {}
    if rcols['gameName'] and rcols['gameDate']:
        for _, row in raw_df.iterrows():
            g  = str(row.get(rcols['gameName'], '')).strip()
            mk = fmt_month(row.get(rcols['gameDate'], ''))
            if not g or g == 'nan' or not mk: continue
            if g not in gm_run_map: gm_run_map[g] = {}
            gm_run_map[g][mk] = gm_run_map[g].get(mk, 0) + 1
            if rcols['userId']:
                u = str(row.get(rcols['userId'], '')).strip()
                if u and u != 'nan':
                    if g not in gm_user_map: gm_user_map[g] = {}
                    if mk not in gm_user_map[g]: gm_user_map[g][mk] = set()
                    gm_user_map[g][mk].add(u)
    all_games = sorted(set(list(gm_user_map.keys()) + list(gm_run_map.keys())))
    gm_rows = [['게임명', '월', '참여자수', '실행수']]
    for g in all_games:
        all_months = sorted(set(list(gm_user_map.get(g, {}).keys()) + list(gm_run_map.get(g, {}).keys())))
        for mk in all_months:
            participants = len(gm_user_map.get(g, {}).get(mk, set()))
            runs = gm_run_map.get(g, {}).get(mk, 0)
            gm_rows.append([g, mk, participants, runs])
    write_sheet(service, '집계_게임_월별', gm_rows)
    print('  집계_게임_월별 완료')

    print('\n[4.5/5] 수익률 산출 탭 작성...')
    prize_monthly, coupon_monthly = compute_monthly_data(
        raw_df, rcols, coupon_df, ccols, prize_df, pcols,
        txToGame, txToPrize, amountGameMap)
    save_monthly_raw(service, prize_monthly, coupon_monthly)
    build_revenue_sheets(service, prize_monthly, coupon_monthly,
                         game_points, face_map, fee_map, vendor_map)
    write_internal_report(service)
    write_external_report(service)

    prize_total = sum(v.get('prizeAmt', 0) for v in daily_stats.values())
    print(f'\n[5/5] 처리 결과:')
    print(f'  총실행수: {total:,} / 유니크참여자: {unique_users:,} / 소진포인트: {int(total_points):,}')
    print(f'  경품완료: {prize_done:,} / 일수: {len(daily_stats)} / 월수: {len(monthly)}')
    print(f'  경품총액 합계: {prize_total:,.0f}원  ← 0이면 매체사경품 파일 미제공 또는 컬럼 오류')
    print(f'  prize_df 있음: {prize_df is not None} / MMS컬럼: {pcols.get("mms")} / 가격컬럼: {pcols.get("price")}')


def run_append(raw_df, rcols, coupon_df, ccols, prize_df, pcols, service):
    print('\n[2/5] 기존 집계 데이터 읽기...')
    existing_daily = read_sheet(service, '집계_일별')
    existing_dates = set(existing_daily['날짜'].tolist()) if not existing_daily.empty and '날짜' in existing_daily.columns else set()
    existing_gd = read_sheet(service, '집계_게임_일별')
    existing_gd_dates = set(existing_gd['날짜'].tolist()) if not existing_gd.empty and '날짜' in existing_gd.columns else set()
    existing_users = read_set(service, '집계_유저')

    existing_mu_df = read_sheet(service, '집계_유저_월별')
    existing_mu = {}
    if not existing_mu_df.empty and len(existing_mu_df.columns) >= 2:
        for _, row in existing_mu_df.iterrows():
            mk, uid = str(row.iloc[0]).strip(), str(row.iloc[1]).strip()
            if mk not in existing_mu: existing_mu[mk] = set()
            existing_mu[mk].add(uid)

    # 날짜 필터: 이미 처리된 날짜 제외
    if rcols['gameDate']:
        raw_df = raw_df.copy()
        raw_df['_date'] = raw_df[rcols['gameDate']].apply(day_key)
        raw_df = raw_df[~raw_df['_date'].isin(existing_dates)]

    if raw_df.empty:
        print('  새로 처리할 날짜가 없습니다. 수익률 탭만 재생성합니다.')
        master_df = read_sheet(service, '경품코드 마스터')
        vendor_map_e, face_map_e, fee_map_e = {}, {}, {}
        if not master_df.empty:
            cmn = find_col(master_df, '경품명'); cmv = find_col(master_df, '교환처')
            cmf = find_col(master_df, '면가'); cmfee = find_col(master_df, '수수료율')
            for _, row in master_df.iterrows():
                pn = str(row.get(cmn, '')).strip() if cmn else ''
                if not pn or pn == 'nan': continue
                if cmv:
                    v = str(row.get(cmv, '')).strip()
                    if v and v != 'nan': vendor_map_e[pn] = v
                if cmf:
                    try: face_map_e[pn] = float(str(row.get(cmf, 0)).replace(',', '') or 0)
                    except Exception: pass
                if cmfee:
                    try:
                        raw_fee = float(str(row.get(cmfee, 0)).replace(',', '').replace('%', '') or 0)
                        fee_map_e[pn] = raw_fee / 1.1
                    except Exception: pass
        game_points_e = {}
        gp_df_e = read_sheet(service, '집계_게임별')
        if not gp_df_e.empty and '게임명' in gp_df_e.columns:
            for _, row in gp_df_e.iterrows():
                g = str(row.get('게임명', ''))
                try: game_points_e[g] = int(str(row.get('포인트P', 0) or 0))
                except Exception: pass
        hist_pm, hist_cm = load_monthly_raw(service)
        build_revenue_sheets(service, hist_pm, hist_cm, game_points_e, face_map_e, fee_map_e, vendor_map_e)
        write_internal_report(service)
        write_external_report(service)
        print('  수익률 탭 재생성 완료')
        return

    new_dates = sorted(raw_df['_date'].dropna().unique().tolist()) if '_date' in raw_df.columns else []
    print(f'  새 날짜: {new_dates}')

    print('\n[3/5] 증분 집계 계산...')
    total_new = len(raw_df)
    new_users, new_mu_users = set(), {}

    if rcols['userId']:
        for _, row in raw_df.iterrows():
            uid = str(row.get(rcols['userId'], '')).strip()
            mk = fmt_month(row.get(rcols['gameDate'], ''))
            if not uid or uid == 'nan': continue
            if uid not in existing_users: new_users.add(uid)
            if mk:
                if mk not in existing_mu: existing_mu[mk] = set()
                if uid not in existing_mu[mk]:
                    existing_mu[mk].add(uid)
                    if mk not in new_mu_users: new_mu_users[mk] = set()
                    new_mu_users[mk].add(uid)

    total_pts_new = raw_df[rcols['points']].apply(
        lambda v: int(float(str(v).replace(',', ''))) if v and str(v).strip() not in ('', 'nan') else 0
    ).sum() if rcols['points'] else 0
    prize_done_new = raw_df[raw_df[rcols['prizeStatus']] == '완료'].shape[0] if rcols['prizeStatus'] else 0

    # 누적 업데이트
    existing_summary = read_sheet(service, '집계_누적')
    if not existing_summary.empty:
        s = existing_summary.iloc[0]
        total_all = int(str(s.get('총실행수', 0) or 0)) + total_new
        unique_all = int(str(s.get('유니크참여자', 0) or 0)) + len(new_users)
        pts_all = int(str(s.get('총소진포인트', 0) or 0)) + int(total_pts_new)
        done_all = int(str(s.get('경품완료', 0) or 0)) + prize_done_new
        fail_all = total_all - done_all
        min_d = str(s.get('데이터시작', ''))
        max_d = new_dates[-1] if new_dates else str(s.get('데이터종료', ''))
        all_days = len(existing_dates) + len(new_dates)
        avg_runs = round(total_all / all_days) if all_days else 0
        daily_u = raw_df.groupby('_date')[rcols['userId']].nunique().mean() if (rcols['userId'] and '_date' in raw_df.columns) else 0
        existing_avg_u = float(str(s.get('일평균참여자', 0) or 0))
        avg_u = round((existing_avg_u * len(existing_dates) + daily_u * len(new_dates)) / all_days) if all_days else 0
    else:
        total_all = total_new; unique_all = len(new_users); pts_all = int(total_pts_new)
        done_all = prize_done_new; fail_all = total_all - done_all
        min_d = new_dates[0] if new_dates else ''; max_d = new_dates[-1] if new_dates else ''
        avg_runs = 0; avg_u = 0

    write_sheet(service, '집계_누적', [
        ['총실행수','유니크참여자','총소진포인트','경품완료','경품실패','데이터시작','데이터종료','일평균실행','일평균참여자'],
        [total_all, unique_all, pts_all, done_all, fail_all, min_d, max_d, avg_runs, avg_u]
    ])
    print('  집계_누적 업데이트')

    # 게임별 업데이트
    existing_game = read_sheet(service, '집계_게임별')
    game_map = {}
    if not existing_game.empty and '게임명' in existing_game.columns:
        for _, row in existing_game.iterrows():
            game_map[str(row['게임명'])] = {'cnt': int(str(row.get('실행수', 0) or 0)), 'pt': str(row.get('포인트P', ''))}
    if rcols['gameName']:
        game_pts = {}
        if rcols['points']:
            for g, grp in raw_df.groupby(rcols['gameName']):
                pts = grp[rcols['points']].apply(lambda v: int(float(str(v).replace(',', ''))) if v and str(v).strip() not in ('', 'nan') else 0)
                game_pts[g] = int(pts.iloc[0]) if len(pts) else 0
        for g, cnt in raw_df[rcols['gameName']].value_counts().items():
            if g not in game_map: game_map[g] = {'cnt': 0, 'pt': str(game_pts.get(g, ''))}
            game_map[g]['cnt'] += int(cnt)
    game_rows = [['게임명','실행수','포인트P']] + [[g, game_map[g]['cnt'], game_map[g]['pt']] for g in sorted(game_map, key=lambda x: -game_map[x]['cnt'])]
    write_sheet(service, '집계_게임별', game_rows)
    print('  집계_게임별 업데이트')

    # 게임경품 업데이트
    existing_gp = read_sheet(service, '집계_게임경품')
    gp_map = {}
    if not existing_gp.empty and '게임명' in existing_gp.columns:
        for _, row in existing_gp.iterrows():
            g, p = str(row.get('게임명','')), str(row.get('경품명',''))
            if g not in gp_map: gp_map[g] = {}
            gp_map[g][p] = int(str(row.get('발행수', 0) or 0))
    amountGameMap = {}
    if rcols['gameName'] and rcols['prizeName']:
        for _, row in raw_df.iterrows():
            g = row.get(rcols['gameName'], '')
            p = str(row.get(rcols['prizeName'], '')).strip()
            if not p or p == 'nan': continue
            if g not in gp_map: gp_map[g] = {}
            gp_map[g][p] = gp_map[g].get(p, 0) + 1
            if '할인쿠폰' in p:
                amt = extract_amount(p)
                if amt: amountGameMap[amt] = g
    gp_rows = [['게임명','경품명','발행수']]
    for g in sorted(gp_map):
        for p, cnt in sorted(gp_map[g].items(), key=lambda x: -x[1]): gp_rows.append([g, p, cnt])
    write_sheet(service, '집계_게임경품', gp_rows)
    print('  집계_게임경품 업데이트')

    face_map_u = {}
    txToGame, txToPrize = {}, {}
    if rcols['txId'] and rcols['gameName']:
        for _, row in raw_df.iterrows():
            tx = str(row.get(rcols['txId'], '')).strip()
            if tx and tx != 'nan':
                txToGame[tx] = str(row.get(rcols['gameName'], ''))
                txToPrize[tx] = str(row.get(rcols['prizeName'], '') or '')

    # 경품사용: 매체사경품은 항상 전체 재처리
    if prize_df is not None:
        new_usage = compute_prize_usage(prize_df, pcols, txToGame, txToPrize)
        if new_usage:
            existing_pu = read_sheet(service, '집계_경품사용')
            pu_map = {}
            if not existing_pu.empty and '게임명' in existing_pu.columns:
                for _, row in existing_pu.iterrows():
                    g, p = str(row.get('게임명','')), str(row.get('경품명',''))
                    if g not in pu_map: pu_map[g] = {}
                    pu_map[g][p] = {'vendor': str(row.get('교환처','')), 'issued': int(str(row.get('발행수',0) or 0)), 'used': int(str(row.get('사용수',0) or 0)), 'expired': int(str(row.get('만료수',0) or 0))}
            master_df = read_sheet(service, '경품코드 마스터')
            vendor_map, face_map_u = {}, {}
            if not master_df.empty:
                cmn = find_col(master_df, '경품명'); cmv = find_col(master_df, '교환처'); cmf = find_col(master_df, '면가')
                for _, row in master_df.iterrows():
                    pn = str(row.get(cmn,'')).strip() if cmn else ''
                    if not pn or pn == 'nan': continue
                    if cmv:
                        v = str(row.get(cmv,'')).strip()
                        if v and v != 'nan': vendor_map[pn] = v
                    if cmf:
                        try: face_map_u[pn] = float(str(row.get(cmf, 0)).replace(',','') or 0)
                        except: pass
            for g in new_usage:
                if g not in pu_map: pu_map[g] = {}
                for p, d in new_usage[g].items():
                    if p not in pu_map[g]: pu_map[g][p] = {'vendor': vendor_map.get(p,''), 'issued': 0, 'used': 0, 'expired': 0}
                    pu_map[g][p]['issued'] += d['issued']; pu_map[g][p]['used'] += d['used']; pu_map[g][p]['expired'] += d['expired']
            pu_rows = [['게임명','경품명','교환처','발행수','사용수','만료수']]
            for g in sorted(pu_map):
                for p in sorted(pu_map[g]): pu_rows.append([g, p, pu_map[g][p]['vendor'], pu_map[g][p]['issued'], pu_map[g][p]['used'], pu_map[g][p]['expired']])
            write_sheet(service, '집계_경품사용', pu_rows)
            print('  집계_경품사용 업데이트')

    # 쿠폰 업데이트
    if coupon_df is not None:
        new_coupon = compute_coupon_stats(coupon_df, ccols, amountGameMap)
        existing_c = read_sheet(service, '집계_쿠폰')
        c_map = {}
        if not existing_c.empty and '쿠폰명' in existing_c.columns:
            for _, row in existing_c.iterrows():
                nm = str(row.get('쿠폰명',''))
                c_map[nm] = {'game': str(row.get('게임명','')), 'issued': int(str(row.get('발행수',0) or 0)), 'used': int(str(row.get('사용수',0) or 0))}
        for nm, d in new_coupon.items():
            if nm not in c_map: c_map[nm] = {'game': d['game'], 'issued': 0, 'used': 0}
            c_map[nm]['issued'] += d['issued']; c_map[nm]['used'] += d['used']
        c_rows = [['쿠폰명','게임명','발행수','사용수']] + [[nm, c_map[nm]['game'], c_map[nm]['issued'], c_map[nm]['used']] for nm in sorted(c_map)]
        write_sheet(service, '집계_쿠폰', c_rows)
        print('  집계_쿠폰 업데이트')

    # 월별 업데이트
    new_monthly = {}
    if rcols['gameDate']:
        for _, row in raw_df.iterrows():
            mk = fmt_month(row.get(rcols['gameDate'], ''))
            if not mk: continue
            if mk not in new_monthly: new_monthly[mk] = {'total': 0, 'points': 0, 'done': 0}
            new_monthly[mk]['total'] += 1
            pts = row.get(rcols['points'], 0)
            new_monthly[mk]['points'] += int(float(str(pts).replace(',', ''))) if pts and str(pts).strip() not in ('', 'nan') else 0
            if rcols['prizeStatus'] and str(row.get(rcols['prizeStatus'], '')) == '완료': new_monthly[mk]['done'] += 1
    existing_m = read_sheet(service, '집계_월별')
    m_map = {}
    if not existing_m.empty and '월' in existing_m.columns:
        for _, row in existing_m.iterrows():
            mk = str(row['월'])
            m_map[mk] = {'total': int(str(row.get('실행수',0) or 0)), 'unique': int(str(row.get('유니크참여자',0) or 0)), 'points': int(str(row.get('소진포인트',0) or 0)), 'done': int(str(row.get('경품완료',0) or 0))}
    for mk, d in new_monthly.items():
        if mk not in m_map: m_map[mk] = {'total': 0, 'unique': 0, 'points': 0, 'done': 0}
        m_map[mk]['total'] += d['total']
        m_map[mk]['unique'] += len(new_mu_users.get(mk, set()))
        m_map[mk]['points'] += d['points']
        m_map[mk]['done'] += d['done']
    m_rows = [['월','실행수','유니크참여자','소진포인트','경품완료']] + [[mk, m_map[mk]['total'], m_map[mk]['unique'], m_map[mk]['points'], m_map[mk]['done']] for mk in sorted(m_map)]
    write_sheet(service, '집계_월별', m_rows)
    print('  집계_월별 업데이트')

    # 게임별 월별 참여자/실행수 업데이트
    existing_gmu = read_sheet(service, '집계_게임_월별')
    gmu_map = {}
    grun_map = {}
    if not existing_gmu.empty and '게임명' in existing_gmu.columns:
        for _, row in existing_gmu.iterrows():
            g = str(row.get('게임명', '')); mk = str(row.get('월', ''))
            if not g or not mk: continue
            if g not in gmu_map: gmu_map[g] = {}
            if g not in grun_map: grun_map[g] = {}
            gmu_map[g][mk] = int(str(row.get('참여자수', 0) or 0))
            grun_map[g][mk] = int(str(row.get('실행수', 0) or 0))
    new_gmu_sets = {}
    new_grun_map = {}
    if rcols['gameName'] and rcols['gameDate']:
        for _, row in raw_df.iterrows():
            g  = str(row.get(rcols['gameName'], '')).strip()
            mk = fmt_month(row.get(rcols['gameDate'], ''))
            if not g or g == 'nan' or not mk: continue
            if g not in new_grun_map: new_grun_map[g] = {}
            new_grun_map[g][mk] = new_grun_map[g].get(mk, 0) + 1
            if rcols['userId']:
                u = str(row.get(rcols['userId'], '')).strip()
                if u and u != 'nan':
                    if g not in new_gmu_sets: new_gmu_sets[g] = {}
                    if mk not in new_gmu_sets[g]: new_gmu_sets[g][mk] = set()
                    new_gmu_sets[g][mk].add(u)
    for g, months in new_gmu_sets.items():
        if g not in gmu_map: gmu_map[g] = {}
        for mk, users in months.items():
            gmu_map[g][mk] = gmu_map[g].get(mk, 0) + len(users)
    for g, months in new_grun_map.items():
        if g not in grun_map: grun_map[g] = {}
        for mk, cnt in months.items():
            grun_map[g][mk] = grun_map[g].get(mk, 0) + cnt
    all_games_a = sorted(set(list(gmu_map.keys()) + list(grun_map.keys())))
    gm_rows_a = [['게임명', '월', '참여자수', '실행수']]
    for g in all_games_a:
        all_months = sorted(set(list(gmu_map.get(g, {}).keys()) + list(grun_map.get(g, {}).keys())))
        for mk in all_months:
            gm_rows_a.append([g, mk, gmu_map.get(g, {}).get(mk, 0), grun_map.get(g, {}).get(mk, 0)])
    write_sheet(service, '집계_게임_월별', gm_rows_a)
    print('  집계_게임_월별 업데이트')

    # 일별 추가
    daily_stats = compute_daily_stats(raw_df, rcols, coupon_df, ccols, prize_df, pcols,
                                      txToPrize=txToPrize, face_map=face_map_u)
    new_day_rows = []
    for dk in sorted(daily_stats.keys()):
        if dk in existing_dates: continue
        d = daily_stats[dk]
        ca = d.get('couponAmt', 0); pa = d.get('prizeAmt', 0)
        new_day_rows.append([dk, weekday_kr(dk), int(d.get('points',0)), int(ca+pa), d.get('couponCnt',0), int(ca), d.get('prizeCnt',0), int(pa)])
    if new_day_rows:
        # 기존 일별 데이터 + 새 데이터 합쳐서 날짜순 정렬 후 전체 재기록
        all_day_rows = [['날짜','요일','소진포인트','총혜택금액','할인쿠폰발행','할인쿠폰총액','경품발행','경품총액']]
        if not existing_daily.empty:
            for _, row in existing_daily.iterrows():
                all_day_rows.append([row.get('날짜',''), row.get('요일',''), row.get('소진포인트',0), row.get('총혜택금액',0), row.get('할인쿠폰발행',0), row.get('할인쿠폰총액',0), row.get('경품발행',0), row.get('경품총액',0)])
        all_day_rows += new_day_rows
        all_day_rows[1:] = sorted(all_day_rows[1:], key=lambda x: str(x[0]))
        write_sheet(service, '집계_일별', all_day_rows)
        print(f'  집계_일별 {len(new_day_rows)}일 추가')

    new_gd_cnt = {}
    if rcols['gameName'] and rcols['gameDate']:
        for _, row in raw_df.iterrows():
            dk = day_key(row.get(rcols['gameDate'], ''))
            if dk in existing_gd_dates:
                continue
            gn = str(row.get(rcols['gameName'], '')).strip()
            if dk and gn and gn != 'nan':
                new_gd_cnt.setdefault(dk, {})
                new_gd_cnt[dk][gn] = new_gd_cnt[dk].get(gn, 0) + 1
    if new_gd_cnt:
        prev_gd = existing_gd.values.tolist() if not existing_gd.empty else []
        new_gd_rows = []
        for dk in sorted(new_gd_cnt.keys()):
            for gn, cnt in sorted(new_gd_cnt[dk].items()):
                new_gd_rows.append([dk, gn, cnt])
        all_gd = [['날짜', '게임명', '실행수']] + prev_gd + new_gd_rows
        write_sheet(service, '집계_게임_일별', all_gd)
        print(f'  집계_게임_일별 {len(new_gd_rows)}행 추가')

    # 유저 추가
    if new_users:
        append_rows(service, '집계_유저', [[u] for u in sorted(new_users)])
        print(f'  집계_유저 {len(new_users)}명 추가')
    if new_mu_users:
        mu_rows = []
        for mk in sorted(new_mu_users): mu_rows += [[mk, uid] for uid in sorted(new_mu_users[mk])]
        append_rows(service, '집계_유저_월별', mu_rows)
        print(f'  집계_유저_월별 업데이트')

    # ── 수익률 탭 재계산 ───────────────────────────────────────────────────────
    print('\n[4.5/5] 수익률 탭 재계산...')

    # 마스터 시트에서 face/fee/vendor 재로드
    master_df = read_sheet(service, '경품코드 마스터')
    vendor_map_a, face_map_a, fee_map_a = {}, {}, {}
    if not master_df.empty:
        cmn = find_col(master_df, '경품명')
        cmv = find_col(master_df, '교환처')
        cmf = find_col(master_df, '면가')
        cmfee = find_col(master_df, '수수료율')
        for _, row in master_df.iterrows():
            pn = str(row.get(cmn, '')).strip() if cmn else ''
            if not pn or pn == 'nan': continue
            if cmv:
                v = str(row.get(cmv, '')).strip()
                if v and v != 'nan': vendor_map_a[pn] = v
            if cmf:
                try: face_map_a[pn] = float(str(row.get(cmf, 0)).replace(',', '') or 0)
                except Exception: pass
            if cmfee:
                try:
                    raw_fee = float(str(row.get(cmfee, 0)).replace(',', '').replace('%', '') or 0)
                    fee_map_a[pn] = raw_fee / 1.1
                except Exception: pass

    # game_points: 집계_게임별 시트에서 복원
    game_points_a = {}
    gp_df = read_sheet(service, '집계_게임별')
    if not gp_df.empty and '게임명' in gp_df.columns:
        for _, row in gp_df.iterrows():
            g = str(row.get('게임명', ''))
            try: game_points_a[g] = int(str(row.get('포인트P', 0) or 0))
            except Exception: pass

    # 기존 월별 데이터 로드 + 신규 데이터 계산 + 병합
    hist_pm, hist_cm = load_monthly_raw(service)
    new_pm, new_cm = compute_monthly_data(
        raw_df, rcols, coupon_df, ccols, prize_df, pcols,
        txToGame, txToPrize, amountGameMap)
    merged_pm, merged_cm = merge_monthly(hist_pm, hist_cm, new_pm, new_cm)
    save_monthly_raw(service, merged_pm, merged_cm)
    build_revenue_sheets(service, merged_pm, merged_cm,
                         game_points_a, face_map_a, fee_map_a, vendor_map_a)
    write_internal_report(service)
    write_external_report(service)

    print(f'\n[5/5] 증분 처리 완료: {new_dates}')


def detect_file_type(path):
    """파일 헤더 컬럼으로 종류 자동 판별 → 'raw' | 'prize' | 'coupon' | None
    컬럼 인식 실패 시 파일명으로 폴백."""
    fname = os.path.basename(path)
    # 파일명 기반 힌트
    name_hint = None
    if '할인쿠폰' in fname:
        name_hint = 'coupon'
    elif '게임결과' in fname:
        name_hint = 'raw'
    elif '매체사' in fname:
        name_hint = 'prize'

    try:
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.xlsx', '.xls'):
            df = pd.read_excel(path, nrows=0, dtype=str)
        else:
            df = None
            for enc in ('cp949', 'euc-kr', 'utf-8-sig'):
                try:
                    df = pd.read_csv(path, nrows=0, encoding=enc, dtype=str)
                    break
                except Exception:
                    continue
        if df is None:
            return name_hint
        cols = ' '.join(str(c) for c in df.columns)
        # 매체사경품: B2B2C_TR_ID 또는 핀상태+공급가격
        if 'B2B2C_TR_ID' in cols or ('핀상태' in cols and '공급가격' in cols):
            return 'prize'
        # 할인쿠폰: 쿠폰명 + (핀번호|발행일자|생성일|쿠폰ID)
        if '쿠폰명' in cols and any(k in cols for k in ('핀번호', '발행일자', '생성일', '쿠폰ID')):
            return 'coupon'
        # 로우데이터: 게임명 + (게임 실행일|차감 포인트|게임결과)
        if '게임명' in cols and any(k in cols for k in ('게임 실행일', '차감 포인트', '게임결과', '게임 결과')):
            return 'raw'
        return name_hint
    except Exception:
        return name_hint


def parse_path_line(line):
    """한 줄에 여러 경로가 있을 때 분리 (드래그 시 "경로1" "경로2" 형태 처리)"""
    import shlex
    line = line.strip()
    if not line:
        return []
    try:
        parts = shlex.split(line, posix=False)
        return [p.strip('"\'') for p in parts if p.strip('"\'')]
    except Exception:
        return [line.strip('"\'')]


def classify_dropped_files(args):
    """파일 내용(헤더) 기반 자동 분류 — 파일명 무관"""
    raw_paths, coupon_paths, prize_paths, unknown = [], [], [], []
    for path in args:
        path = path.strip().strip('"\'')
        if not path or not os.path.exists(path):
            if path:
                print(f'  [무시] 파일 없음: {path}')
            continue
        name = os.path.basename(path)
        kind = detect_file_type(path)
        if kind == 'raw':
            raw_paths.append(path)
            print(f'  [로우데이터] {name}')
        elif kind == 'prize':
            prize_paths.append(path)
            print(f'  [매체사경품] {name}')
        elif kind == 'coupon':
            coupon_paths.append(path)
            print(f'  [할인쿠폰] {name}')
        else:
            unknown.append(path)
    if unknown:
        print(f'\n자동 인식 불가 파일 ({len(unknown)}개):')
        for p in unknown:
            print(f'  {os.path.basename(p)}')
            t = input('  종류 입력 (1=로우/2=매체사/3=쿠폰/엔터=무시): ').strip()
            if t == '1': raw_paths.append(p)
            elif t == '2': prize_paths.append(p)
            elif t == '3': coupon_paths.append(p)
    return raw_paths or None, coupon_paths or None, prize_paths or None


def main():
    args = sys.argv[1:]

    print('\n============================================')
    print('  IBK 게임 운영현황 보고 데이터 처리기')
    print('============================================\n')

    print('실행 모드를 선택하세요:')
    print('  1. 전체 처리 (첫 실행 또는 전체 재처리)')
    print('  2. 일별 추가 (전일 데이터 누적)')
    mode_input = input('\n선택 (1/2): ').strip()
    append_mode = (mode_input == '2')

    if args:
        # 배치 파일에 드래그한 경우 — sys.argv로 전달됨
        all_paths = args
    else:
        # 직접 실행 — 한 번에 모든 파일 드래그 또는 붙여넣기
        print('\n' + '─' * 44)
        print('  파일을 이 창에 모두 드래그하세요.')
        print('  여러 파일 동시 드래그 가능 / 완료 후 엔터')
        print('─' * 44)
        all_paths = []
        while True:
            try:
                line = input('  파일: ').strip()
            except EOFError:
                break
            if not line:
                if all_paths:
                    break
                print('  최소 1개 파일이 필요합니다.')
                continue
            all_paths.extend(parse_path_line(line))

    print(f'\n파일 {len(all_paths)}개 자동 인식 중...')
    raw_paths, coupon_paths, prize_paths = classify_dropped_files(all_paths)

    if not raw_paths:
        print('\n[오류] 로우데이터 파일을 인식하지 못했습니다. 직접 입력하세요.')
        raw_paths = ask_files('  로우데이터 엑셀:')

    print('\n[1/5] 파일 읽기...')
    raw_df, rcols = load_raw(raw_paths)
    coupon_df, ccols = load_coupon(coupon_paths) if coupon_paths else (None, {})
    prize_df, pcols  = load_prize_csv(prize_paths)  if prize_paths  else (None, {})

    service = get_service()

    if append_mode:
        run_append(raw_df, rcols, coupon_df, ccols, prize_df, pcols, service)
    else:
        run_full(raw_df, rcols, coupon_df, ccols, prize_df, pcols, service)

    print('\n✅ 완료! 구글 시트에서 [보고 생성] 버튼을 클릭하세요.')
    input('\n아무 키나 누르면 창이 닫힙니다...')

    print('\n[2/6] 집계 계산...')

    total = len(raw_df)

    users = raw_df[rcols['userId']].dropna().unique() if rcols['userId'] else []
    unique_users = len(users)

    total_points = raw_df[rcols['points']].apply(
        lambda v: int(float(str(v).replace(',', ''))) if v and str(v).strip() not in ('', 'nan') else 0
    ).sum() if rcols['points'] else 0

    prize_done = raw_df[raw_df[rcols['prizeStatus']] == '완료'].shape[0] if rcols['prizeStatus'] else 0
    prize_fail = total - prize_done

    dates = raw_df[rcols['gameDate']].apply(parse_date_val).dropna() if rcols['gameDate'] else pd.Series([], dtype=object)
    min_date = dates.min() if len(dates) else None
    max_date = dates.max() if len(dates) else None

    unique_days = dates.nunique() if len(dates) else 0
    avg_daily_runs = round(total / unique_days) if unique_days > 0 else 0

    daily_user_counts = raw_df.groupby(
        raw_df[rcols['gameDate']].apply(day_key)
    )[rcols['userId']].nunique() if (rcols['gameDate'] and rcols['userId']) else pd.Series([], dtype=int)
    avg_daily_users = round(daily_user_counts.mean()) if len(daily_user_counts) else 0

    game_counts = raw_df[rcols['gameName']].value_counts().to_dict() if rcols['gameName'] else {}
    game_points = {}
    if rcols['gameName'] and rcols['points']:
        for g, grp in raw_df.groupby(rcols['gameName']):
            pts = grp[rcols['points']].apply(
                lambda v: int(float(str(v).replace(',', ''))) if v and str(v).strip() not in ('', 'nan') else 0
            )
            game_points[g] = int(pts.iloc[0]) if len(pts) else 0

    game_prize_counts = {}
    amountGameMap = {}
    if rcols['gameName'] and rcols['prizeName']:
        for _, row in raw_df.iterrows():
            g = row.get(rcols['gameName'], '')
            p = str(row.get(rcols['prizeName'], '')).strip()
            if not p or p == 'nan':
                continue
            if g not in game_prize_counts:
                game_prize_counts[g] = {}
            game_prize_counts[g][p] = game_prize_counts[g].get(p, 0) + 1
            if '할인쿠폰' in p:
                amt = extract_amount(p)
                if amt:
                    amountGameMap[amt] = g

    txToGame = {}
    txToPrize = {}
    if rcols['txId'] and rcols['gameName']:
        for _, row in raw_df.iterrows():
            tx = str(row.get(rcols['txId'], '')).strip()
            if tx and tx != 'nan':
                txToGame[tx] = str(row.get(rcols['gameName'], ''))
                txToPrize[tx] = str(row.get(rcols['prizeName'], '') or '')

    monthly = {}
    if rcols['gameDate']:
        for _, row in raw_df.iterrows():
            mk = fmt_month(row.get(rcols['gameDate'], ''))
            if not mk:
                continue
            if mk not in monthly:
                monthly[mk] = {'total': 0, 'users': set(), 'points': 0, 'done': 0}
            monthly[mk]['total'] += 1
            uid = str(row.get(rcols['userId'], ''))
            if uid and uid != 'nan':
                monthly[mk]['users'].add(uid)
            pts = row.get(rcols['points'], 0)
            monthly[mk]['points'] += int(float(str(pts).replace(',', ''))) if pts and str(pts).strip() not in ('', 'nan') else 0
            if rcols['prizeStatus'] and str(row.get(rcols['prizeStatus'], '')) == '완료':
                monthly[mk]['done'] += 1

    prize_usage = compute_prize_usage(prize_df, pcols, txToGame, txToPrize)
    coupon_stats = compute_coupon_stats(coupon_df, ccols, amountGameMap)

    print('\n[3/6] 경품코드 마스터 읽기...')
    service = get_service()
    master_df = read_sheet(service, '경품코드 마스터')
    vendor_map, face_map_n = {}, {}
    if not master_df.empty:
        col_mn = find_col(master_df, '경품명')
        col_mv = find_col(master_df, '교환처')
        col_mf = find_col(master_df, '면가')
        for _, row in master_df.iterrows():
            pn = str(row.get(col_mn, '')).strip() if col_mn else ''
            if not pn or pn == 'nan': continue
            if col_mv:
                v = str(row.get(col_mv, '')).strip()
                if v and v != 'nan': vendor_map[pn] = v
            if col_mf:
                try: face_map_n[pn] = float(str(row.get(col_mf, 0)).replace(',', '') or 0)
                except: pass

    daily_stats = compute_daily_stats(raw_df, rcols, coupon_df, ccols, prize_df, pcols,
                                      txToPrize=txToPrize, face_map=face_map_n)

    print('\n[4/6] 시트 쓰기...')

    def fmt_date(d):
        if d is None:
            return ''
        return d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)

    print('  집계_누적...')
    accum_data = [
        ['총실행수', '유니크참여자', '총소진포인트', '경품완료', '경품실패',
         '데이터시작', '데이터종료', '일평균실행', '일평균참여자'],
        [total, unique_users, int(total_points), prize_done, prize_fail,
         fmt_date(min_date), fmt_date(max_date), avg_daily_runs, avg_daily_users]
    ]
    write_sheet(service, '집계_누적', accum_data)



if __name__ == '__main__':
    main()
