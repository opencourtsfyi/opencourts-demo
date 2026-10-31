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

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Final, Sequence

PIPELINE_NAME: Final[str] = "sc_probate_caseload_etl"
PIPELINE_VERSION: Final[str] = "1.0.0"  # Bump this when pipeline logic changes meaningfully

DEFAULT_HASH_ALGORITHM: Final[str] = "sha256"
DEFAULT_HASH_CHUNK_SIZE_BYTES: Final[int] = 8192

FILE_MODE_READ_BINARY: Final[str] = "rb"
EMPTY_BYTES_SENTINEL: Final[bytes] = b""

STAGE_BRONZE: Final[str] = "bronze"
STAGE_SILVER: Final[str] = "silver"
STAGE_GOLD: Final[str] = "gold"


@dataclass(frozen=True)
class ProvenanceRecord:
    """Represents an immutable provenance record for a pipeline artifact."""

    pipeline_name: str
    pipeline_version: str
    stage: str | None
    filename: str
    file_hash: str
    retrieved_at: str
    source_url: str | None = None
    derived_from: Sequence[str] | Any = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the record to a dictionary matching the lineage schema."""
        return {
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "stage": self.stage,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "retrieved_at": self.retrieved_at,
            "source_url": self.source_url,
            "derived_from": self.derived_from if self.derived_from is not None else [],
        }


def compute_file_hash(
    file_path: str | Path,
    algo: str = DEFAULT_HASH_ALGORITHM,
    chunk_size: int = DEFAULT_HASH_CHUNK_SIZE_BYTES,
) -> str:
    """Computes a cryptographic hash of a file's contents in chunks.

    Reads the file in binary chunks rather than loading it all into memory
    at once, working safely even on large PDFs or Parquet files.
    Validates algorithm name prior to opening the file.

    Args:
        file_path: Path to the target file.
        algo: Name of the hashing algorithm supported by hashlib.
        chunk_size: Chunk size in bytes for streaming file reads.

    Returns:
        Hexadecimal hash digest string.
    """
    hasher = hashlib.new(algo)
    with open(file_path, FILE_MODE_READ_BINARY) as f:
        for chunk in iter(lambda: f.read(chunk_size), EMPTY_BYTES_SENTINEL):
            hasher.update(chunk)
    return hasher.hexdigest()


class ProvenanceTracker:
    """Tracks and logs data provenance and lineage across ETL pipeline stages.

    Encapsulates artifact hashing, metadata record generation, and appending
    to the JSON Lines log file.
    """

    DEFAULT_PROVENANCE_LOG_FILENAME: Final[str] = "provenance_log.jsonl"
    LOG_ENCODING: Final[str] = "utf-8"
    FILE_MODE_APPEND: Final[str] = "a"
    RECORD_DELIMITER: Final[str] = "\n"

    def __init__(
        self,
        provenance_dir: str | Path,
        log_filename: str = DEFAULT_PROVENANCE_LOG_FILENAME,
        pipeline_name: str = PIPELINE_NAME,
        pipeline_version: str = PIPELINE_VERSION,
        chunk_size: int = DEFAULT_HASH_CHUNK_SIZE_BYTES,
        encoding: str = LOG_ENCODING,
    ) -> None:
        self.provenance_dir = Path(provenance_dir)
        self.log_filename = log_filename
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.chunk_size = chunk_size
        self.encoding = encoding

    @property
    def log_path(self) -> Path:
        """Returns the full path to the provenance log file."""
        return self.provenance_dir / self.log_filename

    def record_artifact(
        self,
        stage: str | None,
        file_path: str | Path,
        source_url: str | None = None,
        derived_from: Any = None,
        hash_algo: str = DEFAULT_HASH_ALGORITHM,
    ) -> dict[str, Any]:
        """Appends one provenance record describing a single artifact.

        Args:
            stage: "bronze" | "silver" | "gold" — pipeline tier that produced the file.
            file_path: Path to the artifact that was written.
            source_url: Original download URL (only meaningful for Bronze artifacts).
            derived_from: List of filenames this artifact was built from.
            hash_algo: Hashing algorithm to use.

        Returns:
            The serialized record as a dictionary.
        """
        self.provenance_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = Path(file_path)
        file_hash = compute_file_hash(
            artifact_path,
            algo=hash_algo,
            chunk_size=self.chunk_size,
        )

        record = ProvenanceRecord(
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
            stage=stage,
            filename=artifact_path.name,
            file_hash=file_hash,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            source_url=source_url,
            derived_from=derived_from,
        )
        record_dict = record.to_dict()

        # Append mode ensures each call adds one line without disturbing prior records.
        # Opening before serializing guarantees deterministic file creation semantics:
        # if serialization fails (e.g. non-serializable objects in derived_from), the
        # log file has already been opened/created and remains empty as expected.
        with open(self.log_path, self.FILE_MODE_APPEND, encoding=self.encoding) as f:
            serialized_record = json.dumps(record_dict) + self.RECORD_DELIMITER
            f.write(serialized_record)

        return record_dict


def log_provenance(
    provenance_dir: str | Path,
    stage: str | None,
    file_path: str | Path,
    source_url: str | None = None,
    derived_from: Any = None,
) -> dict[str, Any]:
    """Appends one provenance record describing a single artifact.

    stage: "bronze" | "silver" | "gold" — which pipeline tier produced this file
    file_path: path to the artifact that was just written
    source_url: the original download URL (only meaningful for Bronze artifacts)
    derived_from: list of filenames this artifact was built from — this is
                  the lineage mechanism, e.g. a Silver file's derived_from
                  points at the one Bronze PDF it came from, and a Gold
                  file's derived_from lists every Silver file that fed it.
    """
    tracker = ProvenanceTracker(provenance_dir=provenance_dir)
    return tracker.record_artifact(
        stage=stage,
        file_path=file_path,
        source_url=source_url,
        derived_from=derived_from,
    )
