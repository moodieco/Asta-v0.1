# Security notes

V0.1 reads public market data and posts to Discord webhooks. It holds no exchange trading
permissions and executes no orders.

## Secrets

| Secret | Where | Notes |
|---|---|---|
| `DISCORD_WEBHOOK_*` | `.env` only | treated as credentials: anyone with the URL can post |
| `OANDA_API_TOKEN` | `.env` only | practice token is enough for V0.1 |

* `.env` is gitignored and created with `0600` permissions.
* YAML only references secrets as `${VAR}`; the loader expands them in memory.
* Logs never print full webhook URLs: `ChannelConfig.masked()` and health output show
  `https://...abcd` only.
* CLI output for `--health` lists market names, not URLs.

## Webhooks

* A Discord webhook URL is a bearer credential for one channel — do not paste it into
  issues, screenshots, or commits. If leaked, delete and recreate it in Discord.
* Delivery validates the URL shape (`https://…/api/webhooks/…`) before sending.
* Rate limits (429) are honoured via `Retry-After`; repeated failures are reported in
  `delivery_errors` rather than retried forever (max 3 attempts).

## Dry-run and test modes

* `asta --once --dry-run` never posts.
* `--test-alert` and `--sample-alert` post **explicitly labelled** messages
  (`🧪 ASTA TEST ALERT`, `🧪 SAMPLE`) so no one mistakes them for trading signals.
* `ASTA_DRY_RUN=1` forces dry-run for the whole process.

## Market data

* Binance and Yahoo endpoints are public and need no key.
* OANDA requests use a bearer token over HTTPS; no account/order endpoints are called
  (`/v3/instruments/.../candles` and `/v3/accounts/.../pricing` are read-only).
* Candle data is used for analysis only; no order routing exists in this codebase.

## Logging and exposure

* Console + rotating file (`data/logs/asta.log`, 5 MB × 3).
* Log fields include scanner id, symbol, status codes, error messages — never secrets.
* `logging.format: json` produces machine-readable lines for ingestion.

## Hardening checklist for deployment

- [ ] Run as an unprivileged user, not root.
- [ ] Keep `.env` out of backups that leave the machine, or store secrets in a vault.
- [ ] Restrict outbound traffic to the provider domains and `discord.com` if possible.
- [ ] Rotate webhooks if the host is shared or the repo is ever made public.
- [ ] Review `data/history/` retention — signals reveal your strategies.
