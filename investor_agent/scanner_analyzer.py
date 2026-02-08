"""
Scanner Analyzer Module - Deep Analysis Pipeline with Al Brooks Price Action

This module orchestrates analysis of scanner candidates by:
1. Calling existing analysis tools (technical, ML, RS, volume)
2. Generating Al Brooks price action analysis
3. Calculating composite scoring
4. Producing rich output with trading recommendations

Al Brooks Price Action Trading:
- Always-In Direction (market bias)
- Pattern Detection (High 1/2, Low 1/2, Breakout Pullback, etc.)
- Bar-by-Bar Reading
- Trap Risk Assessment
- Probability Estimation based on context
"""

import logging
from typing import Any, Literal
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Import volumetric liquidity functions
try:
    from .technical_analysis_bootstrap import (
        calculate_exhaustion_score,
        enhance_brooks_with_cvd,
        analyze_cvd
    )
    _volumetric_available = True
except ImportError:
    _volumetric_available = False
    logger.warning("Volumetric liquidity functions not available")

# Import new scanner enhancement tools (December 2025)
try:
    from .tools.catalysts import (
        detect_catalyst_strength_impl as detect_catalyst_strength,
        detect_insider_cluster_impl as detect_insider_cluster,
        detect_unusual_options_activity_impl as detect_unusual_options_activity,
        calculate_quality_score_impl as calculate_quality_score,
        analyze_competitors_impl as analyze_competitors,
    )
    _new_tools_available = True
except ImportError:
    _new_tools_available = False
    logger.warning("New scanner enhancement tools not available")

# generate_trading_signal imported lazily where needed (from tools.signals)


