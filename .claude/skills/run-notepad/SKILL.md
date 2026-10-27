---
name: run-notepad
description: Run, launch, drive and screenshot PyNotepad (the Python/Tk re-creation of Windows Notepad). Use when asked to start the app, check a menu/shortcut/feature in the real window, take a screenshot of its UI, open a file in it, or run its tests.
---

PyNotepad is a Tkinter desktop app (Windows only in practice: it calls Win32 via ctypes).
An agent drives the **real window** with `.claude/skills/run-notepad/driver.py`, which reads
one command per line from stdin, prints results, and saves PNG screenshots.

All paths are relative to the project root (`C:\WORK-Claude\Notepad`). Commands are for the
Git Bash tool.

## Prerequisites

- Windows 11, Python 3.10+ (verified with 3.14.6). The app itself uses only the standard library.
- The driver needs Pillow for screenshots (`PIL.ImageGrab`). Check with:

```bash
python -c "import PIL; print(PIL.__version__)"
```

No build step.

## Run (agent path)

Pipe a script into the driver. Always wrap it in `timeout`: if anything modal stays open
(a dialog, a menu), the process blocks forever.

```bash
timeout 60 python .claude/skills/run-notepad/driver.py --out "$TMPDIR/shots" <<'EOF'
type 파이썬 tkinter 메모장\n둘째 줄
selectall
key Ctrl+E
labels 편집
menu 편집
context
click 편집 Google
state
EOF
```

Output is line-oriented: `READY <title>`, `> <command>` echo, then `URL ...` (captured
browser opens), `MSG ...` (message boxes), `ITEM label<TAB>accel<TAB>state`, `SHOT <png path>`,
`TITLE/STATUS/PREVIEW/SELECTION/TEXT` (from `state`), `ERR ...` (a command failed; the script
keeps going), `BYE`. Screenshots go to `--out` (default `%TEMP%\pynotepad-run`).
**Open the PNGs and look at them.**

| command | what it does |
|---|---|
| `type <text>` | insert at the caret; `\n` = newline (rest of line is literal) |
| `selectall` | 편집 > 모두 선택 |
| `select <first> <last>` | select a Tk index range (e.g. `1.0 1.5`) and put the caret at `first` |
| `key <spec>` | key event to the editor: `Ctrl+E`, `Ctrl+Shift+S`, `Ctrl+Plus`/`Minus`/`Insert`/`0`, `F3`, `Shift+F3`, `F5` |
| `labels <menu>` | print every item of a menu bar menu (`파일`/`편집`/`서식`/`보기`), the theme drop-down (`테마`) or `context`, with enabled state |
| `menu <menu> [name]` | open that menu bar menu (or `테마`), screenshot it (`<name>.png`, default `menu-<menu>.png`), close it |
| `context [x y]` | open the right-click menu in the editor, screenshot (`context.png`), close it |
| `click <menu> <item-prefix>` | invoke a menu item, e.g. `click 보기 줄 번호`, `click 편집 Google`, `click 테마 슬레이트` |
| `open <path>` | load a file (encoding detection, `.md` opens in preview) |
| `ss [name]` | screenshot the window to `<name>.png` |
| `state` | print title, status bar, preview mode, selection, text |
| `eval <python>` | run Python with `app` (NotepadApp), `root`, `tk`, `out` in scope |
| `sleep <sec>` | pump the event loop for a while |
| `quit` | close without the save prompt (also done automatically at end of input) |

Example — set the search string and press F3 (the find dialog is modal, so skip it):

```bash
timeout 60 python .claude/skills/run-notepad/driver.py --out "$TMPDIR/shots" <<'EOF'
type 파이썬 tkinter 메모장
eval app.settings["searchString"] = "메모장"
select 1.0 1.0
key F3
key Ctrl+Plus
key F5
state
EOF
```

## Run (human path)

```bash
pythonw notepad.pyw            # window opens, no console; close it to exit
python -m pynotepad some.txt   # same, opens a file
```

Closing normally writes `%APPDATA%\PyNotepad\settings.json` (the user's real settings).

## Test

```bash
python -m unittest discover -s tests -t .
```

Expected: `Ran 63 tests ... OK` (a few seconds; the smoke tests open real Tk windows).

## Gotchas

- **The driver never touches the user's settings or browser.** It uses `--out/settings.json`,
  replaces `webbrowser.open` with a printer (`URL ...`) and `messagebox.showinfo/warning/error`
  with a printer (`MSG ...`). It does **not** stub `askyesno`/`askokcancel` or the app's own
  dialogs (찾기/바꾸기, 이동, 저장 확인, 인코딩, 파일 열기): invoking those blocks until `timeout`
  kills the run. Set state through `eval` instead (e.g. `app.settings["searchString"]`).
- **Posted menus are modal on Windows.** `menu.post()` / `tk_popup()` run a Win32 menu loop
  and do not return until the menu closes. The driver screenshots from a helper thread, then
  posts Esc straight to the popup menu window (class `#32768`). A synthesized keypress
  (`keybd_event`) goes to whatever window is in the foreground; when focus had moved elsewhere
  the menu stayed open and the run hung until `timeout`. If the helper thread dies, it hangs too.
- **The theme drop-down is not a direct child of the menu bar.** It is a Menubutton inside a
  1-px border frame (`app.theme_button` in `app.theme_box`); the driver looks it up next to
  `app.menu_buttons`. Switching themes: `click 테마 슬레이트` / `click 테마 종이`.
- **Tk is main-thread only.** Calling `root.winfo_*` from the helper thread raises
  `RuntimeError: main thread is not in main loop`; compute everything Tk-related before
  starting a thread.
- **Screenshots need the app's DPI mode.** The driver calls `SetProcessDpiAwareness(2)` like
  `pynotepad.app.main()`; without it `winfo_rootx/rooty` and `ImageGrab` pixels disagree on
  scaled displays. Menu screenshots grow the box by the menu's `winfo_reqheight()` — a window-
  sized box cuts off the bottom of 편집.
- **Ctrl shortcuts are dispatched by virtual-key code**, not keysym (`_on_control_key`), so
  `event_generate("<Control-KeyPress>", keycode=<VK>, state=0x4)` is what triggers them;
  `Ctrl+Plus` is VK `0xBB`, not `=`.
- **Find starts at the caret.** With no selection, F3 searches from `insert`; after `selectall`
  the caret is at the end and (with 주위에 배치 off by default) nothing is found. That is why
  `select` also moves the caret.
- **The window is topmost and takes keyboard focus.** Keys you type elsewhere while a run is
  in progress go into the editor. Once, an F3-selected word was replaced by a space and the
  replay never reproduced it — don't type during a run, and rerun before blaming the app.
- **Title `*` is updated on `<<Modified>>`**, which fires from the event loop; the driver's
  `type` pumps it so `state` shows the dirty marker right away.

## Troubleshooting

- **Run hangs until `timeout` kills it (exit 124)**: a modal dialog or menu is open. Remove
  the command that opens a dialog, or use `eval` to set the state it would have set.
- **`ERR TypeError: ord() expected a character`**: an unknown named key in `key Ctrl+<name>`.
  Add it to `NAMED_VK` in the driver.
- **Korean text arrives garbled**: the driver reconfigures stdin to UTF-8; feed it a UTF-8
  heredoc (Git Bash default), not a cp949 file.
