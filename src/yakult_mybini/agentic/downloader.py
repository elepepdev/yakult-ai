import os
import re
import uuid

from loguru import logger

DOWNLOAD_DIR = os.environ.get(
    "PLAYLIST_DOWNLOAD_DIR", os.path.join(os.getcwd(), "playlists", "downloads")
)
VIDEO_DIR = os.environ.get(
    "PLAYLIST_VIDEO_DIR", os.path.join(os.getcwd(), "playlists", "videos")
)


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r'[^\w\- ]', "", title)
    return cleaned.strip()[:80] or "media"


def _download(video_url: str, title: str, filename: str, out_dir: str, video: bool) -> str:
    import yt_dlp

    os.makedirs(out_dir, exist_ok=True)
    safe = filename or _safe_filename(title or video_url)
    unique = f"{safe}_{uuid.uuid4().hex[:8]}"
    outtmpl = os.path.join(out_dir, f"{unique}.%(ext)s")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestvideo+bestaudio/best" if video else "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
    }
    if not video:
        ydl_opts["format"] = "bestaudio/best"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        if info and info.get("requested_downloads"):
            return info["requested_downloads"][0]["filepath"]
        filepath = ydl.prepare_filename(info)
        if os.path.exists(filepath):
            return filepath
    raise RuntimeError("Download failed: no output file produced")


def download_audio(video_url: str, title: str = "", filename: str = "") -> str:
    """Download YouTube audio to a local file. Returns absolute file path."""
    return _download(video_url, title, filename, DOWNLOAD_DIR, video=False)


def download_video(video_url: str, title: str = "", filename: str = "") -> str:
    """Download a YouTube video to a local file. Returns absolute file path."""
    return _download(video_url, title, filename, VIDEO_DIR, video=True)
