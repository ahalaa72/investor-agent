# Investor-Agent New Tools Specification

**Version:** 1.0  
**Date:** October 31, 2025  
**Purpose:** Technical specifications for new tools to be added to investor-agent

---

## Priority 1: Volume Analysis

### 1. analyze_volume

```python
@mcp.tool()
def analyze_volume(
    ticker: str,
    period: Literal["1mo", "3mo", "6mo", "1y"] = "3mo"
) -> dict[str, Any]:
    """
    Comprehensive volume analysis including VWAP, Volume Profile, and volume indicators.
    
    Args:
        ticker: Stock ticker symbol
        period: Historical period to analyze
    
    Returns:
        {
            "symbol": str,
            "period": str,
            "current_price": float,
            "vwap": {
                "daily": float,
                "weekly": float,
                "distance_from_vwap": float,  # % above/below
                "position": str  # "Above VWAP" | "Below VWAP"
            },
            "volume_profile": {
                "poc": float,  # Point of Control (price with most volume)
                "value_area_high": float,
                "value_area_low": float,
                "current_vs_poc": str  # "Above POC" | "Below POC"
            },
            "volume_indicators": {
                "obv": float,
                "obv_trend": str,  # "Rising" | "Falling"
                "accumulation_distribution": float,
                "mfi": float,  # Money Flow Index (0-100)
                "mfi_signal": str  # "Overbought" | "Oversold" | "Neutral"
            },
            "relative_volume": {
                "current_volume": int,
                "avg_volume_20d": int,
                "relative_volume": float,  # Current / Average
                "status": str  # "High" (>1.5x) | "Normal" | "Low" (<0.5x)
            },
            "volume_surges": [
                {
                    "date": str,
                    "volume": int,
                    "vs_average": float,
                    "price_change": float
                }
            ]
        }
    """
```

---

## Priority 2: Volatility Analysis

### 2. analyze_volatility

```python
@mcp.tool()
def analyze_volatility(
    ticker: str,
    period: Literal["1mo", "3mo", "6mo", "1y"] = "3mo"
) -> dict[str, Any]:
    """
    Advanced volatility analysis for risk management and position sizing.
    
    Args:
        ticker: Stock ticker symbol
        period: Historical period to analyze
    
    Returns:
        {
            "symbol": str,
            "current_price": float,
            "atr": {
                "atr_14": float,
                "atr_20": float,
                "atr_percent": float,  # ATR as % of price
                "trend": str,  # "Expanding" | "Contracting" | "Stable"
                "recommended_stop_distance": float  # 2-3x ATR
            },
            "historical_volatility": {
                "hv_10d": float,  # Annualized %
                "hv_20d": float,
                "hv_30d": float,
                "hv_60d": float,
                "current_vs_average": float  # Current vs 60d average
            },
            "volatility_regime": {
                "percentile": float,  # 0-100 vs 1-year range
                "regime": str,  # "Low" | "Normal" | "High" | "Extreme"
                "classification": str  # "Below 25th" | "25-75th" | "Above 75th"
            },
            "beta": {
                "vs_spy": float,
                "interpretation": str  # "More volatile" | "Less volatile"
            },
            "keltner_channels": {
                "upper": float,
                "middle": float,  # EMA
                "lower": float,
                "position": str  # "Above" | "Within" | "Below"
            },
            "position_sizing_guidance": {
                "max_position_pct": float,  # Based on volatility
                "risk_per_share": float,  # For 2x ATR stop
                "shares_for_1pct_risk": int  # $10k account example
            }
        }
    """
```

---

## Priority 3: Relative Strength

### 3. calculate_relative_strength

```python
@mcp.tool()
def calculate_relative_strength(
    ticker: str,
    benchmark: str = "SPY",
    period: Literal["1mo", "3mo", "6mo", "1y"] = "3mo"
) -> dict[str, Any]:
    """
    Calculate relative strength vs market and sector to identify leaders.
    
    Args:
        ticker: Stock ticker symbol
        benchmark: Benchmark ticker (default SPY)
        period: Period for RS calculation
    
    Returns:
        {
            "symbol": str,
            "benchmark": str,
            "period": str,
            "rs_score": {
                "value": float,  # 0-100 (IBD-style)
                "percentile": int,  # Among all stocks
                "rating": str  # "Leader" (>80) | "Average" | "Laggard" (<40)
            },
            "performance": {
                "stock_return": float,  # % return in period
                "benchmark_return": float,
                "outperformance": float,  # Stock - Benchmark
                "relative_strength_line": str  # "Rising" | "Falling"
            },
            "vs_sector": {
                "sector": str,
                "sector_etf": str,
                "vs_sector_return": float,
                "sector_percentile": int
            },
            "trend": {
                "short_term_rs": str,  # "Improving" | "Deteriorating"
                "medium_term_rs": str,
                "long_term_rs": str
            },
            "interpretation": str  # Summary assessment
        }
    """
```

