# ASTA V0.1 — API documentation

Four public surfaces: **scanner contract**, **provider contract**, **services**, and the
**Discord payload**. Everything else is internal but documented for contributors.

## 1. Scanner contract

```python
from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market

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

    def evaluate(self, context):
        return self.signals_from(context, self.impl.evaluate(context))
```

`scan(context)` order: market check → `min_candles` check → `evaluate()` → identity check.
Unknown exceptions become `ScannerError`; too few candles raises `InsufficientDataError`.

### `ScanContext`

| Attribute | Type | Notes |
|---|---|---|
| `market` | `Market` | forex / crypto / stock |
| `symbol` | `str` | as requested; signals upper-case it |
| `timeframe` | `str` | canonical (1m … 1w) |
| `candles` | `List[Candle]` | oldest → newest, UTC, ordered |
| `scanner_id` | `str` | filled on the internal copy |
| `now` | `datetime` | UTC |
| `closes/highs/lows/opens/volumes` | `List[float]` | convenience |
| `last`, `price`, `last_timestamp` | — | helpers |
| `tail(n)` / `require(n)` | — | slice / raise on short data |

### `Signal`

See [SIGNAL_SPECIFICATION.md](SIGNAL_SPECIFICATION.md) for the full field contract,
validation codes and dedup rules. Key derived values:

```python
signal.dedup_key  # "crypto:CXS002_VOLUME_SPIKE:BTCUSDT:15m:long"
signal.signal_id  # "9f1c0a2e5b77"
```

## 2. Provider contract

```python
class MarketDataProvider(ABC):
    market: Market
    name: str
    def fetch_candles(self, symbol, timeframe, limit=200) -> List[Candle]: ...
    def is_configured(self) -> bool: ...
    def health_check(self) -> bool: ...
    def fetch_price(self, symbol) -> Optional[float]: ...   # binance / oanda
```

Guarantees: closed candles only (`filter_closed_candles`), UTC timestamps, oldest → newest,
`ProviderError` on any failure. `BaseHttpClient` supplies retries, backoff, `Retry-After`
handling and JSON decoding.

| Provider | Package | Endpoint | Auth |
|---|---|---|---|
| Binance | `providers/crypto/binance/` | `/api/v3/klines`, `/api/v3/ticker/price` | none |
| OANDA | `providers/forex/oanda/` | `/v3/instruments/{i}/candles`, `/v3/accounts/{id}/pricing` | `Bearer $OANDA_API_TOKEN` |
| Yahoo | `providers/stock/yahoo/` | `/v8/finance/chart/{ticker}` | none |

Optional realtime: `providers/crypto/binance/websocket.py` (`parse_kline_message`,
`stream_klines`) — requires `pip install "asta[stream]"`.

## 3. Services

### `DataService`

```python
data.build_context(scanner, symbol)          # -> ScanContext (candles cached 30 s)
data.fetch_candles(market, symbol, tf, n)    # -> List[Candle]
data.symbols(market)                         # configured -> universe fallback
data.health()                                # {"crypto": True, ...}
```

### `AnalysisService`

```python
analysis.run_cycle(scanner_ids=None, markets=None)   # -> CycleReport
analysis.inventory()                                  # scanner descriptions
```

Publishes `cycle.started`, `signal.detected`, `signal.accepted`, `scan.failed`,
`cycle.completed` on the `EventBus`.

### `NotificationService`

```python
notifications.dispatch(signal)          # -> DeliveryResult
notifications.send_test_alerts()        # labelled connectivity test per webhook
notifications.send_sample_alerts(...)   # labelled sample signal cards
```

## 4. Discord payload

```json
{
  "username": "ASTA",
  "embeds": [{
    "title": "🟢 LONG · BTCUSDT · 15M",
    "description": "Volume spike 5.2x the 20-bar average on a bullish candle (+3.00% body, 98% of range).",
    "color": 3066993,
    "fields": [
      {"name": "Market", "value": "🪙 Crypto", "inline": true},
      {"name": "Scanner", "value": "CXS002_VOLUME_SPIKE", "inline": true},
      {"name": "Strategy", "value": "Volume Spike", "inline": true},
      {"name": "Confidence", "value": "88%", "inline": true},
      {"name": "Price", "value": "104,250.50", "inline": true},
      {"name": "Time", "value": "2026-11-13T20:15:00Z", "inline": true},
      {"name": "Indicators", "value": "volume_ratio=5.2, body_ratio=0.98", "inline": false}
    ],
    "footer": {"text": "ASTA V0.1 · Volume Spike · CXS002_VOLUME_SPIKE"},
    "timestamp": "2026-11-13T20:15:00Z"
  }]
}
```

