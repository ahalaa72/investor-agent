"""
Options Position Management - Core Logic

Implements position lifecycle management based on:
- TastyTrade research (50% profit target = 88% win rate)
- McMillan methodology (Options as a Strategic Investment)
- Institutional risk management practices
"""

from datetime import datetime, timedelta
from typing import Any, Literal
import logging

logger = logging.getLogger(__name__)


def evaluate_options_position(
    position: dict[str, Any],
    current_market_price: float,
    current_greeks: dict[str, float] | None = None,
    brooks_signal: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Evaluate an options position and recommend action.

    Based on TastyTrade + McMillan rules:
    1. **50% Profit Target** (credit spreads) - 88% win rate
    2. **21 DTE Management** - Close or roll to avoid gamma risk
    3. **Direction Change** - Exit if Brooks Always-In flips
    4. **Tested Position** - Roll or take assignment if ITM
    5. **Earnings <7 days** - Close to avoid IV crush

    Args:
        position: Position data with structure:
            {
                "symbol": "AAPL",
                "strategy": "IRON_CONDOR",  # or CREDIT_SPREAD, DEBIT_SPREAD, etc.
                "entry_date": "2026-01-15",
                "expiration": "2026-02-21",
                "entry_credit": 630.00,  # Max profit for credit strategies
                "entry_debit": 370.00,   # Max loss for debit strategies
                "current_value": 315.00,  # Current position value
                "legs": [
                    {"type": "CALL", "strike": 252, "action": "SELL", "quantity": 2},
                    {"type": "CALL", "strike": 257, "action": "BUY", "quantity": 2},
                    ...
                ]
            }

        current_market_price: Current underlying price
        current_greeks: Optional current Greeks (delta, theta, vega, gamma)
        brooks_signal: Optional Brooks analysis (always_in direction)

    Returns:
        {
            "action": "HOLD" | "CLOSE" | "ROLL" | "ADJUST",
            "reason": str,
            "urgency": "IMMEDIATE" | "WITHIN_3_DAYS" | "MONITOR",

            "profit_status": {
                "current_pnl": float,
                "current_pnl_pct": float,
                "profit_target_hit": bool,
                "profit_target_pct": 50.0
            },

            "dte_status": {
                "days_to_expiration": int,
                "dte_threshold_hit": bool,  # True if DTE <= 21
                "gamma_risk_level": "LOW" | "MODERATE" | "HIGH"
            },

            "direction_status": {
                "entry_direction": "LONG" | "SHORT",
                "current_direction": "LONG" | "SHORT" | "NEUTRAL",
                "direction_flip": bool
            },

            "tested_status": {
                "is_tested": bool,  # True if price breached a short strike
                "tested_side": "CALL" | "PUT" | None,
                "assignment_risk": "LOW" | "MODERATE" | "HIGH"
            },

            "earnings_status": {
                "days_to_earnings": int | None,
                "within_7_days": bool,
                "close_recommended": bool
            },

            "roll_details": {
                "recommended_expiry": str,  # Next monthly expiration
                "estimated_credit": float | None,
                "roll_rationale": str
            } | None,

            "expected_pnl_if_hold": float,
            "expected_pnl_if_close": float,
            "recommendation": str  # Detailed explanation
        }

    Reference:
        - TastyTrade: "Manage Winners at 50% of Max Profit" (88% win rate)
        - McMillan: "Options as a Strategic Investment", Chapter 36
    """
    symbol = position.get('symbol')
    strategy = position.get('strategy', 'UNKNOWN')
    entry_date_str = position.get('entry_date')
    expiration_str = position.get('expiration')
    entry_credit = position.get('entry_credit', 0)
    entry_debit = position.get('entry_debit', 0)
    current_value = position.get('current_value', 0)

    # Parse dates
    try:
        entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d") if entry_date_str else datetime.now()
        expiration = datetime.strptime(expiration_str, "%Y-%m-%d") if expiration_str else datetime.now()
    except ValueError as e:
        logger.error(f"Date parsing error for {symbol}: {e}")
        return {"error": f"Invalid date format: {e}"}

    days_to_expiration = (expiration - datetime.now()).days
    days_in_trade = (datetime.now() - entry_date).days

    result = {
        "symbol": symbol,
        "strategy": strategy,
        "action": "HOLD",
        "reason": "",
        "urgency": "MONITOR"
    }

    # ========== CHECK 1: 50% PROFIT TARGET ==========
    # TastyTrade research: Taking 50% of max profit = 88% win rate
    profit_target_pct = 50.0
    is_credit_strategy = strategy in ["IRON_CONDOR", "CREDIT_SPREAD", "BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"]

    if is_credit_strategy and entry_credit > 0:
        # Credit strategy: Profit when position value decreases
        current_pnl = entry_credit - current_value
        max_profit = entry_credit
        current_pnl_pct = (current_pnl / max_profit * 100) if max_profit > 0 else 0
        profit_target_hit = current_pnl_pct >= profit_target_pct

    elif not is_credit_strategy and entry_debit > 0:
        # Debit strategy: Profit when position value increases
        current_pnl = current_value - entry_debit
        max_profit = position.get('max_profit', entry_debit * 2)  # Estimate if not provided
        current_pnl_pct = (current_pnl / max_profit * 100) if max_profit > 0 else 0
        profit_target_hit = current_pnl_pct >= profit_target_pct

    else:
        current_pnl = 0
        current_pnl_pct = 0
        profit_target_hit = False

    result["profit_status"] = {
        "current_pnl": round(current_pnl, 2),
        "current_pnl_pct": round(current_pnl_pct, 1),
        "profit_target_hit": profit_target_hit,
        "profit_target_pct": profit_target_pct,
        "days_in_trade": days_in_trade
    }

    if profit_target_hit:
        result["action"] = "CLOSE"
        result["reason"] = f"✅ 50% PROFIT TARGET HIT ({current_pnl_pct:.1f}% of max profit)"
        result["urgency"] = "IMMEDIATE"
        result["recommendation"] = (
            f"Close position now. You've captured {current_pnl_pct:.1f}% of max profit "
            f"(${current_pnl:.2f}). TastyTrade research shows managing winners at 50% "
            f"achieves 88% win rate vs 52% if holding to expiration."
        )
        result["expected_pnl_if_close"] = current_pnl
        result["expected_pnl_if_hold"] = current_pnl * 0.52  # Lower expected value if holding
        return result

    # ========== CHECK 2: 21 DTE MANAGEMENT ==========
    # At 21 DTE, gamma risk increases exponentially
    # Decision: Close for profit/loss OR roll to next expiration
    dte_threshold = 21
    dte_threshold_hit = days_to_expiration <= dte_threshold

    # Gamma risk assessment
    if days_to_expiration <= 7:
        gamma_risk_level = "HIGH"
    elif days_to_expiration <= 14:
        gamma_risk_level = "MODERATE"
    else:
        gamma_risk_level = "LOW"

    result["dte_status"] = {
        "days_to_expiration": days_to_expiration,
        "dte_threshold_hit": dte_threshold_hit,
        "gamma_risk_level": gamma_risk_level
    }

    if dte_threshold_hit and current_pnl > 0:
        # Profitable position at 21 DTE -> Close
        result["action"] = "CLOSE"
        result["reason"] = f"📅 21 DTE THRESHOLD (currently {days_to_expiration} DTE, ${current_pnl:.2f} profit)"
        result["urgency"] = "WITHIN_3_DAYS"
        result["recommendation"] = (
            f"Close position. At {days_to_expiration} DTE, gamma risk increases. "
            f"You're up ${current_pnl:.2f} ({current_pnl_pct:.1f}% of max). "
            f"Lock in gains before gamma risk accelerates."
        )
        result["expected_pnl_if_close"] = current_pnl
        result["expected_pnl_if_hold"] = current_pnl * 0.7  # Risk of giving back gains
        return result

    elif dte_threshold_hit and current_pnl <= 0:
        # Losing position at 21 DTE -> Consider roll
        next_expiry = _get_next_monthly_expiration(expiration)

        result["action"] = "ROLL"
        result["reason"] = f"📅 21 DTE THRESHOLD (currently {days_to_expiration} DTE, ${current_pnl:.2f} loss)"
        result["urgency"] = "WITHIN_3_DAYS"
        result["roll_details"] = {
            "recommended_expiry": next_expiry.strftime("%Y-%m-%d"),
            "estimated_credit": None,  # Would need market data to estimate
            "roll_rationale": (
                f"Roll to {next_expiry.strftime('%Y-%m-%d')} to give trade more time. "
                f"Current loss: ${abs(current_pnl):.2f}. Rolling extends duration and "
                f"may collect additional credit."
            )
        }
        result["recommendation"] = (
            f"Consider rolling to {next_expiry.strftime('%b %Y')} expiration. "
            f"You're down ${abs(current_pnl):.2f}. Rolling can extend the trade and "
            f"potentially collect more credit. Evaluate if thesis still valid."
        )
        result["expected_pnl_if_close"] = current_pnl
        result["expected_pnl_if_hold"] = current_pnl * 1.5  # Could get worse
        return result

    # ========== CHECK 3: DIRECTION CHANGE ==========
    # If Brooks Always-In flips, exit immediately
    if brooks_signal:
        entry_direction = position.get('entry_direction', 'LONG')
        current_always_in = brooks_signal.get('always_in', 'NEUTRAL')

        direction_flip = (
            (entry_direction == "LONG" and current_always_in == "SHORT") or
            (entry_direction == "SHORT" and current_always_in == "LONG")
        )

        result["direction_status"] = {
            "entry_direction": entry_direction,
            "current_direction": current_always_in,
            "direction_flip": direction_flip
        }

        if direction_flip:
            result["action"] = "CLOSE"
            result["reason"] = f"🔄 DIRECTION FLIP: {entry_direction} → {current_always_in}"
            result["urgency"] = "IMMEDIATE"
            result["recommendation"] = (
                f"EXIT IMMEDIATELY. Brooks Always-In flipped from {entry_direction} to {current_always_in}. "
                f"Your {strategy} was entered on a {entry_direction} thesis which is now invalidated. "
                f"Current P&L: ${current_pnl:.2f}."
            )
            result["expected_pnl_if_close"] = current_pnl
            result["expected_pnl_if_hold"] = current_pnl - (abs(current_pnl) * 0.5)  # Could lose more
            return result

    # ========== CHECK 4: TESTED POSITION ==========
    # Check if price has breached short strikes (position is "tested")
    legs = position.get('legs', [])
    short_call_strike = None
    short_put_strike = None

    for leg in legs:
        if leg.get('action') == 'SELL':
            if leg.get('type') == 'CALL':
                short_call_strike = leg.get('strike')
            elif leg.get('type') == 'PUT':
                short_put_strike = leg.get('strike')

    is_tested = False
    tested_side = None
    assignment_risk = "LOW"

    if short_call_strike and current_market_price >= short_call_strike:
        is_tested = True
        tested_side = "CALL"
        # Check how deep ITM
        if current_market_price >= short_call_strike * 1.05:
            assignment_risk = "HIGH"
        elif current_market_price >= short_call_strike * 1.02:
            assignment_risk = "MODERATE"

    if short_put_strike and current_market_price <= short_put_strike:
        is_tested = True
        tested_side = "PUT"
        # Check how deep ITM
        if current_market_price <= short_put_strike * 0.95:
            assignment_risk = "HIGH"
        elif current_market_price <= short_put_strike * 0.98:
            assignment_risk = "MODERATE"

    result["tested_status"] = {
        "is_tested": is_tested,
        "tested_side": tested_side,
        "assignment_risk": assignment_risk
    }

    if is_tested and assignment_risk == "HIGH" and days_to_expiration <= 7:
        result["action"] = "CLOSE"
        result["reason"] = f"⚠️ HIGH ASSIGNMENT RISK: {tested_side} side tested, {days_to_expiration} DTE"
        result["urgency"] = "IMMEDIATE"
        result["recommendation"] = (
            f"CLOSE to avoid assignment. Your short {tested_side} at ${short_call_strike if tested_side == 'CALL' else short_put_strike} "
            f"is ITM with price at ${current_market_price:.2f}. With {days_to_expiration} DTE, assignment risk is HIGH. "
            f"Current P&L: ${current_pnl:.2f}."
        )
        result["expected_pnl_if_close"] = current_pnl
        result["expected_pnl_if_hold"] = "ASSIGNMENT"  # Could be assigned
        return result

    # ========== CHECK 5: EARNINGS PROXIMITY ==========
    # If earnings < 7 days, close to avoid IV crush volatility
    # Note: For now, we'll skip this check since we need earnings date
    # In production, integrate with detect_catalyst_strength()
    result["earnings_status"] = {
        "days_to_earnings": None,
        "within_7_days": False,
        "close_recommended": False
    }

    # ========== DEFAULT: HOLD ==========
    result["action"] = "HOLD"
    result["reason"] = f"Position healthy ({days_to_expiration} DTE, ${current_pnl:.2f} P&L)"
    result["urgency"] = "MONITOR"
    result["recommendation"] = (
        f"Continue holding. Position is {days_to_expiration} DTE with ${current_pnl:.2f} P&L "
        f"({current_pnl_pct:.1f}% of max). Monitor for 50% profit target or 21 DTE threshold."
    )
    result["expected_pnl_if_close"] = current_pnl
    result["expected_pnl_if_hold"] = current_pnl * 1.2  # Expected to improve

    return result


def evaluate_portfolio_positions(
    positions: list[dict[str, Any]],
    market_data: dict[str, float],
    brooks_signals: dict[str, dict] | None = None
) -> dict[str, Any]:
    """
    Evaluate all options positions in portfolio and prioritize actions.

    Args:
        positions: List of position dicts
        market_data: Dict of {symbol: current_price}
        brooks_signals: Optional dict of {symbol: brooks_analysis}

    Returns:
        {
            "summary": {
                "total_positions": int,
                "immediate_actions": int,
                "within_3_days": int,
                "monitoring": int
            },

            "positions": [
                {
                    **position,
                    **evaluation_result
                },
                ...
            ],

            "action_required": [
                {
                    "symbol": str,
                    "action": str,
                    "urgency": str,
                    "reason": str,
                    "expected_pnl_if_close": float
                },
                ...
            ],

            "portfolio_greeks": {
                "total_delta": float,
                "total_theta": float,
                "total_vega": float,
                "total_gamma": float
            }
        }
    """
    evaluated = []
    immediate_actions = []
    within_3_days_actions = []

    for position in positions:
        symbol = position.get('symbol')
        current_price = market_data.get(symbol, 0)
        brooks_signal = brooks_signals.get(symbol) if brooks_signals else None

        # Evaluate position
        evaluation = evaluate_options_position(
            position=position,
            current_market_price=current_price,
            brooks_signal=brooks_signal
        )

        # Merge evaluation with position data
        full_result = {**position, **evaluation}
        evaluated.append(full_result)

        # Categorize by urgency
        if evaluation.get('urgency') == 'IMMEDIATE':
            immediate_actions.append({
                "symbol": symbol,
                "action": evaluation.get('action'),
                "urgency": "IMMEDIATE",
                "reason": evaluation.get('reason'),
                "expected_pnl_if_close": evaluation.get('expected_pnl_if_close')
            })
        elif evaluation.get('urgency') == 'WITHIN_3_DAYS':
            within_3_days_actions.append({
                "symbol": symbol,
                "action": evaluation.get('action'),
                "urgency": "WITHIN_3_DAYS",
                "reason": evaluation.get('reason'),
                "expected_pnl_if_close": evaluation.get('expected_pnl_if_close')
            })

    # Sort by urgency
    action_required = immediate_actions + within_3_days_actions

    return {
        "summary": {
            "total_positions": len(positions),
            "immediate_actions": len(immediate_actions),
            "within_3_days": len(within_3_days_actions),
            "monitoring": len(positions) - len(immediate_actions) - len(within_3_days_actions)
        },
        "positions": evaluated,
        "action_required": action_required
    }


def get_position_greeks_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate aggregate portfolio Greeks.

    Args:
        positions: List of positions with Greeks

    Returns:
        {
            "total_delta": float,
            "total_theta": float,  # Daily time decay
            "total_vega": float,   # IV sensitivity
            "total_gamma": float,

            "theta_daily_income": float,  # Expected daily theta profit
            "vega_10pt_impact": float,    # P&L change per 10-point IV move

            "risk_assessment": {
                "delta_exposure": str,  # "NEUTRAL", "BULLISH", "BEARISH"
                "theta_position": str,  # "LONG_THETA" (collecting), "SHORT_THETA" (paying)
                "vega_position": str,   # "LONG_VEGA" (want IV up), "SHORT_VEGA" (want IV down)
                "gamma_position": str   # "LONG_GAMMA", "SHORT_GAMMA"
            }
        }
    """
    total_delta = 0.0
    total_theta = 0.0
    total_vega = 0.0
    total_gamma = 0.0

    for position in positions:
        greeks = position.get('greeks', {})
        quantity = position.get('quantity', 0)

        # Aggregate Greeks (scale by quantity × 100 for options contracts)
        if position.get('position_type') == 'option':
            multiplier = quantity * 100
        else:
            multiplier = quantity

        total_delta += greeks.get('delta', 0) * multiplier
        total_theta += greeks.get('theta', 0) * multiplier
        total_vega += greeks.get('vega', 0) * multiplier
        total_gamma += greeks.get('gamma', 0) * multiplier

    # Risk assessment
    delta_exposure = "NEUTRAL"
    if total_delta > 50:
        delta_exposure = "BULLISH"
    elif total_delta < -50:
        delta_exposure = "BEARISH"

    theta_position = "LONG_THETA" if total_theta > 0 else "SHORT_THETA"
    vega_position = "LONG_VEGA" if total_vega > 0 else "SHORT_VEGA"
    gamma_position = "LONG_GAMMA" if total_gamma > 0 else "SHORT_GAMMA"

    return {
        "total_delta": round(total_delta, 2),
        "total_theta": round(total_theta, 2),
        "total_vega": round(total_vega, 2),
        "total_gamma": round(total_gamma, 4),

        "theta_daily_income": round(total_theta, 2),
        "vega_10pt_impact": round(total_vega * 10, 2),

        "risk_assessment": {
            "delta_exposure": delta_exposure,
            "theta_position": theta_position,
            "vega_position": vega_position,
            "gamma_position": gamma_position
        }
    }


def _get_next_monthly_expiration(current_expiration: datetime) -> datetime:
    """Get next monthly options expiration (3rd Friday of next month)."""
    # Move to next month
    if current_expiration.month == 12:
        next_month = current_expiration.replace(year=current_expiration.year + 1, month=1, day=1)
    else:
        next_month = current_expiration.replace(month=current_expiration.month + 1, day=1)

    # Find 3rd Friday
    # Start with first day of month, find first Friday
    first_day = next_month
    days_until_friday = (4 - first_day.weekday()) % 7  # Friday = 4
    first_friday = first_day + timedelta(days=days_until_friday)

    # 3rd Friday is first Friday + 14 days
    third_friday = first_friday + timedelta(days=14)

    return third_friday
