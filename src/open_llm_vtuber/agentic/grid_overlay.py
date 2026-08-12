"""Grid overlay system for mouse click coordinate accuracy.

Overlays a labeled grid (e.g. A1-H6) on screenshots so vision-language
models can identify targets by grid cell rather than guessing pixel coordinates.
"""

from PIL import Image, ImageDraw, ImageFont
from typing import Optional


def _col_label(n: int) -> str:
    """Convert 0-indexed column number to letter(s). A=0, B=1, ..., Z=25, AA=26."""
    label = ""
    n += 1
    while n > 0:
        n -= 1
        label = chr(65 + (n % 26)) + label
        n //= 26
    return label


def _parse_cell(cell: str) -> tuple[int, int] | None:
    """Parse a cell label like 'A1', 'B3', 'AA10' into (col_idx, row_idx).

    Returns None if the format is invalid.
    """
    cell = cell.strip().upper()
    if not cell:
        return None
    letters = ""
    numbers = ""
    for ch in cell:
        if ch.isalpha():
            letters += ch
        elif ch.isdigit():
            numbers += ch
        else:
            return None
    if not letters or not numbers:
        return None
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    col -= 1
    row = int(numbers) - 1
    if col < 0 or row < 0:
        return None
    return (col, row)


def add_grid(
    image: Image.Image,
    rows: int = 6,
    cols: int = 8,
    line_width: int = 2,
    line_color: tuple = (255, 0, 0),
    label_color: tuple = (255, 255, 255),
    font_size: int = 18,
) -> Image.Image:
    """Overlay a labeled grid on an image.

    Draws thin red grid lines and labels each cell with a letter-number
    combination (e.g. A1, B3, H6). A small legend in the bottom-right
    corner shows the cell range.

    Returns a new RGBA image with the grid overlaid.
    """
    img = image.convert("RGBA")
    w, h = img.size

    cell_w = w / cols
    cell_h = h / rows

    font = _try_load_font(font_size)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for col in range(cols + 1):
        x = int(col * cell_w)
        draw.line([(x, 0), (x, h)], fill=line_color + (180,), width=line_width)

    for row in range(rows + 1):
        y = int(row * cell_h)
        draw.line([(0, y), (w, y)], fill=line_color + (180,), width=line_width)

    for row in range(rows):
        for col in range(cols):
            label = f"{_col_label(col)}{row + 1}"
            cx = int(cell_w * col + cell_w / 2)
            cy = int(cell_h * row + cell_h / 2)
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.rectangle(
                [cx - tw // 2 - 3, cy - th // 2 - 2, cx + tw // 2 + 3, cy + th // 2 + 2],
                fill=(0, 0, 0, 160),
            )
            draw.text(
                (cx - tw // 2, cy - th // 2),
                label,
                fill=label_color + (255,),
                font=font,
            )

    img = Image.alpha_composite(img, overlay)
    return img


def _try_load_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, font_size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def cell_to_pixel(
    cell: str,
    image_width: int,
    image_height: int,
    rows: int = 6,
    cols: int = 8,
) -> tuple[int, int] | None:
    """Convert a grid cell label to center pixel coordinates in image-space.

    Args:
        cell: Cell label like 'A1', 'E5', 'H6'.
        image_width: Width of the image the grid was overlaid on.
        image_height: Height of the image.
        rows: Number of grid rows.
        cols: Number of grid columns.

    Returns:
        (x, y) center pixel coordinates in image-space, or None if invalid.
    """
    parsed = _parse_cell(cell)
    if parsed is None:
        return None
    col_idx, row_idx = parsed
    if col_idx >= cols or row_idx >= rows:
        return None
    cell_w = image_width / cols
    cell_h = image_height / rows
    cx = int(cell_w * col_idx + cell_w / 2)
    cy = int(cell_h * row_idx + cell_h / 2)
    return (cx, cy)


def parse_grid_spec(spec: str) -> tuple[int, int] | None:
    """Parse a grid specification string like '8x6' or '10x10'.

    Returns (rows, cols) or None if invalid.
    """
    try:
        parts = spec.lower().split("x")
        if len(parts) != 2:
            return None
        cols = int(parts[0])
        rows = int(parts[1])
        if cols < 1 or rows < 1 or cols > 26 or rows > 99:
            return None
        return (rows, cols)
    except (ValueError, IndexError):
        return None
