import pandas as pd
from pathlib import Path
import pytest

from normalize_parquets import SCHEMA
from validate_pipeline import validate_gold_csv


@pytest.fixture
def clean_gold_data():
    return pd.DataFrame(
        [["source.pdf", "Estate", "7", "2024", "Aiken", "Added", "12"]],
        columns=SCHEMA,
    )


@pytest.fixture
def dirty_gold_data():
    return pd.DataFrame(
        [
            ["category-source.pdf", "Unknown", "7", "2024", "Aiken", "Added", "5"],
            ["county-source.pdf", "Estate", "7", "2024", "Atlantis", "Added", "5"],
            ["month-source.pdf", "Estate", "13", "2024", "Aiken", "Added", "5"],
            ["year-source.pdf", "Estate", "7", "not-a-year", "Aiken", "Added", "5"],
            ["metric-source.pdf", "Estate", "7", "2024", "Aiken", "Orders", "5"],
            ["value-source.pdf", "Estate", "7", "2024", "Aiken", "Added", "many"],
            ["duplicate-source.pdf", "Estate", "7", "2024", "Aiken", "Added", "5"],
            ["duplicate-source.pdf", "Estate", "7", "2024", "Aiken", "Added", "6"],
        ],
        columns=SCHEMA,
    )


def write_gold_data(data, path):
    data.to_csv(path, index=False)
    return path


def test_clean_data_creates_empty_error_report(tmp_path, clean_gold_data):
    gold_path = write_gold_data(clean_gold_data, tmp_path / "gold.csv")
    report_path = Path(__file__).parent.parent / "src/data/validation/errors.csv"

    assert validate_gold_csv(gold_path) == []

    report = pd.read_csv(report_path)
    assert list(report.columns) == ["filename", "row_number", "error_details"]
    assert report.empty


def test_dirty_data_reports_each_offending_row(tmp_path, dirty_gold_data):
    gold_path = write_gold_data(dirty_gold_data, tmp_path / "gold.csv")
    report_path = Path(__file__).parent.parent / "src/data/validation/errors.csv"

    issues = validate_gold_csv(gold_path)
    report = pd.read_csv(report_path, dtype=str)

    assert issues
    assert list(report.columns) == ["filename", "row_number", "error_details"]
    expected_rows = {
        ("category-source.pdf", "2", "Unrecognized category"),
        ("county-source.pdf", "3", "Unrecognized county"),
        ("month-source.pdf", "4", "Invalid month"),
        ("year-source.pdf", "5", "Invalid year"),
        ("metric-source.pdf", "6", "does not match category"),
        ("value-source.pdf", "7", "Invalid value"),
        ("duplicate-source.pdf", "8", "Duplicate data point"),
        ("duplicate-source.pdf", "9", "Duplicate data point"),
    }
    actual_rows = {
        (row.filename, row.row_number, row.error_details)
        for row in report.itertuples(index=False)
    }
    for filename, row_number, detail in expected_rows:
        assert any(
            actual_filename == filename
            and actual_row_number == row_number
            and detail in actual_details
            for actual_filename, actual_row_number, actual_details in actual_rows
        )


def test_clean_run_overwrites_previous_errors(tmp_path, dirty_gold_data, clean_gold_data):
    gold_path = tmp_path / "gold.csv"
    report_path = Path(__file__).parent.parent / "src/data/validation/errors.csv"
    write_gold_data(dirty_gold_data, gold_path)
    validate_gold_csv(gold_path)
    assert len(pd.read_csv(report_path)) > 0

    write_gold_data(clean_gold_data, gold_path)
    assert validate_gold_csv(gold_path) == []

    report = pd.read_csv(report_path)
    assert list(report.columns) == ["filename", "row_number", "error_details"]
    assert report.empty