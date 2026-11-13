# ASTA — Development Roadmap

## V0.1 (current) — signal detection + Discord alerting

Shipped:

- [x] Core contracts: `Signal`, `ScanContext`, `ScannerBase`, `Strategy`
- [x] Scanner registry with package discovery and per-scanner `config.yaml`
- [x] Scanner manager + async scheduler with per-timeframe cadence
- [x] Market manager (provider selection, symbol lists, health)
- [x] Signal pipeline: validator, deduplication, JSONL history, delivery accounting
- [x] Providers: Binance (crypto), OANDA (forex), Yahoo (stock)
- [x] Scanners: FXS001 RSI divergence, FXS002 EMA cross, CXS001 RSI divergence,
      CXS002 volume spike, CXS003 breakout, STS001 EMA trend, STS002 breakout
- [x] Discord: webhook client with retries, embeds, per-market routing, alert manager
- [x] Config: YAML + `.env` + `${VAR}`, per-scanner overrides, dry-run mode
- [x] CLI (`--once`, `--dry-run`, `--list-scanners`, `--health`), CI workflow
- [x] 91 tests: unit (indicators/scanners/validation/dedup), integration (providers,
      Discord), end-to-end (app cycle + dedup across cycles)

Known limitations (deliberate, V0.1 scope):

- No order execution, no positions, no PnL — notification only.
- Single process; state is in-memory + JSONL (no database).
- Stock data comes from Yahoo's public chart endpoint (unofficial, rate limited).
- Forex requires an OANDA token; without it those scanners report provider errors.
- Dedup is time-window based, not candle-close aware.
- No backtesting engine; confidence scores are heuristics, not calibrated probabilities.

## V0.2 — robustness and signal quality

- [ ] Backtest harness: replay historical candles through scanners, report hit rate/expectancy
- [ ] Confidence calibration from backtest output instead of hand-tuned constants
- [ ] Candle-close awareness (skip evaluating a forming candle; expose `is_closed`)
- [ ] Provider failover + per-provider circuit breaker
- [ ] SQLite (or Postgres) storage behind the existing `SignalHistory` interface
- [ ] Alert policies per scanner: throttle, quiet hours, min confidence per channel
- [ ] `/health` metrics endpoint (Prometheus text format) + structured JSON logs everywhere
- [ ] Stock provider options: Polygon / Alpaca / Finnhub adapters

## V0.3 — operations

- [ ] Docker image + docker-compose (app + optional Postgres)
- [ ] Multi-account Discord routing and test-channel mode
- [ ] Scanner hot-reload of `config.yaml` without restart
- [ ] Dashboard (signal timeline, scanner hit rate, provider latency)

## V1.0 — decision support

- [ ] Portfolio-aware signal filtering (correlation, exposure caps)
- [ ] Paper-trading execution adapter (orders simulated, fills recorded)
- [ ] Risk sizing suggestions attached to each alert
