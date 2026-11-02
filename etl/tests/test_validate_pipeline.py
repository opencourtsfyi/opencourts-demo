import pytest
import pandas as pd
from pydantic import ValidationError
from pathlib import Path

from validate_pipeline import GoldRow, validate_gold_csv, validate_gold_dataframe, write_error_report
from normalize import SCHEMA

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
    ("category", "", "Unrecognized category"),
])
def test_validation_flags_invalid_field(tmp_path, invalid_field, override_val, expected_error):
    gold_path = write_gold_data([make_gold_row(**{invalid_field: override_val})], tmp_path / "gold.csv")
    errors = validate_gold_csv(gold_path)
    
    assert len(errors) == 1
    assert expected_error in errors[0]["error_details"]

@pytest.mark.parametrize("allowed_value", ["DNR", "TI", "N/A", ""])
def test_non_numeric_placeholder_values_are_valid(tmp_path, allowed_value):
    gold_path = write_gold_data([make_gold_row(value=allowed_value)], tmp_path / "gold.csv")
    assert validate_gold_csv(gold_path) == []

def test_clean_run_creates_empty_report(tmp_path):
    gold_path = write_gold_data([make_gold_row()], tmp_path / "gold.csv")
    errors = validate_gold_csv(gold_path)
    assert len(errors) == 0

def test_missing_file():
    errors = validate_gold_csv("does_not_exist.csv")
    assert len(errors) == 1
    assert "not found" in errors[0]["error_details"]

def test_unreadable_file(tmp_path):
    bad_file = tmp_path / "bad.csv"
    # To force a Pandas ParserError
    bad_file.write_text("A,B\n1,2,3\n4,5,6,7\n")
    
    errors = validate_gold_csv(bad_file)
    assert any("Could not read" in e["error_details"] for e in errors)

def test_empty_file(tmp_path):
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")
    errors = validate_gold_csv(empty_file)
    assert any("Could not read" in e["error_details"] or "empty" in e["error_details"] for e in errors)

def test_schema_mismatch(tmp_path):
    df = pd.DataFrame([{"wrong_col": "val"}])
    path = tmp_path / "bad_schema.csv"
    df.to_csv(path, index=False)
    errors = validate_gold_csv(path)
    assert any("Column mismatch" in e["error_details"] for e in errors)

def test_fully_blank_row(tmp_path):
    row = make_gold_row()
    blank_row = {k: "" for k in row.keys()}
    gold_path = write_gold_data([row, blank_row], tmp_path / "gold.csv")
    errors = validate_gold_csv(gold_path)
    assert any("fully-null row" in e["error_details"] for e in errors)

def test_duplicate_rows(tmp_path):
    row1 = make_gold_row(value="1")
    row2 = make_gold_row(value="2")
    gold_path = write_gold_data([row1, row2], tmp_path / "gold.csv")
    
    errors = validate_gold_csv(gold_path)
    dup_errors = [e for e in errors if "Duplicate data point" in e["error_details"]]
    assert len(dup_errors) == 2
    assert dup_errors[0]["row_number"] == 2
    assert dup_errors[1]["row_number"] == 3

def test_write_error_report_overwrites(tmp_path):
    report_path = tmp_path / "custom_errors.csv"
    write_error_report([{"filename": "a", "row_number": 1, "error_details": "err"}], report_path)
    assert len(pd.read_csv(report_path)) == 1
    
    write_error_report([], report_path)
    report = pd.read_csv(report_path)
    assert report.empty

def row_messages(row):
    with pytest.raises(ValidationError) as exc_info:
        GoldRow.model_validate(row)
    return [err["msg"].removeprefix("Value error, ") for err in exc_info.value.errors()]

def test_gold_row_skips_metric_error_when_category_is_unrecognized():
    messages = row_messages(make_gold_row(category="Unknown", metric="Bogus"))
    assert messages == ["Unrecognized category value: 'Unknown'"]

def test_gold_row_checks_metric_even_when_other_fields_fail():
    messages = row_messages(make_gold_row(county="Atlantis", metric="Bogus"))
    assert "Metric 'Bogus' does not match category 'Estate'" in messages
    assert "Unrecognized county value: 'Atlantis'" in messages

def test_validate_gold_dataframe_flags_duplicates_in_memory():
    df = pd.DataFrame([make_gold_row(), make_gold_row()], columns=SCHEMA)
    errors = validate_gold_dataframe(df, "gold.csv")
    assert [e["row_number"] for e in errors] == [2, 3]
    assert all(e["filename"] == "source.pdf" for e in errors)
