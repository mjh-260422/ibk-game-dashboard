const test = require('node:test');
const assert = require('node:assert/strict');
const { mergeRawFiles, stripWooriPrefix, extractSendMonth } = require('./주문_자동화_script.js');

test('stripWooriPrefix: "[우리카드]_" 접두사를 제거한다', () => {
  assert.equal(stripWooriPrefix('[우리카드]_다이슨 슈퍼소닉 뉴럴 헤어 드라이기'), '다이슨 슈퍼소닉 뉴럴 헤어 드라이기');
});

test('stripWooriPrefix: "[우리카드] " (공백) 접두사도 제거한다', () => {
  assert.equal(stripWooriPrefix('[우리카드] 스타벅스 아메리카노'), '스타벅스 아메리카노');
});

test('stripWooriPrefix: 접두사가 없으면 그대로 반환한다(양쪽 공백만 정리)', () => {
  assert.equal(stripWooriPrefix('  스타벅스 아메리카노  '), '스타벅스 아메리카노');
});

test('extractSendMonth: 배송요청일(YYYYMMDD)에서 월을 숫자 문자열로 추출한다', () => {
  assert.equal(extractSendMonth(['20260707'], { shipDate: 0 }), '7');
  assert.equal(extractSendMonth(['20261203'], { shipDate: 0 }), '12');
});

test('extractSendMonth: shipDate 컬럼이 없거나 형식이 다르면 빈 문자열을 반환한다', () => {
  assert.equal(extractSendMonth(['20260707'], { shipDate: -1 }), '');
  assert.equal(extractSendMonth(['2026-07-07 10:30'], { shipDate: 0 }), '');
  assert.equal(extractSendMonth([''], { shipDate: 0 }), '');
});

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

test('헤더만 있고 데이터 행이 없는 파일은 에러 없이 0행으로 취급한다', () => {
  const filesData = [
    { name: 'header-only.xls', rows: [['번호', '이름']] },
    { name: 'b.xls', rows: [['번호', '이름'], ['1', '홍길동']] }
  ];
  const result = mergeRawFiles(filesData);
  assert.equal(result.error, undefined);
  assert.deepEqual(result.rows, [
    ['번호', '이름'],
    ['1', '홍길동']
  ]);
  assert.deepEqual(result.log, ['header-only.xls: 0행', 'b.xls: 1행']);
});
