# Comprehensive Trading Report Generator

## Purpose
Generate professional trading reports that integrate ALL investor-agent tools with Al Brooks price action methodology to create actionable trade plans.

## Report Structure (Based on Template)

### 1. STOCK OVERVIEW
- Company name, ticker, sector
- Market cap, business model
- Recent catalysts (earnings, news, events)
- Key highlights and strategic initiatives

**Tools to Use:**
```
get_ticker_data(ticker, max_news=10)
get_earnings_history(ticker, max_entries=4)
```

---

### 2. TECHNICAL ANALYSIS - AL BROOKS METHODOLOGY

This is the CRITICAL section that sets professional reports apart.

#### A. Multi-Timeframe Structure Analysis

**Monthly/Weekly Chart (Higher Timeframe):**
- Overall trend direction (bull/bear/range)
- Major swing highs and lows
- Key support/resistance levels
- Trend strength and phase

**Daily Chart (Trading Timeframe):**
- Current price action structure
- Recent bar analysis (last 10-20 bars)
- Pattern identification
- Volume characteristics

**Intraday (15m/1h for day trades):**
- Intraday structure
- Entry timing patterns

**Tools to Use:**
```
# Price data
get_price_history(ticker, period="1y")  # For monthly context
get_price_history(ticker, period="3mo") # For daily analysis
fetch_intraday_1h(ticker, window=200)   # For intraday

# Technical analysis
analyze_technical(ticker, period="6mo")
find_support_resistance(ticker, lookback_period="3mo")
detect_chart_patterns(ticker, period="3mo")
analyze_trend_strength(ticker, period="6mo")

# CRITICAL: Bootstrap tools
analyze_volume_tool(ticker, period="3mo", vwap_mode="session")
analyze_volatility_tool(ticker, period="6mo")
```

#### B. Al Brooks Key Concepts to Include

Reference Al Brooks books at: `/Users/AhmedE/Documents/books/AI-Brooks/`

**Books Available:**
1. Trading Price Action - Trends
2. Trading Price Action - Reversals  
3. Trading Price Action - Trading Ranges

**Core Concepts to Analyze:**

1. **Always-In Direction**
   - Is market Always-In Long or Always-In Short?
   - What would cause Always-In to flip?

2. **Market Structure**
   - Bull trend (higher highs, higher lows)
   - Bear trend (lower highs, lower lows)
   - Trading range (horizontal movement)
   - Channel vs spike vs trading range

3. **Bar-by-Bar Analysis**
   For last 5-10 bars, describe:
   - Bar type (trend bar, doji, reversal bar)
   - Close position (near high/low/middle)
   - Size relative to average
   - Tails/wicks (rejection)
   - Context within trend

4. **Pattern Recognition**
   Brooks patterns to identify:
   - **Flags** (bull/bear) - pullback in trend
   - **Wedges** (bull/bear top/bottom) - 3 pushes with divergence
   - **Channels** - parallel trend lines
   - **Double tops/bottoms** - major reversal
   - **Failed breakouts** - traps
   - **Triangles** - compression before breakout
   - **Trading ranges** - horizontal movement

5. **Entry Patterns**
   Brooks setups:
   - **High 1, High 2, High 3** (bull pullback entries)
   - **Low 1, Low 2, Low 3** (bear pullback entries)
   - **Breakout pullback** (first or second entry)
   - **Failed breakout** (reversal trade)
   - **Wedge reversal** (climactic exhaustion)
   - **Trading range reversal** (boundaries)

6. **Probability Assessment**
   - Setup probability (40%, 60%, etc.)
   - Context factors affecting probability
   - Trader's equation calculation

---

### 3. FUNDAMENTAL ANALYSIS

**Valuation Metrics:**
- Forward P/E, Price/Book, Market Cap
- Enterprise Value
- Book Value per Share

**Profitability & Growth:**
- Recent earnings performance
- Revenue growth
- Profit margins
- Operating efficiency

**Balance Sheet:**
- Total assets/equity
- Cash position
- Debt levels and ratios
- Credit profile

