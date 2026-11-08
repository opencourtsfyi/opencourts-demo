# AGENTS.md

## Project Overview
Extract-transform-load for south carolina probate courts.

## Tech Stack
- **Languages:** Python

## Commands
- **Install (dev):** `python -m venv .venv` then activate and `pip install -r requirements-dev.txt`
- **Run:** `python orchestrator.py` (from `src/`, or with `src` on `PYTHONPATH`)
- **Test:** `pytest`
- **Lint:** `ruff check src tests`
- **Typecheck:** `ty check`

Lint and typecheck must exit non-zero on findings. Prefer a local `.venv` so `ty` can resolve third-party imports.

## Boundaries

**Always do:**
- Include unit tests for new functions
- Run lint before committing
- Use environment variables for configuration

**Ask first:**
- Adding new dependencies
- Modifying CI/CD pipelines
- Changes to authentication or authorization logic

**Never do:**
- Commit secrets, API keys, or connection strings
- Edit generated migration files
- Push directly to master branch