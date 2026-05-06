from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES   = ['https://www.googleapis.com/auth/spreadsheets']
KEY_FILE = r'C:/Users/jihye/.claude/google-sheets-key.json'
SS_ID    = '1fnpOeYElebxh1K74mtoFyQXvb1Rhq6AxKURqh6e8pHc'
SHEET    = '제세공과금 부과'
GID      = 2046097687

creds = service_account.Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
svc   = build('sheets', 'v4', credentials=creds)

CLIENT = '농협중앙회 사내 경진대회'
DATE   = '2026년 04월 16일'
items = [
    {'name': '애플 맥북네오 6코어 CPU / RAM 8GB / SSD 256GB', 'price': 990000,  'qty': 2, 'tax': 217800},
    {'name': '아이패드 미니 Wi-Fi 128GB',                      'price': 749000,  'qty': 6, 'tax': 164780},
    {'name': '소니 WH-1000XM6',                               'price': 619000,  'qty': 8, 'tax': 136180},
    {'name': '로지텍 MX Mechanical 갈축',                      'price': 240000,  'qty': 8, 'tax':  52800},
]
total_supply = sum(i['price'] * i['qty'] for i in items)
total_tax    = sum(i['tax'] for i in items)
total_bill   = total_supply + total_tax

def rgb(r, g, b):
    return {'red': r/255, 'green': g/255, 'blue': b/255}

def border_side(style='SOLID', width=1, color=(0,0,0)):
    return {'style': style, 'width': width, 'color': rgb(*color)}

SOLID = border_side()
THICK = border_side('SOLID', 2)
ALL_BORDERS  = {'top': SOLID, 'bottom': SOLID, 'left': SOLID, 'right': SOLID}
THICK_BORDER = {'top': THICK, 'bottom': THICK, 'left': THICK, 'right': THICK}

def merge(r1, c1, r2, c2):
    return {'mergeCells': {'range': {'sheetId': GID,
        'startRowIndex': r1, 'endRowIndex': r2,
        'startColumnIndex': c1, 'endColumnIndex': c2},
        'mergeType': 'MERGE_ALL'}}

def fmt_req(r1, c1, r2, c2, bg=None, bold=False, size=9, align='CENTER',
            valign='MIDDLE', borders=None, wrap='OVERFLOW_CELL', fg=None):
    f = {}
    if bg:  f['backgroundColor'] = rgb(*bg)
    if borders: f['borders'] = borders
    tf = {'bold': bold, 'fontSize': size}
    if fg: tf['foregroundColor'] = rgb(*fg)
    f['textFormat'] = tf
    f['horizontalAlignment'] = align
    f['verticalAlignment']   = valign
    f['wrapStrategy'] = wrap
    return {'repeatCell': {
        'range': {'sheetId': GID, 'startRowIndex': r1, 'endRowIndex': r2,
                  'startColumnIndex': c1, 'endColumnIndex': c2},
        'cell': {'userEnteredFormat': f},
        'fields': 'userEnteredFormat'
    }}

def set_val(r, c, val, num=False):
    v = {'numberValue': val} if num else {'stringValue': str(val)}
    return {'updateCells': {
        'rows': [{'values': [{'userEnteredValue': v}]}],
        'fields': 'userEnteredValue',
        'start': {'sheetId': GID, 'rowIndex': r, 'columnIndex': c}
    }}

def set_formula(r, c, formula):
    return {'updateCells': {
        'rows': [{'values': [{'userEnteredValue': {'formulaValue': formula}}]}],
        'fields': 'userEnteredValue',
        'start': {'sheetId': GID, 'rowIndex': r, 'columnIndex': c}
    }}

def num_fmt_req(r, c, pattern='#,##0'):
    return {'repeatCell': {
        'range': {'sheetId': GID, 'startRowIndex': r, 'endRowIndex': r+1,
                  'startColumnIndex': c, 'endColumnIndex': c+1},
        'cell': {'userEnteredFormat': {'numberFormat': {'type': 'NUMBER', 'pattern': pattern}}},
        'fields': 'userEnteredFormat.numberFormat'
    }}

