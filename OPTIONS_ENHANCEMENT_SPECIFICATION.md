# Investor-Agent Options Enhancement Specification

**Version:** 1.0  
**Date:** January 9, 2026  
**Author:** Claude (AI Assistant)  
**Target:** Developer Implementation Guide  
**Timeline:** Near-Term (1-2 Weeks)  

---

## Executive Summary

This document provides detailed implementation specifications for three high-priority options trading enhancements to the investor-agent MCP server. These features will transform the current "strategy suggestions" into actionable, fully-constructed trade plans with explicit contract selections, Greeks profiles, and institutional-grade management rules.

**Features to Implement:**
1. Explicit Strategy Construction for Iron Condors and Butterflies
2. IV Skew Analysis for Sentiment Confirmation
3. 21 DTE Roll Reminder in Trade Plan Output

---

## Current State Analysis

### Existing Infrastructure

The investor-agent currently provides:

- **`analyze_options_mcmillan`**: Returns IV analysis, put/call ratio, max pain, unusual activity, Greeks assessment, and strategy suggestions (as text lists)
- **`generate_options_trade_plan`**: Generates stock-based trade plan with entry/stop/target; options plan is either "SKIP" or basic strategy name
- **`IV_STRATEGY_MATRIX`**: Defines strategy categories by IV environment (HIGH_IV_70_100, HIGH_IV_50_70, etc.)
- **`INSTITUTIONAL_OPTIONS_PARAMS`**: Contains all institutional parameters (45 DTE, 16-delta, 50% profit target, 21 DTE roll threshold)
- **Questrade Integration**: Real-time Greeks from Questrade API when available
- **Earnings Filter**: Automatically skips options within 30 days of earnings

### Current Limitations

1. **Strategies are listed, not constructed** - Output says "Iron Condor" but doesn't provide specific strikes, width, premium, or Greeks
2. **No IV skew analysis** - Put/call ratio exists but doesn't compare OTM put IV vs OTM call IV
3. **No roll reminder** - 21 DTE threshold exists in parameters but isn't surfaced in trade plan output

---

## Feature 1: Explicit Strategy Construction

### 1.1 Objective

Transform strategy suggestions into fully-constructed trade plans with:
- Specific strike prices for all legs
- Premium collected/paid
- Max profit, max loss, breakeven points
- Aggregate Greeks (Delta, Gamma, Theta, Vega)
- Probability of profit (POP)
- Risk/reward ratio
- Position sizing recommendation

### 1.2 Strategies to Implement

#### 1.2.1 Iron Condor (Primary - High IV Environments)

**When to Suggest:** IV Rank ≥ 50%, Neutral outlook, 30-50 DTE

**Structure:**
```
Short Call Spread (Bear Call Credit):
  - Sell OTM Call (16-20 delta)
  - Buy further OTM Call (5-10 delta)

Short Put Spread (Bull Put Credit):
  - Sell OTM Put (16-20 delta)  
  - Buy further OTM Put (5-10 delta)
```

**Algorithm for Strike Selection:**

```python
def construct_iron_condor(
    ticker: str,
    current_price: float,
    expiry: str,
    target_short_delta: float = 0.16,
    target_wing_delta: float = 0.05,
    options_chain: pd.DataFrame,
    greeks_data: dict
) -> dict:
    """
    Construct Iron Condor with institutional parameters.
    
    Returns:
        {
            "strategy": "IRON_CONDOR",
            "legs": [
                {"type": "SELL", "option": "CALL", "strike": X, "delta": Y, "premium": Z},
                {"type": "BUY", "option": "CALL", "strike": X, "delta": Y, "premium": Z},
                {"type": "SELL", "option": "PUT", "strike": X, "delta": Y, "premium": Z},
                {"type": "BUY", "option": "PUT", "strike": X, "delta": Y, "premium": Z},
            ],
            "net_credit": float,
            "max_profit": float,  # = net_credit × 100
            "max_loss": float,    # = (width - net_credit) × 100
            "breakeven_upper": float,
            "breakeven_lower": float,
            "pop": float,  # probability of profit
            "risk_reward": float,
            "aggregate_greeks": {
                "delta": float,
                "gamma": float,
                "theta": float,  # Should be positive (collecting theta)
                "vega": float    # Should be negative (short volatility)
            },
            "width": int,  # Strike width of spreads
            "contracts_recommended": int,  # Based on account size
            "total_buying_power": float,
            "margin_requirement": float
        }
    """
```

**Strike Selection Logic:**

