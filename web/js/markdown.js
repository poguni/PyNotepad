// Small Markdown renderer (no dependencies), ported from pynotepad/markdown_view.py.
//
// Supported: ATX/setext headings, paragraphs with hard breaks, **bold**, *italic*, ***both***,
// ~~strike~~, `code`, fenced code blocks, block quotes (nested blocks inside), ordered/unordered and
// nested lists, task lists, pipe tables with alignment, links, autolinks, bare URLs, images (shown as
// alt text), horizontal rules and backslash escapes. Raw HTML is shown as text.

// ---------------------------------------------------------------------------------------- parsing

const FENCE = /^ {0,3}(`{3,}|~{3,})\s*([\w+-]*)/;
const HEADING = /^ {0,3}(#{1,6})(?:\s+(.*?))?\s*#*\s*$/;
const HR = /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/;
const SETEXT = /^ {0,3}(=+|-+)\s*$/;
const LIST = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const TASK = /^\[([ xX])\]\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;
const QUOTE = /^ {0,3}> ?(.*)$/;

const isBlank = (line) => !line.trim();

function expandTabs(text, size = 4) {
  let out = '';
  for (const ch of text) out += ch === '\t' ? ' '.repeat(size - (out.length % size)) : ch;
  return out;
}

function splitRow(line) {
  line = line.trim();
  if (line.startsWith('|')) line = line.slice(1);
  if (line.endsWith('|') && !line.endsWith('\\|')) line = line.slice(0, -1);
  return line.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|'));
}

function isTableStart(line, next) {
  return line.includes('|') && next != null && TABLE_SEP.test(next) && next.includes('-');
}

function startsBlock(line, next) {
  return FENCE.test(line) || HEADING.test(line) || HR.test(line) || QUOTE.test(line) || LIST.test(line)
    || isTableStart(line, next);
}

export function parse(source) {
  const lines = source.replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const next = i + 1 < lines.length ? lines[i + 1] : null;

    if (isBlank(line)) {
      i++;
      continue;
    }

    let m = FENCE.exec(line);
    if (m) {
      const [, fence, lang] = m;
      const body = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence[0].repeat(fence.length))) body.push(lines[i++]);
      blocks.push({ kind: 'code', text: body.join('\n'), lang });
      i++;
      continue;
    }

    m = HEADING.exec(line);
    if (m) {
      blocks.push({ kind: 'heading', text: m[2] || '', level: m[1].length });
      i++;
      continue;
    }

    if (HR.test(line)) {
      blocks.push({ kind: 'hr' });
      i++;
      continue;
    }

    if (QUOTE.test(line)) {
      const inner = [];
      while (i < lines.length && !isBlank(lines[i]) && (QUOTE.test(lines[i]) || inner.length)) {
        const q = QUOTE.exec(lines[i]);
        if (!q && startsBlock(lines[i], null)) break;
        inner.push(q ? q[1] : lines[i]);
        i++;
      }
      blocks.push({ kind: 'quote', children: parse(inner.join('\n')) });
      continue;
    }

    if (isTableStart(line, next)) {
      const header = splitRow(line);
      const aligns = splitRow(next).map((cell) => {
        const left = cell.startsWith(':'), right = cell.endsWith(':');
        return left && right ? 'center' : right ? 'right' : 'left';
      });
      const rows = [];
      i += 2;
      while (i < lines.length && !isBlank(lines[i]) && lines[i].includes('|')) rows.push(splitRow(lines[i++]));
      blocks.push({ kind: 'table', header, aligns, rows });
      continue;
    }

    if (LIST.test(line)) {
      const items = []; // { level, marker, task, text }
      const indents = [];
      while (i < lines.length) {
        const cur = lines[i];
        const lm = LIST.exec(cur);
        if (lm) {
          const indent = expandTabs(lm[1]).length;
          const ordered = /\d/.test(lm[2][0]);
          // switching between bullets and numbers starts a new list
          if (items.length && indent <= indents[0] && ordered !== /\d/.test(items[0].marker[0])) break;
          while (indents.length && indent < indents[indents.length - 1]) indents.pop();
          if (!indents.length || indent > indents[indents.length - 1]) indents.push(indent);
          let text = lm[3], task = null;
          const tm = TASK.exec(text);
          if (tm) {
            task = tm[1].toLowerCase() === 'x';
            text = tm[2];
          }
          items.push({ level: indents.length - 1, marker: lm[2], task, text });
          i++;
        } else if (!isBlank(cur) && ' \t'.includes(cur[0]) && items.length) {
          items[items.length - 1].text += ' ' + cur.trim();
          i++;
        } else if (isBlank(cur) && i + 1 < lines.length
          && (LIST.test(lines[i + 1]) || (' \t'.includes(lines[i + 1][0] || 'x') && !isBlank(lines[i + 1])))) {
          i++;
        } else {
          break;
        }
      }
      blocks.push({ kind: 'list', items });
      continue;
    }

    // Paragraph (possibly a setext heading).
    let para = [line];
    i++;
    while (i < lines.length && !isBlank(lines[i])) {
      const next2 = i + 1 < lines.length ? lines[i + 1] : null;
      if (SETEXT.test(lines[i])) {
        const level = lines[i].trim().startsWith('=') ? 1 : 2;
        blocks.push({ kind: 'heading', text: para.map((p) => p.trim()).join(' '), level });
        para = [];
        i++;
        break;
      }
      if (startsBlock(lines[i], next2)) break;
      para.push(lines[i++]);
    }
    if (para.length) {
      let text = '';
      para.forEach((p, k) => {
        const hard = p.endsWith('  ') || p.endsWith('\\');
        const piece = p.endsWith('\\') ? p.replace(/\\+$/, '').trim() : p.trim();
        const last = k === para.length - 1;
        text += piece + (last ? '' : hard ? '\n' : ' ');
      });
      blocks.push({ kind: 'para', text });
    }
  }
  return blocks;
}

const INLINE = new RegExp([
  '(?<code>`+)(?<codetext>.+?)\\k<code>',
  '!\\[(?<imgalt>[^\\]]*)\\]\\((?<imgsrc>[^)\\s]+)(?:\\s+"[^"]*")?\\)',
  '\\[(?<linktext>[^\\]]+)\\]\\((?<href>[^)\\s]+)(?:\\s+"[^"]*")?\\)',
  '<(?<autolink>(?:https?://|mailto:)[^>\\s]+)>',
  '(?<bi>\\*\\*\\*|___)(?<bitext>.+?)\\k<bi>',
  '(?<b>\\*\\*|__)(?<btext>.+?)\\k<b>',
  '(?<s>~~)(?<stext>.+?)\\k<s>',
  '(?<![\\p{L}\\p{N}_*])(?<i>[*_])(?<itext>[^\\s*_](?:.*?[^\\s])?)\\k<i>(?![\\p{L}\\p{N}_*])',
  '\\\\(?<esc>[\\\\`*_{}\\[\\]()#+\\-.!|>~])',
  '(?<url>https?://[^\\s<>()]+[^\\s<>().,;:!?\'"])',
].join('|'), 'gu');

