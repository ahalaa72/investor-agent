# Market Opportunity Scanner Report Generator

Scan markets for top LONG and SHORT candidates with detailed analysis per stock.

**Structure:** 5 Sections per Stock (Overview + Catalyst + McMillan Options + Al Brooks + **Trading Signal**) | **Time:** 50-70 minutes | **Stocks:** Top 3 LONG + Top 3 SHORT

**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy) + **4-Gate Signal Classification**

---

## ⚠️ CRITICAL PRINCIPLE: CATALYST IS MANDATORY

**NO CATALYST = NO TRADE. Period.**

Every trade MUST have an identifiable catalyst. Without a catalyst, there's no reason for institutional money to move the stock. Catalysts include:
- **Earnings** (upcoming or recent beat/miss)
- **Insider Buying Clusters** (3+ insiders in 30 days)
- **Unusual Options Activity** (smart money positioning)
- **News/Events** (product launch, FDA, M&A)
- **IV Spike** (options market expecting move)

**Use `detect_catalyst_strength()` for every candidate - NO CATALYST = REJECT**

---

## 🔧 6 NEW ENHANCED TOOLS

| Tool | Purpose | Gate |
|------|---------|------|
| `detect_catalyst_strength` | Aggregate ALL catalyst signals | **MANDATORY** |
| `generate_trading_signal` | Final signal with 4-gate validation | **CORE** |
| `detect_unusual_options_activity` | Smart money options detection | Scoring |
| `detect_insider_cluster` | Clustered insider buying patterns | Scoring |
| `calculate_quality_score` | F-Score + Z-Score + ROE unified | Scoring |
| `analyze_competitors` | Sector comparison + leader detection | Scoring |

---

## 🚦 4-GATE SIGNAL CLASSIFICATION

**ALL 4 GATES MUST PASS for STRONG_BUY/SELL. Missing ANY gate = Downgrade.**

| Gate | Requirement | Tool |
|------|-------------|------|
| **1. CATALYST** | MUST have identifiable catalyst | `detect_catalyst_strength` |
| **2. FRESHNESS** | Trend Days ≤3, Exhaustion <50, CVD aligned | Scanner metrics |
| **3. BROOKS** | Always-In supports direction, Trap Risk LOW, Prob ≥55% | `analyze_ml_enhanced` |
| **4. QUALITY** | F-Score ≥5, Z-Score >1.81, No red flags | `calculate_quality_score` |

### Signal Classification

| Signal | Requirements |
|--------|--------------|
| **STRONG_BUY/SELL** | All 4 gates PASS + Score ≥80 + Success >65% |
| **BUY/SELL** | 3+ gates PASS + Score ≥70 + Success >55% |
| **WATCH** | 2+ gates PASS OR any warning flags |
| **NO_TRADE** | Any gate FAIL: No catalyst, Exhaustion >60, Brooks against, or Quality fail |

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

---

## 📊 SCAN STATISTICS

| Direction | Raw Candidates | Validated | 4/4 Gates | 3/4 Gates | Returned |
|-----------|----------------|-----------|-----------|-----------|----------|
| LONG      | XXX            | XX        | X         | X         | 3        |
| SHORT     | XXX            | XX        | X         | X         | 3        |

**Pass Rate:** X.X% (4/4) | X.X% (3+/4)
**Elapsed:** XXs | **Relaxed:** [YES/NO - filled with 3/4 if needed]

---

# TOP 3 LONG CANDIDATES

═══════════════════════════════════════════════════════════════
## LONG #1: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

**Price:** $XX.XX | **Score:** XX/100 | **Signal:** [🟢🟢 STRONG_BUY / 🟢 BUY / 🟡 WATCH / 🔴 NO_TRADE]

### 🚦 GATE STATUS [generate_trading_signal]
```
CATALYST:   [✅ PASS / ❌ FAIL] - [Primary catalyst or "No catalyst detected"]
FRESHNESS:  [✅ PASS / ❌ FAIL] - [X trend days, XX exhaustion, CVD status]
BROOKS:     [✅ PASS / ❌ FAIL] - [Always-In direction, XX% prob, trap risk]
QUALITY:    [✅ PASS / ❌ FAIL] - [F-Score X/9, Z-Score X.XX]
```

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

**Quality Scores:** [calculate_quality_score] ⭐ NEW
```
Quality Grade:    [A / B / C / D / F]
Quality Score:    XX/100
GATE 4 STATUS:    [✅ PASS / ❌ FAIL]
```

| Metric | Value | Status |
|--------|-------|--------|
| **F-Score** | X/9 | [STRONG ≥7 / MODERATE 5-6 / WEAK <5] |
| **Z-Score** | X.XX | [SAFE >2.99 / GREY 1.81-2.99 / DISTRESS <1.81] |
| **ROE** | XX.X% | [GOOD >15% / MODERATE 8-15% / WEAK <8%] |
| **Debt/Equity** | X.XX | [GOOD <1.0 / MODERATE 1-2 / HIGH >2] |
| **Net Margin** | XX.X% | [GOOD >10% / MODERATE 5-10% / WEAK <5%] |

**Red Flags:** [List any concerns]
**Green Flags:** [List any positives]

---

**Competitor Analysis:** [analyze_competitors] ⭐ NEW
```
Sector:           [Technology / Healthcare / etc.]
Sector Rank:      X of Y
Is Leader:        [YES / NO]
```

| Rank | Ticker | RS Score | 30d Perf | 90d Perf |
|------|--------|----------|----------|----------|
| 1 | [XXX] | XX | +XX.X% | +XX.X% |
| 2 | [XXX] | XX | +XX.X% | +XX.X% |
| 3 | [THIS] | XX | +XX.X% | +XX.X% |

