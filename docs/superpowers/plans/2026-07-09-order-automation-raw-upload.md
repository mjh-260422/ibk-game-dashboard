# 주문 자동화 로우데이터 업로드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `주문_자동화_script.js`에 여러 `.xls`/`.xlsx` 로우데이터 파일을 앱스크립트 다이얼로그에서 한 번에 첨부하면 자동으로 취합해서 "로우" 탭에 채우는 기능을 추가한다.

**Architecture:** 병합/검증 로직(`mergeRawFiles`)은 GAS API에 의존하지 않는 순수 함수로 작성해 Node.js로 단위 테스트한다. Google Sheets 읽기/쓰기(`processRawFiles`)는 그 순수 함수를 감싸는 얇은 래퍼로만 작성한다. 파일 파싱(xls/xlsx → 2차원 배열)은 브라우저 쪽 다이얼로그(`RawUpload.html`)에서 SheetJS로 처리해 서버로 이미 파싱된 배열만 전달한다.

**Tech Stack:** Google Apps Script (GAS, 클래식 `.gs`/`.html` 파일, clasp 미사용 — 수동 배포), SheetJS(`xlsx.full.min.js`, CDN), Node.js 내장 테스트 러너(`node --test`, 별도 패키지 설치 없음 — 이 저장소에 `package.json`/테스트 프레임워크가 없으므로 새 의존성을 추가하지 않음).

## Global Constraints
- 시트 편집 권한만 있으면 추가 설정(Drive API 활성화, OAuth 스코프 등) 없이 사용 가능해야 함 — Drive API 변환 방식 금지
- 병합 시 파일 간 헤더(컬럼명·순서)가 하나라도 다르면 전체 중단, "로우" 탭은 변경하지 않음 (부분 병합 금지)
- 데이터 누적 없음 — 업로드마다 "로우" 탭 전체 내용을 새 병합 결과로 완전히 대체
- "변환 & 파일 저장"(`convertAndSave`)과는 분리 — 업로드 후 자동으로 이어서 실행하지 않음
- `.xls`(레거시 BIFF) 파싱을 위해 클라이언트에서 `xlsx.full.min.js`(mini 빌드 금지) 사용

---

### Task 1: 병합/검증 순수 로직 (`mergeRawFiles`) — TDD

**Files:**
- Modify: `업무_우리카드구간포상/주문_자동화_script.js` (파일 맨 끝에 추가)
- Create: `업무_우리카드구간포상/주문_자동화_script.test.js`

**Interfaces:**
- Produces: `mergeRawFiles(filesData)` — `filesData`는 `[{ name: string, rows: any[][] }]` (각 파일의 시트를 2차원 배열로, 1행이 헤더). 반환값은 성공 시 `{ header: string[], rows: any[][], log: string[] }` (rows는 헤더 포함 전체 병합 결과), 실패 시 `{ error: string }`.

- [ ] **Step 1: 테스트 파일 작성 (실패하는 테스트)**

`업무_우리카드구간포상/주문_자동화_script.test.js` 생성:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { mergeRawFiles } = require('./주문_자동화_script.js');

test('병합: 헤더가 같은 파일 여러 개는 순서대로 이어붙인다', () => {
  const filesData = [
    { name: 'a.xls', rows: [['번호', '이름'], ['1', '홍길동'], ['2', '김철수']] },
    { name: 'b.xls', rows: [['번호', '이름'], ['3', '이영희']] }
  ];
  const result = mergeRawFiles(filesData);
  assert.equal(result.error, undefined);
  assert.deepEqual(result.header, ['번호', '이름']);
  assert.deepEqual(result.rows, [
    ['번호', '이름'],
    ['1', '홍길동'],
    ['2', '김철수'],
    ['3', '이영희']
  ]);
  assert.deepEqual(result.log, ['a.xls: 2행', 'b.xls: 1행']);
});

test('헤더가 다른 파일이 섞여 있으면 에러를 반환하고 병합하지 않는다', () => {
  const filesData = [
    { name: 'a.xls', rows: [['번호', '이름'], ['1', '홍길동']] },
    { name: 'b.xls', rows: [['이름', '번호'], ['2', '김철수']] }
  ];
  const result = mergeRawFiles(filesData);
  assert.match(result.error, /b\.xls/);
  assert.equal(result.rows, undefined);
});

