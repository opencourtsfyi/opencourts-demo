import logging
import os
import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import orchestrator
from orchestrator import main, parse_args, run_pipeline

STAGE_NAMES = (
    "download_pdfs",
    "extract_pdfs_to_silver",
    "normalize_silver_to_gold",
    "validate_gold_csv",
    "write_error_report",
)
EXPECTED_STAGE_ORDER = list(STAGE_NAMES)
EXPECTED_BASE_DIR = Path(orchestrator.__file__).parent
EXPECTED_BRONZE = EXPECTED_BASE_DIR / "data/pdfs_bronze"
EXPECTED_SILVER = EXPECTED_BASE_DIR / "data/cases_silver"
EXPECTED_GOLD = EXPECTED_BASE_DIR / "data/cases_gold"
EXPECTED_PROVENANCE = EXPECTED_BASE_DIR / "data/provenance"
EXPECTED_LOG_DIR = EXPECTED_BASE_DIR / "data/logs"
EXPECTED_ERRORS_CSV = EXPECTED_BASE_DIR / "data/validation/errors.csv"
EXPECTED_GOLD_CSV = EXPECTED_GOLD / "caseloads_normalized.csv"
STEP_COUNT = 4
SAMPLE_ERROR_COUNT = 2


@pytest.fixture
def stages():
    """Patch all stage functions and the logger; record call order in a shared manager."""
    manager = MagicMock()
    mocks = {}
    patches = []
    for name in STAGE_NAMES:
        p = patch(f"orchestrator.{name}")
        mock = p.start()
        patches.append(p)
        manager.attach_mock(mock, name)
        mocks[name] = mock
    mocks["validate_gold_csv"].return_value = []
    logger_patch = patch.object(orchestrator, "logger")
    mock_logger = logger_patch.start()
    patches.append(logger_patch)
    mocks["logger"] = mock_logger
    mocks["manager"] = manager
    yield mocks
    for p in patches:
        p.stop()


def called_stage_names(stages):
    return [c[0] for c in stages["manager"].mock_calls if c[0] in STAGE_NAMES]


# ==============================================================================
# Module import side effects
# ==============================================================================


