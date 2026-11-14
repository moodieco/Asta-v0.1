"""Desktop launcher: a native WebView window over the local control panel.

The window is a WKWebView (pywebview) showing ``panel/index.html`` served by
:class:`asta.launcher.control.PanelServer`. The scanner is not owned by this process:
Start spawns ``asta serve`` detached, so closing the window never stops it.

Why not Tk: this machine runs Tk 8.5, where drawn widgets (labels, frames, canvas)
render as nothing while only native controls appear, and the aqua theme ignores
colour. A WebView uses the system browser engine, so the panel matches the dashboard.
"""

from __future__ import annotations

import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional

from asta.config import load_config
from asta.launcher.control import PanelServer
from asta.launcher.supervisor import Supervisor
from asta.setup.state import SetupState
from asta.utils.logger import get_logger

logger = get_logger("asta.launcher")

PANEL_PORT = 4311


def _open_window(
    url: str,
    title: str = "ASTA",
    width: int = 1280,
    height: int = 860,
) -> None:
    """Show the app in a native window; fall back to the default browser."""
    try:
        import webview  # type: ignore
    except ImportError:
        webview = None  # type: ignore[assignment]

    if webview is not None:
        webview.create_window(
            title,
            url,
            width=width,
            height=height,
            min_size=(520, 640),
            background_color="#f5f6f9",
        )
        webview.start()
        return

    logger.warning("pywebview is not installed - opening the panel in a browser instead")
    print("pywebview missing; opening %s in the default browser" % url)
    if not webbrowser.open(url):
        print("open this URL manually: %s" % url)
        try:
            input("press enter to close the panel…")
        except EOFError:
            pass


def run_launcher(
    config_dir: Optional[str] = None,
    focus_setup: bool = False,
    in_browser: bool = False,
) -> int:
    """Open the single ASTA window.

    No setup yet  -> the control panel's setup wizard.
    Engine up     -> the dashboard itself (one app, not a second panel).
    Engine down   -> the control panel, which can start it and then hand over.
    """
    config = load_config(config_dir, require=False)
    root = Path(config.project_root).resolve()
    supervisor = Supervisor(
        root=root,
        host=config.web.host,
        port=config.web.port,
        config_dir=config_dir,
    )

    panel = PanelServer(supervisor, port=PANEL_PORT, config_dir=config_dir)
    try:
        url = panel.start()
    except OSError:
        logger.warning("panel port %s busy - using a free port", PANEL_PORT)
        panel = PanelServer(supervisor, port=0, config_dir=config_dir)
        url = panel.start()

    state = SetupState.load(config.resolve_path(config.setup.state_path))
    dashboard_ready = state.complete and supervisor.health() is not None

    target = supervisor.url if dashboard_ready and not focus_setup else url
    if not dashboard_ready and focus_setup:
        target = url + "?setup=1"

    print("ASTA launcher: %s" % target, file=sys.stderr, flush=True)
    try:
        if in_browser:
            webbrowser.open(target)
            print("ASTA running on %s - press Ctrl+C to close it" % url)
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                return 0
        _open_window(
            target,
            width=1280 if dashboard_ready else 620,
            height=860 if dashboard_ready else 880,
        )
        return 0
    finally:
        panel.stop()
