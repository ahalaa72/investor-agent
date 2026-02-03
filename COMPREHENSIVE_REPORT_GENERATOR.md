# Comprehensive Trading Report Generator

Generate institutional-grade reports integrating all investor-agent tools with Al Brooks methodology and McMillan options strategy.

**Report Structure:** 13 sections | **Time:** 100 minutes | **Framework:** 10-Phase Institutional

**Key Methodologies:**
- **Al Brooks** - Price Action (Trading Price Action series)
- **McMillan** - Options Strategy (Options as a Strategic Investment, 5th Ed.)
- **Ray Dalio** - Economic Machine (How the Economic Machine Works) ⭐ NEW

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
- `analyze_options_mcmillan()` ⭐ McMillan Options Strategy
- `get_insider_trades()`
- `get_institutional_holders()`
- `get_earnings_history()`
- `analyze_technical()` - Basic technical indicators (use `analyze_ml_enhanced()` for full analysis)
- `find_support_resistance()`
- `analyze_volume_tool()`
- `analyze_volatility_tool()`
- `calculate_relative_strength_tool()`
- `detect_chart_patterns()`
- `analyze_trend_strength()`
- `fetch_intraday_1h()` (sync but needs market open)
- `fetch_intraday_15m()` (sync but needs market open)

### 🚨 CATALYST VERIFICATION (Dec 2025) - REAL MONEY PROTECTION

**MANDATORY for Phase 2:**
1. **ALWAYS run `detect_catalyst_strength()`** before analyzing catalysts
2. **Check verification_rate ≥ 50%** before recommending trade
3. **If trade_allowed = False** → DO NOT RECOMMEND TRADE
4. **If requires_manual_verification = True** → Warn user to verify manually
5. **Old news (>3 days) = STALE** - Already priced in, DO NOT TRADE on it
6. **Report verified_catalysts and unverified_catalysts** in Section 7

**Verification Confidence Levels:**
| Level | Meaning | Trade Action |
|-------|---------|--------------|
| **HIGH** | SEC filing, credible source (Reuters, Bloomberg, CNBC), API data | ✅ Trade allowed |
| **MEDIUM** | Recent but unverified source | ⚠️ Trade with caution |
| **LOW** | Old news (>3 days) or unknown source | ❌ Stale - DO NOT TRADE |
| **UNVERIFIED** | Could not verify | 🚫 BLOCKED until verified |

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

### 1B. DIRECTION VALIDATION ⚠️ (Data Consensus Check)

**Purpose:** Validates that the trading direction is supported by INDEPENDENT data sources. If scanner suggested one direction but data suggests another, you'll see a warning here.

**Scanner Origin:** [LONG/SHORT] candidate (if from scanner, otherwise "Direct Analysis")
**Data Consensus:** [LONG/SHORT/NO_CONSENSUS] from independent tool votes

**📊 DIRECTION VOTES TABLE:**

| Tool | Vote | Reason |
|------|------|--------|
| Catalyst | [BULLISH/BEARISH/NEUTRAL] | [Primary catalyst detected] |
| CVD | [BULLISH/BEARISH] | [Trend direction from volume delta] |
| Exhaustion | [LONG/SHORT] | [Fresh direction detected] |
| Brooks Always-In | [LONG/SHORT/NEUTRAL] | [Price action direction] |
| Dalio Ratio | [BULLISH/BEARISH] | [>1.0 = BULLISH, <1.0 = BEARISH] |
| Dollar Flow | [BULLISH/BEARISH] | [Positive = BULLISH, Negative = BEARISH] |

**Consensus Count:** X LONG votes, Y SHORT votes

[If NO conflict - votes align with direction]:
✅ **DIRECTION CONFIRMED**
All independent data sources support the [LONG/SHORT] direction. Proceed with full confidence.

[If CONFLICT detected - votes oppose direction]:
🚨 **DIRECTION CONFLICT DETECTED**

Scanner/Report suggested **[DIRECTION]** but data votes suggest **[OPPOSITE]**.

**What this means:**
- The stock passed [DIRECTION] validation gates (fundamentals, technicals, quality)
- BUT the underlying data (CVD, Dalio, Brooks) points to [OPPOSITE]
- This creates UNCERTAINTY and higher risk

**Recommended Action:**
1. ⚠️ **Reduce position size by 50%** - Mixed signals = smaller bet
2. ⏳ **Wait for alignment** - Let data confirm direction before entry
3. 🎯 **Use tighter stops** - Protect against reversal risk
4. 📊 **Re-analyze in 2-3 days** - Direction may clarify

**Why conflicts happen:**
- Scanner uses gate-based validation (pass/fail)
- Data consensus uses vote-based direction (majority rules)
- A stock can pass LONG gates while having SHORT data votes

**Tools:** `generate_trading_signal()` → `direction_votes`, `data_direction`

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

**Tools:** `analyze_ml_enhanced()` (includes Al Brooks + Order Blocks + Supply/Demand), `fetch_intraday_1h()`, `fetch_intraday_15m()`

**Note:** `analyze_ml_enhanced()` returns comprehensive analysis including:
- `al_brooks` section: always_in_direction, pattern, base_probability, adjusted_probability, bar_reading, trap_risk, entry/stop/target levels
- `order_blocks` section: bullish/bearish blocks, closest blocks, distance, interpretation
- `supply_demand` section: demand/supply zones, closest zones, distance
- `ema_vwap_confluence` section: multi-indicator alignment signals

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

**📊 ORDER BLOCKS (Institutional Footprints):**

| Block Type | Price Range | Age | Impulse | Distance | Signal |
|------------|-------------|-----|---------|----------|--------|
| 🟢 Bullish OB | $XXX.XX - $XXX.XX | X days | +X.X% | -X.X% | [TESTING/NEAR/FAR] |
| 🔴 Bearish OB | $XXX.XX - $XXX.XX | X days | -X.X% | +X.X% | [TESTING/NEAR/FAR] |

**Order Block Analysis:**
- **Signal:** [BULLISH_ORDER_BLOCK_TEST / BEARISH_ORDER_BLOCK_TEST / NONE]
- **Bullish Blocks Found:** X blocks below current price
- **Bearish Blocks Found:** X blocks above current price
- **Closest Bullish Block:** $XXX.XX (X.X% below) - Potential support zone
- **Closest Bearish Block:** $XXX.XX (X.X% above) - Potential resistance zone

**Interpretation:**
[Order block interpretation - e.g., "Price testing bullish order block from X days ago. Original impulse +X.X%. Watch for bounce."]

**Tools:** `analyze_ml_enhanced()` → order_blocks section

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

#### 📚 AL BROOKS EDUCATIONAL BREAKDOWN (Teach Me Price Action!)

**Purpose:** This section translates raw price action data into actionable trading decisions. Al Brooks' methodology from "Reading Price Charts Bar By Bar" teaches us to read what the market is DOING, not what we WANT it to do.

---

#### 1. WHAT THE MARKET IS DOING (Always-In Direction)

**Always-In Direction:** [LONG / SHORT / NEUTRAL]

[If Always-In LONG]:
The market is currently **"Always-In LONG"**, which means **bulls are in control** and you should look for opportunities to **buy dips** or **pullbacks to support**. Shorting against this trend is dangerous - the market wants to go higher.

**What "Always-In LONG" means:**
- If a trader were **forced to be in the market** (either long or short), they would choose LONG because bulls have the edge.
- **Every pullback is a buying opportunity** - the trend is your friend.
- Bears are getting trapped - their shorts are losing money and will cover (creating buying pressure).

**Trading Implication:**
- ✅ **DO:** Buy pullbacks to EMA20, VWAP, or support levels. Use bull flag breakouts. Enter on High 2 or Low 1 setups.
- ❌ **DON'T:** Short into this strength. Even if you think it's "overbought," the trend can stay overbought longer than you can stay solvent.

**Brooks' Teaching:** "When Always-In is LONG, every selloff is a bull flag until proven otherwise. Buy the dips, don't fight the bulls." (Reading Price Charts Bar By Bar, Chapter 5)

[If Always-In SHORT]:
The market is currently **"Always-In SHORT"**, which means **bears are in control** and you should look for opportunities to **sell rallies** or **resistance rejections**. Buying against this trend is dangerous - the market wants to go lower.

**What "Always-In SHORT" means:**
- If a trader were **forced to be in the market**, they would choose SHORT because bears have the edge.
- **Every rally is a selling opportunity** - the downtrend is strong.
- Bulls are getting trapped - their longs are losing money and will exit (creating selling pressure).

**Trading Implication:**
- ✅ **DO:** Sell rallies to EMA20, VWAP, or resistance. Use bear flag breakdowns. Enter on Low 2 or High 1 setups.
- ❌ **DON'T:** Buy dips in a bear trend. "Catching falling knives" loses money.

**Brooks' Teaching:** "When Always-In is SHORT, every rally is a bear flag. Sell the rips, ride the trend down." (Chapter 6)

[If Always-In NEUTRAL]:
The market is **"Always-In NEUTRAL"** - neither bulls nor bears are in control. This is **range-bound, choppy price action** where the market is in **balance**.

**What "Neutral" means:**
- **No clear trend** - price is oscillating between support and resistance.
- **Both sides are getting trapped** - breakouts fail, reversals happen quickly.
- **Low conviction environment** - wait for clarity before taking directional bets.

**Trading Implication:**
- ✅ **DO:** Fade extremes (sell resistance, buy support). Trade the range. Wait for breakout confirmation before trend-following.
- ❌ **DON'T:** Chase breakouts without strong confirmation. Most breakouts in ranges FAIL.

**Brooks' Teaching:** "In trading ranges, buy low, sell high, and get out quickly. Wait for a strong breakout before switching to trend mode." (Chapter 8)

---

#### 2. THE PATTERN (Continuation vs Reversal Setup)

**Current Pattern:** [Pattern Name from analyze_ml_enhanced]

**Pattern Description:**

[If High 2]:
📋 **HIGH 2** (Bull Reversal - High Probability Setup)

**What it is:** A High 2 is a **two-legged pullback in an uptrend** that tests a prior high. It's one of Al Brooks' **highest probability buy setups** (60-70% win rate).

**Setup Structure:**
1. **Bar 1:** A strong bull bar makes a new high
2. **Bar 2:** A pullback bar (bear bar or doji) pulls back but stays above support
3. **Bar 3 (Entry):** Price makes another attempt at the high - if it breaks above Bar 1's high, BUY

**Why it works:**
- **Failed bear breakout:** Bears tried to push lower (Bar 2) but failed - creates a "bear trap"
- **Bull resumption:** Bulls regain control and push to new highs
- **Trapped bears cover:** Bears who shorted on Bar 2 must cover, adding buying pressure

**Example from current chart:**
- Bar [Date-2]: High at $XXX.XX (Bar 1)
- Bar [Date-1]: Pullback to $XXX.XX (Bar 2) - bears tried to break down
- Bar [Today]: Pushing back above $XXX.XX (Bar 3) - **This is the High 2 entry**

**Entry:** Buy stop above Bar 1 high ($XXX.XX)
**Stop:** Below Bar 2 low ($XXX.XX)
**Target:** Measured move or prior swing high ($XXX.XX)

**Brooks' Teaching:** "High 2 is a failed bear breakout that becomes a bull signal. The best trades are when one side gives up." (Chapter 17)

[If Low 1]:
📋 **LOW 1** (Bull Entry - High Probability Setup)

**What it is:** A Low 1 is the **first pullback in a strong bull trend**. It's a **buy-the-dip setup** with 60%+ win rate when trend is strong.

**Setup Structure:**
1. Strong bull trend with consecutive bull bars
2. First pullback (1-3 bars) to support (EMA20, VWAP, prior resistance turned support)
3. Entry: Buy when price bounces off support with a bull reversal bar

**Why it works:**
- **Strong trend momentum:** Bulls are in control, first pullback is shallow
- **Late bulls enter:** Traders who missed the initial move buy the dip
- **Bears weak:** Bears aren't strong enough to create deep pullback

**Current Setup:**
- Prior trend: [X consecutive bull bars, +XX% move]
- Pullback depth: [X% from high to current support]
- Support level: $XXX.XX (EMA20 / VWAP / prior resistance)

**Entry:** Buy above bull reversal bar at support
**Stop:** Below support ($XXX.XX)
**Target:** Swing high or measured move

**Brooks' Teaching:** "The first pullback in a strong trend is the best entry. Buy it before the second leg up begins." (Chapter 16)

[If Wedge]:
📋 **WEDGE** ([Bull/Bear] Wedge - Reversal Setup)

**What it is:** A wedge is a **three-push pattern** that signals **exhaustion** and likely **reversal**. It's a climactic move where the trend is running out of steam.

**Wedge Structure:**
1. **Push 1:** Strong move in trend direction
2. **Push 2:** Pullback, then another push (usually weaker momentum)
3. **Push 3:** Final push (often weakest) - **THIS IS THE REVERSAL POINT**

**Why it works:**
- **Exhaustion:** Each push gets weaker (shrinking bars, lower volume, divergences)
- **Trapped traders:** Late trend-followers buy/sell the top/bottom (Push 3)
- **Smart money exits:** Early traders take profits, reversing the move

**Current Wedge Analysis:**
- **Push 1:** [Date] - $XXX.XX to $XXX.XX (+XX%)
- **Push 2:** [Date] - $XXX.XX to $XXX.XX (+XX%) ← Weaker momentum
- **Push 3:** [Today] - $XXX.XX to $XXX.XX (+XX%) ← **Weakest push, reversal likely**

