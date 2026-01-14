"""
Prediction Tracker - Store and track trading predictions for efficiency analysis.

This module provides:
1. PredictionTracker - Store predictions from any report type
2. ComponentAnalyzer - Analyze accuracy of individual components
3. EfficiencyReportGenerator - Generate weekly efficiency reports

Integrates with generate_trading_signal() output to capture all gate results,
component scores, and trading plan details for outcome tracking.
"""

import json
import logging
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any
from statistics import mean, stdev

import yfinance as yf

from .database import execute_query, execute_insert, get_db_session

logger = logging.getLogger(__name__)

# Directory for JSON backups
PREDICTIONS_DIR = Path(__file__).parent / "predictions"
PREDICTIONS_DIR.mkdir(exist_ok=True)


class PredictionTracker:
    """
    Store and track predictions from all report types.

    Extracts data from generate_trading_signal() output and stores:
    - All 4 gate results (PASS/FAIL)
    - Sub-component details (catalyst, freshness, Dalio, Brooks, quality, options)
    - Trading plan (entry, stop, targets)
    - Direction voting and conflict detection
    """

    def store_prediction(
        self,
        trading_signal: dict[str, Any],
        report_type: str,
        ticker: str | None = None,
        direction: str | None = None
    ) -> dict[str, Any]:
        """
        Store a prediction from generate_trading_signal output.

        Args:
            trading_signal: Full output from generate_trading_signal()
            report_type: "comprehensive" | "concise" | "scanner" | "portfolio"
            ticker: Override ticker (uses signal ticker if not provided)
            direction: Override direction (uses signal direction if not provided)

        Returns:
            dict with status, prediction_id, and storage confirmation
        """
        prediction_id = str(uuid.uuid4())
        now = datetime.now()

        # Extract basic info
        ticker = ticker or trading_signal.get("ticker", "UNKNOWN")
        direction = direction or trading_signal.get("direction", "LONG")

        # Extract trading plan (use 'or {}' to handle None values)
        trading_plan = trading_signal.get("trading_plan") or {}
        entry_price = trading_plan.get("entry_price", 0)
        stop_loss = trading_plan.get("stop_loss") or {}
        stop_price = stop_loss.get("price") if isinstance(stop_loss, dict) else None
        target_1 = trading_plan.get("target_1") or {}
        target_1_price = target_1.get("price") if isinstance(target_1, dict) else None
        target_2 = trading_plan.get("target_2") or {}
        target_2_price = target_2.get("price") if isinstance(target_2, dict) else None

        # Extract gate status
        gate_status = trading_signal.get("gate_status") or {}
        gates_passed = sum(1 for g in gate_status.values() if g == "PASS")

        # Extract catalyst analysis
        catalyst = trading_signal.get("catalyst_analysis") or {}

        # Extract freshness/Dalio analysis
        freshness = trading_signal.get("freshness_analysis") or {}
        dalio = trading_signal.get("dalio_economic_machine") or {}
        dalio_key_metrics = dalio.get("key_metrics") or {}
        dalio_ratio_data = dalio_key_metrics.get("dalio_ratio") or {}
        dollar_flow_data = dalio_key_metrics.get("cumulative_dollar_flow") or {}
        sustainability_data = dalio_key_metrics.get("trend_sustainability") or {}

        # Extract Brooks analysis
        brooks = trading_signal.get("brooks_analysis") or {}

        # Extract quality analysis
        quality = trading_signal.get("quality_analysis") or {}

        # Extract options analysis (if available)
        options = trading_signal.get("options_analysis") or {}

        # Extract direction voting
        direction_votes = trading_signal.get("direction_votes") or {}

        # Extract historical validation (handle null/None explicitly)
        proof = trading_signal.get("proof_of_validity") or {}

        # Build INSERT query
        query = """
            INSERT INTO predictions (
                id, ticker, direction, report_type, created_at, prediction_date,
                entry_price, stop_price, target_1_price, target_2_price,
                signal, confidence_score, composite_score,
                gate_catalyst, gate_freshness, gate_brooks, gate_quality, gates_passed,
                catalyst_direction, catalyst_strength, catalyst_score, bullish_score, bearish_score, trade_allowed,
                cvd_trend, exhaustion_score, fresh_direction, dalio_ratio, dalio_interpretation,
                cumulative_dollar_flow, sustainability_score, freshness_checks_passed,
                always_in, trap_risk, brooks_probability, brooks_pattern,
                quality_score, quality_grade, f_score, z_score,
                iv_rank, iv_percentile, recommended_strategy, put_call_ratio,
                vote_catalyst, vote_cvd, vote_exhaustion, vote_brooks, data_direction, direction_conflict,
                similar_setups_count, historical_success_rate, historical_confidence,
                outcome, validated, full_analysis_json
            )
            VALUES (
                :id, :ticker, :direction, :report_type, :created_at, :prediction_date,
                :entry_price, :stop_price, :target_1_price, :target_2_price,
                :signal, :confidence_score, :composite_score,
                :gate_catalyst, :gate_freshness, :gate_brooks, :gate_quality, :gates_passed,
                :catalyst_direction, :catalyst_strength, :catalyst_score, :bullish_score, :bearish_score, :trade_allowed,
                :cvd_trend, :exhaustion_score, :fresh_direction, :dalio_ratio, :dalio_interpretation,
                :cumulative_dollar_flow, :sustainability_score, :freshness_checks_passed,
                :always_in, :trap_risk, :brooks_probability, :brooks_pattern,
                :quality_score, :quality_grade, :f_score, :z_score,
                :iv_rank, :iv_percentile, :recommended_strategy, :put_call_ratio,
                :vote_catalyst, :vote_cvd, :vote_exhaustion, :vote_brooks, :data_direction, :direction_conflict,
                :similar_setups_count, :historical_success_rate, :historical_confidence,
                :outcome, :validated, :full_analysis_json
            )
        """

        params = {
            "id": prediction_id,
            "ticker": ticker,
            "direction": direction,
            "report_type": report_type,
            "created_at": now,
            "prediction_date": now.date(),
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_1_price": target_1_price,
            "target_2_price": target_2_price,
            "signal": trading_signal.get("signal"),
            "confidence_score": trading_signal.get("confidence"),
            "composite_score": trading_signal.get("composite_score"),
            "gate_catalyst": gate_status.get("catalyst"),
            "gate_freshness": gate_status.get("freshness"),
            "gate_brooks": gate_status.get("brooks"),
            "gate_quality": gate_status.get("quality"),
            "gates_passed": gates_passed,
            "catalyst_direction": catalyst.get("direction"),
            "catalyst_strength": catalyst.get("strength"),
            "catalyst_score": catalyst.get("score"),
            "bullish_score": catalyst.get("bullish_score"),
            "bearish_score": catalyst.get("bearish_score"),
            "trade_allowed": catalyst.get("trade_allowed"),
            "cvd_trend": freshness.get("cvd_trend"),
            "exhaustion_score": freshness.get("exhaustion_score"),
            "fresh_direction": freshness.get("fresh_direction"),
            # All Dalio fields from freshness_analysis (single source)
            "dalio_ratio": freshness.get("dalio_ratio"),
            "dalio_interpretation": freshness.get("dalio_interpretation"),
            "cumulative_dollar_flow": freshness.get("cumulative_dollar_flow_20d"),
            "sustainability_score": freshness.get("sustainability_score"),
            "freshness_checks_passed": freshness.get("checks_passed"),
            "always_in": brooks.get("always_in"),
            "trap_risk": brooks.get("trap_risk"),
            "brooks_probability": brooks.get("probability"),
            "brooks_pattern": brooks.get("pattern"),
            "quality_score": quality.get("score"),
            "quality_grade": quality.get("grade"),
            "f_score": quality.get("f_score"),
            "z_score": quality.get("z_score"),
            "iv_rank": options.get("iv_rank"),
            "iv_percentile": options.get("iv_percentile"),
            "recommended_strategy": options.get("recommended_strategy"),
            "put_call_ratio": options.get("put_call_ratio"),
            "vote_catalyst": direction_votes.get("catalyst"),
            "vote_cvd": direction_votes.get("cvd"),
            "vote_exhaustion": direction_votes.get("exhaustion"),
            "vote_brooks": direction_votes.get("brooks"),
            "data_direction": trading_signal.get("data_direction"),
            "direction_conflict": trading_signal.get("direction_conflict", False),
            "similar_setups_count": proof.get("similar_setups"),
            "historical_success_rate": proof.get("success_rate"),
            "historical_confidence": proof.get("confidence"),
            "outcome": "OPEN",
            "validated": False,
            "full_analysis_json": json.dumps(trading_signal, default=str)
        }

        try:
            # Store in database
            execute_insert(query, params)

            # Also save JSON backup
            self._save_json_backup(prediction_id, ticker, params, trading_signal)

            logger.info(f"Stored prediction {prediction_id} for {ticker} ({direction})")

            return {
                "status": "stored",
                "prediction_id": prediction_id,
                "ticker": ticker,
                "direction": direction,
                "report_type": report_type,
                "entry_price": entry_price,
                "stored_at": now.isoformat(),
                "components_stored": {
                    "catalyst": gate_status.get("catalyst") is not None,
                    "freshness": gate_status.get("freshness") is not None,
                    "dalio": dalio_ratio_data.get("value") is not None if isinstance(dalio_ratio_data, dict) else False,
                    "brooks": gate_status.get("brooks") is not None,
                    "quality": gate_status.get("quality") is not None,
                    "options": options.get("iv_rank") is not None
                }
            }

        except Exception as e:
            logger.error(f"Failed to store prediction: {e}")
            return {
                "status": "error",
                "error": str(e),
                "ticker": ticker,
                "direction": direction
            }

    def _save_json_backup(
        self,
        prediction_id: str,
        ticker: str,
        params: dict,
        trading_signal: dict
    ) -> None:
        """Save JSON backup file for human review."""
        filename = f"{ticker}_{date.today().isoformat()}_{prediction_id[:8]}.json"
        filepath = PREDICTIONS_DIR / filename

        backup_data = {
            "prediction_id": prediction_id,
            "stored_params": {k: str(v) if isinstance(v, (datetime, date)) else v for k, v in params.items()},
            "full_trading_signal": trading_signal
        }

        with open(filepath, "w") as f:
            json.dump(backup_data, f, indent=2, default=str)

        logger.info(f"JSON backup saved: {filepath}")

    def update_outcomes(self, prediction_id: str | None = None) -> dict[str, Any]:
        """
        Update all open predictions with current prices and determine outcomes.

        Args:
            prediction_id: Optional specific prediction to update. Updates all if None.

        Returns:
            dict with update statistics
        """
        # Get open predictions
        if prediction_id:
            query = """
                SELECT id, ticker, direction, entry_price, stop_price, target_1_price, target_2_price,
                       prediction_date, created_at
                FROM predictions
                WHERE id = :prediction_id AND outcome = 'OPEN'
            """
            predictions = execute_query(query, {"prediction_id": prediction_id})
        else:
            query = """
                SELECT id, ticker, direction, entry_price, stop_price, target_1_price, target_2_price,
                       prediction_date, created_at
                FROM predictions
                WHERE outcome = 'OPEN'
            """
            predictions = execute_query(query)

        if not predictions:
            return {
                "status": "no_updates",
                "message": "No open predictions to update"
            }

        updated = []
        outcomes = {"WIN": 0, "LOSS": 0, "OPEN": 0}

        for pred in predictions:
            try:
                result = self._update_single_prediction(pred)
                updated.append(result)
                outcomes[result.get("outcome", "OPEN")] += 1
            except Exception as e:
                logger.error(f"Failed to update prediction {pred['id']}: {e}")

        return {
            "status": "updated",
            "total_open": len(predictions),
            "updated": len(updated),
            "newly_validated": sum(1 for u in updated if u.get("validated")),
            "outcomes": outcomes,
            "updated_predictions": updated
        }

    def _update_single_prediction(self, pred: dict) -> dict[str, Any]:
        """Update a single prediction with current price data."""
        ticker = pred["ticker"]
        direction = pred["direction"]
        entry_price = float(pred["entry_price"])
        stop_price = float(pred["stop_price"]) if pred["stop_price"] else None
        target_1 = float(pred["target_1_price"]) if pred["target_1_price"] else None
        prediction_date = pred["prediction_date"]

        # Calculate days held
        days_held = (date.today() - prediction_date).days

        # Get current price
        try:
            stock = yf.Ticker(ticker)
            current_price = stock.info.get("regularMarketPrice") or stock.info.get("currentPrice", 0)
        except Exception:
            current_price = entry_price  # Fallback

        # Calculate return
        if direction == "LONG":
            current_return = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            current_return = ((entry_price - current_price) / entry_price) * 100

        # Determine outcome
        outcome = "OPEN"
        hit_target = False
        hit_stop = False

        if direction == "LONG":
            if target_1 and current_price >= target_1:
                outcome = "WIN"
                hit_target = True
            elif stop_price and current_price <= stop_price:
                outcome = "LOSS"
                hit_stop = True
        else:  # SHORT
            if target_1 and current_price <= target_1:
                outcome = "WIN"
                hit_target = True
            elif stop_price and current_price >= stop_price:
                outcome = "LOSS"
                hit_stop = True

        # Mark as validated after 3 days (quick feedback loop)
        validated = days_held >= 3

        # Determine horizon prices (simplified - uses current as proxy)
        # In production, would fetch historical prices
        price_5d = current_price if days_held >= 5 else None
        price_10d = current_price if days_held >= 10 else None
        price_20d = current_price if days_held >= 3 else None  # Use 3-day validation

        # Update database
        update_query = """
            UPDATE predictions SET
                outcome = :outcome,
                validated = :validated,
                validated_at = CASE WHEN :validated = 1 THEN GETDATE() ELSE validated_at END,
                price_5d = COALESCE(:price_5d, price_5d),
                price_10d = COALESCE(:price_10d, price_10d),
                price_20d = COALESCE(:price_20d, price_20d),
                return_5d = CASE WHEN :days_held >= 5 THEN :current_return ELSE return_5d END,
                return_10d = CASE WHEN :days_held >= 10 THEN :current_return ELSE return_10d END,
                return_20d = CASE WHEN :days_held >= 20 THEN :current_return ELSE return_20d END,
                hit_target_1 = :hit_target,
                hit_stop = :hit_stop,
                days_to_target = CASE WHEN :hit_target = 1 AND days_to_target IS NULL THEN :days_held ELSE days_to_target END,
                days_to_stop = CASE WHEN :hit_stop = 1 AND days_to_stop IS NULL THEN :days_held ELSE days_to_stop END
            WHERE id = :id
        """

        execute_insert(update_query, {
            "id": str(pred["id"]),
            "outcome": outcome,
            "validated": validated,
            "price_5d": price_5d,
            "price_10d": price_10d,
            "price_20d": price_20d,
            "days_held": days_held,
            "current_return": current_return,
            "hit_target": hit_target,
            "hit_stop": hit_stop
        })

        return {
            "id": str(pred["id"]),
            "ticker": ticker,
            "direction": direction,
            "days_held": days_held,
            "return_current": round(current_return, 2),
            "outcome": outcome,
            "validated": validated,
            "hit_target": hit_target,
            "hit_stop": hit_stop
        }

    def get_prediction_by_id(self, prediction_id: str) -> dict[str, Any] | None:
        """Get a specific prediction by ID."""
        query = "SELECT * FROM predictions WHERE id = :id"
        results = execute_query(query, {"id": prediction_id})
        return results[0] if results else None


