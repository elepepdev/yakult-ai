import io
import os
from typing import Dict, Tuple

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".xml", ".csv",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".sh", ".bash", ".zsh", ".fish",
    ".html", ".css", ".scss", ".sql", ".toml", ".ini", ".cfg", ".conf",
    ".log", ".rst", ".tex", ".dockerfile", ".gitignore", ".env", ".ipynb",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
OCR_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

MAX_TEXT_TOKENS = 2000
MAX_TEXT_CHARS = MAX_TEXT_TOKENS * 4  # ~4 chars/token for latin text
def _kind_for(filename: str, mime_type: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in IMAGE_EXTENSIONS or (mime_type or "").startswith("image/"):
        return "image"
    if ext in TEXT_EXTENSIONS or (mime_type or "").startswith("text/"):
        return "text"
    if ext == ".pdf" or mime_type == "application/pdf":
        return "pdf"
    if ext == ".docx" or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return "docx"
    return "text"


def _decode_text(data: bytes) -> str:
    try:
        import chardet
        detected = chardet.detect(data)
        encoding = detected.get("encoding") or "utf-8"
        return data.decode(encoding, errors="replace")
    except Exception:
        return data.decode("utf-8", errors="replace")


def _truncate(text: str, max_chars: int = MAX_TEXT_CHARS) -> Tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n...[truncated]", True


def _extract_pdf(data: bytes, enable_ocr: bool) -> str:
    text = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(p for p in pages if p.strip())
    except Exception:
        text = ""
    if not text.strip() and enable_ocr:
        text = _extract_image_ocr(data)
    return text


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""


def _extract_image_ocr(data: bytes) -> str:
    try:
        from .ocr import ocr_image_from_pil
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        import json
        result = json.loads(ocr_image_from_pil(img))
        return result.get("text", "")
    except Exception:
        return ""


def extract_file(data: bytes, filename: str = "", mime_type: str = "", enable_ocr: bool = True, token_budget: int = MAX_TEXT_TOKENS) -> Dict:
    """Extract readable text from an uploaded file.

    Returns:
        dict with keys:
            kind: 'text' | 'image' | 'pdf' | 'docx'
            text: extracted text (truncated to token_budget)
            truncated: bool
            error: optional error message
    """
    kind = _kind_for(filename, mime_type)
    text = ""
    error = None
    try:
        if kind == "image":
            text = ""  # handled as vision input, not text
        elif kind == "pdf":
            text = _extract_pdf(data, enable_ocr)
        elif kind == "docx":
            text = _extract_docx(data)
        else:
            text = _decode_text(data)
    except Exception as e:
        error = str(e)

    if kind != "image":
        text, truncated = _truncate(text or "", token_budget * 4)
    else:
        truncated = False

    return {
        "kind": kind,
        "text": text,
        "truncated": truncated,
        "error": error,
        "filename": filename,
        "mime_type": mime_type,
        "size": len(data),
    }
