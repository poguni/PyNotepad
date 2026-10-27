"""Find/replace logic on plain strings (offsets), independent of the UI."""

from __future__ import annotations

import re


def _pattern(needle: str, match_case: bool, whole_word: bool) -> re.Pattern:
    body = re.escape(needle)
    if whole_word:
        body = rf"(?<!\w){body}(?!\w)"
    return re.compile(body, 0 if match_case else re.IGNORECASE)


def find(text: str, needle: str, start: int, *, down: bool = True, match_case: bool = False,
         whole_word: bool = False, wrap_around: bool = False) -> tuple[int, int] | None:
    """Return (start, end) of the next match from offset `start`, or None.

    Searching down begins at `start`; searching up finds the last match ending at or before `start`.
    """
    if not needle:
        return None
    rx = _pattern(needle, match_case, whole_word)

    if down:
        m = rx.search(text, start)
        if m is None and wrap_around:
            m = rx.search(text, 0)
        return m.span() if m else None

    last = None
    for m in rx.finditer(text, 0, start):
        last = m
    if last is None and wrap_around:
        for m in rx.finditer(text, start):
            last = m
    return last.span() if last else None


def find_all(text: str, needle: str, *, match_case: bool = False,
             whole_word: bool = False) -> list[tuple[int, int]]:
    """Every non-overlapping match as (start, end), in document order."""
    if not needle:
        return []
    return [m.span() for m in _pattern(needle, match_case, whole_word).finditer(text)]


def replace_all(text: str, needle: str, replacement: str, *, match_case: bool = False,
                whole_word: bool = False) -> tuple[str, int]:
    """Replace every match; returns (new_text, count)."""
    if not needle:
        return text, 0
    rx = _pattern(needle, match_case, whole_word)
    return rx.subn(lambda _m: replacement, text)