# 열 인덱스 (0-based)
B,C,D,E,F   = 1,2,3,4,5
G,H,I,J,K,L = 6,7,8,9,10,11
M            = 12
N,O          = 13,14
P            = 15
Q,R,S        = 16,17,18
T,U,V,W,X   = 19,20,21,22,23
Y,Z,AA       = 24,25,26
AB           = 27

BLUE  = (24, 95, 165)
GREEN = (29, 158, 117)
LGRAY = (242, 242, 242)
WHITE = (255, 255, 255)
LBLU  = (248, 252, 255)
LYEL  = (255, 252, 240)
LGRN  = (225, 245, 238)
LLBL  = (230, 230, 230)

tax_r   = 10 + len(items)   # 제세공과금 행 (0-based)
sum_r   = tax_r + 1          # 합계 행
blank_r = sum_r + 1          # 빈 행
final_r = blank_r + 1        # 최종합계 행
note_r  = final_r + 1        # 안내문구 시작

reqs = []

# 0) 시트 크기 확장 (AB열=28열 필요)
reqs.append({'updateSheetProperties': {
    'properties': {'sheetId': GID, 'gridProperties': {'rowCount': 100, 'columnCount': 28}},
    'fields': 'gridProperties.rowCount,gridProperties.columnCount'
}})

# 1) 클리어
reqs.append({'updateCells': {'range': {'sheetId': GID}, 'fields': 'userEnteredValue,userEnteredFormat'}})

# 2) 열 너비
col_widths = {0:8, 1:40,2:40,3:40,4:40,5:40, 6:45,7:45,8:45,9:45,10:45,11:45,
              12:80, 13:40,14:40, 15:50, 16:65,17:65,18:65,
              19:65,20:65,21:65,22:65,23:65, 24:50,25:50,26:50, 27:90}
for ci, px in col_widths.items():
    reqs.append({'updateDimensionProperties': {
        'range': {'sheetId': GID, 'dimension': 'COLUMNS', 'startIndex': ci, 'endIndex': ci+1},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}})

# 3) 행 높이
for ri, px in {0:8,1:35,2:20,3:20,4:20,5:20,6:20,7:20,8:20,9:24}.items():
    reqs.append({'updateDimensionProperties': {
        'range': {'sheetId': GID, 'dimension': 'ROWS', 'startIndex': ri, 'endIndex': ri+1},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}})
for ri in range(10, final_r + 3):
    reqs.append({'updateDimensionProperties': {
        'range': {'sheetId': GID, 'dimension': 'ROWS', 'startIndex': ri, 'endIndex': ri+1},
        'properties': {'pixelSize': 22}, 'fields': 'pixelSize'}})

# 4) 병합
reqs.append(merge(1, B, 4, AB+1))       # 제목 B2:AB4
reqs.append(merge(4, B, 9, L+1))        # 날짜/인사 B5:L9
reqs.append(merge(4, M, 9, N+1))        # 공급자 M5:N9
reqs.append(merge(4, O, 5, R+1))        # O5:R5
reqs.append(merge(4, S, 5, AB+1))       # S5:AB5
reqs.append(merge(5, O, 6, R+1))
reqs.append(merge(5, S, 6, V+1))
reqs.append(merge(5, W, 6, X+1))
reqs.append(merge(5, Y, 6, AB+1))
reqs.append(merge(6, O, 7, R+1))
reqs.append(merge(6, S, 7, AB+1))
reqs.append(merge(7, O, 8, R+1))
reqs.append(merge(7, S, 8, V+1))
reqs.append(merge(7, W, 8, X+1))
reqs.append(merge(7, Y, 8, AB+1))
reqs.append(merge(8, O, 9, R+1))
reqs.append(merge(8, S, 9, AB+1))
reqs.append(merge(9, B, 10, L+1))       # 헤더 상품명
reqs.append(merge(9, N, 10, O+1))
reqs.append(merge(9, Q, 10, S+1))
reqs.append(merge(9, T, 10, X+1))
reqs.append(merge(9, Y, 10, AA+1))
for i in range(len(items) + 1):         # 데이터 + 제세공과금
    r = 10 + i
    reqs.append(merge(r, B, r+1, F+1))
    reqs.append(merge(r, G, r+1, L+1))
    reqs.append(merge(r, N, r+1, O+1))
    reqs.append(merge(r, Q, r+1, S+1))
    reqs.append(merge(r, T, r+1, X+1))
    reqs.append(merge(r, Y, r+1, AA+1))
