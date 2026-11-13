# Scanner guide

How to add a scanner without touching the pipeline.

## 1. Folder

```
src/asta/markets/<market>/scanners/<ID>/
├── __init__.py
├── scanner.py        # identity + strategy wiring (thin)
├── config.yaml       # timeframe, symbols, params  <- the only file you tune
└── README.md         # entry conditions, params, when it stays quiet
```

ID convention: `FXS###` forex, `CXS###` crypto, `STS###` stock, upper snake case.

## 2. Strategy first

Put the logic in a strategy class so it is testable without a scanner:

```python
# markets/strategies/my_setup.py  (shared) or markets/<market>/strategies/my_setup.py (tuned)
from asta.core.strategy import Strategy, StrategyResult
from asta.core.indicators import ema, rsi_series

class MySetupStrategy(Strategy):
    name = "My Setup"
    default_params = {"fast": 20, "slow": 50, "min_confidence": 0.55, "min_candles": 60}

    def evaluate(self, context):
        context.require(int(self.param("min_candles")))
        fast, slow = ema(context.closes, self.param("fast")), ema(context.closes, self.param("slow"))
        if fast is None or slow is None or fast <= slow:
            return []
        return [StrategyResult(
            signal_type=SignalType.LONG,
            confidence=0.6,
            reason="EMA{} above EMA{} with RSI {:.1f}".format(
                self.param("fast"), self.param("slow"), rsi_series(context.closes)[-1] or 0),
            indicators={"ema_fast": fast, "ema_slow": slow},
        )]
```

Rules: no IO, no Discord, no config reads; return `[]` when there is nothing to say.

## 3. Scanner

```python
from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.crypto.strategies.my_setup import CryptoMySetupStrategy

@register_scanner
class MySetupScanner(ScannerBase):
    id = "CXS099_MY_SETUP"
    name = "My Setup"
    market = Market.CRYPTO
    default_timeframe = "1h"
    strategy = "My Setup"
    min_candles = 90
    default_params = CryptoMySetupStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = CryptoMySetupStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> list:
        return self.signals_from(context, self.impl.evaluate(context))
```

## 4. config.yaml

```yaml
id: CXS099_MY_SETUP
name: My Setup
market: crypto
timeframe: 1h
enabled: true
symbols: []          # empty -> market universe (markets/<market>/market_config.yaml)
description: >
  One paragraph: what edge this captures and what invalidates it.
params:
  fast: 20
  slow: 50
  min_confidence: 0.55
```

Deployment tuning goes in `config/markets.yaml` under `scanner_overrides`, not here.

## 5. Tests

`tests/unit/<market>/test_<market>_scanners.py`:

1. fires on the intended pattern (assert `signal_type`, confidence floor, key indicators),
2. stays quiet on a non-matching pattern,
3. raises `InsufficientDataError` with too few candles,
4. rejects a context from another market.

Candles must be deterministic: build them with `tests/fixtures/market_data.py`
(`make_context`, `make_candles`, pattern helpers). Never call a live API.

## 6. Verify

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_config.py
.venv/bin/python scripts/inspect_market.py --market crypto --symbols BTCUSDT --timeframes 1h
```

`inspect_market.py` prints the indicator values and every scanner's verdict for a symbol,
which is the fastest way to see why a scanner stayed quiet.
