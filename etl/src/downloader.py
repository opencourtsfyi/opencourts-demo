# downloader.py
"""
Bronze stage: downloads raw SC Probate Estate Monthly Caseload PDF reports
from the SC Courts website and saves them locally, untouched, as the
preserved source artifact (Bronze tier of the Medallion architecture).
Also logs a provenance record for every successfully downloaded file.
"""

import argparse
import logging
import mimetypes
from collections.abc import Generator, Mapping
from pathlib import Path
import random
import re
import time
import urllib.parse
from datetime import date

import magic
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random,
)

from logging_config import get_logger
from provenance import log_provenance
from i18n import t

logger = get_logger(__name__)

MIN_YEAR = 2008  # The first year for which the SC Courts website has data
FISCAL_YEAR_START_MONTH = 7
DEFAULT_USER_AGENT = "Mozilla/5.0"  # Mimic a browser to avoid being blocked
REQUEST_TIMEOUT_SECONDS = 10
MAX_DOWNLOAD_ATTEMPTS = 3
RETRY_MIN_WAIT_SECONDS = 1.0
RETRY_MAX_WAIT_SECONDS = 5.0
POLITE_DELAY_MIN_SECONDS = 1.0
POLITE_DELAY_MAX_SECONDS = 5.0
DEFAULT_CHUNK_SIZE = 8192

PROVENANCE_STAGE_BRONZE = "bronze"
BRONZE_FILENAME_TEMPLATE = "estate_monthly_caseload_{year}_to_{next_year}_bronze.pdf"
YEAR_RANGE_REGEX = re.compile(r"(\d{4})-(\d{4})")

DEFAULT_PDF_DIR = "data/pdfs_bronze"
DEFAULT_PROVENANCE_DIR = "data/provenance"

HEADER_USER_AGENT = "User-Agent"
HEADER_CONTENT_TYPE = "Content-Type"
FILE_WRITE_BINARY_MODE = "wb"
HEADER_SEPARATOR = ";"

PDF_MIME_TYPE = "application/pdf"
OCTET_STREAM_MIME_TYPE = "application/octet-stream"
SUPPORTED_TYPES = [PDF_MIME_TYPE]

# Localized message templates and errors loaded from locale files
LOG_ATTEMPT_DOWNLOAD = t("downloader.log_attempt_download")
LOG_DOWNLOAD_SUCCESS = t("downloader.log_download_success")
LOG_SKIP_ALREADY_EXISTS = t("downloader.log_skip_already_exists")
LOG_FAILED_DOWNLOAD_ATTEMPTS = t("downloader.log_failed_download_attempts")
LOG_FAILED_DOWNLOAD_ERROR = t("downloader.log_failed_download_error")

ERROR_URL_REQUIRED = t("downloader.error_url_required")
ERROR_DESTINATION_REQUIRED = t("downloader.error_destination_required")
ERROR_FILENAME_REQUIRED = t("downloader.error_filename_required")
ERROR_MIME_MISMATCH_TEMPLATE = t("downloader.error_mime_mismatch")

RETRYABLE_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.HTTPError,
)


class MimeTypeMismatchError(ValueError):
    """Raised when downloaded content is not a supported type."""
    pass


