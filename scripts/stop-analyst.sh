#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# stop-analyst.sh
# Stops both the analyst server and Cloudflare tunnel
# ─────────────────────────────────────────────────────────────────────────────

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"

stop_process() {
  local pid_file=$1 name=$2
  if [ ! -f "$pid_file" ]; then
    echo "⚠️   $name: no PID file"
    return
  fi
  local pid
  pid=$(cat "$pid_file")
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "⚠️   $name: not running (stale PID $pid)"
    rm -f "$pid_file"
    return
  fi
  echo "🛑  Stopping $name (PID $pid)…"
  kill "$pid" 2>/dev/null
  for i in {1..5}; do
    sleep 1
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$pid_file"
      echo "✅  $name stopped"
      return
    fi
  done
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$pid_file"
  echo "✅  $name force stopped"
}

stop_process "$LOG_DIR/tunnel.pid" "Tunnel"
stop_process "$LOG_DIR/analyst-server.pid" "Server"
rm -f "$LOG_DIR/tunnel-url.txt"
echo "🏁  All stopped"
