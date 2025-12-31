# ETF & Mutual Fund Analysis Plan

## Overview

This document outlines the strategy for handling ETFs and Mutual Funds in the Daily Portfolio Report, including recommended new tools for consistent, reliable fund analysis.

---

## Problem Statement

Current tools are designed for individual stocks. When analyzing a portfolio that contains ETFs and Mutual Funds:

1. **Mutual Funds** - No options, no earnings, no fundamentals available
2. **ETFs** - Options available, but no company fundamentals
3. **Different data sources** - yfinance provides limited fund-specific data

---

## Tool Compatibility Matrix

| Tool | Stocks | ETFs | Mutual Funds | Notes |
|------|--------|------|--------------|-------|
| `analyze_options_mcmillan()` | ✅ | ✅ | ❌ | No options for MFs |
| `analyze_technical()` (Al Brooks) | ✅ | ✅ | ⚠️ | NAV-based, limited |
| `calculate_fundamental_scores_tool()` | ✅ | ❌ | ❌ | No company financials |
| `get_earnings_history()` | ✅ | ❌ | ❌ | Not applicable |
| `get_insider_trades()` | ✅ | ❌ | ❌ | Not applicable |
| `analyze_volume_tool()` | ✅ | ✅ | ❌ | MFs have no volume |
| `analyze_volatility_tool()` | ✅ | ✅ | ✅ | Works for all |
| `calculate_relative_strength_tool()` | ✅ | ✅ | ✅ | Works for all |
| `find_support_resistance()` | ✅ | ✅ | ⚠️ | NAV-based |
| `get_price_history()` | ✅ | ✅ | ✅ | Works for all |

---

## Proposed Solution

### 1. Normal Portfolio Report Logic

```
For each position in portfolio:
├── Detect asset type (Stock / ETF / Mutual Fund)
│
├── If STOCK:
│   └── Full Analysis (McMillan + Al Brooks + Fundamentals)
│       - analyze_options_mcmillan() → Options Verdict
│       - analyze_technical() → Al Brooks Verdict
│       - calculate_fundamental_scores_tool() → F-Score, Z-Score
│       - Full decision matrix → HOLD/ADD/TRIM/CLOSE
│
├── If ETF:
│   └── Modified Analysis (Technical + Options, no fundamentals)
│       - analyze_options_mcmillan() → Options Verdict (if liquid)
│       - analyze_technical() → Al Brooks Verdict
│       - analyze_volume_tool() → Volume analysis
│       - calculate_relative_strength_tool() → RS vs benchmark
│       - SKIP: fundamentals, earnings, insiders
│
└── If MUTUAL FUND:
    └── Summary Only (P&L display)
        - Show: Symbol, Shares, Current Value, P&L %
        - Note: "Full analysis available on request"
        - SKIP: All technical/options analysis
```

### 2. ETF Analysis Workflow

For ETFs, use this reduced but effective toolset:

```python
# ETF Analysis (Modified McMillan + Al Brooks)
def analyze_etf(symbol: str):
    # Technical Analysis (Al Brooks works on price action)
    technical = analyze_technical(symbol, period="3mo")

    # Options Analysis (if liquid ETF like SPY, QQQ, IWM)
    try:
        options = analyze_options_mcmillan(symbol)  # direction-independent
        has_options = True
    except:
        has_options = False

    # Volume Analysis
    volume = analyze_volume_tool(symbol)

    # Volatility for position sizing
    volatility = analyze_volatility_tool(symbol)

    # Relative Strength vs appropriate benchmark
    # SPY for sector ETFs, AGG for bond ETFs
    rs = calculate_relative_strength_tool(symbol, benchmark="SPY")

    # Support/Resistance levels
    levels = find_support_resistance(symbol)

    return {
        "technical": technical,
        "options": options if has_options else None,
        "volume": volume,
        "volatility": volatility,
        "relative_strength": rs,
        "levels": levels
    }
```