```python
# Step 1: Find short call strike (closest to 16-delta)
calls = options_chain[options_chain['type'] == 'call'].copy()
calls['delta_diff'] = abs(calls['delta'] - target_short_delta)
short_call_strike = calls.loc[calls['delta_diff'].idxmin(), 'strike']

# Step 2: Find long call strike (wing, ~5-delta, typically 1-2 strikes OTM from short)
# Standard width: $5 for stocks <$100, $10 for stocks $100-500, $25 for >$500
wing_width = get_optimal_width(current_price)
long_call_strike = short_call_strike + wing_width

# Step 3: Symmetric for puts (find 16-delta put, then wing)
puts = options_chain[options_chain['type'] == 'put'].copy()
puts['delta_diff'] = abs(abs(puts['delta']) - target_short_delta)
short_put_strike = puts.loc[puts['delta_diff'].idxmin(), 'strike']
long_put_strike = short_put_strike - wing_width

# Step 4: Calculate aggregate metrics
net_credit = (short_call_premium - long_call_premium + 
              short_put_premium - long_put_premium)
max_profit = net_credit * 100
max_loss = (wing_width - net_credit) * 100

# Step 5: Calculate breakevens
breakeven_upper = short_call_strike + net_credit
breakeven_lower = short_put_strike - net_credit

# Step 6: Estimate POP (probability between breakevens)
# Simplified: Use delta of short strikes as proxy
# Better: Use expected move calculation
pop = 1 - abs(short_call_delta) - abs(short_put_delta)
```

**Optimal Width Selection:**

```python
def get_optimal_width(price: float) -> float:
    """
    Determine optimal spread width based on stock price.
    TastyTrade research: ~16-delta short strikes with standard widths.
    """
    if price <= 50:
        return 2.5
    elif price <= 100:
        return 5.0
    elif price <= 250:
        return 10.0
    elif price <= 500:
        return 25.0
    else:
        return 50.0
```

#### 1.2.2 Iron Butterfly (High IV, ATM Pinning)

**When to Suggest:** IV Rank ≥ 70%, Expecting ATM pinning, High reward potential

**Structure:**
```
Short Straddle (ATM):
  - Sell ATM Call
  - Sell ATM Put (same strike)

Long Wings:
  - Buy OTM Call (wing protection)
  - Buy OTM Put (wing protection)
```

**Algorithm:**

```python
def construct_iron_butterfly(
    ticker: str,
    current_price: float,
    expiry: str,
    wing_width: float = None,  # If None, use optimal width
    options_chain: pd.DataFrame
) -> dict:
    """
    Construct Iron Butterfly for ATM pinning scenarios.
    
    Key difference from Iron Condor:
    - Short strikes are SAME (ATM)
    - Higher max profit potential (~4.5x risk)
    - Lower POP (~30% vs ~70%)
    
    Returns similar structure to iron_condor plus:
        "atm_strike": float,
        "reward_to_risk": float  # Typically 3:1 to 5:1
    """
    # Find ATM strike (closest to current price)
    all_strikes = options_chain['strike'].unique()
    atm_strike = min(all_strikes, key=lambda x: abs(x - current_price))
    
    # Set wing width (typically same as iron condor)
    if wing_width is None:
        wing_width = get_optimal_width(current_price)
    
    # Get premiums
    atm_call = options_chain[(options_chain['strike'] == atm_strike) & 
                              (options_chain['type'] == 'call')].iloc[0]
    atm_put = options_chain[(options_chain['strike'] == atm_strike) & 
                             (options_chain['type'] == 'put')].iloc[0]
    
    call_wing_strike = atm_strike + wing_width
    put_wing_strike = atm_strike - wing_width
    
    # Calculate metrics
    net_credit = (atm_call['premium'] + atm_put['premium'] - 
                  call_wing_premium - put_wing_premium)
    max_profit = net_credit * 100
    max_loss = (wing_width - net_credit) * 100
    
    # Butterfly has narrow profit zone
    breakeven_upper = atm_strike + net_credit
    breakeven_lower = atm_strike - net_credit
    
    # POP is lower for butterflies (need price at ATM)
    # Estimate using expected move vs breakeven distance
    pop = estimate_butterfly_pop(current_price, breakeven_upper, breakeven_lower, dte, iv)
```

#### 1.2.3 Broken Wing Butterfly (BWB) - Directional Enhancement

**When to Suggest:** IV Rank ≥ 50%, Slight directional bias, Want reduced risk on one side

**Structure (Bullish BWB - Put side):**
```
  - Sell 2x ATM Puts (or slightly OTM)
  - Buy 1x OTM Put (lower wing)
  - Buy 1x ITM Put (higher wing, closer to ATM)
  
  Result: Asymmetric wings - no risk or credit on upside
```

### 1.3 Implementation Details

#### 1.3.1 New Function: `construct_options_strategy`

**Location:** `investor_agent/server.py`

**Function Signature:**