**Relative Advantage:** [What makes this stock better/worse than peers]

---

**Recent Headlines:**
1. "[Headline 1]" - [Source, Date] [get_ticker_data]
2. "[Headline 2]" - [Source, Date] [get_ticker_data]

---

### SECTION B: CATALYST VERIFICATION ⚠️ MANDATORY GATE

**🚨 GATE 1: CATALYST CHECK** - NO CATALYST = NO TRADE

#### Catalyst Strength Assessment [detect_catalyst_strength] ⭐ ENHANCED (Dec 2025)
```
Catalyst Direction: [BULLISH / BEARISH / NEUTRAL]
Catalyst Strength:  [STRONG / MODERATE / WEAK / NONE]
Catalyst Score:     XX/100 (Bullish: XX, Bearish: XX)
Trade Allowed:      [YES / NO]
Primary Catalyst:   [Description]
```

**NEW ENHANCED FIELDS:**
```
News Sentiment:     [BULLISH / BEARISH / NEUTRAL] (X headlines analyzed)
Major Catalysts:
  - "[Headline]" - [Source] - [X days ago] [BULLISH/BEARISH]
  - "[Headline]" - [Source] - [X days ago] [BULLISH/BEARISH]

Insider Context:    10b5-1 Detected: [YES/NO] | Confidence: [HIGH/MEDIUM/LOW]
Warnings:           [List any items requiring manual verification]
```

**Key Enhancements:**
- **Web Search**: Fetches news from Google News RSS with publication dates
- **Recency Scoring**: Only news ≤3 days old counts; today's news = 2x weight
- **10b5-1 Detection**: Discounts insider selling 75% if pre-planned sale detected

**If NONE → REJECT CANDIDATE. Do not continue analysis.**

---

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

---

#### Smart Money Verification ⭐ ENHANCED

**Insider Cluster Detection:** [detect_insider_cluster] ⭐ NEW
```
Cluster Detected:   [YES / NO]
Cluster Type:       [BUYING / SELLING / MIXED]
Cluster Strength:   [STRONG (3+) / MODERATE (2) / WEAK (1) / NONE]
Total Value:        $XXM
Notable Insider:    [CEO/CFO buy = significant]
```

**Insider Trading (90d):** [get_insider_trades]
- **Net Activity:** [Net Buying $XXM / Net Selling $XXM / No Activity]
- **Notable Transactions:**
  - [Role] [bought/sold] $XXM at $XX.XX on MM/DD
  - [Role] [bought/sold] $XXM at $XX.XX on MM/DD
- **Interpretation:** [Bullish conviction / Routine / Concerning]

**Unusual Options Activity:** [detect_unusual_options_activity] ⭐ NEW
```
Unusual Activity:   [YES / NO]
Activity Type:      [BULLISH / BEARISH / MIXED]
Implied Move:       +/-X.X%
Largest Bet:        [Description of biggest position]
```

**Signals Detected:**
| Type | Strike | Expiry | Volume | OI Ratio | Premium |
|------|--------|--------|--------|----------|---------|
| [CALL/PUT] | $XXX | MM/DD | XXX,XXX | X.Xx | $XXM |

**Institutional Holdings:** [get_institutional_holders]
- **Top Holders:** [Vanguard XX%, BlackRock XX%, State Street XX%]
- **13F Changes (Latest Quarter):**
  - New positions: X funds
  - Increased stakes: X funds (+XX% net)
  - Decreased stakes: X funds (-XX% net)
- **Net Flow:** [ACCUMULATION / DISTRIBUTION / MIXED]

---

#### Catalyst Score: XX/100 [detect_catalyst_strength]

**Scoring Breakdown:**
- Earnings proximity (0-25 pts): XX pts
- Historical beat rate (0-25 pts): XX pts
- Insider cluster (0-25 pts): XX pts
- Unusual options (0-15 pts): XX pts
- Institutional flow (0-10 pts): XX pts

**Catalyst Verdict:** [STRONG / MODERATE / WEAK / NO CATALYST]
**GATE 1 STATUS:** [✅ PASS / ❌ FAIL]

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

#### Greeks Analysis (ATM) [analyze_options_mcmillan.greeks_assessment]

| Greek | ATM Call | ATM Put | Interpretation |
|-------|----------|---------|----------------|
| **Delta** | +X.XX | -X.XX | XX% chance ITM / $XX P&L per $1 move |
| **Gamma** | X.XXXX | X.XXXX | [HIGH = explosive near expiry / LOW = stable] |
| **Theta** | -$X.XX | -$X.XX | Daily decay - [favors buyer/seller] |
| **Vega** | $X.XX | $X.XX | +/-$X.XX per 1% IV change |

**Greeks Source:** [questrade / yfinance_estimated]

**Position Risk Profile:**
- **Delta Exposure:** [Long/Short delta, directional bias]
- **Gamma Risk:** [HIGH if near ATM + near expiry / LOW if far OTM]
- **Theta Burn:** [Positive = selling time / Negative = buying time]
- **Vega Sensitivity:** [Long vega = benefit from IV rise]

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

#### 📚 McMILLAN OPTIONS LESSON (Teach Me!)

**Purpose:** Translate options data into actionable strategy. Match strategy to volatility environment per McMillan's framework.

---

**1. WHAT THE OPTIONS MARKET IS SAYING**

[If IV Rank >60%]: Options market says **"Expect volatility."** IV near HIGH end of 52w range = **premium-selling environment** (Iron Condors, Credit Spreads).

[If IV Rank 30-60%]: **"Normal volatility."** Use directional strategies (Long Calls/Puts) with conviction OR neutral strategies (Iron Condors) if range-bound.

