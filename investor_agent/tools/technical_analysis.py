"""
Technical analysis tools: indicators, support/resistance, technical comparison.
"""
import logging
import datetime
from typing import Literal, Any
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import yfinance as yf

from ..core.config import INSTITUTIONAL_OPTIONS_PARAMS
from ..core.http import safe_future_result
from ..core.validation import validate_ticker
from ..core.price import (
    get_price_history_questrade_first, get_current_price_questrade_first,
    get_ticker_info_questrade_first, convert_numpy_types, yf_call, to_clean_csv,
)
from ..technical.indicators import (
    detect_ema_bounce, detect_ema_cross, detect_ema_extension,
    detect_vwap_bounce, detect_vwap_cross, interpret_vwap_position,
    detect_volume_surge, calculate_obv_signal, confirm_crossover_with_volume,
    detect_ema_vwap_confluence, detect_order_blocks, detect_supply_demand_zones,
)
from ..entry_exit_strategy import (
    find_support_resistance_kmeans,
    calculate_optimized_macd,
    calculate_adx,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level imports for _impl functions
# ---------------------------------------------------------------------------
from .scanning import _get_ohlcv_cached, _get_ohlcv_cached_multitimeframe

try:
    from ..technical_analysis import TechnicalAnalysis
    _advanced_ta_available = True
except ImportError:
    _advanced_ta_available = False
    logger.warning("Advanced technical analysis module not available")

from ..ml_core import get_trend_scanning_labels
from ..backtesting import SimilarityEngine

try:
    from investor_agent.scanner_analyzer import AlBrooksAnalyzer, calculate_timeframe_confluence
    _analyzer_available = True
except ImportError:
    _analyzer_available = False

try:
    from ..technical_analysis_bootstrap import (
        analyze_volume,
        analyze_volatility,
        calculate_relative_strength,
        calculate_fundamental_scores,
    )
    _bootstrap_available = True
except ImportError:
    _bootstrap_available = False
    logger.warning("Technical analysis bootstrap functions not available")


# ---------------------------------------------------------------------------
# Implementation functions (module-level, importable by other modules)
# ---------------------------------------------------------------------------

def analyze_technical_impl(
    ticker: str,
    period: str = "6mo",
    include_ml_analysis: bool = True,
    include_trend_score: bool = True,
) -> dict:
    """Comprehensive technical analysis with RSI, MACD, BB, MA, Al Brooks, ML."""
    ticker = validate_ticker(ticker)

    history = _get_ohlcv_cached(ticker, period=period)
    if history is None or history.empty:
        raise ValueError(f"No historical data found for {ticker}")

    indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)

    result = {
        "symbol": ticker,
        "period": period,
        "data_points": len(history),
        "analysis": indicators,
    }

    # ML probability layer
    if include_ml_analysis:
        try:
            current_conditions = {
                'rsi': indicators['rsi']['value'],
                'price_level': indicators['current_price'],
                'trend': 'UPTREND' if indicators['moving_averages']['trend'] == 'bullish' else 'DOWNTREND',
                'macd_trend': indicators['macd']['trend'],
            }

            engine = SimilarityEngine(similarity_threshold=0.75, min_similar_setups=10)
            similar_setups = engine.find_similar_setups(
                ticker=ticker,
                current_conditions=current_conditions,
                historical_data=history,
                lookback_periods=min(200, len(history) - 20),
            )

            if len(similar_setups) >= 1:
                analysis_result = engine.analyze_similar_setups(
                    ticker=ticker,
                    current_conditions=current_conditions,
                    similar_setups=similar_setups,
                )
                result['ml_probability_layer'] = {
                    'similar_setups_found': len(similar_setups),
                    'historical_success_rate_10d': analysis_result.aggregate_statistics.get('success_rate_10d', 0.0),
                    'avg_return_10d': analysis_result.aggregate_statistics.get('avg_return_10d', 0.0),
                    'confidence': analysis_result.recommendation.get('confidence', 0.0),
                    'recommendation': analysis_result.recommendation.get('take_trade', False),
                    'expected_return': analysis_result.recommendation.get('expected_return', 0.0),
                    'risk_reward_ratio': analysis_result.aggregate_statistics.get('risk_reward_ratio', 0.0),
                    'confidence_interval_95': analysis_result.aggregate_statistics.get('confidence_interval_95', [0.0, 0.0]),
                    'interpretation': (
                        f"Based on {len(similar_setups)} similar historical setups, "
                        f"{analysis_result.aggregate_statistics.get('success_rate_10d', 0.0):.1%} success rate. "
                        f"{'HIGH PROBABILITY' if analysis_result.recommendation.get('confidence', 0) > 0.7 else 'MODERATE' if analysis_result.recommendation.get('confidence', 0) > 0.5 else 'LOW'} setup."
                    ),
                }
            else:
                data_days = len(history) if history is not None and not history.empty else 0
                if data_days < 60:
                    reason = f'Insufficient historical data ({data_days} days). New stock or limited trading history.'
                else:
                    reason = 'No similar historical setups found matching current conditions (very unique setup).'
                result['ml_probability_layer'] = {
                    'similar_setups_found': 0,
                    'data_availability': f'{data_days} days',
                    'note': reason,
                    'interpretation': 'ML probability analysis unavailable. Rely on technical indicators and price action instead.',
                    'recommendation': 'Use Al Brooks price action analysis and traditional technical indicators for this setup.',
                }
        except Exception as e:
            result['ml_probability_layer'] = {
                'error': f'ML analysis failed: {str(e)}',
                'interpretation': 'ML analysis unavailable',
            }

    # Al Brooks Price Action Analysis
    try:
        if _analyzer_available:
            brooks = AlBrooksAnalyzer()
            ma_trend = indicators.get('moving_averages', {}).get('trend', 'neutral')
            macd_trend = indicators.get('macd', {}).get('trend', 'neutral')
            direction = 'long' if ma_trend == 'bullish' or macd_trend == 'bullish' else 'short'

            brooks_result = brooks.analyze(
                ticker=ticker, direction=direction,
                ohlcv_data=history, technical_data=result,
            )
            result['al_brooks'] = {
                'always_in_direction': brooks_result.get('always_in', 'UNKNOWN'),
                'pattern': brooks_result.get('pattern', 'none'),
                'pattern_description': brooks_result.get('pattern_description', ''),
                'base_probability': brooks_result.get('base_probability', 50),
                'adjusted_probability': brooks_result.get('adjusted_probability', 50),
                'probability_adjustments': brooks_result.get('probability_adjustments', []),
                'bar_reading': brooks_result.get('bar_reading', []),
                'trap_risk': brooks_result.get('trap_risk', 'UNKNOWN'),
                'trap_explanation': brooks_result.get('trap_explanation', ''),
                'entry': brooks_result.get('entry'),
                'stop': brooks_result.get('stop'),
                'target': brooks_result.get('target'),
                'risk_reward_ratio': brooks_result.get('risk_reward_ratio'),
                'commentary': brooks_result.get('commentary', ''),
                # Phase 2 enhanced fields
                'trap_type': brooks_result.get('trap_type', 'none'),
                'trap_classification': brooks_result.get('trap_classification', {}),
                'trend_evolution': brooks_result.get('trend_evolution', {}),
                'climax_detection': brooks_result.get('climax_detection', {}),
                'confirmation_status': brooks_result.get('confirmation_status', {}),
                'measured_move_targets': brooks_result.get('measured_move_targets', {}),
                'micro_channel': brooks_result.get('micro_channel', {}),
                'spike_and_channel': brooks_result.get('spike_and_channel', {}),
                'bars_detailed': brooks_result.get('bars_detailed', {}),
                'probability_narrative': brooks_result.get('probability_narrative', ''),
                'lesson': brooks_result.get('lesson', ''),
                'pattern_lesson': brooks_result.get('pattern_lesson', {}),
            }
        else:
            result['al_brooks'] = {
                'error': 'AlBrooksAnalyzer not available',
                'note': 'Scanner analyzer module not loaded',
            }
    except Exception as e:
        result['al_brooks'] = {
            'error': f'Al Brooks analysis failed: {str(e)}',
            'interpretation': 'Al Brooks analysis unavailable',
        }

    # Multi-timeframe Brooks (weekly + monthly + confluence)
    try:
        if _analyzer_available:
            monthly_df = _get_ohlcv_cached_multitimeframe(ticker, "OneMonth", "5y")
            weekly_df = _get_ohlcv_cached_multitimeframe(ticker, "OneWeek", "2y")

            # Monthly trend from indicators
            monthly_trend = None
            if monthly_df is not None and not monthly_df.empty and len(monthly_df) >= 5:
                try:
                    monthly_ind = TechnicalAnalysis.calculate_comprehensive_indicators(monthly_df)
                    ma_trend = monthly_ind.get("moving_averages", {}).get("trend", "").lower()
                    macd_trend = monthly_ind.get("macd", {}).get("trend", "").lower()
                    if "bullish" in ma_trend or "bullish" in macd_trend:
                        monthly_trend = "BULLISH"
                    elif "bearish" in ma_trend or "bearish" in macd_trend:
                        monthly_trend = "BEARISH"
                    else:
                        monthly_trend = "MIXED"
                except Exception:
                    pass

            # Weekly Brooks analysis
            weekly_brooks = None
            weekly_indicators = None
            if weekly_df is not None and not weekly_df.empty and len(weekly_df) >= 10:
                try:
                    brooks_mtf = AlBrooksAnalyzer()
                    weekly_brooks = brooks_mtf.analyze_weekly(
                        ticker=ticker, weekly_ohlcv=weekly_df,
                    )
                    weekly_indicators = TechnicalAnalysis.calculate_comprehensive_indicators(weekly_df)
                except Exception as e:
                    logger.warning(f"Weekly Brooks failed for {ticker}: {e}")

            # Daily Brooks for confluence (reuse what we already computed)
            daily_brooks_for_confluence = result.get('al_brooks', {})

            # Confluence scoring
            confluence = calculate_timeframe_confluence(
                monthly_trend=monthly_trend,
                weekly_analysis=weekly_brooks,
                daily_analysis=daily_brooks_for_confluence,
                weekly_indicators=weekly_indicators,
                daily_indicators=indicators,
            )

            result['multi_timeframe_brooks'] = {
                'monthly_trend': monthly_trend or "UNKNOWN",
                'weekly_always_in': weekly_brooks.get("weekly_always_in", "UNKNOWN") if weekly_brooks else "UNKNOWN",
                'weekly_pattern': weekly_brooks.get("weekly_pattern", "UNKNOWN") if weekly_brooks else "UNKNOWN",
                'weekly_pattern_description': weekly_brooks.get("weekly_pattern_description", "") if weekly_brooks else "",
                'weekly_trend_strength': weekly_brooks.get("weekly_trend_strength", "UNKNOWN") if weekly_brooks else "UNKNOWN",
                'weekly_bar_reading': weekly_brooks.get("weekly_bar_reading", []) if weekly_brooks else [],
                'daily_always_in': result.get('al_brooks', {}).get('always_in_direction', 'UNKNOWN'),
                'confluence_score': confluence.get("confluence_score", 0),
                'confluence_grade': confluence.get("confluence_grade", "N/A"),
                'alignment': confluence.get("alignment", "UNKNOWN"),
                'conflicts': confluence.get("conflicts", []),
                'swing_suitability': confluence.get("swing_suitability", "UNKNOWN"),
                'recommendation': confluence.get("recommendation", ""),
            }
    except Exception as e:
        logger.warning(f"Multi-timeframe Brooks failed for {ticker}: {e}")

    # Trend Strength Score (0-100) with statistical validation
    if include_trend_score:
        try:
            trend_analysis = TechnicalAnalysis.calculate_trend_strength(history)
            result['trend_strength'] = trend_analysis

            try:
                prices = history['Close']
                if not isinstance(prices.index, pd.DatetimeIndex):
                    prices = prices.copy()
                    prices.index = pd.to_datetime(prices.index)

                trend_result = get_trend_scanning_labels(
                    prices=prices, lookforward_window=20, t_stat_threshold=1.96,
                )

                if trend_result is not None and len(trend_result.labels) > 0:
                    t_stat = float(trend_result.t_statistics.iloc[-1])
                    p_value = float(trend_result.p_values.iloc[-1])
                    trend_label = int(trend_result.labels.iloc[-1])
                    confidence = 1 - p_value

                    if abs(t_stat) > 2.58:
                        significance = "HIGHLY SIGNIFICANT (99%)"
                    elif abs(t_stat) > 1.96:
                        significance = "STATISTICALLY SIGNIFICANT (95%)"
                    elif abs(t_stat) > 1.645:
                        significance = "MODERATELY SIGNIFICANT (90%)"
                    else:
                        significance = "NOT SIGNIFICANT"

                    trend_direction = "UPTREND" if trend_label == 1 else "DOWNTREND" if trend_label == -1 else "NEUTRAL"

                    result['trend_strength']['statistical_validation'] = {
                        't_statistic': float(t_stat),
                        'p_value': float(p_value),
                        'confidence': float(confidence),
                        'significance': significance,
                        'trend_direction': trend_direction,
                        'interpretation': (
                            f"{trend_direction} with {confidence:.1%} confidence. "
                            f"{'Trend is statistically robust' if abs(t_stat) > 1.96 else 'Trend may be noise - use caution'}."
                        ),
                    }
                else:
                    result['trend_strength']['statistical_validation'] = {
                        'note': 'Insufficient data for statistical validation',
                    }
            except Exception as stat_e:
                result['trend_strength']['statistical_validation'] = {
                    'error': f'Statistical validation failed: {str(stat_e)}',
                }
        except Exception as e:
            result['trend_strength'] = {
                'error': f'Trend strength analysis failed: {str(e)}',
            }

    return convert_numpy_types(result)


