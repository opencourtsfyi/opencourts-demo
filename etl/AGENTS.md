# AGENTS.md

## Project Overview
Extract-transform-load for south carolina probate courts.

## Tech Stack
- **Languages:** Python

## Commands
- **Run:** python orchestrator.py

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
## Commands
- **Run:** python orchestrator.py
- **Test:** pytest