**ETF Verdict Logic:**
| Options (if available) | Al Brooks | Action |
|------------------------|-----------|--------|
| ✅ SUPPORTS LONG | ✅ LONG | **HOLD/ADD** |
| ✅ SUPPORTS LONG | ❌ SHORT | **WATCH** |
| ❌ OPPOSES LONG | ✅ LONG | **WATCH** |
| ❌ OPPOSES LONG | ❌ SHORT | **TRIM/CLOSE** |
| N/A (illiquid) | ✅ LONG | **HOLD** |
| N/A (illiquid) | ❌ SHORT | **REVIEW** |

### 3. On-Demand Mutual Fund Analysis

When user explicitly requests mutual fund analysis ("analyze my mutual funds"):

#### New Tool: `analyze_mutual_fund()`

```python
def analyze_mutual_fund(ticker: str) -> dict:
    """
    Comprehensive mutual fund analysis using available data.

    Data Sources:
    - yfinance: Price history, expense ratio (if available)
    - Calculated: Returns, risk metrics, benchmark comparison

    Returns:
        dict with performance, risk, and recommendation
    """

    # Get price history for returns calculation
    prices = get_price_history(ticker, period="5y")
    benchmark_prices = get_price_history("SPY", period="5y")  # or appropriate benchmark

    # Calculate returns
    returns = {
        "1yr": calculate_return(prices, "1y"),
        "3yr": calculate_annualized_return(prices, "3y"),
        "5yr": calculate_annualized_return(prices, "5y"),
        "ytd": calculate_return(prices, "ytd")
    }

    # Calculate risk metrics
    risk = {
        "sharpe_ratio": calculate_sharpe(prices),
        "sortino_ratio": calculate_sortino(prices),
        "max_drawdown": calculate_max_drawdown(prices),
        "volatility": calculate_volatility(prices)
    }

    # Benchmark comparison
    vs_benchmark = {
        "alpha": calculate_alpha(prices, benchmark_prices),
        "beta": calculate_beta(prices, benchmark_prices),
        "outperformance_1yr": returns["1yr"] - benchmark_returns["1yr"],
        "outperformance_3yr": returns["3yr"] - benchmark_returns["3yr"]
    }

    # Get expense ratio if available
    info = yf.Ticker(ticker).info
    expense_ratio = info.get("annualReportExpenseRatio", "N/A")

    # Generate recommendation
    recommendation = generate_fund_recommendation(returns, risk, vs_benchmark, expense_ratio)

    return {
        "ticker": ticker,
        "returns": returns,
        "risk_metrics": risk,
        "vs_benchmark": vs_benchmark,
        "expense_ratio": expense_ratio,
        "recommendation": recommendation  # KEEP / WATCH / REPLACE
    }
```

#### New Tool: `compare_mutual_funds()`

```python
def compare_mutual_funds(current_fund: str, candidates: list[str]) -> dict:
    """
    Compare current fund against alternative candidates.

    Scoring System (100 points total):
    - Performance Score (40%): Risk-adjusted returns vs peers
    - Cost Score (30%): Expense ratio comparison
    - Risk Score (30%): Volatility, max drawdown

    Returns:
        Ranked list with KEEP/REPLACE recommendation
    """

    all_funds = [current_fund] + candidates
    analyses = [analyze_mutual_fund(f) for f in all_funds]

    # Score each fund
    for analysis in analyses:
        performance_score = score_performance(analysis["returns"], analysis["risk_metrics"])
        cost_score = score_cost(analysis["expense_ratio"])
        risk_score = score_risk(analysis["risk_metrics"])

        analysis["total_score"] = (
            performance_score * 0.40 +
            cost_score * 0.30 +
            risk_score * 0.30
        )

    # Rank funds
    ranked = sorted(analyses, key=lambda x: x["total_score"], reverse=True)

    # Generate recommendation
    current_rank = next(i for i, a in enumerate(ranked) if a["ticker"] == current_fund)

    if current_rank == 0:
        recommendation = "KEEP"
        rationale = "Current fund is the best option"
    elif current_rank <= 2:
        recommendation = "WATCH"
        rationale = f"Consider switching to {ranked[0]['ticker']}"
    else:
        recommendation = "REPLACE"
        rationale = f"Switch to {ranked[0]['ticker']} for better performance"

    return {
        "current_fund": current_fund,
        "ranking": ranked,
        "recommendation": recommendation,
        "rationale": rationale,
        "suggested_replacement": ranked[0]["ticker"] if recommendation == "REPLACE" else None
    }
```

