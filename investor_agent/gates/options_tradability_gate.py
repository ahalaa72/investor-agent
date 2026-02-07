"""
Gate 5: Options Tradability Validation

This module implements the 5th gate in the validation system, determining:
1. Whether options are tradable for this ticker
2. Which options strategy to use (based on IV environment)
3. How to construct the optimal position

Integrates with existing institutional features:
- IV Skew Analysis (analyze_iv_skew)
- Term Structure (analyze_iv_term_structure)
- Advanced Greeks (Vanna for earnings protection)
- Portfolio Risk (concentration, beta-weighted delta)

Author: Investor Agent Team
Date: January 28, 2026
"""

import math
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_expected_moves(
    current_price: float,
    iv: float,
    dte: int = 45
) -> dict[str, Any]:
    """
    Calculate 1 SD and 2 SD expected price moves for strike selection.

    Formula: Expected Move = Price × IV × √(DTE/365)

    Standard Deviation Ranges:
    - 1 SD (68% probability): ±1 × Expected Move
    - 2 SD (95% probability): ±2 × Expected Move

    Args:
        current_price: Current stock price
        iv: Implied volatility (decimal, e.g., 0.30 for 30%)
        dte: Days to expiration (default 45 - institutional standard)

    Returns:
        {
            "dte": 45,
            "iv_decimal": 0.30,
            "current_price": 228.00,
            "1sd_move": 24.09,
            "1sd_range": {"low": 203.91, "high": 252.09},
            "2sd_move": 48.18,
            "2sd_range": {"low": 179.82, "high": 276.18},
            "optimal_strikes": {
                "call_16delta": 252,  # 1 SD above (84% OTM probability)
                "call_5delta": 276,   # 2 SD above (95% OTM probability)
                "put_16delta": 204,   # 1 SD below (84% OTM probability)
                "put_5delta": 180     # 2 SD below (95% OTM probability)
            },
            "methodology": "TastyTrade 16-delta optimal for premium selling"
        }

    Reference: TastyTrade Research - "16-delta short strikes have 84% win rate"
    """
    if current_price <= 0 or iv <= 0 or dte <= 0:
        return {
            "error": "Invalid inputs",
            "current_price": current_price,
            "iv_decimal": iv,
            "dte": dte
        }

    # Calculate time factor: √(DTE / 365)
    time_factor = math.sqrt(dte / 365)

    # 1 SD move
    move_1sd = current_price * iv * time_factor

    # 2 SD move
    move_2sd = 2 * move_1sd

    # Calculate ranges
    range_1sd_low = current_price - move_1sd
    range_1sd_high = current_price + move_1sd

    range_2sd_low = current_price - move_2sd
    range_2sd_high = current_price + move_2sd

    # Optimal strikes (rounded to nearest standard strike interval)
    # For stocks $50-$100: round to nearest $2.50
    # For stocks $100-$200: round to nearest $5
    # For stocks $200+: round to nearest $10

    if current_price < 100:
        round_to = 2.5
    elif current_price < 200:
        round_to = 5
    else:
        round_to = 10

    def round_strike(price: float) -> int:
        return int(round(price / round_to) * round_to)

    optimal_strikes = {
        "call_16delta": round_strike(range_1sd_high),
        "call_5delta": round_strike(range_2sd_high),
        "put_16delta": round_strike(range_1sd_low),
        "put_5delta": round_strike(range_2sd_low)
    }

    return {
        "dte": dte,
        "iv_decimal": iv,
        "iv_percent": round(iv * 100, 1),
        "current_price": round(current_price, 2),
        "1sd_move": round(move_1sd, 2),
        "1sd_range": {
            "low": round(range_1sd_low, 2),
            "high": round(range_1sd_high, 2)
        },
        "2sd_move": round(move_2sd, 2),
        "2sd_range": {
            "low": round(range_2sd_low, 2),
            "high": round(range_2sd_high, 2)
        },
        "optimal_strikes": optimal_strikes,
        "methodology": "TastyTrade 16-delta optimal for premium selling",
        "probabilities": {
            "within_1sd": "68%",
            "within_2sd": "95%",
            "beyond_16delta_strike": "16%"
        }
    }


