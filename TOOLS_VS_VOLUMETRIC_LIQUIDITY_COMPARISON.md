# Current Tools vs Volumetric Liquidity Analysis

**Date:** December 23, 2025
**Purpose:** Gap analysis comparing current MCP tools against proposed volumetric liquidity enhancements
**Status:** READY FOR IMPLEMENTATION

---

## Executive Summary

The investor-agent already has **47 MCP tools** with robust infrastructure. The VOLUMETRIC_LIQUIDITY_ANALYSIS proposes **4 new analysis capabilities** that are **largely ALREADY IMPLEMENTED** in existing tools via recent enhancements.

### Verdict: IMPLEMENTATION STATUS

| Proposed Enhancement | Status | Current Tool | Notes |
|---------------------|--------|--------------|-------|
| CVD Analysis | **IMPLEMENTED** | `analyze_volume_tool()` | Has CVD + divergence detection |
| Exhaustion Detection | **IMPLEMENTED** | `analyze_ml_enhanced()` | Exhaustion scoring exists |
| Multi-VWAP | **PARTIAL** | `analyze_volume_tool()` | Has 3 VWAP modes, needs synthesis |
| Liquidity Zone Mapping | **PARTIAL** | `find_support_resistance()` | Needs volume-weighting |

---

## Part 1: Complete Current Tool Inventory (47 Tools)

### Category 1: Market Data & Sentiment (5 tools)

| Tool | Purpose | Data Source |
|------|---------|-------------|
| `get_market_movers` | Gainers/losers/most-active | Yahoo Finance |
| `get_cnn_fear_greed_index` | Market fear/greed indicators | CNN API |
| `get_crypto_fear_greed_index` | Crypto fear/greed | Alternative.me |
| `get_google_trends` | Search interest for keywords | Google Trends |
| `get_nasdaq_earnings_calendar` | Earnings dates by date | Nasdaq API |

### Category 2: Ticker/Company Data (6 tools)

| Tool | Purpose | Data Source |
|------|---------|-------------|
| `get_ticker_data` | Comprehensive ticker metrics | yfinance |
| `get_options` | Basic options chain | yfinance |
| `get_financial_statements` | Income/balance/cash flow | yfinance |
| `get_earnings_history` | Historical earnings data | yfinance |
| `get_institutional_holders` | Fund ownership | yfinance |
| `get_insider_trades` | Insider activity | yfinance |

### Category 3: Questrade Account (13 tools)

| Tool | Purpose | Yahoo Fallback |
|------|---------|----------------|
| `get_questrade_accounts` | Account list | No |
| `get_questrade_positions` | Holdings/P&L | No |
| `get_questrade_balances` | Cash/equity | No |
| `get_questrade_quotes` | Real-time quotes | **YES** |
| `get_questrade_candles` | OHLCV history | **YES** |
| `search_questrade_symbols` | Symbol search | No |
| `get_questrade_symbol_info` | Symbol details | No |
| `get_questrade_markets` | Markets list | No |
| `get_questrade_orders` | Order history | No |
| `get_questrade_order` | Single order | No |
| `get_questrade_executions` | Trade fills | No |
| `get_questrade_activities` | Account activity | No |
| `get_questrade_options_chain` | Options chain | **YES** |
| `get_questrade_option_quotes` | Option Greeks | No |
| `get_portfolio_summary` | Portfolio rollup | No |

### Category 4: Options Analysis (2 tools)

| Tool | Purpose |
|------|---------|
| `get_options` | Basic chain from yfinance |
| `analyze_options_mcmillan` | McMillan strategy with IV/Greeks analysis |

### Category 5: Technical Analysis (4 tools)

| Tool | Purpose | Key Features |
|------|---------|--------------|
| `calculate_technical_indicator` | TA-Lib wrapper | SMA, EMA, RSI, MACD, BBANDS |
| `analyze_technical` | Comprehensive TA | RSI, MACD, BBands, MAs, Stochastic, Al Brooks, Trend Score |
| `find_support_resistance` | S/R levels | Local extrema detection |
| `compare_technical` | Multi-stock comparison | Side-by-side indicators |

### Category 6: Volume/Volatility/RS (4 tools)

