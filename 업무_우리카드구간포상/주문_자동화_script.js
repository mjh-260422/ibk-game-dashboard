// ============================================================
//  주문 데이터 자동 변환 + 품의서 생성 + 우리카드 구간포상 누적 스크립트 최종
//  설치 위치: Google Sheets > 확장 프로그램 > Apps Script
// ============================================================

var CONFIG = {
  RAW_SHEET_NAME: "로우",
  MASTER_SHEET_NAME: "상품마스터",
  MASTER_COL_PRODUCT_NAME:  "상품",
  MASTER_COL_PURCHASE_URL:  "구매링크",
  MASTER_COL_BILLING_PRICE: "청구가",
  OUTPUT_SHEET_NAME:      "경영지원팀_전달용",
  REQUISITION_SHEET_NAME: "구매품의서",
  WOORICRD_SS_ID: "17qJfmlYUXcI74oOxZqJ6DpjJ9mlBv5aRRr3gnb-fVHI",
  WOORICRD_SHEET_NAME: "실물 배송"
};


function formatPhone(value) {
  if (!value) return "";
  var str = String(value).trim().replace(/[^0-9]/g, "");
  if (str.length === 9)       str = "0" + str;
  else if (str.length === 10) str = "0" + str;
  if (str.length === 11) return str;
  return str;
}


function extractZoneSu(mediaName) {
  if (!mediaName) return "";
  var match = String(mediaName).match(/\((\d+)\)/);
  if (!match) return "";
  return String(parseInt(match[1], 10));
}


function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("주문 자동화")
    .addItem("로우데이터 업로드", "showRawUploadDialog")
    .addItem("변환 & 파일 저장 (전체 실행)", "convertAndSave")
    .addSeparator()
    .addItem("상품 마스터 시트 만들기", "createMasterSheet")
    .addToUi();
}


