"""Pullback Personality Analyzer — Stock-Specific Entry Level Detection.

Learns each stock's unique pullback behavior using 9 institutional techniques:
    1. Historical MA Bounce Rate — which EMA/SMA each stock respects
    2. Volume Profile (VPOC/HVN) — institutional defense zones
    3. ICT Order Blocks — last opposing candle before impulsive move
    4. ICT Fair Value Gaps — 3-candle imbalance gaps price returns to fill
    5. ICT Liquidity Pools — equal highs/lows where stops cluster
    6. Anchored VWAP — cost basis since earnings/gap/breakout events
    7. Ornstein-Uhlenbeck Half-Life — stock-specific mean reversion speed
    8. Keltner Channel — volatility-adjusted pullback bands
    9. Regime-Dependent Depth — pullback depth varies by trend regime

MCP tools (1):
    analyze_pullback_personality — Full pullback personality analysis

References:
    - ICT (Inner Circle Trader): Order Blocks, FVGs, Liquidity Pools
    - Ornstein-Uhlenbeck: Mean reversion half-life estimation
    - Keltner Channel: ATR-based volatility bands
    - Volume Profile: CME/CBOT methodology (POC, VAH, VAL)
"""
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================

def _safe(val):
    """Convert numpy/pandas types to JSON-safe Python."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, (np.ndarray,)):
        return [_safe(v) for v in val]
    if isinstance(val, (pd.Timestamp,)):
        return val.strftime("%Y-%m-%d")
    if pd.isna(val):
        return None
    if isinstance(val, float):
        return round(val, 4)
    return val


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns from yfinance."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _safe_download(ticker: str, period: str = "1y") -> pd.DataFrame | None:
    """Download OHLCV data with error handling."""
    try:
        df = yf.download(ticker, period=period, progress=False)
        if df is None or len(df) == 0:
            return None
        return _flatten(df)
    except Exception as e:
        logger.warning(f"Failed to download {ticker}: {e}")
        return None


# ============================================================================
# 1. Historical MA Bounce Rate
# ============================================================================

def _calculate_ma_values(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Calculate all candidate moving average series."""
    close = df["Close"]
    return {
        "EMA8": close.ewm(span=8, adjust=False).mean(),
        "EMA10": close.ewm(span=10, adjust=False).mean(),
        "EMA21": close.ewm(span=21, adjust=False).mean(),
        "EMA50": close.ewm(span=50, adjust=False).mean(),
        "SMA200": close.rolling(200).mean(),
    }


def _detect_ma_bounces(
    df: pd.DataFrame,
    ma_values: dict[str, pd.Series],
    proximity_pct: float = 0.003,
    bounce_threshold_pct: float = 0.005,
    bounce_window: int = 3,
) -> list[dict[str, Any]]:
    """
    For each MA, count how many times price approached within proximity_pct
    and then bounced vs broke through.

    A bounce: price touches the MA (within proximity), then moves away
    by bounce_threshold_pct in the trend direction within bounce_window bars.

    A break: price closes through the MA and continues.
    """
    results = []
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    n = len(df)

    for ma_name, ma_series in ma_values.items():
        ma = ma_series.values
        bounces = 0
        breaks = 0
        bounce_magnitudes = []
        recent_bounces = 0  # last 60 bars
        recent_total = 0

        for i in range(60, n - bounce_window):
            if np.isnan(ma[i]):
                continue

            # Check proximity: low touched MA from above or high touched from below
            dist_pct = abs(close[i] - ma[i]) / ma[i]
            low_dist = abs(low[i] - ma[i]) / ma[i]
            high_dist = abs(high[i] - ma[i]) / ma[i]

            touched = dist_pct <= proximity_pct or low_dist <= proximity_pct or high_dist <= proximity_pct

            if not touched:
                continue

            is_recent = i >= n - 60

            # Determine if price was above or below MA before touch
            above_ma = close[i - 1] > ma[i - 1] if i > 0 else close[i] > ma[i]

            # Check next bounce_window bars for bounce or break
            bounced = False
            for j in range(1, min(bounce_window + 1, n - i)):
                if above_ma:
                    # Price was above MA, touched it, check if it bounced up
                    move_pct = (close[i + j] - ma[i]) / ma[i]
                    if move_pct > bounce_threshold_pct:
                        bounced = True
                        bounce_magnitudes.append(move_pct * 100)
                        break
                else:
                    # Price was below MA, touched it, check if it bounced down
                    move_pct = (ma[i] - close[i + j]) / ma[i]
                    if move_pct > bounce_threshold_pct:
                        bounced = True
                        bounce_magnitudes.append(move_pct * 100)
                        break

            if bounced:
                bounces += 1
                if is_recent:
                    recent_bounces += 1
            else:
                breaks += 1

            if is_recent:
                recent_total += 1

        total = bounces + breaks
        if total < 3:
            continue

        bounce_rate = bounces / total
        recency_score = recent_bounces / recent_total if recent_total > 0 else 0.5
        avg_bounce = np.mean(bounce_magnitudes) if bounce_magnitudes else 0

        # Composite score: 50% bounce rate + 30% recency + 20% sample size
        sample_factor = min(total / 20, 1.0)
        composite = bounce_rate * 50 + recency_score * 30 + sample_factor * 20

        current_ma_value = float(ma[-1]) if not np.isnan(ma[-1]) else None
        current_price = float(close[-1])
        distance_pct = ((current_price - current_ma_value) / current_ma_value * 100) if current_ma_value else None

        results.append({
            "level_name": ma_name,
            "level_type": "moving_average",
            "bounce_rate": _safe(bounce_rate),
            "bounces": bounces,
            "breaks": breaks,
            "total_touches": total,
            "avg_bounce_pct": _safe(avg_bounce),
            "recency_score": _safe(recency_score),
            "composite_score": _safe(composite),
            "current_value": _safe(current_ma_value),
            "current_distance_pct": _safe(distance_pct),
        })

    return sorted(results, key=lambda x: x["composite_score"], reverse=True)


