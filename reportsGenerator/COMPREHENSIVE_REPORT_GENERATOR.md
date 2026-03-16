# Comprehensive Trading Report Generator

Generate institutional-grade reports integrating all investor-agent tools with Al Brooks, McMillan, and Dalio methodology.

**Report Structure:** 13 sections | **Framework:** 10-Phase Institutional
**Reference:** See [TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md) for methodology details (Brooks patterns, McMillan strategy matrix, Dalio metrics, position management, scoring tiers).

---

## QUESTRADE TOKEN WARNING

**NEVER write Python scripts to access data** — consumes the single-use refresh token.
**ALWAYS use MCP tools ONLY.** If HTTP 400 errors occur, see [CLAUDE.md](CLAUDE.md) for recovery.

---

## REPORT OUTPUT: OBSIDIAN VAULT

**MANDATORY:** Save the complete report as markdown in the Obsidian vault.

```text
Path: /Users/AhmedE/Ahmed/Trading Reports/
Filename: TICKER_COMPREHENSIVE_YYYY-MM-DD.md
```

Use the `Write` tool. Save AFTER generating the full report (not incrementally).

---

## CRITICAL RULES

### Data Integrity

1. **NEVER fabricate numbers** — If a tool fails, report "DATA UNAVAILABLE"
2. **NEVER estimate scores** — Only use actual tool outputs
3. **NEVER guess probabilities** — If data is insufficient, say "INSUFFICIENT DATA"
4. Every number in the report MUST trace back to a specific tool output
5. Tag every data point with its source: `**RSI:** 73.78 [analyze_technical]`

### Error Handling

When a tool fails:
```markdown
⚠️ **DATA ERROR** — Tool: `[tool_name]` | Error: [message]
Score: N/A (excluded from weighted calculation)
```

### Catalyst Verification (MANDATORY)

1. ALWAYS run `detect_catalyst_strength()` before analyzing catalysts
2. Check `verification_rate ≥ 50%` before recommending trade
3. If `trade_allowed = False` → DO NOT RECOMMEND TRADE
4. Old news (>3 days) = STALE — already priced in

### Async Functions (use MCP tools — they handle async automatically)

Async: `get_cnn_fear_greed_index()`, `get_nasdaq_earnings_calendar()`, `find_similar_historical_setups()`, `analyze_ml_enhanced()`, `calculate_feature_importance_analysis()`, `get_market_movers()`

Sync: `get_ticker_data()`, `get_financial_statements()`, `get_options()`, `analyze_options_mcmillan()`, `get_insider_trades()`, `get_institutional_holders()`, `get_earnings_history()`, `analyze_technical()`, `find_support_resistance()`, `analyze_volume_tool()`, `analyze_volatility_tool()`, `calculate_relative_strength_tool()`, `analyze_multitimeframe()`

### Market Hours Check

Before calling intraday functions (`fetch_intraday_1h`, `fetch_intraday_15m`): check if market is open (weekday, 9:30 AM - 4:00 PM ET). If closed, skip intraday calls and note: "⚠️ [WEEKEND/AFTER-HOURS] — Intraday data not available"

---

## MANDATORY SECTION ORDER

**The report MUST follow this logical flow. Do NOT put Options before Technical Analysis.**

```
0. Macro Context Header
1. Executive Summary + Direction Validation
2. Stock Overview (company info, fundamentals)
3. Price Action Analysis (Multi-Timeframe + Al Brooks TOGETHER — not separate)
   - Multi-timeframe is PART OF Brooks: Monthly → Weekly → Daily confluence
4. Fundamental Analysis
5. Smart Money Positioning
6. McMillan Options Strategy (AFTER technical — options strategy is informed by price action)
7. Trading Plan (LAST — synthesizes everything above)
```

---

## REPORT SECTIONS

### 0. MACRO CONTEXT HEADER `[generate_macro_context_header]` + `[analyze_vix_term_structure]`

**MUST appear at the VERY TOP of every report, before Executive Summary.**

| Metric | Value | Signal |
|--------|-------|--------|
| **Regime** | {macro_summary.regime} | [EXPANSION / LATE_CYCLE / CONTRACTION / RECOVERY] |
| **Yield Curve** | {macro_summary.yield_curve} | [NORMAL / FLAT / INVERTED] (spread: X.XX%) |
| **VIX** | {macro_summary.vix} | [COMPLACENT / NORMAL / ELEVATED / PANIC] |
| **VIX Term Structure** | {vix_vix3m_ratio} | [CONTANGO / BACKWARDATION] |
| **Credit** | {macro_summary.credit} | HYG/LQD ratio |
| **Fed Stance** | {macro_summary.fed_policy_stance} | [DOVISH / NEUTRAL / HAWKISH] |
| **Options Bias** | {macro_summary.options_strategy_bias} | [BUY_PREMIUM / SELL_PREMIUM / NEUTRAL] |

**Macro Narrative:** {narrative}

**Trading Implications:** {trading_implications}

**Tools:** `generate_macro_context_header(include_breadth=True, include_intermarket=True)`, `analyze_vix_term_structure()`

---

### 1. EXECUTIVE SUMMARY

**Quick Decision Snapshot**

**Recommendation:** [STRONG BUY / BUY / HOLD / SELL / STRONG SELL]
**Conviction:** [HIGH / MODERATE / LOW] — Based on gates passed + weighted score

**Target Price:** $XXX.XX (+XX% upside) | **Stop Loss:** $XXX.XX (-X%)

**Investment Thesis (3 bullets):**
1. [Primary catalyst/driver]
2. [Technical setup — Brooks pattern + probability]
3. [Smart money confirmation — Dalio + institutional flow]

**Top Risks (2-3 bullets):**
1. [Key risk]
2. [Secondary risk]

**Quick Stats:**
- **Weighted Score:** XX/100 (Phases 1-8)
- **Brooks Probability:** XX% (context-informed)
- **Historical Success:** XX% (XX similar setups, p=X.XXX)
- **Risk/Reward:** X.X:1

**Bottom Line:** [1-2 sentence summary with clear action]

---

### 1B. DIRECTION VALIDATION

**Purpose:** Validates that direction is supported by INDEPENDENT data sources.

**Scanner Origin:** [LONG/SHORT candidate or "Direct Analysis"]
**Data Consensus:** [LONG/SHORT/NO_CONSENSUS]

**Direction Votes:**

| Tool | Vote | Reason |
|------|------|--------|
| Catalyst | [BULLISH/BEARISH/NEUTRAL] | [Primary catalyst] |
| CVD | [BULLISH/BEARISH] | [Volume delta trend] |
| Exhaustion | [LONG/SHORT] | [Fresh direction] |
| Brooks Always-In | [LONG/SHORT/NEUTRAL] | [Price action] |
| Dalio Ratio | [BULLISH/BEARISH] | [>1.0 BULLISH / <1.0 BEARISH] |
| Dollar Flow | [BULLISH/BEARISH] | [Positive/Negative] |
| Weekly Trend | [BULLISH/BEARISH/MIXED] | Weekly Always-In direction |

**Consensus:** X LONG votes, Y SHORT votes

- If aligned: ✅ **DIRECTION CONFIRMED** — proceed with full confidence
- If conflict: 🚨 **DIRECTION CONFLICT** — reduce size 50%, use tighter stops, re-analyze in 2-3 days

**Tools:** `generate_trading_signal()` → `direction_votes`, `data_direction`

---

### 2. STOCK OVERVIEW

**Company Profile:**
- Ticker, company name, sector, industry
- Market cap, business model summary

**Recent Catalysts:**
- Earnings (upcoming or recent < 30 days)
- Product launches, partnerships, regulatory, management changes

**Tools:** `get_ticker_data()`, `get_earnings_history()`

---

### 2B. SUPPLEMENTAL RESEARCH (Web Search)

