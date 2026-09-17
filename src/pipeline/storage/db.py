"""SQLite connection management and schema initialization.

Thin wrapper around sqlite3 so the rest of the storage layer never
touches connection details. Swapping to Postgres later means changing
this file and the SQL dialect in loader.py, nothing else.

Input:  path to the SQLite file
Output: sqlite3.Connection with foreign_keys on and row_factory set
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection, creating parent directories if needed."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    logger.info("Opened SQLite connection: %s", db_path)
    return conn

def init_schema(conn: sqlite3.Connection) -> None:
    """Execute schema.sql. Safe to call repeatedly (IF NOT EXISTS)."""
    sql = SCHEMA_PATH.read_text()
    conn.executescript(sql)
    conn.commit()
    logger.info("Schema initialized from %s", SCHEMA_PATH.name)