# ============================================================================
# 2. Volume Profile (VPOC, VAH, VAL, HVN)
# ============================================================================

def _build_volume_profile(
    df: pd.DataFrame,
    lookback_days: int = 60,
    num_bins: int = 80,
) -> dict[str, Any]:
    """
    Build volume profile from daily OHLCV.

    Distributes each bar's volume uniformly across bins between its Low and High.
    Returns POC, VAH, VAL, and High Volume Nodes.
    """
    recent = df.tail(lookback_days).copy()
    if len(recent) < 10:
        return {"error": "Insufficient data for volume profile"}

    price_min = float(recent["Low"].min())
    price_max = float(recent["High"].max())
    if price_max <= price_min:
        return {"error": "Invalid price range"}

    bin_edges = np.linspace(price_min, price_max, num_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    volume_at_price = np.zeros(num_bins)

    for _, row in recent.iterrows():
        lo, hi, vol = float(row["Low"]), float(row["High"]), float(row["Volume"])
        if hi <= lo or vol <= 0:
            continue
        # Find bins that overlap with this bar's range
        lo_idx = max(0, np.searchsorted(bin_edges, lo) - 1)
        hi_idx = min(num_bins - 1, np.searchsorted(bin_edges, hi) - 1)
        num_covered = hi_idx - lo_idx + 1
        if num_covered > 0:
            vol_per_bin = vol / num_covered
            volume_at_price[lo_idx:hi_idx + 1] += vol_per_bin

    # POC = bin with highest volume
    poc_idx = np.argmax(volume_at_price)
    poc = float(bin_centers[poc_idx])

    # Value Area (70% of total volume, expanding from POC)
    total_vol = volume_at_price.sum()
    if total_vol == 0:
        return {"error": "Zero volume in profile"}

    va_vol = volume_at_price[poc_idx]
    lo_boundary = poc_idx
    hi_boundary = poc_idx

    while va_vol / total_vol < 0.70:
        expand_up = volume_at_price[hi_boundary + 1] if hi_boundary + 1 < num_bins else 0
        expand_down = volume_at_price[lo_boundary - 1] if lo_boundary - 1 >= 0 else 0

        if expand_up >= expand_down and hi_boundary + 1 < num_bins:
            hi_boundary += 1
            va_vol += volume_at_price[hi_boundary]
        elif lo_boundary - 1 >= 0:
            lo_boundary -= 1
            va_vol += volume_at_price[lo_boundary]
        else:
            break

    vah = float(bin_edges[hi_boundary + 1])  # Upper edge of highest bin in VA
    val = float(bin_edges[lo_boundary])  # Lower edge of lowest bin in VA

    # Detect High Volume Nodes (peaks in the histogram)
    from scipy.signal import find_peaks
    peaks, properties = find_peaks(volume_at_price, prominence=total_vol * 0.02)
    hvns = []
    for p in peaks:
        if p != poc_idx:
            hvns.append({
                "price": _safe(bin_centers[p]),
                "volume_pct": _safe(volume_at_price[p] / total_vol * 100),
            })
    hvns.sort(key=lambda x: x["volume_pct"], reverse=True)

    current_price = float(df["Close"].iloc[-1])

    return {
        "poc": _safe(poc),
        "vah": _safe(vah),
        "val": _safe(val),
        "poc_distance_pct": _safe((current_price - poc) / poc * 100),
        "hvns": hvns[:5],
        "lookback_days": lookback_days,
        "total_volume": _safe(total_vol),
    }


# ============================================================================
# 3. ICT Order Blocks
# ============================================================================

def _find_swing_points(
    df: pd.DataFrame,
    swing_length: int = 10,
) -> list[dict]:
    """Detect swing highs and lows using fractal method."""
    highs = df["High"].values
    lows = df["Low"].values
    n = len(df)
    swings = []

    for i in range(swing_length, n - swing_length):
        # Swing High: high[i] is highest in window
        if highs[i] == max(highs[i - swing_length:i + swing_length + 1]):
            swings.append({"index": i, "type": "high", "price": float(highs[i])})
        # Swing Low: low[i] is lowest in window
        if lows[i] == min(lows[i - swing_length:i + swing_length + 1]):
            swings.append({"index": i, "type": "low", "price": float(lows[i])})

    return sorted(swings, key=lambda x: x["index"])


def _detect_order_blocks(
    df: pd.DataFrame,
    swing_length: int = 10,
    atr_multiplier: float = 1.5,
) -> list[dict[str, Any]]:
    """
    Detect ICT Order Blocks.

    Bullish OB: Last bearish candle before a bullish break of structure.
    Bearish OB: Last bullish candle before a bearish break of structure.
    Filter: impulse move > atr_multiplier * ATR, OB volume > 1x avg.
    """
    if len(df) < 50:
        return []

    close = df["Close"].values
    open_ = df["Open"].values
    high = df["High"].values
    low = df["Low"].values
    volume = df["Volume"].values
    n = len(df)

    # ATR for filtering
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1]))
    )
    atr_14 = pd.Series(tr).rolling(14).mean().values
    avg_volume = pd.Series(volume).rolling(20).mean().values

    swings = _find_swing_points(df, swing_length)
    order_blocks = []
    dates = df.index

    # Find breaks of structure
    swing_highs = [s for s in swings if s["type"] == "high"]
    swing_lows = [s for s in swings if s["type"] == "low"]

    # Bullish BOS: price breaks above a prior swing high
    for i in range(1, len(swing_highs)):
        bos_level = swing_highs[i - 1]["price"]
        bos_idx = swing_highs[i]["index"]

        # Check if close broke above prior swing high
        if close[bos_idx] <= bos_level:
            continue

        # Impulse strength check
        atr_at_bos = atr_14[min(bos_idx - 1, len(atr_14) - 1)] if bos_idx - 1 < len(atr_14) else 0
        if atr_at_bos and (close[bos_idx] - bos_level) < atr_multiplier * atr_at_bos:
            continue

        # Find last bearish candle before the BOS (the order block)
        for j in range(bos_idx - 1, max(bos_idx - 20, 0), -1):
            if close[j] < open_[j]:  # Bearish candle
                # Volume filter
                vol_ok = avg_volume[j] and volume[j] >= avg_volume[j]
                # Check if OB is still unmitigated (price hasn't closed below OB low since)
                ob_low = float(low[j])
                ob_high = float(high[j])
                mitigated = False
                for k in range(j + 1, n):
                    if close[k] < ob_low:
                        mitigated = True
                        break

                if not mitigated:
                    order_blocks.append({
                        "direction": "bullish",
                        "ob_top": _safe(ob_high),
                        "ob_bottom": _safe(ob_low),
                        "ob_date": _safe(dates[j]),
                        "volume_confirmed": bool(vol_ok),
                        "mitigated": False,
                        "bars_ago": n - 1 - j,
                    })
                break

    # Bearish BOS: price breaks below a prior swing low
    for i in range(1, len(swing_lows)):
        bos_level = swing_lows[i - 1]["price"]
        bos_idx = swing_lows[i]["index"]

        if close[bos_idx] >= bos_level:
            continue

        atr_at_bos = atr_14[min(bos_idx - 1, len(atr_14) - 1)] if bos_idx - 1 < len(atr_14) else 0
        if atr_at_bos and (bos_level - close[bos_idx]) < atr_multiplier * atr_at_bos:
            continue

        for j in range(bos_idx - 1, max(bos_idx - 20, 0), -1):
            if close[j] > open_[j]:  # Bullish candle
                vol_ok = avg_volume[j] and volume[j] >= avg_volume[j]
                ob_low = float(low[j])
                ob_high = float(high[j])
                mitigated = False
                for k in range(j + 1, n):
                    if close[k] > ob_high:
                        mitigated = True
                        break

                if not mitigated:
                    order_blocks.append({
                        "direction": "bearish",
                        "ob_top": _safe(ob_high),
                        "ob_bottom": _safe(ob_low),
                        "ob_date": _safe(dates[j]),
                        "volume_confirmed": bool(vol_ok),
                        "mitigated": False,
                        "bars_ago": n - 1 - j,
                    })
                break

    # Sort by recency (most recent first), limit to 5
    order_blocks.sort(key=lambda x: x["bars_ago"])
    return order_blocks[:5]


