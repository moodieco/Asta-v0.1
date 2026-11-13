# ASTA V0.1 — API Documentation

Three public surfaces: the **scanner contract**, the **provider contract**, and the
**Discord payload**. Everything else is internal but documented for contributors.

## 1. Scanner contract

```python
from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal

@register_scanner
class MyScanner(ScannerBase):
    id = "CXS099_MY_SCANNER"
    name = "My Scanner"
    market = Market.CRYPTO
    default_timeframe = "1h"
    strategy = "My Strategy"
    min_candles = 60
    default_params = {"threshold": 1.5}

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = MyStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> list[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
```

`ScannerBase.scan(context)` performs, in order: market check → candle count check
(`min_candles`) → `evaluate()` → identity check on produced signals. Errors are wrapped in
`ScannerError`; `InsufficientDataError` is raised without enough candles.

### `ScanContext`

| Attribute | Type | Notes |
|---|---|---|
| `market` | `Market` | enum: forex / crypto / stock |
| `symbol` | `str` | upper-case in `Signal`, as provided here |
| `timeframe` | `str` | canonical: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w |
| `candles` | `List[Candle]` | oldest → newest, UTC, validated order |
| `scanner_id` | `str` | filled by `scan()` on its internal copy |
| `now` | `datetime` | UTC, defaults to now |
| `closes/highs/lows/opens/volumes` | `List[float]` | convenience |
| `last`, `price`, `last_timestamp` | — | last candle helpers |
| `tail(n)` | `List[Candle]` | last n candles |
| `require(n)` | — | raises `InsufficientDataError` |

### `Signal` (the only output of a scanner)

```json
{
  "scanner_id": "FXS001_RSI_DIVERGENCE",
  "scanner_name": "RSI Divergence",
  "market": "forex",
  "symbol": "EUR_USD",
  "timeframe": "1h",
  "signal_type": "long",
  "reason": "Regular bullish RSI divergence: price printed a lower low (-1.88%) while RSI printed a higher low (+18.8 pts, 20.0 -> 38.8).",
  "confidence": 0.81,
  "price": 1.09234,
  "timestamp": "2026-11-13T20:00:00Z",
  "strategy": "RSI Divergence",
  "indicators": {"rsi": 38.82, "rsi_prev": 20.0, "rsi_delta": 18.82},
  "metadata": {"pivot_bars_ago": 3}
}
```

`confidence` is clamped to `[0, 1]`. `dedup_key` = `market:scanner_id:SYMBOL:timeframe:signal_type`.
`signal_id` is a short hash of `dedup_key + timestamp`.

### Strategy layer

`asta.core.strategy.Strategy` holds `params` and returns `StrategyResult` objects
(`signal_type`, `confidence`, `reason`, `indicators`, `metadata`, `price`). Scanners convert
them with `ScannerBase.signals_from(context, results)`. Indicator math lives in
`asta.markets.indicators` (pure functions, no IO).

## 2. Provider contract

```python
class MarketDataProvider(ABC):
    market: Market
    name: str
    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]: ...
    def is_configured(self) -> bool: ...
    def health_check(self) -> bool: ...
```

Guarantees expected from an implementation: candles sorted oldest → newest, tz-aware UTC
timestamps, `ProviderError` on any failure (including malformed payloads), no silent
partial data.

`_request_json(url, params, headers)` from the base class provides retries with exponential
backoff, `Retry-After` support, 5xx/429 retry, and immediate failure on other 4xx.

| Provider | Endpoint | Auth | Timeframes |
|---|---|---|---|
| `BinanceProvider` | `GET {base}/api/v3/klines` | none | 1m…1w |
| `OandaProvider` | `GET {base}/v3/instruments/{instrument}/candles` | `Bearer $OANDA_API_TOKEN` | 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w |
| `StockProvider` | `GET {base}/v8/finance/chart/{ticker}` | none | 1m…1h (intraday), 1d, 1w |

## 3. Discord payload

`build_payload(signal)` → `{"username": "ASTA", "embeds": [ ... ]}`.

Embed fields: `title` (`🟢 LONG · BTCUSDT · 15M`), `description` (reason), `color`
(green long / red short), fields `Market`, `Scanner`, `Strategy`, `Confidence`, `Price`,
`Time`, optional `Indicators`, `footer` (`ASTA V0.1 · <scanner name> · <scanner id>`),
`timestamp` (ISO-8601 Z).

Delivery result (`DeliveryResult`): `ok`, `status_code`, `error`, `attempts`, `dry_run`.
Valid webhook URLs must be `https://…/api/webhooks/…`.

## 4. Configuration reference

```yaml
environment: development
log_level: INFO
dry_run: false

scheduler: { tick_seconds: 60, respect_timeframe: true }
validator: { min_confidence: 0.35, max_signal_age_seconds: 3600 }
storage:   { signal_history_path: data/signal_history.jsonl, dedup_window_seconds: 3600, enabled: true }

providers:
  binance: { base_url: "https://api.binance.com", timeout_seconds: 15 }
  oanda:   { base_url: "https://api-fxpractice.oanda.com", api_token: "${OANDA_API_TOKEN}" }
  stock:   { base_url: "https://query1.finance.yahoo.com", timeout_seconds: 20 }

markets:
  forex:  { enabled: true, symbols: [EUR_USD, GBP_USD, USD_JPY] }
  crypto: { enabled: true, symbols: [BTCUSDT, ETHUSDT, SOLUSDT] }
  stock:  { enabled: true, symbols: [AAPL, MSFT, NVDA] }

scanner_overrides:
  CXS002_VOLUME_SPIKE:
    timeframe: 15m
    params: { spike_multiplier: 3.0 }
```

Environment variables: `ASTA_CONFIG`, `ASTA_LOG_LEVEL`, `ASTA_LOG_FORMAT=json`,
`ASTA_DRY_RUN=1`, `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`, and the three
`DISCORD_WEBHOOK_*` variables. `${VAR}` placeholders inside the YAML are expanded from the
environment (`.env` is loaded automatically).

## 5. CLI

| Command | Effect |
|---|---|
| `asta` | scheduler loop until Ctrl-C |
| `asta --once` | single cycle, prints `CycleReport` JSON |
| `asta --once --dry-run` | cycle without Discord posts |
| `asta --once --markets crypto,stock` | market filter |
| `asta --once --scanners CXS002_VOLUME_SPIKE` | scanner filter |
| `asta --list-scanners` | discovered scanners + config state |
| `asta --health` | provider health, webhook coverage, history count |

Exit codes: `0` success, `2` configuration/startup error.

## 6. `CycleReport`

```json
{
  "started_at": "…", "finished_at": "…", "duration_seconds": 1.73,
  "scanners_run": 7, "contexts_built": 15,
  "signals_detected": 0, "signals_accepted": 0, "signals_rejected": 0,
  "signals_delivered": 0, "errors": ["…"]
}
```
