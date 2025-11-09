# Training Guide for Perplexity Desktop: Questrade Tools

## 🎯 PASTE THIS ENTIRE GUIDE INTO PERPLEXITY DESKTOP

Copy everything below and paste it at the start of your Perplexity conversation.

---

# QUESTRADE TOOLS TRAINING

I have access to 15 Questrade brokerage tools through the investor-agent MCP server. Here's how to use them:

## 📋 AVAILABLE TOOLS

### 1. Account Management

**get_questrade_accounts()**
- Returns: List of all Questrade accounts
- Parameters: None
- Example: `get_questrade_accounts()`

**get_questrade_positions(account_number)**
- Returns: Current holdings with P&L
- Parameters: account_number (string)
- Example: `get_questrade_positions(account_number="12345678")`

**get_questrade_balances(account_number)**
- Returns: Cash, buying power, total equity
- Parameters: account_number (string)
- Example: `get_questrade_balances(account_number="12345678")`

### 2. Market Data

**get_questrade_quote(symbol)**
- Returns: Real-time quote for single symbol
- Parameters: symbol (string)
- Example: `get_questrade_quote(symbol="AAPL")`

**get_questrade_quotes(symbols)**
- Returns: Quotes for multiple symbols (EFFICIENT - use this for multiple!)
- Parameters: symbols (list of strings)
- Example: `get_questrade_quotes(symbols=["AAPL", "MSFT", "GOOGL"])`

**get_questrade_candles(symbol, interval, start_time, end_time)**
- Returns: Historical OHLCV data
- Parameters:
  - symbol (string)
  - interval (string): "OneDay", "OneHour", "FifteenMinutes", etc.
  - start_time (string): ISO 8601 format with timezone
  - end_time (string): ISO 8601 format with timezone
- Example:
  ```
  get_questrade_candles(
      symbol="TSLA",
      interval="OneDay",
      start_time="2025-11-01T00:00:00-05:00",
      end_time="2025-11-30T23:59:59-05:00"
  )
  ```

**get_questrade_search_symbols(prefix, offset)**
- Returns: Symbols matching prefix
- Parameters: prefix (string), offset (integer, usually 0)
- Example: `get_questrade_search_symbols(prefix="AAPL", offset=0)`

**get_questrade_symbol_info(symbol)**
- Returns: Symbol details, exchange, currency
- Parameters: symbol (string)
- Example: `get_questrade_symbol_info(symbol="AAPL")`

**get_questrade_markets()**
- Returns: Available markets/exchanges
- Parameters: None
- Example: `get_questrade_markets()`

### 3. Orders & Trading History

**get_questrade_orders(account_number, state_filter, start_time, end_time)**
- Returns: Order history
- Parameters:
  - account_number (string, required)
  - state_filter (string, optional): "Open", "Closed", "All"
  - start_time (string, optional): ISO 8601 format
  - end_time (string, optional): ISO 8601 format
- Default: Last 30 days if no dates
- Example:
  ```
  get_questrade_orders(
      account_number="12345678",
      state_filter="Closed",
      start_time="2025-11-01T00:00:00-05:00",
      end_time="2025-11-30T23:59:59-05:00"
  )
  ```

**get_questrade_order(account_number, order_id)**
- Returns: Specific order details
- Parameters: account_number (string), order_id (string)
- Example: `get_questrade_order(account_number="12345678", order_id="987654")`

**get_questrade_executions(account_number, start_time, end_time)**
- Returns: Trade executions with commissions
- Parameters:
  - account_number (string, required)
  - start_time (string, optional)
  - end_time (string, optional)
- Default: Last 90 days if no dates
- ⚠️ IMPORTANT: For heavy traders (100+ trades/month), use MONTHLY ranges!
- Example:
  ```
  get_questrade_executions(
      account_number="12345678",
      start_time="2025-11-01T00:00:00-05:00",
      end_time="2025-11-30T23:59:59-05:00"
  )
  ```

**get_questrade_activities(account_number, start_time, end_time)**
- Returns: Deposits, withdrawals, dividends, fees
- Parameters:
  - account_number (string, required)
  - start_time (string, optional)
  - end_time (string, optional)
- Default: Last 30 days if no dates
- ⚠️ IMPORTANT: For heavy traders, use MONTHLY ranges!
- Example:
  ```
  get_questrade_activities(
      account_number="12345678",
      start_time="2025-11-01T00:00:00-05:00",
      end_time="2025-11-30T23:59:59-05:00"
  )
  ```

### 4. Options

**get_questrade_options_chain(symbol)**
- Returns: Available option contracts
- Parameters: symbol (string)
- Example: `get_questrade_options_chain(symbol="AAPL")`

**get_questrade_option_quotes(option_ids, filters)**
- Returns: Option prices with Greeks
- Parameters:
  - option_ids (list of integers)
  - filters (list of strings): ["delta", "gamma", "theta", "vega"]
