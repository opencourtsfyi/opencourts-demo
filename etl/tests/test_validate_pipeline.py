import pytest
import pandas as pd
from pathlib import Path

from validate_pipeline import validate_gold_csv, write_error_report
from normalize_parquets import SCHEMA

# The hardcoded path from our code
REPORT_PATH = Path(__file__).parent.parent / "src/data/validation/errors.csv"

def make_gold_row(**overrides):
    """Test Data Builder: sensible clean defaults, override only the field under test."""
    row = {
        "file": "source.pdf",
        "category": "Estate",
        "month": "7",
        "year": "2024",
        "county": "Aiken",
        "metric": "Added",
        "value": "12",
    }
    row.update(overrides)
    return row

def write_gold_data(data_list, path):
    df = pd.DataFrame(data_list, columns=SCHEMA)
    df.to_csv(path, index=False)
    return path

@pytest.mark.parametrize("invalid_field, override_val, expected_error", [
    ("category", "Unknown", "Unrecognized category"),
    ("county", "Atlantis", "Unrecognized county"),
    ("month", "13", "Invalid month"),
    ("year", "not-a-year", "Invalid year"),
    ("metric", "Orders", "does not match category"),
    ("value", "many", "Invalid value"),
    ("category", "", "Unrecognized category"),  # Tests keep_default_na=False behavior
])
def test_validation_flags_invalid_field(tmp_path, invalid_field, override_val, expected_error):
    # Given a dataset with exactly one deliberate defect
    gold_path = write_gold_data([make_gold_row(**{invalid_field: override_val})], tmp_path / "gold.csv")
    
    # When validated
    issues = validate_gold_csv(gold_path)
    
    # Then only that specific defect is reported
    assert len(issues) == 1
    assert expected_error in issues[0]
    
    # And the report CSV matches exactly
    report = pd.read_csv(REPORT_PATH, dtype=str)
    assert len(report) == 1
    assert expected_error in report.iloc[0]["error_details"]

def test_clean_run_creates_empty_report(tmp_path):
    gold_path = write_gold_data([make_gold_row()], tmp_path / "gold.csv")
    
    issues = validate_gold_csv(gold_path)
    assert len(issues) == 0
    
    report = pd.read_csv(REPORT_PATH, dtype=str)
    assert report.empty
    assert list(report.columns) == ["filename", "row_number", "error_details"]

# --- Edge Cases Requested by Reviewer ---

def test_missing_file():
    issues = validate_gold_csv("does_not_exist.csv")
    assert len(issues) == 1
    assert "not found" in issues[0]

def test_unreadable_file(tmp_path):
    bad_file = tmp_path / "bad.csv"
    bad_file.write_text("This is not a valid CSV \0 null bytes...")
    issues = validate_gold_csv(bad_file)
    assert len(issues) >= 1

def test_empty_file(tmp_path):
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")
    issues = validate_gold_csv(empty_file)
    assert any("Could not read" in issue or "empty" in issue for issue in issues)

def test_schema_mismatch(tmp_path):
    df = pd.DataFrame([{"wrong_col": "val"}])
    path = tmp_path / "bad_schema.csv"
    df.to_csv(path, index=False)
    
    issues = validate_gold_csv(path)
    assert any("Column mismatch" in issue for issue in issues)

def test_fully_blank_row(tmp_path):
    row = make_gold_row()
    blank_row = {k: "" for k in row.keys()}
    gold_path = write_gold_data([row, blank_row], tmp_path / "gold.csv")
    
    issues = validate_gold_csv(gold_path)
    assert any("fully-null row" in issue for issue in issues)

def test_write_error_report_overwrites(tmp_path):
    """Directly tests the separated file-writing helper."""
    report_path = tmp_path / "custom_errors.csv"
    
    # Write initial data
    write_error_report([{"filename": "a", "row_number": 1, "error_details": "err"}], report_path)
    assert len(pd.read_csv(report_path)) == 1
    
    # Write empty array (should overwrite file completely)
    write_error_report([], report_path)
    report = pd.read_csv(report_path)
    assert report.empty
    assert list(report.columns) == ["filename", "row_number", "error_details"]