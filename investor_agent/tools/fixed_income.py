"""
Fixed Income / Bond Analysis Tools — Phase 2: Full Implementation

5 MCP tools for institutional-grade bond analysis:
  1. monitor_credit_spreads    — FRED OAS + ETF proxy + yield curve + stress score
  2. analyze_bond_allocation   — Tax-aware placement (RRSP/LIRA/TFSA/CCPC)
  3. calculate_bond_beta       — Rolling beta vs AGG, rate regime, SPY hedge
  4. analyze_yield_curve       — Full US+CA curve, butterfly, roll-down, carry
  5. recommend_bond_trades     — BUY/SELL/HOLD per ETF with scoring pipeline

Data sources:
  - FRED API: Yield curve, ICE BofA OAS, breakeven inflation, term premium
  - Bank of Canada Valet API: GoC yields (free, no key)
  - Yahoo Finance: Bond ETF prices and returns
  - Questrade: Account positions and balances (via other tools)
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

# Expanded Bond ETF universe (40+ ETFs)
BOND_ETFS = {
    # ── Canadian Aggregate ──
    "XBB.TO":   {"name": "iShares Canada Aggregate Bond",    "duration": 8,   "risk": "LOW",      "currency": "CAD", "type": "aggregate",     "category": "broad"},
    "ZAG.TO":   {"name": "BMO Aggregate Bond",               "duration": 8,   "risk": "LOW",      "currency": "CAD", "type": "aggregate",     "category": "broad"},
    "VAB.TO":   {"name": "Vanguard CA Aggregate Bond",        "duration": 7.4, "risk": "LOW",      "currency": "CAD", "type": "aggregate",     "category": "broad"},
    "HBB.TO":   {"name": "Horizons CDN Select Universe Bond", "duration": 8,   "risk": "LOW",      "currency": "CAD", "type": "swap_based",    "category": "broad"},
    # ── Canadian Short-Term ──
    "XSB.TO":   {"name": "iShares Short-Term Bond",          "duration": 3,   "risk": "VERY_LOW", "currency": "CAD", "type": "short_term",    "category": "short"},
    "VSB.TO":   {"name": "Vanguard CA Short-Term Bond",       "duration": 2.7, "risk": "VERY_LOW", "currency": "CAD", "type": "short_term",    "category": "short"},
    "ZCS.TO":   {"name": "BMO Short Corporate Bond",          "duration": 3,   "risk": "LOW",      "currency": "CAD", "type": "short_corp",    "category": "short"},
    "XSH.TO":   {"name": "iShares Short-Term Corp Bond",      "duration": 3,   "risk": "LOW",      "currency": "CAD", "type": "short_corp",    "category": "short"},
    "PSA.TO":   {"name": "Purpose Savings ETF",               "duration": 0,   "risk": "VERY_LOW", "currency": "CAD", "type": "savings",       "category": "cash"},
    "CLF.TO":   {"name": "iShares 1-5yr Laddered Corp",       "duration": 3,   "risk": "LOW",      "currency": "CAD", "type": "short_corp",    "category": "short"},
    # ── Canadian Long-Term ──
    "ZFL.TO":   {"name": "BMO Long Federal Bond",             "duration": 15,  "risk": "MODERATE", "currency": "CAD", "type": "long_govt",     "category": "long"},
    "XLB.TO":   {"name": "iShares Core CA Long-Term Bond",    "duration": 15,  "risk": "MODERATE", "currency": "CAD", "type": "long_broad",    "category": "long"},
    # ── Canadian Government ──
    "ZGB.TO":   {"name": "BMO Government Bond",               "duration": 8,   "risk": "LOW",      "currency": "CAD", "type": "govt",          "category": "govt"},
    "XGB.TO":   {"name": "iShares CA Government Bond",        "duration": 8,   "risk": "LOW",      "currency": "CAD", "type": "govt",          "category": "govt"},
    # ── Canadian Corporate ──
    "XCB.TO":   {"name": "iShares Corporate Bond",            "duration": 7,   "risk": "MODERATE", "currency": "CAD", "type": "corporate",     "category": "corp"},
    "ZCM.TO":   {"name": "BMO Mid-Term Corporate Bond",       "duration": 5,   "risk": "LOW_MOD",  "currency": "CAD", "type": "corporate",     "category": "corp"},
    # ── Canadian High Yield ──
    "XHY.TO":   {"name": "iShares CA High Yield Bond",        "duration": 4,   "risk": "HIGH",     "currency": "CAD", "type": "high_yield",    "category": "hy"},
    # ── US-Listed (CAD-Hedged) ──
    "ZMU.TO":   {"name": "BMO Mid-Term US IG Corp Hedged",    "duration": 7,   "risk": "LOW_MOD",  "currency": "CAD", "type": "us_ig_hedged",  "category": "corp"},
    "ZIC.TO":   {"name": "BMO Mid-Term US IG Corp (CAD)",     "duration": 7,   "risk": "LOW_MOD",  "currency": "CAD", "type": "us_ig_hedged",  "category": "corp"},
    # ── US Broad ──
    "AGG":      {"name": "iShares US Aggregate Bond",         "duration": 6,   "risk": "LOW",      "currency": "USD", "type": "aggregate",     "category": "broad"},
    "BND":      {"name": "Vanguard Total Bond Market",        "duration": 6,   "risk": "LOW",      "currency": "USD", "type": "aggregate",     "category": "broad"},
    # ── US Treasury ──
    "TLT":      {"name": "iShares 20+ Year Treasury",         "duration": 17,  "risk": "MODERATE", "currency": "USD", "type": "long_treasury", "category": "long"},
    "IEF":      {"name": "iShares 7-10yr Treasury",           "duration": 7,   "risk": "LOW_MOD",  "currency": "USD", "type": "mid_treasury",  "category": "mid"},
    "SHY":      {"name": "iShares 1-3yr Treasury",            "duration": 2,   "risk": "VERY_LOW", "currency": "USD", "type": "short_treasury","category": "short"},
    # ── US Corporate ──
    "LQD":      {"name": "iShares IG Corporate Bond",         "duration": 8,   "risk": "MODERATE", "currency": "USD", "type": "ig_corporate",  "category": "corp"},
    "HYG":      {"name": "iShares High Yield Corp",           "duration": 4,   "risk": "HIGH",     "currency": "USD", "type": "high_yield",    "category": "hy"},
    # ── US Specialty ──
    "TIP":      {"name": "iShares TIPS",                      "duration": 7,   "risk": "LOW",      "currency": "USD", "type": "tips",          "category": "inflation"},
    "MINT":     {"name": "PIMCO Enhanced Short Maturity",     "duration": 0.3, "risk": "VERY_LOW", "currency": "USD", "type": "ultra_short",   "category": "cash"},
}

# Tax rules per account type (updated for 2026)
ACCOUNT_TAX_RULES = {
    "RRSP":   {"interest_tax": 0,     "cap_gains_tax": 0,      "bond_placement": "EXCELLENT", "note": "Tax-deferred — interest income sheltered"},
    "LIRA":   {"interest_tax": 0,     "cap_gains_tax": 0,      "bond_placement": "EXCELLENT", "note": "Tax-deferred (locked-in) — same as RRSP"},
    "TFSA":   {"interest_tax": 0,     "cap_gains_tax": 0,      "bond_placement": "GOOD",      "note": "Tax-free — US bond interest exempt (IRS 871h QII), but equity cap gains more valuable here"},
    "MARGIN": {"interest_tax": 0.53,  "cap_gains_tax": 0.265,  "bond_placement": "POOR",      "note": "Interest taxed at marginal rate ~53%"},
    "CCPC":   {"interest_tax": 0.5017,"cap_gains_tax": 0.3334, "bond_placement": "POOR",      "note": "CCPC 2026: interest at 50.17%, cap gains at 66.67% inclusion. USE HBB.TO (swap-based) to convert interest→cap gains"},
}

# Regime-based duration and bond allocation targets
# ============================================================
# BOND LESSONS — Educational content indexed by signal/concept
# Mirrors PATTERN_LESSONS from scanner_analyzer.py (Brooks)
# ============================================================

BOND_LESSONS = {
    # ── Yield Curve Signals ──
    "yield_curve_inverted": {
        "name": "Inverted Yield Curve — Recession Warning",
        "quote": "When short-term rates exceed long-term rates, the bond market is pricing in economic contraction.",
        "source": "Campbell Harvey (1986) — yield curve inversion predicted every US recession since 1970",
        "why_it_works": "Banks borrow short and lend long. When the curve inverts, lending is unprofitable — credit contracts, growth slows. The bond market has a better forecasting record than any economist.",
        "what_to_do": "Favor short-duration bonds (SHY, XSB.TO, PSA.TO) until the curve steepens. When steepening begins, aggressively extend duration — that's where the biggest bond gains come from.",
        "what_invalidates": "Central bank yield curve control (e.g., Japan) can keep curves inverted without recession. Also check: is inversion driven by falling long rates (bearish) or rising short rates (hawkish Fed)?",
        "win_rate": "Inverted curve has predicted 8 of last 8 US recessions, with 1-2 false signals over 50 years.",
    },
    "yield_curve_steep": {
        "name": "Steep Yield Curve — Expansion Signal",
        "quote": "A steep curve is the bond market's way of saying: growth is coming, rates will rise.",
        "source": "Federal Reserve research — steep curves precede GDP acceleration",
        "why_it_works": "Steep curve = cheap short-term funding + higher long-term rates. Banks earn wide margins, lending expands, economy grows. Long bonds offer attractive roll-down return as they 'slide down' the curve.",
        "what_to_do": "Extend duration to capture roll-down return. Overweight 5-10Y maturity where the slope is steepest. Corporate bonds outperform in expansion — add IG credit (LQD, XCB.TO).",
        "what_invalidates": "If steepness is driven by rising inflation expectations (not growth), long bonds will underperform. Check breakeven inflation — if >2.8%, the steep curve is an inflation warning, not a growth signal.",
        "win_rate": "Steep curve + tightening spreads = 75%+ probability of positive 12-month bond returns.",
    },
    "yield_curve_steepening": {
        "name": "Curve Steepening — Rate Cuts Approaching",
        "quote": "When the curve steepens from inversion, the market is front-running rate cuts. This is where bond bulls make the most money.",
        "source": "Historical: 2001, 2007, 2019 — steepening preceded Fed cuts by 3-6 months",
        "why_it_works": "Short rates drop as the Fed cuts, but long rates stay anchored or rise (inflation expectations). The spread widens. Long-duration bonds rally hard — TLT gained 25%+ in 2019-2020.",
        "what_to_do": "BEGIN extending duration. Start with 7-10Y (IEF), then add 20Y+ (TLT, ZFL.TO) as cuts materialize. This is the most profitable duration trade in fixed income.",
        "what_invalidates": "If steepening is 'bear steepening' (long rates rising faster than short), that's inflationary — NOT bond-bullish. Check: are 10Y yields rising or falling?",
        "win_rate": "Bull steepening (short rates falling) has 80%+ hit rate for long-bond outperformance over 6 months.",
    },
    "yield_curve_flattening": {
        "name": "Curve Flattening — Reduce Duration",
        "quote": "A flattening curve is the bond market slowly turning bearish. Don't fight the flattener.",
        "source": "Standard fixed income portfolio management — flattening = reduce duration risk",
        "why_it_works": "Flattening usually means the Fed is hiking (short rates rise) or growth is slowing (long rates fall). Either way, long-duration bonds face headwinds. Short-duration preserves capital.",
        "what_to_do": "Shorten duration. Move from TLT/ZFL.TO to IEF/XBB.TO. In severe flattening, go to SHY/XSB.TO/PSA.TO. Monitor for inversion — that's the next phase.",
        "what_invalidates": "If flattening is driven by a 'flight to quality' (long rates drop because of equity crash), long bonds are actually the right trade. Context matters.",
        "win_rate": "Flattening + rising short rates = 70% probability long bonds underperform short bonds.",
    },

    # ── Credit Spread Signals ──
    "spreads_widening": {
        "name": "Credit Spreads Widening — Risk-Off",
        "quote": "When spreads widen, the market is demanding more compensation for credit risk. Fear is rising.",
        "source": "ICE BofA OAS — institutional-grade credit spread data (FRED)",
        "why_it_works": "Widening spreads = investors selling corporate bonds for Treasuries. This is a flight to quality. It precedes equity weakness 70% of the time. High yield (HYG) drops first, then IG (LQD), then equities.",
        "what_to_do": "SELL high yield (HYG, XHY.TO). REDUCE corporate bond exposure (LQD, XCB.TO). BUY government bonds (TLT, ZGB.TO) — they benefit from the flight to quality. Increase overall bond allocation.",
        "what_invalidates": "Brief widening during quarter-end rebalancing or illiquidity events (not fundamental). If widening reverses within 5 days with no equity follow-through, it was technical noise.",
        "win_rate": "HY spread widening >100bp over 30 days → 65% probability of equity drawdown >5% within 60 days.",
    },
    "spreads_tightening": {
        "name": "Credit Spreads Tightening — Risk-On",
        "quote": "Tightening spreads are the bond market's vote of confidence. Corporate bonds are being bought — credit risk is falling.",
        "source": "ICE BofA OAS historical patterns",
        "why_it_works": "Tightening = investors comfortable with credit risk, reaching for yield. Economy is stable or improving. Corporate bonds outperform Treasuries. High yield can return 8-12% annualized in a tightening regime.",
        "what_to_do": "Overweight corporate bonds (LQD, XCB.TO, ZMU.TO). Consider high yield (HYG, XHY.TO) for income. Reduce Treasury overweight. Focus on mid-duration corporates for best risk-adjusted returns.",
        "what_invalidates": "If tightening to historically extreme levels (HY OAS <250bp), spreads have nowhere to go but wider. Check: are spreads tightening to fair value, or to euphoric levels?",
        "win_rate": "Spread tightening + positive carry = 70%+ probability of positive total return over 6 months.",
    },

    # ── Duration Management ──
    "duration_extend": {
        "name": "Extend Duration — Rate Cuts Coming",
        "quote": "Duration is a bond investor's best friend when rates are falling. Every 1% rate drop adds ~duration% to your return.",
        "source": "Fixed Income Mathematics — Duration × Yield Change = Price Change",
        "why_it_works": "Duration measures price sensitivity to rates. A bond with 15-year duration gains ~15% if rates drop 1%. When the Fed cuts, long bonds rally hardest. TLT gained 20%+ in the 2019-2020 cutting cycle.",
        "what_to_do": "Extend from short-duration (SHY, XSB.TO) to long-duration (TLT, ZFL.TO, XLB.TO). The more confident you are in rate cuts, the longer your duration should be. Each year of duration = 1% gain per 1% rate drop.",
        "what_invalidates": "If inflation reignites, the Fed pauses or reverses cuts — long duration gets crushed. Always pair duration extension with inflation monitoring (breakeven inflation, TIP performance).",
        "win_rate": "Duration extension when 10Y yield is >1% above Fed Funds rate → 75% probability of outperformance.",
    },
    "duration_reduce": {
        "name": "Reduce Duration — Protect Capital",
        "quote": "In a rising rate environment, short duration is not just conservative — it's the only rational choice.",
        "source": "2022 bond crash: AGG lost 13%, TLT lost 31%. Short-term bonds (SHY) lost only 3%.",
        "why_it_works": "Rising rates devastate long bonds. Duration works both ways — if you're long 15-year duration and rates rise 2%, you lose 30%. Short-duration bonds have less rate sensitivity and roll over at higher rates faster.",
        "what_to_do": "Move to short-duration: SHY (1-3Y Treasury), XSB.TO (CA short-term), PSA.TO (savings/cash), MINT (ultra-short). Accept lower yield for capital preservation. Re-extend when the Fed signals a pause.",
        "what_invalidates": "If the rate increase is a one-time adjustment (not a hiking cycle), the duration reduction may sacrifice carry for no reason. Check: is the Fed hiking, or is this a market-driven move?",
        "win_rate": "Short duration during Fed hiking cycles outperforms long duration 85% of the time.",
    },

    # ── Inflation Signals ──
    "buy_tips": {
        "name": "Breakeven Inflation Rising — Buy TIPS",
        "quote": "When breakeven inflation exceeds 2.5%, the market is telling you: real assets beat nominal assets.",
        "source": "FRED T5YIE/T10YIE — market-implied inflation expectations",
        "why_it_works": "TIPS pay a real yield + inflation adjustment. When breakevens are high, nominal bonds lose real purchasing power — you earn 4% but inflation eats 3.5%. TIPS protect against this erosion. They outperform nominals when actual inflation exceeds breakeven.",
        "what_to_do": "Shift from nominal bonds (AGG, XBB.TO) to TIPS (TIP). Also consider: short-duration nominals + TIPS barbell. Canadian alternative: real return bonds (rrb). Reduce long-duration nominal exposure.",
        "what_invalidates": "If breakevens are high but the Fed is aggressively tightening, inflation may fall faster than expected — nominals would outperform. Also: TIPS have duration risk too.",
        "win_rate": "TIPS outperform nominals 70% of the time when 10Y breakeven >2.5% and rising.",
    },
    "buy_nominals": {
        "name": "Breakeven Inflation Falling — Buy Nominal Bonds",
        "quote": "Falling inflation expectations are the most powerful tailwind for traditional bonds.",
        "source": "FRED T10YIE — when breakevens drop below 2%, nominal bonds rally",
        "why_it_works": "When inflation expectations fall, nominal bond yields drop and prices rise. TIPS underperform because their inflation adjustment shrinks. The real yield of nominals rises as inflation drops — you get paid more in real terms.",
        "what_to_do": "Overweight nominal bonds (AGG, TLT, XBB.TO, ZAG.TO). Reduce or exit TIPS. This is the classic 'deflation trade' — long duration nominals are the biggest winners.",
        "what_invalidates": "If breakevens are falling because of recession fears, you want bonds but also need to worry about credit risk. Stick with Treasuries/government bonds, not corporates.",
        "win_rate": "Nominals outperform TIPS 75% of the time when 10Y breakeven <2% and falling.",
    },

    # ── Risk Regime ──
    "risk_off": {
        "name": "Risk-Off Regime — Treasuries Rally",
        "quote": "In a true risk-off event, only government bonds protect you. Corporate bonds are NOT safe havens.",
        "source": "2008, 2020 — TLT rallied 20-30% while HYG dropped 15-25%",
        "why_it_works": "Risk-off = investors dump equities AND corporate bonds for Treasuries. The TLT/SPY negative correlation is your hedge. This is why long-duration Treasuries are in portfolios — not for yield, but for crash protection.",
        "what_to_do": "Overweight long Treasuries (TLT, ZFL.TO). Exit all high yield. Reduce corporate bonds. Government bonds only. The worse equity markets get, the more your Treasury position gains.",
        "what_invalidates": "Stagflationary risk-off (2022) — both stocks AND bonds drop because inflation forces the Fed to hike into weakness. Check: is the risk-off driven by growth fears (bond-bullish) or inflation fears (everything drops)?",
        "win_rate": "TLT gains >5% in 80% of months where SPY drops >5%.",
    },
    "stagflation": {
        "name": "Stagflation — Nothing Works Well",
        "quote": "Stagflation is a bond investor's nightmare: inflation erodes returns while recession kills credit quality.",
        "source": "1970s stagflation — bonds lost real value for a decade. 2022 mini-stagflation — worst bond year ever.",
        "why_it_works": "Stocks and bonds both lose when growth slows AND inflation stays high. The Fed can't cut (inflation) or hike (recession). Traditional bond allocations fail because the stock/bond negative correlation breaks.",
        "what_to_do": "Short duration + TIPS + cash. Avoid all long-duration bonds. MINT, SHY, PSA.TO, TIP are your only tools. Keep powder dry — eventually the Fed breaks one way or the other, and that's when you deploy.",
        "what_invalidates": "If the stagflation is mild and temporary (supply shock resolving), long bonds may still work as recession hedges. True stagflation is rare — most episodes resolve within 12-18 months.",
        "win_rate": "Short duration + TIPS outperforms long duration 90% of the time in stagflationary periods.",
    },

    # ── Tax Placement ──
    "tax_rrsp_bonds": {
        "name": "RRSP/LIRA — The Bond Home",
        "quote": "Bond interest is the most tax-inefficient income. Sheltering it in an RRSP turns a tax liability into a compounding machine.",
        "source": "CRA Tax Rules — interest income taxed at 100% inclusion (vs 50% for cap gains)",
        "why_it_works": "Bond interest is taxed at your full marginal rate (~53% in Ontario). In an RRSP, that interest compounds tax-free. A 4% bond yielding 4% after-tax in RRSP would only yield ~1.9% after-tax in a taxable account. The RRSP doubles your effective bond return.",
        "what_to_do": "Place ALL interest-paying bond ETFs (ZAG.TO, XBB.TO, AGG, IEF) in RRSP/LIRA. Keep equity in TFSA (tax-free cap gains more valuable there). This is the single most impactful tax optimization for Canadian investors.",
        "what_invalidates": "If RRSP room is limited and you have high-conviction equity positions that need shelter, you may choose equity in RRSP. But for pure fixed income allocation, RRSP is unambiguously best.",
        "win_rate": "Tax-aware placement adds 0.5-1.5% annualized return vs naive placement, depending on marginal rate.",
    },
    "tax_ccpc_swap": {
        "name": "CCPC — Use Swap-Based ETFs (HBB.TO)",
        "quote": "In a CCPC, bond interest is taxed at 50.17% passive income rate. Swap-based ETFs convert that interest into capital gains — taxed at only 33.3% effective rate.",
        "source": "2026 CCPC tax rules — cap gains inclusion raised to 66.67%, but still better than 100% interest inclusion at 50.17%",
        "why_it_works": "HBB.TO uses a total return swap instead of holding bonds directly. The return is delivered as capital gains, not interest. At 66.67% inclusion × 50.17% rate = ~33.4% effective tax vs 50.17% on raw interest. Saves ~17% tax on every dollar of bond return.",
        "what_to_do": "In CCPC accounts, use HBB.TO as the primary bond holding. For cash needs, PSA.TO (savings) or XSB.TO (short-term). Accept that HBB.TO doesn't pay distributions — the return is embedded in the price.",
        "what_invalidates": "CRA could reclassify swap-based ETFs (has been discussed). Monitor tax law changes. Also: HBB.TO has slightly higher MER than direct bond ETFs.",
        "win_rate": "HBB.TO saves 15-17% tax on bond returns in CCPC accounts — material for large allocations.",
    },
    "tax_tfsa_equity": {
        "name": "TFSA — Keep Equity, Not Bonds",
        "quote": "Tax-free capital gains in a TFSA are worth more than tax-free interest. The TFSA is equity territory.",
        "source": "CRA TFSA rules + IRS 871(h) Portfolio Interest Exemption for US bonds",
        "why_it_works": "Capital gains are already taxed at 50% inclusion outside TFSA. Sheltering them saves ~26.5% tax. Interest is taxed at 100% inclusion — sheltering saves ~53% tax. BUT: equity expected returns (8-10%) are higher than bond returns (3-5%), so the dollar value of sheltering equity gains is larger despite the lower tax rate.",
        "what_to_do": "Prioritize equity in TFSA. If you must hold US bonds in TFSA, they benefit from IRS 871(h) QII exemption (0% withholding on qualified interest). But the opportunity cost of using TFSA room for bonds is high.",
        "what_invalidates": "In extreme risk-off scenarios where you're 100% bonds across all accounts, TFSA bond allocation makes sense. Also: retirees drawing income may prefer bond stability in TFSA.",
        "win_rate": "Equity in TFSA outperforms bond-in-TFSA by 2-4% annualized on a tax-adjusted basis over 20+ years.",
    },

    # ── Butterfly & Curve Trades ──
    "butterfly_belly_cheap": {
        "name": "Belly Cheap — Overweight Mid-Duration",
        "quote": "When the 5Y point is cheap relative to 2Y and 10Y, it's the bond market's best value play.",
        "source": "Fixed income relative value trading — butterfly 2s5s10s",
        "why_it_works": "The butterfly measures curvature: 2×5Y - 2Y - 10Y. Positive = belly cheap (5Y yields too high relative to wings). This creates a value opportunity: mid-duration bonds (IEF, XBB.TO) offer higher carry per unit of duration than wings.",
        "what_to_do": "Overweight 5-7Y maturities (IEF, ZAG.TO, XBB.TO). This is the 'short butterfly' trade — buy the belly, let curvature normalize. Best implemented with ETFs rather than individual bonds.",
        "what_invalidates": "If the belly is cheap because the market expects the Fed to hike to exactly the 5Y point, it may stay cheap. Check Fed dot plot vs 5Y yield.",
        "win_rate": "Butterfly mean-reverts within 3 months 65% of the time.",
    },
    "butterfly_belly_rich": {
        "name": "Belly Rich — Favor the Wings",
        "quote": "When the 5Y is rich, buy the wings: short-term for safety, long-term for convexity.",
        "source": "Barbell strategy — classic fixed income portfolio construction",
        "why_it_works": "Negative butterfly = 5Y point yields too little relative to 2Y and 10Y. The barbell (SHY + TLT) gives you better carry AND better convexity than a bullet portfolio centered on 5Y.",
        "what_to_do": "Use a barbell: SHY/XSB.TO (short end) + TLT/ZFL.TO (long end). Avoid mid-duration. This maximizes convexity — you gain more when rates move in either direction.",
        "what_invalidates": "If the Fed is on hold for an extended period, the bullet (5Y) may outperform because it's on the steepest part of the curve. Barbell requires rate movement to work.",
        "win_rate": "Barbell outperforms bullet in 70% of periods with >50bp rate movement over 6 months.",
    },

    # ── Carry & Roll-Down ──
    "carry_positive": {
        "name": "Positive Carry — You're Getting Paid to Hold",
        "quote": "Carry is the foundation of bond investing. If you earn more than your financing cost, time is on your side.",
        "source": "AQR Research — carry is the single most important predictor of future bond returns",
        "why_it_works": "Carry = bond yield minus financing cost (short-term rate). Positive carry means every day you hold, you earn the spread. Over 12 months, positive carry has explained 70%+ of total bond returns historically.",
        "what_to_do": "When carry is positive, lean into longer-duration bonds — they offer more carry per dollar invested. The 'carry trade' is: borrow short, lend long. Your ETF does this for you.",
        "what_invalidates": "If rates are rising faster than your carry income, you lose on price more than you earn on carry. Carry is a slow earner; price moves can overwhelm it quickly.",
        "win_rate": "Positive carry strategies have been profitable in 75% of 12-month periods since 1990.",
    },
    "carry_negative": {
        "name": "Negative Carry — Hold Only If Expecting Rate Cuts",
        "quote": "Negative carry means you're paying to hold bonds. The only reason to do this is if you believe rates will drop enough to offset the cost.",
        "source": "Inverted yield curve periods — negative carry is the norm before recessions",
        "why_it_works": "When short rates exceed long rates, every day you hold long bonds costs you money (the spread). But if you're RIGHT about rate cuts, the capital gains from falling long rates will dwarf the carry cost. It's a bet on the Fed's next move.",
        "what_to_do": "Accept negative carry ONLY if you have high conviction on rate cuts within 6-12 months. Otherwise, park in short-term/cash (PSA.TO, MINT, SHY). Negative carry is a ticking clock — you need the capital gain thesis to play out.",
        "what_invalidates": "If the Fed delays cuts longer than expected, negative carry erodes your returns. The carry clock is relentless — you need to be right on timing, not just direction.",
        "win_rate": "Negative carry positions profitable 60% of the time IF rate cuts materialize within 12 months, only 30% otherwise.",
    },

    # ── Term Premium ──
    "term_premium_high": {
        "name": "Term Premium High — Duration Attractive",
        "quote": "When the term premium is positive and rising, long bonds are compensating you for uncertainty. Take the deal.",
        "source": "ACM Term Premium Model (Federal Reserve Bank of New York)",
        "why_it_works": "Term premium = extra yield for holding long-maturity bonds above expected future short rates. When it's high, long bonds offer genuine compensation for duration risk. You're being paid — not just for direction, but for uncertainty itself.",
        "what_to_do": "Extend duration. The term premium is your margin of safety — even if rates don't fall, you earn more than short-term investors. Focus on 10-30Y maturities where term premium concentrates.",
        "what_invalidates": "Term premium can spike during market stress for the wrong reasons (liquidity premium, not real compensation). Check if the spike is accompanied by credit stress — that's a warning, not an opportunity.",
        "win_rate": "Positive term premium >0.5% → 10Y bonds outperform cash 70% of the time over following 12 months.",
    },
    "term_premium_negative": {
        "name": "Term Premium Negative — Flight to Quality",
        "quote": "Negative term premium means investors are paying for the safety of long bonds. They're scared.",
        "source": "ACM Term Premium Model — went deeply negative in 2020, 2016, 2012",
        "why_it_works": "Investors accept LESS yield on long bonds than expected short rates — they're buying insurance, not return. This happens during uncertainty, geopolitical stress, or when central banks are buying bonds (QE).",
        "what_to_do": "Be cautious with long duration — you're not being compensated for the risk. If term premium is negative because of QE, the trade may still work (central bank backstop). If negative because of fear, consider whether the fear is justified.",
        "what_invalidates": "QE can keep term premium negative for years. Don't fight the central bank. If the Fed/BoC is buying, negative term premium doesn't mean 'sell long bonds.'",
        "win_rate": "N/A — term premium direction matters more than level. Watch for inflection from negative to rising.",
    },
}


REGIME_BOND_TARGETS = {
    "EXPANSION":    {"bond_pct": 15, "duration_target": "SHORT",  "preferred": ["SHY", "XSB.TO", "PSA.TO"],             "note": "Growth — minimal bonds, short duration, rates likely rising"},
    "LATE_CYCLE":   {"bond_pct": 25, "duration_target": "MEDIUM", "preferred": ["IEF", "XBB.TO", "TIP", "ZAG.TO"],      "note": "Late cycle — build buffer, add TIPS for inflation"},
    "CONTRACTION":  {"bond_pct": 40, "duration_target": "LONG",   "preferred": ["TLT", "ZAG.TO", "AGG", "ZFL.TO"],      "note": "Recession — max bonds, long duration benefits from rate cuts"},
    "RECOVERY":     {"bond_pct": 20, "duration_target": "MEDIUM", "preferred": ["LQD", "XCB.TO", "ZMU.TO"],             "note": "Recovery — corporates outperform as spreads tighten"},
    "STAGFLATION":  {"bond_pct": 30, "duration_target": "SHORT",  "preferred": ["TIP", "SHY", "MINT", "PSA.TO"],        "note": "Stagflation — short duration + TIPS, avoid long bonds"},
}

# FRED series IDs
FRED_YIELD_SERIES = {
    "1m": "DGS1MO", "3m": "DGS3MO", "6m": "DGS6MO",
    "1y": "DGS1",   "2y": "DGS2",   "3y": "DGS3",
    "5y": "DGS5",   "7y": "DGS7",   "10y": "DGS10",
    "20y": "DGS20", "30y": "DGS30",
}

FRED_CREDIT_SERIES = {
    "ig_oas":  "BAMLC0A0CM",
    "aaa_oas": "BAMLC0A1CAAA",
    "bbb_oas": "BAMLC0A4CBBB",
    "hy_oas":  "BAMLH0A0HYM2",
    "bb_oas":  "BAMLH0A1HYBB",
    "b_oas":   "BAMLH0A2HYB",
    "ccc_oas": "BAMLH0A3HYC",
}

BOC_YIELD_SERIES = {
    "2y":   "BD.CDN.2YR.DQ.YLD",
    "3y":   "BD.CDN.3YR.DQ.YLD",
    "5y":   "BD.CDN.5YR.DQ.YLD",
    "7y":   "BD.CDN.7YR.DQ.YLD",
    "10y":  "BD.CDN.10YR.DQ.YLD",
    "long": "BD.CDN.LONG.DQ.YLD",
    "rrb":  "BD.CDN.RRB.DQ.YLD",
}


# ============================================================
# HELPERS
# ============================================================

def _safe_float(val) -> float:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 0.0
    return round(float(val), 4)


def _get_etf_returns(ticker: str, period: str = "1y") -> pd.Series:
    """Get daily returns for a bond ETF from Yahoo Finance."""
    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    if hist.empty:
        raise ValueError(f"No data for {ticker}")
    if hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)
    returns = hist["Close"].pct_change().dropna()
    returns.name = ticker
    return returns


def _get_fred_series(series_id: str, days: int = 365) -> pd.Series | None:
    """Fetch a FRED time series. Returns None if unavailable."""
    try:
        from fredapi import Fred
        import os
        api_key = os.environ.get("FRED_API_KEY", "")
        if not api_key:
            return None
        fred = Fred(api_key=api_key)
        end = datetime.now()
        start = end - timedelta(days=days)
        data = fred.get_series(series_id, observation_start=start, observation_end=end)
        return data.dropna() if data is not None else None
    except Exception as e:
        logger.warning(f"FRED fetch failed for {series_id}: {e}")
        return None


def _get_fred_latest(series_id: str) -> float | None:
    """Get the latest value from a FRED series."""
    s = _get_fred_series(series_id, days=30)
    if s is not None and not s.empty:
        return float(s.iloc[-1])
    return None


def _get_boc_yields() -> dict[str, float]:
    """Fetch Canadian GoC bond yields from Bank of Canada Valet API (free, no key)."""
    result = {}
    try:
        import urllib.request
        import json
        for label, series_id in BOC_YIELD_SERIES.items():
            url = f"https://www.bankofcanada.ca/valet/observations/{series_id}/json?recent=1"
            req = urllib.request.Request(url, headers={"User-Agent": "investor-agent/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                obs = data.get("observations", [])
                if obs:
                    val = obs[-1].get("v") or obs[-1].get(series_id, {}).get("v")
                    if val is not None:
                        result[label] = float(val)
    except Exception as e:
        logger.warning(f"Bank of Canada API failed: {e}")
    return result


def _get_etf_price_and_yield(ticker: str) -> dict:
    """Get current price and estimated yield for a bond ETF."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist.empty:
            return {}
        price = float(hist["Close"].iloc[-1])
        yld = t.info.get("yield") or t.info.get("trailingAnnualDividendYield") or 0
        vol_20d = 0
        hist_20 = t.history(period="1mo")
        if len(hist_20) >= 5:
            vol_20d = int(hist_20["Volume"].tail(20).mean())
        return {
            "price": round(price, 2),
            "yield_pct": round(float(yld) * 100, 2) if yld else 0,
            "avg_volume_20d": vol_20d,
        }
    except Exception:
        return {}


