"""Global state for grid overlay mode on screen-sharing images.

When enabled, screen-sharing images sent to the LLM will have a labeled
grid overlaid so the LLM can use grid_cell for click precision.
"""

from .grid_overlay import add_grid, parse_grid_spec

_grid_enabled: bool = False
_grid_rows: int = 6
_grid_cols: int = 8


def is_grid_enabled() -> bool:
    return _grid_enabled


def get_grid_spec() -> str:
    return f"{_grid_cols}x{_grid_rows}"


def get_grid_rows() -> int:
    return _grid_rows


def get_grid_cols() -> int:
    return _grid_cols


def enable(grid_spec: str = "8x6") -> str:
    """Enable grid overlay on screen-sharing images.

    Returns a description string for the LLM.
    """
    global _grid_enabled, _grid_rows, _grid_cols
    parsed = parse_grid_spec(grid_spec)
    if parsed is None:
        return f"Invalid grid spec '{grid_spec}'. Use format like '8x6' or '10x10'."
    _grid_rows, _grid_cols = parsed
    _grid_enabled = True
    return (
        f"Grid overlay enabled: {_grid_cols}x{_grid_rows} "
        f"(cells {_col_label(0)}1 – {_col_label(_grid_cols - 1)}{_grid_rows}). "
        "Now overlay a grid on every screen-shared image sent to you. "
        "Use grid_cell='cellname' in click/type_text/x11_click instead of raw x,y."
    )


def disable() -> str:
    """Disable grid overlay on screen-sharing images."""
    global _grid_enabled
    _grid_enabled = False
    return "Grid overlay disabled. Screen images will be sent without grid."


def _col_label(n: int) -> str:
    label = ""
    n += 1
    while n > 0:
        n -= 1
        label = chr(65 + (n % 26)) + label
        n //= 26
    return label


def apply_grid_to_image(base64_data_uri: str) -> str:
    """Apply grid overlay to a base64 data URI image.

    Returns the modified data URI with grid overlaid, or the original if grid is disabled.
    """
    if not _grid_enabled:
        return base64_data_uri
    try:
        import base64
        from PIL import Image
        import io

        prefix, b64 = base64_data_uri.split("base64,", 1)
        pil_img = Image.open(io.BytesIO(base64.b64decode(b64)))
        grid_img = add_grid(pil_img, rows=_grid_rows, cols=_grid_cols)
        buf = io.BytesIO()
        grid_img.save(buf, format="PNG")
        return prefix + "base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return base64_data_uri
