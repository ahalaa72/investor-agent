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
