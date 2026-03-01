#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start-analyst-server.sh
# Starts analyst_server.py in the background via nohup.
# Logs go to logs/analyst-server.log  (stdout + stderr)
# PID is written to logs/analyst-server.pid for easy stopping.
# ─────────────────────────────────────────────────────────────────────────────

# Resolve repo root (parent of this script's directory)
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/analyst-server.log"
PID_FILE="$LOG_DIR/analyst-server.pid"
SERVER="$REPO_DIR/analyst_server.py"
PORT=7799

# ── Preflight checks ──────────────────────────────────────────────────────────
if [ ! -f "$SERVER" ]; then
  echo "❌  analyst_server.py not found at $SERVER"
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "❌  python3 not found in PATH"
  exit 1
fi

# ── Already running? ──────────────────────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "⚠️   Analyst server already running (PID $OLD_PID)"
    echo "    Stop it first:  bash $REPO_DIR/scripts/stop-analyst-server.sh"
    exit 1
  else
    # Stale PID file — clean up
    rm -f "$PID_FILE"
  fi
fi

# ── Create logs directory ─────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── Rotate log if larger than 10 MB ──────────────────────────────────────────
if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE")" -gt 10485760 ]; then
  ROTATED="$LOG_DIR/analyst-server-$(date +%Y%m%d-%H%M%S).log"
  mv "$LOG_FILE" "$ROTATED"
  echo "📦  Log rotated → $ROTATED"
fi

# ── Launch ────────────────────────────────────────────────────────────────────
cd "$REPO_DIR"

echo "──────────────────────────────────────────────────"
echo "  Ahmed's Analyst Server"
echo "──────────────────────────────────────────────────"
echo "  Repo   : $REPO_DIR"
echo "  Log    : $LOG_FILE"
echo "  PID    : $PID_FILE"
echo "  Port   : $PORT"
echo "──────────────────────────────────────────────────"

nohup python3 "$SERVER" >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

# Give it a moment then confirm it's alive
sleep 1
if kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "✅  Started (PID $SERVER_PID)"
  echo "    UI   → http://localhost:$PORT"
  echo "    Logs → tail -f $LOG_FILE"
  echo "    Stop → bash $REPO_DIR/scripts/stop-analyst-server.sh"
else
  echo "❌  Server failed to start. Check logs:"
  echo "    cat $LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi
