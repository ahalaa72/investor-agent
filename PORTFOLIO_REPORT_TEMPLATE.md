# DAILY PORTFOLIO REPORT TEMPLATE

**Report Structure:** ~200 lines per run | **Time:** 5 min context + 90 sec per position (with 4-gate validation)

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
| **2. FRESHNESS** | Is it fresh? | Exhausted? | Score <50 | Score 50-70 | Score >70 |
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

#### Gate 1: Catalyst Lifecycle [detect_catalyst_strength]

| Metric | Value | Status |
|--------|-------|--------|
| Primary Catalyst | [Earnings/Product/FDA/etc.] | [Active/Exhausted/Failed] |
| Catalyst Date | YYYY-MM-DD | [X days ago/away] |
| Next Catalyst | [Description] | In X days |
| Catalyst Stage | [PRE/ACTIVE/POST/EXHAUSTED] | - |

**Catalyst Verdict:** [ACTIVE ✅ / EXHAUSTED ⚠️ / FAILED ❌]

---

#### Gate 2: Freshness/Exhaustion [analyze_volume_tool]

| Metric | Value | Signal |
|--------|-------|--------|
| Trend Days | X consecutive | [Fresh ≤5 / Extended 6-10 / Exhausted >10] |
| Exhaustion Score | XX/100 | [Fresh <50 / Tired 50-70 / Exhausted >70] |
| CVD Trend | [RISING/FALLING/FLAT] | [Aligned/Diverging] |
| CVD Divergence | [NONE/BULLISH/BEARISH] | [No warning / Warning!] |
| VWAP σ Distance | X.XX | [Sustainable <2 / Extended 2-3 / Extreme >3] |

**Freshness Verdict:** [FRESH ✅ / TIRED ⚠️ / EXHAUSTED ❌]

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
*Al Brooks Price Action + McMillan Options + Smart Money Detection*
*Saved to: /Users/AhmedE/Ahmed/PORTFOLIO_DAILY_YYYY-MM-DD.md*
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
