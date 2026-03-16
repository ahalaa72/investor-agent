"""Trading prediction tracking tools: store, retrieve, validate predictions and generate reports."""
import logging
import json
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path

import numpy as np
import yfinance as yf

from ..core.price import get_current_price_questrade_first, convert_numpy_types

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Recent predictions cache (used by scanner to skip re-analysis)
# ---------------------------------------------------------------------------

def _get_recent_predictions(direction: str, days: int = 7) -> dict[str, dict]:
    """
    Get predictions from DB for the last N days.

    Used by scanner to skip re-analysis of recently validated tickers.

    Args:
        direction: "LONG" or "SHORT"
        days: Number of days to look back (default 7)

    Returns:
        Dict mapping ticker -> prediction data (most recent per ticker)
    """
    from ..database import execute_query

    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    query = """
        SELECT
            ticker, direction, signal, confidence_score, gates_passed,
            gate_catalyst, gate_freshness, gate_brooks, gate_quality,
            entry_price, stop_price, target_1_price, target_2_price,
            catalyst_direction, catalyst_strength,
            dalio_ratio, dalio_interpretation,
            brooks_probability, brooks_pattern, trap_risk,
            quality_score, quality_grade, f_score, z_score,
            data_direction, created_at
        FROM predictions
        WHERE direction = :direction
          AND prediction_date >= :cutoff_date
          AND report_type = 'scanner'
        ORDER BY created_at DESC
    """

    try:
        rows = execute_query(query, {"direction": direction, "cutoff_date": cutoff_date})

        # Build lookup dict - use most recent prediction per ticker
        result = {}
        for row in rows:
            ticker = row['ticker']
            if ticker not in result:  # Only keep most recent
                result[ticker] = {
                    'signal': row['signal'],
                    'confidence': row['confidence_score'],
                    'gates_passed': row['gates_passed'],
                    'gate_status': {
                        'catalyst': row['gate_catalyst'],
                        'freshness': row['gate_freshness'],
                        'brooks': row['gate_brooks'],
                        'quality': row['gate_quality']
                    },
                    'entry_price': float(row['entry_price']) if row['entry_price'] else None,
                    'stop_price': float(row['stop_price']) if row['stop_price'] else None,
                    'target_1': float(row['target_1_price']) if row['target_1_price'] else None,
                    'target_2': float(row['target_2_price']) if row['target_2_price'] else None,
                    'catalyst_direction': row['catalyst_direction'],
                    'catalyst_strength': row['catalyst_strength'],
                    'dalio_ratio': float(row['dalio_ratio']) if row['dalio_ratio'] else None,
                    'dalio_interpretation': row['dalio_interpretation'],
                    'brooks_probability': float(row['brooks_probability']) if row['brooks_probability'] else None,
                    'brooks_pattern': row['brooks_pattern'],
                    'trap_risk': row['trap_risk'],
                    'quality_score': float(row['quality_score']) if row['quality_score'] else None,
                    'quality_grade': row['quality_grade'],
                    'f_score': row['f_score'],
                    'z_score': float(row['z_score']) if row['z_score'] else None,
                    'data_direction': row['data_direction'],
                    'stored_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'is_repeated': True
                }

        logger.info(f"DB Cache: Found {len(result)} {direction} predictions from last {days} days")
        return result

    except Exception as e:
        logger.warning(f"Failed to fetch recent predictions from DB: {e}")
        return {}


# =============================================================================
# RANKING VALIDATION SYSTEM
# =============================================================================

# Performance tracking storage (in-memory, persisted to JSON)
_pick_history: list[dict] = []
_pick_history_file = Path(__file__).parent.parent / "pick_history.json"


def _load_pick_history():
    """Load pick history from JSON file."""
    global _pick_history
    if _pick_history_file.exists():
        try:
            with open(_pick_history_file, 'r') as f:
                _pick_history = json.load(f)
            logger.info(f"Loaded {len(_pick_history)} picks from history")
        except Exception as e:
            logger.warning(f"Failed to load pick history: {e}")
            _pick_history = []


def _save_pick_history():
    """Save pick history to JSON file."""
    try:
        with open(_pick_history_file, 'w') as f:
            json.dump(_pick_history, f, indent=2, default=str)
        logger.debug(f"Saved {len(_pick_history)} picks to history")
    except Exception as e:
        logger.warning(f"Failed to save pick history: {e}")


