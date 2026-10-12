import pytest
from rich.console import Console

from cli_app.utils.console import get_console
from cli_app.utils.progress import generate_progress_bar


def test_generate_progress_bar_uses_shared_console() -> None:
    bar = generate_progress_bar(console="project")
    assert bar.console is get_console()


def test_generate_progress_bar_internal_console_is_distinct() -> None:
    bar = generate_progress_bar(console="internal")
    assert bar.console is not get_console()


def test_generate_progress_bar_uses_supplied_console() -> None:
    console = Console()
    bar = generate_progress_bar(console=console)
    assert bar.console is console


def test_generate_progress_bar_invalid_console_raises() -> None:
    with pytest.raises(RuntimeError, match="Incorrect console type"):
        generate_progress_bar(console="invalid")  # type: ignore[arg-type]
