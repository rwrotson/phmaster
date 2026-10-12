from functools import cache

from rich.console import Console

from phmaster.config import ConsoleSettings, load_settings
from phmaster.utils.format import get_theme


def build_console(settings: ConsoleSettings, *, stderr: bool = False) -> Console:
    """Create a themed Rich console from console settings, writing to stdout or stderr."""
    return Console(theme=get_theme(), stderr=stderr, **settings.model_dump())


@cache
def get_console() -> Console:
    """Return the shared Rich console."""
    return build_console(load_settings().console)
