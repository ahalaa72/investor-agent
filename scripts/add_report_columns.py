"""Add report columns to predictions table."""
from investor_agent.database import get_db_session
from sqlalchemy import text

with get_db_session() as s:
    r = s.execute(text("SELECT 1"))
    print(f"Connection OK: {r.fetchone()[0]}")

    for col_name, col_type in [
        ("report_markdown", "NVARCHAR(MAX)"),
        ("report_quality_score", "INT"),
        ("report_quality_grade", "VARCHAR(2)"),
        ("vault_file", "VARCHAR(500)"),
    ]:
        try:
            s.execute(text(f"""
                IF NOT EXISTS (
                    SELECT * FROM sys.columns
                    WHERE object_id = OBJECT_ID('predictions') AND name = '{col_name}'
                )
                ALTER TABLE predictions ADD {col_name} {col_type}
            """))
            s.commit()
            print(f"  Column {col_name} added/verified")
        except Exception as e:
            print(f"  Column {col_name} error: {e}")

    # Verify
    r = s.execute(text(
        "SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('predictions') "
        "AND name IN ('report_markdown', 'report_quality_score', 'report_quality_grade', 'vault_file')"
    ))
    cols = [row[0] for row in r.fetchall()]
    print(f"Report columns present: {cols}")
