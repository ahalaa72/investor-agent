# OI=0 Bug Analysis Report

**Date:** January 9, 2026  
**Severity:** CRITICAL - Blocks all options trading recommendations  
**Status:** ROOT CAUSE IDENTIFIED

---

## Executive Summary

The `analyze_options_mcmillan` tool consistently reports `openInterest = 0` for all strikes, causing:
- `options_allowed: false`
- `tradeable: false`  
- `"🚫 REJECT: OI 0 < 100 min"` warnings

This occurs even for TIER_1 institutional-grade stocks like NVDA that have significant options liquidity.

---

## Root Cause Analysis

### Issue 1: `to_clean_csv()` Column Removal (CONFIRMED)

**Location:** `server.py` lines 442-447

```python
def to_clean_csv(df: pd.DataFrame) -> str:
    mask = (df.notna().any() & (df != '').any() &
            ((df != 0).any() | (df.dtypes == 'object')))  # ← BUG
    return df.loc[:, mask].fillna('').to_csv(index=False)
```

**Problem:** Removes columns where ALL values are 0, including `openInterest`

**Evidence:** The `get_options` output CSV is missing `openInterest` column entirely:
```
contractSymbol,lastTradeDate,strike,lastPrice,volume,impliedVolatility,inTheMoney,contractSize,currency,expiryDate
```

### Issue 2: yfinance Data Source Quality

yfinance returns `openInterest` column, but values may be:
- All zeros for certain expirations
- Delayed/stale data
- Missing for some option contracts

### Issue 3: Questrade API OI Availability

**Location:** Line 2304 comment: "Questrade API often doesn't include openInterest in the response"

Questrade `markets_options` API (used at line 2832):
- Does return `openInterest` field
- But may return 0 or null
- Individual option quote failures silently caught (line 2865-2866)

### Data Flow Analysis

```
get_options() → yfinance → to_clean_csv() → OI column removed if all 0
                                          → CSV output missing OI

analyze_options_mcmillan():
  1. Try Questrade chain → get symbolIds
  2. Call markets_options(symbolId) → may return OI=0 or fail
  3. Fall back to yfinance → chain.calls/puts have OI=0
  4. All calculations show OI=0
  5. Liquidity filter rejects: "🚫 REJECT: OI 0 < 100 min"
```

---

## Recommended Fixes

### Fix 1: Preserve Essential Columns in CSV (Quick Fix)

```python
ESSENTIAL_OPTIONS_COLUMNS = {'openInterest', 'bid', 'ask', 'volume', 'change', 'percentChange'}

def to_clean_csv(df: pd.DataFrame, preserve_columns: set | None = None) -> str:
    """Clean DataFrame while preserving essential columns."""
    preserve = preserve_columns or set()
    
    mask = (
        (df.notna().any() & (df != '').any() & ((df != 0).any() | (df.dtypes == 'object'))) |
        df.columns.isin(preserve)
    )
    return df.loc[:, mask].fillna('').to_csv(index=False)

# Update get_options() line 2113:
return to_clean_csv(df_subset, preserve_columns=ESSENTIAL_OPTIONS_COLUMNS)
```

### Fix 2: Improve Questrade Options Data Retrieval

Current code (lines 2830-2866) fetches options one at a time. 
Batch the requests:

```python
# Collect all option IDs first
all_option_ids = []
for root in exp.get('chainPerRoot', []):
    for strike_info in root.get('chainPerStrikePrice', []):
        if strike_info.get('callSymbolId'):
            all_option_ids.append(strike_info['callSymbolId'])
        if strike_info.get('putSymbolId'):
            all_option_ids.append(strike_info['putSymbolId'])

# Batch fetch quotes (Questrade supports up to 100 IDs per call)
if all_option_ids:
    for batch in chunks(all_option_ids, 100):
        quotes = q.markets_options(optionIds=batch)
        # Process quotes...
```

### Fix 3: Add OI Validation and Fallback

