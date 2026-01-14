# DAILY PORTFOLIO REPORT TEMPLATE

**Report Structure:** ~200 lines per run | **Time:** 5 min context + 90 sec per position (with 4-gate validation)

**Methodology:** Al Brooks (Price Action) + McMillan (Options Strategy) + Ray Dalio (Economic Machine) + **4-Gate Continuous Validation**

---

## CRITICAL PRINCIPLE: CONTINUOUS VALIDATION

> **"Entry is half the battle. The OTHER half is knowing when the thesis breaks."**
>
> Every position gets 4-GATE VALIDATION on every review.
> - **Gate fails = Action required**
> - **All gates pass = Continue holding**

---

## 6 ENHANCED TOOLS FOR PORTFOLIO VALIDATION

| Tool | Portfolio Purpose | Gate |
|------|------------------|------|
| `detect_catalyst_strength` | Is catalyst still valid? | Gate 1 |
| `analyze_volume_tool` | Has move become exhausted? | Gate 2 |
| `analyze_ml_enhanced` | Does Al Brooks still support? | Gate 3 |
| `calculate_quality_score` | Has quality deteriorated? | Gate 4 |
| `detect_insider_cluster` | Smart money still buying? | Override |
| `analyze_competitors` | Still sector leader? | Override |

---

## 4-GATE PORTFOLIO VALIDATION SYSTEM

| Gate | Entry Question | Portfolio Question | HOLD if | TRIM if | CLOSE if |
|------|----------------|-------------------|---------|---------|----------|
| **1. CATALYST** | Is there one? | Still valid? | Active or next <30d | Exhausted >30d | Failed/Reversed |
| **2. FRESHNESS + DALIO** | Is it fresh? Money flowing? | Exhausted? Money reversing? | 5/6 checks pass | 4/6 checks pass | ≤3/6 checks pass |
| **3. BROOKS** | Good entry? | Still supports? | Always-In aligned | Flipping | Reversed |
| **4. QUALITY** | Is it quality? | Deteriorated? | Grade A-B | Grade C | Grade D-F |

### Portfolio Signal Classification

| Gates Passing | Signal | Action |
|---------------|--------|--------|
| **4/4** | STRONG_HOLD | Continue position, consider ADD on pullback |
| **3/4** | HOLD | Maintain, monitor failed gate closely |
| **2/4** | TRIM | Reduce position 25-50%, raise stops |
| **1/4** | CLOSE 75% | Keep 25% runner only if Gate 3 passes |
| **0/4** | CLOSE IMMEDIATELY | Full exit, no exceptions |

---

## ANALYSIS MODES

| Mode | Scope | Use Case |
|------|-------|----------|
| **Top 5 (Default)** | Top 5 positions by value across ALL accounts | Daily quick review |
| **Full Portfolio** | All positions across all accounts | Weekly deep dive |
| **Single Account** | All positions in one account | Account-specific review |

---

## REPORT FORMAT

