"""Launch the real PyNotepad window and drive it with commands read from stdin (one per line).

    python .claude/skills/run-notepad/driver.py [--out DIR] < script.txt

Runs the actual NotepadApp in this process with:
  - a throwaway settings file in --out (the user's %APPDATA%\\PyNotepad\\settings.json is never touched),
  - webbrowser.open captured (printed as "URL ..."), not opened,
  - messagebox.show* printed (as "MSG ...") instead of blocking on a modal box.
Screenshots are PNGs in --out. See SKILL.md for the command list.
"""
from __future__ import annotations

import argparse
import ctypes
import shlex
import sys
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path

UNIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(UNIT))

from PIL import ImageGrab  # noqa: E402

from pynotepad import app as app_mod  # noqa: E402
from pynotepad.settings import Settings  # noqa: E402

VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x2
WM_KEYDOWN, WM_KEYUP = 0x100, 0x101
# Ctrl+<name> keys that are not a single letter/digit (the app dispatches Ctrl combos by VK code).
NAMED_VK = {"Plus": 0xBB, "Minus": 0xBD, "Insert": 0x2D, "NumAdd": 0x6B, "NumSub": 0x6D, "Num0": 0x60}
CONTROL_MASK, SHIFT_MASK = 0x4, 0x1


def out(*parts):
    print(*parts, flush=True)


