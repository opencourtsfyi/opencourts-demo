# Power BI Desktop: 5-minute setup

This guide is for **developers and analysts working from a checkout of this repo** on a Windows machine. You will load OpenCourts **Gold** caseload data into [Power BI Desktop](https://powerbi.microsoft.com/desktop/) so you can filter and chart it locally.

> **NOTE**: you do **not** need an OpenCourts Azure account, a Power BI Pro license, or a sign-in for this walkthrough. Everything stays on your PC (or talks only to `localhost`).

## Contents

- [Prerequisites](#prerequisites)
- [What “Gold” means](#what-gold-means)
- [Load Gold data into Power BI](#load-gold-data-into-power-bi)
  - [Install and open Power BI Desktop](#install-and-open-power-bi-desktop)
  - [Option A — Local CSV file (fastest)](#option-a--local-csv-file-fastest)
  - [Option B — Web connector (local HTTP / future REST API)](#option-b--web-connector-local-http--future-rest-api)
- [Suggested first visual](#suggested-first-visual)
- [Refresh](#refresh)
- [Troubleshooting](#troubleshooting)
- [Who this is for (and what it is not)](#who-this-is-for-and-what-it-is-not)

## Prerequisites

| Need | Notes |
| --- | --- |
| Windows PC | Power BI Desktop does not run on macOS/Linux. |
| This repository cloned locally | You need the sample CSV under `docs/sample-data/` (see [What “Gold” means](#what-gold-means) for alternatives). |
| [Power BI Desktop](https://powerbi.microsoft.com/desktop/) installed | Free. Install from the [Microsoft Download Center](https://www.microsoft.com/en-us/download/details.aspx?id=58494) (64-bit). |

## What “Gold” means

This project’s ETL uses a Bronze → Silver → Gold pattern (see [`etl/README.md`](../etl/README.md)):

- **Bronze** — raw source PDFs as downloaded  
- **Silver** — tables extracted from those PDFs, still close to the source layout  
- **Gold** — cleaned, normalized, analysis-ready rows (the dataset Power BI should load)

When this guide says **Gold**, it means the Gold CSV (`caseloads_normalized.csv`): one metric value per county / month / year, ready for charts and filters.

### Gold schema

| Column | Example |
| --- | --- |
| `file` | `estate_monthly_caseload_2023_to_2024_bronze.csv` |
| `category` | `Estate` |
| `month` | `7` |
| `year` | `2023` |
| `county` | `Abbeville` |
| `metric` | `Added`, `Disposed`, `Pending first of month`, … |
| `value` | `12` |

### Which Gold file to use

For this walkthrough, use the committed sample:

`docs/sample-data/caseloads_normalized.csv`

If you have already run the ETL pipeline (`cd etl`, then `python orchestrator.py`), you can use the pipeline’s Gold output instead:

`etl/data/cases_gold/caseloads_normalized.csv`

Both files share the same schema. The steps below use the sample path; substitute the ETL path if you prefer.

## Load Gold data into Power BI

Get Desktop ready, then pick **one** load path: a local file (**Option A**) or a URL via the Web connector (**Option B**).

### Install and open Power BI Desktop

1. Install Desktop from the [Microsoft Download Center](https://www.microsoft.com/en-us/download/details.aspx?id=58494) (64-bit).
2. Open it from the Windows **Start** menu: search for **Power BI Desktop** and launch it.
3. Click on **blank report** on the home screen.

> **NOTE**: if Desktop asks you to **sign in**, you can skip or close that for this local demo.

Then continue with **Option A** or **Option B**.

### Option A — Local CSV file (fastest)

1. On the ribbon: **Home** → **Get data** → **Text/CSV**.
2. Browse to your clone of this repo and select `docs/sample-data/caseloads_normalized.csv` (or your ETL Gold CSV).
3. Confirm the column preview, then click **Load** (or **Transform data** to filter in Power Query first).

You now have a table in the report. Continue to [Suggested first visual](#suggested-first-visual).

### Option B — Web connector (local HTTP / future REST API)

Use this when you want the same **Get data → Web** flow you would use against a running HTTP API. Power Query loads from a URL instead of a file path.

**Prerequisite for Option B:** Python 3 on your `PATH` (`python --version` should print a 3.x version). That is only needed to run the tiny local file server below.

#### 1. Serve the sample CSV on localhost

In PowerShell, copy and paste this block (it finds the repo root via `git`, so your current folder does not have to be the root):

```powershell
Set-Location (Join-Path (git rev-parse --show-toplevel) "docs/sample-data")
python -m http.server 8000 --bind 127.0.0.1
```

Leave that window open. You should see `Serving HTTP on 127.0.0.1 port 8000`.

**Check in a browser first** (before Power BI): open

`http://127.0.0.1:8000/caseloads_normalized.csv`

You should see CSV text (header row starting with `file,category,month,...`). If the browser fails, fix the server / path before continuing.

To serve ETL Gold instead:

```powershell
Set-Location (Join-Path (git rev-parse --show-toplevel) "etl/data/cases_gold")
python -m http.server 8000 --bind 127.0.0.1
```

#### 2. Connect with Power Query (`Web.Contents`, not “From Web” UI)

**Do not use Home → Get data → Web for this CSV URL.** In current Power BI Desktop that path often uses `Web.BrowserContents` (meant for HTML pages) and fails on a raw CSV with:

`[DataSource.Error] We were unable to retrieve the contents of the web page`

For a CSV or API file over HTTP, use a **Blank query** and `Web.Contents` (Microsoft’s connector for non-HTML payloads such as CSV/JSON):

1. **Home** → **Get data** → **Blank query**.  
   (If needed: **Get data** → **More…** → search **Blank query**.)
2. In Power Query Editor, open **Home** → **Advanced Editor**.
3. Replace the stub with this (copy/paste the whole block):

```powerquery
let
  Source = Csv.Document(
    Web.Contents("http://127.0.0.1:8000/caseloads_normalized.csv"),
    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
  ),
  #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
  #"Promoted Headers"
```

4. Click **Done**.
5. If asked how to authenticate, choose **Anonymous**.
6. Confirm the Gold columns in the preview, then **Home** → **Close & Apply**.

If Power BI asks about a privacy level for `127.0.0.1`, choose **Organizational**, or use **Ignore Privacy Levels** for this local-only demo (**File** → **Options and settings** → **Options** → **Privacy**).

#### 3. When the Flask API exists

Issue #16 plans a local Flask API (for example `http://127.0.0.1:5000/api/gold/`). When that endpoint serves Gold CSV, use the same **Blank query** + `Web.Contents` / `Csv.Document` pattern (or `Json.Document` if the API returns JSON). Until then, Option B with `python -m http.server` exercises the HTTP load path end to end.

## Suggested first visual

These steps assume you already **Load**ed the Gold table (Option A or B) and are on the **Report** canvas (left-hand icons: the bar-chart icon is Report view).

A **field well** is a drop target where you put a column: the labeled boxes under **Build visual** (**Y-axis**, **X-axis**, **Field**, and so on) and the filter cards in the **Filters** pane. Drag a field from **Data** onto a well; Power BI shows it as a pill.

1. Click a blank area of the canvas so no visual is selected.
2. In the **Visualizations** pane (usually on the right), click the **Clustered bar chart** icon (tooltip says “Clustered bar chart”). An empty chart placeholder appears on the canvas; leave it selected.
3. In the **Data** pane (far right; lists your table and fields), find `category`. Drag it into the **Filters on this visual** well in the **Filters** pane. Expand the filter card, check **Estate**, and click elsewhere so the filter applies.
4. Do the same with `metric`: drag it to **Filters on this visual**, then check **Disposed** (or **Added**).
5. With the bar chart still selected, use the field wells under **Build visual** in the **Visualizations** pane (directly under the chart-type icons):  
   - Drag `county` from **Data** onto **Y-axis**.  
   - Drag `value` from **Data** onto **X-axis** (not Legend / Tooltips). The pill should read **Sum of value**.  
   - If the pill says **Count of value** instead, click the small ▼ on that pill → **Sum**.
6. OPTIONAL - add a slicer for year:  
   1. Click a **blank** spot on the canvas so the bar chart is *not* selected.  
   2. In **Visualizations**, click the **Slicer** icon:  
      ![Slicer icon in the Visualizations pane](images/powerbi-slicer-icon.png)  
   3. With that new slicer selected, stay on **Build visual** (not the **Filters** pane). Drag `year` from **Data** into the slicer’s **Field** well (under the chart icons — same place **Y-axis** / **X-axis** were for the bar chart).  
      - Do **not** put `year` under **Filters on this visual**. That only filters the selected visual; an empty slicer filtered this way will not change the bar chart.  
      - If the slicer still says “Select or drag fields…”, `year` is not in **Field** yet.  
   4. Because `year` is numeric, Power BI often opens a range control (**is less than** / **Between**). Switch it to a year list: with the slicer selected, click on **Year** under filters and change the **Filter Type** from **Advanced Filtering** to **Basic Filtering**. Then click one or more years in the list.  
   5. The bar chart updates if both visuals are on the same page (default).  
   6. Repeat with a second slicer and the `month` field if you want month filtering too (same Style → **List** tip if you see a range control).

The map UI’s clearance rate is `Disposed / Added` over a date range. In Power BI you can build the same idea later with a measure once both metrics are in the model.

## Refresh

- **Option A:** **Home** → **Refresh** reloads from the same file path.  
- **Option B:** Keep the local server (or Flask app) running, then **Home** → **Refresh**.

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| “Power BI Desktop” not in Start menu | Finish the Download Center install; reboot if the shortcut is missing. |
| Sign-in dialog blocks you | Dismiss or skip — not required for local CSV/Web-to-localhost. |
| Browser cannot open `http://127.0.0.1:8000/caseloads_normalized.csv` | Run the serve commands from repo root with `--bind 127.0.0.1`; confirm port `8000` is free; keep the server window open. |
| `[DataSource.Error] We were unable to retrieve the contents of the web page` | You likely used **Get data → Web** (browser/HTML path). Use **Blank query** + `Web.Contents` / `Csv.Document` as in Option B step 2. Confirm the URL works in a browser; auth **Anonymous**; serve with `--bind 127.0.0.1`. |
| Empty or wrong columns | Point at `caseloads_normalized.csv`, not Silver/Bronze files. |
| ETL path missing | Use `docs/sample-data/caseloads_normalized.csv`, or run the ETL first. |
| Privacy / firewall prompt | Allow local loopback for Power BI, or use Option A (file). |

## Who this is for (and what it is not)

| | This guide (Desktop, local) | Power BI *Service* (cloud) |
| --- | --- | --- |
| App | Power BI Desktop on your PC | app.powerbi.com in a browser |
| Account | None required for local load | Microsoft / work account in a tenant |
| Data | Files or `localhost` URLs from this repo | Published datasets in the cloud |
| Sharing | Send a `.pbix` file, or screenshots | Workspace / app sharing (needs licenses) |

This ticket (#17) only covers the **Desktop + local Gold** path so someone cloning the demo can explore the data in Power BI without org cloud setup.
