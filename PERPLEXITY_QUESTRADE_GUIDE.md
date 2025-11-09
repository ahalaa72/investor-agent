# Questrade Tools Quick Start Guide for AI Assistants

## 🏦 Available Questrade Tools (15 Total)

Copy this guide into your AI assistant to help it understand how to use Questrade brokerage tools.

---

## 📋 ACCOUNT & PORTFOLIO (3 tools)

### 1. Get All Accounts
```
Tool: get_questrade_accounts()
Returns: List of all your Questrade accounts (TFSA, RRSP, Margin, Cash)
Example usage: "Get my Questrade accounts"
```

### 2. Get Positions (Holdings)
```
Tool: get_questrade_positions(account_number="12345678")
Returns: Current holdings with unrealized P&L
Example usage: "Show me my positions in account 12345678"
```

### 3. Get Balances
```
Tool: get_questrade_balances(account_number="12345678")
Returns: Cash balances, buying power, total equity
Example usage: "What's my cash balance in account 12345678"
```

---

## 📊 MARKET DATA (6 tools)

### 4. Get Single Quote
```
Tool: get_questrade_quote(symbol="AAPL")
Returns: Real-time quote with bid/ask, volume
Example usage: "What's the current price of AAPL"
```

### 5. Get Multiple Quotes (Efficient!)
```
Tool: get_questrade_quotes(symbols=["AAPL", "MSFT", "GOOGL"])
Returns: Multiple quotes in one call
Example usage: "Get quotes for AAPL, MSFT, and GOOGL"
Pro tip: Use this instead of calling get_questrade_quote multiple times
```

### 6. Get Historical Candles
```
Tool: get_questrade_candles(
    symbol="TSLA",
    interval="OneDay",
    start_time="2025-11-01T00:00:00-05:00",
    end_time="2025-11-09T23:59:59-05:00"
)
Returns: OHLCV historical data
Intervals: OneMinute, FiveMinutes, FifteenMinutes, ThirtyMinutes, OneHour, OneDay, OneWeek, OneMonth
Example usage: "Get daily candles for TSLA for the last month"
```

### 7. Search Symbols
```
Tool: get_questrade_search_symbols(prefix="AAPL", offset=0)
Returns: Symbols matching the prefix
Example usage: "Search for symbols starting with TD"
```

### 8. Get Symbol Info
```
Tool: get_questrade_symbol_info(symbol="AAPL")
Returns: Symbol details, exchange, currency, status
Example usage: "Get details for AAPL"
```

### 9. Get Markets
```
Tool: get_questrade_markets()
Returns: Available markets/exchanges
Example usage: "What markets can I trade on Questrade"
```

---

## 📈 ORDERS & TRADING HISTORY (4 tools)

### 10. Get Orders
```
Tool: get_questrade_orders(
    account_number="12345678",
    state_filter="Open",  # or "Closed" or "All"
    start_time="2025-11-01T00:00:00-05:00",
    end_time="2025-11-09T23:59:59-05:00"
)
Returns: Order history with filters
Default: Last 30 days if no dates specified
Example usage: "Show me all open orders in account 12345678"
```

### 11. Get Specific Order
```
Tool: get_questrade_order(account_number="12345678", order_id="987654321")
Returns: Detailed info for one order
Example usage: "Get details for order 987654321"
```

### 12. Get Trade Executions
```
Tool: get_questrade_executions(
    account_number="12345678",
    start_time="2025-11-01T00:00:00-05:00",
    end_time="2025-11-30T23:59:59-05:00"
)
Returns: Executed trades with commissions
Default: Last 90 days if no dates specified
⚠️ For heavy traders: Use month-by-month (see below)
Example usage: "Show me all trades in November 2025"
```

### 13. Get Account Activities
```
Tool: get_questrade_activities(
    account_number="12345678",
    start_time="2025-11-01T00:00:00-05:00",
    end_time="2025-11-30T23:59:59-05:00"
)
Returns: Deposits, withdrawals, dividends, fees
Default: Last 30 days if no dates specified
⚠️ For heavy traders: Use month-by-month (see below)
Example usage: "Show me dividend income in Q4 2025"
```

---

## 🎯 OPTIONS (2 tools)

### 14. Get Options Chain
```
Tool: get_questrade_options_chain(symbol="AAPL")
Returns: Available option contracts
Example usage: "Show me the options chain for AAPL"
```

### 15. Get Option Quotes
```
Tool: get_questrade_option_quotes(
    option_ids=[12345, 12346],
    filters=["delta", "gamma", "theta", "vega"]
)
Returns: Option prices with Greeks
Example usage: "Get option quotes with Greeks for option IDs 12345 and 12346"
```

---

## 🔥 CRITICAL: Month-by-Month for Heavy Traders

**Problem:** If you have 100+ trades per month, you'll get error 1003: "Argument length exceeds imposed limit"

**Solution:** Use monthly date ranges and iterate

### Pattern for Executions:
```
For January 2025:
get_questrade_executions(
    account_number="12345678",
    start_time="2025-01-01T00:00:00-05:00",
    end_time="2025-01-31T23:59:59-05:00"
)

For February 2025:
get_questrade_executions(
    account_number="12345678",
    start_time="2025-02-01T00:00:00-05:00",
    end_time="2025-02-28T23:59:59-05:00"
)

... continue for each month
```

