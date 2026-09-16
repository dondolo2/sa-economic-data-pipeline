"""Transform raw JSON files into a single validated processed CSV.

Usage:
    python -m src.pipeline.transformation.run \
        --raw-dir data/raw \
        --out-dir data/processed
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..validation.validators import validate_observations
from .clean_data import (
    combine,
    transform_frankfurter_fx,
    transform_world_bank_cpi,
)

logger = logging.getLogger("pipeline.transformation")


def latest_raw(raw_dir: Path, prefix: str) -> Path:
    """Return the most recently-modified file matching prefix_*.json."""
    matches = sorted(raw_dir.glob(f"{prefix}_*.json"))
    if not matches:
        raise FileNotFoundError(f"No raw files matching {prefix}_*.json in {raw_dir}")
    # Filenames embed an ISO-like UTC timestamp, so lexical sort == chronological
    return matches[-1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Transform raw SA economic data.")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--out-dir", default="data/processed")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cpi_file = latest_raw(raw_dir, "world_bank_cpi")
    fx_file = latest_raw(raw_dir, "frankfurter_USD_ZAR")
    logger.info("Using CPI raw file: %s", cpi_file.name)
    logger.info("Using FX  raw file: %s", fx_file.name)

    cpi_df = transform_world_bank_cpi(json.loads(cpi_file.read_text()))
    fx_df = transform_frankfurter_fx(json.loads(fx_file.read_text()))
    combined = combine([cpi_df, fx_df])

    report = validate_observations(combined)
    report.raise_if_failed()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"economic_indicators_{ts}.csv"
    combined.to_csv(out_path, index=False)
    logger.info("Wrote %d rows to %s", len(combined), out_path)


if __name__ == "__main__":
    main()