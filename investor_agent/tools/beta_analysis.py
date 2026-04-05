"""
Dynamic Beta Analysis Tools

Rolling beta, beta regime detection, and BAB (Betting Against Beta) screening.

Data source priority:
- User's ticker: Questrade candles (primary) → yfinance (fallback)
- Benchmarks (SPY, XLU, sector ETFs): yfinance (batch efficiency)

Based on:
- Frazzini & Pedersen (2014) "Betting Against Beta" — Sharpe 0.78
- Gayed & Bilello (2014) "An Intermarket Approach to Beta Rotation" — Dow Award
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# HELPER: Get daily returns
# ============================================================

def _get_returns_questrade(ticker: str, days: int = 504) -> pd.Series | None:
    """Get daily close returns from Questrade candles (inside Docker)."""
    try:
        from ..tools.questrade_api import get_questrade_candles_impl
        result = get_questrade_candles_impl(
            symbol=ticker,
            interval="OneDay",
            window=days
        )
        candles = result.get("candles", [])
        if not candles or len(candles) < 60:
            return None

        dates = []
        closes = []
        for c in candles:
            dt = c.get("start") or c.get("date") or c.get("end")
            cl = c.get("close") or c.get("VWAP")
            if dt and cl is not None:
                ts = pd.Timestamp(dt)
                if ts.tzinfo is not None:
                    ts = ts.tz_convert("America/New_York").tz_localize(None)
                dates.append(ts)
                closes.append(float(cl))

        if len(closes) < 60:
            return None

        series = pd.Series(closes, index=pd.DatetimeIndex(dates), name=ticker)
        series = series.sort_index()
        returns = series.pct_change().dropna()
        logger.info(f"✓ {ticker}: {len(returns)} daily returns from Questrade")
        return returns

    except Exception as e:
        logger.warning(f"Questrade candles failed for {ticker}: {e}")
        return None


def _get_returns_yfinance(ticker: str, period: str = "2y") -> pd.Series:
    """Get daily close returns from Yahoo Finance."""
    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    if hist.empty:
        raise ValueError(f"No price data for {ticker}")
    # Normalize to tz-naive for alignment with Questrade data
    if hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)
    returns = hist["Close"].pct_change().dropna()
    returns.name = ticker
    logger.info(f"✓ {ticker}: {len(returns)} daily returns from yfinance")
    return returns


def _get_returns(ticker: str, use_questrade: bool = True, period: str = "2y") -> tuple[pd.Series, str]:
    """Get daily returns — Questrade primary, yfinance fallback. Returns (series, source)."""
    if use_questrade:
        qt_returns = _get_returns_questrade(ticker)
        if qt_returns is not None and len(qt_returns) >= 60:
            return qt_returns, "QUESTRADE"

    return _get_returns_yfinance(ticker, period), "YAHOO_FINANCE"


def _safe_float(val) -> float:
    """Convert numpy/pandas types to Python float."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 0.0
    return round(float(val), 4)


# ============================================================
# IMPLEMENTATION: Rolling Beta
# ============================================================

