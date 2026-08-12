import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from loguru import logger
from uuid import uuid4

PLAYLISTS_DIR = os.environ.get(
    "PLAYLISTS_DIR", os.path.join(os.getcwd(), "playlists")
)
MAX_PLAYLISTS = 50
MAX_SONGS = 500


class PlaylistSong:
    def __init__(
        self,
        title: str,
        video_url: str,
        duration: int = 0,
        thumbnail: str = "",
        file_path: str = "",
        song_id: Optional[str] = None,
        added_at: Optional[str] = None,
    ):
        self.id = song_id or f"song_{uuid4().hex[:12]}"
        self.title = title
        self.video_url = video_url
        self.duration = duration
        self.thumbnail = thumbnail
        self.file_path = file_path
        self.added_at = added_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "video_url": self.video_url,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "file_path": self.file_path,
            "added_at": self.added_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaylistSong":
        return cls(
            title=data.get("title", ""),
            video_url=data.get("video_url", ""),
            duration=data.get("duration", 0),
            thumbnail=data.get("thumbnail", ""),
            file_path=data.get("file_path", ""),
            song_id=data.get("id"),
            added_at=data.get("added_at"),
        )


class Playlist:
    def __init__(
        self,
        name: str,
        playlist_id: Optional[str] = None,
        created_at: Optional[str] = None,
        songs: Optional[List[PlaylistSong]] = None,
    ):
        self.id = playlist_id or f"playlist_{uuid4().hex[:12]}"
        self.name = name
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.songs = songs or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "songs": [s.to_dict() for s in self.songs],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playlist":
        return cls(
            name=data.get("name", ""),
            playlist_id=data.get("id"),
            created_at=data.get("created_at"),
            songs=[PlaylistSong.from_dict(s) for s in data.get("songs", [])],
        )


class PlaylistManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, base_dir: str = PLAYLISTS_DIR):
        if self._initialized:
            return
        self._initialized = True
        self._base_dir = base_dir
        self._cache: List[Playlist] | None = None

    def _file_path(self) -> str:
        return os.path.join(self._base_dir, "playlists.json")

    def load(self) -> List[Playlist]:
        file_path = self._file_path()
        if not os.path.exists(file_path):
            self._cache = []
            return []
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            self._cache = [Playlist.from_dict(item) for item in data]
            return self._cache
        except Exception as e:
            logger.error(f"Failed to load playlists: {e}")
            self._cache = []
            return []

    def save(self, items: List[Playlist]) -> None:
        os.makedirs(self._base_dir, exist_ok=True)
        data = [item.to_dict() for item in items]
        try:
            with open(self._file_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._cache = items
        except Exception as e:
            logger.error(f"Failed to save playlists: {e}")

    def list(self) -> List[Playlist]:
        return self.load()

    def get(self, playlist_id: str) -> Optional[Playlist]:
        for p in self.load():
            if p.id == playlist_id:
                return p
        return None

    def create(self, name: str) -> Optional[Playlist]:
        name = (name or "").strip()
        if not name:
            return None
        playlist = Playlist(name=name)
        items = self.load()
        items.append(playlist)
        if len(items) > MAX_PLAYLISTS:
            items = items[-MAX_PLAYLISTS:]
        self.save(items)
        return playlist

    def delete(self, playlist_id: str) -> bool:
        items = self.load()
        filtered = [p for p in items if p.id != playlist_id]
        if len(filtered) == len(items):
            return False
        self.save(filtered)
        return True

    def rename(self, playlist_id: str, name: str) -> Optional[Playlist]:
        name = (name or "").strip()
        if not name:
            return None
        items = self.load()
        for p in items:
            if p.id == playlist_id:
                p.name = name
                self.save(items)
                return p
        return None

    def add_song(self, playlist_id: str, song: PlaylistSong) -> Optional[PlaylistSong]:
        items = self.load()
        for p in items:
            if p.id == playlist_id:
                for existing in p.songs:
                    if existing.video_url == song.video_url:
                        logger.info(
                            f"Song already in playlist {playlist_id}, skipping: {song.video_url}"
                        )
                        return existing
                p.songs.append(song)
                if len(p.songs) > MAX_SONGS:
                    p.songs = p.songs[-MAX_SONGS:]
                self.save(items)
                return song
        return None

    def remove_song(self, playlist_id: str, song_id: str) -> bool:
        items = self.load()
        for p in items:
            if p.id == playlist_id:
                before = len(p.songs)
                p.songs = [s for s in p.songs if s.id != song_id]
                if len(p.songs) == before:
                    return False
                self.save(items)
                return True
        return False

    def to_prompt_string(self) -> str:
        items = self.load()
        if not items:
            return ""
        lines = [f"- {p.name} (id: {p.id}): {', '.join(s.title for s in p.songs[:10])}" for p in items]
        return "[PLAYLISTS]\n" + "\n".join(lines)


playlist_manager = PlaylistManager()
