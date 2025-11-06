# Investor Agent MCP-HTTP Bridge

This bridge exposes the Investor Agent MCP server as a REST API, enabling integration with n8n workflows and other HTTP-based systems.

## 🎯 Overview

The MCP-HTTP Bridge converts the Model Context Protocol (MCP) server into HTTP REST API endpoints, allowing you to:

- Use investor-agent tools from n8n workflows
- Build AI agents that call financial data tools via HTTP
- Integrate with any HTTP client or workflow automation platform

## 🏗️ Architecture

```
User Request → n8n Webhook → AI Agent (Claude/GPT-4) → HTTP Bridge → MCP Server
                                         ↓
                                   Market Data APIs
                                         ↓
                                   Response → User
```

## 🚀 Quick Start

### 1. Prerequisites

- Docker and Docker Compose installed
- API keys for:
  - Alpaca Markets (for intraday data)
  - OpenAI or Anthropic (for AI agent)

### 2. Configuration

Copy the environment template and fill in your credentials:

```bash
cp .env.template .env
```

Edit `.env` and add your API keys:

```env
# Required for intraday data tools
ALPACA_API_KEY=your_alpaca_key
ALPACA_API_SECRET=your_alpaca_secret

# Required for n8n AI Agent (choose one)
OPENAI_API_KEY=your_openai_key
# OR
ANTHROPIC_API_KEY=your_anthropic_key

# n8n authentication (change defaults)
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=your_secure_password
```

### 3. Start the Services

```bash
# Start both bridge and n8n
docker-compose -f docker-compose.n8n.yml up -d

# Check status
docker-compose -f docker-compose.n8n.yml ps

# View logs
docker-compose -f docker-compose.n8n.yml logs -f
```

### 4. Access the Services

- **n8n UI**: http://localhost:5678
- **Bridge API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)

## 📡 API Endpoints

### List All Tools

```bash
GET /tools
```

Returns all available MCP tools with their schemas.

**Example Response:**
```json
{
  "tools": [
    {
      "name": "get_market_movers",
      "description": "Get market movers. market_session only applies to 'most-active'.",
      "parameters": {
        "type": "object",
        "properties": {
          "category": {
            "type": "string",
            "enum": ["gainers", "losers", "most-active"],
            "default": "most-active"
          },
          "count": {
            "type": "integer",
            "default": 25
          }
        }
      },
      "is_async": true
    }
  ],
  "count": 25
}
```

### Get Tool Information

```bash
GET /tools/{tool_name}
```

Get detailed information about a specific tool.

### Call a Tool

```bash
POST /call
Content-Type: application/json

{
  "tool_name": "get_market_movers",
  "arguments": {
    "category": "gainers",
    "count": 10
  }
}
```

**Example Response:**
```json
{
  "success": true,
  "tool_name": "get_market_movers",
  "result": "Symbol,Name,Price,Change,% Change\nAAPL,Apple Inc.,175.50,+5.25,+3.08%\n..."
}
```

### Health Check

```bash
GET /health
```

## 🔧 Development Setup

### Run Bridge Locally (Without Docker)

```bash
# Install dependencies
uv pip install -e ".[bridge]"

# Set environment variables
export ALPACA_API_KEY=your_key
export ALPACA_API_SECRET=your_secret

# Run the bridge
python -m uvicorn investor_agent.bridge:app --reload --port 8000
```

### Test the API

```bash
# List all tools
curl http://localhost:8000/tools

# Call a tool
curl -X POST http://localhost:8000/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_ticker_data",
    "arguments": {
      "ticker": "AAPL",
      "max_news": 3
    }
  }'

# Get specific tool info
curl http://localhost:8000/tools/get_market_movers
```

## 🎨 n8n Integration

### Option 1: Using HTTP Request Node

1. Add **HTTP Request** node
2. Set method to `POST`
3. Set URL to `http://investor-agent-bridge:8000/call`
4. Add JSON body with tool name and arguments

### Option 2: Using AI Agent Node (Recommended)

1. Add **AI Agent** node (OpenAI or Anthropic)
2. Configure with your LLM API key
3. Add **HTTP Request** tool nodes
4. Point to bridge endpoints
5. Configure tool schemas from `/tools` endpoint

See the n8n workflow examples in the `n8n/workflows/` directory.

## 🛠️ Available Tools

The bridge exposes 25+ tools across these categories:

### Market Data
- `get_market_movers` - Top gainers, losers, most active
- `get_ticker_data` - Comprehensive stock data with news
- `get_price_history` - Historical OHLCV data
- `get_options` - Options chains
- `get_financial_statements` - Income, balance, cash flow

### Intraday Data (Alpaca)
- `fetch_intraday_15m` - 15-minute bars
- `fetch_intraday_1h` - 1-hour bars

### Market Sentiment
- `get_cnn_fear_greed_index` - CNN Fear & Greed Index
- `get_crypto_fear_greed_index` - Crypto sentiment
- `get_google_trends` - Search trends

### Analysis
- `get_earnings_history` - Historical earnings
- `get_insider_trades` - Insider trading activity
- `get_institutional_holders` - Major holders

For complete tool documentation, see the main [README.md](README.md).

## 🔒 Security Considerations

1. **API Keys**: Never commit `.env` files to version control
2. **n8n Authentication**: Change default credentials in production
3. **Network**: Use HTTPS in production with reverse proxy
4. **Rate Limiting**: Consider adding rate limiting for production use
5. **CORS**: Configure CORS appropriately for your use case

## 🐛 Troubleshooting

### Bridge won't start

```bash
# Check logs
docker-compose -f docker-compose.n8n.yml logs investor-agent-bridge

# Common issues:
# - Missing environment variables
# - Port 8000 already in use
# - Invalid API keys
```

### Tools returning errors

```bash
# Test individual tools
curl -X POST http://localhost:8000/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "get_market_movers", "arguments": {}}'

# Check if Alpaca keys are set for intraday tools
echo $ALPACA_API_KEY
```

### n8n can't connect to bridge

```bash
# From inside n8n container, test connectivity
docker exec -it n8n ping investor-agent-bridge

# Use internal Docker network URL
http://investor-agent-bridge:8000
```

## 📚 Example Use Cases

### 1. Daily Market Summary Bot

Create a workflow that:
1. Triggers daily at market open
2. Calls `get_market_movers` for gainers
3. Calls `get_cnn_fear_greed_index`
4. Uses AI to generate summary
5. Sends to Slack/Discord

### 2. Stock Alert System

Create a workflow that:
1. Monitors specific tickers with `get_ticker_data`
2. Checks for insider trades with `get_insider_trades`
3. Analyzes with AI agent
4. Sends alerts on significant events

### 3. Research Assistant

Create an AI agent that:
1. Accepts natural language queries
2. Uses multiple tools to gather data
3. Synthesizes comprehensive reports
4. Returns formatted analysis

## 🔗 Resources

- [n8n Documentation](https://docs.n8n.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [OpenAPI/Swagger UI](http://localhost:8000/docs)

## 📝 License

MIT License - See [LICENSE](LICENSE) for details

## 🤝 Contributing

Contributions welcome! Please open issues or pull requests.

---

**Questions?** Open an issue or check the main [README.md](README.md) for more information.
