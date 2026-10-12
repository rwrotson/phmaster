from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from phmaster.services.dsp.gain import GainApplier, GainPlan, plan_gain
from phmaster.services.dsp.loudness import (
    SAMPLE_RATE,
    BlockMeter,
    LoudnessEnvelope,
    channel_weights,
)
from phmaster.services.dsp.presets import Preset
from phmaster.services.errors import InvalidInputError, MediaError
from phmaster.services.media.commands import (
    Codec,
    DecodeSpec,
    EncodeSpec,
    decode_command,
    encode_command,
)
from phmaster.services.media.layouts import channel_names, has_center, kept_layout
from phmaster.services.media.pcm import PcmWriter, read_pcm
from phmaster.services.media.probe import AudioTrack, MediaInfo
from phmaster.services.media.tools import Tools

CHUNK_FRAMES = SAMPLE_RATE
_STEREO_CHANNELS = 2


class Layout(StrEnum):
    """Channel layouts to generate for each source track."""

    stereo = "stereo"
    keep = "keep"
    both = "both"


class CodecChoice(StrEnum):
    """Codec of generated tracks; `auto` picks AAC for stereo and E-AC-3 for surround."""

    auto = "auto"
    aac = "aac"
    eac3 = "eac3"
    ac3 = "ac3"
    opus = "opus"
    flac = "flac"


@dataclass(frozen=True, slots=True)
class TrackSelection:
    """Source tracks to process: audio indices and language codes; empty means all."""

    indices: tuple[int, ...] = ()
    languages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TrackFormat:
    """Layout, codec, and downmix options of generated tracks."""

    layout: Layout = Layout.stereo
    codec: CodecChoice = CodecChoice.auto
    stereo_bitrate: str = "256k"
    surround_bitrate: str = "640k"
    center_mix_db: float = 0.0


@dataclass(frozen=True, slots=True)
class Job:
    """One generated track: a source track rendered with a preset into a layout."""

    track: AudioTrack
    preset: Preset
    layout: str
    codec: Codec
    bitrate: str
    title_base: str | None = None

    @property
    def dialog_channel(self) -> bool:
        """Tell whether the decoder must add the source center channel for dialogue metering."""
        return has_center(self.track.layout) and "FC" not in channel_names(self.layout)

    @property
    def title(self) -> str:
        """Track title shown by players; its suffix identifies phmaster tracks and their source."""
        base = (
            self.title_base
            or self.track.title
            or self.track.language
            or f"Track {self.track.audio_index + 1}"
        )
        return f"{base} · phmaster {self.preset.name} ({self.layout}, a:{self.track.audio_index})"

    @property
    def tag(self) -> str:
        """Value of the PHMASTER tag written to Matroska outputs."""
        return f"{self.preset.name}:{self.layout}:{self.track.audio_index}"


class ProgressSink(Protocol):
    """Receives progress of long-running steps."""

    def stage(self, description: str, total: float | None) -> None:
        """Start a step that processes `total` seconds of audio."""

    def advance(self, seconds: float) -> None:
        """Report that more audio was processed."""


class NullProgress:
    """A progress sink that ignores all updates."""

    def stage(self, description: str, total: float | None) -> None:
        """Ignore the step."""

    def advance(self, seconds: float) -> None:
        """Ignore the update."""


def select_tracks(info: MediaInfo, selection: TrackSelection) -> list[AudioTrack]:
    """Return the source tracks to process, skipping tracks phmaster generated."""
    count = len(info.audio_tracks)
    for index in selection.indices:
        if not 0 <= index < count:
            raise InvalidInputError(
                f"{info.path.name}: no audio track a:{index} (file has {count})"
            )
    languages = {language.lower() for language in selection.languages}
    tracks = [
        track
        for track in info.audio_tracks
        if not track.is_generated
        and (not selection.indices or track.audio_index in selection.indices)
        and (not languages or (track.language or "").lower() in languages)
    ]
    if not tracks:
        raise MediaError(f"{info.path.name}: no audio tracks to process")
    return tracks


