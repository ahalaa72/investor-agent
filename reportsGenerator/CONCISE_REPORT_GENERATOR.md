# Concise Trading Report Generator

Fast analysis with bullet points for data, detailed Al Brooks, McMillan Options, and Trading Plan.

**Structure:** ~210 lines | **Time:** 35 minutes | **Framework:** 10-Phase Institutional

**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy) + Ray Dalio (Economic Machine)

---

## 🚨 QUESTRADE TOKEN WARNING 🚨

**NEVER write Python scripts to access data** - This consumes the single-use refresh token.

**ALWAYS use MCP tools ONLY:**

- `get_questrade_quotes()` for real-time prices
- `get_ticker_data()` for company data
- All other investor-agent MCP tools

If HTTP 400 errors occur, token is consumed. See [CLAUDE.md](CLAUDE.md) for recovery.

---

## 📁 REPORT OUTPUT: OBSIDIAN VAULT

**MANDATORY:** After generating the report, save it as a markdown file in the Obsidian vault.

```text
Path: /Users/AhmedE/Ahmed/Trading Reports/
Filename: TICKER_CONCISE_YYYY-MM-DD.md
```

**Example:** `/Users/AhmedE/Ahmed/Trading Reports/AAPL_CONCISE_2026-02-08.md`

**Rules:**

- Use the `Write` tool to save the complete report to the vault
- Date format: YYYY-MM-DD (analysis date)
- Always save AFTER generating the full report (not incrementally)

---

## CRITICAL RULES

### Data Integrity
- **NEVER fabricate numbers** - If tool fails, report "DATA UNAVAILABLE"
- **Every number MUST have [tool_name] source tag**
- **Async functions need asyncio.run():** get_cnn_fear_greed_index, find_similar_historical_setups, analyze_ml_enhanced
- **Check market hours before intraday calls** (weekends/after-hours = skip)

### 🚨 Catalyst Verification (Dec 2025) - REAL MONEY PROTECTION
- **ALWAYS run `detect_catalyst_strength()`** in Phase 2 (MANDATORY)
- **Check verification_rate ≥ 50%** before recommending trade
- **If trade_allowed = False** → DO NOT RECOMMEND TRADE
- **If requires_manual_verification = True** → Warn user to verify manually
- **Old news (>3 days) = STALE** - Already priced in, DO NOT TRADE on it
- **Report verified_catalysts and unverified_catalysts** in every analysis

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

### Phase 2: Catalysts (15.2%) - [BULLISH/BEARISH/NEUTRAL] 🚨 WITH VERIFICATION
- **Verification Rate:** XX% [detect_catalyst_strength] [≥50% OK / <50% BLOCKED]
- **Trade Allowed:** [TRUE/FALSE] [detect_catalyst_strength]
- Last earnings: [Date] ([Beat/Miss] +/-XX%) [get_earnings_history]
- Next earnings: [Date] [get_nasdaq_earnings_calendar]
- Recent news: "[Headline]" (X days ago, [VERIFIED/UNVERIFIED]) [detect_catalyst_strength]
- **Verified Catalysts:** X HIGH, X MEDIUM confidence
- **Unverified Catalysts:** X (⚠️ VERIFY BEFORE TRADING)
- **10b5-1 Check:** [N/A / Pre-planned / Discretionary selling]
- **Score: XX/100** → XX.X pts

### Phase 3: McMillan Options Strategy (13.4%) - [BULLISH/BEARISH/NEUTRAL] [✓/✗]

⚠️ **NOTE:** `analyze_options_mcmillan()` analyzes **ONE SPECIFIC EXPIRATION** (30-45 DTE optimal). If liquidity appears poor but `detect_unusual_options_activity()` shows volume, they're analyzing **DIFFERENT EXPIRATIONS** - both can be correct!

- IV Rank: XX% / IV Percentile: XX% [analyze_options_mcmillan]
  - Divergence: [ALIGNED / DIVERGENT: recent spike vs historical norm]
- P/C Ratio: X.XX [analyze_options_mcmillan]
  - Raw: [Bullish <0.7 / Neutral 0.7-1.0 / Bearish >1.0]
  - **Contrarian:** [BULLISH if >1.2 / BEARISH if <0.5 / NO SIGNAL 0.5-1.2]
- Max Pain: $XXX.XX ([Above/Below/At] price) [analyze_options_mcmillan]
  - Reliability: [HIGH (near expiry + high OI) / MEDIUM / LOW (early cycle)]