**Tools to Use:**
```
get_ticker_data(ticker)
get_financial_statements(ticker, statement_types=["income", "balance", "cash"], frequency="quarterly", max_periods=8)
calculate_fundamental_scores_tool(ticker)  # F-Score, Z-Score
```

---

### 4. SENTIMENT & POSITIONING

**Analyst Sentiment:**
- Recommendation distribution
- Price targets
- Recent changes

**Institutional Holdings:**
- Top holders
- Ownership concentration
- Recent changes

**Insider Activity:**
- Recent buys/sells
- Size and significance
- Timing relative to events

**Options Flow:**
- Open interest at key strikes
- Put/Call ratio
- Unusual activity

**Short Interest:**
- Current short %
- Days to cover
- Recent changes

**Tools to Use:**
```
get_institutional_holders(ticker, top_n=20)
get_insider_trades(ticker, max_trades=20)
get_options(ticker, num_options=20)
```

---

### 5. CATALYST VERIFICATION

**Primary Catalysts:**
Verify all mentioned catalysts with sources:
- Earnings (dates, results, guidance)
- Product launches
- Partnerships
- Regulatory approvals
- Management changes

**Macro Environment:**
- Sector trends
- Market conditions
- Economic factors

**Tools to Use:**
```
get_nasdaq_earnings_calendar(date="YYYY-MM-DD")
get_ticker_data(ticker, max_news=10)
get_google_trends(keywords=[...])
```

---

### 6. TRADE PLAN & RECOMMENDATION 🎯

This is where EVERYTHING comes together into an actionable plan.

#### Step-by-Step Trade Plan Construction:

**A. Direction Decision**
```
LONG / SHORT / WAIT

Rationale (checklist):
✓/✗ Technical breakout/breakdown
✓/✗ Fundamental quality (F-Score ≥5)
✓/✗ Market leader (RS >70)
✓/✗ Volume confirmation
✓/✗ Positive catalysts
✓/✗ Favorable risk/reward
! Concerns to note
```

**B. Entry Strategy**

Based on Al Brooks methodology, provide 3 entry scenarios:

**Scenario 1: Aggressive Entry (25-33% position)**
- Entry Zone: $XX-XX (current area)
- Thesis: Breakout/breakdown continuation
- Stop Loss: $XX (specific level with reasoning)
- Risk: $X per share (X%)

**Scenario 2: Pullback Entry (50% position)** ⭐ BEST
- Entry Zone: $XX-XX (support/resistance test)
- Thesis: Second entry long/short (Brooks playbook)
- Stop Loss: $XX (below/above key level)
- Risk: $X per share (X%)

**Scenario 3: Breakout Confirmation (25-33% position)**
- Entry Zone: $XX+ (above/below key level)
- Thesis: Measured move continuation
- Stop Loss: $XX (recent swing point)
- Risk: $X per share (X%)

**Tools to Use:**
```
analyze_volatility_tool(ticker)  # For ATR-based stops
find_support_resistance(ticker)  # For entry/stop levels
```

**C. Profit Targets**

**PT1 (Conservative): $XX → X% gain**
- Rationale: First resistance / measured move
- Action: Scale 1/3 position

**PT2 (Moderate): $XX → X% gain**
- Rationale: Measured move / key level
- Action: Scale 1/3 position

**PT3 (Aggressive): $XX → X% gain**
- Rationale: Extension / trend continuation
- Action: Final 1/3 or trailing stop

**D. Stop Loss Management**

**Initial Stop:** $XX
- Invalidation point: [What would prove setup wrong]
- Based on: [2.5x ATR / swing level / pattern breakdown]

**Trailing Stop Strategy:**
1. Move to breakeven at: $XX (after X% gain)
2. Trail at $X below swing highs (after PT1 hit)
3. Tighten to $X below (after PT2 hit)

**E. Position Sizing**

