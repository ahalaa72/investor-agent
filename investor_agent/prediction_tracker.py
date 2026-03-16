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
from typing import Any
from statistics import mean, stdev

import yfinance as yf

from .database import execute_query, execute_insert, get_db_session

logger = logging.getLogger(__name__)


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

        # ── Helper: coerce to float or None ──
        def _num(val, default=None):
            """Safely convert to float. Returns default for non-numeric strings."""
            if val is None:
                return default
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                try:
                    return float(val)
                except ValueError:
                    return default
            return default

        # ── Detect simplified vault JSON format ──
        # Vault JSON has flat keys (entry_price, stop_loss, target_1, gates)
        # vs full generate_trading_signal output (trading_plan.entry_price, gate_status, etc.)
        is_vault_format = "gates" in trading_signal and "gate_status" not in trading_signal

        # Extract basic info
        ticker = ticker or trading_signal.get("ticker", "UNKNOWN")
        direction = direction or trading_signal.get("direction", "LONG")

        # Extract trading plan (handle both vault flat format and full nested format)
        if is_vault_format:
            entry_price = _num(trading_signal.get("entry_price"), 0)
            stop_price = _num(trading_signal.get("stop_loss"))
            target_1_price = _num(trading_signal.get("target_1"))
            target_2_price = _num(trading_signal.get("target_2"))
        else:
            trading_plan = trading_signal.get("trading_plan") or {}
            entry_price = _num(trading_plan.get("entry_price"), 0)
            stop_loss = trading_plan.get("stop_loss") or {}
            stop_price = _num(stop_loss.get("price") if isinstance(stop_loss, dict) else stop_loss)
            target_1 = trading_plan.get("target_1") or {}
            target_1_price = _num(target_1.get("price") if isinstance(target_1, dict) else target_1)
            target_2 = trading_plan.get("target_2") or {}
            target_2_price = _num(target_2.get("price") if isinstance(target_2, dict) else target_2)

        # Extract gate status (vault uses "gates", full uses "gate_status")
        gate_status = trading_signal.get("gate_status") or trading_signal.get("gates") or {}
        gates_passed = trading_signal.get("gates_passed") or sum(1 for g in gate_status.values() if g == "PASS")

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
        # Vault format may have flat iv_rank
        if is_vault_format and not options:
            options = {"iv_rank": _num(trading_signal.get("iv_rank"))}

        # Extract direction voting
        direction_votes = trading_signal.get("direction_votes") or {}

        # Extract historical validation (handle null/None explicitly)
        proof = trading_signal.get("proof_of_validity") or {}

        # Capture macro regime context at prediction time
        macro_regime = None
        vix_at_entry = None
        yield_curve_at_entry = None
        market_breadth_at_entry = None
        try:
            import yfinance as yf
            # VIX
            vix_ticker = yf.Ticker("^VIX")
            vix_info = vix_ticker.info or {}
            vix_at_entry = vix_info.get("regularMarketPrice") or vix_info.get("previousClose")

            # Yield curve: 10Y - 3M
            tnx = yf.Ticker("^TNX").info or {}
            irx = yf.Ticker("^IRX").info or {}
            tnx_yield = tnx.get("regularMarketPrice") or tnx.get("previousClose")
            irx_yield = irx.get("regularMarketPrice") or irx.get("previousClose")
            if tnx_yield and irx_yield:
                yield_curve_at_entry = round(tnx_yield - irx_yield, 4)

            # Macro regime classification
            if vix_at_entry and yield_curve_at_entry is not None:
                if yield_curve_at_entry < 0 and vix_at_entry > 25:
                    macro_regime = "CONTRACTION"
                elif yield_curve_at_entry < 0.5 and vix_at_entry > 20:
                    macro_regime = "LATE_CYCLE"
                elif vix_at_entry < 20 and yield_curve_at_entry > 0.5:
                    macro_regime = "EXPANSION"
                else:
                    macro_regime = "RECOVERY"
        except Exception as e:
            logger.warning(f"Failed to capture macro regime: {e}")

        # Build INSERT query
        query = """
            INSERT INTO predictions (
                id, ticker, direction, report_type, created_at, prediction_date,
                entry_price, stop_price, target_1_price, target_2_price,
                signal, confidence_score, composite_score,
                gate_catalyst, gate_freshness, gate_brooks, gate_quality, gate_options, gates_passed,
                catalyst_direction, catalyst_strength, catalyst_score, bullish_score, bearish_score, trade_allowed,
                cvd_trend, exhaustion_score, fresh_direction, dalio_ratio, dalio_interpretation,
                cumulative_dollar_flow, sustainability_score, freshness_checks_passed,
                always_in, trap_risk, brooks_probability, brooks_pattern,
                quality_score, quality_grade, f_score, z_score,
                iv_rank, iv_percentile, recommended_strategy, put_call_ratio,
                vote_catalyst, vote_cvd, vote_exhaustion, vote_brooks, data_direction, direction_conflict,
                similar_setups_count, historical_success_rate, historical_confidence,
                macro_regime, vix_at_entry, yield_curve_at_entry, market_breadth_at_entry,
                raw_probability,
                outcome, validated, full_analysis_json
            )
            VALUES (
                :id, :ticker, :direction, :report_type, :created_at, :prediction_date,
                :entry_price, :stop_price, :target_1_price, :target_2_price,
                :signal, :confidence_score, :composite_score,
                :gate_catalyst, :gate_freshness, :gate_brooks, :gate_quality, :gate_options, :gates_passed,
                :catalyst_direction, :catalyst_strength, :catalyst_score, :bullish_score, :bearish_score, :trade_allowed,
                :cvd_trend, :exhaustion_score, :fresh_direction, :dalio_ratio, :dalio_interpretation,
                :cumulative_dollar_flow, :sustainability_score, :freshness_checks_passed,
                :always_in, :trap_risk, :brooks_probability, :brooks_pattern,
                :quality_score, :quality_grade, :f_score, :z_score,
                :iv_rank, :iv_percentile, :recommended_strategy, :put_call_ratio,
                :vote_catalyst, :vote_cvd, :vote_exhaustion, :vote_brooks, :data_direction, :direction_conflict,
                :similar_setups_count, :historical_success_rate, :historical_confidence,
                :macro_regime, :vix_at_entry, :yield_curve_at_entry, :market_breadth_at_entry,
                :raw_probability,
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
            "confidence_score": _num(trading_signal.get("confidence")),
            "composite_score": _num(trading_signal.get("composite_score")),
            "gate_catalyst": gate_status.get("catalyst"),
            "gate_freshness": gate_status.get("freshness"),
            "gate_brooks": gate_status.get("brooks"),
            "gate_quality": gate_status.get("quality"),
            "gates_passed": gates_passed,
            "catalyst_direction": catalyst.get("direction"),
            "catalyst_strength": catalyst.get("strength"),
            "catalyst_score": _num(catalyst.get("score")),
            "bullish_score": _num(catalyst.get("bullish_score")),
            "bearish_score": _num(catalyst.get("bearish_score")),
            "trade_allowed": catalyst.get("trade_allowed"),
            "cvd_trend": freshness.get("cvd_trend"),
            "exhaustion_score": _num(freshness.get("exhaustion_score")),
            "fresh_direction": freshness.get("fresh_direction"),
            # All Dalio fields from freshness_analysis (single source)
            "dalio_ratio": _num(freshness.get("dalio_ratio")),
            "dalio_interpretation": freshness.get("dalio_interpretation"),
            "cumulative_dollar_flow": _num(freshness.get("cumulative_dollar_flow_20d")),
            "sustainability_score": _num(freshness.get("sustainability_score")),
            "freshness_checks_passed": _num(freshness.get("checks_passed")),
            "always_in": brooks.get("always_in"),
            "trap_risk": brooks.get("trap_risk"),
            "brooks_probability": _num(brooks.get("probability")),
            "brooks_pattern": brooks.get("pattern"),
            "quality_score": _num(quality.get("score")),
            "quality_grade": quality.get("grade"),
            "f_score": _num(quality.get("f_score")),
            "z_score": _num(quality.get("z_score")),
            "iv_rank": _num(options.get("iv_rank")),
            "iv_percentile": _num(options.get("iv_percentile")),
            "recommended_strategy": options.get("recommended_strategy"),
            "put_call_ratio": _num(options.get("put_call_ratio")),
            "vote_catalyst": direction_votes.get("catalyst"),
            "vote_cvd": direction_votes.get("cvd"),
            "vote_exhaustion": direction_votes.get("exhaustion"),
            "vote_brooks": direction_votes.get("brooks"),
            "data_direction": trading_signal.get("data_direction"),
            "direction_conflict": trading_signal.get("direction_conflict", False),
            "similar_setups_count": _num(proof.get("similar_setups")),
            "historical_success_rate": _num(proof.get("success_rate")),
            "historical_confidence": proof.get("confidence"),
            "macro_regime": macro_regime,
            "vix_at_entry": vix_at_entry,
            "yield_curve_at_entry": yield_curve_at_entry,
            "market_breadth_at_entry": market_breadth_at_entry,
            "raw_probability": _num(brooks.get("probability")),
            "gate_options": gate_status.get("options"),
            "outcome": "OPEN",
            "validated": False,
            "full_analysis_json": json.dumps(trading_signal, default=str)
        }

        try:
            # Store in database
            execute_insert(query, params)

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
        """Update a single prediction with current price data and MFE/MAE."""
        ticker = pred["ticker"]
        direction = pred["direction"]
        entry_price = float(pred["entry_price"]) if pred["entry_price"] else 0
        if entry_price <= 0:
            return {"id": str(pred["id"]), "ticker": ticker, "outcome": "OPEN", "error": "invalid entry_price"}
        stop_price = float(pred["stop_price"]) if pred["stop_price"] else None
        target_1 = float(pred["target_1_price"]) if pred["target_1_price"] else None
        prediction_date = pred["prediction_date"]

        # Calculate days held
        days_held = (date.today() - prediction_date).days

        # Fetch daily OHLC history since prediction for accurate horizon prices + MFE/MAE
        price_5d = None
        price_10d = None
        price_20d = None
        return_5d = None
        return_10d = None
        return_20d = None
        mfe_5d = None
        mae_5d = None
        mfe_10d = None
        mae_10d = None
        mfe_20d = None
        mae_20d = None
        current_price = entry_price
        hit_target = False
        hit_stop = False
        days_to_target = None
        days_to_stop = None

        try:
            stock = yf.Ticker(ticker)
            # Fetch enough history (prediction_date to today)
            start_dt = prediction_date + timedelta(days=1)
            hist = stock.history(start=start_dt.isoformat(), end=(date.today() + timedelta(days=1)).isoformat())

            if hist is not None and not hist.empty:
                closes = hist['Close'].values
                highs = hist['High'].values
                lows = hist['Low'].values
                current_price = float(closes[-1])

                # Helper: compute MFE/MAE for a given horizon
                def _compute_mfe_mae(n_days):
                    if len(highs) < n_days:
                        return None, None, None, None
                    h_slice = highs[:n_days]
                    l_slice = lows[:n_days]
                    c_price = float(closes[n_days - 1])

                    if direction == "LONG":
                        mfe = round(((float(max(h_slice)) - entry_price) / entry_price) * 100, 4)
                        mae = round(((entry_price - float(min(l_slice))) / entry_price) * 100, 4)
                        ret = round(((c_price - entry_price) / entry_price) * 100, 4)
                    else:  # SHORT
                        mfe = round(((entry_price - float(min(l_slice))) / entry_price) * 100, 4)
                        mae = round(((float(max(h_slice)) - entry_price) / entry_price) * 100, 4)
                        ret = round(((entry_price - c_price) / entry_price) * 100, 4)
                    return c_price, ret, max(mfe, 0), max(mae, 0)

                # 5-day
                if days_held >= 5:
                    price_5d, return_5d, mfe_5d, mae_5d = _compute_mfe_mae(5)
                # 10-day
                if days_held >= 10:
                    price_10d, return_10d, mfe_10d, mae_10d = _compute_mfe_mae(10)
                # 20-day
                if days_held >= 20:
                    price_20d, return_20d, mfe_20d, mae_20d = _compute_mfe_mae(20)

                # Check target/stop hit using intraday highs/lows
                for i in range(len(highs)):
                    if direction == "LONG":
                        if target_1 and float(highs[i]) >= target_1 and not hit_target:
                            hit_target = True
                            days_to_target = i + 1
                        if stop_price and float(lows[i]) <= stop_price and not hit_stop:
                            hit_stop = True
                            days_to_stop = i + 1
                    else:  # SHORT
                        if target_1 and float(lows[i]) <= target_1 and not hit_target:
                            hit_target = True
                            days_to_target = i + 1
                        if stop_price and float(highs[i]) >= stop_price and not hit_stop:
                            hit_stop = True
                            days_to_stop = i + 1
            else:
                # Fallback to info
                info = stock.info or {}
                current_price = info.get("regularMarketPrice") or info.get("currentPrice", entry_price)
        except Exception as e:
            logger.warning(f"Failed to fetch history for {ticker}: {e}")

        # Calculate current return
        if direction == "LONG":
            current_return = ((current_price - entry_price) / entry_price) * 100
        else:
            current_return = ((entry_price - current_price) / entry_price) * 100

        # Determine outcome
        outcome = "OPEN"
        if hit_target and not hit_stop:
            outcome = "WIN"
        elif hit_stop and not hit_target:
            outcome = "LOSS"
        elif hit_target and hit_stop:
            outcome = "WIN" if (days_to_target or 999) <= (days_to_stop or 999) else "LOSS"
        elif days_held >= 20:
            outcome = "WIN" if current_return > 0 else "LOSS"

        # Mark as validated after 3 days
        validated = days_held >= 3

        # Update database (including MFE/MAE)
        update_query = """
            UPDATE predictions SET
                outcome = :outcome,
                validated = :validated,
                validated_at = CASE WHEN :validated = 1 THEN GETDATE() ELSE validated_at END,
                price_5d = COALESCE(:price_5d, price_5d),
                price_10d = COALESCE(:price_10d, price_10d),
                price_20d = COALESCE(:price_20d, price_20d),
                return_5d = COALESCE(:return_5d, return_5d),
                return_10d = COALESCE(:return_10d, return_10d),
                return_20d = COALESCE(:return_20d, return_20d),
                mfe_5d = COALESCE(:mfe_5d, mfe_5d),
                mae_5d = COALESCE(:mae_5d, mae_5d),
                mfe_10d = COALESCE(:mfe_10d, mfe_10d),
                mae_10d = COALESCE(:mae_10d, mae_10d),
                mfe_20d = COALESCE(:mfe_20d, mfe_20d),
                mae_20d = COALESCE(:mae_20d, mae_20d),
                hit_target_1 = :hit_target,
                hit_stop = :hit_stop,
                days_to_target = CASE WHEN :hit_target = 1 AND days_to_target IS NULL THEN :days_to_target ELSE days_to_target END,
                days_to_stop = CASE WHEN :hit_stop = 1 AND days_to_stop IS NULL THEN :days_to_stop ELSE days_to_stop END
            WHERE id = :id
        """

        execute_insert(update_query, {
            "id": str(pred["id"]),
            "outcome": outcome,
            "validated": validated,
            "price_5d": price_5d,
            "price_10d": price_10d,
            "price_20d": price_20d,
            "return_5d": return_5d,
            "return_10d": return_10d,
            "return_20d": return_20d,
            "mfe_5d": mfe_5d,
            "mae_5d": mae_5d,
            "mfe_10d": mfe_10d,
            "mae_10d": mae_10d,
            "mfe_20d": mfe_20d,
            "mae_20d": mae_20d,
            "hit_target": hit_target,
            "hit_stop": hit_stop,
            "days_to_target": days_to_target,
            "days_to_stop": days_to_stop
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
            "hit_stop": hit_stop,
            "mfe_5d": mfe_5d,
            "mae_5d": mae_5d
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


# =============================================================================
# SELF-IMPROVEMENT SYSTEM: Calibration, Gate Effectiveness, Stop Optimization
# =============================================================================


class CalibrationEngine:
    """
    Brier score calibration + confidence adjustment multipliers.

    Compares predicted confidence vs actual win rates per bucket,
    then generates multipliers to shrink or stretch future confidence.
    """

    BUCKETS = [
        (50, 60, "50_60"),
        (60, 70, "60_70"),
        (70, 80, "70_80"),
        (80, 101, "80_plus"),
    ]

    def calibrate(self, days: int = 90, min_bucket_n: int = 5) -> dict[str, Any]:
        """
        Run full calibration: Brier score + per-bucket multipliers.

        Returns dict with brier_score, calibration curve, multipliers,
        and stores result in calibration_history table.
        """
        cutoff = date.today() - timedelta(days=days)

        # Fetch all resolved predictions with confidence
        query = """
            SELECT
                confidence_score,
                outcome
            FROM predictions
            WHERE prediction_date >= :cutoff
              AND validated = 1
              AND outcome IN ('WIN', 'LOSS')
              AND confidence_score IS NOT NULL
        """
        rows = execute_query(query, {"cutoff": cutoff})

        if len(rows) < 10:
            return {
                "status": "insufficient_data",
                "sample_size": len(rows),
                "message": f"Need 10+ resolved predictions with confidence, have {len(rows)}"
            }

        # Build arrays
        predicted = []
        actual = []
        for r in rows:
            conf = float(r["confidence_score"]) / 100.0  # normalize to 0-1
            outcome = 1.0 if r["outcome"] == "WIN" else 0.0
            predicted.append(conf)
            actual.append(outcome)

        # Brier Score: mean((predicted - actual)^2)
        brier = sum((p - a) ** 2 for p, a in zip(predicted, actual)) / len(predicted)

        # Decomposition: calibration + resolution
        # Calibration = mean((bucket_avg_pred - bucket_actual_rate)^2 * n_k) / N
        # Resolution  = mean((bucket_actual_rate - overall_rate)^2 * n_k) / N
        overall_rate = sum(actual) / len(actual)

        bucket_results = {}
        calibration_sum = 0.0
        resolution_sum = 0.0
        multipliers = {}

        for low, high, label in self.BUCKETS:
            bucket_pred = []
            bucket_actual = []
            for p, a in zip(predicted, actual):
                p_pct = p * 100
                if low <= p_pct < high:
                    bucket_pred.append(p)
                    bucket_actual.append(a)

            n_k = len(bucket_pred)
            if n_k == 0:
                bucket_results[label] = {"n": 0, "avg_predicted": None, "actual_rate": None}
                multipliers[label] = 1.0
                continue

            avg_pred = sum(bucket_pred) / n_k
            actual_rate = sum(bucket_actual) / n_k

            calibration_sum += n_k * (avg_pred - actual_rate) ** 2
            resolution_sum += n_k * (actual_rate - overall_rate) ** 2

            # Multiplier: actual_rate / avg_predicted, capped [0.5, 1.5]
            if avg_pred > 0 and n_k >= min_bucket_n:
                raw_mult = actual_rate / avg_pred
                mult = max(0.5, min(1.5, round(raw_mult, 4)))
            else:
                mult = 1.0

            multipliers[label] = mult
            bucket_results[label] = {
                "n": n_k,
                "avg_predicted": round(avg_pred * 100, 1),
                "actual_rate": round(actual_rate * 100, 1),
                "multiplier": mult,
                "significant": n_k >= min_bucket_n
            }

        brier_calibration = calibration_sum / len(predicted) if predicted else 0
        brier_resolution = resolution_sum / len(predicted) if predicted else 0

        result = {
            "status": "calibrated",
            "calibration_date": date.today().isoformat(),
            "sample_size": len(rows),
            "brier_score": round(brier, 4),
            "brier_calibration": round(brier_calibration, 4),
            "brier_resolution": round(brier_resolution, 4),
            "overall_win_rate": round(overall_rate * 100, 1),
            "buckets": bucket_results,
            "multipliers": {
                f"multiplier_{k}": v for k, v in multipliers.items()
            },
            "interpretation": self._interpret_brier(brier),
        }

        # Store in calibration_history
        self._store_calibration(result, bucket_results, multipliers)

        return result

    def get_latest_multipliers(self) -> dict[str, float]:
        """Get most recent calibration multipliers from DB."""
        query = """
            SELECT TOP 1
                multiplier_50_60, multiplier_60_70,
                multiplier_70_80, multiplier_80_plus
            FROM calibration_history
            ORDER BY calibration_date DESC
        """
        rows = execute_query(query)
        if not rows:
            return {"50_60": 1.0, "60_70": 1.0, "70_80": 1.0, "80_plus": 1.0}

        r = rows[0]
        return {
            "50_60": float(r["multiplier_50_60"] or 1.0),
            "60_70": float(r["multiplier_60_70"] or 1.0),
            "70_80": float(r["multiplier_70_80"] or 1.0),
            "80_plus": float(r["multiplier_80_plus"] or 1.0),
        }

    def _interpret_brier(self, brier: float) -> str:
        if brier < 0.1:
            return "EXCELLENT — predictions are well-calibrated"
        elif brier < 0.2:
            return "GOOD — minor calibration gap, multipliers will help"
        elif brier < 0.25:
            return "FAIR — noticeable overconfidence or underconfidence"
        else:
            return "POOR — confidence scores need significant recalibration"

    def _store_calibration(self, result: dict, buckets: dict, multipliers: dict) -> None:
        query = """
            INSERT INTO calibration_history (
                calibration_date,
                brier_score, brier_calibration, brier_resolution,
                bucket_50_60_actual, bucket_60_70_actual,
                bucket_70_80_actual, bucket_80_plus_actual,
                bucket_50_60_n, bucket_60_70_n,
                bucket_70_80_n, bucket_80_plus_n,
                multiplier_50_60, multiplier_60_70,
                multiplier_70_80, multiplier_80_plus,
                total_predictions, total_resolved
            )
            VALUES (
                :cal_date,
                :brier, :brier_cal, :brier_res,
                :b50_actual, :b60_actual, :b70_actual, :b80_actual,
                :b50_n, :b60_n, :b70_n, :b80_n,
                :m50, :m60, :m70, :m80,
                :total_pred, :total_resolved
            )
        """
        params = {
            "cal_date": date.today(),
            "brier": result["brier_score"],
            "brier_cal": result["brier_calibration"],
            "brier_res": result["brier_resolution"],
            "b50_actual": buckets.get("50_60", {}).get("actual_rate"),
            "b60_actual": buckets.get("60_70", {}).get("actual_rate"),
            "b70_actual": buckets.get("70_80", {}).get("actual_rate"),
            "b80_actual": buckets.get("80_plus", {}).get("actual_rate"),
            "b50_n": buckets.get("50_60", {}).get("n", 0),
            "b60_n": buckets.get("60_70", {}).get("n", 0),
            "b70_n": buckets.get("70_80", {}).get("n", 0),
            "b80_n": buckets.get("80_plus", {}).get("n", 0),
            "m50": multipliers.get("50_60", 1.0),
            "m60": multipliers.get("60_70", 1.0),
            "m70": multipliers.get("70_80", 1.0),
            "m80": multipliers.get("80_plus", 1.0),
            "total_pred": result["sample_size"],
            "total_resolved": result["sample_size"],
        }
        try:
            execute_insert(query, params)
            logger.info(f"Calibration stored: Brier={result['brier_score']}")
        except Exception as e:
            logger.error(f"Failed to store calibration: {e}")


class GateEffectivenessAnalyzer:
    """
    Compute lift scores for each gate: PASS win rate vs FAIL win rate.

    A high lift score means the gate is a strong predictor.
    Stores results in gate_weights table with recommended weights.
    """

    GATES = ["catalyst", "freshness", "brooks", "quality", "options"]

    def analyze(self, days: int = 90) -> dict[str, Any]:
        """
        Compute gate lift scores and recommended weights.

        Returns per-gate lift analysis + recommended weight distribution.
        """
        cutoff = date.today() - timedelta(days=days)

        gate_results = {}
        total_lift = 0.0

        for gate in self.GATES:
            query = f"""
                SELECT
                    gate_{gate} as gate_status,
                    outcome,
                    COUNT(*) as cnt
                FROM predictions
                WHERE prediction_date >= :cutoff
                  AND validated = 1
                  AND outcome IN ('WIN', 'LOSS')
                  AND gate_{gate} IS NOT NULL
                GROUP BY gate_{gate}, outcome
            """  # noqa: S608

            rows = execute_query(query, {"cutoff": cutoff})

            pass_win = sum(r["cnt"] for r in rows if r["gate_status"] == "PASS" and r["outcome"] == "WIN")
            pass_loss = sum(r["cnt"] for r in rows if r["gate_status"] == "PASS" and r["outcome"] == "LOSS")
            fail_win = sum(r["cnt"] for r in rows if r["gate_status"] == "FAIL" and r["outcome"] == "WIN")
            fail_loss = sum(r["cnt"] for r in rows if r["gate_status"] == "FAIL" and r["outcome"] == "LOSS")

            total_pass = pass_win + pass_loss
            total_fail = fail_win + fail_loss
            sample_size = total_pass + total_fail

            pass_wr = (pass_win / total_pass * 100) if total_pass > 0 else 50.0
            fail_wr = (fail_win / total_fail * 100) if total_fail > 0 else 50.0
            lift = pass_wr - fail_wr

            # Only count positive lift toward weight allocation
            if lift > 0 and sample_size >= 10:
                total_lift += lift

            gate_results[gate] = {
                "pass_win_rate": round(pass_wr, 1),
                "fail_win_rate": round(fail_wr, 1),
                "lift_score": round(lift, 1),
                "pass_total": total_pass,
                "fail_total": total_fail,
                "sample_size": sample_size,
                "significant": sample_size >= 20,
            }

        # Calculate recommended weights (proportional to lift)
        for gate, data in gate_results.items():
            lift = max(data["lift_score"], 0)
            if total_lift > 0 and data["sample_size"] >= 10:
                weight = round(lift / total_lift, 4)
            else:
                weight = round(1.0 / len(self.GATES), 4)  # Equal weight fallback
            data["recommended_weight"] = weight

        # Rank gates by effectiveness
        ranked = sorted(gate_results.items(), key=lambda x: x[1]["lift_score"], reverse=True)

        result = {
            "status": "analyzed",
            "analysis_date": date.today().isoformat(),
            "period_days": days,
            "gates": gate_results,
            "ranking": [{"gate": g, "lift": d["lift_score"], "weight": d["recommended_weight"]} for g, d in ranked],
            "best_gate": ranked[0][0] if ranked else None,
            "worst_gate": ranked[-1][0] if ranked else None,
            "interpretation": self._interpret(gate_results),
        }

        # Store in gate_weights
        self._store_weights(gate_results)

        return result

    def _interpret(self, gates: dict) -> str:
        strong = [g for g, d in gates.items() if d["lift_score"] > 10 and d["significant"]]
        weak = [g for g, d in gates.items() if d["lift_score"] < 3 and d["significant"]]
        msgs = []
        if strong:
            msgs.append(f"Strong predictors: {', '.join(strong)}")
        if weak:
            msgs.append(f"Weak predictors (consider downweighting): {', '.join(weak)}")
        if not msgs:
            msgs.append("Insufficient data for conclusive gate ranking")
        return "; ".join(msgs)

    def _store_weights(self, gates: dict) -> None:
        for gate_name, data in gates.items():
            query = """
                INSERT INTO gate_weights (
                    effective_date, gate_name,
                    lift_score, pass_win_rate, fail_win_rate,
                    recommended_weight, sample_size
                )
                VALUES (
                    :eff_date, :gate_name,
                    :lift, :pass_wr, :fail_wr,
                    :weight, :sample_size
                )
            """
            try:
                execute_insert(query, {
                    "eff_date": date.today(),
                    "gate_name": gate_name,
                    "lift": data["lift_score"],
                    "pass_wr": data["pass_win_rate"],
                    "fail_wr": data["fail_win_rate"],
                    "weight": data["recommended_weight"],
                    "sample_size": data["sample_size"],
                })
            except Exception as e:
                logger.error(f"Failed to store gate weight for {gate_name}: {e}")


class StopTargetOptimizer:
    """
    Analyze MFE/MAE data to recommend optimal stop and target levels.

    Uses actual intraday extremes from resolved predictions to find:
    - Stops that don't prematurely exit winners
    - Targets that capture most of the available move
    """

    def optimize(self, days: int = 180) -> dict[str, Any]:
        """
        Run MFE/MAE analysis and generate optimal stop/target recommendations.

        Stratifies by direction and macro regime.
        """
        cutoff = date.today() - timedelta(days=days)

        query = """
            SELECT
                direction, outcome, macro_regime,
                entry_price, stop_price, target_1_price,
                mfe_5d, mae_5d, mfe_10d, mae_10d, mfe_20d, mae_20d,
                return_5d, return_10d, return_20d,
                hit_target_1, hit_stop, days_to_target, days_to_stop
            FROM predictions
            WHERE prediction_date >= :cutoff
              AND validated = 1
              AND outcome IN ('WIN', 'LOSS')
              AND mfe_20d IS NOT NULL
              AND mae_20d IS NOT NULL
        """
        rows = execute_query(query, {"cutoff": cutoff})

        if len(rows) < 10:
            return {
                "status": "insufficient_data",
                "sample_size": len(rows),
                "message": f"Need 10+ resolved predictions with MFE/MAE data, have {len(rows)}"
            }

        result = {
            "status": "optimized",
            "optimization_date": date.today().isoformat(),
            "period_days": days,
            "sample_size": len(rows),
        }

        # Overall analysis
        result["overall"] = self._analyze_group(rows, "ALL", "ALL")

        # By direction
        for direction in ["LONG", "SHORT"]:
            dir_rows = [r for r in rows if r["direction"] == direction]
            if len(dir_rows) >= 5:
                result[f"by_direction_{direction.lower()}"] = self._analyze_group(
                    dir_rows, direction, "ALL"
                )

        # By regime (if data exists)
        regimes = set(r["macro_regime"] for r in rows if r["macro_regime"])
        for regime in regimes:
            regime_rows = [r for r in rows if r["macro_regime"] == regime]
            if len(regime_rows) >= 5:
                result[f"by_regime_{regime.lower()}"] = self._analyze_group(
                    regime_rows, "BOTH", regime
                )

        # Store results
        self._store_optimization(result)

        return result

    def _analyze_group(self, rows: list, direction: str, regime: str) -> dict[str, Any]:
        """Analyze MFE/MAE for a group of predictions."""
        mfe_20 = [float(r["mfe_20d"]) for r in rows if r["mfe_20d"] is not None]
        mae_20 = [float(r["mae_20d"]) for r in rows if r["mae_20d"] is not None]
        mfe_10 = [float(r["mfe_10d"]) for r in rows if r["mfe_10d"] is not None]
        mae_10 = [float(r["mae_10d"]) for r in rows if r["mae_10d"] is not None]

        if not mfe_20 or not mae_20:
            return {"n": 0, "message": "No MFE/MAE data"}

        mfe_median = sorted(mfe_20)[len(mfe_20) // 2]
        mae_median = sorted(mae_20)[len(mae_20) // 2]

        # Winners analysis: how much MFE did winners achieve?
        winners = [r for r in rows if r["outcome"] == "WIN"]
        losers = [r for r in rows if r["outcome"] == "LOSS"]

        winner_mfe = [float(r["mfe_20d"]) for r in winners if r["mfe_20d"] is not None]
        winner_mae = [float(r["mae_20d"]) for r in winners if r["mae_20d"] is not None]
        loser_mfe = [float(r["mfe_20d"]) for r in losers if r["mfe_20d"] is not None]
        loser_mae = [float(r["mae_20d"]) for r in losers if r["mae_20d"] is not None]

        # Optimal stop: set at the 75th percentile of winner MAE
        # (only 25% of winners would have been stopped out)
        winner_mae_sorted = sorted(winner_mae) if winner_mae else [0]
        optimal_stop_pct = winner_mae_sorted[int(len(winner_mae_sorted) * 0.75)] if winner_mae_sorted else mae_median

        # Optimal target: set at 50th percentile of winner MFE
        # (captures the median favorable move)
        winner_mfe_sorted = sorted(winner_mfe) if winner_mfe else [0]
        optimal_target_pct = winner_mfe_sorted[len(winner_mfe_sorted) // 2] if winner_mfe_sorted else mfe_median

        # How many winners would have been stopped prematurely with current stops?
        premature_stops = 0
        for r in winners:
            if r["mae_20d"] is not None and r["stop_price"] and r["entry_price"]:
                entry = float(r["entry_price"])
                stop = float(r["stop_price"])
                if entry > 0:
                    stop_pct = abs(entry - stop) / entry * 100
                    if float(r["mae_20d"]) > stop_pct:
                        premature_stops += 1

        premature_pct = (premature_stops / len(winners) * 100) if winners else 0

        # Profit left on table: compare actual return vs MFE
        profit_left = []
        for r in winners:
            if r["return_20d"] is not None and r["mfe_20d"] is not None:
                left = float(r["mfe_20d"]) - abs(float(r["return_20d"]))
                if left > 0:
                    profit_left.append(left)

        avg_profit_left = mean(profit_left) if profit_left else 0

        return {
            "n": len(rows),
            "direction": direction,
            "regime": regime,
            "win_rate": round(len(winners) / len(rows) * 100, 1) if rows else 0,
            "mfe_20d_median": round(mfe_median, 3),
            "mae_20d_median": round(mae_median, 3),
            "mfe_10d_median": round(sorted(mfe_10)[len(mfe_10) // 2], 3) if mfe_10 else None,
            "mae_10d_median": round(sorted(mae_10)[len(mae_10) // 2], 3) if mae_10 else None,
            "optimal_stop_pct": round(optimal_stop_pct, 3),
            "optimal_target_pct": round(optimal_target_pct, 3),
            "winners_stopped_prematurely_pct": round(premature_pct, 1),
            "avg_profit_left_on_table_pct": round(avg_profit_left, 2),
            "recommendation": self._recommend(optimal_stop_pct, optimal_target_pct, premature_pct, avg_profit_left),
        }

    def _recommend(self, stop: float, target: float, premature: float, left: float) -> str:
        msgs = []
        if premature > 25:
            msgs.append(f"Widen stops — {premature:.0f}% of winners stopped out prematurely. Suggested stop: {stop:.1f}%")
        if left > 2.0:
            msgs.append(f"Raise targets — leaving {left:.1f}% profit on table. Suggested target: {target:.1f}%")
        if not msgs:
            msgs.append(f"Current levels reasonable. Optimal stop: {stop:.1f}%, target: {target:.1f}%")
        return "; ".join(msgs)

    def _store_optimization(self, result: dict) -> None:
        overall = result.get("overall", {})
        if not overall or overall.get("n", 0) == 0:
            return

        query = """
            INSERT INTO stop_target_optimization (
                optimization_date, direction, regime,
                optimal_stop_pct, optimal_target_pct,
                winners_stopped_prematurely_pct, profit_left_on_table_pct,
                mfe_median, mae_median, sample_size
            )
            VALUES (
                :opt_date, :direction, :regime,
                :stop_pct, :target_pct,
                :premature, :left_pct,
                :mfe_med, :mae_med, :sample_size
            )
        """
        try:
            execute_insert(query, {
                "opt_date": date.today(),
                "direction": overall.get("direction", "BOTH"),
                "regime": overall.get("regime", "ALL"),
                "stop_pct": overall.get("optimal_stop_pct"),
                "target_pct": overall.get("optimal_target_pct"),
                "premature": overall.get("winners_stopped_prematurely_pct"),
                "left_pct": overall.get("avg_profit_left_on_table_pct"),
                "mfe_med": overall.get("mfe_20d_median"),
                "mae_med": overall.get("mae_20d_median"),
                "sample_size": overall.get("n"),
            })
            logger.info("Stop/target optimization stored")
        except Exception as e:
            logger.error(f"Failed to store optimization: {e}")
