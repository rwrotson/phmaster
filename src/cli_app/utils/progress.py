from collections.abc import Callable
from typing import Literal

from rich.console import Console
from rich.progress import Progress, ProgressColumn

from cli_app.utils.console import get_console


def generate_progress_bar(  # noqa: PLR0913 - mirrors rich.progress.Progress options
    *columns: str | ProgressColumn,
    console: Literal["internal", "project"] | Console = "project",
    auto_refresh: bool = True,
    refresh_per_second: float = 1,
    speed_estimate_period: float = 30.0,
    transient: bool = False,
    redirect_stdout: bool = True,
    redirect_stderr: bool = True,
    get_time: Callable[[], float] | None = None,
    disable: bool = False,
    expand: bool = False,
) -> Progress:
    """Build a Rich Progress bar with the project, internal, or supplied console."""
    resolved_console: Console | None
    if console == "project":
        resolved_console = get_console()
    elif console == "internal":
        resolved_console = None
    elif isinstance(console, Console):
        resolved_console = console
    else:
        raise RuntimeError("Incorrect console type")

    return Progress(
        *columns,
        console=resolved_console,
        auto_refresh=auto_refresh,
        refresh_per_second=refresh_per_second,
        speed_estimate_period=speed_estimate_period,
        transient=transient,
        redirect_stdout=redirect_stdout,
        redirect_stderr=redirect_stderr,
        get_time=get_time,
        disable=disable,
        expand=expand,
    )
