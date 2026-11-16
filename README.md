# ASTA V0.1 — AI Signal Trading Agent

Multi-market signal scanner (Forex, Crypto, Stock) that detects setups with modular
scanners and pushes formatted alerts to Discord. **V0.1 detects and notifies — it never
places orders.**

```
providers ──► data_service ──► scanners ──► signal_manager ──► notifications
          (candles, cached)            (validate → dedupe → store)   (Discord)
```

## Status

| Area | State |
|---|---|
| Core (contracts, registry, manager, scheduler, event bus) | done |
| Services (data, analysis, notification) | done |
| Providers: Binance crypto, **MT5 MCP forex**, Yahoo stock | done |
| Scanners: 2 forex, 4 crypto, 2 stock | done |
| Signal pipeline: validate, dedupe, entry/stop/target, outcome scoring | done |
| Storage: SQLite history (single source of truth), 1.4k backfilled signals | done |
| Dashboard: `asta serve` — read-only API + React UI on 127.0.0.1:4310 | done |
| Desktop launcher: Quick Setup wizard, start/stop/restart, system status | done |
| Discord: webhook client, embeds, per-market routing, test/sample alerts | done |
| Config: 4 files, env expansion, dry-run, per-scanner overrides | done |
| Tooling: CLI, 5 scripts, CI (tests + lint) | done |
| Tests | see `pytest -q` |

## Share and run 24/7

| Goal | Command |
|---|---|
| Stable public HTTPS (no domain, free) | `./scripts/share-tailscale.sh` → `https://<machine>.<tailnet>.ts.net` |
| Random public URL (dies on restart) | `./scripts/share.sh` (cloudflared quick tunnel) |
| Run as a background service | `./deploy/install.sh` (macOS/Linux) · `deploy\windows\install-service.ps1` |

Runbooks: [`docs/TAILSCALE.md`](docs/TAILSCALE.md) · [`deploy/README.md`](deploy/README.md) (macOS/Windows/Linux matrix).

## Deploy (Render)

