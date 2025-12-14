# Concise Trading Report Generator

Fast analysis with bullet points for data, detailed Al Brooks and Trading Plan.

**Structure:** ~185 lines | **Time:** 30 minutes | **Framework:** 9-Phase Institutional

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

### Phase 3: Smart Money (17.9%) - [BULLISH/BEARISH/NEUTRAL] [✓/✗]
- Insider activity: [Description] [get_insider_trades]
- Options P/C: X.XX ([Bullish/Bearish]) [get_options]
- Unusual activity: [Description] [get_options]
- **Score: XX/100** → XX.X pts

### Phase 4: Institutions (4.5%) - [ACCUMULATING/DISTRIBUTING/MIXED]
- Top holders: [Vanguard X%, BlackRock X%] [get_institutional_holders]
- 13F changes: [+/-X% net] [get_institutional_holders]
- **Score: XX/100** → XX.X pts

### Phase 5: Technical (17.9%) - [BULLISH/BEARISH/NEUTRAL] [✓/✗]
- RSI: XX.X ([Overbought/Neutral/Oversold]) [analyze_technical]
- MACD: [Bullish/Bearish] (X.XX) [analyze_technical]
- Price vs EMA20: +/-XX.X%, vs VWAP: +/-XX.X% [analyze_technical]
- RS vs SPY: XX ([LEADER/LAGGARD]) [calculate_relative_strength_tool]
- Trend: [UPTREND/DOWNTREND], XX.X% confidence [analyze_ml_enhanced]
- OBV: [Accumulation/Distribution] [analyze_volume_tool]
- **Score: XX/100** → XX.X pts

### Phase 6: Market Context (5.3%) - [BULLISH/BEARISH/NEUTRAL]
- Fear & Greed: XX.X ([Extreme Fear/Fear/Neutral/Greed/Extreme Greed]) [get_cnn_fear_greed_index]
- **Score: XX/100** → XX.X pts

---

## PHASE 7: AL BROOKS PRICE ACTION (19.6%) ⭐ CRITICAL

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

## PHASE 8: HISTORICAL CONFIRMATION (0% Weight)

- **Setups Found:** XX [find_similar_historical_setups]
- **[LONG/SHORT] Success:** XX%
- **Confidence:** [HIGH/MEDIUM/LOW]
- **Status:** [✅ STRONG / ⚠️ LIMITED / ✗ WEAK]

---

## TRADING PLAN 🎯

### Weighted Score ([LONG/SHORT])
```
Fundamentals:  XX.X pts (XX/100 × 19.6%)
Catalysts:     XX.X pts (XX/100 × 15.2%)
Options:       XX.X pts (XX/100 × 13.4%)
Insiders:      XX.X pts (XX/100 × 4.5%)
Institutions:  XX.X pts (XX/100 × 4.5%)
Technical:     XX.X pts (XX/100 × 17.9%)
Context:       XX.X pts (XX/100 × 5.3%)
Al Brooks:     XX.X pts (XX/100 × 19.6%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL:         XX.X/100 ([HIGH/MODERATE/LOW] CONVICTION [LONG/SHORT])
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
| Historical | XX% [LONG/SHORT] |
| Confidence | [HIGH/MEDIUM/LOW] |

**Bottom Line:** [1-2 sentence summary with key thesis and action]

---

*All data from MCP tools - [source] tags above*
```

---

## WORKFLOW

```python
# PHASE 1-6: Data Collection (10 min) - BULLET POINTS ONLY
get_ticker_data(), calculate_fundamental_scores_tool()
get_earnings_history(), get_nasdaq_earnings_calendar()
get_options(), get_insider_trades(), get_institutional_holders()
analyze_technical(), analyze_ml_enhanced(), calculate_relative_strength_tool()
analyze_volume_tool(), get_cnn_fear_greed_index()

# PHASE 7: Al Brooks (15 min) - DETAILED
# Bar-by-bar, patterns, probability factors, context adjustments

# PHASE 8: Historical (2 min) - BRIEF
find_similar_historical_setups()

# PHASE 9: Trading Plan (3 min) - DETAILED
# Weighted score, position sizing, action plan
```

---

**Time:** 30 minutes | **Output:** ~185 lines | **Quality:** Institutional-grade
