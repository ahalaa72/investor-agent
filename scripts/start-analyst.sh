#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start-analyst.sh
# One script: Server + Cloudflare Tunnel + Email URL to phone
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
SERVER="$REPO_DIR/analyst_server.py"
PORT=7799

# Read auth from .env (FIX-01: no more hardcoded admin:admin)
AUTH_USER=$(grep -m1 '^ANALYST_USER=' "$REPO_DIR/.env" 2>/dev/null | cut -d= -f2 || true)
AUTH_PASS=$(grep -m1 '^ANALYST_PASS=' "$REPO_DIR/.env" 2>/dev/null | cut -d= -f2 || true)
if [ -z "$AUTH_PASS" ]; then
  echo "❌ ANALYST_PASS not set in .env — add ANALYST_USER=... and ANALYST_PASS=... first"
  exit 1
fi
AUTH="${AUTH_USER:-admin}:${AUTH_PASS}"

SERVER_PID_FILE="$LOG_DIR/analyst-server.pid"
SERVER_LOG="$LOG_DIR/analyst-server.log"
TUNNEL_PID_FILE="$LOG_DIR/tunnel.pid"
TUNNEL_LOG="$LOG_DIR/tunnel.log"
URL_FILE="$LOG_DIR/tunnel-url.txt"

mkdir -p "$LOG_DIR"

# ── Helpers ──────────────────────────────────────────────────────────────────
cleanup_stale() {
  local pid_file=$1 name=$2
  if [ -f "$pid_file" ]; then
    local old_pid
    old_pid=$(cat "$pid_file")
    if kill -0 "$old_pid" 2>/dev/null; then
      echo "⚠️   $name already running (PID $old_pid) — stopping…"
      kill "$old_pid" 2>/dev/null; sleep 2
      kill -9 "$old_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

# ── Preflight ────────────────────────────────────────────────────────────────
if [ ! -f "$SERVER" ]; then echo "❌ analyst_server.py not found"; exit 1; fi
if ! command -v python3 &>/dev/null; then echo "❌ python3 not found"; exit 1; fi
if ! command -v cloudflared &>/dev/null; then echo "❌ cloudflared not found — brew install cloudflared"; exit 1; fi
if ! command -v claude &>/dev/null; then echo "❌ claude not found"; exit 1; fi

# ── 0. Verify OAuth token exists in Keychain ─────────────────────────────
# claude -p reads the Keychain directly — we just verify it's there
if security find-generic-password -s "Claude Code-credentials" -w &>/dev/null; then
  echo "✅ OAuth token found in macOS Keychain"
else
  echo "❌ No OAuth token in Keychain — run 'claude' interactively to log in first"
  exit 1
fi

# ── Stop previous instances ──────────────────────────────────────────────────
cleanup_stale "$SERVER_PID_FILE" "Server"
cleanup_stale "$TUNNEL_PID_FILE" "Tunnel"
# Kill anything still holding the port
lsof -ti :"$PORT" | xargs kill -9 2>/dev/null || true
sleep 1

# ── Rotate logs ──────────────────────────────────────────────────────────────
for f in "$SERVER_LOG" "$TUNNEL_LOG"; do
  if [ -f "$f" ] && [ "$(wc -c < "$f")" -gt 10485760 ]; then
    mv "$f" "${f%.log}-$(date +%Y%m%d-%H%M%S).log"
  fi
done

# ── 1. Start Server (env -i = clean env, no Claude/VS Code session leaks) ──
cd "$REPO_DIR"
env -i \
  HOME="$HOME" \
  USER="${USER:-AhmedE}" \
  SHELL="${SHELL:-/bin/zsh}" \
  PATH="/Users/AhmedE/.nvm/versions/node/v22.20.0/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  LANG="en_US.UTF-8" \
  TERM="xterm-256color" \
  PYTHONUNBUFFERED=1 \
  TMPDIR="${TMPDIR:-/tmp}" \
  NVM_DIR="${NVM_DIR:-$HOME/.nvm}" \
  nohup python3 -u "$SERVER" >> "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$SERVER_PID_FILE"
sleep 2

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "❌ Server failed to start — check $SERVER_LOG"
  exit 1
fi
echo "✅ Server started (PID $SERVER_PID) on port $PORT"

# ── 2. Start Cloudflare Tunnel ──────────────────────────────────────────────
nohup cloudflared tunnel --url "http://localhost:$PORT" > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
echo "$TUNNEL_PID" > "$TUNNEL_PID_FILE"

echo "⏳ Waiting for Cloudflare tunnel…"
TUNNEL_URL=""
for i in $(seq 1 30); do
  TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
  if [ -n "$TUNNEL_URL" ]; then break; fi
  sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
  echo "❌ Tunnel failed to start — check $TUNNEL_LOG"
  kill "$TUNNEL_PID" 2>/dev/null || true
  rm -f "$TUNNEL_PID_FILE"
  echo "   Server still running at http://localhost:$PORT"
  exit 1
fi

echo "$TUNNEL_URL" > "$URL_FILE"
echo "✅ Tunnel ready: $TUNNEL_URL"

# ── 3. Email the URL (via server's /notify endpoint) ────────────────────────
EMAIL_BODY="Ahmed's Analyst Server is live.

Tap to open: $TUNNEL_URL

Login: ${AUTH_USER:-admin} (password in .env)
3 concurrent scans · Claude + Gemini + Claude pipeline
Reports auto-saved to vault and emailed"

RESULT=$(curl -s -u "$AUTH" -X POST "http://localhost:$PORT/notify" \
  -H "Content-Type: application/json" \
  -d "{\"subject\":\"Analyst Server — $TUNNEL_URL\",\"message\":$(python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$EMAIL_BODY")}" 2>/dev/null)