- Smart Money: [BULLISH/BEARISH/MIXED/NO_SIGNAL] [analyze_options_mcmillan]
- **Strategy:** [Bull Put Spread / Long Call / Iron Condor / etc.] [analyze_options_mcmillan]
- **Liquidity (XX DTE - [DATE]):** [Grade + specific expiration analyzed]
  - If unusual activity detected on DIFFERENT expiration → **NOTE THE DIFFERENCE**

**Greeks (ATM):** [analyze_options_mcmillan.greeks_assessment]
| Greek | Call | Put | Signal |
|-------|------|-----|--------|
| Delta | +X.XX | -X.XX | XX% ITM prob |
| Gamma | X.XXXX | X.XXXX | [HIGH/LOW] |
| Theta | -$X.XX | -$X.XX | [decay rate] |
| Vega | $X.XX | $X.XX | [IV sensitivity] |

- **Greeks Source:** [questrade / yfinance_estimated]
- **Position Risk:** [Theta-positive/negative], [Vega-long/short], [Gamma-stable/explosive]

**📊 EXPECTED MOVES & STANDARD DEVIATION:** ⭐ NEW
| Timeframe | 1 SD (68%) | 2 SD (95%) | Strike Selection |
|-----------|------------|------------|------------------|
| Weekly (7d) | ±$X.XX | ±$X.XX | 16Δ: $XXX (84% OTM) |
| Monthly (30d) | ±$X.XX | ±$X.XX | 16Δ: $XXX (84% OTM) |
| 45 DTE | ±$X.XX | ±$X.XX | 16Δ: $XXX (84% OTM) ⭐ |

**Why 16-Delta (1 SD) is Optimal:** 84% win rate + reasonable premium = best risk-adjusted returns (TastyTrade)
- **2 SD (5Δ):** 95% win rate BUT low premium (negative expected value)
- **1 SD (16Δ):** 84% win rate + good premium (**POSITIVE expected value**) ✅
- **ATM (50Δ):** 50% win rate (coin flip, avoid)

- **Score: XX/100** → XX.X pts

**McMillan Options Score: XX/100** (See [TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md) for IV strategy matrix, P/C interpretation, Max Pain, Greeks, and strategy selection methodology)

- **Score: XX/100** → XX.X pts

---

### Phase 4: Insiders (4.5%) - [BUYING/SELLING/MIXED]
- Insider activity: [Description] [get_insider_trades]
- **Score: XX/100** → XX.X pts

### Phase 5: Institutions (4.5%) - [ACCUMULATING/DISTRIBUTING/MIXED]
- Top holders: [Vanguard X%, BlackRock X%] [get_institutional_holders]
- 13F changes: [+/-X% net] [get_institutional_holders]
- **Score: XX/100** → XX.X pts

### Phase 6: Technical (17.9%) - [BULLISH/BEARISH/NEUTRAL] [✓/✗]
- RSI: XX.X ([Overbought/Neutral/Oversold]) [analyze_ml_enhanced]
- MACD: [Bullish/Bearish] (X.XX) [analyze_ml_enhanced]
- Price vs EMA20: +/-XX.X%, vs VWAP: +/-XX.X% [analyze_ml_enhanced]
- RS vs SPY: XX ([LEADER/LAGGARD]) [calculate_relative_strength_tool]
- Trend: [UPTREND/DOWNTREND], XX.X% confidence [analyze_ml_enhanced]
- OBV: [Accumulation/Distribution] [analyze_volume_tool]
- **CVD:** [RISING/FALLING/FLAT], divergence: [BULLISH/BEARISH/NONE] [analyze_volume_tool.cvd_analysis]
- **Exhaustion:** XX/100 ([NO/LOW/MODERATE/HIGH]_EXHAUSTION) [analyze_ml_enhanced.exhaustion]
- **Multi-VWAP:** [STRONG_BULLISH/BULLISH/MIXED/BEARISH] alignment [analyze_volume_tool.multi_vwap]
- **Al Brooks:** [Pattern], [XX]% adjusted probability [analyze_ml_enhanced.al_brooks]

**Dalio Economic Machine:** [analyze_volume_tool.dalio_metrics] ⭐ NEW
- **Dalio Ratio:** X.XXXX ([BULLISH >1.0 / NEUTRAL ~1.0 / BEARISH <1.0])
- **Dollar Flow:** $XX.XXM ([ACCUMULATION / DISTRIBUTION])
- **Sustainability:** XX/100, Grade [A-F]
- **Dalio Gate 2:** [X/6 checks passing] - [PASS (5+) / WARN (4) / FAIL (≤3)]

