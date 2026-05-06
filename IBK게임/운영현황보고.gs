// IBK 게임 운영현황 보고서
// 시트 구성: 로우데이터 / 할인쿠폰 / 매체사 경품 / 경품코드 마스터 / 외부보고 / 내부보고 / 누적현황 / 일별현황

var C = {
  T_BG:  '#DBEAFE',  // 타이틀 배경 (연한 파란)
  T_FG:  '#1E3A5F',  // 타이틀 텍스트 (진한 네이비)
  S_BG:  '#BFDBFE',  // 섹션 헤더 배경
  S_FG:  '#1E3A5F',  // 섹션 텍스트
  CH_BG: '#EFF6FF',  // 컬럼 헤더 배경 (아주 연한)
  CH_FG: '#1E3A5F',  // 컬럼 헤더 텍스트
  GS_BG: '#F0F9FF',  // 게임 서브헤더 배경
  GS_FG: '#1E3A5F',
  TOT_BG:'#DBEAFE',  // 합계 행 배경
  TOT_FG:'#1E3A5F',  // 합계 행 텍스트
  WHITE: '#FFFFFF',
  BLACK: '#000000',
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('📊 IBK 보고')
    .addItem('① 시트 초기 설정', 'setupSheets')
    .addSeparator()
    .addItem('② 보고 생성', 'generateReport')
    .addSeparator()
    .addItem('③ 오류 보고 시트 생성', 'buildErrorReport')
    .addItem('④ 오류 메일 초안 생성', 'createErrorDrafts')
    .addToUi();
}

// ══════════════════════════════════════════════════
// 시트 초기 설정
// ══════════════════════════════════════════════════
function setupSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  if (!ss.getSheetByName('로우데이터')) ss.insertSheet('로우데이터');

  if (!ss.getSheetByName('할인쿠폰')) {
    var cs = ss.insertSheet('할인쿠폰');
    var ch = ['일련번호','매체사','유저ID','쿠폰명','상품코드','상품명','주문번호','쿠폰코드','상태','VIEW','유효일','유효기간시작일','유효기간종료일','발행일자','발행시각','소멸자','사용시각'];
    cs.getRange(1, 1, 1, ch.length).setValues([ch])
      .setBackground(C.T_BG).setFontColor(C.T_FG).setFontWeight('bold').setFontSize(10);
    cs.setFrozenRows(1);
    cs.setColumnWidths(1, ch.length, 120);
    cs.setTabColor('#10B981');
  }

  if (!ss.getSheetByName('매체사 경품')) {
    var ps = ss.insertSheet('매체사 경품');
    var ph = ['거래번호','핀번호','캠페인명','이벤트명','상품공급사명','핀상태','발행매체명','상품명','상품수량','상품형태','교환처명','수신자번호','발송번호','공급가격','정상가격','실구매가격','MMS발송일','MMS발송시간','상품번호','B2B2C_TR_ID','유효기간','결제방법','구매번호','구매전송번호','윈큐브주문번호','실결제가격','브랜드할인금액','쿠폰할인금액','배송비'];
    ps.getRange(1, 1, 1, ph.length).setValues([ph])
      .setBackground(C.T_BG).setFontColor(C.T_FG).setFontWeight('bold').setFontSize(10);
    ps.setFrozenRows(1);
    ps.setColumnWidths(1, ph.length, 120);
    ps.setColumnWidth(8, 220);
    ps.setTabColor('#8B5CF6');
  }

  if (!ss.getSheetByName('경품코드 마스터')) {
    var ms = ss.insertSheet('경품코드 마스터');
    ms.getRange(1, 1, 1, 4).setValues([['경품코드', '경품명', '교환처', '쿠폰유형']])
      .setBackground(C.T_BG).setFontColor(C.T_FG).setFontWeight('bold').setFontSize(10);
    ms.setFrozenRows(1);
    ms.setColumnWidth(1, 320);
    ms.setColumnWidth(2, 220);
    ms.setColumnWidth(3, 150);
    ms.setColumnWidth(4, 100);
    ms.setTabColor('#F59E0B');
    populateMaster(ss, ms);
  }

  buildGuide(ss);

  SpreadsheetApp.getUi().alert(
    '✅ 시트 초기 설정 완료!\n\n' +
    '1. 로우데이터 시트에 게임결과 엑셀 붙여넣기\n' +
    '2. 할인쿠폰 시트에 할인쿠폰 발행목록 붙여넣기\n' +
    '3. 매체사 경품 시트에 매체사 CSV 붙여넣기\n' +
    '4. 경품코드 마스터에서 교환처 직접 입력\n' +
    '5. ② 보고 생성 실행'
  );
}

