"""
Options vs Stock Decision Framework

This module implements the decision logic for determining whether to:
1. Trade options
2. Trade stock
3. Mix both (e.g., stock + covered calls)

Integrates with Gate 5 validation to make intelligent routing decisions
based on liquidity, IV environment, conviction level, and account size.

Author: Investor Agent Team
Date: January 28, 2026
"""

from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


def should_use_options(
    gate_5_result: dict,
    stock_liquidity: dict,
    conviction_level: str,  # "STRONG" (4/4 gates) | "MODERATE" (3/4 gates) | "WEAK" (2/4 gates)
    account_size: float,
    current_position_value: float = 0
) -> dict[str, Any]:
    """
    Decide: Options vs Stock vs Mixed

    Decision Logic:
    1. If Gate 5 FAIL → Stock only
    2. If conviction WEAK (2/4 gates) → Stock only (reduce complexity on uncertain trades)
    3. If Gate 5 PASS + HIGH IV + Excellent liquidity + STRONG conviction → Options (credit spreads)
    4. If Gate 5 PASS + LOW IV + Excellent liquidity + STRONG conviction → Options (debit spreads)
    5. If Gate 5 PASS + Moderate liquidity → Stock (safer execution)
    6. If account too small (<$5K) → Stock only (options require larger capital)

    Args:
        gate_5_result: Output from validate_options_tradability()
        stock_liquidity: Stock market data (volume, spread)
        conviction_level: "STRONG" | "MODERATE" | "WEAK"
        account_size: Total account value
        current_position_value: Current position value (for sizing checks)

    Returns:
        {
            "use_options": bool,
            "primary_vehicle": "OPTIONS" | "STOCK" | "MIXED",
            "reason": str,
            "decision_rationale": str,
            "confidence": "HIGH" | "MEDIUM" | "LOW",
            "recommended_allocation": {
                "options_pct": 0-100,
                "stock_pct": 0-100
            }
        }
    """
    reasons = []
    use_options = False
    primary_vehicle = "STOCK"  # Default to stock
    options_pct = 0
    stock_pct = 100

    # Rule 1: Gate 5 must pass
    if gate_5_result['gate_status'] == 'FAIL':
        reasons.append("Gate 5 failed - options not tradable")
        reasons.append(f"Failure reason: {gate_5_result.get('strategy_rationale', 'Liquidity or IV issues')}")
        confidence = "HIGH"  # High confidence in stock-only decision
        return {
            "use_options": False,
            "primary_vehicle": "STOCK",
            "reason": "; ".join(reasons),
            "decision_rationale": "Options gate failed validation. Trade stock for better execution and simplicity.",
            "confidence": confidence,
            "recommended_allocation": {
                "options_pct": 0,
                "stock_pct": 100
            }
        }

    # Rule 2: Account size minimum
    if account_size < 5000:
        reasons.append(f"Account size (${account_size:,.0f}) below $5K minimum for options")
        reasons.append("Options require larger capital for proper position sizing")
        return {
            "use_options": False,
            "primary_vehicle": "STOCK",
            "reason": "; ".join(reasons),
            "decision_rationale": "Small account size. Build capital with stock trades first, then graduate to options.",
            "confidence": "HIGH",
            "recommended_allocation": {
                "options_pct": 0,
                "stock_pct": 100
            }
        }

    # Rule 3: Conviction level matters
    if conviction_level == "WEAK":
        reasons.append("Conviction WEAK (2/4 gates) - reduce complexity")
        reasons.append("Options add leverage and complexity to uncertain trades")
        return {
            "use_options": False,
            "primary_vehicle": "STOCK",
            "reason": "; ".join(reasons),
            "decision_rationale": "Low conviction trade. Stick to stock to avoid options complexity on uncertain thesis.",
            "confidence": "MEDIUM",
            "recommended_allocation": {
                "options_pct": 0,
                "stock_pct": 100
            }
        }

    # At this point: Gate 5 passed + Account size OK + Conviction MODERATE/STRONG
    # Now evaluate IV environment and liquidity

    gate_5_score = gate_5_result.get('score', 0)
    iv_env = gate_5_result.get('checks', {}).get('iv_environment', {})
    iv_classification = iv_env.get('classification', 'UNKNOWN')
    liquidity = gate_5_result.get('checks', {}).get('liquidity', {})
    liquidity_tier = liquidity.get('liquidity_tier', 'TIER_3')
    recommended_strategy = gate_5_result.get('recommended_strategy', '')

    # Rule 4: HIGH IV + Good liquidity + STRONG conviction → Prefer options (sell premium)
    if iv_classification == "HIGH" and liquidity_tier in ["TIER_1", "TIER_2"] and conviction_level == "STRONG":
        use_options = True
        primary_vehicle = "OPTIONS"
        options_pct = 100
        stock_pct = 0
        reasons.append(f"HIGH IV ({iv_env.get('iv_rank', 0):.1f}%) → SELL PREMIUM strategies optimal")
        reasons.append(f"{liquidity_tier} liquidity → Excellent execution")
        reasons.append(f"STRONG conviction (4/4 gates) → High confidence in options")
        reasons.append(f"Strategy: {recommended_strategy}")
        confidence = "HIGH"

    # Rule 5: LOW IV + Good liquidity + STRONG conviction → Consider options (buy premium)
    elif iv_classification == "LOW" and liquidity_tier == "TIER_1" and conviction_level == "STRONG":
        use_options = True
        primary_vehicle = "OPTIONS"
        options_pct = 80  # 80% options, 20% stock for flexibility
        stock_pct = 20
        reasons.append(f"LOW IV ({iv_env.get('iv_rank', 0):.1f}%) → BUY PREMIUM cheap")
        reasons.append(f"{liquidity_tier} liquidity → Good execution")
        reasons.append(f"STRONG conviction → High confidence in directional bet")
        reasons.append(f"Strategy: {recommended_strategy}")
        confidence = "MEDIUM"  # Lower confidence than HIGH IV sell premium

    # Rule 6: MEDIUM IV or TIER_2 liquidity + STRONG conviction → Mixed approach
    elif conviction_level == "STRONG" and liquidity_tier in ["TIER_1", "TIER_2"]:
        use_options = True
        primary_vehicle = "MIXED"
        options_pct = 50
        stock_pct = 50
        reasons.append(f"{iv_classification} IV → Neutral environment")
        reasons.append(f"{liquidity_tier} liquidity → Adequate but not ideal")
        reasons.append("Mixed approach: 50% options, 50% stock for balance")
        confidence = "MEDIUM"

    # Rule 7: MODERATE conviction → Lean towards stock
    elif conviction_level == "MODERATE":
        use_options = False
        primary_vehicle = "STOCK"
        options_pct = 0
        stock_pct = 100
        reasons.append("Conviction MODERATE (3/4 gates) → Prefer simpler stock trade")
        reasons.append("Gate 5 passed but conviction not strong enough for options complexity")
        confidence = "MEDIUM"

    # Rule 8: Default fallback → Stock
    else:
        use_options = False
        primary_vehicle = "STOCK"
        options_pct = 0
        stock_pct = 100
        reasons.append("No strong case for options")
        reasons.append(f"{iv_classification} IV + {liquidity_tier} + {conviction_level} conviction → Stock safer")
        confidence = "MEDIUM"

    decision_rationale = build_decision_rationale(
        use_options=use_options,
        primary_vehicle=primary_vehicle,
        iv_classification=iv_classification,
        liquidity_tier=liquidity_tier,
        conviction_level=conviction_level,
        gate_5_score=gate_5_score,
        recommended_strategy=recommended_strategy
    )

    return {
        "use_options": use_options,
        "primary_vehicle": primary_vehicle,
        "reason": "; ".join(reasons),
        "decision_rationale": decision_rationale,
        "confidence": confidence,
        "recommended_allocation": {
            "options_pct": options_pct,
            "stock_pct": stock_pct
        }
    }


