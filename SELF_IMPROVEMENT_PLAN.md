# Self-Improving Trading System: Implementation Plan

**Version:** 1.0
**Date:** 2026-03-15
**Status:** PLANNED

---

## Executive Summary

Transform the investor-agent from an **open-loop** system (measures but never adjusts) into a **closed-loop** system that continuously improves signal accuracy, gate weights, stop/target levels, and confidence calibration using empirical outcome data.

### Current State

| Asset | Count | Status |
|-------|-------|--------|
| MCP Tools | 89 | All documented |
| Vault Reports | 257+ | **Write-only** (never read back) |
| DB Schema | 122 columns | MFE/MAE columns **never populated** |
| Tracking Tools | 7 | Measure accuracy but **don't adjust anything** |
| Efficiency Reports | Weekly | Suggestions generated but **never enforced** |
| JSON Metadata | 257+ files | In `/Ahmed/Trading Reports/` — machine-readable but unused |
| Checkpoint Data | 252K files | Raw MCP outputs in `.checkpoints/` — unused |

### Target State

| Capability | Mechanism |
|-----------|-----------|
| Confidence calibration | Brier score + calibration curve → adjustment multipliers applied automatically |
| Gate weighting | Empirical lift scores per gate → weighted signal generation |
| Stop/target optimization | MFE/MAE analysis → data-driven defaults replace hardcoded % |
| Regime awareness | Macro regime stored at prediction time → regime-adjusted confidence |
| Vault feedback | 257+ reports parsed → predictions DB populated → statistical analysis |

---

## Architecture: 5 Feedback Loops

### Loop 1: Calibration Engine (HIGHEST IMPACT)

**Problem:** When the system says "72% probability," we don't know if it actually wins 72% of the time.

**Mechanism:**
1. Compute **Brier Score** across all resolved predictions
   - Formula: `mean((predicted_probability - actual_outcome)^2)`
   - Perfect = 0.0, random coin flip = 0.25, always wrong = 1.0
2. Build **calibration curve** (reliability diagram)
   - Bucket predictions by confidence: 50-60%, 60-70%, 70-80%, 80+%
   - Measure actual win rate per bucket
   - Perfect calibration = diagonal line
3. Generate **confidence adjustment multipliers**
   - Per bucket: `multiplier = actual_win_rate / predicted_confidence`
   - Example: "80% confidence" predictions win 65% → multiplier = 0.8125
   - Store multipliers in `component_accuracy` table

**New MCP Tool:** `calibrate_confidence(days=90)`

```python
# Returns:
{
    "brier_score": 0.21,                    # Overall calibration quality
    "brier_decomposition": {
        "calibration": 0.08,                # How accurate probabilities are
        "resolution": 0.12,                 # Can system distinguish easy/hard?
        "uncertainty": 0.25                 # Base rate difficulty
    },
    "calibration_curve": {
        "50-60%": {"predicted": 55, "actual": 52, "n": 34, "multiplier": 0.945},
        "60-70%": {"predicted": 65, "actual": 58, "n": 28, "multiplier": 0.892},
        "70-80%": {"predicted": 75, "actual": 68, "n": 19, "multiplier": 0.907},
        "80+%":   {"predicted": 85, "actual": 72, "n": 8,  "multiplier": 0.847}
    },
    "trend": {                              # Is calibration improving?
        "30d_brier": 0.23,
        "60d_brier": 0.21,
        "90d_brier": 0.22,
        "direction": "IMPROVING"
    },
    "recommendation": "System is overconfident by ~12%. Apply multipliers to reduce."
}
```

**Auto-adjustment integration point:** `generate_trading_signal()` reads multipliers from DB and applies:
```python
calibrated_probability = raw_probability * multiplier[bucket]
```

**Data source:** Already in `predictions` table — `brooks_probability` + `outcome` fields. Just needs the math.

---

### Loop 2: Vault Report Ingestion (UNLOCK 257+ DEAD REPORTS)

**Problem:** 257+ rich reports with ~75 metrics each sit unused. `vault_file` column stores the path but nothing reads it back.

**Data sources (priority order):**

1. **JSON metadata files** (highest priority — already machine-readable)
   - Location: `/Users/AhmedE/Ahmed/Trading Reports/*.json`
   - Fields: ticker, signal, confidence, current_price, entry_price, stop_loss, target_1, target_2, risk_reward_ratio, direction, gates (5 statuses), gates_passed, iv_rank, rsi, data_source, key_catalyst
   - Parse: `json.load()` — no regex needed

2. **Checkpoint MCP data** (raw tool outputs)
   - Location: `/Users/AhmedE/Ahmed/Trading Reports/.checkpoints/*_mcp_data.json`
   - Contains: Complete raw MCP tool responses for each analysis
   - Value: Ground truth verification — can confirm gate pass/fail against actual data

