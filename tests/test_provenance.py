import json

from provenance import compute_file_hash, log_provenance


def test_compute_file_hash_returns_sha256_digest(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("hello from provenance", encoding="utf-8")

    digest = compute_file_hash(artifact)

    assert len(digest) == 64
    assert digest == __import__("hashlib").sha256(b"hello from provenance").hexdigest()


def test_log_provenance_appends_json_record(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("payload", encoding="utf-8")

    record = log_provenance(
        tmp_path,
        stage="gold",
        file_path=artifact,
        source_url="https://example.com/source",
        derived_from=["silver_1.parquet"],
    )

    log_file = tmp_path / "provenance_log.jsonl"
    assert log_file.exists()

    data = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert data["filename"] == "artifact.txt"
    assert data["stage"] == "gold"
    assert data["source_url"] == "https://example.com/source"
    assert data["derived_from"] == ["silver_1.parquet"]
    assert data["file_hash"] == record["file_hash"]
