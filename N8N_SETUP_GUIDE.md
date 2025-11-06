# n8n Setup Guide for Investor Agent

Complete step-by-step guide to integrate Investor Agent MCP server with n8n workflows.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Starting the Services](#starting-the-services)
5. [Creating Your First Workflow](#creating-your-first-workflow)
6. [Advanced Usage](#advanced-usage)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required

- **Docker** (v20.10+) and **Docker Compose** (v2.0+)
- **Git** (to clone the repository)
- **API Keys**:
  - [Alpaca Markets API](https://alpaca.markets/) - For intraday stock data
  - [OpenAI API](https://platform.openai.com/) OR [Anthropic API](https://console.anthropic.com/) - For AI agent

### Optional

- **TA-Lib** - For technical indicators (optional)
- **Postman** or **cURL** - For testing the bridge API

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/investor-agent.git
cd investor-agent
```

### Step 2: Create Environment File

```bash
# Copy the template
cp .env.template .env

# Edit with your favorite editor
nano .env  # or vim, code, etc.
```

### Step 3: Add Your API Keys

Edit `.env` and add your credentials:

```env
# Alpaca API (Required for intraday data)
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_API_SECRET=your_alpaca_api_secret_here

# LLM API Key (Required - choose one or both)
OPENAI_API_KEY=sk-your-openai-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# n8n Authentication (Change these!)
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=YourSecurePassword123!

# Optional: Timezone
TIMEZONE=America/New_York
```

**Important**:
- Never commit the `.env` file to git
- Use strong passwords for n8n authentication
- Keep your API keys secure

---

## Configuration

### Environment Variables Explained

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ALPACA_API_KEY` | Yes* | Alpaca API key | `PK...` |
| `ALPACA_API_SECRET` | Yes* | Alpaca API secret | `...` |
| `OPENAI_API_KEY` | Yes** | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Yes** | Anthropic API key | `sk-ant-...` |
| `N8N_BASIC_AUTH_USER` | No | n8n login username | `admin` |
| `N8N_BASIC_AUTH_PASSWORD` | No | n8n login password | `secure123` |
| `TIMEZONE` | No | Your timezone | `America/New_York` |

\* Required only for `fetch_intraday_15m` and `fetch_intraday_1h` tools
\** At least one LLM API key is required for AI agent functionality

---

## Starting the Services

### Quick Start

```bash
# Build and start all services
docker-compose -f docker-compose.n8n.yml up -d

# Verify services are running
docker-compose -f docker-compose.n8n.yml ps

# Expected output:
# NAME                    STATUS              PORTS
# investor-agent-bridge   Up (healthy)        0.0.0.0:8000->8000/tcp
# n8n                     Up                  0.0.0.0:5678->5678/tcp
```

### Check Logs

```bash
# View all logs
docker-compose -f docker-compose.n8n.yml logs -f

# View bridge logs only
docker-compose -f docker-compose.n8n.yml logs -f investor-agent-bridge

# View n8n logs only
docker-compose -f docker-compose.n8n.yml logs -f n8n
```

### Access the Services

1. **n8n UI**: http://localhost:5678
   - Username: (from `N8N_BASIC_AUTH_USER`)
   - Password: (from `N8N_BASIC_AUTH_PASSWORD`)

2. **Bridge API**: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

---

## Creating Your First Workflow

### Method 1: Import Example Workflow

1. Open n8n at http://localhost:5678
2. Click **"Workflows"** → **"Import from File"**
3. Select `n8n/workflows/investor-agent-example.json`
4. Click **"Activate"** to enable the workflow

### Method 2: Build from Scratch

#### Step 1: Create New Workflow

1. In n8n, click **"New Workflow"**
2. Give it a name: "Market Analysis Agent"

#### Step 2: Add Webhook Trigger

1. Click **"+"** → Search for **"Webhook"**
2. Set:
   - **HTTP Method**: POST
   - **Path**: `market-query`
   - **Response Mode**: "Using 'Respond to Webhook' Node"

#### Step 3: Add HTTP Request to List Tools

1. Add **"HTTP Request"** node
2. Set:
   - **Method**: GET
   - **URL**: `http://investor-agent-bridge:8000/tools`

#### Step 4: Add AI Agent Node

**For OpenAI (GPT-4):**

1. Add **"OpenAI"** node
2. Set:
   - **Resource**: "Chat"
   - **Operation**: "Message"
   - **Model**: "gpt-4" or "gpt-4-turbo"
   - **Messages**:
     ```
     You are a financial analyst with access to market data tools.
     User query: {{ $json.body.message }}

     Available tools: {{ $('HTTP Request').item.json.tools }}

     Based on the user's question, decide which tool to call and with what parameters.
     ```

**For Anthropic (Claude):**

1. Add **"Anthropic"** node (via HTTP Request)
2. Set:
   - **Method**: POST
   - **URL**: `https://api.anthropic.com/v1/messages`
   - **Headers**:
     - `x-api-key`: `{{ $env.ANTHROPIC_API_KEY }}`
     - `anthropic-version`: `2023-06-01`
     - `Content-Type`: `application/json`

#### Step 5: Add Tool Execution

1. Add **"HTTP Request"** node (for calling tools)
2. Set:
   - **Method**: POST
   - **URL**: `http://investor-agent-bridge:8000/call`
   - **Body**:
     ```json
     {
       "tool_name": "{{ $json.tool_name }}",
       "arguments": {{ $json.arguments }}
     }
     ```

#### Step 6: Add Response Formatting

1. Add **"Respond to Webhook"** node
2. Set:
   - **Response Body**:
     ```json
     {
       "success": {{ $json.success }},
       "data": {{ $json.result }},
       "tool_used": "{{ $json.tool_name }}"
     }
     ```

#### Step 7: Test Your Workflow

1. Click **"Test workflow"**
2. Use the webhook URL to send a test request:

```bash
curl -X POST http://localhost:5678/webhook/market-query \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the top gainers today?"}'
```

---

## Advanced Usage

### Using Multiple Tools in Sequence

Create a workflow that:

1. Gets market movers
2. For top 3 stocks, get detailed ticker data
3. Check insider trades
4. Use AI to synthesize a report

Example workflow structure:

```
Webhook → Get Movers → Loop (top 3) → Get Ticker Data → Get Insider Trades → AI Summary → Response
```

### Scheduling Workflows

1. Replace **Webhook** trigger with **Schedule** trigger
2. Set cron expression:
   - Daily at market open: `0 30 9 * * 1-5` (9:30 AM, weekdays)
   - Every hour during market: `0 * 9-16 * * 1-5`

### Sending to Slack/Discord

1. Add **Slack** or **Discord** node at the end
2. Configure webhook URL
3. Format the message with AI-generated summary

---

## Testing the Bridge API

### Using cURL

```bash
# List all tools
curl http://localhost:8000/tools | jq

# Get specific tool info
curl http://localhost:8000/tools/get_market_movers | jq

# Call a tool
curl -X POST http://localhost:8000/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_market_movers",
    "arguments": {
      "category": "gainers",
      "count": 10
    }
  }' | jq
```

### Using the Test Script

```bash
# Run all tests
python test_bridge.py

# Test specific tool
python test_bridge.py --tool get_ticker_data

# Test different URL
python test_bridge.py --url http://your-server:8000
```

---

## Troubleshooting

### Services Won't Start

**Problem**: Docker containers fail to start

**Solutions**:

```bash
# Check if ports are already in use
lsof -i :8000  # Bridge port
lsof -i :5678  # n8n port

# Check Docker logs
docker-compose -f docker-compose.n8n.yml logs

# Rebuild containers
docker-compose -f docker-compose.n8n.yml down
docker-compose -f docker-compose.n8n.yml build --no-cache
docker-compose -f docker-compose.n8n.yml up -d
```

### Bridge Returns Errors

**Problem**: Tools return error messages

**Common Issues**:

1. **Missing Alpaca Keys**:
   - Error: "ALPACA_API_KEY and ALPACA_API_SECRET environment variables must be set"
   - Solution: Add keys to `.env` file and restart

2. **Rate Limiting**:
   - Error: "Rate limit exceeded"
   - Solution: Wait a few minutes, the bridge has automatic retry logic

3. **Invalid Ticker**:
   - Error: "No information available for XYZ"
   - Solution: Verify ticker symbol is correct

### n8n Can't Connect to Bridge

**Problem**: n8n workflows get connection errors

**Solutions**:

```bash
# Test from inside n8n container
docker exec -it n8n curl http://investor-agent-bridge:8000/health

# If that fails, check network
docker network ls
docker network inspect investor-agent-network

# Restart services
docker-compose -f docker-compose.n8n.yml restart
```

### Tools Not Showing in n8n

**Problem**: AI agent doesn't see available tools

**Solutions**:

1. Verify bridge is accessible:
   ```bash
   curl http://localhost:8000/tools
   ```

2. Check tool schema format matches your AI provider's requirements

3. In n8n workflow, add a debug node to inspect the tools response

---

## Example Use Cases

### 1. Daily Market Report

**Trigger**: Schedule (daily at 9:35 AM)
**Steps**:
1. Get market movers (gainers, losers)
2. Get fear & greed index
3. AI generates summary
4. Send to Slack

### 2. Stock Alert System

**Trigger**: Schedule (every 15 minutes during market hours)
**Steps**:
1. Get ticker data for watchlist
2. Check for insider trades
3. Check for news
4. If significant event, send alert

### 3. Research Assistant

**Trigger**: Webhook
**Steps**:
1. User asks question via API
2. AI agent analyzes question
3. Calls appropriate tools (ticker data, financials, etc.)
4. Synthesizes comprehensive response
5. Returns formatted report

---

## Next Steps

- Explore all [25+ available tools](BRIDGE_README.md#available-tools)
- Build custom workflows for your use cases
- Set up monitoring and alerts
- Deploy to production with HTTPS

---

## Resources

- [n8n Documentation](https://docs.n8n.io/)
- [Bridge API Documentation](http://localhost:8000/docs)
- [Investor Agent README](README.md)
- [MCP Protocol](https://modelcontextprotocol.io/)

---

**Need Help?** Open an issue on GitHub or check the troubleshooting section above.

**Happy Trading! 📈**
