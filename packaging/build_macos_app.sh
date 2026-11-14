#!/usr/bin/env bash
# Build ASTA.app — a double-clickable launcher for the repo it sits in.
#
#   ./packaging/build_macos_app.sh            # creates ASTA.app in the repo root
#   ./packaging/build_macos_app.sh --open     # ... and opens it
#
# The bundle is unsigned except for an ad-hoc signature, which is enough for a
# local app. On first launch macOS may ask to confirm: right-click -> Open.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/ASTA.app"
PYTHON="$ROOT/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "error: $PYTHON not found - create the venv first:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -e \".[dev]\"" >&2
  exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>ASTA</string>
  <key>CFBundleDisplayName</key><string>ASTA</string>
  <key>CFBundleIdentifier</key><string>com.asta.launcher</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>ASTA</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.finance</string>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/ASTA" <<'STUB'
#!/bin/bash
# Resolve the repo root: ASTA.app/Contents/MacOS/ASTA -> ../../..
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT" || exit 1
exec "$ROOT/.venv/bin/python" -m asta.main launcher >>"$ROOT/data/logs/launcher.log" 2>&1
STUB
chmod +x "$APP/Contents/MacOS/ASTA"

mkdir -p "$ROOT/data/logs"
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

echo "built $APP"
if [ "${1:-}" = "--open" ]; then
  open "$APP"
fi
