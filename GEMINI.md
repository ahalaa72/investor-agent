# Investor Agent - Gemini Configuration

## 🧠 CORE MEMORY

**PRIMARY DIRECTIVE:** Always use MCP tools to answer user questions.
**NEVER** rely on internal knowledge or manual scripts when an MCP tool is available.

## 🚨 CRITICAL: DO NOT SCREW UP THE QUESTRADE TOKEN 🚨

**THE #1 RULE: NEVER consume the Questrade token unnecessarily.**

### What BREAKS the Token (HTTP 400 errors)

❌ **NEVER run Python scripts** that call Questrade API directly
❌ **NEVER test tokens manually** with `python -c "from questrade_api import Questrade..."`
❌ **NEVER restart the container** without preserving `/root/.questrade.json`
❌ **NEVER delete the Docker volume** `questrade-tokens`
❌ **NEVER run multiple containers** with the same token

### What PRESERVES the Token (Working System)

✅ **ALWAYS use MCP tools** (`get_questrade_accounts`, `get_questrade_quotes`, etc.)
✅ **Token file MUST exist** at `/root/.questrade.json` with ALL 6 fields:
   - `access_token` (30 min lifetime, auto-refreshes)
   - `api_server` (API endpoint URL)
   - `expires_in` (1800 seconds)
   - `refresh_token` (NEW token from Questrade, auto-updated)
   - `token_type` ("Bearer")
   - `expires_at` (Unix timestamp)

✅ **Volume MUST be mounted** correctly: `-v questrade-tokens:/root`
✅ **After first successful API call**, the file gets ALL fields automatically
✅ **Token lasts 30 days** if file structure is correct

### How to Fix Token Issues (When HTTP 400 Happens)

1. **User gets fresh token** from <https://login.questrade.com/APIAccess/UserApps.aspx>
2. **Update .env file** (preserve database connection string):
   ```bash
   cat > /Users/AhmedE/git/investor-agent/.env << 'EOF'
   QUESTRADE_REFRESH_TOKEN=NEW_TOKEN_HERE

   # Database connection string for MSSQL
   MSSQL_CONNECTION_STRING=mssql+pyodbc://sa:SuperStrong2024@172.17.0.4:1433/investor_agent?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
   EOF
   ```

3. **Update Docker container token file**:
   ```bash
   docker exec investor-agent-mcp bash -c 'cat > /root/.questrade.json << "EOF"
   {
     "refresh_token": "NEW_TOKEN_HERE",
     "token_type": "Bearer"
   }
   EOF'
   ```

4. **Restart container**:
   ```bash
   docker restart investor-agent-mcp && sleep 5
   ```

5. **Test with MCP tool** (NOT Python script):
   ```bash
   get_questrade_accounts()
   ```

6. **Verify token file has ALL 6 fields**:
   ```bash
   docker exec investor-agent-mcp python -c "
   import json
   from pathlib import Path
   with open('/root/.questrade.json') as f:
       data = json.load(f)
   print('Fields:', list(data.keys()))
   print('Has all 6:', len(data) == 6)
   "
   ```

**If file has all 6 fields, token will auto-refresh for 30 days. Otherwise, it will fail on next API call.**

---

## MCP Tools

This project has an **investor-agent** MCP server with 80+ tools for stock analysis, portfolio management, and trading signals.

**IMPORTANT:** Always use the MCP tools from `investor-agent` for any investment-related tasks:

### Account & Portfolio
- `get_questrade_accounts` - List all Questrade accounts
- `get_questrade_positions` - Get positions for an account
- `get_questrade_balances` - Get account balances
- `get_portfolio_summary` - Full portfolio analysis

### Stock Analysis
- `get_questrade_quotes` - **⭐ USE FIRST** - Real-time quotes with bid/ask, pre-market data
- `get_ticker_data` - Comprehensive ticker data (falls back to Yahoo Finance)
- `analyze_technical` - RSI, MACD, Bollinger Bands, Al Brooks analysis
- `generate_trading_signal` - Complete trading signal with 4-gate validation
- `detect_catalyst_strength` - Detect earnings, insider activity, upgrades

### Market Scanning
- `scan_long_candidates` - Find LONG opportunities
- `scan_short_candidates` - Find SHORT opportunities
- `scan_market_opportunities` - Full market scan

### Options
- `analyze_options_mcmillan` - McMillan methodology analysis
- `generate_options_trade_plan` - Complete options trade plan

## Usage Rules

1. **ALWAYS use Questrade API for real-time data** - Prioritize `get_questrade_quotes` over `get_ticker_data`
2. **Pre-market/After-hours**: Use `get_questrade_quotes` for live bid/ask and current trading activity
3. **NEVER write Python scripts** to access Questrade or analyze stocks - use MCP tools instead
4. **ALWAYS prefer MCP tools** over manual code for any investment task
5. For portfolio queries, use `get_questrade_accounts` first to get account numbers

### Data Source Priority (CRITICAL)

**When user asks for current price or wants to analyze a stock:**

1. **FIRST**: Use `get_questrade_quotes(symbols=["TICKER"])`
   - Real-time bid/ask spread
   - Pre-market/after-hours activity
   - Live volume and VWAP
   - No delay (live data)

2. **SECOND**: Use `get_ticker_data(ticker="TICKER")` only for:
   - Historical context (52-week high/low)
   - Fundamental data (P/E, market cap)
   - News and analyst recommendations
   - Earnings calendar

**Example Workflow:**
```
User: "What's the price of AAPL?"

CORRECT:
1. get_questrade_quotes(["AAPL"]) → $233.31 (real-time, bid $233.30, ask $233.50)
2. Report: "AAPL is trading at $233.31 with bid/ask $233.30/$233.50"

WRONG:
1. get_ticker_data("AAPL") → $239.12 (previous close, delayed)
2. Report: "AAPL is $239.12" (STALE DATA - could be hours old!)
```

## Questrade API Setup (CRITICAL)

**⚠️ IMPORTANT:** Questrade API requires special configuration to work. If you encounter `HTTP Error 403: Forbidden`, see `QUESTRADE_SETUP.md` immediately.

### Automatic Troubleshooting Protocol

When Questrade API fails, follow this protocol **WITHOUT asking the user to manually fix it**:

#### Error: HTTP 400 (Bad Request)

**Cause:** Refresh token has been consumed (single-use token is dead)

**AUTO-FIX STEPS:**

1. Tell user: "Questrade token expired. I'll guide you through the refresh."
2. Instruct user to generate a new token at <https://login.questrade.com/APIAccess/UserApps.aspx>
3. Once user provides new token, execute the update commands (see "How to Fix Token Issues" above).

#### Error: HTTP 403 (Forbidden)

**Cause:** Cloudflare blocking (missing User-Agent header)

**AUTO-FIX STEPS:**

1. Check if monkey-patch exists:
   ```bash
   docker exec investor-agent-mcp grep -A 5 "_urlopen_with_user_agent" /app/investor_agent/questrade.py
   ```
2. If missing, rebuild container:
   ```bash
   bash /Users/AhmedE/git/investor-agent/rebuild.sh
   ```

#### Fallback to Yahoo Finance

**When MCP tools return `data_source: "YAHOO_FINANCE"`:**

**MANDATORY DISCLOSURE:**
- **ALWAYS state clearly:** "Using Yahoo Finance data (delayed 15-20 min) - Questrade unavailable"
- **Label all prices:** "Price: $249.53 (Yahoo Finance, may be stale)"

## Critical Principle: Intellectual Honesty

- If you lack data, admit it.
- If analysis is unclear, state it.
- NEVER guess or speculate about market data.