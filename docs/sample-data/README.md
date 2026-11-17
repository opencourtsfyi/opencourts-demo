# Sample data

`caseloads_normalized.csv` is a Gold-shaped sample for local demos and the [Power BI setup guide](../powerbi-setup.md).

It mirrors the schema of ETL output `etl/data/cases_gold/caseloads_normalized.csv` and is generated from `frontend/public/data/caseloads_sample.json`.

Regenerate from the repository root:

```powershell
python docs/sample-data/generate_caseloads_normalized.py
```

A CI test (`etl/tests/test_docs_sample_caseloads.py`) checks that the committed CSV still matches that generator so the Power BI walkthrough cannot drift silently from the frontend sample.
