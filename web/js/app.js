// PyNotepad web: the browser version of pynotepad/app.py (same menus, shortcuts, dialogs and themes).

import * as E from './encoding.js';
import { render as renderMarkdown } from './markdown.js';
import * as S from './search.js';

const ZOOM_MIN = 10, ZOOM_MAX = 500, ZOOM_STEP = 10;
const UNTITLED = '제목 없음';
const TITLE_SUFFIX = ' - 메모장';
const MARKDOWN_SUFFIXES = ['.md', '.markdown', '.mdown', '.mkd'];
const PREVIEW_LABEL = '▶ 미리 보기', SOURCE_LABEL = '✎ 원본 보기';
const GOOGLE_SEARCH_URL = 'https://www.google.com/search?q=';
const THEMES = {
  paper: { label: '종이', chrome: '#F3F0EA' },
  slate: { label: '슬레이트', chrome: '#1E232B' },
};
const LINE_ENDING_LABELS = { '\r\n': 'Windows (CRLF)', '\n': 'Unix (LF)', '\r': 'Macintosh (CR)' };
const FILE_TYPES = [
  { description: '텍스트 문서(*.txt)', accept: { 'text/plain': ['.txt'] } },
  { description: '마크다운 문서(*.md)', accept: { 'text/markdown': ['.md', '.markdown'] } },
];
const FONT_FAMILIES = ['D2Coding', 'Consolas', 'Cascadia Mono', 'Courier New', 'GulimChe', 'BatangChe',
  'Malgun Gothic', 'IBM Plex Sans KR', 'Noto Sans KR', 'monospace', 'serif', 'sans-serif'];
const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72];

// Messages from pynotepad/resources.py ("{name}" is the file name).
const MSG = {
  saveChanges: (name) => `변경 내용을 ${name}에 저장하시겠습니까?`,
  textNotFound: (text) => `"${text}"을(를) 찾을 수 없습니다.`,
  fileTooLarge: (name) => `${name} 파일이 너무 커서 메모장에서 열 수 없습니다.\n\n다른 편집기를 사용하여 파일을 편집하십시오.`,
  cannotOpen: (name) => `${name} 파일을 열 수 없습니다.`,
  cannotCreate: (name) => `${name} 파일을 만들 수 없습니다.\n\n경로와 파일 이름이 올바른지 확인하십시오.`,
  ansiLoss: (name) => `${name}\n이 파일에는 ANSI로 인코딩된 문서로 저장하는 경우 손실될 유니코드 포맷 문자가 포함되어 있습니다. `
    + '유니코드 정보를 보존하려면 [취소]를 클릭한 다음 인코딩 드롭다운 목록에서 유니코드 옵션 중 하나를 선택하십시오. 계속하시겠습니까?',
  lineOutOfRange: '줄 번호가 전체 줄 수를 넘습니다.',
  // Web only: browsers let a page read the clipboard only with permission.
  pasteBlocked: '브라우저가 클립보드 읽기를 허용하지 않았습니다.\n\nCtrl+V를 눌러 붙여 넣으십시오.',
};

// ------------------------------------------------------------------ settings (same keys as settings.py)

const SETTINGS_KEY = 'pynotepad.settings';
const DEFAULTS = {
  lfFaceName: 'D2Coding',
  iPointSize: 120, // tenths of a point, like the registry value
  fWrap: false,
  StatusBar: true,
  fLineNumbers: true,
  fReverse: false,
  fWrapAround: false,
  fMatchCase: false,
  fWholeWord: false,
  searchString: '',
  replaceString: '',
  iDefaultEncoding: E.UTF8,
  theme: 'paper',
};

const settings = { ...DEFAULTS };
try {
  const stored = JSON.parse(localStorage.getItem(SETTINGS_KEY));
  for (const key of Object.keys(DEFAULTS)) {
    if (stored && typeof stored[key] === typeof DEFAULTS[key]) settings[key] = stored[key];
  }
} catch { /* private window or blocked storage: keep the defaults */ }

function saveSettings() {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch { /* not persisted */ }
}

// ------------------------------------------------------------------ elements and document state

const $ = (id) => document.getElementById(id);
const text = $('text');
const editor = $('editor');
const mirror = $('mirror');
const preview = $('preview');
const popupLayer = $('popup-layer');
const findPanel = $('find-panel');
const hasFileSystemAccess = 'showOpenFilePicker' in window && 'showSaveFilePicker' in window;

const doc = { name: null, handle: null, encoding: settings.iDefaultEncoding, lineEnding: '\r\n', dirty: false };
let zoom = 100;
let previewMode = false;

const displayName = () => doc.name || UNTITLED;
const isMarkdown = () => !!doc.name && MARKDOWN_SUFFIXES.some((s) => doc.name.toLowerCase().endsWith(s));
const hasSelection = () => text.selectionStart !== text.selectionEnd;
const selectedText = () => text.value.slice(text.selectionStart, text.selectionEnd);
const caret = () => (text.selectionDirection === 'backward' ? text.selectionStart : text.selectionEnd);

function previewSelectionText() {
  const sel = window.getSelection();
  return sel.rangeCount && preview.contains(sel.anchorNode) ? sel.toString() : '';
}

function activeSelectionText() {
  return previewMode ? previewSelectionText() : selectedText();
}

function setDirty(value) {
  doc.dirty = value;
  updateTitle();
}

function updateTitle() {
  document.title = `${doc.dirty ? '*' : ''}${displayName()}${TITLE_SUFFIX}`;
  $('doc-name').textContent = displayName();
  $('doc-dirty').hidden = !doc.dirty;
}