3. **Markdown reports** (richest but requires parsing)
   - Location: `/Users/AhmedE/Ahmed/Trading Reports/*.md` + `/Users/AhmedE/Ahmed/*.md`
   - Extractable: Executive summary tables, 5-gate status, technical indicators, Dalio metrics, Brooks analysis, trading plan levels
   - Parse: Regex for structured sections (tables, key-value pairs)

**New MCP Tool:** `ingest_vault_reports(days=30, backfill=False)`

```python
# Returns:
{
    "reports_found": 45,
    "reports_ingested": 38,
    "reports_skipped": 7,                   # Already in DB
    "predictions_created": 32,              # New predictions from vault
    "predictions_updated": 6,               # Existing predictions enriched
    "outcomes_resolved": 28,                # Outcomes computed from price history
    "data_sources": {
        "json_metadata": 38,
        "checkpoint_mcp": 35,
        "markdown_parsed": 38
    }
}
```

**Outcome resolution:** For each ingested report:
1. Extract entry_price, stop_price, target_1, target_2, prediction_date
2. Fetch actual prices at 5d/10d/20d/60d post-entry via `yfinance`
3. Compute: `return_Xd`, `hit_target`, `hit_stop`, `days_to_target`, `days_to_stop`
4. Populate MFE/MAE (see Loop 5)

**Backfill mode:** `backfill=True` processes ALL historical reports (257+), not just recent.

---

### Loop 3: Gate Effectiveness Scoring (WHICH GATES MATTER?)

**Problem:** All 5 gates treated equally, but some may be noise. No interaction analysis.

**Mechanism:**

1. **Individual gate lift:** For each gate, compare win rate when PASS vs FAIL
   ```
   Gate 1 (Catalyst):  PASS → 68% win rate, FAIL → 42% win rate → Lift = +26%
   Gate 2 (Freshness):  PASS → 61% win rate, FAIL → 55% win rate → Lift = +6%
   Gate 3 (Brooks):     PASS → 72% win rate, FAIL → 38% win rate → Lift = +34%
   Gate 4 (Quality):    PASS → 59% win rate, FAIL → 52% win rate → Lift = +7%
   Gate 5 (Options):    PASS → 63% win rate, FAIL → 57% win rate → Lift = +6%
   ```

2. **Gate pair interactions:** 2x2 matrix for each gate pair
   ```
   Catalyst PASS + Brooks PASS = 75% win rate
   Catalyst PASS + Brooks FAIL = 48% win rate
   Catalyst FAIL + Brooks PASS = 55% win rate
   Catalyst FAIL + Brooks FAIL = 32% win rate
   ```

3. **Sub-component predictive power:** Rank all 38+ stored fields by correlation with outcome
   ```
   Top 5: brooks_probability (r=0.42), catalyst_strength (r=0.38), ...
   Bottom 5: iv_rank (r=0.05), put_call_ratio (r=0.03), ...
   ```

4. **Feature importance:** Logistic regression on stored predictions → coefficient weights

**New MCP Tool:** `analyze_gate_effectiveness(days=90)`

```python
# Returns:
{
    "gate_lift_scores": {
        "catalyst": {"pass_wr": 68, "fail_wr": 42, "lift": 26, "n": 120},
        "brooks":   {"pass_wr": 72, "fail_wr": 38, "lift": 34, "n": 115},
        # ...
    },
    "gate_interactions": {
        "catalyst+brooks": {"both_pass": 75, "both_fail": 32, "synergy": 8},
        # ...
    },
    "top_predictors": [
        {"field": "brooks_probability", "correlation": 0.42, "p_value": 0.001},
        {"field": "catalyst_strength", "correlation": 0.38, "p_value": 0.003},
        # ...
    ],
    "weak_predictors": [
        {"field": "iv_rank", "correlation": 0.05, "p_value": 0.45},
        # ...
    ],
    "recommended_weights": {
        "catalyst": 0.22, "freshness": 0.12, "brooks": 0.35,
        "quality": 0.15, "options": 0.16
    }
}
```

**Auto-adjustment:** `generate_trading_signal()` uses empirical weights instead of equal weighting. Gates with 0% lift get reduced weight. Gates with 30%+ lift get increased weight.

**Minimum sample size:** Require 50+ resolved predictions per gate before adjusting weights. Below that, use equal weights (current behavior).

---

### Loop 4: Market Regime Stratification (CONTEXT-AWARE ACCURACY)

**Problem:** Predictions stored without macro context. If LONG signals fail 60% during corrections, the system doesn't know.

