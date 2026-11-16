# ASTA v0.1

Multi-market signal scanner for **crypto, stock and forex**: it watches candles with
modular scanners, validates and de-duplicates what it finds, stores every signal in
SQLite, and pushes the actionable ones to Discord. A local dashboard shows the engine,
the scanners and the historical edge.

**It detects and notifies. It never places orders and holds no exchange permissions.**

```
providers ──► data service ──► scanners ──► validator ──► dedup ──► SQLite ──► Discord
            (Binance / Yahoo / MT5)                  (entry · stop · target · R)
```

## Quick start

```bash
git clone https://github.com/moodieco/Asta-V0.1.git asta && cd asta
python3 -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env                        # Discord webhooks + dashboard tokens
cd web && npm ci && npm run build && cd ..   # dashboard bundle (web/dist is not committed)
.venv/bin/asta --health                     # providers, storage, webhooks
.venv/bin/asta serve                        # scanner + dashboard on 127.0.0.1:4310
```

Open `http://127.0.0.1:4310/?token=<ASTA_EDITOR_TOKEN>`.

Full walkthrough, per OS, plus a stable public HTTPS link:
**[`docs/INSTALL.md`](docs/INSTALL.md)**.

## Reach it from anywhere

| Goal | How | Notes |
|---|---|---|
| Stable public HTTPS, no domain, free | `./scripts/share-tailscale.sh` | `https://<machine>.<tailnet>.ts.net`, survives reboots |
| Anything, quickly | `./scripts/share.sh` | cloudflared quick tunnel; the URL changes on restart |
| Same Wi-Fi | `asta serve --host 0.0.0.0` | token required for every non-loopback request |
| Hosted (no local machine) | `Dockerfile` + `render.yaml` | crypto + stock only (no MT5 terminal on a server) |

