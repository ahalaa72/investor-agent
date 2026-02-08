"""
Portfolio risk tools: concentration limits, beta-weighted delta, Value at Risk (VaR/CVaR).
"""
import logging
from typing import Any

import pandas as pd

from ..core.config import INSTITUTIONAL_OPTIONS_PARAMS
from ..core.price import get_price_history_questrade_first, get_ticker_info_questrade_first

logger = logging.getLogger(__name__)


def _get_ticker_beta(ticker: str) -> float:
    """
    Get beta to SPY for a given ticker.

    Reusable helper function for portfolio risk calculations.
    Uses the existing get_ticker_info_questrade_first infrastructure.

    Args:
        ticker: Stock symbol

    Returns:
        float: Beta to SPY (defaults to 1.0 if unavailable)
    """
    try:
        if ticker == 'SPY':
            return 1.0

        # Use existing infrastructure to get ticker info
        ticker_info = get_ticker_info_questrade_first(ticker)
        info = ticker_info.get("merged", {})

        beta = info.get('beta')
        if beta is not None and beta != 0:
            return float(beta)

        # Fallback: default to 1.0
        logger.warning(f"Beta not available for {ticker}, defaulting to 1.0")
        return 1.0

    except Exception as e:
        logger.warning(f"Failed to get beta for {ticker}: {e}, defaulting to 1.0")
        return 1.0


def _get_current_price(ticker: str) -> float:
    """
    Get current price for a ticker.

    Reusable helper function for position valuation.
    Uses get_current_price_questrade_first (Questrade primary, Yahoo fallback).

    Args:
        ticker: Stock symbol

    Returns:
        float: Current price

    Raises:
        ValueError: If price cannot be determined from any source
    """
    from ..core.price import get_current_price_questrade_first

    try:
        return get_current_price_questrade_first(ticker)
    except Exception:
        pass

    # Fallback: try get_ticker_info_questrade_first
    try:
        ticker_info = get_ticker_info_questrade_first(ticker)
        info = ticker_info.get("merged", {})

        price = info.get('currentPrice')
        if price is not None and price > 0:
            return float(price)
    except Exception:
        pass

    raise ValueError(f"Cannot determine current price for {ticker} from any source")


def _get_ticker_sector_industry(ticker: str) -> tuple[str, str]:
    """
    Get sector and industry for a ticker.

    Reusable helper function for concentration analysis.
    Uses the existing get_ticker_info_questrade_first infrastructure.

    Args:
        ticker: Stock symbol

    Returns:
        tuple: (sector, industry) - defaults to ("Unknown", "Unknown") if unavailable
    """
    try:
        # Use existing infrastructure to get ticker info
        ticker_info = get_ticker_info_questrade_first(ticker)
        info = ticker_info.get("merged", {})

        sector = info.get('sector', 'Unknown')
        industry = info.get('industry', 'Unknown')

        return (sector, industry)

    except Exception as e:
        logger.warning(f"Failed to get sector/industry for {ticker}: {e}")
        return ("Unknown", "Unknown")