// ------------------------------------------------------------------ mirror: line numbers and current line
// Every line of the textarea is repeated in the mirror behind it (with transparent text), so line
// numbers and the current-line band follow wrapped lines without measuring anything.

let mirrorLines = [];
const lineTemplate = document.createElement('div');
lineTemplate.className = 'ln';
lineTemplate.innerHTML = '<span class="num"></span><span class="txt"></span>';

function makeLine(line) {
  const el = lineTemplate.cloneNode(true);
  el.lastChild.textContent = line || ' ';
  return el;
}

function syncMirror() {
  const lines = text.value.split('\n');
  const old = mirrorLines;
  // Only the changed run of lines is rebuilt.
  let start = 0;
  const shortest = Math.min(old.length, lines.length);
  while (start < shortest && old[start] === lines[start]) start++;
  let oldEnd = old.length, newEnd = lines.length;
  while (oldEnd > start && newEnd > start && old[oldEnd - 1] === lines[newEnd - 1]) {
    oldEnd--;
    newEnd--;
  }
  const rows = mirror.children;
  const common = Math.min(oldEnd, newEnd) - start;
  for (let k = 0; k < common; k++) rows[start + k].lastChild.textContent = lines[start + k] || ' ';
  if (oldEnd - start > common) {
    const range = document.createRange();
    range.setStartBefore(rows[start + common]);
    range.setEndAfter(rows[oldEnd - 1]);
    range.deleteContents();
  } else if (newEnd - start > common) {
    const fragment = document.createDocumentFragment();
    for (let k = start + common; k < newEnd; k++) fragment.append(makeLine(lines[k]));
    mirror.insertBefore(fragment, rows[start + common] || null);
  }
  mirrorLines = lines;
  updateMetrics();
}

function updateMetrics() {
  const digits = Math.max(2, String(mirrorLines.length).length);
  editor.style.setProperty('--gutter-w', settings.fLineNumbers ? `calc(${digits}ch + 24px)` : '0px');
  editor.style.setProperty('--sb-w', `${text.offsetWidth - text.clientWidth}px`);
  editor.style.setProperty('--sb-h', `${text.offsetHeight - text.clientHeight}px`);
  syncScroll();
}

function syncScroll() {
  mirror.scrollTop = text.scrollTop;
  mirror.scrollLeft = text.scrollLeft;
}

function lineIndexAt(offset) {
  let count = 0;
  for (let i = text.value.indexOf('\n'); i !== -1 && i < offset; i = text.value.indexOf('\n', i + 1)) count++;
  return count;
}

let currentRow = null;
let statusQueued = false;

function queueStatus() {
  if (!statusQueued) {
    statusQueued = true;
    requestAnimationFrame(() => {
      statusQueued = false;
      updateStatus();
    });
  }
}

function updateStatus() {
  if (previewMode) {
    $('st-pos').textContent = '마크다운 미리 보기';
  } else {
    const offset = caret();
    const line = lineIndexAt(offset);
    const col = offset - (text.value.lastIndexOf('\n', offset - 1) + 1);
    $('st-pos').textContent = `줄 ${line + 1}, 열 ${col + 1}`;
    const row = mirror.children[line];
    if (row !== currentRow) {
      currentRow?.classList.remove('cur');
      row?.classList.add('cur');
      currentRow = row;
    }
  }
  $('st-zoom').textContent = `${zoom}%`;
  $('st-eol').textContent = LINE_ENDING_LABELS[doc.lineEnding];
  $('st-enc').textContent = E.NAMES[doc.encoding];
}

// Scroll the textarea so the character at `offset` is visible (it does not do this by itself while
// another element, like the find box, has the focus).
function revealOffset(offset) {
  const row = mirror.children[lineIndexAt(offset)];
  if (!row) return;
  const node = row.lastChild.firstChild;
  const col = offset - (text.value.lastIndexOf('\n', offset - 1) + 1);
  const range = document.createRange();
  range.setStart(node, Math.min(col, node.length));
  const rect = range.getClientRects()[0] || range.getBoundingClientRect();
  const box = mirror.getBoundingClientRect();
  const lineHeight = rect.height || row.offsetHeight;
  const y = rect.top - box.top + mirror.scrollTop;
  const x = rect.left - box.left + mirror.scrollLeft - text.offsetLeft;
  if (y < text.scrollTop) text.scrollTop = y - lineHeight;
  else if (y + lineHeight > text.scrollTop + text.clientHeight) text.scrollTop = y + 2 * lineHeight - text.clientHeight;
  if (x < text.scrollLeft) text.scrollLeft = Math.max(0, x - 40);
  else if (x > text.scrollLeft + text.clientWidth - 20) text.scrollLeft = x - text.clientWidth + 60;
  syncScroll();
}

function select(start, end, backward = false) {
  text.setSelectionRange(start, end, backward ? 'backward' : 'forward');
  revealOffset(backward ? start : end);
  updateStatus();
}

// Edits go through the browser's editing commands so that 실행 취소 (Ctrl+Z) can undo them.
function insertText(value) {
  text.focus();
  const done = value ? document.execCommand('insertText', false, value) : document.execCommand('delete');
  if (!done) {
    text.setRangeText(value, text.selectionStart, text.selectionEnd, 'end');
    onInput();
  }
}

function onInput() {
  if (!doc.dirty) setDirty(true);
  syncMirror();
  queueStatus();
}

// ------------------------------------------------------------------ font / view

function applyFont() {
  const size = `${(settings.iPointSize / 10) * (zoom / 100)}pt`;
  editor.style.fontFamily = `"${settings.lfFaceName}", "D2Coding", monospace`;
  editor.style.fontSize = size;
  preview.style.fontSize = size;
  updateMetrics();
  updateStatus();
}

