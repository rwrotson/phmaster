from collections.abc import Iterator
from contextlib import contextmanager

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from phmaster.cli.context import AppContext
from phmaster.services.pipeline import ProgressSink
from phmaster.utils.console import build_console
from phmaster.utils.output import OutputFormat


class RichProgressSink:
    """Show pipeline progress as a single Rich progress bar."""

    def __init__(self, progress: Progress) -> None:
        self._progress = progress
        self._task: TaskID | None = None

    def stage(self, description: str, total: float | None) -> None:
        """Restart the bar for a new step."""
        # Rich treats total=None as "unchanged" in reset(), so start a fresh task instead.
        if self._task is not None:
            self._progress.remove_task(self._task)
        self._task = self._progress.add_task(description, total=total)

    def advance(self, seconds: float) -> None:
        """Move the bar forward by the processed audio duration."""
        if self._task is not None:
            self._progress.advance(self._task, seconds)


@contextmanager
def progress_sink(app_context: AppContext) -> Iterator[ProgressSink]:
    """Yield a progress sink drawing on stderr; hidden for JSON output."""
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=build_console(app_context.settings.console, stderr=True),
        refresh_per_second=4,
        transient=True,
        disable=app_context.output_format == OutputFormat.json,
    )
    with progress:
        yield RichProgressSink(progress)
