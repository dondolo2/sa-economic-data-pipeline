from src.pipeline.transformation.clean_data import (
    CANONICAL_COLUMNS,
    combine,
    transform_frankfurter_fx,
    transform_world_bank_cpi,
)


def _wb_record(year, value, country="ZAF"):
    return {
        "date": str(year),
        "value": value,
        "countryiso3code": country,
        "indicator": {"id": "FP.CPI.TOTL"},
    }


def test_cpi_transform_produces_canonical_schema():
    payload = [{"page": 1}, [_wb_record(2023, 158.3), _wb_record(2024, 165.1)]]
    df = transform_world_bank_cpi(payload)
    assert list(df.columns) == CANONICAL_COLUMNS
    assert len(df) == 2
    assert df.iloc[0]["date"] == "2023-01-01"
    assert df.iloc[0]["indicator_name"] == "CPI"
    assert df.iloc[0]["unit"] == "index_2010_100"


def test_cpi_transform_drops_null_values():
    payload = [{"page": 1}, [_wb_record(2023, None), _wb_record(2024, 165.1)]]
    df = transform_world_bank_cpi(payload)
    assert len(df) == 1
    assert df.iloc[0]["date"] == "2024-01-01"


def test_cpi_transform_drops_non_za_records():
    payload = [{"page": 1}, [_wb_record(2023, 100.0, country="KEN"),
                              _wb_record(2024, 165.1, country="ZAF")]]
    df = transform_world_bank_cpi(payload)
    assert len(df) == 1


def test_fx_transform_produces_canonical_schema():
    payload = {"rates": {"2024-01-02": {"ZAR": 18.5},
                         "2024-01-03": {"ZAR": 18.7}}}
    df = transform_frankfurter_fx(payload)
    assert list(df.columns) == CANONICAL_COLUMNS
    assert len(df) == 2
    assert df.iloc[0]["unit"] == "ZAR_per_USD"
    assert df.iloc[0]["source"] == "frankfurter"


def test_fx_transform_skips_dates_missing_zar():
    payload = {"rates": {"2024-01-02": {"EUR": 0.92},
                         "2024-01-03": {"ZAR": 18.7}}}
    df = transform_frankfurter_fx(payload)
    assert len(df) == 1


def test_combine_deduplicates_on_natural_key():
    import pandas as pd
    a = pd.DataFrame([{"indicator_name": "CPI", "date": "2023-01-01",
                       "value": 1.0, "unit": "x", "source": "world_bank"}])
    b = pd.DataFrame([{"indicator_name": "CPI", "date": "2023-01-01",
                       "value": 2.0, "unit": "x", "source": "world_bank"}])
    out = combine([a, b])
    assert len(out) == 1
    assert out.iloc[0]["value"] == 2.0   # keep='last'


def test_combine_is_deterministic():
    import pandas as pd
    frames = [
        pd.DataFrame([{"indicator_name": "CPI", "date": "2023-01-01",
                       "value": 1.0, "unit": "x", "source": "world_bank"}]),
        pd.DataFrame([{"indicator_name": "USD_ZAR", "date": "2024-01-02",
                       "value": 18.5, "unit": "y", "source": "frankfurter"}]),
    ]
    assert combine(frames).equals(combine(frames))