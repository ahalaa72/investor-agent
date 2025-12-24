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

**Greeks (ATM):** [analyze_options_mcmillan.greeks_assessment]
| Greek | Call | Put | Signal |
|-------|------|-----|--------|
| Delta | +X.XX | -X.XX | XX% ITM prob |
| Gamma | X.XXXX | X.XXXX | [HIGH/LOW] |
| Theta | -$X.XX | -$X.XX | [decay rate] |
| Vega | $X.XX | $X.XX | [IV sensitivity] |

- **Greeks Source:** [questrade / yfinance_estimated]
- **Position Risk:** [Theta-positive/negative], [Vega-long/short], [Gamma-stable/explosive]
- **Score: XX/100** → XX.X pts

---

#### 📚 McMILLAN OPTIONS EDUCATIONAL BREAKDOWN (Teach Me!)

**Purpose:** This section translates raw options data into actionable strategy selection. McMillan's methodology from "Options as a Strategic Investment" teaches us to **match strategy to volatility environment** - not just pick random strikes.

**Time allocation:** 15 minutes (detailed teaching)

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
- **CVD:** [RISING/FALLING/FLAT], divergence: [BULLISH/BEARISH/NONE] [analyze_volume_tool.cvd_analysis] ⭐ NEW
- **Exhaustion:** XX/100 ([NO/LOW/MODERATE/HIGH]_EXHAUSTION) [analyze_ml_enhanced.exhaustion] ⭐ NEW
- **Multi-VWAP:** [STRONG_BULLISH/BULLISH/MIXED/BEARISH] alignment [analyze_volume_tool.multi_vwap] ⭐ NEW
- **Al Brooks:** [Pattern], [XX]% adjusted probability [analyze_ml_enhanced.al_brooks]

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

### H. 📚 AL BROOKS EDUCATIONAL BREAKDOWN (Teach Me!)

**This section teaches you PRICE ACTION - not just signals. Real money requires understanding WHY.**

---

#### 1. WHAT THE MARKET IS DOING

**Always-In Direction:** [LONG / SHORT / NEUTRAL] `[analyze_ml_enhanced.al_brooks.always_in_direction]`

**Explanation in Plain English:**

[If LONG]:
The market is currently **'Always-In LONG'**, which means **bulls are in control** and you should look for opportunities to **buy dips** or **pullbacks to support**. Shorting against this trend is dangerous - the market wants to go higher.

[If SHORT]:
The market is currently **'Always-In SHORT'**, which means **bears are in control** and you should look for opportunities to **sell rallies** or **fades to resistance**. Buying against this trend is dangerous - the market wants to go lower.

[If NEUTRAL]:
The market is currently **'Always-In NEUTRAL'**, which means **neither bulls nor bears have control**. This is a **trading range** or **balance area**. Wait for a breakout and trade in the direction of the breakout. Do NOT try to predict the direction - let the market show you.

**Flip Level:** Close [above/below] $XX.XX would flip to [opposite direction]

---

#### 2. THE PATTERN (Setup Type)

**Pattern:** [Pattern Name] - [Pattern Description] `[analyze_ml_enhanced.al_brooks.pattern]`

**What This Pattern Means:**
- [If continuation]: This is a **continuation pattern** - the trend is likely to continue in the same direction. Trade WITH the trend.
- [If reversal]: This is a **reversal pattern** - the trend may be changing. Wait for strong confirmation before entering.

**Al Brooks Teaching:**
[If High 2/Low 2]: This is one of the **highest probability setups** (60%+). Second entries are reliable because the market tested once, pulled back, and is trying again.

[If High 1/Low 1]: This is a **first entry** - moderate probability (50%). Better to wait for a second entry (pullback + re-entry).

[If Breakout Pullback]: Breakouts that test are **more reliable** than parabolic moves. This pullback gives you a better entry with defined risk.

---

#### 3. RECENT PRICE ACTION (Bar Reading)

**Last 5 Bars:** `[analyze_ml_enhanced.al_brooks.bar_reading]`

**What The Bars Tell Us:**
- **Strong bull bars** (close near high) = Buyers in control
- **Strong bear bars** (close near low) = Sellers in control
- **Doji bars** (equal tails) = Indecision, battle between bulls/bears
- **Inside bars** (smaller range) = Consolidation before next move
- **Outside bars** (larger range) = Volatility spike

