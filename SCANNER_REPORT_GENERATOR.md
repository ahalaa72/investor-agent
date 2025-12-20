# Market Opportunity Scanner Report Generator

Scan markets for top LONG and SHORT candidates with detailed analysis per stock.

**Structure:** 4 Sections per Stock (Overview + Catalyst + McMillan Options + Al Brooks) | **Time:** 50-70 minutes | **Stocks:** Top 3 LONG + Top 3 SHORT

**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy)

---

## 10-PHASE FRAMEWORK WEIGHTS (100.0%)

| Phase | Weight | Description |
|-------|--------|-------------|
| 1. Fundamentals | 19.6% | F-Score, Z-Score, quality metrics |
| 2. Catalysts | 15.2% | Earnings, events, timing |
| 3. McMillan Options | 13.4% | IV Rank, P/C Ratio, Max Pain, UOA |
| 4. Insiders | 4.5% | Cluster buying/selling patterns |
| 5. Institutions | 4.5% | 13F holdings, accumulation/distribution |
| 6. Technical | 17.9% | ML signals (9.8%) + Indicators (8.1%) |
| 7. Market Context | 5.3% | Fear/Greed, sector analysis |
| 8. Al Brooks | 19.6% | Context-informed price action |
| 9. Historical | 0% | Confirmation only, not weighted |

**Weight Sum:** 19.6 + 15.2 + 13.4 + 4.5 + 4.5 + 17.9 + 5.3 + 19.6 = **100.0%**

---

## CRITICAL RULES

### Data Integrity
- **NEVER fabricate numbers** - If tool fails, report "DATA UNAVAILABLE"
- **Every number MUST have [tool_name] source tag**
- **Async functions need asyncio.run():** get_cnn_fear_greed_index, find_similar_historical_setups, analyze_ml_enhanced, get_nasdaq_earnings_calendar

### Workflow
1. **Scan first** using `scan_market_opportunities(market="america", top_n=3)`
2. **Analyze each candidate** in order (LONG 1-3, then SHORT 1-3)
3. **No pausing** - Generate full report continuously
4. **Default market: US only** - Use Canada only if user explicitly requests

---

## REPORT TEMPLATE

