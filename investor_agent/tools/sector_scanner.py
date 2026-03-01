"""Sector-based market scanning with AI expert analysis.

MCP tool: scan_market_by_sector
Scans the market sector-by-sector, collects LONG and SHORT candidates,
classifies by sector, and generates an AI expert recommendation report.

Uses TradingView sector field + existing 5-gate validation pipeline.
"""
import logging
import time
from datetime import datetime
from typing import Any, Literal

import pytz

from ..core.price import convert_numpy_types

logger = logging.getLogger(__name__)

# TradingView sector names (their proprietary classification)
TRADINGVIEW_SECTORS = [
    "Electronic Technology",
    "Technology Services",
    "Health Technology",
    "Health Services",
    "Finance",
    "Energy Minerals",
    "Consumer Durables",
    "Consumer Non-Durables",
    "Consumer Services",
    "Retail Trade",
    "Producer Manufacturing",
    "Industrial Services",
    "Commercial Services",
    "Distribution Services",
    "Transportation",
    "Utilities",
    "Communications",
    "Process Industries",
    "Non-Energy Minerals",
    "Miscellaneous",
]

# Map TradingView sectors to GICS-like display names for reports
SECTOR_DISPLAY_NAMES = {
    "Electronic Technology": "Technology (Hardware/Semis)",
    "Technology Services": "Technology (Software/Services)",
    "Health Technology": "Healthcare (Biotech/Pharma)",
    "Health Services": "Healthcare (Services)",
    "Finance": "Financials",
    "Energy Minerals": "Energy",
    "Consumer Durables": "Consumer Discretionary (Durables)",
    "Consumer Non-Durables": "Consumer Staples",
    "Consumer Services": "Consumer Discretionary (Services)",
    "Retail Trade": "Consumer Discretionary (Retail)",
    "Producer Manufacturing": "Industrials (Manufacturing)",
    "Industrial Services": "Industrials (Services)",
    "Commercial Services": "Industrials (Commercial)",
    "Distribution Services": "Industrials (Distribution)",
    "Transportation": "Industrials (Transportation)",
    "Utilities": "Utilities",
    "Communications": "Communication Services",
    "Process Industries": "Materials (Process)",
    "Non-Energy Minerals": "Materials (Mining)",
    "Miscellaneous": "Other",
}

# Sector groupings for high-level analysis
SECTOR_GROUPS = {
    "Technology": ["Electronic Technology", "Technology Services"],
    "Healthcare": ["Health Technology", "Health Services"],
    "Financials": ["Finance"],
    "Energy": ["Energy Minerals"],
    "Consumer Discretionary": ["Consumer Durables", "Consumer Services", "Retail Trade"],
    "Consumer Staples": ["Consumer Non-Durables"],
    "Industrials": ["Producer Manufacturing", "Industrial Services", "Commercial Services", "Distribution Services", "Transportation"],
    "Utilities": ["Utilities"],
    "Communication Services": ["Communications"],
    "Materials": ["Process Industries", "Non-Energy Minerals"],
}


