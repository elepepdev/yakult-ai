"""Grid overlay system for mouse click coordinate accuracy.

Overlays a labeled grid (e.g. A1-H6) on screenshots so vision-language
models can identify targets by grid cell rather than guessing pixel coordinates.
"""

from PIL import Image, ImageDraw, ImageFont


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
    line_color: tuple = (255, 50, 50),
    label_color: tuple = (255, 255, 255),
) -> Image.Image:
    """Overlay a labeled grid on an image.

    Draws grid lines (red) and labels every cell with letter-number
    (e.g. A1, B3, H6).  Column headers (A–H) run across the top in
    a dark band, row numbers (1–6) run down the left side.

    Font size is auto-scaled based on image dimensions — bigger
    images get bigger labels.
    """
    img = image.convert("RGBA")
    w, h = img.size

    cell_w = w / cols
    cell_h = h / rows

    # Auto-scale font — ~30 % of the smaller cell dimension [14, 52]
    font_size = max(14, min(int(min(cell_w, cell_h) * 0.30), 52))
    font = _try_load_font(font_size)
    small_font = _try_load_font(max(12, font_size - 6))

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # ── grid lines ──────────────────────────────────────────────
    lc = line_color + (160,)
    for col in range(cols + 1):
        x = int(col * cell_w)
        draw.line([(x, 0), (x, h)], fill=lc, width=line_width)
    for row in range(rows + 1):
        y = int(row * cell_h)
        draw.line([(0, y), (w, y)], fill=lc, width=line_width)

    # ── cell labels ─────────────────────────────────────────────
    for row in range(rows):
        for col in range(cols):
            label = f"{_col_label(col)}{row + 1}"
            cx = int(cell_w * col + cell_w / 2)
            cy = int(cell_h * row + cell_h / 2)
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.rectangle(
                [
                    cx - tw // 2 - 5,
                    cy - th // 2 - 3,
                    cx + tw // 2 + 5,
                    cy + th // 2 + 3,
                ],
                fill=(0, 0, 0, 150),
            )
            draw.text(
                (cx - tw // 2, cy - th // 2),
                label,
                fill=label_color + (255,),
                font=font,
            )

    # ── corner badge (bottom-right) ─────────────────────────────
    range_label = f"{_col_label(0)}1 – {_col_label(cols - 1)}{rows}"
    bb = draw.textbbox((0, 0), range_label, font=small_font)
    rw = bb[2] - bb[0] + 16
    rh = bb[3] - bb[1] + 10
    draw.rectangle(
        [w - rw - 4, h - rh - 4, w - 4, h - 4],
        fill=(180, 0, 0, 200),
    )
    draw.text(
        (w - rw + 4, h - rh + 1),
        range_label,
        fill=(255, 255, 255, 220),
        font=small_font,
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
    cell_x: float = 0.5,
    cell_y: float = 0.5,
) -> tuple[int, int] | None:
    """Convert a grid cell label to pixel coordinates in image-space.

    Args:
        cell: Cell label like 'A1', 'E5', 'H6'.
        image_width: Width of the image the grid was overlaid on.
        image_height: Height of the image.
        rows: Number of grid rows.
        cols: Number of grid columns.
        cell_x: Horizontal position within cell (0.0=left, 0.5=center, 1.0=right).
        cell_y: Vertical position within cell (0.0=top, 0.5=center, 1.0=bottom).

    Returns:
        (x, y) pixel coordinates in image-space, or None if invalid.
    """
    parsed = _parse_cell(cell)
    if parsed is None:
        return None
    col_idx, row_idx = parsed
    if col_idx >= cols or row_idx >= rows:
        return None
    cell_w = image_width / cols
    cell_h = image_height / rows
    cell_x = max(0.0, min(1.0, cell_x))
    cell_y = max(0.0, min(1.0, cell_y))
    cx = int(cell_w * col_idx + cell_w * cell_x)
    cy = int(cell_h * row_idx + cell_h * cell_y)
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
