# Cost Management & Optimization Guide

## Understanding Claude API Costs

### Pricing (Claude 3.5 Sonnet - as of January 2025)

- **Input tokens:** $3 per million tokens
- **Output tokens:** $15 per million tokens

See: https://www.anthropic.com/pricing

### What Affects Cost?

1. **Input tokens:**
   - Your question
   - System prompt (defines Claude's role)
   - Conversation history
   - Tool results (stock data from MCP)

2. **Output tokens:**
   - Claude's response length
   - More detailed answers = more tokens = higher cost

## Response Modes & Cost Control

The proxy service offers 3 response modes to control costs:

### Mode 1: Concise (Cheapest)
```bash
# In .env
CLAUDE_RESPONSE_MODE=concise
```

- **Max tokens:** 1,024
- **Style:** Brief, to-the-point (2-3 paragraphs)
- **Cost per query:** ~$0.001-0.002
- **Best for:** Quick lookups, simple questions
- **Example:** "What's Apple's stock price?" → Short answer with price

### Mode 2: Balanced (Default)
```bash
# In .env
CLAUDE_RESPONSE_MODE=balanced
```

- **Max tokens:** 2,048
- **Style:** Standard analysis (3-5 paragraphs)
- **Cost per query:** ~$0.002-0.004
- **Best for:** General use, moderate analysis
- **Example:** "What are top gainers?" → List + brief context

### Mode 3: Detailed (Most expensive)
```bash
# In .env
CLAUDE_RESPONSE_MODE=detailed
```

- **Max tokens:** 4,096
- **Style:** Comprehensive analysis with full context
- **Cost per query:** ~$0.004-0.008
- **Best for:** In-depth analysis, research
- **Example:** "Analyze Tesla" → Full analysis with context

## Cost Examples

### Example 1: Simple Question (Concise mode)

**Question:** "What's Apple's current stock price?"

**Breakdown:**
- Input: ~200 tokens (question + system prompt + tool results)
- Output: ~100 tokens (concise answer)
- **Total cost: ~$0.0020**

### Example 2: Market Analysis (Balanced mode)

**Question:** "What are today's top 5 stock gainers and why are they up?"

**Breakdown:**
- Input: ~500 tokens (question + system + tool results with 5 stocks)
- Output: ~300 tokens (analysis with context)
- **Total cost: ~$0.0060**

### Example 3: Comprehensive Report (Detailed mode)

**Question:** "Give me a full analysis of Tesla including financials, technicals, and market sentiment"

**Breakdown:**
- Input: ~2,000 tokens (multiple tool results)
- Output: ~1,500 tokens (detailed analysis)
- **Total cost: ~$0.0285**

## Monthly Cost Estimates

### Light Usage (Concise mode)
- 50 queries/day × 30 days = 1,500 queries/month
- ~$0.002 per query
- **Monthly cost: ~$3.00**

### Moderate Usage (Balanced mode)
- 100 queries/day × 30 days = 3,000 queries/month
- ~$0.003 per query
- **Monthly cost: ~$9.00**

### Heavy Usage (Mixed modes)
- 200 queries/day × 30 days = 6,000 queries/month
- 50% concise, 30% balanced, 20% detailed
- **Monthly cost: ~$15-20**

### Power User (Detailed mode)
- 300 queries/day × 30 days = 9,000 queries/month
- ~$0.005 average per query
- **Monthly cost: ~$45**

## Cost Optimization Strategies

### 1. Use Appropriate Response Mode

```python
# For quick lookups - use concise
{
  "message": "AAPL stock price?",
  "response_mode": "concise"
}

# For analysis - use balanced
{
  "message": "Analyze AAPL vs MSFT",
  "response_mode": "balanced"
}

# For research - use detailed
{
  "message": "Full analysis of semiconductor sector",
  "response_mode": "detailed"
}
```

### 2. Ask Focused Questions

**❌ Expensive:**
"Tell me everything about Apple, Microsoft, Google, Amazon, and Tesla including their financials, market position, recent news, analyst ratings, and future outlook"

**✅ Cheaper:**
"Compare Apple and Microsoft's P/E ratios and revenue growth"

### 3. Use Direct MCP API When Possible

If you just need raw data without analysis:

```javascript
// Instead of asking Claude:
// "What are today's top gainers?" (~$0.003)

// Call MCP directly:
fetch('/call', {
  body: JSON.stringify({
    tool_name: 'get_market_movers',
    arguments: { category: 'gainers', count: 5 }
  })
})
// Cost: FREE (just format the CSV yourself)
```

### 4. Limit Conversation History

Each message in history adds to input tokens:

```javascript
// Keep only recent history
const recentHistory = conversation_history.slice(-4); // Last 4 messages

fetch('/chat', {
  body: JSON.stringify({
    message: "What about Tesla?",
    conversation_history: recentHistory  // Not full history
  })
});
```

### 5. Batch Similar Questions

**❌ Expensive:**
- "What's Apple's price?" ($0.002)
- "What's Microsoft's price?" ($0.002)
- "What's Google's price?" ($0.002)
- Total: $0.006

**✅ Cheaper:**
- "What are the prices for AAPL, MSFT, and GOOGL?" ($0.003)
- Total: $0.003 (50% savings)

### 6. Set Max Tokens Per Request

```python
# Limit response length programmatically
{
  "message": "Quick summary of market today",
  "max_tokens": 512  # Force shorter response
}
```

### 7. Monitor and Alert

```python
# Track cumulative costs
total_cost = 0.0

response = await chat(...)
total_cost += response.estimated_cost

if total_cost > 1.00:  # $1 daily limit
    send_alert("Daily cost limit reached!")
```

## System Prompt Optimization

The system prompt is sent with EVERY request. Current prompt: ~300 tokens.

### Shorter System Prompt (saves ~$0.0005 per query)

Edit `claude_proxy_service.py`:

```python
# Original: ~300 tokens
SYSTEM_PROMPT = """You are an expert financial analyst..."""

# Optimized: ~100 tokens
SYSTEM_PROMPT = """You are a financial analyst with real-time market data tools.
Use tools when needed. Response mode: {response_mode}.
- concise: 2-3 paragraphs
- balanced: 3-5 paragraphs
- detailed: comprehensive"""
```

**Savings:** ~$0.0005 per query × 1000 queries = $0.50/month

## Real-World Cost Scenarios

### Scenario A: Day Trader
- **Usage:** 200 quick price checks/day
- **Mode:** Concise
- **Cost:** 200 × $0.0015 = $0.30/day = **$9/month**

### Scenario B: Swing Trader
- **Usage:** 50 stock analyses/day
- **Mode:** Balanced
- **Cost:** 50 × $0.003 = $0.15/day = **$4.50/month**

### Scenario C: Research Analyst
- **Usage:** 20 deep analyses/day
- **Mode:** Detailed
- **Cost:** 20 × $0.006 = $0.12/day = **$3.60/month**

### Scenario D: Mixed Usage
- **Usage:**
  - 50 quick checks (concise) = $0.075
  - 20 analyses (balanced) = $0.060
  - 5 reports (detailed) = $0.030
- **Daily cost:** $0.165 = **$4.95/month**

## Cost vs Value

### When to Pay for Claude API

✅ **Worth it:**
- Need intelligent analysis, not just data
- Want natural language interaction
- Value time saved over a few dollars
- Need mobile access to analysis

❌ **Not worth it:**
- Only need raw data (use direct MCP API)
- Can use Claude Desktop (free)
- On tight budget
- Don't need mobile access

### Alternative: Claude Desktop (Free)

If cost is a concern, use Claude Desktop on laptop:
- **Cost:** $0 (free)
- **Limitation:** Only works on laptop, not mobile
- **Setup:** See Setup A in DEPLOYMENT_GUIDE.md

## Tracking Costs in the UI

The `mobile_chat.html` can show costs. Add to the interface:

```javascript
// Display cost after each response
const result = await response.json();
showMessage(result.response, 'assistant', result.tool_calls_made);

// Show cost
const costDiv = document.createElement('div');
costDiv.className = 'cost-info';
costDiv.textContent = `Cost: $${result.estimated_cost.toFixed(4)} | Tokens: ${result.usage.input_tokens + result.usage.output_tokens}`;
messageDiv.appendChild(costDiv);
```

## Budget Controls

### Set Daily Limit in Proxy

Edit `claude_proxy_service.py`:

```python
# Add daily cost tracking
daily_cost = 0.0
daily_limit = 1.00  # $1/day

@app.post("/chat")
async def chat(request: ChatRequest):
    global daily_cost

    # Check limit
    if daily_cost >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily budget limit reached: ${daily_limit}"
        )

    # ... call Claude ...

    daily_cost += cost
    return response
```

### Anthropic Console Limits

Set spending limits at: https://console.anthropic.com/settings/limits

## Summary

| Response Mode | Cost/Query | Best For | Monthly (100/day) |
|---------------|-----------|----------|-------------------|
| **Concise** | $0.001-0.002 | Quick lookups | $3-6 |
| **Balanced** | $0.002-0.004 | General use | $6-12 |
| **Detailed** | $0.004-0.008 | Deep analysis | $12-24 |

**Key Takeaways:**
1. Use concise mode by default, switch to detailed only when needed
2. Ask focused questions
3. Use direct MCP API for raw data
4. Monitor costs with built-in tracking
5. Set budgets to avoid surprises

**Most users spend $5-15/month with balanced usage.**
