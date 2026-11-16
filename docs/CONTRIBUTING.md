# Contributing to ASTA

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts

# dashboard changes need the frontend checks too
cd web && npm ci && npx tsc -p tsconfig.json --noEmit && npm run build
```

## Layout rules

* `core/` holds contracts and engine code; it never imports `services`, `providers`,
  `integrations` or `storage` implementations.
* `services/` orchestrate; they receive collaborators, they do not construct them.
* `bootstrap.py` is the only composition root.
* **All** strategies live in `markets/strategies/`: `<name>.py` for the generic
  implementation, `<market>_<name>.py` for the tuning subclass. Never add
  `markets/<market>/strategies/` again — that split duplicated algorithm bodies.
* Market-only plumbing (sessions, overnight gaps, universes) stays under
  `markets/<market>/indicators/` and `markets/<market>/universe.py`.
* Indicator maths shared by several markets belongs in `core/indicators/`.
* The dashboard HTTP layer lives in `src/asta/web/`; it never imports `AstaApp` —
  everything arrives through injected callables, which keeps it testable without an engine.

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
