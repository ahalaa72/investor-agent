# Quick Start - Investor Agent + n8n

Get up and running in 5 minutes! 🚀

## Prerequisites

- Docker & Docker Compose installed
- API keys ready:
  - Alpaca Markets: https://alpaca.markets/
  - OpenAI OR Anthropic

## Installation (3 Steps)

### 1. Setup Environment

```bash
# Copy template
cp .env.template .env

# Edit and add your API keys
nano .env
```

Add your keys:
```env
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
OPENAI_API_KEY=your_openai_key
N8N_BASIC_AUTH_PASSWORD=ChangeMe123!
```

### 2. Start Services

```bash
docker-compose -f docker-compose.n8n.yml up -d
```

### 3. Verify

```bash
# Check status
docker-compose -f docker-compose.n8n.yml ps

# Test bridge
curl http://localhost:8000/health
```

## Access

- **n8n**: http://localhost:5678 (login: admin / your_password)
- **Bridge API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Quick Test

```bash
# List all tools
curl http://localhost:8000/tools | jq '.count'

# Get market movers
curl -X POST http://localhost:8000/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_market_movers",
    "arguments": {"category": "gainers", "count": 5}
  }' | jq '.result' -r
```

## Common Commands

```bash
# View logs
docker-compose -f docker-compose.n8n.yml logs -f

# Restart services
docker-compose -f docker-compose.n8n.yml restart

# Stop services
docker-compose -f docker-compose.n8n.yml down

# Update and rebuild
docker-compose -f docker-compose.n8n.yml down
docker-compose -f docker-compose.n8n.yml build --no-cache
docker-compose -f docker-compose.n8n.yml up -d
```

## Example Tools

| Tool | Description | Example Arguments |
|------|-------------|-------------------|
| `get_market_movers` | Top gainers/losers | `{"category": "gainers", "count": 10}` |
| `get_ticker_data` | Stock info + news | `{"ticker": "AAPL", "max_news": 5}` |
| `get_price_history` | Historical prices | `{"ticker": "TSLA", "period": "1mo"}` |
| `get_cnn_fear_greed_index` | Market sentiment | `{}` |
| `fetch_intraday_15m` | 15-min bars | `{"stock": "AAPL", "window": 100}` |

See all 25+ tools: `curl http://localhost:8000/tools`

## Create Your First Workflow

1. Open n8n: http://localhost:5678
2. Import: `n8n/workflows/investor-agent-example.json`
3. Activate workflow
4. Test webhook:

```bash
curl -X POST http://localhost:5678/webhook/market-query \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the top gainers?"}'
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Port already in use | `docker-compose -f docker-compose.n8n.yml down` |
| Can't connect to bridge | Check logs: `docker-compose -f docker-compose.n8n.yml logs investor-agent-bridge` |
| Tool returns error | Verify API keys in `.env` |
| n8n can't reach bridge | Use URL: `http://investor-agent-bridge:8000` (not localhost) |

## Full Documentation

- [Complete Setup Guide](N8N_SETUP_GUIDE.md)
- [Bridge Documentation](BRIDGE_README.md)
- [Main README](README.md)

---

**Questions?** Open an issue on GitHub
