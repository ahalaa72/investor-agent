#!/bin/bash
# Claude Telegram Wrapper - Provides real progress updates
#
# Usage: ./claude-telegram-wrapper.sh "message" "/path/to/output.txt" [session_id]

MESSAGE="$1"
OUTFILE="$2"
SESSION_ID="$3"
MCP_CONFIG="${4:-.mcp.json}"

SESSION_DIR=~/.claude/projects/-Users-AhmedE-git-investor-agent

# Load environment
source ~/.zshenv 2>/dev/null || true
cd /Users/AhmedE/git/investor-agent

# Initialize output file
echo "STATUS:STARTING" > "$OUTFILE"

# Record existing session files BEFORE starting Claude
EXISTING_SESSIONS=$(ls "$SESSION_DIR"/*.jsonl 2>/dev/null | sort)

# Build Claude command
if [ -n "$SESSION_ID" ]; then
    CLAUDE_CMD="claude --mcp-config $MCP_CONFIG --dangerously-skip-permissions --resume \"$SESSION_ID\" -p \"$MESSAGE\" --output-format json"
else
    CLAUDE_CMD="claude --mcp-config $MCP_CONFIG --dangerously-skip-permissions -p \"$MESSAGE\" --output-format json"
fi

# Create temp file for Claude output
CLAUDE_OUTPUT=$(mktemp)

# Run Claude in background
echo "STATUS:RUNNING" >> "$OUTFILE"
eval $CLAUDE_CMD > "$CLAUDE_OUTPUT" 2>&1 &
CLAUDE_PID=$!

# Wait a moment for Claude to create its session file
sleep 2

# Find the NEW session file
NEW_SESSION=""
for session in "$SESSION_DIR"/*.jsonl; do
    if ! echo "$EXISTING_SESSIONS" | grep -q "^${session}$"; then
        NEW_SESSION="$session"
        break
    fi
done

# If no new session, use the most recently modified one
if [ -z "$NEW_SESSION" ]; then
    NEW_SESSION=$(ls -t "$SESSION_DIR"/*.jsonl 2>/dev/null | head -1)
fi

echo "PROGRESS:0: Started" >> "$OUTFILE"

# Monitor progress
LAST_TOOLS=""
LAST_LIVE=""
PROGRESS_COUNT=0
POLL_COUNT=0
LIVE_PROGRESS_FILE="/tmp/claude-scan-live-progress.txt"

# Clear old progress file
rm -f "$LIVE_PROGRESS_FILE" 2>/dev/null

while kill -0 $CLAUDE_PID 2>/dev/null; do
    POLL_COUNT=$((POLL_COUNT + 1))

    if [ -n "$NEW_SESSION" ] && [ -f "$NEW_SESSION" ]; then
        CURRENT_SIZE=$(stat -f%z "$NEW_SESSION" 2>/dev/null || echo 0)
        SIZE_KB=$((CURRENT_SIZE / 1024))

        # Check for LIVE progress from scanner (written by Python MCP server)
        LIVE_PROGRESS=""
        if [ -f "$LIVE_PROGRESS_FILE" ]; then
            LIVE_PROGRESS=$(cat "$LIVE_PROGRESS_FILE" 2>/dev/null | head -1)
        fi

        # Extract tool names from session
        TOOLS=$(tail -50 "$NEW_SESSION" 2>/dev/null | \
            grep -o '"name":"mcp__investor-agent__[^"]*"' | \
            tail -3 | \
            sed 's/"name":"mcp__investor-agent__//g; s/"//g' | \
            tr '\n' ',' | \
            sed 's/,$//')

        # Priority 1: Use LIVE progress from scanner (real detail like "Checking AAPL...")
        if [ -n "$LIVE_PROGRESS" ] && [ "$LIVE_PROGRESS" != "$LAST_LIVE" ]; then
            PROGRESS_COUNT=$((PROGRESS_COUNT + 1))
            echo "PROGRESS:$PROGRESS_COUNT: $LIVE_PROGRESS" >> "$OUTFILE"
            LAST_LIVE="$LIVE_PROGRESS"
        # Priority 2: Tool changes
        elif [ -n "$TOOLS" ] && [ "$TOOLS" != "$LAST_TOOLS" ]; then
            PROGRESS_COUNT=$((PROGRESS_COUNT + 1))
            echo "PROGRESS:$PROGRESS_COUNT: Running: $TOOLS" >> "$OUTFILE"
            LAST_TOOLS="$TOOLS"
        # Priority 3: Heartbeat every 30 seconds
        elif [ $((POLL_COUNT % 6)) -eq 0 ]; then
            PROGRESS_COUNT=$((PROGRESS_COUNT + 1))
            ELAPSED=$((POLL_COUNT * 5))
            if [ -n "$LIVE_PROGRESS" ]; then
                echo "PROGRESS:$PROGRESS_COUNT: ${ELAPSED}s - $LIVE_PROGRESS" >> "$OUTFILE"
            elif [ -n "$TOOLS" ]; then
                echo "PROGRESS:$PROGRESS_COUNT: ${ELAPSED}s - $TOOLS (${SIZE_KB}KB)" >> "$OUTFILE"
            else
                echo "PROGRESS:$PROGRESS_COUNT: ${ELAPSED}s - Working... (${SIZE_KB}KB)" >> "$OUTFILE"
            fi
        fi
    fi

    sleep 5
done

# Wait for Claude to fully complete
wait $CLAUDE_PID
EXIT_CODE=$?

# Write final result
echo "" >> "$OUTFILE"
echo "STATUS:COMPLETE" >> "$OUTFILE"

if [ $EXIT_CODE -eq 0 ] && [ -s "$CLAUDE_OUTPUT" ]; then
    cat "$CLAUDE_OUTPUT" >> "$OUTFILE"
else
    echo "{\"error\": \"Claude exited with code $EXIT_CODE\", \"output\": \"$(cat "$CLAUDE_OUTPUT" 2>/dev/null | tr '\n' ' ' | sed 's/"/\\"/g')\"}" >> "$OUTFILE"
fi

# Cleanup
rm -f "$CLAUDE_OUTPUT"

# Add done marker
echo "" >> "$OUTFILE"
echo "__CLAUDE_DONE__" >> "$OUTFILE"
