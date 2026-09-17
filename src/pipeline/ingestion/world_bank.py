"""Fetch South African CPI from the World Bank API.

Endpoint: /v2/country/ZAF/indicator/FP.CPI.TOTL
Returns annual CPI as an index (2010 = 100).

Input:  an HTTP session (see http.py)
Output: path to the raw JSON file written under data/raw/
"""

import logging

import requests

from .http import get_json
from .raw import write_raw

logger = logging.getLogger(__name__)

WORLD_BANK_BASE = "https://api.worldbank.org/v2"
COUNTRY = "ZAF"
INDICATOR_CPI = "FP.CPI.TOTL"
RAW_PREFIX = "world_bank_cpi"


def fetch_cpi(session: requests.Session, out_dir: str = "data/raw") -> str:
    url = f"{WORLD_BANK_BASE}/country/{COUNTRY}/indicator/{INDICATOR_CPI}"
    payload = get_json(session, url, params={"format": "json", "per_page": 200})

    _validate(payload)
    records = payload[1]
    logger.info("World Bank CPI: %d records returned", len(records))

    path = write_raw(out_dir, RAW_PREFIX, payload)
    return str(path)


def _validate(payload) -> None:
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("World Bank response missing [metadata, records] structure")

    records = payload[1]
    if records is None:
        raise ValueError("World Bank returned null records — likely an API error")
    if not isinstance(records, list):
        raise ValueError(f"Expected list of records, got {type(records).__name__}")
    if not records:
        raise ValueError("World Bank returned zero records")

    first = records[0]
    for key in ("date", "value", "indicator", "countryiso3code"):
        if key not in first:
            raise ValueError(f"World Bank record missing key: {key}")