# provenance.py
"""
Provenance and lineage tracking for the SC Probate Caseload ETL pipeline.
Satisfies FR-10 (provenance: source URL, timestamp, hash, pipeline
version) and lineage requirement (linking Gold back to Silver and Bronze).

Appends one JSON record per artifact to data/provenance/provenance_log.jsonl.
JSON Lines (one JSON object per line) is used instead of a single JSON array
so the log can be safely appended to across many separate pipeline runs
without needing to read and rewrite the whole file each time.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_NAME = "sc_probate_caseload_etl"
PIPELINE_VERSION = "1.0.0"  # Bump this when pipeline logic changes meaningfully


def compute_file_hash(file_path, algo="sha256"):
    """Computes a hash of the file's exact contents, used to verify integrity
    and detect if two files claiming to be the same artifact actually differ.

    Reads the file in 8KB chunks rather than loading it all into memory at
    once, so this works safely even on large PDFs or Parquet files.
    """
    h = hashlib.new(algo)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def log_provenance(provenance_dir, stage, file_path, source_url=None, derived_from=None):
    """Appends one provenance record describing a single artifact.

    stage: "bronze" | "silver" | "gold" — which pipeline tier produced this file
    file_path: path to the artifact that was just written
    source_url: the original download URL (only meaningful for Bronze artifacts)
    derived_from: list of filenames this artifact was built from — this is
                  the lineage mechanism, e.g. a Silver file's derived_from
                  points at the one Bronze PDF it came from, and a Gold
                  file's derived_from lists every Silver file that fed it.
    """
    provenance_dir = Path(provenance_dir)
    provenance_dir.mkdir(parents=True, exist_ok=True)
    log_path = provenance_dir / "provenance_log.jsonl"

    record = {
        "pipeline_name": PIPELINE_NAME,
        "pipeline_version": PIPELINE_VERSION,
        "stage": stage,
        "filename": Path(file_path).name,
        "file_hash": compute_file_hash(file_path),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),  # UTC, timezone-aware
        "source_url": source_url,
        "derived_from": derived_from or [],
    }

    # "a" = append mode, so each call adds one line without disturbing prior records
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    return record