```markdown
# MARKET OPPORTUNITY SCAN

**Date:** YYYY-MM-DD HH:MM ET
**Market:** US Stocks (Price > $2, MCap > $1B)
**Scanned:** X,XXX stocks

---

# TOP 3 LONG CANDIDATES

═══════════════════════════════════════════════════════════════
## LONG #1: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

**Price:** $XX.XX | **Score:** XX/100 | **Signal:** [STRONG BUY / BUY / WATCH]

---

### SECTION A: COMPANY OVERVIEW

**Business Profile:**
- **Sector:** [Technology / Healthcare / etc.] [get_ticker_data]
- **Industry:** [Specific industry] [get_ticker_data]
- **Market Cap:** $XXB [get_ticker_data]
- **Employees:** XX,XXX [get_ticker_data]

**What They Do:**
[2-3 sentence description of the company's core business, products/services, and competitive position. This should be enough for someone unfamiliar with the stock to understand what they're potentially buying.]

**Key Fundamentals:**
- **Revenue (TTM):** $XXB (+/-XX% YoY) [get_ticker_data]
- **EPS (TTM):** $X.XX [get_ticker_data]
- **P/E Ratio:** XX.X (vs industry XX.X) [get_ticker_data]
- **Profit Margin:** XX.X% [get_ticker_data]
- **ROE:** XX.X% [get_ticker_data]

**Quality Scores:**
- **Piotroski F-Score:** X/9 [STRONG ≥7 / MODERATE 5-6 / WEAK <5] [calculate_fundamental_scores_tool]
- **Altman Z-Score:** X.XX [SAFE >2.99 / GREY 1.81-2.99 / DISTRESS <1.81] [calculate_fundamental_scores_tool]

**Recent Headlines:**
1. "[Headline 1]" - [Source, Date] [get_ticker_data]
2. "[Headline 2]" - [Source, Date] [get_ticker_data]

---

### SECTION B: CATALYST VERIFICATION (Phase 2)

**Why Is This Stock Moving?**

#### Primary Catalyst
- **Event:** [Earnings / Product Launch / FDA Approval / M&A / Partnership / Sector Momentum]
- **Date:** YYYY-MM-DD (X days away)
- **Expected Impact:** [HIGH / MEDIUM / LOW]

#### Catalyst Details [get_nasdaq_earnings_calendar, get_ticker_data]

**Upcoming Earnings:**
- **Report Date:** [Date] (X days away) [get_nasdaq_earnings_calendar]
- **EPS Estimate:** $X.XX vs $X.XX prior quarter [get_ticker_data]
- **Revenue Estimate:** $XXB (+XX% YoY expected) [get_ticker_data]
- **Surprise History:** [Typically beats / misses / meets]

**Historical Earnings Performance:** [get_earnings_history]

| Quarter | Date | EPS Est | EPS Actual | Surprise | Revenue |
|---------|------|---------|------------|----------|---------|
| Q3 2024 | MM/DD | $X.XX | $X.XX | +X.X% ✅ | $XXB |
| Q2 2024 | MM/DD | $X.XX | $X.XX | +X.X% ✅ | $XXB |
| Q1 2024 | MM/DD | $X.XX | $X.XX | -X.X% ❌ | $XXB |
| Q4 2023 | MM/DD | $X.XX | $X.XX | +X.X% ✅ | $XXB |

**Historical Beat Rate:** XX% (X/4 quarters beat) [get_earnings_history]

#### Secondary Catalysts (< 30 days) [get_ticker_data]
- [Event 1]: [Date] - [Description]
- [Event 2]: [Date] - [Description]
- [Recent News]: "[Headline]" - [Impact assessment]

#### Smart Money Verification

**Insider Trading (90d):** [get_insider_trades]
- **Net Activity:** [Net Buying $XXM / Net Selling $XXM / No Activity]
- **Notable Transactions:**
  - [Role] [bought/sold] $XXM at $XX.XX on MM/DD
  - [Role] [bought/sold] $XXM at $XX.XX on MM/DD
- **Cluster Buying:** [Yes - X insiders within 2 weeks / No]
- **Interpretation:** [Bullish conviction / Routine / Concerning]

**Institutional Holdings:** [get_institutional_holders]
- **Top Holders:** [Vanguard XX%, BlackRock XX%, State Street XX%]
- **13F Changes (Latest Quarter):**
  - New positions: X funds
  - Increased stakes: X funds (+XX% net)
  - Decreased stakes: X funds (-XX% net)
- **Net Flow:** [ACCUMULATION / DISTRIBUTION / MIXED]

**Options Flow:** [get_options]
- **Put/Call Ratio:** X.XX [Bullish <0.7 / Neutral 0.7-1.0 / Bearish >1.0]
- **Open Interest:** XXX,XXX calls vs XXX,XXX puts
- **Unusual Activity:** [Describe any notable sweeps, blocks, or unusual volume]
- **Gamma Exposure:** [If significant, note max pain strike]

#### Catalyst Score: XX/100

**Scoring Breakdown:**
- Earnings proximity (0-30 pts): XX pts
- Historical beat rate (0-25 pts): XX pts
- Insider activity (0-20 pts): XX pts
- Institutional flow (0-15 pts): XX pts
- Options sentiment (0-10 pts): XX pts

**Catalyst Verdict:** [STRONG / MODERATE / WEAK / NO CATALYST]

[1-2 sentences summarizing why this stock is an opportunity RIGHT NOW. What's the thesis driving the move?]

---

### SECTION C: McMILLAN OPTIONS STRATEGY ⭐ NEW

**Options Analysis:** [analyze_options_mcmillan]

#### IV Environment
- **Current IV:** XX.X%
- **IV Rank:** XX% [HIGH >70 sell premium / LOW <30 buy premium / NORMAL 30-70]
- **IV Percentile:** XX%
- **Divergence Check:** [ALIGNED / DIVERGENT: recent spike vs historical norm]
  - Both HIGH = Genuinely elevated → Premium selling optimal
  - Both LOW = Genuinely suppressed → Premium buying optimal
  - Rank HIGH + Percentile LOW = Recent spike → Watch for mean reversion
  - Rank LOW + Percentile HIGH = Unusual compression → Potential breakout
- **Environment:** [HIGH_IV / LOW_IV / NORMAL_IV]

#### Put/Call Analysis
- **Volume P/C Ratio:** X.XX
  - Raw Sentiment: [Bullish <0.7 / Neutral 0.7-1.0 / Bearish >1.0]
  - **Contrarian Signal:** [BULLISH if >1.2 / BEARISH if <0.5 / NO SIGNAL 0.5-1.2]
- **OI P/C Ratio:** X.XX [Positioning bias]
- **Sentiment:** [EXTREMELY_BEARISH / BEARISH / NEUTRAL / BULLISH / EXTREMELY_BULLISH]

#### Open Interest & Max Pain
- **Max Pain Strike:** $XXX.XX
- **Distance to Max Pain:** +/-XX.X% ([Above/Below/At] price)
- **Days to Expiry:** XX days
- **Aggregate OI:** XXX,XXX contracts [HIGH >100k / MEDIUM 25-100k / LOW <25k]
- **Max Pain Reliability:** [HIGH (near expiry + high OI) / MEDIUM / LOW (early cycle)]
- **Key Call Wall:** $XXX (XXX,XXX OI)
- **Key Put Wall:** $XXX (XXX,XXX OI)
- **OI Bias:** [BULLISH / BEARISH / NEUTRAL]

#### Smart Money (Unusual Activity)
- **UOA Detection:** [X trades with Vol > 2x OI]
- **Signal:** [BULLISH / BEARISH / MIXED / NO_SIGNAL]
- **Notable Activity:** [Description of unusual trades]

#### McMillan Strategy Recommendation
```
IV Environment: [HIGH / LOW / NORMAL]
Direction:      [LONG / SHORT / NEUTRAL]

