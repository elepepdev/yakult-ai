import os
import re
from pathlib import Path
from typing import Optional

from .osu_beatmap import OsuBeatmapParser
from .osu_types import Beatmap


OSU_LAZER_DATA_DIR = os.path.expanduser("~/.local/share/osu")
OSU_STABLE_SONGS_DIR = os.path.expanduser("~/.wine/drive_c/osu/Songs")


class OsuManager:
    def __init__(self):
        self._library: dict[str, list[Beatmap]] = {}
        self._scanned = False

    def scan_library(self) -> dict[str, list[Beatmap]]:
        self._library = {}
        found_files = self._find_osu_files()

        for fpath in found_files:
            try:
                bm = OsuBeatmapParser.parse(fpath)
                key = f"{bm.artist} - {bm.title}".lower()
                if key not in self._library:
                    self._library[key] = []
                self._library[key].append(bm)
            except Exception:
                pass

        self._scanned = True
        return self._library

    def _find_osu_files(self) -> list[str]:
        files = []

        lazer_dir = Path(OSU_LAZER_DATA_DIR) / "files"
        if lazer_dir.exists():
            for root, _dirs, fnames in os.walk(lazer_dir):
                for fname in fnames:
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "rb") as f:
                            header = f.read(19)
                            if header.startswith(b"osu file format v"):
                                files.append(fpath)
                    except Exception:
                        pass

        stable_dir = Path(OSU_STABLE_SONGS_DIR)
        if stable_dir.exists():
            for fpath in stable_dir.rglob("*.osu"):
                files.append(str(fpath))

        return files

    def list_songs(self) -> list[dict]:
        if not self._scanned:
            self.scan_library()

        songs = []
        for key, beatmaps in sorted(self._library.items()):
            bm = beatmaps[0]
            songs.append({
                "title": bm.title,
                "artist": bm.artist,
                "creator": bm.creator,
                "difficulties": [
                    {
                        "version": b.version,
                        "ar": b.ar,
                        "od": b.od,
                        "cs": b.cs,
                        "hp": b.hp,
                        "objects": b.total_hit_objects,
                        "duration_sec": round(b.duration_ms / 1000, 1),
                    }
                    for b in beatmaps
                ],
                "total_difficulties": len(beatmaps),
            })
        return songs

    def find_beatmap(
        self,
        query: str,
        difficulty: Optional[str] = None,
    ) -> Optional[Beatmap]:
        if not self._scanned:
            self.scan_library()

        query_lower = query.lower().strip()
        matches = []

        for key, beatmaps in self._library.items():
            if query_lower in key:
                matches.extend(beatmaps)

        if not matches:
            for key, beatmaps in self._library.items():
                for bm in beatmaps:
                    if query_lower in bm.title.lower():
                        matches.append(bm)

        if not matches:
            return None

        if difficulty:
            difficulty_lower = difficulty.lower().strip()
            for bm in matches:
                if difficulty_lower in bm.version.lower():
                    return bm
            return matches[0]

        return matches[0]

    @property
    def library(self) -> dict[str, list[Beatmap]]:
        return self._library

    def rescan(self) -> dict[str, list[Beatmap]]:
        self._scanned = False
        return self.scan_library()
