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
| Providers: Binance crypto, OANDA forex, Yahoo stock | done |
| Scanners: 2 forex, 4 crypto, 2 stock | done |
| Signal pipeline: validate, dedupe, entry/stop/target, outcome scoring | done |
| Storage: SQLite history + CSV/Google Sheets export, 1.4k backfilled signals | done |
| Discord: webhook client, embeds, per-market routing, test/sample alerts | done |
| Config: 4 files, env expansion, dry-run, per-scanner overrides | done |
| Tooling: CLI, 5 scripts, CI (tests + lint) | done |
| Tests | 156 passing |

## Quickstart (Bahasa Indonesia)

```bash
cd ~/Projects/asta-v0.1
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,sheets]"
cp .env.example .env                 # webhook Discord (+ token OANDA kalau dipakai)
.venv/bin/asta --health              # provider, storage, webhook
.venv/bin/asta --once --dry-run      # satu siklus, tidak kirim ke Discord
.venv/bin/asta                       # scheduler (tick 60 detik)
```

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
  integrations/sheets/      csv_writer · google_sheets · sync
  storage/                  database · repositories/ · models/ · signal_history · cache
  utils/                    logger · time_utils · exceptions
tests/                      unit/ (core, forex, crypto, stock) · integration/ · e2e/ · fixtures/
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
asta --once [--dry-run] [--markets crypto] [--scanners CXS002_VOLUME_SPIKE]
asta --list-scanners | --health | --test-alert | --sample-alert
asta --config /path/to/config-dir

python scripts/validate_config.py       # static config/scanner checks
python scripts/test_connections.py      # provider + webhook connectivity (--send to post)
python scripts/scanner_status.py        # inventory, health, recent signals
python scripts/inspect_market.py --market crypto --symbols BTCUSDT --timeframes 1h
python scripts/scan_once.py             # offline demo with synthetic candles
python scripts/signal_frequency.py --market crypto   # alerts/day per scanner (history replay)
python scripts/export_signals.py                     # mirror new signals to CSV / Google Sheets
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
| `config/sheets.yaml` | export driver (csv/google), target, cursor, auto-sync |

Secrets hanya di `.env` (`${VAR}` di-expand saat load). `storage.backend: jsonl | sqlite`
menentukan penyimpanan sinyal. Export spreadsheet mengikuti `config/sheets.yaml`
(detail: [docs/SPREADSHEET_SYNC.md](docs/SPREADSHEET_SYNC.md)).

## Documentation

* [ARCHITECTURE](docs/ARCHITECTURE.md) · [API](docs/API_DOCUMENTATION.md) · [SIGNAL SPEC](docs/SIGNAL_SPECIFICATION.md)
* [SCANNER GUIDE](docs/SCANNER_GUIDE.md) · [DATABASE SCHEMA](docs/DATABASE_SCHEMA.md)
* [SPREADSHEET SYNC](docs/SPREADSHEET_SYNC.md) · [SECURITY](docs/SECURITY.md)
* [ROADMAP](docs/DEVELOPMENT_ROADMAP.md) · [CONTRIBUTING](docs/CONTRIBUTING.md) · [AGENTS.md](AGENTS.md)
