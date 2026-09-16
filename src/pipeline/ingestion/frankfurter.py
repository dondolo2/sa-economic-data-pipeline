import logging
from datetime import date

import requests

from .http import get_json
from .raw import write_raw

logger = logging.getLogger(__name__)

FRANKFURTER_BASE = "https://api.frankfurter.app"
BASE_CURRENCY = "USD"
QUOTE_CURRENCY = "ZAR"


def fetch_fx(
    session: requests.Session,
    start: date,
    end: date,
    out_dir: str = "data/raw",
) -> str:
    url = f"{FRANKFURTER_BASE}/{start.isoformat()}..{end.isoformat()}"
    params = {"from": BASE_CURRENCY, "to": QUOTE_CURRENCY}
    payload = get_json(session, url, params=params)

    _validate(payload)
    logger.info(
        "Frankfurter %s/%s: %d observations (%s → %s)",
        BASE_CURRENCY,
        QUOTE_CURRENCY,
        len(payload["rates"]),
        payload.get("start_date"),
        payload.get("end_date"),
    )

    prefix = f"frankfurter_{BASE_CURRENCY}_{QUOTE_CURRENCY}"
    path = write_raw(out_dir, prefix, payload)
    return str(path)


def _validate(payload) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"Expected dict, got {type(payload).__name__}")
    if "rates" not in payload:
        raise ValueError("Frankfurter response missing 'rates' key")
    rates = payload["rates"]
    if not isinstance(rates, dict) or not rates:
        raise ValueError("Frankfurter returned empty rates")
    sample = next(iter(rates.values()))
    if QUOTE_CURRENCY not in sample:
        raise ValueError(f"Frankfurter rates missing {QUOTE_CURRENCY}")