from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from typer import Argument, Context, Option, Typer

from phmaster.cli.commands.process import (
    CenterMixOption,
    LanguageOption,
    LayoutOption,
    PresetOption,
    TrackOption,
    resolve_format,
    resolve_presets,
    resolve_selection,
)
from phmaster.cli.context import get_app_context
from phmaster.cli.progress import progress_sink
from phmaster.services.analyze import AnalysisResult, analyze_file
from phmaster.services.media.probe import MediaInfo, probe
from phmaster.services.media.tools import find_tools
from phmaster.utils.output import render_output

app = Typer()


@app.command("probe")
def probe_command(  # noqa: PLR0913 - one parameter per command-line option
    ctx: Context,
    *,
    path: Annotated[Path, Argument(help="Video file.", metavar="FILE", show_default=False)],
    loudness: Annotated[
        bool,
        Option("--loudness", "-L", help="Measure loudness and estimate the gain of each preset."),
    ] = False,
    preset: PresetOption = None,
    layout: LayoutOption = None,
    track: TrackOption = None,
    lang: LanguageOption = None,
    center_mix: CenterMixOption = None,
) -> None:
    """List the audio tracks of a video file, optionally with loudness statistics."""
    app_context = get_app_context(ctx)
    settings = app_context.settings.processing
    tools = find_tools(settings.ffmpeg, settings.ffprobe)
    if not loudness:
        info = probe(tools, path)
        render_output(
            asdict(info),
            app_context.output_format,
            text_render=lambda: print_tracks(app_context.console, info),
        )
        return
    with progress_sink(app_context) as sink:
        result = analyze_file(
            tools,
            path,
            presets=resolve_presets(preset, settings),
            track_format=resolve_format(settings, layout, None, center_mix),
            selection=resolve_selection(settings, track, lang),
            progress=sink,
        )
    render_output(
        asdict(result),
        app_context.output_format,
        text_render=lambda: print_analysis(app_context.console, result),
    )


def print_tracks(console: Console, info: MediaInfo) -> None:
    """Print the audio tracks of a file as a table."""
    console.print(f"[info]{escape(info.path.name)}[/info] ({escape(info.format_name)})")
    table = Table(box=None, pad_edge=False)
    for column in ("track", "codec", "layout", "language", "title", "duration", "phmaster"):
        table.add_column(column)
    for track in info.audio_tracks:
        table.add_row(
            f"a:{track.audio_index}",
            track.codec,
            track.layout or f"{track.channels} ch",
            track.language or "—",
            escape(track.title or "—"),
            "—" if track.duration is None else _duration(track.duration),
            "yes" if track.is_generated else "",
        )
    console.print(table)


def print_analysis(console: Console, result: AnalysisResult) -> None:
    """Print loudness statistics and preset gain estimates as a table."""
    console.print(f"[info]{escape(result.info.path.name)}[/info]")
    table = Table(box=None, pad_edge=False)
    for column in ("track", "layout", "integrated", "LRA", "peak", "dialogue", "preset gains"):
        table.add_column(column)
    for report in result.reports:
        gains = ", ".join(
            f"{e.preset} {e.min_gain:+.1f}…{e.max_gain:+.1f}" for e in report.estimates
        )
        table.add_row(
            f"a:{report.audio_index}",
            report.layout,
            _lufs(report.integrated),
            f"{report.loudness_range:.1f} LU",
            f"{report.peak_db:.1f} dBFS",
            _lufs(report.reference),
            gains + " dB",
        )
    console.print(table)


def _lufs(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} LUFS"


def _duration(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{secs:02}"
