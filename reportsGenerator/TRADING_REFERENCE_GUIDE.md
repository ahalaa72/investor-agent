# Trading Reference Guide

Educational reference for Al Brooks Price Action, McMillan Options Strategy, and Ray Dalio Economic Machine. This is a **companion document** — the report templates reference this guide for methodology details.

---

## AL BROOKS PRICE ACTION

**Source:** Al Brooks — *Trading Price Action* series, *Reading Price Charts Bar By Bar*

### Always-In Direction

The **Always-In Direction** tells you which side has control. If forced to hold a position, which direction would you choose?

**Always-In LONG:**
- Bulls are in control. Every pullback is a buying opportunity.
- Bears are getting trapped — their shorts lose money and covering adds buying pressure.
- ✅ Buy pullbacks to EMA20, VWAP, or support. Use bull flag breakouts.
- ❌ Don't short into strength. Trends stay overbought longer than you can stay solvent.
- *"When Always-In is LONG, every selloff is a bull flag until proven otherwise."* (Ch. 5)

**Always-In SHORT:**
- Bears are in control. Every rally is a selling opportunity.
- Bulls are getting trapped — their longs lose money and exits add selling pressure.
- ✅ Sell rallies to EMA20, VWAP, or resistance. Use bear flag breakdowns.
- ❌ Don't buy dips in a bear trend. Catching falling knives loses money.
- *"When Always-In is SHORT, every rally is a bear flag."* (Ch. 6)

**Always-In NEUTRAL:**
- Neither side in control. Range-bound, choppy price action.
- Both sides get trapped. Breakouts fail, reversals happen quickly.
- ✅ Fade extremes (sell resistance, buy support). Wait for breakout confirmation.
- ❌ Don't chase breakouts without strong confirmation — most fail in ranges.
- *"In trading ranges, buy low, sell high, and get out quickly."* (Ch. 8)

---

### Pattern Reference

#### High 2 (Bull Reversal — 60-70% win rate)
Two-legged pullback in an uptrend that tests a prior high.

1. Bar 1: Strong bull bar makes new high
2. Bar 2: Pullback bar pulls back but stays above support
3. Bar 3 (Entry): Price breaks above Bar 1's high → BUY

**Why it works:** Failed bear breakout. Bears tried to push lower but failed, creating a "bear trap." Trapped bears must cover, adding buying pressure.

*"High 2 is a failed bear breakout that becomes a bull signal."* (Ch. 17)

#### Low 1 (Bull Entry — 60%+ win rate)
First pullback in a strong bull trend. Buy-the-dip setup.

1. Strong bull trend with consecutive bull bars
2. First pullback (1-3 bars) to support (EMA20, VWAP, prior resistance)
3. Entry: Buy when price bounces off support with bull reversal bar

**Why it works:** Strong momentum. Late bulls enter on dip. Bears too weak for deep pullback.

*"The first pullback in a strong trend is the best entry."* (Ch. 16)

#### Wedge (Reversal — 3-push exhaustion)
Three-push pattern signaling exhaustion and likely reversal.

1. Push 1: Strong move in trend direction
2. Push 2: Pullback, then another push (weaker momentum)
3. Push 3: Final push (weakest) — **reversal point**

**Why it works:** Each push gets weaker (shrinking bars, lower volume, divergences). Late trend-followers get trapped. Smart money exits.

- Bull Wedge → Sell when Push 3 fails to make new high
- Bear Wedge → Buy when Push 3 fails to make new low

*"Wedges are climactic moves. Three pushes with weakening momentum = prepare for reversal."* (Ch. 11)

#### Breakout (Continuation — Variable probability)

**Strong Breakout (70%+ success):**
- Large bar closing near extreme, high volume, follow-through next 1-2 bars
- Entry: Buy/sell pullback to breakout level (now support/resistance)

**Weak Breakout (30-40% success — FADE IT):**
- Small bar/doji, low volume, immediate pullback, overlap with prior bar
- ❌ Don't chase. Wait for failure, then trade the reversal.

*"Strong breakouts have strong bars, high volume, and no pullback. Weak breakouts fail 60-70% of the time — fade them."* (Ch. 9)

