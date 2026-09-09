import logging
import os

import orchestrator


def test_run_pipeline_logs_issue_count_and_calls_each_stage(monkeypatch, caplog):
    calls = []

    def fake_download_pdfs(output_dir, provenance_dir, start_year=2007, end_year=None):
        calls.append(("download", output_dir, provenance_dir))

    def fake_extract_pdfs_to_silver(input_dir, output_dir, provenance_dir):
        calls.append(("extract", input_dir, output_dir, provenance_dir))

    def fake_normalize_silver_to_gold(input_dir, output_dir, provenance_dir, output_filename="caseloads_normalized"):
        calls.append(("normalize", input_dir, output_dir, provenance_dir, output_filename))

    def fake_validate_gold_csv(csv_path, logger=None):
        calls.append(("validate", csv_path, logger))
        return ["bad data"]

    monkeypatch.setattr(orchestrator, "download_pdfs", fake_download_pdfs)
    monkeypatch.setattr(orchestrator, "extract_pdfs_to_silver", fake_extract_pdfs_to_silver)
    monkeypatch.setattr(orchestrator, "normalize_silver_to_gold", fake_normalize_silver_to_gold)
    monkeypatch.setattr(orchestrator, "validate_gold_csv", fake_validate_gold_csv)

    with caplog.at_level(logging.INFO):
        orchestrator.run_pipeline()

    assert os.environ.get("PIPELINE_LOG_DIR") is not None
    assert [label for label, *_ in calls] == ["download", "extract", "normalize", "validate"]
    assert "Pipeline completed with 1 validation issue(s). Review before publishing." in caplog.text


def test_run_pipeline_logs_success_when_no_issues(monkeypatch, caplog):
    monkeypatch.setattr(orchestrator, "download_pdfs", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "extract_pdfs_to_silver", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "normalize_silver_to_gold", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "validate_gold_csv", lambda csv_path, logger=None: [])

    with caplog.at_level(logging.INFO):
        orchestrator.run_pipeline()

    assert "Pipeline completed successfully. All validation checks passed." in caplog.text