**Purpose:** Surface recent information NOT captured by MCP tools — analyst commentary, regulatory filings, competitive developments, management guidance.

**When to Use:** ALWAYS run for comprehensive reports. Web search supplements (does NOT replace) MCP tool data.

**Search Queries** (run 2-3 targeted searches):
1. `"[TICKER] [Company Name] latest news analyst upgrade downgrade"` — Recent analyst actions & news
2. `"[TICKER] earnings guidance outlook 2026"` — Forward guidance & management commentary
3. `"[TICKER] SEC filing insider buyback"` — Regulatory filings, buyback authorizations

**Output Format:**

#### Recent Analyst Actions (Web Search)
| Date | Firm | Action | Rating | Price Target | Notes |
|------|------|--------|--------|-------------|-------|
| MM/DD | [Firm] | [Upgrade/Downgrade/Initiate] | [Buy/Hold/Sell] | $XXX | [Key reason] |

#### Key Developments (Last 30 Days)
- **[Date]:** [Development summary + source]
- **[Date]:** [Development summary + source]

#### Management Guidance (If Available)
- **Revenue Guidance:** $XXB-$XXB (FY20XX)
- **Margin Outlook:** [Expanding/Stable/Compressing]
- **Key Themes:** [AI, cloud, cost cuts, etc.]

**⚠️ RULES:**
- Tag all web-sourced data as `[WebSearch]` — clearly distinguish from MCP tool data
- Do NOT use web data to override MCP tool scores — it provides context only
- If web search is unavailable or returns no results, note: "Web search unavailable — analysis based on MCP tool data only"
- Cross-reference web findings with `detect_catalyst_strength()` output for consistency

**Tools:** WebSearch (Claude built-in), `detect_catalyst_strength()`

---

### 3. PRICE ACTION ANALYSIS (Al Brooks — Phase 7)

**See [TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md) for pattern definitions, bar reading guide, and trap recognition.**

#### A. Multi-Timeframe Structure

**Monthly:** Trend from SMA 10/20, RSI, MACD on monthly bars `[analyze_multitimeframe]`
**Weekly:** Al Brooks bar reading — Always-In, pattern, trend strength `[analyze_multitimeframe]`
**Weekly S/R:** Weekly support/resistance levels (stronger than daily) `[analyze_multitimeframe]`
**Daily:** Current structure, pattern, volume `[analyze_technical]`
**Intraday:** ⚠️ Check market hours. If open: 15m/1h momentum. If closed: skip.

**Confluence Score:** `[analyze_multitimeframe]`

| Metric | Value |
|--------|-------|
| Score | XX/100 |
| Grade | [A/B/C/D/F] |
| Alignment | [ALIGNED/PARTIAL/CONFLICTING] |
| Swing Suitability | [HIGH/MODERATE/LOW/AVOID] |

#### B. Brooks Analysis

**Always-In Direction:** [LONG/SHORT/NEUTRAL] `[analyze_ml_enhanced]`

**Market Structure:**
- **Trend Type:** [Strong Bull / Weak Bull / Range / Weak Bear / Strong Bear / Channel]
- **Trend Phase:** [Breakout / Acceleration / Exhaustion / Correction]

**Primary Pattern:** [Name — e.g., High 2, Low 1, Failed Breakout, Wedge]
- **Setup Type:** [Specific Brooks identification]
- **Pattern Completion:** [X% complete / Needs confirmation]
- **Base Probability:** XX%

**Trap Analysis:**
- **Bull Trap Risk:** [High/Medium/Low] — [Why]
- **Bear Trap Risk:** [High/Medium/Low] — [Why]
- **Failed Breakout:** [Above/Below $XXX creates trap]

**Bar-by-Bar Analysis (Last 5 bars):**

For each bar: Type (bull/bear/doji/inside), Close (near high/low/middle), Size, Tails, Volume, Interpretation.

**Pattern Observations:** [Trend strength, momentum, overlap analysis]

#### C. Price Action Levels

| Level | Price | Distance | Description |
|-------|-------|----------|-------------|
| R3 | $XXX.XX | +XX% | Major resistance / Target 3 |
| R2 | $XXX.XX | +XX% | Resistance / Target 2 |
| R1 | $XXX.XX | +XX% | Near resistance / Target 1 |
| CURRENT | $XXX.XX | 0% | Entry zone |
| S1 | $XXX.XX | -X% | Near support / STOP LOSS |
| S2 | $XXX.XX | -XX% | Support |
| S3 | $XXX.XX | -XX% | Major support |

**Key Indicators:** VWAP, EMA20, EMA50, SMA200, RS vs SPY

**Pullback Personality:** `[analyze_pullback_personality]`
- **Ranked Entry Levels:** [Top 3-5 confluence zones with scores]
- **MA Bounce Rates:** EMA20 XX%, SMA50 XX%, SMA200 XX% (historical)
- **ICT Levels:** Order Blocks, Fair Value Gaps, Liquidity Pools
- **Mean Reversion:** Half-life XX bars, Z-score XX.XX
- **Regime Depth:** [SHALLOW / NORMAL / DEEP] pullbacks in current regime

**Supply/Demand Zones:** `[analyze_ml_enhanced → supply_demand]`

| Zone Type | Price Range | Strength | Evidence | Distance |
|-----------|-------------|----------|----------|----------|
| Supply | $XXX - $XXX | [High/Low] | [Rejections, volume] | +XX% |
| CURRENT | $XXX.XX | - | - | 0% |
| Demand | $XXX - $XXX | [High/Low] | [Bounces, volume] | -XX% |

**Order Blocks:** `[analyze_ml_enhanced → order_blocks]`

| Block Type | Price Range | Age | Impulse | Distance | Signal |
|------------|-------------|-----|---------|----------|--------|
| Bullish OB | $XXX - $XXX | X days | +X.X% | -X.X% | [TESTING/NEAR/FAR] |
| Bearish OB | $XXX - $XXX | X days | -X.X% | +X.X% | [TESTING/NEAR/FAR] |

#### D. Context-Informed Brooks Probability

**Base Pattern Probability:** XX% ([Pattern name])

**Context Adjustments:** (See [TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md) for full adjustment table)
- Fundamentals (Phase 1): +/- XX%
- Catalyst (Phase 2): +/- XX%
- Options Flow (Phase 3): +/- XX%
- Insider/Institutional (Phase 4-5): +/- XX%
- Technical Strength (Phase 6): +/- XX%
- Market Context (Phase 7): +/- XX%
- Dalio (Ratio + Flow + Sustainability): +/- XX%

**Final Brooks Probability:** XX% (capped 30-80%)

**AL BROOKS PRICE ACTION SCORE: XX/100**
- Pattern Quality: XX/30 | Bar Reading: XX/25 | Context Alignment: XX/25 | Trap Avoidance: XX/20

#### E. Brooks Lesson (Pattern-Indexed from BROOKS_MASTERY_GUIDE.md)

**Pattern:** {pattern_name} — {pattern_lesson.name}
**Brooks Quote:** "{pattern_lesson.brooks_quote}"
**Win Rate:** {pattern_lesson.win_rate}
**Why This Works Here:** {lesson — from `brooks_analysis.lesson` in generate_trading_signal()}

**Trap Analysis:**
- **Trap Type:** {trap_type} — {trap_classification.explanation}
- **Severity:** {trap_classification.severity}
- **Action:** {trap_classification.action}

**Probability Breakdown:** (from `brooks_analysis.probability_narrative`)
```
{probability_narrative — shows each adjustment: Base 50% + X% pattern + Y% Always-In...}
```

**Measured Move Targets:**

| Method | Target | Source |
|--------|--------|--------|
| Leg1=Leg2 | ${leg1_leg2} | Prior leg projected |
| Range Projection | ${range_projection} | Range height from breakout |
| Primary Target | ${primary_target} | Best available method |

