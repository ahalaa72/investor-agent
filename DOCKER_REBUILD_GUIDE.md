# Rebuilding Docker Container with Latest Questrade Fixes

## Issue
Claude Desktop cannot use Questrade tools because the Docker container is running old code.

## Solution
Rebuild the Docker container with all the latest fixes.

---

## Step-by-Step Fix

### 1. Stop the Current Container

```bash
docker-compose down
```

### 2. Pull Latest Code (Already Done ✅)

You're already on the latest commit: `2833b9a`

### 3. Rebuild Docker Image (CRITICAL)

```bash
# Build with --no-cache to ensure fresh build
docker-compose build --no-cache
```

**Expected output:**
```
[+] Building 45.2s (15/15) FINISHED
 => [internal] load build definition from Dockerfile
 => => transferring dockerfile: 1.23kB
 => [internal] load .dockerignore
 => ...
 => => naming to docker.io/library/investor-agent-mcp:latest
```

### 4. Start Container with New Image

```bash
docker-compose up -d
```

**Expected output:**
```
[+] Running 1/1
 ✔ Container investor-agent-mcp  Started
```

### 5. Verify Container is Running

```bash
docker-compose ps
```

**Expected output:**
```
NAME                 STATUS              PORTS
investor-agent-mcp   Up X seconds
```

### 6. Check Container Logs

```bash
docker-compose logs investor-agent
```

Look for:
- ✅ "Starting MCP server"
- ✅ No errors about missing questrade-api package
- ✅ No import errors

### 7. Verify Questrade Tools are Loaded in Container

```bash
docker-compose exec investor-agent python -c "
from investor_agent import server
tools = list(server.mcp._tool_manager._tools.keys())
questrade_tools = [t for t in tools if 'questrade' in t.lower()]
print(f'Total tools: {len(tools)}')
print(f'Questrade tools: {len(questrade_tools)}')
print('\nQuestrade Tools:')
for tool in sorted(questrade_tools):
    print(f'  ✅ {tool}')
"
```

**Expected output:**
```
Total tools: 39
Questrade tools: 15

Questrade Tools:
  ✅ get_questrade_accounts
  ✅ get_questrade_activities
  ✅ get_questrade_balances
  ✅ get_questrade_candles
  ✅ get_questrade_executions
  ✅ get_questrade_markets
  ✅ get_questrade_option_quotes
  ✅ get_questrade_options_chain
  ✅ get_questrade_order
  ✅ get_questrade_orders
  ✅ get_questrade_positions
  ✅ get_questrade_quote
  ✅ get_questrade_quotes
  ✅ get_questrade_symbol_info
  ✅ search_questrade_symbols
```

### 8. Test One Tool Directly in Container

```bash
docker-compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client
client = get_questrade_client()
accounts = client.get_accounts()
print(f'✅ Retrieved {len(accounts[\"accounts\"])} accounts')
"
```

**Expected output:**
```
2025-11-07 XX:XX:XX - INFO - QuestradeClient initialized
2025-11-07 XX:XX:XX - INFO - Using stored Questrade tokens from ~/.questrade.json
2025-11-07 XX:XX:XX - INFO - Questrade API client connected
2025-11-07 XX:XX:XX - INFO - Fetching Questrade accounts
2025-11-07 XX:XX:XX - INFO - Retrieved 7 accounts
✅ Retrieved 7 accounts
```

### 9. Restart Claude Desktop

**Important:** Claude Desktop caches the MCP server connection.

**On macOS:**
1. Quit Claude Desktop completely (Cmd+Q)
2. Wait 5 seconds
3. Relaunch Claude Desktop

**On Windows:**
1. Close Claude Desktop
2. Wait 5 seconds
3. Relaunch Claude Desktop

### 10. Verify in Claude Desktop

In Claude Desktop, check for Questrade tools:

1. Look for the 🔌 MCP icon in the input box
2. You should see 15 Questrade tools available:
   - get_questrade_accounts
   - get_questrade_positions
   - get_questrade_balances
   - get_questrade_quote
   - get_questrade_quotes
   - get_questrade_candles
   - search_questrade_symbols
   - get_questrade_symbol_info
   - get_questrade_markets
   - get_questrade_orders
   - get_questrade_order
   - get_questrade_executions
   - get_questrade_activities
   - get_questrade_options_chain
   - get_questrade_option_quotes

---

## Troubleshooting

### Issue: "Cannot connect to MCP server"

**Check MCP configuration:**

```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Should contain:**

```json
{
  "mcpServers": {
    "investor-agent": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "investor-agent-mcp",
        "python",
        "-m",
        "investor_agent"
      ]
    }
  }
}
```

### Issue: "Container not found"

**Check container name:**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

If the name is different, update your MCP config.

### Issue: "Tool errors when called"

**Check token file exists in container:**

```bash
docker-compose exec investor-agent ls -la /root/.questrade.json
```

If missing, the container will use your manual token from `.env` on first call.

### Issue: "Still seeing old code/behavior"

**Force complete rebuild:**

```bash
# Remove everything
docker-compose down
docker rmi investor-agent-mcp:latest

# Rebuild from scratch
docker-compose build --no-cache

# Start fresh
docker-compose up -d
```

---

## Quick Verification Checklist

- [ ] Docker container rebuilt: `docker-compose build --no-cache`
- [ ] Container is running: `docker-compose ps`
- [ ] No errors in logs: `docker-compose logs investor-agent`
- [ ] 15 Questrade tools loaded in container
- [ ] Test tool works: `get_questrade_accounts()` succeeds
- [ ] Token file persists: `/root/.questrade.json` exists in container
- [ ] Claude Desktop restarted completely
- [ ] MCP config points to correct container
- [ ] Tools visible in Claude Desktop MCP menu

---

## Expected Result

After rebuilding and restarting Claude Desktop, you should see all 15 Questrade tools available and working, with:

✅ No "worked once, now 400 error" issues
✅ Token persistence across container restarts
✅ All market data, orders, historical, and options tools functional
✅ Clean error messages with helpful troubleshooting

---

## Need Help?

If still not working after rebuild:

1. Share Docker logs: `docker-compose logs investor-agent | tail -50`
2. Share tool verification output from Step 7
3. Check Claude Desktop logs (Help → View Logs)
