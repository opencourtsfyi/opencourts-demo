import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest
import time_machine

from provenance import (
    PIPELINE_NAME,
    PIPELINE_VERSION,
    compute_file_hash,
    log_provenance,
)

LOG_FILENAME = "provenance_log.jsonl"
READ_CHUNK_BYTES = 8192
EXPECTED_RECORD_KEYS = {
    "pipeline_name",
    "pipeline_version",
    "stage",
    "filename",
    "file_hash",
    "retrieved_at",
    "source_url",
    "derived_from",
}
SAMPLE_CONTENT = b"%PDF-1.4 sample content"
FROZEN_TIME = dt.datetime(2024, 5, 17, 12, 30, 45, tzinfo=dt.timezone.utc)
SOURCE_URL = "https://example.com/report.pdf"


def make_artifact(tmp_path, name="artifact.pdf", content=SAMPLE_CONTENT):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def read_records(provenance_dir):
    text = (Path(provenance_dir) / LOG_FILENAME).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


# ==============================================================================
# compute_file_hash
# ==============================================================================

class TestComputeFileHash:
    def test_default_algorithm_is_sha256(self, tmp_path):
        path = make_artifact(tmp_path)

        assert compute_file_hash(path) == hashlib.sha256(SAMPLE_CONTENT).hexdigest()

    def test_accepts_str_path(self, tmp_path):
        path = make_artifact(tmp_path)

        assert compute_file_hash(str(path)) == hashlib.sha256(SAMPLE_CONTENT).hexdigest()

    def test_empty_file(self, tmp_path):
        path = make_artifact(tmp_path, content=b"")

        assert compute_file_hash(path) == hashlib.sha256(b"").hexdigest()

    @pytest.mark.parametrize("algo", ["md5", "sha1", "sha512"])
    def test_custom_algorithm(self, tmp_path, algo):
        path = make_artifact(tmp_path)

        assert compute_file_hash(path, algo=algo) == hashlib.new(algo, SAMPLE_CONTENT).hexdigest()

    @pytest.mark.parametrize(
        "size",
        [READ_CHUNK_BYTES - 1, READ_CHUNK_BYTES, READ_CHUNK_BYTES + 1, READ_CHUNK_BYTES * 3 + 5],
    )
    def test_chunk_boundaries_match_one_shot_hash(self, tmp_path, size):
        content = bytes(i % 251 for i in range(size))
        path = make_artifact(tmp_path, content=content)

        assert compute_file_hash(path) == hashlib.sha256(content).hexdigest()

    def test_reads_in_chunks_not_whole_file(self, tmp_path):
        content = b"a" * (READ_CHUNK_BYTES * 2 + 1)
        path = make_artifact(tmp_path, content=content)
        read_sizes = []
        real_open = open

        class SpyFile:
            def __init__(self, f):
                self._f = f

            def read(self, n=-1):
                read_sizes.append(n)
                return self._f.read(n)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return self._f.__exit__(*exc)

        def spy_open(*args, **kwargs):
            return SpyFile(real_open(*args, **kwargs))

        from unittest.mock import patch

        with patch("provenance.open", spy_open, create=True):
            compute_file_hash(path)

        assert set(read_sizes) == {READ_CHUNK_BYTES}

    def test_binary_content_is_not_text_decoded(self, tmp_path):
        content = b"\x00\xff\xfe\r\n\x80"
        path = make_artifact(tmp_path, content=content)

        assert compute_file_hash(path) == hashlib.sha256(content).hexdigest()

    def test_different_content_gives_different_hash(self, tmp_path):
        a = make_artifact(tmp_path, "a.bin", b"one")
        b = make_artifact(tmp_path, "b.bin", b"two")

        assert compute_file_hash(a) != compute_file_hash(b)

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            compute_file_hash(tmp_path / "missing.pdf")

    def test_directory_path_raises_os_error(self, tmp_path):
        with pytest.raises(OSError):
            compute_file_hash(tmp_path)

    def test_unknown_algorithm_raises_value_error(self, tmp_path):
        path = make_artifact(tmp_path)

        with pytest.raises(ValueError):
            compute_file_hash(path, algo="not-a-real-algo")

    def test_variable_length_shake_algorithm_raises_type_error(self, tmp_path):
        """Surprising: shake_* is accepted by hashlib.new but hexdigest() needs a length."""
        path = make_artifact(tmp_path)

        with pytest.raises(TypeError):
            compute_file_hash(path, algo="shake_128")

    def test_unknown_algorithm_checked_before_file_opened(self, tmp_path):
        """Algorithm validation happens first, so a bad algo wins over a missing file."""
        with pytest.raises(ValueError):
            compute_file_hash(tmp_path / "missing.pdf", algo="not-a-real-algo")


