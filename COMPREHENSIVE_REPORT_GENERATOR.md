# Comprehensive Trading Report Generator

Generate institutional-grade reports integrating all investor-agent tools with Al Brooks methodology.

**Report Structure:** 12 sections | **Time:** 90 minutes | **Framework:** 9-Phase Institutional

---

## CRITICAL RULES - REAL MONEY, NO EXCEPTIONS

### DATA INTEGRITY (NEVER VIOLATE)

**⛔ ABSOLUTELY FORBIDDEN:**
1. **NEVER fabricate numbers** - If a tool fails, report "DATA UNAVAILABLE" not made-up values
2. **NEVER estimate scores** - Only use actual tool outputs to calculate scores
3. **NEVER guess probabilities** - If historical data is insufficient, say "INSUFFICIENT DATA"
4. **NEVER fill placeholders with invented data** - Leave as "N/A" or "DATA ERROR"

**✅ REQUIRED BEHAVIOR:**
1. If a tool returns an error → Log the error and mark that section as "⚠️ DATA UNAVAILABLE"
2. If a tool returns empty data → State "No data returned" with the specific tool name
3. If async function not awaited → Fix it before proceeding, never use coroutine object as data
4. Every number in the report MUST trace back to a specific tool output

### MARKET HOURS CHECK (MANDATORY)

Before calling intraday functions (`fetch_intraday_1h`, `fetch_intraday_15m`):

```python
from datetime import datetime
import pytz

def is_market_open():
    """Check if US stock market is open"""
    et = pytz.timezone('US/Eastern')
    now = datetime.now(et)

    # Weekend check (Saturday=5, Sunday=6)
    if now.weekday() >= 5:
        return False, "WEEKEND"

    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = now.replace(hour=9, minute=30, second=0)
    market_close = now.replace(hour=16, minute=0, second=0)

    if now < market_open:
        return False, "PRE-MARKET"
    elif now > market_close:
        return False, "AFTER-HOURS"
    else:
        return True, "MARKET OPEN"

# Usage in report:
is_open, status = is_market_open()
if not is_open:
    # SKIP intraday calls entirely
    intraday_note = f"⚠️ [{status}] - Intraday data not available"
else:
    # Call intraday functions
    intraday_1h = fetch_intraday_1h(ticker)
    intraday_15m = fetch_intraday_15m(ticker)
```

### ASYNC FUNCTION HANDLING (MANDATORY)

**Async functions (MUST use asyncio.run()):**
- `get_cnn_fear_greed_index()`
- `get_nasdaq_earnings_calendar()`
- `find_similar_historical_setups()`
- `analyze_ml_enhanced()`
- `calculate_feature_importance_analysis()`
- `get_market_movers()`

**Sync functions (call directly):**
- `get_ticker_data()`
- `get_financial_statements()`
- `calculate_fundamental_scores_tool()`
- `get_options()`
- `get_insider_trades()`
- `get_institutional_holders()`
- `get_earnings_history()`
- `analyze_technical()`
- `find_support_resistance()`
- `analyze_volume_tool()`
- `analyze_volatility_tool()`
- `calculate_relative_strength_tool()`
- `detect_chart_patterns()`
- `analyze_trend_strength()`
- `fetch_intraday_1h()` (sync but needs market open)
- `fetch_intraday_15m()` (sync but needs market open)

### DATA SOURCE TAGGING

Every data point in the report MUST be tagged with its source:

```markdown
**RSI:** 73.78 `[analyze_technical]`
**F-Score:** 3/9 `[calculate_fundamental_scores_tool]`
**Fear & Greed:** 42 `[get_cnn_fear_greed_index]`
**Intraday:** ⚠️ WEEKEND - Data unavailable `[SKIPPED]`
```

### ERROR HANDLING TEMPLATE

When a tool fails:

```markdown
### [Section Name]

⚠️ **DATA ERROR**
- **Tool:** `[tool_name]`
- **Error:** [Error message]
- **Impact:** This section cannot be scored
- **Recommendation:** Re-run when [condition] is met

**Score:** N/A (excluded from weighted calculation)
```

---

## REPORT SECTIONS

### 1. EXECUTIVE SUMMARY ⭐

**Quick Decision Snapshot**

**Recommendation:** [STRONG BUY / BUY / HOLD / SELL / STRONG SELL]

**Target Price:** $XXX.XX (+XX% upside) | **Stop Loss:** $XXX.XX (-X%)