function setZoom(value) {
  value = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, value));
  if (value !== zoom) {
    zoom = value;
    applyFont();
  }
}

function applyWrap() {
  editor.classList.toggle('wrap', settings.fWrap);
  text.wrap = settings.fWrap ? 'soft' : 'off';
  updateMetrics();
}

function applyStatusBar() {
  $('status').hidden = !settings.StatusBar;
  updateMetrics();
}

function applyLineNumbers() {
  editor.classList.toggle('numbers', settings.fLineNumbers);
  updateMetrics();
}

function applyTheme() {
  const name = THEMES[settings.theme] ? settings.theme : DEFAULTS.theme;
  document.documentElement.dataset.theme = name;
  $('favicon').href = `icons/icon-${name}.svg`;
  document.querySelector('meta[name="theme-color"]').content = THEMES[name].chrome;
  $('theme-button').innerHTML = `<span class="prefix">테마: </span>${THEMES[name].label} ▾`;
}

function setTheme(name) {
  settings.theme = name;
  saveSettings();
  applyTheme();
}

// ------------------------------------------------------------------ Markdown preview

function ensureSource() {
  // Editing commands always act on the source, so leave the preview first.
  if (previewMode) setPreview(false);
}

function renderPreview() {
  preview.innerHTML = renderMarkdown(text.value);
}

function setPreview(on) {
  if (on !== previewMode) {
    previewMode = on;
    if (on) {
      const fraction = text.scrollTop / Math.max(1, text.scrollHeight - text.clientHeight);
      renderPreview();
      preview.hidden = false;
      editor.classList.add('previewing');
      preview.scrollTop = fraction * (preview.scrollHeight - preview.clientHeight);
      preview.focus();
    } else {
      preview.hidden = true;
      editor.classList.remove('previewing');
      text.focus();
    }
  }
  updatePreviewButton();
  updateStatus();
}

function updatePreviewButton() {
  const button = $('preview-button');
  button.hidden = !(isMarkdown() || previewMode);
  button.textContent = previewMode ? SOURCE_LABEL : PREVIEW_LABEL;
}

// ------------------------------------------------------------------ dialogs

// '저장(&S)' -> '저장(<u>S</u>)'. Labels are constants in this file, so they need no escaping.
const mnemonicHtml = (label) => label.replace(/&(.)/, '<u>$1</u>');

const mnemonicOf = (label) => (/&(.)/.exec(label)?.[1] || '').toUpperCase();

// Message box. `buttons` are [label, value] pairs; the first is the default. Resolves to the value
// of the pressed button, or 'cancel' for Esc.
function showMessage(message, buttons = [['확인', 'ok']]) {
  const dialog = $('message-dialog');
  $('message-text').textContent = message;
  const box = $('message-buttons');
  box.replaceChildren(...buttons.map(([label, value], i) => {
    const button = document.createElement('button');
    button.value = value;
    button.innerHTML = mnemonicHtml(label);
    button.dataset.key = mnemonicOf(label);
    if (i === 0) button.className = 'primary';
    return button;
  }));
  dialog.returnValue = '';
  dialog.showModal();
  box.firstChild.focus();
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue || 'cancel'), { once: true });
  });
}

$('message-dialog').addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || !e.code.startsWith('Key')) return;
  const button = [...$('message-buttons').children].find((b) => b.dataset.key === e.code.slice(3));
  if (button) {
    e.preventDefault();
    button.click();
  }
});

// Runs a <dialog> with a form. `accept()` returns the result, or undefined to keep the dialog open.
function runForm(dialog, accept) {
  const form = dialog.querySelector('form');
  dialog.returnValue = '';
  dialog.showModal();
  return new Promise((resolve) => {
    const onSubmit = async (e) => {
      e.preventDefault();
      if (e.submitter?.value === 'cancel') return dialog.close();
      const result = await accept();
      if (result !== undefined) {
        dialog.returnValue = 'ok';
        dialog.close();
        resolve(result);
      }
    };
    form.addEventListener('submit', onSubmit);
    dialog.addEventListener('close', () => {
      form.removeEventListener('submit', onSubmit);
      if (dialog.returnValue !== 'ok') resolve(null);
    }, { once: true });
  });
}

async function checkSave() {
  // Ask to save unsaved changes. Returns false if the user cancelled.
  if (!doc.dirty) return true;
  const answer = await showMessage(MSG.saveChanges(displayName()),
    [['저장(&S)', 'save'], ['저장 안 함(&N)', 'discard'], ['취소', 'cancel']]);
  if (answer === 'save') return cmdSave();
  return answer === 'discard';
}

// 다른 이름으로 저장: the encoding (and, without a native save dialog, the file name).
function askSaveOptions(name) {
  const dialog = $('save-dialog');
  const nameInput = $('save-name');
  const select = $('save-encoding');
  select.replaceChildren(...E.CHOICES.map((enc) => new Option(E.NAMES[enc], enc)));
  select.value = String(E.CHOICES.includes(doc.encoding) ? doc.encoding : E.UTF8);
  dialog.querySelectorAll('.name-row').forEach((el) => { el.hidden = name === null; });
  const result = runForm(dialog, () => {
    let fileName = name;
    if (name !== null) {
      fileName = nameInput.value.trim();
      if (!fileName) return undefined;
      if (!fileName.includes('.')) fileName += '.txt';
    }
    return { name: fileName, encoding: Number(select.value) };
  });
  if (name !== null) {
    nameInput.value = name;
    nameInput.focus();
    nameInput.setSelectionRange(0, name.lastIndexOf('.') > 0 ? name.lastIndexOf('.') : name.length);
  } else {
    select.focus();
  }
  return result;
}