def _generate_bond_lessons(signals: dict) -> list[dict]:
    """
    Pick relevant BOND_LESSONS based on detected signals.
    Returns a list of lesson dicts with name, quote, why_it_works, what_to_do.
    """
    lessons = []
    seen = set()

    def _add(key):
        if key in BOND_LESSONS and key not in seen:
            seen.add(key)
            lessons.append(BOND_LESSONS[key])

    # Yield curve shape
    shape = signals.get("curve_shape", "").upper()
    if shape == "INVERTED":
        _add("yield_curve_inverted")
    elif shape == "STEEP":
        _add("yield_curve_steep")

    # Yield curve direction
    direction = signals.get("curve_direction", "").upper()
    if direction == "STEEPENING":
        _add("yield_curve_steepening")
    elif direction == "FLATTENING":
        _add("yield_curve_flattening")

    # Credit spreads
    spread_sig = signals.get("oas_signal", "").upper()
    if spread_sig == "WIDENING":
        _add("spreads_widening")
    elif spread_sig == "TIGHTENING":
        _add("spreads_tightening")

    # Duration preference
    dur_pref = signals.get("duration_preference", "").upper()
    if dur_pref in ("LONG", "EXTEND"):
        _add("duration_extend")
    elif dur_pref == "SHORT":
        _add("duration_reduce")

    # Inflation / TIPS
    tips = signals.get("tips_signal", "").upper()
    if tips == "BUY_TIPS":
        _add("buy_tips")
    elif tips == "BUY_NOMINALS":
        _add("buy_nominals")

    # Risk regime
    regime = signals.get("risk_regime", "").upper()
    if regime == "RISK_OFF":
        _add("risk_off")
    elif regime == "STAGFLATION":
        _add("stagflation")

    # Butterfly
    bf = signals.get("butterfly_signal", "").upper()
    if bf == "BELLY_CHEAP":
        _add("butterfly_belly_cheap")
    elif bf == "BELLY_RICH":
        _add("butterfly_belly_rich")

    # Carry
    carry_pos = signals.get("carry_positive")
    if carry_pos is True:
        _add("carry_positive")
    elif carry_pos is False:
        _add("carry_negative")

    # Term premium
    tp = signals.get("term_premium")
    if tp is not None:
        if tp > 0.5:
            _add("term_premium_high")
        elif tp < 0:
            _add("term_premium_negative")

    return lessons


