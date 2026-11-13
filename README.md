# ASTA V0.1 — AI Signal Trading Agent

Multi-market signal scanner (Forex, Crypto, Stock) that detects trading setups with
modular scanners and pushes formatted alerts to Discord channels. **V0.1 detects and
notifies only — it never places orders.**

```
provider (Binance / OANDA / Yahoo)  ->  scanners  ->  validate -> dedupe -> history -> Discord
```

## Status V0.1

| Area | State |
|---|---|
| Core (scanner base, registry, manager, scheduler) | done |
| Signal pipeline (validator, deduplication, history, manager) | done |
| Providers: Binance (crypto), OANDA (forex), Yahoo (stock) | done |
| Scanners: 2 forex, 3 crypto, 2 stock | done |
| Discord: webhook client, embed builder, router, alert manager | done |
| Config (YAML + `.env` + `${VAR}` expansion), CLI, CI | done |
| Tests | 91 passing (`pytest -q`) |
| Live order execution / portfolio | out of scope for V0.1 |

## Quickstart (Bahasa Indonesia)

```bash
cd ~/Projects/asta-v0.1
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env          # isi webhook Discord + token OANDA (opsional)
.venv/bin/asta --health       # cek provider & kredensial
.venv/bin/asta --once --dry-run   # satu siklus scan, tidak kirim ke Discord
.venv/bin/asta                # jalankan scheduler (default tiap 60 detik)
```

`--once` tanpa `--dry-run` akan mengirim sinyal ke channel Discord sesuai market.
Sinyal yang sama (scanner + symbol + timeframe + arah) tidak dikirim dua kali dalam
satu dedup window (default 3600 detik).

## Layout

```
config/asta.yaml                 runtime config (markets, providers, overrides)
src/asta/core/                   scanner contract, registry, managers, signal pipeline
src/asta/providers/              binance / oanda / stock (Yahoo) data providers
src/asta/markets/<market>/       scanners/, strategies/, indicators/
src/asta/integrations/discord/   webhook client, embeds, routing, alerts
src/asta/storage/                TTL cache + append-only JSONL history
tests/                           unit + integration + end-to-end tests
```

Each scanner lives in `src/asta/markets/<market>/scanners/<SCANNER_ID>/` with a
`scanner.py` (identity + strategy wiring) and a `config.yaml` (timeframe, symbols,
tunables). Discovery is automatic — drop a folder and it is picked up.

## Scanners in V0.1

| ID | Market | TF | Strategy |
|---|---|---|---|
| `FXS001_RSI_DIVERGENCE` | forex | 1h | regular bullish/bearish RSI divergence |
| `FXS002_EMA_CROSSOVER` | forex | 1h | EMA20/EMA50 cross, EMA200 context |
| `CXS001_RSI_DIVERGENCE` | crypto | 1h | RSI divergence + volume expansion |
| `CXS002_VOLUME_SPIKE` | crypto | 15m | 3x volume spike with directional body |
| `CXS003_BREAKOUT_TREND` | crypto | 1h | 30-bar breakout + volume + ATR cap |
| `STS001_EMA_TREND` | stock | 1d | EMA cross aligned with EMA200 |
| `STS002_BREAKOUT_TREND` | stock | 1d | 40-bar breakout + volume |

## CLI

```bash
asta --list-scanners                  # inventory with timeframe/state
asta --health                         # provider + credential + history status
asta --once [--dry-run]               # one cycle
asta --once --markets crypto,stock    # market filter
asta --once --scanners CXS002_VOLUME_SPIKE
asta                                  # scheduler loop
```

## Credentials

* **Crypto** — Binance public REST, no key required.
* **Forex** — `OANDA_API_TOKEN` (+ optional `OANDA_ACCOUNT_ID`) for a practice account.
  Missing token degrades gracefully: forex scanners log a provider error, other markets keep running.
* **Stock** — Yahoo Finance chart endpoint, no key required.
* **Discord** — `DISCORD_WEBHOOK_FOREX`, `DISCORD_WEBHOOK_CRYPTO`, `DISCORD_WEBHOOK_STOCK`.
  Without a webhook the alert fails loudly in the log/report instead of silently disappearing.

## Offline demo

```bash
PYTHONPATH=src .venv/bin/python scripts/scan_once.py
PYTHONPATH=src .venv/bin/python scripts/preview_alert.py
```

`scan_once.py` runs the whole pipeline against deterministic synthetic candles, so you can
verify scanners, validation, dedup and Discord payloads without any API key.

## Documentation

* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, data flow, design decisions
* [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) — scanner/provider contracts, signal schema, Discord payload, CLI
* [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) — what V0.1 covers and V0.2 candidates
* [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — conventions, adding scanners, test rules
* [AGENTS.md](AGENTS.md) — instructions for AI coding agents working in this repo
