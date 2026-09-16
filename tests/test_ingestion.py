import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.pipeline.ingestion.frankfurter import fetch_fx, _validate as validate_fx
from src.pipeline.ingestion.world_bank import fetch_cpi, _validate as validate_wb


def test_world_bank_validation_rejects_empty_records():
    with pytest.raises(ValueError, match="zero records"):
        validate_wb([{"page": 1}, []])


def test_world_bank_validation_rejects_null_records():
    with pytest.raises(ValueError, match="null records"):
        validate_wb([{"page": 1}, None])


def test_world_bank_validation_accepts_valid_payload():
    payload = [
        {"page": 1},
        [{
            "date": "2023",
            "value": 158.3,
            "indicator": {"id": "FP.CPI.TOTL"},
            "countryiso3code": "ZAF",
        }],
    ]
    validate_wb(payload)  # should not raise


def test_world_bank_writes_raw_file(tmp_path, monkeypatch):
    fake_payload = [
        {"page": 1},
        [{
            "date": "2023",
            "value": 158.3,
            "indicator": {"id": "FP.CPI.TOTL"},
            "countryiso3code": "ZAF",
        }],
    ]

    class FakeResponse:
        status_code = 200
        content = b"{}"
        def raise_for_status(self): pass
        def json(self): return fake_payload

    session = MagicMock()
    session.get.return_value = FakeResponse()

    path = fetch_cpi(session, out_dir=str(tmp_path))
    assert Path(path).exists()
    written = json.loads(Path(path).read_text())
    assert written[1][0]["value"] == 158.3


def test_frankfurter_validation_rejects_missing_rates():
    with pytest.raises(ValueError, match="missing 'rates'"):
        validate_fx({"amount": 1.0, "base": "USD"})


def test_frankfurter_validation_rejects_wrong_quote_currency():
    with pytest.raises(ValueError, match="missing ZAR"):
        validate_fx({"rates": {"2024-01-01": {"EUR": 0.92}}})


def test_frankfurter_writes_raw_file(tmp_path):
    fake_payload = {
        "amount": 1.0,
        "base": "USD",
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "rates": {"2024-01-02": {"ZAR": 18.5}, "2024-01-03": {"ZAR": 18.7}},
    }

    class FakeResponse:
        status_code = 200
        content = b"{}"
        def raise_for_status(self): pass
        def json(self): return fake_payload

    session = MagicMock()
    session.get.return_value = FakeResponse()

    path = fetch_fx(session, date(2024, 1, 1), date(2024, 1, 3), out_dir=str(tmp_path))
    written = json.loads(Path(path).read_text())
    assert written["rates"]["2024-01-02"]["ZAR"] == 18.5