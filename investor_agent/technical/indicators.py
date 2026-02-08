"""
Technical indicator detection functions.

EMA, VWAP, volume, order blocks, and supply/demand zone detection.
"""
import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# PRICE/EMA INTERACTION INDICATORS
# ============================================================================

def detect_ema_bounce(
    prices: pd.Series,
    volumes: pd.Series | None = None,
    ema_period: int = 20,
    bounce_tolerance_pct: float = 2.0
) -> dict[str, Any]:
    """
    Detect when price bounces off EMA as support/resistance.

    A bounce occurs when:
    1. Price approaches EMA (within tolerance %)
    2. Price touches or slightly penetrates EMA
    3. Price reverses and moves away from EMA
    4. Ideally with increased volume

    Args:
        prices: Price series
        volumes: Optional volume series for confirmation
        ema_period: EMA period (default 20)
        bounce_tolerance_pct: Distance tolerance from EMA (default 2%)

    Returns:
        {
            'signal': 'BULLISH_BOUNCE' | 'BEARISH_BOUNCE' | 'NONE',
            'ema_level': float,
            'distance_pct': float,
            'bounce_days_ago': int,
            'volume_confirmed': bool,
            'strength': 'STRONG' | 'MODERATE' | 'WEAK'
        }
    """
    if len(prices) < ema_period + 5:
        return {
            'signal': 'NONE',
            'ema_level': 0.0,
            'distance_pct': 0.0,
            'bounce_days_ago': 0,
            'volume_confirmed': False,
            'strength': 'NONE'
        }

    # Calculate EMA
    ema = prices.ewm(span=ema_period, adjust=False).mean()

    current_price = prices.iloc[-1]
    current_ema = ema.iloc[-1]

    # Current distance from EMA
    distance_pct = ((current_price / current_ema) - 1) * 100

    # Look back 5 days for bounce pattern
    bounce_signal = 'NONE'
    bounce_days_ago = 0
    volume_confirmed = False
    strength = 'NONE'

    # Check last 5 days for bounce pattern
    for i in range(1, min(6, len(prices))):
        past_price = prices.iloc[-i]
        past_ema = ema.iloc[-i]
        past_distance_pct = ((past_price / past_ema) - 1) * 100

        # BULLISH BOUNCE: Price was below/at EMA, now above
        if past_distance_pct <= bounce_tolerance_pct and past_distance_pct >= -bounce_tolerance_pct:
            if distance_pct > 1.0:  # Now clearly above
                bounce_signal = 'BULLISH_BOUNCE'
                bounce_days_ago = i

                # Check volume confirmation
                if volumes is not None and i < len(volumes):
                    avg_volume = volumes.iloc[-20:-i].mean() if len(volumes) >= 20 + i else volumes.mean()
                    bounce_volume = volumes.iloc[-i]
                    volume_confirmed = bounce_volume > avg_volume * 1.2  # 20% above average

                # Determine strength
                if distance_pct > 3.0:
                    strength = 'STRONG'
                elif distance_pct > 1.5:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'

                break

        # BEARISH BOUNCE: Price was above/at EMA, now below
        if past_distance_pct <= bounce_tolerance_pct and past_distance_pct >= -bounce_tolerance_pct:
            if distance_pct < -1.0:  # Now clearly below
                bounce_signal = 'BEARISH_BOUNCE'
                bounce_days_ago = i

                # Check volume confirmation
                if volumes is not None and i < len(volumes):
                    avg_volume = volumes.iloc[-20:-i].mean() if len(volumes) >= 20 + i else volumes.mean()
                    bounce_volume = volumes.iloc[-i]
                    volume_confirmed = bounce_volume > avg_volume * 1.2

                # Determine strength
                if distance_pct < -3.0:
                    strength = 'STRONG'
                elif distance_pct < -1.5:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'

                break

    return {
        'signal': bounce_signal,
        'ema_level': current_ema,
        'distance_pct': distance_pct,
        'bounce_days_ago': bounce_days_ago,
        'volume_confirmed': volume_confirmed,
        'strength': strength
    }


def detect_ema_cross(
    prices: pd.Series,
    ema_period: int = 20
) -> dict[str, Any]:
    """
    Detect when price crosses above or below EMA.

    Crossover = price moving from one side of EMA to the other
    This is a dynamic support/resistance breakout/breakdown signal.

    Args:
        prices: Price series
        ema_period: EMA period (default 20)

    Returns:
        {
            'signal': 'BULLISH_CROSS' | 'BEARISH_CROSS' | 'ABOVE' | 'BELOW',
            'ema_level': float,
            'distance_pct': float,
            'cross_days_ago': int
        }
    """
    if len(prices) < ema_period + 5:
        return {
            'signal': 'NONE',
            'ema_level': 0.0,
            'distance_pct': 0.0,
            'cross_days_ago': 0
        }

    # Calculate EMA
    ema = prices.ewm(span=ema_period, adjust=False).mean()

    current_price = prices.iloc[-1]
    current_ema = ema.iloc[-1]

    # Current distance from EMA
    distance_pct = ((current_price / current_ema) - 1) * 100

    # Look back 5 days for crossover
    cross_signal = 'NONE'
    cross_days_ago = 0

    for i in range(1, min(6, len(prices))):
        prev_price = prices.iloc[-i-1]
        prev_ema = ema.iloc[-i-1]
        curr_price = prices.iloc[-i]
        curr_ema = ema.iloc[-i]

        # BULLISH CROSS: Was below, now above
        if prev_price <= prev_ema and curr_price > curr_ema:
            cross_signal = 'BULLISH_CROSS'
            cross_days_ago = i
            break

        # BEARISH CROSS: Was above, now below
        if prev_price >= prev_ema and curr_price < curr_ema:
            cross_signal = 'BEARISH_CROSS'
            cross_days_ago = i
            break

    # If no recent cross, just indicate position
    if cross_signal == 'NONE':
        cross_signal = 'ABOVE' if current_price > current_ema else 'BELOW'

    return {
        'signal': cross_signal,
        'ema_level': current_ema,
        'distance_pct': distance_pct,
        'cross_days_ago': cross_days_ago
    }


