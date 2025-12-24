# MCP "Not Connected" Issue After Docker Restart

## Problem Summary

After restarting the `investor-agent-mcp` Docker container, the MCP client in Claude Code shows **"Not connected"** and won't reconnect automatically, even though the server is running perfectly.

## Symptoms

1. Container is running: `docker ps` shows `investor-agent-mcp` is up
2. Server responds correctly when tested directly via stdin/stdout
3. All MCP tools work when tested with raw JSON-RPC protocol
4. But Claude Code shows: `Error: Not connected` for all tool calls
5. Waiting doesn't help - connection never restores automatically

## Root Cause

**Claude Code MCP client does NOT auto-reconnect when the underlying container restarts.**

The MCP client in Claude Code:
- Establishes connection when you first open Claude Code
- Caches the connection to the Docker container
- **Does NOT detect when container is restarted**
- **Does NOT auto-reconnect to the new container instance**

This is a **client-side limitation**, not a server issue.

## The Fix

**Option 1: Restart Claude Code (RECOMMENDED)**

```bash
# On macOS:
# 1. Quit Claude Code completely (Cmd+Q)
# 2. Reopen Claude Code
# MCP connection will be re-established automatically
```

**Option 2: Force MCP Reconnection (if supported)**

Some MCP clients support manual reconnection. Check if Claude Code has a "Reconnect MCP Servers" option in settings.

**Option 3: Avoid Container Restarts**

Instead of restarting the container, update code and refresh:

```bash
# DON'T DO THIS (breaks MCP connection):
docker-compose restart investor-agent

# DO THIS INSTEAD (preserves connection):
# 1. Make code changes in investor_agent/ directory
# 2. If using volume mount, changes are live immediately
# 3. If not using volume mount, copy files into running container:
docker cp investor_agent/server.py investor-agent-mcp:/app/investor_agent/server.py
```

## Testing MCP Server Without Client

To verify the MCP server is working without Claude Code:

```bash
# Test MCP protocol directly
cat << 'EOF' | docker exec -i investor-agent-mcp python -m investor_agent.server 2>&1
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","id":2,"method":"notifications/initialized"}
{"jsonrpc":"2.0","id":3,"method":"tools/list"}
EOF
```

If you see a list of tools in the response, the server is working correctly.

## Preventing This Issue

### 1. Use Hot-Reload Development Setup

Mount the code directory as a volume for live updates:

```yaml
# docker-compose.yml
services:
  investor-agent:
    volumes:
      - ./investor_agent:/app/investor_agent  # Hot reload
      - questrade-tokens:/root                # Persist tokens
```

This way, code changes don't require container restart.

### 2. Keep Container Running

The container is designed to run continuously with `tail -f /dev/null`. Only restart when:
- Updating dependencies (requirements.txt changes)
- Updating Docker configuration
- Updating entrypoint script

### 3. Update Code Without Restart

For code-only changes:

```bash
# Copy updated file to running container
docker cp investor_agent/server.py investor-agent-mcp:/app/investor_agent/server.py

# Or use hot-reload volume mount (see above)
```

## When You MUST Restart Container

If you must restart (e.g., new dependencies, environment variables):

1. Restart the container:
   ```bash
   docker-compose restart investor-agent
   ```

2. **Immediately restart Claude Code** to reconnect MCP client

3. Verify connection works:
   ```bash
   # Test any MCP tool via Claude Code
   ```

## What Happened in This Session

### Issue Timeline

1. **Fixed `analyze_competitors`**: Added 60+ industry mappings with fuzzy matching and sector fallback
2. **Rebuilt container**: To deploy the fix
3. **Container restarted**: New token loaded, old token file cleared
4. **MCP client lost connection**: Claude Code still showed old connection
5. **Server was working perfectly**: Tested via stdin/stdout - all tools responded correctly
6. **Client never reconnected**: Waited 2+ minutes, tried multiple times - still "Not connected"

### Verified Working

Direct MCP protocol tests showed:
- ✅ `analyze_competitors("NVDA")` → returned 5 competitors (TSM, QCOM, AMD, INTC, AVGO)
- ✅ `analyze_competitors("UNH")` → returned 5 competitors (HUM, CNC, ELV, CVS, CI) - **FIXED!**
- ✅ `get_questrade_accounts()` → returned 7 accounts with fresh token

**The server was fully functional. Only the MCP client connection was broken.**

## Technical Details

### Why Client Doesn't Auto-Reconnect

MCP clients typically:
1. Spawn subprocess: `docker exec -i investor-agent-mcp python -m investor_agent.server`
2. Keep stdin/stdout pipes open
3. Send JSON-RPC requests via stdin
4. Read responses from stdout

When container restarts:
- Old subprocess dies (container stopped)
- Pipes are broken
- Client doesn't detect this and retry
- Client still thinks old connection is alive
- New requests fail with "Not connected"

### Why Restart Claude Code Fixes It

Restarting Claude Code:
1. Kills all old MCP subprocess connections
2. Reads `.mcp.json` configuration again
3. Spawns fresh `docker exec` subprocess
4. Establishes new stdin/stdout pipes
5. Connection works again

## Summary

**Problem**: MCP client doesn't auto-reconnect after container restart
**Cause**: Client-side limitation in Claude Code
**Fix**: Restart Claude Code to force reconnection
**Prevention**: Use hot-reload volume mounts to avoid container restarts

**Time Lost**: 30 minutes waiting for auto-reconnection that never happens
**Lesson Learned**: Always restart Claude Code after restarting MCP server containers

---

**Last Updated**: 2025-12-23
**Applies To**: Claude Code with Docker-based MCP servers
