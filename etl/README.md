# ETL

This folder contains the local-only data processing code for the demo. The ETL work is responsible for downloading source documents, converting or normalizing them into structured data, and producing the staged outputs used by the app.

## Overview
South Carolina's court administration publishes annually a probate caseload
statistic as PDF reports, broken out by month, county and case category. This
pipeline extracts, cleans, and normalizes those reports into a single
long-format dataset suitable for time-series analysis, cross-county
comparison, and integration into downstream data portals.

The pipeline follows a **Bronze / Silver / Gold** medallion architecture,
a standard pattern in data engineering that separates raw ingestion,
cleaned transformation, and publication-ready output into distinct,
independently reproducible stages.

The ETL layer supports the demo's Bronze -> Silver -> Gold pattern:

- Bronze: raw source data, including downloaded PDFs and minimally processed content
- Silver: cleaned, normalized, and structured data ready for downstream use
- Gold: curated, query-ready data prepared for presentation or consumption

Every artifact the pipeline produces is hashed and logged with full
provenance and lineage, so any row in the final dataset can be traced
back to the exact source file and download it came from.

## Architecture

| Stage | Responsibility | Module | Output |
|---|---|---|---|
| **Bronze** | Ingest raw source PDFs | `downloader.py` | `data/pdfs_bronze/*.pdf` |
| **Silver** | Extract raw tabular data from each PDF | `pdf_extraction.py` | `data/cases_silver/*.parquet` |
| **Gold** | Normalize and publish the final dataset | `normalize_parquets.py` | `data/cases_gold/caseloads_normalized.{csv,parquet}` |
| **Validation** | Verify structural and content integrity of the Gold dataset | `validate_pipeline.py` | Pass/fail report, logged |
| **Orchestration** | Run all stages in sequence | `orchestrator.py` | — |

**Bronze** preserves the original source artifact, untouched, as
downloaded. **Silver** contains the same data in a machine-readable form,
extracted but not yet interpreted — table rows as they appear in the
source document. **Gold** is the fully normalized, semantically labeled
dataset intended for consumption by analysts and downstream systems.

Separating these stages means the pipeline can be re-run from any point
without repeating earlier, more expensive work — for example, fixing a
bug in normalization logic requires only re-running Gold generation
against existing Silver files, not re-downloading or re-extracting from
source PDFs.

---

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.10 or later (uses the walrus operator and modern
`pathlib` conventions).

## Usage

Run the full pipeline:

```bash
python orchestrator.py
```

This downloads any source reports not already present, extracts and
normalizes all available data, and validates the resulting Gold dataset.
Re-running is safe and idempotent: already-downloaded reports and
already-extracted tables are skipped, and the Gold dataset is rebuilt
in full from all available Silver data on each run.

Individual stages can also be run independently, which is useful when
iterating on a single part of the pipeline:

```bash
python downloader.py           # Bronze only
python pdf_extraction.py       # Silver only
python normalize_parquets.py   # Gold only
python validate_pipeline.py    # Validate an existing Gold dataset
```

---

## Output schema

The Gold dataset is a long-format table — one row per data point, rather
than one row per county or report — which makes it straightforward to
filter, aggregate, and join without reshaping.

| Column | Type | Description |
|---|---|---|
| `file` | string | Source report filename this row was derived from |
| `category` | string | Case category: `Estate`, `Guardian`, `Conservator`, or `Mental Health` |
| `month` | integer | Month of the reporting period (1–12) |
| `year` | integer | Calendar year corresponding to that month |
| `county` | string | One of South Carolina's 46 counties |
| `metric` | string | The measured statistic (see below) |
| `value` | string | The reported figure, or a coded data-quality state |

**Metrics by category:**

- `Estate`, `Guardian`, `Conservator`: `Pending first of month`, `Added`,
  `Disposed`, `Pending end of Month`
- `Mental Health`: `Added`, `Orders`

**Coded values:**

| Value | Meaning |
|---|---|
| *(numeric)* | Reported case count |
| `DNR` | Data Not Received — the county did not report a figure for this period |
| `TI` | Technical Issue — data collection was disrupted for this figure |
| *(empty)* | The source report left this cell blank |

Coded and blank values are preserved as-is rather than removed or
imputed, since they represent real reporting conditions rather than
extraction errors.

---

## Provenance and lineage

Every file the pipeline produces is recorded in
`data/provenance/provenance_log.jsonl`, one JSON record per artifact:

```json
{
  "pipeline_name": "sc_probate_caseload_etl",
  "pipeline_version": "1.0.0",
  "stage": "silver",
  "filename": "estate_monthly_caseload_2023_to_2024_bronze.parquet",
  "file_hash": "sha256...",
  "retrieved_at": "2026-07-06T18:03:11+00:00",
  "source_url": null,
  "derived_from": ["estate_monthly_caseload_2023_to_2024_bronze.pdf"]
}
```

`source_url` is populated for Bronze artifacts and identifies the exact
report URL a file was downloaded from. `derived_from` links each
artifact to the upstream file(s) it was built from, allowing any row in
the Gold dataset to be traced back through Silver to the original
Bronze PDF and its source URL.

---

## Data validation

After each full run, `validate_pipeline.py` checks the Gold dataset for:

- Correct column structure
- Category, county, and metric values drawn only from known valid sets
- Month and year values within expected ranges
- Metrics consistent with their reported category
- Values that are numeric, a recognized data-quality code, or blank
- No duplicate records for the same file, category, month, year, county,
  and metric

Validation results are written to the shared pipeline log alongside
every other stage's activity.

---

## Logging

All pipeline activity is logged to both the console and
`data/logs/pipeline.log`, providing a complete, timestamped record of
each run — downloads attempted, pages extracted, rows normalized, and
validation results — independent of whether the console output is
still available afterward.
## Testing
To run the ETL tests, install the developer dependencies and run pytest:
```bash
pip install -r requirements-dev.txt
pytest
```
