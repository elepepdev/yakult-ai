import os
import subprocess
import tempfile
import time
from typing import Optional

from PIL import Image

from .osu_types import Beatmap


class OsuScreenMonitor:
    def __init__(self):
        self._osu_window_id: Optional[int] = None
        self._window_geometry: Optional[dict] = None
        self._tmpdir = tempfile.mkdtemp(prefix="osu_screen_")

    def find_osu_window(self) -> Optional[int]:
        for name_attr in [("--class", "osu"), ("--classname", "osu"), ("--name", "osu")]:
            result = subprocess.run(
                ["xdotool", "search", name_attr[0], name_attr[1]],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                windows = result.stdout.strip().split("\n")
                self._osu_window_id = int(windows[0])
                self._update_window_geometry()
                return self._osu_window_id
        return None

    def _update_window_geometry(self) -> Optional[dict]:
        if not self._osu_window_id:
            return None
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", str(self._osu_window_id)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        geo = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                geo[k.strip()] = int(v.strip())
        self._window_geometry = geo
        return geo

    @property
    def window_geometry(self) -> Optional[dict]:
        return self._window_geometry

    def _fullscreen_capture(self) -> Optional[Image.Image]:
        tmp = f"{self._tmpdir}/osu_shot.png"
        result = subprocess.run(
            ["spectacle", "--background", "--nonotify", "-o", tmp],
            capture_output=True, timeout=10,
        )
        if result.returncode != 0 or not os.path.isfile(tmp):
            return None
        return Image.open(tmp).convert("RGB")

    def _capture_playfield_region(self) -> Optional[Image.Image]:
        full = self._fullscreen_capture()
        if full is None:
            return None

        geo = self._window_geometry
        if not geo:
            return full

        wx, wy = geo.get("X", 0), geo.get("Y", 0)
        ww, wh = geo.get("WIDTH", 0), geo.get("HEIGHT", 0)

        pf_center_x = wx + ww // 2
        pf_center_y = wy + wh // 2
        size = min(ww, wh) // 3
        half = size // 2

        left = max(0, pf_center_x - half)
        top = max(0, pf_center_y - half)
        right = min(full.width, pf_center_x + half)
        bottom = min(full.height, pf_center_y + half)

        return full.crop((left, top, right, bottom))

    def _is_gameplay(self, img: Image.Image) -> bool:
        pixels = list(img.getdata())
        n = len(pixels)
        if n == 0:
            return False

        r = [p[0] for p in pixels]
        g = [p[1] for p in pixels]
        b = [p[2] for p in pixels]

        avg = (sum(r) + sum(g) + sum(b)) / (n * 3)

        r_var = sum((x - sum(r) / n) ** 2 for x in r) / n if n > 1 else 0
        g_var = sum((x - sum(g) / n) ** 2 for x in g) / n if n > 1 else 0
        b_var = sum((x - sum(b) / n) ** 2 for x in b) / n if n > 1 else 0
        var = (r_var + g_var + b_var) / 3

        # Gameplay: bright (avg > 30) and varied (var > 500)
        return avg > 30 and var > 500

    def detect_gameplay_start(
        self,
        beatmap: Beatmap,
        enter_time: float,
        timeout: float = 20.0,
    ) -> Optional[float]:
        if not self.find_osu_window():
            return None

        start_time = time.monotonic()
        first_check = True

        while time.monotonic() - start_time < timeout:
            img = self._capture_playfield_region()
            if img is None:
                time.sleep(1.0)
                continue

            is_gameplay = self._is_gameplay(img)

            if is_gameplay:
                now_ms = time.monotonic() * 1000
                if beatmap.hit_objects:
                    first_time = beatmap.hit_objects[0].time_ms
                    approach_ms = beatmap.approach_duration_ms

                    # Estimate: detection happens some time after song start
                    # t0 = now - first_time + approach_ms
                    # This assumes detection happened at approach circle appearance.
                    # Since spectacle is slow, we may detect later.
                    # Compensate by subtracting half the capture delay (~500ms).
                    capture_delay = time.monotonic() - start_time
                    compensated = min(capture_delay / 2 * 1000, approach_ms / 2)
                    t0 = now_ms - first_time + approach_ms - compensated
                else:
                    t0 = now_ms
                return t0

            interval = 0.5 if first_check else 1.0
            first_check = False
            time.sleep(interval)

        return None

    def close(self):
        import shutil
        if hasattr(self, '_tmpdir'):
            shutil.rmtree(self._tmpdir, ignore_errors=True)