# ============================================================
# TOOL 1: Credit Spread Monitor (UPGRADED with FRED OAS)
# ============================================================

def monitor_credit_spreads_impl() -> dict[str, Any]:
    """Monitor credit spreads using FRED OAS (primary) + ETF proxies (fallback)."""
    result = {
        "credit_spreads": {},
        "oas_spreads": {},
        "risk_regime": {},
        "yield_curve": {},
        "breakeven_inflation": {},
        "term_premium": {},
        "composite": {},
    }

    try:
        # ── FRED ICE BofA OAS (primary — institutional-grade) ──
        oas_data = {}
        for label, series_id in FRED_CREDIT_SERIES.items():
            val = _get_fred_latest(series_id)
            if val is not None:
                oas_data[label] = val

        if oas_data:
            ig = oas_data.get("ig_oas")
            hy = oas_data.get("hy_oas")
            ccc = oas_data.get("ccc_oas")
            bbb = oas_data.get("bbb_oas")
            aaa = oas_data.get("aaa_oas")

            result["oas_spreads"] = {
                "ig_oas": ig,
                "hy_oas": hy,
                "ccc_oas": ccc,
                "bbb_oas": bbb,
                "aaa_oas": aaa,
                "hy_ig_spread": round(hy - ig, 0) if hy and ig else None,
                "bbb_aaa_spread": round(bbb - aaa, 0) if bbb and aaa else None,
                "source": "FRED_ICE_BOFA",
            }

            # Classify from OAS
            if hy and hy > 500:
                oas_signal = "WIDENING"
            elif hy and hy < 300:
                oas_signal = "TIGHTENING"
            else:
                oas_signal = "STABLE"
            result["oas_spreads"]["signal"] = oas_signal

        # ── HYG/LQD ratio (fallback / supplementary) ──
        hyg_hist = yf.Ticker("HYG").history(period="6mo")
        lqd_hist = yf.Ticker("LQD").history(period="6mo")

        if not hyg_hist.empty and not lqd_hist.empty:
            if hyg_hist.index.tz is not None:
                hyg_hist.index = hyg_hist.index.tz_localize(None)
            if lqd_hist.index.tz is not None:
                lqd_hist.index = lqd_hist.index.tz_localize(None)

            common = hyg_hist.index.intersection(lqd_hist.index)
            hyg_close = hyg_hist.loc[common, "Close"]
            lqd_close = lqd_hist.loc[common, "Close"]
            ratio = hyg_close / lqd_close

            current_ratio = _safe_float(ratio.iloc[-1])
            change_20d = _safe_float((ratio.iloc[-1] / ratio.iloc[-20] - 1) * 100) if len(ratio) >= 20 else 0

            if change_20d > 0.5:
                spread_signal = "TIGHTENING"
            elif change_20d < -0.5:
                spread_signal = "WIDENING"
            else:
                spread_signal = "STABLE"

            result["credit_spreads"] = {
                "hyg_lqd_ratio": current_ratio,
                "hyg_lqd_20d_change_pct": change_20d,
                "signal": spread_signal,
            }

        # ── TLT/SPY correlation (risk regime) ──
        tlt_hist = yf.Ticker("TLT").history(period="6mo")
        spy_hist = yf.Ticker("SPY").history(period="6mo")

        if not tlt_hist.empty and not spy_hist.empty:
            if tlt_hist.index.tz is not None:
                tlt_hist.index = tlt_hist.index.tz_localize(None)
            if spy_hist.index.tz is not None:
                spy_hist.index = spy_hist.index.tz_localize(None)

            tlt_ret = tlt_hist["Close"].pct_change().dropna()
            spy_ret = spy_hist["Close"].pct_change().dropna()
            aligned = pd.concat([tlt_ret, spy_ret], axis=1, join="inner").dropna()

            if len(aligned) >= 60:
                aligned.columns = ["tlt", "spy"]
                corr_60d = _safe_float(aligned.iloc[-60:]["tlt"].corr(aligned.iloc[-60:]["spy"]))

                if corr_60d < -0.2:
                    regime = "RISK_OFF" if tlt_ret.iloc[-20:].mean() > 0 else "RISK_ON"
                elif corr_60d > 0.2:
                    regime = "STAGFLATION"
                else:
                    regime = "TRANSITION"

                result["risk_regime"] = {
                    "tlt_spy_correlation_60d": corr_60d,
                    "regime": regime,
                }

        # ── Yield curve (FRED primary, ETF proxy fallback) ──
        ten_yr = _get_fred_latest("DGS10")
        two_yr = _get_fred_latest("DGS2")

        if ten_yr is not None and two_yr is not None:
            slope_bp = round((ten_yr - two_yr) * 100, 1)
            source = "FRED"
        else:
            # Fallback: ^TNX - ^IRX via yfinance
            try:
                tnx = yf.Ticker("^TNX").history(period="5d")
                irx = yf.Ticker("^IRX").history(period="5d")
                if not tnx.empty and not irx.empty:
                    slope_bp = round((float(tnx["Close"].iloc[-1]) - float(irx["Close"].iloc[-1])) * 100, 1)
                    source = "YAHOO_PROXY"
                else:
                    slope_bp = None
                    source = "UNAVAILABLE"
            except Exception:
                slope_bp = None
                source = "UNAVAILABLE"

        if slope_bp is not None:
            if slope_bp > 50:
                curve_signal = "STEEP"
            elif slope_bp < -10:
                curve_signal = "INVERTED"
            else:
                curve_signal = "FLAT"

            result["yield_curve"] = {
                "slope_10y_2y_bp": slope_bp,
                "signal": curve_signal,
                "us_10y": ten_yr,
                "us_2y": two_yr,
                "source": source,
            }

        # ── Breakeven inflation (FRED) ──
        be5 = _get_fred_latest("T5YIE")
        be10 = _get_fred_latest("T10YIE")
        fwd = _get_fred_latest("T5YIFR")

        if be5 is not None or be10 is not None:
            tips_signal = "NEUTRAL"
            if be10 and be10 > 2.8:
                tips_signal = "BUY_TIPS"
            elif be10 and be10 < 2.0:
                tips_signal = "BUY_NOMINALS"

            result["breakeven_inflation"] = {
                "breakeven_5y": be5,
                "breakeven_10y": be10,
                "forward_5y5y": fwd,
                "tips_signal": tips_signal,
            }

        # ── Term premium (FRED ACM) ──
        tp = _get_fred_latest("THREEFYTP10")
        if tp is not None:
            if tp > 0.5:
                tp_note = "Long bonds compensating for risk — duration attractive"
            elif tp > 0:
                tp_note = "Fair compensation — neutral duration"
            else:
                tp_note = "Investors paying for safety — flight to quality"
            result["term_premium"] = {"acm_10y": round(tp, 2), "interpretation": tp_note}

        # ── Composite stress score ──
        stress = 50
        oas_sig = result.get("oas_spreads", {}).get("signal") or result.get("credit_spreads", {}).get("signal", "STABLE")
        if oas_sig == "WIDENING": stress += 20
        elif oas_sig == "TIGHTENING": stress -= 15

        rr = result.get("risk_regime", {}).get("regime", "TRANSITION")
        if rr == "STAGFLATION": stress += 25
        elif rr == "RISK_OFF": stress += 10
        elif rr == "RISK_ON": stress -= 10

        cs = result.get("yield_curve", {}).get("signal", "FLAT")
        if cs == "INVERTED": stress += 15
        elif cs == "STEEP": stress -= 10

        stress = max(0, min(100, stress))
        if stress >= 75: level = "CRISIS"
        elif stress >= 55: level = "STRESS"
        elif stress >= 35: level = "CAUTIOUS"
        else: level = "BENIGN"

        result["composite"] = {
            "credit_stress_score": stress,
            "level": level,
            "bond_allocation_bias": "OVERWEIGHT" if stress >= 55 else ("NEUTRAL" if stress >= 35 else "UNDERWEIGHT"),
        }

        # ── Educational lessons based on detected signals ──
        lesson_signals = {
            "oas_signal": oas_signal,
            "curve_shape": result.get("yield_curve", {}).get("signal", ""),
            "risk_regime": result.get("risk_regime", {}).get("regime", ""),
            "tips_signal": result.get("breakeven_inflation", {}).get("tips_signal", ""),
            "term_premium": result.get("term_premium", {}).get("acm_10y"),
        }
        lessons = _generate_bond_lessons(lesson_signals)
        if lessons:
            result["lessons"] = [
                {"name": l["name"], "quote": l["quote"], "what_to_do": l["what_to_do"], "win_rate": l.get("win_rate", "")}
                for l in lessons
            ]

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Credit spread monitoring failed: {e}", exc_info=True)

    return result


