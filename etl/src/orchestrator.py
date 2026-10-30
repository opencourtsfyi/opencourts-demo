# orchestrator.py
"""
Top-level entry point for the local ETL pipeline.
Runs all four stages in order: Bronze download, Silver extraction,
Gold normalization, and final validation. All paths are defined once,
here, and passed down to each stage function.
"""

from __future__ import annotations

import argparse
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Domain and operational constants (No Magic Values)
DEFAULT_OVERWRITE_EXISTING: bool = False
STEP_COUNT: int = 4
EXIT_CODE_SUCCESS: int = 0
EXIT_CODE_FAILURE: int = 1

STEP_NUMBER_BRONZE: int = 1
STEP_DESC_BRONZE: str = "Bronze — Downloading PDFs"

STEP_NUMBER_SILVER: int = 2
STEP_DESC_SILVER: str = "Silver — Extracting tables from PDFs"

STEP_NUMBER_GOLD: int = 3
STEP_DESC_GOLD: str = "Gold — Normalizing to CSV and Parquet"

STEP_NUMBER_VALIDATION: int = 4
STEP_DESC_VALIDATION: str = "Validating Gold output"

LOGGER_NAME: str = "orchestrator"
ENV_PIPELINE_LOG_DIR: str = "PIPELINE_LOG_DIR"

DIR_NAME_DATA: str = "data"
DIR_NAME_BRONZE: str = "pdfs_bronze"
DIR_NAME_SILVER: str = "cases_silver"
DIR_NAME_GOLD: str = "cases_gold"
DIR_NAME_PROVENANCE: str = "provenance"
DIR_NAME_LOGS: str = "logs"
DIR_NAME_VALIDATION: str = "validation"

FILE_NAME_GOLD_CSV: str = "caseloads_normalized.csv"
FILE_NAME_ERRORS_CSV: str = "errors.csv"

# Set before importing stage modules: each stage module builds its logger
# at import time via get_logger(__name__) with no log_dir argument, so the
# file destination has to be available as an env var *before* those imports
# run, or those loggers only ever get a console handler (see logging_config
# get_logger docstring / issue #2).
_base_dir = Path(__file__).parent
os.environ.setdefault(ENV_PIPELINE_LOG_DIR, str(_base_dir / DIR_NAME_DATA / DIR_NAME_LOGS))

from downloader import download_pdfs
from pdf_extraction import extract_pdfs_to_silver
from normalize import normalize_silver_to_gold
from validate_pipeline import validate_gold_csv, write_error_report
from logging_config import setup_logging

logger = logging.getLogger(__name__)
from i18n import t

#TODO internationalize user facing strings in this file
@dataclass(frozen=True)
class PipelineConfig:
    """Holds configuration paths and execution parameters for the ETL pipeline."""

    base_dir: Path
    bronze_dir: Path
    silver_dir: Path
    gold_dir: Path
    provenance_dir: Path
    log_dir: Path
    validation_dir: Path
    gold_csv_path: Path
    error_report_path: Path
    overwrite_existing: bool = DEFAULT_OVERWRITE_EXISTING
    start_year: int | None = None
    end_year: int | None = None
    category: str | None = None

    @classmethod
    def from_base_dir(
        cls,
        base_dir: Path,
        overwrite_existing: bool = DEFAULT_OVERWRITE_EXISTING,
        start_year: int | None = None,
        end_year: int | None = None,
        category: str | None = None,
    ) -> PipelineConfig:
        """Construct pipeline configuration relative to a base directory."""
        data_dir = base_dir / DIR_NAME_DATA
        gold_dir = data_dir / DIR_NAME_GOLD
        validation_dir = data_dir / DIR_NAME_VALIDATION
        return cls(
            base_dir=base_dir,
            bronze_dir=data_dir / DIR_NAME_BRONZE,
            silver_dir=data_dir / DIR_NAME_SILVER,
            gold_dir=gold_dir,
            provenance_dir=data_dir / DIR_NAME_PROVENANCE,
            log_dir=data_dir / DIR_NAME_LOGS,
            validation_dir=validation_dir,
            gold_csv_path=gold_dir / FILE_NAME_GOLD_CSV,
            error_report_path=validation_dir / FILE_NAME_ERRORS_CSV,
            overwrite_existing=overwrite_existing,
            start_year=start_year,
            end_year=end_year,
            category=category,
        )


@dataclass
class PipelineContext:
    """Runtime context passed across stages during pipeline execution."""

    config: PipelineConfig
    validation_errors: list[Any] = field(default_factory=list)


class PipelineStage(ABC):
    """Abstract base class representing a single discrete stage in the ETL pipeline."""

    @property
    @abstractmethod
    def step_number(self) -> int:
        """The 1-indexed execution step number."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the stage for headers and logging."""
        ...

    @abstractmethod
    def execute(self, context: PipelineContext) -> None:
        """Execute the stage logic using the provided pipeline context."""
        ...


