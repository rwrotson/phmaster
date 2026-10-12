import pytest
from rich.console import Console

from phmaster.config import ConsoleSettings
from phmaster.utils.console import build_console, get_console


def test_build_console_applies_settings() -> None:
    console = build_console(ConsoleSettings(width=120, no_color=True, quiet=True))
    assert console.width == 120
    assert console.no_color is True
    assert console.quiet is True


def test_build_console_uses_project_theme() -> None:
    console = build_console(ConsoleSettings())
    assert console.get_style("danger").color is not None


def test_get_console_returns_console_instance() -> None:
    assert isinstance(get_console(), Console)


def test_get_console_is_cached() -> None:
    assert get_console() is get_console()


def test_get_console_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHMASTER_CONSOLE__WIDTH", "77")
    assert get_console().width == 77