**New DB columns for `predictions` table:**

```sql
ALTER TABLE predictions ADD macro_regime VARCHAR(20);      -- EXPANSION/LATE_CYCLE/CONTRACTION/RECOVERY
ALTER TABLE predictions ADD vix_at_entry DECIMAL(8,2);     -- VIX level when prediction made
ALTER TABLE predictions ADD yield_curve_at_entry DECIMAL(8,4); -- 10Y-3M spread
ALTER TABLE predictions ADD market_breadth_at_entry DECIMAL(8,2); -- % above 200 SMA
```

**Mechanism:**

1. At prediction time: `get_macro_regime()` → store regime + VIX in prediction row
2. Track accuracy stratified by regime:
   ```
   EXPANSION:   LONG 72% win rate, SHORT 35% win rate (n=89)
   LATE_CYCLE:  LONG 55% win rate, SHORT 52% win rate (n=45)
   CONTRACTION: LONG 38% win rate, SHORT 68% win rate (n=32)
   RECOVERY:    LONG 65% win rate, SHORT 40% win rate (n=21)
   ```
3. Track accuracy by VIX bucket:
   ```
   VIX <15:  LONG 70%, SHORT 30% (complacent — longs work)
   VIX 15-25: LONG 58%, SHORT 48% (normal)
   VIX 25-35: LONG 42%, SHORT 62% (elevated — shorts work)
   VIX >35:  LONG 35%, SHORT 55% (panic — mean reversion)
   ```

**Auto-adjustment:** When `get_macro_regime()` returns CONTRACTION:
- Apply regime penalty to LONG confidence: `calibrated * 0.75`
- Apply regime bonus to SHORT confidence: `calibrated * 1.15`
- Tighten entry criteria: require 4/5 gates instead of 3/5
- Reduce position sizing multiplier by 30%
- Flag in report: "Regime-adjusted confidence: 72% raw → 54% adjusted (CONTRACTION -25%)"

**Integration point:** `store_trading_prediction()` calls `get_macro_regime()` internally and stores regime data automatically.

---

### Loop 5: Intrabar Extremes — MFE/MAE (STOP & TARGET OPTIMIZATION)

**Problem:** Schema has `mfe_5d`, `mae_5d`, `mfe_10d`, `mae_10d`, `mfe_20d`, `mae_20d` columns — **never populated**.

**Mechanism:**

1. For each resolved prediction, fetch daily OHLC for 5/10/20 days post-entry via `yfinance`
2. Compute:
   - **MFE (Max Favorable Excursion):** Best price reached in our direction
     - LONG: `max(high_prices) - entry_price`
     - SHORT: `entry_price - min(low_prices)`
   - **MAE (Max Adverse Excursion):** Worst price reached against us
     - LONG: `entry_price - min(low_prices)`
     - SHORT: `max(high_prices) - entry_price`

3. Analyze distributions:
   ```
   Winners (n=85):
     Avg MFE: +8.2%  →  Targets could be higher
     Avg MAE: -2.1%  →  Stops at -2% would've been fine

   Losers (n=42):
     Avg MFE: +3.1%  →  Had brief profit window (could've scaled)
     Avg MAE: -5.8%  →  Went deep against before hitting stop

   Key insight: Winners rarely go below -3%. Stops tighter than -3%
   cut winners prematurely. Optimal stop = -4.5% (captures 85% of winners).
   ```

**New MCP Tool:** `optimize_stops_targets(days=90, direction="BOTH")`

```python
# Returns:
{
    "optimal_stop_pct": -4.5,               # Data-driven stop level
    "optimal_target_pct": 7.2,              # Data-driven target level
    "current_stop_avg": -3.0,               # What we're using now
    "current_target_avg": 5.0,              # What we're using now
    "stop_analysis": {
        "too_tight_pct": 22,                # % of winners stopped out prematurely
        "optimal_range": [-3.5, -5.5],      # Sweet spot
        "by_regime": {
            "EXPANSION": -3.5,
            "CONTRACTION": -6.0             # Wider stops in volatile markets
        }
    },
    "target_analysis": {
        "left_on_table_pct": 35,            # % of winners that went much further
        "mfe_percentiles": {
            "25th": 3.2, "50th": 6.8, "75th": 12.1, "90th": 18.5
        }
    },
    "r_multiple_distribution": {
        "negative": 33,                     # % of trades < 0R
        "0_to_1R": 22,                      # Break-even to 1R
        "1_to_2R": 25,                      # 1-2R winners
        "2_to_3R": 12,                      # 2-3R winners
        "3R_plus": 8                        # Home runs
    }
}
```