```markdown
# DAILY PORTFOLIO REPORT - 4-GATE VALIDATION

**Date:** YYYY-MM-DD | **Time:** HH:MM ET | **Mode:** Top 5 by Value
**Accounts:** All (X accounts, Y positions) | **Methodology:** 4-Gate Continuous Validation

---

## MARKET CONTEXT

| Metric | Value | Signal |
|--------|-------|--------|
| Fear & Greed | XX ([Fear/Neutral/Greed]) | [Caution/Neutral/Favorable] |
| VIX Level | XX.XX | [High Vol/Normal/Low Vol] |
| Market Trend | [Bullish/Bearish/Neutral] | Based on SPY |
| Sector Rotation | [Risk-On/Risk-Off/Mixed] | XLK vs XLU ratio |

**Today's Earnings:** [List stocks reporting today that affect positions]
**Macro Events:** [Fed, CPI, Jobs if applicable]

---

## ACCOUNT SUMMARY

| Metric | Value | Change |
|--------|-------|--------|
| Total Equity (CAD) | $XX,XXX.XX | +/-$X,XXX.XX (+/-X.X%) |
| Cash Available | $XX,XXX.XX | - |
| Buying Power | $XX,XXX.XX | - |
| Open P&L | +/-$X,XXX.XX | [Green/Red] |

---

## PORTFOLIO GATE SUMMARY

| Position | Gate 1 | Gate 2 | Gate 3 | Gate 4 | Signal | Action |
|----------|--------|--------|--------|--------|--------|--------|
| NVDA | ✅ | ✅ | ✅ | ✅ | 4/4 STRONG | HOLD |
| AAPL | ✅ | ⚠️ | ✅ | ✅ | 3/4 HOLD | Monitor G2 |
| TSLA | ❌ | ⚠️ | ✅ | ⚠️ | 2/4 TRIM | Reduce 50% |
| META | ❌ | ❌ | ❌ | ✅ | 1/4 CLOSE | Exit 75% |

**Legend:** ✅ PASS | ⚠️ WARNING | ❌ FAIL

---

## STOCKS

### [SYMBOL] - [Company Name]

**Position:** XX shares @ $XX.XX avg | **Current:** $XX.XX | **P&L:** +/-$XXX (+/-X.X%)

#### 🚦 4-GATE STATUS

| Gate | Status | Details |
|------|--------|---------|
| **1. CATALYST** | ✅/⚠️/❌ | [Catalyst description + status] |
| **2. FRESHNESS** | ✅/⚠️/❌ | Exhaustion XX/100, CVD [aligned/diverging] |
| **3. BROOKS** | ✅/⚠️/❌ | Always-In [LONG/SHORT], Trap [LOW/MED/HIGH] |
| **4. QUALITY** | ✅/⚠️/❌ | Grade [A-F], F-Score X/9, Z-Score X.XX |

**GATE SIGNAL:** [4/4 STRONG_HOLD / 3/4 HOLD / 2/4 TRIM / 1/4 CLOSE 75% / 0/4 CLOSE]

---

#### Gate 1: Catalyst Lifecycle [detect_catalyst_strength] ⭐ ENHANCED (Dec 2025)

| Metric | Value | Status |
|--------|-------|--------|
| Primary Catalyst | [Earnings/Product/FDA/etc.] | [Active/Exhausted/Failed] |
| Catalyst Direction | [BULLISH/BEARISH/NEUTRAL] | Score: XX/100 |
| Catalyst Date | YYYY-MM-DD | [X days ago/away] |
| Next Catalyst | [Description] | In X days |
| Catalyst Stage | [PRE/ACTIVE/POST/EXHAUSTED] | - |

**NEW ENHANCED FIELDS:**
| Field | Value |
|-------|-------|
| News Sentiment | [BULLISH/BEARISH/NEUTRAL] - X headlines (last 3 days) |
| Major Catalysts | [Recent headlines with dates and sources] |
| 10b5-1 Detected | [YES/NO] - Confidence: [HIGH/MEDIUM/LOW] |
| Warnings | [Any items requiring manual verification] |

**Key Enhancements:**
- Web search fetches dated news from Google News RSS
- Only news ≤3 days old counts toward score; today's news = 2x weight
- Insider selling discounted 75% if 10b5-1 pre-planned sale detected

**Catalyst Verdict:** [ACTIVE ✅ / EXHAUSTED ⚠️ / FAILED ❌]

---

#### Gate 2: Freshness + Dalio Economic Machine (6 Checks) [analyze_volume_tool]

**Source:** `analyze_volume_tool(ticker).dalio_metrics`

| # | Check | Value | HOLD | TRIM | CLOSE |
|---|-------|-------|------|------|-------|
| 1 | CVD Aligned | [RISING/FALLING] | RISING/FLAT | FLAT | FALLING |
| 2 | Not Exhausted | XX/100 | <50 | 50-70 | >70 |
| 3 | Fresh Direction | [LONG/SHORT] | Aligned | NEUTRAL | Opposed |
| 4 | **Dalio Ratio** | X.XXXX | ≥1.0 | 0.95-1.0 | <0.95 |
| 5 | **Dollar Flow** | $XX.XXM | Positive | ~0 | Negative |
| 6 | **Sustainability** | XX/100 | ≥50 | 40-49 | <40 |

**Checks Passing:** X/6 (Need 5/6 to PASS)

**Dalio Exit Triggers (CRITICAL):**
- **Dalio Ratio drops below 1.0** → Buyers paying less = weakening demand → TRIM
- **Dollar Flow turns negative** → Net distribution = institutions exiting → TRIM
- **Sustainability drops below 40** → Trend losing momentum = reversal risk → CLOSE

**Freshness Verdict:** [FRESH ✅ (5-6/6) / TIRED ⚠️ (4/6) / EXHAUSTED ❌ (≤3/6)]

---

#### Gate 3: Al Brooks Price Action [analyze_ml_enhanced]

| Metric | Value | Signal |
|--------|-------|--------|
| Always-In Direction | [LONG/SHORT/NEUTRAL] | [Supports/Neutral/Opposes] position |
| Days in Current Direction | X days | Since $XX.XX |
| Pattern | [Bull Flag/Wedge/etc.] | [Continuation/Reversal] |
| Probability | XX% | [Strong >60% / Weak <55%] |
| Trap Risk | [LOW/MEDIUM/HIGH] | [Safe/Caution/Danger] |

**Brooks Verdict:** [SUPPORTS ✅ / NEUTRAL ⚠️ / OPPOSES ❌]

---

#### 📚 AL BROOKS EDUCATIONAL BREAKDOWN

**1. WHAT THE MARKET IS DOING (Always-In Direction)**

**Always-In:** [LONG / SHORT / NEUTRAL]

[If LONG]: **Bulls control.** This means every pullback to support (EMA20, VWAP, prior swing low) is a **buying opportunity**, not a time to panic. If you were forced to be in this market RIGHT NOW, you'd go long - that's what "Always-In LONG" means. The trend is your friend.

[If SHORT]: **Bears control.** Every bounce to resistance is a **shorting opportunity** or exit point for longs. If you were forced to be in this market, you'd go short - that's Always-In SHORT. Fighting this is financial suicide.

[If NEUTRAL]: **Market is in balance.** No edge for bulls or bears. Price is chopping in a range. Wait for breakout with volume before taking new positions.

**Brooks' Teaching:** "When Always-In is LONG, every selloff is a bull flag until proven otherwise. Buy the dips, don't fight the bulls." (Reading Price Charts Bar By Bar, Chapter 5)

**2. THE PATTERN (Continuation vs Reversal)**

**Current Pattern:** [Bull Flag / Bear Flag / Wedge Top / Wedge Bottom / Tight Channel / Breakout / High 2 / Low 1 / etc.]

**What this pattern means:**
- [Bull Flag]: This is a **continuation pattern** - the market is taking a breath before going higher. Look to **buy the pullback to EMA20 or VWAP**. Target new highs.
- [Bear Flag]: Market is pausing before next leg down. **Exit longs or add shorts** on bounce to EMA20/VWAP.
- [Wedge Top]: Climactic buying, bears stepping in. **Warning of reversal** - tighten stops, consider trim.
- [High 2 / Low 1]: Classic reversal signals. High 2 = second attempt to make new highs fails, bears take control. Low 1 = first attempt to make new lows, strong buy signal if holds.

**Brooks' Framework:** "Trade WITH the pattern until you see a CLEAR reversal signal with follow-through. Failed signals become continuation trades." (Price Action Trends Bar by Bar, Chapter 12)

**3. RECENT PRICE ACTION (Bar Reading)**

**Last [5-10] bars show:**
- [Consecutive bull bars with big bodies]: **STRONG BUYING** - don't fight this, join the trend
- [Doji bars, overlapping candles]: **Weak momentum** - market losing conviction, reversal or continuation breakout coming
- [Big reversal bar with follow-through]: **TREND CHANGE** - Always-In direction likely flipping soon
- [Failed breakout, immediate rejection]: **BULL/BEAR TRAP** - smart money fading retail breakout traders

**Key Bar to Watch:** [Describe most important recent bar - e.g., "Yesterday's bear bar closed on its low after testing resistance - strong rejection, bears in control"]

**4. WHY THIS MATTERS FOR YOUR POSITION**

[If Always-In aligned with position]:
✅ **You are trading WITH the trend.** This is the RIGHT side. Your job now is to **hold until Always-In flips** or you hit target. Don't take profits too early - let winners run.

[If Always-In opposed to position]:
❌ **You are fighting the market.** Every day you hold this is a bet that Always-In will flip in your favor. That's HOPE, not strategy. Consider **trimming or exiting** if this persists >3 days.

[If Always-In NEUTRAL]:
⚠️ **Market in balance.** Your position has no trend support. Either wait for Always-In to align, or exit if it flips against you.

**Brooks' Wisdom:** "When you're on the wrong side of Always-In, the best you can hope for is a small loss. Get out and wait for the next setup WITH the trend." (Trading Price Action Trends, Chapter 3)

**5. TRAP WARNING (When NOT to Hold This Position)**

**Current Trap Risk:** [LOW / MEDIUM / HIGH]

[If HIGH]:
🚨 **DANGER:** This setup has **HIGH trap risk**. Signs of trap:
- Always-In direction just flipped (new trend not yet confirmed)
- Pattern is late-stage (wedge, 3rd push, exhaustion gap)
- Volume declining on recent bars (weak follow-through)
- Failed breakout recently (bulls/bears got trapped, now revenge trading)

**What to do:** **Tighten stops immediately** to break-even or small profit. Don't let winner turn into loser. If stop gets hit, accept it - better small win than big loss.

[If MEDIUM]:
⚠️ **CAUTION:** Not a trap yet, but watch for:
- [Specific warning sign - e.g., "If price closes below EMA20 two days in a row"]
- [Specific warning sign - e.g., "If Always-In flips to NEUTRAL or opposes position"]

**What to do:** **Monitor daily.** Have stop loss ready. Don't add to position until trap risk drops to LOW.

[If LOW]:
✅ **SAFE:** This is a good setup with low trap risk. Market showing conviction, follow-through, and alignment. Hold with confidence.

**Brooks' Warning:** "Most traders lose money not from being wrong, but from holding losing positions too long and cutting winners too soon. When trap risk is HIGH, your edge is GONE - exit now." (Price Action Trading Ranges, Chapter 8)

**6. TRADING IMPLICATION (What To Do NOW)**

**Based on Gate 3 Analysis:**

[If SUPPORTS ✅]:
📈 **HOLD with conviction.** Brooks price action confirms your thesis.
- **Action:** Continue holding, trail stop below recent swing low
- **Add Opportunity:** If pullback to EMA20 or VWAP AND Always-In stays aligned, consider adding small (25-50% of current position)
- **Exit Signal:** Wait for Always-In flip or target hit - don't exit on noise

[If NEUTRAL ⚠️]:
⚠️ **HOLD but DON'T add.** Market is in balance, no edge.
- **Action:** Maintain position but tighten stop to protect capital
- **Watch for:** Always-In direction to establish - if flips in your favor, continue hold; if opposes, exit
- **No Adding:** Wait for trend clarity before sizing up

[If OPPOSES ❌]:
🚨 **TRIM or CLOSE.** Brooks says you're on wrong side.
- **Action:** Trim 50% now, close remaining 50% if Always-In stays opposed >3 days
- **Why:** Fighting Always-In direction is -EV (negative expected value). The longer you hold, the more you'll likely lose
- **Exception:** ONLY hold if strong catalyst coming in <7 days that could flip market

**Position Sizing Guidance:**
- **4/4 Gates + Brooks SUPPORTS:** Full position (100%), can add on pullback
- **3/4 Gates + Brooks NEUTRAL:** 75% position, tighten stops
- **2/4 Gates OR Brooks OPPOSES:** 50% position max, consider further trim
- **≤1/4 Gates:** Close position regardless of Brooks

**Time Horizon:**
- **Days in Current Always-In:** [X days]
- **Average Duration:** Most Always-In directions last 5-15 days before flip
- **Implication:** [If X < 5]: Fresh trend, safe to hold. [If X > 10]: Aging trend, prepare for reversal

---

#### Gate 4: Quality Score [calculate_quality_score]

| Metric | Value | Status |
|--------|-------|--------|
| Quality Grade | [A/B/C/D/F] | [Excellent/Good/Fair/Poor/Failing] |
| Quality Score | XX/100 | - |
| F-Score | X/9 | [Strong ≥7 / OK 4-6 / Weak <4] |
| Z-Score | X.XX | [Safe >2.99 / Caution 1.81-2.99 / Distress <1.81] |
| ROE | XX.X% | [Strong >15% / Weak <10%] |
| Debt/Equity | X.XX | [Healthy <1 / Concern 1-2 / Danger >2] |

**Quality Verdict:** [STRONG ✅ / ADEQUATE ⚠️ / DETERIORATING ❌]

---

#### Smart Money Signals [detect_unusual_options_activity + detect_insider_cluster]

| Signal Type | Activity | Interpretation |
|-------------|----------|----------------|
| **Options Flow** | [BULLISH/BEARISH/MIXED/NONE] | [Smart money view] |
| Unusual Activity | [Yes/No] | [Details if yes] |
| IV Rank | XX% | [HIGH >70 / NORMAL / LOW <30] |
| P/C Ratio | X.XX | Contrarian: [BULLISH >1.2 / BEARISH <0.5] |
| **Insider Activity** | [BUYING/SELLING/MIXED/NONE] | Last X days |
| Cluster Strength | [STRONG/MODERATE/WEAK/NONE] | [X buys in 30d] |
| Notable Insiders | [CEO/CFO/Director] | [Names if applicable] |

**Smart Money Override:**
- If STRONG insider buying cluster → Override TRIM to HOLD
- If STRONG options bearish flow → Consider TRIM regardless of gates

---

#### 📚 McMILLAN OPTIONS EDUCATIONAL BREAKDOWN

**1. WHAT THE OPTIONS MARKET IS SAYING**

**Options Flow:** [BULLISH / BEARISH / MIXED / NONE]

[If BULLISH]:
Smart money is **buying calls or selling puts** - they expect upside. This is **confirmation** for long positions. Options traders with big money are positioning for a move higher.

[If BEARISH]:
Smart money is **buying puts or selling calls** - they expect downside. This is a **WARNING** for long positions. Big money is hedging or betting on decline.

[If MIXED]:
Options market is **confused or balanced**. No clear directional bet from smart money. Use other gates for decision.

**McMillan's Insight:** "Options volume often leads stock price. When smart money positions through options before a move, they know something. Pay attention." (Options as a Strategic Investment, Chapter 1)

**2. IV ENVIRONMENT EXPLAINED (High/Low/Normal)**

**IV Rank:** [XX%] - [HIGH >70% / NORMAL 30-70% / LOW <30%]

**What this means for YOUR position:**

[If HIGH IV]:
📈 **EXPENSIVE OPTIONS** - Premium is inflated due to uncertainty/event risk.
- **For existing position:** Good time to SELL covered calls (collect premium while holding stock)
- **For new options:** BAD time to buy - you're overpaying for time value
- **What's causing it:** [Earnings in X days / FDA decision / Macro event]

[If NORMAL IV]:
⚡ **FAIR VALUE** - Options normally priced.
- **For existing position:** Standard options activity, no special opportunity
- **For new options:** Fair pricing for strategies

[If LOW IV]:
📉 **CHEAP OPTIONS** - Good time to BUY options if you expect movement.
- **For existing position:** Consider buying protective puts (cheap insurance)
- **For new options:** GOOD time to buy - low cost, high potential reward if volatility expands
- **Warning:** Low IV can stay low - don't buy options just because they're cheap without a catalyst

**McMillan's Rule:** "Never buy options when IV Rank is >80%. You're paying for volatility that will crush you when it reverts. Never sell naked options when IV <20% - not enough premium to justify risk." (Chapter 28: Volatility)

**3. PUT/CALL RATIO INTERPRETATION**

**P/C Ratio:** [X.XX] - [BULLISH >1.2 / NEUTRAL 0.5-1.2 / BEARISH <0.5]

**Contrarian Signal:**

[If P/C > 1.2]:
🟢 **BULLISH CONTRARIAN** - Excessive put buying = fear/hedging.
- **What it means:** Retail scared, buying puts for protection. Often a bottom signal.
- **McMillan's take:** "When everyone is hedged for downside, the downside often doesn't come. Excessive fear = opportunity." (Chapter 30)

[If P/C < 0.5]:
🔴 **BEARISH CONTRARIAN** - Excessive call buying = greed/speculation.
- **What it means:** Retail greedy, chasing upside with calls. Often a top signal.
- **McMillan's take:** "When calls overwhelm puts, it's retail FOMO. Smart money fades this." (Chapter 30)

[If P/C 0.5-1.2]:
⚪ **NEUTRAL** - Balanced options activity, no extreme sentiment.

**For YOUR position:**
- [If LONG + P/C >1.2]: **BULLISH confirmation** - fear is high, good for longs
- [If LONG + P/C <0.5]: **WARNING** - greed is high, consider trim
- [If SHORT + P/C <0.5]: **BEARISH confirmation** - greed is high, good for shorts

**4. MAX PAIN & PRICE MAGNETISM**

**Max Pain Price:** $[XX.XX] ([+/-X.X% from current])

**What is Max Pain?**
Max Pain is the strike price where **most options expire worthless**, causing maximum loss for options buyers (and maximum profit for options sellers - usually market makers).

**McMillan's Theory:** "Stock price tends to gravitate toward Max Pain as expiration approaches. Market makers hedge their positions by buying/selling stock, creating price pressure toward this level." (Chapter 36)

**For YOUR position:**

[If current price > Max Pain]:
⚠️ **DOWNWARD PULL** - Price may drift down toward $[XX.XX] by expiration ([X days away])
- **Action:** Consider trimming if up significantly, or wait until after expiration for upside continuation

[If current price < Max Pain]:
📈 **UPWARD PULL** - Price may drift up toward $[XX.XX] by expiration
- **Action:** HOLD through expiration for potential upside drift

[If current price ≈ Max Pain]:
🎯 **AT TARGET** - Price likely to stay range-bound until expiration
- **Action:** Don't expect big moves until after expiration

**Reliability:** Max Pain is most reliable within 5 days of expiration and for high-volume stocks. Less reliable for low-liquidity names.

**5. GREEKS BREAKDOWN FOR YOUR TRADE**

**If you own stock (no options):**
- Your position has **Delta = 1.0** (moves $1 for every $1 stock move)
- No Theta decay, no Vega exposure
- Consider: Selling covered calls to collect Theta premium if IV is high

**If considering adding options to position:**

**DELTA:** [Call: +0.XX | Put: -0.XX]
- **What it means:** How much option price moves per $1 stock move
- **Rule:** Delta 0.50 (ATM) = 50% chance of expiring in-the-money
- **For your position:**
  - [If bullish + high IV]: Sell ATM/OTM covered calls (Delta 0.30-0.50) for income
  - [If bullish + low IV]: Buy ATM calls (Delta 0.50) for leverage
  - [If want protection]: Buy OTM puts (Delta 0.20-0.30) for insurance

**GAMMA:** [+X.XX]
- **What it means:** How fast Delta changes as stock moves
- **High Gamma (>0.05):** Explosive near ATM - price swings create big P&L swings
- **Low Gamma (<0.02):** Stable - deep ITM/OTM options don't change much
- **For your position:** High Gamma = high risk/reward. Only use if you're RIGHT on direction.

**THETA:** [-$X.XX per day]
- **What it means:** How much option value you LOSE every day
- **Rule:** Theta accelerates in final 30 days before expiration
- **For your position:**
  - [If buying options]: Minimize Theta by buying >60 days out
  - [If selling options]: Maximize Theta by selling 30-45 days out (sweet spot)

**VEGA:** [+$X.XX per 1% IV change]
- **What it means:** How much option value changes per 1% move in IV
- **High Vega:** Your option is IV-sensitive (good if you expect vol expansion, bad if vol crushes)
- **For your position:**
  - [If IV Rank >70%]: Don't buy options (Vega will crush you when IV drops)
  - [If IV Rank <30%]: Safe to buy options (Vega works in your favor if IV expands)

**McMillan's Greeks Summary:** "Delta tells you direction, Gamma tells you risk, Theta tells you cost, Vega tells you timing. Master these four and you master options." (Chapter 28)

**6. RECOMMENDED STRATEGY & WHY**

**Based on IV Environment + Position:**

[If LONG stock + HIGH IV (>70%)]:
💰 **SELL COVERED CALLS** (Income Strategy)
- **Why:** Collect fat premium while IV is high, reduce cost basis
- **Strike:** [OTM +5-10%] - $[XX.XX] (Delta 0.30)
- **Expiration:** [30-45 days out]
- **Premium:** ~$[X.XX] per contract ([X.X% yield on stock])
- **Risk:** Stock called away if it rallies >10% (acceptable if at profit target)

[If LONG stock + LOW IV (<30%) + BULLISH]:
🚀 **BUY ATM CALLS** (Leverage Strategy)
- **Why:** Cheap leverage to amplify gains with small capital
- **Strike:** [ATM] - $[XX.XX] (Delta 0.50)
- **Expiration:** [60-90 days out] (minimize Theta)
- **Cost:** ~$[X.XX] per contract
- **Risk:** Theta decay if stock doesn't move - only do this if catalyst in <60 days

[If LONG stock + UNCERTAIN + WANT PROTECTION]:
🛡️ **BUY PROTECTIVE PUTS** (Insurance Strategy)
- **Why:** Lock in gains, limit downside, keep upside
- **Strike:** [OTM -5-10%] - $[XX.XX] (Delta 0.20-0.30)
- **Expiration:** [30-60 days out]
- **Cost:** ~$[X.XX] per contract ([X.X% of stock value])
- **Best when:** IV is low (<30%) so insurance is cheap

[If LONG stock + BEARISH OPTIONS FLOW + HIGH IV]:
⚠️ **CONSIDER PROTECTIVE COLLAR**
- **Sell covered call** (collect premium)
- **Buy protective put** (limit downside)
- **Net Cost:** Often free or small credit
- **Why:** Smart money is bearish (options flow), protect yourself while collecting premium

**McMillan's Strategy Selection Matrix:**
- **HIGH IV:** SELL options (covered calls, cash-secured puts)
- **LOW IV:** BUY options (long calls/puts, debit spreads)
- **NORMAL IV:** Stock-only or neutral strategies (iron condors if range-bound)

**For YOUR specific position:**
[Insert specific recommendation based on IV Rank + current gates + position status]

---

#### 📊 OPTIMAL OPTIONS STRATEGY FOR POSITION (Risk-Managed)

**Source:** `analyze_options_mcmillan()` for IV environment

**Strategy Selection Matrix:**

| IV Environment | Position | Optimal Strategy | Max Risk | Rationale |
|----------------|----------|------------------|----------|-----------|
| LOW IV (<30%) | LONG stock | Buy protective puts | Premium paid | Cheap insurance |
| LOW IV (<30%) | LONG stock + leverage | Buy call spread | Premium paid | Cheap upside |
| HIGH IV (>60%) | LONG stock | Sell covered calls | Called away | Collect premium |
| HIGH IV (>60%) | Want protection | Protective collar | Net zero | Free protection |
| MEDIUM (30-60%) | LONG stock | Hold stock OR covered call | Depends | Standard |

**🎯 RECOMMENDED OPTIONS ACTION:**

**Current IV Rank:** {X}% ({LOW/MEDIUM/HIGH})
**Your Position:** {X} shares @ ${X} avg

[If HIGH IV (>60%) + LONG stock]:
💰 **RECOMMENDED: Sell Covered Call**

| Field | Value |
|-------|-------|
| Strike | ${X} (X% OTM) |
| Expiry | 30-45 DTE |
| Premium | ~${X.XX}/share |
| Yield | ~X.X% for X days |
| Max Risk | Called away at strike |

**Exit Rules:**
1. Buy back at 50% profit
2. Roll up/out if stock rallies past strike
3. Let assign if at target price

[If LOW IV (<30%) + Want Protection]:
🛡️ **RECOMMENDED: Buy Protective Put**

| Field | Value |
|-------|-------|
| Strike | ${X} (X% OTM) |
| Expiry | 60-90 DTE |
| Cost | ~${X.XX}/share |
| Protection | Below ${X} |

**Position Sizing:**
- Max Risk per Trade: 1% of portfolio = ${X}
- Max Contracts: {X} based on premium/spread width

---

#### Sector Leadership [analyze_competitors]

| Metric | Value | Status |
|--------|-------|--------|
| Sector | [Technology/Healthcare/etc.] | - |
| Sector Rank | #X of Y peers | [Leader ≤3 / Middle / Laggard] |
| RS vs Sector | XX | [Outperforming/Underperforming] |
| RS vs SPY | XX | [Leader >70 / Laggard <30] |
| Best Competitor | [TICKER] | RS: XX |

**Leadership Verdict:** [LEADER ✅ / MIDDLE ⚠️ / LAGGARD ❌]

**Leadership Override:**
- If LAGGARD and competitor is LEADER → Consider rotation
- If LEADER falling to MIDDLE → Early warning, monitor closely

---

#### Technical Levels

| Level | Price | Distance | Method |
|-------|-------|----------|--------|
| **Stop Loss** | $XX.XX | -X.X% | [Swing Low / ATR / Support] |
| **Raised Stop** | $XX.XX | -X.X% | If 2+ gates fail |
| Support 1 | $XX.XX | -X.X% | - |
| Support 2 | $XX.XX | -X.X% | - |
| Resistance 1 | $XX.XX | +X.X% | - |
| Target | $XX.XX | +X.X% | Original thesis target |

---

#### Order Blocks [analyze_ml_enhanced.order_blocks]

| Block Type | Price | Distance | Age | Impulse | Signal |
|------------|-------|----------|-----|---------|--------|
| 🟢 Bullish OB | $XX.XX | -X.X% | X days | +X.X% | [TESTING/NEAR/FAR] |
| 🔴 Bearish OB | $XX.XX | +X.X% | X days | -X.X% | [TESTING/NEAR/FAR] |

---

### 📊 POSITION ACTION

| Gate | Status | Weight |
|------|--------|--------|
| 1. Catalyst | [PASS/WARN/FAIL] | Critical |
| 2. Freshness | [PASS/WARN/FAIL] | Important |
| 3. Brooks | [PASS/WARN/FAIL] | Critical |
| 4. Quality | [PASS/WARN/FAIL] | Important |
| **Gates Passing** | **X/4** | - |

**Smart Money:** [Supports/Neutral/Opposes]
**Sector Position:** [Leader/Middle/Laggard]

---

**ACTION: [STRONG_HOLD / HOLD / TRIM XX% / CLOSE XX% / CLOSE]**

**Rationale:** [2-3 sentences explaining gate status and action]

---

#### UPDATED TRADING PLAN 🎯

**POSITION STATUS**
- **Entry Price:** $XX.XX
- **Entry Date:** YYYY-MM-DD ([X days ago])
- **Current Price:** $XX.XX
- **Current P&L:** +/-XX.X% (+/-$X,XXX)
- **Position Size:** XXX shares ($XX,XXX value)
- **% of Portfolio:** XX.X%
- **Account:** [Account Type - TFSA/RRSP/Margin]

---

**UPDATED PRICE TARGETS**

```
TARGET 3:    $XX.XX ┈┈┈┈┈┈┈┈ (+XX%) Extension target (Fib 1.618 / Major resistance)
TARGET 2:    $XX.XX ━━━━━━━━ (+XX%) Measured move (Pattern target / Resistance)
TARGET 1:    $XX.XX ━━━━━━━━ (+X.X%) Near-term resistance (Previous high / Round number)
─────────────────────────────────────────────────
CURRENT:     $XX.XX ═════════ (0%)
─────────────────────────────────────────────────
RAISED STOP: $XX.XX ┅┅┅┅┅┅┅┅ (-X.X%) Lock gains ⭐ [If position up >10%]
ORIG STOP:   $XX.XX ━━━━━━━━ (-XX%) Original risk (Swing low / 2.5x ATR)
```

**Target Calculation Method:**
- T1: [Previous swing high / EMA resistance / Round number]
- T2: [Measured move from pattern / Major resistance level]
- T3: [Fibonacci extension 1.618 / Long-term resistance]

---

**STOP LOSS STRATEGY**

[If Position up >10%]:
✅ **RAISE STOP** to lock gains
- **New Stop:** $XX.XX (break-even +X% or small profit)
- **Why:** Position has delivered - protect capital, let remainder run with house money
- **Trigger:** Use trailing stop or ATR-based stop (2x ATR from recent high)

[If Position up 5-10%]:
📈 **TRAIL STOP** to break-even
- **Raised Stop:** $XX.XX (break-even or -X% max risk)
- **Why:** Reduce risk to zero while giving room for continuation

[If Position flat or down]:
⚠️ **HONOR ORIGINAL STOP**
- **Original Stop:** $XX.XX (-XX% max loss)
- **Why:** Thesis not playing out yet - respect risk management
- **If Gate 3 or Gate 1 fails:** Consider tightening stop to -X% (half risk)

**Stop Adjustment Rules:**
- **Never** move stop further from entry (increasing risk)
- **Always** trail stop as position moves in your favor
- **Respect** the stop - no hoping, no waiting "one more day"

---

**TARGET MANAGEMENT**

**Scaling Out Plan:**

[If 4/4 Gates]:
💎 **LET IT RUN** - All systems go, hold full position
- **T1 Hit:** Sell 25-33% (lock some gains)
- **T2 Hit:** Sell another 25-33% (significant profit secured)
- **T3 or Beyond:** Trail final 33-50% with raised stop, let winners run

[If 3/4 Gates]:
⚡ **NORMAL SCALING** - One gate failing, reduce risk gradually
- **T1 Hit:** Sell 33% (take some profits)
- **T2 Hit:** Sell another 33% (majority of position out)
- **Remaining:** Small runner (33%) with tight trail stop

[If 2/4 Gates]:
⚠️ **AGGRESSIVE SCALING** - Multiple failures, prioritize capital preservation
- **T1 Hit:** Sell 50% immediately
- **T2 Hit:** Sell another 25% (75% total out)
- **Remaining:** Tiny runner (25%) with very tight stop

[If ≤1/4 Gates]:
🚨 **CLOSE ON ANY BOUNCE** - Setup broken, exit on strength
- Don't wait for targets - any bounce to resistance is a gift to exit

**Why Scale Out?**
- **Lock gains progressively** - you can't go broke taking profits
- **Reduce risk as position ages** - longer you hold, more likely thesis changes
- **Let final piece run** - capture unexpected extensions while protecting bulk of gains

---

**POSITION SIZING ADJUSTMENT**

**Current Gates: [X/4]**

[If 4/4 gates]:
💡 **CONSIDER ADDING** on pullback to support
- **Add Zone:** $XX.XX - $XX.XX (EMA20/VWAP area, recent support)
- **Add Size:** XX shares (25-50% of current position)
- **Condition:** Must test support AND bounce with volume AND Always-In stays aligned
- **Stop for new piece:** $XX.XX (below support)
- **Why:** All gates pass + pullback to value = high-probability add

[If 3/4 gates]:
📊 **HOLD CURRENT SIZE** - Don't add, don't reduce yet
- **Why:** One gate failing = uncertainty, maintain current exposure
- **Watch:** If gate recovers → consider add. If second gate fails → trim.

[If 2/4 gates]:
⚠️ **TRIM 25-50%**
- **Trim Size:** XX shares (sell 25-50% of position)
- **Execute:** On bounce to resistance or EMA20
- **Why:** Two gates failing = thesis weakening, reduce exposure
- **Keep:** Enough for runner if setup recovers

[If ≤1/4 gates]:
🚨 **CLOSE 75-100%**
- **Why:** Setup is broken, preserve capital for next opportunity
- **Exception:** Keep 25% runner ONLY if Gate 3 (Brooks) still passes and strong catalyst <7 days

**Position Size Rules:**
- **Never** add to losing position (averaging down = recipe for disaster)
- **Only** add to winning position that pulls back to support with all gates passing
- **Always** size adds smaller than original position (pyramid up, not build base)

---

**TIME HORIZON TRACKING**

- **Original Thesis Timeframe:** [Days/Weeks/Months]
- **Days in Position:** [X days] (Entry: YYYY-MM-DD)
- **Expected Hold Duration:** [X-Y days based on catalyst/pattern]
- **Days Until Next Catalyst:** [X days] ([Earnings/FDA/Product Launch])

**Time-Based Exit Rules:**
- If held >30 days with no progress toward T1 → Re-evaluate thesis
- If catalyst passes and position doesn't move → Exit (catalyst failed)
- If Always-In opposed >5 days → Exit (trend against you)

**Psychological Check:**
- [If position green]: Am I getting greedy? Should I take some off?
- [If position red]: Am I hoping? Or do I have conviction based on gates?
- [If position flat]: Is my capital better deployed elsewhere?

---

**EXECUTION CHECKLIST**

**Before ANY Action (Buy/Sell/Add/Trim):**
- [ ] Check all 4 gates - what's current status?
- [ ] Check Smart Money - insiders/options aligned or opposed?
- [ ] Check sector leadership - still a leader or falling to laggard?
- [ ] Check Al Brooks - Always-In direction support or oppose?
- [ ] Check market context - Fear/Greed, VIX, sector rotation
- [ ] Have clear trigger price - not "around here", exact level
- [ ] Know stop loss for ANY new position/add
- [ ] Size position based on gates (4/4 = full, 3/4 = 75%, 2/4 = 50%, ≤1/4 = close)

**Execution Discipline:**
- Use **limit orders** for entries/exits (don't chase with market orders)
- Scale out at **target levels**, not emotional levels
- **Honor stops** - if stop hit, exit immediately (no hoping)
- **Trade size** matches conviction (gates passing = size up, gates failing = size down)

---

**If TRIM/CLOSE:**
- Trigger: [Price level or condition]
- Execute: [Limit/Market at X price]
- Retain: [X% for runner if applicable]

---

[Repeat for each STOCK position]

---

## ETFs

### [ETF SYMBOL] - [ETF Name]

**Position:** XX shares @ $XX.XX avg | **Current:** $XX.XX | **P&L:** +/-$XXX (+/-X.X%)

#### 🚦 GATE STATUS (Simplified for ETFs)

| Gate | Status | Details |
|------|--------|---------|
| **2. FRESHNESS** | ✅/⚠️/❌ | Exhaustion XX/100 |
| **3. BROOKS** | ✅/⚠️/❌ | Always-In [LONG/SHORT] |

*Note: ETFs skip Gate 1 (Catalyst) and Gate 4 (Quality) - use market context instead*

#### Technical Analysis [analyze_ml_enhanced]

| Metric | Value | Signal |
|--------|-------|--------|
| Always-In | [LONG/SHORT] | Current trend |
| RSI | XX.X | [Overbought/Neutral/Oversold] |
| RS vs SPY | XX | [Leader/Laggard] |
| Pattern | [Description] | Setup quality |
| Trap Risk | [LOW/MEDIUM/HIGH] | Reversal risk |

#### Volume Analysis [analyze_volume_tool]

| Metric | Value | Signal |
|--------|-------|--------|
| Exhaustion Score | XX/100 | [Fresh/Tired/Exhausted] |
| CVD Trend | [RISING/FALLING] | [Aligned/Diverging] |

#### Options (if liquid) [analyze_options_mcmillan]

| Metric | Value | Signal |
|--------|-------|--------|
| IV Rank | XX% | [HIGH/NORMAL/LOW] |
| P/C Ratio | X.XX | [BULLISH/NEUTRAL/BEARISH] |
| Smart Money | [BULLISH/BEARISH/MIXED] | Options flow |

---

**ACTION: [HOLD / ADD / TRIM / CLOSE]**

**Rationale:** [1-2 sentence explanation]

---

[Repeat for each ETF position]

---

## MUTUAL FUNDS (Summary Only)

| Symbol | Shares | Value | P&L | P&L % |
|--------|--------|-------|-----|-------|
| VFIAX | XXX | $XX,XXX | +$X,XXX | +X.X% |
| FXAIX | XXX | $XX,XXX | +$X,XXX | +X.X% |

*Mutual funds: Long-term holds, no daily gate validation required*
*Full analysis available: "analyze my mutual funds"*

---

## GATE FAILURE SUMMARY

### Positions with Failed Gates

| Position | Failed Gate | Failure Reason | Days Failed | Action Required |
|----------|-------------|----------------|-------------|-----------------|
| TSLA | Gate 1 | Catalyst exhausted 45d ago | 15 | TRIM 50% |
| META | Gate 2, 3 | Exhaustion 72, Brooks SHORT | 3 | CLOSE 75% |

### Gate Failure Trends

| Position | Last Week | This Week | Trend |
|----------|-----------|-----------|-------|
| NVDA | 4/4 | 4/4 | Stable ✅ |
| AAPL | 4/4 | 3/4 | Declining ⚠️ |
| TSLA | 3/4 | 2/4 | Deteriorating ❌ |

---

## ROTATION OPPORTUNITIES

*Based on `analyze_competitors` showing laggards with better alternatives*

| Current | Rank | Rotate To | Rank | RS Gain | Rationale |
|---------|------|-----------|------|---------|-----------|
| [TICKER] | #7/10 | [TICKER] | #1/10 | +XX pts | Sector leader, fresh breakout |

---

## ACTION SUMMARY

| Symbol | Type | Gates | Signal | Action | Trigger | Notes |
|--------|------|-------|--------|--------|---------|-------|
| NVDA | Stock | 4/4 | STRONG | HOLD | - | All gates pass |
| AAPL | Stock | 3/4 | HOLD | Monitor | G2 fails | Watch exhaustion |
| TSLA | Stock | 2/4 | TRIM | $XXX | 50% | Catalyst gone |
| META | Stock | 1/4 | CLOSE | Market | 75% | Multiple failures |
| SPY | ETF | 2/2 | HOLD | - | Market exposure |

---

## TODAY'S PRIORITIES

1. **[URGENT - CLOSE]** [Position with 0-1 gates passing]
2. **[ACTION - TRIM]** [Position with 2 gates, specific trigger]
3. **[WATCH]** [Position with 3 gates, monitor failing gate]
4. **[OPPORTUNITY]** [Strong position for potential ADD on pullback]

---

## SMART MONEY ALERTS

| Position | Alert Type | Details | Action |
|----------|------------|---------|--------|
| [TICKER] | Insider Cluster | 3 buys in 14 days, $2.1M | Consider override to HOLD |
| [TICKER] | Options Bearish | Large put sweep $500K | Monitor for exit |

---

*Generated by Investor-Agent | Methodology: 4-Gate Continuous Validation*
*Al Brooks Price Action + McMillan Options + Ray Dalio Economic Machine + Smart Money Detection*
*Saved to: /Users/AhmedE/Ahmed/PORTFOLIO_DAILY_YYYY-MM-DD.md*

---

## 🔴 MANDATORY: STORE PREDICTIONS FOR POSITION CHANGES

After generating the portfolio report, store predictions for:
1. **New positions** being recommended (ADD signals)
2. **Major position changes** (TRIM/CLOSE decisions)

### Prediction Storage for Portfolio Actions

```python
# For NEW positions or ADD recommendations with specific entry
store_trading_prediction(
    ticker="XXXX",
    direction="LONG",
    report_type="portfolio",
    trading_signal=<output from generate_trading_signal() for this position>
)
```

### Stored Predictions Table

| Symbol | Action | Direction | Prediction ID | Entry |
|--------|--------|-----------|---------------|-------|
| NVDA | ADD | LONG | abc-123 | $145.50 |
| AAPL | NEW | LONG | xyz-456 | $198.25 |

```