RECOMMENDED: [Strategy Name]
Rationale:  [McMillan-based explanation]

Alternative Strategies:
1. [Strategy 1] - [Risk profile]
2. [Strategy 2] - [Risk profile]

Suggested Strikes:
- ATM:      $XXX
- OTM Call: $XXX
- OTM Put:  $XXX
```

#### Options Score: XX/100 [CONFIDENCE]

**McMillan Reference:** Chapter [X] - [Topic]

---

### SECTION D: AL BROOKS PRICE ACTION ANALYSIS

**Technical Snapshot:** [analyze_technical]
- **RSI:** XX.X [Oversold <30 / Neutral 30-70 / Overbought >70]
- **MACD:** [Bullish / Bearish / Neutral] (MACD: X.XX, Signal: X.XX)
- **Price vs EMA20:** +/-XX.X%
- **Price vs EMA50:** +/-XX.X%
- **Price vs SMA200:** +/-XX.X%

**Relative Strength:** [calculate_relative_strength_tool]
- **RS Score vs SPY:** XX [LEADER >70 / NEUTRAL 50-70 / LAGGARD <50]
- **Interpretation:** [Outperforming / Inline with / Underperforming] the market

**Volume Analysis:** [analyze_volume_tool]
- **Relative Volume:** X.Xx average
- **OBV Trend:** [Accumulation / Distribution / Neutral]
- **Interpretation:** [Smart money buying / selling / neutral]

**ML Prediction:** [analyze_ml_enhanced]
- **Trend Direction:** [UPTREND / DOWNTREND / SIDEWAYS]
- **Confidence:** XX%
- **Predicted Return:** +/-X.X% over X days

---

#### AL BROOKS METHODOLOGY

**Always-In Direction:**
- **Current:** [LONG / SHORT] since [Date/Price level]
- **Reason:** [Why the Always-In direction is what it is]
- **Flip Level:** Close [above/below] $XX.XX would flip to [opposite direction]

**Market Structure:**
- **Trend Type:** [Strong Bull / Weak Bull / Trading Range / Weak Bear / Strong Bear]
- **Trend Phase:** [Breakout / Acceleration / Exhaustion / Correction]
- **Pattern Quality:** [STRONG / MODERATE / WEAK]

**Primary Brooks Pattern:**
```
PATTERN: [High 1 / High 2 / High 3 / Low 1 / Low 2 / Low 3 / Breakout Pullback /
          Wedge / Channel / Double Bottom / Double Top / Failed Breakout]