class Driver:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.urls: list[str] = []
        app_mod.webbrowser.open = lambda url, *a, **k: (self.urls.append(url), out("URL", url))
        for name in ("showinfo", "showwarning", "showerror"):
            setattr(app_mod.messagebox, name, lambda title, msg, _n=name, **k: out("MSG", _n, msg))

        # Same DPI mode as pynotepad.app.main(), so winfo_* coordinates match ImageGrab pixels.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        self.root = tk.Tk()
        self.app = app_mod.NotepadApp(self.root, settings=Settings(out_dir / "settings.json"))
        self.root.attributes("-topmost", True)  # keep the terminal from covering the screenshots
        self.root.update()
        self.root.focus_force()
        self.app.text.focus_force()
        self.root.update()
        out("READY", self.root.title())

    # ------------------------------------------------------------ helpers

    def _window_box(self, extra: tk.Menu | None = None, at: tuple[int, int] | None = None):
        r = self.root
        x0, y0 = r.winfo_rootx() - 8, r.winfo_rooty() - 40  # include the title bar
        x1, y1 = r.winfo_rootx() + r.winfo_width() + 8, r.winfo_rooty() + r.winfo_height() + 8
        if extra is not None and at is not None:  # grow the box so a posted menu is not cut off
            x1 = max(x1, at[0] + extra.winfo_reqwidth() + 8)
            y1 = max(y1, at[1] + extra.winfo_reqheight() + 8)
        return x0, y0, x1, y1

    def _grab(self, box, name: str) -> Path:
        path = self.out_dir / f"{name}.png"
        ImageGrab.grab(bbox=box, all_screens=True).save(path)
        return path

    def _post_and_shoot(self, menu: tk.Menu, x: int, y: int, name: str, popup: bool):
        """Posted Tk menus run a modal Win32 loop, so shoot and dismiss them from a helper thread."""
        box = self._window_box(menu, (x, y))  # Tk calls are main-thread only: compute before posting
        path = self.out_dir / f"{name}.png"

        def worker():
            time.sleep(0.8)
            ImageGrab.grab(bbox=box, all_screens=True).save(path)
            # Post Esc to the popup menu window itself: a synthesized keypress would go to whatever window
            # is in the foreground and leave the menu (and this run) hanging if focus moved elsewhere.
            user32 = ctypes.windll.user32
            menu_hwnd = user32.FindWindowW("#32768", None)
            if menu_hwnd:
                user32.PostMessageW(menu_hwnd, WM_KEYDOWN, VK_ESCAPE, 0)
                user32.PostMessageW(menu_hwnd, WM_KEYUP, VK_ESCAPE, 0)
            else:
                user32.keybd_event(VK_ESCAPE, 0, 0, 0)
                user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)

        threading.Thread(target=worker, daemon=True).start()
        if popup:
            menu.tk_popup(x, y)
        else:
            menu.post(x, y)
        self.root.update()
        out("SHOT", path)

    def _menubar(self, prefix: str) -> tuple[tk.Menubutton, tk.Menu]:
        # The theme drop-down ("테마: 종이 ▾") sits in its own frame at the right end of the bar.
        for button in [*self.app.menu_buttons, self.app.theme_button]:
            if button.cget("text").startswith(prefix):
                return button, self.root.nametowidget(button.cget("menu"))
        raise ValueError(f"no menu starting with {prefix!r}")

    def _menu(self, prefix: str) -> tk.Menu:
        return self.app.context_menu if prefix == "context" else self._menubar(prefix)[1]

    @staticmethod
    def _entries(menu: tk.Menu):
        end = menu.index("end")
        for i in range(0 if end is None else end + 1):
            if menu.type(i) in ("command", "checkbutton", "radiobutton", "cascade"):
                yield i, menu.entrycget(i, "label")

    def _find_entry(self, menu: tk.Menu, prefix: str) -> int:
        for i, label in self._entries(menu):
            if label.startswith(prefix):
                return i
        raise ValueError(f"no item starting with {prefix!r}")

    # ------------------------------------------------------------ commands

    def cmd_type(self, *words):
        self.app.text.insert("insert", " ".join(words).replace("\\n", "\n"))
        self.root.update()  # lets <<Modified>> fire so the title gets its '*'

    def cmd_selectall(self):
        self.app.cmd_select_all()

    def cmd_select(self, first, last):
        t = self.app.text
        t.tag_remove("sel", "1.0", "end")
        t.tag_add("sel", first, last)
        t.mark_set("insert", first)  # find/F3 start from the caret when nothing is selected

    def cmd_key(self, spec):
        """Ctrl+E, Ctrl+Shift+S, Ctrl+Plus, F3, Shift+F3, F5 ... sent to the editor as real key events."""
        *mods, key = spec.split("+")
        t = self.app.text
        if "Ctrl" in mods:
            state = CONTROL_MASK | (SHIFT_MASK if "Shift" in mods else 0)
            if key in NAMED_VK:
                t.event_generate("<Control-KeyPress>", keycode=NAMED_VK[key], state=state)
            else:
                t.event_generate("<Control-KeyPress>", keycode=ord(key.upper()), keysym=key.lower(), state=state)
        else:
            t.event_generate(f"<{'Shift-' if 'Shift' in mods else ''}{key}>")
        self.root.update()

    def cmd_menu(self, prefix, name=None):
        button, menu = self._menubar(prefix)
        self.app.update_edit_menu()
        x, y = button.winfo_rootx(), button.winfo_rooty() + button.winfo_height()
        self._post_and_shoot(menu, x, y, name or f"menu-{prefix}", popup=False)

    def cmd_context(self, x="120", y="40"):
        t = self.app.text
        self._post_and_shoot(self.app.context_menu, t.winfo_rootx() + int(x), t.winfo_rooty() + int(y),
                             "context", popup=True)

    def cmd_labels(self, prefix):
        menu = self._menu(prefix)
        self.app.update_edit_menu()
        for i, label in self._entries(menu):
            state = menu.entrycget(i, "state")
            accel = menu.entrycget(i, "accelerator") if menu.type(i) != "cascade" else ">"
            out("ITEM", f"{label}\t{accel}\t{state}")

    def cmd_click(self, prefix, item):
        menu = self._menu(prefix)
        self.app.update_edit_menu()
        menu.invoke(self._find_entry(menu, item))
        self.root.update()

    def cmd_open(self, path):
        self.app.load_file(Path(path))
        self.root.update()

    def cmd_ss(self, name="window"):
        self.root.update()
        time.sleep(0.2)
        out("SHOT", self._grab(self._window_box(), name))

    def cmd_state(self):
        a = self.app
        status = " | ".join(lbl.cget("text").strip() for lbl in a.status_labels.values())
        text = a.get_text()
        out("TITLE", self.root.title())
        out("STATUS", status)
        out("PREVIEW", a.preview_mode)
        out("SELECTION", repr(a.selected_text()))
        out("TEXT", repr(text if len(text) <= 200 else text[:200] + "..."))

    def cmd_eval(self, *words):
        exec(" ".join(words), {"app": self.app, "root": self.root, "tk": tk, "out": out})
        self.root.update()

    def cmd_sleep(self, seconds):
        end = time.time() + float(seconds)
        while time.time() < end:
            self.root.update()
            time.sleep(0.05)

    def cmd_quit(self):
        self.root.destroy()  # skip cmd_exit: no save prompt, no settings write
        out("BYE")

    def run(self, lines):
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            out(">", line)
            name, *args = line.split(None, 1)
            # `type` and `eval` take the rest of the line verbatim; others are shell-split.
            args = args if name in ("type", "eval") else shlex.split(args[0]) if args else []
            handler = getattr(self, f"cmd_{name}", None)
            if handler is None:
                out("ERR", f"unknown command {name!r}")
                continue
            try:
                handler(*args)
            except Exception as exc:  # keep going; the next agent wants every result
                out("ERR", f"{type(exc).__name__}: {exc}")
            if name == "quit":
                return
        self.cmd_quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "pynotepad-run")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    Driver(args.out.resolve()).run(sys.stdin)


if __name__ == "__main__":
    main()