Guide: [`docs/TAILSCALE.md`](docs/TAILSCALE.md) · [`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md)

Two tokens exist and both matter: **editor** (full control) and **viewer** (read-only).
They come from `ASTA_EDITOR_TOKEN` / `ASTA_VIEWER_TOKEN` or `data/share.json`; the
dashboard stores them in an `HttpOnly` cookie. `/healthz` is the only unauthenticated
path, and it returns nothing but `{"ok": true}`.

## What is inside

| Area | Detail |
|---|---|
| Scanners | 9 built-in across three markets, each a folder with `scanner.py`, `config.yaml`, `README.md` |
| Strategies | one folder `markets/strategies/` — generic implementation + `crypto_/stock_/forex_` tuning subclasses |
| Providers | Binance (crypto), Yahoo (stock), MT5 MCP with public-data fallback (forex) or OANDA |
| Signal pipeline | validator → dedup window → SQLite history → Discord, with entry/stop/target and realized R |
| Dashboard | React + Vite SPA: overview, signal history, scanner management, alerts, system monitor, dark mode |
| Write API | install/uninstall/restore/purge scanners, enable toggles, test & sample alerts, regenerate share links |
| Storage | SQLite (WAL, single source of truth) or JSONL, one switch in `config/app.yaml` |
| Tests | 181 unit tests, `ruff` clean, `tsc` + Vite build in CI |

### Scanners

| ID | Market | TF | Setup |
|---|---|---|---|
| `FXS001_RSI_DIVERGENCE` | forex | 1h | regular RSI divergence |
| `FXS002_EMA_CROSSOVER` | forex | 1h | EMA 20/50 cross with EMA 200 context |
| `FXS003_ASIA_RANGE_BREAKOUT` | forex | 1h | Asia-session range break (NY hours, DST aware) |
| `CXS001_RSI_DIVERGENCE` | crypto | 1h | divergence + volume gate |
| `CXS002_VOLUME_SPIKE` | crypto | 15m | 3× volume spike with directional body |
| `CXS003_BREAKOUT_TREND` | crypto | 1h | 30-bar breakout + volume + ATR extension cap |
| `CXS004_EMA_PULLBACK` | crypto | 1h | trend pullback continuation (EMA 20/100 + RSI reset) |
| `STS001_EMA_TREND` | stock | 1d | EMA cross aligned with EMA 200 |
| `STS002_BREAKOUT_TREND` | stock | 1d | 40-bar breakout + volume + overnight gap |

Writing your own: **[`docs/SCANNER_GUIDE.md`](docs/SCANNER_GUIDE.md)**.
Uploading one: the dashboard installer is marked *coming soon* — the single-file
contract (metadata + strategy in one `scanner.py`) is the next planned change.

## CLI

```bash
asta serve [--port 4310] [--no-browser]     # scanner + dashboard
asta status | setup | launcher               # inspect, configure, desktop window

asta --once [--dry-run] [--markets crypto] [--scanners CXS002_VOLUME_SPIKE]
asta --list-scanners | --health | --test-alert | --sample-alert
```

Utilities live in `scripts/`: `validate_config.py`, `test_connections.py`,
`scanner_status.py`, `inspect_market.py`, `backfill_history.py`, `update_outcomes.py`.

## Install as a service

```bash
./deploy/install.sh                                   # macOS (launchd) / Linux (systemd)
powershell -File .\deploy\windows\install-service.ps1 # Windows (NSSM)
./deploy/install.sh --uninstall                       # stop and remove, data/ survives
```

Same command on every OS (`asta serve --host 127.0.0.1 --port 4310 --no-browser`); only the
supervisor differs. Matrix and rules: [`deploy/README.md`](deploy/README.md).

## Project layout

```
config/        app.yaml · markets.yaml · logging.yaml · discord.yaml
src/asta/
  core/        signal model, scanner base/registry/manager, scheduler, validator, dedup, indicators
  markets/     strategies/ (generic + per-market) · <market>/scanners/ · <market>/indicators/ · universe
  providers/   binance · yahoo · mt5 · oanda
  services/    data · analysis · notification
  storage/     sqlite · repositories · history
  web/         http server · routes (read + write) · queries · share tokens
  setup/       quick-setup state and writers
web/           React + Vite dashboard (dist/ built locally)
deploy/        launchd · systemd · windows service templates
docs/          install, tailscale, render, architecture, web API, scanner guide, schema
data/          history/ · scanners/ · alerts/ · logs/   (gitignored)
```

## Configuration

| File | Holds |
|---|---|
| `config/app.yaml` | environment, scheduler, validator, storage, provider settings, `web:` host/port |
| `config/markets.yaml` | enabled markets, symbol universes, per-scanner overrides |
| `config/logging.yaml` | level, format (text/json), rotation, per-logger levels |
| `config/discord.yaml` | market → webhook env var, channel label |
| `.env` | secrets only; YAML refers to them as `${VAR}` |

Runtime data (SQLite history, installed scanners, tokens, alert log) lives under `data/`
and is never committed. Set `ASTA_DATA_DIR` to move it onto a volume.

## Documentation

| Doc | What |
|---|---|
| [INSTALL](docs/INSTALL.md) | zero → running → stable public URL |
| [TAILSCALE](docs/TAILSCALE.md) | Funnel setup, services, troubleshooting |
| [DEPLOY_RENDER](docs/DEPLOY_RENDER.md) | docker + blueprint deploy |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | layers and responsibilities |
| [WEB API](docs/WEB_API.md) | every HTTP endpoint |
| [SCANNER GUIDE](docs/SCANNER_GUIDE.md) | add a scanner + strategy |
| [SIGNAL SPEC](docs/SIGNAL_SPECIFICATION.md) · [DB SCHEMA](docs/DATABASE_SCHEMA.md) | contracts and storage |
| [SECURITY](docs/SECURITY.md) | secrets, tokens, exposure model |
| [CONTRIBUTING](docs/CONTRIBUTING.md) · [AGENTS](AGENTS.md) | conventions for humans and agents |

## Status

Working and tested: engine, 9 scanners, SQLite history, Discord delivery, dashboard
(read + write), share tokens, Tailscale Funnel, service units for three OSes.

Next, in order: single-file scanner upload (template + strict validation), Windows
end-to-end verification of the service scripts, and forex on Linux via OANDA.

Not in scope for v0.1: order execution, position tracking, PnL accounting.
