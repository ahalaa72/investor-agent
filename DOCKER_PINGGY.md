# Docker Setup for Investor Agent with Pinggy

Complete guide for running the Investor Agent MCP server with Pinggy tunnel support using Docker.

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# 1. Configure environment
cp .env.template .env
# Edit .env and set your API keys (especially MCP_API_KEY)

# 2. Start the Pinggy service
docker-compose up investor-agent-pinggy

# Your server will be available at http://localhost:8000
```

### Option 2: With Automatic Pinggy Tunnel

```bash
# 1. Configure environment
cp .env.template .env

# 2. Edit .env and enable tunnel:
# ENABLE_PINGGY_TUNNEL=true
# MCP_API_KEY=your-secure-api-key

# 3. Start with tunnel enabled
docker-compose up investor-agent-pinggy

# The Pinggy URL will appear in the logs
```

## 📦 Available Services

The `docker-compose.yml` provides two services:

### 1. `investor-agent` (Original MCP Server)
- For local use with Claude Desktop
- Uses `Dockerfile`
- No exposed ports
- Access via Docker exec

```bash
docker-compose up investor-agent
```

### 2. `investor-agent-pinggy` (Remote Access Wrapper)
- For web/mobile app access
- Uses `Dockerfile.pinggy`
- Exposed on port 8000
- Includes Pinggy tunnel support

```bash
docker-compose up investor-agent-pinggy
```

## ⚙️ Configuration

### Environment Variables

Edit your `.env` file:

```bash
# REQUIRED: API Key for authentication
MCP_API_KEY=your-secure-random-key-here-32-chars-min

# Optional: Enable automatic Pinggy tunnel
ENABLE_PINGGY_TUNNEL=false

# Optional: Custom subdomain (paid Pinggy feature)
PINGGY_SUBDOMAIN=my-investor-agent

# API keys for MCP tools
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
QUESTRADE_REFRESH_TOKEN=...

# Rate limiting
RATE_LIMIT_CALLS=100
RATE_LIMIT_WINDOW=3600
```

### Important Configuration Notes

1. **MCP_API_KEY** - **REQUIRED**. The container will refuse to start without this for security.
2. **ENABLE_PINGGY_TUNNEL** - Set to `true` to automatically create a Pinggy tunnel
3. **PINGGY_SUBDOMAIN** - Only works with Pinggy paid plans

## 🔨 Building and Running

### Build the Image

```bash
# Build Pinggy wrapper image
docker-compose build investor-agent-pinggy

# Or build directly
docker build -f Dockerfile.pinggy -t investor-agent-pinggy:latest .
```

### Run the Container

```bash
# Start in foreground
docker-compose up investor-agent-pinggy

# Start in background
docker-compose up -d investor-agent-pinggy

# View logs
docker-compose logs -f investor-agent-pinggy
```

### Stop the Container

```bash
# Stop gracefully
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## 🌐 Access Modes

### Mode 1: Local Access Only (Default)

```bash
# Start without tunnel
ENABLE_PINGGY_TUNNEL=false docker-compose up investor-agent-pinggy
```

Access at: `http://localhost:8000`

**Use for:**
- Local development
- Testing
- Integration with local apps
- Reverse proxy setup (Nginx, Caddy, Traefik)

### Mode 2: With Pinggy Tunnel (Remote Access)

```bash
# Start with tunnel
ENABLE_PINGGY_TUNNEL=true docker-compose up investor-agent-pinggy
```

The tunnel URL will appear in logs:
```
https://randomstring.a.pinggy.io
```

**Use for:**
- Remote mobile app access
- Public API access
- Quick demos
- Development across devices

### Mode 3: Manual Tunnel from Host

```bash
# 1. Start container without tunnel
docker-compose up -d investor-agent-pinggy

# 2. Create tunnel from host machine
ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

**Use for:**
- More control over tunnel
- Easier debugging
- Custom SSH options

### Mode 4: Manual Tunnel from Inside Container

```bash
# 1. Start container
docker-compose up -d investor-agent-pinggy

# 2. Exec into container and create tunnel
docker exec -it investor-agent-pinggy \
    ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

