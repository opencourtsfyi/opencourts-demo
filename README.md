# OpenCourts Demo

[![Tests](https://github.com/opencourtsfyi/opencourts-demo/actions/workflows/tests.yml/badge.svg)](https://github.com/opencourtsfyi/opencourts-demo/actions/workflows/tests.yml)

A fullstack demonstration of opencourts.

## Requirements
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — Python version and dependency management (`etl/.python-version`, `etl/pyproject.toml`, `etl/uv.lock`). Run `cd etl && uv sync --locked` to create the local `.venv` using the locked dependencies in the `etl/pyproject.toml`.
- **[fnm](https://github.com/Schniz/fnm#installation)** — Node.js version management ([`frontend/.node-version`](frontend/.node-version)). Run `cd frontend && fnm use` to install & use the correct Node.js version. Then to install dependencies using the lockfile, run `npm ci`.

## Project Structure
- [`etl/`](etl/README.md): Local-only data pipeline transforming annual court reports into clean data.
- [`backend/`](backend/README.md): Python Flask web API for browsing and downloading data.
- [`frontend/`](frontend/README.md): TypeScript single-page application for data visualization.
- [`docs/`](docs/powerbi-setup.md): Short setup guides (for example Power BI Desktop).

## Tutorials
- [Power BI Desktop setup (≈5 minutes)](docs/powerbi-setup.md) — load Gold caseload CSV locally or via the Power Query Web connector.