def calculate_rolling_beta_impl(
    ticker: str,
    benchmark: str = "SPY",
    windows: list[int] | None = None,
    use_questrade: bool = True,
) -> dict[str, Any]:
    """
    Core rolling beta implementation.

    Computes rolling beta at multiple windows, trend detection,
    conditional (bull/bear) beta, and position sizing adjustment.
    """
    if windows is None:
        windows = [60, 120, 252]

    # Get returns — Questrade for user ticker, yfinance for benchmark
    stock_returns, data_source = _get_returns(ticker, use_questrade=use_questrade)
    market_returns, _ = _get_returns(benchmark, use_questrade=False)

    # Align dates
    aligned = pd.concat([stock_returns, market_returns], axis=1, join="inner").dropna()
    aligned.columns = ["stock", "market"]

    if len(aligned) < 60:
        return {
            "ticker": ticker,
            "benchmark": benchmark,
            "error": f"Insufficient data: {len(aligned)} days (need 60+)",
            "current_betas": {},
            "data_source": data_source,
        }

    result = {
        "ticker": ticker,
        "benchmark": benchmark,
        "data_points": len(aligned),
        "date_range": f"{aligned.index[0].date()} to {aligned.index[-1].date()}",
        "data_source": data_source,
        "current_betas": {},
        "beta_trend": "STABLE",
        "beta_acceleration": 0.0,
        "beta_percentile_2yr": 50.0,
        "conditional_beta": {},
        "regime": {},
        "history": {},
    }

    # ── Rolling betas at each window ──
    beta_series_60 = None
    for w in windows:
        if len(aligned) < w:
            continue
        cov = aligned["stock"].rolling(w).cov(aligned["market"])
        var = aligned["market"].rolling(w).var()
        rolling_b = (cov / var).replace([np.inf, -np.inf], np.nan).dropna()

        if len(rolling_b) > 0:
            current = rolling_b.iloc[-1]
            result["current_betas"][f"{w}d"] = _safe_float(current)

            if w == 60:
                beta_series_60 = rolling_b

    # ── Beta trend (60d beta slope over last 20 days) ──
    if beta_series_60 is not None and len(beta_series_60) >= 20:
        recent = beta_series_60.iloc[-20:]
        x = np.arange(len(recent))
        slope = np.polyfit(x, recent.values, 1)[0]

        if slope > 0.005:
            result["beta_trend"] = "RISING"
        elif slope < -0.005:
            result["beta_trend"] = "FALLING"
        else:
            result["beta_trend"] = "STABLE"

        result["beta_acceleration"] = _safe_float(slope)

        # Percentile vs full history
        current_beta = beta_series_60.iloc[-1]
        percentile = float((beta_series_60 < current_beta).sum() / len(beta_series_60) * 100)
        result["beta_percentile_2yr"] = round(percentile, 1)

        # History for charting (last 20 data points)
        hist_points = beta_series_60.iloc[-20:]
        result["history"] = {
            "beta_60d_series": [_safe_float(v) for v in hist_points.values],
            "dates": [str(d.date()) for d in hist_points.index],
        }

    # ── Conditional beta (bull vs bear market days) ──
    up_days = aligned[aligned["market"] > 0]
    down_days = aligned[aligned["market"] < 0]

    if len(up_days) >= 30 and len(down_days) >= 30:
        bull_cov = up_days["stock"].cov(up_days["market"])
        bull_var = up_days["market"].var()
        bear_cov = down_days["stock"].cov(down_days["market"])
        bear_var = down_days["market"].var()

        bull_beta = bull_cov / bull_var if bull_var > 0 else 1.0
        bear_beta = bear_cov / bear_var if bear_var > 0 else 1.0
        asymmetry = bull_beta - bear_beta

        if asymmetry > 0.3:
            interp = "BETA_TIMING"
            interp_detail = "Rides market up, hides on way down — alpha may be fake"
        elif asymmetry < -0.3:
            interp = "DEFENSIVE_ALPHA"
            interp_detail = "Underperforms in rallies, outperforms in selloffs — genuine defensive alpha"
        else:
            interp = "GENUINE_ALPHA"
            interp_detail = "Symmetric beta across regimes — stock-specific alpha"

        result["conditional_beta"] = {
            "bull_beta": _safe_float(bull_beta),
            "bear_beta": _safe_float(bear_beta),
            "asymmetry": _safe_float(asymmetry),
            "interpretation": interp,
            "detail": interp_detail,
            "bull_days": len(up_days),
            "bear_days": len(down_days),
        }

    # ── Regime classification ──
    beta_60 = result["current_betas"].get("60d", 1.0)
    if beta_60 > 1.3:
        regime = "HIGH_BETA"
        signal = "CORRELATING"
        multiplier = 0.7
    elif beta_60 < 0.7:
        regime = "LOW_BETA"
        signal = "DECOUPLING"
        multiplier = 1.3
    else:
        regime = "NORMAL"
        signal = "STABLE"
        multiplier = 1.0

    # Adjust by trend
    if result["beta_trend"] == "RISING":
        multiplier *= 0.9
    elif result["beta_trend"] == "FALLING":
        multiplier *= 1.1

    multiplier = round(max(0.5, min(1.5, multiplier)), 2)

    result["regime"] = {
        "current": regime,
        "signal": signal,
        "position_size_multiplier": multiplier,
        "interpretation": f"Beta {beta_60:.2f} ({regime}) — "
                         f"{'reduce' if multiplier < 1 else 'increase' if multiplier > 1 else 'maintain'} "
                         f"position size by {abs(1 - multiplier) * 100:.0f}%",
    }

    return result


