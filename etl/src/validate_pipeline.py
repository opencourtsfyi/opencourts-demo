# validate_pipeline.py
"""
Validation stage: sanity-checks the Gold CSV after the pipeline runs, to
catch a broken or malformed output before anyone downstream trusts it.
Run standalone for a quick check, or as the orchestrator's final step.
"""

from pathlib import Path
import pandas as pd

from normalize_parquets import CATEGORY, SC_COUNTIES, EXPECTED_METRICS, EXPECTED_METRICS_MENTAL_HEALTH, SCHEMA


def validate_gold_csv(gold_csv_path, logger=None):
    """Runs a series of structural and content checks against the Gold CSV.
    Returns a list of issue descriptions (empty list means all checks passed).
    """
    issues = []
    gold_csv_path = Path(gold_csv_path)

    if not gold_csv_path.exists():
        return [f"Gold CSV not found at {gold_csv_path}"]

    # dtype=str keeps every column as text so we can validate formatting
    # ourselves (e.g. catching non-numeric "value" entries) rather than
    # letting pandas silently coerce or error on read
    df = pd.read_csv(gold_csv_path, dtype=str)

    if df.empty:
        return ["Gold CSV is empty"]

    # --- Structural checks ---
    if list(df.columns) != SCHEMA:
        issues.append(f"Column mismatch. Expected {SCHEMA}, got {list(df.columns)}")

    if df.isnull().all(axis=1).any():
        issues.append("Found fully-null row(s)")

    # --- Content checks: every value should come from a known, canonical set ---
    bad_categories = set(df["category"].dropna()) - set(CATEGORY)
    if bad_categories:
        issues.append(f"Unrecognized category values: {bad_categories}")

    bad_counties = set(df["county"].dropna()) - set(SC_COUNTIES)
    if bad_counties:
        issues.append(f"Unrecognized county values: {bad_counties}")

    # Month/year should be valid integers within a sane range
    try:
        months = df["month"].astype(int)
        if not months.between(1, 12).all():
            issues.append("Found month values outside 1-12")
    except ValueError:
        issues.append("Month column contains non-integer values")

    try:
        years = df["year"].astype(int)
        if not years.between(2007, 2100).all():
            issues.append("Found year values outside expected range (2007-2100)")
    except ValueError:
        issues.append("Year column contains non-integer values")

    # A metric should only ever appear under the category it actually belongs to
    # (e.g. "Orders" should never show up under an "Estate" row)
    def metric_is_valid(row):
        if row["category"] in ("Estate", "Guardian", "Conservator"):
            return row["metric"] in EXPECTED_METRICS
        if row["category"] == "Mental Health":
            return row["metric"] in EXPECTED_METRICS_MENTAL_HEALTH
        return False

    invalid_metric_rows = df[~df.apply(metric_is_valid, axis=1)]
    if not invalid_metric_rows.empty:
        issues.append(f"{len(invalid_metric_rows)} row(s) have a metric that doesn't match their category")

    # Value should be numeric, or one of our two known placeholder strings
    def value_is_valid(v):
        if v in ("DNR", "TI", ""):
            return True
        try:
            int(v)
            return True
        except (ValueError, TypeError):
            return False

    invalid_values = df[~df["value"].apply(value_is_valid)]
    if not invalid_values.empty:
        issues.append(f"{len(invalid_values)} row(s) have a value that isn't numeric, "", DNR, or TI")

    # No two rows should describe the exact same data point — that would
    # indicate a row got processed twice (e.g. a bug in the state-machine loop)
    dupe_keys = ["file", "category", "month", "year", "county", "metric"]
    duplicates = df[df.duplicated(subset=dupe_keys, keep=False)]
    if not duplicates.empty:
        issues.append(f"{len(duplicates)} duplicate row(s) for the same file/category/month/year/county/metric")

    if logger:
        if issues:
            for issue in issues:
                logger.warning(f"VALIDATION: {issue}")
        else:
            logger.info(f"VALIDATION: all checks passed ({len(df)} rows)")

    return issues


if __name__ == "__main__":
    from logging_config import get_logger

    base_dir = Path(__file__).parent
    gold_csv = base_dir / "data/cases_gold/caseloads_normalized.csv"
    logger = get_logger(__name__, log_dir=base_dir / "data/logs")

    issues = validate_gold_csv(gold_csv, logger=logger)
    # Non-zero exit code lets this be used as a CI/CD gate later (e.g. Issue 19's QA pipeline)
    exit(1 if issues else 0)
