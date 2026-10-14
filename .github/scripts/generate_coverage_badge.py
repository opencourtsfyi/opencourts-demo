"""Generate SVG and JSON coverage badges from coverage.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

# Coverage Threshold Constants
TARGET_COVERAGE_PERCENT = 85
MIN_COVERAGE_PERCENT = 70

COLOR_PASS_HEX = "#4c1"
COLOR_PASS_NAME = "brightgreen"
COLOR_WARN_HEX = "#dfb317"
COLOR_WARN_NAME = "yellow"
COLOR_FAIL_HEX = "#e05d44"
COLOR_FAIL_NAME = "red"


def get_color(percent: int) -> tuple[str, str]:
    """Return hex color and shields color name for given percentage."""
    if percent >= TARGET_COVERAGE_PERCENT:
        return COLOR_PASS_HEX, COLOR_PASS_NAME
    if percent >= MIN_COVERAGE_PERCENT:
        return COLOR_WARN_HEX, COLOR_WARN_NAME
    return COLOR_FAIL_HEX, COLOR_FAIL_NAME


def generate_svg(label: str, message: str, color_hex: str) -> str:
    """Generate a clean shields.io-compatible flat SVG badge."""
    label_width = len(label) * 6 + 18
    message_width = len(message) * 7 + 14
    total_width = label_width + message_width

    label_x = (label_width / 2) * 10
    message_x = (label_width + message_width / 2) * 10

    label_text_length = len(label) * 65
    message_text_length = len(message) * 75

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {message}">
  <title>{label}: {message}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{message_width}" height="20" fill="{color_hex}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <text aria-hidden="true" x="{label_x:.0f}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{label_text_length}">{label}</text>
    <text x="{label_x:.0f}" y="140" transform="scale(.1)" fill="#fff" textLength="{label_text_length}">{label}</text>
    <text aria-hidden="true" x="{message_x:.0f}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{message_text_length}">{message}</text>
    <text x="{message_x:.0f}" y="140" transform="scale(.1)" fill="#fff" textLength="{message_text_length}">{message}</text>
  </g>
</svg>
"""


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    if len(sys.argv) > 1:
        cov_file = Path(sys.argv[1])
    else:
        candidates = [
            repo_root / "etl" / "coverage.json",
            Path("etl/coverage.json"),
            Path("coverage.json"),
        ]
        cov_file = next((p for p in candidates if p.exists()), None)

    if not cov_file or not cov_file.exists():
        print(f"Coverage file not found. Candidates checked: {cov_file}", file=sys.stderr)
        sys.exit(1)

    with open(cov_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    percent_covered = data["totals"]["percent_covered"]
    percent_int = round(percent_covered)
    message = f"{percent_int}%"
    label = "coverage"

    color_hex, shields_color = get_color(percent_int)

    badges_dir = repo_root / ".github" / "badges"
    badges_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write SVG badge
    svg_content = generate_svg(label, message, color_hex)
    svg_file = badges_dir / "coverage.svg"
    svg_file.write_text(svg_content, encoding="utf-8")
    print(f"Generated {svg_file} with coverage {message}")

    # 2. Write Shields endpoint JSON
    json_badge_file = badges_dir / "coverage.json"
    badge_data = {
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": shields_color,
    }
    json_badge_file.write_text(json.dumps(badge_data, indent=2), encoding="utf-8")
    print(f"Generated {json_badge_file}")

    # 3. Emit GitHub Actions annotations and write step summary
    if percent_int < MIN_COVERAGE_PERCENT:
        print(
            f"::error title=Coverage Failure::Overall coverage ({percent_int}%) is below the minimum required threshold of {MIN_COVERAGE_PERCENT}%."
        )
    elif percent_int < TARGET_COVERAGE_PERCENT:
        print(
            f"::warning title=Coverage Advisory::Overall coverage ({percent_int}%) is below the advisory target of {TARGET_COVERAGE_PERCENT}%."
        )

    step_summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_file:
        with open(step_summary_file, "a", encoding="utf-8") as f:
            f.write("## Test & Coverage Results\n\n")
            f.write(f"- **Overall Coverage:** {percent_int}%\n")
            f.write(f"- **Advisory Target:** {TARGET_COVERAGE_PERCENT}%\n")
            f.write(f"- **Minimum Required:** {MIN_COVERAGE_PERCENT}%\n\n")
            if percent_int < MIN_COVERAGE_PERCENT:
                f.write(
                    f"> [!CAUTION]\n> Coverage ({percent_int}%) is below the required {MIN_COVERAGE_PERCENT}% threshold. Build will fail.\n"
                )
            elif percent_int < TARGET_COVERAGE_PERCENT:
                f.write(
                    f"> [!WARNING]\n> Coverage ({percent_int}%) is below the advisory target of {TARGET_COVERAGE_PERCENT}%.\n"
                )
            else:
                f.write(
                    f"> [!NOTE]\n> Coverage ({percent_int}%) meets or exceeds the target of {TARGET_COVERAGE_PERCENT}%.\n"
                )


if __name__ == "__main__":
    main()
