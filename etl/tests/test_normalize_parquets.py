import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from normalize_parquets import (
    CATEGORY,
    COUNTIES_LOWER,
    EXPECTED_METRICS,
    EXPECTED_METRICS_MENTAL_HEALTH,
    METRICS_LOWER,
    METRICS_MH_LOWER,
    MONTHS,
    SC_COUNTIES,
    SCHEMA,
    match_metric,
    normalize_silver_to_gold,
)

EXPECTED_COUNTY_COUNT = 46
EXPECTED_MONTH_COUNT = 12
FIRST_YEAR = 2019
SECOND_YEAR = 2020
SILVER_NAME = "estate_2019_2020_bronze.parquet"
ESTATE_TITLE = "South Carolina Court Administration\nEstate Monthly Caseload Report\nPeriod 2019-2020"
GUARDIAN_TITLE = "South Carolina Court Administration\nGuardian and Conservator Monthly Caseload Report\nPeriod"
MENTAL_HEALTH_TITLE = "South Carolina Court Administration\nMental Health Monthly Caseload Report\nPeriod"
FULL_YEAR_HEADER = [
    "", "", "July", "August", "September", "October", "November", "December",
    "January", "February", "March", "April", "May", "June",
]
SHORT_HEADER = ["", "", "July", "December", "January"]
PROVENANCE_FILE = "provenance_log.jsonl"
CSV_STEM = "caseloads_normalized"
CUSTOM_STEM = "custom_name"


def write_silver(directory, name, rows):
    """Writes a Silver-style parquet with a single list<string> 'raw_row' column."""
    table = pa.table({"raw_row": pa.array(rows, type=pa.list_(pa.string()))})
    pq.write_table(table, directory / name)


def dirs(tmp_path):
    silver = tmp_path / "silver"
    silver.mkdir()
    return silver, tmp_path / "gold", tmp_path / "prov"


def run(tmp_path, rows_by_file, **kwargs):
    silver, gold, prov = dirs(tmp_path)
    for name, rows in rows_by_file.items():
        write_silver(silver, name, rows)
    return normalize_silver_to_gold(silver, gold, prov, **kwargs), gold, prov


def estate_rows(county="Abbeville", metric="Added", values=("1", "2", "3")):
    return [
        [ESTATE_TITLE, None, None, None, None],
        SHORT_HEADER,
        [county, None, None, None, None],
        [None, metric, *values],
    ]


# ==============================================================================
# Reference data
# ==============================================================================

class TestReferenceData:
    def test_all_counties_present_and_lookup_is_lowercase(self):
        assert len(SC_COUNTIES) == EXPECTED_COUNTY_COUNT
        assert COUNTIES_LOWER["mccormick"] == "McCormick"

    def test_all_months_present(self):
        assert len(MONTHS) == EXPECTED_MONTH_COUNT
        assert MONTHS["July"] == "7"
        assert MONTHS["June"] == "6"

    def test_categories_and_metrics(self):
        assert CATEGORY == ["Estate", "Guardian", "Conservator", "Mental Health"]
        assert EXPECTED_METRICS_MENTAL_HEALTH == ["Added", "Orders"]
        assert SCHEMA == ["file", "category", "month", "year", "county", "metric", "value"]


# ==============================================================================
# match_metric
# ==============================================================================

class TestMatchMetric:
    @pytest.mark.parametrize("item,expected", [
        ("Added", "Added"),
        ("added", "Added"),
        ("  DISPOSED  ", "Disposed"),
        ("Pending first of month", "Pending first of month"),
        ("Pending End Of Month", "Pending end of Month"),
        ("Added*", "Added"),
        ("Disposed 1", "Disposed"),
    ])
    def test_matches_case_insensitive_and_prefix(self, item, expected):
        assert match_metric(item, METRICS_LOWER) == expected

    def test_none_returns_none(self):
        assert match_metric(None, METRICS_LOWER) is None

    @pytest.mark.parametrize("item", ["", "   ", "Unknown", "Pending", "xAdded"])
    def test_non_matches_return_none(self, item):
        assert match_metric(item, METRICS_LOWER) is None

    def test_non_string_is_stringified(self):
        assert match_metric(123, METRICS_LOWER) is None

    def test_orders_footnote_for_mental_health(self):
        assert match_metric("Orders*", METRICS_MH_LOWER) == "Orders"

    def test_empty_dict_returns_none(self):
        assert match_metric("Added", {}) is None

    def test_mental_health_dict_ignores_estate_metrics(self):
        assert match_metric("Disposed", METRICS_MH_LOWER) is None


