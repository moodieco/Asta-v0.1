"""Ties the dashboard server to a built :class:`AstaApp`.

One process, two threads: the scanner owns the asyncio loop in the main thread,
the dashboard owns its socket thread. Nothing here writes to the database.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

from asta.utils.logger import get_logger
from asta.web.server import DashboardServer

logger = get_logger("asta.web.service")


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
        self.server = DashboardServer(
            db_path=config.resolve_path(config.storage.sqlite_path),
            web_dir=self.web_dir,
            host=self.host,
            port=self.port,
            status_provider=self.status,
            config_summary=self.config_summary,
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


def probe(url: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """Read /api/health from a running dashboard, or None when it is down."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