def classify_iv_environment(iv_rank: float) -> dict[str, Any]:
    """
    Classify IV environment and recommend strategy type.

    Classification:
    - HIGH IV (>50%): SELL PREMIUM (credit spreads, iron condors)
    - MEDIUM IV (30-50%): NEUTRAL (debit spreads, calendars)
    - LOW IV (<30%): BUY PREMIUM (long calls/puts, debit spreads)

    Args:
        iv_rank: IV Rank (0-100 scale)

    Returns:
        {
            "iv_rank": 68.2,
            "classification": "HIGH" | "MEDIUM" | "LOW",
            "interpretation": "SELL_PREMIUM" | "NEUTRAL" | "BUY_PREMIUM",
            "recommended_strategies": [
                "Iron Condor",
                "Credit Spreads",
                "Covered Calls"
            ],
            "rationale": str
        }

    Reference: McMillan "Options as a Strategic Investment" Ch. 30
    """
    if iv_rank >= 50:
        classification = "HIGH"
        interpretation = "SELL_PREMIUM"
        strategies = [
            "Iron Condor",
            "Credit Spreads (Bull Put, Bear Call)",
            "Covered Calls",
            "Cash-Secured Puts"
        ]
        rationale = (
            f"IV Rank {iv_rank:.1f}% is in the HIGH range (>50%). "
            "IV is elevated and likely to mean-revert downward. "
            "SELL PREMIUM strategies profit from IV crush and time decay. "
            "Probability of profit: 84% with 16-delta short strikes (TastyTrade research)."
        )
    elif iv_rank >= 30:
        classification = "MEDIUM"
        interpretation = "NEUTRAL"
        strategies = [
            "Debit Spreads",
            "Calendar Spreads",
            "Iron Butterflies",
            "Stock (avoid complexity)"
        ]
        rationale = (
            f"IV Rank {iv_rank:.1f}% is in the MEDIUM range (30-50%). "
            "IV is neither cheap nor expensive. Consider debit spreads for directional conviction "
            "or calendar spreads to profit from term structure. Stock may be simpler."
        )
    else:
        classification = "LOW"
        interpretation = "BUY_PREMIUM"
        strategies = [
            "Long Calls/Puts",
            "Call/Put Debit Spreads",
            "Protective Puts (cheap insurance)"
        ]
        rationale = (
            f"IV Rank {iv_rank:.1f}% is in the LOW range (<30%). "
            "IV is cheap and likely to expand. BUY PREMIUM strategies benefit from IV expansion. "
            "Long options or debit spreads are optimal. Avoid selling premium (low credit received)."
        )

    return {
        "iv_rank": round(iv_rank, 1),
        "classification": classification,
        "interpretation": interpretation,
        "recommended_strategies": strategies,
        "rationale": rationale
    }