function buildGuide(ss) {
  var old = ss.getSheetByName('사용 가이드');
  if (old) ss.deleteSheet(old);
  var sh = ss.insertSheet('사용 가이드', ss.getSheets().length);
  sh.setTabColor('#64748B');
  sh.setColumnWidth(1, 30);
  sh.setColumnWidth(2, 200);
  sh.setColumnWidth(3, 420);
  sh.setColumnWidth(4, 30);

  var rows = [
    ['TITLE', 'IBK 게이미피케이션 보고 자동화 — 사용 가이드'],
    ['GAP'],
    ['SEC', '📋 시트 구성'],
    ['ROW', '로우데이터',     '게임 결과 원본 데이터를 붙여넣는 곳'],
    ['ROW', '할인쿠폰',       '할인쿠폰 발행 목록을 붙여넣는 곳'],
    ['ROW', '매체사 경품',     '매체사 CSV 경품 로우데이터를 붙여넣는 곳 (GAME_ 거래번호 대조)'],
    ['ROW', '경품코드 마스터','경품별 교환처를 직접 입력하는 곳'],
    ['ROW', '외부보고',       '손란대리님께 공유하는 요약 보고'],
    ['ROW', '내부보고',       '팀 내부 공유용 상세 보고 (할인쿠폰 포함)'],
    ['ROW', '누적현황',       '보고 생성할 때마다 집계 행이 자동으로 추가됨'],
    ['ROW', '일별현황',       '날짜별 포인트·쿠폰·경품 발행 집계 (보고 생성마다 갱신)'],
    ['GAP'],
    ['SEC', '🚀 사용 순서'],
    ['NUM', '①', '로우데이터 시트 A1 클릭 → 원하는 기간 데이터 전체 붙여넣기'],
    ['NUM', '②', '할인쿠폰 시트 A1 클릭 → 같은 기간 할인쿠폰 발행 목록 붙여넣기'],
    ['NUM', '③', '매체사 경품 시트 A1 클릭 → 매체사 CSV 데이터 붙여넣기'],
    ['NUM', '④', '상단 메뉴 [📊 IBK 보고] → [② 보고 생성] 클릭'],
    ['NUM', '⑤', '외부보고 / 내부보고 시트를 캡처해서 슬랙 공유'],
    ['GAP'],
    ['SEC', '📌 기간 설정 방법'],
    ['ROW', '하루치 보고',   '해당 하루 데이터만 붙여넣고 실행'],
    ['ROW', '한 달치 보고',  '한 달 전체 데이터 붙여넣고 실행'],
    ['ROW', '누적 필요 없음','붙여넣는 기간이 곧 보고 기간, 매번 덮어쓰면 됨'],
    ['GAP'],
    ['SEC', '📂 로우데이터 필수 컬럼'],
    ['ROW', '거래번호',       '중복 행 자동 제거 기준'],
    ['ROW', '사용자 ID',      '참여자 집계'],
    ['ROW', '게임명',         '게임별 통계'],
    ['ROW', '게임 실행일',    '날짜/시간 형식'],
    ['ROW', '차감 포인트',    '포인트 집계'],
    ['ROW', '게임 결과',      '"준비" 상태는 자동 제외'],
    ['ROW', '경품명 / 경품코드', '경품 통계 및 마스터 연동'],
    ['ROW', '경품 지급 상태', '"완료" 여부 집계'],
    ['GAP'],
    ['SEC', '📂 할인쿠폰 필수 컬럼'],
    ['ROW', '핀번호',   '중복 행 자동 제거 기준'],
    ['ROW', '쿠폰명',   '종류별 집계'],
    ['ROW', '상품코드', '값 있으면 사용된 것으로 처리'],
    ['GAP'],
    ['SEC', '⚙️ 경품코드 마스터 관리'],
    ['ROW', '자동 업데이트', '보고 생성 시 로우데이터의 신규 경품을 자동으로 추가'],
    ['ROW', '교환처 입력',   '마스터 시트에서 교환처 컬럼에 직접 입력 — 이후 보고에 자동 반영'],
    ['ROW', '기존 값 유지',  '교환처가 이미 입력된 경품은 덮어쓰지 않음'],
    ['GAP'],
    ['SEC', '🤖 Claude Code로 스크립트 수정하기'],
    ['NUM', '①', '[스킬 설치] ibk-gamification-report 폴더를 C:\\Users\\[내 이름]\\.claude\\skills\\ 에 넣기'],
    ['NUM', '②', '[파일 열기] Claude Code에서 운영현황보고.gs 파일이 있는 폴더 열기'],
    ['NUM', '③', '[수정 요청] 클로드에게 말로 요청 — 예: "월평균 실행 수 칸 추가해줘"'],
    ['NUM', '④', '[파일 반영] 수정된 운영현황보고.gs 파일 내용 전체 복사'],
    ['NUM', '⑤', '[붙여넣기] 구글 시트 → 확장 프로그램 → Apps Script → 기존 코드 전체 선택 후 붙여넣기 → 저장(Ctrl+S)'],
    ['NUM', '⑥', '[확인] 구글 시트로 돌아와서 ② 보고 생성 실행하여 정상 동작 확인'],
    ['GAP'],
    ['ROW', '스킬 파일 위치', 'C:\\Users\\[내 이름]\\.claude\\skills\\ibk-gamification-report\\SKILL.md'],
    ['ROW', 'gs 파일 위치',   '스킬 파일과 같은 폴더 또는 동료에게 받은 경로'],
    ['ROW', '요청 예시',      '"표 색상 바꿔줘" / "할인쿠폰 사용률 강조해줘" / "새 섹션 추가해줘"'],
    ['GAP'],
    ['SEC', '🚨 오류 보고 자동화 흐름'],
    ['NUM', '①', '[슬랙 오류 확인] ibk게이미피케이션-소통방에 오류 거래번호 메시지 올라옴'],
    ['NUM', '②', '[클로드 동기화] 클로드에게 "슬랙 오류 동기화해줘" 요청 → 오류입력 시트 자동 업데이트'],
    ['NUM', '③', '[보고 시트 생성] 메뉴 [③ 오류 보고 시트 생성] 클릭 → 오류입력 시트 읽어서 오류보고 시트 자동 생성'],
    ['NUM', '④', '[내용 검토] 오류보고 시트에서 IBK/두잇 섹션 내용 확인 및 수정'],
    ['NUM', '⑤', '[메일 초안] 메뉴 [④ 오류 메일 초안 생성] 클릭 → Gmail 임시보관함에 초안 자동 생성'],
    ['NUM', '⑥', '[발송] Gmail 임시보관함 → 수신자 이메일 입력 → 발송'],
    ['GAP'],
    ['ROW', '오류입력 시트', '클로드가 슬랙을 읽어 자동으로 채움 — 구분(IBK/두잇) / 거래번호 / 오류내용 / 발생일시'],
    ['ROW', 'IBK 보고 대상', 'IBK API 오류 전반 — 포인트 차감 실패, timeout, 보안세션 만료 등'],
    ['ROW', '두잇 보고 대상', 'COMPLETE 상태 거래에 보상 재요청 발생 등 두잇 시스템 오류'],
    ['ROW', '로우데이터 대조', '오류 거래번호를 로우데이터에서 조회해 게임명·포인트 등 자동 채움'],
  ];

  var r = 1;
  for (var i = 0; i < rows.length; i++) {
    var type = rows[i][0];
    if (type === 'TITLE') {
      sh.setRowHeight(r, 44);
      sh.getRange(r, 2, 1, 2).merge().setValue(rows[i][1])
        .setBackground(C.WHITE).setFontColor(C.T_FG)
        .setFontSize(14).setFontWeight('bold').setVerticalAlignment('middle');
    } else if (type === 'GAP') {
      sh.setRowHeight(r, 12);
    } else if (type === 'SEC') {
      sh.setRowHeight(r, 30);
      sh.getRange(r, 2, 1, 2).merge().setValue(rows[i][1])
        .setBackground(C.S_BG).setFontColor(C.S_FG)
        .setFontSize(10).setFontWeight('bold').setVerticalAlignment('middle');
    } else if (type === 'NUM') {
      sh.setRowHeight(r, 26);
      sh.getRange(r, 2).setValue(rows[i][1])
        .setBackground(C.WHITE).setFontColor(C.T_FG)
        .setFontSize(10).setFontWeight('bold').setVerticalAlignment('middle').setHorizontalAlignment('center');
      sh.getRange(r, 3).setValue(rows[i][2])
        .setBackground(C.WHITE).setFontColor(C.BLACK)
        .setFontSize(10).setVerticalAlignment('middle');
    } else if (type === 'ROW') {
      sh.setRowHeight(r, 26);
      sh.getRange(r, 2).setValue(rows[i][1])
        .setBackground(C.CH_BG).setFontColor(C.CH_FG)
        .setFontSize(9).setFontWeight('bold').setVerticalAlignment('middle');
      sh.getRange(r, 3).setValue(rows[i][2])
        .setBackground(C.WHITE).setFontColor(C.BLACK)
        .setFontSize(9).setVerticalAlignment('middle');
    }
    r++;
  }
}

function populateMaster(ss, ms) {
  var raw = ss.getSheetByName('로우데이터');
  if (!raw || raw.getLastRow() <= 1) return;
  var data = raw.getDataRange().getValues();
  var h = data[0];
  var codeIdx = h.indexOf('경품코드');
  var nameIdx = h.indexOf('경품명');
  if (codeIdx < 0) return;

  var existingVendor = {};
  if (ms.getLastRow() > 1) {
    var msData = ms.getDataRange().getValues();
    var msH = msData[0];
    var msCodeIdx = msH.indexOf('경품코드');
    var msVendorIdx = msH.indexOf('교환처');
    if (msCodeIdx >= 0 && msVendorIdx >= 0) {
      for (var i = 1; i < msData.length; i++) {
        var ec = msData[i][msCodeIdx];
        var ev = msData[i][msVendorIdx];
        if (ec && ev) existingVendor[ec] = ev;
      }
    }
  }

  var seen = {}, codeOrder = [], nameMap = {};
  for (var i = 1; i < data.length; i++) {
    var code = data[i][codeIdx];
    var name = data[i][nameIdx];
    if (code && !seen[code]) {
      seen[code] = true;
      codeOrder.push(code);
      nameMap[code] = name || '';
    }
  }
  if (!codeOrder.length) return;

  if (ms.getLastRow() > 1) ms.getRange(2, 1, ms.getLastRow() - 1, 4).clearContent();
  var rows = [];
  for (var i = 0; i < codeOrder.length; i++) {
    var code = codeOrder[i];
    var name = nameMap[code];
    var vendor = existingVendor[code] || '';
    var type = (name && String(name).indexOf('할인쿠폰') >= 0) ? '할인쿠폰' : '모바일쿠폰';
    rows.push([code, name, vendor, type]);
  }
  ms.getRange(2, 1, rows.length, 4).setValues(rows)
    .setFontSize(10).setVerticalAlignment('middle').setBackground(C.WHITE);
  ms.setRowHeights(2, rows.length, 28);
}

// ══════════════════════════════════════════════════
// 보고 생성
// ══════════════════════════════════════════════════
function generateReport() {
  try { _run(); }
  catch(e) { SpreadsheetApp.getUi().alert('오류: ' + e.message + '\n\n' + e.stack); }
}

