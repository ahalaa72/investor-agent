[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/ferdousbhai-investor-agent-badge.png)](https://mseep.ai/app/ferdousbhai-investor-agent)

[![Trust Score](https://archestra.ai/mcp-catalog/api/badge/quality/ferdousbhai/investor-agent)](https://archestra.ai/mcp-catalog/ferdousbhai__investor-agent)

# investor-agent: A Financial Analysis MCP Server

## Overview

The **investor-agent** is a Model Context Protocol (MCP) server that provides comprehensive financial insights and analysis to Large Language Models. It leverages real-time market data, fundamental and technical analysis to deliver:

- **Market Movers:** Top gainers, losers, and most active stocks with support for different market sessions
- **Ticker Analysis:** Company overview, news, metrics, analyst recommendations, and upgrades/downgrades
- **Options Data:** Filtered options chains with customizable parameters
- **Historical Data:** Price trends and earnings history
- **Financial Statements:** Income, balance sheet, and cash flow statements
- **Ownership Analysis:** Institutional holders and insider trading activity
- **Earnings Calendar:** Upcoming earnings announcements with date filtering
- **Market Sentiment:** CNN Fear & Greed Index, Crypto Fear & Greed Index, and Google Trends sentiment analysis
- **Technical Analysis:** SMA, EMA, RSI, MACD, BBANDS indicators (optional)
- **Questrade Integration:** Account information, positions (assets), and cash balances (optional)

The server integrates with [yfinance](https://pypi.org/project/yfinance/) for market data and automatically optimizes data volume for better performance.

## Architecture & Performance

**Robust Caching & Error Handling Strategy:**

1. **`yfinance[nospam]`** → Built-in smart caching + rate limiting for Yahoo Finance API
2. **`hishel`** → HTTP response caching for external APIs (CNN, crypto, earnings data)
3. **`tenacity`** → Retry logic with exponential backoff for transient failures

This multi-layered approach ensures reliable data delivery while respecting API rate limits and minimizing redundant requests.

## Prerequisites

- **Python:** 3.12 or higher
- **Package Manager:** [uv](https://docs.astral.sh/uv/). Install if needed:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Optional Dependencies

- **TA-Lib C Library:** Required for technical indicators. Follow [official installation instructions](https://ta-lib.org/install/).
- **Questrade API:** Required for Questrade account, position, and balance tools. See [Questrade API Getting Started](https://www.questrade.com/api/documentation/getting-started).

## Installation

### Quick Start

```bash
# Core features only
uvx investor-agent

# With technical indicators (requires TA-Lib)
uvx "investor-agent[ta]"

# With Questrade integration
uvx "investor-agent[questrade]"

# With all optional features
uvx "investor-agent[ta,questrade]"

```

### Questrade Setup

To use Questrade features, you need to:

1. Install with Questrade support: `uvx "investor-agent[questrade]"` or `uv pip install "investor-agent[questrade]"`
2. Generate a refresh token from [Questrade API Portal](https://www.questrade.com/api/)
3. Set the environment variable:
   ```bash
   export QUESTRADE_REFRESH_TOKEN="your_refresh_token_here"
   ```

## Tools

### Market Data
- **`get_market_movers(category="most-active", count=25, market_session="regular")`** - Market movers data including top gainers, losers, or most active stocks. Supports different market sessions (regular/pre-market/after-hours) for most-active category. Returns up to 100 stocks with cleaned percentage changes, volume, and market cap data
- **`get_ticker_data(ticker, max_news=5, max_recommendations=5, max_upgrades=5)`** - Comprehensive ticker report with essential field filtering and configurable limits for news, analyst recommendations, and upgrades/downgrades
- **`get_options(ticker_symbol, num_options=10, start_date=None, end_date=None, strike_lower=None, strike_upper=None, option_type=None)`** - Options data with advanced filtering by date range (YYYY-MM-DD), strike price bounds, and option type (C=calls, P=puts)
- **`get_price_history(ticker, period="1mo")`** - Historical OHLCV data with intelligent interval selection: daily intervals for periods ≤1y, monthly intervals for periods ≥2y to optimize data volume
- **`get_financial_statements(ticker, statement_types=["income"], frequency="quarterly", max_periods=8)`** - Financial statements with parallel fetching support. Returns dict with statement type as key
- **`get_institutional_holders(ticker, top_n=20)`** - Major institutional and mutual fund holders data
- **`get_earnings_history(ticker, max_entries=8)`** - Historical earnings data with configurable entry limits
- **`get_insider_trades(ticker, max_trades=20)`** - Recent insider trading activity with configurable trade limits
- **`get_nasdaq_earnings_calendar(date=None, limit=100)`** - Upcoming earnings announcements using Nasdaq API (YYYY-MM-DD format, defaults to today).
- **`fetch_intraday_15m(stock, window=200)`** - Fetch 15-minute historical stock bars using Alpaca API. Returns CSV string with timestamp and close price data in EST timezone.
- **`fetch_intraday_1h(stock, window=200)`** - Fetch 1-Hour historical stock bars using Alpaca API. Returns CSV string with timestamp and close price data in EST timezone.

### Questrade Integration (Optional)

#### Account Data
- **`get_questrade_accounts()`** - Get list of all Questrade accounts for the authenticated user. Returns account type (Margin, TFSA, RRSP, etc.), account number, status, and other account details.
- **`get_questrade_positions(account_number)`** - Get all positions (holdings/assets) for a specific Questrade account. Returns detailed information including symbol, quantity, current market value, entry price, and profit/loss.
- **`get_questrade_balances(account_number, start_time=None)`** - Get cash balances and account equity for a specific Questrade account. Returns per-currency balances (CAD, USD), market value, total equity, buying power, and maintenance excess.

#### Market Data
- **`get_questrade_quote(symbol)`** - Get real-time Level 1 market quote for a single symbol. Returns bid/ask prices, volumes, last trade price, and other quote data.
- **`get_questrade_quotes(symbols)`** - Get real-time Level 1 market quotes for multiple symbols (list). Returns quote data for all requested symbols in a single call.
- **`get_questrade_candles(symbol, interval, start_time, end_time)`** - Get historical OHLCV candle data for a symbol. Intervals: OneMinute, TwoMinutes, ThreeMinutes, FourMinutes, FiveMinutes, TenMinutes, FifteenMinutes, TwentyMinutes, HalfHour, OneHour, TwoHours, FourHours, OneDay, OneWeek, OneMonth, OneYear. Times in ISO 8601 format (YYYY-MM-DDTHH:MM:SS-05:00).
- **`search_questrade_symbols(query, offset=0)`** - Search for symbols by name or description prefix. Returns matching symbols with details. Use offset for pagination.
- **`get_questrade_symbol_info(symbols)`** - Get detailed information for one or more symbols (comma-separated). Returns symbol ID, description, security type, listing exchange, currency, and trading rules.
- **`get_questrade_markets()`** - Get information about available trading markets and their current status (open/closed).

#### Orders
- **`get_questrade_orders(account_number, start_time=None, end_time=None, state_filter=None)`** - Get orders for a specific account. Filter by time range and state (All, Open, Closed). Returns order details including symbol, quantity, price, state, and timestamps.
- **`get_questrade_order(account_number, order_id)`** - Get detailed information for a specific order by order ID.

#### Historical Data
- **`get_questrade_executions(account_number, start_time=None, end_time=None)`** - Get trade executions (fills) for an account within a time range. Returns execution price, quantity, commission, and settlement details.
- **`get_questrade_activities(account_number, start_time=None, end_time=None)`** - Get account activities including deposits, withdrawals, dividends, fees, and other transactions within a time range.

#### Options
- **`get_questrade_options_chain(symbol)`** - Get the full options chain for an underlying symbol. Returns all available option expiries and strikes.
- **`get_questrade_option_quotes(option_ids)`** - Get quotes with Greeks (delta, gamma, theta, vega, rho) for specific option IDs (list of integers).

**Note:** All Questrade tools require QUESTRADE_REFRESH_TOKEN environment variable. See [Questrade Setup](#questrade-setup) for configuration details.

### Market Sentiment
- **`get_cnn_fear_greed_index(indicators=None)`** - CNN Fear & Greed Index with selective indicator filtering. Available indicators: fear_and_greed, fear_and_greed_historical, put_call_options, market_volatility_vix, market_volatility_vix_50, junk_bond_demand, safe_haven_demand
- **`get_crypto_fear_greed_index()`** - Current Crypto Fear & Greed Index with value, classification, and timestamp
- **`get_google_trends(keywords, period_days=7)`** - Google Trends relative search interest for market-related keywords. Requires a list of keywords to track (e.g., ["stock market crash", "bull market", "recession", "inflation"]). Returns relative search interest scores that can be used as sentiment indicators.

### Technical Analysis
- **`calculate_technical_indicator(ticker, indicator, period="1y", timeperiod=14, fastperiod=12, slowperiod=26, signalperiod=9, nbdev=2, matype=0, num_results=100)`** - Calculate technical indicators (SMA, EMA, RSI, MACD, BBANDS) with configurable parameters and result limiting. Returns dictionary with price_data and indicator_data as CSV strings. matype values: 0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA, 5=TRIMA, 6=KAMA, 7=MAMA, 8=T3. Requires TA-Lib library.

## Usage with MCP Clients

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "investor": {
      "command": "uvx",
      "args": ["investor-agent"]
    }
  }
}
```

## Local Testing

For local development and testing, use the included `chat.py` script:

```bash
# Install dev dependencies
uv sync --group dev

# Set up your API key
export OPENAI_API_KEY="your-api-key"  # or ANTHROPIC_API_KEY, GEMINI_API_KEY, etc.

# Optional: Set custom model (defaults to openai:gpt-5-mini)
export MODEL_IDENTIFIER="your-preferred-model"

# Run the chat interface
python chat.py
```

For available model providers and identifiers, see the [pydantic-ai documentation](https://ai.pydantic.dev/models/).

## Debugging

```bash
npx @modelcontextprotocol/inspector uvx investor-agent
```

## License

MIT License. See [LICENSE](LICENSE) file for details.