def track_scanner_pick(
    ticker: str,
    direction: str,
    composite_score: float,
    entry_price: float,
    stop_price: float,
    target_price: float,
    signal: str,
    scanner_source: str = "tradingview"
) -> dict:
    """
    Track a scanner pick for future performance validation.

    Args:
        ticker: Stock symbol
        direction: LONG or SHORT
        composite_score: Composite score from scanner (0-100)
        entry_price: Recommended entry price
        stop_price: Stop loss price
        target_price: Target price
        signal: Signal type (BUY, WATCH, SKIP, etc.)
        scanner_source: Data source (tradingview, finviz)

    Returns:
        dict: Pick record
    """
    from datetime import datetime
    import pytz

    et = pytz.timezone("America/New_York")
    now = datetime.now(et)

    pick = {
        "id": f"{ticker}_{now.strftime('%Y%m%d_%H%M%S')}",
        "ticker": ticker,
        "direction": direction,
        "composite_score": composite_score,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "signal": signal,
        "scanner_source": scanner_source,
        "picked_at": now.isoformat(),
        "picked_date": now.strftime("%Y-%m-%d"),
        # Forward returns (updated later)
        "return_5d": None,
        "return_10d": None,
        "return_20d": None,
        "hit_target": None,
        "hit_stop": None,
        "days_to_target": None,
        "days_to_stop": None,
        "outcome": None,  # WIN / LOSS / OPEN
        "validated": False
    }

    _pick_history.append(pick)
    _save_pick_history()

    return pick


def validate_pick_outcomes():
    """
    Validate outcomes for all tracked picks by fetching current prices.

    Updates forward returns and outcome status for each pick.
    """
    from datetime import datetime, timedelta
    import pytz

    from .scanning import _get_ohlcv_for_ticker_v2

    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    today = now.date()

    validated_count = 0

    for pick in _pick_history:
        if pick.get("validated"):
            continue

        pick_date = datetime.fromisoformat(pick["picked_at"]).date()
        days_since_pick = (today - pick_date).days

        if days_since_pick < 1:
            continue  # Need at least 1 day of data

        ticker = pick["ticker"]
        direction = pick["direction"]
        entry_price = pick["entry_price"]
        stop_price = pick["stop_price"]
        target_price = pick["target_price"]

        try:
            # Fetch price history since pick
            ohlcv = _get_ohlcv_for_ticker_v2(ticker, period="1mo")

            if ohlcv is None or ohlcv.empty:
                continue

            # Filter to dates after pick
            pick_datetime = datetime.fromisoformat(pick["picked_at"])
            ohlcv_after = ohlcv[ohlcv.index > pick_datetime]

            if ohlcv_after.empty:
                continue

            # Calculate forward returns
            closes = ohlcv_after['Close'].values
            current_price = closes[-1] if len(closes) > 0 else entry_price

            # 5d, 10d, 20d returns (invert for SHORT: profit when price drops)
            sign = -1 if direction == "SHORT" else 1
            if len(closes) >= 5:
                pick["return_5d"] = round(sign * (closes[4] - entry_price) / entry_price * 100, 2)
            if len(closes) >= 10:
                pick["return_10d"] = round(sign * (closes[9] - entry_price) / entry_price * 100, 2)
            if len(closes) >= 20:
                pick["return_20d"] = round(sign * (closes[19] - entry_price) / entry_price * 100, 2)
                pick["validated"] = True

            # Check if hit target or stop
            if direction == "LONG":
                highs = ohlcv_after['High'].values
                lows = ohlcv_after['Low'].values

                for i, (high, low) in enumerate(zip(highs, lows)):
                    if high >= target_price and pick["hit_target"] is None:
                        pick["hit_target"] = True
                        pick["days_to_target"] = i + 1
                    if low <= stop_price and pick["hit_stop"] is None:
                        pick["hit_stop"] = True
                        pick["days_to_stop"] = i + 1

            else:  # SHORT
                highs = ohlcv_after['High'].values
                lows = ohlcv_after['Low'].values

                for i, (high, low) in enumerate(zip(highs, lows)):
                    if low <= target_price and pick["hit_target"] is None:
                        pick["hit_target"] = True
                        pick["days_to_target"] = i + 1
                    if high >= stop_price and pick["hit_stop"] is None:
                        pick["hit_stop"] = True
                        pick["days_to_stop"] = i + 1

            # Determine outcome
            if pick["hit_target"] and not pick.get("hit_stop"):
                pick["outcome"] = "WIN"
            elif pick["hit_stop"] and not pick.get("hit_target"):
                pick["outcome"] = "LOSS"
            elif pick["hit_target"] and pick["hit_stop"]:
                # Both hit - check which came first
                if (pick.get("days_to_target") or 999) <= (pick.get("days_to_stop") or 999):
                    pick["outcome"] = "WIN"
                else:
                    pick["outcome"] = "LOSS"
            elif days_since_pick >= 20:
                # 20 days passed without hitting target or stop
                if direction == "LONG":
                    pick["outcome"] = "WIN" if current_price > entry_price else "LOSS"
                else:
                    pick["outcome"] = "WIN" if current_price < entry_price else "LOSS"
            else:
                pick["outcome"] = "OPEN"

            validated_count += 1

        except Exception as e:
            logger.warning(f"Failed to validate {ticker}: {e}")
            continue

    _save_pick_history()
    return validated_count