def build_decision_rationale(
    use_options: bool,
    primary_vehicle: str,
    iv_classification: str,
    liquidity_tier: str,
    conviction_level: str,
    gate_5_score: float,
    recommended_strategy: str
) -> str:
    """
    Build comprehensive rationale for options vs stock decision.
    """
    if not use_options:
        return (
            f"Stock recommended. Conviction: {conviction_level}, Gate 5 score: {gate_5_score:.0f}/100. "
            f"Stock provides simpler execution and lower complexity for this setup."
        )

    elif primary_vehicle == "OPTIONS":
        return (
            f"Options recommended ({recommended_strategy}). "
            f"IV: {iv_classification}, Liquidity: {liquidity_tier}, Conviction: {conviction_level}, "
            f"Gate 5: {gate_5_score:.0f}/100. "
            f"Options provide better risk/reward with defined risk and favorable Greeks."
        )

    else:  # MIXED
        return (
            f"Mixed approach recommended (50% options, 50% stock). "
            f"IV: {iv_classification}, Liquidity: {liquidity_tier}, Conviction: {conviction_level}. "
            f"Balance options leverage with stock simplicity and flexibility."
        )


def build_options_plan(
    gate_5_result: dict,
    ticker: str,
    direction: str,
    account_size: float,
    allocation_pct: float
) -> dict[str, Any]:
    """
    Build full options plan with position sizing based on allocation.

    This is a lightweight wrapper that formats Gate 5 output for execution.

    Args:
        gate_5_result: Output from validate_options_tradability()
        ticker: Stock symbol
        direction: "LONG" | "SHORT"
        account_size: Total account size
        allocation_pct: Percent of account to allocate (0-100)

    Returns:
        {
            "strategy": str,
            "entry": {
                "legs": [...],
                "net_credit_or_debit": float,
                "contracts": int
            },
            "risk_reward": {
                "max_profit": float,
                "max_loss": float,
                "risk_reward_ratio": float,
                "probability_of_profit": float
            },
            "management_rules": {
                "profit_target_pct": 50,  # Close at 50% profit
                "dte_review": 21,  # Review at 21 DTE
                "direction_change": "Close if Brooks flips",
                "earnings_warning": "Close 1-2 days before earnings"
            }
        }
    """
    recommended_strategy = gate_5_result.get('recommended_strategy', 'STOCK_ONLY')

    # Calculate position size
    allocated_capital = account_size * (allocation_pct / 100)

    # Extract expected moves for strike selection
    expected_moves = gate_5_result.get('checks', {}).get('expected_move', {})
    optimal_strikes = expected_moves.get('optimal_strikes', {})

    # Build simplified plan (detailed construction happens in generate_options_trade_plan)
    return {
        "strategy": recommended_strategy,
        "ticker": ticker,
        "direction": direction,
        "allocated_capital": allocated_capital,
        "optimal_strikes": optimal_strikes,
        "expected_moves": expected_moves,
        "management_rules": {
            "profit_target_pct": 50,
            "dte_review": 21,
            "direction_change": "Close if Brooks Always-In flips",
            "earnings_warning": "Close 1-2 days before earnings if holding through",
            "methodology": "McMillan + TastyTrade (45 DTE entry, 50% profit target, 21 DTE management)"
        },
        "gate_5_score": gate_5_result.get('score', 0),
        "warnings": gate_5_result.get('warnings', [])
    }


