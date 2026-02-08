"""
Position management tools: position evaluation, portfolio Greeks, order flow, bid/ask analysis.
"""
import logging
import datetime
from typing import Any

import numpy as np
import yfinance as yf

from ..core.config import INSTITUTIONAL_OPTIONS_PARAMS
from ..core.price import get_current_price_questrade_first, convert_numpy_types
from ..questrade import get_questrade_client

logger = logging.getLogger(__name__)


def register_tools(mcp):
    @mcp.tool()
    def evaluate_options_position_management(
        symbol: str,
        strategy: str,
        entry_date: str,
        expiration: str,
        entry_credit: float = 0.0,
        entry_debit: float = 0.0,
        current_value: float = 0.0,
        entry_direction: str = "LONG",
        legs: list[dict] | None = None
    ) -> dict[str, Any]:
        """
        Evaluate an options position and recommend management action.

        Implements TastyTrade + McMillan methodology:
        1. **50% Profit Target** - Close when 50% of max profit achieved (88% win rate)
        2. **21 DTE Management** - Close or roll at 21 days to expiration
        3. **Direction Change** - Exit if Brooks Always-In flips
        4. **Tested Position** - Manage if price breaches short strikes
        5. **Earnings <7 days** - Close to avoid IV crush

        Args:
            symbol: Underlying symbol (e.g., "AAPL")
            strategy: Options strategy type
                ("IRON_CONDOR", "CREDIT_SPREAD", "DEBIT_SPREAD", "BULL_PUT_SPREAD", etc.)
            entry_date: Position entry date (YYYY-MM-DD)
            expiration: Options expiration date (YYYY-MM-DD)
            entry_credit: Max profit for credit strategies (default 0.0)
            entry_debit: Max loss for debit strategies (default 0.0)
            current_value: Current position value (default 0.0 = will fetch from market)
            entry_direction: Direction when entered ("LONG" or "SHORT")
            legs: Optional list of position legs:
                [
                    {"type": "CALL", "strike": 252, "action": "SELL", "quantity": 2},
                    {"type": "CALL", "strike": 257, "action": "BUY", "quantity": 2},
                    ...
                ]

        Returns:
            {
                "action": "HOLD" | "CLOSE" | "ROLL" | "ADJUST",
                "reason": str,
                "urgency": "IMMEDIATE" | "WITHIN_3_DAYS" | "MONITOR",

                "profit_status": {
                    "current_pnl": float,
                    "current_pnl_pct": float,
                    "profit_target_hit": bool
                },

                "dte_status": {
                    "days_to_expiration": int,
                    "dte_threshold_hit": bool,
                    "gamma_risk_level": "LOW" | "MODERATE" | "HIGH"
                },

                "recommendation": str,
                "expected_pnl_if_close": float,
                "expected_pnl_if_hold": float | str
            }

        Example:
            evaluate_options_position_management(
                symbol="AAPL",
                strategy="IRON_CONDOR",
                entry_date="2026-01-15",
                expiration="2026-02-21",
                entry_credit=630.00,
                current_value=315.00,
                entry_direction="NEUTRAL",
                legs=[
                    {"type": "CALL", "strike": 252, "action": "SELL", "quantity": 2},
                    {"type": "CALL", "strike": 257, "action": "BUY", "quantity": 2},
                    {"type": "PUT", "strike": 204, "action": "SELL", "quantity": 2},
                    {"type": "PUT", "strike": 199, "action": "BUY", "quantity": 2}
                ]
            )

        Reference:
            - TastyTrade: "Manage Winners at 50% of Max Profit"
            - McMillan: "Options as a Strategic Investment", Chapter 36
        """
        from investor_agent.positions import evaluate_options_position

        try:
            # BUG-10 FIX: Use get_current_price_questrade_first instead of direct yf.Ticker()
            current_market_price = get_current_price_questrade_first(symbol)

            if not current_market_price:
                raise ValueError(f"Could not get current price for {symbol}")

            # Get Brooks signal for direction check
            brooks_signal = None
            try:
                from .scanning import _get_ohlcv_cached
                from .technical_analysis import analyze_technical_impl as analyze_technical
                ohlcv = _get_ohlcv_cached(symbol, period="3mo")
                technical_data = analyze_technical(symbol, period="3mo", include_ml_analysis=False)
                from investor_agent.scanner_analyzer import AlBrooksAnalyzer
                brooks_analyzer = AlBrooksAnalyzer()
                brooks_signal = brooks_analyzer.analyze(
                    ticker=symbol,
                    direction="long",  # Doesn't matter for always_in
                    ohlcv_data=ohlcv,
                    technical_data=technical_data or {}
                )
            except Exception as e:
                logger.debug(f"Could not get Brooks signal for {symbol}: {e}")

            # Build position dict
            position = {
                "symbol": symbol,
                "strategy": strategy,
                "entry_date": entry_date,
                "expiration": expiration,
                "entry_credit": entry_credit,
                "entry_debit": entry_debit,
                "current_value": current_value,
                "entry_direction": entry_direction,
                "legs": legs or []
            }

            # Evaluate position
            result = evaluate_options_position(
                position=position,
                current_market_price=current_market_price,
                brooks_signal=brooks_signal
            )

            logger.info(f"Evaluated {symbol} {strategy}: Action={result.get('action')}, Urgency={result.get('urgency')}")
            return result

        except Exception as e:
            logger.error(f"Error evaluating position {symbol}: {e}")
            raise ValueError(f"Failed to evaluate position: {str(e)}")


    @mcp.tool()
    def get_portfolio_greeks_dashboard() -> dict[str, Any]:
        """
        Get aggregate portfolio Greeks across all options positions.

        Calculates portfolio-level risk metrics:
        - **Delta**: Directional exposure (positive = bullish, negative = bearish)
        - **Theta**: Daily time decay (positive = collecting premium)
        - **Vega**: IV sensitivity (positive = want IV up, negative = want IV down)
        - **Gamma**: Delta change rate (positive = long gamma, negative = short gamma)

        Returns:
            {
                "data_quality": "ESTIMATED",
                "total_delta": float,
                "total_theta": float,
                "total_vega": float,
                "total_gamma": float,

                "theta_daily_income": float,  # Expected daily profit from time decay
                "vega_10pt_impact": float,    # P&L change if IV moves 10 points

                "risk_assessment": {
                    "delta_exposure": "NEUTRAL" | "BULLISH" | "BEARISH",
                    "theta_position": "LONG_THETA" | "SHORT_THETA",
                    "vega_position": "LONG_VEGA" | "SHORT_VEGA",
                    "gamma_position": "LONG_GAMMA" | "SHORT_GAMMA"
                },

                "recommendations": list[str]
            }

        Note:
            Requires Questrade account with options positions.
            Use get_questrade_accounts() to get account numbers first.

        Example Output:
            {
                "total_delta": +142.3,  # Bullish directional bias
                "total_theta": +12.45,  # Collecting $12.45/day in time decay
                "total_vega": -156.8,   # Want IV to decrease (short premium)
                "total_gamma": -2.34,   # Short gamma (need to hedge as price moves)

                "theta_daily_income": 12.45,
                "vega_10pt_impact": -1568.00,  # Lose $1,568 if IV increases 10 points

                "risk_assessment": {
                    "delta_exposure": "BULLISH",
                    "theta_position": "LONG_THETA",
                    "vega_position": "SHORT_VEGA",
                    "gamma_position": "SHORT_GAMMA"
                },

                "recommendations": [
                    "Short gamma position - hedge as price approaches short strikes",
                    "Positive theta - time decay working in your favor",
                    "Short vega - vulnerable to IV expansion"
                ]
            }

        Reference:
            Hull - "Options, Futures, and Other Derivatives", Chapter 19
        """
        from investor_agent.positions import get_position_greeks_summary
        from .questrade_api import get_questrade_accounts_impl as get_questrade_accounts, get_questrade_positions_impl as get_questrade_positions

        try:
            # Get all Questrade accounts
            accounts_data = get_questrade_accounts()
            accounts = accounts_data.get('accounts', [])

            if not accounts:
                return {"error": "No Questrade accounts found"}

            # Collect all options positions across accounts
            all_positions = []

            for account in accounts:
                account_number = account.get('number')
                try:
                    positions_data = get_questrade_positions(account_number)
                    positions = positions_data.get('positions', [])

                    # Filter for options only (symbolId format indicates options)
                    for pos in positions:
                        symbol = pos.get('symbol', '')
                        # Options symbols contain expiry dates
                        if any(char.isdigit() for char in symbol):
                            # BUG-7 FIX: Add greeks_warning to each position's greeks dict
                            # Note: In production, fetch option quotes with Greeks here
                            all_positions.append({
                                "symbol": symbol,
                                "quantity": pos.get('openQuantity', 0),
                                "position_type": "option",
                                "greeks": {
                                    "delta": 0.5,  # Placeholder - fetch real Greeks
                                    "theta": -0.15,
                                    "vega": 1.0,
                                    "gamma": 0.01,
                                    "greeks_warning": "ESTIMATED VALUES - Not from live options quotes. Use for directional guidance only, not precise risk management."
                                }
                            })

                except Exception as e:
                    logger.warning(f"Could not get positions for account {account_number}: {e}")
                    continue

            if not all_positions:
                return {
                    "data_quality": "ESTIMATED",
                    "total_delta": 0.0,
                    "total_theta": 0.0,
                    "total_vega": 0.0,
                    "total_gamma": 0.0,
                    "risk_assessment": {
                        "delta_exposure": "NEUTRAL",
                        "theta_position": "NEUTRAL",
                        "vega_position": "NEUTRAL",
                        "gamma_position": "NEUTRAL"
                    },
                    "recommendations": ["No options positions found in portfolio"]
                }

            # Calculate aggregate Greeks
            greeks_summary = get_position_greeks_summary(all_positions)

            # BUG-7 FIX: Add data_quality to top-level response
            greeks_summary['data_quality'] = "ESTIMATED"

            # Add recommendations based on Greeks
            recommendations = []

            if greeks_summary['total_theta'] > 5:
                recommendations.append("Positive theta - time decay working in your favor")
            elif greeks_summary['total_theta'] < -5:
                recommendations.append("Negative theta - paying time decay daily")

            if greeks_summary['total_vega'] < -50:
                recommendations.append("Short vega - vulnerable to IV expansion")
            elif greeks_summary['total_vega'] > 50:
                recommendations.append("Long vega - benefit from IV expansion")

            if greeks_summary['total_gamma'] < -1:
                recommendations.append("Short gamma position - hedge as price approaches short strikes")
            elif greeks_summary['total_gamma'] > 1:
                recommendations.append("Long gamma - delta self-hedges as price moves")

            abs_delta = abs(greeks_summary['total_delta'])
            if abs_delta > 100:
                direction = "bullish" if greeks_summary['total_delta'] > 0 else "bearish"
                recommendations.append(f"High delta exposure ({abs_delta:.0f}) - strong {direction} bias")

            greeks_summary['recommendations'] = recommendations

            logger.info(f"Portfolio Greeks: Delta={greeks_summary['total_delta']:.1f}, Theta={greeks_summary['total_theta']:.2f}")
            return greeks_summary

        except Exception as e:
            logger.error(f"Error calculating portfolio Greeks: {e}")
            raise ValueError(f"Failed to get portfolio Greeks: {str(e)}")


    # ============================================================================
    # Real-Time Order Flow Tools
    # ============================================================================

    @mcp.tool()
    def analyze_realtime_trade_flow(
        ticker: str,
        duration_minutes: int = 30
    ) -> dict[str, Any]:
        """
        Analyze real-time trade flow using Questrade Level 1 data.

        Uses lastTradeTick to classify trades as buyer or seller initiated.
        This is TRUE order flow classification, not OHLCV approximation.

        Tick meanings:
        - "Up" = Trade at higher price = Buyer hitting ask (BULLISH)
        - "Down" = Trade at lower price = Seller hitting bid (BEARISH)
        - "Equal" = Trade at same price = Neutral

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            duration_minutes: How many minutes of data to analyze (default 30)

        Returns:
            Trade flow analysis with:
            - buy_volume / sell_volume / neutral_volume
            - tick_ratio: buy_vol / (buy_vol + sell_vol)
            - aggression_bias: BULLISH (>55%), BEARISH (<45%), NEUTRAL
            - large_trade_details: Trades > 2x average size
        """
        from investor_agent.realtime_order_flow import analyze_trade_flow_snapshot

        try:
            # For single call, use snapshot function
            result = analyze_trade_flow_snapshot(ticker)
            logger.info(f"Retrieved trade flow snapshot for {ticker}")
            return result

        except Exception as e:
            logger.error(f"Error in analyze_realtime_trade_flow for {ticker}: {e}")
            raise ValueError(f"Failed to analyze trade flow for {ticker}: {str(e)}")


    @mcp.tool()
    def get_bid_ask_imbalance(ticker: str) -> dict[str, Any]:
        """
        Get current bid/ask size imbalance for a ticker.

        Monitors passive order flow to detect institutional positioning.

        Interpretation:
        - High bid/ask ratio (>2.0) = STRONG_BID = Buyers have size advantage
        - Low bid/ask ratio (<0.5) = STRONG_ASK = Sellers have size advantage
        - Ratio 0.8-1.2 = BALANCED

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")

        Returns:
            Bid/ask imbalance analysis with:
            - imbalance_ratio: bidSize / askSize
            - imbalance_pct: (bid - ask) / total * 100
            - signal: STRONG_BID / WEAK_BID / BALANCED / WEAK_ASK / STRONG_ASK
            - spread_bps: Spread in basis points
            - liquidity_wall: Side with larger size
        """
        try:
            client = get_questrade_client()
            quotes = client.get_quote(ticker)

            if not quotes.get('quotes'):
                return {"error": f"No quote data for {ticker}"}

            q = quotes['quotes'][0]

            bid_size = q.get('bidSize') or 0
            ask_size = q.get('askSize') or 0
            bid_price = q.get('bidPrice') or 0
            ask_price = q.get('askPrice') or 0

            # Calculate imbalance
            if ask_size > 0:
                imbalance = bid_size / ask_size
            else:
                imbalance = 1.0

            total = bid_size + ask_size
            if total > 0:
                imbalance_pct = (bid_size - ask_size) / total * 100
            else:
                imbalance_pct = 0

            # Determine signal
            if imbalance > 2.0:
                signal = "STRONG_BID"
            elif imbalance > 1.2:
                signal = "WEAK_BID"
            elif imbalance < 0.5:
                signal = "STRONG_ASK"
            elif imbalance < 0.8:
                signal = "WEAK_ASK"
            else:
                signal = "BALANCED"

            # Calculate spread in basis points
            mid_price = (bid_price + ask_price) / 2 if (bid_price + ask_price) > 0 else 1
            spread = ask_price - bid_price
            spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0

            result = {
                "ticker": ticker.upper(),
                "bid_size": bid_size,
                "ask_size": ask_size,
                "bid_price": bid_price,
                "ask_price": ask_price,
                "imbalance_ratio": round(imbalance, 2),
                "imbalance_pct": round(imbalance_pct, 1),
                "signal": signal,
                "spread": round(spread, 4),
                "spread_bps": round(spread_bps, 1),
                "liquidity_wall": {
                    "side": "BID" if bid_size > ask_size else "ASK",
                    "size": max(bid_size, ask_size),
                    "price": bid_price if bid_size > ask_size else ask_price
                },
                "interpretation": f"{'Buyers' if imbalance > 1 else 'Sellers'} have size advantage ({signal})"
            }

            logger.info(f"Retrieved bid-ask imbalance for {ticker}: {signal}")
            return result

        except Exception as e:
            logger.error(f"Error in get_bid_ask_imbalance for {ticker}: {e}")
            raise ValueError(f"Failed to retrieve bid-ask imbalance for {ticker}: {str(e)}")


    @mcp.tool()
    def analyze_spread_dynamics(ticker: str) -> dict[str, Any]:
        """
        Analyze spread dynamics for liquidity assessment.

        Spread is a key indicator of market liquidity and potential volatility:
        - Tight spread = High liquidity, lower transaction costs
        - Wide spread = Lower liquidity, higher volatility expected

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")

        Returns:
            Spread analysis with:
            - current_spread: Ask - Bid in dollars
            - spread_bps: Spread in basis points
            - liquidity_grade: A (excellent) to F (very poor)
            - total_depth: Combined bid + ask size
        """
        try:
            client = get_questrade_client()
            quotes = client.get_quote(ticker)

            if not quotes.get('quotes'):
                return {"error": f"No quote data for {ticker}"}

            q = quotes['quotes'][0]

            bid_price = q.get('bidPrice') or 0
            ask_price = q.get('askPrice') or 0
            bid_size = q.get('bidSize') or 0
            ask_size = q.get('askSize') or 0

            # Current spread
            spread = ask_price - bid_price
            mid_price = (bid_price + ask_price) / 2 if (bid_price + ask_price) > 0 else 1
            spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0

            # Liquidity grade based on spread and size
            total_size = bid_size + ask_size
            if spread_bps < 5 and total_size > 1000:
                grade = "A"  # Excellent
            elif spread_bps < 10 and total_size > 500:
                grade = "B"  # Good
            elif spread_bps < 20 and total_size > 100:
                grade = "C"  # Average
            elif spread_bps < 50:
                grade = "D"  # Poor
            else:
                grade = "F"  # Very poor

            result = {
                "ticker": ticker.upper(),
                "bid_price": bid_price,
                "ask_price": ask_price,
                "current_spread": round(spread, 4),
                "spread_bps": round(spread_bps, 1),
                "bid_size": bid_size,
                "ask_size": ask_size,
                "total_depth": total_size,
                "liquidity_grade": grade,
                "interpretation": f"Liquidity Grade {grade} - Spread {round(spread_bps, 1)} bps"
            }

            logger.info(f"Analyzed spread dynamics for {ticker}: Grade {grade}")
            return result

        except Exception as e:
            logger.error(f"Error in analyze_spread_dynamics for {ticker}: {e}")
            raise ValueError(f"Failed to analyze spread dynamics for {ticker}: {str(e)}")
