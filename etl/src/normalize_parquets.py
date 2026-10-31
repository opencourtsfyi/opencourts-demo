# normalize_parquets.py
"""
Gold stage: reads Silver Parquet files (raw extracted PDF tables) and
normalizes them into a long-format dataset, one row per (county, metric,
month, year) data point, matching the project's target schema.

Writes the SAME in-memory rows to both CSV and Parquet, so the two output
formats can never drift apart from each other. Also logs a provenance/
lineage record linking the Gold output back to every Silver file that fed it.
"""

import logging
from collections.abc import Sequence
from pathlib import Path
import re
from typing import Any, Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from provenance import log_provenance

logger = logging.getLogger(__name__)

# --- Shared defaults and output schema ---
DEFAULT_OUTPUT_FILENAME = "caseloads_normalized"

# --- Reference data used to recognize and label rows during normalization ---

CATEGORY_ESTATE = "Estate"
CATEGORY_GUARDIAN = "Guardian"
CATEGORY_CONSERVATOR = "Conservator"
CATEGORY_MENTAL_HEALTH = "Mental Health"

CATEGORY = [CATEGORY_ESTATE, CATEGORY_GUARDIAN, CATEGORY_CONSERVATOR, CATEGORY_MENTAL_HEALTH]
STANDARD_CATEGORIES = {CATEGORY_ESTATE, CATEGORY_GUARDIAN, CATEGORY_CONSERVATOR}

# Maps full month names (as they appear in the PDF headers) to their numeric string form
MONTHS = {
    "July": "7", "August": "8", "September": "9", "October": "10",
    "November": "11", "December": "12", "January": "1", "February": "2",
    "March": "3", "April": "4", "May": "5", "June": "6",
}

# All 46 South Carolina counties, used to detect county rows in the raw table
SC_COUNTIES = [
    "Abbeville", "Aiken", "Allendale", "Anderson", "Bamberg", "Barnwell", "Beaufort", "Berkeley",
    "Calhoun", "Charleston", "Cherokee", "Chester", "Chesterfield", "Clarendon", "Colleton",
    "Darlington", "Dillon", "Dorchester", "Edgefield", "Fairfield", "Florence", "Georgetown",
    "Greenville", "Greenwood", "Hampton", "Horry", "Jasper", "Kershaw", "Lancaster", "Laurens",
    "Lee", "Lexington", "Marion", "Marlboro", "McCormick", "Newberry", "Oconee", "Orangeburg",
    "Pickens", "Richland", "Saluda", "Spartanburg", "Sumter", "Union", "Williamsburg", "York",
]

# Metric labels differ by category. Estate/Guardian reports use 4 metrics;
# Mental Health reports use a different, smaller set (with footnote markers
# like "Orders*" in the raw PDF, handled by match_metric below).
EXPECTED_METRICS = ["Pending first of month", "Added", "Disposed", "Pending end of Month"]
EXPECTED_METRICS_MENTAL_HEALTH = ["Added", "Orders"]

# Column order for the output CSV/Parquet
FILE_COLUMN = "file"
CATEGORY_COLUMN = "category"
MONTH_COLUMN = "month"
YEAR_COLUMN = "year"
COUNTY_COLUMN = "county"
METRIC_COLUMN = "metric"
VALUE_COLUMN = "value"

SCHEMA = [
    FILE_COLUMN,
    CATEGORY_COLUMN,
    MONTH_COLUMN,
    YEAR_COLUMN,
    COUNTY_COLUMN,
    METRIC_COLUMN,
    VALUE_COLUMN,
]

# Pre-computed lowercase lookup dicts: {lowercase_version: canonical_version}
# Lets us match case-insensitively while outputting clean, consistently-cased
# labels regardless of how a given PDF year capitalized things.
CATEGORY_LOWER = {c.lower(): c for c in CATEGORY}
MONTHS_LOWER = {k.lower(): v for k, v in MONTHS.items()}
COUNTIES_LOWER = {c.lower(): c for c in SC_COUNTIES}
METRICS_LOWER = {m.lower(): m for m in EXPECTED_METRICS}
METRICS_MH_LOWER = {m.lower(): m for m in EXPECTED_METRICS_MENTAL_HEALTH}