def detect_ema_extension(
    prices: pd.Series,
    ema_period: int = 20,
    extension_threshold_pct: float = 5.0
) -> dict[str, Any]:
    """
    Detect when price is extended too far from EMA (reversal warning).

    When price moves >5% from EMA, it's often "overbought" or "oversold"
    relative to the moving average and may snap back (mean reversion).

    Args:
        prices: Price series
        ema_period: EMA period (default 20)
        extension_threshold_pct: Extension threshold (default 5%)

    Returns:
        {
            'signal': 'OVEREXTENDED_BULLISH' | 'OVEREXTENDED_BEARISH' | 'NORMAL',
            'ema_level': float,
            'distance_pct': float,
            'severity': 'EXTREME' | 'HIGH' | 'MODERATE' | 'NORMAL'
        }
    """
    if len(prices) < ema_period:
        return {
            'signal': 'NORMAL',
            'ema_level': 0.0,
            'distance_pct': 0.0,
            'severity': 'NORMAL'
        }

    # Calculate EMA
    ema = prices.ewm(span=ema_period, adjust=False).mean()

    current_price = prices.iloc[-1]
    current_ema = ema.iloc[-1]

    # Current distance from EMA
    distance_pct = ((current_price / current_ema) - 1) * 100

    # Determine signal and severity
    if distance_pct > extension_threshold_pct:
        signal = 'OVEREXTENDED_BULLISH'
        if distance_pct > 10.0:
            severity = 'EXTREME'
        elif distance_pct > 7.5:
            severity = 'HIGH'
        else:
            severity = 'MODERATE'
    elif distance_pct < -extension_threshold_pct:
        signal = 'OVEREXTENDED_BEARISH'
        if distance_pct < -10.0:
            severity = 'EXTREME'
        elif distance_pct < -7.5:
            severity = 'HIGH'
        else:
            severity = 'MODERATE'
    else:
        signal = 'NORMAL'
        severity = 'NORMAL'

    return {
        'signal': signal,
        'ema_level': current_ema,
        'distance_pct': distance_pct,
        'severity': severity
    }


# ============================================================================
# VWAP SUPPORT/RESISTANCE INDICATORS
# ============================================================================

def detect_vwap_bounce(
    prices: pd.Series,
    volumes: pd.Series,
    window: int = 20,
    bounce_tolerance_pct: float = 1.5
) -> dict[str, Any]:
    """
    Detect when price bounces off VWAP as support or resistance.

    VWAP (Volume Weighted Average Price) is considered institutional "fair value".
    When price bounces off VWAP, it often indicates strong support/resistance.

    A bounce occurs when:
    1. Price approaches VWAP (within tolerance %)
    2. Price touches or slightly penetrates VWAP
    3. Price reverses and moves away from VWAP
    4. Ideally with increased volume

    Args:
        prices: Price series
        volumes: Volume series
        window: VWAP calculation window (default 20 days)
        bounce_tolerance_pct: Distance tolerance from VWAP (default 1.5%)

    Returns:
        {
            'signal': 'VWAP_BOUNCE_SUPPORT' | 'VWAP_BOUNCE_RESISTANCE' | 'NONE',
            'vwap_level': float,
            'distance_pct': float,
            'bounce_days_ago': int,
            'volume_confirmed': bool,
            'strength': 'STRONG' | 'MODERATE' | 'WEAK' | 'NONE'
        }
    """
    if len(prices) < window + 5:
        return {
            'signal': 'NONE',
            'vwap_level': 0.0,
            'distance_pct': 0.0,
            'bounce_days_ago': 0,
            'volume_confirmed': False,
            'strength': 'NONE'
        }

    # Calculate VWAP (Volume Weighted Average Price)
    # VWAP = Σ(Price × Volume) / Σ(Volume)
    typical_price = prices  # Using close prices
    vol_sum = volumes.rolling(window=window).sum()
    # Avoid division by zero
    vol_sum = vol_sum.replace(0, np.nan)
    vwap = (typical_price * volumes).rolling(window=window).sum() / vol_sum

    current_price = prices.iloc[-1]
    current_vwap = vwap.iloc[-1]

    # Check for valid VWAP - if NaN, return DATA_UNAVAILABLE signal
    if pd.isna(current_vwap) or current_vwap <= 0:
        return {
            'signal': 'DATA_UNAVAILABLE',
            'vwap_level': 0.0,
            'distance_pct': 0.0,
            'bounce_days_ago': 0,
            'volume_confirmed': False,
            'strength': 'NONE',
            'error': 'VWAP calculation returned NaN - check volume data'
        }

    # Current distance from VWAP
    distance_pct = ((current_price / current_vwap) - 1) * 100

    # Look back 5 days for bounce pattern
    bounce_signal = 'NONE'
    bounce_days_ago = 0
    volume_confirmed = False
    strength = 'NONE'

    # Check last 5 days for bounce pattern
    for i in range(1, min(6, len(prices))):
        past_price = prices.iloc[-i]
        past_vwap = vwap.iloc[-i]

        # Skip if past VWAP is NaN
        if pd.isna(past_vwap) or past_vwap <= 0:
            continue

        past_distance_pct = ((past_price / past_vwap) - 1) * 100

        # SUPPORT BOUNCE: Price was at/below VWAP, now above
        if past_distance_pct <= bounce_tolerance_pct and past_distance_pct >= -bounce_tolerance_pct:
            if distance_pct > 0.5:  # Now clearly above
                bounce_signal = 'VWAP_BOUNCE_SUPPORT'
                bounce_days_ago = i

                # Check volume confirmation
                avg_volume = volumes.iloc[-20:-i].mean() if len(volumes) >= 20 + i else volumes.mean()
                bounce_volume = volumes.iloc[-i]
                volume_confirmed = bounce_volume > avg_volume * 1.2  # 20% above average

                # Determine strength
                if distance_pct > 2.0:
                    strength = 'STRONG'
                elif distance_pct > 1.0:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'

                break

        # RESISTANCE BOUNCE: Price was at/above VWAP, now below
        if past_distance_pct <= bounce_tolerance_pct and past_distance_pct >= -bounce_tolerance_pct:
            if distance_pct < -0.5:  # Now clearly below
                bounce_signal = 'VWAP_BOUNCE_RESISTANCE'
                bounce_days_ago = i

                # Check volume confirmation
                avg_volume = volumes.iloc[-20:-i].mean() if len(volumes) >= 20 + i else volumes.mean()
                bounce_volume = volumes.iloc[-i]
                volume_confirmed = bounce_volume > avg_volume * 1.2

                # Determine strength
                if distance_pct < -2.0:
                    strength = 'STRONG'
                elif distance_pct < -1.0:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'

                break

    return {
        'signal': bounce_signal,
        'vwap_level': float(current_vwap),
        'distance_pct': float(distance_pct),
        'bounce_days_ago': bounce_days_ago,
        'volume_confirmed': volume_confirmed,
        'strength': strength
    }


