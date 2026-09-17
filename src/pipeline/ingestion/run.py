"""CLI entrypoint for the ingestion stage.

Fetches CPI from the World Bank and USD/ZAR from Frankfurter, writing
each raw payload to data/raw/.

Usage:
    python -m src.pipeline.ingestion.run [--fx-start YYYY-MM-DD]
                                         [--fx-end YYYY-MM-DD]
"""

import argparse
import logging
from datetime import date, timedelta

from .frankfurter import fetch_fx
from .http import build_session
from .world_bank import fetch_cpi

logger = logging.getLogger("pipeline.ingestion")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch raw SA economic data.")
    p.add_argument("--out-dir", default="data/raw")
    p.add_argument("--fx-start", default="2020-01-01")
    p.add_argument("--fx-end", default=None, help="ISO date; defaults to today")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    fx_start = date.fromisoformat(args.fx_start)
    fx_end = date.fromisoformat(args.fx_end) if args.fx_end else date.today()

    session = build_session()

    logger.info("Starting ingestion")
    cpi_path = fetch_cpi(session, out_dir=args.out_dir)
    fx_path = fetch_fx(session, fx_start, fx_end, out_dir=args.out_dir)
    logger.info("Ingestion complete")
    logger.info("  CPI: %s", cpi_path)
    logger.info("  FX:  %s", fx_path)


if __name__ == "__main__":
    main()