#### Channel (Trend with parallel boundaries)
Price oscillates between trend line (support in uptrend) and channel line (parallel opposite side).

- **Bull Channel:** Buy trend line tests, take profit at channel line
- **Bear Channel:** Sell trend line tests, take profit at channel line
- **Breakout above channel:** Acceleration — trend strengthening
- **Breakdown below channel:** Trend failure — potential reversal

*"Trade with the channel — buy lows, sell highs within the trend."* (Ch. 10)

---

### Bar Reading

**Strong Bull Bar (closing near high):** Buyers dominated. No selling pressure even at highs. Expect continuation or shallow pullback.

**Strong Bear Bar (closing near low):** Sellers dominated. No buying support even at lows. Expect continuation or shallow bounce.

**Doji / Small Bar:** Indecision. Neither side in control. After a strong trend = potential exhaustion. Wait for next bar to clarify.

**Inside Bar:** Compression before explosive move. Direction unclear. Entry: breakout of inside bar's high/low.

**Pattern Observations:**
- String of bull/bear bars = strong trend (trade first pullback)
- Overlapping bars = congestion/range (fade extremes, wait for breakout)
- Decreasing bar size = momentum fading (tighten stops, watch for reversal)

---

### Trap Recognition

**Late-in-Move Trap** (Buying tops / Selling bottoms):
Price has rallied X bars without pullback. Late retail buys the top. Smart money sells to them. Wait for pullback instead.

**Counter-Trend Trap** (Fighting the trend):
Always-In is LONG but you short because "it's overbought." Trend continues. Shorts cover at loss. Only trade WITH Always-In direction.

**Failed Breakout Trap** (Chasing weak breakouts):
Weak bar, low volume, immediate pullback. Retail buys breakout. Breakout fails. Require strong bar + high volume + follow-through.

*"Recognizing traps is more important than recognizing setups."*

### Trap Type Taxonomy (5 Types)

| Trap Type | Description | Severity | How to Trade |
|-----------|-------------|----------|-------------|
| `bull_trap` | Failed breakout above resistance | HIGH | Short when price drops back below resistance |
| `bear_trap` | Failed breakdown below support | HIGH | Long when price recovers above support |
| `late_move_trap` | Entry after 3+ pushes, exhaustion imminent | MOD-HIGH | Reduce size, tighten stops, watch for reversal |
| `failed_reversal_trap` | Reversal pattern fails, trend resumes | HIGH | Re-enter with trend — failed reversals are strongest continuation |
| `vacuum_fill_trap` | Price fills gap then reverses | MODERATE | Tight stop — once gap filled, original direction often resumes |

**Full details:** See [BROOKS_MASTERY_GUIDE.md](BROOKS_MASTERY_GUIDE.md) Section 2.

### Trend Evolution Model

```
STRONG_TREND (80-100) → CHANNEL (60-80) → BROAD_CHANNEL (40-60) → TRADING_RANGE (20-40)
```

| Phase | Bar Overlap | Pullback Depth | How to Trade |
|-------|------------|----------------|-------------|
| STRONG_TREND | <20% | <30% | With trend ONLY. Buy any dip. |
| CHANNEL | 20-40% | 30-50% | Buy trend line, sell channel line. |
| BROAD_CHANNEL | 40-60% | 50-70% | Reduced size. Both directions at extremes. |
| TRADING_RANGE | >60% | >70% | Buy low, sell high, scalp. Iron condors. |

### Climax Detection (4 Types)

| Type | Definition | Severity | Expected Resolution |
|------|-----------|----------|-------------------|
| Simple | Single bar, body > 2x avg | LOW | 1-3 bar pullback |
| Consecutive | 3+ strong bars same direction | MODERATE | Multi-bar pullback to EMA |
| Parabolic | Each bar LARGER than previous | HIGH | Deep pullback or reversal |
| Channel Overshoot | Price breaks channel line | HIGH | Reversal to channel |

### Measured Move Methods

