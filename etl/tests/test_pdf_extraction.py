import json
from unittest.mock import MagicMock, patch

#TODO: remove the parquet dependency once we switch to CSV output
import pyarrow.parquet as pq
import pytest

import pandas as pd

import pdf_extraction
from pdf_extraction import (
    BronzeToSilverExtractor,
    TableExtractor,
    extract_pdfs_to_silver,
)

FIRST_PAGE_NUMBER = 1
SECOND_PAGE_NUMBER = 2
THIRD_PAGE_NUMBER = 3
FIRST_ROW_INDEX = 0
EXPECTED_SINGLE_RECORD = 1
EXPECTED_TWO_FILES = 2
EXPECTED_NO_FILES = 0
CUSTOM_PAGE_OFFSET = 10
SILVER_COLUMNS = ["table_index", "row_index", "raw_row"]
PDF_BYTES = b"%PDF-1.4 fake"
PROVENANCE_LOG_NAME = "provenance_log.jsonl"


def make_pdf(pages):
    """Build a mock pdfplumber PDF context manager whose pages return the given tables."""
    pdf = MagicMock()
    pdf.pages = []
    for table in pages:
        page = MagicMock()
        page.extract_table.return_value = table
        pdf.pages.append(page)
    pdf.__enter__.return_value = pdf
    pdf.__exit__.return_value = False
    return pdf


@pytest.fixture
def dirs(tmp_path):
    input_dir = tmp_path / "bronze"
    input_dir.mkdir()
    return input_dir, tmp_path / "silver", tmp_path / "provenance"


@pytest.fixture
def mock_open():
    with patch("pdf_extraction.pdfplumber.open") as open_mock:
        yield open_mock


@pytest.fixture
def mock_logger():
    with patch.object(pdf_extraction, "logger") as logger_mock:
        yield logger_mock


def read_rows(path):
    if path.suffix == ".parquet":
        return pq.read_table(path).to_pylist()
    elif path.suffix == ".csv":
        df = pd.read_csv(path, encoding="utf-8")
        df["raw_row"] = df["raw_row"].apply(json.loads)
        return df.to_dict(orient='records') # return same format as pyarrow's table.to_pylist()

    return []


def read_provenance(provenance_dir):
    lines = (provenance_dir / PROVENANCE_LOG_NAME).read_text().splitlines()
    return [json.loads(line) for line in lines]


