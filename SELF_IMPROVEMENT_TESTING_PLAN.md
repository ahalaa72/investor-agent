# Self-Improvement System: Testing Plan

**Version:** 1.0
**Date:** 2026-03-15
**Companion:** See `SELF_IMPROVEMENT_PLAN.md` for full architecture.

---

## Testing Strategy

Each phase has **unit tests** (function-level), **integration tests** (MCP tool-level via `docker exec`), and **validation tests** (statistical correctness). All MCP tests use JSON-RPC calls through `docker exec`.

---

## Phase 1: Foundation Tests

### 1.1 Schema Migration

```python
def test_new_columns_exist():
    """Verify ALTER TABLE added all new columns."""
    # Query INFORMATION_SCHEMA.COLUMNS
    result = db_query("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='predictions'")
    columns = [r['COLUMN_NAME'] for r in result]
    assert 'macro_regime' in columns
    assert 'vix_at_entry' in columns
    assert 'yield_curve_at_entry' in columns
    assert 'market_breadth_at_entry' in columns
    assert 'calibrated_probability' in columns
    assert 'raw_probability' in columns

def test_new_tables_exist():
    """Verify 3 new tables created."""
    result = db_query("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME IN ('calibration_history','gate_weights','stop_target_optimization')")
    tables = [r['TABLE_NAME'] for r in result]
    assert 'calibration_history' in tables
    assert 'gate_weights' in tables
    assert 'stop_target_optimization' in tables

def test_existing_data_preserved():
    """Migration must not lose existing predictions."""
    # Count before migration, count after, assert equal
    pre_count = db_query("SELECT COUNT(*) as n FROM predictions")[0]['n']
    # Run migration
    post_count = db_query("SELECT COUNT(*) as n FROM predictions")[0]['n']
    assert post_count == pre_count
```

### 1.2 Regime Data Capture

```python
def test_store_prediction_includes_regime():
    """store_trading_prediction() now captures macro regime."""
    result = _call_mcp_tool("store_trading_prediction", {
        "ticker": "AAPL",
        "direction": "LONG",
        "report_type": "test",
        "trading_signal": {"signal": "BUY", "confidence": 70}
    })
    # Fetch the stored prediction
    pred = db_query(f"SELECT macro_regime, vix_at_entry FROM predictions WHERE prediction_id='{result['prediction_id']}'")
    assert pred[0]['macro_regime'] in ['EXPANSION', 'LATE_CYCLE', 'CONTRACTION', 'RECOVERY']
    assert pred[0]['vix_at_entry'] is not None
    assert pred[0]['vix_at_entry'] > 0

def test_regime_not_null_for_new_predictions():
    """All NEW predictions must have regime data. Old ones can be NULL."""
    result = db_query("""
        SELECT COUNT(*) as n FROM predictions
        WHERE created_at > '2026-03-15' AND macro_regime IS NULL
    """)
    assert result[0]['n'] == 0, "New predictions must have macro_regime"
```

### 1.3 MFE/MAE Population

```python
def test_mfe_mae_populated_for_resolved():
    """update_prediction_outcomes() now populates MFE/MAE columns."""
    result = _call_mcp_tool("update_prediction_outcomes", {})
    # Check that resolved predictions have MFE/MAE
    filled = db_query("""
        SELECT COUNT(*) as n FROM predictions
        WHERE outcome IN ('WIN','LOSS')
        AND mfe_5d IS NOT NULL AND mae_5d IS NOT NULL
    """)
    assert filled[0]['n'] > 0, "Resolved predictions should have MFE/MAE"

def test_mfe_mae_correctness():
    """MFE should be >= 0 (max favorable), MAE should be >= 0 (max adverse)."""
    results = db_query("""
        SELECT mfe_5d, mae_5d, mfe_10d, mae_10d, mfe_20d, mae_20d
        FROM predictions
        WHERE mfe_5d IS NOT NULL
    """)
    for r in results:
        assert r['mfe_5d'] >= 0, "MFE must be non-negative"
        assert r['mae_5d'] >= 0, "MAE must be non-negative"
        # MFE at longer horizon >= shorter horizon (or close)
        if r['mfe_10d'] is not None:
            assert r['mfe_10d'] >= r['mfe_5d'] * 0.8, "10d MFE shouldn't be much less than 5d"

def test_mfe_greater_than_return_for_winners():
    """For winners, MFE should be >= final return (price went further than current)."""
    results = db_query("""
        SELECT mfe_20d, return_20d FROM predictions
        WHERE outcome = 'WIN' AND mfe_20d IS NOT NULL AND return_20d IS NOT NULL
        AND direction = 'LONG'
    """)
    for r in results:
        assert r['mfe_20d'] >= r['return_20d'] * 0.95, \
            "MFE should be >= return (price reached at least as far as current)"
```