# ============================================================
# TOOL 2: Bond Allocation (UPGRADED with HBB swap + 2026 tax)
# ============================================================

def analyze_bond_allocation_impl(risk_target: str = "MODERATE") -> dict[str, Any]:
    """Recommend bond ETFs with tax-aware account placement. 2026 CCPC rules."""
    risk_map = {"CONSERVATIVE": 40, "MODERATE": 25, "AGGRESSIVE": 10}
    target_bond_pct = risk_map.get(risk_target.upper(), 25)

    result = {
        "risk_target": risk_target,
        "target_bond_pct": target_bond_pct,
        "recommended_purchases": [],
        "account_placement_rules": {},
    }

    try:
        # Get prices for top candidates
        bond_data = {}
        top_tickers = ["ZAG.TO", "XBB.TO", "IEF", "TLT", "XSB.TO", "VSB.TO",
                        "PSA.TO", "HBB.TO", "TIP", "LQD", "SHY", "MINT",
                        "ZFL.TO", "ZMU.TO", "XCB.TO", "HYG", "AGG"]
        for ticker in top_tickers:
            info = BOND_ETFS.get(ticker, {})
            if not info:
                continue
            pdata = _get_etf_price_and_yield(ticker)
            if pdata:
                bond_data[ticker] = {**info, **pdata}

        result["account_placement_rules"] = {
            acct: {"quality": r["bond_placement"], "interest_tax": f"{r['interest_tax']*100:.1f}%", "note": r["note"]}
            for acct, r in ACCOUNT_TAX_RULES.items()
        }

        recs = []

        # RRSP/LIRA: Best for interest-heavy bonds
        for acct in ["RRSP", "LIRA"]:
            etfs = (["ZAG.TO", "XBB.TO"] if risk_target.upper() == "CONSERVATIVE"
                    else ["XSB.TO"] if risk_target.upper() == "AGGRESSIVE"
                    else ["ZAG.TO", "IEF"])
            for etf in etfs:
                if etf in bond_data:
                    recs.append({
                        "account_type": acct, "etf": etf, "name": bond_data[etf]["name"],
                        "price": bond_data[etf].get("price", 0), "yield_pct": bond_data[etf].get("yield_pct", 0),
                        "duration": bond_data[etf]["duration"], "risk": bond_data[etf]["risk"],
                        "rationale": f"Interest sheltered in {acct} (0% tax)",
                        "tax_efficiency": "EXCELLENT",
                    })

        # TFSA: Keep equity, but US bond interest is QII-exempt
        recs.append({
            "account_type": "TFSA", "etf": "KEEP_EQUITY",
            "name": "Equity preferred — tax-free cap gains more valuable",
            "price": 0, "yield_pct": 0, "duration": 0, "risk": "N/A",
            "rationale": "US bond interest exempt (IRS 871h QII), but equity cap gains more valuable tax-free",
            "tax_efficiency": "KEEP_EQUITY",
        })

        # CCPC: Use HBB.TO (swap-based) to avoid 50.17% passive interest tax
        if "HBB.TO" in bond_data:
            recs.append({
                "account_type": "CCPC", "etf": "HBB.TO", "name": bond_data["HBB.TO"]["name"],
                "price": bond_data["HBB.TO"].get("price", 0), "yield_pct": 0,
                "duration": bond_data["HBB.TO"]["duration"], "risk": bond_data["HBB.TO"]["risk"],
                "rationale": "Swap-based: converts interest→cap gains. 2026 CCPC cap gains at 66.67% inclusion still better than 100% interest inclusion at 50.17%",
                "tax_efficiency": "BEST_FOR_CCPC",
            })
        # Also short-term for cash needs
        for etf in ["PSA.TO", "XSB.TO"]:
            if etf in bond_data:
                recs.append({
                    "account_type": "CCPC", "etf": etf, "name": bond_data[etf]["name"],
                    "price": bond_data[etf].get("price", 0), "yield_pct": bond_data[etf].get("yield_pct", 0),
                    "duration": bond_data[etf]["duration"], "risk": bond_data[etf]["risk"],
                    "rationale": "Short duration for cash needs — interest taxed at 50.17%",
                    "tax_efficiency": "POOR",
                })

        result["recommended_purchases"] = recs

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Bond allocation failed: {e}", exc_info=True)

    return result


