"""Tests for the idempotent SQLite loader."""

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src.pipeline.storage.db import connect, init_schema
from src.pipeline.storage.loader import load_observations


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    init_schema(c)
    yield c
    c.close()


def _df(rows):
    return pd.DataFrame(rows, columns=[
        "indicator_name", "date", "value", "unit", "source",
    ])


def test_init_schema_is_idempotent(tmp_path):
    c = connect(tmp_path / "t.db")
    init_schema(c)
    init_schema(c)  # must not raise
    tables = {r["name"] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "economic_indicators" in tables
    c.close()


def test_load_inserts_new_rows(conn):
    df = _df([
        ["CPI", "2023-01-01", 158.3, "index_2010_100", "world_bank"],
        ["USD_ZAR", "2024-01-02", 18.5, "ZAR_per_USD", "frankfurter"],
    ])
    result = load_observations(conn, df)
    assert result.inserted == 2
    assert result.updated == 0
    assert result.unchanged == 0


def test_load_is_idempotent(conn):
    """The property the whole stage exists to guarantee."""
    df = _df([
        ["CPI", "2023-01-01", 158.3, "index_2010_100", "world_bank"],
    ])
    load_observations(conn, df)
    count_after_first = conn.execute(
        "SELECT COUNT(*) AS c FROM economic_indicators"
    ).fetchone()["c"]

    result = load_observations(conn, df)
    count_after_second = conn.execute(
        "SELECT COUNT(*) AS c FROM economic_indicators"
    ).fetchone()["c"]

    assert count_after_first == count_after_second == 1
    assert result.inserted == 0
    assert result.unchanged == 1


def test_load_updates_changed_value(conn):
    df1 = _df([["CPI", "2023-01-01", 158.3, "index_2010_100", "world_bank"]])
    df2 = _df([["CPI", "2023-01-01", 159.0, "index_2010_100", "world_bank"]])
    load_observations(conn, df1)
    result = load_observations(conn, df2)
    assert result.updated == 1
    value = conn.execute(
        "SELECT value FROM economic_indicators WHERE indicator_name='CPI'"
    ).fetchone()["value"]
    assert value == 159.0


def test_load_empty_dataframe_is_noop(conn):
    result = load_observations(conn, _df([]))
    assert result.total == 0
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM economic_indicators"
    ).fetchone()["c"]
    assert count == 0


def test_unique_key_rejects_duplicate_insert(conn):
    conn.execute(
        "INSERT INTO economic_indicators "
        "(indicator_name, date, value, unit, source) "
        "VALUES ('CPI', '2023-01-01', 1.0, 'x', 'world_bank')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO economic_indicators "
            "(indicator_name, date, value, unit, source) "
            "VALUES ('CPI', '2023-01-01', 2.0, 'x', 'world_bank')"
        )