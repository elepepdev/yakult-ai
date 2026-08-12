import json
import logging
import os
import random
from typing import Optional

import yt_dlp

logger = logging.getLogger(__name__)


class MusicPlayerManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.current_song: Optional[dict] = None
        self.history: list[dict] = []
        self.is_recommended: bool = False
        self._queue: list[dict] = []
        self._queue_index: int = -1
        self._queue_active: bool = False

    def play_song(self, song_info: dict, is_recommended: bool = False):
        if self.current_song:
            self.history.append(self.current_song)
        self.current_song = song_info
        self.is_recommended = is_recommended

    def set_queue(self, songs: list[dict], shuffle: bool = False):
        order = list(songs)
        if shuffle:
            random.shuffle(order)
        self._queue = order
        self._queue_index = -1
        self._queue_active = True
        logger.info(f"Queue set with {len(order)} song(s), shuffle={shuffle}")

    def queue_active(self) -> bool:
        return self._queue_active

    def next_queued(self) -> Optional[dict]:
        if not self._queue_active or not self._queue:
            return None
        self._queue_index += 1
        if self._queue_index >= len(self._queue):
            self._queue_active = False
            self._queue_index = -1
            return None
        return self._queue[self._queue_index]

    def seek_queue(self, index: int) -> None:
        if not self._queue:
            return
        self._queue_index = max(0, min(index, len(self._queue) - 1)) - 1

    def clear_queue(self):
        self._queue = []
        self._queue_index = -1
        self._queue_active = False

    def stop(self):
        self.current_song = None
        self.is_recommended = False
        self.clear_queue()

    async def refresh_stream_url(self, video_url: str) -> Optional[str]:
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestaudio/best",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info.get("url")
        except Exception as e:
            logger.error(f"Failed to refresh stream URL for {video_url}: {e}")
            return None

    def resolve_stream_url(self, song: dict) -> Optional[str]:
        """Return playable stream URL, preferring a downloaded local file."""
        file_path = song.get("file_path")
        if file_path and os.path.exists(file_path):
            return file_path
        return song.get("stream_url")


music_player_manager = MusicPlayerManager()
