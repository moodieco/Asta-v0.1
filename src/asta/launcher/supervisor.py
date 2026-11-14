"""Process control for the launcher.

``asta serve`` runs as a detached child: closing the browser, the launcher window,
or Terminal must not stop the scanner. Liveness is therefore decided by two
independent signals - the pidfile and ``/api/health`` - so a stale pidfile after a
crash never reports "running".
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from asta.web.service import probe

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4310


def project_root() -> Path:
    env = os.getenv("ASTA_PROJECT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # src/asta/launcher/supervisor.py -> repo root
    return Path(__file__).resolve().parents[3]


class Supervisor:
    def __init__(
        self,
        root: Optional[Path | str] = None,
        python: Optional[str] = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        config_dir: Optional[str] = None,
    ):
        self.root = Path(root or project_root()).expanduser().resolve()
        self.python = python or sys.executable
        self.host = host
        self.port = int(port)
        self.config_dir = config_dir
        self.logs_dir = self.root / "data" / "logs"
        self.pid_path = self.logs_dir / "asta-serve.pid"
        self.log_path = self.logs_dir / "dashboard.log"

    # -- introspection ----------------------------------------------------
    @property
    def url(self) -> str:
        base = "localhost" if self.host in ("127.0.0.1", "::1") else self.host
        return "http://{}:{}/".format(base, self.port)

    def health(self) -> Optional[Dict[str, Any]]:
        return probe(self.url, timeout=1.5)

    def read_pid(self) -> Optional[int]:
        try:
            raw = self.pid_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    @staticmethod
    def _alive(pid: Optional[int]) -> bool:
        if not pid:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def status(self) -> Dict[str, Any]:
        pid = self.read_pid()
        health = self.health()
        running = health is not None or self._alive(pid)
        payload: Dict[str, Any] = {
            "running": running,
            "pid": pid,
            "pidAlive": self._alive(pid),
            "url": self.url,
            "logPath": str(self.log_path),
            "pidPath": str(self.pid_path),
        }
        if health:
            payload["health"] = health
        return payload

    def tail_log(self, lines: int = 40) -> List[str]:
        try:
            content = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        return content[-lines:]

    # -- lifecycle --------------------------------------------------------
    def _write_pid(self, pid: int) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.pid_path.write_text(str(pid), encoding="utf-8")

    def _clear_pid(self) -> None:
        try:
            self.pid_path.unlink()
        except OSError:
            pass

    def start(self, wait: float = 25.0, open_browser: bool = True) -> Dict[str, Any]:
        current = self.status()
        if current["running"]:
            if open_browser:
                self.open_dashboard()
            return {"started": False, "alreadyRunning": True, **current}

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        command = [self.python, "-m", "asta.main", "serve", "--port", str(self.port), "--no-browser"]
        if self.config_dir:
            command.extend(["--config", self.config_dir])
        env = dict(os.environ)
        env.setdefault("ASTA_PROJECT_ROOT", str(self.root))
        env.setdefault("PYTHONUNBUFFERED", "1")

        try:
            with open(self.log_path, "ab") as log:
                log.write("\n=== asta serve start {} ===\n".format(time.strftime("%Y-%m-%d %H:%M:%S")).encode())
                log.flush()
                process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
                    command,
                    cwd=str(self.root),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except OSError as exc:
            return {"started": False, "error": "cannot launch: {}".format(exc)}

        self._write_pid(process.pid)
        deadline = time.time() + max(wait, 3)
        while time.time() < deadline:
            health = self.health()
            if health is not None:
                if open_browser:
                    webbrowser.open(self.url)
                return {
                    "started": True,
                    "pid": process.pid,
                    "url": self.url,
                    "health": health,
                    "logPath": str(self.log_path),
                }
            if process.poll() is not None:
                return {
                    "started": False,
                    "exitCode": process.returncode,
                    "error": "process exited before the dashboard was ready",
                    "log": self.tail_log(15),
                }
            time.sleep(0.4)
        return {
            "started": False,
            "error": "dashboard did not become ready in {:.0f}s".format(wait),
            "log": self.tail_log(15),
        }

    def stop(self, timeout: float = 12.0) -> Dict[str, Any]:
        pid = self.read_pid()
        if not self._alive(pid):
            self._clear_pid()
            return {"stopped": False, "reason": "not running"}
        assert pid is not None
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            self._clear_pid()
            return {"stopped": False, "reason": str(exc)}

        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._alive(pid):
                self._clear_pid()
                return {"stopped": True, "pid": pid, "forced": False}
            time.sleep(0.2)

        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        self._clear_pid()
        return {"stopped": True, "pid": pid, "forced": True}

    def restart(self, wait: float = 25.0, open_browser: bool = True) -> Dict[str, Any]:
        stopped = self.stop()
        started = self.start(wait=wait, open_browser=open_browser)
        return {"stop": stopped, "start": started}

    def open_dashboard(self) -> bool:
        if self.health() is None:
            return False
        webbrowser.open(self.url)
        return True
