"""Persistent settings. Key names match HKCU\\Software\\Microsoft\\Notepad, stored as JSON instead."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import encoding

DEFAULTS = {
    "lfFaceName": "D2Coding",
    "iPointSize": 120,  # tenths of a point, like the registry value
    "fWrap": False,
    "StatusBar": True,
    "fLineNumbers": True,
    "iWindowPosX": None,
    "iWindowPosY": None,
    "iWindowPosDX": 900,
    "iWindowPosDY": 600,
    "fReverse": False,
    "fWrapAround": False,
    "fMatchCase": False,
    "fWholeWord": False,
    "searchString": "",
    "replaceString": "",
    "iDefaultEncoding": encoding.UTF8,
    "fSaveWindowPositions": True,
    "theme": "paper",  # PyNotepad only: "paper" | "slate" (pynotepad/themes.py)
}


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "PyNotepad" / "settings.json"


class Settings(dict):
    def __init__(self, path: Path | None = None):
        super().__init__(DEFAULTS)
        self.path = path or settings_path()
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            self.update({k: v for k, v in data.items() if k in DEFAULTS})

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
