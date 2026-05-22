"""Generate icon.ico for the Windows installer."""
import math
from PIL import Image, ImageDraw


def _draw_star(draw: ImageDraw.ImageDraw, cx: float, cy: float,
               outer: float, inner: float, fill: tuple) -> None:
    pts = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(pts, fill=fill)


def _make_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(1, size // 10)
    radius = size // 4

    # Navy background with rounded corners
    draw.rounded_rectangle(
        [pad, pad, size - pad - 1, size - pad - 1],
        radius=radius,
        fill=(22, 33, 100, 255),
    )

    # Outer ring highlight
    draw.rounded_rectangle(
        [pad, pad, size - pad - 1, size - pad - 1],
        radius=radius,
        outline=(60, 90, 200, 180),
        width=max(1, size // 32),
    )

    # Gold star
    cx, cy = size / 2, size / 2
    _draw_star(draw, cx, cy, size * 0.36, size * 0.15, (255, 205, 0, 255))

    return img


def create_ico(output: str = "icon.ico") -> None:
    sizes = [16, 32, 48, 64, 128, 256]
    frames = [_make_frame(s) for s in sizes]
    frames[0].save(
        output,
        format="ICO",
        append_images=frames[1:],
        sizes=[(s, s) for s in sizes],
    )
    print(f"icon.ico 已生成 → {output}")


if __name__ == "__main__":
    create_ico()
