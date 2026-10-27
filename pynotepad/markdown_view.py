"""Small Markdown renderer for a Tk Text widget (standard library only).

Supported: ATX/setext headings, paragraphs with hard breaks, **bold**, *italic*, ***both***,
~~strike~~, `code`, fenced code blocks, block quotes (nested blocks inside), ordered/unordered and
nested lists, task lists, pipe tables with alignment, links, autolinks, bare URLs, images (shown as
alt text), horizontal rules and backslash escapes. Raw HTML is shown as text.
"""

from __future__ import annotations

import re
import tkinter as tk
import unicodedata
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------------------- parsing


@dataclass
class Block:
    kind: str                       # heading, para, code, quote, list, table, hr
    text: str = ""
    level: int = 0
    lang: str = ""
    children: list["Block"] = field(default_factory=list)
    items: list[tuple[int, str, bool | None, str]] = field(default_factory=list)  # level, marker, task, text
    header: list[str] = field(default_factory=list)
    aligns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([\w+-]*)")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:\s+(.*?))?\s*#*\s*$")
_HR = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)\s*$")
_LIST = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$")
_TASK = re.compile(r"^\[([ xX])\]\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
_QUOTE = re.compile(r"^ {0,3}> ?(.*)$")


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells = re.split(r"(?<!\\)\|", line)
    return [c.strip().replace("\\|", "|") for c in cells]


def _starts_block(line: str, next_line: str | None) -> bool:
    return bool(_FENCE.match(line) or _HEADING.match(line) or _HR.match(line) or _QUOTE.match(line)
                or _LIST.match(line)
                or ("|" in line and next_line is not None and _TABLE_SEP.match(next_line) and "-" in next_line))


def parse(source: str) -> list[Block]:
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else None

        if not line.strip():
            i += 1
            continue

        m = _FENCE.match(line)
        if m:
            fence, lang = m.group(1), m.group(2)
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence[0] * len(fence)):
                body.append(lines[i])
                i += 1
            blocks.append(Block("code", "\n".join(body), lang=lang))
            i += 1
            continue

        m = _HEADING.match(line)
        if m:
            blocks.append(Block("heading", m.group(2) or "", level=len(m.group(1))))
            i += 1
            continue

        if _HR.match(line):
            blocks.append(Block("hr"))
            i += 1
            continue

        if _QUOTE.match(line):
            inner = []
            while i < len(lines) and lines[i].strip() and (_QUOTE.match(lines[i]) or inner):
                q = _QUOTE.match(lines[i])
                if not q and _starts_block(lines[i], None):
                    break
                inner.append(q.group(1) if q else lines[i])
                i += 1
            blocks.append(Block("quote", children=parse("\n".join(inner))))
            continue

        if "|" in line and nxt is not None and _TABLE_SEP.match(nxt) and "-" in nxt:
            header = _split_row(line)
            aligns = []
            for cell in _split_row(nxt):
                left, right = cell.startswith(":"), cell.endswith(":")
                aligns.append("center" if left and right else "right" if right else "left")
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                rows.append(_split_row(lines[i]))
                i += 1
            blocks.append(Block("table", header=header, aligns=aligns, rows=rows))
            continue

        if _LIST.match(line):
            items: list[tuple[int, str, bool | None, str]] = []
            indents: list[int] = []
            while i < len(lines):
                cur = lines[i]
                lm = _LIST.match(cur)
                if lm:
                    indent = len(lm.group(1).expandtabs(4))
                    ordered = lm.group(2)[0].isdigit()
                    if items and indent <= indents[0] and ordered != items[0][1][0].isdigit():
                        break  # switching between bullets and numbers starts a new list
                    while indents and indent < indents[-1]:
                        indents.pop()
                    if not indents or indent > indents[-1]:
                        indents.append(indent)
                    text, task = lm.group(3), None
                    tm = _TASK.match(text)
                    if tm:
                        task, text = tm.group(1).lower() == "x", tm.group(2)
                    items.append((len(indents) - 1, lm.group(2), task, text))
                    i += 1
                elif cur.strip() and cur[:1] in " \t" and items:
                    lvl, marker, task, text = items[-1]
                    items[-1] = (lvl, marker, task, text + " " + cur.strip())
                    i += 1
                elif not cur.strip() and i + 1 < len(lines) and (
                        _LIST.match(lines[i + 1]) or lines[i + 1][:1] in " \t" and lines[i + 1].strip()):
                    i += 1
                else:
                    break
            blocks.append(Block("list", items=items))
            continue

        # Paragraph (possibly a setext heading).
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip():
            nxt2 = lines[i + 1] if i + 1 < len(lines) else None
            if _SETEXT.match(lines[i]) and len(para) >= 1:
                level = 1 if lines[i].strip().startswith("=") else 2
                blocks.append(Block("heading", " ".join(p.strip() for p in para), level=level))
                para = []
                i += 1
                break
            if _starts_block(lines[i], nxt2):
                break
            para.append(lines[i])
            i += 1
        if para:
            text = ""
            for k, p in enumerate(para):
                hard = p.endswith("  ") or p.endswith("\\")
                piece = p.rstrip("\\").strip() if p.endswith("\\") else p.strip()
                text += piece + ("\n" if hard and k < len(para) - 1 else " " if k < len(para) - 1 else "")
            blocks.append(Block("para", text))
    return blocks