---

## Mutual Fund Decision Framework

### KEEP Criteria (All must be true)
- Outperforms benchmark over 3+ years (positive alpha)
- Expense ratio < category average (typically < 0.75% for active, < 0.20% for passive)
- Sharpe ratio > 1.0 (good risk-adjusted returns)
- Max drawdown < benchmark max drawdown

### WATCH Criteria (Mixed signals)
- Performance within +/- 2% of benchmark
- Expense ratio near category average
- Sharpe ratio 0.5-1.0

### REPLACE Criteria (Any is true)
- Underperforms benchmark consistently (3+ years negative alpha)
- High expense ratio (> 1% for active, > 0.50% for passive)
- Sharpe ratio < 0.5
- Better alternatives exist in same category with lower fees

---

## Data Source Options for Fund Holdings

### Option A: SEC EDGAR N-PORT Filings (Recommended)

All mutual funds file quarterly N-PORT reports with the SEC containing:
- Full holdings list
- Sector allocation
- Top 10 positions
- Asset breakdown

**Implementation:**
```python
def get_fund_holdings_sec(ticker: str) -> dict:
    """
    Fetch fund holdings from SEC EDGAR N-PORT filings.

    Steps:
    1. Map ticker to CIK (SEC identifier)
    2. Fetch latest N-PORT filing
    3. Parse XML for holdings data

    Returns:
        Holdings, sector allocation, top positions
    """
    # SEC EDGAR API: https://www.sec.gov/cgi-bin/browse-edgar
    # N-PORT filings contain complete holdings
```

**Pros:**
- Official, reliable data
- Free access
- Complete holdings

**Cons:**
- Quarterly updates only (45-60 day lag)
- Complex XML parsing
- Need ticker-to-CIK mapping

### Option B: Morningstar API (Premium)

**Pros:**
- Real-time ratings
- Category rankings
- Manager information
- Holdings data

**Cons:**
- Paid API
- Rate limits

### Option C: Yahoo Finance + Calculated Metrics (Current)

**Pros:**
- Already integrated
- Free
- Real-time prices

**Cons:**
- No holdings data
- Limited fund-specific metrics
- Expense ratio sometimes missing

---

## Implementation Priority

### Phase 1: Immediate (Update Portfolio Report)
1. Add asset type detection in portfolio report workflow
2. Implement ETF analysis with reduced toolset
3. Skip mutual funds with summary-only display
4. Update `PORTFOLIO_INSTRUCTIONS.md` with new logic

### Phase 2: Short-term (New Mutual Fund Tool)
1. Build `analyze_mutual_fund()` using yfinance + calculated metrics
2. Add performance, risk, and benchmark comparison
3. Implement KEEP/WATCH/REPLACE recommendation logic

### Phase 3: Medium-term (Fund Comparison)
1. Build `compare_mutual_funds()` for side-by-side analysis
2. Add scoring system (performance, cost, risk)
3. Generate replacement suggestions

### Phase 4: Future (Holdings Integration)
1. SEC EDGAR N-PORT integration for holdings data
2. Sector allocation analysis
3. Overlap detection between funds

---

## Report Format Updates

### ETF Section in Portfolio Report

