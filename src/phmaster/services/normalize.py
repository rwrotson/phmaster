import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from phmaster.services.dsp.presets import Preset
from phmaster.services.errors import InvalidInputError, MediaError
from phmaster.services.media.commands import (
    Container,
    NewTrack,
    choose_container,
    encoder_name,
    mux_command,
)
from phmaster.services.media.probe import MediaInfo, probe
from phmaster.services.media.tools import Tools, require_encoders, run_tool
from phmaster.services.pipeline import (
    Job,
    NullProgress,
    ProgressSink,
    TrackFormat,
    TrackSelection,
    iter_plans,
    plan_jobs,
    render,
    select_tracks,
)


@dataclass(frozen=True, slots=True)
class NormalizeRequest:
    """What to generate for one media file and where to write it."""

    source: Path
    presets: tuple[Preset, ...]
    track_format: TrackFormat = field(default_factory=TrackFormat)
    selection: TrackSelection = field(default_factory=TrackSelection)
    suffix: str = ".phm"
    in_place: bool = False
    set_default: bool = True
    force: bool = False
    dry_run: bool = False
    title: str | None = None


@dataclass(frozen=True, slots=True)
class GeneratedTrack:
    """A normalized track added to the output, with its planned gain range."""

    source_index: int
    preset: str
    layout: str
    codec: str
    title: str
    reference: float | None = None
    static_gain: float | None = None
    min_gain: float | None = None
    max_gain: float | None = None


@dataclass(frozen=True, slots=True)
class NormalizeResult:
    """Outcome of processing one media file."""

    source: Path
    output: Path
    tracks: tuple[GeneratedTrack, ...] = ()
    skipped: str | None = None
    dry_run: bool = False


def output_path(source: Path, container: Container, suffix: str, *, in_place: bool) -> Path:
    """Return the output file: next to the source with a suffix, or the source itself."""
    if in_place:
        return source.with_suffix(container.extension)
    return source.with_name(f"{source.stem}{suffix}{container.extension}")


def normalize_file(
    tools: Tools, request: NormalizeRequest, progress: ProgressSink | None = None
) -> NormalizeResult:
    """Add normalized tracks to a copy of a media file, or to the file itself in place."""
    if request.title is not None and not request.title.strip():
        raise InvalidInputError("track title must not be empty")
    try:
        return _normalize(tools, request, progress or NullProgress())
    except OSError as error:
        raise MediaError(f"{request.source.name}: {error}") from error


def _normalize(tools: Tools, request: NormalizeRequest, sink: ProgressSink) -> NormalizeResult:
    info = probe(tools, request.source)
    jobs = plan_jobs(
        select_tracks(info, request.selection),
        request.presets,
        request.track_format,
        title_base=request.title,
    )
    container = choose_container(request.source, (job.codec for job in jobs))
    output = output_path(request.source, container, request.suffix, in_place=request.in_place)

    skipped = _skip_reason(info, output, request)
    if skipped or request.dry_run:
        tracks = tuple(_generated(job) for job in jobs)
        return NormalizeResult(
            request.source, output, tracks, skipped=skipped, dry_run=request.dry_run
        )

    require_encoders(tools, (encoder_name(job.codec) for job in jobs))
    titles = {job.title for job in jobs}
    replaced = (
        tuple(
            track.stream_index
            for track in info.audio_tracks
            if track.is_generated and track.title in titles
        )
        if request.force
        else ()
    )
    with tempfile.TemporaryDirectory(prefix=".phmaster-", dir=output.parent) as workdir:
        work = Path(workdir)
        new_tracks: list[NewTrack] = []
        generated: list[GeneratedTrack] = []
        for number, (job, envelope, plan) in enumerate(
            iter_plans(tools, request.source, jobs, request.track_format, sink)
        ):
            path = work / f"track{number}.mka"
            render(
                tools,
                request.source,
                job,
                output=request.track_format,
                plan=plan,
                destination=path,
                progress=sink,
            )
            new_tracks.append(
                NewTrack(path=path, title=job.title, language=job.track.language, tag=job.tag)
            )
            generated.append(
                _generated(job, plan.reference, plan.static_gain, plan.min_gain, plan.max_gain)
            )
            del envelope, plan
        sink.stage(f"Writing {output.name}", None)
        muxed = work / f"output{container.extension}"
        run_tool(
            mux_command(
                tools,
                request.source,
                new_tracks,
                muxed,
                container,
                source_audio_count=len(info.audio_tracks) - len(replaced),
                set_default=request.set_default,
                excluded_stream_indices=replaced,
            )
        )
        if request.in_place:
            shutil.copymode(request.source, muxed)
        if request.force or output == request.source:
            os.replace(muxed, output)
        elif not _publish_new(muxed, output):
            return NormalizeResult(
                request.source,
                output,
                tuple(generated),
                skipped=f"output exists: {output.name}",
            )
    if request.in_place and output != request.source:
        request.source.unlink()
    return NormalizeResult(request.source, output, tuple(generated))


def _publish_new(muxed: Path, output: Path) -> bool:
    """Move `muxed` to a new `output` path; False if another process created it first."""
    try:
        os.link(muxed, output)
    except FileExistsError:
        return False
    except OSError:
        # FAT, exFAT, and some network shares have no hard links: reserve the name with an
        # exclusive create, then replace the empty placeholder.
        try:
            os.close(os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            return False
        try:
            os.replace(muxed, output)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return True


def _skip_reason(info: MediaInfo, output: Path, request: NormalizeRequest) -> str | None:
    if request.force:
        return None
    if info.has_generated_tracks:
        return "already contains phmaster tracks"
    if output != request.source and output.exists():
        return f"output exists: {output.name}"
    return None


def _generated(
    job: Job,
    reference: float | None = None,
    static_gain: float | None = None,
    min_gain: float | None = None,
    max_gain: float | None = None,
) -> GeneratedTrack:
    return GeneratedTrack(
        source_index=job.track.audio_index,
        preset=job.preset.name,
        layout=job.layout,
        codec=job.codec.value,
        title=job.title,
        reference=reference,
        static_gain=static_gain,
        min_gain=min_gain,
        max_gain=max_gain,
    )