if echo "$RESULT" | grep -q "EMAIL_SENT"; then
  echo "✉️  URL emailed"
else
  echo "⚠️  Email: $RESULT"
fi

# ── 4. Start Self-Improvement Scheduler ──────────────────────────────────────
SCHEDULER="$REPO_DIR/scripts/self-improvement-scheduler.py"
SCHEDULER_PID_FILE="$LOG_DIR/scheduler.pid"
SCHEDULER_LOG="$LOG_DIR/scheduler.log"

# Stop any previous scheduler
if [ -f "$SCHEDULER_PID_FILE" ]; then
  old_pid=$(cat "$SCHEDULER_PID_FILE")
  kill "$old_pid" 2>/dev/null || true
  rm -f "$SCHEDULER_PID_FILE"
fi

python3 "$SCHEDULER" --daemon
if [ -f "$SCHEDULER_PID_FILE" ]; then
  SCHED_PID=$(cat "$SCHEDULER_PID_FILE")
  echo "✅ Self-improvement scheduler started (PID $SCHED_PID)"
  echo "   Catch-up + daily/weekly/monthly jobs active"
else
  echo "⚠️  Scheduler failed to start — check $SCHEDULER_LOG"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  Ahmed's Analyst Server"
echo "══════════════════════════════════════════════════"
echo "  Local  : http://localhost:$PORT"
echo "  Public : $TUNNEL_URL"
echo "  Login  : ${AUTH_USER:-admin} / ****"
EMAIL_TO=$(grep -m1 '^EMAIL_TO=' "$REPO_DIR/.env" 2>/dev/null | cut -d= -f2 || echo "not configured")
echo "  Email  : ${EMAIL_TO}"
echo "  Server : PID $SERVER_PID  (log: $SERVER_LOG)"
echo "  Tunnel : PID $TUNNEL_PID  (log: $TUNNEL_LOG)"
echo "  Sched  : PID ${SCHED_PID:-N/A}  (log: $SCHEDULER_LOG)"
echo "══════════════════════════════════════════════════"
echo "  Logs   : tail -f $SERVER_LOG"
echo "  Sched  : python3 $SCHEDULER --status"
echo "  Stop   : bash $REPO_DIR/scripts/stop-analyst.sh"
echo "══════════════════════════════════════════════════"