class MetricMatcher:
    """Matches and resolves metric labels from raw table cells."""

    @staticmethod
    def match(item: Any, metrics_lower_dict: dict[str, str]) -> str | None:
        """Returns the canonical metric name if item starts with a known metric
        (case-insensitive), handling footnote markers like 'Orders*'. Returns None
        if no match is found.

        startswith() instead of exact match handles the PDF appending a footnote
        marker directly onto the label. Safe here because no metric name is a
        prefix of another metric name.
        """
        if item is None:
            return None
        item_clean = str(item).strip().lower()
        for metric_lower, metric_canonical in metrics_lower_dict.items():
            if item_clean.startswith(metric_lower):
                return metric_canonical
        return None

    @classmethod
    def find_in_row(cls, raw_row: Sequence[Any], metrics_lower_dict: dict[str, str]) -> str | None:
        """Returns the first matching canonical metric found across cells in raw_row,
        or None if no known metric is present.
        """
        for item in raw_row:
            matched = cls.match(item, metrics_lower_dict)
            if matched is not None:
                return matched
        return None


def match_metric(item: Any, metrics_lower_dict: dict[str, str]) -> str | None:
    """Returns the canonical metric name if item starts with a known metric
    (case-insensitive), handling footnote markers like 'Orders*'. Returns None
    if no match is found.

    startswith() instead of exact match handles the PDF appending a footnote
    marker directly onto the label. Safe here because no metric name is a
    prefix of another metric name.
    """
    return MetricMatcher.match(item, metrics_lower_dict)


class SilverDataLoader:
    """Discovers and loads Silver stage Parquet files and metadata."""

    PARQUET_FILE_PATTERN: Final[str] = "*.parquet"
    YEAR_REGEX_PATTERN: Final[str] = r"\d{4}"
    YEAR_PATTERN: Final[re.Pattern[str]] = re.compile(YEAR_REGEX_PATTERN)
    FIRST_YEAR_INDEX: Final[int] = 0
    SECOND_YEAR_INDEX: Final[int] = 1

    @staticmethod
    def find_parquet_files(input_dir: Path) -> list[Path]:
        """Returns all Parquet files in input_dir, sorted deterministically."""
        return sorted(input_dir.glob(SilverDataLoader.PARQUET_FILE_PATTERN))

    @staticmethod
    def extract_fiscal_years(file_path: Path) -> tuple[str, str]:
        """Extracts the two fiscal years from a Silver file's stem.

        Raises IndexError if fewer than two 4-digit years are found.
        """
        years_found = SilverDataLoader.YEAR_PATTERN.findall(file_path.stem)
        return (
            years_found[SilverDataLoader.FIRST_YEAR_INDEX],
            years_found[SilverDataLoader.SECOND_YEAR_INDEX],
        )

    @staticmethod
    def load_rows_dataframe(file_path: Path) -> pd.DataFrame:
        """Reads a Silver Parquet table into a pandas DataFrame."""
        return pq.read_table(file_path).to_pandas()


