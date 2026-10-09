#!/usr/bin/env bash
# ComotVid dev runner with Watch Mode & Auto-Reload
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-3000}"
PY="${PYTHON:-python3}"
NO_OPEN="${NO_OPEN:-0}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "✗ $PY tidak ditemukan. Set PYTHON=... atau install python3." >&2
  exit 1
fi

# Cari port kosong jika default terpakai
if command -v lsof >/dev/null 2>&1; then
  while lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; do
    echo "… port $PORT terpakai, coba $((PORT + 1))"
    PORT=$((PORT + 1))
  done
fi

URL="http://localhost:$PORT"
echo ""
echo "  🚀 ComotVid dev (Watch Mode) -> $URL"
echo "  Watching: server.py, app.js, index.html, style.css"
echo "  Stop: Ctrl+C"
echo ""

if [ "$NO_OPEN" != "1" ]; then
  (
    sleep 1.2
    if command -v open >/dev/null 2>&1; then open "$URL"
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
    fi
  ) >/dev/null 2>&1 &
fi

SERVER_PID=""

cleanup() {
  echo ""
  echo "🛑 Menghentikan server..."
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

start_server() {
  "$PY" server.py "$PORT" &
  SERVER_PID=$!
}

start_server

# Watch loop: cek modifikasi server.py untuk auto-restart
LAST_STATE=""
get_state() {
  if stat -f "%m" server.py >/dev/null 2>&1; then
    stat -f "%m" server.py 2>/dev/null || echo "0"
  else
    stat -c "%Y" server.py 2>/dev/null || echo "0"
  fi
}

LAST_STATE=$(get_state)

while true; do
  sleep 1
  if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    echo "⚠️ Server berhenti. Me-restart..."
    start_server
  fi

  CURRENT_STATE=$(get_state)
  if [ "$CURRENT_STATE" != "$LAST_STATE" ]; then
    echo "🔄 Perubahan terdeteksi di server.py, restarting server..."
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    start_server
    LAST_STATE="$CURRENT_STATE"
    echo "✅ Server berhasil di-restart di $URL"
  fi
done
