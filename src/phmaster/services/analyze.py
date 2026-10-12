import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from phmaster.services.dsp.loudness import integrated_loudness, loudness_range
from phmaster.services.dsp.presets import Preset
from phmaster.services.media.probe import MediaInfo, probe
from phmaster.services.media.tools import Tools
from phmaster.services.pipeline import (
    NullProgress,
    ProgressSink,
    TrackFormat,
    TrackSelection,
    plan_all,
    plan_jobs,
    select_tracks,
)

_PEAK_FLOOR = 1e-10


@dataclass(frozen=True, slots=True)
class PresetEstimate:
    """Planned gain of one preset for a measured track."""

    preset: str
    static_gain: float
    min_gain: float
    max_gain: float


@dataclass(frozen=True, slots=True)
class TrackReport:
    """Loudness statistics of a source track in one target layout."""

    audio_index: int
    layout: str
    integrated: float | None
    loudness_range: float
    peak_db: float
    reference: float | None
    estimates: tuple[PresetEstimate, ...]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Loudness statistics and planned gains of the selected tracks of a file."""

    info: MediaInfo
    reports: tuple[TrackReport, ...] = field(default=())


def analyze_file(  # noqa: PLR0913 - mirrors the options of the process command
    tools: Tools,
    path: Path,
    *,
    presets: Sequence[Preset],
    track_format: TrackFormat,
    selection: TrackSelection,
    progress: ProgressSink | None = None,
) -> AnalysisResult:
    """Measure the selected tracks and estimate the gain each preset would apply."""
    info = probe(tools, path)
    jobs = plan_jobs(select_tracks(info, selection), presets, track_format)
    planned = plan_all(tools, path, jobs, track_format, progress or NullProgress())
    reports: dict[tuple[int, str], TrackReport] = {}
    for job, envelope, plan in planned:
        key = (job.track.audio_index, job.layout)
        report = reports.get(key) or TrackReport(
            audio_index=job.track.audio_index,
            layout=job.layout,
            integrated=integrated_loudness(envelope.program),
            loudness_range=loudness_range(envelope.program),
            peak_db=20 * math.log10(max(envelope.peak, _PEAK_FLOOR)),
            reference=plan.reference,
            estimates=(),
        )
        estimate = PresetEstimate(job.preset.name, plan.static_gain, plan.min_gain, plan.max_gain)
        reports[key] = replace(report, estimates=(*report.estimates, estimate))
    return AnalysisResult(info=info, reports=tuple(reports.values()))