function convertAndSave() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ui = SpreadsheetApp.getUi();

  var rawSheet = ss.getActiveSheet();
  var skipNames = [CONFIG.OUTPUT_SHEET_NAME, CONFIG.MASTER_SHEET_NAME, CONFIG.REQUISITION_SHEET_NAME];
  if (skipNames.indexOf(rawSheet.getName()) !== -1) {
    ui.alert("로우데이터 시트를 선택한 뒤 실행해주세요.");
    return;
  }

  var rawData = rawSheet.getDataRange().getValues();
  if (rawData.length < 2) {
    ui.alert("데이터가 없습니다.");
    return;
  }

  var headers = rawData[0].map(function(h) { return String(h).trim(); });

  function col(name) {
    var idx = headers.indexOf(name);
    if (idx === -1) throw new Error('"' + name + '" 컬럼을 찾을 수 없습니다.');
    return idx;
  }

  var CI;
  try {
    CI = {
      orderNo:   headers.indexOf("구매번호") !== -1 ? headers.indexOf("구매번호") : -1,
      mediaName: headers.indexOf("매체명")   !== -1 ? headers.indexOf("매체명")   : -1,
      name:      col("이름"),
      phone:     col("연락처"),
      tel:       headers.indexOf("전화번호") !== -1 ? headers.indexOf("전화번호") : -1,
      zip:       col("우편번호"),
      address:   col("주소"),
      product:   col("상품명"),
      qty:       col("수량"),
      note:      col("유의사항"),
      shipDate:  headers.indexOf("배송요청일") !== -1 ? headers.indexOf("배송요청일") : -1
    };
  } catch (e) {
    ui.alert("오류: " + e.message + "\n로우데이터 헤더명을 확인해주세요.");
    return;
  }

  // 1단계: 구매번호 기준 중복 제거 (같은 구매번호 2번 이상이면 둘 다 스킵)
  var keyCounts = {};
  for (var i = 1; i < rawData.length; i++) {
    var row = rawData[i];
    if (!row[CI.name]) continue;
    var key = (CI.orderNo !== -1 && row[CI.orderNo])
      ? String(row[CI.orderNo]).trim()
      : String(row[CI.name]).trim() + "|" + String(row[CI.phone]).trim() + "|" + String(row[CI.product]).trim();
    keyCounts[key] = (keyCounts[key] || 0) + 1;
  }

  var dedupData = [];
  var dupCount = { count: 0 };
  for (var i = 1; i < rawData.length; i++) {
    var row = rawData[i];
    if (!row[CI.name]) continue;
    var key = (CI.orderNo !== -1 && row[CI.orderNo])
      ? String(row[CI.orderNo]).trim()
      : String(row[CI.name]).trim() + "|" + String(row[CI.phone]).trim() + "|" + String(row[CI.product]).trim();
    if (keyCounts[key] > 1) { dupCount.count++; continue; }
    dedupData.push(row);
  }

  // 2단계: 실물 배송 시트 기배송 건 제외
  var shippedPhones = getShippedPhones();
  var alreadyShippedCount = 0;
  var finalData = [];
  for (var i = 0; i < dedupData.length; i++) {
    var phone = String(dedupData[i][CI.phone] || "").replace(/\D/g, "");
    if (shippedPhones[phone]) {
      alreadyShippedCount++;
    } else {
      finalData.push(dedupData[i]);
    }
  }

  // 상품 마스터 Map 빌드
  var masterSheet = ss.getSheetByName(CONFIG.MASTER_SHEET_NAME);
  if (!masterSheet) {
    ui.alert('"' + CONFIG.MASTER_SHEET_NAME + '" 시트를 찾을 수 없습니다.');
    return;
  }

  var masterData = masterSheet.getDataRange().getValues();
  var masterHead = masterData[0].map(function(h) { return String(h).trim(); });

  function mCol(name) {
    var idx = masterHead.indexOf(name);
    if (idx === -1) throw new Error('마스터 시트에서 "' + name + '" 컬럼을 찾을 수 없습니다.');
    return idx;
  }

  var mCI;
  try {
    var latestPriceIdx = -1;
    for (var i = 0; i < masterHead.length; i++) {
      var h = String(masterHead[i]);
      if (h.endsWith("매입가") && /^\d/.test(h)) latestPriceIdx = i;
    }
    if (latestPriceIdx === -1) throw new Error("마스터 시트에서 날짜+매입가 형식의 컬럼을 찾을 수 없습니다. (예: 0311매입가)");
    Logger.log("사용 중인 매입가 컬럼: " + masterHead[latestPriceIdx]);
    mCI = {
      name:          mCol(CONFIG.MASTER_COL_PRODUCT_NAME),
      purchasePrice: latestPriceIdx,
      billingPrice:  mCol(CONFIG.MASTER_COL_BILLING_PRICE),
      url:           mCol(CONFIG.MASTER_COL_PURCHASE_URL)
    };
  } catch (e) {
    ui.alert("오류: " + e.message);
    return;
  }

  var productMap = {};
  for (var i = 1; i < masterData.length; i++) {
    var row = masterData[i];
    var name = String(row[mCI.name] || "").trim();
    if (name) {
      productMap[name] = {
        purchasePrice: Number(row[mCI.purchasePrice]) || 0,
        billingPrice:  Number(row[mCI.billingPrice])  || 0,
        url:           row[mCI.url]
      };
    }
  }

  var today = Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd");
  var warnings = [];
  makeOutputSheet(ss, finalData, CI, productMap, today, warnings);
  makeRequisitionSheet(ss, finalData, CI, productMap, today);
  appendToWooriCard(finalData, CI);

  var msg = "완료!\n\n전달 건수: " + finalData.length + "건\n"
    + "생성/갱신 시트:\n"
    + "  " + CONFIG.OUTPUT_SHEET_NAME + "\n"
    + "  " + CONFIG.REQUISITION_SHEET_NAME + "\n"
    + "  [2026 우리카드 구간포상 이벤트] > " + CONFIG.WOORICRD_SHEET_NAME;
  if (dupCount.count > 0)      msg += "\n\n중복 제거: " + dupCount.count + "건";
  if (alreadyShippedCount > 0) msg += "\n기배송 제외: " + alreadyShippedCount + "건";
  if (warnings.length > 0)     msg += "\n마스터 미등록: " + warnings.length + "건";

  ui.alert(msg);
}


