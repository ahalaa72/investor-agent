# McMillan Options Mastery Guide

> **Source:** Lawrence G. McMillan — *Options as a Strategic Investment* (5th Edition, Prentice Hall Press)
> **Purpose:** Institutional-grade reference for report generators. Strategy selection, volatility framework, position management, and educational content.
> **Strategies:** 18 core strategies organized by IV environment and market outlook — aligned with `options_analysis.py`

---

## 1. VOLATILITY FRAMEWORK

### 1A. The Foundation: Volatility Trades in a Range

**McMillan Ch.36:** *"Volatility almost invariably trades in a range. This is the basic premise of volatility trading."*

Implied volatility is mean-reverting. It will not trend up or down forever. The only exception: material fundamental changes (takeover, major acquisition). This mean-reversion property is the single most exploitable edge in options trading.

**Key Insight:** *"Implied volatility is NOT a good predictor of actual volatility."* The difference between implied and actual swings wildly rather than hovering near zero. This is why volatility trading works — the market consistently misprices future volatility.

### 1B. The Percentile Method (McMillan's Preferred)

**McMillan Ch.39:** *"Compare current composite implied volatility to its own past levels."*

| Percentile | Classification | Action | McMillan Reference |
|-----------|---------------|--------|-------------------|
| 0-10% | CHEAP | Buy premium (straddles, strangles, debit spreads, LEAPS) | Ch.39: "Options in the 10th percentile or less" |
| 10-30% | LOW | Favor buying; calendars acceptable | Ch.39: percentile approach |
| 30-70% | NORMAL | Flexible — match strategy to outlook | Ch.37: strategy selection |
| 70-90% | HIGH | Favor selling; credit spreads, iron condors | Ch.39: "expensive" territory |
| 90-100% | EXPENSIVE | Aggressive premium selling — but CHECK for insider activity first | Ch.39: "90th percentile or higher" |

**Critical Parameters:**
- Use **600 trading days** (~2.4 years) of IV history for percentile calculation
- **Width test:** If IV rises from current low percentile to 50th percentile in one month, will the IV increase equal or exceed time decay? If yes, the range is wide enough to trade
- **LEAPS caveat:** LEAPS IV ranges are much narrower (17%-32%) vs near-term (14%-40%). LEAPS rarely appear "cheap" when compared to all options

### 1C. Implied vs Historical Volatility Comparison

**McMillan Ch.39:** *"This method is inferior to the percentile method."*

McMillan considers this a secondary screen only. Problems:
1. Convergence may not occur in your timeframe
2. Even if convergence occurs, both may converge at the wrong level (you lose money)
3. Does not tell you if implied is high or low in its own range

**If using this method:** Require implied volatility < 80% of EACH of the 10-, 20-, 50-, and 100-day historical volatilities before buying premium.

### 1D. Reading the Volatility Chart

**McMillan Ch.39:** Wait for the **trend of implied volatility to reverse** before entering.

- Do NOT buy volatility into a steep downtrend, even at the 0th percentile. Wait for a "pop" in IV
- Do NOT sell volatility into a steep uptrend. Wait for IV to roll over
- This technique is especially useful for sellers — avoids stepping into insider-driven IV spikes

### 1E. When NOT to Trade Volatility (Safety Rules)

| Warning Sign | Action | McMillan Reference |
|-------------|--------|-------------------|
| Sudden IV spike + volume spike + stock rising | DO NOT SELL — probable insider trading | Ch.36 |
| Known news event (earnings, FDA) causing expensive options | DO NOT SELL — IV is expensive for a reason | Ch.36 |
| Unknown reason for expensive options | DEFER — likely insider knowledge | Ch.36 |
| News is public (poor earnings drove stock down, IV up) | CAN sell after analysis | Ch.36 |
| Options at tiny fractional prices | DO NOT SELL — "pennies in front of steamroller" | Ch.20 |

### 1F. VIX as Market Regime Indicator

**McMillan Ch.41:**

| VIX Level | Regime | Market Implication |
|-----------|--------|-------------------|
| < 10 | EXTREME LOW | Complacent — sharp decline (~1%+) typically within a week |
| 10-15 | LOW | Calm — favor buying premium |
| 15-25 | NORMAL | Balanced — flexible strategy |
| 25-35 | ELEVATED | Fear — contrarian bullish, favor selling premium |
| > 35 | PANIC | Extreme fear — spike peaks are contrarian buy signals |
| > 50 | CRISIS | Severe bearish — but "when the last trader has bought the last put, the market turns" |

**VIX Confirmation Rules:**
- Market declining + VIX NOT rising = temporary decline, protection is cheap
- Market declining + VIX rising = genuinely bearish, respect the move
- Market rising + VIX falling = bullish confirmation
- Market rising + VIX rising = uptrend may be suspect

**VIX moves opposite to the market ~75-80% of the time** on a daily basis.

---

## 2. STRATEGY CATALOG

### 2A. PREMIUM BUYING STRATEGIES (Low IV Environment)

---

#### `long_straddle` — Buy ATM Straddle

**McMillan Ch.18:** *"Buy a call and put at the same strike and expiration."*

**When to Use:** Volatile stock expected to make a large move in either direction. IV in low percentile (0-30%).

**Construction:** Buy 1 ATM call + Buy 1 ATM put, same strike, same expiration.

**Formulas:**
- Cost = Call premium + Put premium
- Upside breakeven = Strike + Total cost
- Downside breakeven = Strike - Total cost
- Max loss = Total cost (only if stock exactly at strike at expiration)