# ==============================================================================
# normalize_silver_to_gold: happy paths
# ==============================================================================

class TestNormalizeHappyPath:
    def test_estate_rows_long_format(self, tmp_path):
        df, _, _ = run(tmp_path, {SILVER_NAME: estate_rows()})

        assert list(df.columns) == SCHEMA
        assert len(df) == 3
        assert df["file"].unique().tolist() == [SILVER_NAME]
        assert df["category"].unique().tolist() == ["Estate"]
        assert df["county"].unique().tolist() == ["Abbeville"]
        assert df["metric"].unique().tolist() == ["Added"]
        assert list(zip(df["month"], df["year"], df["value"])) == [
            (7, FIRST_YEAR, "1"), (12, FIRST_YEAR, "2"), (1, SECOND_YEAR, "3"),
        ]

    def test_full_year_header_assigns_fiscal_years(self, tmp_path):
        values = [str(i) for i in range(EXPECTED_MONTH_COUNT)]
        rows = [
            [ESTATE_TITLE] + [None] * 13,
            FULL_YEAR_HEADER,
            ["Aiken"] + [None] * 13,
            [None, "Disposed", *values, ],
        ]
        # Pad: header month columns are 2..13, so the metric row needs same width
        rows[3] = [None, "Disposed"] + values
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})

        assert len(df) == EXPECTED_MONTH_COUNT
        by_month = {m: y for m, y in zip(df["month"], df["year"])}
        for month in (7, 8, 9, 10, 11, 12):
            assert by_month[month] == FIRST_YEAR
        for month in (1, 2, 3, 4, 5, 6):
            assert by_month[month] == SECOND_YEAR

    def test_county_match_is_case_insensitive_and_canonicalized(self, tmp_path):
        df, _, _ = run(tmp_path, {SILVER_NAME: estate_rows(county="MCCORMICK")})
        assert df["county"].unique().tolist() == ["McCormick"]

    def test_thousands_commas_stripped_and_codes_preserved(self, tmp_path):
        df, _, _ = run(tmp_path, {SILVER_NAME: estate_rows(values=("1,086", "DNR", "TI"))})
        assert df["value"].tolist() == ["1086", "DNR", "TI"]

    def test_none_cell_becomes_string_none(self, tmp_path):
        df, _, _ = run(tmp_path, {SILVER_NAME: estate_rows(values=(None, "", "5"))})
        assert df["value"].tolist() == ["None", "", "5"]

    def test_values_always_strings_month_year_ints(self, tmp_path):
        df, _, _ = run(tmp_path, {SILVER_NAME: estate_rows()})
        assert df["month"].dtype == "int64"
        assert df["year"].dtype == "int64"
        assert all(isinstance(v, str) for v in df["value"])

    def test_multiple_metrics_and_counties(self, tmp_path):
        rows = [
            [ESTATE_TITLE, None, None, None, None],
            SHORT_HEADER,
            ["Aiken", None, None, None, None],
            [None, "Pending first of month", "1", "2", "3"],
            [None, "Added", "4", "5", "6"],
            ["", "", "", "", ""],
            ["York", None, None, None, None],
            [None, "Disposed", "7", "8", "9"],
        ]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})

        assert len(df) == 9
        assert df[df["county"] == "Aiken"]["metric"].unique().tolist() == [
            "Pending first of month", "Added",
        ]
        assert df[df["county"] == "York"]["metric"].unique().tolist() == ["Disposed"]

    def test_guardian_title_maps_to_guardian_not_conservator(self, tmp_path):
        rows = estate_rows()
        rows[0] = [GUARDIAN_TITLE, None, None, None, None]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df["category"].unique().tolist() == ["Guardian"]

    def test_conservator_title(self, tmp_path):
        rows = estate_rows()
        rows[0] = [
            "South Carolina Court Administration\nConservator Monthly Report\nPeriod",
            None, None, None, None,
        ]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df["category"].unique().tolist() == ["Conservator"]

    def test_mental_health_uses_its_own_metrics(self, tmp_path):
        rows = [
            [MENTAL_HEALTH_TITLE, None, None, None, None],
            SHORT_HEADER,
            ["Richland", None, None, None, None],
            [None, "Added", "1", "2", "3"],
            [None, "Orders*", "4", "5", "6"],
            [None, "Disposed", "7", "8", "9"],
            [None, "Pending first of month", "7", "8", "9"],
        ]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})

        assert df["category"].unique().tolist() == ["Mental Health"]
        assert df["metric"].tolist() == ["Added"] * 3 + ["Orders"] * 3

    def test_estate_ignores_mental_health_only_metric(self, tmp_path):
        df, _, _ = run(tmp_path, {SILVER_NAME: estate_rows(metric="Orders")})
        assert df.empty

    def test_metric_found_in_any_cell_of_row(self, tmp_path):
        rows = estate_rows()
        rows[3] = ["junk", "x", "Added", "2", "3"]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        # Metric label is in column 2, which is also a month column: its text is the value
        assert df["value"].tolist() == ["Added", "2", "3"]
        assert df["metric"].unique().tolist() == ["Added"]

    def test_header_with_extra_columns_uses_exact_positions(self, tmp_path):
        rows = [
            [ESTATE_TITLE, None, None, None, None, None],
            ["", "", "July", "Q1 Total", "December", "January"],
            ["Aiken", None, None, None, None, None],
            [None, "Added", "1", "99", "2", "3"],
        ]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df["value"].tolist() == ["1", "2", "3"]

    def test_header_month_matching_is_case_insensitive(self, tmp_path):
        rows = estate_rows()
        rows[1] = ["", "", "JULY", "december", "January"]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df["month"].tolist() == [7, 12, 1]

    def test_header_replaced_by_later_header(self, tmp_path):
        rows = estate_rows() + [
            ["", "", "March", "April", "May"],
            [None, "Added", "7", "8", "9"],
        ]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df["month"].tolist() == [7, 12, 1, 3, 4, 5]
        assert df["year"].tolist()[3:] == [FIRST_YEAR] * 3

    def test_header_month_in_first_two_columns_is_not_trigger(self, tmp_path):
        rows = estate_rows()
        rows[1] = ["July", "August", None, None, None]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df.empty

    def test_header_month_in_first_two_columns_included_when_triggered(self, tmp_path):
        rows = estate_rows()
        rows[1] = ["July", "", "August", "September", "October"]
        rows[3] = ["x", "Added", "a", "b", "c"]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df["month"].tolist() == [7, 8, 9, 10]
        assert df["value"].tolist() == ["x", "a", "b", "c"]