def analyze_multitimeframe_impl(
    ticker: str,
    include_brooks: bool = True,
) -> dict:
    """
    Full multi-timeframe analysis: Monthly → Weekly → Daily.

    Returns indicators, Brooks weekly analysis, S/R, and confluence score.
    """
    ticker = validate_ticker(ticker)

    # Fetch data top-down: monthly first, then weekly, then daily
    monthly_df = _get_ohlcv_cached_multitimeframe(ticker, "OneMonth", "5y")
    weekly_df = _get_ohlcv_cached_multitimeframe(ticker, "OneWeek", "2y")
    daily_df = _get_ohlcv_cached(ticker, period="6mo")

    if daily_df is None or daily_df.empty:
        raise ValueError(f"No daily data found for {ticker}")

    # Multi-timeframe indicators
    mtf_indicators = TechnicalAnalysis.calculate_multitimeframe_indicators(
        daily_df=daily_df,
        weekly_df=weekly_df if weekly_df is not None and not weekly_df.empty else None,
        monthly_df=monthly_df if monthly_df is not None and not monthly_df.empty else None,
    )

    # Multi-timeframe S/R
    mtf_sr = TechnicalAnalysis.find_support_resistance_multitimeframe(
        daily_df=daily_df,
        weekly_df=weekly_df if weekly_df is not None and not weekly_df.empty else None,
    )

    result = {
        "symbol": ticker,
        "timeframes_available": {
            "daily": daily_df is not None and not daily_df.empty,
            "weekly": weekly_df is not None and not weekly_df.empty,
            "monthly": monthly_df is not None and not monthly_df.empty,
        },
        "data_points": {
            "daily": len(daily_df) if daily_df is not None else 0,
            "weekly": len(weekly_df) if weekly_df is not None and not weekly_df.empty else 0,
            "monthly": len(monthly_df) if monthly_df is not None and not monthly_df.empty else 0,
        },
        "indicators": mtf_indicators,
        "support_resistance": mtf_sr,
    }

    # Weekly Brooks analysis
    weekly_brooks = None
    daily_brooks = None
    if include_brooks and _analyzer_available:
        brooks = AlBrooksAnalyzer()

        if weekly_df is not None and not weekly_df.empty and len(weekly_df) >= 10:
            weekly_brooks = brooks.analyze_weekly(
                ticker=ticker,
                weekly_ohlcv=weekly_df,
                weekly_technical=mtf_indicators.get("weekly"),
            )
            result["weekly_brooks"] = weekly_brooks

        # Daily Brooks for confluence
        try:
            ma_trend = mtf_indicators.get("daily", {}).get("moving_averages", {}).get("trend", "neutral")
            macd_trend = mtf_indicators.get("daily", {}).get("macd", {}).get("trend", "neutral")
            direction = "long" if "bullish" in str(ma_trend).lower() or "bullish" in str(macd_trend).lower() else "short"
            daily_brooks_result = brooks.analyze(
                ticker=ticker, direction=direction,
                ohlcv_data=daily_df, technical_data=mtf_indicators.get("daily", {}),
            )
            daily_brooks = daily_brooks_result
            result["daily_brooks"] = {
                "always_in_direction": daily_brooks_result.get("always_in", "UNKNOWN"),
                "pattern": daily_brooks_result.get("pattern", "none"),
                "pattern_description": daily_brooks_result.get("pattern_description", ""),
                "bar_reading": daily_brooks_result.get("bar_reading", []),
                "trap_risk": daily_brooks_result.get("trap_risk", "UNKNOWN"),
            }
        except Exception as e:
            logger.warning(f"Daily Brooks failed for {ticker}: {e}")

    # Monthly trend from indicators
    monthly_trend = None
    if mtf_indicators.get("monthly") and mtf_indicators["monthly"].get("trend_summary"):
        monthly_trend = mtf_indicators["monthly"]["trend_summary"].get("direction")

    # Confluence scoring
    if _analyzer_available:
        confluence = calculate_timeframe_confluence(
            monthly_trend=monthly_trend,
            weekly_analysis=weekly_brooks,
            daily_analysis=daily_brooks,
            weekly_indicators=mtf_indicators.get("weekly"),
            daily_indicators=mtf_indicators.get("daily"),
        )
        result["timeframe_confluence"] = confluence

    return convert_numpy_types(result)