**Trend Phase:** {trend_evolution.phase} ({trend_evolution.phase_score}/100)
{trend_evolution.transition_signals — if any}

**Confirmation Status:** {confirmation_status.confirmed} — {confirmation_status.reason}

**Multi-Timeframe Confirmation:** Monthly [dir] → Weekly [dir] → Daily [pattern]. Confluence: XX/100 Grade [X].
**What Would Invalidate:** [Key level or condition]
**Trader Takeaway:** [1 sentence actionable lesson the trader can learn from this analysis]

**Tools:** `generate_trading_signal()` → `brooks_analysis.*`, `analyze_multitimeframe()`, `find_support_resistance()`

---

#### F. Dalio Economic Machine Analysis

**Principle:** *Price = Total Spending / Quantity Sold* — Ray Dalio

| Metric | Value | Signal |
|--------|-------|--------|
| **Dalio Ratio** | {dalio_ratio.current} | {dalio_ratio.interpretation} ({dalio_ratio.strength}) |
| **Dollar Flow (20d)** | ${cumulative_dollar_flow.20d} | {cumulative_dollar_flow.direction} |
| **Sustainability** | {trend_sustainability.score}/100 | Grade {trend_sustainability.grade} |
| **Institutional Activity** | {institutional_activity.detected} | {institutional_activity.confidence} confidence |
| **Macro Regime** | {regime} | {yield_curve.status} / VIX {vix_regime.status} |

**Spending Analysis:** {lesson — from analyze_dalio_economic_machine()}

**Money Flow Confirmation:**
- If Dalio confirms Brooks direction: "Money flow SUPPORTS the price action — real capital flowing in this direction."
- If Dalio contradicts Brooks: "CAUTION: Money flow CONTRADICTS the pattern. Reduce position size or wait."

**Tools:** `analyze_dalio_economic_machine()`, `get_macro_regime()`

---

#### G. Intermarket Correlations & Expected Move `[analyze_intermarket_correlation]` + `[calculate_expected_move]`

**Intermarket Correlations:** `analyze_intermarket_correlation(ticker, benchmarks=["UUP","^TNX","USO","GLD","SPY","TLT","HYG"])`

| Benchmark | Correlation | Strength | Implication |
|-----------|-------------|----------|-------------|
| SPY | X.XX | [STRONG/MODERATE/WEAK] | [Market beta] |
| UUP (Dollar) | X.XX | [STRONG/MODERATE/WEAK] | [Dollar sensitivity] |
| ^TNX (10Y Yield) | X.XX | [STRONG/MODERATE/WEAK] | [Rate sensitivity] |
| USO (Crude) | X.XX | [STRONG/MODERATE/WEAK] | [Energy correlation] |
| GLD (Gold) | X.XX | [STRONG/MODERATE/WEAK] | [Safe haven correlation] |
| TLT (Long Bonds) | X.XX | [STRONG/MODERATE/WEAK] | [Duration risk] |
| HYG (High Yield) | X.XX | [STRONG/MODERATE/WEAK] | [Credit risk] |

**Regime Implications:** {regime_implications}
**Hedging Suggestions:** {hedging_suggestions}

**Expected Move:** `calculate_expected_move(ticker, dte=30, use_straddle=True)`

| Method | Move ($) | Move (%) | Lower | Upper |
|--------|----------|----------|-------|-------|
| IV-Based | ±$X.XX | ±X.X% | $XXX.XX | $XXX.XX |
| Straddle (×0.85) | ±$X.XX | ±X.X% | $XXX.XX | $XXX.XX |
| **Primary** | **±$X.XX** | **±X.X%** | **$XXX.XX** | **$XXX.XX** |

**Strike Selection Guidance:** Use expected move to validate options strike placement — short strikes should be OUTSIDE the expected move range.

**Tools:** `analyze_intermarket_correlation()`, `calculate_expected_move()`

---

### 4. FUNDAMENTAL ANALYSIS (Phase 1 — 17.9%)

**Valuation:** Forward P/E, Price/Book, EV/EBITDA, Market Cap
**Quality Scores:**
- **Piotroski F-Score:** X/9 [Excellent >7 / Good 5-7 / Poor <5]
- **Altman Z-Score:** X.XX [Safe >2.99 / Gray 1.81-2.99 / Distress <1.81]

**Profitability:** Revenue growth YoY, Net margin, Operating margin, ROE
**Balance Sheet:** Cash, Total debt, Debt/Equity, Current ratio

#### Analyst Consensus [get_ticker_data]

| Metric | Value |
|--------|-------|
| **Consensus Rating** | [Strong Buy / Buy / Hold / Sell / Strong Sell] |
| **# Analysts** | XX covering |
| **Average Price Target** | $XXX.XX (+/-XX% from current) |
| **High Target** | $XXX.XX (+XX%) |
| **Low Target** | $XXX.XX (-XX%) |
| **Recent Changes** | X upgrades, Y downgrades (last 30d) |

**Key Analyst Actions (if available from WebSearch):**
- [Firm Name]: [Upgraded/Downgraded] to [Rating], PT $XXX (Date)

**If <3 analysts covering:** "Limited analyst coverage — consensus unreliable"

#### Forward Outlook [get_ticker_data]

| Metric | TTM (Actual) | Forward (Estimate) | Growth |
|--------|-------------|-------------------|--------|
| EPS | $X.XX | $X.XX | +/-XX% |
| P/E Ratio | XX.X | XX.X (forward) | - |
| Revenue Growth | XX% (TTM) | XX% (est) | [Accelerating/Decelerating] |
| Earnings Growth | - | XX% | [Accelerating/Decelerating] |

**Forward vs Trailing:** [If forward P/E < trailing P/E: Growth expected | If forward > trailing: Deceleration expected]

#### Share Structure [get_ticker_data + get_financial_statements]

| Metric | Value | Signal |
|--------|-------|--------|
| Shares Outstanding | X.XXB | Current float |
| YoY Change | +/-X.X% | [BUYBACK if negative / DILUTION if positive] |
| Buyback Yield | X.X% | Annual repurchase as % of market cap |

**Interpretation:**
- **Declining shares** (negative YoY change) = Active buyback → Bullish (reduces supply, boosts EPS)
- **Rising shares** (positive YoY change) = Dilution → Bearish (stock comp, secondary offerings)
- **Flat** = No significant program

**If buyback active:** "Company repurchasing ~$XXB annually (X.X% yield), supporting EPS growth"
**If dilution:** "⚠️ Share count increasing X.X% YoY — dilution headwind for EPS growth"

**Data:** Compare current `sharesOutstanding` [get_ticker_data] vs prior period from `get_financial_statements()`. If historical shares unavailable, note "Share trend data unavailable — check 10-K for buyback authorization."

**Tools:** `get_financial_statements()`, `calculate_fundamental_scores_tool()`, `get_ticker_data()`

---

### 5. SMART MONEY POSITIONING (Phase 3 — 4.5% + Phase 4 — 4.5%)

#### Options Flow

| Type | Contracts | Premium | % of Total | Signal |
|------|-----------|---------|------------|--------|
| Calls | XXXX | $XXM | XX% | [Signal] |
| Puts | XXXX | $XXM | XX% | [Signal] |
| **P/C Ratio** | **X.XX** | - | - | **[Signal]** |

#### Unusual Options Activity `[detect_unusual_options_activity]`

| Type | Strike | Volume | OI | V/OI | Signal |
|------|--------|--------|-----|------|--------|
| [CALL/PUT] | $XXX | XX,XXX | X,XXX | XX.X | [ITM/OTM] |

**Smart Money Signal:** [BULLISH/BEARISH/MIXED/NO_SIGNAL]

#### Insider Trading `[detect_insider_cluster]`

