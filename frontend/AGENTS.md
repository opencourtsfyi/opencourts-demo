# AGENTS.md

## Project Overview
Frontend application for the project. This is a TypeScript-based single-page application built with Vite.

## Tech Stack
- **Framework:** Vite
- **Language:** TypeScript
- **Testing:** Vitest
- **Runtime:** Browser-based client app

## Commands
- **Install dependencies:** `npm install`
- **Run dev server:** `npm run dev`
- **Build for production:** `npm run build`
- **Preview production build:** `npm run preview`
- **Run tests:** `npm test`
- **Type-check:** `npm run typecheck`

<!-- ## Project Structure
```text
frontend/
├── src/                    # Application source files
├── tests/                 # Frontend tests
├── index.html             # App entry HTML
├── package.json           # Scripts and dependencies
├── tsconfig.json          # TypeScript configuration
├── vite.config.ts         # Vite configuration
├── AGENTS.md              # Frontend-specific instructions
└── node_modules/          # Installed dependencies
``` -->

## Coding Style & Rules
- Use TypeScript for all application logic.
- Prefer explicit types for data models and function signatures.
- Keep components, utilities, and tests small and focused.
- Use modern browser-safe JavaScript and avoid unnecessary polyfills.
- Prefer readable, maintainable code over clever abstractions.
- Use `const` and `let` appropriately; prefer `const` by default.

## Frontend Conventions
- Write feature or component-specific tests in `tests/` or near the related source files.
- Keep UI logic separate from API calls when practical.
- Treat the backend as an integration boundary; model request/response shapes explicitly.
- Avoid hardcoded secrets or environment-specific values in source.
- Prefer relative or centralized configuration for API URLs.

## Styling & UI Guidance
- Keep the DOM structure semantic and accessible.
- Prefer simple, reusable patterns for state and rendering.
- Avoid inline logic that is hard to test and maintain.

## Testing Instructions
- Add or update tests for any behavior change.
- Use Vitest for unit and component-level validation.
- Prefer targeted tests over broad suites when iterating.

## Boundaries
**Always do:**
- Validate with the relevant frontend test or type-check command.
- Keep API contracts in sync with backend changes.
- Use environment variables for any configuration that changes by environment.
- Keep the app lightweight and framework-free unless there is a clear project need.

**Ask first:**
- Adding new frontend tooling or build dependencies
- Large UI refactors that affect common pages or shared patterns
- Changes that affect backend contracts or shared API behavior
- Adding a new UI framework.

**Never do:**
- Commit secrets or tokens
- Put backend-only logic into the frontend
- Make broad formatting or unrelated code churn in the same PR
