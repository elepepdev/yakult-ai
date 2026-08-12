import math
import random
from pathlib import Path
from typing import Optional

from .osu_types import (
    Beatmap, HitObject, TimingPoint, MovementPath, PathPoint,
)


class OsuBeatmapParser:

    @staticmethod
    def parse(file_path: str | Path) -> Beatmap:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        sections: dict[str, list[str]] = {}
        current_section = None
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                sections[current_section] = []
            elif current_section:
                sections[current_section].append(line)

        meta = OsuBeatmapParser._parse_kv(sections.get("General", []))
        metadata = OsuBeatmapParser._parse_kv(sections.get("Metadata", []))
        diff = OsuBeatmapParser._parse_kv(sections.get("Difficulty", []))

        title = metadata.get("Title", "Unknown")
        artist = metadata.get("Artist", "Unknown")
        creator = metadata.get("Creator", "Unknown")
        version = metadata.get("Version", "Unknown")

        audio_filename = meta.get("AudioFilename", "")
        audio_lead_in = int(meta.get("AudioLeadIn", "0"))
        mode = int(meta.get("Mode", "0"))

        ar = float(diff.get("ApproachRate", "5"))
        od = float(diff.get("OverallDifficulty", "5"))
        cs = float(diff.get("CircleSize", "4"))
        hp = float(diff.get("HPDrainRate", "5"))
        slider_mult = float(diff.get("SliderMultiplier", "1.4"))
        slider_tick = float(diff.get("SliderTickRate", "1"))

        timing_points = OsuBeatmapParser._parse_timing_points(
            sections.get("TimingPoints", [])
        )
        hit_objects = OsuBeatmapParser._parse_hit_objects(
            sections.get("HitObjects", [])
        )

        return Beatmap(
            title=title,
            artist=artist,
            creator=creator,
            version=version,
            audio_filename=audio_filename,
            audio_lead_in=audio_lead_in,
            mode=mode,
            ar=ar,
            od=od,
            cs=cs,
            hp=hp,
            slider_multiplier=slider_mult,
            slider_tick_rate=slider_tick,
            hit_objects=hit_objects,
            timing_points=timing_points,
            file_path=str(file_path),
        )

    @staticmethod
    def _parse_kv(lines: list[str]) -> dict[str, str]:
        result = {}
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                result[key.strip()] = val.strip()
        return result

    @staticmethod
    def _parse_timing_points(lines: list[str]) -> list[TimingPoint]:
        points = []
        for line in lines:
            parts = line.split(",")
            if len(parts) < 8:
                continue
            try:
                points.append(TimingPoint(
                    time_ms=int(parts[0]),
                    beat_length=float(parts[1]),
                    meter=int(parts[2]),
                    sample_set=int(parts[3]),
                    sample_index=int(parts[4]),
                    volume=int(parts[5]),
                    uninherited=bool(int(parts[6])),
                    effects=int(parts[7]) if len(parts) > 7 else 0,
                ))
            except (ValueError, IndexError):
                continue
        points.sort(key=lambda tp: tp.time_ms)
        return points

    @staticmethod
    def _parse_hit_objects(lines: list[str]) -> list[HitObject]:
        objects = []
        for line in lines:
            parts = line.split(",")
            if len(parts) < 5:
                continue
            try:
                x = int(parts[0])
                y = int(parts[1])
                time_ms = int(parts[2])
                obj_type = int(parts[3])
                hit_sound = int(parts[4])

                end_time_ms = None
                curve_type = None
                curve_points = []
                slides = 0
                length = 0.0

                if len(parts) > 5 and parts[5]:
                    obj_params = parts[5]
                    if obj_type & 2:
                        # Slider: curveType|curvePoints,slides,length,edgeSounds,edgeSets
                        sub_parts = obj_params.split(",")
                        if len(sub_parts) >= 3:
                            curve_info = sub_parts[0].split("|")
                            curve_type = curve_info[0]
                            for p in curve_info[1:]:
                                if ":" in p:
                                    cx, cy = p.split(":")
                                    curve_points.append((int(cx), int(cy)))
                            slides = int(sub_parts[1])
                            length = float(sub_parts[2])
                            if len(sub_parts) > 4:
                                edge_sounds = sub_parts[3]
                                edge_sets = sub_parts[4]
                    elif obj_type & 8:
                        # Spinner
                        try:
                            end_time_ms = int(obj_params)
                        except ValueError:
                            pass
                    elif obj_type & 128:
                        # Mania hold
                        try:
                            end_time_ms = int(obj_params)
                        except ValueError:
                            pass

                ho = HitObject(
                    x=x, y=y, time_ms=time_ms, obj_type=obj_type,
                    hit_sound=hit_sound, end_time_ms=end_time_ms,
                    curve_type=curve_type, curve_points=curve_points,
                    slides=slides, length=length,
                )
                objects.append(ho)
            except (ValueError, IndexError):
                continue
        return objects

    @staticmethod
    def precompute_paths(
        beatmap: Beatmap,
        screen_width: int,
        screen_height: int,
        window_x: int,
        window_y: int,
        window_w: int,
        window_h: int,
        cursor_speed: float = 1.0,
        jitter: float = 1.0,
    ) -> list[MovementPath]:
        scale_x = window_w / 512.0
        scale_y = window_h / 384.0

        def map_coords(gx: float, gy: float) -> tuple[float, float]:
            sx = window_x + gx * ((window_w) / 512.0)
            sy = window_y + gy * ((window_h) / 384.0)
            return sx, sy

        def ease_in_out_sine(t: float) -> float:
            return -(math.cos(math.pi * t) - 1) / 2

        paths = []
        prev_x, prev_y = None, None

        for obj in beatmap.hit_objects:
            if not (obj.obj_type & 1):
                continue

            tx, ty = map_coords(obj.x, obj.y)

            if prev_x is not None:
                dx = tx - prev_x
                dy = ty - prev_y
                dist = math.hypot(dx, dy)
                travel_time = max(dist / (2000 * cursor_speed), 50.0)

                move_start_time = max(prev_time, obj.time_ms - travel_time)
                move_end_time = obj.time_ms

                path_points = []
                duration = move_end_time - move_start_time
                if duration > 0:
                    num_steps = max(int(duration / 6), 10)
                    for i in range(num_steps + 1):
                        t = i / num_steps
                        eased = ease_in_out_sine(t)
                        px = prev_x + dx * eased
                        py = prev_y + dy * eased
                        jx = random.uniform(-jitter, jitter)
                        jy = random.uniform(-jitter, jitter)
                        pt = move_start_time + t * duration
                        path_points.append(PathPoint(px + jx, py + jy, pt))
                else:
                    path_points = [PathPoint(prev_x, prev_y, obj.time_ms)]

                mp = MovementPath(
                    start_time_ms=move_start_time,
                    end_time_ms=move_end_time,
                    start_x=prev_x,
                    start_y=prev_y,
                    end_x=tx,
                    end_y=ty,
                    points=path_points,
                    click_time_ms=obj.time_ms,
                    hold_until_ms=obj.end_time_ms,
                )
                paths.append(mp)
            else:
                mp = MovementPath(
                    start_time_ms=obj.time_ms,
                    end_time_ms=obj.time_ms,
                    start_x=tx,
                    start_y=ty,
                    end_x=tx,
                    end_y=ty,
                    points=[PathPoint(tx, ty, obj.time_ms)],
                    click_time_ms=obj.time_ms,
                    hold_until_ms=obj.end_time_ms,
                )
                paths.append(mp)

            prev_x, prev_y = tx, ty
            prev_time = obj.time_ms

        return paths
