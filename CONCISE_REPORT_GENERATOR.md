# Concise Trading Report Generator

Fast analysis with bullet points for data, detailed Al Brooks, McMillan Options, and Trading Plan.

**Structure:** ~210 lines | **Time:** 35 minutes | **Framework:** 10-Phase Institutional

**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy)

---

## CRITICAL RULES

### Data Integrity
- **NEVER fabricate numbers** - If tool fails, report "DATA UNAVAILABLE"
- **Every number MUST have [tool_name] source tag**
- **Async functions need asyncio.run():** get_cnn_fear_greed_index, find_similar_historical_setups, analyze_ml_enhanced
- **Check market hours before intraday calls** (weekends/after-hours = skip)

---

## REPORT TEMPLATE

```markdown
# [TICKER] ([Company]) - CONCISE [LONG/SHORT] ANALYSIS

**Date:** YYYY-MM-DD | **Price:** $XX.XX | **Position:** [LONG/SHORT] @ $XX.XX (+X.X%)

---

## QUICK DATA SUMMARY (Phases 1-6)

### Phase 1: Fundamentals (19.6%) - [BULLISH/BEARISH/NEUTRAL] [✓/✗]
- F-Score: X/9 ([STRONG/WEAK]) [calculate_fundamental_scores_tool]
- Z-Score: X.XX ([SAFE/GREY/DISTRESS]) [calculate_fundamental_scores_tool]
- Revenue: +/-XX.X% YoY [get_ticker_data]
- ROE: XX.X%, EPS: $X.XX [get_ticker_data]
- **Score: XX/100** → XX.X pts

### Phase 2: Catalysts (15.2%) - [BULLISH/BEARISH/NEUTRAL]
- Last earnings: [Date] ([Beat/Miss] +/-XX%) [get_earnings_history]
- Next earnings: [Date] [get_nasdaq_earnings_calendar]
- Recent news: "[Headline]" [get_ticker_data]
- **Score: XX/100** → XX.X pts

### Phase 3: McMillan Options Strategy (13.4%) - [BULLISH/BEARISH/NEUTRAL] [✓/✗]
- IV Rank: XX% / IV Percentile: XX% [analyze_options_mcmillan]
  - Divergence: [ALIGNED / DIVERGENT: recent spike vs historical norm]
- P/C Ratio: X.XX [analyze_options_mcmillan]
  - Raw: [Bullish <0.7 / Neutral 0.7-1.0 / Bearish >1.0]
  - **Contrarian:** [BULLISH if >1.2 / BEARISH if <0.5 / NO SIGNAL 0.5-1.2]
- Max Pain: $XXX.XX ([Above/Below/At] price) [analyze_options_mcmillan]
  - Reliability: [HIGH (near expiry + high OI) / MEDIUM / LOW (early cycle)]
- Smart Money: [BULLISH/BEARISH/MIXED/NO_SIGNAL] [analyze_options_mcmillan]
- **Strategy:** [Bull Put Spread / Long Call / Iron Condor / etc.] [analyze_options_mcmillan]
- **Score: XX/100** → XX.X pts

### Phase 4: Insiders (4.5%) - [BUYING/SELLING/MIXED]
- Insider activity: [Description] [get_insider_trades]
- **Score: XX/100** → XX.X pts

### Phase 5: Institutions (4.5%) - [ACCUMULATING/DISTRIBUTING/MIXED]
- Top holders: [Vanguard X%, BlackRock X%] [get_institutional_holders]
- 13F changes: [+/-X% net] [get_institutional_holders]
- **Score: XX/100** → XX.X pts

### Phase 6: Technical (17.9%) - [BULLISH/BEARISH/NEUTRAL] [✓/✗]
- RSI: XX.X ([Overbought/Neutral/Oversold]) [analyze_technical]
- MACD: [Bullish/Bearish] (X.XX) [analyze_technical]
- Price vs EMA20: +/-XX.X%, vs VWAP: +/-XX.X% [analyze_technical]
- RS vs SPY: XX ([LEADER/LAGGARD]) [calculate_relative_strength_tool]
- Trend: [UPTREND/DOWNTREND], XX.X% confidence [analyze_ml_enhanced]
- OBV: [Accumulation/Distribution] [analyze_volume_tool]
- **Al Brooks (from analyze_technical):** [Pattern], [XX]% adjusted probability [analyze_technical.al_brooks]
- **Score: XX/100** → XX.X pts

### Phase 7: Market Context (5.3%) - [BULLISH/BEARISH/NEUTRAL]
- Fear & Greed: XX.X ([Extreme Fear/Fear/Neutral/Greed/Extreme Greed]) [get_cnn_fear_greed_index]
- **Score: XX/100** → XX.X pts

---

## PHASE 8: AL BROOKS PRICE ACTION (19.6%) ⭐ CRITICAL

### A. Always-In Direction
- **Current:** [LONG/SHORT] since [Date] ([reason])
- **Flip level:** Close [above/below] $XX.XX with volume

### B. Market Structure
- **Trend Type:** [Strong Bull / Weak Bull / Range / Weak Bear / Strong Bear]
- **Trend Phase:** [Breakout / Acceleration / Exhaustion / Second leg]
- **Pattern Quality:** [Strong/Medium/Weak] - [Explain why]

### C. Specific Brooks Pattern
**PRIMARY:** [High 1/High 2/Low 1/Low 2/Breakout Pullback/etc.]
- First leg: $XX.XX → $XX.XX
- Bounce/Pullback to: $XX.XX
- Current leg: In progress → Target $XX.XX

### D. Bar-by-Bar (Last 5)
| Date | Type | Close | Interpretation |
|------|------|-------|----------------|
| [Date] | [Bull/Bear/Doji] | [High/Low/Mid] | [Signal] |
| [Date-1] | [Type] | [Close] | [Signal] |
| [Date-2] | [Type] | [Close] | [Signal] |
| [Date-3] | [Type] | [Close] | [Signal] |
| [Date-4] | [Type] | [Close] | [Signal] |

**Pattern:** [X consecutive bull/bear bars = Y]

### E. Trap Analysis
- **Bull Trap Risk:** [HIGH/MEDIUM/LOW] - [Reason]
- **Bear Trap Risk:** [HIGH/MEDIUM/LOW] - [Reason]

### F. Brooks Probability Factors

**✓ POSITIVE (Favoring [LONG/SHORT]):**
- [Factor 1: trend/momentum aligned]
- [Factor 2: price vs EMAs/VWAP]
- [Factor 3: RS score]
- [Factor 4: fundamental support]
- [Factor 5: smart money aligned]

**✗ NEGATIVE (Risk):**
- [Risk 1]
- [Risk 2]
- [Risk 3]

### G. Price Levels ([LONG/SHORT])

```
    STOP:    $XX.XX ━━━━━━━━━━━━ (+/-XX.X%) ⚠️
    R2:      $XX.XX ━━━━━━━━━━━━ [Description] (+/-XX.X%)
    R1:      $XX.XX ━━━━━━━━━━━━ [Description] (+/-XX.X%)
    ENTRY:   $XX.XX ═══════════ Your Position (+/-XX.X%)
    CURRENT: $XX.XX ═══════════
    S1:      $XX.XX ┅┅┅┅┅┅┅┅┅┅ PT1 (+/-XX.X%)
    TARGET:  $XX.XX ┅┅┅┅┅┅┅┅┅┅ PT2 (+/-XX.X%)
