"""Canonical filesystem paths for the pipeline.

Single source of truth so the loader and the dashboard can't drift apart.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "economic.db"