"""Shrink the bundled UI fonts to the characters the app needs (dev tool; needs fontTools).

    python tools/subset_fonts.py <folder with the original font files>

Keeps Hangul (all 11,172 syllables + jamo), Latin, punctuation and the symbols the UI and the
Markdown preview draw (arrows, box drawing, shapes, check boxes, ✎). Drops Hanja and other CJK
ideographs, which are most of each file. Text outside the subset still shows: Tk falls back to
another installed font for missing characters.

Originals (SIL OFL):
  https://github.com/google/fonts/tree/main/ofl/ibmplexsanskr  IBMPlexSansKR-{Regular,Medium,SemiBold}.ttf
  https://github.com/notofonts/noto-cjk/tree/main/Sans/SubsetOTF/KR  NotoSansKR-{Regular,Medium}.otf
"""
import sys
from pathlib import Path

from fontTools import subset

OUT = Path(__file__).resolve().parents[1] / "pynotepad" / "fonts"
FILES = ("IBMPlexSansKR-Regular.ttf", "IBMPlexSansKR-Medium.ttf", "IBMPlexSansKR-SemiBold.ttf",
         "NotoSansKR-Regular.otf", "NotoSansKR-Medium.otf")
RANGES = (
    (0x0020, 0x024F),  # Basic Latin, Latin-1, Latin Extended-A/B
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x2000, 0x206F),  # General Punctuation (• … ‘ ’ “ ”)
    (0x20A0, 0x20CF),  # Currency (₩ €)
    (0x2100, 0x214F),  # Letterlike (№ ™)
    (0x2190, 0x21FF),  # Arrows
    (0x2500, 0x257F),  # Box Drawing (Markdown tables)
    (0x25A0, 0x25FF),  # Geometric Shapes (▶ ▾ ▪ ◦ ●)
    (0x2600, 0x26FF),  # Miscellaneous Symbols (☐ ☑)
    (0x2700, 0x27BF),  # Dingbats (✎)
    (0x3000, 0x303F),  # CJK Symbols and Punctuation (「」 、 。)
    (0x3130, 0x318F),  # Hangul Compatibility Jamo (ㄱ ㅏ)
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xAC00, 0xD7A3),  # Hangul Syllables: all 11,172
    (0xD7B0, 0xD7FF),  # Hangul Jamo Extended-B
    (0xFF00, 0xFFEF),  # Halfwidth and Fullwidth Forms
)


def main(src: Path):
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]           # keep family/style names: Tk finds the font by them
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.hinting = True             # GDI rendering at small sizes relies on it
    unicodes = [c for lo, hi in RANGES for c in range(lo, hi + 1)]
    for name in FILES:
        font = subset.load_font(str(src / name), options)
        subsetter = subset.Subsetter(options)
        subsetter.populate(unicodes=unicodes)
        subsetter.subset(font)
        out = OUT / name
        subset.save_font(font, str(out), options)
        print(f"{name}: {(src / name).stat().st_size / 1e6:.1f} MB -> {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
