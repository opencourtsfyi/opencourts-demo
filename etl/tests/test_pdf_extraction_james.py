# TODO integrate James' tests
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

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
    """
    monkeypatch pdfplumber.open to return a FakePDF with the given tables.
    tables_by_name is a dict mapping PDF file names to lists of tables (or None for no tables).
    """
    def open_pdf(path):
        return FakePDF(tables_by_name[Path(path).name])

    monkeypatch.setattr(module.pdfplumber, "open", open_pdf)


def create_empty_pdfs(directory: Path, names: list[str]) -> None:
    """
    Helper function writes empty PDF files. To ensure content checkers allow the file,
    we write the PDF content type header into the top of the file and nothing else.

    directory: Path to the directory where the PDFs will be created.
    names: List of PDF file names to create.

    """
    directory.mkdir(parents=True)
    for name in names:
        # TODO shouldn't we use library to get the PDF content header?
        (directory / name).write_bytes(b"%PDF")


def read_provenance(provenance_dir):
    log_path = provenance_dir / "provenance_log.jsonl"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


#TODO test extract_pdfs_to_silver returns a list of Paths to the generated Silver files


def test_silver_csv_preserves_cell_text(tmp_path, monkeypatch, pdf_extraction):
    """
    Test that extract_pdfs_to_silver writes a CSV with the expected header and cell text, and that provenance is recorded correctly.
    """
    # Arrange
    REPORT_PDF = "estate_monthly_caseload_2023_to_2024_bronze.pdf"


    REPORT_CSV = "estate_monthly_caseload_2023_to_2024_bronze.csv"

    SILVER_COLUMNS = ["table_index", "row_index", "raw_row"]
    # Represent FakePDF with 4 FakePages which get created during install_tables() call
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

    bronze = tmp_path / "bronze"
    create_empty_pdfs(bronze, [REPORT_PDF])
    install_tables(monkeypatch, pdf_extraction, {REPORT_PDF: [REPORT_TABLE]})

    silver = tmp_path / "silver"
    provenance = tmp_path / "provenance"

    # Act
    pdf_extraction.extract_pdfs_to_silver(input_dir=bronze, output_dir=silver, provenance_dir=provenance)

    # Assert

    # Assert that the silver CSV exists and has the expected header and cell text
    csv_path = silver / REPORT_CSV
    assert csv_path.is_file()
    text = csv_path.read_text(encoding="utf-8")
    assert text.startswith(",".join(SILVER_COLUMNS))

    stored = pd.read_csv(csv_path, encoding="utf-8")
    restored = [json.loads(value) for value in stored["raw_row"]]
    assert restored == REPORT_TABLE

    # # Assert that provenance log contains a record for the silver CSV derived from the PDF
    records = read_provenance(provenance)
    assert records[0]["stage"] == "silver"
    assert records[0]["filename"] == REPORT_CSV
    assert records[0]["derived_from"] == [REPORT_PDF]


# def test_pdf_without_tables_writes_header_and_provenance(tmp_path, monkeypatch, pdf_extraction):
#     # Arrange
#     EMPTY_PDF = "estate_monthly_caseload_2022_to_2023_bronze.pdf"
#     EMPTY_CSV = "estate_monthly_caseload_2022_to_2023_bronze.csv"

#     bronze = tmp_path / "bronze"
#     silver = tmp_path / "silver"
#     provenance = tmp_path / "provenance"
#     create_empty_pdfs(bronze, [EMPTY_PDF])
#     install_tables(monkeypatch, pdf_extraction, {EMPTY_PDF: [None]})

#     # Act
#     pdf_extraction.extract_pdfs_to_silver(bronze, silver, provenance)

#     # Assert
#     header = (silver / EMPTY_CSV).read_text(encoding="utf-8").strip()
#     assert header == ",".join(pdf_extraction.SILVER_COLUMNS)
#     records = read_provenance(provenance)
#     assert records[0]["filename"] == EMPTY_CSV
#     assert records[0]["derived_from"] == [EMPTY_PDF]