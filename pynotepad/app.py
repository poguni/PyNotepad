"""Main window: a Tk re-creation of the classic Windows Notepad (notepad.exe 10.0.26100)."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk
from urllib.parse import quote_plus

from . import encoding, ime, resources as R, search, themes
from .dialogs import EncodingDialog, FindReplaceDialog, GoToDialog, SaveChangesDialog
from .linenumbers import LineNumbers
from .markdown_view import MarkdownRenderer
from .settings import Settings

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 10, 500, 10

# UI typography (menus, status bar, dialogs) comes from the active theme (themes.py). The native
# Windows menu bar ignores Tk fonts, so the bar is built from Menubuttons.
MENU_FONT_SIZE = 11
STATUS_FONT_SIZE = 10
CHIP_FONT_SIZE = 9
TK_NAMED_FONTS = ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont",
                  "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont")
THEME_BOX_FORMAT = "테마: {label}  ▾"
MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd"}
PREVIEW_LABEL, SOURCE_LABEL = "▶ 미리 보기", "✎ 원본 보기"

# Windows virtual-key codes used by the accelerator tables (GLOBALACC / MAINACC).
VK_INSERT, VK_0, VK_NUMPAD0, VK_ADD, VK_SUBTRACT, VK_OEM_PLUS, VK_OEM_MINUS = (
    0x2D, 0x30, 0x60, 0x6B, 0x6D, 0xBB, 0xBD)
SHIFT_MASK = 0x0001
CONTROL_MASK = 0x0004


def split_mnemonic(text: str) -> tuple[str, int]:
    """'저장(&S)' -> ('저장(S)', 3): strip the Win32 '&' marker and return Tk's underline index."""
    index = text.find("&")
    if index < 0:
        return text, -1
    return text[:index] + text[index + 1:], index


def windows_time_date() -> str:
    """'time date' exactly as notepad builds it: GetTimeFormatW(TIME_NOSECONDS) + ' ' + GetDateFormatW(DATE_SHORTDATE)."""
    if sys.platform == "win32":
        buf_t = ctypes.create_unicode_buffer(80)
        buf_d = ctypes.create_unicode_buffer(80)
        kernel32 = ctypes.windll.kernel32
        if (kernel32.GetTimeFormatW(0x400, 0x2, None, None, buf_t, 80)
                and kernel32.GetDateFormatW(0x400, 0x1, None, None, buf_d, 80)):
            return f"{buf_t.value} {buf_d.value}"
    return time.strftime("%H:%M %Y-%m-%d")