**Investment Thesis (3 bullets):**
1. [Primary catalyst/driver - e.g., "Earnings beat expected in 12 days, 85% historical beat rate"]
2. [Technical setup - e.g., "High-probability Brooks setup (95% context-informed) at demand zone"]
3. [Smart money confirmation - e.g., "Strong institutional accumulation + bullish gamma exposure"]

**Top Risks (2-3 bullets):**
1. [Key risk - e.g., "Binary earnings event creates volatility risk"]
2. [Secondary risk - e.g., "Sector rotation could pressure valuation"]

**Quick Stats:**
- **Weighted Score:** XX/100 (Phases 1-7)
- **Brooks Probability:** XX% (context-informed)
- **Historical Success:** XX% (XX similar setups, p=X.XXX)
- **Expected Return:** +X.X% over X days
- **Risk/Reward:** X.X:1

**Bottom Line:**
[1-2 sentence compelling summary with clear action - e.g., "High-conviction LONG setup with 89/100 score, 95% Brooks probability, and 68% historical validation. Best entry on pullback to $XXX (50% position) with $XXX stop."]

---

### 2. STOCK OVERVIEW

**Company Profile:**
- Ticker, company name, sector, industry
- Market cap, business model summary
- Key highlights and competitive advantages

**Recent Catalysts:**
- Earnings (upcoming or recent < 30 days)
- Product launches, partnerships
- Regulatory approvals
- Management changes

**Tools:** `get_ticker_data()`, `get_earnings_history()`

---

### 3. PRICE ACTION ANALYSIS (Al Brooks - Phase 7)

#### A. Multi-Timeframe Structure

**Monthly/Weekly (Higher Timeframe):**
- Overall trend direction: Bull/Bear/Range
- Major swing highs and lows
- Key support/resistance zones
- Trend strength and phase

**Daily (Trading Timeframe):**
- Current price action structure
- Recent bar-by-bar analysis (last 10-20 bars)
- Pattern identification
- Volume characteristics

**Intraday (15m/1h):**
⚠️ **Check market hours first:**
- If weekend/after-hours: State "⚠️ [Weekend/After Hours] - No intraday data available"
- If market hours: Analyze 15m/1h structure and momentum
- Entry timing patterns only if market is open

**Tools:** `get_price_history()`, `analyze_technical()`, `fetch_intraday_1h()`, `fetch_intraday_15m()`

#### B. Brooks Methodology Analysis ⭐ DETAILED

**Always-In Direction:**
- Current Always-In: [Long/Short]
- Since when: [Date/price level Always-In flipped]
- What would flip Always-In to opposite direction?
- Key price level that changes everything: $XXX.XX

**Market Structure (Detailed):**
- **Trend Type:** [Strong Bull / Weak Bull / Trading Range / Weak Bear / Strong Bear / Channel]
- **Trend Phase:** [Breakout / Acceleration / Exhaustion / Correction]
- **Current Leg:** [First entry / Second entry / Third push / Measured move]
- **Pattern Quality:** [Strong/Medium/Weak] - [Explain why]

**Specific Brooks Setup Identification:**

**PRIMARY PATTERN:** [Name the specific Brooks pattern]
- **Setup Type:** [High 1/High 2/High 3 / Low 1/Low 2/Low 3 / Failed Breakout / Wedge / Flag / Second Entry Long/Short]
- **Pattern Description:** [Detailed explanation of how pattern formed]
- **Legs Count:** [1st leg / 2nd leg / 3rd leg overshoot]
- **Pattern Completion:** [X% complete / Needs confirmation]

**TRAP ANALYSIS:**
- **Bull Trap Risk:** [High/Medium/Low] - [Explain indicators]
- **Bear Trap Risk:** [High/Medium/Low] - [Explain indicators]
- **Failed Breakout:** [Above $XXX or below $XXX creates trap]

**CRITICAL BAR-BY-BAR ANALYSIS (Last 5-10 Bars):**

**Bar [Date] (Most Recent):**
- **Type:** [Strong bull/bear trend bar / Doji / Inside bar / Outside bar / Reversal bar]
- **Close:** [Near high/low/middle] - [What this signals]
- **Tails:** [Upper/lower tail significance]
- **Volume:** [Above/below average] - [Conviction signal]
- **Interpretation:** [What traders are thinking]

**Bar [Date-1]:**
- [Same detailed analysis]

**Bar [Date-2]:**
- [Same detailed analysis]

**Bar [Date-3]:**
- [Same detailed analysis]