# ============================================================
# IMPLEMENTATION: Beta Regime (XLU/SPY + Dispersion)
# ============================================================

def analyze_beta_regime_impl() -> dict[str, Any]:
    """
    Market regime detection: XLU/SPY ratio + sector beta dispersion.
    Uses yfinance for all benchmarks (batch efficiency).
    """
    result = {
        "regime_signal": "TRANSITION",
        "xlu_spy_ratio": {},
        "beta_dispersion": {},
        "recommendation": {},
    }

    try:
        # ── XLU/SPY ratio signal (Gayed/Bilello) ──
        xlu_hist = yf.Ticker("XLU").history(period="6mo")
        spy_hist = yf.Ticker("SPY").history(period="6mo")

        if xlu_hist.empty or spy_hist.empty:
            result["error"] = "Could not fetch XLU/SPY data"
            return result

        xlu_close = xlu_hist["Close"]
        spy_close = spy_hist["Close"]

        # Align
        common_idx = xlu_close.index.intersection(spy_close.index)
        xlu_aligned = xlu_close.loc[common_idx]
        spy_aligned = spy_close.loc[common_idx]

        ratio = xlu_aligned / spy_aligned
        ratio = ratio.dropna()

        if len(ratio) >= 20:
            ratio_20d_change = (ratio.iloc[-1] / ratio.iloc[-20] - 1) * 100
        else:
            ratio_20d_change = 0

        if ratio_20d_change > 1.0:
            regime_signal = "RISK_OFF"
            strength = "STRONG" if ratio_20d_change > 3.0 else "MODERATE"
        elif ratio_20d_change < -1.0:
            regime_signal = "RISK_ON"
            strength = "STRONG" if ratio_20d_change < -3.0 else "MODERATE"
        else:
            regime_signal = "TRANSITION"
            strength = "WEAK"

        result["regime_signal"] = regime_signal
        result["xlu_spy_ratio"] = {
            "current": _safe_float(ratio.iloc[-1]),
            "20d_change_pct": round(float(ratio_20d_change), 2),
            "trend": "RISING" if ratio_20d_change > 0 else "FALLING",
            "strength": strength,
            "methodology": "Gayed & Bilello (2014 Dow Award) — XLU/SPY 20-day momentum",
        }

        # ── Sector beta dispersion ──
        sector_etfs = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU"]
        spy_returns = spy_hist["Close"].pct_change().dropna()

        sector_betas = {}
        for etf in sector_etfs:
            try:
                etf_hist = yf.Ticker(etf).history(period="6mo")
                if etf_hist.empty:
                    continue
                etf_returns = etf_hist["Close"].pct_change().dropna()

                # Align with SPY
                aligned = pd.concat([etf_returns, spy_returns], axis=1, join="inner").dropna()
                if len(aligned) < 60:
                    continue
                aligned.columns = ["etf", "spy"]

                recent = aligned.iloc[-60:]
                cov = recent["etf"].cov(recent["spy"])
                var = recent["spy"].var()
                beta = cov / var if var > 0 else 1.0
                sector_betas[etf] = _safe_float(beta)
            except Exception as e:
                logger.warning(f"Beta calc failed for {etf}: {e}")
                continue

        betas_list = list(sector_betas.values())
        if betas_list:
            dispersion = float(np.std(betas_list))
            beta_range = max(betas_list) - min(betas_list)
        else:
            dispersion = 0
            beta_range = 0

        if dispersion < 0.15:
            disp_regime = "COMPRESSED"
            stock_picking = "LOW"
            disp_note = "All sectors moving together — index-driven market, stock selection adds little value"
        elif dispersion > 0.35:
            disp_regime = "EXPANDING"
            stock_picking = "HIGH"
            disp_note = "Sectors decoupling — stock-picker's market, individual analysis matters"
        else:
            disp_regime = "NORMAL"
            stock_picking = "MODERATE"
            disp_note = "Normal dispersion — balanced between index and stock-specific drivers"

        result["beta_dispersion"] = {
            "current": round(dispersion, 3),
            "beta_range": round(beta_range, 3),
            "regime": disp_regime,
            "stock_picking_value": stock_picking,
            "interpretation": disp_note,
            "sector_betas": sector_betas,
        }

        # ── Recommendation ──
        if regime_signal == "RISK_OFF":
            scanner_bias = "DEFENSIVE"
            size_mult = 0.7
            preferred_beta = [0.3, 0.9]
            rationale = (f"Utilities outperforming SPY ({ratio_20d_change:+.1f}% in 20d) — "
                        f"capital flowing to safety. Favor low-beta quality names.")
        elif regime_signal == "RISK_ON" and disp_regime != "COMPRESSED":
            scanner_bias = "AGGRESSIVE"
            size_mult = 1.2
            preferred_beta = [1.0, 2.0]
            rationale = (f"Utilities underperforming SPY ({ratio_20d_change:+.1f}% in 20d) — "
                        f"risk appetite healthy. Favor high-beta momentum names.")
        else:
            scanner_bias = "NEUTRAL"
            size_mult = 1.0
            preferred_beta = [0.7, 1.3]
            rationale = (f"Mixed signals — XLU/SPY {ratio_20d_change:+.1f}%, "
                        f"dispersion {disp_regime}. No strong directional bias.")

        result["recommendation"] = {
            "scanner_bias": scanner_bias,
            "position_size_multiplier": size_mult,
            "preferred_beta_range": preferred_beta,
            "rationale": rationale,
        }

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Beta regime analysis failed: {e}", exc_info=True)

    return result


