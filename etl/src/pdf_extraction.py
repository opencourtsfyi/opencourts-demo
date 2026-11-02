# pdf_extraction.py
"""
Silver stage: extracts raw tables from each Bronze PDF using pdfplumber
and saves them as CSV files, preserving the table structure exactly
as pdfplumber found it (no interpretation or cleanup happens here).
Also logs a provenance/lineage record linking each Silver file back to
the one Bronze PDF it was derived from.
"""

import json
import logging
from pathlib import Path
from typing import Any, Final

import pdfplumber
import pandas as pd

from provenance import log_provenance
from i18n import t

logger = logging.getLogger(__name__)

# Constants to eliminate magic numbers and domain literals
COLUMN_TABLE_INDEX: Final[str] = "table_index"
COLUMN_ROW_INDEX: Final[str] = "row_index"
COLUMN_RAW_ROW: Final[str] = "raw_row"
SILVER_COLUMNS = (COLUMN_TABLE_INDEX, COLUMN_ROW_INDEX, COLUMN_RAW_ROW)

DEFAULT_BRONZE_DIR: Final[str] = "data/pdfs_bronze"
DEFAULT_SILVER_DIR: Final[str] = "data/cases_silver"
DEFAULT_PROVENANCE_DIR: Final[str] = "data/provenance"

class TableExtractor:
    """Extracts raw tables from PDF pages using pdfplumber."""

    PAGE_INDEX_OFFSET: Final[int] = 1  # 1-based page/table numbering for human-readable indexing
    ROW_INDEX_START: Final[int] = 0  # 0-based row numbering within each extracted table

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

                #Warn about pages with no detectable table (e.g. blank pages)
                if table_data is None:
                    logger.warning(
                        t(
                            "pdf_extraction.log_no_table_found",
                            table_index=table_index,
                            filename=file_path.name,
                        )
                    )
                    continue

                for row_index, raw_row in enumerate(table_data, start=self.ROW_INDEX_START):
                    collected_records.append({
                        COLUMN_TABLE_INDEX: table_index,
                        COLUMN_ROW_INDEX: row_index,
                        COLUMN_RAW_ROW: raw_row,
                    })

        return collected_records


class BronzeToSilverExtractor:
    """Coordinates extraction of Bronze files into Silver files with provenance tracking."""

    PDF_FILE_PATTERNS: Final[tuple[str, str]] = ("*.pdf", "*.PDF")
    CSV_FILE_EXTENSION: Final[str] = ".csv"
    STAGE_SILVER: Final[str] = "silver"

    def __init__(
        self,
        input_dir: Path | str = DEFAULT_BRONZE_DIR,
        output_dir: Path | str = DEFAULT_SILVER_DIR,
        provenance_dir: Path | str = DEFAULT_PROVENANCE_DIR,
        table_extractor: TableExtractor | None = None,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.provenance_dir = Path(provenance_dir)
        self.table_extractor = table_extractor or TableExtractor()

    def find_pdf_files(self) -> list[Path]:
        """Finds all PDF files in input_dir using case-insensitive globbing, sorted deterministically."""
        if not self.input_dir.is_dir():
            return []

        matched_files: set[Path] = set()
        for pattern in self.PDF_FILE_PATTERNS:
            for file_path in self.input_dir.glob(pattern):
                if file_path.is_file():
                    matched_files.add(file_path)

        return sorted(matched_files, key=lambda p: p.name)

    def extract_file(self, file_path: Path) -> Path:
        """Extracts a single PDF into a Silver CSV file and logs provenance."""

        collected_records = self.table_extractor.extract_from_pdf(file_path)

        if collected_records:
            df = pd.DataFrame(collected_records, columns=SILVER_COLUMNS)
            # Turn each list in raw_row into a JSON string, this is because 
            # a CSV column cannot store the original list, including empty cells,
            df["raw_row"] = df["raw_row"].apply(lambda value: json.dumps(value, ensure_ascii=False))
        else:
            # A PDF with no tables still gets a header-only file so every Bronze
            # input produces a Silver artifact. 
            df = pd.DataFrame(columns=SILVER_COLUMNS)

        output_file_path = self.output_dir / f"{file_path.stem}{self.CSV_FILE_EXTENSION}"
        df.to_csv(output_file_path, index=False, encoding="utf-8")

        logger.info(t("pdf_extraction.log_saved", filename=output_file_path.name))

        log_provenance(
            self.provenance_dir,
            stage=self.STAGE_SILVER,
            file_path=output_file_path,
            derived_from=[file_path.name],
        )

        return output_file_path

    def extract_all(self) -> list[Path]:
        """Extracts all PDFs in input_dir to CSV in output_dir, logging provenance."""

        self.output_dir.mkdir(parents=True, exist_ok=True)

        output_files: list[Path] = []
        for file_path in self.find_pdf_files():
            logger.info(t("pdf_extraction.log_starting_extraction", filename=file_path.name))
            output_file = self.extract_file(file_path)
            output_files.append(output_file)

        return output_files


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()

    base_dir = Path(__file__).resolve().parent.parent
    BronzeToSilverExtractor(
        input_dir=base_dir / DEFAULT_BRONZE_DIR,
        output_dir=base_dir / DEFAULT_SILVER_DIR,
        provenance_dir=base_dir / DEFAULT_PROVENANCE_DIR,
    ).extract_all()
