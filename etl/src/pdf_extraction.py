# pdf_extraction.py
"""
Silver stage: extracts raw tables from each Bronze PDF using pdfplumber
and saves them as Parquet files, preserving the table structure exactly
as pdfplumber found it (no interpretation or cleanup happens here).
Also logs a provenance/lineage record linking each Silver file back to
the one Bronze PDF it was derived from.
"""

import pdfplumber
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

from provenance import log_provenance
from logging_config import get_logger

logger = get_logger(__name__)


def extract_pdfs_to_silver(input_dir, output_dir, provenance_dir):
    """Extracts raw tables from all PDFs in input_dir and saves them as Parquet in output_dir."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # sorted() ensures deterministic processing order across runs, which
    # matters for reproducible, hash-comparable output
    for file_path in sorted(input_dir.glob("*.pdf")):
        logger.info(f"Starting extraction on: {file_path.name}")
        collected_records = []  # One dict per extracted row, across all pages of this PDF

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                table_index = i + 1  # 1-based page/table numbering for readability
                table_data = page.extract_table()  # list of lists, or None if no table found

                # Guard against pages with no detectable table (e.g. blank pages)
                if table_data is None:
                    logger.warning(f"No table found on page {table_index} of {file_path.name}, skipping")
                    continue

                # Store each row exactly as pdfplumber gave it, tagged with its
                # page number and its position within that table's rows
                for row_index, raw_row in enumerate(table_data):
                    collected_records.append({
                        "table_index": table_index,
                        "row_index": row_index,
                        "raw_row": raw_row
                    })

        # Explicit schema keeps Parquet output consistent even if a page
        # produces an empty or unusually shaped table
        parquet_schema = pa.schema([
            ('table_index', pa.int64()),
            ('row_index', pa.int64()),
            ('raw_row', pa.list_(pa.string()))
        ])

        df = pd.DataFrame(collected_records)
        arrow_table = pa.Table.from_pandas(df, schema=parquet_schema)

        # One Silver Parquet file per source PDF, same base filename
        output_file_path = output_dir / f"{file_path.stem}.parquet"
        pq.write_table(arrow_table, output_file_path)
        logger.info(f"Saved {output_file_path.name}")

        # Lineage: this Silver file was derived from exactly one Bronze PDF
        log_provenance(
            provenance_dir,
            stage="silver",
            file_path=output_file_path,
            derived_from=[file_path.name],
        )


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    extract_pdfs_to_silver(
        base_dir / "data/pdfs_bronze",
        base_dir / "data/cases_silver",
        base_dir / "data/provenance",
    )
