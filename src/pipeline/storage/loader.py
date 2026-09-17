"""Idempotent loader: validated CSV → economic_indicators table.

Uses INSERT ... ON CONFLICT DO UPDATE on the natural key
(indicator_name, date, source), so re-running the loader produces the
same database state as running it once.

Input:  a pandas DataFrame in canonical shape
Output: a LoadResult with inserted / updated / unchanged counts
"""

import logging
from dataclasses import dataclass
import sqlite3

import pandas as pd

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO economic_indicators
    (indicator_name, date, value, unit, source, updated_at)
VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(indicator_name, date, source) DO UPDATE SET
    value      = excluded.value,
    unit       = excluded.unit,
    updated_at = CURRENT_TIMESTAMP
"""


@dataclass
class LoadResult:
    """Counts of what the loader did to the database."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.unchanged


def load_observations(
    conn: sqlite3.Connection, df: pd.DataFrame
) -> LoadResult:
    """Upsert every row in df. Returns counts of inserted/updated/unchanged."""
    result = LoadResult()
    if df.empty:
        logger.info("Loader received empty DataFrame — nothing to do")
        return result

    # Pre-read existing values so we can distinguish 'updated' from
    # 'unchanged'. ON CONFLICT alone can't tell us which rows changed.
    existing = {
        (r["indicator_name"], r["date"], r["source"]): r["value"]
        for r in conn.execute(
            "SELECT indicator_name, date, source, value FROM economic_indicators"
        )
    }

    rows = [
        (
            r["indicator_name"],
            r["date"],
            float(r["value"]),
            r["unit"],
            r["source"],
        )
        for r in df.to_dict(orient="records")
    ]

    for key_row in rows:
        key = (key_row[0], key_row[1], key_row[4])
        new_value = key_row[2]
        if key not in existing:
            result.inserted += 1
        elif existing[key] != new_value:
            result.updated += 1
        else:
            result.unchanged += 1

    conn.executemany(UPSERT_SQL, rows)
    conn.commit()

    logger.info(
        "Load complete: inserted=%d updated=%d unchanged=%d (total=%d)",
        result.inserted, result.updated, result.unchanged, result.total,
    )
    return result