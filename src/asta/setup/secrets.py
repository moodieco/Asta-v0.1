"""Secret handling for Quick Setup.

Secrets live in ``.env`` only (never YAML, never JSON state). The file is written
atomically with ``0600`` permissions, and every value that leaves this module for
display is masked first.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ENV_FILENAME = ".env"
ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def read_env(path: Path | str) -> Dict[str, str]:
    target = Path(path).expanduser()
    values: Dict[str, str] = {}
    if not target.exists():
        return values
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def mask(value: Optional[str], keep: int = 4) -> str:
    """``abcd...wxyz`` -> ``••••wxyz``. Short values are fully hidden."""
    if not value:
        return ""
    text = str(value)
    if len(text) <= keep + 2:
        return "•" * len(text)
    return "•" * 8 + text[-keep:]


def mask_env(values: Dict[str, str]) -> Dict[str, str]:
    return {key: mask(value) for key, value in values.items()}


def is_configured(value: Optional[str]) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    return lowered not in ("", "your-local-mcp-token", "your-marketdata-token", "xxx", "changeme")


def _format_assignment(key: str, value: str) -> str:
    if value == "" or re.search(r"[\s#\"']", value):
        return '{}="{}"'.format(key, value.replace('"', '\\"'))
    return "{}={}".format(key, value)


def render_env(existing: str, updates: Dict[str, str]) -> str:
    """Merge ``updates`` into an env file body, preserving comments and order."""
    lines = existing.splitlines()
    pending = dict(updates)
    for index, raw in enumerate(lines):
        match = ASSIGNMENT.match(raw)
        if not match:
            continue
        key = match.group(1)
        if key in pending:
            lines[index] = _format_assignment(key, pending.pop(key))
    if pending:
        if lines and lines[-1].strip():
            lines.append("")
        for key, value in pending.items():
            lines.append(_format_assignment(key, value))
    return "\n".join(lines) + "\n"


def write_env(path: Path | str, updates: Dict[str, str]) -> Path:
    """Merge and write ``.env`` atomically, then force ``0600``."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    body = render_env(existing, updates)

    handle, temp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(body)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    if target.stat().st_mode & 0o777 != 0o600:
        os.chmod(target, 0o600)
    return target


def missing_keys(env: Dict[str, str], keys: Iterable[str]) -> List[str]:
    return [key for key in keys if not is_configured(env.get(key))]
