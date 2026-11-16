"""User-installed scanner library with a recycle bin.

Uploaded scanners are kept *separate* from the built-in scanners that ship in
``src/asta/markets/``. Directory layout under the library root (``data/scanners``
by default):

    <market>/<ID>/scanner.py      user scanner source (imported by the engine)
    <market>/<ID>/config.yaml     ScannerConfig the engine loads
    <market>/<ID>/manifest.json   install metadata + bundle provenance
    .trash/<ID>/…                 deleted scanners (moved, never erased)
    history.jsonl                 upload / uninstall / restore / purge events

"Delete" therefore *moves* a scanner folder into ``.trash/`` — reversible via
``restore`` and permanent only via ``purge``. Nothing is silently erased, which
is what lets Scanner Management offer a recycle bin.
"""

from __future__ import annotations

import base64
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from asta.utils.exceptions import ConfigurationError
from asta.utils.logger import get_logger

logger = get_logger("asta.scanner_library")

MARKET_PREFIX = {"stock": "STS", "crypto": "CXS", "forex": "FXS"}
VALID_MARKETS = set(MARKET_PREFIX)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([+-][\w.]+)?$")


def _now() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ScannerLibrary:
    """File-system manager for user-installed scanners and their recycle bin."""

    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser()
        self.trash_root = self.root / ".trash"
        self.history_path = self.root / "history.jsonl"

    # -- paths ------------------------------------------------------------
    def _installed_dir(self, market: str, scanner_id: str) -> Path:
        return self.root / market / scanner_id

    def _trash_dir(self, scanner_id: str) -> Path:
        return self.trash_root / scanner_id

    # -- manifest IO ------------------------------------------------------
    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    @staticmethod
    def _write_json(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(data, indent=2, sort_keys=True) + "\n"
        handle, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".manifest.", suffix=".tmp")
        try:
            with open(handle, "w", encoding="utf-8") as stream:
                stream.write(body)
            Path(tmp).replace(path)
        finally:
            if Path(tmp).exists():
                Path(tmp).unlink()

    def _append_history(self, event: Dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event.setdefault("at", _now())
        with self.history_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True, default=str) + "\n")

    # -- queries ----------------------------------------------------------
    def list_installed(self) -> List[Dict[str, Any]]:
        """Manifests of every installed user scanner, newest first."""
        records: List[Dict[str, Any]] = []
        if not self.root.is_dir():
            return records
        for market in sorted(self.root.iterdir()):
            if not market.is_dir() or market.name.startswith("."):
                continue
            for folder in sorted(market.iterdir()):
                manifest = self._read_json(folder / "manifest.json")
                if manifest:
                    manifest.setdefault("sourcePath", str(folder / "scanner.py"))
                    records.append(manifest)
        return sorted(records, key=lambda r: r.get("uploadedAt", ""), reverse=True)

    def list_trash(self) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        if not self.trash_root.is_dir():
            return records
        for folder in sorted(self.trash_root.iterdir()):
            manifest = self._read_json(folder / "manifest.json")
            if manifest:
                manifest.setdefault("sourcePath", str(folder / "scanner.py"))
                records.append(manifest)
        return sorted(records, key=lambda r: r.get("deletedAt", ""), reverse=True)

    def history(self, limit: int = 200) -> List[Dict[str, Any]]:
        if not self.history_path.is_file():
            return []
        rows: List[Dict[str, Any]] = []
        try:
            for line in self.history_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        except OSError:
            return []
        return list(reversed(rows[-limit:]))

    def find_installed(self, scanner_id: str) -> Optional[Dict[str, Any]]:
        for record in self.list_installed():
            if record.get("scannerId") == scanner_id:
                return record
        return None

    def find_trash(self, scanner_id: str) -> Optional[Dict[str, Any]]:
        for record in self.list_trash():
            if record.get("scannerId") == scanner_id:
                return record
        return None

    # -- id extraction ----------------------------------------------------
    @staticmethod
    def _extract_declared_id(source_text: str) -> Optional[str]:
        """Read the ``id = "…"`` a scanner class declares in its source."""
        match = re.search(r"\bid\s*=\s*[\"']([A-Za-z0-9_]+)[\"']", source_text)
        return match.group(1) if match else None

    # -- validation -------------------------------------------------------
    def _validate(self, market: str, name: str, version: str, source_name: str) -> None:
        if market not in VALID_MARKETS:
            raise ConfigurationError("unknown market {!r}".format(market))
        if not name or not name.strip():
            raise ConfigurationError("scanner name is required")
        if not SEMVER_RE.match(version or ""):
            raise ConfigurationError("version must be semantic (e.g. 0.1.0)")
        if not source_name:
            raise ConfigurationError("a source file is required")
        suffix = source_name.lower()
        if not (suffix.endswith(".py") or suffix.endswith(".zip")):
            raise ConfigurationError("bundle must be a .py or .zip file")

    # -- mutations --------------------------------------------------------
    def install(
        self,
        market: str,
        name: str,
        version: str,
        source: str,
        source_name: str,
        timeframes: Optional[List[str]] = None,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        changes: Optional[List[str]] = None,
        sha256: str = "",
    ) -> Dict[str, Any]:
        """Validate and install a scanner bundle, returning its manifest.

        The scanner's id comes from the ``id = "…"`` it declares in ``scanner.py``
        (that is the id ``@register_scanner`` registers), so the folder and the
        engine config use the same id and the engine picks the scanner up intact.
        """
        self._validate(market, name, version, source_name)
        timeframes = [tf for tf in (timeframes or []) if tf] or ["1h"]
        prefix = MARKET_PREFIX[market]

        archive = None
        py_names: List[str] = []
        if source_name.lower().endswith(".zip"):
            try:
                archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(source)))
            except (ValueError, zipfile.BadZipFile) as exc:
                raise ConfigurationError("invalid zip bundle: {}".format(exc)) from exc
            py_names = [n for n in archive.namelist() if n.endswith(".py") and "/" not in n]
            if not py_names:
                raise ConfigurationError("zip bundle has no scanner.py at its root")
            source_text = archive.read(py_names[0]).decode("utf-8")
        else:
            source_text = source
            if not source_text or not source_text.strip():
                raise ConfigurationError("scanner source is empty")

        scanner_id = self._extract_declared_id(source_text)
        if not scanner_id:
            raise ConfigurationError(
                "scanner.py must declare an id, e.g. id = \"{}001_MY_SCANNER\"".format(prefix)
            )
        if not scanner_id.startswith(prefix):
            raise ConfigurationError(
                "scanner id {!r} must start with {!r} for the {} market".format(scanner_id, prefix, market)
            )
        if self.find_installed(scanner_id) or self.find_trash(scanner_id):
            raise ConfigurationError("scanner id {!r} already exists".format(scanner_id))

        folder = self._installed_dir(market, scanner_id)
        if folder.exists():
            raise ConfigurationError("scanner folder already exists: {}".format(folder))
        folder.mkdir(parents=True, exist_ok=False)

        source_path = folder / "scanner.py"
        if archive is not None:
            archive.extractall(folder)
            extracted = folder / py_names[0]
            if extracted != source_path:
                extracted.rename(source_path)
        else:
            source_path.write_text(source_text, encoding="utf-8")

        size_bytes = source_path.stat().st_size
        config = {
            "id": scanner_id,
            "name": name.strip(),
            "market": market,
            "timeframe": timeframes[0],
            "enabled": True,
            "symbols": [],
            "params": {},
            "description": description.strip(),
        }
        (folder / "config.yaml").write_text(
            yaml.safe_dump(config, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

        record: Dict[str, Any] = {
            "id": "up_{}_{}".format(scanner_id.lower(), int(_now().replace("-", "").replace(":", "").replace("T", "").replace("Z", "")) % 100000),
            "scannerId": scanner_id,
            "name": name.strip(),
            "market": market,
            "version": version.strip(),
            "uploadedAt": _now(),
            "status": "installed",
            "enabled": True,
            "sizeBytes": size_bytes,
            "timeframes": timeframes,
            "description": description.strip(),
            "dependencies": list(dependencies or ["asta-core>=0.1"]),
            "changes": list(changes or ["Uploaded through the dashboard installer"]),
            "compatibility": "ASTA 0.1.x · core >= 0.1",
            "sha256": sha256,
            "sourceName": source_name,
            "sourcePath": str(source_path),
        }
        self._write_json(folder / "manifest.json", record)
        self._append_history(
            {
                "action": "install",
                "scannerId": scanner_id,
                "name": record["name"],
                "market": market,
                "version": record["version"],
                "detail": "installed from {}".format(source_name),
            }
        )
        logger.info("scanner installed", extra={"scanner_id": scanner_id, "market": market})
        return record

    def uninstall(self, scanner_id: str, reason: str = "") -> Dict[str, Any]:
        """Move an installed scanner into the recycle bin."""
        record = self.find_installed(scanner_id)
        if record is None:
            raise ConfigurationError("scanner {!r} is not installed".format(scanner_id))
        market = str(record.get("market", ""))
        source = self._installed_dir(market, scanner_id)
        target = self._trash_dir(scanner_id)
        if target.exists():
            raise ConfigurationError("a deleted copy of {!r} already exists".format(scanner_id))
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)

        record["status"] = "deleted"
        record["deletedAt"] = _now()
        record["deletedReason"] = reason or "removed from scanner management"
        self._write_json(target / "manifest.json", record)
        self._append_history(
            {
                "action": "uninstall",
                "scannerId": scanner_id,
                "name": record.get("name"),
                "market": market,
                "version": record.get("version"),
                "detail": record["deletedReason"],
            }
        )
        logger.info("scanner moved to recycle bin", extra={"scanner_id": scanner_id})
        return record

    def set_enabled(self, scanner_id: str, enabled: bool) -> Dict[str, Any]:
        """Flip ``enabled`` in a user scanner's config.yaml + manifest (restart to apply)."""
        record = self.find_installed(scanner_id)
        if record is None:
            raise ConfigurationError("scanner {!r} is not installed".format(scanner_id))
        market = str(record.get("market", ""))
        folder = self._installed_dir(market, scanner_id)
        config_path = folder / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        config["enabled"] = bool(enabled)
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        record["enabled"] = bool(enabled)
        self._write_json(folder / "manifest.json", record)
        self._append_history(
            {
                "action": "set-enabled",
                "scannerId": scanner_id,
                "name": record.get("name"),
                "market": market,
                "version": record.get("version"),
                "detail": "enabled" if enabled else "disabled",
            }
        )
        return record

    def restore(self, scanner_id: str) -> Dict[str, Any]:
        """Move a deleted scanner back out of the recycle bin."""
        record = self.find_trash(scanner_id)
        if record is None:
            raise ConfigurationError("no deleted scanner named {!r}".format(scanner_id))
        market = str(record.get("market", ""))
        target = self._installed_dir(market, scanner_id)
        if target.exists():
            raise ConfigurationError("an installed copy of {!r} already exists".format(scanner_id))
        source = self._trash_dir(scanner_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)

        record.pop("deletedAt", None)
        record.pop("deletedReason", None)
        record["status"] = "installed"
        record["restoredAt"] = _now()
        self._write_json(target / "manifest.json", record)
        self._append_history(
            {
                "action": "restore",
                "scannerId": scanner_id,
                "name": record.get("name"),
                "market": market,
                "version": record.get("version"),
                "detail": "restored from recycle bin",
            }
        )
        logger.info("scanner restored", extra={"scanner_id": scanner_id})
        return record

    def purge(self, scanner_id: str) -> Dict[str, Any]:
        """Permanently delete a scanner from the recycle bin."""
        record = self.find_trash(scanner_id)
        if record is None:
            raise ConfigurationError("no deleted scanner named {!r}".format(scanner_id))
        import shutil

        target = self._trash_dir(scanner_id)
        shutil.rmtree(target)
        self._append_history(
            {
                "action": "purge",
                "scannerId": scanner_id,
                "name": record.get("name"),
                "market": record.get("market"),
                "version": record.get("version"),
                "detail": "permanently deleted",
            }
        )
        logger.info("scanner purged", extra={"scanner_id": scanner_id})
        return {"scannerId": scanner_id, "purged": True}
