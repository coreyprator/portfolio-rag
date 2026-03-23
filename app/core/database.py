"""SQL Server connection for word_dictionary_links audit table.

Uses google-cloud-sql-connector + pytds on Cloud Run (auto-detects via
/cloudsql in DB_SERVER). Falls back to pyodbc for local development.
"""

import logging
import os
from contextlib import contextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)

_connector = None  # Lazy-initialized Cloud SQL connector


def _is_cloud_run() -> bool:
    """Detect Cloud Run environment."""
    return "/cloudsql" in settings.DB_SERVER or os.getenv("K_SERVICE") is not None


def _get_cloud_sql_connection():
    """Connect via google-cloud-sql-connector + pytds (Cloud Run)."""
    global _connector
    if _connector is None:
        from google.cloud.sql.connector import Connector
        _connector = Connector()

    instance_connection_name = settings.DB_SERVER.replace("/cloudsql/", "")

    conn = _connector.connect(
        instance_connection_name,
        "pytds",
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        db=settings.DB_NAME,
    )
    return conn


def _get_pyodbc_connection():
    """Connect via pyodbc (local development)."""
    import pyodbc

    server = settings.DB_SERVER
    if "," not in server and ":" not in server and "/" not in server:
        server = f"{server},1433"

    conn_str = (
        f"DRIVER={{{settings.DB_DRIVER}}};"
        f"SERVER={server};"
        f"DATABASE={settings.DB_NAME};"
        f"UID={settings.DB_USER};"
        f"PWD={settings.DB_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Encrypt=Optional;"
    )

    conn = pyodbc.connect(conn_str, timeout=30)
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16-le")
    conn.setencoding(encoding="utf-16-le")
    return conn


def get_connection():
    """Create a SQL Server connection. Auto-selects driver based on environment."""
    if _is_cloud_run():
        logger.info("Using Cloud SQL Connector (pytds)")
        return _get_cloud_sql_connection()
    else:
        logger.info("Using pyodbc (local)")
        return _get_pyodbc_connection()


@contextmanager
def get_db():
    """Context manager for SQL queries with auto-commit/rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_connection() -> bool:
    """Test SQL Server connectivity."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception as e:
        logger.error(f"SQL Server connection failed: {e}")
        return False