```python
@mcp.tool()
async def construct_options_strategy(
    ticker: str,
    strategy: Literal["iron_condor", "iron_butterfly", "broken_wing_butterfly"],
    direction: Literal["NEUTRAL", "LONG", "SHORT"] = "NEUTRAL",
    account_size: float = 10000,
    target_dte: int = 45,
    custom_short_delta: float = None,  # Override default 16-delta
    custom_width: float = None  # Override auto-width
) -> dict:
    """
    Construct complete options strategy with specific strikes and Greeks.
    
    Args:
        ticker: Stock symbol
        strategy: Strategy type to construct
        direction: Market outlook (NEUTRAL, LONG bias, SHORT bias)
        account_size: Account size for position sizing
        target_dte: Target days to expiration (default 45)
        custom_short_delta: Override default 16-delta short strikes
        custom_width: Override auto-calculated spread width
    
    Returns:
        Complete strategy construction with:
        - All leg details (strike, premium, delta, etc.)
        - Aggregate position Greeks
        - Max profit/loss calculations
        - Breakeven points
        - Probability of profit
        - Position sizing recommendation
        - Margin requirement
        - Exit rules (50% profit target, 21 DTE roll)
    """
```

#### 1.3.2 Data Requirements

**From Questrade API (Primary):**
```python
# Get options chain with Greeks
qt_client = get_questrade_client()
chain = qt_client.get_options_chain(ticker)
# Returns: strike, bid, ask, volume, openInterest, delta, gamma, theta, vega, impliedVolatility

# For each option in selected expiry
greeks = qt_client.get_option_quotes(option_ids)
```

**Fallback (yfinance - limited Greeks):**
```python
ticker_obj = yf.Ticker(ticker)
chain = ticker_obj.option_chain(expiry)
# Note: yfinance Greeks are estimated, prefer Questrade
```

#### 1.3.3 Output Schema

```python
{
    "strategy_construction": {
        "strategy_name": "IRON_CONDOR",
        "ticker": "AAPL",
        "current_price": 259.04,
        "expiration": "2026-02-27",
        "dte": 48,
        
        "legs": [
            {
                "leg_id": 1,
                "action": "SELL",
                "option_type": "CALL",
                "strike": 275.0,
                "quantity": 1,
                "premium": 2.45,
                "bid": 2.40,
                "ask": 2.50,
                "delta": 0.16,
                "gamma": 0.008,
                "theta": -0.045,
                "vega": 0.28,
                "iv": 0.259
            },
            {
                "leg_id": 2,
                "action": "BUY",
                "option_type": "CALL", 
                "strike": 285.0,
                "quantity": 1,
                "premium": 1.05,
                "bid": 1.00,
                "ask": 1.10,
                "delta": 0.06,
                "gamma": 0.004,
                "theta": -0.025,
                "vega": 0.15,
                "iv": 0.262
            },
            {
                "leg_id": 3,
                "action": "SELL",
                "option_type": "PUT",
                "strike": 245.0,
                "quantity": 1,
                "premium": 2.30,
                "bid": 2.25,
                "ask": 2.35,
                "delta": -0.16,
                "gamma": 0.009,
                "theta": -0.042,
                "vega": 0.26,
                "iv": 0.265
            },
            {
                "leg_id": 4,
                "action": "BUY",
                "option_type": "PUT",
                "strike": 235.0,
                "quantity": 1,
                "premium": 0.95,
                "bid": 0.90,
                "ask": 1.00,
                "delta": -0.05,
                "gamma": 0.003,
                "theta": -0.020,
                "vega": 0.12,
                "iv": 0.270
            }
        ],
        
        "position_summary": {
            "net_credit": 2.75,
            "net_credit_per_contract": 275.00,
            "max_profit": 275.00,
            "max_loss": 725.00,  # (10 width - 2.75 credit) × 100
            "risk_reward_ratio": 0.38,
            "breakeven_upper": 277.75,
            "breakeven_lower": 242.25,
            "profit_zone_width": 35.50,  # Upper BE - Lower BE
            "probability_of_profit": 68.0,  # Estimated %
            "expected_value": 93.50  # (POP × max_profit) - ((1-POP) × max_loss)
        },
        
        "aggregate_greeks": {
            "position_delta": 0.01,  # Near neutral
            "position_gamma": -0.010,  # Short gamma (want price to stay still)
            "position_theta": 0.042,  # Positive (collecting time decay)
            "position_vega": -0.27,  # Negative (short volatility)
            "theta_per_day_dollars": 4.20  # Per contract
        },
        
        "position_sizing": {
            "account_size": 10000,
            "risk_per_trade_pct": 3.0,
            "max_loss_per_contract": 725.00,
            "contracts_recommended": 4,  # floor(10000 × 0.03 / 725)
            "total_premium_collected": 1100.00,
            "total_max_loss": 2900.00,
            "buying_power_required": 2900.00,
            "buying_power_pct_of_account": 29.0
        },
        
        "trade_management": {
            "profit_target_pct": 50,
            "profit_target_dollars": 137.50,  # Per contract
            "roll_dte_threshold": 21,
            "exit_rules": [
                "Close at 50% profit ($137.50/contract)",
                "Roll or close at 21 DTE (Feb 6, 2026)",
                "Review if loss reaches 50% of max loss ($362.50/contract)",
                "Adjust if position delta exceeds ±0.35"
            ],
            "adjustment_triggers": {
                "delta_threshold": 0.35,
                "loss_review_threshold": 0.50
            }
        },
        
        "liquidity_assessment": {
            "call_spread_bid_ask_spread_pct": 2.1,
            "put_spread_bid_ask_spread_pct": 2.3,
            "total_slippage_estimate": 0.12,  # Per contract
            "liquidity_grade": "A",
            "tier": "TIER_1"
        },
        
        "warnings": [],
        
        "entry_instruction": "Place as single Iron Condor order. Limit order at $2.75 credit or better. If not filled in 30 minutes, adjust to mid-price."
    }
}
```

