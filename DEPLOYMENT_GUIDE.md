# Deployment Guide: Which Setup Should I Use?

This guide helps you choose the right deployment setup based on your use case.

## 🎯 Quick Decision Tree

```
┌─ What do you want to do? ─────────────────────────────────────┐
│                                                                │
│  1. Use with Claude Desktop locally?                          │
│     ├─ Yes → See: Setup A (Local MCP)                        │
│     └─ No  → Continue...                                      │
│                                                                │
│  2. Use Claude from your mobile/tablet with MCP tools?       │
│     ├─ Yes → See: Setup D (Claude API Proxy) 🌟              │
│     └─ No  → Continue...                                      │
│                                                                │
│  3. Build custom mobile app calling MCP tools directly?      │
│     ├─ Yes → See: Setup B (Pinggy Remote Access)            │
│     └─ No  → Continue...                                      │
│                                                                │
│  4. Use both Claude Desktop AND mobile app?                   │
│     └─ Yes → See: Setup C (Both Services)                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Important Notes:**
- ❌ Claude Mobile app does NOT support MCP natively
- ❌ Claude Web (claude.ai) does NOT support MCP
- ✅ Setup D lets you use Claude from mobile WITH MCP tools (via Claude API)
- ✅ Setup B is for building YOUR OWN mobile app

---

## Setup A: Local MCP for Claude Desktop

**Use this when:** You only want to use the MCP server with Claude Desktop on your laptop.

### 📁 Files to Use
- **Dockerfile:** `Dockerfile`
- **Docker Service:** `investor-agent`
- **Claude Config:** Required ✅

### 🚀 How to Run

#### Option 1: With Docker Compose

```bash
# 1. Configure environment
cp .env.template .env
# Edit .env and set API keys (ALPACA, QUESTRADE, etc.)

# 2. Start the service
docker-compose up -d investor-agent

# 3. Check it's running
docker ps
```

#### Option 2: With Docker directly

```bash
# 1. Build the image
docker build -f Dockerfile -t investor-agent-mcp:latest .

# 2. Run the container
docker run -d \
  --name investor-agent-mcp \
  --env-file .env \
  investor-agent-mcp:latest

# Container will stay running (tail -f /dev/null)
```

### ⚙️ Claude Desktop Configuration

Add this to your `claude_desktop_config.json`:

**Location:**
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

**Configuration:**

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
        "mcp.server.stdio",
        "investor_agent.server:mcp"
      ],
      "env": {
        "ALPACA_API_KEY": "your_alpaca_key",
        "ALPACA_API_SECRET": "your_alpaca_secret",
        "QUESTRADE_REFRESH_TOKEN": "your_questrade_token"
      }
    }
  }
}
```

**Or without Docker (uvx):**

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

### ✅ How to Verify

1. Restart Claude Desktop
2. Look for the 🔌 icon at the bottom
3. You should see "investor-agent" listed
4. Try asking Claude: "What are today's top stock gainers?"

### 📊 What You Can Do
- ✅ Ask Claude to analyze stocks
- ✅ Get market data through Claude
- ✅ All 28 MCP tools available via Claude chat
- ❌ Cannot call from mobile apps (local only)
- ❌ No web API access

---

## Setup B: Pinggy Remote Access (Mobile Apps & Web API)

**Use this when:** You want to call MCP tools from a mobile app, web app, or any HTTP client.

### 📁 Files to Use
- **Dockerfile:** `Dockerfile.pinggy`
- **Docker Service:** `investor-agent-pinggy`
- **Claude Config:** Not needed ❌ (this is a REST API)

### 🚀 How to Run

#### Option 1: With Docker Compose (Recommended)

```bash
# 1. Configure environment
cp .env.template .env

# 2. Edit .env and set:
MCP_API_KEY=your-secure-random-key-here  # REQUIRED!
ENABLE_PINGGY_TUNNEL=false              # true to auto-create tunnel
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
QUESTRADE_REFRESH_TOKEN=...

# 3. Start the service
docker-compose up -d investor-agent-pinggy

# 4. Check logs
docker-compose logs -f investor-agent-pinggy
```

#### Option 2: With Docker directly

```bash
# 1. Build the image
docker build -f Dockerfile.pinggy -t investor-agent-pinggy:latest .

# 2. Run the container
docker run -d \
  --name investor-agent-pinggy \
  --env-file .env \
  -p 8000:8000 \
  investor-agent-pinggy:latest
```

### 🌐 Creating the Pinggy Tunnel

#### Method 1: Auto-tunnel (in Docker)