| Method | Calculation | Reliability |
|--------|------------|------------|
| Leg1 = Leg2 | Target = Pullback_Low + Leg1_Height | HIGH (60-70%) |
| Range Projection | Target = Breakout + Range_Height | HIGH for strong breakouts |
| Spike Projection | Target = Current + Spike_Height | MODERATE (50-60%) |

When 2+ methods agree within 2%: HIGH CONFIDENCE target.

---

### Brooks Probability Framework

**Base Probability:** Each pattern has a historical success rate (e.g., High 2 = 60-70%).

**Context Adjustments:**

| Factor | Impact | Example |
|--------|--------|---------|
| Strong trend (Always-In aligned) | +10-15% | Trading with the trend |
| High volume on setup bar | +10% | Institutions participating |
| Multi-timeframe alignment | +10-15% | Daily + weekly both bullish |
| Catalyst present | +5-10% | Earnings in X days |
| Failed opposite setup | +10-15% | Trapped traders must cover |
| Strong bars (closing near extremes) | +5-10% | Conviction |
| Dalio Ratio aligned | +5% | Buyers paying premium (LONG) or discount (SHORT) |
| Positive/Negative Dollar Flow | +3% | Net accumulation/distribution |
| High sustainability | +3% | Trend is sustainable |
| Counter-trend trade | -20-30% | Fighting Always-In direction |
| Low volume | -10-15% | Retail only, no institutions |
| Choppy/overlapping bars | -10% | Indecision |
| Late in move | -10-15% | Exhaustion risk |
| Weak bars (dojis, long tails) | -10% | Low momentum |
| Divergences (RSI/MACD) | -10-15% | Bearish divergence |

**Probability capped at 30-80% range per Brooks methodology.**

**Conviction Tiers:**
- ≥70%: HIGH — Full position size (within 2% risk). Textbook setup.
- 50-69%: MODERATE — Reduced size (50-75%). Acceptable with caveats.
- <50%: LOW — DO NOT TRADE. Wait for better setup.

*"If you don't have ≥60% probability AND 1:1 R/R (or 50% with 2:1 R/R), don't trade."* (Ch. 22)

---

## McMILLAN OPTIONS STRATEGY

**Source:** Lawrence McMillan — *Options as a Strategic Investment* (5th Ed.) + TastyTrade Research

### IV Environment → Strategy Selection

The **single most important decision** in options trading: match your strategy to the volatility environment.

| IV Rank | Environment | Strategy | Rationale |
|---------|------------|----------|-----------|
| >50% | HIGH IV | **Sell premium** (Credit Spreads, Iron Condors) | Options expensive → collect inflated premium, profit from IV crush |
| 30-50% | NORMAL IV | **Directional** (Debit Spreads) or **Neutral** (Iron Condors) | Options fairly priced → use conviction for direction |
| <30% | LOW IV | **Buy premium** (Long Calls/Puts, Debit Spreads) | Options cheap → buy discounted premium before vol expansion |

**Detailed Strategy Matrix:**

| IV Rank | BULLISH | BEARISH | NEUTRAL |
|---------|---------|---------|---------|
| HIGH (>50%) | Bull Put Credit Spread (16Δ short) | Bear Call Credit Spread (16Δ short) | Iron Condor |
| MEDIUM (30-50%) | Bull Call Debit Spread | Bear Put Debit Spread | Butterfly |
| LOW (<30%) | Long Call (ATM) | Long Put (ATM) | Calendar Spread |

*"Sell premium when IV is high, buy premium when IV is low. Match strategy to volatility, not your market opinion."*

### Put/Call Ratio (Contrarian Signals)

P/C Ratio = Put Volume / Call Volume

| Range | Raw Sentiment | Contrarian Signal |
|-------|--------------|-------------------|
| >1.2 | Excessive bearishness | **Contrarian BULLISH** — everyone hedged, squeeze likely |
| 0.7-1.2 | Normal/balanced | No signal — use other factors |
| <0.5 | Excessive bullishness | **Contrarian BEARISH** — complacency, profit-taking likely |

P/C spikes >1.2 often precede 5-10 day rallies as bearish positioning unwinds.

### Max Pain (Price Magnetism)

