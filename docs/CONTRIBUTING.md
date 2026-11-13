# Contributing to ASTA

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

## Conventions

* Python 3.9 compatible (the project targets 3.9+); use `typing.List/Optional/Dict`.
* Type hints on public functions; docstrings state the contract, not the implementation.
* UTC everywhere; never `datetime.now()` without a timezone.
* No new runtime dependencies without a strong reason — the V0.1 footprint is
  `pydantic`, `httpx`, `PyYAML` (plus `pytest` for dev).
* One responsibility per module; scanners must not know about Discord or storage.
* Errors derive from `AstaError` so the scheduler can distinguish expected failures from bugs.

## Adding a scanner

1. `src/asta/markets/<market>/scanners/<ID>/{__init__.py,scanner.py,config.yaml}`
2. Scanner class: id, name, market, `default_timeframe`, `strategy`, `min_candles`,
   `default_params`; delegate to a strategy module.
3. Strategy: shared logic in `markets/strategies/`, market tuning in
   `markets/<market>/strategies/`. Return `StrategyResult` objects.
4. Reuse `markets/indicators/`; add new indicator maths there with unit tests.
5. Tests in `tests/<market>/`: fires on the intended pattern, stays quiet otherwise,
   correct `signal_type`/confidence floor. Deterministic candles only — see `tests/helpers.py`.

## Tests

* `tests/core` — models, scanner contract, registry, dedup, validator, managers, scheduler, config
* `tests/forex|crypto|stock` — scanner behaviour per market
* `tests/integrations` — Discord client/router/embeds, provider payload parsing
* `tests/test_app.py` — end-to-end cycle with a stub provider and tmp history

Rules:

* No live network calls. Providers and Discord are exercised with `httpx.MockTransport`.
* Time-sensitive tests must inject clocks (`FakeClock`) rather than sleeping.
* A bug fix needs a failing test first; a new scanner needs at least three tests.

## Pull requests

* Keep diffs focused; do not reformat unrelated files.
* Update `README.md` scanner table and `docs/API_DOCUMENTATION.md` when contracts change.
* CI runs `pytest -q` on Python 3.9 / 3.11 / 3.12.
