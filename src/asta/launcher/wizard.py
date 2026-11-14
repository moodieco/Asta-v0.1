"""Quick Setup wizard (5 steps).

Runs once: the result is recorded in ``config/setup_state.json`` and every later
change can be made through the same window (Settings) or the YAML files. Credentials
that already exist and validate are never asked for again.
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from asta.config import load_config
from asta.core.scanner_registry import ScannerRegistry
from asta.launcher import theme
from asta.launcher.supervisor import Supervisor
from asta.setup import secrets, validators, writer
from asta.setup.state import SetupState

MARKETS = ("forex", "crypto", "stock")
MARKET_LABEL = {"forex": "Forex", "crypto": "Crypto", "stock": "Stocks"}
WEBHOOK_KEY = {
    "forex": "DISCORD_WEBHOOK_FOREX",
    "crypto": "DISCORD_WEBHOOK_CRYPTO",
    "stock": "DISCORD_WEBHOOK_STOCK",
}
STEPS = ("discord", "providers", "scanners", "system", "review")
STEP_TITLE = {
    "discord": "Discord channels",
    "providers": "Data providers",
    "scanners": "Markets & scanners",
    "system": "Local system",
    "review": "Validate & save",
}
STEP_HINT = {
    "discord": "One webhook per market channel. URLs are stored in .env, never in YAML.",
    "providers": "Credentials already present and valid are reused - change only what is missing.",
    "scanners": "Enable or disable scanners. Strategy code and parameters stay untouched.",
    "system": "Where the database lives and which loopback port the dashboard uses.",
    "review": "Everything is validated before it touches disk. Secrets are masked here.",
}


def _root(config_dir: Optional[str] = None) -> Path:
    cfg = load_config(config_dir, require=False)
    return Path(cfg.project_root).resolve()


def load_context(config_dir: Optional[str] = None) -> Dict[str, Any]:
    cfg = load_config(config_dir, require=False)
    root = Path(cfg.project_root).resolve()
    env = secrets.read_env(root / ".env")
    scanners: List[Dict[str, Any]] = []
    try:
        registry = ScannerRegistry()
        registry.discover()
        overrides = cfg.scanner_overrides or {}
        for scanner_id, scanner_config in sorted(registry.load_configs().items()):
            effective = scanner_config
            if isinstance(overrides.get(scanner_id), dict):
                effective = scanner_config.with_overrides(overrides[scanner_id])
            scanners.append(
                {
                    "id": scanner_id,
                    "name": effective.name,
                    "market": effective.market.value if hasattr(effective.market, "value") else str(effective.market),
                    "timeframe": effective.timeframe,
                    "enabled": bool(effective.enabled),
                }
            )
    except Exception:  # noqa: BLE001 - wizard must open even if discovery breaks
        scanners = []
    return {
        "config": cfg,
        "root": root,
        "env": env,
        "scanners": scanners,
        "state_path": cfg.resolve_path(cfg.setup.state_path),
        "app_yaml": root / "config" / "app.yaml",
        "markets_yaml": root / "config" / "markets.yaml",
        "discord_yaml": root / "config" / "discord.yaml",
        "env_path": root / ".env",
    }


class Wizard(tk.Toplevel):
    """A Toplevel so the launcher can open it without a second Tk root."""

    def __init__(self, master: Optional[tk.Misc] = None, config_dir: Optional[str] = None,
                 settings_mode: bool = False):
        super().__init__(master)
        self.config_dir = config_dir
        self.settings_mode = settings_mode
        self.context = load_context(config_dir)
        self.state = SetupState.load(self.context["state_path"])
        self.index = 0

        if settings_mode or self.state.complete:
            self.title("ASTA — Settings")
        else:
            self.title("ASTA — Quick Setup")
        self.geometry("780x640")
        self.minsize(720, 560)
        self.configure(padx=18, pady=14)
        self.style = theme.apply(self)

        self.vars: Dict[str, Any] = {}
        self.results: Dict[str, List[Dict[str, Any]]] = {"webhooks": [], "providers": [], "local": []}

        self._build_header()
        self._container = ttk.Frame(self)
        self._container.pack(fill="both", expand=True, pady=(10, 0))
        self.pages: Dict[str, ttk.Frame] = {}
        for step in STEPS:
            page = ttk.Frame(self._container)
            self.pages[step] = page
            getattr(self, "_build_{}".format(step))(page)
        self._build_footer()
        self._show_step(0)

    # -- chrome -----------------------------------------------------------
    def _build_header(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x")
        title = "ASTA settings" if (self.settings_mode or self.state.complete) else "ASTA quick setup"
        ttk.Label(header, text=title, style="Title.TLabel").pack(anchor="w")
        self.step_label = ttk.Label(header, text="", style="Muted.TLabel")
        self.step_label.pack(anchor="w", pady=(2, 0))
        self.hint_label = ttk.Label(header, text="", style="Faint.TLabel", wraplength=700, justify="left")
        self.hint_label.pack(anchor="w", pady=(2, 0))
        ttk.Separator(self).pack(fill="x", pady=(10, 0))

    def _build_footer(self) -> None:
        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(12, 0))
        self.status = ttk.Label(footer, text="", style="Faint.TLabel")
        self.status.pack(side="left")
        self.next_button = ttk.Button(footer, text="Next →", command=self._next, style="Accent.TButton")
        self.next_button.pack(side="right")
        self.back_button = ttk.Button(footer, text="← Back", command=self._back)
        self.back_button.pack(side="right", padx=(0, 8))
        self.save_button = ttk.Button(footer, text="Save & finish", command=self._save, style="Accent.TButton")
        self.save_button.pack(side="right", padx=(0, 8))

    # -- page: discord ----------------------------------------------------
    def _build_discord(self, page: ttk.Frame) -> None:
        env = self.context["env"]
        self.discord_entries: Dict[str, ttk.Entry] = {}
        self.discord_status: Dict[str, ttk.Label] = {}
        for row, market in enumerate(MARKETS):
            frame = ttk.LabelFrame(page, text=MARKET_LABEL[market], padding=10, style="Card.TLabelframe")
            frame.grid(row=row, column=0, sticky="ew", pady=6, padx=2)
            page.columnconfigure(0, weight=1)
            existing = env.get(WEBHOOK_KEY[market], "")
            entry = ttk.Entry(frame, width=74, show="•" if existing else "")
            entry.insert(0, existing)
            entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            frame.columnconfigure(0, weight=1)

            def toggle(target=entry) -> None:
                target.configure(show="" if target.cget("show") else "•")

            ttk.Button(frame, text="show", width=6, command=toggle).grid(row=0, column=1)
            ttk.Button(
                frame,
                text="Test",
                width=6,
                command=lambda m=market: self._test_webhook(m),
            ).grid(row=0, column=2, padx=(6, 0))
            status = ttk.Label(frame, text="✓ saved" if secrets.is_configured(existing) else "not configured",
                               foreground=theme.ACCENT if secrets.is_configured(existing) else theme.WARN)
            status.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
            self.discord_entries[market] = entry
            self.discord_status[market] = status

    def _test_webhook(self, market: str) -> None:
        value = self.discord_entries[market].get().strip()
        self.discord_status[market].configure(text="testing…", foreground=theme.DIM)

        def done(result) -> None:
            self.discord_status[market].configure(
                text=("✓ " if result.ok else "✗ ") + result.detail,
                foreground=theme.ACCENT if result.ok else theme.DANGER,
            )

        self._async(lambda: validators.validate_discord_webhook(value), done)

    # -- page: providers --------------------------------------------------
    def _build_providers(self, page: ttk.Frame) -> None:
        cfg = self.context["config"]
        env = self.context["env"]
        providers = cfg.providers or {}
        self.provider_labels: Dict[str, ttk.Label] = {}

        for row, market in enumerate(MARKETS):
            block = providers.get(market) or (providers.get(market) or {})
            kind = block.get("type") or {"crypto": "binance", "forex": "mt5", "stock": "yahoo"}[market]
            frame = ttk.LabelFrame(page, text="{} · {}".format(MARKET_LABEL[market], kind), padding=10, style="Card.TLabelframe")
            frame.grid(row=row, column=0, sticky="ew", pady=5, padx=2)
            page.columnconfigure(0, weight=1)
            detail = block.get("base_url") or block.get("terminal_url") or ""
            ttk.Label(frame, text=detail or "default endpoint", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
            label = ttk.Label(frame, text="not tested", style="Muted.TLabel")
            label.grid(row=1, column=0, sticky="w", pady=(4, 0))
            self.provider_labels[market] = label

        mt5 = ttk.LabelFrame(page, text="MT5 bridge (forex, optional)", padding=10, style="Card.TLabelframe")
        mt5.grid(row=3, column=0, sticky="ew", pady=5, padx=2)
        ttk.Label(mt5, text="Terminal URL").grid(row=0, column=0, sticky="w")
        self.mt5_url = ttk.Entry(mt5, width=52)
        self.mt5_url.insert(0, env.get("MT5_TERMINAL_URL", ""))
        self.mt5_url.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(mt5, text="Token").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.mt5_token = ttk.Entry(mt5, width=52, show="•")
        self.mt5_token.insert(0, env.get("MT5_TERMINAL_TOKEN", ""))
        self.mt5_token.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        mt5.columnconfigure(1, weight=1)

        ttk.Button(page, text="Test providers", command=self._test_providers).grid(
            row=4, column=0, sticky="w", pady=(8, 0)
        )

    def _test_providers(self) -> None:
        cfg = self.context["config"]
        env = dict(self.context["env"])
        env["MT5_TERMINAL_URL"] = self.mt5_url.get().strip()
        env["MT5_TERMINAL_TOKEN"] = self.mt5_token.get().strip()
        providers = cfg.providers or {}

        def work() -> list:
            return validators.validate_all(env, providers)["providers"]

        def done(items) -> None:
            for result in items:
                label_name = str(result.get("label", "")).lower()
                market = "forex" if "mt5" in label_name or "oanda" in label_name else (
                    "stock" if "yahoo" in label_name else "crypto"
                )
                label = self.provider_labels.get(market)
                if label is None:
                    continue
                label.configure(
                    text=("✓ " if result["ok"] else "✗ ") + result["detail"],
                    foreground=theme.ACCENT if result["ok"] else theme.DANGER,
                )

        self._async(work, done)

    # -- page: scanners ---------------------------------------------------
    def _build_scanners(self, page: ttk.Frame) -> None:
        scanners = self.context["scanners"]
        self.scanner_vars: Dict[str, tk.BooleanVar] = {}
        if not scanners:
            ttk.Label(page, text="No scanners discovered - check src/asta/markets/.").pack(anchor="w")
            return
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in scanners:
            groups.setdefault(item["market"], []).append(item)
        row = 0
        for market in MARKETS:
            if market not in groups:
                continue
            frame = ttk.LabelFrame(page, text=MARKET_LABEL[str(market)] if market in MARKET_LABEL else market, padding=8, style="Card.TLabelframe")
            frame.grid(row=row, column=0, sticky="ew", pady=5, padx=2)
            page.columnconfigure(0, weight=1)
            for index, item in enumerate(groups[market]):
                var = tk.BooleanVar(value=item["enabled"])
                self.scanner_vars[item["id"]] = var
                ttk.Checkbutton(
                    frame,
                    text="{}  ·  {}  ·  {}".format(item["id"], item["timeframe"], item["name"]),
                    variable=var,
                ).grid(row=index, column=0, sticky="w")
            row += 1

    # -- page: system -----------------------------------------------------
    def _build_system(self, page: ttk.Frame) -> None:
        cfg = self.context["config"]
        frame = ttk.LabelFrame(page, text="Storage", padding=10, style="Card.TLabelframe")
        frame.pack(fill="x", pady=5)
        ttk.Label(frame, text="SQLite path").grid(row=0, column=0, sticky="w")
        self.db_path = ttk.Entry(frame, width=56)
        self.db_path.insert(0, cfg.storage.sqlite_path)
        self.db_path.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        frame.columnconfigure(1, weight=1)

        web = ttk.LabelFrame(page, text="Dashboard", padding=10, style="Card.TLabelframe")
        web.pack(fill="x", pady=5)
        ttk.Label(web, text="Host").grid(row=0, column=0, sticky="w")
        self.host_var = tk.StringVar(value=cfg.web.host)
        ttk.Combobox(web, textvariable=self.host_var, values=["127.0.0.1", "localhost"], width=18,
                     state="readonly").grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(web, text="Port").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.port_var = tk.StringVar(value=str(cfg.web.port))
        ttk.Entry(web, textvariable=self.port_var, width=10).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        self.open_browser_var = tk.BooleanVar(value=bool(cfg.web.open_browser))
        ttk.Checkbutton(web, text="Open the dashboard in a browser after start",
                        variable=self.open_browser_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        note = (
            "The scanner and the dashboard run in one process (asta serve). "
            "Closing the browser does not stop the scanner."
        )
        ttk.Label(page, text=note, style="Faint.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=(10, 0))

    # -- page: review -----------------------------------------------------
    def _build_review(self, page: ttk.Frame) -> None:
        ttk.Button(page, text="Run validation", command=self._validate_all).pack(anchor="w")
        self.review_text = theme.text_widget(page, height=14, wrap="word")
        self.review_text.pack(fill="both", expand=True, pady=(8, 0))
        self.review_text.configure(state="disabled")
        self.start_after_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(page, text="Start ASTA now (scanner + dashboard)", variable=self.start_after_var).pack(
            anchor="w", pady=(8, 0)
        )

    # -- navigation -------------------------------------------------------
    def _show_step(self, index: int) -> None:
        self.index = max(0, min(index, len(STEPS) - 1))
        step = STEPS[self.index]
        for page in self.pages.values():
            page.pack_forget()
        self.pages[step].pack(fill="both", expand=True)
        self.step_label.configure(text="Step {} of {} · {}".format(self.index + 1, len(STEPS), STEP_TITLE[step]))
        self.hint_label.configure(text=STEP_HINT[step])
        self.back_button.configure(state="normal" if self.index > 0 else "disabled")
        is_last = self.index == len(STEPS) - 1
        self.next_button.configure(state="disabled" if is_last else "normal")
        self.save_button.configure(state="normal" if is_last else "disabled")
        if step == "review":
            self._validate_all()

    def _next(self) -> None:
        if not self._collect():
            return
        self._show_step(self.index + 1)

    def _back(self) -> None:
        self._show_step(self.index - 1)

    # -- data collection --------------------------------------------------
    def _collect(self) -> bool:
        """Validate the current page before leaving it."""
        step = STEPS[self.index]
        if step == "discord":
            for market in MARKETS:
                value = self.discord_entries[market].get().strip()
                if value and not validators.validate_discord_webhook(value).ok:
                    messagebox.showerror("Discord webhook", "{}: the URL does not look valid.".format(MARKET_LABEL[market]))
                    return False
        if step == "system":
            try:
                port = int(self.port_var.get())
            except ValueError:
                messagebox.showerror("Port", "Port must be a number.")
                return False
            if not (1 <= port <= 65535):
                messagebox.showerror("Port", "Port must be between 1 and 65535.")
                return False
        return True

    def _validate_all(self) -> None:
        self._set_review("Running checks…")
        env = dict(self.context["env"])
        for market in MARKETS:
            value = self.discord_entries[market].get().strip()
            if value:
                env[WEBHOOK_KEY[market]] = value
        env["MT5_TERMINAL_URL"] = self.mt5_url.get().strip()
        env["MT5_TERMINAL_TOKEN"] = self.mt5_token.get().strip()
        providers = self.context["config"].providers or {}
        db_path = self.db_path.get().strip()
        host = self.host_var.get().strip() or "127.0.0.1"
        try:
            port = int(self.port_var.get())
        except ValueError:
            port = 0

        def work():
            return validators.validate_all(env, providers, db_path, host, port)

        def done(results) -> None:
            self.results = results
            lines: List[str] = []
            for group, title in (("webhooks", "Discord"), ("providers", "Providers"), ("local", "Local system")):
                lines.append(title)
                for item in results.get(group, []):
                    mark = "✓" if item["ok"] else ("–" if item["optional"] else "✗")
                    lines.append("   {} {} — {}".format(mark, item["label"], item["detail"]))
                lines.append("")
            lines.append("Saved secrets (masked)")
            for market in MARKETS:
                value = self.discord_entries[market].get().strip()
                lines.append("   {}: {}".format(MARKET_LABEL[market], secrets.mask(value) or "not set"))
            lines.append("   Port: {}".format(port))
            lines.append("   Database: {}".format(db_path))
            lines.append("   Scanners enabled: {}".format(sum(1 for v in self.scanner_vars.values() if v.get())))
            self._set_review("\n".join(lines))

        self._async(work, done)

    def _set_review(self, text: str) -> None:
        self.review_text.configure(state="normal")
        self.review_text.delete("1.0", "end")
        self.review_text.insert("1.0", text)
        self.review_text.configure(state="disabled")

    def _async(self, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001 - surface in the UI, never crash the window
                message = str(exc)
                self.after(0, lambda: messagebox.showerror("Check failed", message))
                return
            self.after(0, lambda: done(result))

        threading.Thread(target=runner, daemon=True).start()

    # -- persistence ------------------------------------------------------
    def _save(self) -> None:
        if not self._collect():
            return
        failed = [
            item
            for group in self.results.values()
            for item in group
            if not item.get("ok") and not item.get("optional")
        ]
        if failed:
            proceed = messagebox.askyesno(
                "Validation",
                "{} check(s) failed. Save anyway?\n\n{}".format(
                    len(failed), "\n".join("· {}: {}".format(f["label"], f["detail"]) for f in failed[:5])
                ),
            )
            if not proceed:
                return

        try:
            self._write_config()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save failed", str(exc))
            return

        summary = {
            "webhooks": {market: secrets.mask(self.discord_entries[market].get().strip()) for market in MARKETS},
            "scanners": sorted([sid for sid, var in self.scanner_vars.items() if var.get()]),
            "port": self.port_var.get(),
            "database": self.db_path.get().strip(),
        }
        self.state.mark_complete(summary)

        if self.start_after_var.get():
            supervisor = Supervisor(root=self.context["root"], host=self.host_var.get().strip() or "127.0.0.1",
                                    port=int(self.port_var.get()), config_dir=self.config_dir)
            outcome = supervisor.start(open_browser=self.open_browser_var.get())
            if not outcome.get("started") and not outcome.get("alreadyRunning"):
                messagebox.showwarning("Start", "Saved, but ASTA did not start:\n{}".format(outcome.get("error", "")))
        messagebox.showinfo("ASTA", "Configuration saved. You can reopen this window from Settings.")
        self.destroy()

    def _write_config(self) -> None:
        env_updates: Dict[str, str] = {}
        for market in MARKETS:
            value = self.discord_entries[market].get().strip()
            if value:
                env_updates[WEBHOOK_KEY[market]] = value
        mt5_url = self.mt5_url.get().strip()
        mt5_token = self.mt5_token.get().strip()
        if mt5_url:
            env_updates["MT5_TERMINAL_URL"] = mt5_url
        if mt5_token:
            env_updates["MT5_TERMINAL_TOKEN"] = mt5_token
        if env_updates:
            secrets.write_env(self.context["env_path"], env_updates)

        app_doc = writer.set_web(self.context["app_yaml"], host=self.host_var.get().strip() or None,
                                 port=int(self.port_var.get()))
        writer.set_sqlite_path(self.context["app_yaml"], self.db_path.get().strip())
        app_doc.set(["web", "open_browser"], bool(self.open_browser_var.get()))
        app_doc.write()

        markets_doc = writer.YamlFile(self.context["markets_yaml"])
        for scanner_id, var in self.scanner_vars.items():
            markets_doc.set(["scanner_overrides", scanner_id, "enabled"], bool(var.get()))
        markets_doc.write()

        self.state.record_step("discord", {"configured": [m for m in MARKETS if secrets.is_configured(env_updates.get(WEBHOOK_KEY[m]))]})
        self.state.record_step("providers", {"tested": len(self.results.get("providers", []))})
        self.state.record_step("scanners", {"enabled": sorted([sid for sid, var in self.scanner_vars.items() if var.get()])})
        self.state.record_step("system", {"port": self.port_var.get(), "database": self.db_path.get().strip()})
        self.state.record_step("review", {"validated": True})


def run_wizard(config_dir: Optional[str] = None, settings_mode: bool = False) -> int:
    root = tk.Tk()
    root.withdraw()
    Wizard(root, config_dir=config_dir, settings_mode=settings_mode)
    root.mainloop()
    return 0
