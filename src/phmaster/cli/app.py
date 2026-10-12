import logging
from typing import Annotated

from typer import Context, Option, Typer

from phmaster.cli.callbacks import meta as meta_callbacks
from phmaster.cli.commands import completion_app, probe_app, process_app
from phmaster.cli.context import AppContext
from phmaster.cli.errors import ServiceErrorGroup
from phmaster.config import load_settings
from phmaster.utils.console import get_console
from phmaster.utils.output import OutputFormat

app = Typer(cls=ServiceErrorGroup, help="Add smoothly loudness-normalized audio tracks to videos.")
app.add_typer(process_app)
app.add_typer(probe_app)
app.add_typer(completion_app, name="completion")


@app.callback()
def main(
    ctx: Context,
    version: Annotated[  # noqa: ARG001
        bool,
        Option(
            "--version",
            "-v",
            help="Show the application's version and exit.",
            callback=meta_callbacks.version_cb,
            is_eager=True,
        ),
    ] = False,
    authors: Annotated[  # noqa: ARG001
        bool,
        Option(
            "--authors",
            "-A",
            help="Show the application's authors contacts and exit.",
            callback=meta_callbacks.authors_cb,
            is_eager=True,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        Option(
            "--verbose",
            "-V",
            help="Enable verbose (DEBUG) logging.",
        ),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        Option(
            "--output-format",
            "-f",
            help="Output format.",
        ),
    ] = OutputFormat.text,
) -> None:
    """Create the invocation context and set the logging level for CLI commands."""
    ctx.obj = AppContext(
        settings=load_settings(), console=get_console(), output_format=output_format
    )
    if verbose:
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        for handler in root.handlers:
            handler.setLevel(logging.DEBUG)