- Cluster buying: [Yes/No]
- Net insider buying: $XXM
- Timing: [Before catalyst / Routine]

#### Institutional Holdings `[get_institutional_holders]`

**Top 5 Holders:** [List with shares and %]
**13F Changes:** New positions, increased/decreased stakes, net flow [Accumulation/Distribution]

**Tools:** `get_options()`, `get_insider_trades()`, `get_institutional_holders()`, `detect_unusual_options_activity()`

---

### 6. McMILLAN OPTIONS STRATEGY (Phase 3 — 17.9%)

**See [TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md) for IV environment strategy matrix, P/C interpretation framework, Greeks reference, and standard deviation analysis.**

#### A. IV Analysis `[analyze_options_mcmillan]` + `[analyze_iv_term_structure]` + `[analyze_iv_skew]`

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Current IV | XX.X% | ATM implied volatility |
| IV Rank | XX% | Position in 52-week range |
| IV Percentile | XX% | % of days IV was lower |
| 52W High / Low | XX.X% / XX.X% | Historical range |
| Divergence | [ALIGNED/DIVERGENT] | Rank vs Percentile |
| **IV Trend** | **[RISING/FALLING/STABLE]** | **Rank vs Percentile divergence direction** |
| **IV vs HV** | **XX.X% vs XX.X%** | **[OVERPRICED/UNDERPRICED/FAIR]** |
| **IV Environment** | **[HIGH/LOW/NORMAL]** | **Strategy driver** |

**IV Trend Interpretation:**
- **Rank > Percentile:** Recent IV spike — mean reversion likely (IV to fall)
- **Rank < Percentile:** IV compressed below norm — expansion possible (IV to rise)
- **Rank ≈ Percentile (±10):** Stable — aligned with historical pattern

**IV Term Structure:** `[analyze_iv_term_structure]`
- **Shape:** [CONTANGO / BACKWARDATION / FLAT]
- **Front vs Back IV:** XX.X% vs XX.X%
- **Implication:** [CONTANGO = market expects stability / BACKWARDATION = near-term event risk / FLAT = uncertain]

**IV Skew:** `[analyze_iv_skew]`
- **Put Skew:** [STEEP / NORMAL / FLAT]
- **Call Skew:** [STEEP / NORMAL / FLAT]
- **Implication:** [STEEP put skew = expensive downside protection = fear / FLAT = balanced expectations]

#### B. Expected Price Movement (Standard Deviation Ranges)

**Formula:** Expected Move = Price × IV × √(DTE / 365)

| Timeframe | DTE | 1 SD Range (68% prob) | 2 SD Range (95% prob) |
|-----------|-----|-----------------------|-----------------------|
| Weekly | 7 | $XXX.XX - $XXX.XX | $XXX.XX - $XXX.XX |
| Monthly | 30 | $XXX.XX - $XXX.XX | $XXX.XX - $XXX.XX |
| 45 DTE | 45 | $XXX.XX - $XXX.XX | $XXX.XX - $XXX.XX |

#### C. Put/Call & Max Pain

| Metric | Value | Signal |
|--------|-------|--------|
| Volume P/C Ratio | X.XX | [Contrarian signal or neutral] |
| Sentiment | [RAW] | [EXTREMELY_BEARISH to EXTREMELY_BULLISH] |
| Max Pain Strike | $XXX.XX | [Above/Below/At current price] |
| Distance to Max Pain | +/-XX.X% | [Gravitational pull direction] |
| Max Pain Reliability | [HIGH/MEDIUM/LOW] | [Based on DTE + OI] |

**Top OI Strikes:**

| Type | Strike | OI | Significance |
|------|--------|----|-------------|
| Call | $XXX | XXX,XXX | [Call wall / resistance] |
| Put | $XXX | XXX,XXX | [Put wall / support] |

#### D. Greeks Assessment

| Greek | Call | Put | Impact |
|-------|------|-----|--------|
| Delta | X.XX | -X.XX | Directional exposure |
| Gamma | X.XXXX | X.XXXX | Delta change rate |
| Theta | -$X.XX | -$X.XX | Daily time decay |
| Vega | $X.XX | $X.XX | IV sensitivity |

#### E. Strategy Recommendation

**IV [XX%] + Direction [LONG/SHORT] → [SELECTED STRATEGY]**

| Factor | Current | Impact |
|--------|---------|--------|
| IV Environment | [HIGH/LOW/NORMAL] | Strategy type |
| Direction | [LONG/SHORT/NEUTRAL] | Directional bias |
| Holding Period | XX days | Time horizon |

**Primary Strategy:** [e.g., Bull Put Credit Spread / Long Call / Iron Condor]
**Rationale:** [Why this strategy for current IV + direction — 2-3 sentences]

**Alternative Strategies:**

| Strategy | Type | Max Profit | Max Loss |
|----------|------|------------|----------|
| [Alt 1] | [Credit/Debit] | [Description] | [Description] |
| [Alt 2] | [Credit/Debit] | [Description] | [Description] |

#### F. McMillan Options Score

| Factor | Points | Max | Interpretation |
|--------|--------|-----|----------------|
| IV Environment | +XX | 15 | [Favorable/Unfavorable] |
| P/C Contrarian | +XX | 15 | [Aligned/Conflicting] |
| Max Pain Bias | +XX | 10 | [Supportive/Opposing] |
| UOA Signal | +XX | 15 | [Confirming/Mixed] |
| BASE | 50 | 50 | Starting neutral |
| **TOTAL** | **XX/100** | 100 | **[HIGH/MODERATE/LOW]** |

#### G. McMillan Mastery Analysis `[analyze_options_mcmillan → mcmillan_mastery]`

**Volatility Regime:**

| Component | Value | Signal |
|-----------|-------|--------|
| IV Percentile Signal | [ELEVATED / LOW / NORMAL] | `[mcmillan_mastery.volatility_regime.percentile_signal]` |
| IV vs HV Signal | [OVERPRICED / UNDERPRICED / FAIR] | `[mcmillan_mastery.volatility_regime.iv_hv_signal]` |
| **Composite Regime** | **[STRONG_BUY_VOL / BUY_VOL / NEUTRAL / SELL_VOL / STRONG_SELL_VOL]** | `[mcmillan_mastery.volatility_regime.volatility_regime]` |
| Percentile Action | [Sell premium / Buy options / Neutral] | `[mcmillan_mastery.volatility_regime.percentile_action]` |

**Narrative:** `[mcmillan_mastery.volatility_regime.narrative]`

**P/C Ratio Narrative (McMillan Ch.30):**