def detect_vwap_cross(
    prices: pd.Series,
    volumes: pd.Series,
    window: int = 20
) -> dict[str, Any]:
    """
    Detect when price crosses above or below VWAP (sentiment shift).

    VWAP crossovers indicate institutional sentiment shifts:
    - Cross above VWAP = Bullish sentiment (buyers in control)
    - Cross below VWAP = Bearish sentiment (sellers in control)

    Args:
        prices: Price series
        volumes: Volume series
        window: VWAP calculation window (default 20 days)

    Returns:
        {
            'signal': 'BULLISH_VWAP_CROSS' | 'BEARISH_VWAP_CROSS' | 'ABOVE_VWAP' | 'BELOW_VWAP',
            'vwap_level': float,
            'distance_pct': float,
            'cross_days_ago': int
        }
    """
    if len(prices) < window + 5:
        return {
            'signal': 'NONE',
            'vwap_level': 0.0,
            'distance_pct': 0.0,
            'cross_days_ago': 0
        }

    # Calculate VWAP
    typical_price = prices
    vol_sum = volumes.rolling(window=window).sum()
    # Avoid division by zero
    vol_sum = vol_sum.replace(0, np.nan)
    vwap = (typical_price * volumes).rolling(window=window).sum() / vol_sum

    current_price = prices.iloc[-1]
    current_vwap = vwap.iloc[-1]

    # Check for valid VWAP - if NaN, return DATA_UNAVAILABLE signal
    if pd.isna(current_vwap) or current_vwap <= 0:
        return {
            'signal': 'DATA_UNAVAILABLE',
            'vwap_level': 0.0,
            'distance_pct': 0.0,
            'cross_days_ago': 0,
            'error': 'VWAP calculation returned NaN - check volume data'
        }

    # Current distance from VWAP
    distance_pct = ((current_price / current_vwap) - 1) * 100

    # Look back 5 days for crossover
    cross_signal = 'NONE'
    cross_days_ago = 0

    for i in range(1, min(6, len(prices))):
        prev_price = prices.iloc[-i-1]
        prev_vwap = vwap.iloc[-i-1]
        curr_price = prices.iloc[-i]
        curr_vwap = vwap.iloc[-i]

        # Skip if VWAP is NaN
        if pd.isna(prev_vwap) or pd.isna(curr_vwap):
            continue

        # BULLISH CROSS: Was below, now above
        if prev_price <= prev_vwap and curr_price > curr_vwap:
            cross_signal = 'BULLISH_VWAP_CROSS'
            cross_days_ago = i
            break

        # BEARISH CROSS: Was above, now below
        if prev_price >= prev_vwap and curr_price < curr_vwap:
            cross_signal = 'BEARISH_VWAP_CROSS'
            cross_days_ago = i
            break

    # If no recent cross, just indicate position
    if cross_signal == 'NONE':
        cross_signal = 'ABOVE_VWAP' if current_price > current_vwap else 'BELOW_VWAP'

    return {
        'signal': cross_signal,
        'vwap_level': float(current_vwap),
        'distance_pct': float(distance_pct),
        'cross_days_ago': cross_days_ago
    }


