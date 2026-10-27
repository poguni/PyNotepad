import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from pynotepad.app import NotepadApp
from pynotepad.settings import Settings


class LineNumberTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("600x300+0+0")
        self.app = NotepadApp(self.root, settings=Settings(Path(tempfile.mkdtemp()) / "s.json"))
        self.gutter = self.app.line_numbers
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def numbers(self) -> list[str]:
        self.root.update()
        return [self.gutter.itemcget(i, "text") for i in self.gutter.find_all()
                if self.gutter.type(i) == "text"]

    def test_follows_edits(self):
        self.assertEqual(self.numbers(), ["1"])
        self.app.text.insert("1.0", "a\nb\nc")
        self.assertEqual(self.numbers(), ["1", "2", "3"])
        self.app.text.delete("2.0", "3.0")
        self.assertEqual(self.numbers(), ["1", "2"])
        self.app.cmd_undo()
        self.assertEqual(self.numbers(), ["1", "2", "3"])

    def test_scroll_shows_visible_lines_only(self):
        self.app.text.insert("1.0", "\n".join(str(i) for i in range(1, 501)))
        self.app.text.see("400.0")
        shown = self.numbers()
        self.assertIn("400", shown)
        self.assertNotIn("1", shown)
        self.assertLess(len(shown), 100)

    def test_width_grows_with_digits(self):
        self.app.text.insert("1.0", "x\n" * 5)
        self.root.update()
        narrow = int(self.gutter.cget("width"))
        self.app.text.insert("end", "x\n" * 2000)
        self.root.update()
        self.assertGreater(int(self.gutter.cget("width")), narrow)

    def test_wrapped_line_has_one_number(self):
        self.app.wrap_var.set(True)
        self.app.cmd_word_wrap()
        self.app.text.insert("1.0", "word " * 400 + "\nsecond")
        self.assertEqual(self.numbers()[:2], ["1", "2"])

    def test_toggle(self):
        self.app.line_numbers_var.set(False)
        self.app.cmd_line_numbers()
        self.root.update()
        self.assertFalse(self.gutter.winfo_ismapped())
        self.assertFalse(self.app.settings["fLineNumbers"])
        self.app.line_numbers_var.set(True)
        self.app.cmd_line_numbers()
        self.root.update()
        self.assertTrue(self.gutter.winfo_ismapped())

    def test_status_follows_programmatic_cursor_moves(self):
        self.app.text.insert("1.0", "ab\ncdef")
        self.app.text.mark_set("insert", "2.3")
        self.root.update()
        self.assertEqual(self.app.status_labels["pos"].cget("text"), " 줄 2, 열 4")

    def test_tk_errors_still_reach_callers(self):
        # Copy with no selection: Tk catches the error internally; nothing may leak into mainloop.
        self.app.text.event_generate("<<Copy>>")
        self.root.update()
        with self.assertRaises(tk.TclError):
            self.app.text.index("sel.first")


if __name__ == "__main__":
    unittest.main()