Set in `.env`:
```bash
ENABLE_PINGGY_TUNNEL=true
```

Restart the container:
```bash
docker-compose restart investor-agent-pinggy
docker-compose logs -f investor-agent-pinggy  # See the Pinggy URL
```

#### Method 2: Manual tunnel (from host)

```bash
# While container is running, create tunnel from your laptop
ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

You'll see output like:
```
https://randomstring.a.pinggy.io
```

This is your public URL! 🎉

### ✅ How to Verify

**Test locally:**
```bash
curl http://localhost:8000/health
```

**Test via Pinggy:**
```bash
curl https://your-url.a.pinggy.io/health
```

**List tools:**
```bash
curl -H "X-API-Key: your-api-key" \
     https://your-url.a.pinggy.io/tools
```

**Call a tool:**
```bash
curl -X POST https://your-url.a.pinggy.io/call \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "tool_name": "get_market_movers",
    "arguments": {"category": "gainers", "count": 5}
  }'
```

### 📊 What You Can Do
- ✅ Call from iOS/Android apps
- ✅ Call from web applications
- ✅ Call from any HTTP client (curl, Postman, etc.)
- ✅ Interactive API docs at `/docs`
- ✅ Access from anywhere via Pinggy URL
- ❌ Not integrated with Claude Desktop (it's a REST API)

### 📱 Mobile App Example

```javascript
// React Native / JavaScript
const response = await fetch('https://your-url.a.pinggy.io/call', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    tool_name: 'get_ticker_data',
    arguments: { ticker: 'AAPL' }
  })
});

const data = await response.json();
console.log(data.result);
```

---

## Setup C: Both Services (Claude Desktop + Mobile Apps)

**Use this when:** You want to use Claude Desktop AND make HTTP API calls from mobile/web apps.

### 📁 Files to Use
- **Both Dockerfiles:** `Dockerfile` AND `Dockerfile.pinggy`
- **Docker Services:** Both `investor-agent` and `investor-agent-pinggy`
- **Claude Config:** Required ✅

### 🚀 How to Run

```bash
# 1. Configure environment
cp .env.template .env

# 2. Edit .env and set ALL required keys:
MCP_API_KEY=your-secure-random-key-here  # For Pinggy
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
QUESTRADE_REFRESH_TOKEN=...
ENABLE_PINGGY_TUNNEL=false  # true for auto-tunnel

# 3. Start BOTH services
docker-compose up -d

# This starts:
# - investor-agent (for Claude Desktop)
# - investor-agent-pinggy (for web/mobile access)
```

### ⚙️ Claude Desktop Configuration

Use the same config as Setup A:

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
        "mcp.server.stdio",
        "investor_agent.server:mcp"
      ],
      "env": {
        "ALPACA_API_KEY": "your_alpaca_key",
        "ALPACA_API_SECRET": "your_alpaca_secret",
        "QUESTRADE_REFRESH_TOKEN": "your_questrade_token"
      }
    }
  }
}
```

### 🌐 Create Pinggy Tunnel for Mobile Access

```bash
# Create tunnel for the Pinggy service
ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

### ✅ How to Verify

**Check both containers:**
```bash
docker ps

# You should see:
# - investor-agent-mcp (no ports exposed)
# - investor-agent-pinggy (port 8000 exposed)
```

**Test Claude Desktop:**
1. Restart Claude Desktop
2. Look for 🔌 icon
3. Ask: "What are today's top gainers?"

**Test Pinggy API:**
```bash
curl -H "X-API-Key: your-api-key" \
     https://your-url.a.pinggy.io/health
```

### 📊 What You Can Do
- ✅ Use with Claude Desktop locally
- ✅ Call from mobile/web apps remotely
- ✅ Best of both worlds!
- ⚠️ Runs two containers (more resources)

---

## Setup D: Claude API Proxy (Use Claude from Mobile with MCP) 🌟

**Use this when:** You want to use Claude from your mobile device/browser AND have access to MCP tools.

**⚠️ Important:** This requires a Claude API key and will incur API usage costs (~$0.002-0.005 per query).

### 📁 Files to Use
- **Python Script:** `claude_proxy_service.py`
- **Mobile UI (optional):** `mobile_chat.html`
- **Claude Config:** Not needed ❌ (this uses Claude API, not Desktop)

### 🚀 How to Run

```bash
# 1. Configure environment
cp .env.template .env