reqs.append(merge(sum_r, B, sum_r+1, L+1))
reqs.append(merge(sum_r, N, sum_r+1, O+1))
reqs.append(merge(sum_r, Q, sum_r+1, S+1))
reqs.append(merge(sum_r, T, sum_r+1, X+1))
reqs.append(merge(sum_r, Y, sum_r+1, AA+1))
reqs.append(merge(blank_r, B, blank_r+1, AB+1))
reqs.append(merge(final_r, B, final_r+1, L+1))
reqs.append(merge(final_r, M, final_r+1, X+1))
reqs.append(merge(final_r, Y, final_r+1, AB+1))

# 5) 서식
reqs.append(fmt_req(1, B, 4, AB+1, bg=BLUE, bold=True, size=16, fg=WHITE))
reqs.append(fmt_req(4, B, 9, L+1,  bg=WHITE, align='LEFT', valign='MIDDLE', wrap='WRAP', size=10))
reqs.append(fmt_req(4, M, 9, N+1,  bg=LGRAY, bold=True, size=9, align='CENTER', wrap='WRAP'))
for ri in range(4, 9):
    reqs.append(fmt_req(ri, O, ri+1, R+1,  bg=LLBL, bold=True, size=9, borders=ALL_BORDERS))
    reqs.append(fmt_req(ri, S, ri+1, AB+1, bg=WHITE, size=9, align='LEFT', borders=ALL_BORDERS))
    if ri == 5:
        reqs.append(fmt_req(ri, W, ri+1, X+1,  bg=LLBL, bold=True, size=9, borders=ALL_BORDERS))
        reqs.append(fmt_req(ri, Y, ri+1, AB+1, bg=WHITE, size=9, align='LEFT', borders=ALL_BORDERS))
    if ri == 7:
        reqs.append(fmt_req(ri, W, ri+1, X+1,  bg=LLBL, bold=True, size=9, borders=ALL_BORDERS))
        reqs.append(fmt_req(ri, Y, ri+1, AB+1, bg=WHITE, size=9, align='LEFT', borders=ALL_BORDERS))
reqs.append(fmt_req(9, B, 10, AB+1, bg=BLUE, bold=True, size=9, fg=WHITE, borders=ALL_BORDERS))
for i in range(len(items)):
    r = 10 + i
    alt = LBLU if i % 2 == 0 else WHITE
    reqs.append(fmt_req(r, B, r+1, AB+1, bg=alt, size=9, borders=ALL_BORDERS))
    reqs.append(fmt_req(r, G, r+1, L+1,  bg=alt, size=9, align='LEFT', borders=ALL_BORDERS))
reqs.append(fmt_req(tax_r, B, tax_r+1, AB+1, bg=LYEL, size=9, borders=ALL_BORDERS))
reqs.append(fmt_req(tax_r, G, tax_r+1, L+1,  bg=LYEL, size=9, align='LEFT', borders=ALL_BORDERS))
reqs.append(fmt_req(sum_r, B, sum_r+1, AB+1, bg=LGRAY, bold=True, size=9, borders=ALL_BORDERS))
reqs.append(fmt_req(blank_r, B, blank_r+1, AB+1, bg=WHITE))
reqs.append(fmt_req(final_r, B, final_r+1, L+1,  bg=LGRN, bold=True, size=10, borders=THICK_BORDER))
reqs.append(fmt_req(final_r, M, final_r+1, X+1,  bg=LGRN, bold=True, size=12, borders=THICK_BORDER))
reqs.append(fmt_req(final_r, Y, final_r+1, AB+1, bg=LGRN, bold=True, size=9,  borders=THICK_BORDER))

# 숫자 서식
for ri in range(10, tax_r + 1):
    for ci in [M, Q, T]:
        reqs.append(num_fmt_req(ri, ci))
