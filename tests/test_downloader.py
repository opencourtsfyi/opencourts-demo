import logging

import downloader


def test_download_pdfs_skips_existing_files(tmp_path, monkeypatch, caplog):
    output_dir = tmp_path / "bronze"
    output_dir.mkdir()
    provenance_dir = tmp_path / "provenance"
    existing = output_dir / "estate_monthly_caseload_2007_to_2008_bronze.pdf"
    existing.write_bytes(b"existing")

    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        raise AssertionError("HTTP should not be called when the file already exists")

    monkeypatch.setattr(downloader.requests, "get", fake_get)

    with caplog.at_level(logging.INFO):
        downloader.download_pdfs(output_dir, provenance_dir, start_year=2007, end_year=2007)

    assert calls == []
    assert "Skipping: estate_monthly_caseload_2007_to_2008_bronze.pdf (already exists)" in caplog.text


def test_download_pdfs_retries_and_succeeds(tmp_path, monkeypatch):
    output_dir = tmp_path / "bronze"
    provenance_dir = tmp_path / "provenance"

    responses = iter([
        downloader.requests.exceptions.RequestException("boom"),
        type("Resp", (), {"content": b"pdf-content", "raise_for_status": lambda self: None})(),
    ])

    def fake_get(url, headers=None, timeout=None):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(downloader.requests, "get", fake_get)
    monkeypatch.setattr(downloader.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(downloader.random, "uniform", lambda *_args, **_kwargs: 0)

    downloader.download_pdfs(output_dir, provenance_dir, start_year=2007, end_year=2007)

    assert (output_dir / "estate_monthly_caseload_2007_to_2008_bronze.pdf").exists()
    assert (provenance_dir / "provenance_log.jsonl").exists()


def test_download_pdfs_logs_failure_after_retries(tmp_path, monkeypatch, caplog):
    output_dir = tmp_path / "bronze"
    provenance_dir = tmp_path / "provenance"

    class FakeResponse:
        def raise_for_status(self):
            raise downloader.requests.exceptions.RequestException("bad status")

    def fake_get(url, headers=None, timeout=None):
        return FakeResponse()

    monkeypatch.setattr(downloader.requests, "get", fake_get)
    monkeypatch.setattr(downloader.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(downloader.random, "uniform", lambda *_args, **_kwargs: 0)

    with caplog.at_level(logging.WARNING):
        downloader.download_pdfs(output_dir, provenance_dir, start_year=2007, end_year=2007)

    assert "Failed to download estate_monthly_caseload_2007_to_2008_bronze.pdf after 3 attempts." in caplog.text
    assert not (output_dir / "estate_monthly_caseload_2007_to_2008_bronze.pdf").exists()


def test_download_pdfs_uses_default_end_year_when_not_provided(monkeypatch, tmp_path):
    output_dir = tmp_path / "bronze"
    provenance_dir = tmp_path / "provenance"
    calls = []

    monkeypatch.setattr(downloader.time, "localtime", lambda: type("T", (), {"tm_year": 2024})())

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)

        class Response:
            content = b"pdf"

            def raise_for_status(self):
                return None

        return Response()

    monkeypatch.setattr(downloader.requests, "get", fake_get)
    monkeypatch.setattr(downloader.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(downloader.random, "uniform", lambda *_args, **_kwargs: 0)

    downloader.download_pdfs(output_dir, provenance_dir, start_year=2023)

    assert calls == ["https://www.sccourts.org/media/annualReports/2023-2024/CATotalsES2.pdf"]