class FileDownloader:
    """Download one file, accepting only supported MIME types."""

    def __init__(
        self,
        url: str,
        destination: Path | str | None = None,
        headers: dict | None = None,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
        max_attempts: int = MAX_DOWNLOAD_ATTEMPTS,
        retry_min_wait: float = RETRY_MIN_WAIT_SECONDS,
        retry_max_wait: float = RETRY_MAX_WAIT_SECONDS,
        overwrite_existing: bool = False,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        """Configure a downloader for a URL and optional request settings.

        Args:
            url: URL to fetch. A missing or empty URL is rejected by ``download``.
            destination: Default output file path. If omitted, the file is saved
                in the current working directory using the URL's final path segment.
            headers: Request headers. Defaults to a browser-like User-Agent.
            timeout: Request timeout in seconds.
            max_attempts: Maximum number of attempts for retryable request failures.
            retry_min_wait: Minimum delay in seconds between retries.
            retry_max_wait: Maximum delay in seconds between retries.
            overwrite_existing: If False, skip downloading when the destination exists.
            chunk_size: Size in bytes of each chunk written during download. Default: 8192.

        Invalid URL syntax or a URL without a filename raises an error; URL-related
        request exceptions are not retried unless they are in the retryable set.
        """
        self.url = url
        self.destination = Path(destination) if destination is not None else None
        self.headers = headers if headers is not None else {HEADER_USER_AGENT: DEFAULT_USER_AGENT}
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.overwrite_existing = overwrite_existing
        self.chunk_size = chunk_size

    def _guess_content_type(self, url: str | None = None) -> str | None:
        """Helper method to guesses the expected MIME content type based on the URL extension."""
        target_url = url or self.url
        if not target_url:
            return None
        parsed_path = urllib.parse.urlsplit(target_url).path or target_url
        content_type, _ = mimetypes.guess_type(parsed_path)
        return content_type

    def _check_mime_type(
        self,
        content: bytes,
        expected_mime_type: str | None = None,
        response: requests.Response | None = None,
        url: str | None = None,
    ) -> None:
        """Helper method that checks the URL's expected MIME type and the downloaded content type.

        Raises MimeTypeMismatchError if either type is not supported.
        """
        expected = expected_mime_type or self._guess_content_type(url)
        self._ensure_supported_mime_type(expected or OCTET_STREAM_MIME_TYPE, url=url)

        detected = magic.from_buffer(content, mime=True)
        self._ensure_supported_mime_type(detected, url=url)

        if response is not None:
            headers = getattr(response, "headers", None)
            if isinstance(headers, Mapping):
                raw_header = headers.get(HEADER_CONTENT_TYPE)
                if isinstance(raw_header, str) and raw_header:
                    header_mime = raw_header.split(HEADER_SEPARATOR)[0].strip().lower()
                    if header_mime not in (PDF_MIME_TYPE, OCTET_STREAM_MIME_TYPE):
                        self._ensure_supported_mime_type(header_mime, url=url)

    def _ensure_supported_mime_type(self, detected: str, url: str | None = None) -> None:
        """Helper method. Raise when a MIME type is not in the supported-type list."""
        if detected.lower() not in SUPPORTED_TYPES:
            supported = ", ".join(SUPPORTED_TYPES)
            raise MimeTypeMismatchError(
                t(
                    "downloader.error_mime_mismatch",
                    detected=detected,
                    supported=supported,
                    url=url or self.url or "",
                )
            )

    @retry(
        stop=stop_after_attempt(MAX_DOWNLOAD_ATTEMPTS),
        wait=wait_random(min=RETRY_MIN_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        sleep=lambda delay: time.sleep(delay),
        reraise=True,
    )
    def fetch(self, url: str) -> requests.Response:
        """Fetches the response from the URL with retry logic."""
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response


    def _iter_chunks(
        self,
        response: requests.Response,
        chunk_size: int | None = None,
    ) -> Generator[bytes, None, None]:
        """Yields chunks of data from response.iter_content or response.content."""
        effective_chunk_size = chunk_size if chunk_size is not None else self.chunk_size
        if hasattr(response, "iter_content"):
            try:
                chunks = response.iter_content(chunk_size=effective_chunk_size)
                iterator = iter(chunks)
                first_chunk = next(iterator)
                if isinstance(first_chunk, (bytes, bytearray)):
                    yield bytes(first_chunk)
                    for chunk in iterator:
                        if chunk:
                            yield bytes(chunk)
                    return
            except (StopIteration, TypeError):
                pass

        content = getattr(response, "content", None)
        if isinstance(content, (bytes, bytearray)):
            for i in range(0, len(content), effective_chunk_size):
                yield bytes(content[i : i + effective_chunk_size])

    def download(
        self,
        url: str | None = None,
        destination: Path | str | None = None,
    ) -> Path | None:
        """Download a file, returning None when an existing destination is skipped."""
        target_url = url or self.url
        if not target_url:
            raise ValueError(t("downloader.error_url_required"))

        target_dest = Path(destination) if destination is not None else self.destination
        if target_dest is None:
            filename = Path(urllib.parse.urlsplit(target_url).path).name
            if not filename:
                raise ValueError(t("downloader.error_filename_required"))
            target_dest = Path.cwd() / filename
        if not target_dest:
            raise ValueError(t("downloader.error_destination_required"))

        filename = target_dest.name
        if target_dest.exists() and not self.overwrite_existing:
            logger.info(t("downloader.log_skip_already_exists", filename=filename))
            return None

        logger.info(t("downloader.log_attempt_download", filename=filename))

        expected_mime_type = self._guess_content_type(target_url) or OCTET_STREAM_MIME_TYPE
        self._ensure_supported_mime_type(expected_mime_type, url=target_url)
        response = self.fetch(target_url)

        self._check_mime_type(
            response.content,
            expected_mime_type=expected_mime_type,
            response=response,
            url=target_url,
        )

        target_dest.parent.mkdir(parents=True, exist_ok=True)
        with open(target_dest, FILE_WRITE_BINARY_MODE) as f:
            for chunk in self._iter_chunks(response):
                f.write(chunk)

        logger.info(t("downloader.log_download_success", filename=filename))
        return target_dest


def build_urls(start_year: int | None = None, end_year: int | None = None) -> list[str]:
    """Helper method to find the report URLs. The South Carolina Courts website uses a calendar-year based URL 
    pattern to represent a fiscal year (July through June). For example, the fiscal year 2023 (July 1, 2022 - June 30, 2023)
    is represented in the URL as "2022-2023".

    start_year: first fiscal-year start year, e.g. 2007 covers calendar year 1 JUL 2006 - 30 JUN 2007. Default: MIN_YEAR. If start_year is less than MIN_YEAR, it will be set to MIN_YEAR.
    end_year: last fiscal-year to include. If end_year is less than start_year, it will be set to start_year. Defaults to the previous fiscal year. 
    """
    if start_year is None:
        start_year = MIN_YEAR
    else:
        start_year = max(start_year, MIN_YEAR)

    if end_year is None:
        # Determine the previous fiscal year based on today's date
        today = date.today()
        current_fiscal_year  = today.year+1 if today.month >= FISCAL_YEAR_START_MONTH else today.year

        # Use the previous fiscal year as the end_year because the courts only publish reports for the already closed out fiscal years. 
        # For example, if today is 1 JUL 2026, the current fiscal year is 2027 (1 JUL 2026 - 30 JUN 2027), but the most recent report
        # available is for fiscal year 2026 (1 JUL 2025 - 30 JUN 2026).
        end_year = current_fiscal_year - 1 #use the previous fiscal year as the default end_year

    if end_year < start_year:
        end_year = start_year

    urls = []
    for fiscal_year in range(start_year, end_year + 1):
        url = f"https://www.sccourts.org/media/annualReports/{fiscal_year-1}-{fiscal_year}/CATotalsES2.pdf"
        urls.append(url)
    return urls


def download_pdfs(
    output_dir: Path | str | None = None,
    provenance_dir: Path | str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    overwrite_existing: bool = False,
) -> None:
    """Downloads SC Probate estate monthly caseload PDFs into output_dir.
    South Carolina fiscal year runs from 1 JUL to 30 JUN, so calendar date 1 JUL 2026 is in Fiscal year 2027.

    Each report covers a fiscal year (July through June), so the SC Courts
    URL pattern uses two consecutive years, e.g. 2022-2023 representing July 2022 - June 2023.

    output_dir: directory the downloaded PDFs are written to (created
                if it doesn't already exist, including all intermediate directories).
                Default: Path.cwd() / DEFAULT_PDF_DIR
    provenance_dir: directory the provenance log (provenance_log.jsonl) is
                     written/appended to for each successfully downloaded file. (creates dir if not already exist
                     including all intermediate directories.)
                     Default: Path.cwd() / DEFAULT_PROVENANCE_DIR
    start_year: first fiscal-year start year to attempt, e.g. 2007 pulls the
                JUL2006- JUN 2007 report. Default: 2007
    end_year: last fiscal-year to include e.g. 2007 pulls Jul 2006-30 JUN 2007 Default: previous calendar year
    """
    base_dir = Path.cwd()
    if output_dir is None:
        output_dir = base_dir / DEFAULT_PDF_DIR
    else:
        output_dir = Path(output_dir)

    if provenance_dir is None:
        provenance_dir = base_dir / DEFAULT_PROVENANCE_DIR
    else:
        provenance_dir = Path(provenance_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    provenance_dir.mkdir(parents=True, exist_ok=True) 

    urls = build_urls(start_year=start_year, end_year=end_year)

    for url in urls:
        match = YEAR_RANGE_REGEX.search(url)
        if match:
            year, next_year = match.groups()
            filename = BRONZE_FILENAME_TEMPLATE.format(year=year, next_year=next_year)
        else:
            filename = Path(url).name
        filepath = output_dir / filename

        try:
            downloader = FileDownloader(
                url=url,
                destination=filepath,
                overwrite_existing=overwrite_existing,
            )
            downloaded_path = downloader.download()
            if downloaded_path is None:
                continue
        except requests.exceptions.RequestException:
            logger.error(
                t(
                    "downloader.log_failed_download_attempts",
                    filename=filename,
                    attempts=MAX_DOWNLOAD_ATTEMPTS,
                )
            )
            continue
        except MimeTypeMismatchError as err:
            logger.error(
                t(
                    "downloader.log_failed_download_error",
                    filename=filename,
                    error=str(err),
                )
            )
            continue

        # Record provenance the moment a Bronze artifact exists on disk:
        # which URL it came from, when, and its content hash
        log_provenance(provenance_dir, stage=PROVENANCE_STAGE_BRONZE, file_path=filepath, source_url=url)

        # Polite delay between files so we don't hit the server too fast
        delay = random.uniform(POLITE_DELAY_MIN_SECONDS, POLITE_DELAY_MAX_SECONDS)
        time.sleep(delay)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments for downloader.py."""
    parser = argparse.ArgumentParser(description=t("downloader.cli_description"))
    parser.add_argument(
        "--overwrite-existing",
        "--overwrite",
        dest="overwrite_existing",
        action="store_true",
        default=False,
        help=t("downloader.cli_help_overwrite_existing"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=t("downloader.cli_help_output_dir"),
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> None:
    """CLI entry point for downloader.py."""
    cli_args = parse_args(args)
    download_pdfs(
        output_dir=cli_args.output_dir,
        overwrite_existing=cli_args.overwrite_existing,
    )


# Only runs when this file is executed directly, not when imported by the orchestrator
if __name__ == "__main__":
    main()
