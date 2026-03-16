-- Investor Agent Prediction Tracking Schema
-- Database: investor_agent

USE investor_agent;
GO

-- Table 1: predictions - Store all trading predictions
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'predictions')
CREATE TABLE predictions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

    -- Identification
    ticker VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    report_type VARCHAR(20) NOT NULL,

    -- Timestamps
    created_at DATETIME2 DEFAULT GETDATE(),
    prediction_date DATE NOT NULL,

    -- Entry Details
    entry_price DECIMAL(18,4) NOT NULL,
    stop_price DECIMAL(18,4),
    target_1_price DECIMAL(18,4),
    target_2_price DECIMAL(18,4),

    -- Signal Quality
    signal VARCHAR(20),
    confidence_score DECIMAL(5,2),
    composite_score DECIMAL(5,2),

    -- 4-GATE RESULTS
    gate_catalyst VARCHAR(10),
    gate_freshness VARCHAR(10),
    gate_brooks VARCHAR(10),
    gate_quality VARCHAR(10),
    gates_passed INT,

    -- GATE 1: CATALYST DETAILS
    catalyst_direction VARCHAR(10),
    catalyst_strength VARCHAR(10),
    catalyst_score DECIMAL(5,2),
    bullish_score DECIMAL(5,2),
    bearish_score DECIMAL(5,2),
    trade_allowed BIT,

    -- GATE 2: FRESHNESS + DALIO DETAILS
    cvd_trend VARCHAR(10),
    exhaustion_score DECIMAL(5,2),
    fresh_direction VARCHAR(10),
    dalio_ratio DECIMAL(8,4),
    dalio_interpretation VARCHAR(20),
    cumulative_dollar_flow DECIMAL(18,2),
    sustainability_score DECIMAL(5,2),
    freshness_checks_passed INT,

    -- GATE 3: AL BROOKS DETAILS
    always_in VARCHAR(10),
    trap_risk VARCHAR(10),
    brooks_probability DECIMAL(5,2),
    brooks_pattern VARCHAR(50),

    -- GATE 4: QUALITY DETAILS
    quality_score DECIMAL(5,2),
    quality_grade VARCHAR(2),
    f_score INT,
    z_score DECIMAL(5,2),

    -- OPTIONS ANALYSIS (McMillan)
    iv_rank DECIMAL(5,2),
    iv_percentile DECIMAL(5,2),
    recommended_strategy VARCHAR(50),
    put_call_ratio DECIMAL(5,2),

    -- DIRECTION VOTING
    vote_catalyst VARCHAR(10),
    vote_cvd VARCHAR(10),
    vote_exhaustion VARCHAR(10),
    vote_brooks VARCHAR(10),
    data_direction VARCHAR(15),
    direction_conflict BIT,

    -- HISTORICAL VALIDATION
    similar_setups_count INT,
    historical_success_rate DECIMAL(5,2),
    historical_confidence VARCHAR(10),

    -- OUTCOME TRACKING
    outcome VARCHAR(10),
    validated BIT DEFAULT 0,
    validated_at DATETIME2,

    -- Price at horizons
    price_5d DECIMAL(18,4),
    price_10d DECIMAL(18,4),
    price_20d DECIMAL(18,4),
    price_60d DECIMAL(18,4),

    -- Returns at horizons
    return_5d DECIMAL(8,4),
    return_10d DECIMAL(8,4),
    return_20d DECIMAL(8,4),
    return_60d DECIMAL(8,4),

    -- MFE/MAE
    mfe_5d DECIMAL(8,4),
    mae_5d DECIMAL(8,4),
    mfe_10d DECIMAL(8,4),
    mae_10d DECIMAL(8,4),
    mfe_20d DECIMAL(8,4),
    mae_20d DECIMAL(8,4),

    -- Target/Stop Hit Tracking
    hit_target_1 BIT,
    hit_target_2 BIT,
    hit_stop BIT,
    days_to_target INT,
    days_to_stop INT,

    -- Raw JSON
    full_analysis_json NVARCHAR(MAX)
);
GO

-- Create indexes for predictions table
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_predictions_ticker')
    CREATE INDEX IX_predictions_ticker ON predictions(ticker);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_predictions_date')
    CREATE INDEX IX_predictions_date ON predictions(prediction_date);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_predictions_outcome')
    CREATE INDEX IX_predictions_outcome ON predictions(outcome);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_predictions_signal')
    CREATE INDEX IX_predictions_signal ON predictions(signal);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_predictions_report_type')
    CREATE INDEX IX_predictions_report_type ON predictions(report_type);
GO

