"""Shared HTTP session for all external API calls.

Provides a requests.Session pre-configured with retries, exponential
backoff, and a hard timeout, plus a get_json() helper that raises on
non-2xx responses instead of returning an error body.

Used by: world_bank.py, frankfurter.py
"""

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3


def build_session(retries: int = DEFAULT_RETRIES) -> requests.Session:
    """Session with retries on transient failures and a hard timeout."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=0.5,          # 0s, 0.5s, 1s, 2s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,       # let raise_for_status handle it
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_json(
    session: requests.Session,
    url: str,
    params: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict | list:
    logger.info("GET %s params=%s", url, params)
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    logger.info("HTTP %s (%d bytes)", response.status_code, len(response.content))
    return response.json()