// ------------------------------------------------------------------ file I/O

function setDocument(value, name, handle, encoding, lineEnding) {
  text.value = value;
  text.setSelectionRange(0, 0);
  text.scrollTop = 0;
  text.scrollLeft = 0;
  Object.assign(doc, { name, handle, encoding, lineEnding });
  syncMirror();
  setDirty(false);
  // Markdown documents open rendered; everything else opens as plain text.
  setPreview(false);
  setPreview(isMarkdown());
}

async function loadFile(file, handle = null) {
  if (file.size >= E.MAX_FILE_SIZE) {
    await showMessage(MSG.fileTooLarge(file.name));
    return false;
  }
  let data;
  try {
    data = new Uint8Array(await file.arrayBuffer());
  } catch {
    await showMessage(MSG.cannotOpen(file.name));
    return false;
  }
  const decoded = E.decode(data);
  setDocument(decoded.text, file.name, handle, decoded.encoding, decoded.lineEnding);

  // .LOG files: append a time stamp at the end (case-sensitive check, like the original).
  if (decoded.text.startsWith('.LOG')) {
    ensureSource();
    text.setSelectionRange(text.value.length, text.value.length);
    insertText(`\n${timeDate()}\n`);
    revealOffset(text.value.length);
  }
  return true;
}

function pickFileWithInput() {
  const input = $('file-input');
  input.value = '';
  return new Promise((resolve) => {
    input.onchange = () => resolve(input.files[0] || null);
    input.oncancel = () => resolve(null);
    input.click();
  });
}

async function writeDocument(target, encoding) {
  const value = text.value;
  if (encoding === E.ANSI && E.losesDataAsAnsi(value)) {
    if (await showMessage(MSG.ansiLoss(target.name), [['확인', 'ok'], ['취소', 'cancel']]) !== 'ok') return false;
  }
  const bytes = E.encode(value, encoding, doc.lineEnding);
  try {
    if (target.handle) {
      const writable = await target.handle.createWritable();
      await writable.write(bytes);
      await writable.close();
    } else {
      // No file system access (Firefox, Safari): save through a download.
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = target.name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }
  } catch {
    await showMessage(MSG.cannotCreate(target.name));
    return false;
  }
  Object.assign(doc, { name: target.name, handle: target.handle, encoding });
  setDirty(false);
  updatePreviewButton();
  updateStatus();
  return true;
}

// ------------------------------------------------------------------ 파일 menu

async function cmdNew() {
  if (await checkSave()) setDocument('', null, null, settings.iDefaultEncoding, '\r\n');
}

function cmdNewWindow() {
  window.open(location.href.split('#')[0], '_blank');
}

async function cmdOpen() {
  if (!(await checkSave())) return;
  if (!hasFileSystemAccess) {
    const file = await pickFileWithInput();
    if (file) await loadFile(file);
    return;
  }
  let handle;
  try {
    [handle] = await window.showOpenFilePicker({ types: FILE_TYPES });
  } catch (err) {
    if (err.name !== 'AbortError') await showMessage(`파일 열기 창을 띄우지 못했습니다. 다시 시도하십시오.\n\n${err.message}`);
    return;
  }
  try {
    await loadFile(await handle.getFile(), handle);
  } catch {
    await showMessage(MSG.cannotOpen(handle.name));
  }
}

async function cmdSave() {
  if (doc.handle || (doc.name && !hasFileSystemAccess)) {
    return writeDocument({ name: doc.name, handle: doc.handle }, doc.encoding);
  }
  return cmdSaveAs();
}

async function cmdSaveAs() {
  const suggested = doc.name || `${UNTITLED}.txt`;
  if (!hasFileSystemAccess) {
    const options = await askSaveOptions(suggested);
    return options ? writeDocument({ name: options.name, handle: null }, options.encoding) : false;
  }
  let handle;
  try {
    handle = await window.showSaveFilePicker({ suggestedName: suggested, types: FILE_TYPES });
  } catch (err) {
    if (err.name !== 'AbortError') await showMessage(MSG.cannotCreate(suggested));
    return false;
  }
  const options = await askSaveOptions(null);
  return options ? writeDocument({ name: handle.name, handle }, options.encoding) : false;
}

function cmdPrint() {
  $('print-area').textContent = text.value;
  window.print();
}

// ------------------------------------------------------------------ 편집 menu

function cmdUndo() {
  ensureSource();
  text.focus();
  document.execCommand('undo');
}

function cmdCut() {
  ensureSource();
  if (!hasSelection()) return;
  text.focus();
  if (!document.execCommand('cut')) {
    navigator.clipboard.writeText(selectedText()).then(() => insertText(''), () => {});
  }
}

function cmdCopy() {
  const value = activeSelectionText();
  if (!value) return;
  if (!previewMode) text.focus();
  if (!document.execCommand('copy')) navigator.clipboard.writeText(value).catch(() => {});
}

async function cmdPaste() {
  ensureSource();
  let value;
  try {
    value = await navigator.clipboard.readText();
  } catch {
    await showMessage(MSG.pasteBlocked);
    text.focus();
    return;
  }
  insertText(value.replace(/\r\n?/g, '\n'));
}

function cmdDelete() {
  ensureSource();
  if (hasSelection()) insertText('');
}

function cmdSearchGoogle() {
  const query = activeSelectionText().trim();
  if (query) window.open(GOOGLE_SEARCH_URL + encodeURIComponent(query).replace(/%20/g, '+'), '_blank', 'noopener');
}