# ============================================================================
# 4. ICT Fair Value Gaps
# ============================================================================

def _detect_fair_value_gaps(
    df: pd.DataFrame,
    min_gap_atr_multiple: float = 0.3,
) -> list[dict[str, Any]]:
    """
    Detect Fair Value Gaps (3-candle imbalance pattern).

    Bullish FVG: Candle1.high < Candle3.low (gap between candle 1 and 3)
    Bearish FVG: Candle1.low > Candle3.high
    """
    if len(df) < 20:
        return []

    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)
    dates = df.index

    # ATR for minimum gap size filter
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1]))
    )
    atr_14 = pd.Series(tr).rolling(14).mean().values

    fvgs = []
    current_price = float(close[-1])

    for i in range(2, n):
        atr_val = atr_14[min(i - 1, len(atr_14) - 1)] if i - 1 < len(atr_14) else 0

        # Bullish FVG: candle1 high < candle3 low
        if low[i] > high[i - 2]:
            gap_size = float(low[i] - high[i - 2])
            if atr_val and gap_size < min_gap_atr_multiple * atr_val:
                continue

            fvg_top = float(low[i])
            fvg_bottom = float(high[i - 2])

            # Check if mitigated (price returned to fill the gap)
            mitigated = False
            for k in range(i + 1, n):
                if low[k] <= fvg_bottom:
                    mitigated = True
                    break

            if not mitigated and fvg_bottom < current_price:
                fvgs.append({
                    "direction": "bullish",
                    "fvg_top": _safe(fvg_top),
                    "fvg_bottom": _safe(fvg_bottom),
                    "fvg_midpoint": _safe((fvg_top + fvg_bottom) / 2),
                    "gap_size": _safe(gap_size),
                    "date": _safe(dates[i - 1]),
                    "mitigated": False,
                    "bars_ago": n - 1 - i,
                    "distance_pct": _safe((current_price - fvg_top) / current_price * 100),
                })

        # Bearish FVG: candle1 low > candle3 high
        if high[i] < low[i - 2]:
            gap_size = float(low[i - 2] - high[i])
            if atr_val and gap_size < min_gap_atr_multiple * atr_val:
                continue

            fvg_top = float(low[i - 2])
            fvg_bottom = float(high[i])

            mitigated = False
            for k in range(i + 1, n):
                if high[k] >= fvg_top:
                    mitigated = True
                    break

            if not mitigated and fvg_top > current_price:
                fvgs.append({
                    "direction": "bearish",
                    "fvg_top": _safe(fvg_top),
                    "fvg_bottom": _safe(fvg_bottom),
                    "fvg_midpoint": _safe((fvg_top + fvg_bottom) / 2),
                    "gap_size": _safe(gap_size),
                    "date": _safe(dates[i - 1]),
                    "mitigated": False,
                    "bars_ago": n - 1 - i,
                    "distance_pct": _safe((fvg_bottom - current_price) / current_price * 100),
                })

    # Most recent first, limit to 5
    fvgs.sort(key=lambda x: x["bars_ago"])
    return fvgs[:5]