---

## GATE VALIDATION RULES

### Gate 1: Catalyst Lifecycle

| Stage | Days | Status | Action |
|-------|------|--------|--------|
| PRE | -30 to -7 | ✅ ACTIVE | Anticipation building |
| ACTIVE | -7 to +3 | ✅ ACTIVE | Peak interest |
| POST | +3 to +30 | ⚠️ FADING | Continuation or reversal? |
| EXHAUSTED | >+30 | ❌ FAILED | Need new catalyst |

### Gate 2: Exhaustion Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 0-30 | ✅ FRESH | Strong conviction hold |
| 31-49 | ✅ OK | Normal hold |
| 50-59 | ⚠️ TIRED | Tighten stops |
| 60-69 | ⚠️ EXTENDED | Consider trim |
| 70-100 | ❌ EXHAUSTED | Trim or close |

### Gate 3: Al Brooks Rules

| Always-In | Position | Status |
|-----------|----------|--------|
| LONG | LONG | ✅ ALIGNED |
| SHORT | LONG | ❌ OPPOSED |
| NEUTRAL | LONG | ⚠️ WATCH |

| Trap Risk | Action |
|-----------|--------|
| LOW | ✅ Safe to hold |
| MEDIUM | ⚠️ Tighten stops |
| HIGH | ❌ Consider exit |

