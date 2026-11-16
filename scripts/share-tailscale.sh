#!/usr/bin/env bash
# asta share-tailscale — a STABLE public https URL through Tailscale Funnel.
#
#   ./scripts/share-tailscale.sh            # dashboard (if needed) + funnel + links
#   ./scripts/share-tailscale.sh --status    # what the funnel is serving now
#   ./scripts/share-tailscale.sh --off       # stop serving publicly
#
# Unlike the cloudflared quick tunnel in scripts/share.sh, the hostname here does
# not change: it is https://<machine>.<tailnet>.ts.net for as long as the node
# keeps its name. Prerequisites, once per machine:
#   * tailscale installed and logged in            -> tailscale up
#   * MagicDNS + HTTPS Certificates enabled        -> https://login.tailscale.com/admin/dns
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT=$PWD
PORT=${ASTA_PORT:-4310}
LOGS="$ROOT/data/logs"

MODE=share
case "${1:-}" in
  ""|--share|share) MODE=share ;;
  --off|off) MODE=off ;;
  --status|status) MODE=status ;;
  *) echo "usage: $0 [--status|--off]" >&2; exit 2 ;;
esac

# The macOS App Store build has no `tailscale` on PATH; use the app binary.
tailscale_bin() {
  if command -v tailscale >/dev/null 2>&1; then
    command -v tailscale
  elif [ -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]; then
    echo "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
  else
    return 1
  fi
}

TS=$(tailscale_bin) || {
  echo "tailscale not found." >&2
  echo "  macOS:  brew install --cask tailscale   (or the App Store app)" >&2
  echo "  Linux:  https://tailscale.com/download/linux" >&2
  exit 1
}

if ! "$TS" status >/dev/null 2>&1; then
  echo "tailscale is installed but not connected — run: $TS up" >&2
  exit 1
fi

if [ "$MODE" = status ]; then
  "$TS" funnel status
  exit 0
fi

if [ "$MODE" = off ]; then
  "$TS" funnel reset
  echo "funnel stopped — the dashboard is local-only again (http://127.0.0.1:$PORT)"
  exit 0
fi

port_up() { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }

if ! port_up; then
  echo "→ starting dashboard on 127.0.0.1:$PORT"
  mkdir -p "$LOGS"
  nohup .venv/bin/asta serve --no-browser >>"$LOGS/dashboard.log" 2>&1 &
  for _ in $(seq 1 40); do
    port_up && break
    sleep 0.5
  done
  port_up || { echo "dashboard did not start — see data/logs/dashboard.log" >&2; exit 1; }
else
  echo "→ dashboard already listening on :$PORT"
fi

# `tailscale funnel` can sit retrying (macOS has no `timeout`), and its stderr is
# the ONLY place the per-node activation link appears — capture it, bound the
# wait, and print it verbatim when the proxy does not come up.
FUNNEL_LOG=$(mktemp -t asta-funnel)
"$TS" funnel --bg "$PORT" >"$FUNNEL_LOG" 2>&1 &
FUNNEL_PID=$!
disown "$FUNNEL_PID" 2>/dev/null || true   # keep job-control noise out of the output
FUNNEL_OK=0
for _ in $(seq 1 25); do
  if "$TS" funnel status 2>/dev/null | grep -q "127.0.0.1:$PORT"; then
    FUNNEL_OK=1
    break
  fi
  sleep 1
done

if [ "$FUNNEL_OK" -ne 1 ]; then
  kill "$FUNNEL_PID" 2>/dev/null || true
  echo "funnel did not come up. tailscale said:" >&2
  sed 's/^/  /' "$FUNNEL_LOG" >&2
  echo >&2
  if grep -qi "not enabled on your tailnet" "$FUNNEL_LOG"; then
    echo "→ open the activation link above once, then re-run this script." >&2
  else
    echo "→ check, in this order:" >&2
    echo "  1. https://login.tailscale.com/admin/dns -> MagicDNS + HTTPS Certificates ON" >&2
    echo "  2. tailscale status                      -> this machine is connected" >&2
    echo "  3. tailscale funnel status               -> no stale config on port 443" >&2
  fi
  rm -f "$FUNNEL_LOG"
  exit 1
fi
rm -f "$FUNNEL_LOG"

HOST=$("$TS" status --json | .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')

read -r EDITOR VIEWER < <(curl -sf "http://127.0.0.1:$PORT/api/share" | .venv/bin/python -c '
import json, sys
d = json.load(sys.stdin)
print(d["editorToken"], d["viewerToken"])
')

echo
echo "Stable (Tailscale Funnel):"
echo "  viewer  https://$HOST/?token=$VIEWER"
echo "  editor  https://$HOST/?token=$EDITOR"
echo
echo "Local (this machine only):"
echo "  http://127.0.0.1:$PORT/?token=$EDITOR"
echo
echo "Viewer = read-only. Editor = full control, only share it if you mean it."
echo "Funnel is PUBLIC: anyone with the URL reaches the token page. Keep the editor link private."
echo "Stop sharing with: ./scripts/share-tailscale.sh --off"