# ============================================================================
# 5. ICT Liquidity Pools
# ============================================================================

def _detect_liquidity_pools(
    df: pd.DataFrame,
    swing_length: int = 10,
    tolerance_pct: float = 0.001,
    min_touches: int = 2,
) -> list[dict[str, Any]]:
    """
    Detect liquidity pools: clusters of equal highs/lows where stop-losses
    accumulate. Market makers engineer pullbacks to sweep these pools.
    """
    if len(df) < 50:
        return []

    swings = _find_swing_points(df, swing_length)
    close = df["Close"].values
    current_price = float(close[-1])
    n = len(df)
    pools = []

    # Group swing highs that are at similar prices (equal highs)
    swing_highs = [s for s in swings if s["type"] == "high"]
    swing_lows = [s for s in swings if s["type"] == "low"]

    def _find_clusters(points: list[dict], point_type: str) -> list[dict]:
        """Find clusters of swing points at similar prices."""
        if len(points) < min_touches:
            return []

        clusters = []
        used = set()

        for i, p1 in enumerate(points):
            if i in used:
                continue
            cluster = [p1]
            used.add(i)

            for j, p2 in enumerate(points):
                if j in used:
                    continue
                if abs(p1["price"] - p2["price"]) / p1["price"] <= tolerance_pct:
                    cluster.append(p2)
                    used.add(j)

            if len(cluster) >= min_touches:
                avg_price = np.mean([c["price"] for c in cluster])
                most_recent_idx = max(c["index"] for c in cluster)

                # Check if swept (price pierced through and reversed)
                swept = False
                if point_type == "high":
                    for k in range(most_recent_idx + 1, n):
                        if close[k] > avg_price * (1 + tolerance_pct):
                            swept = True
                            break
                else:
                    for k in range(most_recent_idx + 1, n):
                        if close[k] < avg_price * (1 - tolerance_pct):
                            swept = True
                            break

                if not swept:
                    liq_type = "buy_side" if point_type == "high" else "sell_side"
                    clusters.append({
                        "type": liq_type,
                        "level": _safe(avg_price),
                        "touches": len(cluster),
                        "most_recent_bars_ago": n - 1 - most_recent_idx,
                        "swept": False,
                        "distance_pct": _safe((avg_price - current_price) / current_price * 100),
                        "explanation": (
                            f"{'Buy-side' if liq_type == 'buy_side' else 'Sell-side'} liquidity: "
                            f"{len(cluster)} equal {'highs' if point_type == 'high' else 'lows'} "
                            f"at ~${avg_price:.2f}. Stop-losses clustered here — "
                            f"expect {'sweep above' if liq_type == 'buy_side' else 'sweep below'} "
                            f"before reversal."
                        ),
                    })

        return clusters

    pools.extend(_find_clusters(swing_highs, "high"))
    pools.extend(_find_clusters(swing_lows, "low"))

    # Sort by distance from current price (closest first)
    pools.sort(key=lambda x: abs(x["distance_pct"]))
    return pools[:6]


# ============================================================================
# 6. Anchored VWAP
# ============================================================================