_INLINE = re.compile(r"""
    (?P<code>`+)(?P<codetext>.+?)(?P=code)
  | !\[(?P<imgalt>[^\]]*)\]\((?P<imgsrc>[^)\s]+)(?:\s+"[^"]*")?\)
  | \[(?P<linktext>[^\]]+)\]\((?P<href>[^)\s]+)(?:\s+"[^"]*")?\)
  | <(?P<autolink>(?:https?://|mailto:)[^>\s]+)>
  | (?P<bi>\*\*\*|___)(?P<bitext>.+?)(?P=bi)
  | (?P<b>\*\*|__)(?P<btext>.+?)(?P=b)
  | (?P<s>~~)(?P<stext>.+?)(?P=s)
  | (?<![\w*])(?P<i>[*_])(?P<itext>[^\s*_](?:.*?[^\s])?)(?P=i)(?![\w*])
  | \\(?P<esc>[\\`*_{}\[\]()#+\-.!|>~])
  | (?P<url>https?://[^\s<>()]+[^\s<>().,;:!?'"])
""", re.X)


def plain_inline(text: str) -> str:
    """Text with inline markup removed (used for table cells)."""
    def repl(m: re.Match) -> str:
        for name in ("codetext", "imgalt", "linktext", "autolink", "bitext", "btext", "stext", "itext", "esc", "url"):
            if m.group(name) is not None:
                return plain_inline(m.group(name)) if name in ("linktext", "bitext", "btext", "stext", "itext") else m.group(name)
        return m.group(0)
    return _INLINE.sub(repl, text)


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


# ---------------------------------------------------------------------------------------- rendering

HEADING_SCALE = {1: 1.9, 2: 1.55, 3: 1.3, 4: 1.15, 5: 1.05, 6: 1.0}
COLORS = {
    "text": "#1f2328", "muted": "#59636e", "link": "#0969da", "code_bg": "#eff1f3",
    "block_bg": "#f6f8fa", "rule": "#d1d9e0", "quote_bar": "#d1d9e0",
}
BULLETS = ("•", "◦", "▪")
SAFE_SCHEMES = ("http://", "https://", "mailto:")


