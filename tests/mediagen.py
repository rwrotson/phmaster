import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phmaster.services.media.layouts import channel_names

_VIDEO_CODECS = {".webm": "libvpx", ".avi": "mpeg4"}
_SUBTITLE_CODECS = {".mkv": "srt", ".mp4": "mov_text"}


@dataclass(frozen=True, slots=True)
class AudioSpec:
    """A synthetic audio track: quiet tones with an optional burst 20 dB louder."""

    layout: str = "stereo"
    codec: str = "aac"
    language: str | None = None
    title: str | None = None
    level: float = 0.03
    burst: tuple[float, float] | None = (2.0, 3.0)


def run(command: list[str]) -> str:
    """Run a test helper command and return its stdout."""
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        raise AssertionError(f"{command[0]} failed: {result.stderr}")
    return result.stdout


def _audio_source(spec: AudioSpec, duration: float) -> str:
    gain = f"(1+9*between(t,{spec.burst[0]},{spec.burst[1]}))" if spec.burst else "1"
    exprs = "|".join(
        f"{spec.level}*{gain}*sin(2*PI*{60 if name == 'LFE' else 220 + 70 * i}*t)"
        for i, name in enumerate(channel_names(spec.layout))
    )
    return f"aevalsrc=exprs='{exprs}':s=48000:d={duration}:c={spec.layout}"


def _audio_options(audio: Sequence[AudioSpec]) -> list[str]:
    options: list[str] = []
    for index, spec in enumerate(audio):
        options += [f"-c:a:{index}", spec.codec]
        if spec.language:
            options += [f"-metadata:s:a:{index}", f"language={spec.language}"]
        if spec.title:
            options += [f"-metadata:s:a:{index}", f"title={spec.title}"]
    return options


def make_media(
    path: Path,
    audio: Sequence[AudioSpec] = (AudioSpec(),),
    *,
    duration: float = 5.0,
    subtitles: bool = False,
) -> Path:
    """Generate a small media file with a test video, synthetic audio, and optional subtitles."""
    inputs = ["-f", "lavfi", "-i", f"testsrc=size=64x48:rate=10:duration={duration}"]
    for spec in audio:
        inputs += ["-f", "lavfi", "-i", _audio_source(spec, duration)]
    maps = ["-map", "0:v"] + [arg for i in range(len(audio)) for arg in ("-map", f"{i + 1}:a")]
    codecs = ["-c:v", _VIDEO_CODECS.get(path.suffix, "mpeg4"), *_audio_options(audio)]
    if subtitles:
        srt = path.with_suffix(".srt")
        srt.write_text("1\n00:00:00,500 --> 00:00:02,000\nHello\n", encoding="utf-8")
        inputs += ["-i", str(srt)]
        maps += ["-map", f"{len(audio) + 1}:s"]
        codecs += ["-c:s", _SUBTITLE_CODECS[path.suffix]]
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, *maps, *codecs, str(path)])
    return path


def ffprobe_streams(path: Path) -> list[dict[str, Any]]:
    """Return ffprobe's stream list for a file."""
    output = run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)])
    streams: list[dict[str, Any]] = json.loads(output)["streams"]
    return streams


def packet_hashes(path: Path, stream: str) -> str:
    """Return per-packet sizes and hashes of a stream, to compare stream copies bit for bit."""
    output = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            stream,
            "-c",
            "copy",
            "-f",
            "framemd5",
            "-",
        ]
    )
    rows = (line.split(",") for line in output.splitlines() if not line.startswith("#"))
    return "\n".join(f"{row[-2].strip()} {row[-1].strip()}" for row in rows)
