# OpenCourts Frontend

Frontend single-page application for visualizing South Carolina probate caseload data. Built with vanilla TypeScript and Vite.

## Tech Stack

- **Tooling & Dev Server:** [Vite](https://vite.dev/)
- **Language:** [TypeScript](https://www.typescriptlang.org/)
- **Testing:** [Vitest](https://vitest.dev/) with JSDOM and [Playwright](https://playwright.dev/) for browser end-to-end tests
- **Styling:** Vanilla CSS

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) (v22+, see `.node-version`)
- [npm](https://www.npmjs.com/) (bundled with Node.js)

### Installation

From the repository root:

```bash
cd frontend
npm install
```

## Available Scripts

Run these scripts from within the `frontend/` directory:

| Command | Description |
|---|---|
| `npm run dev` | Start the local Vite development server with HMR. |
| `npm test` | Run all unit and integration tests with Vitest. |
| `npm run test:unit` | Run unit tests (`src/**/*.test.ts`) with Vitest. |
| `npm run test:integration` | Run integration tests (`tests/integration/**/*.test.ts`) with Vitest. |
| `npm run test:e2e` | Run browser end-to-end tests (`e2e/**/*.spec.ts`) with Playwright. |
| `npm run typecheck` | Type-check the project without emitting output files (`tsc --noEmit`). |
| `npm run build` | Compile TypeScript and bundle production assets into `dist/`. |
| `npm run preview` | Locally preview the production build output from `dist/`. |
| `npm run format` | Runs prettier formatting on the source and tests |
| `npm run format:` | Runs formatting on the source and tests (HTML, CSS, TS) |
| `npm run format:check` | Checks formatting on the source and tests but does not modify (HTML, CSS, TS) |