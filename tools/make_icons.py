"""Generate the add-on icon and logo.

Run with `uv run python tools/make_icons.py` after changing the design. The output
is committed so the add-on directory needs no build step.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parent.parent / "private_source_manager"

BLUE = (3, 155, 229, 255)
DEEP = (2, 119, 189, 255)
WHITE = (255, 255, 255, 255)

# Everything is drawn at 8x and downsampled, which is cheaper than writing an
# antialiasing rasteriser by hand.
SCALE = 8


def _padlock(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top

    body_top = top + int(height * 0.42)
    body = (left, body_top, right, bottom)
    draw.rounded_rectangle(body, radius=int(width * 0.16), fill=WHITE)

    shackle_width = int(width * 0.15)
    inset = int(width * 0.21)
    arc_bottom = body_top + int(height * 0.2)
    draw.arc(
        (left + inset, top, right - inset, arc_bottom),
        start=180,
        end=360,
        fill=WHITE,
        width=shackle_width,
    )

    # Pillow grows arc thickness inwards, so each leg is centred half a stroke
    # inside the arc bounding box rather than on its edge.
    half = shackle_width // 2
    knee = (top + arc_bottom) // 2
    for x in (left + inset + half, right - inset - half):
        draw.line([(x, knee), (x, body_top)], fill=WHITE, width=shackle_width)

    # Keyhole, drawn as a branch node so the mark reads as "private git" rather
    # than a generic padlock.
    centre_x = (left + right) // 2
    node = int(width * 0.075)
    upper_y = body_top + int(height * 0.16)
    lower_y = bottom - int(height * 0.16)
    draw.line([(centre_x, upper_y), (centre_x, lower_y)], fill=DEEP, width=max(2, node // 2))
    for y in (upper_y, lower_y):
        draw.ellipse((centre_x - node, y - node, centre_x + node, y + node), fill=DEEP)


def make_icon(size: int = 128) -> Image.Image:
    canvas = Image.new("RGBA", (size * SCALE, size * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    edge = size * SCALE

    draw.rounded_rectangle((0, 0, edge - 1, edge - 1), radius=int(edge * 0.22), fill=BLUE)
    margin = int(edge * 0.26)
    _padlock(draw, (margin, int(edge * 0.2), edge - margin, edge - int(edge * 0.22)))

    return canvas.resize((size, size), Image.LANCZOS)


def make_logo(width: int = 250, height: int = 100) -> Image.Image:
    canvas = Image.new("RGBA", (width * SCALE, height * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    mark = height * SCALE
    draw.rounded_rectangle(
        ((width * SCALE - mark) // 2, 0, (width * SCALE + mark) // 2, mark - 1),
        radius=int(mark * 0.22),
        fill=BLUE,
    )
    inset = int(mark * 0.26)
    left = (width * SCALE - mark) // 2
    _padlock(draw, (left + inset, int(mark * 0.2), left + mark - inset, mark - int(mark * 0.22)))

    return canvas.resize((width, height), Image.LANCZOS)


def main() -> None:
    make_icon().save(OUTPUT / "icon.png")
    make_logo().save(OUTPUT / "logo.png")
    print(f"wrote {OUTPUT / 'icon.png'} and {OUTPUT / 'logo.png'}")


if __name__ == "__main__":
    main()
