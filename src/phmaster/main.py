import sys

from pydantic import ValidationError

from phmaster.cli.app import app
from phmaster.config import get_settings
from phmaster.utils.console import get_console
from phmaster.utils.log import setup_logging

CONFIG_ERROR_EXIT_CODE = 2


def main() -> None:
    """Initialize logging and the console, then run the CLI."""
    try:
        settings = get_settings()
    except ValidationError as error:
        sys.stderr.write(f"Invalid configuration: {error}\n")
        sys.exit(CONFIG_ERROR_EXIT_CODE)
    setup_logging(settings.log)
    get_console()
    app()
