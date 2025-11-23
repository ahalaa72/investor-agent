# Dual Mode Setup: Claude Desktop + Mobile API Proxy

This guide shows you how to run **BOTH** setups simultaneously:
- **Claude Desktop** (local MCP via stdio)
- **Claude API Proxy** (mobile access via FastAPI)

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Laptop                              │
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │  Claude Desktop  │         │ Claude API Proxy │        │
│  │                  │         │                  │        │
│  │  Calls MCP via   │         │  Port: 8001      │        │
│  │  stdio           │         │  FastAPI Server  │        │
│  └────────┬─────────┘         └────────┬─────────┘        │
│           │                            │                   │
│           └────────┬───────────────────┘                   │
│                    │                                       │
│           ┌────────▼─────────┐                            │
│           │   MCP Server     │                            │
│           │  28 Tools        │                            │
│           │  (Python)        │                            │
│           └──────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Pinggy Tunnel
                              ▼
                    ┌──────────────────┐
                    │   Your Mobile    │
                    │   Browser/App    │
                    └──────────────────┘
```

**Key Point:** The MCP server runs once, but can be accessed by:
1. Claude Desktop (local, via stdio)
2. Claude API Proxy (which then exposes via HTTP)

## Prerequisites

- Python 3.12+
- Claude Desktop app installed
- Anthropic API key (for mobile proxy)
- Internet connection

## Step-by-Step Setup

### Step 1: Configure Environment

```bash
# 1. Navigate to project
cd /home/user/investor-agent

# 2. Copy environment template
cp .env.template .env

# 3. Edit .env with your credentials
nano .env  # or your preferred editor
```

**Required configuration in `.env`:**

```bash
# ==========================================
# REQUIRED for MCP Tools
# ==========================================
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_API_SECRET=your_alpaca_api_secret
QUESTRADE_REFRESH_TOKEN=your_questrade_refresh_token

# ==========================================
# REQUIRED for Mobile (Claude API Proxy)
# ==========================================
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key

# ==========================================
# OPTIONAL Security
# ==========================================
MCP_API_KEY=your-secure-random-key-for-mobile-access

# ==========================================
# OPTIONAL Response Control
# ==========================================
CLAUDE_RESPONSE_MODE=balanced  # concise, balanced, or detailed
CLAUDE_PROXY_PORT=8001
```

Save and close the file.

### Step 2: Install Dependencies

```bash
# Install with bridge dependencies (includes FastAPI)
pip install -e ".[bridge]"

# Or with uv
uv pip install -e ".[bridge]"
```

### Step 3: Configure Claude Desktop

Edit your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

**Option A: Using uvx (Recommended)**

```json
{
  "mcpServers": {
    "investor-agent": {
      "command": "uvx",
      "args": ["investor-agent"],
      "env": {
        "ALPACA_API_KEY": "your_alpaca_key",
        "ALPACA_API_SECRET": "your_alpaca_secret",
        "QUESTRADE_REFRESH_TOKEN": "your_questrade_token"
      }
    }
  }
}
```

**Option B: Using Python directly**

```json
{
  "mcpServers": {
    "investor-agent": {
      "command": "python",
      "args": ["-m", "mcp", "run", "/home/user/investor-agent/investor_agent/server.py"],
      "env": {
        "ALPACA_API_KEY": "your_alpaca_key",
        "ALPACA_API_SECRET": "your_alpaca_secret",
        "QUESTRADE_REFRESH_TOKEN": "your_questrade_token"
      }
    }
  }
}
```

Save the file.

### Step 4: Start the Claude API Proxy

Open a terminal and start the proxy service:

```bash
# Terminal 1: Start Claude API Proxy
cd /home/user/investor-agent
python claude_proxy_service.py
```

You should see output like:
```
INFO:     Starting Claude API Proxy on port 8001
INFO:     API Key Auth: Enabled
INFO:     Response mode: balanced, Max tokens: 2048
INFO:     Available MCP tools: 28
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

**✅ Proxy is running!**

### Step 5: Start Claude Desktop

1. Launch Claude Desktop application
2. Wait a few seconds for it to connect to MCP
3. Look for the 🔌 (plug) icon at the bottom of the window
4. Click it to see "investor-agent" listed

