from dataclasses import dataclass

import typer
from rich.console import Console

from cli_app.config import Settings
from cli_app.utils.output import OutputFormat


@dataclass(frozen=True, slots=True)
class AppContext:
    """Hold the settings, console, and output format of one CLI invocation."""

    settings: Settings
    console: Console
    output_format: OutputFormat


def get_app_context(ctx: typer.Context) -> AppContext:
    """Return the context created by the root callback."""
    app_context = ctx.find_object(AppContext)
    if app_context is None:
        raise RuntimeError("AppContext is missing; invoke commands through the root app")
    return app_context
