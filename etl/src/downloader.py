# downloader.py
"""
Bronze stage: downloads raw SC Probate Estate Monthly Caseload PDF reports
from the SC Courts website and saves them locally, untouched, as the
preserved source artifact (Bronze tier of the Medallion architecture).
Also logs a provenance record for every successfully downloaded file.
"""

import requests
import time
import random
from pathlib import Path

from provenance import log_provenance
from logging_config import get_logger

logger = get_logger(__name__)


def download_pdfs(output_dir, provenance_dir, start_year=2007, end_year=None):
    """Downloads SC Probate estate monthly caseload PDFs into output_dir.

    Each report covers a fiscal year (July through June), so the SC Courts
    URL pattern uses two consecutive years, e.g. 2022-2023.

    output_dir: directory the downloaded Bronze PDFs are written to (created
                if it doesn't already exist).
    provenance_dir: directory the provenance log (provenance_log.jsonl) is
                     written/appended to for each successfully downloaded file.
    start_year: first fiscal-year start year to attempt, e.g. 2007 pulls the
                2007-2008 report.
    end_year: last fiscal-year start year to attempt. Defaults to last
              calendar year, since the current year's report may not exist yet.
    """
    if end_year is None:
        end_year = time.localtime().tm_year - 1  # Default to last year, since current year's report may not exist yet

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for year in range(start_year, end_year + 1):
        next_year = year + 1
        url = f"https://www.sccourts.org/media/annualReports/{year}-{next_year}/CATotalsES2.pdf"
        headers = {'User-Agent': 'Mozilla/5.0'}  # Mimic a browser to avoid being blocked
        filename = f"estate_monthly_caseload_{year}_to_{next_year}_bronze.pdf"
        filepath = output_dir / filename

        # Skip files already downloaded, makes reruns cheap and idempotent
        if filepath.exists():
            logger.info(f"⏭️ Skipping: {filename} (already exists)")
            continue

        success = False
        for attempt in range(1, 4):  # Retry up to 3 times per file
            try:
                logger.info(f"Attempt {attempt} to download: {filename}")
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()  # Raises on HTTP error codes

                # "wb" = write binary, since a PDF is binary data, not text
                with open(filepath, "wb") as f:
                    f.write(response.content)
                logger.info(f"✅ Downloaded: {filename}")
                success = True
                break

            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ Attempt {attempt} failed for {filename}: {e}")
                wait_time = random.uniform(1, 5)  # Random delay avoids hammering the server on retries
                time.sleep(wait_time)

        if not success:
            logger.error(f"❌ Failed to download {filename} after 3 attempts.")
        else:
            # Record provenance the moment a Bronze artifact exists on disk:
            # which URL it came from, when, and its content hash
            log_provenance(provenance_dir, stage="bronze", file_path=filepath, source_url=url)

            # Polite delay between files so we don't hit the server too fast
            delay = random.uniform(1, 5)
            time.sleep(delay)


# Only runs when this file is executed directly, not when imported by the orchestrator
if __name__ == "__main__":
    base_dir = Path(__file__).parent
    download_pdfs(
        base_dir / "data/pdfs_bronze",
        base_dir / "data/provenance",
    )
