import io
import sys

import pytest

from cli_app.utils.stdin import (
    is_stdin_piped,
    iter_stdin_lines,
    read_stdin,
    read_stdin_if_piped,
)


def test_is_stdin_piped_returns_false_for_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert is_stdin_piped() is False


def test_is_stdin_piped_returns_true_for_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert is_stdin_piped() is True


def test_read_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("hello world"))
    assert read_stdin() == "hello world"


def test_iter_stdin_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("line1\nline2\nline3\n"))
    assert list(iter_stdin_lines()) == ["line1", "line2", "line3"]


def test_read_stdin_if_piped_returns_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("piped content"))
    assert read_stdin_if_piped() == "piped content"


@pytest.mark.parametrize(
    ("piped", "expected"),
    [("hi\n", "hi"), ("hi\r\n", "hi"), ("a\nb\n\n", "a\nb"), ("  hi  \n", "  hi  "), ("\n", "")],
)
def test_read_stdin_if_piped_strips_trailing_line_breaks(
    monkeypatch: pytest.MonkeyPatch, piped: str, expected: str
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(piped))
    assert read_stdin_if_piped() == expected


def test_read_stdin_keeps_trailing_newline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("hi\n"))
    assert read_stdin() == "hi\n"


def test_read_stdin_if_piped_returns_none_for_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert read_stdin_if_piped() is None
