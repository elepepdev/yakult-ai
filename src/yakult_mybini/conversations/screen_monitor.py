import time
import base64
from loguru import logger
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None


class ScreenMonitor:
    """Time-based cooldown for proactive screen watching.

    Does NOT gate on pixel changes — the AI sees the screen every
    time the cooldown expires and decides for itself whether
    something interesting is happening.

    A lightweight change summary is computed for extra context,
    but never blocks the LLM call.
    """

    COOLDOWN_SECONDS: float = 8.0

    def __init__(self) -> None:
        self._thumb64: bytes | None = None
        self._last_change_desc: str = ""
        self._last_processed_time: float = 0.0

    def can_proactive_speak(self) -> bool:
        """Return True if the cooldown has elapsed."""
        elapsed = time.time() - self._last_processed_time
        if elapsed < self.COOLDOWN_SECONDS:
            logger.debug(
                f"Proactive speak skipped: {elapsed:.1f}s < "
                f"{self.COOLDOWN_SECONDS}s"
            )
            return False
        return True

    def update(self, b64_data: str) -> None:
        """Analyse the incoming frame and update internal state.

        This is purely informational — never blocks.  The caller
        should always proceed if can_proactive_speak() is True.
        """
        thumb = self._to_thumbnail(b64_data, 64)
        if thumb is None:
            return

        if self._thumb64 is None:
            self._thumb64 = thumb
            self._last_change_desc = (
                "[Pertama kali melihat layar — " 
                "awasi dan komentari jika ada yang menarik]"
            )
            logger.debug("ScreenMonitor: first frame")
            return

        diff = self._pixel_diff(self._thumb64, thumb)
        self._thumb64 = thumb

        if diff > 0.50:
            desc = (
                f"[Perubahan layar besar ({diff:.0%}) — "
                "kemungkinan pindah aplikasi. "
                "Cari sesuatu yang menarik untuk dikomentari.]"
            )
        elif diff > 0.10:
            desc = (
                f"[Ada perubahan di layar ({diff:.0%}) — "
                "cek apakah ada yang menarik.]"
            )
        else:
            desc = (
                f"[Perubahan kecil ({diff:.0%}) — "
                "mungkin scroll atau update biasa, "
                "abaikan jika tidak menarik.]"
            )

        self._last_change_desc = desc
        logger.debug(f"ScreenMonitor: {desc}")

    def mark_processed(self) -> None:
        self._last_processed_time = time.time()

    @property
    def change_description(self) -> str:
        return self._last_change_desc

    # ── internal helpers ────────────────────────────────────────

    def _to_thumbnail(self, b64_data: str, size: int) -> bytes | None:
        if not b64_data or Image is None:
            return None
        try:
            if "base64," in b64_data:
                b64_data = b64_data.split("base64,")[1]
            raw = base64.b64decode(b64_data)
            img = Image.open(BytesIO(raw))
            return img.resize((size, size), Image.LANCZOS).tobytes()
        except Exception as exc:
            logger.debug(f"ScreenMonitor: thumbnail({size}) error: {exc}")
            return None

    @staticmethod
    def _pixel_diff(a: bytes, b: bytes) -> float:
        if len(a) != len(b):
            return 1.0
        total = sum(abs(ai - bi) for ai, bi in zip(a, b))
        return total / (len(a) * 255.0)