def interpret_vwap_position(
    price_vs_vwap_pct: float
) -> dict[str, Any]:
    """
    Interpret price position relative to VWAP.

    VWAP Position Interpretation:
    - Above VWAP: Bullish sentiment, buyers in control
    - Below VWAP: Bearish sentiment, sellers in control
    - Distance magnitude indicates strength

    Args:
        price_vs_vwap_pct: Price distance from VWAP as percentage

    Returns:
        {
            'position': 'STRONG_ABOVE' | 'ABOVE' | 'AT_VWAP' | 'BELOW' | 'STRONG_BELOW',
            'sentiment': 'STRONG_BULLISH' | 'BULLISH' | 'NEUTRAL' | 'BEARISH' | 'STRONG_BEARISH',
            'interpretation': str (human-readable explanation)
        }
    """
    if price_vs_vwap_pct > 3.0:
        return {
            'position': 'STRONG_ABOVE',
            'sentiment': 'STRONG_BULLISH',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% above VWAP - Strong bullish sentiment, buyers firmly in control'
        }
    elif price_vs_vwap_pct > 1.0:
        return {
            'position': 'ABOVE',
            'sentiment': 'BULLISH',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% above VWAP - Bullish sentiment, buyers in control'
        }
    elif price_vs_vwap_pct > -1.0:
        return {
            'position': 'AT_VWAP',
            'sentiment': 'NEUTRAL',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% from VWAP - Neutral sentiment, balanced market'
        }
    elif price_vs_vwap_pct > -3.0:
        return {
            'position': 'BELOW',
            'sentiment': 'BEARISH',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% below VWAP - Bearish sentiment, sellers in control'
        }
    else:
        return {
            'position': 'STRONG_BELOW',
            'sentiment': 'STRONG_BEARISH',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% below VWAP - Strong bearish sentiment, sellers firmly in control'
        }


# ============================================================================
# VOLUME CONFIRMATION INDICATORS
# ============================================================================

def detect_volume_surge(
    volumes: pd.Series,
    window: int = 20,
    threshold_pct: float = 0.50
) -> dict[str, Any]:
    """
    Detect unusual volume spikes (>50% above average).

    Volume surges often precede or confirm significant price moves.
    Research shows volume should increase 50%+ on valid crossovers.

    Args:
        volumes: Volume series
        window: Rolling average window (default 20 days)
        threshold_pct: Surge threshold as decimal (default 0.50 = 50%)

    Returns:
        {
            'signal': 'VOLUME_SURGE' | 'NORMAL' | 'LOW_VOLUME',
            'current_volume': int,
            'avg_volume': float,
            'volume_ratio': float,
            'surge_strength': 'EXTREME' | 'STRONG' | 'MODERATE' | 'NORMAL' | 'LOW'
        }
    """
    if len(volumes) < window:
        return {
            'signal': 'NORMAL',
            'current_volume': 0,
            'avg_volume': 0.0,
            'volume_ratio': 0.0,
            'surge_strength': 'NORMAL'
        }

    # Calculate average volume
    avg_volume = volumes.iloc[-window:].mean()
    current_volume = volumes.iloc[-1]

    # Calculate volume ratio
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0.0

    # Determine signal and strength
    if volume_ratio > (1 + threshold_pct):
        signal = 'VOLUME_SURGE'

        # Classify surge strength
        if volume_ratio > 3.0:  # 3x average
            surge_strength = 'EXTREME'
        elif volume_ratio > 2.0:  # 2x average
            surge_strength = 'STRONG'
        elif volume_ratio > 1.5:  # 1.5x average
            surge_strength = 'MODERATE'
        else:
            surge_strength = 'NORMAL'
    elif volume_ratio < 0.5:  # Less than half average
        signal = 'LOW_VOLUME'
        surge_strength = 'LOW'
    else:
        signal = 'NORMAL'
        surge_strength = 'NORMAL'

    return {
        'signal': signal,
        'current_volume': int(current_volume),
        'avg_volume': float(avg_volume),
        'volume_ratio': float(volume_ratio),
        'surge_strength': surge_strength
    }


