"""Data-quality checks on the canonical schema.

This is the trust boundary: nothing reaches the database unless it passes.
If a check fails, the pipeline exits non-zero and the processed file is not
written. See decisions.md point 3.
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["indicator_name", "date", "value", "unit", "source"]
VALID_SOURCES = {"world_bank", "frankfurter"}


@dataclass
class ValidationReport:
    rows_checked: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_failed(self) -> None:
        if self.errors:
            raise ValueError(
                "Validation failed:\n  - " + "\n  - ".join(self.errors)
            )


def validate_observations(df: pd.DataFrame) -> ValidationReport:
    report = ValidationReport(rows_checked=len(df))

    if df.empty:
        report.errors.append("Dataset is empty")
        return report

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        report.errors.append(f"Missing required columns: {missing}")
        return report

    # 1. No nulls in required columns
    null_counts = df[REQUIRED_COLUMNS].isna().sum()
    for col, count in null_counts.items():
        if count:
            report.errors.append(f"Column '{col}' has {count} null value(s)")

    # 2. Dates parse as ISO
    bad_dates = pd.to_datetime(df["date"], errors="coerce").isna().sum()
    if bad_dates:
        report.errors.append(f"{bad_dates} row(s) with unparseable date")

    # 3. Values are finite
    import numpy as np
    non_finite = (~np.isfinite(df["value"].astype(float))).sum()
    if non_finite:
        report.errors.append(f"{non_finite} row(s) with non-finite value")

    # 4. No duplicate natural key
    dupes = df.duplicated(subset=["indicator_name", "date", "source"]).sum()
    if dupes:
        report.errors.append(f"{dupes} duplicate row(s) on (indicator_name, date, source)")

    # 5. Source is a known value
    unknown = set(df["source"].unique()) - VALID_SOURCES
    if unknown:
        report.errors.append(f"Unknown source(s): {sorted(unknown)}")

    # 6. Units are non-empty
    empty_units = (df["unit"].astype(str).str.strip() == "").sum()
    if empty_units:
        report.errors.append(f"{empty_units} row(s) with empty unit")

    if report.ok:
        logger.info("Validation passed: %d rows, %d indicators",
                    report.rows_checked, df["indicator_name"].nunique())
    else:
        logger.error("Validation FAILED with %d error(s)", len(report.errors))
        for e in report.errors:
            logger.error("  - %s", e)

    return report