# ==============================================================================
# normalize_silver_to_gold: state handling
# ==============================================================================

class TestNormalizeStateHandling:
    def test_metric_without_county_ignored(self, tmp_path):
        rows = estate_rows()
        del rows[2]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df.empty

    def test_metric_without_category_ignored(self, tmp_path):
        rows = estate_rows()
        del rows[0]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df.empty

    def test_metric_before_header_yields_no_rows(self, tmp_path):
        rows = estate_rows()
        del rows[1]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df.empty

    def test_blank_row_resets_county(self, tmp_path):
        rows = estate_rows()
        rows.insert(3, ["", None, "", None, ""])
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df.empty

    def test_county_persists_across_non_blank_rows(self, tmp_path):
        rows = estate_rows() + [[None, "Disposed", "4", "5", "6"]]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert len(df) == 6

    def test_state_resets_between_files(self, tmp_path):
        second = "estate_2021_2022_bronze.parquet"
        # Second file has metric row but no title/header/county of its own
        rows2 = [[None, "Added", "1", "2", "3"]]
        df, _, _ = run(tmp_path, {SILVER_NAME: estate_rows(), second: rows2})
        assert set(df["file"]) == {SILVER_NAME}

    def test_files_processed_in_sorted_order_with_own_years(self, tmp_path):
        later = "estate_2021_2022_bronze.parquet"
        df, _, _ = run(tmp_path, {later: estate_rows(), SILVER_NAME: estate_rows()})
        assert df["file"].unique().tolist() == [SILVER_NAME, later]
        assert sorted(df["year"].unique().tolist()) == [2019, 2020, 2021, 2022]

    def test_non_parquet_files_ignored(self, tmp_path):
        silver, gold, prov = dirs(tmp_path)
        write_silver(silver, SILVER_NAME, estate_rows())
        (silver / "notes_2019_2020.txt").write_text("ignore me")
        df = normalize_silver_to_gold(silver, gold, prov)
        assert set(df["file"]) == {SILVER_NAME}

    def test_title_with_unknown_category_keeps_previous_category(self, tmp_path):
        rows = estate_rows()
        rows.insert(1, ["South Carolina Court Administration\nProbate Other Report\nPeriod", None, None, None, None])
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df["category"].unique().tolist() == ["Estate"]

    def test_unrecognized_county_does_not_change_county(self, tmp_path):
        rows = estate_rows()
        rows.insert(3, ["Atlantis", None, None, None, None])
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        assert df["county"].unique().tolist() == ["Abbeville"]

    def test_year_map_when_header_only_has_second_year_months(self, tmp_path):
        rows = estate_rows()
        rows[1] = ["", "", "January", "February", "March"]
        df, _, _ = run(tmp_path, {SILVER_NAME: rows})
        # No decrease in month numbers, so these are attributed to year1
        assert df["year"].tolist() == [FIRST_YEAR] * 3

    def test_same_year_filename_collapses_year_map(self, tmp_path):
        df, _, _ = run(tmp_path, {"estate_2019_2019.parquet": estate_rows()})
        assert df["year"].unique().tolist() == [FIRST_YEAR]