class BronzeDownloadStage(PipelineStage):
    """Downloads raw PDF reports from the court website into the Bronze tier."""

    def __init__(self, download_fn: Callable[..., Any] | None = None) -> None:
        self._download_fn = download_fn

    @property
    def step_number(self) -> int:
        return STEP_NUMBER_BRONZE

    @property
    def description(self) -> str:
        return STEP_DESC_BRONZE

    def execute(self, context: PipelineContext) -> None:
        fn = self._download_fn if self._download_fn is not None else download_pdfs
        fn(
            context.config.bronze_dir,
            context.config.provenance_dir,
            overwrite_existing=context.config.overwrite_existing,
        )


class SilverExtractionStage(PipelineStage):
    """Extracts tables from the original PDFs in Bronze location and stores them in the Silver location."""

    def __init__(self, extract_fn: Callable[..., Any] | None = None) -> None:
        self._extract_fn = extract_fn

    @property
    def step_number(self) -> int:
        return STEP_NUMBER_SILVER

    @property
    def description(self) -> str:
        return STEP_DESC_SILVER

    def execute(self, context: PipelineContext) -> None:
        fn = self._extract_fn if self._extract_fn is not None else extract_pdfs_to_silver
        fn(context.config.bronze_dir, context.config.silver_dir, context.config.provenance_dir)


class GoldNormalizationStage(PipelineStage):
    """Normalizes Silver parquets into final Gold CSV and parquet datasets."""

    def __init__(self, normalize_fn: Callable[..., Any] | None = None) -> None:
        self._normalize_fn = normalize_fn

    @property
    def step_number(self) -> int:
        return STEP_NUMBER_GOLD

    @property
    def description(self) -> str:
        return STEP_DESC_GOLD

    def execute(self, context: PipelineContext) -> None:
        fn = self._normalize_fn if self._normalize_fn is not None else normalize_silver_to_gold
        fn(context.config.silver_dir, context.config.gold_dir, context.config.provenance_dir)


class GoldValidationStage(PipelineStage):
    """Validates Gold CSV outputs and writes any validation issues to an error report."""

    def __init__(
        self,
        validate_fn: Callable[..., Any] | None = None,
        report_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._validate_fn = validate_fn
        self._report_fn = report_fn

    @property
    def step_number(self) -> int:
        return STEP_NUMBER_VALIDATION

    @property
    def description(self) -> str:
        return STEP_DESC_VALIDATION

    def execute(self, context: PipelineContext) -> None:
        validate_fn = self._validate_fn if self._validate_fn is not None else validate_gold_csv
        report_fn = self._report_fn if self._report_fn is not None else write_error_report

        errors = validate_fn(context.config.gold_csv_path)
        context.validation_errors = list(errors) if errors else []
        report_fn(errors, context.config.error_report_path)


class PipelineOrchestrator:
    """Coordinates execution of sequential pipeline stages with unified logging."""

    def __init__(
        self,
        stages: Sequence[PipelineStage] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.stages: list[PipelineStage] = (
            list(stages) if stages is not None else self.default_stages()
        )
        self.logger = logger

    @staticmethod
    def default_stages() -> list[PipelineStage]:
        """Creates the default 4-stage pipeline for Bronze -> Silver -> Gold -> Validation."""
        return [
            BronzeDownloadStage(),
            SilverExtractionStage(),
            GoldNormalizationStage(),
            GoldValidationStage(),
        ]

    def run(self, context: PipelineContext) -> PipelineContext:
        """Executes all stages in sequence and logs overall pipeline status."""
        logger = self.logger or logging.getLogger(__name__)
        for stage in self.stages:
            logger.info(f"=== Step {stage.step_number}: {stage.description} ===")
            stage.execute(context)

        if context.validation_errors:
            logger.error(
                f"Pipeline completed with {len(context.validation_errors)} validation issue(s). Review before publishing."
            )
        else:
            logger.info("Pipeline completed successfully. All validation checks passed.")

        return context


def run_pipeline(
    overwrite_existing: bool = DEFAULT_OVERWRITE_EXISTING,
    start_year: int | None = None,
    end_year: int | None = None,
    category: str | None = None
) -> None:
    """Run all ETL pipeline stages in order from Bronze download to Gold validation."""
    base_dir = Path(__file__).parent
    pipeline_config = PipelineConfig.from_base_dir(
        base_dir=base_dir,
        overwrite_existing=overwrite_existing,
        start_year=start_year,
        end_year=end_year,
        category=category,
    )
    setup_logging(log_dir=pipeline_config.log_dir)
    context = PipelineContext(config=pipeline_config)
    pipeline_orchestrator = PipelineOrchestrator(logger=logger)
    pipeline_orchestrator.run(context)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments for orchestrator.py."""
    parser = argparse.ArgumentParser(description=t("orchestrator.cli_description"))
    parser.add_argument(
        "--overwrite-existing",
        "--overwrite",
        dest="overwrite_existing",
        action="store_true",
        default=DEFAULT_OVERWRITE_EXISTING,
        help=t("orchestrator.cli_help_overwrite_existing"),
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> None:
    """CLI entry point for orchestrator.py."""
    cli_args = parse_args(args)
    run_pipeline(overwrite_existing=cli_args.overwrite_existing)


if __name__ == "__main__":
    main()