// Find/replace logic on plain strings (offsets), ported from pynotepad/search.py.

function pattern(needle, matchCase, wholeWord) {
  let body = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (wholeWord) body = `(?<![\\p{L}\\p{N}_])${body}(?![\\p{L}\\p{N}_])`;
  return new RegExp(body, matchCase ? 'gu' : 'giu');
}

function* matches(rx, text, from = 0, to = text.length) {
  rx.lastIndex = from;
  let m;
  while ((m = rx.exec(text)) && m.index + m[0].length <= to) {
    yield [m.index, m.index + m[0].length];
    if (!m[0].length) rx.lastIndex++;
  }
}

// Return [start, end] of the next match from offset `start`, or null.
// Searching down begins at `start`; searching up finds the last match ending at or before `start`.
export function find(text, needle, start, { down = true, matchCase = false, wholeWord = false, wrapAround = false } = {}) {
  if (!needle) return null;
  const rx = pattern(needle, matchCase, wholeWord);

  if (down) {
    const first = matches(rx, text, start).next();
    if (!first.done) return first.value;
    if (!wrapAround) return null;
    const again = matches(rx, text, 0).next();
    return again.done ? null : again.value;
  }

  let last = null;
  for (const span of matches(rx, text, 0, start)) last = span;
  if (last === null && wrapAround) {
    for (const span of matches(rx, text, start)) last = span;
  }
  return last;
}

// Every non-overlapping match as [start, end], in document order.
export function findAll(text, needle, { matchCase = false, wholeWord = false } = {}) {
  if (!needle) return [];
  return [...matches(pattern(needle, matchCase, wholeWord), text)];
}

// Replace every match; returns [newText, count].
export function replaceAll(text, needle, replacement, { matchCase = false, wholeWord = false } = {}) {
  if (!needle) return [text, 0];
  let count = 0;
  const result = text.replace(pattern(needle, matchCase, wholeWord), () => {
    count++;
    return replacement;
  });
  return [result, count];
}