**✅ Claude Desktop is connected!**

### Step 6: Create Pinggy Tunnel (for Mobile Access)

Open a **second terminal**:

```bash
# Terminal 2: Create Pinggy tunnel
ssh -p 443 -R0:localhost:8001 a.pinggy.io
```

You'll see output like:
```
You can access local server via following URL:
https://randomstring-abc123.a.pinggy.io
```

**Copy this URL!** This is your mobile access point.

**✅ Tunnel is created!**

---

## Testing the Setup

### Test 1: Claude Desktop (Local)

In Claude Desktop app, type:

```
What are today's top 5 stock gainers?
```

**Expected result:**
- Claude should call the `get_market_movers` tool
- You'll see a response with real stock data
- Check for tool usage indicator

**✅ If you get stock data, Claude Desktop works!**

### Test 2: Claude API Proxy (Local)

In a **third terminal**:

```bash
# Terminal 3: Test proxy locally
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "message": "What is Apple stock price?",
    "response_mode": "concise"
  }'
```

**Expected result:**
```json
{
  "response": "Apple (AAPL) is currently trading at $185.50, up 2.3% today...",
  "tool_calls_made": ["get_ticker_data(ticker='AAPL')"],
  "usage": {
    "input_tokens": 245,
    "output_tokens": 87
  },
  "estimated_cost": 0.0021,
  "response_mode": "concise"
}
```

**✅ If you get a response with cost, proxy works locally!**

### Test 3: Mobile Access via Pinggy

On your mobile device browser, open:

```
https://your-pinggy-url.a.pinggy.io
```

Or test from terminal:

```bash
curl -X POST https://your-pinggy-url.a.pinggy.io/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "message": "What are the top 3 market movers?",
    "response_mode": "balanced"
  }'
```

**✅ If you get a response, mobile access works!**

### Test 4: Use Mobile Chat Interface

1. Open `mobile_chat.html` in your mobile browser
2. Click ⚙️ Settings
3. Enter:
   - **API URL:** `https://your-pinggy-url.a.pinggy.io`
   - **API Key:** `your-api-key` (if you set MCP_API_KEY)
4. Save
5. Ask: "What are today's top gainers?"

**✅ If you get an answer with tool indicators, it works!**

---

## Simultaneous Usage Example

### Scenario: You're researching stocks

**On your laptop (Claude Desktop):**
```
You: "Give me a detailed analysis of Tesla including financials
     and technical indicators"

Claude: [Calls multiple tools]
        "Here's a comprehensive analysis of Tesla..."
```

**At the same time, on your phone:**
```
You: "Quick - what's Apple's current price?"

Mobile: [Via Claude API Proxy]
        "AAPL is at $185.50, up 2.3%"
        Cost: $0.0018
```

**Both work simultaneously!** They're using the same MCP server but different interfaces.

---

## Understanding the Architecture

### What's Running

1. **MCP Server** (Python process)
   - Runs automatically when Claude Desktop connects
   - Provides 28 financial analysis tools
   - Can be called by multiple clients

2. **Claude Desktop** (App)
   - Calls MCP server via stdio
   - Free to use
   - Full conversation UI
   - Local only

3. **Claude API Proxy** (Python FastAPI)
   - Separate process on port 8001
   - Imports and uses MCP tools
   - Calls Claude API with tool results
   - Accessible remotely via Pinggy

### Process List

When everything is running:

```bash
# Check running processes
ps aux | grep -E "claude|uvicorn|python"

# You should see:
# - Claude Desktop app
# - python claude_proxy_service.py (port 8001)
# - ssh tunnel (Pinggy)
```

---

## Daily Usage Workflow

### Starting Everything

**Morning routine (3 commands):**

```bash
# Terminal 1: Start proxy
cd /home/user/investor-agent
python claude_proxy_service.py &

# Terminal 2: Create tunnel
ssh -p 443 -R0:localhost:8001 a.pinggy.io &

# Launch Claude Desktop
open -a Claude  # macOS
# or just click the app icon
```

### Stopping Everything

**End of day:**