function _run() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var rawSheet = ss.getSheetByName('로우데이터');
  if (!rawSheet) { alert_('로우데이터 시트가 없습니다.'); return; }

  var data = rawSheet.getDataRange().getValues();
  var headers = data[0];
  var idx = {
    userId:      headers.indexOf('사용자 ID'),
    gameName:    headers.indexOf('게임명'),
    gameDate:    headers.indexOf('게임 실행일'),
    points:      headers.indexOf('차감 포인트'),
    ptSt:        headers.indexOf('포인트 차감 상태'),
    gameResult:  headers.indexOf('게임 결과'),
    prizeName:   headers.indexOf('경품명'),
    prizeCode:   headers.indexOf('경품코드'),
    prizeStatus: headers.indexOf('경품 지급 상태'),
    txId:        headers.indexOf('거래번호'),
  };

  var seenTx = {}, rows = [];
  for (var i = 1; i < data.length; i++) {
    if (data[i][idx.gameResult] === '준비') continue;
    if (idx.ptSt >= 0 && data[i][idx.ptSt] === '실패') continue;
    var tx = idx.txId >= 0 ? data[i][idx.txId] : null;
    if (tx && seenTx[tx]) continue;
    if (tx) seenTx[tx] = true;
    rows.push(data[i]);
  }
  if (!rows.length) { alert_('유효한 데이터가 없습니다.'); return; }

  var total = rows.length;
  var userSet = {}, gameCounts = {}, gamePoints = {}, prizeCounts = {}, gamePrizes = {}, monthlyData = {};
  var amountGameMap = {};
  var totalPoints = 0, prizeDone = 0;

  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    userSet[r[idx.userId]] = 1;
    totalPoints += Number(r[idx.points]) || 0;
    if (r[idx.prizeStatus] === '완료') prizeDone++;

    var g = r[idx.gameName];
    gameCounts[g] = (gameCounts[g] || 0) + 1;
    if (!gamePoints[g]) gamePoints[g] = Number(r[idx.points]) || 0;

    var p = r[idx.prizeName];
    if (p) {
      prizeCounts[p] = (prizeCounts[p] || 0) + 1;
      if (!gamePrizes[g]) gamePrizes[g] = {};
      gamePrizes[g][p] = (gamePrizes[g][p] || 0) + 1;
      if (String(p).indexOf('할인쿠폰') >= 0) {
        var amt = extractAmount(String(p));
        if (amt) amountGameMap[amt] = g;
      }
    }

    var d = new Date(r[idx.gameDate]);
    var mk = d.getFullYear() + '년 ' + p2(d.getMonth() + 1) + '월';
    if (!monthlyData[mk]) monthlyData[mk] = { total: 0, users: {}, points: 0, done: 0 };
    monthlyData[mk].total++;
    monthlyData[mk].users[r[idx.userId]] = 1;
    monthlyData[mk].points += Number(r[idx.points]) || 0;
    if (r[idx.prizeStatus] === '완료') monthlyData[mk].done++;
  }

  var prizeCodeByName = {};
  for (var i = 0; i < rows.length; i++) {
    var pn = rows[i][idx.prizeName];
    var pc = idx.prizeCode >= 0 ? rows[i][idx.prizeCode] : null;
    if (pn && pc && !prizeCodeByName[pn]) prizeCodeByName[pn] = String(pc).trim();
  }

  var uniqueUsers = Object.keys(userSet).length;
  var prizeFail   = total - prizeDone;

  // 일별 통계
  var dailyRuns = {}, dailyUsers = {};
  for (var i = 0; i < rows.length; i++) {
    var dr = rows[i];
    var dd = new Date(dr[idx.gameDate]);
    var dayKey = fmtDay(dd);
    dailyRuns[dayKey] = (dailyRuns[dayKey] || 0) + 1;
    if (!dailyUsers[dayKey]) dailyUsers[dayKey] = {};
    dailyUsers[dayKey][dr[idx.userId]] = 1;
  }
  var uniqueDays = Object.keys(dailyRuns).length;
  var avgDailyRuns = uniqueDays > 0 ? Math.round(total / uniqueDays) : 0;
  var dailyUserCounts = Object.keys(dailyUsers).map(function(k) { return Object.keys(dailyUsers[k]).length; });
  var avgDailyUsers = uniqueDays > 0 ? Math.round(dailyUserCounts.reduce(function(a, b) { return a + b; }, 0) / uniqueDays) : 0;

  var gameEntries  = sortEntries(gameCounts);
  var monthEntries = Object.keys(monthlyData).sort().reverse().map(function(k) { return [k, monthlyData[k]]; });

  var gameLabel = {};
  for (var g in gameCounts) {
    var pt = gamePoints[g];
    gameLabel[g] = g + (pt ? ' (' + n(pt) + 'P)' : '');
  }

  var vendorMap = {}, codeVendorMap = {};
  var ms = ss.getSheetByName('경품코드 마스터');
  if (ms && ms.getLastRow() > 1) {
    var msData = ms.getDataRange().getValues();
    var msH = msData[0];
    var msNameIdx = msH.indexOf('경품명');
    var msVendorIdx = msH.indexOf('교환처');
    var msCodeIdx2 = msH.indexOf('경품코드');
    if (msNameIdx >= 0 && msVendorIdx >= 0) {
      for (var i = 1; i < msData.length; i++) {
        var pname = msData[i][msNameIdx];
        var vendor = msData[i][msVendorIdx];
        if (pname && vendor) vendorMap[pname] = vendor;
        if (msCodeIdx2 >= 0 && msData[i][msCodeIdx2] && vendor) {
          codeVendorMap[String(msData[i][msCodeIdx2]).trim()] = vendor;
        }
      }
    }
  }

  var dates   = rows.map(function(r) { return new Date(r[idx.gameDate]); }).filter(function(d) { return !isNaN(d); });
  var minDate = new Date(Math.min.apply(null, dates));
  var maxDate = new Date(Math.max.apply(null, dates));
  var today   = new Date();
  var repDate = fmtDate(today);
  var dateRange = fmtDT(minDate) + ' ~ ' + fmtDT(maxDate);

  var couponStats = null;
  var couponSheet = ss.getSheetByName('할인쿠폰');
  if (couponSheet && couponSheet.getLastRow() > 1) {
    couponStats = getCouponStats(couponSheet, amountGameMap);
  }

  if (ms) populateMaster(ss, ms);

  var txToGame = {}, txToPrize = {};
  for (var i = 0; i < rows.length; i++) {
    var tx = idx.txId >= 0 ? rows[i][idx.txId] : null;
    if (tx) {
      txToGame[String(tx)] = rows[i][idx.gameName];
      txToPrize[String(tx)] = rows[i][idx.prizeName] || '';
    }
  }

  var prizeUsage = null;
  var prizeSheet = ss.getSheetByName('매체사 경품');
  if (prizeSheet && prizeSheet.getLastRow() > 1) {
    prizeUsage = getPrizeUsage(prizeSheet, txToGame, txToPrize, today);
  }

  buildExternal(ss, repDate, dateRange, total, uniqueUsers, prizeDone, prizeFail, gameEntries, gameLabel);
  buildInternal(ss, repDate, dateRange, total, uniqueUsers, totalPoints, prizeDone, prizeFail, gameEntries, gameLabel, gamePrizes, gameCounts, monthEntries, couponStats, vendorMap, avgDailyRuns, avgDailyUsers, prizeUsage, prizeCounts, prizeCodeByName, codeVendorMap);
  buildDailySheet(ss, rows, idx, couponSheet, prizeSheet);
  appendDashboard(ss, repDate, minDate, maxDate, total, uniqueUsers, totalPoints, prizeDone, prizeFail, gameCounts);

  ss.setActiveSheet(ss.getSheetByName('외부보고'));
  alert_('✅ 완료! (총 ' + total + '건 처리)');
}

function getCouponStats(couponSheet, amountGameMap) {
  var data = couponSheet.getDataRange().getValues();
  var h = data[0];
  var nameIdx = h.indexOf('쿠폰명');
  var codeIdx = h.indexOf('상품코드');
  if (nameIdx < 0) return null;

  var pinIdx = h.indexOf('핀번호');
  var seenPin = {}, byType = {};
  for (var i = 1; i < data.length; i++) {
    var pin = pinIdx >= 0 ? data[i][pinIdx] : null;
    if (pin && seenPin[pin]) continue;
    if (pin) seenPin[pin] = true;
    var name = String(data[i][nameIdx]);
    if (!name || name === 'undefined') continue;
    var isUsed = data[i][codeIdx] ? 1 : 0;
    if (!byType[name]) {
      byType[name] = { issued: 0, used: 0, game: amountGameMap[extractAmount(name)] || '-' };
    }
    byType[name].issued++;
    byType[name].used += isUsed;
  }
  return byType;
}