def check_liquidity_requirements(
    ticker: str,
    options_data: dict
) -> dict[str, Any]:
    """
    Check if options meet institutional liquidity requirements.

    Requirements (ALL must pass):
    1. Bid/Ask Spread ≤ 5% of mid-price
    2. Open Interest ≥ 100 contracts (≥1000 preferred)
    3. Daily Volume ≥ 50 contracts
    4. Underlying in Tier 1 or Tier 2 liquidity

    Args:
        ticker: Stock symbol
        options_data: Output from analyze_options_mcmillan()

    Returns:
        {
            "status": "PASS" | "FAIL",
            "liquidity_score": 0-100,
            "liquidity_tier": "TIER_1" | "TIER_2" | "TIER_3",
            "checks": {
                "spread": {
                    "status": "PASS" | "FAIL",
                    "spread_pct": 2.1,
                    "threshold": 5.0,
                    "rationale": "Tight spread = low slippage"
                },
                "open_interest": {...},
                "volume": {...},
                "underlying_tier": {...}
            },
            "warnings": [...]
        }
    """
    checks = {}
    warnings = []
    liquidity_score = 0

    # Extract liquidity data from analyze_options_mcmillan output
    # Data is under 'institutional' key
    institutional = options_data.get('institutional', {})
    liquidity_data = institutional.get('liquidity_score', {})
    tier_data = institutional.get('liquidity_tier', {})

    # Check 1: Bid/Ask Spread
    # Get spread from liquidity_score factors
    factors = liquidity_data.get('factors', [])
    spread_pct = 999  # Default if not found
    for factor in factors:
        if 'Spread' in factor:
            # Extract spread percentage from factor string like "Spread 0.2% ≤ 2.0%: +35"
            import re
            match = re.search(r'Spread\s+([\d.]+)%', factor)
            if match:
                spread_pct = float(match.group(1))
                break

    spread_status = "PASS" if spread_pct <= 5.0 else "FAIL"
    checks['spread'] = {
        "status": spread_status,
        "spread_pct": round(spread_pct, 2),
        "threshold": 5.0,
        "rationale": "Tight spread reduces execution cost and slippage"
    }
    if spread_status == "PASS":
        liquidity_score += 30
    else:
        warnings.append(f"Wide spread ({spread_pct:.1f}%) will increase slippage costs")

    # Check 2: Open Interest
    # Extract OI from factors like "OI 15,357: +25"
    avg_oi = 0
    for factor in factors:
        if 'OI ' in factor:
            match = re.search(r'OI\s+([\d,]+)', factor)
            if match:
                avg_oi = int(match.group(1).replace(',', ''))
                break

    oi_status = "PASS" if avg_oi >= 100 else "FAIL"
    oi_tier = "EXCELLENT" if avg_oi >= 1000 else "ADEQUATE" if avg_oi >= 100 else "POOR"
    checks['open_interest'] = {
        "status": oi_status,
        "avg_oi": int(avg_oi),
        "threshold": 100,
        "tier": oi_tier,
        "rationale": "High OI ensures market depth and ability to enter/exit positions"
    }
    if oi_status == "PASS":
        if avg_oi >= 1000:
            liquidity_score += 30  # Excellent OI
        else:
            liquidity_score += 20  # Adequate OI
    else:
        warnings.append(f"Low open interest ({int(avg_oi)}) may cause difficulty exiting positions")

    # Check 3: Daily Volume
    # Extract volume from factors like "Volume 215: +9"
    avg_volume = 0
    for factor in factors:
        if 'Volume ' in factor:
            match = re.search(r'Volume\s+([\d,]+)', factor)
            if match:
                avg_volume = int(match.group(1).replace(',', ''))
                break

    volume_status = "PASS" if avg_volume >= 50 else "FAIL"
    checks['volume'] = {
        "status": volume_status,
        "avg_volume": int(avg_volume),
        "threshold": 50,
        "rationale": "Active trading ensures tight spreads and quick fills"
    }
    if volume_status == "PASS":
        liquidity_score += 20
    else:
        warnings.append(f"Low volume ({int(avg_volume)}) may result in wide spreads intraday")

    # Check 4: Underlying Liquidity Tier
    liquidity_tier = tier_data.get('tier', 'TIER_3')
    tier_status = "PASS" if liquidity_tier in ['TIER_1', 'TIER_2'] else "FAIL"
    checks['underlying_tier'] = {
        "status": tier_status,
        "tier": liquidity_tier,
        "rationale": "Tier 1/2 stocks have reliable options markets"
    }
    if tier_status == "PASS":
        if liquidity_tier == 'TIER_1':
            liquidity_score += 20  # Best tier
        else:
            liquidity_score += 15  # Tier 2
    else:
        warnings.append(f"{ticker} is {liquidity_tier} - options may be illiquid")

    # Overall status: ALL checks must pass
    overall_status = "PASS" if all(
        check['status'] == "PASS" for check in checks.values()
    ) else "FAIL"

    return {
        "status": overall_status,
        "liquidity_score": liquidity_score,
        "liquidity_tier": liquidity_tier,
        "checks": checks,
        "warnings": warnings,
        "recommendation": (
            "Options are liquid and tradable" if overall_status == "PASS"
            else "Trade stock only - options liquidity insufficient"
        )
    }