# ============================================================
# IMPLEMENTATION: BAB Screening
# ============================================================

def screen_bab_candidates_impl(
    universe: list[str] | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Screen for low-beta stocks (Betting Against Beta).
    Frazzini & Pedersen (2014) — Sharpe 0.78.
    """
    if universe is None:
        universe = [
            # Diversified large/mid caps across sectors
            "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA",
            "JNJ", "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD",
            "JPM", "BAC", "GS", "V", "MA",
            "UNH", "PFE", "ABBV", "LLY", "MRK",
            "XOM", "CVX", "COP",
            "NEE", "DUK", "SO",
            "LMT", "RTX", "GD", "CAT", "DE", "HON",
        ]

    spy_returns, _ = _get_returns("SPY", use_questrade=False, period="1y")
    candidates = []

    for ticker in universe:
        try:
            stock_returns, _ = _get_returns(ticker, use_questrade=False, period="1y")

            # Align
            aligned = pd.concat([stock_returns, spy_returns], axis=1, join="inner").dropna()
            if len(aligned) < 120:
                continue
            aligned.columns = ["stock", "market"]

            # Full-period beta
            cov_full = aligned["stock"].cov(aligned["market"])
            var_full = aligned["market"].var()
            beta_full = cov_full / var_full if var_full > 0 else 1.0

            # 60d beta
            recent = aligned.iloc[-60:]
            cov_60 = recent["stock"].cov(recent["market"])
            var_60 = recent["market"].var()
            beta_60 = cov_60 / var_60 if var_60 > 0 else 1.0

            # Annualized return
            ann_return = float(aligned["stock"].mean() * 252 * 100)

            # Sharpe proxy (annualized return / annualized vol)
            ann_vol = float(aligned["stock"].std() * np.sqrt(252) * 100)
            sharpe = ann_return / ann_vol if ann_vol > 0 else 0

            candidates.append({
                "ticker": ticker,
                "rolling_beta_60d": _safe_float(beta_60),
                "rolling_beta_full": _safe_float(beta_full),
                "annualized_return_pct": round(ann_return, 1),
                "annualized_vol_pct": round(ann_vol, 1),
                "sharpe_proxy": round(sharpe, 2),
            })
        except Exception as e:
            logger.warning(f"BAB screening failed for {ticker}: {e}")
            continue

    # Sort by beta ascending (lowest beta first)
    candidates.sort(key=lambda x: x["rolling_beta_60d"])

    # Top N lowest beta
    low_beta = candidates[:top_n]

    # Universe stats
    if candidates:
        all_betas = [c["rolling_beta_60d"] for c in candidates]
        median = float(np.median(all_betas))
        p25 = float(np.percentile(all_betas, 25))
        p75 = float(np.percentile(all_betas, 75))
    else:
        median = p25 = p75 = 1.0

    return {
        "candidates": low_beta,
        "universe_stats": {
            "total_screened": len(candidates),
            "median_beta": round(median, 3),
            "low_beta_threshold_25pct": round(p25, 3),
            "high_beta_threshold_75pct": round(p75, 3),
        },
        "methodology": "Frazzini & Pedersen (2014) BAB factor — Sharpe 0.78 across 20 countries",
        "note": "Low-beta stocks systematically outperform high-beta on risk-adjusted basis",
    }


# ============================================================
# MCP TOOL REGISTRATION
# ============================================================

def register_tools(mcp):
    """Register all beta analysis MCP tools."""

    @mcp.tool()
    def calculate_rolling_beta(
        ticker: str,
        benchmark: str = "SPY",
    ) -> dict:
        """
        Calculate dynamic rolling beta with regime detection.

        Returns 60/120/252-day rolling beta, trend direction (RISING/FALLING/STABLE),
        bull-beta vs bear-beta (alpha verification), and position sizing multiplier.

        Uses Questrade candles for the ticker (real-time), yfinance for benchmark.

        Use to verify whether a trading signal represents genuine alpha
        or is just riding market beta.

        Args:
            ticker: Stock symbol to analyze
            benchmark: Market benchmark (default SPY)
        """
        return calculate_rolling_beta_impl(ticker, benchmark)

    @mcp.tool()
    def analyze_beta_regime() -> dict:
        """
        Market regime detection using beta rotation and dispersion.

        Combines XLU/SPY ratio signal (Gayed/Bilello 2014 Dow Award method)
        with cross-sectional beta dispersion across 8 SPDR sector ETFs.

        Returns:
        - RISK_ON / RISK_OFF / TRANSITION regime
        - Beta dispersion: COMPRESSED (index-driven) / EXPANDING (stock-picker's market)
        - Scanner bias: AGGRESSIVE / DEFENSIVE / NEUTRAL
        - Position sizing multiplier
        """
        return analyze_beta_regime_impl()

    @mcp.tool()
    def screen_bab_candidates(
        top_n: int = 10,
    ) -> dict:
        """
        Screen for Betting Against Beta opportunities (Frazzini & Pedersen 2014).

        Identifies low-beta stocks from a diversified universe. The BAB anomaly
        shows low-beta stocks outperform high-beta on risk-adjusted basis
        (Sharpe 0.78 across 20 countries, bonds, and futures).

        Args:
            top_n: Number of lowest-beta candidates to return
        """
        return screen_bab_candidates_impl(top_n=top_n)