// 실물 배송 시트에서 이미 처리된 전화번호 객체 반환 {phone: true}
function getShippedPhones() {
  try {
    var ss = SpreadsheetApp.openById(CONFIG.WOORICRD_SS_ID);
    var sheet = ss.getSheetByName(CONFIG.WOORICRD_SHEET_NAME);
    if (!sheet) return {};
    var lastRow = sheet.getLastRow();
    if (lastRow <= 3) return {};
    var values = sheet.getRange(4, 4, lastRow - 3, 1).getValues();
    var phoneObj = {};
    for (var i = 0; i < values.length; i++) {
      var p = String(values[i][0]).replace(/\D/g, "");
      if (p) phoneObj[p] = true;
    }
    return phoneObj;
  } catch(e) {
    Logger.log("실물 배송 시트 로드 실패: " + e);
    return {};
  }
}


function makeOutputSheet(ss, dedupData, CI, productMap, today, warnings) {
  var outputRows = [["No.", "이름", "연락처", "우편번호", "주소", "배송메시지", "상품명", "구매링크", "구매가", "상품수량"]];

  var no = 1;
  for (var i = 0; i < dedupData.length; i++) {
    var row = dedupData[i];
    var productName = String(row[CI.product] || "").trim().replace(/^\[우리카드\][_ ]?/i, "");
    var info = productMap[productName];
    if (!info) warnings.push('"' + productName + '" - 마스터에 없는 상품명');

    outputRows.push([
      no++,
      row[CI.name]    || "",
      formatPhone(row[CI.phone]),
      String(row[CI.zip] || "").padStart(5, "0"),
      row[CI.address] || "",
      row[CI.note]    || "",
      productName,
      info ? info.url           : "마스터 없음",
      info ? info.purchasePrice : 0,
      Number(row[CI.qty]) || 0
    ]);
  }

  var sheet = ss.getSheetByName(CONFIG.OUTPUT_SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(CONFIG.OUTPUT_SHEET_NAME);
  else sheet.clearContents();

  sheet.getRange(1, 1, outputRows.length, outputRows[0].length).setValues(outputRows);
  sheet.getRange(1, 1, 1, outputRows[0].length)
    .setBackground("#185FA5").setFontColor("#ffffff").setFontWeight("bold");
  sheet.setFrozenRows(1);

  if (outputRows.length > 1) {
    var dr = outputRows.length - 1;
    sheet.getRange(2, 3, dr, 1).setNumberFormat("@");
    sheet.getRange(2, 4, dr, 1).setNumberFormat("@");
    sheet.getRange(2, 9, dr, 1).setNumberFormat("#,##0");
    sheet.getRange(2, 10, dr, 1).setNumberFormat("#,##0");
  }

  sheet.autoResizeColumns(1, outputRows[0].length);
}


function makeRequisitionSheet(ss, dedupData, CI, productMap, today) {
  var sheet = ss.getSheetByName(CONFIG.REQUISITION_SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(CONFIG.REQUISITION_SHEET_NAME);
  else sheet.clearContents();

  var productQty = {};
  for (var i = 0; i < dedupData.length; i++) {
    var row = dedupData[i];
    var name = String(row[CI.product] || "").trim().replace(/^\[우리카드\][_ ]?/i, "");
    var qty = Number(row[CI.qty]) || 1;
    if (!name) continue;
    productQty[name] = (productQty[name] || 0) + qty;
  }

  var dataRows = [];
  var keys = Object.keys(productQty);
  for (var i = 0; i < keys.length; i++) {
    var name = keys[i];
    var qty = productQty[name];
    var info = productMap[name];
    var purchasePrice = info ? info.purchasePrice : 0;
    var billingPrice  = info ? info.billingPrice  : 0;
    dataRows.push([name, purchasePrice, qty, purchasePrice * qty, billingPrice * qty]);
  }

  var totalPurchaseSum = 0, totalBillingSum = 0;
  for (var i = 0; i < dataRows.length; i++) {
    totalPurchaseSum += dataRows[i][3];
    totalBillingSum  += dataRows[i][4];
  }
  var profit     = totalBillingSum - totalPurchaseSum;
  var profitRate = totalBillingSum > 0
    ? Math.round(profit / totalBillingSum * 100) + "%" : "0%";

  sheet.getRange("A1").setValue(today).setFontWeight("bold");

  sheet.getRange(3, 1, 1, 5).setValues([["상품명", "구매가", "수량", "총 구매가", "총 청구가"]])
    .setBackground("#1D9E75").setFontColor("#ffffff").setFontWeight("bold").setHorizontalAlignment("center");

  if (dataRows.length > 0) {
    sheet.getRange(4, 1, dataRows.length, 5).setValues(dataRows);
    sheet.getRange(4, 2, dataRows.length, 4).setNumberFormat("#,##0");
  }

  var sumRow = dataRows.length + 4;
  var totalQty = 0;
  for (var i = 0; i < dataRows.length; i++) totalQty += dataRows[i][2];
  sheet.getRange(sumRow, 1).setValue("합계");
  sheet.getRange(sumRow, 3).setValue(totalQty);
  sheet.getRange(sumRow, 4).setValue(totalPurchaseSum);
  sheet.getRange(sumRow, 5).setValue(totalBillingSum);
  sheet.getRange(sumRow, 1, 1, 5).setBackground("#E1F5EE").setFontWeight("bold");
  sheet.getRange(sumRow, 3, 1, 3).setNumberFormat("#,##0");

  sheet.getRange(3, 7, 1, 4).setValues([["구매금액", "청구금액", "수익금액", "수익률"]])
    .setBackground("#185FA5").setFontColor("#ffffff").setFontWeight("bold").setHorizontalAlignment("center");
  sheet.getRange(4, 7, 1, 4).setValues([[totalPurchaseSum, totalBillingSum, profit, profitRate]]);
  sheet.getRange(4, 7, 1, 3).setNumberFormat("#,##0");
  sheet.getRange(4, 10).setHorizontalAlignment("center");

  sheet.getRange(3, 1, dataRows.length + 2, 5).setBorder(true, true, true, true, true, true);
  sheet.getRange(3, 7, 2, 4).setBorder(true, true, true, true, true, true);

  sheet.setColumnWidth(1, 220); sheet.setColumnWidth(2, 90);
  sheet.setColumnWidth(3, 60);  sheet.setColumnWidth(4, 100);
  sheet.setColumnWidth(5, 100); sheet.setColumnWidth(6, 30);
  sheet.setColumnWidth(7, 100); sheet.setColumnWidth(8, 100);
  sheet.setColumnWidth(9, 100); sheet.setColumnWidth(10, 80);
}


function appendToWooriCard(dedupData, CI) {
  var targetSS    = SpreadsheetApp.openById(CONFIG.WOORICRD_SS_ID);
  var targetSheet = targetSS.getSheetByName(CONFIG.WOORICRD_SHEET_NAME);

  if (!targetSheet) {
    SpreadsheetApp.getUi().alert('"' + CONFIG.WOORICRD_SHEET_NAME + '" 시트를 찾을 수 없습니다.');
    return;
  }

  var lastRow = targetSheet.getLastRow();
  var lastNo  = lastRow <= 1 ? 0 : Number(targetSheet.getRange(lastRow, 1).getValue()) || lastRow - 1;

  var appendRows = [];
  var no = lastNo + 1;

  for (var i = 0; i < dedupData.length; i++) {
    var row = dedupData[i];
    var rawTel   = CI.tel !== -1 ? row[CI.tel] : row[CI.phone];
    var phoneStr = formatPhone(rawTel);
    var zoneSu   = CI.mediaName !== -1 ? extractZoneSu(row[CI.mediaName]) : "";

    var sendMonth   = "";
    var shipDateFmt = "";
    if (CI.shipDate !== -1 && row[CI.shipDate]) {
      var raw = String(row[CI.shipDate]).trim().replace(/[^0-9]/g, "");
      if (raw.length === 8) {
        var yyyy = raw.slice(0, 4);
        var mm   = raw.slice(4, 6);
        var dd   = raw.slice(6, 8);
        sendMonth   = String(parseInt(mm, 10));
        shipDateFmt = yyyy + "-" + mm + "-" + dd;
      }
    }

    appendRows.push([no++, sendMonth, zoneSu, phoneStr, shipDateFmt, "", "", "", "", "", "", "", ""]);
  }

  if (appendRows.length > 0) {
    var startRow = targetSheet.getLastRow() + 1;
    targetSheet.getRange(startRow, 1, appendRows.length, 13).setValues(appendRows);
    targetSheet.getRange(startRow, 4, appendRows.length, 1).setNumberFormat("@");
    targetSheet.getRange(startRow, 2, appendRows.length, 1).setNumberFormat("@");
    targetSheet.getRange(startRow, 3, appendRows.length, 1).setNumberFormat("@");
  }
}


function createMasterSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  if (ss.getSheetByName(CONFIG.MASTER_SHEET_NAME)) {
    SpreadsheetApp.getUi().alert('"' + CONFIG.MASTER_SHEET_NAME + '" 시트가 이미 존재합니다.');
    return;
  }

  var sheet = ss.insertSheet(CONFIG.MASTER_SHEET_NAME);
  var headers = [["달성구간(社)", "No.", "상품", "구분", "0311매입가", "매입가", "전시가", "청구가", "구매링크"]];
  sheet.getRange(1, 1, 1, headers[0].length).setValues(headers);
  sheet.getRange(1, 1, 1, headers[0].length)
    .setBackground("#0F6E56").setFontColor("#ffffff").setFontWeight("bold");

  sheet.getRange(2, 1, 2, 9).setValues([
    ["A구간", 1, "스타벅스 아메리카노 T", "음료권", 4000, 4200, 4800, 4500, "https://example.com/1"],
    ["B구간", 2, "CU 편의점 1만원권", "금액권", 9500, 9700, 10000, 9800, "https://example.com/2"]
  ]);
  sheet.autoResizeColumns(1, headers[0].length);
  SpreadsheetApp.getUi().alert('"' + CONFIG.MASTER_SHEET_NAME + '" 시트를 만들었습니다.');
}


function checkSheetNames() {
  var ss = SpreadsheetApp.openById("1Ce3swcsiFJLRW9dnAqnvXjmPmh2istTASiHOwCbnUiU");
  var names = ss.getSheets().map(function(s) { return '"' + s.getName() + '"'; }).join("\n");
  SpreadsheetApp.getUi().alert("시트 목록:\n" + names);
}


function showRawUploadDialog() {
  var html = HtmlService.createHtmlOutputFromFile('RawUpload')
    .setWidth(480)
    .setHeight(440);
  SpreadsheetApp.getUi().showModalDialog(html, '로우데이터 업로드');
}


function processRawFiles(filesData) {
  var merged = mergeRawFiles(filesData);
  if (merged.error) {
    return { success: false, message: merged.error };
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CONFIG.RAW_SHEET_NAME);
  if (!sheet) {
    return { success: false, message: '"' + CONFIG.RAW_SHEET_NAME + '" 탭을 찾을 수 없습니다.' };
  }

  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow > 0 && lastCol > 0) {
    sheet.getRange(1, 1, lastRow, lastCol).clearContent();
  }

  sheet.getRange(1, 1, merged.rows.length, merged.header.length).setValues(merged.rows);

  var totalRows = merged.rows.length - 1;
  return {
    success: true,
    message: '완료: 총 ' + totalRows + '행 병합\n\n' + merged.log.join('\n')
  };
}


