import logging

import pandas as pd

from normalize_parquets import SCHEMA
from validate_pipeline import validate_gold_csv


def _write_csv(tmp_path, rows, columns=SCHEMA):
    df = pd.DataFrame(rows, columns=columns)
    path = tmp_path / "gold.csv"
    df.to_csv(path, index=False)
    return path


def test_validate_gold_csv_missing_file(tmp_path):
    missing = tmp_path / "does-not-exist.csv"

    assert validate_gold_csv(missing) == [f"Gold CSV not found at {missing}"]


def test_validate_gold_csv_empty_csv(tmp_path):
    empty_csv = _write_csv(tmp_path, [], columns=SCHEMA)

    assert validate_gold_csv(empty_csv) == ["Gold CSV is empty"]


def test_validate_gold_csv_valid_csv_logs_success(tmp_path, caplog):
    rows = [
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "1",
            "year": "2024",
            "county": "Abbeville",
            "metric": "Added",
            "value": "DNR",
        },
        {
            "file": "report.csv",
            "category": "Mental Health",
            "month": "2",
            "year": "2024",
            "county": "Aiken",
            "metric": "Orders",
            "value": "TI",
        },
    ]
    valid_csv = _write_csv(tmp_path, rows)
    logger = logging.getLogger("validate_gold_csv_valid")

    with caplog.at_level(logging.INFO, logger=logger.name):
        issues = validate_gold_csv(valid_csv, logger=logger)

    assert issues == []
    assert "VALIDATION: all checks passed" in caplog.text


def test_validate_gold_csv_detects_full_null_and_content_issues(tmp_path):
    rows = [
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "1",
            "year": "2024",
            "county": "Abbeville",
            "metric": "Pending first of month",
            "value": "10",
        },
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "1",
            "year": "2024",
            "county": "Abbeville",
            "metric": "Pending first of month",
            "value": "10",
        },
        {
            "file": "report.csv",
            "category": "BadCategory",
            "month": "2",
            "year": "2024",
            "county": "Abbeville",
            "metric": "Added",
            "value": "5",
        },
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "2",
            "year": "2024",
            "county": "BadCounty",
            "metric": "Added",
            "value": "7",
        },
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "3",
            "year": "2024",
            "county": "Abbeville",
            "metric": "BadMetric",
            "value": "11",
        },
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "4",
            "year": "2024",
            "county": "Abbeville",
            "metric": "Added",
            "value": "oops",
        },
        {"file": None, "category": None, "month": None, "year": None, "county": None, "metric": None, "value": None},
    ]
    csv_path = _write_csv(tmp_path, rows, columns=SCHEMA + ["extra"])

    issues = validate_gold_csv(csv_path)

    assert any("Column mismatch" in issue for issue in issues)
    assert any("Found fully-null row(s)" in issue for issue in issues)
    assert any("Unrecognized category values" in issue for issue in issues)
    assert any("Unrecognized county values" in issue for issue in issues)
    assert any("row(s) have a metric that doesn't match their category" in issue for issue in issues)
    assert any("row(s) have a value that isn't numeric" in issue for issue in issues)
    assert any("duplicate row(s)" in issue for issue in issues)


def test_validate_gold_csv_detects_invalid_month_and_year_ranges(tmp_path):
    rows = [
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "13",
            "year": "2024",
            "county": "Abbeville",
            "metric": "Added",
            "value": "5",
        },
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "1",
            "year": "3000",
            "county": "Aiken",
            "metric": "Disposed",
            "value": "9",
        },
    ]
    csv_path = _write_csv(tmp_path, rows)

    issues = validate_gold_csv(csv_path)

    assert any("Found month values outside 1-12" in issue for issue in issues)
    assert any("Found year values outside expected range (2007-2100)" in issue for issue in issues)


def test_validate_gold_csv_flags_non_integer_month_and_year(tmp_path, caplog):
    rows = [
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "abc",
            "year": "2024",
            "county": "Abbeville",
            "metric": "Added",
            "value": "1",
        },
        {
            "file": "report.csv",
            "category": "Estate",
            "month": "1",
            "year": "def",
            "county": "Aiken",
            "metric": "Disposed",
            "value": "2",
        },
    ]
    csv_path = _write_csv(tmp_path, rows)
    logger = logging.getLogger("validate_gold_csv_warning")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        issues = validate_gold_csv(csv_path, logger=logger)

    assert any("Month column contains non-integer values" in issue for issue in issues)
    assert any("Year column contains non-integer values" in issue for issue in issues)
    assert "VALIDATION: Month column contains non-integer values" in caplog.text
    assert "VALIDATION: Year column contains non-integer values" in caplog.text
