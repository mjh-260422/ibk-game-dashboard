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
