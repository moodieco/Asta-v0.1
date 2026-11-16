# AGENTS.md

Instructions for AI coding agents and humans working in this repository.

## Non-negotiables

1. **Scanners produce signals; they never send messages.** Discord access is limited to
   `asta.integrations.discord` and `asta.services.notification_service`.
2. **One market per scanner.** `ScannerBase` rejects a config whose market differs.
3. **No network in tests.** Providers and Discord use `httpx.MockTransport`; candles come
   from `tests/fixtures/market_data.py`.
4. **Every scanner ships three files**: `scanner.py`, `config.yaml`, `README.md`.
5. **UTC everywhere** (`asta.utils.time_utils`), never naive datetimes.
6. **Python 3.9 compatible**: no `X | Y` annotations, no `match`, no walrus in odd places.
7. **Composition only in `bootstrap.py`.** Services receive collaborators, never build them.

## Before finishing a change

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q              # 130 tests, must stay green
.venv/bin/python scripts/validate_config.py
.venv/bin/asta --list-scanners             # discovery must still find every scanner
.venv/bin/asta --once --dry-run            # errors must be explainable
.venv/bin/ruff check src tests scripts     # lint
```

## Where things go

| You are adding… | Put it in |
|---|---|
| Strategy logic shared by markets | `markets/strategies/<name>.py` |
| Market-tuned defaults | `markets/strategies/<market>_<name>.py` (same folder, market prefix) |
| Indicator maths used by several markets | `core/indicators/` |
| Market-specific indicator helper (sessions, gaps, percentile) | `markets/<market>/indicators/` |
| New provider / broker | `providers/<market>/<broker>/` (`client.py` + `candles.py`) |
| New persistence | `storage/` (`database.py`, `repositories/`, `models/`) |
| Orchestration | `services/` |
| Dashboard HTTP surface (read-only API + SPA) | `web/` |
| Desktop launcher (start/stop/status) | `launcher/` |
| Quick setup (state, secrets, validators, YAML writer) | `setup/` |
| React dashboard source | `web/` (repo root) |

## Invariants worth tests

* `Signal.dedup_key` = market:scanner:symbol:timeframe:direction.
* A still-forming candle is never scanned (`filter_closed_candles`).
* Rejected signals never reach storage or Discord.
* Delivery failures are reported but the signal stays persisted.
* Event bus handlers cannot break a cycle.

## Files that must stay in sync

* `config/markets.yaml: scanner_overrides` ⇄ scanner ids.
* `README.md` scanner table ⇄ `asta --list-scanners`.
* `docs/API_DOCUMENTATION.md` ⇄ public contracts.
* `docs/DATABASE_SCHEMA.md` ⇄ `storage/database.py` schema.