function cmdFind() {
  ensureSource();
  openFindPanel(false);
}

function cmdReplace() {
  ensureSource();
  openFindPanel(true);
}

function cmdFindNext() {
  ensureSource();
  if (settings.searchString) findNext(true);
  else cmdFind();
}

function cmdFindPrev() {
  ensureSource();
  if (settings.searchString) findNext(false);
  else cmdFind();
}

const searchOptions = () => ({ matchCase: settings.fMatchCase, wholeWord: settings.fWholeWord });

function findNext(down) {
  const needle = settings.searchString;
  const start = hasSelection() ? (down ? text.selectionEnd : text.selectionStart) : caret();
  const span = S.find(text.value, needle, start, { down, wrapAround: settings.fWrapAround, ...searchOptions() });
  if (!span) {
    showMessage(MSG.textNotFound(needle));
    return false;
  }
  select(span[0], span[1], !down);
  return true;
}

function replaceOne() {
  const needle = settings.searchString;
  const selected = selectedText();
  const same = settings.fMatchCase ? selected === needle : selected.toLowerCase() === needle.toLowerCase();
  if (needle && selected && same) {
    const focused = document.activeElement;
    insertText(settings.replaceString);
    focused?.focus();
  }
  findNext(true);
}

function replaceAll() {
  const needle = settings.searchString;
  const [result, count] = S.replaceAll(text.value, needle, settings.replaceString, searchOptions());
  if (!count) {
    showMessage(MSG.textNotFound(needle));
    return;
  }
  // One edit for the whole document, so a single 실행 취소 restores it.
  const focused = document.activeElement;
  const position = Math.min(caret(), result.length);
  text.focus();
  text.select();
  insertText(result);
  text.setSelectionRange(position, position);
  updateStatus();
  focused?.focus();
}

async function cmdGoto() {
  ensureSource();
  const total = mirrorLines.length;
  const input = $('goto-line');
  const result = runForm($('goto-dialog'), async () => {
    const line = Number(input.value.trim());
    if (!Number.isInteger(line) || !input.value.trim()) return undefined;
    if (line < 1 || line > total) {
      await showMessage(MSG.lineOutOfRange);
      input.focus();
      input.select();
      return undefined;
    }
    return line;
  });
  input.value = String(lineIndexAt(caret()) + 1);
  input.select();
  const line = await result;
  text.focus();
  if (line) {
    const offset = mirrorLines.slice(0, line - 1).reduce((sum, l) => sum + l.length + 1, 0);
    select(offset, offset);
  }
}

function cmdSelectAll() {
  if (previewMode) {
    const range = document.createRange();
    range.selectNodeContents(preview);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
  } else {
    text.focus();
    text.select();
  }
  updateStatus();
}

