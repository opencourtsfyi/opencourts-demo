import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from normalize import normalize_silver_to_gold


REPORT_CSV = "estate_monthly_caseload_2023_to_2024_bronze.csv"
EMPTY_CSV = "estate_monthly_caseload_2022_to_2023_bronze.csv"
SILVER_COLUMNS = ("table_index", "row_index", "raw_row")

REPORT_TABLE = [
    [
        "South Carolina Court Administration\nEstate Monthly Caseload Report\nPeriod",
        None,
        "",
        'say "hi"',
    ],
    [None, None, "July", "January"],
    ["Abbeville", None, None, None],
    ["Pending first of month", "line\nbreak", "1,086", "5"],
]


def write_silver_csv(directory, name, rows):
    directory.mkdir(parents=True, exist_ok=True)
    records = [
        {"table_index": 1, "row_index": index, "raw_row": json.dumps(row)}
        for index, row in enumerate(rows)
    ]
    pd.DataFrame(records, columns=SILVER_COLUMNS).to_csv(
        directory / name, index=False, encoding="utf-8"
    )


def read_provenance(provenance_dir):
    log_path = provenance_dir / "provenance_log.jsonl"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_normalize_reads_silver_csv_not_parquet(tmp_path):
    silver = tmp_path / "silver"
    gold = tmp_path / "gold"
    provenance = tmp_path / "provenance"
    write_silver_csv(silver, EMPTY_CSV, [])
    write_silver_csv(silver, REPORT_CSV, REPORT_TABLE)
    (silver / "estate_monthly_caseload_2021_to_2022_bronze.parquet").write_text("old", encoding="utf-8")

    result = normalize_silver_to_gold(silver, gold, provenance)

    assert result["file"].tolist() == [REPORT_CSV, REPORT_CSV]
    assert result["category"].tolist() == ["Estate", "Estate"]
    assert result["county"].tolist() == ["Abbeville", "Abbeville"]
    assert result["metric"].tolist() == ["Pending first of month", "Pending first of month"]
    assert result["month"].tolist() == [7, 1]
    assert result["year"].tolist() == [2023, 2024]
    assert result["value"].tolist() == ["1086", "5"]

    written = pq.read_table(gold / "caseloads_normalized.parquet").to_pandas()
    assert written["value"].tolist() == ["1086", "5"]
    assert written["month"].tolist() == [7, 1]

    gold_records = [record for record in read_provenance(provenance) if record["stage"] == "gold"]
    assert gold_records[0]["derived_from"] == [EMPTY_CSV, REPORT_CSV]
    assert "estate_monthly_caseload_2021_to_2022_bronze.parquet" not in gold_records[0]["derived_from"]


def test_normalize_silver_csv_pandas_na_safety(tmp_path):
    """Skip raw_row cells that pandas would treat as NA, instead of crashing in json.loads."""
    silver = tmp_path / "silver"
    gold = tmp_path / "gold"
    provenance = tmp_path / "provenance"
    silver.mkdir(parents=True)

    records = [
        {"table_index": 1, "row_index": 0, "raw_row": json.dumps(REPORT_TABLE[0])},
        {"table_index": 1, "row_index": 1, "raw_row": "null"},
        {"table_index": 1, "row_index": 2, "raw_row": "NA"},
        {"table_index": 1, "row_index": 3, "raw_row": ""},
        {"table_index": 1, "row_index": 4, "raw_row": json.dumps(REPORT_TABLE[1])},
        {"table_index": 1, "row_index": 5, "raw_row": json.dumps(REPORT_TABLE[2])},
        {"table_index": 1, "row_index": 6, "raw_row": json.dumps(REPORT_TABLE[3])},
    ]
    pd.DataFrame(records).to_csv(silver / REPORT_CSV, index=False, encoding="utf-8")

    result = normalize_silver_to_gold(silver, gold, provenance)

    assert result["value"].tolist() == ["1086", "5"]