**Bar [Date-4]:**
- [Same detailed analysis]

**PATTERN OBSERVATIONS:**
- **Consecutive Bars:** [String of X bull/bear bars suggests Y]
- **Bar Size:** [Getting larger/smaller - momentum building/fading]
- **Overlap:** [Bars overlapping = congestion vs clean trend bars]
- **Tails Pattern:** [Upper tails = selling pressure / Lower tails = buying support]

**FAILED PATTERNS & REVERSALS:**
- **Failed Bullish Patterns:** [List any failed bull setups - Low 1/2/3 failures, wedge failures]
- **Failed Bearish Patterns:** [List any failed bear setups - High 1/2/3 failures]
- **Reversal Signals:** [Two-legged pullback / Micro double top/bottom / Exhaustion gap]

**BROOKS PROBABILITY FACTORS:**
- ✓ **Positive Factors:**
  - [Factor 1: e.g., "Strong trend bars with minimal overlap"]
  - [Factor 2: e.g., "Second entry long at support"]
  - [Factor 3: e.g., "Failed bear breakout creates bull trap"]

- ✗ **Negative Factors:**
  - [Factor 1: e.g., "Many doji bars = uncertainty"]
  - [Factor 2: e.g., "Wedge overshoot suggests exhaustion"]
  - [Factor 3: e.g., "Low volume on breakout = likely fail"]

**📊 PRICE ACTION LEVELS:**

| Level Type | Price | Distance | Description |
|------------|-------|----------|-------------|
| **R3** | $XXX.XX | +XX% | Major resistance / Target 3 |
| **R2** | $XXX.XX | +XX% | Resistance / Target 2 |
| **R1** | $XXX.XX | +XX% | Near resistance / Target 1 |
| **CURRENT** | $XXX.XX | 0% | Entry zone |
| **S1** | $XXX.XX | -X% | Near support / STOP LOSS ⚠️ |
| **S2** | $XXX.XX | -XX% | Support |
| **S3** | $XXX.XX | -XX% | Major support |

**Key Indicators:**
- VWAP: $XXX.XX | EMA20: $XXX.XX | EMA50: $XXX.XX | SMA200: $XXX.XX
- Pattern: [High 2 / Low 1 / Breakout / Wedge]
- Trend: [Bull / Bear / Range] | RS vs SPY: XX

**📊 SUPPLY/DEMAND ZONES:**

| Zone Type | Price Range | Strength | Evidence | Distance |
|-----------|-------------|----------|----------|----------|
| 🔴 Strong Supply | $XXX.XX - $XXX.XX | High | 3 rejections, high volume | +XX% |
| 🟡 Weak Supply | $XXX.XX - $XXX.XX | Low | 1 rejection, low volume | +XX% |
| ⚪ **CURRENT** | **$XXX.XX** | - | - | **0%** |
| 🟡 Weak Demand | $XXX.XX - $XXX.XX | Low | 1 bounce, low volume | -XX% |
| 🟢 Strong Demand | $XXX.XX - $XXX.XX | High | 4 bounces, high volume | -XX% |

**Analysis:**
- Nearest Zone: [Demand/Supply] at $XXX.XX (X% away)
- Probability: XX% price tests nearest zone within 5 days

#### C. Context-Informed Brooks Probability

**Base Pattern Probability:** XX% ([High 2 / Low 1 / Breakout Pullback])

**Context Adjustments (from Phases 1-6):**
- Fundamentals (Phase 1): +XX% (F-Score X/9, strong quality)
- Catalyst (Phase 2): +XX% (earnings in X days)
- Options Flow (Phase 3): +XX% (gamma squeeze setup)
- Insider Buying (Phase 3): +XX% ($XXM cluster buying)
- Institutional Accumulation (Phase 4): +XX% (13F data)
- Technical Strength (Phase 5): +XX% (RS>70, ML confidence)
- Market Context (Phase 6): +XX% (greed>70, sector leading)

**Final Brooks Probability:** XX% (context-informed)

**Tools:** `find_support_resistance()`, `detect_chart_patterns()`, `analyze_trend_strength()`

---

### 4. FUNDAMENTAL ANALYSIS (Phase 1 - 19.6%)

**Valuation Metrics:**
- Forward P/E: XX.X (vs industry avg XX.X)
- Price/Book: X.XX
- EV/EBITDA: XX.X
- Market Cap: $XXB