[If IV Rank <30%]: **"Volatility cheap - options on sale."** IV near LOW end = **premium-buying environment** (Long Calls/Puts, Debit Spreads).

**P/C Ratio Sentiment:**
- [If >1.2]: Excessive bearish positioning = **contrarian BULLISH signal** (squeeze likely)
- [If <0.7]: Excessive bullish positioning = **contrarian BEARISH signal** (reversal likely)
- [If 0.7-1.2]: Neutral - no contrarian signal

**Max Pain:** [If Above]: Upward pull | [If Below]: Downward pull | [If At]: Range-bound

---

**2. IV ENVIRONMENT → STRATEGY**

IV Rank XX% = **[HIGH / NORMAL / LOW]**

[If HIGH IV >60%]:
✅ **SELL PREMIUM:** Iron Condor, Credit Spreads, Covered Calls
❌ **AVOID:** Long Calls/Puts (fighting IV crush)

[If NORMAL IV 30-60%]:
✅ **DIRECTIONAL:** Debit Spreads, Long Calls/Puts if conviction

[If LOW IV <30%]:
✅ **BUY PREMIUM:** Long Calls/Puts, Debit Spreads (cheap options)
❌ **AVOID:** Premium selling (not enough edge)

**McMillan:** "Sell premium when IV high, buy premium when IV low."

---

**3. GREEKS EXPLAINED**

**Delta (+X.XX / -X.XX):** $1 stock move = $X.XX option move | ~XX% ITM probability
**Gamma (X.XXXX):** [HIGH = explosive] [LOW = stable]
**Theta (-$X.XX/day):** Time decay - [enemy for buyers / friend for sellers]
**Vega ($X.XX):** +1% IV = $X.XX option gain

[If Theta-negative + Vega-long in High IV]: ⚠️ DANGER - Buying expensive premium, fighting decay + IV crush
[If Theta-positive + Vega-short in High IV]: ✅ IDEAL - Selling expensive premium, collecting decay
[If Theta-negative + Vega-long in Low IV]: ✅ STRATEGIC - Buying cheap options before volatility expansion

---

**4. RECOMMENDED STRATEGY & WHY**

**STRATEGY:** [Bull Put Spread / Long Call / Iron Condor / etc.]

[If Bull Put Spread]:
📋 **BULL PUT SPREAD** - Sell $XXX Put / Buy $XXX Put
- **Why:** High IV (collect expensive premium) + Bullish bias + Theta advantage
- **Probability:** ~XX% profit if stock stays above $XXX
- **McMillan:** "Sell premium with defined risk in high IV." (Ch 8)

[If Long Call]:
📋 **LONG CALL** - Buy $XXX Call
- **Why:** Low IV (cheap options) + Bullish catalyst + Vega works for us
- **Risk:** $XXX max loss (premium paid)
- **McMillan:** "Buy options when IV low + strong conviction." (Ch 3)

[If Iron Condor]:
📋 **IRON CONDOR** - Sell $XXX Call + $XXX Put, Buy wings
- **Why:** High IV both sides + Neutral bias + Double theta collection
- **Profit Range:** $XXX - $XXX
- **McMillan:** "Ideal for high IV, low-movement environments." (Ch 14)

---

**5. EXECUTION CHECKLIST**

✅ **Entry:**
- [ ] IV environment matches strategy
- [ ] Directional bias confirmed
- [ ] Risk <2% of account
- [ ] Greeks understood

✅ **Exit:**
- [ ] Profit target: [50% / $X.XX / stock price]
- [ ] Stop loss: $XXX max loss
- [ ] Time stop: [X days / 7 days before expiry]

**McMillan:** "Never enter without exit plan for both profit AND loss."

---

**McMillan Score: XX/100** | [If ≥75]: HIGH CONVICTION | [If 50-74]: MODERATE | [If <50]: AVOID

**Key Takeaway:** Match strategy to volatility environment, not emotions. High IV? Sell premium. Low IV? Buy premium.

---

### SECTION D: AL BROOKS PRICE ACTION ANALYSIS

**🚨 GATE 2: FRESHNESS CHECK** - Fresh Breakout Required

#### Fresh Breakout Validation ⭐ NEW
```
Is Fresh:          [YES / NO]
Trend Days:        X (max 3)
Exhaustion Score:  XX/100 (max 50)
CVD Alignment:     [ALIGNED / MISALIGNED]
CVD Divergence:    [NONE / BULLISH / BEARISH]
```

**GATE 2 STATUS:** [✅ PASS / ❌ FAIL]

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Trend Days | X | ≤ 3 | [✅/❌] |
| Exhaustion | XX | < 50 | [✅/❌] |
| CVD Aligned | [Y/N] | Must align | [✅/❌] |
| CVD Divergence | [Type] | None against | [✅/❌] |

**If ANY metric fails → GATE 2 FAIL → Downgrade signal**

---

**🚨 GATE 3: AL BROOKS CHECK** - Price Action Must Confirm

---

**Technical Snapshot:** [analyze_ml_enhanced]
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

**Volumetric Liquidity:** [analyze_volume_tool] ⭐ NEW
- **CVD Trend:** [RISING/FALLING/FLAT] - [buying/selling pressure interpretation]
- **CVD Divergence:** [BULLISH/BEARISH/NONE] - [exhaustion signal if present]
- **Multi-VWAP:** [STRONG_BULLISH/BULLISH/MIXED/BEARISH] alignment
- **VWAP σ Distance:** X.XX ([SUSTAINABLE/EXTENDED/UNSUSTAINABLE])

**Exhaustion Score:** [analyze_ml_enhanced.exhaustion] ⭐ NEW
- **Score:** XX/100 ([NO/LOW/MODERATE/HIGH]_EXHAUSTION)
- **Action:** [PROCEED/FLAG/REDUCE_SIZE/EXCLUDE]

