"""Comment-preserving edits to the config YAML files.

The wizard changes a handful of scalars (``web.port``, ``markets.<m>.enabled``,
``scanner_overrides.<ID>.enabled``, ``storage.sqlite_path``). Dumping the parsed
document back would delete every comment, so edits are done line-by-line and the
result is re-parsed with PyYAML before it is allowed to touch disk.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from asta.utils.exceptions import ConfigurationError

KEY_LINE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.\-]+)\s*:(?P<rest>.*)$")


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or re.search(r"[:#\[\]{}&*!|>'\"%@`,\s]", text):
        return '"{}"'.format(text.replace('"', '\\"'))
    return text


def _split_rest(rest: str) -> Tuple[str, str]:
    """Split ``" 4310    # comment"`` into ``("4310", "    # comment")``."""
    stripped = rest.lstrip()
    if not stripped:
        return "", ""
    match = re.search(r"\s+#", stripped)
    if match:
        return stripped[: match.start()].rstrip(), stripped[match.start() :]
    return stripped, ""


def _is_content(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


class YamlFile:
    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        self.lines: List[str] = (
            self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else []
        )
        self.changed = False

    # -- lookup -----------------------------------------------------------
    def _block_end(self, start: int, indent: int) -> int:
        index = start + 1
        while index < len(self.lines):
            line = self.lines[index]
            if not _is_content(line):
                index += 1
                continue
            if _indent(line) <= indent:
                break
            index += 1
        return index

    def _find_child(self, key: str, start: int, end: int, indent: int) -> Optional[int]:
        for index in range(start, end):
            line = self.lines[index]
            if not _is_content(line):
                continue
            match = KEY_LINE.match(line)
            if match and _indent(line) == indent and match.group("key") == key:
                return index
        return None

    def _find_top(self, key: str) -> Optional[int]:
        return self._find_child(key, 0, len(self.lines), 0)

    # -- editing ----------------------------------------------------------
    def set(self, keys: List[str], value: Any) -> bool:
        if not keys:
            raise ValueError("keys must not be empty")
        index = self._find_top(keys[0])
        if index is None:
            return self._append_block(keys, value)

        check = self.lines[index]
        for depth, key in enumerate(keys[1:], start=1):
            end = self._block_end(index, _indent(check))
            child = self._find_child(key, index + 1, end, _indent(check) + 2)
            if child is None:
                return self._insert_child(index, key, value, keys[depth + 1 :])
            index = child
            check = self.lines[index]

        match = KEY_LINE.match(self.lines[index])
        if match is None:
            raise ConfigurationError("unexpected YAML shape at {}".format(self.path))
        _, comment = _split_rest(match.group("rest"))
        head = "{}{}:".format(match.group("indent"), match.group("key"))
        newline = "{} {}".format(head, format_value(value))
        if comment:
            newline += " " + comment.strip()
        self.lines[index] = newline
        self.changed = True
        return True

    def _insert_child(self, parent_index: int, key: str, value: Any, remaining: List[str]) -> bool:
        parent_indent = _indent(self.lines[parent_index])
        indent = parent_indent + 2
        new_lines = []
        current_key = key
        current_value: Any = value
        for depth, extra in enumerate(remaining):
            new_lines.append("{}{}:".format(" " * (indent + depth * 2), current_key))
            current_key = extra
        if remaining:
            new_lines.append("{}{}: {}".format(" " * (indent + len(remaining) * 2), current_key, format_value(current_value)))
        else:
            new_lines.append("{}{}: {}".format(" " * indent, current_key, format_value(current_value)))
        self.lines[parent_index + 1 : parent_index + 1] = new_lines
        self.changed = True
        return True

    def _append_block(self, keys: List[str], value: Any) -> bool:
        if self.lines and self.lines[-1].strip():
            self.lines.append("")
        for depth, key in enumerate(keys):
            indent = " " * (depth * 2)
            if depth == len(keys) - 1:
                self.lines.append("{}{}: {}".format(indent, key, format_value(value)))
            else:
                self.lines.append("{}{}:".format(indent, key))
        self.changed = True
        return True

    # -- persistence ------------------------------------------------------
    def dumps(self) -> str:
        return "\n".join(self.lines) + "\n"

    def write(self) -> Path:
        body = self.dumps()
        try:
            yaml.safe_load(body)
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            raise ConfigurationError("edit would break {}: {}".format(self.path, exc)) from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(body, encoding="utf-8")
        return self.path


def set_market_enabled(markets_yaml: Path | str, market: str, enabled: bool) -> YamlFile:
    document = YamlFile(markets_yaml)
    document.set(["markets", market, "enabled"], bool(enabled))
    return document


def set_scanner_enabled(markets_yaml: Path | str, scanner_id: str, enabled: bool) -> YamlFile:
    document = YamlFile(markets_yaml)
    document.set(["scanner_overrides", scanner_id, "enabled"], bool(enabled))
    return document


def set_web(app_yaml: Path | str, host: Optional[str] = None, port: Optional[int] = None) -> YamlFile:
    document = YamlFile(app_yaml)
    if host:
        document.set(["web", "host"], host)
    if port is not None:
        document.set(["web", "port"], int(port))
    return document


def set_sqlite_path(app_yaml: Path | str, path: str) -> YamlFile:
    document = YamlFile(app_yaml)
    document.set(["storage", "sqlite_path"], path)
    return document


def set_discord_labels(discord_yaml: Path | str, labels: Dict[str, str]) -> YamlFile:
    document = YamlFile(discord_yaml)
    for market, label in labels.items():
        document.set(["channels", market, "label"], label)
    return document