def _calculate_anchored_vwaps(
    df: pd.DataFrame,
    ticker: str,
) -> list[dict[str, Any]]:
    """
    Calculate Anchored VWAPs from significant events:
    - Earnings dates
    - Large gap days (>3%)
    - Swing lows/highs
    - High-volume breakout candles
    """
    if len(df) < 20:
        return []

    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    close = df["Close"].values
    volume = df["Volume"].values
    current_price = float(close[-1])
    dates = df.index
    n = len(df)
    avwaps = []

    def _calc_avwap(anchor_idx: int) -> float | None:
        """Calculate AVWAP from anchor index to present."""
        if anchor_idx >= n:
            return None
        tp_slice = typical_price.iloc[anchor_idx:]
        vol_slice = df["Volume"].iloc[anchor_idx:]
        cumtpv = (tp_slice * vol_slice).cumsum()
        cumvol = vol_slice.cumsum()
        avwap_series = cumtpv / cumvol
        return float(avwap_series.iloc[-1]) if len(avwap_series) > 0 else None

    # 1. Earnings dates
    try:
        tick = yf.Ticker(ticker)
        earnings_dates = tick.get_earnings_dates(limit=8)
        if earnings_dates is not None and len(earnings_dates) > 0:
            for ed in earnings_dates.index:
                ed_ts = pd.Timestamp(ed).tz_localize(None)
                # Find nearest trading day
                mask = dates >= ed_ts
                if mask.any():
                    anchor_idx = mask.values.argmax()
                    if anchor_idx < n - 5:
                        val = _calc_avwap(anchor_idx)
                        if val:
                            avwaps.append({
                                "anchor": "earnings",
                                "anchor_date": _safe(dates[anchor_idx]),
                                "avwap_value": _safe(val),
                                "distance_pct": _safe((current_price - val) / val * 100),
                            })
    except Exception:
        pass

    # 2. Large gap days (>3%)
    pct_change = pd.Series(close).pct_change().values
    for i in range(1, n):
        if abs(pct_change[i]) > 0.03:  # >3% gap
            val = _calc_avwap(i)
            if val:
                direction = "up" if pct_change[i] > 0 else "down"
                avwaps.append({
                    "anchor": f"gap_{direction}",
                    "anchor_date": _safe(dates[i]),
                    "avwap_value": _safe(val),
                    "distance_pct": _safe((current_price - val) / val * 100),
                    "gap_pct": _safe(pct_change[i] * 100),
                })

    # 3. Swing lows (last 3)
    swings = _find_swing_points(df, swing_length=10)
    swing_lows = [s for s in swings if s["type"] == "low"]
    for sl in swing_lows[-3:]:
        val = _calc_avwap(sl["index"])
        if val:
            avwaps.append({
                "anchor": "swing_low",
                "anchor_date": _safe(dates[sl["index"]]),
                "avwap_value": _safe(val),
                "distance_pct": _safe((current_price - val) / val * 100),
            })

    # 4. Highest volume day in last 60 bars
    recent_vol = volume[-60:]
    if len(recent_vol) > 0:
        max_vol_idx = n - 60 + np.argmax(recent_vol)
        val = _calc_avwap(max_vol_idx)
        if val:
            avwaps.append({
                "anchor": "volume_spike",
                "anchor_date": _safe(dates[max_vol_idx]),
                "avwap_value": _safe(val),
                "distance_pct": _safe((current_price - val) / val * 100),
            })

    # Sort by distance from current price
    avwaps.sort(key=lambda x: abs(x.get("distance_pct", 999)))
    return avwaps[:6]


# ============================================================================
# 7. Ornstein-Uhlenbeck Mean Reversion Half-Life
# ============================================================================

