import pandas as pd
import pyarrow.parquet as pq

import pdf_extraction


def test_extract_pdfs_to_silver_handles_blank_pages_and_writes_provenance(tmp_path, monkeypatch):
    input_dir = tmp_path / "bronze"
    input_dir.mkdir()
    pdf_path = input_dir / "sample_2023_2024.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    class FakePage:
        def __init__(self, table_data):
            self._table_data = table_data

        def extract_table(self):
            return self._table_data

    class FakePdf:
        def __init__(self, pages):
            self.pages = pages

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    fake_pdf = FakePdf([
        FakePage(None),
        FakePage([["A", "B"], ["1", "2"]]),
    ])

    monkeypatch.setattr(pdf_extraction.pdfplumber, "open", lambda _path: fake_pdf)

    output_dir = tmp_path / "silver"
    provenance_dir = tmp_path / "provenance"
    pdf_extraction.extract_pdfs_to_silver(input_dir, output_dir, provenance_dir)

    output_file = output_dir / "sample_2023_2024.parquet"
    assert output_file.exists()

    df = pq.read_table(output_file).to_pandas()
    assert len(df) == 2
    assert list(df.columns) == ["table_index", "row_index", "raw_row"]
    assert (provenance_dir / "provenance_log.jsonl").exists()


def test_extract_pdfs_to_silver_handles_empty_input_directory(tmp_path):
    input_dir = tmp_path / "bronze"
    input_dir.mkdir()
    output_dir = tmp_path / "silver"
    provenance_dir = tmp_path / "provenance"

    pdf_extraction.extract_pdfs_to_silver(input_dir, output_dir, provenance_dir)

    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []
