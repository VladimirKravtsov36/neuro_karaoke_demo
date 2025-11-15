"""
Integration helpers for the unofficial Yandex Music API.

The module exposes a thin wrapper that hides the low-level details of the
`yandex-music` package so the rest of the codebase can search, download and
retrieve lyrics with a single, well-typed API.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from pathlib import Path
from typing import Optional

from yandex_music import Client, Track
from yandex_music.download_info import DownloadInfo
from yandex_music.exceptions import NotFoundError, YandexMusicError

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TrackChoice:
    """Serializable representation of a track shown in the UI."""

    id: str
    title: str
    artists: str
    album: str
    duration_ms: int
    cover_url: Optional[str]
    has_sync_lyrics: bool
    has_text_lyrics: bool

    @property
    def duration_str(self) -> str:
        seconds = max(1, int(self.duration_ms / 1000))
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes}:{seconds:02d}"


@dataclass(slots=True)
class KaraokeLine:
    """Single LRC cue."""

    time: float
    text: str


@dataclass(slots=True)
class LyricsPayload:
    """Holds either synced (LRC) or plain lyrics."""

    source_format: str
    raw_text: str
    cues: list[KaraokeLine]
    plain_text: Optional[str] = None

    @property
    def is_synced(self) -> bool:
        return len(self.cues) > 0

    @property
    def duration(self) -> float:
        if not self.cues:
            return 0.0
        return self.cues[-1].time


class YandexMusicService:
    """High level API for searching and downloading Yandex Music tracks."""

    _filename_pattern = re.compile(r"[^\w\s-]", re.UNICODE)
    _lrc_tag_pattern = re.compile(r"\[(\d{1,2}):(\d{1,2})(?:\.(\d{1,3}))?]")

    def __init__(self, token: str) -> None:
        token = (token or "").strip()
        if not token:
            raise ValueError("Yandex Music token is empty")

        self.token = token
        self.client = Client(token).init()

    # --------------------------------------------------------------------- API
    def search_tracks(self, query: str, limit: int = 10) -> list[TrackChoice]:
        if not query.strip():
            return []

        search = self.client.search(query, type_="track")
        if not search or not search.tracks or not search.tracks.results:
            return []

        normalized: list[TrackChoice] = []
        for track in search.tracks.results[:limit]:
            artists = ", ".join(artist.name for artist in (track.artists or []) if artist and artist.name)
            album_title = track.albums[0].title if track.albums else "—"
            cover_url = None
            if track.cover_uri:
                cover_url = f"https://{track.cover_uri.replace('%%', '200x200')}"
            lyrics_info = track.lyrics_info
            normalized.append(
                TrackChoice(
                    id=str(track.id),
                    title=track.title or "Без названия",
                    artists=artists or "Неизвестный исполнитель",
                    album=album_title,
                    duration_ms=track.duration_ms or 0,
                    cover_url=cover_url,
                    has_sync_lyrics=bool(getattr(lyrics_info, "has_available_sync_lyrics", False)),
                    has_text_lyrics=bool(getattr(lyrics_info, "has_available_text_lyrics", False)),
                )
            )

        return normalized

    def download_track(self, track_id: str, destination_dir: Path | str) -> tuple[Path, Track]:
        track = self._fetch_track(track_id)
        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self._sanitize_filename(f"{track.title or 'track'}_{track.id}")
        file_path = destination_dir / f"{safe_name}.mp3"

        download_info = self._pick_download_info(track.id)
        audio_bytes = download_info.download_bytes()
        file_path.write_bytes(audio_bytes)

        return file_path, track

    def download_track_with_lyrics(
        self,
        track_id: str,
        destination_dir: Path | str,
    ) -> tuple[Path, Track, Optional[LyricsPayload]]:
        path, track = self.download_track(track_id, destination_dir)
        lyrics = self.fetch_lyrics(track.id)
        return path, track, lyrics

    def fetch_lyrics(self, track_id: str) -> Optional[LyricsPayload]:
        """Get synced lyrics when possible, otherwise plain text."""

        try:
            lrc = self.client.tracks_lyrics(track_id, format="LRC")
            if lrc:
                raw_lrc = lrc.fetch_lyrics()
                cues = self._parse_lrc(raw_lrc)
                if cues:
                    return LyricsPayload(
                        source_format="LRC",
                        raw_text=raw_lrc,
                        cues=cues,
                    )
        except (NotFoundError, YandexMusicError) as exc:
            LOGGER.debug("LRC lyrics unavailable for %s: %s", track_id, exc)

        try:
            plain = self.client.tracks_lyrics(track_id, format="TEXT")
            if plain:
                raw_text = plain.fetch_lyrics()
                return LyricsPayload(
                    source_format="TEXT",
                    raw_text=raw_text,
                    cues=[],
                    plain_text=raw_text,
                )
        except (NotFoundError, YandexMusicError) as exc:
            LOGGER.debug("Plain lyrics unavailable for %s: %s", track_id, exc)

        return None

    # ----------------------------------------------------------------- Helpers
    def _fetch_track(self, track_id: str) -> Track:
        response = self.client.tracks(track_id)
        if not response:
            raise ValueError(f"Track {track_id} not found")
        return response[0]

    def _pick_download_info(self, track_id: str) -> DownloadInfo:
        infos = self.client.tracks_download_info(track_id, get_direct_links=True)
        if not infos:
            raise RuntimeError(f"Download info for track {track_id} not available")

        return max(infos, key=lambda info: info.bitrate_in_kbps or 0)

    def _sanitize_filename(self, name: str) -> str:
        name = self._filename_pattern.sub("", name)
        name = re.sub(r"\s+", "_", name.strip())
        return name or "track"

    def _parse_lrc(self, raw_lrc: str) -> list[KaraokeLine]:
        cues: list[KaraokeLine] = []
        for line in raw_lrc.splitlines():
            tags = list(self._lrc_tag_pattern.finditer(line))
            if not tags:
                continue
            lyric_text = self._lrc_tag_pattern.sub("", line).strip()
            if not lyric_text:
                lyric_text = "..."
            for match in tags:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                millis = (match.group(3) or "0").ljust(3, "0")
                fractional = int(millis)
                timestamp = minutes * 60 + seconds + fractional / 1000
                cues.append(KaraokeLine(time=timestamp, text=lyric_text))

        cues.sort(key=lambda cue: cue.time)
        return cues


__all__ = [
    "YandexMusicService",
    "TrackChoice",
    "LyricsPayload",
    "KaraokeLine",
]

