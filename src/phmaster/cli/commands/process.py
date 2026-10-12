import math
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from typer import Argument, Context, Option, Typer

from phmaster.cli.context import AppContext, get_app_context
from phmaster.cli.progress import progress_sink
from phmaster.config import ProcessingSettings
from phmaster.services.batch import FileFailure, discover, process_files
from phmaster.services.dsp.presets import PRESETS, Preset, PresetName
from phmaster.services.errors import InvalidInputError
from phmaster.services.media.tools import find_tools
from phmaster.services.normalize import NormalizeRequest, NormalizeResult
from phmaster.services.pipeline import CodecChoice, Layout, TrackFormat, TrackSelection
from phmaster.utils.log import get_logger
from phmaster.utils.output import OutputFormat, render_output

app = Typer()
log = get_logger()
_MIN_CENTER_MIX = -12.0
_MAX_CENTER_MIX = 12.0

PresetOption = Annotated[
    list[PresetName] | None,
    Option(
        "--preset", "-p", help="Preset to generate; repeat for several tracks.", show_default=False
    ),
]
LayoutOption = Annotated[
    Layout | None,
    Option(
        "--layout",
        "-l",
        help="stereo downmix, keep the source layout, or both.",
        show_default=False,
    ),
]
CodecOption = Annotated[
    CodecChoice | None,
    Option(
        "--codec",
        "-c",
        help="Codec of new tracks; auto is AAC for stereo, E-AC-3 for 5.1.",
        show_default=False,
    ),
]
TrackOption = Annotated[
    list[int] | None,
    Option(
        "--track", "-t", help="Audio track index (a:N in `probe`); repeatable.", show_default=False
    ),
]
LanguageOption = Annotated[
    list[str] | None,
    Option(
        "--lang",
        help="Process only tracks in this language (e.g. rus); repeatable.",
        show_default=False,
    ),
]
CenterMixOption = Annotated[
    float | None,
    Option(
        "--center-mix",
        help="Center (dialogue) level in stereo downmixes, dB.",
        min=_MIN_CENTER_MIX,
        max=_MAX_CENTER_MIX,
        show_default=False,
    ),
]


def resolve_presets(
    names: list[PresetName] | None, settings: ProcessingSettings
) -> tuple[Preset, ...]:
    """Return the requested presets, or the configured ones."""
    chosen = names or [PresetName(name) for name in settings.presets]
    return tuple(PRESETS[name] for name in dict.fromkeys(chosen))


def resolve_format(
    settings: ProcessingSettings,
    layout: Layout | None,
    codec: CodecChoice | None,
    center_mix: float | None,
) -> TrackFormat:
    """Combine command options with configured defaults."""
    if center_mix is not None and (
        not math.isfinite(center_mix) or not _MIN_CENTER_MIX <= center_mix <= _MAX_CENTER_MIX
    ):
        raise InvalidInputError("center mix must be between -12 and 12 dB")
    return TrackFormat(
        layout=layout or Layout(settings.layout),
        codec=codec or CodecChoice(settings.codec),
        stereo_bitrate=settings.stereo_bitrate,
        surround_bitrate=settings.surround_bitrate,
        center_mix_db=settings.center_mix_db if center_mix is None else center_mix,
    )


def resolve_selection(
    settings: ProcessingSettings, tracks: list[int] | None, languages: list[str] | None
) -> TrackSelection:
    """Combine track options with configured languages."""
    return TrackSelection(
        indices=tuple(tracks or ()), languages=tuple(languages or settings.languages)
    )


@app.command()
def process(  # noqa: PLR0913 - one parameter per command-line option
    ctx: Context,
    *,
    paths: Annotated[
        list[Path],
        Argument(help="Video files or directories.", metavar="PATH", show_default=False),
    ],
    preset: PresetOption = None,
    layout: LayoutOption = None,
    codec: CodecOption = None,
    track: TrackOption = None,
    lang: LanguageOption = None,
    center_mix: CenterMixOption = None,
    title: Annotated[
        str | None,
        Option("--title", help="Title for new tracks; keep earlier phmaster tracks with --force."),
    ] = None,
    recursive: Annotated[
        bool, Option("--recursive", "-r", help="Search directories recursively.")
    ] = False,
    in_place: Annotated[
        bool, Option("--in-place", help="Replace the source file instead of writing a copy.")
    ] = False,
    force: Annotated[
        bool,
        Option("--force", help="Process files that already have phmaster tracks or outputs."),
    ] = False,
    dry_run: Annotated[
        bool, Option("--dry-run", "-n", help="Show what would be generated without writing.")
    ] = False,
    set_default: Annotated[
        bool | None,
        Option(
            "--default/--no-default",
            help="Mark the first new track as default.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Add smoothly normalized audio tracks to video files."""
    app_context = get_app_context(ctx)
    settings = app_context.settings.processing
    tools = find_tools(settings.ffmpeg, settings.ffprobe)
    files = discover(paths, recursive=recursive, suffix=settings.suffix)
    if not files:
        raise InvalidInputError("no video files found")
    template = NormalizeRequest(
        source=files[0],
        presets=resolve_presets(preset, settings),
        track_format=resolve_format(settings, layout, codec, center_mix),
        selection=resolve_selection(settings, track, lang),
        suffix=settings.suffix,
        in_place=in_place,
        set_default=settings.set_default if set_default is None else set_default,
        force=force,
        dry_run=dry_run,
        title=title,
    )
    log.debug("processing files", count=len(files), presets=[p.name for p in template.presets])

    def report(outcome: NormalizeResult | FileFailure) -> None:
        if app_context.output_format == OutputFormat.text:
            print_outcome(app_context, outcome)

    with progress_sink(app_context) as sink:
        batch = process_files(tools, files, template, sink, on_result=report)

    if app_context.output_format == OutputFormat.json:
        render_output(
            {
                "results": [asdict(result) for result in batch.results],
                "failures": [failure_dict(failure) for failure in batch.failures],
            },
            app_context.output_format,
        )
    if batch.failures:
        raise typer.Exit(batch.exit_code)


def failure_dict(failure: FileFailure) -> dict[str, Any]:
    """Serialize a failed file for JSON output."""
    return {
        "path": str(failure.path),
        "error": {"type": type(failure.error).__name__, "message": str(failure.error)},
    }


def print_outcome(app_context: AppContext, outcome: NormalizeResult | FileFailure) -> None:
    """Print one processed, skipped, or failed file."""
    console = app_context.console
    if isinstance(outcome, FileFailure):
        typer.echo(f"Error: {outcome.path}: {outcome.error}", err=True)
        return
    name = escape(outcome.source.name)
    if outcome.skipped:
        console.print(f"[warning]skipped[/warning] {name}: {escape(outcome.skipped)}")
        return
    verb = "would write" if outcome.dry_run else "wrote"
    console.print(f"[info]{verb}[/info] {name} → {escape(outcome.output.name)}")
    print_tracks(console, outcome)


def print_tracks(console: Console, result: NormalizeResult) -> None:
    """Print the generated tracks of a file as a table."""
    table = Table(box=None, pad_edge=False)
    for column in ("source", "preset", "layout", "codec", "dialogue", "gain"):
        table.add_column(column)
    for track in result.tracks:
        dialogue = "—" if track.reference is None else f"{track.reference:.1f} LUFS"
        gain = "—"
        if track.min_gain is not None and track.max_gain is not None:
            gain = f"{track.min_gain:+.1f} … {track.max_gain:+.1f} dB"
        table.add_row(
            f"a:{track.source_index}", track.preset, track.layout, track.codec, dialogue, gain
        )
    console.print(table)
