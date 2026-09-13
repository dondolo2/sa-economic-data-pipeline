import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def write_raw(out_dir: str | Path, prefix: str, payload: dict | list) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{prefix}_{ts}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.info("Saved raw file: %s", path)
    return path