-- Table 2: component_accuracy - Track accuracy of each component
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'component_accuracy')
CREATE TABLE component_accuracy (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    report_date DATE NOT NULL,
    component_name VARCHAR(50) NOT NULL,
    sub_component VARCHAR(50),

    -- Accuracy Metrics
    total_predictions INT,
    correct_predictions INT,
    accuracy_rate DECIMAL(5,2),

    -- By Direction
    long_accuracy DECIMAL(5,2),
    short_accuracy DECIMAL(5,2),

    -- By Market Regime
    risk_on_accuracy DECIMAL(5,2),
    risk_off_accuracy DECIMAL(5,2),

    -- Statistical Significance
    sample_size INT,
    confidence_interval_low DECIMAL(5,2),
    confidence_interval_high DECIMAL(5,2),
    is_significant BIT,

    created_at DATETIME2 DEFAULT GETDATE()
);
GO

-- Create indexes for component_accuracy table
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_component_accuracy_date')
    CREATE INDEX IX_component_accuracy_date ON component_accuracy(report_date);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_component_accuracy_component')
    CREATE INDEX IX_component_accuracy_component ON component_accuracy(component_name);
GO

-- Table 3: efficiency_reports - Store weekly efficiency reports
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'efficiency_reports')
CREATE TABLE efficiency_reports (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    report_date DATE NOT NULL,
    report_period_start DATE,
    report_period_end DATE,

    -- Overall Metrics
    total_predictions INT,
    validated_predictions INT,
    overall_win_rate DECIMAL(5,2),
    overall_avg_return DECIMAL(8,4),

    -- By Report Type
    comprehensive_win_rate DECIMAL(5,2),
    concise_win_rate DECIMAL(5,2),
    scanner_win_rate DECIMAL(5,2),
    portfolio_win_rate DECIMAL(5,2),

    -- By Signal Type
    strong_buy_win_rate DECIMAL(5,2),
    buy_win_rate DECIMAL(5,2),
    watch_win_rate DECIMAL(5,2),
    sell_win_rate DECIMAL(5,2),

    -- By Gates Passed
    four_gate_win_rate DECIMAL(5,2),
    three_gate_win_rate DECIMAL(5,2),
    two_gate_win_rate DECIMAL(5,2),

    -- Best/Worst Components
    best_component VARCHAR(50),
    best_component_accuracy DECIMAL(5,2),
    worst_component VARCHAR(50),
    worst_component_accuracy DECIMAL(5,2),

    -- JSON Data
    suggestions_json NVARCHAR(MAX),
    full_report_json NVARCHAR(MAX),

    created_at DATETIME2 DEFAULT GETDATE()
);
GO

-- Create indexes for efficiency_reports table
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_efficiency_reports_date')
    CREATE INDEX IX_efficiency_reports_date ON efficiency_reports(report_date);
GO

-- Add report columns to predictions table (analyst pipeline attaches full report after generation)
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'report_markdown')
    ALTER TABLE predictions ADD report_markdown NVARCHAR(MAX);
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'report_quality_score')
    ALTER TABLE predictions ADD report_quality_score INT;
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'report_quality_grade')
    ALTER TABLE predictions ADD report_quality_grade VARCHAR(2);
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'vault_file')
    ALTER TABLE predictions ADD vault_file VARCHAR(500);
GO

-- ═══════════════════════════════════════════════════════════════════════════
-- SELF-IMPROVEMENT SYSTEM: Phase 1 — Regime Context at Prediction Time
-- ═══════════════════════════════════════════════════════════════════════════

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'macro_regime')
    ALTER TABLE predictions ADD macro_regime VARCHAR(20);
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'vix_at_entry')
    ALTER TABLE predictions ADD vix_at_entry DECIMAL(8,2);
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'yield_curve_at_entry')
    ALTER TABLE predictions ADD yield_curve_at_entry DECIMAL(8,4);
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'market_breadth_at_entry')
    ALTER TABLE predictions ADD market_breadth_at_entry DECIMAL(8,2);
GO

-- Phase 3: Calibration tracking on predictions
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'calibrated_probability')
    ALTER TABLE predictions ADD calibrated_probability DECIMAL(5,2);
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'calibration_multiplier')
    ALTER TABLE predictions ADD calibration_multiplier DECIMAL(5,4);
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'regime_adjustment')
    ALTER TABLE predictions ADD regime_adjustment DECIMAL(5,4);
GO
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'raw_probability')
    ALTER TABLE predictions ADD raw_probability DECIMAL(5,2);
GO

-- Gate 5: Options (was missing from original schema)
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('predictions') AND name = 'gate_options')
    ALTER TABLE predictions ADD gate_options VARCHAR(10);
GO

