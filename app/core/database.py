"""SQL Server connection for word_dictionary_links audit table."""

import logging
from contextlib import contextmanager

import pyodbc

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_connection() -> pyodbc.Connection:
    """Create a SQL Server connection with UTF-16LE encoding."""
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
    )

    conn = pyodbc.connect(conn_str, timeout=30)
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16-le")
    conn.setencoding(encoding="utf-16-le")
    return conn


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
