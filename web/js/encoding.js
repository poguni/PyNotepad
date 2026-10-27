// Encoding detection and conversion, ported from pynotepad/encoding.py (notepad.exe FUN_140010f48).

// Internal encoding IDs used by notepad.exe (iDefaultEncoding).
export const ANSI = 1;
export const UTF16_LE = 2;
export const UTF16_BE = 3;
export const UTF8_BOM = 4;
export const UTF8 = 5;

export const NAMES = {
  [ANSI]: 'ANSI',
  [UTF16_LE]: 'UTF-16 LE',
  [UTF16_BE]: 'UTF-16 BE',
  [UTF8]: 'UTF-8',
  [UTF8_BOM]: 'UTF-8(BOM)',
};

// Order used by the save-as encoding combo box.
export const CHOICES = [ANSI, UTF16_LE, UTF16_BE, UTF8, UTF8_BOM];

// Files of 1 GiB or more are rejected.
export const MAX_FILE_SIZE = 0x40000000;

// "ANSI" is the Korean Windows code page (CP949); the WHATWG name for it is euc-kr.
const ANSI_LABEL = 'euc-kr';

function startsWith(data, bytes) {
  return data.length >= bytes.length && bytes.every((b, i) => data[i] === b);
}

// Stand-in for advapi32!IsTextUnicode on BOM-less files: UTF-16 LE text of mostly Latin
// characters has a NUL in (nearly) every odd byte and almost none in the even bytes.
function looksLikeUtf16Le(data) {
  if (data.length < 2 || data.length % 2) return false;
  let odd = 0, even = 0;
  for (let i = 0; i < data.length; i += 2) {
    if (data[i] === 0) even++;
    if (data[i + 1] === 0) odd++;
  }
  const pairs = data.length / 2;
  return odd / pairs > 0.5 && even / pairs < 0.05;
}

function isValidUtf8(data) {
  try {
    new TextDecoder('utf-8', { fatal: true }).decode(data);
    return true;
  } catch {
    return false;
  }
}

export function detect(data) {
  if (startsWith(data, [0xef, 0xbb, 0xbf])) return UTF8_BOM;
  if (startsWith(data, [0xff, 0xfe])) return UTF16_LE;
  if (startsWith(data, [0xfe, 0xff])) return UTF16_BE;
  if (looksLikeUtf16Le(data)) return UTF16_LE;
  if (isValidUtf8(data)) return UTF8;
  return ANSI;
}

// Pick the first line ending found in the text; CRLF when there is none.
export function detectLineEnding(text) {
  const i = text.search(/[\r\n]/);
  if (i < 0) return '\r\n';
  if (text[i] === '\n') return '\n';
  return text[i + 1] === '\n' ? '\r\n' : '\r';
}

export function normalizeNewlines(text) {
  return text.replace(/\r\n?/g, '\n');
}

// Decode file bytes (Uint8Array) into { text, encoding, lineEnding }.
export function decode(data, encoding = detect(data)) {
  let text;
  if (encoding === UTF8_BOM || encoding === UTF8) {
    // TextDecoder strips a leading UTF-8 BOM by itself.
    text = new TextDecoder('utf-8').decode(data);
  } else if (encoding === UTF16_LE) {
    text = new TextDecoder('utf-16le').decode(data);
  } else if (encoding === UTF16_BE) {
    text = new TextDecoder('utf-16be').decode(data);
  } else {
    text = new TextDecoder(ANSI_LABEL).decode(data);
  }
  // notepad replaces embedded NUL characters with spaces.
  text = text.replace(/\0/g, ' ');
  return { text: normalizeNewlines(text), encoding, lineEnding: detectLineEnding(text) };
}

// Browsers can decode CP949 but not encode it, so build the reverse table once from the decoder.
let ansiTable = null;
function ansiEncoder() {
  if (!ansiTable) {
    ansiTable = new Map();
    const decoder = new TextDecoder(ANSI_LABEL);
    const pair = new Uint8Array(2);
    for (let lead = 0x81; lead <= 0xfe; lead++) {
      for (let trail = 0x41; trail <= 0xfe; trail++) {
        pair[0] = lead;
        pair[1] = trail;
        const ch = decoder.decode(pair);
        if (ch.length === 1 && ch !== '�' && !ansiTable.has(ch)) ansiTable.set(ch, [lead, trail]);
      }
    }
  }
  return ansiTable;
}

function encodeAnsi(text) {
  const table = ansiEncoder();
  const out = [];
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (code < 0x80) out.push(code);
    else out.push(...(table.get(ch) || [0x3f])); // '?' like WideCharToMultiByte's default char
  }
  return new Uint8Array(out);
}

// True when saving as ANSI would replace characters (notepad warning string 27).
export function losesDataAsAnsi(text) {
  const table = ansiEncoder();
  for (const ch of text) {
    if (ch.codePointAt(0) >= 0x80 && !table.has(ch)) return true;
  }
  return false;
}

function encodeUtf16(text, littleEndian) {
  const out = new Uint8Array(2 + text.length * 2);
  const view = new DataView(out.buffer);
  view.setUint16(0, 0xfeff, littleEndian);
  for (let i = 0; i < text.length; i++) view.setUint16(2 + i * 2, text.charCodeAt(i), littleEndian);
  return out;
}

// Encode editor text (\n line endings) to file bytes.
export function encode(text, encoding, lineEnding) {
  text = text.replace(/\n/g, lineEnding);
  if (encoding === UTF8_BOM) return new Uint8Array([0xef, 0xbb, 0xbf, ...new TextEncoder().encode(text)]);
  if (encoding === UTF8) return new TextEncoder().encode(text);
  if (encoding === UTF16_LE) return encodeUtf16(text, true);
  if (encoding === UTF16_BE) return encodeUtf16(text, false);
  return encodeAnsi(text);
}