def calculate_obv_signal(
    prices: pd.Series,
    volumes: pd.Series
) -> dict[str, Any]:
    """
    Calculate On-Balance Volume (OBV) trend and divergence signals.

    OBV measures buying/selling pressure by adding volume on up days
    and subtracting volume on down days.

    Divergences:
    - Price up, OBV down = Warning (distribution)
    - Price down, OBV up = Bullish (accumulation)

    Args:
        prices: Price series
        volumes: Volume series

    Returns:
        {
            'obv': pd.Series,
            'obv_trend': 'UPTREND' | 'DOWNTREND' | 'NEUTRAL',
            'obv_strength': float (0-100),
            'divergence': 'BULLISH_DIVERGENCE' | 'BEARISH_DIVERGENCE' | 'NONE',
            'signal': 'BULLISH' | 'BEARISH' | 'NEUTRAL'
        }
    """
    if len(prices) < 20 or len(volumes) < 20:
        return {
            'obv': pd.Series(),
            'obv_trend': 'NEUTRAL',
            'obv_strength': 0.0,
            'divergence': 'NONE',
            'signal': 'NEUTRAL'
        }

    # Calculate OBV
    # OBV = Previous OBV + Volume (if price up) or - Volume (if price down)
    price_changes = prices.diff()
    obv = pd.Series(index=prices.index, dtype=float)
    obv.iloc[0] = volumes.iloc[0]

    for i in range(1, len(prices)):
        if price_changes.iloc[i] > 0:
            obv.iloc[i] = obv.iloc[i-1] + volumes.iloc[i]
        elif price_changes.iloc[i] < 0:
            obv.iloc[i] = obv.iloc[i-1] - volumes.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]

    # Determine OBV trend (last 10 days)
    if len(obv) >= 10:
        obv_recent = obv.iloc[-10:]
        obv_slope = (obv_recent.iloc[-1] - obv_recent.iloc[0]) / 10

        if obv_slope > 0:
            obv_trend = 'UPTREND'
            obv_strength = min(100, abs(obv_slope) / obv.iloc[-10:].std() * 50) if obv.iloc[-10:].std() > 0 else 50
        elif obv_slope < 0:
            obv_trend = 'DOWNTREND'
            obv_strength = min(100, abs(obv_slope) / obv.iloc[-10:].std() * 50) if obv.iloc[-10:].std() > 0 else 50
        else:
            obv_trend = 'NEUTRAL'
            obv_strength = 0.0
    else:
        obv_trend = 'NEUTRAL'
        obv_strength = 0.0

    # Detect divergences (last 20 days)
    divergence = 'NONE'
    if len(prices) >= 20 and len(obv) >= 20:
        price_trend = (prices.iloc[-1] - prices.iloc[-20]) / prices.iloc[-20]
        obv_trend_pct = (obv.iloc[-1] - obv.iloc[-20]) / abs(obv.iloc[-20]) if obv.iloc[-20] != 0 else 0

        # Bullish divergence: Price down, OBV up
        if price_trend < -0.05 and obv_trend_pct > 0.05:
            divergence = 'BULLISH_DIVERGENCE'
        # Bearish divergence: Price up, OBV down
        elif price_trend > 0.05 and obv_trend_pct < -0.05:
            divergence = 'BEARISH_DIVERGENCE'

    # Generate final signal
    if obv_trend == 'UPTREND' or divergence == 'BULLISH_DIVERGENCE':
        signal = 'BULLISH'
    elif obv_trend == 'DOWNTREND' or divergence == 'BEARISH_DIVERGENCE':
        signal = 'BEARISH'
    else:
        signal = 'NEUTRAL'

    return {
        'obv': obv,
        'obv_trend': obv_trend,
        'obv_strength': float(obv_strength),
        'divergence': divergence,
        'signal': signal
    }


def confirm_crossover_with_volume(
    cross_signal: str,
    volume_surge: dict[str, Any]
) -> dict[str, Any]:
    """
    Confirm if a crossover signal has volume support.

    Research shows valid crossovers have 50%+ volume increase.
    Volume confirmation significantly improves win rate (75% -> 85%).

    Args:
        cross_signal: Crossover signal ('BULLISH_CROSS', 'BEARISH_CROSS', etc.)
        volume_surge: Result from detect_volume_surge()

    Returns:
        {
            'confirmed': bool,
            'confidence': 'HIGH' | 'MODERATE' | 'LOW',
            'explanation': str
        }
    """
    # Check if this is a crossover signal
    is_crossover = 'CROSS' in cross_signal

    if not is_crossover:
        return {
            'confirmed': False,
            'confidence': 'LOW',
            'explanation': 'Not a crossover signal - no volume confirmation needed'
        }

    # Check volume surge
    has_volume_surge = volume_surge['signal'] == 'VOLUME_SURGE'
    volume_ratio = volume_surge['volume_ratio']

    if has_volume_surge:
        # Determine confidence based on surge strength
        if volume_ratio > 2.0:  # 2x average or more
            confidence = 'HIGH'
            explanation = f'Strong volume confirmation: {volume_ratio:.1f}x average volume'
        elif volume_ratio > 1.5:
            confidence = 'MODERATE'
            explanation = f'Moderate volume confirmation: {volume_ratio:.1f}x average volume'
        else:
            confidence = 'MODERATE'
            explanation = f'Volume confirmation: {volume_ratio:.1f}x average volume'

        confirmed = True
    else:
        confirmed = False
        confidence = 'LOW'
        if volume_surge['signal'] == 'LOW_VOLUME':
            explanation = f'WARNING: Low volume ({volume_ratio:.1f}x avg) - weak crossover'
        else:
            explanation = f'No volume surge ({volume_ratio:.1f}x avg) - unconfirmed crossover'

    return {
        'confirmed': confirmed,
        'confidence': confidence,
        'explanation': explanation
    }


# ============================================================================
# EMA/VWAP CONFLUENCE INDICATORS
# ============================================================================