class TableNormalizer:
    """Normalizes raw table rows from a Silver Parquet file into structured records.

    Tracks parsing state (category, county, month column positions, fiscal year mapping)
    across sequential rows of an extracted PDF table.
    """

    TITLE_COLUMN_INDEX: Final[int] = 0
    COUNTY_COLUMN_INDEX: Final[int] = 0
    HEADER_MONTH_SEARCH_START_INDEX: Final[int] = 2
    CATEGORY_TITLE_LINE_INDEX: Final[int] = 1
    FIRST_INDEX: Final[int] = 0
    PREVIOUS_INDEX_OFFSET: Final[int] = 1
    RAW_ROW_COLUMN: Final[str] = "raw_row"
    COURT_ADMIN_TITLE_MARKER: Final[str] = "court administration"
    EMPTY_CELL: Final[str] = ""
    EMPTY_STRING: Final[str] = ""
    COMMA_DELIMITER: Final[str] = ","
    NEWLINE_DELIMITER: Final[str] = "\n"

    def __init__(self, file_path: Path, year1: str, year2: str) -> None:
        self.file_path = file_path
        self.year1 = year1
        self.year2 = year2
        self.current_category: str | None = None
        self.current_county: str | None = None
        self.current_month_positions: dict[int, str] = {}
        self.current_year_map: dict[str, list[str]] = {year1: [], year2: []}

    def normalize(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Processes all raw rows from a Silver DataFrame and returns normalized records."""
        collected_rows: list[dict[str, Any]] = []

        for _, row in df.iterrows():
            raw_row = row[self.RAW_ROW_COLUMN]
            self._process_row(raw_row, collected_rows)

        return collected_rows

    def _process_row(self, raw_row: Sequence[Any], collected_rows: list[dict[str, Any]]) -> None:
        """Inspects a single raw row and updates state or appends normalized metrics."""
        self._check_title_row(raw_row)
        self._check_header_row(raw_row)

        if self._is_blank_row(raw_row):
            self.current_county = None

        if self._is_county_row(raw_row):
            self.current_county = COUNTIES_LOWER[str(raw_row[self.COUNTY_COLUMN_INDEX]).lower()]
        elif self.current_county is not None:
            self._collect_metric_rows(raw_row, collected_rows)

    def _check_title_row(self, raw_row: Sequence[Any]) -> None:
        """Detects a title row and extracts the canonical category if recognized."""
        first_cell = raw_row[self.TITLE_COLUMN_INDEX]
        if first_cell is not None and self.COURT_ADMIN_TITLE_MARKER in str(first_cell).lower():
            # Title looks like: "South Carolina Court Administration\n{Category} Monthly Caseload Report\nPeriod ..."
            raw_category = str(first_cell).split(self.NEWLINE_DELIMITER)[self.CATEGORY_TITLE_LINE_INDEX].lower()
            for cat_lower, cat_canonical in CATEGORY_LOWER.items():
                if cat_lower in raw_category:
                    self.current_category = cat_canonical
                    break

    def _check_header_row(self, raw_row: Sequence[Any]) -> None:
        """Detects a header row and updates month column positions and fiscal year map."""
        # Some PDFs insert extra columns (e.g. quarterly totals) between months,
        # so we record exact column positions rather than assuming a fixed layout.
        if any(
            str(cell).lower() in MONTHS_LOWER
            for cell in raw_row[self.HEADER_MONTH_SEARCH_START_INDEX:]
            if cell
        ):
            self.current_month_positions = {
                i: MONTHS_LOWER[str(cell).lower()]
                for i, cell in enumerate(raw_row)
                if str(cell).lower() in MONTHS_LOWER
            }

            # Build month -> fiscal year mapping. Report spans July (year1)
            # through June (year2); detect the year boundary by watching
            # for the month number decreasing (Dec=12 -> Jan=1).
            self.current_year_map = {self.year1: [], self.year2: []}
            current_year = self.year1
            months_list = list(self.current_month_positions.values())

            for i, month in enumerate(months_list):
                if (
                    i > self.FIRST_INDEX
                    and int(month) < int(months_list[i - self.PREVIOUS_INDEX_OFFSET])
                ):
                    current_year = self.year2  # Crossed from December into January
                self.current_year_map[current_year].append(month)

    @staticmethod
    def _is_blank_row(raw_row: Sequence[Any]) -> bool:
        """Returns True if every cell in raw_row is empty or None."""
        return all(cell == TableNormalizer.EMPTY_CELL or cell is None for cell in raw_row)

    @staticmethod
    def _is_county_row(raw_row: Sequence[Any]) -> bool:
        """Returns True if the first cell matches a known South Carolina county."""
        first_cell = raw_row[TableNormalizer.COUNTY_COLUMN_INDEX]
        return first_cell is not None and str(first_cell).lower() in COUNTIES_LOWER

    def _find_matching_metric(self, raw_row: Sequence[Any]) -> str | None:
        """Finds a matching metric according to current category rules."""
        if self.current_category in STANDARD_CATEGORIES:
            return MetricMatcher.find_in_row(raw_row, METRICS_LOWER)
        if self.current_category == CATEGORY_MENTAL_HEALTH:
            return MetricMatcher.find_in_row(raw_row, METRICS_MH_LOWER)
        return None

    def _collect_metric_rows(self, raw_row: Sequence[Any], collected_rows: list[dict[str, Any]]) -> None:
        """Collects one normalized output record per month if raw_row contains an expected metric."""
        metric = self._find_matching_metric(raw_row)
        if metric is None:
            return

        for col_index, month in self.current_month_positions.items():
            # Strip thousands-separator commas (e.g. "1,086" -> "1086").
            # DNR/TI are preserved as-is since they're not numeric commas.
            value = str(raw_row[col_index]).replace(self.COMMA_DELIMITER, self.EMPTY_STRING)
            assigned_year = self.year1 if month in self.current_year_map[self.year1] else self.year2
            collected_rows.append({
                FILE_COLUMN: self.file_path.name,
                CATEGORY_COLUMN: self.current_category,
                MONTH_COLUMN: int(month),
                YEAR_COLUMN: int(assigned_year),
                COUNTY_COLUMN: self.current_county,
                METRIC_COLUMN: metric,
                VALUE_COLUMN: value,
            })


class GoldPublisher:
    """Exports normalized rows to CSV and Parquet files and records provenance lineage."""

    CSV_EXTENSION: Final[str] = ".csv"
    PARQUET_EXTENSION: Final[str] = ".parquet"
    STAGE_NAME_GOLD: Final[str] = "gold"
    UTF8_ENCODING: Final[str] = "utf-8"
    GOLD_ARROW_SCHEMA: Final[pa.Schema] = pa.schema([
        (FILE_COLUMN, pa.string()),
        (CATEGORY_COLUMN, pa.string()),
        (MONTH_COLUMN, pa.int64()),
        (YEAR_COLUMN, pa.int64()),
        (COUNTY_COLUMN, pa.string()),
        (METRIC_COLUMN, pa.string()),
        (VALUE_COLUMN, pa.string()),
    ])

    @staticmethod
    def publish(
        collected_rows: list[dict[str, Any]],
        output_dir: Path,
        provenance_dir: Path,
        output_filename: str,
        silver_files_used: list[str],
    ) -> pd.DataFrame:
        """Writes collected rows to CSV and Parquet, logs provenance, and returns the DataFrame."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_csv = output_dir / f"{output_filename}{GoldPublisher.CSV_EXTENSION}"
        output_parquet = output_dir / f"{output_filename}{GoldPublisher.PARQUET_EXTENSION}"

        # Single source of truth — written to both CSV and Parquet so outputs never drift
        gold_df = pd.DataFrame(collected_rows, columns=SCHEMA)
        gold_df.to_csv(output_csv, index=False, encoding=GoldPublisher.UTF8_ENCODING)

        arrow_table = pa.Table.from_pandas(
            gold_df,
            schema=GoldPublisher.GOLD_ARROW_SCHEMA,
            preserve_index=False,
        )
        pq.write_table(arrow_table, output_parquet)

        logger.info(f"Wrote {len(gold_df)} rows to {output_csv.name} and {output_parquet.name}")

        # Lineage: this Gold output was derived from every Silver file processed
        log_provenance(
            provenance_dir,
            stage=GoldPublisher.STAGE_NAME_GOLD,
            file_path=output_csv,
            derived_from=silver_files_used,
        )
        log_provenance(
            provenance_dir,
            stage=GoldPublisher.STAGE_NAME_GOLD,
            file_path=output_parquet,
            derived_from=silver_files_used,
        )

        return gold_df


class SilverToGoldNormalizer:
    """High-level coordinator transforming Silver Parquet tables into Gold datasets."""

    def __init__(
        self,
        data_loader: SilverDataLoader | None = None,
        publisher: GoldPublisher | None = None,
    ) -> None:
        self.data_loader = data_loader or SilverDataLoader()
        self.publisher = publisher or GoldPublisher()

    def normalize(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
        provenance_dir: str | Path,
        output_filename: str = DEFAULT_OUTPUT_FILENAME,
    ) -> pd.DataFrame:
        """Reads Silver Parquet files and writes normalized Gold CSV and Parquet."""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        provenance_path = Path(provenance_dir)

        collected_rows: list[dict[str, Any]] = []
        silver_files_used: list[str] = []

        # sorted() for deterministic, reproducible output across runs
        for file_path in self.data_loader.find_parquet_files(input_path):
            logger.info(f"Starting extraction on: {file_path.name}")
            silver_files_used.append(file_path.name)

            year1, year2 = self.data_loader.extract_fiscal_years(file_path)
            df = self.data_loader.load_rows_dataframe(file_path)

            file_normalizer = TableNormalizer(file_path, year1, year2)
            file_rows = file_normalizer.normalize(df)
            collected_rows.extend(file_rows)

        return self.publisher.publish(
            collected_rows=collected_rows,
            output_dir=output_path,
            provenance_dir=provenance_path,
            output_filename=output_filename,
            silver_files_used=silver_files_used,
        )


def normalize_silver_to_gold(
    input_dir: str | Path,
    output_dir: str | Path,
    provenance_dir: str | Path,
    output_filename: str = DEFAULT_OUTPUT_FILENAME,
) -> pd.DataFrame:
    """Reads Silver Parquet files and writes a normalized Gold CSV and Parquet.

    Walks each Silver Parquet file row by row. Since the raw PDF table
    doesn't repeat context (category/county) on every row, this function
    tracks "current state" as it moves through the rows, updating that
    state whenever it recognizes a title, header, or county row, and
    collecting an output row whenever it recognizes a metric row.
    """
    normalizer = SilverToGoldNormalizer()
    return normalizer.normalize(
        input_dir=input_dir,
        output_dir=output_dir,
        provenance_dir=provenance_dir,
        output_filename=output_filename,
    )


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()

    base_dir = Path(__file__).resolve().parent.parent
    normalize_silver_to_gold(
        base_dir / "data/cases_silver",
        base_dir / "data/cases_gold",
        base_dir / "data/provenance",
    )