**Auto-adjustment:** Feed optimal stops/targets into `generate_trading_signal()`:
- Replace hardcoded stop % with `optimal_stop_by_regime[current_regime]`
- Replace hardcoded target % with data-driven levels from MFE analysis
- Adjust per-signal-type: "STRONG_BUY optimal target = 9.2%, BUY optimal target = 5.8%"

---

## Data Flow: Closed Loop

```
┌─────────────────────────────────────────────────────────┐
│                   SIGNAL GENERATION                      │
│                                                          │
│  generate_trading_signal()                               │
│    ├── Reads: calibration multipliers (Loop 1)           │
│    ├── Reads: gate weights (Loop 3)                      │
│    ├── Reads: regime adjustments (Loop 4)                │
│    ├── Reads: optimal stops/targets (Loop 5)             │
│    └── Outputs: calibrated signal with adjusted params   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   DATA CAPTURE                           │
│                                                          │
│  store_trading_prediction()                              │
│    ├── Stores: full signal + gate details                │
│    ├── Stores: macro_regime + VIX (Loop 4)               │
│    └── Stores: vault_file path                           │
│                                                          │
│  analyst_server.py pipeline                              │
│    ├── Generates: full markdown report                   │
│    ├── Saves: vault report + JSON metadata               │
│    └── Saves: checkpoint MCP data                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   OUTCOME RESOLUTION                     │
│                                                          │
│  update_prediction_outcomes() [daily cron]               │
│    ├── Fetches: current price via yfinance               │
│    ├── Computes: return_5d/10d/20d/60d                   │
│    ├── Computes: MFE/MAE at each horizon (Loop 5)        │
│    ├── Sets: hit_target, hit_stop, days_to_target        │
│    └── Sets: outcome (WIN/LOSS/OPEN)                     │
│                                                          │
│  ingest_vault_reports() [daily cron] (Loop 2)            │
│    ├── Parses: JSON metadata + markdown reports           │
│    ├── Creates: new predictions from vault               │
│    └── Backfills: missing data in existing predictions   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   ANALYSIS & ADJUSTMENT                  │
│                                                          │
│  calibrate_confidence() [weekly cron] (Loop 1)           │
│    ├── Computes: Brier score + calibration curve         │
│    ├── Generates: confidence multipliers per bucket      │
│    └── Stores: multipliers in component_accuracy table   │
│                                                          │
│  analyze_gate_effectiveness() [weekly cron] (Loop 3)     │
│    ├── Computes: per-gate lift scores                    │
│    ├── Computes: gate interaction matrix                 │
│    ├── Ranks: sub-component predictive power             │
│    └── Stores: recommended weights in DB                 │
│                                                          │
│  optimize_stops_targets() [monthly] (Loop 5)             │
│    ├── Analyzes: MFE/MAE distributions                   │
│    ├── Computes: optimal stop/target by regime           │
│    └── Stores: optimal levels in DB                      │
│                                                          │
│  detect_model_decay() [weekly cron] (existing)           │
│    ├── Compares: rolling 30d/60d/90d accuracy            │
│    ├── Alerts: if declining > 5% between windows         │
│    └── Identifies: which gates are decaying              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
               ┌───────┴───────┐
               │  FEEDS BACK   │
               │  INTO SIGNAL  │
               │  GENERATION   │
               │    (TOP)      │
               └───────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal:** Add missing data capture and backfill historical data.

| Task | File | Description |
|------|------|-------------|
| 1.1 | `schema.sql` | Add `macro_regime`, `vix_at_entry`, `yield_curve_at_entry`, `market_breadth_at_entry` columns |
| 1.2 | `prediction_tracker.py` | Store regime data in `store_trading_prediction()` flow |
| 1.3 | `tools/tracking.py` | `update_prediction_outcomes()` → populate MFE/MAE columns using daily OHLC |
| 1.4 | `tools/tracking.py` | New tool: `ingest_vault_reports()` — parse JSON metadata + markdown |
| 1.5 | Run backfill | Process all 257+ historical vault reports into predictions DB |
| 1.6 | Run backfill | Compute MFE/MAE for all existing resolved predictions |

**Dependencies:** None
**Risk:** JSON metadata may have inconsistent fields across report versions
**Mitigation:** Defensive parsing with fallbacks for missing fields

### Phase 2: Measurement (Week 3-4)

**Goal:** Build the analysis tools that compute calibration, gate effectiveness, and stop optimization.

| Task | File | Description |
|------|------|-------------|
| 2.1 | `tools/tracking.py` | New tool: `calibrate_confidence(days=90)` |
| 2.2 | `tools/tracking.py` | New tool: `analyze_gate_effectiveness(days=90)` |
| 2.3 | `tools/tracking.py` | New tool: `optimize_stops_targets(days=90)` |
| 2.4 | `server_modular.py` | Register new tools (if in new module) |
| 2.5 | Manual validation | Run each tool, verify outputs match manual calculations |

**Dependencies:** Phase 1 (need populated data)
**Minimum data requirement:** 50+ resolved predictions for meaningful statistics

### Phase 3: Auto-Adjustment (Week 5-6)

**Goal:** Close the loop — signal generation reads empirical adjustments.

| Task | File | Description |
|------|------|-------------|
| 3.1 | `tools/signals.py` | `generate_trading_signal()` reads calibration multipliers from DB |
| 3.2 | `tools/signals.py` | `generate_trading_signal()` applies regime penalty/bonus |
| 3.3 | `tools/signals.py` | `generate_trading_signal()` uses empirical gate weights |
| 3.4 | `tools/signals.py` | `generate_trading_signal()` uses MFE/MAE-derived stops/targets |
| 3.5 | `tools/signals.py` | Add `calibration_applied` section to signal output |
| 3.6 | Report templates | Add "Calibration Applied" section showing raw → adjusted confidence |

**Dependencies:** Phase 2 (need analysis tools producing adjustments)
**Safety:** All adjustments bounded — multipliers capped at [0.5, 1.5], weights normalized to sum to 1.0

### Phase 4: Automation (Week 7-8)

**Goal:** Set up cron jobs for continuous operation.

| Task | File | Description |
|------|------|-------------|
| 4.1 | `scripts/cron_daily_outcomes.py` | Daily: resolve outcomes + compute MFE/MAE |
| 4.2 | `scripts/cron_daily_ingest.py` | Daily: ingest new vault reports |
| 4.3 | `scripts/cron_weekly_calibration.py` | Weekly: recalibrate confidence + gate weights |
| 4.4 | `scripts/cron_monthly_optimization.py` | Monthly: optimize stops/targets |
| 4.5 | `scripts/cron_weekly_report.py` | Update existing weekly report to include calibration data |
| 4.6 | Report templates | Add "System Health" dashboard section to portfolio reports |

**Dependencies:** Phase 3

### Phase 5: Dashboard & Reporting (Week 9-10)

**Goal:** Make the feedback loop visible in reports.

| Task | File | Description |
|------|------|-------------|
| 5.1 | Report templates | Add calibration curve visualization (text-based) |
| 5.2 | Report templates | Add gate effectiveness summary to scanner reports |
| 5.3 | Report templates | Add "Regime-Adjusted" label when confidence is adjusted |
| 5.4 | Report templates | Add MFE/MAE analysis to trade plan sections |
| 5.5 | `PORTFOLIO_REPORT_GENERATOR.md` | Add "System Health" section with Brier score trend |

**Dependencies:** Phase 4

---

## New MCP Tools Summary

| # | Tool | Module | Phase | Frequency |
|---|------|--------|-------|-----------|
| 1 | `ingest_vault_reports(days, backfill)` | tracking.py | 1 | Daily cron |
| 2 | `calibrate_confidence(days)` | tracking.py | 2 | Weekly cron |
| 3 | `analyze_gate_effectiveness(days)` | tracking.py | 2 | Weekly cron |
| 4 | `optimize_stops_targets(days, direction)` | tracking.py | 2 | Monthly |

**Total tools after implementation:** 93 (89 existing + 4 new)

---

## Database Changes

### New Columns on `predictions` Table

```sql
-- Phase 1: Regime context at prediction time
ALTER TABLE predictions ADD macro_regime VARCHAR(20);
ALTER TABLE predictions ADD vix_at_entry DECIMAL(8,2);
ALTER TABLE predictions ADD yield_curve_at_entry DECIMAL(8,4);
ALTER TABLE predictions ADD market_breadth_at_entry DECIMAL(8,2);