```
CRITICAL: Use ATR-based sizing from analyze_volatility_tool()

Entry: $XX.XX
Stop: $XX.XX
Risk per Share: $X.XX (X%)

For 1% account risk on $100k account:
- Total risk allowed: $1,000
- Risk per share: $X.XX
- Shares: 1,000 / X.XX = XXX shares
- Total position: $XX,XXX (X% of account)

Adjust for volatility:
- High volatility (ATR >5%): Reduce to 0.5% risk
- Normal volatility (ATR 2-5%): Standard 1% risk
- Low volatility (ATR <2%): Can increase to 1.5% risk
```

**F. Risk/Reward Calculation**

```
Entry: $XX.XX
Stop: $XX.XX
Target (PT2): $XX.XX

Risk: $X.XX per share (X%)
Reward: $X.XX per share (X%)

R/R Ratio: X.X:1

✓ Minimum 2:1 required
✓ Preferred 3:1 or better
```

**G. Probability Assessment (Brooks Style)**

```
Setup Probability: XX%

Trader's Equation:
XX% × $X.XX (reward) - (100-XX)% × $X.XX (risk) = $X.XX

Expected Value: $X.XX per share

✓ POSITIVE = Take trade
✗ NEGATIVE = Skip trade
```

**H. Trade Management Rules**

```
ENTRY CONDITIONS (ALL must be true):
✓ Setup identified
✓ Stop level clear
✓ Risk/reward >2:1
✓ Volume confirms
✓ Always-In aligned
✓ Position sized correctly

EXIT CONDITIONS (ANY triggers exit):
✗ Stop hit
✗ Target reached
✗ Pattern invalidated
✗ Volume divergence
✗ Time stop (X days)
```

---

### 7. CONFIDENCE LEVEL & RISK ASSESSMENT

**Overall Confidence: XX% (HIGH/MEDIUM/LOW)**

**Bullish Factors (+):**
1. Factor 1 (+X%)
2. Factor 2 (+X%)
3. ... (list all)

**Bearish Factors (-):**
1. Risk 1 (-X%)
2. Risk 2 (-X%)
3. ... (list all)

**Net Score:** +XX% bullish/bearish tilt

**Risk Categories:**

**HIGH RISK:**
- List high-impact risks

**MEDIUM RISK:**
- List medium-impact risks

**LOW RISK:**
- List low-impact risks

**Tools to Use:**
```
calculate_relative_strength_tool(ticker, benchmark="SPY", period="3mo")
# RS <50 = HIGH RISK (laggard)
# RS 50-70 = MEDIUM RISK
# RS >70 = LOW RISK (leader)
```

---

### 8. TIME HORIZON

- **Short-term (1-4 weeks):** Expected move and targets
- **Medium-term (1-3 months):** Potential scenarios
- **Long-term (6-12 months):** Fundamental trajectory

---

### 9. FINAL VERDICT

**TRADE RECOMMENDATION: BUY/SELL/WAIT with [Entry Type]**

**Optimal Strategy:**
1. Entry 1: XX% position at $XX-XX
2. Entry 2: XX% position on pullback to $XX-XX
3. Entry 3: XX% position on breakout above/below $XX

**For Conservative Traders:**
- Specific conservative approach

**For Aggressive Traders:**
- Specific aggressive approach

**Key Monitoring Points:**
1. Key level 1
2. Key level 2
3. Volume pattern
4. Any other critical factors

---

### 10. AL BROOKS WISDOM - FINAL CONTEXT

Include relevant quote or concept from Brooks books that applies to this setup.

Example format:
```
From "Trading Price Action Trends" (Chapter X):

"[Relevant Brooks quote]"

Application to [TICKER]:
[Explain how this applies to the current setup]

Brooks teaches: [Key lesson]

Bottom Line: [Synthesis of analysis with Brooks principles]
```

---

## Complete Workflow for AI Agents

### Phase 1: Data Collection (10 minutes)

```python
# Market Overview
get_market_movers()
get_cnn_fear_greed_index()

# Stock Data
ticker_data = get_ticker_data(ticker, max_news=10)
price_history = get_price_history(ticker, period="1y")
financials = get_financial_statements(ticker, statement_types=["income", "balance", "cash"])
earnings = get_earnings_history(ticker)
institutions = get_institutional_holders(ticker, top_n=20)
insiders = get_insider_trades(ticker, max_trades=20)
options = get_options(ticker, num_options=20)
```