**Quality Scores:**
- **Piotroski F-Score:** X/9 ([Excellent >7 / Good 5-7 / Poor <5])
- **Altman Z-Score:** X.XX ([Safe >2.99 / Gray 1.81-2.99 / Distress <1.81])

**Profitability:**
- Revenue growth: XX% YoY
- Net margin: XX%
- Operating margin: XX%
- ROE: XX%

**Balance Sheet:**
- Cash: $XXB
- Total debt: $XXB
- Debt/Equity: X.XX
- Current ratio: X.XX

**Tools:** `get_financial_statements()`, `calculate_fundamental_scores_tool()`

---

### 5. SMART MONEY POSITIONING (Phase 3 - 17.9% + Phase 4 - 4.5%)

#### Options Flow Analysis (Phase 3 - 13.4%)

**📊 OPTIONS FLOW (Last 30 days):**

| Type | Contracts | Premium | % of Total | Signal |
|------|-----------|---------|------------|--------|
| Calls | XXXX | $XXM | 65% | Bullish |
| Puts | XXXX | $XXM | 35% | Defensive |
| **P/C Ratio** | **X.XX** | - | - | **[Bullish/Bearish]** |

**Unusual Options Activity:**

| Activity Type | Strike | Contracts | Premium | Interpretation |
|---------------|--------|-----------|---------|----------------|
| 🔵 Call Sweep | $XXX | XXXk | $XXM | Bullish directional bet |
| 🔴 Put Block | $XXX | XXXk | $XXM | Hedging / Protection |

**Gamma Exposure:**
- Max GEX Strike: $XXX (XX% squeeze potential)
- Current vs Max GEX: [Above/Below] → [Squeeze/Crash] setup

**📊 INSIDER TRADES (Last 90 days):**

| Transaction Type | Count | Total Value | % of Total | Interpretation |
|------------------|-------|-------------|------------|----------------|
| Buys | X | $XXM | 80% | Bullish conviction |
| Sells | X | $XXM | 20% | Normal activity |

**Cluster Analysis:**
- Cluster Buying: [Yes/No]
- CEO Activity: $XXM bought at $XXX (confidence signal)
- Directors Activity: $XXM total buys (alignment)

**Smart Money Interpretation:** [Strong bullish / Bearish / Neutral / Mixed] positioning

#### Insider Trading (Phase 3 - 4.5%)

**Recent Activity:**
- Cluster buying: [Yes/No]
- Net insider buying: $XXM
- Timing: [Before catalyst / Routine]
- Significance: [High/Medium/Low]

#### Institutional Holdings (Phase 4 - 4.5%)

**Top 5 Holders:**
1. [Institution]: XX.XM shares (X.X%)
2. [Institution]: XX.XM shares (X.X%)
3. ...

**13F Changes:**
- New positions: X funds
- Increased stakes: X funds (+XX%)
- Decreased stakes: X funds (-XX%)
- Net flow: [Accumulation/Distribution]

**Tools:** `get_options()`, `get_insider_trades()`, `get_institutional_holders()`

---

### 6. CATALYST VERIFICATION (Phase 2 - 15.2%)

**Primary Catalyst:**
- Event: [Earnings / Product Launch / Partnership]
- Date: YYYY-MM-DD (X days away)
- Expected impact: [High/Medium/Low]

**Catalyst Details:**
- Earnings estimate: $X.XX vs $X.XX prior
- Revenue estimate: $XXB (+XX% YoY)
- Historical beat rate: XX% (last 4 quarters)

**Secondary Catalysts:**
- [List other upcoming events < 30 days]

**Tools:** `get_nasdaq_earnings_calendar()`, `get_ticker_data()`

---

### 7. MACRO & SECTOR CONTEXT (Phase 6 - 5.3%) ⭐

**Market Environment:**
- **Fear & Greed Index:** XX ([Extreme Fear <20 / Fear 20-45 / Neutral 45-55 / Greed 55-80 / Extreme Greed >80])
- **Interpretation:** [Risk-on/Risk-off environment]
- **Impact on setup:** [How current sentiment affects trade probability]

**Sector Analysis:**
- **Sector:** [Technology / Healthcare / Finance / etc.]
- **Sector Performance (YTD):** +XX% vs SPY +XX%
- **Sector Trend:** [Leading/Lagging/Inline]
- **Sector Rotation:** [Money flowing in/out]

**📊 PEER COMPARISON:**

