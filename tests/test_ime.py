"""Inline IME composition: rendering and message handling, driven with synthetic window messages."""

import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from pynotepad import ime
from pynotepad.app import NotepadApp
from pynotepad.settings import Settings


@unittest.skipUnless(sys.platform == "win32", "Windows IME only")
class InlineCompositionTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("500x300+0+0")
        self.app = NotepadApp(self.root, settings=Settings(Path(tempfile.mkdtemp()) / "s.json"))
        self.app.text.insert("1.0", "Hello\n")
        self.app.text.focus_force()
        self.root.update()
        self.comp = self.app.ime

    def tearDown(self):
        self.root.destroy()

    def send(self, msg, wparam=0, lparam=0):
        return ime._user32.CallWindowProcW(ctypes_ptr(self.comp._proc), self.comp.hwnd, msg, wparam, lparam)

    def test_composition_uses_editor_font_at_caret(self):
        self.app.text.mark_set("insert", "2.0")
        self.comp.show("고")
        self.root.update()
        label = self.comp.label
        self.assertTrue(label.winfo_ismapped())
        self.assertEqual(label.cget("text"), "고")
        self.assertEqual(str(label.cget("font")), str(self.app.font))
        x, y, _w, _h = self.app.text.bbox("insert")
        self.assertEqual(int(label.place_info()["x"]), x)
        # Baseline of the overlay matches the baseline of the text line.
        line = self.app.text.dlineinfo("insert")
        self.assertEqual(int(label.place_info()["y"]) + self.app.font.metrics("ascent"), line[1] + line[4])

    def test_follows_zoom(self):
        self.app.cmd_zoom_in()
        self.comp.show("가")
        self.assertEqual(str(self.comp.label.cget("font")), str(self.app.font))

    def test_start_and_end_messages_are_consumed_and_hide_overlay(self):
        self.comp.composition = "고"
        self.comp.sync()
        self.root.update()
        self.assertTrue(self.comp.label.winfo_ismapped())
        self.assertEqual(self.send(ime.WM_IME_STARTCOMPOSITION), 0)
        self.assertEqual(self.comp.composition, "")
        self.comp.sync()
        self.root.update()
        self.assertFalse(self.comp.label.winfo_ismapped())
        self.comp.composition = "고"
        self.assertEqual(self.send(ime.WM_IME_ENDCOMPOSITION), 0)
        self.assertEqual(self.comp.composition, "")

    def test_messages_during_tk_activity_do_not_crash(self):
        # Regression: calling Tk from the window procedure aborted the interpreter
        # (PyEval_RestoreThread with a NULL thread state) on the next Tcl->Python callback.
        for _ in range(50):
            self.send(ime.WM_IME_STARTCOMPOSITION)
            self.send(ime.WM_IME_COMPOSITION, 0, ime.GCS_COMPSTR)
            self.send(ime.WM_IME_ENDCOMPOSITION)
            self.app.text.insert("end", "x")  # triggers the line-number Tcl->Python callback
            self.root.update()
        self.assertTrue(self.app.get_text().endswith("x" * 50))

    def test_key_event_starts_sync(self):
        self.comp.composition = "가"
        self.app.text.event_generate("<KeyRelease>", keycode=229, keysym="space")
        self.root.after(50, self.root.quit)
        self.root.mainloop()
        self.assertEqual(self.comp.label.cget("text"), "가")
        self.assertTrue(self.comp.label.winfo_ismapped())

    def test_overlay_does_not_touch_document(self):
        self.app.text.edit_reset()
        self.app.dirty = False
        self.comp.show("고")
        self.comp.hide()
        self.assertEqual(self.app.get_text(), "Hello\n")
        self.assertFalse(self.app.dirty)
        self.assertFalse(self.app.text.edit("canundo"))

    def test_other_messages_pass_through(self):
        # Non-IME messages (here WM_GETTEXTLENGTH) give exactly what the original window procedure gives.
        original = ime._user32.CallWindowProcW(self.comp._old, self.comp.hwnd, 0x000E, 0, 0)
        self.assertEqual(self.send(0x000E), original)


def ctypes_ptr(proc):
    import ctypes
    return ctypes.cast(proc, ctypes.c_void_p)


if __name__ == "__main__":
    unittest.main()