# ==============================================================================
# normalize_silver_to_gold: outputs and provenance
# ==============================================================================

class TestNormalizeOutputs:
    def test_writes_csv_and_parquet_matching_returned_frame(self, tmp_path):
        df, gold, _ = run(tmp_path, {SILVER_NAME: estate_rows()})

        csv_df = pd.read_csv(gold / f"{CSV_STEM}.csv", dtype=str)
        parquet_df = pq.read_table(gold / f"{CSV_STEM}.parquet").to_pandas()

        assert list(csv_df.columns) == SCHEMA
        assert list(parquet_df.columns) == SCHEMA
        assert csv_df["value"].tolist() == parquet_df["value"].tolist() == df["value"].tolist()
        assert len(csv_df) == len(parquet_df) == len(df)

    def test_parquet_has_explicit_schema(self, tmp_path):
        _, gold, _ = run(tmp_path, {SILVER_NAME: estate_rows()})
        schema = pq.read_schema(gold / f"{CSV_STEM}.parquet")
        assert schema.field("month").type == pa.int64()
        assert schema.field("year").type == pa.int64()
        for name in ("file", "category", "county", "metric", "value"):
            assert schema.field(name).type == pa.string()

    def test_custom_output_filename(self, tmp_path):
        _, gold, _ = run(tmp_path, {SILVER_NAME: estate_rows()}, output_filename=CUSTOM_STEM)
        assert (gold / f"{CUSTOM_STEM}.csv").exists()
        assert (gold / f"{CUSTOM_STEM}.parquet").exists()
        assert not (gold / f"{CSV_STEM}.csv").exists()

    def test_creates_nested_output_dir_and_accepts_str_paths(self, tmp_path):
        silver, _, prov = dirs(tmp_path)
        write_silver(silver, SILVER_NAME, estate_rows())
        nested = tmp_path / "a" / "b" / "gold"
        normalize_silver_to_gold(str(silver), str(nested), str(prov))
        assert (nested / f"{CSV_STEM}.csv").exists()

    def test_empty_input_dir_writes_empty_outputs(self, tmp_path):
        df, gold, prov = run(tmp_path, {})

        assert df.empty
        assert list(df.columns) == SCHEMA
        assert pq.read_table(gold / f"{CSV_STEM}.parquet").num_rows == 0
        assert (gold / f"{CSV_STEM}.csv").read_text().strip() == ",".join(SCHEMA)
        records = [json.loads(l) for l in (prov / PROVENANCE_FILE).read_text().splitlines()]
        assert [r["derived_from"] for r in records] == [[], []]

    def test_provenance_logged_for_csv_and_parquet(self, tmp_path):
        other = "estate_2021_2022_bronze.parquet"
        _, _, prov = run(tmp_path, {SILVER_NAME: estate_rows(), other: estate_rows()})

        records = [json.loads(l) for l in (prov / PROVENANCE_FILE).read_text().splitlines()]
        assert [r["filename"] for r in records] == [f"{CSV_STEM}.csv", f"{CSV_STEM}.parquet"]
        for record in records:
            assert record["stage"] == "gold"
            assert record["derived_from"] == [SILVER_NAME, other]

    def test_file_with_no_matching_rows_still_listed_in_lineage(self, tmp_path):
        _, _, prov = run(tmp_path, {SILVER_NAME: [[None, None]]})
        record = json.loads((prov / PROVENANCE_FILE).read_text().splitlines()[0])
        assert record["derived_from"] == [SILVER_NAME]

    def test_rerun_overwrites_outputs_and_appends_provenance(self, tmp_path):
        silver, gold, prov = dirs(tmp_path)
        write_silver(silver, SILVER_NAME, estate_rows())
        normalize_silver_to_gold(silver, gold, prov)
        normalize_silver_to_gold(silver, gold, prov)

        assert len(pd.read_csv(gold / f"{CSV_STEM}.csv")) == 3
        assert len((prov / PROVENANCE_FILE).read_text().splitlines()) == 4