def integrate_iv_skew(
    iv_skew_data: dict,
    direction: str
) -> dict[str, Any]:
    """
    Integrate IV skew analysis into strategy selection.

    IV Skew Impact:
    - STEEP_PUT_SKEW (>10 pts): Puts expensive → Favor call spreads
    - NORMAL_PUT_SKEW (3-10 pts): Standard → Balanced approach
    - FLAT_SKEW (0-3 pts): Neutral → Standard strategies
    - INVERTED_SKEW (<0 pts): Calls expensive → Favor put spreads

    Args:
        iv_skew_data: Output from analyze_iv_skew()
        direction: "LONG" or "SHORT"

    Returns:
        {
            "skew_type": str,
            "skew_absolute": float,
            "put_spread_edge": "Rich" | "Fair" | "Cheap",
            "call_spread_edge": "Rich" | "Fair" | "Cheap",
            "recommended_adjustment": str,
            "strategy_bias": "CALL_SIDE" | "PUT_SIDE" | "BALANCED"
        }
    """
    # Handle None case
    if not iv_skew_data:
        return {
            "skew_type": "UNKNOWN",
            "skew_absolute": 0,
            "put_spread_edge": "Unknown",
            "call_spread_edge": "Unknown",
            "recommended_adjustment": "Standard structure - no skew data",
            "strategy_bias": "BALANCED"
        }

    skew_summary = iv_skew_data.get('skew_summary', {})
    trading_implications = iv_skew_data.get('trading_implications', {})

    skew_type = skew_summary.get('classification', 'UNKNOWN')
    primary_skew = skew_summary.get('primary_skew', 0)

    put_edge = trading_implications.get('put_spread_edge', 'Fair')
    call_edge = trading_implications.get('call_spread_edge', 'Fair')

    # Determine strategy bias
    if skew_type == 'STEEP_PUT_SKEW':
        strategy_bias = "CALL_SIDE"
        adjustment = "Puts are expensive. Favor call spreads or sell put spreads for extra credit."
    elif skew_type == 'INVERTED_SKEW':
        strategy_bias = "PUT_SIDE"
        adjustment = "Calls are expensive (unusual). Favor put spreads or sell call spreads for extra credit."
    else:
        strategy_bias = "BALANCED"
        adjustment = "Normal skew. Use standard iron condor with balanced wings."

    return {
        "skew_type": skew_type,
        "skew_absolute": round(primary_skew, 2),
        "put_spread_edge": put_edge,
        "call_spread_edge": call_edge,
        "recommended_adjustment": adjustment,
        "strategy_bias": strategy_bias,
        "integration_note": (
            f"Skew analysis suggests {strategy_bias.lower()} bias. "
            f"Adjust iron condor wings: stronger on {strategy_bias.split('_')[0]} side."
        )
    }