```python
def get_best_oi_data(ticker: str, expiry: str) -> dict:
    """Try multiple sources to get valid OI data."""
    
    # Try Questrade first
    oi_data = get_questrade_options_oi(ticker, expiry)
    if oi_data and sum(oi_data.values()) > 0:
        return {'source': 'questrade', 'data': oi_data}
    
    # Fall back to yfinance
    chain = yf.Ticker(ticker).option_chain(expiry)
    total_oi = chain.calls['openInterest'].sum() + chain.puts['openInterest'].sum()
    if total_oi > 0:
        return {'source': 'yfinance', 'data': {...}}
    
    # Warning: No valid OI data
    return {
        'source': 'none',
        'warning': 'OI data unavailable - liquidity assessment may be inaccurate',
        'recommendation': 'Use bid/ask spread and volume as liquidity proxies'
    }
```

### Fix 4: Improve Liquidity Assessment Without OI

When OI is unavailable, use alternative metrics:

```python
def calculate_liquidity_score_v2(
    bid: float,
    ask: float,
    volume: int,
    open_interest: int,
    underlying_volume: int,
    price: float
) -> dict:
    """Calculate liquidity score with OI-unavailable fallback."""
    
    score = 0
    factors = []
    warnings = []
    tradeable = True
    
    # Spread analysis (always available)
    spread_pct = ((ask - bid) / ((ask + bid) / 2)) * 100 if ask > 0 and bid > 0 else float('inf')
    if spread_pct <= 2.0:
        score += 35
        factors.append(f"Spread {spread_pct:.1f}% ≤ 2.0%: +35")
    elif spread_pct <= 5.0:
        score += 20
        factors.append(f"Spread {spread_pct:.1f}%: +20")
    else:
        warnings.append(f"⚠️ Wide spread {spread_pct:.1f}%")
    
    # OI analysis (may be unavailable)
    if open_interest > 0:
        if open_interest >= 1000:
            score += 25
            factors.append(f"OI {open_interest:,}: +25")
        elif open_interest >= 100:
            score += 15
            factors.append(f"OI {open_interest:,}: +15")
        else:
            warnings.append(f"⚠️ Low OI ({open_interest})")
    else:
        # OI unavailable - use alternative assessment
        factors.append("OI data unavailable - using volume/spread proxy")
        if volume >= 100 and spread_pct <= 2.0:
            score += 15  # Give some credit for good spread + volume
            factors.append("Volume + tight spread proxy: +15")
        else:
            warnings.append("⚠️ Cannot verify OI - trade with caution")
    
    # Volume analysis
    if volume >= 500:
        score += 20
    elif volume >= 100:
        score += 10
    
    # Don't reject solely on OI=0 if other metrics are good
    if open_interest == 0 and spread_pct <= 2.0 and volume >= 100:
        tradeable = True
        warnings.append("ℹ️ OI=0 but spread/volume acceptable")
    
    return {
        'score': score,
        'tradeable': tradeable,
        'factors': factors,
        'warnings': warnings
    }
```

---

## Testing Plan

After implementing fixes:

1. **Test 1:** Verify `get_options` CSV includes `openInterest` column
   ```
   get_options(ticker_symbol="NVDA", num_options=10)
   # Check: openInterest column present in output
   ```

2. **Test 2:** Verify `analyze_options_mcmillan` gets valid OI
   ```
   analyze_options_mcmillan(ticker="NVDA", holding_period_days=45)
   # Check: open_interest.top_call_oi_strikes[0].openInterest > 0
   ```

3. **Test 3:** Verify `options_allowed: true` for liquid stocks
   ```
   # Should pass for: NVDA, AAPL, SPY, QQQ, TSLA
   # Check: institutional.options_allowed == true
   ```

4. **Test 4:** Verify fallback works when Questrade unavailable
   ```
   # Disable Questrade, test with yfinance only
   # Check: Still gets OI data from yfinance
   ```

---

## Priority

**CRITICAL** - Must fix before options tools are usable for real trading.

**Estimated Effort:** 2-4 hours

**Files to Modify:**
1. `server.py` - `to_clean_csv()` function
2. `server.py` - Options data retrieval in `analyze_options_mcmillan()`
3. `server.py` - Liquidity scoring function

---

## Summary

The OI=0 bug is caused by multiple issues:
1. **Primary:** `to_clean_csv()` removes columns with all-zero values
2. **Secondary:** yfinance/Questrade may return OI=0 for some options
3. **Tertiary:** Liquidity filter is too strict when OI unavailable

Fix all three for robust options analysis.
