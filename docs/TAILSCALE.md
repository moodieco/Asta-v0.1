# Share ASTA with Tailscale Funnel

A **stable** public HTTPS address for the dashboard, with no domain, no port
forwarding and no cost:

```
https://<machine>.<tailnet>.ts.net
```

It stays the same across reboots and IP changes. It only changes if you rename the
machine or remove the node from the tailnet — unlike the cloudflared quick tunnel
in `scripts/share.sh`, whose random `trycloudflare.com` URL dies on every restart.

## How it works

`tailscale funnel` terminates TLS on Tailscale's edge and proxies to
`127.0.0.1:4310` on your machine. Tailscale adds `X-Forwarded-For`, so ASTA sees a
**remote** request and demands a share token — the dashboard is never open. The
engine, the database and the tokens stay local.

```
browser → https://asta.tailxxxx.ts.net (TLS) → tailscaled → 127.0.0.1:4310 → token gate
```

## Prerequisites (once per machine)

1. Tailscale installed and logged in:
   - macOS: `brew install --cask tailscale` (or the App Store app), then
     `tailscale up` (App Store build: `/Applications/Tailscale.app/Contents/MacOS/Tailscale up`)
   - Windows: `winget install --id Tailscale.Tailscale -e`, then `tailscale up`
   - Linux: `curl -fsSL https://tailscale.com/install.sh | sh`, then `sudo tailscale up`
2. In <https://login.tailscale.com/admin/dns> enable **both**:
   - MagicDNS (without it the `*.ts.net` name does not resolve)
   - HTTPS Certificates (without it `tailscale funnel` refuses to start)
3. The dashboard must be running: `asta serve --host 127.0.0.1 --port 4310 --no-browser`

## Turn it on

```bash
./scripts/share-tailscale.sh            # macOS / Linux
```
```powershell
.\scripts\share-tailscale.ps1           # Windows
```

The script starts the dashboard if needed, enables the funnel on port 4310, then
prints four links: viewer/editor × funnel/local. `--status` shows what the funnel
serves now; `--off` stops public access (`tailscale funnel reset`) without touching
the dashboard.

## Run it 24/7

| | macOS | Windows | Linux |
|---|---|---|---|
| Service | `./deploy/install.sh` → launchd `com.asta.engine` | `deploy/windows/install-service.ps1` (NSSM) | `./deploy/install.sh` → systemd user unit |
| Survive logout | (login agent) | service starts before login | `sudo loginctl enable-linger $USER` |
| No sleep | `sudo pmset -a sleep 0 disksleep 0` | `powercfg /change standby-timeout-ac 0` | `systemctl mask sleep.target suspend.target` |

Tailscale itself must run at boot too: the macOS app launches at login, the Windows
service is automatic, Linux `systemctl enable --now tailscaled`.

## Security

- **Funnel is public.** Anyone with the URL reaches the token page; the token is the
  only gate. Never send the **editor** link — use **viewer** for other people.
- Rotate by changing `ASTA_EDITOR_TOKEN` / `ASTA_VIEWER_TOKEN` in `.env` and
  restarting the service (env wins over `data/share.json`).
- The dashboard keeps listening on `127.0.0.1` only, so the LAN/coffee-shop Wi-Fi
  cannot reach it directly. Do not set `--host 0.0.0.0` unless you mean it.
- Funnel exposes only the port you pass. Nothing else on the machine is reachable.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `funnel: HTTPS is disabled` | Enable HTTPS Certificates at <https://login.tailscale.com/admin/dns> |
| `funnel: not logged in` | `tailscale up`; on Linux check `systemctl status tailscaled` |
| `tailscale not found` on macOS | App Store build has no PATH binary — the script falls back to `/Applications/Tailscale.app/Contents/MacOS/Tailscale` |
| URL opens but `502` | dashboard is down or on another port; `curl -s http://127.0.0.1:4310/healthz` |
| `/api/access` returns `editor` without a token | proxy headers not detected — that is a security bug in `src/asta/web/server.py`, not a Tailscale issue |
| URL changed | machine renamed or node removed from the tailnet; renaming back restores it |
| Works locally, not from phone | phone is on a network that blocks `*.ts.net`; DERP relay is TCP 443, check DNS |
| Certificate warning | happens right after enabling HTTPS certs; re-run the command after ~1 min |
