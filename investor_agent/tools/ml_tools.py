"""
ML-enhanced analysis tools: similarity-based backtesting, ML-enhanced technical analysis,
strategy robustness validation, and feature importance analysis.
"""
import logging
from typing import Literal

import numpy as np
import pandas as pd

from ..core.validation import validate_ticker
from ..core.price import yf_call, convert_numpy_types
from ..ml_core import (
    apply_triple_barrier_labels,
    get_trend_scanning_labels,
    calculate_kelly_size,
    calculate_deflated_sharpe,
    calculate_feature_importance,
)
from ..ml_validation import harvey_liu_zhu_threshold
from ..backtesting import SimilarityEngine, generate_similarity_report
from ..technical.indicators import (
    detect_ema_bounce,
    detect_ema_cross,
    detect_ema_extension,
    detect_vwap_bounce,
    detect_vwap_cross,
    interpret_vwap_position,
    detect_volume_surge,
    calculate_obv_signal,
    confirm_crossover_with_volume,
    detect_ema_vwap_confluence,
    detect_order_blocks,
    detect_supply_demand_zones,
)

# Import bootstrap functions
try:
    from ..technical_analysis_bootstrap import calculate_exhaustion_score
    _bootstrap_available = True
except ImportError:
    _bootstrap_available = False

logger = logging.getLogger(__name__)


def find_similar_historical_setups_impl(
    ticker: str,
    lookback_period: Literal["6mo", "1y", "2y"] = "2y",
    similarity_threshold: float = 0.80,
    use_feature_importance: bool = True,
    target_return_pct: float | None = None,
    holding_period_days: int | None = None,
    direction: Literal["LONG", "SHORT"] = "LONG"
) -> dict:
    """Find historical setups similar to current TECHNICAL conditions.

    Returns dict with report + structured metrics (similar_setups_found,
    success_rate_5d, average_return_5d, statistical_confidence, etc.).
    """
    from .scanning import _get_ohlcv_cached

    ticker = validate_ticker(ticker)

    # Map period to number of days
    period_map = {"6mo": 126, "1y": 252, "2y": 504}
    lookback_days = period_map[lookback_period]

    # Get historical data (Questrade primary, Yahoo fallback, cached)
    hist = _get_ohlcv_cached(ticker, period=lookback_period)

    if hist.empty or len(hist) < 50:
        return {"error": f"Insufficient historical data for {ticker}"}

    # CRITICAL FIX: Remove timezone for backtesting (AMZN fix)
    if isinstance(hist.index, pd.DatetimeIndex) and hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)

    # Get earnings dates for earnings context matching
    earnings_dates = None
    try:
        earnings_history = yf_call(ticker, "get_earnings_history")
        if earnings_history is not None and isinstance(earnings_history, pd.DataFrame) and not earnings_history.empty:
            if hasattr(earnings_history.index, 'to_list'):
                earnings_dates = [pd.Timestamp(d) for d in earnings_history.index.to_list()]
            logger.info(f"Found {len(earnings_dates) if earnings_dates else 0} earnings dates for {ticker}")
    except Exception as e:
        logger.warning(f"Could not fetch earnings history for {ticker}: {e}")
        earnings_dates = None

    engine = SimilarityEngine(
        similarity_threshold=similarity_threshold,
        min_similar_setups=5
    )

    current_idx = len(hist) - 1
    current_conditions = engine._calculate_conditions(hist, current_idx, earnings_dates)

    if not current_conditions:
        return {"error": f"Insufficient data to calculate current technical conditions for {ticker}"}

    # Get feature importance weights if requested
    feature_weights = None
    if use_feature_importance:
        try:
            prices = hist['Close']
            forward_returns = prices.shift(-10) / prices - 1

            feature_matrix = []
            valid_indices = []

            for idx in range(50, len(hist) - 10):
                conditions = engine._calculate_conditions(hist, idx)
                if conditions and not pd.isna(forward_returns.iloc[idx]):
                    numerical_features = {
                        k: v for k, v in conditions.items()
                        if not isinstance(v, str)
                    }
                    feature_matrix.append(numerical_features)
                    valid_indices.append(idx)

            if len(feature_matrix) > 30:
                features_df = pd.DataFrame(feature_matrix)
                returns = forward_returns.iloc[valid_indices]

                importances = calculate_feature_importance(
                    features_df, returns, method='spearman'
                )

                total_importance = sum(abs(imp) for imp in importances.values())
                if total_importance > 0:
                    feature_weights = {
                        k: abs(v) / total_importance
                        for k, v in importances.items()
                    }

                logger.info(f"Calculated feature importance for {ticker}: {feature_weights}")
            else:
                logger.warning(f"Insufficient samples for feature importance ({len(feature_matrix)} < 30), using defaults")

        except Exception as e:
            logger.warning(f"Could not calculate feature importance: {e}, using defaults")
            feature_weights = None

    similar_setups = engine.find_similar_setups(
        ticker=ticker,
        current_conditions=current_conditions,
        historical_data=hist,
        lookback_periods=min(lookback_days, len(hist) - 20),
        feature_weights=feature_weights,
        target_return_pct=target_return_pct,
        holding_period_days=holding_period_days,
        direction=direction,
        earnings_dates=earnings_dates
    )

    result = engine.analyze_similar_setups(
        ticker=ticker,
        current_conditions=current_conditions,
        similar_setups=similar_setups,
        target_return_pct=target_return_pct,
        holding_period_days=holding_period_days,
        direction=direction
    )

    report = generate_similarity_report(result)

    if feature_weights:
        sorted_features = sorted(feature_weights.items(), key=lambda x: x[1], reverse=True)

        feature_section = "\n## Feature Importance Weights Used\n\n"
        feature_section += "**Top Features in Similarity Matching:**\n"

        for feature, weight in sorted_features[:5]:
            feature_section += f"- **{feature}:** {weight:.1%} weight\n"

        feature_section += "\n*Similarity matching weighted by feature importance - " \
                          "important features (RSI, trend) have more influence than less predictive features.*\n"

        report = report.replace(
            "---\n*Generated with institutional-grade similarity-based backtesting*",
            f"{feature_section}\n---\n*Generated with feature-weighted institutional-grade similarity-based backtesting*"
        )

    # Build structured return dict
    agg = result.aggregate_statistics
    rec = result.recommendation
    val = result.statistical_validation

    return convert_numpy_types({
        "report": report,
        "similar_setups_found": agg.get("total_similar", 0),
        "success_rate_5d": round(agg.get("success_rate_5d", 0.0) * 100, 1),
        "average_return_5d": round(agg.get("avg_return_5d", 0.0) * 100, 2),
        "statistical_confidence": rec.get("confidence_label", "N/A"),
        "take_trade": rec.get("take_trade", False),
        "p_value": val.get("p_value", None),
        "statistically_significant": val.get("significant_at_05", False),
    })