# 2. Edit .env and set:
ANTHROPIC_API_KEY=sk-ant-your-key-here  # REQUIRED! Get from console.anthropic.com
MCP_API_KEY=your-secure-key            # Optional but recommended
CLAUDE_PROXY_PORT=8001                 # Optional, defaults to 8001
ALPACA_API_KEY=...                     # For MCP tools
QUESTRADE_REFRESH_TOKEN=...            # For MCP tools

# 3. Start the proxy service
python claude_proxy_service.py

# 4. Create Pinggy tunnel
ssh -p 443 -R0:localhost:8001 a.pinggy.io
# Note the HTTPS URL you get
```

### 📱 Access from Mobile

**Option 1: Use Mobile Chat Interface**

1. Open `mobile_chat.html` in your mobile browser
2. Click ⚙️ Settings
3. Enter your Pinggy URL: `https://your-url.a.pinggy.io`
4. Enter API key if you set MCP_API_KEY
5. Save and start chatting!

**Option 2: Build Your Own App**

```javascript
// Your mobile app (React Native, Flutter, etc.)
const response = await fetch('https://your-pinggy-url.a.pinggy.io/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    message: "What are today's top stock gainers?",
    conversation_history: [],
    model: 'claude-3-5-sonnet-20241022'
  })
});

const data = await response.json();
console.log(data.response);          // Claude's answer
console.log(data.tool_calls_made);   // MCP tools that were called
```

### ✅ How to Verify

**Test locally first:**
```bash
# Check health
curl http://localhost:8001/health

# List available tools
curl http://localhost:8001/tools

# Test chat
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Apple stock price?"}'
```

**Test via Pinggy:**
```bash
curl https://your-url.a.pinggy.io/health
```

### 📊 What You Can Do
- ✅ Use Claude from your mobile device
- ✅ Claude has access to ALL 28 MCP tools
- ✅ Claude automatically calls tools when needed
- ✅ Works from anywhere (not just your home WiFi)
- ✅ Mobile-friendly chat interface included
- ⚠️ Requires Claude API key (costs money)
- ⚠️ Laptop must be running for MCP tools to work

### 💰 Cost Estimate

Claude API usage (approximate):
- Simple query: ~$0.001
- Query with 1-2 tool calls: ~$0.002-0.003
- Complex query with multiple tools: ~$0.005-0.010

Example: 100 queries/day = ~$0.20-0.50/day

See: https://www.anthropic.com/pricing

### 🔍 How It Works

```
Mobile Browser/App
    ↓ "What are top gainers?"
Claude API Proxy (your laptop)
    ↓ Calls get_market_movers()
MCP Server
    ↓ Returns stock data
Claude API Proxy
    ↓ Sends data to Claude API
Anthropic's Servers
    ↓ Claude analyzes data
    ↓ Returns formatted answer
Mobile Browser/App
    ✓ Shows "Here are today's top gainers: ..."
```

### 📖 Full Documentation

See **[CLAUDE_MOBILE_SOLUTION.md](CLAUDE_MOBILE_SOLUTION.md)** for:
- Detailed setup instructions
- Security best practices
- Troubleshooting guide
- Alternative solutions comparison

---

## 📋 Quick Reference Table

| Feature | Setup A<br>(Local MCP) | Setup B<br>(Pinggy API) | Setup C<br>(Both) | Setup D<br>(Claude API Proxy) |
|---------|------------------------|-------------------------|-------------------|-------------------------------|
| **Dockerfile** | `Dockerfile` | `Dockerfile.pinggy` | Both | None (Python script) |
| **Service** | `investor-agent` | `investor-agent-pinggy` | Both | `claude_proxy_service.py` |
| **Claude Config** | ✅ Required | ❌ Not needed | ✅ Required | ❌ Not needed |
| **Claude Desktop** | ✅ Yes | ❌ No | ✅ Yes | ❌ No |
| **Claude from Mobile** | ❌ No | ❌ No | ❌ No | ✅ Yes 🌟 |
| **Custom Mobile Apps** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Web API** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Pinggy Tunnel** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **MCP_API_KEY** | Not needed | ✅ Required | ✅ Required | Optional |
| **ANTHROPIC_API_KEY** | ❌ No | ❌ No | ❌ No | ✅ Required |
| **Port Exposed** | None | 8000 | 8000 | 8001 |
| **API Costs** | Free | Free | Free | ~$0.20-0.50/day |
| **Resource Usage** | Low | Medium | High | Low |

---

## 🔧 Environment Variables by Setup

### Setup A (Local MCP)
```bash
# Required
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
QUESTRADE_REFRESH_TOKEN=...

# Optional
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=...
```