-- Phase 3: Calibration tracking
ALTER TABLE predictions ADD calibrated_probability DECIMAL(5,2);
ALTER TABLE predictions ADD calibration_multiplier DECIMAL(5,4);
ALTER TABLE predictions ADD regime_adjustment DECIMAL(5,4);
ALTER TABLE predictions ADD raw_probability DECIMAL(5,2);
```

### New Table: `calibration_history`

```sql
CREATE TABLE calibration_history (
    id INT IDENTITY(1,1) PRIMARY KEY,
    calibration_date DATE NOT NULL,
    brier_score DECIMAL(6,4),
    brier_calibration DECIMAL(6,4),
    brier_resolution DECIMAL(6,4),
    bucket_50_60_actual DECIMAL(5,2),
    bucket_60_70_actual DECIMAL(5,2),
    bucket_70_80_actual DECIMAL(5,2),
    bucket_80_plus_actual DECIMAL(5,2),
    bucket_50_60_n INT,
    bucket_60_70_n INT,
    bucket_70_80_n INT,
    bucket_80_plus_n INT,
    multiplier_50_60 DECIMAL(5,4),
    multiplier_60_70 DECIMAL(5,4),
    multiplier_70_80 DECIMAL(5,4),
    multiplier_80_plus DECIMAL(5,4),
    total_predictions INT,
    total_resolved INT,
    created_at DATETIME DEFAULT GETDATE()
);
```

### New Table: `gate_weights`

```sql
CREATE TABLE gate_weights (
    id INT IDENTITY(1,1) PRIMARY KEY,
    effective_date DATE NOT NULL,
    gate_name VARCHAR(20) NOT NULL,          -- catalyst/freshness/brooks/quality/options
    lift_score DECIMAL(5,2),                 -- Win rate delta: PASS vs FAIL
    pass_win_rate DECIMAL(5,2),
    fail_win_rate DECIMAL(5,2),
    recommended_weight DECIMAL(5,4),
    sample_size INT,
    created_at DATETIME DEFAULT GETDATE()
);
```

### New Table: `stop_target_optimization`

```sql
CREATE TABLE stop_target_optimization (
    id INT IDENTITY(1,1) PRIMARY KEY,
    optimization_date DATE NOT NULL,
    direction VARCHAR(10),                   -- LONG/SHORT/BOTH
    regime VARCHAR(20),                      -- EXPANSION/LATE_CYCLE/CONTRACTION/RECOVERY/ALL
    optimal_stop_pct DECIMAL(6,3),
    optimal_target_pct DECIMAL(6,3),
    winners_stopped_prematurely_pct DECIMAL(5,2),
    profit_left_on_table_pct DECIMAL(5,2),
    mfe_median DECIMAL(6,3),
    mae_median DECIMAL(6,3),
    sample_size INT,
    created_at DATETIME DEFAULT GETDATE()
);
```

---

## Safety Guardrails

| Risk | Mitigation |
|------|-----------|
| Calibration multiplier too extreme | Cap at [0.5, 1.5] — never more than 2x adjustment |
| Gate weights based on small sample | Require 50+ resolved predictions per gate before adjusting; below threshold use equal weights |
| Regime adjustment too aggressive | Regime penalty/bonus capped at ±25% |
| Stop optimization from outliers | Use median MFE/MAE, not mean; require 30+ samples per regime |
| Overfitting to recent data | Use 90-day rolling window, not all-time; compare 30d vs 90d for stability |
| Feedback loop runaway | Log all adjustments with timestamp; weekly human review of `calibration_history` |
| Backward compatibility | All adjustments additive — `generate_trading_signal()` returns both `raw_probability` and `calibrated_probability` |

---

## Success Metrics

| Metric | Current (Baseline) | Target (6 months) | Measurement |
|--------|-------------------|-------------------|-------------|
| Brier Score | Unknown | < 0.20 | `calibrate_confidence()` |
| Calibration error | Unknown | < 8% avg per bucket | Calibration curve |
| Gate weight utilization | Equal (20% each) | Empirical (data-driven) | `analyze_gate_effectiveness()` |
| MFE/MAE populated | 0% | 100% of resolved | DB query |
| Vault reports ingested | 0/257 | 257/257 | `ingest_vault_reports()` |
| Regime data captured | 0% of predictions | 100% of new predictions | DB query |
| Winners stopped prematurely | Unknown | < 10% | `optimize_stops_targets()` |
| Profit left on table | Unknown | < 20% | MFE analysis |

---

## Cron Schedule

| Job | Frequency | Time | Script |
|-----|-----------|------|--------|
| Outcome resolution | Daily | 8:00 PM ET | `cron_daily_outcomes.py` |
| Vault ingestion | Daily | 8:30 PM ET | `cron_daily_ingest.py` |
| Calibration + Gate analysis | Weekly (Sunday) | 6:00 PM ET | `cron_weekly_calibration.py` |
| Stop/target optimization | Monthly (1st) | 6:00 PM ET | `cron_monthly_optimization.py` |
| Efficiency report (existing) | Weekly (Sunday) | 7:00 PM ET | `cron_weekly_report.py` |
| Model decay detection | Weekly (Sunday) | 7:30 PM ET | `cron_weekly_decay.py` |

---

## Resilience: Startup Catch-Up & Self-Healing

### Problem

Cron jobs fail silently when the system is off. If the Mac sleeps, Docker stops, or the MCP server isn't running during a scheduled job, that run is skipped. Without catch-up, the system falls behind — stale calibration multipliers, unresolved outcomes, missed vault reports.

### Solution: Last-Run Checkpoint Pattern

Each job writes a **completion timestamp** to the DB on success. On startup, the system checks all timestamps and runs anything overdue.

### New Table: `job_checkpoints`

```sql
CREATE TABLE job_checkpoints (
    job_name VARCHAR(50) PRIMARY KEY,        -- unique job identifier
    last_run_at DATETIME2 NOT NULL,          -- when it last completed successfully
    last_status VARCHAR(20) NOT NULL,        -- SUCCESS / FAILED / RUNNING
    last_duration_ms INT,                    -- runtime in milliseconds
    consecutive_failures INT DEFAULT 0,      -- failure streak counter
    last_error NVARCHAR(500),                -- error message if failed
    updated_at DATETIME2 DEFAULT GETDATE()
);
```

**Seeded with:**

| job_name | interval | max_staleness |
|----------|----------|---------------|
| `daily_outcomes` | 1 day | 2 days (weekends OK) |
| `daily_vault_ingest` | 1 day | 2 days |
| `weekly_calibration` | 7 days | 10 days |
| `weekly_gate_effectiveness` | 7 days | 10 days |
| `weekly_efficiency_report` | 7 days | 10 days |
| `weekly_model_decay` | 7 days | 10 days |
| `monthly_stop_optimization` | 30 days | 35 days |

### Startup Catch-Up Logic

```python
# investor_agent/self_improvement.py — called on MCP server startup