# ==============================================================================
# log_provenance
# ==============================================================================

class TestLogProvenance:
    def test_returns_record_with_expected_fields(self, tmp_path):
        artifact = make_artifact(tmp_path)

        with time_machine.travel(FROZEN_TIME, tick=False):
            record = log_provenance(tmp_path / "prov", "bronze", artifact, source_url=SOURCE_URL)

        assert set(record) == EXPECTED_RECORD_KEYS
        assert record["pipeline_name"] == PIPELINE_NAME
        assert record["pipeline_version"] == PIPELINE_VERSION
        assert record["stage"] == "bronze"
        assert record["filename"] == "artifact.pdf"
        assert record["file_hash"] == hashlib.sha256(SAMPLE_CONTENT).hexdigest()
        assert record["retrieved_at"] == FROZEN_TIME.isoformat()
        assert record["source_url"] == SOURCE_URL
        assert record["derived_from"] == []

    def test_written_line_equals_returned_record(self, tmp_path):
        artifact = make_artifact(tmp_path)
        prov_dir = tmp_path / "prov"

        record = log_provenance(prov_dir, "silver", artifact, derived_from=["a.pdf"])

        assert read_records(prov_dir) == [record]

    def test_log_file_is_single_json_line_with_trailing_newline(self, tmp_path):
        artifact = make_artifact(tmp_path)
        prov_dir = tmp_path / "prov"

        log_provenance(prov_dir, "bronze", artifact)

        raw = (prov_dir / LOG_FILENAME).read_bytes()
        assert raw.endswith(b"\n")
        assert raw.count(b"\n") == 1

    def test_defaults_source_url_none_and_derived_from_empty(self, tmp_path):
        artifact = make_artifact(tmp_path)

        record = log_provenance(tmp_path, "gold", artifact)

        assert record["source_url"] is None
        assert record["derived_from"] == []

    def test_empty_derived_from_list_is_normalised_to_new_empty_list(self, tmp_path):
        artifact = make_artifact(tmp_path)
        lineage = []

        record = log_provenance(tmp_path, "gold", artifact, derived_from=lineage)

        assert record["derived_from"] == []

    def test_derived_from_preserved_in_order(self, tmp_path):
        artifact = make_artifact(tmp_path, "gold.csv")
        lineage = ["silver_b.parquet", "silver_a.parquet"]

        record = log_provenance(tmp_path, "gold", artifact, derived_from=lineage)

        assert record["derived_from"] == lineage
        assert read_records(tmp_path)[0]["derived_from"] == lineage

    def test_filename_is_basename_only(self, tmp_path):
        nested = tmp_path / "deep" / "dir"
        nested.mkdir(parents=True)
        artifact = make_artifact(nested, "file.parquet")

        record = log_provenance(tmp_path / "prov", "silver", artifact)

        assert record["filename"] == "file.parquet"

    def test_accepts_str_paths(self, tmp_path):
        artifact = make_artifact(tmp_path)
        prov_dir = tmp_path / "prov"

        record = log_provenance(str(prov_dir), "bronze", str(artifact))

        assert record["filename"] == "artifact.pdf"
        assert (prov_dir / LOG_FILENAME).exists()

    def test_creates_nested_provenance_directory(self, tmp_path):
        artifact = make_artifact(tmp_path)
        prov_dir = tmp_path / "a" / "b" / "c"

        log_provenance(prov_dir, "bronze", artifact)

        assert (prov_dir / LOG_FILENAME).is_file()

    def test_existing_provenance_directory_is_reused(self, tmp_path):
        artifact = make_artifact(tmp_path)
        prov_dir = tmp_path / "prov"
        prov_dir.mkdir()

        log_provenance(prov_dir, "bronze", artifact)

        assert len(read_records(prov_dir)) == 1

    def test_appends_across_calls_without_modifying_earlier_records(self, tmp_path):
        first = make_artifact(tmp_path, "one.pdf", b"one")
        second = make_artifact(tmp_path, "two.pdf", b"two")
        prov_dir = tmp_path / "prov"

        rec1 = log_provenance(prov_dir, "bronze", first, source_url=SOURCE_URL)
        rec2 = log_provenance(prov_dir, "silver", second, derived_from=["one.pdf"])

        assert read_records(prov_dir) == [rec1, rec2]

    def test_appends_to_preexisting_log_content(self, tmp_path):
        artifact = make_artifact(tmp_path)
        prov_dir = tmp_path / "prov"
        prov_dir.mkdir()
        (prov_dir / LOG_FILENAME).write_text('{"existing": true}\n', encoding="utf-8")

        log_provenance(prov_dir, "bronze", artifact)

        records = read_records(prov_dir)
        assert records[0] == {"existing": True}
        assert len(records) == 2

    def test_same_file_logged_twice_creates_duplicate_records(self, tmp_path):
        """No de-duplication: logging is purely append-only."""
        artifact = make_artifact(tmp_path)

        log_provenance(tmp_path, "bronze", artifact)
        log_provenance(tmp_path, "bronze", artifact)

        assert len(read_records(tmp_path)) == 2

    def test_retrieved_at_is_timezone_aware_utc_iso(self, tmp_path):
        artifact = make_artifact(tmp_path)

        record = log_provenance(tmp_path, "bronze", artifact)

        parsed = dt.datetime.fromisoformat(record["retrieved_at"])
        assert parsed.utcoffset() == dt.timedelta(0)

    def test_hash_reflects_content_at_logging_time(self, tmp_path):
        artifact = make_artifact(tmp_path, content=b"v1")
        rec1 = log_provenance(tmp_path, "bronze", artifact)
        artifact.write_bytes(b"v2")
        rec2 = log_provenance(tmp_path, "bronze", artifact)

        assert rec1["file_hash"] == hashlib.sha256(b"v1").hexdigest()
        assert rec2["file_hash"] == hashlib.sha256(b"v2").hexdigest()

    def test_stage_is_not_validated(self, tmp_path):
        """Surprising: any value (even None or a typo) is accepted as stage."""
        artifact = make_artifact(tmp_path)

        assert log_provenance(tmp_path, "platinum", artifact)["stage"] == "platinum"
        assert log_provenance(tmp_path, None, artifact)["stage"] is None

    def test_non_ascii_values_are_escaped_and_round_trip(self, tmp_path):
        artifact = make_artifact(tmp_path, "café.pdf")
        url = "https://example.com/café"

        record = log_provenance(tmp_path, "bronze", artifact, source_url=url)

        raw = (tmp_path / LOG_FILENAME).read_text(encoding="ascii")  # ensure_ascii default
        assert "\\u00e9" in raw
        assert read_records(tmp_path)[0] == record

    def test_missing_artifact_raises_before_log_is_written(self, tmp_path):
        prov_dir = tmp_path / "prov"

        with pytest.raises(FileNotFoundError):
            log_provenance(prov_dir, "bronze", tmp_path / "missing.pdf")

        assert prov_dir.is_dir()  # directory is created before hashing...
        assert not (prov_dir / LOG_FILENAME).exists()  # ...but no record is written

    def test_non_serialisable_derived_from_raises_and_leaves_empty_log(self, tmp_path):
        """Surprising: the log is opened before serialising, so a failure leaves an empty file."""
        artifact = make_artifact(tmp_path)

        with pytest.raises(TypeError):
            log_provenance(tmp_path, "gold", artifact, derived_from=[object()])

        assert (tmp_path / LOG_FILENAME).read_bytes() == b""

    def test_path_objects_in_derived_from_are_not_serialisable(self, tmp_path):
        """Surprising: callers must pass str names; Path entries raise TypeError."""
        artifact = make_artifact(tmp_path)

        with pytest.raises(TypeError):
            log_provenance(tmp_path, "gold", artifact, derived_from=[Path("a.parquet")])

    def test_provenance_dir_that_is_a_file_raises(self, tmp_path):
        artifact = make_artifact(tmp_path)
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir")

        with pytest.raises(OSError):
            log_provenance(blocker, "bronze", artifact)

    def test_unwritable_log_propagates_error(self, tmp_path):
        from unittest.mock import patch

        artifact = make_artifact(tmp_path)

        with patch("provenance.open", side_effect=PermissionError("denied"), create=True):
            with pytest.raises(PermissionError, match="denied"):
                log_provenance(tmp_path / "prov", "bronze", artifact)

    def test_log_written_with_platform_default_encoding(self, tmp_path):
        """Characterization: open() has no explicit encoding; output is pure ASCII so it is safe."""
        artifact = make_artifact(tmp_path)

        log_provenance(tmp_path, "bronze", artifact, source_url="https://example.com/ü")

        raw = (tmp_path / LOG_FILENAME).read_bytes()
        assert raw.isascii()
