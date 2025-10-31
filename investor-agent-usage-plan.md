# Investor Agent Usage Plan

## Overview
This document provides a comprehensive guide for using the investor-agent MCP server tools, organized by use case and workflow. Updated with all available tools including technical analysis capabilities.

**Last Updated:** October 31, 2025

---

## Table of Contents
1. [Market Overview & Sentiment](#market-overview--sentiment)
2. [Stock Research & Analysis](#stock-research--analysis)
3. [Technical Analysis](#technical-analysis)
4. [Options Trading](#options-trading)
5. [Earnings & Events](#earnings--events)
6. [Intraday Trading](#intraday-trading)
7. [Common Workflows](#common-workflows)

---

## Market Overview & Sentiment

### Quick Market Pulse
**Tools:** `get_market_movers`, `get_cnn_fear_greed_index`, `get_crypto_fear_greed_index`

**Workflow:**
```
1. get_market_movers(category="gainers", count=10)
2. get_market_movers(category="losers", count=10)
3. get_market_movers(category="most-active", count=25)
4. get_cnn_fear_greed_index()
```

**Use Case:** Start your trading day with a quick overview of market conditions, sentiment, and major movers.

---

### Tracking Public Interest
**Tool:** `get_google_trends`

**Example:**
```
get_google_trends(
    keywords=["Tesla", "TSLA stock", "electric vehicles"],
    period_days=30
)
```

**Use Case:** Gauge retail investor interest and public sentiment around specific stocks or sectors.

---

## Stock Research & Analysis

### Comprehensive Stock Overview
**Tool:** `get_ticker_data`

**Example:**
```
get_ticker_data(
    ticker="AAPL",
    max_news=10,
    max_recommendations=10,
    max_upgrades=5
)
```

**Returns:**
- Key metrics (P/E, market cap, etc.)
- Recent news
- Analyst recommendations
- Upgrades/downgrades
- Calendar events

---

### Fundamental Analysis Workflow
**Tools:** `get_ticker_data`, `get_financial_statements`, `get_institutional_holders`, `get_earnings_history`

**Workflow:**
```
1. get_ticker_data(ticker="MSFT")
2. get_financial_statements(
       ticker="MSFT",
       statement_types=["income", "balance", "cash"],
       frequency="quarterly",
       max_periods=8
   )
3. get_institutional_holders(ticker="MSFT", top_n=20)
4. get_earnings_history(ticker="MSFT", max_entries=8)
```

**Use Case:** Deep dive into a company's financial health, ownership structure, and earnings trends.

---

### Historical Price Analysis
**Tool:** `get_price_history`

**Examples:**
```
# Short-term: 1 month
get_price_history(ticker="GOOGL", period="1mo")

# Long-term: 5 years
get_price_history(ticker="GOOGL", period="5y")

# Year-to-date
get_price_history(ticker="GOOGL", period="ytd")
```

**Available Periods:** "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"

---

### Insider Activity Monitoring
**Tool:** `get_insider_trades`

**Example:**
```
get_insider_trades(ticker="NVDA", max_trades=20)
```

**Use Case:** Track insider buying/selling to gauge management confidence in the company.

---

## Technical Analysis

### Comprehensive Technical Analysis
**Tool:** `analyze_technical` ⭐ NEW

**Example:**
```
analyze_technical(ticker="AAPL", period="6mo")
```

**Returns:**
- RSI (Relative Strength Index) with overbought/oversold signals
- MACD (Moving Average Convergence Divergence) with trend analysis
- Bollinger Bands with price position
- Multiple Moving Averages (SMA 20/50/200, EMA 20)
- Stochastic Oscillator

**Available Periods:** "3mo", "6mo", "1y", "2y"

**Use Case:** Get a complete technical picture of a stock's momentum, trend, and potential reversal points.

---

### Support & Resistance Levels
**Tool:** `find_support_resistance` ⭐ NEW

**Example:**
```
find_support_resistance(
    ticker="TSLA",
    lookback_period="3mo"
)
```

**Returns:**
- Top 3 resistance levels (price ceilings)
- Top 3 support levels (price floors)
- Nearest support and resistance to current price

**Available Lookback Periods:** "1mo", "3mo", "6mo"

**Use Case:** Identify key price levels for entry/exit points and stop-loss placement.

---

### Stock Screening by Technical Criteria
**Tool:** `screen_stocks_technical` ⭐ NEW

**Example 1 - Find Oversold Stocks:**
```
screen_stocks_technical(
    tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    rsi_below=30,
    above_sma50=True
)
```

**Example 2 - Find Overbought Stocks:**
```
screen_stocks_technical(
    tickers=["TSLA", "NVDA", "AMD", "NFLX"],
    rsi_above=70,
    macd_bullish=True
)
```

**Criteria Options:**
- `rsi_below`: RSI below this value (e.g., 30 for oversold)
- `rsi_above`: RSI above this value (e.g., 70 for overbought)
- `above_sma50`: Trading above 50-day moving average
- `macd_bullish`: Bullish MACD crossover

**Use Case:** Screen multiple stocks at once to find those meeting specific technical criteria.

---

### Compare Technical Indicators Across Stocks
**Tool:** `compare_technical` ⭐ NEW

**Example:**
```
compare_technical(
    tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    period="3mo"
)
```

**Returns comparison table with:**
- Current price
- RSI value and signal
- MACD trend
- Moving average trend
- Bollinger Bands position

**Available Periods:** "1mo", "3mo", "6mo"

**Use Case:** Quickly compare technical health across multiple stocks to identify best opportunities.

---

### Analyze Trend Strength & Momentum
**Tool:** `analyze_trend_strength` ⭐ NEW

**Example:**
```
analyze_trend_strength(ticker="NVDA", period="6mo")
```

**Returns:**
- **Trend strength score (0-100)** based on:
  - RSI momentum (25 points)
  - MACD trend direction (25 points)
  - Price vs moving averages (30 points)
  - Bollinger Bands position (20 points)
- Overall assessment (Strong Bullish, Moderate Bullish, Weak, Bearish)
- Detailed analysis points
- Full indicator breakdown

**Available Periods:** "3mo", "6mo", "1y"

**Use Case:** Quantify how strong a trend is and determine conviction level for entering a trade.

---

### Detect Chart Patterns
**Tool:** `detect_chart_patterns` ⭐ NEW

**Example:**
```
detect_chart_patterns(ticker="TSLA", period="3mo")
```

**Identifies:**
- **Golden Cross** (50-day MA crosses above 200-day MA) - Bullish
- **Death Cross** (50-day MA crosses below 200-day MA) - Bearish
- **Strong uptrends** (consistent upward movement)
- **Strong downtrends** (consistent downward movement)
- **Consolidation patterns** (low volatility, sideways movement)

**Available Periods:** "1mo", "3mo", "6mo", "1y"

**Use Case:** Automatically identify significant chart patterns and potential trend changes.

---

## Options Trading

### Options Chain Analysis
**Tool:** `get_options`

**Example 1 - All Near-the-Money Calls:**
```
get_options(
    ticker_symbol="SPY",
    option_type="C",
    strike_lower=550,
    strike_upper=600,
    num_options=20
)
```

**Example 2 - Puts Expiring in a Date Range:**
```
get_options(
    ticker_symbol="AAPL",
    option_type="P",
    start_date="2025-11-15",
    end_date="2025-12-20",
    num_options=15
)
```

**Use Case:** Analyze options chains for specific strikes and expirations to plan options strategies.

---

## Earnings & Events

### Earnings Calendar Tracking
**Tool:** `get_nasdaq_earnings_calendar`

**Example:**
```
# Today's earnings
get_nasdaq_earnings_calendar()

# Specific date
get_nasdaq_earnings_calendar(date="2025-11-15", limit=50)
```

**Returns:** CSV with Date, Symbol, Company Name, EPS, % Surprise, Market Cap

**Note:** Single date per call - loop for date ranges

**Use Case:** Plan trades around earnings announcements, identify potential volatility events.

---

### Historical Earnings Analysis
**Tool:** `get_earnings_history`

**Example:**
```
get_earnings_history(ticker="NFLX", max_entries=12)
```

**Use Case:** Analyze historical earnings beat/miss patterns to predict earnings reactions.

---

## Intraday Trading

### 15-Minute Bar Data
**Tool:** `fetch_intraday_15m`

**Example:**
```
fetch_intraday_15m(stock="TSLA", window=200)
```

**Returns:** CSV with timestamp and close price (EST timezone)

**Use Case:** Intraday analysis, day trading strategies, short-term momentum.

**Note:** Only works during market hours (Monday-Friday).

---

### 1-Hour Bar Data
**Tool:** `fetch_intraday_1h`

**Example:**
```
fetch_intraday_1h(stock="AAPL", window=200)
```

**Returns:** CSV with timestamp and close price (EST timezone)

**Use Case:** Intraday swing trading, hourly trend analysis.

**Note:** Only works during market hours (Monday-Friday).

---

## Common Workflows

### 1. Daily Market Routine

```
Morning Routine:
1. get_cnn_fear_greed_index() - Check market sentiment
2. get_market_movers(category="gainers", count=10)
3. get_market_movers(category="losers", count=10)
4. get_nasdaq_earnings_calendar() - Today's earnings
5. Review watchlist with compare_technical()
```

---

### 2. New Stock Research Workflow

```
Complete Analysis for Stock XYZ:

Step 1: Overview
- get_ticker_data(ticker="XYZ", max_news=10)

Step 2: Fundamentals
- get_financial_statements(ticker="XYZ", statement_types=["income", "balance", "cash"])
- get_institutional_holders(ticker="XYZ", top_n=20)
- get_earnings_history(ticker="XYZ")

Step 3: Technical Analysis
- analyze_technical(ticker="XYZ", period="6mo")
- find_support_resistance(ticker="XYZ", lookback_period="3mo")
- analyze_trend_strength(ticker="XYZ", period="6mo")
- detect_chart_patterns(ticker="XYZ", period="3mo")

Step 4: Additional Checks
- get_insider_trades(ticker="XYZ", max_trades=20)
- get_google_trends(keywords=["XYZ", "XYZ stock"], period_days=30)
```

---

### 3. Sector Rotation Strategy

```
Compare Leading Stocks in a Sector:

1. Define sector tickers (e.g., Tech: AAPL, MSFT, GOOGL, NVDA, META)

2. compare_technical(
       tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
       period="3mo"
   )

3. For each strong stock:
   - analyze_trend_strength()
   - find_support_resistance()

4. Rank by technical strength scores
```

---

### 4. Options Strategy Setup

```
Covered Call Strategy on Stock XYZ:

1. get_ticker_data(ticker="XYZ") - Current price and metrics

2. analyze_technical(ticker="XYZ", period="3mo") - Trend confirmation

3. find_support_resistance(ticker="XYZ") - Identify resistance for strike

4. get_options(
       ticker_symbol="XYZ",
       option_type="C",
       strike_lower=<current_price>,
       strike_upper=<resistance_level>
   )

5. Review options chain for optimal strike and premium
```

---

### 5. Swing Trading Setup

```
Finding Swing Trade Opportunities:

1. screen_stocks_technical(
       tickers=<watchlist>,
       rsi_below=35,  # Oversold but not extreme
       above_sma50=True  # Still in uptrend
   )

2. For each filtered stock:
   - detect_chart_patterns() - Look for bullish patterns
   - find_support_resistance() - Entry at support
   - analyze_trend_strength() - Confirm overall trend

3. Set alerts at support levels for entry
```

---

### 6. Earnings Play Strategy

```
Pre-Earnings Analysis:

1. get_nasdaq_earnings_calendar(date="<target_date>")

2. For each ticker:
   - get_earnings_history() - Historical beat/miss pattern
   - analyze_technical() - Current technical setup
   - get_options() - IV and option pricing
   - get_institutional_holders() - Smart money positioning

3. Identify stocks with:
   - Strong earnings history
   - Bullish technical setup
   - Reasonable option premiums
```

---

### 7. Momentum Screening

```
Finding High Momentum Stocks:

1. get_market_movers(category="gainers", count=50)

2. screen_stocks_technical(
       tickers=<top_gainers>,
       macd_bullish=True,
       above_sma50=True
   )

3. For top results:
   - analyze_trend_strength() - Quantify momentum
   - get_price_history(period="3mo") - Confirm trend
   - find_support_resistance() - Risk management levels
   - get_google_trends() - Retail interest confirmation
```

---

### 8. Reversal Hunting

```
Finding Potential Reversals:

1. get_market_movers(category="losers", count=50)

2. screen_stocks_technical(
       tickers=<top_losers>,
       rsi_below=30,  # Oversold
       macd_bullish=True  # Starting to turn
   )

3. For candidates:
   - detect_chart_patterns() - Look for bottoming patterns
   - find_support_resistance() - Confirm at strong support
   - get_insider_trades() - Check for insider buying
   - get_institutional_holders() - Strong hands holding?
```

---

## Tool Categories Summary

### Market Sentiment (4 tools)
- get_market_movers
- get_cnn_fear_greed_index
- get_crypto_fear_greed_index
- get_google_trends

### Fundamental Data (6 tools)
- get_ticker_data
- get_financial_statements
- get_institutional_holders
- get_earnings_history
- get_insider_trades
- get_nasdaq_earnings_calendar

### Technical Analysis (6 tools) ⭐ NEW
- analyze_technical
- find_support_resistance
- screen_stocks_technical
- compare_technical
- analyze_trend_strength
- detect_chart_patterns

### Price Data (3 tools)
- get_price_history
- fetch_intraday_15m
- fetch_intraday_1h

### Options (1 tool)
- get_options

---

## Best Practices

1. **Start Broad, Then Narrow:** Begin with market overview, then sector analysis, then individual stocks

2. **Combine Technical + Fundamental:** Use technical tools for timing, fundamental tools for conviction

3. **Multiple Timeframes:** Check both long-term trends (6mo-1y) and short-term setups (1mo-3mo)

4. **Confirm Signals:** Don't rely on one indicator - use multiple tools to confirm thesis

5. **Risk Management:** Always use find_support_resistance() to identify stop-loss levels

6. **Monitor Sentiment:** Track Google Trends and Fear/Greed for contrarian signals

7. **Track Smart Money:** Use institutional holders and insider trades for conviction

8. **Screen First:** Use screening tools to filter large universes before deep analysis

---

## Quick Reference: Tool Selection by Question

**"What's the market doing today?"**
→ get_market_movers, get_cnn_fear_greed_index

**"Should I buy stock XYZ?"**
→ get_ticker_data, analyze_technical, find_support_resistance, get_financial_statements

**"What stocks are oversold right now?"**
→ screen_stocks_technical (rsi_below=30)

**"Where should I place my stop-loss?"**
→ find_support_resistance

**"Is this stock trending strongly?"**
→ analyze_trend_strength, detect_chart_patterns

**"What earnings are coming up?"**
→ get_nasdaq_earnings_calendar

**"Who's buying this stock?"**
→ get_institutional_holders, get_insider_trades

**"What options should I trade?"**
→ get_options, analyze_technical

**"Is retail interested in this stock?"**
→ get_google_trends

**"How does XYZ compare to its peers?"**
→ compare_technical

---

## New Technical Analysis Tools (Added October 2025)

The investor-agent now includes 6 powerful technical analysis tools that provide:

✅ **Comprehensive indicators** (RSI, MACD, Bollinger Bands, Moving Averages, Stochastic)
✅ **Support/resistance identification** 
✅ **Multi-stock screening** by technical criteria
✅ **Side-by-side comparison** of stocks
✅ **Quantified trend strength** scoring
✅ **Automated pattern detection** (Golden Cross, Death Cross, etc.)

These tools enable fully automated technical analysis workflows without manual charting.

---

## Known Limitations

- **Alpaca intraday data:** Only 15m and 1h bars exposed
- **Weekend/holiday access:** Alpaca functions will fail when markets closed
- **Historical intraday:** May have limited lookback period
- **Rate limits:** May apply depending on API tier
- **Technical Analysis:** Pure Python implementations (no TA-Lib dependency for advanced tools)

---

## Total Available Tools: 16

**4** Market Sentiment Tools  
**6** Fundamental Data Tools  
**6** Technical Analysis Tools (NEW)  
**3** Price Data Tools  
**1** Options Tool  

---

**Version:** 2.0  
**Last Updated:** October 31, 2025  
**Major Update:** Added 6 technical analysis tools