def _fetch_sector_candidates(
    sector: str,
    direction: str,
    market: str,
    min_price: float,
    min_market_cap: int,
    limit: int,
) -> list[dict]:
    """Fetch raw candidates from TradingView for a single sector and direction."""
    try:
        from tradingview_screener import Query, col
    except ImportError:
        logger.error("tradingview-screener not available")
        return []

    try:
        fields = [
            "name", "close", "volume", "market_cap_basic", "change",
            "change_abs", "Recommend.All", "sector", "industry",
            "RSI", "RSI[1]", "MACD.macd", "MACD.signal",
            "SMA20", "SMA50", "SMA200", "EMA20", "EMA50",
            "relative_volume_10d_calc",
            "price_52_week_high", "price_52_week_low",
            "BB.upper", "BB.lower", "ADX", "ATR",
            "Perf.3M", "Perf.1M", "High.1M", "Low.1M",
        ]

        query = Query().select(*fields)
        if market and market != "both":
            query = query.set_markets(market)

        conditions = [
            col("sector") == sector,
            col("close") >= min_price,
            col("market_cap_basic") >= min_market_cap,
            col("volume") >= 100_000,
            col("type") == "stock",
        ]

        if direction == "LONG":
            conditions.append(col("Recommend.All") > 0)
            conditions.append(col("Perf.3M") < 50)
            conditions.append(col("Perf.1M") < 30)
        else:
            conditions.append(col("Recommend.All") < 0)
            conditions.append(col("Perf.3M") > -40)
            conditions.append(col("Perf.1M") > -25)

        query = query.where(*conditions)

        if direction == "LONG":
            query = query.order_by("Recommend.All", ascending=False)
        else:
            query = query.order_by("Recommend.All", ascending=True)

        query = query.limit(limit)
        count, df = query.get_scanner_data()

        if df.empty:
            return []

        results = []
        import pandas as pd

        def safe_val(val, default=0):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default
            return val

        for _, row in df.iterrows():
            price = safe_val(row.get("close"), 0)
            if price < min_price:
                continue
            results.append({
                "symbol": row.get("name", "UNKNOWN"),
                "price": round(price, 2),
                "change_pct": round(safe_val(row.get("change"), 0), 2),
                "volume": int(safe_val(row.get("volume"), 0)),
                "market_cap": int(safe_val(row.get("market_cap_basic"), 0)),
                "sector": row.get("sector", sector),
                "industry": row.get("industry", "Unknown"),
                "rsi": round(safe_val(row.get("RSI"), 50), 1),
                "adx": round(safe_val(row.get("ADX"), 0), 1),
                "recommend_all": round(safe_val(row.get("Recommend.All"), 0), 3),
                "rel_volume": round(safe_val(row.get("relative_volume_10d_calc"), 1), 2),
                "perf_1m": round(safe_val(row.get("Perf.1M"), 0), 1),
                "perf_3m": round(safe_val(row.get("Perf.3M"), 0), 1),
            })

        return results

    except Exception as e:
        logger.warning(f"Sector scan failed for {sector} ({direction}): {e}")
        return []


def _validate_candidates_through_gates(
    candidates: list[dict],
    direction: str,
    max_validate: int,
    progress_callback=None,
) -> list[dict]:
    """Run 5-gate validation on a list of candidates.

    Returns only candidates passing 3+ gates, enriched with full signal data.
    """
    from .signals import fetch_analysis_data, generate_trading_signal_impl as generate_trading_signal

    validated = []
    for i, cand in enumerate(candidates[:max_validate]):
        symbol = cand["symbol"]
        if progress_callback:
            progress_callback(f"[{direction} {i+1}/{min(len(candidates), max_validate)}] Validating {symbol}...")

        try:
            cached_data = fetch_analysis_data(symbol)
            signal = generate_trading_signal(
                ticker=symbol,
                direction=direction,
                report_type="scanner",
                cached_data=cached_data,
            )
            gate_status = signal.get("gate_status", {})
            gates_passed = sum(1 for g in gate_status.values() if g == "PASS")

            if gates_passed >= 3:
                validated.append({
                    "symbol": symbol,
                    "sector": cand.get("sector"),
                    "industry": cand.get("industry"),
                    "price": signal.get("current_price") or cand.get("price"),
                    "direction": direction,
                    "signal": signal.get("signal"),
                    "confidence": signal.get("confidence", 0),
                    "gates_passed": gates_passed,
                    "gate_status": gate_status,
                    "vehicle": signal.get("vehicle", "STOCK"),
                    "trading_plan": signal.get("trading_plan"),
                    "catalyst_analysis": signal.get("catalyst_analysis"),
                    "freshness_analysis": signal.get("freshness_analysis"),
                    "brooks_analysis": signal.get("brooks_analysis"),
                    "quality_analysis": signal.get("quality_analysis"),
                    "gate_5_analysis": signal.get("gate_5_analysis"),
                })
                if progress_callback:
                    progress_callback(f"   ✅ {symbol}: {gates_passed}/5 gates PASSED")
            else:
                if progress_callback:
                    progress_callback(f"   ❌ {symbol}: {gates_passed}/5 gates")

        except Exception as e:
            if progress_callback:
                progress_callback(f"   ⚠️ {symbol} error: {str(e)[:60]}")

    return validated


