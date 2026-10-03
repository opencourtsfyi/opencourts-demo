# logging_config.py
"""
Central logging configuration for the SC Probate Caseload ETL pipeline.
Import get_logger(__name__) in each stage module instead of using print(),
so every stage's output goes to both the console and a persistent log file.
"""

import logging
import os
from pathlib import Path

# Env var used to inject a log destination without code changes, e.g. a path
# mounted/synced to a central location in the cloud (see issue #2). If set,
# every module's logger will write to {PIPELINE_LOG_DIR}/pipeline.log in
# addition to the console, even if that module builds its logger at import
# time with no explicit log_dir argument.
LOG_DIR_ENV_VAR = "PIPELINE_LOG_DIR"


def get_logger(name, log_dir=None):
    """Returns a configured logger for the given module name.

    log_dir: if provided, also writes logs to {log_dir}/pipeline.log.
    If omitted, falls back to the PIPELINE_LOG_DIR environment variable
    if it's set. If neither is provided, logs only go to the console
    (useful for quick standalone runs).

    Safe to call more than once for the same name (e.g. once by a stage
    module at import time with no log_dir, once by the orchestrator with
    one) — console and file handlers are tracked independently, so a later
    call that supplies a log_dir still attaches a file handler even though
    the console handler was already attached by an earlier call. Without
    this, only the first caller's handlers would ever get attached, which
    is what silently dropped stage-module logs from the file previously.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    resolved_log_dir = log_dir if log_dir is not None else os.environ.get(LOG_DIR_ENV_VAR)

    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    has_file = any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    # Always log to console, but only attach once
    if not has_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Optionally also log to a file, for runs that need a persistent audit
    # trail (or that stream logs to a central/cloud location via the env var)
    if resolved_log_dir is not None and not has_file:
        resolved_log_dir = Path(resolved_log_dir)
        resolved_log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(resolved_log_dir / "pipeline.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