**Reversal Signal:**
[If Bull Wedge]: **Sell** when Push 3 fails to make new high or breaks below wedge line
[If Bear Wedge]: **Buy** when Push 3 fails to make new low or breaks above wedge line

**Entry:** Reversal confirmed by strong counter-trend bar
**Stop:** Beyond Push 3 extreme
**Target:** Opposite side of wedge or measured move

**Brooks' Teaching:** "Wedges are climactic moves. When you see three pushes with weakening momentum, prepare for reversal." (Chapter 11)

[If Breakout]:
📋 **BREAKOUT** (Trend Continuation - Moderate Probability)

**What it is:** Price breaks above/below a significant level (resistance, support, trendline, range). **Breakouts can succeed (continuation) or fail (reversal)** - confirmation is critical.

**Breakout Analysis:**
- **Breakout Level:** $XXX.XX ([Resistance / Support / Range high/low])
- **Breakout Bar:** [Strong bull/bear bar / Weak doji] ← **Strength matters**
- **Volume:** [XX% above average / Below average] ← **Confirms conviction**
- **Follow-Through:** [Consecutive bars in breakout direction / Immediate pullback]

**Probability Assessment:**

[If Strong Breakout]:
✅ **HIGH PROBABILITY BREAKOUT** (70%+ success rate)
- **Strong breakout bar:** Large bull/bear bar closing near extreme
- **High volume:** XX% above average (institutions participating)
- **Follow-through:** Next 1-2 bars continue in breakout direction
- **No immediate pullback:** Price doesn't retest breakout level immediately

**Entry:** Buy/Sell pullback to breakout level (now support/resistance)
**Stop:** Below/Above breakout level
**Target:** Measured move (height of range projected from breakout)

[If Weak Breakout]:
⚠️ **WEAK BREAKOUT - LIKELY TO FAIL** (30-40% success rate)
- **Weak breakout bar:** Small bar, doji, or immediate reversal
- **Low volume:** Below average (retail traders only, no institutions)
- **Immediate pullback:** Price retests breakout level right away
- **Overlap:** Breakout bar overlaps prior bar (lack of conviction)

**Trading Implication:**
- ❌ **DON'T chase weak breakouts** - wait for them to fail, then trade the reversal
- ✅ **Fade the breakout:** If it fails to follow through, take the opposite trade

**Brooks' Teaching:** "Strong breakouts have strong bars, high volume, and no pullback. Weak breakouts fail 60-70% of the time - fade them." (Chapter 9)

[If Channel]:
📋 **CHANNEL** (Trend with Parallel Lines)

**What it is:** A channel is a **trend with clear boundaries** - price oscillates between a **trend line** (support in uptrend, resistance in downtrend) and a **channel line** (parallel line on opposite side).

**Channel Characteristics:**
- **Direction:** [Bull Channel / Bear Channel]
- **Slope:** [Steep / Moderate / Shallow] ← Determines sustainability
- **Width:** [Wide / Tight] ← Determines volatility
- **Touches:** X touches on trend line, X touches on channel line

**Trading the Channel:**

[If Bull Channel]:
✅ **Buy the Trend Line (Support):** Each pullback to the lower channel line is a buy opportunity
- Entry: Buy when price tests trend line with bull reversal bar
- Stop: Below trend line
- Target: Upper channel line

⚠️ **Fade the Channel Line (Resistance):** When price reaches upper channel line, consider taking profits or selling
- Not a short unless channel breaks (trend is still bullish)

[If Bear Channel]:
✅ **Sell the Trend Line (Resistance):** Each rally to the upper channel line is a sell opportunity
- Entry: Sell when price tests trend line with bear reversal bar
- Stop: Above trend line
- Target: Lower channel line

**Channel Breakout:**
- **Breakout above channel (Bull):** Acceleration signal - trend strengthening
- **Breakdown below channel (Bear):** Trend failure - potential reversal

**Brooks' Teaching:** "Trade with the channel - buy lows, sell highs within the trend. Only reverse when channel breaks." (Chapter 10)

---

#### 3. RECENT PRICE ACTION (Bar-by-Bar Reading)

**Last 5 Bars Analysis:** (Read the bars like a story - what are they telling us?)

**Bar [Today]:**
- **Type:** [Strong Bull Bar / Bear Bar / Doji / Inside Bar]
- **Close:** $XXX.XX ([Near High / Near Low / Middle])
- **Size:** [Large / Average / Small] relative to recent bars
- **Tails:** [Long upper tail / Long lower tail / No tails]

**Interpretation:**
[If Strong Bull Bar closing near high]:
✅ **BULLISH CONVICTION** - Buyers dominated this entire period. They bought the open, pushed price higher, and held into the close. This is **strong buying pressure**.
- **No upper tail:** No selling pressure even at highs - bulls are aggressive
- **Small/no lower tail:** No downside test - bulls confident
- **Implication:** Expect continuation higher or at worst a shallow pullback

[If Bear Bar closing near low]:
⚠️ **BEARISH PRESSURE** - Sellers dominated. They sold the open, pushed price lower, and held into the close. This is **strong selling pressure**.
- **No lower tail:** No buying support even at lows - bears are aggressive
- **Small/no upper tail:** No upside test - bears confident
- **Implication:** Expect continuation lower or at worst a shallow bounce

[If Doji / Small Bar]:
⚠️ **INDECISION** - Neither bulls nor bears in control. Price opened, went nowhere, closed near open. This is **neutral** and suggests:
- **Market uncertainty:** Waiting for catalyst or breakout direction
- **Potential reversal:** After strong trend, doji = exhaustion
- **Inside bar:** Low conviction - next bar will determine direction

**Implication:** Wait for next bar to clarify direction. Don't trade indecision.