### Phase 2: Critical Analysis (15 minutes)

```python
# BOOTSTRAP TOOLS (MANDATORY)
volume_analysis = analyze_volume_tool(ticker, period="3mo")
volatility_analysis = analyze_volatility_tool(ticker, period="6mo")
relative_strength = calculate_relative_strength_tool(ticker, benchmark="SPY")
fundamental_scores = calculate_fundamental_scores_tool(ticker)

# Technical Analysis
technical = analyze_technical(ticker, period="6mo")
support_resistance = find_support_resistance(ticker)
patterns = detect_chart_patterns(ticker)
trend_strength = analyze_trend_strength(ticker)
```

### Phase 3: Al Brooks Analysis (20 minutes)

**Read relevant sections from Brooks books:**
- `/Users/AhmedE/Documents/books/AI-Brooks/Trading Price Action Trends (Al Brooks).pdf`
- `/Users/AhmedE/Documents/books/AI-Brooks/Trading Price Action - Reversals (Al Brooks).pdf`
- `/Users/AhmedE/Documents/books/AI-Brooks/Trading Price Action Trading Ranges (Al Brooks).pdf`

**Apply Brooks methodology:**
1. Identify market structure (trend/range/channel)
2. Determine Always-In position
3. Analyze last 10-20 bars
4. Identify specific setup patterns
5. Calculate probability
6. Determine entry, stop, target

### Phase 4: Trade Plan Construction (10 minutes)

Synthesize all data into:
1. Direction decision (long/short/wait)
2. Entry scenarios (3 options)
3. Stop loss levels (ATR-based)
4. Profit targets (measured moves)
5. Position sizing (risk-based)
6. Risk/reward calculation
7. Probability assessment
8. Management rules

### Phase 5: Report Writing (15 minutes)

Write comprehensive report following template structure with:
- All sections completed
- Specific numbers and levels
- Clear reasoning
- Actionable recommendations
- Risk disclaimers

**Total Time: 70 minutes for professional-grade report**

---

## Critical Rules for AI Agents

### ALWAYS DO:
✓ Run ALL bootstrap tools (volume, volatility, RS, F-Score)
✓ Calculate ATR-based stops (2.5x ATR minimum)
✓ Verify volume confirmation
✓ Check RS >70 for longs (leaders only)
✓ Provide specific entry/stop/target prices
✓ Calculate risk/reward and expectancy
✓ Include Brooks methodology explicitly
✓ Reference Brooks books for context
✓ Size positions based on ATR
✓ Provide multiple entry scenarios

### NEVER DO:
✗ Arbitrary stop losses (2%, 5%, etc.)
✗ Ignore volume analysis
✗ Buy laggards (RS <70)
✗ Skip fundamental quality check (F-Score)
✗ Recommend trades without specific levels
✗ Ignore insider selling
✗ Chase breakouts without pullback plan
✗ Use gut feel instead of probability
✗ Skip multi-timeframe analysis
✗ Forget risk disclaimers

---


## Quality Checklist

Before finalizing report, verify:

- [ ] All 10 sections completed
- [ ] Specific prices for entry/stop/target (not ranges)
- [ ] ATR-based stop calculation shown
- [ ] Position sizing formula included
- [ ] Risk/reward ratio calculated
- [ ] Probability assessment with trader's equation
- [ ] Al Brooks concepts explicitly referenced
- [ ] Multi-timeframe analysis included
- [ ] Volume confirmation addressed
- [ ] RS >70 for longs verified (or explained if not)
- [ ] F-Score checked (or explained if poor)
- [ ] Insider activity noted
- [ ] Catalyst verification with sources
- [ ] Time horizons specified
- [ ] Conservative and aggressive options provided
- [ ] Risk disclaimers included

---

**This framework ensures every report is comprehensive, actionable, and professional.**