def plan_jobs(
    tracks: Sequence[AudioTrack],
    presets: Sequence[Preset],
    output: TrackFormat,
    *,
    title_base: str | None = None,
) -> list[Job]:
    """Expand tracks into jobs for every requested layout and preset."""
    jobs: list[Job] = []
    for track in tracks:
        for layout in _layouts(track, output.layout):
            codec, bitrate = _codec(layout, output)
            jobs.extend(
                Job(track, preset, layout, codec, bitrate, title_base) for preset in presets
            )
    return jobs


def _layouts(track: AudioTrack, layout: Layout) -> list[str]:
    kept = kept_layout(track.layout)
    if layout == Layout.stereo:
        return ["stereo"]
    if layout == Layout.keep or track.channels <= _STEREO_CHANNELS:
        return [kept]
    return ["stereo", kept]


def _codec(layout: str, output: TrackFormat) -> tuple[Codec, str]:
    surround = len(channel_names(layout)) > _STEREO_CHANNELS
    bitrate = output.surround_bitrate if surround else output.stereo_bitrate
    if output.codec == CodecChoice.auto:
        return (Codec.eac3 if surround else Codec.aac), bitrate
    return Codec(output.codec.value), bitrate


def _decode_spec(source: Path, job: Job, output: TrackFormat) -> DecodeSpec:
    return DecodeSpec(
        source=source,
        audio_index=job.track.audio_index,
        source_layout=job.track.layout,
        target_layout=job.layout,
        center_gain=10 ** (output.center_mix_db / 20),
        dialog_channel=job.dialog_channel,
    )


def measure(
    tools: Tools, source: Path, job: Job, output: TrackFormat, progress: ProgressSink
) -> LoudnessEnvelope:
    """Decode a job's track in its target layout and measure its loudness envelope."""
    spec = _decode_spec(source, job, output)
    names = channel_names(job.layout)
    weights = channel_weights(names)
    if job.dialog_channel:
        weights.append(0.0)
        dialog_index: int | None = len(names)
    else:
        dialog_index = names.index("FC") if "FC" in names else None
    meter = BlockMeter(weights, dialog_index)
    label = job.track.title or job.track.language or f"track {job.track.audio_index + 1}"
    progress.stage(f"Measuring {label} ({job.layout})", job.track.duration)
    with read_pcm(decode_command(tools, spec), spec.channels, CHUNK_FRAMES) as chunks:
        for frames in chunks:
            meter.feed(frames)
            progress.advance(len(frames) / SAMPLE_RATE)
    return meter.finish()


def render(  # noqa: PLR0913 - the render step needs the full job context
    tools: Tools,
    source: Path,
    job: Job,
    *,
    output: TrackFormat,
    plan: GainPlan,
    destination: Path,
    progress: ProgressSink,
) -> None:
    """Apply a planned gain to a job's track and encode the result to `destination`."""
    spec = _decode_spec(source, job, output)
    channels = len(channel_names(job.layout))
    applier = GainApplier(plan.gain)
    encode = EncodeSpec(
        output=destination,
        layout=job.layout,
        codec=job.codec,
        bitrate=job.bitrate,
        ceiling_db=job.preset.ceiling,
    )
    progress.stage(f"Rendering {job.title}", job.track.duration)
    with (
        PcmWriter(encode_command(tools, encode)) as writer,
        read_pcm(decode_command(tools, spec), spec.channels, CHUNK_FRAMES) as chunks,
    ):
        for frames in chunks:
            writer.write(applier.apply(frames, channels))
            progress.advance(len(frames) / SAMPLE_RATE)


def iter_plans(
    tools: Tools,
    source: Path,
    jobs: Sequence[Job],
    output: TrackFormat,
    progress: ProgressSink,
) -> Iterator[tuple[Job, LoudnessEnvelope, GainPlan]]:
    """Yield plans in job order, measuring each (track, layout) pair once."""
    last_use = {(job.track.audio_index, job.layout): index for index, job in enumerate(jobs)}
    envelopes: dict[tuple[int, str], LoudnessEnvelope] = {}
    for index, job in enumerate(jobs):
        key = (job.track.audio_index, job.layout)
        if key not in envelopes:
            envelopes[key] = measure(tools, source, job, output, progress)
        envelope = envelopes[key]
        plan = plan_gain(envelope, job.preset)
        yield job, envelope, plan
        if index == last_use[key]:
            del envelopes[key]
        del envelope, plan
