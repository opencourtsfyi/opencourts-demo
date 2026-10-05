# normalize_parquets.py
"""
Gold stage: reads Silver Parquet files (raw extracted PDF tables) and
normalizes them into a long-format dataset, one row per (county, metric,
month, year) data point, matching the project's target schema.

Writes the SAME in-memory rows to both CSV and Parquet, so the two output
formats can never drift apart from each other. Also logs a provenance/
lineage record linking the Gold output back to every Silver file that fed it.
"""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
import re

from provenance import log_provenance
from logging_config import get_logger

logger = get_logger(__name__)


# --- Reference data used to recognize and label rows during normalization ---

CATEGORY = ["Estate", "Guardian", "Conservator", "Mental Health"]

# Maps full month names (as they appear in the PDF headers) to their numeric string form
MONTHS = {
    "July": "7", "August": "8", "September": "9", "October": "10",
    "November": "11", "December": "12", "January": "1", "February": "2",
    "March": "3", "April": "4", "May": "5", "June": "6"
}

# All 46 South Carolina counties, used to detect county rows in the raw table
SC_COUNTIES = [
    "Abbeville", "Aiken", "Allendale", "Anderson", "Bamberg", "Barnwell", "Beaufort", "Berkeley",
    "Calhoun", "Charleston", "Cherokee", "Chester", "Chesterfield", "Clarendon", "Colleton",
    "Darlington", "Dillon", "Dorchester", "Edgefield", "Fairfield", "Florence", "Georgetown",
    "Greenville", "Greenwood", "Hampton", "Horry", "Jasper", "Kershaw", "Lancaster", "Laurens",
    "Lee", "Lexington", "Marion", "Marlboro", "McCormick", "Newberry", "Oconee", "Orangeburg",
    "Pickens", "Richland", "Saluda", "Spartanburg", "Sumter", "Union", "Williamsburg", "York"
]

# Metric labels differ by category. Estate/Guardian reports use 4 metrics;
# Mental Health reports use a different, smaller set (with footnote markers
# like "Orders*" in the raw PDF, handled by match_metric below).
EXPECTED_METRICS = ["Pending first of month", "Added", "Disposed", "Pending end of Month"]
EXPECTED_METRICS_MENTAL_HEALTH = ["Added", "Orders"]

# Column order for the output CSV/Parquet
SCHEMA = ["file", "category", "month", "year", "county", "metric", "value"]

# Pre-computed lowercase lookup dicts: {lowercase_version: canonical_version}
# Lets us match case-insensitively while outputting clean, consistently-cased
# labels regardless of how a given PDF year capitalized things.
CATEGORY_LOWER = {c.lower(): c for c in CATEGORY}
MONTHS_LOWER = {k.lower(): v for k, v in MONTHS.items()}
COUNTIES_LOWER = {c.lower(): c for c in SC_COUNTIES}
METRICS_LOWER = {m.lower(): m for m in EXPECTED_METRICS}
METRICS_MH_LOWER = {m.lower(): m for m in EXPECTED_METRICS_MENTAL_HEALTH}


def match_metric(item, metrics_lower_dict):
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


