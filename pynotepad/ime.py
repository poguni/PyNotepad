"""Inline IME composition for the editor on Windows.

Tk 8.6 leaves the syllable being composed (e.g. Korean '고' before it is committed) to the IME's own
composition window, which is drawn in a small default font at the caret. This module subclasses the
toplevel's Win32 window, hides that window and draws the composition string itself, directly
at the caret in the editor font. Committed text still goes through Tk's own handling, so undo, the
modified flag and key bindings behave exactly as before. No-op on other platforms.
"""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from ctypes import wintypes

WM_IME_SETCONTEXT = 0x0281
WM_IME_STARTCOMPOSITION = 0x010D
WM_IME_ENDCOMPOSITION = 0x010E
WM_IME_COMPOSITION = 0x010F
GCS_COMPSTR = 0x0008
GCS_RESULTSTR = 0x0800
ISC_SHOWUICOMPOSITIONWINDOW = 0x80000000
GWLP_WNDPROC = -4

if sys.platform == "win32":
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _user32 = ctypes.WinDLL("user32")
    _user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    _user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    _user32.CallWindowProcW.restype = LRESULT
    _user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                        wintypes.WPARAM, wintypes.LPARAM]
    _imm32 = ctypes.WinDLL("imm32")
    _imm32.ImmGetContext.restype = wintypes.HANDLE
    _imm32.ImmGetContext.argtypes = [wintypes.HWND]
    _imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
    _imm32.ImmGetCompositionStringW.restype = wintypes.LONG
    _imm32.ImmGetCompositionStringW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                                wintypes.DWORD]


def _composition_string(hwnd: int) -> str:
    himc = _imm32.ImmGetContext(hwnd)
    if not himc:
        return ""
    try:
        size = _imm32.ImmGetCompositionStringW(himc, GCS_COMPSTR, None, 0)
        if size <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(size // 2 + 1)
        _imm32.ImmGetCompositionStringW(himc, GCS_COMPSTR, buf, size)
        return buf.value
    finally:
        _imm32.ImmReleaseContext(hwnd, himc)


POLL_MS = 15


class InlineComposition:
    """Draws the IME composition string at the caret of `text` using `get_font()`.

    The window procedure runs inside Tcl's event dispatch while tkinter has released the GIL, so it
    must never call back into Tk (that corrupts tkinter's thread state and aborts the interpreter).
    It only records the composition string; the Tk side applies it from key events and, while a
    syllable is being composed, from a short `after` loop.
    """

    def __init__(self, text: tk.Text, get_font):
        self.text = text
        self.get_font = get_font
        self.label = tk.Label(text, borderwidth=0, padx=0, pady=0, highlightthickness=0)
        self.composition = ""   # written by the window procedure
        self._shown = None      # what the overlay currently displays
        self._polling = None    # pending `after` id while the overlay is being synced
        self.active = sys.platform == "win32"
        if not self.active:
            return
        text.update_idletasks()
        # Keyboard focus (and so every IME message) goes to the toplevel's own window, not its wm frame.
        self.hwnd = text.winfo_toplevel().winfo_id()
        self._proc = WNDPROC(self._wndproc)  # keep a reference: the window holds a raw pointer to it
        self._old = _user32.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC,
                                              ctypes.cast(self._proc, ctypes.c_void_p))
        for seq in ("<KeyPress>", "<KeyRelease>"):
            text.bind(seq, lambda _e: self.kick(), add="+")
        text.bind("<Destroy>", lambda _e: self.detach(), add="+")

    def detach(self):
        if self._polling:
            self.text.after_cancel(self._polling)
            self._polling = None
        if self.active and self._old:
            _user32.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC, self._old)
            self._old = None

    # ---- Win32 side: no Tk calls allowed here ----

    def _call_original(self, hwnd, msg, wparam, lparam):
        return _user32.CallWindowProcW(self._old, hwnd, msg, wparam, lparam)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_IME_SETCONTEXT:
                # Tell the IME that the application draws the composition string itself.
                lparam &= ~ISC_SHOWUICOMPOSITIONWINDOW
            elif msg in (WM_IME_STARTCOMPOSITION, WM_IME_ENDCOMPOSITION):
                self.composition = ""
                return 0  # not passed on: the IME's own composition window never appears
            elif msg == WM_IME_COMPOSITION:
                result = 0
                if lparam & GCS_RESULTSTR:
                    self.composition = ""
                    result = self._call_original(hwnd, msg, wparam, lparam & ~GCS_COMPSTR)
                if lparam & GCS_COMPSTR:
                    self.composition = _composition_string(hwnd)
                return result
        except Exception:  # never let an exception escape into the Win32 message loop
            self.composition = ""
        return self._call_original(hwnd, msg, wparam, lparam)

    # ---- Tk side ----

    def kick(self):
        """Start syncing the overlay (called from key events, i.e. safely inside tkinter)."""
        if not self._polling:
            self._polling = self.text.after(1, self._poll)

    def _poll(self):
        self.sync()
        self._polling = self.text.after(POLL_MS, self._poll) if self.composition else None

    def sync(self):
        if self.composition != self._shown:
            if self.composition:
                self.show(self.composition)
            else:
                self.hide()

    def show(self, composition: str):
        if not composition:
            self.hide()
            return
        text = self.text
        text.see("insert")
        bbox = text.bbox("insert")
        line = text.dlineinfo("insert")
        if bbox is None or line is None:
            self.hide()
            return
        font = self.get_font()
        baseline_y = line[1] + line[4]
        self.label.configure(text=composition, font=font, background=text.cget("background"),
                             foreground=text.cget("foreground"))
        self.label.place(x=bbox[0], y=baseline_y - font.metrics("ascent"))
        self.label.lift()
        self._shown = composition

    def hide(self):
        self._shown = None
        if self.label.place_info():
            self.label.place_forget()
