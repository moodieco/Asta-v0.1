#!/usr/bin/env bash
# asta deploy install — register ASTA as a background service on macOS or Linux.
#
#   ./deploy/install.sh              # render the unit, register it, start it
#   ./deploy/install.sh --dry-run    # print the rendered file, change nothing
#   ./deploy/install.sh --uninstall  # stop and remove the service (data/ stays)
#
# Windows uses deploy/windows/install-service.ps1 instead (NSSM).
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT=$PWD
BIN="$ROOT/.venv/bin/asta"
MODE=install

for arg in "$@"; do
  case "$arg" in
    --dry-run) MODE=dry ;;
    --uninstall) MODE=uninstall ;;
    *) echo "usage: $0 [--dry-run|--uninstall]" >&2; exit 2 ;;
  esac
done

[ -x "$BIN" ] || {
  echo "missing $BIN" >&2
  echo "run: python3 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
}

mkdir -p "$ROOT/data/logs"

render() {
  sed -e "s|@ASTA_ROOT@|$ROOT|g" -e "s|@ASTA_BIN@|$BIN|g" "$1"
}

case "$(uname -s)" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/com.asta.engine.plist"
    echo "→ rendering deploy/launchd/com.asta.engine.plist.tpl"
    render deploy/launchd/com.asta.engine.plist.tpl > "$PLIST.new"

    if [ "$MODE" = dry ]; then
      cat "$PLIST.new"
      rm -f "$PLIST.new"
      exit 0
    fi

    if [ "$MODE" = uninstall ]; then
      launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
      rm -f "$PLIST"
      echo "→ launchd agent removed (data/ and .env are untouched)"
      exit 0
    fi

    plutil -lint "$PLIST.new" >/dev/null
    mv "$PLIST.new" "$PLIST"
    launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    launchctl print "gui/$(id -u)/com.asta.engine" >/dev/null
    echo "→ installed $PLIST"
    echo "  keep it awake:  sudo pmset -a sleep 0 disksleep 0"
    ;;

  Linux)
    UNIT="$HOME/.config/systemd/user/asta.service"
    mkdir -p "$(dirname "$UNIT")"
    echo "→ rendering deploy/systemd/asta.service"
    render deploy/systemd/asta.service > "$UNIT.new"

    if [ "$MODE" = dry ]; then
      cat "$UNIT.new"
      rm -f "$UNIT.new"
      exit 0
    fi

    if [ "$MODE" = uninstall ]; then
      systemctl --user disable --now asta 2>/dev/null || true
      rm -f "$UNIT"
      systemctl --user daemon-reload
      echo "→ systemd unit removed (data/ and .env are untouched)"
      exit 0
    fi

    mv "$UNIT.new" "$UNIT"
    systemctl --user daemon-reload
    systemctl --user enable --now asta
    systemctl --user --no-pager --lines=0 status asta || true
    echo "→ installed $UNIT"
    echo "  survive logout:  sudo loginctl enable-linger $USER"
    ;;

  *)
    echo "unsupported OS: $(uname -s) — on Windows use deploy/windows/install-service.ps1" >&2
    exit 1
    ;;
esac

echo
echo "next: ./scripts/share-tailscale.sh --status"
