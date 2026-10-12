import logging
import logging.handlers
import sys
from pathlib import Path
from typing import TextIO, cast

import structlog

from phmaster.config import LogSettings, get_settings


class _AppFileHandler(logging.handlers.RotatingFileHandler):
    """Mark file handlers for replacement when logging is reconfigured."""


class _AppConsoleHandler(logging.StreamHandler[TextIO]):
    """Mark console handlers for replacement when logging is reconfigured."""


def setup_logging(config: LogSettings | None = None) -> None:
    """Configure shared structlog and stdlib console and file handlers.

    If the log file cannot be opened, only console logging is set up and a warning is logged.
    """
    if config is None:
        config = get_settings().log

    log_file_path = config.resolved_dir.resolve() / config.file_name

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    console_renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if config.format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    file_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            console_renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(config.level)

    file_error: OSError | None = None
    fh: _AppFileHandler | None = None
    try:
        fh = _file_handler(config, log_file_path, file_formatter)
    except OSError as error:
        file_error = error

    sh = _AppConsoleHandler(sys.stderr)
    sh.setLevel(config.console_level)
    sh.setFormatter(console_formatter)

    for handler in root_logger.handlers[:]:
        if isinstance(handler, (_AppFileHandler, _AppConsoleHandler)):
            root_logger.removeHandler(handler)
            handler.close()

    if fh is not None:
        root_logger.addHandler(fh)
    root_logger.addHandler(sh)

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    if file_error is not None:
        get_logger().warning(
            "file logging disabled", path=str(log_file_path), error=str(file_error)
        )


def _file_handler(config: LogSettings, path: Path, formatter: logging.Formatter) -> _AppFileHandler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = _AppFileHandler(
        filename=path, maxBytes=config.file_max_bytes, backupCount=config.file_backup_count
    )
    handler.setLevel(config.file_level)
    handler.setFormatter(formatter)
    return handler


def get_logger() -> structlog.typing.FilteringBoundLogger:
    """Return a logger that writes to stderr before logging is configured."""
    return cast(structlog.typing.FilteringBoundLogger, structlog.get_logger())


# Keep early logs off stdout so JSON command output remains valid.
structlog.configure(
    logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=False,
)