### Setup B (Pinggy API)
```bash
# Required
MCP_API_KEY=your-secure-random-key  # MUST set this!
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
QUESTRADE_REFRESH_TOKEN=...

# Optional
ENABLE_PINGGY_TUNNEL=false
PINGGY_SUBDOMAIN=
RATE_LIMIT_CALLS=100
RATE_LIMIT_WINDOW=3600
```

### Setup C (Both)
```bash
# Required (all of the above)
MCP_API_KEY=your-secure-random-key
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
QUESTRADE_REFRESH_TOKEN=...

# Optional
ENABLE_PINGGY_TUNNEL=false
PINGGY_SUBDOMAIN=
RATE_LIMIT_CALLS=100
RATE_LIMIT_WINDOW=3600
```

---

## 🚦 Common Commands

### Managing Services

```bash
# Start specific service
docker-compose up -d investor-agent         # Local MCP only
docker-compose up -d investor-agent-pinggy  # Pinggy API only
docker-compose up -d                        # Both services

# Stop specific service
docker-compose stop investor-agent
docker-compose stop investor-agent-pinggy

# View logs
docker-compose logs -f investor-agent
docker-compose logs -f investor-agent-pinggy

# Restart after config changes
docker-compose restart investor-agent-pinggy

# Stop all and remove
docker-compose down
```

### Creating Pinggy Tunnels

```bash
# From host machine (recommended)
ssh -p 443 -R0:localhost:8000 a.pinggy.io

# From inside Docker container
docker exec -it investor-agent-pinggy \
    ssh -p 443 -R0:localhost:8000 a.pinggy.io

# With custom subdomain (paid)
ssh -p 443 -R0:localhost:8000 -t a.pinggy.io my-investor-agent
```

---

## 📚 Related Documentation

- **[DOCKER_PINGGY.md](DOCKER_PINGGY.md)** - Complete Docker guide with mobile app examples
- **[PINGGY_SETUP.md](PINGGY_SETUP.md)** - Detailed Pinggy setup and usage
- **[PINGGY_QUICKSTART.md](PINGGY_QUICKSTART.md)** - Quick reference guide
- **[README.md](README.md)** - Main project documentation

---

## 🆘 Troubleshooting

### "Container won't start"
```bash
# Check logs
docker-compose logs investor-agent-pinggy

# Common issue: Missing MCP_API_KEY
# Solution: Add to .env file
echo "MCP_API_KEY=$(openssl rand -hex 32)" >> .env
```

### "Claude Desktop can't connect"
```bash
# 1. Check container is running
docker ps | grep investor-agent-mcp

# 2. Verify Claude config path is correct
# 3. Restart Claude Desktop
# 4. Check for errors in Claude's logs
```

### "Pinggy tunnel disconnects"
```bash
# Use ServerAliveInterval to keep connection alive
ssh -o ServerAliveInterval=30 -p 443 -R0:localhost:8000 a.pinggy.io

# Or enable auto-tunnel in Docker
ENABLE_PINGGY_TUNNEL=true
```

### "401 Unauthorized on API calls"
```bash
# Verify API key matches
docker exec investor-agent-pinggy env | grep MCP_API_KEY

# Test with correct key
curl -H "X-API-Key: $(grep MCP_API_KEY .env | cut -d= -f2)" \
     http://localhost:8000/health
```

---

## 💡 Best Practices

1. **Development:** Use Setup B (Pinggy) for mobile app development
2. **Personal Use:** Use Setup A (Local MCP) with Claude Desktop
3. **Production:** Use Setup C (Both) with proper security
4. **Testing:** Use Setup B without tunnel (local access only)
5. **Demos:** Use Setup B with `ENABLE_PINGGY_TUNNEL=true`

---

## 🎓 Examples

### Example 1: Solo Developer with Claude Desktop
```bash
# Just want to use Claude Desktop
docker-compose up -d investor-agent
# Configure Claude Desktop with config from Setup A
# Done! ✅
```

### Example 2: Mobile App Developer
```bash
# Building an iOS/Android app
docker-compose up -d investor-agent-pinggy
ssh -p 443 -R0:localhost:8000 a.pinggy.io
# Use the Pinggy URL in your mobile app
# Done! ✅
```

### Example 3: Full Stack Developer
```bash
# Want both Claude Desktop and mobile app access
docker-compose up -d
ssh -p 443 -R0:localhost:8000 a.pinggy.io
# Configure Claude Desktop with config from Setup A
# Use Pinggy URL in mobile app
# Done! ✅
```

---

**Need help?** See the troubleshooting section above or check the related documentation.