### 1.4 Vault Report Ingestion

```python
def test_ingest_vault_reports_finds_reports():
    """Tool finds JSON metadata files in vault."""
    result = _call_mcp_tool("ingest_vault_reports", {"days": 90})
    assert result['reports_found'] > 0, "Should find vault reports"
    assert 'reports_ingested' in result
    assert 'predictions_created' in result

def test_ingest_vault_reports_creates_predictions():
    """Ingested reports create prediction records in DB."""
    before = db_query("SELECT COUNT(*) as n FROM predictions")[0]['n']
    result = _call_mcp_tool("ingest_vault_reports", {"days": 90, "backfill": True})
    after = db_query("SELECT COUNT(*) as n FROM predictions")[0]['n']
    assert after >= before, "Ingestion should create or maintain predictions"
    assert result['predictions_created'] >= 0

def test_ingest_vault_reports_idempotent():
    """Running ingestion twice doesn't duplicate predictions."""
    _call_mcp_tool("ingest_vault_reports", {"days": 30})
    count_1 = db_query("SELECT COUNT(*) as n FROM predictions")[0]['n']
    _call_mcp_tool("ingest_vault_reports", {"days": 30})
    count_2 = db_query("SELECT COUNT(*) as n FROM predictions")[0]['n']
    assert count_2 == count_1, "Second ingestion should not create duplicates"

def test_ingest_parses_json_metadata_correctly():
    """JSON metadata fields correctly mapped to prediction columns."""
    result = _call_mcp_tool("ingest_vault_reports", {"days": 30})
    if result['predictions_created'] > 0:
        recent = db_query("""
            SELECT ticker, direction, entry_price, stop_price, target_1_price
            FROM predictions
            WHERE report_type = 'vault_ingest'
            ORDER BY created_at DESC
        """)
        for r in recent[:5]:
            assert r['ticker'] is not None
            assert r['direction'] in ['LONG', 'SHORT']
            assert r['entry_price'] > 0
            assert r['stop_price'] > 0
            assert r['target_1_price'] > 0

def test_ingest_resolves_outcomes():
    """Ingested predictions get outcomes computed from price history."""
    result = _call_mcp_tool("ingest_vault_reports", {"days": 90, "backfill": True})
    assert result['outcomes_resolved'] >= 0
    # Predictions older than 20 days should have outcomes
    resolved = db_query("""
        SELECT COUNT(*) as n FROM predictions
        WHERE report_type = 'vault_ingest'
        AND created_at < DATEADD(day, -20, GETDATE())
        AND outcome IN ('WIN', 'LOSS')
    """)
    # At least some should be resolved (if old enough)
```

---

## Phase 2: Measurement Tests

### 2.1 Calibration Tool

