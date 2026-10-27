"""UI themes (design/DESIGN.md): colors, UI fonts and icon for 종이 (paper) and 슬레이트 (slate)."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
FONT_DIR = PACKAGE_DIR / "fonts"
ASSET_DIR = PACKAGE_DIR / "assets"
FALLBACK_FAMILY = "맑은 고딕"
FR_PRIVATE = 0x10

DEFAULT_THEME = "paper"

THEMES: dict[str, dict] = {
    "paper": {
        "label": "종이",
        "icon": "icon-paper.ico",
        "doc_style": "header",  # document name row with a '수정됨' chip
        "font": "IBM Plex Sans KR",
        "font_medium": "IBM Plex Sans KR Medium",
        "font_title": "IBM Plex Sans KR SemiBold",
        "title_size": 13,
        "dark_caption": False,
        "caption": "#F3F0EA",
        "caption_text": "#4A463E",
        "chrome": "#F3F0EA",
        "chrome_text": "#2B2924",
        "chrome_line": "#E4DFD5",
        "menu_active": "#E4DFD4",
        "doc_bg": "#FBFAF7",
        "tab_bg": "#FBFAF7",
        "doc_text": "#23211D",
        "editor_bg": "#FFFEFB",
        "text": "#23211D",
        "gutter_bg": "#F7F5F0",
        "gutter_line": "#ECE8DF",
        "line_num": "#ADA697",
        "line_num_current": "#23211D",
        "current_line": "#F4F1EA",
        "selection": "#CFE6E3",
        "accent": "#0F6E6E",
        "accent_soft": "#E3EFEE",
        "popup_bg": "#FFFFFF",
        "popup_text": "#23211D",
        "popup_hover_bg": "#E3EFEE",
        "popup_hover_text": "#0F6E6E",
        "disabled": "#B9B2A4",
        "status_text": "#5B564C",
        "status_sep": "#DDD7CB",
        "button_bg": "#E3EFEE",
        "button_text": "#0F6E6E",
        "button_hover": "#D3E7E5",
        "box_border": "#D6D0C4",
    },
    "slate": {
        "label": "슬레이트",
        "icon": "icon-slate.ico",
        "doc_style": "tab",  # document tab with a dot when modified
        "font": "Noto Sans KR",
        "font_medium": "Noto Sans KR Medium",
        "font_title": "Noto Sans KR Medium",
        "title_size": 11,
        "dark_caption": True,
        "caption": "#1E232B",
        "caption_text": "#C9CFD9",
        "chrome": "#1E232B",
        "chrome_text": "#E9ECF1",
        "chrome_line": "#1E232B",
        "menu_active": "#3A414D",
        "doc_bg": "#2A303A",
        "tab_bg": "#FFFFFF",
        "doc_text": "#1B2029",
        "editor_bg": "#FFFFFF",
        "text": "#1B2029",
        "gutter_bg": "#F4F6F9",
        "gutter_line": "#E6EAF0",
        "line_num": "#9AA3B2",
        "line_num_current": "#1B2029",
        "current_line": "#F1F5FC",
        "selection": "#CFE0FA",
        "accent": "#2F6FDB",
        "accent_soft": "#EAF1FD",
        "popup_bg": "#FFFFFF",
        "popup_text": "#1B2029",
        "popup_hover_bg": "#1F5BC4",
        "popup_hover_text": "#FFFFFF",
        "disabled": "#A9B1BE",
        "status_text": "#C3C9D3",
        "status_sep": "#3A414D",
        "button_bg": "#3A414D",
        "button_text": "#E9ECF1",
        "button_hover": "#4A5260",
        "box_border": "#4A5260",
    },
}


def get(name: str | None) -> dict:
    return THEMES.get(name or "", THEMES[DEFAULT_THEME])


def icon_path(theme: dict) -> Path:
    return ASSET_DIR / theme["icon"]


_fonts_registered = False


def register_fonts() -> None:
    """Make the bundled OFL fonts available to this process only (no system install)."""
    global _fonts_registered
    if _fonts_registered or sys.platform != "win32":
        return
    _fonts_registered = True
    for path in sorted(FONT_DIR.glob("*.[ot]tf")):
        ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, None)


def resolve_family(family: str, installed: set[str]) -> str:
    return family if family in installed else FALLBACK_FAMILY


def colorref(hex_color: str) -> int:
    """'#RRGGBB' -> Win32 COLORREF (0x00BBGGRR)."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return r | (g << 8) | (b << 16)


def apply_caption(root, theme: dict) -> None:
    """Color the native title bar (Windows 11). Its font cannot be changed, so the document row repeats the name."""
    if sys.platform != "win32":
        return
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    if not hwnd:  # the frame window exists only once the toplevel has been mapped
        return
    dwm = ctypes.windll.dwmapi
    for attribute, value in (
        (20, int(theme["dark_caption"])),       # DWMWA_USE_IMMERSIVE_DARK_MODE: light/dark caption buttons
        (35, colorref(theme["caption"])),       # DWMWA_CAPTION_COLOR
        (36, colorref(theme["caption_text"])),  # DWMWA_TEXT_COLOR
    ):
        data = ctypes.c_int(value)
        dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))