### 1.4 Integration with `generate_options_trade_plan`

Modify `generate_options_trade_plan` to call `construct_options_strategy` internally:

```python
# In generate_options_trade_plan, after determining strategy recommendation:

if options_allowed and iv_environment in ['HIGH_IV_70_100', 'HIGH_IV_50_70']:
    if direction == 'NEUTRAL':
        if iv_rank >= 70:
            strategy_construction = await construct_options_strategy(
                ticker=ticker,
                strategy="iron_butterfly",
                direction=direction,
                account_size=account_size,
                target_dte=target_dte
            )
        else:
            strategy_construction = await construct_options_strategy(
                ticker=ticker,
                strategy="iron_condor",
                direction=direction,
                account_size=account_size,
                target_dte=target_dte
            )
    elif direction in ['LONG', 'SHORT']:
        # Use broken wing butterfly for directional bias
        strategy_construction = await construct_options_strategy(
            ticker=ticker,
            strategy="broken_wing_butterfly",
            direction=direction,
            account_size=account_size,
            target_dte=target_dte
        )
```

---

## Feature 2: IV Skew Analysis

### 2.1 Objective

Implement IV skew analysis to measure the difference in implied volatility between OTM puts and OTM calls, providing sentiment confirmation and trading edge detection.

### 2.2 What is IV Skew?

**Definition:** The difference in IV between equidistant OTM puts and OTM calls.

**Normal Skew (Equity Markets):**
- OTM puts typically have HIGHER IV than OTM calls
- This is called "negative skew" or "put skew"
- Reflects demand for downside protection

**Skew Interpretation:**

| Skew Level | Meaning | Trading Implication |
|------------|---------|---------------------|
| **Steep (>10%)** | High fear, demand for puts | Bearish sentiment, put spreads expensive |
| **Normal (3-8%)** | Typical market conditions | Standard pricing |
| **Flat (0-3%)** | Complacency, low fear | Potential warning sign |
| **Inverted (<0%)** | Call demand exceeds puts | Bullish positioning, speculative fervor |

### 2.3 Implementation

#### 2.3.1 New Function: `analyze_iv_skew`

```python
@mcp.tool()
async def analyze_iv_skew(
    ticker: str,
    target_dte: int = 45,
    delta_levels: list[float] = [0.25, 0.15, 0.10]
) -> dict:
    """
    Analyze IV skew across OTM options for sentiment confirmation.
    
    Compares IV of equidistant OTM puts vs OTM calls at multiple delta levels.
    
    Args:
        ticker: Stock symbol
        target_dte: Target days to expiration for analysis
        delta_levels: Delta levels to analyze (default: 25-delta, 15-delta, 10-delta)
    
    Returns:
        Complete IV skew analysis with:
        - Skew at each delta level
        - Overall skew classification
        - Sentiment interpretation
        - Historical skew context (if available)
        - Trading implications
        - Strategy adjustments based on skew
    """
```

#### 2.3.2 Calculation Algorithm