[If Inside Bar]:
⚠️ **COMPRESSION** - Inside bar (high/low both inside prior bar's high/low) = **coiling price action**. Market is compressing before explosive move.
- **Breakout coming:** Inside bars often precede strong breakouts (up or down)
- **Direction unclear:** Wait for breakout bar to show direction
- **Entry:** Buy/Sell breakout of inside bar's high/low

**Bar [Date-1]:**
- **Type:** [Bar type]
- **Close:** $XXX.XX
- **Interpretation:** [Same detailed analysis]

**Bar [Date-2]:**
- **Type:** [Bar type]
- **Close:** $XXX.XX
- **Interpretation:** [Same detailed analysis]

**Bar [Date-3]:**
- **Type:** [Bar type]
- **Close:** $XXX.XX
- **Interpretation:** [Same detailed analysis]

**Bar [Date-4]:**
- **Type:** [Bar type]
- **Close:** $XXX.XX
- **Interpretation:** [Same detailed analysis]

**PATTERN OBSERVATIONS (5-Bar Story):**

[If String of Bull Bars]:
📈 **STRONG BULL TREND** - X consecutive bull bars closing near highs = **powerful buying pressure**. Each bar confirms bulls are in control. This is a **trend day** or **strong trending move**.
- **Entry Signal:** Buy first pullback (Low 1 setup)
- **Risk:** Buying too late after X bars up - wait for pullback

[If Overlapping Bars / Congestion]:
⚠️ **CONSOLIDATION / RANGE** - Bars overlapping, no clear direction = **trading range**. Neither bulls nor bears winning.
- **Entry Signal:** Buy support, sell resistance WITHIN the range
- **Breakout Setup:** Waiting for breakout of range (strong bar + volume)

[If Decreasing Bar Size]:
⚠️ **MOMENTUM FADING** - Bars getting smaller = trend losing steam. This often precedes **reversal** or **deeper pullback**.
- **Warning Sign:** If in a trend, be ready to take profits or tighten stops
- **Reversal Setup:** Look for reversal pattern (Wedge, Failed Breakout)

---

#### 4. WHY THIS MATTERS (Probability + Conviction)

**BASE PATTERN PROBABILITY:** XX% ([Pattern name] has historical XX% success rate)

**CONTEXT ADJUSTMENTS:**

Al Brooks teaches us that **context is everything** - a pattern's probability changes based on surrounding factors:

**Positive Factors (Increase Probability):**
✅ **Strong Trend:** Always-In LONG/SHORT = +10-15% (trend continuation favored)
✅ **High Volume on Setup Bar:** XX% above average = +10% (institutions participating)
✅ **Multiple Timeframe Alignment:** Daily + Weekly both bullish = +10-15% (higher timeframe confirms)
✅ **Catalyst Present:** Earnings in X days / News event = +5-10% (fundamental driver)
✅ **Failed Opposite Setup:** Bears tried to break down but failed (High 2) = +10-15% (trapped traders must cover)
✅ **Strong Bars:** Large bars, closing near extremes = +5-10% (conviction)
✅ **Clean Pattern:** No overlap, clear structure = +5% (textbook setup)

**Negative Factors (Decrease Probability):**
❌ **Counter-Trend Trade:** Shorting Always-In LONG = -20-30% (fighting the trend)
❌ **Low Volume:** XX% below average = -10-15% (retail only, no institutional support)
❌ **Choppy/Overlapping Bars:** = -10% (indecision, low conviction)
❌ **Late in Move:** X bars into trend without pullback = -10-15% (exhaustion risk)
❌ **Multiple Failed Attempts:** Prior breakouts failed = -10% (resistance strong)
❌ **Weak Bars:** Small bars, dojis, long tails = -10% (weak momentum)
❌ **Divergences:** Price higher but RSI/MACD lower = -10-15% (bearish divergence)

**🆕 DALIO ECONOMIC MACHINE ADJUSTMENTS (Ray Dalio):**

*"Price = Total Spending / Quantity Sold"* - Understanding money flow tells you what the REAL buyers are doing.

✅ **Dalio Ratio ≥1.02 (LONG):** = +5% (buyers paying premium = strong demand)
✅ **Dalio Ratio ≤0.98 (SHORT):** = +5% (buyers paying discount = weak demand)
✅ **Positive Dollar Flow (LONG):** = +3% (net accumulation = institutions buying)
✅ **Negative Dollar Flow (SHORT):** = +3% (net distribution = institutions selling)
✅ **High Sustainability ≥70:** = +3% (trend is sustainable = stay in trade)

❌ **Dalio Ratio <0.98 (LONG):** = -5% (buyers paying less = weakening demand)
❌ **Dalio Ratio >1.02 (SHORT):** = -5% (buyers paying premium = not weak enough)
❌ **Negative Dollar Flow (LONG):** = -3% (distribution opposes LONG)
❌ **Positive Dollar Flow (SHORT):** = -3% (accumulation opposes SHORT)
❌ **Low Sustainability ≤30:** = -3% (trend reversing = exit)

**Total Dalio Impact:** Up to +11% or -11% probability adjustment

**CALCULATION:**

Base Pattern (e.g., High 2): 60%
+ Strong Trend (Always-In LONG): +15%
+ High Volume: +10%
+ Failed Bear Breakout: +15%
+ Clean Pattern: +5%
+ Dalio Ratio 1.03 (buyers paying 3% premium): +5%
+ Positive Dollar Flow ($500M accumulation): +3%
+ High Sustainability (75): +3%
- Late in Move (X bars up): -10%

**= FINAL BROOKS PROBABILITY: 106% → capped at 80%**

*Note: Probability capped at 30-80% range per Al Brooks methodology*

**CONVICTION ASSESSMENT:**

[If Probability ≥70%]:
✅ **VERY STRONG CONVICTION - HIGH PROBABILITY TRADE**

This is a **textbook setup** with multiple factors aligned:
- Pattern is clear and clean (no ambiguity)
- Context supports the setup (trend, volume, catalyst)
- Risk/reward is favorable (tight stop, clear target)

**Trading Implication:** **Full position size** (within 2% risk limit). This is the kind of setup you SHOULD take. All the factors align - this is what we wait for.

**Brooks' Teaching:** "When you have 70%+ probability, strong conviction, and all factors aligned - BET BIG (within your risk rules). These setups don't come every day." (Chapter 20)

[If Probability 50-69%]:
⚠️ **MODERATE CONVICTION - ACCEPTABLE TRADE**

This is a **decent setup** but not perfect:
- Pattern is present but some negative factors exist (late in move, weak volume, etc.)
- Risk/reward is acceptable but not ideal
- Could work, but not a "slam dunk"

**Trading Implication:** **Reduced position size** (50-75% of normal). This is tradeable but not a high-conviction setup. Be ready to exit quickly if it doesn't work.

**Brooks' Teaching:** "50-60% setups are coin flips. Only take them if risk/reward is 2:1 or better to compensate for lower probability." (Chapter 21)

[If Probability <50%]:
❌ **LOW CONVICTION - AVOID OR WAIT**

This setup has **too many negative factors**:
- Counter-trend, weak bars, low volume, or conflicting signals
- Probability is AGAINST you (less than 50% = losing trade long-term)

**Trading Implication:** **DO NOT TRADE** - Wait for better setup. Forcing trades with <50% probability is how traders lose money.

**Brooks' Teaching:** "If you don't have at least 60% probability AND 1:1 risk/reward (or 50% probability with 2:1 R/R), DON'T TRADE. Patience is a position." (Chapter 22)

---

#### 5. TRAP WARNING (When NOT To Trade)

**TRAP RISK ASSESSMENT:** [HIGH / MODERATE / LOW]

Al Brooks teaches that **recognizing TRAPS is more important than recognizing setups**. Most traders lose money because they get trapped, not because they miss good setups.

**COMMON TRAPS TO AVOID:**

[If TRAP RISK = HIGH]:
🚨 **HIGH TRAP RISK - DO NOT ENTER**

**Why This Is A Trap:**

[If Late in Trend]:
⚠️ **LATE-IN-MOVE TRAP** (Buying the Top / Selling the Bottom)

**What's happening:** Price has rallied X bars / XX% without pullback. Everyone sees the trend and wants in. This is when **late bulls buy the top** and get trapped.

**Trap Mechanism:**
1. **Early bulls (smart money):** Already in from $XXX - sitting on XX% gains
2. **Late bulls (retail):** Seeing the move NOW, buying at $XXX (the high)
3. **Early bulls take profit:** Sell to late bulls at the top
4. **Late bulls trapped:** Price reverses, they're underwater immediately

**How to Avoid:**
- ✅ **Wait for pullback:** Don't chase. Wait for first pullback (Low 1 setup)
- ✅ **Check for exhaustion signals:** Wedge, divergence, weak bars, low volume
- ❌ **Don't buy breakouts after X bars up:** You're late. The move is over.

**Brooks' Teaching:** "The best time to buy is when nobody wants it (support, pullback). The worst time is when everyone wants it (breakout after big move). Don't be the last buyer." (Chapter 7)

[If Counter-Trend]:
⚠️ **COUNTER-TREND TRAP** (Fighting the Trend)

**What's happening:** Always-In is LONG but you want to short because "it's overbought" or "it has to pull back." This is **fighting the trend** - one of the most common traps.

**Trap Mechanism:**
1. **Strong trend:** Bulls are in control, Always-In LONG
2. **Retail shorts:** "This is too high, I'm shorting" (counter-trend)
3. **Trend continues:** Bulls keep buying, price keeps rising
4. **Shorts cover at loss:** Retail covers, adding to buying pressure (squeeze)

**How to Avoid:**
- ✅ **Trade WITH the trend:** If Always-In LONG, ONLY look for longs (buy dips)
- ✅ **Wait for trend reversal:** Need strong reversal pattern (Wedge, Failed Breakout) before counter-trend
- ❌ **Don't short strong uptrends:** "Trend is too strong" = not a reason to short

**Brooks' Teaching:** "The trend is always stronger than you think. When Always-In is LONG, every selloff is a bull flag until proven otherwise. Don't fight it." (Chapter 5)

[If Weak Breakout]:
⚠️ **FAILED BREAKOUT TRAP** (Chasing Weak Breakouts)

**What's happening:** Price breaks above resistance with **weak bar, low volume, immediate pullback**. Retail traders buy the breakout. Smart money fades it (sells). Breakout fails.

**Trap Mechanism:**
1. **Weak breakout:** Small bar, low volume, doji
2. **Retail buys:** "Breakout! I'm buying!" (no confirmation)
3. **Breakout fails:** Price immediately reverses back into range
4. **Retail stops hit:** Buyers trapped, stopped out at loss

**How to Avoid:**
- ✅ **Require confirmation:** Strong breakout bar + high volume + follow-through
- ✅ **Wait for retest:** Buy the pullback to breakout level (now support), not the breakout itself
- ❌ **Don't chase weak breakouts:** 60-70% of weak breakouts FAIL

**Brooks' Teaching:** "Most breakouts fail. Only trade breakouts with strong bars, high volume, and no immediate reversal. Otherwise, fade them." (Chapter 9)

[If TRAP RISK = MODERATE]:
⚠️ **MODERATE TRAP RISK - REDUCE SIZE OR WAIT**

**Caution Areas:**
- **Overlapping bars:** Choppy price action = indecision = reversals likely
- **Divergences present:** Price higher but RSI/MACD lower = bearish divergence (momentum fading)
- **Multiple timeframe conflict:** Daily bullish but weekly bearish = mixed signals
- **Earnings/event coming:** Unpredictable volatility ahead (X days to earnings)

**How to Trade:**
- ✅ **Reduce position size:** 50% of normal size (less conviction)
- ✅ **Tighter stops:** Be ready to exit quickly if setup fails
- ✅ **Consider waiting:** If unsure, better to miss trade than lose money

[If TRAP RISK = LOW]:
✅ **LOW TRAP RISK - GOOD SETUP**

**Why This Is Safe:**
- **Clear pattern:** Textbook setup (High 2, Low 1, strong breakout)
- **Strong bars:** Large bars closing near extremes = conviction
- **High volume:** Institutions participating
- **Trend alignment:** Trading WITH Always-In direction
- **No conflicting signals:** All factors agree

**Trading Implication:** This is a **high-probability, low-trap-risk setup**. Full position size justified (within 2% risk limit).

---

#### 6. TRADING IMPLICATION (What To Do RIGHT NOW)

**Based on ALL analysis above, here's your SPECIFIC action plan:**

[If Always-In LONG + High Probability Setup]:
✅ **BUY SIGNAL - Enter Long Position**

**Entry Strategy:**

**Option 1: Aggressive Entry (If Currently At Support)**
- **Entry:** BUY NOW at $XXX.XX (current price at [EMA20 / VWAP / support])
- **Why:** Price is testing support RIGHT NOW with [bull reversal bar / hammer / strong bounce]
- **Risk:** If you wait, you might miss the entry as price bounces

**Option 2: Conservative Entry (Wait for Confirmation)**
- **Entry:** BUY STOP at $XXX.XX (above prior bar high or resistance)
- **Why:** Confirms bulls are in control before entering
- **Risk:** Slightly worse entry price but more confirmation

**Stop Loss:**
- **Price:** $XXX.XX (below [support / EMA20 / prior swing low])
- **Distance:** -X.X% from entry
- **Dollar Risk:** $XXX per share × position size = $XXX total risk
- **Why this stop:** If price breaks below support, the setup has FAILED - exit immediately

**Position Sizing:**
- **Account Size:** $XX,XXX
- **Risk per trade:** 2% = $XXX max loss
- **Share Size:** $XXX max loss ÷ $X.XX stop distance = XXX shares
- **Capital Deployed:** XXX shares × $XXX.XX entry = $XX,XXX

**Profit Targets:**

**Target 1 (Conservative):** $XXX.XX (+X.X%) - [Prior resistance / R1 level]
- **Action:** Sell 50% of position, move stop to breakeven on remaining
- **Why:** Lock in profit, reduce risk to zero

**Target 2 (Moderate):** $XXX.XX (+XX%) - [Major resistance / R2 level]
- **Action:** Sell 25% more (75% total out)
- **Why:** Take majority of profit off table

**Target 3 (Aggressive):** $XXX.XX (+XX%) - [Measured move / R3 level]
- **Action:** Let final 25% run with trailing stop
- **Why:** Capture full trend move if it continues

**Time Horizon:** X-XX days (based on [setup type / catalyst timing / trend strength])

**Exit Triggers (STOP LOSS SCENARIOS):**
1. **Price breaks below $XXX.XX:** Setup failed - exit immediately
2. **Pattern invalidation:** If Always-In flips to SHORT, exit longs
3. **Time stop:** If X days pass with no progress, re-evaluate (might be wrong)
4. **Catalyst:** If earnings/news is negative, exit regardless of price

**Risk/Reward:**
- **Risk:** $XXX (X.X%)
- **Reward:** $XXX (Target 1) to $XXX (Target 3) = XX% to XX%
- **R/R Ratio:** [2:1 / 3:1 / 5:1] ✅ (Acceptable for XX% probability trade)

**Brooks' Checklist Before Entry:**
- [ ] Always-In direction = LONG ✅
- [ ] Pattern probability ≥60% ✅
- [ ] Risk/reward ≥2:1 ✅
- [ ] Stop loss defined and acceptable ✅
- [ ] Position size = 2% max risk ✅
- [ ] Volume confirms setup ✅
- [ ] No major trap risks ✅

**IF ALL CHECKBOXES = ✅, EXECUTE THE TRADE.**

**Brooks' Final Teaching:** "The best trades are obvious, boring, and textbook. If you have to convince yourself to take it, don't take it. Wait for the setups that scream at you." (Chapter 23)

[If Always-In SHORT + High Probability Setup]:
✅ **SELL SIGNAL - Enter Short Position**

[Same detailed structure as LONG, but inverted for shorts]
- Entry: Sell at resistance / breakdown level
- Stop: Above resistance / prior swing high
- Targets: Support levels (S1, S2, S3)

[If NEUTRAL / Low Probability]:
⚠️ **NO TRADE - WAIT FOR BETTER SETUP**

**Why NOT to trade:**
- [Always-In NEUTRAL = choppy, no edge]
- [Probability <60% = coin flip]
- [Trap risk HIGH = likely to lose money]
- [Conflicting signals = uncertainty]

**What to do instead:**
1. ✅ **Wait for clarity:** Let market resolve (breakout or reversal)
2. ✅ **Set alerts:** Price at $XXX (support) or $XXX (resistance) - wait for test
3. ✅ **Re-evaluate tomorrow:** New bar = new information
4. ❌ **Don't force trades:** No trade is better than bad trade

**Brooks' Teaching:** "The market is there every day. If you don't have a good setup TODAY, wait for tomorrow. Patience is the most important skill." (Chapter 24)

---

**📊 AL BROOKS PRICE ACTION SCORE: XX/100**

**Components:**
- **Pattern Quality:** XX/30 pts (Clean pattern, high probability setup)
- **Bar Reading:** XX/25 pts (Strong bars, conviction, momentum)
- **Context Alignment:** XX/25 pts (Trend, volume, catalysts aligned)
- **Trap Avoidance:** XX/20 pts (Low trap risk, good entry timing)

[If Score ≥75]:
✅ **HIGH CONVICTION - TEXTBOOK SETUP**
This is the kind of setup Al Brooks teaches in his books - clear pattern, strong context, low trap risk. This is a **high-probability trade** worth taking (full position size within 2% risk limit).

[If Score 50-74]:
⚠️ **MODERATE CONVICTION - ACCEPTABLE WITH CAVEATS**
Setup is decent but has some flaws (weak bars, late in move, moderate volume). Tradeable with **reduced size** (50-75%) and tight stops.

[If Score <50]:
❌ **LOW CONVICTION - AVOID**
Too many red flags (counter-trend, weak bars, high trap risk, conflicting signals). **DO NOT FORCE THIS TRADE** - wait for better setup.

---

**🎓 KEY TAKEAWAY:**

Al Brooks teaches us to **read price action like a language** - every bar tells a story. The best traders:
1. Know what the market is DOING (Always-In direction)
2. Recognize patterns (High 2, Low 1, Wedge, Breakout)
3. Read bars for conviction (strong vs weak, bulls vs bears)
4. Calculate probability (context adjustments)
5. Avoid traps (late entries, counter-trend, weak breakouts)
6. Execute with discipline (entry, stop, targets, position size)

**Your edge is NOT predicting the future - it's reading what's happening NOW and acting on high-probability setups with disciplined risk management.**

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

### 6. McMILLAN OPTIONS STRATEGY (Phase 3 - 17.9%) ⭐ NEW

**Reference:** Lawrence McMillan, "Options as a Strategic Investment" (5th Edition)

#### A. Implied Volatility Analysis

**📊 IV METRICS:**

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Current IV** | XX.X% | ATM option implied volatility |
| **IV Rank** | XX% | Current IV vs 52-week range (0-100) |
| **IV Percentile** | XX% | % of days IV was lower |
| **52W IV High** | XX.X% | Historical ceiling |
| **52W IV Low** | XX.X% | Historical floor |
| **Divergence Check** | **[ALIGNED/DIVERGENT]** | Rank vs Percentile comparison |
| **IV Environment** | **[HIGH/LOW/NORMAL]** | Strategy selection driver |

**IV Divergence Interpretation:**
- **Both HIGH (Rank >70, Percentile >70):** Genuinely elevated IV → Premium selling optimal
- **Both LOW (Rank <30, Percentile <30):** Genuinely suppressed IV → Premium buying optimal
- **Rank HIGH + Percentile LOW:** Recent volatility spike but historically normal → Watch for mean reversion
- **Rank LOW + Percentile HIGH:** Unusual IV compression → Potential breakout setup

**IV Interpretation:**
- **HIGH IV (>70 rank):** Sell premium strategies - IV likely to contract
- **LOW IV (<30 rank):** Buy premium strategies - IV likely to expand
- **NORMAL IV:** Flexible strategy selection based on direction

**McMillan Reference:** Chapter 28 - Volatility Trading

#### A.1. Expected Price Movement & Standard Deviation Ranges ⭐ NEW

**📊 STANDARD DEVIATION ANALYSIS:**

**Formula:** Expected Move = Current Price × IV × √(DTE / 365)

| Timeframe | DTE | 1 SD Move | 1 SD Range (68% prob) | 2 SD Move | 2 SD Range (95% prob) |
|-----------|-----|-----------|----------------------|-----------|----------------------|
| **Weekly** | 7 | ±$X.XX | $XXX.XX - $XXX.XX | ±$X.XX | $XXX.XX - $XXX.XX |
| **Monthly** | 30 | ±$X.XX | $XXX.XX - $XXX.XX | ±$X.XX | $XXX.XX - $XXX.XX |
| **45 DTE** | 45 | ±$X.XX | $XXX.XX - $XXX.XX | ±$X.XX | $XXX.XX - $XXX.XX |
| **Quarterly** | 90 | ±$X.XX | $XXX.XX - $XXX.XX | ±$X.XX | $XXX.XX - $XXX.XX |

**Current Price:** $XXX.XX
**Current IV:** XX.X%

**Probability-Based Strike Selection:**

| Delta | Standard Deviation | Probability OTM | Strike Price | Use Case |
|-------|-------------------|-----------------|--------------|----------|
| **50Δ** | 0 SD (ATM) | 50% | $XXX.XX | Neutral / Maximum theta |
| **30Δ** | ~0.5 SD | 70% | $XXX.XX | Moderate premium collection |
| **16Δ** | ~1 SD | 84% | $XXX.XX | **TastyTrade Standard (Optimal R/R)** ⭐ |
| **10Δ** | ~1.5 SD | 90% | $XXX.XX | Higher probability |
| **5Δ** | ~2 SD | 95% | $XXX.XX | Highest probability (but low premium) |

**Interpretation:**

**1 Standard Deviation (68% Probability):**
- Stock has **68% chance** of staying within ±$X.XX range over next [X] days
- **16-delta options** sit at ~1 SD → **84% probability of expiring OTM**
- **OPTIMAL for credit spreads** per TastyTrade research
- Example: Sell $XXX put (16Δ) / Buy $XXX put (5Δ) = **84% win rate with reasonable premium**

**2 Standard Deviation (95% Probability):**
- Stock has **95% chance** of staying within ±$X.XX range
- **5-delta options** sit at ~2 SD → **95% probability of expiring OTM**
- **HIGH win rate BUT low premium** - not optimal for expected value
- Use for protective strikes in spreads, not primary income generation

**Why 16-Delta (1 SD) is Optimal:**

| Strike Selection | Delta | Win Rate | Premium | Expected Value | Recommendation |
|-----------------|-------|----------|---------|----------------|----------------|
| ATM (50Δ) | 50Δ | 50% | $3.00 | Negative | ❌ Coin flip |
| 1 SD (16Δ) | 16Δ | 84% | $1.00 | **POSITIVE** | ✅ **OPTIMAL** |
| 2 SD (5Δ) | 5Δ | 95% | $0.30 | Negative | ❌ Too far OTM |

**TastyTrade Research:** 16-delta strikes provide the **best risk-adjusted returns** over time:
- Good win rate (84%)
- Reasonable premium collection
- Positive expected value
- Manageable losses when wrong

**Reference:** TastyTrade "The Skinny on Options Math" + McMillan Ch. 28

#### B. Put/Call Ratio Analysis

**📊 P/C RATIO METRICS:**

| Metric | Value | Signal |
|--------|-------|--------|
| **Volume P/C Ratio** | X.XX | Raw sentiment indicator |
| **Raw Sentiment** | - | [Bullish <0.7 / Neutral 0.7-1.0 / Bearish >1.0] |
| **Contrarian Signal** | **[BULLISH/BEARISH/NO SIGNAL]** | **BULLISH if >1.2 / BEARISH if <0.5 / NO SIGNAL 0.5-1.2** |
| **OI P/C Ratio** | X.XX | [Positioning bias - longer-term view] |
| **Call Volume** | XXX,XXX | Total call contracts |
| **Put Volume** | XXX,XXX | Total put contracts |
| **Sentiment** | [EXTREMELY_BEARISH/BEARISH/NEUTRAL/BULLISH/EXTREMELY_BULLISH] |

**P/C Interpretation:**
- **P/C > 1.2 (Extreme Bearishness):** Contrarian BULLISH signal - crowd is overly bearish
- **P/C < 0.5 (Extreme Bullishness):** Contrarian BEARISH signal - crowd is overly bullish
- **P/C 0.5-1.2 (Normal Range):** No contrarian signal - sentiment is balanced
[Detailed explanation of what P/C ratio suggests about market sentiment]

**McMillan Reference:** Chapter 24 - Stock Option Strategies

#### C. Open Interest Analysis

**📊 MAX PAIN & KEY LEVELS:**

| Metric | Value | Impact |
|--------|-------|--------|
| **Max Pain Strike** | $XXX.XX | Where options sellers profit most |
| **Current Price** | $XXX.XX | Market price |
| **Distance to Max Pain** | +/-XX.X% | Gravitational pull direction |
| **Days to Expiry** | XX days | Expiration timing |
| **Aggregate OI** | XXX,XXX | [HIGH >100k / MEDIUM 25-100k / LOW <25k] |
| **Max Pain Reliability** | **[HIGH/MEDIUM/LOW]** | HIGH if near expiry + high OI |
| **OI Bias** | [BULLISH/BEARISH/NEUTRAL] | Price magnet effect |

**Max Pain Reliability Conditions:**
- **HIGH:** Current expiry + Last 5 days before expiration + Aggregate OI >100k
- **MEDIUM:** Current expiry + Days 6-15 before expiration OR Aggregate OI 25-100k
- **LOW:** Early cycle (>15 days) OR Aggregate OI <25k

**Top OI Strikes:**

| Type | Strike | OI | Significance |
|------|--------|-----|-------------|
| 🔵 Call | $XXX | XXX,XXX | Resistance / Call wall |
| 🔵 Call | $XXX | XXX,XXX | Secondary resistance |
| 🔴 Put | $XXX | XXX,XXX | Support / Put wall |
| 🔴 Put | $XXX | XXX,XXX | Secondary support |

**Max Pain Interpretation:**
[Explanation of how max pain affects expected price movement]

**McMillan Reference:** Chapter 25 - Index Option Strategies

#### D. Unusual Options Activity (Smart Money)

**📊 UOA DETECTION:**

| Type | Strike | Volume | OI | V/OI Ratio | Signal |
|------|--------|--------|-----|------------|--------|
| [CALL/PUT] | $XXX | XX,XXX | X,XXX | XX.X | [ITM/OTM] |
| [CALL/PUT] | $XXX | XX,XXX | X,XXX | XX.X | [ITM/OTM] |
| ... | ... | ... | ... | ... | ... |

**UOA Criteria:** Volume > 2x Open Interest + Volume > 100 contracts

**Smart Money Signal:** [BULLISH/BEARISH/MIXED/NO_SIGNAL]

**Interpretation:**
[Explanation of what unusual activity suggests about institutional positioning]

**McMillan Reference:** Chapter 36 - Portfolio Management

#### E. Greeks Assessment

**📊 ATM GREEKS:**

| Greek | Call | Put | Impact |
|-------|------|-----|--------|
| **Delta** | X.XX | -X.XX | Directional exposure |
| **Gamma** | X.XXXX | X.XXXX | Rate of delta change |
| **Theta** | -$X.XX | -$X.XX | Daily time decay |
| **Vega** | $X.XX | $X.XX | IV sensitivity |

**Greeks Source:** [yfinance_estimated / questrade]

**Greeks Interpretation:**

| Greek | Value | Actionable Insight |
|-------|-------|-------------------|
| **Delta** | X.XX | XX% chance ITM / $XX P&L per $1 stock move |
| **Gamma** | X.XXXX | [HIGH = explosive near expiry / LOW = stable position] |
| **Theta** | -$X.XX | Losing $X.XX/day - [Good/Bad] for [buyer/seller] |
| **Vega** | $X.XX | +/-$X.XX per 1% IV change - [Benefit/Hurt] if IV [rises/falls] |

**Position Risk Profile:** [Theta-positive/negative], [Vega-long/short], [Gamma-stable/explosive]

**Greeks Quick Reference:**
- **High Delta (>0.70):** Deep ITM, high directional exposure
- **High Gamma (>0.05):** Near ATM, dangerous near expiry
- **High Theta (>-$0.10):** Rapid time decay, favors sellers
- **High Vega (>$0.50):** IV-sensitive, benefits from vol expansion

#### F. McMillan Strategy Selection Matrix

**📊 OPTIMAL STRATEGY:**

| Factor | Current | Impact |
|--------|---------|--------|
| **IV Environment** | [HIGH/LOW/NORMAL] | Strategy type driver |
| **Direction** | [LONG/SHORT/NEUTRAL] | Directional bias |
| **Holding Period** | XX days | Time horizon |

**📊 McMILLAN STRATEGY MATRIX:**

| IV Environment | LONG Direction | SHORT Direction | NEUTRAL |
|----------------|----------------|-----------------|---------|
| **HIGH (>70)** | Bull Put Spread | Bear Call Spread | Iron Condor |
| **NORMAL (30-70)** | Long Call / Call Debit Spread | Long Put / Put Debit Spread | Butterfly |
| **LOW (<30)** | Long Call + Long Stock | Long Put + Short Stock | Calendar Spread |

**Current Selection:** Based on IV [XX%] + Direction [LONG/SHORT/NEUTRAL] → See highlighted cell above

**PRIMARY STRATEGY RECOMMENDATION:**

**[Strategy Name]** (e.g., Bull Put Spread, Long Call, Iron Condor)

**Rationale:**
[McMillan-based explanation of why this strategy is optimal for current IV + direction]

**Alternative Strategies:**

| Strategy | Type | Risk | Max Profit | Max Loss |
|----------|------|------|------------|----------|
| [Strategy 1] | Credit/Debit | Defined/Undefined | [Description] | [Description] |
| [Strategy 2] | Credit/Debit | Defined/Undefined | [Description] | [Description] |
| [Strategy 3] | Credit/Debit | Defined/Undefined | [Description] | [Description] |

**Suggested Strikes:**

| Strike Type | Price | Description |
|-------------|-------|-------------|
| ATM | $XXX | At-the-money |
| OTM Call | $XXX | Out-of-the-money call strike |
| OTM Put | $XXX | Out-of-the-money put strike |
| Deep OTM Call | $XXX | Far out-of-the-money call |
| Deep OTM Put | $XXX | Far out-of-the-money put |

#### G. McMillan Options Composite Score

**📊 OPTIONS SCORE:**

| Factor | Points | Max | Interpretation |
|--------|--------|-----|----------------|
| IV Environment | +XX | 15 | [Favorable/Unfavorable] |
| P/C Contrarian | +XX | 15 | [Aligned/Conflicting] |
| Max Pain Bias | +XX | 10 | [Supportive/Opposing] |
| UOA Signal | +XX | 15 | [Confirming/Mixed] |
| **BASE** | 50 | 50 | Starting neutral |
| **TOTAL** | **XX/100** | 100 | **[HIGH/MODERATE/LOW] Confidence** |

**Options Summary:**
- **Score:** XX/100
- **Confidence:** [HIGH/MODERATE/LOW]
- **Strategy:** [Recommended strategy]
- **IV Environment:** [HIGH/LOW/NORMAL]
- **Smart Money:** [BULLISH/BEARISH/MIXED]

**Bottom Line:**
[2-3 sentence summary of McMillan options analysis and recommended strategy with specific strikes]

**Tools:** `analyze_options_mcmillan(ticker, holding_period_days)` (direction-independent)

---

#### ⚠️ OPTIONS DATA INTERPRETATION - UNDERSTANDING EXPIRATION-SPECIFIC ANALYSIS

**CRITICAL: Why Options Data May Appear Contradictory**

`analyze_options_mcmillan()` analyzes options at **ONE SPECIFIC EXPIRATION** (the optimal 30-45 DTE entry point), while `detect_unusual_options_activity()` scans **ALL EXPIRATIONS** across the entire chain.

**Example of Apparent Contradiction:**
```
analyze_options_mcmillan(ticker, holding_period_days=45)
→ Analyzes: Feb 27, 2026 expiry (45 DTE)
→ Returns: OI=0, Volume=1, "Poor liquidity"

detect_unusual_options_activity(ticker)
→ Scans: ALL expirations
→ Finds: Jan 30, 2026 $350 call with 1,243 volume
```

**Both are CORRECT - they're analyzing DIFFERENT expirations!**

**When reporting liquidity conflicts, ALWAYS specify expiration:**

❌ **BAD (Confusing):**
```
Liquidity: Grade F (OI=0)
Unusual Activity: YES - 1,243 volume
[User thinks: "WTF? Different functions?"]
```

✅ **GOOD (Clear):**
```
Liquidity (45 DTE - Feb 27): Grade F (OI=0, Volume=1)
Unusual Activity (10 DTE - Jan 30): 1,243 volume on $350 call

**Interpretation:** The optimal 45 DTE expiration has NO liquidity.
Unusual activity detected on 10 DTE expiration (1 day after Jan 29 earnings).
This is a speculative earnings bet, NOT recommended for institutional approach.

**Recommendation:** Trade the stock OR check 60-90 DTE expirations for better liquidity.
```

**When unusual activity conflicts with McMillan liquidity assessment:**

1. ✅ **Check the expiration date** of the unusual activity
2. ✅ **Check if earnings are nearby** (earnings plays = speculative, avoid)
3. ✅ **Note the DTE difference** in your report
4. ✅ **Recommend appropriate alternatives** (stock, later expirations)
5. ❌ **NEVER say "I'm using different functions"** - say "different expirations"

---

#### 📚 McMILLAN OPTIONS EDUCATIONAL BREAKDOWN (Teach Me!)

**Purpose:** This section translates raw options data into actionable strategy selection. McMillan's methodology from "Options as a Strategic Investment" teaches us to **match strategy to volatility environment** - not just pick random strikes.

---

#### 1. WHAT THE OPTIONS MARKET IS SAYING

**Summary of Options Activity:**

[Based on analyze_options_mcmillan data]

**IV Rank:** XX% | **IV Percentile:** XX% | **P/C Ratio:** X.XX | **Max Pain:** $XXX

**Combined Reading:**

[If IV Rank >60%]:
The options market is saying: **"Expect volatility."** IV Rank above 60% means implied volatility is near the HIGH end of its 52-week range. Options are **expensive right now** - premium sellers have an edge. This is a **premium-selling environment** - strategies like Iron Condors, Credit Spreads, and Covered Calls work best.

[If IV Rank 30-60%]:
The options market is saying: **"Normal volatility environment."** IV is in the middle of its range - neither cheap nor expensive. You can use **directional strategies** (Long Calls/Puts, Debit Spreads) if you have strong conviction on direction, OR **neutral strategies** (Iron Condors) if you expect range-bound action.

[If IV Rank <30%]:
The options market is saying: **"Volatility is cheap - options are on sale."** IV Rank below 30% means implied volatility is near the LOW end of its 52-week range. This is a **premium-buying environment** - strategies like Long Calls, Long Puts, and Debit Spreads are attractive because options are underpriced relative to potential moves.

**Put/Call Ratio Sentiment:**

[If P/C Ratio >1.2]:
Put/call ratio of X.XX suggests **excessive bearish positioning**. McMillan teaches us this is often a **contrarian BULLISH signal** - when everyone is hedged/positioned bearish, a squeeze higher becomes likely.

[If P/C Ratio <0.7]:
Put/call ratio of X.XX suggests **excessive bullish positioning**. This is often a **contrarian BEARISH signal** - when everyone is positioned bullish (heavy call buying), the market may reverse lower.

[If P/C Ratio 0.7-1.2]:
Put/call ratio of X.XX is **neutral** - no contrarian signal. Use other factors for direction.

**Max Pain Price Magnetism:**

[If Max Pain is Above Current Price]:
Max pain at $XXX is **above current price ($XXX)**. Theory suggests price has **upward gravitational pull** toward max pain as market makers hedge their positions. This suggests **bullish bias** into expiration.

[If Max Pain is Below Current Price]:
Max pain at $XXX is **below current price ($XXX)**. Theory suggests price has **downward gravitational pull** toward max pain. This suggests **bearish bias** into expiration.

[If Max Pain is At Current Price]:
Max pain at $XXX is **at current price** - price is already at equilibrium. Expect **range-bound action** into expiration unless a catalyst breaks the range.

---

#### 2. IV ENVIRONMENT EXPLAINED (Strategy Selection Framework)

**Current IV Rank:** XX% → **[HIGH / NORMAL / LOW] Volatility Environment**

**What IV Rank Tells You:**

IV Rank compares **current implied volatility** to the **52-week high/low range**:

- **IV Rank = (Current IV - 52w Low IV) / (52w High IV - 52w Low IV) × 100**

**Translation:**
- **>60% = HIGH** → Options are expensive, volatility is elevated
- **30-60% = NORMAL** → Options are fairly priced
- **<30% = LOW** → Options are cheap, volatility is compressed

**Why This Matters for Strategy Selection:**

[If IV Rank >60%]:
✅ **PREMIUM SELLING STRATEGIES** (Collect expensive premium, profit from IV crush):
- **Iron Condor:** Neutral, profit from range-bound action + IV drop
- **Credit Spreads:** Directional income, sell overpriced options
- **Covered Calls:** Income generation on existing shares
- **Cash-Secured Puts:** Get paid to wait for entry

❌ **AVOID Premium Buying:** Long Calls/Puts are overpriced - you're fighting IV crush (Vega risk).

[If IV Rank 30-60%]:
✅ **DIRECTIONAL STRATEGIES** (If you have conviction):
- **Debit Spreads:** Defined risk, directional bets
- **Long Calls/Puts:** If conviction is strong and catalyst expected

✅ **NEUTRAL STRATEGIES** (If expecting range):
- **Iron Condors:** Profit from theta decay in range

[If IV Rank <30%]:
✅ **PREMIUM BUYING STRATEGIES** (Buy cheap options before volatility expansion):
- **Long Calls/Puts:** Cheap options, position for volatility spike
- **Debit Spreads:** Defined risk, cheaper entry
- **Straddles/Strangles:** If expecting big move but uncertain direction

❌ **AVOID Premium Selling:** You're selling cheap options - not enough edge.

**McMillan's Rule:** "Sell premium when IV is high, buy premium when IV is low. Match your strategy to the volatility environment, not your market opinion."

---

#### 3. PUT/CALL RATIO INTERPRETATION (Sentiment + Contrarian Signals)

**Current P/C Ratio:** X.XX

**What Put/Call Ratio Measures:**

P/C Ratio = **Put Volume / Call Volume**

**Raw Interpretation:**
- **<0.7:** Bullish sentiment (heavy call buying)
- **0.7-1.0:** Neutral to slightly bullish
- **1.0-1.2:** Neutral to slightly bearish
- **>1.2:** Bearish sentiment (heavy put buying)

**McMillan's Contrarian Framework:**

[If P/C >1.2]:
⚠️ **CONTRARIAN BULLISH SIGNAL**

**What it means:** When P/C ratio exceeds 1.2, it indicates **excessive bearish positioning** - too many puts being bought relative to calls. This often signals a **market bottom** because:

1. **Everyone is hedged:** Institutions already protected downside
2. **No sellers left:** If everyone is bearish, who's left to sell?
3. **Short squeeze potential:** Bearish positions get squeezed on any good news

**Historical Context:** McMillan's research shows P/C spikes >1.2 often precede **5-10 day rallies** as bearish positioning unwinds.

**Trading Implication:** Consider **bullish strategies** (Long Calls, Bull Call Spreads) when P/C >1.2, even if fundamental outlook is uncertain. Sentiment extremes reverse.

[If P/C <0.7]:
⚠️ **CONTRARIAN BEARISH SIGNAL**

**What it means:** When P/C ratio drops below 0.7, it indicates **excessive bullish positioning** - too many calls being bought relative to puts. This often signals a **market top** because:

1. **Everyone is positioned long:** No more buyers left to push price higher
2. **Complacency risk:** Low put buying = no fear = dangerous
3. **Profit-taking likely:** Bullish positions vulnerable to selloff

**Trading Implication:** Consider **bearish strategies** (Long Puts, Bear Put Spreads) or **protective strategies** when P/C <0.7.

[If P/C 0.7-1.2]:
✅ **NEUTRAL - NO CONTRARIAN SIGNAL**

**What it means:** P/C ratio between 0.7-1.2 is **normal balanced positioning** - no extreme sentiment. Use **other factors** (IV environment, technical setup, fundamentals) for direction.

**Trading Implication:** Focus on IV environment and directional conviction rather than sentiment.

---

#### 4. MAX PAIN & PRICE MAGNETISM (Price Target + Reliability)

**Max Pain Theory:** The price at which **option sellers** (market makers) experience **minimum loss** at expiration. Market makers delta-hedge their positions, creating **buying/selling pressure** that "pulls" price toward max pain.

**Current Max Pain:** $XXX | **Current Price:** $XXX | **Distance:** [+/-X.X%]

**Price Relationship:**

[If Max Pain Above Price]:
📈 **UPWARD GRAVITATIONAL PULL**

**What it means:** Max pain is $XXX, **above current price** by X.X%. Theory suggests market makers will **delta-hedge in a way that pushes price higher** toward max pain as expiration approaches.

**Why it happens:**
- Market makers are **short calls** above max pain → Must buy shares to hedge as price rises (creates buying pressure)
- Market makers are **long puts** below max pain → Must sell shares to hedge as puts lose value (creates more buying pressure)

**Trading Implication:** **Bullish bias** into expiration. Consider bullish strategies with targets near max pain level.

[If Max Pain Below Price]:
📉 **DOWNWARD GRAVITATIONAL PULL**

**What it means:** Max pain is $XXX, **below current price** by X.X%. Theory suggests market makers will **delta-hedge in a way that pushes price lower** toward max pain.

**Trading Implication:** **Bearish bias** into expiration. Consider bearish strategies with targets near max pain level.

[If Max Pain At Price]:
⚖️ **EQUILIBRIUM - RANGE-BOUND**

**What it means:** Max pain is **at current price** - no gravitational pull. Price is already at the optimal level for option sellers.

**Trading Implication:** Expect **range-bound action** unless a fundamental catalyst breaks the range. Consider **neutral strategies** (Iron Condor, Short Straddle).

**Reliability Assessment:**

[If Reliability HIGH]:
✅ **HIGH RELIABILITY** (Trust the max pain signal)

**Why:** High reliability occurs when:
- **Near expiration:** <7 days to expiry = stronger gravitational pull
- **High open interest:** More options = more delta-hedging pressure
- **Low volatility:** Stable environment = predictable hedging

**Confidence:** 70-80% - Max pain is a **strong price target** in these conditions.

[If Reliability MEDIUM]:
⚠️ **MEDIUM RELIABILITY** (Use with caution)

**Why:** Medium reliability when expiration is 1-2 weeks away or open interest is moderate.

**Confidence:** 50-60% - Max pain is a **weak directional bias**, not a precise target.

[If Reliability LOW]:
❌ **LOW RELIABILITY** (Do NOT trade based on max pain)

**Why:** Low reliability when:
- **Far from expiration:** >2 weeks = too early for gravitational pull
- **Low open interest:** Not enough options to create hedging pressure
- **High volatility:** Unpredictable moves overwhelm hedging effects

**Confidence:** <40% - Max pain is **noise**, ignore it.

---

#### 5. GREEKS BREAKDOWN FOR YOUR TRADE (Plain English)

**Greeks are NOT just numbers - they tell you exactly what risks you're taking and how your position will behave.**

[From analyze_options_mcmillan.greeks_assessment]

**📈 DELTA:** Call: +X.XX | Put: -X.XX

**What it means:**
- Delta tells you **how much your option price moves per $1 stock move**.
- **Call Delta +X.XX:** If stock goes up $1, your call gains ~$X.XX × 100 = $XXX per contract.
- **Put Delta -X.XX:** If stock goes down $1, your put gains ~$X.XX × 100 = $XXX per contract.

**Probability Interpretation:**
- Delta also approximates **probability of expiring ITM**:
  - Call with +0.70 delta = ~70% chance of finishing in-the-money
  - Put with -0.30 delta = ~30% chance of finishing in-the-money

**Trading Implication:**
[If Delta >0.70]: **Deep ITM** - High probability, expensive, acts like stock
[If Delta 0.40-0.70]: **ATM/Slightly ITM** - Balanced probability, good for directional trades
[If Delta <0.40]: **OTM** - Lower probability, cheap, high leverage (lotto tickets)

---

**⚡ GAMMA:** Call: X.XXXX | Put: X.XXXX → [HIGH / LOW]

**What it means:**
- Gamma tells you **how fast Delta changes** as stock moves.
- **High Gamma (>0.05):** Delta changes rapidly = **explosive gains/losses** near strike.
- **Low Gamma (<0.02):** Delta changes slowly = **stable, predictable** behavior.

**Trading Implication:**
[If Gamma HIGH]:
⚠️ **EXPLOSIVE RISK/REWARD** - Your Delta will accelerate quickly as stock moves. Great for **swing trades** if you're right, but losses accelerate fast if you're wrong.

**Example:** If stock moves $1 in your favor, your Delta might jump from 0.50 → 0.60, giving you 20% more exposure on the next $1 move.

[If Gamma LOW]:
✅ **STABLE BEHAVIOR** - Your Delta won't change much. Good for **longer-term positions** where you want predictable exposure.

---

**⏳ THETA:** Call: -$X.XX | Put: -$X.XX per day

**What it means:**
- Theta is **time decay** - how much value your option loses **per day** as expiration approaches.
- **-$X.XX per day** means you lose $X.XX × 100 = $XXX per contract every day, even if stock doesn't move.

**Trading Implication:**
[If Theta High (>-$2)]:
⚠️ **BURNING CASH FAST** - You're losing $XXX+ per day to time decay. This is **dangerous for premium buyers** (Long Calls/Puts) - you need stock to move FAST.

✅ **GREAT for premium sellers** (Iron Condors, Credit Spreads) - you're collecting this decay.

[If Theta Low (<-$0.50)]:
✅ **Slow time decay** - Longer-dated options, more time for your thesis to play out.

**McMillan's Rule:** "Theta is your enemy when you buy options, your friend when you sell them."

---

**🌪️ VEGA:** Call: $X.XX | Put: $X.XX per 1% IV change

**What it means:**
- Vega tells you **how much your option price changes per 1% move in implied volatility**.
- **Vega $X.XX** means if IV increases by 1%, your option gains $X.XX × 100 = $XXX per contract.

**Trading Implication:**

[If High IV Environment (IV Rank >60%)]:
⚠️ **VEGA RISK FOR PREMIUM BUYERS** - If you buy options in high IV, you're exposed to **IV crush** (volatility drop after earnings, news). Even if stock moves your way, IV drop can kill your gains.

**Example:** You buy a call for $5.00 in high IV (60%). Stock moves up 2%, but IV drops 10% → Your call might LOSE money due to Vega losses overwhelming Delta gains.

✅ **VEGA OPPORTUNITY FOR PREMIUM SELLERS** - Selling options in high IV means you profit from IV crush (volatility normalization).

[If Low IV Environment (IV Rank <30%)]:
✅ **VEGA OPPORTUNITY FOR PREMIUM BUYERS** - Buying options in low IV means you profit from **volatility expansion** when news/events hit.

**McMillan's Rule:** "Sell Vega (premium sell) when IV is high, buy Vega (premium buy) when IV is low."

---

**Position Risk Summary:**

[From analyze_options_mcmillan Position Risk assessment]

- **Theta Risk:** [Theta-positive = collecting decay / Theta-negative = fighting decay]
- **Vega Risk:** [Vega-long = profit from IV rise / Vega-short = profit from IV drop]
- **Gamma Risk:** [Gamma-stable = predictable / Gamma-explosive = rapid changes]

**Combined Risk Profile:**

[If Theta-negative + Vega-long in High IV]:
⚠️ **DANGER:** You're **buying premium in expensive IV** - fighting both time decay AND potential IV crush. You need a BIG, FAST move to overcome these headwinds.

[If Theta-positive + Vega-short in High IV]:
✅ **IDEAL:** You're **selling premium in expensive IV** - collecting decay AND benefiting from IV normalization. Time is on your side.

[If Theta-negative + Vega-long in Low IV]:
✅ **STRATEGIC:** You're **buying cheap options** - positioned for volatility expansion. Good for event-driven plays (earnings, FDA approvals).

---

#### 6. RECOMMENDED STRATEGY & WHY (McMillan's Strategy Selection Matrix)

**Based on:**
- **IV Environment:** [HIGH / NORMAL / LOW] (IV Rank XX%)
- **Directional Bias:** [BULLISH / BEARISH / NEUTRAL]
- **P/C Sentiment:** [Contrarian BULLISH / Contrarian BEARISH / No signal]
- **Max Pain Bias:** [Upward pull / Downward pull / Neutral]

[From analyze_options_mcmillan.strategy_selection]

**RECOMMENDED STRATEGY:** [Bull Put Spread / Long Call / Iron Condor / etc.]

**Why This Strategy:**

[If Bull Put Spread in High IV + Bullish Bias]:
📋 **BULL PUT SPREAD** (Premium Selling Strategy)

**Setup:**
- **Sell:** $XXX Put (higher strike) - Collect premium
- **Buy:** $XXX Put (lower strike) - Define max loss
- **Net Credit:** $X.XX per spread ($XXX per contract)
- **Max Profit:** $XXX (keep full credit if stock stays above $XXX at expiry)
- **Max Loss:** $XXX (if stock drops below $XXX at expiry)

**Why it works NOW:**

1. **High IV (XX%):** Options are expensive → Selling premium gives us an edge. We collect inflated premium and profit from IV crush.

2. **Bullish Bias:** [Max pain above price / Contrarian P/C signal / Technical support] suggests upward pressure. We only need stock to stay above $XXX (not rally hard).

3. **Theta Advantage:** We collect $X.XX per day in time decay. Every day stock doesn't drop, we make money.

4. **Defined Risk:** Max loss is $XXX - we know our risk upfront. Better than naked puts.

**McMillan's Take:** "In high IV, sell premium with defined risk spreads. Bull Put Spreads give you bullish exposure while collecting inflated premium." (Options as a Strategic Investment, Chapter 8)

**Probability of Profit:** ~XX% (Delta of short put = probability of expiring OTM = profit)

**Break-Even:** $XXX - $X.XX = $XXX (Stock can drop X.X% and we still profit)

[If Long Call in Low IV + Bullish Bias]:
📋 **LONG CALL** (Premium Buying Strategy)

**Setup:**
- **Buy:** $XXX Call (strike near current price or slightly OTM)
- **Expiration:** [Date] (XX days)
- **Cost:** $X.XX per contract ($XXX per contract)
- **Max Profit:** Unlimited as stock rises
- **Max Loss:** $XXX (premium paid)

**Why it works NOW:**

1. **Low IV (XX%):** Options are cheap relative to historical range. We're buying discounted premium before volatility expands.

2. **Bullish Catalyst:** [Earnings / Max pain / Technical breakout] suggests upward move. Vega will work in our favor when IV spikes.

3. **Leverage:** $XXX controls ~$XX,XXX of stock exposure (~XX:1 leverage). Small % stock move = large % option gain.

4. **Limited Risk:** Max loss is $XXX (premium paid). No margin calls, no unlimited risk.

**McMillan's Take:** "Buy options when IV is low and you have strong directional conviction. Low IV = cheap insurance against being wrong." (Chapter 3)

**Target:** $XXX stock price = $X.XX option value (XXX% gain)

**Time Risk:** Losing -$X.XX per day to theta. Need stock to move within XX days.

[If Iron Condor in High IV + Neutral Bias]:
📋 **IRON CONDOR** (Premium Selling, Neutral Strategy)

**Setup:**
- **Sell:** $XXX Call + $XXX Put (collect premium on both sides)
- **Buy:** $XXX Call + $XXX Put (define max loss on both sides)
- **Net Credit:** $X.XX per spread ($XXX per contract)
- **Profit Range:** Stock stays between $XXX - $XXX at expiry
- **Max Profit:** $XXX (keep full credit)
- **Max Loss:** $XXX (if stock breaks out of range)

**Why it works NOW:**

1. **High IV (XX%):** Options are expensive on BOTH sides. We collect inflated premium and profit from IV crush as volatility normalizes.

2. **Neutral Bias:** [Max pain at current price / Balanced P/C ratio / Range-bound technicals] suggests no strong directional move. We profit from lack of movement.

3. **Double Theta:** We collect time decay from BOTH the call spread AND put spread. Every day stock stays in range, we make money.

4. **Probability of Profit:** ~XX% (stock has XX% range to stay within, only loses if it moves >X% in either direction)

**McMillan's Take:** "Iron Condors are ideal in high IV, low-movement environments. You're selling overpriced options on both sides and betting on mean reversion." (Chapter 14)

**Management:** If stock approaches $XXX or $XXX, **close early** to avoid max loss. Take 50% profit target.

---

**STRATEGY EXECUTION CHECKLIST:**

✅ **Entry Criteria Met:**
- [ ] IV environment matches strategy (High IV for selling, Low IV for buying)
- [ ] Directional bias confirmed by [technicals / max pain / P/C ratio]
- [ ] Position sizing: Risk <2% of account on this trade
- [ ] Greeks understood: Know your Theta/Vega/Gamma exposure

✅ **Exit Plan Defined:**
- [ ] **Profit Target:** Close at [50% profit / $X.XX target / specific stock price]
- [ ] **Stop Loss:** Close if loss exceeds $XXX or stock breaks [support/resistance]
- [ ] **Time Stop:** Close if [X days pass with no movement / 7 days before expiry]

✅ **Risk Management:**
- [ ] Max loss is acceptable ($XXX = X% of account)
- [ ] No overlapping positions that increase correlation risk
- [ ] Expiration is far enough for thesis to play out (>XX days for buyers)

**McMillan's Final Rule:** "Never enter an options trade without knowing your exit plan for BOTH profit and loss scenarios. Hope is not a strategy."

---

**📊 MCMILLAN STRATEGY SCORE: XX/100**

**Components:**
- **IV Environment Match:** XX/30 pts (Strategy aligns with volatility regime)
- **Directional Alignment:** XX/25 pts (Bias confirmed by multiple factors)
- **Risk/Reward:** XX/25 pts (Favorable probability of profit)
- **Timing:** XX/20 pts (Sufficient time for thesis, no Theta burn issues)

[If Score ≥75]:
✅ **HIGH CONVICTION - Excellent Options Setup**
All factors align - IV environment, direction, sentiment, and Greeks favor this strategy. This is a **high-probability trade** per McMillan's framework.

[If Score 50-74]:
⚠️ **MODERATE CONVICTION - Acceptable Setup with Caveats**
Some factors align, but [IV environment / directional bias / sentiment] creates headwinds. Reduce position size or wait for better setup.

[If Score <50]:
❌ **LOW CONVICTION - AVOID or WAIT**
Too many factors misaligned. [High IV but buying premium / Low IV but selling premium / Conflicting signals]. **Do NOT force the trade** - wait for better opportunity.

---

**🎓 KEY TAKEAWAY:**

McMillan's framework teaches us: **"Match your strategy to market conditions, not your emotions."**

- **High IV?** Sell premium (Iron Condors, Credit Spreads)
- **Low IV?** Buy premium (Long Calls/Puts, Debit Spreads)
- **Strong direction + Catalyst?** Use directional strategies
- **No clear direction?** Use neutral strategies (Iron Condor, Calendar Spread)

**Your options strategy is NOT about predicting the future - it's about positioning yourself to profit from the CURRENT volatility environment while managing risk.**

---

### 6B. 🎯 OPTIMAL OPTIONS STRATEGY (Risk-Managed Trade Setup)

**Purpose:** Provides a SPECIFIC, actionable options trade with defined risk. All strategies use SPREADS for defined risk (no naked options).

#### Strategy Selection (McMillan Matrix Applied)

**Market Conditions:** `[analyze_options_mcmillan]`
- **IV Rank:** XX% → [HIGH (>50%) = SELL premium / LOW (<30%) = BUY premium]
- **Direction:** [LONG/SHORT] from Al Brooks + Dalio analysis
- **Risk Tolerance:** CONSERVATIVE (always defined risk)

**📊 STRATEGY SELECTION MATRIX:**

| IV Environment | BULLISH Direction | BEARISH Direction |
|----------------|-------------------|-------------------|
| **LOW IV (<30%)** | ✅ **Bull Call Debit Spread** | ✅ **Bear Put Debit Spread** |
| **MEDIUM IV (30-50%)** | Bull Call Debit Spread | Bear Put Debit Spread |
| **HIGH IV (>50%)** | ✅ **Bull Put Credit Spread** | ✅ **Bear Call Credit Spread** |

**Current Selection:** IV [XX%] + Direction [LONG/SHORT] = **[SELECTED STRATEGY]**

---

#### 🎯 RECOMMENDED TRADE SETUP

**Strategy:** [Bull Call Spread / Bear Put Spread / Bull Put Credit Spread / Bear Call Credit Spread]

**Why This Strategy:**
1. **IV Environment:** [LOW/HIGH] → [BUY/SELL] premium is optimal
2. **Direction:** [LONG/SHORT] → [bullish/bearish] strategy aligns
3. **Risk Profile:** DEFINED RISK (max loss = spread width - credit OR debit paid)

**📊 TRADE STRUCTURE:**

| Leg | Action | Strike | Expiry | Delta | Premium |
|-----|--------|--------|--------|-------|---------|
| **Leg 1** | [BUY/SELL] | $XXX [CALL/PUT] | [Date] | X.XX | $X.XX |
| **Leg 2** | [BUY/SELL] | $XXX [CALL/PUT] | [Date] | X.XX | $X.XX |
| **Net** | [DEBIT/CREDIT] | - | - | - | **$X.XX** |

**📊 RISK/REWARD ANALYSIS:**

| Metric | Value | Calculation |
|--------|-------|-------------|
| **Max Risk** | **$XXX** | [Debit paid OR Spread width - credit] |
| **Max Profit** | **$XXX** | [Spread width - debit OR credit received] |
| **Break-Even** | **$XXX.XX** | [Strike +/- net debit/credit] |
| **Risk/Reward** | **1:X.X** | Max Profit / Max Risk |
| **Probability of Profit** | **XX%** | Based on short strike delta |

**📊 POSITION SIZING (1% Account Risk Rule):**

| Account Size | Max Risk (1%) | Max Contracts | Capital Required |
|--------------|---------------|---------------|------------------|
| $10,000 | $100 | X contracts | $XXX |
| $25,000 | $250 | X contracts | $XXX |
| $50,000 | $500 | X contracts | $XXX |
| $100,000 | $1,000 | X contracts | $XXX |

**Formula:** Max Contracts = (Account × 1%) / (Max Risk per Spread)

---

#### Exit Rules (Discipline = Profit)

**📊 EXIT STRATEGY:**

| Exit Condition | Action | Reason |
|----------------|--------|--------|
| **Profit Target** | Close at 50% max profit | Lock in gains, don't get greedy |
| **Stop Loss** | Close at 100% of max loss | [For credits: 2x credit received] |
| **Time Stop** | Close at 21 DTE | Gamma risk increases exponentially |
| **Direction Change** | Close immediately | Al Brooks flips Always-In |
| **IV Crush** | Close after catalyst | Vol drops = spread value changes |

**Adjustment Rules:**
- **If underlying moves against you:** DO NOT add to losing position
- **If underlying near short strike:** Consider rolling out in time
- **If IV spikes unexpectedly:** Debit spreads benefit, credit spreads hurt

---

#### Greeks Management

**📊 POSITION GREEKS:**

| Greek | Current Value | Target Range | Action if Outside |
|-------|---------------|--------------|-------------------|
| **Delta** | +/- X.XX | -0.30 to +0.30 | Reduce position or hedge |
| **Theta** | +/- $X.XX | Positive for credits | Monitor daily |
| **Vega** | +/- $X.XX | Match IV outlook | Long vega in low IV |
| **Gamma** | X.XXXX | < 0.05 | Close near expiry |

**Greeks Interpretation:**
- **Delta:** Your directional exposure - keep small to limit directional risk
- **Theta:** Time decay - positive theta means you profit each day
- **Vega:** IV sensitivity - long vega profits from vol expansion
- **Gamma:** Delta change rate - high gamma near expiry = dangerous

---

#### Trade Checklist (Before Execution)

**✅ PRE-TRADE CHECKLIST:**

- [ ] IV Rank checked → [LOW/HIGH] environment identified
- [ ] Direction confirmed → Al Brooks + Dalio aligned
- [ ] Spread width defined → Max risk calculated
- [ ] Position size calculated → 1% account risk rule applied
- [ ] Expiry selected → 30-45 DTE for optimal theta
- [ ] Exit rules written → Profit target + stop loss defined
- [ ] No earnings within expiry → Binary risk avoided (unless intentional)

**⚠️ DO NOT TRADE IF:**
- [ ] IV Rank and direction suggest conflicting strategies
- [ ] Position size exceeds 1% account risk
- [ ] Earnings within 7 days of expiry (gamma risk)
- [ ] Direction conflict detected (Section 1B warning)

---

**Tools:** `analyze_options_mcmillan()`, `get_options()`, `get_questrade_option_quotes()`

---

### 6C. 📊 POSITION MANAGEMENT (Phase 4 - NEW) ⭐

**Purpose:** For EXISTING options positions - provides daily monitoring and management recommendations based on TastyTrade + McMillan methodology.

**⚠️ Note:** This section only applies if you ALREADY HAVE an options position open. For NEW positions, use Section 6B above.

---

#### Position Management Framework

The system automatically evaluates your position against 5 critical management rules:

**📊 MANAGEMENT PRIORITY (Institutional Rules):**

| Priority | Check | Trigger | Action | Urgency |
|----------|-------|---------|--------|---------|
| **1** | 50% Profit Target | P&L ≥ 50% max profit | CLOSE | IMMEDIATE |
| **2** | 21 DTE Management | DTE ≤ 21 days | CLOSE or ROLL | WITHIN_3_DAYS |
| **3** | Direction Change | Brooks Always-In flips | CLOSE | IMMEDIATE |
| **4** | Tested Position | Price breaches short strike + DTE ≤ 7 | CLOSE | IMMEDIATE |
| **5** | Earnings Proximity | Earnings < 7 days | CLOSE | IMMEDIATE |

**Why This Order:**
1. Take profits early (88% win rate at 50% vs 52% at expiration)
2. Avoid gamma risk acceleration after 21 DTE
3. Exit invalidated thesis immediately
4. Manage assignment risk in danger zone
5. Avoid IV crush and binary risk

---

#### How to Use Position Management

**Daily Check (For Each Options Position):**

```python
# Check your position
evaluate_options_position_management(
    symbol="AAPL",
    strategy="IRON_CONDOR",          # or CREDIT_SPREAD, DEBIT_SPREAD, etc.
    entry_date="2026-01-15",         # When you entered
    expiration="2026-02-21",         # Options expiry
    entry_credit=630.00,             # Credit collected (for credit spreads)
    current_value=315.00,            # Current position value
    entry_direction="NEUTRAL",       # LONG/SHORT/NEUTRAL
    legs=[                           # Position structure
        {"type": "CALL", "strike": 252, "action": "SELL", "quantity": 2},
        {"type": "CALL", "strike": 257, "action": "BUY", "quantity": 2},
        {"type": "PUT", "strike": 204, "action": "SELL", "quantity": 2},
        {"type": "PUT", "strike": 199, "action": "BUY", "quantity": 2}
    ]
)
```

**Response Format:**

```json
{
  "action": "CLOSE",
  "reason": "✅ 50% PROFIT TARGET HIT (50.0% of max profit)",
  "urgency": "IMMEDIATE",

  "profit_status": {
    "current_pnl": 315.00,
    "current_pnl_pct": 50.0,
    "profit_target_hit": true,
    "days_in_trade": 10
  },

  "dte_status": {
    "days_to_expiration": 30,
    "gamma_risk_level": "LOW"
  },

  "recommendation": "Close position now. You've captured 50.0% of max profit..."
}
```

---

#### Management Action Codes

**📊 ACTION TYPES:**

| Action | Meaning | When Applied |
|--------|---------|--------------|
| **HOLD** | Position healthy, continue monitoring | No triggers hit |
| **CLOSE** | Exit position now | Profit target, direction flip, assignment risk |
| **ROLL** | Move to next expiration | 21 DTE + losing position |
| **ADJUST** | Modify strikes | Advanced management (manual) |

**📊 URGENCY LEVELS:**

| Urgency | Timeframe | Examples |
|---------|-----------|----------|
| **IMMEDIATE** | Today | 50% profit, direction flip, high assignment risk |
| **WITHIN_3_DAYS** | This week | 21 DTE threshold, moderate gamma risk |
| **MONITOR** | No action needed | Continue daily checks |

---

#### Example Management Scenarios

**Scenario 1: 50% Profit Target Hit**

```
Position: AAPL Iron Condor
Entry Credit: $630
Current Value: $315
P&L: $315 (50%)
DTE: 30

✅ ACTION: CLOSE (IMMEDIATE)
Reason: 50% profit target hit
Recommendation: Close now - TastyTrade shows 88% win rate at 50%
                vs 52% if holding to expiration.
```

**Scenario 2: 21 DTE with Profit**

```
Position: TSLA Bull Put Spread
Entry Credit: $400
Current Value: $320
P&L: $80 (20% profit)
DTE: 18

📅 ACTION: CLOSE (WITHIN_3_DAYS)
Reason: 21 DTE threshold + profitable
Recommendation: Close to lock gains before gamma risk accelerates.
```

**Scenario 3: 21 DTE with Loss**

```
Position: MSFT Credit Spread
Entry Credit: $500
Current Value: $575
P&L: -$75 (-15%)
DTE: 19

🔄 ACTION: ROLL (WITHIN_3_DAYS)
Reason: 21 DTE threshold + losing position
Recommendation: Roll to Mar 2026 expiration for additional credit.
                Extends duration and may recover loss.
```

**Scenario 4: Direction Change**

```
Position: NVDA Long Call Spread
Entry Direction: LONG
Current Direction: SHORT (Brooks flipped)
P&L: -$20

🔄 ACTION: CLOSE (IMMEDIATE)
Reason: Brooks Always-In flipped from LONG → SHORT
Recommendation: EXIT NOW - Your thesis is invalidated.
```

**Scenario 5: Tested Position (High Assignment Risk)**

```
Position: SPY Iron Condor
Short Call Strike: $580
Current Price: $609 (5% ITM)
DTE: 6

⚠️ ACTION: CLOSE (IMMEDIATE)
Reason: High assignment risk + DTE ≤ 7
Recommendation: Close to avoid assignment at $580 strike.
```

---

#### Portfolio Greeks Dashboard

**Use Case:** Monitor aggregate portfolio risk across ALL options positions

```python
# Check total portfolio risk
get_portfolio_greeks_dashboard()
```

**📊 EXAMPLE OUTPUT:**

```
Total Delta: +142.3         (Bullish directional bias)
Total Theta: +$12.45        (Collecting $12.45/day in time decay)
Total Vega: -156.8          (Want IV to decrease - short vega)
Total Gamma: -2.34          (Short gamma - need hedging near strikes)

Daily Theta Income: $12.45
10-Point IV Impact: -$1,568  (Lose $1,568 if IV increases 10 points)

Risk Assessment:
  Delta Exposure: BULLISH (>+50 delta)
  Theta Position: LONG_THETA (time decay working for you)
  Vega Position: SHORT_VEGA (vulnerable to IV expansion)
  Gamma Position: SHORT_GAMMA (hedge as price approaches strikes)

Recommendations:
  ⚠️ Short gamma position - hedge if price approaches short strikes
  ✅ Positive theta - time decay is in your favor ($12.45/day)
  ⚠️ Short vega - vulnerable to IV spike events
```

**Delta Exposure Guide:**
- `< -50`: BEARISH portfolio (net short)
- `-50 to +50`: NEUTRAL (balanced)
- `> +50`: BULLISH portfolio (net long)

**Theta Position:**
- `LONG_THETA`: Collecting premium (credit spreads, iron condors)
- `SHORT_THETA`: Paying for time (debit spreads, long options)

**Vega Position:**
- `LONG_VEGA`: Profit from IV increase (long options)
- `SHORT_VEGA`: Profit from IV decrease (short premium)

**Gamma Position:**
- `LONG_GAMMA`: Delta increases as price moves favorably
- `SHORT_GAMMA`: Delta works against you (credit spreads)

---

#### Position Management Tools

**📊 MCP TOOLS:**

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `evaluate_options_position_management()` | Evaluate single position | Daily check on each position |
| `get_portfolio_greeks_dashboard()` | Portfolio-level risk | Weekly portfolio review |

**Reference:**
- TastyTrade: "Manage Winners at 50% of Max Profit" (88% win rate)
- McMillan: "Options as a Strategic Investment", Chapter 36 (Position Management)

---

**⚠️ IMPORTANT NOTES:**

1. **NO Stop Losses on Credit Spreads** - Research shows stops reduce profitability (TastyTrade). Manage at 21 DTE instead.

2. **Priority Matters** - The system checks in order (50% profit → 21 DTE → Direction → Tested → Earnings). First trigger wins.

3. **Daily Monitoring** - Check positions DAILY using `evaluate_options_position_management()`.

4. **Portfolio Greeks** - Check weekly to ensure portfolio-level risk is acceptable.

5. **Trust the System** - These rules are backed by institutional research (TastyTrade 88% win rate at 50% profit target).

---

### 7. CATALYST VERIFICATION (Phase 2 - 13.4%) 🚨 WITH VERIFICATION SYSTEM

**Note:** Catalyst weight reduced from 15.2% to 13.4% to accommodate McMillan Options Strategy (17.9%)

**🚨 VERIFICATION SYSTEM (Dec 2025) - REAL MONEY PROTECTION:**

| Metric | Value | Status |
|--------|-------|--------|
| **Verification Rate** | XX% | [≥50% OK / <50% BLOCKED] |
| **High Confidence** | X/X catalysts | [Credible sources] |
| **Requires Manual** | X catalysts | [⚠️ VERIFY BEFORE TRADING] |
| **Trade Allowed** | [TRUE/FALSE] | [detect_catalyst_strength] |

**✅ VERIFIED CATALYSTS:** [detect_catalyst_strength.verified_catalysts]
| Type | Description | Confidence | Method |
|------|-------------|------------|--------|
| EARNINGS | Earnings on YYYY-MM-DD | HIGH | Company IR via API |
| NEWS | "[Headline]" | HIGH | Credible source (Reuters) |
| INSIDER | Insider buying detected | HIGH | SEC Filing via API |

**⚠️ UNVERIFIED CATALYSTS:** [detect_catalyst_strength.unverified_catalysts]
| Type | Warning | Action Required |
|------|---------|-----------------|
| NEWS | OLD NEWS (X days ago) | DO NOT TRADE - Already priced in |
| INSIDER | Selling context unknown | Search SEC EDGAR for Form 4 |

**Primary Catalyst:**
- Event: [Earnings / Product Launch / Partnership]
- Date: YYYY-MM-DD (X days away)
- Expected impact: [High/Medium/Low]
- **Verification Status:** [VERIFIED HIGH / VERIFIED MEDIUM / UNVERIFIED]

**Catalyst Details:**
- Earnings estimate: $X.XX vs $X.XX prior
- Revenue estimate: $XXB (+XX% YoY)
- Historical beat rate: XX% (last 4 quarters)
- **10b5-1 Check:** [Not applicable / Pre-planned sale detected / Discretionary selling]

**Secondary Catalysts:**
- [List other upcoming events < 30 days]

**News Sentiment:** [detect_catalyst_strength.news_sentiment]
- Sentiment: [BULLISH/BEARISH/NEUTRAL/MIXED]
- Recent headlines: X bullish, X bearish (last 3 days only)

**Tools:** `detect_catalyst_strength()` ⭐ MANDATORY, `get_nasdaq_earnings_calendar()`, `get_ticker_data()`

---

### 8. MACRO & SECTOR CONTEXT (Phase 7 - 5.3%) ⭐

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

### 9. FEATURE IMPORTANCE ANALYSIS (Phase 6 - 5.4% of 17.9%)

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

### 10. ML-ENHANCED ANALYSIS (Phase 6A - 9.8% of 17.9% Technical) ⭐ MANDATORY

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

### 11. HISTORICAL CONFIRMATION (Phase 9 - 0% Weight) ⚠️ MANDATORY

**⚠️ CRITICAL:** Confirmation only, NOT weighted in final score

**⚠️ CRITICAL:** Use ACTUAL Trading Plan targets from Section 11, NOT hardcoded values!

**Call with dynamic targets from YOUR Trading Plan:**
```python
# Get targets from YOUR Trading Plan (Section 11)
# Example: If PT1 = 3.6%, PT2 = 5.6%, holding = 10 days
find_similar_historical_setups(
    ticker="XXXX",
    target_return_pct=3.6,      # Use YOUR PT1 or PT2 from Trading Plan
    holding_period_days=10,     # Use YOUR holding period from Trading Plan
    direction="LONG"            # Use YOUR direction from Trading Plan
)
```

**Similar Historical Setups (2-year lookback):**

**📊 Trading Plan Target:** ← MUST match YOUR Trading Plan!
- **Direction:** [LONG/SHORT]
- **Target Return:** X.X%
- **Holding Period:** XX trading days

**📊 Results Summary:**
- **Similar Setups Found:** XX setups
- **Avg Achievement:** XX.X% ([STRONG/MODERATE/WEAK])
- **Hit Target Rate:** XX% (XX/XX setups)
- **Success Rate (10-day):** XX.X% profitable
- **Average Return:** +X.X%
- **Risk/Reward:** X.X:1

**📊 Trading Plan Validation (Per Setup):**

| Date | Sim% | Actual | Target | Achieve | Status |
|------|------|--------|--------|---------|--------|
| YYYY-MM-DD | XX.X% | +X.XX% | X.X% | +XXX.X% | ✅ HIT |
| YYYY-MM-DD | XX.X% | +X.XX% | X.X% | +XX.X% | 🟡 PARTIAL |
| YYYY-MM-DD | XX.X% | +X.XX% | X.X% | +XX.X% | 🟠 WEAK |
| YYYY-MM-DD | XX.X% | -X.XX% | X.X% | -XX.X% | ❌ WRONG |
| ... | ... | ... | ... | ... | ... |

**Status Legend:**
- ✅ HIT TARGET (≥100%): Achieved full target or exceeded
- 🟡 PARTIAL (60-99%): Achieved 60-99% of target
- 🟠 WEAK (0-59%): Moved right direction but fell short
- ❌ WRONG WAY (<0%): Moved opposite to trade direction

**📊 Achievement Distribution:**

| Category | Count | Rate | Interpretation |
|----------|-------|------|----------------|
| STRONG (≥80%) | XX | XX% | Achieved 80%+ of target |
| MODERATE (60-79%) | XX | XX% | Achieved 60-79% of target |
| WEAK (0-59%) | XX | XX% | Right direction, fell short |
| NEGATIVE (<0%) | XX | XX% | Wrong direction |

**📈 Statistical Validation:**
- **95% Confidence Interval:** [XX%, XX%]
- **P-Value:** X.XXX (✓ significant if <0.05)
- **Sample Size:** XX setups (note count for confidence assessment)
- **Statistical Significance:** ✓ YES / ✗ NO

**Confirmation Status:**

✅ **STRONG** (≥60% hit target OR avg achievement ≥80%): Analysis validated
⚠️ **MODERATE** (40-59% hit target OR avg achievement 60-79%): Partial validation
⚠️ **WEAK** (<40% hit target OR avg achievement <60%): Conflicts with analysis
⚠️ **LIMITED** (low sample count <5): Use with caution

**Comparison to Baseline:**
- ML-Enhanced System: XX.X% accuracy
- Simple Indicators: XX.X% accuracy
- Improvement: +XX.X percentage points

**📌 Bottom Line:** Historical data validates trading plan - XX% of similar setups achieved target

**Tools:** `find_similar_historical_setups(ticker, target_return_pct=YOUR_PT, holding_period_days=YOUR_HOLD, direction=YOUR_DIR)`

**⚠️ REMINDER:** Run Section 11 (Trading Plan) FIRST to determine PT1/PT2/holding period, THEN run this section with those actual values!

---

### 12. TRADE PLAN 🎯 (Phase 10)

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

**WEIGHTED SCORE (Phases 1-8):**

| Phase | Raw Score | Weight | Weighted Points |
|-------|-----------|--------|-----------------|
| Fundamentals (Phase 1) | XX/100 | 17.9% | XX pts |
| Catalysts (Phase 2) | XX/100 | 13.4% | XX pts |
| **McMillan Options (Phase 3)** ⭐ | **XX/100** | **17.9%** | **XX pts** |
| Insider Trading (Phase 4) | XX/100 | 4.5% | XX pts |
| Institutional Holdings (Phase 5) | XX/100 | 4.5% | XX pts |
| Technical Analysis (Phase 6) | XX/100 | 17.9% | XX pts |
| └─ ML Signals (9.8%) | - | - | - |
| └─ Indicators (8.1%) | - | - | - |
| Market Context (Phase 7) | XX/100 | 5.3% | XX pts |
| Al Brooks (Phase 8) | XX% | 17.9% | XX pts |
| **TOTAL** | - | **100.0%** | **XX/100** |

**NOTE:** Weights sum to exactly 100% - NO normalization needed
**NEW:** McMillan Options Strategy now a primary component (17.9% weight)

**PHASE 8: BROOKS PROBABILITY (Context-Informed):**

| Component | Value | Impact |
|-----------|-------|--------|
| Base Pattern | XX% | [High 2/Low 1/etc.] |
| + Fundamentals | +XX% | F-Score X/9 |
| + Catalyst | +XX% | X days to event |
| + **McMillan Options** | +XX% | IV environment + strategy |
| + Insiders | +XX% | $XXM buying |
| + Institutions | +XX% | Accumulation |
| + Technicals | +XX% | RS>70, breakout |
| + Market | +XX% | Greed>70, sector lead |
| **Final Brooks Probability** | **XX%** | **(vs XX% base)** |

**PHASE 9: HISTORICAL CONFIRMATION (0% Weight):**

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

### 13. TECHNICAL INDICATORS (Phase 6B - 8.1% of 17.9% Technical)

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

**Volumetric Liquidity Analysis:** [analyze_volume_tool] ⭐ NEW

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **CVD Trend** | [RISING/FALLING/FLAT] | [Buying/Selling pressure] |
| **CVD Divergence** | [BULLISH/BEARISH/NONE] | [Exhaustion signal if present] |
| **Multi-VWAP Alignment** | [STRONG_BULLISH/BULLISH/MIXED/BEARISH] | Price position vs all VWAPs |
| **VWAP σ Distance** | X.XX | [SUSTAINABLE <1σ / EXTENDED 1-2σ / UNSUSTAINABLE >2σ] |
| **Exhaustion Score** | XX/100 | [NO/LOW/MODERATE/HIGH]_EXHAUSTION |
| **Exhaustion Action** | [PROCEED/FLAG/REDUCE_SIZE/EXCLUDE] | Tiered response |

**CVD Divergence Details:**
- **Signal:** [BULLISH_DIVERGENCE / BEARISH_DIVERGENCE / NONE]
- **Strength:** [STRONG / MODERATE / WEAK]
- **Interpretation:** [Description of what the divergence means for the trade]

**Multi-VWAP Breakdown:**

| VWAP Type | Price | Position | Band |
|-----------|-------|----------|------|
| Rolling (20d) | $XXX.XX | [ABOVE/BELOW] | [Normal/+1σ/+2σ] |
| Anchored | $XXX.XX | [ABOVE/BELOW] | [Normal/+1σ/+2σ] |

**Exhaustion Score Components:**

| Factor | Points | Max | Current Value |
|--------|--------|-----|---------------|
| CVD Divergence | XX | 20 | [Status] |
| RSI Divergence | XX | 20 | [Status] |
| Trend Days | XX | 25 | X days |
| VWAP Extension | XX | 15 | X.XX σ |
| Volume Decline | XX | 20 | X days |
| **TOTAL** | **XX** | **100** | **[Level]** |

**Liquidity Verdict:** [SUPPORTS/OPPOSES] [LONG/SHORT] - [1-2 sentence interpretation]

---

**Dalio Economic Machine Analysis:** [analyze_volume_tool.dalio_metrics] ⭐ NEW

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Dalio Ratio** | X.XXXX | [BULLISH >1.0 = buyers paying more / BEARISH <1.0 = buyers paying less] |
| **Dollar Flow** | $XX.XXM | [ACCUMULATION (positive) / DISTRIBUTION (negative)] |
| **Sustainability** | XX/100, Grade [A-F] | [SUSTAINABLE ≥60 / MODERATING 40-59 / UNSUSTAINABLE <40] |
| **Institutional Activity** | [HIGH/MODERATE/LOW] | [Accumulation/Distribution/Neutral] |

**Gate 2 Enhanced (6 Checks):**

| # | Check | Value | Status |
|---|-------|-------|--------|
| 1 | CVD Aligned | [RISING/FALLING] | [✅/❌] |
| 2 | Not Exhausted | XX/100 | [✅ <50 / ❌ ≥50] |
| 3 | Fresh Direction | [LONG/SHORT] | [✅/❌] |
| 4 | Dalio Ratio | X.XXXX | [✅ ≥1.0 / ❌ <1.0] |
| 5 | Dollar Flow | $XX.XXM | [✅ Positive / ❌ Negative] |
| 6 | Sustainability | XX/100 | [✅ ≥50 / ❌ <50] |

**Checks Passing:** X/6 (Need 5/6 for Gate 2 PASS)

**Dalio Teaching Points:**
- **Dalio Ratio >1.0:** "When spending increases faster than production, prices rise." - Buyers paying more = bullish demand.
- **Positive Dollar Flow:** Net accumulation = institutions building positions = trend has fuel.
- **Sustainability ≥60:** Trend has aligned money flow + volume + momentum = can continue.

**Dalio Verdict:** [ALIGNED/MIXED/DIVERGENT] - [1-2 sentence interpretation]

---

**Volatility:**
- ATR: $X.XX (X.X%)
- ATR-based stop: 2.5x ATR = $X.XX below entry

**Tools:** `analyze_ml_enhanced()`, `calculate_relative_strength_tool()`, `analyze_volume_tool()`, `analyze_volatility_tool()`

---

## QUALITY CHECKLIST

Before publishing:

**Framework Compliance:**
- [ ] All 10 phases executed in order
- [ ] Phase 3 (McMillan Options) ran with correct direction ⭐ NEW
- [ ] Phase 8 (Brooks) ran AFTER Phases 1-7
- [ ] Phase 9 (Historical) ran AFTER Phase 8
- [ ] Historical labeled "CONFIRMATION (0% weight)"
- [ ] Weighted score uses Phases 1-8 only

**Visual Charts:**
- [ ] Price Action Chart included (Section 3)
- [ ] Supply/Demand Zones included (Section 3)
- [ ] Order Blocks included (Section 3)
- [ ] Volumetric Liquidity Analysis included (Section 13)
- [ ] Dalio Economic Machine Analysis included (Section 13) ⭐ NEW
- [ ] McMillan Options Tables included (Section 6)
- [ ] Position Sizing Ladder included (Section 12)
- [ ] Block Order Flow included (Section 5)
- [ ] Peer Comparison Table included (Section 8)
- [ ] ML Analysis Tables included (Section 10)

**Content Quality:**
- [ ] Executive Summary included (Section 1) with quick decision snapshot
- [ ] McMillan Options Strategy included (Section 6) with IV analysis, P/C ratio, strategy ⭐ NEW
- [ ] Macro & Sector Context standalone (Section 8) with peer comparison
- [ ] ML-Enhanced Analysis included (Section 10) with all tables
- [ ] Scenario Analysis included (Section 12) with expected value calculation
- [ ] Brooks probability = context-informed (base + adjustments)
- [ ] Options score included in probability communication ⭐ NEW
- [ ] Historical shown separately (NOT combined with Brooks)
- [ ] Decision matrix applied (now includes Options score column)
- [ ] All support/resistance levels specific ($XXX.XX)
- [ ] Position sizing calculated (ATR-based)
- [ ] Risk/reward ratio calculated (min 2:1)
- [ ] McMillan strategy recommendation included ⭐ NEW

**Probability Communication:**
- [ ] Never claim certainty ("will go up")
- [ ] Always cite sample size (XX setups)
- [ ] Always show statistical significance (p-value)
- [ ] Note sample size for confidence assessment
- [ ] Include McMillan Options Score (XX/100) ⭐ NEW

**No Circular Logic:**
- [ ] Historical NOT used for Brooks probability
- [ ] Historical NOT in weighted score (0%)
- [ ] Clear separation: Analysis → Confirmation → Score
- [ ] Options analysis independent of Brooks probability

**Prediction Tracking:** ⭐ NEW
- [ ] Called `store_trading_prediction()` after report generation
- [ ] Passed full `trading_signal` output to store function
- [ ] Confirmed prediction ID returned

---

## MANDATORY: STORE PREDICTION ⭐ NEW

**After generating the report, you MUST store the prediction for tracking:**

```python
# 1. Generate the trading signal (used throughout report)
signal = generate_trading_signal(ticker="TICKER", direction="LONG")

# 2. MANDATORY: Store for performance tracking
result = store_trading_prediction(
    ticker="TICKER",
    direction="LONG",
    report_type="comprehensive",
    trading_signal=signal
)

# 3. Confirm storage
print(f"✅ Prediction stored: {result['prediction_id']}")
print(f"   Ticker: {result['ticker']} | Direction: {result['direction']}")
print(f"   Entry: ${result['entry_price']}")
```

**Why This Matters:**
- Tracks which analysis components are most accurate
- Generates weekly efficiency reports after 5+ predictions
- Identifies improvement areas automatically
- Validates the 5-gate system performance (Phase 3 Complete - Jan 2026)

---

## OPTIONS WISDOM (Institutional Trading Rules)

**Source:** McMillan "Options as a Strategic Investment" + TastyTrade Research
**Full Reference:** `Institutional Options Trading-Complete Methodology for Algorithmic Systems.md`

### Core Principles

| Rule | Principle | Rationale |
|------|-----------|-----------|
| **1** | **IV Drives Strategy** | HIGH IV → SELL premium; LOW IV → BUY premium |
| **2** | **45 DTE Entry** | Optimal theta decay with manageable gamma |
| **3** | **50% Profit Target** | Close at 50% max profit = 88% win rate |
| **4** | **NO Stop Losses** | On credit spreads - manage at 21 DTE instead |
| **5** | **21 DTE Exit** | Gamma risk explodes - roll or close |
| **6** | **Half-Kelly Sizing** | Kelly/2 reduces volatility, increases longevity |
| **7** | **Earnings Filter** | Skip if earnings < 30 days (IV crush risk) |
| **8** | **Liquidity Rules** | Spread ≤5%, OI ≥100, Volume ≥50 |

### Strategy Matrix (Quick Reference)

| IV Rank | BULLISH | BEARISH |
|---------|---------|---------|
| HIGH (>50%) | Bull Put Credit Spread (16Δ short) | Bear Call Credit Spread (16Δ short) |
| MEDIUM (30-50%) | Bull Call Debit Spread | Bear Put Debit Spread |
| LOW (<30%) | Long Call (ATM) | Long Put (ATM) |

### Trading Plan Generation Rules

**GENERATE full stock + options trading plan ONLY for:**
- ✅ STRONG_BUY (5/5 gates, score ≥70)
- ✅ BUY (4/5 gates, score ≥60)
- ✅ SELL (4/5 gates, score ≥60)
- ✅ STRONG_SELL (5/5 gates, score ≥70)

**DO NOT generate trading plan for:**
- ❌ WATCH (3/5 gates, score 50-59) - No conviction, wait
- ❌ NO_TRADE (<3/5 gates, score <50) - Gates failed, skip

**Rationale:** Trading plans for low-conviction signals encourage overtrading. Only commit capital to high-conviction setups that pass validation gates.

---

**Last Updated:** January 8, 2026
**Version:** 3.1 - Added OPTIONS WISDOM + Trading Plan Rules

---

**Time:** 100 minutes for institutional-grade report with embedded visuals
**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy) + Ray Dalio (Economic Machine) + López de Prado (ML)
