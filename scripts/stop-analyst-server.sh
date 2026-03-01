#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# stop-analyst-server.sh
# Gracefully stops the analyst server started by start-analyst-server.sh.
# ─────────────────────────────────────────────────────────────────────────────

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$REPO_DIR/logs/analyst-server.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "⚠️   No PID file found — server may not be running"
  echo "    Check manually: lsof -i :7799"
  exit 0
fi

PID=$(cat "$PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
  echo "⚠️   Process $PID is not running (stale PID file removed)"
  rm -f "$PID_FILE"
  exit 0
fi

echo "🛑  Stopping analyst server (PID $PID)…"
kill "$PID"

# Wait up to 5 seconds for clean exit
for i in {1..5}; do
  sleep 1
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "✅  Stopped"
    exit 0
  fi
done

# Force kill if still alive
echo "⚡  Force killing PID $PID…"
kill -9 "$PID" 2>/dev/null
rm -f "$PID_FILE"
echo "✅  Force stopped"
