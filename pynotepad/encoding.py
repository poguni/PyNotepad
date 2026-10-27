"""Encoding detection and conversion, mirroring notepad.exe FUN_140010f48 / FUN_14000ca10."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass

# Internal encoding IDs used by notepad.exe (iDefaultEncoding / DAT_140035624).
ANSI = 1
UTF16_LE = 2
UTF16_BE = 3
UTF8_BOM = 4
UTF8 = 5

NAMES = {
    ANSI: "ANSI",
    UTF16_LE: "UTF-16 LE",
    UTF16_BE: "UTF-16 BE",
    UTF8: "UTF-8",
    UTF8_BOM: "UTF-8(BOM)",
}

# Order used by the save-as encoding combo box.
CHOICES = [ANSI, UTF16_LE, UTF16_BE, UTF8, UTF8_BOM]

BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"

# Files of 1 GiB or more are rejected (dwMaximumSizeLow < 0x40000000).
MAX_FILE_SIZE = 0x40000000

# IsTextUnicode result flag that only reflects statistical evidence.
IS_TEXT_UNICODE_STATISTICS = 0x0002

ANSI_CODEC = "mbcs" if sys.platform == "win32" else "cp1252"


@dataclass
class DecodedText:
    text: str
    encoding: int
    line_ending: str


def _is_text_unicode(data: bytes) -> bool:
    """Call advapi32!IsTextUnicode exactly like notepad does (flags = -1)."""
    if sys.platform != "win32" or len(data) < 2:
        return False
    flags = ctypes.c_int(-1)
    ok = ctypes.windll.advapi32.IsTextUnicode(data, len(data), ctypes.byref(flags))
    if not ok:
        return False
    # Short files that only pass the statistical test are treated as non-Unicode.
    if flags.value == IS_TEXT_UNICODE_STATISTICS and len(data) < 100:
        return False
    return True


def _is_valid_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def detect(data: bytes) -> int:
    """Return the notepad encoding ID for raw file bytes."""
    if data.startswith(BOM_UTF8):
        return UTF8_BOM
    if data.startswith(BOM_UTF16_LE):
        return UTF16_LE
    if data.startswith(BOM_UTF16_BE):
        return UTF16_BE
    if _is_text_unicode(data):
        return UTF16_LE
    if _is_valid_utf8(data):
        return UTF8
    return ANSI


def detect_line_ending(text: str) -> str:
    """Pick the first line ending found in the text; CRLF when there is none."""
    for i, ch in enumerate(text):
        if ch == "\r":
            return "\r\n" if text[i + 1:i + 2] == "\n" else "\r"
        if ch == "\n":
            return "\n"
    return "\r\n"


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode(data: bytes, encoding: int | None = None) -> DecodedText:
    """Decode file bytes. Pass `encoding` to force one instead of auto-detecting."""
    if encoding is None:
        encoding = detect(data)

    if encoding == UTF8_BOM:
        body = data[3:] if data.startswith(BOM_UTF8) else data
        text = body.decode("utf-8", errors="replace")
    elif encoding == UTF8:
        text = data.decode("utf-8", errors="replace")
    elif encoding == UTF16_LE:
        body = data[2:] if data.startswith(BOM_UTF16_LE) else data
        text = body.decode("utf-16-le", errors="replace")
    elif encoding == UTF16_BE:
        body = data[2:] if data.startswith(BOM_UTF16_BE) else data
        text = body.decode("utf-16-be", errors="replace")
    else:
        text = data.decode(ANSI_CODEC, errors="replace")

    # notepad replaces embedded NUL characters with spaces.
    text = text.replace("\0", " ")
    line_ending = detect_line_ending(text)
    return DecodedText(normalize_newlines(text), encoding, line_ending)


def loses_data_as_ansi(text: str) -> bool:
    """True when saving as ANSI would replace characters (notepad warning string 27)."""
    try:
        text.encode(ANSI_CODEC, errors="strict")
    except UnicodeEncodeError:
        return True
    return False


def encode(text: str, encoding: int, line_ending: str) -> bytes:
    """Encode editor text (\\n line endings) to file bytes."""
    text = text.replace("\n", line_ending)
    if encoding == UTF8_BOM:
        return BOM_UTF8 + text.encode("utf-8")
    if encoding == UTF8:
        return text.encode("utf-8")
    if encoding == UTF16_LE:
        return BOM_UTF16_LE + text.encode("utf-16-le")
    if encoding == UTF16_BE:
        return BOM_UTF16_BE + text.encode("utf-16-be")
    return text.encode(ANSI_CODEC, errors="replace")