// 'time date' like notepad: GetTimeFormatW(TIME_NOSECONDS) + ' ' + GetDateFormatW(DATE_SHORTDATE) on ko-KR.
function timeDate() {
  const now = new Date();
  const time = now.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' });
  const pad = (n) => String(n).padStart(2, '0');
  return `${time} ${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function cmdTimeDate() {
  ensureSource();
  insertText(timeDate());
}

// ------------------------------------------------------------------ 서식 / 보기

function cmdWordWrap() {
  settings.fWrap = !settings.fWrap;
  saveSettings();
  applyWrap();
}

async function cmdFont() {
  const family = $('font-family');
  const size = $('font-size');
  const sample = $('font-sample');
  $('font-families').replaceChildren(...FONT_FAMILIES.map((f) => new Option(f)));
  size.replaceChildren(...FONT_SIZES.map((s) => new Option(String(s))));
  const current = Math.round(settings.iPointSize / 10);
  if (!FONT_SIZES.includes(current)) size.add(new Option(String(current)));
  family.value = settings.lfFaceName;
  size.value = String(current);
  const updateSample = () => {
    sample.style.fontFamily = `"${family.value}", monospace`;
    sample.style.fontSize = `${size.value}pt`;
  };
  family.oninput = updateSample;
  size.onchange = updateSample;
  updateSample();
  const result = runForm($('font-dialog'), () => (family.value.trim() ? { family: family.value.trim(), size: Number(size.value) } : undefined));
  family.focus();
  family.select();
  const picked = await result;
  if (picked) {
    settings.lfFaceName = picked.family;
    settings.iPointSize = picked.size * 10;
    saveSettings();
    applyFont();
  }
  focusActive();
}

function cmdStatusBar() {
  settings.StatusBar = !settings.StatusBar;
  saveSettings();
  applyStatusBar();
}

function cmdLineNumbers() {
  settings.fLineNumbers = !settings.fLineNumbers;
  saveSettings();
  applyLineNumbers();
}

const cmdTogglePreview = () => setPreview(!previewMode);
const cmdZoomIn = () => setZoom(zoom + ZOOM_STEP);
const cmdZoomOut = () => setZoom(zoom - ZOOM_STEP);
const cmdZoomReset = () => setZoom(100);

// ------------------------------------------------------------------ 찾기 / 바꾸기 panel (modeless)

let findReplaceMode = false;

function openFindPanel(replace) {
  findReplaceMode = replace;
  findPanel.classList.toggle('replace', replace);
  $('find-title').textContent = replace ? '바꾸기' : '찾기';
  const selected = selectedText();
  $('find-what').value = selected && !selected.includes('\n') ? selected : settings.searchString;
  $('find-with').value = settings.replaceString;
  $('opt-word').checked = settings.fWholeWord;
  $('opt-case').checked = settings.fMatchCase;
  $('opt-wrap').checked = settings.fWrapAround;
  findPanel.querySelector(`input[value="${settings.fReverse ? 'up' : 'down'}"]`).checked = true;
  findPanel.hidden = false;
  $('find-what').focus();
  $('find-what').select();
}

function storeFindOptions() {
  settings.searchString = $('find-what').value;
  settings.replaceString = $('find-with').value;
  settings.fWholeWord = $('opt-word').checked;
  settings.fMatchCase = $('opt-case').checked;
  settings.fWrapAround = $('opt-wrap').checked;
  if (!findReplaceMode) settings.fReverse = findPanel.querySelector('input[value="up"]').checked;
  saveSettings();
}

function closeFindPanel() {
  storeFindOptions();
  findPanel.hidden = true;
  text.focus();
}

function panelFindNext() {
  storeFindOptions();
  if (settings.searchString) findNext(findReplaceMode || !settings.fReverse);
}

const panelReplace = () => { storeFindOptions(); replaceOne(); };
const panelReplaceAll = () => { storeFindOptions(); replaceAll(); };

$('btn-find-next').addEventListener('click', panelFindNext);
$('btn-replace').addEventListener('click', panelReplace);
$('btn-replace-all').addEventListener('click', panelReplaceAll);
$('btn-find-close').addEventListener('click', closeFindPanel);
findPanel.addEventListener('change', storeFindOptions);
findPanel.addEventListener('keydown', (e) => {
  let handler = null;
  if (e.key === 'Enter' && !e.isComposing && !e.altKey && !e.ctrlKey && e.target.tagName !== 'BUTTON') handler = panelFindNext;
  else if (e.key === 'Escape') handler = closeFindPanel;
  else if (e.altKey && !e.ctrlKey) {
    const toggle = (id) => () => $(id).click();
    const focus = (id) => () => $(id).focus();
    handler = {
      KeyF: panelFindNext, KeyN: focus('find-what'), KeyW: toggle('opt-word'), KeyC: toggle('opt-case'),
      KeyR: findReplaceMode ? panelReplace : toggle('opt-wrap'),
      ...(findReplaceMode
        ? { KeyA: panelReplaceAll, KeyP: focus('find-with') }
        : { KeyU: () => { findPanel.querySelector('input[value="up"]').click(); }, KeyD: () => { findPanel.querySelector('input[value="down"]').click(); } }),
    }[e.code];
  }
  if (handler) {
    e.preventDefault();
    e.stopPropagation();
    handler();
  }
});

// ------------------------------------------------------------------ menus

const SEP = null;
const always = () => true;
const item = (label, action, accel = '', extra = {}) => ({ label, action, accel, enabled: always, ...extra });
const needsSelection = { enabled: () => !!activeSelectionText() };
const needsSourceSelection = { enabled: () => hasSelection() };
const needsNeedle = { enabled: () => !!settings.searchString };

// 새로 만들기 / 새 창 have no shortcut here: browsers keep Ctrl+N and Ctrl+Shift+N for themselves.
// 끝내기 is left out because a page cannot close its own tab; the browser asks before leaving unsaved changes.
const MENUS = [
  { label: '파일(&F)', items: [
    item('새로 만들기(&N)', cmdNew),
    item('새 창(&W)', cmdNewWindow),
    item('열기(&O)...', cmdOpen, 'Ctrl+O'),
    item('저장(&S)', cmdSave, 'Ctrl+S'),
    item('다른 이름으로 저장(&A)...', cmdSaveAs, 'Ctrl+Shift+S'),
    SEP,
    item('인쇄(&P)...', cmdPrint, 'Ctrl+P'),
  ] },
  { label: '편집(&E)', items: [
    item('실행 취소(&U)', cmdUndo, 'Ctrl+Z'),
    SEP,
    item('잘라내기(&T)', cmdCut, 'Ctrl+X', needsSourceSelection),
    item('복사(&C)', cmdCopy, 'Ctrl+C', needsSelection),
    item('붙여넣기(&P)', cmdPaste, 'Ctrl+V'),
    item('삭제(&L)', cmdDelete, 'Del', needsSourceSelection),
    SEP,
    item('Google로 검색(&S)...', cmdSearchGoogle, 'Ctrl+E', needsSelection),
    item('찾기(&F)...', cmdFind, 'Ctrl+F'),
    item('다음 찾기(&N)', cmdFindNext, 'F3', needsNeedle),
    item('이전 찾기(&V)', cmdFindPrev, 'Shift+F3', needsNeedle),
    item('바꾸기(&R)...', cmdReplace, 'Ctrl+H'),
    item('이동(&G)...', cmdGoto, 'Ctrl+G'),
    SEP,
    item('모두 선택(&A)', cmdSelectAll, 'Ctrl+A'),
    item('시간/날짜(&D)', cmdTimeDate, 'F5'),
  ] },
  { label: '서식(&O)', items: [
    item('자동 줄 바꿈(&W)', cmdWordWrap, '', { checked: () => settings.fWrap }),
    item('글꼴(&F)...', cmdFont),
  ] },
  { label: '보기(&V)', items: [
    item('확대하기/축소하기(&Z)', null, '', { submenu: [
      item('확대(&I)', cmdZoomIn, 'Ctrl+더하기'),
      item('축소(&O)', cmdZoomOut, 'Ctrl+빼기'),
      item('확대하기/축소하기 기본값 복원(&R)', cmdZoomReset, 'Ctrl+0'),
    ] }),
    item('상태 표시줄(&S)', cmdStatusBar, '', { checked: () => settings.StatusBar }),
    item('줄 번호(&L)', cmdLineNumbers, '', { checked: () => settings.fLineNumbers }),
    SEP,
    item('마크다운 미리 보기(&M)', cmdTogglePreview, 'Ctrl+Shift+M', { checked: () => previewMode }),
  ] },
];

const CONTEXT_MENU = [
  item('실행 취소(&U)', cmdUndo),
  SEP,
  item('잘라내기(&T)', cmdCut, '', needsSourceSelection),
  item('복사(&C)', cmdCopy, '', needsSelection),
  item('붙여넣기(&P)', cmdPaste),
  item('삭제(&L)', cmdDelete, '', needsSourceSelection),
  SEP,
  item('모두 선택(&A)', cmdSelectAll),
  SEP,
  item('Google로 검색(&S)...', cmdSearchGoogle, '', needsSelection),
];

const themeMenu = () => Object.entries(THEMES).map(([key, theme]) =>
  item(theme.label, () => setTheme(key), '', { checked: () => settings.theme === key }));

const menuButtons = MENUS.map((menu, index) => {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'menu-button';
  button.innerHTML = mnemonicHtml(menu.label);
  button.setAttribute('aria-haspopup', 'menu');
  button.addEventListener('click', () => (menuOwner?.index === index ? closeMenus() : openMenubar(index)));
  button.addEventListener('pointerenter', () => {
    if (menuOwner && menuOwner.index !== undefined && menuOwner.index !== index) openMenubar(index);
  });
  $('menus').append(button);
  return button;
});

const popups = []; // open menus, outermost first: { el, items, rows, active }
let menuOwner = null; // { index } for the menu bar, { theme: true }, or { context: true }
let returnFocus = null;

function focusActive() {
  (previewMode ? preview : text).focus();
}

function closeMenus(restoreFocus = true) {
  while (popups.length) popups.pop().el.remove();
  menuButtons.forEach((b) => b.classList.remove('open'));
  $('theme-button').classList.remove('open');
  menuOwner = null;
  if (restoreFocus) {
    if (returnFocus?.isConnected && returnFocus.offsetParent !== null) returnFocus.focus();
    else focusActive();
  }
}

function closeDeeper(level) {
  while (popups.length > level) popups.pop().el.remove();
}

function openPopup(items, x, y, level = 0) {
  closeDeeper(level);
  if (!popups.length && !menuOwner) returnFocus = document.activeElement;
  const el = document.createElement('div');
  el.className = 'popup';
  el.setAttribute('role', 'menu');
  const popup = { el, items, rows: [], active: -1 };
  items.forEach((it, i) => {
    if (!it) {
      el.append(Object.assign(document.createElement('div'), { className: 'sep' }));
      popup.rows.push(null);
      return;
    }
    it.isEnabled = it.enabled();
    const row = document.createElement('div');
    row.className = 'item';
    row.setAttribute('role', it.checked ? 'menuitemcheckbox' : 'menuitem');
    row.classList.toggle('disabled', !it.isEnabled);
    row.classList.toggle('sub', !!it.submenu);
    if (it.checked) {
      row.classList.toggle('checked', it.checked());
      row.setAttribute('aria-checked', String(it.checked()));
    }
    row.innerHTML = `<span class="label">${mnemonicHtml(it.label)}</span>${it.accel ? `<span class="accel">${it.accel}</span>` : ''}`;
    row.addEventListener('pointerenter', () => setActive(popup, i, true));
    row.addEventListener('click', () => activate(popup, i));
    el.append(row);
    popup.rows.push(row);
  });
  popupLayer.append(el);
  const rect = el.getBoundingClientRect();
  el.style.left = `${Math.max(8, Math.min(x, innerWidth - rect.width - 8))}px`;
  el.style.top = `${Math.max(8, Math.min(y, innerHeight - rect.height - 8))}px`;
  el.style.maxHeight = `${innerHeight - 16}px`;
  popups.push(popup);
  return popup;
}

function setActive(popup, i, openSub = false) {
  popup.active = i;
  popup.rows.forEach((row, k) => row?.classList.toggle('active', k === i));
  const level = popups.indexOf(popup);
  const it = popup.items[i];
  if (openSub && it?.submenu) openSubmenu(popup, i, false);
  else closeDeeper(level + 1);
}

function moveActive(popup, step) {
  const n = popup.items.length;
  let i = popup.active;
  for (let k = 0; k < n; k++) {
    i = (i + step + n) % n;
    if (popup.items[i]) return setActive(popup, i);
  }
}

function openSubmenu(popup, i, focusFirst) {
  const rect = popup.rows[i].getBoundingClientRect();
  const sub = openPopup(popup.items[i].submenu, rect.right + 2, rect.top - 7, popups.indexOf(popup) + 1);
  if (focusFirst) moveActive(sub, 1);
}

function activate(popup, i) {
  const it = popup.items[i];
  if (!it || !it.isEnabled) return;
  if (it.submenu) return openSubmenu(popup, i, true);
  closeMenus();
  it.action();
}

function openMenubar(index, focusFirst = false) {
  const keepFocus = menuOwner ? returnFocus : document.activeElement;
  closeMenus(false);
  returnFocus = keepFocus;
  const button = menuButtons[index];
  button.classList.add('open');
  menuOwner = { index };
  const rect = button.getBoundingClientRect();
  const popup = openPopup(MENUS[index].items, rect.left, rect.bottom + 4);
  if (focusFirst) moveActive(popup, 1);
}

function menuIndexForCode(code) {
  return code.startsWith('Key') ? MENUS.findIndex((m) => mnemonicOf(m.label) === code.slice(3)) : -1;
}

function handleMenuKey(e) {
  const popup = popups[popups.length - 1];
  const bar = menuOwner?.index;
  e.preventDefault();
  if (e.altKey && menuIndexForCode(e.code) >= 0) return openMenubar(menuIndexForCode(e.code), true);
  switch (e.key) {
    case 'ArrowDown': return moveActive(popup, 1);
    case 'ArrowUp': return moveActive(popup, -1);
    case 'Enter':
    case ' ':
      return popup.active >= 0 ? activate(popup, popup.active) : undefined;
    case 'Escape':
      return popups.length > 1 ? closeDeeper(popups.length - 1) : closeMenus();
    case 'ArrowRight':
      if (popup.items[popup.active]?.submenu) return openSubmenu(popup, popup.active, true);
      if (bar !== undefined) return openMenubar((bar + 1) % MENUS.length, true);
      return undefined;
    case 'ArrowLeft':
      if (popups.length > 1) return closeDeeper(popups.length - 1);
      if (bar !== undefined) return openMenubar((bar - 1 + MENUS.length) % MENUS.length, true);
      return undefined;
    case 'Tab':
    case 'Alt':
      return closeMenus();
    default: {
      // A mnemonic letter runs its item (matched by key code, so the Korean IME does not interfere).
      const key = e.code.startsWith('Key') || e.code.startsWith('Digit') ? e.code.slice(-1) : '';
      const i = popup.items.findIndex((it) => it && mnemonicOf(it.label) === key);
      if (key && i >= 0) {
        setActive(popup, i);
        activate(popup, i);
      }
    }
  }
}

document.addEventListener('pointerdown', (e) => {
  if (popups.length && !e.target.closest('.popup, .menu-button, .theme-box')) closeMenus(false);
});
window.addEventListener('blur', () => { if (popups.length) closeMenus(false); });
window.addEventListener('resize', () => { if (popups.length) closeMenus(false); });

$('theme-button').addEventListener('click', () => {
  if (menuOwner?.theme) return closeMenus();
  closeMenus(false);
  const button = $('theme-button');
  const rect = button.getBoundingClientRect();
  menuOwner = { theme: true };
  button.classList.add('open');
  openPopup(themeMenu(), rect.left, rect.bottom + 4);
});

$('preview-button').addEventListener('click', cmdTogglePreview);

function showContextMenu(e) {
  if (e.pointerType === 'touch') return; // keep the phone's own text menu
  e.preventDefault();
  if (!previewMode) text.focus();
  closeMenus(false);
  returnFocus = previewMode ? preview : text;
  menuOwner = { context: true };
  openPopup(CONTEXT_MENU, e.clientX, e.clientY);
}

// ------------------------------------------------------------------ keyboard
// Shortcuts match on key codes (e.code), so they work with the Korean IME on and with Caps Lock.

const CTRL_KEYS = {
  KeyO: cmdOpen, KeyS: cmdSave, KeyP: cmdPrint, KeyG: cmdGoto, KeyF: cmdFind, KeyH: cmdReplace,
  KeyE: cmdSearchGoogle, KeyA: cmdSelectAll,
  Equal: cmdZoomIn, NumpadAdd: cmdZoomIn, Minus: cmdZoomOut, NumpadSubtract: cmdZoomOut,
  Digit0: cmdZoomReset, Numpad0: cmdZoomReset,
};
const CTRL_SHIFT_KEYS = { KeyS: cmdSaveAs, KeyM: cmdTogglePreview, Equal: cmdZoomIn };

window.addEventListener('keydown', (e) => {
  if (popups.length) return handleMenuKey(e);
  if (document.querySelector('dialog[open]')) return; // modal dialogs handle their own keys
  const ctrl = e.ctrlKey || e.metaKey;
  let handler = null;
  if (ctrl && !e.altKey) {
    handler = (e.shiftKey ? CTRL_SHIFT_KEYS : CTRL_KEYS)[e.code];
    if (!handler && e.code === 'KeyZ' && !e.shiftKey && previewMode) handler = cmdUndo;
  } else if (e.altKey && !ctrl && !e.shiftKey) {
    if (e.code === 'Backspace') handler = cmdUndo;
    else if (menuIndexForCode(e.code) >= 0) handler = () => openMenubar(menuIndexForCode(e.code), true);
  } else if (!ctrl && !e.altKey && !e.isComposing) {
    if (e.code === 'F3') handler = e.shiftKey ? cmdFindPrev : cmdFindNext;
    else if (e.code === 'F5' && !e.shiftKey) handler = cmdTimeDate;
    else if (e.code === 'F10' && !e.shiftKey) handler = () => openMenubar(0, true);
  }
  if (handler) {
    e.preventDefault();
    handler();
  }
});

// ------------------------------------------------------------------ wiring

text.addEventListener('input', onInput);
text.addEventListener('scroll', syncScroll);
for (const type of ['keyup', 'mouseup', 'select', 'focus']) text.addEventListener(type, queueStatus);
document.addEventListener('selectionchange', queueStatus);
text.addEventListener('contextmenu', showContextMenu);
preview.addEventListener('contextmenu', showContextMenu);
editor.addEventListener('wheel', (e) => {
  if (!e.ctrlKey) return;
  e.preventDefault();
  setZoom(zoom + (e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
}, { passive: false });
new ResizeObserver(updateMetrics).observe(text);
window.addEventListener('beforeunload', (e) => {
  if (doc.dirty) e.preventDefault();
});

applyTheme();
applyFont();
applyWrap();
applyStatusBar();
applyLineNumbers();
setDocument('', null, null, settings.iDefaultEncoding, '\r\n');
document.fonts?.ready.then(updateMetrics);
text.focus();
