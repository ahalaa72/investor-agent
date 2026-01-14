"""
Database connection utilities for MSSQL.
Uses SQLAlchemy with pyodbc for MSSQL connectivity.
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)


def get_connection_string() -> str:
    """
    Get MSSQL connection string from environment variable.
    Falls back to default local connection if not set.
    """
    conn_str = os.getenv("MSSQL_CONNECTION_STRING")
    if conn_str:
        return conn_str

    # Default connection for local Docker MSSQL
    # Format: mssql+pyodbc://user:password@host:port/database?driver=ODBC+Driver+18+for+SQL+Server
    return (
        "mssql+pyodbc://sa:Ahmed!0a@localhost:1433/investor_agent"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )


def create_db_engine(connection_string: str | None = None) -> Engine:
    """
    Create SQLAlchemy engine for MSSQL.

    Args:
        connection_string: Optional connection string. Uses env var if not provided.

    Returns:
        SQLAlchemy Engine instance
    """
    conn_str = connection_string or get_connection_string()

    engine = create_engine(
        conn_str,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # Recycle connections after 30 minutes
        echo=False  # Set to True for SQL debugging
    )

    return engine


# Global engine instance (lazy initialized)
_engine: Engine | None = None


def get_engine() -> Engine:
    """
    Get or create the global database engine.
    Thread-safe singleton pattern.
    """
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    """
    Get SQLAlchemy session factory.
    """
    return sessionmaker(bind=get_engine())


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Automatically handles commit/rollback.

    Usage:
        with get_db_session() as session:
            session.execute(text("SELECT ..."))
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def execute_query(query: str, params: dict | None = None) -> list[dict[str, Any]]:
    """
    Execute a raw SQL query and return results as list of dicts.

    Args:
        query: SQL query string
        params: Optional dictionary of query parameters

    Returns:
        List of dictionaries, one per row
    """
    with get_db_session() as session:
        result = session.execute(text(query), params or {})

        # For SELECT queries, return results
        if result.returns_rows:
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

        return []


def execute_insert(query: str, params: dict | None = None) -> str | None:
    """
    Execute an INSERT query and return the inserted ID (if UUID).

    Args:
        query: SQL INSERT query string
        params: Dictionary of query parameters

    Returns:
        Inserted ID as string, or None
    """
    with get_db_session() as session:
        result = session.execute(text(query), params or {})
        session.commit()

        # For INSERT...OUTPUT, get the returned ID
        if result.returns_rows:
            row = result.fetchone()
            if row:
                return str(row[0])

        return None


def test_connection() -> bool:
    """
    Test database connectivity.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with get_db_session() as session:
            result = session.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            return row is not None and row[0] == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def get_table_count(table_name: str) -> int:
    """
    Get row count for a table.

    Args:
        table_name: Name of the table

    Returns:
        Number of rows in the table
    """
    query = f"SELECT COUNT(*) as cnt FROM {table_name}"  # noqa: S608
    result = execute_query(query)
    return result[0]["cnt"] if result else 0


def check_schema_exists() -> dict[str, bool]:
    """
    Check if all required tables exist.

    Returns:
        Dictionary mapping table name to existence status
    """
    tables = ["predictions", "component_accuracy", "efficiency_reports"]
    result = {}

    for table in tables:
        query = """
            SELECT COUNT(*) as exists_flag
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = :table_name
        """
        rows = execute_query(query, {"table_name": table})
        result[table] = rows[0]["exists_flag"] > 0 if rows else False

    return result


# Initialize engine on module load (lazy)
def init_db():
    """
    Initialize database connection.
    Call this at application startup.
    """
    try:
        engine = get_engine()
        logger.info(f"Database engine initialized: {engine.url}")

        # Test connection
        if test_connection():
            logger.info("Database connection test passed")

            # Check schema
            schema_status = check_schema_exists()
            logger.info(f"Schema status: {schema_status}")

            return True
        else:
            logger.error("Database connection test failed")
            return False

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False
