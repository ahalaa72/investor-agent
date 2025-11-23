# Docker Dual Mode Setup: Claude Desktop + Mobile API Proxy

This guide shows you how to run **BOTH** setups using Docker:
- **Claude Desktop** (connects to MCP container via stdio)
- **Claude API Proxy** (mobile access via FastAPI in container)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Laptop                              │
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │  Claude Desktop  │         │   Your Mobile    │        │
│  │      App         │         │   Browser/App    │        │
│  └────────┬─────────┘         └────────┬─────────┘        │
│           │                            │                   │
│           │ stdio                      │ HTTP (Pinggy)     │
│           │                            │                   │
│  ┌────────▼────────────────────────────▼─────────┐        │
│  │          Docker Environment                   │        │
│  │                                                │        │
│  │  ┌──────────────────┐  ┌──────────────────┐  │        │
│  │  │  MCP Container   │  │ Claude API Proxy │  │        │
│  │  │  Port: stdio     │  │  Port: 8001      │  │        │
│  │  │  28 Tools        │  │  FastAPI Server  │  │        │
│  │  └──────────────────┘  └──────────────────┘  │        │
│  │                                                │        │
│  └────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- ✅ Both modes work simultaneously
- ✅ Easy deployment with `docker-compose`
- ✅ Automatic restarts and health checks
- ✅ Isolated environments with consistent dependencies
- ✅ Simple updates with `docker-compose pull`

## Prerequisites

- Docker & Docker Compose installed
- Claude Desktop app installed
- Anthropic API key (for mobile proxy)
- Internet connection

## Quick Start (3 Commands)

```bash
# 1. Clone and configure
cd /home/user/investor-agent
cp .env.template .env
nano .env  # Add your API keys

# 2. Start all services
docker-compose up -d investor-agent investor-agent-claude-proxy

# 3. Configure Claude Desktop (see Step 3 below)
```

That's it! Now follow the detailed setup below.

---

## Detailed Setup

### Step 1: Configure Environment

```bash
# Navigate to project
cd /home/user/investor-agent

# Copy environment template
cp .env.template .env

# Edit with your credentials
nano .env
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

Save the file (Ctrl+X, then Y, then Enter).

### Step 2: Build and Start Docker Containers

```bash
# Build all images
docker-compose build investor-agent investor-agent-claude-proxy

# Start both containers in background
docker-compose up -d investor-agent investor-agent-claude-proxy

# Verify they're running
docker-compose ps
```

**Expected output:**
```
NAME                          STATUS              PORTS
investor-agent-mcp            Up 10 seconds
investor-agent-claude-proxy   Up 10 seconds       0.0.0.0:8001->8001/tcp
```

**Check logs:**
```bash
# View Claude proxy logs
docker-compose logs -f investor-agent-claude-proxy

# Expected output:
# INFO:     Starting Claude API Proxy on port 8001
# INFO:     API Key Auth: Enabled
# INFO:     Response mode: balanced, Max tokens: 2048
# INFO:     Available MCP tools: 28
# INFO:     Uvicorn running on http://0.0.0.0:8001
```

✅ **Both containers are running!**

### Step 3: Configure Claude Desktop for Docker MCP

Edit your Claude Desktop configuration:

**File locations:**
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
        "mcp",
        "run",
        "/app/investor_agent/server.py"
      ]
    }
  }
}
```

**What this does:**
- Connects Claude Desktop to the Docker container via stdio
- Uses `docker exec -i` to run commands inside the container
- The container name is `investor-agent-mcp` (from docker-compose.yml)

**Alternative: Using uvx inside Docker**

```json
{
  "mcpServers": {
    "investor-agent": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "investor-agent-mcp",
        "uvx",
        "investor-agent"
      ]
    }
  }
}
```

Save the file.

### Step 4: Restart Claude Desktop

```bash
# macOS
killall Claude
open -a Claude

# Linux
killall claude
claude &

# Windows: Close and reopen from Start Menu
```

**Verify connection:**
1. Look for 🔌 (plug) icon at the bottom of Claude Desktop
2. Click it to see "investor-agent" listed with 28 tools
3. If you see it, **Claude Desktop is connected to Docker container!** ✅

### Step 5: Test Claude Desktop (Local Docker)