| Tool | Purpose | Key Features |
|------|---------|--------------|
| `analyze_volume_tool` | Comprehensive volume | VWAP (3 modes), CVD, OBV, MFI, A/D Line, POC |
| `analyze_volatility_tool` | Risk management | ATR, Beta, Historical Vol, Stop recommendations |
| `calculate_relative_strength_tool` | Stock selection | IBD-style RS score (0-100) |
| `calculate_fundamental_scores_tool` | Quality scoring | Piotroski F-Score, Altman Z-Score |

### Category 7: Order Flow (3 tools)

| Tool | Purpose |
|------|---------|
| `analyze_realtime_trade_flow` | Trade direction analysis |
| `get_bid_ask_imbalance` | Bid/ask ratio |
| `analyze_spread_dynamics` | Spread analysis |

### Category 8: ML-Enhanced Analysis (4 tools)

| Tool | Purpose |
|------|---------|
| `find_similar_historical_setups` | Pattern matching with target achievement |
| `analyze_ml_enhanced` | ML probability, EMA crosses, Kelly sizing, Exhaustion |
| `validate_strategy_robustness` | p-hacking detection (Deflated Sharpe) |
| `calculate_feature_importance_analysis` | MDI/MDA/SFI feature ranking |

### Category 9: Scanner (2 tools)

| Tool | Purpose |
|------|---------|
| `scan_market_opportunities` | 4-Tier inflection scanner (US + Canada) |
| `scan_stocks_by_setup` | Specific setup scanner (12 setup types) |

### Category 10: Fund Analysis (3 tools)

| Tool | Purpose |
|------|---------|
| `analyze_mutual_fund` | Fund analysis vs benchmark |
| `compare_mutual_funds` | Multi-fund comparison |
| `analyze_etf` | ETF analysis with options |

---

## Part 2: Proposed Tools from VOLUMETRIC_LIQUIDITY_ANALYSIS

The document proposes 4 "new" tools based on a Reddit trader's methodology:

### Proposed Tool 1: `analyze_volume_delta`

**Purpose:** CVD-style analysis using OHLCV approximation

**Proposed Features:**
- Volume delta per bar
- CVD trend (bullish/bearish/neutral)
- Price-CVD divergence detection
- Exhaustion at S/R zones

**CURRENT STATUS: ALREADY IMPLEMENTED**

The `analyze_volume_tool()` in `technical_analysis_bootstrap.py` (lines 180-350) already has:
- CVD calculation using exact same formula proposed
- CVD trend detection (RISING/FALLING/FLAT)
- Divergence detection via `detect_cvd_divergence()`
- Integration with exhaustion scoring

**Evidence from code:**
```python
# From technical_analysis_bootstrap.py
def analyze_cvd(df: pd.DataFrame) -> dict:
    """CVD (Cumulative Volume Delta) analysis with divergence detection."""
    delta = calculate_volume_delta(df)
    cvd = delta.cumsum()
    # ... divergence detection included
```

---

### Proposed Tool 2: `detect_exhaustion_zones`

**Purpose:** Combine multiple exhaustion signals

**Proposed Features:**
- CVD divergence signal
- RSI divergence signal
- Trend day count
- Near liquidity zone detection
- Composite exhaustion score (0-100)

**CURRENT STATUS: ALREADY IMPLEMENTED**

The `calculate_exhaustion_score()` function exists in `technical_analysis_bootstrap.py`:
- Uses CVD divergence (20 pts)
- Uses RSI divergence (20 pts)
- Uses trend days (25 pts)
- Uses VWAP extension (15 pts)
- Uses volume decline (20 pts)
- Returns composite score with tiered response

**Already integrated into:**
- `analyze_ml_enhanced()` output
- Scanner Tier 4 exclusions

---

### Proposed Tool 3: `analyze_multi_vwap`

**Purpose:** Multi-anchor VWAP synthesis

**Proposed Features:**
- Session VWAP + bands
- Weekly VWAP + bands
- Swing-anchored VWAP + bands
- Sustainability score
- Mean reversion target

**CURRENT STATUS: PARTIALLY IMPLEMENTED**

The `analyze_volume_tool()` already has 3 VWAP modes:
- `vwap_mode="session"` - Daily session VWAP
- `vwap_mode="rolling"` - 20-day rolling VWAP
- `vwap_mode="anchored"` - Anchored to period start

**What's missing:**
- Standard deviation bands (1σ, 2σ)
- Simultaneous multi-anchor comparison
- "Unsustainable move" detection

**Implementation effort:** LOW (add bands + synthesis to existing)

---

