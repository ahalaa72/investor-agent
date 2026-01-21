# Data Source Priority - Critical Update

## Problem Identified

When user asked "What's the price of AMZN?", the system used `get_ticker_data()` which returned **stale data** from Yahoo Finance (delayed 15-20 minutes). This is unacceptable for trading decisions.

## Solution

**ALWAYS prioritize Questrade API for real-time data.**

---

## Data Source Hierarchy

### 1. Real-Time Price Data (HIGHEST PRIORITY)

**Tool:** `get_questrade_quotes(symbols=["TICKER"])`

**Returns:**
- **Real-time price** (no delay)
- **Bid/Ask spread** (critical for options and entry timing)
- **Pre-market/After-hours activity**
- **Live volume and VWAP**
- **Last trade time** (verify data freshness)

**When to use:**
- ✅ User asks "What's the price of X?"
- ✅ Pre-market analysis
- ✅ Options trading (need bid/ask)
- ✅ Entry/exit timing
- ✅ Before ANY analysis that depends on current price

**Example Response:**
```
AMZN Current Price: $233.31 (Real-time)
Bid/Ask: $233.30 / $233.50
Pre-Market: $233.45 (-$5.67 from previous close)
Volume: 434,038
Last Trade: 7:48 AM ET
```

---

### 2. Fundamental Data (SECONDARY)

**Tool:** `get_ticker_data(ticker, max_news=10)`

**Returns:**
- Previous close (delayed)
- 52-week high/low
- Market cap, P/E ratio
- News headlines
- Analyst recommendations
- Earnings calendar

**When to use:**
- ✅ Historical context (52-week range)
- ✅ Fundamental metrics (P/E, market cap)
- ✅ News and catalysts
- ✅ Earnings dates

**When NOT to use:**
- ❌ Current price (15-20 min delayed)
- ❌ Pre-market analysis (no pre-market data)
- ❌ Options trading (no bid/ask spread)

---

## Updated Workflow

### Old Workflow (WRONG)
```python
# User: "What's AMZN price?"
get_ticker_data("AMZN")
# Returns: $239.12 (previous close, could be hours old)
```

### New Workflow (CORRECT)
```python
# User: "What's AMZN price?"
get_questrade_quotes(["AMZN"])
# Returns: $233.31 (live), Bid: $233.30, Ask: $233.50, Pre-market active

# Then get fundamentals if needed:
get_ticker_data("AMZN")  # For news, earnings, 52-week range
```

---

## Integration with Analysis Tools

### Full Analysis Workflow

```python
# PHASE 0: Real-Time Context (ALWAYS FIRST) ⭐
quotes = get_questrade_quotes([ticker])
current_price = quotes[0]['lastTradePrice']
bid_ask_spread = quotes[0]['askPrice'] - quotes[0]['bidPrice']
pre_market_active = quotes[0]['volume'] > 0  # Check if trading

# PHASE 1: Fundamentals (using delayed data is OK)
ticker_data = get_ticker_data(ticker)  # News, earnings, 52w range
fundamentals = calculate_fundamental_scores_tool(ticker)

# PHASE 2-9: Continue with standard workflow...
```

---

## Critical Rules

### ✅ ALWAYS

1. **Call `get_questrade_quotes()` FIRST** when user asks for price
2. **Report bid/ask spread** for options analysis
3. **Check pre-market activity** before market open
4. **Use real-time data** for entry/exit decisions
5. **Verify data source** in output: "AMZN: $233.31 (Real-time)"

### ❌ NEVER

1. **Use `get_ticker_data()` for current price** (delayed data)
2. **Report stale prices** without checking Questrade first
3. **Trade options without bid/ask spread** (need real-time quotes)
4. **Analyze pre-market without Questrade** (Yahoo doesn't have it)
5. **Assume previous close is current price** (could be hours old)

---

## Impact on Existing Tools

### Tools Updated

1. **CLAUDE.md**
   - Added `get_questrade_quotes` to Stock Analysis section
   - Added "Data Source Priority" section with examples
   - Marked `get_questrade_quotes` with ⭐ USE FIRST

2. **instructions.md**
   - Added Phase 0: Real-Time Context
   - Moved `get_questrade_quotes` to top of Core Data Tools
   - Updated MANDATORY WORKFLOW to call Questrade first
   - Added rules to ALWAYS and NEVER sections

3. **This Document (DATA_SOURCE_PRIORITY.md)**
   - New reference guide for data source hierarchy
   - Examples and workflows
   - Integration patterns

---

## Testing

### Test Cases

#### Test 1: Current Price Query
```
User: "What's the price of TSLA?"

Expected:
1. Call get_questrade_quotes(["TSLA"])
2. Report real-time price with bid/ask
3. If pre-market/after-hours, mention that

NOT Expected:
1. Call get_ticker_data("TSLA") first
2. Report previous close as "current price"
```

#### Test 2: Full Analysis
```
User: "Analyze META"

Expected:
1. get_questrade_quotes(["META"]) - Real-time price
2. get_ticker_data("META") - Fundamentals
3. Continue with phases 2-9

NOT Expected:
1. Skip real-time quote
2. Use previous close for analysis
```

#### Test 3: Pre-Market Analysis
```
User: "What's NVDA doing pre-market?"

Expected:
1. get_questrade_quotes(["NVDA"])
2. Report pre-market activity: volume, last trade time, change
3. Mention if pre-market is active or not

NOT Expected:
1. Use get_ticker_data (no pre-market data)
2. Report "not available" without checking Questrade
```

---

## Benefits

1. **Real-time data** for accurate trading decisions
2. **Pre-market/After-hours visibility** for overnight moves
3. **Bid/Ask spreads** critical for options trading
4. **Live volume tracking** for intraday momentum
5. **No stale data** reported to users

---

## Implementation Status

- ✅ CLAUDE.md updated
- ✅ instructions.md updated
- ✅ DATA_SOURCE_PRIORITY.md created
- ⏳ Pending: Update all report generators to use Questrade first
- ⏳ Pending: Add Questrade check to generate_trading_signal()

---

## Next Steps

1. **Test the workflow** with next user query
2. **Update report templates** to include real-time data section
3. **Add Questrade health check** (verify API is accessible)
4. **Create fallback logic** if Questrade unavailable (use Yahoo but warn user)

---

**Last Updated:** January 20, 2026
**Impact:** CRITICAL - affects all price queries and analysis workflows
