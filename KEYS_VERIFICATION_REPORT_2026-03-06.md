# KEYS (Keysight Technologies) - Audit Verification Report

**Date:** 2026-03-06
**Stock Price:** ~$302
**Purpose:** Resolve 6 discrepancies flagged between original MCP report and Gemini audit

---

## 1. Max Pain Verification (April 17, 2026 Options)

**Original Report:** $260 | **Gemini Audit:** $210 | **Discrepancy:** 13% vs 30% downside gravity

### Finding: UNABLE TO VERIFY -- Expiration May Not Exist Yet

- Multiple options data sources show KEYS currently lists **February 20, May 15, and June 18** as 2026 expirations. The **April 17, 2026 expiration is not yet listed** on most chains.
- All automated attempts to scrape max pain data from maximum-pain.com, swaggystocks.com, barchart.com, optioncharts.io, Yahoo Finance, and Nasdaq returned 403 errors.
- With KEYS at $302, both $260 and $210 are substantially below current price (14% and 30% respectively).

### Action Required
Check manually in your browser:
1. https://maximum-pain.com/options/KEYS
2. https://www.barchart.com/stocks/quotes/KEYS/max-pain-chart
3. https://swaggystocks.com/dashboard/options-max-pain/KEYS

**Verdict:** Neither $260 nor $210 can be confirmed. If the April 17 expiration doesn't exist yet, both figures may have been fabricated. **Do not trade options based on either max pain figure until manually verified.**

---

## 2. Insider Selling Severity

**MCP Conflict:** CLUSTER module showed 0 sells; Catalyst module flagged "Insider Sell detected"

### Finding: HEAVY INSIDER SELLING CONFIRMED -- Catalyst Module Was Correct

| Insider | Title | Date | Shares | Value | Type |
|---------|-------|------|--------|-------|------|
| Ronald Nersesian | Director/Former CEO | Dec 2, 2025 | 30,000 | $5.9M | 10b5-1 |
| John Page | SVP | Dec 10-12, 2025 | 15,000 | $3.2M | 10b5-1 |
| **Satish Dhanasekaran** | **CEO** | Dec 1 & 9, 2025 | **16,758** | **$3.35M** | **10b5-1** |
| Ingrid Estrada | SVP | Dec 1, 2025 + Feb 20, 2026 | 6,827 | $1.42M | 10b5-1 |
| Kailash Narayanan | SVP | Dec 1, 2025 | 3,201 | $629K | 10b5-1 |
| **Neil Dougherty** | **CFO** | Dec 22, 2025 | **1,000** | **$203K** | Planned |
| Jo Ann Juskie | SVP | Feb 27, 2026 | 1,000 | $304K | -- |
| Sung Yoon | SVP | Dec 30, 2025 | 889 | $184K | -- |

**Aggregate:** ~74,675 shares sold, ~$15.7M total. **ZERO insider purchases.** 100% sell / 0% buy ratio.

### Assessment

- **Both CEO and CFO sold into post-earnings strength** -- this is the red flag scenario.
- All major sales were under pre-arranged 10b5-1 plans (adopted May 2025), which reduces the "panic selling" interpretation.
- However, 10b5-1 plans are set up precisely when insiders anticipate wanting to sell. The timing (December 2025, post Q4 FY2025 results) and volume ($15.7M across 8+ insiders) is notable.
- CEO retained ~125,732 shares; CFO retained ~127,833 shares -- substantial positions remain.

**Verdict:** Insider selling is real and broad-based. The CLUSTER module (0 sells) was wrong; the Catalyst module was correct. While 10b5-1 plans mitigate the alarm, the breadth (8+ insiders, zero buyers) and C-suite participation warrant **reducing conviction by at least 1 tier**. This is not a pass/fail signal on its own, but it tilts the risk-reward negatively.

---

## 3. F-Score 2/9 Balance Sheet Drill-Down

**Question:** Are the 7 failing Piotroski criteria cash flow/debt related (value trap) or accounting artifacts?

### Finding: SCORE HAS RECOVERED TO 9/9 -- The 2/9 Was Based on Stale FY2024 Data

The "2/9" figure was calculated on **FY2024 data** (ended October 2024), which was a severe cyclical trough compounded by M&A accounting distortions. As of FY2025 data (ended October 2025), GuruFocus reports **9/9**.