def _calculate_ou_half_life(df: pd.DataFrame) -> dict[str, Any]:
    """
    Estimate stock-specific mean reversion half-life via OLS on the
    Ornstein-Uhlenbeck process.

    Half-life tells HOW LONG pullbacks take to resolve.
    Short half-life = quick snaps back. Long half-life = extended pullbacks.
    """
    try:
        import statsmodels.api as sm

        close = df["Close"].values
        if len(close) < 60:
            return {"error": "Need 60+ bars for half-life estimation"}

        # Spread = deviation from 20-day moving average
        ma = pd.Series(close).rolling(20).mean().values
        spread = close - ma

        # Remove NaN from rolling
        valid = ~np.isnan(spread)
        spread = spread[valid]

        if len(spread) < 40:
            return {"error": "Insufficient valid data after MA calculation"}

        spread_lag = spread[:-1]
        spread_diff = spread[1:] - spread[:-1]

        # OLS: spread_diff = alpha + beta * spread_lag
        X = sm.add_constant(spread_lag)
        model = sm.OLS(spread_diff, X)
        res = model.fit()

        beta = res.params[1]

        if beta >= 0:
            return {
                "half_life_days": None,
                "interpretation": "NOT_MEAN_REVERTING",
                "explanation": "Stock is trending, not mean-reverting. Pullback depth is unpredictable — use trend-following entries instead.",
                "r_squared": _safe(res.rsquared),
            }

        half_life = -math.log(2) / beta

        if half_life < 5:
            interpretation = "FAST_REVERTER"
            explanation = f"Pullbacks resolve quickly (~{half_life:.0f} days). Use shallow entries near EMA10/EMA8. Stock snaps back fast."
        elif half_life < 15:
            interpretation = "MODERATE_REVERTER"
            explanation = f"Pullbacks take ~{half_life:.0f} days to resolve. EMA21/EMA50 entries work well. Standard swing timeframe."
        elif half_life < 30:
            interpretation = "SLOW_REVERTER"
            explanation = f"Extended pullbacks (~{half_life:.0f} days). Deeper entries near EMA50/SMA200 are appropriate. Be patient."
        else:
            interpretation = "VERY_SLOW"
            explanation = f"Very extended mean reversion (~{half_life:.0f} days). This stock trends more than it reverts. Consider breakout entries."

        # Current z-score (how far from mean right now)
        current_spread = spread[-1]
        spread_std = np.std(spread)
        z_score = current_spread / spread_std if spread_std > 0 else 0

        return {
            "half_life_days": _safe(half_life),
            "interpretation": interpretation,
            "explanation": explanation,
            "theta": _safe(-beta),
            "r_squared": _safe(res.rsquared),
            "current_z_score": _safe(z_score),
            "z_interpretation": (
                "OVERSOLD (extended pullback)" if z_score < -1.5
                else "SLIGHTLY_BELOW_MEAN" if z_score < -0.5
                else "AT_MEAN" if abs(z_score) <= 0.5
                else "SLIGHTLY_ABOVE_MEAN" if z_score < 1.5
                else "OVERBOUGHT (extended rally)"
            ),
        }
    except Exception as e:
        logger.error(f"OU half-life calculation failed: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# 8. Keltner Channel
# ============================================================================

def _calculate_keltner(
    df: pd.DataFrame,
    ema_period: int = 20,
    atr_multiplier: float = 2.0,
) -> dict[str, Any]:
    """
    Calculate Keltner Channel levels as pullback bands.

    Middle = EMA20, Upper/Lower = EMA ± multiplier * ATR
    ~77% bounce rate on SPY (QuantifiedStrategies).
    """
    if len(df) < ema_period + 14:
        return {"error": "Insufficient data for Keltner Channel"}

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ema = close.ewm(span=ema_period, adjust=False).mean()

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    upper = ema + atr_multiplier * atr
    middle = ema
    lower = ema - atr_multiplier * atr

    current_price = float(close.iloc[-1])

    return {
        "upper": _safe(float(upper.iloc[-1])),
        "middle": _safe(float(middle.iloc[-1])),
        "lower": _safe(float(lower.iloc[-1])),
        "atr": _safe(float(atr.iloc[-1])),
        "price_position": (
            "ABOVE_UPPER" if current_price > float(upper.iloc[-1])
            else "UPPER_HALF" if current_price > float(middle.iloc[-1])
            else "LOWER_HALF" if current_price > float(lower.iloc[-1])
            else "BELOW_LOWER"
        ),
        "middle_distance_pct": _safe((current_price - float(middle.iloc[-1])) / float(middle.iloc[-1]) * 100),
        "lower_distance_pct": _safe((current_price - float(lower.iloc[-1])) / float(lower.iloc[-1]) * 100),
    }


# ============================================================================
# 9. Regime-Dependent Pullback Depth
# ============================================================================

def _classify_trend_regime(df: pd.DataFrame) -> dict[str, Any]:
    """
    Classify current trend regime to determine expected pullback depth.

    Uses ADX + ATR percentile + body-to-range ratio.
    """
    if len(df) < 60:
        return {"regime": "UNKNOWN", "expected_depth": "38.2%-50%"}

    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    n = len(df)

    # ADX calculation (simplified)
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1]))
    )
    atr_14 = pd.Series(tr).rolling(14).mean()

    # +DM / -DM
    plus_dm = np.where(
        (high[1:] - high[:-1]) > (low[:-1] - low[1:]),
        np.maximum(high[1:] - high[:-1], 0),
        0,
    )
    minus_dm = np.where(
        (low[:-1] - low[1:]) > (high[1:] - high[:-1]),
        np.maximum(low[:-1] - low[1:], 0),
        0,
    )

    plus_di = pd.Series(plus_dm).rolling(14).mean() / atr_14 * 100
    minus_di = pd.Series(minus_dm).rolling(14).mean() / atr_14 * 100
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    adx = dx.rolling(14).mean()

    current_adx = float(adx.iloc[-1]) if not np.isnan(adx.iloc[-1]) else 20

    # Volatility percentile (ATR vs recent history)
    atr_pctile = float((atr_14 < atr_14.iloc[-1]).mean() * 100) if len(atr_14) > 20 else 50

    # Trend direction
    ema50 = pd.Series(close).ewm(span=50, adjust=False).mean()
    trend_dir = "BULLISH" if close[-1] > float(ema50.iloc[-1]) else "BEARISH"

    # Regime classification
    if current_adx > 35:
        regime = "STRONG_TREND"
        expected_depth = "23.6%-38.2%"
        explanation = f"Strong trend (ADX={current_adx:.0f}). Shallow pullbacks expected — enter near EMA8-EMA10."
    elif current_adx > 25:
        regime = "MODERATE_TREND"
        expected_depth = "38.2%-50%"
        explanation = f"Moderate trend (ADX={current_adx:.0f}). Standard pullbacks — enter near EMA21."
    elif current_adx > 20:
        regime = "WEAK_TREND"
        expected_depth = "50%-61.8%"
        explanation = f"Weak trend (ADX={current_adx:.0f}). Deep pullbacks likely — wait for EMA50 or Fib 61.8%."
    else:
        regime = "RANGE"
        expected_depth = "Full range"
        explanation = f"Ranging market (ADX={current_adx:.0f}). No trending pullbacks — trade range boundaries."

    return {
        "regime": regime,
        "trend_direction": trend_dir,
        "adx": _safe(current_adx),
        "atr_percentile": _safe(atr_pctile),
        "expected_pullback_depth": expected_depth,
        "explanation": explanation,
    }


# ============================================================================
# Composite Ranking Engine
# ============================================================================

