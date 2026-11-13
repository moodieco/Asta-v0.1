# ASTA — Development roadmap

## V0.1 (current) — detect and notify

Shipped:

- [x] Layered codebase: `core` (engine) · `services` (orchestration) · `providers` ·
      `storage` · `integrations` · `markets`, wired only in `bootstrap.py`
- [x] Scanner contract, registry with discovery, per-scanner `config.yaml` + README
- [x] Scheduler with per-timeframe cadence, worker-thread cycles, graceful stop
- [x] Signal pipeline: validator → dedup → storage → Discord, with rejection codes
- [x] Event bus (`cycle.*`, `signal.*`, `scan.failed`) with isolated subscribers
- [x] Providers: Binance REST (+ optional websocket module), OANDA candles/pricing,
      Yahoo chart; retries, rate limits, closed-candle filtering
- [x] Storage: JSONL or SQLite (`signals` table, repository, row model) in one switch
- [x] Discord: webhook client, embeds, per-market routing, labelled test/sample alerts
- [x] Config split into app/markets/logging/discord, `${VAR}` expansion, dry-run
- [x] Market defaults shipped in code (`market_config.yaml`, `universe.py`) with
      market-specific indicator helpers (sessions, volume percentile, overnight gaps)
- [x] Tooling: CLI, 5 scripts, validate/test/status/inspect, offline demo
- [x] 122 tests across unit/integration/e2e; CI: pytest matrix + ruff

Known limitations:

- No order execution, positions or PnL — notification only.
- Single process; SQLite is local, no migration framework.
- Stock data via Yahoo's public chart endpoint (unofficial, rate limited).
- Forex scanners require an OANDA token; the trial runs without it.
- Confidence has not been calibrated against outcomes (no backtester yet).
- Binance websocket path exists but is not wired into the pipeline.
- `data/cache/` is reserved; candle caching is in-memory (30 s TTL).

## V0.2 — signal quality and resilience

- [ ] Backtest harness: replay historical candles, report hit rate / expectancy per scanner
- [ ] Confidence calibration from backtest results instead of hand-tuned constants
- [ ] Wire the Binance websocket to update the latest candle instead of polling
- [ ] Provider failover + circuit breaker per provider
- [ ] Retention job for `signals` (partition by month / delete old rows)
- [ ] Alert policies: per-scanner throttle, quiet hours, per-channel min confidence
- [ ] `/metrics` endpoint (Prometheus) and JSON logs by default in production

## V0.3 — operations

- [ ] Docker image + compose (app + optional Postgres)
- [ ] Multi-guild Discord routing and a dedicated test channel
- [ ] Hot reload of `config/markets.yaml` without restart
- [ ] Dashboard: signal timeline, scanner hit rate, provider latency

## V1.0 — decision support

- [ ] Portfolio-aware filtering (correlation, exposure caps)
- [ ] Paper-trading execution adapter with simulated fills
- [ ] Risk sizing suggestions attached to every alert
