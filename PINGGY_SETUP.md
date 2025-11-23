# Pinggy Tunnel Setup for Investor Agent MCP

This guide explains how to expose your Investor Agent MCP server to the internet using Pinggy tunnels, allowing remote access from anywhere.

## Overview

The `pinggy_wrapper.py` provides a secure FastAPI wrapper around the MCP server with the following features:

- ✅ **API Key Authentication** - Secure your endpoints with custom API keys
- ✅ **Rate Limiting** - Prevent abuse with configurable rate limits
- ✅ **CORS Support** - Enable web-based clients
- ✅ **OpenAPI Documentation** - Interactive API docs at `/docs`
- ✅ **Health Checks** - Monitor service status
- ✅ **Error Handling** - Comprehensive error responses

## Quick Start

### Option 1: Using the Startup Script (Recommended)

```bash
# 1. Configure your environment
cp .env.template .env
# Edit .env and add your API keys

# 2. Run the startup script
./start_pinggy.sh
```

The script will:
- ✓ Check and install dependencies
- ✓ Start the FastAPI server
- ✓ Optionally create a Pinggy tunnel
- ✓ Provide usage instructions

### Option 2: Manual Setup

```bash
# 1. Install dependencies
pip install -e ".[bridge]"

# 2. Configure environment (see Configuration section below)
export MCP_API_KEY="your-secure-api-key"
export PINGGY_PORT=8000
export RATE_LIMIT_CALLS=100
export RATE_LIMIT_WINDOW=3600

# 3. Start the server
python -m investor_agent.pinggy_wrapper

# 4. In another terminal, create Pinggy tunnel
ssh -p 443 -R0:localhost:8000 a.pinggy.io
# OR
pinggy -p 8000
```

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Security (REQUIRED for production)
MCP_API_KEY=your-secure-random-api-key-here

# Server Configuration
PINGGY_HOST=127.0.0.1
PINGGY_PORT=8000

# Rate Limiting
RATE_LIMIT_CALLS=100        # Max calls per window
RATE_LIMIT_WINDOW=3600      # Window in seconds (1 hour)

# API Keys for MCP Tools
ALPACA_API_KEY=your_alpaca_key
ALPACA_API_SECRET=your_alpaca_secret
QUESTRADE_REFRESH_TOKEN=your_questrade_token

# Optional: LLM API Keys (for n8n integration)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### Security Best Practices

1. **Always set `MCP_API_KEY`** when exposing to the internet
2. **Use strong, random keys** (32+ characters)
3. **Configure rate limits** based on your usage patterns
4. **Monitor logs** for suspicious activity
5. **Use HTTPS** (Pinggy provides this automatically)

## Creating a Pinggy Tunnel

Pinggy provides free HTTPS tunnels to expose your local server to the internet.

### Method 1: Using SSH (No installation required)

```bash
ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

This will output a URL like:
```
https://randomstring.a.pinggy.io
```

### Method 2: Using Pinggy CLI

```bash
# Install Pinggy CLI
# See: https://pinggy.io/download

# Create tunnel
pinggy -p 8000
```

### Method 3: Using Pinggy with Custom Subdomain (Paid)

```bash
# With custom subdomain
ssh -p 443 -R0:localhost:8000 -t a.pinggy.io your-subdomain
```

Your public URL will be: `https://your-subdomain.a.pinggy.io`

## API Usage

### Authentication

Include your API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" https://your-url.a.pinggy.io/health
```

### Endpoints

#### `GET /` - API Information
```bash
curl https://your-url.a.pinggy.io/
```

Response:
```json
{
  "name": "Investor Agent MCP - Pinggy Tunnel",
  "version": "1.0.0",
  "status": "running",
  "authentication": "required",
  "endpoints": {
    "tools": "/tools",
    "call": "/call",
    "health": "/health",
    "rate_limit": "/rate-limit",
    "docs": "/docs"
  }
}
```

#### `GET /health` - Health Check
```bash
curl https://your-url.a.pinggy.io/health
```

#### `GET /tools` - List All Tools
```bash
curl -H "X-API-Key: your-api-key" \
     https://your-url.a.pinggy.io/tools
```

Response:
```json
{
  "tools": [
    {
      "name": "get_market_movers",
      "description": "Get top market movers...",
      "parameters": {
        "type": "object",
        "properties": {
          "category": {
            "type": "string",
            "enum": ["gainers", "losers", "most_active"]
          },
          "count": {
            "type": "integer",
            "default": 10
          }
        },
        "required": ["category"]
      },
      "is_async": false
    }
  ],
  "count": 28
}
```

#### `GET /tools/{tool_name}` - Get Tool Info
```bash
curl -H "X-API-Key: your-api-key" \
     https://your-url.a.pinggy.io/tools/get_ticker_data
```

#### `POST /call` - Call a Tool
```bash
curl -X POST https://your-url.a.pinggy.io/call \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "tool_name": "get_market_movers",
    "arguments": {
      "category": "gainers",
      "count": 5
    }
  }'
```

Response:
```json
{
  "success": true,
  "tool_name": "get_market_movers",
  "result": "Symbol,Name,Price,Change,Percent Change\nNVDA,NVIDIA,850.50,..."
}
```

#### `GET /rate-limit` - Check Rate Limit
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

### Interactive API Documentation

Visit `https://your-url.a.pinggy.io/docs` for interactive Swagger UI documentation.

