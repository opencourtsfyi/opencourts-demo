from __future__ import annotations
# downloader.py
"""
Downloads raw SC Probate Estate Monthly Caseload PDF reports
from the SC Courts website and saves them locally, untouched, as the
preserved source artifact (Bronze tier of the Medallion architecture).
Also logs a provenance record for every successfully downloaded file.
"""

import argparse
import logging
import mimetypes
from collections.abc import Generator, Mapping
from functools import total_ordering
from pathlib import Path
import random
import re
import time
import urllib.parse
import uuid
from datetime import date
from typing import Final

import magic
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random,
)

from provenance import log_provenance
from i18n import t

logger = logging.getLogger(__name__)
from typing import Final

ANNUAL_REPORT_URL_TEMPLATE: Final[str] = "https://www.sccourts.org/media/annualReports/{start_year}-{end_year}/CATotalsES2.pdf"
DEFAULT_USER_AGENT: Final[str] = "Mozilla/5.0"  # Mimic a browser to avoid being blocked
REQUEST_TIMEOUT_SECONDS: Final[int] = 10
MAX_DOWNLOAD_ATTEMPTS: Final[int] = 3
RETRY_MIN_WAIT_SECONDS: Final[float] = 1.0
RETRY_MAX_WAIT_SECONDS: Final[float] = 5.0
POLITE_DELAY_MIN_SECONDS: Final[float] = 1.0
POLITE_DELAY_MAX_SECONDS: Final[float] = 5.0
DEFAULT_CHUNK_SIZE: Final[int] = 8192

PROVENANCE_STAGE_BRONZE: Final[str] = "bronze"
BRONZE_FILENAME_TEMPLATE: Final[str] = "estate_monthly_caseload_{year}_to_{next_year}_bronze.pdf"
YEAR_RANGE_REGEX: Final[re.Pattern] = re.compile(r"(\d{4})-(\d{4})")

DEFAULT_PDF_DIR: Final[str] = "data/pdfs_bronze"
DEFAULT_PROVENANCE_DIR: Final[str] = "data/provenance"

HEADER_USER_AGENT: Final[str] = "User-Agent"
HEADER_CONTENT_TYPE: Final[str] = "Content-Type"
FILE_WRITE_BINARY_MODE: Final[str] = "wb"
TEMP_FILE_PREFIX: Final[str] = "."
TEMP_FILE_SUFFIX: Final[str] = ".tmp"
HEADER_SEPARATOR: Final[str] = ";"

PDF_MIME_TYPE: Final[str] = "application/pdf"
OCTET_STREAM_MIME_TYPE: Final[str] = "application/octet-stream"
SUPPORTED_TYPES: Final[list[str]] = [PDF_MIME_TYPE]

# Localized message templates and errors loaded from locale files
LOG_ATTEMPT_DOWNLOAD: Final[str] = t("downloader.log_attempt_download")
LOG_DOWNLOAD_SUCCESS: Final[str] = t("downloader.log_download_success")
LOG_SKIP_ALREADY_EXISTS: Final[str] = t("downloader.log_skip_already_exists")
LOG_FAILED_DOWNLOAD_ATTEMPTS: Final[str] = t("downloader.log_failed_download_attempts")
LOG_FAILED_DOWNLOAD_ERROR: Final[str] = t("downloader.log_failed_download_error")

ERROR_URL_REQUIRED: Final[str] = t("downloader.error_url_required")
ERROR_DESTINATION_REQUIRED: Final[str] = t("downloader.error_destination_required")
ERROR_FILENAME_REQUIRED: Final[str] = t("downloader.error_filename_required")
ERROR_MIME_MISMATCH_TEMPLATE: Final[str] = t("downloader.error_mime_mismatch")

RETRYABLE_EXCEPTIONS: Final[tuple[type[Exception], ...]] = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.HTTPError,
)


class MimeTypeMismatchError(ValueError):
    """Raised when downloaded content is not a supported type."""
    pass