class ComponentAnalyzer:
    """
    Analyze accuracy of individual components.

    Calculates accuracy rates for:
    - Each of the 4 gates (catalyst, freshness, brooks, quality)
    - Sub-components (cvd_trend, trap_risk, dalio_ratio, etc.)
    """

    def analyze_gate_accuracy(self, days: int = 90) -> dict[str, Any]:
        """
        Calculate accuracy for each gate.

        Returns dict mapping gate name to accuracy metrics.
        """
        cutoff_date = date.today() - timedelta(days=days)

        gates = ["catalyst", "freshness", "brooks", "quality"]
        result = {}

        for gate in gates:
            query = f"""
                SELECT
                    gate_{gate} as gate_status,
                    outcome,
                    COUNT(*) as cnt
                FROM predictions
                WHERE prediction_date >= :cutoff
                  AND validated = 1
                  AND outcome IN ('WIN', 'LOSS')
                GROUP BY gate_{gate}, outcome
            """  # noqa: S608

            rows = execute_query(query, {"cutoff": cutoff_date})

            pass_win = sum(r["cnt"] for r in rows if r["gate_status"] == "PASS" and r["outcome"] == "WIN")
            pass_loss = sum(r["cnt"] for r in rows if r["gate_status"] == "PASS" and r["outcome"] == "LOSS")
            total_pass = pass_win + pass_loss

            accuracy = (pass_win / total_pass * 100) if total_pass > 0 else 0

            result[gate] = {
                "pass_win": pass_win,
                "pass_loss": pass_loss,
                "total_pass": total_pass,
                "accuracy": round(accuracy, 1)
            }

        return result

    def analyze_sub_components(self, days: int = 90) -> dict[str, Any]:
        """
        Analyze accuracy of sub-components within each gate.
        """
        cutoff_date = date.today() - timedelta(days=days)

        result = {}

        # CVD Trend accuracy
        result["cvd_trend"] = self._analyze_categorical_component(
            "cvd_trend", ["RISING", "FALLING", "FLAT"], cutoff_date
        )

        # Trap Risk accuracy
        result["trap_risk"] = self._analyze_categorical_component(
            "trap_risk", ["LOW", "MEDIUM", "HIGH"], cutoff_date
        )

        # Brooks Always-In accuracy
        result["always_in"] = self._analyze_categorical_component(
            "always_in", ["LONG", "SHORT", "NEUTRAL"], cutoff_date
        )

        # Quality Grade accuracy
        result["quality_grade"] = self._analyze_categorical_component(
            "quality_grade", ["A", "B", "C", "D", "F"], cutoff_date
        )

        # Numeric component buckets
        result["brooks_probability"] = self._analyze_numeric_buckets(
            "brooks_probability",
            [(0, 55, "<55%"), (55, 65, "55-65%"), (65, 100, ">65%")],
            cutoff_date
        )

        result["exhaustion_score"] = self._analyze_numeric_buckets(
            "exhaustion_score",
            [(0, 30, "<30"), (30, 50, "30-50"), (50, 100, ">50")],
            cutoff_date
        )

        result["sustainability_score"] = self._analyze_numeric_buckets(
            "sustainability_score",
            [(0, 50, "<50"), (50, 70, "50-70"), (70, 100, ">70")],
            cutoff_date
        )

        result["iv_rank"] = self._analyze_numeric_buckets(
            "iv_rank",
            [(0, 30, "<30"), (30, 60, "30-60"), (60, 100, ">60")],
            cutoff_date
        )

        return result

    def _analyze_categorical_component(
        self,
        column: str,
        categories: list[str],
        cutoff_date: date
    ) -> dict[str, float]:
        """Analyze accuracy for a categorical component."""
        result = {}

        for category in categories:
            query = f"""
                SELECT outcome, COUNT(*) as cnt
                FROM predictions
                WHERE {column} = :category
                  AND prediction_date >= :cutoff
                  AND validated = 1
                  AND outcome IN ('WIN', 'LOSS')
                GROUP BY outcome
            """  # noqa: S608

            rows = execute_query(query, {"category": category, "cutoff": cutoff_date})

            wins = sum(r["cnt"] for r in rows if r["outcome"] == "WIN")
            losses = sum(r["cnt"] for r in rows if r["outcome"] == "LOSS")
            total = wins + losses

            accuracy = (wins / total * 100) if total > 0 else 0
            result[category] = round(accuracy, 1)

        return result

    def _analyze_numeric_buckets(
        self,
        column: str,
        buckets: list[tuple[float, float, str]],
        cutoff_date: date
    ) -> dict[str, float]:
        """Analyze accuracy for numeric component in buckets."""
        result = {}

        for low, high, label in buckets:
            query = f"""
                SELECT outcome, COUNT(*) as cnt
                FROM predictions
                WHERE {column} >= :low AND {column} < :high
                  AND prediction_date >= :cutoff
                  AND validated = 1
                  AND outcome IN ('WIN', 'LOSS')
                GROUP BY outcome
            """  # noqa: S608

            rows = execute_query(query, {"low": low, "high": high, "cutoff": cutoff_date})

            wins = sum(r["cnt"] for r in rows if r["outcome"] == "WIN")
            losses = sum(r["cnt"] for r in rows if r["outcome"] == "LOSS")
            total = wins + losses

            accuracy = (wins / total * 100) if total > 0 else 0
            result[label] = round(accuracy, 1)

        return result

    def find_best_predictors(self, days: int = 90) -> list[dict[str, Any]]:
        """
        Identify most predictive components.
        Returns list sorted by accuracy.
        """
        sub_components = self.analyze_sub_components(days)

        all_components = []
        for component, values in sub_components.items():
            if isinstance(values, dict):
                for sub_key, accuracy in values.items():
                    all_components.append({
                        "component": component,
                        "sub_component": sub_key,
                        "accuracy": accuracy
                    })

        # Sort by accuracy descending
        return sorted(all_components, key=lambda x: x["accuracy"], reverse=True)

    def find_improvement_areas(self, days: int = 90, threshold: float = 55.0) -> list[dict[str, Any]]:
        """
        Identify components with accuracy below threshold.
        """
        sub_components = self.analyze_sub_components(days)

        needs_improvement = []
        for component, values in sub_components.items():
            if isinstance(values, dict):
                for sub_key, accuracy in values.items():
                    if accuracy < threshold and accuracy > 0:
                        needs_improvement.append({
                            "component": component,
                            "sub_component": sub_key,
                            "current_accuracy": accuracy,
                            "target_accuracy": threshold,
                            "gap": round(threshold - accuracy, 1)
                        })

        # Sort by gap (worst first)
        return sorted(needs_improvement, key=lambda x: x["gap"], reverse=True)