### 4. compare_peers

```python
@mcp.tool()
def compare_peers(
    ticker: str,
    peers: list[str] | None = None,
    auto_detect_peers: bool = True
) -> dict[str, Any]:
    """
    Compare ticker to competitors across multiple dimensions.
    
    Args:
        ticker: Primary ticker to analyze
        peers: List of peer tickers (optional)
        auto_detect_peers: Automatically find peers if not provided
    
    Returns:
        {
            "ticker": str,
            "peers": list[str],
            "comparison": {
                "performance_3mo": {
                    ticker: float,
                    "PEER1": float,
                    ...
                },
                "rs_score": {...},
                "valuation": {
                    "pe_ratio": {...},
                    "price_to_sales": {...}
                },
                "technical_strength": {
                    "trend_strength": {...},
                    "rsi": {...}
                },
                "institutional_ownership": {...}
            },
            "ranking": {
                "performance_rank": int,
                "rs_rank": int,
                "valuation_rank": int,
                "technical_rank": int,
                "overall_rank": int
            },
            "recommendation": str  # Which stocks are strongest
        }
    """
```

---

## Priority 4: Options Analysis

### 5. calculate_options_greeks

```python
@mcp.tool()
def calculate_options_greeks(
    ticker: str,
    expiry: str,  # YYYY-MM-DD
    option_type: Literal["C", "P"] | None = None
) -> dict[str, Any]:
    """
    Calculate Greeks for options at specified expiration.
    
    Args:
        ticker: Stock ticker symbol
        expiry: Option expiration date
        option_type: "C" for calls, "P" for puts, None for both
    
    Returns:
        {
            "symbol": str,
            "expiry": str,
            "spot_price": float,
            "risk_free_rate": float,
            "dividend_yield": float,
            "options": [
                {
                    "strike": float,
                    "type": str,  # "call" | "put"
                    "bid": float,
                    "ask": float,
                    "last": float,
                    "volume": int,
                    "open_interest": int,
                    "implied_volatility": float,
                    "greeks": {
                        "delta": float,
                        "gamma": float,
                        "theta": float,
                        "vega": float,
                        "rho": float
                    },
                    "intrinsic_value": float,
                    "extrinsic_value": float,
                    "moneyness": str  # "ITM" | "ATM" | "OTM"
                }
            ]
        }
    """
```

### 6. analyze_iv_metrics

```python
@mcp.tool()
def analyze_iv_metrics(ticker: str) -> dict[str, Any]:
    """
    Analyze implied volatility metrics for options timing.
    
    Returns:
        {
            "symbol": str,
            "current_iv": float,
            "iv_rank": float,  # 0-100 (vs 52-week range)
            "iv_percentile": float,  # 0-100
            "iv_52w_high": float,
            "iv_52w_low": float,
            "historical_volatility": float,
            "iv_vs_hv": {
                "difference": float,
                "status": str  # "IV Premium" | "IV Discount"
            },
            "iv_skew": {
                "call_iv_avg": float,
                "put_iv_avg": float,
                "skew": float,  # Put IV - Call IV
                "interpretation": str  # "Put skew" | "Balanced"
            },
            "term_structure": [
                {
                    "expiry": str,
                    "days_to_expiry": int,
                    "iv": float
                }
            ],
            "recommendation": str  # "High IV - consider selling" etc
        }
    """
```

### 7. detect_unusual_options_activity

```python
@mcp.tool()
def detect_unusual_options_activity(
    ticker: str,
    lookback_days: int = 5,
    min_premium: float = 100000  # $100k
) -> dict[str, Any]:
    """
    Detect unusual options activity that may signal smart money.
    
    Returns:
        {
            "symbol": str,
            "lookback_days": int,
            "unusual_activity": [
                {
                    "date": str,
                    "strike": float,
                    "expiry": str,
                    "type": str,  # "call" | "put"
                    "activity_type": str,  # "Block" | "Sweep" | "OI Spike"
                    "volume": int,
                    "open_interest": int,
                    "premium": float,
                    "sentiment": str,  # "Bullish" | "Bearish"
                    "urgency": str,  # "Aggressive" | "Normal"
                }
            ],
            "summary": {
                "total_unusual_trades": int,
                "total_premium": float,
                "bullish_premium": float,
                "bearish_premium": float,
                "net_sentiment": str,
                "smart_money_score": float  # 0-100
            },
            "key_strikes": [
                {
                    "strike": float,
                    "expiry": str,
                    "type": str,
                    "reason": str  # Why it's significant
                }
            ]
        }
    """
```

