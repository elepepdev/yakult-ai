import math
import os
import subprocess
import time
from typing import Optional

from .osu_beatmap import OsuBeatmapParser
from .osu_types import Beatmap


class OsuPlayer:
    def __init__(self, cursor_speed: float = 1.0, jitter: float = 2.0):
        self.cursor_speed = cursor_speed
        self.jitter = jitter
        self._running = False

    def _xdotool_relative_move(self, dx: float, dy: float):
        idx = round(dx)
        idy = round(dy)
        if idx == 0 and idy == 0:
            return
        subprocess.run(
            ["xdotool", "mousemove_relative", "--", str(idx), str(idy)],
            capture_output=True, timeout=2,
        )

    def _xdotool_absolute_move(self, x: int, y: int):
        subprocess.run(
            ["xdotool", "mousemove", str(x), str(y)],
            capture_output=True, timeout=2,
        )

    def _xdotool_click(self):
        subprocess.run(["xdotool", "click", "1"], capture_output=True, timeout=2)

    def _xdotool_mousedown(self):
        subprocess.run(["xdotool", "mousedown", "1"], capture_output=True, timeout=2)

    def _xdotool_mouseup(self):
        subprocess.run(["xdotool", "mouseup", "1"], capture_output=True, timeout=2)

    def focus_window(self, window_id: int) -> bool:
        result = subprocess.run(
            ["xdotool", "windowactivate", str(window_id)],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0

    def get_window_geometry(self, window_id: int) -> Optional[dict]:
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", str(window_id)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        geo = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                geo[k.strip()] = int(v.strip())
        return geo

    def click_play(self, window_id: int) -> bool:
        geo = self.get_window_geometry(window_id)
        if not geo:
            return False

        wx = geo.get("X", 0)
        wy = geo.get("Y", 0)
        ww = geo.get("WIDTH", 0)
        wh = geo.get("HEIGHT", 0)

        play_x = wx + ww // 2
        play_y = wy + wh - int(wh * 0.12)

        self._xdotool_absolute_move(play_x, play_y)
        time.sleep(0.15)
        self._xdotool_click()
        return True

    def set_borderless_mode(self, enable: bool = True) -> bool:
        ini_path = os.path.expanduser("~/.local/share/osu/framework.ini")
        try:
            with open(ini_path) as f:
                lines = f.readlines()

            new_lines = []
            mode = "Borderless" if enable else "Fullscreen"
            found = False
            for line in lines:
                if line.strip().startswith("WindowMode "):
                    new_lines.append(f"WindowMode = {mode}\n")
                    found = True
                else:
                    new_lines.append(line)

            if not found:
                new_lines.append(f"WindowMode = {mode}\n")

            with open(ini_path, "w") as f:
                f.writelines(new_lines)
            return True
        except Exception:
            return False

    def _busy_sleep(self, target_ms: float, t0: float):
        while True:
            now_ms = time.monotonic() * 1000
            remaining = target_ms - (now_ms - t0)
            if remaining <= 2:
                break
            time.sleep(max((remaining - 1) / 1000, 0.001))

    def execute(
        self,
        beatmap: Beatmap,
        t0: float,
        window_x: int,
        window_y: int,
        window_w: int,
        window_h: int,
    ) -> dict:
        self._running = True

        paths = OsuBeatmapParser.precompute_paths(
            beatmap,
            window_w, window_h,
            window_x, window_y,
            window_w, window_h,
            cursor_speed=self.cursor_speed,
            jitter=self.jitter,
        )

        circle_objects = [o for o in beatmap.hit_objects if o.obj_type & 1]
        total = len(circle_objects)

        stats = {
            "total_objects": total,
            "hit_300": 0,
            "hit_100": 0,
            "hit_50": 0,
            "miss": 0,
            "max_combo": 0,
            "combo": 0,
            "score": 0,
        }

        cursor_x, cursor_y = None, None
        held = False
        hold_until_ms = 0.0

        first = True
        for mp in paths:
            if not self._running:
                break

            self._busy_sleep(mp.start_time_ms, t0)

            if first:
                self._xdotool_absolute_move(round(mp.start_x), round(mp.start_y))
                cursor_x, cursor_y = mp.start_x, mp.start_y
                first = False

            if held:
                now = time.monotonic() * 1000
                if now >= hold_until_ms:
                    self._xdotool_mouseup()
                    held = False

            for pp in mp.points:
                if not self._running:
                    break

                self._busy_sleep(pp.time_ms, t0)

                dx = pp.x - cursor_x
                dy = pp.y - cursor_y
                if abs(dx) > 0.5 or abs(dy) > 0.5:
                    self._xdotool_relative_move(dx, dy)

                cursor_x, cursor_y = pp.x, pp.y

            if not self._running:
                break

            if mp.click_time_ms is not None:
                self._busy_sleep(mp.click_time_ms, t0)

                final_x, final_y = round(mp.end_x), round(mp.end_y)
                dx = final_x - cursor_x
                dy = final_y - cursor_y
                if abs(dx) > 0.5 or abs(dy) > 0.5:
                    self._xdotool_relative_move(dx, dy)
                cursor_x, cursor_y = float(final_x), float(final_y)

                self._xdotool_click()

                hit_ms = time.monotonic() * 1000 - t0
                hit_diff = abs(hit_ms - mp.click_time_ms)

                stats["combo"] += 1
                if hit_diff <= beatmap.hit_window_300:
                    stats["hit_300"] += 1
                    stats["score"] += 300
                elif hit_diff <= beatmap.hit_window_100:
                    stats["hit_100"] += 1
                    stats["score"] += 100
                elif hit_diff <= beatmap.hit_window_50:
                    stats["hit_50"] += 1
                    stats["score"] += 50
                else:
                    stats["miss"] += 1
                    stats["combo"] = 0

                stats["max_combo"] = max(stats["max_combo"], stats["combo"])

                if mp.hold_until_ms is not None:
                    self._xdotool_mousedown()
                    held = True
                    hold_until_ms = t0 + mp.hold_until_ms
                    self._busy_sleep(mp.hold_until_ms, t0)
                    self._xdotool_mouseup()
                    held = False

        if held:
            self._xdotool_mouseup()

        total_hits = stats["hit_300"] + stats["hit_100"] + stats["hit_50"] + stats["miss"]
        if total_hits > 0:
            accuracy = (
                (stats["hit_300"] * 300 + stats["hit_100"] * 100 + stats["hit_50"] * 50)
                / (total_hits * 300) * 100
            )
        else:
            accuracy = 0.0

        stats["accuracy"] = round(accuracy, 2)

        if stats["miss"] == 0 and stats["hit_50"] == 0:
            stats["rank"] = "SS" if accuracy == 100 else "S"
        elif stats["miss"] == 0:
            stats["rank"] = "S"
        elif accuracy > 90:
            stats["rank"] = "A"
        elif accuracy > 80:
            stats["rank"] = "B"
        elif accuracy > 70:
            stats["rank"] = "C"
        else:
            stats["rank"] = "D"

        self._running = False
        return stats

    def stop(self):
        self._running = False