**ML Prediction:** [analyze_ml_enhanced]
- **Trend Direction:** [UPTREND / DOWNTREND / SIDEWAYS]
- **Confidence:** XX%
- **Predicted Return:** +/-X.X% over X days

**Order Blocks (Institutional Footprints):** [analyze_ml_enhanced.order_blocks]
- **Signal:** [BULLISH_ORDER_BLOCK_TEST / BEARISH_ORDER_BLOCK_TEST / NONE]
- **Bullish Blocks Found:** X blocks below current price
- **Bearish Blocks Found:** X blocks above current price
- **Closest Bullish OB:** $XX.XX (X.X% below) - [X days old, +X.X% impulse]
- **Closest Bearish OB:** $XX.XX (X.X% above) - [X days old, -X.X% impulse]
- **Interpretation:** [Price testing bullish support zone / Near bearish resistance / No blocks nearby]

**Supply/Demand Zones:** [analyze_ml_enhanced.supply_demand]
- **Signal:** [DEMAND_ZONE_TEST / SUPPLY_ZONE_TEST / NONE]
- **Closest Demand Zone:** $XX.XX (X.X% below)
- **Closest Supply Zone:** $XX.XX (X.X% above)

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

#### Gate 3 Validation
```
Always-In Direction:  [LONG / SHORT / NEUTRAL]
Direction Supports:   [YES / NO]
Trap Risk:            [HIGH / MEDIUM / LOW]
Trap Risk OK:         [YES / NO] (HIGH = FAIL)
Probability:          XX%
Probability OK:       [YES / NO] (≥55% required)
```

**GATE 3 STATUS:** [✅ PASS / ❌ FAIL]

**If Always-In against OR Trap Risk HIGH OR Probability <55% → GATE 3 FAIL**

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

#### 📚 AL BROOKS LESSON (Teach Me!)

**Purpose:** Read price action like a language. Understand what market is DOING, not what we WANT it to do.

---

**1. WHAT THE MARKET IS DOING (Always-In)**

**Always-In:** [LONG / SHORT / NEUTRAL]

[If LONG]: **Bulls control.** Buy dips to EMA20/VWAP/support. Every pullback = buying opportunity. DON'T short against this.
- **Brooks:** "When Always-In LONG, every selloff is a bull flag. Buy the dips." (Ch 5)

[If SHORT]: **Bears control.** Sell rallies to EMA20/VWAP/resistance. Every bounce = selling opportunity. DON'T buy against this.
- **Brooks:** "When Always-In SHORT, every rally is a bear flag. Sell the rips." (Ch 6)

[If NEUTRAL]: **Range-bound, choppy.** No clear trend. Fade extremes (sell resistance, buy support). Wait for breakout confirmation.
- **Brooks:** "In ranges, buy low, sell high, get out quick." (Ch 8)

---

**2. THE PATTERN & PROBABILITY**

**Pattern:** [High 2 / Low 1 / Wedge / Breakout / Channel]

[If High 2]:
📋 **HIGH 2** - Two-legged pullback tests prior high = **60-70% win rate**
- **Why:** Failed bear breakout (Bar 2) → Bulls resume → Bears trapped and cover
- **Entry:** Buy above Bar 1 high | **Stop:** Below Bar 2 low
- **Brooks:** "High 2 = failed bear breakout = bull signal." (Ch 17)

[If Low 1]:
📋 **LOW 1** - First pullback in strong trend = **60%+ win rate**
- **Why:** Strong momentum + Late bulls enter + Bears weak
- **Entry:** Buy bounce at support | **Stop:** Below support
- **Brooks:** "First pullback in strong trend = best entry." (Ch 16)

[If Wedge]:
📋 **WEDGE** - Three pushes, weakening momentum = **Exhaustion/Reversal**
- **Why:** Each push weaker → Late traders trapped → Smart money exits
- **Entry:** Reversal on Push 3 failure | **Stop:** Beyond Push 3
- **Brooks:** "Three pushes with weakening = reversal coming." (Ch 11)

[If Breakout]:
📋 **BREAKOUT** - Breaking key level
- **STRONG:** Large bar + High volume + Follow-through = 70%+ success
- **WEAK:** Small bar + Low volume + Immediate pullback = 60-70% FAIL
- **Brooks:** "Strong breakouts have strong bars. Weak breakouts fail - fade them." (Ch 9)

---

**3. BAR READING (Recent Action)**

**Last Bar:**
[If Strong Bull Bar]: ✅ **Bullish Conviction** - Close near high, no upper tail = buyers dominated. Expect continuation or shallow pullback.

[If Bear Bar]: ⚠️ **Bearish Pressure** - Close near low, no lower tail = sellers dominated. Expect continuation lower.

[If Doji/Small Bar]: ⚠️ **Indecision** - Neutral. Wait for next bar to clarify direction. Don't trade uncertainty.

[If Inside Bar]: ⚠️ **Compression** - Coiling before explosive move. Wait for breakout direction.

**Pattern Over 5 Bars:**
- [If Consecutive Bull Bars]: Strong bull trend - Buy first pullback (Low 1)
- [If Overlapping Bars]: Consolidation/Range - Buy support, sell resistance
- [If Decreasing Bar Size]: Momentum fading - Warning sign, reversal setup

---

**4. PROBABILITY CALCULATION**

**Base Pattern:** XX% | **Final Brooks Probability:** XX%

**Positive Factors:**
✅ Strong Trend (Always-In LONG/SHORT): +10-15%
✅ High Volume (XX% above avg): +10%
✅ Failed Opposite Setup (Trapped traders): +10-15%
✅ Strong Bars (closing near extremes): +5-10%

