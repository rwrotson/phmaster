import sys

from pydantic import ValidationError

from cli_app.cli.app import app
from cli_app.config import load_settings
from cli_app.utils.console import get_console
from cli_app.utils.log import setup_logging

CONFIG_ERROR_EXIT_CODE = 2


def main() -> None:
    """Initialize logging and the console, then run the CLI."""
    try:
        settings = load_settings()
    except ValidationError as error:
        sys.stderr.write(f"Invalid configuration: {error}\n")
        sys.exit(CONFIG_ERROR_EXIT_CODE)
    setup_logging(settings.log)
    get_console()
    app()