class TestModuleSetup:
    def test_pipeline_log_dir_env_is_set(self):
        assert "PIPELINE_LOG_DIR" in os.environ

    def test_setdefault_preserves_existing_env_value(self, monkeypatch):
        monkeypatch.setenv("PIPELINE_LOG_DIR", "custom-dir")
        runpy.run_path(orchestrator.__file__, run_name="not_main")
        assert os.environ["PIPELINE_LOG_DIR"] == "custom-dir"

    def test_setdefault_sets_env_when_missing(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_LOG_DIR", raising=False)
        runpy.run_path(orchestrator.__file__, run_name="not_main")
        assert os.environ["PIPELINE_LOG_DIR"] == str(EXPECTED_LOG_DIR)


# ==============================================================================
# CLI argument parsing
# ==============================================================================


class TestParseArgs:
    def test_default_is_no_overwrite(self):
        assert parse_args([]).overwrite_existing is False

    @pytest.mark.parametrize("flag", ["--overwrite-existing", "--overwrite"])
    def test_overwrite_flags(self, flag):
        assert parse_args([flag]).overwrite_existing is True

    def test_unknown_argument_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            parse_args(["--bogus"])
        assert exc.value.code != 0
        assert "--bogus" in capsys.readouterr().err

    def test_positional_argument_rejected(self):
        with pytest.raises(SystemExit):
            parse_args(["extra"])

    def test_ambiguous_abbreviation_rejected(self, capsys):
        # Characterization: '--overwrite' is an alias of '--overwrite-existing', so
        # argparse prefix matching sees '--over' as ambiguous between the two.
        with pytest.raises(SystemExit):
            parse_args(["--over"])
        assert "ambiguous" in capsys.readouterr().err

    def test_unambiguous_abbreviation_accepted(self):
        # allow_abbrev is left at its default, so '--overwrite-e' is accepted.
        assert parse_args(["--overwrite-e"]).overwrite_existing is True

    def test_help_exits_zero_and_uses_localized_text(self, capsys):
        with pytest.raises(SystemExit) as exc:
            parse_args(["--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--overwrite-existing" in out
        assert "orchestrator.cli_description" not in out
        assert "orchestrator.cli_help_overwrite_existing" not in out

    def test_none_reads_sys_argv(self):
        with patch("sys.argv", ["orchestrator.py", "--overwrite"]):
            assert parse_args().overwrite_existing is True


# ==============================================================================
# Stage sequencing
# ==============================================================================


class TestRunPipeline:
    def test_stages_run_in_order(self, stages):
        run_pipeline()
        assert called_stage_names(stages) == EXPECTED_STAGE_ORDER

    def test_download_receives_paths_and_default_overwrite(self, stages):
        run_pipeline()
        stages["download_pdfs"].assert_called_once_with(
            EXPECTED_BRONZE, EXPECTED_PROVENANCE, overwrite_existing=False
        )

    def test_overwrite_flag_forwarded(self, stages):
        run_pipeline(overwrite_existing=True)
        stages["download_pdfs"].assert_called_once_with(
            EXPECTED_BRONZE, EXPECTED_PROVENANCE, overwrite_existing=True
        )

    def test_extract_receives_paths(self, stages):
        run_pipeline()
        stages["extract_pdfs_to_silver"].assert_called_once_with(
            EXPECTED_BRONZE, EXPECTED_SILVER, EXPECTED_PROVENANCE
        )

    def test_normalize_receives_paths(self, stages):
        run_pipeline()
        stages["normalize_silver_to_gold"].assert_called_once_with(
            EXPECTED_SILVER, EXPECTED_GOLD, EXPECTED_PROVENANCE
        )

    def test_validate_receives_gold_csv(self, stages):
        run_pipeline()
        stages["validate_gold_csv"].assert_called_once_with(EXPECTED_GOLD_CSV)

    def test_error_report_receives_errors_and_path(self, stages):
        errors = ["e1", "e2"]
        stages["validate_gold_csv"].return_value = errors
        run_pipeline()
        stages["write_error_report"].assert_called_once_with(errors, EXPECTED_ERRORS_CSV)

    def test_error_report_written_even_when_no_errors(self, stages):
        run_pipeline()
        stages["write_error_report"].assert_called_once_with([], EXPECTED_ERRORS_CSV)

    def test_returns_none(self, stages):
        assert run_pipeline() is None


class TestPipelineContext:
    def test_context_does_not_require_logger(self, caplog, tmp_path):
        context = orchestrator.PipelineContext(
            config=orchestrator.PipelineConfig.from_base_dir(tmp_path)
        )
        pipeline_orchestrator = orchestrator.PipelineOrchestrator(stages=[])

        with caplog.at_level(logging.INFO, logger="orchestrator"):
            result = pipeline_orchestrator.run(context)

        assert result is context
        assert "Pipeline completed successfully" in caplog.text


class TestRunPipelineLogging:
    def test_logger_is_module_logger(self):
        import logging
        assert isinstance(orchestrator.logger, logging.Logger)
        assert orchestrator.logger.name == "orchestrator" 

    def test_step_headers_logged(self, stages):
        run_pipeline()
        infos = [c.args[0] for c in stages["logger"].info.call_args_list]
        headers = [m for m in infos if m.startswith("=== Step")]
        assert len(headers) == STEP_COUNT
        for i, header in enumerate(headers, start=1):
            assert header.startswith(f"=== Step {i}:")

    def test_success_message_logged_when_no_errors(self, stages):
        run_pipeline()
        stages["logger"].error.assert_not_called()
        last_info = stages["logger"].info.call_args_list[-1].args[0]
        assert "completed successfully" in last_info

    def test_error_logged_with_count_when_validation_fails(self, stages):
        stages["validate_gold_csv"].return_value = ["a"] * SAMPLE_ERROR_COUNT
        run_pipeline()
        stages["logger"].error.assert_called_once()
        message = stages["logger"].error.call_args.args[0]
        assert str(SAMPLE_ERROR_COUNT) in message
        assert "validation issue" in message
        infos = [c.args[0] for c in stages["logger"].info.call_args_list]
        assert not any("completed successfully" in m for m in infos)

    def test_validation_errors_do_not_raise(self, stages):
        stages["validate_gold_csv"].return_value = ["bad"]
        run_pipeline()  # characterization: validation issues never fail the run


# ==============================================================================
# Failure paths
# ==============================================================================


class TestRunPipelineFailures:
    @pytest.mark.parametrize(
        "failing, skipped",
        [
            ("download_pdfs", STAGE_NAMES[1:]),
            ("extract_pdfs_to_silver", STAGE_NAMES[2:]),
            ("normalize_silver_to_gold", STAGE_NAMES[3:]),
            ("validate_gold_csv", STAGE_NAMES[4:]),
        ],
    )
    def test_stage_exception_propagates_and_halts_pipeline(self, stages, failing, skipped):
        stages[failing].side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            run_pipeline()
        ran = called_stage_names(stages)
        for name in skipped:
            assert name not in ran
        assert failing in ran

    def test_error_report_failure_propagates(self, stages):
        stages["write_error_report"].side_effect = OSError("disk full")
        with pytest.raises(OSError, match="disk full"):
            run_pipeline()

    def test_failure_is_not_logged_by_orchestrator(self, stages):
        stages["download_pdfs"].side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            run_pipeline()
        stages["logger"].error.assert_not_called()

    def test_logger_failure_propagates_before_any_stage(self, stages):
        stages["logger"].info.side_effect = OSError("log error")
        with pytest.raises(OSError, match="log error"):
            run_pipeline()
        assert called_stage_names(stages) == []


# ==============================================================================
# main / entry point
# ==============================================================================


class TestMain:
    def test_main_default_runs_pipeline_without_overwrite(self):
        with patch("orchestrator.run_pipeline") as run:
            main([])
        run.assert_called_once_with(overwrite_existing=False)

    def test_main_forwards_overwrite(self):
        with patch("orchestrator.run_pipeline") as run:
            main(["--overwrite-existing"])
        run.assert_called_once_with(overwrite_existing=True)

    def test_main_invalid_args_do_not_run_pipeline(self):
        with patch("orchestrator.run_pipeline") as run, pytest.raises(SystemExit):
            main(["--nope"])
        run.assert_not_called()

    def test_main_end_to_end_with_mocked_stages(self, stages):
        main(["--overwrite"])
        assert called_stage_names(stages) == EXPECTED_STAGE_ORDER
        assert stages["download_pdfs"].call_args.kwargs == {"overwrite_existing": True}

    def test_dunder_main_invokes_main(self):
        with patch("sys.argv", ["orchestrator.py", "--help"]), pytest.raises(SystemExit) as exc:
            runpy.run_path(orchestrator.__file__, run_name="__main__")
        assert exc.value.code == 0