-- ═══════════════════════════════════════════════════════════════════════════
-- Table 4: calibration_history — Weekly Brier score + confidence multipliers
-- ═══════════════════════════════════════════════════════════════════════════

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'calibration_history')
CREATE TABLE calibration_history (
    id INT IDENTITY(1,1) PRIMARY KEY,
    calibration_date DATE NOT NULL,

    -- Brier Score
    brier_score DECIMAL(6,4),
    brier_calibration DECIMAL(6,4),
    brier_resolution DECIMAL(6,4),

    -- Calibration Curve: actual win rates per confidence bucket
    bucket_50_60_actual DECIMAL(5,2),
    bucket_60_70_actual DECIMAL(5,2),
    bucket_70_80_actual DECIMAL(5,2),
    bucket_80_plus_actual DECIMAL(5,2),

    -- Sample sizes per bucket
    bucket_50_60_n INT,
    bucket_60_70_n INT,
    bucket_70_80_n INT,
    bucket_80_plus_n INT,

    -- Confidence adjustment multipliers (capped [0.5, 1.5])
    multiplier_50_60 DECIMAL(5,4),
    multiplier_60_70 DECIMAL(5,4),
    multiplier_70_80 DECIMAL(5,4),
    multiplier_80_plus DECIMAL(5,4),

    -- Summary
    total_predictions INT,
    total_resolved INT,

    created_at DATETIME2 DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_calibration_history_date')
    CREATE INDEX IX_calibration_history_date ON calibration_history(calibration_date);
GO

-- ═══════════════════════════════════════════════════════════════════════════
-- Table 5: gate_weights — Empirical gate lift scores and recommended weights
-- ═══════════════════════════════════════════════════════════════════════════

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'gate_weights')
CREATE TABLE gate_weights (
    id INT IDENTITY(1,1) PRIMARY KEY,
    effective_date DATE NOT NULL,
    gate_name VARCHAR(20) NOT NULL,          -- catalyst/freshness/brooks/quality/options

    -- Lift Analysis
    lift_score DECIMAL(5,2),                 -- Win rate delta: PASS vs FAIL
    pass_win_rate DECIMAL(5,2),
    fail_win_rate DECIMAL(5,2),

    -- Weight
    recommended_weight DECIMAL(5,4),

    -- Sample Size
    sample_size INT,

    created_at DATETIME2 DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_gate_weights_date')
    CREATE INDEX IX_gate_weights_date ON gate_weights(effective_date);
GO

-- ═══════════════════════════════════════════════════════════════════════════
-- Table 6: stop_target_optimization — MFE/MAE-derived optimal levels
-- ═══════════════════════════════════════════════════════════════════════════

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stop_target_optimization')
CREATE TABLE stop_target_optimization (
    id INT IDENTITY(1,1) PRIMARY KEY,
    optimization_date DATE NOT NULL,
    direction VARCHAR(10),                   -- LONG/SHORT/BOTH
    regime VARCHAR(20),                      -- EXPANSION/LATE_CYCLE/CONTRACTION/RECOVERY/ALL

    -- Optimal Levels (data-driven)
    optimal_stop_pct DECIMAL(6,3),
    optimal_target_pct DECIMAL(6,3),

    -- Analysis
    winners_stopped_prematurely_pct DECIMAL(5,2),
    profit_left_on_table_pct DECIMAL(5,2),
    mfe_median DECIMAL(6,3),
    mae_median DECIMAL(6,3),

    -- Sample Size
    sample_size INT,

    created_at DATETIME2 DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_stop_target_optimization_date')
    CREATE INDEX IX_stop_target_optimization_date ON stop_target_optimization(optimization_date);
GO

-- ═══════════════════════════════════════════════════════════════════════════
-- Table 7: job_checkpoints — Cron job last-run tracking for startup catch-up
-- ═══════════════════════════════════════════════════════════════════════════

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'job_checkpoints')
CREATE TABLE job_checkpoints (
    job_name VARCHAR(50) PRIMARY KEY,
    last_run_at DATETIME2 NOT NULL,
    last_status VARCHAR(20) NOT NULL,        -- SUCCESS / FAILED / RUNNING
    last_duration_ms INT,
    consecutive_failures INT DEFAULT 0,
    last_error NVARCHAR(500),
    updated_at DATETIME2 DEFAULT GETDATE()
);
GO

-- Seed initial checkpoint rows (never ran = epoch)
IF NOT EXISTS (SELECT * FROM job_checkpoints WHERE job_name = 'daily_outcomes')
BEGIN
    INSERT INTO job_checkpoints (job_name, last_run_at, last_status) VALUES
        ('daily_outcomes',             '2000-01-01', 'NEVER'),
        ('daily_vault_ingest',         '2000-01-01', 'NEVER'),
        ('weekly_calibration',         '2000-01-01', 'NEVER'),
        ('weekly_gate_effectiveness',  '2000-01-01', 'NEVER'),
        ('weekly_efficiency_report',   '2000-01-01', 'NEVER'),
        ('weekly_model_decay',         '2000-01-01', 'NEVER'),
        ('monthly_stop_optimization',  '2000-01-01', 'NEVER');
END
GO

PRINT 'Schema creation completed successfully (including self-improvement tables)!';
GO