In Claude Desktop app, type:

```
What are today's top 5 stock gainers?
```

**Expected behavior:**
- Claude calls the `get_market_movers` tool
- Data is fetched from inside the Docker container
- You get real stock data

**✅ If you see stock data, Claude Desktop → Docker works!**

### Step 6: Test Claude API Proxy (Mobile Access)

```bash
# Test the proxy health
curl http://localhost:8001/health

# Expected response:
# {"status":"healthy","claude_api":"connected"}
```

**Test with a chat request:**

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "message": "What is Apple stock price?",
    "response_mode": "concise"
  }'
```

**Expected response:**
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

**✅ If you get a response with cost, the proxy works!**

### Step 7: Create Pinggy Tunnel (For Mobile Access)

Open a new terminal:

```bash
# Create tunnel to Claude proxy
ssh -p 443 -R0:localhost:8001 a.pinggy.io
```

**Output:**
```
You can access local server via following URL:
https://randomstring-abc123.a.pinggy.io
```

**Copy this URL!** This is your mobile endpoint.

**Test tunnel from mobile:**

```bash
# From your phone or another terminal
curl -X POST https://randomstring-abc123.a.pinggy.io/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "message": "What are the top 3 market movers?",
    "response_mode": "balanced"
  }'
```

**✅ If you get a response, mobile access works!**

### Step 8: Use Mobile Chat Interface

1. Open `mobile_chat.html` in your mobile browser
2. Click ⚙️ Settings
3. Enter:
   - **API URL:** `https://your-pinggy-url.a.pinggy.io`
   - **API Key:** `your-api-key` (from .env MCP_API_KEY)
4. Save
5. Ask: "What are today's top gainers?"

**✅ Complete setup verified!**

---

## Docker Management

### Starting and Stopping Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d investor-agent-claude-proxy

# Stop all services
docker-compose down

# Stop specific service
docker-compose stop investor-agent-claude-proxy

# Restart a service
docker-compose restart investor-agent-claude-proxy
```

### Viewing Logs

```bash
# Follow all logs
docker-compose logs -f

# Follow specific service
docker-compose logs -f investor-agent-claude-proxy

# View last 100 lines
docker-compose logs --tail=100 investor-agent-claude-proxy

# View logs for MCP container
docker-compose logs -f investor-agent
```

### Updating Services

```bash
# Pull latest changes from git
git pull

# Rebuild images
docker-compose build

# Restart with new images
docker-compose up -d --force-recreate

# Or in one command
docker-compose up -d --build
```

### Health Checks

```bash
# Check container health
docker-compose ps

# Manual health check for proxy
curl http://localhost:8001/health

# Check what tools are available
curl http://localhost:8001/tools \
  -H "X-API-Key: your-api-key"
```

### Container Shell Access

```bash
# Access MCP container shell
docker exec -it investor-agent-mcp /bin/bash

# Access Claude proxy container shell
docker exec -it investor-agent-claude-proxy /bin/bash

# Run Python inside container
docker exec -it investor-agent-mcp python

# Test MCP server directly
docker exec -it investor-agent-mcp python -m mcp run /app/investor_agent/server.py
```

---

## Daily Workflow with Docker

### Morning Startup (2 commands)

```bash
# 1. Start Docker services
docker-compose up -d investor-agent investor-agent-claude-proxy

# 2. Create tunnel (separate terminal)
ssh -p 443 -R0:localhost:8001 a.pinggy.io
```

**Then just open Claude Desktop** - it will auto-connect to the container!

### Evening Shutdown

```bash
# Stop tunnel
# (Ctrl+C in the tunnel terminal)

# Stop Docker services
docker-compose down

# Or keep them running (they auto-restart on reboot)
```

### Auto-start on System Boot

Docker containers are configured with `restart: unless-stopped`, so they will:
- ✅ Automatically start when Docker daemon starts
- ✅ Restart if they crash
- ✅ NOT restart if you manually stop them

**To enable Docker on boot:**

```bash
# macOS/Linux
sudo systemctl enable docker

# Windows: Docker Desktop settings → "Start Docker Desktop when you log in"
```

---

## Troubleshooting

### Issue 1: Claude Desktop not connecting to Docker container

**Symptoms:** No 🔌 icon, or error in Claude Desktop

**Solutions:**

```bash
# 1. Verify container is running
docker-compose ps investor-agent