function getPrizeUsage(prizeSheet, txToGame, txToPrize, today) {
  var data = prizeSheet.getDataRange().getValues();
  var h = data[0];
  var tridIdx = h.indexOf('B2B2C_TR_ID');
  var statusIdx = h.indexOf('핀상태');
  var expIdx = h.indexOf('유효기간');
  var pinIdx = h.indexOf('핀번호');
  if (tridIdx < 0 || statusIdx < 0) return null;

  var result = {};
  var seenPin = {};

  for (var i = 1; i < data.length; i++) {
    var trid = String(data[i][tridIdx]).replace(/^=?"?|"$/g, '').trim();
    if (trid.indexOf('GAME_') !== 0) continue;

    var status = String(data[i][statusIdx]);
    if (status.indexOf('취소') >= 0 || status.indexOf('환불') >= 0) continue;

    var pin = pinIdx >= 0 ? String(data[i][pinIdx]).replace(/^=?"?|"$/g, '').trim() : null;
    if (pin && seenPin[pin]) continue;
    if (pin) seenPin[pin] = true;

    var txId = trid.replace('GAME_', '');
    var game = txToGame[txId];
    var pname = txToPrize[txId];
    if (!game || !pname) continue;

    if (!result[game]) result[game] = {};
    if (!result[game][pname]) result[game][pname] = { issued: 0, used: 0, expired: 0 };

    if (status.indexOf('사용') >= 0 || status.indexOf('교환') >= 0) {
      result[game][pname].used++;
    } else if (status === '발행' || status === '반품') {
      if (expIdx >= 0) {
        var expStr = String(data[i][expIdx]).replace(/[^0-9]/g, '').trim();
        if (expStr.length === 8) {
          var expDate = new Date(Number(expStr.substring(0, 4)), Number(expStr.substring(4, 6)) - 1, Number(expStr.substring(6, 8)));
          if (expDate < today) {
            result[game][pname].expired++;
          } else {
            result[game][pname].issued++;
          }
        } else {
          result[game][pname].issued++;
        }
      } else {
        result[game][pname].issued++;
      }
    }
  }

  return (Object.keys(result).length > 0) ? result : null;
}

// ══════════════════════════════════════════════════
// 외부보고
// ══════════════════════════════════════════════════
function buildExternal(ss, repDate, dateRange, total, uniqueUsers, prizeDone, prizeFail, gameEntries, gameLabel) {
  var sh = resetSheet(ss, '외부보고');
  setColWidths(sh, [20, 210, 100, 130, 100, 20]);
  var r = 1;

  titleRow(sh, r, 'IBK 카드앱 게이미피케이션 운영 현황', 2, 4); r++;
  subRow(sh, r, '기준일: ' + repDate + '   |   데이터 기간: ' + dateRange, 2, 4); r++;
  gap(sh, r, 10); r++;

  secRow(sh, r, '종합 현황', 2, 4); r++;
  kpiR(sh, r, 2, ['총 게임 실행 수(회)', n(total), '실제 참여자(명)', n(uniqueUsers)]); r++;
  var pl = prizeFail === 0 ? n(prizeDone) : '완료 ' + n(prizeDone) + ' / 미완료 ' + n(prizeFail);
  kpiR(sh, r, 2, ['경품 지급 완료(건)', pl]); r++;
  gap(sh, r, 10); r++;

  secRow(sh, r, '게임별 실행 수', 2, 4); r++;
  colR(sh, r, 2, ['게임명', '실행 수(회)', '비율']); r++;
  for (var i = 0; i < gameEntries.length; i++) {
    dataR(sh, r, 2, [gameLabel[gameEntries[i][0]], n(gameEntries[i][1]), pct(gameEntries[i][1], total)]); r++;
  }
  totalR(sh, r, 2, ['합계', n(total), '100%']); r++;
  gap(sh, r, 10);
}

// ══════════════════════════════════════════════════
// 내부보고 (가로 레이아웃)
// ══════════════════════════════════════════════════
function buildInternal(ss, repDate, dateRange, total, uniqueUsers, totalPoints, prizeDone, prizeFail, gameEntries, gameLabel, gamePrizes, gameCounts, monthEntries, couponStats, vendorMap, avgDailyRuns, avgDailyUsers, prizeUsage, prizeCounts, prizeCodeByName, codeVendorMap) {
  var sh = resetSheet(ss, '내부보고');
  setColWidths(sh, [20, 155, 100, 70, 70, 70, 55, 55, 20, 30, 170, 85, 85, 85, 20]);
  var r = 1;

  titleRow(sh, r, 'IBK 게임 운영 내부 현황', 2, 4); r++;
  subRow(sh, r, '기준일: ' + repDate + '   |   데이터 기간: ' + dateRange, 2, 4); r++;
  gap(sh, r, 10); r++;

  secRow(sh, r, '종합 현황', 2, 4); r++;
  kpiR(sh, r, 2, ['총 게임 실행 수(회)', n(total), '실제 참여자(명)', n(uniqueUsers)]); r++;
  kpiR(sh, r, 2, ['일 평균 게임 실행 수(회)', n(avgDailyRuns), '일 평균 실제 참여자(명)', n(avgDailyUsers)]); r++;
  kpiR(sh, r, 2, ['포인트 사용 합계(P)', n(totalPoints), '게임당 평균(P)', n(Math.round(totalPoints / total))]); r++;
  var pl = prizeFail === 0 ? n(prizeDone) : '완료 ' + n(prizeDone) + ' / 미완료 ' + n(prizeFail);
  kpiR(sh, r, 2, ['경품 지급 완료(건)', pl]); r++;
  gap(sh, r, 10); r++;

  secRow(sh, r, '게임별 실행 수', 2, 4); r++;
  colR(sh, r, 2, ['게임명', '실행 수(회)', '비율']); r++;
  for (var i = 0; i < gameEntries.length; i++) {
    dataR(sh, r, 2, [gameLabel[gameEntries[i][0]], n(gameEntries[i][1]), pct(gameEntries[i][1], total)]); r++;
  }
  totalR(sh, r, 2, ['합계', n(total), '100%']); r++;
  gap(sh, r, 10); r++;

  var couponUsedMap = {}, couponPendingMap = {};
  if (couponStats) {
    var cnames = Object.keys(couponStats);
    for (var ci = 0; ci < cnames.length; ci++) {
      var cn = cnames[ci];
      var cd = couponStats[cn];
      var cg = cd.game || '-';
      if (!couponUsedMap[cg]) couponUsedMap[cg] = {};
      if (!couponPendingMap[cg]) couponPendingMap[cg] = {};
      couponUsedMap[cg][cn] = cd.used;
      couponPendingMap[cg][cn] = cd.issued - cd.used;
    }
  }

  var hasUsageData = prizeUsage || couponStats;

  var pzCounts = prizeCounts || {};
  var pzCodeByName = prizeCodeByName || {};
  var cdVendorMap = codeVendorMap || {};

  secRow(sh, r, '게임별 경품 발행 · 사용 현황', 2, 7); r++;
  for (var i = 0; i < gameEntries.length; i++) {
    var game = gameEntries[i][0];
    var gTotal = gameCounts[game];
    var prizes = sortEntries(gamePrizes[game] || {});
    if (!prizes.length) continue;

    gameSubRow(sh, r, gameLabel[game] + '  (총 ' + n(gTotal) + '회)', 2, 7); r++;
    colR(sh, r, 2, ['경품명', '교환처', '발행(건)', '사용(건)', '기간만료(건)', '사용률', '당첨확률']); r++;

    var gPrizeCount = 0, gUsed = 0, gExpired = 0;
    for (var j = 0; j < prizes.length; j++) {
      var pn = prizes[j][0];
      var prizeCount = prizes[j][1];
      var used = 0, expired = 0;

      if (prizeUsage && prizeUsage[game] && prizeUsage[game][pn]) {
        used = prizeUsage[game][pn].used;
        expired = prizeUsage[game][pn].expired;
      }

      if (used === 0) {
        if (couponUsedMap[game]) {
          if (couponUsedMap[game][pn] !== undefined) {
            used = couponUsedMap[game][pn];
          } else {
            var amt = extractAmount(pn);
            if (amt) {
              var ck = Object.keys(couponUsedMap[game]);
              for (var ci = 0; ci < ck.length; ci++) {
                if (extractAmount(ck[ci]) === amt) { used = couponUsedMap[game][ck[ci]]; break; }
              }
            }
          }
        }
      }

      var vendorCode = pzCodeByName[pn] ? cdVendorMap[pzCodeByName[pn]] : '';
      var vendor = vendorCode || vendorMap[pn] || '';

      gPrizeCount += prizeCount;
      gUsed += used;
      gExpired += expired;
      var useRate = hasUsageData ? (prizeCount > 0 ? (used / prizeCount * 100).toFixed(1) + '%' : '-') : '-';
      var hitRate = gTotal > 0 ? (prizeCount / gTotal * 100).toFixed(1) + '%' : '-';
      dataR(sh, r, 2, [shorten(pn), vendor, n(prizeCount), hasUsageData ? n(used) : '-', hasUsageData ? n(expired) : '-', useRate, hitRate],
        ['left', 'left', 'right', 'right', 'right', 'right', 'right']); r++;
    }
    var gUseRate = hasUsageData ? (gPrizeCount > 0 ? (gUsed / gPrizeCount * 100).toFixed(1) + '%' : '-') : '-';
    totalR(sh, r, 2, ['합계', '', n(gPrizeCount), hasUsageData ? n(gUsed) : '-', hasUsageData ? n(gExpired) : '-', gUseRate, '100%']); r++;
    gap(sh, r, 6); r++;
  }

  if (monthEntries.length > 1) {
    gap(sh, r, 4); r++;
    secRow(sh, r, '월별 집계', 2, 4); r++;
    colR(sh, r, 2, ['월', '총 실행(회)', '참여자(명)']); r++;
    for (var i = 0; i < monthEntries.length; i++) {
      var md = monthEntries[i][1];
      dataR(sh, r, 2, [monthEntries[i][0], n(md.total), n(Object.keys(md.users).length)]); r++;
    }
  }

  if (couponStats) buildCouponSection(sh, couponStats, repDate, dateRange, pzCounts);
}

