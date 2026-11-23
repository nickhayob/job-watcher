"""Draw the app icons (a magnifying glass over three bars).

Run once:  uv run python tools/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

TEAL = (15, 107, 92)
CREAM = (246, 244, 239)
AMBER = (232, 160, 90)
OUT = Path(__file__).resolve().parent.parent / "icons"


def draw(size, safe):
    """safe < 1 shrinks the drawing so a maskable icon survives cropping."""
    scale = 4  # draw big, then shrink for smooth edges
    s = size * scale
    img = Image.new("RGB", (s, s), TEAL)
    d = ImageDraw.Draw(img)
    u = s * safe / 100  # one percent of the safe drawing area
    ox = oy = s * (1 - safe) / 2

    def p(x, y):
        return ox + x * u, oy + y * u

    # lens
    d.ellipse([*p(14, 14), *p(66, 66)], outline=CREAM, width=int(7 * u))
    # handle
    d.line([*p(58, 58), *p(86, 86)], fill=CREAM, width=int(9 * u))
    # three bars inside the lens
    for x0, top in ((28, 44), (40, 33), (52, 24)):
        d.rectangle([*p(x0, top), *p(x0 + 7, 56)], fill=AMBER)
    return img.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(exist_ok=True)
    draw(192, 0.92).save(OUT / "icon-192.png")
    draw(512, 0.92).save(OUT / "icon-512.png")
    draw(512, 0.66).save(OUT / "icon-maskable-512.png")
    print("wrote icons to", OUT)


if __name__ == "__main__":
    main()