test('행마다 열 개수가 다르면 기준 헤더 길이에 맞춰 채우거나 자른다', () => {
  const filesData = [
    { name: 'a.xls', rows: [['번호', '이름', '전화'], ['1', '홍길동']] }
  ];
  const result = mergeRawFiles(filesData);
  assert.deepEqual(result.rows[1], ['1', '홍길동', '']);
});

test('파일이 하나도 없으면 에러를 반환한다', () => {
  const result = mergeRawFiles([]);
  assert.match(result.error, /선택된 파일이 없습니다/);
});

test('파일에 데이터 행이 하나도 없으면 에러를 반환한다', () => {
  const result = mergeRawFiles([{ name: 'empty.xls', rows: [] }]);
  assert.match(result.error, /empty\.xls/);
});
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `node --test "업무_우리카드구간포상/주문_자동화_script.test.js"`
Expected: FAIL (`mergeRawFiles is not a function` 또는 `Cannot find module` 관련 에러 — 아직 구현/export 없음)

- [ ] **Step 3: `mergeRawFiles` 구현 + Node에서 테스트 가능하도록 export**

`업무_우리카드구간포상/주문_자동화_script.js` 파일 맨 끝(마지막 `checkSheetNames` 함수 뒤)에 추가:

```js


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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `node --test "업무_우리카드구간포상/주문_자동화_script.test.js"`
Expected: PASS — 5개 테스트 모두 통과 (`# pass 5`, `# fail 0`)

- [ ] **Step 5: GAS 문법 오류 없는지 확인**

Run: `node --check "업무_우리카드구간포상/주문_자동화_script.js"`
Expected: 아무 출력 없이 종료 (exit code 0) — `SpreadsheetApp` 등 GAS 전역객체는 함수 바디 안에서만 참조되므로 `--check`(파싱만, 실행 안 함)는 문제없이 통과함

- [ ] **Step 6: 커밋**

```bash
git add "업무_우리카드구간포상/주문_자동화_script.js" "업무_우리카드구간포상/주문_자동화_script.test.js"
git commit -m "feat: 로우데이터 다중 파일 병합/검증 순수 로직 추가"
```

---

### Task 2: GAS I/O 래퍼 + 메뉴 연동

**Files:**
- Modify: `업무_우리카드구간포상/주문_자동화_script.js:6-15` (CONFIG), `:36-43` (onOpen), 파일 끝 (Task 1에서 추가한 함수들 뒤)

**Interfaces:**
- Consumes: `mergeRawFiles(filesData)` — Task 1에서 정의한 반환 형태 `{header, rows, log}` 또는 `{error}`
- Produces: `processRawFiles(filesData)` — 반환값 `{ success: boolean, message: string }`. `RawUpload.html`(Task 3)이 `google.script.run.processRawFiles(filesData)`로 호출하는 이름/형태이므로 그대로 유지해야 함. `showRawUploadDialog()` — 메뉴에서 호출하는 함수명, `RawUpload.html` 파일명을 참조.

- [ ] **Step 1: CONFIG에 로우 탭 이름 추가**

`업무_우리카드구간포상/주문_자동화_script.js`의 CONFIG 블록을 다음으로 교체:

```js
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
```

- [ ] **Step 2: onOpen 메뉴에 항목 추가**

`onOpen()` 함수를 다음으로 교체:

```js
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("주문 자동화")
    .addItem("로우데이터 업로드", "showRawUploadDialog")
    .addItem("변환 & 파일 저장 (전체 실행)", "convertAndSave")
    .addSeparator()
    .addItem("상품 마스터 시트 만들기", "createMasterSheet")
    .addToUi();
}
```

- [ ] **Step 3: `showRawUploadDialog` / `processRawFiles` 추가**

Task 1에서 추가한 `mergeRawFiles` 함수 바로 앞에 삽입 (즉 `checkSheetNames` 함수와 `mergeRawFiles` 함수 사이):

```js


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
```

- [ ] **Step 4: 문법 확인 + 기존 테스트 재확인**

Run: `node --check "업무_우리카드구간포상/주문_자동화_script.js" && node --test "업무_우리카드구간포상/주문_자동화_script.test.js"`
Expected: `--check` 통과(무출력), 5개 테스트 모두 PASS (`processRawFiles`/`showRawUploadDialog`는 `SpreadsheetApp`/`HtmlService`를 함수 바디에서만 쓰므로 require 시점에는 실행되지 않아 테스트에 영향 없음)

