# validate_pipeline.py
"""
Validation stage: sanity-checks the Gold CSV after the pipeline runs, to
catch a broken or malformed output before anyone downstream trusts it.
Run standalone for a quick check, or as the orchestrator's final step.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, field_validator

from normalize import CATEGORY, SC_COUNTIES, EXPECTED_METRICS, EXPECTED_METRICS_MENTAL_HEALTH, SCHEMA

logger = logging.getLogger(__name__)

DUPLICATE_KEYS = ["file", "category", "month", "year", "county", "metric"]
ALLOWED_TEXT_VALUES = ("DNR", "TI", "N/A", "")
MIN_MONTH = 1
MAX_MONTH = 12
MIN_YEAR = 2007
MAX_YEAR = 2100
FIRST_DATA_ROW_NUMBER = 2
HEADER_ROW_NUMBER = 1
PYDANTIC_VALUE_ERROR_PREFIX = "Value error, "


class GoldRow(BaseModel):
    """Schema for one Gold row. A field that is None (column absent) is not checked."""

    model_config = ConfigDict(extra="ignore")

    category: Optional[str] = None
    county: Optional[str] = None
    month: Optional[str] = None
    year: Optional[str] = None
    # Declared after category so check_metric can see the validated category.
    metric: Optional[str] = None
    value: Optional[str] = None

    @field_validator("category")
    @classmethod
    def check_category(cls, v):
        if v is not None and v not in CATEGORY:
            raise ValueError(f"Unrecognized category value: {v!r}")
        return v

    @field_validator("county")
    @classmethod
    def check_county(cls, v):
        if v is not None and v not in SC_COUNTIES:
            raise ValueError(f"Unrecognized county value: {v!r}")
        return v

    @field_validator("month")
    @classmethod
    def check_month(cls, v):
        if v is not None:
            try:
                month = int(v)
                if not MIN_MONTH <= month <= MAX_MONTH:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid month value {v!r}; expected an integer from {MIN_MONTH} to {MAX_MONTH}"
                )
        return v

    @field_validator("year")
    @classmethod
    def check_year(cls, v):
        if v is not None:
            try:
                year = int(v)
                if not MIN_YEAR <= year <= MAX_YEAR:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid year value {v!r}; expected an integer from {MIN_YEAR} to {MAX_YEAR}"
                )
        return v

    @field_validator("metric")
    @classmethod
    def check_metric(cls, v, info: ValidationInfo):
        # Only check the metric if the category is actually recognized (it is
        # absent from info.data otherwise), to avoid a redundant error.
        category = info.data.get("category")
        if v is None or category is None:
            return v
        if category in ("Estate", "Guardian", "Conservator"):
            metric_is_valid = v in EXPECTED_METRICS
        elif category == "Mental Health":
            metric_is_valid = v in EXPECTED_METRICS_MENTAL_HEALTH
        else:
            metric_is_valid = False
        if not metric_is_valid:
            raise ValueError(f"Metric {v!r} does not match category {category!r}")
        return v

    @field_validator("value")
    @classmethod
    def check_value(cls, v):
        if v is not None:
            try:
                int(v)
                value_is_valid = True
            except (ValueError, TypeError):
                value_is_valid = v in ALLOWED_TEXT_VALUES
            if not value_is_valid:
                raise ValueError(
                    f"Invalid value {v!r}; expected an integer, blank, 'DNR', 'TI', or 'N/A'"
                )
        return v


def _resolve_row_filename(row, fallback_filename):
    """Return the row's 'file' value if present and non-empty, else fallback_filename."""
    if "file" in row and pd.notna(row["file"]) and row["file"] != "":
        return str(row["file"])
    return fallback_filename


def validate_gold_dataframe(df, fallback_filename):
    """Validate an in-memory Gold DataFrame (no file I/O) and return structured error dicts."""
    errors = []

    def add_error(details, row_number, row=None):
        errors.append({
            "filename": fallback_filename if row is None else _resolve_row_filename(row, fallback_filename),
            "row_number": row_number,
            "error_details": details,
        })

    if df.empty:
        add_error("Gold CSV is empty", HEADER_ROW_NUMBER)

    if list(df.columns) != SCHEMA:
        add_error(f"Column mismatch. Expected {SCHEMA}, got {list(df.columns)}", HEADER_ROW_NUMBER)

    for index, (_, row) in enumerate(df.iterrows()):
        row_number = index + FIRST_DATA_ROW_NUMBER
        if row.eq("").all():
            add_error("Found fully-null row", row_number, row)

        try:
            GoldRow.model_validate(row.to_dict())
        except ValidationError as exc:
            for err in exc.errors():
                add_error(err["msg"].removeprefix(PYDANTIC_VALUE_ERROR_PREFIX), row_number, row)

    if all(column in df.columns for column in DUPLICATE_KEYS):
        duplicates = df[df.duplicated(subset=DUPLICATE_KEYS, keep=False)]
        for index, row in duplicates.iterrows():
            add_error(
                "Duplicate data point for file/category/month/year/county/metric",
                index + FIRST_DATA_ROW_NUMBER,
                row,
            )

    return errors


def write_error_report(errors, output_path):
    """Writes the structured error report to a CSV file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(errors, columns=["filename", "row_number", "error_details"]).to_csv(
        output_path,
        index=False,
    )


def validate_gold_csv(gold_csv_path):
    """Validate the Gold CSV and return a list of structured error dicts."""
    gold_csv_path = Path(gold_csv_path)
    fallback_filename = gold_csv_path.name
    errors = []
    df = None

    if not gold_csv_path.exists():
        errors.append({
            "filename": fallback_filename,
            "row_number": HEADER_ROW_NUMBER,
            "error_details": f"Gold CSV not found at {gold_csv_path}",
        })
    else:
        try:
            # Keep values as text so formatting errors are checked explicitly.
            df = pd.read_csv(gold_csv_path, dtype=str, keep_default_na=False)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, UnicodeError) as error:
            errors.append({
                "filename": fallback_filename,
                "row_number": HEADER_ROW_NUMBER,
                "error_details": f"Could not read Gold CSV: {error}",
            })

    if df is not None:
        errors.extend(validate_gold_dataframe(df, fallback_filename))

    if errors:
        for err in errors:
            logger.warning(f"VALIDATION: {err['filename']}, row {err['row_number']}: {err['error_details']}")
    else:
        row_count = len(df) if df is not None else 0
        logger.info(f"VALIDATION: all checks passed ({row_count} rows)")

    return errors


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()

    base_dir = Path(__file__).resolve().parent.parent
    gold_csv = base_dir / "data/cases_gold/caseloads_normalized.csv"

    errors = validate_gold_csv(gold_csv)
    write_error_report(errors, base_dir / "data/validation/errors.csv")
    exit(1 if errors else 0)
