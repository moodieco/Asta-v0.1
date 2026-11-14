"""Desktop launcher window.

Start / Stop / Restart / Open Dashboard / System Status / Quick Setup. The window
never owns the scanner process: it starts ``asta serve`` detached, then only polls
its pidfile and ``/api/health``.
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, Optional

from asta.config import load_config
from asta.launcher import flatui as ttk
from asta.launcher import theme
from asta.launcher.supervisor import Supervisor
from asta.launcher.wizard import Wizard
from asta.setup.state import SetupState


def _format_uptime(seconds: Optional[float]) -> str:
    if not seconds:
        return "—"
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return "{}h {:02d}m".format(hours, minutes)
    if minutes:
        return "{}m {:02d}s".format(minutes, secs)
    return "{}s".format(secs)


class Launcher(tk.Tk):
    REFRESH_MS = 3000

    def __init__(self, config_dir: Optional[str] = None):
        super().__init__()
        self.config_dir = config_dir
        config = load_config(config_dir, require=False)
        self.root_dir = config.project_root
        self.state = SetupState.load(config.resolve_path(config.setup.state_path))
        self.supervisor = Supervisor(
            root=self.root_dir,
            host=config.web.host,
            port=config.web.port,
            config_dir=config_dir,
        )

        self.title("ASTA — Launcher")
        self.geometry("540x700")
        self.minsize(500, 640)
        self.configure(padx=18, pady=16)
        self.style = theme.apply(self)

        self.status: Dict[str, Any] = {}
        self._busy = False

        self._build()
        self.refresh()
        self.after(self.REFRESH_MS, self._tick)

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="ASTA", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="AI signal scanner · dashboard · v0.1",
            style="Muted.TLabel",
        ).pack(anchor="w")

        card = ttk.LabelFrame(self, text="STATUS", padding=12, style="Card.TLabelframe")
        card.pack(fill="x", pady=(14, 10))
        self.state_label = ttk.Label(card, text="checking…", style="StatusDown.TLabel")
        self.state_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.detail_labels: Dict[str, ttk.Label] = {}
        for row, key in enumerate(("pid", "url", "uptime", "scanners", "signals", "cycle"), start=1):
            ttk.Label(card, text=key.upper(), style="Faint.TLabel").grid(
                row=row, column=0, sticky="w", pady=(5, 0)
            )
            label = ttk.Label(card, text="—", style="Mono.TLabel")
            label.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=(5, 0))
            self.detail_labels[key] = label
        card.columnconfigure(1, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(4, 10))
        for column in range(2):
            actions.columnconfigure(column, weight=1)
        self.buttons: Dict[str, ttk.Button] = {}
        specs = (
            ("start", "▶  Start ASTA", self.start_asta, "Accent.TButton"),
            ("stop", "■  Stop ASTA", self.stop_asta, "Danger.TButton"),
            ("restart", "↻  Restart", self.restart_asta, "TButton"),
            ("open", "🌐  Open Dashboard", self.open_dashboard, "TButton"),
            ("status", "ⓘ  System Status", self.show_status, "TButton"),
            ("setup", "⚙  Quick Setup", self.open_setup, "TButton"),
        )
        for index, (key, label, command, style_name) in enumerate(specs):
            button = ttk.Button(actions, text=label, command=command, style=style_name)
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=4, pady=4)
            self.buttons[key] = button
        # sensible defaults until the first status poll returns
        for disabled in ("stop", "restart", "open"):
            self.buttons[disabled].configure(state="disabled")

        ttk.Label(self, text="SETTINGS", style="Faint.TLabel").pack(anchor="w", pady=(12, 4))
        settings_row = ttk.Frame(self)
        settings_row.pack(fill="x")
        ttk.Button(settings_row, text="Open config folder", command=self.open_config_folder).pack(side="left")
        ttk.Button(settings_row, text="Re-run setup", command=lambda: self.open_setup(force=True)).pack(
            side="left", padx=(8, 0)
        )

        log_frame = ttk.LabelFrame(self, text="RECENT LOG", padding=8, style="Card.TLabelframe")
        log_frame.pack(fill="both", expand=True, pady=(14, 0))
        self.log_text = theme.text_widget(log_frame, height=8, wrap="none")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        self.footer = ttk.Label(self, text="", style="Faint.TLabel")
        self.footer.pack(anchor="w", pady=(10, 0))

    # -- status -----------------------------------------------------------
    def refresh(self) -> None:
        try:
            self.status = self.supervisor.status()
        except Exception:  # noqa: BLE001 - status must never break the window
            self.status = {"running": False}
        health = self.status.get("health") or {}
        running = bool(self.status.get("running"))

        self.state_label.configure(
            text="● Running" if running else "● Stopped",
            style="StatusOk.TLabel" if running else "StatusDown.TLabel",
        )
        self.detail_labels["pid"].configure(text=str(self.status.get("pid") or health.get("pid") or "—"))
        self.detail_labels["url"].configure(text=self.status.get("url", "—"))
        self.detail_labels["uptime"].configure(text=_format_uptime(health.get("uptimeSeconds")))
        self.detail_labels["scanners"].configure(
            text="{} enabled / {}".format(health.get("enabledScanners", "—"), health.get("scanners", "—"))
        )
        storage = health.get("storage") or {}
        self.detail_labels["signals"].configure(
            text="{} ({} records)".format(
                (health.get("database") or {}).get("signals", "—"), storage.get("records", "—")
            )
        )
        cycle = health.get("lastCycleAt") or "—"
        self.detail_labels["cycle"].configure(text="{} · {} cycles".format(cycle[:19].replace("T", " "), health.get("cycles", "—")))

        self.buttons["start"].configure(state="disabled" if running or self._busy else "normal")
        self.buttons["stop"].configure(state="normal" if running and not self._busy else "disabled")
        self.buttons["restart"].configure(state="normal" if running and not self._busy else "disabled")
        self.buttons["open"].configure(state="normal" if running else "disabled")
        self.buttons["setup"].configure(text="⚙  Settings" if self.state.complete else "⚙  Quick Setup")
        self.footer.configure(text="config {} · log {}".format(self.root_dir / "config", self.status.get("logPath", "")))
        self._refresh_log()

    def _refresh_log(self) -> None:
        lines = self.supervisor.tail_log(40)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", "\n".join(lines) if lines else "no dashboard log yet")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _tick(self) -> None:
        self.refresh()
        self.after(self.REFRESH_MS, self._tick)

    # -- actions ----------------------------------------------------------
    def _run_async(self, work, done=None) -> None:
        if self._busy:
            return
        self._busy = True
        self.refresh()

        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
            self.after(0, lambda: self._finish(result, done))

        threading.Thread(target=runner, daemon=True).start()

    def _finish(self, result: Dict[str, Any], done=None) -> None:
        self._busy = False
        self.refresh()
        if done:
            done(result)

    def start_asta(self) -> None:
        self.state_label.configure(text="starting…", foreground="#666666")
        self._run_async(
            lambda: self.supervisor.start(open_browser=True),
            lambda result: None
            if result.get("started") or result.get("alreadyRunning")
            else messagebox.showerror(
                "Start failed",
                "{}\n\n{}".format(result.get("error", "unknown error"), "\n".join(result.get("log") or [])),
            ),
        )

    def stop_asta(self) -> None:
        if not messagebox.askyesno("Stop ASTA", "Stop the scanner and the dashboard?"):
            return
        self._run_async(self.supervisor.stop, lambda result: self.refresh())

    def restart_asta(self) -> None:
        self._run_async(lambda: self.supervisor.restart(open_browser=False), lambda result: self.refresh())

    def open_dashboard(self) -> None:
        if not self.supervisor.open_dashboard():
            messagebox.showwarning("Dashboard", "The dashboard is not answering yet. Start ASTA first.")

    def show_status(self) -> None:
        window = tk.Toplevel(self)
        window.title("ASTA — System status")
        window.geometry("640x540")
        window.configure(background=theme.BG)
        text = theme.text_widget(window, wrap="word")
        text.pack(fill="both", expand=True, padx=12, pady=12)
        payload: Dict[str, Any] = {"supervisor": self.status}
        if self.status.get("health"):
            payload["health"] = self.status["health"]
        else:
            payload["note"] = "The dashboard is not answering; showing local supervisor state only."
        text.insert("1.0", json.dumps(payload, indent=2, default=str))
        text.configure(state="disabled")

    def open_setup(self, force: bool = False) -> None:
        settings_mode = force or self.state.complete
        window = Wizard(self, config_dir=self.config_dir, settings_mode=settings_mode)
        window.transient(self)
        self.wait_window(window)
        self.state = SetupState.load(self.state.path)
        self.refresh()

    def open_config_folder(self) -> None:
        import subprocess
        import sys

        path = str(self.root_dir / "config")
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])  # noqa: S603,S607
            elif sys.platform.startswith("win"):
                subprocess.Popen(["explorer", path])  # noqa: S603,S607
            else:
                subprocess.Popen(["xdg-open", path])  # noqa: S603,S607
        except OSError as exc:
            messagebox.showerror("Open folder", str(exc))


def run_launcher(config_dir: Optional[str] = None) -> int:
    app = Launcher(config_dir=config_dir)
    app.mainloop()
    return 0