def integrate_term_structure(
    term_structure: dict,
    iv_environment: str
) -> dict[str, Any]:
    """
    Integrate term structure analysis for calendar/diagonal strategies.

    Term Structure Impact:
    - CONTANGO (slope >0): Far IV > Near IV → Calendar spreads profitable
    - BACKWARDATION (slope <0): Near IV > Far IV → Avoid calendars, reduce selling
    - FLAT (slope ~0): Neutral → Standard strategies

    Args:
        term_structure: Output from analyze_iv_term_structure()
        iv_environment: "HIGH" | "MEDIUM" | "LOW"

    Returns:
        {
            "structure": "CONTANGO" | "BACKWARDATION" | "FLAT",
            "slope": float,
            "calendar_signal": "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE",
            "diagonal_signal": "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE",
            "integration_note": str
        }
    """
    # Handle None case
    if not term_structure:
        return {
            "structure": "UNKNOWN",
            "slope": 0,
            "calendar_signal": "NEUTRAL",
            "diagonal_signal": "NEUTRAL",
            "integration_note": "Term structure data unavailable"
        }

    structure = term_structure.get('structure_classification', 'UNKNOWN')
    slope = term_structure.get('slope', 0)
    calendar_signal = term_structure.get('calendar_spread_signal', 'NEUTRAL')

    # Diagonal spreads have similar requirements to calendars
    diagonal_signal = calendar_signal

    if structure == 'CONTANGO' and iv_environment == 'MEDIUM':
        integration_note = (
            "Contango term structure + medium IV = IDEAL for calendar spreads. "
            "Sell near-term options, buy far-term to profit from theta differential."
        )
    elif structure == 'BACKWARDATION':
        integration_note = (
            "Backwardation detected (market stress). Near-term IV > far-term IV. "
            "AVOID calendar spreads. Consider reducing premium selling overall."
        )
    else:
        integration_note = (
            f"{structure} term structure. Standard strategies apply. "
            "Calendar spreads are {calendar_signal.lower()}."
        )

    return {
        "structure": structure,
        "slope": round(slope, 4),
        "calendar_signal": calendar_signal,
        "diagonal_signal": diagonal_signal,
        "integration_note": integration_note
    }