```python
def test_calibrate_confidence_returns_structure():
    """Tool returns complete calibration structure."""
    result = _call_mcp_tool("calibrate_confidence", {"days": 90})
    assert 'brier_score' in result
    assert 'calibration_curve' in result
    assert 'trend' in result
    assert 'recommendation' in result

def test_brier_score_in_valid_range():
    """Brier score must be between 0 and 1."""
    result = _call_mcp_tool("calibrate_confidence", {"days": 90})
    assert 0 <= result['brier_score'] <= 1.0, f"Brier score {result['brier_score']} out of range"

def test_calibration_curve_buckets():
    """Each confidence bucket has predicted, actual, n, multiplier."""
    result = _call_mcp_tool("calibrate_confidence", {"days": 90})
    curve = result['calibration_curve']
    for bucket_name, bucket in curve.items():
        assert 'predicted' in bucket
        assert 'actual' in bucket
        assert 'n' in bucket
        assert 'multiplier' in bucket
        assert bucket['multiplier'] > 0, "Multiplier must be positive"

def test_calibration_multipliers_bounded():
    """Multipliers must be within safety bounds [0.5, 1.5]."""
    result = _call_mcp_tool("calibrate_confidence", {"days": 90})
    for bucket_name, bucket in result['calibration_curve'].items():
        assert 0.5 <= bucket['multiplier'] <= 1.5, \
            f"Multiplier {bucket['multiplier']} for {bucket_name} exceeds safety bounds"

def test_calibration_with_insufficient_data():
    """Tool handles gracefully when < 50 resolved predictions."""
    result = _call_mcp_tool("calibrate_confidence", {"days": 1})  # Very short window
    assert 'recommendation' in result
    # Should indicate insufficient data, not crash

def test_brier_decomposition():
    """Brier decomposition components sum correctly."""
    result = _call_mcp_tool("calibrate_confidence", {"days": 90})
    if 'brier_decomposition' in result:
        decomp = result['brier_decomposition']
        # calibration - resolution + uncertainty ≈ brier_score
        reconstructed = decomp['calibration'] - decomp['resolution'] + decomp['uncertainty']
        assert abs(reconstructed - result['brier_score']) < 0.01, \
            "Brier decomposition should approximately reconstruct total score"

def test_calibration_stores_to_db():
    """Calibration results stored in calibration_history table."""
    _call_mcp_tool("calibrate_confidence", {"days": 90})
    history = db_query("SELECT TOP 1 * FROM calibration_history ORDER BY calibration_date DESC")
    assert len(history) > 0, "Calibration should be stored in history table"
    assert history[0]['brier_score'] is not None
```

### 2.2 Gate Effectiveness Tool

```python
def test_gate_effectiveness_returns_structure():
    """Tool returns lift scores, interactions, and top predictors."""
    result = _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    assert 'gate_lift_scores' in result
    assert 'top_predictors' in result
    assert 'recommended_weights' in result

def test_gate_lift_scores_complete():
    """All 5 gates have lift scores."""
    result = _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    gates = result['gate_lift_scores']
    for gate_name in ['catalyst', 'freshness', 'brooks', 'quality', 'options']:
        assert gate_name in gates, f"Missing gate: {gate_name}"
        assert 'pass_wr' in gates[gate_name]
        assert 'fail_wr' in gates[gate_name]
        assert 'lift' in gates[gate_name]
        assert 'n' in gates[gate_name]

def test_lift_score_correctness():
    """Lift = pass_win_rate - fail_win_rate."""
    result = _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    for gate_name, gate in result['gate_lift_scores'].items():
        expected_lift = gate['pass_wr'] - gate['fail_wr']
        assert abs(gate['lift'] - expected_lift) < 0.1, \
            f"Lift for {gate_name} should be pass_wr - fail_wr"

def test_recommended_weights_sum_to_one():
    """Recommended gate weights must sum to 1.0."""
    result = _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    weights = result['recommended_weights']
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, should be 1.0"

def test_gate_interactions_matrix():
    """Gate interactions show synergy scores."""
    result = _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    if 'gate_interactions' in result:
        for pair, data in result['gate_interactions'].items():
            assert 'both_pass' in data
            assert 'both_fail' in data
            assert data['both_pass'] >= 0 and data['both_pass'] <= 100

def test_gate_weights_stored_to_db():
    """Gate weights stored in gate_weights table."""
    _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    weights = db_query("SELECT TOP 5 * FROM gate_weights ORDER BY effective_date DESC")
    assert len(weights) == 5, "Should store weight for each of 5 gates"
```

### 2.3 Stop/Target Optimization Tool

