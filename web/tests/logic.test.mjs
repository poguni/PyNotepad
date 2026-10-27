// Unit tests for the web version's UI-independent modules (same cases as tests/test_*.py).
// Run: node --test web/tests
import assert from 'node:assert/strict';
import { test } from 'node:test';

import * as E from '../js/encoding.js';
import * as M from '../js/markdown.js';
import * as S from '../js/search.js';

// ---------------------------------------------------------------- search

const TEXT = 'Cat cat catalog CAT';

test('find: down, case-insensitive', () => assert.deepEqual(S.find(TEXT, 'cat', 1), [4, 7]));
test('find: match case', () => assert.deepEqual(S.find(TEXT, 'CAT', 0, { matchCase: true }), [16, 19]));
test('find: whole word', () => {
  assert.equal(S.find('catalog', 'cat', 0, { wholeWord: true }), null);
  assert.deepEqual(S.find(TEXT, 'cat', 5, { wholeWord: true }), [16, 19]);
  assert.equal(S.find('가나다', '나', 0, { wholeWord: true }), null); // Korean letters are word characters
});
test('find: up', () => assert.deepEqual(S.find(TEXT, 'cat', 7, { down: false }), [4, 7]));
test('find: wrap around', () => {
  assert.equal(S.find(TEXT, 'Cat', 17, { matchCase: true }), null);
  assert.deepEqual(S.find(TEXT, 'Cat', 17, { matchCase: true, wrapAround: true }), [0, 3]);
  assert.deepEqual(S.find(TEXT, 'CAT', 2, { down: false, matchCase: true, wrapAround: true }), [16, 19]);
});
test('find: Korean', () => assert.deepEqual(S.find('가나다 나', '나', 2), [4, 5]));
test('replaceAll: literal needle and replacement', () => {
  assert.deepEqual(S.replaceAll(TEXT, 'cat', 'dog', { wholeWord: true }), ['dog dog catalog dog', 3]);
  assert.deepEqual(S.replaceAll('a.b', '.', '-'), ['a-b', 1]);
  assert.deepEqual(S.replaceAll('x', 'x', '$&$1'), ['$&$1', 1]);
});

// ---------------------------------------------------------------- encoding

const bytes = (...b) => new Uint8Array(b);
const utf16le = (s) => E.encode(s, E.UTF16_LE, '\n').slice(2); // drop the BOM

test('detect: BOMs', () => {
  assert.equal(E.detect(bytes(0xef, 0xbb, 0xbf, 0x61)), E.UTF8_BOM);
  assert.equal(E.detect(bytes(0xff, 0xfe, 0x61, 0)), E.UTF16_LE);
  assert.equal(E.detect(bytes(0xfe, 0xff, 0, 0x61)), E.UTF16_BE);
});
test('detect: UTF-8 without BOM, ASCII is UTF-8', () => {
  assert.equal(E.detect(new TextEncoder().encode('안녕하세요')), E.UTF8);
  assert.equal(E.detect(new TextEncoder().encode('hello world')), E.UTF8);
});
test('detect: ANSI Korean', () => {
  assert.equal(E.detect(E.encode('한글 텍스트 파일입니다', E.ANSI, '\n')), E.ANSI);
});
test('detect: UTF-16 LE without BOM', () => {
  assert.equal(E.detect(utf16le('This is a fairly long UTF-16 little endian text without a BOM. '.repeat(3))), E.UTF16_LE);
});
test('round trip: every encoding and line ending', () => {
  const text = '첫 줄\n둘째 줄 ABC\n';
  for (const enc of E.CHOICES) {
    for (const eol of ['\r\n', '\n', '\r']) {
      const doc = E.decode(E.encode(text, enc, eol));
      assert.equal(doc.text, text, `${enc} ${JSON.stringify(eol)}`);
      assert.equal(doc.lineEnding, eol);
      if (enc !== E.ANSI) assert.equal(doc.encoding, enc);
    }
  }
});
test('decode: NUL becomes space, default line ending is CRLF', () => {
  assert.equal(E.decode(bytes(0x61, 0, 0x62)).text, 'a b');
  assert.equal(E.decode(new TextEncoder().encode('single line')).lineEnding, '\r\n');
});
test('ANSI loss check', () => {
  assert.equal(E.losesDataAsAnsi('한글'), false);
  assert.equal(E.losesDataAsAnsi('emoji 😀'), true);
});

// ---------------------------------------------------------------- markdown

const SAMPLE = `# 제목 1

본문 **굵게** *기울임* ~~취소선~~ \`코드\` [링크](https://example.com)
두 번째 줄\\
강제 줄바꿈 뒤

부제목
---

- 항목 A
  - 하위 항목
- [x] 완료
- [ ] 할 일

1. 첫째
2. 둘째

> 인용문 **강조**
> 이어지는 인용

\`\`\`python
print("hi")
\`\`\`

| 이름 | 수량 |
|:-----|----:|
| 사과 | 3 |
| 바나나 | 12 |

***
`;

test('markdown: block kinds', () => {
  assert.deepEqual(M.parse(SAMPLE).map((b) => b.kind),
    ['heading', 'para', 'heading', 'list', 'list', 'quote', 'code', 'table', 'hr']);
});
test('markdown: setext heading and hard break', () => {
  const blocks = M.parse(SAMPLE);
  assert.deepEqual([blocks[2].text, blocks[2].level], ['부제목', 2]);
  assert.ok(blocks[1].text.includes('두 번째 줄\n강제 줄바꿈 뒤'));
});
test('markdown: list levels and tasks', () => {
  assert.deepEqual(M.parse(SAMPLE)[3].items.map(({ level, task, text }) => [level, task, text]),
    [[0, null, '항목 A'], [1, null, '하위 항목'], [0, true, '완료'], [0, false, '할 일']]);
});
test('markdown: table', () => {
  const table = M.parse(SAMPLE)[7];
  assert.deepEqual(table.header, ['이름', '수량']);
  assert.deepEqual(table.aligns, ['left', 'right']);
  assert.deepEqual(table.rows, [['사과', '3'], ['바나나', '12']]);
});
test('markdown: code and quote', () => {
  const blocks = M.parse(SAMPLE);
  assert.deepEqual([blocks[6].lang, blocks[6].text], ['python', 'print("hi")']);
  assert.deepEqual(blocks[5].children.map((b) => b.kind), ['para']);
});
test('markdown: inline rendering', () => {
  assert.equal(M.inline('**굵게** `x`'), '<strong>굵게</strong> <code>x</code>');
  assert.equal(M.inline('snake_case_name'), 'snake_case_name');
  assert.equal(M.inline('한*글*'), '한*글*');
  assert.equal(M.inline('a\nb'), 'a<br>b');
});
test('markdown: links open only safe schemes, raw HTML is text', () => {
  assert.ok(M.inline('[링크](https://example.com)').includes('href="https://example.com"'));
  assert.ok(!M.inline('[x](javascript:alert(1))').includes('href'));
  assert.equal(M.render('<b onclick="x">hi</b>'), '<p>&lt;b onclick=&quot;x&quot;&gt;hi&lt;/b&gt;</p>');
});
test('markdown: bullets and numbering', () => {
  const html = M.render(SAMPLE);
  for (const mark of ['•', '◦', '☑', '☐', '1.', '2.']) assert.ok(html.includes(mark), mark);
});
