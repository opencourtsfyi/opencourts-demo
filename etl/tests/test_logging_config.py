import logging

import pytest

from logging_config import LOG_DIR_ENV_VAR, LOG_LEVEL_ENV_VAR, setup_logging


def setup_logging_without_capture(*args, **kwargs):
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    setup_logging(*args, **kwargs)


@pytest.fixture(autouse=True)
def isolate_root_logger():
    root_logger = logging.getLogger()
    original_level = root_logger.level
    original_handlers = root_logger.handlers[:]

    for handler in original_handlers:
        root_logger.removeHandler(handler)

    try:
        yield
    finally:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()
        for handler in original_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(original_level)


@pytest.mark.parametrize("env_value", [None, "", "   "], ids=["unset", "empty", "whitespace"])
def test_console_only_when_log_directory_is_missing_or_blank(monkeypatch, env_value):
    monkeypatch.delenv(LOG_LEVEL_ENV_VAR, raising=False)
    if env_value is None:
        monkeypatch.delenv(LOG_DIR_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(LOG_DIR_ENV_VAR, env_value)

    setup_logging_without_capture()

    root_logger = logging.getLogger()
    console_handlers = [
        handler
        for handler in root_logger.handlers
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
    ]
    file_handlers = [handler for handler in root_logger.handlers if isinstance(handler, logging.FileHandler)]
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) == 1
    assert len(console_handlers) == 1
    assert file_handlers == []


@pytest.mark.parametrize("level_name", ["WARNING", "DEBUG"])
def test_log_level_can_be_set_with_environment_variable(monkeypatch, level_name):
    monkeypatch.setenv(LOG_LEVEL_ENV_VAR, level_name)

    setup_logging_without_capture()

    assert logging.getLogger().level == getattr(logging, level_name)


@pytest.mark.parametrize("log_dir", ["", "   "])
def test_blank_explicit_log_directory_does_not_create_file(tmp_path, monkeypatch, log_dir):
    monkeypatch.delenv(LOG_DIR_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)

    setup_logging_without_capture(log_dir)

    assert not (tmp_path / "pipeline.log").exists()


@pytest.mark.parametrize("input_kind", ["path", "string", "nested", "environment"])
def test_file_and_console_configuration(tmp_path, monkeypatch, input_kind):
    expected_log_dir = tmp_path / "logs"
    log_dir = expected_log_dir
    if input_kind == "string":
        log_dir = str(log_dir)
    elif input_kind == "nested":
        expected_log_dir = tmp_path / "a" / "b" / "c"
        log_dir = expected_log_dir
    elif input_kind == "environment":
        monkeypatch.setenv(LOG_DIR_ENV_VAR, str(log_dir))
        log_dir = None
    else:
        monkeypatch.delenv(LOG_DIR_ENV_VAR, raising=False)

    if input_kind == "nested":
        assert not expected_log_dir.exists()

    setup_logging_without_capture(log_dir)

    root_logger = logging.getLogger()
    assert len(root_logger.handlers) == 2
    assert sum(isinstance(handler, logging.FileHandler) for handler in root_logger.handlers) == 1
    assert sum(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in root_logger.handlers
    ) == 1
    assert (expected_log_dir / "pipeline.log").exists()


def test_explicit_log_directory_takes_precedence(tmp_path, monkeypatch):
    explicit_dir = tmp_path / "explicit"
    environment_dir = tmp_path / "environment"
    monkeypatch.setenv(LOG_DIR_ENV_VAR, str(environment_dir))

    setup_logging_without_capture(explicit_dir)

    assert (explicit_dir / "pipeline.log").exists()
    assert not environment_dir.exists()


@pytest.mark.parametrize("first_configuration", ["console", "file"])
def test_repeated_setup_preserves_initial_configuration(tmp_path, monkeypatch, first_configuration):
    monkeypatch.delenv(LOG_DIR_ENV_VAR, raising=False)
    first_log_dir = tmp_path / "first"
    second_log_dir = tmp_path / "second"

    if first_configuration == "console":
        setup_logging_without_capture()
    else:
        setup_logging_without_capture(first_log_dir)

    previous_handlers = logging.getLogger().handlers[:]
    setup_logging(second_log_dir)

    root_logger = logging.getLogger()
    assert root_logger.handlers == previous_handlers
    assert sum(isinstance(handler, logging.FileHandler) for handler in root_logger.handlers) == (
        first_configuration == "file"
    )


def test_child_logger_writes_formatted_message_to_file(tmp_path, monkeypatch):
    monkeypatch.delenv(LOG_DIR_ENV_VAR, raising=False)
    log_dir = tmp_path / "logs"
    setup_logging_without_capture(log_dir)

    logging.getLogger("etl.test_stage").info("test message")
    for handler in logging.getLogger().handlers:
        handler.flush()

    log_text = (log_dir / "pipeline.log").read_text()
    assert " | INFO | etl.test_stage | test message" in log_text