- Example:
  ```
  get_questrade_option_quotes(
      option_ids=[12345, 12346],
      filters=["delta", "gamma", "theta", "vega"]
  )
  ```

---

## 🚨 CRITICAL RULES

### Date Format (MUST USE THIS)
Always use ISO 8601 with Eastern Time zone:
- Format: `YYYY-MM-DDTHH:MM:SS-05:00`
- Start of day: `2025-11-01T00:00:00-05:00`
- End of day: `2025-11-30T23:59:59-05:00`

### Default Date Ranges
- get_questrade_orders: Last 30 days
- get_questrade_executions: Last 90 days
- get_questrade_activities: Last 30 days

### Heavy Traders (100+ trades/month)
Use MONTHLY date ranges to avoid error 1003 ("Argument length exceeds imposed limit")

**Pattern:**
```
For January:
get_questrade_executions(
    account_number="12345678",
    start_time="2025-01-01T00:00:00-05:00",
    end_time="2025-01-31T23:59:59-05:00"
)

For February:
get_questrade_executions(
    account_number="12345678",
    start_time="2025-02-01T00:00:00-05:00",
    end_time="2025-02-28T23:59:59-05:00"
)

... repeat for each month, then combine results
```

### Efficiency Tips
- Use `get_questrade_quotes(symbols=[list])` for multiple symbols (NOT multiple single quote calls)
- Get account number first with `get_questrade_accounts()`
- Cache account numbers - don't query repeatedly

---

## 📋 COMMON WORKFLOWS

### Workflow 1: Account Overview
```
Step 1: Get all accounts
accounts = get_questrade_accounts()

Step 2: For each account, get balances and positions
for account in accounts:
    balances = get_questrade_balances(account_number=account['number'])
    positions = get_questrade_positions(account_number=account['number'])
```

### Workflow 2: Position Analysis
```
Step 1: Get positions
positions = get_questrade_positions(account_number="12345678")

Step 2: Extract symbols
symbols = [position['symbol'] for position in positions]

Step 3: Get current quotes (BATCH - efficient!)
quotes = get_questrade_quotes(symbols=symbols)

Step 4: Calculate P&L for each position
Compare position['entry_price'] to current quote price
```

### Workflow 3: Trading Performance (Heavy Trader)
```
Step 1: Define monthly date ranges
months = [
    ("2025-01-01T00:00:00-05:00", "2025-01-31T23:59:59-05:00"),
    ("2025-02-01T00:00:00-05:00", "2025-02-28T23:59:59-05:00"),
    ... continue for each month
]

Step 2: For each month, get data
all_executions = []
all_activities = []
for start, end in months:
    executions = get_questrade_executions(
        account_number="12345678",
        start_time=start,
        end_time=end
    )
    activities = get_questrade_activities(
        account_number="12345678",
        start_time=start,
        end_time=end
    )
    all_executions.extend(executions)
    all_activities.extend(activities)

Step 3: Calculate metrics
- Total P&L
- Win rate
- Commissions paid
- Best/worst trades
```

### Workflow 4: Dividend Tracking
```
Step 1: Get full year activities
activities = get_questrade_activities(
    account_number="12345678",
    start_time="2025-01-01T00:00:00-05:00",
    end_time="2025-12-31T23:59:59-05:00"
)

Step 2: Filter for dividends
dividends = [a for a in activities if a['type'] == 'Dividends']

Step 3: Summarize
Group by symbol, sum amounts, calculate monthly totals
```

---

## ✅ EXAMPLE QUERIES YOU CAN HANDLE NOW

When the user asks:
- "Show me my Questrade accounts"
  → Call `get_questrade_accounts()`

- "What are my current positions?"
  → Call `get_questrade_accounts()` first to get account number
  → Then call `get_questrade_positions(account_number=...)`

- "What's my cash balance?"
  → Call `get_questrade_balances(account_number=...)`

- "Get quotes for AAPL, MSFT, and GOOGL"
  → Call `get_questrade_quotes(symbols=["AAPL", "MSFT", "GOOGL"])`

- "Show me all my trades from November 2025"
  → Call `get_questrade_executions(account_number=..., start_time="2025-11-01T00:00:00-05:00", end_time="2025-11-30T23:59:59-05:00")`

- "Analyze my 2025 trading performance"
  → Use month-by-month workflow
  → Get executions and activities for each month
  → Combine and analyze

---

## 🎯 NOW YOU KNOW HOW TO USE QUESTRADE TOOLS

When the user asks Questrade-related questions:
1. Identify which tool(s) to use
2. Use correct parameter formats (especially dates!)
3. For heavy traders, use monthly iteration
4. Batch multiple symbols with get_questrade_quotes()
5. Always get account_number from get_questrade_accounts() first

You have everything you need to handle Questrade queries now!
