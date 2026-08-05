#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── Parse conf.yaml ──
CONF="conf.yaml"
DESKTOP_ENGINE=$(grep -E "^\s{4}engine:" "$CONF" | awk '{print $2}' | tr -d "'\"")
SERVER_PORT=$(awk '/^system_config:/, /^character_config:/' "$CONF" | grep -E "^\s{2}port:" | awk '{print $2}')
DESKTOP_ENGINE=${DESKTOP_ENGINE:-electron}
SERVER_PORT=${SERVER_PORT:-12393}

echo "Desktop engine: $DESKTOP_ENGINE"
echo "Server port: $SERVER_PORT"

# Start the backend server in background
echo "Starting backend server..."
uv run run_server.py &
SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for server..."
for i in $(seq 1 30); do
  if curl -s "http://localhost:${SERVER_PORT}" > /dev/null 2>&1; then
    echo "Server is ready."
    break
  fi
  sleep 1
done

# Start desktop frontend based on engine
FRONTEND_PID=""
case "$DESKTOP_ENGINE" in
  web)
    echo "Starting Web frontend..."
    (cd deskcom && npm run dev:web > /dev/null 2>&1) &
    FRONTEND_PID=$!
    ;;
  *)
    echo "Starting Electron frontend..."
    (cd deskcom && npm run dev > /dev/null 2>&1) &
    FRONTEND_PID=$!
    ;;
esac

# Bring server logs to foreground
echo ""
echo "=== Server logs  ==="
echo "Close this terminal to stop everything."
echo ""
wait $SERVER_PID

# Cleanup
kill $FRONTEND_PID 2>/dev/null
