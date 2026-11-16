# Deploy ASTA on your own machine (macOS / Windows / Linux)

One repo, one command, one set of files. The only per-OS difference is *how the
process is kept alive* — everything in `src/` and `config/` is shared.

```
asta serve --host 127.0.0.1 --port 4310 --no-browser      # identical on all three
```

| Step | macOS | Windows | Linux |
|---|---|---|---|
| Python | `brew install python@3.12` | `winget install Python.Python.3.12` | `apt install python3.12-venv` |
| venv + install | `python3.12 -m venv .venv && .venv/bin/pip install -e .` | `py -3.12 -m venv .venv; .\.venv\Scripts\pip install -e .` | same as macOS |
| Run in foreground | `.venv/bin/asta serve --no-browser` | `.\.venv\Scripts\asta serve --no-browser` | `.venv/bin/asta serve --no-browser` |
| Service | `./deploy/install.sh` | `deploy\windows\install-service.ps1` | `./deploy/install.sh` |
| Service manager | launchd (`com.asta.engine`) | NSSM (`ASTA`) | systemd user unit (`asta`) |
| No sleep | `sudo pmset -a sleep 0 disksleep 0` | `powercfg /change standby-timeout-ac 0` | `systemctl mask sleep.target` |
| Public HTTPS | [`docs/TAILSCALE.md`](../docs/TAILSCALE.md) (Tailscale Funnel) | same | same |
| Forex (MT5) | ✖ use OANDA (`providers.forex.type: oanda`) | ✔ native MT5 terminal | ✖ OANDA, or disable forex |

## Install / uninstall

```bash
./deploy/install.sh --dry-run     # print the rendered unit, change nothing
./deploy/install.sh               # register + start
./deploy/install.sh --uninstall   # stop + remove (data/ and .env survive)
```

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install-service.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install-service.ps1 -Uninstall
```

## What lives where

```
deploy/
├── install.sh                       # macOS + Linux renderer/registrar
├── launchd/com.asta.engine.plist.tpl
├── systemd/asta.service
└── windows/install-service.ps1      # NSSM, needs one elevated shell
```

Placeholders `@ASTA_ROOT@` / `@ASTA_BIN@` are substituted with the checkout path, so
the same templates work from any directory (`~/asta`, `/opt/asta`, `C:\asta`).

## Rules that keep the repo from splitting

1. No OS branching in `src/` — the two exceptions are already handled: `resource`
   is optional (Windows has no such module) and `tzdata` is a Windows-only
   dependency for `zoneinfo`.
2. Per-OS files stay in `deploy/` and are thin: they only describe *how to run the
   same command*.
3. Data stays in `data/` (relative) on every OS; no absolute paths in config.
4. Docker (`Dockerfile`) and Render (`render.yaml`) are additional targets, not
   forks — they run the same entry point.