- [ ] **Step 5: 커밋**

```bash
git add "업무_우리카드구간포상/주문_자동화_script.js"
git commit -m "feat: 로우데이터 업로드 메뉴/서버 함수 연동"
```

---

### Task 3: 업로드 다이얼로그 (`RawUpload.html`)

**Files:**
- Create: `업무_우리카드구간포상/RawUpload.html`

**Interfaces:**
- Consumes: 서버 함수 `processRawFiles(filesData)` (Task 2) — `filesData`는 `[{name, rows}]` 형태로 호출해야 함 (Task 1의 `mergeRawFiles` 입력 형태와 동일)

- [ ] **Step 1: 다이얼로그 HTML 작성**

`업무_우리카드구간포상/RawUpload.html` 생성:

```html
<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <script src="https://cdn.sheetjs.com/xlsx-0.20.2/package/dist/xlsx.full.min.js"></script>
  <style>
    body { font-family: Arial, sans-serif; padding: 20px; font-size: 14px; }
    .drop-area {
      border: 2px dashed #ccc; border-radius: 8px; padding: 28px;
      text-align: center; cursor: pointer; color: #555;
      transition: all 0.2s;
    }
    .drop-area:hover, .drop-area.hover { border-color: #4285f4; background: #e8f0fe; }
    #fileList { margin-top: 12px; font-size: 13px; color: #333; line-height: 1.8; }
    .warning { margin-top: 14px; padding: 10px; background: #fef7e0; border-radius: 4px; font-size: 13px; color: #7a5b00; }
    #confirmRow { margin-top: 10px; font-size: 13px; }
    #uploadBtn {
      margin-top: 14px; padding: 9px 24px;
      background: #4285f4; color: white; border: none;
      border-radius: 4px; cursor: pointer; font-size: 14px; width: 100%;
    }
    #uploadBtn:disabled { background: #ccc; cursor: not-allowed; }
    #status { margin-top: 12px; font-size: 13px; white-space: pre-wrap; color: #333; }
    .success { color: #0f9d58; }
    .error { color: #d93025; }
  </style>
</head>
<body>
  <div class="drop-area" id="dropArea" onclick="document.getElementById('fileInput').click()">
    📂 여기를 클릭해서 로우데이터 파일 선택 (여러 개 가능)<br>
    <small style="color:#aaa">관리용_YYYYMMDDHHMMSS.xls 등</small>
  </div>
  <input type="file" id="fileInput" accept=".xls,.xlsx" multiple style="display:none">
  <div id="fileList"></div>

  <div class="warning">⚠️ 선택한 파일로 "로우" 탭의 기존 내용을 모두 삭제하고 대체합니다.</div>
  <div id="confirmRow">
    <label><input type="checkbox" id="confirmCheck"> 확인했습니다. 기존 "로우" 탭 내용을 삭제하고 덮어씁니다.</label>
  </div>

  <button id="uploadBtn" onclick="upload()" disabled>업로드</button>
  <div id="status"></div>

  <script>
    var selectedFiles = [];

    function updateButtonState() {
      document.getElementById('uploadBtn').disabled =
        !(selectedFiles.length > 0 && document.getElementById('confirmCheck').checked);
    }

    document.getElementById('fileInput').addEventListener('change', function(e) {
      selectedFiles = Array.from(e.target.files);
      var list = selectedFiles.map(function(f) { return '✓ ' + f.name; }).join('<br>');
      document.getElementById('fileList').innerHTML = list;
      updateButtonState();
    });

    document.getElementById('confirmCheck').addEventListener('change', updateButtonState);

    function readAsArrayBuffer(file) {
      return new Promise(function(resolve, reject) {
        var reader = new FileReader();
        reader.onload = function(e) { resolve(e.target.result); };
        reader.onerror = function() { reject(new Error(file.name + ' 읽기 실패')); };
        reader.readAsArrayBuffer(file);
      });
    }

    function upload() {
      var btn = document.getElementById('uploadBtn');
      var status = document.getElementById('status');
      btn.disabled = true;
      status.className = '';
      status.textContent = '파싱 중...';

      var filesData = [];
      var files = selectedFiles;
      var i = 0;

      function next() {
        if (i >= files.length) {
          status.textContent = '업로드 중...';
          google.script.run
            .withSuccessHandler(function(result) {
              status.className = result.success ? 'success' : 'error';
              status.textContent = result.message;
              updateButtonState();
            })
            .withFailureHandler(function(err) {
              status.className = 'error';
              status.textContent = '오류: ' + err.message;
              updateButtonState();
            })
            .processRawFiles(filesData);
          return;
        }
        var file = files[i];
        readAsArrayBuffer(file).then(function(buffer) {
          try {
            var wb = XLSX.read(buffer, { type: 'array' });
            var sheet = wb.Sheets[wb.SheetNames[0]];
            var rows = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: false, defval: '' });
            filesData.push({ name: file.name, rows: rows });
          } catch (e) {
            status.className = 'error';
            status.textContent = '오류: ' + file.name + ' 파싱 실패 (' + e.message + ')';
            btn.disabled = false;
            return;
          }
          i++;
          next();
        }).catch(function(err) {
          status.className = 'error';
          status.textContent = '오류: ' + err.message;
          btn.disabled = false;
        });
      }
      next();
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: 정적 검증 — 서버 함수명이 Task 2와 정확히 일치하는지 확인**

Run (Windows PowerShell): `Select-String -Path "업무_우리카드구간포상/RawUpload.html" -Pattern "processRawFiles"`
Expected: 1건 매치 (`.processRawFiles(filesData);`) — Task 2에서 정의한 `processRawFiles`와 이름이 정확히 같아야 함. 다르면 오타이므로 수정.

- [ ] **Step 3: 커밋**

```bash
git add "업무_우리카드구간포상/RawUpload.html"
git commit -m "feat: 로우데이터 업로드 다이얼로그 HTML 추가"
```

---

### Task 4: Apps Script 배포 + 실제 파일로 최종 확인 (사용자 수동 진행)

이 저장소에는 clasp 설정이 없어(배포용 `.clasp.json` 없음) Apps Script 배포는 항상 Google Sheets 편집기에서 수동으로 코드를 붙여넣는 방식이다. 이 태스크는 어떤 에이전트도 대신 실행할 수 없는 사용자 액션이며, 완료 여부를 사용자가 직접 확인해줘야 한다.

- [ ] **Step 1: 스크립트 코드 반영**

Google Sheets(`1Ce3swcsiFJLRW9dnAqnvXjmPmh2istTASiHOwCbnUiU`) 열기 → 확장 프로그램 > Apps Script → 기존 스크립트 파일(주문 자동화 관련)의 코드를 전체 선택 후 Task 1~2에서 완성된 로컬 `업무_우리카드구간포상/주문_자동화_script.js` 전체 내용으로 교체 → 저장(Ctrl+S).

- [ ] **Step 2: HTML 파일 추가**

Apps Script 편집기에서 파일 추가(+) → HTML 선택 → 파일명 `RawUpload`로 저장 → 로컬 `업무_우리카드구간포상/RawUpload.html` 전체 내용을 붙여넣기 → 저장.

- [ ] **Step 3: 시트로 돌아와 새로고침 후 메뉴 확인**

Google Sheets 탭을 새로고침 → 상단 메뉴에 "주문 자동화 > 로우데이터 업로드" 항목이 보이는지 확인 (Apps Script 승인 팝업이 뜨면 권한 승인).

- [ ] **Step 4: 실제 샘플 파일로 업로드 테스트**

"로우데이터 업로드" 클릭 → `업무_우리카드구간포상/0529/배송 로우/` 폴더의 `.xls` 파일 4개를 모두 선택 → 확인 체크박스 체크 → 업로드.
Expected: 완료 메시지에 총 123행 병합 표시 (83+13+7+20), "로우" 탭에 헤더 1행 + 데이터 123행 = 총 124행 채워짐 (기존 팩트체크에서 확인한 수치와 일치).

- [ ] **Step 5: 헤더 불일치 시 중단되는지 확인**

같은 폴더의 파일 중 하나를 복사해 임의로 한 컬럼명을 바꾼 테스트용 파일을 만들어(또는 다른 헤더를 가진 임의 xls) 정상 파일과 함께 업로드 → 에러 메시지가 뜨고 "로우" 탭 내용이 Step 4 결과 그대로 유지되는지 확인.

- [ ] **Step 6: 기존 기능 회귀 확인**

"주문 자동화 > 변환 & 파일 저장 (전체 실행)"을 그대로 실행해 기존 동작(경영지원팀_전달용/구매품의서 생성, 우리카드 구간포상 시트 반영)이 변경 전과 동일하게 동작하는지 확인.