def normalize_silver_to_gold(input_dir, output_dir, provenance_dir, output_filename="caseloads_normalized"):
    """Reads Silver Parquet files and writes a normalized Gold CSV and Parquet.

    Walks each Silver Parquet file row by row. Since the raw PDF table
    doesn't repeat context (category/county) on every row, this function
    tracks "current state" as it moves through the rows, updating that
    state whenever it recognizes a title, header, or county row, and
    collecting an output row whenever it recognizes a metric row.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_csv = output_dir / f"{output_filename}.csv"
    output_parquet = output_dir / f"{output_filename}.parquet"

    collected_rows = []      # Single source of truth — written to both CSV and Parquet at the end
    silver_files_used = []   # Lineage: every Silver file that contributed to this Gold output

    # sorted() for deterministic, reproducible output across runs
    for file_path in sorted(input_dir.glob("*.parquet")):
        logger.info(f"Starting extraction on: {file_path.name}")
        silver_files_used.append(file_path.name)

        # Extract the two fiscal years from the filename by finding any
        # 4-digit numbers, rather than assuming a fixed position, since
        # filename suffixes (like "_bronze") can shift positional indexing.
        years_found = re.findall(r"\d{4}", file_path.stem)
        year1, year2 = years_found[0], years_found[1]

        # --- State variables, reset for every new file ---
        current_category = None       # e.g. "Estate", set when a title row is seen
        current_county = None         # e.g. "Abbeville", set when a county row is seen
        current_month_positions = {}  # {column_index: month_number}, set when a header row is seen
        current_year_map = {year1: [], year2: []}  # which months belong to which fiscal year

        df = pq.read_table(file_path).to_pandas()

        for _, row in df.iterrows():
            raw_row = row["raw_row"]  # One row from the original PDF table, as a list of cell strings

            # --- Detect a title row and extract the category ---
            # Title looks like: "South Carolina Court Administration\n{Category} Monthly Caseload Report\nPeriod ..."
            if raw_row[0] is not None and "court administration" in str(raw_row[0]).lower():
                raw_category = str(raw_row[0]).split("\n")[1].lower()  # 2nd line of the title
                for cat_lower, cat_canonical in CATEGORY_LOWER.items():
                    if cat_lower in raw_category:
                        current_category = cat_canonical
                        break

            # --- Detect a header row and build the month-to-column-index map ---
            # Some PDFs insert extra columns (e.g. quarterly totals) between months,
            # so we record exact column positions rather than assuming a fixed layout.
            if any(str(cell).lower() in MONTHS_LOWER for cell in raw_row[2:] if cell):
                current_month_positions = {
                    i: MONTHS_LOWER[str(cell).lower()]
                    for i, cell in enumerate(raw_row) if str(cell).lower() in MONTHS_LOWER
                }

                # Build month -> fiscal year mapping. Report spans July (year1)
                # through June (year2); detect the year boundary by watching
                # for the month number decreasing (Dec=12 -> Jan=1).
                current_year_map = {year1: [], year2: []}
                current_year = year1
                months_list = list(current_month_positions.values())

                for i, month in enumerate(months_list):
                    if i > 0 and int(month) < int(months_list[i - 1]):
                        current_year = year2  # Crossed from December into January
                    current_year_map[current_year].append(month)

            # --- Detect a blank separator row, signals the next county is coming ---
            # Reset current_county so a metric row can never accidentally attach
            # to a stale county from before the blank row.
            if all(cell == '' or cell is None for cell in raw_row):
                current_county = None

            # --- Detect a county row ---
            if raw_row[0] is not None and str(raw_row[0]).lower() in COUNTIES_LOWER:
                current_county = COUNTIES_LOWER[str(raw_row[0]).lower()]

            # --- Detect an Estate/Guardian metric row and collect one output row per month ---
            # Only runs if the county check above didn't match (elif), and only
            # if we currently have a county and category set, and this row
            # actually contains one of the expected metric labels.
            elif current_county is not None and current_category in ["Estate", "Guardian", "Conservator"] and any(
                (metric := match_metric(item, METRICS_LOWER)) for item in raw_row if match_metric(item, METRICS_LOWER)
            ):
                for col_index, month in current_month_positions.items():
                    # Strip thousands-separator commas (e.g. "1,086" -> "1086").
                    # DNR/TI are preserved as-is since they're not numeric commas.
                    value = str(raw_row[col_index]).replace(",", "")
                    assigned_year = year1 if month in current_year_map[year1] else year2
                    collected_rows.append({
                        "file": file_path.name, "category": current_category,
                        "month": int(month), "year": int(assigned_year),
                        "county": current_county, "metric": metric, "value": value,
                    })

            # --- Same as above, but for Mental Health rows, which use a different metric set ---
            elif current_county is not None and current_category in ["Mental Health"] and any(
                (metric := match_metric(item, METRICS_MH_LOWER)) for item in raw_row if match_metric(item, METRICS_MH_LOWER)
            ):
                for col_index, month in current_month_positions.items():
                    value = str(raw_row[col_index]).replace(",", "")
                    assigned_year = year1 if month in current_year_map[year1] else year2
                    collected_rows.append({
                        "file": file_path.name, "category": current_category,
                        "month": int(month), "year": int(assigned_year),
                        "county": current_county, "metric": metric, "value": value,
                    })

    # Build the final dataframe once, from every row collected across all Silver files
    gold_df = pd.DataFrame(collected_rows, columns=SCHEMA)
    gold_df.to_csv(output_csv, index=False)

    # Explicit schema at write time, same reasoning as Silver: enforced at
    # write time rather than silently inferred/miscast at read time
    gold_schema = pa.schema([
        ("file", pa.string()), ("category", pa.string()),
        ("month", pa.int64()), ("year", pa.int64()),
        ("county", pa.string()), ("metric", pa.string()), ("value", pa.string()),
    ])
    arrow_table = pa.Table.from_pandas(gold_df, schema=gold_schema, preserve_index=False)
    pq.write_table(arrow_table, output_parquet)

    logger.info(f"Wrote {len(gold_df)} rows to {output_csv.name} and {output_parquet.name}")

    # Lineage: this Gold output was derived from every Silver file processed above
    log_provenance(provenance_dir, stage="gold", file_path=output_csv, derived_from=silver_files_used)
    log_provenance(provenance_dir, stage="gold", file_path=output_parquet, derived_from=silver_files_used)

    return gold_df


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    normalize_silver_to_gold(
        base_dir / "data/cases_silver",
        base_dir / "data/cases_gold",
        base_dir / "data/provenance",
    )
