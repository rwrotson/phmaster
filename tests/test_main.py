import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from phmaster.main import CONFIG_ERROR_EXIT_CODE, main


def test_main_calls_startup_sequence() -> None:
    with (
        patch("phmaster.main.setup_logging") as mock_logging,
        patch("phmaster.main.get_console") as mock_console,
        patch("phmaster.main.app") as mock_app,
    ):
        main()
        mock_logging.assert_called_once()
        mock_console.assert_called_once()
        mock_app.assert_called_once()


def test_no_app_variables_leak_into_tests() -> None:
    assert not [name for name in os.environ if name.startswith("PHMASTER_")]


def test_main_runs_without_usable_log_dir(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    clean_root_logger: logging.Logger,
) -> None:
    _ = clean_root_logger
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("PHMASTER_LOG__DIR", str(blocker))
    monkeypatch.setattr(sys, "argv", ["phmaster", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 0
    captured = capsys.readouterr()
    assert "Usage" in captured.out
    assert "file logging disabled" in captured.err


def test_main_rejects_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PHMASTER_LOG__LEVEL", "LOUD")
    with patch("phmaster.main.app") as mock_app, pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == CONFIG_ERROR_EXIT_CODE
    assert "log.level" in capsys.readouterr().err
    mock_app.assert_not_called()
