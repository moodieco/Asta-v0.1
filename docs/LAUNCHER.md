# ASTA Launcher

One window for the whole app: start ASTA, configure it, and use the dashboard without a terminal.

```
open ASTA.app            # or: .venv/bin/asta launcher
.venv/bin/asta setup     # same window, straight into Quick Setup
```

## How it works

The window is a **native WebView** (WKWebView via [pywebview](https://pywebview.flowrl.com)).
What it shows depends on state, so the launcher and the dashboard are one product:

| State | Window |
|---|---|
| Setup not finished | the control panel, opened on the setup wizard |
| Setup finished, engine running | the dashboard itself (`http://localhost:4310/`), 1280×860 |
| Engine stopped | the control panel, which can start it and hand over |

The control panel is served by `asta.launcher.control.PanelServer` on
`127.0.0.1:4311`; it is plain HTML/CSS/JS, so it renders with the system browser
engine. The scanner is a **separate, detached** process (`asta serve` on 4310); the
launcher only supervises it.

```
ASTA.app ──► asta launcher ──► PanelServer :4311 ──► panel (when engine is down / setup needed)
                                   │
                                   └─ start/stop ──► asta serve :4310 (detached)
                                                        └─ scanner + dashboard SPA/API
```

Install the window dependency once: `pip install -e ".[launcher]"` (adds `pywebview`).
Without it, the panel still works — it opens in the default browser.

## What the panel does

| Control | Behaviour |
|---|---|
| **Start ASTA** | Spawns `asta serve` detached (`start_new_session`), waits for `/api/health`, opens the dashboard in the browser. |
| **Stop ASTA** | `SIGTERM`, waits up to 12 s, then `SIGKILL`; clears the pidfile. |
| **Restart** | Stop, then start again. |
| **Open Dashboard** | Only enabled while `/api/health` answers. |
| **Quick Setup / Settings** | Five-step wizard inside the panel (below). |
| **Refresh** | Re-reads status and the last 60 log lines. |

Closing the window, the browser, or Terminal does **not** stop the scanner: the child
is reparented to `launchd` (PPID 1) and only the Stop button, `kill <pid>`, or a reboot
ends it.

## Liveness model

Two independent signals:

1. `data/logs/asta-serve.pid` — written by the launcher after spawn.
2. `GET /api/health` — proof the process actually serves requests.

A stale pidfile after `kill -9` reports **Stopped**, never a false "Running".

Logs: `data/logs/dashboard.log` (child stdout/stderr), `data/logs/launcher.log`
(WebView process, when started from the `.app`).

## Quick Setup (5 steps)

**1 · Discord channels** — one webhook per market. Each URL is validated against
Discord; an existing valid URL shows `✓ saved ••••abcd` and never has to be retyped.

**2 · Data providers** — shows the detected type per market (binance / mt5 / oanda /
yahoo), tests them live, and lets you set the optional MT5 bridge URL/token.

**3 · Markets & scanners** — every discovered scanner with timeframe and id; the
checkboxes write `scanner_overrides.<ID>.enabled` into `config/markets.yaml`. Strategy
code and parameters are never touched.

**4 · Local system** — SQLite path, loopback host, dashboard port (default 4310), and
"open browser after start".

**5 · Validate & save** — runs every check, prints a masked summary, saves, optionally
starts ASTA.

### Where things are stored

| Data | Location | Notes |
|---|---|---|
| Secrets | `.env` | atomic write, `chmod 0600`, merges with existing comments |
| Non-secret setup | `config/app.yaml`, `config/markets.yaml` | line-by-line edit, comments preserved, re-parsed before writing |
| Setup marker | `config/setup_state.json` | `completed_at` + per-step summary; **no secrets** |

Setup runs once; afterwards the button reads **Settings** and re-opens the same wizard.
Existing credentials are detected, so nothing is asked twice.

## Panel API

Loopback only (`127.0.0.1:4311`). Every `POST` must carry `X-ASTA-Panel: 1`, so a random
web page cannot drive it.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/launcher/status` | supervisor state + dashboard health |
| GET | `/api/launcher/log` | last 60 log lines |
| GET | `/api/launcher/setup` | wizard context (secrets masked) |
| POST | `/api/launcher/start` · `stop` · `restart` · `open` | process control |
| POST | `/api/launcher/setup/validate` | run all connectivity checks |
| POST | `/api/launcher/setup/save` | write `.env` + YAML + state, optional start |

## Building the .app bundle

```bash
./packaging/build_macos_app.sh          # creates ./ASTA.app (ad-hoc signed)
./packaging/build_macos_app.sh --open   # build and launch
```

The bundle is a thin stub: `ASTA.app/Contents/MacOS/ASTA` resolves the repo from its
own location (`../../..`) and runs `.venv/bin/python -m asta.main launcher`.

### macOS quirks this bundle already handles

| Symptom | Cause | What we do |
|---|---|---|
| Double-click does nothing; log shows `ImportError: … incompatible architecture (have 'arm64', need 'x86_64')` | A script-only bundle is treated as x86_64 on Apple Silicon, so LaunchServices starts the shell under Rosetta while the venv's native wheels are arm64-only | The stub re-executes the interpreter as `/usr/bin/arch -arm64`; `LSArchitecturePriority` lists arm64 first |
| "ASTA is damaged / cannot be opened" | Ad-hoc signature, not notarised | Right-click → Open once, or `xattr -cr ASTA.app` |
| Window renders grey, or completely blank | This machine's Tk 8.5: `aqua` ignores colour, `clam` paints nothing, and drawn widgets (labels/frames/canvas) never appear — only native controls do | No Tk at all: the UI is HTML in a WebView |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Panel window blank | The panel server is down: check `lsof -nP -iTCP:4311`, then `data/logs/launcher.log`. |
| Start says "dashboard did not become ready" | Port busy or config error; read `data/logs/dashboard.log`. |
| Panel shows Stopped but 4310 is open | Another `asta serve` started outside the launcher (no pidfile): `asta status`, then `kill <pid>`. |
| Validation fails for webhooks | Offline or the URL is revoked — validation is a real request to Discord. |
| `Cannot bind 127.0.0.1:4310` | Something else owns the port: `lsof -nP -iTCP:4310 -sTCP:LISTEN`. |
