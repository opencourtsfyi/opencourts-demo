# ETL

This folder contains the local-only data processing code for the demo. The ETL work is responsible for downloading source documents, converting or normalizing them into structured data, and producing the staged outputs used by the app.

## Purpose

The ETL layer supports the demo's Bronze -> Silver -> Gold pattern:

- Bronze: raw source data, including downloaded PDFs and minimally processed content
- Silver: cleaned, normalized, and structured data ready for downstream use
- Gold: curated, query-ready data prepared for presentation or consumption

The design emphasizes a local demo environment over production-grade infrastructure. The workflow is intentionally simple, transparent, and easy to inspect.

## Typical responsibilities

- Downloading source documents from local or remote inputs
- Converting PDF or document content into parseable text or structured records
- Normalizing field names, values, and formats
- Validating extracted content for completeness and consistency
- Producing intermediate and final output files for downstream use
- Supporting local reproducibility and debugging of each transformation stage

## Current structure

This repository follows a src-based layout for the ETL implementation:

```text
etl/
├── README.md
├── src/
│   ├── download/
│   │   └── ... source document retrieval logic
│   ├── transform/
│   │   └── ... cleaning, normalization, and parsing logic
│   ├── load/
│   │   └── ... output staging and persistence logic
│   ├── orchestrator/
│   │   └── ... pipeline coordination and execution
│   └── utils/
│       └── ... shared helpers and common functionality
├── tests/
│   └── ... ETL-focused test coverage
└── data/
    └── ... local inputs and generated output artifacts
```

## Guidance for changes

- Keep each stage focused on one responsibility inside `src/`.
- Preserve the Bronze -> Silver -> Gold progression.
- Prefer small, readable transformation steps over large, opaque scripts.
- Add or update tests when changing extraction, parsing, or output behavior.
- Keep output formats and file naming consistent across stages.
- Use environment variables or local config for paths and external inputs.
- Prefer keeping helper logic in `src/utils/` rather than scattering it across stage modules.

## Validation

Validate the ETL logic with the smallest relevant checks, such as:

- targeted unit tests for extraction or transformation helpers
- integration tests for end-to-end stage output
- checks to confirm output shapes and record counts are consistent

## Boundaries

- Keep the ETL code separate from runtime web API concerns.
- Avoid mixing frontend presentation logic into this layer.
- Keep local-only development assumptions explicit and easy to understand.
- Do not commit secrets, credentials, or environment-specific configuration values.