function buildCouponSection(sh, couponStats, repDate, dateRange, prizeCounts) {
  var col = 11;
  var r = 1;
  var pzCounts = prizeCounts || {};

  titleRow(sh, r, '할인쿠폰 현황', col, 4); r++;
  subRow(sh, r, '기준일: ' + repDate + '   |   데이터 기간: ' + dateRange, col, 4); r++;
  gap(sh, r, 10); r++;

  secRow(sh, r, '종류별 발행 · 사용 현황', col, 4); r++;
  colR(sh, r, col, ['쿠폰명', '발행(건)', '사용(건)', '사용률']); r++;

  var typeNames = Object.keys(couponStats).sort();
  var totalIssued = 0, totalUsed = 0;
  for (var i = 0; i < typeNames.length; i++) {
    var d = couponStats[typeNames[i]];
    var issued = pzCounts[typeNames[i]] || 0;
    if (!issued) {
      var camt = extractAmount(typeNames[i]);
      if (camt) {
        var pkeys = Object.keys(pzCounts);
        for (var pi = 0; pi < pkeys.length; pi++) {
          if (extractAmount(pkeys[pi]) === camt) { issued = pzCounts[pkeys[pi]]; break; }
        }
      }
    }
    var rate = issued > 0 ? (d.used / issued * 100).toFixed(1) + '%' : '-';
    dataR(sh, r, col, [shorten(typeNames[i]), n(issued), n(d.used), rate]); r++;
    totalIssued += issued;
    totalUsed += d.used;
  }
  var totalRate = totalIssued > 0 ? (totalUsed / totalIssued * 100).toFixed(1) + '%' : '-';
  totalR(sh, r, col, ['합계', n(totalIssued), n(totalUsed), totalRate]); r++;
  gap(sh, r, 10); r++;

  secRow(sh, r, '게임별 쿠폰 발행 · 사용', col, 4); r++;
  colR(sh, r, col, ['게임명', '발행(건)', '사용(건)', '사용률']); r++;

  var gameAgg = {};
  for (var i = 0; i < typeNames.length; i++) {
    var d = couponStats[typeNames[i]];
    var game = d.game;
    var issued = pzCounts[typeNames[i]] || 0;
    if (!issued) {
      var camt2 = extractAmount(typeNames[i]);
      if (camt2) {
        var pkeys2 = Object.keys(pzCounts);
        for (var pi2 = 0; pi2 < pkeys2.length; pi2++) {
          if (extractAmount(pkeys2[pi2]) === camt2) { issued = pzCounts[pkeys2[pi2]]; break; }
        }
      }
    }
    if (!gameAgg[game]) gameAgg[game] = { issued: 0, used: 0 };
    gameAgg[game].issued += issued;
    gameAgg[game].used += d.used;
  }
  var gameKeys = Object.keys(gameAgg);
  for (var i = 0; i < gameKeys.length; i++) {
    var ga = gameAgg[gameKeys[i]];
    var rate = ga.issued > 0 ? (ga.used / ga.issued * 100).toFixed(1) + '%' : '-';
    dataR(sh, r, col, [gameKeys[i], n(ga.issued), n(ga.used), rate]); r++;
  }
}