def register_tools(mcp):
    from .questrade_api import get_questrade_positions_impl as get_questrade_positions, get_questrade_balances_impl as get_questrade_balances

    def _calculate_portfolio_returns(
        account_number: str,
        lookback_days: int = 252
    ) -> tuple[pd.Series, dict]:
        """
        Calculate historical portfolio returns using Questrade positions and price history.

        Reusable helper function for VaR/CVaR calculations.
        Uses get_questrade_positions and get_price_history_questrade_first.

        Args:
            account_number: Questrade account number
            lookback_days: Number of days of history to fetch (default 252 = 1 year)

        Returns:
            tuple: (portfolio_returns Series, position_weights dict)
        """
        import numpy as np

        # Get current positions
        positions_data = get_questrade_positions(account_number)
        if not positions_data or 'positions' not in positions_data:
            raise ValueError("Could not fetch positions from Questrade")

        positions = positions_data['positions']

        # Calculate total portfolio value
        total_value = sum(pos.get('currentMarketValue', 0) for pos in positions if pos.get('openQuantity', 0) > 0)
        if total_value <= 0:
            raise ValueError("Portfolio has no value")

        # Fetch price history for each position and calculate weighted returns
        position_weights = {}
        all_returns = []
        skipped_positions = []

        # Mutual fund prefixes (Canadian mutual funds)
        MUTUAL_FUND_PREFIXES = ['MFC', 'RBF', 'LWF', 'TDB', 'DYN', 'FID', 'CIG', 'AGF', 'BMO', 'CI', 'IG']

        for position in positions:
            if position.get('openQuantity', 0) <= 0:
                continue

            symbol = position.get('symbol', '')
            if not symbol:
                continue

            market_value = position.get('currentMarketValue', 0)
            weight = market_value / total_value

            # Detect position type
            is_option = '.' in symbol or (len(symbol) > 6 and any(c.isdigit() for c in symbol[-8:]))
            is_mutual_fund = any(symbol.startswith(prefix) for prefix in MUTUAL_FUND_PREFIXES)

            ticker_to_fetch = symbol
            delta_weight = 1.0  # Default for stocks

            # Handle options - extract underlying ticker
            if is_option:
                try:
                    import re
                    # Parse option symbol (e.g., "DLO20Feb26C14.00" -> "DLO")
                    match = re.match(r'^([A-Z]+)', symbol)
                    if match:
                        underlying = match.group(1)
                        ticker_to_fetch = underlying
                        # Use approximate delta of 0.5 for ATM options (conservative)
                        delta_weight = 0.5
                        logger.info(f"Option {symbol} -> using underlying {underlying} with delta={delta_weight}")
                    else:
                        skipped_positions.append({
                            'symbol': symbol,
                            'reason': 'Could not parse option symbol',
                            'weight': weight,
                            'type': 'option'
                        })
                        continue
                except Exception as e:
                    skipped_positions.append({
                        'symbol': symbol,
                        'reason': f'Option parsing error: {e}',
                        'weight': weight,
                        'type': 'option'
                    })
                    continue

            position_weights[symbol] = weight

            try:
                # Get historical prices using Questrade-first approach
                period = f"{int(lookback_days/365*12)}mo" if lookback_days > 90 else "3mo"
                df = get_price_history_questrade_first(ticker_to_fetch, period=period)

                if df.empty or len(df) < 10:
                    skipped_positions.append({
                        'symbol': symbol,
                        'reason': f'Insufficient data ({len(df) if not df.empty else 0} days)',
                        'weight': weight,
                        'type': 'mutual_fund' if is_mutual_fund else 'option' if is_option else 'stock'
                    })
                    continue

                # Calculate daily returns
                daily_returns = df['Close'].pct_change().dropna()

                # Apply delta weighting for options
                weighted_returns = daily_returns * weight * delta_weight
                all_returns.append(weighted_returns)

                logger.info(f"Successfully processed {symbol} ({len(daily_returns)} days, weight={weight:.2%})")

            except Exception as e:
                skipped_positions.append({
                    'symbol': symbol,
                    'reason': f'Processing error: {str(e)[:100]}',
                    'weight': weight,
                    'type': 'mutual_fund' if is_mutual_fund else 'option' if is_option else 'stock'
                })
                continue

        # Provide detailed error if all positions were skipped
        if not all_returns:
            skipped_summary = "\n".join([
                f"  - {s['symbol']} ({s.get('type', 'unknown')}): {s['reason']} (weight: {s['weight']:.2%})"
                for s in skipped_positions
            ])
            raise ValueError(
                f"Could not calculate returns for any positions.\n"
                f"Skipped {len(skipped_positions)} positions:\n{skipped_summary}"
            )

        # Log skipped positions as warning if some succeeded
        if skipped_positions:
            skipped_weight = sum(s['weight'] for s in skipped_positions)
            logger.warning(
                f"Skipped {len(skipped_positions)} positions ({skipped_weight:.2%} of portfolio): "
                f"{', '.join(s['symbol'] for s in skipped_positions)}"
            )

        # Combine all weighted returns into portfolio returns
        # Align dates and sum
        portfolio_returns = pd.concat(all_returns, axis=1).sum(axis=1)

        return portfolio_returns, position_weights

    @mcp.tool()
    def check_portfolio_concentration_limits(
        account_number: str
    ) -> dict[str, Any]:
        """
        Check if portfolio violates institutional concentration limits.

        Analyzes a Questrade account for over-concentration using institutional risk standards:
        - Single ticker: 10% max
        - Single sector: 20% max
        - Correlated positions (r > 0.7): 40% max
        - Single expiration: 35% max (for options)

        **Uses Questrade as primary data source** for real-time position data.

        Args:
            account_number: Questrade account number (e.g., "26598145")

        Returns:
            {
                "account_number": str,
                "total_equity": float,

                "current_concentrations": {
                    "by_ticker": {"AAPL": 8.5, "TSLA": 12.3, ...},
                    "by_sector": {"Technology": 35.2, "Finance": 15.1, ...},
                    "by_industry": {"Software": 18.3, ...}
                },

                "violations": list[str],
                "warnings": list[str],

                "institutional_limits": {
                    "max_single_ticker": 10,
                    "max_sector": 20,
                    "max_single_expiration": 35
                },

                "recommendations": list[str],
                "risk_score": int
            }

        **Institutional Limits:**
        - Single ticker: 10% max (per INSTITUTIONAL_OPTIONS_PARAMS)
        - Single sector: 20% max
        - Single expiration: 35% max (options only)

        Reference: Hull - "Options, Futures, and Other Derivatives", Chapter 19
        """
        try:
            # Get positions from Questrade
            positions_data = get_questrade_positions(account_number)

            if not positions_data or 'positions' not in positions_data:
                return {"error": "Could not fetch positions from Questrade"}

            positions = positions_data['positions']

            # Get account balances to calculate total equity
            try:
                balances = get_questrade_balances(account_number)
                total_equity = balances.get('perCurrencyBalances', [{}])[0].get('totalEquity', 0)
                if total_equity == 0:
                    # Fallback: sum position values
                    total_equity = sum(pos.get('currentMarketValue', 0) for pos in positions)
            except Exception:
                # Fallback: sum position values
                total_equity = sum(pos.get('currentMarketValue', 0) for pos in positions)

            if total_equity <= 0:
                return {"error": "Could not determine total equity"}

            # Aggregate by ticker
            by_ticker = {}
            by_sector = {}
            by_industry = {}

            for position in positions:
                if position.get('openQuantity', 0) <= 0:
                    continue

                symbol = position.get('symbol', '')
                if not symbol:
                    continue

                market_value = position.get('currentMarketValue', 0)

                # Add to ticker concentration
                if symbol not in by_ticker:
                    by_ticker[symbol] = 0
                by_ticker[symbol] += market_value

                # Get sector/industry using helper
                sector, industry = _get_ticker_sector_industry(symbol)

                # Add to sector concentration
                if sector and sector != 'Unknown':
                    if sector not in by_sector:
                        by_sector[sector] = 0
                    by_sector[sector] += market_value

                # Add to industry concentration
                if industry and industry != 'Unknown':
                    if industry not in by_industry:
                        by_industry[industry] = 0
                    by_industry[industry] += market_value

            # Convert to percentages
            by_ticker_pct = {ticker: (value / total_equity * 100) for ticker, value in by_ticker.items()}
            by_sector_pct = {sector: (value / total_equity * 100) for sector, value in by_sector.items()}
            by_industry_pct = {industry: (value / total_equity * 100) for industry, value in by_industry.items()}

            # Check violations
            violations = []
            warnings = []
            recommendations = []

            # Get limits from INSTITUTIONAL_OPTIONS_PARAMS
            max_ticker_pct = INSTITUTIONAL_OPTIONS_PARAMS['max_single_underlying'] * 100  # 10%
            max_sector_pct = INSTITUTIONAL_OPTIONS_PARAMS['max_sector_exposure'] * 100  # 20%

            # Check ticker concentration
            for ticker, pct in by_ticker_pct.items():
                if pct > max_ticker_pct:
                    violations.append(
                        f"VIOLATION: {ticker} represents {pct:.1f}% of portfolio (limit: {max_ticker_pct:.0f}%)"
                    )
                    recommendations.append(
                        f"Reduce {ticker} position by {pct - max_ticker_pct:.1f}% to meet institutional limits"
                    )
                elif pct > max_ticker_pct * 0.8:  # Warning at 80% of limit
                    warnings.append(
                        f"WARNING: {ticker} represents {pct:.1f}% of portfolio (approaching {max_ticker_pct:.0f}% limit)"
                    )

            # Check sector concentration
            for sector, pct in by_sector_pct.items():
                if pct > max_sector_pct:
                    violations.append(
                        f"VIOLATION: {sector} sector represents {pct:.1f}% of portfolio (limit: {max_sector_pct:.0f}%)"
                    )
                    recommendations.append(
                        f"Diversify out of {sector} sector - reduce exposure by {pct - max_sector_pct:.1f}%"
                    )
                elif pct > max_sector_pct * 0.8:  # Warning at 80% of limit
                    warnings.append(
                        f"WARNING: {sector} sector represents {pct:.1f}% of portfolio (approaching {max_sector_pct:.0f}% limit)"
                    )

            # Calculate risk score (0-100)
            # Higher score = more concentrated
            ticker_risk = max(by_ticker_pct.values()) if by_ticker_pct else 0
            sector_risk = max(by_sector_pct.values()) if by_sector_pct else 0

            # Risk score = weighted average of concentrations
            risk_score = int(min(100, (ticker_risk * 1.5 + sector_risk) / 2))

            # General recommendations
            if len(by_ticker) <= 3:
                recommendations.append(
                    f"Portfolio has only {len(by_ticker)} position(s) - consider diversifying to 10-15 positions"
                )

            if len(by_sector) <= 2:
                recommendations.append(
                    f"Portfolio concentrated in {len(by_sector)} sector(s) - consider adding exposure to other sectors"
                )

            return {
                "account_number": account_number,
                "total_equity": round(total_equity, 2),
                "position_count": len(by_ticker),

                "current_concentrations": {
                    "by_ticker": {k: round(v, 2) for k, v in sorted(by_ticker_pct.items(), key=lambda x: -x[1])},
                    "by_sector": {k: round(v, 2) for k, v in sorted(by_sector_pct.items(), key=lambda x: -x[1])},
                    "by_industry": {k: round(v, 2) for k, v in sorted(by_industry_pct.items(), key=lambda x: -x[1])}
                },

                "violations": violations,
                "warnings": warnings,

                "institutional_limits": {
                    "max_single_ticker": int(max_ticker_pct),
                    "max_sector": int(max_sector_pct),
                    "max_single_expiration": 35,
                    "note": "Per INSTITUTIONAL_OPTIONS_PARAMS standard"
                },

                "recommendations": recommendations,
                "risk_score": risk_score,
                "risk_level": "LOW" if risk_score < 30 else "MODERATE" if risk_score < 60 else "HIGH"
            }

        except Exception as e:
            logger.error(f"Concentration limits check failed: {e}", exc_info=True)
            return {
                "error": f"Concentration limits check failed: {str(e)}",
                "account_number": account_number
            }

    @mcp.tool()
    def calculate_portfolio_beta_weighted_delta(
        positions: list[dict]
    ) -> dict[str, Any]:
        """
        Calculate beta-weighted delta exposure for entire portfolio.

        Converts all positions to SPY-equivalent delta for portfolio-level risk management.
        Essential for institutional-grade risk management across multi-ticker portfolios.

        **What is Beta-Weighted Delta?**
        - Normalizes all positions to SPY-equivalent exposure
        - Allows portfolio-level risk limits (e.g., +/-200 SPY delta per $100K)
        - Accounts for correlation differences (TSLA beta ~2.0, Utilities beta ~0.5)

        **Formula:**
        Beta-Weighted Delta = Position Delta x Beta to SPY x Position Size

        Args:
            positions: List of positions (stocks + options)
                [
                    {"ticker": "AAPL", "quantity": 100, "position_type": "stock"},
                    {"ticker": "TSLA", "quantity": -200, "position_type": "stock"},
                    {"ticker": "SPY", "strike": 500, "expiry": "2026-02-21",
                     "option_type": "CALL", "quantity": 10, "position_type": "option", "delta": 0.6},
                    ...
                ]

        Returns:
            {
                "total_beta_weighted_delta": float,
                "delta_per_100k": float,
                "risk_level": str,

                "by_ticker": {
                    "AAPL": {
                        "raw_delta": float,
                        "beta": float,
                        "beta_weighted_delta": float,
                        "position_value": float
                    },
                    ...
                },

                "concentration_warnings": list[str],
                "recommendations": list[str],

                "institutional_limits": {
                    "conservative": 100,
                    "moderate": 200,
                    "aggressive": 400
                }
            }

        **Institutional Limits (per $100K):**
        - Conservative: +/-100 SPY delta
        - Moderate: +/-200 SPY delta
        - Aggressive: +/-400 SPY delta

        Reference: Hull - "Options, Futures, and Other Derivatives", Chapter 19
        """
        try:
            by_ticker = {}
            total_beta_weighted_delta = 0.0
            total_portfolio_value = 0.0
            concentration_warnings = []
            recommendations = []

            # Process each position
            for position in positions:
                ticker = position.get('ticker')
                if not ticker:
                    logger.warning(f"Position missing ticker: {position}")
                    continue

                position_type = position.get('position_type', 'stock')

                # Get beta using helper function
                beta = _get_ticker_beta(ticker)

                # Calculate position delta
                if position_type == 'stock':
                    quantity = position.get('quantity', 0)
                    # Stock delta = 1 per share
                    raw_delta = quantity  # 100 shares = +100 delta

                    # Get position value
                    current_price = _get_current_price(ticker)
                    position_value = abs(quantity) * current_price

                elif position_type == 'option':
                    # Option delta calculation
                    quantity = position.get('quantity', 0)
                    option_delta = position.get('delta', 0.5)  # Default 0.5 if not provided

                    # Option delta = contracts x 100 shares/contract x delta
                    raw_delta = quantity * 100 * option_delta

                    # Estimate position value
                    premium = position.get('premium', 1.0)
                    position_value = abs(quantity) * 100 * premium

                else:
                    logger.warning(f"Unknown position type {position_type} for {ticker}")
                    continue

                # Beta-weighted delta = raw delta x beta
                beta_weighted_delta = raw_delta * beta

                # Accumulate
                total_beta_weighted_delta += beta_weighted_delta
                total_portfolio_value += position_value

                # Store by ticker
                if ticker not in by_ticker:
                    by_ticker[ticker] = {
                        "raw_delta": 0,
                        "beta": beta,
                        "beta_weighted_delta": 0,
                        "position_value": 0
                    }

                by_ticker[ticker]["raw_delta"] += raw_delta
                by_ticker[ticker]["beta_weighted_delta"] += beta_weighted_delta
                by_ticker[ticker]["position_value"] += position_value

            # Normalize to $100K
            if total_portfolio_value > 0:
                delta_per_100k = (total_beta_weighted_delta / total_portfolio_value) * 100000
            else:
                delta_per_100k = 0

            # Determine risk level
            abs_delta_per_100k = abs(delta_per_100k)
            if abs_delta_per_100k < 100:
                risk_level = "CONSERVATIVE"
            elif abs_delta_per_100k < 200:
                risk_level = "MODERATE"
            elif abs_delta_per_100k < 400:
                risk_level = "AGGRESSIVE"
            else:
                risk_level = "EXCESSIVE"
                concentration_warnings.append(
                    f"EXCESSIVE RISK: {abs_delta_per_100k:.0f} SPY delta per $100K exceeds institutional limit of 400"
                )

            # Check single-ticker concentration
            for ticker, data in by_ticker.items():
                ticker_pct = (data['position_value'] / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                if ticker_pct > 25:
                    concentration_warnings.append(
                        f"{ticker} represents {ticker_pct:.1f}% of portfolio (>25% concentration)"
                    )

            # Generate recommendations
            if abs_delta_per_100k > 300:
                recommendations.append(
                    f"Reduce exposure: Currently at {abs_delta_per_100k:.0f} SPY delta per $100K (target: <200 for moderate risk)"
                )

            if len(by_ticker) == 1:
                recommendations.append(
                    "Diversify portfolio: Currently concentrated in single ticker"
                )

            if total_beta_weighted_delta > 0:
                recommendations.append(
                    f"Portfolio is net LONG ({total_beta_weighted_delta:.0f} SPY delta). Consider hedging with puts if concerned about downside."
                )
            elif total_beta_weighted_delta < 0:
                recommendations.append(
                    f"Portfolio is net SHORT ({total_beta_weighted_delta:.0f} SPY delta). Consider hedging with calls if concerned about upside."
                )

            return {
                "total_beta_weighted_delta": round(total_beta_weighted_delta, 2),
                "delta_per_100k": round(delta_per_100k, 2),
                "risk_level": risk_level,
                "total_portfolio_value": round(total_portfolio_value, 2),

                "by_ticker": {
                    ticker: {
                        "raw_delta": round(data["raw_delta"], 2),
                        "beta": round(data["beta"], 2),
                        "beta_weighted_delta": round(data["beta_weighted_delta"], 2),
                        "position_value": round(data["position_value"], 2),
                        "portfolio_pct": round((data["position_value"] / total_portfolio_value * 100) if total_portfolio_value > 0 else 0, 2)
                    }
                    for ticker, data in by_ticker.items()
                },

                "concentration_warnings": concentration_warnings,
                "recommendations": recommendations,

                "institutional_limits": {
                    "conservative": 100,
                    "moderate": 200,
                    "aggressive": 400,
                    "note": "SPY delta per $100K portfolio value"
                },

                "interpretation": {
                    "directional_bias": "BULLISH" if total_beta_weighted_delta > 50 else "BEARISH" if total_beta_weighted_delta < -50 else "NEUTRAL",
                    "risk_statement": f"Portfolio has {abs(delta_per_100k):.0f} SPY delta per $100K - {risk_level} risk level"
                }
            }

        except Exception as e:
            logger.error(f"Beta-weighted delta calculation failed: {e}", exc_info=True)
            return {
                "error": f"Beta-weighted delta calculation failed: {str(e)}",
                "total_beta_weighted_delta": 0,
                "risk_level": "UNKNOWN"
            }

    @mcp.tool()
    def calculate_portfolio_var(
        account_number: str,
        confidence_level: float = 0.95,
        time_horizon_days: int = 1,
        lookback_days: int = 252
    ) -> dict[str, Any]:
        """
        Calculate Value at Risk (VaR) and Conditional VaR (CVaR) for a Questrade portfolio.

        **Uses Questrade as primary data source** for both positions and price history.

        VaR = Maximum expected loss at confidence level
        CVaR (Expected Shortfall) = Average loss beyond VaR threshold

        Uses historical simulation method with returns from get_price_history_questrade_first.

        Args:
            account_number: Questrade account number (e.g., "51673853")
            confidence_level: Confidence level (default 95% = 0.95)
            time_horizon_days: Time horizon in days (default 1 day)
            lookback_days: Historical lookback period (default 252 = 1 year)

        Returns:
            {
                "account_number": str,
                "portfolio_value": float,
                "var_95": float,
                "var_99": float,
                "cvar_95": float,
                "cvar_99": float,

                "interpretation": {
                    "var_statement": str,
                    "cvar_statement": str,
                },

                "stress_tests": {
                    "market_crash_20pct": float,
                    "volatility_spike_50pct": float,
                    "combined_scenario": float
                },

                "risk_metrics": {
                    "daily_volatility": float,
                    "annualized_volatility": float,
                    "worst_day": float,
                    "best_day": float,
                    "sharpe_ratio": float
                },

                "risk_level": str,
                "warnings": list[str]
            }

        **Risk Levels:**
        - LOW: VaR < 2% of portfolio
        - MODERATE: VaR 2-5% of portfolio
        - HIGH: VaR 5-10% of portfolio
        - EXTREME: VaR > 10% of portfolio

        Reference: Jorion - "Value at Risk: The New Benchmark for Managing Financial Risk"
        """
        import numpy as np

        try:
            # Get portfolio returns using helper function
            portfolio_returns, position_weights = _calculate_portfolio_returns(account_number, lookback_days)

            if len(portfolio_returns) < 30:
                return {
                    "error": f"Insufficient historical data ({len(portfolio_returns)} days) - need at least 30 days",
                    "account_number": account_number
                }

            # Get current portfolio value
            balances = get_questrade_balances(account_number)
            portfolio_value = balances.get('perCurrencyBalances', [{}])[0].get('totalEquity', 0)

            if portfolio_value <= 0:
                # Fallback to sum of positions
                positions_data = get_questrade_positions(account_number)
                positions = positions_data.get('positions', [])
                portfolio_value = sum(pos.get('currentMarketValue', 0) for pos in positions if pos.get('openQuantity', 0) > 0)

            # Scale returns to time horizon
            scaled_returns = portfolio_returns * np.sqrt(time_horizon_days)

            # Calculate VaR at different confidence levels
            var_95_pct = np.percentile(scaled_returns, (1 - 0.95) * 100)  # 5th percentile
            var_99_pct = np.percentile(scaled_returns, (1 - 0.99) * 100)  # 1st percentile

            # Calculate CVaR (average of losses beyond VaR)
            losses_beyond_var_95 = scaled_returns[scaled_returns <= var_95_pct]
            cvar_95_pct = losses_beyond_var_95.mean() if len(losses_beyond_var_95) > 0 else var_95_pct

            losses_beyond_var_99 = scaled_returns[scaled_returns <= var_99_pct]
            cvar_99_pct = losses_beyond_var_99.mean() if len(losses_beyond_var_99) > 0 else var_99_pct

            # Convert to dollar amounts
            var_95_dollars = abs(var_95_pct * portfolio_value)
            var_99_dollars = abs(var_99_pct * portfolio_value)
            cvar_95_dollars = abs(cvar_95_pct * portfolio_value)
            cvar_99_dollars = abs(cvar_99_pct * portfolio_value)

            # Risk metrics
            daily_vol = portfolio_returns.std()
            annualized_vol = daily_vol * np.sqrt(252)
            worst_day = portfolio_returns.min()
            best_day = portfolio_returns.max()

            # Sharpe ratio (assuming 3% risk-free rate)
            risk_free_rate = 0.03
            daily_rf = risk_free_rate / 252
            excess_returns = portfolio_returns - daily_rf
            sharpe_ratio = (excess_returns.mean() / daily_vol * np.sqrt(252)) if daily_vol > 0 else 0

            # Stress tests
            market_crash_20pct = portfolio_value * -0.20
            # Volatility spike: estimate using historical vol relationship
            vol_spike_impact = portfolio_value * (annualized_vol * 0.5)  # 50% vol increase
            combined_scenario = market_crash_20pct - vol_spike_impact

            # Determine risk level
            var_pct = (var_95_dollars / portfolio_value * 100) if portfolio_value > 0 else 0

            if var_pct < 2:
                risk_level = "LOW"
            elif var_pct < 5:
                risk_level = "MODERATE"
            elif var_pct < 10:
                risk_level = "HIGH"
            else:
                risk_level = "EXTREME"

            # Warnings
            warnings = []
            if var_pct > 10:
                warnings.append(f"EXTREME RISK: 1-day VaR is {var_pct:.1f}% of portfolio (>${var_95_dollars:,.0f})")

            if cvar_95_dollars > var_95_dollars * 1.5:
                warnings.append(f"FAT TAILS: CVaR is {cvar_95_dollars/var_95_dollars:.1f}x VaR - extreme losses possible")

            if annualized_vol > 0.40:
                warnings.append(f"HIGH VOLATILITY: {annualized_vol*100:.1f}% annualized volatility")

            if sharpe_ratio < 0.5:
                warnings.append(f"LOW SHARPE RATIO: {sharpe_ratio:.2f} - risk-adjusted returns are poor")

            return {
                "account_number": account_number,
                "portfolio_value": round(portfolio_value, 2),
                "lookback_period_days": len(portfolio_returns),

                "var_95": round(var_95_dollars, 2),
                "var_95_pct": round(var_pct, 2),
                "var_99": round(var_99_dollars, 2),
                "var_99_pct": round((var_99_dollars / portfolio_value * 100) if portfolio_value > 0 else 0, 2),

                "cvar_95": round(cvar_95_dollars, 2),
                "cvar_99": round(cvar_99_dollars, 2),

                "interpretation": {
                    "var_statement": f"With 95% confidence, portfolio won't lose more than ${var_95_dollars:,.2f} ({var_pct:.1f}%) in {time_horizon_days} day(s)",
                    "cvar_statement": f"If VaR is breached (5% of days), expect average loss of ${cvar_95_dollars:,.2f}",
                    "risk_assessment": f"{risk_level} risk - VaR is {var_pct:.1f}% of portfolio value"
                },

                "stress_tests": {
                    "market_crash_20pct": round(market_crash_20pct, 2),
                    "volatility_spike_50pct": round(-vol_spike_impact, 2),
                    "combined_scenario": round(combined_scenario, 2),
                    "note": "Estimated losses under extreme scenarios"
                },

                "risk_metrics": {
                    "daily_volatility": round(daily_vol, 4),
                    "annualized_volatility": round(annualized_vol, 4),
                    "worst_day": round(worst_day, 4),
                    "worst_day_dollars": round(worst_day * portfolio_value, 2),
                    "best_day": round(best_day, 4),
                    "best_day_dollars": round(best_day * portfolio_value, 2),
                    "sharpe_ratio": round(sharpe_ratio, 2)
                },

                "position_weights": {k: round(v, 4) for k, v in position_weights.items()},

                "risk_level": risk_level,
                "warnings": warnings,

                "methodology": "Historical Simulation VaR using Questrade price history",
                "confidence_level": confidence_level,
                "time_horizon_days": time_horizon_days
            }

        except Exception as e:
            logger.error(f"VaR calculation failed: {e}", exc_info=True)
            return {
                "error": f"VaR calculation failed: {str(e)}",
                "account_number": account_number
            }
