import json
import logging
import logging.handlers
from pathlib import Path

import pytest

import cli_app.config.settings as settings_module
from cli_app.config import LogSettings
from cli_app.utils.log import _AppConsoleHandler, _AppFileHandler, setup_logging

_EXPECTED_HANDLER_COUNT = 2


def test_setup_logging_uses_platform_log_dir_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clean_root_logger: logging.Logger
) -> None:
    monkeypatch.setattr(settings_module, "user_log_path", lambda _: tmp_path / "platform")
    setup_logging(LogSettings())
    file_handler = next(h for h in clean_root_logger.handlers if isinstance(h, _AppFileHandler))
    assert Path(file_handler.baseFilename) == tmp_path / "platform" / "cli-app.log"


def test_setup_logging_reads_settings_when_called_without_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clean_root_logger: logging.Logger
) -> None:
    monkeypatch.setenv("CLI_APP_LOG__DIR", str(tmp_path))
    monkeypatch.setenv("CLI_APP_LOG__LEVEL", "ERROR")
    setup_logging()
    assert clean_root_logger.level == logging.ERROR
    assert (tmp_path / "cli-app.log").exists()


def test_setup_logging_creates_log_dir(tmp_path: Path, clean_root_logger: logging.Logger) -> None:
    _ = clean_root_logger
    log_dir = tmp_path / "logs"
    config = LogSettings(dir=log_dir)
    setup_logging(config)
    assert log_dir.exists()


def test_setup_logging_does_not_add_duplicate_handlers(
    tmp_path: Path, clean_root_logger: logging.Logger
) -> None:
    config = LogSettings(dir=tmp_path / "logs2")
    setup_logging(config)
    count_after_first = len(clean_root_logger.handlers)
    setup_logging(config)
    assert len(clean_root_logger.handlers) == count_after_first


def test_setup_logging_preserves_unrelated_handlers(
    tmp_path: Path, clean_root_logger: logging.Logger
) -> None:
    foreign_console = logging.StreamHandler()
    foreign_file = logging.handlers.RotatingFileHandler(tmp_path / "foreign.log")
    clean_root_logger.addHandler(foreign_console)
    clean_root_logger.addHandler(foreign_file)

    config = LogSettings(dir=tmp_path / "app")
    setup_logging(config)
    setup_logging(config)

    assert foreign_console in clean_root_logger.handlers
    assert foreign_file in clean_root_logger.handlers
    assert sum(isinstance(h, _AppFileHandler) for h in clean_root_logger.handlers) == 1
    assert sum(isinstance(h, _AppConsoleHandler) for h in clean_root_logger.handlers) == 1


def test_setup_logging_replaces_own_handlers_on_reconfiguration(
    tmp_path: Path, clean_root_logger: logging.Logger
) -> None:
    setup_logging(LogSettings(dir=tmp_path / "first"))
    previous_file = next(
        handler for handler in clean_root_logger.handlers if isinstance(handler, _AppFileHandler)
    )

    setup_logging(
        LogSettings(
            dir=tmp_path / "second",
            file_name="changed.log",
            file_level="DEBUG",
            console_level="WARNING",
            format="json",
        )
    )

    assert (
        sum(
            isinstance(h, (_AppFileHandler, _AppConsoleHandler)) for h in clean_root_logger.handlers
        )
        == _EXPECTED_HANDLER_COUNT
    )
    assert previous_file not in clean_root_logger.handlers
    assert previous_file.stream is None
    current_file = next(
        handler for handler in clean_root_logger.handlers if isinstance(handler, _AppFileHandler)
    )
    current_console = next(
        handler for handler in clean_root_logger.handlers if isinstance(handler, _AppConsoleHandler)
    )
    assert Path(current_file.baseFilename) == tmp_path / "second" / "changed.log"
    assert current_file.level == logging.DEBUG
    assert current_console.level == logging.WARNING

    clean_root_logger.warning("reconfigured")
    event = json.loads((tmp_path / "second" / "changed.log").read_text())
    assert event["event"] == "reconfigured"


def test_setup_logging_sets_root_level(tmp_path: Path, clean_root_logger: logging.Logger) -> None:
    config = LogSettings(dir=tmp_path / "logs3", level="WARNING")
    setup_logging(config)
    assert clean_root_logger.level == logging.WARNING


def test_setup_logging_adds_two_handlers(tmp_path: Path, clean_root_logger: logging.Logger) -> None:
    config = LogSettings(dir=tmp_path / "logs4")
    setup_logging(config)
    app_handlers = [
        h
        for h in clean_root_logger.handlers
        if isinstance(h, (_AppFileHandler, _AppConsoleHandler))
    ]
    assert len(app_handlers) == _EXPECTED_HANDLER_COUNT


def test_setup_logging_json_formatter(
    tmp_path: Path, clean_root_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    config = LogSettings(dir=tmp_path / "logs5", format="json")
    setup_logging(config)
    clean_root_logger.warning("json event")
    event = json.loads((config.resolved_dir / config.file_name).read_text())
    assert event["event"] == "json event"
    assert json.loads(capsys.readouterr().err)["event"] == "json event"
