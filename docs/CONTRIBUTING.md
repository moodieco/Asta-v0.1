# Contributing to ASTA

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
```

## Layout rules

* `core/` holds contracts and engine code; it never imports `services`, `providers`,
  `integrations` or `storage` implementations.
* `services/` orchestrate; they receive collaborators, they do not construct them.
* `bootstrap.py` is the only composition root.
* Market-specific code stays under `markets/<market>/`.
* Indicator maths shared by several markets belongs in `core/indicators/`.

## Conventions

* Python 3.9 compatible; type hints on public functions.
* UTC everywhere (`asta.utils.time_utils`).
* Errors derive from `AstaError`; wrap third-party failures at the adapter boundary.
* No new runtime dependency without justification — current footprint is
  `pydantic`, `httpx`, `PyYAML` (optional `websockets` for streaming).
* No reformatting of unrelated files in a PR.

## Tests

| Directory | Covers |
|---|---|
| `tests/unit/core` | models, scanner contract, registry, dedup, validator, services, scheduler, config, event bus, universes |
| `tests/unit/{forex,crypto,stock}` | scanner behaviour per market |
| `tests/integration/providers` | provider payloads, retries, websocket parsing |
| `tests/integration/discord` | embeds, routing, webhook client behaviour |
| `tests/integration/core` | SQLite repository |
| `tests/e2e` | full cycle through `AstaApp` |

Rules: no live network, no sleeps for timing (inject clocks), deterministic fixtures from
`tests/fixtures/market_data.py`, and every bug fix starts with a failing test.

## Adding a scanner

Follow `docs/SCANNER_GUIDE.md`. Checklist: folder with `scanner.py` + `config.yaml` +
`README.md`, strategy in `strategies/`, at least three tests, README table updated,
`scripts/validate_config.py` clean.

## Pull requests

* One concern per PR; describe behaviour change, not file list.
* Update `docs/API_DOCUMENTATION.md`, `docs/SIGNAL_SPECIFICATION.md` or
  `docs/DATABASE_SCHEMA.md` when a contract changes.
* CI runs `pytest` (3.9/3.11/3.12) and `ruff check`.
