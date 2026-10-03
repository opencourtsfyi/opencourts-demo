# AGENTS.md

## Project Overview
This repository contains a full-stack application of a local-only demonstration of the Bronze -> Silver -> Gold transformation of reports on probate cases opened and closed in the South Carolina's Supreme Court. We want a simple, usable demo to convey the idea of OpenCourts early rather than waiting until the project is complete. The project is split into frontend and backend concerns:
- `frontend/`: TypeScript single-page app built with Vite
- `backend/`: Python flask web api and pipeline for ETL processing
- root: shared repo-level configuration, tooling, and documentation

## Shared Principles
- Keep the frontend and backend contracts aligned.
- Prefer small, focused changes that do not cross boundaries unless required.
- Use environment variables for configuration and secrets.
- Never commit secrets, API keys, tokens, or local connection strings.
- Keep commits and changes scoped to the relevant app area.
- Use the appropriate project-level AGENTS.md in each folder for local conventions.

## Repository Structure
```text
/
├── backend/                 # Python Flask web api with ETL pipeline for data transformation
├── frontend/                # TypeScript single page app
├── .gitignore
├── AGENTS.md                # Shared repo guidance
├── README.md
└── opencourts-demo.code-workspace
```

## Cross-Project Rules
- If a frontend change affects an API contract, update the backend contract at the same time.
- If a backend change affects UI assumptions, validate the frontend behavior.
- Prefer shared naming and route conventions that are easy to reason about across both layers.
- Preserve compatibility unless the feature explicitly requires a breaking change.

<!-- ## Commands
### Root-level repo tasks
- TODO -->

## Autonomy rules:
- Do not ask for permission before running build/test/lint.
- Do not ask for permission when performing read-only operations within the workspace file path.
- Do not ask for permission when performing read-only git operations.
- Run the smallest relevant verification command.
- Keep changes scoped to the task.
- Do not touch unrelated files.
- If blocked by missing data, secrets, or a decision, explain the blocker clearly and stop.
- For destructive actions like reset, delete, or force-push, ask before proceeding.

## Testing Expectations
- Frontend changes require relevant Vitest coverage or a focused validation run.
- Backend changes require matching unit/integration tests.
- Run the smallest relevant validation before finishing a task.

## Boundaries
**Always do:**
- Keep changes small and focused.
- Preserve existing conventions.
- Keep each app area responsible for its own files and logic.
- Update both sides of a contract when required.
- Prefer deterministic, repeatable tooling.
- Support cross-platform development (Windows and Mac / OSx).
- Keep README.md files accurate.

**Ask first:**
- If you update code, ask before updating corresponding tests.
- If you update tests, ask before updating corresponding code.
- Adding new shared repo-wide tooling
- Changing CI/CD or deployment pipelines
- Introducing cross-project dependencies or structure changes

**Never do:**
- Commit secrets or environment-specific credentials
- Mix frontend code into the backend app or vice versa
- Add unrelated repo-wide cleanup as part of a feature change