**Negative Factors:**
❌ Counter-Trend (Shorting Always-In LONG): -20-30%
❌ Low Volume: -10-15%
❌ Late in Move (X bars up): -10-15%
❌ Weak Bars (dojis, long tails): -10%

**Conviction:**
- [If ≥70%]: ✅ **VERY STRONG** - Full position size (within 2% risk). This is what we wait for.
- [If 50-69%]: ⚠️ **MODERATE** - Reduced size (50-75%). Be ready to exit quickly.
- [If <50%]: ❌ **LOW** - DO NOT TRADE. Wait for better setup.

**Brooks:** "If <60% probability AND <2:1 R/R, DON'T TRADE." (Ch 22)

---

**5. TRAP WARNING**

**TRAP RISK:** [HIGH / MODERATE / LOW]

[If HIGH - Late in Move]:
🚨 **LATE-IN-MOVE TRAP** - X bars / XX% without pullback
- **Trap:** Early bulls take profit at top → Late bulls trapped
- **Avoid:** Wait for pullback. Don't chase.
- **Brooks:** "Best time to buy = when nobody wants it. Worst = when everyone wants it." (Ch 7)

[If HIGH - Counter-Trend]:
🚨 **COUNTER-TREND TRAP** - Shorting Always-In LONG
- **Trap:** Trend continues → Shorts cover at loss (squeeze)
- **Avoid:** Trade WITH trend. Wait for strong reversal pattern.
- **Brooks:** "Trend always stronger than you think. Don't fight it." (Ch 5)

[If HIGH - Weak Breakout]:
🚨 **FAILED BREAKOUT TRAP** - Small bar, low volume, immediate pullback
- **Trap:** Retail buys weak breakout → Breakout fails → Stops hit
- **Avoid:** Require strong bar + high volume + confirmation
- **Brooks:** "Most breakouts fail. Only trade strong ones." (Ch 9)

[If MODERATE]: ⚠️ Reduce size, tight stops. Choppy bars / Divergences / Event risk.

[If LOW]: ✅ Good setup - Clear pattern, strong bars, high volume, trend alignment.

---

**6. TRADING IMPLICATION (Action)**

[If Always-In LONG + High Probability]:
✅ **BUY SIGNAL**

**Entry:** $XXX.XX ([NOW at support] / [BUY STOP above resistance])
**Stop:** $XXX.XX (below [support / EMA20 / prior low])
**Target 1:** $XXX.XX (+X.X%) - Sell 50%, move stop to breakeven
**Target 2:** $XXX.XX (+XX%) - Sell 25% more
**Target 3:** $XXX.XX (+XX%) - Let 25% run with trailing stop

**Position Size:**
- Account: $XX,XXX | Risk: 2% = $XXX max loss
- Shares: $XXX ÷ $X.XX stop = XXX shares

**Risk/Reward:** [2:1 / 3:1 / 5:1] ✅

**Brooks Checklist:**
- [ ] Always-In = LONG ✅
- [ ] Probability ≥60% ✅
- [ ] R/R ≥2:1 ✅
- [ ] Stop defined ✅
- [ ] Position size = 2% ✅
- [ ] Volume confirms ✅
- [ ] Low trap risk ✅

**IF ALL ✅, EXECUTE.**

**Brooks:** "Best trades are obvious, boring, textbook. If you have to convince yourself, don't take it." (Ch 23)

[If Always-In SHORT + High Probability]:
✅ **SELL SIGNAL**
[Same structure, inverted for shorts]

[If NEUTRAL / Low Probability]:
⚠️ **NO TRADE - WAIT**
- Choppy / <60% probability / High trap risk / Conflicting signals
- **Action:** Wait for clarity. Set alerts at $XXX (support) / $XXX (resistance).
- **Brooks:** "No trade is better than bad trade. Patience is a position." (Ch 24)

---

**Brooks Score: XX/100** | [If ≥75]: HIGH CONVICTION | [If 50-74]: MODERATE | [If <50]: AVOID

**Key Takeaway:** Read price action like language. Know what market is DOING (Always-In), recognize patterns, read bars, calculate probability, avoid traps, execute with discipline.

---

### SECTION E: TRADING SIGNAL ⭐ NEW [generate_trading_signal]

**📊 FINAL SIGNAL CLASSIFICATION**

```
┌─────────────────────────────────────────────────────────────┐
│  SIGNAL: [🟢🟢 STRONG_BUY / 🟢 BUY / 🟡 WATCH / 🔴 NO_TRADE] │
│  CONFIDENCE: XX/100                                         │
└─────────────────────────────────────────────────────────────┘
```

#### Gate Summary
| Gate | Status | Details |
|------|--------|---------|
| **1. CATALYST** | [✅/❌] | [Primary catalyst or "None"] |
| **2. FRESHNESS** | [✅/❌] | [X trend days, XX exhaustion] |
| **3. BROOKS** | [✅/❌] | [XX% prob, trap risk] |
| **4. QUALITY** | [✅/❌] | [F-Score X, Z-Score X.XX] |

**Gates Passed:** X/4

---

#### Complete Trading Plan
```
ENTRY TRIGGER:     [Buy on break above $XXX / Buy on pullback to $XXX]
ENTRY PRICE:       $XXX.XX (LIMIT / STOP / MARKET)
ENTRY TYPE:        [Breakout / Pullback / Reversal]

STOP LOSS:         $XXX.XX (-X.X%)
STOP METHOD:       [SWING_LOW / SUPPORT / ATR-based]
RISK PER SHARE:    $X.XX

TARGET 1:          $XXX.XX (+X.X%) - [First resistance / 1.5x risk]
TARGET 2:          $XXX.XX (+XX.X%) - [Major resistance / 2.5x risk]

POSITION SIZE:     XX shares ($XXX risk on $10K account)
RISK/REWARD:       X.X:1
TIME FRAME:        X-XX trading days
```