// ---------------------------------------------------------------------------------------- rendering

const BULLETS = ['•', '◦', '▪'];
const SAFE_SCHEMES = ['http://', 'https://', 'mailto:'];

export function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

const text = (s) => escapeHtml(s).replace(/\n/g, '<br>');

function link(href, inner) {
  if (!SAFE_SCHEMES.some((scheme) => href.toLowerCase().startsWith(scheme))) return `<span class="md-link">${inner}</span>`;
  return `<a class="md-link" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${inner}</a>`;
}

export function inline(source) {
  let out = '', pos = 0;
  for (const m of source.matchAll(INLINE)) {
    out += text(source.slice(pos, m.index));
    const g = m.groups;
    if (g.codetext !== undefined) out += `<code>${escapeHtml(g.codetext.trim() || g.codetext)}</code>`;
    else if (g.imgsrc !== undefined) out += `<em class="md-muted">[이미지: ${escapeHtml(g.imgalt || g.imgsrc)}]</em>`;
    else if (g.href !== undefined) out += link(g.href, inline(g.linktext));
    else if (g.autolink !== undefined || g.url !== undefined) {
      const url = g.autolink ?? g.url;
      out += link(url, escapeHtml(url));
    } else if (g.bitext !== undefined) out += `<strong><em>${inline(g.bitext)}</em></strong>`;
    else if (g.btext !== undefined) out += `<strong>${inline(g.btext)}</strong>`;
    else if (g.stext !== undefined) out += `<s>${inline(g.stext)}</s>`;
    else if (g.itext !== undefined) out += `<em>${inline(g.itext)}</em>`;
    else if (g.esc !== undefined) out += escapeHtml(g.esc);
    pos = m.index + m[0].length;
  }
  return out + text(source.slice(pos));
}

function renderList(block) {
  const counters = new Map();
  const rows = block.items.map(({ level, marker, task, text: body }) => {
    for (const deeper of [...counters.keys()]) if (deeper > level) counters.delete(deeper);
    const ordered = /\d/.test(marker[0]);
    let bullet;
    if (task !== null) bullet = task ? '☑' : '☐';
    else if (ordered) {
      counters.set(level, (counters.has(level) ? counters.get(level) : parseInt(marker, 10) - 1) + 1);
      bullet = `${counters.get(level)}.`;
    } else bullet = BULLETS[level % BULLETS.length];
    const cls = task ? ' md-done' : '';
    return `<div class="md-li${cls}" style="--level:${level}"><span class="md-bullet${ordered ? ' md-num' : ''}">${bullet}</span>`
      + `<span>${inline(body)}</span></div>`;
  });
  return `<div class="md-list">${rows.join('')}</div>`;
}

function renderTable(block) {
  const ncols = Math.max(block.header.length, ...block.rows.map((r) => r.length));
  const align = (c) => block.aligns[c] || 'left';
  const cells = (row, tag) => Array.from({ length: ncols }, (_, c) =>
    `<${tag} style="text-align:${align(c)}">${inline(row[c] || '')}</${tag}>`).join('');
  const body = block.rows.map((r) => `<tr>${cells(r, 'td')}</tr>`).join('');
  return `<table><thead><tr>${cells(block.header, 'th')}</tr></thead><tbody>${body}</tbody></table>`;
}

export function renderBlocks(blocks) {
  return blocks.map((block) => {
    switch (block.kind) {
      case 'heading': return `<h${block.level}>${inline(block.text)}</h${block.level}>`;
      case 'para': return `<p>${inline(block.text)}</p>`;
      case 'hr': return '<hr>';
      case 'code': return `<pre><code>${escapeHtml(block.text)}</code></pre>`;
      case 'quote': return `<blockquote>${renderBlocks(block.children)}</blockquote>`;
      case 'list': return renderList(block);
      case 'table': return renderTable(block);
      default: return '';
    }
  }).join('\n');
}

export function render(source) {
  return renderBlocks(parse(source));
}