### 8. calculate_max_pain

```python
@mcp.tool()
def calculate_max_pain(
    ticker: str,
    expiry: str  # YYYY-MM-DD
) -> dict[str, Any]:
    """
    Calculate max pain price (theory: stock gravitates here at expiration).
    
    Returns:
        {
            "symbol": str,
            "expiry": str,
            "current_price": float,
            "max_pain_price": float,
            "distance_to_max_pain": float,  # %
            "max_pain_zone": {
                "low": float,
                "high": float
            },
            "pain_by_strike": [
                {
                    "strike": float,
                    "total_pain": float  # Pain for option writers
                }
            ],
            "interpretation": str
        }
    """
```

---

## Priority 5: Multi-Timeframe Analysis

### 9. multi_timeframe_analysis

```python
@mcp.tool()
def multi_timeframe_analysis(
    ticker: str,
    timeframes: list[Literal["1d", "1wk", "1mo"]] = ["1d", "1wk", "1mo"]
) -> dict[str, Any]:
    """
    Analyze multiple timeframes to identify high-probability setups.
    
    Returns:
        {
            "symbol": str,
            "current_price": float,
            "timeframe_analysis": {
                "1mo": {
                    "trend": str,  # "Bullish" | "Bearish" | "Neutral"
                    "trend_strength": float,  # 0-100
                    "key_support": float,
                    "key_resistance": float,
                    "pattern": str | None
                },
                "1wk": {...},
                "1d": {...}
            },
            "alignment": {
                "score": float,  # 0-100 (100 = all aligned)
                "status": str,  # "Strongly Aligned" | "Mixed" | "Conflicting"
                "aligned_timeframes": list[str]
            },
            "confluence_zones": [
                {
                    "price": float,
                    "type": str,  # "Support" | "Resistance"
                    "timeframes": list[str],
                    "strength": int  # Number of timeframes
                }
            ],
            "trade_direction": {
                "recommended": str,  # "LONG" | "SHORT" | "NEUTRAL"
                "confidence": float,  # 0-100
                "reasoning": str,
                "entry_timeframe": str,  # Best TF for entry
                "stop_timeframe": str  # Best TF for stops
            },
            "top_down_summary": str
        }
    """
```

---

## Priority 6: Short Interest

### 10. analyze_short_interest

```python
@mcp.tool()
def analyze_short_interest(ticker: str) -> dict[str, Any]:
    """
    Track short interest for squeeze potential analysis.
    
    Returns:
        {
            "symbol": str,
            "short_interest": {
                "shares_short": int,
                "float_shares": int,
                "short_percent_float": float,
                "short_ratio": float,  # Days to cover
                "shares_outstanding": int
            },
            "trend": {
                "prior_short_interest": int,
                "change": int,
                "change_percent": float,
                "trend": str  # "Increasing" | "Decreasing" | "Stable"
            },
            "cost_to_borrow": {
                "borrow_rate": float,  # % annual
                "availability": str  # "Easy" | "Moderate" | "Hard"
            },
            "squeeze_metrics": {
                "squeeze_score": float,  # 0-100
                "days_to_cover": float,
                "risk_level": str,  # "High" | "Medium" | "Low"
                "catalyst_needed": bool
            },
            "historical": [
                {
                    "date": str,
                    "short_percent_float": float,
                    "days_to_cover": float
                }
            ],
            "interpretation": str
        }
    """
```

---

## Priority 7: Fundamental Scoring

### 11. calculate_fundamental_scores