```markdown
### [ETF SYMBOL] - [ETF Name]
**Current:** XX shares @ $XX.XX | **P&L:** +/-$XXX (+/-X.X%)

#### Technical Analysis (Al Brooks)
| Metric | Value | Signal |
|--------|-------|--------|
| Always-In | [LONG/SHORT] | Current trend |
| Pattern | [Description] | Quality |
| RSI | XX.X | [Overbought/Neutral/Oversold] |
| RS vs SPY | XX | [Leader/Laggard] |

**Price Action Verdict:** [✅ SUPPORTS LONG / ❌ OPPOSES LONG]

#### Options Analysis (if available)
| Metric | Value | Signal |
|--------|-------|--------|
| IV Rank | XX% | [HIGH/NORMAL/LOW] |
| P/C Ratio | X.XX | [BULLISH/NEUTRAL/BEARISH] |

**Options Verdict:** [✅ SUPPORTS LONG / ❌ OPPOSES LONG / N/A]

**🎯 ACTION: [HOLD / ADD / TRIM / CLOSE]**
```

### Mutual Fund Section (Summary Only)

```markdown
### MUTUAL FUNDS (Summary)

| Symbol | Shares | Value | P&L | P&L % |
|--------|--------|-------|-----|-------|
| VFIAX | XXX | $XX,XXX | +$X,XXX | +X.X% |
| FXAIX | XXX | $XX,XXX | +$X,XXX | +X.X% |

*Full mutual fund analysis available on request: "analyze my mutual funds"*
```

### On-Demand Mutual Fund Report

```markdown
# MUTUAL FUND ANALYSIS REPORT
**Date:** YYYY-MM-DD | **Benchmark:** SPY (S&P 500)

---

## FUND: [TICKER] - [Fund Name]

### Performance
| Period | Fund | Benchmark | Difference |
|--------|------|-----------|------------|
| 1 Year | +XX.X% | +XX.X% | +/-X.X% |
| 3 Year | +XX.X% | +XX.X% | +/-X.X% |
| 5 Year | +XX.X% | +XX.X% | +/-X.X% |
| YTD | +XX.X% | +XX.X% | +/-X.X% |

### Risk Metrics
| Metric | Value | Assessment |
|--------|-------|------------|
| Sharpe Ratio | X.XX | [Good >1.0 / Fair 0.5-1.0 / Poor <0.5] |
| Sortino Ratio | X.XX | [Downside risk adjusted] |
| Max Drawdown | -XX.X% | [Acceptable/High] |
| Volatility | XX.X% | [vs benchmark] |

### Cost Analysis
| Metric | Value | Category Avg |
|--------|-------|--------------|
| Expense Ratio | X.XX% | X.XX% |
| Annual Cost ($10k) | $XXX | $XXX |

### Recommendation: **[KEEP / WATCH / REPLACE]**

**Rationale:** [Explanation based on performance, cost, risk]

**If REPLACE:** Consider [Alternative Fund] with:
- Lower expense ratio (X.XX% vs X.XX%)
- Better 3-year performance (+XX.X% vs +XX.X%)
- Similar risk profile
```

---

## Questions for Review

1. **ETF Liquidity Threshold:** Should we skip options analysis for ETFs with daily volume < 100k?

2. **Mutual Fund Benchmarks:** How should we auto-select benchmarks?
   - Equity funds → SPY
   - Bond funds → AGG
   - International → EFA/VEU
   - Mixed → 60/40 blend

3. **Expense Ratio Thresholds:** What's considered "high"?
   - Passive/Index: > 0.20%
   - Active: > 0.75%
   - Target Date: > 0.50%

4. **Replacement Suggestions:** Should we maintain a curated list of low-cost alternatives?

5. **SEC N-PORT Integration:** Worth the complexity for holdings data?

---

## Summary

| Asset Type | Normal Report | On-Demand |
|------------|---------------|-----------|
| **Stock** | Full McMillan + Al Brooks + Fundamentals | Concise Report (existing) |
| **ETF** | Modified (Technical + Options if liquid) | Same as normal |
| **Mutual Fund** | Summary only (P&L display) | Full performance/risk analysis |

**Next Steps:**
1. Update `PORTFOLIO_INSTRUCTIONS.md` with asset type logic
2. Build `analyze_mutual_fund()` tool
3. Build `compare_mutual_funds()` tool
4. Test with real portfolio data