## Example Usage Scenarios

### Scenario 1: Remote Market Data Access

```python
import requests

API_URL = "https://your-url.a.pinggy.io"
API_KEY = "your-api-key"

headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

# Get market movers
response = requests.post(
    f"{API_URL}/call",
    headers=headers,
    json={
        "tool_name": "get_market_movers",
        "arguments": {
            "category": "gainers",
            "count": 10
        }
    }
)

data = response.json()
print(data["result"])
```

### Scenario 2: n8n Integration

1. In n8n, add an **HTTP Request** node
2. Configure:
   - **Method**: POST
   - **URL**: `https://your-url.a.pinggy.io/call`
   - **Authentication**: Generic Credential Type
   - **Header Name**: `X-API-Key`
   - **Header Value**: `your-api-key`
3. Set **Body** to:
```json
{
  "tool_name": "get_ticker_data",
  "arguments": {
    "ticker": "{{ $json.ticker }}"
  }
}
```

### Scenario 3: Claude Desktop Integration (Remote)

While MCP typically runs locally, you can create a custom MCP client that connects to your Pinggy URL:

```python
import requests

class RemoteMCPClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }

    def call_tool(self, tool_name, **arguments):
        response = requests.post(
            f"{self.api_url}/call",
            headers=self.headers,
            json={
                "tool_name": tool_name,
                "arguments": arguments
            }
        )
        return response.json()

# Usage
client = RemoteMCPClient(
    "https://your-url.a.pinggy.io",
    "your-api-key"
)

result = client.call_tool("get_ticker_data", ticker="AAPL")
print(result["result"])
```

## Monitoring and Debugging

### Check Server Logs

```bash
# If running with start_pinggy.sh, logs will appear in terminal

# Or tail the logs
tail -f /var/log/investor-agent-pinggy.log
```

### Test Connectivity

```bash
# Test local server
curl http://localhost:8000/health

# Test through Pinggy tunnel
curl https://your-url.a.pinggy.io/health

# Test with authentication
curl -H "X-API-Key: your-api-key" \
     https://your-url.a.pinggy.io/tools
```

### Common Issues

#### Issue: 401 Unauthorized
**Solution**: Ensure you're sending the correct `X-API-Key` header.

```bash
# Wrong
curl https://your-url.a.pinggy.io/tools

# Correct
curl -H "X-API-Key: your-api-key" https://your-url.a.pinggy.io/tools
```

#### Issue: 429 Rate Limit Exceeded
**Solution**: Wait for the rate limit window to reset, or increase limits in `.env`:

```bash
RATE_LIMIT_CALLS=200
RATE_LIMIT_WINDOW=3600
```

#### Issue: 500 Internal Server Error
**Solution**: Check server logs for details. Common causes:
- Missing environment variables (ALPACA_API_KEY, etc.)
- Invalid API credentials
- Network connectivity issues

#### Issue: Pinggy tunnel disconnected
**Solution**: Reconnect the tunnel. For production, consider:
- Using Pinggy with a persistent connection
- Setting up automatic reconnection
- Using a service like systemd to auto-restart

## Production Deployment

For production use, consider these improvements:

### 1. Process Manager (systemd)

Create `/etc/systemd/system/investor-agent-pinggy.service`:

```ini
[Unit]
Description=Investor Agent MCP Pinggy Wrapper
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/investor-agent
EnvironmentFile=/path/to/investor-agent/.env
ExecStart=/usr/bin/python -m investor_agent.pinggy_wrapper
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable investor-agent-pinggy
sudo systemctl start investor-agent-pinggy
sudo systemctl status investor-agent-pinggy
```

### 2. Persistent Pinggy Tunnel

Create `/etc/systemd/system/pinggy-tunnel.service`:

```ini
[Unit]
Description=Pinggy Tunnel for Investor Agent
After=network.target investor-agent-pinggy.service

[Service]
Type=simple
User=your-user
ExecStart=/usr/bin/ssh -p 443 -R0:localhost:8000 a.pinggy.io
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Use Redis for Rate Limiting

For multi-instance deployments, replace in-memory rate limiting with Redis:

```python
# In pinggy_wrapper.py
import redis

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True
)
```

### 4. Add Nginx Reverse Proxy

For additional security and caching:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Alternatives to Pinggy

While this guide focuses on Pinggy, you can use other tunneling services:

### ngrok
```bash
ngrok http 8000
```

### localhost.run
```bash
ssh -R 80:localhost:8000 localhost.run
```

### Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

## Security Considerations

1. **API Key Rotation**: Regularly rotate your `MCP_API_KEY`
2. **HTTPS Only**: Always use HTTPS (Pinggy provides this)
3. **Rate Limiting**: Monitor and adjust based on usage
4. **Audit Logs**: Enable detailed logging for security audits
5. **Firewall Rules**: If self-hosting, configure firewall appropriately
6. **Environment Isolation**: Never commit `.env` to version control

## Support

For issues or questions:

- **MCP Server Issues**: Check `investor_agent/server.py`
- **Pinggy Issues**: Visit https://pinggy.io/docs
- **API Documentation**: Visit `/docs` endpoint on your running server

## License

Same as the main Investor Agent project.