def _parse_numeric(value, default=0):
    """Parse numeric value from string, handling currency symbols and N/A."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove currency symbols and commas
        cleaned = value.replace('$', '').replace(',', '').replace('%', '').strip()
        if cleaned in ['N/A', 'n/a', '', 'None', 'Insufficient Data']:
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


class AlBrooksAnalyzer:
    """
    Al Brooks Price Action Analysis Engine.

    Generates professional price action analysis including:
    - Always-In Direction determination
    - Pattern recognition (High/Low 1/2, wedges, channels, etc.)
    - Bar-by-bar reading of recent price action
    - Trap risk assessment
    - Probability estimation with adjustments
    """

    # Al Brooks pattern definitions
    LONG_PATTERNS = {
        'high_1': 'High 1 - First pullback in bull trend',
        'high_2': 'High 2 - Second entry long after pullback',
        'high_3': 'High 3 - Third push up (often climax)',
        'high_4': 'High 4 - Fourth entry (trend getting old)',
        'double_bottom': 'Double Bottom - W pattern reversal',
        'higher_low': 'Higher Low - Trend continuation',
        'breakout_pullback': 'Breakout Pullback - Retest of breakout level',
        'wedge_reversal': 'Wedge Reversal - Three pushes down reversing',
        'expanding_triangle': 'Expanding Triangle Bottom',
        'failed_breakdown': 'Failed Breakdown - Bear trap',
        'ema_bounce': 'EMA Bounce - Support at moving average',
        'tight_trading_range_breakout': 'Tight TR Breakout - Compression release',
    }

    SHORT_PATTERNS = {
        'low_1': 'Low 1 - First pullback in bear trend',
        'low_2': 'Low 2 - Second entry short after pullback',
        'low_3': 'Low 3 - Third push down (often climax)',
        'low_4': 'Low 4 - Fourth entry (trend getting old)',
        'double_top': 'Double Top - M pattern reversal',
        'lower_high': 'Lower High - Trend continuation',
        'breakdown_pullback': 'Breakdown Pullback - Retest of breakdown level',
        'wedge_top': 'Wedge Top - Three pushes up reversing',
        'expanding_triangle_top': 'Expanding Triangle Top',
        'failed_breakout': 'Failed Breakout - Bull trap',
        'ema_rejection': 'EMA Rejection - Resistance at moving average',
        'climactic_exhaustion': 'Climactic Exhaustion - Parabolic reversal',
    }

    def __init__(self):
        self.base_probability = 50  # Al Brooks starts at 50-50

    def analyze(
        self,
        ticker: str,
        direction: Literal['long', 'short'],
        ohlcv_data: pd.DataFrame,
        technical_data: dict,
        ml_data: dict | None = None,
        rs_data: dict | None = None,
        volume_data: dict | None = None
    ) -> dict[str, Any]:
        """
        Generate comprehensive Al Brooks price action analysis.

        Args:
            ticker: Stock symbol
            direction: Trade direction (long/short)
            ohlcv_data: OHLCV DataFrame with at least 20 bars
            technical_data: Output from analyze_technical()
            ml_data: Output from analyze_ml_enhanced() (optional)
            rs_data: Output from calculate_relative_strength_tool() (optional)
            volume_data: Output from analyze_volume_tool() (optional)

        Returns:
            Al Brooks analysis including pattern, probability, levels, commentary
        """
        if ohlcv_data is None or len(ohlcv_data) < 10:
            return self._empty_analysis("Insufficient price data")

        # Determine always-in direction
        always_in = self._determine_always_in(ohlcv_data, technical_data)

        # Detect current pattern
        pattern, pattern_desc = self._detect_pattern(
            ohlcv_data, technical_data, direction
        )

        # Bar-by-bar reading
        bar_reading = self._read_recent_bars(ohlcv_data, direction)

        # Assess trap risk
        trap_risk, trap_explanation = self._assess_trap_risk(
            ohlcv_data, direction, always_in, pattern
        )

        # Calculate probability with adjustments
        probability_result = self._calculate_probability(
            direction=direction,
            always_in=always_in,
            pattern=pattern,
            trap_risk=trap_risk,
            ml_data=ml_data,
            rs_data=rs_data,
            volume_data=volume_data,
            technical_data=technical_data
        )

        # Calculate entry, stop, and target levels
        levels = self._calculate_levels(
            ohlcv_data, direction, pattern, technical_data
        )

        # Generate commentary
        commentary = self._generate_commentary(
            ticker=ticker,
            direction=direction,
            pattern=pattern,
            pattern_desc=pattern_desc,
            always_in=always_in,
            bar_reading=bar_reading,
            trap_risk=trap_risk,
            probability_result=probability_result,
            levels=levels
        )

        return {
            'always_in': always_in,
            'pattern': pattern,
            'pattern_description': pattern_desc,
            'bar_reading': bar_reading,
            'trap_risk': trap_risk,
            'trap_explanation': trap_explanation,
            'base_probability': probability_result['base'],
            'adjusted_probability': probability_result['adjusted'],
            'probability_adjustments': probability_result['adjustments'],
            'entry': levels['entry'],
            'stop': levels['stop'],
            'target': levels['target'],
            'risk_reward_ratio': levels['risk_reward'],
            'commentary': commentary
        }

    def _determine_always_in(
        self,
        ohlcv: pd.DataFrame,
        technical: dict
    ) -> str:
        """
        Determine the Always-In direction (market bias).

        Al Brooks: The market is always either Always-In Long or Always-In Short.
        Determined by:
        - Position relative to EMAs
        - Recent swing highs/lows
        - Trend channel direction
        """
        analysis = technical.get('analysis', {})

        # Get moving average data
        ma_data = analysis.get('moving_averages', {})
        ma_trend = ma_data.get('trend', 'neutral')

        # Get RSI for momentum - handle string values
        rsi_data = analysis.get('rsi', {})
        rsi = _parse_numeric(rsi_data.get('value', 50), 50)

        # Get MACD trend
        macd_data = analysis.get('macd', {})
        macd_trend = macd_data.get('trend', 'neutral')

        # Recent price action
        recent_closes = ohlcv['Close'].tail(10)
        recent_highs = ohlcv['High'].tail(20)
        recent_lows = ohlcv['Low'].tail(20)

        # Higher highs and higher lows = bullish
        # Lower highs and lower lows = bearish
        hh = recent_highs.iloc[-1] > recent_highs.iloc[-5:-1].max()
        hl = recent_lows.iloc[-1] > recent_lows.iloc[-5:-1].min()
        lh = recent_highs.iloc[-1] < recent_highs.iloc[-5:-1].max()
        ll = recent_lows.iloc[-1] < recent_lows.iloc[-5:-1].min()

        # Score the bias
        bull_score = 0
        bear_score = 0

        if ma_trend == 'bullish':
            bull_score += 2
        elif ma_trend == 'bearish':
            bear_score += 2

        if macd_trend == 'bullish':
            bull_score += 1
        elif macd_trend == 'bearish':
            bear_score += 1

        if rsi > 50:
            bull_score += 1
        elif rsi < 50:
            bear_score += 1

        if hh and hl:
            bull_score += 2
        if lh and ll:
            bear_score += 2

        # Close relative to recent range
        range_high = recent_closes.max()
        range_low = recent_closes.min()
        current = recent_closes.iloc[-1]

        if range_high != range_low:
            range_position = (current - range_low) / (range_high - range_low)
            if range_position > 0.7:
                bull_score += 1
            elif range_position < 0.3:
                bear_score += 1

        if bull_score > bear_score:
            return 'LONG'
        elif bear_score > bull_score:
            return 'SHORT'
        else:
            return 'NEUTRAL'

    def _detect_pattern(
        self,
        ohlcv: pd.DataFrame,
        technical: dict,
        direction: str
    ) -> tuple[str, str]:
        """
        Detect the current Al Brooks price action pattern.

        Returns:
            Tuple of (pattern_id, pattern_description)
        """
        analysis = technical.get('analysis', {})

        # Get key metrics - handle string values
        rsi = _parse_numeric(analysis.get('rsi', {}).get('value', 50), 50)
        ma_trend = analysis.get('moving_averages', {}).get('trend', 'neutral')

        # Recent price action analysis
        closes = ohlcv['Close'].values
        highs = ohlcv['High'].values
        lows = ohlcv['Low'].values

        if len(closes) < 10:
            return 'unknown', 'Insufficient data for pattern detection'

        # Calculate recent swings
        recent_high = max(highs[-10:])
        recent_low = min(lows[-10:])
        current_price = closes[-1]

        # EMA values - handle string values like '$276.30'
        ema_20_raw = analysis.get('moving_averages', {}).get('sma_20', current_price)
        ema_50_raw = analysis.get('moving_averages', {}).get('sma_50', current_price)
        ema_20 = _parse_numeric(ema_20_raw, current_price)
        ema_50 = _parse_numeric(ema_50_raw, current_price)

        if direction == 'long':
            # Check for LONG patterns

            # RSI Oversold Bounce
            if rsi < 35:
                if closes[-1] > closes[-2] and closes[-2] > closes[-3]:
                    return 'double_bottom', self.LONG_PATTERNS['double_bottom']
                return 'higher_low', self.LONG_PATTERNS['higher_low']

            # EMA Bounce
            if abs(current_price - ema_20) / ema_20 < 0.02:  # Within 2% of EMA
                if current_price > closes[-2]:
                    return 'ema_bounce', self.LONG_PATTERNS['ema_bounce']

            # Breakout Pullback
            if current_price > ema_20 and current_price > ema_50:
                if abs(current_price - recent_high) / recent_high < 0.03:
                    return 'breakout_pullback', self.LONG_PATTERNS['breakout_pullback']

            # High 2 - Second pullback in uptrend
            if ma_trend == 'bullish':
                # Count recent pullbacks
                pullback_count = self._count_pullbacks(ohlcv, 'long')
                if pullback_count == 2:
                    return 'high_2', self.LONG_PATTERNS['high_2']
                elif pullback_count == 1:
                    return 'high_1', self.LONG_PATTERNS['high_1']
                elif pullback_count == 3:
                    return 'high_3', self.LONG_PATTERNS['high_3']

            # Default bullish pattern
            if ma_trend == 'bullish':
                return 'higher_low', self.LONG_PATTERNS['higher_low']

            return 'breakout_pullback', self.LONG_PATTERNS['breakout_pullback']

        else:  # SHORT patterns
            # RSI Overbought Reversal
            if rsi > 65:
                if closes[-1] < closes[-2]:
                    return 'double_top', self.SHORT_PATTERNS['double_top']
                return 'lower_high', self.SHORT_PATTERNS['lower_high']

            # EMA Rejection
            if abs(current_price - ema_20) / ema_20 < 0.02:
                if current_price < closes[-2]:
                    return 'ema_rejection', self.SHORT_PATTERNS['ema_rejection']

            # Climactic Exhaustion (parabolic move)
            if self._detect_climax(ohlcv):
                return 'climactic_exhaustion', self.SHORT_PATTERNS['climactic_exhaustion']

            # Low 2 - Second pullback in downtrend
            if ma_trend == 'bearish':
                pullback_count = self._count_pullbacks(ohlcv, 'short')
                if pullback_count == 2:
                    return 'low_2', self.SHORT_PATTERNS['low_2']
                elif pullback_count == 1:
                    return 'low_1', self.SHORT_PATTERNS['low_1']
                elif pullback_count == 3:
                    return 'low_3', self.SHORT_PATTERNS['low_3']

            # Failed Breakout (bull trap)
            if current_price < ema_20 and closes[-3] > recent_high * 0.98:
                return 'failed_breakout', self.SHORT_PATTERNS['failed_breakout']

            return 'lower_high', self.SHORT_PATTERNS['lower_high']

    def _count_pullbacks(self, ohlcv: pd.DataFrame, direction: str) -> int:
        """Count pullbacks in the recent trend."""
        closes = ohlcv['Close'].values[-20:]
        if len(closes) < 10:
            return 1

        pullbacks = 0
        if direction == 'long':
            # Look for dips in an uptrend
            for i in range(2, len(closes) - 1):
                if closes[i] < closes[i-1] and closes[i] < closes[i+1]:
                    pullbacks += 1
        else:
            # Look for bounces in a downtrend
            for i in range(2, len(closes) - 1):
                if closes[i] > closes[i-1] and closes[i] > closes[i+1]:
                    pullbacks += 1

        return min(pullbacks, 4)

    def _detect_climax(self, ohlcv: pd.DataFrame) -> bool:
        """Detect climactic/parabolic move."""
        if len(ohlcv) < 10:
            return False

        closes = ohlcv['Close'].values[-10:]
        returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]

        # Parabolic if 5+ consecutive up days with increasing magnitude
        consecutive_up = sum(1 for r in returns[-5:] if r > 0)
        avg_return = np.mean([r for r in returns[-5:] if r > 0]) if consecutive_up > 0 else 0

        return consecutive_up >= 4 and avg_return > 0.01

    def _read_recent_bars(
        self,
        ohlcv: pd.DataFrame,
        direction: str
    ) -> str:
        """Generate bar-by-bar reading of last 5 bars."""
        if len(ohlcv) < 5:
            return "Insufficient bars for reading"

        bars = ohlcv.tail(5)
        readings = []

        for i, (_, bar) in enumerate(bars.iterrows()):
            open_p = bar['Open']
            high = bar['High']
            low = bar['Low']
            close = bar['Close']

            # Bar body
            body_size = abs(close - open_p)
            range_size = high - low
            body_pct = body_size / range_size if range_size > 0 else 0

            # Bar type
            if close > open_p:
                bar_type = "bull"
                close_position = (close - low) / range_size if range_size > 0 else 0.5
            elif close < open_p:
                bar_type = "bear"
                close_position = (close - low) / range_size if range_size > 0 else 0.5
            else:
                bar_type = "doji"
                close_position = 0.5

            # Describe bar
            if body_pct > 0.7:
                body_desc = "strong"
            elif body_pct > 0.4:
                body_desc = "moderate"
            else:
                body_desc = "small"

            if close_position > 0.7:
                close_desc = "near high"
            elif close_position < 0.3:
                close_desc = "near low"
            else:
                close_desc = "mid-range"

            readings.append(f"{body_desc} {bar_type} bar closing {close_desc}")

        # Summarize
        bull_count = sum(1 for r in readings if 'bull' in r)
        bear_count = sum(1 for r in readings if 'bear' in r)

        if bull_count >= 4:
            summary = "5 bar pattern shows strong bullish momentum"
        elif bear_count >= 4:
            summary = "5 bar pattern shows strong bearish momentum"
        elif bull_count >= 3:
            summary = "5 bar pattern shows bullish bias with some pullback"
        elif bear_count >= 3:
            summary = "5 bar pattern shows bearish bias with some bounce"
        else:
            summary = "5 bar pattern shows mixed/consolidation action"

        return summary

    def _assess_trap_risk(
        self,
        ohlcv: pd.DataFrame,
        direction: str,
        always_in: str,
        pattern: str
    ) -> tuple[str, str]:
        """
        Assess the risk of a bull or bear trap.

        Returns:
            Tuple of (risk_level: LOW/MEDIUM/HIGH, explanation)
        """
        risk_factors = []

        # Trading against always-in direction
        if direction == 'long' and always_in == 'SHORT':
            risk_factors.append("Trading against Always-In SHORT")
        elif direction == 'short' and always_in == 'LONG':
            risk_factors.append("Trading against Always-In LONG")

        # Late in trend (High 3/4 or Low 3/4)
        if pattern in ['high_3', 'high_4', 'low_3', 'low_4']:
            risk_factors.append("Late in trend cycle (possible exhaustion)")

        # Climactic patterns
        if pattern == 'climactic_exhaustion':
            risk_factors.append("Climactic move may squeeze further before reversing")

        # Failed patterns have inherent trap risk
        if 'failed' in pattern:
            risk_factors.append("Failed pattern could fail again (whipsaw)")

        # Assess volume (simplified - would use volume_data in full implementation)
        closes = ohlcv['Close'].values
        if len(closes) >= 3:
            recent_range = max(closes[-3:]) - min(closes[-3:])
            if recent_range / closes[-1] < 0.01:  # Very tight range
                risk_factors.append("Tight range - breakout could trap both sides")

        # Determine risk level
        if len(risk_factors) >= 3:
            level = 'HIGH'
        elif len(risk_factors) >= 1:
            level = 'MEDIUM'
        else:
            level = 'LOW'

        explanation = "; ".join(risk_factors) if risk_factors else "No significant trap signals"

        return level, explanation

    def _calculate_probability(
        self,
        direction: str,
        always_in: str,
        pattern: str,
        trap_risk: str,
        ml_data: dict | None,
        rs_data: dict | None,
        volume_data: dict | None,
        technical_data: dict
    ) -> dict[str, Any]:
        """
        Calculate trade probability with Al Brooks base + adjustments.

        Al Brooks: Base probability is around 40-60% (random).
        Adjustments are made based on context.
        """
        base = 50  # Start at 50-50
        adjustments = []

        # Pattern quality adjustment
        high_probability_patterns = ['high_2', 'low_2', 'breakout_pullback',
                                     'breakdown_pullback', 'failed_breakdown', 'failed_breakout']
        medium_probability_patterns = ['high_1', 'low_1', 'ema_bounce', 'ema_rejection',
                                       'double_bottom', 'double_top']

        if pattern in high_probability_patterns:
            base += 5
            adjustments.append("+5% High probability pattern")
        elif pattern in medium_probability_patterns:
            base += 3
            adjustments.append("+3% Good pattern setup")

        # Always-in alignment
        if direction == 'long' and always_in == 'LONG':
            base += 5
            adjustments.append("+5% Aligned with Always-In LONG")
        elif direction == 'short' and always_in == 'SHORT':
            base += 5
            adjustments.append("+5% Aligned with Always-In SHORT")
        elif always_in == 'NEUTRAL':
            pass  # No adjustment
        else:
            base -= 5
            adjustments.append("-5% Against Always-In direction")

        # Trap risk adjustment
        if trap_risk == 'HIGH':
            base -= 8
            adjustments.append("-8% High trap risk")
        elif trap_risk == 'MEDIUM':
            base -= 3
            adjustments.append("-3% Moderate trap risk")

        # ML prediction alignment
        if ml_data:
            ml_confidence = ml_data.get('confidence', 0.5)
            ml_direction = ml_data.get('trend_direction', 'NEUTRAL')

            if direction == 'long' and ml_direction in ['UP', 'UPTREND', 'BULLISH']:
                bonus = int(ml_confidence * 10)
                base += bonus
                adjustments.append(f"+{bonus}% ML predicts {ml_direction} ({ml_confidence:.0%} conf)")
            elif direction == 'short' and ml_direction in ['DOWN', 'DOWNTREND', 'BEARISH']:
                bonus = int(ml_confidence * 10)
                base += bonus
                adjustments.append(f"+{bonus}% ML predicts {ml_direction} ({ml_confidence:.0%} conf)")
            elif ml_direction not in ['NEUTRAL', 'SIDEWAYS', None]:
                base -= 5
                adjustments.append(f"-5% ML predicts opposite ({ml_direction})")

        # Relative strength alignment
        if rs_data:
            rs_score = rs_data.get('rs_score', 50)
            classification = rs_data.get('classification', 'NEUTRAL')

            if direction == 'long' and rs_score > 70:
                base += 5
                adjustments.append(f"+5% RS Leader (score: {rs_score})")
            elif direction == 'long' and rs_score < 30:
                base -= 5
                adjustments.append(f"-5% RS Laggard (score: {rs_score})")
            elif direction == 'short' and rs_score > 80:
                base += 3
                adjustments.append(f"+3% Extended RS (mean reversion)")
            elif direction == 'short' and rs_score < 30:
                base -= 3
                adjustments.append(f"-3% Already weak (limited downside)")

        # Volume confirmation
        if volume_data:
            quality = volume_data.get('volume_quality_score', {})
            confirmation = quality.get('volume_confirmation', 'NORMAL')
            accumulation = quality.get('accumulation_detected', False)
            distribution = quality.get('distribution_detected', False)

            if direction == 'long' and accumulation:
                base += 5
                adjustments.append("+5% Accumulation pattern detected")
            elif direction == 'short' and distribution:
                base += 5
                adjustments.append("+5% Distribution pattern detected")

            if confirmation == 'STRONG':
                base += 3
                adjustments.append("+3% Strong volume confirmation")
            elif confirmation == 'WEAK':
                base -= 3
                adjustments.append("-3% Weak volume")

            # Dalio Economic Machine adjustments (Ray Dalio's Price = Total Spending / Quantity)
            dalio = volume_data.get('dalio_economic_machine', {})
            if dalio and not dalio.get('error'):
                # Extract Dalio metrics from nested structure
                dalio_ratio_data = dalio.get('dalio_ratio', {})
                dalio_ratio = dalio_ratio_data.get('current', 1.0) if isinstance(dalio_ratio_data, dict) else dalio_ratio_data

                cdf_data = dalio.get('cumulative_dollar_flow', {})
                dollar_flow = cdf_data.get('20d', 0) if isinstance(cdf_data, dict) else cdf_data

                sustain_data = dalio.get('trend_sustainability', {})
                sustainability = sustain_data.get('score', 50) if isinstance(sustain_data, dict) else sustain_data

                # Dalio Ratio alignment (buyers paying premium/discount)
                if direction == 'long' and dalio_ratio >= 1.02:
                    base += 5
                    adjustments.append(f"+5% Dalio: Buyers paying {(dalio_ratio-1)*100:.1f}% premium")
                elif direction == 'long' and dalio_ratio < 0.98:
                    base -= 5
                    adjustments.append(f"-5% Dalio: Buyers paying {(1-dalio_ratio)*100:.1f}% discount")
                elif direction == 'short' and dalio_ratio <= 0.98:
                    base += 5
                    adjustments.append(f"+5% Dalio: Buyers paying {(1-dalio_ratio)*100:.1f}% discount")
                elif direction == 'short' and dalio_ratio > 1.02:
                    base -= 5
                    adjustments.append(f"-5% Dalio: Buyers paying {(dalio_ratio-1)*100:.1f}% premium")

                # Dollar Flow alignment
                if direction == 'long' and dollar_flow > 0:
                    base += 3
                    adjustments.append(f"+3% Dalio: Positive dollar flow (accumulation)")
                elif direction == 'long' and dollar_flow < 0:
                    base -= 3
                    adjustments.append(f"-3% Dalio: Negative dollar flow (distribution)")
                elif direction == 'short' and dollar_flow < 0:
                    base += 3
                    adjustments.append(f"+3% Dalio: Negative dollar flow confirms SHORT")
                elif direction == 'short' and dollar_flow > 0:
                    base -= 3
                    adjustments.append(f"-3% Dalio: Positive dollar flow opposes SHORT")

                # Sustainability score
                if sustainability >= 70:
                    base += 3
                    adjustments.append(f"+3% Dalio: High sustainability ({sustainability})")
                elif sustainability <= 30:
                    base -= 3
                    adjustments.append(f"-3% Dalio: Low sustainability ({sustainability})")

        # Technical indicators
        analysis = technical_data.get('analysis', {})
        rsi = _parse_numeric(analysis.get('rsi', {}).get('value', 50), 50)

        # RSI extremes
        if direction == 'long' and rsi < 30:
            base += 5
            adjustments.append(f"+5% RSI oversold ({rsi:.0f})")
        elif direction == 'short' and rsi > 70:
            base += 5
            adjustments.append(f"+5% RSI overbought ({rsi:.0f})")

        # Clamp probability
        adjusted = max(30, min(80, base))

        return {
            'base': 50,
            'adjusted': adjusted,
            'adjustments': adjustments
        }

    def _calculate_levels(
        self,
        ohlcv: pd.DataFrame,
        direction: str,
        pattern: str,
        technical: dict
    ) -> dict[str, Any]:
        """Calculate entry, stop, and target levels."""
        current_price = ohlcv['Close'].iloc[-1]
        recent_high = ohlcv['High'].tail(10).max()
        recent_low = ohlcv['Low'].tail(10).min()

        # ATR for stop calculation
        atr = self._calculate_atr(ohlcv)

        if direction == 'long':
            # Entry above current bar high or on pullback
            entry = round(current_price * 1.002, 2)  # Slightly above current

            # Stop below recent swing low or 2x ATR
            stop = round(min(recent_low, current_price - 2 * atr), 2)

            # Target based on risk-reward
            risk = entry - stop
            target = round(entry + risk * 2.5, 2)  # 2.5:1 risk/reward
        else:
            # Entry below current bar low
            entry = round(current_price * 0.998, 2)

            # Stop above recent swing high or 2x ATR
            stop = round(max(recent_high, current_price + 2 * atr), 2)

            # Target based on risk-reward
            risk = stop - entry
            target = round(entry - risk * 2.5, 2)

        # Calculate risk/reward ratio
        if direction == 'long':
            risk_amt = entry - stop
            reward_amt = target - entry
        else:
            risk_amt = stop - entry
            reward_amt = entry - target

        rr_ratio = round(reward_amt / risk_amt, 2) if risk_amt > 0 else 0

        return {
            'entry': entry,
            'stop': stop,
            'target': target,
            'risk_reward': rr_ratio,
            'risk_pct': round((risk_amt / entry) * 100, 2),
            'reward_pct': round((reward_amt / entry) * 100, 2)
        }

    def _calculate_atr(self, ohlcv: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(ohlcv) < period:
            return ohlcv['High'].iloc[-1] - ohlcv['Low'].iloc[-1]

        high = ohlcv['High'].values
        low = ohlcv['Low'].values
        close = ohlcv['Close'].values

        tr = []
        for i in range(1, len(ohlcv)):
            tr.append(max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            ))

        return np.mean(tr[-period:])

    def _generate_commentary(
        self,
        ticker: str,
        direction: str,
        pattern: str,
        pattern_desc: str,
        always_in: str,
        bar_reading: str,
        trap_risk: str,
        probability_result: dict,
        levels: dict
    ) -> str:
        """Generate Al Brooks style commentary."""
        dir_text = "LONG" if direction == 'long' else "SHORT"

        # Opening statement
        if probability_result['adjusted'] >= 65:
            quality = "high probability"
        elif probability_result['adjusted'] >= 55:
            quality = "reasonable"
        else:
            quality = "marginal"

        commentary = f"This is a {quality} {dir_text} setup. "

        # Pattern description
        commentary += f"The pattern is {pattern_desc}. "

        # Always-in context
        if always_in == dir_text:
            commentary += f"Market is Always-In {always_in}, aligned with this trade. "
        elif always_in == 'NEUTRAL':
            commentary += "Market is in trading range - need clear breakout. "
        else:
            commentary += f"CAUTION: Market is Always-In {always_in}, against this trade direction. "

        # Bar reading
        commentary += f"{bar_reading}. "

        # Trap risk
        if trap_risk == 'HIGH':
            commentary += "HIGH TRAP RISK - consider waiting for confirmation bar. "
        elif trap_risk == 'MEDIUM':
            commentary += "Moderate trap risk - use tight stop. "

        # Entry recommendation
        if probability_result['adjusted'] >= 60:
            commentary += f"Entry above ${levels['entry']:.2f} with stop at ${levels['stop']:.2f}. "
            commentary += f"Target ${levels['target']:.2f} for {levels['risk_reward']:.1f}:1 risk/reward."
        else:
            commentary += f"Wait for stronger setup or confirmation bar above ${levels['entry']:.2f}."

        return commentary

    def _empty_analysis(self, reason: str) -> dict[str, Any]:
        """Return empty analysis structure with reason."""
        return {
            'always_in': 'UNKNOWN',
            'pattern': 'unknown',
            'pattern_description': reason,
            'bar_reading': reason,
            'trap_risk': 'UNKNOWN',
            'trap_explanation': reason,
            'base_probability': 50,
            'adjusted_probability': 50,
            'probability_adjustments': [],
            'entry': 0,
            'stop': 0,
            'target': 0,
            'risk_reward_ratio': 0,
            'commentary': reason
        }


class ScannerAnalyzer:
    """
    Deep Analysis Pipeline for Scanner Candidates.

    Orchestrates:
    1. Calls to existing analysis tools (technical, ML, RS, volume)
    2. Al Brooks price action analysis
    3. Composite scoring
    4. Rich output generation

    Updated Scoring Weights (Inflection Point Detection):
    - Momentum Quality (30): ADX, RSI, EMA20, MACD
    - Pattern Quality (25): Breakout, Volume, Trend Days
    - Relative Strength (15): RS vs SPY
    - Catalyst Quality (20): Earnings, Insider, IV
    - Al Brooks Pattern (10): Pattern type, completion
    """

    # Scoring weights (must sum to 100) - Updated for inflection detection
    WEIGHTS = {
        'momentum': 30,   # ADX, RSI, EMA20, MACD alignment
        'pattern': 25,    # Breakout patterns, volume surge, trend days
        'rs': 15,         # Relative Strength vs benchmark
        'catalyst': 20,   # Earnings proximity, IV rank, insider activity
        'brooks': 10,     # Al Brooks pattern + probability
    }

    # Max consecutive trend days before exhaustion
    MAX_TREND_DAYS = 6

    def __init__(self):
        self.brooks_analyzer = AlBrooksAnalyzer()

    def count_trend_days(
        self,
        ohlcv: pd.DataFrame,
        direction: Literal['long', 'short'],
        use_atr_weighting: bool = True
    ) -> int:
        """
        Count trend days with ATR-weighted significance (PROPOSAL 4).

        IMPROVED LOGIC:
        - A "trend day" requires price move > 0.3*ATR in the trend direction
        - Allows up to 2 small counter-trend days without resetting
        - Small moves (< 0.3*ATR) don't count as trend OR counter-trend

        Tier 2 Pattern Quality Filter:
        - LONG: Count significant up days
        - SHORT: Count significant down days

        Args:
            ohlcv: DataFrame with OHLC data
            direction: 'long' or 'short'
            use_atr_weighting: If True, use ATR-weighted logic; if False, use simple count

        Returns:
            Number of trend days (reject if > MAX_TREND_DAYS)
        """
        if ohlcv is None or len(ohlcv) < 2:
            return 0

        closes = ohlcv['Close'].values

        # Fall back to simple counting if ATR weighting disabled or insufficient data
        if not use_atr_weighting or len(ohlcv) < 15:
            # Original simple logic
            count = 0
            if direction == 'long':
                for i in range(len(closes) - 1, 0, -1):
                    if closes[i] > closes[i - 1]:
                        count += 1
                    else:
                        break
            else:
                for i in range(len(closes) - 1, 0, -1):
                    if closes[i] < closes[i - 1]:
                        count += 1
                    else:
                        break
            return count

        # === PROPOSAL 4: ATR-Weighted Trend Day Counting ===
        # Calculate ATR for significance threshold
        highs = ohlcv['High'].values
        lows = ohlcv['Low'].values

        # True Range calculation
        tr = []
        for i in range(1, len(ohlcv)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i - 1])
            tr3 = abs(lows[i] - closes[i - 1])
            tr.append(max(tr1, tr2, tr3))

        if len(tr) < 14:
            # Not enough data for ATR, fall back to simple count
            return self.count_trend_days(ohlcv, direction, use_atr_weighting=False)

        # Calculate 14-period ATR
        atr_14 = sum(tr[-14:]) / 14

        # Threshold: Move must be > 30% of ATR to count as significant
        threshold = 0.3

        trend_days = 0
        counter_trend_days = 0
        max_allowed_counter_trend = 2  # Allow 2 small pullbacks

        for i in range(len(closes) - 1, 0, -1):
            # Calculate daily move as % of price
            move = closes[i] - closes[i - 1]
            atr_pct = atr_14 / closes[i - 1] if closes[i - 1] > 0 else 0

            # Significant move threshold
            significant_threshold = threshold * atr_pct * closes[i - 1]

            if direction == 'long':
                if move > significant_threshold:
                    # Significant up day - counts as trend day
                    trend_days += 1
                    counter_trend_days = 0  # Reset counter-trend
                elif move < -significant_threshold:
                    # Significant down day - counter-trend
                    counter_trend_days += 1
                    if counter_trend_days > max_allowed_counter_trend:
                        break  # Too many counter-trend days, stop counting
                # else: insignificant move, continue counting

            else:  # short
                if move < -significant_threshold:
                    # Significant down day - counts as trend day
                    trend_days += 1
                    counter_trend_days = 0
                elif move > significant_threshold:
                    # Significant up day - counter-trend
                    counter_trend_days += 1
                    if counter_trend_days > max_allowed_counter_trend:
                        break
                # else: insignificant move, continue counting

        return trend_days

    def is_trend_exhausted(
        self,
        ohlcv: pd.DataFrame,
        direction: Literal['long', 'short']
    ) -> tuple[bool, int]:
        """
        Check if trend shows exhaustion based on consecutive days.

        Returns:
            Tuple of (is_exhausted, trend_day_count)
        """
        trend_days = self.count_trend_days(ohlcv, direction)
        is_exhausted = trend_days >= self.MAX_TREND_DAYS
        return is_exhausted, trend_days

    def analyze_candidate(
        self,
        ticker: str,
        direction: Literal['long', 'short'],
        tv_data: dict,
        technical_fn=None,
        ml_fn=None,
        rs_fn=None,
        volume_fn=None,
        get_ohlcv_fn=None
    ) -> dict[str, Any]:
        """
        Run full analysis pipeline on a candidate.

        Args:
            ticker: Stock symbol
            direction: Trade direction (long/short)
            tv_data: Data from TradingView scanner
            technical_fn: Function to call analyze_technical (optional)
            ml_fn: Function to call analyze_ml_enhanced (optional)
            rs_fn: Function to call calculate_relative_strength_tool (optional)
            volume_fn: Function to call analyze_volume_tool (optional)
            get_ohlcv_fn: Function to get OHLCV data for Brooks analysis

        Returns:
            Complete analysis with all components and composite score
        """
        result = {
            'symbol': ticker,
            'direction': direction.upper(),
            'price': tv_data.get('close', tv_data.get('price', 0)),
            'tv_data': tv_data,
        }

        # Initialize scores with new weight structure
        scores = {
            'momentum_score': 0,   # 30 pts max
            'pattern_score': 0,    # 25 pts max
            'rs_score': 0,         # 15 pts max
            'catalyst_score': 0,   # 20 pts max
            'brooks_score': 0,     # 10 pts max
            # Legacy scores for compatibility
            'technical_score': 0,
            'ml_score': 0,
            'volume_score': 0,
        }

        # 1. Technical Analysis (for momentum scoring)
        technical_data = None
        if technical_fn:
            try:
                technical_data = technical_fn(ticker, period="3mo", include_ml_analysis=False)
                scores['technical_score'] = self._score_technical(technical_data, direction)
                result['technical'] = self._summarize_technical(technical_data)
            except Exception as e:
                logger.warning(f"Technical analysis failed for {ticker}: {e}")
                result['technical'] = {'error': str(e)}
        else:
            # Use TradingView data as fallback
            scores['technical_score'] = self._score_tv_technical(tv_data, direction)
            result['technical'] = self._summarize_tv_technical(tv_data)

        # 2. ML Analysis (for catalyst scoring)
        ml_data = None
        if ml_fn:
            try:
                ml_result = ml_fn(ticker, period="3mo")
                # Parse ML result if it's a string
                ml_data = self._parse_ml_result(ml_result)
                scores['ml_score'] = self._score_ml(ml_data, direction)
                result['ml_prediction'] = ml_data
            except Exception as e:
                logger.warning(f"ML analysis failed for {ticker}: {e}")
                result['ml_prediction'] = {'error': str(e)}

        # 3. Relative Strength
        rs_data = None
        if rs_fn:
            try:
                benchmark = "SPY" if not ticker.endswith(".TO") else "XIU.TO"
                rs_data = rs_fn(ticker, benchmark=benchmark, period="3mo")
                scores['rs_score'] = self._score_rs(rs_data, direction)
                result['relative_strength'] = rs_data
            except Exception as e:
                logger.warning(f"RS analysis failed for {ticker}: {e}")
                result['relative_strength'] = {'error': str(e)}

        # 4. Volume Analysis (for pattern scoring)
        volume_data = None
        if volume_fn:
            try:
                volume_data = volume_fn(ticker, period="3mo", include_quality_score=True)
                scores['volume_score'] = self._score_volume(volume_data, direction)
                result['volume_analysis'] = self._summarize_volume(volume_data)
            except Exception as e:
                logger.warning(f"Volume analysis failed for {ticker}: {e}")
                result['volume_analysis'] = {'error': str(e)}

        # 5. Get OHLCV data for Brooks and Trend Day analysis
        ohlcv = None
        if get_ohlcv_fn:
            try:
                ohlcv = get_ohlcv_fn(ticker)
            except Exception as e:
                logger.warning(f"Failed to get OHLCV for {ticker}: {e}")

        # 6. Calculate Trend Day Counter (Tier 2)
        trend_days = self.count_trend_days(ohlcv, direction) if ohlcv is not None else 0
        is_exhausted, _ = self.is_trend_exhausted(ohlcv, direction) if ohlcv is not None else (False, 0)
        result['trend_days'] = trend_days
        result['trend_exhausted'] = is_exhausted

        # 7. Al Brooks Analysis
        brooks_analysis = self.brooks_analyzer.analyze(
            ticker=ticker,
            direction=direction,
            ohlcv_data=ohlcv,
            technical_data=technical_data or {'analysis': {}},
            ml_data=ml_data,
            rs_data=rs_data,
            volume_data=volume_data
        )
        result['brooks_analysis'] = brooks_analysis

        # 8. Calculate NEW scores (Tier-based scoring)
        scores['momentum_score'] = self._score_momentum(
            technical_data or {}, tv_data, direction
        )
        scores['pattern_score'] = self._score_pattern(
            tv_data, direction, trend_days, volume_data  # Pass volume_data for CVD bonus
        )
        scores['catalyst_score'] = self._score_catalyst(ml_data, direction, ticker)
        scores['brooks_score'] = self._score_brooks(brooks_analysis)

        # 9. Exhaustion Score Analysis (NEW - Tier 4 Exclusion Check)
        exhaustion_data = None
        if _volumetric_available:
            try:
                exhaustion_data = calculate_exhaustion_score(ticker, direction.upper(), "3mo")
                result['exhaustion'] = exhaustion_data

                # Apply tiered exhaustion response
                exhaustion_score = exhaustion_data.get('score', 0)
                exhaustion_level = exhaustion_data.get('level', 'UNKNOWN')
                exhaustion_action = exhaustion_data.get('suggested_action', 'PROCEED')

                if exhaustion_action == 'EXCLUDE':
                    result['tier4_exclusion'] = {
                        'excluded': True,
                        'reason': f"Exhaustion score {exhaustion_score}/100 - {exhaustion_level}",
                        'action': 'EXCLUDE'
                    }
                elif exhaustion_action == 'REDUCE_SIZE':
                    result['tier4_exclusion'] = {
                        'excluded': False,
                        'reason': f"Exhaustion score {exhaustion_score}/100 - reduce position by 50%",
                        'action': 'REDUCE_SIZE',
                        'size_multiplier': 0.5
                    }
                elif exhaustion_action == 'FLAG':
                    result['tier4_exclusion'] = {
                        'excluded': False,
                        'reason': f"Exhaustion warning: score {exhaustion_score}/100",
                        'action': 'FLAG'
                    }
                else:
                    result['tier4_exclusion'] = {
                        'excluded': False,
                        'reason': 'No exhaustion concern',
                        'action': 'PROCEED'
                    }
            except Exception as e:
                logger.warning(f"Exhaustion analysis failed for {ticker}: {e}")
                result['exhaustion'] = {'error': str(e)}
                result['tier4_exclusion'] = {'excluded': False, 'action': 'PROCEED'}
        else:
            result['tier4_exclusion'] = {'excluded': False, 'action': 'PROCEED'}

        # 10. Liquidity Zone Checks (from volume_data) - Tier 4 enhancements
        if volume_data and _volumetric_available:
            liquidity_zones = volume_data.get('liquidity_zones', {})
            multi_vwap = volume_data.get('multi_vwap', {})

            # Store liquidity analysis in result
            result['liquidity_zones'] = liquidity_zones
            result['multi_vwap'] = multi_vwap

            current_tier4 = result.get('tier4_exclusion', {})

            # Check for Low Volume Gap - FLAG, don't exclude (per plan revision)
            if liquidity_zones.get('current_zone_type') == 'LOW_VOLUME_GAP':
                if current_tier4.get('action') == 'PROCEED':
                    result['tier4_exclusion'] = {
                        'excluded': False,
                        'reason': 'Price in Low Volume Gap - wider stop recommended (3x ATR)',
                        'action': 'FLAG_LVG',
                        'stop_multiplier': 3.0,
                        'size_multiplier': 0.7  # Reduce position by 30%
                    }
                else:
                    # Append to existing reason
                    current_tier4['reason'] += '; Also in Low Volume Gap'
                    current_tier4['stop_multiplier'] = 3.0
                    result['tier4_exclusion'] = current_tier4

            # Check for VWAP extreme extension - FLAG, don't exclude
            if multi_vwap.get('extreme_extension', False):
                sigma_dist = multi_vwap.get('sigma_distance', 0)
                if current_tier4.get('action') in ['PROCEED', 'FLAG_LVG']:
                    if current_tier4.get('action') == 'PROCEED':
                        result['tier4_exclusion'] = {
                            'excluded': False,
                            'reason': f'Price extended {sigma_dist:.1f}σ from VWAP - mean reversion risk',
                            'action': 'FLAG_EXTENDED',
                            'mean_reversion_target': multi_vwap.get('mean_reversion_target')
                        }
                    else:
                        current_tier4['reason'] += f'; Also extended {sigma_dist:.1f}σ from VWAP'
                        current_tier4['mean_reversion_target'] = multi_vwap.get('mean_reversion_target')
                        result['tier4_exclusion'] = current_tier4

        # Calculate composite score using new weights
        composite = self._calculate_composite(scores)
        result['composite_score'] = composite
        result['scores'] = scores

        # Apply exhaustion penalty to composite if flagged
        if exhaustion_data and exhaustion_data.get('suggested_action') == 'REDUCE_SIZE':
            result['composite_score_adjusted'] = composite * 0.8  # 20% penalty
        elif exhaustion_data and exhaustion_data.get('suggested_action') == 'FLAG':
            result['composite_score_adjusted'] = composite * 0.9  # 10% penalty
        else:
            result['composite_score_adjusted'] = composite

        # Generate recommendation
        result['recommendation'] = self._generate_recommendation(
            composite, direction, brooks_analysis
        )

        return result

    def _score_momentum(self, data: dict, tv_data: dict, direction: str) -> int:
        """Score momentum quality (0-30 points).

        Tier 1 Momentum Scoring:
        - ADX 20-40 (trending but not exhausted): 8 pts
        - RSI 40-65 (long) / 35-60 (short): 8 pts
        - EMA20 Distance < 5%: 7 pts
        - MACD Histogram alignment: 7 pts
        """
        score = 0

        # Get values from TV data or technical data
        adx = tv_data.get('ADX', 25)
        rsi = tv_data.get('RSI', 50)
        ema20 = tv_data.get('EMA20', 0)
        close = tv_data.get('close', 0)
        macd = tv_data.get('MACD.macd', 0)
        macd_signal = tv_data.get('MACD.signal', 0)

        # Override with technical data if available
        if data and 'analysis' in data:
            analysis = data['analysis']
            rsi = _parse_numeric(analysis.get('rsi', {}).get('value', rsi), rsi)

        # ADX Score (0-8 pts): Trending but not exhausted
        if 20 <= adx <= 40:
            score += 8  # Optimal range
        elif 15 <= adx < 20 or 40 < adx <= 45:
            score += 5  # Acceptable
        elif adx > 45:
            score += 2  # Exhausted trend
        # else: score += 0 (no trend)

        # RSI Score (0-8 pts): Room to run
        if direction == 'long':
            if 40 <= rsi <= 65:
                score += 8  # Optimal range - room to run
            elif 35 <= rsi < 40 or 65 < rsi <= 70:
                score += 5  # Acceptable
            elif rsi < 35:
                score += 2  # Potentially falling knife
            # else: overbought, no points
        else:  # short
            if 35 <= rsi <= 60:
                score += 8  # Optimal range - room to fall
            elif 30 <= rsi < 35 or 60 < rsi <= 65:
                score += 5  # Acceptable
            elif rsi > 65:
                score += 2  # May squeeze higher first
            # else: oversold, no points

        # EMA20 Distance Score (0-7 pts): Price near trend
        if ema20 > 0 and close > 0:
            ema_distance = abs((close - ema20) / ema20) * 100
            if ema_distance < 3:
                score += 7  # Very close to EMA
            elif ema_distance < 5:
                score += 5  # Within 5%
            elif ema_distance < 8:
                score += 2  # Somewhat extended
            # else: too far, no points

        # MACD Score (0-7 pts): Histogram alignment
        if direction == 'long':
            if macd > macd_signal:
                score += 7  # MACD bullish
            elif macd > macd_signal * 0.95:
                score += 3  # Near crossover
        else:  # short
            if macd < macd_signal:
                score += 7  # MACD bearish
            elif macd < macd_signal * 1.05:
                score += 3  # Near crossover

        return max(0, min(30, score))

    def _score_pattern(
        self,
        tv_data: dict,
        direction: str,
        trend_days: int = 0,
        volume_data: dict = None
    ) -> int:
        """Score pattern quality (0-25 points + CVD bonus).

        Tier 2 Pattern Scoring:
        - Consolidation Breakout: 10 pts
        - Volume Surge 1.5-4x: 8 pts
        - Trend Day Counter < 6: 7 pts
        - CVD Confirmation Bonus: +3 pts (if CVD aligns with direction)
        """
        score = 0

        close = tv_data.get('close', 0)
        high_20d = tv_data.get('High.1M', 0)  # Using 1-month high as proxy for 20-day
        low_20d = tv_data.get('Low.1M', 0)    # Using 1-month low as proxy for 20-day
        rel_vol = tv_data.get('relative_volume_10d_calc', 1)

        # Consolidation Breakout Score (0-10 pts)
        if direction == 'long' and high_20d > 0:
            if close > high_20d:
                score += 10  # Breaking 20-day high
            elif close > high_20d * 0.98:
                score += 5  # Near breakout
        elif direction == 'short' and low_20d > 0:
            if close < low_20d:
                score += 10  # Breaking 20-day low
            elif close < low_20d * 1.02:
                score += 5  # Near breakdown

        # Volume Score (0-8 pts)
        if 1.5 <= rel_vol <= 4.0:
            score += 8  # Optimal volume surge
        elif 1.2 <= rel_vol < 1.5:
            score += 5  # Moderate volume
        elif rel_vol > 4.0:
            score += 3  # Potentially panic buying/selling

        # Trend Day Score (0-7 pts): Not too extended
        if trend_days <= 3:
            score += 7  # Fresh move
        elif trend_days <= 5:
            score += 4  # Moderate extension
        elif trend_days >= 6:
            score += 0  # Exhausted - no points

        # CVD Confirmation Bonus (0-3 pts) - NEW
        # If CVD trend aligns with trade direction, add bonus points
        if volume_data and _volumetric_available:
            cvd_analysis = volume_data.get('cvd_analysis', {})
            cvd_trend = cvd_analysis.get('cvd_trend', 'FLAT')
            cvd_divergence = cvd_analysis.get('divergence', {}).get('signal', 'NONE')

            if direction == 'long':
                # For LONG: Rising CVD or bullish divergence = confirmation
                if cvd_trend == 'RISING':
                    score += 3
                elif cvd_divergence == 'BULLISH_DIVERGENCE':
                    score += 2  # Sellers exhausted at support
            else:  # short
                # For SHORT: Falling CVD or bearish divergence = confirmation
                if cvd_trend == 'FALLING':
                    score += 3
                elif cvd_divergence == 'BEARISH_DIVERGENCE':
                    score += 2  # Buyers exhausted at resistance

        return max(0, min(28, score))  # Max 28 with CVD bonus

    def _get_days_to_earnings(self, ticker: str) -> int:
        """Get days until next earnings announcement.

        Returns:
            Days to earnings (999 if no upcoming earnings found)
        """
        try:
            import yfinance as yf
            from datetime import datetime, timedelta

            t = yf.Ticker(ticker)
            calendar = t.calendar

            if calendar is None:
                return 999

            # Try to get earnings date from calendar
            if isinstance(calendar, pd.DataFrame):
                if 'Earnings Date' in calendar.index:
                    earnings_date = calendar.loc['Earnings Date'].iloc[0]
                elif len(calendar) > 0 and 0 in calendar.columns:
                    earnings_date = calendar[0].iloc[0]
                else:
                    return 999
            elif isinstance(calendar, dict):
                earnings_date = calendar.get('Earnings Date', [None])[0]
            else:
                return 999

            if earnings_date is None:
                return 999

            # Convert to datetime if needed
            if isinstance(earnings_date, str):
                earnings_date = pd.to_datetime(earnings_date)

            days = (earnings_date - datetime.now()).days
            return max(0, days)

        except Exception as e:
            logger.debug(f"Failed to get earnings date for {ticker}: {e}")
            return 999

    def _get_historical_beat_rate(self, ticker: str) -> float:
        """Get historical earnings beat rate (last 4 quarters).

        Returns:
            Beat rate as float (0.0 to 1.0), 0.5 if no data
        """
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            earnings = t.earnings_history

            if earnings is None or earnings.empty:
                return 0.5  # Neutral if no data

            # Count beats (actual > estimate)
            recent = earnings.head(4)  # Last 4 quarters
            if 'epsActual' in recent.columns and 'epsEstimate' in recent.columns:
                beats = (recent['epsActual'] > recent['epsEstimate']).sum()
                return beats / len(recent)

            return 0.5

        except Exception as e:
            logger.debug(f"Failed to get beat rate for {ticker}: {e}")
            return 0.5

    def _score_catalyst(self, ml_data: dict, direction: str, ticker: str = None) -> int:
        """Score catalyst quality (0-20 points).

        ENHANCED (December 2025): Now uses detect_catalyst_strength for comprehensive
        catalyst analysis including earnings, insider, options, and institutional data.

        Catalyst Scoring:
        - STRONG catalyst: 20 pts
        - MODERATE catalyst: 15 pts
        - WEAK catalyst: 8 pts
        - NONE: 0 pts (trade not allowed)
        """
        # Try new comprehensive catalyst detection
        if ticker and _new_tools_available:
            try:
                catalyst_data = detect_catalyst_strength(ticker)

                if isinstance(catalyst_data, dict) and 'error' not in catalyst_data:
                    strength = catalyst_data.get('catalyst_strength', 'NONE')
                    catalyst_score = catalyst_data.get('catalyst_score', 0)

                    # Store for later use in report
                    self._last_catalyst_data = catalyst_data

                    # Map strength to score
                    if strength == 'STRONG':
                        return 20
                    elif strength == 'MODERATE':
                        return 15
                    elif strength == 'WEAK':
                        return 8
                    else:  # NONE
                        return 0

            except Exception as e:
                logger.warning(f"New catalyst detection failed for {ticker}: {e}")
                # Fall back to legacy method

        # LEGACY METHOD (fallback)
        score = 10  # Start neutral

        # Earnings proximity scoring (if ticker provided)
        if ticker:
            days_to_earnings = self._get_days_to_earnings(ticker)

            if 7 <= days_to_earnings <= 30:
                score += 8  # Ideal: 1-4 weeks out (high activity pre-earnings)
            elif 30 < days_to_earnings <= 45:
                score += 4  # Acceptable: 30-45 days
            elif 0 <= days_to_earnings <= 4:
                score -= 5  # Binary event risk - too close
            # No change for > 45 days (neutral)

            # Beat rate scoring
            beat_rate = self._get_historical_beat_rate(ticker)
            if direction == 'long' and beat_rate > 0.60:
                score += 5  # Strong beat history for longs
            elif direction == 'short' and beat_rate < 0.50:
                score += 5  # Weak beat history for shorts

        # ML prediction alignment (remaining points)
        if ml_data and 'error' not in ml_data:
            confidence = ml_data.get('confidence', 0.5)
            trend = ml_data.get('trend_direction', 'NEUTRAL')

            if direction == 'long' and trend in ['UP', 'UPTREND', 'BULLISH']:
                score += int(confidence * 6)  # Max 6 pts from ML
            elif direction == 'short' and trend in ['DOWN', 'DOWNTREND', 'BEARISH']:
                score += int(confidence * 6)
            elif trend not in ['NEUTRAL', 'SIDEWAYS', None, '']:
                score -= 3  # Opposing signal

        return max(0, min(20, score))

    def _score_technical(self, data: dict, direction: str) -> int:
        """Score technical analysis (0-25 points) - Legacy method for compatibility."""
        if not data or 'analysis' not in data:
            return 12  # Neutral

        analysis = data['analysis']
        score = 12  # Start neutral

        # RSI - handle string values
        rsi = _parse_numeric(analysis.get('rsi', {}).get('value', 50), 50)
        if direction == 'long':
            if rsi < 35:
                score += 5  # Oversold = bullish
            elif rsi < 45:
                score += 3
            elif rsi > 70:
                score -= 3  # Overbought = bearish for longs
        else:
            if rsi > 65:
                score += 5  # Overbought = bearish
            elif rsi > 55:
                score += 3
            elif rsi < 30:
                score -= 3

        # MACD
        macd_trend = analysis.get('macd', {}).get('trend', 'neutral')
        if direction == 'long' and macd_trend == 'bullish':
            score += 4
        elif direction == 'short' and macd_trend == 'bearish':
            score += 4
        elif macd_trend not in ['neutral', None]:
            score -= 2

        # Moving averages
        ma_trend = analysis.get('moving_averages', {}).get('trend', 'neutral')
        if direction == 'long' and ma_trend == 'bullish':
            score += 4
        elif direction == 'short' and ma_trend == 'bearish':
            score += 4
        elif ma_trend not in ['neutral', None]:
            score -= 2

        return max(0, min(25, score))

    def _score_tv_technical(self, tv_data: dict, direction: str) -> int:
        """Score technical from TradingView data (0-25 points)."""
        score = 12

        rsi = tv_data.get('RSI', 50)
        if rsi is not None:
            if direction == 'long' and rsi < 35:
                score += 5
            elif direction == 'short' and rsi > 65:
                score += 5

        # TradingView recommendation
        rec = tv_data.get('Recommend.All', 0)
        if rec is not None:
            if direction == 'long' and rec > 0.3:
                score += 5
            elif direction == 'short' and rec < -0.3:
                score += 5

        return max(0, min(25, score))

    def _score_ml(self, ml_data: dict, direction: str) -> int:
        """Score ML prediction (0-20 points)."""
        if not ml_data or 'error' in ml_data:
            return 10  # Neutral

        score = 10

        confidence = ml_data.get('confidence', 0.5)
        trend = ml_data.get('trend_direction', 'NEUTRAL')

        # Direction alignment
        if direction == 'long' and trend in ['UP', 'UPTREND', 'BULLISH']:
            score += int(confidence * 10)
        elif direction == 'short' and trend in ['DOWN', 'DOWNTREND', 'BEARISH']:
            score += int(confidence * 10)
        elif trend not in ['NEUTRAL', 'SIDEWAYS', None, '']:
            score -= 5

        return max(0, min(20, score))

    def _score_rs(self, rs_data: dict, direction: str) -> int:
        """Score relative strength (0-15 points)."""
        if not rs_data or 'error' in rs_data:
            return 7  # Neutral

        score = 7
        rs_value = rs_data.get('rs_score', 50)

        if direction == 'long':
            if rs_value > 80:
                score += 8  # Strong leader
            elif rs_value > 60:
                score += 5
            elif rs_value < 30:
                score -= 5  # Laggard
        else:  # short
            if rs_value > 85:
                score += 5  # Extended - mean reversion candidate
            elif rs_value < 30:
                score += 5  # Weak - good for shorting
            elif rs_value > 60:
                score -= 3  # Strong stock - bad short

        return max(0, min(15, score))

    def _score_volume(self, volume_data: dict, direction: str) -> int:
        """Score volume analysis (0-15 points)."""
        if not volume_data:
            return 7  # Neutral

        score = 7

        quality = volume_data.get('volume_quality_score', {})

        # Accumulation/Distribution
        if direction == 'long' and quality.get('accumulation_detected'):
            score += 5
        elif direction == 'short' and quality.get('distribution_detected'):
            score += 5

        # Volume confirmation
        confirmation = quality.get('volume_confirmation', 'NORMAL')
        if confirmation == 'STRONG':
            score += 3
        elif confirmation == 'WEAK':
            score -= 3

        return max(0, min(15, score))

    def _score_brooks(self, brooks: dict) -> int:
        """Score Al Brooks analysis (0-10 points).

        Updated to 10 pts weight for inflection detection focus.
        """
        if not brooks or brooks.get('always_in') == 'UNKNOWN':
            return 5  # Neutral

        # Base score from adjusted probability
        prob = brooks.get('adjusted_probability', 50)

        # Map 30-80 probability to 0-10 score
        score = int((prob - 30) / 5)

        # Bonus for low trap risk
        if brooks.get('trap_risk') == 'LOW':
            score += 1
        elif brooks.get('trap_risk') == 'HIGH':
            score -= 2

        # Bonus for good risk/reward
        rr = brooks.get('risk_reward_ratio', 0)
        if rr >= 2.5:
            score += 1

        return max(0, min(10, score))

    def _calculate_composite(self, scores: dict) -> int:
        """Calculate weighted composite score (0-100).

        New scoring system for inflection point detection:
        - Momentum: 30 pts (ADX, RSI, EMA20, MACD)
        - Pattern: 25 pts (Breakout, Volume, Trend Days)
        - RS: 15 pts (Relative Strength)
        - Catalyst: 20 pts (Earnings, IV, Insider)
        - Brooks: 10 pts (Pattern quality)
        """
        # Map old scores to new weights
        momentum_score = scores.get('momentum_score', scores.get('technical_score', 15))
        pattern_score = scores.get('pattern_score', scores.get('volume_score', 12))
        rs_score = scores.get('rs_score', 7)
        catalyst_score = scores.get('catalyst_score', scores.get('ml_score', 10))
        brooks_score = scores.get('brooks_score', 5)

        # Scale to new weights
        # momentum: 0-30, pattern: 0-25, rs: 0-15, catalyst: 0-20, brooks: 0-10
        return min(100, max(0,
            momentum_score +
            pattern_score +
            rs_score +
            catalyst_score +
            brooks_score
        ))

    def _generate_recommendation(
        self,
        composite: int,
        direction: str,
        brooks: dict
    ) -> dict[str, Any]:
        """Generate recommendation based on composite score."""
        dir_text = direction.upper()

        if composite >= 80:
            label = f"STRONG {dir_text}"
            action = "Enter position with full size"
        elif composite >= 65:
            label = dir_text
            action = "Enter with reduced size, add on confirmation"
        elif composite >= 50:
            label = "WATCH"
            action = "Wait for confirmation bar or additional signals"
        else:
            label = "SKIP"
            action = "Low probability setup - pass"

        return {
            'label': label,
            'action': action,
            'brooks_pattern': brooks.get('pattern', 'unknown'),
            'brooks_probability': brooks.get('adjusted_probability', 50),
            'trap_risk': brooks.get('trap_risk', 'UNKNOWN')
        }

    def _summarize_technical(self, data: dict) -> dict:
        """Summarize technical analysis for output."""
        if not data or 'analysis' not in data:
            return {}

        analysis = data['analysis']
        return {
            'rsi': analysis.get('rsi', {}).get('value'),
            'rsi_signal': analysis.get('rsi', {}).get('signal'),
            'macd_trend': analysis.get('macd', {}).get('trend'),
            'ma_trend': analysis.get('moving_averages', {}).get('trend'),
            'current_price': analysis.get('current_price'),
        }

    def _summarize_tv_technical(self, tv_data: dict) -> dict:
        """Summarize TradingView technical data."""
        return {
            'rsi': tv_data.get('RSI'),
            'recommendation': tv_data.get('Recommend.All'),
            'sma20': tv_data.get('SMA20'),
            'sma50': tv_data.get('SMA50'),
        }

    def _summarize_volume(self, data: dict) -> dict:
        """Summarize volume analysis."""
        quality = data.get('volume_quality_score', {})
        return {
            'relative_volume': data.get('relative_volume'),
            'obv_trend': data.get('obv_trend'),
            'accumulation': quality.get('accumulation_detected'),
            'distribution': quality.get('distribution_detected'),
            'confirmation': quality.get('volume_confirmation'),
        }

    def _parse_ml_result(self, ml_result) -> dict:
        """Parse ML result (may be string or dict)."""
        if isinstance(ml_result, dict):
            return ml_result

        # Try to parse string result
        if isinstance(ml_result, str):
            result = {
                'trend_direction': 'NEUTRAL',
                'confidence': 0.5
            }

            ml_lower = ml_result.lower()
            if 'bullish' in ml_lower or 'uptrend' in ml_lower:
                result['trend_direction'] = 'UPTREND'
            elif 'bearish' in ml_lower or 'downtrend' in ml_lower:
                result['trend_direction'] = 'DOWNTREND'

            # Try to extract confidence
            import re
            conf_match = re.search(r'(\d{2,3})%', ml_result)
            if conf_match:
                result['confidence'] = int(conf_match.group(1)) / 100

            return result

        return {'trend_direction': 'NEUTRAL', 'confidence': 0.5}


def format_analysis_report(analysis: dict) -> str:
    """
    Format analysis result as rich text report.

    This produces the Al Brooks style output that the user expects.
    Enhanced December 2025 with catalyst, freshness, and trading signal sections.
    """
    lines = []

    symbol = analysis.get('symbol', 'UNKNOWN')
    price = analysis.get('price', 0)
    composite = analysis.get('composite_score', 0)
    direction = analysis.get('direction', 'LONG')
    recommendation = analysis.get('recommendation', {})

    # Header with trading signal if available
    label = recommendation.get('label', 'UNKNOWN')
    trading_signal = analysis.get('trading_signal', {})
    signal = trading_signal.get('signal', '') if trading_signal else ''

    if composite >= 80 or signal in ['STRONG_BUY', 'STRONG_SELL']:
        star = "⭐ "
    else:
        star = ""

    # Add signal emoji
    signal_emoji = ""
    if signal == 'STRONG_BUY':
        signal_emoji = "🟢🟢 "
    elif signal == 'BUY':
        signal_emoji = "🟢 "
    elif signal == 'STRONG_SELL':
        signal_emoji = "🔴🔴 "
    elif signal == 'SELL':
        signal_emoji = "🔴 "
    elif signal == 'WATCH':
        signal_emoji = "👁️ "
    elif signal == 'NO_TRADE':
        signal_emoji = "⛔ "

    lines.append(f"\n#{analysis.get('rank', '?')} {symbol} - ${price:.2f} | Score: {composite}/100 | {signal_emoji}{star}{label}")
    lines.append("═" * 65)

    # NEW: Catalyst Analysis Section
    catalyst = analysis.get('catalyst_analysis', {})
    if catalyst and 'error' not in catalyst:
        strength = catalyst.get('strength', 'N/A')
        cat_score = catalyst.get('score', 0)
        catalysts = catalyst.get('catalysts', [])

        strength_emoji = "🔥" if strength == 'STRONG' else "✅" if strength == 'MODERATE' else "⚠️" if strength == 'WEAK' else "❌"

        lines.append(f"\n📊 CATALYST ANALYSIS (CORE):")
        lines.append(f"   Strength: {strength_emoji} {strength} ({cat_score}/100)")
        if catalysts:
            for cat in catalysts[:3]:
                lines.append(f"   • {cat}")
        if not catalysts:
            lines.append(f"   ⚠️ No catalyst detected - trade not recommended")

    # NEW: Freshness Status
    freshness = analysis.get('freshness_analysis', {})
    if freshness:
        cvd = freshness.get('cvd_trend', 'N/A')
        exhaustion = freshness.get('exhaustion_score', 'N/A')
        trend_days = freshness.get('trend_days', 'N/A')

        cvd_emoji = "↗️" if cvd == 'RISING' else "↘️" if cvd == 'FALLING' else "➡️"
        exhaustion_emoji = "✅" if isinstance(exhaustion, (int, float)) and exhaustion < 50 else "⚠️"

        lines.append(f"\n🌱 FRESHNESS STATUS:")
        lines.append(f"   CVD Trend: {cvd_emoji} {cvd}")
        lines.append(f"   Exhaustion: {exhaustion_emoji} {exhaustion}/100")
        if trend_days != 'N/A':
            lines.append(f"   Trend Days: {trend_days}")

        # Dalio Economic Machine (NEW - part of enhanced Gate 2)
        dalio_ratio = freshness.get('dalio_ratio', None)
        dollar_flow = freshness.get('dollar_flow', None)
        sustainability = freshness.get('sustainability', None)
        dalio_checks = freshness.get('dalio_checks_passing', None)

        if dalio_ratio is not None:
            lines.append(f"\n💰 DALIO ECONOMIC MACHINE:")
            ratio_emoji = "✅" if dalio_ratio >= 1.0 else "⚠️" if dalio_ratio >= 0.95 else "❌"
            ratio_signal = "BULLISH" if dalio_ratio >= 1.0 else "NEUTRAL" if dalio_ratio >= 0.95 else "BEARISH"
            lines.append(f"   Dalio Ratio: {ratio_emoji} {dalio_ratio:.4f} ({ratio_signal})")

            if dollar_flow is not None:
                flow_emoji = "✅" if dollar_flow > 0 else "❌"
                flow_signal = "ACCUMULATION" if dollar_flow > 0 else "DISTRIBUTION"
                lines.append(f"   Dollar Flow: {flow_emoji} ${dollar_flow/1e6:.2f}M ({flow_signal})")

            if sustainability is not None:
                sus_emoji = "✅" if sustainability >= 50 else "⚠️" if sustainability >= 40 else "❌"
                lines.append(f"   Sustainability: {sus_emoji} {sustainability}/100")

            if dalio_checks is not None:
                checks_emoji = "✅" if dalio_checks >= 5 else "⚠️" if dalio_checks == 4 else "❌"
                lines.append(f"   Gate 2 (6 checks): {checks_emoji} {dalio_checks}/6 passing")

    # Technical Analysis Summary
    tech = analysis.get('technical', {})
    if tech and 'error' not in tech:
        rsi = tech.get('rsi', 'N/A')
        macd = tech.get('macd_trend', tech.get('recommendation', 'N/A'))
        ma = tech.get('ma_trend', 'N/A')
        lines.append(f"\n📈 Technical Analysis:")
        lines.append(f"   RSI: {rsi} | MACD: {macd} | MA Trend: {ma}")

    # ML Prediction
    ml = analysis.get('ml_prediction', {})
    if ml and 'error' not in ml:
        trend = ml.get('trend_direction', 'N/A')
        conf = ml.get('confidence', 0)
        lines.append(f"🤖 ML Prediction: {trend} ({conf:.0%} confidence)")

    # Relative Strength
    rs = analysis.get('relative_strength', {})
    if rs and 'error' not in rs:
        rs_score = rs.get('rs_score', 'N/A')
        classification = rs.get('classification', 'N/A')
        lines.append(f"💪 Relative Strength: {rs_score} ({classification})")

    # Volume Analysis
    vol = analysis.get('volume_analysis', {})
    if vol and 'error' not in vol:
        confirmation = vol.get('confirmation', 'N/A')
        accum = "ACCUMULATION" if vol.get('accumulation') else ""
        dist = "DISTRIBUTION" if vol.get('distribution') else ""
        pattern = accum or dist or "NEUTRAL"
        lines.append(f"📦 Volume Analysis: {pattern} | Confirmation: {confirmation}")

    # Al Brooks Analysis (THE MAIN EVENT)
    brooks = analysis.get('brooks_analysis', {})
    if brooks and brooks.get('always_in') != 'UNKNOWN':
        lines.append(f"\n🎯 AL BROOKS ANALYSIS (CENTRAL):")
        lines.append(f"   Pattern: {brooks.get('pattern_description', 'Unknown')}")
        lines.append(f"   Always-In: {brooks.get('always_in', 'UNKNOWN')}")
        lines.append(f"   Bar Reading: {brooks.get('bar_reading', 'N/A')}")
        lines.append(f"   Trap Risk: {brooks.get('trap_risk', 'UNKNOWN')}")

        # Probability
        base = brooks.get('base_probability', 50)
        adjusted = brooks.get('adjusted_probability', 50)
        adjustments = brooks.get('probability_adjustments', [])

        lines.append(f"\n   Brooks Probability: {base}% → Adjusted to {adjusted}%")
        if adjustments:
            adj_str = ", ".join(adjustments[:3])  # Show top 3 adjustments
            lines.append(f"   Adjustments: {adj_str}")

        # Levels
        entry = brooks.get('entry', 0)
        stop = brooks.get('stop', 0)
        target = brooks.get('target', 0)
        rr = brooks.get('risk_reward_ratio', 0)

        if entry > 0:
            lines.append(f"\n   📍 Levels: Entry ${entry:.2f} | Stop ${stop:.2f} | Target ${target:.2f}")
            lines.append(f"   📍 Risk/Reward: {rr:.1f}:1")

        # Commentary
        commentary = brooks.get('commentary', '')
        if commentary:
            lines.append(f"\n   \"{commentary}\"")

    # NEW: Trading Plan Section
    trading_plan = analysis.get('trading_plan', {})
    if trading_plan and 'error' not in trading_plan:
        entry_price = trading_plan.get('entry_price', 0)
        stop_loss = trading_plan.get('stop_loss', {})
        target_1 = trading_plan.get('target_1', {})
        target_2 = trading_plan.get('target_2', {})
        rr_ratio = trading_plan.get('risk_reward_ratio', 0)
        pos_size = trading_plan.get('position_size', {})

        lines.append(f"\n📋 TRADING PLAN:")
        lines.append(f"   Entry: ${entry_price:.2f}")
        if stop_loss:
            lines.append(f"   Stop Loss: ${stop_loss.get('price', 0):.2f} ({stop_loss.get('risk_pct', 0):.1f}% risk)")
        if target_1:
            lines.append(f"   Target 1: ${target_1.get('price', 0):.2f} (+{target_1.get('reward_pct', 0):.1f}%)")
        if target_2:
            lines.append(f"   Target 2: ${target_2.get('price', 0):.2f} (+{target_2.get('reward_pct', 0):.1f}%)")
        lines.append(f"   Risk/Reward: {rr_ratio:.1f}:1")
        if pos_size:
            lines.append(f"   Position Size: {pos_size.get('shares', 0)} shares (${pos_size.get('dollar_risk', 0):.0f} risk)")

    # NEW: Proof of Validity Section
    proof = analysis.get('proof_of_validity', {})
    if proof and 'error' not in proof:
        setups = proof.get('similar_setups', 0)
        success = proof.get('success_rate', 0)
        confidence = proof.get('confidence', 'N/A')

        lines.append(f"\n✅ PROOF OF VALIDITY:")
        lines.append(f"   Similar Setups: {setups} found")
        lines.append(f"   Historical Success: {success:.0f}%")
        lines.append(f"   Confidence: {confidence}")

    # NEW: Gate Status Summary
    gates = analysis.get('gate_status', {})
    if gates:
        lines.append(f"\n🚦 GATE STATUS:")
        for gate, status in gates.items():
            emoji = "✅" if status == 'PASS' else "❌" if status == 'FAIL' else "⚠️"
            lines.append(f"   {emoji} {gate.upper()}: {status}")

    lines.append("")
    return "\n".join(lines)