#### FY2024 Failures (4-5 criteria failed):

| # | Criterion | FY2024 Result | Why It Failed |
|---|-----------|---------------|---------------|
| 1 | Positive net income | FAIL (Q4 only) | $315M one-time Singapore tax charge created Q4 GAAP loss of -$73M |
| 3 | ROA increasing | FAIL | Net income -42% while assets +$1.8B from Spirent acquisition |
| 5 | LT debt decreasing | FAIL | Debt +49.8% ($1.195B -> $1.79B) to fund $1.5B Spirent acquisition |
| 8 | Gross margin increasing | FAIL | Declined ~1.6pp on lower volumes + acquired business mix |
| 9 | Asset turnover increasing | FAIL | Revenue -8.9% while assets ballooned from acquisitions |

#### What Passed in FY2024:
- Criterion 2: Positive OCF ($1.05B) -- PASS
- Criterion 4: Cash flow > net income ($1.05B vs $614M) -- PASS
- Criterion 6: Current ratio increasing (2.84 -> 2.98) -- PASS
- Criterion 7: No dilution (shares 179M -> 175M, buybacks active) -- PASS

### Value Trap Assessment: **NO -- These Were Acquisition Artifacts, Not Distress**

- **3 of 5 failures** (criteria 3, 5, 9) are direct consequences of the $1.8B Spirent acquisition -- assets and debt inflate immediately, revenue synergies lag 1-2 years.
- **1 failure** (criterion 8) is cyclical -- FY2024 was the test-and-measurement spending trough. Q1 FY2026 gross margin already recovered to 66.7%.
- **1 failure** (criterion 1) was a non-cash one-time tax charge.
- Cash flow quality was never impaired (OCF consistently exceeded net income).
- Net-debt-to-EBITDA remained conservative at 0.5x.

**Evidence of recovery:** Q1 FY2026 revenue +23% YoY, orders +30%, OCF $441M. F-Score back to 9/9.

**Verdict:** The 2/9 F-Score was stale data from a cyclical trough + M&A accounting collision. The value trap risk is **LOW**. The original report should have flagged this as "historically low, now recovered" rather than presenting it as a current concern.

---

## 4. Freshness Sub-Metrics Verification

**Metrics in question:** CVD, Dalio score (1.19), $5.76B dollar flow, B+ sustainability

### Finding: ALL FOUR ARE PROPRIETARY MODEL OUTPUTS -- Not Independently Verifiable

| Metric | What It Actually Is | Standard? | Verifiable? |
|--------|-------------------|-----------|-------------|
| **CVD** | Approximate buy/sell pressure from daily OHLC bars (not true tick-level CVD) | Concept is real, implementation is approximate | No -- differs from TradingView/Bookmap CVD |
| **Dalio Score (1.19)** | Current VWAP / Prior VWAP ratio. 1.19 = buyers paying 19% more. Novel metric inspired by Dalio's economic machine principles. | **NOT a Dalio-published metric** | No -- proprietary to this codebase |
| **Dollar Flow ($5.76B)** | 20-day net cumulative dollar volume (up-days minus down-days). Not institutional flow tracking. | Not standard (differs from Chaikin MF, MFI) | No -- proprietary heuristic |
| **Sustainability (B+)** | Composite of Dalio ratio, dollar volume momentum, spending efficiency, and price vs. POC. **NOT ESG-related.** | Not standard | No -- proprietary composite |

**Source code:** `investor_agent/technical_analysis_bootstrap.py`
**Design doc:** `RAY_DALIO_ECONOMIC_MACHINE_IMPLEMENTATION.md`

**Verdict:** These metrics are internally consistent and calculated from real price/volume data, but they **cannot be cross-referenced against any external source**. The "Dalio Score" name is misleading -- Ray Dalio never published this metric. These should be treated as **proprietary model signals with unvalidated predictive power**, not as established financial indicators. Use for directional color only, not for conviction scoring.

---

## 5. Options Trade Plan (LONG Direction)

**Request:** Re-run `generate_options_trade_plan(ticker="KEYS", direction="LONG")` for actual spread/OI data.

### Finding: MCP TOOLS NOT AVAILABLE IN THIS ENVIRONMENT

The MCP investor-agent server is not connected in this session, so I cannot execute the tool directly.

