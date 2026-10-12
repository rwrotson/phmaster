import json
from collections.abc import Callable
from enum import StrEnum
from typing import Any

import typer

from cli_app.utils.console import get_console


class OutputFormat(StrEnum):
    """Output format for CLI commands."""

    text = "text"
    json = "json"


def echo_json(data: dict[str, Any] | list[Any]) -> None:
    """Serialise *data* to JSON and write it to stdout."""
    typer.echo(json.dumps(data, indent=2, default=str))


def error_json(error_type: str, message: str) -> None:
    """Write an error object as JSON to stderr."""
    typer.echo(json.dumps({"error": {"type": error_type, "message": message}}), err=True)


def render_output(
    data: dict[str, Any] | list[Any],
    fmt: OutputFormat,
    *,
    text_render: Callable[[], None] | None = None,
) -> None:
    """Render JSON or use the supplied text renderer or Rich console."""
    if fmt == OutputFormat.json:
        echo_json(data)
    elif text_render is not None:
        text_render()
    else:
        get_console().print(data)