```
PEER COMPARISON TABLE:
═══════════════════════════════════════════════════════════════
Ticker | Price | RS | P/E | F-Score | Trend | Recommendation
───────────────────────────────────────────────────────────────
[AAPL] | $XXX  | 82 | XX.X|   8/9   | BULL  | ⭐ PRIMARY
 MSFT  | $XXX  | 75 | XX.X|   7/9   | BULL  | Alternative
 GOOGL | $XXX  | 68 | XX.X|   6/9   | RANGE | Neutral
 META  | $XXX  | 71 | XX.X|   7/9   | BULL  | Alternative
───────────────────────────────────────────────────────────────
SECTOR RANK: X/XX stocks (Top XX%)
```

**Sector Positioning:**
- **Leadership Status:** [Top 10% / Top 25% / Average / Lagging]
- **Relative Strength vs Sector:** XX (>100 = Outperforming)
- **Key Differentiators:** [What makes this stock stand out in sector]

**Macro Tailwinds/Headwinds:**
- ✓ **Tailwinds:** [List favorable macro factors]
- ✗ **Headwinds:** [List unfavorable macro factors]

**Bottom Line:**
[TICKER] is [leading/lagging] its sector with [strong/weak/neutral] relative strength. Current [fear/greed] environment [supports/opposes] the setup.

**Tools:** `get_cnn_fear_greed_index()`, `calculate_relative_strength_tool()`, `get_ticker_data()`

---

### 8. FEATURE IMPORTANCE ANALYSIS (Phase 5 - 5.4% of 17.9%)

**Which indicators matter for THIS stock?**

Ranked by predictive power for 10-day forward returns:

**1. [Feature Name] - Correlation: X.XX** (Strong/Moderate/Weak)
   - Current reading: XX.X
   - Interpretation: Higher values predict [higher/lower] returns
   - Significance: ✓ (p<0.05)
   - Weight: XX%

**2. [Feature Name] - Correlation: X.XX**
   - Current reading: XX.X
   - Interpretation: [Explanation]
   - Significance: ✓/✗
   - Weight: XX%

**3. [Feature Name] - Correlation: X.XX**
   - ...

**Summary:**
- Significant features: X/9 indicators
- Predictability: [HIGH/MODERATE/LOW]
- Key drivers: [Top 2-3 features]

**Actionable Insight:**
For [TICKER], the most important factor is [Feature 1] at [current value], which historically predicts [outcome].

**Tools:** `calculate_feature_importance_analysis()`

---

### 9. ML-ENHANCED ANALYSIS (Phase 5A - 9.8% of 17.9% Technical) ⭐ MANDATORY

**Machine Learning Probability Assessment**

**Triple-Barrier Analysis:**

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Historical Setups Found | XX | Sample size for ML |
| Profitable Setups | XX | Wins based on profit/stop/time barriers |
| Success Rate | XX.X% | Probability of hitting profit before stop |
| Avg Profit (Winners) | +X.X% | Average gain when profitable |
| Avg Loss (Losers) | -X.X% | Average loss when stopped |
| Risk/Reward Ratio | X.X:1 | Asymmetric payoff |
| Avg Holding Days | X.X days | Expected time horizon |
| **Recommendation** | **[FAVORABLE/UNFAVORABLE]** | **[Success rate with R/R context]** |

**Trend-Scanning Statistical Test:**

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Current Trend | [UPTREND/DOWNTREND/RANGE] | Directional bias |
| T-Statistic | X.XX | Strength of trend |
| P-Value | X.XXX | Statistical significance |
| Confidence Level | XX.X% | Probability trend is real |
| Significance | [STATISTICALLY SIGNIFICANT / NOT SIGNIFICANT] | Is trend backed by stats? |
| Lookforward Window | XX days | Prediction horizon |
| **Assessment** | **[Trend description]** | **[Confidence context]** |

**Meta-Labeling Decision:**

| Factor | Value | Impact |
|--------|-------|--------|
| Should Trade? | [YES/NO] | ML model decision |
| ML Confidence | XX% | Model certainty |
| Key Reasoning | [Primary factors] | Why trade/skip |
| Predicted Return | +X.X% | Expected gain |
| Predicted Hold Period | X days | Time to target |
| **Quality Assessment** | **[HIGH/MEDIUM/LOW]** | **Setup quality score** |

**Position Sizing (Kelly Criterion):**

| Metric | Value | Guidance |
|--------|-------|----------|
| Full Kelly Fraction | XX.X% | Aggressive sizing |
| Fractional Kelly (50%) | X.X% | Conservative sizing ⭐ |
| Suggested Position | X.X% of portfolio | Recommended allocation |
| Max Risk Per Share | $X.XX | Stop distance |
| Kelly Stop Price | $XXX.XX | Calculated stop level |

