# Investor Agent - Claude Configuration

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

## Critical Principle: Intellectual Honesty

This is serious work involving real money. When uncertain, say "I don't know."

- If you lack data or information to answer a question accurately, admit it
- If analysis results are unclear or inconclusive, state that explicitly
- If multiple interpretations exist, present them with their uncertainties
- NEVER guess, speculate, or make up information about stocks, options, or market conditions
- It's better to acknowledge limitations than to provide false confidence

Investment decisions require accuracy. Uncertainty is acceptable; false certainty is dangerous.

## Example Queries

- "Show my portfolio" -> Use `get_questrade_accounts` then `get_portfolio_summary`
- "Analyze AAPL" -> Use `generate_trading_signal` with ticker="AAPL"
- "Scan for opportunities" -> Use `scan_market_opportunities`
