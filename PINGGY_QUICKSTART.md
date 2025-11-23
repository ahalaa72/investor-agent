# Pinggy Quick Start Guide

## 🚀 Quick Setup (3 Steps)

### Step 1: Configure Environment
```bash
cp .env.template .env
```

Edit `.env` and set at minimum:
```bash
MCP_API_KEY=your-secure-random-key-here
```

### Step 2: Install Dependencies
```bash
pip install -e ".[bridge]"
```

### Step 3: Start Server
```bash
./start_pinggy.sh
```

Or manually:
```bash
# Terminal 1: Start server
python -m investor_agent.pinggy_wrapper

# Terminal 2: Create tunnel
ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

## 📡 Your Public URL

After starting the tunnel, you'll see output like:
```
https://randomstring.a.pinggy.io
```

Copy this URL - this is your public endpoint!

## 🧪 Test Your Setup

```bash
# Test health check (no auth required)
curl https://your-url.a.pinggy.io/health

# List all tools (auth required)
curl -H "X-API-Key: your-api-key" \
     https://your-url.a.pinggy.io/tools

# Call a tool
curl -X POST "https://your-url.a.pinggy.io/call" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "tool_name": "get_market_movers",
    "arguments": {"category": "gainers", "count": 5}
  }'
```

## 📚 Interactive API Docs

Visit: `https://your-url.a.pinggy.io/docs`

This provides a Swagger UI where you can:
- Browse all available tools
- Test endpoints interactively
- See request/response schemas
- Authenticate with your API key

## 🔐 Security Checklist

- ✅ Set strong `MCP_API_KEY` (32+ characters)
- ✅ Configure rate limits in `.env`
- ✅ Use HTTPS (automatic with Pinggy)
- ✅ Monitor logs for suspicious activity
- ✅ Never commit `.env` to git

## 🔧 Configuration Options

In your `.env` file:

```bash
# Required
MCP_API_KEY=your-secure-api-key

# Optional
PINGGY_PORT=8000                # Server port
RATE_LIMIT_CALLS=100           # Max calls per window
RATE_LIMIT_WINDOW=3600         # Window in seconds

# API Keys for MCP tools
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
QUESTRADE_REFRESH_TOKEN=...
```

## 📖 Common Use Cases

### Use Case 1: Remote Python Client

```python
import requests

API_URL = "https://your-url.a.pinggy.io"
API_KEY = "your-api-key"

response = requests.post(
    f"{API_URL}/call",
    headers={"X-API-Key": API_KEY},
    json={
        "tool_name": "get_ticker_data",
        "arguments": {"ticker": "AAPL"}
    }
)

print(response.json()["result"])
```

### Use Case 2: n8n Workflow

1. Add HTTP Request node
2. Set URL: `https://your-url.a.pinggy.io/call`
3. Method: POST
4. Headers: `X-API-Key: your-api-key`
5. Body:
```json
{
  "tool_name": "get_market_movers",
  "arguments": {"category": "gainers"}
}
```

### Use Case 3: Webhook Integration

Use your Pinggy URL as a webhook endpoint in any service that supports HTTP POST requests.

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Check `X-API-Key` header matches `.env` |
| 429 Rate Limit | Wait for window reset or increase limits |
| 500 Server Error | Check server logs for missing env vars |
| Tunnel disconnected | Restart `ssh` command or use Pinggy CLI |

## 📊 Monitoring

Check rate limit status:
```bash
curl -H "X-API-Key: your-api-key" \
     https://your-url.a.pinggy.io/rate-limit
```

Response:
```json
{
  "limit": 100,
  "remaining": 85,
  "reset_time": "2024-01-15T15:30:00"
}
```

## 🔗 Resources

- **Full Documentation**: [PINGGY_SETUP.md](PINGGY_SETUP.md)
- **Pinggy Docs**: https://pinggy.io/docs
- **API Reference**: https://your-url.a.pinggy.io/docs
- **MCP Server Code**: [investor_agent/server.py](investor_agent/server.py)

## 💡 Pro Tips

1. **Custom Subdomain** (paid): `ssh -p 443 -R0:localhost:8000 -t a.pinggy.io your-subdomain`
2. **Production Setup**: Use systemd for auto-restart (see PINGGY_SETUP.md)
3. **Multiple Instances**: Use Redis for rate limiting across instances
4. **Logging**: Tail logs with `journalctl -u investor-agent-pinggy -f`

## ⚡ Need Help?

1. Check [PINGGY_SETUP.md](PINGGY_SETUP.md) for detailed instructions
2. Visit `/docs` on your running server for API documentation
3. Review logs for error details

---

**Ready to go?** Run `./start_pinggy.sh` and start building! 🎉