Formation:
- First leg: $XX.XX → $XX.XX (XX bars)
- Pullback to: $XX.XX (X.X% retracement)
- Current leg: In progress, target $XX.XX

Completion: [XX% complete / Triggered / Needs confirmation]
```

**Bar-by-Bar Analysis (Last 5 Bars):**

| Date | Bar Type | Close Position | Volume | Signal |
|------|----------|----------------|--------|--------|
| [Most Recent] | [Strong Bull/Bear/Doji/Inside] | [Near High/Low/Middle] | [Above/Below Avg] | [What it means] |
| [Date-1] | [Type] | [Position] | [Volume] | [Interpretation] |
| [Date-2] | [Type] | [Position] | [Volume] | [Interpretation] |
| [Date-3] | [Type] | [Position] | [Volume] | [Interpretation] |
| [Date-4] | [Type] | [Position] | [Volume] | [Interpretation] |

**Pattern Observation:**
[What does this sequence of bars tell us? Momentum building? Exhaustion? Consolidation?]

**Trap Analysis:**
- **Bull Trap Risk:** [HIGH / MEDIUM / LOW] - [Reason]
- **Bear Trap Risk:** [HIGH / MEDIUM / LOW] - [Reason]

**Brooks Probability Calculation:**

**Base Probability:** XX% (for [Pattern Name])

✓ **Positive Factors (Adding to probability):**
- [Factor 1]: +X% (e.g., "Strong trend bars with follow-through")
- [Factor 2]: +X% (e.g., "RS leader outperforming SPY")
- [Factor 3]: +X% (e.g., "ML prediction aligned with direction")
- [Factor 4]: +X% (e.g., "Volume confirming the move")

✗ **Negative Factors (Reducing probability):**
- [Risk 1]: -X% (e.g., "Approaching resistance")
- [Risk 2]: -X% (e.g., "RSI overbought")

**FINAL BROOKS PROBABILITY: XX%** [LONG/SHORT]

---

**TRADE LEVELS:**

```
    TARGET 2:  $XX.XX ━━━━━━━━ (+XX.X%) Extended target
    TARGET 1:  $XX.XX ━━━━━━━━ (+XX.X%) Primary target
    ─────────────────────────────────────────────────
    CURRENT:   $XX.XX ═════════
    ─────────────────────────────────────────────────
    ENTRY:     $XX.XX ┅┅┅┅┅┅┅┅ Best entry zone
    STOP:      $XX.XX ━━━━━━━━ (-X.X%) Maximum risk
