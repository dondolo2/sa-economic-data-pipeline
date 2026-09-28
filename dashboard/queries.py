"""SQL queries for the dashboard.

Kept separate from app.py so they can be tested without running Streamlit.
Every function takes an open sqlite3.Connection — the caller owns the lifecycle.
"""

import sqlite3

import pandas as pd


def load_indicators(con: sqlite3.Connection) -> pd.DataFrame:
    """All observations, ordered by date. Parses 'date' to datetime."""
    df = pd.read_sql_query(
        """
        SELECT indicator_name, date, value, unit, source
        FROM economic_indicators
        ORDER BY date
        """,
        con,
    )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def latest_value_by_indicator(con: sqlite3.Connection) -> pd.DataFrame:
    """Most recent observation per indicator."""
    return pd.read_sql_query(
        """
        SELECT indicator_name, date, value, unit
        FROM economic_indicators e
        WHERE date = (
            SELECT MAX(date) FROM economic_indicators
            WHERE indicator_name = e.indicator_name
        )
        ORDER BY indicator_name
        """,
        con,
    )


def row_count_by_source(con: sqlite3.Connection) -> pd.DataFrame:
    """Row count grouped by source — used on the data-quality tab."""
    return pd.read_sql_query(
        """
        SELECT source, indicator_name, COUNT(*) AS rows
        FROM economic_indicators
        GROUP BY source, indicator_name
        ORDER BY source, indicator_name
        """,
        con,
    )


def date_range_by_indicator(con: sqlite3.Connection) -> pd.DataFrame:
    """Min and max date per indicator."""
    return pd.read_sql_query(
        """
        SELECT indicator_name,
               MIN(date) AS first_date,
               MAX(date) AS last_date,
               COUNT(*)  AS rows
        FROM economic_indicators
        GROUP BY indicator_name
        ORDER BY indicator_name
        """,
        con,
    )


def cpi_vs_fx_by_year(con: sqlite3.Connection) -> pd.DataFrame:
    """CPI and average USD/ZAR joined on year.

    Join is on year, not date, because CPI is annual and FX is daily.
    See decisions.md §12.
    """
    return pd.read_sql_query(
        """
        SELECT CAST(strftime('%Y', c.date) AS INTEGER) AS year,
               c.value    AS cpi,
               AVG(f.value) AS fx_avg
        FROM economic_indicators c
        JOIN economic_indicators f
          ON strftime('%Y', c.date) = strftime('%Y', f.date)
        WHERE c.indicator_name = 'CPI'
          AND f.indicator_name = 'USD_ZAR'
        GROUP BY year
        ORDER BY year
        """,
        con,
    )