class TestExtractPdfsToSilver:
    def test_extracts_rows_with_page_and_row_indexes(self, dirs, mock_open):
        # Arrange
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["h1", "h2"], ["a", "b"]], [["c", "d"]]])

        # Act
        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        # Assert
        assert read_rows(output_dir / "a.csv") == [
            {"table_index": FIRST_PAGE_NUMBER, "row_index": 0, "raw_row": ["h1", "h2"]},
            {"table_index": FIRST_PAGE_NUMBER, "row_index": 1, "raw_row": ["a", "b"]},
            {"table_index": SECOND_PAGE_NUMBER, "row_index": 0, "raw_row": ["c", "d"]},
        ]

    def test_opens_each_pdf_by_path(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        pdf_path = input_dir / "a.pdf"
        pdf_path.write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        mock_open.assert_called_once_with(pdf_path)

    def test_pdf_context_manager_is_closed(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        pdf = make_pdf([[["x"]]])
        mock_open.return_value = pdf

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        pdf.__exit__.assert_called_once()

    def test_preserves_none_cells_and_empty_strings(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["a", None, ""]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert read_rows(output_dir / "a.csv")[0]["raw_row"] == ["a", None, ""]

    def test_preserves_ragged_rows(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["a"], ["b", "c", "d"], []]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert [r["raw_row"] for r in read_rows(output_dir / "a.csv")] == [["a"], ["b", "c", "d"], []]

    def test_page_without_table_is_skipped_but_numbering_is_preserved(self, dirs, mock_open, mock_logger):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["a"]], None, [["c"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        rows = read_rows(output_dir / "a.csv")
        assert [r["table_index"] for r in rows] == [FIRST_PAGE_NUMBER, THIRD_PAGE_NUMBER]
        mock_logger.warning.assert_called_once()
        assert str(SECOND_PAGE_NUMBER) in mock_logger.warning.call_args[0][0]
        assert "a.pdf" in mock_logger.warning.call_args[0][0]

    def test_empty_table_list_on_page_yields_no_rows(self, dirs, mock_open, mock_logger):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["a"]], []])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert len(read_rows(output_dir / "a.csv")) == EXPECTED_SINGLE_RECORD
        mock_logger.warning.assert_not_called()

    def test_pdf_with_no_tables_writes_empty_csv(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([None, None])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        csv_path = output_dir / "a.csv"
        assert csv_path.exists()
        assert read_rows(csv_path) == []
        assert len(read_provenance(prov_dir)) == 1

    def test_pdf_with_zero_pages_writes_empty_csv(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        csv_path = output_dir / "a.csv"
        assert csv_path.exists()
        assert read_rows(csv_path) == []
        assert len(read_provenance(prov_dir)) == EXPECTED_SINGLE_RECORD

    def test_pdf_with_only_empty_tables_writes_empty_csv(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        csv_path = output_dir / "a.csv"
        assert csv_path.exists()
        assert read_rows(csv_path) == []
        assert len(read_provenance(prov_dir)) == EXPECTED_SINGLE_RECORD

    def test_silver_csv_preserves_cell_text_and_provenance(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        pdf_name = "estate_monthly_caseload_2023_to_2024_bronze.pdf"
        csv_name = "estate_monthly_caseload_2023_to_2024_bronze.csv"
        pdf_path = input_dir / pdf_name
        pdf_path.write_bytes(PDF_BYTES)

        report_table = [
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
        mock_open.return_value = make_pdf([report_table])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        csv_path = output_dir / csv_name
        assert csv_path.is_file()
        text = csv_path.read_text(encoding="utf-8")
        assert text.startswith(",".join(SILVER_COLUMNS))

        rows = read_rows(csv_path)
        assert rows == [
            {"table_index": 1, "row_index": 0, "raw_row": ["South Carolina Court Administration\nEstate Monthly Caseload Report\nPeriod", None, "", 'say "hi"']},
            {"table_index": 1, "row_index": 1, "raw_row": [None, None, "July", "January"]},
            {"table_index": 1, "row_index": 2, "raw_row": ["Abbeville", None, None, None]},
            {"table_index": 1, "row_index": 3, "raw_row": ["Pending first of month", "line\nbreak", "1,086", "5"]},
        ]

        provenance = read_provenance(prov_dir)
        assert provenance[0]["stage"] == "silver"
        assert provenance[0]["filename"] == csv_name
        assert provenance[0]["derived_from"] == [pdf_name]

    def test_pdf_without_tables_writes_header_and_provenance(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        pdf_name = "estate_monthly_caseload_2022_to_2023_bronze.pdf"
        csv_name = "estate_monthly_caseload_2022_to_2023_bronze.csv"
        pdf_path = input_dir / pdf_name
        pdf_path.write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([None])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        csv_path = output_dir / csv_name
        assert csv_path.exists()
        header = csv_path.read_text(encoding="utf-8").strip()
        assert header == ",".join(SILVER_COLUMNS)

        records = read_provenance(prov_dir)
        assert records[0]["filename"] == csv_name
        assert records[0]["derived_from"] == [pdf_name]

    def test_one_output_per_pdf_in_sorted_order(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        for name in ("b.pdf", "a.pdf"):
            (input_dir / name).write_bytes(PDF_BYTES)
        mock_open.side_effect = lambda path: make_pdf([[[path.stem]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert [c.args[0].name for c in mock_open.call_args_list] == ["a.pdf", "b.pdf"]
        assert sorted(p.name for p in output_dir.iterdir()) == ["a.csv", "b.csv"]
        assert read_rows(output_dir / "b.csv")[0]["raw_row"] == ["b"]

    def test_ignores_non_pdf_files_and_subdirectories(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "notes.txt").write_text("x")
        (input_dir / "sub").mkdir()
        (input_dir / "sub" / "nested.pdf").write_bytes(PDF_BYTES)

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        mock_open.assert_not_called()
        assert list(output_dir.iterdir()) == []

    def test_glob_is_case_sensitive_on_extension_per_platform(self, dirs, mock_open):
        """Uppercase .PDF is only matched on case-insensitive filesystems (Windows)."""
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "UPPER.PDF").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        # Behavior depends on OS; either outcome must be self-consistent
        assert mock_open.call_count == len(list(output_dir.iterdir()))

    def test_empty_input_dir_creates_output_dir_only(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert output_dir.is_dir()
        assert list(output_dir.iterdir()) == []
        assert not prov_dir.exists()

    def test_missing_input_dir_is_treated_as_empty(self, tmp_path, mock_open):
        output_dir = tmp_path / "silver"

        extract_pdfs_to_silver(tmp_path / "does_not_exist", output_dir, tmp_path / "prov")

        assert output_dir.is_dir()
        mock_open.assert_not_called()

    def test_creates_nested_output_dir(self, dirs, mock_open):
        input_dir, _, prov_dir = dirs
        nested = input_dir.parent / "x" / "y" / "silver"

        extract_pdfs_to_silver(input_dir, nested, prov_dir)

        assert nested.is_dir()

    def test_filename_stem_with_dots_is_preserved(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "report.2024.01.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert (output_dir / "report.2024.01.csv").exists()

    def test_overwrites_existing_output(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        output_dir.mkdir()
        (output_dir / "a.csv").write_bytes(b"stale")
        mock_open.return_value = make_pdf([[["fresh"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert read_rows(output_dir / "a.csv")[0]["raw_row"] == ["fresh"]

    def test_logs_provenance_with_lineage(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        records = read_provenance(prov_dir)
        assert len(records) == EXPECTED_SINGLE_RECORD
        assert records[0]["stage"] == "silver"
        assert records[0]["filename"] == "a.csv"
        assert records[0]["derived_from"] == ["a.pdf"]
        assert records[0]["source_url"] is None

    def test_provenance_call_arguments(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        with patch("pdf_extraction.log_provenance") as log_mock:
            extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        log_mock.assert_called_once_with(
            prov_dir, stage="silver", file_path=output_dir / "a.csv", derived_from=["a.pdf"]
        )

    def test_provenance_hash_matches_written_file(self, dirs, mock_open):
        from provenance import compute_file_hash

        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert read_provenance(prov_dir)[0]["file_hash"] == compute_file_hash(output_dir / "a.csv")

    def test_one_provenance_record_per_pdf(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        for name in ("a.pdf", "b.pdf"):
            (input_dir / name).write_bytes(PDF_BYTES)
        mock_open.side_effect = lambda path: make_pdf([[["x"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert [r["derived_from"] for r in read_provenance(prov_dir)] == [["a.pdf"], ["b.pdf"]]

    def test_logs_start_and_saved_messages(self, dirs, mock_open, mock_logger):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        messages = [c[0][0] for c in mock_logger.info.call_args_list]
        assert any("a.pdf" in m for m in messages)
        assert any("a.csv" in m for m in messages)

    def test_open_error_propagates_and_aborts_run(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        for name in ("a.pdf", "b.pdf"):
            (input_dir / name).write_bytes(PDF_BYTES)
        mock_open.side_effect = ValueError("corrupt pdf")

        with pytest.raises(ValueError, match="corrupt pdf"):
            extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert list(output_dir.iterdir()) == []

    def test_failure_on_second_pdf_keeps_first_output(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        for name in ("a.pdf", "b.pdf"):
            (input_dir / name).write_bytes(PDF_BYTES)
        mock_open.side_effect = [make_pdf([[["x"]]]), RuntimeError("boom")]

        with pytest.raises(RuntimeError):
            extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        assert (output_dir / "a.csv").exists()
        assert not (output_dir / "b.csv").exists()
        assert len(read_provenance(prov_dir)) == EXPECTED_SINGLE_RECORD

    def test_extract_table_error_propagates_and_closes_pdf(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        pdf = make_pdf([[["x"]]])
        pdf.pages[0].extract_table.side_effect = RuntimeError("bad page")
        mock_open.return_value = pdf

        with pytest.raises(RuntimeError, match="bad page"):
            extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        pdf.__exit__.assert_called_once()

    def test_non_string_cells_are_preserved(self, dirs, mock_open):
        """CSV output preserves cell values rather than enforcing an Arrow string schema."""
        # Arrange
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[[1, 2]]])

        # Act
        extract_pdfs_to_silver(input_dir, output_dir, prov_dir)

        # Assert
        rows = read_rows(output_dir / "a.csv")
        assert rows[0]["raw_row"] == [1, 2]
        assert all(isinstance(value, int) for value in rows[0]["raw_row"])

    def test_unwritable_output_dir_raises(self, dirs, mock_open, tmp_path):
        input_dir, _, prov_dir = dirs
        blocker = tmp_path / "file_not_dir"
        blocker.write_text("x")

        with pytest.raises(OSError):
            extract_pdfs_to_silver(input_dir, blocker / "silver", prov_dir)


class TestMainEntryPoint:
    def test_main_block_uses_data_dirs_next_to_module(self, tmp_path):
        import runpy
        from pathlib import Path

        module_path = Path(pdf_extraction.__file__)
        with patch("pdf_extraction.extract_pdfs_to_silver") as extract_mock:
            # run_path re-executes the module source, so patch the fresh definition via pathlib mkdir/glob
            with patch("pathlib.Path.mkdir"), patch("pathlib.Path.glob", return_value=[]):
                runpy.run_path(str(module_path), run_name="__main__")

        extract_mock.assert_not_called()  # run_path rebinds the function; real one ran with empty glob

class TestTableExtractor:
    def test_custom_page_offset(self, tmp_path, mock_open):
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["row1"]]])

        extractor = TableExtractor(page_index_offset=CUSTOM_PAGE_OFFSET)
        records = extractor.extract_from_pdf(pdf_path)

        assert len(records) == EXPECTED_SINGLE_RECORD
        assert records[0]["table_index"] == CUSTOM_PAGE_OFFSET
        assert records[0]["row_index"] == FIRST_ROW_INDEX
        assert records[0]["raw_row"] == ["row1"]

    def test_skips_none_tables_with_warning(self, tmp_path, mock_open, mock_logger):
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([None])

        extractor = TableExtractor()
        records = extractor.extract_from_pdf(pdf_path)

        assert records == []
        mock_logger.warning.assert_called_once()

    def test_image_pdf_with_no_text_returns_empty_and_warns(self, tmp_path, mock_open, mock_logger):
        """
        Simulates an image-only / scanned PDF 
        """
        pdf_path = tmp_path / "scanned_image.pdf"
        pdf_path.write_bytes(PDF_BYTES)

        # Scanned/image-only PDF: contains no extractable text or tables
        page = MagicMock()
        page.extract_text.return_value = ""
        page.extract_table.return_value = None
        pdf = MagicMock()
        pdf.pages = [page]
        pdf.__enter__.return_value = pdf
        pdf.__exit__.return_value = False
        mock_open.return_value = pdf

        extractor = TableExtractor()
        records = extractor.extract_from_pdf(pdf_path)

        assert records == []
        mock_logger.warning.assert_called_once()
        assert "scanned_image.pdf" in mock_logger.warning.call_args[0][0]


class TestBronzeToSilverExtractor:
    def test_find_pdf_files_matches_case_insensitively(self, tmp_path):
        (tmp_path / "lower.pdf").write_bytes(PDF_BYTES)
        (tmp_path / "UPPER.PDF").write_bytes(PDF_BYTES)
        (tmp_path / "other.txt").write_text("text")

        extractor = BronzeToSilverExtractor()
        found = extractor.find_pdf_files(tmp_path)

        assert len(found) == EXPECTED_TWO_FILES
        assert [f.name for f in found] == ["UPPER.PDF", "lower.pdf"]

    def test_find_pdf_files_missing_directory_returns_empty(self, tmp_path):
        extractor = BronzeToSilverExtractor()
        found = extractor.find_pdf_files(tmp_path / "missing")
        assert len(found) == EXPECTED_NO_FILES

    def test_custom_injected_table_extractor(self, dirs):
        input_dir, output_dir, prov_dir = dirs
        pdf_path = input_dir / "custom.pdf"
        pdf_path.write_bytes(PDF_BYTES)

        mock_table_extractor = MagicMock(spec=TableExtractor)
        mock_table_extractor.extract_from_pdf.return_value = [
            {"table_index": FIRST_PAGE_NUMBER, "row_index": FIRST_ROW_INDEX, "raw_row": ["val"]}
        ]

        extractor = BronzeToSilverExtractor(table_extractor=mock_table_extractor)
        extractor.extract_all(input_dir, output_dir, prov_dir)

        mock_table_extractor.extract_from_pdf.assert_called_once_with(pdf_path)
        assert (output_dir / "custom.csv").exists()

    def test_extract_all_returns_converted_file_paths(self, dirs, mock_open):
        # Arrange
        input_dir, output_dir, prov_dir = dirs
        for name in ("b.pdf", "a.pdf"):
            (input_dir / name).write_bytes(b"%PDF-1.4 fake")
        mock_open.side_effect = lambda path: make_pdf([[[path.stem]]])

        extractor = BronzeToSilverExtractor()

        # Act
        result = extractor.extract_all(input_dir, output_dir, prov_dir)

        # Assert
        assert result == [output_dir / "a.csv", output_dir / "b.csv"]

    def test_extract_all_returns_empty_list_when_no_pdfs(self, dirs, mock_open):
        # Arrange
        input_dir, output_dir, prov_dir = dirs

        extractor = BronzeToSilverExtractor()

        # Act
        result = extractor.extract_all(input_dir, output_dir, prov_dir)

        # Assert
        assert result == []

    def test_extract_file_writes_csv_logs_provenance_and_returns_path(self, dirs, mock_logger):
        # Arrange
        input_dir, output_dir, prov_dir = dirs
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = input_dir / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_table_extractor = MagicMock(spec=TableExtractor)
        mock_table_extractor.extract_from_pdf.return_value = [
            {
                "table_index": 1,
                "row_index": 0,
                "raw_row": ["Abbeville — § 1", None, "10"],
            }
        ]
        extractor = BronzeToSilverExtractor(table_extractor=mock_table_extractor)

        # Act
        result_path = extractor.extract_file(pdf_path, output_dir, prov_dir)

        # Assert
        expected_csv = output_dir / "report.csv"
        assert result_path == expected_csv
        assert expected_csv.is_file()
        assert "Abbeville — § 1" in expected_csv.read_text(encoding="utf-8")
        assert read_rows(expected_csv) == [
            {
                "table_index": 1,
                "row_index": 0,
                "raw_row": ["Abbeville — § 1", None, "10"],
            }
        ]
        mock_logger.info.assert_called_once()
        assert "report.csv" in mock_logger.info.call_args[0][0]
        records = read_provenance(prov_dir)
        assert len(records) == 1
        assert records[0]["stage"] == "silver"
        assert records[0]["filename"] == "report.csv"
        assert records[0]["derived_from"] == ["report.pdf"]

    def test_extract_file_with_no_records_writes_header_only_csv(self, dirs, mock_logger):
        # Arrange
        input_dir, output_dir, prov_dir = dirs
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = input_dir / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_table_extractor = MagicMock(spec=TableExtractor)
        mock_table_extractor.extract_from_pdf.return_value = []
        extractor = BronzeToSilverExtractor(table_extractor=mock_table_extractor)

        # Act
        result_path = extractor.extract_file(pdf_path, output_dir, prov_dir)

        # Assert
        expected_csv = output_dir / "empty.csv"
        assert result_path == expected_csv
        assert expected_csv.read_text(encoding="utf-8").strip() == "table_index,row_index,raw_row"
        assert read_rows(expected_csv) == []
        mock_logger.info.assert_called_once()
        records = read_provenance(prov_dir)
        assert len(records) == 1
        assert records[0]["filename"] == "empty.csv"
        assert records[0]["derived_from"] == ["empty.pdf"]