`Dockerfile` + `render.yaml` build the dashboard and run the scanner in one
service. Push to GitHub, then Render → **New → Blueprint**. Full checklist,
env vars and caveats: [`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md).

## Install

Panduan lengkap dari nol (clone → dashboard → link HTTPS stabil):
[`docs/INSTALL.md`](docs/INSTALL.md).

## Quickstart (Bahasa Indonesia)

```bash
cd ~/Projects/asta-v0.1
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env                 # webhook Discord + ASTA_EDITOR_TOKEN/VIEWER_TOKEN
cd web && npm ci && npm run build && cd ..   # dashboard bundle (web/dist, tidak di-commit)
.venv/bin/asta --health              # provider, storage, webhook
.venv/bin/asta --once --dry-run      # satu siklus, tidak kirim ke Discord
.venv/bin/asta serve                 # scanner + dashboard (browser terbuka otomatis)
```

Launcher desktop (tanpa terminal): buka `ASTA.app` (lihat `docs/LAUNCHER.md`), atau
`asta launcher`. Quick Setup dijalankan sekali; setelah itu konfigurasi diubah lewat
Settings.

## Struktur folder

```
config/                     app.yaml · markets.yaml · logging.yaml · discord.yaml
docs/                       architecture, API, signal spec, scanner guide, db schema, security
src/asta/
  main.py                   CLI
  bootstrap.py              composition root (satu-satunya tempat objek dirakit)
  config.py                 loader untuk 4 file config
  core/                     signal model, scanner base/registry/manager, scheduler,
                            validator, manager, dedup, market manager, event bus, indicators/
  markets/<market>/         market_config.yaml · universe.py · indicators/ · strategies/ · scanners/
  providers/                base.py + crypto/binance/ · forex/oanda/ · stock/yahoo/
  services/                 data_service · analysis_service · notification_service
  integrations/discord/     client · embed_builder · router · alert_manager · channel_config
  web/                      server · routes · queries · service   (dashboard HTTP, read-only)
  launcher/                 app (Tk) · supervisor · wizard          (desktop launcher)
  setup/                    state · secrets · validators · writer   (quick setup logic)
  storage/                  database · repositories/ · models/ · signal_history · cache
  utils/                    logger · time_utils · exceptions
web/                        Vite + React dashboard (source + dist/)
tests/                      unit/ (core, forex, crypto, stock, web, setup, launcher) · integration/ · e2e/ · fixtures/
scripts/                    run_asta · test_connections · validate_config · scanner_status · inspect_market
data/                       cache/ · history/ · logs/
```

Setiap scanner punya folder sendiri berisi `scanner.py`, `config.yaml`, dan `README.md`
(entry conditions, parameter, kapan dia diam).

## Scanner V0.1

| ID | Market | TF | Strategi |
|---|---|---|---|
| `FXS001_RSI_DIVERGENCE` | forex | 1h | regular RSI divergence |
| `FXS002_EMA_CROSSOVER` | forex | 1h | EMA20/50 cross + EMA200 context |
| `CXS001_RSI_DIVERGENCE` | crypto | 1h | RSI divergence + volume gate |
| `CXS002_VOLUME_SPIKE` | crypto | 15m | 3x volume spike, directional body |
| `CXS003_BREAKOUT_TREND` | crypto | 1h | 30-bar breakout + volume + ATR cap |
| `CXS004_EMA_PULLBACK` | crypto | 1h | trend pullback continuation (EMA20/100 + RSI reset) |
| `STS001_EMA_TREND` | stock | 1d | EMA cross aligned with EMA200 |
| `STS002_BREAKOUT_TREND` | stock | 1d | 40-bar breakout + volume + gap |

## CLI & scripts

```bash
asta serve [--port 4310] [--no-browser]     # scanner + dashboard
asta status                                  # JSON status of a running instance
asta setup                                   # quick setup wizard
asta launcher                                # desktop launcher window

asta --once [--dry-run] [--markets crypto] [--scanners CXS002_VOLUME_SPIKE]
asta --list-scanners | --health | --test-alert | --sample-alert
asta --config /path/to/config-dir

python scripts/validate_config.py       # static config/scanner checks
python scripts/test_connections.py      # provider + webhook connectivity (--send to post)
python scripts/scanner_status.py        # inventory, health, recent signals
python scripts/inspect_market.py --market crypto --symbols BTCUSDT --timeframes 1h
python scripts/scan_once.py             # offline demo with synthetic candles
python scripts/signal_frequency.py --market crypto   # alerts/day per scanner (history replay)
python scripts/migrate_history.py                    # JSONL -> SQLite, idempotent
python scripts/backfill_history.py --market crypto --days 60 --commit   # historical replay
python scripts/update_outcomes.py                    # score open signals (TP/SL/expiry)
```

## Configuration

| File | Isi |
|---|---|
| `config/app.yaml` | environment, scheduler, validator, storage backend, provider settings |
| `config/markets.yaml` | market mana yang aktif, daftar symbol, override per scanner |
| `config/logging.yaml` | level, format (text/json), rotating file, per-logger level |
| `config/discord.yaml` | mapping market → env var webhook + label channel |
| `config/setup_state.json` | quick-setup marker (written by the wizard, no secrets) |

Secrets hanya di `.env` (`${VAR}` di-expand saat load). `storage.backend: jsonl | sqlite`
menentukan penyimpanan sinyal; dashboard membaca file SQLite yang sama secara read-only.
Blok `web:` mengatur host/port dashboard.

## Documentation

* [ARCHITECTURE](docs/ARCHITECTURE.md) · [API](docs/API_DOCUMENTATION.md) · [SIGNAL SPEC](docs/SIGNAL_SPECIFICATION.md)
* [SCANNER GUIDE](docs/SCANNER_GUIDE.md) · [DATABASE SCHEMA](docs/DATABASE_SCHEMA.md)
* [LAUNCHER](docs/LAUNCHER.md) · [WEB API](docs/WEB_API.md) · [SECURITY](docs/SECURITY.md)
* [ROADMAP](docs/DEVELOPMENT_ROADMAP.md) · [CONTRIBUTING](docs/CONTRIBUTING.md) · [AGENTS.md](AGENTS.md)
