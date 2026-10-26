# orchestrator.py
"""
Top-level entry point for the local ETL pipeline.
Runs all four stages in order: Bronze download, Silver extraction,
Gold normalization, and final validation. All paths are defined once,
here, and passed down to each stage function.
"""

import logging
from logging_config import setup_logging

import argparse
from pathlib import Path

from downloader import download_pdfs
from pdf_extraction import extract_pdfs_to_silver
from normalize_parquets import normalize_silver_to_gold
from validate_pipeline import validate_gold_csv, write_error_report

logger = logging.getLogger(__name__)
from i18n import t

#TODO internationalize user facing strings in this file
def run_pipeline(overwrite_existing: bool = False) -> None:
    base_dir = Path(__file__).parent
    bronze_dir = base_dir / "data/pdfs_bronze"
    silver_dir = base_dir / "data/cases_silver"
    gold_dir = base_dir / "data/cases_gold"
    provenance_dir = base_dir / "data/provenance"
    log_dir = base_dir / "data/logs"

    setup_logging(log_dir=log_dir)

    logger.info("=== Step 1: Bronze — Downloading PDFs ===")
    download_pdfs(bronze_dir, provenance_dir, overwrite_existing=overwrite_existing)

    logger.info("=== Step 2: Silver — Extracting tables from PDFs ===")
    extract_pdfs_to_silver(bronze_dir, silver_dir, provenance_dir)

    logger.info("=== Step 3: Gold — Normalizing to CSV and Parquet ===")
    normalize_silver_to_gold(silver_dir, gold_dir, provenance_dir)

    logger.info("=== Step 4: Validating Gold output ===")
    errors = validate_gold_csv(gold_dir / "caseloads_normalized.csv")
    write_error_report(errors, base_dir / "data/validation/errors.csv")

    if errors:
        logger.error(f"Pipeline completed with {len(errors)} validation issue(s). Review before publishing.")
    else:
        logger.info("Pipeline completed successfully. All validation checks passed.")


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments for orchestrator.py."""
    parser = argparse.ArgumentParser(description=t("orchestrator.cli_description"))
    parser.add_argument(
        "--overwrite-existing",
        "--overwrite",
        dest="overwrite_existing",
        action="store_true",
        default=False,
        help=t("orchestrator.cli_help_overwrite_existing"),
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> None:
    """CLI entry point for orchestrator.py."""
    cli_args = parse_args(args)
    run_pipeline(overwrite_existing=cli_args.overwrite_existing)


if __name__ == "__main__":
    main()