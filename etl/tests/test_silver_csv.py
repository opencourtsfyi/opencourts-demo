import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from pdf_extraction import SILVER_COLUMNS, extract_pdfs_to_silver
from normalize_parquets import normalize_silver_to_gold

REPORT_PDF = "estate_monthly_caseload_2023_to_2024_bronze.pdf"
REPORT_CSV = "estate_monthly_caseload_2023_to_2024_bronze.csv"
EMPTY_PDF = "estate_monthly_caseload_2022_to_2023_bronze.pdf"
EMPTY_CSV = "estate_monthly_caseload_2022_to_2023_bronze.csv"

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


class FakePage:
    def __init__(self, table):
        self._table = table

    def extract_table(self):
        return self._table


class FakePDF:
    def __init__(self, tables):
        self.pages = [FakePage(table) for table in tables]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def install_tables(monkeypatch, tables_by_name):
    def open_pdf(path):
        return FakePDF(tables_by_name[Path(path).name])

    monkeypatch.setattr("pdf_extraction.pdfplumber.open", open_pdf)


def write_pdfs(directory, names):
    directory.mkdir(parents=True)
    for name in names:
        (directory / name).write_bytes(b"%PDF")


def read_provenance(provenance_dir):
    log_path = provenance_dir / "provenance_log.jsonl"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_silver_csv_preserves_cell_text(tmp_path, monkeypatch):
    bronze = tmp_path / "bronze"
    silver = tmp_path / "silver"
    provenance = tmp_path / "provenance"
    write_pdfs(bronze, [REPORT_PDF])
    install_tables(monkeypatch, {REPORT_PDF: [REPORT_TABLE]})

    extract_pdfs_to_silver(bronze, silver, provenance)

    csv_path = silver / REPORT_CSV
    assert csv_path.is_file()
    text = csv_path.read_text(encoding="utf-8")
    assert text.startswith(",".join(SILVER_COLUMNS))

    stored = pd.read_csv(csv_path, encoding="utf-8")
    restored = [json.loads(value) for value in stored["raw_row"]]
    assert restored == REPORT_TABLE

    records = read_provenance(provenance)
    assert records[0]["stage"] == "silver"
    assert records[0]["filename"] == REPORT_CSV
    assert records[0]["derived_from"] == [REPORT_PDF]


def test_pdf_without_tables_writes_header_and_provenance(tmp_path, monkeypatch):
    bronze = tmp_path / "bronze"
    silver = tmp_path / "silver"
    provenance = tmp_path / "provenance"
    write_pdfs(bronze, [EMPTY_PDF])
    install_tables(monkeypatch, {EMPTY_PDF: [None]})

    extract_pdfs_to_silver(bronze, silver, provenance)

    header = (silver / EMPTY_CSV).read_text(encoding="utf-8").strip()
    assert header == ",".join(SILVER_COLUMNS)
    records = read_provenance(provenance)
    assert records[0]["filename"] == EMPTY_CSV
    assert records[0]["derived_from"] == [EMPTY_PDF]


def test_normalize_reads_silver_csv_not_parquet(tmp_path, monkeypatch):
    bronze = tmp_path / "bronze"
    silver = tmp_path / "silver"
    gold = tmp_path / "gold"
    provenance = tmp_path / "provenance"
    write_pdfs(bronze, [EMPTY_PDF, REPORT_PDF])
    install_tables(monkeypatch, {EMPTY_PDF: [None], REPORT_PDF: [REPORT_TABLE]})
    extract_pdfs_to_silver(bronze, silver, provenance)
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