```python
def calculate_iv_skew(options_chain: pd.DataFrame, current_price: float) -> dict:
    """
    Calculate IV skew at multiple delta levels.
    
    Skew = Put_IV - Call_IV at equidistant strikes
    
    Positive skew = puts more expensive (normal/bearish)
    Negative skew = calls more expensive (unusual/bullish)
    """
    results = {}
    
    for target_delta in [0.25, 0.15, 0.10]:
        # Find put with closest delta to target
        puts = options_chain[options_chain['type'] == 'put'].copy()
        puts['delta_diff'] = abs(abs(puts['delta']) - target_delta)
        put_option = puts.loc[puts['delta_diff'].idxmin()]
        
        # Find call with closest delta to target
        calls = options_chain[options_chain['type'] == 'call'].copy()
        calls['delta_diff'] = abs(calls['delta'] - target_delta)
        call_option = calls.loc[calls['delta_diff'].idxmin()]
        
        # Calculate skew
        put_iv = put_option['impliedVolatility'] * 100  # Convert to %
        call_iv = call_option['impliedVolatility'] * 100
        skew = put_iv - call_iv
        skew_pct = (skew / call_iv) * 100 if call_iv > 0 else 0
        
        results[f'delta_{int(target_delta*100)}'] = {
            'put_strike': put_option['strike'],
            'put_iv': round(put_iv, 2),
            'call_strike': call_option['strike'],
            'call_iv': round(call_iv, 2),
            'skew_absolute': round(skew, 2),  # IV points
            'skew_relative_pct': round(skew_pct, 2)  # % difference
        }
    
    return results


def classify_skew(skew_data: dict) -> dict:
    """
    Classify overall skew and provide interpretation.
    """
    # Use 25-delta as primary reference (most liquid OTM options)
    primary_skew = skew_data['delta_25']['skew_absolute']
    
    if primary_skew > 10:
        classification = "STEEP_PUT_SKEW"
        sentiment = "FEARFUL"
        interpretation = "High demand for downside protection. Market participants are willing to pay premium for puts. Bearish sentiment."
        trading_implication = "Put credit spreads are rich - consider selling. Call credit spreads may offer less premium."
    elif primary_skew > 5:
        classification = "NORMAL_PUT_SKEW"
        sentiment = "CAUTIOUS"
        interpretation = "Normal market conditions with typical put premium. Standard pricing dynamics."
        trading_implication = "Standard iron condor construction is appropriate."
    elif primary_skew > 0:
        classification = "FLAT_SKEW"
        sentiment = "COMPLACENT"
        interpretation = "Low fear in market. Puts are cheap relative to historical norms. Potential complacency warning."
        trading_implication = "Put protection is cheap - consider protective puts. Be wary of sudden vol spikes."
    else:
        classification = "INVERTED_SKEW"
        sentiment = "SPECULATIVE_BULLISH"
        interpretation = "Unusual condition - calls more expensive than puts. Heavy call buying, speculative fervor."
        trading_implication = "Sell call spreads (expensive). Market may be overheated."
    
    # Check for term structure inversion (near-term IV > far-term IV)
    # This would require additional expiration analysis
    
    return {
        'classification': classification,
        'sentiment': sentiment,
        'interpretation': interpretation,
        'trading_implication': trading_implication,
        'primary_skew': primary_skew
    }
```

#### 2.3.3 Output Schema

```python
{
    "iv_skew_analysis": {
        "ticker": "AAPL",
        "analysis_date": "2026-01-09",
        "expiration_analyzed": "2026-02-27",
        "dte": 48,
        "current_price": 259.04,
        
        "skew_by_delta": {
            "delta_25": {
                "put_strike": 245.0,
                "put_iv": 28.5,
                "call_strike": 275.0,
                "call_iv": 24.2,
                "skew_absolute": 4.3,
                "skew_relative_pct": 17.8
            },
            "delta_15": {
                "put_strike": 235.0,
                "put_iv": 30.2,
                "call_strike": 285.0,
                "call_iv": 23.8,
                "skew_absolute": 6.4,
                "skew_relative_pct": 26.9
            },
            "delta_10": {
                "put_strike": 225.0,
                "put_iv": 32.1,
                "call_strike": 295.0,
                "call_iv": 23.5,
                "skew_absolute": 8.6,
                "skew_relative_pct": 36.6
            }
        },
        
        "summary": {
            "classification": "NORMAL_PUT_SKEW",
            "primary_skew": 4.3,
            "sentiment": "CAUTIOUS",
            "interpretation": "Normal market conditions with typical put premium. OTM puts are ~18% more expensive than equidistant OTM calls.",
            "trading_implication": "Standard iron condor construction is appropriate. Put credit spreads offer slightly more premium.",
            "skew_trend": "STABLE"  # Would need historical data
        },
        
        "smile_shape": {
            "description": "Standard volatility smile - IV increases as you move away from ATM in both directions, with steeper increase on put side.",
            "atm_iv": 25.9,
            "25_delta_put_premium": "+10.0%",  # vs ATM
            "25_delta_call_premium": "+6.6%"   # vs ATM
        },
        
        "strategy_adjustments": {
            "iron_condor_adjustment": "Consider widening put spread or moving short put strike closer to ATM to capture put skew premium.",
            "put_spread_note": "Put credit spreads are rich due to skew - favorable for selling.",
            "call_spread_note": "Call credit spreads offer less premium - acceptable but not optimal."
        },
        
        "historical_context": {
            "current_skew_percentile": 55,  # vs 52-week range
            "52w_skew_high": 15.2,
            "52w_skew_low": -2.1,
            "avg_skew": 5.8,
            "note": "Current skew is within normal range (percentile 55)"
        },
        
        "sentiment_confirmation": {
            "skew_signal": "NEUTRAL",
            "put_call_ratio_signal": "NEUTRAL",  # From existing analysis
            "unusual_activity_signal": "NO_SIGNAL",  # From existing analysis
            "combined_signal": "NEUTRAL",
            "confidence": "MEDIUM"
        }
    }
}
```

### 2.4 Integration Points