def validate_options_tradability(
    ticker: str,
    direction: str,
    current_price: float,
    options_data: dict,
    iv_skew_data: dict,
    term_structure: dict,
    earnings_days: Optional[int],
    account_size: float,
    vanna_data: Optional[dict] = None
) -> dict[str, Any]:
    """
    Gate 5: Validate options tradability and recommend strategy.

    This is the main entry point for Gate 5 validation. It orchestrates all checks:
    1. Liquidity requirements
    2. IV environment classification
    3. Earnings proximity filter
    4. Expected move calculation
    5. IV skew integration
    6. Term structure integration
    7. Vanna protection (if earnings < 45 days)

    Args:
        ticker: Stock symbol
        direction: "LONG" or "SHORT"
        current_price: Current stock price
        options_data: Output from analyze_options_mcmillan()
        iv_skew_data: Output from analyze_iv_skew()
        term_structure: Output from analyze_iv_term_structure()
        earnings_days: Days to next earnings (None if unknown)
        account_size: Account size for position sizing
        vanna_data: Optional Vanna analysis (for earnings protection)

    Returns:
        {
            "gate_status": "PASS" | "FAIL",
            "score": 0-100,
            "checks": {
                "liquidity": {...},
                "iv_environment": {...},
                "earnings_filter": {...},
                "expected_move": {...},
                "skew_integration": {...},
                "term_structure_integration": {...},
                "vanna_protection": {...} | None
            },
            "recommended_strategy": str,
            "strategy_rationale": str,
            "alternatives": list[dict],
            "warnings": list[str],
            "options_viable": bool
        }
    """
    checks = {}
    warnings = []
    gate_score = 0

    # Check 1: Liquidity (MANDATORY - 30 points)
    liquidity_check = check_liquidity_requirements(ticker, options_data)
    checks['liquidity'] = liquidity_check
    gate_score += liquidity_check['liquidity_score'] * 0.3  # Scale to 30 points max

    if liquidity_check['status'] == 'FAIL':
        warnings.extend(liquidity_check['warnings'])
        return {
            "gate_status": "FAIL",
            "score": gate_score,
            "checks": checks,
            "recommended_strategy": "STOCK_ONLY",
            "strategy_rationale": "Liquidity requirements not met. Trade stock instead.",
            "alternatives": [],
            "warnings": warnings,
            "options_viable": False
        }

    # Check 2: IV Environment (20 points)
    iv_rank = options_data.get('iv_analysis', {}).get('iv_rank', 50)
    iv_env = classify_iv_environment(iv_rank)
    checks['iv_environment'] = iv_env
    checks['iv_environment']['status'] = 'PASS'
    gate_score += 20

    # Check 3: Earnings Filter (20 points)
    earnings_status = "PASS"
    earnings_blocked = False

    if earnings_days is not None and earnings_days < 30:
        if iv_env['interpretation'] == 'BUY_PREMIUM':
            # Buying premium with earnings < 30 days = IV crush risk
            earnings_status = "FAIL"
            earnings_blocked = True
            warnings.append(
                f"Earnings in {earnings_days} days. IV crush will hurt long options positions. "
                "BLOCKED for premium buying. Consider selling premium instead (benefits from IV crush)."
            )
        else:
            # Selling premium with earnings < 30 days = opportunity (IV crush = profit)
            earnings_status = "WARN"
            warnings.append(
                f"Earnings in {earnings_days} days. IV crush expected. "
                "This BENEFITS premium sellers (credit received stays, IV drops). "
                "Consider closing 1-2 days before earnings to lock gains."
            )
            gate_score += 20
    else:
        gate_score += 20

    checks['earnings_filter'] = {
        "status": earnings_status,
        "days_to_earnings": earnings_days,
        "buying_blocked": earnings_blocked,
        "rationale": (
            "Earnings proximity affects IV. Buyers avoid <30 days (IV crush risk). "
            "Sellers profit from IV crush."
        )
    }

    if earnings_blocked:
        return {
            "gate_status": "FAIL",
            "score": gate_score,
            "checks": checks,
            "recommended_strategy": "STOCK_ONLY",
            "strategy_rationale": f"Earnings in {earnings_days} days blocks premium buying (IV crush risk).",
            "alternatives": [
                {
                    "strategy": "SELL_PREMIUM",
                    "reason": "Sell premium to benefit from IV crush instead"
                }
            ],
            "warnings": warnings,
            "options_viable": False
        }

    # Check 4: Expected Moves (10 points)
    current_iv = options_data.get('iv_analysis', {}).get('current_iv', 0.30)
    expected_moves = calculate_expected_moves(current_price, current_iv, dte=45)
    checks['expected_move'] = expected_moves
    checks['expected_move']['status'] = 'PASS'
    gate_score += 10

    # Check 5: IV Skew Integration (10 points)
    skew_integration = integrate_iv_skew(iv_skew_data, direction)
    checks['skew_integration'] = skew_integration
    checks['skew_integration']['status'] = 'PASS'
    gate_score += 10

    # Check 6: Term Structure Integration (10 points)
    ts_integration = integrate_term_structure(term_structure, iv_env['classification'])
    checks['term_structure_integration'] = ts_integration
    checks['term_structure_integration']['status'] = 'PASS'
    gate_score += 10

    # Check 7: Vanna Protection (optional, no score impact)
    if vanna_data:
        checks['vanna_protection'] = vanna_data
        warnings.append(
            f"Vanna exposure: {vanna_data.get('total_vanna', 0):.2f}. "
            "Monitor for IV changes near earnings."
        )

    # Strategy Selection Logic
    recommended_strategy = select_strategy(
        iv_env['interpretation'],
        direction,
        skew_integration['strategy_bias'],
        ts_integration['calendar_signal'],
        liquidity_check['liquidity_tier']
    )

    strategy_rationale = build_rationale(
        recommended_strategy,
        iv_env,
        skew_integration,
        ts_integration,
        liquidity_check,
        earnings_days
    )

    alternatives = build_alternatives(
        recommended_strategy,
        iv_env,
        direction
    )

    return {
        "gate_status": "PASS",
        "score": round(gate_score, 1),
        "checks": checks,
        "recommended_strategy": recommended_strategy,
        "strategy_rationale": strategy_rationale,
        "alternatives": alternatives,
        "warnings": warnings,
        "options_viable": True
    }


