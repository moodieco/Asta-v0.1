"""Scanner registry + discovery.

Two responsibilities:
  * map ``scanner.id`` -> scanner class (via :func:`register_scanner`),
  * discover scanner packages on disk and turn their ``config.yaml`` into
    :class:`ScannerConfig` objects.

Adding a scanner therefore means: drop a folder with ``scanner.py`` +
``config.yaml`` under ``markets/<market>/scanners/<ID>/``. No wiring needed.
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Type

import yaml

from asta.core.scanner_base import ScannerBase, ScannerConfig
from asta.utils.exceptions import ConfigurationError
from asta.utils.logger import get_logger

logger = get_logger("asta.registry")

#: LogRecord reserves names like "module", "name", "args"; using them in `extra`
#: raises KeyError while logging, which would mask the real import error.
_RESERVED_LOG_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime",
}


def log_discovery_error(name: str) -> None:
    """Report a package that failed to import during discovery (never raises)."""
    payload = {"package": name}
    payload = {key: value for key, value in payload.items() if key not in _RESERVED_LOG_KEYS}
    try:
        logger.error("package import failed during discovery", extra=payload)
    except Exception:  # noqa: BLE001 - discovery must keep going
        pass

#: Global class registry populated by ``@register_scanner``.
SCANNER_CLASSES: Dict[str, Type[ScannerBase]] = {}


def register_scanner(cls: Type[ScannerBase]) -> Type[ScannerBase]:
    """Class decorator: register a scanner under its ``id``."""
    scanner_id = getattr(cls, "id", "")
    if not scanner_id:
        raise ConfigurationError("{} has no id".format(cls.__name__))
    if getattr(cls, "market", None) is None:
        raise ConfigurationError("{} has no market".format(cls.__name__))
    existing = SCANNER_CLASSES.get(scanner_id)
    if existing is not None and existing is not cls:
        raise ConfigurationError(
            "duplicate scanner id {!r}: {} and {}".format(scanner_id, existing.__name__, cls.__name__)
        )
    SCANNER_CLASSES[scanner_id] = cls
    return cls


class ScannerRegistry:
    """Registry facade used by the application."""

    def __init__(self, classes: Optional[Dict[str, Type[ScannerBase]]] = None):
        self._classes: Dict[str, Type[ScannerBase]] = dict(classes or SCANNER_CLASSES)
        self._discovered_packages: List[str] = []

    # -- class registry ---------------------------------------------------
    @property
    def classes(self) -> Dict[str, Type[ScannerBase]]:
        return dict(self._classes)

    def register(self, cls: Type[ScannerBase]) -> Type[ScannerBase]:
        register_scanner(cls)
        self._classes[cls.id] = cls
        return cls

    def get_class(self, scanner_id: str) -> Type[ScannerBase]:
        try:
            return self._classes[scanner_id]
        except KeyError:
            raise ConfigurationError(
                "unknown scanner id {!r}; registered: {}".format(
                    scanner_id, ", ".join(sorted(self._classes)) or "<none>"
                )
            ) from None

    def ids(self) -> List[str]:
        return sorted(self._classes)

    # -- discovery --------------------------------------------------------
    def discover(self, packages: Iterable[str] = ("asta.markets",)) -> List[str]:
        """Import every ``scanner`` module below the given packages."""
        imported: List[str] = []
        for package_name in packages:
            package = importlib.import_module(package_name)

            for module_info in pkgutil.walk_packages(
                package.__path__, prefix=package_name + ".", onerror=log_discovery_error
            ):
                if not module_info.name.endswith(".scanner"):
                    continue
                try:
                    importlib.import_module(module_info.name)
                except Exception as exc:  # noqa: BLE001 - a broken scanner must not kill startup
                    logger.error(
                        "failed to import scanner module",
                        extra={"module": module_info.name, "error": str(exc)},
                    )
                    continue
                imported.append(module_info.name)
            self._discovered_packages.append(package_name)
        self._classes = dict(SCANNER_CLASSES)
        logger.info(
            "scanner discovery complete",
            extra={"modules": len(imported), "scanners": len(self._classes)},
        )
        return imported

    # -- configs ----------------------------------------------------------
    @staticmethod
    def scanner_root() -> Path:
        import asta.markets as markets_package

        return Path(list(markets_package.__path__)[0])

    @classmethod
    def config_paths(cls, root: Optional[Path] = None) -> List[Path]:
        base = Path(root) if root else cls.scanner_root()
        return sorted(base.glob("*/scanners/*/config.yaml"))

    @classmethod
    def load_configs(cls, root: Optional[Path] = None) -> Dict[str, ScannerConfig]:
        configs: Dict[str, ScannerConfig] = {}
        for path in cls.config_paths(root):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                raw.pop("scanner_id", None)
                raw.setdefault("id", path.parent.name)
                raw["source_path"] = str(path)
                config = ScannerConfig(**raw)
            except Exception as exc:  # noqa: BLE001 - surface bad config, keep going
                logger.error(
                    "invalid scanner config",
                    extra={"path": str(path), "error": str(exc)},
                )
                continue
            if config.id in configs:
                raise ConfigurationError("duplicate scanner config id {!r}".format(config.id))
            configs[config.id] = config
        return configs

    # -- user scanners (uploaded through the dashboard) --------------------
    def discover_user_scanners(self, root: Path) -> List[str]:
        """Import user ``scanner.py`` files from ``<root>/<market>/<ID>/``.

        Uploaded scanners live outside ``src/asta/markets/``, so they cannot be
        found by :meth:`discover`. Each file is imported by path under a synthetic
        module name; its ``@register_scanner`` decorator registers the class exactly
        like a built-in scanner.
        """
        imported: List[str] = []
        if not Path(root).is_dir():
            return imported
        for scanner_py in sorted(Path(root).glob("*/*/scanner.py")):
            scanner_id = scanner_py.parent.name
            market = scanner_py.parent.parent.name
            module_name = "asta_user_scanners.{}.{}".format(market, scanner_id)
            if module_name in sys.modules:
                continue
            try:
                spec = importlib.util.spec_from_file_location(module_name, scanner_py)
                if spec is None or spec.loader is None:
                    logger.error("cannot load user scanner", extra={"path": str(scanner_py)})
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            except Exception as exc:  # noqa: BLE001 - a broken scanner must not kill startup
                logger.error(
                    "failed to import user scanner module",
                    extra={"path": str(scanner_py), "error": str(exc)},
                )
                continue
            imported.append(module_name)
        self._classes = dict(SCANNER_CLASSES)
        return imported

    @classmethod
    def load_user_configs(cls, root: Path) -> Dict[str, ScannerConfig]:
        """Read ``<root>/<market>/<ID>/config.yaml`` into ScannerConfig objects."""
        configs: Dict[str, ScannerConfig] = {}
        if not Path(root).is_dir():
            return configs
        for path in sorted(Path(root).glob("*/*/config.yaml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                raw.pop("scanner_id", None)
                raw.setdefault("id", path.parent.name)
                raw["source_path"] = str(path)
                config = ScannerConfig(**raw)
            except Exception as exc:  # noqa: BLE001 - surface bad config, keep going
                logger.error(
                    "invalid user scanner config",
                    extra={"path": str(path), "error": str(exc)},
                )
                continue
            configs[config.id] = config
        return configs

    def create(self, config: ScannerConfig, overrides: Optional[Dict[str, object]] = None) -> ScannerBase:
        scanner_cls = self.get_class(config.id)
        if overrides:
            config = config.with_overrides(dict(overrides))
        return scanner_cls(config)

    def build_all(
        self,
        configs: Dict[str, ScannerConfig],
        overrides: Optional[Dict[str, Dict[str, object]]] = None,
    ) -> List[ScannerBase]:
        scanners: List[ScannerBase] = []
        for scanner_id, config in sorted(configs.items()):
            if scanner_id not in self._classes:
                logger.warning(
                    "config without scanner class, skipped",
                    extra={"scanner_id": scanner_id},
                )
                continue
            scanners.append(self.create(config, (overrides or {}).get(scanner_id)))
        return scanners