def _auto_track_picks(result: dict, scanner_source: str = "tradingview"):
    """Automatically track picks from scan results."""
    for direction in ["long_candidates", "short_candidates"]:
        candidates = result.get(direction, [])
        for c in candidates[:3]:  # Only track top 3
            try:
                brooks = c.get("brooks_analysis", {})
                track_scanner_pick(
                    ticker=c.get("symbol", "UNKNOWN"),
                    direction="LONG" if "long" in direction else "SHORT",
                    composite_score=c.get("composite_score", 0),
                    entry_price=brooks.get("entry", c.get("price", 0)),
                    stop_price=brooks.get("stop", 0),
                    target_price=brooks.get("target", 0),
                    signal=c.get("recommendation", {}).get("label", "UNKNOWN"),
                    scanner_source=scanner_source
                )
            except Exception as e:
                logger.warning(f"Failed to track pick: {e}")


# Load history on module import
_load_pick_history()


def register_tools(mcp):
    @mcp.tool()
    def get_ranking_validation_report() -> dict:
        """
        Generate a comprehensive ranking validation report.

        Analyzes all tracked picks to show:
        - Overall win rate
        - Win rate by score bucket (60-70, 70-80, 80+)
        - Win rate by signal type (BUY, WATCH, SKIP)
        - Average returns by score bucket
        - Score-return correlation

        Returns:
            dict: Comprehensive validation report proving (or disproving) ranking quality
        """
        _load_pick_history()

        # Validate any unvalidated picks
        validated_count = validate_pick_outcomes()

        if not _pick_history:
            return {
                "status": "NO_DATA",
                "message": "No picks tracked yet. Scanner picks will be tracked automatically.",
                "how_to_track": "Run scan_market_opportunities() - picks are tracked automatically."
            }

        # Filter to picks with outcomes
        picks_with_outcome = [p for p in _pick_history if p.get("outcome") in ["WIN", "LOSS"]]

        if not picks_with_outcome:
            open_picks = [p for p in _pick_history if p.get("outcome") == "OPEN"]
            return {
                "status": "PENDING",
                "message": f"{len(open_picks)} picks tracked, waiting for 20-day validation period",
                "tracked_picks": len(_pick_history),
                "open_picks": len(open_picks)
            }

        # Calculate metrics
        total_picks = len(picks_with_outcome)
        wins = sum(1 for p in picks_with_outcome if p["outcome"] == "WIN")
        losses = total_picks - wins
        overall_win_rate = round(wins / total_picks * 100, 1) if total_picks > 0 else 0

        # Win rate by score bucket
        score_buckets = {
            "40-50": {"wins": 0, "total": 0, "returns": []},
            "50-60": {"wins": 0, "total": 0, "returns": []},
            "60-70": {"wins": 0, "total": 0, "returns": []},
            "70-80": {"wins": 0, "total": 0, "returns": []},
            "80+": {"wins": 0, "total": 0, "returns": []},
        }

        for p in picks_with_outcome:
            score = p.get("composite_score", 0)
            ret_20d = p.get("return_20d")

            if score >= 80:
                bucket = "80+"
            elif score >= 70:
                bucket = "70-80"
            elif score >= 60:
                bucket = "60-70"
            elif score >= 50:
                bucket = "50-60"
            else:
                bucket = "40-50"

            score_buckets[bucket]["total"] += 1
            if p["outcome"] == "WIN":
                score_buckets[bucket]["wins"] += 1
            if ret_20d is not None:
                score_buckets[bucket]["returns"].append(ret_20d)

        # Calculate bucket stats
        bucket_stats = {}
        for bucket, data in score_buckets.items():
            if data["total"] > 0:
                bucket_stats[bucket] = {
                    "total_picks": data["total"],
                    "wins": data["wins"],
                    "losses": data["total"] - data["wins"],
                    "win_rate": round(data["wins"] / data["total"] * 100, 1),
                    "avg_return": round(sum(data["returns"]) / len(data["returns"]), 2) if data["returns"] else None
                }

        # Win rate by signal type
        signal_stats = {}
        for signal_type in ["BUY", "WATCH", "SKIP", "NO_TRADE"]:
            signal_picks = [p for p in picks_with_outcome if p.get("signal") == signal_type]
            if signal_picks:
                signal_wins = sum(1 for p in signal_picks if p["outcome"] == "WIN")
                signal_stats[signal_type] = {
                    "total_picks": len(signal_picks),
                    "wins": signal_wins,
                    "win_rate": round(signal_wins / len(signal_picks) * 100, 1)
                }

        # Calculate correlation (simple linear)
        scores = [p.get("composite_score", 0) for p in picks_with_outcome if p.get("return_20d") is not None]
        returns = [p.get("return_20d") for p in picks_with_outcome if p.get("return_20d") is not None]

        correlation = None
        if len(scores) >= 5:
            try:
                import numpy as np
                correlation = round(np.corrcoef(scores, returns)[0, 1], 3)
            except:
                pass

        # Build report
        report = {
            "status": "OK",
            "summary": {
                "total_picks_tracked": len(_pick_history),
                "picks_with_outcome": total_picks,
                "open_picks": len([p for p in _pick_history if p.get("outcome") == "OPEN"]),
                "overall_win_rate": overall_win_rate,
                "total_wins": wins,
                "total_losses": losses
            },
            "score_bucket_analysis": bucket_stats,
            "signal_type_analysis": signal_stats,
            "score_return_correlation": correlation,
            "interpretation": {
                "ranking_quality": "GOOD" if overall_win_rate >= 55 else "NEEDS_IMPROVEMENT" if overall_win_rate >= 45 else "POOR",
                "correlation_strength": "STRONG" if correlation and correlation > 0.3 else "MODERATE" if correlation and correlation > 0.1 else "WEAK" if correlation else "UNKNOWN",
                "recommendation": "Higher scores DO correlate with better returns" if correlation and correlation > 0.1 else "Score correlation unclear - more data needed"
            },
            "validation_date": datetime.now().isoformat()
        }

        # Add markdown report
        md = f"""
## Scanner Ranking Validation Report

### Overall Performance
- **Total Picks**: {total_picks}
- **Win Rate**: {overall_win_rate}%
- **Wins**: {wins} | **Losses**: {losses}

### Win Rate by Score Bucket
"""
        for bucket, stats in bucket_stats.items():
            md += f"- **{bucket}**: {stats['win_rate']}% ({stats['wins']}/{stats['total_picks']} wins)"
            if stats['avg_return'] is not None:
                md += f" | Avg Return: {stats['avg_return']:+.1f}%"
            md += "\n"

        md += f"""
### Score-Return Correlation
- **Correlation**: {correlation if correlation else 'N/A'}
- **Interpretation**: {report['interpretation']['correlation_strength']}

### Conclusion
**Ranking Quality**: {report['interpretation']['ranking_quality']}
{report['interpretation']['recommendation']}
"""

        report["markdown_report"] = md

        return report

    @mcp.tool()
    def store_trading_prediction(
        ticker: str,
        direction: str,
        report_type: str,
        trading_signal: dict
    ) -> dict:
        """
        Store a trading prediction for outcome tracking and efficiency analysis.

        NOTE: This is now OPTIONAL - generate_trading_signal() auto-stores predictions by default.
        Use this only if you need to manually store a prediction with custom parameters.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            direction: Trade direction - "LONG" or "SHORT"
            report_type: Source report type - "comprehensive", "concise", "scanner", or "portfolio"
            trading_signal: Full output from generate_trading_signal()

        Returns:
            dict with:
            - status: "stored" or "error"
            - prediction_id: UUID of stored prediction
            - ticker, direction, report_type
            - entry_price: Entry price from trading plan
            - stored_at: ISO timestamp
            - components_stored: Which components were captured (catalyst, freshness, dalio, brooks, quality, options)
        """
        try:
            from ..prediction_tracker import PredictionTracker
            tracker = PredictionTracker()
            return tracker.store_prediction(
                trading_signal=trading_signal,
                report_type=report_type,
                ticker=ticker,
                direction=direction
            )
        except ImportError as e:
            return {
                "status": "error",
                "error": f"Prediction tracker not available: {e}",
                "ticker": ticker
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "ticker": ticker
            }

    @mcp.tool()
    def get_cached_predictions(
        direction: str,
        days: int = 7
    ) -> dict:
        """
        Get cached predictions from DB for the last N days.

        Use this BEFORE scanning to identify repeated tickers that can be skipped.
        This enables the optimized workflow:
        1. Call get_cached_predictions() to get DB cached tickers
        2. Filter raw candidates to get only NEW tickers
        3. Show repeated tickers with their stored data immediately
        4. Process only NEW tickers in batches with scan_long/short_candidates

        Args:
            direction: "LONG" or "SHORT"
            days: Number of days to look back (default 7)

        Returns:
            dict with:
            - direction: LONG or SHORT
            - days_lookback: Number of days searched
            - total_cached: Count of cached predictions
            - tickers: List of ticker symbols in cache
        """
        try:
            recent = _get_recent_predictions(direction.upper(), days=days)

            # Return ONLY ticker names - not full prediction data (too large)
            return {
                "direction": direction.upper(),
                "days_lookback": days,
                "total_cached": len(recent),
                "tickers": list(recent.keys())
            }
        except Exception as e:
            logger.warning(f"Failed to get cached predictions: {e}")
            return {
                "direction": direction.upper(),
                "days_lookback": days,
                "total_cached": 0,
                "tickers": [],
                "error": str(e)
            }

    @mcp.tool()
    def get_best_cached_trades(
        direction: str = "BOTH",
        days: int = 7,
        top_n: int = 10,
        min_gates: int = 3
    ) -> dict:
        """
        Get the best trading opportunities from cached predictions without re-scanning.

        Use this when you want to retrieve stored analysis results sorted by quality,
        without running a new market scan. Perfect for:
        - Quick review of best opportunities from recent scans
        - Identifying repeated high-quality setups (stronger confirmation)
        - Getting trade ideas when market is closed
        - Reviewing historical scan results

        Sorting Priority:
        1. composite_score (highest first)
        2. gates_passed (5/5 > 3/5)
        3. scan_count (more appearances = stronger signal)
        4. recency (most recent first)

        Args:
            direction: Trade direction filter - "LONG", "SHORT", or "BOTH" (default: "BOTH")
            days: Number of days to look back (default: 7)
            top_n: Maximum number of results to return (default: 10)
            min_gates: Minimum gates passed to include (default: 3, range: 0-4)

        Returns:
            dict with:
            - direction: Filter used (LONG/SHORT/BOTH)
            - days_lookback: Number of days searched
            - min_gates: Minimum gates filter applied
            - total_found: Total predictions matching criteria
            - returned: Number of results returned
            - trades: List of trade opportunities with full details:
                - ticker, direction, signal, composite_score
                - gates_passed, gate_status (catalyst/freshness/brooks/quality)
                - entry_price, stop_price, target_1, target_2
                - dalio_ratio, dalio_interpretation
                - brooks_probability, trap_risk
                - quality_score, quality_grade, f_score, z_score
                - scan_count (times appeared in scans)
                - last_scanned (most recent scan date)
        """
        from ..database import execute_query
        from datetime import datetime, timedelta

        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            direction = direction.upper()

            # Build direction filter
            if direction == "BOTH":
                direction_filter = "direction IN ('LONG', 'SHORT')"
                direction_params = {}
            else:
                direction_filter = "direction = :direction"
                direction_params = {"direction": direction}

            # Query with aggregation to get scan_count and most recent data
            # Use COALESCE to get the best available score (confidence_score has varied values)
            query = f"""
                WITH RankedPredictions AS (
                    SELECT
                        ticker,
                        direction,
                        signal,
                        confidence_score,
                        composite_score,
                        COALESCE(confidence_score, composite_score, 0) as best_score,
                        gates_passed,
                        gate_catalyst,
                        gate_freshness,
                        gate_brooks,
                        gate_quality,
                        entry_price,
                        stop_price,
                        target_1_price,
                        target_2_price,
                        catalyst_direction,
                        catalyst_strength,
                        dalio_ratio,
                        dalio_interpretation,
                        brooks_probability,
                        brooks_pattern,
                        trap_risk,
                        quality_score,
                        quality_grade,
                        f_score,
                        z_score,
                        data_direction,
                        created_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY ticker, direction
                            ORDER BY created_at DESC
                        ) as rn,
                        COUNT(*) OVER (PARTITION BY ticker, direction) as scan_count
                    FROM predictions
                    WHERE {direction_filter}
                      AND prediction_date >= :cutoff_date
                      AND report_type = 'scanner'
                      AND gates_passed >= :min_gates
                )
                SELECT
                    ticker,
                    direction,
                    signal,
                    confidence_score,
                    composite_score,
                    best_score,
                    gates_passed,
                    gate_catalyst,
                    gate_freshness,
                    gate_brooks,
                    gate_quality,
                    entry_price,
                    stop_price,
                    target_1_price,
                    target_2_price,
                    catalyst_direction,
                    catalyst_strength,
                    dalio_ratio,
                    dalio_interpretation,
                    brooks_probability,
                    brooks_pattern,
                    trap_risk,
                    quality_score,
                    quality_grade,
                    f_score,
                    z_score,
                    data_direction,
                    created_at,
                    scan_count
                FROM RankedPredictions
                WHERE rn = 1
                ORDER BY
                    CAST(created_at AS DATE) DESC,
                    best_score DESC,
                    gates_passed DESC,
                    scan_count DESC
            """

            params = {
                "cutoff_date": cutoff_date,
                "min_gates": min_gates,
                **direction_params
            }

            rows = execute_query(query, params)

            # Format results
            trades = []
            for row in rows[:top_n]:
                # Use best_score as the primary score for sorting/display
                best_score = float(row['best_score']) if row['best_score'] else 0
                trades.append({
                    "ticker": row['ticker'],
                    "direction": row['direction'],
                    "signal": row['signal'],
                    "score": best_score,  # Primary sorting score
                    "confidence_score": float(row['confidence_score']) if row['confidence_score'] else None,
                    "composite_score": float(row['composite_score']) if row['composite_score'] else None,
                    "gates_passed": row['gates_passed'],
                    "gate_status": {
                        "catalyst": row['gate_catalyst'],
                        "freshness": row['gate_freshness'],
                        "brooks": row['gate_brooks'],
                        "quality": row['gate_quality']
                    },
                    "entry_price": float(row['entry_price']) if row['entry_price'] else None,
                    "stop_price": float(row['stop_price']) if row['stop_price'] else None,
                    "target_1": float(row['target_1_price']) if row['target_1_price'] else None,
                    "target_2": float(row['target_2_price']) if row['target_2_price'] else None,
                    "catalyst_direction": row['catalyst_direction'],
                    "catalyst_strength": row['catalyst_strength'],
                    "dalio_ratio": float(row['dalio_ratio']) if row['dalio_ratio'] else None,
                    "dalio_interpretation": row['dalio_interpretation'],
                    "brooks_probability": float(row['brooks_probability']) if row['brooks_probability'] else None,
                    "brooks_pattern": row['brooks_pattern'],
                    "trap_risk": row['trap_risk'],
                    "quality_score": float(row['quality_score']) if row['quality_score'] else None,
                    "quality_grade": row['quality_grade'],
                    "f_score": row['f_score'],
                    "z_score": float(row['z_score']) if row['z_score'] else None,
                    "data_direction": row['data_direction'],
                    "scan_count": row['scan_count'],
                    "scan_date": row['created_at'].strftime('%Y-%m-%d') if row['created_at'] else None,
                    "last_scanned": row['created_at'].isoformat() if row['created_at'] else None
                })

            logger.info(f"Best Cached Trades: Found {len(rows)} {direction} trades, returning top {len(trades)}")

            return {
                "direction": direction,
                "days_lookback": days,
                "min_gates": min_gates,
                "total_found": len(rows),
                "returned": len(trades),
                "trades": trades
            }

        except Exception as e:
            logger.error(f"Failed to get best cached trades: {e}")
            return {
                "direction": direction,
                "days_lookback": days,
                "min_gates": min_gates,
                "total_found": 0,
                "returned": 0,
                "trades": [],
                "error": str(e)
            }

    @mcp.tool()
    def update_prediction_outcomes(
        prediction_id: str | None = None
    ) -> dict:
        """
        Update all open predictions with current prices and determine outcomes.

        Fetches current market prices and updates:
        - Returns at 5d, 10d, 20d horizons
        - Target/stop hit tracking
        - WIN/LOSS/OPEN outcome classification
        - Validates predictions after 20 days

        Args:
            prediction_id: Optional specific prediction UUID to update.
                          If None, updates ALL open predictions.

        Returns:
            dict with:
            - status: "updated" or "no_updates"
            - total_open: Number of open predictions
            - updated: Number successfully updated
            - newly_validated: Predictions that reached 20-day validation
            - outcomes: Count of WIN/LOSS/OPEN
            - updated_predictions: List of updated prediction details
        """
        try:
            from ..prediction_tracker import PredictionTracker
            tracker = PredictionTracker()
            return tracker.update_outcomes(prediction_id=prediction_id)
        except ImportError as e:
            return {
                "status": "error",
                "error": f"Prediction tracker not available: {e}"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    def generate_efficiency_report(
        period_days: int = 7,
        min_sample: int = 5
    ) -> dict:
        """
        Generate weekly efficiency report with component accuracy analysis.

        Analyzes all stored predictions to determine:
        - Overall win rate and average returns
        - Performance by report type (comprehensive, concise, scanner, portfolio)
        - Performance by signal type (STRONG_BUY, BUY, WATCH, etc.)
        - Performance by gates passed (4/4, 3/4, 2/4)
        - Individual gate accuracy (catalyst, freshness, brooks, quality)
        - Sub-component accuracy (cvd_trend, trap_risk, dalio_ratio, etc.)
        - Improvement suggestions for low-accuracy components

        Args:
            period_days: Number of days to analyze (default: 7 for weekly)
            min_sample: Minimum predictions required to generate report (default: 5)

        Returns:
            dict with:
            - status: "generated" or "insufficient_data"
            - report_date: Date of report
            - period: Date range analyzed
            - executive_summary: Key metrics overview
            - by_report_type: Performance breakdown by report type
            - by_signal: Performance breakdown by signal type
            - by_gates_passed: Performance breakdown by gates passed
            - gate_accuracy: Accuracy for each of 5 gates
            - component_accuracy: Accuracy for sub-components
            - improvement_suggestions: Auto-generated suggestions
            - historical_trend: Win rate trend over past 4 weeks
            - full_report_markdown: Complete report in markdown format
        """
        try:
            from ..prediction_tracker import EfficiencyReportGenerator
            generator = EfficiencyReportGenerator()
            return generator.generate_weekly_report(
                period_days=period_days,
                min_sample=min_sample
            )
        except ImportError as e:
            return {
                "status": "error",
                "error": f"Efficiency report generator not available: {e}"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    def update_prediction_report(
        prediction_id: str,
        report_markdown: str,
        quality_score: int = 0,
        quality_grade: str = "",
        vault_file: str = ""
    ) -> dict:
        """
        Attach the full analyst report to an existing prediction record.

        Called by the analyst pipeline after generating and saving the report.
        Updates the prediction that was auto-stored during generate_trading_signal().

        Args:
            prediction_id: UUID of the prediction to update
            report_markdown: Full markdown report from the analyst pipeline
            quality_score: Report quality gate score (0-100)
            quality_grade: Report quality grade (A/B/C/D/F)
            vault_file: Path to the saved vault file

        Returns:
            dict with status and prediction_id
        """
        try:
            from ..database import get_db_session
            from sqlalchemy import text

            with get_db_session() as session:
                result = session.execute(
                    text("""
                        UPDATE predictions
                        SET report_markdown = :report_markdown,
                            report_quality_score = :quality_score,
                            report_quality_grade = :quality_grade,
                            vault_file = :vault_file
                        WHERE id = :prediction_id
                    """),
                    {
                        "prediction_id": prediction_id,
                        "report_markdown": report_markdown,
                        "quality_score": quality_score,
                        "quality_grade": quality_grade or None,
                        "vault_file": vault_file or None,
                    }
                )
                session.commit()
                rows = result.rowcount

            if rows == 0:
                return {
                    "status": "not_found",
                    "prediction_id": prediction_id,
                    "error": "No prediction found with this ID",
                }

            return {
                "status": "updated",
                "prediction_id": prediction_id,
                "report_length": len(report_markdown),
                "quality_score": quality_score,
            }

        except Exception as e:
            logger.error(f"Failed to update prediction report: {e}")
            return {
                "status": "error",
                "error": str(e),
                "prediction_id": prediction_id,
            }

    # =========================================================================
    # SELF-IMPROVEMENT TOOLS
    # =========================================================================

    @mcp.tool()
    def calibrate_confidence(
        days: int = 90,
        min_bucket_n: int = 5
    ) -> dict:
        """
        Run Brier score calibration and generate confidence adjustment multipliers.

        Compares predicted confidence scores vs actual win rates per bucket
        (50-60%, 60-70%, 70-80%, 80%+), then computes multipliers to correct
        overconfidence or underconfidence in future predictions.

        Run weekly (or after 20+ new validated predictions) to keep calibration current.

        Args:
            days: Number of days of prediction history to analyze (default: 90)
            min_bucket_n: Minimum predictions per bucket for significant multiplier (default: 5)

        Returns:
            dict with:
            - status: "calibrated" or "insufficient_data"
            - brier_score: Overall calibration metric (0=perfect, 0.25=coin flip)
            - brier_calibration: Calibration component (lower = better calibrated)
            - brier_resolution: Resolution component (higher = better discrimination)
            - overall_win_rate: Actual overall win rate
            - buckets: Per-bucket analysis (avg_predicted, actual_rate, multiplier, n)
            - multipliers: Confidence adjustment multipliers per bucket
            - interpretation: Human-readable quality assessment
        """
        try:
            from ..prediction_tracker import CalibrationEngine
            engine = CalibrationEngine()
            return engine.calibrate(days=days, min_bucket_n=min_bucket_n)
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    def analyze_gate_effectiveness(
        days: int = 90
    ) -> dict:
        """
        Compute lift scores for each of the 5 gates to measure predictive power.

        Lift = PASS win rate minus FAIL win rate. A gate with high lift is a strong
        predictor of outcomes. Low-lift gates may need recalibration or downweighting.

        Results are stored in gate_weights table and used to inform weight adjustments.

        Run weekly to track gate effectiveness over time.

        Args:
            days: Number of days of prediction history to analyze (default: 90)

        Returns:
            dict with:
            - status: "analyzed"
            - gates: Per-gate analysis with pass_win_rate, fail_win_rate, lift_score, recommended_weight
            - ranking: Gates sorted by lift score (best to worst)
            - best_gate: Strongest predictor gate name
            - worst_gate: Weakest predictor gate name
            - interpretation: Human-readable summary of gate effectiveness
        """
        try:
            from ..prediction_tracker import GateEffectivenessAnalyzer
            analyzer = GateEffectivenessAnalyzer()
            return analyzer.analyze(days=days)
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    def optimize_stops_targets(
        days: int = 180
    ) -> dict:
        """
        Analyze MFE/MAE data to recommend optimal stop-loss and profit target levels.

        Uses actual intraday price extremes from resolved predictions to determine:
        - Are current stops too tight? (prematurely stopping out winners)
        - Are current targets too conservative? (leaving profit on the table)
        - How do optimal levels vary by direction (LONG vs SHORT)?
        - How do optimal levels vary by macro regime?

        Run monthly after sufficient MFE/MAE data has accumulated.

        Args:
            days: Number of days of prediction history to analyze (default: 180)

        Returns:
            dict with:
            - status: "optimized" or "insufficient_data"
            - overall: Aggregate MFE/MAE analysis with optimal_stop_pct and optimal_target_pct
            - by_direction_long: LONG-specific analysis (if sufficient data)
            - by_direction_short: SHORT-specific analysis (if sufficient data)
            - by_regime_*: Per-regime analysis (EXPANSION, LATE_CYCLE, etc.)
            - Each group includes: mfe/mae medians, winners_stopped_prematurely_pct,
              avg_profit_left_on_table_pct, and actionable recommendations
        """
        try:
            from ..prediction_tracker import StopTargetOptimizer
            optimizer = StopTargetOptimizer()
            return optimizer.optimize(days=days)
        except Exception as e:
            return {"status": "error", "error": str(e)}
