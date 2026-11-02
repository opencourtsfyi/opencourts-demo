from pathlib import Path
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


class TestMainEntryPoint:
    def test_main_block_uses_data_dirs_next_to_module(self, tmp_path):
        import runpy
        from pathlib import Path

        module_path = Path(pdf_extraction.__file__)
        # run_path re-executes the module source, so patch mkdir and glob on pathlib.Path
        with patch("pathlib.Path.mkdir") as mkdir_mock, patch("pathlib.Path.glob", return_value=[]):
            runpy.run_path(str(module_path), run_name="__main__")

        mkdir_mock.assert_called_once()


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
    def test_extracts_rows_with_page_and_row_indexes(self, dirs, mock_open):
        # Arrange
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["h1", "h2"], ["a", "b"]], [["c", "d"]]])

        # Act
        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

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

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        mock_open.assert_called_once_with(pdf_path)

    def test_pdf_context_manager_is_closed(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        pdf = make_pdf([[["x"]]])
        mock_open.return_value = pdf

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        pdf.__exit__.assert_called_once()

    def test_preserves_none_cells_and_empty_strings(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["a", None, ""]]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert read_rows(output_dir / "a.csv")[0]["raw_row"] == ["a", None, ""]

    def test_preserves_ragged_rows(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["a"], ["b", "c", "d"], []]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert [r["raw_row"] for r in read_rows(output_dir / "a.csv")] == [["a"], ["b", "c", "d"], []]

    def test_page_without_table_is_skipped_but_numbering_is_preserved(self, dirs, mock_open, mock_logger):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["a"]], None, [["c"]]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        rows = read_rows(output_dir / "a.csv")
        assert [r["table_index"] for r in rows] == [FIRST_PAGE_NUMBER, THIRD_PAGE_NUMBER]
        mock_logger.warning.assert_called_once()
        assert str(SECOND_PAGE_NUMBER) in mock_logger.warning.call_args[0][0]
        assert "a.pdf" in mock_logger.warning.call_args[0][0]

    def test_empty_table_list_on_page_yields_no_rows(self, dirs, mock_open, mock_logger):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["a"]], []])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert len(read_rows(output_dir / "a.csv")) == EXPECTED_SINGLE_RECORD
        mock_logger.warning.assert_not_called()

    def test_pdf_with_no_tables_writes_empty_csv(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([None, None])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        csv_path = output_dir / "a.csv"
        assert csv_path.exists()
        assert read_rows(csv_path) == []
        assert len(read_provenance(prov_dir)) == 1

    def test_pdf_with_zero_pages_writes_empty_csv(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        csv_path = output_dir / "a.csv"
        assert csv_path.exists()
        assert read_rows(csv_path) == []
        assert len(read_provenance(prov_dir)) == EXPECTED_SINGLE_RECORD

    def test_pdf_with_only_empty_tables_writes_empty_csv(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

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

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

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

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

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

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert [c.args[0].name for c in mock_open.call_args_list] == ["a.pdf", "b.pdf"]
        assert sorted(p.name for p in output_dir.iterdir()) == ["a.csv", "b.csv"]
        assert read_rows(output_dir / "b.csv")[0]["raw_row"] == ["b"]

    def test_ignores_non_pdf_files_and_subdirectories(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "notes.txt").write_text("x")
        (input_dir / "sub").mkdir()
        (input_dir / "sub" / "nested.pdf").write_bytes(PDF_BYTES)

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        mock_open.assert_not_called()
        assert list(output_dir.iterdir()) == []

    def test_glob_is_case_sensitive_on_extension_per_platform(self, dirs, mock_open):
        """Uppercase .PDF is matched, extracted to UPPER.csv, and deduplicated."""
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "UPPER.PDF").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        extractor = BronzeToSilverExtractor(input_dir, output_dir, prov_dir)
        matched = extractor.find_pdf_files()

        assert [f.name for f in matched] == ["UPPER.PDF"]
        extractor.extract_all()

        mock_open.assert_called_once_with(input_dir / "UPPER.PDF")
        assert [p.name for p in output_dir.iterdir()] == ["UPPER.csv"]

    def test_find_pdf_files_matches_mixed_extension_casings(self, tmp_path):
        """Finds files with both .pdf and .PDF extensions in the same directory."""
        (tmp_path / "foo.pdf").write_bytes(PDF_BYTES)
        (tmp_path / "bar.PDF").write_bytes(PDF_BYTES)

        extractor = BronzeToSilverExtractor(input_dir=tmp_path)
        found = extractor.find_pdf_files()

        assert [f.name for f in found] == ["bar.PDF", "foo.pdf"]

    def test_find_pdf_files_deduplicates_same_file_matched_by_multiple_patterns(self, tmp_path):
        """When glob matches the same physical file under multiple patterns, it is deduplicated."""
        (tmp_path / "doc.pdf").write_bytes(PDF_BYTES)
        extractor = BronzeToSilverExtractor(input_dir=tmp_path)
        matched = extractor.find_pdf_files()
        assert len(matched) == 1
        assert matched[0].name.lower() == "doc.pdf"

    def test_empty_input_dir_creates_output_dir_only(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert output_dir.is_dir()
        assert list(output_dir.iterdir()) == []
        assert not prov_dir.exists()

    def test_missing_input_dir_is_treated_as_empty(self, tmp_path, mock_open):
        output_dir = tmp_path / "silver"

        BronzeToSilverExtractor(tmp_path / "does_not_exist", output_dir, tmp_path / "prov").extract_all()

        assert output_dir.is_dir()
        mock_open.assert_not_called()

    def test_creates_nested_output_dir(self, dirs, mock_open):
        input_dir, _, prov_dir = dirs
        nested = input_dir.parent / "x" / "y" / "silver"

        BronzeToSilverExtractor(input_dir, nested, prov_dir).extract_all()

        assert nested.is_dir()

    def test_filename_stem_with_dots_is_preserved(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "report.2024.01.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert (output_dir / "report.2024.01.csv").exists()

    def test_overwrites_existing_output(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        output_dir.mkdir()
        (output_dir / "a.csv").write_bytes(b"stale")
        mock_open.return_value = make_pdf([[["fresh"]]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert read_rows(output_dir / "a.csv")[0]["raw_row"] == ["fresh"]

    def test_logs_provenance_with_lineage(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

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
            BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        log_mock.assert_called_once_with(
            prov_dir, stage="silver", file_path=output_dir / "a.csv", derived_from=["a.pdf"]
        )

    def test_provenance_hash_matches_written_file(self, dirs, mock_open):
        from provenance import compute_file_hash

        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert read_provenance(prov_dir)[0]["file_hash"] == compute_file_hash(output_dir / "a.csv")

    def test_one_provenance_record_per_pdf(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        for name in ("a.pdf", "b.pdf"):
            (input_dir / name).write_bytes(PDF_BYTES)
        mock_open.side_effect = lambda path: make_pdf([[["x"]]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert [r["derived_from"] for r in read_provenance(prov_dir)] == [["a.pdf"], ["b.pdf"]]

    def test_logs_start_and_saved_messages(self, dirs, mock_open, mock_logger):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["x"]]])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        messages = [c[0][0] for c in mock_logger.info.call_args_list]
        assert any("a.pdf" in m for m in messages)
        assert any("a.csv" in m for m in messages)

    def test_open_error_propagates_and_aborts_run(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        for name in ("a.pdf", "b.pdf"):
            (input_dir / name).write_bytes(PDF_BYTES)
        mock_open.side_effect = ValueError("corrupt pdf")

        with pytest.raises(ValueError, match="corrupt pdf"):
            BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        assert list(output_dir.iterdir()) == []

    def test_failure_on_second_pdf_keeps_first_output(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        for name in ("a.pdf", "b.pdf"):
            (input_dir / name).write_bytes(PDF_BYTES)
        mock_open.side_effect = [make_pdf([[["x"]]]), RuntimeError("boom")]

        with pytest.raises(RuntimeError):
            BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

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
            BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        pdf.__exit__.assert_called_once()

    def test_non_string_cells_are_preserved(self, dirs, mock_open):
        """CSV output preserves cell values rather than enforcing an Arrow string schema."""
        # Arrange
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "a.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[[1, 2]]])

        # Act
        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        # Assert
        rows = read_rows(output_dir / "a.csv")
        assert rows[0]["raw_row"] == [1, 2]
        assert all(isinstance(value, int) for value in rows[0]["raw_row"])

    def test_unwritable_output_dir_raises(self, dirs, mock_open, tmp_path):
        input_dir, _, prov_dir = dirs
        blocker = tmp_path / "file_not_dir"
        blocker.write_text("x")

        with pytest.raises(OSError):
            BronzeToSilverExtractor(input_dir, blocker / "silver", prov_dir).extract_all()

    def test_find_pdf_files_matches_case_insensitively(self, tmp_path):
        (tmp_path / "lower.pdf").write_bytes(PDF_BYTES)
        (tmp_path / "UPPER.PDF").write_bytes(PDF_BYTES)
        (tmp_path / "other.txt").write_text("text")

        extractor = BronzeToSilverExtractor(input_dir=tmp_path)
        found = extractor.find_pdf_files()

        assert len(found) == EXPECTED_TWO_FILES
        assert [f.name for f in found] == ["UPPER.PDF", "lower.pdf"]

    def test_find_pdf_files_missing_directory_returns_empty(self, tmp_path):
        extractor = BronzeToSilverExtractor(input_dir=tmp_path / "missing")
        found = extractor.find_pdf_files()
        assert len(found) == EXPECTED_NO_FILES

    def test_custom_injected_table_extractor(self, dirs):
        input_dir, output_dir, prov_dir = dirs
        pdf_path = input_dir / "custom.pdf"
        pdf_path.write_bytes(PDF_BYTES)

        mock_table_extractor = MagicMock(spec=TableExtractor)
        mock_table_extractor.extract_from_pdf.return_value = [
            {"table_index": FIRST_PAGE_NUMBER, "row_index": FIRST_ROW_INDEX, "raw_row": ["val"]}
        ]

        extractor = BronzeToSilverExtractor(
            input_dir=input_dir,
            output_dir=output_dir,
            provenance_dir=prov_dir,
            table_extractor=mock_table_extractor,
        )
        extractor.extract_all()

        mock_table_extractor.extract_from_pdf.assert_called_once_with(pdf_path)
        assert (output_dir / "custom.csv").exists()

    def test_extract_all_returns_converted_file_paths(self, dirs, mock_open):
        # Arrange
        input_dir, output_dir, prov_dir = dirs
        for name in ("b.pdf", "a.pdf"):
            (input_dir / name).write_bytes(b"%PDF-1.4 fake")
        mock_open.side_effect = lambda path: make_pdf([[[path.stem]]])

        extractor = BronzeToSilverExtractor(
            input_dir=input_dir,
            output_dir=output_dir,
            provenance_dir=prov_dir,
        )

        # Act
        result = extractor.extract_all()

        # Assert
        assert result == [output_dir / "a.csv", output_dir / "b.csv"]

    def test_extract_all_returns_empty_list_when_no_pdfs(self, dirs, mock_open):
        # Arrange
        input_dir, output_dir, prov_dir = dirs

        extractor = BronzeToSilverExtractor(
            input_dir=input_dir,
            output_dir=output_dir,
            provenance_dir=prov_dir,
        )

        # Act
        result = extractor.extract_all()

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
        extractor = BronzeToSilverExtractor(
            input_dir=input_dir,
            output_dir=output_dir,
            provenance_dir=prov_dir,
            table_extractor=mock_table_extractor,
        )

        # Act
        result_path = extractor.extract_file(pdf_path)

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
        extractor = BronzeToSilverExtractor(
            input_dir=input_dir,
            output_dir=output_dir,
            provenance_dir=prov_dir,
            table_extractor=mock_table_extractor,
        )

        # Act
        result_path = extractor.extract_file(pdf_path)

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

    def test_i18n_logging_in_spanish(self, dirs, mock_open, mock_logger):
        from i18n import use_locale

        input_dir, output_dir, prov_dir = dirs
        (input_dir / "informe.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([None])

        with use_locale("es"):
            BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        info_messages = [c[0][0] for c in mock_logger.info.call_args_list]
        warning_messages = [c[0][0] for c in mock_logger.warning.call_args_list]

        assert "Iniciando extracción en: informe.pdf" in info_messages
        assert "Guardado informe.csv" in info_messages
        assert warning_messages == [
            "No se encontró ninguna tabla en la página 1 de informe.pdf, omitiendo"
        ]

    def test_i18n_fallback_when_locale_is_missing(self, dirs, mock_open, mock_logger):
        from i18n import use_locale

        input_dir, output_dir, prov_dir = dirs
        (input_dir / "fallback.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["data"]]])

        with use_locale("nonexistent_locale"):
            BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        info_messages = [c[0][0] for c in mock_logger.info.call_args_list]
        assert "Starting extraction on: fallback.pdf" in info_messages
        assert "Saved fallback.csv" in info_messages

    def test_find_pdf_files_includes_hidden_pdf(self, tmp_path):
        (tmp_path / ".hidden.pdf").write_bytes(PDF_BYTES)
        (tmp_path / "visible.pdf").write_bytes(PDF_BYTES)

        extractor = BronzeToSilverExtractor(input_dir=tmp_path)
        found = extractor.find_pdf_files()

        assert [f.name for f in found] == [".hidden.pdf", "visible.pdf"]

    def test_duplicate_stems_across_casing_behavior(self, dirs, mock_open):
        """When duplicate stems exist (e.g. x.PDF and x.pdf), they sort deterministically and extract to x.csv."""
        input_dir, output_dir, prov_dir = dirs
        mock_open.side_effect = lambda p: make_pdf([[[p.name]]])

        extractor = BronzeToSilverExtractor(input_dir, output_dir, prov_dir)
        with patch.object(
            extractor,
            "find_pdf_files",
            return_value=[input_dir / "x.PDF", input_dir / "x.pdf"],
        ):
            output_files = extractor.extract_all()

        assert output_files == [output_dir / "x.csv", output_dir / "x.csv"]
        assert read_rows(output_dir / "x.csv")[0]["raw_row"] == ["x.pdf"]
        provenance = read_provenance(prov_dir)
        assert len(provenance) == 2
        assert provenance[0]["derived_from"] == ["x.PDF"]
        assert provenance[1]["derived_from"] == ["x.pdf"]

    def test_extract_table_with_tuple_rows_and_ragged_lengths_coerces_cleanly(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "oddball.pdf").write_bytes(PDF_BYTES)
        odd_table = [("cell1", "cell2"), ["single_cell"], ["col1", "col2", "col3"]]
        mock_open.return_value = make_pdf([odd_table])

        BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

        rows = read_rows(output_dir / "oddball.csv")
        assert len(rows) == 3
        assert rows[0]["raw_row"] == ["cell1", "cell2"]
        assert rows[1]["raw_row"] == ["single_cell"]
        assert rows[2]["raw_row"] == ["col1", "col2", "col3"]

    def test_extract_table_non_iterable_payload_fails_loudly(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "corrupt_table.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([12345])

        with pytest.raises(TypeError):
            BronzeToSilverExtractor(input_dir, output_dir, prov_dir).extract_all()

    def test_repeat_runs_append_provenance_without_overwriting(self, dirs, mock_open):
        input_dir, output_dir, prov_dir = dirs
        (input_dir / "run1.pdf").write_bytes(PDF_BYTES)
        mock_open.return_value = make_pdf([[["row1"]]])

        extractor = BronzeToSilverExtractor(input_dir, output_dir, prov_dir)

        extractor.extract_all()
        log_after_run1 = read_provenance(prov_dir)
        assert len(log_after_run1) == 1
        assert log_after_run1[0]["filename"] == "run1.csv"
        assert log_after_run1[0]["derived_from"] == ["run1.pdf"]

        (input_dir / "run2.pdf").write_bytes(PDF_BYTES)
        extractor.extract_all()
        log_after_run2 = read_provenance(prov_dir)

        assert len(log_after_run2) == 3
        assert log_after_run2[0] == log_after_run1[0]
        assert [r["filename"] for r in log_after_run2] == ["run1.csv", "run1.csv", "run2.csv"]