// ══════════════════════════════════════════════════
// 일별현황
// ══════════════════════════════════════════════════
function buildDailySheet(ss, rows, idx, couponSheet, prizeSheet) {
  var sh = resetSheet(ss, '일별현황');
  sh.setTabColor('#0EA5E9');
  sh.setColumnWidth(1, 110);
  sh.setColumnWidth(2, 50);
  sh.setColumnWidth(3, 140);
  sh.setColumnWidth(4, 130);
  sh.setColumnWidth(5, 160);
  sh.setColumnWidth(6, 120);
  sh.setColumnWidth(7, 150);

  var DAYS = ['일', '월', '화', '수', '목', '금', '토'];

  // 1. 포인트 일별 집계 (로우데이터)
  var dailyPoints = {};
  for (var i = 0; i < rows.length; i++) {
    var dk = fmtDay(new Date(rows[i][idx.gameDate]));
    dailyPoints[dk] = (dailyPoints[dk] || 0) + (Number(rows[i][idx.points]) || 0);
  }

  // 2. 할인쿠폰 일별 집계 (발행일자 기준, 핀번호 중복 제거)
  var dailyCouponCount = {}, dailyCouponAmt = {};
  if (couponSheet && couponSheet.getLastRow() > 1) {
    var cd = couponSheet.getDataRange().getValues();
    var ch = cd[0];
    var cdDateIdx = ch.indexOf('발행일자');
    var cdNameIdx = ch.indexOf('쿠폰명');
    var cdPinIdx  = ch.indexOf('핀번호');
    var seenPinC  = {};
    for (var i = 1; i < cd.length; i++) {
      var pin = cdPinIdx >= 0 ? String(cd[i][cdPinIdx]) : null;
      if (pin && seenPinC[pin]) continue;
      if (pin) seenPinC[pin] = true;
      if (cdDateIdx < 0 || !cd[i][cdDateIdx]) continue;
      var dk = fmtDayFromVal(cd[i][cdDateIdx]);
      if (!dk) continue;
      dailyCouponCount[dk] = (dailyCouponCount[dk] || 0) + 1;
      dailyCouponAmt[dk]   = (dailyCouponAmt[dk] || 0) + extractAmountNum(String(cd[i][cdNameIdx] || ''));
    }
  }

  // 3. 매체사 경품 일별 집계 (MMS발송일 기준, 핀번호 중복·취소 제거)
  var dailyPrizeCount = {}, dailyPrizeAmt = {};
  if (prizeSheet && prizeSheet.getLastRow() > 1) {
    var pd = prizeSheet.getDataRange().getValues();
    var ph = pd[0];
    var pdMmsIdx    = ph.indexOf('MMS발송일');
    var pdPriceIdx  = ph.indexOf('공급가격');
    var pdTridIdx   = ph.indexOf('B2B2C_TR_ID');
    var pdStatusIdx = ph.indexOf('핀상태');
    var pdPinIdx    = ph.indexOf('핀번호');
    var seenPinP    = {};
    for (var i = 1; i < pd.length; i++) {
      var trid = pdTridIdx >= 0 ? String(pd[i][pdTridIdx]).replace(/^=?"?|"$/g, '').trim() : '';
      if (trid.indexOf('GAME_') !== 0) continue;
      var status = pdStatusIdx >= 0 ? String(pd[i][pdStatusIdx]) : '';
      if (status.indexOf('취소') >= 0 || status.indexOf('환불') >= 0) continue;
      var pin = pdPinIdx >= 0 ? String(pd[i][pdPinIdx]).replace(/^=?"?|"$/g, '').trim() : null;
      if (pin && seenPinP[pin]) continue;
      if (pin) seenPinP[pin] = true;
      if (pdMmsIdx < 0 || !pd[i][pdMmsIdx]) continue;
      var dk = fmtDayFromVal(pd[i][pdMmsIdx]);
      if (!dk) continue;
      dailyPrizeCount[dk] = (dailyPrizeCount[dk] || 0) + 1;
      dailyPrizeAmt[dk]   = (dailyPrizeAmt[dk] || 0) + (Number(pd[i][pdPriceIdx]) || 0);
    }
  }

  // 전체 날짜 모아 정렬
  var allDays = {};
  Object.keys(dailyPoints).forEach(function(k) { allDays[k] = 1; });
  Object.keys(dailyCouponCount).forEach(function(k) { allDays[k] = 1; });
  Object.keys(dailyPrizeCount).forEach(function(k) { allDays[k] = 1; });
  var sortedDays = Object.keys(allDays).sort();
  if (!sortedDays.length) return;

  // 헤더
  var r = 1;
  sh.setRowHeight(r, 28);
  var hdrs = ['날짜', '요일', '소진 포인트(P)', '할인쿠폰 발행(건)', '할인쿠폰 발행금액(원)', '경품 발행(건)', '경품 발행금액(원)'];
  sh.getRange(r, 1, 1, 7).setValues([hdrs])
    .setBackground(C.T_BG).setFontColor(C.T_FG).setFontWeight('bold').setFontSize(10)
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setFrozenRows(1);
  r++;

  var monthData = {};
  var totP = 0, totCC = 0, totCA = 0, totPC = 0, totPA = 0;

  for (var di = 0; di < sortedDays.length; di++) {
    var dk = sortedDays[di];
    var dateObj = new Date(dk + 'T00:00:00');
    var dow = dateObj.getDay();
    var pts = dailyPoints[dk] || 0;
    var cc  = dailyCouponCount[dk] || 0;
    var ca  = dailyCouponAmt[dk] || 0;
    var pc  = dailyPrizeCount[dk] || 0;
    var pa  = dailyPrizeAmt[dk] || 0;

    sh.setRowHeight(r, 26);
    sh.getRange(r, 1).setValue(dk)
      .setHorizontalAlignment('center').setBackground(C.WHITE).setFontSize(10).setFontColor(C.BLACK).setVerticalAlignment('middle');
    sh.getRange(r, 2).setValue(DAYS[dow])
      .setHorizontalAlignment('center').setBackground(C.WHITE).setFontSize(10).setVerticalAlignment('middle')
      .setFontColor(dow === 0 ? '#EF4444' : (dow === 6 ? '#3B82F6' : C.BLACK));
    sh.getRange(r, 3, 1, 5).setValues([[n(pts), n(cc), n(ca), n(pc), n(pa)]])
      .setHorizontalAlignment('right').setBackground(C.WHITE).setFontSize(10).setFontColor(C.BLACK).setVerticalAlignment('middle');
    r++;

    var mk = dk.substring(0, 7);
    if (!monthData[mk]) monthData[mk] = { p: 0, cc: 0, ca: 0, pc: 0, pa: 0 };
    monthData[mk].p  += pts; monthData[mk].cc += cc; monthData[mk].ca += ca;
    monthData[mk].pc += pc;  monthData[mk].pa += pa;
    totP += pts; totCC += cc; totCA += ca; totPC += pc; totPA += pa;
  }

  // 합계 행
  gap(sh, r, 8); r++;
  totalR(sh, r, 1, ['합계', '', n(totP), n(totCC), n(totCA), n(totPC), n(totPA)]); r++;

  // 월별 합계
  gap(sh, r, 12); r++;
  secRow(sh, r, '월별 합계', 1, 7); r++;
  sh.setRowHeight(r, 24);
  sh.getRange(r, 1, 1, 7).setValues([['월', '', '소진 포인트(P)', '할인쿠폰 발행(건)', '할인쿠폰 발행금액(원)', '경품 발행(건)', '경품 발행금액(원)']])
    .setBackground(C.CH_BG).setFontColor(C.CH_FG).setFontWeight('bold').setFontSize(9)
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  r++;

  var sortedMonths = Object.keys(monthData).sort();
  for (var mi = 0; mi < sortedMonths.length; mi++) {
    var mk = sortedMonths[mi];
    var md = monthData[mk];
    var mLabel = mk.replace('-', '년 ') + '월';
    sh.setRowHeight(r, 26);
    sh.getRange(r, 1).setValue(mLabel)
      .setHorizontalAlignment('center').setBackground(C.WHITE).setFontSize(10).setFontColor(C.BLACK).setVerticalAlignment('middle');
    sh.getRange(r, 2).setValue('').setBackground(C.WHITE);
    sh.getRange(r, 3, 1, 5).setValues([[n(md.p), n(md.cc), n(md.ca), n(md.pc), n(md.pa)]])
      .setHorizontalAlignment('right').setBackground(C.WHITE).setFontSize(10).setFontColor(C.BLACK).setVerticalAlignment('middle');
    r++;
  }
}

// ══════════════════════════════════════════════════
// 누적현황
// ══════════════════════════════════════════════════
function appendDashboard(ss, repDate, minDate, maxDate, total, uniqueUsers, totalPoints, prizeDone, prizeFail, gameCounts) {
  var sh = ss.getSheetByName('누적현황');
  var isNew = !sh;
  if (isNew) sh = ss.insertSheet('누적현황');

  var gameNames = Object.keys(gameCounts).sort();

  if (isNew || sh.getLastRow() === 0) {
    var heads = ['보고일','데이터 시작','데이터 종료','총 실행(회)','참여자(명)','포인트 사용(P)','경품 완료(건)','경품 미완료(건)'].concat(gameNames);
    sh.getRange(1, 1, 1, heads.length).setValues([heads])
      .setBackground(C.T_BG).setFontColor(C.T_FG).setFontWeight('bold').setFontSize(10).setVerticalAlignment('middle');
    sh.setFrozenRows(1);
    sh.setRowHeight(1, 32);
    sh.setColumnWidths(1, heads.length, 110);
    sh.setColumnWidth(1, 100);
    sh.setColumnWidth(2, 150);
    sh.setColumnWidth(3, 150);
    sh.setTabColor(C.T_FG);
  }

  var newRow = [repDate, fmtDT(minDate), fmtDT(maxDate), total, uniqueUsers, totalPoints, prizeDone, prizeFail];
  for (var i = 0; i < gameNames.length; i++) newRow.push(gameCounts[gameNames[i]] || 0);

  var nr = sh.getLastRow() + 1;
  sh.getRange(nr, 1, 1, newRow.length).setValues([newRow])
    .setBackground(C.WHITE).setFontSize(10).setVerticalAlignment('middle');
  sh.setRowHeight(nr, 28);
}

// ══════════════════════════════════════════════════
// 오류 보고 시트 생성
// ══════════════════════════════════════════════════
function buildErrorReport() {
  try { _buildErrorReport(); }
  catch(e) { SpreadsheetApp.getUi().alert('오류: ' + e.message + '\n\n' + e.stack); }
}