```python
@mcp.tool()
def calculate_fundamental_scores(ticker: str) -> dict[str, Any]:
    """
    Calculate composite fundamental quality scores.
    
    Returns:
        {
            "symbol": str,
            "piotroski_f_score": {
                "score": int,  # 0-9
                "components": {
                    "profitability": int,  # 0-4
                    "leverage": int,  # 0-3
                    "operating": int  # 0-2
                },
                "details": {
                    "positive_roe": bool,
                    "positive_operating_cf": bool,
                    "roa_increase": bool,
                    "cf_vs_ni": bool,
                    "debt_decrease": bool,
                    "current_ratio_increase": bool,
                    "shares_decrease": bool,
                    "margin_increase": bool,
                    "turnover_increase": bool
                }
            },
            "altman_z_score": {
                "score": float,
                "zone": str,  # "Safe" (>2.99) | "Grey" (1.81-2.99) | "Distress" (<1.81)
                "bankruptcy_risk": str  # "Low" | "Medium" | "High"
            },
            "quality_score": {
                "score": float,  # 0-100
                "roic": float,
                "roic_trend": str,
                "margin_trend": str,
                "revenue_consistency": float,
                "earnings_quality": float
            },
            "value_score": {
                "score": float,  # 0-100
                "pe_ratio": float,
                "peg_ratio": float,
                "price_to_book": float,
                "price_to_fcf": float,
                "assessment": str
            },
            "growth_score": {
                "score": float,  # 0-100
                "revenue_cagr_3y": float,
                "eps_cagr_3y": float,
                "fcf_growth": float,
                "assessment": str
            },
            "composite_score": {
                "total": float,  # 0-100
                "rating": str,  # "Excellent" | "Good" | "Average" | "Poor"
                "strengths": list[str],
                "weaknesses": list[str]
            }
        }
    """
```

---

## Priority 8: Sector Rotation

### 12. analyze_sector_rotation

```python
@mcp.tool()
def analyze_sector_rotation(
    lookback_period: Literal["1mo", "3mo", "6mo"] = "3mo"
) -> dict[str, Any]:
    """
    Analyze 11 GICS sectors to identify rotation and leaders.
    
    Returns:
        {
            "period": str,
            "sectors": [
                {
                    "name": str,  # "Technology", "Healthcare", etc.
                    "ticker": str,  # Sector ETF ticker
                    "performance": float,  # % return
                    "momentum_score": float,  # 0-100
                    "rank": int,  # 1-11
                    "trend": str,  # "Leading" | "Lagging" | "Improving" | "Weakening"
                    "vs_spy": float,  # Relative performance
                    "recommendation": str  # "Overweight" | "Neutral" | "Underweight"
                }
            ],
            "rotation_stage": {
                "current_stage": str,  # "Early Cycle" | "Mid Cycle" | "Late Cycle" | "Recession"
                "leading_sectors": list[str],
                "lagging_sectors": list[str],
                "money_flow": str  # Where money is moving
            },
            "market_breadth": {
                "advancing_sectors": int,
                "declining_sectors": int,
                "market_health": str  # "Healthy" | "Weak"
            },
            "recommendations": list[str]
        }
    """
```

---

## Priority 9: Economic Calendar

### 13. get_economic_calendar

```python
@mcp.tool()
def get_economic_calendar(
    days_ahead: int = 14,
    importance: Literal["all", "high", "medium", "low"] = "all"
) -> dict[str, Any]:
    """
    Get upcoming economic events and releases.
    
    Returns:
        {
            "period": f"Next {days_ahead} days",
            "events": [
                {
                    "date": str,
                    "time": str,
                    "event": str,
                    "importance": str,  # "High" | "Medium" | "Low"
                    "country": str,
                    "forecast": str | None,
                    "previous": str | None,
                    "impact": str  # Expected market impact
                }
            ],
            "high_impact_dates": list[str],
            "fomc_meetings": [
                {
                    "date": str,
                    "type": str  # "Rate Decision" | "Minutes" | "Speech"
                }
            ],
            "earnings_heavy_dates": list[str],
            "recommendations": str
        }
    """
```

---

## Priority 10: Macro Indicators

### 14. get_macro_indicators

```python
@mcp.tool()
def get_macro_indicators() -> dict[str, Any]:
    """
    Get current macro market indicators.
    
    Returns:
        {
            "treasury_yields": {
                "2y": float,
                "10y": float,
                "30y": float,
                "yield_curve": float,  # 10Y - 2Y
                "curve_status": str  # "Normal" | "Flat" | "Inverted"
            },
            "volatility": {
                "vix": float,
                "vix_percentile": float,  # vs 1-year
                "regime": str  # "Low" | "Normal" | "High" | "Extreme"
            },
            "dollar": {
                "dxy": float,
                "trend": str,
                "impact": str  # On stocks
            },
            "commodities": {
                "gold": float,
                "oil_wti": float,
                "bitcoin": float,
                "trends": str
            },
            "market_breadth": {
                "spy": float,
                "qqq": float,
                "iwm": float,
                "advance_decline": str,
                "market_health": str
            },
            "regime_classification": {
                "growth_regime": str,  # "Growth" | "Slowdown" | "Recession"
                "risk_appetite": str,  # "Risk-On" | "Risk-Off"
                "volatility_regime": str,
                "rate_environment": str  # "Rising" | "Stable" | "Falling"
            },
            "summary": str
        }
    """
```