> [mcmillan_mastery.pc_ratio_narrative — dynamic interpretation of put/call ratio using McMillan's Chapter 30 framework]

**Vega-Theta Trade-Off:**

| Metric | Value |
|--------|-------|
| Seller Risk | **[HIGH / MODERATE / LOW]** `[mcmillan_mastery.vega_theta_tradeoff.seller_risk]` |
| Seller Warning | [Warning text — e.g., "High vega exposure makes short premium risky"] `[mcmillan_mastery.vega_theta_tradeoff.seller_warning]` |
| Buyer Opportunity | [Opportunity text] `[mcmillan_mastery.vega_theta_tradeoff.buyer_opportunity]` |

**Skew Opportunity:**

| Metric | Value |
|--------|-------|
| Skew Type | **[NEGATIVE_SKEW / POSITIVE_SKEW / FLAT_SKEW]** `[mcmillan_mastery.skew_opportunity.skew_type]` |
| Skew Points | X.X `[mcmillan_mastery.skew_opportunity.skew_points]` |
| Recommended Strategies | [Strategy 1, Strategy 2, ...] `[mcmillan_mastery.skew_opportunity.recommended_strategies]` |
| Rationale | [Why these strategies fit the skew] `[mcmillan_mastery.skew_opportunity.rationale]` |

**McMillan Lesson:**

| Field | Value |
|-------|-------|
| **Strategy** | [Strategy name] `[mcmillan_mastery.lesson.strategy]` |
| **McMillan Quote** | *"[Quote from McMillan]"* `[mcmillan_mastery.lesson.mcmillan_quote]` |
| **Chapter** | Ch. XX `[mcmillan_mastery.lesson.chapter]` |
| **Win Rate** | XX% `[mcmillan_mastery.lesson.win_rate]` |
| **When to Use** | [Conditions] `[mcmillan_mastery.lesson.when_to_use]` |
| **Key Risk** | [Primary risk] `[mcmillan_mastery.lesson.key_risk]` |

**Lesson:** `[mcmillan_mastery.lesson.lesson]`

**Summary Fields (also in top-level summary):**

- **Vol Regime:** `[summary.vol_regime]` — `[summary.vol_regime_action]`
- **Skew Type:** `[summary.skew_type]`
- **Vega-Theta Risk:** `[summary.vega_theta_risk]`

**Tools:** `analyze_options_mcmillan()` (returns `mcmillan_mastery` block), `get_options()`, `detect_unusual_options_activity()`

---

#### H. Gamma Exposure (GEX) Analysis `[analyze_gamma_exposure]`

| Metric | Value | Implication |
|--------|-------|-------------|
| **GEX Flip Level** | $XXX.XX | Above = positive gamma (mean-reverting), Below = negative gamma (trending) |
| **Gamma Wall (Call)** | $XXX.XX | Magnetic resistance — dealers sell here |
| **Gamma Wall (Put)** | $XXX.XX | Magnetic support — dealers buy here |
| **Net GEX** | [POSITIVE / NEGATIVE] | Positive = range-bound, Negative = volatile moves |
| **Dealer Positioning** | [LONG_GAMMA / SHORT_GAMMA] | Long = dealers dampen moves, Short = dealers amplify moves |

**GEX + Brooks Integration:**

- [If positive gamma + trading range]: "GEX CONFIRMS range — fade extremes per Brooks"
- [If negative gamma + trend]: "GEX CONFIRMS trend — dealers amplifying directional move"
- [If GEX conflicts with Brooks]: "⚠️ GEX DIVERGENCE — gamma regime conflicts with price action setup"

**Tools:** `analyze_gamma_exposure()`

---

### 6B. OPTIMAL OPTIONS TRADE SETUP (Risk-Managed) `[generate_options_trade_plan]`

**All strategies use SPREADS for defined risk (no naked options).**

**Market Conditions:** IV Rank XX% → [HIGH/LOW] | Direction: [LONG/SHORT] from Brooks + Dalio

| IV Environment | BULLISH | BEARISH |
|----------------|---------|---------|
| LOW (<30%) | Bull Call Debit Spread | Bear Put Debit Spread |
| MEDIUM (30-50%) | Bull Call Debit Spread | Bear Put Debit Spread |
| HIGH (>50%) | Bull Put Credit Spread | Bear Call Credit Spread |

**Trade Structure:**

| Leg | Action | Strike | Expiry | Delta | Premium |
|-----|--------|--------|--------|-------|---------|
| Leg 1 | [BUY/SELL] | $XXX [CALL/PUT] | [Date] | X.XX | $X.XX |
| Leg 2 | [BUY/SELL] | $XXX [CALL/PUT] | [Date] | X.XX | $X.XX |
| Net | [DEBIT/CREDIT] | - | - | - | **$X.XX** |

**Risk/Reward:**

| Metric | Value |
|--------|-------|
| Max Risk | $XXX |
| Max Profit | $XXX |
| Break-Even | $XXX.XX |
| Risk/Reward | 1:X.X |
| Probability of Profit | XX% |

**Position Sizing (1% Account Risk):**

| Account Size | Max Risk (1%) | Max Contracts | Capital |
|--------------|---------------|---------------|---------|
| $25,000 | $250 | X | $XXX |
| $50,000 | $500 | X | $XXX |
| $100,000 | $1,000 | X | $XXX |

**Exit Rules:**

| Condition | Action | Reason |
|-----------|--------|--------|
| Profit Target | Close at 50% max profit | Lock gains |
| Stop Loss | Close at 2x credit received | Limit loss |
| Time Stop | Close at 21 DTE | Gamma risk |
| Direction Change | Close immediately | Thesis invalidated |
| IV Crush | Close after catalyst | Vol drops |

**Pre-Trade Checklist:**
- [ ] IV environment matches strategy
- [ ] Direction confirmed (Brooks + Dalio)
- [ ] Position size ≤ 1% account risk
- [ ] Expiry 30-45 DTE
- [ ] Exit rules defined
- [ ] No earnings within expiry (unless intentional)

**Tools:** `analyze_options_mcmillan()`, `get_options()`, `get_questrade_option_quotes()`, `generate_options_trade_plan()`, `analyze_gamma_exposure()`

---

### 7. CATALYST VERIFICATION (Phase 2 — 13.4%)

**Verification System:** `[detect_catalyst_strength]`

| Metric | Value | Status |
|--------|-------|--------|
| Verification Rate | XX% | [≥50% OK / <50% BLOCKED] |
| High Confidence | X/X catalysts | Credible sources |
| Requires Manual | X catalysts | ⚠️ VERIFY |
| Trade Allowed | [TRUE/FALSE] | Gate result |

**Verified Catalysts:**

| Type | Description | Confidence | Method |
|------|-------------|------------|--------|
| [EARNINGS/NEWS/INSIDER] | [Description] | [HIGH/MEDIUM] | [Source] |

**Unverified Catalysts:**

| Type | Warning | Action |
|------|---------|--------|
| [Type] | [Issue] | [Required action] |

**Primary Catalyst:** [Event, date, expected impact, verification status]
**Earnings Detail:** Estimate $X.XX vs prior $X.XX, beat rate XX%, 10b5-1 check
**News Sentiment:** [BULLISH/BEARISH/NEUTRAL/MIXED]

#### Multi-Timeframe Catalyst Timeline

| Timeframe | Catalyst | Date | Impact | Source |
|-----------|---------|------|--------|--------|
| **Near-term (0-7d)** | [Earnings/FDA/Event] | MM/DD | [HIGH/MED/LOW] | [detect_catalyst_strength] |
| **Medium-term (7-30d)** | [Product launch/Conference] | MM/DD | [HIGH/MED/LOW] | [get_ticker_data / WebSearch] |
| **Long-term (30-90d)** | [Guidance/Sector trend/Regulatory] | MM/DD | [HIGH/MED/LOW] | [WebSearch / get_ticker_data] |

**Catalyst Density:** [HIGH: 2+ catalysts in 30d / MODERATE: 1 catalyst / LOW: none upcoming]
**Catalyst Sequencing:** [STACKED: multiple catalysts reinforce thesis / CONFLICTING: mixed signals across timeframes / SINGLE: one dominant catalyst]

**Tools:** `detect_catalyst_strength()`, `get_nasdaq_earnings_calendar()`, `get_ticker_data()`

---

### 8. MACRO & SECTOR CONTEXT (Phase 7 — 5.3%)

**Market Environment:** `[get_cnn_fear_greed_index]`
- **Fear & Greed Index:** XX ([Extreme Fear <20 / Fear 20-45 / Neutral 45-55 / Greed 55-80 / Extreme Greed >80])
- **Impact on setup:** [How sentiment affects trade probability]

**Sector Analysis:** `[analyze_competitors]`
- **Sector/Industry:** [Name]
- **Sector Rank:** X/XX (Top XX%)
- **RS vs SPY:** XX [Leader >70 / Neutral 50-70 / Laggard <50]

**Peer Comparison:**

| Ticker | Price | RS | P/E | P/S | EV/EBITDA | F-Score | Trend | Note |
|--------|-------|----|-----|-----|-----------|---------|-------|------|
| [TARGET] | $XXX | XX | XX.X | XX.X | XX.X | X/9 | [BULL/BEAR/RANGE] | PRIMARY |
| [Peer 1] | $XXX | XX | XX.X | XX.X | XX.X | X/9 | [Trend] | [Note] |
| [Peer 2] | $XXX | XX | XX.X | XX.X | XX.X | X/9 | [Trend] | [Note] |

**Valuation vs Peers:**
- **P/E vs Peer Avg:** XX.X vs XX.X → [PREMIUM / DISCOUNT / IN-LINE] (+/-XX%)
- **P/S vs Peer Avg:** XX.X vs XX.X → [PREMIUM / DISCOUNT / IN-LINE]
- **EV/EBITDA vs Peer Avg:** XX.X vs XX.X → [PREMIUM / DISCOUNT / IN-LINE]
- **Premium Justified?** [YES: growth/margins > peers / NO: growth < peers / MIXED]

**Data:** Use `analyze_competitors()` to get peer tickers, then `get_ticker_data()` on each peer for P/E, P/S, EV/EBITDA. If data unavailable for a peer, mark "N/A".

**Macro Tailwinds/Headwinds:**
- ✓ Tailwinds: [List]
- ✗ Headwinds: [List]

#### Macro Risk Assessment

| Risk Factor | Current State | Impact on Trade | Source |
|-------------|--------------|-----------------|--------|
| **Interest Rates** | [Rising/Falling/Stable] | [Headwind/Tailwind/Neutral] | [get_cnn_fear_greed_index / WebSearch] |
| **USD Strength** | [Strong/Weak/Stable] | [Headwind for multinationals / Tailwind for domestic] | [WebSearch] |
| **Sector Rotation** | [Risk-On/Risk-Off/Mixed] | [Favors/Opposes sector] | [get_cnn_fear_greed_index] |
| **Volatility (VIX)** | [XX.X — High/Normal/Low] | [Elevated risk / Normal / Complacency] | [get_cnn_fear_greed_index] |

**Macro Risk Level:** [LOW / MODERATE / ELEVATED / HIGH]
- **LOW:** Fear & Greed 40-60, VIX <20, rates stable → Full position sizing
- **MODERATE:** Fear & Greed 20-40 or 60-80, VIX 20-30 → Normal sizing
- **ELEVATED:** Fear & Greed <20 or >80, VIX 30-40 → Reduce size 25-50%
- **HIGH:** VIX >40, macro crisis → Cash preservation, avoid new entries

#### ESG Considerations (If Material) [WebSearch]

**ESG Relevance:** [HIGH (energy, mining, defense, tobacco) / MEDIUM (tech, finance, pharma) / LOW (most other sectors)]

[If HIGH relevance]:
- **Environmental:** [Carbon footprint, emissions targets, regulatory exposure]
- **Social:** [Labor practices, diversity, supply chain ethics]
- **Governance:** [Board independence, executive compensation, shareholder rights]
- **Institutional Impact:** [ESG-focused funds may increase/decrease allocation — check `get_institutional_holders()` for ESG fund presence]

[If MEDIUM relevance]:
- **Key ESG Factor:** [Single most material ESG issue for this sector — e.g., data privacy for tech, lending practices for banks]
- **Institutional Impact:** [Note if ESG-focused funds are among top holders]

[If LOW relevance]:
*ESG factors not material for this sector/stock. Standard analysis applies.*

**Data:** Search `"[TICKER] ESG rating sustainability controversy"` via WebSearch if sector is HIGH/MEDIUM relevance. Check `get_institutional_holders()` for ESG-focused fund presence (e.g., Calvert, Parnassus, iShares ESG). If no ESG data available, note: "ESG data unavailable — no material ESG flags identified."

**Bottom Line:** [TICKER] is [leading/lagging] sector with [strong/weak] RS. [Fear/Greed] environment [supports/opposes] setup.

**Tools:** `get_cnn_fear_greed_index()`, `analyze_competitors()`, `calculate_relative_strength_tool()`

---

### 9. FEATURE IMPORTANCE ANALYSIS (Phase 6 — 5.4% of 17.9%)

**Which indicators matter for THIS stock?** Ranked by predictive power for 10-day returns:

| Rank | Feature | Correlation | Current Value | Significant? | Weight |
|------|---------|-------------|---------------|-------------|--------|
| 1 | [Name] | X.XX | XX.X | ✓/✗ | XX% |
| 2 | [Name] | X.XX | XX.X | ✓/✗ | XX% |
| 3 | [Name] | X.XX | XX.X | ✓/✗ | XX% |

**Summary:** X/9 significant features. Predictability: [HIGH/MODERATE/LOW]
**Actionable Insight:** For [TICKER], the key driver is [Feature 1] at [value], predicting [outcome].

**Tools:** `calculate_feature_importance_analysis()`

---

### 10. ML-ENHANCED ANALYSIS (Phase 6A — 9.8% of 17.9%)

**Triple-Barrier Analysis:** `[analyze_ml_enhanced]`

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Historical Setups | XX | Sample size |
| Success Rate | XX.X% | Probability of hitting profit before stop |
| Avg Profit (Winners) | +X.X% | Average gain |
| Avg Loss (Losers) | -X.X% | Average loss |
| Risk/Reward | X.X:1 | Asymmetric payoff |
| Recommendation | [FAVORABLE/UNFAVORABLE] | [Context] |

**Trend-Scanning:**

| Metric | Value |
|--------|-------|
| Current Trend | [UPTREND/DOWNTREND/RANGE] |
| T-Statistic | X.XX |
| P-Value | X.XXX |
| Significance | [YES/NO] |

**Meta-Labeling Decision:**

| Factor | Value |
|--------|-------|
| Should Trade? | [YES/NO] |
| ML Confidence | XX% |
| Predicted Return | +X.X% |
| Quality Assessment | [HIGH/MEDIUM/LOW] |

**Kelly Criterion Position Sizing:**

| Metric | Value |
|--------|-------|
| Full Kelly | XX.X% |
| Fractional Kelly (50%) | X.X% |
| Suggested Position | X.X% of portfolio |
| Kelly Stop Price | $XXX.XX |

**ML Validation:**

| Metric | Value | Status |
|--------|-------|--------|
| Deflated Sharpe | X.XX | [>1.0 = PASS] |
| Prob NOT Overfit | XX% | [<0.30 = PASS] |

**Dalio Economic Machine:** `[analyze_ml_enhanced → dalio_metrics]`

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Dalio Ratio | X.XXXX | [BULLISH >1.0 / BEARISH <1.0] |
| Dollar Flow | $XX.XXM | [ACCUMULATION / DISTRIBUTION] |
| Sustainability | XX/100, Grade [A-F] | [SUSTAINABLE ≥60 / MODERATING / UNSUSTAINABLE <40] |

**Gate 2 Enhanced (6 Checks):**

| # | Check | Value | Status |
|---|-------|-------|--------|
| 1 | CVD Aligned | [RISING/FALLING] | [✅/❌] |
| 2 | Not Exhausted | XX/100 | [✅ <50 / ❌ ≥50] |
| 3 | Fresh Direction | [LONG/SHORT] | [✅/❌] |
| 4 | Dalio Ratio | X.XXXX | [✅/❌] |
| 5 | Dollar Flow | $XX.XXM | [✅/❌] |
| 6 | Sustainability | XX/100 | [✅ ≥50 / ❌ <50] |

**Checks Passing:** X/6 (Need 5/6 for Gate 2 PASS)

**Brooks Analysis:** `[analyze_ml_enhanced → al_brooks]`
- Always-In: [LONG/SHORT] | Pattern: [Name] | Base Prob: XX% | Trap Risk: [HIGH/MEDIUM/LOW]

**ML Summary:** [2-3 sentences combining triple-barrier, trend-scanning, meta-label, and Dalio findings]

**Tools:** `analyze_ml_enhanced()`, `calculate_feature_importance_analysis()`

---

### 10B. STATISTICAL VALIDATION (Phase 6 — Statistical Edge)

**Pattern Win Rate Backtesting:** `[validate_brooks_pattern_win_rate]`

| Pattern | Backtested Win Rate | Expected Win Rate | Sample Size | 95% Confidence |
|---------|--------------------|--------------------|-------------|----------------|
| [Pattern Name] | XX.X% | XX% | XX trades | [XX%, XX%] |

**Edge Quantification:** `[quantify_pattern_edge]`

| Metric | Value |
|--------|-------|
| Expected Return/Trade | +X.XX% |
| Edge Quality | [STRONG / MODERATE / WEAK / NO_EDGE] |
| Quarter-Kelly Size | X.X% of portfolio |
| Recommendation | [TRADE / REDUCE_SIZE / SKIP] |

**Probability Narrative:** `[quantify_pattern_edge.recommendation]`
> [Edge analysis narrative — e.g., "Pattern shows XX% win rate over XX samples with X.X:1 reward/risk. Quarter-Kelly sizing limits drawdown while capturing edge."]

**Tools:** `validate_brooks_pattern_win_rate()`, `quantify_pattern_edge()`

---

### 11. HISTORICAL CONFIRMATION (Phase 9 — 0% Weight)

**⚠️ Confirmation only, NOT weighted in final score.**
**Use ACTUAL targets from Section 12 Trade Plan.**

```python
find_similar_historical_setups(
    ticker="XXXX",
    target_return_pct=X.X,       # YOUR PT1 or PT2
    holding_period_days=XX,      # YOUR holding period
    direction="LONG/SHORT"       # YOUR direction
)
```

**Trading Plan Target:**
- Direction: [LONG/SHORT] | Target: X.X% | Holding: XX days

**Results:**

| Metric | Value |
|--------|-------|
| Similar Setups Found | XX |
| Hit Target Rate | XX% |
| Avg Achievement | XX.X% |
| Success Rate (10-day) | XX.X% |
| 95% CI | [XX%, XX%] |
| P-Value | X.XXX |
| Statistically Significant | [YES/NO] |

**Per-Setup Validation:**

| Date | Similarity | Actual | Target | Achievement | Status |
|------|-----------|--------|--------|-------------|--------|
| YYYY-MM-DD | XX.X% | +X.XX% | X.X% | +XXX% | ✅ HIT / 🟡 PARTIAL / ❌ WRONG |

**Status:** ✅ HIT (≥100%) | 🟡 PARTIAL (60-99%) | 🟠 WEAK (0-59%) | ❌ WRONG (<0%)

**Confirmation:** [STRONG ≥60% hit / MODERATE 40-59% / WEAK <40% / INSUFFICIENT <5 setups]

**Tools:** `find_similar_historical_setups()`

---

### 12. TRADE PLAN (Phase 10)

**This is the SINGLE source of truth for position sizing, entries, exits, and risk/reward.**

#### A. Direction Decision

**RECOMMENDATION: [LONG / SHORT / WAIT]**

**5-Gate Validation:**

| Gate | Status | Detail |
|------|--------|--------|
| Gate 1: Catalyst | [✅/❌] | [Score/detail] |
| Gate 2: Freshness + Dalio | [✅/❌] | [X/6 checks] |
| Gate 3: Brooks | [✅/❌] | [Always-In + probability] |
| Gate 4: Quality | [✅/❌] | [Grade + F-Score] |
| Gate 5: Options | [✅/❌] | [Spread % + vehicle] |

**Result:** X/5 gates PASS → [STRONG_BUY/BUY/SELL/STRONG_SELL/WATCH/NO_TRADE]

**Rationale Checklist:**
- ✓/✗ Technical breakout/breakdown confirmed
- ✓/✗ Fundamental quality (F-Score ≥5, Z-Score >1.81)
- ✓/✗ Market leader (RS >70 for LONG, <30 for SHORT)
- ✓/✗ Volume confirmation (>avg)
- ✓/✗ Positive catalysts (<30 days)
- ✓/✗ Favorable risk/reward (≥2:1)
- ! Concerns: [Red flags]

#### B. Entry & Exit Strategy

**Entry Status:** `[generate_trading_signal.entry_status]`

| Field | Value |
|-------|-------|
| Entry Status | **[ACTIONABLE / WAIT / CHASE_WARNING]** |
| Entry Price | $XXX.XX |
| Current Price | $XXX.XX |
| Entry Zone | $XXX.XX - $XXX.XX |
| Entry Strategy | [AT_SUPPORT / PULLBACK_TO_SUPPORT / NO_CLEAR_ENTRY / etc.] |
| Position Size Multiplier | X.Xx |

[If ACTIONABLE]:
**ACTIONABLE** — Price is at or near the recommended entry level. Execute now per the entry ladder below.

[If WAIT]:
**WAIT** — Price is NOT at the recommended entry. Set a limit order at $XXX.XX (entry_price) within the entry zone $XXX.XX - $XXX.XX. Do NOT chase at current price.

[If CHASE_WARNING]:
**CHASE WARNING** — Entry strategy is [NO_CLEAR_ENTRY/WAIT_FOR_PULLBACK] AND [RSI > 70 / exhaustion > 70]. Do NOT enter at current price $XXX.XX. Wait for pullback to $XXX.XX or clearer setup. Position size reduced to 0.5x.

**Risk Per Trade:** $X,XXX (1% of account)

**Entry Ladder:**

| Entry | % Position | Price | Shares | Capital | Type |
|-------|------------|-------|--------|---------|------|
| Entry 1 | 33% | $XXX.XX | XXX | $X,XXX | Aggressive (now) |
| Entry 2 ⭐ | 50% | $XXX.XX | XXX | $X,XXX | Pullback (BEST) |
| Entry 3 | 17% | $XXX.XX | XXX | $X,XXX | Breakout confirm |
| **TOTAL** | **100%** | - | **XXX** | **$XX,XXX** | |

**Exit Strategy:**

| Level | % to Sell | Price | Gain | Profit | Description |
|-------|-----------|-------|------|--------|-------------|
| PT1 | 33% | $XXX.XX | +X% | $X,XXX | First target |
| PT2 | 33% | $XXX.XX | +XX% | $X,XXX | Second target |
| PT3 | 34% | $XXX.XX | +XX% | $X,XXX | Final target |
| **STOP** | **100%** | **$XXX.XX** | **-X%** | **-$XXX** | **Max loss** |

**Risk/Reward:** X.X:1 (Risk $XXX to make $X,XXX avg)

**Exit Triggers:**
1. Price breaks stop level → exit immediately
2. Always-In direction flips → exit
3. Time stop: X days with no progress → re-evaluate
4. Negative catalyst → exit regardless of price

#### C. Weighted Score (Phases 1-8)

| Phase | Raw | Weight | Points |
|-------|-----|--------|--------|
| Fundamentals (1) | XX/100 | 17.9% | XX |
| Catalysts (2) | XX/100 | 13.4% | XX |
| **McMillan Options (3)** | **XX/100** | **17.9%** | **XX** |
| Insider Trading (4) | XX/100 | 4.5% | XX |
| Institutional (5) | XX/100 | 4.5% | XX |
| Technical (6) | XX/100 | 17.9% | XX |
| Market Context (7) | XX/100 | 5.3% | XX |
| Al Brooks (8) | XX/100 | 17.9% | XX |
| **TOTAL** | - | **100%** | **XX/100** |

**Brooks Probability Breakdown:**

| Component | Value |
|-----------|-------|
| Base Pattern | XX% |
| + Fundamentals | +XX% |
| + Catalyst | +XX% |
| + McMillan | +XX% |
| + Insiders/Institutions | +XX% |
| + Technicals | +XX% |
| + Market Context | +XX% |
| + Dalio | +XX% |
| **Final** | **XX%** |

**Historical Confirmation (0% Weight):**

| Metric | Value | Status |
|--------|-------|--------|
| Success Rate | XX.X% | [XX setups] |
| P-Value | X.XXX | [Significant?] |
| Confirmation | [STRONG/MODERATE/WEAK/INSUFFICIENT] |

**FINAL DECISION:** [STRONG BUY/BUY/SELL/STRONG SELL/WAIT/SKIP]
**Conviction:** [HIGH / MODERATE / LOW]
**Reasoning:** Score XX/100 + Brooks XX% + Historical XX%

**Conviction Mapping:**
- **HIGH:** Score ≥80 + 5/5 gates + Brooks ≥60% → Full position size
- **MODERATE:** Score 70-79 + 4/5 gates + Brooks ≥55% → 50-75% position size
- **LOW:** Score <70 or <4 gates → Do not trade / Wait

(See [TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md) for Decision Matrix thresholds)

#### D. Scenario Analysis (Probability-Weighted Valuation)

**Probability Derivation (from Brooks + Context):**
- Brooks Final Probability: XX% → Bull prob baseline
- Bear prob = 100% - Brooks prob, adjusted for catalyst strength
- Base prob = remainder after Bull + Bear allocation

**BULL CASE (XX% probability):**
- **Target:** $XXX.XX (+XX%) — Analyst high target [get_ticker_data] / R2-R3 resistance [find_support_resistance]
- **Trigger:** [Catalyst beats expectations + momentum continuation]
- **Timeline:** X-XX days
- **Weighted Return:** +XX% × XX% = **+X.X%**

**BASE CASE (XX% probability):**
- **Target:** $XXX.XX (+XX%) — Analyst mean target [get_ticker_data] / PT1 [generate_trading_signal]
- **Trigger:** [Normal execution, catalyst as expected]
- **Timeline:** X-XX days
- **Weighted Return:** +XX% × XX% = **+X.X%**

**BEAR CASE (XX% probability):**
- **Target:** $XXX.XX (-XX%) — Stop loss / Analyst low target [get_ticker_data] / S2-S3 support
- **Trigger:** [Catalyst fails, direction reversal, macro shock]
- **Timeline:** X-X days
- **Weighted Return:** -XX% × XX% = **-X.X%**

**Expected Value Summary:**

| Scenario | Probability | Return | Weighted |
|----------|------------|--------|----------|
| Bull | XX% | +XX% | +X.X% |
| Base | XX% | +XX% | +X.X% |
| Bear | XX% | -XX% | -X.X% |
| **TOTAL EXPECTED VALUE** | **100%** | - | **+X.X%** |

**Win Probability:** XX% (Bull + Base) | **Loss Probability:** XX% (Bear)
**Kelly Size:** X.X% of portfolio

**Decision Rule:** EV > 0% AND Win Probability > 50% → PROCEED
**If EV < 0% or Win Prob < 50%:** DO NOT TRADE — unfavorable risk/reward

---

### 13. TECHNICAL INDICATORS (Phase 6B — 8.1% of 17.9%)

**Relative Strength:** RS XX vs SPY [Leader/Neutral/Laggard] `[analyze_competitors]`

**Volumetric Liquidity:** `[analyze_volume_tool]`

| Metric | Value | Interpretation |
|--------|-------|----------------|
| CVD Trend | [RISING/FALLING/FLAT] | [Buying/Selling pressure] |
| CVD Divergence | [BULLISH/BEARISH/NONE] | [Exhaustion signal] |
| Multi-VWAP Alignment | [STRONG_BULLISH to BEARISH] | Price vs all VWAPs |
| VWAP σ Distance | X.XX | [SUSTAINABLE <1σ / EXTENDED / UNSUSTAINABLE >2σ] |
| Exhaustion Score | XX/100 | [Action: PROCEED/FLAG/REDUCE_SIZE/EXCLUDE] |

**Exhaustion Score Components:**

| Factor | Points | Max | Status |
|--------|--------|-----|--------|
| CVD Divergence | XX | 20 | [Status] |
| RSI Divergence | XX | 20 | [Status] |
| Trend Days | XX | 25 | X days |
| VWAP Extension | XX | 15 | X.XX σ |
| Volume Decline | XX | 20 | X days |
| **TOTAL** | **XX** | **100** | **[Level]** |

**Volatility:** ATR $X.XX (X.X%) | ATR-based stop: 2.5x ATR = $X.XX

**Tools:** `analyze_ml_enhanced()`, `analyze_volume_tool()`, `analyze_volatility_tool()`, `calculate_relative_strength_tool()`

---

## QUALITY CHECKLIST

**Framework:**
- [ ] All 10 phases executed in order
- [ ] Phase 3 (McMillan) ran with correct direction
- [ ] Phase 8 (Brooks) ran AFTER Phases 1-7
- [ ] Phase 9 (Historical) ran AFTER Phase 8 with actual trade plan targets
- [ ] Historical = "CONFIRMATION (0% weight)"
- [ ] Weighted score uses Phases 1-8 only

**Content:**
- [ ] Executive Summary with quick decision snapshot
- [ ] Direction Validation with vote table
- [ ] McMillan Options with IV, P/C, strategy, score
- [ ] Peer Comparison table
- [ ] ML Analysis with Triple-Barrier + Dalio
- [ ] Scenario Analysis with expected value
- [ ] Brooks probability = context-informed (base + adjustments)
- [ ] Position sizing calculated (1% risk rule)
- [ ] Risk/reward ≥ 2:1

**Multi-Timeframe:**
- [ ] Multi-timeframe analysis completed (analyze_multitimeframe called)
- [ ] Brooks Lesson included with educational insight
- [ ] Confluence score reported

**Data Integrity:**
- [ ] Every number tagged with source tool
- [ ] No fabricated data
- [ ] Historical NOT in weighted score
- [ ] No circular logic

---

## MANDATORY: STORE PREDICTION

**After generating the report, store prediction for tracking:**

`generate_trading_signal()` auto-stores predictions by default. If manual storage needed:

```python
store_trading_prediction(
    ticker="TICKER",
    direction="LONG/SHORT",
    report_type="comprehensive",
    trading_signal=signal
)
```

This tracks accuracy, generates efficiency reports after 5+ predictions, and validates the 5-gate system.

---

*Last Updated: February 2026 | Version 4.2 — Appendix removed, references TRADING_REFERENCE_GUIDE.md*

---

## METHODOLOGY REFERENCE

For educational details on all methodologies used in this report, see **[TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md)**:

- **Al Brooks Price Action** — Always-In direction, pattern reference (High 2, Low 1, Wedge, Breakout, Channel), bar reading, trap recognition, probability framework with context adjustments
- **McMillan Options Strategy** — IV environment strategy matrix, P/C ratio contrarian signals, max pain, Greeks reference, standard deviation & strike selection
- **Institutional Options Rules** — 8 rules (IV drives strategy, 45 DTE, 50% profit target, 21 DTE exit, etc.)
- **Ray Dalio Economic Machine** — Dalio Ratio, Dollar Flow, Sustainability, Gate 2 Enhanced (6 checks), Brooks probability adjustments
- **Position Management Framework** — 5-priority management system (50% profit, 21 DTE, direction change, tested position, earnings)
- **Scoring Tiers & Decision Matrix** — Conviction tiers, weighted score thresholds, trading plan generation rules
- **Statistical Validation** — Pattern win rate backtesting (`validate_brooks_pattern_win_rate`), edge quantification (`quantify_pattern_edge`), Kelly position sizing