#### 2.4.1 Add to `analyze_options_mcmillan`

```python
# In analyze_options_mcmillan, add skew analysis section:

iv_skew = await analyze_iv_skew(ticker, target_dte=45)

result['iv_skew'] = iv_skew['summary']
result['sentiment_confirmation'] = {
    'skew_signal': iv_skew['summary']['sentiment'],
    'put_call_ratio_signal': put_call_result['sentiment'],
    'combined_signal': combine_sentiment_signals(
        skew=iv_skew['summary']['sentiment'],
        put_call=put_call_result['sentiment'],
        unusual_activity=uoa_result['signal']
    )
}
```

#### 2.4.2 Use in Strategy Construction

```python
# In construct_options_strategy, adjust based on skew:

skew_data = await analyze_iv_skew(ticker, target_dte)

if skew_data['summary']['classification'] == 'STEEP_PUT_SKEW':
    # Put spreads are rich - favor put credit spreads
    # Consider asymmetric iron condor (wider put spread)
    put_width = standard_width * 1.2
    call_width = standard_width * 0.8
    
elif skew_data['summary']['classification'] == 'INVERTED_SKEW':
    # Calls are expensive - favor call credit spreads
    put_width = standard_width * 0.8
    call_width = standard_width * 1.2
```

---

## Feature 3: 21 DTE Roll Reminder

### 3.1 Objective

Add explicit 21 DTE roll reminder to trade plan output, including:
- Calendar date when 21 DTE is reached
- Decision framework for roll vs close
- Specific roll instructions

### 3.2 Implementation

#### 3.2.1 Calculation Logic

```python
def calculate_roll_date(expiration_date: str) -> dict:
    """
    Calculate the date when position reaches 21 DTE.
    
    At 21 DTE:
    - Gamma risk accelerates
    - Theta decay becomes less favorable for time spent in trade
    - Decision point: roll, close, or continue
    
    Returns:
        {
            'expiration_date': 'YYYY-MM-DD',
            'roll_date': 'YYYY-MM-DD',  # 21 DTE date
            'days_until_roll': int,
            'roll_decision_framework': str,
            'roll_instructions': list[str]
        }
    """
    from datetime import datetime, timedelta
    
    exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
    roll_date = exp_date - timedelta(days=21)
    today = datetime.now()
    days_until_roll = (roll_date - today).days
    
    return {
        'expiration_date': expiration_date,
        'roll_date': roll_date.strftime('%Y-%m-%d'),
        'roll_date_formatted': roll_date.strftime('%B %d, %Y'),  # "February 6, 2026"
        'days_until_roll': max(0, days_until_roll),
        'dte_at_roll': 21,
        'is_past_roll_date': days_until_roll < 0
    }
```

#### 3.2.2 Roll Decision Framework

```python
def generate_roll_decision_framework(
    strategy: str,
    current_pnl_pct: float = None,
    position_delta: float = None
) -> dict:
    """
    Generate decision framework for 21 DTE roll/close.
    
    Based on TastyTrade research:
    - 50% profit target wins 88% of trades
    - No stop losses - manage mechanically
    - Roll to next monthly cycle at same delta
    """
    
    framework = {
        'primary_rule': "At 21 DTE, evaluate position for roll or close",
        
        'close_conditions': [
            "✓ Position has reached 50% profit target",
            "✓ Position is at max loss and conditions have not improved",
            "✓ Underlying has had significant fundamental change",
            "✓ Earnings are within the new expiration cycle"
        ],
        
        'roll_conditions': [
            "✓ Position is profitable but <50% of max profit",
            "✓ Position is at small loss but setup remains valid",
            "✓ IV remains elevated (IV Rank >30%)",
            "✓ No earnings in next 30-45 days"
        ],
        
        'roll_instructions': [
            "1. Close current position as single order",
            "2. Open new position at same delta in next monthly cycle",
            "3. Target: Collect additional credit on roll",
            "4. If cannot collect credit, consider closing instead",
            "5. New position DTE should be 40-50 days"
        ],
        
        'roll_pricing': {
            'minimum_credit': "Aim to collect credit on roll (even small)",
            'maximum_debit': "Do not roll for debit >20% of original credit",
            'strike_adjustment': "Keep strikes at same delta or adjust toward ATM if needed"
        },
        
        'do_not_roll_if': [
            "Position has already hit 50% profit target",
            "Underlying has earnings before new expiration",
            "IV has collapsed below IV Rank 20%",
            "Position is at 100% max loss"
        ]
    }
    
    return framework
```

#### 3.2.3 Output Schema Addition

Add to `generate_options_trade_plan` and `construct_options_strategy`:

```python
{
    "trade_management": {
        # ... existing fields ...
        
        "roll_reminder": {
            "expiration_date": "2026-02-27",
            "roll_decision_date": "2026-02-06",
            "roll_decision_date_formatted": "February 6, 2026",
            "days_until_roll_date": 27,
            "dte_at_roll": 21,
            
            "reminder_message": "⏰ ROLL DECISION: February 6, 2026 (21 DTE)",
            
            "decision_framework": {
                "if_profitable_above_50pct": "CLOSE - Take profits",
                "if_profitable_below_50pct": "ROLL to March expiration at same delta",
                "if_small_loss_under_25pct": "ROLL if setup still valid and IV remains elevated",
                "if_large_loss_over_50pct": "EVALUATE - Consider closing if thesis broken"
            },
            
            "roll_target": {
                "next_expiration": "2026-03-27",
                "target_dte": 48,
                "target_delta": 16,
                "roll_type": "Calendar roll to next monthly"
            },
            
            "roll_instructions": [
                "1. On Feb 6, assess position P/L",
                "2. If <50% profit: Prepare roll order",
                "3. Close Feb 27 iron condor + Open Mar 27 iron condor",
                "4. Aim to collect net credit on the roll",
                "5. If no credit available, consider just closing"
            ],
            
            "critical_dates": [
                {
                    "date": "2026-01-29",
                    "event": "AAPL Earnings",
                    "action": "Monitor - may need early exit"
                },
                {
                    "date": "2026-02-06",
                    "event": "21 DTE Roll Decision",
                    "action": "Evaluate roll vs close"
                },
                {
                    "date": "2026-02-20",
                    "event": "7 DTE Warning",
                    "action": "Must be closed - gamma risk too high"
                },
                {
                    "date": "2026-02-27",
                    "event": "Expiration",
                    "action": "Position expires"
                }
            ]
        }
    }
}
```

### 3.3 Integration

#### 3.3.1 Add to `generate_options_trade_plan`

```python
# After constructing options plan, add roll reminder:

if options_plan and options_plan.get('status') != 'SKIP':
    expiration = options_plan['expiration']
    
    roll_info = calculate_roll_date(expiration)
    roll_framework = generate_roll_decision_framework(
        strategy=options_plan['strategy'],
        current_pnl_pct=0  # At entry
    )
    
    options_plan['trade_management']['roll_reminder'] = {
        **roll_info,
        'decision_framework': roll_framework['decision_framework'],
        'roll_instructions': roll_framework['roll_instructions'],
        'reminder_message': f"⏰ ROLL DECISION: {roll_info['roll_date_formatted']} (21 DTE)"
    }
```

#### 3.3.2 Add Calendar Date Calculation

```python
def get_critical_dates(expiration: str, earnings_date: str = None) -> list[dict]:
    """
    Generate list of critical dates for position management.
    """
    from datetime import datetime, timedelta
    
    exp = datetime.strptime(expiration, '%Y-%m-%d')
    
    dates = [
        {
            'date': (exp - timedelta(days=21)).strftime('%Y-%m-%d'),
            'dte': 21,
            'event': '21 DTE Roll Decision',
            'action': 'Evaluate roll vs close'
        },
        {
            'date': (exp - timedelta(days=7)).strftime('%Y-%m-%d'),
            'dte': 7,
            'event': '7 DTE Warning',
            'action': 'Exit zone - gamma risk elevated'
        },
        {
            'date': expiration,
            'dte': 0,
            'event': 'Expiration',
            'action': 'Position expires'
        }
    ]
    
    if earnings_date:
        dates.insert(0, {
            'date': earnings_date,
            'event': 'Earnings',
            'action': 'Monitor - may need early management'
        })
    
    return sorted(dates, key=lambda x: x['date'])
```

---

## Implementation Checklist

### Phase 1: Foundation (Days 1-3)

- [ ] Create `construct_iron_condor()` function
- [ ] Create `construct_iron_butterfly()` function  
- [ ] Implement `get_optimal_width()` helper
- [ ] Add aggregate Greeks calculation
- [ ] Add position sizing calculation
- [ ] Test with Tier 1 underlyings (SPY, AAPL, NVDA)

### Phase 2: IV Skew (Days 4-6)

- [ ] Create `analyze_iv_skew()` MCP tool
- [ ] Implement skew calculation at 25/15/10 delta levels
- [ ] Add skew classification logic
- [ ] Integrate with `analyze_options_mcmillan`
- [ ] Add sentiment confirmation aggregation
- [ ] Test with various skew conditions

### Phase 3: Roll Reminder (Days 7-8)

- [ ] Implement `calculate_roll_date()` function
- [ ] Create `generate_roll_decision_framework()` function
- [ ] Add `get_critical_dates()` helper
- [ ] Integrate into `generate_options_trade_plan`
- [ ] Add to `construct_options_strategy` output
- [ ] Test date calculations

### Phase 4: Integration & Testing (Days 9-10)

- [ ] Update `generate_options_trade_plan` to use new functions
- [ ] Add `construct_options_strategy` as standalone MCP tool
- [ ] Update output schemas
- [ ] End-to-end testing with real market data
- [ ] Documentation updates
- [ ] Edge case handling (no Greeks available, illiquid options, etc.)