# 2. Check container logs
docker-compose logs investor-agent

# 3. Test MCP server manually
docker exec -it investor-agent-mcp python -m mcp run /app/investor_agent/server.py

# 4. Verify Claude Desktop config
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# 5. Check Docker is accessible
docker ps

# 6. Restart container
docker-compose restart investor-agent

# 7. Restart Claude Desktop
killall Claude && open -a Claude
```

### Issue 2: Claude API Proxy not starting

**Symptoms:** Container exits immediately, or port 8001 not accessible

**Solutions:**

```bash
# Check container status
docker-compose ps investor-agent-claude-proxy

# View logs for errors
docker-compose logs investor-agent-claude-proxy

# Common issues:

# A. Missing ANTHROPIC_API_KEY
grep ANTHROPIC_API_KEY .env

# B. Port 8001 already in use on host
lsof -i :8001
# Kill the process or change port in docker-compose.yml

# C. Rebuild image
docker-compose build investor-agent-claude-proxy
docker-compose up -d investor-agent-claude-proxy
```

### Issue 3: Mobile can't connect via Pinggy

**Symptoms:** Timeout or connection refused from mobile

**Solutions:**

```bash
# 1. Verify proxy is running
docker-compose ps investor-agent-claude-proxy

# 2. Test locally first
curl http://localhost:8001/health

# 3. Check Pinggy tunnel is active
# Look for https:// URL in tunnel terminal

# 4. Test tunnel endpoint
curl https://your-url.a.pinggy.io/health

# 5. Verify API key if using one
curl -H "X-API-Key: your-key" https://your-url.a.pinggy.io/health

# 6. Check Docker logs
docker-compose logs -f investor-agent-claude-proxy
```

### Issue 4: "Permission denied" when Claude Desktop connects

**Symptoms:** Claude Desktop shows connection error

**Solution:**

```bash
# Ensure Docker container is running with stdin_open and tty
# (Already configured in docker-compose.yml)

# Verify container configuration
docker inspect investor-agent-mcp | grep -A5 "OpenStdin\|Tty"

# Should show:
# "OpenStdin": true,
# "Tty": true,
```

### Issue 5: Container crashes or exits

**Symptoms:** Container not in `docker-compose ps` output

**Solutions:**

```bash
# View crash logs
docker-compose logs --tail=50 investor-agent-claude-proxy

# Common causes:
# A. Missing environment variables
docker-compose config

# B. Port conflict
docker-compose down
docker-compose up -d

# C. Image needs rebuild
docker-compose build
docker-compose up -d

# D. Check .env file exists
ls -la .env
```

---

## Cost Tracking with Docker

### View Response Modes

```bash
# Check current response mode
docker exec investor-agent-claude-proxy printenv CLAUDE_RESPONSE_MODE

# Change response mode (edit .env, then restart)
nano .env  # Change CLAUDE_RESPONSE_MODE
docker-compose restart investor-agent-claude-proxy
```

### Monitor Costs

Every response includes cost information:

```json
{
  "usage": {
    "input_tokens": 245,
    "output_tokens": 87
  },
  "estimated_cost": 0.0021,
  "response_mode": "concise"
}
```

**Track daily costs:**
- Response costs are returned in each API call
- Use mobile_chat.html to see costs in real-time
- See COST_MANAGEMENT.md for optimization strategies

---

## Development Mode

### Enable Code Hot-Reload

Edit `docker-compose.yml` and uncomment the volumes:

```yaml
  investor-agent-claude-proxy:
    # ... other config ...
    volumes:
      - ./investor_agent:/app/investor_agent
      - ./claude_proxy_service.py:/app/claude_proxy_service.py
```

Then restart:

```bash
docker-compose up -d investor-agent-claude-proxy
```

**Now code changes are reflected immediately!** (You may need to restart the container for some changes)

### Run Tests Inside Container

```bash
# Run tests
docker exec -it investor-agent-mcp pytest

# Run specific test
docker exec -it investor-agent-mcp pytest tests/test_server.py