---

#### Proof of Validity [find_similar_historical_setups]
```
HISTORICAL VALIDATION:
─────────────────────────────────────
Similar Setups Found:     XX
Historical Success Rate:  XX%
Avg Target Achievement:   XX%
Statistical Confidence:   XX% (p=X.XX)
95% Confidence Interval:  [XX%, XX%]
Win/Loss Record:          XXW / XXL
```

**Validation Status:** [STRONG ≥20 setups, >65% / MODERATE 10-20, >55% / WEAK <10]

---

#### Final Recommendation
```
[IF STRONG_BUY:]
✅ ALL 4 GATES PASSED
✅ Historical success rate >65%
✅ Risk/Reward >2:1
→ EXECUTE TRADE with full position size

[IF BUY:]
✅ 3+ GATES PASSED
✅ Historical success rate >55%
✅ Risk/Reward >1.5:1
→ EXECUTE TRADE with 75% position size

[IF WATCH:]
⚠️ 2+ GATES PASSED but warnings exist
→ MONITOR for better entry, do not trade yet

[IF NO_TRADE:]
❌ GATE FAILURE: [Which gate failed and why]
→ SKIP this candidate
```

---

═══════════════════════════════════════════════════════════════
## LONG #2: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D, E format with 4-gate validation]

---

═══════════════════════════════════════════════════════════════
## LONG #3: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D, E format with 4-gate validation]

---

# TOP 3 SHORT CANDIDATES

═══════════════════════════════════════════════════════════════
## SHORT #1: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D, E format - Note: For shorts, look for:
- Overbought RSI (>70)
- Bearish MACD
- Distribution volume
- RS Laggard (<50)
- ML downtrend prediction
- Bear patterns (Low 1/2/3, Failed Breakout, Wedge Top)
- High IV environment for bear spreads ⭐ McMillan
- Contrarian bearish P/C signal ⭐ McMillan
- **CVD FALLING** for shorts (Gate 2)
- **Always-In SHORT** or NEUTRAL (Gate 3)]

---

═══════════════════════════════════════════════════════════════
## SHORT #2: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D, E format with 4-gate validation]

---

═══════════════════════════════════════════════════════════════
## SHORT #3: [TICKER] - [Company Name]
═══════════════════════════════════════════════════════════════

[Repeat SECTION A, B, C, D, E format with 4-gate validation]

---

# SCAN SUMMARY

## Top Picks Ranking (with 4-Gate Status)

| Rank | Dir | Ticker | Signal | Score | Gates | Brooks | R/R | Status |
|------|-----|--------|--------|-------|-------|--------|-----|--------|
| 1 | LONG | [XXX] | 🟢🟢 | XX/100 | 4/4 | XX% | X.X:1 | EXECUTE |
| 2 | LONG | [XXX] | 🟢 | XX/100 | 3/4 | XX% | X.X:1 | EXECUTE 75% |
| 3 | LONG | [XXX] | 🟡 | XX/100 | 2/4 | XX% | X.X:1 | WATCH |
| 1 | SHORT | [XXX] | 🟢🟢 | XX/100 | 4/4 | XX% | X.X:1 | EXECUTE |
| 2 | SHORT | [XXX] | 🟢 | XX/100 | 3/4 | XX% | X.X:1 | EXECUTE 75% |
| 3 | SHORT | [XXX] | 🔴 | XX/100 | 1/4 | XX% | X.X:1 | SKIP |

**Signal Legend:** 🟢🟢 STRONG_BUY/SELL | 🟢 BUY/SELL | 🟡 WATCH | 🔴 NO_TRADE

## Gate Failure Summary

| Ticker | Failed Gate | Reason |
|--------|-------------|--------|
| [XXX] | CATALYST | No identifiable catalyst within 45 days |
| [XXX] | FRESHNESS | Exhaustion score 72 (max 50) |
| [XXX] | BROOKS | Trap risk HIGH at resistance |

## Best Opportunities

**Top LONG:** [TICKER] - [1 sentence why + gates passed + primary catalyst]
**Top SHORT:** [TICKER] - [1 sentence why + gates passed + primary catalyst]

## Market Context

- **Fear & Greed Index:** XX [get_cnn_fear_greed_index]
- **Market Bias:** [Risk-On favors LONGS / Risk-Off favors SHORTS / Neutral]
- **VIX Level:** XX.XX [If available]

---

*Scan completed at [TIME]. All data from MCP investor-agent tools with 4-gate validation.*
```

---

## WORKFLOW

### Step 1: Run the Scanner (2-5 min)

**Option A: Separate Calls (Recommended - More Reliable)**
```python
# Step 1a: Get raw LONG candidates (verify scanner works)
get_raw_scan_candidates(direction="LONG", market="america", limit=500)
# Returns: 200-500 raw LONG candidates from TradingView (no validation)

# Step 1b: Validate LONG candidates
scan_long_candidates(market="america", max_scan=50, top_n=3)
# Returns: Top 3 LONG with 4-gate validation + progress log

# Step 1c: Get raw SHORT candidates
get_raw_scan_candidates(direction="SHORT", market="america", limit=500)
# Returns: 200-500 raw SHORT candidates from TradingView (no validation)