class MarkdownRenderer:
    def __init__(self, widget: tk.Text, family: str, mono_family: str, size: int, on_link=None):
        self.w = widget
        self.family = family
        self.mono = mono_family
        self.size = max(6, size)
        self.on_link = on_link
        self.links: dict[str, str] = {}
        self._font_tags: set[str] = set()
        self._setup_tags()

    # ---- tags

    def _setup_tags(self):
        w, s, c = self.w, self.size, COLORS
        w.configure(foreground=c["text"])
        w.tag_configure("para", spacing3=round(s * 0.8))
        for level in range(1, 7):
            w.tag_configure(f"h{level}", spacing1=round(s * (1.2 if level <= 2 else 0.9)), spacing3=round(s * 0.5))
        w.tag_configure("h6", foreground=c["muted"])
        w.tag_configure("rule", background=c["rule"], font=(self.family, -2))  # negative size = pixels
        w.tag_configure("spacer", font=(self.family, -max(4, round(s * 0.8))))
        w.tag_configure("code", background=c["code_bg"])
        w.tag_configure("codeblock", background=c["block_bg"], lmargin1=14, lmargin2=14, rmargin=14)
        w.tag_configure("codeblock_pad", background=c["block_bg"], font=(self.family, 4))
        w.tag_configure("after_block", spacing3=round(s * 0.8))
        w.tag_configure("strike", overstrike=True)
        w.tag_configure("muted", foreground=c["muted"])
        w.tag_configure("link", foreground=c["link"], underline=True)
        w.tag_configure("table", spacing1=1, spacing3=1)
        w.tag_bind("link", "<Enter>", lambda _e: w.configure(cursor="hand2"))
        w.tag_bind("link", "<Leave>", lambda _e: w.configure(cursor=""))

    def _font_tag(self, scale=1.0, bold=False, italic=False, mono=False) -> str:
        name = f"f{scale}-{int(bold)}{int(italic)}{int(mono)}"
        if name not in self._font_tags:
            font = (self.mono if mono else self.family, max(1, round(self.size * scale)),
                    *(["bold"] if bold else []), *(["italic"] if italic else []))
            self.w.tag_configure(name, font=font)
            self._font_tags.add(name)
        return name

    def _quote_tag(self, depth: int) -> str:
        name = f"quote{depth}"
        margin = 18 * depth
        self.w.tag_configure(name, lmargin1=margin, lmargin2=margin, foreground=COLORS["muted"],
                             lmargincolor=COLORS["quote_bar"] if depth else "")
        return name

    def _list_tag(self, level: int, depth: int) -> str:
        name = f"list{level}-{depth}"
        base = 18 * depth + 8 + 22 * level
        self.w.tag_configure(name, lmargin1=base, lmargin2=base + 18, spacing3=2)
        return name

    # ---- insertion

    def _insert(self, text: str, style: dict, tags: tuple[str, ...]):
        font = self._font_tag(style.get("scale", 1.0), style.get("bold", False),
                              style.get("italic", False), style.get("mono", False))
        self.w.insert("end", text, (font,) + tags)

    def inline(self, text: str, style: dict, tags: tuple[str, ...]):
        pos = 0
        for m in _INLINE.finditer(text):
            if m.start() > pos:
                self._insert(text[pos:m.start()], style, tags)
            g = m.groupdict()
            if g["codetext"] is not None:
                self._insert(g["codetext"].strip() or g["codetext"], dict(style, mono=True, scale=style.get("scale", 1.0) * 0.92),
                             tags + ("code",))
            elif g["imgsrc"] is not None:
                self._insert(f"[이미지: {g['imgalt'] or g['imgsrc']}]", dict(style, italic=True), tags + ("muted",))
            elif g["href"] is not None:
                self.inline(g["linktext"], style, tags + self._link_tags(g["href"]))
            elif g["autolink"] is not None or g["url"] is not None:
                url = g["autolink"] or g["url"]
                self._insert(url, style, tags + self._link_tags(url))
            elif g["bitext"] is not None:
                self.inline(g["bitext"], dict(style, bold=True, italic=True), tags)
            elif g["btext"] is not None:
                self.inline(g["btext"], dict(style, bold=True), tags)
            elif g["stext"] is not None:
                self.inline(g["stext"], style, tags + ("strike",))
            elif g["itext"] is not None:
                self.inline(g["itext"], dict(style, italic=True), tags)
            elif g["esc"] is not None:
                self._insert(g["esc"], style, tags)
            pos = m.end()
        if pos < len(text):
            self._insert(text[pos:], style, tags)

    def _link_tags(self, href: str) -> tuple[str, ...]:
        name = f"href{len(self.links)}"
        self.links[name] = href
        self.w.tag_bind(name, "<Button-1>", lambda _e, h=href: self._open(h))
        return ("link", name)

    def _open(self, href: str):
        if self.on_link and href.lower().startswith(SAFE_SCHEMES):
            self.on_link(href)

    # ---- blocks

    def render(self, source: str):
        w = self.w
        w.configure(state="normal")
        w.delete("1.0", "end")
        self.render_blocks(parse(source), depth=0)
        # Drop trailing blank space.
        while (w.get("end-2c") == "\n" and w.compare("end-2c", ">", "1.0")
               and "rule" not in w.tag_names("end-2c")):
            w.delete("end-2c")
        w.configure(state="disabled")

    def render_blocks(self, blocks: list[Block], depth: int):
        base = (self._quote_tag(depth),) if depth else ()
        for block in blocks:
            getattr(self, f"_render_{block.kind}")(block, base, depth)

    def _render_heading(self, block, base, depth):
        style = {"scale": HEADING_SCALE[block.level], "bold": True}
        self.inline(block.text, style, base + (f"h{block.level}",))
        self.w.insert("end", "\n", base + (f"h{block.level}",))
        if block.level <= 2:
            self._rule(base)

    def _rule(self, base):
        self.w.insert("end", "\n", base + ("rule",))
        self.w.insert("end", "\n", base + ("spacer",))

    def _render_para(self, block, base, depth):
        self.inline(block.text, {}, base + ("para",))
        self.w.insert("end", "\n", base + ("para",))

    def _render_hr(self, block, base, depth):
        self.w.insert("end", "\n", base + ("spacer",))
        self._rule(base)

    def _render_code(self, block, base, depth):
        tags = base + ("codeblock",)
        self.w.insert("end", "\n", base + ("codeblock_pad",))
        for line in block.text.split("\n"):
            self._insert(line + "\n", {"mono": True, "scale": 0.92}, tags)
        self.w.insert("end", "\n", base + ("codeblock_pad", "after_block"))

    def _render_quote(self, block, base, depth):
        self.render_blocks(block.children, depth + 1)

    def _render_list(self, block, base, depth):
        counters: dict[int, int] = {}
        for level, marker, task, text in block.items:
            for deeper in [k for k in counters if k > level]:
                del counters[deeper]
            tags = base + (self._list_tag(level, depth),)
            if task is not None:
                bullet = "☑" if task else "☐"
            elif marker[0].isdigit():
                counters[level] = counters.get(level, int(marker[:-1]) - 1) + 1
                bullet = f"{counters[level]}."
            else:
                bullet = BULLETS[level % len(BULLETS)]
            self._insert(bullet + " ", {"bold": marker[0].isdigit()}, tags)
            self.inline(text, {}, tags + (("muted", "strike") if task else ()))
            self.w.insert("end", "\n", tags)
        self.w.insert("end", "\n", base + ("table",))

    def _render_table(self, block, base, depth):
        ncols = max(len(block.header), *(len(r) for r in block.rows)) if block.rows else len(block.header)
        rows = [block.header + [""] * (ncols - len(block.header))]
        rows += [r + [""] * (ncols - len(r)) for r in block.rows]
        cells = [[plain_inline(c) for c in r[:ncols]] for r in rows]
        widths = [max(display_width(r[c]) for r in cells) for c in range(ncols)]
        aligns = block.aligns + ["left"] * (ncols - len(block.aligns))

        def fmt(row):
            out = []
            for c, cell in enumerate(row):
                pad = widths[c] - display_width(cell)
                if aligns[c] == "right":
                    cell = " " * pad + cell
                elif aligns[c] == "center":
                    cell = " " * (pad // 2) + cell + " " * (pad - pad // 2)
                else:
                    cell = cell + " " * pad
                out.append(" " + cell + " ")
            return "│" + "│".join(out) + "│"

        border = lambda l, m, r: l + m.join("─" * (w + 2) for w in widths) + r
        tags = base + ("table",)
        mono = {"mono": True}
        self._insert(border("┌", "┬", "┐") + "\n", mono, tags + ("muted",))
        self._insert(fmt(cells[0]) + "\n", dict(mono, bold=True), tags)
        self._insert(border("├", "┼", "┤") + "\n", mono, tags + ("muted",))
        for row in cells[1:]:
            self._insert(fmt(row) + "\n", mono, tags)
        self._insert(border("└", "┴", "┘") + "\n", mono, tags + ("muted",))
        self.w.insert("end", "\n", base + ("table",))