# ==============================================================================
# normalize_silver_to_gold: error paths (current behavior)
# ==============================================================================

class TestNormalizeErrors:
    def test_missing_input_dir_yields_empty_output(self, tmp_path):
        # Path.glob on a missing directory yields nothing rather than raising
        df = normalize_silver_to_gold(tmp_path / "nope", tmp_path / "gold", tmp_path / "prov")
        assert df.empty

    def test_filename_with_fewer_than_two_years_raises_index_error(self, tmp_path):
        with pytest.raises(IndexError):
            run(tmp_path, {"estate_2019.parquet": estate_rows()})

    def test_filename_without_years_raises_index_error(self, tmp_path):
        with pytest.raises(IndexError):
            run(tmp_path, {"estate.parquet": estate_rows()})

    def test_filename_with_extra_years_uses_first_two(self, tmp_path):
        df, _, _ = run(tmp_path, {"estate_2019_2020_2021.parquet": estate_rows()})
        assert sorted(df["year"].unique().tolist()) == [FIRST_YEAR, SECOND_YEAR]

    def test_missing_raw_row_column_raises_key_error(self, tmp_path):
        silver, gold, prov = dirs(tmp_path)
        pq.write_table(pa.table({"other": ["a"]}), silver / SILVER_NAME)
        with pytest.raises(KeyError):
            normalize_silver_to_gold(silver, gold, prov)

    def test_corrupt_parquet_raises(self, tmp_path):
        silver, gold, prov = dirs(tmp_path)
        (silver / SILVER_NAME).write_bytes(b"not a parquet file")
        with pytest.raises(pa.ArrowInvalid):
            normalize_silver_to_gold(silver, gold, prov)

    def test_title_without_second_line_raises_index_error(self, tmp_path):
        rows = [["South Carolina Court Administration", None, None]]
        with pytest.raises(IndexError):
            run(tmp_path, {SILVER_NAME: rows})

    def test_metric_row_shorter_than_header_raises_index_error(self, tmp_path):
        rows = estate_rows()
        rows[3] = [None, "Added", "1"]
        with pytest.raises(IndexError):
            run(tmp_path, {SILVER_NAME: rows})

    def test_empty_silver_file_produces_no_rows(self, tmp_path):
        df, _, _ = run(tmp_path, {SILVER_NAME: []})
        assert df.empty
