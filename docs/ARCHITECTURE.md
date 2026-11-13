# ASTA V0.1 — Architecture

## Goals

* Scan many symbols across three markets on independent schedules.
* Keep strategy logic isolated per scanner so one broken scanner cannot stop the system.
* Deliver exactly one Discord alert per (scanner, symbol, timeframe, direction) per window.
* Stay single-process, dependency-light, and runnable on a laptop.

## Data flow

```
             +----------------------+        +----------------------+
             | MarketDataProvider   |        |  ScannerRegistry     |
             | binance/oanda/stock  |        |  discover + configs  |
             +----------+-----------+        +----------+-----------+
                        |                               |
                        v                               v
             +----------------------+        +----------------------+
             |   MarketManager      |<------>|   ScannerManager     |
             |  provider + symbols  |        |  (one cycle = scans) |
             +----------+-----------+        +----------+-----------+
                        |                               |
                        |  ScanContext (candles)        |  List[Signal]
                        v                               v
             +------------------------------------------------------+
             |                    SignalManager                     |
             |  SignalValidator -> DeduplicationStore -> History     |
             |                          |                            |
             |                          v                            |
             |                    AlertManager -> DiscordRouter     |
             +------------------------------------------------------+
```

`ScannerScheduler` ticks every `scheduler.tick_seconds` and asks `ScannerManager` to run
the scanners that are due (half their timeframe, floored at the tick). Each cycle runs in
a worker thread so blocking HTTP does not stall the event loop.

## Components

| Module | Responsibility |
|---|---|
| `core/signal_model.py` | `Candle`, `ScanContext`, `Signal`, `Market`, `SignalType` (pydantic v2) |
| `core/scanner_base.py` | scanner contract, config merging, signal construction, error wrapping |
| `core/scanner_registry.py` | `@register_scanner`, package discovery, YAML config loading, overrides |
| `core/scanner_manager.py` | runs scanners over symbols, aggregates a `CycleReport` |
| `core/scanner_scheduler.py` | async tick loop, per-timeframe cadence, graceful stop |
| `core/market_manager.py` | provider selection, symbol lists, `ScanContext` building, health |
| `core/signal_validator.py` | deterministic sanity gate (confidence, age, price, reason, indicators) |
| `core/deduplication.py` | key = market:scanner:symbol:timeframe:direction, TTL window per timeframe |
| `core/signal_manager.py` | validate -> dedupe -> persist -> notify, with rejected/error accounting |
| `core/strategy.py` | `Strategy` + `StrategyResult` (pure strategy layer used by scanners) |
| `providers/*` | candle fetching, retries/backoff, rate-limit handling, payload validation |
| `integrations/discord/*` | channel config, embeds, webhook client, routing, alert counters |
| `storage/cache.py` | thread-safe TTL cache (dedup store, memoisation) |
| `storage/signal_history.py` | append-only JSONL, flush + fsync per accepted signal |
| `utils/*` | logging, timeframe maths, exception hierarchy |

## Key decisions

1. **Synchronous pipeline, async only at the edge.** Providers, Discord and storage use
   blocking IO; `ScannerScheduler` is the only async component. This keeps tests trivial
   and the failure modes obvious.
2. **One config file per scanner.** Code holds identity and strategy wiring; YAML holds
   timeframe, symbols and tunables, so tuning never touches Python.
3. **Config overrides live centrally.** `config/asta.yaml: scanner_overrides` may override
   `enabled`, `timeframe`, `params` and `symbols` per scanner without editing its file.
4. **Validation is deterministic.** `SignalValidator` checks structural sanity only
   (ranges, staleness, finite indicators). Strategy quality lives in the confidence score.
5. **Dedup before persistence.** A rejected duplicate never reaches history or Discord, so
   the JSONL file is a true alert log.
6. **Failures are per symbol.** A provider error or scanner bug is captured in
   `CycleReport.errors`; the cycle keeps going and the scheduler keeps ticking.
7. **No secrets in the repo.** Discord webhooks and OANDA tokens come from `.env`
   (`${VAR}` expansion in YAML) and are never logged unmasked.

## Deduplication semantics

`dedup_key = market:scanner_id:SYMBOL:timeframe:direction`

TTL = `min(2 x timeframe_seconds, storage.dedup_window_seconds)`.

So a 15m spike scanner cannot re-alert the same symbol for 30 minutes, while a daily
scanner stays quiet for two days (capped at one hour by default — raise
`dedup_window_seconds` if you want candle-accurate dedup on higher timeframes).

## Failure handling

| Failure | Behaviour |
|---|---|
| Provider HTTP error / bad payload | retried 3x with backoff (429 honours `Retry-After`), then `ProviderError` logged per symbol |
| Missing credentials (OANDA) | `ConfigurationError` at fetch time; market skipped, others continue |
| Scanner exception | wrapped in `ScannerError`, recorded in `CycleReport.errors` |
| Invalid signal | rejected with a machine-readable reason, counted, never delivered |
| Discord 4xx | not retried, reported in `delivery_errors` |
| Discord 429/5xx | retried with the server's `retry_after` |
| Crash inside a cycle | caught by the scheduler, logged, loop continues |

## Resources

* One HTTP client per provider, created lazily and closed in `AstaApp.close()`.
* Memory: dedup cache holds one small record per active signal window.
* Storage: one JSONL line per accepted signal (`data/signal_history.jsonl`).