Max pain = price where option sellers profit most. Market makers delta-hedge, creating gravitational pull toward max pain into expiration.

| Relationship | Signal | Implication |
|-------------|--------|-------------|
| Max pain ABOVE price | Upward pull | Bullish bias into expiry |
| Max pain BELOW price | Downward pull | Bearish bias into expiry |
| Max pain AT price | Equilibrium | Range-bound into expiry |

**Reliability:** HIGH near expiry (<7 days) + high OI. LOW far from expiry (>15 days) or low OI.

### Greeks Quick Reference

| Greek | Measures | Buyer Impact | Seller Impact |
|-------|----------|-------------|---------------|
| **Delta** | $/move per $1 stock move. Also ≈ probability ITM | Directional exposure | Directional risk |
| **Gamma** | Rate of delta change | Explosive gains near strike | Explosive losses near strike |
| **Theta** | Time decay per day | Enemy (paying decay) | Friend (collecting decay) |
| **Vega** | $/move per 1% IV change | Profits from IV rise | Profits from IV drop |

**Key thresholds:**
- High Delta (>0.70): Deep ITM, acts like stock
- High Gamma (>0.05): Near ATM, explosive near expiry
- High Theta (>-$0.10): Rapid decay, favors sellers
- High Vega (>$0.50): IV-sensitive

**Position Risk Profiles:**
- Theta-negative + Vega-long in HIGH IV = DANGER (fighting time decay AND IV crush)
- Theta-positive + Vega-short in HIGH IV = IDEAL (collecting decay + IV normalization)
- Theta-negative + Vega-long in LOW IV = STRATEGIC (positioned for vol expansion)

### Standard Deviation & Strike Selection

**Formula:** Expected Move = Price × IV × √(DTE / 365)

| Delta | SD | Probability OTM | Use Case |
|-------|----|-----------------|----------|
| 50Δ | 0 SD (ATM) | 50% | Neutral / max theta |
| 30Δ | ~0.5 SD | 70% | Moderate premium |
| **16Δ** | **~1 SD** | **84%** | **TastyTrade optimal (best R/R)** |
| 10Δ | ~1.5 SD | 90% | Higher probability |
| 5Δ | ~2 SD | 95% | Highest probability (low premium) |

16-delta strikes provide the **best risk-adjusted returns**: 84% win rate, reasonable premium, positive expected value.

### McMillan Volatility Regime Assessment (NEW)

`analyze_options_mcmillan()` now returns a `mcmillan_mastery` block with institutional-depth volatility analysis.

**Volatility Regime (McMillan Ch.39 Three-Step Process):**

| Regime | IV Percentile | Action |
|--------|--------------|--------|
| STRONG_BUY_VOL | 0-10% + IV < 80% of HV | Aggressive buying: straddles, strangles, backspreads |
| BUY_VOL | 10-30% | Moderate buying: debit spreads, calendars, long options |
| NEUTRAL | 30-70% | Flexible: match strategy to directional outlook |
| SELL_VOL | 70-90% | Moderate selling: credit spreads, iron condors, covered calls |
| STRONG_SELL_VOL | 90-100% + IV > 120% of HV | Check for insider activity first. If clear: aggressive selling |

**McMillan's Percentile Method:** Uses 600 trading days of IV history. The width of the IV range must be sufficient — if a rise from current to the 50th percentile won't offset one month of time decay, the range is too narrow.

**Vega-Theta Trade-Off (McMillan Ch.37):**
- A 6-point IV increase can offset ONE FULL MONTH of ATM time decay
- Premium sellers at low IV face HIGH vega risk (IV likely to expand)
- Premium sellers at high IV face LOW vega risk (IV likely to contract via mean reversion)

**Volatility Skew Trading (McMillan Ch.39):**

| Skew Type | Description | High IV Strategy | Low IV Strategy |
|-----------|-------------|-----------------|-----------------|
| NEGATIVE | OTM puts expensive (equity indices) | Put Ratio Write | Call Backspread |
| POSITIVE | OTM calls expensive (commodities) | Call Ratio Spread | Put Backspread |
| FLAT | No significant imbalance | Standard IV-based selection | Standard IV-based selection |