def build_stock_plan(
    ticker: str,
    direction: str,
    current_price: float,
    account_size: float,
    allocation_pct: float,
    brooks_data: dict,
    atr: float
) -> dict[str, Any]:
    """
    Build stock trading plan with position sizing.

    Args:
        ticker: Stock symbol
        direction: "LONG" | "SHORT"
        current_price: Current stock price
        account_size: Total account size
        allocation_pct: Percent of account to allocate (0-100)
        brooks_data: Al Brooks price action data
        atr: Average True Range for stop placement

    Returns:
        {
            "vehicle": "STOCK",
            "entry_price": float,
            "stop_loss": float,
            "target_1": float,
            "target_2": float,
            "shares": int,
            "position_value": float,
            "risk_per_share": float,
            "total_risk": float,
            "reward_risk_ratio": float
        }
    """
    allocated_capital = account_size * (allocation_pct / 100)

    # Stop loss: 2.5x ATR (Brooks recommendation)
    atr_multiplier = 2.5
    stop_distance = atr * atr_multiplier

    if direction == "LONG":
        stop_loss = current_price - stop_distance
        target_1 = current_price + (stop_distance * 1.5)  # 1.5:1 R/R
        target_2 = current_price + (stop_distance * 2.5)  # 2.5:1 R/R
    else:  # SHORT
        stop_loss = current_price + stop_distance
        target_1 = current_price - (stop_distance * 1.5)
        target_2 = current_price - (stop_distance * 2.5)

    # Position sizing: Risk 1% of account per trade (matches trading_plan in signals.py)
    # Previously used 2% which contradicted the risk-managed plan in Section F
    risk_pct = 0.01
    risk_per_trade = account_size * risk_pct
    risk_per_share = abs(current_price - stop_loss)

    shares = int(risk_per_trade / risk_per_share) if risk_per_share > 0 else 0
    position_value = shares * current_price
    total_risk = shares * risk_per_share

    # Reward/Risk ratio
    reward_to_target_1 = abs(target_1 - current_price)
    reward_risk_ratio = reward_to_target_1 / risk_per_share

    return {
        "vehicle": "STOCK",
        "ticker": ticker,
        "direction": direction,
        "entry_price": round(current_price, 2),
        "stop_loss": round(stop_loss, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "shares": shares,
        "position_value": round(position_value, 2),
        "risk_per_share": round(risk_per_share, 2),
        "total_risk": round(total_risk, 2),
        "reward_risk_ratio": round(reward_risk_ratio, 2),
        "methodology": "Al Brooks 2.5x ATR stop, 1% account risk per trade"
    }
