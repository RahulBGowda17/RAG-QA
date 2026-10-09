import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.config import Config

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_db_connection() -> sqlite3.Connection:
    """Return a new SQLite database connection configured with Row factory and WAL mode."""
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for safely executing transactions with automatic commit/rollback."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def init_db() -> None:
    """Initialize database tables, foreign keys, and indexes from schema.sql."""
    Config.ensure_directories()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_db_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