```

### H. Context-Informed Probability

**Base:** XX% ([Pattern Name])

**Adjustments:**
- [Adjustment 1]: +/-XX%
- [Adjustment 2]: +/-XX%
- [Adjustment 3]: +/-XX%

**FINAL BROOKS ([LONG/SHORT]): XX%** ⭐

**Score: XX/100** → XX.X pts

---

## PHASE 9: HISTORICAL CONFIRMATION (0% Weight)

**⚠️ CRITICAL:** Use ACTUAL Trading Plan targets from Phase 10, NOT hardcoded values!

**Call with dynamic targets:**
```python
# Get targets from YOUR Trading Plan (Phase 9)
# Example: If PT1 = 3.6%, PT2 = 5.6%, holding = 10 days
find_similar_historical_setups(
    ticker="XXXX",
    target_return_pct=3.6,      # Use YOUR PT1 or PT2 from Trading Plan
    holding_period_days=10,     # Use YOUR holding period from Trading Plan
    direction="LONG"            # Use YOUR direction from Trading Plan
)
```

### Summary
- **Setups Found:** XX [find_similar_historical_setups]
- **Target:** X.X% in XX days ([LONG/SHORT]) ← MUST match Trading Plan!
- **Avg Achievement:** XX.X% ([STRONG/MODERATE/WEAK])
- **Hit Target Rate:** XX% (XX/XX setups)
- **Confidence:** [HIGH/MEDIUM/LOW]

### Trading Plan Validation (Top 10)

| Date | Sim% | Actual | Target | Achieve | Status |
|------|------|--------|--------|---------|--------|
| YYYY-MM-DD | XX.X% | +X.XX% | X.X% | +XXX.X% | ✅ HIT |
| YYYY-MM-DD | XX.X% | +X.XX% | X.X% | +XX.X% | 🟡 PARTIAL |
| YYYY-MM-DD | XX.X% | -X.XX% | X.X% | -XX.X% | ❌ WRONG |
| ... | ... | ... | ... | ... | ... |

**Status Legend:** ✅ HIT (≥100%) | 🟡 PARTIAL (60-99%) | 🟠 WEAK (0-59%) | ❌ WRONG (<0%)

### Achievement Distribution
| Category | Count | Rate |
|----------|-------|------|
| STRONG (≥80%) | XX | XX% |
| MODERATE (60-79%) | XX | XX% |
| WEAK (0-59%) | XX | XX% |
| NEGATIVE (<0%) | XX | XX% |

**Status:** [✅ STRONG / ⚠️ LIMITED / ✗ WEAK]

---

## TRADING PLAN 🎯 (Phase 10)

### Weighted Score ([LONG/SHORT])
```
Fundamentals:  XX.X pts (XX/100 × 19.6%)
Catalysts:     XX.X pts (XX/100 × 15.2%)
McMillan Opts: XX.X pts (XX/100 × 13.4%)
Insiders:      XX.X pts (XX/100 × 4.5%)
Institutions:  XX.X pts (XX/100 × 4.5%)
Technical:     XX.X pts (XX/100 × 17.9%)
Context:       XX.X pts (XX/100 × 5.3%)
Al Brooks:     XX.X pts (XX/100 × 19.6%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL:         XX.X/100 ([HIGH/MODERATE/LOW] CONVICTION [LONG/SHORT])

**Weights Sum:** 100.0% (NO normalization needed)
```

### Recommendation: **[STRONG BUY/BUY/HOLD/ADD/SELL/SHORT]**

### Position Management
| Action | Price | Size | Notes |
|--------|-------|------|-------|
| Current | $XX.XX | Held | +/-XX.X% profit/loss |
| Add 1 | $XX.XX | XX% | [Level description] |
| Add 2 | $XX.XX | XX% | [Level description] ⭐ BEST |
| STOP | $XX.XX | Exit | -XX.X% from entry |
| PT1 | $XX.XX | Cover XX% | +XX.X% |
| PT2 | $XX.XX | Cover XX% | +XX.X% |

**R/R Ratio:** X.X:1

### Action Plan
- **NOW:** [Immediate action]
- **ADD:** [When to add]
- **STOP:** [Exit criteria]
- **TARGET:** [Price target]

---

## VERDICT

**[RECOMMENDATION]**

| Metric | Value |
|--------|-------|
| Weighted Score | XX.X/100 |
| Brooks Probability | XX% |
| **McMillan Options Score** | **XX/100** ⭐ NEW |
| **Options Strategy** | **[Strategy Name]** ⭐ NEW |
| Historical | XX% [LONG/SHORT] |
| Confidence | [HIGH/MEDIUM/LOW] |

**Bottom Line:** [1-2 sentence summary with key thesis, options strategy, and action]

---

*All data from MCP tools - [source] tags above*
```

---

## WORKFLOW

```python
# PHASE 1-7: Data Collection (12 min) - BULLET POINTS ONLY
get_ticker_data(), calculate_fundamental_scores_tool()
get_earnings_history(), get_nasdaq_earnings_calendar()
analyze_options_mcmillan(ticker, direction="LONG")  # ⭐ McMillan Options
get_insider_trades(), get_institutional_holders()
analyze_technical()  # ⭐ Now includes Al Brooks output in 'al_brooks' section
analyze_ml_enhanced(), calculate_relative_strength_tool()
analyze_volume_tool(), get_cnn_fear_greed_index()

# PHASE 8: Al Brooks (15 min) - DETAILED
# Use analyze_technical().al_brooks for: always_in_direction, pattern, probability
# Add bar-by-bar analysis, probability factors, context adjustments

# PHASE 10: Trading Plan (3 min) - DETAILED FIRST!
# Weighted score, position sizing, action plan
# DETERMINE: PT1, PT2, holding period, direction, options strategy

# PHASE 9: Historical (2 min) - USE TRADING PLAN TARGETS!
# ⚠️ MUST use actual targets from Phase 10
find_similar_historical_setups(
    ticker="XXXX",
    target_return_pct=PT1_or_PT2,  # From YOUR Trading Plan
    holding_period_days=YOUR_HOLD, # From YOUR Trading Plan
    direction="LONG/SHORT"         # From YOUR Trading Plan
)
```

---

**Time:** 35 minutes | **Output:** ~210 lines | **Quality:** Institutional-grade
**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy)