*"Always buy lower IV, sell higher IV. At expiration, the skew must disappear, so holding to expiration creates positive expected return."*

**McMillan Strategy Lessons:**

Each strategy now returns pattern-indexed educational content with:
- McMillan quote and chapter reference
- Historical win rate range
- When to use (market conditions)
- Key risk to monitor
- Educational lesson explaining the strategy dynamics

Key McMillan rules surfaced in lessons:
- *"Taking small profits on straddles is a POOR strategy"* — the edge comes from infrequent large winners
- *"Selling short-term, fractionally-priced OTM options is a poor strategy"* — pennies in front of steamroller
- *"NEVER leverage your account heavily in naked puts regardless of stock quality"*
- *"Strategies with limited profit and unlimited risk are INFERIOR under fat-tail distributions"*

### Options Data Interpretation Warning

`analyze_options_mcmillan()` analyzes ONE expiration (optimal 30-45 DTE). `detect_unusual_options_activity()` scans ALL expirations. When they appear contradictory, they're analyzing different expirations — always specify which expiration in the report.

---

## INSTITUTIONAL OPTIONS RULES

| # | Rule | Rationale |
|---|------|-----------|
| 1 | IV drives strategy | HIGH IV → sell premium; LOW IV → buy premium |
| 2 | 45 DTE entry | Optimal theta decay with manageable gamma |
| 3 | 50% profit target | Close at 50% max profit = 88% win rate (TastyTrade) |
| 4 | NO stop losses on credit spreads | Manage at 21 DTE instead — stops reduce profitability |
| 5 | 21 DTE exit | Gamma risk explodes — roll or close |
| 6 | Half-Kelly sizing | Kelly/2 reduces volatility, increases longevity |
| 7 | Earnings filter | Skip if earnings < 30 days (IV crush risk) |
| 8 | Liquidity rules | Spread ≤5%, OI ≥100, Volume ≥50 |

---

## RAY DALIO ECONOMIC MACHINE

**Source:** Ray Dalio — *How the Economic Machine Works*

*"Price = Total Spending / Quantity Sold"* — Understanding money flow reveals what REAL buyers are doing.

### Key Metrics

| Metric | Meaning | Bullish | Bearish |
|--------|---------|---------|---------|
| **Dalio Ratio** | Price buyers pay vs fair value | >1.0 (paying premium) | <1.0 (paying discount) |
| **Dollar Flow** | Net money flow | Positive (accumulation) | Negative (distribution) |
| **Sustainability** | Trend durability (0-100) | ≥60 (sustainable) | <40 (unsustainable) |

### Gate 2 Enhanced (6 Checks — need 5/6 to PASS)

1. CVD aligned with direction
2. Not exhausted (<50/100)
3. Fresh direction detected
4. Dalio Ratio aligned (≥1.0 for LONG, <1.0 for SHORT)
5. Dollar Flow aligned (positive for LONG, negative for SHORT)
6. Sustainability ≥50

### Brooks Probability Adjustments

| Condition | Impact |
|-----------|--------|
| Dalio Ratio ≥1.02 (LONG) or ≤0.98 (SHORT) | +5% |
| Dollar Flow aligned with direction | +3% |
| Sustainability ≥70 | +3% |
| Dalio Ratio opposes direction | -5% |
| Dollar Flow opposes direction | -3% |
| Sustainability ≤30 | -3% |

**Total Dalio impact:** Up to ±11% probability adjustment.

---

## STATISTICAL VALIDATION FRAMEWORK

**Source:** López de Prado — *Advances in Financial Machine Learning* + Kelly Criterion (Ed Thorp)

### Kelly Criterion Position Sizing

The Kelly Criterion calculates the optimal fraction of capital to risk on a trade, given edge and odds.

**Formula:** `f* = (p × b - q) / b` where p = win rate, b = avg win / avg loss, q = 1 - p