---

## Testing Requirements

### Unit Tests

```python
# tests/test_options_construction.py

def test_iron_condor_construction():
    """Test iron condor builds correctly with 16-delta shorts"""
    result = construct_iron_condor('SPY', 590.0, '2026-02-27')
    
    assert result['legs'][0]['delta'] between 0.14 and 0.18  # Short call
    assert result['legs'][2]['delta'] between -0.18 and -0.14  # Short put
    assert result['position_summary']['net_credit'] > 0
    assert result['aggregate_greeks']['position_theta'] > 0  # Collecting theta
    assert result['aggregate_greeks']['position_vega'] < 0  # Short vega

def test_iv_skew_calculation():
    """Test IV skew correctly identifies put premium"""
    result = analyze_iv_skew('SPY', target_dte=45)
    
    # SPY should have normal put skew
    assert result['summary']['classification'] in ['NORMAL_PUT_SKEW', 'STEEP_PUT_SKEW']
    assert result['skew_by_delta']['delta_25']['put_iv'] > result['skew_by_delta']['delta_25']['call_iv']

def test_roll_date_calculation():
    """Test 21 DTE roll date is correct"""
    result = calculate_roll_date('2026-02-27')
    
    assert result['roll_date'] == '2026-02-06'
    assert result['dte_at_roll'] == 21
```

### Integration Tests

```python
def test_full_trade_plan_with_construction():
    """Test complete trade plan includes strategy construction"""
    result = generate_options_trade_plan('SPY', 'NEUTRAL', account_size=50000)
    
    if result['options_plan']['status'] != 'SKIP':
        assert 'legs' in result['options_plan']
        assert 'roll_reminder' in result['options_plan']['trade_management']
        assert len(result['options_plan']['legs']) == 4  # Iron condor
```

---

## Error Handling

### Graceful Degradation

```python
# When Questrade Greeks unavailable:
try:
    greeks = qt_client.get_option_quotes(option_ids)
except Exception as e:
    logger.warning(f"Questrade Greeks unavailable: {e}")
    greeks = estimate_greeks_from_chain(options_chain)  # Use yfinance or calculate

# When options chain is empty (off-market hours):
if options_chain.empty:
    return {
        'status': 'UNAVAILABLE',
        'reason': 'Options data unavailable (likely off-market hours)',
        'fallback': 'Use theoretical strikes based on expected move calculation'
    }

# When skew calculation fails:
if not all_required_options_found:
    return {
        'status': 'PARTIAL',
        'available_levels': ['delta_25'],
        'missing_levels': ['delta_15', 'delta_10'],
        'note': 'Insufficient option strikes for full skew analysis'
    }
```

---

## References

### McMillan - Options as a Strategic Investment
- Chapter 1-10: Basic Option Strategies (Iron Condor, Butterfly construction)
- Chapter 24: Stock Option Strategies (Put/Call ratios)
- Chapter 25: Index Option Strategies (Skew analysis)
- Chapter 28: Volatility Trading (IV rank, IV percentile)
- Chapter 36: Portfolio Management (Position sizing)

### TastyTrade Research
- 45 DTE entry with 50% profit management: 88% win rate
- No stop losses: Trades with 2x credit stops showed 46% win rate vs 75%+ without
- 21 DTE roll threshold: Gamma acceleration point

### Natenberg - Option Volatility and Pricing
- Variance risk premium: IV overstates realized volatility 85% of time
- Skew dynamics and mean reversion

---

## Appendix A: Constants and Configuration

```python
# Add to INSTITUTIONAL_OPTIONS_PARAMS in server.py:

INSTITUTIONAL_OPTIONS_PARAMS.update({
    # Strategy Construction
    'iron_condor': {
        'min_iv_rank': 50,
        'target_short_delta': 0.16,
        'target_wing_delta': 0.05,
        'min_pop': 0.65
    },
    'iron_butterfly': {
        'min_iv_rank': 70,
        'target_atm_only': True,
        'min_reward_risk': 3.0
    },
    
    # IV Skew Thresholds
    'skew': {
        'steep_threshold': 10.0,      # Steep put skew
        'normal_range': (3.0, 8.0),   # Normal skew
        'flat_threshold': 3.0,        # Flat skew
        'inverted_threshold': 0.0     # Inverted (calls > puts)
    },
    
    # Roll Management
    'roll': {
        'decision_dte': 21,           # DTE to make roll decision
        'warning_dte': 7,             # Warning zone
        'target_roll_dte': 45,        # New position target DTE
        'min_roll_credit': 0.0,       # Minimum credit to accept roll
        'max_roll_debit_pct': 0.20    # Max debit as % of original credit
    }
})
```

---

**Document End**

*This specification provides complete implementation details for the three options trading enhancements. The developer should implement features in the order presented, with comprehensive testing after each phase.*