## 🧪 Testing Your Setup

### Test Health Endpoint

```bash
# From host machine
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","service":"investor-agent-pinggy","timestamp":"..."}
```

### Test API with Authentication

```bash
# Set your API key
export API_KEY="your-api-key-from-env"

# List all tools
curl -H "X-API-Key: $API_KEY" http://localhost:8000/tools

# Call a tool
curl -X POST http://localhost:8000/call \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "tool_name": "get_market_movers",
    "arguments": {"category": "gainers", "count": 5}
  }'
```

### Test via Pinggy URL

```bash
# Replace with your actual Pinggy URL
PINGGY_URL="https://xxxx.a.pinggy.io"

curl -H "X-API-Key: $API_KEY" $PINGGY_URL/health
```

### Access API Documentation

Open in browser:
- Local: http://localhost:8000/docs
- Remote: https://your-url.a.pinggy.io/docs

## 📱 Mobile App Integration

### iOS (Swift)

```swift
import Foundation

class InvestorAgentAPI {
    let baseURL = "https://your-url.a.pinggy.io"
    let apiKey = "your-api-key"

    func callTool(name: String, arguments: [String: Any]) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/call")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")

        let body: [String: Any] = [
            "tool_name": name,
            "arguments": arguments
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONSerialization.jsonObject(with: data) as! [String: Any]
    }
}

// Usage
let api = InvestorAgentAPI()
let result = try await api.callTool(
    name: "get_ticker_data",
    arguments: ["ticker": "AAPL"]
)
print(result)
```

### Android (Kotlin)

```kotlin
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class InvestorAgentAPI(
    private val baseUrl: String = "https://your-url.a.pinggy.io",
    private val apiKey: String = "your-api-key"
) {
    private val client = OkHttpClient()
    private val mediaType = "application/json".toMediaType()

    suspend fun callTool(name: String, arguments: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        val body = JSONObject().apply {
            put("tool_name", name)
            put("arguments", arguments)
        }

        val request = Request.Builder()
            .url("$baseUrl/call")
            .post(body.toString().toRequestBody(mediaType))
            .addHeader("X-API-Key", apiKey)
            .build()

        val response = client.newCall(request).execute()
        JSONObject(response.body!!.string())
    }
}

// Usage
val api = InvestorAgentAPI()
val result = api.callTool("get_ticker_data", JSONObject().apply {
    put("ticker", "AAPL")
})
println(result)
```

### React Native (JavaScript)

```javascript
class InvestorAgentAPI {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl || 'https://your-url.a.pinggy.io';
    this.apiKey = apiKey || 'your-api-key';
  }

  async callTool(toolName, arguments) {
    const response = await fetch(`${this.baseUrl}/call`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
      },
      body: JSON.stringify({
        tool_name: toolName,
        arguments: arguments,
      }),
    });

    return await response.json();
  }
}

// Usage
const api = new InvestorAgentAPI();
const result = await api.callTool('get_ticker_data', { ticker: 'AAPL' });
console.log(result);
```

### Flutter (Dart)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class InvestorAgentAPI {
  final String baseUrl;
  final String apiKey;

  InvestorAgentAPI({
    this.baseUrl = 'https://your-url.a.pinggy.io',
    required this.apiKey,
  });

  Future<Map<String, dynamic>> callTool(
    String toolName,
    Map<String, dynamic> arguments,
  ) async {
    final response = await http.post(
      Uri.parse('$baseUrl/call'),
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: jsonEncode({
        'tool_name': toolName,
        'arguments': arguments,
      }),
    );

    return jsonDecode(response.body);
  }
}

// Usage
final api = InvestorAgentAPI(apiKey: 'your-api-key');
final result = await api.callTool('get_ticker_data', {'ticker': 'AAPL'});
print(result);
```

## 🔍 Monitoring and Debugging

### View Logs

```bash
# Follow logs
docker-compose logs -f investor-agent-pinggy

# View last 100 lines
docker-compose logs --tail=100 investor-agent-pinggy