# Step 1d: Validate SHORT candidates
scan_short_candidates(market="america", max_scan=50, top_n=3)
# Returns: Top 3 SHORT with 4-gate validation + progress log
```

**Option B: One-Shot Full Scan**
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

### Step 2: Analyze Each Candidate (10 min per stock)

For each of the 6 candidates (3 LONG + 3 SHORT):

```python
# ═══════════════════════════════════════════════════════════
# Section A: Company Overview + Quality Score (Gate 4)
# ═══════════════════════════════════════════════════════════
get_ticker_data(ticker)                        # Company info, fundamentals, news
calculate_quality_score(ticker)                # ⭐ NEW: Unified quality score (Gate 4)
analyze_competitors(ticker)                    # ⭐ NEW: Sector comparison, leader detection

# ═══════════════════════════════════════════════════════════
# Section B: Catalyst Verification (Gate 1 - MANDATORY)
# ═══════════════════════════════════════════════════════════
detect_catalyst_strength(ticker)               # ⭐ NEW: MANDATORY - Aggregate catalyst signals
# IF detect_catalyst_strength returns "NONE" → SKIP CANDIDATE

asyncio.run(get_nasdaq_earnings_calendar(ticker))  # Upcoming earnings date (async)
get_earnings_history(ticker)                       # Historical beat rate, surprises

# Smart Money Detection ⭐ ENHANCED
detect_insider_cluster(ticker)                 # ⭐ NEW: Clustered insider buying patterns
detect_unusual_options_activity(ticker)        # ⭐ NEW: Smart money options detection
get_institutional_holders(ticker)              # 13F accumulation/distribution

# ═══════════════════════════════════════════════════════════
# Section C: McMillan Options Strategy
# ═══════════════════════════════════════════════════════════
analyze_options_mcmillan(ticker)  # Full McMillan analysis (direction-independent)
# Returns: TRUE IV Rank, P/C Ratio, Max Pain, UOA, IV-based strategies, Quality Score

# ═══════════════════════════════════════════════════════════
# Section D: Al Brooks Analysis + Freshness (Gates 2 & 3)
# ═══════════════════════════════════════════════════════════
asyncio.run(analyze_ml_enhanced(ticker))           # Full analysis with exhaustion score (async)
# Gate 2: Check trend_days <= 3, exhaustion < 50, CVD aligned
# Gate 3: Check always_in direction, trap_risk, probability >= 55%

calculate_relative_strength_tool(ticker, benchmark="SPY")  # RS vs market
analyze_volume_tool(ticker, include_quality_score=True)    # CVD, VWAP, volume quality

# ═══════════════════════════════════════════════════════════
# Section E: Generate Trading Signal (4-Gate Validation)
# ═══════════════════════════════════════════════════════════
generate_trading_signal(ticker, direction="LONG")  # ⭐ NEW: Final signal with all gates
# Returns: signal, confidence, trading_plan, proof_of_validity, gate_status

