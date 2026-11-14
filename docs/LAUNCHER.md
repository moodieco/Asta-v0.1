# ASTA Launcher

A native window to start, stop and configure ASTA without a terminal.

```
open ASTA.app          # or: .venv/bin/asta launcher
```

## What the window does

| Control | Behaviour |
|---|---|
| **Start ASTA** | Spawns `asta serve` **detached** (`start_new_session`), waits for `/api/health`, then opens the dashboard in the browser. Scanner + web server run in that one process. |
| **Stop ASTA** | `SIGTERM`, waits up to 12 s, then `SIGKILL`. Clears the pidfile. |
| **Restart** | Stop, then start without re-opening the browser. |
| **Open Dashboard** | Only enabled while `/api/health` answers. |
| **System Status** | Window with the supervisor snapshot + the full health payload (pid, uptime, scanners, cycles, storage). |
| **Quick Setup / Settings** | Five-step wizard. Shows *Quick Setup* before the first completion, *Settings* afterwards. |

Closing the window, the browser, or Terminal does **not** stop the scanner: the
child is reparented to `launchd` (PPID 1) and is only stopped by the Stop button,
`kill <pid>` or a reboot.

## Liveness model

Two independent signals, both required for "Running":

1. `data/logs/asta-serve.pid` — written by the launcher after spawn.
2. `GET /api/health` — the real proof the process serves requests.

A stale pidfile (crash, `kill -9`) therefore reports **Stopped**, never a false
"Running". The launcher never trusts the pidfile alone.

Logs: `data/logs/dashboard.log` (child stdout/stderr) and `data/logs/launcher.log`
(when started from the `.app` bundle).

## Quick Setup (5 steps)

**1 · Discord channels** — one webhook per market (forex/crypto/stock). Each URL is
validated against Discord (`GET /api/webhooks/<id>/<token>`); a saved URL shows
`✓ saved` and does not have to be retyped.

**2 · Data providers** — reads the `providers:` block. Credentials already present
and valid are reused. MT5 bridge URL/token are optional: without them forex falls
back to public market data.

**3 · Markets & scanners** — every discovered scanner with its timeframe and name;
the checkboxes write `scanner_overrides.<ID>.enabled` into `config/markets.yaml`.
Strategy code and parameters are never touched.

**4 · Local system** — SQLite path, loopback host (`127.0.0.1` or `localhost` only)
and dashboard port (default 4310), plus "open browser after start".

**5 · Validate & save** — runs every check, shows a masked summary, saves, and
optionally starts ASTA.

### Where things are stored

| Data | Location | Notes |
|---|---|---|
| Secrets | `.env` | written atomically, `chmod 0600`, merged with existing comments |
| Non-secret setup | `config/app.yaml`, `config/markets.yaml` | edited line-by-line, comments preserved, re-parsed before writing |
| Setup marker | `config/setup_state.json` | `completed_at` + per-step summary; **no secrets** |

Setup runs once. Later changes go through **Settings** (same wizard) or the YAML
files; the wizard re-detects existing credentials and never asks twice.

## Building the .app bundle

```bash
./packaging/build_macos_app.sh          # creates ./ASTA.app (ad-hoc signed)
./packaging/build_macos_app.sh --open   # build and launch
```

The bundle is a thin stub: `ASTA.app/Contents/MacOS/ASTA` resolves the repo from its
own location (`../../..`) and runs `.venv/bin/python -m asta.main launcher`. Move the
`.app` inside the repo (as built) or rebuild it where the repo lives — it assumes the
bundle sits in the project root.

Unsigned bundles can be blocked on first launch: right-click → **Open** → **Open**.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Start says "dashboard did not become ready" | Port busy or a config error. Read the tail shown in the dialog and `data/logs/dashboard.log`. |
| Window shows Stopped but the port is open | Another `asta serve` was started outside the launcher (no pidfile). Use `asta status`, then stop it with `kill`. |
| Wizard cannot validate webhooks | Offline or the URL is revoked; validation is a real request to Discord. |
| `Cannot bind 127.0.0.1:4310` | Something else owns the port: `lsof -nP -iTCP:4310 -sTCP:LISTEN`. |
