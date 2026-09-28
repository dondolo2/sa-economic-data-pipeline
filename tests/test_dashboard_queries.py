import sqlite3

import pytest

from dashboard.queries import (
    cpi_vs_fx_by_year,
    date_range_by_indicator,
    latest_value_by_indicator,
    load_indicators,
    row_count_by_source,
)

SCHEMA = """
CREATE TABLE economic_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(indicator_name, date, source)
);
"""

FIXTURE = [
    ("CPI",     "2022-01-01", 140.0, "index_2010_100", "world_bank"),
    ("CPI",     "2023-01-01", 150.0, "index_2010_100", "world_bank"),
    ("CPI",     "2024-01-01", 158.3, "index_2010_100", "world_bank"),
    ("USD_ZAR", "2023-06-15", 18.5,  "ZAR_per_USD",    "frankfurter"),
    ("USD_ZAR", "2023-12-15", 18.7,  "ZAR_per_USD",    "frankfurter"),
    ("USD_ZAR", "2024-06-15", 18.2,  "ZAR_per_USD",    "frankfurter"),
]


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA)
    c.executemany(
        "INSERT INTO economic_indicators "
        "(indicator_name, date, value, unit, source) VALUES (?, ?, ?, ?, ?)",
        FIXTURE,
    )
    c.commit()
    yield c
    c.close()


def test_load_indicators_returns_all_rows(con):
    df = load_indicators(con)
    assert len(df) == 6
    assert df["date"].dtype.kind == "M"  # datetime64


def test_latest_value_picks_most_recent_per_indicator(con):
    df = latest_value_by_indicator(con)
    cpi = df[df["indicator_name"] == "CPI"].iloc[0]
    fx = df[df["indicator_name"] == "USD_ZAR"].iloc[0]
    assert cpi["date"] == "2024-01-01"
    assert fx["date"] == "2024-06-15"


def test_row_count_groups_by_source_and_indicator(con):
    df = row_count_by_source(con)
    assert set(df["source"]) == {"world_bank", "frankfurter"}
    assert df[df["indicator_name"] == "CPI"]["rows"].iloc[0] == 3


def test_date_range_reports_min_max(con):
    df = date_range_by_indicator(con)
    cpi = df[df["indicator_name"] == "CPI"].iloc[0]
    assert cpi["first_date"] == "2022-01-01"
    assert cpi["last_date"] == "2024-01-01"


def test_cpi_vs_fx_joins_on_year(con):
    df = cpi_vs_fx_by_year(con)
    # Years 2023 and 2024 overlap between CPI and FX
    assert set(df["year"]) == {2023, 2024}
    row_2023 = df[df["year"] == 2023].iloc[0]
    assert row_2023["cpi"] == 150.0
    assert row_2023["fx_avg"] == pytest.approx(18.6)