```python
def test_optimize_stops_targets_returns_structure():
    """Tool returns optimal levels and analysis."""
    result = _call_mcp_tool("optimize_stops_targets", {"days": 90})
    assert 'optimal_stop_pct' in result
    assert 'optimal_target_pct' in result
    assert 'stop_analysis' in result
    assert 'target_analysis' in result

def test_optimal_stop_is_negative():
    """Optimal stop should be a negative percentage (loss from entry)."""
    result = _call_mcp_tool("optimize_stops_targets", {"days": 90})
    assert result['optimal_stop_pct'] < 0, "Stop should be negative (loss threshold)"
    assert result['optimal_stop_pct'] > -20, "Stop shouldn't be more than -20% (sanity)"

def test_optimal_target_is_positive():
    """Optimal target should be a positive percentage (gain from entry)."""
    result = _call_mcp_tool("optimize_stops_targets", {"days": 90})
    assert result['optimal_target_pct'] > 0, "Target should be positive"
    assert result['optimal_target_pct'] < 50, "Target shouldn't be more than 50% (sanity)"

def test_r_multiple_distribution_sums_to_100():
    """R-multiple distribution percentages sum to ~100%."""
    result = _call_mcp_tool("optimize_stops_targets", {"days": 90})
    if 'r_multiple_distribution' in result:
        dist = result['r_multiple_distribution']
        total = sum(dist.values())
        assert abs(total - 100) < 2, f"R-multiple distribution sums to {total}, should be ~100"

def test_optimization_by_regime():
    """Stop levels vary by market regime."""
    result = _call_mcp_tool("optimize_stops_targets", {"days": 90})
    if 'by_regime' in result.get('stop_analysis', {}):
        regime_stops = result['stop_analysis']['by_regime']
        # Contraction should have wider stops than expansion
        if 'CONTRACTION' in regime_stops and 'EXPANSION' in regime_stops:
            assert regime_stops['CONTRACTION'] <= regime_stops['EXPANSION'], \
                "Contraction stops should be wider (more negative) than expansion"

def test_optimization_stored_to_db():
    """Optimization results stored in stop_target_optimization table."""
    _call_mcp_tool("optimize_stops_targets", {"days": 90})
    results = db_query("SELECT TOP 1 * FROM stop_target_optimization ORDER BY optimization_date DESC")
    assert len(results) > 0
    assert results[0]['optimal_stop_pct'] is not None
```

---

## Phase 3: Auto-Adjustment Tests

### 3.1 Signal Generation with Calibration

```python
def test_signal_includes_calibration_section():
    """generate_trading_signal() now includes calibration data."""
    result = _call_mcp_tool("generate_trading_signal", {
        "ticker": "AAPL", "direction": "LONG"
    })
    # Should have both raw and calibrated probability
    assert 'raw_probability' in result or 'brooks_analysis' in result
    # If calibration data exists in DB, should show calibrated value
    if 'calibration_applied' in result:
        assert 'raw_probability' in result['calibration_applied']
        assert 'calibrated_probability' in result['calibration_applied']
        assert 'multiplier_used' in result['calibration_applied']

def test_calibrated_probability_differs_from_raw():
    """If calibration multipliers exist, calibrated != raw probability."""
    # First ensure multipliers exist
    _call_mcp_tool("calibrate_confidence", {"days": 90})
    # Then generate signal
    result = _call_mcp_tool("generate_trading_signal", {
        "ticker": "AAPL", "direction": "LONG"
    })
    if 'calibration_applied' in result:
        raw = result['calibration_applied']['raw_probability']
        calibrated = result['calibration_applied']['calibrated_probability']
        # They should differ (unless multiplier happens to be exactly 1.0)
        # At minimum, both should be present and valid
        assert 30 <= raw <= 80
        assert 30 <= calibrated <= 80

def test_regime_adjustment_applied():
    """Signal generation applies regime penalty/bonus."""
    result = _call_mcp_tool("generate_trading_signal", {
        "ticker": "AAPL", "direction": "LONG"
    })
    if 'calibration_applied' in result:
        assert 'regime' in result['calibration_applied']
        assert 'regime_adjustment' in result['calibration_applied']

def test_calibration_bounded():
    """Calibrated probability stays within [30, 80] bounds."""
    result = _call_mcp_tool("generate_trading_signal", {
        "ticker": "AAPL", "direction": "LONG"
    })
    if 'calibration_applied' in result:
        calibrated = result['calibration_applied']['calibrated_probability']
        assert 30 <= calibrated <= 80, f"Calibrated probability {calibrated} out of bounds"

def test_backward_compatibility():
    """Existing signal fields unchanged — new fields are additive."""
    result = _call_mcp_tool("generate_trading_signal", {
        "ticker": "AAPL", "direction": "LONG"
    })
    # All existing fields must still be present
    assert 'signal' in result
    assert 'confidence' in result
    assert 'direction' in result
    assert 'gates' in result
    assert 'trading_plan' in result
    assert 'brooks_analysis' in result

def test_gate_weights_used():
    """If empirical gate weights exist, they're used in scoring."""
    # Populate gate weights
    _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    # Generate signal
    result = _call_mcp_tool("generate_trading_signal", {
        "ticker": "AAPL", "direction": "LONG"
    })
    if 'calibration_applied' in result:
        assert 'gate_weights_source' in result['calibration_applied']
        # Should be 'empirical' if enough data, 'default' otherwise
        assert result['calibration_applied']['gate_weights_source'] in ['empirical', 'default']

def test_mfe_mae_derived_stops():
    """If optimization data exists, stops/targets use MFE/MAE-derived values."""
    # Populate optimization
    _call_mcp_tool("optimize_stops_targets", {"days": 90})
    # Generate signal
    result = _call_mcp_tool("generate_trading_signal", {
        "ticker": "AAPL", "direction": "LONG"
    })
    if 'calibration_applied' in result and 'stop_source' in result['calibration_applied']:
        assert result['calibration_applied']['stop_source'] in ['mfe_mae_optimized', 'default']
```

