import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import normalize_parquets as npq


def test_match_metric_handles_none_prefixes_and_unknown_values():
    assert npq.match_metric(None, {"pending first of month": "Pending first of month"}) is None
    assert npq.match_metric("Orders*", {"orders": "Orders"}) == "Orders"
    assert npq.match_metric("Pending first of month extra", {"pending first of month": "Pending first of month"}) == "Pending first of month"
    assert npq.match_metric("Unknown metric", {"pending first of month": "Pending first of month"}) is None


def test_normalize_silver_to_gold_handles_empty_input(tmp_path):
    input_dir = tmp_path / "silver"
    input_dir.mkdir()
    output_dir = tmp_path / "gold"
    provenance_dir = tmp_path / "provenance"

    result = npq.normalize_silver_to_gold(input_dir, output_dir, provenance_dir)

    assert result.empty
    assert (output_dir / "caseloads_normalized.csv").exists()
    assert (output_dir / "caseloads_normalized.parquet").exists()
    assert pd.read_csv(output_dir / "caseloads_normalized.csv").empty


def test_normalize_silver_to_gold_processes_title_header_county_and_metric_rows(tmp_path):
    input_dir = tmp_path / "silver"
    input_dir.mkdir()
    output_dir = tmp_path / "gold"
    provenance_dir = tmp_path / "provenance"

    raw_rows = [
        ["South Carolina Court Administration\nEstate Monthly Caseload Report\nPeriod 2023-2024", "", "", ""],
        ["", "", "July", "August"],
        ["", "", "", ""],
        ["Abbeville", "", "", ""],
        ["", "Pending first of month", "10", "20"],
        ["South Carolina Court Administration\nMental Health Monthly Caseload Report\nPeriod 2023-2024", "", "", ""],
        ["", "", "July", "August"],
        ["", "", "", ""],
        ["Aiken", "", "", ""],
        ["", "Orders*", "5", "7"],
    ]

    table = pa.Table.from_pandas(pd.DataFrame({"raw_row": raw_rows}), schema=pa.schema([("raw_row", pa.list_(pa.string()))]))
    pq.write_table(table, input_dir / "estate_2023_2024.parquet")

    result = npq.normalize_silver_to_gold(input_dir, output_dir, provenance_dir)

    assert len(result) == 4
    assert set(result["category"]) == {"Estate", "Mental Health"}
    assert set(result["metric"]) == {"Pending first of month", "Orders"}
    assert set(result["county"]) == {"Abbeville", "Aiken"}
    assert set(result["year"]) == {2023}
    assert (provenance_dir / "provenance_log.jsonl").exists()