**ML Validation Metrics:**

| Metric | Value | Status |
|--------|-------|--------|
| Deflated Sharpe Ratio | X.XX | Adjusted for multiple trials |
| Probability Significant | XX% | Confidence in results |
| Probability NOT Overfit | XX% | Robustness check |
| **Validation Status** | **[PASS/FAIL]** | **[Sharpe >1.0, PBO <0.30]** |

**ML Feature Importance (This Stock):**

| Feature | Importance Score | Current Reading | Interpretation |
|---------|------------------|-----------------|----------------|
| [Top Feature 1] | XX% | [Value] | [Impact on prediction] |
| [Top Feature 2] | XX% | [Value] | [Impact on prediction] |
| [Top Feature 3] | XX% | [Value] | [Impact on prediction] |
| [Top Feature 4] | XX% | [Value] | [Impact on prediction] |
| [Top Feature 5] | XX% | [Value] | [Impact on prediction] |

**ML Summary:**
- **Success Probability:** XX% (based on XX historical setups with similar ML profile)
- **Statistical Confidence:** XX% (trend is statistically significant with p=X.XXX)
- **Meta-Model Decision:** [TAKE TRADE / SKIP TRADE] with XX% confidence
- **Expected Outcome:** +X.X% return over X days (based on ML predictions)
- **Position Sizing:** X.X% of portfolio (fractional Kelly)

**ML Interpretation:**
[2-3 sentences explaining what the ML models indicate about this setup, combining triple-barrier success rate, trend-scanning significance, and meta-label quality assessment]

**Tools:** `analyze_ml_enhanced()`, `calculate_feature_importance_analysis()`

---

### 10. HISTORICAL CONFIRMATION (Phase 8 - 0% Weight) ⚠️ MANDATORY

**⚠️ CRITICAL:** Confirmation only, NOT weighted in final score

**Similar Historical Setups (2-year lookback):**

**📊 Results:**
- **Similar Setups Found:** XX setups
- **Success Rate (10-day):** XX.X% profitable
- **Average Return:** +X.X%
- **Win/Loss:** XX wins, XX losses
- **Best Return:** +X.X%
- **Worst Return:** -X.X%
- **Risk/Reward:** X.X:1

**📈 Statistical Validation:**
- **95% Confidence Interval:** [XX%, XX%]
- **P-Value:** X.XXX (✓ significant if <0.05)
- **Sample Size:** XX setups (note count for confidence assessment)
- **Statistical Significance:** ✓ YES / ✗ NO

**Confirmation Status:**

✅ **STRONG** (≥60% success rate): Analysis validated by historical evidence
⚠️ **WEAK** (<60% success rate): Conflicts with analysis, lower confidence
⚠️ **LIMITED** (low sample count): Use with caution, note sample size

**Comparison to Baseline:**
- ML-Enhanced System: XX.X% accuracy
- Simple Indicators: XX.X% accuracy
- Improvement: +XX.X percentage points

**📌 Bottom Line:** Historical data shown for validation, NOT driving score

**Tools:** `find_similar_historical_setups()`

---

### 11. TRADE PLAN 🎯 (Phase 9)

#### A. Direction Decision

**RECOMMENDATION: [LONG / SHORT / WAIT]**

**Rationale Checklist:**
- ✓/✗ Technical breakout/breakdown confirmed
- ✓/✗ Fundamental quality (F-Score ≥5, Z-Score >1.81)
- ✓/✗ Market leader (RS >70 for LONG, <30 for SHORT)
- ✓/✗ Volume confirmation (>XX% avg)
- ✓/✗ Positive catalysts (<30 days)
- ✓/✗ Favorable risk/reward (≥2:1)
- ! Concerns: [List any red flags]

#### B. Entry Scenarios

**📊 POSITION SIZING LADDER:**

**Risk Per Trade:** $X,XXX (1% of account)

**Entry Strategy:**

| Entry | % Position | Price | Shares | Capital | Type |
|-------|------------|-------|--------|---------|------|
| Entry 1 | 33% | $XXX.XX | XXX | $X,XXX | Aggressive (now) |
| Entry 2 ⭐ | 50% | $XXX.XX | XXX | $X,XXX | Pullback (BEST) |
| Entry 3 | 17% | $XXX.XX | XXX | $X,XXX | Breakout (confirmation) |
| **TOTAL** | **100%** | - | **XXX** | **$XX,XXX** | **X% of account** |

