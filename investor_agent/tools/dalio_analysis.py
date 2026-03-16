"""Dalio Economic Machine Analysis — Standalone MCP Tool Module.

Implements Ray Dalio's "Price = Total Spending / Quantity Sold" principle
as standalone MCP tools. Reuses existing helpers from technical_analysis_bootstrap.py.

Tools:
    analyze_dalio_economic_machine  — Full Dalio analysis for a ticker
    get_macro_regime                — Macro regime detection (yield curve, breadth, VIX, credit)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core implementation functions (can be imported by other modules)
# ---------------------------------------------------------------------------

def analyze_dalio_economic_machine_impl(
    ticker: str,
    period: str = "3mo",
    lookback_days: int = 20,
    include_profile: bool = True,
) -> dict[str, Any]:
    """
    Analyze stock using Ray Dalio's Economic Machine principle.

    Core insight: Price = Total Spending / Quantity Sold = VWAP

    Returns comprehensive dollar-volume analysis including Dalio Ratio,
    Dollar Volume Momentum, Spending Efficiency, Cumulative Dollar Flow,
    Dollar Volume Profile, Institutional Activity, Trend Sustainability.
    """
    from ..technical_analysis_bootstrap import (
        _interpret_dalio_ratio,
        _classify_dv_momentum,
        _interpret_spending_efficiency,
        _derive_efficiency_implication,
        _calculate_dollar_volume_profile,
        _detect_institutional_activity,
        _assess_trend_sustainability,
    )

    try:
        # Fetch OHLCV data
        data = yf.download(ticker, period=period, progress=False)
        if data is None or len(data) < lookback_days + 5:
            return {"error": f"Insufficient data for {ticker} (need {lookback_days + 5} bars, got {len(data) if data is not None else 0})"}

        # Flatten MultiIndex columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        current_price = float(data['Close'].iloc[-1])

        # --- Calculate VWAP ---
        data['Typical_Price'] = (data['High'] + data['Low'] + data['Close']) / 3
        data['Dollar_Volume'] = data['Typical_Price'] * data['Volume']

        # --- Dalio Ratio ---
        # Current period VWAP / Prior period VWAP
        recent = data.tail(lookback_days)
        prior = data.iloc[-(lookback_days * 2):-lookback_days] if len(data) >= lookback_days * 2 else data.head(lookback_days)

        recent_vwap = float(recent['Dollar_Volume'].sum() / recent['Volume'].sum()) if recent['Volume'].sum() > 0 else current_price
        prior_vwap = float(prior['Dollar_Volume'].sum() / prior['Volume'].sum()) if prior['Volume'].sum() > 0 else current_price

        dalio_ratio_current = recent_vwap / prior_vwap if prior_vwap > 0 else 1.0

        # 5d and 20d average ratios
        ratios_5d = []
        ratios_20d = []
        for i in range(min(20, len(data) - lookback_days)):
            idx = -(i + 1)
            if abs(idx) > len(data) - lookback_days:
                break
            window = data.iloc[max(0, len(data) + idx - lookback_days):len(data) + idx + 1]
            prev_window = data.iloc[max(0, len(data) + idx - lookback_days * 2):max(0, len(data) + idx - lookback_days + 1)]
            if len(window) > 0 and len(prev_window) > 0:
                w_vwap = float(window['Dollar_Volume'].sum() / window['Volume'].sum()) if window['Volume'].sum() > 0 else 0
                p_vwap = float(prev_window['Dollar_Volume'].sum() / prev_window['Volume'].sum()) if prev_window['Volume'].sum() > 0 else 0
                if p_vwap > 0:
                    r = w_vwap / p_vwap
                    ratios_20d.append(r)
                    if i < 5:
                        ratios_5d.append(r)

        dalio_5d_avg = float(np.mean(ratios_5d)) if ratios_5d else dalio_ratio_current
        dalio_20d_avg = float(np.mean(ratios_20d)) if ratios_20d else dalio_ratio_current

        # Trend direction of ratio
        if dalio_ratio_current > dalio_20d_avg * 1.01:
            ratio_trend = "INCREASING"
        elif dalio_ratio_current < dalio_20d_avg * 0.99:
            ratio_trend = "DECREASING"
        else:
            ratio_trend = "FLAT"

        interpretation = _interpret_dalio_ratio(dalio_ratio_current)

        # Strength
        deviation = abs(dalio_ratio_current - 1.0)
        if deviation > 0.05:
            strength = "STRONG"
        elif deviation > 0.02:
            strength = "MODERATE"
        else:
            strength = "WEAK"

        # --- Dollar Volume Analysis ---
        dv_today = float(data['Dollar_Volume'].iloc[-1])
        dv_5d_avg = float(data['Dollar_Volume'].tail(5).mean())
        dv_20d_avg = float(data['Dollar_Volume'].tail(20).mean())
        dv_50d_avg = float(data['Dollar_Volume'].tail(50).mean()) if len(data) >= 50 else dv_20d_avg

        dv_momentum = ((dv_today - dv_20d_avg) / dv_20d_avg * 100) if dv_20d_avg > 0 else 0
        dv_rel_50d = dv_today / dv_50d_avg if dv_50d_avg > 0 else 1.0

        momentum_class = _classify_dv_momentum(dv_momentum)

        # Percentile rank
        dv_series = data['Dollar_Volume'].tail(90)
        percentile = int((dv_series < dv_today).sum() / len(dv_series) * 100) if len(dv_series) > 0 else 50

        # --- Spending Efficiency ---
        price_change_pct = ((current_price - float(data['Close'].iloc[-2])) / float(data['Close'].iloc[-2]) * 100) if len(data) >= 2 else 0
        dv_change_pct = ((dv_today - dv_20d_avg) / dv_20d_avg * 100) if dv_20d_avg > 0 else 0
        spending_efficiency = price_change_pct / dv_change_pct if dv_change_pct != 0 else 0

        efficiency_interp = _interpret_spending_efficiency(spending_efficiency)

        # --- Cumulative Dollar Flow (CDF) ---
        data['Direction'] = np.sign(data['Close'] - data['Open'])
        data['Directional_DV'] = data['Dollar_Volume'] * data['Direction']

        cdf_5d = float(data['Directional_DV'].tail(5).sum())
        cdf_20d = float(data['Directional_DV'].tail(20).sum())
        cdf_total = float(data['Directional_DV'].sum())

        cdf_direction = "ACCUMULATION" if cdf_20d > 0 else "DISTRIBUTION"

        # --- Dollar Volume Profile ---
        profile = {}
        if include_profile:
            profile = _calculate_dollar_volume_profile(data, bins=20)

        poc_price = profile.get('point_of_control', current_price) if isinstance(profile, dict) else current_price

        # --- Institutional Activity ---
        high_dv_days = int((data['Dollar_Volume'].tail(20) > dv_20d_avg * 1.5).sum())
        institutional = _detect_institutional_activity(
            dv_momentum=dv_momentum,
            spending_efficiency=spending_efficiency,
            cdf_20d=cdf_20d,
            avg_dv_20d=dv_20d_avg,
            high_dv_days=high_dv_days,
        )

        # --- Trend Sustainability ---
        implication = _derive_efficiency_implication(spending_efficiency, cdf_20d)
        sustainability = _assess_trend_sustainability(
            dalio_ratio=dalio_ratio_current,
            dv_momentum=dv_momentum,
            spending_efficiency=spending_efficiency,
            cdf_20d=cdf_20d,
            current_price=current_price,
            poc_price=poc_price,
        )

        # --- Educational Lesson ---
        lesson = _generate_dalio_lesson(
            dalio_ratio=dalio_ratio_current,
            interpretation=interpretation,
            cdf_direction=cdf_direction,
            sustainability_score=sustainability.get('score', 50),
            institutional_detected=institutional.get('detected', False),
        )

        return {
            "ticker": ticker,
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "period": period,
            "current_price": round(current_price, 2),

            "dalio_ratio": {
                "current": round(dalio_ratio_current, 4),
                "5d_avg": round(dalio_5d_avg, 4),
                "20d_avg": round(dalio_20d_avg, 4),
                "interpretation": interpretation,
                "trend": ratio_trend,
                "strength": strength,
            },

            "dollar_volume": {
                "today": int(dv_today),
                "5d_avg": int(dv_5d_avg),
                "20d_avg": int(dv_20d_avg),
                "50d_avg": int(dv_50d_avg),
                "relative_to_20d": round(dv_today / dv_20d_avg, 2) if dv_20d_avg > 0 else 1.0,
                "relative_to_50d": round(dv_rel_50d, 2),
                "momentum": momentum_class,
                "percentile_90d": percentile,
            },

            "spending_efficiency": {
                "ratio": round(spending_efficiency, 4),
                "interpretation": efficiency_interp,
                "implication": implication,
            },

            "cumulative_dollar_flow": {
                "5d": int(cdf_5d),
                "20d": int(cdf_20d),
                "total": int(cdf_total),
                "direction": cdf_direction,
            },

            "dollar_volume_profile": profile if include_profile else {},

            "institutional_activity": institutional,

            "trend_sustainability": sustainability,

            "lesson": lesson,
        }

    except Exception as e:
        logger.error(f"Dalio analysis failed for {ticker}: {e}")
        return {"error": f"Analysis failed: {str(e)}", "ticker": ticker}


def get_macro_regime_impl(include_breadth: bool = False) -> dict[str, Any]:
    """
    Detect macro economic regime using market data (no FRED API needed).

    Uses yfinance for:
    - Yield curve: ^TNX (10Y) - ^IRX (3mo)
    - VIX regime: ^VIX level
    - Credit cycle: HYG/LQD ratio
    - Market breadth (optional): % of top holdings above 200 SMA
    """
    try:
        result = {
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "regime": "UNKNOWN",
            "yield_curve": {},
            "vix_regime": {},
            "credit_cycle": {},
            "market_breadth": {},
        }

        # --- Yield Curve ---
        try:
            tnx = yf.download("^TNX", period="3mo", progress=False)
            irx = yf.download("^IRX", period="3mo", progress=False)

            if isinstance(tnx.columns, pd.MultiIndex):
                tnx.columns = tnx.columns.get_level_values(0)
            if isinstance(irx.columns, pd.MultiIndex):
                irx.columns = irx.columns.get_level_values(0)

            if len(tnx) > 0 and len(irx) > 0:
                ten_year = float(tnx['Close'].iloc[-1])
                three_month = float(irx['Close'].iloc[-1])
                spread = ten_year - three_month

                if spread > 0.5:
                    yc_status = "NORMAL"
                elif spread > 0:
                    yc_status = "FLATTENING"
                else:
                    yc_status = "INVERTED"

                result["yield_curve"] = {
                    "10y_rate": round(ten_year, 2),
                    "3mo_rate": round(three_month, 2),
                    "spread": round(spread, 2),
                    "status": yc_status,
                }
        except Exception as e:
            result["yield_curve"] = {"error": str(e)}

        # --- VIX Regime ---
        try:
            vix = yf.download("^VIX", period="3mo", progress=False)
            if isinstance(vix.columns, pd.MultiIndex):
                vix.columns = vix.columns.get_level_values(0)

            if len(vix) > 0:
                vix_level = float(vix['Close'].iloc[-1])
                vix_20d_avg = float(vix['Close'].tail(20).mean())

                if vix_level < 15:
                    vix_status = "COMPLACENT"
                elif vix_level < 20:
                    vix_status = "LOW"
                elif vix_level < 25:
                    vix_status = "NORMAL"
                elif vix_level < 35:
                    vix_status = "ELEVATED"
                else:
                    vix_status = "PANIC"

                vix_trend = "RISING" if vix_level > vix_20d_avg * 1.05 else ("FALLING" if vix_level < vix_20d_avg * 0.95 else "STABLE")

                result["vix_regime"] = {
                    "level": round(vix_level, 2),
                    "20d_avg": round(vix_20d_avg, 2),
                    "status": vix_status,
                    "trend": vix_trend,
                }
        except Exception as e:
            result["vix_regime"] = {"error": str(e)}

        # --- Credit Cycle (HYG/LQD ratio) ---
        try:
            hyg = yf.download("HYG", period="6mo", progress=False)
            lqd = yf.download("LQD", period="6mo", progress=False)

            if isinstance(hyg.columns, pd.MultiIndex):
                hyg.columns = hyg.columns.get_level_values(0)
            if isinstance(lqd.columns, pd.MultiIndex):
                lqd.columns = lqd.columns.get_level_values(0)

            if len(hyg) > 20 and len(lqd) > 20:
                # Align dates
                common_dates = hyg.index.intersection(lqd.index)
                if len(common_dates) > 20:
                    hyg_aligned = hyg.loc[common_dates]
                    lqd_aligned = lqd.loc[common_dates]

                    ratio_current = float(hyg_aligned['Close'].iloc[-1] / lqd_aligned['Close'].iloc[-1])
                    ratio_20d = float(hyg_aligned['Close'].tail(20).mean() / lqd_aligned['Close'].tail(20).mean())
                    ratio_60d = float(hyg_aligned['Close'].tail(60).mean() / lqd_aligned['Close'].tail(60).mean()) if len(common_dates) >= 60 else ratio_20d

                    if ratio_current > ratio_60d * 1.01:
                        credit_trend = "RISK_ON"
                    elif ratio_current < ratio_60d * 0.99:
                        credit_trend = "RISK_OFF"
                    else:
                        credit_trend = "NEUTRAL"

                    result["credit_cycle"] = {
                        "hyg_lqd_ratio": round(ratio_current, 4),
                        "20d_avg": round(ratio_20d, 4),
                        "60d_avg": round(ratio_60d, 4),
                        "trend": credit_trend,
                    }
        except Exception as e:
            result["credit_cycle"] = {"error": str(e)}

        # --- Market Breadth (optional, slower) ---
        if include_breadth:
            try:
                # Top 20 SPY holdings — representative sample
                top_holdings = [
                    "AAPL", "MSFT", "NVDA", "AMZN", "META",
                    "GOOGL", "BRK-B", "LLY", "AVGO", "JPM",
                    "TSLA", "UNH", "XOM", "V", "MA",
                    "PG", "COST", "JNJ", "HD", "ABBV",
                ]
                above_200sma = 0
                total_checked = 0
                for sym in top_holdings:
                    try:
                        d = yf.download(sym, period="1y", progress=False)
                        if isinstance(d.columns, pd.MultiIndex):
                            d.columns = d.columns.get_level_values(0)
                        if len(d) >= 200:
                            sma_200 = float(d['Close'].tail(200).mean())
                            current = float(d['Close'].iloc[-1])
                            total_checked += 1
                            if current > sma_200:
                                above_200sma += 1
                    except Exception:
                        continue

                breadth_pct = (above_200sma / total_checked * 100) if total_checked > 0 else 50
                result["market_breadth"] = {
                    "above_200sma_pct": round(breadth_pct, 1),
                    "sample_size": total_checked,
                    "status": "STRONG" if breadth_pct > 70 else ("MODERATE" if breadth_pct > 50 else "WEAK"),
                }
            except Exception as e:
                result["market_breadth"] = {"error": str(e)}

        # --- Classify Regime ---
        yc_status = result.get("yield_curve", {}).get("status", "UNKNOWN")
        vix_status = result.get("vix_regime", {}).get("status", "UNKNOWN")
        credit_trend = result.get("credit_cycle", {}).get("trend", "UNKNOWN")
        breadth_status = result.get("market_breadth", {}).get("status", "UNKNOWN")

        # Scoring-based regime classification
        expansion_score = 0
        contraction_score = 0

        if yc_status == "NORMAL":
            expansion_score += 2
        elif yc_status == "INVERTED":
            contraction_score += 3

        if vix_status in ("COMPLACENT", "LOW"):
            expansion_score += 2
        elif vix_status in ("ELEVATED", "PANIC"):
            contraction_score += 2

        if credit_trend == "RISK_ON":
            expansion_score += 2
        elif credit_trend == "RISK_OFF":
            contraction_score += 2

        if breadth_status == "STRONG":
            expansion_score += 1
        elif breadth_status == "WEAK":
            contraction_score += 1

        if expansion_score >= 5:
            regime = "EXPANSION"
        elif contraction_score >= 5:
            regime = "CONTRACTION"
        elif expansion_score > contraction_score:
            regime = "LATE_CYCLE"
        elif contraction_score > expansion_score:
            regime = "RECOVERY" if vix_status in ("NORMAL", "LOW") else "CONTRACTION"
        else:
            regime = "LATE_CYCLE"

        result["regime"] = regime

        # Lesson
        regime_lessons = {
            "EXPANSION": "Economy expanding — normal yield curve, low VIX, risk-on credit. Favor long equities, sell put premium.",
            "LATE_CYCLE": "Late-cycle dynamics — flattening yield curve, moderate VIX. Be selective, favor quality, tighten stops.",
            "CONTRACTION": "Contraction signals — inverted yield curve, elevated VIX, risk-off credit. Favor defensive positions, buy put protection.",
            "RECOVERY": "Recovery phase — yield curve steepening, VIX declining. Early cyclicals outperform. Increase equity exposure.",
        }
        result["lesson"] = regime_lessons.get(regime, "Regime unclear — use caution.")

        return result

    except Exception as e:
        logger.error(f"Macro regime detection failed: {e}")
        return {"error": f"Macro regime failed: {str(e)}"}


def _generate_dalio_lesson(
    dalio_ratio: float,
    interpretation: str,
    cdf_direction: str,
    sustainability_score: int,
    institutional_detected: bool,
) -> str:
    """Generate educational paragraph explaining Dalio analysis results."""
    parts = []

    parts.append(
        f"Dalio's Economic Machine principle tells us that Price = Total Spending / Quantity Sold. "
        f"For this stock, the Dalio Ratio is {dalio_ratio:.3f} ({interpretation}), meaning "
    )

    if dalio_ratio > 1.02:
        parts.append(
            "buyers are paying a PREMIUM per share compared to the prior period. "
            "This indicates real capital is flowing INTO this stock at increasingly higher prices — bullish."
        )
    elif dalio_ratio < 0.98:
        parts.append(
            "buyers are paying a DISCOUNT per share compared to the prior period. "
            "This indicates sellers are accepting lower prices to exit — bearish."
        )
    else:
        parts.append(
            "spending per share is roughly FLAT compared to the prior period. "
            "Neither buyers nor sellers have a clear edge — neutral."
        )

    parts.append(
        f" Dollar flow shows {cdf_direction.lower()}, and the trend sustainability score "
        f"is {sustainability_score}/100."
    )

    if institutional_detected:
        parts.append(
            " Institutional activity detected — large players are deploying significant capital, "
            "which tends to sustain the current direction."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Tool registration for MCP server
# ---------------------------------------------------------------------------

def register_tools(mcp):
    @mcp.tool()
    def analyze_dalio_economic_machine(
        ticker: str,
        period: str = "3mo",
        lookback_days: int = 20,
        include_profile: bool = True,
    ) -> dict[str, Any]:
        """
        Analyze stock using Ray Dalio's Economic Machine principle.

        Core insight: Price = Total Spending / Quantity Sold

        Returns comprehensive dollar-volume analysis including:
        - Dalio Ratio (current vs prior VWAP)
        - Dollar Volume Momentum & classification
        - Spending Efficiency Ratio
        - Cumulative Dollar Flow (5d, 20d, total)
        - Dollar Volume Profile with POC & Value Area
        - Institutional activity detection
        - Trend sustainability score (0-100)
        - Educational lesson explaining the analysis

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            period: Historical data period ('1mo', '3mo', '6mo', '1y')
            lookback_days: Rolling window for ratio calculations (default: 20)
            include_profile: Whether to calculate dollar volume profile (default: True)

        Returns:
            Comprehensive Dalio Economic Machine analysis
        """
        return analyze_dalio_economic_machine_impl(ticker, period, lookback_days, include_profile)

    @mcp.tool()
    def get_macro_regime(include_breadth: bool = False) -> dict[str, Any]:
        """
        Detect current macro economic regime using market data.

        No external API keys needed — uses yfinance for:
        - Yield curve: 10Y Treasury (^TNX) minus 3-month (^IRX)
        - VIX regime: Volatility level and trend
        - Credit cycle: HYG/LQD ratio (risk appetite)
        - Market breadth (optional): % of top 20 S&P stocks above 200 SMA

        Regime classification:
        - EXPANSION: Normal yield curve, low VIX, risk-on credit
        - LATE_CYCLE: Flattening curve, moderate VIX
        - CONTRACTION: Inverted curve, elevated VIX, risk-off
        - RECOVERY: Steepening curve, falling VIX

        Args:
            include_breadth: Calculate market breadth (slower, fetches 20 tickers)

        Returns:
            Macro regime analysis with components
        """
        return get_macro_regime_impl(include_breadth)