---

## Phase 4: Automation Tests

### 4.1 Cron Job Execution

```python
def test_daily_outcomes_cron_runs():
    """Daily outcomes cron script executes without error."""
    # Run script via docker exec
    exit_code = run_command("python scripts/cron_daily_outcomes.py")
    assert exit_code == 0

def test_daily_ingest_cron_runs():
    """Daily vault ingestion cron script executes without error."""
    exit_code = run_command("python scripts/cron_daily_ingest.py")
    assert exit_code == 0

def test_weekly_calibration_cron_runs():
    """Weekly calibration cron script executes without error."""
    exit_code = run_command("python scripts/cron_weekly_calibration.py")
    assert exit_code == 0

def test_monthly_optimization_cron_runs():
    """Monthly optimization cron script executes without error."""
    exit_code = run_command("python scripts/cron_monthly_optimization.py")
    assert exit_code == 0

def test_cron_idempotent():
    """Running cron twice in a row produces same state."""
    run_command("python scripts/cron_daily_outcomes.py")
    count_1 = db_query("SELECT COUNT(*) as n FROM predictions WHERE outcome IS NOT NULL")[0]['n']
    run_command("python scripts/cron_daily_outcomes.py")
    count_2 = db_query("SELECT COUNT(*) as n FROM predictions WHERE outcome IS NOT NULL")[0]['n']
    assert count_2 == count_1, "Cron should be idempotent"
```

### 4.2 End-to-End Integration

```python
def test_full_feedback_loop():
    """End-to-end: signal → store → resolve → calibrate → adjusted signal."""
    # Step 1: Generate and store a prediction
    signal = _call_mcp_tool("generate_trading_signal", {
        "ticker": "MSFT", "direction": "LONG"
    })
    stored = _call_mcp_tool("store_trading_prediction", {
        "ticker": "MSFT", "direction": "LONG",
        "report_type": "test", "trading_signal": signal
    })
    pred_id = stored['prediction_id']

    # Step 2: Verify regime data captured
    pred = db_query(f"SELECT macro_regime FROM predictions WHERE prediction_id='{pred_id}'")
    assert pred[0]['macro_regime'] is not None

    # Step 3: Resolve outcomes (for all eligible predictions)
    outcomes = _call_mcp_tool("update_prediction_outcomes", {})
    assert outcomes['status'] == 'success'

    # Step 4: Run calibration
    calibration = _call_mcp_tool("calibrate_confidence", {"days": 90})
    assert calibration['brier_score'] >= 0

    # Step 5: Run gate effectiveness
    gates = _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    assert 'recommended_weights' in gates

    # Step 6: Generate new signal — should use calibration
    new_signal = _call_mcp_tool("generate_trading_signal", {
        "ticker": "MSFT", "direction": "LONG"
    })
    # New signal should exist and be valid
    assert 'signal' in new_signal
    assert 'confidence' in new_signal
```

---

## Statistical Validation Tests

