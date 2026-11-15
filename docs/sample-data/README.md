# Sample data

`caseloads_normalized.csv` is a Gold-shaped sample for local demos and the [Power BI setup guide](../powerbi-setup.md).

It mirrors the schema of ETL output `etl/data/cases_gold/caseloads_normalized.csv` and was derived from `frontend/public/data/caseloads_sample.json`.

Regenerate from the frontend sample (from the repository root):

```powershell
python -c "import csv, json; from pathlib import Path; rows=json.load(open('frontend/public/data/caseloads_sample.json', encoding='utf-8')); cols=['file','category','month','year','county','metric','value']; out=Path('docs/sample-data/caseloads_normalized.csv'); f=out.open('w', encoding='utf-8', newline=''); w=csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows({c:r.get(c,'') for c in cols} for r in rows); f.close(); print(len(rows), 'rows')"
```
