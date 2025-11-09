# Perplexity + Questrade: Hybrid Workflow Guide

## ⚠️ IMPORTANT: Perplexity Cannot Access Local MCP Servers

Perplexity is a web-based AI assistant and **CANNOT** directly access your local investor-agent MCP server or Questrade tools.

**Who CAN access Questrade tools:**
- ✅ Claude Desktop (has local MCP access)
- ❌ Perplexity (web-based, no local access)
- ❌ ChatGPT (web-based, no local access)
- ❌ Gemini (web-based, no local access)

---

## ✅ Recommended Approach: Use Claude Desktop

### Simple Queries (Just ask Claude Desktop)

**Account Overview:**
```
Claude Desktop:
Show me my Questrade accounts, balances, and current positions
```

**Position Analysis:**
```
Claude Desktop:
For each of my Questrade positions:
1. Get current market quote
2. Calculate P&L %
3. Run technical analysis (RSI, MACD, trend strength)
4. Check volume analysis (VWAP, OBV)
5. Recommend hold/sell/add
```

**Trading Performance (Heavy Trader):**
```
Claude Desktop:
Analyze my 2025 Questrade trading performance:
1. Retrieve executions month by month (Jan-Nov)
2. Retrieve activities month by month
3. Calculate total P&L, win rate, commissions
4. Find best and worst trades
5. Identify most traded symbols
```

---

## 🔄 Hybrid Workflow (If You Want to Use Both)

### Use Case: Complex Analysis Requiring Research

Sometimes you want Perplexity's web research combined with your Questrade data.

**Step 1: Get Data from Claude Desktop**
```
Ask Claude Desktop:
"Get my Questrade positions with full details:
- Symbol
- Quantity
- Entry price
- Current price
- Unrealized P&L
- Days held

Format as a detailed markdown table."
```

**Step 2: Copy Results to Perplexity**
```
Ask Perplexity:
"Here's my current portfolio:

[Paste Claude Desktop's table]

For each position:
1. Research recent news and catalysts
2. Check analyst ratings
3. Evaluate sector trends
4. Provide hold/sell/add recommendation with rationale
"
```

**Step 3: Execute Trades (Back in Claude Desktop)**
```
Ask Claude Desktop:
"Based on this analysis: [paste Perplexity's recommendations]

Review my Questrade positions and suggest specific actions with entry/exit prices"
```

---

## 📊 Example Complete Workflow

### Goal: Analyze and optimize your Questrade portfolio

**STEP 1: Data Collection (Claude Desktop)**
```
Get my Questrade data package:

1. All accounts with balances
2. All current positions with entry prices
3. Recent executions (last 30 days)
4. Recent activities (dividends, fees)

Format everything as structured data I can share with another AI.
```

**STEP 2: Technical Analysis (Claude Desktop)**
```
For each position symbol:
1. analyze_technical(symbol, period="6mo")
2. analyze_volume_tool(symbol, period="3mo")
3. analyze_volatility_tool(symbol, period="6mo")
4. calculate_relative_strength_tool(symbol, benchmark="SPY")
5. calculate_fundamental_scores_tool(symbol)

Summarize:
- Which positions are leaders (RS >70)?
- Which have value trap risk (F-Score <5)?
- Which have volume divergence?
- What are ATR-based stops for each?
```

**STEP 3: Market Research (Perplexity - Optional)**
```
[Paste position list from Claude Desktop]

For each stock:
1. What are the latest earnings results?
2. Any recent major news or catalysts?
3. What are analyst targets?
4. Are there sector-wide trends affecting this stock?
```

**STEP 4: Action Plan (Claude Desktop)**
```
Synthesize all analysis:

Current positions: [data from Step 1]
Technical analysis: [results from Step 2]
Market research: [insights from Step 3]

For each position, provide specific action:
- HOLD (why, what stop price?)
- SELL (why, at what price?)
- ADD (why, at what price?)

Include ATR-based stops and position sizing.
```

---

## 🎯 Claude Desktop Advantage: End-to-End Analysis

**Claude Desktop can do everything in one conversation:**

```
Comprehensive Questrade Portfolio Analysis:

PHASE 1: DATA COLLECTION
- Get all my Questrade accounts
- Get positions with entry prices and current P&L
- Get recent executions and activities

PHASE 2: TECHNICAL ANALYSIS (for each position)
- Technical indicators (RSI, MACD, moving averages)
- Volume analysis (VWAP, OBV, institutional support)
- Volatility analysis (ATR for stops)
- Relative strength (is it a market leader?)
- Fundamental quality (F-Score, Z-Score)

PHASE 3: MARKET CONTEXT
- Market sentiment (Fear & Greed Index)
- Sector performance
- Recent news for held symbols

PHASE 4: RECOMMENDATIONS
For each position:
- Action: HOLD / SELL / ADD
- Rationale based on ALL analysis
- Specific prices (entry, stop, target)
- ATR-based stop placement
- Position sizing recommendation

PHASE 5: SUMMARY
- Portfolio health score
- Total P&L
- Risk assessment
- Top 3 actions to take immediately
```

**Claude Desktop has access to 39 tools** to do all of this without needing external help!

---

## 💡 When to Use Each

### Use Claude Desktop When:
- ✅ You need Questrade data (accounts, positions, orders, executions)
- ✅ You want technical analysis (RSI, MACD, support/resistance)
- ✅ You need volume/volatility analysis (VWAP, ATR, OBV)
- ✅ You want everything in one place
- ✅ You need specific entry/exit prices with stops

### Use Perplexity When:
- ✅ You need web research (latest news, earnings reports)
- ✅ You want sector/macro analysis
- ✅ You need current analyst ratings
- ✅ You're researching new stocks (not in your portfolio yet)

### Hybrid Approach When:
- ✅ You want deep research on your existing positions
- ✅ You need both quantitative (Claude) + qualitative (Perplexity) analysis
- ✅ You're making major portfolio decisions

---

## 🚫 What Perplexity CANNOT Do

Even with the prompt template:
- ❌ Access your local Questrade account
- ❌ Call get_questrade_* tools
- ❌ See your positions or balances
- ❌ Retrieve your trading history
- ❌ Connect to local MCP servers

Perplexity can only:
- ✅ Explain how the tools work
- ✅ Suggest what tools you should use
- ✅ Analyze data you paste from Claude Desktop
- ✅ Research stocks using web search

---

## ✅ Bottom Line

**For Questrade analysis: Use Claude Desktop**

Claude Desktop gives you:
- Direct Questrade access (15 tools)
- Complete technical analysis (6 tools)
- Bootstrap analysis for risk management (4 tools)
- Fundamental analysis (6 tools)
- Market sentiment (4 tools)
- All in ONE conversation

**Only use Perplexity as a supplement** for web research if Claude Desktop's analysis needs additional context.

---

## 🎯 Try This Now

**In Claude Desktop, ask:**
```
Show me my Questrade portfolio with complete analysis:

1. All accounts and total equity
2. Current positions with P&L
3. For each position:
   - Technical analysis
   - Volume analysis
   - RS Score (is it a leader?)
   - F-Score (value trap check?)
   - ATR-based stop price
4. Recommend actions with specific prices
```

**Claude Desktop will handle everything!**

No need to copy-paste between AI assistants. No need for workarounds. Just ask and get comprehensive analysis.
