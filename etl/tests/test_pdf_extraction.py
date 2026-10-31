import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


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


@pytest.fixture
def pdf_extraction(monkeypatch):
    """Install a pdfplumber stand-in for this test only.

    pdf_extraction imports pdfplumber at load time. The stand-in is removed
    when the test ends so later tests still see the real module if it is installed.
    """
    monkeypatch.setitem(sys.modules, "pdfplumber", MagicMock())
    sys.modules.pop("pdf_extraction", None)
    import pdf_extraction as module

    yield module
    sys.modules.pop("pdf_extraction", None)


def install_tables(monkeypatch, module, tables_by_name):
    def open_pdf(path):
        return FakePDF(tables_by_name[Path(path).name])

    monkeypatch.setattr(module.pdfplumber, "open", open_pdf)


def write_pdfs(directory, names):
    directory.mkdir(parents=True)
    for name in names:
        (directory / name).write_bytes(b"%PDF")


def read_provenance(provenance_dir):
    log_path = provenance_dir / "provenance_log.jsonl"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_silver_csv_preserves_cell_text(tmp_path, monkeypatch, pdf_extraction):
    bronze = tmp_path / "bronze"
    silver = tmp_path / "silver"
    provenance = tmp_path / "provenance"
    write_pdfs(bronze, [REPORT_PDF])
    install_tables(monkeypatch, pdf_extraction, {REPORT_PDF: [REPORT_TABLE]})

    pdf_extraction.extract_pdfs_to_silver(bronze, silver, provenance)

    csv_path = silver / REPORT_CSV
    assert csv_path.is_file()
    text = csv_path.read_text(encoding="utf-8")
    assert text.startswith(",".join(pdf_extraction.SILVER_COLUMNS))

    stored = pd.read_csv(csv_path, encoding="utf-8")
    restored = [json.loads(value) for value in stored["raw_row"]]
    assert restored == REPORT_TABLE

    records = read_provenance(provenance)
    assert records[0]["stage"] == "silver"
    assert records[0]["filename"] == REPORT_CSV
    assert records[0]["derived_from"] == [REPORT_PDF]


def test_pdf_without_tables_writes_header_and_provenance(tmp_path, monkeypatch, pdf_extraction):
    bronze = tmp_path / "bronze"
    silver = tmp_path / "silver"
    provenance = tmp_path / "provenance"
    write_pdfs(bronze, [EMPTY_PDF])
    install_tables(monkeypatch, pdf_extraction, {EMPTY_PDF: [None]})

    pdf_extraction.extract_pdfs_to_silver(bronze, silver, provenance)

    header = (silver / EMPTY_CSV).read_text(encoding="utf-8").strip()
    assert header == ",".join(pdf_extraction.SILVER_COLUMNS)
    records = read_provenance(provenance)
    assert records[0]["filename"] == EMPTY_CSV
    assert records[0]["derived_from"] == [EMPTY_PDF]
