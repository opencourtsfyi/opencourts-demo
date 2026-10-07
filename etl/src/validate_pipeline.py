# validate_pipeline.py
"""
Validation stage: sanity-checks the Gold CSV after the pipeline runs, to
catch a broken or malformed output before anyone downstream trusts it.
Run standalone for a quick check, or as the orchestrator's final step.
"""

from pathlib import Path
import pandas as pd

from normalize_parquets import CATEGORY, SC_COUNTIES, EXPECTED_METRICS, EXPECTED_METRICS_MENTAL_HEALTH, SCHEMA


def validate_gold_csv(gold_csv_path, error_report_path=None, logger=None):
    """Validate the Gold CSV and write a CSV report for each detected error."""
    issues = []
    errors = []
    gold_csv_path = Path(gold_csv_path)
    if error_report_path is None:
        error_report_path = Path(__file__).resolve().parent / "data/validation/errors.csv"
    error_report_path = Path(error_report_path)

    def add_error(details, row_number=1, row=None):
        filename = gold_csv_path.name
        if row is not None and "file" in row and pd.notna(row["file"]) and row["file"] != "":
            filename = str(row["file"])
        issues.append(f"{filename}, row {row_number}: {details}")
        errors.append({
            "filename": filename,
            "row_number": row_number,
            "error_details": details,
        })

    df = None
    if not gold_csv_path.exists():
        add_error(f"Gold CSV not found at {gold_csv_path}")
    else:
        try:
            # Keep values as text so formatting errors are checked explicitly.
            df = pd.read_csv(gold_csv_path, dtype=str, keep_default_na=False)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, UnicodeError) as error:
            add_error(f"Could not read Gold CSV: {error}")

    if df is not None:
        if df.empty:
            add_error("Gold CSV is empty")

        if list(df.columns) != SCHEMA:
            add_error(f"Column mismatch. Expected {SCHEMA}, got {list(df.columns)}")

        for index, (_, row) in enumerate(df.iterrows()):
            row_number = index + 2
            if row.eq("").all():
                add_error("Found fully-null row", row_number, row)

            if "category" in df.columns and row["category"] not in CATEGORY:
                add_error(f"Unrecognized category value: {row['category']!r}", row_number, row)

            if "county" in df.columns and row["county"] not in SC_COUNTIES:
                add_error(f"Unrecognized county value: {row['county']!r}", row_number, row)

            if "month" in df.columns:
                try:
                    month = int(row["month"])
                    if not 1 <= month <= 12:
                        raise ValueError
                except (ValueError, TypeError):
                    add_error(f"Invalid month value {row['month']!r}; expected an integer from 1 to 12", row_number, row)

            if "year" in df.columns:
                try:
                    year = int(row["year"])
                    if not 2007 <= year <= 2100:
                        raise ValueError
                except (ValueError, TypeError):
                    add_error(f"Invalid year value {row['year']!r}; expected an integer from 2007 to 2100", row_number, row)

            if "category" in df.columns and "metric" in df.columns:
                category = row["category"]
                metric = row["metric"]
                
                # Only check the metric if the category is actually recognized. 
                # Otherwise, it produces a redundant error on top of the category error.
                if category in CATEGORY:
                    if category in ("Estate", "Guardian", "Conservator"):
                        metric_is_valid = metric in EXPECTED_METRICS
                    elif category == "Mental Health":
                        metric_is_valid = metric in EXPECTED_METRICS_MENTAL_HEALTH
                    else:
                        metric_is_valid = False
                    
                    if not metric_is_valid:
                        add_error(f"Metric {metric!r} does not match category {category!r}", row_number, row)

            if "value" in df.columns:
                value = row["value"]
                try:
                    int(value)
                    value_is_valid = True
                except (ValueError, TypeError):
                    value_is_valid = value in ("DNR", "TI", "")
                if not value_is_valid:
                    add_error(f"Invalid value {value!r}; expected an integer, blank, 'DNR', or 'TI'", row_number, row)

        duplicate_keys = ["file", "category", "month", "year", "county", "metric"]
        if all(column in df.columns for column in duplicate_keys):
            duplicates = df[df.duplicated(subset=duplicate_keys, keep=False)]
            for index, row in duplicates.iterrows():
                add_error(
                    "Duplicate data point for file/category/month/year/county/metric",
                    index + 2,
                    row,
                )

    error_report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(errors, columns=["filename", "row_number", "error_details"]).to_csv(
        error_report_path,
        index=False,
    )

    if logger:
        if issues:
            for issue in issues:
                logger.warning(f"VALIDATION: {issue}")
        else:
            row_count = len(df) if df is not None else 0
            logger.info(f"VALIDATION: all checks passed ({row_count} rows)")

    return issues


if __name__ == "__main__":
    from logging_config import get_logger

    base_dir = Path(__file__).parent
    gold_csv = base_dir / "data/cases_gold/caseloads_normalized.csv"
    logger = get_logger(__name__, log_dir=base_dir / "data/logs")

    issues = validate_gold_csv(gold_csv, logger=logger)
    # Non-zero exit code lets this be used as a CI/CD gate later (e.g. Issue 19's QA pipeline)
    exit(1 if issues else 0)
