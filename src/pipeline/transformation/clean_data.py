"""Turn raw source payloads into the canonical observation schema.

Canonical schema (matches decisions.md point 5):
    indicator_name : str    e.g. 'CPI', 'USD_ZAR'
    date           : str    ISO 8601 (YYYY-MM-DD)
    value          : float
    unit           : str    e.g. 'index_2010_100', 'ZAR_per_USD'
    source         : str    e.g. 'world_bank', 'frankfurter'
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

CANONICAL_COLUMNS = ["indicator_name", "date", "value", "unit", "source"]

COUNTRY_ZAF = "ZAF"


# ---------------------------------------------------------------------------
# World Bank CPI
# ---------------------------------------------------------------------------

def transform_world_bank_cpi(payload: list[Any]) -> pd.DataFrame:
    """payload is the raw [metadata, records] list from the World Bank API."""
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("World Bank payload missing [metadata, records]")

    records = payload[1] or []
    rows: list[dict[str, Any]] = []
    skipped_non_za = 0
    skipped_null_value = 0
    skipped_bad_value = 0

    for r in records:
        if r.get("countryiso3code") != COUNTRY_ZAF:
            skipped_non_za += 1
            continue

        raw_value = r.get("value")
        if raw_value is None:
            skipped_null_value += 1
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            skipped_bad_value += 1
            logger.warning("Dropping CPI record with unparseable value: %r", raw_value)
            continue

        year = r.get("date")
        if not year or not str(year).isdigit():
            skipped_bad_value += 1
            logger.warning("Dropping CPI record with bad year: %r", year)
            continue

        rows.append({
            "indicator_name": "CPI",
            "date": f"{year}-01-01",
            "value": value,
            "unit": "index_2010_100",
            "source": "world_bank",
        })

    logger.info(
        "CPI: kept=%d skipped(non-ZA=%d null=%d bad=%d)",
        len(rows), skipped_non_za, skipped_null_value, skipped_bad_value,
    )
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)


# ---------------------------------------------------------------------------
# Frankfurter FX
# ---------------------------------------------------------------------------

def transform_frankfurter_fx(payload: dict[str, Any]) -> pd.DataFrame:
    """payload is the raw Frankfurter {rates: {date: {ZAR: val}}} dict."""
    if not isinstance(payload, dict):
        raise ValueError(f"Expected dict, got {type(payload).__name__}")

    rates = payload.get("rates")
    if not isinstance(rates, dict):
        raise ValueError("Frankfurter payload missing 'rates' dict")

    rows: list[dict[str, Any]] = []
    skipped_missing_quote = 0
    skipped_bad_value = 0

    for date_str, quote in rates.items():
        if "ZAR" not in quote:
            skipped_missing_quote += 1
            continue
        try:
            value = float(quote["ZAR"])
        except (TypeError, ValueError):
            skipped_bad_value += 1
            logger.warning("Dropping FX record with bad value: %r", quote)
            continue

        rows.append({
            "indicator_name": "USD_ZAR",
            "date": date_str,
            "value": value,
            "unit": "ZAR_per_USD",
            "source": "frankfurter",
        })

    logger.info(
        "FX: kept=%d skipped(missing-quote=%d bad=%d)",
        len(rows), skipped_missing_quote, skipped_bad_value,
    )
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)


# ---------------------------------------------------------------------------
# Combine
# ---------------------------------------------------------------------------

def combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate, sort, and de-duplicate on the natural key."""
    non_empty = [f for f in frames if not f.empty]
    if not non_empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    combined = pd.concat(non_empty, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.strftime("%Y-%m-%d")

    before = len(combined)
    combined = combined.drop_duplicates(
        subset=["indicator_name", "date", "source"], keep="last"
    )
    dropped = before - len(combined)
    if dropped:
        logger.warning("Dropped %d duplicate rows on natural key", dropped)

    combined = combined.sort_values(
        ["indicator_name", "source", "date"]
    ).reset_index(drop=True)
    return combined