# Historical Validation
asyncio.run(find_similar_historical_setups(
    ticker,
    target_return_pct=5.0,      # Expected target %
    holding_period_days=10,     # Expected holding period
    direction="LONG"            # Trade direction
))  # Proof of validity with success rate
```

### Step 3: Gate Validation (CRITICAL)

**For each stock, validate ALL 4 GATES:**

| Gate | Check | Tool | Fail Condition |
|------|-------|------|----------------|
| **1. CATALYST** | Has identifiable catalyst | `detect_catalyst_strength` | `strength == "NONE"` |
| **2. FRESHNESS** | Fresh breakout | Scanner metrics | `trend_days > 3 OR exhaustion >= 50 OR CVD misaligned` |
| **3. BROOKS** | Price action confirms | `analyze_ml_enhanced` | `trap_risk == "HIGH" OR probability < 55%` |
| **4. QUALITY** | Financial health OK | `calculate_quality_score` | `f_score < 3 OR z_score < 1.81` |

**Signal Classification:**
- **4/4 Gates + Score ≥80 + Success >65%** → STRONG_BUY/SELL
- **3/4 Gates + Score ≥70 + Success >55%** → BUY/SELL
- **2/4 Gates OR warnings** → WATCH
- **Any critical gate fail** → NO_TRADE

### Step 4: Generate Brooks Analysis (AI interpretation)

For each stock, interpret the data through Al Brooks methodology:
- Identify the pattern (High 2, Low 2, Breakout Pullback, etc.)
- Read the bars (bar type, close position, volume)
- Calculate context-adjusted probability with gate adjustments
- Set entry/stop/targets based on Brooks levels

### Step 5: Compile Summary with Gate Status

Create the final ranking table with:
- Signal type (🟢🟢/🟢/🟡/🔴)
- Gates passed (X/4)
- Gate failure reasons
- Best opportunities with catalyst callout

---

## TOOL REFERENCE

### 🔧 6 NEW ENHANCED TOOLS ⭐

| Tool | Purpose | Gate |
|------|---------|------|
| `detect_catalyst_strength()` | Aggregate ALL catalyst signals | **GATE 1** |
| `generate_trading_signal()` | Final signal with 4-gate validation | **CORE** |
| `detect_unusual_options_activity()` | Smart money options detection | Scoring |
| `detect_insider_cluster()` | Clustered insider buying patterns | Scoring |
| `calculate_quality_score()` | F-Score + Z-Score + ROE unified | **GATE 4** |
| `analyze_competitors()` | Sector comparison + leader detection | Scoring |

---

### Scanner Tools (Use in Order)

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `get_raw_scan_candidates(direction, limit)` | Raw TradingView list (NO validation) | Verify scanner returns candidates |
| `scan_long_candidates(max_scan, top_n)` | LONG only with 4-gate validation | After raw list verified |
| `scan_short_candidates(max_scan, top_n)` | SHORT only with 4-gate validation | After LONG scan |
| `scan_market_opportunities(top_n)` | Full scan (LONG + SHORT) | One-shot full scan |

**Recommended Workflow:**
1. `get_raw_scan_candidates(direction="LONG")` → See raw LONG list
2. `scan_long_candidates()` → Validate LONG candidates
3. `get_raw_scan_candidates(direction="SHORT")` → See raw SHORT list
4. `scan_short_candidates()` → Validate SHORT candidates

### Section A: Company Overview + Quality (Gate 4)
| Tool | Data |
|------|------|
| `get_ticker_data()` | Company info, fundamentals, news |
| `calculate_quality_score()` | ⭐ NEW: Unified quality score (Gate 4) |
| `analyze_competitors()` | ⭐ NEW: Sector comparison, leader detection |

### Section B: Catalyst Verification (Gate 1 - MANDATORY)
| Tool | Data |
|------|------|
| `detect_catalyst_strength()` | ⭐ NEW: MANDATORY aggregate catalyst check |
| `get_nasdaq_earnings_calendar()` | Upcoming earnings date (async) |
| `get_earnings_history()` | Past earnings beats/misses, beat rate |
| `detect_insider_cluster()` | ⭐ NEW: Clustered insider buying patterns |
| `detect_unusual_options_activity()` | ⭐ NEW: Smart money options detection |
| `get_institutional_holders()` | 13F institutional changes, accumulation |

### Section C: McMillan Options Strategy
| Tool | Data |
|------|------|
| `analyze_options_mcmillan()` | Full McMillan analysis (IV Rank, P/C Ratio, Max Pain, UOA, Strategy) |

### Section D: Al Brooks Analysis + Freshness (Gates 2 & 3)
| Tool | Data |
|------|------|
| `analyze_ml_enhanced()` | Full analysis: RSI, MACD, EMAs, Al Brooks, exhaustion (async) |
| `calculate_relative_strength_tool()` | RS vs SPY |
| `analyze_volume_tool()` | OBV, CVD, VWAP, volume quality |
| `get_cnn_fear_greed_index()` | Market sentiment (async) |

### Section E: Trading Signal (4-Gate Validation) ⭐ NEW
| Tool | Data |
|------|------|
| `generate_trading_signal()` | Final signal with all gates, trading plan |
| `find_similar_historical_setups()` | Proof of validity, success rate (async) |

---

## SCORING GUIDE

### 🚦 4-GATE SIGNAL CLASSIFICATION (NEW)

**ALL 4 GATES MUST PASS for STRONG signal. Missing gates = Downgrade.**

| Gate | Requirement | Tool | Fail = |
|------|-------------|------|--------|
| **1. CATALYST** | Has identifiable catalyst | `detect_catalyst_strength` | NO_TRADE |
| **2. FRESHNESS** | Trend Days ≤3, Exhaustion <50, CVD aligned | Scanner | Downgrade |
| **3. BROOKS** | Always-In OK, Trap LOW, Prob ≥55% | `analyze_ml_enhanced` | Downgrade |
| **4. QUALITY** | F-Score ≥5, Z-Score >1.81 | `calculate_quality_score` | Downgrade |

### Signal Classification

| Gates Passed | Score | Success | Signal | Action |
|--------------|-------|---------|--------|--------|
| 4/4 | ≥80 | >65% | 🟢🟢 STRONG_BUY/SELL | Execute full size |
| 3/4 | ≥70 | >55% | 🟢 BUY/SELL | Execute 75% size |
| 2/4 | ≥60 | >50% | 🟡 WATCH | Monitor, don't trade |
| <2 | Any | Any | 🔴 NO_TRADE | Skip candidate |

---

### 4-Tier Composite Score (100 points)

The scanner uses inflection point detection to find stocks ENTERING trends, not exhausted.

| Component | Points | Factors |
|-----------|--------|---------|
| Momentum Quality | 30 | ADX 20-40, RSI 40-65 (L)/35-60 (S), EMA20 <5%, MACD |
| Pattern Quality | 25 | Consolidation Breakout, Volume 1.5-3x, Trend Days ≤3 |
| Relative Strength | 15 | RS vs SPY (55-85 for L, 15-45 for S) |
| Catalyst Quality | 20 | Earnings proximity, IV Rank, Insider cluster |
| Al Brooks Pattern | 10 | Pattern type, completion, probability |

### Fresh Breakout Thresholds (Gate 2)

| Metric | Threshold | Old Value |
|--------|-----------|-----------|
| Trend Days | ≤ 3 | Was 6 |
| Exhaustion Score | < 50 | Was 80 |
| Volume Surge | 1.5-3.0x | Was 1.5-4x |
| EMA20 Distance | < 3% | Was 5% |
| CVD Alignment | REQUIRED | Was bonus |

### Tier Exclusions (Hard Rejects)

Stocks automatically rejected:
- **Extended Moves:** 3mo return >+50% (L) or <-40% (S)
- **Recent Surge:** 1mo return >+30% (L) or <-25% (S)
- **52-Week Proximity:** Within 5% of high (L) or low (S)
- **Low Volatility:** ATR < 2% of price
- **No Catalyst:** No identifiable catalyst (Gate 1 FAIL)
- **Exhausted:** Exhaustion score ≥50 (Gate 2 FAIL)

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

**Time:** 60-90 minutes for full 6-stock scan report with 4-gate validation
**Output:** ~400-500 lines per stock, ~2500+ lines total
**Sections:** 5 per stock (A: Overview + B: Catalyst + C: Options + D: Brooks + E: Signal)
**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy) + 4-Gate Validation
**New Tools:** 6 enhanced tools (detect_catalyst_strength, generate_trading_signal, etc.)
**Critical:** CATALYST IS MANDATORY - No catalyst = No trade
