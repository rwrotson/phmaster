from unittest.mock import MagicMock, patch

import pytest
from typer import Exit

from cli_app.cli.callbacks.meta import summary_cb


def test_summary_cb_noop_when_false() -> None:
    summary_cb(v=False)


def test_summary_cb_prints_summary_and_exits() -> None:
    mock_meta = MagicMock()
    mock_meta.__getitem__ = MagicMock(return_value="A template CLI app.")
    mock_console = MagicMock()

    with (
        patch("cli_app.cli.callbacks.meta.get_project_meta", return_value=mock_meta),
        patch("cli_app.cli.callbacks.meta.get_console", return_value=mock_console),
        pytest.raises(Exit),
    ):
        summary_cb(v=True)

    mock_console.print.assert_called_once()