# ============================================================
# TOOL 3: Bond Beta (UNCHANGED — already solid)
# ============================================================

def calculate_bond_beta_impl(ticker: str, benchmark: str = "AGG", window_days: int = 120) -> dict[str, Any]:
    """Calculate rolling beta for a bond ETF vs benchmark."""
    result = {"ticker": ticker, "benchmark": benchmark, "window_days": window_days}

    try:
        etf_returns = _get_etf_returns(ticker, period="2y")
        bench_returns = _get_etf_returns(benchmark, period="2y")
        spy_returns = _get_etf_returns("SPY", period="2y")

        aligned = pd.concat([etf_returns, bench_returns, spy_returns], axis=1, join="inner").dropna()
        if len(aligned) < window_days:
            result["error"] = f"Insufficient data: {len(aligned)} days (need {window_days})"
            return result

        aligned.columns = ["etf", "benchmark", "spy"]
        recent = aligned.iloc[-window_days:]

        cov_bench = recent["etf"].cov(recent["benchmark"])
        var_bench = recent["benchmark"].var()
        beta_vs_bench = cov_bench / var_bench if var_bench > 0 else 1.0

        # Beta trend
        slope = 0
        beta_trend = "STABLE"
        if len(aligned) >= window_days + 20:
            betas = []
            for i in range(20):
                offset = -(20 - i)
                w = aligned.iloc[offset - window_days:offset] if offset < 0 else aligned.iloc[-window_days:]
                c = w["etf"].cov(w["benchmark"])
                v = w["benchmark"].var()
                betas.append(c / v if v > 0 else 1.0)
            slope = np.polyfit(range(len(betas)), betas, 1)[0]
            beta_trend = "RISING" if slope > 0.003 else ("FALLING" if slope < -0.003 else "STABLE")

        # SPY hedge
        corr_vs_spy = _safe_float(recent["etf"].corr(recent["spy"]))
        cov_spy = recent["etf"].cov(recent["spy"])
        var_spy = recent["spy"].var()
        beta_vs_spy = cov_spy / var_spy if var_spy > 0 else 0

        # Rate regime beta
        rate_rising = aligned[aligned["benchmark"] < 0]
        rate_falling = aligned[aligned["benchmark"] > 0]
        if len(rate_rising) >= 30 and len(rate_falling) >= 30:
            rising_beta = rate_rising["etf"].cov(rate_rising["benchmark"]) / rate_rising["benchmark"].var()
            falling_beta = rate_falling["etf"].cov(rate_falling["benchmark"]) / rate_falling["benchmark"].var()
        else:
            rising_beta = falling_beta = beta_vs_bench

        hedge = ("EXCELLENT" if corr_vs_spy < -0.3 else
                 "GOOD" if corr_vs_spy < -0.1 else
                 "POOR" if corr_vs_spy < 0.2 else "NOT_A_HEDGE")

        etf_info = BOND_ETFS.get(ticker, {})
        result.update({
            "etf_name": etf_info.get("name", ticker),
            "duration": etf_info.get("duration", "unknown"),
            "risk_level": etf_info.get("risk", "unknown"),
            "current_beta_vs_benchmark": _safe_float(beta_vs_bench),
            "beta_trend": beta_trend,
            "beta_trend_slope": _safe_float(slope),
            "rate_regime_beta": {
                "rising_rate_beta": _safe_float(rising_beta),
                "falling_rate_beta": _safe_float(falling_beta),
                "asymmetry": _safe_float(rising_beta - falling_beta),
            },
            "vs_spy": {
                "correlation_60d": corr_vs_spy,
                "beta_vs_spy": _safe_float(beta_vs_spy),
                "hedge_effectiveness": hedge,
            },
        })

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Bond beta failed for {ticker}: {e}", exc_info=True)

    return result


