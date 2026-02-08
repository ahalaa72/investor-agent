"""
Bootstrap Tools Enhancement Module - IMPROVED VERSION v3
Fixes VWAP calculation to match TradingView behavior with proper daily reset
Uses Questrade as primary data source, yfinance as fallback

Key Fix: VWAP now properly resets daily for daily charts, matching TradingView exactly
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any
import warnings
import logging

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# Module-level cache for price history (5 minute TTL)
_price_history_cache: Dict[str, tuple] = {}
_cache_ttl_seconds = 300  # 5 minutes
_last_data_source: Dict[str, str] = {}  # Track last data source per ticker


def _get_data_source(ticker: str) -> str:
    """Get the last data source used for a ticker."""
    return _last_data_source.get(ticker, "UNKNOWN")


def _get_price_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """
    Get price history with Questrade as primary, yfinance as fallback.
    CACHED: Same ticker/period will return cached data for 5 minutes.
    """
    # Check cache first
    cache_key = f"{ticker}_{period}"
    if cache_key in _price_history_cache:
        df, timestamp, source = _price_history_cache[cache_key]
        age_seconds = (datetime.now() - timestamp).total_seconds()
        if age_seconds < _cache_ttl_seconds:
            logger.debug(f"💾 Price history cache HIT for {ticker} from {source} (age: {age_seconds:.1f}s)")
            _last_data_source[ticker] = source  # Track source from cache
            return df.copy()

    # Map period to window size for Questrade (trading days)
    period_windows = {
        '1d': 5, '5d': 10, '1mo': 30, '3mo': 70, '6mo': 140,
        '1y': 260, '2y': 520, '5y': 1300
    }
    window = period_windows.get(period, 70)

    # Try Questrade first - use the working get_questrade_candles pattern
    try:
        from .tools.questrade_api import get_questrade_candles_impl as get_questrade_candles

        candles_result = get_questrade_candles(ticker, "OneDay", window=window)

        if candles_result and candles_result.get('candles') and len(candles_result['candles']) >= 10:
            df = pd.DataFrame(candles_result['candles'])
            df = df.rename(columns={
                'start': 'Date', 'open': 'Open', 'high': 'High',
                'low': 'Low', 'close': 'Close', 'volume': 'Volume'
            })
            # Keep VWAP if available
            if 'VWAP' in df.columns:
                df = df.rename(columns={'VWAP': 'vwap'})

            # Convert with utc=True to handle timezone-aware strings properly
            df['Date'] = pd.to_datetime(df['Date'], utc=True)
            df.set_index('Date', inplace=True)
            # Remove timezone info for consistent downstream processing
            df.index = df.index.tz_convert(None)

            logger.info(f"✅ Using QUESTRADE data for {ticker} ({len(df)} bars)")
            # Cache with source info and track last source
            _price_history_cache[cache_key] = (df.copy(), datetime.now(), "QUESTRADE")
            _last_data_source[ticker] = "QUESTRADE"
            return df

    except Exception as e:
        logger.warning(f"⚠️ Questrade failed for {ticker}: {e}")

    # Fallback to yfinance
    logger.warning(f"⚠️ FALLBACK: Using yfinance for {ticker} (Questrade unavailable)")
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)

    # Normalize timezone-aware index to avoid pandas conversion issues
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    # Cache before returning with source info (3-tuple to match cache retrieval)
    if not df.empty:
        _price_history_cache[cache_key] = (df.copy(), datetime.now(), "YFINANCE")
        _last_data_source[ticker] = "YFINANCE"

    return df


# ============================================================================
# DALIO ECONOMIC MACHINE - Helper Functions
# Based on Ray Dalio's principle: Price = Total Spending / Quantity Sold
# ============================================================================

def _interpret_dalio_ratio(ratio: float) -> str:
    """Interpret the Dalio Ratio value"""
    if ratio > 1.05:
        return "STRONG_BULLISH"
    elif ratio > 1.02:
        return "BULLISH"
    elif ratio > 0.98:
        return "NEUTRAL"
    elif ratio > 0.95:
        return "BEARISH"
    else:
        return "STRONG_BEARISH"


def _classify_dv_momentum(momentum_pct: float) -> str:
    """Classify dollar volume momentum"""
    if momentum_pct > 100:
        return "EXTREME_INFLOW"
    elif momentum_pct > 50:
        return "STRONG_INFLOW"
    elif momentum_pct > 20:
        return "INFLOW"
    elif momentum_pct > -20:
        return "NEUTRAL"
    elif momentum_pct > -50:
        return "OUTFLOW"
    else:
        return "STRONG_OUTFLOW"


def _interpret_spending_efficiency(efficiency: float) -> str:
    """Interpret spending efficiency ratio"""
    if abs(efficiency) > 1.5:
        return "LOW_LIQUIDITY"
    elif abs(efficiency) < 0.3:
        return "VERY_HIGH_ABSORPTION"
    elif abs(efficiency) < 0.5:
        return "HIGH_ABSORPTION"
    elif abs(efficiency) <= 1.2:
        return "NORMAL"
    else:
        return "ELEVATED"


def _derive_efficiency_implication(efficiency: float, cdf: float) -> str:
    """Derive implication from spending efficiency and dollar flow"""
    if abs(efficiency) < 0.5 and cdf > 0:
        return "ACCUMULATION"
    elif abs(efficiency) < 0.5 and cdf < 0:
        return "DISTRIBUTION"
    elif abs(efficiency) > 1.5:
        return "BREAKOUT_OR_BREAKDOWN"
    else:
        return "NORMAL_TRADING"


def _calculate_dollar_volume_profile(df: pd.DataFrame, bins: int = 20) -> dict:
    """
    Calculate dollar volume profile (spending at each price level).
    This shows where the MOST CAPITAL was deployed, not just shares.
    """
    try:
        price_min = df['Low'].min()
        price_max = df['High'].max()
        price_range = price_max - price_min

        if price_range <= 0:
            return {"error": "Insufficient price range"}

        bin_size = price_range / bins

        # Calculate dollar volume for each bar
        df_calc = df.copy()
        df_calc['Typical_Price'] = (df_calc['High'] + df_calc['Low'] + df_calc['Close']) / 3
        df_calc['Dollar_Volume'] = df_calc['Typical_Price'] * df_calc['Volume']

        profile = {}
        for i in range(bins):
            price_low = price_min + (i * bin_size)
            price_high = price_low + bin_size
            price_mid = (price_low + price_high) / 2

            # Estimate dollar volume at this level (bars that touched this price)
            mask = (df_calc['Low'] <= price_mid) & (df_calc['High'] >= price_mid)
            if mask.sum() > 0:
                dv_at_level = df_calc.loc[mask, 'Dollar_Volume'].sum() / mask.sum()
            else:
                dv_at_level = 0

            profile[round(price_mid, 2)] = int(dv_at_level)

        # Find POC (Point of Control) - price with highest dollar volume
        if not profile:
            return {"error": "Could not calculate profile"}

        poc_price = max(profile, key=profile.get)

        # Calculate Value Area (70% of dollar volume)
        total_dv = sum(profile.values())
        sorted_levels = sorted(profile.items(), key=lambda x: x[1], reverse=True)

        cumulative = 0
        value_area_prices = []
        for price, dv in sorted_levels:
            cumulative += dv
            value_area_prices.append(price)
            if cumulative >= total_dv * 0.70:
                break

        va_high = max(value_area_prices) if value_area_prices else price_max
        va_low = min(value_area_prices) if value_area_prices else price_min

        # Identify high/low volume nodes
        avg_dv = total_dv / bins if bins > 0 else 0
        nodes = []
        for price, dv in sorted(profile.items()):
            if dv > avg_dv * 1.5:
                nodes.append({"price": price, "dollar_volume": dv, "type": "HIGH_VOLUME"})
            elif dv < avg_dv * 0.5 and dv > 0:
                nodes.append({"price": price, "dollar_volume": dv, "type": "LOW_VOLUME"})

        current_price = df['Close'].iloc[-1]

        return {
            "point_of_control": round(poc_price, 2),
            "value_area_high": round(va_high, 2),
            "value_area_low": round(va_low, 2),
            "current_vs_poc": "ABOVE" if current_price > poc_price else "BELOW" if current_price < poc_price else "AT",
            "total_dollar_volume": int(total_dv),
            "dollar_nodes": nodes[:10]  # Top 10 notable nodes
        }
    except Exception as e:
        return {"error": str(e)}


def _detect_institutional_activity(
    dv_momentum: float,
    spending_efficiency: float,
    cdf_20d: float,
    avg_dv_20d: float,
    high_dv_days: int
) -> dict:
    """
    Detect institutional activity based on dollar volume patterns.
    """
    signals = []
    confidence = 0

    # Check 1: Dollar volume significantly above average
    if dv_momentum > 50:
        signals.append(f"Dollar volume {dv_momentum:.0f}% above 20d avg")
        confidence += 30
    elif dv_momentum > 20:
        signals.append(f"Dollar volume {dv_momentum:.0f}% above 20d avg")
        confidence += 15

    # Check 2: High absorption (big money, small moves)
    if abs(spending_efficiency) < 0.5:
        signals.append("High absorption - large capital, small price moves")
        confidence += 25
    elif abs(spending_efficiency) < 0.8:
        signals.append("Moderate absorption detected")
        confidence += 10

    # Check 3: Consistent directional flow
    if avg_dv_20d > 0 and abs(cdf_20d) > avg_dv_20d * 0.3:
        signals.append("Strong directional dollar commitment")
        confidence += 25
    elif avg_dv_20d > 0 and abs(cdf_20d) > avg_dv_20d * 0.15:
        signals.append("Moderate directional dollar commitment")
        confidence += 10

    # Check 4: Multiple high-dollar-volume days
    if high_dv_days >= 5:
        signals.append(f"{high_dv_days} high-dollar-volume days in 20d")
        confidence += 20
    elif high_dv_days >= 3:
        signals.append(f"{high_dv_days} high-dollar-volume days in 20d")
        confidence += 10

    # Determine confidence level
    if confidence >= 75:
        conf_level = "HIGH"
    elif confidence >= 50:
        conf_level = "MEDIUM"
    else:
        conf_level = "LOW"

    return {
        "detected": confidence >= 50,
        "confidence": conf_level,
        "confidence_score": confidence,
        "signals": signals,
        "likely_direction": "ACCUMULATION" if cdf_20d > 0 else "DISTRIBUTION",
        "estimated_commitment": abs(int(cdf_20d))
    }


def _assess_trend_sustainability(
    dalio_ratio: float,
    dv_momentum: float,
    spending_efficiency: float,
    cdf_20d: float,
    current_price: float,
    poc_price: float
) -> dict:
    """
    Assess trend sustainability using Dalio metrics.
    Returns score 0-100 and grade A-F.
    """
    score = 0
    factors = {}
    risk_factors = []

    # Factor 1: Dalio Ratio trend (25 points)
    if dalio_ratio > 1.05:
        score += 25
        factors["dalio_ratio"] = "STRONG_POSITIVE"
    elif dalio_ratio > 1.02:
        score += 20
        factors["dalio_ratio"] = "POSITIVE"
    elif dalio_ratio > 0.98:
        score += 12
        factors["dalio_ratio"] = "NEUTRAL"
    elif dalio_ratio > 0.95:
        score += 5
        factors["dalio_ratio"] = "NEGATIVE"
        risk_factors.append("Dalio ratio bearish - buyers paying less")
    else:
        factors["dalio_ratio"] = "STRONG_NEGATIVE"
        risk_factors.append("Dalio ratio strongly bearish")

    # Factor 2: Dollar volume momentum (25 points)
    if dv_momentum > 50:
        score += 25
        factors["dollar_volume_trend"] = "STRONG_POSITIVE"
    elif dv_momentum > 20:
        score += 20
        factors["dollar_volume_trend"] = "POSITIVE"
    elif dv_momentum > -20:
        score += 12
        factors["dollar_volume_trend"] = "NEUTRAL"
    elif dv_momentum > -50:
        score += 5
        factors["dollar_volume_trend"] = "NEGATIVE"
        risk_factors.append("Dollar volume declining")
    else:
        factors["dollar_volume_trend"] = "STRONG_NEGATIVE"
        risk_factors.append("Dollar volume strongly declining")

    # Factor 3: Spending efficiency (25 points)
    abs_eff = abs(spending_efficiency) if spending_efficiency != 0 else 1.0
    if 0.3 <= abs_eff <= 1.2:
        score += 25
        factors["efficiency_trend"] = "STABLE"
    elif abs_eff < 0.3:
        score += 20
        factors["efficiency_trend"] = "HIGH_ABSORPTION"
    elif abs_eff <= 1.5:
        score += 15
        factors["efficiency_trend"] = "SLIGHTLY_ELEVATED"
    else:
        score += 5
        factors["efficiency_trend"] = "UNSTABLE"
        risk_factors.append("Low liquidity - moves may not sustain")

    # Factor 4: Price vs POC (25 points)
    if poc_price > 0:
        price_vs_poc = ((current_price - poc_price) / poc_price) * 100
    else:
        price_vs_poc = 0

    if -5 <= price_vs_poc <= 10:
        score += 25
        factors["price_vs_poc"] = "FAVORABLE"
    elif -10 <= price_vs_poc <= 15:
        score += 15
        factors["price_vs_poc"] = "ACCEPTABLE"
    else:
        score += 5
        factors["price_vs_poc"] = "EXTENDED"
        if price_vs_poc > 15:
            risk_factors.append(f"Price {price_vs_poc:.1f}% above POC - extended")
        else:
            risk_factors.append(f"Price {abs(price_vs_poc):.1f}% below POC")

    # Determine grade
    if score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B+"
    elif score >= 60:
        grade = "B"
    elif score >= 50:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    # Determine assessment
    if score >= 60:
        assessment = "SUSTAINABLE"
    elif score >= 40:
        assessment = "AT_RISK"
    else:
        assessment = "UNSUSTAINABLE"

    return {
        "score": score,
        "grade": grade,
        "assessment": assessment,
        "factors": factors,
        "risk_factors": risk_factors
    }


def analyze_volume(ticker: str, period: str = "3mo", vwap_mode: str = "session") -> dict:
    """
    Comprehensive volume analysis - THE most important confirmation indicator.

    NOW INCLUDES: Ray Dalio's Economic Machine metrics for institutional-grade analysis.

    Args:
        ticker: Stock ticker symbol
        period: Historical period (1mo, 3mo, 6mo, 1y, 2y)
        vwap_mode:
            - "session": Each day's VWAP (TradingView default) - calculates VWAP per trading session
            - "rolling": 20-day rolling VWAP
            - "anchored": VWAP from start of period (what TradingView calls "Anchored VWAP")

    Returns:
        Dictionary containing:
        - Standard volume metrics (VWAP, OBV, MFI, CVD, Volume Profile)
        - Multi-VWAP analysis (rolling, anchored positions)
        - Liquidity zones (HVN/LVN analysis)
        - **NEW: dalio_metrics** - Ray Dalio Economic Machine analysis:
            - dalio_ratio: Current VWAP / Prior VWAP (>1 = bullish)
            - dollar_volume: Total spending analysis
            - spending_efficiency: Price change vs dollar volume change
            - cumulative_dollar_flow: Net directional capital
            - dollar_profile: Dollar-weighted volume profile
            - institutional_activity: Smart money detection
            - trend_sustainability: Score 0-100 with grade
            - gate_2_contribution: For 4-gate validation integration
    """
    try:
        # Use Questrade-first approach
        df = _get_price_history(ticker, period)

        if df.empty:
            return {"error": f"No data available for {ticker}"}
        
        # Calculate Typical Price = (High + Low + Close) / 3
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        
        # Calculate different VWAP modes
        if vwap_mode == "session":
            # TradingView default: Each bar on a daily chart represents one session's VWAP
            # Since we have daily data, each row IS the session's VWAP
            # For daily bars, VWAP = Typical Price (each bar is the full session)
            df['VWAP'] = df['Typical_Price']
            current_vwap = df['VWAP'].iloc[-1]
            vwap_type = "Session VWAP (Daily)"
            vwap_note = "For daily charts, each bar's typical price IS that day's VWAP. For true intraday VWAP matching TradingView's live calculation, use analyze_volume_intraday() with 15-min data."
            
        elif vwap_mode == "rolling":
            # Rolling 20-day VWAP (commonly used for swing trading)
            df['PV'] = df['Typical_Price'] * df['Volume']
            df['VWAP'] = (
                df['PV'].rolling(window=20).sum() / 
                df['Volume'].rolling(window=20).sum()
            )
            current_vwap = df['VWAP'].iloc[-1]
            vwap_type = "20-Day Rolling VWAP"
            vwap_note = "Rolling VWAP useful for identifying intermediate-term support/resistance"
            
        else:  # anchored
            # Anchored VWAP from start of period (what some call "cumulative")
            # This is useful for longer-term position trades
            df['PV'] = df['Typical_Price'] * df['Volume']
            df['VWAP'] = df['PV'].cumsum() / df['Volume'].cumsum()
            current_vwap = df['VWAP'].iloc[-1]
            vwap_type = f"Anchored VWAP (from start of {period})"
            vwap_note = "Anchored VWAP from period start - useful for position trading"
        
        current_price = df['Close'].iloc[-1]
        vwap_distance = ((current_price - current_vwap) / current_vwap) * 100
        
        # Volume Profile - Find Point of Control (POC)
        price_bins = 20
        df['Price_Bin'] = pd.cut(df['Close'], bins=price_bins)
        volume_profile = df.groupby('Price_Bin')['Volume'].sum().sort_values(ascending=False)
        poc_bin = volume_profile.index[0]
        poc_price = (poc_bin.left + poc_bin.right) / 2
        
        # Value Area (70% of volume)
        total_volume = df['Volume'].sum()
        cumsum_volume = volume_profile.cumsum()
        value_area_mask = cumsum_volume <= total_volume * 0.70
        value_area_high = volume_profile[value_area_mask].index[0].right if value_area_mask.any() else df['High'].max()
        value_area_low = volume_profile[value_area_mask].index[-1].left if value_area_mask.any() else df['Low'].min()
        
        # Relative Volume
        avg_volume = df['Volume'].tail(20).mean()
        current_volume = df['Volume'].iloc[-1]
        relative_volume = current_volume / avg_volume if avg_volume > 0 else 0
        
        # OBV (On-Balance Volume)
        df['OBV_Change'] = 0
        df.loc[df['Close'] > df['Close'].shift(1), 'OBV_Change'] = df['Volume']
        df.loc[df['Close'] < df['Close'].shift(1), 'OBV_Change'] = -df['Volume']
        df['OBV'] = df['OBV_Change'].cumsum()
        obv_current = df['OBV'].iloc[-1]
        obv_20_ago = df['OBV'].iloc[-20] if len(df) >= 20 else df['OBV'].iloc[0]
        obv_trend = "Accumulation" if obv_current > obv_20_ago else "Distribution"
        
        # MFI (Money Flow Index) - RSI of money flow
        typical_price = df['Typical_Price']
        money_flow = typical_price * df['Volume']
        
        # Positive and negative money flow
        df['Price_Change'] = typical_price.diff()
        positive_flow = money_flow.where(df['Price_Change'] > 0, 0).rolling(14).sum()
        negative_flow = money_flow.where(df['Price_Change'] < 0, 0).rolling(14).sum()
        
        # Avoid division by zero
        negative_flow = negative_flow.replace(0, 0.001)
        money_ratio = positive_flow / negative_flow
        mfi = 100 - (100 / (1 + money_ratio))
        current_mfi = mfi.iloc[-1]
        
        # MFI Signal
        if current_mfi > 80:
            mfi_signal = "Overbought - Possible Reversal"
        elif current_mfi < 20:
            mfi_signal = "Oversold - Possible Reversal"
        else:
            mfi_signal = "Neutral"
        
        # Accumulation/Distribution Line
        df['CLV'] = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'])
        df['CLV'] = df['CLV'].fillna(0)  # Handle days where High = Low
        df['AD_Line'] = (df['CLV'] * df['Volume']).cumsum()
        ad_current = df['AD_Line'].iloc[-1]
        ad_20_ago = df['AD_Line'].iloc[-20] if len(df) >= 20 else df['AD_Line'].iloc[0]
        ad_trend = "Accumulation" if ad_current > ad_20_ago else "Distribution"
        
        # Price-Volume Confirmation
        recent_price_change = ((df['Close'].iloc[-1] - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100 if len(df) >= 5 else 0
        if recent_price_change > 2 and relative_volume > 1.5:
            confirmation = "STRONG BULLISH - Price surge confirmed by high volume"
        elif recent_price_change > 2 and relative_volume < 1.0:
            confirmation = "WEAK BULLISH - Price surge NOT confirmed (low volume warning)"
        elif recent_price_change < -2 and relative_volume > 1.5:
            confirmation = "STRONG BEARISH - Decline confirmed by high volume"
        elif recent_price_change < -2 and relative_volume < 1.0:
            confirmation = "WEAK BEARISH - Decline on low volume (possible reversal)"
        else:
            confirmation = "NEUTRAL - No significant price/volume divergence"
        
        # Volume surges and dry-ups
        volume_2x = df[df['Volume'] > avg_volume * 2].tail(5)
        # Ensure index is DatetimeIndex before calling strftime
        if len(volume_2x) > 0:
            if isinstance(volume_2x.index, pd.DatetimeIndex):
                volume_surge_dates = volume_2x.index.strftime('%Y-%m-%d').tolist()
            else:
                # Convert to DatetimeIndex if needed
                volume_surge_dates = pd.to_datetime(volume_2x.index).strftime('%Y-%m-%d').tolist()
        else:
            volume_surge_dates = []

        volume_dry = df[df['Volume'] < avg_volume * 0.5].tail(5)
        # Ensure index is DatetimeIndex before calling strftime
        if len(volume_dry) > 0:
            if isinstance(volume_dry.index, pd.DatetimeIndex):
                volume_dryup_dates = volume_dry.index.strftime('%Y-%m-%d').tolist()
            else:
                # Convert to DatetimeIndex if needed
                volume_dryup_dates = pd.to_datetime(volume_dry.index).strftime('%Y-%m-%d').tolist()
        else:
            volume_dryup_dates = []
        
        # ========== CVD (Cumulative Volume Delta) Analysis ==========
        # Calculate volume delta and CVD
        delta = calculate_volume_delta(df)
        cvd = delta.cumsum()

        current_cvd = float(cvd.iloc[-1])
        current_delta = float(delta.iloc[-1])

        # CVD trend (20-day slope normalized)
        cvd_20d = cvd.tail(20)
        if len(cvd_20d) >= 20:
            x = np.arange(len(cvd_20d))
            slope, _ = np.polyfit(x, cvd_20d.values, 1)
            avg_cvd = abs(cvd_20d).mean()
            normalized_slope = slope / avg_cvd if avg_cvd > 0 else 0
        else:
            normalized_slope = 0

        if normalized_slope > 0.02:
            cvd_trend = "RISING"
            cvd_interpretation = "Buying pressure dominant - accumulation"
        elif normalized_slope < -0.02:
            cvd_trend = "FALLING"
            cvd_interpretation = "Selling pressure dominant - distribution"
        else:
            cvd_trend = "FLAT"
            cvd_interpretation = "Balanced buying/selling pressure"

        # Delta for last 5 bars
        delta_bars = []
        for i in range(-5, 0):
            if abs(i) <= len(df):
                delta_bars.append({
                    "date": df.index[i].strftime('%Y-%m-%d') if hasattr(df.index[i], 'strftime') else str(df.index[i]),
                    "delta": round(float(delta.iloc[i]), 0),
                    "cumulative": round(float(cvd.iloc[i]), 0),
                    "price": round(float(df['Close'].iloc[i]), 2),
                    "interpretation": "Buyers" if delta.iloc[i] > 0 else "Sellers"
                })

        # Detect CVD divergence
        divergence = detect_cvd_divergence(df)

        # Overall CVD assessment
        if divergence["signal"] == "BULLISH_DIVERGENCE":
            cvd_assessment = f"BULLISH - {divergence.get('strength', 'MODERATE')} divergence (sellers exhausted)"
        elif divergence["signal"] == "BEARISH_DIVERGENCE":
            cvd_assessment = f"BEARISH - {divergence.get('strength', 'MODERATE')} divergence (buyers exhausted)"
        elif cvd_trend == "RISING":
            cvd_assessment = "BULLISH - Accumulation in progress"
        elif cvd_trend == "FALLING":
            cvd_assessment = "BEARISH - Distribution in progress"
        else:
            cvd_assessment = "NEUTRAL - No clear directional pressure"

        # ========== Multi-VWAP Analysis (for swing trading) ==========
        df['Typical_Price_VWAP'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['PV_VWAP'] = df['Typical_Price_VWAP'] * df['Volume']

        # Rolling 20-day VWAP
        df['Rolling_VWAP'] = (
            df['PV_VWAP'].rolling(window=20).sum() /
            df['Volume'].rolling(window=20).sum()
        )
        rolling_vwap = float(df['Rolling_VWAP'].iloc[-1])
        rolling_std = float(df['Typical_Price_VWAP'].tail(20).std())

        # Anchored VWAP from period start
        df['Anchored_VWAP'] = df['PV_VWAP'].cumsum() / df['Volume'].cumsum()
        anchored_vwap = float(df['Anchored_VWAP'].iloc[-1])

        # VWAP positions and alignment
        def get_vwap_position(price, vwap, std):
            if price > vwap + 2 * std:
                return "EXTREME_ABOVE"
            elif price > vwap + std:
                return "EXTENDED_ABOVE"
            elif price > vwap:
                return "ABOVE"
            elif price < vwap - 2 * std:
                return "EXTREME_BELOW"
            elif price < vwap - std:
                return "EXTENDED_BELOW"
            else:
                return "BELOW"

        rolling_position = get_vwap_position(current_price, rolling_vwap, rolling_std)
        anchored_position = get_vwap_position(current_price, anchored_vwap, rolling_std)

        above_count = sum(1 for p in [rolling_position, anchored_position] if "ABOVE" in p)
        extreme_count = sum(1 for p in [rolling_position, anchored_position] if "EXTREME" in p)

        if above_count == 2:
            vwap_alignment = "STRONG_BULLISH"
        elif above_count == 0:
            vwap_alignment = "STRONG_BEARISH"
        else:
            vwap_alignment = "MIXED"

        extreme_extension = extreme_count >= 1
        sigma_distance = (current_price - rolling_vwap) / rolling_std if rolling_std > 0 else 0

        # ========== Liquidity Zones (HVN/LVN) Analysis ==========
        # Classify volume at each price level as High Volume Node or Low Volume Node
        volume_at_price = volume_profile.values  # Already sorted by volume descending
        mean_volume_at_price = volume_at_price.mean()
        std_volume_at_price = volume_at_price.std() if len(volume_at_price) > 1 else 0

        hvn_threshold = mean_volume_at_price + std_volume_at_price  # Above avg = HVN
        lvn_threshold = mean_volume_at_price - 0.5 * std_volume_at_price  # Below avg = LVN

        high_volume_nodes = []
        low_volume_nodes = []

        for idx, vol in enumerate(volume_profile.items()):
            price_bin, volume_val = vol
            price_level = (price_bin.left + price_bin.right) / 2
            relative_vol = volume_val / mean_volume_at_price if mean_volume_at_price > 0 else 0

            if volume_val > hvn_threshold:
                high_volume_nodes.append({
                    "price": round(float(price_level), 2),
                    "volume": int(volume_val),
                    "relative_volume": round(float(relative_vol), 2),
                    "type": "HVN"
                })
            elif volume_val < lvn_threshold:
                low_volume_nodes.append({
                    "price_low": round(float(price_bin.left), 2),
                    "price_high": round(float(price_bin.right), 2),
                    "volume": int(volume_val),
                    "relative_volume": round(float(relative_vol), 2),
                    "type": "LVN"
                })

        # Sort by proximity to current price
        high_volume_nodes.sort(key=lambda x: abs(x["price"] - current_price))
        low_volume_nodes.sort(key=lambda x: abs((x["price_low"] + x["price_high"]) / 2 - current_price))

        # Determine current zone type
        nearest_hvn = high_volume_nodes[0] if high_volume_nodes else None
        nearest_lvn = low_volume_nodes[0] if low_volume_nodes else None

        # Check if current price is in HVN zone (within 2% of HVN level)
        if nearest_hvn and abs(current_price - nearest_hvn["price"]) / current_price < 0.02:
            current_zone_type = "HIGH_VOLUME_NODE"
            expected_behavior = "CONSOLIDATION"
            zone_interpretation = "Price at HVN (magnet) - expect sideways consolidation"
        # Check if current price is in LVN zone
        elif nearest_lvn and (nearest_lvn["price_low"] <= current_price <= nearest_lvn["price_high"]):
            current_zone_type = "LOW_VOLUME_GAP"
            expected_behavior = "FAST_MOVE"
            zone_interpretation = "Price in LVN (gap) - expect fast, volatile movement"
        else:
            current_zone_type = "NORMAL"
            expected_behavior = "NORMAL"
            zone_interpretation = "Price in normal volume zone - standard price action expected"

        liquidity_zones = {
            "poc": round(float(poc_price), 2),
            "value_area_high": round(float(value_area_high), 2),
            "value_area_low": round(float(value_area_low), 2),
            "high_volume_nodes": high_volume_nodes[:5],  # Top 5 nearest
            "low_volume_nodes": low_volume_nodes[:3],    # Top 3 nearest
            "current_zone_type": current_zone_type,
            "expected_behavior": expected_behavior,
            "nearest_liquidity_magnet": nearest_hvn["price"] if nearest_hvn else round(float(poc_price), 2),
            "interpretation": zone_interpretation
        }

        # ========== DALIO ECONOMIC MACHINE METRICS ==========
        # Based on Ray Dalio's principle: Price = Total Spending / Quantity Sold
        # Dollar Volume = Typical Price * Volume (Total Spending)
        # VWAP = Dollar Volume / Volume (Average Price Paid)

        # 1. Dollar Volume Calculations
        df['Dollar_Volume'] = df['Typical_Price'] * df['Volume']

        dv_today = float(df['Dollar_Volume'].iloc[-1])
        dv_5d_avg = float(df['Dollar_Volume'].iloc[-5:].mean()) if len(df) >= 5 else dv_today
        dv_20d_avg = float(df['Dollar_Volume'].iloc[-20:].mean()) if len(df) >= 20 else dv_5d_avg
        dv_50d_avg = float(df['Dollar_Volume'].iloc[-50:].mean()) if len(df) >= 50 else dv_20d_avg

        # Relative dollar volume
        dv_relative_20d = dv_today / dv_20d_avg if dv_20d_avg > 0 else 1.0
        dv_relative_50d = dv_today / dv_50d_avg if dv_50d_avg > 0 else 1.0

        # Dollar volume percentile (90-day)
        dv_90d = df['Dollar_Volume'].iloc[-90:] if len(df) >= 90 else df['Dollar_Volume']
        dv_percentile = float((dv_90d < dv_today).sum() / len(dv_90d) * 100) if len(dv_90d) > 0 else 50.0

        # 2. Dalio Ratio (Current VWAP / Prior VWAP)
        # Session VWAP = Dollar Volume / Volume for each day
        df['Session_VWAP'] = df['Dollar_Volume'] / df['Volume']

        current_session_vwap = float(df['Session_VWAP'].iloc[-1])
        prior_5d_vwap = float(df['Session_VWAP'].iloc[-6:-1].mean()) if len(df) >= 6 else current_session_vwap
        prior_20d_vwap = float(df['Session_VWAP'].iloc[-21:-1].mean()) if len(df) >= 21 else prior_5d_vwap

        dalio_ratio_5d = current_session_vwap / prior_5d_vwap if prior_5d_vwap > 0 else 1.0
        dalio_ratio_20d = current_session_vwap / prior_20d_vwap if prior_20d_vwap > 0 else 1.0

        # Dalio ratio trend (is it increasing or decreasing?)
        if len(df) >= 10:
            dalio_ratios = []
            for i in range(-5, 0):
                curr_vwap = df['Session_VWAP'].iloc[i]
                prior_vwap = df['Session_VWAP'].iloc[i-5:i].mean() if abs(i-5) <= len(df) else curr_vwap
                if prior_vwap > 0:
                    dalio_ratios.append(curr_vwap / prior_vwap)
            if len(dalio_ratios) >= 2:
                dalio_trend = "INCREASING" if dalio_ratios[-1] > dalio_ratios[0] else "DECREASING" if dalio_ratios[-1] < dalio_ratios[0] else "FLAT"
            else:
                dalio_trend = "FLAT"
        else:
            dalio_trend = "INSUFFICIENT_DATA"

        # 3. Dollar Volume Momentum
        dv_momentum = ((dv_today - dv_20d_avg) / dv_20d_avg * 100) if dv_20d_avg > 0 else 0.0
        dv_momentum_class = _classify_dv_momentum(dv_momentum)

        # 4. Spending Efficiency Ratio
        if len(df) >= 2:
            price_change_pct = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100) if df['Close'].iloc[-2] > 0 else 0.0
            dv_change_pct = ((dv_today - float(df['Dollar_Volume'].iloc[-2])) / float(df['Dollar_Volume'].iloc[-2]) * 100) if df['Dollar_Volume'].iloc[-2] > 0 else 0.0
            spending_efficiency = price_change_pct / dv_change_pct if dv_change_pct != 0 else 0.0
        else:
            price_change_pct = 0.0
            dv_change_pct = 0.0
            spending_efficiency = 0.0

        efficiency_interpretation = _interpret_spending_efficiency(spending_efficiency)

        # 5. Cumulative Dollar Flow - TWO METHODS

        # METHOD 1: Simple Dollar Flow (Close vs Prior Close) - RAY DALIO ALIGNED
        # This is what traders actually mean by "money flow" - did the stock go UP or DOWN today?
        # Up day (close > prior close) = net buying, Down day = net selling
        df['Prior_Close'] = df['Close'].shift(1)
        df['Daily_Direction'] = np.where(df['Close'] > df['Prior_Close'], 1,
                                         np.where(df['Close'] < df['Prior_Close'], -1, 0))
        df['Simple_DV'] = df['Dollar_Volume'] * df['Daily_Direction']

        simple_5d = float(df['Simple_DV'].iloc[-5:].sum()) if len(df) >= 5 else 0.0
        simple_20d = float(df['Simple_DV'].iloc[-20:].sum()) if len(df) >= 20 else simple_5d
        simple_direction = "ACCUMULATION" if simple_20d > 0 else "DISTRIBUTION"

        # Calculate up/down day breakdown
        last_20 = df.iloc[-20:] if len(df) >= 20 else df
        up_days = (last_20['Daily_Direction'] > 0).sum()
        down_days = (last_20['Daily_Direction'] < 0).sum()
        flat_days = (last_20['Daily_Direction'] == 0).sum()
        up_volume = float(last_20[last_20['Daily_Direction'] > 0]['Dollar_Volume'].sum())
        down_volume = float(last_20[last_20['Daily_Direction'] < 0]['Dollar_Volume'].sum())
        total_volume = up_volume + down_volume
        up_pct = round(up_volume / total_volume * 100, 1) if total_volume > 0 else 0
        down_pct = round(down_volume / total_volume * 100, 1) if total_volume > 0 else 0

        # Build day-by-day breakdown for debugging
        daily_breakdown = []
        for idx in range(len(last_20)):
            row = last_20.iloc[idx]
            date_str = row.name.strftime('%Y-%m-%d') if hasattr(row.name, 'strftime') else str(row.name)
            direction = "UP" if row['Daily_Direction'] > 0 else "DOWN" if row['Daily_Direction'] < 0 else "FLAT"
            daily_breakdown.append({
                "date": date_str,
                "close": round(float(row['Close']), 2),
                "prior_close": round(float(row['Prior_Close']), 2) if pd.notna(row['Prior_Close']) else None,
                "pct_change": round((row['Close'] / row['Prior_Close'] - 1) * 100, 2) if pd.notna(row['Prior_Close']) and row['Prior_Close'] > 0 else None,
                "volume": int(row['Volume']),
                "dollar_volume": int(row['Dollar_Volume']),
                "direction": direction,
                "contribution": int(row['Simple_DV'])
            })

        # METHOD 2: Candle Dollar Flow (Close vs Open) - INTRADAY SENTIMENT
        # This shows intraday sentiment: green candle = buyers won that day
        df['Candle_Direction'] = np.where(df['Close'] >= df['Open'], 1, -1)
        df['Candle_DV'] = df['Dollar_Volume'] * df['Candle_Direction']

        candle_5d = float(df['Candle_DV'].iloc[-5:].sum()) if len(df) >= 5 else 0.0
        candle_20d = float(df['Candle_DV'].iloc[-20:].sum()) if len(df) >= 20 else candle_5d
        candle_direction = "BULLISH_CANDLES" if candle_20d > 0 else "BEARISH_CANDLES"

        # Use SIMPLE dollar flow as the primary CDF (Dalio-aligned)
        cdf_5d = simple_5d
        cdf_20d = simple_20d
        cdf_direction = simple_direction

        # CDF acceleration (is flow speeding up or slowing down?)
        if len(df) >= 10:
            cdf_first_half = float(df['Simple_DV'].iloc[-20:-10].sum()) if len(df) >= 20 else 0.0
            cdf_second_half = float(df['Simple_DV'].iloc[-10:].sum())
            if cdf_first_half != 0:
                cdf_acceleration = "INCREASING" if abs(cdf_second_half) > abs(cdf_first_half) * 1.2 else "DECREASING" if abs(cdf_second_half) < abs(cdf_first_half) * 0.8 else "STABLE"
            else:
                cdf_acceleration = "STABLE"
        else:
            cdf_acceleration = "INSUFFICIENT_DATA"

        # Efficiency implication
        efficiency_implication = _derive_efficiency_implication(spending_efficiency, cdf_20d)

        # 6. Dollar Volume Profile
        dollar_profile = _calculate_dollar_volume_profile(df)
        dv_poc = dollar_profile.get("point_of_control", poc_price)

        # 7. Institutional Activity Detection
        # Count high DV days in last 20
        if len(df) >= 20:
            high_dv_threshold = dv_20d_avg * 1.5
            high_dv_days = int((df['Dollar_Volume'].iloc[-20:] > high_dv_threshold).sum())
        else:
            high_dv_days = 0

        institutional = _detect_institutional_activity(
            dv_momentum, spending_efficiency, cdf_20d, dv_20d_avg, high_dv_days
        )

        # 8. Trend Sustainability Score
        sustainability = _assess_trend_sustainability(
            dalio_ratio_20d, dv_momentum, spending_efficiency, cdf_20d,
            current_price, float(dv_poc)
        )

        # Compile Dalio Metrics
        dalio_metrics = {
            "principle": "Price = Total Spending / Quantity Sold (Ray Dalio)",
            # Dalio Ratio
            "dalio_ratio": {
                "current": round(dalio_ratio_5d, 4),
                "5d_avg": round(dalio_ratio_5d, 4),
                "20d_avg": round(dalio_ratio_20d, 4),
                "interpretation": _interpret_dalio_ratio(dalio_ratio_20d),
                "trend": dalio_trend,
                "note": ">1.0 = buyers paying more (bullish), <1.0 = buyers paying less (bearish)"
            },
            # Dollar Volume
            "dollar_volume": {
                "today": int(dv_today),
                "5d_avg": int(dv_5d_avg),
                "20d_avg": int(dv_20d_avg),
                "50d_avg": int(dv_50d_avg),
                "relative_to_20d": round(dv_relative_20d, 2),
                "relative_to_50d": round(dv_relative_50d, 2),
                "momentum_pct": round(dv_momentum, 1),
                "momentum": dv_momentum_class,
                "percentile_90d": round(dv_percentile, 1)
            },
            # Spending Efficiency
            "spending_efficiency": {
                "ratio": round(spending_efficiency, 4),
                "interpretation": efficiency_interpretation,
                "implication": efficiency_implication,
                "price_change_pct": round(price_change_pct, 2),
                "dv_change_pct": round(dv_change_pct, 2),
                "note": "<0.5 = high absorption (accumulation/distribution), >1.5 = low liquidity"
            },
            # Cumulative Dollar Flow (Simple = Close vs Prior Close, Dalio-aligned)
            "cumulative_dollar_flow": {
                "5d": int(simple_5d),
                "20d": int(simple_20d),
                "20d_formatted": f"${simple_20d/1e9:,.2f}B" if abs(simple_20d) >= 1e9 else f"${simple_20d/1e6:,.1f}M",
                "direction": simple_direction,
                "acceleration": cdf_acceleration,
                "method": "SIMPLE (Close vs Prior Close)",
                "up_days": int(up_days),
                "down_days": int(down_days),
                "flat_days": int(flat_days),
                "up_volume_pct": up_pct,
                "down_volume_pct": down_pct,
                "up_dollar_volume": int(up_volume),
                "down_dollar_volume": int(down_volume),
                "daily_breakdown": daily_breakdown,
                "note": "Simple dollar flow: Up day (close > prior close) = +$, Down day = -$"
            },
            # Candle Dollar Flow (Close vs Open - intraday sentiment)
            "candle_dollar_flow": {
                "5d": int(candle_5d),
                "20d": int(candle_20d),
                "20d_formatted": f"${candle_20d/1e9:,.2f}B" if abs(candle_20d) >= 1e9 else f"${candle_20d/1e6:,.1f}M",
                "direction": candle_direction,
                "method": "CANDLE (Close vs Open)",
                "note": "Intraday sentiment: Green candle = +$, Red candle = -$"
            },
            # Dollar Volume Profile
            "dollar_profile": dollar_profile,
            # Institutional Activity
            "institutional_activity": institutional,
            # Trend Sustainability
            "trend_sustainability": sustainability,
            # Gate 2 Integration (for 4-gate validation)
            "gate_2_contribution": {
                "dalio_ratio_bullish": dalio_ratio_20d > 1.0,
                "dalio_ratio_bearish": dalio_ratio_20d < 1.0,
                "dollar_flow_positive": simple_20d > 0,
                "dollar_flow_negative": simple_20d < 0,
                "sustainability_ok": sustainability["score"] >= 50,
                "dollar_flow_method": "SIMPLE (Close vs Prior Close)",
                "note": "Uses SIMPLE dollar flow (Dalio-aligned) for Gate 2 validation"
            }
        }

        return {
            "ticker": ticker,
            "data_source": _get_data_source(ticker),
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "current_price": round(current_price, 2),
            "vwap": round(current_vwap, 2),
            "vwap_type": vwap_type,
            "vwap_mode": vwap_mode,
            "vwap_distance_%": round(vwap_distance, 2),
            "vwap_interpretation": "Above VWAP (bullish)" if vwap_distance > 0 else "Below VWAP (bearish)",
            "volume_profile": {
                "poc_price": round(poc_price, 2),
                "value_area_high": round(value_area_high, 2),
                "value_area_low": round(value_area_low, 2),
                "poc_vs_price": "Price above POC" if current_price > poc_price else "Price below POC"
            },
            "current_volume": int(current_volume),
            "avg_volume_20d": int(avg_volume),
            "relative_volume": round(relative_volume, 2),
            "relative_volume_interpretation":
                "VERY HIGH (2x+ average)" if relative_volume > 2.0 else
                "HIGH (1.5x+ average)" if relative_volume > 1.5 else
                "Above Average" if relative_volume > 1.0 else
                "Below Average" if relative_volume > 0.7 else
                "VERY LOW (caution)",
            "volume_surges_recent": volume_surge_dates,
            "volume_dryups_recent": volume_dryup_dates,
            "obv_trend": obv_trend,
            "accumulation_distribution_trend": ad_trend,
            "mfi": round(current_mfi, 2),
            "mfi_signal": mfi_signal,
            "price_volume_confirmation": confirmation,
            # ========== NEW: CVD Analysis ==========
            "cvd_analysis": {
                "current_cvd": round(current_cvd, 0),
                "current_delta": round(current_delta, 0),
                "cvd_trend": cvd_trend,
                "cvd_slope_20d": round(normalized_slope, 4),
                "trend_interpretation": cvd_interpretation,
                "divergence": divergence,
                "delta_bars": delta_bars,
                "assessment": cvd_assessment,
                "methodology_note": "CVD approximated from OHLCV. Bullish/Bearish divergence = exhaustion signal."
            },
            # ========== NEW: Multi-VWAP Analysis ==========
            "multi_vwap": {
                "rolling_vwap": round(rolling_vwap, 2),
                "anchored_vwap": round(anchored_vwap, 2),
                "rolling_position": rolling_position,
                "anchored_position": anchored_position,
                "alignment": vwap_alignment,
                "extreme_extension": extreme_extension,
                "sigma_distance": round(sigma_distance, 2),
                "mean_reversion_target": round(rolling_vwap, 2) if extreme_extension else None,
                "interpretation": f"Price is {vwap_alignment} vs VWAPs. {'Extended - expect reversion.' if extreme_extension else 'Sustainable move.'}"
            },
            # ========== NEW: Liquidity Zones Analysis ==========
            "liquidity_zones": liquidity_zones,
            # ========== NEW: Dalio Economic Machine Metrics ==========
            "dalio_metrics": dalio_metrics,
            "professional_note": vwap_note
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def analyze_volume_intraday(ticker: str, window: int = 100) -> dict:
    """
    Calculate TRUE intraday VWAP like TradingView using 15-minute bars.
    This matches TradingView's VWAP exactly - resets daily and uses intraday data.
    
    Args:
        ticker: Stock ticker symbol  
        window: Number of 15-minute bars (default 100 = ~25 hours of trading)
    
    Returns:
        Dictionary with today's true intraday VWAP
    """
    try:
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        import os
        
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')
        
        if not api_key or not api_secret:
            return {"error": "Alpaca API credentials not set. Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables"}
        
        # Fetch 15-minute intraday bars
        timeframe = TimeFrame(15, TimeFrameUnit.Minute)
        client = StockHistoricalDataClient(api_key, api_secret)
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=timeframe,
            limit=window
        )
        
        df_raw = client.get_stock_bars(request).df
        
        if df_raw.empty:
            return {"error": f"No intraday data for {ticker}"}
        
        # Convert to Eastern Time
        df_raw.index = df_raw.index.get_level_values('timestamp').tz_convert("America/New_York")
        
        # Get today's data only (THIS IS THE KEY - DAILY RESET)
        today = pd.Timestamp.now(tz='America/New_York').date()
        df_today = df_raw[df_raw.index.date == today].copy()
        
        if df_today.empty:
            return {"error": "No data for today yet (market may not be open)"}
        
        # Calculate VWAP correctly: Typical Price * Volume, cumulative for TODAY ONLY
        df_today['Typical_Price'] = (df_today['high'] + df_today['low'] + df_today['close']) / 3
        df_today['TP_Volume'] = df_today['Typical_Price'] * df_today['volume']
        
        # Calculate cumulative VWAP for today's session
        df_today['Cumulative_TPV'] = df_today['TP_Volume'].cumsum()
        df_today['Cumulative_Volume'] = df_today['volume'].cumsum()
        df_today['VWAP'] = df_today['Cumulative_TPV'] / df_today['Cumulative_Volume']
        
        # Current values
        vwap_today = df_today['VWAP'].iloc[-1]
        current_price = df_today['close'].iloc[-1]
        vwap_distance = ((current_price - vwap_today) / vwap_today) * 100
        
        # VWAP standard deviation bands (like Bollinger Bands for VWAP)
        df_today['Price_Dev'] = df_today['Typical_Price'] - df_today['VWAP']
        df_today['Squared_Dev'] = df_today['Price_Dev'] ** 2
        variance = (df_today['Squared_Dev'] * df_today['volume']).cumsum() / df_today['Cumulative_Volume']
        std_dev = np.sqrt(variance.iloc[-1])
        
        vwap_upper_1 = vwap_today + std_dev
        vwap_lower_1 = vwap_today - std_dev
        vwap_upper_2 = vwap_today + (2 * std_dev)
        vwap_lower_2 = vwap_today - (2 * std_dev)
        
        # Determine band position
        if current_price > vwap_upper_2:
            band_position = "Above +2 StdDev (extremely overbought)"
        elif current_price > vwap_upper_1:
            band_position = "Above +1 StdDev (overbought)"
        elif current_price < vwap_lower_2:
            band_position = "Below -2 StdDev (extremely oversold)"
        elif current_price < vwap_lower_1:
            band_position = "Below -1 StdDev (oversold)"
        else:
            band_position = "Within ±1 StdDev (normal range)"
        
        return {
            "ticker": ticker,
            "date": str(today),
            "current_time": df_today.index[-1].strftime("%Y-%m-%d %H:%M:%S %Z"),
            "current_price": round(current_price, 2),
            "vwap_intraday": round(vwap_today, 2),
            "vwap_distance_%": round(vwap_distance, 2),
            "vwap_type": "Intraday VWAP (Today's Session Only)",
            "vwap_bands": {
                "upper_2_stddev": round(vwap_upper_2, 2),
                "upper_1_stddev": round(vwap_upper_1, 2),
                "vwap": round(vwap_today, 2),
                "lower_1_stddev": round(vwap_lower_1, 2),
                "lower_2_stddev": round(vwap_lower_2, 2)
            },
            "band_position": band_position,
            "bars_analyzed": len(df_today),
            "session_high": round(df_today['high'].max(), 2),
            "session_low": round(df_today['low'].min(), 2),
            "interpretation": "Above VWAP (bullish intraday)" if vwap_distance > 0 else "Below VWAP (bearish intraday)",
            "trading_note": "This EXACTLY matches TradingView's VWAP - resets daily, uses intraday data"
        }
        
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def analyze_volatility(ticker: str, period: str = "6mo") -> dict:
    """
    Comprehensive volatility analysis for risk management.
    ATR is THE professional standard for stop placement.
    
    Args:
        ticker: Stock ticker symbol
        period: Historical period (3mo, 6mo, 1y, 2y)
    
    Returns:
        Dictionary containing volatility metrics
    """
    try:
        # Use Questrade-first approach
        df = _get_price_history(ticker, period)
        spy = _get_price_history("SPY", period)

        if df.empty:
            return {"error": f"No data available for {ticker}"}
        
        # ATR (Average True Range) - THE standard for stops
        # Calculate True Range
        df['H-L'] = df['High'] - df['Low']
        df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        
        # ATR using Wilder's smoothing (RMA) - matches TradingView
        # Formula: ATR = (Previous ATR * (n-1) + Current TR) / n
        def calculate_atr_wilder(tr_series, period=14):
            """Calculate ATR using Wilder's smoothing (RMA) - TradingView method"""
            atr_values = []
            for i in range(len(tr_series)):
                if i < period:
                    # Not enough data yet
                    atr_values.append(np.nan)
                elif i == period:
                    # First ATR is simple average of first n periods
                    atr_values.append(tr_series.iloc[:period].mean())
                else:
                    # Subsequent ATRs use Wilder's smoothing
                    prev_atr = atr_values[-1]
                    current_tr = tr_series.iloc[i]
                    new_atr = (prev_atr * (period - 1) + current_tr) / period
                    atr_values.append(new_atr)
            return pd.Series(atr_values, index=tr_series.index)
        
        df['ATR_14'] = calculate_atr_wilder(df['TR'], 14)
        df['ATR_20'] = calculate_atr_wilder(df['TR'], 20)
        
        current_atr_14 = df['ATR_14'].iloc[-1]
        current_atr_20 = df['ATR_20'].iloc[-1]
        current_price = df['Close'].iloc[-1]
        atr_pct_14 = (current_atr_14 / current_price) * 100
        atr_pct_20 = (current_atr_20 / current_price) * 100
        
        # Historical Volatility (annualized)
        df['Returns'] = df['Close'].pct_change()
        hv_10d = df['Returns'].tail(10).std() * np.sqrt(252) * 100
        hv_20d = df['Returns'].tail(20).std() * np.sqrt(252) * 100
        hv_30d = df['Returns'].tail(30).std() * np.sqrt(252) * 100
        hv_60d = df['Returns'].tail(60).std() * np.sqrt(252) * 100
        
        # Volatility Percentile (current vs 1-year)
        one_year_hvs = df['Returns'].rolling(20).std().tail(252) * np.sqrt(252) * 100
        current_hv = hv_20d
        percentile = (one_year_hvs < current_hv).sum() / len(one_year_hvs.dropna()) * 100 if len(one_year_hvs.dropna()) > 0 else 50
        
        # Volatility Regime
        if percentile > 80:
            vol_regime = "EXTREME HIGH"
        elif percentile > 60:
            vol_regime = "HIGH"
        elif percentile > 40:
            vol_regime = "NORMAL"
        elif percentile > 20:
            vol_regime = "LOW"
        else:
            vol_regime = "EXTREME LOW"
        
        # Beta vs SPY
        if not spy.empty:
            combined = pd.merge(df[['Close']], spy[['Close']], 
                              left_index=True, right_index=True, suffixes=('_stock', '_spy'))
            combined['Returns_Stock'] = combined['Close_stock'].pct_change()
            combined['Returns_SPY'] = combined['Close_spy'].pct_change()
            covariance = combined['Returns_Stock'].cov(combined['Returns_SPY'])
            spy_variance = combined['Returns_SPY'].var()
            beta = covariance / spy_variance if spy_variance != 0 else 1.0
        else:
            beta = 1.0
        
        # Beta interpretation
        if beta > 1.5:
            beta_interp = "Very High Volatility vs Market"
        elif beta > 1.0:
            beta_interp = "Higher Volatility than Market"
        elif beta > 0.5:
            beta_interp = "Lower Volatility than Market"
        else:
            beta_interp = "Much Lower Volatility than Market"
        
        # Keltner Channels (ATR-based bands)
        df['EMA_20'] = df['Close'].ewm(span=20).mean()
        df['Keltner_Upper'] = df['EMA_20'] + (2 * df['ATR_20'])
        df['Keltner_Lower'] = df['EMA_20'] - (2 * df['ATR_20'])
        keltner_upper = df['Keltner_Upper'].iloc[-1]
        keltner_lower = df['Keltner_Lower'].iloc[-1]
        
        # Bollinger Band Width (volatility indicator)
        df['BB_Middle'] = df['Close'].rolling(20).mean()
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Middle'] + (2 * df['BB_Std'])
        df['BB_Lower'] = df['BB_Middle'] - (2 * df['BB_Std'])
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
        bb_width = df['BB_Width'].iloc[-1] * 100
        
        # ATR-based stop recommendations (PROFESSIONAL STANDARD)
        stop_2x_atr = round(current_price - (current_atr_14 * 2), 2)
        stop_2_5x_atr = round(current_price - (current_atr_14 * 2.5), 2)
        stop_3x_atr = round(current_price - (current_atr_14 * 3), 2)
        
        # ATR-based position sizing (1% risk rule)
        # Example: If account = $100k, risk 1% = $1000
        # Risk per share = 2.5x ATR
        # Shares = $1000 / (2.5 * ATR)
        risk_per_share_2_5x = current_atr_14 * 2.5
        
        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "atr_14": round(current_atr_14, 2),
            "atr_20": round(current_atr_20, 2),
            "atr_14_%_of_price": round(atr_pct_14, 2),
            "atr_20_%_of_price": round(atr_pct_20, 2),
            "historical_volatility": {
                "10_day_%": round(hv_10d, 2),
                "20_day_%": round(hv_20d, 2),
                "30_day_%": round(hv_30d, 2),
                "60_day_%": round(hv_60d, 2)
            },
            "volatility_percentile": round(percentile, 1),
            "volatility_regime": vol_regime,
            "beta_vs_spy": round(beta, 2),
            "beta_interpretation": beta_interp,
            "keltner_channels": {
                "upper": round(keltner_upper, 2),
                "middle": round(df['EMA_20'].iloc[-1], 2),
                "lower": round(keltner_lower, 2)
            },
            "bollinger_band_width_%": round(bb_width, 2),
            "stop_loss_recommendations": {
                "aggressive_2x_atr": stop_2x_atr,
                "standard_2.5x_atr": stop_2_5x_atr,
                "conservative_3x_atr": stop_3x_atr,
                "note": "2.5x ATR is professional standard"
            },
            "position_sizing_example": {
                "risk_per_share_2.5x_atr": round(risk_per_share_2_5x, 2),
                "formula": "Shares = (Account_Size * Risk_%) / (2.5 * ATR)",
                "example": f"For $100k account, 1% risk: {int(1000/risk_per_share_2_5x)} shares"
            }
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def calculate_relative_strength(ticker: str, benchmark: str = "SPY", period: str = "3mo") -> dict:
    """
    Calculate relative strength to identify market leaders.
    RS Rating >70 = Buy only leaders (IBD methodology)
    
    Args:
        ticker: Stock ticker symbol
        benchmark: Benchmark ticker (default SPY)
        period: Comparison period (1mo, 3mo, 6mo, 1y, 2y)
    
    Returns:
        Dictionary containing RS metrics
    """
    try:
        # Use Questrade-first approach
        stock = _get_price_history(ticker, period)
        bench = _get_price_history(benchmark, period)

        if stock.empty or bench.empty:
            return {"error": f"No data available"}
        
        # Align dates
        combined = pd.merge(stock[['Close']], bench[['Close']], 
                          left_index=True, right_index=True, suffixes=('_stock', '_bench'))
        
        # Calculate returns from start
        combined['Stock_Return'] = (combined['Close_stock'] / combined['Close_stock'].iloc[0] - 1) * 100
        combined['Bench_Return'] = (combined['Close_bench'] / combined['Close_bench'].iloc[0] - 1) * 100
        combined['Relative_Return'] = combined['Stock_Return'] - combined['Bench_Return']
        
        # Current outperformance
        outperformance = combined['Relative_Return'].iloc[-1]
        
        # RS Trend (improving or deteriorating?)
        recent_rs = combined['Relative_Return'].tail(20)
        rs_slope = np.polyfit(range(len(recent_rs)), recent_rs, 1)[0]
        rs_trend = "Improving" if rs_slope > 0 else "Deteriorating"
        
        # RS Score (0-100, IBD-style)
        # Professional traders focus on RS > 70
        if outperformance > 20:
            rs_score = 99
        elif outperformance > 15:
            rs_score = 95
        elif outperformance > 10:
            rs_score = 90
        elif outperformance > 7:
            rs_score = 85
        elif outperformance > 5:
            rs_score = 80
        elif outperformance > 3:
            rs_score = 75
        elif outperformance > 1:
            rs_score = 70
        elif outperformance > 0:
            rs_score = 60
        elif outperformance > -2:
            rs_score = 50
        elif outperformance > -5:
            rs_score = 40
        elif outperformance > -10:
            rs_score = 30
        else:
            rs_score = 20
        
        # Classification
        if rs_score >= 90:
            classification = "EXCEPTIONAL LEADER"
        elif rs_score >= 80:
            classification = "STRONG LEADER"
        elif rs_score >= 70:
            classification = "LEADER"
        elif rs_score >= 60:
            classification = "MARKET PERFORMER"
        elif rs_score >= 40:
            classification = "LAGGARD"
        else:
            classification = "WEAK LAGGARD"
        
        # Trading recommendation based on RS
        if rs_score >= 70 and rs_trend == "Improving":
            recommendation = "BUY - Strong leader with improving RS"
        elif rs_score >= 70 and rs_trend == "Deteriorating":
            recommendation = "HOLD - Leader but RS deteriorating"
        elif rs_score < 70 and rs_score >= 50:
            recommendation = "NEUTRAL - Wait for RS improvement"
        else:
            recommendation = "AVOID - Weak relative strength"
        
        return {
            "ticker": ticker,
            "benchmark": benchmark,
            "period": period,
            "rs_score": rs_score,
            "rs_trend": rs_trend,
            "classification": classification,
            "outperformance_%": round(outperformance, 2),
            "stock_return_%": round(combined['Stock_Return'].iloc[-1], 2),
            "benchmark_return_%": round(combined['Bench_Return'].iloc[-1], 2),
            "recommendation": recommendation,
            "ibd_note": "IBD methodology: Only buy stocks with RS > 70"
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def calculate_fundamental_scores(ticker: str, max_periods: int = 8) -> dict:
    """
    Calculate comprehensive fundamental quality scores.
    Piotroski F-Score: >7 = Excellent, <3 = Value trap
    Altman Z-Score: >2.99 = Safe, <1.81 = Bankruptcy risk
    
    Args:
        ticker: Stock ticker symbol
        max_periods: Number of periods to analyze
    
    Returns:
        Dictionary containing fundamental scores
    """
    try:
        stock = yf.Ticker(ticker)
        balance_sheet = stock.quarterly_balance_sheet
        income_stmt = stock.quarterly_income_stmt
        cashflow = stock.quarterly_cashflow
        info = stock.info
        
        if balance_sheet.empty or income_stmt.empty:
            return {"error": f"No financial data for {ticker}"}
        
        # Get latest and previous period data
        latest_bs = balance_sheet.iloc[:, 0]
        prev_bs = balance_sheet.iloc[:, 1] if len(balance_sheet.columns) > 1 else latest_bs
        latest_is = income_stmt.iloc[:, 0]
        prev_is = income_stmt.iloc[:, 1] if len(income_stmt.columns) > 1 else latest_is
        latest_cf = cashflow.iloc[:, 0] if not cashflow.empty else pd.Series()
        
        # ========== PIOTROSKI F-SCORE (0-9) ==========
        f_score = 0
        f_score_details = []
        
        # 1. Positive Net Income
        net_income = latest_is.get('Net Income', 0)
        if net_income > 0:
            f_score += 1
            f_score_details.append("✓ Positive Net Income")
        else:
            f_score_details.append("✗ Negative Net Income")
        
        # 2. Positive Operating Cash Flow
        operating_cf = latest_cf.get('Operating Cash Flow', 0)
        if operating_cf > 0:
            f_score += 1
            f_score_details.append("✓ Positive Operating Cash Flow")
        else:
            f_score_details.append("✗ Negative Operating Cash Flow")
        
        # 3. ROA Improvement
        total_assets = latest_bs.get('Total Assets', 1)
        prev_total_assets = prev_bs.get('Total Assets', 1)
        roa_current = net_income / total_assets if total_assets != 0 else 0
        prev_net_income = prev_is.get('Net Income', 0)
        roa_prev = prev_net_income / prev_total_assets if prev_total_assets != 0 else 0
        if roa_current > roa_prev:
            f_score += 1
            f_score_details.append("✓ ROA Improving")
        else:
            f_score_details.append("✗ ROA Declining")
        
        # 4. Quality of Earnings (CF > NI)
        if operating_cf > net_income:
            f_score += 1
            f_score_details.append("✓ Cash Flow > Net Income")
        else:
            f_score_details.append("✗ Cash Flow < Net Income")
        
        # 5. Decreasing Long-term Debt
        ltd_current = latest_bs.get('Long Term Debt', 0)
        ltd_prev = prev_bs.get('Long Term Debt', 0)
        if ltd_current < ltd_prev:
            f_score += 1
            f_score_details.append("✓ Debt Decreasing")
        else:
            f_score_details.append("✗ Debt Increasing")
        
        # 6. Current Ratio Improvement
        current_assets = latest_bs.get('Current Assets', 0)
        current_liabilities = latest_bs.get('Current Liabilities', 1)
        prev_current_assets = prev_bs.get('Current Assets', 0)
        prev_current_liabilities = prev_bs.get('Current Liabilities', 1)
        current_ratio = current_assets / current_liabilities if current_liabilities != 0 else 0
        prev_current_ratio = prev_current_assets / prev_current_liabilities if prev_current_liabilities != 0 else 0
        if current_ratio > prev_current_ratio:
            f_score += 1
            f_score_details.append("✓ Current Ratio Improving")
        else:
            f_score_details.append("✗ Current Ratio Declining")
        
        # 7. No New Shares Issued (simplified - using shares outstanding)
        shares_current = info.get('sharesOutstanding', 0)
        # Approximate previous shares (we'll give benefit of doubt if data not available)
        f_score += 1
        f_score_details.append("✓ No Dilution (assumed)")
        
        # 8. Gross Margin Improvement
        revenue = latest_is.get('Total Revenue', 1)
        cogs = latest_is.get('Cost Of Revenue', 0)
        gross_margin = (revenue - cogs) / revenue if revenue != 0 else 0
        prev_revenue = prev_is.get('Total Revenue', 1)
        prev_cogs = prev_is.get('Cost Of Revenue', 0)
        prev_gross_margin = (prev_revenue - prev_cogs) / prev_revenue if prev_revenue != 0 else 0
        if gross_margin > prev_gross_margin:
            f_score += 1
            f_score_details.append("✓ Gross Margin Improving")
        else:
            f_score_details.append("✗ Gross Margin Declining")
        
        # 9. Asset Turnover Improvement
        asset_turnover = revenue / total_assets if total_assets != 0 else 0
        prev_asset_turnover = prev_revenue / prev_total_assets if prev_total_assets != 0 else 0
        if asset_turnover > prev_asset_turnover:
            f_score += 1
            f_score_details.append("✓ Asset Turnover Improving")
        else:
            f_score_details.append("✗ Asset Turnover Declining")
        
        # F-Score Interpretation
        if f_score >= 7:
            f_interpretation = "EXCELLENT - Strong fundamentals"
        elif f_score >= 5:
            f_interpretation = "GOOD - Decent fundamentals"
        elif f_score >= 3:
            f_interpretation = "WEAK - Questionable fundamentals"
        else:
            f_interpretation = "POOR - Likely value trap"
        
        # ========== ALTMAN Z-SCORE (Bankruptcy Prediction) ==========
        retained_earnings = latest_bs.get('Retained Earnings', 0)
        ebit = latest_is.get('EBIT', latest_is.get('Operating Income', 0))
        total_liabilities = latest_bs.get('Total Liabilities Net Minority Interest', 1)
        market_cap = info.get('marketCap', 0)
        
        # Working Capital
        working_capital = current_assets - current_liabilities
        
        # Z-Score components
        x1 = working_capital / total_assets if total_assets != 0 else 0
        x2 = retained_earnings / total_assets if total_assets != 0 else 0
        x3 = ebit / total_assets if total_assets != 0 else 0
        x4 = market_cap / total_liabilities if total_liabilities != 0 else 0
        x5 = revenue / total_assets if total_assets != 0 else 0
        
        # Z-Score formula
        z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
        
        # Z-Score zones
        if z_score > 2.99:
            z_zone = "SAFE ZONE"
            bankruptcy_risk = "Low"
        elif z_score > 1.81:
            z_zone = "GREY ZONE"
            bankruptcy_risk = "Medium"
        else:
            z_zone = "DISTRESS ZONE"
            bankruptcy_risk = "High"
        
        # Additional metrics
        debt_to_equity = total_liabilities / (total_assets - total_liabilities) if (total_assets - total_liabilities) != 0 else 0
        interest_coverage = ebit / latest_is.get('Interest Expense', 1) if latest_is.get('Interest Expense', 0) != 0 else 999
        
        return {
            "ticker": ticker,
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "piotroski_f_score": {
                "score": f_score,
                "out_of": 9,
                "interpretation": f_interpretation,
                "details": f_score_details,
                "recommendation": "BUY candidate if >7" if f_score >= 7 else "AVOID if <3" if f_score < 3 else "NEUTRAL"
            },
            "altman_z_score": {
                "score": round(z_score, 2),
                "zone": z_zone,
                "bankruptcy_risk": bankruptcy_risk,
                "interpretation": 
                    "Financially strong" if z_score > 2.99 else
                    "Caution advised" if z_score > 1.81 else
                    "High distress - avoid"
            },
            "additional_metrics": {
                "current_ratio": round(current_ratio, 2),
                "debt_to_equity": round(debt_to_equity, 2),
                "interest_coverage": round(interest_coverage, 2) if interest_coverage < 999 else "N/A",
                "roa_%": round(roa_current * 100, 2),
                "gross_margin_%": round(gross_margin * 100, 2)
            },
            "overall_assessment":
                "STRONG BUY candidate" if f_score >= 7 and z_score > 2.99 else
                "Quality company" if f_score >= 5 and z_score > 2.99 else
                "Proceed with caution" if f_score >= 3 or z_score > 1.81 else
                "AVOID - Poor fundamentals"
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


# ============================================================================
# CVD (Cumulative Volume Delta) Analysis - Volumetric Liquidity Sequencing
# Based on Reddit trader methodology ($122k YTD, 54% win rate, 2.31 PF)
# Key insight: "Price is simply an ad seeking liquidity"
# ============================================================================

def calculate_volume_delta(df: pd.DataFrame) -> pd.Series:
    """
    Approximate buy/sell volume using OHLCV data.

    Logic: If close is near high, more buying pressure.
           If close is near low, more selling pressure.

    This is the standard approximation used by TradingView and most
    retail platforms without tick data.

    Formula:
        buy_ratio = (Close - Low) / (High - Low)
        sell_ratio = (High - Close) / (High - Low)
        delta = buy_volume - sell_volume
    """
    high_low_range = df['High'] - df['Low']

    # Avoid division by zero (doji bars where High = Low)
    high_low_range = high_low_range.replace(0, 0.0001)

    # Buy volume: proportion of bar that closed higher
    buy_ratio = (df['Close'] - df['Low']) / high_low_range
    buy_volume = buy_ratio * df['Volume']

    # Sell volume: proportion of bar that closed lower
    sell_ratio = (df['High'] - df['Close']) / high_low_range
    sell_volume = sell_ratio * df['Volume']

    # Delta = Buy - Sell
    delta = buy_volume - sell_volume

    return delta


def calculate_cvd(df: pd.DataFrame) -> pd.Series:
    """
    Cumulative Volume Delta - running sum of delta.

    Interpretation:
    - Rising CVD = buying pressure dominant
    - Falling CVD = selling pressure dominant
    - CVD divergence from price = exhaustion signal
    """
    delta = calculate_volume_delta(df)
    cvd = delta.cumsum()
    return cvd


def find_swing_points(df: pd.DataFrame, min_bars_each_side: int = 3, min_swing_pct: float = 2.0) -> dict:
    """
    Identify swing highs and lows for divergence detection.

    Parameters:
    - min_bars_each_side: Bars required on each side to qualify as swing
      (3 = swing must be highest/lowest of 7 bars: 3-1-3)
    - min_swing_pct: Minimum % move to qualify as significant swing

    Why these defaults:
    - 3 bars: Filters noise, but catches real swings in 3-month period
    - 2%: Significant enough to matter, not so high we miss smaller divergences

    Returns:
        {
            "highs": [{"index": i, "date": ..., "price": ..., "swing_pct": ...}, ...],
            "lows": [{"index": i, "date": ..., "price": ..., "swing_pct": ...}, ...]
        }
    """
    swings = {"highs": [], "lows": []}

    # Need at least min_bars_each_side * 2 + 1 bars
    if len(df) < min_bars_each_side * 2 + 1:
        return swings

    for i in range(min_bars_each_side, len(df) - min_bars_each_side):
        # Check for swing high
        window_high = df['High'].iloc[i-min_bars_each_side:i+min_bars_each_side+1]
        if df['High'].iloc[i] == window_high.max():
            # Verify minimum swing percentage
            nearby_low = df['Low'].iloc[i-min_bars_each_side:i+min_bars_each_side+1].min()
            swing_pct = ((df['High'].iloc[i] - nearby_low) / nearby_low * 100) if nearby_low > 0 else 0
            if swing_pct >= min_swing_pct:
                swings["highs"].append({
                    "index": i,
                    "date": df.index[i].strftime('%Y-%m-%d') if hasattr(df.index[i], 'strftime') else str(df.index[i]),
                    "price": float(df['High'].iloc[i]),
                    "swing_pct": round(swing_pct, 2)
                })

        # Check for swing low
        window_low = df['Low'].iloc[i-min_bars_each_side:i+min_bars_each_side+1]
        if df['Low'].iloc[i] == window_low.min():
            nearby_high = df['High'].iloc[i-min_bars_each_side:i+min_bars_each_side+1].max()
            swing_pct = ((nearby_high - df['Low'].iloc[i]) / df['Low'].iloc[i] * 100) if df['Low'].iloc[i] > 0 else 0
            if swing_pct >= min_swing_pct:
                swings["lows"].append({
                    "index": i,
                    "date": df.index[i].strftime('%Y-%m-%d') if hasattr(df.index[i], 'strftime') else str(df.index[i]),
                    "price": float(df['Low'].iloc[i]),
                    "swing_pct": round(swing_pct, 2)
                })

    return swings


def _calculate_divergence_strength(price_change_pct: float, cvd_change_pct: float) -> str:
    """Calculate strength of divergence based on magnitude."""
    # Larger divergence = stronger signal
    divergence_magnitude = abs(price_change_pct) + abs(cvd_change_pct)

    if divergence_magnitude > 15:
        return "STRONG"
    elif divergence_magnitude > 8:
        return "MODERATE"
    else:
        return "WEAK"


def detect_cvd_divergence(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    Detect CVD divergence from price action using explicit swing detection.

    BULLISH DIVERGENCE (Sellers Exhausted):
    - Price makes LOWER LOW
    - CVD makes HIGHER LOW
    - Meaning: Sellers pushing price down but volume delta improving

    BEARISH DIVERGENCE (Buyers Exhausted):
    - Price makes HIGHER HIGH
    - CVD makes LOWER HIGH
    - Meaning: Buyers pushing price up but volume delta weakening

    Returns:
        {
            "signal": "BULLISH_DIVERGENCE" | "BEARISH_DIVERGENCE" | "NONE",
            "price_swing": {"from": price1, "to": price2, "change_pct": X},
            "cvd_swing": {"from": cvd1, "to": cvd2, "change_pct": Y},
            "strength": "STRONG" | "MODERATE" | "WEAK",
            "bars_ago": N,
            "interpretation": "Sellers exhausted at support..."
        }
    """
    if len(df) < lookback + 10:
        return {"signal": "NONE", "interpretation": "Insufficient data for divergence detection"}

    # Calculate CVD
    cvd = calculate_cvd(df)

    # Find swing points
    swings = find_swing_points(df)

    # Filter to lookback period
    recent_lows = [s for s in swings["lows"] if s["index"] >= len(df) - lookback]
    recent_highs = [s for s in swings["highs"] if s["index"] >= len(df) - lookback]

    divergences = []

    # Check for bullish divergence (price lower low, CVD higher low)
    if len(recent_lows) >= 2:
        prev_low = recent_lows[-2]
        curr_low = recent_lows[-1]

        prev_cvd_low = float(cvd.iloc[prev_low["index"]])
        curr_cvd_low = float(cvd.iloc[curr_low["index"]])

        # Price makes lower low but CVD makes higher low
        if curr_low["price"] < prev_low["price"] and curr_cvd_low > prev_cvd_low:
            price_change_pct = ((curr_low["price"] - prev_low["price"]) / prev_low["price"]) * 100
            cvd_change_pct = ((curr_cvd_low - prev_cvd_low) / abs(prev_cvd_low)) * 100 if prev_cvd_low != 0 else 0

            divergences.append({
                "signal": "BULLISH_DIVERGENCE",
                "strength": _calculate_divergence_strength(price_change_pct, cvd_change_pct),
                "price_swing": {
                    "from": prev_low["price"],
                    "to": curr_low["price"],
                    "change_pct": round(price_change_pct, 2)
                },
                "cvd_swing": {
                    "from": prev_cvd_low,
                    "to": curr_cvd_low,
                    "change_pct": round(cvd_change_pct, 2)
                },
                "bars_ago": len(df) - curr_low["index"],
                "interpretation": "Sellers exhausted - price making lower lows but selling pressure decreasing. Potential reversal or bounce."
            })

    # Check for bearish divergence (price higher high, CVD lower high)
    if len(recent_highs) >= 2:
        prev_high = recent_highs[-2]
        curr_high = recent_highs[-1]

        prev_cvd_high = float(cvd.iloc[prev_high["index"]])
        curr_cvd_high = float(cvd.iloc[curr_high["index"]])

        # Price makes higher high but CVD makes lower high
        if curr_high["price"] > prev_high["price"] and curr_cvd_high < prev_cvd_high:
            price_change_pct = ((curr_high["price"] - prev_high["price"]) / prev_high["price"]) * 100
            cvd_change_pct = ((curr_cvd_high - prev_cvd_high) / abs(prev_cvd_high)) * 100 if prev_cvd_high != 0 else 0

            divergences.append({
                "signal": "BEARISH_DIVERGENCE",
                "strength": _calculate_divergence_strength(price_change_pct, cvd_change_pct),
                "price_swing": {
                    "from": prev_high["price"],
                    "to": curr_high["price"],
                    "change_pct": round(price_change_pct, 2)
                },
                "cvd_swing": {
                    "from": prev_cvd_high,
                    "to": curr_cvd_high,
                    "change_pct": round(cvd_change_pct, 2)
                },
                "bars_ago": len(df) - curr_high["index"],
                "interpretation": "Buyers exhausted - price making higher highs but buying pressure decreasing. Potential reversal or pullback."
            })

    # Return most recent divergence if multiple found
    if divergences:
        return min(divergences, key=lambda x: x["bars_ago"])

    return {"signal": "NONE", "interpretation": "No divergence detected in recent price action"}


def analyze_cvd(ticker: str, period: str = "3mo") -> dict:
    """
    Comprehensive CVD (Cumulative Volume Delta) analysis.

    This is the core of volumetric liquidity sequencing - understanding
    whether buyers or sellers are in control at the order flow level.

    Args:
        ticker: Stock ticker symbol
        period: Historical period to analyze

    Returns:
        Dictionary containing:
        - current_cvd: Latest CVD value
        - cvd_trend: RISING / FALLING / FLAT
        - delta_bars: Last 5 bars with delta values
        - divergence: Divergence detection result
        - cvd_slope: Normalized slope for trend detection
    """
    try:
        df = _get_price_history(ticker, period)

        if df.empty or len(df) < 20:
            return {"error": f"Insufficient data for {ticker}"}

        # Calculate CVD
        delta = calculate_volume_delta(df)
        cvd = delta.cumsum()

        # Current values
        current_cvd = float(cvd.iloc[-1])
        current_delta = float(delta.iloc[-1])

        # CVD trend (20-day slope normalized)
        cvd_20d = cvd.tail(20)
        if len(cvd_20d) >= 20:
            x = np.arange(len(cvd_20d))
            slope, _ = np.polyfit(x, cvd_20d.values, 1)
            # Normalize by average CVD magnitude
            avg_cvd = abs(cvd_20d).mean()
            normalized_slope = slope / avg_cvd if avg_cvd > 0 else 0
        else:
            normalized_slope = 0

        # Determine trend
        if normalized_slope > 0.02:
            cvd_trend = "RISING"
            trend_interpretation = "Buying pressure dominant - accumulation"
        elif normalized_slope < -0.02:
            cvd_trend = "FALLING"
            trend_interpretation = "Selling pressure dominant - distribution"
        else:
            cvd_trend = "FLAT"
            trend_interpretation = "Balanced buying/selling pressure"

        # Delta for last 5 bars
        delta_bars = []
        for i in range(-5, 0):
            if abs(i) <= len(df):
                delta_bars.append({
                    "date": df.index[i].strftime('%Y-%m-%d') if hasattr(df.index[i], 'strftime') else str(df.index[i]),
                    "delta": round(float(delta.iloc[i]), 0),
                    "cumulative": round(float(cvd.iloc[i]), 0),
                    "price": round(float(df['Close'].iloc[i]), 2),
                    "interpretation": "Buyers" if delta.iloc[i] > 0 else "Sellers"
                })

        # Detect divergence
        divergence = detect_cvd_divergence(df)

        # Overall CVD assessment
        if divergence["signal"] == "BULLISH_DIVERGENCE":
            assessment = f"BULLISH - {divergence['strength']} divergence detected (sellers exhausted)"
        elif divergence["signal"] == "BEARISH_DIVERGENCE":
            assessment = f"BEARISH - {divergence['strength']} divergence detected (buyers exhausted)"
        elif cvd_trend == "RISING":
            assessment = "BULLISH - Accumulation in progress"
        elif cvd_trend == "FALLING":
            assessment = "BEARISH - Distribution in progress"
        else:
            assessment = "NEUTRAL - No clear directional pressure"

        return {
            "ticker": ticker,
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "current_cvd": round(current_cvd, 0),
            "current_delta": round(current_delta, 0),
            "cvd_trend": cvd_trend,
            "cvd_slope_20d": round(normalized_slope, 4),
            "trend_interpretation": trend_interpretation,
            "delta_bars": delta_bars,
            "divergence": divergence,
            "assessment": assessment,
            "methodology_note": "CVD approximated from OHLCV data. For precise order flow, tick data required."
        }

    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def calculate_multi_vwap(ticker: str, period: str = "3mo", trading_style: str = "swing") -> dict:
    """
    Calculate and compare multiple VWAP anchors simultaneously.

    For swing trading (multi-week holds), we focus on:
    - Rolling 20-day VWAP (PRIMARY)
    - Anchored VWAP from last significant swing (SECONDARY)
    - Skip session VWAP (not relevant for swing timeframe)

    For day trading, all three are calculated.

    Standard Deviation Bands:
    - 1σ: Normal trading range
    - 2σ: Extended - potential mean reversion

    Args:
        ticker: Stock ticker symbol
        period: Historical period
        trading_style: "swing" or "day"

    Returns:
        Multi-VWAP synthesis with alignment and sustainability assessment
    """
    try:
        df = _get_price_history(ticker, period)

        if df.empty or len(df) < 20:
            return {"error": f"Insufficient data for {ticker}"}

        current_price = float(df['Close'].iloc[-1])

        # Calculate Typical Price
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['PV'] = df['Typical_Price'] * df['Volume']

        # Rolling 20-day VWAP (PRIMARY for swing trading)
        df['Rolling_VWAP'] = (
            df['PV'].rolling(window=20).sum() /
            df['Volume'].rolling(window=20).sum()
        )
        rolling_vwap = float(df['Rolling_VWAP'].iloc[-1])

        # Calculate standard deviation for rolling VWAP
        rolling_std = float(df['Typical_Price'].tail(20).std())

        rolling_bands = {
            "vwap": round(rolling_vwap, 2),
            "upper_1sigma": round(rolling_vwap + rolling_std, 2),
            "upper_2sigma": round(rolling_vwap + 2 * rolling_std, 2),
            "lower_1sigma": round(rolling_vwap - rolling_std, 2),
            "lower_2sigma": round(rolling_vwap - 2 * rolling_std, 2),
            "std": round(rolling_std, 2)
        }

        # Anchored VWAP from period start
        df['Anchored_VWAP'] = df['PV'].cumsum() / df['Volume'].cumsum()
        anchored_vwap = float(df['Anchored_VWAP'].iloc[-1])
        anchored_std = float(df['Typical_Price'].std())

        anchored_bands = {
            "vwap": round(anchored_vwap, 2),
            "upper_1sigma": round(anchored_vwap + anchored_std, 2),
            "upper_2sigma": round(anchored_vwap + 2 * anchored_std, 2),
            "lower_1sigma": round(anchored_vwap - anchored_std, 2),
            "lower_2sigma": round(anchored_vwap - 2 * anchored_std, 2),
            "std": round(anchored_std, 2)
        }

        # Position vs each VWAP
        def get_position(price, bands):
            if price > bands["upper_2sigma"]:
                return "EXTREME_ABOVE"
            elif price > bands["upper_1sigma"]:
                return "EXTENDED_ABOVE"
            elif price > bands["vwap"]:
                return "ABOVE"
            elif price < bands["lower_2sigma"]:
                return "EXTREME_BELOW"
            elif price < bands["lower_1sigma"]:
                return "EXTENDED_BELOW"
            else:
                return "BELOW"

        positions = {
            "rolling": get_position(current_price, rolling_bands),
            "anchored": get_position(current_price, anchored_bands)
        }

        # Calculate alignment
        above_count = sum(1 for p in positions.values() if "ABOVE" in p)
        below_count = sum(1 for p in positions.values() if "BELOW" in p)
        extreme_count = sum(1 for p in positions.values() if "EXTREME" in p)

        if above_count == 2:
            alignment = "STRONG_BULLISH"
        elif below_count == 2:
            alignment = "STRONG_BEARISH"
        elif above_count >= 1:
            alignment = "BULLISH"
        elif below_count >= 1:
            alignment = "BEARISH"
        else:
            alignment = "MIXED"

        # Sustainability assessment
        extreme_extension = extreme_count >= 1
        if extreme_count >= 2:
            sustainability = "UNSUSTAINABLE"
            mean_reversion_target = rolling_vwap
        elif extreme_count == 1:
            sustainability = "EXTENDED"
            mean_reversion_target = rolling_vwap
        else:
            sustainability = "SUSTAINABLE"
            mean_reversion_target = None

        # VWAP distance percentages
        rolling_distance_pct = ((current_price - rolling_vwap) / rolling_vwap) * 100
        anchored_distance_pct = ((current_price - anchored_vwap) / anchored_vwap) * 100

        # Sigma distance (how many std devs from VWAP)
        rolling_sigma = (current_price - rolling_vwap) / rolling_std if rolling_std > 0 else 0

        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "trading_style": trading_style,
            "rolling_vwap": rolling_bands,
            "anchored_vwap": anchored_bands,
            "positions": positions,
            "alignment": alignment,
            "sustainability": sustainability,
            "extreme_extension": extreme_extension,
            "mean_reversion_target": round(mean_reversion_target, 2) if mean_reversion_target else None,
            "distances": {
                "rolling_pct": round(rolling_distance_pct, 2),
                "anchored_pct": round(anchored_distance_pct, 2),
                "sigma_from_rolling": round(rolling_sigma, 2)
            },
            "interpretation": f"Price is {alignment} vs VWAPs. Move is {sustainability}."
        }

    except Exception as e:
        return {"error": str(e), "ticker": ticker}


# ============================================================================
# EXHAUSTION SCORE FUNCTIONS (Phase 2 of Volumetric Liquidity Enhancement)
# ============================================================================

def detect_rsi_divergence(df: pd.DataFrame, rsi_period: int = 14, lookback: int = 20) -> dict:
    """
    Detect RSI divergence from price action.

    BULLISH DIVERGENCE:
    - Price makes LOWER LOW
    - RSI makes HIGHER LOW
    - Meaning: Momentum improving despite price decline

    BEARISH DIVERGENCE:
    - Price makes HIGHER HIGH
    - RSI makes LOWER HIGH
    - Meaning: Momentum weakening despite price rise

    Returns:
        {
            "signal": "BULLISH_DIVERGENCE" | "BEARISH_DIVERGENCE" | "NONE",
            "strength": "STRONG" | "MODERATE" | "WEAK",
            "rsi_current": XX.X,
            "interpretation": "..."
        }
    """
    if len(df) < rsi_period + lookback:
        return {"signal": "NONE", "strength": "NONE", "rsi_current": 50.0, "interpretation": "Insufficient data"}

    # Calculate RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=rsi_period).mean()
    avg_loss = loss.rolling(window=rsi_period).mean()

    rs = avg_gain / avg_loss.replace(0, 0.0001)
    rsi = 100 - (100 / (1 + rs))

    current_rsi = float(rsi.iloc[-1])

    # Get price and RSI swings in lookback period
    recent_df = df.tail(lookback)
    recent_rsi = rsi.tail(lookback)

    # Find swing lows and highs in price
    price_swings = find_swing_points(recent_df, min_bars_each_side=2, min_swing_pct=1.0)

    # Check for bullish divergence (price lower low, RSI higher low)
    if len(price_swings["lows"]) >= 2:
        prev_low = price_swings["lows"][-2]
        curr_low = price_swings["lows"][-1]

        # Indices are relative to recent_df/recent_rsi slice, use directly
        try:
            prev_rsi = float(recent_rsi.iloc[prev_low["index"]])
            curr_rsi_at_low = float(recent_rsi.iloc[curr_low["index"]])
        except (IndexError, KeyError):
            prev_rsi = float(recent_rsi.iloc[-1])
            curr_rsi_at_low = float(recent_rsi.iloc[-1])

        if curr_low["price"] < prev_low["price"] and curr_rsi_at_low > prev_rsi:
            strength = "STRONG" if (curr_rsi_at_low - prev_rsi) > 10 else "MODERATE" if (curr_rsi_at_low - prev_rsi) > 5 else "WEAK"
            return {
                "signal": "BULLISH_DIVERGENCE",
                "strength": strength,
                "rsi_current": round(current_rsi, 1),
                "interpretation": "Price making lower lows but RSI improving - momentum strengthening"
            }

    # Check for bearish divergence (price higher high, RSI lower high)
    if len(price_swings["highs"]) >= 2:
        prev_high = price_swings["highs"][-2]
        curr_high = price_swings["highs"][-1]

        # Indices are relative to recent_df/recent_rsi slice, use directly
        try:
            prev_rsi = float(recent_rsi.iloc[prev_high["index"]])
            curr_rsi_at_high = float(recent_rsi.iloc[curr_high["index"]])
        except (IndexError, KeyError):
            prev_rsi = float(recent_rsi.iloc[-1])
            curr_rsi_at_high = float(recent_rsi.iloc[-1])

        if curr_high["price"] > prev_high["price"] and curr_rsi_at_high < prev_rsi:
            strength = "STRONG" if (prev_rsi - curr_rsi_at_high) > 10 else "MODERATE" if (prev_rsi - curr_rsi_at_high) > 5 else "WEAK"
            return {
                "signal": "BEARISH_DIVERGENCE",
                "strength": strength,
                "rsi_current": round(current_rsi, 1),
                "interpretation": "Price making higher highs but RSI weakening - momentum fading"
            }

    return {
        "signal": "NONE",
        "strength": "NONE",
        "rsi_current": round(current_rsi, 1),
        "interpretation": "No RSI divergence detected"
    }


def detect_volume_decline(df: pd.DataFrame, lookback: int = 10) -> dict:
    """
    Detect declining volume trend (sign of exhaustion).

    Volume declining during a price move indicates:
    - Decreasing participation
    - Potential exhaustion of the move
    - Possible reversal ahead

    Returns:
        {
            "declining": bool,
            "days_declining": int,
            "volume_trend_pct": float,  # Negative = declining
            "interpretation": "..."
        }
    """
    if 'Volume' not in df.columns or len(df) < lookback:
        return {"declining": False, "days_declining": 0, "volume_trend_pct": 0.0, "interpretation": "Insufficient data"}

    volumes = df['Volume'].tail(lookback)

    # Count consecutive declining days from most recent
    days_declining = 0
    for i in range(len(volumes) - 1, 0, -1):
        if volumes.iloc[i] < volumes.iloc[i - 1]:
            days_declining += 1
        else:
            break

    # Calculate volume trend (slope)
    x = np.arange(len(volumes))
    slope, _ = np.polyfit(x, volumes.values, 1)
    avg_volume = volumes.mean()
    trend_pct = (slope * lookback / avg_volume) * 100 if avg_volume > 0 else 0

    declining = trend_pct < -10  # 10% decline threshold

    if declining and days_declining >= 5:
        interpretation = f"Strong volume decline ({days_declining} consecutive days) - exhaustion signal"
    elif declining:
        interpretation = "Moderate volume decline - watch for exhaustion"
    else:
        interpretation = "Volume stable or increasing"

    return {
        "declining": declining,
        "days_declining": days_declining,
        "volume_trend_pct": round(trend_pct, 1),
        "interpretation": interpretation
    }


def count_trend_days(df: pd.DataFrame, direction: str = "LONG", lookback: int = 10) -> int:
    """
    Count trend days in a rolling window to detect trend extension.

    For LONG positions: Count up days (close > close[-1]) in last N days
    For SHORT positions: Count down days (close < close[-1]) in last N days

    IMPROVED: Uses rolling window instead of breaking on first opposite day.
    This gives more realistic exhaustion readings (e.g., 7/10 up days = extended).

    Returns:
        Number of trend days in the lookback window
    """
    if df is None or len(df) < 2:
        return 0

    closes = df['Close'].tail(lookback + 1).values
    count = 0

    if direction.upper() == "LONG":
        # Count up days in the window
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                count += 1
    else:  # SHORT
        # Count down days in the window
        for i in range(1, len(closes)):
            if closes[i] < closes[i - 1]:
                count += 1

    return count


def calculate_exhaustion_score(
    ticker: str,
    direction: str | None = None,
    period: str = "3mo"
) -> dict:
    """
    Composite exhaustion score (0-100) combining multiple signals.

    NOW DIRECTION-INDEPENDENT: Calculates exhaustion for BOTH directions
    and returns which direction is fresher (less exhausted).

    PURPOSE: Detect when a move is running out of steam.

    For LONG positions:
    - HIGH exhaustion score (>70) = Move may be ending, consider TRIM
    - LOW exhaustion score (<30) = Move has room to run, HOLD

    For SHORT candidates:
    - HIGH long_exhaustion = Good SHORT entry (buyers exhausted)
    - HIGH short_exhaustion = Avoid SHORT (sellers exhausted)

    Scoring Components (100 points total per direction):
    - CVD Divergence: 20 pts
    - RSI Divergence: 20 pts
    - Trend Day Count: 25 pts
    - VWAP Extension: 15 pts
    - Volume Decline: 20 pts

    Returns:
        {
            "fresh_direction": "LONG" | "SHORT" | "NEUTRAL",
            "long_exhaustion": {"score": int, "level": str, "action": str, "components": {}},
            "short_exhaustion": {"score": int, "level": str, "action": str, "components": {}},
            "interpretation": "..."
        }
    """
    try:
        df = _get_price_history(ticker, period)

        if df.empty or len(df) < 30:
            return {"error": f"Insufficient data for {ticker}", "score": 0, "level": "UNKNOWN"}

        # Get divergence signals (direction-independent)
        cvd_result = detect_cvd_divergence(df)
        rsi_result = detect_rsi_divergence(df)
        vol_result = detect_volume_decline(df)

        # Get VWAP extension (direction-specific)
        multi_vwap = calculate_multi_vwap(ticker, period, "swing")
        sigma_distance = 0
        if not multi_vwap.get("error"):
            sigma_distance = multi_vwap.get("distances", {}).get("sigma_from_rolling", 0)

        # Helper function to convert strength to points
        def strength_to_pts(strength, max_pts=20):
            if strength == "STRONG":
                return max_pts
            elif strength == "MODERATE":
                return int(max_pts * 0.65)
            elif strength == "WEAK":
                return int(max_pts * 0.35)
            return 0

        def score_to_level(score):
            if score >= 70:
                return "HIGH_EXHAUSTION"
            elif score >= 50:
                return "MODERATE_EXHAUSTION"
            elif score >= 30:
                return "LOW_EXHAUSTION"
            return "NO_EXHAUSTION"

        def score_to_action(score):
            if score >= 80:
                return "EXCLUDE"
            elif score >= 70:
                return "REDUCE_SIZE"
            elif score >= 60:
                return "FLAG"
            return "PROCEED"

        # ========== CALCULATE LONG EXHAUSTION ==========
        long_score = 0
        long_components = {}

        # Get current RSI for baseline scoring
        rsi_current = rsi_result.get("rsi_current", 50)

        # CVD: Bearish divergence = LONG exhausted
        if cvd_result["signal"] == "BEARISH_DIVERGENCE":
            pts = strength_to_pts(cvd_result["strength"], 20)
            long_score += pts
            long_components["cvd_divergence"] = {"points": pts, "signal": "BEARISH", "note": "Buyers exhausted"}
        else:
            long_components["cvd_divergence"] = {"points": 0, "signal": "NONE"}

        # RSI: Bearish divergence = LONG exhausted
        # IMPROVED: Also use RSI LEVEL as baseline when no divergence
        if rsi_result["signal"] == "BEARISH_DIVERGENCE":
            pts = strength_to_pts(rsi_result["strength"], 20)
            long_score += pts
            long_components["rsi_divergence"] = {"points": pts, "signal": "BEARISH", "rsi": rsi_current}
        else:
            # RSI BASELINE: High RSI indicates overbought (LONG exhaustion)
            rsi_baseline_pts = 0
            if rsi_current >= 80:
                rsi_baseline_pts = 15  # Very overbought
            elif rsi_current >= 70:
                rsi_baseline_pts = 10  # Overbought
            elif rsi_current >= 60:
                rsi_baseline_pts = 5   # Extended
            long_score += rsi_baseline_pts
            long_components["rsi_divergence"] = {
                "points": rsi_baseline_pts,
                "signal": "LEVEL_BASED",
                "rsi": rsi_current,
                "note": f"RSI {rsi_current:.0f} - {'overbought' if rsi_current >= 70 else 'extended' if rsi_current >= 60 else 'neutral'}"
            }

        # Trend days: Count UP days in rolling 10-day window for LONG exhaustion
        up_trend_days = count_trend_days(df, "LONG", lookback=10)
        up_trend_pts = 0
        # Scoring: Out of 10 days, how many were up?
        if up_trend_days >= 8:      # 80%+ up days
            up_trend_pts = 25
        elif up_trend_days >= 7:    # 70% up days
            up_trend_pts = 18
        elif up_trend_days >= 6:    # 60% up days
            up_trend_pts = 12
        elif up_trend_days >= 5:    # 50% up days
            up_trend_pts = 6
        long_score += up_trend_pts
        long_components["trend_days"] = {"points": up_trend_pts, "count": up_trend_days, "note": f"{up_trend_days}/10 up days"}

        # VWAP Extension: Positive sigma = LONG extended
        long_vwap_pts = 0
        if sigma_distance >= 2.0:
            long_vwap_pts = 15
        elif sigma_distance >= 1.5:
            long_vwap_pts = 10
        elif sigma_distance >= 1.0:
            long_vwap_pts = 5
        long_score += long_vwap_pts
        long_components["vwap_extension"] = {"points": long_vwap_pts, "sigma": round(sigma_distance, 2)}

        # Volume decline on up move = LONG exhausted
        long_vol_pts = 0
        current_trend = "UP" if df['Close'].iloc[-1] > df['Close'].iloc[-5] else "DOWN"
        if vol_result["declining"] and current_trend == "UP":
            if vol_result["days_declining"] >= 5:
                long_vol_pts = 20
            elif vol_result["days_declining"] >= 3:
                long_vol_pts = 12
            else:
                long_vol_pts = 6
        long_score += long_vol_pts
        long_components["volume_decline"] = {"points": long_vol_pts, "days": vol_result["days_declining"]}

        # ========== CALCULATE SHORT EXHAUSTION ==========
        short_score = 0
        short_components = {}

        # CVD: Bullish divergence = SHORT exhausted (sellers gave up)
        if cvd_result["signal"] == "BULLISH_DIVERGENCE":
            pts = strength_to_pts(cvd_result["strength"], 20)
            short_score += pts
            short_components["cvd_divergence"] = {"points": pts, "signal": "BULLISH", "note": "Sellers exhausted"}
        else:
            short_components["cvd_divergence"] = {"points": 0, "signal": "NONE"}

        # RSI: Bullish divergence = SHORT exhausted
        # IMPROVED: Also use RSI LEVEL as baseline when no divergence
        if rsi_result["signal"] == "BULLISH_DIVERGENCE":
            pts = strength_to_pts(rsi_result["strength"], 20)
            short_score += pts
            short_components["rsi_divergence"] = {"points": pts, "signal": "BULLISH", "rsi": rsi_current}
        else:
            # RSI BASELINE: Low RSI indicates oversold (SHORT exhaustion)
            rsi_baseline_pts = 0
            if rsi_current <= 20:
                rsi_baseline_pts = 15  # Very oversold
            elif rsi_current <= 30:
                rsi_baseline_pts = 10  # Oversold
            elif rsi_current <= 40:
                rsi_baseline_pts = 5   # Extended down
            short_score += rsi_baseline_pts
            short_components["rsi_divergence"] = {
                "points": rsi_baseline_pts,
                "signal": "LEVEL_BASED",
                "rsi": rsi_current,
                "note": f"RSI {rsi_current:.0f} - {'oversold' if rsi_current <= 30 else 'extended down' if rsi_current <= 40 else 'neutral'}"
            }

        # Trend days: Count DOWN days in rolling 10-day window for SHORT exhaustion
        down_trend_days = count_trend_days(df, "SHORT", lookback=10)
        down_trend_pts = 0
        # Scoring: Out of 10 days, how many were down?
        if down_trend_days >= 8:    # 80%+ down days
            down_trend_pts = 25
        elif down_trend_days >= 7:  # 70% down days
            down_trend_pts = 18
        elif down_trend_days >= 6:  # 60% down days
            down_trend_pts = 12
        elif down_trend_days >= 5:  # 50% down days
            down_trend_pts = 6
        short_score += down_trend_pts
        short_components["trend_days"] = {"points": down_trend_pts, "count": down_trend_days, "note": f"{down_trend_days}/10 down days"}

        # VWAP Extension: Negative sigma = SHORT extended
        short_vwap_pts = 0
        if sigma_distance <= -2.0:
            short_vwap_pts = 15
        elif sigma_distance <= -1.5:
            short_vwap_pts = 10
        elif sigma_distance <= -1.0:
            short_vwap_pts = 5
        short_score += short_vwap_pts
        short_components["vwap_extension"] = {"points": short_vwap_pts, "sigma": round(sigma_distance, 2)}

        # Volume decline on down move = SHORT exhausted
        short_vol_pts = 0
        if vol_result["declining"] and current_trend == "DOWN":
            if vol_result["days_declining"] >= 5:
                short_vol_pts = 20
            elif vol_result["days_declining"] >= 3:
                short_vol_pts = 12
            else:
                short_vol_pts = 6
        short_score += short_vol_pts
        short_components["volume_decline"] = {"points": short_vol_pts, "days": vol_result["days_declining"]}

        # ========== DETERMINE FRESH DIRECTION ==========
        if long_score < short_score - 20:
            fresh_direction = "LONG"
        elif short_score < long_score - 20:
            fresh_direction = "SHORT"
        else:
            fresh_direction = "NEUTRAL"

        # Build result
        result = {
            "ticker": ticker,
            "fresh_direction": fresh_direction,
            "long_exhaustion": {
                "score": long_score,
                "level": score_to_level(long_score),
                "action": score_to_action(long_score),
                "components": long_components
            },
            "short_exhaustion": {
                "score": short_score,
                "level": score_to_level(short_score),
                "action": score_to_action(short_score),
                "components": short_components
            },
            "interpretation": (
                f"LONG exhaustion: {long_score}/100 ({score_to_level(long_score)}). "
                f"SHORT exhaustion: {short_score}/100 ({score_to_level(short_score)}). "
                f"Fresh direction: {fresh_direction}."
            ),
            "component_weights": {
                "cvd_divergence": 20,
                "rsi_divergence": 20,
                "trend_days": 25,
                "vwap_extension": 15,
                "volume_decline": 20
            }
        }

        # For backward compatibility, if direction was specified, also include legacy fields
        if direction:
            direction = direction.upper()
            if direction == "LONG":
                result["score"] = long_score
                result["level"] = score_to_level(long_score)
                result["suggested_action"] = score_to_action(long_score)
                result["direction"] = "LONG"
            else:
                result["score"] = short_score
                result["level"] = score_to_level(short_score)
                result["suggested_action"] = score_to_action(short_score)
                result["direction"] = "SHORT"

        return result

    except Exception as e:
        return {"error": str(e), "ticker": ticker, "score": 0, "level": "ERROR"}


# ============================================================================
# CVD + AL BROOKS INTEGRATION (Phase 3 of Volumetric Liquidity Enhancement)
# ============================================================================

def enhance_brooks_with_cvd(
    brooks_pattern: str,
    direction: str,
    cvd_analysis: dict,
    base_probability: float = 50.0
) -> dict:
    """
    Enhance Al Brooks pattern probability based on CVD confirmation.

    Brooks teaches: Volume confirms. CVD is directional volume.

    Pattern-Specific Adjustments:
    - Wedge Reversal: CVD divergence at apex = higher reversal probability
    - Breakout: Positive delta on breakout bar = confirmed breakout
    - Bull Flag Pullback: Declining CVD on pullback = healthy consolidation
    - Failed Breakout: Delta spike then reversal = trap confirmation
    - Measured Move: CVD rising throughout = strong continuation

    Args:
        brooks_pattern: Al Brooks pattern name (e.g., 'high_2', 'wedge_reversal')
        direction: Trade direction ('LONG' or 'SHORT')
        cvd_analysis: Output from analyze_cvd() or detect_cvd_divergence()
        base_probability: Starting probability from Al Brooks analysis

    Returns:
        {
            "adjusted_probability": float,
            "adjustment": int,
            "confirmation": "STRONG" | "MODERATE" | "WEAK" | "NONE" | "NEGATIVE",
            "explanation": str
        }
    """
    adjustment = 0
    explanation = ""
    confirmation = "NONE"

    # Normalize inputs
    pattern = brooks_pattern.lower() if brooks_pattern else ""
    direction = direction.upper() if direction else "LONG"

    # Get CVD data
    divergence_signal = cvd_analysis.get("divergence", {}).get("signal", "NONE")
    divergence_strength = cvd_analysis.get("divergence", {}).get("strength", "NONE")
    cvd_trend = cvd_analysis.get("cvd_trend", "FLAT")
    current_delta = cvd_analysis.get("current_delta", 0)

    # Get last few deltas for recent trend
    delta_bars = cvd_analysis.get("delta_bars", [])
    recent_deltas = [bar.get("delta", 0) for bar in delta_bars[-3:]] if delta_bars else [0]
    avg_recent_delta = sum(recent_deltas) / len(recent_deltas) if recent_deltas else 0

    # -------------------------------------------------------------------------
    # Pattern-Specific CVD Enhancements
    # -------------------------------------------------------------------------

    # 1. WEDGE REVERSAL PATTERNS
    if pattern in ['wedge_reversal', 'wedge_top', 'double_bottom', 'double_top']:
        # CVD divergence at reversal point = STRONG confirmation
        if direction == "LONG" and divergence_signal == "BULLISH_DIVERGENCE":
            if divergence_strength == "STRONG":
                adjustment = +10
                confirmation = "STRONG"
                explanation = "CVD bullish divergence confirms wedge reversal (sellers exhausted)"
            elif divergence_strength == "MODERATE":
                adjustment = +6
                confirmation = "MODERATE"
                explanation = "CVD moderate divergence supports reversal"
            else:
                adjustment = +3
                confirmation = "WEAK"
                explanation = "CVD weak divergence - partial confirmation"
        elif direction == "SHORT" and divergence_signal == "BEARISH_DIVERGENCE":
            if divergence_strength == "STRONG":
                adjustment = +10
                confirmation = "STRONG"
                explanation = "CVD bearish divergence confirms top reversal (buyers exhausted)"
            elif divergence_strength == "MODERATE":
                adjustment = +6
                confirmation = "MODERATE"
                explanation = "CVD moderate divergence supports top"
            else:
                adjustment = +3
                confirmation = "WEAK"
                explanation = "CVD weak divergence - partial confirmation"
        elif divergence_signal != "NONE":
            # Divergence against trade direction
            adjustment = -8
            confirmation = "NEGATIVE"
            explanation = f"CVD divergence AGAINST trade direction - caution"

    # 2. BREAKOUT/BREAKDOWN PATTERNS
    elif pattern in ['breakout_pullback', 'breakdown_pullback', 'tight_trading_range_breakout']:
        # Positive delta on breakout = confirmed
        if direction == "LONG":
            if current_delta > 0 and avg_recent_delta > 0:
                adjustment = +8
                confirmation = "STRONG"
                explanation = "Positive CVD delta confirms breakout (buying pressure)"
            elif current_delta > 0:
                adjustment = +4
                confirmation = "MODERATE"
                explanation = "Current delta positive - partial confirmation"
            elif current_delta < 0:
                adjustment = -5
                confirmation = "NEGATIVE"
                explanation = "Negative delta on breakout - likely failed breakout"
        else:  # SHORT
            if current_delta < 0 and avg_recent_delta < 0:
                adjustment = +8
                confirmation = "STRONG"
                explanation = "Negative CVD delta confirms breakdown (selling pressure)"
            elif current_delta < 0:
                adjustment = +4
                confirmation = "MODERATE"
                explanation = "Current delta negative - partial confirmation"
            elif current_delta > 0:
                adjustment = -5
                confirmation = "NEGATIVE"
                explanation = "Positive delta on breakdown - likely failed breakdown"

    # 3. PULLBACK PATTERNS (High 1/2, Low 1/2, Bull/Bear Flags)
    elif pattern in ['high_1', 'high_2', 'low_1', 'low_2', 'higher_low', 'lower_high']:
        # Healthy pullback has declining volume/CVD
        if direction == "LONG":
            if cvd_trend == "FALLING" and current_delta < 0:
                adjustment = +5
                confirmation = "MODERATE"
                explanation = "Declining CVD on pullback - healthy consolidation"
            elif cvd_trend == "RISING" and current_delta > 0:
                adjustment = +3
                confirmation = "WEAK"
                explanation = "CVD still rising - aggressive buyers"
            elif cvd_trend == "FALLING" and avg_recent_delta < 0:
                adjustment = +2
                confirmation = "WEAK"
                explanation = "Recent CVD declining - consolidation in progress"
        else:  # SHORT
            if cvd_trend == "RISING" and current_delta > 0:
                adjustment = +5
                confirmation = "MODERATE"
                explanation = "Rising CVD on bounce - weak rally (healthy for short)"
            elif cvd_trend == "FALLING" and current_delta < 0:
                adjustment = +3
                confirmation = "WEAK"
                explanation = "CVD falling - confirms selling pressure"

    # 4. FAILED BREAKOUT/BREAKDOWN (Traps)
    elif pattern in ['failed_breakout', 'failed_breakdown']:
        # Delta spike then reversal = trap confirmation
        if len(recent_deltas) >= 2:
            delta_reversal = (recent_deltas[0] > 0 and recent_deltas[-1] < 0) or \
                           (recent_deltas[0] < 0 and recent_deltas[-1] > 0)
            if delta_reversal:
                adjustment = +8
                confirmation = "STRONG"
                explanation = "CVD delta reversal confirms trap pattern"
            else:
                adjustment = +3
                confirmation = "WEAK"
                explanation = "No clear CVD reversal - trap less reliable"

    # 5. CLIMACTIC/EXHAUSTION PATTERNS
    elif pattern in ['climactic_exhaustion', 'high_3', 'high_4', 'low_3', 'low_4']:
        # Divergence = confirms exhaustion
        if direction == "LONG" and divergence_signal == "BULLISH_DIVERGENCE":
            adjustment = +7
            confirmation = "MODERATE"
            explanation = "CVD divergence confirms selling exhaustion"
        elif direction == "SHORT" and divergence_signal == "BEARISH_DIVERGENCE":
            adjustment = +7
            confirmation = "MODERATE"
            explanation = "CVD divergence confirms buying exhaustion"
        # CVD trend continuation = not yet exhausted
        elif (direction == "SHORT" and cvd_trend == "RISING") or \
             (direction == "LONG" and cvd_trend == "FALLING"):
            adjustment = -5
            confirmation = "NEGATIVE"
            explanation = "CVD trend not exhausted - wait for divergence"

    # 6. MEASURED MOVE / CONTINUATION
    elif pattern in ['ema_bounce', 'ema_rejection']:
        # CVD trending in direction = confirms continuation
        if direction == "LONG" and cvd_trend == "RISING":
            adjustment = +5
            confirmation = "MODERATE"
            explanation = "Rising CVD confirms bullish continuation"
        elif direction == "SHORT" and cvd_trend == "FALLING":
            adjustment = +5
            confirmation = "MODERATE"
            explanation = "Falling CVD confirms bearish continuation"
        elif cvd_trend == "FLAT":
            adjustment = 0
            confirmation = "NONE"
            explanation = "CVD neutral - no additional confirmation"
        else:
            adjustment = -3
            confirmation = "WEAK"
            explanation = "CVD trending against direction"

    # 7. DEFAULT - No specific pattern match
    else:
        # Generic CVD alignment check
        if direction == "LONG":
            if cvd_trend == "RISING":
                adjustment = +3
                confirmation = "WEAK"
                explanation = "CVD rising - general bullish confirmation"
            elif cvd_trend == "FALLING":
                adjustment = -2
                confirmation = "NEGATIVE"
                explanation = "CVD falling - general bearish pressure"
        else:  # SHORT
            if cvd_trend == "FALLING":
                adjustment = +3
                confirmation = "WEAK"
                explanation = "CVD falling - general bearish confirmation"
            elif cvd_trend == "RISING":
                adjustment = -2
                confirmation = "NEGATIVE"
                explanation = "CVD rising - general bullish pressure"

    # Calculate adjusted probability
    adjusted_probability = base_probability + adjustment
    adjusted_probability = max(20, min(80, adjusted_probability))  # Clamp to 20-80%

    return {
        "base_probability": round(base_probability, 1),
        "adjusted_probability": round(adjusted_probability, 1),
        "adjustment": adjustment,
        "confirmation": confirmation,
        "reason": explanation,  # Added for compatibility with test
        "explanation": explanation,
        "cvd_trend": cvd_trend,
        "divergence": divergence_signal,
        "pattern_analyzed": pattern
    }
