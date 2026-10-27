"""Drives the real Tk window without user interaction (dialogs that would block are avoided)."""

import tempfile
import tkinter as tk
import tkinter.font as tkfont
import unittest
from pathlib import Path

from pynotepad import encoding as E
from pynotepad.app import NotepadApp, split_mnemonic
from pynotepad.settings import Settings


class AppSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NotepadApp(self.root, settings=Settings(self.tmp / "settings.json"))

    def tearDown(self):
        self.root.destroy()

    def test_mnemonic(self):
        self.assertEqual(split_mnemonic("저장(&S)"), ("저장(S)", 3))
        self.assertEqual(split_mnemonic("&확대하기/축소하기"), ("확대하기/축소하기", 0))

    def test_title_and_dirty(self):
        self.assertEqual(self.root.title(), "제목 없음 - Windows 메모장")
        self.app.text.insert("1.0", "x")
        self.root.update()
        self.assertTrue(self.app.dirty)
        self.assertEqual(self.root.title(), "*제목 없음 - Windows 메모장")

    def test_load_save_preserves_encoding_and_eol(self):
        src = self.tmp / "a.txt"
        src.write_bytes(E.encode("하나\n둘\n", E.UTF16_BE, "\n"))
        self.assertTrue(self.app.load_file(src))
        self.assertEqual(self.app.encoding, E.UTF16_BE)
        self.assertEqual(self.app.line_ending, "\n")
        self.assertEqual(self.app.status_labels["eol"].cget("text"), " Unix (LF)")
        self.assertEqual(self.app.status_labels["enc"].cget("text"), " UTF-16 BE")
        self.app.text.insert("end-1c", "셋")
        self.assertTrue(self.app.cmd_save())
        self.assertEqual(src.read_bytes(), E.encode("하나\n둘\n셋", E.UTF16_BE, "\n"))
        self.assertFalse(self.app.dirty)

    def test_log_file_gets_timestamp(self):
        src = self.tmp / "log.txt"
        src.write_bytes(b".LOG\r\nfirst\r\n")
        self.app.load_file(src)
        text = self.app.get_text()
        self.assertTrue(text.startswith(".LOG\nfirst\n\n"))
        self.assertTrue(text.endswith("\n"))
        self.assertGreater(len(text), len(".LOG\nfirst\n\n\n"))
        self.assertTrue(self.app.dirty)

    def test_lowercase_log_is_ignored(self):
        src = self.tmp / "log.txt"
        src.write_bytes(b".log\r\n")
        self.app.load_file(src)
        self.assertEqual(self.app.get_text(), ".log\n")

    def test_find_and_replace_all(self):
        self.app.text.insert("1.0", "apple Apple apple")
        self.app.text.mark_set("insert", "1.0")
        s = self.app.settings
        s["searchString"], s["replaceString"], s["fMatchCase"] = "apple", "pear", True
        self.assertTrue(self.app.find_next(down=True))
        self.assertEqual(self.app.selected_text(), "apple")
        self.assertTrue(self.app.find_next(down=True))
        self.assertEqual(self.app.text.index("sel.first"), "1.12")
        self.app.replace_all()
        self.assertEqual(self.app.get_text(), "pear Apple pear")
        self.app.cmd_undo()
        self.assertEqual(self.app.get_text(), "apple Apple apple")

    def test_zoom_limits(self):
        for _ in range(60):
            self.app.cmd_zoom_in()
        self.assertEqual(self.app.zoom, 500)
        for _ in range(60):
            self.app.cmd_zoom_out()
        self.assertEqual(self.app.zoom, 10)
        self.app.cmd_zoom_reset()
        self.assertEqual(self.app.status_labels["zoom"].cget("text"), " 100%")

    def test_status_position(self):
        self.app.text.insert("1.0", "ab\ncde")
        self.app.text.mark_set("insert", "2.2")
        self.app.update_status()
        self.assertEqual(self.app.status_labels["pos"].cget("text"), " 줄 2, 열 3")

    def test_word_wrap_toggle(self):
        self.app.wrap_var.set(True)
        self.app.cmd_word_wrap()
        self.assertEqual(self.app.text.cget("wrap"), "word")
        self.app.wrap_var.set(False)
        self.app.cmd_word_wrap()
        self.assertEqual(self.app.text.cget("wrap"), "none")

    def test_menu_bar_without_help_and_with_menu_font(self):
        labels = [b.cget("text") for b in self.app.menu_bar.winfo_children() if isinstance(b, tk.Menubutton)]
        self.assertEqual(labels, ["파일(F)", "편집(E)", "서식(O)", "보기(V)"])
        # Bundled fonts are registered for the process, so the paper theme's families are available.
        self.assertEqual(self.app.menu_font.actual("family"), "IBM Plex Sans KR Medium")
        self.assertEqual(tkfont.nametofont("TkDefaultFont").actual("family"), "IBM Plex Sans KR")
        self.assertEqual(self.app.menu_font.actual("size"), 11)
        self.assertEqual(str(self.app.edit_menu.cget("font")), str(self.app.menu_font))

    def test_default_theme_is_paper(self):
        self.assertEqual(self.app.settings["theme"], "paper")
        self.assertEqual(self.app.theme_button.cget("text"), "테마: 종이  ▾")
        self.assertEqual(self.app.menu_bar.cget("background"), "#F3F0EA")

    def test_switch_theme_restyles_and_persists(self):
        self.app.set_theme("slate")
        self.assertEqual(self.app.theme_button.cget("text"), "테마: 슬레이트  ▾")
        self.assertEqual(self.app.menu_bar.cget("background"), "#1E232B")
        self.assertEqual(str(self.app.edit_menu.cget("activebackground")), "#1F5BC4")
        self.assertEqual(self.app.menu_font.actual("family"), "Noto Sans KR Medium")
        self.app.settings.save()
        self.assertEqual(Settings(self.tmp / "settings.json")["theme"], "slate")

    def test_unknown_theme_falls_back_to_paper(self):
        settings = Settings(self.tmp / "other.json")
        settings["theme"] = "neon"
        app = NotepadApp(tk.Toplevel(self.root), settings=settings)
        self.assertEqual(app.theme_button.cget("text"), "테마: 종이  ▾")

    def test_doc_bar_shows_name_and_modified_marker(self):
        self.assertEqual(self.app.doc_name.cget("text"), "제목 없음")
        self.assertFalse(self.app.doc_dirty.winfo_manager())
        self.app.text.insert("1.0", "x")
        self.root.update()
        self.assertTrue(self.app.doc_dirty.winfo_manager())

    def test_default_body_font(self):
        if "D2Coding" in tkfont.families(self.root):
            self.assertEqual(self.app.font.actual("family"), "D2Coding")
        self.assertEqual(self.app.font.actual("size"), 12)

    def test_settings_persist(self):
        self.app.settings["fWrap"] = True
        self.app.settings.save()
        self.assertTrue(Settings(self.tmp / "settings.json")["fWrap"])


if __name__ == "__main__":
    unittest.main()