def startup_catchup(db):
    """Check all job checkpoints and run anything overdue."""

    jobs = {
        "daily_outcomes": {
            "max_stale_days": 2,
            "run": lambda: update_prediction_outcomes(),
        },
        "daily_vault_ingest": {
            "max_stale_days": 2,
            "run": lambda: ingest_vault_reports(days=7),  # catch up last week
        },
        "weekly_calibration": {
            "max_stale_days": 10,
            "run": lambda: calibrate_confidence(days=90),
        },
        "weekly_gate_effectiveness": {
            "max_stale_days": 10,
            "run": lambda: analyze_gate_effectiveness(days=90),
        },
        "weekly_model_decay": {
            "max_stale_days": 10,
            "run": lambda: detect_model_decay(days=60),
        },
        "monthly_stop_optimization": {
            "max_stale_days": 35,
            "run": lambda: optimize_stops_targets(days=90),
        },
    }

    now = datetime.utcnow()
    ran = []

    for job_name, config in jobs.items():
        checkpoint = db.query(
            "SELECT last_run_at, last_status FROM job_checkpoints WHERE job_name = ?",
            job_name
        )

        if not checkpoint:
            # Never ran — run now
            stale = True
        else:
            age_days = (now - checkpoint.last_run_at).days
            stale = age_days > config["max_stale_days"]

        if stale:
            try:
                start = time.time()
                config["run"]()
                duration_ms = int((time.time() - start) * 1000)

                db.upsert("job_checkpoints", {
                    "job_name": job_name,
                    "last_run_at": now,
                    "last_status": "SUCCESS",
                    "last_duration_ms": duration_ms,
                    "consecutive_failures": 0,
                    "last_error": None,
                })
                ran.append(job_name)

            except Exception as e:
                failures = (checkpoint.consecutive_failures or 0) + 1 if checkpoint else 1
                db.upsert("job_checkpoints", {
                    "job_name": job_name,
                    "last_run_at": now,
                    "last_status": "FAILED",
                    "consecutive_failures": failures,
                    "last_error": str(e)[:500],
                })

    return ran  # List of jobs that were caught up