```

**Risk/Reward:** X.X:1

**Action Summary:**
- **Setup:** [Pattern name with confidence]
- **Entry:** [Specific price or condition]
- **Stop:** $XX.XX (-X.X% from entry)
- **Target 1:** $XX.XX (+X.X%)
- **Target 2:** $XX.XX (+XX.X%)

---

═══════════════════════════════════════════════════════════════
## LONG #2: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D format]

---

═══════════════════════════════════════════════════════════════
## LONG #3: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D format]

---

# TOP 3 SHORT CANDIDATES

═══════════════════════════════════════════════════════════════
## SHORT #1: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D format - Note: For shorts, look for:
- Overbought RSI (>70)
- Bearish MACD
- Distribution volume
- RS Laggard (<50)
- ML downtrend prediction
- Bear patterns (Low 1/2/3, Failed Breakout, Wedge Top)
- High IV environment for bear spreads ⭐ McMillan
- Contrarian bearish P/C signal ⭐ McMillan]

---

═══════════════════════════════════════════════════════════════
## SHORT #2: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D format]

---

═══════════════════════════════════════════════════════════════
## SHORT #3: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D format]

---

# SCAN SUMMARY

## Top Picks Ranking

| Rank | Dir | Ticker | Score | Brooks | Options | Strategy | R/R |
|------|-----|--------|-------|--------|---------|----------|-----|
| 1 | LONG | [XXX] | XX/100 | XX% | XX/100 | [Strategy] | X.X:1 |
| 2 | LONG | [XXX] | XX/100 | XX% | XX/100 | [Strategy] | X.X:1 |
| 3 | LONG | [XXX] | XX/100 | XX% | XX/100 | [Strategy] | X.X:1 |
| 1 | SHORT | [XXX] | XX/100 | XX% | XX/100 | [Strategy] | X.X:1 |
| 2 | SHORT | [XXX] | XX/100 | XX% | XX/100 | [Strategy] | X.X:1 |
| 3 | SHORT | [XXX] | XX/100 | XX% | XX/100 | [Strategy] | X.X:1 |

## Best Opportunities

**Top LONG:** [TICKER] - [1 sentence why]
**Top SHORT:** [TICKER] - [1 sentence why]

## Market Context

- **Fear & Greed Index:** XX [get_cnn_fear_greed_index]
- **Market Bias:** [Risk-On favors LONGS / Risk-Off favors SHORTS / Neutral]

---

*Scan completed at [TIME]. All data from MCP investor-agent tools.*
```

---

## WORKFLOW

### Step 1: Run the Scanner (2 min)
```python
# Call the scan tool with US market (default)
scan_market_opportunities(
    market="america",      # Default US only
    min_price=2.0,
    min_market_cap=1_000_000_000,
    top_n=3
)

# Or for Canada if user requests:
scan_market_opportunities(market="canada", top_n=3)
scan_market_opportunities(market="both", top_n=3)
```

### Step 2: Analyze Each Candidate (8 min per stock)

For each of the 6 candidates (3 LONG + 3 SHORT):

```python
# Section A: Company Overview
get_ticker_data(ticker)                        # Company info, fundamentals, news
calculate_fundamental_scores_tool(ticker)      # F-Score, Z-Score

# Section B: Catalyst Verification (Same methodology as Comprehensive Report)
asyncio.run(get_nasdaq_earnings_calendar(ticker))  # Upcoming earnings date (async)
get_earnings_history(ticker)                       # Historical beat rate, surprises
get_ticker_data(ticker)                            # Secondary catalysts, news
get_insider_trades(ticker)                         # Insider buying/selling patterns
get_institutional_holders(ticker)                  # 13F accumulation/distribution

# Section C: McMillan Options Strategy ⭐ NEW
analyze_options_mcmillan(ticker, direction="LONG")  # Full McMillan analysis
# Returns: IV Rank, P/C Ratio, Max Pain, UOA, Strategy Recommendation

# Section D: Al Brooks Analysis
analyze_technical(ticker)                          # RSI, MACD, EMAs
calculate_relative_strength_tool(ticker, benchmark="SPY")  # RS vs market
analyze_volume_tool(ticker)                        # OBV, accumulation/distribution
asyncio.run(analyze_ml_enhanced(ticker))           # ML trend prediction (async)
```

### Step 3: Generate Brooks Analysis (AI interpretation)

For each stock, interpret the data through Al Brooks methodology:
- Identify the pattern
- Read the bars
- Calculate context-adjusted probability
- Set entry/stop/targets

### Step 4: Compile Summary

Create the final ranking table and best opportunities.

---

## TOOL REFERENCE

### Scanner Tool
| Tool | Purpose |
|------|---------|
| `scan_market_opportunities()` | Find top LONG/SHORT candidates |