`DeliveryResult`: `ok`, `status_code`, `error`, `attempts`, `dry_run`. Webhook URLs must be
`https://…/api/webhooks/…`.

### `SheetSyncService`

```python
sync.sync_once()   # -> {"driver": "csv", "appended": 2, "total_rows": 2, "cursor": "..."}
sync.status()      # -> driver, target, cursor, total rows
```

Incremental: reads history rows newer than the cursor in `data/history/sheet_sync_state.json`,
appends them, moves the cursor. Drivers: `CsvSheetWriter`, `GoogleSheetsWriter`.

## 5. Configuration

### `config/app.yaml`

```yaml
environment: development
dry_run: false
scheduler: {tick_seconds: 60, respect_timeframe: true}
validator: {min_confidence: 0.35, max_signal_age_seconds: 3600}
storage:
  backend: jsonl              # jsonl | sqlite
  signal_history_path: data/history/signals.jsonl
  sqlite_path: data/history/asta.db
  dedup_window_seconds: 3600
  enabled: true
providers:
  binance: {base_url: "https://api.binance.com", timeout_seconds: 15, max_attempts: 3}
  oanda:   {base_url: "https://api-fxpractice.oanda.com", api_token: "${OANDA_API_TOKEN}"}
  stock:   {base_url: "https://query1.finance.yahoo.com", timeout_seconds: 20}
```

### `config/markets.yaml`

```yaml
markets:
  crypto: {enabled: true, symbols: [BTCUSDT, ETHUSDT]}
scanner_overrides:
  CXS002_VOLUME_SPIKE: {timeframe: 15m, params: {spike_multiplier: 3.0}}
```

### `config/logging.yaml`

```yaml
level: INFO
format: text            # text | json
file: data/logs/asta.log
max_bytes: 5242880
backup_count: 3
loggers: {httpx: WARNING}
```

### `config/discord.yaml`

```yaml
username: ASTA
channels:
  crypto: {env: DISCORD_WEBHOOK_CRYPTO, label: "#cryptic"}
```

### `config/sheets.yaml`

```yaml
enabled: true
driver: csv | google
csv_path: data/history/signals_export.csv
state_path: data/history/sheet_sync_state.json
spreadsheet_id: ""          # google: existing sheet, or empty + create_if_missing
sheet_name: Signals
token_path: ~/.hermes/google_token.json
batch_size: 200
auto_sync: true
```

Environment: `ASTA_CONFIG_DIR`, `ASTA_LOG_LEVEL`, `ASTA_LOG_FORMAT`, `ASTA_DRY_RUN`,
`OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`, `DISCORD_WEBHOOK_{FOREX,CRYPTO,STOCK}`.

## 6. CLI

| Command | Effect |
|---|---|
| `asta` | scheduler loop |
| `asta --once` | one cycle, prints `CycleReport` JSON |
| `asta --once --dry-run` | cycle without Discord posts |
| `asta --once --markets crypto,stock --scanners CXS002_VOLUME_SPIKE` | filters |
| `asta --list-scanners` | discovered scanners |
| `asta --health` | providers, storage, webhooks, cache, events |
| `asta --test-alert` / `--sample-alert` | labelled Discord checks |
| `asta --sync-sheet` | export new signals to the configured spreadsheet |
| `asta --config <dir>` | alternate config directory |

Exit codes: `0` ok, `1` test/sample alert failed, `2` configuration/startup error.

## 7. `CycleReport`

```json
{
  "started_at": "…", "finished_at": "…", "duration_seconds": 1.73,
  "scanners_run": 5, "contexts_built": 25,
  "signals_detected": 0, "signals_accepted": 0, "signals_rejected": 0,
  "signals_delivered": 0, "errors": []
}
```
