"""Logging setup shared by every ASTA component.

Console + optional rotating file handler. ``format: json`` emits one JSON
object per line (journald/grep friendly).
"""

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_CONFIGURED = False
_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


class TextFormatter(logging.Formatter):
    default_format = "%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s"

    def __init__(self, fmt: Optional[str] = None, datefmt: str = "%Y-%m-%d %H:%M:%S"):
        super().__init__(fmt or self.default_format, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = get_extra_fields(record)
        if extras:
            line += " | " + " ".join("{}={}".format(k, v) for k, v in extras.items())
        return line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(get_extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_extra_fields(record: logging.LogRecord) -> Dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED and not key.startswith("_")
    }


def configure_logging(
    level: str = "INFO",
    fmt: Optional[str] = None,
    logger_levels: Optional[Dict[str, str]] = None,
    log_file: Optional[str] = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
    force: bool = False,
) -> None:
    global _CONFIGURED
    if _CONFIGURED and not force:
        return
    fmt = (fmt or os.getenv("ASTA_LOG_FORMAT", "text")).lower()
    formatter = JsonFormatter() if fmt == "json" else TextFormatter()

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file:
        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)

    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    for name, logger_level in (logger_levels or {}).items():
        logging.getLogger(name).setLevel(getattr(logging, str(logger_level).upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