def find_support_resistance_impl(
    ticker: str,
    lookback_period: str = "3mo",
) -> dict:
    """Identify key support and resistance levels."""
    ticker = validate_ticker(ticker)

    history = _get_ohlcv_cached(ticker, period=lookback_period)
    if history is None or history.empty:
        raise ValueError(f"No historical data found for {ticker}")

    levels = TechnicalAnalysis.find_support_resistance(history)
    return convert_numpy_types({"symbol": ticker, "lookback_period": lookback_period, **levels})


def analyze_volume_tool_impl(
    ticker: str,
    period: str = "3mo",
    vwap_mode: str = "session",
    include_quality_score: bool = True,
) -> dict:
    """Comprehensive volume analysis with optional quality score."""
    ticker = validate_ticker(ticker)
    result = analyze_volume(ticker, period, vwap_mode)

    if include_quality_score:
        try:
            history = _get_ohlcv_cached(ticker, period=period)
            if history is not None and not history.empty:
                closes = history['Close'].values
                volumes = history['Volume'].values

                # Volume trend (slope)
                if len(volumes) >= 20:
                    recent_vol = np.mean(volumes[-10:])
                    older_vol = np.mean(volumes[-20:-10])
                    vol_trend = "INCREASING" if recent_vol > older_vol * 1.1 else "DECREASING" if recent_vol < older_vol * 0.9 else "STABLE"
                else:
                    vol_trend = "INSUFFICIENT_DATA"

                # Price-volume relationship
                if len(closes) >= 10 and len(volumes) >= 10:
                    price_change = (closes[-1] - closes[-10]) / closes[-10]
                    vol_change = (np.mean(volumes[-5:]) - np.mean(volumes[-10:-5])) / max(np.mean(volumes[-10:-5]), 1)

                    if price_change > 0 and vol_change > 0:
                        accumulation_ratio = min(abs(price_change * vol_change) * 100, 1.0)
                    elif price_change < 0 and vol_change > 0:
                        accumulation_ratio = -min(abs(price_change * vol_change) * 100, 1.0)
                    else:
                        accumulation_ratio = 0.0

                    # Volume confirmation
                    if abs(accumulation_ratio) > 0.3:
                        confirmation = "STRONG"
                    elif abs(accumulation_ratio) > 0.1:
                        confirmation = "MODERATE"
                    elif abs(accumulation_ratio) > 0.05:
                        confirmation = "NORMAL"
                    else:
                        confirmation = "WEAK"

                    # Accumulation / Distribution days
                    acc_days = sum(1 for i in range(-min(20, len(closes)), 0)
                                  if closes[i] > closes[i-1] and volumes[i] > np.mean(volumes[-20:]))
                    dist_days = sum(1 for i in range(-min(20, len(closes)), 0)
                                   if closes[i] < closes[i-1] and volumes[i] > np.mean(volumes[-20:]))

                    interpretation = f"{'Accumulation' if accumulation_ratio > 0.1 else 'Distribution' if accumulation_ratio < -0.1 else 'Neutral'} detected with {confirmation} volume confirmation"

                    result['volume_quality_score'] = {
                        'smart_money_probability': float(abs(accumulation_ratio)),
                        'accumulation_detected': accumulation_ratio > 0.1,
                        'distribution_detected': accumulation_ratio < -0.1,
                        'volume_confirmation': confirmation,
                        'accumulation_days': int(acc_days),
                        'distribution_days': int(dist_days),
                        'volume_trend': vol_trend,
                        'interpretation': interpretation,
                    }
                else:
                    result['volume_quality_score'] = {
                        'note': 'Insufficient data for quality score',
                        'interpretation': 'Volume quality analysis unavailable',
                    }
            else:
                result['volume_quality_score'] = {
                    'note': 'Insufficient data for quality score',
                    'interpretation': 'Volume quality analysis unavailable',
                }
        except Exception as e:
            result['volume_quality_score'] = {
                'error': f'Quality score calculation failed: {str(e)}',
                'interpretation': 'Volume quality analysis unavailable',
            }

    return convert_numpy_types(result)