function mergeRawFiles(filesData) {
  if (!filesData || filesData.length === 0) {
    return { error: '선택된 파일이 없습니다.' };
  }

  var firstRows = filesData[0].rows;
  if (!firstRows || firstRows.length === 0) {
    return { error: filesData[0].name + ': 빈 파일입니다.' };
  }
  var canonicalHeader = firstRows[0].map(function(h) { return String(h).trim(); });

  var mergedRows = [canonicalHeader];
  var log = [];

  for (var f = 0; f < filesData.length; f++) {
    var file = filesData[f];
    var rows = file.rows;
    if (!rows || rows.length === 0) {
      return { error: file.name + ': 빈 파일입니다.' };
    }
    var header = rows[0].map(function(h) { return String(h).trim(); });
    if (JSON.stringify(header) !== JSON.stringify(canonicalHeader)) {
      return {
        error: file.name + '의 헤더가 ' + filesData[0].name + '와 다릅니다.\n\n'
          + '기준: ' + canonicalHeader.join(', ') + '\n\n'
          + file.name + ': ' + header.join(', ')
      };
    }

    var dataRows = rows.slice(1).map(function(row) {
      var padded = row.slice(0, canonicalHeader.length);
      while (padded.length < canonicalHeader.length) padded.push('');
      return padded;
    });
    mergedRows = mergedRows.concat(dataRows);
    log.push(file.name + ': ' + dataRows.length + '행');
  }

  return { header: canonicalHeader, rows: mergedRows, log: log };
}


if (typeof module !== 'undefined') {
  module.exports = { mergeRawFiles: mergeRawFiles };
}
