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
from asta.utils.logger import get_logger

logger = get_logger("asta.launcher")

PANEL_PORT = 4311


def _open_window(url: str, title: str = "ASTA") -> None:
    """Show the panel in a native window; fall back to the default browser."""
    try:
        import webview  # type: ignore
    except ImportError:
        webview = None  # type: ignore[assignment]

    if webview is not None:
        webview.create_window(
            title,
            url,
            width=620,
            height=880,
            min_size=(520, 640),
            background_color="#0b1012",
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

    target = url + ("?setup=1" if focus_setup else "")
    print("ASTA launcher panel: %s" % target, file=sys.stderr, flush=True)
    try:
        if in_browser:
            webbrowser.open(target)
            print("panel running on %s - press Ctrl+C to close it" % url)
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                return 0
        _open_window(target)
        return 0
    finally:
        panel.stop()
