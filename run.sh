#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── Parse conf.yaml ──
CONF="conf.yaml"
SERVER_PORT=$(awk '/^system_config:/, /^character_config:/' "$CONF" | grep -E "^\s{2}port:" | awk '{print $2}')
SERVER_PORT=${SERVER_PORT:-12393}

echo "Server port: $SERVER_PORT"

# ── Ask user for frontend mode ──
echo ""
echo "Pilih mode frontend:"
echo "  1) Web   (buka otomatis di browser)"
echo "  2) Electron (desktop app)"
echo -n "Pilihan [1/2] (default: electron): "
read -r CHOICE
CHOICE=${CHOICE:-2}
echo ""

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

# Start desktop frontend based on user choice
FRONTEND_PID=""
case "$CHOICE" in
  1|web)
    echo "Starting Web frontend..."
    (cd deskcom && pnpm run dev:web > /dev/null 2>&1) &
    FRONTEND_PID=$!
    echo "Opening browser at http://localhost:3000 ..."
    sleep 3
    xdg-open "http://localhost:3000" > /dev/null 2>&1 || sensible-browser "http://localhost:3000" > /dev/null 2>&1 || true
    ;;
  *)
    echo "Starting Electron frontend..."
    (cd deskcom && pnpm run dev > /dev/null 2>&1) &
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
