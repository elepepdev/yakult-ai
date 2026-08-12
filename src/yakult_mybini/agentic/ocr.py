import json
import threading
from typing import Optional, Tuple

_engine = None
_engine_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from rapidocr_onnxruntime import RapidOCR
                _engine = RapidOCR()
    return _engine


def _to_pil(img, detail: bool, source: str):
    result, _ = _get_engine()(img)
    if not result:
        return {"success": True, "source": source, "text": ""}
    if detail:
        items = []
        for box, text, conf in result:
            items.append({"text": text, "confidence": round(float(conf), 3)})
        return {"success": True, "source": source, "text": "\n".join(i["text"] for i in items), "items": items}
    return {"success": True, "source": source, "text": "\n".join(t for _, t, _ in result)}


def ocr_image(path: str, detail: bool = False) -> str:
    """OCR text from an image file. Returns extracted text, optionally per-line confidence."""
    try:
        from PIL import Image
        return json.dumps(_to_pil(Image.open(path), detail, f"image:{path}"))
    except FileNotFoundError:
        return json.dumps({"success": False, "error": f"File not found: {path}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def ocr_screen(region: Optional[Tuple[int, int, int, int]] = None, detail: bool = False) -> str:
    """Capture the screen (or a region) and OCR the text on it."""
    try:
        import mss
        with mss.mss() as sct:
            if region is None:
                mon = sct.monitors[1]
                box = {"left": mon["left"], "top": mon["top"],
                       "width": mon["width"], "height": mon["height"]}
            else:
                left, top, width, height = region
                box = {"left": left, "top": top, "width": width, "height": height}
            shot = sct.grab(box)
        from PIL import Image
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return json.dumps(_to_pil(img, detail, "screen"))
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def ocr_image_from_pil(img) -> str:
    """OCR text from a PIL image in memory."""
    return json.dumps(_to_pil(img, False, "image"))


def demo():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (800, 200), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 70), "OCR works: 12345 ABC", fill="black")
    img.save("/tmp/ocr_demo.png")
    out = ocr_image("/tmp/ocr_demo.png")
    assert "OCR works" in out, out
    print(out)


if __name__ == "__main__":
    demo()