def _generate_sector_analysis(sector_data: dict, market_regime: dict) -> dict:
    """Generate AI expert analysis for a sector based on collected data.

    Uses signal strength from raw candidate metrics (recommend_all, change_pct,
    perf_1m, RSI) to determine real sector bias - not just candidate counts.
    """
    longs = sector_data.get("longs", [])
    shorts = sector_data.get("shorts", [])

    # Calculate REAL signal strength from candidate metrics
    # Long strength: average of recommend_all (0 to 1), change_pct, 1m performance
    long_signal_strength = 0.0
    if longs:
        for c in longs:
            rec = abs(c.get("recommend_all", 0))  # 0-1 scale
            chg = max(0, c.get("change_pct", 0)) / 5  # normalize: 5% = 1.0
            perf_1m = max(0, c.get("perf_1m", 0)) / 20  # normalize: 20% = 1.0
            perf_3m = max(0, c.get("perf_3m", 0)) / 30  # normalize: 30% = 1.0
            vol_ratio = min(2, c.get("rel_volume", 1))  # volume confirmation
            long_signal_strength += (rec * 0.3 + chg * 0.2 + perf_1m * 0.25 + perf_3m * 0.15 + vol_ratio * 0.1)
        long_signal_strength /= len(longs)

    short_signal_strength = 0.0
    if shorts:
        for c in shorts:
            rec = abs(c.get("recommend_all", 0))  # 0-1 scale
            chg = abs(min(0, c.get("change_pct", 0))) / 5  # negative change = short strength
            perf_1m = abs(min(0, c.get("perf_1m", 0))) / 20  # negative 1m = short strength
            perf_3m = abs(min(0, c.get("perf_3m", 0))) / 30
            # Low RSI strengthens short signal
            rsi_weak = max(0, (50 - c.get("rsi", 50))) / 30  # RSI 20 = 1.0
            short_signal_strength += (rec * 0.25 + chg * 0.2 + perf_1m * 0.25 + perf_3m * 0.15 + rsi_weak * 0.15)
        short_signal_strength /= len(shorts)

    # Also check if validated gates exist (for validation-enabled scans)
    long_gate_strength = sum(c.get("confidence", 0) for c in longs) if longs else 0
    short_gate_strength = sum(c.get("confidence", 0) for c in shorts) if shorts else 0
    has_validation = any(c.get("gates_passed", 0) > 0 for c in longs + shorts)

    # Use gate-based strength if validation was run, otherwise use signal strength
    if has_validation:
        bull_score = long_gate_strength
        bear_score = short_gate_strength
    else:
        bull_score = long_signal_strength
        bear_score = short_signal_strength

    # Determine bias using strength differential
    strength_ratio = bull_score / bear_score if bear_score > 0 else (10 if bull_score > 0 else 1)

    if strength_ratio >= 2.5:
        bias = "BULLISH"
        bias_reason = f"Strong long signals ({bull_score:.2f}) vs weak shorts ({bear_score:.2f})"
    elif strength_ratio >= 1.5:
        bias = "LEAN_BULLISH"
        bias_reason = f"Longs ({bull_score:.2f}) outpace shorts ({bear_score:.2f})"
    elif strength_ratio <= 0.4:
        bias = "BEARISH"
        bias_reason = f"Strong short signals ({bear_score:.2f}) vs weak longs ({bull_score:.2f})"
    elif strength_ratio <= 0.67:
        bias = "LEAN_BEARISH"
        bias_reason = f"Shorts ({bear_score:.2f}) outpace longs ({bull_score:.2f})"
    else:
        bias = "MIXED"
        bias_reason = f"Balanced signals - longs ({bull_score:.2f}) vs shorts ({bear_score:.2f})"

    # No candidates at all
    if not longs and not shorts:
        bias = "SKIP"
        bias_reason = "No candidates found"

    # Calculate sector score (0-100) based on overall opportunity quality
    opportunity_count = len(longs) + len(shorts)
    avg_confidence = 0
    if has_validation and opportunity_count > 0:
        avg_confidence = (long_gate_strength + short_gate_strength) / opportunity_count

    gate_quality = 0
    all_validated = longs + shorts
    if has_validation and all_validated:
        gate_quality = sum(c.get("gates_passed", 0) for c in all_validated) / len(all_validated) / 5 * 100

    # Score reflects directional conviction, not just opportunity count
    directional_strength = max(bull_score, bear_score)
    if has_validation:
        sector_score = min(100, int(
            opportunity_count * 8 +
            avg_confidence * 0.3 +
            gate_quality * 0.4
        ))
    else:
        # For raw scans, score based on signal quality
        sector_score = min(100, int(directional_strength * 100))

    # Recommendation
    if sector_score >= 70 and bias in ("BULLISH",):
        recommendation = "STRONG_BUY_SECTOR"
        action = "Overweight this sector - strong bullish momentum and signals"
    elif sector_score >= 70 and bias in ("BEARISH",):
        recommendation = "STRONG_SHORT_SECTOR"
        action = "Underweight this sector - strong bearish momentum and signals"
    elif sector_score >= 50 and bias in ("LEAN_BULLISH",):
        recommendation = "BUY_SECTOR"
        action = "Sector leaning bullish - accumulate quality longs"
    elif sector_score >= 50 and bias in ("LEAN_BEARISH",):
        recommendation = "SHORT_SECTOR"
        action = "Sector leaning bearish - consider shorts on rallies"
    elif bias == "MIXED" and sector_score >= 40:
        recommendation = "SELECTIVE"
        action = "Pick individual names - sector has mixed signals"
    elif opportunity_count == 0 or bias == "SKIP":
        recommendation = "SKIP"
        action = "No opportunities found - skip this sector"
    else:
        recommendation = "WATCH"
        action = "Monitor for developing setups - low conviction currently"

    return {
        "bias": bias,
        "bias_reason": bias_reason,
        "sector_score": sector_score,
        "recommendation": recommendation,
        "action": action,
        "bull_strength": round(bull_score, 3),
        "bear_strength": round(bear_score, 3),
        "strength_ratio": round(strength_ratio, 2),
        "avg_confidence": round(avg_confidence, 1),
        "gate_quality_pct": round(gate_quality, 1),
        "opportunity_count": opportunity_count,
    }


