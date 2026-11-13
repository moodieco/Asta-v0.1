# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.

## Ground rules

1. **Scanners produce signals; they never send messages.** Discord access is only
   allowed through `asta.integrations.discord`. A scanner that imports `httpx` or a
   webhook URL is a bug.
2. **One market per scanner.** `ScannerBase` validates `config.market == scanner.market`
   at construction; do not weaken this check.
3. **No network in tests.** Use `httpx.MockTransport` for providers/Discord and
   `tests/helpers.py` for deterministic candles. Never call live APIs from a test.
4. **Every scanner needs a config.yaml** next to `scanner.py`; discovery and the registry
   both rely on it.
5. **Time is UTC everywhere.** Use `asta.utils.time_utils.utcnow` / `ensure_utc`.
6. Keep the code Python 3.9 compatible (no `X | Y` annotations, no `match`).

## Before finishing any change

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q          # must stay green (91 tests today)
.venv/bin/asta --list-scanners         # discovery must still find every scanner
.venv/bin/asta --once --dry-run        # must not raise; errors list should be explainable
```

## Adding a scanner (checklist)

1. Create `src/asta/markets/<market>/scanners/<ID>/`.
2. Add `__init__.py`, `scanner.py`, `config.yaml` (copy an existing scanner).
3. Put reusable logic in `markets/strategies/` (shared) or `markets/<market>/strategies/`
   (market-tuned subclass). Scanners should stay ~30 lines.
4. Reuse `markets/indicators/` instead of re-deriving math inline.
5. Add `tests/<market>/test_*.py` covering: fires on the intended pattern, stays quiet
   otherwise, and emits the expected `signal_type`.
6. Run the checks above; extend README's scanner table.

## Files that must stay in sync

* `config/asta.yaml` `scanner_overrides` keys ⇄ scanner ids.
* `docs/API_DOCUMENTATION.md` ⇄ public contracts (`Signal`, `ScannerBase`,
  `MarketDataProvider`, `DeliveryResult`).
* `README.md` scanner table ⇄ discovered scanners.
