"""Create the trading_reports table in MSSQL."""
from investor_agent.database import get_db_session
from sqlalchemy import text

with get_db_session() as s:
    r = s.execute(text("SELECT 1"))
    print(f"Connection OK: {r.fetchone()[0]}")

    s.execute(text("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'trading_reports')
        CREATE TABLE trading_reports (
            id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
            ticker VARCHAR(10),
            request_type VARCHAR(30) NOT NULL,
            report_type VARCHAR(20) NOT NULL,
            created_at DATETIME2 DEFAULT GETDATE(),
            report_date DATE NOT NULL,
            quality_score INT,
            quality_grade VARCHAR(2),
            signal VARCHAR(20),
            confidence VARCHAR(10),
            entry_price DECIMAL(18,4),
            stop_loss DECIMAL(18,4),
            target_1 DECIMAL(18,4),
            target_2 DECIMAL(18,4),
            gates_passed INT,
            data_source VARCHAR(20),
            report_markdown NVARCHAR(MAX) NOT NULL,
            structured_json NVARCHAR(MAX),
            mcp_data_summary NVARCHAR(MAX),
            vault_file VARCHAR(500),
            prediction_id UNIQUEIDENTIFIER,
            job_id VARCHAR(50),
            pipeline_duration_sec INT,
            draft_length INT,
            final_length INT
        )
    """))
    s.commit()
    print("Table created/verified")

    for idx_name, col in [
        ("IX_trading_reports_ticker", "ticker"),
        ("IX_trading_reports_date", "report_date"),
        ("IX_trading_reports_request_type", "request_type"),
        ("IX_trading_reports_signal", "signal"),
        ("IX_trading_reports_quality", "quality_score"),
    ]:
        try:
            s.execute(text(f"CREATE INDEX {idx_name} ON trading_reports({col})"))
            s.commit()
            print(f"  Index {idx_name} created")
        except Exception as e:
            if "already exists" in str(e):
                print(f"  Index {idx_name} exists")
            else:
                print(f"  Index {idx_name} skipped: {e}")

    r = s.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='trading_reports'"
    ))
    print(f"Columns: {r.fetchone()[0]}")