def detect_ema_vwap_confluence(
    price: float,
    ema_20: float,
    ema_50: float,
    vwap: float
) -> dict[str, Any]:
    """
    Detect confluence between EMAs and VWAP for high-probability setups.

    When multiple indicators align in the same direction, the signal
    strength increases significantly. Research shows confluence of 3+
    indicators improves win rate from 65% -> 80%+.

    Args:
        price: Current price
        ema_20: EMA 20 value
        ema_50: EMA 50 value
        vwap: VWAP value

    Returns:
        {
            'signal': 'STRONG_BULLISH_CONFLUENCE' | 'BULLISH_CONFLUENCE' |
                     'STRONG_BEARISH_CONFLUENCE' | 'BEARISH_CONFLUENCE' |
                     'MIXED_SIGNALS',
            'alignment_count': int (0-4),
            'bullish_count': int,
            'bearish_count': int,
            'strength': 'MAXIMUM' | 'STRONG' | 'MODERATE' | 'WEAK' | 'NONE',
            'price_above_ema20': bool,
            'price_above_ema50': bool,
            'price_above_vwap': bool,
            'ema20_above_ema50': bool,
            'interpretation': str
        }
    """
    # Calculate price positions
    price_above_ema20 = price > ema_20
    price_above_ema50 = price > ema_50
    price_above_vwap = price > vwap
    ema20_above_ema50 = ema_20 > ema_50

    # Count bullish and bearish alignments
    bullish_count = sum([
        price_above_ema20,
        price_above_ema50,
        price_above_vwap,
        ema20_above_ema50
    ])

    bearish_count = sum([
        not price_above_ema20,
        not price_above_ema50,
        not price_above_vwap,
        not ema20_above_ema50
    ])

    # Determine alignment strength (all 4 indicators pointing same way)
    alignment_count = max(bullish_count, bearish_count)

    # Generate signal based on confluence
    if bullish_count == 4:
        signal = 'STRONG_BULLISH_CONFLUENCE'
        strength = 'MAXIMUM'
        interpretation = (
            'MAXIMUM bullish confluence: Price above EMA 20, EMA 50, and VWAP. '
            'EMA 20 above EMA 50. All indicators aligned bullish - HIGHEST probability setup.'
        )
    elif bullish_count == 3:
        signal = 'BULLISH_CONFLUENCE'
        strength = 'STRONG'
        interpretation = (
            'Strong bullish confluence: 3 of 4 indicators aligned bullish. '
            'High probability setup with multiple confirmations.'
        )
    elif bearish_count == 4:
        signal = 'STRONG_BEARISH_CONFLUENCE'
        strength = 'MAXIMUM'
        interpretation = (
            'MAXIMUM bearish confluence: Price below EMA 20, EMA 50, and VWAP. '
            'EMA 20 below EMA 50. All indicators aligned bearish - HIGHEST probability setup.'
        )
    elif bearish_count == 3:
        signal = 'BEARISH_CONFLUENCE'
        strength = 'STRONG'
        interpretation = (
            'Strong bearish confluence: 3 of 4 indicators aligned bearish. '
            'High probability setup with multiple confirmations.'
        )
    elif bullish_count == 2 and bearish_count == 2:
        signal = 'MIXED_SIGNALS'
        strength = 'WEAK'
        interpretation = (
            'Mixed signals: Equal bullish and bearish indicators. '
            'No clear confluence - wait for clearer alignment.'
        )
    else:
        signal = 'MIXED_SIGNALS'
        strength = 'MODERATE'
        if bullish_count > bearish_count:
            interpretation = f'Moderate bullish lean: {bullish_count} bullish vs {bearish_count} bearish indicators.'
        else:
            interpretation = f'Moderate bearish lean: {bearish_count} bearish vs {bullish_count} bullish indicators.'

    return {
        'signal': signal,
        'alignment_count': alignment_count,
        'bullish_count': bullish_count,
        'bearish_count': bearish_count,
        'strength': strength,
        'price_above_ema20': price_above_ema20,
        'price_above_ema50': price_above_ema50,
        'price_above_vwap': price_above_vwap,
        'ema20_above_ema50': ema20_above_ema50,
        'interpretation': interpretation
    }


# ============================================================================
# ORDER BLOCKS (Institutional Footprints)
# ============================================================================

