"""CLI entrypoint for the storage stage.

Reads the latest processed CSV from data/processed/ and upserts it into
SQLite using the natural key (indicator_name, date, source). Idempotent:
re-running with the same input produces the same database state.

Usage:
    python -m src.pipeline.storage.run [--db-path PATH]
                                       [--in-dir DIR]
"""

import argparse
import logging
from pathlib import Path

import pandas as pd

from .db import connect, init_schema
from .loader import load_observations

logger = logging.getLogger("pipeline.storage")


def latest_processed(in_dir: Path) -> Path:
    """Return the most recent economic_indicators_*.csv in in_dir."""
    matches = sorted(in_dir.glob("economic_indicators_*.csv"))
    if not matches:
        raise FileNotFoundError(
            f"No processed CSV matching economic_indicators_*.csv in {in_dir}"
        )
    return matches[-1]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    p = argparse.ArgumentParser(description="Load processed data into SQLite.")
    p.add_argument("--db-path", default="data/economic.db")
    p.add_argument("--in-dir", default="data/processed")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args()


def main() -> None:
    """Run the storage stage end to end."""
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    csv_path = latest_processed(Path(args.in_dir))
    logger.info("Using processed CSV: %s", csv_path.name)

    df = pd.read_csv(csv_path)
    logger.info("Read %d rows from %s", len(df), csv_path.name)

    conn = connect(args.db_path)
    try:
        init_schema(conn)
        load_observations(conn, df)
    finally:
        conn.close()


if __name__ == "__main__":
    main()