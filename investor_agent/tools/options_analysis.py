"""Options analysis tools - McMillan methodology.

7 MCP tools + ~27 helper functions for institutional options analysis.
Reference: McMillan "Options as a Strategic Investment" (5th Edition)
"""
import logging
import math
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm
from typing import Any

from ..core.config import (
    INSTITUTIONAL_OPTIONS_PARAMS,
    TIER_1_UNDERLYINGS,
    IV_STRATEGY_MATRIX,
    THETA_DECAY_TABLE,
)
from ..core.validation import validate_ticker
from ..core.price import yf_call, convert_numpy_types, get_ticker_info_questrade_first
from ..questrade import get_questrade_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level references, populated by register_tools()
# Other modules import these _impl names; they become callable after
# register_tools() runs during server startup.
# ---------------------------------------------------------------------------
analyze_options_mcmillan_impl = None
analyze_iv_skew_impl = None
analyze_iv_term_structure_impl = None


def _get_earnings_proximity(ticker: str) -> dict:
    """
    Get days to next earnings for options trading filter.

    CRITICAL: Buyers and Sellers have OPPOSITE positions on IV crush!
    - BUYERS: Hurt by IV crush (overpay for premium, lose value even if right)
    - SELLERS: Profit from IV crush (collect max premium when IV high, buy back cheap)

    McMillan/TastyTrade methodology: "When IV is HIGH, be a SELLER"

    Uses multiple data sources with fallback:
    1. yf_call with retry logic (calendar)
    2. yfinance earnings_dates property
    3. NASDAQ earnings calendar fallback

    Returns:
        dict with:
        - days_to_earnings: int or None
        - earnings_date: str or None
        - options_buying_allowed: bool (False if <30 days - IV crush hurts buyers)
        - options_selling_allowed: bool (True even <30 days - IV crush helps sellers)
        - options_allowed: bool (legacy - True if selling allowed)
        - buyer_warning: str or None
        - seller_opportunity: str or None
        - recommended_strategies: list of strategies when near earnings
    """
    from datetime import datetime, timedelta

    try:
        # Try to get earnings dates using yf_call (has retry logic)
        earnings_dates = None

        # Method 1: yf_call for calendar (with retry)
        try:
            calendar = yf_call(ticker, "calendar")
            if calendar is not None:
                # Handle DataFrame format
                if hasattr(calendar, 'empty') and not calendar.empty:
                    if 'Earnings Date' in calendar.index:
                        earnings_dates = calendar.loc['Earnings Date']
                    elif hasattr(calendar, 'columns') and 'Earnings Date' in calendar.columns:
                        earnings_dates = calendar['Earnings Date']
                # Handle dict format (newer yfinance versions)
                elif isinstance(calendar, dict) and 'Earnings Date' in calendar:
                    earnings_dates = calendar['Earnings Date']
        except Exception as e:
            logger.debug(f"Calendar method failed for {ticker}: {e}")

        # Method 2: Try earnings_dates property
        if earnings_dates is None:
            try:
                ed = yf_call(ticker, "earnings_dates")
                if ed is not None and hasattr(ed, 'empty') and not ed.empty:
                    future_dates = ed[ed.index > datetime.now()]
                    if not future_dates.empty:
                        earnings_dates = [future_dates.index[0]]
            except Exception as e:
                logger.debug(f"earnings_dates property failed for {ticker}: {e}")

        # Method 3: Fallback to NASDAQ earnings calendar (async function)
        if earnings_dates is None:
            import asyncio
            from .financial_data import get_nasdaq_earnings_calendar_impl as get_nasdaq_earnings_calendar
            try:
                # Check next 30 days of NASDAQ calendar
                today_dt = datetime.now()
                for days_ahead in [0, 7, 14, 21, 28]:
                    check_date = (today_dt + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
                    # get_nasdaq_earnings_calendar is async, need to run it
                    try:
                        nasdaq_cal = asyncio.run(get_nasdaq_earnings_calendar(date=check_date, limit=200))
                    except RuntimeError:
                        # Already in async context, try get_event_loop
                        loop = asyncio.get_event_loop()
                        nasdaq_cal = loop.run_until_complete(get_nasdaq_earnings_calendar(date=check_date, limit=200))

                    # nasdaq_cal is CSV string directly (not a dict)
                    if nasdaq_cal and isinstance(nasdaq_cal, str) and ticker.upper() in nasdaq_cal.upper():
                        # Parse CSV data for ticker
                        for line in nasdaq_cal.split('\n')[1:]:  # Skip header
                            if ticker.upper() in line.upper():
                                # Found ticker in NASDAQ calendar
                                earnings_dates = [check_date]
                                logger.info(f"Found {ticker} earnings on {check_date} via NASDAQ calendar")
                                break
                    if earnings_dates:
                        break
            except Exception as e:
                logger.debug(f"NASDAQ calendar fallback failed for {ticker}: {e}")

        # Calculate days to earnings
        today = datetime.now()
        min_days_to_earnings = INSTITUTIONAL_OPTIONS_PARAMS['min_days_to_earnings']

        if earnings_dates is not None:
            # Handle both Series and list
            if hasattr(earnings_dates, 'tolist'):
                dates_list = earnings_dates.tolist()
            elif hasattr(earnings_dates, 'values'):
                dates_list = list(earnings_dates.values)
            else:
                dates_list = list(earnings_dates) if earnings_dates else []

            # Find next earnings date
            next_earnings = None
            for d in dates_list:
                try:
                    if isinstance(d, str):
                        dt = datetime.strptime(d[:10], '%Y-%m-%d')
                    elif hasattr(d, 'to_pydatetime'):
                        dt = d.to_pydatetime()
                    elif isinstance(d, datetime):
                        dt = d
                    elif hasattr(d, 'year') and hasattr(d, 'month') and hasattr(d, 'day'):
                        # Handle datetime.date objects (from yfinance calendar dict)
                        dt = datetime(d.year, d.month, d.day)
                    else:
                        continue

                    # Ensure dt is timezone-naive for comparison
                    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)

                    # Compare dates only (earnings TODAY should be included!)
                    today_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
                    if dt >= today_date:
                        if next_earnings is None or dt < next_earnings:
                            next_earnings = dt
                except Exception:
                    continue

            if next_earnings:
                days_to_earnings = (next_earnings - today).days
                earnings_date_str = next_earnings.strftime('%Y-%m-%d')

                # CRITICAL: Separate logic for buyers vs sellers
                # Buyers: Hurt by IV crush, should avoid near earnings
                # Sellers: Profit from IV crush, prime time to sell premium
                options_buying_allowed = days_to_earnings >= min_days_to_earnings
                options_selling_allowed = True  # Sellers ALWAYS benefit from high IV

                # Build appropriate warnings/opportunities
                buyer_warning = None
                seller_opportunity = None
                recommended_strategies = []

                if not options_buying_allowed:
                    # Near earnings - differentiate buyer vs seller guidance
                    buyer_warning = f"⚠️ SKIP BUYING OPTIONS - EARNINGS in {days_to_earnings} days. IV crush will hurt you even if direction is right."
                    seller_opportunity = f"✅ PRIME TIME TO SELL PREMIUM - EARNINGS in {days_to_earnings} days. High IV = max premium. Profit from IV crush after announcement."
                    recommended_strategies = [
                        "short_put" if days_to_earnings >= 7 else "cash_secured_put",
                        "short_call",
                        "iron_condor",
                        "credit_spread",
                        "short_strangle" if days_to_earnings >= 14 else None,
                        "short_straddle" if days_to_earnings >= 14 else None,
                    ]
                    recommended_strategies = [s for s in recommended_strategies if s]  # Remove None

                return {
                    "days_to_earnings": days_to_earnings,
                    "earnings_date": earnings_date_str,
                    # New buyer/seller specific flags
                    "options_buying_allowed": options_buying_allowed,
                    "options_selling_allowed": options_selling_allowed,
                    # Legacy field - now means selling is allowed (more permissive)
                    "options_allowed": options_selling_allowed,
                    # Specific guidance
                    "buyer_warning": buyer_warning,
                    "seller_opportunity": seller_opportunity,
                    "recommended_strategies": recommended_strategies,
                    # Legacy warning field (now buyer-specific)
                    "warning": buyer_warning
                }

        # No earnings data found - assume allowed for both buyers and sellers
        return {
            "days_to_earnings": None,
            "earnings_date": None,
            "options_buying_allowed": True,
            "options_selling_allowed": True,
            "options_allowed": True,
            "buyer_warning": None,
            "seller_opportunity": None,
            "recommended_strategies": [],
            "warning": "No earnings date found - proceed with caution"
        }

    except Exception as e:
        logger.warning(f"Error getting earnings for {ticker}: {e}")
        return {
            "days_to_earnings": None,
            "earnings_date": None,
            "options_buying_allowed": True,
            "options_selling_allowed": True,
            "options_allowed": True,
            "buyer_warning": None,
            "seller_opportunity": None,
            "recommended_strategies": [],
            "warning": f"Could not determine earnings date: {str(e)}"
        }


def _calculate_liquidity_tier(ticker: str, avg_volume: float = None) -> dict:
    """
    Classify ticker into liquidity tiers for options trading.

    Tier 1: TIER_1_UNDERLYINGS - penny-wide spreads, 10,000+ OI (FULL SIZE)
    Tier 2: S&P 500 with weeklies, high volume (STANDARD SIZE)
    Tier 3: Other liquid stocks (REDUCED SIZE with warning)
    Non-Liquid: Skip options entirely

    Returns:
        dict with tier, size_multiplier, warnings
    """
    ticker_upper = ticker.upper()

    # Check Tier 1
    if ticker_upper in TIER_1_UNDERLYINGS:
        return {
            "tier": "TIER_1",
            "tier_name": "Institutional Grade",
            "size_multiplier": 1.0,
            "description": "Penny-wide spreads, 10,000+ OI per strike",
            "warnings": []
        }

    # Get underlying volume if not provided
    if avg_volume is None:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            avg_volume = info.get('averageVolume', 0) or info.get('averageDailyVolume10Day', 0)
        except Exception:
            avg_volume = 0

    min_volume = INSTITUTIONAL_OPTIONS_PARAMS['min_underlying_volume']

    # Check Tier 2 (high volume stocks)
    if avg_volume >= min_volume * 2:  # 1M+ shares/day
        return {
            "tier": "TIER_2",
            "tier_name": "High Liquidity",
            "size_multiplier": 0.75,
            "description": "S&P 500 level liquidity with weeklies",
            "warnings": ["Reduce position size by 25% vs Tier 1"]
        }

    # Check Tier 3 (moderate volume)
    if avg_volume >= min_volume:  # 500K+ shares/day
        return {
            "tier": "TIER_3",
            "tier_name": "Moderate Liquidity",
            "size_multiplier": 0.50,
            "description": "Tradeable but with wider spreads",
            "warnings": [
                "⚠️ Reduce position size by 50% vs Tier 1",
                "⚠️ Expect 100-150% spread slippage on multi-leg trades",
                "⚠️ Use limit orders only"
            ]
        }

    # Non-liquid
    return {
        "tier": "NON_LIQUID",
        "tier_name": "Illiquid",
        "size_multiplier": 0.0,
        "description": "Options not recommended",
        "warnings": [
            "🚫 SKIP OPTIONS - Underlying volume too low",
            f"Volume {avg_volume:,.0f} < minimum {min_volume:,.0f}",
            "Wide spreads will eat profits"
        ]
    }