### Section A: Company Overview
| Tool | Data |
|------|------|
| `get_ticker_data()` | Company info, fundamentals, news |
| `calculate_fundamental_scores_tool()` | F-Score, Z-Score |

### Section B: Catalyst Verification (Phase 2)
| Tool | Data |
|------|------|
| `get_nasdaq_earnings_calendar()` | Upcoming earnings date (async) |
| `get_earnings_history()` | Past earnings beats/misses, beat rate |
| `get_ticker_data()` | Secondary catalysts, news headlines |
| `get_insider_trades()` | Insider buying/selling, cluster analysis |
| `get_institutional_holders()` | 13F institutional changes, accumulation |

### Section C: McMillan Options Strategy ⭐ NEW
| Tool | Data |
|------|------|
| `analyze_options_mcmillan()` | Full McMillan analysis (IV Rank, P/C Ratio, Max Pain, UOA, Strategy) |

### Section D: Al Brooks Analysis
| Tool | Data |
|------|------|
| `analyze_technical()` | RSI, MACD, EMAs, price data |
| `calculate_relative_strength_tool()` | RS vs SPY |
| `analyze_volume_tool()` | OBV, volume analysis |
| `analyze_ml_enhanced()` | ML trend prediction (async) |
| `get_cnn_fear_greed_index()` | Market sentiment (async) |

---

## SCORING GUIDE

### NEW 4-Tier Composite Score (100 points)

The scanner now uses inflection point detection to find stocks ENTERING trends, not stocks already exhausted.

| Component | Points | Factors |
|-----------|--------|---------|
| Momentum Quality | 30 | ADX 20-40, RSI 40-65 (L)/35-60 (S), EMA20 <5%, MACD |
| Pattern Quality | 25 | Consolidation Breakout, Volume 1.5-4x, Trend Days <6 |
| Relative Strength | 15 | RS vs SPY (55-85 for L, 15-45 for S) |
| Catalyst Quality | 20 | Earnings proximity, IV Rank, ML prediction |
| Al Brooks Pattern | 10 | Pattern type, completion, probability |

### Tier Exclusions (Hard Rejects)

Stocks automatically rejected:
- **Extended Moves:** 3mo return >+50% (L) or <-40% (S)
- **Recent Surge:** 1mo return >+30% (L) or <-25% (S)
- **52-Week Proximity:** Within 5% of high (L) or low (S)
- **Low Volatility:** ATR < 2% of price

### Score Interpretation

| Score | Signal | Meaning |
|-------|--------|---------|
| 80-100 | STRONG BUY/SHORT | High probability inflection point |
| 65-79 | BUY/SHORT | Good setup at early trend entry |
| 50-64 | WATCH | Developing, wait for confirmation |
| 0-49 | SKIP | Exhausted move or low probability |

---

## AL BROOKS PATTERN REFERENCE

### LONG Patterns
- **High 1:** First pullback in uptrend
- **High 2:** Second entry long (most reliable)
- **High 3:** Third push (often exhaustion)
- **Breakout Pullback:** Test of breakout level
- **Failed Low 2:** Bear trap becomes bull signal
- **Double Bottom:** Two tests of support
- **Wedge Bottom:** Falling wedge reversal

### SHORT Patterns
- **Low 1:** First pullback in downtrend
- **Low 2:** Second entry short (most reliable)
- **Low 3:** Third push (often exhaustion)
- **Failed Breakout:** Bull trap becomes bear signal
- **Failed High 2:** Bull trap becomes bear signal
- **Double Top:** Two tests of resistance
- **Wedge Top:** Rising wedge reversal

### Base Probabilities
- High 2 / Low 2: 60% base
- Breakout Pullback: 55% base
- Failed Patterns: 65% base (traps are powerful)
- First Entries (H1/L1): 50% base
- Third Entries (H3/L3): 45% base (exhaustion risk)

---

**Time:** 50-70 minutes for full 6-stock scan report
**Output:** ~350-450 lines per stock, ~2200+ lines total
**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy)