function _buildErrorReport() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var rawSheet = ss.getSheetByName('로우데이터');
  if (!rawSheet || rawSheet.getLastRow() <= 1) { alert_('로우데이터가 없습니다.'); return; }

  // 오류입력 시트에서 슬랙 오류 데이터 읽기
  var inputSheet = ss.getSheetByName('오류입력');
  if (!inputSheet || inputSheet.getLastRow() <= 1) {
    alert_('오류입력 시트가 없거나 데이터가 없습니다.\n클로드에게 슬랙 오류 동기화를 요청하세요.');
    return;
  }
  var inputData = inputSheet.getDataRange().getValues();

  var ibkTxList = [], doitTxList = [], slackMemoMap = {};
  for (var i = 1; i < inputData.length; i++) {
    var gubun = String(inputData[i][0]).trim();
    var tx    = String(inputData[i][1]).trim();
    var memo  = String(inputData[i][2]).trim();
    if (!tx) continue;
    slackMemoMap[tx] = memo;
    if (gubun === 'IBK')  ibkTxList.push(tx);
    if (gubun === '두잇') doitTxList.push(tx);
  }

  // 로우데이터 → 거래번호 맵
  var data = rawSheet.getDataRange().getValues();
  var h    = data[0];
  var eidx = {
    tx:     h.indexOf('거래번호'),
    game:   h.indexOf('게임명'),
    date:   h.indexOf('게임 실행일'),
    pts:    h.indexOf('차감 포인트'),
    ptSt:   h.indexOf('포인트 차감 상태'),
    result: h.indexOf('게임 결과')
  };
  var txMap = {};
  for (var i = 1; i < data.length; i++) {
    var tx = String(data[i][eidx.tx] || '').trim();
    if (tx) txMap[tx] = data[i];
  }

  // IBK 거래번호 → 로우데이터 조회
  var ibkRows = [];
  for (var i = 0; i < ibkTxList.length; i++) {
    var tx  = ibkTxList[i];
    var row = txMap[tx];
    if (row) {
      var gameDate = new Date(row[eidx.date]);
      var ptSt     = String(row[eidx.ptSt]   || '');
      var result   = String(row[eidx.result] || '');
      var memo     = slackMemoMap[tx] || '';
      ibkRows.push([fmtDT(gameDate), tx, row[eidx.game] || '',
                    Number(row[eidx.pts]) || 0, ptSt, result, memo]);
    } else {
      ibkRows.push(['(로우데이터 미포함)', tx, '-', '-', '-', '-', slackMemoMap[tx] || '로우데이터에 없음']);
    }
  }

  // 두잇 거래번호 → 로우데이터 조회
  var doitRows = [];
  for (var i = 0; i < doitTxList.length; i++) {
    var tx      = doitTxList[i];
    var row     = txMap[tx];
    var gameDate = row ? new Date(row[eidx.date]) : null;
    var slackDt  = inputData.filter(function(r) { return String(r[1]).trim() === tx; });
    var slackDate = '';
    if (slackDt.length > 0) {
      var sdVal = slackDt[0][3];
      slackDate = sdVal instanceof Date ? fmtDT(sdVal) : String(sdVal);
    }
    doitRows.push([
      slackDate || (gameDate ? fmtDT(gameDate) : '(확인 필요)'),
      tx,
      slackMemoMap[tx] || 'COMPLETE 상태 거래 보상 재요청',
      gameDate ? fmtDT(gameDate) : '',
      '', '', ''
    ]);
  }

  // 시트 생성
  var sh = resetSheet(ss, '오류보고');
  sh.setTabColor('#EF4444');
  setColWidths(sh, [20, 165, 200, 220, 160, 130, 120, 180]);

  var today = new Date();
  var r = 1;

  titleRow(sh, r, '📋 IBK 게이미피케이션 오류 발생 현황', 2, 7); r++;
  subRow(sh, r, '기준일: ' + fmtDate(today), 2, 7); r++;
  gap(sh, r, 12); r++;

  // IBK 섹션
  secRow(sh, r, '① IBK(고객사) 확인 요청 — IBK API 오류 건', 2, 7); r++;
  colR(sh, r, 2, ['게임 실행일시', '거래번호', '게임명', '포인트(P)', '차감 상태', '게임 결과', '비고']); r++;

  if (ibkRows.length === 0) {
    sh.setRowHeight(r, 28);
    sh.getRange(r, 2, 1, 7).merge().setValue('입력된 거래번호 없음')
      .setBackground(C.WHITE).setFontColor('#9CA3AF').setFontSize(10)
      .setHorizontalAlignment('center').setVerticalAlignment('middle');
    r++;
  } else {
    for (var i = 0; i < ibkRows.length; i++) {
      var er = ibkRows[i];
      var rowAligns = ['left', 'left', 'left', 'right', 'center', 'center', 'left'];
      // 로우데이터 미포함 행은 회색 처리
      if (er[6] === '로우데이터에 없음') {
        sh.setRowHeight(r, 28);
        for (var ci = 0; ci < er.length; ci++) {
          sh.getRange(r, 2 + ci).setValue(er[ci])
            .setBackground('#F3F4F6').setFontColor('#6B7280').setFontSize(10)
            .setVerticalAlignment('middle').setHorizontalAlignment(rowAligns[ci]);
        }
        r++;
      } else {
        dataR(sh, r, 2, [er[0], er[1], er[2], n(er[3]) + 'P', er[4], er[5], er[6]], rowAligns);
        r++;
      }
    }
    totalR(sh, r, 2, ['합계', '총 ' + ibkRows.length + '건', '', '', '', '', '']); r++;
  }

  gap(sh, r, 16); r++;

  // 두잇 섹션
  secRow(sh, r, '② 두잇(게임사) 확인 요청 — 중복 보상 요청 건 (수정 가능)', 2, 7); r++;
  colR(sh, r, 2, ['게임 실행일시', '거래번호', '오류 내용', '첫 처리 시각', '재요청 시각', '경과 시간', '비고']); r++;

  if (doitRows.length === 0) {
    sh.setRowHeight(r, 28);
    sh.getRange(r, 2, 1, 7).merge().setValue('입력된 거래번호 없음')
      .setBackground(C.WHITE).setFontColor('#9CA3AF').setFontSize(10)
      .setHorizontalAlignment('center').setVerticalAlignment('middle');
    r++;
  } else {
    for (var i = 0; i < doitRows.length; i++) {
      dataR(sh, r, 2, doitRows[i], ['left','left','left','left','left','left','left']);
      r++;
    }
  }
  // 추가 입력용 빈 행 3개
  for (var k = 0; k < 3; k++) {
    sh.setRowHeight(r, 28);
    sh.getRange(r, 2, 1, 7).setBackground(C.WHITE).setFontSize(10).setVerticalAlignment('middle');
    r++;
  }

  gap(sh, r, 10); r++;
  sh.setRowHeight(r, 30);
  sh.getRange(r, 2, 1, 7).merge()
    .setValue('💡 내용 확인 후 상단 메뉴 [📊 IBK 보고] → [④ 오류 메일 초안 생성] 클릭')
    .setBackground('#FEF9C3').setFontColor('#92400E').setFontSize(9)
    .setHorizontalAlignment('left').setVerticalAlignment('middle');

  ss.setActiveSheet(sh);
  alert_('✅ 오류보고 시트 생성 완료!\n\n· IBK 확인 요청: ' + ibkRows.length + '건\n· 두잇 확인 요청: ' + doitRows.length + '건\n\n내용 검토 후 [④ 오류 메일 초안 생성]을 실행하세요.');
}

// ══════════════════════════════════════════════════
// 오류 메일 초안 생성 (Gmail 임시보관함)
// ══════════════════════════════════════════════════
function createErrorDrafts() {
  try { _createErrorDrafts(); }
  catch(e) { SpreadsheetApp.getUi().alert('오류: ' + e.message + '\n\n' + e.stack); }
}

