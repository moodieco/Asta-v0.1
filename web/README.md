# ASTA — Signal Performance UI

A local, read-only dashboard for the signal history in `data/history/asta.db`.
Built with Vite + React 19 + Tailwind v4 + [Magic UI](https://magicui.design) components
(`number-ticker`, `magic-card`, `border-beam`, `dot-pattern`) and Recharts.

## Run

```bash
cd ui
npm install          # once
npm run dev          # http://localhost:4310
```

Production build:

```bash
npm run build
npm run preview      # http://localhost:4310
```

## Data

The UI never touches SQLite directly. It reads a single JSON snapshot:

```
src/data/asta.json     <- generated, ~950 KB, 1.4k signals
```

Regenerate after the scanner writes new signals:

```bash
python3 scripts/export_dashboard.py            # from the repo root
python3 scripts/export_dashboard.py --limit 500
```

The exporter opens the database read-only (`mode=ro`), so it is safe to run while
ASTA is live. `meta` in the JSON carries the snapshot time, win rate, expectancy,
net R and profit factor; every derived chart filters/aggregates from the raw rows
in the browser, which is what makes the All-time / 90d / 30d switch instant.

## Views

- **Overview** — KPI cards, cumulative R, streak + long/short diagnostics, R
  distribution, confidence calibration, 26-week signal rhythm calendar.
- **Performance** — net R by scanner, timeframe breakdown, scanner ledger
  (win rate / expectancy / PF / max DD), symbol map.
- **History** — every signal, searchable and filterable by status, scanner,
  market, timeframe; sortable; click any row for a detail drawer with the reason,
  R:R, levels and timeline.

## Conventions

- R multiples come straight from `realized_r`; nothing is recomputed from prices.
- Green = positive R, rose = negative. Nothing else uses those two hues.
- All numbers use tabular figures so columns do not jitter.
- Dark-only by design; the palette is defined once in `src/index.css` under
  `@theme` — change `--color-up` / `--color-down` there to re-skin.
