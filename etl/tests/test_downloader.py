import errno
import hashlib
import json
from http import HTTPStatus
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import time_machine

from downloader import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PDF_DIR,
    DEFAULT_PROVENANCE_DIR,
    DEFAULT_USER_AGENT,
    MAX_DOWNLOAD_ATTEMPTS,
    SouthCarolinaFiscalYear,
    POLITE_DELAY_MAX_SECONDS,
    POLITE_DELAY_MIN_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_MIN_WAIT_SECONDS,
    FileDownloader,
    MimeTypeMismatchError,
    build_urls,
    download_pdfs,
)


@pytest.fixture(autouse=True)
def mock_sleep():
    """Mock time.sleep across tests to prevent delays and capture sleep calls."""
    with patch("downloader.time.sleep") as sleep_mock:
        yield sleep_mock


def create_mock_response(status_code=200, content=b"%PDF-1.4 mock binary content", error=None):
    """Helper to build a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.content = content
    if error:
        resp.raise_for_status.side_effect = error
    else:
        resp.raise_for_status.return_value = None
    return resp


# ==============================================================================
# FileDownloader Test Suite
# ==============================================================================

class TestFileDownloader:
    def test_constructor_uses_default_settings(self):
        downloader = FileDownloader("https://example.com/report.pdf")

        assert downloader.url == "https://example.com/report.pdf"
        assert downloader.destination is None
        assert downloader.headers == {"User-Agent": DEFAULT_USER_AGENT}
        assert downloader.timeout == REQUEST_TIMEOUT_SECONDS
        assert downloader.max_attempts == MAX_DOWNLOAD_ATTEMPTS
        assert downloader.retry_min_wait == RETRY_MIN_WAIT_SECONDS
        assert downloader.retry_max_wait == RETRY_MAX_WAIT_SECONDS
        assert downloader.chunk_size == DEFAULT_CHUNK_SIZE

    def test_constructor_converts_destination_and_preserves_custom_settings(self, tmp_path):
        destination = tmp_path / "report.pdf"
        headers = {"Authorization": "Bearer test"}

        downloader = FileDownloader(
            "https://example.com/report.pdf",
            destination=str(destination),
            headers=headers,
            timeout=20,
            max_attempts=5,
            retry_min_wait=2.0,
            retry_max_wait=8.0,
            chunk_size=4096,
        )

        assert downloader.destination == destination
        assert downloader.headers is headers
        assert downloader.timeout == 20
        assert downloader.max_attempts == 5
        assert downloader.retry_min_wait == 2.0
        assert downloader.retry_max_wait == 8.0
        assert downloader.chunk_size == 4096

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://example.com/report.pdf", "application/pdf"),
            ("https://example.com/report.json?download=true", "application/json"),
            ("https://example.com/download", None),
        ],
    )
    def test_guess_content_type_from_url(self, url, expected):
        downloader = FileDownloader(url)

        assert downloader._guess_content_type() == expected

    def test_guess_content_type_accepts_url_override(self):
        downloader = FileDownloader("https://example.com/report.pdf")

        assert downloader._guess_content_type("https://example.com/data.json") == "application/json"

    def test_check_mime_type_accepts_matching_content(self):
        downloader = FileDownloader("https://example.com/report.pdf")

        downloader._check_mime_type(b"%PDF-1.4\nbody")

    def test_check_mime_type_rejects_mismatched_content(self):
        downloader = FileDownloader("https://example.com/report.pdf")

        with pytest.raises(MimeTypeMismatchError, match="text/plain"):
            downloader._check_mime_type(b"not a PDF")

    def test_check_mime_type_rejects_mismatched_response_header(self):
        downloader = FileDownloader("https://example.com/report.pdf")
        response = create_mock_response(content=b"%PDF-1.4\nbody")
        response.headers = {"Content-Type": "text/html; charset=utf-8"}

        with pytest.raises(MimeTypeMismatchError, match="text/html"):
            downloader._check_mime_type(response.content, response=response)

    def test_fetch_passes_configured_request_arguments(self):
        headers = {"X-Test": "value"}
        downloader = FileDownloader(
            "https://example.com/report.pdf",
            headers=headers,
            timeout=25,
        )
        response = create_mock_response()

        with patch("downloader.requests.get", return_value=response) as mock_get:
            assert downloader.fetch(downloader.url) is response

        mock_get.assert_called_once_with(
            downloader.url,
            headers=headers,
            timeout=25,
        )
        response.raise_for_status.assert_called_once_with()

    @pytest.mark.parametrize(
        "status",
        [
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
            HTTPStatus.TOO_MANY_REQUESTS,
        ],
    )
    def test_fetch_retries_retryable_http_errors(self, status):
        downloader = FileDownloader("https://example.com/report.pdf")
        error_response = MagicMock(spec=requests.Response)
        error_response.status_code = status
        http_error = requests.exceptions.HTTPError(
            f"{status.value} {status.phrase}",
            response=error_response,
        )
        response = create_mock_response()

        with patch(
            "downloader.requests.get",
            side_effect=[http_error, response],
        ) as mock_get:
            assert downloader.fetch(downloader.url) is response

        assert mock_get.call_count == 2

    @pytest.mark.parametrize(
        "network_exception",
        [
            requests.exceptions.ConnectTimeout("Connection timed out"),
            requests.exceptions.ReadTimeout("Read timed out"),
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.SSLError("SSL error"),
            requests.exceptions.ChunkedEncodingError("Incomplete response"),
        ],
    )
    def test_fetch_retries_retryable_network_errors(self, network_exception):
        downloader = FileDownloader("https://example.com/report.pdf")
        response = create_mock_response()

        with patch(
            "downloader.requests.get",
            side_effect=[network_exception, response],
        ) as mock_get:
            assert downloader.fetch(downloader.url) is response

        assert mock_get.call_count == 2

    def test_fetch_retry_backoff_is_within_configured_bounds(self, mock_sleep):
        downloader = FileDownloader("https://example.com/report.pdf")
        timeout_error = requests.exceptions.Timeout("request timed out")
        response = create_mock_response()

        with patch(
            "downloader.requests.get",
            side_effect=[timeout_error, response],
        ):
            assert downloader.fetch(downloader.url) is response

        mock_sleep.assert_called_once()
        retry_delay = mock_sleep.call_args.args[0]
        assert RETRY_MIN_WAIT_SECONDS <= retry_delay <= RETRY_MAX_WAIT_SECONDS

    def test_download_writes_to_configured_destination(self, tmp_path):
        destination = tmp_path / "nested" / "report.pdf"
        content = b"%PDF-1.4\nreport"
        downloader = FileDownloader("https://example.com/report.pdf", destination=destination)

        with patch("downloader.requests.get", return_value=create_mock_response(content=content)):
            result = downloader.download()

        assert result == destination
        assert destination.read_bytes() == content

    def test_download_can_overwrite_existing_file(self, tmp_path):
        destination = tmp_path / "report.pdf"
        destination.write_bytes(b"%PDF-1.4\nold report")
        new_content = b"%PDF-1.4\nupdated report"
        downloader = FileDownloader("https://example.com/report.pdf", destination=destination, overwrite_existing=True)

        with patch(
            "downloader.requests.get",
            return_value=create_mock_response(content=new_content),
        ):
            result = downloader.download()

        assert result == destination
        assert destination.read_bytes() == new_content

    def test_download_writes_in_chunks_using_iter_content(self, tmp_path):
        """FileDownloader writes streamed chunks to destination via iter_content."""
        destination = tmp_path / "chunked.pdf"
        custom_chunk_size = 16
        downloader = FileDownloader(
            "https://example.com/report.pdf",
            destination=destination,
            chunk_size=custom_chunk_size,
        )
        chunks = [b"%PDF-1.4\n", b"chunk-payload-1", b"chunk-payload-2"]
        expected_bytes = b"".join(chunks)

        response = create_mock_response(content=expected_bytes)
        response.iter_content = MagicMock(return_value=iter(chunks))

        with patch("downloader.requests.get", return_value=response):
            result = downloader.download()

        assert result == destination
        assert destination.read_bytes() == expected_bytes
        response.iter_content.assert_called_once_with(chunk_size=custom_chunk_size)

    def test_download_fallback_chunking_when_iter_content_unavailable(self, tmp_path):
        """When iter_content is empty or unavailable, fallback chunks response.content."""
        destination = tmp_path / "fallback_chunked.pdf"
        custom_chunk_size = 8
        downloader = FileDownloader(
            "https://example.com/report.pdf",
            destination=destination,
            chunk_size=custom_chunk_size,
        )
        full_content = b"%PDF-1.4\nfallback-data-stream"
        response = create_mock_response(content=full_content)
        response.iter_content = MagicMock(return_value=iter([]))

        with patch("downloader.requests.get", return_value=response):
            result = downloader.download()

        assert result == destination
        assert destination.read_bytes() == full_content


    def test_download_uses_url_filename_in_current_directory_when_destination_omitted(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        content = b"%PDF-1.4\nreport"
        downloader = FileDownloader("https://example.com/reports/report.pdf")

        with patch("downloader.requests.get", return_value=create_mock_response(content=content)):
            result = downloader.download()

        assert result == tmp_path / "report.pdf"
        assert result is not None
        assert result.read_bytes() == content

    def test_download_accepts_url_and_destination_overrides(self, tmp_path):
        content = b"%PDF-1.4\nreport"
        downloader = FileDownloader("https://example.com/original.pdf")
        destination = tmp_path / "override.pdf"
        url = "https://example.com/override.pdf"

        with patch("downloader.requests.get", return_value=create_mock_response(content=content)) as mock_get:
            result = downloader.download(url=url, destination=destination)

        assert result == destination
        assert destination.read_bytes() == content
        assert mock_get.call_args.args[0] == url

    def test_download_rejects_empty_url(self, tmp_path):
        downloader = FileDownloader("", destination=tmp_path / "report.pdf")

        with pytest.raises(ValueError, match="URL must be provided"):
            downloader.download()

    def test_download_rejects_url_without_filename(self):
        downloader = FileDownloader("https://example.com/")

        with pytest.raises(ValueError, match="URL must include a filename"):
            downloader.download()

    def test_download_propagates_invalid_url_error_without_retrying(self, tmp_path):
        downloader = FileDownloader("https://exa mple.com/report.pdf", destination=tmp_path / "report.pdf")
        invalid_url_error = requests.exceptions.InvalidURL("Invalid URL")

        with patch("downloader.requests.get", side_effect=invalid_url_error) as mock_get:
            with pytest.raises(requests.exceptions.InvalidURL, match="Invalid URL"):
                downloader.download()

        mock_get.assert_called_once()

    def test_download_does_not_write_mime_mismatched_content(self, tmp_path):
        destination = tmp_path / "report.pdf"
        downloader = FileDownloader("https://example.com/report.pdf", destination=destination)

        with patch("downloader.requests.get", return_value=create_mock_response(content=b"not a PDF")):
            with pytest.raises(MimeTypeMismatchError):
                downloader.download()

        assert not destination.exists()

    def test_download_file_write_permission_error(self, tmp_path):
        destination = tmp_path / "report.pdf"
        downloader = FileDownloader("https://example.com/report.pdf", destination=destination)
        response = create_mock_response(content=b"%PDF-1.4\nreport")

        with patch("downloader.requests.get", return_value=response), patch(
            "builtins.open",
            side_effect=PermissionError(errno.EACCES, "Permission denied"),
        ):
            with pytest.raises(PermissionError, match="Permission denied"):
                downloader.download()

    def test_download_disk_full_error(self, tmp_path):
        destination = tmp_path / "report.pdf"
        downloader = FileDownloader("https://example.com/report.pdf", destination=destination)
        response = create_mock_response(content=b"%PDF-1.4\nreport")
        real_open = open

        def failing_open(path, mode="r", *args, **kwargs):
            if "wb" in mode:
                raise OSError(errno.ENOSPC, "No space left on device")
            return real_open(path, mode, *args, **kwargs)

        with patch("downloader.requests.get", return_value=response), patch(
            "builtins.open",
            side_effect=failing_open,
        ):
            with pytest.raises(OSError) as exc_info:
                downloader.download()

        assert exc_info.value.errno == errno.ENOSPC

    def test_download_preserves_binary_content(self, tmp_path):
        destination = tmp_path / "report.pdf"
        downloader = FileDownloader("https://example.com/report.pdf", destination=destination)
        raw_binary = b"%PDF-1.5\n\x00\xff\xfe\r\n\n\x1a\x7f\x80\x99test stream"

        with patch(
            "downloader.requests.get",
            return_value=create_mock_response(content=raw_binary),
        ):
            downloader.download()

        assert destination.read_bytes() == raw_binary

    def test_download_rejects_empty_content(self, tmp_path):
        destination = tmp_path / "report.pdf"
        downloader = FileDownloader("https://example.com/report.pdf", destination=destination)

        with patch(
            "downloader.requests.get",
            return_value=create_mock_response(content=b""),
        ):
            with pytest.raises(MimeTypeMismatchError):
                downloader.download()

        assert not destination.exists()


# ==============================================================================
# SouthCarolinaFiscalYear Test Suite
# ==============================================================================

class TestSouthCarolinaFiscalYear:
    """Test suite for the SouthCarolinaFiscalYear domain class."""

    def test_init_from_integer(self):
        """Verify initialization from an integer fiscal year."""
        fy = SouthCarolinaFiscalYear(2023)
        assert fy.year == 2023
        assert fy.start_date == date(2022, 7, 1)
        assert fy.end_date == date(2023, 6, 30)

    def test_init_from_another_instance(self):
        """Verify initialization copy from an existing SouthCarolinaFiscalYear."""
        original = SouthCarolinaFiscalYear(2023)
        copy_fy = SouthCarolinaFiscalYear(original)
        assert copy_fy.year == 2023
        assert copy_fy.start_date == original.start_date
        assert copy_fy.end_date == original.end_date

    def test_start_year_and_end_year_properties(self):
        """Verify calendar year properties for start and end."""
        fy = SouthCarolinaFiscalYear(2023)
        assert fy.start_year == 2022
        assert fy.end_year == 2023

    @pytest.mark.parametrize(
        ("test_date", "expected_year"),
        [
            (date(2023, 6, 30), 2023),
            (date(2023, 7, 1), 2024),
            (date(2023, 1, 15), 2023),
            (date(2023, 12, 31), 2024),
        ],
    )
    def test_from_date(self, test_date, expected_year):
        """Verify from_date determines the correct fiscal year according to the July 1 boundary."""
        fy = SouthCarolinaFiscalYear.from_date(test_date)
        assert fy.year == expected_year

    @time_machine.travel("2025-06-30")
    def test_current_at_end_of_fiscal_year(self):
        """Verify current() before July 1 returns the ending fiscal year."""
        fy = SouthCarolinaFiscalYear.current()
        assert fy.year == 2025

    @time_machine.travel("2025-07-01")
    def test_current_at_beginning_of_fiscal_year(self):
        """Verify current() on July 1 returns the new fiscal year."""
        fy = SouthCarolinaFiscalYear.current()
        assert fy.year == 2026

    def test_previous_and_next(self):
        """Verify navigating to previous and next fiscal years."""
        fy = SouthCarolinaFiscalYear(2023)
        assert fy.previous() == SouthCarolinaFiscalYear(2022)
        assert fy.next() == SouthCarolinaFiscalYear(2024)

    def test_range_generates_inclusive_sequence(self):
        """Verify range generates all fiscal years in inclusive order."""
        start = SouthCarolinaFiscalYear(2020)
        end = SouthCarolinaFiscalYear(2023)
        years = list(SouthCarolinaFiscalYear.range(start, end))
        assert years == [
            SouthCarolinaFiscalYear(2020),
            SouthCarolinaFiscalYear(2021),
            SouthCarolinaFiscalYear(2022),
            SouthCarolinaFiscalYear(2023),
        ]

    def test_range_with_start_after_end_yields_empty(self):
        """Verify range yields nothing when start exceeds end."""
        start = SouthCarolinaFiscalYear(2023)
        end = SouthCarolinaFiscalYear(2020)
        assert list(SouthCarolinaFiscalYear.range(start, end)) == []

    def test_min_fiscal_year(self):
        """Verify min_fiscal_year returns MIN_FISCAL_YEAR (2008)."""
        min_fy = SouthCarolinaFiscalYear.min_fiscal_year()
        assert min_fy.year == 2008
        assert min_fy == SouthCarolinaFiscalYear(2008)

    def test_int_conversion(self):
        """Verify integer conversion returns the fiscal year ending year."""
        fy = SouthCarolinaFiscalYear(2023)
        assert int(fy) == 2023

    def test_string_representations(self):
        """Verify __str__ and __repr__ formatting."""
        fy = SouthCarolinaFiscalYear(2023)
        assert str(fy) == "FiscalYear(2023) is from 2022-07-01 to 2023-06-30, inclusive of both dates."
        assert repr(fy) == "FiscalYear(2023)"

    def test_equality_and_ordering_with_fiscal_year(self):
        """Verify comparison operators with other SouthCarolinaFiscalYear instances."""
        fy1 = SouthCarolinaFiscalYear(2022)
        fy2 = SouthCarolinaFiscalYear(2023)
        fy3 = SouthCarolinaFiscalYear(2022)

        assert fy1 == fy3
        assert fy1 != fy2
        assert fy1 < fy2
        assert fy1 <= fy2
        assert fy2 > fy1
        assert fy2 >= fy1
        assert fy1 <= fy3
        assert fy1 >= fy3

    def test_equality_and_ordering_with_integers(self):
        """Verify comparison operators with raw integer years."""
        fy = SouthCarolinaFiscalYear(2023)

        assert fy == 2023
        assert fy != 2022
        assert fy < 2024
        assert fy <= 2023
        assert fy > 2022
        assert fy >= 2023

    def test_equality_with_incompatible_type(self):
        """Verify equality returns False for incompatible types."""
        fy = SouthCarolinaFiscalYear(2023)
        assert fy != "2023"
        assert fy != [2023]

    def test_ordering_with_incompatible_type_raises_type_error(self):
        """Verify ordering operators raise TypeError for incompatible types."""
        fy = SouthCarolinaFiscalYear(2023)
        with pytest.raises(TypeError):
            _ = fy < "2023"

    def test_hashing_and_set_membership(self):
        """Verify hashability and uniqueness in sets and dict keys."""
        fy1 = SouthCarolinaFiscalYear(2023)
        fy2 = SouthCarolinaFiscalYear(2023)
        fy3 = SouthCarolinaFiscalYear(2024)

        assert hash(fy1) == hash(fy2)
        fy_set = {fy1, fy2, fy3}
        assert len(fy_set) == 2
        assert fy1 in fy_set
        assert fy3 in fy_set


# ==============================================================================
#  build_urls Test Suite
# ==============================================================================

class TestBuildURLs:
    """Test suite for the build_urls helper function."""

    def test_single_fiscal_year(self):
        """Verify build_urls formats the correct URL for a single fiscal year."""
        urls = build_urls(start_year=2021, end_year=2021)
        assert urls == [
            "https://www.sccourts.org/media/annualReports/2020-2021/CATotalsES2.pdf"
        ]

    def test_multi_year_range(self):
        """Verify build_urls returns all URLs in sequential fiscal year order."""
        urls = build_urls(start_year=2018, end_year=2020)
        assert urls == [
            "https://www.sccourts.org/media/annualReports/2017-2018/CATotalsES2.pdf",
            "https://www.sccourts.org/media/annualReports/2018-2019/CATotalsES2.pdf",
            "https://www.sccourts.org/media/annualReports/2019-2020/CATotalsES2.pdf",
        ]

    @time_machine.travel("2025-06-30")
    def test_default_end_year_uses_current_fiscal_year_end(self):
        """When end_year is omitted, use the current South Carolina fiscal year which runs from July 1 to June 30.
        This means 30 JUN 2025 is fiscal year 2025 and 1 JUL 2025 is fiscal year 2026.

        In this test, we are at the end of the fiscal year.
        """
        urls = build_urls(start_year=2023)
        assert urls == [
            "https://www.sccourts.org/media/annualReports/2022-2023/CATotalsES2.pdf",
            "https://www.sccourts.org/media/annualReports/2023-2024/CATotalsES2.pdf",
        ]

    @time_machine.travel("2025-07-1")
    def test_default_end_year_uses_current_fiscal_year_beginning(self):
        """When end_year is omitted, use the current South Carolina fiscal year which runs from July 1 to June 30.
        This means 30 JUN 2025 is fiscal year 2025 and 1 JUL 2025 is fiscal year 2026.

        In this test, we are at the beginning of the fiscal year.
        """
        urls = build_urls(start_year=2023)
        assert urls == [
            "https://www.sccourts.org/media/annualReports/2022-2023/CATotalsES2.pdf",
            "https://www.sccourts.org/media/annualReports/2023-2024/CATotalsES2.pdf",
            "https://www.sccourts.org/media/annualReports/2024-2025/CATotalsES2.pdf",
        ]

    @time_machine.travel("2009-10-11")
    def test_default_start_year_is_min_year(self):
        """When start_year is omitted, it defaults to MIN_YEAR (2008)."""
        urls = build_urls()
        assert urls == [
            "https://www.sccourts.org/media/annualReports/2007-2008/CATotalsES2.pdf",
            "https://www.sccourts.org/media/annualReports/2008-2009/CATotalsES2.pdf",
        ]

    def test_start_year_before_min_year_clamped(self):
        """Years before MIN_YEAR (2008) are clamped to MIN_YEAR."""
        urls = build_urls(start_year=2000, end_year=SouthCarolinaFiscalYear.min_fiscal_year())
        assert urls == [
            "https://www.sccourts.org/media/annualReports/2007-2008/CATotalsES2.pdf"
        ]

    def test_end_year_before_start_year_adjusted(self):
        """When end_year precedes start_year, end_year is adjusted to start_year."""
        urls = build_urls(start_year=2025, end_year=2024)
        assert urls == [
            "https://www.sccourts.org/media/annualReports/2024-2025/CATotalsES2.pdf"
        ]

    @time_machine.travel("2009-10-11")
    def test_both_arguments_explicitly_none(self):
        """When both start_year and end_year are explicitly None, defaults are applied."""
        urls = build_urls(start_year=None, end_year=None)
        assert urls == [
            "https://www.sccourts.org/media/annualReports/2007-2008/CATotalsES2.pdf",
            "https://www.sccourts.org/media/annualReports/2008-2009/CATotalsES2.pdf",
        ]

# ==============================================================================
# download_pdfs Test Suite
# ==============================================================================

class TestDownloadPDFs:
    def test_download_single_year_success(self, tmp_path, mock_sleep):
        """Test successful single-year download: URL formatting, headers, binary write, provenance, delays."""
        out_dir = tmp_path / "pdfs_bronze"
        prov_dir = tmp_path / "provenance"
        mock_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (SC Probate) >>\nendobj\n%%EOF"

        with patch("downloader.requests.get") as mock_get:
            mock_get.return_value = create_mock_response(content=mock_pdf_bytes)

            download_pdfs(out_dir, prov_dir, start_year=2021, end_year=2021)

            # Verify request parameters
            expected_url = "https://www.sccourts.org/media/annualReports/2020-2021/CATotalsES2.pdf"
            mock_get.assert_called_once_with(
                expected_url,
                headers={"User-Agent": DEFAULT_USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            # Verify output file
            target_file = out_dir / "estate_monthly_caseload_2020_to_2021_bronze.pdf"
            assert target_file.exists()
            assert target_file.read_bytes() == mock_pdf_bytes

            # Verify provenance record
            prov_file = prov_dir / "provenance_log.jsonl"
            assert prov_file.exists()
            records = [json.loads(line) for line in prov_file.read_text().splitlines() if line.strip()]
            assert len(records) == 1
            record = records[0]
            assert record["stage"] == "bronze"
            assert record["filename"] == "estate_monthly_caseload_2020_to_2021_bronze.pdf"
            assert record["source_url"] == expected_url
            assert record["file_hash"] == hashlib.sha256(mock_pdf_bytes).hexdigest()

            # Verify polite delay was called once for the successful download
            assert mock_sleep.call_count == 1
            sleep_arg = mock_sleep.call_args[0][0]
            assert POLITE_DELAY_MIN_SECONDS <= sleep_arg <= POLITE_DELAY_MAX_SECONDS


    def test_download_multi_year_range(self, tmp_path):
        """Test downloading a sequential range of multiple fiscal years."""
        out_dir = tmp_path / "pdfs"
        prov_dir = tmp_path / "prov"

        with patch("downloader.requests.get") as mock_get:
            mock_get.return_value = create_mock_response(content=b"%PDF-1.4\nmulti-year test")

            download_pdfs(out_dir, prov_dir, start_year=2018, end_year=2020)

            assert mock_get.call_count == 3
            expected_years = [(2017, 2018), (2018, 2019), (2019, 2020)]
            for start, end in expected_years:
                pdf_path = out_dir / f"estate_monthly_caseload_{start}_to_{end}_bronze.pdf"
                assert pdf_path.exists()

            records = [json.loads(line) for line in (prov_dir / "provenance_log.jsonl").read_text().splitlines()]
            assert len(records) == 3


    @time_machine.travel("2025-10-11")
    def test_download_default_end_year(self, tmp_path):
        """When end_year is omitted, it attempts reports through the current year."""
        out_dir = tmp_path / "pdfs"
        prov_dir = tmp_path / "prov"

        with patch("downloader.requests.get") as mock_get:
            mock_get.return_value = create_mock_response(content=b"%PDF-1.4\ndefault end year")

            # should download 2023-2024, 2024-2025
            download_pdfs(out_dir, prov_dir, start_year=2023)

            assert mock_get.call_count == 3
            assert (out_dir / "estate_monthly_caseload_2022_to_2023_bronze.pdf").exists()
            assert (out_dir / "estate_monthly_caseload_2023_to_2024_bronze.pdf").exists()
            assert (out_dir / "estate_monthly_caseload_2024_to_2025_bronze.pdf").exists()

    @time_machine.travel("2025-10-11")
    def test_download_default_end_year_attempts_unavailable_current_report(self, tmp_path):
        """An unavailable current-year report is attempted without undoing earlier downloads."""
        out_dir = tmp_path / "pdfs"
        prov_dir = tmp_path / "prov"

        unavailable_report = requests.exceptions.HTTPError("404 Not Found")
        with patch(
            "downloader.requests.get",
            side_effect=[
                create_mock_response(content=b"%PDF-1.4\n2023 report"),
                create_mock_response(content=b"%PDF-1.4\n2024 report"),
                *([unavailable_report] * MAX_DOWNLOAD_ATTEMPTS),
            ],
        ) as mock_get:
            download_pdfs(out_dir, prov_dir, start_year=2023)

        requested_urls = [call.args[0] for call in mock_get.call_args_list]
        assert requested_urls == [
            "https://www.sccourts.org/media/annualReports/2022-2023/CATotalsES2.pdf",
            "https://www.sccourts.org/media/annualReports/2023-2024/CATotalsES2.pdf",
            *(
                ["https://www.sccourts.org/media/annualReports/2024-2025/CATotalsES2.pdf"]
                * MAX_DOWNLOAD_ATTEMPTS
            ),
        ]
        assert (out_dir / "estate_monthly_caseload_2022_to_2023_bronze.pdf").exists()
        assert (out_dir / "estate_monthly_caseload_2023_to_2024_bronze.pdf").exists()
        assert not (out_dir / "estate_monthly_caseload_2024_to_2025_bronze.pdf").exists()


    def test_paths_accepted_as_strings_and_path_objects(self, tmp_path):
        """Ensure download_pdfs works cleanly with both str and pathlib.Path inputs."""
        str_out = tmp_path / "str_pdfs"
        str_prov = tmp_path / "str_prov"

        with patch("downloader.requests.get") as mock_get:
            mock_get.return_value = create_mock_response(content=b"%PDF-1.4\nstring path test")
            download_pdfs(str_out, str_prov, start_year=2020, end_year=2020)

            assert Path(str_out).exists()
            assert (Path(str_out) / "estate_monthly_caseload_2019_to_2020_bronze.pdf").exists()
            assert (Path(str_prov) / "provenance_log.jsonl").exists()

    @time_machine.travel("2008-10-11")
    def test_download_all_arguments_omitted_uses_defaults(self, tmp_path, monkeypatch):
        """When called with no arguments, download_pdfs creates default directories and runs."""
        monkeypatch.chdir(tmp_path)

        with patch("downloader.requests.get") as mock_get:
            mock_get.return_value = create_mock_response(content=b"%PDF-1.4\ndefault test")

            download_pdfs()

            expected_pdf_path = tmp_path / DEFAULT_PDF_DIR / "estate_monthly_caseload_2007_to_2008_bronze.pdf"
            expected_prov_path = tmp_path / DEFAULT_PROVENANCE_DIR / "provenance_log.jsonl"
            assert expected_pdf_path.exists()
            assert expected_prov_path.exists()

    @time_machine.travel("2008-10-11")
    def test_download_all_arguments_explicitly_none(self, tmp_path, monkeypatch):
        """When called with None for all arguments, download_pdfs uses defaults."""
        monkeypatch.chdir(tmp_path)

        with patch("downloader.requests.get") as mock_get:
            mock_get.return_value = create_mock_response(content=b"%PDF-1.4\nnone test")

            download_pdfs(output_dir=None, provenance_dir=None, start_year=None, end_year=None)

            expected_pdf_path = tmp_path / DEFAULT_PDF_DIR / "estate_monthly_caseload_2007_to_2008_bronze.pdf"
            expected_prov_path = tmp_path / DEFAULT_PROVENANCE_DIR / "provenance_log.jsonl"
            assert expected_pdf_path.exists()
            assert expected_prov_path.exists()


    # ==============================================================================
    # Idempotency & Caching / Skipping Tests
    # ==============================================================================

    def test_skip_already_downloaded_files(self, tmp_path):
        """Files that already exist on disk must be skipped without network calls or duplicate provenance."""
        out_dir = tmp_path / "pdfs"
        prov_dir = tmp_path / "prov"
        out_dir.mkdir(parents=True)

        existing_file = out_dir / "estate_monthly_caseload_2020_to_2021_bronze.pdf"
        existing_content = b"original unmodified content"
        existing_file.write_bytes(existing_content)

        with patch("downloader.requests.get") as mock_get:
            download_pdfs(out_dir, prov_dir, start_year=2021, end_year=2021)

            mock_get.assert_not_called()
            assert existing_file.read_bytes() == existing_content
            assert not (prov_dir / "provenance_log.jsonl").exists()


    def test_partial_run_skips_existing_and_downloads_missing(self, tmp_path):
        """When some files exist and some are missing, only missing files are downloaded."""
        out_dir = tmp_path / "pdfs"
        prov_dir = tmp_path / "prov"
        out_dir.mkdir(parents=True)

        existing_2019 = out_dir / "estate_monthly_caseload_2018_to_2019_bronze.pdf"

        # Warning: This is a mock PDF file. We just used the header to pass the mime check.
        existing_2019.write_bytes(b"%PDF-1.4\nexisting-2019")

        with patch("downloader.requests.get") as mock_get:
            mock_get.return_value = create_mock_response(content=b"%PDF-1.4\nnew-2020")
            download_pdfs(out_dir, prov_dir, start_year=2019, end_year=2020)

            assert mock_get.call_count == 1
            called_url = mock_get.call_args[0][0]
            assert "2019-2020" in called_url

            records = [json.loads(line) for line in (prov_dir / "provenance_log.jsonl").read_text().splitlines()]
            assert len(records) == 1
            assert records[0]["filename"] == "estate_monthly_caseload_2019_to_2020_bronze.pdf"



    def test_interrupted_download_leaves_no_partial_file_and_reattempts(self, tmp_path):
        """When a download is interrupted mid-write, provenance is not recorded,
        no partial file is left behind, and a subsequent run downloads the file rather than skipping."""
        out_dir = tmp_path / "pdfs"
        prov_dir = tmp_path / "prov"
        target_file = out_dir / "estate_monthly_caseload_2020_to_2021_bronze.pdf"
        prov_file = prov_dir / "provenance_log.jsonl"
        full_content = b"%PDF-1.4\nfull complete report content"

        def interrupted_chunks():
            yield b"%PDF-1.4\npartial truncated content"
            raise requests.exceptions.ChunkedEncodingError("Connection broken mid-download")

        interrupted_resp = create_mock_response(content=full_content)
        interrupted_resp.iter_content = MagicMock(return_value=interrupted_chunks())

        success_resp = create_mock_response(content=full_content)
        success_resp.iter_content = MagicMock(return_value=iter([full_content]))

        # First run: interrupted during streaming
        with patch("downloader.requests.get", return_value=interrupted_resp):
            download_pdfs(out_dir, prov_dir, start_year=2021, end_year=2021)

        # Ensure no partial file exists and provenance was not recorded
        assert not target_file.exists()
        assert not prov_file.exists()
        assert list(out_dir.glob("*.tmp")) == []

        # Second run: reattempting the download successfully downloads the file instead of skipping
        with patch("downloader.requests.get", return_value=success_resp) as mock_get_retry:
            download_pdfs(out_dir, prov_dir, start_year=2021, end_year=2021)

            mock_get_retry.assert_called_once()
            assert target_file.exists()
            assert target_file.read_bytes() == full_content
            assert prov_file.exists()
            records = [json.loads(line) for line in prov_file.read_text().splitlines() if line.strip()]
            assert len(records) == 1
            assert records[0]["filename"] == target_file.name


    # ==============================================================================
    # Network Failures & Transient Retry Tests
    # ==============================================================================

    def test_exhausted_retries_logs_error_and_continues_to_next_year(self, tmp_path):
        """When retries are exhausted, log the failure and continue to the next report."""
        out_dir = tmp_path / "pdfs"
        prov_dir = tmp_path / "prov"

        fail_err = requests.exceptions.HTTPError("404 Not Found")
        succ_resp = create_mock_response(status_code=200, content=b"%PDF-1.4\nyear 2 success")

        # The first year exhausts retries; the next year succeeds immediately.
        side_effects = [fail_err] * MAX_DOWNLOAD_ATTEMPTS + [succ_resp]

        with patch("downloader.requests.get", side_effect=side_effects) as mock_get, \
             patch("downloader.logger.error") as mock_log_err:
            download_pdfs(out_dir, prov_dir, start_year=2020, end_year=2021)

            assert mock_get.call_count == MAX_DOWNLOAD_ATTEMPTS + 1

            # 2020 file was not created, but 2021 file was
            assert not (out_dir / "estate_monthly_caseload_2019_to_2020_bronze.pdf").exists()
            assert (out_dir / "estate_monthly_caseload_2020_to_2021_bronze.pdf").exists()

            # Logger logged error for failed 2020
            mock_log_err.assert_called_once()
            assert "estate_monthly_caseload_2019_to_2020_bronze.pdf" in mock_log_err.call_args[0][0]

            # Provenance only recorded for 2021
            records = [json.loads(line) for line in (prov_dir / "provenance_log.jsonl").read_text().splitlines()]
            assert len(records) == 1
            assert records[0]["filename"] == "estate_monthly_caseload_2020_to_2021_bronze.pdf"


    # ==============================================================================
    # Cross-Platform File System Differences (Windows vs macOS vs Linux)
    # ==============================================================================

    def test_nested_paths_with_spaces_and_special_characters(self, tmp_path):
        """Nested paths with special characters are created across supported platforms."""
        special_out = tmp_path / "Court Data (2024)" / "Bronze [Probate] - SC" / "reports"
        special_prov = tmp_path / "Audit Logs & Lineage" / "runs" / "v1"

        with patch("downloader.requests.get") as mock_get:
            mock_get.return_value = create_mock_response(content=b"%PDF-1.4\nspecial chars test")
            download_pdfs(special_out, special_prov, start_year=2021, end_year=2021)

            assert special_out.is_dir()
            assert special_prov.is_dir()
            assert (special_out / "estate_monthly_caseload_2020_to_2021_bronze.pdf").exists()
            assert (special_prov / "provenance_log.jsonl").exists()


    def test_output_dir_is_existing_file_raises_os_error(self, tmp_path):
        """When output_dir is an existing file (not a folder), mkdir raises FileExistsError/OSError."""
        blocked_path = tmp_path / "not_a_dir"
        blocked_path.write_text("i am a file")

        with pytest.raises(OSError):
            download_pdfs(blocked_path, tmp_path / "prov", start_year=2021, end_year=2021)


    # ==============================================================================
    # Provenance Failure Handling
    # ==============================================================================


    def test_provenance_failure_propagates_to_caller(self, tmp_path):
        """If provenance directory is unwritable or log_provenance fails, exception bubbles up."""
        out_dir = tmp_path / "pdfs"
        prov_dir = tmp_path / "prov"

        with patch("downloader.requests.get") as mock_get, \
             patch("downloader.log_provenance", side_effect=PermissionError("Cannot write provenance")):
            mock_get.return_value = create_mock_response(content=b"%PDF-1.4\ntest")

            with pytest.raises(PermissionError) as exc_info:
                download_pdfs(out_dir, prov_dir, start_year=2021, end_year=2021)

            assert "Cannot write provenance" in str(exc_info.value)