**Order Blocks (Institutional Footprints):** [analyze_ml_enhanced.order_blocks]
- Signal: [BULLISH_OB_TEST / BEARISH_OB_TEST / NONE]
- Closest Bullish OB: $XX.XX (X.X% below) - [X days old, +X.X% impulse]
- Closest Bearish OB: $XX.XX (X.X% above) - [X days old, -X.X% impulse]
- Interpretation: [Near support zone / Near resistance zone / No blocks nearby]

**Supply/Demand Zones:** [analyze_ml_enhanced.supply_demand]
- Closest Demand: $XX.XX (X.X% below)
- Closest Supply: $XX.XX (X.X% above)

**Volumetric Liquidity:** [analyze_volume_tool] ⭐ NEW
- CVD Trend: [RISING/FALLING/FLAT] - [buying/selling pressure interpretation]
- CVD Divergence: [BULLISH/BEARISH/NONE] - [exhaustion signal if present]
- VWAP σ Distance: X.XX ([SUSTAINABLE/EXTENDED/UNSUSTAINABLE])

- **Score: XX/100** → XX.X pts

### Phase 7: Market Context (5.3%) - [BULLISH/BEARISH/NEUTRAL]
- Fear & Greed: XX.X ([Extreme Fear/Fear/Neutral/Greed/Extreme Greed]) [get_cnn_fear_greed_index]
- **Score: XX/100** → XX.X pts

---

## DIRECTION VALIDATION ⚠️ NEW

**Purpose:** Validates trading direction using independent data sources.

**📊 DIRECTION VOTES:** `[generate_trading_signal.direction_votes]`

| Tool | Vote | Reason |
|------|------|--------|
| Catalyst | [BULLISH/BEARISH/NEUTRAL] | Primary catalyst |
| CVD | [BULLISH/BEARISH] | Volume delta trend |
| Exhaustion | [LONG/SHORT] | Fresh direction |
| Brooks | [LONG/SHORT/NEUTRAL] | Always-In direction |
| Dalio Ratio | [BULLISH/BEARISH] | >1.0 = BULLISH |
| Dollar Flow | [BULLISH/BEARISH] | >0 = BULLISH |

**Consensus:** X LONG votes, Y SHORT votes → **[LONG/SHORT/NO_CONSENSUS]**

[If conflict]:
🚨 **DIRECTION CONFLICT DETECTED**
Scanner/Analysis suggests **[DIRECTION]** but data votes suggest **[OPPOSITE]**.
⚠️ **Action:** Reduce position size by 50% or wait for alignment.

---

## 🎯 OPTIMAL OPTIONS STRATEGY (Risk-Managed) ⭐ NEW

**Market Conditions:** `[analyze_options_mcmillan]`
- IV Rank: XX% → [LOW = BUY premium / HIGH = SELL premium]
- Direction: [LONG/SHORT] from Brooks + Dalio

**📊 STRATEGY SELECTION:**

| IV Environment | BULLISH | BEARISH |
|----------------|---------|---------|
| LOW (<30%) | Bull Call Spread | Bear Put Spread |
| HIGH (>50%) | Bull Put Credit Spread | Bear Call Credit Spread |

**🎯 RECOMMENDED TRADE:**

| Leg | Action | Strike | Expiry | Premium |
|-----|--------|--------|--------|---------|
| 1 | [BUY/SELL] | $XXX [C/P] | [Date] | $X.XX |
| 2 | [BUY/SELL] | $XXX [C/P] | [Date] | $X.XX |

| Metric | Value |
|--------|-------|
| Max Risk | $XXX (defined) |
| Max Profit | $XXX |
| Break-Even | $XXX.XX |
| R/R Ratio | 1:X.X |
| Prob of Profit | XX% |

**Position Sizing (1% Rule):** Max Contracts = (Account × 1%) / Max Risk

**Exit Rules:**
- Profit: 50% of max profit
- Stop: 100% of max loss
- Time: 21 DTE
- Direction flip: Exit immediately

---

## 📊 POSITION MANAGEMENT (Phase 4 - NEW) ⭐

**⚠️ For EXISTING options positions only** - Skip if opening NEW position.

