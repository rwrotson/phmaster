from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from phmaster.services.media.layouts import channel_names
from phmaster.services.media.tools import Tools

SAMPLE_RATE = 48_000
# The safety limiter runs at 4x the output rate to catch inter-sample (true) peaks.
LIMITER_SAMPLE_RATE = 4 * SAMPLE_RATE
SURROUND_MIX_LEVEL = 0.707


class Codec(StrEnum):
    """Audio codec of a generated track."""

    aac = "aac"
    eac3 = "eac3"
    ac3 = "ac3"
    opus = "opus"
    flac = "flac"


_ENCODERS: dict[Codec, str] = {
    Codec.aac: "aac",
    Codec.eac3: "eac3",
    Codec.ac3: "ac3",
    Codec.opus: "libopus",
    Codec.flac: "flac",
}

_MP4_CODECS = frozenset({Codec.aac, Codec.eac3, Codec.ac3})
_MATROSKA_INPUTS = frozenset({".mkv", ".mk3d", ".mka"})
_MP4_INPUTS: dict[str, str] = {".mp4": "mp4", ".m4v": "mp4", ".mov": "mov"}
# Containers whose timestamps are often incomplete when stream-copied into Matroska.
_GENPTS_INPUTS = frozenset({".avi", ".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".vob", ".wmv"})


@dataclass(frozen=True, slots=True)
class DecodeSpec:
    """How to decode one audio track to raw float PCM."""

    source: Path
    audio_index: int
    source_layout: str | None
    target_layout: str
    center_gain: float = 1.0
    dialog_channel: bool = False

    @property
    def channels(self) -> int:
        """Number of interleaved channels in the decoded stream."""
        return len(channel_names(self.target_layout)) + int(self.dialog_channel)


@dataclass(frozen=True, slots=True)
class EncodeSpec:
    """How to encode raw float PCM into a temporary Matroska audio file."""

    output: Path
    layout: str
    codec: Codec
    bitrate: str | None
    ceiling_db: float


@dataclass(frozen=True, slots=True)
class NewTrack:
    """An encoded audio file to mux into the output with its metadata."""

    path: Path
    title: str
    language: str | None
    tag: str


@dataclass(frozen=True, slots=True)
class Container:
    """Output container: file extension and ffmpeg muxer name."""

    extension: str
    muxer: str

    @property
    def is_matroska(self) -> bool:
        """Tell whether the container is Matroska."""
        return self.muxer == "matroska"


def decode_command(tools: Tools, spec: DecodeSpec) -> list[str]:
    """Build an ffmpeg command that writes the track as interleaved f32le PCM to stdout."""
    main = _layout_filter(spec)
    if spec.dialog_channel:
        graph = (
            f"[0:a:{spec.audio_index}]asplit=2[main][dialog];"
            f"[main]{main}[mainout];"
            f"[dialog]pan=mono|c0=FC,aresample={SAMPLE_RATE},"
            "aformat=sample_fmts=flt:channel_layouts=mono[dialogout];"
            "[mainout][dialogout]amerge=inputs=2[out]"
        )
    else:
        graph = f"[0:a:{spec.audio_index}]{main}[out]"
    return [
        tools.ffmpeg,
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(spec.source),
        "-filter_complex",
        graph,
        "-map",
        "[out]",
        "-f",
        "f32le",
        "-c:a",
        "pcm_f32le",
        "pipe:1",
    ]


def _layout_filter(spec: DecodeSpec) -> str:
    resample = f"aresample={SAMPLE_RATE}"
    if spec.source_layout != spec.target_layout:
        resample += (
            f":ochl={spec.target_layout}:clev={spec.center_gain:.4f}"
            f":slev={SURROUND_MIX_LEVEL}:lfe_mix_level=0"
        )
    return f"{resample},aformat=sample_fmts=flt:channel_layouts={spec.target_layout}"


def encode_command(tools: Tools, spec: EncodeSpec) -> list[str]:
    """Build an ffmpeg command that limits and encodes f32le PCM read from stdin."""
    ceiling = 10 ** (spec.ceiling_db / 20)
    limiter = (
        f"aresample={LIMITER_SAMPLE_RATE},"
        f"alimiter=limit={ceiling:.4f}:attack=1:release=60:level=false:latency=true,"
        f"aresample={SAMPLE_RATE}"
    )
    command = [
        tools.ffmpeg,
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-f",
        "f32le",
        "-ar",
        str(SAMPLE_RATE),
        "-ch_layout",
        spec.layout,
        "-i",
        "pipe:0",
        "-af",
        limiter,
        "-c:a",
        _ENCODERS[spec.codec],
    ]
    if spec.bitrate is not None and spec.codec != Codec.flac:
        command += ["-b:a", spec.bitrate]
    return [*command, "-f", "matroska", str(spec.output)]


def choose_container(source: Path, codecs: Iterable[Codec]) -> Container:
    """Keep the source container when it can hold the new codecs, otherwise use Matroska."""
    suffix = source.suffix.lower()
    used = set(codecs)
    if suffix in _MP4_INPUTS and used <= _MP4_CODECS:
        return Container(extension=suffix, muxer=_MP4_INPUTS[suffix])
    if suffix == ".webm" and used <= {Codec.opus}:
        return Container(extension=suffix, muxer="webm")
    extension = suffix if suffix in _MATROSKA_INPUTS - {".mka"} else ".mkv"
    return Container(extension=extension, muxer="matroska")


def mux_command(  # noqa: PLR0913 - every argument shapes the ffmpeg command
    tools: Tools,
    source: Path,
    tracks: Sequence[NewTrack],
    output: Path,
    container: Container,
    *,
    source_audio_count: int,
    set_default: bool,
) -> list[str]:
    """Build an ffmpeg command that copies all source streams and appends the new tracks."""
    command = [tools.ffmpeg, "-nostdin", "-v", "error", "-y"]
    if source.suffix.lower() in _GENPTS_INPUTS:
        command += ["-fflags", "+genpts"]
    command += ["-i", str(source)]
    for track in tracks:
        command += ["-i", str(track.path)]

    maps = ["0:v?", "0:a?", "0:s?"]
    if container.is_matroska:
        maps.append("0:t?")
    maps += [f"{number}:a:0" for number in range(1, len(tracks) + 1)]
    for stream in maps:
        command += ["-map", stream]
    command += ["-c", "copy"]

    for offset, track in enumerate(tracks):
        selector = f"s:a:{source_audio_count + offset}"
        command += [f"-metadata:{selector}", f"title={track.title}"]
        command += [f"-metadata:{selector}", f"language={track.language or 'und'}"]
        if container.is_matroska:
            command += [f"-metadata:{selector}", f"PHMASTER={track.tag}"]
    if set_default and tracks:
        command += ["-disposition:a", "0", f"-disposition:a:{source_audio_count}", "default"]
    return [*command, "-f", container.muxer, str(output)]
