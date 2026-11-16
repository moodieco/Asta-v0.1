# Install ASTA from zero

End state: the scanner runs on your machine, the dashboard answers on
`http://127.0.0.1:4310`, and a **stable** public link
`https://<machine>.<tailnet>.ts.net` works through Tailscale Funnel.

Time: ~15 minutes. Costs: nothing (Tailscale Personal is free).

---

## 0. What you need

| Item | Why | Check |
|---|---|---|
| Git | clone the repo | `git --version` |
| Python 3.9+ | engine + dashboard API | `python3 -V` |
| Node 20+ | build the dashboard bundle (`web/dist`) | `node -v` |
| Tailscale (optional) | public HTTPS link | `tailscale version` |
| Discord webhook (optional) | signal alerts | Discord → Server settings → Integrations |

> `web/dist` is **not** in the repo. A fresh clone has no dashboard until you
> build it (step 3). Skipping it gives `dashboard build missing` from `asta serve`.

---

## 1. Clone and install the engine

```bash
cd ~                      # Windows: cd %USERPROFILE%
# feat/web-launcher is the branch that carries the dashboard + deploy tooling;
# main is still the older pre-dashboard line.
git clone --branch feat/web-launcher https://github.com/moodieco/Asta-V0.1.git asta
cd asta
python3 -m venv .venv
.venv/bin/pip install -e .
```

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\pip install -e .
```

## 2. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` — three kinds of values:

```bash
# Discord delivery (optional; leave empty to run without alerts)
DISCORD_WEBHOOK_CRYPTO=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_STOCK=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_FOREX=https://discord.com/api/webhooks/...

# Dashboard access. Generate your own so the links never change:
#   openssl rand -hex 24
ASTA_EDITOR_TOKEN=<64 hex chars>
ASTA_VIEWER_TOKEN=<64 hex chars>
```

If you leave the tokens empty, ASTA generates them once into `data/share.json`
and you read them with `curl -s http://127.0.0.1:4310/api/share`.

**Forex:** needs a MetaTrader 5 terminal (`MT5_TERMINAL_URL`), which only exists on
Windows. On macOS/Linux use OANDA (`providers.forex.type: oanda` + `OANDA_*`) or
turn forex off in `config/markets.yaml` (`enabled: false`).

## 3. Build the dashboard

```bash
cd web
npm ci
npm run build          # writes web/dist, then 'cd ..'
cd ..
```

## 4. First run

```bash
.venv/bin/asta --health                 # providers, storage, webhooks
.venv/bin/asta serve --no-browser       # Ctrl-C to stop
```

Open `http://127.0.0.1:4310/?token=<ASTA_EDITOR_TOKEN>`.

Verify before going further:

```bash
curl -s http://127.0.0.1:4310/healthz                       # {"ok":true}
curl -s http://127.0.0.1:4310/api/access?token=<editor>      # {"access":"editor"}
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: 1.2.3.4' \
     http://127.0.0.1:4310/api/access                        # 401  <- token gate works
```

The third line matters: it proves a proxy/tunnel cannot slip in as editor.

## 5. Stable public URL (Tailscale)

**One-time setup**

1. Create/sign in at <https://login.tailscale.com> (free Personal plan). This
   creates your tailnet `xxxx.ts.net`.
2. Install + login on this machine:

   ```bash
   # macOS
   brew install --cask tailscale && tailscale up
   # Windows
   winget install --id Tailscale.Tailscale -e
   & "C:\Program Files\Tailscale\tailscale.exe" up
   # Linux
   curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up
   ```

3. In <https://login.tailscale.com/admin/dns> enable **MagicDNS** *and*
   **HTTPS Certificates** (both are required).
4. Enable Funnel for this node. The CLI prints the exact link the first time:

   ```bash
   tailscale funnel --bg 4310
   # → "Funnel is not enabled on your tailnet. To enable, visit:
   #    https://login.tailscale.com/f/funnel?node=..."
   ```

   Open that link once. (If it hangs silently instead of printing, the HTTPS
   certificate from step 3 is still off.)

**Everyday use**

```bash
./scripts/share-tailscale.sh            # macOS/Linux
```
```powershell
.\scripts\share-tailscale.ps1           # Windows
```

```bash
./scripts/share-tailscale.sh --status   # what the funnel serves now
./scripts/share-tailscale.sh --off      # stop public access
```

Output:

```
Stable (Tailscale Funnel):
  viewer  https://atan.tailxxxx.ts.net/?token=...
  editor  https://atan.tailxxxx.ts.net/?token=...
```

That hostname does **not** change on reboot or IP change. Share the **viewer**
link; the editor link is full control.

## 6. Keep it running 24/7

```bash
./deploy/install.sh                     # macOS (launchd) / Linux (systemd user)
```
```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install-service.ps1
```

Also stop the machine from sleeping:

| OS | Command |
|---|---|
| macOS | `sudo pmset -a sleep 0 disksleep 0` |
| Windows | `powercfg /change standby-timeout-ac 0` |
| Linux | `sudo systemctl mask sleep.target suspend.target` |

Verify after a reboot:

```bash
./scripts/share-tailscale.sh --status     # funnel config survives
curl -s http://127.0.0.1:4310/healthz     # engine came back
```

If the funnel is empty after a boot (tailscaled started late), just run
`./scripts/share-tailscale.sh` again.

## 7. Update

```bash
cd ~/asta
git pull
.venv/bin/pip install -e .
cd web && npm ci && npm run build && cd ..
# restart the service
./deploy/install.sh          # or: launchctl kickstart -k gui/$(id -u)/com.asta.engine
```

`data/` (history, scanner library, tokens, alerts) is untouched by updates.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `dashboard build missing` | step 3 not run, or `web/dist` deleted |
| Every URL returns 401 | open with `?token=...`; `data/share.json` or env tokens must match |
| `/api/access` returns `editor` without a token through a tunnel | security bug — check `X-Forwarded-For` handling in `src/asta/web/server.py` |
| `funnel did not come up` | HTTPS Certificates or the Funnel toggle still off (step 5.3/5.4) |
| `Address already in use` | another `asta serve` is running: `pgrep -fl 'asta serve'` |
| Forex scanner silent | MT5 terminal not running / no OANDA token; check `asta --health` |
| Dashboard empty after deploy | first scan cycle takes ~60 s; watch `data/logs/asta.log` |
| Windows: `No module named resource` | you are on an older commit — the current code guards it |

## 9. Alternatives to a local machine

| Target | Guide |
|---|---|
| Render (docker, `starter` plan) | [`DEPLOY_RENDER.md`](DEPLOY_RENDER.md) |
| Random public URL (no Tailscale) | `./scripts/share.sh` (cloudflared quick tunnel, URL changes on restart) |
| LAN only | `asta serve --host 0.0.0.0` |
