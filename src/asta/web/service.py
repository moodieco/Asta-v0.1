"""Ties the dashboard server to a built :class:`AstaApp`.

One process, two threads: the scanner owns the asyncio loop in the main thread,
the dashboard owns its socket thread. Nothing here writes to the database.
"""

from __future__ import annotations

import json
import os
import re
import resource
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from asta.setup import secrets
from asta.setup.state import SetupState
from asta.utils.logger import get_logger
from asta.web.server import DashboardServer

logger = get_logger("asta.web.service")

LOG_LINE = re.compile(
    r"^(?P<at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(?P<level>[A-Z]+)\s*\|\s*"
    r"(?P<module>[^|]+?)\s*\|\s*(?P<message>.*)$"
)
TAIL_BYTES = 96 * 1024


class WebService:
    def __init__(
        self,
        app,
        web_dir: Optional[Path | str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        open_browser: bool = True,
    ):
        self.app = app
        config = app.config
        project_root = config.project_root
        web_cfg = getattr(config, "web", None)
        self.host = host or (getattr(web_cfg, "host", None) or "127.0.0.1")
        self.port = int(port or getattr(web_cfg, "port", None) or 4310)
        self.web_dir = Path(web_dir or project_root / "web" / "dist").expanduser()
        self.open_browser = open_browser
        self.root = Path(project_root).resolve()
        self.started_at = time.time()
        self._cpu_mark: Dict[str, float] = {"t": time.time(), "cpu": self._process_cpu_seconds()}
        self.server = DashboardServer(
            db_path=config.resolve_path(config.storage.sqlite_path),
            web_dir=self.web_dir,
            host=self.host,
            port=self.port,
            status_provider=self.status,
            config_summary=self.config_summary,
            setup_summary=self.setup_summary,
            system_snapshot=self.system_snapshot,
        )

    # -- lifecycle --------------------------------------------------------
    def start(self) -> str:
        url = self.server.start()
        if self.open_browser:
            threading.Thread(target=self._open_when_ready, name="asta-browser", daemon=True).start()
        return url

    def stop(self) -> None:
        self.server.stop()

    def _open_when_ready(self, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._healthy():
                try:
                    webbrowser.open(self.server.url)
                    logger.info("browser opened", extra={"url": self.server.url})
                except Exception:  # noqa: BLE001 - headless sessions have no browser
                    logger.warning("could not open a browser", extra={"url": self.server.url})
                return
            time.sleep(0.25)
        logger.warning("dashboard did not answer before the browser timeout")

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.server.url + "api/health", timeout=2) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    # -- data for /api/health and /api/config -----------------------------
    def status(self) -> Dict[str, Any]:
        app = self.app
        scheduler = getattr(app, "scheduler", None)
        analysis = getattr(app, "analysis", None)
        history = getattr(app, "history", None)
        scanners = 0
        enabled = 0
        try:
            if analysis is not None:
                scanners = len(analysis)
                enabled = len(analysis.enabled())
        except Exception:  # noqa: BLE001
            pass
        records = None
        try:
            records = history.count() if history is not None else None
        except Exception:  # noqa: BLE001
            pass
        return {
            "environment": app.config.environment,
            "dryRun": app.config.dry_run,
            "scanners": scanners,
            "enabledScanners": enabled,
            "cycles": getattr(scheduler, "cycles", None) if scheduler is not None else None,
            "lastCycleAt": getattr(scheduler, "last_cycle_at", None) if scheduler is not None else None,
            "storage": {
                "backend": app.config.storage.backend,
                "records": records,
            },
            "web": {"host": self.host, "port": self.port, "webDir": str(self.web_dir)},
        }

    def config_summary(self) -> Dict[str, Any]:
        """Everything a UI needs to describe the setup - never a secret."""
        config = self.app.config
        markets = {}
        for name, settings in (config.markets or {}).items():
            markets[name] = {
                "enabled": bool(getattr(settings, "enabled", False)),
                "symbols": len(getattr(settings, "symbols", []) or []),
            }
        scanners = []
        try:
            scanners = [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "market": item["market"],
                    "timeframe": item["timeframe"],
                    "enabled": item["enabled"],
                }
                for item in self.app.scanner_inventory()
            ]
        except Exception:  # noqa: BLE001
            pass
        providers = {}
        for market, settings in (config.providers or {}).items():
            if isinstance(settings, dict):
                providers[market] = {"type": settings.get("type", ""), "configured": True}
        return {
            "environment": config.environment,
            "dryRun": config.dry_run,
            "storage": {"backend": config.storage.backend},
            "web": {"host": self.host, "port": self.port},
            "markets": markets,
            "providers": providers,
            "scanners": scanners,
            "channels": sorted(
                channel.env for channel in (config.discord.channels or {}).values()
            ),
        }

    # -- setup state for the in-dashboard wizard --------------------------
    def setup_summary(self) -> Dict[str, Any]:
        """Real setup state: masked secrets only, never a webhook URL."""
        config = self.app.config
        state_path = config.resolve_path(config.setup.state_path)
        state = SetupState.load(state_path)
        env = secrets.read_env(self.root / ".env")

        webhooks: Dict[str, Any] = {}
        channels: List[Dict[str, Any]] = []
        for market, channel in (config.discord.channels or {}).items():
            value = env.get(channel.env, "")
            webhooks[market] = {
                "env": channel.env,
                "label": getattr(channel, "label", "") or "",
                "configured": secrets.is_configured(value),
                "masked": secrets.mask(value),
            }
            channels.append(
                {"market": market, "env": channel.env, "label": getattr(channel, "label", "") or ""}
            )

        providers: Dict[str, Any] = {}
        for market, settings in (config.providers or {}).items():
            if not isinstance(settings, dict):
                continue
            providers[market] = {
                "type": settings.get("type", ""),
                "configured": True,
                "terminalUrlConfigured": bool(settings.get("terminal_url")),
                "tokenConfigured": secrets.is_configured(
                    env.get("MT5_TERMINAL_TOKEN") or settings.get("terminal_token")
                ),
            }

        db_path = config.resolve_path(config.storage.sqlite_path)
        return {
            "available": True,
            "complete": state.complete,
            "completedAt": state.data.get("completed_at"),
            "updatedAt": state.data.get("updated_at"),
            "steps": {name: state.step(name) for name in ("discord", "providers", "scanners", "system", "review")},
            "completedSteps": state.completed_steps(),
            "webhooks": webhooks,
            "channels": channels,
            "providers": providers,
            "markets": {
                name: {
                    "enabled": bool(getattr(item, "enabled", False)),
                    "symbols": list(getattr(item, "symbols", []) or []),
                }
                for name, item in (config.markets or {}).items()
            },
            "scanners": self._inventory(),
            "system": {
                "dbPath": str(db_path),
                "dbExists": db_path.exists(),
                "host": self.host,
                "port": self.port,
                "environment": config.environment,
                "root": str(self.root),
            },
        }

    def _inventory(self) -> List[Dict[str, Any]]:
        try:
            return [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "market": item["market"],
                    "timeframe": item["timeframe"],
                    "enabled": item["enabled"],
                }
                for item in self.app.scanner_inventory()
            ]
        except Exception:  # noqa: BLE001 - the UI must render without the engine
            return []

    # -- system snapshot --------------------------------------------------
    @staticmethod
    def _process_cpu_seconds() -> float:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return float(usage.ru_utime + usage.ru_stime)

    def _cpu_percent(self) -> Optional[float]:
        """CPU% of this process since the previous snapshot (real, sampled)."""
        now = time.time()
        cpu = self._process_cpu_seconds()
        previous = self._cpu_mark
        elapsed = max(1e-6, now - previous["t"])
        pct = ((cpu - previous["cpu"]) / elapsed) * 100.0
        self._cpu_mark = {"t": now, "cpu": cpu}
        if pct < 0 or pct > 100 * max(1, os.cpu_count() or 1):
            return None
        return round(pct, 1)

    @staticmethod
    def _rss_bytes() -> Optional[int]:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        raw = float(usage.ru_maxrss)
        # macOS reports bytes, Linux kilobytes.
        return int(raw if raw > 10_000_000 or os.uname().sysname == "Darwin" else raw * 1024)

    def _log_snapshot(self) -> Dict[str, Any]:
        logs_dir = self.root / "data" / "logs"
        target = logs_dir / "asta.log"
        if not target.is_file():
            return {"path": str(target), "available": False, "errors": 0, "warnings": 0, "recent": []}
        size = target.stat().st_size
        try:
            with target.open("rb") as stream:
                stream.seek(max(0, size - TAIL_BYTES))
                raw = stream.read().decode("utf-8", errors="replace")
        except OSError:
            return {"path": str(target), "available": False, "errors": 0, "warnings": 0, "recent": []}
        lines = raw.splitlines()
        errors = 0
        warnings = 0
        recent: List[Dict[str, Any]] = []
        for line in lines:
            match = LOG_LINE.match(line)
            if not match:
                continue
            level = match.group("level")
            if level in ("ERROR", "CRITICAL"):
                errors += 1
            elif level == "WARNING":
                warnings += 1
            if level in ("ERROR", "CRITICAL", "WARNING"):
                recent.append(
                    {
                        "at": match.group("at"),
                        "level": "error" if level in ("ERROR", "CRITICAL") else "warning",
                        "module": match.group("module").strip(),
                        "message": match.group("message").strip()[:280],
                    }
                )
        return {
            "path": str(target),
            "available": True,
            "sizeBytes": size,
            "errors": errors,
            "warnings": warnings,
            "sampledLines": len(lines),
            "recent": recent[-24:],
        }

    def system_snapshot(self) -> Dict[str, Any]:
        """Real process/system metrics; nothing here is simulated."""
        config = self.app.config
        status = self.status()
        db_path = config.resolve_path(config.storage.sqlite_path)
        db_size = 0
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(db_path) + suffix)
            try:
                db_size += candidate.stat().st_size
            except OSError:
                pass
        try:
            load = [round(value, 2) for value in os.getloadavg()]
        except (OSError, AttributeError):
            load = None
        return {
            "version": __import__("asta").__version__,
            "pid": os.getpid(),
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started_at)),
            "uptimeSeconds": round(time.time() - self.started_at, 1),
            "loadAvg": load,
            "cpuPct": self._cpu_percent(),
            "rssBytes": self._rss_bytes(),
            "threads": threading.active_count(),
            "database": {
                "path": str(db_path),
                "sizeBytes": db_size,
                "available": db_path.exists(),
                "signals": status.get("storage", {}).get("records"),
            },
            "logs": self._log_snapshot(),
            "cycles": status.get("cycles"),
            "lastCycleAt": status.get("lastCycleAt"),
            "storage": status.get("storage"),
            "scanners": {"total": status.get("scanners"), "enabled": status.get("enabledScanners")},
            "environment": status.get("environment"),
            "dryRun": status.get("dryRun"),
            "web": status.get("web"),
        }


def probe(url: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """Read /api/health from a running dashboard, or None when it is down."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
