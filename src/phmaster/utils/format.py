from functools import cache

from rich.style import Style
from rich.theme import Theme


@cache
def get_theme() -> Theme:
    """Return the Rich theme with info, warning, and danger styles."""
    return Theme(
        {
            "info": Style(
                color="cyan",
                dim=True,
                bold=True,
            ),
            "warning": Style(
                color="magenta",
                bold=True,
            ),
            "danger": Style(
                color="red",
                bold=True,
            ),
        },
    )
