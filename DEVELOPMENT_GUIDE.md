# Development Guide for investor-agent

## CRITICAL: Code Changes Require Docker Rebuild

**The MCP server runs inside a Docker container.** When you modify code in `investor_agent/`, the changes will NOT take effect until you rebuild the Docker image.

### Why This Matters

```
Host Machine                    Docker Container
================                ==================
investor_agent/                 /app/investor_agent/
  server.py (YOUR EDITS)   !=     server.py (OLD CODE)
  questrade.py             !=     questrade.py
```

When you edit files on your host machine, the Docker container still has the **old code** baked into its image.

### How to Apply Code Changes

**Step 1: Rebuild the Docker Image**
```bash
cd /Users/AhmedE/git/investor-agent
docker build -t investor-agent-mcp .
```

**Step 2: Restart the Container**
```bash
docker stop investor-agent-mcp
docker rm investor-agent-mcp
docker run -d --name investor-agent-mcp \
  -v ~/.questrade.json:/root/.questrade.json \
  investor-agent-mcp
```

**Or use docker-compose (recommended):**
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### Quick One-Liner to Rebuild & Restart
```bash
docker-compose down && docker-compose build && docker-compose up -d
```

### Verify New Code is Running
```bash
# Check if your changes are in the container
docker exec investor-agent-mcp grep "YOUR_UNIQUE_STRING" /app/investor_agent/server.py

# Example: Check for "SMART SCAN RESULTS" (new code) vs "HIGH-QUALITY SCAN" (old code)
docker exec investor-agent-mcp grep -c "SMART SCAN RESULTS" /app/investor_agent/server.py
# Returns 1 if new code, 0 if old code
```

---

## Common Issues

### Issue 1: "I edited the code but MCP still shows old behavior"
**Cause:** Docker container has old code
**Fix:** Rebuild Docker image (see above)

### Issue 2: "pip install -e doesn't work"
**Cause:** `pip install -e` only works on the host, not inside Docker
**Fix:** Rebuild Docker image to get new code into container

### Issue 3: "Questrade token not working"
**Cause:** Token file might not be accessible inside container

**Check 1:** Verify token file exists
```bash
cat ~/.questrade.json
```

**Check 2:** Verify token is mounted in container
```bash
docker exec investor-agent-mcp cat /root/.questrade.json
```

**Fix:** If file only has `refresh_token` (no `access_token`), the code will auto-refresh. Updated code in `questrade.py` handles this case.

### Issue 4: "MCP server returns old cached scan results"
**Cause:** Scan cache (5 minute TTL)
**Fix:** Wait 5 minutes, or the cache is per-filter combination, so changing any filter will bypass cache

---

## Questrade Token Handling

### CRITICAL: Tokens are SINGLE-USE

Questrade refresh tokens are **consumed on first use**. Once used, the old token is **DEAD FOREVER**.

```
You get token from Questrade website: "abc123xyz"
         │
         ▼
First API call (get_questrade_accounts):
  1. Sends refresh_token to Questrade
  2. Questrade INVALIDATES "abc123xyz" forever
  3. Returns NEW access_token + NEW refresh_token
  4. Library saves to ~/.questrade.json
         │
         ▼
Original token "abc123xyz" = DEAD (cannot reuse)
```

### Token File Location

| Environment | Path |
|-------------|------|
| Docker Container | `/root/.questrade.json` |
| Local macOS/Linux | `~/.questrade.json` |

### Token File Formats

**Format 1: Just refresh token (new token from website)**
```json
{"refresh_token": "abc123xyz"}
```

**Format 2: Full token (after first API call)**
```json
{
  "refresh_token": "NEW_TOKEN_HERE",
  "access_token": "eyJ0eXAi...",
  "api_server": "https://api05.iq.questrade.com/",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

### How the Code Handles Tokens

1. If `access_token` is missing → forces refresh using `refresh_token`
2. If `access_token` exists and file is <4 min old → uses stored tokens
3. If file is >4 min old → refreshes using stored `refresh_token`

### When Questrade Fails with "400 Bad Request"

**Cause:** The refresh token was consumed (used elsewhere or expired)

**Fix:**
1. Go to: https://login.questrade.com/APIAccess/UserApps.aspx
2. Click "Generate new token"
3. Update the token in Docker container:
```bash
docker exec investor-agent-mcp bash -c 'echo "{\"refresh_token\": \"NEW_TOKEN\"}" > /root/.questrade.json'
```
4. Test via MCP: `get_questrade_accounts()`

### Avoid Token Conflicts

| Do | Don't |
|----|-------|
| Keep single container running | Run multiple containers with same token |
| Update token in container directly | Test manually on host while container runs |
| Use volume for persistence | Restart container without volume |

---

## Testing After Code Changes

**1. Test Questrade (MCP tool):**
```
get_questrade_accounts()
get_questrade_quotes(symbols=["AAPL"])
```

**2. Test Scanner with Progress Log:**
```
scan_market_opportunities(market="america", top_n=2, max_scan=20)
```
Check the response for `progress_log` field and "SCAN PROGRESS LOG" section in report.

**3. Verify specific code changes:**
```bash
# Check if new code is in container
docker exec investor-agent-mcp grep "YOUR_PATTERN" /app/investor_agent/server.py
```

---

## Development Workflow

1. Edit code in `investor_agent/` on host machine
2. **REBUILD DOCKER:** `docker-compose down && docker-compose build && docker-compose up -d`
3. Restart Claude Code (to reconnect MCP)
4. Test via MCP tools
5. Repeat

**DO NOT** just run `pip install -e .` and expect changes in Docker container!