# View logs since 1 hour ago
docker-compose logs --since 1h investor-agent-pinggy
```

### Check Container Status

```bash
# List running containers
docker-compose ps

# Check health status
docker inspect investor-agent-pinggy | grep -A 10 Health
```

### Access Container Shell

```bash
# Execute bash in running container
docker exec -it investor-agent-pinggy /bin/bash

# Run commands inside container
docker exec investor-agent-pinggy curl http://localhost:8000/health
```

### Debug Network Issues

```bash
# Check exposed ports
docker port investor-agent-pinggy

# Test from inside container
docker exec investor-agent-pinggy curl http://localhost:8000/health

# Test from host
curl http://localhost:8000/health
```

## 🏭 Production Deployment

### 1. Use Docker Compose with Restart Policies

```yaml
# docker-compose.prod.yml
services:
  investor-agent-pinggy:
    # ... other config ...
    restart: always
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 2. Behind Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. With Traefik

```yaml
services:
  investor-agent-pinggy:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.investor-agent.rule=Host(`api.yourdomain.com`)"
      - "traefik.http.routers.investor-agent.entrypoints=websecure"
      - "traefik.http.routers.investor-agent.tls.certresolver=letsencrypt"
```

### 4. Environment Management

```bash
# Use different env files for different environments
docker-compose --env-file .env.production up -d

# Or set variables directly
MCP_API_KEY=prod-key \
ENABLE_PINGGY_TUNNEL=true \
docker-compose up -d investor-agent-pinggy
```

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check if MCP_API_KEY is set
docker-compose config | grep MCP_API_KEY

# View container logs
docker-compose logs investor-agent-pinggy

# Common issue: Missing MCP_API_KEY
# Solution: Add to .env file
```

### Port 8000 Already in Use

```bash
# Find what's using the port
lsof -i :8000

# Or use different port
docker-compose up -d
docker run -p 8001:8000 ...
```

### Pinggy Tunnel Not Connecting

```bash
# Check if SSH is available in container
docker exec investor-agent-pinggy which ssh

# Manually test tunnel
docker exec -it investor-agent-pinggy \
    ssh -p 443 -R0:localhost:8000 a.pinggy.io

# Check container logs for tunnel output
docker-compose logs -f investor-agent-pinggy | grep -i pinggy
```

### API Returns 401 Unauthorized

```bash
# Verify API key is set correctly
docker exec investor-agent-pinggy env | grep MCP_API_KEY

# Test with correct header
curl -H "X-API-Key: $(grep MCP_API_KEY .env | cut -d= -f2)" \
     http://localhost:8000/tools
```

### High Memory Usage

```bash
# Check container stats
docker stats investor-agent-pinggy

# Limit memory in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
```

## 📚 Additional Resources

- **Pinggy Documentation**: https://pinggy.io/docs
- **Docker Compose Reference**: https://docs.docker.com/compose/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Main Pinggy Setup Guide**: [PINGGY_SETUP.md](PINGGY_SETUP.md)
- **Quick Start Guide**: [PINGGY_QUICKSTART.md](PINGGY_QUICKSTART.md)

## 🔐 Security Best Practices

1. **Never expose without MCP_API_KEY** - The container enforces this
2. **Use strong API keys** - Minimum 32 characters, random
3. **Rotate keys regularly** - Change MCP_API_KEY periodically
4. **Monitor logs** - Watch for suspicious activity
5. **Use HTTPS** - Always use Pinggy or reverse proxy with SSL
6. **Rate limiting** - Configure appropriate limits for your use case
7. **Network isolation** - Use Docker networks to isolate services
8. **Keep images updated** - Rebuild regularly to get security patches

## 💡 Pro Tips

1. **Use .env.production** for production deployments
2. **Enable Docker logging driver** for centralized logs
3. **Use health checks** for automatic restart on failure
4. **Consider Redis** for distributed rate limiting
5. **Set up monitoring** with Prometheus/Grafana
6. **Use Docker secrets** for sensitive data in Swarm mode

---

**Ready to deploy?** Start with `docker-compose up investor-agent-pinggy` and you're good to go! 🚀
