"""Dialogs laid out after the MUI dialog templates (찾기 1540, 바꾸기 1541, 줄 이동 14)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import encoding, resources as R


class _Modal(tk.Toplevel):
    def __init__(self, master: tk.Misc, title: str):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.result = None

    def run(self):
        self.update_idletasks()
        master = self.master
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_reqwidth()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.grab_set()
        self.wait_window()
        return self.result


class SaveChangesDialog(_Modal):
    """'변경 내용을 %1에 저장하시겠습니까?' with 저장 / 저장 안 함 / 취소. Returns True, False or None."""

    def __init__(self, master: tk.Misc, name: str):
        super().__init__(master, R.APP_NAME)
        frame = ttk.Frame(self, padding=(16, 16, 16, 8))
        frame.pack(fill="both")
        ttk.Label(frame, text=R.MSG_SAVE_CHANGES.format(name=name), wraplength=360).pack(anchor="w")
        buttons = ttk.Frame(self, padding=(16, 8, 16, 16))
        buttons.pack(fill="x")
        ttk.Button(buttons, text=R.BTN_CANCEL, command=self._cancel).pack(side="right")
        ttk.Button(buttons, text=R.BTN_DONT_SAVE, underline=6, command=self._no).pack(side="right", padx=6)
        save = ttk.Button(buttons, text=R.BTN_SAVE, underline=3, command=self._yes)
        save.pack(side="right")
        self.bind("<Return>", lambda _e: self._yes())
        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Alt-s>", lambda _e: self._yes())
        self.bind("<Alt-n>", lambda _e: self._no())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        save.focus_set()

    def _yes(self):
        self.result = True
        self.destroy()

    def _no(self):
        self.result = False
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class GoToDialog(_Modal):
    """줄 이동 dialog. Returns the 1-based line number or None."""

    def __init__(self, master: tk.Misc, current_line: int, line_count: int):
        super().__init__(master, "줄 이동")
        self.line_count = line_count
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both")
        ttk.Label(frame, text="줄 번호(L):", underline=4).grid(row=0, column=0, columnspan=2, sticky="w")
        self.var = tk.StringVar(value=str(current_line))
        entry = ttk.Entry(frame, textvariable=self.var, width=32)
        entry.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 12))
        ttk.Button(frame, text="이동", command=self._ok).grid(row=2, column=0, sticky="e", padx=(0, 6))
        ttk.Button(frame, text=R.BTN_CANCEL, command=self.destroy).grid(row=2, column=1, sticky="e")
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        entry.focus_set()
        entry.select_range(0, "end")

    def _ok(self):
        from tkinter import messagebox

        try:
            line = int(self.var.get())
        except ValueError:
            return
        if line < 1 or line > self.line_count:
            messagebox.showinfo(R.MSG_GOTO_TITLE, R.MSG_LINE_OUT_OF_RANGE, parent=self)
            return
        self.result = line
        self.destroy()


class EncodingDialog(_Modal):
    """Stand-in for the 인코딩(E) combo box of the save dialog (resource 15). Returns an encoding ID."""

    def __init__(self, master: tk.Misc, current: int):
        super().__init__(master, "인코딩")
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both")
        ttk.Label(frame, text="인코딩(E):", underline=4).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.combo = ttk.Combobox(frame, state="readonly", width=20,
                                  values=[encoding.NAMES[e] for e in encoding.CHOICES])
        self.combo.current(encoding.CHOICES.index(current) if current in encoding.CHOICES else 3)
        self.combo.grid(row=0, column=1, sticky="we")
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text=R.BTN_OK, command=self._ok).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text=R.BTN_CANCEL, command=self.destroy).pack(side="left")
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.combo.focus_set()

    def _ok(self):
        self.result = encoding.CHOICES[self.combo.current()]
        self.destroy()


class FindReplaceDialog(tk.Toplevel):
    """Modeless 찾기 / 바꾸기 dialog. Calls back into the app for the actual work."""

    def __init__(self, app, replace: bool):
        super().__init__(app.root)
        self.app = app
        self.replace_mode = replace
        self.title("바꾸기" if replace else "찾기")
        self.resizable(False, False)
        self.transient(app.root)
        s = app.settings

        self.find_var = tk.StringVar(value=app.selected_text_single_line() or s["searchString"])
        self.replace_var = tk.StringVar(value=s["replaceString"])
        self.whole_word = tk.BooleanVar(value=s["fWholeWord"])
        self.match_case = tk.BooleanVar(value=s["fMatchCase"])
        self.wrap_around = tk.BooleanVar(value=s["fWrapAround"])
        self.direction = tk.StringVar(value="up" if s["fReverse"] else "down")

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both")
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nw")
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="ne", padx=(12, 0))

        ttk.Label(left, text="찾을 내용(N):", underline=7).grid(row=0, column=0, sticky="w")
        self.find_entry = ttk.Entry(left, textvariable=self.find_var, width=34)
        self.find_entry.grid(row=0, column=1, sticky="we", pady=2)
        row = 1
        if replace:
            ttk.Label(left, text="바꿀 내용(P):", underline=7).grid(row=1, column=0, sticky="w")
            ttk.Entry(left, textvariable=self.replace_var, width=34).grid(row=1, column=1, sticky="we", pady=2)
            row = 2

        opts = ttk.Frame(left)
        opts.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(opts, text="단어 단위로(W)", underline=7, variable=self.whole_word).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opts, text="대/소문자 구분(C)", underline=10, variable=self.match_case).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(opts, text="주위에 배치(R)", underline=7, variable=self.wrap_around).grid(row=2, column=0, sticky="w")
        if not replace:
            box = ttk.LabelFrame(opts, text="방향", padding=(6, 2))
            box.grid(row=0, column=1, rowspan=2, sticky="n", padx=(16, 0))
            ttk.Radiobutton(box, text="위로(U)", underline=3, value="up", variable=self.direction).pack(side="left")
            ttk.Radiobutton(box, text="아래로(D)", underline=4, value="down", variable=self.direction).pack(side="left")

        ttk.Button(right, text="다음 찾기(F)", underline=6, command=self.find_next).pack(fill="x", pady=1)
        if replace:
            ttk.Button(right, text="바꾸기(R)", underline=4, command=self.replace_one).pack(fill="x", pady=1)
            ttk.Button(right, text="모두 바꾸기(A)", underline=7, command=self.replace_all).pack(fill="x", pady=1)
        ttk.Button(right, text=R.BTN_CANCEL, command=self.close).pack(fill="x", pady=1)

        self.bind("<Return>", lambda _e: self.find_next())
        self.bind("<Escape>", lambda _e: self.close())
        self.bind("<Alt-f>", lambda _e: self.find_next())
        if replace:
            self.bind("<Alt-r>", lambda _e: self.replace_one())
            self.bind("<Alt-a>", lambda _e: self.replace_all())
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.update_idletasks()
        root = app.root
        self.geometry(f"+{root.winfo_rootx() + 80}+{root.winfo_rooty() + 80}")
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")

    def store_options(self):
        s = self.app.settings
        s["searchString"] = self.find_var.get()
        s["replaceString"] = self.replace_var.get()
        s["fWholeWord"] = self.whole_word.get()
        s["fMatchCase"] = self.match_case.get()
        s["fWrapAround"] = self.wrap_around.get()
        if not self.replace_mode:
            s["fReverse"] = self.direction.get() == "up"

    def find_next(self):
        self.store_options()
        down = True if self.replace_mode else self.direction.get() == "down"
        self.app.find_next(down=down, parent=self)

    def replace_one(self):
        self.store_options()
        self.app.replace_one(parent=self)

    def replace_all(self):
        self.store_options()
        self.app.replace_all()

    def close(self):
        self.store_options()
        self.app.find_dialog = None
        self.destroy()
        self.app.text.focus_set()