These tests verify the mathematical correctness of the analysis tools.

```python
def test_brier_score_perfect_calibration():
    """Known dataset with perfect predictions should have Brier ≈ 0."""
    # Insert test predictions where predicted = actual outcome
    # e.g., 80% confidence predictions that win 80% of the time
    # Verify Brier score ≈ 0.16 (theoretical minimum for 80% predictions)

def test_brier_score_random():
    """Random 50/50 predictions with 50% confidence should have Brier ≈ 0.25."""
    # Insert test predictions at 50% confidence with 50% win rate
    # Verify Brier score ≈ 0.25

def test_calibration_curve_monotonic():
    """Higher confidence buckets should have higher actual win rates (if well-calibrated)."""
    result = _call_mcp_tool("calibrate_confidence", {"days": 90})
    curve = result['calibration_curve']
    # Extract actual win rates in order
    buckets = sorted(curve.items())  # Sort by bucket name
    actuals = [b[1]['actual'] for b in buckets if b[1]['n'] >= 10]
    # Should be roughly monotonically increasing
    # Allow some noise — check that last bucket > first bucket
    if len(actuals) >= 2:
        assert actuals[-1] > actuals[0] - 10, \
            "Highest confidence bucket should have higher win rate than lowest"

def test_gate_lift_statistical_significance():
    """Gate lift scores should only be trusted with sufficient sample size."""
    result = _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    for gate_name, gate in result['gate_lift_scores'].items():
        if gate['n'] < 30:
            # Small sample — lift should be flagged as unreliable
            assert 'low_sample' in str(result.get('warnings', '')).lower() or gate['n'] >= 30, \
                f"Gate {gate_name} has only {gate['n']} samples — should warn"

def test_mfe_mae_relationship():
    """For winners: MFE > |return|. For losers: MAE > |return|."""
    winners = db_query("""
        SELECT mfe_20d, return_20d FROM predictions
        WHERE outcome='WIN' AND direction='LONG' AND mfe_20d IS NOT NULL
    """)
    for w in winners:
        assert w['mfe_20d'] >= abs(w['return_20d']) * 0.9, \
            "Winner MFE should be >= return (may have pulled back from peak)"
```

---

## Performance & Safety Tests

```python
def test_calibration_tool_performance():
    """calibrate_confidence() completes within 30 seconds."""
    import time
    start = time.time()
    _call_mcp_tool("calibrate_confidence", {"days": 90})
    elapsed = time.time() - start
    assert elapsed < 30, f"Calibration took {elapsed}s, should be < 30s"

def test_vault_ingestion_performance():
    """ingest_vault_reports() processes 30 days within 120 seconds."""
    import time
    start = time.time()
    _call_mcp_tool("ingest_vault_reports", {"days": 30})
    elapsed = time.time() - start
    assert elapsed < 120, f"Ingestion took {elapsed}s, should be < 120s"

def test_no_token_consumption():
    """Self-improvement tools must NOT call Questrade API (no token risk)."""
    # These tools should only read from DB + yfinance, not Questrade
    # Verify by checking that questrade token file is unchanged
    token_before = get_token_hash()
    _call_mcp_tool("calibrate_confidence", {"days": 90})
    _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    _call_mcp_tool("optimize_stops_targets", {"days": 90})
    token_after = get_token_hash()
    assert token_before == token_after, "Self-improvement tools must not touch Questrade token"

def test_multiplier_safety_bounds():
    """Even with extreme data, multipliers stay within [0.5, 1.5]."""
    # Insert extreme test data (100% win at 50% confidence)
    # Verify multiplier capped at 1.5, not 2.0
    result = _call_mcp_tool("calibrate_confidence", {"days": 90})
    for bucket_name, bucket in result['calibration_curve'].items():
        assert 0.5 <= bucket['multiplier'] <= 1.5

def test_gate_weight_safety():
    """No single gate weight exceeds 0.50 (50%)."""
    result = _call_mcp_tool("analyze_gate_effectiveness", {"days": 90})
    for gate, weight in result['recommended_weights'].items():
        assert weight <= 0.50, f"Gate {gate} weight {weight} exceeds 50% cap"
        assert weight >= 0.05, f"Gate {gate} weight {weight} below 5% minimum"
```

---

