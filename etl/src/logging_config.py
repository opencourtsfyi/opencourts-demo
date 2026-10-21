"""Central logging configuration for the SC Probate Caseload ETL pipeline."""

import logging
import os
from pathlib import Path

LOG_DIR_ENV_VAR = "PIPELINE_LOG_DIR"


def setup_logging(log_dir=None):
    """Configure the root logger for console and optional file output."""
    resolved_log_dir = log_dir or os.environ.get(LOG_DIR_ENV_VAR)
    handlers = [logging.StreamHandler()]

    if resolved_log_dir is not None and str(resolved_log_dir).strip():
        resolved_log_dir = Path(resolved_log_dir)
        resolved_log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(resolved_log_dir / "pipeline.log"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )
