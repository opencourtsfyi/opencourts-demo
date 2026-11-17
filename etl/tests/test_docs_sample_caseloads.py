"""Keep docs/sample-data Gold CSV aligned with the frontend sample generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_SCRIPT = REPO_ROOT / "docs" / "sample-data" / "generate_caseloads_normalized.py"
COMMITTED_CSV = REPO_ROOT / "docs" / "sample-data" / "caseloads_normalized.csv"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_caseloads_normalized",
        GENERATOR_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_sample_csv_matches_frontend_generator(tmp_path: Path) -> None:
    generator = _load_generator()
    expected_path = tmp_path / "caseloads_normalized.csv"
    rows = generator.rows_from_frontend_sample(generator.frontend_sample_path(REPO_ROOT))
    generator.write_caseloads_csv(rows, expected_path)

    committed = COMMITTED_CSV.read_text(encoding="utf-8")
    expected = expected_path.read_text(encoding="utf-8")
    assert committed == expected


def test_generator_script_exists() -> None:
    assert GENERATOR_SCRIPT.is_file()
    assert COMMITTED_CSV.is_file()