def detect_order_blocks(
    prices: pd.Series,
    lookback: int = 50,
    impulse_threshold_pct: float = 3.0,
    proximity_pct: float = 2.0
) -> dict[str, Any]:
    """
    Detect Order Blocks - institutional supply/demand zones.

    Order Blocks are the last opposing candle before a strong price move.
    They represent zones where institutions executed large orders and often
    act as strong support/resistance when price returns.

    Bullish Order Block: Last down candle before strong up move (buying zone)
    Bearish Order Block: Last up candle before strong down move (selling zone)

    Args:
        prices: Price series (Close prices)
        lookback: How many candles to look back for order blocks
        impulse_threshold_pct: Minimum move % to qualify as impulse (default 3%)
        proximity_pct: How close price must be to order block (default 2%)

    Returns:
        {
            'signal': 'BULLISH_ORDER_BLOCK_TEST' | 'BEARISH_ORDER_BLOCK_TEST' | 'NONE',
            'bullish_blocks': list[dict],  # List of bullish order blocks
            'bearish_blocks': list[dict],  # List of bearish order blocks
            'closest_bullish_block': dict | None,
            'closest_bearish_block': dict | None,
            'distance_to_bullish_pct': float,
            'distance_to_bearish_pct': float,
            'interpretation': str
        }
    """
    if len(prices) < lookback + 5:
        return {
            'signal': 'NONE',
            'bullish_blocks': [],
            'bearish_blocks': [],
            'closest_bullish_block': None,
            'closest_bearish_block': None,
            'distance_to_bullish_pct': 100.0,
            'distance_to_bearish_pct': 100.0,
            'interpretation': 'Insufficient data for order block detection'
        }

    current_price = prices.iloc[-1]
    bullish_blocks = []
    bearish_blocks = []

    # Search for order blocks in lookback period
    for i in range(len(prices) - lookback, len(prices) - 5):
        # Calculate candle direction and size
        candle_change_pct = (prices.iloc[i] - prices.iloc[i-1]) / prices.iloc[i-1] * 100

        # Look ahead for impulse move (next 1-3 candles)
        future_max = prices.iloc[i:i+4].max()
        future_min = prices.iloc[i:i+4].min()

        # Check for bullish impulse (strong up move after down candle)
        if candle_change_pct < 0:  # Down candle
            impulse_up = (future_max - prices.iloc[i]) / prices.iloc[i] * 100
            if impulse_up >= impulse_threshold_pct:
                # This is a bullish order block
                bullish_blocks.append({
                    'candle_index': i,
                    'price_low': prices.iloc[i-1:i+1].min(),
                    'price_high': prices.iloc[i-1:i+1].max(),
                    'impulse_size': impulse_up,
                    'age_days': len(prices) - i - 1
                })

        # Check for bearish impulse (strong down move after up candle)
        elif candle_change_pct > 0:  # Up candle
            impulse_down = (prices.iloc[i] - future_min) / prices.iloc[i] * 100
            if impulse_down >= impulse_threshold_pct:
                # This is a bearish order block
                bearish_blocks.append({
                    'candle_index': i,
                    'price_low': prices.iloc[i-1:i+1].min(),
                    'price_high': prices.iloc[i-1:i+1].max(),
                    'impulse_size': impulse_down,
                    'age_days': len(prices) - i - 1
                })

    # Find closest order blocks to current price
    closest_bullish_block = None
    closest_bearish_block = None
    distance_to_bullish = 100.0
    distance_to_bearish = 100.0

    # Find closest bullish block (below current price)
    bullish_below = [b for b in bullish_blocks if b['price_high'] < current_price]
    if bullish_below:
        closest_bullish_block = min(bullish_below, key=lambda b: abs(current_price - b['price_high']))
        distance_to_bullish = (current_price - closest_bullish_block['price_high']) / current_price * 100

    # Find closest bearish block (above current price)
    bearish_above = [b for b in bearish_blocks if b['price_low'] > current_price]
    if bearish_above:
        closest_bearish_block = min(bearish_above, key=lambda b: abs(b['price_low'] - current_price))
        distance_to_bearish = (closest_bearish_block['price_low'] - current_price) / current_price * 100

    # Determine signal based on proximity
    signal = 'NONE'
    interpretation = ''

    if distance_to_bullish <= proximity_pct and closest_bullish_block is not None:
        signal = 'BULLISH_ORDER_BLOCK_TEST'
        interpretation = (
            f'Price testing bullish order block from {closest_bullish_block["age_days"]} days ago. '
            f'Distance: {distance_to_bullish:.2f}%. '
            f'Original impulse: +{closest_bullish_block["impulse_size"]:.1f}%. '
            f'Potential support zone - watch for bounce.'
        )
    elif distance_to_bearish <= proximity_pct and closest_bearish_block is not None:
        signal = 'BEARISH_ORDER_BLOCK_TEST'
        interpretation = (
            f'Price testing bearish order block from {closest_bearish_block["age_days"]} days ago. '
            f'Distance: {distance_to_bearish:.2f}%. '
            f'Original impulse: -{closest_bearish_block["impulse_size"]:.1f}%. '
            f'Potential resistance zone - watch for rejection.'
        )
    else:
        interpretation = (
            f'No order blocks in proximity. '
            f'Closest bullish block: {distance_to_bullish:.1f}% below. '
            f'Closest bearish block: {distance_to_bearish:.1f}% above.'
        )

    return {
        'signal': signal,
        'bullish_blocks': bullish_blocks,
        'bearish_blocks': bearish_blocks,
        'closest_bullish_block': closest_bullish_block,
        'closest_bearish_block': closest_bearish_block,
        'distance_to_bullish_pct': distance_to_bullish,
        'distance_to_bearish_pct': distance_to_bearish,
        'interpretation': interpretation
    }


# ============================================================================
# SUPPLY/DEMAND ZONES (Price Action Zones)
# ============================================================================

