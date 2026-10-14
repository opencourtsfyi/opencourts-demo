# pdf_extraction.py
"""
Silver stage: extracts raw tables from each Bronze PDF using pdfplumber
and saves them as Parquet files, preserving the table structure exactly
as pdfplumber found it (no interpretation or cleanup happens here).
Also logs a provenance/lineage record linking each Silver file back to
the one Bronze PDF it was derived from.
"""

from pathlib import Path
from typing import Any

import pdfplumber
import pyarrow as pa
import pyarrow.parquet as pq

from logging_config import get_logger
from provenance import log_provenance

logger = get_logger(__name__)

# Constants to eliminate magic numbers and domain literals
PAGE_INDEX_OFFSET = 1  # 1-based page/table numbering for human-readable indexing
ROW_INDEX_START = 0  # 0-based row numbering within each extracted table
STAGE_SILVER = "silver"

COLUMN_TABLE_INDEX = "table_index"
COLUMN_ROW_INDEX = "row_index"
COLUMN_RAW_ROW = "raw_row"

PARQUET_FILE_EXTENSION = ".parquet"
PDF_FILE_PATTERNS = ("*.pdf", "*.PDF")

DEFAULT_BRONZE_DIR = "data/pdfs_bronze"
DEFAULT_SILVER_DIR = "data/cases_silver"
DEFAULT_PROVENANCE_DIR = "data/provenance"

# Canonical PyArrow schema for Silver tier extracted tables
SILVER_SCHEMA = pa.schema([
    (COLUMN_TABLE_INDEX, pa.int64()),
    (COLUMN_ROW_INDEX, pa.int64()),
    (COLUMN_RAW_ROW, pa.list_(pa.string())),
])


class TableExtractor:
    """Extracts raw tables from PDF pages using pdfplumber."""

    def __init__(self, page_index_offset: int = PAGE_INDEX_OFFSET) -> None:
        self.page_index_offset = page_index_offset

    def extract_from_pdf(self, file_path: Path) -> list[dict[str, Any]]:
        """Extracts all table rows across all pages of a PDF file.

        Returns a list of dict records with table_index, row_index, and raw_row.
        If a page contains no extractable table, logs a warning and skips it.
        """
        collected_records: list[dict[str, Any]] = []

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                table_index = i + self.page_index_offset
                table_data = page.extract_table()

                if table_data is None:
                    logger.warning(
                        f"No table found on page {table_index} of {file_path.name}, skipping"
                    )
                    continue

                for row_index, raw_row in enumerate(table_data, start=ROW_INDEX_START):
                    collected_records.append({
                        COLUMN_TABLE_INDEX: table_index,
                        COLUMN_ROW_INDEX: row_index,
                        COLUMN_RAW_ROW: raw_row,
                    })

        return collected_records


class PdfSilverExtractor:
    """Coordinates extraction of Bronze PDFs into Silver Parquet files with provenance tracking."""

    def __init__(
        self,
        table_extractor: TableExtractor | None = None,
        schema: pa.Schema = SILVER_SCHEMA,
    ) -> None:
        self.table_extractor = table_extractor or TableExtractor()
        self.schema = schema

    def find_pdf_files(self, input_dir: Path) -> list[Path]:
        """Finds all PDF files in input_dir using case-insensitive globbing, sorted deterministically."""
        if not input_dir.is_dir():
            return []

        matched_files: set[Path] = set()
        for pattern in PDF_FILE_PATTERNS:
            for file_path in input_dir.glob(pattern):
                if file_path.is_file():
                    matched_files.add(file_path)

        return sorted(matched_files, key=lambda p: p.name)

    def extract_file(
        self,
        file_path: Path,
        output_dir: Path,
        provenance_dir: Path,
    ) -> Path:
        """Extracts a single PDF into a Silver Parquet file and logs provenance."""
        collected_records = self.table_extractor.extract_from_pdf(file_path)

        arrow_table = pa.Table.from_pylist(collected_records, schema=self.schema)

        output_file_path = output_dir / f"{file_path.stem}{PARQUET_FILE_EXTENSION}"
        pq.write_table(arrow_table, output_file_path)
        logger.info(f"Saved {output_file_path.name}")

        log_provenance(
            provenance_dir,
            stage=STAGE_SILVER,
            file_path=output_file_path,
            derived_from=[file_path.name],
        )
        return output_file_path

    def extract_all(
        self,
        input_dir: Path | str,
        output_dir: Path | str,
        provenance_dir: Path | str,
    ) -> list[Path]:
        """Extracts all PDFs in input_dir to Parquet in output_dir, logging provenance."""
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        provenance_dir = Path(provenance_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        output_files: list[Path] = []
        for file_path in self.find_pdf_files(input_dir):
            logger.info(f"Starting extraction on: {file_path.name}")
            output_file = self.extract_file(file_path, output_dir, provenance_dir)
            output_files.append(output_file)

        return output_files


def extract_pdfs_to_silver(
    input_dir: Path | str,
    output_dir: Path | str,
    provenance_dir: Path | str,
) -> list[Path]:
    """Extracts raw tables from all PDFs in input_dir and saves them as Parquet in output_dir."""
    extractor = PdfSilverExtractor()
    return extractor.extract_all(input_dir, output_dir, provenance_dir)


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    extract_pdfs_to_silver(
        base_dir / DEFAULT_BRONZE_DIR,
        base_dir / DEFAULT_SILVER_DIR,
        base_dir / DEFAULT_PROVENANCE_DIR,
    )