**Exit Strategy:**

| Exit Level | % to Sell | Price | Gain | Profit | Description |
|------------|-----------|-------|------|--------|-------------|
| PT1 | 33% | $XXX.XX | +X% | $X,XXX | First target |
| PT2 | 33% | $XXX.XX | +XX% | $X,XXX | Second target |
| PT3 | 34% | $XXX.XX | +XX% | $X,XXX | Final target |
| **STOP** | **100%** | **$XXX.XX** | **-X%** | **-$XXX** | **Max loss** |

**Risk/Reward Ratio:** X.X:1 (Risk $XXX to make $X,XXX avg)

**Scenario 1: Aggressive Entry (33%)**
- Entry: $XX-XX (current area)
- Thesis: Breakout continuation
- Stop: $XX (2.5x ATR below)
- Risk: $X per share (X%)

**Scenario 2: Pullback Entry (50%) ⭐ BEST**
- Entry: $XX-XX (support test)
- Thesis: Brooks "Second Entry Long"
- Stop: $XX (below key level)
- Risk: $X per share (X%)

**Scenario 3: Breakout Confirmation (17%)**
- Entry: $XX+ (above resistance)
- Thesis: Measured move
- Stop: $XX (swing point)
- Risk: $X per share (X%)

#### C. Probability Assessment

**WEIGHTED SCORE (Phases 1-7):**

| Phase | Raw Score | Weight | Weighted Points |
|-------|-----------|--------|-----------------|
| Fundamentals | XX/100 | 19.6% | XX pts |
| Catalysts | XX/100 | 15.2% | XX pts |
| Options Flow | XX/100 | 13.4% | XX pts |
| Insider Trading | XX/100 | 4.5% | XX pts |
| Institutional Holdings | XX/100 | 4.5% | XX pts |
| Technical Analysis | XX/100 | 17.9% | XX pts |
| └─ ML Signals (9.8%) | - | - | - |
| └─ Indicators (8.1%) | - | - | - |
| Market Context | XX/100 | 5.3% | XX pts |
| Al Brooks | XX% | 19.6% | XX pts |
| **TOTAL** | - | **100.0%** | **XX/100** |

**NOTE:** Weights sum to exactly 100% - NO normalization needed

**PHASE 7: BROOKS PROBABILITY (Context-Informed):**

| Component | Value | Impact |
|-----------|-------|--------|
| Base Pattern | XX% | [High 2/Low 1/etc.] |
| + Fundamentals | +XX% | F-Score X/9 |
| + Catalyst | +XX% | X days to event |
| + Options | +XX% | Gamma squeeze |
| + Insiders | +XX% | $XXM buying |
| + Institutions | +XX% | Accumulation |
| + Technicals | +XX% | RS>70, breakout |
| + Market | +XX% | Greed>70, sector lead |
| **Final Brooks Probability** | **XX%** | **(vs XX% base)** |

**PHASE 8: HISTORICAL CONFIRMATION (0% Weight):**

| Metric | Value | Status |
|--------|-------|--------|
| Success Rate | XX.X% | XX similar setups |
| Sample Size | XX setups | [✓ Adequate / ✗ Insufficient] |
| Statistical Significance | p=X.XXX | [✓ Significant / ✗ Not significant] |
| **Confirmation** | - | **[STRONG ✓ / WEAK ⚠️ / INSUFFICIENT ✗]** |

**FINAL RECOMMENDATION:**

| Element | Value |
|---------|-------|
| **Decision** | **[STRONG BUY/BUY/WAIT/SKIP]** |
| **Confidence** | **[HIGH/MEDIUM/LOW]** |
| **Reasoning** | Score XX/100 + Brooks XX% + Historical XX% validates |

**Decision Matrix:**

| Score | Brooks | Historical | Decision |
|-------|--------|------------|----------|
| >80 | >60% | >60% | STRONG BUY/SELL ✓ |
| >80 | >60% | <60% | BUY/SELL ⚠️ |
| 70-80 | >60% | >60% | BUY/SELL ✓ |
| 70-80 | >60% | <60% | CONSIDER ⚠️ |
| <70 | >60% | Any | WAIT ⚠️ |
| Any | <50% | Any | SKIP ✗ |

#### D. Scenario Analysis ⭐

**Expected Value Calculation:**