def detect_supply_demand_zones(
    prices: pd.Series,
    lookback: int = 50,
    consolidation_bars: int = 3,
    impulse_threshold_pct: float = 5.0,
    proximity_pct: float = 2.0
) -> dict[str, Any]:
    """
    Detect Supply/Demand Zones - price consolidation areas before strong moves.

    Unlike Order Blocks (single candles), Supply/Demand Zones are consolidation
    ranges where price moved sideways before a strong impulse. These zones
    represent areas of accumulated buying/selling pressure.

    Demand Zone: Consolidation followed by strong rally (buying pressure)
    Supply Zone: Consolidation followed by strong drop (selling pressure)

    Args:
        prices: Price series (Close prices)
        lookback: How many candles to look back for zones
        consolidation_bars: Minimum bars in consolidation (default 3)
        impulse_threshold_pct: Minimum move % to qualify as impulse (default 5%)
        proximity_pct: How close price must be to zone (default 2%)

    Returns:
        {
            'signal': 'DEMAND_ZONE_TEST' | 'SUPPLY_ZONE_TEST' | 'NONE',
            'demand_zones': list[dict],  # List of demand zones (support)
            'supply_zones': list[dict],  # List of supply zones (resistance)
            'closest_demand_zone': dict | None,
            'closest_supply_zone': dict | None,
            'distance_to_demand_pct': float,
            'distance_to_supply_pct': float,
            'interpretation': str
        }
    """
    if len(prices) < lookback + consolidation_bars + 5:
        return {
            'signal': 'NONE',
            'demand_zones': [],
            'supply_zones': [],
            'closest_demand_zone': None,
            'closest_supply_zone': None,
            'distance_to_demand_pct': 100.0,
            'distance_to_supply_pct': 100.0,
            'interpretation': 'Insufficient data for supply/demand zone detection'
        }

    current_price = prices.iloc[-1]
    demand_zones = []
    supply_zones = []

    # Search for consolidation zones followed by impulse moves
    i = len(prices) - lookback
    while i < len(prices) - consolidation_bars - 5:
        # Get consolidation window
        consolidation_window = prices.iloc[i:i+consolidation_bars]

        # Calculate consolidation range
        zone_high = consolidation_window.max()
        zone_low = consolidation_window.min()
        zone_range_pct = (zone_high - zone_low) / zone_low * 100

        # Only consider tight consolidations (range < 3%)
        if zone_range_pct < 3.0:
            # Look for impulse move after consolidation
            future_window_start = i + consolidation_bars
            future_window_end = min(i + consolidation_bars + 10, len(prices))
            future_prices = prices.iloc[future_window_start:future_window_end]

            if len(future_prices) > 0:
                future_high = future_prices.max()
                future_low = future_prices.min()

                # Check for bullish impulse (strong rally from zone)
                impulse_up = (future_high - zone_high) / zone_high * 100
                if impulse_up >= impulse_threshold_pct:
                    # This is a demand zone (support)
                    demand_zones.append({
                        'start_index': i,
                        'zone_low': zone_low,
                        'zone_high': zone_high,
                        'zone_range_pct': zone_range_pct,
                        'impulse_size': impulse_up,
                        'age_days': len(prices) - (i + consolidation_bars) - 1,
                        'consolidation_bars': consolidation_bars
                    })
                    # Skip past this zone
                    i += consolidation_bars + 5
                    continue

                # Check for bearish impulse (strong drop from zone)
                impulse_down = (zone_low - future_low) / zone_low * 100
                if impulse_down >= impulse_threshold_pct:
                    # This is a supply zone (resistance)
                    supply_zones.append({
                        'start_index': i,
                        'zone_low': zone_low,
                        'zone_high': zone_high,
                        'zone_range_pct': zone_range_pct,
                        'impulse_size': impulse_down,
                        'age_days': len(prices) - (i + consolidation_bars) - 1,
                        'consolidation_bars': consolidation_bars
                    })
                    # Skip past this zone
                    i += consolidation_bars + 5
                    continue

        i += 1

    # Find closest zones to current price
    closest_demand_zone = None
    closest_supply_zone = None
    distance_to_demand = 100.0
    distance_to_supply = 100.0

    # Find closest demand zone (below current price)
    demand_below = [z for z in demand_zones if z['zone_high'] < current_price]
    if demand_below:
        closest_demand_zone = min(demand_below, key=lambda z: abs(current_price - z['zone_high']))
        distance_to_demand = (current_price - closest_demand_zone['zone_high']) / current_price * 100

    # Find closest supply zone (above current price)
    supply_above = [z for z in supply_zones if z['zone_low'] > current_price]
    if supply_above:
        closest_supply_zone = min(supply_above, key=lambda z: abs(z['zone_low'] - current_price))
        distance_to_supply = (closest_supply_zone['zone_low'] - current_price) / current_price * 100

    # Determine signal based on proximity
    signal = 'NONE'
    interpretation = ''

    if distance_to_demand <= proximity_pct and closest_demand_zone is not None:
        signal = 'DEMAND_ZONE_TEST'
        interpretation = (
            f'Price testing demand zone from {closest_demand_zone["age_days"]} days ago. '
            f'Distance: {distance_to_demand:.2f}%. '
            f'Zone range: ${closest_demand_zone["zone_low"]:.2f} - ${closest_demand_zone["zone_high"]:.2f}. '
            f'Original impulse: +{closest_demand_zone["impulse_size"]:.1f}%. '
            f'Potential support - watch for bounce.'
        )
    elif distance_to_supply <= proximity_pct and closest_supply_zone is not None:
        signal = 'SUPPLY_ZONE_TEST'
        interpretation = (
            f'Price testing supply zone from {closest_supply_zone["age_days"]} days ago. '
            f'Distance: {distance_to_supply:.2f}%. '
            f'Zone range: ${closest_supply_zone["zone_low"]:.2f} - ${closest_supply_zone["zone_high"]:.2f}. '
            f'Original impulse: -{closest_supply_zone["impulse_size"]:.1f}%. '
            f'Potential resistance - watch for rejection.'
        )
    else:
        interpretation = (
            f'No supply/demand zones in proximity. '
            f'Closest demand zone: {distance_to_demand:.1f}% below. '
            f'Closest supply zone: {distance_to_supply:.1f}% above.'
        )

    return {
        'signal': signal,
        'demand_zones': demand_zones,
        'supply_zones': supply_zones,
        'closest_demand_zone': closest_demand_zone,
        'closest_supply_zone': closest_supply_zone,
        'distance_to_demand_pct': distance_to_demand,
        'distance_to_supply_pct': distance_to_supply,
        'interpretation': interpretation
    }