**Daily Position Check:** `evaluate_options_position_management()`

**📊 MANAGEMENT RULES (Priority Order):**

| Rule | Trigger | Action | Urgency |
|------|---------|--------|---------|
| **1. Profit Target** | P&L ≥ 50% max profit | CLOSE | IMMEDIATE |
| **2. 21 DTE** | DTE ≤ 21 (profitable) | CLOSE | WITHIN_3_DAYS |
| **2. 21 DTE** | DTE ≤ 21 (losing) | ROLL | WITHIN_3_DAYS |
| **3. Direction Flip** | Brooks Always-In flips | CLOSE | IMMEDIATE |
| **4. Tested Position** | Price breaches strike + DTE ≤ 7 | CLOSE | IMMEDIATE |
| **5. Earnings** | Earnings < 7 days | CLOSE | IMMEDIATE |

**Example Output:**
```
Action: CLOSE
Reason: ✅ 50% PROFIT TARGET HIT (50.0% of max profit)
Urgency: IMMEDIATE
P&L: $315 (50.0% of $630 max)
Days in Trade: 10
DTE: 30
Recommendation: Close now - TastyTrade shows 88% win rate at 50%
```

**Portfolio Greeks:** `get_portfolio_greeks_dashboard()`
```
Total Delta: +142.3 (BULLISH bias)
Total Theta: +$12.45/day (collecting premium)
Total Vega: -156.8 (want IV down)
Total Gamma: -2.34 (short gamma risk)

Risk Assessment:
  ✅ Positive theta - time decay in your favor
  ⚠️ Short gamma - hedge near strikes
  ⚠️ Short vega - vulnerable to IV expansion
```

**Reference:** TastyTrade (88% win rate at 50%) + McMillan Chapter 36

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

**🆕 DALIO ADJUSTMENTS:** `[analyze_volume_tool.dalio_economic_machine]`
- Dalio Ratio: X.XXXX ([BULLISH >1.02 / BEARISH <0.98 / NEUTRAL]) → +/-5%
- Dollar Flow: $XXM 20d ([ACCUMULATION / DISTRIBUTION]) → +/-3%
- Sustainability: XX ([HIGH ≥70 / LOW ≤30 / NEUTRAL]) → +/-3%
- **Total Dalio Impact:** +/-XX%

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

### H. Brooks Probability & Score

**Base Probability:** XX% ([Pattern Name])

**Context Adjustments:** (See [TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md) for full adjustment table, pattern definitions, bar reading guide, and trap recognition)

- Fundamentals: +/-XX% | Catalyst: +/-XX% | Options: +/-XX%
- Technicals: +/-XX% | Market: +/-XX% | Dalio: +/-XX%

**FINAL BROOKS PROBABILITY: XX%** (capped 30-80%)

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

### Entry Status `[generate_trading_signal.entry_status]`

| Field | Value |
|-------|-------|
| Entry Status | **[ACTIONABLE / WAIT / CHASE_WARNING]** |
| Entry Price | $XX.XX |
| Current Price | $XX.XX |
| Entry Zone | $XX.XX - $XX.XX |
| Entry Strategy | [AT_SUPPORT / PULLBACK_TO_SUPPORT / NO_CLEAR_ENTRY / etc.] |

[If ACTIONABLE]:
**ACTIONABLE** — Price is at/near entry. Execute now.

[If WAIT]:
**WAIT** — Set limit order at $XX.XX (entry_price). Do NOT chase at current price.

[If CHASE_WARNING]:
**CHASE WARNING** — [RSI > 70 / exhaustion > 70] + no clear entry. Do NOT enter. Wait for pullback to $XX.XX. Size reduced to 0.5x.

### Position Management

| Action | Price | Size | Notes |
|--------|-------|------|-------|
| Current | $XX.XX | Held | +/-XX.X% profit/loss |
| Add 1 | $XX.XX | XX% | [Level description] |
| Add 2 | $XX.XX | XX% | [Level description] BEST |
| STOP | $XX.XX | Exit | -XX.X% from entry |
| PT1 | $XX.XX | Cover XX% | +XX.X% |
| PT2 | $XX.XX | Cover XX% | +XX.X% |

**R/R Ratio:** X.X:1

### Action Plan
- **NOW:** [If ACTIONABLE: action] [If WAIT: set limit at entry_price] [If CHASE_WARNING: do NOT enter]
- **ADD:** [When to add]
- **STOP:** [Exit criteria]
- **TARGET:** [Price target]

