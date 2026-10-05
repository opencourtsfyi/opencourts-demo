# orchestrator.py
"""
Top-level entry point for the local ETL pipeline.
Runs all four stages in order: Bronze download, Silver extraction,
Gold normalization, and final validation. All paths are defined once,
here, and passed down to each stage function.
"""

import os
from pathlib import Path

# Set before importing stage modules: each stage module builds its logger
# at import time via get_logger(__name__) with no log_dir argument, so the
# file destination has to be available as an env var *before* those imports
# run, or those loggers only ever get a console handler (see logging_config
# get_logger docstring / issue #2).
_base_dir = Path(__file__).parent
os.environ.setdefault("PIPELINE_LOG_DIR", str(_base_dir / "data" / "logs"))

from downloader import download_pdfs
from pdf_extraction import extract_pdfs_to_silver
from normalize_parquets import normalize_silver_to_gold
from validate_pipeline import validate_gold_csv
from logging_config import get_logger


def run_pipeline():
    base_dir = Path(__file__).parent
    bronze_dir = base_dir / "data/pdfs_bronze"
    silver_dir = base_dir / "data/cases_silver"
    gold_dir = base_dir / "data/cases_gold"
    provenance_dir = base_dir / "data/provenance"
    log_dir = base_dir / "data/logs"

    # One shared logger for the whole run, writes to both console and pipeline.log
    logger = get_logger("orchestrator", log_dir=log_dir)

    logger.info("=== Step 1: Bronze — Downloading PDFs ===")
    download_pdfs(bronze_dir, provenance_dir)

    logger.info("=== Step 2: Silver — Extracting tables from PDFs ===")
    extract_pdfs_to_silver(bronze_dir, silver_dir, provenance_dir)

    logger.info("=== Step 3: Gold — Normalizing to CSV and Parquet ===")
    normalize_silver_to_gold(silver_dir, gold_dir, provenance_dir)

    logger.info("=== Step 4: Validating Gold output ===")
    issues = validate_gold_csv(gold_dir / "caseloads_normalized.csv", logger=logger)

    if issues:
        logger.error(f"Pipeline completed with {len(issues)} validation issue(s). Review before publishing.")
    else:
        logger.info("Pipeline completed successfully. All validation checks passed.")


if __name__ == "__main__":
    run_pipeline()
