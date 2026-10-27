import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from pynotepad import markdown_view as M
from pynotepad.app import NotepadApp
from pynotepad.settings import Settings

SAMPLE = """# 제목 1

본문 **굵게** *기울임* ~~취소선~~ `코드` [링크](https://example.com)
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

```python
print("hi")
```

| 이름 | 수량 |
|:-----|----:|
| 사과 | 3 |
| 바나나 | 12 |

***
"""


class ParseTests(unittest.TestCase):
    def test_block_kinds(self):
        kinds = [b.kind for b in M.parse(SAMPLE)]
        self.assertEqual(kinds, ["heading", "para", "heading", "list", "list", "quote", "code", "table", "hr"])

    def test_setext_and_hard_break(self):
        blocks = M.parse(SAMPLE)
        self.assertEqual((blocks[2].text, blocks[2].level), ("부제목", 2))
        self.assertIn("두 번째 줄\n강제 줄바꿈 뒤", blocks[1].text)

    def test_lists_levels_and_tasks(self):
        items = M.parse(SAMPLE)[3].items
        self.assertEqual([(lvl, task, text) for lvl, _m, task, text in items],
                         [(0, None, "항목 A"), (1, None, "하위 항목"), (0, True, "완료"), (0, False, "할 일")])

    def test_table(self):
        table = M.parse(SAMPLE)[7]
        self.assertEqual(table.header, ["이름", "수량"])
        self.assertEqual(table.aligns, ["left", "right"])
        self.assertEqual(table.rows, [["사과", "3"], ["바나나", "12"]])

    def test_code_and_quote(self):
        blocks = M.parse(SAMPLE)
        self.assertEqual((blocks[6].lang, blocks[6].text), ("python", 'print("hi")'))
        self.assertEqual([b.kind for b in blocks[5].children], ["para"])

    def test_plain_inline_and_width(self):
        self.assertEqual(M.plain_inline("**굵게** `x` [a](http://b)"), "굵게 x a")
        self.assertEqual(M.display_width("가a"), 3)

    def test_underscore_inside_word_is_not_italic(self):
        self.assertEqual(M.plain_inline("snake_case_name"), "snake_case_name")


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.text = tk.Text(self.root)
        self.opened = []
        self.r = M.MarkdownRenderer(self.text, "맑은 고딕", "D2Coding", 12, on_link=self.opened.append)
        self.r.render(SAMPLE)

    def tearDown(self):
        self.root.destroy()

    def tagged(self, tag: str) -> str:
        ranges = self.text.tag_ranges(tag)
        return "".join(self.text.get(a, b) for a, b in zip(ranges[::2], ranges[1::2]))

    def test_markup_is_removed_and_styled(self):
        content = self.text.get("1.0", "end")
        self.assertNotIn("**", content)
        self.assertNotIn("```", content)
        self.assertIn("굵게", self.tagged("f1.0-100"))
        self.assertIn("기울임", self.tagged("f1.0-010"))
        self.assertEqual(self.tagged("strike").strip(), "취소선완료")
        self.assertIn('print("hi")', self.tagged("codeblock"))

    def test_trailing_horizontal_rule_is_kept(self):
        self.assertTrue(self.text.tag_ranges("rule"))
        last_rule = self.text.tag_ranges("rule")[-1]
        self.assertTrue(self.text.compare(last_rule, ">", self.text.tag_ranges("table")[-1]))

    def test_read_only(self):
        self.assertEqual(self.text.cget("state"), "disabled")

    def test_links_open_only_safe_schemes(self):
        name = next(n for n, h in self.r.links.items() if h == "https://example.com")
        self.r._open("https://example.com")
        self.r._open("javascript:alert(1)")
        self.r._open("file:///C:/Windows/System32/calc.exe")
        self.assertEqual(self.opened, ["https://example.com"])
        self.assertEqual(self.tagged(name), "링크")

    def test_table_columns_align(self):
        rows = [ln for ln in self.tagged("table").split("\n") if ln.startswith("│")]
        widths = {M.display_width(r) for r in rows}
        self.assertEqual(len(widths), 1, rows)
        self.assertTrue(rows[1].rstrip("│").endswith(" 3 "))  # right aligned

    def test_bullets(self):
        content = self.text.get("1.0", "end")
        for mark in ("• 항목 A", "◦ 하위 항목", "☑ 완료", "☐ 할 일", "1. 첫째", "2. 둘째"):
            self.assertIn(mark, content)


class AppPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NotepadApp(self.root, settings=Settings(self.tmp / "s.json"))

    def tearDown(self):
        self.root.destroy()

    def test_markdown_opens_in_preview_and_toggles(self):
        md = self.tmp / "doc.md"
        md.write_bytes(SAMPLE.encode("utf-8"))
        self.app.load_file(md)
        self.root.update()
        self.assertTrue(self.app.preview_mode)
        self.assertEqual(self.app.preview_button.cget("text"), "✎ 원본 보기")
        self.assertEqual(self.app.preview_button.winfo_manager(), "pack")
        self.assertEqual(self.app.status_labels["pos"].cget("text"), " 마크다운 미리 보기")
        self.app.cmd_toggle_preview()
        self.root.update()
        self.assertFalse(self.app.preview_mode)
        self.assertEqual(self.app.text.winfo_manager(), "grid")
        self.assertEqual(self.app.preview.winfo_manager(), "")
        self.assertEqual(self.app.preview_button.cget("text"), "▶ 미리 보기")
        self.assertEqual(self.app.get_text(), SAMPLE)  # the source is untouched

    def test_preview_reflects_unsaved_edits(self):
        md = self.tmp / "doc.md"
        md.write_bytes(b"# A\n")
        self.app.load_file(md)
        self.app.set_preview(False)
        self.app.text.insert("end", "\n**new**")
        self.app.set_preview(True)
        self.assertIn("new", self.app.preview.get("1.0", "end"))
        self.assertNotIn("**", self.app.preview.get("1.0", "end"))

    def test_plain_text_has_no_button_and_editing_leaves_preview(self):
        txt = self.tmp / "a.txt"
        txt.write_bytes(b"x")
        self.app.load_file(txt)
        self.root.update()
        self.assertFalse(self.app.preview_mode)
        self.assertEqual(self.app.preview_button.winfo_manager(), "")
        self.app.set_preview(True)          # preview works for any document from the 보기 menu
        self.app.cmd_paste()                # editing command switches back to the source
        self.assertFalse(self.app.preview_mode)

    def test_zoom_rerenders_preview(self):
        md = self.tmp / "doc.md"
        md.write_bytes(b"hello")
        self.app.load_file(md)
        self.app.cmd_zoom_in()
        fonts = {self.app.preview.tag_cget(t, "font") for t in self.app.preview.tag_names() if t.startswith("f1.0")}
        self.assertTrue(any(" 13" in f or "13" in f.split() for f in fonts), fonts)


if __name__ == "__main__":
    unittest.main()