```

### Cron Job Wrapper

Every cron script uses the same pattern — write checkpoint on success, increment failure counter on error:

```python
# scripts/cron_daily_outcomes.py

def main():
    db = get_database()
    job_name = "daily_outcomes"

    # Mark as RUNNING
    db.upsert("job_checkpoints", {
        "job_name": job_name, "last_status": "RUNNING"
    })

    try:
        start = time.time()
        result = update_prediction_outcomes()
        duration_ms = int((time.time() - start) * 1000)

        db.upsert("job_checkpoints", {
            "job_name": job_name,
            "last_run_at": datetime.utcnow(),
            "last_status": "SUCCESS",
            "last_duration_ms": duration_ms,
            "consecutive_failures": 0,
            "last_error": None,
        })
        print(f"✅ {job_name}: {result['updated']} predictions updated in {duration_ms}ms")

    except Exception as e:
        checkpoint = db.query("SELECT consecutive_failures FROM job_checkpoints WHERE job_name=?", job_name)
        failures = (checkpoint.consecutive_failures or 0) + 1 if checkpoint else 1

        db.upsert("job_checkpoints", {
            "job_name": job_name,
            "last_run_at": datetime.utcnow(),
            "last_status": "FAILED",
            "consecutive_failures": failures,
            "last_error": str(e)[:500],
        })
        print(f"❌ {job_name}: {e} (failure #{failures})")

        # Alert after 3 consecutive failures
        if failures >= 3:
            print(f"🚨 {job_name}: {failures} consecutive failures — check DB/system health")
