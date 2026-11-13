# ASTA V0.1 — Architecture

## Goals

* Scan many symbols across three markets on independent schedules.
* Keep strategy logic isolated so one broken scanner cannot stop the system.
* Deliver exactly one Discord alert per (scanner, symbol, timeframe, direction) per window.
* Single process, few dependencies, runnable on a laptop.

## Layers

```
┌──────────────────────────── src/asta ────────────────────────────┐
│ main.py            CLI (argparse)                                 │
│ bootstrap.py       composition root, logging, scheduler wiring    │
│ config.py          merges config/{app,markets,logging,discord}    │
├──────────────────────────────────────────────────────────────────┤
│ services/          DataService · AnalysisService · Notification    │
│                    (orchestration; no HTTP or SQL details)         │
├──────────────────────────────────────────────────────────────────┤
│ core/              Signal model, ScannerBase/Registry/Manager,     │
│                    Scheduler, SignalValidator/Manager, Dedup,      │
│                    MarketManager, EventBus, indicators/            │
├──────────────────────────────────────────────────────────────────┤
│ markets/<market>/  scanners/, strategies/, indicators/, universe   │
│ providers/         binance/ · oanda/ · yahoo/ (client + candles)   │
│ integrations/      discord/ (client, embeds, router, alerts)       │
│ storage/           database · repositories · models · history      │
│ utils/             logger · time_utils · exceptions                │
└──────────────────────────────────────────────────────────────────┘
```

Dependency rule: `core` never imports `services`, `providers`, `integrations` or `storage`
implementations; `services` orchestrate `core` + `providers` + `storage`; only `bootstrap`
knows concrete classes.

## One cycle

1. `ScannerScheduler` ticks (default 60 s) and selects scanners that are due
   (half their timeframe, floored at the tick).
2. `AnalysisService.run_cycle(scanner_ids)`:
   * for each scanner × symbol: `DataService.build_context()` → candles (TTL cached 30 s,
     forming bar dropped by the provider) → `scanner.scan(context)`;
   * errors per symbol are recorded, never fatal;
   * `SignalManager.process(signals)` validates → dedupes → persists → notifies;
   * publishes `cycle.started`, `signal.detected`, `signal.accepted`, `scan.failed`,
     `cycle.completed` on the `EventBus`.
3. `CycleReport` returns counters (`contexts_built`, `signals_detected/accepted/rejected/
   delivered`, `errors`) — printed by `asta --once`, logged by the scheduler.

## Components

| Module | Responsibility |
|---|---|
| `config.py` | load 4 YAML files, expand `${VAR}`, merge, validate |
| `bootstrap.py` | build providers → services → scheduler; own logging setup |
| `core/signal_model.py` | `Candle`, `ScanContext`, `Signal`, `Market`, `SignalType` |
| `core/scanner_base.py` | scanner contract, config merge, signal construction |
| `core/scanner_registry.py` | `@register_scanner`, discovery, per-scanner `config.yaml` |
| `core/scanner_manager.py` | scanner collection + `CycleReport` |
| `core/scanner_scheduler.py` | async tick loop, due calculation, graceful stop |
| `core/market_manager.py` | provider lookup, market settings, shipped defaults + universes |
| `core/event_bus.py` | synchronous pub/sub with isolated handlers |
| `core/indicators/` | pure math: trend, momentum, volatility, volume, structure |
| `services/data_service.py` | candles with TTL cache, context building, provider health |
| `services/analysis_service.py` | cycle orchestration, event publishing |
| `services/notification_service.py` | dispatch + labelled test/sample alerts |
| `providers/base.py` | `BaseHttpClient` (retries, rate limits) + provider contract |
| `storage/` | SQLite database + signal repository + JSONL history + TTL cache |
| `integrations/discord/` | webhook client, embeds, routing, alert counters |
| `utils/` | logging (console + rotating file), timeframe maths, exceptions |

## Key decisions

1. **Sync pipeline, async only at the edge.** Providers/storage/Discord are blocking;
   the scheduler runs each cycle in a worker thread so HTTP cannot stall the loop.
2. **One config file per scanner.** Code owns identity/strategy, YAML owns timeframe,
   symbols and tunables. Deployment overrides live in `config/markets.yaml`.
3. **Market defaults ship with the code.** `markets/<market>/market_config.yaml` +
   `universe.py` define sensible symbols; deployment config overrides them.
4. **Validation is structural.** `SignalValidator` checks ranges, staleness, finite
   indicators. Strategy quality lives in `confidence`, which is a ranking score.
5. **Dedup before persistence.** A duplicate never reaches storage or Discord.
6. **Failures are per symbol.** Provider/scanner errors land in `CycleReport.errors`;
   the cycle and the scheduler keep going.
7. **Storage is swappable.** `storage.backend: jsonl | sqlite` selects the implementation
   behind the `append/load_all/tail/count/stats` interface.

## Deduplication

`dedup_key = market:scanner_id:SYMBOL:timeframe:direction`

TTL = `min(2 × timeframe_seconds, storage.dedup_window_seconds)`.
A 15m volume spike cannot re-alert the same symbol for 30 minutes; daily scanners are
capped by `dedup_window_seconds` (3600 s by default — raise it for candle-accurate dedup).

## Failure handling

| Failure | Behaviour |
|---|---|
| Provider HTTP error / bad payload | 3 attempts with backoff (429 honours `Retry-After`), then `ProviderError` per symbol |
| Missing OANDA token | `ConfigurationError` at fetch time; other markets continue |
| Scanner exception | wrapped in `ScannerError`, recorded, cycle continues |
| Invalid signal | rejected with a machine-readable code, counted, never delivered |
| Discord 4xx | not retried, surfaced in `delivery_errors` |
| Discord 429/5xx | retried with `retry_after` |
| Crash inside a cycle | caught by the scheduler, logged, loop continues |
| Event handler exception | logged and swallowed |

## Resources

* One `BaseHttpClient` per provider, closed in `AstaApp.close()`.
* Candles cached for 30 s per (market, symbol, timeframe, limit).
* Dedup cache holds one small record per active window.
* Storage: JSONL line per accepted signal, or a row in `signals` (SQLite, WAL).
