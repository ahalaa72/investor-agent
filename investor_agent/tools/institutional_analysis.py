"""Institutional Analysis — Phase 5 MCP Tools.

Goldman/JPM-style institutional enhancements:
- Intermarket correlation analysis (DXY, TNX, crude, gold vs ticker)
- VIX term structure (contango/backwardation regime filter)
- Expected move from straddle pricing
- Macro context header (aggregates all regime signals)

MCP tools (4):
    analyze_intermarket_correlation  — Cross-asset correlation signals
    analyze_vix_term_structure       — VIX contango/backwardation detection
    calculate_expected_move          — Expected move from IV or straddle
    generate_macro_context_header    — Goldman-style regime summary
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ============================================================================
# Helper: flatten yfinance MultiIndex
# ============================================================================

def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _safe_download(symbol: str, period: str = "6mo") -> pd.DataFrame | None:
    """Download price data with error handling."""
    try:
        df = yf.download(symbol, period=period, progress=False)
        if df is None or len(df) == 0:
            return None
        return _flatten(df)
    except Exception as e:
        logger.warning(f"Failed to download {symbol}: {e}")
        return None


# ============================================================================
# 1. Intermarket Correlation Analysis
# ============================================================================

# Default benchmarks: dollar, rates, crude, gold, broad market
DEFAULT_BENCHMARKS = {
    "UUP": "US Dollar (DXY proxy)",
    "^TNX": "10Y Treasury Yield",
    "USO": "Crude Oil",
    "GLD": "Gold",
    "SPY": "S&P 500",
    "TLT": "20Y+ Treasury Bonds",
    "HYG": "High-Yield Credit",
}


def _intermarket_correlation_impl(
    ticker: str,
    benchmarks: list[str] | None = None,
    lookback_days: int = 60,
) -> dict[str, Any]:
    """
    Calculate rolling correlation between a ticker and macro benchmarks.

    Returns correlation matrix, strongest/weakest correlations,
    and regime implications.
    """
    try:
        if benchmarks is None:
            benchmarks_map = DEFAULT_BENCHMARKS.copy()
        else:
            benchmarks_map = {b: b for b in benchmarks}

        period = "12mo" if lookback_days > 180 else "6mo"

        # Download ticker
        ticker_df = _safe_download(ticker, period=period)
        if ticker_df is None or len(ticker_df) < lookback_days:
            return {"error": f"Insufficient data for {ticker}"}

        ticker_returns = ticker_df['Close'].pct_change().dropna()

        # Download benchmarks
        benchmark_returns = {}
        benchmark_labels = {}
        for sym, label in benchmarks_map.items():
            df = _safe_download(sym, period=period)
            if df is not None and len(df) >= lookback_days // 2:
                benchmark_returns[sym] = df['Close'].pct_change().dropna()
                benchmark_labels[sym] = label

        if not benchmark_returns:
            return {"error": "Could not download any benchmark data"}

        # Align all series
        all_returns = {"TICKER": ticker_returns}
        all_returns.update(benchmark_returns)
        returns_df = pd.DataFrame(all_returns).dropna()

        if len(returns_df) < 20:
            return {"error": f"Insufficient overlapping data ({len(returns_df)} days, need 20+)"}

        # Use last N days
        returns_df = returns_df.tail(lookback_days)

        # Full correlation matrix
        corr_matrix = returns_df.corr()

        # Extract ticker correlations
        ticker_corrs = {}
        for sym in benchmark_returns:
            r = float(corr_matrix.loc["TICKER", sym])
            ticker_corrs[sym] = {
                "label": benchmark_labels[sym],
                "correlation": round(r, 4),
                "strength": (
                    "STRONG_POSITIVE" if r > 0.6 else
                    "MODERATE_POSITIVE" if r > 0.3 else
                    "WEAK" if abs(r) <= 0.3 else
                    "MODERATE_NEGATIVE" if r > -0.6 else
                    "STRONG_NEGATIVE"
                ),
            }

        # Sort by absolute correlation
        sorted_corrs = sorted(ticker_corrs.items(), key=lambda x: abs(x[1]["correlation"]), reverse=True)

        # Regime implications
        implications = []

        # Dollar correlation
        uup_corr = ticker_corrs.get("UUP", {}).get("correlation", 0)
        if abs(uup_corr) > 0.3:
            direction = "positively" if uup_corr > 0 else "negatively"
            implications.append(
                f"{ticker} is {direction} correlated with USD (r={uup_corr:.2f}). "
                f"{'Dollar strength supports' if uup_corr > 0 else 'Dollar strength pressures'} this stock."
            )

        # Rates correlation
        tnx_corr = ticker_corrs.get("^TNX", {}).get("correlation", 0)
        if abs(tnx_corr) > 0.3:
            direction = "positively" if tnx_corr > 0 else "negatively"
            implications.append(
                f"{ticker} is {direction} correlated with 10Y yields (r={tnx_corr:.2f}). "
                f"{'Rising rates support' if tnx_corr > 0 else 'Rising rates pressure'} this stock."
            )

        # SPY correlation (beta proxy)
        spy_corr = ticker_corrs.get("SPY", {}).get("correlation", 0)
        if spy_corr > 0.7:
            implications.append(f"{ticker} is highly correlated with SPY (r={spy_corr:.2f}) — moves with broad market.")
        elif spy_corr < 0.3:
            implications.append(f"{ticker} has LOW correlation with SPY (r={spy_corr:.2f}) — potential diversifier.")

        # Gold correlation (risk-off behavior)
        gld_corr = ticker_corrs.get("GLD", {}).get("correlation", 0)
        if gld_corr > 0.3:
            implications.append(f"{ticker} moves with gold (r={gld_corr:.2f}) — behaves as defensive/inflation hedge.")

        # Format full matrix for output
        corr_output = {}
        for col in corr_matrix.columns:
            label = "TICKER" if col == "TICKER" else benchmark_labels.get(col, col)
            corr_output[label] = {}
            for row in corr_matrix.columns:
                row_label = "TICKER" if row == "TICKER" else benchmark_labels.get(row, row)
                corr_output[label][row_label] = round(float(corr_matrix.loc[col, row]), 4)

        return {
            "ticker": ticker,
            "lookback_days": lookback_days,
            "data_points": len(returns_df),

            "ticker_correlations": ticker_corrs,

            "strongest_correlation": {
                "benchmark": sorted_corrs[0][0] if sorted_corrs else None,
                "label": sorted_corrs[0][1]["label"] if sorted_corrs else None,
                "correlation": sorted_corrs[0][1]["correlation"] if sorted_corrs else 0,
            },

            "weakest_correlation": {
                "benchmark": sorted_corrs[-1][0] if sorted_corrs else None,
                "label": sorted_corrs[-1][1]["label"] if sorted_corrs else None,
                "correlation": sorted_corrs[-1][1]["correlation"] if sorted_corrs else 0,
            },

            "full_correlation_matrix": corr_output,

            "regime_implications": implications,

            "hedging_suggestions": _generate_hedge_suggestions(ticker, ticker_corrs),

            "methodology": f"{lookback_days}-day rolling Pearson correlation with macro benchmarks",
        }

    except Exception as e:
        logger.error(f"Intermarket correlation failed: {e}", exc_info=True)
        return {"error": str(e), "ticker": ticker}


def _generate_hedge_suggestions(ticker: str, correlations: dict) -> list[str]:
    """Generate hedging suggestions based on correlations."""
    suggestions = []

    spy_corr = correlations.get("SPY", {}).get("correlation", 0)
    tlt_corr = correlations.get("TLT", {}).get("correlation", 0)
    gld_corr = correlations.get("GLD", {}).get("correlation", 0)
    uup_corr = correlations.get("UUP", {}).get("correlation", 0)

    # SPY hedge
    if spy_corr > 0.5:
        suggestions.append(f"SPY puts can hedge {ticker} (r={spy_corr:.2f}). Use beta-adjusted ratio.")

    # TLT as hedge
    if tlt_corr < -0.3:
        suggestions.append(f"TLT is a natural hedge for {ticker} (r={tlt_corr:.2f}). Consider TLT calls.")
    elif tlt_corr > 0.3:
        suggestions.append(f"TLT and {ticker} move together (r={tlt_corr:.2f}) — NOT a hedge. Use puts instead.")

    # Gold as hedge
    if gld_corr < -0.2:
        suggestions.append(f"GLD provides diversification from {ticker} (r={gld_corr:.2f}).")

    # Dollar exposure
    if abs(uup_corr) > 0.3:
        direction = "long" if uup_corr < 0 else "short"
        suggestions.append(f"Consider {direction} UUP to hedge dollar exposure (r={uup_corr:.2f}).")

    if not suggestions:
        suggestions.append("No strong macro correlations detected — position-level hedging (puts/collars) recommended.")

    return suggestions


# ============================================================================
# 2. VIX Term Structure Analysis
# ============================================================================

def _vix_term_structure_impl() -> dict[str, Any]:
    """
    Analyze VIX term structure: contango vs backwardation.

    Uses ^VIX (spot) vs ^VIX3M (3-month VIX) to determine
    whether volatility markets are in normal (contango) or stressed
    (backwardation) state.

    Contango (VIX < VIX3M): Normal — short-term calm, premium sellers benefit
    Backwardation (VIX > VIX3M): Stress — near-term fear, premium buyers benefit
    """
    try:
        # Download VIX spot and 3-month VIX
        vix_spot = _safe_download("^VIX", period="6mo")
        vix_3m = _safe_download("^VIX3M", period="6mo")

        if vix_spot is None or len(vix_spot) < 5:
            return {"error": "Could not download VIX spot data"}

        current_vix = float(vix_spot['Close'].iloc[-1])
        vix_20d_avg = float(vix_spot['Close'].tail(20).mean())
        vix_5d_avg = float(vix_spot['Close'].tail(5).mean())

        # VIX percentile (6-month)
        vix_values = vix_spot['Close'].dropna()
        vix_percentile = float((vix_values < current_vix).mean() * 100)

        result = {
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "vix_spot": round(current_vix, 2),
            "vix_5d_avg": round(vix_5d_avg, 2),
            "vix_20d_avg": round(vix_20d_avg, 2),
            "vix_percentile_6mo": round(vix_percentile, 1),
        }

        # Term structure analysis
        if vix_3m is not None and len(vix_3m) >= 5:
            current_vix3m = float(vix_3m['Close'].iloc[-1])
            ratio = current_vix / current_vix3m

            if ratio < 0.90:
                structure = "STEEP_CONTANGO"
                description = "Deep contango — markets very calm, premium selling strongly favored"
            elif ratio < 1.0:
                structure = "CONTANGO"
                description = "Normal contango — short-term vol below long-term, premium selling favored"
            elif ratio < 1.05:
                structure = "FLAT"
                description = "Flat term structure — neutral, no strong directional bias"
            elif ratio < 1.15:
                structure = "BACKWARDATION"
                description = "Backwardation — near-term fear elevated, consider buying protection"
            else:
                structure = "STEEP_BACKWARDATION"
                description = "Steep backwardation — extreme near-term stress, markets pricing crash risk"

            # Historical context
            vix3m_values = vix_3m['Close'].dropna()
            common = vix_spot.index.intersection(vix_3m.index)
            if len(common) >= 20:
                hist_ratios = vix_spot.loc[common]['Close'] / vix_3m.loc[common]['Close']
                ratio_percentile = float((hist_ratios < ratio).mean() * 100)
                days_in_backwardation = int((hist_ratios > 1.0).sum())
                pct_in_backwardation = round(days_in_backwardation / len(hist_ratios) * 100, 1)
            else:
                ratio_percentile = 50.0
                days_in_backwardation = 0
                pct_in_backwardation = 0

            result.update({
                "vix_3m": round(current_vix3m, 2),
                "vix_vix3m_ratio": round(ratio, 4),
                "term_structure": structure,
                "description": description,
                "ratio_percentile_6mo": round(ratio_percentile, 1),
                "days_in_backwardation_6mo": days_in_backwardation,
                "pct_time_backwardation": pct_in_backwardation,
            })
        else:
            # Fallback: use VIX trend as proxy
            if current_vix < vix_20d_avg * 0.90:
                structure = "CONTANGO_IMPLIED"
                description = "VIX below 20d avg — implied contango, market calm"
            elif current_vix > vix_20d_avg * 1.10:
                structure = "BACKWARDATION_IMPLIED"
                description = "VIX above 20d avg — implied backwardation, stress rising"
            else:
                structure = "FLAT_IMPLIED"
                description = "VIX near 20d avg — neutral implied term structure"

            result.update({
                "vix_3m": None,
                "vix_vix3m_ratio": None,
                "term_structure": structure,
                "description": description,
                "note": "VIX3M unavailable — using VIX trend as proxy",
            })

        # VIX regime classification
        if current_vix < 15:
            vix_regime = "COMPLACENT"
            options_bias = "Sell premium aggressively — IV cheap, theta decay maximized"
        elif current_vix < 20:
            vix_regime = "LOW"
            options_bias = "Sell premium selectively — normal conditions, favor defined-risk"
        elif current_vix < 25:
            vix_regime = "NORMAL"
            options_bias = "Balanced — consider both premium selling and directional"
        elif current_vix < 35:
            vix_regime = "ELEVATED"
            options_bias = "Buy protection — IV elevated, straddles/strangles expensive to sell"
        else:
            vix_regime = "PANIC"
            options_bias = "Crisis mode — buy puts, sell covered calls, wait for VIX to normalize"

        result.update({
            "vix_regime": vix_regime,
            "options_bias": options_bias,
            "vix_trend": (
                "RISING" if current_vix > vix_20d_avg * 1.05
                else "FALLING" if current_vix < vix_20d_avg * 0.95
                else "STABLE"
            ),
        })

        # Trading implications
        implications = []
        if "CONTANGO" in result["term_structure"]:
            implications.append("Short volatility strategies favored — sell strangles, iron condors")
            implications.append("VIX ETNs (SVXY long, VXX short) may benefit from roll yield")
        elif "BACKWARDATION" in result["term_structure"]:
            implications.append("Long volatility strategies favored — buy straddles, protective puts")
            implications.append("VXX/UVXY may outperform due to positive roll yield")
            implications.append("Widen iron condor wings or switch to iron butterflies")

        if current_vix < 15 and "CONTANGO" in result["term_structure"]:
            implications.append("CAUTION: Very low VIX + contango = complacency. Black swan risk elevated.")

        result["trading_implications"] = implications

        return result

    except Exception as e:
        logger.error(f"VIX term structure analysis failed: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# 3. Expected Move Calculation
# ============================================================================

def _expected_move_impl(
    ticker: str,
    dte: int = 30,
    use_straddle: bool = True,
) -> dict[str, Any]:
    """
    Calculate expected move from IV and/or straddle pricing.

    Two methods:
    1. IV-based: Price × IV × √(DTE/365)
    2. Straddle-based: ATM Straddle Price × 0.85 (more accurate near earnings)
    """
    import math

    try:
        # Get current price
        from ..core.price import get_current_price_questrade_first
        try:
            current_price = get_current_price_questrade_first(ticker)
        except Exception:
            tick = yf.Ticker(ticker)
            current_price = tick.info.get('currentPrice') or tick.info.get('regularMarketPrice', 0)

        if not current_price or current_price <= 0:
            return {"error": f"Could not get price for {ticker}"}

        result = {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "dte": dte,
        }

        # Method 1: IV-based expected move
        iv = None
        try:
            from .options_analysis import analyze_options_mcmillan_impl
            if analyze_options_mcmillan_impl:
                options_data = analyze_options_mcmillan_impl(ticker)
                if options_data and "error" not in options_data:
                    iv_data = options_data.get("iv_analysis", {})
                    iv = iv_data.get("current_iv")
                    if iv and iv > 1.5:
                        iv = iv / 100  # Convert from percentage
        except Exception:
            pass

        if iv is None:
            # Fallback: get IV from yfinance options
            try:
                tick = yf.Ticker(ticker)
                expirations = tick.options
                if expirations:
                    chain = tick.option_chain(expirations[0])
                    calls = chain.calls
                    # ATM call IV
                    atm_idx = (calls['strike'] - current_price).abs().idxmin()
                    iv = float(calls.loc[atm_idx, 'impliedVolatility'])
            except Exception:
                iv = 0.30  # Default 30% IV

        if iv and iv > 0:
            time_factor = math.sqrt(dte / 365)
            em_iv = current_price * iv * time_factor
            em_iv_pct = iv * time_factor * 100

            result["iv_method"] = {
                "iv_used_pct": round(iv * 100, 1),
                "expected_move_dollars": round(em_iv, 2),
                "expected_move_pct": round(em_iv_pct, 2),
                "upper_range": round(current_price + em_iv, 2),
                "lower_range": round(current_price - em_iv, 2),
                "formula": f"${current_price:.2f} × {iv*100:.1f}% × √({dte}/365) = ${em_iv:.2f}",
                "one_sd_range": f"${current_price - em_iv:.2f} — ${current_price + em_iv:.2f}",
                "two_sd_range": f"${current_price - em_iv*2:.2f} — ${current_price + em_iv*2:.2f}",
            }

        # Method 2: Straddle-based (more accurate near earnings)
        straddle_em = None
        if use_straddle:
            try:
                tick = yf.Ticker(ticker)
                expirations = tick.options
                if expirations:
                    # Find expiration closest to target DTE
                    target_date = pd.Timestamp.now() + pd.Timedelta(days=dte)
                    best_exp = min(expirations, key=lambda x: abs((pd.Timestamp(x) - target_date).days))
                    actual_dte = (pd.Timestamp(best_exp) - pd.Timestamp.now()).days

                    chain = tick.option_chain(best_exp)
                    calls = chain.calls
                    puts = chain.puts

                    if len(calls) > 0 and len(puts) > 0:
                        # Find ATM strike
                        atm_strike_idx = (calls['strike'] - current_price).abs().idxmin()
                        atm_strike = float(calls.loc[atm_strike_idx, 'strike'])

                        # ATM call + put mid prices
                        call_row = calls.loc[atm_strike_idx]
                        call_mid = (float(call_row.get('bid', 0)) + float(call_row.get('ask', 0))) / 2
                        if call_mid == 0:
                            call_mid = float(call_row.get('lastPrice', 0))

                        put_row = puts[(puts['strike'] - atm_strike).abs() < 0.5]
                        if len(put_row) > 0:
                            put_mid = (float(put_row.iloc[0].get('bid', 0)) + float(put_row.iloc[0].get('ask', 0))) / 2
                            if put_mid == 0:
                                put_mid = float(put_row.iloc[0].get('lastPrice', 0))
                        else:
                            put_mid = 0

                        straddle_price = call_mid + put_mid
                        if straddle_price > 0:
                            straddle_em = straddle_price * 0.85  # McMillan's 85% rule
                            straddle_em_pct = (straddle_em / current_price) * 100

                            result["straddle_method"] = {
                                "atm_strike": atm_strike,
                                "expiration": best_exp,
                                "actual_dte": actual_dte,
                                "call_mid": round(call_mid, 2),
                                "put_mid": round(put_mid, 2),
                                "straddle_price": round(straddle_price, 2),
                                "expected_move_dollars": round(straddle_em, 2),
                                "expected_move_pct": round(straddle_em_pct, 2),
                                "upper_range": round(current_price + straddle_em, 2),
                                "lower_range": round(current_price - straddle_em, 2),
                                "formula": f"Straddle ${straddle_price:.2f} × 0.85 = ${straddle_em:.2f}",
                                "mcmillan_note": "McMillan Ch.36: ATM straddle × 0.85 = expected 1-SD move",
                            }
            except Exception as e:
                logger.warning(f"Straddle method failed for {ticker}: {e}")

        # Primary expected move (prefer straddle near earnings, IV otherwise)
        if straddle_em and straddle_em > 0:
            primary_em = straddle_em
            primary_method = "straddle"
        elif "iv_method" in result:
            primary_em = result["iv_method"]["expected_move_dollars"]
            primary_method = "iv"
        else:
            return {"error": f"Could not calculate expected move for {ticker}", "ticker": ticker}

        result["primary"] = {
            "method": primary_method,
            "expected_move_dollars": round(primary_em, 2),
            "expected_move_pct": round(primary_em / current_price * 100, 2),
            "upper_bound": round(current_price + primary_em, 2),
            "lower_bound": round(current_price - primary_em, 2),
        }

        result["interpretation"] = (
            f"{ticker} expected to move ±${primary_em:.2f} ({primary_em/current_price*100:.1f}%) "
            f"over next {dte} days (1 standard deviation). "
            f"Range: ${current_price - primary_em:.2f} — ${current_price + primary_em:.2f}"
        )

        return result

    except Exception as e:
        logger.error(f"Expected move calculation failed: {e}", exc_info=True)
        return {"error": str(e), "ticker": ticker}


# ============================================================================
# 4. Macro Context Header
# ============================================================================

def _macro_context_header_impl(
    include_breadth: bool = False,
    include_intermarket: bool = True,
) -> dict[str, Any]:
    """
    Generate Goldman/JPM-style macro context header.

    Aggregates:
    - Macro regime (from get_macro_regime)
    - VIX term structure
    - Intermarket signals (DXY, rates, credit)
    - Fed policy stance

    Returns a structured summary suitable for report headers.
    """
    try:
        # 1. Get macro regime
        from .dalio_analysis import get_macro_regime_impl
        macro = get_macro_regime_impl(include_breadth=include_breadth)

        # 2. Get VIX term structure
        vix_ts = _vix_term_structure_impl()

        # 3. Build header
        regime = macro.get("regime", "UNKNOWN")
        yc = macro.get("yield_curve", {})
        vix = macro.get("vix_regime", {})
        credit = macro.get("credit_cycle", {})
        breadth = macro.get("market_breadth", {})

        # Regime emoji/icon mapping (text-based)
        regime_icons = {
            "EXPANSION": "[EXPANSION]",
            "LATE_CYCLE": "[LATE CYCLE]",
            "CONTRACTION": "[CONTRACTION]",
            "RECOVERY": "[RECOVERY]",
        }

        # Yield curve status
        yc_spread = yc.get("spread", 0)
        yc_status = yc.get("status", "UNKNOWN")
        ten_yr = yc.get("10y_rate", 0)

        # VIX data
        vix_level = vix.get("level", 0) or vix_ts.get("vix_spot", 0)
        vix_regime = vix.get("status", "UNKNOWN")
        vix_trend = vix.get("trend", vix_ts.get("vix_trend", "UNKNOWN"))

        # Term structure
        term_structure = vix_ts.get("term_structure", "UNKNOWN")
        vix_ratio = vix_ts.get("vix_vix3m_ratio")

        # Credit
        credit_trend = credit.get("trend", "UNKNOWN")
        hyg_lqd = credit.get("hyg_lqd_ratio", 0)

        # Build summary table
        macro_table = {
            "regime": regime,
            "yield_curve": f"{yc_status} (10Y: {ten_yr}%, spread: {yc_spread:+.2f}%)",
            "vix": f"{vix_level:.1f} ({vix_regime}, {vix_trend})",
            "vix_term_structure": f"{term_structure}" + (f" (ratio: {vix_ratio:.3f})" if vix_ratio else ""),
            "credit": f"{credit_trend}" + (f" (HYG/LQD: {hyg_lqd:.4f})" if hyg_lqd else ""),
        }

        if breadth:
            macro_table["breadth"] = f"{breadth.get('status', 'N/A')} ({breadth.get('above_200sma_pct', 0):.0f}% above 200 SMA)"

        # Fed policy stance (derived from yield curve)
        if yc_status == "INVERTED":
            fed_stance = "RESTRICTIVE — Inverted curve signals tight monetary policy"
        elif yc_status == "FLATTENING":
            fed_stance = "TRANSITIONING — Flattening curve, policy tightening or nearing pivot"
        elif yc_spread > 1.0:
            fed_stance = "ACCOMMODATIVE — Steep curve, loose monetary conditions"
        else:
            fed_stance = "NEUTRAL — Normal curve, balanced monetary conditions"

        macro_table["fed_policy_stance"] = fed_stance

        # Options strategy bias
        if "CONTANGO" in term_structure and vix_level < 20:
            strategy_bias = "SELL PREMIUM — Low VIX + contango = theta harvest"
        elif "BACKWARDATION" in term_structure or vix_level > 30:
            strategy_bias = "BUY PROTECTION — Elevated VIX or backwardation = hedging mode"
        elif vix_level < 25:
            strategy_bias = "BALANCED — Normal VIX, use defined-risk strategies"
        else:
            strategy_bias = "CAUTIOUS — Elevated volatility, reduce position sizes"

        macro_table["options_strategy_bias"] = strategy_bias

        # Generate narrative
        narrative = (
            f"MACRO REGIME: {regime_icons.get(regime, regime)} — "
            f"Yield curve {yc_status.lower()} ({yc_spread:+.2f}%), "
            f"VIX at {vix_level:.1f} ({vix_regime.lower()}, {vix_trend.lower()}), "
            f"credit {credit_trend.lower().replace('_', ' ')}. "
            f"VIX term structure in {term_structure.lower().replace('_', ' ')}. "
            f"{fed_stance.split('—')[0].strip()}. "
            f"Strategy bias: {strategy_bias.split('—')[0].strip()}."
        )

        return {
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "macro_summary": macro_table,
            "narrative": narrative,
            "regime": regime,
            "regime_lesson": macro.get("lesson", ""),

            "components": {
                "macro_regime": macro,
                "vix_term_structure": vix_ts,
            },

            "key_levels": {
                "10y_yield": ten_yr,
                "vix_spot": vix_level,
                "vix_20d_avg": vix_ts.get("vix_20d_avg"),
                "hyg_lqd_ratio": hyg_lqd,
            },

            "trading_implications": vix_ts.get("trading_implications", []),

            "methodology": "Aggregated macro regime (yield curve + VIX + credit + breadth) with VIX term structure overlay",
        }

    except Exception as e:
        logger.error(f"Macro context header failed: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# MCP Tool Registration
# ============================================================================

def register_tools(mcp):
    """Register Phase 5 institutional analysis tools with MCP server."""

    @mcp.tool()
    def analyze_intermarket_correlation(
        ticker: str,
        benchmarks: list[str] | None = None,
        lookback_days: int = 60,
    ) -> dict[str, Any]:
        """
        Analyze cross-asset correlations between a ticker and macro benchmarks.

        Calculates rolling correlations with USD, 10Y yields, crude oil, gold,
        SPY, treasuries, and credit. Identifies hedging opportunities and
        regime implications.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            benchmarks: Custom benchmark list (default: UUP, ^TNX, USO, GLD, SPY, TLT, HYG)
            lookback_days: Rolling window for correlation (default 60 days)

        Returns:
            Correlation matrix, strongest/weakest correlations, regime implications,
            hedging suggestions
        """
        return _intermarket_correlation_impl(ticker, benchmarks, lookback_days)

    @mcp.tool()
    def analyze_vix_term_structure() -> dict[str, Any]:
        """
        Analyze VIX term structure: contango vs backwardation.

        Compares VIX spot (^VIX) vs VIX 3-month (^VIX3M) to determine
        if volatility markets are calm (contango) or stressed (backwardation).

        Contango = short premium favored (iron condors, strangles)
        Backwardation = long premium favored (straddles, protective puts)

        Returns:
            VIX spot, VIX3M, ratio, term structure classification,
            historical context, VIX regime, options bias, trading implications
        """
        return _vix_term_structure_impl()

    @mcp.tool()
    def calculate_expected_move(
        ticker: str,
        dte: int = 30,
        use_straddle: bool = True,
    ) -> dict[str, Any]:
        """
        Calculate expected price move from IV and/or straddle pricing.

        Two methods:
        1. IV-based: Price × IV × √(DTE/365) — standard Black-Scholes
        2. Straddle-based: ATM Straddle × 0.85 — McMillan's method (more accurate near earnings)

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            dte: Days to expiration / forecast horizon (default 30)
            use_straddle: Whether to also calculate straddle-based move (default True)

        Returns:
            Expected move (dollars, percent), upper/lower ranges for 1-SD and 2-SD,
            both IV-based and straddle-based calculations
        """
        return _expected_move_impl(ticker, dte, use_straddle)

    @mcp.tool()
    def generate_macro_context_header(
        include_breadth: bool = False,
        include_intermarket: bool = True,
    ) -> dict[str, Any]:
        """
        Generate Goldman/JPM-style macro context header for reports.

        Aggregates all macro signals into a single institutional-grade summary:
        - Economic regime (EXPANSION/LATE_CYCLE/CONTRACTION/RECOVERY)
        - Yield curve status and Fed policy stance
        - VIX level, trend, and term structure
        - Credit cycle (HYG/LQD risk-on/risk-off)
        - Market breadth (optional, slower)
        - Options strategy bias

        Args:
            include_breadth: Include market breadth analysis (slower, checks 20 stocks)
            include_intermarket: Include intermarket context

        Returns:
            Macro summary table, narrative paragraph, key levels,
            trading implications, options strategy bias
        """
        return _macro_context_header_impl(include_breadth, include_intermarket)