function _createErrorDrafts() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName('오류보고');
  if (!sh) { alert_('오류보고 시트가 없습니다.\n[③ 오류 보고 시트 생성]을 먼저 실행해 주세요.'); return; }

  var allData  = sh.getDataRange().getValues();
  var ibkRows  = [], doitRows = [], mode = '';

  for (var i = 0; i < allData.length; i++) {
    var c = String(allData[i][1]);
    if (c.indexOf('IBK(고객사)') >= 0)  { mode = 'ibk';  continue; }
    if (c.indexOf('두잇(게임사)') >= 0) { mode = 'doit'; continue; }
    if (mode === 'ibk' && allData[i][1] &&
        c !== '게임 실행일시' && c !== '합계' && c.indexOf('해당 기간') < 0) {
      ibkRows.push(allData[i]);
    }
    if (mode === 'doit' && allData[i][2] &&
        c !== '발생 일시' && c.indexOf('💡') < 0 && String(allData[i][2]).trim() !== '') {
      doitRows.push(allData[i]);
    }
  }

  var today        = new Date();
  var dateStr      = fmtDate(today);
  var draftsCreated = 0;

  // IBK 메일 초안
  if (ibkRows.length > 0) {
    var ibkList = '';
    for (var i = 0; i < ibkRows.length; i++) {
      var rr = ibkRows[i];
      ibkList += '  · ' + rr[1] + ' | ' + rr[2] + ' | ' + rr[3] + ' | ' + rr[4] + '\n';
    }
    var ibkBody =
      'IBK카드 담당자님, 안녕하세요.\n' +
      '윈큐브마케팅 명지혜입니다.\n\n' +
      'IBK 카드앱 게이미피케이션 서비스 운영 중 아래와 같이 IBK API 오류 건이 확인되어\n' +
      '내용 공유 및 확인 요청드립니다.\n\n' +
      '■ 오류 발생 건 (총 ' + ibkRows.length + '건)\n' +
      '──────────────────────────────────────────────\n' +
      '  게임 실행일시               거래번호                   게임명              포인트\n' +
      '──────────────────────────────────────────────\n' +
      ibkList +
      '──────────────────────────────────────────────\n\n' +
      '해당 건 처리 여부 확인 및 오류 원인 공유 부탁드립니다.\n' +
      '감사합니다.\n\n' +
      '윈큐브마케팅 명지혜 드림';
    GmailApp.createDraft(
      '',
      '[IBK 게이미피케이션] IBK API 오류 건 확인 요청 (' + dateStr + ')',
      ibkBody
    );
    draftsCreated++;
  }

  // 두잇 메일 초안
  if (doitRows.length > 0) {
    var doitList = '';
    for (var i = 0; i < doitRows.length; i++) {
      var rr = doitRows[i];
      doitList +=
        '  · [거래번호] ' + rr[2] + '\n' +
        '    오류 내용 : ' + rr[3] + '\n' +
        '    첫 처리   : ' + rr[4] + '\n' +
        '    재요청    : ' + rr[5] + ' (' + rr[6] + ')\n\n';
    }
    var doitBody =
      '두잇파이브 담당자님, 안녕하세요.\n' +
      '윈큐브마케팅 명지혜입니다.\n\n' +
      'IBK 게이미피케이션 운영 중 이미 완료 처리된 거래에 대해 보상 요청이 재발생하는\n' +
      '이상 건이 확인되어 내용 공유드립니다.\n\n' +
      '■ 이상 발생 건 (총 ' + doitRows.length + '건)\n' +
      '──────────────────────────────────────────────\n' +
      doitList +
      '──────────────────────────────────────────────\n\n' +
      '※ 이미 COMPLETE 처리된 거래번호에 대해 보상 재요청이 발생한 건으로,\n' +
      '   시스템 비즈니스 로직에 따라 오류 처리되었습니다.\n\n' +
      '발생 원인 분석 및 재발 방지 조치 계획 공유 부탁드립니다.\n' +
      '감사합니다.\n\n' +
      '윈큐브마케팅 명지혜 드림';
    GmailApp.createDraft(
      '',
      '[IBK 게이미피케이션] 중복 보상 요청 이상 건 확인 요청 (' + dateStr + ')',
      doitBody
    );
    draftsCreated++;
  }

  if (draftsCreated === 0) {
    alert_('생성할 초안이 없습니다.\n오류보고 시트에 데이터가 있는지 확인해 주세요.');
    return;
  }
  alert_('✅ Gmail 초안 ' + draftsCreated + '개 생성 완료!\n\nGmail → 임시보관함에서 확인 후\n수신자 이메일 입력하여 발송해 주세요.');
}

// ══════════════════════════════════════════════════
// 헬퍼 함수
// ══════════════════════════════════════════════════

function resetSheet(ss, name) {
  var old = ss.getSheetByName(name);
  var pos = old ? old.getIndex() - 1 : ss.getSheets().length;
  if (old) ss.deleteSheet(old);
  var sh = ss.insertSheet(name, pos);
  sh.setTabColor(C.T_FG);
  return sh;
}

function setColWidths(sh, widths) {
  for (var i = 0; i < widths.length; i++) sh.setColumnWidth(i + 1, widths[i]);
}

function gap(sh, r, h) { sh.setRowHeight(r, h); }

function titleRow(sh, r, label, col, span) {
  sh.setRowHeight(r, 40);
  sh.getRange(r, col, 1, span).merge().setValue(label)
    .setBackground(C.WHITE).setFontColor(C.T_FG)
    .setFontSize(13).setFontWeight('bold').setVerticalAlignment('middle');
}
function subRow(sh, r, label, col, span) {
  sh.setRowHeight(r, 24);
  sh.getRange(r, col, 1, span).merge().setValue(label)
    .setBackground(C.WHITE).setFontColor(C.S_FG)
    .setFontSize(9).setVerticalAlignment('middle');
}
function secRow(sh, r, label, col, span) {
  sh.setRowHeight(r, 30);
  sh.getRange(r, col, 1, span).merge().setValue(label)
    .setBackground(C.S_BG).setFontColor(C.S_FG)
    .setFontSize(10).setFontWeight('bold').setVerticalAlignment('middle');
}
function gameSubRow(sh, r, label, col, span) {
  sh.setRowHeight(r, 26);
  sh.getRange(r, col, 1, span).merge().setValue(label)
    .setBackground(C.GS_BG).setFontColor(C.GS_FG)
    .setFontSize(10).setFontWeight('bold').setVerticalAlignment('middle');
}
function colR(sh, r, col, labels, aligns) {
  sh.setRowHeight(r, 24);
  for (var i = 0; i < labels.length; i++) {
    var align = aligns ? aligns[i] : 'center';
    sh.getRange(r, col + i).setValue(labels[i])
      .setBackground(C.CH_BG).setFontColor(C.CH_FG)
      .setFontSize(9).setFontWeight('bold').setVerticalAlignment('middle')
      .setHorizontalAlignment(align);
  }
}
function kpiR(sh, r, col, items) {
  sh.setRowHeight(r, 32);
  for (var i = 0; i < items.length; i++) {
    var isLabel = (i % 2 === 0);
    sh.getRange(r, col + i).setValue(items[i])
      .setBackground(C.WHITE).setFontSize(10).setFontColor(C.BLACK)
      .setVerticalAlignment('middle').setHorizontalAlignment(isLabel ? 'left' : 'right');
  }
}
function dataR(sh, r, col, values, aligns) {
  sh.setRowHeight(r, 28);
  for (var i = 0; i < values.length; i++) {
    var align = aligns ? aligns[i] : (i === 0 ? 'left' : 'right');
    sh.getRange(r, col + i).setValue(values[i])
      .setBackground(C.WHITE).setFontSize(10).setFontColor(C.BLACK)
      .setVerticalAlignment('middle').setHorizontalAlignment(align);
  }
}
function totalR(sh, r, col, values) {
  sh.setRowHeight(r, 30);
  for (var i = 0; i < values.length; i++) {
    sh.getRange(r, col + i).setValue(values[i])
      .setBackground(C.TOT_BG).setFontColor(C.TOT_FG)
      .setFontSize(10).setFontWeight('bold').setVerticalAlignment('middle')
      .setHorizontalAlignment(i === 0 ? 'left' : 'right');
  }
}

function sortEntries(obj) {
  return Object.keys(obj).map(function(k) { return [k, obj[k]]; })
    .sort(function(a, b) { return b[1] - a[1]; });
}
function extractAmount(name) {
  var m = String(name).match(/[\d,]+원/);
  return m ? m[0] : '';
}
function extractAmountNum(name) {
  var m = String(name).match(/([\d,]+)원/);
  return m ? Number(m[1].replace(/,/g, '')) : 0;
}
function fmtDay(d) {
  return d.getFullYear() + '-' + p2(d.getMonth() + 1) + '-' + p2(d.getDate());
}
function fmtDayFromVal(v) {
  if (!v) return null;
  var d = (v instanceof Date) ? v : new Date(v);
  if (isNaN(d.getTime())) return null;
  return fmtDay(d);
}
function shorten(name) { return String(name).replace('[IBK] ', '').replace('모바일쿠폰샵 ', ''); }
function pct(v, t)     { return t > 0 ? ((v / t) * 100).toFixed(1) + '%' : '-'; }
function p2(v)         { return String(v).padStart(2, '0'); }
function n(v)          { return Number(v).toLocaleString(); }
function fmtDate(d)    { return d.getFullYear() + '.' + p2(d.getMonth() + 1) + '.' + p2(d.getDate()); }
function fmtDT(d)      { return d.getFullYear() + '-' + p2(d.getMonth() + 1) + '-' + p2(d.getDate()) + ' ' + p2(d.getHours()) + ':' + p2(d.getMinutes()); }
function alert_(msg)   { SpreadsheetApp.getUi().alert(msg); }
