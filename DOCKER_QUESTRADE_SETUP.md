# Questrade Integration - Docker Setup Guide

## 🐳 For Docker Users

Since you're running `investor-agent` as a Docker container, the setup is different from the standard installation.

---

## ✅ What I Fixed

1. **Updated Dockerfile** - Added `questrade-api>=1.0.0` to the dependencies
2. **Created .env file** - Copied from .env.template

---

## 🔧 Setup Steps

### Step 1: Add Your Questrade Token to .env

Edit the `.env` file in the project root:

```bash
# Open the .env file
nano .env   # or use your preferred editor
```

Find this line:
```bash
QUESTRADE_REFRESH_TOKEN=your_questrade_refresh_token_here
```

Replace `your_questrade_refresh_token_here` with your actual Questrade refresh token:
```bash
QUESTRADE_REFRESH_TOKEN=YourActualTokenFromQuestrade123456
```

**How to get your token:**
1. Visit: https://www.questrade.com/api/
2. Log in to your Questrade account
3. Generate a "Manual Refresh Token"
4. Copy the token and paste it in the .env file

### Step 2: Rebuild the Docker Container

Since we updated the Dockerfile to include questrade-api, you need to rebuild the container:

```bash
# Stop the existing container
docker-compose down

# Rebuild with the new dependencies
docker-compose build --no-cache

# Start the container
docker-compose up -d
```

**Why rebuild?**
- The Dockerfile now includes `questrade-api>=1.0.0`
- Docker needs to rebuild the image to install this package
- The `--no-cache` flag ensures a clean rebuild

### Step 3: Verify Installation

Check that questrade-api is installed in the container:

```bash
docker exec -it investor-agent-mcp python -c "import questrade_api; print('✅ questrade-api installed')"
```

Expected output:
```
✅ questrade-api installed
```

### Step 4: Check Environment Variable

Verify the token is loaded in the container:

```bash
docker exec -it investor-agent-mcp python -c "import os; print('✅ Token is set' if os.getenv('QUESTRADE_REFRESH_TOKEN') else '❌ Token NOT set')"
```

Expected output:
```
✅ Token is set
```

### Step 5: Test the Questrade Tools

Check that the tools are available:

```bash
docker exec -it investor-agent-mcp python -c "
from investor_agent.server import mcp
tools = list(mcp._tool_manager._tools.keys())
questrade_tools = [t for t in tools if 'questrade' in t.lower()]
print(f'Questrade tools: {questrade_tools}')
"
```

Expected output:
```
Questrade tools: ['get_questrade_accounts', 'get_questrade_positions', 'get_questrade_balances']
```

### Step 6: Restart Your MCP Client

- **Claude Desktop:** Quit and reopen
- The server will reconnect to the container automatically

---

## 📋 Your Current MCP Configuration

Your Claude Desktop config is correct for Docker:

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
        "investor_agent.server"
      ]
    }
  }
}
```

**No changes needed to MCP config!** The token is passed via the `.env` file that docker-compose loads.

---

## 🧪 Testing the Integration

Once everything is set up, test in Claude Desktop:

1. Open Claude Desktop
2. Ask: "List my Questrade accounts"
3. The AI should use the `get_questrade_accounts` tool
4. You should see your account information

---

## 🐛 Troubleshooting

### Issue: Still seeing "questrade-api package not available"

**Solution:** Make sure you rebuilt the Docker container:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Issue: "Refresh token required" error

**Check:**
1. .env file exists in project root
2. .env file has QUESTRADE_REFRESH_TOKEN=your_token
3. No quotes around the token (unless required by docker-compose)
4. Container was restarted after adding the token

**Verify token in container:**
```bash
docker exec -it investor-agent-mcp printenv | grep QUESTRADE
```

### Issue: Container won't start

**Check logs:**
```bash
docker-compose logs investor-agent
```

**Common issues:**
- Syntax error in .env file
- Port conflicts
- Build errors (check Dockerfile syntax)

### Issue: Token in .env but not in container

**Solution:** docker-compose needs to be restarted to pick up .env changes:
```bash
docker-compose down
docker-compose up -d
```

---

## 🔄 Updating the Code

If you pull new changes from git:

```bash
# Pull latest changes
git pull

# Rebuild container with new code
docker-compose build

# Restart container
docker-compose down
docker-compose up -d
```

---

## 🔐 Security Notes

**⚠️ Important:**
- Keep your .env file secure
- .env is in .gitignore - don't commit it!
- Rotate your Questrade token regularly
- Never share your .env file or logs containing the token

---

## 📊 Docker Container Structure

```
investor-agent-mcp container:
├── Python 3.12
├── Dependencies:
│   ├── yfinance, pandas, numpy, scipy
│   ├── mcp, httpx, tenacity
│   ├── questrade-api ← newly added
│   └── ... other packages
├── Code:
│   └── /app/investor_agent/
└── Environment Variables:
    ├── QUESTRADE_REFRESH_TOKEN (from .env)
    ├── ALPACA_API_KEY (from .env)
    └── ... other variables
```

---

## ✅ Verification Checklist

- [ ] Updated Dockerfile (already done ✓)
- [ ] Created .env file from template
- [ ] Added QUESTRADE_REFRESH_TOKEN to .env
- [ ] Ran `docker-compose build --no-cache`
- [ ] Ran `docker-compose up -d`
- [ ] Verified questrade-api is installed in container
- [ ] Verified token is set in container
- [ ] Verified 3 Questrade tools are available
- [ ] Restarted Claude Desktop
- [ ] Tested with "List my Questrade accounts"

---

## 🚀 Quick Commands Reference

```bash
# Rebuild and restart container
docker-compose down && docker-compose build --no-cache && docker-compose up -d

# Check if questrade-api is installed
docker exec -it investor-agent-mcp pip list | grep questrade

# Check environment variables
docker exec -it investor-agent-mcp printenv | grep QUESTRADE

# View container logs
docker-compose logs -f investor-agent

# Access container shell
docker exec -it investor-agent-mcp bash

# Test Python imports
docker exec -it investor-agent-mcp python -c "from investor_agent.questrade import get_questrade_client; print('OK')"
```

---

## 📚 Additional Resources

- Docker Compose docs: https://docs.docker.com/compose/
- Questrade API: https://www.questrade.com/api/
- See `QUESTRADE_SETUP.md` for general Questrade setup
- See `check_questrade_env.py` for environment verification (run inside container)

---

**Need help?** Check the container logs first: `docker-compose logs investor-agent`
