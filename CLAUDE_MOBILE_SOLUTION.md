# Using MCP Tools from Mobile with Claude

**TL;DR:** Claude Mobile app and Claude Web don't support MCP. But you can use Claude API with MCP tools from your mobile device using the proxy service.

## The Problem

- ❌ **Claude Mobile app** - No MCP support
- ❌ **Claude Web (claude.ai)** - No MCP support
- ❌ **Claude Desktop** - No remote access capability
- ✅ **Claude Desktop** - Only app that supports MCP (local only)

## The Solutions

### Solution 1: Claude API Proxy (Use Claude from Mobile with MCP) 🌟

This solution lets you chat with Claude from your mobile device while having access to all MCP tools running on your laptop.

**How it works:**
```
Mobile Browser
    ↓
Pinggy Tunnel (HTTPS)
    ↓
Claude API Proxy (your laptop)
    ↓ calls MCP tools
MCP Server (gets stock data)
    ↓
Claude API (Anthropic's servers)
    ↓
Returns answer to your mobile
```

#### Setup Steps

**1. Configure Environment**

Edit `.env`:
```bash
# REQUIRED: Get from https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional: Secure your proxy
MCP_API_KEY=your-secure-key

# Optional: Custom port
CLAUDE_PROXY_PORT=8001

# Required for MCP tools
ALPACA_API_KEY=...
QUESTRADE_REFRESH_TOKEN=...
```

**2. Start the Claude API Proxy**

```bash
# Start the proxy service
python claude_proxy_service.py

# In another terminal, create Pinggy tunnel
ssh -p 443 -R0:localhost:8001 a.pinggy.io
```

You'll get a URL like: `https://randomstring.a.pinggy.io`

**3. Use from Mobile**

Open `mobile_chat.html` in your mobile browser or access the Pinggy URL directly.

#### Mobile Browser Interface

Open `mobile_chat.html` in your browser:

1. **Locally (testing):**
   - Connect phone to same WiFi as laptop
   - Find laptop's IP: `ifconfig` or `ipconfig`
   - Open: `http://YOUR-LAPTOP-IP:8001/mobile_chat.html`

2. **Remotely (via Pinggy):**
   - After creating tunnel, note the Pinggy URL
   - Serve the HTML: `python -m http.server 9000`
   - Create tunnel for HTML: `ssh -p 443 -R0:localhost:9000 a.pinggy.io`
   - Open the Pinggy URL in mobile browser

3. **Configure in App:**
   - Click ⚙️ Settings
   - Enter Pinggy URL: `https://your-url.a.pinggy.io`
   - Enter API Key (if you set MCP_API_KEY)
   - Save

4. **Start Chatting:**
   - Ask: "What are today's top stock gainers?"
   - Claude will automatically call MCP tools
   - See results with tool usage indicators

#### API Usage (Build Your Own App)

You can also call the proxy API directly from your custom mobile app:

```javascript
// Your mobile app (React Native, Flutter, etc.)
async function chatWithClaude(message, history = []) {
  const response = await fetch('https://your-pinggy-url.a.pinggy.io/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'your-api-key'  // if MCP_API_KEY is set
    },
    body: JSON.stringify({
      message: message,
      conversation_history: history,
      model: 'claude-3-5-sonnet-20241022'
    })
  });

  const data = await response.json();
  return {
    response: data.response,
    toolsCalled: data.tool_calls_made,
    history: data.conversation_history
  };
}

// Usage
const result = await chatWithClaude("What's Apple's stock price?");
console.log(result.response);
console.log("Tools used:", result.toolsCalled);
```

#### Example Conversation

**You:** "What are today's top 3 stock gainers?"

**Claude Proxy:**
- Calls `get_market_movers(category="gainers", count=3)`
- Gets real data from MCP server
- Sends to Claude API with context
- Returns: "Here are today's top 3 gainers: [detailed analysis]"

**You see:** The answer plus indicator showing it used `get_market_movers()`

---

### Solution 2: Direct MCP API (Custom Mobile App)

Use the Pinggy wrapper to call MCP tools directly and format results yourself.

**Setup:**
```bash
docker-compose up -d investor-agent-pinggy
ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

**From Mobile App:**
```javascript
// Call MCP tool directly
const response = await fetch('https://your-url.a.pinggy.io/call', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    tool_name: 'get_market_movers',
    arguments: { category: 'gainers', count: 5 }
  })
});