def _rank_pullback_levels(
    current_price: float,
    ma_bounces: list[dict],
    volume_profile: dict,
    order_blocks: list[dict],
    fvgs: list[dict],
    liquidity_pools: list[dict],
    avwaps: list[dict],
    keltner: dict,
    regime: dict,
) -> list[dict[str, Any]]:
    """
    Rank all candidate pullback levels by confluence score.
    Each technique that agrees on a level adds points.
    Levels within 0.5% of each other are merged.
    """
    # Collect all candidate levels with their sources
    candidates = []  # list of (price, source_name, base_score, detail)

    # MA bounce levels — include if below OR within 3% above current price
    # (stock may be AT or just below an MA during a pullback)
    for ma in ma_bounces:
        if ma["current_value"]:
            dist = (ma["current_value"] - current_price) / current_price
            if dist < 0.03:  # Below price OR within 3% above
                score = ma["composite_score"] * 0.4  # Scale to 0-40 range
                candidates.append((
                    ma["current_value"],
                    f"{ma['level_name']} ({ma['bounce_rate']*100:.0f}% bounce, {ma['total_touches']} touches)",
                    min(score, 30),
                    ma,
                ))

    # Volume profile levels
    if "poc" in volume_profile and not volume_profile.get("error"):
        poc = volume_profile["poc"]
        if poc < current_price:
            candidates.append((poc, "VPOC (highest volume node)", 25, volume_profile))
        val = volume_profile.get("val")
        if val and val < current_price:
            candidates.append((val, "Value Area Low", 18, volume_profile))
        vah = volume_profile.get("vah")
        if vah and vah < current_price:
            candidates.append((vah, "Value Area High", 12, volume_profile))
        for hvn in volume_profile.get("hvns", []):
            if hvn["price"] < current_price:
                candidates.append((hvn["price"], f"HVN ({hvn['volume_pct']:.1f}% vol)", 15, hvn))

    # ICT Order Blocks
    for ob in order_blocks:
        if ob["direction"] == "bullish" and ob["ob_top"] < current_price:
            vol_bonus = 5 if ob["volume_confirmed"] else 0
            recency_bonus = max(0, 10 - ob["bars_ago"] / 10)
            score = 25 + vol_bonus + recency_bonus
            candidates.append((
                ob["ob_top"],
                f"ICT Bullish OB ({ob['ob_date']}, vol={'YES' if ob['volume_confirmed'] else 'NO'})",
                min(score, 35),
                ob,
            ))
        elif ob["direction"] == "bearish" and ob["ob_bottom"] > current_price:
            vol_bonus = 5 if ob["volume_confirmed"] else 0
            recency_bonus = max(0, 10 - ob["bars_ago"] / 10)
            score = 25 + vol_bonus + recency_bonus
            candidates.append((
                ob["ob_bottom"],
                f"ICT Bearish OB ({ob['ob_date']})",
                min(score, 35),
                ob,
            ))

    # ICT Fair Value Gaps
    for fvg in fvgs:
        if fvg["direction"] == "bullish" and fvg["fvg_top"] < current_price:
            candidates.append((
                fvg["fvg_midpoint"],
                f"ICT Bullish FVG ({fvg['date']}, gap ${fvg['gap_size']:.2f})",
                20,
                fvg,
            ))
        elif fvg["direction"] == "bearish" and fvg["fvg_bottom"] > current_price:
            candidates.append((
                fvg["fvg_midpoint"],
                f"ICT Bearish FVG ({fvg['date']})",
                20,
                fvg,
            ))

    # ICT Liquidity Pools
    for pool in liquidity_pools:
        candidates.append((
            pool["level"],
            f"ICT Liquidity Pool ({pool['touches']} equal {'highs' if pool['type'] == 'buy_side' else 'lows'})",
            15 + pool["touches"] * 3,
            pool,
        ))

    # Anchored VWAPs
    for av in avwaps:
        val = av["avwap_value"]
        if val < current_price:
            anchor_bonus = 10 if av["anchor"] == "earnings" else 5
            candidates.append((
                val,
                f"Anchored VWAP ({av['anchor']}, {av['anchor_date']})",
                15 + anchor_bonus,
                av,
            ))

    # Keltner levels
    if not keltner.get("error"):
        if keltner.get("middle") and keltner["middle"] < current_price:
            candidates.append((keltner["middle"], "Keltner Middle (EMA20)", 12, keltner))
        if keltner.get("lower") and keltner["lower"] < current_price:
            candidates.append((keltner["lower"], "Keltner Lower Band", 10, keltner))

    if not candidates:
        return []

    # Merge nearby levels (within 0.5% of each other)
    candidates.sort(key=lambda x: x[0])
    merged = []
    i = 0
    while i < len(candidates):
        group = [candidates[i]]
        j = i + 1
        while j < len(candidates):
            if abs(candidates[j][0] - candidates[i][0]) / candidates[i][0] <= 0.005:
                group.append(candidates[j])
                j += 1
            else:
                break

        # Merge group: average price, sum scores, collect all sources
        avg_price = np.mean([g[0] for g in group])
        total_score = sum(g[2] for g in group)
        sources = [g[1] for g in group]
        distance_pct = (current_price - avg_price) / current_price * 100

        merged.append({
            "price": _safe(avg_price),
            "confluence_score": _safe(min(total_score, 100)),
            "num_sources": len(group),
            "sources": sources,
            "distance_pct": _safe(distance_pct),
        })
        i = j

    # Sort by confluence score (highest first)
    merged.sort(key=lambda x: x["confluence_score"], reverse=True)

    # Assign rank and entry type
    for idx, level in enumerate(merged):
        level["rank"] = idx + 1
        if idx == 0:
            level["entry_type"] = "PRIMARY"
        elif idx == 1:
            level["entry_type"] = "SECONDARY"
        elif idx == 2:
            level["entry_type"] = "TERTIARY"
        else:
            level["entry_type"] = "BACKUP"

    return merged[:8]


# ============================================================================
# Narrative Generation
# ============================================================================

def _generate_narrative(
    ticker: str,
    ranked_levels: list[dict],
    ou_result: dict,
    regime: dict,
) -> str:
    """Generate human-readable pullback recommendation."""
    if not ranked_levels:
        return f"No clear pullback levels identified for {ticker}. Consider using limit orders at round numbers or waiting for new structure."

    primary = ranked_levels[0]
    parts = [
        f"{ticker}'s primary pullback level is ${primary['price']:.2f} "
        f"({primary['num_sources']}-way confluence, score {primary['confluence_score']:.0f}/100). "
        f"Sources: {', '.join(primary['sources'][:3])}."
    ]

    # Half-life context
    hl = ou_result.get("half_life_days")
    if hl and hl > 0:
        parts.append(
            f" Mean reversion half-life is {hl:.1f} days, "
            f"so expect pullback to resolve within ~{hl * 2:.0f} days."
        )

    # Regime context
    regime_str = regime.get("regime", "UNKNOWN")
    depth = regime.get("expected_pullback_depth", "unknown")
    parts.append(f" In the current {regime_str} regime, {depth} retracements are typical.")

    # Secondary level
    if len(ranked_levels) > 1:
        secondary = ranked_levels[1]
        parts.append(
            f" If ${primary['price']:.2f} fails, secondary entry at "
            f"${secondary['price']:.2f} ({', '.join(secondary['sources'][:2])})."
        )

    # Z-score alert
    z = ou_result.get("current_z_score", 0)
    if z and z < -1.5:
        parts.append(f" ALERT: Z-score is {z:.1f} — currently in extended pullback territory, entry may be imminent.")
    elif z and z > 1.5:
        parts.append(f" CAUTION: Z-score is {z:.1f} — currently overbought, wait for pullback to develop.")

    return "".join(parts)