def _get_tradier_option_bidask(
    ticker: str,
    strike: float,
    expiry: str,
    option_type: str = "call"
) -> tuple[float, float]:
    """
    Fetch real-time bid/ask for an option from Tradier API.

    Tradier provides Level 1 options data including bid/ask spreads.
    Free sandbox has 15-min delay, but still useful when Questrade returns null.

    Args:
        ticker: Stock symbol (e.g., "SPY")
        strike: Option strike price
        expiry: Expiration date in YYYY-MM-DD format
        option_type: "call" or "put"

    Returns:
        (bid, ask) tuple, or (0, 0) if unavailable

    Requires:
        TRADIER_API_TOKEN environment variable
        TRADIER_API_ENDPOINT environment variable (default: sandbox)
    """
    import os
    import requests

    api_token = os.getenv('TRADIER_API_TOKEN')
    api_endpoint = os.getenv('TRADIER_API_ENDPOINT', 'https://sandbox.tradier.com/v1/')

    if not api_token:
        logger.debug("TRADIER_API_TOKEN not configured, skipping Tradier fallback")
        return (0, 0)

    try:
        # Fetch options chain for the specific expiration
        url = f"{api_endpoint}markets/options/chains"
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Accept': 'application/json'
        }
        params = {
            'symbol': ticker,
            'expiration': expiry,
            'greeks': 'false'  # Don't need Greeks, just bid/ask
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Navigate response structure
        if not data or 'options' not in data or 'option' not in data['options']:
            logger.debug(f"Tradier returned no options data for {ticker} {expiry}")
            return (0, 0)

        # Find the matching strike and type
        for option in data['options']['option']:
            if (abs(option.get('strike', 0) - strike) < 0.5 and
                option.get('option_type') == option_type):
                bid = float(option.get('bid', 0) or 0)
                ask = float(option.get('ask', 0) or 0)

                if bid > 0 and ask > 0:
                    logger.info(f"✅ Tradier bid/ask for {ticker} ${strike} {option_type}: bid=${bid}, ask=${ask}")
                    return (bid, ask)

        logger.debug(f"No matching option found in Tradier data for {ticker} ${strike} {option_type}")
        return (0, 0)

    except Exception as e:
        logger.debug(f"Tradier API fallback failed: {e}")
        return (0, 0)


def _fetch_yf_option_chain(ticker, expiry: str, copy: bool = False):
    """Fetch options chain from yfinance with logging.

    Args:
        ticker: Ticker string or yfinance.Ticker object
        expiry: Expiration date string (YYYY-MM-DD)
        copy: If True, return .copy() of DataFrames

    Returns:
        (calls_df, puts_df) tuple of DataFrames
    """
    t = yf.Ticker(ticker) if isinstance(ticker, str) else ticker
    chain = t.option_chain(expiry)
    calls_df = chain.calls.copy() if copy else chain.calls
    puts_df = chain.puts.copy() if copy else chain.puts
    return calls_df, puts_df


def _get_oi_with_yf_fallback(
    questrade_oi: int,
    ticker: str,
    strike: float,
    expiry: str,
    option_type: str = "call"
) -> int:
    """
    Get Open Interest with yfinance fallback when Questrade returns 0.

    Questrade API often doesn't include openInterest in the response.
    This function falls back to yfinance to get accurate OI data.

    Args:
        questrade_oi: OI value from Questrade (may be 0)
        ticker: Stock symbol
        strike: Option strike price
        expiry: Expiration date string (YYYY-MM-DD format)
        option_type: "call" or "put"

    Returns:
        Open interest value (from Questrade if valid, otherwise from yfinance)
    """
    # If Questrade provided valid OI, use it
    if questrade_oi > 0:
        return questrade_oi

    # Fallback to yfinance
    try:
        calls_df, puts_df = _fetch_yf_option_chain(ticker, expiry)
        options_df = calls_df if option_type == "call" else puts_df

        # Find the closest strike (may not be exact due to floating point)
        strike_diff = (options_df['strike'] - strike).abs()
        closest_idx = strike_diff.idxmin()
        closest_row = options_df.loc[closest_idx]

        # Only use if strike matches within $0.50
        if abs(closest_row['strike'] - strike) <= 0.50:
            oi = int(closest_row.get('openInterest', 0) or 0)
            if oi > 0:
                logger.debug(f"OI fallback to yfinance for {ticker} {strike} {expiry}: {oi}")
                return oi
    except Exception as e:
        logger.debug(f"yfinance OI fallback failed for {ticker}: {e}")

    return questrade_oi  # Return original (0) if fallback fails


def _calculate_liquidity_score(
    bid_ask_spread_pct: float,
    open_interest: int,
    daily_volume: int,
    underlying_volume: int,
    bid_size: int = 10,
    ask_size: int = 10,
    liquidity_tier: str = None
) -> dict:
    """
    Calculate composite liquidity score using institutional weights.

    Weights (from institutional document):
    - Bid-ask spread %: 35%
    - Open interest: 25%
    - Daily volume: 20%
    - Underlying volume: 10%
    - Size at bid/ask: 10%

    Args:
        liquidity_tier: TIER_1, TIER_2, TIER_3, or TIER_4. If TIER_1 and data unavailable
                       (off-market hours), uses underlying volume as proxy instead of rejecting.

    Returns:
        dict with score (0-100), grade, warnings
    """
    params = INSTITUTIONAL_OPTIONS_PARAMS
    score = 0
    warnings = []
    factors = []
    is_tier_1 = liquidity_tier == "TIER_1"

    # Detect off-market hours scenario: OI=0 AND spread looks defaulted
    # This happens when running reports at 6am before options markets open
    off_market_data = (open_interest == 0 and daily_volume == 0 and bid_ask_spread_pct >= 5.0)

    if off_market_data and is_tier_1:
        warnings.append("ℹ️ Options data unavailable (likely off-market hours) - using TIER_1 proxy")

    # 1. Bid-Ask Spread (35% weight) - Lower is better
    # CHECK OFF-MARKET TIER_1 FIRST - when data is clearly unavailable
    if off_market_data and is_tier_1:
        # TIER_1 off-market: assume penny-wide spreads typical of institutional-grade options
        spread_score = 30
        factors.append(f"Spread unavailable (off-market), TIER_1 proxy: +{spread_score:.0f}")
    elif bid_ask_spread_pct <= params['preferred_spread_pct']:
        spread_score = 35
        factors.append(f"Spread {bid_ask_spread_pct:.1f}% ≤ {params['preferred_spread_pct']}%: +35")
    elif bid_ask_spread_pct <= params['max_spread_pct']:
        spread_score = 35 * (1 - (bid_ask_spread_pct - params['preferred_spread_pct']) /
                           (params['max_spread_pct'] - params['preferred_spread_pct']))
        factors.append(f"Spread {bid_ask_spread_pct:.1f}%: +{spread_score:.0f}")
    else:
        spread_score = 0
        warnings.append(f"🚫 REJECT: Spread {bid_ask_spread_pct:.1f}% > {params['max_spread_pct']}% max")
        factors.append(f"Spread {bid_ask_spread_pct:.1f}% too wide: +0")
    score += spread_score

    # 2. Open Interest (25% weight)
    # CHECK OFF-MARKET TIER_1 FIRST - when data is clearly unavailable
    if off_market_data and is_tier_1:
        # TIER_1 off-market: use underlying volume as proxy
        # High underlying volume (>10M) indicates actively traded stock with liquid options
        if underlying_volume >= 10_000_000:
            oi_score = 22  # High confidence proxy
            factors.append(f"OI unavailable (off-market), TIER_1 + high vol proxy: +{oi_score:.0f}")
        elif underlying_volume >= 1_000_000:
            oi_score = 18  # Medium confidence proxy
            factors.append(f"OI unavailable (off-market), TIER_1 proxy: +{oi_score:.0f}")
        else:
            oi_score = 10  # Low confidence - verify during market hours
            factors.append(f"OI unavailable (off-market), TIER_1 low vol: +{oi_score:.0f}")
            warnings.append("⚠️ Verify liquidity during market hours")
    elif open_interest >= params['preferred_open_interest']:
        oi_score = 25
        factors.append(f"OI {open_interest:,}: +{oi_score:.0f}")
    elif open_interest >= params['min_open_interest']:
        oi_score = 25 * (open_interest - params['min_open_interest']) / \
                   (params['preferred_open_interest'] - params['min_open_interest'])
        warnings.append(f"⚠️ Low OI ({open_interest}) - reduce size")
        factors.append(f"OI {open_interest:,}: +{oi_score:.0f}")
    else:
        oi_score = 0
        warnings.append(f"🚫 REJECT: OI {open_interest} < {params['min_open_interest']} min")
        factors.append(f"OI {open_interest}: +{oi_score:.0f}")
    score += oi_score

    # 3. Daily Volume (20% weight)
    if daily_volume >= params['min_volume'] * 10:  # 500+ volume
        vol_score = 20
        factors.append(f"Volume {daily_volume:,}: +{vol_score:.0f}")
    elif daily_volume >= params['min_volume']:
        vol_score = 20 * (daily_volume / (params['min_volume'] * 10))
        factors.append(f"Volume {daily_volume:,}: +{vol_score:.0f}")
    elif off_market_data and is_tier_1:
        # TIER_1 off-market: assume typical volume based on underlying activity
        vol_score = 15  # Conservative proxy
        factors.append(f"Volume unavailable (off-market), TIER_1 proxy: +{vol_score:.0f}")
    else:
        vol_score = 0 if open_interest < params['min_open_interest'] * 5 else 10  # OI can substitute
        if daily_volume < params['min_volume'] and open_interest < params['min_open_interest'] * 5:
            warnings.append(f"⚠️ Low volume ({daily_volume}) and OI")
        factors.append(f"Volume {daily_volume:,}: +{vol_score:.0f}")
    score += vol_score

    # 4. Underlying Volume (10% weight)
    if underlying_volume >= params['min_underlying_volume'] * 2:
        under_score = 10
    elif underlying_volume >= params['min_underlying_volume']:
        under_score = 10 * (underlying_volume / (params['min_underlying_volume'] * 2))
    else:
        under_score = 0
        warnings.append(f"⚠️ Low underlying volume ({underlying_volume:,})")
    score += under_score
    factors.append(f"Underlying Vol {underlying_volume:,}: +{under_score:.0f}")

    # 5. Size at Bid/Ask (10% weight)
    min_size = 5  # Minimum contracts each side
    if bid_size >= min_size and ask_size >= min_size:
        size_score = 10
    elif bid_size >= min_size or ask_size >= min_size:
        size_score = 5
    else:
        size_score = 0
        warnings.append(f"⚠️ Thin book: bid size {bid_size}, ask size {ask_size}")
    score += size_score
    factors.append(f"Book depth: +{size_score:.0f}")

    # Determine grade
    if score >= 80:
        grade = "A"
        grade_desc = "Excellent liquidity"
    elif score >= 60:
        grade = "B"
        grade_desc = "Good liquidity"
    elif score >= 40:
        grade = "C"
        grade_desc = "Fair liquidity - use caution"
    else:
        grade = "F"
        grade_desc = "Poor liquidity - SKIP"
        if "REJECT" not in str(warnings):
            warnings.append("🚫 REJECT: Liquidity score < 40")

    return {
        "score": round(score, 1),
        "grade": grade,
        "grade_description": grade_desc,
        "factors": factors,
        "warnings": warnings,
        "tradeable": score >= 40 and "🚫 REJECT" not in str(warnings)
    }


def _find_target_expiry(expirations: list, target_dte: int = None) -> dict:
    """
    Find optimal expiration targeting ~45 DTE.

    RULE: 45 DTE entry with 50% profit management = 88% win rate

    Args:
        expirations: List of expiration dates (YYYY-MM-DD strings)
        target_dte: Target days to expiration (default: 45)

    Returns:
        dict with optimal_expiry, dte, theta_zone
    """
    from datetime import datetime, timedelta

    if target_dte is None:
        target_dte = INSTITUTIONAL_OPTIONS_PARAMS['target_dte']

    today = datetime.now()
    target_date = today + timedelta(days=target_dte)

    if not expirations:
        return {
            "optimal_expiry": None,
            "dte": None,
            "theta_zone": "UNKNOWN",
            "warning": "No expirations available"
        }

    # Find closest expiry to target
    best_expiry = None
    best_dte = None
    min_diff = float('inf')

    for exp in expirations:
        try:
            exp_date = datetime.strptime(exp[:10], '%Y-%m-%d')
            dte = (exp_date - today).days
            diff = abs(dte - target_dte)

            # Prefer slightly longer than shorter (safer)
            if diff < min_diff or (diff == min_diff and dte > target_dte):
                min_diff = diff
                best_expiry = exp[:10]
                best_dte = dte
        except Exception:
            continue

    # Determine theta zone
    theta_zone = "UNKNOWN"
    zone_warning = None
    for (high, low), decay in THETA_DECAY_TABLE.items():
        if low <= best_dte <= high:
            if high == 60:
                theta_zone = "OPTIMAL_ENTRY"
            elif high == 45:
                theta_zone = "PRIMARY_CAPTURE"
            elif high == 30:
                theta_zone = "DECISION_POINT"
                zone_warning = "⚠️ Near 21 DTE - plan to roll or close"
            elif high == 21:
                theta_zone = "HIGH_GAMMA_RISK"
                zone_warning = "🚨 Exit zone - high gamma risk"
            else:
                theta_zone = "BINARY_ZONE"
                zone_warning = "🚫 AVOID - binary expiration risk"
            break

    return {
        "optimal_expiry": best_expiry,
        "dte": best_dte,
        "target_dte": target_dte,
        "theta_zone": theta_zone,
        "daily_decay_rate": THETA_DECAY_TABLE.get(
            next(((h, l) for (h, l) in THETA_DECAY_TABLE.keys() if l <= best_dte <= h), (45, 30)),
            0.01
        ),
        "warning": zone_warning
    }


def _find_delta_strike(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    current_price: float,
    direction: str,
    target_delta: float = None
) -> dict:
    """
    Find strike at target delta for institutional options strategies.

    RULE: 16-delta for short strikes in credit strategies

    Args:
        calls_df: Calls dataframe with delta column
        puts_df: Puts dataframe with delta column
        current_price: Current stock price
        direction: LONG or SHORT
        target_delta: Target delta (default: 16)

    Returns:
        dict with strike, actual_delta, premium
    """
    if target_delta is None:
        target_delta = INSTITUTIONAL_OPTIONS_PARAMS['short_strike_delta'] / 100  # Convert to decimal

    # For LONG direction: sell put at -16 delta (OTM put)
    # For SHORT direction: sell call at +16 delta (OTM call)

    result = {
        "short_strike": None,
        "short_delta": None,
        "short_premium": None,
        "long_strike": None,  # For spreads (wing)
        "long_delta": None,
        "long_premium": None,
        "method": "delta_targeting"
    }

    try:
        if direction == "LONG":
            # Sell OTM put - find put with delta closest to -0.16
            if not puts_df.empty and 'delta' in puts_df.columns:
                puts_df_sorted = puts_df.copy()
                puts_df_sorted['delta_diff'] = abs(abs(puts_df_sorted['delta']) - target_delta)
                best_put = puts_df_sorted.nsmallest(1, 'delta_diff').iloc[0]

                result["short_strike"] = float(best_put['strike'])
                result["short_delta"] = float(best_put.get('delta', 0))
                result["short_premium"] = float(best_put.get('bid', 0) or best_put.get('lastPrice', 0))

                # Wing strike (5 points lower for spread)
                wing_strike = result["short_strike"] - 5
                wing_row = puts_df[puts_df['strike'] == wing_strike]
                if not wing_row.empty:
                    result["long_strike"] = float(wing_strike)
                    result["long_delta"] = float(wing_row.iloc[0].get('delta', 0))
                    result["long_premium"] = float(wing_row.iloc[0].get('ask', 0) or wing_row.iloc[0].get('lastPrice', 0))
            else:
                # Fallback: estimate OTM put strike from price
                otm_pct = 0.05  # 5% OTM for ~16 delta
                result["short_strike"] = round(current_price * (1 - otm_pct) / 5) * 5  # Round to $5
                result["method"] = "price_estimation"

        elif direction == "SHORT":
            # Sell OTM call - find call with delta closest to +0.16
            if not calls_df.empty and 'delta' in calls_df.columns:
                calls_df_sorted = calls_df.copy()
                calls_df_sorted['delta_diff'] = abs(calls_df_sorted['delta'] - target_delta)
                best_call = calls_df_sorted.nsmallest(1, 'delta_diff').iloc[0]

                result["short_strike"] = float(best_call['strike'])
                result["short_delta"] = float(best_call.get('delta', 0))
                result["short_premium"] = float(best_call.get('bid', 0) or best_call.get('lastPrice', 0))

                # Wing strike (5 points higher for spread)
                wing_strike = result["short_strike"] + 5
                wing_row = calls_df[calls_df['strike'] == wing_strike]
                if not wing_row.empty:
                    result["long_strike"] = float(wing_strike)
                    result["long_delta"] = float(wing_row.iloc[0].get('delta', 0))
                    result["long_premium"] = float(wing_row.iloc[0].get('ask', 0) or wing_row.iloc[0].get('lastPrice', 0))
            else:
                # Fallback: estimate OTM call strike from price
                otm_pct = 0.05  # 5% OTM for ~16 delta
                result["short_strike"] = round(current_price * (1 + otm_pct) / 5) * 5
                result["method"] = "price_estimation"

    except Exception as e:
        logger.warning(f"Error finding delta strike: {e}")
        result["warning"] = str(e)

    return result


def _get_current_price(ticker: str) -> float:
    """
    Get current price for a ticker.

    Reusable helper function for position valuation.
    Uses the existing get_ticker_info_questrade_first infrastructure.

    Args:
        ticker: Stock symbol

    Returns:
        float: Current price (defaults to 100.0 if unavailable)
    """
    try:
        # Use existing infrastructure to get ticker info
        ticker_info = get_ticker_info_questrade_first(ticker)
        info = ticker_info.get("merged", {})

        price = info.get('currentPrice')
        if price is not None and price > 0:
            return float(price)

        # Fallback: estimate $100
        logger.warning(f"Price not available for {ticker}, defaulting to 100.0")
        return 100.0

    except Exception as e:
        logger.warning(f"Failed to get price for {ticker}: {e}, defaulting to 100.0")
        return 100.0


def _get_questrade_options_with_greeks(
    ticker: str,
    expiry_date: str,
    current_price: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetch options chain from Questrade with full Greeks (delta, gamma, theta, vega).

    This is the CORRECT way to get Questrade options - used by GEX, IV Skew, etc.
    Returns separate DataFrames for calls and puts with all Greeks populated.

    Args:
        ticker: Stock symbol
        expiry_date: Target expiration date in 'YYYY-MM-DD' format
        current_price: Current stock price for validation

    Returns:
        (calls_df, puts_df) - Both DataFrames have columns:
            - strike: float
            - delta: float
            - gamma: float
            - theta: float
            - vega: float
            - impliedVolatility: float (as percentage)
            - bid: float
            - ask: float
            - lastPrice: float
            - openInterest: int
            - volume: int

    Raises:
        Exception if Questrade fetch fails
    """
    from datetime import datetime
    from questrade_api import Questrade

    logger.info(f"Fetching Questrade options for {ticker} expiry {expiry_date}")

    # 1. Get symbol ID
    qt_client = get_questrade_client()
    symbol_info = qt_client.get_symbol_info(ticker)

    if not symbol_info or not symbol_info.get('symbols'):
        raise ValueError(f"Symbol {ticker} not found in Questrade")

    symbol_id = symbol_info['symbols'][0]['symbolId']
    logger.info(f"Got symbol ID {symbol_id} for {ticker}")

    # 2. Get options chain using raw Questrade API
    q = Questrade()
    qt_options = q.symbol_options(symbol_id)

    if not qt_options or 'optionChain' not in qt_options:
        raise ValueError(f"No options chain available for {ticker}")

    # 3. Find matching expiration
    expirations_list = qt_options['optionChain']
    if not expirations_list:
        raise ValueError(f"No expirations available for {ticker}")

    selected_exp_obj = None
    for exp_obj in expirations_list:
        exp_str = datetime.strptime(exp_obj['expiryDate'], '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%d')
        if exp_str == expiry_date:
            selected_exp_obj = exp_obj
            break

    if not selected_exp_obj:
        raise ValueError(f"Expiration {expiry_date} not found for {ticker}")

    logger.info(f"Found matching expiration {expiry_date}")

    # 4. Collect all option IDs
    option_ids = []
    for root_data in selected_exp_obj['chainPerRoot']:
        for strike_data in root_data['chainPerStrikePrice']:
            if 'callSymbolId' in strike_data and strike_data['callSymbolId']:
                option_ids.append(strike_data['callSymbolId'])
            if 'putSymbolId' in strike_data and strike_data['putSymbolId']:
                option_ids.append(strike_data['putSymbolId'])

    if len(option_ids) == 0:
        raise ValueError(f"No option IDs found for {ticker} {expiry_date}")

    logger.info(f"Collected {len(option_ids)} option IDs")

    # 5. Fetch quotes with Greeks in batches
    all_quotes = []
    batch_size = 100
    for i in range(0, len(option_ids), batch_size):
        batch = option_ids[i:i+batch_size]
        logger.info(f"Fetching batch {i//batch_size + 1} of {(len(option_ids)-1)//batch_size + 1} ({len(batch)} options)")
        quotes = q.markets_options(optionIds=batch)
        if quotes and 'optionQuotes' in quotes:
            all_quotes.extend(quotes['optionQuotes'])

    logger.info(f"Total quotes retrieved: {len(all_quotes)}")

    # 6. Parse quotes into calls and puts DataFrames
    calls_data = []
    puts_data = []

    for quote in all_quotes:
        symbol = quote['symbol']

        # Parse Questrade symbol format: "SPY20Feb26C335.00"
        # Find rightmost C or P (ticker might contain C or P)
        c_pos = symbol.rfind('C')
        p_pos = symbol.rfind('P')

        if c_pos > p_pos and c_pos != -1:
            # Call option
            strike = float(symbol[c_pos+1:])
            option_data = {
                'strike': strike,
                'delta': float(quote.get('delta', 0) or 0),
                'gamma': float(quote.get('gamma', 0) or 0),
                'theta': float(quote.get('theta', 0) or 0),
                'vega': float(quote.get('vega', 0) or 0),
                'impliedVolatility': float(quote.get('volatility', 0) or 0),
                'bid': float(quote.get('bidPrice', 0) or 0),
                'ask': float(quote.get('askPrice', 0) or 0),
                'lastPrice': float(quote.get('lastTradePrc', 0) or 0),
                'openInterest': int(quote.get('openInterest', 0) or 0),
                'volume': int(quote.get('volume', 0) or 0)
            }
            calls_data.append(option_data)

        elif p_pos > c_pos and p_pos != -1:
            # Put option
            strike = float(symbol[p_pos+1:])
            option_data = {
                'strike': strike,
                'delta': float(quote.get('delta', 0) or 0),
                'gamma': float(quote.get('gamma', 0) or 0),
                'theta': float(quote.get('theta', 0) or 0),
                'vega': float(quote.get('vega', 0) or 0),
                'impliedVolatility': float(quote.get('volatility', 0) or 0),
                'bid': float(quote.get('bidPrice', 0) or 0),
                'ask': float(quote.get('askPrice', 0) or 0),
                'lastPrice': float(quote.get('lastTradePrc', 0) or 0),
                'openInterest': int(quote.get('openInterest', 0) or 0),
                'volume': int(quote.get('volume', 0) or 0)
            }
            puts_data.append(option_data)

    calls_df = pd.DataFrame(calls_data)
    puts_df = pd.DataFrame(puts_data)

    logger.info(f"✅ Questrade options: {len(calls_df)} calls, {len(puts_df)} puts with full Greeks")

    return calls_df, puts_df


def _construct_iron_condor(
    ticker: str,
    current_price: float,
    expiry: str,
    dte: int,
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    account_size: float
) -> dict:
    """
    Construct explicit 4-leg Iron Condor with full parameters.

    Returns fully actionable trade with strikes, premiums, Greeks, and position sizing.

    Strategy Structure:
    - SELL 16-delta OTM put
    - BUY 5-delta OTM put (protection)
    - SELL 16-delta OTM call
    - BUY 5-delta OTM call (protection)

    Args:
        ticker: Stock symbol
        current_price: Current stock price
        expiry: Expiration date
        dte: Days to expiration
        calls_df: Options chain calls dataframe
        puts_df: Options chain puts dataframe
        account_size: Account size for position sizing

    Returns:
        dict with full Iron Condor specification
    """
    import pandas as pd

    # 1. Find 16-delta short strikes (both put and call)
    put_short = None
    put_long = None
    call_short = None
    call_long = None

    # Find short put (16-delta OTM put)
    if not puts_df.empty and 'delta' in puts_df.columns:
        puts_df_sorted = puts_df.copy()
        target_delta = 0.16
        puts_df_sorted['delta_diff'] = abs(abs(puts_df_sorted['delta']) - target_delta)
        best_put = puts_df_sorted.nsmallest(1, 'delta_diff').iloc[0]

        put_short = {
            "strike": float(best_put['strike']),
            "delta": float(best_put.get('delta', -0.16)),
            "premium": float(best_put.get('bid', 0) or best_put.get('lastPrice', 0)),
            "iv": float(best_put.get('impliedVolatility', 0)) * 100 if best_put.get('impliedVolatility', 0) < 1.5 else float(best_put.get('impliedVolatility', 0)),
            "gamma": float(best_put.get('gamma', 0)),
            "theta": float(best_put.get('theta', 0)),
            "vega": float(best_put.get('vega', 0))
        }

        # Find long put (5-delta protection - further OTM)
        target_delta_long = 0.05
        puts_df_sorted['delta_diff_long'] = abs(abs(puts_df_sorted['delta']) - target_delta_long)
        # Only consider strikes below the short put
        puts_below = puts_df_sorted[puts_df_sorted['strike'] < put_short['strike']]
        if not puts_below.empty:
            best_put_long = puts_below.nsmallest(1, 'delta_diff_long').iloc[0]

            put_long = {
                "strike": float(best_put_long['strike']),
                "delta": float(best_put_long.get('delta', -0.05)),
                "premium": float(best_put_long.get('ask', 0) or best_put_long.get('lastPrice', 0)),
                "iv": float(best_put_long.get('impliedVolatility', 0)) * 100 if best_put_long.get('impliedVolatility', 0) < 1.5 else float(best_put_long.get('impliedVolatility', 0)),
                "gamma": float(best_put_long.get('gamma', 0)),
                "theta": float(best_put_long.get('theta', 0)),
                "vega": float(best_put_long.get('vega', 0))
            }

    # Find short call (16-delta OTM call)
    if not calls_df.empty and 'delta' in calls_df.columns:
        calls_df_sorted = calls_df.copy()
        target_delta = 0.16
        calls_df_sorted['delta_diff'] = abs(calls_df_sorted['delta'] - target_delta)
        best_call = calls_df_sorted.nsmallest(1, 'delta_diff').iloc[0]

        call_short = {
            "strike": float(best_call['strike']),
            "delta": float(best_call.get('delta', 0.16)),
            "premium": float(best_call.get('bid', 0) or best_call.get('lastPrice', 0)),
            "iv": float(best_call.get('impliedVolatility', 0)) * 100 if best_call.get('impliedVolatility', 0) < 1.5 else float(best_call.get('impliedVolatility', 0)),
            "gamma": float(best_call.get('gamma', 0)),
            "theta": float(best_call.get('theta', 0)),
            "vega": float(best_call.get('vega', 0))
        }

        # Find long call (5-delta protection - further OTM)
        target_delta_long = 0.05
        calls_df_sorted['delta_diff_long'] = abs(calls_df_sorted['delta'] - target_delta_long)
        # Only consider strikes above the short call
        calls_above = calls_df_sorted[calls_df_sorted['strike'] > call_short['strike']]
        if not calls_above.empty:
            best_call_long = calls_above.nsmallest(1, 'delta_diff_long').iloc[0]

            call_long = {
                "strike": float(best_call_long['strike']),
                "delta": float(best_call_long.get('delta', 0.05)),
                "premium": float(best_call_long.get('ask', 0) or best_call_long.get('lastPrice', 0)),
                "iv": float(best_call_long.get('impliedVolatility', 0)) * 100 if best_call_long.get('impliedVolatility', 0) < 1.5 else float(best_call_long.get('impliedVolatility', 0)),
                "gamma": float(best_call_long.get('gamma', 0)),
                "theta": float(best_call_long.get('theta', 0)),
                "vega": float(best_call_long.get('vega', 0))
            }

    # If we couldn't find all 4 legs, return None
    if not all([put_short, put_long, call_short, call_long]):
        return None

    # 2. Calculate net credit
    net_credit = (put_short['premium'] + call_short['premium']) - (put_long['premium'] + call_long['premium'])

    # 3. Calculate spread widths
    put_spread_width = put_short['strike'] - put_long['strike']
    call_spread_width = call_long['strike'] - call_short['strike']
    max_spread_width = max(put_spread_width, call_spread_width)

    # 4. Calculate risk metrics
    max_loss_per_contract = (max_spread_width - net_credit) * 100
    max_profit_per_contract = net_credit * 100

    # 5. Position sizing (limit risk to 2% of account)
    max_risk_dollars = account_size * 0.02  # 2% risk
    contracts = max(1, int(max_risk_dollars / max_loss_per_contract))

    # 6. Aggregate Greeks (for entire position)
    # Each leg's contribution: short = negative sign, long = positive sign
    position_delta = (
        -put_short['delta'] * contracts * 100 +  # Short put = negative delta
        put_long['delta'] * contracts * 100 +     # Long put = positive delta
        -call_short['delta'] * contracts * 100 +  # Short call = negative delta
        call_long['delta'] * contracts * 100      # Long call = positive delta
    )

    position_gamma = (
        -put_short['gamma'] * contracts * 100 +
        put_long['gamma'] * contracts * 100 +
        -call_short['gamma'] * contracts * 100 +
        call_long['gamma'] * contracts * 100
    )

    position_theta = (
        -put_short['theta'] * contracts * 100 +
        put_long['theta'] * contracts * 100 +
        -call_short['theta'] * contracts * 100 +
        call_long['theta'] * contracts * 100
    )

    position_vega = (
        -put_short['vega'] * contracts * 100 +
        put_long['vega'] * contracts * 100 +
        -call_short['vega'] * contracts * 100 +
        call_long['vega'] * contracts * 100
    )

    # 7. Calculate POP (probability of profit)
    # POP = 100 - (short put delta + short call delta) * 50
    pop = round(100 - (abs(put_short['delta']) + abs(call_short['delta'])) * 50, 1)

    # 8. Calculate breakevens
    breakeven_lower = put_short['strike'] - net_credit
    breakeven_upper = call_short['strike'] + net_credit

    # 9. Liquidity score (estimate based on bid-ask spread)
    avg_spread_pct = (
        (put_short['premium'] * 0.02) +  # Estimate 2% spread for liquid options
        (call_short['premium'] * 0.02)
    ) / 2
    liquidity_score = max(0, min(100, 100 - avg_spread_pct * 10))  # Simple scoring

    # 10. Slippage estimate (4% of net credit)
    spread_cost_estimate = net_credit * 0.04 * contracts * 100

    # 11. Build output
    return {
        "strategy": "IRON_CONDOR",
        "legs": [
            {
                "action": "SELL",
                "option_type": "CALL",
                "strike": call_short['strike'],
                "expiry": expiry,
                "delta": call_short['delta'],
                "iv": call_short['iv'],
                "premium": call_short['premium'],
                "contracts": contracts
            },
            {
                "action": "BUY",
                "option_type": "CALL",
                "strike": call_long['strike'],
                "expiry": expiry,
                "delta": call_long['delta'],
                "iv": call_long['iv'],
                "premium": call_long['premium'],
                "contracts": contracts
            },
            {
                "action": "SELL",
                "option_type": "PUT",
                "strike": put_short['strike'],
                "expiry": expiry,
                "delta": put_short['delta'],
                "iv": put_short['iv'],
                "premium": put_short['premium'],
                "contracts": contracts
            },
            {
                "action": "BUY",
                "option_type": "PUT",
                "strike": put_long['strike'],
                "expiry": expiry,
                "delta": put_long['delta'],
                "iv": put_long['iv'],
                "premium": put_long['premium'],
                "contracts": contracts
            }
        ],
        "net_credit": round(net_credit, 2),
        "max_profit": round(max_profit_per_contract * contracts, 2),
        "max_loss": round(max_loss_per_contract * contracts, 2),
        "breakeven_upper": round(breakeven_upper, 2),
        "breakeven_lower": round(breakeven_lower, 2),
        "probability_of_profit": pop,
        "position_greeks": {
            "delta": round(position_delta, 2),
            "gamma": round(position_gamma, 4),
            "theta": round(position_theta, 2),
            "vega": round(position_vega, 2)
        },
        "liquidity_score": round(liquidity_score, 1),
        "spread_cost_estimate": round(spread_cost_estimate, 2),
        "dte": dte,
        "put_spread_width": put_spread_width,
        "call_spread_width": call_spread_width,
        "contracts": contracts,
        "buying_power_required": round(max_loss_per_contract * contracts, 2)
    }


def _calculate_expected_move(current_price: float, iv: float, dte: int) -> dict:
    """
    Calculate expected move from IV.

    Formula: Expected Move = Price × IV × √(DTE/365)
    Alternative: ATM Straddle Price × 0.85

    Returns:
        dict with expected_move_dollars, expected_move_pct, range
    """
    import math

    # Convert IV to decimal if percentage
    if iv > 1.5:
        iv = iv / 100

    time_factor = math.sqrt(dte / 365)
    expected_move = current_price * iv * time_factor
    expected_move_pct = iv * time_factor * 100

    return {
        "expected_move_dollars": round(expected_move, 2),
        "expected_move_pct": round(expected_move_pct, 2),
        "upper_range": round(current_price + expected_move, 2),
        "lower_range": round(current_price - expected_move, 2),
        "iv_used": round(iv * 100, 1),
        "dte": dte,
        "formula": f"${current_price:.2f} × {iv*100:.1f}% × √({dte}/365) = ${expected_move:.2f}"
    }


def _construct_calendar_spread(
    ticker: str,
    current_price: float,
    front_month_expiry: str,
    back_month_expiry: str,
    front_calls_df: pd.DataFrame,
    front_puts_df: pd.DataFrame,
    back_calls_df: pd.DataFrame,
    back_puts_df: pd.DataFrame,
    account_size: float,
    direction: str = 'NEUTRAL'
) -> dict:
    """
    Construct Calendar Spread (time spread).

    **Uses Questrade as primary source** (dataframes already fetched with Questrade-first).

    Structure:
    - SELL near-term option (higher theta decay)
    - BUY far-term option at same strike (lower theta decay)

    Profit from theta differential when:
    - Term structure in contango (back-month IV > front-month IV)
    - Price stays near ATM strike
    - IV Rank < 50% (don't sell premium in low IV)

    Args:
        ticker: Stock symbol
        current_price: Current stock price
        front_month_expiry: Near-term expiration (to sell)
        back_month_expiry: Far-term expiration (to buy)
        front_calls_df: Front month calls dataframe
        front_puts_df: Front month puts dataframe
        back_calls_df: Back month calls dataframe
        back_puts_df: Back month puts dataframe
        account_size: Account size for position sizing
        direction: 'NEUTRAL' (default), 'BULLISH', or 'BEARISH'

    Returns:
        dict with full Calendar Spread specification or None if cannot construct
    """
    import pandas as pd
    from datetime import datetime

    # Calculate DTE for front and back months
    front_dte = (datetime.strptime(front_month_expiry, '%Y-%m-%d') - datetime.now()).days
    back_dte = (datetime.strptime(back_month_expiry, '%Y-%m-%d') - datetime.now()).days

    # Choose calls or puts based on direction
    if direction.upper() == 'BULLISH':
        # Use calls for bullish bias
        front_options = front_calls_df
        back_options = back_calls_df
        option_type = 'CALL'
    elif direction.upper() == 'BEARISH':
        # Use puts for bearish bias
        front_options = front_puts_df
        back_options = back_puts_df
        option_type = 'PUT'
    else:
        # NEUTRAL - use calls (slightly bullish bias typical for calendars)
        front_options = front_calls_df
        back_options = back_calls_df
        option_type = 'CALL'

    if front_options.empty or back_options.empty:
        logger.warning(f"Calendar Spread: Empty options dataframes for {ticker}")
        return None

    # Find ATM strike (closest to current price)
    all_strikes = set(front_options['strike'].tolist()) & set(back_options['strike'].tolist())
    if not all_strikes:
        logger.warning(f"Calendar Spread: No common strikes between front and back months")
        return None

    atm_strike = min(all_strikes, key=lambda x: abs(x - current_price))

    # Get front month option (to SELL)
    front_option = front_options[front_options['strike'] == atm_strike]
    if front_option.empty:
        return None
    front_option = front_option.iloc[0]

    # Get back month option (to BUY)
    back_option = back_options[back_options['strike'] == atm_strike]
    if back_option.empty:
        return None
    back_option = back_option.iloc[0]

    # Extract data
    front_premium = float(front_option.get('bid', 0) or front_option.get('lastPrice', 0))
    back_premium = float(back_option.get('ask', 0) or back_option.get('lastPrice', 0))

    front_iv = float(front_option.get('impliedVolatility', 0))
    back_iv = float(back_option.get('impliedVolatility', 0))

    # Normalize IV
    if front_iv > 5:
        front_iv = front_iv / 100
    if back_iv > 5:
        back_iv = back_iv / 100

    # Check term structure (need contango: back_iv > front_iv)
    if back_iv <= front_iv:
        logger.warning(f"Calendar Spread: Term structure NOT in contango (back IV {back_iv:.2%} <= front IV {front_iv:.2%})")
        # Still allow construction but warn

    # Net debit (we pay to enter)
    net_debit = back_premium - front_premium

    if net_debit <= 0:
        logger.warning(f"Calendar Spread: Net debit is non-positive ({net_debit}), cannot construct")
        return None

    # Position sizing (limit risk to 2% of account)
    max_loss_per_contract = net_debit * 100  # Debit paid
    max_risk_dollars = account_size * 0.02
    contracts = max(1, int(max_risk_dollars / max_loss_per_contract))

    # Max profit occurs when front month expires worthless and back month retains value
    # Approximate: back month value at front expiration - debit paid
    # Conservative estimate: 50% of back month premium
    max_profit_estimate = (back_premium * 0.5 - net_debit) * 100 * contracts

    # Greeks (approximate)
    front_delta = float(front_option.get('delta', 0))
    back_delta = float(back_option.get('delta', 0))
    front_theta = float(front_option.get('theta', 0))
    back_theta = float(back_option.get('theta', 0))
    front_vega = float(front_option.get('vega', 0))
    back_vega = float(back_option.get('vega', 0))

    # Position Greeks (SELL front, BUY back)
    position_delta = (-front_delta + back_delta) * contracts * 100
    position_theta = (-front_theta + back_theta) * contracts * 100  # Positive theta (profit from time decay)
    position_vega = (-front_vega + back_vega) * contracts * 100      # Positive vega (want IV to rise)

    # Liquidity score (simple average)
    front_volume = front_option.get('volume', 0) or 0
    back_volume = back_option.get('volume', 0) or 0
    liquidity_score = min(10, (front_volume + back_volume) / 20)

    return {
        "strategy": "Calendar Spread",
        "option_type": option_type,
        "direction": direction,
        "strike": atm_strike,
        "front_expiry": front_month_expiry,
        "back_expiry": back_month_expiry,
        "front_dte": front_dte,
        "back_dte": back_dte,

        "legs": [
            {
                "action": "SELL",
                "option_type": option_type,
                "strike": atm_strike,
                "expiry": front_month_expiry,
                "premium": front_premium,
                "iv": round(front_iv * 100, 2),
                "delta": front_delta,
                "theta": front_theta,
                "vega": front_vega
            },
            {
                "action": "BUY",
                "option_type": option_type,
                "strike": atm_strike,
                "expiry": back_month_expiry,
                "premium": back_premium,
                "iv": round(back_iv * 100, 2),
                "delta": back_delta,
                "theta": back_theta,
                "vega": back_vega
            }
        ],

        "net_debit": round(net_debit, 2),
        "max_loss": round(max_loss_per_contract * contracts, 2),
        "max_profit_estimate": round(max_profit_estimate, 2),
        "contracts": contracts,
        "buying_power_required": round(max_loss_per_contract * contracts, 2),

        "position_greeks": {
            "delta": round(position_delta, 2),
            "theta": round(position_theta, 2),
            "vega": round(position_vega, 2)
        },

        "term_structure": {
            "front_iv": round(front_iv * 100, 2),
            "back_iv": round(back_iv * 100, 2),
            "iv_differential": round((back_iv - front_iv) * 100, 2),
            "is_contango": back_iv > front_iv
        },

        "liquidity_score": round(liquidity_score, 1),

        "ideal_conditions": [
            f"✅ Term structure in contango" if back_iv > front_iv else "❌ Term structure NOT in contango",
            f"✅ Price near ATM (${atm_strike})" if abs(current_price - atm_strike) < current_price * 0.05 else f"⚠️ Price {abs(current_price - atm_strike)/current_price*100:.1f}% from ATM",
            "✅ Positive theta (profit from time decay)" if position_theta > 0 else "❌ Negative theta"
        ]
    }


def _construct_jade_lizard(
    ticker: str,
    current_price: float,
    expiry: str,
    dte: int,
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    account_size: float
) -> dict:
    """
    Construct Jade Lizard (no upside risk).

    **Uses Questrade as primary source** (dataframes already fetched with Questrade-first).

    Structure:
    - SELL OTM call spread (bear call spread)
    - SELL OTM put (cash-secured put)

    Condition for NO upside risk:
    - Put premium >= Call spread width
    - This creates NO upside risk (max loss on downside only)

    Ideal when:
    - IV Rank > 60%
    - Neutral to bullish bias
    - Put premium is inflated (put skew)

    Args:
        ticker: Stock symbol
        current_price: Current stock price
        expiry: Expiration date
        dte: Days to expiration
        calls_df: Calls dataframe
        puts_df: Puts dataframe
        account_size: Account size for position sizing

    Returns:
        dict with full Jade Lizard specification or None if cannot construct
    """
    import pandas as pd

    if calls_df.empty or puts_df.empty:
        logger.warning(f"Jade Lizard: Empty options dataframes for {ticker}")
        return None

    # 1. Find OTM put to SELL (around 20-30 delta)
    if 'delta' not in puts_df.columns:
        logger.warning(f"Jade Lizard: No delta column in puts dataframe")
        return None

    target_put_delta = 0.25  # 25-delta OTM put
    puts_df_sorted = puts_df.copy()
    puts_df_sorted['delta_diff'] = abs(abs(puts_df_sorted['delta']) - target_put_delta)
    best_put = puts_df_sorted.nsmallest(1, 'delta_diff')

    if best_put.empty:
        return None

    best_put = best_put.iloc[0]
    put_strike = float(best_put['strike'])
    put_premium = float(best_put.get('bid', 0) or best_put.get('lastPrice', 0))
    put_delta = float(best_put.get('delta', -0.25))
    put_iv = float(best_put.get('impliedVolatility', 0))
    if put_iv > 5:
        put_iv = put_iv / 100

    # 2. Find OTM call spread (SELL 20-delta, BUY 10-delta)
    if 'delta' not in calls_df.columns:
        logger.warning(f"Jade Lizard: No delta column in calls dataframe")
        return None

    target_call_short_delta = 0.20
    calls_df_sorted = calls_df.copy()
    calls_df_sorted['delta_diff'] = abs(calls_df_sorted['delta'] - target_call_short_delta)
    best_call_short = calls_df_sorted.nsmallest(1, 'delta_diff')

    if best_call_short.empty:
        return None

    best_call_short = best_call_short.iloc[0]
    call_short_strike = float(best_call_short['strike'])
    call_short_premium = float(best_call_short.get('bid', 0) or best_call_short.get('lastPrice', 0))
    call_short_delta = float(best_call_short.get('delta', 0.20))
    call_short_iv = float(best_call_short.get('impliedVolatility', 0))
    if call_short_iv > 5:
        call_short_iv = call_short_iv / 100

    # Find long call (10-delta protection)
    target_call_long_delta = 0.10
    calls_df_sorted['delta_diff_long'] = abs(calls_df_sorted['delta'] - target_call_long_delta)
    calls_above = calls_df_sorted[calls_df_sorted['strike'] > call_short_strike]

    if calls_above.empty:
        logger.warning(f"Jade Lizard: No long call strikes found above short call")
        return None

    best_call_long = calls_above.nsmallest(1, 'delta_diff_long').iloc[0]
    call_long_strike = float(best_call_long['strike'])
    call_long_premium = float(best_call_long.get('ask', 0) or best_call_long.get('lastPrice', 0))
    call_long_delta = float(best_call_long.get('delta', 0.10))

    # 3. Calculate net credit and check Jade Lizard condition
    call_spread_width = call_long_strike - call_short_strike
    call_spread_credit = call_short_premium - call_long_premium
    total_credit = put_premium + call_spread_credit

    # Jade Lizard condition: Put premium >= Call spread width (NO upside risk)
    has_no_upside_risk = put_premium >= call_spread_width

    # 4. Calculate risk metrics
    # Max loss occurs on downside (put assignment)
    max_loss_put_side = (put_strike - (put_strike - total_credit)) * 100  # Effective put cost
    # Max loss on call side (if call spread breached)
    max_loss_call_side = (call_spread_width - total_credit) * 100

    # Overall max loss is worst case
    max_loss_per_contract = max(max_loss_put_side, max_loss_call_side)
    max_profit_per_contract = total_credit * 100

    # Position sizing
    max_risk_dollars = account_size * 0.02
    contracts = max(1, int(max_risk_dollars / max_loss_per_contract))

    # Aggregate Greeks
    put_theta = float(best_put.get('theta', 0))
    call_short_theta = float(best_call_short.get('theta', 0))
    call_long_theta = float(best_call_long.get('theta', 0))

    position_delta = (-put_delta - call_short_delta + call_long_delta) * contracts * 100
    position_theta = (-put_theta - call_short_theta + call_long_theta) * contracts * 100

    # Liquidity
    put_volume = best_put.get('volume', 0) or 0
    call_short_volume = best_call_short.get('volume', 0) or 0
    call_long_volume = best_call_long.get('volume', 0) or 0
    liquidity_score = min(10, (put_volume + call_short_volume + call_long_volume) / 30)

    # Breakevens
    breakeven_downside = put_strike - total_credit
    breakeven_upside = call_short_strike + call_spread_credit if has_no_upside_risk else call_short_strike + total_credit

    return {
        "strategy": "Jade Lizard",
        "dte": dte,
        "has_no_upside_risk": has_no_upside_risk,

        "legs": [
            {
                "action": "SELL",
                "option_type": "PUT",
                "strike": put_strike,
                "premium": put_premium,
                "delta": put_delta,
                "iv": round(put_iv * 100, 2),
                "theta": put_theta
            },
            {
                "action": "SELL",
                "option_type": "CALL",
                "strike": call_short_strike,
                "premium": call_short_premium,
                "delta": call_short_delta,
                "iv": round(call_short_iv * 100, 2),
                "theta": call_short_theta
            },
            {
                "action": "BUY",
                "option_type": "CALL",
                "strike": call_long_strike,
                "premium": call_long_premium,
                "delta": call_long_delta
            }
        ],

        "net_credit": round(total_credit, 2),
        "max_profit": round(max_profit_per_contract * contracts, 2),
        "max_loss": round(max_loss_per_contract * contracts, 2),
        "breakeven_downside": round(breakeven_downside, 2),
        "breakeven_upside": round(breakeven_upside, 2),
        "contracts": contracts,
        "buying_power_required": round(max_loss_per_contract * contracts, 2),

        "position_greeks": {
            "delta": round(position_delta, 2),
            "theta": round(position_theta, 2)
        },

        "call_spread_width": call_spread_width,
        "put_premium": put_premium,
        "liquidity_score": round(liquidity_score, 1),

        "jade_lizard_condition": {
            "put_premium": put_premium,
            "call_spread_width": call_spread_width,
            "condition_met": has_no_upside_risk,
            "message": f"✅ NO upside risk (Put premium ${put_premium:.2f} >= Call spread width ${call_spread_width:.2f})" if has_no_upside_risk else f"⚠️ Has upside risk (Put premium ${put_premium:.2f} < Call spread width ${call_spread_width:.2f})"
        }
    }


def _calculate_options_position_size(
    account_size: float,
    max_risk: float,
    spread_width: float = None,
    premium_received: float = None,
    is_defined_risk: bool = True,
    contracts_per_lot: int = 1
) -> dict:
    """
    Calculate position size using institutional methodology.

    Defined-risk: Position Size = (Account × 2-3%) / Max Loss per Contract
    Undefined-risk: Max 1-5% of buying power per trade

    Uses Half-Kelly for conservative sizing.

    Args:
        account_size: Total account value
        max_risk: Maximum risk per contract (spread width - premium for spreads)
        spread_width: Width of spread in dollars (for spreads)
        premium_received: Premium collected (for credit strategies)
        is_defined_risk: True for spreads, False for naked
        contracts_per_lot: Contracts per standard lot

    Returns:
        dict with contracts, total_risk, risk_pct
    """
    params = INSTITUTIONAL_OPTIONS_PARAMS

    if is_defined_risk:
        risk_pct = params['defined_risk_pct']
        max_position_risk = account_size * risk_pct

        if spread_width and premium_received:
            max_loss_per_contract = (spread_width - premium_received) * 100  # Per 100 shares
        elif max_risk:
            max_loss_per_contract = max_risk * 100
        else:
            max_loss_per_contract = 500  # Default $500 max loss

        if max_loss_per_contract > 0:
            contracts = int(max_position_risk / max_loss_per_contract)
        else:
            contracts = 1

    else:
        # Undefined risk - use buying power limit
        risk_pct = params['undefined_risk_pct']
        # For naked options, BP requirement is typically 20% of underlying
        # Use more conservative sizing
        contracts = max(1, int(account_size * risk_pct / 2000))  # Assume ~$2000 BP per contract

    # Apply Half-Kelly
    contracts = max(1, int(contracts * params['kelly_fraction']))

    # Calculate total risk
    total_risk = contracts * max_loss_per_contract if is_defined_risk else contracts * 2000
    risk_pct_actual = total_risk / account_size * 100

    return {
        "contracts": contracts,
        "total_risk": round(total_risk, 2),
        "risk_pct": round(risk_pct_actual, 2),
        "max_risk_per_contract": round(max_loss_per_contract if is_defined_risk else 2000, 2),
        "sizing_method": "Half-Kelly" if params['kelly_fraction'] == 0.5 else f"{params['kelly_fraction']*100:.0f}% Kelly",
        "is_defined_risk": is_defined_risk
    }


def _calculate_iv_analysis(ticker: str, calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """
    Calculate TRUE IV Rank/Percentile using actual options Implied Volatility.

    IV Rank = (Current IV - 52w Low IV) / (52w High IV - 52w Low IV) × 100
    IV Percentile = % of days where IV was LOWER than current IV

    Since we don't have historical IV data, we use HV (Historical Volatility) range
    as a proxy for IV range. This is valid because IV tends to mean-revert toward HV.
    """
    import numpy as np

    def calc_hv_metrics(returns, window):
        """Calculate HV metrics for a given rolling window."""
        hv_series = returns.rolling(window).std() * np.sqrt(252)
        hv_values = hv_series.dropna().values

        if len(hv_values) == 0:
            return None

        current_hv = hv_values[-1]
        hv_high = np.percentile(hv_values, 95)
        hv_low = np.percentile(hv_values, 5)

        return {
            "current": round(current_hv * 100, 1),
            "high_52w": round(hv_high * 100, 1),
            "low_52w": round(hv_low * 100, 1),
            "all_values": hv_values * 100  # Keep for percentile calc
        }

    # ========== STEP 1: Get ATM options IV (the ACTUAL implied volatility) ==========
    options_iv = None
    if not calls_df.empty:
        atm_calls = calls_df[abs(calls_df['strike'] - current_price) == abs(calls_df['strike'] - current_price).min()]
        atm_puts = puts_df[abs(puts_df['strike'] - current_price) == abs(puts_df['strike'] - current_price).min()] if not puts_df.empty else pd.DataFrame()

        if 'impliedVolatility' in atm_calls.columns and not atm_calls.empty:
            call_iv = atm_calls['impliedVolatility'].iloc[0] if not atm_calls['impliedVolatility'].isna().all() else None
            put_iv = atm_puts['impliedVolatility'].iloc[0] if not atm_puts.empty and 'impliedVolatility' in atm_puts.columns and not atm_puts['impliedVolatility'].isna().all() else None

            def normalize_to_decimal(iv_val):
                if iv_val is None or pd.isna(iv_val):
                    return None
                iv_val = float(iv_val)
                if iv_val > 5.0:  # Likely percentage form (e.g., 43.7 instead of 0.437)
                    return iv_val / 100
                return iv_val

            call_iv = normalize_to_decimal(call_iv)
            put_iv = normalize_to_decimal(put_iv)

            if call_iv and put_iv:
                options_iv = (call_iv + put_iv) / 2
            elif call_iv:
                options_iv = call_iv
            elif put_iv:
                options_iv = put_iv

    # ========== STEP 2: Calculate HV metrics for reference ==========
    hv_20 = None
    hv_values_for_percentile = None

    try:
        from .scanning import _get_ohlcv_cached
        hist = _get_ohlcv_cached(ticker, period="1y")
        if hist is not None and not hist.empty and len(hist) >= 40:
            returns = np.log(hist['Close'] / hist['Close'].shift(1)).dropna()
            hv_20 = calc_hv_metrics(returns, 20)
            if hv_20:
                hv_values_for_percentile = hv_20.pop("all_values")
    except Exception:
        pass

    # ========== STEP 3: Calculate TRUE IV Rank using Options IV ==========
    # Use options IV as current, compare to HV range (proxy for IV range)
    if options_iv and hv_20:
        current_iv = options_iv * 100  # Convert to percentage
        iv_high = hv_20["high_52w"]
        iv_low = hv_20["low_52w"]

        # IV Rank formula: (Current - Low) / (High - Low) * 100
        iv_range = iv_high - iv_low
        if iv_range > 0:
            iv_rank = ((current_iv - iv_low) / iv_range) * 100
            iv_rank = max(0, min(100, iv_rank))  # Clamp to 0-100
        else:
            iv_rank = 50

        # IV Percentile: % of HV values below current IV
        if hv_values_for_percentile is not None and len(hv_values_for_percentile) > 0:
            iv_percentile = (hv_values_for_percentile < current_iv).sum() / len(hv_values_for_percentile) * 100
            iv_percentile = max(0, min(100, iv_percentile))
        else:
            iv_percentile = iv_rank  # Fallback to rank

    elif hv_20:
        # Fallback: No options IV available, use HV-20
        current_iv = hv_20["current"]
        iv_high = hv_20["high_52w"]
        iv_low = hv_20["low_52w"]

        iv_range = iv_high - iv_low
        if iv_range > 0:
            iv_rank = ((current_iv - iv_low) / iv_range) * 100
            iv_rank = max(0, min(100, iv_rank))
        else:
            iv_rank = 50

        if hv_values_for_percentile is not None and len(hv_values_for_percentile) > 0:
            iv_percentile = (hv_values_for_percentile < current_iv).sum() / len(hv_values_for_percentile) * 100
        else:
            iv_percentile = iv_rank
    else:
        # No data at all
        current_iv = 30.0
        iv_high = 50.0
        iv_low = 20.0
        iv_rank = 50.0
        iv_percentile = 50.0

    # ========== STEP 4: Determine IV Environment ==========
    if iv_rank >= 50:
        iv_environment = "HIGH_IV"
        iv_interpretation = "IV is elevated vs historical range - favor SELLING premium (credit spreads, iron condors)"
    elif iv_rank <= 30:
        iv_environment = "LOW_IV"
        iv_interpretation = "IV is low vs historical range - favor BUYING premium (long calls/puts, debit spreads)"
    else:
        iv_environment = "NORMAL_IV"
        iv_interpretation = "IV is normal - flexible strategy selection"

    return {
        "current_iv": round(current_iv, 1),
        "iv_rank": round(iv_rank, 1),
        "iv_percentile": round(iv_percentile, 1),
        "iv_52w_high": round(iv_high, 1),
        "iv_52w_low": round(iv_low, 1),
        "iv_environment": iv_environment,
        "interpretation": iv_interpretation,
        "hv_20_current": hv_20["current"] if hv_20 else None,
        "options_iv": round(options_iv * 100, 1) if options_iv else None,
        "iv_premium": round(current_iv - hv_20["current"], 1) if options_iv and hv_20 else None,
        "methodology": "TRUE IV Rank (compares current options IV to 52-week HV range)",
        "mcmillan_reference": "Chapter 28: Volatility Trading"
    }


def _calculate_pc_ratio(calls_df: pd.DataFrame, puts_df: pd.DataFrame) -> dict:
    """Calculate Put/Call ratio analysis per McMillan methodology."""
    # Volume-based P/C ratio
    call_volume = calls_df['volume'].sum() if 'volume' in calls_df.columns else 0
    put_volume = puts_df['volume'].sum() if 'volume' in puts_df.columns else 0

    # FIX: Handle division by zero properly
    # - call_vol=0, put_vol>0 = EXTREMELY BEARISH (use 99.0 to represent infinity)
    # - call_vol=0, put_vol=0 = NO DATA (use None)
    # - otherwise = normal calculation
    if call_volume == 0 and put_volume == 0:
        volume_pc_ratio = None  # No data
    elif call_volume == 0 and put_volume > 0:
        volume_pc_ratio = 99.0  # Infinite P/C = extremely bearish (all puts, no calls)
    else:
        volume_pc_ratio = put_volume / call_volume

    # Open Interest-based P/C ratio (same logic)
    call_oi = calls_df['openInterest'].sum() if 'openInterest' in calls_df.columns else 0
    put_oi = puts_df['openInterest'].sum() if 'openInterest' in puts_df.columns else 0

    if call_oi == 0 and put_oi == 0:
        oi_pc_ratio = None
    elif call_oi == 0 and put_oi > 0:
        oi_pc_ratio = 99.0
    else:
        oi_pc_ratio = put_oi / call_oi

    # McMillan interpretation (contrarian indicator)
    # High P/C = Bearish sentiment = Contrarian Bullish
    # Low P/C = Bullish sentiment = Contrarian Bearish
    # NEW: trading_signal shows the ACTIONABLE signal (what to do)
    # raw_sentiment shows what options market is saying (crowd behavior)
    if volume_pc_ratio is None:
        raw_sentiment = "NO_DATA"
        trading_signal = "NEUTRAL"
        contrarian_signal = "NEUTRAL"
        interpretation = "No options volume data available"
    elif volume_pc_ratio >= 99.0:
        # All puts, no calls = extreme bearish sentiment
        raw_sentiment = "ALL_PUTS_NO_CALLS"
        trading_signal = "CONTRARIAN_BULLISH"  # What to DO
        contrarian_signal = "BULLISH"
        interpretation = f"All puts ({put_volume}), zero calls - EXTREME fear → contrarian BULLISH"
    elif volume_pc_ratio > 1.2:
        raw_sentiment = "EXTREMELY_BEARISH"
        trading_signal = "CONTRARIAN_BULLISH"
        contrarian_signal = "BULLISH"
        interpretation = "Extreme put buying = fear → contrarian BULLISH signal"
    elif volume_pc_ratio > 0.9:
        raw_sentiment = "BEARISH"
        trading_signal = "SLIGHTLY_BULLISH"
        contrarian_signal = "SLIGHTLY_BULLISH"
        interpretation = "Elevated puts = moderate fear → mild contrarian bullish"
    elif volume_pc_ratio < 0.5:
        raw_sentiment = "EXTREMELY_BULLISH"
        trading_signal = "CONTRARIAN_BEARISH"  # What to DO (clear!)
        contrarian_signal = "BEARISH"
        interpretation = "Extreme call buying = greed → contrarian BEARISH signal"
    elif volume_pc_ratio < 0.7:
        raw_sentiment = "BULLISH"
        trading_signal = "SLIGHTLY_BEARISH"
        contrarian_signal = "SLIGHTLY_BEARISH"
        interpretation = "Elevated calls = moderate greed → mild contrarian bearish"
    else:
        raw_sentiment = "NEUTRAL"
        trading_signal = "NEUTRAL"
        contrarian_signal = "NEUTRAL"
        interpretation = "P/C ratio in neutral zone - no strong signal"

    return {
        "volume_pc_ratio": round(volume_pc_ratio, 3) if volume_pc_ratio is not None else None,
        "oi_pc_ratio": round(oi_pc_ratio, 3) if oi_pc_ratio is not None else None,
        "call_volume": int(call_volume),
        "put_volume": int(put_volume),
        "call_oi": int(call_oi),
        "put_oi": int(put_oi),
        "raw_sentiment": raw_sentiment,  # What the crowd is doing
        "trading_signal": trading_signal,  # What to DO (actionable)
        "sentiment": raw_sentiment,  # Keep for backward compatibility
        "contrarian_signal": contrarian_signal,
        "interpretation": interpretation,
        "mcmillan_reference": "Chapter 24: Stock Option Strategies"
    }


def _calculate_oi_analysis(calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """Analyze Open Interest for max pain and positioning."""
    import numpy as np

    # Find max pain (strike where options sellers profit most)
    all_strikes = sorted(set(calls_df['strike'].tolist() + puts_df['strike'].tolist()))

    max_pain_strike = current_price
    min_pain_value = float('inf')

    for strike in all_strikes:
        # Calculate pain at this strike
        call_pain = 0
        put_pain = 0

        # Call pain: sum of (strike - exercise_strike) * OI for all ITM calls
        itm_calls = calls_df[calls_df['strike'] < strike]
        if not itm_calls.empty and 'openInterest' in itm_calls.columns:
            call_pain = ((strike - itm_calls['strike']) * itm_calls['openInterest']).sum()

        # Put pain: sum of (exercise_strike - strike) * OI for all ITM puts
        itm_puts = puts_df[puts_df['strike'] > strike]
        if not itm_puts.empty and 'openInterest' in itm_puts.columns:
            put_pain = ((itm_puts['strike'] - strike) * itm_puts['openInterest']).sum()

        total_pain = call_pain + put_pain
        if total_pain < min_pain_value:
            min_pain_value = total_pain
            max_pain_strike = strike

    # Find highest OI strikes (important levels)
    top_call_strikes = calls_df.nlargest(3, 'openInterest')[['strike', 'openInterest']].to_dict('records') if 'openInterest' in calls_df.columns else []
    top_put_strikes = puts_df.nlargest(3, 'openInterest')[['strike', 'openInterest']].to_dict('records') if 'openInterest' in puts_df.columns else []

    # Max pain interpretation
    distance_to_max_pain = (max_pain_strike - current_price) / current_price * 100
    if abs(distance_to_max_pain) < 2:
        oi_bias = "NEUTRAL"
        interpretation = "Price near max pain - likely to stay range-bound into expiration"
    elif distance_to_max_pain > 2:
        oi_bias = "BULLISH"
        interpretation = f"Max pain {distance_to_max_pain:.1f}% above price - gravitational pull higher"
    else:
        oi_bias = "BEARISH"
        interpretation = f"Max pain {abs(distance_to_max_pain):.1f}% below price - gravitational pull lower"

    # Outlier detection: flag when max pain is >20% from current price
    is_outlier = abs(distance_to_max_pain) > 20
    outlier_warning = None
    if is_outlier:
        outlier_warning = f"Max pain {abs(distance_to_max_pain):.1f}% from price is unusual (>20%) - positioning may be stale, manipulated, or reflect unusual market conditions"
        interpretation += f" ⚠️ UNUSUAL: {outlier_warning}"

    return {
        "max_pain_strike": max_pain_strike,
        "distance_to_max_pain_pct": round(distance_to_max_pain, 2),
        "top_call_oi_strikes": top_call_strikes,
        "top_put_oi_strikes": top_put_strikes,
        "oi_bias": oi_bias,
        "interpretation": interpretation,
        "is_outlier": is_outlier,  # NEW: Flag for unusual max pain distance
        "outlier_warning": outlier_warning,  # NEW: Warning message if outlier
        "mcmillan_reference": "Chapter 25: Index Option Strategies"
    }


def _detect_unusual_activity(calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """Detect unusual options activity (smart money signals)."""
    unusual_trades = []

    # Check for volume > OI (indicates new positions)
    for df, opt_type in [(calls_df, 'CALL'), (puts_df, 'PUT')]:
        if 'volume' in df.columns and 'openInterest' in df.columns:
            # Unusual: Volume > 2x OI
            unusual = df[(df['volume'] > df['openInterest'] * 2) & (df['volume'] > 100)]
            for _, row in unusual.iterrows():
                unusual_trades.append({
                    'type': opt_type,
                    'strike': row['strike'],
                    'volume': int(row['volume']),
                    'oi': int(row['openInterest']),
                    'volume_oi_ratio': round(row['volume'] / max(row['openInterest'], 1), 1),
                    'moneyness': 'ITM' if (opt_type == 'CALL' and row['strike'] < current_price) or
                                          (opt_type == 'PUT' and row['strike'] > current_price) else 'OTM'
                })

    # Sort by volume/OI ratio
    unusual_trades.sort(key=lambda x: x['volume_oi_ratio'], reverse=True)
    unusual_trades = unusual_trades[:5]  # Top 5

    # Determine smart money signal
    if not unusual_trades:
        smart_money_signal = "NO_SIGNAL"
        interpretation = "No unusual options activity detected"
    else:
        call_unusual = sum(1 for t in unusual_trades if t['type'] == 'CALL')
        put_unusual = sum(1 for t in unusual_trades if t['type'] == 'PUT')

        if call_unusual > put_unusual * 2:
            smart_money_signal = "BULLISH"
            interpretation = f"Unusual call activity ({call_unusual} trades) suggests smart money bullish positioning"
        elif put_unusual > call_unusual * 2:
            smart_money_signal = "BEARISH"
            interpretation = f"Unusual put activity ({put_unusual} trades) suggests smart money bearish positioning"
        else:
            smart_money_signal = "MIXED"
            interpretation = f"Mixed unusual activity ({call_unusual} calls, {put_unusual} puts)"

    return {
        "unusual_trades": unusual_trades,
        "unusual_trade_count": len(unusual_trades),
        "smart_money_signal": smart_money_signal,
        "interpretation": interpretation,
        "mcmillan_reference": "Chapter 36: Portfolio Management"
    }


def _get_questrade_greeks(ticker: str, expiration: str, current_price: float) -> dict | None:
    """Get Greeks from Questrade API for more accurate data."""
    from questrade_api import Questrade

    try:
        client = get_questrade_client()
        options_chain = client.get_options_chain(ticker)

        if not options_chain or 'optionChain' not in options_chain:
            return None

        # Get raw Questrade client for option quotes
        q = client._get_client()

        # Find the matching expiration
        target_exp = None
        for exp in options_chain.get('optionChain', []):
            exp_date = exp.get('expiryDate', '')[:10]  # Get YYYY-MM-DD
            if expiration in exp_date or exp_date in expiration:
                target_exp = exp
                break

        # If no exact match, use first non-expired expiration
        if not target_exp and options_chain.get('optionChain'):
            target_exp = options_chain['optionChain'][0]

        if not target_exp:
            return None

        # Find ATM strike and get Greeks
        atm_call_id = None
        atm_put_id = None
        atm_strike = None
        min_distance = float('inf')

        for root in target_exp.get('chainPerRoot', []):
            for strike_info in root.get('chainPerStrikePrice', []):
                strike = strike_info['strikePrice']
                distance = abs(strike - current_price)
                if distance < min_distance:
                    min_distance = distance
                    atm_strike = strike
                    atm_call_id = strike_info.get('callSymbolId')
                    atm_put_id = strike_info.get('putSymbolId')

        if not atm_call_id and not atm_put_id:
            return None

        greeks = {
            "source": "questrade",
            "note": "Real-time Greeks from Questrade API"
        }

        # Fetch ATM call Greeks
        if atm_call_id:
            try:
                call_quotes = q.markets_options(optionIds=[atm_call_id])
                if call_quotes and call_quotes.get('optionQuotes'):
                    cq = call_quotes['optionQuotes'][0]
                    greeks["atm_call_delta"] = round(cq.get('delta') or 0, 4)
                    greeks["atm_call_gamma"] = round(cq.get('gamma') or 0, 6)
                    greeks["atm_call_theta"] = round(cq.get('theta') or 0, 4)
                    greeks["atm_call_vega"] = round(cq.get('vega') or 0, 4)
                    greeks["atm_call_impliedVolatility"] = round((cq.get('volatility') or 30) / 100, 4)
            except Exception as e:
                logger.warning(f"Failed to get call Greeks: {e}")

        # Fetch ATM put Greeks
        if atm_put_id:
            try:
                put_quotes = q.markets_options(optionIds=[atm_put_id])
                if put_quotes and put_quotes.get('optionQuotes'):
                    pq = put_quotes['optionQuotes'][0]
                    greeks["atm_put_delta"] = round(pq.get('delta') or 0, 4)
                    greeks["atm_put_gamma"] = round(pq.get('gamma') or 0, 6)
                    greeks["atm_put_theta"] = round(pq.get('theta') or 0, 4)
                    greeks["atm_put_vega"] = round(pq.get('vega') or 0, 4)
                    greeks["atm_put_impliedVolatility"] = round((pq.get('volatility') or 30) / 100, 4)
            except Exception as e:
                logger.warning(f"Failed to get put Greeks: {e}")

        # Add interpretation
        if greeks.get("atm_call_delta"):
            greeks["interpretation"] = {
                "delta_exposure": f"Call: +{greeks['atm_call_delta']:.2f} = {abs(greeks['atm_call_delta'])*100:.0f}% ITM probability",
                "gamma_risk": "HIGH - near ATM, delta can change rapidly" if abs(greeks.get('atm_call_gamma', 0)) > 0.03 else "MODERATE - stable delta",
                "theta_burn": f"${abs(greeks.get('atm_call_theta', 0)):.2f}/day decay",
                "vega_sensitivity": f"${abs(greeks.get('atm_call_vega', 0)):.2f} per 1% IV change"
            }

        return greeks if greeks.get("atm_call_delta") or greeks.get("atm_put_delta") else None

    except Exception as e:
        logger.warning(f"Questrade Greeks unavailable: {e}")
        return None


def _calculate_black_scholes_greeks(
    S: float,  # Current stock price
    K: float,  # Strike price
    T: float,  # Time to expiration in years
    r: float,  # Risk-free rate (annual)
    sigma: float,  # Implied volatility (annual)
    option_type: str = "call"  # "call" or "put"
) -> dict:
    """
    Calculate option Greeks using Black-Scholes model.

    Reference: Hull, J.C. "Options, Futures, and Other Derivatives"

    Returns:
        dict with delta, gamma, theta (daily), vega (per 1% IV change)
    """
    import numpy as np
    from scipy.stats import norm

    # Handle edge cases
    if T <= 0 or sigma <= 0:
        return {"delta": 0.5 if option_type == "call" else -0.5,
                "gamma": 0, "theta": 0, "vega": 0}

    # Calculate d1 and d2
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    # Standard normal CDF and PDF
    N_d1 = norm.cdf(d1)
    N_d2 = norm.cdf(d2)
    n_d1 = norm.pdf(d1)  # Standard normal PDF

    # Greeks calculation
    if option_type == "call":
        delta = N_d1
        theta = (-(S * sigma * n_d1) / (2 * sqrt_T)
                 - r * K * np.exp(-r * T) * N_d2)
    else:  # put
        delta = N_d1 - 1
        theta = (-(S * sigma * n_d1) / (2 * sqrt_T)
                 + r * K * np.exp(-r * T) * norm.cdf(-d2))

    # Gamma and Vega are same for calls and puts
    gamma = n_d1 / (S * sigma * sqrt_T)
    vega = S * sqrt_T * n_d1 / 100  # Per 1% IV change

    # Convert theta to daily (divide by 365)
    theta_daily = theta / 365

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta_daily, 4),  # Daily theta
        "vega": round(vega, 4)  # Per 1% IV change
    }


def _calculate_vanna(
    S: float,  # Current stock price
    K: float,  # Strike price
    T: float,  # Time to expiration in years
    r: float,  # Risk-free rate (annual)
    sigma: float,  # Implied volatility (annual)
    option_type: str = "call"  # "call" or "put"
) -> float:
    """
    Calculate Vanna (∂Delta/∂IV) - sensitivity of delta to IV changes.

    Vanna measures how much delta changes when implied volatility changes by 1 point.
    Critical for earnings and event trading where IV changes dramatically.

    **Formula:**
    Vanna = -φ(d1) * (d2 / σ)

    where:
    - φ(d1) = standard normal PDF of d1
    - d2 = d1 - σ√T

    **Interpretation:**
    - Long options have NEGATIVE vanna (delta decreases when IV drops)
    - Short options have POSITIVE vanna (delta increases when IV drops)
    - Highest for ATM options
    - Critical for IV crush scenarios (earnings)

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate
        sigma: Implied volatility (decimal)
        option_type: 'call' or 'put' (vanna is same for both)

    Returns:
        Vanna value (change in delta per 1 point IV change)

    Reference: Taleb - "Dynamic Hedging", Chapter 9: Second-Order Greeks
    """
    import numpy as np
    from scipy.stats import norm

    if T <= 0 or sigma <= 0:
        return 0.0

    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    # Standard normal PDF
    phi_d1 = norm.pdf(d1)

    # Vanna formula (same for calls and puts)
    vanna = -phi_d1 * (d2 / sigma)

    return round(vanna, 6)


def _calculate_charm(
    S: float,  # Current stock price
    K: float,  # Strike price
    T: float,  # Time to expiration in years
    r: float,  # Risk-free rate (annual)
    sigma: float,  # Implied volatility (annual)
    option_type: str = "call"  # "call" or "put"
) -> float:
    """
    Calculate Charm (∂Delta/∂Time) - delta decay over time.

    Charm measures how much delta changes as time passes (delta bleed).
    Critical for understanding Friday EOD flows and 0DTE positioning.

    **Formula:**
    Charm = -φ(d1) * ((2(r)T - d2*σ*√T) / (2T*σ*√T))

    **Interpretation:**
    - ATM options have highest charm (delta decays fastest)
    - Explains Friday EOD "pin" to strikes with max OI
    - Dealer rehedging flows create predictable moves
    - Peaks near expiration

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate
        sigma: Implied volatility (decimal)
        option_type: 'call' or 'put'

    Returns:
        Charm value (daily delta decay)

    Reference: Hull - "Options, Futures, and Other Derivatives", Chapter 19
    """
    import numpy as np
    from scipy.stats import norm

    if T <= 0.001 or sigma <= 0:  # Near expiration
        return 0.0

    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    phi_d1 = norm.pdf(d1)

    # Charm formula
    charm = -phi_d1 * ((2 * r * T - d2 * sigma * sqrt_T) / (2 * T * sigma * sqrt_T))

    # Convert to daily (divide by 365)
    charm_daily = charm / 365

    return round(charm_daily, 6)



def _estimate_greeks_from_chain(calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """
    Estimate Greeks from yfinance chain data.

    If Greeks are not in the chain, calculates them using Black-Scholes model.
    Uses the ATM (At-The-Money) options for analysis.
    """
    import numpy as np
    from datetime import datetime

    greeks = {
        "source": "calculated_black_scholes",
        "note": "Greeks calculated using Black-Scholes model from IV and time to expiry"
    }

    try:
        # Get ATM options (closest strike to current price)
        if calls_df.empty or puts_df.empty:
            return {"source": "unavailable", "note": "No options data available"}

        atm_calls = calls_df.loc[calls_df['strike'].sub(current_price).abs().idxmin():calls_df['strike'].sub(current_price).abs().idxmin()]
        atm_puts = puts_df.loc[puts_df['strike'].sub(current_price).abs().idxmin():puts_df['strike'].sub(current_price).abs().idxmin()]

        if atm_calls.empty or atm_puts.empty:
            return {"source": "unavailable", "note": "Could not find ATM options"}

        # Get ATM strike and IV
        atm_call = atm_calls.iloc[0]
        atm_put = atm_puts.iloc[0]

        strike = atm_call['strike']
        call_iv = atm_call.get('impliedVolatility', 0.3)  # Default to 30% IV
        put_iv = atm_put.get('impliedVolatility', 0.3)

        # Handle NaN IV values and suspiciously low IVs
        # yfinance sometimes returns IV as decimal (0.30) but sometimes as percentage (30)
        # If IV < 0.05 (5%), it's likely in decimal form and we should use a default
        # If IV > 1.5 (150%), it's likely a data error
        def normalize_iv(iv_value, default=0.3):
            if pd.isna(iv_value) or iv_value is None or iv_value <= 0:
                return default
            if iv_value < 0.05:  # Less than 5% - likely bad data or needs conversion
                return default
            if iv_value > 1.5:  # More than 150% - likely bad data
                return default
            return float(iv_value)

        call_iv = normalize_iv(call_iv)
        put_iv = normalize_iv(put_iv)

        # Calculate time to expiration
        # Try to get expiration from dataframe index or assume 30 days
        T = 30 / 365  # Default: 30 days

        # Check if 'lastTradeDate' column exists to estimate time
        if 'lastTradeDate' in calls_df.columns:
            try:
                # Get contract name which often contains expiry
                contract = atm_call.get('contractSymbol', '')
                if contract:
                    # Extract date from contract symbol (format varies)
                    pass  # Use default T if we can't parse
            except Exception:
                pass

        # Risk-free rate (approximate from current Fed funds rate)
        r = 0.045  # 4.5% annual risk-free rate

        # First check if yfinance already provides Greeks
        greek_cols = ['delta', 'gamma', 'theta', 'vega']
        have_chain_greeks = all(col in atm_call.index and pd.notna(atm_call.get(col)) for col in greek_cols)

        # Helper to safely extract Greek value
        def safe_greek(row, col, default=0.0):
            val = row.get(col)
            if pd.isna(val) or val is None or val == 0:
                return None  # Return None to indicate need for calculation
            return float(val)

        # Check if we have valid chain Greeks (not NaN or zero)
        call_greeks_valid = all(safe_greek(atm_call, col) is not None for col in greek_cols)
        put_greeks_valid = all(safe_greek(atm_put, col) is not None for col in greek_cols)

        if have_chain_greeks and call_greeks_valid:
            # Use chain Greeks for calls if valid
            greeks["source"] = "yfinance_chain"
            greeks["atm_call_delta"] = round(float(atm_call['delta']), 4)
            greeks["atm_call_gamma"] = round(float(atm_call['gamma']), 6)
            greeks["atm_call_theta"] = round(float(atm_call['theta']), 4)
            greeks["atm_call_vega"] = round(float(atm_call['vega']), 4)
        else:
            # Calculate call Greeks using Black-Scholes
            call_bs = _calculate_black_scholes_greeks(
                S=current_price, K=strike, T=T, r=r, sigma=call_iv, option_type="call"
            )
            greeks["source"] = "calculated_black_scholes"
            greeks["atm_call_delta"] = call_bs["delta"]
            greeks["atm_call_gamma"] = call_bs["gamma"]
            greeks["atm_call_theta"] = call_bs["theta"]
            greeks["atm_call_vega"] = call_bs["vega"]

        if have_chain_greeks and put_greeks_valid:
            # Use chain Greeks for puts if valid
            greeks["atm_put_delta"] = round(float(atm_put['delta']), 4)
            greeks["atm_put_gamma"] = round(float(atm_put['gamma']), 6)
            greeks["atm_put_theta"] = round(float(atm_put['theta']), 4)
            greeks["atm_put_vega"] = round(float(atm_put['vega']), 4)
        else:
            # Calculate put Greeks using Black-Scholes (common case - yfinance often has 0 for puts)
            put_bs = _calculate_black_scholes_greeks(
                S=current_price, K=strike, T=T, r=r, sigma=put_iv, option_type="put"
            )
            greeks["atm_put_delta"] = put_bs["delta"]
            greeks["atm_put_gamma"] = put_bs["gamma"]
            greeks["atm_put_theta"] = put_bs["theta"]
            greeks["atm_put_vega"] = put_bs["vega"]
            if "source" not in greeks or greeks["source"] == "yfinance_chain":
                greeks["source"] = "mixed_chain_and_calculated"

        # Add IV for reference
        greeks["atm_call_impliedVolatility"] = round(float(call_iv), 4)
        greeks["atm_put_impliedVolatility"] = round(float(put_iv), 4)

        # Add interpretation
        greeks["interpretation"] = {
            "delta_exposure": f"Call: {greeks['atm_call_delta']:+.2f} = {abs(greeks['atm_call_delta'])*100:.0f}% ITM probability",
            "gamma_risk": "HIGH - near ATM, delta can change rapidly" if abs(greeks.get('atm_call_gamma', 0)) > 0.05 else "MODERATE - stable delta",
            "theta_burn": f"${abs(greeks.get('atm_call_theta', 0)):.2f}/day decay" if greeks.get('atm_call_theta') else "N/A",
            "vega_sensitivity": f"${abs(greeks.get('atm_call_vega', 0)):.2f} per 1% IV change"
        }

    except Exception as e:
        logger.warning(f"Error calculating Greeks: {e}")
        greeks = {
            "source": "error",
            "note": f"Could not calculate Greeks: {str(e)}"
        }

    return greeks


def _get_iv_based_strategies(
    iv_rank: float,
    current_price: float,
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame
) -> dict:
    """
    Get IV-based strategy suggestions (direction-independent).

    HIGH IV (>50): Favor selling premium - credit spreads, iron condors, strangles
    LOW IV (<30): Favor buying premium - long calls/puts, debit spreads, LEAPS
    NORMAL IV: Flexible - can use either approach
    """
    # Find ATM strike (convert to float to avoid numpy.int64 serialization issues)
    if not calls_df.empty:
        atm_strike = float(calls_df.iloc[(calls_df['strike'] - current_price).abs().argsort()[:1]]['strike'].values[0])
    else:
        atm_strike = float(round(current_price / 5) * 5)  # Round to nearest $5

    # Define strategies by IV environment
    high_iv_strategies = [
        "Iron Condor (sell OTM call spread + put spread)",
        "Credit Spread (bull put or bear call)",
        "Short Strangle (sell OTM call + put)",
        "Covered Call (if holding shares)",
        "Cash-Secured Put (for stock you want to own)"
    ]

    low_iv_strategies = [
        "Long Call or Put (directional bet)",
        "Debit Spread (bull call or bear put)",
        "LEAPS (long-dated options)",
        "Calendar Spread (sell near, buy far)",
        "Straddle (if expecting big move)"
    ]

    neutral_strategies = [
        "Iron Butterfly (ATM short straddle + wings)",
        "Calendar Spread",
        "Diagonal Spread",
        "Ratio Spread"
    ]

    # Suggested strikes
    suggested_strikes = {
        "atm": atm_strike,
        "otm_call": atm_strike + 5,
        "otm_put": atm_strike - 5,
        "deep_otm_call": atm_strike + 10,
        "deep_otm_put": atm_strike - 10
    }

    return {
        "high_iv_strategies": high_iv_strategies,
        "low_iv_strategies": low_iv_strategies,
        "neutral_strategies": neutral_strategies,
        "suggested_strikes": suggested_strikes,
        "recommendation": f"IV Rank {iv_rank:.0f}% - {'SELL premium' if iv_rank >= 50 else 'BUY premium' if iv_rank <= 30 else 'Flexible'}",
        "mcmillan_reference": "Chapter 1-10: Basic Option Strategies"
    }


def _calculate_options_quality_score(
    iv_analysis: dict,
    pc_ratio_analysis: dict,
    oi_analysis: dict,
    uoa_analysis: dict
) -> dict:
    """
    Calculate direction-independent options quality score.

    Measures how favorable options conditions are for ANY trade:
    - IV environment clarity (extreme = better for strategy selection)
    - Liquidity (open interest)
    - Unusual activity (smart money signals)
    """
    score = 50  # Base score
    factors = []

    # IV Clarity (extreme IV = clearer strategy choice)
    iv_rank = iv_analysis.get('iv_rank', 50)
    if iv_rank >= 70 or iv_rank <= 30:
        score += 15
        factors.append(f"Clear IV signal ({iv_rank:.0f}%): +15")
    elif iv_rank >= 60 or iv_rank <= 40:
        score += 5
        factors.append(f"Moderate IV signal ({iv_rank:.0f}%): +5")

    # P/C Ratio extremes (contrarian signals)
    sentiment = pc_ratio_analysis.get('sentiment', 'NEUTRAL')
    if 'EXTREMELY' in sentiment:
        score += 10
        factors.append(f"Extreme sentiment ({sentiment}): +10")
    elif sentiment not in ['NEUTRAL', 'BALANCED']:
        score += 5
        factors.append(f"Sentiment signal ({sentiment}): +5")

    # Unusual activity (smart money)
    smart_money = uoa_analysis.get('smart_money_signal', 'NO_SIGNAL')
    if smart_money != 'NO_SIGNAL':
        score += 15
        factors.append(f"Smart money signal ({smart_money}): +15")

    # Open interest / liquidity
    total_oi = oi_analysis.get('top_call_oi_strikes', [{}])[0].get('openInterest', 0)
    if total_oi > 5000:
        score += 10
        factors.append(f"High liquidity (OI {total_oi}): +10")
    elif total_oi > 1000:
        score += 5
        factors.append(f"Moderate liquidity (OI {total_oi}): +5")

    # Determine confidence
    if score >= 80:
        confidence = "HIGH"
    elif score >= 60:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "score": min(100, score),
        "confidence": confidence,
        "factors": factors,
        "interpretation": f"Options environment is {confidence.lower()} quality for trading"
    }


def _select_mcmillan_strategy(
    direction: str,
    iv_rank: float,
    iv_percentile: float,
    current_price: float,
    holding_period_days: int,
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame
) -> dict:
    """Select optimal strategy using McMillan's Strategy Selection Matrix (LEGACY - kept for compatibility)."""

    # McMillan Strategy Selection Matrix
    # Based on IV environment + Directional bias

    strategies = []

    # HIGH IV (>70) - Favor selling premium
    if iv_rank >= 70:
        if direction == "LONG":
            strategies = [
                {"name": "Short Put", "type": "credit", "risk": "moderate", "max_profit": "premium", "max_loss": "strike - premium"},
                {"name": "Bull Put Spread", "type": "credit", "risk": "defined", "max_profit": "net credit", "max_loss": "spread width - credit"},
                {"name": "Covered Call", "type": "income", "risk": "stock ownership", "max_profit": "premium + (strike - stock price)", "max_loss": "stock price - premium"}
            ]
            primary = "Bull Put Spread (Credit)"
            rationale = "High IV favors selling premium. Bull put spread defines risk while collecting elevated premium."

        elif direction == "SHORT":
            strategies = [
                {"name": "Short Call", "type": "credit", "risk": "unlimited", "max_profit": "premium", "max_loss": "unlimited"},
                {"name": "Bear Call Spread", "type": "credit", "risk": "defined", "max_profit": "net credit", "max_loss": "spread width - credit"},
                {"name": "Protective Put + Short Stock", "type": "hedged", "risk": "defined", "max_profit": "stock decline - premium", "max_loss": "premium"}
            ]
            primary = "Bear Call Spread (Credit)"
            rationale = "High IV favors selling premium. Bear call spread defines risk while collecting elevated premium."

        else:  # NEUTRAL
            strategies = [
                {"name": "Iron Condor", "type": "credit", "risk": "defined", "max_profit": "net credit", "max_loss": "wing width - credit"},
                {"name": "Short Strangle", "type": "credit", "risk": "undefined", "max_profit": "premium", "max_loss": "unlimited"},
                {"name": "Short Straddle", "type": "credit", "risk": "undefined", "max_profit": "premium", "max_loss": "unlimited"}
            ]
            primary = "Iron Condor"
            rationale = "High IV + neutral outlook ideal for iron condor. Collect premium from both sides with defined risk."

    # LOW IV (<30) - Favor buying premium
    elif iv_rank <= 30:
        if direction == "LONG":
            strategies = [
                {"name": "Long Call", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"},
                {"name": "Bull Call Spread", "type": "debit", "risk": "defined", "max_profit": "spread width - debit", "max_loss": "net debit"},
                {"name": "LEAPS Call", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"}
            ]
            primary = "Long Call or Bull Call Spread"
            rationale = "Low IV makes buying options cheap. Long calls for conviction, spreads for cost reduction."

        elif direction == "SHORT":
            strategies = [
                {"name": "Long Put", "type": "debit", "risk": "defined", "max_profit": "strike - premium", "max_loss": "premium"},
                {"name": "Bear Put Spread", "type": "debit", "risk": "defined", "max_profit": "spread width - debit", "max_loss": "net debit"},
                {"name": "Put Backspread", "type": "debit/credit", "risk": "defined upside", "max_profit": "large on big move", "max_loss": "limited"}
            ]
            primary = "Long Put or Bear Put Spread"
            rationale = "Low IV makes buying options cheap. Long puts for conviction, spreads for cost reduction."

        else:  # NEUTRAL
            strategies = [
                {"name": "Long Straddle", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"},
                {"name": "Long Strangle", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"},
                {"name": "Calendar Spread", "type": "debit", "risk": "defined", "max_profit": "front month decay", "max_loss": "net debit"}
            ]
            primary = "Long Straddle or Calendar Spread"
            rationale = "Low IV with neutral outlook suggests volatility expansion expected. Long vol strategies benefit."

    # NORMAL IV (30-70) - Flexible
    else:
        if direction == "LONG":
            strategies = [
                {"name": "Bull Call Spread", "type": "debit", "risk": "defined", "max_profit": "spread width - debit", "max_loss": "net debit"},
                {"name": "Call Diagonal", "type": "debit", "risk": "defined", "max_profit": "variable", "max_loss": "net debit"},
                {"name": "Long Call", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"}
            ]
            primary = "Bull Call Spread"
            rationale = "Normal IV allows flexibility. Bull call spread balances cost and reward."

        elif direction == "SHORT":
            strategies = [
                {"name": "Bear Put Spread", "type": "debit", "risk": "defined", "max_profit": "spread width - debit", "max_loss": "net debit"},
                {"name": "Put Diagonal", "type": "debit", "risk": "defined", "max_profit": "variable", "max_loss": "net debit"},
                {"name": "Long Put", "type": "debit", "risk": "defined", "max_profit": "strike - premium", "max_loss": "premium"}
            ]
            primary = "Bear Put Spread"
            rationale = "Normal IV allows flexibility. Bear put spread balances cost and reward."

        else:  # NEUTRAL
            strategies = [
                {"name": "Iron Butterfly", "type": "credit", "risk": "defined", "max_profit": "net credit", "max_loss": "wing width - credit"},
                {"name": "Calendar Spread", "type": "debit", "risk": "defined", "max_profit": "front month decay", "max_loss": "net debit"},
                {"name": "Double Diagonal", "type": "mixed", "risk": "defined", "max_profit": "time decay", "max_loss": "net debit"}
            ]
            primary = "Iron Butterfly or Calendar Spread"
            rationale = "Normal IV with neutral outlook. Iron butterfly for premium, calendar for time decay."

    # Calculate suggested strikes based on ATM
    atm_strike = round(current_price / 5) * 5  # Round to nearest $5

    return {
        "primary_strategy": primary,
        "rationale": rationale,
        "alternative_strategies": strategies,
        "suggested_strikes": {
            "atm": atm_strike,
            "otm_call": atm_strike + 5,
            "otm_put": atm_strike - 5,
            "deep_otm_call": atm_strike + 10,
            "deep_otm_put": atm_strike - 10
        },
        "iv_environment": "HIGH" if iv_rank >= 70 else "LOW" if iv_rank <= 30 else "NORMAL",
        "mcmillan_reference": "Chapter 1-10: Basic Option Strategies"
    }


def _calculate_options_composite_score(
    iv_analysis: dict,
    pc_ratio_analysis: dict,
    oi_analysis: dict,
    uoa_analysis: dict,
    direction: str
) -> dict:
    """Calculate composite options score for the given direction."""

    score = 50  # Start neutral
    factors = []

    # IV Factor (±15 points)
    iv_rank = iv_analysis['iv_rank']
    if direction in ["LONG", "SHORT"]:
        if iv_rank <= 30:
            score += 10
            factors.append(f"Low IV ({iv_rank:.0f}) favors buying premium: +10")
        elif iv_rank >= 70:
            score += 5
            factors.append(f"High IV ({iv_rank:.0f}) good for selling premium: +5")
    else:  # NEUTRAL
        if 30 <= iv_rank <= 70:
            score += 10
            factors.append(f"Normal IV ({iv_rank:.0f}) ideal for neutral strategies: +10")

    # P/C Ratio Factor (±15 points) - Contrarian
    if direction == "LONG":
        if pc_ratio_analysis['contrarian_signal'] in ["BULLISH", "SLIGHTLY_BULLISH"]:
            score += 15
            factors.append(f"P/C ratio contrarian bullish: +15")
        elif pc_ratio_analysis['contrarian_signal'] in ["BEARISH", "SLIGHTLY_BEARISH"]:
            score -= 10
            factors.append(f"P/C ratio contrarian bearish: -10")
    elif direction == "SHORT":
        if pc_ratio_analysis['contrarian_signal'] in ["BEARISH", "SLIGHTLY_BEARISH"]:
            score += 15
            factors.append(f"P/C ratio contrarian bearish: +15")
        elif pc_ratio_analysis['contrarian_signal'] in ["BULLISH", "SLIGHTLY_BULLISH"]:
            score -= 10
            factors.append(f"P/C ratio contrarian bullish: -10")

    # OI/Max Pain Factor (±10 points)
    if direction == "LONG" and oi_analysis['oi_bias'] == "BULLISH":
        score += 10
        factors.append(f"Max pain above price (gravitational pull higher): +10")
    elif direction == "SHORT" and oi_analysis['oi_bias'] == "BEARISH":
        score += 10
        factors.append(f"Max pain below price (gravitational pull lower): +10")
    elif oi_analysis['oi_bias'] == "NEUTRAL":
        score += 5
        factors.append(f"Price near max pain (range-bound): +5")

    # Unusual Activity Factor (±15 points)
    if direction == "LONG" and uoa_analysis['smart_money_signal'] == "BULLISH":
        score += 15
        factors.append(f"Smart money bullish positioning: +15")
    elif direction == "SHORT" and uoa_analysis['smart_money_signal'] == "BEARISH":
        score += 15
        factors.append(f"Smart money bearish positioning: +15")
    elif uoa_analysis['smart_money_signal'] == "MIXED":
        factors.append(f"Mixed smart money signals: +0")

    # Cap score
    score = max(0, min(100, score))

    # Determine confidence
    if score >= 80:
        confidence = "HIGH"
    elif score >= 65:
        confidence = "MODERATE"
    elif score >= 50:
        confidence = "LOW"
    else:
        confidence = "VERY_LOW"

    return {
        "total_score": score,
        "confidence": confidence,
        "factors": factors,
        "interpretation": f"Options analysis {'strongly supports' if score >= 80 else 'supports' if score >= 65 else 'is neutral on' if score >= 50 else 'does not support'} {direction} position"
    }


def register_tools(mcp):
    """Register options analysis tools with MCP server."""
    from .market_data import get_options_impl as get_options  # Late import to avoid circular deps

    @mcp.tool()
    def analyze_options_mcmillan(
        ticker: str,
        holding_period_days: int = 30,
        use_questrade_greeks: bool = True
    ) -> dict[str, Any]:
        """
        McMillan Options Strategy Analysis - Direction-independent options analysis using
        Lawrence McMillan's methodology from "Options as a Strategic Investment".

        This tool is PURELY ANALYTICAL - it provides data for decision making without
        assuming a direction. Use the output to inform your trading decisions.

        Provides institutional-grade options analysis including:
        - IV Rank/Percentile Analysis (TRUE IV from options vs historical range)
        - Put/Call Ratio Analysis (sentiment indicator)
        - Open Interest Analysis (max pain, positioning)
        - Unusual Options Activity Detection (smart money signals)
        - Greeks Assessment (Delta, Gamma, Theta, Vega exposure)
        - IV-Based Strategy Suggestions (based on IV environment only)

        Args:
            ticker: Stock symbol to analyze
            holding_period_days: Expected holding period for strategy selection (default 30)
            use_questrade_greeks: Try to get Greeks from Questrade API (more accurate)

        Returns:
            dict: Comprehensive McMillan options analysis (direction-independent)

        Reference: McMillan, L.G. "Options as a Strategic Investment" (5th Edition)
        """
        import numpy as np
        from datetime import datetime, timedelta

        ticker = validate_ticker(ticker)

        try:
            # Get current stock price
            t = yf.Ticker(ticker)
            info = t.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            if not current_price:
                raise ValueError(f"Could not get current price for {ticker}")

            # Try Questrade first for options chain (more accurate, especially for split-adjusted stocks)
            calls_df = None
            puts_df = None
            nearest_exp = None
            expirations = []
            options_source = "yfinance"

            try:
                from investor_agent.questrade import get_questrade_client
                from questrade_api import Questrade

                qt_client = get_questrade_client()
                symbol_info = qt_client.get_symbol_info(ticker)

                if symbol_info and symbol_info.get('symbols') and symbol_info['symbols'][0].get('hasOptions'):
                    symbol_id = symbol_info['symbols'][0]['symbolId']

                    # Get Questrade client directly for options
                    q = Questrade()
                    qt_options = q.symbol_options(symbol_id)

                    if qt_options and qt_options.get('optionChain'):
                        # Parse Questrade options chain into DataFrames
                        target_date = datetime.now() + timedelta(days=holding_period_days)

                        # Find nearest expiration
                        exp_dates = [exp['expiryDate'][:10] for exp in qt_options['optionChain']]
                        expirations = exp_dates

                        if exp_dates:
                            nearest_exp = min(exp_dates, key=lambda x: abs(
                                (datetime.strptime(x, '%Y-%m-%d') - target_date).days
                            ))

                            # Get the chain for nearest expiration
                            for exp in qt_options['optionChain']:
                                if exp['expiryDate'].startswith(nearest_exp):
                                    # Build calls and puts DataFrames from Questrade data
                                    calls_data = []
                                    puts_data = []

                                    for root in exp.get('chainPerRoot', []):
                                        for strike_info in root.get('chainPerStrikePrice', []):
                                            strike = strike_info['strikePrice']
                                            call_id = strike_info.get('callSymbolId')
                                            put_id = strike_info.get('putSymbolId')

                                            # Get quotes for these options using keyword argument
                                            try:
                                                if call_id:
                                                    call_quotes = q.markets_options(optionIds=[call_id])
                                                    if call_quotes and call_quotes.get('optionQuotes'):
                                                        cq = call_quotes['optionQuotes'][0]
                                                        calls_data.append({
                                                            'strike': strike,
                                                            'lastPrice': cq.get('lastTradePrice') or 0,
                                                            'bid': cq.get('bidPrice') or 0,
                                                            'ask': cq.get('askPrice') or 0,
                                                            'volume': cq.get('volume') or 0,
                                                            'openInterest': cq.get('openInterest') or 0,
                                                            'impliedVolatility': cq.get('volatility') or 0.3,
                                                            'delta': cq.get('delta') or 0,
                                                            'gamma': cq.get('gamma') or 0,
                                                            'theta': cq.get('theta') or 0,
                                                            'vega': cq.get('vega') or 0
                                                        })
                                                if put_id:
                                                    put_quotes = q.markets_options(optionIds=[put_id])
                                                    if put_quotes and put_quotes.get('optionQuotes'):
                                                        pq = put_quotes['optionQuotes'][0]
                                                        puts_data.append({
                                                            'strike': strike,
                                                            'lastPrice': pq.get('lastTradePrice') or 0,
                                                            'bid': pq.get('bidPrice') or 0,
                                                            'ask': pq.get('askPrice') or 0,
                                                            'volume': pq.get('volume') or 0,
                                                            'openInterest': pq.get('openInterest') or 0,
                                                            'impliedVolatility': pq.get('volatility') or 0.3,
                                                            'delta': pq.get('delta') or 0,
                                                            'gamma': pq.get('gamma') or 0,
                                                            'theta': pq.get('theta') or 0,
                                                            'vega': pq.get('vega') or 0
                                                        })
                                            except Exception:
                                                pass  # Skip individual option quote errors

                                    if calls_data or puts_data:
                                        temp_calls_df = pd.DataFrame(calls_data) if calls_data else pd.DataFrame()
                                        temp_puts_df = pd.DataFrame(puts_data) if puts_data else pd.DataFrame()

                                        # CRITICAL: Validate Questrade strikes are reasonable
                                        # (Questrade sometimes returns unadjusted/stale split data)
                                        all_strikes = []
                                        if not temp_calls_df.empty:
                                            all_strikes.extend(temp_calls_df['strike'].tolist())
                                        if not temp_puts_df.empty:
                                            all_strikes.extend(temp_puts_df['strike'].tolist())

                                        if all_strikes:
                                            min_strike = min(all_strikes)
                                            max_strike = max(all_strikes)

                                            # Check if ATM strikes exist (within 20% of current price)
                                            atm_strikes = [s for s in all_strikes if 0.8 * current_price <= s <= 1.2 * current_price]

                                            if not atm_strikes:
                                                # No reasonable ATM strikes - Questrade data is stale
                                                logger.warning(
                                                    f"Questrade options data appears stale for {ticker}: "
                                                    f"strikes {min_strike:.2f}-{max_strike:.2f} vs price {current_price:.2f}. "
                                                    f"Falling back to yfinance."
                                                )
                                                # Don't set calls_df/puts_df - let it fall through to yfinance
                                            else:
                                                # Questrade data is valid
                                                calls_df = temp_calls_df
                                                puts_df = temp_puts_df
                                                options_source = "questrade"
                                                logger.info(f"Using Questrade options data for {ticker} (validated strikes near {current_price:.2f})")
                                        else:
                                            logger.warning(f"No strike data from Questrade for {ticker}")
                                    break
            except Exception as qt_err:
                logger.warning(f"Questrade options unavailable for {ticker}: {qt_err}")

            # Fall back to yfinance if Questrade didn't work
            if calls_df is None or (calls_df.empty if hasattr(calls_df, 'empty') else True):
                logger.info(f"Falling back to yfinance for {ticker} options")
                expirations = t.options
                if not expirations:
                    raise ValueError(f"No options available for {ticker}")

                target_date = datetime.now() + timedelta(days=holding_period_days)
                nearest_exp = min(expirations, key=lambda x: abs(
                    (datetime.strptime(x, '%Y-%m-%d') - target_date).days
                ))

                calls_df, puts_df = _fetch_yf_option_chain(t, nearest_exp)
                options_source = "yfinance"

                # Validate yfinance data - check if strikes are reasonable vs price
                if not calls_df.empty:
                    min_strike = calls_df['strike'].min()
                    max_strike = calls_df['strike'].max()
                    # If strikes are way off (like 3x+ away from price), data is bad
                    if min_strike > current_price * 2 or max_strike < current_price * 0.5:
                        logger.warning(f"yfinance options data appears invalid for {ticker}: strikes {min_strike}-{max_strike} vs price {current_price}")
                        raise ValueError(f"Invalid options data for {ticker} (possible split adjustment issue)")

            if (calls_df is None or (hasattr(calls_df, 'empty') and calls_df.empty)) and \
               (puts_df is None or (hasattr(puts_df, 'empty') and puts_df.empty)):
                raise ValueError(f"No options data for {ticker} at {nearest_exp}")

            # ============================================================
            # 1. IV ANALYSIS (McMillan Ch. 28: Volatility Trading)
            # ============================================================
            iv_analysis = _calculate_iv_analysis(ticker, calls_df, puts_df, current_price)

            # ============================================================
            # 2. PUT/CALL RATIO ANALYSIS (McMillan Ch. 24: Stock Option Strategies)
            # ============================================================
            pc_ratio_analysis = _calculate_pc_ratio(calls_df, puts_df)

            # ============================================================
            # 3. OPEN INTEREST ANALYSIS (McMillan Ch. 25: Index Option Strategies)
            # ============================================================
            oi_analysis = _calculate_oi_analysis(calls_df, puts_df, current_price)

            # ============================================================
            # 4. UNUSUAL OPTIONS ACTIVITY (McMillan Ch. 36: Portfolio Management)
            # ============================================================
            uoa_analysis = _detect_unusual_activity(calls_df, puts_df, current_price)

            # ============================================================
            # 5. GREEKS ASSESSMENT (Try Questrade for accurate Greeks)
            # ============================================================
            greeks_analysis = None
            if use_questrade_greeks:
                try:
                    greeks_analysis = _get_questrade_greeks(ticker, nearest_exp, current_price)
                except Exception as e:
                    logger.warning(f"Questrade Greeks unavailable: {e}")

            if greeks_analysis is None:
                # Fallback to yfinance Greeks (less accurate but available)
                greeks_analysis = _estimate_greeks_from_chain(calls_df, puts_df, current_price)

            # ============================================================
            # 6. IV-BASED STRATEGY SUGGESTIONS (Direction-Independent)
            # ============================================================
            strategy_suggestions = _get_iv_based_strategies(
                iv_rank=iv_analysis['iv_rank'],
                current_price=current_price,
                calls_df=calls_df,
                puts_df=puts_df
            )

            # ============================================================
            # 7. OPTIONS QUALITY SCORE (Direction-Independent)
            # ============================================================
            options_quality = _calculate_options_quality_score(
                iv_analysis=iv_analysis,
                pc_ratio_analysis=pc_ratio_analysis,
                oi_analysis=oi_analysis,
                uoa_analysis=uoa_analysis
            )

            # ============================================================
            # 8. INSTITUTIONAL OPTIONS ENHANCEMENTS (NEW)
            # ============================================================

            # 8a. Earnings Proximity Check - Skip if < 30 days
            earnings_check = _get_earnings_proximity(ticker)

            # 8b. Liquidity Tier Classification
            avg_volume = info.get('averageVolume', 0) or info.get('averageDailyVolume10Day', 0)
            liquidity_tier = _calculate_liquidity_tier(ticker, avg_volume)

            # 8c. Liquidity Score (calculate from ATM options)
            atm_liquidity = {"score": 50, "grade": "C", "tradeable": True, "warnings": []}
            try:
                if not calls_df.empty:
                    # Find ATM strike
                    atm_idx = (calls_df['strike'] - current_price).abs().idxmin()
                    atm_call = calls_df.loc[atm_idx]
                    atm_strike = float(atm_call.get('strike', 0) or 0)

                    # Calculate bid-ask spread % with multiple fallbacks
                    bid = atm_call.get('bid', 0) or 0
                    ask = atm_call.get('ask', 0) or 0

                    # FALLBACK 1: Try fresh Questrade option quote if bid/ask is missing
                    if (bid == 0 or ask == 0) and options_source == "questrade":
                        try:
                            from investor_agent.questrade import get_questrade_client
                            from questrade_api import Questrade

                            qt_client = get_questrade_client()
                            symbol_info = qt_client.get_symbol_info(ticker)

                            if symbol_info and symbol_info.get('symbols'):
                                symbol_id = symbol_info['symbols'][0]['symbolId']
                                q = Questrade()
                                qt_options = q.symbol_options(symbol_id)

                                # Find the matching expiration and strike
                                if qt_options and qt_options.get('optionChain'):
                                    for exp in qt_options['optionChain']:
                                        if exp['expiryDate'][:10] == nearest_exp:
                                            for root in exp.get('chainPerRoot', []):
                                                for strike_info in root.get('chainPerStrikePrice', []):
                                                    if abs(strike_info['strikePrice'] - atm_strike) < 0.5:
                                                        call_id = strike_info.get('callSymbolId')
                                                        if call_id:
                                                            # Fetch real-time quote
                                                            call_quotes = q.markets_options(optionIds=[call_id])
                                                            if call_quotes and call_quotes.get('optionQuotes'):
                                                                cq = call_quotes['optionQuotes'][0]
                                                                qt_bid = cq.get('bidPrice') or 0
                                                                qt_ask = cq.get('askPrice') or 0
                                                                if qt_bid > 0 and qt_ask > 0:
                                                                    bid = qt_bid
                                                                    ask = qt_ask
                                                                    logger.info(f"✅ Real-time Questrade bid/ask for {ticker} ATM ${atm_strike}: bid=${bid}, ask=${ask}")
                                                                    break
                                            if bid > 0 and ask > 0:
                                                break
                        except Exception as e:
                            logger.debug(f"Questrade real-time quote fallback failed: {e}")

                    # FALLBACK 2: Try yfinance if still no bid/ask
                    if (bid == 0 or ask == 0):
                        try:
                            # Use global yf (imported at top of file)
                            t_yf = yf.Ticker(ticker)
                            # Get nearest expiry
                            target_date = datetime.now() + timedelta(days=holding_period_days)
                            if t_yf.options:
                                nearest_yf_exp = min(t_yf.options, key=lambda x: abs(
                                    (datetime.strptime(x, '%Y-%m-%d') - target_date).days
                                ))
                                yf_calls, _ = _fetch_yf_option_chain(t_yf, nearest_yf_exp)
                                # Find ATM strike
                                atm_yf_row = yf_calls.loc[(yf_calls['strike'] - atm_strike).abs().idxmin()]
                                yf_bid = float(atm_yf_row.get('bid', 0) or 0)
                                yf_ask = float(atm_yf_row.get('ask', 0) or 0)
                                if yf_bid > 0 and yf_ask > 0:
                                    bid = yf_bid
                                    ask = yf_ask
                                    logger.debug(f"Bid/ask fallback to yfinance for {ticker}: bid=${bid}, ask=${ask}")
                        except Exception as e:
                            logger.debug(f"yfinance bid/ask fallback failed: {e}")

                    # Calculate spread using midpoint (more robust than bid-only)
                    if bid > 0 and ask > 0:
                        midpoint = (bid + ask) / 2
                        spread_pct = ((ask - bid) / midpoint * 100)
                    elif ask > 0:
                        # Only ask available - estimate spread as 2x the ask-to-lastPrice gap
                        last_price = atm_call.get('lastPrice', 0) or 0
                        if last_price > 0:
                            spread_pct = abs(ask - last_price) / last_price * 100 * 2
                        else:
                            # Use tier-based proxy when data unavailable
                            tier = liquidity_tier.get('tier')
                            if tier == 'TIER_1':
                                spread_pct = 0.1  # SPY, QQQ: $0.01-0.05 typical (penny-wide)
                                logger.debug(f"Using TIER_1 spread proxy (0.1%) for {ticker} - bid/ask unavailable")
                            elif tier == 'TIER_2':
                                spread_pct = 0.3  # High-volume S&P 500: $0.05-0.15 typical
                                logger.debug(f"Using TIER_2 spread proxy (0.3%) for {ticker} - bid/ask unavailable")
                            elif tier == 'TIER_3':
                                spread_pct = 1.0  # Mid-caps: $0.10-0.50 typical
                                logger.debug(f"Using TIER_3 spread proxy (1.0%) for {ticker} - bid/ask unavailable")
                            else:
                                spread_pct = 5.0  # NON_LIQUID: wide spreads, likely to fail (correct)
                                logger.debug(f"Using NON_LIQUID spread proxy (5.0%) for {ticker} - bid/ask unavailable")
                    else:
                        # Use tier-based proxy when data unavailable
                        tier = liquidity_tier.get('tier')
                        if tier == 'TIER_1':
                            spread_pct = 0.1  # SPY, QQQ: $0.01-0.05 typical (penny-wide)
                            logger.debug(f"Using TIER_1 spread proxy (0.1%) for {ticker} - bid/ask unavailable")
                        elif tier == 'TIER_2':
                            spread_pct = 0.3  # High-volume S&P 500: $0.05-0.15 typical
                            logger.debug(f"Using TIER_2 spread proxy (0.3%) for {ticker} - bid/ask unavailable")
                        elif tier == 'TIER_3':
                            spread_pct = 1.0  # Mid-caps: $0.10-0.50 typical
                            logger.debug(f"Using TIER_3 spread proxy (1.0%) for {ticker} - bid/ask unavailable")
                        else:
                            spread_pct = 5.0  # NON_LIQUID: wide spreads, likely to fail (correct)
                            logger.debug(f"Using NON_LIQUID spread proxy (5.0%) for {ticker} - bid/ask unavailable")

                    # Determine target expiry for OI fallback lookup
                    target_date = datetime.now() + timedelta(days=holding_period_days)
                    target_expiry_str = None
                    if expirations:
                        target_expiry_str = min(expirations, key=lambda x: abs(
                            (datetime.strptime(x[:10], '%Y-%m-%d') - target_date).days
                        ))[:10]

                    # Get OI with yfinance fallback if OI is 0 (any source)
                    raw_oi = int(atm_call.get('openInterest', 0) or 0)
                    if raw_oi == 0 and target_expiry_str:
                        # Primary fallback: yfinance option chain
                        raw_oi = _get_oi_with_yf_fallback(
                            questrade_oi=raw_oi,
                            ticker=ticker,
                            strike=atm_strike,
                            expiry=target_expiry_str,
                            option_type="call"
                        )

                        # Secondary fallback: use get_options() which is known to return correct OI
                        if raw_oi == 0:
                            try:
                                options_result = get_options(
                                    ticker_symbol=ticker,
                                    start_date=target_expiry_str,
                                    end_date=target_expiry_str,
                                    option_type="C",
                                    strike_lower=atm_strike - 1,
                                    strike_upper=atm_strike + 1,
                                    num_options=5
                                )
                                if "data" in options_result:
                                    import csv
                                    from io import StringIO
                                    reader = csv.DictReader(StringIO(options_result["data"]))
                                    for row in reader:
                                        try:
                                            row_strike = float(row.get('strike', 0))
                                            if abs(row_strike - atm_strike) <= 1.0:
                                                oi_val = int(row.get('openInterest', 0) or 0)
                                                if oi_val > raw_oi:
                                                    raw_oi = oi_val
                                                    logger.info(f"OI fallback via get_options for {ticker}: {raw_oi}")
                                        except (ValueError, TypeError):
                                            pass
                            except Exception as oi_fallback_err:
                                logger.debug(f"get_options OI fallback failed: {oi_fallback_err}")

                    atm_liquidity = _calculate_liquidity_score(
                        bid_ask_spread_pct=spread_pct,
                        open_interest=raw_oi,
                        daily_volume=int(atm_call.get('volume', 0) or 0),
                        underlying_volume=int(avg_volume),
                        bid_size=5,  # Default if not available
                        ask_size=5,
                        liquidity_tier=liquidity_tier.get('tier')  # Pass tier for off-market handling
                    )
            except Exception as liq_err:
                logger.warning(f"Liquidity score calculation error: {liq_err}")

            # 8d. Optimal 45 DTE Expiry
            optimal_expiry = _find_target_expiry(expirations, target_dte=45)

            # 8e. Expected Move Calculation
            current_iv = iv_analysis.get('current_iv', 30) / 100  # Convert to decimal
            expected_move = _calculate_expected_move(
                current_price=current_price,
                iv=current_iv,
                dte=optimal_expiry.get('dte', 45) or 45
            )

            # 8f. Determine if options trading allowed (now distinguishes buyers vs sellers)
            # CRITICAL: Sellers benefit from high IV near earnings, buyers get hurt
            is_liquid = liquidity_tier.get('tier') != 'NON_LIQUID' and atm_liquidity.get('tradeable', True)

            options_buying_allowed = (
                earnings_check.get('options_buying_allowed', True) and is_liquid
            )
            options_selling_allowed = (
                earnings_check.get('options_selling_allowed', True) and is_liquid
            )
            # Legacy field - now True if SELLING is allowed (more permissive for sellers)
            options_allowed = options_selling_allowed

            # Collect all warnings and opportunities
            all_warnings = []
            seller_opportunities = []

            # Buyer warning (if buying not allowed near earnings)
            if earnings_check.get('buyer_warning'):
                all_warnings.append(earnings_check['buyer_warning'])

            # Seller opportunity (highlighted when near earnings)
            if earnings_check.get('seller_opportunity'):
                seller_opportunities.append(earnings_check['seller_opportunity'])

            all_warnings.extend(liquidity_tier.get('warnings', []))
            all_warnings.extend(atm_liquidity.get('warnings', []))
            if optimal_expiry.get('warning'):
                all_warnings.append(optimal_expiry['warning'])

            # Get recommended selling strategies if near earnings
            earnings_strategies = earnings_check.get('recommended_strategies', [])

            result = {
                "ticker": ticker,
                "current_price": current_price,
                "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "holding_period_days": holding_period_days,
                "nearest_expiration": nearest_exp,
                "available_expirations": expirations[:5],  # First 5 expirations

                # McMillan Analysis Components
                "iv_analysis": iv_analysis,
                "put_call_ratio": pc_ratio_analysis,
                "open_interest": oi_analysis,
                "unusual_activity": uoa_analysis,
                "greeks_assessment": greeks_analysis,

                # IV-Based Strategy Suggestions (not direction-dependent)
                "strategy_suggestions": strategy_suggestions,

                # Options Quality Score
                "options_quality": options_quality,

                # ============================================================
                # INSTITUTIONAL OPTIONS DATA (NEW)
                # ============================================================
                "institutional": {
                    # Earnings Filter - NOW WITH BUYER/SELLER DISTINCTION
                    "earnings_check": earnings_check,
                    "days_to_earnings": earnings_check.get('days_to_earnings'),

                    # Liquidity Assessment
                    "liquidity_tier": liquidity_tier,
                    "liquidity_score": atm_liquidity,

                    # Optimal Entry
                    "optimal_expiry": optimal_expiry,
                    "target_dte": 45,
                    "recommended_dte": optimal_expiry.get('dte'),

                    # Expected Move
                    "expected_move": expected_move,

                    # Trade Allowed Flags - BUYER vs SELLER
                    "options_allowed": options_allowed,  # Legacy (True if selling allowed)
                    "options_buying_allowed": options_buying_allowed,  # NEW: Buyers hurt by IV crush
                    "options_selling_allowed": options_selling_allowed,  # NEW: Sellers profit from IV crush
                    "skip_reason": all_warnings[0] if all_warnings and not options_buying_allowed else None,

                    # Earnings-Related Strategies (when near earnings, sellers benefit)
                    "earnings_strategies": earnings_strategies,
                    "seller_opportunities": seller_opportunities,

                    # All Warnings
                    "warnings": all_warnings,

                    # Position Sizing Multiplier
                    "size_multiplier": liquidity_tier.get('size_multiplier', 1.0),
                },

                # Quick Summary (Enhanced)
                "summary": {
                    "iv_environment": iv_analysis['iv_environment'],
                    "iv_rank": iv_analysis['iv_rank'],
                    "sentiment": pc_ratio_analysis['sentiment'],
                    "smart_money_signal": uoa_analysis['smart_money_signal'],
                    "options_quality_score": options_quality['score'],
                    "primary_suggestion": strategy_suggestions['high_iv_strategies'][0] if iv_analysis['iv_rank'] >= 50 else strategy_suggestions['low_iv_strategies'][0],
                    # Institutional summary - NOW WITH BUYER/SELLER DISTINCTION
                    "options_allowed": options_allowed,  # Legacy
                    "options_buying_allowed": options_buying_allowed,  # NEW
                    "options_selling_allowed": options_selling_allowed,  # NEW
                    "liquidity_tier": liquidity_tier.get('tier'),
                    "liquidity_grade": atm_liquidity.get('grade'),
                    "days_to_earnings": earnings_check.get('days_to_earnings'),
                    "optimal_dte": optimal_expiry.get('dte'),
                    "expected_move_pct": expected_move.get('expected_move_pct'),
                    "warnings_count": len(all_warnings),
                    "seller_opportunities_count": len(seller_opportunities),  # NEW
                    "earnings_strategy_hint": earnings_strategies[0] if earnings_strategies else None,  # NEW
                },

                "methodology": "McMillan - Options as a Strategic Investment (5th Ed.) + Institutional Parameters"
            }

            # Convert numpy types to Python native types for JSON serialization
            return convert_numpy_types(result)

        except Exception as e:
            logger.error(f"Error in analyze_options_mcmillan for {ticker}: {e}")
            raise ValueError(f"McMillan options analysis failed: {str(e)}")


    @mcp.tool()
    def generate_options_trade_plan(
        ticker: str,
        direction: str,
        account_size: float = 10000,
        target_dte: int = 45
    ) -> dict[str, Any]:
        """
        Generate complete institutional options trade plan.

        Creates a professional options trade plan following McMillan methodology:
        - Strategy selection based on IV environment + direction
        - 45 DTE targeting with 50% profit management (88% win rate)
        - 16-delta short strikes for credit strategies
        - Position sizing using Half-Kelly criterion
        - Complete exit rules (NO stop losses per TastyTrade research)

        CRITICAL EARNINGS RULES (BUYER vs SELLER):
        - BUYERS: Skip if earnings < 30 days (IV crush will hurt you)
        - SELLERS: PRIME TIME near earnings (IV crush = profit for premium sellers)
        - McMillan/TastyTrade: "When IV is HIGH, be a SELLER"

        Liquidity Rules:
        - Liquidity warnings for non-Tier 1 underlyings
        - Greeks-based position limits

        Args:
            ticker: Stock symbol
            direction: LONG or SHORT
            account_size: Account value for position sizing (default $10,000)
            target_dte: Target days to expiration (default 45)

        Returns:
            Complete options trade plan with:
            - options_allowed: Whether options are recommended
            - options_buying_allowed: Whether BUYING options is recommended
            - options_selling_allowed: Whether SELLING options is recommended
            - stock_plan: Stock trading plan (entry, stop, targets)
            - options_plan: Options strategy with specific legs
            - position_sizing: Contracts based on account
            - exit_rules: 50% profit, 21 DTE roll, NO stops
            - warnings: All liquidity/earnings warnings
            - seller_opportunities: Highlighted opportunities for premium sellers
        """
        from datetime import datetime, timedelta

        ticker = validate_ticker(ticker)
        direction = direction.upper()
        if direction not in ('LONG', 'SHORT'):
            raise ValueError(f"Direction must be LONG or SHORT, got: {direction}")

        params = INSTITUTIONAL_OPTIONS_PARAMS

        try:
            # Get McMillan analysis (includes institutional data now)
            mcmillan = analyze_options_mcmillan(ticker, holding_period_days=target_dte)

            current_price = mcmillan['current_price']
            iv_analysis = mcmillan['iv_analysis']
            institutional = mcmillan.get('institutional', {})
            greeks = mcmillan.get('greeks_assessment', {})

            # Extract key data - NOW WITH BUYER/SELLER DISTINCTION
            iv_rank = iv_analysis.get('iv_rank', 50)
            iv_percentile = iv_analysis.get('iv_percentile', 50)
            options_allowed = institutional.get('options_allowed', True)  # Legacy (selling allowed)
            options_buying_allowed = institutional.get('options_buying_allowed', True)
            options_selling_allowed = institutional.get('options_selling_allowed', True)
            liquidity_tier = institutional.get('liquidity_tier', {})
            size_multiplier = liquidity_tier.get('size_multiplier', 1.0)  # Extract early for Iron Condor path
            optimal_expiry = institutional.get('optimal_expiry', {})
            expected_move = institutional.get('expected_move', {})
            all_warnings = institutional.get('warnings', [])
            seller_opportunities = institutional.get('seller_opportunities', [])
            earnings_strategies = institutional.get('earnings_strategies', [])
            days_to_earnings = institutional.get('days_to_earnings')

            # ============================================================
            # 1. STOCK TRADING PLAN (Always generated)
            # ============================================================
            atr_pct = 2.5  # Default 2.5% ATR for stop calculation

            if direction == "LONG":
                stop_price = round(current_price * (1 - atr_pct * 2 / 100), 2)
                target_1 = round(current_price * 1.05, 2)  # +5%
                target_2 = round(current_price * 1.10, 2)  # +10%
                risk_per_share = current_price - stop_price
            else:  # SHORT
                stop_price = round(current_price * (1 + atr_pct * 2 / 100), 2)
                target_1 = round(current_price * 0.95, 2)  # -5%
                target_2 = round(current_price * 0.90, 2)  # -10%
                risk_per_share = stop_price - current_price

            # Position sizing for stock
            stock_risk_pct = 0.02  # 2% risk per trade
            max_stock_risk = account_size * stock_risk_pct
            shares = int(max_stock_risk / risk_per_share) if risk_per_share > 0 else 0
            position_value = shares * current_price

            stock_plan = {
                "direction": direction,
                "entry_price": current_price,
                "stop_loss": stop_price,
                "stop_loss_pct": round((stop_price - current_price) / current_price * 100, 2),
                "target_1": target_1,
                "target_1_pct": round((target_1 - current_price) / current_price * 100, 2),
                "target_2": target_2,
                "target_2_pct": round((target_2 - current_price) / current_price * 100, 2),
                "shares": shares,
                "position_value": round(position_value, 2),
                "risk_per_share": round(risk_per_share, 2),
                "total_risk": round(shares * risk_per_share, 2),
                "reward_risk_ratio": round(abs(target_1 - current_price) / risk_per_share, 2) if risk_per_share > 0 else 0
            }

            # ============================================================
            # 2. OPTIONS TRADING PLAN - NOW DISTINGUISHES BUYERS vs SELLERS
            # ============================================================
            options_plan = None

            # CRITICAL: Check buyer vs seller allowed separately
            # Near earnings: Buying blocked (IV crush hurts), Selling ENCOURAGED (IV crush helps)
            near_earnings_selling_opportunity = (
                not options_buying_allowed and options_selling_allowed and days_to_earnings is not None
            )

            if not options_selling_allowed:
                # Complete skip - likely liquidity issue (both buyer and seller blocked)
                options_plan = {
                    "status": "SKIP",
                    "reason": institutional.get('skip_reason', "Options not recommended - liquidity issue"),
                    "warnings": all_warnings
                }
            elif near_earnings_selling_opportunity:
                # PRIME TIME FOR SELLERS: Near earnings, high IV, suggest selling strategies
                options_plan = {
                    "status": "SELL_PREMIUM",
                    "reason": f"✅ PRIME TIME TO SELL PREMIUM - Earnings in {days_to_earnings} days. High IV = max premium collection. Profit from IV crush.",
                    "buyer_warning": "⚠️ DO NOT BUY OPTIONS - IV crush will hurt you even if direction is right",
                    "seller_opportunity": seller_opportunities[0] if seller_opportunities else f"Sell premium to profit from IV crush after earnings",
                    "recommended_strategies": earnings_strategies if earnings_strategies else [
                        "short_put" if direction == "LONG" else "short_call",
                        "credit_spread",
                        "iron_condor"
                    ],
                    "iv_rank": iv_rank,
                    "days_to_earnings": days_to_earnings,
                    "warnings": all_warnings
                }
            else:
                # Determine IV environment for strategy selection
                if iv_rank >= 70:
                    iv_env = "HIGH_IV_70_100"
                elif iv_rank >= 50:
                    iv_env = "HIGH_IV_50_70"
                elif iv_rank >= 30:
                    iv_env = "NORMAL_IV_30_50"
                else:
                    iv_env = "LOW_IV_0_30"

                # Get strategy suggestions based on IV environment
                strategy_matrix = IV_STRATEGY_MATRIX.get(iv_env, {})
                direction_key = direction.lower()
                suggested_strategies = strategy_matrix.get(direction_key, [])
                primary_strategy = suggested_strategies[0] if suggested_strategies else "Credit Spread"
                rationale = strategy_matrix.get('rationale', '')

                # Get recommended expiry
                expiry_date = optimal_expiry.get('optimal_expiry')
                dte = optimal_expiry.get('dte', target_dte)

                # Get option chain data with Greeks
                # Use the proper Questrade helper function (same as GEX, IV Skew, etc.)
                calls_df = pd.DataFrame()
                puts_df = pd.DataFrame()

                try:
                    calls_df, puts_df = _get_questrade_options_with_greeks(ticker, expiry_date, current_price)
                except Exception as e:
                    logger.warning(f"Questrade options fetch failed: {e}, falling back to yfinance")

                # Fallback to yfinance if Questrade failed
                if calls_df.empty or puts_df.empty:
                    logger.info(f"Using yfinance for options data (Questrade had no Greeks)")
                    t = yf.Ticker(ticker)
                    try:
                        if expiry_date and expiry_date in t.options:
                            calls_df, puts_df = _fetch_yf_option_chain(t, expiry_date, copy=True)

                            # yfinance doesn't provide Greeks - calculate approximate deltas
                            # Simple approximation: delta ≈ probability of finishing ITM
                            # For calls: delta ≈ 1 - (strike/spot)^2 for ITM, (strike/spot)^2 for OTM
                            # For puts: delta ≈ -delta_call

                            if not calls_df.empty and 'strike' in calls_df.columns:
                                calls_df['delta'] = calls_df['strike'].apply(
                                    lambda s: max(0.01, min(0.99,
                                        0.5 + 0.5 * (current_price - s) / (0.3 * current_price)
                                    ))
                                )
                                # Add dummy Greeks for compatibility
                                calls_df['gamma'] = 0
                                calls_df['theta'] = -0.02  # Approximate theta
                                calls_df['vega'] = 0
                                logger.info(f"Calculated approximate deltas for {len(calls_df)} calls")

                            if not puts_df.empty and 'strike' in puts_df.columns:
                                puts_df['delta'] = puts_df['strike'].apply(
                                    lambda s: -max(0.01, min(0.99,
                                        0.5 + 0.5 * (s - current_price) / (0.3 * current_price)
                                    ))
                                )
                                # Add dummy Greeks for compatibility
                                puts_df['gamma'] = 0
                                puts_df['theta'] = -0.02  # Approximate theta
                                puts_df['vega'] = 0
                                logger.info(f"Calculated approximate deltas for {len(puts_df)} puts")
                    except Exception as e:
                        logger.warning(f"yfinance fallback also failed: {e}")

                # ============================================================
                # IRON CONDOR CONSTRUCTION (IV Rank >= 70)
                # ============================================================
                iron_condor = None
                logger.info(f"IV Rank {iv_rank}% - checking if Iron Condor construction should be attempted")
                logger.info(f"Calls DF: {len(calls_df)} rows, Puts DF: {len(puts_df)} rows")
                if iv_rank >= 70:
                    # High IV environment - ideal for Iron Condor
                    logger.info(f"High IV detected ({iv_rank}%) - Attempting Iron Condor construction for {ticker}")
                    iron_condor = _construct_iron_condor(
                        ticker=ticker,
                        current_price=current_price,
                        expiry=expiry_date,
                        dte=dte,
                        calls_df=calls_df,
                        puts_df=puts_df,
                        account_size=account_size
                    )
                    logger.info(f"Iron Condor result: {'SUCCESS' if iron_condor else 'FAILED (returned None)'}")

                # If Iron Condor construction succeeded, use it
                if iron_condor is not None:
                    logger.info("Using Iron Condor strategy")
                    # Use Iron Condor data
                    primary_strategy = "Iron Condor"
                    rationale = f"High IV ({iv_rank}%) makes selling premium attractive. Iron Condor collects premium from both sides with defined risk. Full 4-leg specification with institutional parameters (16-delta shorts, 5-delta longs)."

                    # Build options_plan from Iron Condor data
                    exit_rules = {
                        "profit_target": "Close at 50% of max profit",
                        "profit_target_value": round(iron_condor['max_profit'] * 0.50, 2),
                        "time_exit": "Roll or close at 21 DTE",
                        "roll_trigger_dte": 21,
                        "delta_adjustment": f"Roll if position delta exceeds ±{params['delta_adjustment_threshold']}",
                        "stop_loss": "⚠️ NO STOP LOSS - per TastyTrade research (stops reduce win rate to 46%)",
                        "loss_review": f"Review position at {params['loss_review_threshold']*100:.0f}% of max loss"
                    }

                    options_plan = {
                        "status": "TRADE",
                        "strategy": primary_strategy,
                        "iv_environment": iv_env,
                        "rationale": rationale,

                        # Entry Details
                        "entry": {
                            "expiry": expiry_date,
                            "dte": iron_condor['dte'],
                            "theta_zone": optimal_expiry.get('theta_zone'),
                            "legs": iron_condor['legs'],
                            "net_credit": iron_condor['net_credit'],
                            "spread_width": f"Put: ${iron_condor['put_spread_width']}, Call: ${iron_condor['call_spread_width']}"
                        },

                        # Risk/Reward
                        "risk_reward": {
                            "max_profit": iron_condor['max_profit'],
                            "max_profit_per_contract": round(iron_condor['max_profit'] / iron_condor['contracts'], 2),
                            "max_loss": iron_condor['max_loss'],
                            "max_loss_per_contract": round(iron_condor['max_loss'] / iron_condor['contracts'], 2),
                            "breakeven_lower": iron_condor['breakeven_lower'],
                            "breakeven_upper": iron_condor['breakeven_upper'],
                            "probability_of_profit": iron_condor['probability_of_profit'],
                            "reward_risk_ratio": round(iron_condor['max_profit'] / iron_condor['max_loss'], 2) if iron_condor['max_loss'] > 0 else 0
                        },

                        # Position Sizing
                        "position_sizing": {
                            "contracts": iron_condor['contracts'],
                            "buying_power_required": iron_condor['buying_power_required'],
                            "account_risk_pct": round(iron_condor['buying_power_required'] / account_size * 100, 2),
                            "size_multiplier": size_multiplier,
                            "sizing_method": "Iron Condor - 2% max risk"
                        },

                        # Exit Rules
                        "exit_rules": exit_rules,

                        # Expected Move
                        "expected_move": expected_move,

                        # Greeks (from Iron Condor aggregation)
                        "greeks": iron_condor['position_greeks'],

                        # Liquidity & Slippage
                        "liquidity_score": iron_condor['liquidity_score'],
                        "spread_cost_estimate": iron_condor['spread_cost_estimate'],

                        # Warnings
                        "warnings": all_warnings if all_warnings else ["✅ No liquidity warnings - Tier 1 underlying"]
                    }

                # ============================================================
                # JADE LIZARD CONSTRUCTION (IV Rank > 60, put skew)
                # ============================================================
                elif iv_rank > 60 and iv_rank < 70:
                    # High IV but not quite Iron Condor territory - try Jade Lizard
                    logger.info(f"IV Rank {iv_rank}% (60-70 range) - Attempting Jade Lizard construction for {ticker}")
                    jade_lizard = _construct_jade_lizard(
                        ticker=ticker,
                        current_price=current_price,
                        expiry=expiry_date,
                        dte=dte,
                        calls_df=calls_df,
                        puts_df=puts_df,
                        account_size=account_size
                    )

                    if jade_lizard is not None and jade_lizard.get('has_no_upside_risk'):
                        logger.info("Using Jade Lizard strategy")
                        primary_strategy = "Jade Lizard"
                        rationale = f"High IV ({iv_rank}%) + Put skew makes Jade Lizard attractive. NO upside risk (put premium >= call spread width). Collect premium from put + call spread with risk only on downside."

                        exit_rules = {
                            "profit_target": "Close at 50% of max profit",
                            "profit_target_value": round(jade_lizard['max_profit'] * 0.50, 2),
                            "time_exit": "Roll or close at 21 DTE",
                            "roll_trigger_dte": 21,
                            "delta_adjustment": f"Roll if position delta exceeds ±{params['delta_adjustment_threshold']}",
                            "stop_loss": "⚠️ NO STOP LOSS - per TastyTrade research",
                            "loss_review": f"Review position at {params['loss_review_threshold']*100:.0f}% of max loss"
                        }

                        options_plan = {
                            "status": "TRADE",
                            "strategy": primary_strategy,
                            "iv_environment": iv_env,
                            "rationale": rationale,

                            "entry": {
                                "expiry": expiry_date,
                                "dte": jade_lizard['dte'],
                                "theta_zone": optimal_expiry.get('theta_zone'),
                                "legs": jade_lizard['legs'],
                                "net_credit": jade_lizard['net_credit'],
                                "jade_lizard_condition": jade_lizard['jade_lizard_condition']
                            },

                            "risk_reward": {
                                "max_profit": jade_lizard['max_profit'],
                                "max_profit_per_contract": round(jade_lizard['max_profit'] / jade_lizard['contracts'], 2),
                                "max_loss": jade_lizard['max_loss'],
                                "max_loss_per_contract": round(jade_lizard['max_loss'] / jade_lizard['contracts'], 2),
                                "breakeven_downside": jade_lizard['breakeven_downside'],
                                "breakeven_upside": jade_lizard['breakeven_upside'],
                                "reward_risk_ratio": round(jade_lizard['max_profit'] / jade_lizard['max_loss'], 2) if jade_lizard['max_loss'] > 0 else 0
                            },

                            "position_sizing": {
                                "contracts": jade_lizard['contracts'],
                                "buying_power_required": jade_lizard['buying_power_required'],
                                "account_risk_pct": round(jade_lizard['buying_power_required'] / account_size * 100, 2),
                                "size_multiplier": size_multiplier,
                                "sizing_method": "Jade Lizard - 2% max risk"
                            },

                            "exit_rules": exit_rules,
                            "expected_move": expected_move,
                            "greeks": jade_lizard['position_greeks'],
                            "liquidity_score": jade_lizard['liquidity_score'],
                            "warnings": all_warnings if all_warnings else ["✅ No liquidity warnings"]
                        }
                    else:
                        logger.info(f"Jade Lizard construction failed or doesn't meet no-upside-risk condition, falling back to credit spreads")
                        options_plan = None  # Will trigger credit spread fallback

                # ============================================================
                # CALENDAR SPREAD CONSTRUCTION (IV Rank < 50, contango)
                # ============================================================
                elif iv_rank < 50:
                    # Low to moderate IV - check term structure for calendar spread opportunity
                    logger.info(f"IV Rank {iv_rank}% (< 50) - Checking term structure for Calendar Spread")

                    # Get term structure
                    try:
                        term_structure = analyze_iv_term_structure(ticker, expirations_to_analyze=4)
                        is_contango = term_structure.get('structure_classification') == 'CONTANGO'
                        calendar_signal = term_structure.get('calendar_spread_signal')

                        if is_contango and calendar_signal == 'FAVORABLE':
                            logger.info("Term structure in contango - Attempting Calendar Spread construction")

                            # Get front and back month options
                            # Front month: nearest expiration
                            # Back month: next expiration
                            t = yf.Ticker(ticker)
                            if len(t.options) >= 2:
                                front_expiry = t.options[0]
                                back_expiry = t.options[1]

                                # Fetch both chains
                                try:
                                    front_calls, front_puts = _fetch_yf_option_chain(t, front_expiry)
                                    back_calls, back_puts = _fetch_yf_option_chain(t, back_expiry)

                                    # Attempt calendar spread construction
                                    calendar_spread = _construct_calendar_spread(
                                        ticker=ticker,
                                        current_price=current_price,
                                        front_month_expiry=front_expiry,
                                        back_month_expiry=back_expiry,
                                        front_calls_df=front_calls,
                                        front_puts_df=front_puts,
                                        back_calls_df=back_calls,
                                        back_puts_df=back_puts,
                                        account_size=account_size,
                                        direction='NEUTRAL'  # Calendars are typically neutral
                                    )

                                    if calendar_spread is not None:
                                        logger.info("Using Calendar Spread strategy")
                                        primary_strategy = "Calendar Spread"
                                        rationale = f"Low IV ({iv_rank}%) + Contango term structure makes Calendar Spread attractive. Profit from theta differential as front month decays faster than back month."

                                        exit_rules = {
                                            "profit_target": "Close when front month approaches expiration or at 50% profit",
                                            "time_exit": "Close before front month expiration (7 DTE)",
                                            "adjustment": "Close if price moves more than 10% from ATM strike",
                                            "stop_loss": "Close at max loss (debit paid)"
                                        }

                                        options_plan = {
                                            "status": "TRADE",
                                            "strategy": primary_strategy,
                                            "iv_environment": iv_env,
                                            "rationale": rationale,

                                            "entry": {
                                                "front_expiry": calendar_spread['front_expiry'],
                                                "back_expiry": calendar_spread['back_expiry'],
                                                "strike": calendar_spread['strike'],
                                                "option_type": calendar_spread['option_type'],
                                                "legs": calendar_spread['legs'],
                                                "net_debit": calendar_spread['net_debit'],
                                                "term_structure": calendar_spread['term_structure']
                                            },

                                            "risk_reward": {
                                                "max_loss": calendar_spread['max_loss'],
                                                "max_profit_estimate": calendar_spread['max_profit_estimate'],
                                                "ideal_outcome": "Front month expires worthless, back month retains value"
                                            },

                                            "position_sizing": {
                                                "contracts": calendar_spread['contracts'],
                                                "buying_power_required": calendar_spread['buying_power_required'],
                                                "account_risk_pct": round(calendar_spread['buying_power_required'] / account_size * 100, 2),
                                                "sizing_method": "Calendar Spread - 2% max risk"
                                            },

                                            "exit_rules": exit_rules,
                                            "greeks": calendar_spread['position_greeks'],
                                            "liquidity_score": calendar_spread['liquidity_score'],
                                            "ideal_conditions": calendar_spread['ideal_conditions'],
                                            "warnings": all_warnings if all_warnings else ["✅ Favorable calendar spread environment"]
                                        }
                                    else:
                                        logger.info("Calendar Spread construction failed, falling back to credit spreads")
                                        options_plan = None
                                except Exception as e:
                                    logger.warning(f"Calendar Spread chain fetch failed: {e}")
                                    options_plan = None
                            else:
                                logger.warning("Not enough expirations for Calendar Spread")
                                options_plan = None
                        else:
                            logger.info(f"Term structure not favorable for Calendar Spread (classification: {term_structure.get('structure_classification')})")
                            options_plan = None
                    except Exception as e:
                        logger.warning(f"Term structure analysis failed: {e}")
                        options_plan = None
                else:
                    options_plan = None

                # ============================================================
                # FALLBACK: CREDIT SPREADS (if all advanced strategies failed)
                # ============================================================
                if options_plan is None:
                    # Fallback to regular credit spreads if advanced strategies failed
                    logger.info("Using fallback Credit Spread strategy")
                    # Find 16-delta strikes
                    delta_strikes = _find_delta_strike(
                        calls_df=calls_df,
                        puts_df=puts_df,
                        current_price=current_price,
                        direction=direction,
                        target_delta=0.16
                    )

                    # Calculate trade details based on strategy type
                    short_strike = delta_strikes.get('short_strike')
                    long_strike = delta_strikes.get('long_strike')
                    short_premium = delta_strikes.get('short_premium', 0) or 0
                    long_premium = delta_strikes.get('long_premium', 0) or 0

                    # For credit spreads
                    spread_width = abs(short_strike - long_strike) if short_strike and long_strike else 5
                    net_credit = short_premium - long_premium if short_premium and long_premium else 0.50
                    max_profit = net_credit * 100  # Per contract
                    max_loss = (spread_width - net_credit) * 100  # Per contract

                    # Position sizing
                    # size_multiplier already defined at top of function (line 3717)
                    position_sizing = _calculate_options_position_size(
                        account_size=account_size,
                        max_risk=(spread_width - net_credit),
                        spread_width=spread_width,
                        premium_received=net_credit,
                        is_defined_risk=True
                    )
                    # Apply liquidity multiplier
                    adjusted_contracts = max(1, int(position_sizing['contracts'] * size_multiplier))

                    # Calculate break-even
                    if direction == "LONG":
                        break_even = short_strike - net_credit if short_strike else current_price - net_credit
                    else:
                        break_even = short_strike + net_credit if short_strike else current_price + net_credit

                    # Probability of profit (approximation: 100 - delta for credit spreads)
                    pop = round(100 - (delta_strikes.get('short_delta', 0.16) or 0.16) * 100, 1)

                    # Build trade legs
                    if direction == "LONG":
                        # Bull Put Spread: Sell put at higher strike, buy put at lower strike
                        legs = [
                            {
                                "action": "SELL",
                                "option_type": "PUT",
                                "strike": short_strike,
                                "expiry": expiry_date,
                                "premium": short_premium,
                                "delta": delta_strikes.get('short_delta'),
                                "contracts": adjusted_contracts
                            },
                            {
                                "action": "BUY",
                                "option_type": "PUT",
                                "strike": long_strike,
                                "expiry": expiry_date,
                                "premium": long_premium,
                                "delta": delta_strikes.get('long_delta'),
                                "contracts": adjusted_contracts
                            }
                        ]
                    else:  # SHORT
                        # Bear Call Spread: Sell call at lower strike, buy call at higher strike
                        legs = [
                            {
                                "action": "SELL",
                                "option_type": "CALL",
                                "strike": short_strike,
                                "expiry": expiry_date,
                                "premium": short_premium,
                                "delta": delta_strikes.get('short_delta'),
                                "contracts": adjusted_contracts
                            },
                            {
                                "action": "BUY",
                                "option_type": "CALL",
                                "strike": long_strike,
                                "expiry": expiry_date,
                                "premium": long_premium,
                                "delta": delta_strikes.get('long_delta'),
                                "contracts": adjusted_contracts
                            }
                        ]

                    # Exit rules (NO STOP LOSSES per TastyTrade research)
                    exit_rules = {
                        "profit_target": "Close at 50% of max profit",
                        "profit_target_value": round(max_profit * 0.50, 2),
                        "time_exit": "Roll or close at 21 DTE",
                        "roll_trigger_dte": 21,
                        "delta_adjustment": f"Roll if position delta exceeds ±{params['delta_adjustment_threshold']}",
                        "stop_loss": "⚠️ NO STOP LOSS - per TastyTrade research (stops reduce win rate to 46%)",
                        "loss_review": f"Review position at {params['loss_review_threshold']*100:.0f}% of max loss"
                    }

                    options_plan = {
                        "status": "TRADE",
                        "strategy": primary_strategy,
                        "iv_environment": iv_env,
                        "rationale": rationale,

                        # Entry Details
                        "entry": {
                            "expiry": expiry_date,
                            "dte": dte,
                            "theta_zone": optimal_expiry.get('theta_zone'),
                            "legs": legs,
                            "net_credit": round(net_credit, 2),
                            "spread_width": spread_width
                        },

                        # Risk/Reward
                        "risk_reward": {
                            "max_profit": round(max_profit * adjusted_contracts, 2),
                            "max_profit_per_contract": round(max_profit, 2),
                            "max_loss": round(max_loss * adjusted_contracts, 2),
                            "max_loss_per_contract": round(max_loss, 2),
                            "break_even": round(break_even, 2),
                            "probability_of_profit": pop,
                            "reward_risk_ratio": round(max_profit / max_loss, 2) if max_loss > 0 else 0
                        },

                    # Position Sizing
                    "position_sizing": {
                        "contracts": adjusted_contracts,
                        "buying_power_required": round(max_loss * adjusted_contracts, 2),
                        "account_risk_pct": round(max_loss * adjusted_contracts / account_size * 100, 2),
                        "size_multiplier": size_multiplier,
                        "sizing_method": position_sizing.get('sizing_method')
                    },

                    # Exit Rules
                    "exit_rules": exit_rules,

                    # Expected Move
                    "expected_move": expected_move,

                    # Greeks (if available)
                    "greeks": {
                        "position_delta": round((delta_strikes.get('short_delta', 0) or 0) * adjusted_contracts * 100, 2),
                        "position_theta": round((greeks.get('atm_call_theta', 0) or 0) * adjusted_contracts * 100, 2),
                    },

                    # Warnings
                    "warnings": all_warnings if all_warnings else ["✅ No liquidity warnings - Tier 1 underlying"]
                }

            # ============================================================
            # 3. COMBINED RESULT
            # ============================================================
            return {
                "ticker": ticker,
                "direction": direction,
                "current_price": current_price,
                "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "account_size": account_size,

                # IV Analysis Summary
                "iv_summary": {
                    "iv_rank": iv_rank,
                    "iv_percentile": iv_percentile,
                    "iv_environment": iv_analysis.get('iv_environment'),
                    "interpretation": iv_analysis.get('interpretation')
                },

                # Both Plans
                "stock_plan": stock_plan,
                "options_plan": options_plan,

                # Trade Decision - NOW WITH BUYER/SELLER DISTINCTION
                "recommendation": {
                    # Enhanced recommendation considering buyer vs seller
                    "primary": (
                        "SELL_PREMIUM" if near_earnings_selling_opportunity and iv_rank >= 50
                        else "OPTIONS" if options_selling_allowed and iv_rank >= 50
                        else "STOCK"
                    ),
                    "options_allowed": options_allowed,  # Legacy
                    "options_buying_allowed": options_buying_allowed,  # NEW
                    "options_selling_allowed": options_selling_allowed,  # NEW
                    "near_earnings_selling_opportunity": near_earnings_selling_opportunity,  # NEW
                    "liquidity_tier": liquidity_tier.get('tier'),
                    "days_to_earnings": days_to_earnings
                },

                # Seller Opportunities (highlighted when near earnings)
                "seller_opportunities": seller_opportunities,
                "earnings_strategies": earnings_strategies,

                # All Warnings
                "warnings": all_warnings,

                "methodology": "McMillan Options Strategy + TastyTrade 45 DTE / 50% Profit Management"
            }

        except Exception as e:
            logger.error(f"Error generating options trade plan for {ticker}: {e}")
            raise ValueError(f"Options trade plan generation failed: {str(e)}")



    @mcp.tool()
    def analyze_iv_skew(
        ticker: str,
        target_dte: int = 45,
        delta_levels: list[float] | None = None
    ) -> dict[str, Any]:
        """
        Analyze IV skew across the volatility surface.

        Calculates Put IV - Call IV at equidistant strikes (by delta) to measure
        market fear/greed and identify premium selling/buying opportunities.

        **IV Skew Types:**
        - **Put Skew (Normal)**: OTM puts more expensive than calls → market fear
        - **Flat Skew**: Puts ≈ Calls → neutral sentiment
        - **Inverted Skew**: OTM calls more expensive → unusual bullishness (meme stocks)

        **Trading Implications:**
        - **Steep Put Skew (>10pts)**: Sell put spreads (rich), avoid call spreads
        - **Normal Put Skew (3-10pts)**: Balanced, favor put credit spreads
        - **Flat Skew (0-3pts)**: Neutral, no skew edge
        - **Inverted Skew (<0pts)**: Sell call spreads (rich), unusual condition

        Args:
            ticker: Stock symbol
            target_dte: Target days to expiration (default 45)
            delta_levels: Delta levels to analyze (default [0.25, 0.15, 0.10])

        Returns:
            {
                "ticker": str,
                "expiry": str,
                "dte": int,
                "current_price": float,

                "skew_by_delta": {
                    "delta_25": {
                        "put_strike": float,
                        "put_iv": float,
                        "call_strike": float,
                        "call_iv": float,
                        "skew_absolute": float,  # Put IV - Call IV (percentage points)
                        "skew_relative_pct": float  # (Put IV - Call IV) / Call IV * 100
                    },
                    "delta_15": {...},
                    "delta_10": {...}
                },

                "skew_summary": {
                    "classification": str,  # STEEP_PUT_SKEW, NORMAL_PUT_SKEW, FLAT_SKEW, INVERTED_SKEW
                    "primary_skew": float,  # Delta-25 skew (most liquid)
                    "interpretation": str,
                    "sentiment_signal": str,  # BEARISH_FEAR, NEUTRAL, BULLISH_GREED
                    "skew_percentile": float  # Current skew vs 52-week range
                },

                "trading_implications": {
                    "recommended_adjustments": list[str],
                    "put_spread_edge": str,  # "Rich", "Fair", "Cheap"
                    "call_spread_edge": str,
                    "iron_condor_adjustment": str
                },

                "historical_context": {
                    "current_skew_percentile": float,
                    "52w_skew_high": float,
                    "52w_skew_low": float,
                    "avg_skew": float,
                    "note": str
                }
            }

        Reference: Natenberg - "Option Volatility and Pricing", Chapter 8: Volatility Skews
        """
        ticker = validate_ticker(ticker)

        if delta_levels is None:
            delta_levels = [0.25, 0.15, 0.10]  # 25-delta, 15-delta, 10-delta

        try:
            from datetime import datetime, timedelta
            import numpy as np

            # Get current price first
            t = yf.Ticker(ticker)
            current_price = t.info.get('currentPrice') or t.info.get('regularMarketPrice') or t.history(period='1d')['Close'].iloc[-1]

            # Try Questrade first (has Greeks already)
            calls_df = None
            puts_df = None
            closest_expiry = None
            options_source = "yfinance"

            try:
                from investor_agent.questrade import get_questrade_client
                from questrade_api import Questrade

                qt_client = get_questrade_client()
                symbol_info = qt_client.get_symbol_info(ticker)

                if symbol_info and symbol_info.get('symbols') and symbol_info['symbols'][0].get('hasOptions'):
                    symbol_id = symbol_info['symbols'][0]['symbolId']

                    q = Questrade()
                    qt_options = q.symbol_options(symbol_id)

                    if qt_options and qt_options.get('optionChain'):
                        # Find expiration closest to target DTE
                        target_date = datetime.now() + timedelta(days=target_dte)
                        exp_dates = [exp['expiryDate'][:10] for exp in qt_options['optionChain']]

                        if exp_dates:
                            closest_expiry = min(exp_dates, key=lambda x: abs(
                                (datetime.strptime(x, '%Y-%m-%d') - target_date).days
                            ))

                            # Get the chain for nearest expiration
                            for exp in qt_options['optionChain']:
                                if exp['expiryDate'].startswith(closest_expiry):
                                    calls_data = []
                                    puts_data = []

                                    for root in exp.get('chainPerRoot', []):
                                        for strike_info in root.get('chainPerStrikePrice', []):
                                            strike = strike_info['strikePrice']
                                            call_id = strike_info.get('callSymbolId')
                                            put_id = strike_info.get('putSymbolId')

                                            try:
                                                if call_id:
                                                    call_quotes = q.markets_options(optionIds=[call_id])
                                                    if call_quotes and call_quotes.get('optionQuotes'):
                                                        cq = call_quotes['optionQuotes'][0]
                                                        calls_data.append({
                                                            'strike': strike,
                                                            'impliedVolatility': cq.get('volatility') or 0.3,
                                                            'delta': cq.get('delta') or 0
                                                        })
                                                if put_id:
                                                    put_quotes = q.markets_options(optionIds=[put_id])
                                                    if put_quotes and put_quotes.get('optionQuotes'):
                                                        pq = put_quotes['optionQuotes'][0]
                                                        puts_data.append({
                                                            'strike': strike,
                                                            'impliedVolatility': pq.get('volatility') or 0.3,
                                                            'delta': pq.get('delta') or 0
                                                        })
                                            except Exception:
                                                pass

                                    if calls_data or puts_data:
                                        temp_calls_df = pd.DataFrame(calls_data) if calls_data else pd.DataFrame()
                                        temp_puts_df = pd.DataFrame(puts_data) if puts_data else pd.DataFrame()

                                        # Validate strikes are reasonable
                                        all_strikes = []
                                        if not temp_calls_df.empty:
                                            all_strikes.extend(temp_calls_df['strike'].tolist())
                                        if not temp_puts_df.empty:
                                            all_strikes.extend(temp_puts_df['strike'].tolist())

                                        if all_strikes:
                                            atm_strikes = [s for s in all_strikes if 0.8 * current_price <= s <= 1.2 * current_price]
                                            if atm_strikes:
                                                calls_df = temp_calls_df
                                                puts_df = temp_puts_df
                                                options_source = "questrade"
                                                logger.info(f"Using Questrade options data with Greeks for {ticker} IV skew analysis")
                                    break
            except Exception as qt_err:
                logger.warning(f"Questrade options unavailable for {ticker} IV skew: {qt_err}")

            # Fall back to yfinance if Questrade didn't work
            if calls_df is None or (calls_df.empty if hasattr(calls_df, 'empty') else True):
                logger.info(f"Falling back to yfinance for {ticker} IV skew analysis")
                expirations = t.options
                if not expirations:
                    raise ValueError(f"No options available for {ticker}")

                target_date = datetime.now() + timedelta(days=target_dte)
                closest_expiry = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))

                calls_df, puts_df = _fetch_yf_option_chain(t, closest_expiry)
                options_source = "yfinance"

            # Calculate DTE
            expiry_dt = datetime.strptime(closest_expiry, '%Y-%m-%d')
            dte = (expiry_dt - datetime.now()).days
            T = dte / 365
            r = 0.05

            # If using yfinance (no delta), calculate it with Black-Scholes
            if options_source == "yfinance":
                if not puts_df.empty:
                    puts_df_copy = puts_df.copy()
                    puts_df_copy['delta'] = puts_df_copy.apply(
                        lambda row: _calculate_black_scholes_greeks(
                            S=current_price,
                            K=row['strike'],
                            T=T,
                            r=r,
                            sigma=row['impliedVolatility'],
                            option_type='put'
                        )['delta'],
                        axis=1
                    )
                else:
                    puts_df_copy = puts_df

                if not calls_df.empty:
                    calls_df_copy = calls_df.copy()
                    calls_df_copy['delta'] = calls_df_copy.apply(
                        lambda row: _calculate_black_scholes_greeks(
                            S=current_price,
                            K=row['strike'],
                            T=T,
                            r=r,
                            sigma=row['impliedVolatility'],
                            option_type='call'
                        )['delta'],
                        axis=1
                    )
                else:
                    calls_df_copy = calls_df
            else:
                # Questrade already has delta
                puts_df_copy = puts_df.copy() if not puts_df.empty else puts_df
                calls_df_copy = calls_df.copy() if not calls_df.empty else calls_df

            # Calculate skew at each delta level
            skew_by_delta = {}

            for target_delta in delta_levels:
                delta_key = f"delta_{int(target_delta * 100)}"

                # Find put with target delta (puts have negative delta)
                if not puts_df_copy.empty and 'delta' in puts_df_copy.columns:
                    puts_df_copy['delta_diff'] = abs(abs(puts_df_copy['delta']) - target_delta)
                    best_put = puts_df_copy.nsmallest(1, 'delta_diff').iloc[0]

                    put_strike = float(best_put['strike'])
                    put_iv = float(best_put.get('impliedVolatility', 0))

                    # Normalize IV to percentage if needed
                    if put_iv > 0 and put_iv < 5:
                        put_iv = put_iv * 100  # Convert decimal to percentage
                else:
                    put_strike = None
                    put_iv = None

                # Find call with target delta (calls have positive delta)
                if not calls_df_copy.empty and 'delta' in calls_df_copy.columns:
                    calls_df_copy['delta_diff'] = abs(calls_df_copy['delta'] - target_delta)
                    best_call = calls_df_copy.nsmallest(1, 'delta_diff').iloc[0]

                    call_strike = float(best_call['strike'])
                    call_iv = float(best_call.get('impliedVolatility', 0))

                    # Normalize IV to percentage if needed
                    if call_iv > 0 and call_iv < 5:
                        call_iv = call_iv * 100  # Convert decimal to percentage
                else:
                    call_strike = None
                    call_iv = None

                # Calculate skew
                if put_iv is not None and call_iv is not None and call_iv > 0:
                    skew_absolute = put_iv - call_iv
                    skew_relative_pct = (skew_absolute / call_iv) * 100
                else:
                    skew_absolute = None
                    skew_relative_pct = None

                skew_by_delta[delta_key] = {
                    "put_strike": put_strike,
                    "put_iv": round(put_iv, 2) if put_iv else None,
                    "call_strike": call_strike,
                    "call_iv": round(call_iv, 2) if call_iv else None,
                    "skew_absolute": round(skew_absolute, 2) if skew_absolute is not None else None,
                    "skew_relative_pct": round(skew_relative_pct, 2) if skew_relative_pct is not None else None
                }

            # Classify skew using 25-delta (most liquid)
            primary_skew = skew_by_delta.get('delta_25', {}).get('skew_absolute')

            if primary_skew is None:
                classification = "INSUFFICIENT_DATA"
                sentiment_signal = "NEUTRAL"
                interpretation = "Insufficient options data for skew analysis"
            elif primary_skew > 10:
                classification = "STEEP_PUT_SKEW"
                sentiment_signal = "BEARISH_FEAR"
                interpretation = f"Steep put skew ({primary_skew:.1f} pts) indicates elevated fear premium. Put spreads are RICH - excellent for selling."
            elif primary_skew > 3:
                classification = "NORMAL_PUT_SKEW"
                sentiment_signal = "MODERATE_FEAR"
                interpretation = f"Normal put skew ({primary_skew:.1f} pts) reflects typical equity fear premium. Balanced environment for credit spreads."
            elif primary_skew > 0:
                classification = "FLAT_SKEW"
                sentiment_signal = "NEUTRAL"
                interpretation = f"Flat skew ({primary_skew:.1f} pts) shows minimal put/call IV difference. No significant skew edge."
            else:
                classification = "INVERTED_SKEW"
                sentiment_signal = "BULLISH_GREED"
                interpretation = f"Inverted skew ({primary_skew:.1f} pts) - calls more expensive than puts. UNUSUAL condition, often seen in meme stocks. Call spreads are RICH."

            # Trading implications
            if primary_skew is not None:
                if primary_skew > 8:
                    put_spread_edge = "Rich"
                    call_spread_edge = "Cheap"
                    recommended_adjustments = [
                        "Favor selling put credit spreads (inflated premium)",
                        "Widen put spread width to capture extra premium",
                        "Move put short strike closer to ATM for higher credit",
                        "Avoid buying call spreads (relatively cheap but still disadvantaged)"
                    ]
                    ic_adjustment = "Widen put spread or move put short strike up to capture put skew premium"
                elif primary_skew > 3:
                    put_spread_edge = "Fair-to-Rich"
                    call_spread_edge = "Fair"
                    recommended_adjustments = [
                        "Put credit spreads slightly favored",
                        "Iron condors balanced but slight put premium edge",
                        "Standard 16-delta strikes appropriate"
                    ]
                    ic_adjustment = "Balanced iron condor - slight edge to collecting more on put side"
                elif primary_skew > 0:
                    put_spread_edge = "Fair"
                    call_spread_edge = "Fair"
                    recommended_adjustments = [
                        "No skew edge - use IV rank for strategy selection",
                        "Focus on directional bias over skew considerations"
                    ]
                    ic_adjustment = "Symmetric iron condor - no skew adjustment needed"
                else:  # Inverted
                    put_spread_edge = "Cheap"
                    call_spread_edge = "Rich"
                    recommended_adjustments = [
                        "UNUSUAL: Favor selling call credit spreads (inflated premium)",
                        "Avoid put spreads (relatively underpriced)",
                        "Monitor for meme stock behavior or event-driven distortion",
                        "Consider this an anomaly - proceed with caution"
                    ]
                    ic_adjustment = "Widen call spread or move call short strike down to capture call skew premium (rare scenario)"
            else:
                put_spread_edge = "Unknown"
                call_spread_edge = "Unknown"
                recommended_adjustments = ["Insufficient data for skew-based recommendations"]
                ic_adjustment = "Unable to analyze - insufficient options data"

            # Historical context (simplified - using current as proxy for historical range)
            # In production, would track skew history in database
            if primary_skew is not None:
                # Estimate historical range based on skew type
                if classification == "STEEP_PUT_SKEW":
                    skew_percentile = 85  # High end
                    avg_skew = 6.5
                    skew_high_52w = primary_skew + 3
                    skew_low_52w = 2.0
                elif classification == "NORMAL_PUT_SKEW":
                    skew_percentile = 55  # Mid range
                    avg_skew = 5.5
                    skew_high_52w = 11.0
                    skew_low_52w = 1.5
                elif classification == "FLAT_SKEW":
                    skew_percentile = 25  # Low end
                    avg_skew = 4.0
                    skew_high_52w = 9.0
                    skew_low_52w = 0.0
                else:  # Inverted
                    skew_percentile = 5  # Very low (unusual)
                    avg_skew = 3.5
                    skew_high_52w = 8.0
                    skew_low_52w = primary_skew - 2
            else:
                skew_percentile = 50
                avg_skew = 5.0
                skew_high_52w = 10.0
                skew_low_52w = 0.0

            return {
                "ticker": ticker,
                "expiry": closest_expiry,
                "dte": dte,
                "current_price": round(current_price, 2),

                "skew_by_delta": skew_by_delta,

                "skew_summary": {
                    "classification": classification,
                    "primary_skew": round(primary_skew, 2) if primary_skew is not None else None,
                    "interpretation": interpretation,
                    "sentiment_signal": sentiment_signal,
                    "skew_percentile": round(skew_percentile, 1)
                },

                "trading_implications": {
                    "recommended_adjustments": recommended_adjustments,
                    "put_spread_edge": put_spread_edge,
                    "call_spread_edge": call_spread_edge,
                    "iron_condor_adjustment": ic_adjustment
                },

                "historical_context": {
                    "current_skew_percentile": round(skew_percentile, 1),
                    "52w_skew_high": round(skew_high_52w, 1),
                    "52w_skew_low": round(skew_low_52w, 1),
                    "avg_skew": round(avg_skew, 1),
                    "note": "Historical context estimated from current classification (production version would use database)"
                },

                "methodology": "Natenberg - Option Volatility and Pricing, Chapter 8: Volatility Skews"
            }

        except Exception as e:
            logger.error(f"Error analyzing IV skew for {ticker}: {e}")
            raise ValueError(f"IV skew analysis failed: {str(e)}")


    @mcp.tool()
    def analyze_iv_term_structure(
        ticker: str,
        expirations_to_analyze: int = 4
    ) -> dict[str, Any]:
        """
        Analyze IV term structure across multiple expirations.

        Detects contango (normal) vs backwardation (stress) conditions to guide
        calendar spread and diagonal strategies.

        **Term Structure Patterns:**
        - **Contango (Normal)**: Far-term IV > Near-term IV → Calendar spreads profitable
        - **Backwardation (Stress)**: Near-term IV > Far-term IV → Reduce premium selling
        - **Flat**: Near-term ≈ Far-term → Neutral

        **Trading Implications:**
        - **Contango**: Calendar spreads collect theta differential, favorable environment
        - **Backwardation**: Market stress, avoid calendars, reduce premium selling
        - **Flat**: No term structure edge

        Args:
            ticker: Stock symbol
            expirations_to_analyze: Number of expirations to analyze (default 4)

        Returns:
            {
                "ticker": str,
                "current_price": float,

                "term_structure": [
                    {
                        "expiry": str,
                        "dte": int,
                        "atm_iv": float,
                        "iv_percentile": float
                    },
                    ...
                ],

                "structure_classification": str,  # CONTANGO, BACKWARDATION, FLAT
                "slope": float,  # Positive = contango, negative = backwardation
                "interpretation": str,

                "calendar_spread_signal": str,  # FAVORABLE, NEUTRAL, UNFAVORABLE
                "diagonal_spread_signal": str,

                "recommended_strategies": list[str],
                "warnings": list[str]
            }

        Reference: McMillan - "Options as a Strategic Investment", Chapter 30: Volatility Trading
        """
        ticker = validate_ticker(ticker)

        try:
            from datetime import datetime, timedelta
            import numpy as np

            # Get current price
            t = yf.Ticker(ticker)
            current_price = t.info.get('currentPrice') or t.info.get('regularMarketPrice') or t.history(period='1d')['Close'].iloc[-1]

            term_structure = []
            options_source = "yfinance"

            # Try Questrade first (has Greeks and IV)
            try:
                from investor_agent.questrade import get_questrade_client
                from questrade_api import Questrade

                qt_client = get_questrade_client()
                symbol_info = qt_client.get_symbol_info(ticker)

                if symbol_info and symbol_info.get('symbols') and symbol_info['symbols'][0].get('hasOptions'):
                    symbol_id = symbol_info['symbols'][0]['symbolId']

                    q = Questrade()
                    qt_options = q.symbol_options(symbol_id)

                    if qt_options and qt_options.get('optionChain'):
                        # Get up to requested number of expirations
                        expirations_data = qt_options['optionChain'][:expirations_to_analyze]

                        for exp in expirations_data:
                            exp_str = exp['expiryDate'][:10]
                            expiry_dt = datetime.strptime(exp_str, '%Y-%m-%d')
                            dte = (expiry_dt - datetime.now()).days

                            # Get ATM IV from this expiration
                            atm_iv = None
                            for root in exp.get('chainPerRoot', []):
                                for strike_info in root.get('chainPerStrikePrice', []):
                                    strike = strike_info['strikePrice']

                                    # Check if this is ATM (within 5% of current price)
                                    if 0.95 * current_price <= strike <= 1.05 * current_price:
                                        call_id = strike_info.get('callSymbolId')

                                        if call_id:
                                            try:
                                                call_quotes = q.markets_options(optionIds=[call_id])
                                                if call_quotes and call_quotes.get('optionQuotes'):
                                                    cq = call_quotes['optionQuotes'][0]
                                                    iv = cq.get('volatility') or 0
                                                    if iv > 0:
                                                        atm_iv = round(iv * 100, 2) if iv < 5 else round(iv, 2)
                                                        break
                                            except Exception:
                                                pass

                                if atm_iv:
                                    break

                            if atm_iv:
                                term_structure.append({
                                    "expiry": exp_str,
                                    "dte": dte,
                                    "atm_iv": atm_iv,
                                    "iv_percentile": 50
                                })

                        if len(term_structure) >= 2:
                            options_source = "questrade"
                            logger.info(f"Using Questrade options data for {ticker} term structure analysis")

            except Exception as qt_err:
                logger.warning(f"Questrade options unavailable for {ticker} term structure: {qt_err}")

            # Fall back to yfinance if Questrade didn't work
            if len(term_structure) < 2:
                logger.info(f"Falling back to yfinance for {ticker} term structure analysis")
                expirations = t.options
                if not expirations or len(expirations) < 2:
                    raise ValueError(f"Insufficient expirations for term structure analysis ({len(expirations) if expirations else 0} available)")

                # Limit to requested number
                expirations = expirations[:min(expirations_to_analyze, len(expirations))]

                term_structure = []

                # Analyze each expiration
                for exp_str in expirations:
                    calls_df, puts_df = _fetch_yf_option_chain(t, exp_str)

                    if calls_df.empty and puts_df.empty:
                        continue

                    # Calculate DTE
                    expiry_dt = datetime.strptime(exp_str, '%Y-%m-%d')
                    dte = (expiry_dt - datetime.now()).days

                    # Find ATM options (closest to current price)
                    atm_iv = None

                    if not calls_df.empty:
                        calls_df_copy = calls_df.copy()
                        calls_df_copy['distance'] = abs(calls_df_copy['strike'] - current_price)
                        atm_call = calls_df_copy.nsmallest(1, 'distance').iloc[0]
                        call_iv = float(atm_call.get('impliedVolatility', 0))

                        # Normalize to percentage
                        if call_iv > 0 and call_iv < 5:
                            call_iv = call_iv * 100

                        atm_iv = call_iv

                    if not puts_df.empty and atm_iv is None:
                        puts_df_copy = puts_df.copy()
                        puts_df_copy['distance'] = abs(puts_df_copy['strike'] - current_price)
                        atm_put = puts_df_copy.nsmallest(1, 'distance').iloc[0]
                        put_iv = float(atm_put.get('impliedVolatility', 0))

                        if put_iv > 0 and put_iv < 5:
                            put_iv = put_iv * 100

                        atm_iv = put_iv

                    if atm_iv:
                        term_structure.append({
                            "expiry": exp_str,
                            "dte": dte,
                            "atm_iv": round(atm_iv, 2),
                            "iv_percentile": 50  # Simplified - would need historical data
                        })

            if len(term_structure) < 2:
                raise ValueError("Insufficient valid expirations for term structure analysis")

            # Sort by DTE
            term_structure.sort(key=lambda x: x['dte'])

            # Calculate slope (linear regression of IV vs DTE)
            dtes = [x['dte'] for x in term_structure]
            ivs = [x['atm_iv'] for x in term_structure]

            # Simple slope: (far_iv - near_iv) / (far_dte - near_dte)
            near_iv = term_structure[0]['atm_iv']
            far_iv = term_structure[-1]['atm_iv']
            near_dte = term_structure[0]['dte']
            far_dte = term_structure[-1]['dte']

            slope = (far_iv - near_iv) / (far_dte - near_dte) if far_dte > near_dte else 0

            # Classify structure
            iv_diff = far_iv - near_iv

            if iv_diff > 2:  # Far-term IV at least 2 points higher
                structure_classification = "CONTANGO"
                interpretation = f"Contango term structure (far-term IV {far_iv:.1f}% > near-term IV {near_iv:.1f}%). Normal market condition - calendar spreads favorable."
                calendar_signal = "FAVORABLE"
                diagonal_signal = "FAVORABLE"
                recommended_strategies = [
                    "Calendar spreads (sell near-term, buy far-term)",
                    "Diagonal spreads for directional theta capture",
                    "Double calendars for range-bound strategies"
                ]
                warnings = []

            elif iv_diff < -2:  # Near-term IV at least 2 points higher
                structure_classification = "BACKWARDATION"
                interpretation = f"Backwardation term structure (near-term IV {near_iv:.1f}% > far-term IV {far_iv:.1f}%). MARKET STRESS DETECTED - reduce premium selling, avoid calendars."
                calendar_signal = "UNFAVORABLE"
                diagonal_signal = "UNFAVORABLE"
                recommended_strategies = [
                    "Reduce or close calendar spreads",
                    "Focus on directional strategies",
                    "Consider volatility spike protective trades"
                ]
                warnings = [
                    "⚠️ BACKWARDATION INDICATES MARKET STRESS",
                    "Near-term volatility elevated - potential event or crisis",
                    "Avoid premium selling strategies until structure normalizes",
                    "Monitor for mean reversion to contango"
                ]

            else:  # Flat structure
                structure_classification = "FLAT"
                interpretation = f"Flat term structure (near-term IV {near_iv:.1f}% ≈ far-term IV {far_iv:.1f}%). No significant term structure edge."
                calendar_signal = "NEUTRAL"
                diagonal_signal = "NEUTRAL"
                recommended_strategies = [
                    "No term structure advantage",
                    "Focus on IV rank and directional bias instead",
                    "Consider vertical spreads over calendars"
                ]
                warnings = []

            return {
                "ticker": ticker,
                "current_price": round(current_price, 2),

                "term_structure": term_structure,

                "structure_classification": structure_classification,
                "slope": round(slope, 4),
                "interpretation": interpretation,

                "calendar_spread_signal": calendar_signal,
                "diagonal_spread_signal": diagonal_signal,

                "recommended_strategies": recommended_strategies,
                "warnings": warnings,

                "methodology": "McMillan - Options as a Strategic Investment, Chapter 30: Volatility Trading"
            }

        except Exception as e:
            logger.error(f"Error analyzing IV term structure for {ticker}: {e}")
            raise ValueError(f"IV term structure analysis failed: {str(e)}")


    @mcp.tool()
    def calculate_vanna(
        ticker: str,
        strike: float,
        expiry: str,
        option_type: str = "call"
    ) -> dict[str, Any]:
        """
        Calculate Vanna (∂Delta/∂IV) for a single option.

        Vanna measures how delta changes when IV changes - critical for earnings trades.

        **Use Case:**
        Before earnings: IV = 60%, after earnings: IV = 40% (20 point drop)
        If Vanna = -0.15, delta will change by: -0.15 × -20 = +3.0 delta
        You need to sell 300 shares to rehedge (if 100 contracts).

        Args:
            ticker: Stock symbol
            strike: Option strike price
            expiry: Expiration date (YYYY-MM-DD)
            option_type: 'call' or 'put'

        Returns:
            {
                "ticker": str,
                "strike": float,
                "expiry": str,
                "option_type": str,
                "current_price": float,
                "current_iv": float,
                "dte": int,

                "vanna": float,  # Change in delta per 1 point IV change
                "charm": float,  # Daily delta decay

                "interpretation": {
                    "vanna_meaning": str,
                    "iv_sensitivity": str,
                    "earnings_impact": {
                        "iv_drop_10pts": {"delta_change": float, "hedging_shares": int},
                        "iv_drop_20pts": {"delta_change": float, "hedging_shares": int}
                    }
                }
            }

        Example:
            calculate_vanna("NFLX", 500, "2026-02-21", "call")
            → Shows how delta changes if IV crashes after earnings
        """
        ticker = validate_ticker(ticker)

        try:
            from datetime import datetime
            import numpy as np

            # Get current price
            t = yf.Ticker(ticker)
            current_price = t.info.get('currentPrice') or t.info.get('regularMarketPrice') or t.history(period='1d')['Close'].iloc[-1]

            # Get option chain for this expiration
            calls_df, puts_df = _fetch_yf_option_chain(t, expiry)
            options_df = calls_df if option_type.lower() == 'call' else puts_df

            # Find this strike
            strike_data = options_df[options_df['strike'] == strike]
            if strike_data.empty:
                raise ValueError(f"Strike {strike} not found for {expiry}")

            option_data = strike_data.iloc[0]
            current_iv = float(option_data.get('impliedVolatility', 0))

            # Normalize IV to decimal if needed
            if current_iv > 5:
                current_iv = current_iv / 100

            # Calculate DTE
            expiry_dt = datetime.strptime(expiry, '%Y-%m-%d')
            dte = (expiry_dt - datetime.now()).days
            T = dte / 365
            r = 0.05

            # Calculate Vanna and Charm
            vanna = _calculate_vanna(current_price, strike, T, r, current_iv, option_type)
            charm = _calculate_charm(current_price, strike, T, r, current_iv, option_type)

            # Calculate earnings impact scenarios
            iv_drop_10 = vanna * -10  # 10 point IV drop
            iv_drop_20 = vanna * -20  # 20 point IV drop

            # Vanna interpretation
            if abs(vanna) > 0.10:
                vanna_meaning = "HIGH Vanna - Very sensitive to IV changes"
            elif abs(vanna) > 0.05:
                vanna_meaning = "MODERATE Vanna - Moderately sensitive to IV"
            else:
                vanna_meaning = "LOW Vanna - Minimal IV sensitivity"

            if vanna < 0:
                iv_sensitivity = "LONG option - Delta DECREASES when IV drops (IV crush hurts you)"
            else:
                iv_sensitivity = "SHORT option - Delta INCREASES when IV drops (IV crush helps you)"

            return {
                "ticker": ticker,
                "strike": strike,
                "expiry": expiry,
                "option_type": option_type,
                "current_price": round(current_price, 2),
                "current_iv": round(current_iv * 100, 2),
                "dte": dte,

                "vanna": vanna,
                "charm": charm,

                "interpretation": {
                    "vanna_meaning": vanna_meaning,
                    "iv_sensitivity": iv_sensitivity,
                    "earnings_impact": {
                        "iv_drop_10pts": {
                            "delta_change": round(iv_drop_10, 4),
                            "hedging_shares": int(iv_drop_10 * 100)  # Per 1 contract
                        },
                        "iv_drop_20pts": {
                            "delta_change": round(iv_drop_20, 4),
                            "hedging_shares": int(iv_drop_20 * 100)
                        }
                    }
                },

                "methodology": "Taleb - Dynamic Hedging, Chapter 9: Second-Order Greeks"
            }

        except Exception as e:
            logger.error(f"Error calculating vanna for {ticker}: {e}")
            raise ValueError(f"Vanna calculation failed: {str(e)}")


    @mcp.tool()
    def analyze_expiration_charm(
        ticker: str,
        expiration: str
    ) -> dict[str, Any]:
        """
        Analyze Charm exposure into options expiration.

        **Uses Questrade as primary data source** for options chain and Greeks.

        **What is Charm?**
        Charm = ∂Delta/∂Time (delta decay over time)

        Predicts dealer rehedging flows as time decay changes delta positioning.
        Used to predict Friday EOD "pin" to strikes with max open interest.

        **Why It Matters:**
        - ATM options have highest charm (delta decays fastest)
        - Dealers must rehedge as delta changes
        - Creates predictable flows into expiration
        - Explains Friday EOD "pin" to strikes with max OI

        Args:
            ticker: Stock symbol
            expiration: Expiration date (YYYY-MM-DD format)

        Returns:
            {
                "ticker": str,
                "expiration": str,
                "dte": int,
                "current_price": float,

                "charm_by_strike": [
                    {
                        "strike": float,
                        "total_oi": int,
                        "call_oi": int,
                        "put_oi": int,
                        "call_charm": float,
                        "put_charm": float,
                        "net_charm": float,  # Aggregate charm weighted by OI
                        "dealer_flow_direction": str  # BUY, SELL, NEUTRAL
                    },
                    ...
                ],

                "pin_prediction": {
                    "most_likely_pin_strike": float,
                    "confidence": str,  # HIGH, MEDIUM, LOW
                    "reason": str,
                    "charm_magnitude": float
                },

                "dealer_flow_summary": {
                    "total_call_charm": float,
                    "total_put_charm": float,
                    "net_charm": float,
                    "expected_direction": str  # BUY or SELL pressure
                },

                "risk_level": str,  # LOW, MODERATE, HIGH
                "warnings": list[str]
            }

        Example:
            analyze_expiration_charm("SPY", "2026-01-23")
            → Predicts Friday EOD pin to strike with max OI

        Reference: Hull - "Options, Futures, and Other Derivatives", Chapter 19
        """
        ticker = validate_ticker(ticker)

        try:
            from datetime import datetime
            import numpy as np
            import pandas as pd

            # Get current price using Questrade-first helper
            current_price = _get_current_price(ticker)

            # Calculate DTE
            expiry_dt = datetime.strptime(expiration, '%Y-%m-%d')
            dte = (expiry_dt - datetime.now()).days

            if dte < 0:
                raise ValueError(f"Expiration {expiration} is in the past")

            T = dte / 365
            r = 0.05  # Risk-free rate

            # Try Questrade first (has Greeks and open interest)
            charm_by_strike = []
            use_questrade = False

            try:
                from investor_agent.questrade import get_questrade_client
                from questrade_api import Questrade

                logger.info(f"Charm: Starting Questrade path for {ticker}")

                # Get symbol info
                qt_client = get_questrade_client()
                symbol_info = qt_client.get_symbol_info(ticker)

                if not symbol_info or not symbol_info.get('symbols'):
                    raise ValueError(f"Symbol {ticker} not found in Questrade")

                symbol_id = symbol_info['symbols'][0]['symbolId']
                logger.info(f"Charm: Got symbol info: {symbol_id}, price={current_price}")

                # Use raw Questrade API for options chain
                q = Questrade()
                qt_options = q.symbol_options(symbol_id)
                logger.info(f"Charm: Retrieved options chain from Questrade")

                if not qt_options or 'optionChain' not in qt_options:
                    raise ValueError(f"No options chain available for {ticker}")

                # Find the matching expiration
                expirations_list = qt_options['optionChain']
                if not expirations_list:
                    raise ValueError(f"No expirations available for {ticker}")

                # Select expiration closest to requested date
                target_exp = datetime.strptime(expiration, '%Y-%m-%d').date()
                selected_exp_obj = min(expirations_list, key=lambda x: abs((datetime.strptime(x['expiryDate'], '%Y-%m-%dT%H:%M:%S.%f%z').date() - target_exp).days))

                expiration_str = datetime.strptime(selected_exp_obj['expiryDate'], '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%d')
                expiry_dt = datetime.strptime(expiration_str, '%Y-%m-%d')
                dte = (expiry_dt - datetime.now()).days
                T = dte / 365

                # Collect all option IDs from the selected expiration
                option_ids = []
                for root_data in selected_exp_obj['chainPerRoot']:
                    for strike_data in root_data['chainPerStrikePrice']:
                        if 'callSymbolId' in strike_data and strike_data['callSymbolId']:
                            option_ids.append(strike_data['callSymbolId'])
                        if 'putSymbolId' in strike_data and strike_data['putSymbolId']:
                            option_ids.append(strike_data['putSymbolId'])

                logger.info(f"Charm: Collected {len(option_ids)} option IDs for {ticker} {expiration_str}")

                if len(option_ids) == 0:
                    raise ValueError(f"No option IDs found for {ticker} {expiration_str}")

                # Get quotes with Greeks in batches
                all_quotes = []
                batch_size = 100
                for i in range(0, len(option_ids), batch_size):
                    batch = option_ids[i:i+batch_size]
                    logger.info(f"Charm: Fetching batch {i//batch_size + 1} of {(len(option_ids)-1)//batch_size + 1} ({len(batch)} options)")
                    quotes = q.markets_options(optionIds=batch)
                    if quotes and 'optionQuotes' in quotes:
                        all_quotes.extend(quotes['optionQuotes'])
                        logger.info(f"Charm: Got {len(quotes['optionQuotes'])} quotes in this batch")

                logger.info(f"Charm: Total quotes retrieved: {len(all_quotes)}")

                # Build charm profile by strike
                strike_data = {}  # {strike: {'call_oi': ..., 'call_charm': ..., 'put_oi': ..., 'put_charm': ..., 'call_iv': ..., 'put_iv': ...}}

                for quote in all_quotes:
                    # Parse Questrade symbol format: "SPY20Feb26C335.00" or "SPY20Feb26P335.00"
                    symbol = quote['symbol']

                    # Find the rightmost C or P in the symbol
                    c_pos = symbol.rfind('C')
                    p_pos = symbol.rfind('P')

                    if c_pos > p_pos and c_pos != -1:
                        # Call option
                        is_call = True
                        strike_part = symbol[c_pos+1:]
                    elif p_pos > c_pos and p_pos != -1:
                        # Put option
                        is_call = False
                        strike_part = symbol[p_pos+1:]
                    else:
                        # Can't parse - skip
                        continue

                    strike = float(strike_part)
                    open_interest = quote.get('openInterest', 0) or 0
                    iv = quote.get('volatility', 0) or 0

                    # Normalize IV to decimal if needed
                    if iv > 5:
                        iv = iv / 100

                    if iv <= 0 or T <= 0:
                        continue

                    # Calculate charm for this option
                    option_type = 'call' if is_call else 'put'
                    charm = _calculate_charm(current_price, strike, T, r, iv, option_type)

                    if strike not in strike_data:
                        strike_data[strike] = {
                            'call_oi': 0, 'call_charm': 0, 'call_iv': 0,
                            'put_oi': 0, 'put_charm': 0, 'put_iv': 0
                        }

                    if is_call:
                        strike_data[strike]['call_oi'] = open_interest
                        strike_data[strike]['call_charm'] = charm
                        strike_data[strike]['call_iv'] = iv
                    else:
                        strike_data[strike]['put_oi'] = open_interest
                        strike_data[strike]['put_charm'] = charm
                        strike_data[strike]['put_iv'] = iv

                # Convert to sorted list and calculate aggregate charm
                for strike in sorted(strike_data.keys()):
                    data = strike_data[strike]
                    call_oi = data['call_oi']
                    put_oi = data['put_oi']
                    call_charm = data['call_charm']
                    put_charm = data['put_charm']

                    # Calculate net charm weighted by open interest
                    # Dealers are SHORT options, so their charm is opposite sign
                    net_charm_retail = (call_oi * call_charm) + (put_oi * put_charm)
                    net_charm_dealer = -net_charm_retail  # Dealers are opposite side

                    # Determine dealer flow direction
                    if abs(net_charm_dealer) < 0.01:
                        flow_direction = "NEUTRAL"
                    elif net_charm_dealer > 0:
                        flow_direction = "BUY"  # Dealer needs to buy shares as time decays
                    else:
                        flow_direction = "SELL"  # Dealer needs to sell shares

                    charm_by_strike.append({
                        "strike": strike,
                        "total_oi": call_oi + put_oi,
                        "call_oi": call_oi,
                        "put_oi": put_oi,
                        "call_charm": round(call_charm, 6),
                        "put_charm": round(put_charm, 6),
                        "net_charm": round(net_charm_dealer, 4),
                        "dealer_flow_direction": flow_direction,
                        "distance_from_spot_pct": round((strike - current_price) / current_price * 100, 2)
                    })

                use_questrade = True
                logger.info(f"Charm: Successfully processed {len(charm_by_strike)} strikes from Questrade")

            except Exception as qt_error:
                logger.warning(f"Charm: Questrade failed ({qt_error}), falling back to yfinance")
                use_questrade = False

            # Fallback to yfinance if Questrade failed
            if not use_questrade or not charm_by_strike:
                import yfinance as yf

                calls_df, puts_df = _fetch_yf_option_chain(ticker, expiration)

                # Merge by strike
                all_strikes = sorted(set(calls_df['strike'].tolist() + puts_df['strike'].tolist()))

                for strike in all_strikes:
                    call_data = calls_df[calls_df['strike'] == strike]
                    put_data = puts_df[puts_df['strike'] == strike]

                    call_oi = int(call_data['openInterest'].iloc[0]) if not call_data.empty else 0
                    put_oi = int(put_data['openInterest'].iloc[0]) if not put_data.empty else 0

                    call_iv = float(call_data['impliedVolatility'].iloc[0]) if not call_data.empty else 0
                    put_iv = float(put_data['impliedVolatility'].iloc[0]) if not put_data.empty else 0

                    # Normalize IV
                    if call_iv > 5:
                        call_iv = call_iv / 100
                    if put_iv > 5:
                        put_iv = put_iv / 100

                    # Calculate charm
                    call_charm = _calculate_charm(current_price, strike, T, r, call_iv, 'call') if call_iv > 0 else 0
                    put_charm = _calculate_charm(current_price, strike, T, r, put_iv, 'put') if put_iv > 0 else 0

                    # Net charm weighted by OI (dealer side)
                    net_charm_retail = (call_oi * call_charm) + (put_oi * put_charm)
                    net_charm_dealer = -net_charm_retail

                    if abs(net_charm_dealer) < 0.01:
                        flow_direction = "NEUTRAL"
                    elif net_charm_dealer > 0:
                        flow_direction = "BUY"
                    else:
                        flow_direction = "SELL"

                    charm_by_strike.append({
                        "strike": strike,
                        "total_oi": call_oi + put_oi,
                        "call_oi": call_oi,
                        "put_oi": put_oi,
                        "call_charm": round(call_charm, 6),
                        "put_charm": round(put_charm, 6),
                        "net_charm": round(net_charm_dealer, 4),
                        "dealer_flow_direction": flow_direction,
                        "distance_from_spot_pct": round((strike - current_price) / current_price * 100, 2)
                    })

            if not charm_by_strike:
                raise ValueError("No charm data available for this expiration")

            # Calculate summary statistics
            total_call_charm = sum(s['call_oi'] * s['call_charm'] for s in charm_by_strike)
            total_put_charm = sum(s['put_oi'] * s['put_charm'] for s in charm_by_strike)
            net_charm = total_call_charm + total_put_charm

            # Predict pin: strike with max OI and significant charm (near ATM)
            # Filter to strikes within 10% of current price
            atm_strikes = [s for s in charm_by_strike if abs(s['distance_from_spot_pct']) < 10]

            if not atm_strikes:
                atm_strikes = charm_by_strike  # Fallback to all strikes

            # Find strike with max total OI (pin candidate)
            pin_candidate = max(atm_strikes, key=lambda x: x['total_oi'])

            # Confidence based on OI concentration and charm magnitude
            total_oi = sum(s['total_oi'] for s in charm_by_strike)
            pin_oi_pct = (pin_candidate['total_oi'] / total_oi * 100) if total_oi > 0 else 0

            if pin_oi_pct > 20 and abs(pin_candidate['net_charm']) > 0.05:
                confidence = "HIGH"
            elif pin_oi_pct > 10 and abs(pin_candidate['net_charm']) > 0.02:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            pin_prediction = {
                "most_likely_pin_strike": pin_candidate['strike'],
                "confidence": confidence,
                "reason": f"{pin_oi_pct:.1f}% of total OI, net charm {pin_candidate['net_charm']:.4f}, {abs(pin_candidate['distance_from_spot_pct']):.1f}% from spot",
                "charm_magnitude": abs(pin_candidate['net_charm'])
            }

            # Dealer flow summary
            dealer_flow_summary = {
                "total_call_charm": round(total_call_charm, 4),
                "total_put_charm": round(total_put_charm, 4),
                "net_charm": round(net_charm, 4),
                "expected_direction": "BUY pressure" if net_charm < 0 else "SELL pressure" if net_charm > 0 else "NEUTRAL"
            }

            # Risk assessment
            max_charm = max(abs(s['net_charm']) for s in charm_by_strike)
            if max_charm > 0.10:
                risk_level = "HIGH"
            elif max_charm > 0.05:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            warnings = []
            if dte <= 3:
                warnings.append("⚠️ APPROACHING EXPIRATION: Charm effects peak in final 3 days")
            if confidence == "HIGH":
                warnings.append(f"🎯 STRONG PIN SIGNAL: ${pin_candidate['strike']:.2f} has {pin_oi_pct:.1f}% of total OI")

            return {
                "ticker": ticker,
                "expiration": expiration,
                "dte": dte,
                "current_price": round(current_price, 2),

                "charm_by_strike": charm_by_strike,

                "pin_prediction": pin_prediction,

                "dealer_flow_summary": dealer_flow_summary,

                "risk_level": risk_level,
                "warnings": warnings,

                "data_source": "questrade" if use_questrade else "yfinance",
                "methodology": "Hull - Options, Futures, and Other Derivatives, Chapter 19"
            }

        except Exception as e:
            logger.error(f"Error analyzing charm for {ticker}: {e}")
            raise ValueError(f"Charm analysis failed: {str(e)}")


    @mcp.tool()
    def analyze_gamma_exposure(
        ticker: str,
        expiration: str | None = None
    ) -> dict[str, Any]:
        # IMPORTANT: This function should try Questrade first!
        """
        Analyze aggregate dealer Gamma Exposure (GEX) across all strikes.

        **What is GEX?**
        Dealers (market makers) are SHORT options because retail/institutions are LONG.
        When dealers are short gamma, they must hedge by:
        - BUYING as price rises (amplifies rally)
        - SELLING as price falls (amplifies decline)
        = VOLATILITY AMPLIFICATION

        When dealers are long gamma (rare), they hedge opposite direction:
        = VOLATILITY SUPPRESSION

        **Gamma Walls:**
        Strikes with heavy gamma concentration become support/resistance levels.
        Breaking through a gamma wall triggers cascade effects as dealer hedging flips.

        Args:
            ticker: Stock symbol
            expiration: Specific expiration (None = nearest expiration)

        Returns:
            {
                "ticker": str,
                "current_price": float,
                "expiration": str,
                "dte": int,

                "total_market_gamma": float,  # Net dealer gamma
                "gamma_regime": str,  # NEGATIVE (amplify), POSITIVE (suppress)

                "gamma_by_strike": [
                    {
                        "strike": float,
                        "call_oi": int,
                        "put_oi": int,
                        "call_gamma": float,
                        "put_gamma": float,
                        "net_gamma": float,
                        "dealer_gamma": float,  # Opposite sign (dealers are short)
                        "distance_from_spot_pct": float
                    },
                    ...
                ],

                "gamma_walls": {
                    "zero_gamma_level": float,  # Where dealer gamma = 0
                    "resistance_levels": list[float],  # Heavy negative GEX
                    "support_levels": list[float]  # Heavy positive GEX
                },

                "volatility_forecast": {
                    "regime": str,  # SUPPRESSED, NORMAL, AMPLIFIED
                    "expected_daily_move_pct": float,
                    "confidence": str
                },

                "interpretation": str
            }

        Reference: SqueezeMetrics GEX methodology, SpotGamma research
        """
        ticker = validate_ticker(ticker)

        try:
            from datetime import datetime
            import numpy as np
            import pandas as pd

            # Try Questrade first (has Greeks including gamma)
            gamma_by_strike = []
            current_price = None
            dte = None
            expiration_str = None
            use_questrade = False

            try:
                from questrade_api import Questrade

                logger.info(f"GEX: Starting Questrade path for {ticker}")

                # Get symbol info from our wrapper
                qt_client = get_questrade_client()
                symbol_info = qt_client.get_symbol_info(ticker)

                if not symbol_info or not symbol_info.get('symbols'):
                    raise ValueError(f"Symbol {ticker} not found in Questrade")

                symbol_id = symbol_info['symbols'][0]['symbolId']
                current_price = symbol_info['symbols'][0]['prevDayClosePrice']
                logger.info(f"GEX: Got symbol info: {symbol_id}, price={current_price}")

                # Use raw Questrade API for options chain (like IV Skew does)
                q = Questrade()
                qt_options = q.symbol_options(symbol_id)
                logger.info(f"GEX: Retrieved options chain from Questrade")

                if not qt_options or 'optionChain' not in qt_options:
                    raise ValueError(f"No options chain available for {ticker}")

                # Parse the option chain structure
                # Structure: [{expiryDate, chainPerRoot: [{chainPerStrikePrice: [{strikePrice, callSymbolId, putSymbolId}]}]}]
                expirations_list = qt_options['optionChain']
                if not expirations_list:
                    raise ValueError(f"No expirations available for {ticker}")

                # Select expiration
                if expiration:
                    # User specified an expiration - find closest match
                    target_exp = datetime.strptime(expiration, '%Y-%m-%d').date()
                    selected_exp_obj = min(expirations_list, key=lambda x: abs((datetime.strptime(x['expiryDate'], '%Y-%m-%dT%H:%M:%S.%f%z').date() - target_exp).days))
                else:
                    # Use nearest expiration
                    selected_exp_obj = expirations_list[0]

                expiration_str = datetime.strptime(selected_exp_obj['expiryDate'], '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%d')
                expiry_dt = datetime.strptime(expiration_str, '%Y-%m-%d')
                dte = (expiry_dt - datetime.now()).days

                # Collect all option IDs from the selected expiration
                option_ids = []
                for root_data in selected_exp_obj['chainPerRoot']:
                    for strike_data in root_data['chainPerStrikePrice']:
                        if 'callSymbolId' in strike_data and strike_data['callSymbolId']:
                            option_ids.append(strike_data['callSymbolId'])
                        if 'putSymbolId' in strike_data and strike_data['putSymbolId']:
                            option_ids.append(strike_data['putSymbolId'])

                # Get quotes with Greeks in batches (Questrade may limit batch size)
                logger.info(f"GEX: Collected {len(option_ids)} option IDs for {ticker} {expiration_str}")

                if len(option_ids) == 0:
                    raise ValueError(f"No option IDs found for {ticker} {expiration_str}")

                all_quotes = []
                batch_size = 100
                for i in range(0, len(option_ids), batch_size):
                    batch = option_ids[i:i+batch_size]
                    logger.info(f"GEX: Fetching batch {i//batch_size + 1} of {(len(option_ids)-1)//batch_size + 1} ({len(batch)} options)")
                    # Use raw Questrade API (like IV Skew does)
                    quotes = q.markets_options(optionIds=batch)
                    if quotes and 'optionQuotes' in quotes:
                        all_quotes.extend(quotes['optionQuotes'])
                        logger.info(f"GEX: Got {len(quotes['optionQuotes'])} quotes in this batch")

                logger.info(f"GEX: Total quotes retrieved: {len(all_quotes)}")

                # Build gamma profile by strike
                strike_data = {}  # {strike: {'call_oi': ..., 'call_gamma': ..., 'put_oi': ..., 'put_gamma': ...}}

                for quote in all_quotes:
                    # Parse Questrade symbol format: "SPY20Feb26C335.00" or "SPY20Feb26P335.00"
                    # Need to find the LAST occurrence of C or P (rightmost) because ticker might contain C or P
                    symbol = quote['symbol']

                    # Find the rightmost C or P in the symbol
                    c_pos = symbol.rfind('C')
                    p_pos = symbol.rfind('P')

                    if c_pos > p_pos and c_pos != -1:
                        # Call option - extract everything after the C
                        is_call = True
                        strike_part = symbol[c_pos+1:]
                    elif p_pos > c_pos and p_pos != -1:
                        # Put option - extract everything after the P
                        is_call = False
                        strike_part = symbol[p_pos+1:]
                    else:
                        # Can't parse - skip
                        continue

                    strike = float(strike_part)
                    open_interest = quote.get('openInterest', 0) or 0
                    gamma = quote.get('gamma', 0) or 0

                    if strike not in strike_data:
                        strike_data[strike] = {'call_oi': 0, 'call_gamma': 0, 'put_oi': 0, 'put_gamma': 0}

                    if is_call:
                        strike_data[strike]['call_oi'] = open_interest
                        strike_data[strike]['call_gamma'] = gamma
                    else:
                        strike_data[strike]['put_oi'] = open_interest
                        strike_data[strike]['put_gamma'] = gamma

                # Convert to sorted list
                for strike in sorted(strike_data.keys()):
                    data = strike_data[strike]
                    call_oi = data['call_oi']
                    put_oi = data['put_oi']
                    call_gamma = data['call_gamma']
                    put_gamma = data['put_gamma']

                    # Calculate net gamma (retail/institutional position - they are LONG)
                    net_gamma = (call_oi * call_gamma) + (put_oi * put_gamma)

                    # Dealer gamma is OPPOSITE (dealers are SHORT options)
                    dealer_gamma = -net_gamma

                    distance_pct = ((strike - current_price) / current_price) * 100

                    gamma_by_strike.append({
                        "strike": strike,
                        "call_oi": call_oi,
                        "put_oi": put_oi,
                        "call_gamma": round(call_gamma, 6),
                        "put_gamma": round(put_gamma, 6),
                        "net_gamma": round(net_gamma, 2),
                        "dealer_gamma": round(dealer_gamma, 2),
                        "distance_from_spot_pct": round(distance_pct, 2)
                    })

                use_questrade = True

            except Exception as qt_error:
                logger.error(f"Questrade GEX failed for {ticker}: {qt_error}", exc_info=True)

                # Fall back to yfinance
                t = yf.Ticker(ticker)
                current_price = t.info.get('currentPrice') or t.info.get('regularMarketPrice') or t.history(period='1d')['Close'].iloc[-1]

                # Get options chain
                if expiration is None:
                    expirations = t.options
                    if not expirations:
                        raise ValueError(f"No options available for {ticker}")
                    expiration_str = expirations[0]  # Nearest expiration
                else:
                    expiration_str = expiration

                calls_df, puts_df = _fetch_yf_option_chain(t, expiration_str)

                # Calculate DTE
                expiry_dt = datetime.strptime(expiration_str, '%Y-%m-%d')
                dte = (expiry_dt - datetime.now()).days
                T = dte / 365
                r = 0.05

                # Build gamma profile by strike
                all_strikes = set()

                if not calls_df.empty:
                    all_strikes.update(calls_df['strike'].tolist())
                if not puts_df.empty:
                    all_strikes.update(puts_df['strike'].tolist())

                all_strikes = sorted(list(all_strikes))

                for strike in all_strikes:
                    # Get call data
                    call_oi = 0
                    call_gamma = 0
                    if not calls_df.empty:
                        call_data = calls_df[calls_df['strike'] == strike]
                        if not call_data.empty:
                            call_row = call_data.iloc[0]
                            call_oi_raw = call_row.get('openInterest', 0)
                            call_oi = int(call_oi_raw) if pd.notna(call_oi_raw) else 0
                            call_iv_raw = call_row.get('impliedVolatility', 0)
                            call_iv = float(call_iv_raw) if pd.notna(call_iv_raw) else 0

                            if call_iv > 0 and T > 0:
                                greeks = _calculate_black_scholes_greeks(current_price, strike, T, r, call_iv, 'call')
                                call_gamma = greeks['gamma']

                    # Get put data
                    put_oi = 0
                    put_gamma = 0
                    if not puts_df.empty:
                        put_data = puts_df[puts_df['strike'] == strike]
                        if not put_data.empty:
                            put_row = put_data.iloc[0]
                            put_oi_raw = put_row.get('openInterest', 0)
                            put_oi = int(put_oi_raw) if pd.notna(put_oi_raw) else 0
                            put_iv_raw = put_row.get('impliedVolatility', 0)
                            put_iv = float(put_iv_raw) if pd.notna(put_iv_raw) else 0

                            if put_iv > 0 and T > 0:
                                greeks = _calculate_black_scholes_greeks(current_price, strike, T, r, put_iv, 'put')
                                put_gamma = greeks['gamma']

                    # Calculate net gamma (retail/institutional position - they are LONG)
                    net_gamma = (call_oi * call_gamma) + (put_oi * put_gamma)

                    # Dealer gamma is OPPOSITE (dealers are SHORT options)
                    dealer_gamma = -net_gamma

                    distance_pct = ((strike - current_price) / current_price) * 100

                    gamma_by_strike.append({
                        "strike": strike,
                        "call_oi": call_oi,
                        "put_oi": put_oi,
                        "call_gamma": round(call_gamma, 6),
                        "put_gamma": round(put_gamma, 6),
                        "net_gamma": round(net_gamma, 2),
                        "dealer_gamma": round(dealer_gamma, 2),
                        "distance_from_spot_pct": round(distance_pct, 2)
                    })

            # Calculate total market gamma
            total_dealer_gamma = sum(item['dealer_gamma'] for item in gamma_by_strike)

            # Determine regime
            if total_dealer_gamma < -500:
                gamma_regime = "NEGATIVE"
                regime_description = "VOLATILITY AMPLIFICATION"
            elif total_dealer_gamma > 500:
                gamma_regime = "POSITIVE"
                regime_description = "VOLATILITY SUPPRESSION"
            else:
                gamma_regime = "NEUTRAL"
                regime_description = "NORMAL"

            # Find gamma walls
            # Sort by absolute dealer gamma to find concentrations
            sorted_by_gamma = sorted(gamma_by_strike, key=lambda x: abs(x['dealer_gamma']), reverse=True)

            # Resistance: strikes above price with heavy negative dealer gamma
            resistance_levels = []
            for item in sorted_by_gamma[:5]:  # Top 5 concentrations
                if item['strike'] > current_price and item['dealer_gamma'] < -100:
                    resistance_levels.append(item['strike'])

            # Support: strikes below price with heavy negative dealer gamma
            support_levels = []
            for item in sorted_by_gamma[:5]:
                if item['strike'] < current_price and item['dealer_gamma'] < -100:
                    support_levels.append(item['strike'])

            # Find zero-gamma level (approximate)
            # Where dealer gamma changes sign
            zero_gamma_level = current_price  # Default to current price
            for i in range(len(gamma_by_strike) - 1):
                curr = gamma_by_strike[i]
                next_item = gamma_by_strike[i + 1]
                if curr['dealer_gamma'] * next_item['dealer_gamma'] < 0:  # Sign change
                    zero_gamma_level = (curr['strike'] + next_item['strike']) / 2
                    break

            # Volatility forecast
            if gamma_regime == "NEGATIVE":
                vol_regime = "AMPLIFIED"
                expected_move = 1.5  # 1.5% daily moves expected
                confidence = "HIGH"
                interpretation = f"Dealers are SHORT gamma (total: {total_dealer_gamma:.0f}). They must hedge by BUYING rallies and SELLING dips = VOLATILITY AMPLIFICATION. Expect larger-than-normal price swings."
            elif gamma_regime == "POSITIVE":
                vol_regime = "SUPPRESSED"
                expected_move = 0.5  # 0.5% daily moves expected
                confidence = "MODERATE"
                interpretation = f"Dealers are LONG gamma (total: {total_dealer_gamma:.0f}). They hedge by SELLING rallies and BUYING dips = VOLATILITY SUPPRESSION. Expect muted price action."
            else:
                vol_regime = "NORMAL"
                expected_move = 1.0  # 1% daily moves expected
                confidence = "MODERATE"
                interpretation = f"Dealers are near gamma-neutral (total: {total_dealer_gamma:.0f}). Normal market dynamics expected."

            return {
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "expiration": expiration_str,
                "dte": dte,
                "data_source": "Questrade" if use_questrade else "yfinance",

                "total_market_gamma": round(total_dealer_gamma, 2),
                "gamma_regime": gamma_regime,
                "regime_description": regime_description,

                "gamma_by_strike": gamma_by_strike,

                "gamma_walls": {
                    "zero_gamma_level": round(zero_gamma_level, 2),
                    "resistance_levels": sorted(resistance_levels),
                    "support_levels": sorted(support_levels, reverse=True)
                },

                "volatility_forecast": {
                    "regime": vol_regime,
                    "expected_daily_move_pct": expected_move,
                    "confidence": confidence
                },

                "interpretation": interpretation,

                "methodology": "SqueezeMetrics GEX methodology, SpotGamma research"
            }

        except Exception as e:
            logger.error(f"Error analyzing gamma exposure for {ticker}: {e}")
            raise ValueError(f"Gamma exposure analysis failed: {str(e)}")

    # Expose closure functions via module-level _impl references
    global analyze_options_mcmillan_impl, analyze_iv_skew_impl
    global analyze_iv_term_structure_impl
    analyze_options_mcmillan_impl = analyze_options_mcmillan
    analyze_iv_skew_impl = analyze_iv_skew
    analyze_iv_term_structure_impl = analyze_iv_term_structure