**BEST CASE (20% probability):**
- **Trigger:** Earnings beat + guidance raise + sector momentum
- **Target:** $XXX.XX (+XX% from entry)
- **Timeline:** X-XX days
- **Conditions:** Strong volume >200% avg, immediate breakout
- **Expected Value:** +XX% × 20% = +X.X%

**BASE CASE (60% probability):**
- **Trigger:** As expected - setup plays out normally
- **Target:** $XXX.XX (+XX% from entry)
- **Timeline:** X-XX days
- **Conditions:** Normal volume confirmation, gradual move
- **Expected Value:** +XX% × 60% = +X.X%

**WORST CASE (20% probability):**
- **Trigger:** Catalyst miss / Setup invalidation / Market selloff
- **Loss:** $XXX.XX (-X% from entry to stop)
- **Timeline:** X-X days
- **Conditions:** Volume dries up, support breaks, momentum fades
- **Expected Value:** -X% × 20% = -X.X%

**TOTAL EXPECTED VALUE:** +X.X% (Best) + X.X% (Base) + (-X.X%) (Worst) = **+X.X%**

**Risk-Adjusted Decision:**
- **Win Probability:** 80% (Best + Base cases)
- **Loss Probability:** 20% (Worst case)
- **Expected Return:** +X.X% weighted average
- **Kelly Position Size:** X.X% of portfolio

**Scenario Interpretation:**
[1-2 sentence summary - e.g., "Asymmetric risk/reward with 80% win probability and +5.8% expected value. Base case alone justifies position, while worst case limited by disciplined stop."]

**Tools:** `analyze_volatility_tool()`, `find_support_resistance()`, `analyze_ml_enhanced()`

---

### 12. TECHNICAL INDICATORS (Phase 5B - 8.1% of 17.9% Technical)

**Key Levels:**
- **Resistance:** R1 $XXX, R2 $XXX, R3 $XXX
- **Support:** S1 $XXX (STOP), S2 $XXX, S3 $XXX
- **VWAP:** $XXX
- **Moving Averages:** EMA20 $XXX, EMA50 $XXX, SMA200 $XXX

**Relative Strength:**
- RS Score: XX vs SPY
- Status: [Leader >70 / Neutral 50-70 / Laggard <50]

**Volume Analysis:**
- Current vs 20-day avg: XX%
- OBV trend: [Accumulation/Distribution]
- VWAP position: [Above/Below]

**Volatility:**
- ATR: $X.XX (X.X%)
- ATR-based stop: 2.5x ATR = $X.XX below entry

**Tools:** `analyze_technical()`, `calculate_relative_strength_tool()`, `analyze_volume_tool()`, `analyze_volatility_tool()`

---

## QUALITY CHECKLIST

Before publishing:

**Framework Compliance:**
- [ ] All 9 phases executed in order
- [ ] Phase 7 (Brooks) ran AFTER Phases 1-6
- [ ] Phase 8 (Historical) ran AFTER Phase 7
- [ ] Historical labeled "CONFIRMATION (0% weight)"
- [ ] Weighted score uses Phases 1-7 only

**Visual Charts:**
- [ ] Price Action Chart included (Section 3)
- [ ] Supply/Demand Zones included (Section 3)
- [ ] Position Sizing Ladder included (Section 11)
- [ ] Block Order Flow included (Section 5)
- [ ] Peer Comparison Table included (Section 7)
- [ ] ML Analysis Tables included (Section 9)

**Content Quality:**
- [ ] Executive Summary included (Section 1) with quick decision snapshot
- [ ] Macro & Sector Context standalone (Section 7) with peer comparison
- [ ] ML-Enhanced Analysis included (Section 9) with all tables
- [ ] Scenario Analysis included (Section 11) with expected value calculation
- [ ] Brooks probability = context-informed (base + adjustments)
- [ ] Historical shown separately (NOT combined with Brooks)
- [ ] Decision matrix applied
- [ ] All support/resistance levels specific ($XXX.XX)
- [ ] Position sizing calculated (ATR-based)
- [ ] Risk/reward ratio calculated (min 2:1)

**Probability Communication:**
- [ ] Never claim certainty ("will go up")
- [ ] Always cite sample size (XX setups)
- [ ] Always show statistical significance (p-value)
- [ ] Note sample size for confidence assessment

**No Circular Logic:**
- [ ] Historical NOT used for Brooks probability
- [ ] Historical NOT in weighted score (0%)
- [ ] Clear separation: Analysis → Confirmation → Score

---

**Time:** 90 minutes for institutional-grade report with embedded visuals