# ============================================================================
# Main Implementation
# ============================================================================

def _analyze_pullback_personality_impl(
    ticker: str,
    period: str = "1y",
    lookback_days: int = 60,
) -> dict[str, Any]:
    """
    Full pullback personality analysis combining 9 institutional techniques.

    Learns which levels each stock historically respects and ranks them
    by confluence score.
    """
    try:
        df = _safe_download(ticker, period=period)
        if df is None or len(df) < 60:
            return {"error": f"Insufficient data for {ticker} (need 60+ bars)", "ticker": ticker}

        current_price = float(df["Close"].iloc[-1])

        # Run all 9 analyses
        ma_values = _calculate_ma_values(df)
        ma_bounces = _detect_ma_bounces(df, ma_values)
        volume_profile = _build_volume_profile(df, lookback_days=lookback_days)
        order_blocks = _detect_order_blocks(df)
        fvgs = _detect_fair_value_gaps(df)
        liquidity_pools = _detect_liquidity_pools(df)
        avwaps = _calculate_anchored_vwaps(df, ticker)
        ou_result = _calculate_ou_half_life(df)
        keltner = _calculate_keltner(df)
        regime = _classify_trend_regime(df)

        # Composite ranking
        ranked_levels = _rank_pullback_levels(
            current_price, ma_bounces, volume_profile,
            order_blocks, fvgs, liquidity_pools, avwaps,
            keltner, regime,
        )

        # Narrative
        recommendation = _generate_narrative(ticker, ranked_levels, ou_result, regime)

        return {
            "ticker": ticker,
            "current_price": _safe(current_price),
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "period_analyzed": period,

            # Composite result
            "ranked_levels": ranked_levels,
            "recommendation": recommendation,

            # Regime context
            "regime": regime,

            # Mean reversion personality
            "mean_reversion": ou_result,

            # Individual technique results
            "ma_bounce_rates": ma_bounces,
            "volume_profile": volume_profile,
            "ict": {
                "order_blocks": order_blocks,
                "fair_value_gaps": fvgs,
                "liquidity_pools": liquidity_pools,
            },
            "anchored_vwaps": avwaps,
            "keltner_channel": keltner,

            "methodology": (
                "9-technique confluence analysis: MA bounce rates, Volume Profile (VPOC/HVN), "
                "ICT Order Blocks, ICT Fair Value Gaps, ICT Liquidity Pools, Anchored VWAP, "
                "Ornstein-Uhlenbeck half-life, Keltner Channel, regime-dependent depth. "
                "Levels within 0.5% are merged. Score = sum of technique weights (max 100)."
            ),
        }

    except Exception as e:
        logger.error(f"Pullback personality analysis failed for {ticker}: {e}", exc_info=True)
        return {"error": str(e), "ticker": ticker}


# ============================================================================
# MCP Tool Registration
# ============================================================================

def register_tools(mcp):
    """Register pullback personality analysis tool with MCP server."""

    @mcp.tool()
    def analyze_pullback_personality(
        ticker: str,
        period: str = "1y",
        lookback_days: int = 60,
    ) -> dict[str, Any]:
        """
        Analyze a stock's pullback personality — which levels it historically
        respects and where the highest-probability entry zones are.

        Combines 9 institutional techniques into a ranked confluence score:
        1. Historical MA Bounce Rate (EMA8/10/21/50, SMA200)
        2. Volume Profile (VPOC, VAH, VAL, High Volume Nodes)
        3. ICT Order Blocks (institutional entry zones)
        4. ICT Fair Value Gaps (3-candle imbalance magnets)
        5. ICT Liquidity Pools (stop-hunt sweep targets)
        6. Anchored VWAP (from earnings, gaps, swing lows)
        7. Ornstein-Uhlenbeck Half-Life (mean reversion speed)
        8. Keltner Channel (ATR-based volatility bands)
        9. Regime-Dependent Depth (ADX-based pullback expectation)

        Instead of generic "wait for EMA20" advice, this tool learns each
        stock's unique pullback behavior from historical data.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            period: Historical data period (default "1y")
            lookback_days: Volume profile lookback (default 60)

        Returns:
            ranked_levels: Pullback levels ranked by confluence score (0-100)
            recommendation: Human-readable entry recommendation
            regime: Current trend regime and expected pullback depth
            mean_reversion: Stock-specific half-life and z-score
            ict: Order blocks, fair value gaps, liquidity pools
            volume_profile: VPOC, VAH, VAL, HVNs
            ma_bounce_rates: Historical bounce rate at each MA
            anchored_vwaps: Event-anchored VWAPs
            keltner_channel: ATR-based pullback bands
        """
        return _analyze_pullback_personality_impl(ticker, period, lookback_days)