class EfficiencyReportGenerator:
    """
    Generate weekly efficiency reports with component accuracy analysis.
    """

    def __init__(self):
        self.tracker = PredictionTracker()
        self.analyzer = ComponentAnalyzer()

    def generate_weekly_report(
        self,
        period_days: int = 7,
        min_sample: int = 5
    ) -> dict[str, Any]:
        """
        Generate comprehensive efficiency report.

        Args:
            period_days: Days to analyze
            min_sample: Minimum predictions required

        Returns:
            Full efficiency report dict
        """
        cutoff_date = date.today() - timedelta(days=period_days)

        # Get total predictions in period
        count_query = """
            SELECT COUNT(*) as total
            FROM predictions
            WHERE prediction_date >= :cutoff
        """
        count_result = execute_query(count_query, {"cutoff": cutoff_date})
        total_predictions = count_result[0]["total"] if count_result else 0

        if total_predictions < min_sample:
            return {
                "status": "insufficient_data",
                "current": total_predictions,
                "required": min_sample,
                "message": f"Need at least {min_sample} predictions, have {total_predictions}"
            }

        # Build report
        report = {
            "status": "generated",
            "report_date": date.today().isoformat(),
            "period": f"{cutoff_date.isoformat()} to {date.today().isoformat()}",
            "period_days": period_days
        }

        # Executive Summary
        report["executive_summary"] = self._generate_executive_summary(cutoff_date)

        # Performance by Report Type
        report["by_report_type"] = self._analyze_by_report_type(cutoff_date)

        # Performance by Signal
        report["by_signal"] = self._analyze_by_signal(cutoff_date)

        # Performance by Gates Passed
        report["by_gates_passed"] = self._analyze_by_gates_passed(cutoff_date)

        # Gate Accuracy
        report["gate_accuracy"] = self.analyzer.analyze_gate_accuracy(period_days)

        # Component Accuracy
        report["component_accuracy"] = self.analyzer.analyze_sub_components(period_days)

        # Improvement Suggestions
        report["improvement_suggestions"] = self._generate_suggestions(period_days)

        # Historical Trend (last 4 weeks)
        report["historical_trend"] = self._get_historical_trend()

        # Full markdown report
        report["full_report_markdown"] = self._generate_markdown_report(report)

        # Store report in database
        self._store_report(report)

        return report

    def _generate_executive_summary(self, cutoff_date: date) -> dict[str, Any]:
        """Generate executive summary metrics."""
        query = """
            SELECT
                COUNT(*) as total_predictions,
                SUM(CASE WHEN validated = 1 THEN 1 ELSE 0 END) as validated,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                AVG(return_20d) as avg_return
            FROM predictions
            WHERE prediction_date >= :cutoff
        """
        result = execute_query(query, {"cutoff": cutoff_date})

        if not result:
            return {}

        r = result[0]
        total = r["wins"] + r["losses"]
        win_rate = (r["wins"] / total * 100) if total > 0 else 0

        # Find best/worst components
        best = self.analyzer.find_best_predictors(90)
        worst = self.analyzer.find_improvement_areas(90)

        return {
            "total_predictions": r["total_predictions"],
            "validated": r["validated"],
            "overall_win_rate": round(win_rate, 1),
            "overall_avg_return": round(r["avg_return"] or 0, 2),
            "best_component": f"{best[0]['component']}.{best[0]['sub_component']}" if best else "N/A",
            "best_accuracy": best[0]["accuracy"] if best else 0,
            "worst_component": f"{worst[0]['component']}.{worst[0]['sub_component']}" if worst else "N/A",
            "worst_accuracy": worst[0]["current_accuracy"] if worst else 0
        }

    def _analyze_by_report_type(self, cutoff_date: date) -> dict[str, Any]:
        """Analyze performance by report type."""
        query = """
            SELECT
                report_type,
                COUNT(*) as count,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                AVG(return_20d) as avg_return
            FROM predictions
            WHERE prediction_date >= :cutoff
              AND validated = 1
            GROUP BY report_type
        """
        results = execute_query(query, {"cutoff": cutoff_date})

        report_types = {}
        for r in results:
            total = r["wins"] + r["losses"]
            win_rate = (r["wins"] / total * 100) if total > 0 else 0
            report_types[r["report_type"]] = {
                "count": r["count"],
                "win_rate": round(win_rate, 1),
                "avg_return": round(r["avg_return"] or 0, 2)
            }

        return report_types

    def _analyze_by_signal(self, cutoff_date: date) -> dict[str, Any]:
        """Analyze performance by signal type."""
        query = """
            SELECT
                signal,
                COUNT(*) as count,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses
            FROM predictions
            WHERE prediction_date >= :cutoff
              AND validated = 1
            GROUP BY signal
        """
        results = execute_query(query, {"cutoff": cutoff_date})

        signals = {}
        for r in results:
            total = r["wins"] + r["losses"]
            win_rate = (r["wins"] / total * 100) if total > 0 else 0
            signals[r["signal"]] = {
                "count": r["count"],
                "win_rate": round(win_rate, 1)
            }

        return signals

    def _analyze_by_gates_passed(self, cutoff_date: date) -> dict[str, Any]:
        """Analyze performance by number of gates passed."""
        query = """
            SELECT
                gates_passed,
                COUNT(*) as count,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses
            FROM predictions
            WHERE prediction_date >= :cutoff
              AND validated = 1
            GROUP BY gates_passed
        """
        results = execute_query(query, {"cutoff": cutoff_date})

        gates = {}
        for r in results:
            total = r["wins"] + r["losses"]
            win_rate = (r["wins"] / total * 100) if total > 0 else 0
            label = f"{r['gates_passed']}/4"
            gates[label] = {
                "count": r["count"],
                "win_rate": round(win_rate, 1)
            }

        return gates

    def _generate_suggestions(self, period_days: int) -> list[dict[str, Any]]:
        """Generate improvement suggestions based on component accuracy."""
        improvement_areas = self.analyzer.find_improvement_areas(period_days)

        suggestions = []
        suggestion_templates = {
            "cvd_trend": {
                "FALLING": "Add volume confirmation: require rel_volume > 1.2 when CVD falling",
                "RISING": "Consider RSI confirmation when CVD rising in overbought territory",
            },
            "trap_risk": {
                "MEDIUM": "Reclassify MEDIUM trap risk signals to WATCH instead of BUY",
                "HIGH": "Add mandatory waiting period for HIGH trap risk setups",
            },
            "exhaustion_score": {
                ">50": "Reduce position size by 50% when exhaustion > 50",
                "30-50": "Add momentum confirmation for borderline exhaustion",
            },
            "brooks_probability": {
                "<55%": "Skip trades below 55% probability threshold",
                "55-65%": "Require 2+ gate confirmations for moderate probability",
            },
            "sustainability_score": {
                "<50": "Wait for sustainability improvement before entry",
            },
        }

        for area in improvement_areas[:5]:  # Top 5 suggestions
            component = area["component"]
            sub = area["sub_component"]

            suggestion_text = suggestion_templates.get(component, {}).get(
                sub,
                f"Review threshold for {component}.{sub}"
            )

            suggestions.append({
                "component": f"{component}.{sub}",
                "current_accuracy": area["current_accuracy"],
                "target_accuracy": area["target_accuracy"],
                "issue": f"{component} {sub} has {area['current_accuracy']}% accuracy",
                "suggestion": suggestion_text,
                "expected_impact": f"+{min(area['gap'], 15):.0f}% accuracy"
            })

        return suggestions

    def _get_historical_trend(self) -> list[dict[str, Any]]:
        """Get win rate trend for last 4 weeks."""
        trend = []

        for weeks_ago in range(4):
            start = date.today() - timedelta(days=7 * (weeks_ago + 1))
            end = date.today() - timedelta(days=7 * weeks_ago)

            query = """
                SELECT
                    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses
                FROM predictions
                WHERE prediction_date >= :start AND prediction_date < :end
                  AND validated = 1
            """
            result = execute_query(query, {"start": start, "end": end})

            if result:
                r = result[0]
                total = (r["wins"] or 0) + (r["losses"] or 0)
                win_rate = ((r["wins"] or 0) / total * 100) if total > 0 else 0

                trend.append({
                    "week": start.isoformat(),
                    "win_rate": round(win_rate, 1),
                    "total": total
                })

        return trend

    def _generate_markdown_report(self, report: dict) -> str:
        """Generate full markdown report."""
        summary = report.get("executive_summary", {})
        by_type = report.get("by_report_type", {})
        by_signal = report.get("by_signal", {})
        by_gates = report.get("by_gates_passed", {})
        gate_acc = report.get("gate_accuracy", {})
        suggestions = report.get("improvement_suggestions", [])

        md = f"""# INVESTOR-AGENT EFFICIENCY REPORT
**Report Date:** {report.get('report_date')}
**Period:** {report.get('period')}

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| Total Predictions | {summary.get('total_predictions', 0)} |
| Validated | {summary.get('validated', 0)} |
| Overall Win Rate | {summary.get('overall_win_rate', 0)}% |
| Avg Return | {summary.get('overall_avg_return', 0)}% |
| Best Component | {summary.get('best_component', 'N/A')} ({summary.get('best_accuracy', 0)}%) |
| Needs Improvement | {summary.get('worst_component', 'N/A')} ({summary.get('worst_accuracy', 0)}%) |

## PERFORMANCE BY REPORT TYPE

| Report Type | Count | Win Rate | Avg Return |
|-------------|-------|----------|------------|
"""
        for rt, data in by_type.items():
            md += f"| {rt} | {data.get('count', 0)} | {data.get('win_rate', 0)}% | {data.get('avg_return', 0)}% |\n"

        md += """
## PERFORMANCE BY SIGNAL

| Signal | Count | Win Rate |
|--------|-------|----------|
"""
        for sig, data in by_signal.items():
            md += f"| {sig} | {data.get('count', 0)} | {data.get('win_rate', 0)}% |\n"

        md += """
## PERFORMANCE BY GATES PASSED

| Gates Passed | Count | Win Rate |
|--------------|-------|----------|
"""
        for gates, data in by_gates.items():
            md += f"| {gates} | {data.get('count', 0)} | {data.get('win_rate', 0)}% |\n"

        md += """
## 4-GATE ACCURACY

| Gate | PASS→WIN | PASS→LOSS | Accuracy |
|------|----------|-----------|----------|
"""
        for gate, data in gate_acc.items():
            md += f"| {gate.title()} | {data.get('pass_win', 0)} | {data.get('pass_loss', 0)} | {data.get('accuracy', 0)}% |\n"

        md += """
## IMPROVEMENT SUGGESTIONS

"""
        for i, sug in enumerate(suggestions, 1):
            md += f"""**{i}. {sug.get('component')}** (Current: {sug.get('current_accuracy')}%, Target: {sug.get('target_accuracy')}%)
- Issue: {sug.get('issue')}
- Suggestion: {sug.get('suggestion')}
- Expected Impact: {sug.get('expected_impact')}

"""

        return md

    def _store_report(self, report: dict) -> None:
        """Store report in database."""
        summary = report.get("executive_summary", {})

        query = """
            INSERT INTO efficiency_reports (
                id, report_date, report_period_start, report_period_end,
                total_predictions, validated_predictions, overall_win_rate, overall_avg_return,
                best_component, best_component_accuracy, worst_component, worst_component_accuracy,
                suggestions_json, full_report_json
            )
            VALUES (
                NEWID(), :report_date, :period_start, :period_end,
                :total, :validated, :win_rate, :avg_return,
                :best_component, :best_accuracy, :worst_component, :worst_accuracy,
                :suggestions_json, :full_report_json
            )
        """

        period_parts = report.get("period", "").split(" to ")
        period_start = period_parts[0] if len(period_parts) > 0 else None
        period_end = period_parts[1] if len(period_parts) > 1 else None

        params = {
            "report_date": date.today(),
            "period_start": period_start,
            "period_end": period_end,
            "total": summary.get("total_predictions"),
            "validated": summary.get("validated"),
            "win_rate": summary.get("overall_win_rate"),
            "avg_return": summary.get("overall_avg_return"),
            "best_component": summary.get("best_component"),
            "best_accuracy": summary.get("best_accuracy"),
            "worst_component": summary.get("worst_component"),
            "worst_accuracy": summary.get("worst_accuracy"),
            "suggestions_json": json.dumps(report.get("improvement_suggestions", [])),
            "full_report_json": json.dumps(report, default=str)
        }

        try:
            execute_insert(query, params)
            logger.info(f"Efficiency report stored for {report.get('report_date')}")
        except Exception as e:
            logger.error(f"Failed to store efficiency report: {e}")
