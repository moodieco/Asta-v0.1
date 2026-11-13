"""Small logging setup shared by every ASTA component.

One formatter, one stream handler, no third-party logging dependency.
Set ``ASTA_LOG_FORMAT=json`` for line-delimited JSON (nice for journals).
"""

import json
import logging
import os
import sys
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


def configure_logging(level: str = "INFO", fmt: Optional[str] = None, force: bool = False) -> None:
    global _CONFIGURED
    if _CONFIGURED and not force:
        return
    fmt = fmt or os.getenv("ASTA_LOG_FORMAT", "text")
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt.lower() == "json" else TextFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