# ============================================================
# TOOL 4: Yield Curve Analysis (NEW)
# ============================================================

def analyze_yield_curve_impl() -> dict[str, Any]:
    """Full US + Canadian yield curve analysis with butterfly, roll-down, carry."""
    result = {"us_curve": {}, "canadian_curve": {}, "butterfly": {}, "roll_down": {}, "carry": {}, "implications": []}

    try:
        # ── US Yield Curve (FRED primary, yfinance fallback) ──
        us_points = {}
        for label, series_id in FRED_YIELD_SERIES.items():
            val = _get_fred_latest(series_id)
            if val is not None:
                us_points[label] = round(val, 3)

        if not us_points:
            # Fallback: yfinance treasury proxies
            yf_map = {"3m": "^IRX", "5y": "^FVX", "10y": "^TNX", "30y": "^TYX"}
            for label, sym in yf_map.items():
                try:
                    h = yf.Ticker(sym).history(period="5d")
                    if not h.empty:
                        us_points[label] = round(float(h["Close"].iloc[-1]), 3)
                except Exception:
                    pass

        if us_points:
            y2 = us_points.get("2y")
            y5 = us_points.get("5y")
            y10 = us_points.get("10y")
            y30 = us_points.get("30y")

            slope_2s10s = round((y10 - y2) * 100, 1) if y10 and y2 else None
            slope_2s30s = round((y30 - y2) * 100, 1) if y30 and y2 else None

            if slope_2s10s is not None:
                shape = "STEEP" if slope_2s10s > 50 else ("INVERTED" if slope_2s10s < -10 else "FLAT")
            else:
                shape = "UNKNOWN"

            # Detect direction from recent FRED data
            curve_direction = "UNKNOWN"
            t10y2y_series = _get_fred_series("T10Y2Y", days=60)
            if t10y2y_series is not None and len(t10y2y_series) >= 20:
                recent_slope = t10y2y_series.iloc[-5:].mean()
                older_slope = t10y2y_series.iloc[-20:-15].mean()
                if recent_slope > older_slope + 0.05:
                    curve_direction = "STEEPENING"
                elif recent_slope < older_slope - 0.05:
                    curve_direction = "FLATTENING"
                else:
                    curve_direction = "STABLE"

            result["us_curve"] = {
                "points": us_points,
                "shape": shape,
                "slope_2s10s_bp": slope_2s10s,
                "slope_2s30s_bp": slope_2s30s,
                "direction": curve_direction,
                "source": "FRED" if len(us_points) > 4 else "YAHOO_PROXY",
            }

            # ── Butterfly (2s5s10s) ──
            if y2 and y5 and y10:
                butterfly = round((2 * y5 - y2 - y10) * 100, 1)  # in basis points
                # Long butterfly = buy wings (2Y+10Y), sell belly (5Y) — positive convexity
                # Short butterfly = buy belly (5Y), sell wings — negative convexity
                if butterfly > 10:
                    bf_signal = "BELLY_CHEAP"
                    bf_trade = "Short butterfly: buy 5Y (belly) — belly is cheap relative to wings"
                elif butterfly < -10:
                    bf_signal = "BELLY_RICH"
                    bf_trade = "Long butterfly: buy 2Y+10Y (wings) — belly is rich relative to wings"
                else:
                    bf_signal = "FAIR"
                    bf_trade = "No curvature trade — butterfly near zero"

                result["butterfly"] = {
                    "value_bp": butterfly,
                    "signal": bf_signal,
                    "trade": bf_trade,
                }

            # ── Roll-down return ──
            # Roll-down = yield difference × duration for adjacent maturities
            roll_down = {}
            pairs = [("5y", "3y", 4.5), ("10y", "7y", 8), ("30y", "20y", 22)]
            for long, short, approx_dur in pairs:
                if long in us_points and short in us_points:
                    rd = round((us_points[long] - us_points[short]) * approx_dur, 2)
                    roll_down[f"roll_{long}"] = rd

            if roll_down:
                best_pos = max(roll_down, key=roll_down.get)
                result["roll_down"] = {
                    **roll_down,
                    "best_position": best_pos.replace("roll_", ""),
                    "best_roll_down_pct": roll_down[best_pos],
                }

            # ── Carry analysis ──
            short_rate = us_points.get("3m") or us_points.get("1m")
            if short_rate:
                carry = {}
                for tenor in ["5y", "10y", "30y"]:
                    if tenor in us_points:
                        carry[f"carry_{tenor}"] = round(us_points[tenor] - short_rate, 2)
                result["carry"] = {
                    **carry,
                    "financing_rate": short_rate,
                    "carry_positive": any(v > 0 for v in carry.values()),
                }

        # ── Canadian Curve (Bank of Canada Valet API) ──
        ca_points = _get_boc_yields()
        if ca_points:
            ca_2y = ca_points.get("2y")
            ca_10y = ca_points.get("10y")
            ca_slope = round((ca_10y - ca_2y) * 100, 1) if ca_10y and ca_2y else None
            ca_shape = "STEEP" if ca_slope and ca_slope > 50 else ("INVERTED" if ca_slope and ca_slope < -10 else "FLAT")

            result["canadian_curve"] = {
                "points": ca_points,
                "shape": ca_shape,
                "slope_10y_2y_bp": ca_slope,
                "rrb_yield": ca_points.get("rrb"),
                "source": "BANK_OF_CANADA",
            }

        # ── Implications ──
        impls = []
        shape = result.get("us_curve", {}).get("shape")
        direction = result.get("us_curve", {}).get("direction")

        if shape == "INVERTED":
            impls.append("Yield curve inverted — recession signal active. Favor short duration or prepare to extend on steepening.")
        elif shape == "STEEP":
            impls.append("Yield curve steep — expansionary. Roll-down return attractive at 5-10Y.")

        if direction == "STEEPENING":
            impls.append("Curve steepening — rate cuts approaching. Begin extending duration.")
        elif direction == "FLATTENING":
            impls.append("Curve flattening — reduce duration exposure.")

        bf = result.get("butterfly", {})
        if bf.get("signal") == "BELLY_CHEAP":
            impls.append(f"Butterfly {bf.get('value_bp')}bp — 5Y belly cheap. Consider overweight mid-duration ETFs (IEF).")
        elif bf.get("signal") == "BELLY_RICH":
            impls.append(f"Butterfly {bf.get('value_bp')}bp — 5Y belly rich. Favor wings (SHY + TLT).")

        carry = result.get("carry", {})
        if not carry.get("carry_positive", True):
            impls.append("Negative carry across all maturities — hold only if expecting rate cuts.")

        result["implications"] = impls

        # ── Educational lessons based on detected signals ──
        lesson_signals = {
            "curve_shape": result.get("us_curve", {}).get("shape", ""),
            "curve_direction": result.get("us_curve", {}).get("direction", ""),
            "butterfly_signal": result.get("butterfly", {}).get("signal", ""),
            "carry_positive": result.get("carry", {}).get("carry_positive"),
        }
        lessons = _generate_bond_lessons(lesson_signals)
        if lessons:
            result["lessons"] = [
                {"name": l["name"], "quote": l["quote"], "why_it_works": l["why_it_works"],
                 "what_to_do": l["what_to_do"], "what_invalidates": l.get("what_invalidates", "")}
                for l in lessons
            ]

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Yield curve analysis failed: {e}", exc_info=True)

    return result


