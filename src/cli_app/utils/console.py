from functools import cache

from rich.console import Console

from cli_app.config import ConsoleSettings, load_settings
from cli_app.utils.format import get_theme


def build_console(settings: ConsoleSettings) -> Console:
    """Create a themed Rich console from console settings."""
    return Console(theme=get_theme(), **settings.model_dump())


@cache
def get_console() -> Console:
    """Return the shared Rich console."""
    return build_console(load_settings().console)
