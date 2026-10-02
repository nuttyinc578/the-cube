"""Official Pixabay Halloween music downloader used by the 6.4 loading screen."""

from __future__ import annotations

import html
import json
import re
import shutil
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import urlparse


TRACK_PAGE = "https://pixabay.com/music/happy-childrens-tunes-halloween-music-609427/"
TRACK_TITLE = "Halloween Music"
TRACK_ARTIST = "Sound4Stock"
TRACK_ID = "609427"
LICENSE_URL = "https://pixabay.com/service/license-summary/"
MAX_AUDIO_BYTES = 40 * 1024 * 1024


class HalloweenMusicError(RuntimeError):
    """Raised when the exact requested track cannot be safely downloaded."""


def _find_audio_url(value: object) -> str | None:
    if isinstance(value, str):
        parsed = urlparse(html.unescape(value))
        if parsed.scheme == "https" and parsed.hostname == "cdn.pixabay.com" and parsed.path.endswith(".mp3"):
            return html.unescape(value)
    elif isinstance(value, list):
        for item in value:
            found = _find_audio_url(item)
            if found:
                return found
    elif isinstance(value, dict):
        for key in ("contentUrl", "url", "src", "audio", "sources"):
            if key in value:
                found = _find_audio_url(value[key])
                if found:
                    return found
        for item in value.values():
            found = _find_audio_url(item)
            if found:
                return found
    return None


def _extract_audio_url(page: str) -> str:
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page,
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            data = json.loads(html.unescape(match.group(1)))
        except (json.JSONDecodeError, TypeError):
            continue
        found = _find_audio_url(data)
        if found:
            return found
    patterns = (
        r'https://cdn\.pixabay\.com/download/audio/[^"\'<>\\ ]+\.mp3[^"\'<>\\ ]*',
        r'"contentUrl"\s*:\s*"(https:\\/\\/cdn\.pixabay\.com\\/[^" ]+)",',
    )
    for pattern in patterns:
        match = re.search(pattern, page)
        if match:
            value = match.group(1) if match.lastindex else match.group(0)
            return html.unescape(value.replace("\\/", "/"))
    raise HalloweenMusicError("Pixabay did not expose the track download. Use OPEN PIXABAY, download it, then return here.")


def _looks_like_mp3(path: Path) -> bool:
    if not path.is_file() or not (4_096 <= path.stat().st_size <= MAX_AUDIO_BYTES):
        return False
    with path.open("rb") as stream:
        header = stream.read(3)
    return header == b"ID3" or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0)


class HalloweenMusicManager:
    def __init__(self, destination: Path):
        self.destination = Path(destination)

    @property
    def ready(self) -> bool:
        return _looks_like_mp3(self.destination)

    def import_from_downloads(self) -> bool:
        downloads = Path.home() / "Downloads"
        candidates = (
            downloads / "halloween-music-609427.mp3",
            downloads / "halloween_music-609427.mp3",
            downloads / "halloween_music.mp3",
        )
        for source in candidates:
            if _looks_like_mp3(source):
                self.destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, self.destination)
                return True
        return False

    def download(self) -> Path:
        if self.ready or self.import_from_downloads():
            return self.destination
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        page_request = urllib.request.Request(TRACK_PAGE, headers=headers)
        try:
            with urllib.request.urlopen(page_request, timeout=35) as response:
                page = response.read(4 * 1024 * 1024).decode("utf-8", "replace")
        except Exception as exc:
            raise HalloweenMusicError(f"Pixabay download page unavailable: {exc}") from exc
        audio_url = _extract_audio_url(page)
        request = urllib.request.Request(audio_url, headers={**headers, "Referer": TRACK_PAGE})
        partial = self.destination.with_suffix(".mp3.part")
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(request, timeout=45) as response, partial.open("wb") as output:
                length = int(response.headers.get("Content-Length", "0") or 0)
                if length > MAX_AUDIO_BYTES:
                    raise HalloweenMusicError("Pixabay audio is unexpectedly large")
                received = 0
                while True:
                    chunk = response.read(512 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > MAX_AUDIO_BYTES:
                        raise HalloweenMusicError("Pixabay audio exceeded the safety limit")
                    output.write(chunk)
            if not _looks_like_mp3(partial):
                raise HalloweenMusicError("The downloaded file is not a valid MP3")
            partial.replace(self.destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return self.destination

    def open_official_page(self) -> bool:
        return webbrowser.open(TRACK_PAGE, new=2)


__all__ = [
    "HalloweenMusicError",
    "HalloweenMusicManager",
    "LICENSE_URL",
    "TRACK_ARTIST",
    "TRACK_ID",
    "TRACK_PAGE",
    "TRACK_TITLE",
]