```bash
# Stop proxy
pkill -f claude_proxy_service

# Stop tunnel
pkill -f "ssh.*pinggy"

# Close Claude Desktop
# (just quit the app)
```

---

## Troubleshooting

### Issue 1: Claude Desktop not seeing MCP tools

**Symptoms:** No 🔌 icon, or icon shows but no tools

**Solutions:**
```bash
# 1. Check Claude Desktop config
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# 2. Restart Claude Desktop completely
killall Claude
open -a Claude

# 3. Check logs (macOS)
tail -f ~/Library/Logs/Claude/mcp*.log
```

### Issue 2: Proxy won't start

**Symptoms:** "Port already in use" or "ANTHROPIC_API_KEY not set"

**Solutions:**
```bash
# Check if port 8001 is in use
lsof -i :8001

# If something is using it, kill it
kill -9 <PID>

# Verify .env has ANTHROPIC_API_KEY
grep ANTHROPIC_API_KEY .env
```

### Issue 3: Mobile can't connect

**Symptoms:** Timeout or connection refused

**Solutions:**
```bash
# 1. Check proxy is running
curl http://localhost:8001/health

# 2. Check Pinggy tunnel is up
# Look for "https://" URL in terminal 2

# 3. Test tunnel
curl https://your-url.a.pinggy.io/health

# 4. Check API key if set
curl -H "X-API-Key: your-key" https://your-url.a.pinggy.io/health
```

### Issue 4: Both work separately, not together

**This is normal!** They're completely independent:
- Claude Desktop connects directly to MCP server
- Proxy imports MCP tools and runs separately
- They can both run at the same time

**No conflict because:**
- Different interfaces (stdio vs HTTP)
- Different Claude instances (Desktop app vs API)
- Both can call MCP tools simultaneously

---

## Cost Tracking

When running both:

### Claude Desktop: FREE ✅
- Uses local MCP server
- No API costs
- Unlimited queries

### Claude API Proxy: PAID 💰
- Uses Claude API (~$0.002-0.006 per query)
- Track costs in proxy responses
- Set `CLAUDE_RESPONSE_MODE=concise` to save money

**Example daily costs:**
- Desktop: 50 queries = $0.00 (free)
- Mobile: 30 queries × $0.003 = $0.09
- **Total: $0.09/day = $2.70/month**

---

## Advanced: Auto-start on Boot

### macOS/Linux: Using systemd or launchd

Create `~/Library/LaunchAgents/com.investor-agent.proxy.plist` (macOS):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.investor-agent.proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/home/user/investor-agent/claude_proxy_service.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/investor-agent-proxy.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/investor-agent-proxy.out</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.investor-agent.proxy.plist
```

---

## Quick Reference

| Component | Status Check | Port | Cost |
|-----------|-------------|------|------|
| **Claude Desktop** | Look for 🔌 icon | - | Free |
| **Claude API Proxy** | `curl localhost:8001/health` | 8001 | ~$0.003/query |
| **Pinggy Tunnel** | Check terminal 2 output | - | Free |

### Useful Commands

```bash
# Start proxy
python claude_proxy_service.py

# Create tunnel
ssh -p 443 -R0:localhost:8001 a.pinggy.io

# Test proxy health
curl http://localhost:8001/health

# Test with query
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "AAPL price?", "response_mode": "concise"}'

# Check what's running
lsof -i :8001
ps aux | grep claude
```

---

## Summary

✅ **What you get:**
1. Claude Desktop with full MCP access (FREE)
2. Mobile access with Claude intelligence ($0.002-0.006/query)
3. Both can run simultaneously
4. Best of both worlds!

🎯 **Use cases:**
- **Desktop:** Deep research, detailed analysis, extended conversations
- **Mobile:** Quick checks, on-the-go queries, price lookups

💰 **Costs:**
- Desktop: $0 (unlimited)
- Mobile: ~$2-5/month (typical usage)

🚀 **You're all set!** Both modes are now running and tested.

---

**Next steps:**
1. Start using Claude Desktop for research
2. Test mobile chat interface
3. Monitor costs in proxy responses
4. Adjust `CLAUDE_RESPONSE_MODE` based on needs

Enjoy your dual-mode investor agent! 📈💼