---

## Helper Tools

### 15. calculate_position_size

```python
@mcp.tool()
def calculate_position_size(
    account_size: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss_price: float,
    atr: float | None = None
) -> dict[str, Any]:
    """
    Calculate optimal position size based on risk parameters.
    
    Returns:
        {
            "account_size": float,
            "risk_per_trade_pct": float,
            "risk_amount": float,  # $ to risk
            "entry_price": float,
            "stop_loss_price": float,
            "risk_per_share": float,
            "shares_to_buy": int,
            "position_value": float,
            "position_pct_of_account": float,
            "atr_based_stop": float | None,  # If ATR provided
            "risk_reward_scenarios": {
                "1R": {"price": float, "gain": float},
                "2R": {"price": float, "gain": float},
                "3R": {"price": float, "gain": float}
            },
            "recommendation": str
        }
    """
```

### 16. analyze_portfolio

```python
@mcp.tool()
def analyze_portfolio(
    positions: list[dict]  # [{ticker, shares, entry_price}, ...]
) -> dict[str, Any]:
    """
    Analyze portfolio risk and diversification.
    
    Args:
        positions: List of position dicts with ticker, shares, entry_price
    
    Returns:
        {
            "total_value": float,
            "total_cost_basis": float,
            "unrealized_pnl": float,
            "unrealized_pnl_pct": float,
            "positions": [
                {
                    "ticker": str,
                    "shares": int,
                    "entry_price": float,
                    "current_price": float,
                    "current_value": float,
                    "pnl": float,
                    "pnl_pct": float,
                    "weight_pct": float
                }
            ],
            "diversification": {
                "sector_exposure": dict[str, float],
                "concentration_risk": str,
                "top_5_weight": float
            },
            "risk_metrics": {
                "portfolio_beta": float,
                "correlation_matrix": dict,
                "diversification_ratio": float
            },
            "recommendations": list[str]
        }
    """
```

---

## Implementation Notes

### Data Source Requirements

1. **Free Sources Available:**
   - Price/volume data: yfinance (current)
   - SEC filings: EDGAR (free)
   - Short interest: FINRA (delayed)
   - Economic calendar: Various free APIs

2. **Paid Sources Needed:**
   - Real-time options data: Polygon.io ($99/mo)
   - Options Greeks: Polygon.io or Intrinio
   - Unusual options activity: Benzinga ($49/mo)
   - Real-time short interest: Ortex ($49/mo)
   - Better fundamentals: Alpha Vantage ($50/mo)

3. **Calculated Metrics:**
   - Technical indicators: Pure Python (no cost)
   - Volume Profile: From price/volume data
   - Fundamental scores: From existing financial data
   - Multi-timeframe: From existing price data

### Recommended Implementation Order

**Week 1-2: Zero Cost**
1. analyze_volatility (uses existing price data)
2. calculate_relative_strength (uses existing price data)
3. multi_timeframe_analysis (uses existing price data)
4. analyze_volume (uses existing price/volume data)
5. calculate_fundamental_scores (uses existing financials)

**Week 3-4: Requires Paid Data**
6. calculate_options_greeks (need better options data)
7. analyze_iv_metrics (need historical IV)
8. detect_unusual_options_activity (need historical OI)
9. analyze_short_interest (need data source)

**Week 5-6: Advanced Features**
10. calculate_max_pain (uses options data)
11. analyze_sector_rotation (uses ETF prices - free)
12. get_economic_calendar (need API)
13. get_macro_indicators (mix of free/paid)

**Week 7-8: Portfolio Tools**
14. calculate_position_size (pure calculation)
15. analyze_portfolio (uses price data)
16. compare_peers (uses existing data)

### Testing Strategy

For each tool:
1. Unit tests with mock data
2. Integration tests with real API calls
3. Performance tests (caching, speed)
4. Documentation with examples
5. Usage in actual reports

---

**Last Updated:** October 31, 2025  
**Status:** Specification Complete - Ready for Implementation