def analyze_volatility_tool_impl(
    ticker: str,
    period: str = "6mo",
) -> dict:
    """Comprehensive volatility analysis with ATR, HV, beta, and position sizing."""
    ticker = validate_ticker(ticker)
    return convert_numpy_types(analyze_volatility(ticker, period))


def calculate_relative_strength_tool_impl(
    ticker: str,
    benchmark: str = "SPY",
    period: str = "3mo",
) -> dict:
    """IBD-style relative strength rating (0-100) vs benchmark."""
    ticker = validate_ticker(ticker)
    benchmark = validate_ticker(benchmark)
    return convert_numpy_types(calculate_relative_strength(ticker, benchmark, period))


def calculate_fundamental_scores_tool_impl(
    ticker: str,
    max_periods: int = 8,
) -> dict:
    """Piotroski F-Score and Altman Z-Score analysis."""
    ticker = validate_ticker(ticker)
    return convert_numpy_types(calculate_fundamental_scores(ticker, max_periods))


def register_tools(mcp):

    # Advanced Technical Analysis Tools
    if _advanced_ta_available:
        @mcp.tool()
        def analyze_technical(
            ticker: str,
            period: Literal["3mo", "6mo", "1y", "2y"] = "6mo",
            include_ml_analysis: bool = True,
            include_trend_score: bool = True
        ) -> dict[str, Any]:
            """Perform comprehensive technical analysis with RSI, MACD, Bollinger Bands, Moving Averages, and Stochastic indicators.

            Returns detailed technical indicators including:
            - RSI (Relative Strength Index) with overbought/oversold signals
            - MACD (Moving Average Convergence Divergence) with trend analysis
            - Bollinger Bands with price position
            - Multiple Moving Averages (SMA 20/50/200, EMA 20)
            - Stochastic Oscillator
            - ML Probability Analysis (if include_ml_analysis=True)
            - Al Brooks Price Action Analysis (pattern, probability, bar reading, trap risk)
            - Trend Strength Score 0-100 with statistical validation (if include_trend_score=True)

            Note: Trend strength scoring with statistical validation (t-statistic, p-value,
            confidence levels) is now included here. This replaces the standalone
            analyze_trend_strength tool. Output appears in result['trend_strength'].
            """
            return analyze_technical_impl(ticker, period, include_ml_analysis, include_trend_score)

        @mcp.tool()
        def analyze_multitimeframe(
            ticker: str,
            include_brooks: bool = True,
        ) -> dict[str, Any]:
            """Multi-timeframe analysis: Monthly trend → Weekly structure → Daily setup.

            Top-down analysis order for swing trading accuracy:
            - Monthly trend context (SMA 10/20, RSI, MACD)
            - Weekly Al Brooks bar reading (Always-In, pattern, trend strength)
            - Weekly support/resistance (stronger than daily levels)
            - Daily indicators for entry timing
            - Timeframe confluence score (0-100) with grade A-F
            - Swing suitability rating (HIGH/MODERATE/LOW/AVOID)

            Use this for swing/position trades where weekly alignment matters.
            """
            return analyze_multitimeframe_impl(ticker, include_brooks)

        @mcp.tool()
        def find_support_resistance(
            ticker: str,
            lookback_period: Literal["1mo", "3mo", "6mo"] = "3mo"
        ) -> dict[str, Any]:
            """Identify key support and resistance levels based on recent price action.

            Uses local extrema detection to find:
            - Top 3 resistance levels (price ceilings)
            - Top 3 support levels (price floors)
            - Nearest support and resistance to current price
            """
            return find_support_resistance_impl(ticker, lookback_period)

        @mcp.tool()
        def compare_technical(
            tickers: list[str],
            period: Literal["1mo", "3mo", "6mo"] = "3mo"
        ) -> dict[str, Any]:
            """Compare technical indicators across multiple stocks side-by-side.

            Provides a comparison table showing:
            - Current price
            - RSI value and signal
            - MACD trend
            - Moving average trend
            - Bollinger Bands position

            Useful for quickly comparing the technical health of multiple stocks.
            """
            tickers = [validate_ticker(t) for t in tickers[:10]]

            comparisons = []
            for t in tickers:
                try:
                    history = _get_ohlcv_cached(t, period=period)
                    if history is None or history.empty:
                        comparisons.append({"symbol": t, "error": "No data available"})
                        continue
                    indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)
                    comparisons.append({
                        "symbol": t,
                        "price": indicators['current_price'],
                        "rsi": indicators['rsi']['value'],
                        "rsi_signal": indicators['rsi']['signal'],
                        "macd_trend": indicators['macd']['trend'],
                        "ma_trend": indicators['moving_averages']['trend'],
                        "bb_position": indicators['bollinger_bands']['position'],
                    })
                except Exception as e:
                    comparisons.append({"symbol": t, "error": str(e)})

            return convert_numpy_types({"period": period, "comparison": comparisons})

    # 4 NEW bootstrap tools (previously only in server.py)
    if _bootstrap_available:
        @mcp.tool()
        def analyze_volume_tool(
            ticker: str,
            period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "3mo",
            vwap_mode: Literal["session", "rolling", "anchored"] = "session",
            include_quality_score: bool = True
        ) -> dict[str, Any]:
            """Comprehensive volume analysis with VWAP, OBV, CVD, and Dalio metrics.

            Includes multi-VWAP analysis, liquidity zones, institutional activity
            detection, and optional ML-based volume quality scoring.
            """
            return analyze_volume_tool_impl(ticker, period, vwap_mode, include_quality_score)

        @mcp.tool()
        def analyze_volatility_tool(
            ticker: str,
            period: Literal["3mo", "6mo", "1y", "2y"] = "6mo"
        ) -> dict[str, Any]:
            """Comprehensive volatility analysis with ATR, HV, beta, and position sizing.

            Returns ATR (14/20), historical volatility, volatility percentile/regime,
            beta vs SPY, Keltner Channels, Bollinger width, and stop loss recommendations.
            """
            return analyze_volatility_tool_impl(ticker, period)

        @mcp.tool()
        def calculate_relative_strength_tool(
            ticker: str,
            benchmark: str = "SPY",
            period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "3mo"
        ) -> dict[str, Any]:
            """IBD-style relative strength rating (0-100) vs benchmark.

            Returns RS score, trend, classification (LEADER/LAGGARD),
            outperformance %, and trading recommendation.
            """
            return calculate_relative_strength_tool_impl(ticker, benchmark, period)

        @mcp.tool()
        def calculate_fundamental_scores_tool(
            ticker: str,
            max_periods: int = 8
        ) -> dict[str, Any]:
            """Piotroski F-Score (0-9) and Altman Z-Score for bankruptcy risk.

            Returns F-Score components, Z-Score with zone classification,
            financial ratios, and overall assessment.
            """
            return calculate_fundamental_scores_tool_impl(ticker, max_periods)
