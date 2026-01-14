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

PRINT 'Schema creation completed successfully!';
GO
