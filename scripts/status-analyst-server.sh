#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# status-analyst-server.sh
# Shows running status, port binding, and recent log tail.
# ─────────────────────────────────────────────────────────────────────────────

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$REPO_DIR/logs/analyst-server.pid"
LOG_FILE="$REPO_DIR/logs/analyst-server.log"
PORT=7799

echo "──────────────────────────────────────────────────"
echo "  Analyst Server Status"
echo "──────────────────────────────────────────────────"

# PID check
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "  Status : ✅  RUNNING (PID $PID)"
  else
    echo "  Status : ❌  DEAD (stale PID $PID)"
  fi
else
  echo "  Status : ⚫  NOT STARTED (no PID file)"
fi

# Port check
PORT_PROC=$(lsof -ti :"$PORT" 2>/dev/null)
if [ -n "$PORT_PROC" ]; then
  echo "  Port   : ✅  :$PORT is bound (PID $PORT_PROC)"
else
  echo "  Port   : ⚫  :$PORT not bound"
fi

echo "  UI     : http://localhost:$PORT"
echo "  Log    : $LOG_FILE"

# Log tail
if [ -f "$LOG_FILE" ]; then
  echo ""
  echo "── Last 20 log lines ──────────────────────────────"
  tail -n 20 "$LOG_FILE"
else
  echo ""
  echo "  (no log file yet)"
fi
echo "──────────────────────────────────────────────────"