### Proposed Tool 4: `map_volume_liquidity_zones`

**Purpose:** Volume-weighted S/R identification

**Proposed Features:**
- High volume nodes (magnets)
- Low volume gaps (fast move zones)
- Volume POC
- Value area bounds
- Expected behavior prediction

**CURRENT STATUS: PARTIALLY IMPLEMENTED**

Current `analyze_volume_tool()` has:
- Volume Profile with POC
- Value Area High/Low (70% of volume)

Current `find_support_resistance()` has:
- Local extrema detection
- Top 3 resistance/support levels

**What's missing:**
- Volume-weighted S/R levels
- HVN vs LVN classification
- Expected behavior prediction

**Implementation effort:** MEDIUM (new classification logic)

---

## Part 3: Gap Analysis Summary

### Features Already Implemented (No Work Needed)

| Feature | Current Tool | Status |
|---------|--------------|--------|
| CVD Calculation | `analyze_volume_tool` | Complete |
| CVD Divergence Detection | `analyze_volume_tool` | Complete |
| Exhaustion Score (0-100) | `calculate_exhaustion_score()` | Complete |
| Tiered Exhaustion Response | Scanner Tier 4 | Complete |
| POC (Point of Control) | `analyze_volume_tool` | Complete |
| Value Area High/Low | `analyze_volume_tool` | Complete |
| VWAP (3 modes) | `analyze_volume_tool` | Complete |
| RSI Divergence | `analyze_ml_enhanced` | Complete |
| Trend Day Counter | `calculate_exhaustion_score()` | Complete |

### Features Needing Enhancement (Low Effort)

| Feature | Target Tool | Effort |
|---------|-------------|--------|
| VWAP 2σ Bands | `analyze_volume_tool` | 1 day |
| Multi-VWAP Synthesis | `analyze_volume_tool` | 1 day |
| Sustainability Scoring | `analyze_volume_tool` | 1 day |

### Features Needing Implementation (Medium Effort)

| Feature | Target Tool | Effort |
|---------|-------------|--------|
| HVN/LVN Classification | New function in bootstrap | 2 days |
| Volume-Weighted S/R | Enhance `find_support_resistance` | 2 days |
| Expected Behavior Prediction | New function in bootstrap | 1 day |

---

## Part 4: Implementation Readiness Assessment

### Ready to Implement? YES

The core infrastructure is complete:
1. CVD analysis exists
2. Exhaustion scoring exists
3. VWAP modes exist
4. Scanner integration exists

### Remaining Work (5-7 days)

| Task | Priority | Days |
|------|----------|------|
| Add VWAP 2σ bands | MEDIUM | 1 |
| Multi-VWAP synthesis | MEDIUM | 1 |
| HVN/LVN classification | MEDIUM | 2 |
| Volume-weighted S/R | MEDIUM | 2 |
| Scanner integration | LOW | 1 |

### NOT Recommended to Implement

| Feature | Reason |
|---------|--------|
| Tick-level sequencing | Requires $200+/mo data feeds |
| Order book depth | Not reliable for stocks (spoofing) |
| Real-time CVD | Questrade doesn't provide tick data |

---

## Part 5: Decision

### Option A: Proceed with Enhancements (RECOMMENDED)

Add the following to existing tools:
1. VWAP bands (2σ) to `analyze_volume_tool`
2. Multi-VWAP synthesis mode
3. HVN/LVN zone classification
4. Volume-weighted S/R enhancement

**Estimated effort:** 5-7 days

### Option B: Mark as Complete

The document's core goals are already achieved:
- CVD analysis implemented
- Exhaustion detection implemented
- Scanner integration complete

The remaining features are "nice to have" not "must have".

---

## Appendix: Tool Cleanup Already Completed

Per the plan file, these tools were already consolidated:

| Removed Tool | Merged Into |
|--------------|-------------|
| `fetch_intraday_15m` | `get_questrade_candles(interval="FifteenMinutes", window=N)` |
| `fetch_intraday_1h` | `get_questrade_candles(interval="OneHour", window=N)` |
| `get_questrade_quote` | `get_questrade_quotes(symbols=["X"])` |
| `detect_chart_patterns` | `analyze_technical()` |
| `analyze_trend_strength` | `analyze_technical(include_trend_score=True)` |
| `calculate_true_cvd` | `analyze_volume_tool()` |

---

**Document Version:** 1.0
**Last Updated:** December 23, 2025