const data = await response.json();
// data.result contains CSV with stock data
// Format and display in your app
```

**Pros:**
- ✅ Direct access to MCP tools
- ✅ Full control over UI
- ✅ No Claude API costs

**Cons:**
- ❌ No Claude's intelligence
- ❌ You handle all data formatting
- ❌ You build entire UI

---

### Solution 3: Remote Desktop to Claude Desktop

Use remote desktop software to access your laptop from mobile:

- **TeamViewer / AnyDesk** - Remote into laptop
- **Chrome Remote Desktop** - Access via browser
- **VNC** - Open source option

**Pros:**
- ✅ Full Claude Desktop experience
- ✅ Access to all MCP features

**Cons:**
- ❌ Not mobile-friendly UI
- ❌ Requires laptop to be on
- ❌ Poor mobile experience

---

## Comparison Table

| Solution | Claude's Intelligence | Mobile Friendly | Costs | Setup Difficulty |
|----------|---------------------|----------------|-------|-----------------|
| **Claude API Proxy** | ✅ Yes | ✅ Yes | Claude API usage | Medium |
| **Direct MCP API** | ❌ No | ✅ Yes | Free | Easy |
| **Remote Desktop** | ✅ Yes | ❌ No | Free | Easy |
| **Claude Desktop** | ✅ Yes | ❌ No | Free | Easy |

---

## Detailed Comparison: API Costs

### Solution 1: Claude API Proxy

**Costs:**
- Claude API usage (pay per token)
- Pricing: https://www.anthropic.com/pricing
- ~$3 per million input tokens
- ~$15 per million output tokens

**Example cost:**
- Question: "What are top gainers?" (~100 tokens)
- MCP tool result: (~500 tokens)
- Claude's response: (~300 tokens)
- **Total: ~$0.0024 per query**

### Solution 2: Direct MCP API

**Costs:**
- Free (no Claude API needed)
- Just your hosting/tunnel costs

---

## Security Considerations

### Claude API Proxy
1. **Protect ANTHROPIC_API_KEY** - This is YOUR API key
2. **Set MCP_API_KEY** - Require auth from mobile
3. **Monitor usage** - Track Claude API costs
4. **Rate limiting** - Prevent abuse

### Direct MCP API
1. **Set MCP_API_KEY** - Required for security
2. **Rate limiting** - Built-in protection
3. **CORS** - Already configured

---

## Recommended Setup

### For Testing/Development
```bash
# Use Solution 2 (Direct MCP API)
docker-compose up -d investor-agent-pinggy
ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

### For Production/Best UX
```bash
# Use Solution 1 (Claude API Proxy)
# Set ANTHROPIC_API_KEY in .env
python claude_proxy_service.py
ssh -p 443 -R0:localhost:8001 a.pinggy.io
# Open mobile_chat.html on your phone
```

---

## FAQ

**Q: Can Claude Mobile app use MCP?**
A: No. Claude Mobile doesn't support MCP. You need to use the Claude API Proxy solution.

**Q: Can Claude Web (claude.ai) use MCP?**
A: No. Only Claude Desktop supports MCP natively.

**Q: Will this work if my laptop is offline?**
A: No. The MCP server runs on your laptop, so it must be on and connected.

**Q: Can multiple people use my proxy?**
A: Yes, if you share the Pinggy URL and API key. But YOU pay for all Claude API usage!

**Q: Is there a way to use Claude Desktop from mobile?**
A: Not directly. Use remote desktop software as a workaround (not recommended).

**Q: Which solution should I use?**
A: Claude API Proxy if you want Claude's intelligence. Direct MCP API if you're building a custom app.

**Q: How much does Claude API cost?**
A: Very little for typical usage. ~$0.002-0.005 per query. See Anthropic's pricing.

---

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
```bash
# Get key from https://console.anthropic.com/
# Add to .env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### "Cannot connect from mobile"
```bash
# Check Pinggy tunnel is running
# Check you're using HTTPS URL
# Check MCP_API_KEY if set
```

### "Tool calls failing"
```bash
# Check MCP tools are working locally
python -c "from investor_agent import server; print('OK')"

# Check API keys for tools
# ALPACA_API_KEY for intraday data
# QUESTRADE_REFRESH_TOKEN for account data
```

### "High Claude API costs"
```bash
# Add rate limiting in proxy service
# Monitor usage at https://console.anthropic.com/
# Set spending limits in Anthropic console
```

---

## Next Steps

1. **Test locally first:**
   ```bash
   python claude_proxy_service.py
   # Open http://localhost:8001 in browser
   ```

2. **Create Pinggy tunnel:**
   ```bash
   ssh -p 443 -R0:localhost:8001 a.pinggy.io
   ```

3. **Access from mobile:**
   - Open Pinggy URL in mobile browser
   - Configure API URL in settings
   - Start chatting!

4. **Build custom app** (optional):
   - Use provided API examples
   - See DOCKER_PINGGY.md for mobile app code
   - Integrate into your iOS/Android/React Native app

---

## Related Documentation

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Which setup to use
- **[PINGGY_SETUP.md](PINGGY_SETUP.md)** - Pinggy tunnel setup
- **[DOCKER_PINGGY.md](DOCKER_PINGGY.md)** - Docker deployment guide

---

**Summary:** You CANNOT use MCP directly from Claude Mobile or Claude Web. But you CAN use the Claude API Proxy to chat with Claude from your mobile while accessing MCP tools on your laptop! 🎉
