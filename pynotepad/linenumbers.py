"""Line-number gutter for a Tk Text widget (not present in the original notepad.exe)."""

from __future__ import annotations

import tkinter as tk

GUTTER_BG = "#f5f5f5"
GUTTER_BORDER = "#e0e0e0"
NUMBER_FG = "#a0a0a0"
CURRENT_FG = "#303030"
PAD_LEFT, PAD_RIGHT = 10, 8

# Forwards every Text command to the renamed original and, after commands that can change the
# visible numbers, calls back into Python. Errors (e.g. "get sel.first" with no selection inside a
# Tk `catch`) propagate natively instead of passing through Python, which would break mainloop.
_PROXY_PROC = r"""
proc ::pynotepad::text_proxy {orig notify args} {
    set result [uplevel 1 [list $orig {*}$args]]
    set cmd [lindex $args 0]
    if {$cmd in {insert delete replace xview yview see edit configure}
            || ($cmd eq "mark" && [lindex $args 1] eq "set" && [lindex $args 2] eq "insert")} {
        $notify
    }
    return $result
}
"""


class LineNumbers(tk.Canvas):
    def __init__(self, master: tk.Misc, text: tk.Text, on_change=None):
        super().__init__(master, background=GUTTER_BG, highlightthickness=0, borderwidth=0, width=1)
        self.text = text
        self.border, self.number_fg, self.current_fg = GUTTER_BORDER, NUMBER_FG, CURRENT_FG
        self.on_change = on_change  # called (once per idle) after any edit, scroll or cursor move
        self._pending = None
        self._install_proxy()
        text.bind("<Configure>", lambda _e: self.schedule_redraw(), add="+")
        self.bind("<Destroy>", lambda _e: self._cancel(), add="+")

    def _cancel(self):
        if self._pending:
            self.after_cancel(self._pending)
            self._pending = None

    def _install_proxy(self):
        """Route every Text widget command through Python so edits, scrolls and cursor moves trigger a redraw."""
        self.tk.eval("namespace eval ::pynotepad {}")
        self.tk.eval(_PROXY_PROC)
        widget = self.text._w
        orig = widget + "_numbered"
        notify = self.register(self.schedule_redraw)
        self.tk.call("rename", widget, orig)
        self.tk.call("interp", "alias", "", widget, "", "::pynotepad::text_proxy", orig, notify)

    def set_colors(self, background: str, border: str, number: str, current: str):
        self.configure(background=background)
        self.border, self.number_fg, self.current_fg = border, number, current
        self.schedule_redraw()

    def schedule_redraw(self):
        if not self._pending:
            self._pending = self.after_idle(self.redraw)

    def redraw(self):
        self._pending = None
        if self.on_change is not None:
            self.on_change()
        if not self.winfo_ismapped():
            return
        text = self.text
        font = text.cget("font")
        total = int(text.index("end-1c").split(".")[0])
        digits = max(2, len(str(total)))
        width = PAD_LEFT + text.tk.call("font", "measure", font, "9" * digits) + PAD_RIGHT
        if int(self.cget("width")) != width:
            self.configure(width=width)

        self.delete("all")
        actual = text.tk.call("font", "actual", font)
        bold = (actual[1], actual[3], "bold")  # -family F -size S ...: the current number is drawn bold
        current = text.index("insert").split(".")[0]
        index = text.index("@0,0 linestart")
        last = int(text.index(f"@0,{text.winfo_height()}").split(".")[0])
        while True:
            line = index.split(".")[0]
            info = text.dlineinfo(index)
            if info is not None:
                is_current = line == current
                self.create_text(width - PAD_RIGHT, info[1], anchor="ne", text=line,
                                 font=bold if is_current else font,
                                 fill=self.current_fg if is_current else self.number_fg)
            if int(line) >= last:
                break
            following = text.index(f"{index} +1 lines")
            if following == index:
                break
            index = following
        self.create_line(width - 1, 0, width - 1, self.winfo_height(), fill=self.border)