### Gate 4: Quality Grades

| Grade | Score | F-Score | Z-Score | Action |
|-------|-------|---------|---------|--------|
| A | 80-100 | 7-9 | >2.99 | ✅ Strong hold |
| B | 65-79 | 5-6 | >2.99 | ✅ Hold |
| C | 50-64 | 4-5 | 1.81-2.99 | ⚠️ Monitor |
| D | 35-49 | 2-3 | <1.81 | ❌ Trim |
| F | 0-34 | 0-1 | <1.81 | ❌ Close |

---

## OVERRIDE CONDITIONS

### Smart Money Override (Supersedes Gate Failures)

| Condition | Override Effect |
|-----------|-----------------|
| STRONG insider cluster (3+ buys, $1M+) in 30 days | TRIM → HOLD |
| CEO/CFO buying | +1 gate equivalent |
| STRONG bearish options flow ($500K+ puts) | HOLD → TRIM |
| Heavy institutional selling (13F) | HOLD → TRIM |

### Sector Leadership Override

| Condition | Override Effect |
|-----------|-----------------|
| Position is LAGGARD (#8+ of 10) | Consider rotation regardless of gates |
| Competitor is LEADER with 4/4 gates | Strong rotation candidate |
| Falling from LEADER to MIDDLE | Early warning, tighten stops |

---

## COMBINED ACTION MATRIX

| Gates | Smart Money | Leadership | Final Action |
|-------|-------------|------------|--------------|
| 4/4 | Supports | Leader | **STRONG HOLD / ADD** |
| 4/4 | Neutral | Leader | **HOLD** |
| 4/4 | Opposes | Leader | **HOLD** (monitor SM) |
| 3/4 | Supports | Leader | **HOLD** |
| 3/4 | Neutral | Middle | **HOLD** (monitor gate) |
| 3/4 | Opposes | Laggard | **TRIM 25%** |
| 2/4 | Supports | Leader | **HOLD** (SM override) |
| 2/4 | Neutral | Any | **TRIM 50%** |
| 2/4 | Opposes | Laggard | **CLOSE 75%** |
| 1/4 | Any | Any | **CLOSE 75%** |
| 0/4 | Any | Any | **CLOSE 100%** |

---

## GREEKS QUICK REFERENCE

| Greek | HIGH Value Means | LOW Value Means |
|-------|------------------|-----------------|
| **Delta** | Deep ITM (>0.70) | Far OTM (<0.30) |
| **Gamma** | Explosive near ATM | Stable position |
| **Theta** | Rapid decay | Slow decay |
| **Vega** | IV-sensitive | IV-stable |

---

## ASSET TYPE DETECTION

```python
# Applied automatically during analysis
if quote_type == 'MUTUALFUND':
    # Summary only - no gate validation
    pass
elif quote_type == 'ETF':
    # Simplified: Gate 2 (Freshness) + Gate 3 (Brooks) only
    # Skip Gate 1 (Catalyst) and Gate 4 (Quality)
    pass
else:
    # Full 4-gate validation for stocks
    # All 6 enhanced tools applied
    pass
```

---

## TOOL REFERENCE

| Tool | When to Call | Output Used |
|------|--------------|-------------|
| `detect_catalyst_strength` | Every stock | Gate 1 status |
| `analyze_volume_tool` | Every position | Gate 2 exhaustion |
| `analyze_ml_enhanced` | Every position | Gate 3 Brooks |
| `calculate_quality_score` | Every stock | Gate 4 quality |
| `detect_insider_cluster` | Every stock | Smart Money section |
| `detect_unusual_options_activity` | Every stock | Smart Money section |
| `analyze_competitors` | Every stock | Leadership section |
| `analyze_options_mcmillan` | Liquid options | Options analysis |
| `find_support_resistance` | Every position | Technical levels |

---

## SAVE LOCATIONS

| Report Type | Path |
|-------------|------|
| Daily Portfolio | `/Users/AhmedE/Ahmed/PORTFOLIO_DAILY_YYYY-MM-DD.md` |
| Concise Ticker | `/Users/AhmedE/Ahmed/[TICKER]_CONCISE_YYYY-MM-DD.md` |
| Mutual Fund Analysis | `/Users/AhmedE/Ahmed/MUTUAL_FUND_ANALYSIS_YYYY-MM-DD.md` |

---

## OPTIONS WISDOM (Institutional Trading Rules)

**Source:** McMillan "Options as a Strategic Investment" + TastyTrade Research
**Full Reference:** `Institutional Options Trading-Complete Methodology for Algorithmic Systems.md`

### Key Principles

| Rule | Principle | Rationale |
|------|-----------|-----------|
| **1** | **IV Drives Strategy** | HIGH IV → SELL premium; LOW IV → BUY premium |
| **2** | **45 DTE Entry** | Optimal theta decay with manageable gamma |
| **3** | **50% Profit Target** | Close at 50% max profit = 88% win rate |
| **4** | **NO Stop Losses** | On credit spreads - manage at 21 DTE instead |
| **5** | **Earnings Filter** | Skip if earnings < 30 days (IV crush risk) |
| **6** | **Liquidity Rules** | Spread ≤5%, OI ≥100, Volume ≥50 |

### Portfolio-Specific Options Strategies

| Situation | IV Environment | Strategy |
|-----------|----------------|----------|
| LONG stock + want income | HIGH IV (>50%) | Sell Covered Calls |
| LONG stock + want protection | LOW IV (<30%) | Buy Protective Puts (cheap) |
| LONG stock + free protection | HIGH IV (>50%) | Protective Collar |
| ADD to position | LOW IV (<30%) | Buy Call Spread |

### Trading Plan Rules

**GENERATE options trading plan for:**
- ✅ ADD recommendation (new position with 4/4 gates)
- ✅ Rotation candidate (replacing TRIM/CLOSE)
- ✅ STRONG_HOLD + want to add on pullback

**DO NOT generate options trading plan for:**
- ❌ HOLD (maintain, no new entry)
- ❌ TRIM (reducing, not adding)
- ❌ CLOSE (exiting, not entering)

---

**Last Updated:** January 8, 2026
**Version:** 2.1 - Added OPTIONS WISDOM + Trading Plan Rules
