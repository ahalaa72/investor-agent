# Investor-Agent MCP Server Usage Plan

**Last Updated:** October 25, 2025

## Overview
This document outlines the recommended approach for using the investor-agent MCP server based on available tools and market conditions.

## Alpaca API Integration (Limited)

### Available Alpaca Endpoints
The server exposes only **two Alpaca endpoints**:
- `fetch_intraday_15m` - Fetches 15-minute price bars (EST timezone)
- `fetch_intraday_1h` - Fetches 1-hour price bars (EST timezone)

### Important Notes
- **Market Hours Only**: These functions only work during trading days (Monday-Friday)
- **Weekend/After-Hours**: Will return errors when markets are closed
- **Data Format**: Returns CSV string with timestamp and close price

## Recommended Data Sources by Use Case

### 1. Weekend/After-Hours Analysis
Use these tools that work anytime:
- `get_price_history` - Historical OHLCV with smart interval selection
- `get_ticker_data` - Comprehensive metrics, calendar, news, recommendations
- `get_financial_statements` - Income, balance sheet, cash flow statements

### 2. Market Scanning & Discovery
- `get_market_movers` - Find gainers, losers, most active stocks
  - Categories: gainers, losers, most-active
  - Sessions: regular, pre-market, after-hours
- `get_nasdaq_earnings_calendar` - Upcoming earnings by date

### 3. Fundamental Analysis
Combine these for comprehensive company analysis:
- `get_ticker_data` - Key metrics, calendar events, recent news
- `get_financial_statements` - Financial performance data
- `get_institutional_holders` - Major fund holdings
- `get_insider_trades` - Insider transaction activity
- `get_earnings_history` - Past earnings performance

### 4. Options Trading Analysis
- `get_options` - Options chain data with filters
  - Filter by strike range
  - Filter by expiration dates
  - Separate calls/puts

### 5. Market Sentiment Analysis
- `get_cnn_fear_greed_index` - Overall market sentiment
- `get_crypto_fear_greed_index` - Crypto market sentiment
- `get_google_trends` - Public interest trends for keywords

### 6. Intraday Trading (Market Hours Only)
When markets are open (Mon-Fri):
- `fetch_intraday_15m` - For shorter-term analysis
- `fetch_intraday_1h` - For hourly trend analysis
- Default window: 200 bars (configurable)

## Complete Tool Reference

### Stock Data Tools (via yfinance)
```
get_ticker_data(ticker, max_news=5, max_recommendations=5, max_upgrades=5)
get_price_history(ticker, period="1mo")
get_financial_statements(ticker, statement_types=["income"], frequency="quarterly", max_periods=8)
get_options(ticker_symbol, option_type, strike_lower, strike_upper, start_date, end_date, num_options=10)
get_institutional_holders(ticker, top_n=20)
get_earnings_history(ticker, max_entries=8)
get_insider_trades(ticker, max_trades=20)
```

### Market Overview Tools
```
get_market_movers(category="most-active", market_session="regular", count=25)
get_nasdaq_earnings_calendar(date=None, limit=100)
get_cnn_fear_greed_index(indicators=None)
get_crypto_fear_greed_index()
```

### Trend Analysis
```
get_google_trends(keywords, period_days=7)
```

### Alpaca Intraday Tools
```
fetch_intraday_15m(stock, window=200)
fetch_intraday_1h(stock, window=200)
```

## Workflow Recommendations

### Daily Market Workflow
1. **Morning (Pre-Market)**
   - Check `get_market_movers` for pre-market activity
   - Review `get_nasdaq_earnings_calendar` for today's earnings
   - Check `get_cnn_fear_greed_index` for market sentiment

2. **During Market Hours**
   - Use `fetch_intraday_15m` / `fetch_intraday_1h` for active positions
   - Monitor `get_market_movers` for regular session activity

3. **After Hours / Weekend**
   - Deep dive analysis with `get_ticker_data` and `get_financial_statements`
   - Review `get_institutional_holders` and `get_insider_trades`
   - Options analysis with `get_options`

### Research Workflow
1. Screen stocks with `get_market_movers`
2. Get overview with `get_ticker_data`
3. Analyze fundamentals with `get_financial_statements`
4. Check institutional interest with `get_institutional_holders`
5. Review insider activity with `get_insider_trades`
6. Analyze options flow with `get_options` (if applicable)

## Best Practices

- **Always check market hours** before using Alpaca intraday functions
- **Combine multiple data sources** for comprehensive analysis
- **Use appropriate time periods** - shorter periods for recent data, longer for trends
- **Cache frequently accessed data** to minimize API calls
- **Monitor sentiment indicators** alongside fundamental data

## Known Limitations

- Alpaca intraday data: Only 15m and 1h bars exposed
- Weekend/holiday access: Alpaca functions will fail when markets closed
- Historical intraday: May have limited lookback period
- Rate limits: May apply depending on API tier

---

**Note**: This plan should be reviewed and updated as MCP server capabilities expand or market conditions change.
