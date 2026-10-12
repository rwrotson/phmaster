import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phmaster.services.errors import MediaError
from phmaster.services.media.layouts import resolve_layout
from phmaster.services.media.tools import Tools, run_tool

# Tag and title marker that identify tracks written by phmaster; MP4 keeps only the title.
TRACK_TAG = "PHMASTER"
TITLE_MARKER = "phmaster"


@dataclass(frozen=True, slots=True)
class AudioTrack:
    """An audio stream of a media file as reported by ffprobe."""

    stream_index: int
    audio_index: int
    codec: str
    channels: int
    layout: str | None
    sample_rate: int
    language: str | None
    title: str | None
    duration: float | None
    generated_by: str | None

    @property
    def is_generated(self) -> bool:
        """Tell whether phmaster wrote this track."""
        return self.generated_by is not None


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """Container-level facts and audio tracks of a media file."""

    path: Path
    format_name: str
    duration: float | None
    stream_count: int
    audio_tracks: tuple[AudioTrack, ...]

    @property
    def has_generated_tracks(self) -> bool:
        """Tell whether the file already contains phmaster tracks."""
        return any(track.is_generated for track in self.audio_tracks)


def probe(tools: Tools, path: Path) -> MediaInfo:
    """Read the streams and format of a media file with ffprobe."""
    if not path.is_file():
        raise MediaError(f"file not found: {path}")
    output = run_tool(
        [
            tools.ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        error=MediaError,
    )
    try:
        data = json.loads(output)
    except json.JSONDecodeError as error:
        raise MediaError(f"ffprobe returned invalid JSON for {path}") from error
    return parse_probe(path, data)


def parse_probe(path: Path, data: dict[str, Any]) -> MediaInfo:
    """Build a MediaInfo from ffprobe JSON output."""
    streams: list[dict[str, Any]] = data.get("streams", [])
    fmt: dict[str, Any] = data.get("format", {})
    format_duration = _float_or_none(fmt.get("duration"))
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    tracks = tuple(
        _parse_audio(stream, audio_index, format_duration)
        for audio_index, stream in enumerate(audio)
    )
    return MediaInfo(
        path=path,
        format_name=str(fmt.get("format_name", "")),
        duration=format_duration,
        stream_count=len(streams),
        audio_tracks=tracks,
    )


def _parse_audio(
    stream: dict[str, Any], audio_index: int, format_duration: float | None
) -> AudioTrack:
    tags = {str(key).lower(): str(value) for key, value in stream.get("tags", {}).items()}
    channels = int(stream.get("channels", 0))
    language = tags.get("language")
    title = tags.get("title") or tags.get("name")
    generated_by = tags.get(TRACK_TAG.lower())
    if generated_by is None and title is not None and TITLE_MARKER in title.lower():
        generated_by = ""
    return AudioTrack(
        stream_index=int(stream["index"]),
        audio_index=audio_index,
        codec=str(stream.get("codec_name", "unknown")),
        channels=channels,
        layout=resolve_layout(stream.get("channel_layout"), channels),
        sample_rate=int(stream.get("sample_rate", 0)),
        language=None if language in {None, "und"} else language,
        title=title,
        duration=_float_or_none(stream.get("duration")) or format_duration,
        generated_by=generated_by,
    )


def _float_or_none(value: object) -> float | None:
    try:
        return float(str(value)) if value is not None else None
    except ValueError:
        return None