**Action Required:** Run this in your MCP-connected environment:
```
generate_options_trade_plan(ticker="KEYS", direction="LONG", account_size=10000, target_dte=45)
```

This will return:
- Actual options chain data with real bid/ask spreads
- Open interest at key strikes
- IV environment assessment
- McMillan-methodology strategy selection
- Position sizing via Half-Kelly criterion

**Verdict:** The original report's spread/OI numbers were flagged as fabricated. **Do not trade options until this tool is re-run with live data.**

---

## 6. Analyst Target Freshness

**Question:** Are Citi ($282), JPM ($300), and UBS ($340) stale pre-earnings targets?

### Finding: ALL THREE TARGETS ARE FRESH -- Updated Post-Q1 FY2026 Earnings (Feb 23-26, 2026)

| Firm | Prior Target | New Target | Rating | Date Updated |
|------|-------------|------------|--------|-------------|
| **UBS** (Andrew Spinola) | $230 | **$340** | Buy | Feb 24, 2026 |
| **Bank of America** | N/A | **$340** | **Upgraded to Buy** | Feb 24, 2026 |
| **Goldman Sachs** | $243 | **$322** | Buy | Feb 24-26, 2026 |
| **Barclays** | $232 | **$320** | Overweight | Feb 24-26, 2026 |
| **JPMorgan Chase** | $255 | **$300** | Overweight | Feb 26, 2026 |
| **Wells Fargo** | $225 | **$300** | Overweight | Feb 24, 2026 |
| **Susquehanna** | -- | **$300** | Positive | Feb 24-26, 2026 |
| **Citigroup** | $220 | **$282** | Buy | Feb 24-26, 2026 |
| **Morgan Stanley** | $227 | **$268** | Equal Weight | Feb 24-26, 2026 |
| **Robert W. Baird** | $230 | **$257** | Outperform | Feb 20, 2026 |

**Consensus:** Moderate Buy | **Average Target:** $295 | **9 Buy / 3 Hold / 0 Sell**

### Context at $302
- Stock is **above** Citi ($282), JPM ($300), Wells Fargo ($300), Morgan Stanley ($268), and Baird ($257) targets.
- Stock is **at** Susquehanna ($300) target.
- Stock is **below** only UBS ($340), BofA ($340), Goldman ($322), and Barclays ($320).
- Meaningful upside exists only to the $320-$340 range (6-13%).

**Verdict:** All targets are freshly updated post-Q1 earnings. However, at $302, KEYS is trading above 6 of 10 analyst targets. The "upside to consensus" argument is weak -- the stock has already priced in the earnings beat. Only the most bullish targets (UBS/BofA at $340) offer >10% upside.

---

## Executive Summary & Conviction Impact

| Item | Original Report | Verified Reality | Impact |
|------|----------------|-----------------|--------|
| Max Pain | $260 | **Unverifiable** (April expiration may not exist) | **Negative** -- cannot assess options gravity |
| Insider Selling | Conflicting (0 sells vs "detected") | **$15.7M across 8+ insiders, CEO+CFO included, zero buys** | **Negative** -- reduce conviction |
| F-Score 2/9 | Presented as current concern | **Stale FY2024 data; now 9/9.** Failures were M&A artifacts. | **Positive** -- value trap risk eliminated |
| Freshness Metrics | Presented as authoritative | **All proprietary, unverifiable, misleadingly named** | **Neutral** -- discount from conviction scoring |
| Options Viability | TIER_2 with fabricated spreads | **Unverified** -- must re-run MCP tool | **Neutral** -- action required before trading |
| Analyst Targets | Assumed fresh | **Confirmed fresh (Feb 2026), but stock above 6/10 targets** | **Slightly Negative** -- limited upside to consensus |

### Net Conviction Adjustment

The F-Score recovery is genuinely positive. But the heavy insider selling (especially C-suite), stock trading above most analyst targets, unverifiable max pain, and proprietary metrics that can't be cross-checked collectively suggest **reducing conviction by 1 full tier** from whatever the original report recommended.

**Key risk:** KEYS at $302 has priced in the Q1 beat. Insiders are selling. Only 4 of 10 analysts see meaningful further upside. The bull case requires continued AI/data-center testing acceleration beyond what's already in guidance.

---

*Generated: 2026-03-06 | Verification methodology: Web research (SEC filings, analyst reports, financial data providers), codebase analysis of proprietary metrics*