---

## VERDICT

**[RECOMMENDATION]** | **Conviction:** [HIGH / MODERATE / LOW]

| Metric | Value |
|--------|-------|
| Weighted Score | XX.X/100 |
| **Conviction** | **[HIGH / MODERATE / LOW]** |
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
analyze_options_mcmillan(ticker)  # ⭐ McMillan Options (direction-independent)
get_insider_trades(), get_institutional_holders()
analyze_ml_enhanced()  # ⭐ Full analysis: Al Brooks + Order Blocks + Supply/Demand
calculate_relative_strength_tool()
analyze_volume_tool(), get_cnn_fear_greed_index()

# PHASE 8: Al Brooks (15 min) - DETAILED
# Use analyze_ml_enhanced() for:
#   - al_brooks: always_in_direction, pattern, probability
#   - order_blocks: bullish/bearish blocks, closest blocks
#   - supply_demand: demand/supply zones
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
**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy) + Ray Dalio (Economic Machine)

---

**Last Updated:** February 2026
**Version:** 4.0 - Redundant appendix removed, references TRADING_REFERENCE_GUIDE.md

---

## MANDATORY: STORE PREDICTION IN DATABASE

**CRITICAL:** After generating every Concise Report with a trading signal, you MUST store the prediction for tracking.

### When to Store

Store prediction when:
- Trading signal is generated (STRONG_BUY, BUY, WATCH, SELL, STRONG_SELL)
- Entry price, stop loss, and targets are defined
- All 5 gates have been evaluated

### Storage Command

After completing the report and generating `generate_trading_signal()`, IMMEDIATELY call:

```python
store_trading_prediction(
    ticker="XXXX",
    direction="LONG",  # or "SHORT"
    report_type="concise",
    trading_signal=<full output from generate_trading_signal()>
)
```

### What Gets Stored

| Category | Fields |
|----------|--------|
| **Core** | ticker, direction, signal_type, entry_price, stop_loss, targets |
| **Gate 1 (Catalyst)** | catalyst_direction, catalyst_strength, catalyst_score, primary_catalyst, trade_allowed |
| **Gate 2 (Freshness)** | cvd_trend, exhaustion_score, fresh_direction |
| **Dalio Metrics** | dalio_ratio, dalio_interpretation, cumulative_dollar_flow, sustainability_score |
| **Gate 3 (Brooks)** | always_in_direction, pattern, trap_risk, brooks_probability |
| **Gate 4 (Quality)** | f_score, z_score, quality_grade, quality_score |
| **Gate 5 (Options Tradability)** | liquidity_tier, iv_environment, earnings_proximity, options_tradable |
| **Options Details** | iv_rank, iv_percentile, put_call_ratio, recommended_strategy |
| **Historical** | historical_setups_found, historical_success_rate, avg_achievement |
| **Score** | composite_score, gates_passed |

### Verification

After storing, verify the response:
```json
{
    "status": "stored",
    "prediction_id": "uuid-here",
    "ticker": "XXXX",
    "entry_price": 123.45
}
```

### Report Completion Checklist

- [ ] All 10 phases completed
- [ ] `generate_trading_signal()` called with direction
- [ ] Trading plan with entry/stop/targets defined
- [ ] `store_trading_prediction()` called with full signal data
- [ ] Prediction ID received and logged
- [ ] Report saved to `/Users/AhmedE/Ahmed/[TICKER]_CONCISE_YYYY-MM-DD.md`

**DO NOT skip prediction storage. This enables the self-learning feedback system.**

---

## METHODOLOGY REFERENCE

For educational details on all methodologies used in this report, see **[TRADING_REFERENCE_GUIDE.md](TRADING_REFERENCE_GUIDE.md)**:

- **Al Brooks Price Action** — Always-In direction, pattern reference, bar reading, trap recognition, probability framework
- **McMillan Options Strategy** — IV environment strategy matrix, P/C ratio contrarian signals, max pain, Greeks reference, strike selection
- **Institutional Options Rules** — 8 rules (IV drives strategy, 45 DTE, 50% profit target, 21 DTE exit, etc.)
- **Ray Dalio Economic Machine** — Dalio Ratio, Dollar Flow, Sustainability, Gate 2 Enhanced
- **Position Management** — 5-priority management system
- **Scoring Tiers & Decision Matrix** — Conviction tiers, trading plan generation rules