def _generate_executive_summary(
    all_sector_results: dict[str, dict],
    market_regime: dict,
    elapsed: float,
) -> str:
    """Generate the full markdown report as an AI expert analysis."""
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    lines = []

    lines.append("=" * 70)
    lines.append(f"  SECTOR MARKET SCAN - AI EXPERT ANALYSIS")
    lines.append(f"  {now.strftime('%Y-%m-%d %H:%M %Z')}")
    lines.append("=" * 70)
    lines.append("")

    # Market regime context
    regime = market_regime.get("regime", "UNKNOWN")
    vol = market_regime.get("volatility", 0)
    spy_trend = market_regime.get("spy_trend", "UNKNOWN")
    lines.append(f"MARKET REGIME: {regime} | SPY Trend: {spy_trend} | Volatility: {vol:.1f}%")
    lines.append("")

    # Rank sectors by score
    ranked = sorted(
        all_sector_results.items(),
        key=lambda x: x[1].get("analysis", {}).get("sector_score", 0),
        reverse=True,
    )

    # Top opportunities summary
    total_longs = sum(len(v.get("longs", [])) for v in all_sector_results.values())
    total_shorts = sum(len(v.get("shorts", [])) for v in all_sector_results.values())
    active_sectors = sum(1 for v in all_sector_results.values() if v.get("analysis", {}).get("opportunity_count", 0) > 0)

    lines.append(f"SUMMARY: {total_longs} LONG + {total_shorts} SHORT across {active_sectors} active sectors")
    lines.append(f"Scan time: {elapsed:.0f}s")
    lines.append("")

    # === HOT SECTORS ===
    hot_sectors = [(k, v) for k, v in ranked if v.get("analysis", {}).get("sector_score", 0) >= 50]
    if hot_sectors:
        lines.append("-" * 70)
        lines.append("  HOT SECTORS (Score >= 50)")
        lines.append("-" * 70)
        for sector_name, data in hot_sectors:
            analysis = data.get("analysis", {})
            display = SECTOR_DISPLAY_NAMES.get(sector_name, sector_name)
            lines.append(
                f"  {analysis.get('sector_score', 0):3d} | {analysis.get('bias', '?'):14s} | "
                f"{display} | {analysis.get('recommendation', '?')}"
            )
            lines.append(f"       {analysis.get('action', '')}")
            lines.append("")
    else:
        lines.append("  No hot sectors (score >= 50) found in this scan.")
        lines.append("")

    # === SECTOR-BY-SECTOR DETAIL ===
    lines.append("=" * 70)
    lines.append("  SECTOR-BY-SECTOR BREAKDOWN")
    lines.append("=" * 70)

    for sector_name, data in ranked:
        analysis = data.get("analysis", {})
        longs = data.get("longs", [])
        shorts = data.get("shorts", [])
        raw_l = data.get("raw_long_count", 0)
        raw_s = data.get("raw_short_count", 0)
        display = SECTOR_DISPLAY_NAMES.get(sector_name, sector_name)

        if analysis.get("opportunity_count", 0) == 0 and raw_l == 0 and raw_s == 0:
            continue  # Skip empty sectors

        lines.append("")
        lines.append(f"--- {display} ---")
        lines.append(
            f"Score: {analysis.get('sector_score', 0)} | Bias: {analysis.get('bias', '?')} | "
            f"Raw: {raw_l}L/{raw_s}S | Validated: {len(longs)}L/{len(shorts)}S"
        )
        lines.append(f"Recommendation: {analysis.get('recommendation', '?')} - {analysis.get('action', '')}")

        if longs:
            lines.append(f"  LONGS:")
            for c in longs[:3]:
                chg = c.get("change_pct", 0)
                p1m = c.get("perf_1m", 0)
                rsi = c.get("rsi", 0)
                rec = c.get("recommend_all", 0)
                if c.get("gates_passed", 0) > 0:
                    lines.append(
                        f"    {c['symbol']:6s} ${c.get('price', 0):8.2f} | "
                        f"{c.get('gates_passed', 0)}/5 gates | "
                        f"Signal: {c.get('signal', '?')} | "
                        f"Conf: {c.get('confidence', 0)}%"
                    )
                else:
                    lines.append(
                        f"    {c['symbol']:6s} ${c.get('price', 0):8.2f} | "
                        f"Chg: {chg:+.1f}% | 1M: {p1m:+.1f}% | RSI: {rsi:.0f} | "
                        f"Rec: {rec:+.2f}"
                    )

        if shorts:
            lines.append(f"  SHORTS:")
            for c in shorts[:3]:
                chg = c.get("change_pct", 0)
                p1m = c.get("perf_1m", 0)
                rsi = c.get("rsi", 0)
                rec = c.get("recommend_all", 0)
                if c.get("gates_passed", 0) > 0:
                    lines.append(
                        f"    {c['symbol']:6s} ${c.get('price', 0):8.2f} | "
                        f"{c.get('gates_passed', 0)}/5 gates | "
                        f"Signal: {c.get('signal', '?')} | "
                        f"Conf: {c.get('confidence', 0)}%"
                    )
                else:
                    lines.append(
                        f"    {c['symbol']:6s} ${c.get('price', 0):8.2f} | "
                        f"Chg: {chg:+.1f}% | 1M: {p1m:+.1f}% | RSI: {rsi:.0f} | "
                        f"Rec: {rec:+.2f}"
                    )

    # === AI EXPERT RECOMMENDATIONS ===
    lines.append("")
    lines.append("=" * 70)
    lines.append("  AI EXPERT RECOMMENDATIONS")
    lines.append("=" * 70)
    lines.append("")

    # Rotation signals
    bullish_sectors = [s for s, d in ranked if d.get("analysis", {}).get("bias", "") in ("BULLISH", "LEAN_BULLISH")]
    bearish_sectors = [s for s, d in ranked if d.get("analysis", {}).get("bias", "") in ("BEARISH", "LEAN_BEARISH")]

    if bullish_sectors:
        lines.append("ROTATE INTO:")
        for s in bullish_sectors[:5]:
            display = SECTOR_DISPLAY_NAMES.get(s, s)
            score = all_sector_results[s].get("analysis", {}).get("sector_score", 0)
            lines.append(f"  + {display} (score: {score})")
        lines.append("")

    if bearish_sectors:
        lines.append("ROTATE OUT OF:")
        for s in bearish_sectors[:5]:
            display = SECTOR_DISPLAY_NAMES.get(s, s)
            score = all_sector_results[s].get("analysis", {}).get("sector_score", 0)
            lines.append(f"  - {display} (score: {score})")
        lines.append("")

    # Top picks across all sectors
    all_longs = []
    all_shorts = []
    for sname, sdata in all_sector_results.items():
        for c in sdata.get("longs", []):
            c["_sector"] = sname
            all_longs.append(c)
        for c in sdata.get("shorts", []):
            c["_sector"] = sname
            all_shorts.append(c)

    # Sort by confidence if validated, otherwise by signal strength
    def _long_sort_key(x):
        if x.get("confidence", 0) > 0:
            return x["confidence"]
        # Composite: recommend strength + momentum + change
        return abs(x.get("recommend_all", 0)) * 3 + max(0, x.get("change_pct", 0)) + max(0, x.get("perf_1m", 0)) / 5

    def _short_sort_key(x):
        if x.get("confidence", 0) > 0:
            return x["confidence"]
        return abs(x.get("recommend_all", 0)) * 3 + abs(min(0, x.get("change_pct", 0))) + abs(min(0, x.get("perf_1m", 0))) / 5

    all_longs.sort(key=_long_sort_key, reverse=True)
    all_shorts.sort(key=_short_sort_key, reverse=True)

    if all_longs:
        lines.append("TOP LONG PICKS (cross-sector):")
        for i, c in enumerate(all_longs[:5], 1):
            display = SECTOR_DISPLAY_NAMES.get(c.get("_sector", ""), c.get("_sector", "?"))
            chg = c.get("change_pct", 0)
            p1m = c.get("perf_1m", 0)
            if c.get("confidence", 0) > 0:
                lines.append(
                    f"  #{i} {c['symbol']:6s} | {display} | "
                    f"Conf: {c.get('confidence', 0)}% | "
                    f"{c.get('gates_passed', 0)}/5 gates"
                )
            else:
                lines.append(
                    f"  #{i} {c['symbol']:6s} | {display} | "
                    f"${c.get('price', 0):.2f} | Chg: {chg:+.1f}% | 1M: {p1m:+.1f}%"
                )
        lines.append("")

    if all_shorts:
        lines.append("TOP SHORT PICKS (cross-sector):")
        for i, c in enumerate(all_shorts[:5], 1):
            display = SECTOR_DISPLAY_NAMES.get(c.get("_sector", ""), c.get("_sector", "?"))
            chg = c.get("change_pct", 0)
            p1m = c.get("perf_1m", 0)
            if c.get("confidence", 0) > 0:
                lines.append(
                    f"  #{i} {c['symbol']:6s} | {display} | "
                    f"Conf: {c.get('confidence', 0)}% | "
                    f"{c.get('gates_passed', 0)}/5 gates"
                )
            else:
                lines.append(
                    f"  #{i} {c['symbol']:6s} | {display} | "
                    f"${c.get('price', 0):.2f} | Chg: {chg:+.1f}% | 1M: {p1m:+.1f}%"
                )
        lines.append("")

    # Market regime alignment warning
    if regime == "BEAR_TREND" and total_longs > total_shorts:
        lines.append("⚠️ WARNING: More longs than shorts in BEAR market regime - exercise caution with longs")
    elif regime == "BULL_TREND" and total_shorts > total_longs:
        lines.append("⚠️ WARNING: More shorts than longs in BULL market regime - exercise caution with shorts")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def register_tools(mcp):
    """Register sector scanning tools with MCP server."""
    from ..tradingview_scanner import SCREENER_AVAILABLE
    from .scanning import detect_market_regime

    @mcp.tool()
    def scan_market_by_sector(
        sectors: list[str] = None,
        market: Literal["america", "canada", "both"] = "both",
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000,
        candidates_per_sector: int = 10,
        validate_top_n: int = 5,
        include_validation: bool = True,
    ) -> dict[str, Any]:
        """
        Scan the market sector-by-sector, collect LONGs and SHORTs, classify
        by sector, and generate an AI expert analysis with recommendations.

        This is the sector rotation analysis tool. It:
        1. Scans each GICS-like sector independently for LONG and SHORT setups
        2. Runs 5-gate validation on top candidates per sector
        3. Classifies sector bias (BULLISH/BEARISH/MIXED)
        4. Generates cross-sector rotation recommendations
        5. Ranks top picks across all sectors

        Sector Bias Classification:
            - BULLISH: Only validated longs, no shorts
            - BEARISH: Only validated shorts, no longs
            - LEAN_BULLISH: Longs dominate 2:1+
            - LEAN_BEARISH: Shorts dominate 2:1+
            - MIXED: Both directions present
            - SKIP: No validated opportunities

        AI Expert Recommendations:
            - STRONG_BUY_SECTOR: Score >= 70, bullish bias -> overweight
            - STRONG_SHORT_SECTOR: Score >= 70, bearish bias -> underweight
            - SELECTIVE: Score >= 50, pick individual names
            - WATCH: Low conviction, monitor
            - SKIP: No opportunities

        Args:
            sectors: Optional list of specific sectors to scan. If None, scans all 20 sectors.
                     Use TradingView sector names: "Electronic Technology", "Technology Services",
                     "Health Technology", "Finance", "Energy Minerals", etc.
                     Or use group names: "Technology", "Healthcare", "Financials", "Energy",
                     "Consumer Discretionary", "Industrials", "Utilities", "Materials",
                     "Communication Services", "Consumer Staples"
            market: Market to scan - "america", "canada", or "both"
            min_price: Minimum stock price (default: $2)
            min_market_cap: Minimum market cap (default: $1B)
            candidates_per_sector: Raw candidates to fetch per sector per direction (default: 10)
            validate_top_n: How many top candidates per sector to run through 5-gate validation (default: 5)
            include_validation: Run 5-gate validation on top candidates (default: True).
                               Set to False for a fast raw scan without validation.

        Returns:
            Dictionary with:
            - scan_time: Timestamp
            - market_regime: Current market regime
            - sectors_scanned: Number of sectors scanned
            - total_longs: Total validated long candidates
            - total_shorts: Total validated short candidates
            - sector_results: Per-sector breakdown with analysis
            - top_longs: Cross-sector top long picks (sorted by confidence)
            - top_shorts: Cross-sector top short picks (sorted by confidence)
            - sector_rankings: Sectors ranked by opportunity score
            - rotation_signals: Sectors to rotate into/out of
            - report: Full AI expert analysis as formatted text
        """
        if not SCREENER_AVAILABLE:
            raise ValueError(
                "TradingView scanner not available. Install with: pip install tradingview-screener"
            )

        et = pytz.timezone("America/New_York")
        scan_start = time.time()
        progress_log = []

        def log_progress(msg: str):
            logger.info(msg)
            progress_log.append(f"[{time.time() - scan_start:.0f}s] {msg}")

        # Resolve sector list
        sectors_to_scan = []
        if sectors:
            for s in sectors:
                if s in SECTOR_GROUPS:
                    sectors_to_scan.extend(SECTOR_GROUPS[s])
                elif s in TRADINGVIEW_SECTORS:
                    sectors_to_scan.append(s)
                else:
                    # Try fuzzy match
                    matched = [tv for tv in TRADINGVIEW_SECTORS if s.lower() in tv.lower()]
                    if matched:
                        sectors_to_scan.extend(matched)
                    else:
                        log_progress(f"⚠️ Unknown sector: {s} - skipping")
            sectors_to_scan = list(dict.fromkeys(sectors_to_scan))  # dedupe
        else:
            sectors_to_scan = TRADINGVIEW_SECTORS[:]

        log_progress(f"Scanning {len(sectors_to_scan)} sectors across {market.upper()} markets")

        # Detect market regime
        market_regime = detect_market_regime()
        log_progress(f"Market Regime: {market_regime.get('regime', '?')} | SPY Vol: {market_regime.get('volatility', 0):.1f}%")

        # Scan each sector
        all_sector_results = {}
        markets_to_scan = ["america", "canada"] if market == "both" else [market]

        for idx, sector in enumerate(sectors_to_scan, 1):
            display = SECTOR_DISPLAY_NAMES.get(sector, sector)
            log_progress(f"")
            log_progress(f"━━━ [{idx}/{len(sectors_to_scan)}] {display} ━━━")

            sector_longs_raw = []
            sector_shorts_raw = []

            for mkt in markets_to_scan:
                sector_longs_raw.extend(
                    _fetch_sector_candidates(sector, "LONG", mkt, min_price, min_market_cap, candidates_per_sector)
                )
                sector_shorts_raw.extend(
                    _fetch_sector_candidates(sector, "SHORT", mkt, min_price, min_market_cap, candidates_per_sector)
                )

            log_progress(f"  Raw: {len(sector_longs_raw)} LONG, {len(sector_shorts_raw)} SHORT")

            # Validate through 5-gate system
            validated_longs = []
            validated_shorts = []

            if include_validation and (sector_longs_raw or sector_shorts_raw):
                # Sort by recommendation strength before validation
                sector_longs_raw.sort(key=lambda x: abs(x.get("recommend_all", 0)), reverse=True)
                sector_shorts_raw.sort(key=lambda x: abs(x.get("recommend_all", 0)), reverse=True)

                if sector_longs_raw:
                    validated_longs = _validate_candidates_through_gates(
                        sector_longs_raw, "LONG", validate_top_n, log_progress,
                    )

                if sector_shorts_raw:
                    validated_shorts = _validate_candidates_through_gates(
                        sector_shorts_raw, "SHORT", validate_top_n, log_progress,
                    )

                log_progress(f"  Validated: {len(validated_longs)} LONG, {len(validated_shorts)} SHORT")
            elif not include_validation:
                # Fast mode: use raw data without validation
                validated_longs = [
                    {**c, "direction": "LONG", "gates_passed": 0, "gate_status": {}, "signal": "UNVALIDATED", "confidence": 0, "vehicle": "STOCK"}
                    for c in sector_longs_raw[:validate_top_n]
                ]
                validated_shorts = [
                    {**c, "direction": "SHORT", "gates_passed": 0, "gate_status": {}, "signal": "UNVALIDATED", "confidence": 0, "vehicle": "STOCK"}
                    for c in sector_shorts_raw[:validate_top_n]
                ]

            sector_data = {
                "raw_long_count": len(sector_longs_raw),
                "raw_short_count": len(sector_shorts_raw),
                "longs": validated_longs,
                "shorts": validated_shorts,
            }

            # Generate per-sector analysis
            sector_data["analysis"] = _generate_sector_analysis(sector_data, market_regime)
            all_sector_results[sector] = sector_data

        elapsed = time.time() - scan_start

        # Aggregate cross-sector results
        all_longs = []
        all_shorts = []
        for sname, sdata in all_sector_results.items():
            for c in sdata.get("longs", []):
                c["sector"] = sname
                c["sector_display"] = SECTOR_DISPLAY_NAMES.get(sname, sname)
                all_longs.append(c)
            for c in sdata.get("shorts", []):
                c["sector"] = sname
                c["sector_display"] = SECTOR_DISPLAY_NAMES.get(sname, sname)
                all_shorts.append(c)

        all_longs.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        all_shorts.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        # Sector rankings
        sector_rankings = []
        for sname, sdata in all_sector_results.items():
            analysis = sdata.get("analysis", {})
            sector_rankings.append({
                "sector": sname,
                "display_name": SECTOR_DISPLAY_NAMES.get(sname, sname),
                "score": analysis.get("sector_score", 0),
                "bias": analysis.get("bias", "?"),
                "recommendation": analysis.get("recommendation", "?"),
                "longs": len(sdata.get("longs", [])),
                "shorts": len(sdata.get("shorts", [])),
                "raw_longs": sdata.get("raw_long_count", 0),
                "raw_shorts": sdata.get("raw_short_count", 0),
            })
        sector_rankings.sort(key=lambda x: x["score"], reverse=True)

        # Rotation signals
        rotate_into = [r for r in sector_rankings if r["bias"] in ("BULLISH", "LEAN_BULLISH") and r["score"] >= 50]
        rotate_out_of = [r for r in sector_rankings if r["bias"] in ("BEARISH", "LEAN_BEARISH") and r["score"] >= 50]

        # Generate report
        report = _generate_executive_summary(all_sector_results, market_regime, elapsed)

        log_progress(f"")
        log_progress(f"Scan complete: {len(all_longs)} longs + {len(all_shorts)} shorts in {elapsed:.0f}s")

        return convert_numpy_types({
            "scan_time": datetime.now(et).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "market_regime": market_regime,
            "market": market,
            "sectors_scanned": len(sectors_to_scan),
            "total_longs": len(all_longs),
            "total_shorts": len(all_shorts),
            "elapsed_seconds": round(elapsed, 1),
            "validation_enabled": include_validation,
            "sector_results": {
                sname: {
                    "display_name": SECTOR_DISPLAY_NAMES.get(sname, sname),
                    "analysis": sdata.get("analysis", {}),
                    "raw_long_count": sdata.get("raw_long_count", 0),
                    "raw_short_count": sdata.get("raw_short_count", 0),
                    "longs": sdata.get("longs", []),
                    "shorts": sdata.get("shorts", []),
                }
                for sname, sdata in all_sector_results.items()
            },
            "top_longs": all_longs[:10],
            "top_shorts": all_shorts[:10],
            "sector_rankings": sector_rankings,
            "rotation_signals": {
                "rotate_into": [
                    {"sector": r["display_name"], "score": r["score"], "bias": r["bias"]}
                    for r in rotate_into
                ],
                "rotate_out_of": [
                    {"sector": r["display_name"], "score": r["score"], "bias": r["bias"]}
                    for r in rotate_out_of
                ],
            },
            "progress_log": progress_log,
            "report": report,
        })