class NotepadApp:
    def __init__(self, root: tk.Tk, path: str | None = None, settings: Settings | None = None):
        self.root = root
        self.settings = settings or Settings()
        self.path: Path | None = None
        self.encoding = self.settings["iDefaultEncoding"]
        self.line_ending = "\r\n"
        self.zoom = 100
        self.find_dialog: FindReplaceDialog | None = None

        self.wrap_var = tk.BooleanVar(value=bool(self.settings["fWrap"]))
        self.status_var = tk.BooleanVar(value=bool(self.settings["StatusBar"]))
        self.line_numbers_var = tk.BooleanVar(value=bool(self.settings["fLineNumbers"]))
        self.preview_var = tk.BooleanVar(value=False)
        self.theme = themes.get(self.settings["theme"])
        self.theme_var = tk.StringVar(value=self.settings["theme"] if self.settings["theme"] in themes.THEMES
                                      else themes.DEFAULT_THEME)

        themes.register_fonts()
        self._build_window()
        self._build_menus()
        self._build_bindings()
        self.apply_theme()
        self.apply_font()
        self.apply_wrap()
        self.apply_status_bar()
        self.apply_line_numbers()
        self.update_title()

        if path:
            self.open_from_command_line(path)
        self.text.focus_set()

    # ------------------------------------------------------------------ layout

    def _build_window(self):
        s = self.settings
        self.root.title(R.APP_NAME)
        geometry = f"{s['iWindowPosDX']}x{s['iWindowPosDY']}"
        if s["fSaveWindowPositions"] and s["iWindowPosX"] is not None and s["iWindowPosY"] is not None:
            geometry += f"+{s['iWindowPosX']}+{s['iWindowPosY']}"
        self.root.geometry(geometry)
        self.root.protocol("WM_DELETE_WINDOW", self.cmd_exit)

        # Document row under the menu bar: the name in the theme font (the native title bar's font is fixed).
        self.doc_bar = tk.Frame(self.root)
        self.doc_bar.pack(side="top", fill="x")

        self.editor_frame = ttk.Frame(self.root)
        self.editor_frame.pack(side="top", fill="both", expand=True)
        self.editor_frame.rowconfigure(0, weight=1)
        self.editor_frame.columnconfigure(1, weight=1)

        self.text = tk.Text(self.editor_frame, undo=True, autoseparators=True, maxundo=-1,
                            borderwidth=0, highlightthickness=0, padx=14, pady=8,
                            exportselection=True, tabs=None)
        self.text.grid(row=0, column=1, sticky="nsew")
        self.line_numbers = LineNumbers(self.editor_frame, self.text, on_change=self.update_status)
        self.line_numbers.grid(row=0, column=0, sticky="ns")
        self.vscroll = ttk.Scrollbar(self.editor_frame, orient="vertical", command=self.text.yview)
        self.vscroll.grid(row=0, column=2, sticky="ns")
        self.hscroll = ttk.Scrollbar(self.editor_frame, orient="horizontal", command=self.text.xview)
        self.hscroll.grid(row=1, column=1, sticky="ew")
        self.text.configure(yscrollcommand=self.vscroll.set, xscrollcommand=self.hscroll.set)

        # Markdown preview: a read-only Text in the same grid cell, swapped with the editor.
        self.preview = tk.Text(self.editor_frame, wrap="word", borderwidth=0, highlightthickness=0,
                               padx=28, pady=16, background="white", insertwidth=0, state="disabled")
        self.preview.grid(row=0, column=1, sticky="nsew")
        self.preview.grid_remove()
        self.preview_mode = False

        # Status bar: [ ... | 줄, 열 | zoom | line ending | encoding ] (tk widgets so the theme can color them)
        self.status = tk.Frame(self.root)
        self.status_line = tk.Frame(self.status, height=1)
        self.status_line.pack(side="top", fill="x")
        self.status_seps = []
        self.status_labels = {}
        tk.Frame(self.status, height=0).pack(side="left", fill="x", expand=True)
        for key, width in (("pos", 18), ("zoom", 7), ("eol", 16), ("enc", 12)):
            sep = tk.Frame(self.status, width=1)
            sep.pack(side="left", fill="y", pady=5)
            self.status_seps.append(sep)
            label = tk.Label(self.status, width=width, anchor="w", padx=6, pady=3)
            label.pack(side="left")
            self.status_labels[key] = label

        self.context_menu = tk.Menu(self.root, tearoff=False)
        self.menus = [self.context_menu]  # every tk.Menu, recolored by apply_theme()

    def _menu_item(self, menu: tk.Menu, text: str, command, accel: str = "", **kw):
        label, underline = split_mnemonic(text)
        menu.add_command(label=label, underline=underline, command=command, accelerator=accel, **kw)
        return menu.index("end")

    def _apply_ui_font(self):
        """Set the theme's UI families on the menu/status/document fonts and every Tk named font (dialogs).

        Widgets hold these Font objects, so reconfiguring them restyles the whole window in place.
        """
        installed = set(tkfont.families(self.root))
        t = self.theme
        regular = themes.resolve_family(t["font"], installed)
        medium = themes.resolve_family(t["font_medium"], installed)
        title = themes.resolve_family(t["font_title"], installed)
        for name in TK_NAMED_FONTS:
            tkfont.nametofont(name, root=self.root).configure(family=regular)
        self.ui_family = regular
        specs = {
            "menu_font": dict(family=medium, size=MENU_FONT_SIZE),
            "status_font": dict(family=regular, size=STATUS_FONT_SIZE),
            "title_font": dict(family=title, size=t["title_size"]),
            "chip_font": dict(family=medium, size=CHIP_FONT_SIZE),
        }
        for attr, spec in specs.items():
            if hasattr(self, attr):
                getattr(self, attr).configure(**spec)
            else:
                setattr(self, attr, tkfont.Font(root=self.root, **spec))

    def _build_menus(self):
        self._apply_ui_font()
        bar = tk.Frame(self.root, padx=6, pady=3)
        bar.pack(side="top", fill="x", before=self.doc_bar)
        self.menu_bar = bar
        self.menu_buttons: list[tk.Menubutton] = []

        def cascade(text: str, **kw) -> tk.Menu:
            label, underline = split_mnemonic(text)
            button = tk.Menubutton(bar, text=label, underline=underline, font=self.menu_font,
                                   relief="flat", borderwidth=0, padx=10, pady=4, takefocus=False)
            button.pack(side="left", padx=1)
            self.menu_buttons.append(button)
            menu = tk.Menu(button, tearoff=False, font=self.menu_font, **kw)
            button.configure(menu=menu)
            self.menus.append(menu)
            return menu

        # Theme picker: a drop-down box at the right end of the menu bar (packed first so it stays rightmost).
        self.theme_box = tk.Frame(bar, padx=1, pady=1)
        self.theme_box.pack(side="right", padx=(6, 2))
        self.theme_button = tk.Menubutton(self.theme_box, font=self.menu_font, relief="flat", borderwidth=0,
                                          padx=12, pady=2, takefocus=False, cursor="hand2")
        self.theme_button.pack()
        theme_menu = tk.Menu(self.theme_button, tearoff=False, font=self.menu_font)
        for key, theme in themes.THEMES.items():
            theme_menu.add_radiobutton(label=theme["label"], value=key, variable=self.theme_var,
                                       command=lambda: self.set_theme(self.theme_var.get()))
        self.theme_button.configure(menu=theme_menu)
        self.menus.append(theme_menu)

        m = cascade("파일(&F)")
        self._menu_item(m, "새로 만들기(&N)", self.cmd_new, "Ctrl+N")
        self._menu_item(m, "새 창(&W)", self.cmd_new_window, "Ctrl+Shift+N")
        self._menu_item(m, "열기(&O)...", self.cmd_open, "Ctrl+O")
        self._menu_item(m, "저장(&S)", self.cmd_save, "Ctrl+S")
        self._menu_item(m, "다른 이름으로 저장(&A)...", self.cmd_save_as, "Ctrl+Shift+S")
        m.add_separator()
        self._menu_item(m, "인쇄(&P)...", self.cmd_print, "Ctrl+P")
        m.add_separator()
        self._menu_item(m, "끝내기(&X)", self.cmd_exit)

        m = cascade("편집(&E)", postcommand=self.update_edit_menu)
        self.edit_menu = m
        self.edit_items = {
            "undo": self._menu_item(m, "실행 취소(&U)", self.cmd_undo, "Ctrl+Z"),
        }
        m.add_separator()
        self.edit_items["cut"] = self._menu_item(m, "잘라내기(&T)", self.cmd_cut, "Ctrl+X")
        self.edit_items["copy"] = self._menu_item(m, "복사(&C)", self.cmd_copy, "Ctrl+C")
        self.edit_items["paste"] = self._menu_item(m, "붙여넣기(&P)", self.cmd_paste, "Ctrl+V")
        self.edit_items["delete"] = self._menu_item(m, "삭제(&L)", self.cmd_delete, "Del")
        m.add_separator()
        self.edit_items["google"] = self._menu_item(m, "Google로 검색(&S)...", self.cmd_search_google, "Ctrl+E")
        self._menu_item(m, "찾기(&F)...", self.cmd_find, "Ctrl+F")
        self.edit_items["find_next"] = self._menu_item(m, "다음 찾기(&N)", self.cmd_find_next, "F3")
        self.edit_items["find_prev"] = self._menu_item(m, "이전 찾기(&V)", self.cmd_find_prev, "Shift+F3")
        self._menu_item(m, "바꾸기(&R)...", self.cmd_replace, "Ctrl+H")
        self._menu_item(m, "이동(&G)...", self.cmd_goto, "Ctrl+G")
        m.add_separator()
        self._menu_item(m, "모두 선택(&A)", self.cmd_select_all, "Ctrl+A")
        self._menu_item(m, "시간/날짜(&D)", self.cmd_time_date, "F5")

        m = cascade("서식(&O)")
        label, underline = split_mnemonic("자동 줄 바꿈(&W)")
        m.add_checkbutton(label=label, underline=underline, variable=self.wrap_var, command=self.cmd_word_wrap)
        self._menu_item(m, "글꼴(&F)...", self.cmd_font)

        m = cascade("보기(&V)")
        zoom = tk.Menu(m, tearoff=False, font=self.menu_font)
        self.menus.append(zoom)
        label, underline = split_mnemonic("&확대하기/축소하기")
        m.add_cascade(label=label, underline=underline, menu=zoom)
        self._menu_item(zoom, "확대(&I)", self.cmd_zoom_in, "Ctrl+더하기")
        self._menu_item(zoom, "축소(&O)", self.cmd_zoom_out, "Ctrl+빼기")
        self._menu_item(zoom, "&확대하기/축소하기 기본값 복원", self.cmd_zoom_reset, "Ctrl+0")
        label, underline = split_mnemonic("상태 표시줄(&S)")
        m.add_checkbutton(label=label, underline=underline, variable=self.status_var, command=self.cmd_status_bar)
        label, underline = split_mnemonic("줄 번호(&L)")
        m.add_checkbutton(label=label, underline=underline, variable=self.line_numbers_var,
                          command=self.cmd_line_numbers)
        m.add_separator()
        label, underline = split_mnemonic("마크다운 미리 보기(&M)")
        m.add_checkbutton(label=label, underline=underline, variable=self.preview_var,
                          accelerator="Ctrl+Shift+M", command=lambda: self.set_preview(self.preview_var.get()))

        # Source/preview toggle at the right end of the menu bar (shown for Markdown documents).
        # A Label, not a tk.Button: the Windows button adds internal padding that made the bar taller.
        self.preview_button = tk.Label(bar, font=self.menu_font, padx=12, pady=2, cursor="hand2")
        self.preview_button.bind("<Button-1>", lambda _e: self.cmd_toggle_preview())
        self.preview_button.bind("<Enter>", lambda _e: self.preview_button.configure(state="active"))
        self.preview_button.bind("<Leave>", lambda _e: self.preview_button.configure(state="normal"))

        # Right-click menu of the edit control.
        c = self.context_menu
        c.configure(postcommand=self.update_edit_menu, font=self.menu_font)
        self.context_items = {
            "undo": self._menu_item(c, "실행 취소(&U)", self.cmd_undo),
        }
        c.add_separator()
        self.context_items["cut"] = self._menu_item(c, "잘라내기(&T)", self.cmd_cut)
        self.context_items["copy"] = self._menu_item(c, "복사(&C)", self.cmd_copy)
        self.context_items["paste"] = self._menu_item(c, "붙여넣기(&P)", self.cmd_paste)
        self.context_items["delete"] = self._menu_item(c, "삭제(&L)", self.cmd_delete)
        c.add_separator()
        self._menu_item(c, "모두 선택(&A)", self.cmd_select_all)
        c.add_separator()
        self.context_items["google"] = self._menu_item(c, "Google로 검색(&S)...", self.cmd_search_google)

    def _build_bindings(self):
        t = self.text
        self.ime = ime.InlineComposition(t, lambda: self.font)
        # Ctrl combinations are dispatched by virtual-key code so they work with the Korean IME and Caps Lock.
        t.bind("<Control-KeyPress>", self._on_control_key)
        self.root.bind("<Control-KeyPress>", self._on_control_key)
        for seq, handler in (
            ("<F3>", self.cmd_find_next),
            ("<Shift-F3>", self.cmd_find_prev),
            ("<F5>", self.cmd_time_date),
            ("<Alt-BackSpace>", self.cmd_undo),
        ):
            t.bind(seq, self._breaking(handler))
            self.root.bind(seq, self._breaking(handler))
        # Tk's default Alt/F10 handling targets the native menu bar, which this window does not use.
        for widget in (t, self.root):
            widget.bind("<Alt-KeyPress>", self._on_alt_key)
            widget.bind("<F10>", self._on_f10)
        t.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        p = self.preview
        p.bind("<Control-KeyPress>", self._on_control_key)
        p.bind("<Alt-KeyPress>", self._on_alt_key)
        p.bind("<F10>", self._on_f10)
        p.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        p.bind("<Button-3>", self._show_context_menu)
        t.bind("<Button-3>", self._show_context_menu)
        t.bind("<<Modified>>", lambda _e: self.update_title())
        # The title bar can only be colored once the window frame exists.
        self.root.bind("<Map>", lambda e: themes.apply_caption(self.root, self.theme) if e.widget is self.root
                       else None, add="+")
        for seq in ("<KeyRelease>", "<ButtonRelease-1>", "<B1-Motion>", "<<Selection>>"):
            t.bind(seq, lambda _e: self.update_status(), add="+")

    @staticmethod
    def _breaking(handler):
        def wrapped(_event=None):
            handler()
            return "break"
        return wrapped

    def _on_control_key(self, event):
        shift = bool(event.state & SHIFT_MASK)
        vk = event.keycode
        table = {
            (ord("N"), False): self.cmd_new,
            (ord("N"), True): self.cmd_new_window,
            (ord("O"), False): self.cmd_open,
            (ord("S"), False): self.cmd_save,
            (ord("S"), True): self.cmd_save_as,
            (ord("M"), True): self.cmd_toggle_preview,
            (ord("P"), False): self.cmd_print,
            (ord("W"), False): self.cmd_exit,
            (ord("G"), False): self.cmd_goto,
            (ord("F"), False): self.cmd_find,
            (ord("H"), False): self.cmd_replace,
            (ord("E"), False): self.cmd_search_google,
            (ord("A"), False): self.cmd_select_all,
            (ord("Z"), False): self.cmd_undo,
            (VK_INSERT, False): self.cmd_copy,
            (VK_OEM_PLUS, False): self.cmd_zoom_in,
            (VK_OEM_PLUS, True): self.cmd_zoom_in,
            (VK_ADD, False): self.cmd_zoom_in,
            (VK_OEM_MINUS, False): self.cmd_zoom_out,
            (VK_SUBTRACT, False): self.cmd_zoom_out,
            (VK_0, False): self.cmd_zoom_reset,
            (VK_NUMPAD0, False): self.cmd_zoom_reset,
        }
        handler = table.get((vk, shift))
        if handler:
            handler()
            return "break"
        # Ctrl+X / C / V (and Y for redo) keep Tk's built-in clipboard handling.
        if vk in (ord("X"), ord("C"), ord("V"), ord("Y")):
            return None
        # Swallow Tk's emacs-style Ctrl+letter bindings (Ctrl+K, Ctrl+T, ...) that the Win32 edit control lacks.
        if ord("A") <= vk <= ord("Z"):
            return "break"
        return None

    def _on_alt_key(self, event):
        """Alt+mnemonic opens the matching menu (by virtual-key code, so the Korean IME does not interfere)."""
        if not ord("A") <= event.keycode <= ord("Z"):
            return None
        char = chr(event.keycode).lower()
        for button in self.menu_buttons:
            label, underline = button.cget("text"), int(button.cget("underline"))
            if 0 <= underline < len(label) and label[underline].lower() == char:
                self.root.tk.call("tk::TraverseToMenu", str(event.widget), char)
                return "break"
        return None

    def _on_f10(self, event):
        self.root.tk.call("tk::FirstMenu", str(event.widget))
        return "break"

    def _on_ctrl_wheel(self, event):
        self.set_zoom(self.zoom + (ZOOM_STEP if event.delta > 0 else -ZOOM_STEP))
        return "break"

    def _show_context_menu(self, event):
        self.text.focus_set()
        self.context_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    # ------------------------------------------------------------------ state helpers

    @property
    def dirty(self) -> bool:
        return bool(self.text.edit_modified())

    @dirty.setter
    def dirty(self, value: bool):
        self.text.edit_modified(value)
        self.update_title()

    def display_name(self) -> str:
        return self.path.name if self.path else R.UNTITLED

    def update_title(self):
        self.root.title(R.TITLE_FORMAT.format(dirty="*" if self.dirty else "", name=self.display_name()))
        self.update_doc_bar()

    def get_text(self) -> str:
        return self.text.get("1.0", "end-1c")

    def has_selection(self) -> bool:
        return bool(self.text.tag_ranges("sel"))

    def selected_text(self) -> str:
        return self.text.get("sel.first", "sel.last") if self.has_selection() else ""

    def selected_text_single_line(self) -> str:
        sel = self.selected_text()
        return "" if "\n" in sel else sel

    def offset_of(self, index: str) -> int:
        result = self.text.count("1.0", index, "chars")
        if not result:
            return 0
        return int(result[0] if isinstance(result, tuple) else result)

    def index_of(self, offset: int) -> str:
        return f"1.0 + {offset} chars"

    def update_status(self):
        if self.preview_mode:
            self.status_labels["pos"].configure(text=" 마크다운 미리 보기")
        else:
            line, col = self.text.index("insert").split(".")
            self.status_labels["pos"].configure(text=R.STATUS_POSITION.format(line=line, col=int(col) + 1))
            self.text.tag_remove("current_line", "1.0", "end")
            self.text.tag_add("current_line", "insert linestart", "insert lineend +1c")
        self.status_labels["zoom"].configure(text=R.STATUS_ZOOM.format(zoom=self.zoom))
        self.status_labels["eol"].configure(text=R.LINE_ENDING_LABELS[self.line_ending])
        self.status_labels["enc"].configure(text=" " + encoding.NAMES[self.encoding])

    def update_edit_menu(self):
        has_sel = bool(self.active_widget().tag_ranges("sel"))
        try:
            has_clip = bool(self.root.clipboard_get())
        except tk.TclError:
            has_clip = False
        can_undo = bool(self.text.edit("canundo"))
        has_needle = bool(self.settings["searchString"])
        states = {
            "undo": can_undo, "cut": has_sel, "copy": has_sel, "paste": has_clip,
            "delete": has_sel, "google": has_sel, "find_next": has_needle, "find_prev": has_needle,
        }
        for items, menu in ((self.edit_items, self.edit_menu), (self.context_items, self.context_menu)):
            for key, index in items.items():
                menu.entryconfigure(index, state="normal" if states[key] else "disabled")

    # ------------------------------------------------------------------ font / view

    def apply_font(self):
        size = self.settings["iPointSize"] / 10 * self.zoom / 100
        self.font = tkfont.Font(family=self.settings["lfFaceName"], size=max(1, round(size)))
        self.text.configure(font=self.font)
        if self.preview_mode:
            self.render_preview(keep_position=True)
        self.update_status()

    def set_zoom(self, value: int):
        value = max(ZOOM_MIN, min(ZOOM_MAX, value))
        if value != self.zoom:
            self.zoom = value
            self.apply_font()

    def apply_wrap(self):
        if self.wrap_var.get() or self.preview_mode:
            self.text.configure(wrap="word" if self.wrap_var.get() else "none")
            self.hscroll.grid_remove()
        else:
            self.text.configure(wrap="none")
            self.hscroll.grid()

    def apply_status_bar(self):
        if self.status_var.get():
            self.status.pack(side="bottom", fill="x", before=self.editor_frame)
            self.update_status()
        else:
            self.status.pack_forget()

    # ------------------------------------------------------------------ theme

    def set_theme(self, name: str):
        self.settings["theme"] = name
        self.theme_var.set(name)
        self.theme = themes.get(name)
        self.apply_theme()

    def apply_theme(self):
        t = self.theme
        self._apply_ui_font()
        chrome = dict(background=t["chrome"], foreground=t["chrome_text"],
                      activebackground=t["menu_active"], activeforeground=t["chrome_text"])
        self.root.configure(background=t["chrome"])
        self.menu_bar.configure(background=t["chrome"])
        for button in self.menu_buttons:
            button.configure(**chrome)
        self.theme_box.configure(background=t["box_border"])
        self.theme_button.configure(text=THEME_BOX_FORMAT.format(label=t["label"]), **chrome)
        self.preview_button.configure(background=t["button_bg"], foreground=t["button_text"],
                                      activebackground=t["button_hover"], activeforeground=t["button_text"])
        for menu in self.menus:
            menu.configure(background=t["popup_bg"], foreground=t["popup_text"],
                           activebackground=t["popup_hover_bg"], activeforeground=t["popup_hover_text"],
                           disabledforeground=t["disabled"], selectcolor=t["accent"],
                           relief="flat", activeborderwidth=0)
        self._build_doc_bar()

        for widget in (self.text, self.preview):
            widget.configure(background=t["editor_bg"], insertbackground=t["text"],
                             selectbackground=t["selection"], selectforeground=t["text"],
                             inactiveselectbackground=t["selection"])
        self.text.configure(foreground=t["text"])
        self.text.tag_configure("current_line", background=t["current_line"])
        self.text.tag_lower("current_line")
        self.line_numbers.set_colors(t["gutter_bg"], t["gutter_line"], t["line_num"], t["line_num_current"])

        for child in self.status.winfo_children():
            child.configure(background=t["chrome"])
        self.status.configure(background=t["chrome"])
        self.status_line.configure(background=t["chrome_line"])
        for sep in self.status_seps:
            sep.configure(background=t["status_sep"])
        for label in self.status_labels.values():
            label.configure(foreground=t["status_text"], font=self.status_font)

        icon = str(themes.icon_path(t))
        try:
            self.root.iconbitmap(icon)
            self.root.iconbitmap(default=icon)  # dialogs too
        except tk.TclError:
            pass
        themes.apply_caption(self.root, t)
        if self.preview_mode:
            self.render_preview(keep_position=True)

    def _build_doc_bar(self):
        """Theme-specific document row: '이름 [수정됨]' header (paper) or a document tab with a dot (slate)."""
        t, bar = self.theme, self.doc_bar
        for child in bar.winfo_children():
            child.destroy()
        bar.configure(background=t["doc_bg"])
        if t["doc_style"] == "tab":
            bar.configure(padx=10, pady=0)
            holder = tk.Frame(bar, background=t["tab_bg"], padx=14, pady=4)
            holder.pack(side="left", pady=(6, 0))
            self.doc_dirty = tk.Canvas(holder, width=9, height=9, background=t["tab_bg"], highlightthickness=0)
            self.doc_dirty.create_oval(0, 0, 8, 8, fill=t["accent"], outline="")
        else:
            bar.configure(padx=18, pady=7)
            holder = tk.Frame(bar, background=t["doc_bg"])
            holder.pack(side="left")
            self.doc_dirty = tk.Label(holder, text="수정됨", font=self.chip_font, padx=8, pady=0,
                                      background=t["accent_soft"], foreground=t["accent"])
        self.doc_name = tk.Label(holder, font=self.title_font, background=holder.cget("background"),
                                 foreground=t["doc_text"], padx=0, pady=0)
        self.doc_name.pack(side="left")
        self.update_doc_bar()

    def update_doc_bar(self):
        if not hasattr(self, "doc_name"):
            return
        self.doc_name.configure(text=self.display_name())
        if self.dirty:
            self.doc_dirty.pack(side="left", padx=(10, 0))
        else:
            self.doc_dirty.pack_forget()

    # ------------------------------------------------------------------ file I/O

    def check_save(self) -> bool:
        """Ask to save unsaved changes. Returns False if the user cancelled."""
        if not self.dirty:
            return True
        answer = SaveChangesDialog(self.root, self.display_name()).run()
        if answer is None:
            return False
        if answer:
            return self.cmd_save()
        return True

    def set_document(self, text: str, path: Path | None, enc: int, line_ending: str):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.edit_reset()
        self.text.mark_set("insert", "1.0")
        self.text.see("1.0")
        self.path = path
        self.encoding = enc
        self.line_ending = line_ending
        self.dirty = False
        # Markdown documents open rendered; everything else opens as plain text.
        self.set_preview(self.is_markdown())

    def load_file(self, path: Path) -> bool:
        name = str(path)
        try:
            if path.stat().st_size >= encoding.MAX_FILE_SIZE:
                messagebox.showwarning(R.APP_NAME, R.MSG_FILE_TOO_LARGE.format(name=name), parent=self.root)
                return False
            data = path.read_bytes()
        except PermissionError:
            messagebox.showwarning(R.APP_NAME, R.MSG_ACCESS_DENIED.format(name=name), parent=self.root)
            return False
        except OSError:
            messagebox.showwarning(R.APP_NAME, R.MSG_CANNOT_OPEN.format(name=name), parent=self.root)
            return False

        doc = encoding.decode(data)
        self.set_document(doc.text, path.resolve(), doc.encoding, doc.line_ending)
        self._add_to_recent_docs(path)

        # .LOG files: append a time stamp at the end (case-sensitive check, like FUN_140010f48).
        if doc.text.startswith(".LOG"):
            self.text.mark_set("insert", "end-1c")
            self.insert_time_date(log_mode=True)
            self.text.see("end")
        return True

    @staticmethod
    def _add_to_recent_docs(path: Path):
        if sys.platform == "win32":
            try:
                ctypes.windll.shell32.SHAddToRecentDocs(3, ctypes.c_wchar_p(str(path.resolve())))  # SHARD_PATHW
            except OSError:
                pass

    def write_file(self, path: Path, enc: int) -> bool:
        text = self.get_text()
        if enc == encoding.ANSI and encoding.loses_data_as_ansi(text):
            if not messagebox.askokcancel(R.APP_NAME, R.MSG_ANSI_LOSS.format(name=path.name), parent=self.root):
                return False
        try:
            path.write_bytes(encoding.encode(text, enc, self.line_ending))
        except OSError:
            messagebox.showwarning(R.APP_NAME, R.MSG_CANNOT_CREATE.format(name=str(path)), parent=self.root)
            return False
        self.path = path.resolve()
        self.encoding = enc
        self.dirty = False
        self.update_preview_button()
        self.update_status()
        return True

    def open_from_command_line(self, arg: str):
        path = Path(arg)
        if path.exists():
            self.load_file(path)
            return
        if messagebox.askyesno(R.APP_NAME, R.MSG_NOT_FOUND_CREATE.format(name=str(path)), parent=self.root):
            try:
                path.touch()
            except OSError:
                messagebox.showwarning(R.APP_NAME, R.MSG_CANNOT_CREATE.format(name=str(path)), parent=self.root)
                return
            self.load_file(path)

    # ------------------------------------------------------------------ 파일 menu

    def cmd_new(self):
        if self.check_save():
            self.set_document("", None, self.settings["iDefaultEncoding"], "\r\n")

    def cmd_new_window(self):
        if getattr(sys, "frozen", False):  # PyInstaller exe: sys.executable is PyNotepad.exe itself
            subprocess.Popen([sys.executable])
            return
        exe = Path(sys.executable)
        pythonw = exe.with_name("pythonw.exe")
        interpreter = str(pythonw if pythonw.exists() else exe)
        subprocess.Popen([interpreter, "-m", "pynotepad"], cwd=str(Path(__file__).resolve().parent.parent))

    def cmd_open(self):
        if not self.check_save():
            return
        filename = filedialog.askopenfilename(
            parent=self.root, title="열기", filetypes=[R.FILTER_TEXT, R.FILTER_MARKDOWN, R.FILTER_ALL],
            initialdir=str(self.path.parent) if self.path else None)
        if filename:
            self.load_file(Path(filename))

    def cmd_save(self) -> bool:
        if self.path is None:
            return self.cmd_save_as()
        return self.write_file(self.path, self.encoding)

    def cmd_save_as(self) -> bool:
        filename = filedialog.asksaveasfilename(
            parent=self.root, title="다른 이름으로 저장", filetypes=[R.FILTER_TEXT, R.FILTER_MARKDOWN, R.FILTER_ALL],
            defaultextension=".txt",
            initialfile=self.path.name if self.path else "*.txt",
            initialdir=str(self.path.parent) if self.path else None)
        if not filename:
            return False
        enc = EncodingDialog(self.root, self.encoding).run()
        if enc is None:
            return False
        return self.write_file(Path(filename), enc)

    def cmd_print(self):
        """Print through the shell 'print' verb (the original draws pages with GDI itself)."""
        if sys.platform != "win32":
            return
        target = self.path
        if target is None or self.dirty:
            fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="pynotepad-")
            with os.fdopen(fd, "wb") as fh:
                fh.write(encoding.encode(self.get_text(), encoding.UTF8_BOM, "\r\n"))
            target = Path(tmp)
        try:
            os.startfile(str(target), "print")
        except OSError as exc:
            messagebox.showwarning(R.APP_NAME, str(exc), parent=self.root)

    def cmd_exit(self):
        if not self.check_save():
            return
        self.save_window_settings()
        self.settings.save()
        self.root.destroy()

    def save_window_settings(self):
        s = self.settings
        if self.root.state() == "normal":
            s["iWindowPosX"] = self.root.winfo_x()
            s["iWindowPosY"] = self.root.winfo_y()
            s["iWindowPosDX"] = self.root.winfo_width()
            s["iWindowPosDY"] = self.root.winfo_height()
        s["fWrap"] = self.wrap_var.get()
        s["StatusBar"] = self.status_var.get()

    # ------------------------------------------------------------------ 편집 menu

    def cmd_undo(self):
        self.ensure_source()
        try:
            self.text.edit_undo()
        except tk.TclError:
            pass
        self.update_status()

    def cmd_cut(self):
        self.ensure_source()
        if self.has_selection():
            self.text.event_generate("<<Cut>>")

    def cmd_copy(self):
        widget = self.active_widget()
        if widget.tag_ranges("sel"):
            widget.event_generate("<<Copy>>")

    def cmd_paste(self):
        self.ensure_source()
        self.text.event_generate("<<Paste>>")

    def cmd_delete(self):
        self.ensure_source()
        if self.has_selection():
            self.text.delete("sel.first", "sel.last")

    def cmd_search_google(self):
        widget = self.active_widget()
        query = widget.get("sel.first", "sel.last").strip() if widget.tag_ranges("sel") else ""
        if query:
            webbrowser.open(R.GOOGLE_SEARCH_URL.format(query=quote_plus(query)))

    def cmd_find(self):
        self.ensure_source()
        self._open_find_dialog(replace=False)

    def cmd_replace(self):
        self.ensure_source()
        self._open_find_dialog(replace=True)

    def _open_find_dialog(self, replace: bool):
        if self.find_dialog is not None:
            self.find_dialog.close()
        self.find_dialog = FindReplaceDialog(self, replace)

    def cmd_find_next(self):
        self.ensure_source()
        if self.settings["searchString"]:
            self.find_next(down=True)
        else:
            self.cmd_find()

    def cmd_find_prev(self):
        self.ensure_source()
        if self.settings["searchString"]:
            self.find_next(down=False)
        else:
            self.cmd_find()

    def _search_options(self) -> dict:
        s = self.settings
        return {"match_case": s["fMatchCase"], "whole_word": s["fWholeWord"]}

    def find_next(self, down: bool, parent: tk.Misc | None = None) -> bool:
        needle = self.settings["searchString"]
        if self.has_selection():
            start = self.offset_of("sel.last" if down else "sel.first")
        else:
            start = self.offset_of("insert")
        span = search.find(self.get_text(), needle, start, down=down,
                           wrap_around=self.settings["fWrapAround"], **self._search_options())
        if span is None:
            messagebox.showinfo(R.APP_NAME, R.MSG_TEXT_NOT_FOUND.format(text=needle), parent=parent or self.root)
            return False
        first, last = self.index_of(span[0]), self.index_of(span[1])
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", first, last)
        self.text.mark_set("insert", last if down else first)
        self.text.see(first)
        self.update_status()
        return True

    def replace_one(self, parent: tk.Misc | None = None):
        s = self.settings
        needle, replacement = s["searchString"], s["replaceString"]
        selected = self.selected_text()
        same = selected == needle if s["fMatchCase"] else selected.lower() == needle.lower()
        if needle and selected and same:
            self.text.edit_separator()
            self.text.delete("sel.first", "sel.last")
            self.text.insert("insert", replacement)
            self.text.edit_separator()
        self.find_next(down=True, parent=parent)

    def replace_all(self):
        s = self.settings
        spans = search.find_all(self.get_text(), s["searchString"], **self._search_options())
        if not spans:
            messagebox.showinfo(R.APP_NAME, R.MSG_TEXT_NOT_FOUND.format(text=s["searchString"]),
                                parent=self.find_dialog or self.root)
            return
        self.text.configure(autoseparators=False)
        self.text.edit_separator()
        for start, end in reversed(spans):
            self.text.delete(self.index_of(start), self.index_of(end))
            self.text.insert(self.index_of(start), s["replaceString"])
        self.text.edit_separator()
        self.text.configure(autoseparators=True)
        self.update_status()

    def cmd_goto(self):
        self.ensure_source()
        current = int(self.text.index("insert").split(".")[0])
        total = int(self.text.index("end-1c").split(".")[0])
        line = GoToDialog(self.root, current, total).run()
        if line:
            self.text.tag_remove("sel", "1.0", "end")
            self.text.mark_set("insert", f"{line}.0")
            self.text.see("insert")
            self.update_status()
        self.text.focus_set()

    def cmd_select_all(self):
        widget = self.active_widget()
        widget.tag_add("sel", "1.0", "end-1c")
        if widget is self.text:
            self.text.mark_set("insert", "end-1c")
        self.update_status()

    def cmd_time_date(self):
        self.ensure_source()
        self.insert_time_date(log_mode=False)

    def insert_time_date(self, log_mode: bool):
        stamp = windows_time_date()
        if log_mode:
            stamp = f"\n{stamp}\n"
        if self.has_selection():
            self.text.delete("sel.first", "sel.last")
        self.text.insert("insert", stamp)
        self.text.see("insert")
        self.update_status()

    # ------------------------------------------------------------------ 서식 / 보기

    def cmd_word_wrap(self):
        self.settings["fWrap"] = self.wrap_var.get()
        self.apply_wrap()

    def cmd_font(self):
        current = (self.settings["lfFaceName"], round(self.settings["iPointSize"] / 10))

        def on_pick(spec):
            actual = tkfont.Font(root=self.root, font=spec).actual()
            self.settings["lfFaceName"] = actual["family"]
            self.settings["iPointSize"] = abs(int(actual["size"])) * 10
            self.apply_font()

        self.root.tk.call("tk", "fontchooser", "configure", "-parent", self.root,
                          "-font", current, "-command", self.root.register(on_pick))
        self.root.tk.call("tk", "fontchooser", "show")

    def cmd_zoom_in(self):
        self.set_zoom(self.zoom + ZOOM_STEP)

    def cmd_zoom_out(self):
        self.set_zoom(self.zoom - ZOOM_STEP)

    def cmd_zoom_reset(self):
        self.set_zoom(100)

    def cmd_status_bar(self):
        self.settings["StatusBar"] = self.status_var.get()
        self.apply_status_bar()

    def cmd_line_numbers(self):
        self.settings["fLineNumbers"] = self.line_numbers_var.get()
        self.apply_line_numbers()

    def apply_line_numbers(self):
        if self.line_numbers_var.get() and not self.preview_mode:
            self.line_numbers.grid()
            self.line_numbers.schedule_redraw()
        else:
            self.line_numbers.grid_remove()

    # ------------------------------------------------------------------ Markdown preview

    def is_markdown(self) -> bool:
        return self.path is not None and self.path.suffix.lower() in MARKDOWN_SUFFIXES

    def active_widget(self) -> tk.Text:
        return self.preview if self.preview_mode else self.text

    def ensure_source(self):
        """Editing commands always act on the source, so leave the preview first."""
        if self.preview_mode:
            self.set_preview(False)

    def cmd_toggle_preview(self):
        self.set_preview(not self.preview_mode)

    def render_preview(self, keep_position: bool = False):
        position = self.preview.yview()[0] if keep_position else self.text.yview()[0]
        size = self.settings["iPointSize"] / 10 * self.zoom / 100
        MarkdownRenderer(self.preview, self.ui_family, self.settings["lfFaceName"], round(size),
                         on_link=webbrowser.open).render(self.get_text())
        self.preview.update_idletasks()
        self.preview.yview_moveto(position)

    def set_preview(self, on: bool):
        if on != self.preview_mode:
            self.preview_mode = on
            if on:
                self.render_preview()
                self.text.grid_remove()
                self.hscroll.grid_remove()
                self.preview.grid()
                self.vscroll.configure(command=self.preview.yview)
                self.preview.configure(yscrollcommand=self.vscroll.set)
                self.vscroll.set(*self.preview.yview())
                self.preview.focus_set()
            else:
                self.preview.grid_remove()
                self.text.grid()
                self.apply_wrap()
                self.vscroll.configure(command=self.text.yview)
                self.vscroll.set(*self.text.yview())
                self.text.focus_set()
            self.apply_line_numbers()
        self.preview_var.set(on)
        self.update_preview_button()
        self.update_status()

    def update_preview_button(self):
        if self.is_markdown() or self.preview_mode:
            self.preview_button.configure(text=SOURCE_LABEL if self.preview_mode else PREVIEW_LABEL)
            self.preview_button.pack(side="right", padx=6)
        else:
            self.preview_button.pack_forget()


def main(argv: list[str] | None = None):
    argv = sys.argv[1:] if argv is None else argv
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware, like the manifest
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    NotepadApp(root, argv[0] if argv else None)
    root.mainloop()