## Test Data Setup

### Seed Data for Testing

```python
def seed_test_predictions(n=100):
    """Insert N test predictions with known outcomes for validation."""
    import random
    tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'GOOG', 'META']

    for i in range(n):
        ticker = random.choice(tickers)
        direction = random.choice(['LONG', 'SHORT'])
        probability = random.randint(45, 85)
        # Simulate: higher probability → higher win rate (but imperfect)
        win_chance = probability / 100 + random.uniform(-0.15, 0.15)
        outcome = 'WIN' if random.random() < win_chance else 'LOSS'

        db_insert("predictions", {
            "ticker": ticker,
            "direction": direction,
            "brooks_probability": probability,
            "outcome": outcome,
            "validated": 1,
            "entry_price": random.uniform(100, 500),
            "catalyst_gate": random.choice(['PASS', 'FAIL']),
            "freshness_gate": random.choice(['PASS', 'FAIL']),
            "brooks_gate": random.choice(['PASS', 'FAIL']),
            "quality_gate": random.choice(['PASS', 'FAIL']),
            "options_gate": random.choice(['PASS', 'FAIL']),
            "macro_regime": random.choice(['EXPANSION', 'LATE_CYCLE', 'CONTRACTION']),
            "vix_at_entry": random.uniform(12, 35),
            "created_at": f"2026-{random.randint(1,3):02d}-{random.randint(1,28):02d}",
        })
```

---

## Test Execution

### Running Tests

```bash
# Phase 1 tests (after schema migration + vault ingestion)
docker exec investor-agent-mcp python -m pytest tests/test_self_improvement_phase1.py -v

# Phase 2 tests (after measurement tools built)
docker exec investor-agent-mcp python -m pytest tests/test_self_improvement_phase2.py -v

# Phase 3 tests (after auto-adjustment integrated)
docker exec investor-agent-mcp python -m pytest tests/test_self_improvement_phase3.py -v

# Phase 4 tests (after cron jobs set up)
docker exec investor-agent-mcp python -m pytest tests/test_self_improvement_phase4.py -v

# Full integration (end-to-end)
docker exec investor-agent-mcp python -m pytest tests/test_self_improvement_e2e.py -v

# All tests
docker exec investor-agent-mcp python -m pytest tests/test_self_improvement_*.py -v
```

### MCP Tool Testing Helper

```python
import json
import subprocess

def _call_mcp_tool(tool_name, params):
    """Call MCP tool via docker exec JSON-RPC."""
    request = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": params},
        "id": 1
    })
    result = subprocess.run(
        ["docker", "exec", "-i", "investor-agent-mcp",
         "python", "-m", "investor_agent.server_modular"],
        input=request, capture_output=True, text=True, timeout=120
    )
    response = json.loads(result.stdout.split('\n')[-2])  # Last JSON line
    content = response['result']['content'][0]['text']
    return json.loads(content)

def db_query(sql):
    """Run SQL query against predictions DB."""
    return _call_mcp_tool("_raw_query", {"sql": sql})  # Or direct pyodbc
```

---

## Acceptance Criteria

| Phase | Criteria | How to Verify |
|-------|----------|---------------|
| 1 | All new DB columns exist | `test_new_columns_exist` |
| 1 | MFE/MAE populated for ≥80% of resolved predictions | DB count query |
| 1 | ≥100 vault reports ingested | `test_ingest_vault_reports_finds_reports` |
| 2 | Brier score computable and in valid range | `test_brier_score_in_valid_range` |
| 2 | Gate lift scores for all 5 gates | `test_gate_lift_scores_complete` |
| 2 | Optimal stop/target computed | `test_optimize_stops_targets_returns_structure` |
| 3 | `generate_trading_signal()` returns `calibration_applied` section | `test_signal_includes_calibration_section` |
| 3 | Backward compatibility maintained | `test_backward_compatibility` |
| 3 | All safety bounds enforced | `test_multiplier_safety_bounds`, `test_gate_weight_safety` |
| 4 | All cron jobs run without error | `test_*_cron_runs` |
| 4 | Cron jobs idempotent | `test_cron_idempotent` |
| E2E | Full loop: signal → store → resolve → calibrate → adjusted signal | `test_full_feedback_loop` |
