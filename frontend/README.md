# OpenCourts Frontend

Frontend single-page application for visualizing South Carolina probate caseload data. Built with vanilla TypeScript and Vite.

## Tech Stack

- **Tooling & Dev Server:** [Vite](https://vite.dev/)
- **Language:** [TypeScript](https://www.typescriptlang.org/)
- **Testing:** [Vitest](https://vitest.dev/) with JSDOM
- **Styling:** Vanilla CSS

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) (v20+ or LTS recommended; v22 used in CI)
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
| `npm test` | Run the test suite with Vitest. |
| `npm run typecheck` | Type-check the project without emitting output files (`tsc --noEmit`). |
| `npm run build` | Compile TypeScript and bundle production assets into `dist/`. |
| `npm run preview` | Locally preview the production build output from `dist/`. |