Same pattern applies to:
- get_questrade_activities()
- get_questrade_orders()

---

## 💡 COMMON WORKFLOWS

### Workflow 1: Account Overview
```
1. get_questrade_accounts()
   → Get list of accounts

2. For each account:
   - get_questrade_balances(account_number)
   → Cash and buying power

   - get_questrade_positions(account_number)
   → Current holdings with P&L
```

### Workflow 2: Position Analysis
```
1. get_questrade_positions(account_number)
   → Get all holdings

2. Extract symbols from positions

3. get_questrade_quotes(symbols=[list_of_symbols])
   → Current market prices

4. For each position:
   - Compare entry price to current price
   - Calculate P&L %
   - Recommend hold/sell/add
```

### Workflow 3: Trading Performance (Heavy Trader - Month by Month)
```
1. Define date ranges monthly:
   Jan: 2025-01-01 to 2025-01-31
   Feb: 2025-02-01 to 2025-02-28
   ... etc

2. For each month:
   - get_questrade_executions(account, start, end)
   → Trades

   - get_questrade_activities(account, start, end)
   → Dividends, fees

   - get_questrade_orders(account, start, end)
   → Orders

3. Combine all monthly data

4. Calculate metrics:
   - Total P&L
   - Win rate
   - Commissions paid
   - Best/worst trades
```

### Workflow 4: Dividend Tracking
```
1. get_questrade_activities(
      account_number="12345678",
      start_time="2025-01-01T00:00:00-05:00",
      end_time="2025-12-31T23:59:59-05:00"
   )

2. Filter for dividend activities

3. Summarize:
   - Total dividend income
   - By symbol
   - By month
```

---

## 🚨 IMPORTANT NOTES

### Date Format (CRITICAL)
Always use: `YYYY-MM-DDTHH:MM:SS-05:00` (ISO 8601 with Eastern Time)

Examples:
- Start of day: `2025-11-01T00:00:00-05:00`
- End of day: `2025-11-30T23:59:59-05:00`

### Default Date Ranges
- get_questrade_orders: Last 30 days
- get_questrade_executions: Last 90 days
- get_questrade_activities: Last 30 days

### Response Size Limits
If you get error 1003 ("Argument length exceeds imposed limit"):
- Break into smaller time periods (monthly)
- Reduce date range to 30 days maximum
- Use month-by-month iteration pattern

### Account Numbers
- Never log or expose account numbers
- Get from get_questrade_accounts() first
- Use the correct account for each query

### Symbol Format
- Standard tickers: "AAPL", "TSLA", "MSFT"
- Canadian stocks: "TD.TO", "RY.TO"
- Use get_questrade_search_symbols() if unsure

---

## 📋 EXAMPLE PROMPTS FOR AI ASSISTANTS

### Basic Account Info
```
"Use get_questrade_accounts to show me my accounts, then get balances and
positions for each account"
```

### Position Analysis
```
"Get my Questrade positions, then for each position get the current quote
and calculate my unrealized P&L percentage"
```

### Trading History (Light Trader)
```
"Show me all my trades from November 2025 with commissions paid"
```

### Trading History (Heavy Trader)
```
"For 2025, retrieve my trading history month by month to avoid API limits.
For each month from January to November, get executions and activities,
then combine all data and calculate my total P&L, win rate, and commissions"
```

### Dividend Income
```
"Get my dividend income for all of 2025, group by symbol, and calculate
total dividends received"
```

### Portfolio Review with Market Data
```
"1. Get my current positions
2. Get current market quotes for all held symbols
3. For each position, show entry price, current price, P&L%, and quantity
4. Summarize total portfolio value and P&L"
```

---

## ✅ QUICK REFERENCE CHECKLIST

When using Questrade tools, remember:

- [ ] Use ISO 8601 date format with timezone
- [ ] Get account numbers from get_questrade_accounts() first
- [ ] Use get_questrade_quotes(symbols=[list]) for multiple symbols (efficient)
- [ ] For heavy traders: Use month-by-month iteration
- [ ] If error 1003: Reduce date range to monthly
- [ ] Default ranges: 30 days (orders/activities), 90 days (executions)
- [ ] Canadian stocks need exchange suffix (.TO)

---

## 🎯 TL;DR - Most Common Tools

**Account Info:**
- get_questrade_accounts() → List accounts
- get_questrade_positions(account_number) → Holdings
- get_questrade_balances(account_number) → Cash

**Market Data:**
- get_questrade_quotes(symbols=[list]) → Batch quotes
- get_questrade_candles(symbol, interval, start, end) → Historical data

**Trading History:**
- get_questrade_executions(account, start, end) → Trades
- get_questrade_activities(account, start, end) → Dividends/fees

**Heavy Traders:** Always use month-by-month date ranges!

---

**Copy this entire guide and paste it into your AI assistant (Perplexity, ChatGPT, Claude, etc.)
before asking Questrade-related questions. The assistant will then know how to use all 15 tools correctly!**
