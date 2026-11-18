#!/usr/bin/env bash
# Start the Stockbit MCP sidecar in stateless Streamable-HTTP mode.
#
#   scripts/start_stockbit_mcp.sh            # foreground, 127.0.0.1:8787/mcp
#   STOCKBIT_TOOLS=all scripts/start_stockbit_mcp.sh
#
# ASTA talks to it through asta.providers.mcp.MCPClient (same path as MT5).
# The Stockbit login itself is NOT done here: run `stockbit-auth login` (or
# `stockbit-auth import-har <file.har> --shred`) once inside third_party/stockbit-mcp.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIDECAR="${STOCKBIT_MCP_DIR:-$ROOT/third_party/stockbit-mcp}"

if [ ! -f "$SIDECAR/dist/bin/stockbit-mcp.js" ]; then
  echo "stockbit-mcp is not built at $SIDECAR" >&2
  echo "run: git clone https://github.com/INo-xious/stockbit-mcp \"$SIDECAR\" && cd \"$SIDECAR\" && npm ci && npm run build" >&2
  exit 1
fi

# Token file keeps the bearer out of shell history and out of the process list.
TOKEN_FILE="${STOCKBIT_MCP_TOKEN_FILE:-$ROOT/third_party/.stockbit-mcp-token}"
if [ -n "${STOCKBIT_MCP_TOKEN:-}" ]; then
  TOKEN="$STOCKBIT_MCP_TOKEN"
elif [ -s "$TOKEN_FILE" ]; then
  TOKEN="$(cat "$TOKEN_FILE")"
else
  TOKEN="$(node -e 'process.stdout.write(require("node:crypto").randomBytes(32).toString("base64url"))')"
  umask 077
  printf '%s' "$TOKEN" > "$TOKEN_FILE"
  echo "generated MCP transport token -> $TOKEN_FILE" >&2
fi

export STOCKBIT_MCP_TRANSPORT=http
export STOCKBIT_MCP_TOKEN="$TOKEN"
export STOCKBIT_MCP_HOST="${STOCKBIT_MCP_HOST:-127.0.0.1}"
export STOCKBIT_MCP_PORT="${STOCKBIT_MCP_PORT:-8787}"
export STOCKBIT_TOOLS="${STOCKBIT_TOOLS:-core}"

echo "stockbit-mcp http://$STOCKBIT_MCP_HOST:$STOCKBIT_MCP_PORT/mcp (tools=$STOCKBIT_TOOLS)" >&2
cd "$SIDECAR"
exec node dist/bin/stockbit-mcp.js