**Selection Criteria:** Use mathematical analysis — assume stock moves up or down by its expected volatility in 60-90 days. Predict both option prices at those levels. Rank straddles by expected percentage profit. 25% probability threshold for upside/downside movement.

**Position Sizing:** Mid-range expirations (2-4 months) tend to have best probabilities. Not LEAPS.

**Follow-Up (CRITICAL — McMillan's Best Technique):**
- **NEVER take small profits.** The strategy depends on infrequent large winners offsetting many small losses
- **Roll the put UP on upside move:** If stock rises to next strike, sell current put, buy put at next higher strike. Reduces max loss without limiting profit potential
- **Roll the call DOWN on downside move:** Mirror image — sell current call, buy call at next lower strike

**Lesson Template:** *"This is a long straddle — McMillan's preferred volatility buying strategy when IV is cheap. You profit from any large move regardless of direction. The key is patience: never take small profits, because one large winner must offset many small losses. Roll the losing side toward the stock to reduce risk while preserving unlimited profit potential."*

---

#### `long_strangle` — Buy OTM Strangle

**McMillan Ch.18:** *"Buy an out-of-the-money put and out-of-the-money call."*

**When to Use:** Cheaper alternative to straddle. Expecting a large move. IV in low percentile.

**Construction:** Buy 1 OTM put + Buy 1 OTM call, different strikes, same expiration.

**Formulas:**
- Cost = Put premium + Call premium
- Upside breakeven = Call strike + Total cost
- Downside breakeven = Put strike - Total cost
- Max loss = Total cost (if stock between the two strikes at expiration — wider loss zone than straddle)

**Warning:** *"Out-of-the-money strangles may appear deceptively cheap but have a high probability of total loss."*

**In-the-Money Alternative:** Buy ITM call + ITM put. More expensive but can never lose entire investment (always worth at least the difference between strikes).

**Lesson Template:** *"This is a long strangle — cheaper than a straddle but with a wider max-loss zone. McMillan warns that OTM strangles appear 'deceptively cheap' but have high probability of total loss. Consider ITM strangles for more conservative positioning."*

---

#### `long_call` / `long_put` — Directional Premium Purchase

**McMillan Ch.3/Ch.16:**

**When to Use:** Strong directional conviction. IV in low percentile. Clear catalyst.

**Put Buying Rules (Ch.16):**
- Never place more than **15% of risk capital** in speculative put buying
- For speculation, **concentrate on in-the-money puts** unless expecting a very substantial decline
- When an ITM put is cheap across expiration months, buy the longest-term put — more time for minimal extra cost

**Lesson Template:** *"Directional option purchase in a low-IV environment. McMillan emphasizes: for puts, concentrate on ITM unless expecting a very large decline. Never commit more than 15% of risk capital to speculative put buying."*

---

#### `debit_spread` — Bull Call Spread / Bear Put Spread

**McMillan Ch.7/Ch.8:**

**When to Use:** Moderate directional conviction. Want to reduce cost vs outright purchase.

**Bull Call Spread:** Buy lower strike call, sell higher strike call. Debit = difference in premiums.
- Max profit = Strike difference - Net debit
- Max loss = Net debit
- Breakeven = Lower strike + Net debit

**Bear Put Spread:** Buy higher strike put, sell lower strike put.
- Max profit = Strike difference - Net debit
- Max loss = Net debit
- Breakeven = Higher strike - Net debit

**McMillan's Assessment:** *"Bull spreads are inferior strategies regardless of distribution."* Under fat-tail distributions (reality), strategies with limited profit potential and unlimited risk equivalents are suboptimal. Debit spreads have limited profit AND limited risk — acceptable but not optimal.

---

#### `calendar_spread` — Sell Near-Term, Buy Longer-Term

**McMillan Ch.9:** *"Sell near-term call, buy longer-term call at the same strike."*

**When to Use:** Neutral to mildly directional. Best established 8-12 weeks before near-term expiration. IV NOT expected to decline.

**Construction:** Sell 1 near-term option + Buy 1 longer-term option, same strike.

**Formulas:**
- Cost = Net debit (longer-term premium - near-term premium)
- Max loss = Net debit
- Max profit = At near-term expiration when stock is at the strike

**CRITICAL Volatility Effect:** Calendar spreads are ANTI-volatility strategies in the short term. As volatility increases, the spread widens (good for holder). As volatility contracts, the spread shrinks (bad).

**Warning:** *"Calendar spreads on volatile stocks look cheap but are traps — if the stock stabilizes, declining volatility may cause a loss greater than the gain from time decay."*

**Follow-Up:**
- Stock breaks down: Usually do nothing. Let short call expire worthless, hope for recovery in long call
- Stock breaks up: Usually do nothing. Both options hold premium in a rally
- **NEVER "leg out" of the spread** — converting to naked option is extremely risky
- Three-month approach: Sell nearest-term, buy longest-term. If near-term expires worthless, sell intermediate against long position

**Lesson Template:** *"Calendar spreads profit from time decay differential, not from directional moves. McMillan warns: calendars on volatile stocks are traps — if the stock calms down, declining IV causes losses that exceed time decay gains. Best used on stocks with stable IV in the normal percentile range."*

---

#### `backspread` — Reverse Ratio Spread

**McMillan Ch.13:** *"Sell calls at a lower strike, buy more calls at a higher strike."*

**When to Use:** Expecting a large move (especially upward). IV in LOW percentile. Best when established for a CREDIT.

**Construction (Call Backspread):** Sell 1 ITM call + Buy 2 OTM calls. Should produce a net credit.

**Key Characteristics:**
- If stock drops below lower strike: profit = initial credit
- Max loss at the purchased call's strike at expiration
- Unlimited upside profit potential
- No naked calls — small investment required

**Delta-Neutral Ratio:** Delta of purchased / Delta of written. Bias slightly bullish since largest profits are upside.

**Rule:** *"Do NOT use this strategy if the longer-term option has a much lower IV than the short-term one. Unlikely to work with LEAPS."*

**Lesson Template:** *"This is a backspread — McMillan's preferred volatility buying strategy when you can establish it for a credit. You profit if the stock makes a big move in either direction (down = keep credit, up = unlimited). Max loss only at the purchased strike at expiration."*

---

### 2B. PREMIUM SELLING STRATEGIES (High IV Environment)

---

#### `covered_call` — Buy Stock + Sell OTM Call

**McMillan Ch.2:** *"The most fundamental and most important option strategy."*

**When to Use:** Mildly bullish. Want income from stock position. IV elevated (makes premium richer).

**Selection Rules:**
- Use the **Total Return Concept**: evaluate return IF exercised (stock called away) AND return IF unchanged
- Select based on desired risk/reward: OTM calls = more upside participation but less protection; ITM calls = more protection but caps upside lower
- **Diversify**: don't put all covered writes in the same strike/expiration

**Follow-Up — Rolling:**
- **Rolling down:** Use technical support levels. Partial roll-down avoids locking in losses while gaining protection
- **Rolling up:** Do NOT roll up unless you can withstand at least a **10% stock price correction**. Prefer rolling for credits when possible
- **Incremental Return Concept:** Roll for credits systematically, locking in profits at each new strike

**Lesson Template:** *"Covered call writing is McMillan's foundational strategy. In elevated IV environments, the premium collected provides meaningful downside protection. Roll down at support levels (partial rolls preserve flexibility), and never roll up unless you can handle a 10% correction."*

---

#### `cash_secured_put` — Sell Put with Cash Collateral

**McMillan Ch.19:** Equivalent profit/loss profile to covered call writing.

**When to Use:** Want to acquire stock at a discount OR collect premium if stock stays above strike.

**Screening Criteria:**
- Reject any put write that does not offer at least **5% downside protection** OR at least **12% annualized return**
- Two ranking lists: (1) highest potential returns, (2) most downside protection

**CRITICAL WARNING (Ch.19):** *"Despite seeming benign, naked put writing can be highly dangerous for two reasons: (1) large losses if stock takes a nasty fall; (2) collateral requirements are small, enabling excessive leverage. ANY stock is subject to crushing decline — do not rely on 'quality' as protection. NEVER leverage your account heavily in naked puts regardless of stock quality."*

**Lesson Template:** *"Cash-secured put writing has the same risk profile as covered calls. McMillan's screening: reject puts offering < 5% downside protection or < 12% annualized return. CRITICAL: never over-leverage — any stock can have a crushing decline regardless of quality."*

---

#### `credit_spread` — Bull Put Spread / Bear Call Spread

**McMillan Ch.8:**

**Bull Put Spread (Credit):** Sell higher strike put, buy lower strike put. Credit received.
- Max profit = Net credit
- Max loss = Strike difference - Net credit
- Breakeven = Higher strike - Net credit

**Bear Call Spread (Credit):** Sell lower strike call, buy higher strike call. Credit received.
- Max profit = Net credit
- Max loss = Strike difference - Net credit
- Breakeven = Lower strike + Net credit

**Key Insight:** *"Less aggressive bear spreads (stock below lower strike) are often better: small credit, but high probability of max profit."* Large-credit spreads where the short option is deep ITM are actually aggressive — you're selling intrinsic value and buying time value, the opposite of sound option philosophy.

**Lesson Template:** *"Credit spreads in high-IV environments capture elevated premium with defined risk. McMillan's key insight: less aggressive spreads (short strike well OTM) have higher probability of max profit. Avoid large-credit spreads where the short option is deep ITM — that reverses sound option philosophy."*

---

#### `iron_condor` — Sell OTM Put Spread + Sell OTM Call Spread

**McMillan Ch.23:** All options OTM, same expiration.

**When to Use:** Neutral outlook, expecting stock to stay in a range. IV elevated.

**Construction:**
- Buy OTM put (lowest strike) — protection
- Sell OTM put (next strike up) — short
- Sell OTM call (next strike down from top) — short
- Buy OTM call (highest strike) — protection

**Formulas:**
- Max profit = Net credit
- Max loss = Greater of (put spread width, call spread width) - Net credit
- Max profit zone: between the two short strikes
- Breakevens: Lower short strike - Credit, Upper short strike + Credit

**CRITICAL Volatility Effect:** Increased volatility harms iron condors in TWO ways: (1) greater probability of breaching short strikes; (2) options become more expensive, causing mark-to-market losses.

**McMillan's Assessment:** *"There are far more attractive strategies in general, especially when the stock market is volatile."*

**Follow-Up Approaches:**
1. **Active:** Close the breached side when stock crosses a short strike. Limits losses but causes more whipsaws
2. **Passive:** Hold to expiration. Requires strict money management: allocate only a portion of capital; only establish condors with 1/3 to 1/2 of allocated capital

**Institutional Construction (from our system):**
- Short strikes at 16-delta (institutional standard)
- Long strikes at 5-delta (protection)
- Target 45 DTE entry
- 50% profit target exit
- Close or roll at 21 DTE

**Lesson Template:** *"Iron condors collect premium from both sides of the market. McMillan warns these have 'great risk' — you can lose 100% of investment. Rising IV hurts you doubly: higher breach probability AND mark-to-market losses. Only allocate 1/3 to 1/2 of capital designated for this strategy. There are 'far more attractive strategies when the market is volatile.'"*

---

#### `short_strangle` — Sell OTM Put + Sell OTM Call (Undefined Risk)

**McMillan Ch.20:**

**When to Use:** Neutral. High IV (90th+ percentile). Wide expected range. Sufficient capital for margin.

**Construction:** Sell OTM put + Sell OTM call, same expiration.

**Formulas:**
- Max profit = Total credit (if stock between both strikes at expiration)
- Breakevens: Put strike - Total credit, Call strike + Total credit
- Max loss: Unlimited in both directions

**Strike Selection:** Probability of stock reaching EITHER strike should be **less than 25%**.

**Index vs Stock:** Index options are the BEST for naked selling; futures next; stocks last (stocks have greatest gap risk).

**Follow-Up (Ranked by McMillan):**
1. **Buy protective option at next strike (BEST):** If stock rises to call strike, buy a call at next higher strike. Limits risk while preserving profit if stock returns
2. **Convert to straddle:** If stock reaches a breakeven, sell a new option at current stock price
3. **Buy back at breakeven points:** Simple but expensive before expiration due to time premium
4. **Do nothing:** Only for very diversified, well-capitalized investors

**Selection Index:** Straddle time value premium / (Stock price x Volatility). Reject straddles worth < 10% of stock price or with < 30 days remaining.

**Lesson Template:** *"Short strangles collect maximum premium in high-IV environments. McMillan's probability rule: each short strike should have < 25% probability of being reached. Prefer index options over stocks (less gap risk). Best follow-up: buy a protective option at the next strike rather than using stop losses."*

---

#### `short_straddle` — Sell ATM Call + ATM Put (Undefined Risk)

**McMillan Ch.20:**

**When to Use:** Strongly neutral. Highest premium collection. Very high IV. Requires sophisticated risk management.

**Construction:** Sell 1 ATM call + Sell 1 ATM put, same strike and expiration.

**Formulas:**
- Max profit = Total credit (only if stock exactly at strike at expiration)
- Profit range: Strike ± Total credit
- Max loss: Unlimited in both directions

**Follow-Up (Best Method):** Buy a protective option at the next strike when the position goes against you. If stock rises to 50, buy the 50 call for protection. Net credit becomes reduced but max loss is now defined.

**Starting with Protection:** Buy OTM call and OTM put at inception. This converts to a butterfly spread — reduced profit but defined risk and significantly lower margin.

**ESP Monitoring:** Calculate Equivalent Stock Position = Quantity x Delta x 100. Adjust by buying stock or options to neutralize.

**Lesson Template:** *"Short straddles maximize premium collection but have unlimited risk in both directions. McMillan's best follow-up: buy a protective option at the next strike when breached — this limits risk while preserving profit if the stock returns. Consider starting with protection (creating a butterfly) for defined risk."*

---

#### `ratio_spread` — Buy Fewer, Sell More

**McMillan Ch.11:** *"Buy fewer calls at a lower strike, sell more calls at a higher strike."*

**When to Use:** Neutral strategy. IV in HIGH percentile (want negative vega). Similar to ratio writing with less downside risk.

**Construction (2:1 example):** Buy 1 call at lower strike, sell 2 calls at higher strike.

**Formulas (2:1 ratio):**
- Max profit = Initial credit + Strike difference (or = Strike difference - Initial debit)
- Upside breakeven = Higher strike + Points of max profit
- If established at a credit: no downside risk at all

**Three Approaches:**
1. **As ratio write substitute:** Buy deep ITM call to simulate stock ownership
2. **Credit spreads only:** Stock below written strike. No downside risk
3. **Delta spread (most sophisticated):** Neutral ratio = Delta of purchased / Delta of written. Reject ratios > 4:1 or < 1.2:1. Reject options selling under $0.50. Limit debit to 1 point per long call

**Follow-Up:**
- **Upside:** Buy more long calls to reduce ratio toward 1:1 (converting to bull spread)
- **Downside:** Roll down the written calls if initial debit was large
- **Delta adjustment:** Recalculate neutral ratio as stock moves. Use ESP to monitor

**Lesson Template:** *"Ratio spreads are McMillan's preferred high-IV neutral strategy — negative vega profits from IV contraction. The delta-neutral approach is most sophisticated: calculate neutral ratio from deltas, reject ratios outside 1.2:1 to 4:1. If established at a credit, there is zero downside risk."*

---

#### `butterfly` — Buy 1 + Sell 2 + Buy 1

**McMillan Ch.10:**

**When to Use:** Neutral. Stock expected to stay near middle strike through expiration. Higher-priced and/or volatile stocks with strikes 10-20 points apart.

**Construction:** Buy 1 call at lowest strike, sell 2 calls at middle strike, buy 1 call at highest strike.

**Formulas (evenly spaced):**
- Cost = Net debit
- Max profit = Strike difference - Net debit
- Downside breakeven = Lowest strike + Net debit
- Upside breakeven = Highest strike - Net debit

**Minimum Attractiveness:** Potential profit should be at least **3x (preferably 4x)** maximum risk.

**Best Construction (Ch.23):** Use calls for the bull spread component, puts for the bear spread component. This avoids selling ITM options that create early exercise risk.

**Follow-Up — "Legging Out" (One Exception):**
- Stock drops sharply: Bear spread portion approaches max profit. Buy back bear spread cheaply (~$0.50), converting to a bull spread with broad upside potential
- Stock rises sharply: Bull spread approaches max value. Close bull spread, converting to a bear spread

**Lesson Template:** *"Butterfly spreads have defined risk and work best when the stock stays near the middle strike. McMillan's minimum attractiveness test: potential profit must be at least 3x maximum risk. The best construction uses calls for the bull spread and puts for the bear spread to avoid early exercise risk."*

---

### 2C. ADVANCED / COMBINATION STRATEGIES

---

#### `jade_lizard` — Short Put + Short Call Spread (No Upside Risk)

**Derived from McMillan's combination principles:**

**When to Use:** Mildly bullish. High IV. Want to eliminate upside risk entirely.

**Construction:** Sell OTM put + Sell OTM call spread (bear call spread). Total credit must exceed the call spread width.

**Key Property:** If total credit > call spread width, there is NO risk to the upside. Risk only exists on the downside (naked put).

**Lesson Template:** *"The Jade Lizard eliminates upside risk entirely when the total credit exceeds the call spread width. This combines McMillan's premium-selling philosophy with directional bias — you're mildly bullish but protected above."*

---

#### `dual_calendar` — Two Calendar Spreads at Different Strikes

**McMillan Ch.23:** *"The two-pronged attack."*

**When to Use:** Expecting stock to remain stable short-term, then move dramatically. Excellent for earnings gaps, FDA announcements.

**Construction:** Sell near-term OTM call + Buy longer-term OTM call AND Sell near-term OTM put + Buy longer-term OTM put.

**Selection Criteria:**
1. Relatively volatile stock
2. Stock price nearly midway between two strikes
3. Strikes at least 10 points apart
4. 2-3 months until near-term expiration
5. Near-term combination worth > 1/2 the longer-term combination price

**Key Insight for Earnings Plays:** Use the near-term straddle price as a guide for how far the stock may gap. Place calendars at those expected gap levels.

**Follow-Up:** If near-term options expire worthless, hold long combination for 6-8 weeks. Do not cut short for small profits.

**Lesson Template:** *"The dual calendar is McMillan's 'two-pronged attack' — ideal before earnings or events. You profit from near-term time decay, then from the large post-event move via the longer-term options. Place the strikes at the expected gap distance (use the straddle price as guide)."*

---

#### `diagonal_butterfly` — Short ATM Straddle + Long OTM Combination

**McMillan Ch.23:** The most sophisticated combination strategy.

**When to Use:** Objective is to own a longer-term combination for free.

**Construction:** Sell near-term ATM straddle + Buy longer-term OTM put + Buy longer-term OTM call.

**Risk:** Limited. Max loss = Strike difference - Net credit.

**Objective:** Buy back the near-term straddle for less than the initial credit. If successful, you own the longer-term combination for FREE.

**One Exception to "Never Leg Out":** This is one of the few strategies where legging out of the short straddle is acceptable, because the long combination provides protection.

**Lesson Template:** *"The diagonal butterfly is McMillan's most sophisticated combination — your goal is to own a longer-term straddle for free by selling near-term time decay. This is one of the only strategies where 'legging out' is acceptable because the long options provide protection."*

---

## 3. PUT/CALL RATIO ANALYSIS

### 3A. Core Principle: Contrarian Indicator

**McMillan Ch.30:** *"The put-call ratio is a contrary indicator. When everyone is buying puts (high ratio), the contrarian takes a bullish stance."*

### 3B. Calculation Methods

| Method | Formula | Best For |
|--------|---------|----------|
| Volume-Based | Puts traded / Calls traded | Daily/weekly signals |
| Open Interest | Put OI / Call OI | Positioning analysis |
| Dollar-Weighted | (Sum of put price x volume) / (Sum of call price x volume) | Smart money detection |

### 3C. Interpretation Framework

| Equity P/C Ratio | Raw Sentiment | Contrarian Signal | McMillan Action |
|------------------|--------------|-------------------|-----------------|
| > 1.00 | EXTREME FEAR | STRONG BULLISH | Buy signal — crowd panicking |
| 0.70 - 1.00 | BEARISH | BULLISH | Elevated fear — lean bullish |
| 0.50 - 0.70 | NEUTRAL | NEUTRAL | No signal |
| 0.30 - 0.50 | BULLISH | BEARISH | Elevated greed — lean bearish |
| < 0.30 | EXTREME GREED | STRONG BEARISH | Sell signal — rampant call buying |

**Index P/C Ratios:** Much larger (average ~2.00 for some indices due to institutional hedging). Do NOT use equity thresholds for index ratios.

### 3D. McMillan's Dynamic Method (Superior to Fixed Thresholds)

**REJECT absolute ratio thresholds** (e.g., "buy when 10-day MA > 0.60") — these fail in prolonged bear markets.

**Use dynamic interpretation:**
- Smooth daily data using 10-, 20-, or 50-day moving averages
- **Buy signal:** When the ratio's MA is rising, wait until it **rolls over and begins declining**
- **Sell signal:** When the ratio's MA is declining, wait until it **bottoms out and begins rising**

**Validation Rule:** The ratio should rise when the underlying falls and vice versa. If the ratio rises while the market rises, **ignore all signals** — the put buying is for hedging, not speculation.

**Lesson Template:** *"McMillan's put/call ratio analysis is contrarian: extreme fear (high P/C) = bullish, extreme greed (low P/C) = bearish. Reject fixed thresholds — use moving average reversals instead. Critical validation: if the ratio rises while the market also rises, ignore all signals (it's hedging, not speculation)."*

---

## 4. GREEKS APPLICATION FRAMEWORK

### 4A. Vega — The Volatility Greek

**McMillan Ch.37:** *"Vega = amount an option's price changes when implied volatility changes by one percentage point."*

**Key Properties:**
- Call and put with same terms have **identical vega**
- Vega decreases as time passes (shorter-term options have less vega)
- Longer-term options have larger vegas — crucial for spread construction
- Vega is surprisingly constant across a wide range of implied volatilities
- Vega decreases when stock price falls significantly below the strike

**Critical Insight:** *"An increase in IV from 20% to 26% (6 percentage points) can completely offset one month of time decay on an ATM option."* Even a rise to 38% offsets TWO months of time decay.

### 4B. Position Greeks

**Position Vega** = Sum of (quantity x individual vega x 100).
- Volatility buyer wants POSITIVE position vega
- Volatility seller wants NEGATIVE position vega

**Position Management Priority (McMillan Ch.40):**
1. **Neutralize gamma FIRST** (only options can offset gamma, not stock)
2. **Then neutralize delta with stock**
3. **Monitor vega exposure** for volatility shifts
4. Accept that theta is the **cost** of maintaining a long-gamma position

**McMillan Quote:** *"The serious strategist should be aware of risk with respect to at least delta, gamma, theta, and vega. To be ignorant of the risk is to be delinquent in the management of the position."*

### 4C. Equivalent Stock Position (ESP)

**Formula:** ESP = Option quantity x Delta x Shares per option

Reduces any complex position to a single number. Use to:
- Monitor total directional exposure across all positions
- Determine when to adjust (if ESP exceeds comfort level)
- Compare positions of different sizes and strategies

### 4D. Position Vega/Gamma Table

| Strategy | Position Vega | Position Gamma | Theta | Best IV Environment |
|----------|--------------|----------------|-------|-------------------|
| Long Straddle | + | + | - | LOW IV (buying) |
| Long Strangle | + | + | - | LOW IV (buying) |
| Short Straddle | - | - | + | HIGH IV (selling) |
| Short Strangle | - | - | + | HIGH IV (selling) |
| Calendar Spread | + (usually) | - | + | NORMAL IV |
| Iron Condor | - | - | + | HIGH IV (selling) |
| Butterfly | - | - | + | HIGH IV (selling) |
| Ratio Spread | - | - | + | HIGH IV (selling) |
| Backspread | + | + | - | LOW IV (buying) |
| Debit Spread | + (small) | + (small) | - (small) | LOW-NORMAL IV |
| Credit Spread | - (small) | - (small) | + (small) | HIGH IV |

---

## 5. POSITION MANAGEMENT & FOLLOW-UP

### 5A. The Three Follow-Up Methods (Ratio Writes)

**McMillan Ch.6:**

**Method 1 — Rolling at Striking Prices (Most Popular):**
- Roll written calls up when stock rises too far, down when it drops too far
- Roll exactly at the next striking price for maximum time premium capture
- *"You are buying back intrinsic value and selling thin air (time value)"*
- Even when rolling down locks in a loss, it is correct if stock has broken support

**Method 2 — Delta-Based Adjustments:**
- Use delta to maintain a neutral ratio at all times
- Formula: Calls to sell = Round lots held long / Delta of call
- Between strikes: adjust by buying/selling stock
- At new strikes: roll and recalculate with new option's delta

**Method 3 — Stop Orders:**
- Use buy/sell stops on stock to automatically adjust
- Less time-consuming but vulnerable to whipsaw

### 5B. Rolling Rules

| Action | When | McMillan Rule |
|--------|------|--------------|
| Roll Down | Stock falls to/below written strike | Use technical support levels. Partial roll-down preserves flexibility |
| Roll Up | Stock rises above written strike | Do NOT roll up unless you can withstand a **10% correction** |
| Roll Out | Approaching expiration | Roll to next month for additional time premium |
| Roll Up for Credits | Volatile stocks | Preferred method — locks in profits at each new strike |

### 5C. Exit Rules (Institutional)

| Trigger | Action | Source |
|---------|--------|--------|
| 50% of max profit reached | Close position | TastyTrade research |
| 21 DTE reached | Roll or close | Gamma acceleration zone |
| Position delta > ±0.35 | Adjust or close | Delta management |
| 50% of max loss reached | Review and decide | Loss management |
| Stock at parity with short option | Close to avoid assignment | McMillan Ch.8 |
| **NO STOP LOSSES** | Never use mechanical stops on options | TastyTrade research (46% win rate with stops) |

### 5D. Volatility Position Follow-Up

**McMillan Ch.40:**
- *"First, neutralize the gamma; then use stock to adjust the delta"*
- Buying options to reduce negative gamma hurts the original thesis (adds vega, subtracts theta) but is better than letting losses build
- Remove the entire position if it becomes profitable from correct volatility prediction
- Volatility buyers need only check positions once a day
- Volatility sellers must watch much more closely

---

## 6. EARLY EXERCISE & ASSIGNMENT

### 6A. Call Assignment Rules

**McMillan Ch.1:**
- Assignment is virtually 100% certain if option expires ITM, even by a penny (OCC automatic exercise)
- Early exercise likely when: (1) option trades at or below parity, (2) ex-dividend date approaching, (3) time value premium disappears from ITM call
- **Dividend-related:** If there is no time value premium remaining in an ITM call, exercise is likely on the day before ex-dividend

### 6B. Put Assignment Rules

**McMillan Ch.15:**
- Put writer should expect assignment on the day **after** the ex-dividend date (holder wants to collect dividend first)
- **Critical threshold:** If time value premium < impending dividend → anticipate assignment. If time premium > dividend → assignment probability much lower
- In spreads, assignment of the short side can dramatically increase risk — always avoid assignment in spread positions

### 6C. Anti-Assignment Rules

- Any writer wanting to avoid assignment should cover (buy back) if stock will be beyond strike at expiration
- Covering at any time during a trading day prevents assignment that day
- For credit spreads: close the spread if short option trades at parity (no time premium left)

---

## 7. STRATEGY SELECTION DECISION TREE

### 7A. IV Environment → Strategy Class

```
IV Rank 0-10% (CHEAP) ──→ Aggressive buying: straddles, strangles, backspreads, LEAPS
IV Rank 10-30% (LOW) ──→ Moderate buying: debit spreads, calendars, long options
IV Rank 30-50% (NORMAL) ──→ Flexible: calendars, conservative iron condors, diagonals
IV Rank 50-70% (HIGH) ──→ Moderate selling: credit spreads, iron condors, covered calls
IV Rank 70-90% (ELEVATED) ──→ Aggressive selling: ratio spreads, short strangles, jade lizards
IV Rank 90-100% (EXPENSIVE) ──→ Check for insider activity first. If clear: naked puts, straddle writes
```

### 7B. Direction + IV → Specific Strategy

| Direction | LOW IV (0-30%) | NORMAL IV (30-50%) | HIGH IV (50-70%) | EXTREME IV (70-100%) |
|-----------|---------------|-------------------|------------------|---------------------|
| BULLISH | Long Call, Bull Call Spread, LEAPS | Diagonal Spread, Bull Call Spread | Bull Put Spread (Credit), Cash-Secured Put | Short Put, Jade Lizard, Bull Put Spread |
| BEARISH | Long Put, Bear Put Spread | Bear Put Spread, Put Calendar | Bear Call Spread (Credit) | Bear Call Spread, Short Call Spread |
| NEUTRAL | Calendar Spread, Long Straddle | Iron Condor (Conservative), Calendar | Iron Condor, Iron Butterfly, Credit Spread | Ratio Spread, Short Strangle, Short Straddle |
| VOLATILE | Long Straddle, Backspread | Dual Calendar | N/A (IV already high) | N/A |

### 7C. Earnings Proximity Filter

| Days to Earnings | Buyers | Sellers |
|-----------------|--------|---------|
| > 45 days | Allowed | Allowed |
| 30-45 days | Caution — IV rising | Prime time — elevated IV |
| < 30 days | **BLOCKED** — IV crush will destroy value | Allowed — IV crush is profitable |
| < 7 days | **BLOCKED** | Caution — gamma risk extreme |

### 7D. Liquidity Tier Filter

| Tier | Criteria | Sizing | Strategies Allowed |
|------|----------|--------|-------------------|
| TIER 1 | Penny-wide spreads, 10K+ OI | Full size (1.0x) | All strategies |
| TIER 2 | S&P 500, high volume, weeklies | 75% size (0.75x) | All except naked strangles |
| TIER 3 | Moderate volume (500K+ shares) | 50% size (0.50x) | Defined-risk only, limit orders |
| NON-LIQUID | < 500K shares/day | **SKIP OPTIONS** | Stock only |

---

## 8. PROBABILITY & EXPECTED RETURN

### 8A. Expected Return Methodology

**McMillan Ch.28/Ch.38:**

**Formula:** Expected Return = Sum of (profit at each price x probability of that price) / Investment

Probabilities derived from stock price distribution (lognormal):
P(below q) = N(ln(q/p) / (V × sqrt(t)))
where N = cumulative normal, p = current price, V = annual volatility, t = time in years

### 8B. Fat-Tail Reality

**McMillan's Key Finding:** Under fat-tail distribution (most realistic):
- **Option buying** strategies perform "much, much better" than under lognormal
- Bull spreads are inferior regardless of distribution
- **Strategies with limited risk and unlimited profit potential perform well**
- **Strategies with limited profit and unlimited risk are INFERIOR in real life**

This means: Straddle buying, backspreads, and long options are systematically undervalued by Black-Scholes. Naked writing and iron condors are systematically riskier than models suggest.

### 8C. Probability Thresholds

| Strategy Type | McMillan's Threshold | What It Measures |
|--------------|---------------------|------------------|
| Volatility Buying | > 80% | Probability of underlying EVER reaching breakeven |
| Volatility Selling | < 25% | Probability of stock reaching loss-causing strikes |
| Straddle Selection | 25% threshold | Probability of up/down movement equal to expected volatility |
| Minimum POP for entry | 65% | Probability of profit (institutional standard) |

### 8D. Back-Testing Validation

**McMillan Ch.39:** After finding mispriced options with good probabilities, verify with past price data.

**Process:**
1. Express the required move as a **percentage** (not dollar amount)
2. Build a histogram of past movements over the same time horizon
3. A good histogram shows: the stock always moved at least the required distance, frequently moved 2-3x that far, continuity with no large gaps
4. A poor histogram clusters moves near the breakeven — do NOT take the trade

### 8E. Three-Step Volatility Trading Process

**McMillan Ch.39:**
1. **Step 1:** Use a selection criterion (percentile, implied vs historical, or chart reading) to find candidates
2. **Step 2:** Use a probability calculator to verify the strategy can be expected to succeed
3. **Step 3:** Use past price histories and histograms to confirm the underlying has made the required moves
4. **Best candidates appear on more than one screening list**

---

## 9. VOLATILITY SKEW TRADING

### 9A. Skew Types

| Skew Type | Description | Where Seen | Cause |
|-----------|-------------|-----------|-------|
| **Negative (Reverse)** | OTM puts most expensive, OTM calls cheapest | Equity indices (SPX, OEX) | Demand for portfolio insurance post-1987 |
| **Positive (Forward)** | OTM calls most expensive, OTM puts cheapest | Commodities (soybeans, gold, sugar) | Supply shock risk |
| **Flat** | All strikes similar IV | Rare | Balanced supply/demand |

### 9B. Skew Trading Strategies

**Principle:** Always buy lower IV, sell higher IV. At expiration, the skew must disappear — holding to expiration creates positive expected return.

**For Negative Skew (equity indices):**
| Strategy | Construction | When |
|----------|-------------|------|
| Bear Put Spread | Buy higher-strike put (lower IV), sell lower-strike put (higher IV) | Any percentile |
| Put Ratio Write | Sell more OTM puts, buy fewer ATM puts | HIGH IV percentile |
| Call Backspread | Sell ITM call, buy more OTM calls | LOW IV percentile |

**For Positive Skew (commodities):**
| Strategy | Construction | When |
|----------|-------------|------|
| Bull Call Spread | Buy lower-strike call (lower IV), sell higher-strike call (higher IV) | Any percentile |
| Put Backspread | Sell ITM put, buy more OTM puts | LOW IV percentile |
| Call Ratio Spread | Buy fewer ATM calls, sell more OTM calls | HIGH IV percentile |

**Key Rule:** Use ratio spreads when IV is in a HIGH percentile. Use backspreads when IV is in a LOW percentile.

---

## 10. THETA DECAY FRAMEWORK

### 10A. Decay Curve

**McMillan Ch.37:** Options lose time value at an accelerating rate as expiration approaches.

| DTE Window | Decay Rate | Trading Phase | Action |
|-----------|-----------|--------------|--------|
| 60-45 DTE | ~0.5%/day | Optimal entry zone | Enter premium-selling positions |
| 45-30 DTE | ~1.0%/day | Primary theta capture | Core profit period |
| 30-21 DTE | ~1.5%/day | Decision point | Roll or close sellers |
| 21-7 DTE | ~3.5%/day | High gamma risk | Exit most positions |
| 7-0 DTE | ~7.5%/day | Binary zone | Avoid — only for day traders |

### 10B. Theta vs Vega Trade-Off

**Critical Insight:** A 6-point IV increase can offset one FULL month of time decay on an ATM option. This means:
- Premium sellers who enter positions expecting theta decay can be wiped out by a volatility spike
- Premium buyers in low-IV environments get "free" time extension when IV expands
- **Always consider vega exposure relative to theta** when sizing positions

---

## 11. RISK MANAGEMENT PRINCIPLES

### 11A. Position Sizing

| Parameter | McMillan/Institutional Value |
|-----------|---------------------------|
| Max risk per defined-risk trade | 3% of account |
| Max risk per undefined-risk trade | 2% of account |
| Max buying power usage | 60% |
| Cash reserve for adjustments | 40% |
| Kelly fraction | Half-Kelly (0.50) |
| Max single underlying | 10% of portfolio |
| Max sector exposure | 20% |
| Max correlated exposure (r > 0.7) | 40% |
| Max single expiration | 35% |
| Speculative put buying limit | 15% of risk capital |
| Naked put minimum protection | 5% downside or 12% annualized return |

### 11B. McMillan's Cardinal Rules

1. **Sellers of volatility must be far more careful than buyers.** One mistake can be the last one
2. **ANY stock is subject to crushing decline** — do not rely on "quality" as protection (IBM 1991, P&G 1999, Xerox 1999)
3. **NEVER leverage your account heavily in naked puts** regardless of stock quality
4. **Taking small profits on straddles is a POOR strategy** — the edge comes from infrequent large winners
5. **Selling short-term, fractionally-priced OTM options is a "poor strategy"** — pennies in front of a steamroller
6. **NEVER "leg" into or out of spreads** — sole exception: diagonal butterfly where long options provide protection
7. **Sell time value, buy intrinsic value** — this is the fundamental philosophy underlying all sound spread strategies
8. **Check fundamentals BEFORE trading** — if options are cheap because of an all-cash tender, do NOT buy
9. **Strategies with limited profit and unlimited risk are INFERIOR** under real (fat-tail) distributions
10. **Best candidates appear on more than one screening list** — confirmation from multiple methods

---

## 12. MCMILLAN-BROOKS-DALIO INTEGRATION

### 12A. How McMillan Complements Brooks

| Brooks Signal | McMillan Enhancement |
|--------------|---------------------|
| Strong trend pattern (High 2, Wedge) | Check IV environment for optimal strategy (debit spread in low IV, credit spread in high IV) |
| Trap detected (bull/bear trap) | Straddle/strangle purchase if IV is cheap — trap implies volatility ahead |
| Climax detection | IV likely to spike — avoid selling premium. Buy straddles for reversal volatility |
| Channel/range pattern | Iron condor or butterfly if IV is elevated — range-bound expected |
| Trend evolution late stage | Calendar spreads for time decay while awaiting breakout |

### 12B. How McMillan Complements Dalio

| Dalio Signal | McMillan Enhancement |
|-------------|---------------------|
| EXPANSION regime | Normal IV environment — flexible strategies, favor calls |
| LATE_CYCLE regime | Elevated IV likely — favor premium selling, iron condors |
| CONTRACTION regime | High IV + high fear — aggressive selling with protection, or contrarian straddle buys |
| RECOVERY regime | IV declining from highs — calendars, diagonal spreads |
| High Dalio Ratio (bullish) | Use bull put spreads (credit) in high IV, bull call spreads (debit) in low IV |
| Low Dalio Ratio (bearish) | Use bear call spreads (credit) in high IV, bear put spreads (debit) in low IV |

---

*Version 1.0 — Generated from McMillan "Options as a Strategic Investment" (5th Edition)*
*Aligned with: `options_analysis.py` (7 MCP tools), `config.py` (institutional parameters), `decision_framework.py` (Gate 5)*
