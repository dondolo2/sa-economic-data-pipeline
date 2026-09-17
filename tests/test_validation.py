import pandas as pd
import pytest

from src.pipeline.validation.validators import validate_observations


def _valid_df():
    return pd.DataFrame([
        {"indicator_name": "CPI", "date": "2023-01-01", "value": 158.3,
         "unit": "index_2010_100", "source": "world_bank"},
    ])


def test_valid_data_passes():
    report = validate_observations(_valid_df())
    assert report.ok


def test_empty_dataframe_fails():
    report = validate_observations(pd.DataFrame())
    assert not report.ok
    assert any("empty" in e.lower() for e in report.errors)


def test_null_value_fails():
    df = _valid_df()
    df.loc[0, "value"] = None
    report = validate_observations(df)
    assert not report.ok
    assert any("null" in e.lower() for e in report.errors)


def test_duplicate_natural_key_fails():
    df = pd.concat([_valid_df(), _valid_df()], ignore_index=True)
    report = validate_observations(df)
    assert not report.ok
    assert any("duplicate" in e.lower() for e in report.errors)


def test_unknown_source_fails():
    df = _valid_df()
    df.loc[0, "source"] = "some_blog"
    report = validate_observations(df)
    assert not report.ok
    assert any("source" in e.lower() for e in report.errors)


def test_bad_date_fails():
    df = _valid_df()
    df.loc[0, "date"] = "not-a-date"
    report = validate_observations(df)
    assert not report.ok
    assert any("date" in e.lower() for e in report.errors)


def test_raise_if_failed_raises():
    report = validate_observations(pd.DataFrame())
    with pytest.raises(ValueError):
        report.raise_if_failed()