#!/usr/bin/env bash
# asta share — start the dashboard + a public https link in one command.
#
#   ./scripts/share.sh          # dashboard (if needed) + cloudflared quick tunnel
#   ./scripts/share.sh --lan    # dashboard only, print LAN links
#
# Prints four links: editor/viewer x public/LAN. The tunnel URL is random and
# dies with the cloudflared process (quick tunnels have no uptime guarantee).
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT=$PWD
PORT=${ASTA_PORT:-4310}
LOGS="$ROOT/data/logs"
TUNNEL_LOG="$LOGS/tunnel.log"
mkdir -p "$LOGS"

LAN_ONLY=0
[[ "${1:-}" == "--lan" ]] && LAN_ONLY=1

port_up() { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }

if ! port_up; then
  echo "→ starting dashboard on 127.0.0.1:$PORT"
  nohup .venv/bin/asta serve --no-browser >>"$LOGS/dashboard.log" 2>&1 &
  for _ in $(seq 1 40); do
    port_up && break
    sleep 0.5
  done
  port_up || { echo "dashboard did not start — see $LOGS/dashboard.log"; exit 1; }
else
  echo "→ dashboard already listening on :$PORT"
fi

read -r EDITOR VIEWER LAN_IP < <(curl -sf "http://127.0.0.1:$PORT/api/share" | .venv/bin/python -c '
import json, sys
d = json.load(sys.stdin)
ips = d.get("lanIps") or []
print(d["editorToken"], d["viewerToken"], ips[0] if ips else "127.0.0.1")
')

echo
echo "LAN (same Wi-Fi):"
echo "  editor  http://$LAN_IP:$PORT?token=$EDITOR"
echo "  viewer  http://$LAN_IP:$PORT?token=$VIEWER"

if [[ $LAN_ONLY -eq 1 ]]; then
  exit 0
fi

PUBLIC=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -1 || true)

# A quick tunnel can die server-side ("Tunnel not found") while the process
# keeps retrying, and the stale URL in the log would otherwise be handed out as
# a live link. Cloudflare drops the hostname's DNS record when that happens, so
# resolve it through a public resolver instead of the local one (which on some
# routers NXDOMAINs *.trycloudflare.com even for a healthy tunnel).
tunnel_alive() {
  local url="$1" host="${1#https://}"
  if command -v dig >/dev/null 2>&1; then
    [[ -n "$(dig +short @1.1.1.1 "$host" 2>/dev/null | head -1)" ]]
  else
    curl -s -m 6 -o /dev/null "$url/api/health"
  fi
}

if pgrep -f "cloudflared tunnel --url http://127.0.0.1:$PORT" >/dev/null \
  && [[ -n "${PUBLIC:-}" ]] \
  && tunnel_alive "$PUBLIC"; then
  echo "→ reusing the running cloudflared tunnel"
else
  if pgrep -f "cloudflared tunnel --url http://127.0.0.1:$PORT" >/dev/null; then
    echo "→ tunnel process is up but $PUBLIC does not answer — restarting it"
    pkill -f "cloudflared tunnel --url http://127.0.0.1:$PORT" || true
    sleep 1
  fi
  command -v cloudflared >/dev/null || { echo "cloudflared missing: brew install cloudflared"; exit 1; }
  echo "→ starting cloudflared quick tunnel"
  BASELINE=$(wc -l <"$TUNNEL_LOG" 2>/dev/null || echo 0)
  nohup cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate >>"$TUNNEL_LOG" 2>&1 &
  PUBLIC=""
  for _ in $(seq 1 60); do
    # only lines written by this launch — the log keeps earlier tunnel URLs
    PUBLIC=$(tail -n "+$((BASELINE + 1))" "$TUNNEL_LOG" 2>/dev/null \
      | grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1 || true)
    [[ -n "$PUBLIC" ]] && break
    sleep 0.5
  done
fi

[[ -n "${PUBLIC:-}" ]] || { echo "tunnel URL not found — see $TUNNEL_LOG"; exit 1; }

# Wait for the edge to actually route the hostname before printing it.
for _ in $(seq 1 20); do
  tunnel_alive "$PUBLIC" && break
  sleep 1
done

if ! tunnel_alive "$PUBLIC"; then
  echo "→ note: ${PUBLIC} is not resolving yet. If this network blocks"
  echo "  *.trycloudflare.com (router DNS), the link still works from mobile data."
fi

echo
echo "Public (anyone with the link):"
echo "  viewer  $PUBLIC/?token=$VIEWER"
echo "  editor  $PUBLIC/?token=$EDITOR"
echo
echo "Viewer = read-only. Editor = full control, only share it if you mean it."
echo "Both links set a cookie, so the dashboard keeps working without the token in every URL."
