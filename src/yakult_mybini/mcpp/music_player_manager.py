import json
import logging
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

    def play_song(self, song_info: dict, is_recommended: bool = False):
        if self.current_song:
            self.history.append(self.current_song)
        self.current_song = song_info
        self.is_recommended = is_recommended

    def stop(self):
        self.current_song = None
        self.is_recommended = False

    def get_prev_song(self) -> Optional[dict]:
        if self.history:
            return self.history.pop()
        return None

    def get_current(self) -> Optional[dict]:
        return self.current_song

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


music_player_manager = MusicPlayerManager()