# Interactive Python for debugging
docker exec -it investor-agent-claude-proxy python
>>> from investor_agent import server
>>> # Test code here
```

---

## Production Deployment

### Using Docker on a VPS

1. **Deploy to server:**
```bash
# Copy project to server
scp -r /home/user/investor-agent user@your-server.com:~/

# SSH into server
ssh user@your-server.com

# Start services
cd ~/investor-agent
docker-compose up -d
```

2. **Use persistent Pinggy subdomain:**
```bash
# Get token from https://pinggy.io
ssh -p 443 -R0:localhost:8001 -t <your-token>@a.pinggy.io
```

3. **Set up reverse proxy (optional):**
   - Use Nginx/Caddy for HTTPS
   - No need for Pinggy if server has public IP

### Environment-Specific Configs

```bash
# Development
cp .env.template .env.dev
# Edit .env.dev with dev settings
docker-compose --env-file .env.dev up -d

# Production
cp .env.template .env.prod
# Edit .env.prod with prod settings
docker-compose --env-file .env.prod up -d
```

---

## Comparison: Docker vs Non-Docker

| Feature | Docker Setup | Non-Docker Setup |
|---------|-------------|------------------|
| **Installation** | `docker-compose up` | `pip install`, manual deps |
| **Updates** | `docker-compose pull` | `git pull && pip install` |
| **Isolation** | ✅ Containerized | ❌ Uses system Python |
| **Consistency** | ✅ Same everywhere | ⚠️ Depends on system |
| **Auto-restart** | ✅ Built-in | ❌ Need systemd/launchd |
| **Health checks** | ✅ Built-in | ❌ Manual |
| **Cleanup** | `docker-compose down` | Manual process cleanup |
| **Deployment** | Copy & run | Install deps on server |

**Use Docker if:**
- ✅ You want easy deployment
- ✅ You need isolation from system
- ✅ You want auto-restarts and health checks
- ✅ You plan to deploy to a server

**Use Non-Docker if:**
- ✅ You're just testing locally
- ✅ You don't have Docker installed
- ✅ You want faster iteration (no rebuild)

---

## Quick Reference

### Essential Commands

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Restart a service
docker-compose restart investor-agent-claude-proxy

# Rebuild after code changes
docker-compose up -d --build

# Check health
curl http://localhost:8001/health

# Create Pinggy tunnel
ssh -p 443 -R0:localhost:8001 a.pinggy.io
```

### Component Status Check

| Component | Check Command | Expected Result |
|-----------|--------------|-----------------|
| **MCP Container** | `docker-compose ps investor-agent` | Up |
| **Claude Proxy** | `curl localhost:8001/health` | `{"status":"healthy"}` |
| **Claude Desktop** | Look for 🔌 icon | Shows "investor-agent" |
| **Pinggy Tunnel** | Check terminal output | Shows https:// URL |

### File Locations

```
/home/user/investor-agent/
├── docker-compose.yml          # Orchestration
├── Dockerfile                  # MCP container
├── Dockerfile.claude-proxy     # Claude proxy container
├── .env                        # Your secrets
├── claude_proxy_service.py     # Proxy service code
├── mobile_chat.html           # Mobile interface
└── investor_agent/            # MCP server code
```

---

## Summary

✅ **What you get with Docker:**
1. Claude Desktop with MCP tools (via Docker container)
2. Mobile access with Claude intelligence (containerized)
3. Auto-restarts and health checks
4. Easy updates with `docker-compose pull`
5. Consistent environment everywhere
6. Simple deployment to servers

🎯 **Use cases:**
- **Desktop:** Deep research, extended conversations (FREE)
- **Mobile:** Quick checks, on-the-go queries (~$0.002-0.006 per query)

💰 **Costs:**
- Desktop: $0 (unlimited)
- Mobile: ~$2-5/month (typical usage)

🚀 **You're all set!** Both modes are running in Docker containers.

---

## Next Steps

1. ✅ Start using Claude Desktop (connects to Docker MCP container)
2. ✅ Test mobile chat interface via Pinggy tunnel
3. ✅ Monitor costs in proxy responses
4. ✅ Adjust `CLAUDE_RESPONSE_MODE` in .env based on needs
5. ✅ Set up auto-start if desired

**Enjoy your Docker-managed dual-mode investor agent!** 📈💼🐳
