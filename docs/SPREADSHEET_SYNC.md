# Spreadsheet sync

Every accepted signal is stored in SQLite (`data/history/asta.db`) and can be mirrored to a
spreadsheet. Two drivers share one row contract:

| Driver | Target | Auth | Use |
|---|---|---|---|
| `csv` | `data/history/signals_export.csv` | none | open/import in Google Sheets or Excel immediately |
| `google` | a Google Sheet | service account key or OAuth token | live rows, no manual import |

## Configuration — `config/sheets.yaml`

```yaml
enabled: true
driver: google                    # csv | google
csv_path: data/history/signals_export.csv
state_path: data/history/sheet_sync_state.json
spreadsheet_id: ""                # required for google
sheet_name: Signals
create_if_missing: true
service_account_path: ~/.asta/google_service_account.json
token_path: ~/.hermes/google_token.json
batch_size: 200
auto_sync: true
```

## Idempotency

`data/history/sheet_sync_state.json` stores the last exported `recorded_at`:

```json
{
  "last_recorded_at": "2026-11-13T21:31:37.126739Z",
  "total_rows": 2,
  "updated_at": "2026-11-13T21:31:37.364153Z"
}
```

Each run asks history for rows newer than the cursor (`recorded_after`), appends them, then
moves the cursor — restarts and repeated runs never duplicate rows. `--reset-cursor`
re-exports everything.

## Commands

```bash
PYTHONPATH=src python scripts/export_signals.py                # export new rows
PYTHONPATH=src python scripts/export_signals.py --dry-run      # preview pending rows
PYTHONPATH=src python scripts/export_signals.py --reset-cursor # re-export all
PYTHONPATH=src python scripts/export_signals.py --out ~/asta.csv
.venv/bin/asta --sync-sheet                                    # via the CLI
```

`auto_sync: true` also exports after each cycle (`cycle.completed` event).

## Columns

`recorded_at, timestamp, market, scanner_id, symbol, timeframe, signal_type, confidence,
entry, stop_loss, take_profit, risk_reward, risk_pct, atr, levels_source, expires_at,
status, realized_r, bars_held, strategy, reason, indicators, signal_id, source`

`indicators` renders as `key=value, key=value`; numeric columns stay numeric.
`status` / `realized_r` / `bars_held` are filled by `scripts/update_outcomes.py`
(or immediately for backfilled rows). `source` is `live` or `backfill`.

After a header change or outcome update, rewrite the tab instead of appending:

```bash
PYTHONPATH=src python scripts/export_signals.py --rewrite
```

## Google Sheets with a service account (recommended)

Service accounts authenticate without a browser but **cannot own Drive files** — Google
returns `Service Accounts do not have storage quota`. So the sheet is created by you and
shared with the service account:

1. Create a blank Google Sheet (or pick an existing one).
2. Share → add `astaku@akuntan-pribadi.iam.gserviceaccount.com` as **Editor**.
3. Copy the id from the URL: `docs.google.com/spreadsheets/d/<THIS_ID>/edit`.
4. Set it in `config/sheets.yaml`:
   ```yaml
   driver: google
   spreadsheet_id: <THIS_ID>
   service_account_path: ~/.asta/google_service_account.json
   auto_sync: true
   ```
5. `PYTHONPATH=src python scripts/export_signals.py` — first run writes the header, later
   runs append.

`create_if_missing` cannot work with a service account (no quota); the writer now raises an
explicit error telling you to share a sheet instead of surfacing a bare 403.

Key handling: keep the JSON key outside the repo, `chmod 600`
(`~/.asta/google_service_account.json`). If it leaks, delete the key in Google Cloud Console
and create a new one. Service-account scopes used: `spreadsheets` (read/write) and `drive`
(only for sharing/inspection).

## Google Sheets with an OAuth user token

Use this if the sheet should live in your own Drive without sharing:

1. Authorize Google Workspace once (Hermes `google-workspace` skill), which writes
   `~/.hermes/google_token.json` with `refresh_token`, `client_id`, `client_secret`.
2. `config/sheets.yaml`: `driver: google`, `service_account_path: ""`, `token_path: ...`.
3. Leave `spreadsheet_id` empty with `create_if_missing: true` to let the user account
   create the file.

## Verification status

* CSV driver + cursor semantics: unit/integration tests.
* Google writer (OAuth path): tested against a stub HTTP server — token refresh, create,
  header-once, append, auth header, 401 re-auth.
* Google writer (service-account path): JWT auth verified live against Google (token
  acquired, Drive API reachable, Sheets API reachable); file creation is blocked by Google's
  no-storage-quota rule, hence the shared-sheet flow above.