# ============================================================
# TOOL 5: Bond Trade Recommendations (NEW)
# ============================================================

def recommend_bond_trades_impl(
    risk_target: str = "MODERATE",
    currency_preference: str = "BOTH",
    include_high_yield: bool = True,
) -> dict[str, Any]:
    """
    Comprehensive bond ETF scanner: scores each ETF on 8 signals,
    produces BUY/SELL/HOLD with tax-optimized account placement.
    """
    result = {
        "risk_target": risk_target,
        "currency_preference": currency_preference,
        "macro_bond_environment": {},
        "recommendations": [],
        "account_allocation": {},
        "summary": {},
    }

    try:
        # ── Gather all signals ──
        credit = monitor_credit_spreads_impl()
        curve = analyze_yield_curve_impl()

        # Extract key signals
        stress = credit.get("composite", {}).get("credit_stress_score", 50)
        stress_level = credit.get("composite", {}).get("level", "CAUTIOUS")
        oas_signal = credit.get("oas_spreads", {}).get("signal") or credit.get("credit_spreads", {}).get("signal", "STABLE")
        risk_regime = credit.get("risk_regime", {}).get("regime", "TRANSITION")
        curve_shape = curve.get("us_curve", {}).get("shape", "FLAT")
        curve_dir = curve.get("us_curve", {}).get("direction", "STABLE")
        tips_signal = credit.get("breakeven_inflation", {}).get("tips_signal", "NEUTRAL")
        butterfly = curve.get("butterfly", {}).get("signal", "FAIR")
        carry_positive = curve.get("carry", {}).get("carry_positive", True)
        tp = credit.get("term_premium", {}).get("acm_10y")

        # Determine duration preference from regime
        if curve_shape == "INVERTED" and curve_dir == "STEEPENING":
            duration_pref = "EXTEND"
        elif curve_shape == "INVERTED":
            duration_pref = "SHORT"
        elif curve_shape == "STEEP":
            duration_pref = "LONG"
        else:
            duration_pref = "NEUTRAL"

        result["macro_bond_environment"] = {
            "credit_stress": stress,
            "credit_stress_level": stress_level,
            "oas_signal": oas_signal,
            "risk_regime": risk_regime,
            "curve_shape": curve_shape,
            "curve_direction": curve_dir,
            "duration_preference": duration_pref,
            "tips_signal": tips_signal,
            "butterfly_signal": butterfly,
            "carry_positive": carry_positive,
            "term_premium_10y": tp,
            "overall_bond_bias": "BULLISH" if stress >= 55 else ("BEARISH" if stress < 30 else "NEUTRAL"),
        }

        # ── Score each ETF ──
        scored = []
        filter_ccy = currency_preference.upper()

        for ticker, info in BOND_ETFS.items():
            # Filter by currency
            if filter_ccy == "CAD" and info["currency"] == "USD":
                continue
            if filter_ccy == "USD" and info["currency"] == "CAD":
                continue

            # Filter HY
            if not include_high_yield and info["type"] in ("high_yield",):
                continue

            score = 50  # baseline

            dur = info["duration"]

            # 1. Duration alignment (0-20)
            if duration_pref == "LONG" and dur >= 10:
                score += 20
            elif duration_pref == "LONG" and dur >= 5:
                score += 10
            elif duration_pref == "SHORT" and dur <= 3:
                score += 20
            elif duration_pref == "SHORT" and dur <= 5:
                score += 10
            elif duration_pref == "EXTEND" and dur >= 7:
                score += 15
            elif duration_pref == "NEUTRAL" and 3 <= dur <= 8:
                score += 10
            # Penalize misalignment
            if duration_pref == "SHORT" and dur > 10:
                score -= 15
            if duration_pref == "LONG" and dur < 3:
                score -= 10

            # 2. Credit signal (0-15)
            if info["type"] in ("high_yield",):
                if oas_signal == "TIGHTENING":
                    score += 15
                elif oas_signal == "WIDENING":
                    score -= 20
                else:
                    score += 0
            elif info["type"] in ("ig_corporate", "corporate", "short_corp", "us_ig_hedged"):
                if oas_signal == "TIGHTENING":
                    score += 10
                elif oas_signal == "WIDENING":
                    score -= 10
            elif info["type"] in ("long_treasury", "mid_treasury", "short_treasury", "govt", "long_govt"):
                if oas_signal == "WIDENING":
                    score += 10  # flight to quality benefits govts
                elif oas_signal == "TIGHTENING":
                    score -= 5

            # 3. Carry + roll-down (0-15)
            if carry_positive:
                if dur >= 5:
                    score += 10
                else:
                    score += 5
            else:
                if dur >= 10:
                    score -= 5  # negative carry hurts long bonds

            # Best roll-down position
            best_rd = curve.get("roll_down", {}).get("best_position", "")
            if best_rd == "5y" and 4 <= dur <= 8:
                score += 5
            elif best_rd == "10y" and 7 <= dur <= 12:
                score += 5

            # 4. Inflation alignment (0-10)
            if info["type"] == "tips":
                if tips_signal == "BUY_TIPS":
                    score += 10
                elif tips_signal == "BUY_NOMINALS":
                    score -= 10
                else:
                    score += 3
            elif info["type"] in ("long_treasury", "aggregate"):
                if tips_signal == "BUY_TIPS":
                    score -= 5  # nominals underperform

            # 5. Bond beta / hedge quality (0-10)
            if info["type"] in ("long_treasury",) and risk_regime in ("RISK_OFF", "STAGFLATION"):
                score += 10  # treasuries shine in risk-off
            elif info["type"] in ("high_yield",) and risk_regime == "STAGFLATION":
                score -= 15

            # 6. Tax efficiency (0-10) — swap-based ETFs get bonus for CCPC
            if info["type"] == "swap_based":
                score += 5

            # 7. FX risk (-10 for USD ETFs for CAD investor)
            if info["currency"] == "USD":
                score -= 7

            # 8. Liquidity (penalty for thin ETFs)
            # We don't have live volume here, so use known low-AUM tickers
            low_liquidity = {"CLF.TO", "VSG.TO", "XLB.TO", "ZCM.TO"}
            if ticker in low_liquidity:
                score -= 5

            # Clamp
            score = max(0, min(100, score))

            # Signal
            if score >= 65:
                signal = "BUY"
            elif score >= 40:
                signal = "HOLD"
            else:
                signal = "SELL"

            # Best account
            if info["type"] == "swap_based":
                best_account = "CCPC"
            elif info["currency"] == "USD":
                best_account = "RRSP"  # treaty exemption + no FX cost in registered
            else:
                best_account = "RRSP"

            # Build rationale
            reasons = []
            if duration_pref == "LONG" and dur >= 10:
                reasons.append("duration aligned with regime")
            elif duration_pref == "SHORT" and dur <= 3:
                reasons.append("short duration matches risk-off")
            if oas_signal == "TIGHTENING" and info["type"] in ("high_yield", "ig_corporate", "corporate"):
                reasons.append("credit spreads tightening")
            if oas_signal == "WIDENING" and info["type"] in ("long_treasury", "govt"):
                reasons.append("flight to quality")
            if tips_signal == "BUY_TIPS" and info["type"] == "tips":
                reasons.append("breakeven inflation rising")
            if info["currency"] == "USD":
                reasons.append("FX risk: consider CAD-hedged alternative")
            if info["type"] == "swap_based":
                reasons.append("CCPC-optimal: interest→cap gains conversion")

            scored.append({
                "ticker": ticker,
                "name": info["name"],
                "signal": signal,
                "score": score,
                "duration": dur,
                "currency": info["currency"],
                "type": info["type"],
                "category": info["category"],
                "best_account": best_account,
                "rationale": "; ".join(reasons) if reasons else f"Score {score}/100",
            })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        result["recommendations"] = scored

        # Account allocation summary
        buys = [s for s in scored if s["signal"] == "BUY"]
        result["account_allocation"] = {
            "RRSP": {"etfs": [s["ticker"] for s in buys if s["best_account"] == "RRSP"][:3],
                     "note": "Interest income sheltered"},
            "LIRA": {"etfs": [s["ticker"] for s in buys if s["best_account"] == "RRSP"][:2],
                     "note": "Same as RRSP — locked-in"},
            "TFSA": {"etfs": [], "note": "Keep equity — tax-free cap gains more valuable"},
            "CCPC": {"etfs": [s["ticker"] for s in buys if s["best_account"] == "CCPC"] or ["HBB.TO"],
                     "note": "Swap-based ETFs only — interest at 50.17%"},
        }

        # Summary
        buy_count = sum(1 for s in scored if s["signal"] == "BUY")
        sell_count = sum(1 for s in scored if s["signal"] == "SELL")
        result["summary"] = {
            "total_etfs_scanned": len(scored),
            "buy_signals": buy_count,
            "hold_signals": len(scored) - buy_count - sell_count,
            "sell_signals": sell_count,
            "top_picks": [{"ticker": s["ticker"], "score": s["score"]} for s in scored[:5]],
            "avoid": [{"ticker": s["ticker"], "score": s["score"]} for s in scored if s["signal"] == "SELL"][:3],
        }

        # ── Educational lessons — full context for reports ──
        lesson_signals = {
            "oas_signal": oas_signal,
            "curve_shape": curve_shape,
            "curve_direction": curve_dir,
            "duration_preference": duration_pref,
            "tips_signal": tips_signal,
            "risk_regime": risk_regime,
            "butterfly_signal": butterfly,
            "carry_positive": carry_positive,
            "term_premium": tp,
        }
        lessons = _generate_bond_lessons(lesson_signals)
        if lessons:
            result["lessons"] = [
                {"name": l["name"], "quote": l["quote"], "source": l.get("source", ""),
                 "why_it_works": l["why_it_works"], "what_to_do": l["what_to_do"],
                 "what_invalidates": l.get("what_invalidates", ""), "win_rate": l.get("win_rate", "")}
                for l in lessons
            ]

        # Tax placement lessons — always include these
        result["tax_lessons"] = [
            {"name": BOND_LESSONS["tax_rrsp_bonds"]["name"], "quote": BOND_LESSONS["tax_rrsp_bonds"]["quote"],
             "what_to_do": BOND_LESSONS["tax_rrsp_bonds"]["what_to_do"]},
            {"name": BOND_LESSONS["tax_ccpc_swap"]["name"], "quote": BOND_LESSONS["tax_ccpc_swap"]["quote"],
             "what_to_do": BOND_LESSONS["tax_ccpc_swap"]["what_to_do"]},
            {"name": BOND_LESSONS["tax_tfsa_equity"]["name"], "quote": BOND_LESSONS["tax_tfsa_equity"]["quote"],
             "what_to_do": BOND_LESSONS["tax_tfsa_equity"]["what_to_do"]},
        ]

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Bond trade recommendation failed: {e}", exc_info=True)

    return result


