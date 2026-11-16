# Deploy ASTA on Render

One web service, built from `Dockerfile` (Vite dashboard + Python engine in one
image), configured by `render.yaml`. Push to GitHub → Render builds → a
long-running process serves the dashboard on HTTPS and keeps the scanner loop
alive.

## 0. What Render gives you (and what it does not)

| | |
|---|---|
| Public HTTPS URL | Yes, `https://<service>.onrender.com`, TLS handled by Render |
| WebSocket/SSE | Not used — the SPA polls `/api/*` |
| Free plan | **Sleeps after ~15 min idle.** The scanner stops while asleep; use `starter` |
| Persistent disk | Paid plans only. Without it, history/scanner library reset on every deploy |
| MT5 forex | Impossible: needs a Windows MetaTrader terminal. Disable forex or use OANDA |

## 1. Prepare the repo (once)

1. Push `asta-v0.1` to GitHub (private is fine).
2. Decide forex. On a server there is no MT5 terminal, so either provide the
   public market-data fallback (`MT5_MARKETDATA_URL` + `MT5_MARKETDATA_TOKEN`)
   or disable it in `config/markets.yaml`:

   ```yaml
   markets:
     forex:
       enabled: false
   ```

3. Commit `config/app.yaml` with provider settings referencing env vars
   (`${MT5_...}`, `${OANDA_...}`) — never literal secrets. `config/setup_state.json`
   is not needed: `ASTA_SETUP_COMPLETE=1` skips the first-run wizard.

## 2. Create the service

Render → **New → Blueprint** → pick the repo. It reads `render.yaml` and asks
for the `sync: false` values.

> `render.yaml` tracks `branch: main`. If the deployment work is still on
> `feat/web-launcher`, either merge it into `main` first or change that one line
> — otherwise Render builds a branch without the Dockerfile.

| Variable | Value |
|---|---|
| `ASTA_EDITOR_TOKEN` | `openssl rand -hex 24` — full control |
| `ASTA_VIEWER_TOKEN` | `openssl rand -hex 24` — read-only |
| `DISCORD_WEBHOOK_CRYPTO` / `_STOCK` / `_FOREX` | webhook URLs from Discord (optional) |
| `MT5_TERMINAL_URL` / `MT5_TERMINAL_TOKEN` | only if you run an MT5 MCP elsewhere |

Set by the blueprint, no action needed:

| Variable | Why |
|---|---|
| `ASTA_DATA_DIR=/var/data` | history, scanner library, alert log, share.json live on the disk |
| `ASTA_SETUP_COMPLETE=1` | no setup wizard on every boot |
| `ASTA_LOG_FORMAT=json` | Render's log viewer parses it |
| `PORT` | injected by Render; the image binds `0.0.0.0:$PORT` |

## 3. First open

```
https://<service>.onrender.com/?token=<ASTA_EDITOR_TOKEN>
```

The token sets an `HttpOnly` cookie, so the dashboard keeps working without the
query string afterwards. Send the **viewer** token to anyone who only needs to
look; editor can install scanners, toggle them and regenerate tokens.

Health check: `GET /healthz` → `{"ok": true}`. It is the only unauthenticated
path (it exposes no data), so Render can probe it without a share token.

## 4. Deploys and your data

* `git push` to the tracked branch → Render rebuilds the image → the disk at
  `/var/data` is reattached, so signals and installed scanners survive.
* Tokens come from env vars, so links do not change between deploys. Rotating
  them = change the env var and redeploy (or POST `/api/share/regenerate` while
  `ASTA_EDITOR_TOKEN` is unset).
* A fresh deploy with no disk starts from an empty `asta.db`: the dashboard
  shows zero signals until the first scan cycle (60 s) writes some.

## 5. Verify after deploy

```bash
curl -s https://<service>.onrender.com/healthz                       # {"ok":true}
curl -s https://<service>.onrender.com/api/access                    # 401 without a token
curl -s "https://<service>.onrender.com/api/access?token=$VIEWER"    # {"access":"viewer"}
curl -s -o /dev/null -w '%{http_code}\n' "https://<service>.onrender.com/?token=$EDITOR"  # 200
```

Then in the UI: Overview should show the engine as *Running*, scanner count 9
(or 8 if forex is off), and the range picker / dark mode working.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Deploy fails at `npm ci` | `web/package-lock.json` out of sync with `package.json`; run `npm install` locally and commit |
| `dashboard build missing` in logs | `web/dist` was not generated — the Dockerfile's `web` stage builds it; check the build log for the Vite error |
| 401 on every URL | Token missing or doesn't match the env var |
| Engine shows *Offline* | Process crashed on boot: read the Render log for the `ASTA ready` line |
| Free plan shows stale data | Service slept; upgrade to `starter` |
| Disk permission errors | Render mounts the disk root-owned. `docker/entrypoint.sh` fixes ownership then drops to uid 10001; if the log shows `could not chown`, the mount path differs from `ASTA_DATA_DIR` |