```

### Health Check in Reports

Portfolio and scanner reports display system health from `job_checkpoints`:

```markdown
### System Health

| Job | Last Run | Status | Staleness |
|-----|----------|--------|-----------|
| Outcomes | 2026-03-15 8:00 PM | ✅ SUCCESS | Fresh |
| Vault Ingest | 2026-03-15 8:30 PM | ✅ SUCCESS | Fresh |
| Calibration | 2026-03-09 6:00 PM | ✅ SUCCESS | Fresh |
| Gate Weights | 2026-03-09 6:15 PM | ✅ SUCCESS | Fresh |
| Decay Detection | 2026-03-09 7:30 PM | ✅ SUCCESS | Fresh |
| Stop Optimization | 2026-03-01 6:00 PM | ✅ SUCCESS | Fresh |

Brier Score: 0.19 (trend: IMPROVING)
Calibration: Active (multipliers applied)
```

**Warning states:**

```markdown
| Outcomes | 2026-03-12 8:00 PM | ❌ FAILED (x3) | ⚠️ 3 DAYS STALE |
```

When `consecutive_failures >= 3` OR staleness exceeds `max_stale_days`, the report flags it with a warning so you know the feedback loop is degraded.

### Integration Points

| Component | How It Uses Checkpoints |
|-----------|------------------------|
| MCP server startup (`server_modular.py`) | Calls `startup_catchup()` — runs overdue jobs in background thread |
| Each cron script | Writes checkpoint on success/failure |
| `generate_trading_signal()` | Checks calibration staleness — if >14 days, uses default multipliers with warning |
| Portfolio report template | Displays System Health table from `job_checkpoints` |
| `detect_model_decay()` | Reads checkpoint failures — consecutive DB failures = system health issue, not model decay |

### Failure Escalation

| Failures | Action |
|----------|--------|
| 1 | Log warning, retry next scheduled run |
| 2 | Log warning, retry next scheduled run |
| 3+ | Flag in reports: "⚠️ {job} failed {n} times — check system" |
| 5+ | `generate_trading_signal()` adds disclaimer: "Calibration data stale — using defaults" |
| 7+ | Stop using stale calibration entirely — revert to raw probabilities until fixed |

---

## File Changes Summary

| File | Phase | Type | Description |
|------|-------|------|-------------|
| `investor_agent/schema.sql` | 1 | MODIFY | Add columns + 3 new tables |
| `investor_agent/prediction_tracker.py` | 1 | MODIFY | Store regime data, populate MFE/MAE |
| `investor_agent/tools/tracking.py` | 1-2 | MODIFY | 4 new tools, enhance `update_prediction_outcomes()` |
| `investor_agent/server_modular.py` | 2 | MODIFY | Register new tools (if separate module) |
| `investor_agent/tools/signals.py` | 3 | MODIFY | Read calibration/weights/regime adjustments |
| `investor_agent/self_improvement.py` | 4 | NEW | Startup catch-up logic, job checkpoint management |
| `scripts/cron_daily_outcomes.py` | 4 | NEW | Daily outcome resolution |
| `scripts/cron_daily_ingest.py` | 4 | NEW | Daily vault ingestion |
| `scripts/cron_weekly_calibration.py` | 4 | NEW | Weekly calibration + gate analysis |
| `scripts/cron_monthly_optimization.py` | 4 | NEW | Monthly stop/target optimization |
| `reportsGenerator/*.md` | 5 | MODIFY | Add calibration sections to templates |
| `reportsGenerator/instructions.md` | 2 | MODIFY | Document 4 new tools |

---

## References

- **Brier Score:** Brier, G.W. (1950). "Verification of forecasts expressed in terms of probability"
- **Calibration:** scikit-learn `brier_score_loss()`, `calibration_curve()`
- **Alpha Decay:** microalphas.com — signal decay patterns, 5-10% annual degradation
- **Kelly Criterion:** Start at quarter-Kelly, graduate to half-Kelly after 200+ calibrated predictions
- **MFE/MAE:** John Sweeney's "Maximum Adverse Excursion" (1997)
- **Polymarket AI Bot:** Multi-model ensemble with calibration accuracy charts (open source reference)
- **FreqTrade FreqAI:** Adaptive self-training ML trading strategies (open source)
