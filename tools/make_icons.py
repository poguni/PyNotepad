"""Build pynotepad/assets/icon-<theme>.ico from the shapes in design/icons/*.svg (dev tool; needs Pillow).

    python tools/make_icons.py

Each size is drawn separately at 8x and scaled down, so small sizes get their own simplified
shapes (fewer, thicker text lines) instead of a blurry copy of the 256 px image.
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "pynotepad" / "assets"
SIZES = (16, 24, 32, 48, 64, 256)
SCALE = 8


def paper(d: ImageDraw.ImageDraw, size: int, u):
    d.rounded_rectangle(u(4, 4, 60, 60), radius=u(14), fill="#0F6E6E")
    d.polygon(u(19, 12, 38, 12, 47, 21, 47, 52, 17, 52, 17, 12), fill="#FFFEFB")
    d.polygon(u(38, 12, 38, 21, 47, 21), fill="#BFDCD9")
    if size <= 16:
        lines = ((30, 20, 5), (40, 12, 5))
    elif size <= 24:
        lines = ((29, 20, 4), (37, 20, 4), (45, 12, 4))
    else:
        lines = ((29, 20, 3.5), (36, 20, 3.5), (43, 12, 3.5))
    for y, w, h in lines:
        d.rounded_rectangle(u(22, y, 22 + w, y + h), radius=u(h / 2), fill="#0F6E6E")


def slate(d: ImageDraw.ImageDraw, size: int, u):
    d.rounded_rectangle(u(4, 4, 60, 60), radius=u(14), fill="#2F6FDB")
    d.rounded_rectangle(u(16, 16, 48, 54), radius=u(4), fill="#FFFFFF")
    d.rounded_rectangle(u(16, 12, 48, 21 if size > 24 else 22), radius=u(3), fill="#163B7A")
    if size <= 16:
        lines, color = ((30, 22, 5), (40, 14, 5)), "#7E9FDB"
    elif size <= 24:
        lines, color = ((30, 22, 4), (39, 14, 4)), "#7E9FDB"
    else:
        lines, color = ((29, 22, 3.5), (36, 22, 3.5), (43, 14, 3.5)), "#9DB7E6"
    for y, w, h in lines:
        d.rounded_rectangle(u(21, y, 21 + w, y + h), radius=u(h / 2), fill=color)


def render(draw_fn, size: int) -> Image.Image:
    big = size * SCALE
    k = big / 64

    def u(*v):
        return v[0] * k if len(v) == 1 else [x * k for x in v]

    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(img), size, u)
    return img.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("paper", paper), ("slate", slate)):
        images = [render(fn, s) for s in SIZES]
        path = OUT / f"icon-{name}.ico"
        images[-1].save(path, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
        images[-1].save(OUT / f"icon-{name}.png")
        print(path)


if __name__ == "__main__":
    main()