**Fractional Kelly (Quarter-Kelly):** Use 25% of full Kelly to reduce variance and drawdown risk. Full Kelly maximizes geometric growth but produces large drawdowns. Half-Kelly cuts variance by 75% with only 25% reduction in growth. Quarter-Kelly is conservative and suitable for most traders.

**Tools:** `recommend_kelly_position_size(win_rate, avg_win_pct, avg_loss_pct, account_value, kelly_fraction, max_position_pct)`

### Edge Quantification

Edge = Expected Return per trade. A positive edge means the strategy is profitable over many trades.

**Edge Quality Tiers:**

| Edge Quality | Expected Return | Action |
|-------------|-----------------|--------|
| STRONG | >1.0% per trade | Full Kelly sizing |
| MODERATE | 0.3-1.0% per trade | Half or Quarter-Kelly |
| WEAK | 0.0-0.3% per trade | Minimum size or skip |
| NO_EDGE | <0.0% per trade | Do not trade |

**Tools:** `quantify_pattern_edge(ticker, pattern_id, lookback_days, holding_period)`, `validate_brooks_pattern_win_rate(ticker, pattern_id, lookback_days, holding_period, profit_target_pct, stop_loss_pct)`

### Monte Carlo Stress Testing

Simulates thousands of portfolio return paths using historical return distributions. Captures fat tails and correlation breakdowns that parametric models miss.

**Key Outputs:**

| Metric | Definition | Use |
|--------|-----------|-----|
| VaR 95% | Max loss in 95% of scenarios | Daily risk budget |
| VaR 99% | Max loss in 99% of scenarios | Extreme risk limit |
| CVaR 95% | Average loss in worst 5% of scenarios | Tail risk assessment |
| Probability of >10% loss | Frequency of large drawdowns | Portfolio stress tolerance |

**Tools:** `run_monte_carlo_stress_test(account_number, n_simulations, time_horizon_days, lookback_days)`

### Drawdown Analysis

Measures peak-to-trough portfolio declines — the most psychologically and financially damaging aspect of trading.

| Metric | Definition | Good | Poor |
|--------|-----------|------|------|
| Max Drawdown | Largest peak-to-trough decline | <15% | >30% |
| Calmar Ratio | Annual return / Max drawdown | >1.0 | <0.5 |
| Ulcer Index | RMS of drawdown depth × duration | <5 | >15 |

**Tools:** `calculate_drawdown_analysis(account_number, lookback_days)`

### Model Decay Detection

Monitors whether the 5-gate signal system is degrading over time. Gate trends, prediction accuracy, and best/worst predictors are tracked.

**Tools:** `detect_model_decay(days, threshold)`

---

## POSITION MANAGEMENT FRAMEWORK

**Source:** TastyTrade + McMillan Ch. 36

For **existing options positions** — daily monitoring and management. Not for new analysis.

### Management Priority (Check in Order)

| Priority | Check | Trigger | Action | Urgency |
|----------|-------|---------|--------|---------|
| 1 | 50% Profit Target | P&L ≥ 50% max profit | CLOSE | IMMEDIATE |
| 2 | 21 DTE Management | DTE ≤ 21 days | CLOSE or ROLL | WITHIN_3_DAYS |
| 3 | Direction Change | Brooks Always-In flips | CLOSE | IMMEDIATE |
| 4 | Tested Position | Price breaches short strike + DTE ≤ 7 | CLOSE | IMMEDIATE |
| 5 | Earnings Proximity | Earnings < 7 days | CLOSE | IMMEDIATE |

**Why this order:** Take profits early (88% win rate at 50% vs 52% at expiration). Avoid gamma acceleration after 21 DTE. Exit invalidated thesis immediately.

### Action Types

| Action | When |
|--------|------|
| **HOLD** | No triggers hit — position healthy |
| **CLOSE** | Profit target, direction flip, assignment risk |
| **ROLL** | 21 DTE + losing position → move to next expiration |

### Tools

- `evaluate_options_position_management()` — Daily check per position
- `get_portfolio_greeks_dashboard()` — Weekly portfolio-level risk

---

## SCORING TIERS (Universal)

Used across all report sections:

| Score | Tier | Position Size | Action |
|-------|------|--------------|--------|
| ≥75/100 | HIGH CONVICTION | Full size (within 2% risk) | Execute |
| 50-74/100 | MODERATE | Reduced size (50-75%) | Execute with caveats |
| <50/100 | LOW | Do not trade | Wait for better setup |

### Decision Matrix

| Weighted Score | Brooks Prob | Historical | Decision |
|---------------|------------|------------|----------|
| >80 | >60% | >60% | STRONG BUY/SELL |
| >80 | >60% | <60% | BUY/SELL (caution) |
| 70-80 | >60% | >60% | BUY/SELL |
| 70-80 | >60% | <60% | CONSIDER |
| <70 | >60% | Any | WAIT |
| Any | <50% | Any | SKIP |

### Trading Plan Generation Rules

**Generate plan for:** STRONG_BUY, BUY, SELL, STRONG_SELL
**Skip plan for:** WATCH (no conviction), NO_TRADE (gates failed)

---

## INTERMARKET ANALYSIS FRAMEWORK

**Source:** John Murphy — *Intermarket Analysis* + Ray Dalio — *How the Economic Machine Works*

### Correlation Interpretation

| Benchmark | Ticker | Positive Correlation Means | Negative Correlation Means |
|-----------|--------|---------------------------|---------------------------|
| **UUP** (US Dollar) | UUP | Stock rises with dollar (exporters hurt) | Stock falls with dollar (dollar-sensitive) |
| **^TNX** (10Y Yield) | ^TNX | Stock rises with rates (financials, value) | Stock falls with rates (growth, tech, REITs) |
| **USO** (Crude Oil) | USO | Stock rises with oil (energy, transports) | Stock falls with oil (airlines, consumers) |
| **GLD** (Gold) | GLD | Stock rises with gold (safe haven, miners) | Stock falls with gold (risk-on asset) |
| **SPY** (S&P 500) | SPY | High beta, moves with market | Defensive/counter-cyclical |
| **TLT** (Long Bonds) | TLT | Stock rises with bonds (rate-sensitive) | Stock rises when bonds fall (risk-on) |
| **HYG** (High Yield) | HYG | Credit-correlated (risk-on) | Defensive/quality |

**Correlation Strength:** |r| > 0.7 = STRONG | 0.4-0.7 = MODERATE | < 0.4 = WEAK

### VIX Term Structure Rules

| Structure | VIX Spot vs VIX3M | Market Signal | Options Bias |
|-----------|-------------------|---------------|-------------|
| **CONTANGO** | Spot < 3M (ratio < 1.0) | Normal/complacent | Sell premium (IV likely to decay) |
| **BACKWARDATION** | Spot > 3M (ratio > 1.0) | Fear/stress | Buy premium (hedging demand elevated) |
| **STEEP CONTANGO** | Ratio < 0.85 | Extreme complacency | Sell premium aggressively, but watch for reversal |
| **STEEP BACKWARDATION** | Ratio > 1.10 | Panic/crisis | Buy protection, reduce exposure |

**Key Rule:** Persistent backwardation (>3 days) signals regime change — reduce risk. Contango normalization after a spike = risk-on signal.

### Expected Move Methodology

**Two methods, use the most reliable:**

1. **IV-Based Expected Move:** `EM = Price × IV × √(DTE / 365)`
   - Derived from implied volatility of at-the-money options
   - Best when options are liquid and IV is stable

2. **Straddle-Based Expected Move:** `EM = ATM Straddle Price × 0.85`
   - Uses actual market pricing of ATM straddle
   - The 0.85 multiplier accounts for time decay already embedded in straddle pricing
   - Best when straddle is liquid and tightly quoted

**Usage:** Short strikes for credit spreads should be placed OUTSIDE the expected move range. If a short strike is inside the EM, the trade has <50% probability of profit.

**Tools:** `analyze_intermarket_correlation()`, `analyze_vix_term_structure()`, `calculate_expected_move()`

---

*Last Updated: March 2026 | Extracted from COMPREHENSIVE_REPORT_GENERATOR.md v3.1 + Statistical Validation Framework + Intermarket Analysis Framework*
