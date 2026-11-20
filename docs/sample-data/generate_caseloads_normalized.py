"""Generate docs/sample-data/caseloads_normalized.csv from the frontend sample JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

COLUMNS = ["file", "category", "month", "year", "county", "metric", "value"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def frontend_sample_path(root: Path | None = None) -> Path:
    base = root or repo_root()
    return base / "frontend" / "public" / "data" / "caseloads_sample.json"


def output_csv_path(root: Path | None = None) -> Path:
    base = root or repo_root()
    return base / "docs" / "sample-data" / "caseloads_normalized.csv"


def rows_from_frontend_sample(sample_path: Path) -> list[dict[str, object]]:
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    return [{column: row.get(column, "") for column in COLUMNS} for row in data]


def write_caseloads_csv(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def generate(root: Path | None = None) -> Path:
    base = root or repo_root()
    out_path = output_csv_path(base)
    write_caseloads_csv(rows_from_frontend_sample(frontend_sample_path(base)), out_path)
    return out_path


def main() -> int:
    path = generate()
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