# ============================================================
# MCP TOOL REGISTRATION
# ============================================================

def register_tools(mcp):
    """Register all fixed income MCP tools."""

    @mcp.tool()
    def monitor_credit_spreads() -> dict:
        """
        Monitor credit spread indicators for risk regime detection.

        PRIMARY: FRED ICE BofA OAS (IG, HY, CCC, BBB, AAA spreads).
        FALLBACK: HYG/LQD ETF price ratio as spread proxy.
        Also: TLT/SPY correlation, yield curve, breakeven inflation, term premium.

        Returns:
            - OAS spreads (IG, HY, CCC with HY-IG and BBB-AAA spreads)
            - Credit signal (TIGHTENING/WIDENING/STABLE)
            - Risk regime (RISK_ON/RISK_OFF/STAGFLATION)
            - Yield curve (STEEP/FLAT/INVERTED with source)
            - Breakeven inflation (5Y, 10Y, TIPS signal)
            - Term premium (ACM 10Y)
            - Composite stress score 0-100 (BENIGN/CAUTIOUS/STRESS/CRISIS)
        """
        return monitor_credit_spreads_impl()

    @mcp.tool()
    def analyze_bond_allocation(risk_target: str = "MODERATE") -> dict:
        """
        Recommend bond ETF allocation with tax-aware account placement.

        2026 Canadian tax rules:
        - RRSP/LIRA: Bond ETFs (interest income tax-sheltered) — BEST
        - TFSA: Keep equity (tax-free cap gains more valuable; US bond interest QII-exempt)
        - CCPC: HBB.TO swap-based (converts interest→cap gains; 66.67% inclusion < 100% interest)
        - Margin: Short-duration only (interest at ~53% marginal)

        Args:
            risk_target: CONSERVATIVE (40% bonds) / MODERATE (25%) / AGGRESSIVE (10%)
        """
        return analyze_bond_allocation_impl(risk_target)

    @mcp.tool()
    def calculate_bond_beta(ticker: str, benchmark: str = "AGG", window_days: int = 120) -> dict:
        """
        Calculate rolling beta for a bond ETF vs benchmark.

        Measures: beta vs AGG, beta trend, rate regime asymmetry
        (rising vs falling rates), and hedge effectiveness vs SPY.

        Args:
            ticker: Bond ETF symbol (e.g., TLT, HYG, XBB.TO)
            benchmark: Bond benchmark ETF (default AGG)
            window_days: Rolling window for beta calculation
        """
        return calculate_bond_beta_impl(ticker, benchmark, window_days)

    @mcp.tool()
    def analyze_yield_curve() -> dict:
        """
        Full US + Canadian yield curve analysis.

        US curve from FRED (11 points: 1M through 30Y) or Yahoo Finance fallback.
        Canadian curve from Bank of Canada Valet API (free, no key).

        Returns:
            - Full yield curve points (US + Canada)
            - Shape (STEEP/FLAT/INVERTED) and direction (STEEPENING/FLATTENING)
            - Butterfly 2s5s10s (curvature trade signal)
            - Roll-down return (best maturity position)
            - Carry analysis (yield - financing cost)
            - Trading implications
        """
        return analyze_yield_curve_impl()

    @mcp.tool()
    def recommend_bond_trades(
        risk_target: str = "MODERATE",
        currency_preference: str = "BOTH",
        include_high_yield: bool = True,
    ) -> dict:
        """
        Comprehensive bond ETF recommendation engine.

        Scans 28+ bond ETFs, combines 8 macro/credit/rate signals into
        BUY/SELL/HOLD per ETF with conviction score (0-100).

        Signals used: yield curve shape, curve direction, butterfly,
        credit spreads (OAS), breakeven inflation, term premium,
        roll-down return, carry, rate regime, bond beta.

        Tax-aware account placement: RRSP (interest-sheltered), CCPC (HBB swap),
        TFSA (keep equity), with FX risk adjustment for USD ETFs.

        Args:
            risk_target: CONSERVATIVE / MODERATE / AGGRESSIVE
            currency_preference: CAD / USD / BOTH
            include_high_yield: Include high yield ETFs in scan
        """
        return recommend_bond_trades_impl(risk_target, currency_preference, include_high_yield)