def register_tools(mcp):
    @mcp.tool()
    def find_similar_historical_setups(
        ticker: str,
        lookback_period: Literal["6mo", "1y", "2y"] = "2y",
        similarity_threshold: float = 0.80,
        use_feature_importance: bool = True,
        target_return_pct: float | None = None,
        holding_period_days: int | None = None,
        direction: Literal["LONG", "SHORT"] = "LONG"
    ) -> dict:
        """
        Find historical setups similar to current TECHNICAL conditions with target achievement analysis.

        **CRITICAL:** Matches on TECHNICAL INDICATORS (RSI, MACD, trend, volume),
        NOT on price levels. Uses tolerance-based matching with feature importance weighting.

        **NEW:** Calculates TARGET ACHIEVEMENT - how well similar setups achieved a specific target.
        This is NOT binary win/loss, but a percentage of target achieved.
        - Example: Target +5% in 10 days, actual +6% = 120% achievement
        - Example: Target +5% in 10 days, actual +4% = 80% achievement

        Args:
            ticker: Stock symbol
            lookback_period: How far back to search (6mo/1y/2y)
            similarity_threshold: Minimum similarity score 0-1 (default 0.80)
            use_feature_importance: Use calculated feature weights (default True)
            target_return_pct: Target return % for trade plan (e.g., 5.0 for 5%)
                              If provided with holding_period_days, calculates achievement
            holding_period_days: Number of trading days to hold (e.g., 10)
                                Required if target_return_pct is provided
            direction: Trade direction 'LONG' or 'SHORT' (default 'LONG')
                      LONG: positive returns are good
                      SHORT: negative returns are good (price going down)

        Returns:
            Dict with report + structured metrics for programmatic consumption.

        References:
            - López de Prado (2018): Feature-weighted similarity
            - Multi-indicator confluence research (85% accuracy)
        """
        return find_similar_historical_setups_impl(
            ticker=ticker,
            lookback_period=lookback_period,
            similarity_threshold=similarity_threshold,
            use_feature_importance=use_feature_importance,
            target_return_pct=target_return_pct,
            holding_period_days=holding_period_days,
            direction=direction,
        )

    @mcp.tool()
    def analyze_ml_enhanced(
        ticker: str,
        period: Literal["3mo", "6mo", "1y"] = "6mo"
    ) -> dict:
        """
        ML-enhanced technical analysis with probability-based predictions.

        Combines traditional indicators with institutional ML methods:
        - Triple-Barrier labeling for success rate calculation
        - Trend-Scanning for statistical trend confidence
        - EMA crossover signals (20/50/100/200 crosses)
        - Kelly sizing for optimal position sizing

        Args:
            ticker: Stock symbol
            period: Analysis window

        Returns:
            Enhanced analysis with:
            - Historical success rate from triple-barrier method
            - Trend confidence (95% or 99% statistical significance)
            - EMA crossover signals (golden/death crosses)
            - Expected returns and holding periods
            - Kelly-optimal position size
        """
        ticker = validate_ticker(ticker)

        # Get historical data (Questrade primary, Yahoo fallback, cached)
        hist = _get_ohlcv_cached(ticker, period=period)

        if hist is None or hist.empty or len(hist) < 50:
            return {"error": f"Insufficient data for {ticker}"}

        # Ensure hist has tz-naive DatetimeIndex (required by ML functions and VWAP calculations)
        if not isinstance(hist.index, pd.DatetimeIndex):
            try:
                hist.index = pd.to_datetime(hist.index, utc=True).tz_localize(None)
            except Exception as e:
                return {"error": f"Could not convert index to DatetimeIndex for {ticker}: {e}"}
        elif hist.index.tz is not None:
            # Remove timezone info if present (ML functions expect tz-naive)
            hist.index = hist.index.tz_localize(None)

        prices = hist['Close']

        # 1. Triple-Barrier Analysis
        tb_result = apply_triple_barrier_labels(
            prices,
            profit_target=0.05,
            stop_loss=0.05,
            max_holding_days=10
        )

        # 2. Trend-Scanning Analysis
        ts_result = get_trend_scanning_labels(
            prices,
            lookforward_window=20,
            t_stat_threshold=1.96
        )

        # 3. EMA Crossover Analysis (CRITICAL TRADING SIGNALS)
        ema_20 = prices.ewm(span=20, adjust=False).mean().iloc[-1]
        ema_50 = prices.ewm(span=50, adjust=False).mean().iloc[-1] if len(prices) >= 50 else ema_20
        ema_100 = prices.ewm(span=100, adjust=False).mean().iloc[-1] if len(prices) >= 100 else ema_50
        ema_200 = prices.ewm(span=200, adjust=False).mean().iloc[-1] if len(prices) >= 200 else ema_100

        current_price = prices.iloc[-1]

        # Detect crossovers (looking back 5 days for recent crosses)
        ema_20_series = prices.ewm(span=20, adjust=False).mean()
        ema_50_series = prices.ewm(span=50, adjust=False).mean() if len(prices) >= 50 else ema_20_series
        ema_100_series = prices.ewm(span=100, adjust=False).mean() if len(prices) >= 100 else ema_50_series
        ema_200_series = prices.ewm(span=200, adjust=False).mean() if len(prices) >= 200 else ema_100_series

        # Detect 20/50 cross
        cross_20_50 = "NONE"
        if len(prices) >= 50:
            for i in range(1, min(6, len(ema_20_series))):
                prev_20 = ema_20_series.iloc[-i-1]
                prev_50 = ema_50_series.iloc[-i-1]
                curr_20 = ema_20_series.iloc[-1]
                curr_50 = ema_50_series.iloc[-1]

                if prev_20 <= prev_50 and curr_20 > curr_50:
                    cross_20_50 = "BULLISH_CROSS"
                    break
                elif prev_20 >= prev_50 and curr_20 < curr_50:
                    cross_20_50 = "BEARISH_CROSS"
                    break

            if cross_20_50 == "NONE":
                cross_20_50 = "BULLISH" if curr_20 > curr_50 else "BEARISH"

        # Detect 20/100 cross
        cross_20_100 = "NONE"
        if len(prices) >= 100:
            for i in range(1, min(6, len(ema_20_series))):
                prev_20 = ema_20_series.iloc[-i-1]
                prev_100 = ema_100_series.iloc[-i-1]
                curr_20 = ema_20_series.iloc[-1]
                curr_100 = ema_100_series.iloc[-1]

                if prev_20 <= prev_100 and curr_20 > curr_100:
                    cross_20_100 = "BULLISH_CROSS"
                    break
                elif prev_20 >= prev_100 and curr_20 < curr_100:
                    cross_20_100 = "BEARISH_CROSS"
                    break

            if cross_20_100 == "NONE":
                cross_20_100 = "BULLISH" if curr_20 > curr_100 else "BEARISH"

        # Detect 20/200 cross (GOLDEN CROSS / DEATH CROSS)
        cross_20_200 = "NONE"
        golden_cross = False
        death_cross = False
        if len(prices) >= 200:
            for i in range(1, min(6, len(ema_20_series))):
                prev_20 = ema_20_series.iloc[-i-1]
                prev_200 = ema_200_series.iloc[-i-1]
                curr_20 = ema_20_series.iloc[-1]
                curr_200 = ema_200_series.iloc[-1]

                if prev_20 <= prev_200 and curr_20 > curr_200:
                    cross_20_200 = "GOLDEN_CROSS"
                    golden_cross = True
                    break
                elif prev_20 >= prev_200 and curr_20 < curr_200:
                    cross_20_200 = "DEATH_CROSS"
                    death_cross = True
                    break

            if cross_20_200 == "NONE":
                cross_20_200 = "BULLISH" if curr_20 > curr_200 else "BEARISH"

        # EMA alignment (all EMAs in order = strong trend)
        bullish_alignment = (ema_20 > ema_50 > ema_100 > ema_200) if len(prices) >= 200 else False
        bearish_alignment = (ema_20 < ema_50 < ema_100 < ema_200) if len(prices) >= 200 else False

        # 4. Price/EMA Interaction Signals (Dynamic Support/Resistance)
        volumes = hist['Volume'] if 'Volume' in hist.columns else None

        # Detect EMA bounce (price bouncing off EMA as support/resistance)
        ema_bounce_20 = detect_ema_bounce(prices, volumes, ema_period=20)
        ema_bounce_50 = detect_ema_bounce(prices, volumes, ema_period=50)

        # Detect price crossing EMA (breakout/breakdown)
        price_ema_cross_20 = detect_ema_cross(prices, ema_period=20)
        price_ema_cross_50 = detect_ema_cross(prices, ema_period=50)

        # Detect EMA extension (overextended price - reversal warning)
        ema_extension_20 = detect_ema_extension(prices, ema_period=20)

        # 5. VWAP Support/Resistance Signals (Institutional Fair Value)
        if volumes is not None:
            # Detect VWAP bounce (institutional support/resistance)
            vwap_bounce = detect_vwap_bounce(prices, volumes, window=20)

            # Detect price crossing VWAP (sentiment shift)
            vwap_cross = detect_vwap_cross(prices, volumes, window=20)

            # Interpret VWAP position
            vwap_position = interpret_vwap_position(vwap_cross['distance_pct'])
        else:
            # No volume data - set defaults
            vwap_bounce = {'signal': 'NONE', 'vwap_level': 0.0, 'distance_pct': 0.0, 'bounce_days_ago': 0, 'volume_confirmed': False, 'strength': 'NONE'}
            vwap_cross = {'signal': 'NONE', 'vwap_level': 0.0, 'distance_pct': 0.0, 'cross_days_ago': 0}
            vwap_position = {'position': 'UNKNOWN', 'sentiment': 'NEUTRAL', 'interpretation': 'No volume data available'}

        # 6. Volume Confirmation Signals (Smart Money Detection)
        if volumes is not None:
            # Detect volume surge
            volume_surge = detect_volume_surge(volumes, window=20, threshold_pct=0.50)

            # Calculate OBV signals
            obv_result = calculate_obv_signal(prices, volumes)

            # Confirm EMA 20/50 crossover with volume
            ema_cross_volume_conf = confirm_crossover_with_volume(cross_20_50, volume_surge)

            # Confirm VWAP crossover with volume
            vwap_cross_volume_conf = confirm_crossover_with_volume(vwap_cross['signal'], volume_surge)
        else:
            # No volume data - set defaults
            volume_surge = {'signal': 'NORMAL', 'current_volume': 0, 'avg_volume': 0.0, 'volume_ratio': 0.0, 'surge_strength': 'NORMAL'}
            obv_result = {'obv': pd.Series(), 'obv_trend': 'NEUTRAL', 'obv_strength': 0.0, 'divergence': 'NONE', 'signal': 'NEUTRAL'}
            ema_cross_volume_conf = {'confirmed': False, 'confidence': 'LOW', 'explanation': 'No volume data'}
            vwap_cross_volume_conf = {'confirmed': False, 'confidence': 'LOW', 'explanation': 'No volume data'}

        # 7. EMA/VWAP Confluence Detection (Multi-Indicator Alignment)
        current_price = prices.iloc[-1]
        vwap_current = vwap_cross['vwap_level'] if vwap_cross['vwap_level'] > 0 else current_price

        confluence_result = detect_ema_vwap_confluence(
            price=current_price,
            ema_20=ema_20,
            ema_50=ema_50,
            vwap=vwap_current
        )

        # 8. Order Blocks Detection (Institutional Footprints)
        order_blocks_result = detect_order_blocks(
            prices=prices,
            lookback=50,
            impulse_threshold_pct=3.0,
            proximity_pct=2.0
        )

        # 9. Supply/Demand Zones Detection (Price Action Zones)
        supply_demand_result = detect_supply_demand_zones(
            prices=prices,
            lookback=50,
            consolidation_bars=3,
            impulse_threshold_pct=5.0,
            proximity_pct=2.0
        )

        # 10. Exhaustion Score Analysis (Volumetric Liquidity Enhancement)
        try:
            exhaustion_result = calculate_exhaustion_score(ticker, period=period) if _bootstrap_available else {"score": 0, "level": "UNKNOWN"}
        except Exception as e:
            logger.warning(f"Exhaustion score failed for {ticker}: {e}")
            exhaustion_result = {"score": 0, "level": "UNKNOWN"}
        exhaustion_long = exhaustion_result.get('long_exhaustion', {"score": 0, "level": "UNKNOWN", "components": {}})
        exhaustion_short = exhaustion_result.get('short_exhaustion', {"score": 0, "level": "UNKNOWN", "components": {}})
        exhaustion_long['interpretation'] = exhaustion_result.get('interpretation', '')
        exhaustion_short['interpretation'] = exhaustion_result.get('interpretation', '')

        # Determine which direction is more relevant based on current trend
        current_trend_direction = "LONG" if ts_result.labels.iloc[-1] >= 0 else "SHORT"
        primary_exhaustion = exhaustion_long if current_trend_direction == "LONG" else exhaustion_short

        # 11. Calculate Kelly size (using triple-barrier success rate)
        if tb_result.success_rate > 0.5:
            expected_return = tb_result.avg_profit if tb_result.avg_profit > 0 else 0.03
            volatility = prices.pct_change().std()
            kelly_size = calculate_kelly_size(
                predicted_prob=tb_result.success_rate,
                predicted_return=expected_return,
                volatility=volatility,
                kelly_fraction=0.25
            )
        else:
            kelly_size = 0.0

        # Build comprehensive recommendation (now 19 signals - added Exhaustion)
        bullish_signals = sum([
            # ML Signals (2)
            tb_result.success_rate > 0.55,
            ts_result.confidence.iloc[-1] > 0.90 and ts_result.labels.iloc[-1] == 1,
            # EMA/EMA Crossovers (4)
            cross_20_50 in ["BULLISH_CROSS", "BULLISH"],
            cross_20_100 in ["BULLISH_CROSS", "BULLISH"],
            cross_20_200 in ["GOLDEN_CROSS", "BULLISH"],
            bullish_alignment,
            # Price/EMA Interactions (3)
            ema_bounce_20['signal'] == 'BULLISH_BOUNCE' or ema_bounce_50['signal'] == 'BULLISH_BOUNCE',
            price_ema_cross_20['signal'] in ['BULLISH_CROSS', 'ABOVE'],
            ema_extension_20['signal'] != 'OVEREXTENDED_UP',  # Not overextended upward = healthy for LONG
            # VWAP Signals (3)
            vwap_bounce['signal'] == 'VWAP_BOUNCE_SUPPORT',
            vwap_cross['signal'] in ['BULLISH_VWAP_CROSS', 'ABOVE_VWAP'],
            vwap_position['sentiment'] in ['STRONG_BULLISH', 'BULLISH'],
            # Volume Confirmation Signals (3)
            volume_surge['signal'] == 'VOLUME_SURGE',
            obv_result['signal'] == 'BULLISH',
            obv_result['divergence'] == 'BULLISH_DIVERGENCE' or ema_cross_volume_conf['confirmed'] or vwap_cross_volume_conf['confirmed'],
            # EMA/VWAP Confluence (1)
            confluence_result['signal'] in ['STRONG_BULLISH_CONFLUENCE', 'BULLISH_CONFLUENCE'],
            # Order Blocks (1)
            order_blocks_result['signal'] == 'BULLISH_ORDER_BLOCK_TEST',
            # Supply/Demand Zones (1)
            supply_demand_result['signal'] == 'DEMAND_ZONE_TEST',
            # Exhaustion (1) - Low exhaustion for LONG = bullish
            exhaustion_long.get('level', '') in ['NO_EXHAUSTION', 'LOW_EXHAUSTION']
        ])

        bearish_signals = sum([
            # ML Signals (2)
            tb_result.success_rate < 0.45,
            ts_result.confidence.iloc[-1] > 0.90 and ts_result.labels.iloc[-1] == -1,
            # EMA/EMA Crossovers (4)
            cross_20_50 in ["BEARISH_CROSS", "BEARISH"],
            cross_20_100 in ["BEARISH_CROSS", "BEARISH"],
            cross_20_200 in ["DEATH_CROSS", "BEARISH"],
            bearish_alignment,
            # Price/EMA Interactions (3)
            ema_bounce_20['signal'] == 'BEARISH_BOUNCE' or ema_bounce_50['signal'] == 'BEARISH_BOUNCE',
            price_ema_cross_20['signal'] in ['BEARISH_CROSS', 'BELOW'],
            ema_extension_20['signal'] != 'OVEREXTENDED_DOWN',  # Not overextended downward = healthy for SHORT
            # VWAP Signals (3)
            vwap_bounce['signal'] == 'VWAP_BOUNCE_RESISTANCE',
            vwap_cross['signal'] in ['BEARISH_VWAP_CROSS', 'BELOW_VWAP'],
            vwap_position['sentiment'] in ['STRONG_BEARISH', 'BEARISH'],
            # Volume Confirmation Signals (3)
            volume_surge['signal'] == 'LOW_VOLUME',  # Low volume on moves = weak
            obv_result['signal'] == 'BEARISH',
            obv_result['divergence'] == 'BEARISH_DIVERGENCE' or (ema_cross_volume_conf['confirmed'] == False and 'CROSS' in cross_20_50),
            # EMA/VWAP Confluence (1)
            confluence_result['signal'] in ['STRONG_BEARISH_CONFLUENCE', 'BEARISH_CONFLUENCE'],
            # Order Blocks (1)
            order_blocks_result['signal'] == 'BEARISH_ORDER_BLOCK_TEST',
            # Supply/Demand Zones (1)
            supply_demand_result['signal'] == 'SUPPLY_ZONE_TEST',
            # Exhaustion (1) - High exhaustion for LONG = bearish
            exhaustion_long.get('level', '') in ['HIGH_EXHAUSTION', 'MODERATE_EXHAUSTION']
        ])

        # Generate recommendation (adjusted thresholds for 19 total signals)
        if bullish_signals >= 10:
            recommendation = "🟢 STRONG BUY - Multiple bullish confirmations"
        elif bullish_signals >= 9:
            recommendation = "🟢 BUY - Bullish signals dominant"
        elif bearish_signals >= 10:
            recommendation = "🔴 STRONG SELL - Multiple bearish confirmations"
        elif bearish_signals >= 9:
            recommendation = "🔴 SELL - Bearish signals dominant"
        else:
            recommendation = "⚪ NEUTRAL - Mixed signals, wait for clearer setup"

        # Calculate total setups from labels
        total_setups = len(tb_result.labels)

        # Pre-compute exhaustion component breakdown (avoids nested f-string dict issues)
        _comps = exhaustion_long.get('components', {})
        if _comps:
            _cvd = _comps.get('cvd_divergence', {})
            _rsi = _comps.get('rsi_divergence', {})
            _trend = _comps.get('trend_days', {})
            _vwap_ext = _comps.get('vwap_extension', {})
            _vol_dec = _comps.get('volume_decline', {})
            _exhaustion_long_breakdown = (
                f"- CVD Divergence: {_cvd.get('points', 0)}/20 pts ({_cvd.get('signal', 'NONE')})\n"
                f"- RSI: {_rsi.get('points', 0)}/20 pts ({_rsi.get('note', _rsi.get('signal', 'NONE'))})\n"
                f"- Trend Days: {_trend.get('points', 0)}/25 pts ({_trend.get('note', 'N/A')})\n"
                f"- VWAP Extension: {_vwap_ext.get('points', 0)}/15 pts (σ={_vwap_ext.get('sigma', 0)})\n"
                f"- Volume Decline: {_vol_dec.get('points', 0)}/20 pts ({_vol_dec.get('days', 0)} days declining)"
            )
        else:
            _exhaustion_long_breakdown = (
                "- CVD Divergence: N/A\n- RSI: N/A\n- Trend Days: N/A\n"
                "- VWAP Extension: N/A\n- Volume Decline: N/A"
            )

        # Build report
        report = f"""# ML-Enhanced Analysis: {ticker}

**Current Price:** ${current_price:.2f}

## EMA Crossover Signals (CRITICAL) 🎯

### Current EMA Levels:
- **EMA 20:** ${ema_20:.2f} ({'+' if current_price > ema_20 else ''}{((current_price/ema_20-1)*100):.1f}%)
- **EMA 50:** ${ema_50:.2f} ({'+' if current_price > ema_50 else ''}{((current_price/ema_50-1)*100):.1f}%)
- **EMA 100:** ${ema_100:.2f} ({'+' if current_price > ema_100 else ''}{((current_price/ema_100-1)*100):.1f}%)
- **EMA 200:** ${ema_200:.2f} ({'+' if current_price > ema_200 else ''}{((current_price/ema_200-1)*100):.1f}%)

### Crossover Status:
- **EMA 20/50:** {cross_20_50}{'  🚀' if cross_20_50 == 'BULLISH_CROSS' else ' 💥' if cross_20_50 == 'BEARISH_CROSS' else ''}
- **EMA 20/100:** {cross_20_100}{'  🚀' if cross_20_100 == 'BULLISH_CROSS' else ' 💥' if cross_20_100 == 'BEARISH_CROSS' else ''}
- **EMA 20/200:** {cross_20_200}{'  🌟 GOLDEN CROSS!' if golden_cross else ' ☠️  DEATH CROSS!' if death_cross else ''}

### EMA Alignment:
{'✅ **BULLISH ALIGNMENT** - All EMAs in bullish order (20>50>100>200)' if bullish_alignment else '❌ **BEARISH ALIGNMENT** - All EMAs in bearish order (20<50<100<200)' if bearish_alignment else '⚪ Mixed alignment - no clear trend from EMAs'}

## Price/EMA Interaction Signals (NEW) 📊

### EMA Bounce Detection:
- **EMA 20 Bounce:** {ema_bounce_20['signal']}{' (' + ema_bounce_20['strength'] + ')' if ema_bounce_20['signal'] != 'NONE' else ''}{' 🔊 Volume Confirmed' if ema_bounce_20.get('volume_confirmed', False) else ''}
  - Distance from EMA 20: {ema_bounce_20['distance_pct']:+.2f}%
  - {ema_bounce_20['bounce_days_ago']} days ago{'⚡' if ema_bounce_20['signal'] in ['BULLISH_BOUNCE', 'BEARISH_BOUNCE'] else ''}

- **EMA 50 Bounce:** {ema_bounce_50['signal']}{' (' + ema_bounce_50['strength'] + ')' if ema_bounce_50['signal'] != 'NONE' else ''}{' 🔊 Volume Confirmed' if ema_bounce_50.get('volume_confirmed', False) else ''}
  - Distance from EMA 50: {ema_bounce_50['distance_pct']:+.2f}%
  - {ema_bounce_50['bounce_days_ago']} days ago{'⚡' if ema_bounce_50['signal'] in ['BULLISH_BOUNCE', 'BEARISH_BOUNCE'] else ''}

### Price Crossing EMA:
- **Price vs EMA 20:** {price_ema_cross_20['signal']}{' (' + str(price_ema_cross_20['cross_days_ago']) + ' days ago)' if price_ema_cross_20['signal'] in ['BULLISH_CROSS', 'BEARISH_CROSS'] else ''}
  - Distance: {price_ema_cross_20['distance_pct']:+.2f}%

- **Price vs EMA 50:** {price_ema_cross_50['signal']}{' (' + str(price_ema_cross_50['cross_days_ago']) + ' days ago)' if price_ema_cross_50['signal'] in ['BULLISH_CROSS', 'BEARISH_CROSS'] else ''}
  - Distance: {price_ema_cross_50['distance_pct']:+.2f}%

### Price Extension Analysis:
- **EMA 20 Extension:** {ema_extension_20['signal']} - {ema_extension_20['severity']}
  - {'⚠️  Price extended ' + f"{ema_extension_20['distance_pct']:+.2f}%" + ' from EMA 20 - potential mean reversion' if ema_extension_20['signal'] != 'NORMAL' else '✅ Price within normal range of EMA 20'}

## VWAP Signals (Institutional Fair Value) 💎

### VWAP Bounce Detection:
- **VWAP Bounce:** {vwap_bounce['signal']}{' (' + vwap_bounce['strength'] + ')' if vwap_bounce['signal'] != 'NONE' else ''}{' 🔊 Volume Confirmed' if vwap_bounce.get('volume_confirmed', False) else ''}
  - VWAP Level: ${vwap_bounce['vwap_level']:.2f}
  - Distance from VWAP: {vwap_bounce['distance_pct']:+.2f}%
  - {vwap_bounce['bounce_days_ago']} days ago{'⚡' if vwap_bounce['signal'] in ['VWAP_BOUNCE_SUPPORT', 'VWAP_BOUNCE_RESISTANCE'] else ''}

### VWAP Crossing:
- **Price vs VWAP:** {vwap_cross['signal']}{' (' + str(vwap_cross['cross_days_ago']) + ' days ago)' if vwap_cross['signal'] in ['BULLISH_VWAP_CROSS', 'BEARISH_VWAP_CROSS'] else ''}
  - Distance: {vwap_cross['distance_pct']:+.2f}%

### VWAP Position Interpretation:
- **{vwap_position['position']}** - {vwap_position['sentiment']}
  - {vwap_position['interpretation']}

## Volume Confirmation (Smart Money) 📈

### Volume Surge Detection:
- **Current Volume:** {volume_surge['current_volume']:,} shares
- **20-Day Average:** {volume_surge['avg_volume']:,.0f} shares
- **Volume Ratio:** {volume_surge['volume_ratio']:.2f}x average
- **Signal:** {volume_surge['signal']} - {volume_surge['surge_strength']}
  - {'⚡ VOLUME SURGE detected!' if volume_surge['signal'] == 'VOLUME_SURGE' else '⚠️ Low volume warning' if volume_surge['signal'] == 'LOW_VOLUME' else '✅ Normal volume'}

### On-Balance Volume (OBV):
- **OBV Trend:** {obv_result['obv_trend']}
- **Trend Strength:** {obv_result['obv_strength']:.1f}/100
- **Divergence:** {obv_result['divergence']}
  - {'⚡ BULLISH DIVERGENCE - Price down but volume accumulating!' if obv_result['divergence'] == 'BULLISH_DIVERGENCE' else '⚠️ BEARISH DIVERGENCE - Price up but volume distributing!' if obv_result['divergence'] == 'BEARISH_DIVERGENCE' else '✅ No divergence detected'}
- **Signal:** {obv_result['signal']}

### Crossover Volume Confirmation:
- **EMA 20/50 Cross:** {ema_cross_volume_conf['explanation']}
  - Confidence: {ema_cross_volume_conf['confidence']}
  - {'✅ Volume confirmed' if ema_cross_volume_conf['confirmed'] else '⚠️ Unconfirmed'}

- **VWAP Cross:** {vwap_cross_volume_conf['explanation']}
  - Confidence: {vwap_cross_volume_conf['confidence']}
  - {'✅ Volume confirmed' if vwap_cross_volume_conf['confirmed'] else '⚠️ Unconfirmed'}

## EMA/VWAP Confluence (Multi-Indicator Alignment) 🎯

### Alignment Analysis:
- **Signal:** {confluence_result['signal']}
- **Strength:** {confluence_result['strength']}
- **Alignment Count:** {confluence_result['alignment_count']}/4 indicators aligned
  - Bullish: {confluence_result['bullish_count']}/4
  - Bearish: {confluence_result['bearish_count']}/4

### Indicator Positions:
- **Price above EMA 20:** {'✅ YES' if confluence_result['price_above_ema20'] else '❌ NO'}
- **Price above EMA 50:** {'✅ YES' if confluence_result['price_above_ema50'] else '❌ NO'}
- **Price above VWAP:** {'✅ YES' if confluence_result['price_above_vwap'] else '❌ NO'}
- **EMA 20 above EMA 50:** {'✅ YES' if confluence_result['ema20_above_ema50'] else '❌ NO'}

### Interpretation:
{confluence_result['interpretation']}

## Order Blocks (Institutional Footprints) 📍

### Order Block Analysis:
- **Signal:** {order_blocks_result['signal']}
- **Bullish Blocks Found:** {len(order_blocks_result['bullish_blocks'])}
- **Bearish Blocks Found:** {len(order_blocks_result['bearish_blocks'])}

### Closest Order Blocks:
- **Bullish Block Distance:** {order_blocks_result['distance_to_bullish_pct']:.2f}% below
  {f"  - Price Range: ${order_blocks_result['closest_bullish_block']['price_low']:.2f} - ${order_blocks_result['closest_bullish_block']['price_high']:.2f}" if order_blocks_result['closest_bullish_block'] else "  - None detected"}
  {f"  - Age: {order_blocks_result['closest_bullish_block']['age_days']} days" if order_blocks_result['closest_bullish_block'] else ""}
  {f"  - Original Impulse: +{order_blocks_result['closest_bullish_block']['impulse_size']:.1f}%" if order_blocks_result['closest_bullish_block'] else ""}

- **Bearish Block Distance:** {order_blocks_result['distance_to_bearish_pct']:.2f}% above
  {f"  - Price Range: ${order_blocks_result['closest_bearish_block']['price_low']:.2f} - ${order_blocks_result['closest_bearish_block']['price_high']:.2f}" if order_blocks_result['closest_bearish_block'] else "  - None detected"}
  {f"  - Age: {order_blocks_result['closest_bearish_block']['age_days']} days" if order_blocks_result['closest_bearish_block'] else ""}
  {f"  - Original Impulse: -{order_blocks_result['closest_bearish_block']['impulse_size']:.1f}%" if order_blocks_result['closest_bearish_block'] else ""}

### Interpretation:
{order_blocks_result['interpretation']}

## Supply/Demand Zones (Price Action Zones) 🏛️

### Zone Analysis:
- **Signal:** {supply_demand_result['signal']}
- **Demand Zones Found:** {len(supply_demand_result['demand_zones'])}
- **Supply Zones Found:** {len(supply_demand_result['supply_zones'])}

### Closest Zones:
- **Demand Zone Distance:** {supply_demand_result['distance_to_demand_pct']:.2f}% below
  {f"  - Zone Range: ${supply_demand_result['closest_demand_zone']['zone_low']:.2f} - ${supply_demand_result['closest_demand_zone']['zone_high']:.2f}" if supply_demand_result['closest_demand_zone'] else "  - None detected"}
  {f"  - Age: {supply_demand_result['closest_demand_zone']['age_days']} days" if supply_demand_result['closest_demand_zone'] else ""}
  {f"  - Original Impulse: +{supply_demand_result['closest_demand_zone']['impulse_size']:.1f}%" if supply_demand_result['closest_demand_zone'] else ""}
  {f"  - Consolidation: {supply_demand_result['closest_demand_zone']['consolidation_bars']} bars" if supply_demand_result['closest_demand_zone'] else ""}

- **Supply Zone Distance:** {supply_demand_result['distance_to_supply_pct']:.2f}% above
  {f"  - Zone Range: ${supply_demand_result['closest_supply_zone']['zone_low']:.2f} - ${supply_demand_result['closest_supply_zone']['zone_high']:.2f}" if supply_demand_result['closest_supply_zone'] else "  - None detected"}
  {f"  - Age: {supply_demand_result['closest_supply_zone']['age_days']} days" if supply_demand_result['closest_supply_zone'] else ""}
  {f"  - Original Impulse: -{supply_demand_result['closest_supply_zone']['impulse_size']:.1f}%" if supply_demand_result['closest_supply_zone'] else ""}
  {f"  - Consolidation: {supply_demand_result['closest_supply_zone']['consolidation_bars']} bars" if supply_demand_result['closest_supply_zone'] else ""}

### Interpretation:
{supply_demand_result['interpretation']}

## Exhaustion Analysis (Volumetric Liquidity) 🔋 NEW

### LONG Position Exhaustion:
- **Score:** {exhaustion_long.get('score', 0)}/100
- **Level:** {exhaustion_long.get('level', 'UNKNOWN')}
- **Suggested Action:** {exhaustion_long.get('suggested_action', 'N/A')}

### Component Breakdown (LONG):
{_exhaustion_long_breakdown}

### Interpretation:
{exhaustion_long.get('interpretation', 'No exhaustion data available')}

{'⚠️ **WARNING:** ' + exhaustion_long.get('action_detail', '') if exhaustion_long.get('level', '') in ['HIGH_EXHAUSTION', 'MODERATE_EXHAUSTION'] else '✅ No significant exhaustion detected for LONG positions'}

## Triple-Barrier Analysis
- **Success Rate:** {tb_result.success_rate:.1%} ({total_setups} historical setups)
- **Average Profit:** {tb_result.avg_profit:.2%} when winning
- **Average Loss:** {tb_result.avg_loss:.2%} when losing
- **Risk/Reward Ratio:** {tb_result.risk_reward_ratio:.2f}:1
- **Average Holding:** {tb_result.avg_holding_days:.1f} days

## Trend Analysis (Statistical)
- **Current Trend:** {'UPTREND' if ts_result.labels.iloc[-1] == 1 else 'DOWNTREND' if ts_result.labels.iloc[-1] == -1 else 'NEUTRAL'}
- **Statistical Confidence:** {ts_result.confidence.iloc[-1]:.1%}
- **T-Statistic:** {ts_result.t_statistics.iloc[-1]:.2f}

## Position Sizing
- **Kelly-Optimal Size:** {kelly_size:.1%} of capital

## Final Recommendation
**{recommendation}**

**Signal Confluence:**
- Bullish Signals: {bullish_signals}/19
- Bearish Signals: {bearish_signals}/19

**Signal Breakdown:**
- ML Signals: 2 (Triple-Barrier + Trend-Scanning)
- EMA/EMA Crosses: 4 (20/50, 20/100, 20/200, Alignment)
- Price/EMA Interactions: 3 (Bounce, Cross, Extension)
- VWAP Signals: 3 (Bounce, Cross, Position)
- Volume Confirmation: 3 (Surge, OBV, Crossover Confirmation)
- EMA/VWAP Confluence: 1 (Multi-Indicator Alignment)
- Order Blocks: 1 (Institutional Footprints)
- Supply/Demand Zones: 1 (Price Action Zones)
- Exhaustion Analysis: 1 (Volumetric Liquidity) ⭐ NEW

---
*Based on {len(prices)} days of historical data with Price/EMA + VWAP + Volume + Confluence + Order Blocks + Supply/Demand + Exhaustion analysis*
"""

        return convert_numpy_types({
            "report": report,
            "ticker": ticker,
            "recommendation": recommendation,
            "bullish_signals": int(bullish_signals),
            "bearish_signals": int(bearish_signals),
            "total_signals": 19,
        })

    @mcp.tool()
    async def validate_strategy_robustness(
        ticker: str,
        n_trials: int = 100
    ) -> dict:
        """
        Validate if analysis results are statistically robust or just lucky.

        Uses multiple testing corrections to account for p-hacking and
        overfitting. Essential before making trading decisions.

        Args:
            ticker: Stock symbol
            n_trials: Number of strategies tested (default 100)

        Returns:
            Validation metrics:
            - Deflated Sharpe Ratio
            - Harvey-Liu-Zhu t-stat threshold
            - Probability results are not due to luck
        """
        ticker = validate_ticker(ticker)

        # Get returns (Questrade primary, Yahoo fallback, cached)
        hist = _get_ohlcv_cached(ticker, period="1y")
        if hist is None or hist.empty:
            return {"error": f"No data for {ticker}"}

        returns = hist['Close'].pct_change().dropna()

        # Calculate Deflated Sharpe
        ds_result = calculate_deflated_sharpe(
            returns,
            n_trials=n_trials,
            annual_factor=252
        )

        # Calculate HLZ threshold
        hlz_threshold = harvey_liu_zhu_threshold(n_trials=n_trials)

        # Determine if robust
        is_robust = (
            ds_result['deflated_sharpe'] > 1.0 and
            ds_result['probability_significant'] > 0.95
        )

        report = f"""# Strategy Robustness Validation: {ticker}

## Deflated Sharpe Ratio
- **Raw Sharpe:** {ds_result['raw_sharpe']:.2f}
- **Deflated Sharpe:** {ds_result['deflated_sharpe']:.2f}
- **Probability Significant:** {ds_result['probability_significant']:.1%}

## Multiple Testing Correction
- **Trials Tested:** {n_trials}
- **HLZ T-Stat Threshold:** {hlz_threshold:.2f} (vs standard 1.96)
- **Expected Max Sharpe:** {ds_result['expected_max_sharpe']:.2f}

## Assessment
**Result:** {'✅ ROBUST - Strategy passes validation' if is_robust else '❌ NOT ROBUST - Results may be due to luck'}

**Interpretation:**
- Deflated Sharpe > 1.0: {'✅ Pass' if ds_result['deflated_sharpe'] > 1.0 else '❌ Fail'}
- Probability > 95%: {'✅ Pass' if ds_result['probability_significant'] > 0.95 else '❌ Fail'}

---
*Validation accounts for {n_trials} tested strategies*
"""

        return convert_numpy_types({
            "report": report,
            "ticker": ticker,
            "raw_sharpe": ds_result['raw_sharpe'],
            "deflated_sharpe": ds_result['deflated_sharpe'],
            "is_robust": is_robust,
        })

    @mcp.tool()
    async def calculate_feature_importance_analysis(
        ticker: str,
        period: Literal["3mo", "6mo", "1y"] = "6mo",
        forward_window: int = 10,
        method: Literal["combined", "mdi", "mda", "sfi", "spearman"] = "combined"
    ) -> dict:
        """
        Calculate which technical indicators are most predictive of future returns.

        **METHODOLOGY:** Uses López de Prado's robust feature importance methodology from
        "Advances in Financial Machine Learning" Chapter 5.

        **DEFAULT (method='combined'):**
        - MDI (Mean Decrease Impurity): Fast, from Random Forest node splits
        - MDA (Mean Decrease Accuracy): Permutation importance, robust
        - SFI (Single Feature Importance): Individual feature performance
        - **Averages all three for maximum robustness**

        This is institutional-grade analysis - more reliable than simple correlation.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            period: Historical data window ("3mo", "6mo", "1y")
            forward_window: Days ahead to predict (default 10)
            method: Importance calculation method (default "combined"):
                    - 'combined': MDI + MDA + SFI averaged (RECOMMENDED for real money)
                    - 'mdi': Mean Decrease Impurity only (fast)
                    - 'mda': Mean Decrease Accuracy only (permutation)
                    - 'sfi': Single Feature Importance only
                    - 'spearman': Simple correlation (fastest, for quick checks)

        Returns:
            Markdown formatted report with feature importance rankings

        Example:
            >>> # Robust analysis (recommended)
            >>> result = await calculate_feature_importance_analysis("AAPL", "6mo")
            >>>
            >>> # Fast analysis (for quick checks)
            >>> result = await calculate_feature_importance_analysis("AAPL", "6mo", method="spearman")

        References:
            López de Prado, M. (2018). Advances in Financial Machine Learning. Chapter 5.
        """
        try:
            # Get historical data (Questrade primary, Yahoo fallback, cached)
            hist = _get_ohlcv_cached(ticker, period=period)

            if hist is None or hist.empty or len(hist) < forward_window + 20:
                return {"error": f"Insufficient data for {ticker} with period {period}"}

            # Calculate future returns (target variable)
            hist['Forward_Return'] = hist['Close'].pct_change(forward_window).shift(-forward_window)

            # Calculate technical indicators
            close = hist['Close']
            high = hist['High']
            low = hist['Low']
            volume = hist['Volume']

            # RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            hist['RSI'] = 100 - (100 / (1 + rs))

            # MACD
            ema_12 = close.ewm(span=12).mean()
            ema_26 = close.ewm(span=26).mean()
            hist['MACD'] = ema_12 - ema_26
            hist['MACD_Signal'] = hist['MACD'].ewm(span=9).mean()
            hist['MACD_Hist'] = hist['MACD'] - hist['MACD_Signal']

            # Moving Averages
            hist['SMA_20'] = close.rolling(window=20).mean()
            hist['SMA_50'] = close.rolling(window=50).mean()
            hist['Price_vs_SMA20'] = (close - hist['SMA_20']) / hist['SMA_20']
            hist['Price_vs_SMA50'] = (close - hist['SMA_50']) / hist['SMA_50']

            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            hist['BB_Middle'] = close.rolling(window=bb_period).mean()
            bb_std_val = close.rolling(window=bb_period).std()
            hist['BB_Upper'] = hist['BB_Middle'] + (bb_std_val * bb_std)
            hist['BB_Lower'] = hist['BB_Middle'] - (bb_std_val * bb_std)
            hist['BB_Position'] = (close - hist['BB_Lower']) / (hist['BB_Upper'] - hist['BB_Lower'])

            # Volume indicators (exclude current day from average)
            hist['Volume_SMA'] = volume.shift(1).rolling(window=20).mean()
            hist['Relative_Volume'] = volume / hist['Volume_SMA']

            # Volatility
            hist['ATR'] = hist[['High', 'Low', 'Close']].apply(
                lambda x: max(x['High'] - x['Low'],
                             abs(x['High'] - x['Close']),
                             abs(x['Low'] - x['Close'])),
                axis=1
            ).rolling(window=14).mean()
            hist['Volatility'] = close.pct_change().rolling(window=20).std()

            # Momentum
            hist['ROC_10'] = close.pct_change(10)
            hist['ROC_20'] = close.pct_change(20)

            # Feature list with descriptions
            feature_descriptions = {
                'RSI': 'RSI (Relative Strength Index)',
                'MACD_Hist': 'MACD Histogram',
                'Price_vs_SMA20': 'Price vs 20-day MA',
                'Price_vs_SMA50': 'Price vs 50-day MA',
                'BB_Position': 'Bollinger Band Position',
                'Relative_Volume': 'Relative Volume',
                'Volatility': 'Price Volatility (20-day)',
                'ROC_10': '10-day Rate of Change',
                'ROC_20': '20-day Rate of Change'
            }

            # Prepare features DataFrame (only existing columns)
            feature_cols = [f for f in feature_descriptions.keys() if f in hist.columns]
            features_df = hist[feature_cols].copy()
            target = hist['Forward_Return'].copy()

            # Remove rows with NaN in features or target
            valid_mask = ~(features_df.isna().any(axis=1) | target.isna())
            features_clean = features_df[valid_mask]
            target_clean = target[valid_mask]

            if len(features_clean) < 30:
                return {"error": f"Insufficient valid data for {ticker} (need 30+ samples, got {len(features_clean)})"}

            # Calculate feature importance using López de Prado methodology
            importances = calculate_feature_importance(
                features_clean,
                target_clean,
                method=method  # 'combined', 'mdi', 'mda', 'sfi', or 'spearman'
            )

            # Build results dictionary with descriptions
            correlations = {}
            for feature, importance in importances.items():
                correlations[feature] = {
                    'description': feature_descriptions.get(feature, feature),
                    'importance': importance,
                    'sample_size': len(features_clean)
                }

            # Sort by importance (already normalized 0-1)
            sorted_features = sorted(
                correlations.items(),
                key=lambda x: x[1]['importance'],
                reverse=True
            )

            # Generate report
            method_name = {
                'combined': 'Combined (MDI + MDA + SFI)',
                'mdi': 'MDI (Mean Decrease Impurity)',
                'mda': 'MDA (Mean Decrease Accuracy)',
                'sfi': 'SFI (Single Feature Importance)',
                'spearman': 'Spearman Correlation'
            }.get(method, method)

            report = f"""# Feature Importance Analysis: {ticker}

**Methodology:** {method_name}
**Analysis Period:** {period}
**Forward Window:** {forward_window} days
**Valid Samples:** {len(features_clean)} (after removing NaN)

## Feature Rankings

Features ranked by predictive importance for {forward_window}-day forward returns:

*Importance scores are normalized (sum to 1.0) - higher = more predictive*

"""

            for rank, (feature, stats) in enumerate(sorted_features, 1):
                importance = stats['importance']

                # Interpret strength (importance is 0-1, normalized across all features)
                # With 9 features, average would be ~0.11
                avg_importance = 1.0 / len(sorted_features)
                relative = importance / avg_importance if avg_importance > 0 else 0

                if relative > 1.5:
                    strength = "CRITICAL"
                elif relative > 1.0:
                    strength = "HIGH"
                elif relative > 0.5:
                    strength = "MODERATE"
                else:
                    strength = "LOW"

                report += f"""### {rank}. {stats['description']}
- **Importance Score:** {importance:.4f} ({importance*100:.2f}%)
- **Strength:** {strength} ({relative:.1f}x average)
- **Interpretation:** {"Critical predictor - prioritize in analysis" if relative > 1.5 else "Important predictor" if relative > 1.0 else "Moderate predictor" if relative > 0.5 else "Minor predictor"}

"""

            # Summary insights
            report += f"""## Summary Insights

### Top Predictive Features:
"""

            for rank, (feature, stats) in enumerate(sorted_features[:3], 1):
                report += f"{rank}. **{stats['description']}** - {stats['importance']:.4f} importance ({stats['importance']*100:.1f}%)\n"

            # Concentration analysis
            top3_importance = sum(stats['importance'] for _, stats in sorted_features[:3])
            total_count = len(correlations)

            # Determine predictability based on importance concentration
            if top3_importance > 0.6:
                predictability = "HIGH"
                pred_desc = "Top 3 features dominate (>60%) - clear strong predictors"
            elif top3_importance > 0.45:
                predictability = "MODERATE"
                pred_desc = "Top 3 features moderately important (45-60%)"
            else:
                predictability = "LOW"
                pred_desc = "Importance widely distributed - no clear dominant predictors"

            report += f"""
### Statistical Summary:
- **Total Features:** {total_count}
- **Top 3 Concentration:** {top3_importance:.1%} of importance
- **Predictability:** {predictability} - {pred_desc}
- **Methodology:** {method_name}

### Recommendations:
"""

            if predictability == "HIGH":
                report += f"- ✅ **Strong predictive power found** - focus on top {min(3, total_count)} features\n"
                report += "- ML models likely to perform well with these features\n"
                report += "- Top features account for majority of predictive power\n"
            elif predictability == "MODERATE":
                report += "- ⚠️ **Moderate predictive power** - use top 3-5 features together\n"
                report += "- Combining multiple indicators recommended\n"
                report += "- Consider feature interactions (not just individual features)\n"
            else:
                report += "- ⚠️ **Limited predictive power in individual features**\n"
                report += "- May need non-linear models to capture relationships\n"
                report += "- Consider regime-based or ensemble approaches\n"

            # Methodology note
            if method == 'combined':
                report += """
**Methodology Note:** This analysis uses López de Prado's robust combined approach (MDI + MDA + SFI averaged).
More reliable than simple correlation for real money trading.
"""
            elif method == 'spearman':
                report += """
**Methodology Note:** Fast Spearman correlation used. For production trading, consider using method='combined'
for more robust results (MDI + MDA + SFI).
"""
            else:
                report += """
**Note:** Feature importance quantifies predictive power, not causation. Use top features together
for more robust predictions. Results may vary across different market regimes.
"""

            return convert_numpy_types({
                "report": report,
                "ticker": ticker,
                "method": method_name,
                "predictability": predictability,
                "top_features": [
                    {"name": f, "importance": s['importance']}
                    for f, s in sorted_features[:5]
                ],
            })

        except Exception as e:
            return {"error": f"Error analyzing feature importance for {ticker}: {str(e)}"}