for ri in [sum_r, final_r]:
    for ci in [N, T, M]:
        reqs.append(num_fmt_req(ri, ci))

svc.spreadsheets().batchUpdate(spreadsheetId=SS_ID, body={'requests': reqs}).execute()
print('서식 완료')

# 6) 값 입력
vals = []
vals.append(set_val(4, B, f'{DATE}\n\n{CLIENT} 귀중\n\n아래와 같이 견적합니다.'))
vals.append(set_val(4, O,  '등록번호'))
vals.append(set_val(4, S,  '214-88-78503'))
vals.append(set_val(5, O,  '상호 (법인명)'))
vals.append(set_val(5, S,  '㈜ 윈큐브마케팅'))
vals.append(set_val(5, W,  '대표자'))
vals.append(set_val(5, Y,  '김 성 필'))
vals.append(set_val(6, O,  '사 업 장'))
vals.append(set_val(6, S,  '서울시 서초구 방배로 42길 61, 4층'))
vals.append(set_val(7, O,  '업  태'))
vals.append(set_val(7, S,  '서비스'))
vals.append(set_val(7, W,  '종목'))
vals.append(set_val(7, Y,  '상품권 및 쿠폰발행유통 외'))
vals.append(set_val(8, O,  '전화번호'))
vals.append(set_val(8, S,  '010-6587-3655'))
vals.append(set_val(9, B,  '상     품     명'))
vals.append(set_val(9, M,  '정상가'))
vals.append(set_val(9, N,  '수량'))
vals.append(set_val(9, P,  '할인율'))
vals.append(set_val(9, Q,  '할인 적용 단가'))
vals.append(set_val(9, T,  '할인 적용 합계'))
vals.append(set_val(9, Y,  '부가세'))
vals.append(set_val(9, AB, '비고'))

for i, item in enumerate(items):
    r = 10 + i
    rn = r + 1  # 1-based row number
    vals.append(set_val(r, B,  '-'))
    vals.append(set_val(r, G,  item['name']))
    vals.append(set_val(r, M,  item['price'], num=True))
    vals.append(set_val(r, N,  item['qty'], num=True))
    vals.append(set_val(r, P,  0, num=True))
    vals.append(set_formula(r, Q, f'=M{rn}'))
    vals.append(set_formula(r, T, f'=N{rn}*Q{rn}'))
    vals.append(set_val(r, Y,  '포함'))

vals.append(set_val(tax_r, B,  '-'))
vals.append(set_val(tax_r, G,  '제세공과금'))
vals.append(set_val(tax_r, M,  '-'))
vals.append(set_val(tax_r, N,  '-'))
vals.append(set_val(tax_r, P,  '-'))
vals.append(set_val(tax_r, Q,  '-'))
vals.append(set_val(tax_r, T,  total_tax, num=True))
vals.append(set_val(tax_r, Y,  '-'))
vals.append(set_val(tax_r, AB, '각 상품 금액의 22%'))

t_start = 11
t_end   = 10 + len(items)
vals.append(set_val(sum_r, B, '합계'))
vals.append(set_formula(sum_r, N, f'=SUM(N{t_start}:N{t_end})'))
vals.append(set_formula(sum_r, T, f'=SUM(T{t_start}:T{tax_r+1})'))

vals.append(set_val(final_r, B, '합   계'))
vals.append(set_val(final_r, M, total_bill, num=True))

vals.append(set_val(note_r,   B, '1. 견적유효 : 견적 제출일로부터 1개월'))
vals.append(set_val(note_r+1, B, '2. 검사조건 : 출고검사 / 유효기간 내 재발송 가능 / CS업무'))
vals.append(set_val(note_r+2, B, '3. 제세공과금은 각 상품 금액의 22%이며 당사에서 대행 신고합니다.'))

svc.spreadsheets().batchUpdate(spreadsheetId=SS_ID, body={'requests': vals}).execute()
print('값 입력 완료')
print(f'공급가액 합계: {total_supply:,}')
print(f'제세공과금:    {total_tax:,}')
print(f'총 청구액:     {total_bill:,}')
