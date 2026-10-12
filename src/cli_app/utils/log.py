import logging
import logging.handlers
import sys
from typing import TextIO, cast

import structlog

from cli_app.config import LogSettings, load_settings


class _AppFileHandler(logging.handlers.RotatingFileHandler):
    """Mark file handlers for replacement when logging is reconfigured."""


class _AppConsoleHandler(logging.StreamHandler[TextIO]):
    """Mark console handlers for replacement when logging is reconfigured."""


def setup_logging(config: LogSettings | None = None) -> None:
    """Configure shared structlog and stdlib console and file handlers."""
    if config is None:
        config = load_settings().log

    logs_dir_path = config.resolved_dir.resolve()
    logs_dir_path.mkdir(parents=True, exist_ok=True)
    log_file_path = logs_dir_path / config.file_name

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

    fh = _AppFileHandler(
        filename=log_file_path,
        maxBytes=config.file_max_bytes,
        backupCount=config.file_backup_count,
    )
    fh.setLevel(config.file_level)
    fh.setFormatter(file_formatter)

    sh = _AppConsoleHandler(sys.stderr)
    sh.setLevel(config.console_level)
    sh.setFormatter(console_formatter)

    for handler in root_logger.handlers[:]:
        if isinstance(handler, (_AppFileHandler, _AppConsoleHandler)):
            root_logger.removeHandler(handler)
            handler.close()

    root_logger.addHandler(fh)
    root_logger.addHandler(sh)

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger() -> structlog.typing.FilteringBoundLogger:
    """Return a logger that writes to stderr before logging is configured."""
    return cast(structlog.typing.FilteringBoundLogger, structlog.get_logger())


# Keep early logs off stdout so JSON command output remains valid.
structlog.configure(
    logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=False,
)