def select_strategy(
    iv_interpretation: str,
    direction: str,
    skew_bias: str,
    calendar_signal: str,
    liquidity_tier: str
) -> str:
    """
    Select optimal strategy based on market conditions.

    Decision Tree:
    1. HIGH IV + Excellent Liquidity → Iron Condor or Credit Spreads
    2. LOW IV + Direction → Long Options or Debit Spreads
    3. MEDIUM IV + Contango → Calendar Spreads
    4. Moderate Liquidity → Simpler strategies (avoid iron condors)
    """
    if iv_interpretation == "SELL_PREMIUM":
        if liquidity_tier == "TIER_1":
            if direction == "LONG":
                return "BULL_PUT_CREDIT_SPREAD"
            elif direction == "SHORT":
                return "BEAR_CALL_CREDIT_SPREAD"
            else:
                return "IRON_CONDOR"
        else:
            return "CREDIT_SPREAD"  # Simpler for TIER_2

    elif iv_interpretation == "BUY_PREMIUM":
        if direction == "LONG":
            return "LONG_CALL" if liquidity_tier == "TIER_1" else "CALL_DEBIT_SPREAD"
        elif direction == "SHORT":
            return "LONG_PUT" if liquidity_tier == "TIER_1" else "PUT_DEBIT_SPREAD"
        else:
            return "DEBIT_SPREAD"

    else:  # NEUTRAL
        if calendar_signal == "FAVORABLE":
            return "CALENDAR_SPREAD"
        else:
            return "STOCK_ONLY"


def build_rationale(
    strategy: str,
    iv_env: dict,
    skew: dict,
    term_structure: dict,
    liquidity: dict,
    earnings_days: Optional[int]
) -> str:
    """Build comprehensive rationale for strategy selection."""

    parts = []

    # IV environment
    parts.append(f"{iv_env['classification']} IV ({iv_env['iv_rank']:.1f}%) → {iv_env['interpretation']}")

    # Liquidity
    parts.append(f"{liquidity['liquidity_tier']} liquidity (score: {liquidity['liquidity_score']}/100)")

    # Skew
    if skew['strategy_bias'] != "BALANCED":
        parts.append(f"IV skew: {skew['skew_type']} → {skew['strategy_bias']} bias")

    # Term structure
    if term_structure['calendar_signal'] == "FAVORABLE":
        parts.append(f"Contango term structure favors calendars")

    # Earnings
    if earnings_days and earnings_days < 45:
        parts.append(f"Earnings in {earnings_days} days")

    return " | ".join(parts)


def build_alternatives(
    primary_strategy: str,
    iv_env: dict,
    direction: str
) -> list[dict]:
    """Build list of alternative strategies."""

    alternatives = []

    if primary_strategy == "IRON_CONDOR":
        alternatives.append({
            "strategy": "BULL_PUT_SPREAD",
            "reason": "If bullish bias stronger, single side has higher credit"
        })
        alternatives.append({
            "strategy": "BEAR_CALL_SPREAD",
            "reason": "If bearish bias stronger, single side has less capital requirement"
        })
        alternatives.append({
            "strategy": "STOCK_ONLY",
            "reason": "If prefer simplicity and directional conviction"
        })

    elif "CREDIT_SPREAD" in primary_strategy:
        alternatives.append({
            "strategy": "IRON_CONDOR",
            "reason": "If neutral, collect credit from both sides"
        })
        alternatives.append({
            "strategy": "STOCK_ONLY",
            "reason": "If liquidity concerns or want unlimited upside"
        })

    elif "DEBIT_SPREAD" in primary_strategy or "LONG" in primary_strategy:
        alternatives.append({
            "strategy": "STOCK_ONLY",
            "reason": "Stock has unlimited upside, no theta decay"
        })
        alternatives.append({
            "strategy": "CALENDAR_SPREAD",
            "reason": "If neutral, profit from theta differential"
        })

    return alternatives