**Current Bar Interpretation:** Watch how the current bar closes - near the high is bullish, near the low is bearish, middle is neutral.

---

#### 4. WHY THIS MATTERS (Probability + Conviction)

**Base Probability:** XX% ([Pattern Name])

**Context Adjustments:**
- Fundamentals: +/-XX% (F-Score, quality)
- Catalyst: +/-XX% (earnings proximity)
- Options: +/-XX% (McMillan signals)
- Technicals: +/-XX% (RS, trend strength)
- Market: +/-XX% (Fear/Greed, sector)

**FINAL BROOKS PROBABILITY: XX%** `[analyze_ml_enhanced.al_brooks.adjusted_probability]`

**Conviction Assessment:**
- **70%+ = Very Strong:** High-conviction trade, excellent probability
- **60-69% = Strong:** Solid trade, good probability (professional threshold)
- **55-59% = Moderate:** Decent setup, proceed with caution + confirmation
- **50-54% = Marginal:** Coin flip - only trade if other factors strongly support
- **<50% = Weak:** Low probability - avoid until conditions improve

**Al Brooks Standard:** You need 60%+ for swing trades, 55%+ for scalps.
This setup **[MEETS / does NOT meet]** the professional threshold.

---

#### 5. TRAP WARNING (Risk Assessment)

**Trap Risk:** [HIGH / MEDIUM / LOW] `[analyze_ml_enhanced.al_brooks.trap_risk]`

[If HIGH]:
⚠️ **HIGH TRAP RISK** - Significant danger of **false breakout or sudden reversal**.

**Why High Risk:**
- At major support/resistance
- Near round numbers ($100, $50, etc.)
- After parabolic move (exhaustion)

**DO NOT ENTER** until you see:
- Multiple consecutive bars in your direction
- Strong volume on the move
- Clean break above/below trap zone

[If MEDIUM]:
⚠️ **MEDIUM TRAP RISK** - Exercise normal caution.

**Recommended Action:**
- Reduce position size by 50%
- Wait for confirmation bar
- Use tighter stops

[If LOW]:
✅ **LOW TRAP RISK** - Clean setup with minimal false breakout danger.

**Pattern Quality:** Well-formed, market structure supports the move.

**Always Use Stops:** Even low-risk setups can fail. Risk management is mandatory.

---

#### 6. TRADING IMPLICATION (What To Do)

[If Always-In LONG]:
**Since we are Always-In LONG → BUY PULLBACKS**

✅ **DO THIS:**
- Wait for pullback to support (EMA20, VWAP, swing low)
- Enter on strong bull bar closing near high
- Stop below most recent swing low

❌ **DO NOT:**
- Short against the trend (dangerous in LONG market)
- Chase price higher without pullback
- Enter on weak bar or doji

**Position Size:**
- Full position if probability ≥60%
- 75% position if probability 55-59%
- 50% or skip if probability <55%

[If Always-In SHORT]:
**Since we are Always-In SHORT → SELL RALLIES**

✅ **DO THIS:**
- Wait for rally to resistance (EMA20, VWAP, swing high)
- Enter on strong bear bar closing near low
- Stop above most recent swing high

❌ **DO NOT:**
- Buy against the trend (dangerous in SHORT market)
- Chase price lower without rally
- Enter on weak bar or doji

**Position Size:**
- Full position if probability ≥60%
- 75% position if probability 55-59%
- 50% or skip if probability <55%

[If Always-In NEUTRAL]:
**In NEUTRAL market → WAIT FOR BREAKOUT**

✅ **DO THIS:**
- Mark range highs/lows clearly
- Wait for breakout with strong volume
- Trade in direction of breakout AFTER confirmation
- Use tight stops (breakouts can fail)

❌ **DO NOT:**
- Buy at range tops or sell at range bottoms
- Enter before breakout happens
- Trade without confirmation

---

**📚 Al Brooks References:**
- Trading Price Action Trends (Chapter 3: Always-In Direction)
- Trading Price Action Reversals (Chapter 5: High 1/High 2/Low 1/Low 2)
- Trading Price Action Trading Ranges (Chapter 7: Breakouts)

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
**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy)