@total_ordering
class SouthCarolinaFiscalYear:
    """Represents a South Carolina fiscal year, which runs from July 1 to June 30.

    For instance, fiscal year 2023 runs from July 1, 2022 to June 30, 2023.
    The SC Courts website uses a calendar-year based URL pattern to represent
    a fiscal year (July through June). For example, the fiscal year 2023 begins
    on July 1, 2022 and ends on June 30, 2023, represented in URLs as '2022-2023'.
    """

    MIN_FISCAL_YEAR: Final[int] = 2008  # The first fiscal year for which the SC Courts website has data (July 1, 2007 - June 30, 2008)
    FISCAL_YEAR_START_MONTH: Final[int] = 7
    FISCAL_YEAR_START_DAY: Final[int] = 1
    FISCAL_YEAR_END_MONTH: Final[int] = 6
    FISCAL_YEAR_END_DAY: Final[int] = 30
    YEAR_OFFSET: Final[int] = 1

    def __init__(self, year: int | "SouthCarolinaFiscalYear") -> None:
        if isinstance(year, SouthCarolinaFiscalYear):
            self.year = year.year
        else:
            self.year = int(year)
        self.start_date = date(self.year - self.YEAR_OFFSET, self.FISCAL_YEAR_START_MONTH, self.FISCAL_YEAR_START_DAY)
        self.end_date = date(self.year, self.FISCAL_YEAR_END_MONTH, self.FISCAL_YEAR_END_DAY)

    @property
    def start_year(self) -> int:
        """The calendar year in which this fiscal year begins (e.g. 2022 for FY2023)."""
        return self.year - self.YEAR_OFFSET

    @property
    def end_year(self) -> int:
        """The calendar year in which this fiscal year ends (e.g. 2023 for FY2023)."""
        return self.year

    @classmethod
    def from_date(cls, d: date) -> "SouthCarolinaFiscalYear":
        """Determine the fiscal year for a given calendar date."""
        fiscal_year = d.year + cls.YEAR_OFFSET if d.month >= cls.FISCAL_YEAR_START_MONTH else d.year
        return cls(fiscal_year)

    @classmethod
    def current(cls) -> "SouthCarolinaFiscalYear":
        """Return the current fiscal year based on today's date."""
        return cls.from_date(date.today())

    def previous(self) -> "SouthCarolinaFiscalYear":
        """Return the preceding fiscal year."""
        return SouthCarolinaFiscalYear(self.year - self.YEAR_OFFSET)

    def next(self) -> "SouthCarolinaFiscalYear":
        """Return the subsequent fiscal year."""
        return SouthCarolinaFiscalYear(self.year + self.YEAR_OFFSET)

    @classmethod
    def range(
        cls,
        start: "SouthCarolinaFiscalYear",
        end: "SouthCarolinaFiscalYear",
    ) -> Generator["SouthCarolinaFiscalYear", None, None]:
        """Yield FiscalYear instances from start to end (inclusive)."""
        for y in range(start.year, end.year + 1):
            yield cls(y)

    @classmethod
    def min_fiscal_year(cls) -> "SouthCarolinaFiscalYear":
        """Return the minimum fiscal year for which the SC Courts website has data."""
        return cls(cls.MIN_FISCAL_YEAR)

    def __int__(self) -> int:
        return self.year

    def __str__(self) -> str:
        return f"FiscalYear({self.year}) is from {self.start_date} to {self.end_date}, inclusive of both dates."

    def __repr__(self) -> str:
        return f"FiscalYear({self.year})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SouthCarolinaFiscalYear):
            return self.year == other.year
        if isinstance(other, int):
            return self.year == other
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, SouthCarolinaFiscalYear):
            return self.year < other.year
        if isinstance(other, int):
            return self.year < other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.year)

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
        temp_dest = target_dest.with_name(
            f"{TEMP_FILE_PREFIX}{target_dest.name}.{uuid.uuid4().hex}{TEMP_FILE_SUFFIX}"
        )
        try:
            with open(temp_dest, FILE_WRITE_BINARY_MODE) as f:
                for chunk in self._iter_chunks(response):
                    f.write(chunk)
            temp_dest.replace(target_dest)
        except BaseException:
            if temp_dest.exists():
                try:
                    temp_dest.unlink()
                except OSError:
                    pass
            raise

        logger.info(t("downloader.log_download_success", filename=filename))
        return target_dest


def build_urls(
    start_year: SouthCarolinaFiscalYear | None = None,
    end_year: SouthCarolinaFiscalYear | None = None,
) -> list[str]:
    """Helper method to find the report URLs. The South Carolina Courts website uses a calendar-year based URL 
    pattern to represent a fiscal year (July through June). For example, the fiscal year 2023 (July 1, 2022 - June 30, 2023)
    is represented in the URL as "2022-2023".

    start_year: first fiscal year to include. Defaults to MIN_FISCAL_YEAR. If start_year is less than MIN_FISCAL_YEAR, it will be clamped to MIN_FISCAL_YEAR.
    end_year: last fiscal year to include. If end_year is less than start_year, it will be set to start_year. Defaults to the previous fiscal year. 
    """

    if start_year is not None and not isinstance(start_year, SouthCarolinaFiscalYear):
        start_year = SouthCarolinaFiscalYear(start_year)
    if end_year is not None and not isinstance(end_year, SouthCarolinaFiscalYear):
        end_year = SouthCarolinaFiscalYear(end_year)

    if start_year is None:
        start_fy = SouthCarolinaFiscalYear.min_fiscal_year()
    else:
        start_fy = max(start_year, SouthCarolinaFiscalYear.min_fiscal_year())

    if end_year is None:
        # Determine the previous fiscal year based on today's date
        # Use the previous fiscal year as the end_year because the courts only publish reports for the already closed out fiscal years. 
        # For example, if today is 1 JUL 2026, the current fiscal year is 2027 (1 JUL 2026 - 30 JUN 2027), but the most recent report
        # available is for fiscal year 2026 (1 JUL 2025 - 30 JUN 2026).
        end_fy = SouthCarolinaFiscalYear.current().previous()
    else:
        end_fy = end_year

    if end_fy < start_fy:
        end_fy = start_fy

    return [ ANNUAL_REPORT_URL_TEMPLATE.format(start_year=fy.start_year, end_year=fy.end_year) for fy in SouthCarolinaFiscalYear.range(start_fy, end_fy)]


def download_pdfs(
    output_dir: Path | str | None = None,
    provenance_dir: Path | str | None = None,
    start_year: SouthCarolinaFiscalYear | None = None,
    end_year: SouthCarolinaFiscalYear | None = None,
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
    start_year: first fiscal year to attempt, e.g. SouthCarolinaFiscalYear(2010) pulls the
                JUL 2009 - JUN 2010 report. If value less than MIN_FISCAL_YEAR, defaults to MIN_FISCAL_YEAR.
    end_year: last fiscal year to include e.g. SouthCarolinaFiscalYear(2020) pulls 1 Jul 2019 - 30 JUN 2020. If value less than start_year, defaults to start_year.
    overwrite_existing: If True, overwrite files already downloaded.
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

    for url in build_urls(start_year=start_year, end_year=end_year):
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
    base_dir = Path(__file__).resolve().parent.parent
    download_pdfs(
        output_dir=cli_args.output_dir or base_dir / DEFAULT_PDF_DIR,
        provenance_dir=base_dir / DEFAULT_PROVENANCE_DIR,
        overwrite_existing=cli_args.overwrite_existing,
    )


# Only runs when this file is executed directly, not when imported by the orchestrator
if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()

    main()