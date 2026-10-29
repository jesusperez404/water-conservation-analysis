# Water Conservation Analysis

A reproducible PDF-to-SQLite analysis pipeline and interactive dashboard for the
**Weir River Water System**, serving Hingham, Hull, and North Cohasset,
Massachusetts. The current release covers **15 official monthly reports from
October 2024 through December 2025**.

**Core project complete:** all nine recurring datasets are extracted and
source-validated, the database has analytical views and integrity checks, and
the repository includes exploratory findings and an offline-friendly dashboard.
External data and longer-term modeling remain future work.

## View the dashboard

The checked-in dashboard includes its data snapshot. From the repository root,
serve it with Python; no package installation or build step is needed to view it:

```sh
python -m http.server 8000 --bind 127.0.0.1 -d dashboard
```

Open [localhost:8000](http://localhost:8000). Use an HTTP server rather than
opening `index.html` directly, because the page fetches its JSON snapshot.

The dashboard supports date-range and metric filtering, production and pond-use
comparison, per-chemical trends, anomaly review, dataset coverage, monthly
details, and filtered CSV export. It has no CDN or external-service dependency.
See [dashboard instructions](dashboard/README.md) for regeneration details.
A separately hosted copy is a snapshot and does not automatically synchronize
with repository changes.

## Dataset coverage

| Dataset | Report months | Rows | Grain |
|---|---:|---:|---|
| Report metadata | 15/15 | 15 | Report month |
| Precipitation | 15/15 | 15 | Month |
| Meter statistics | 15/15 | 15 | Month |
| Operational events | 15/15 | 81 | Month and reported event type |
| Water production | 15/15 | 15 | Month |
| Chemical usage | 15/15 | 120 | Month and chemical; eight per month |
| Customer service | 15/15 | 15 | Month |
| Billing and collections | 15/15 | 15 | Month |
| Field work orders | 15/15 | 30 | Month and work-order type; two per month |
| Maintenance CAP | 15/15 | 15 | Month; current-report total |

Complete dataset coverage does not mean every optional field is populated.
Unreported values remain `NULL`.

Sources are the [Town of Hingham monthly water-system reports](https://www.hingham-ma.gov/885/Water-System-Reports).
Exact report URLs and provenance are retained in `reports` and the observation
tables. See the [data dictionary](docs/data_dictionary.md) and
[database schema](database/schema.sql) for definitions.

## Findings and interpretation

- Mean daily finished-water production ranges from **2.75 MGD in December 2024**
  to **5.38 MGD in July 2025**.
- Accord Pond usage is strongly associated with production in this window
  (**Pearson r = 0.96**). Monthly precipitation has little observed linear
  association (**r = 0.03**).
- Three observations meet the exploratory two-standard-deviation screening
  threshold: November 2024 maintenance paid, August 2025 estimated meter reads,
  and October 2025 precipitation. They remain unchanged as source-validated
  observations; flags are review candidates, not errors or evidence of fraud.

Read the [exploratory analysis](docs/exploratory_analysis.md),
[correlation results](analysis/results/correlations_with_finished_water.csv),
[anomaly results](analysis/results/anomalies.csv), and
[monthly summary](analysis/results/monthly_system_summary.csv).

Fifteen months are insufficient for robust seasonal decomposition, causal
attribution, or evaluated forecasting. Small samples, shared seasonality, and
multiple comparisons limit interpretation of correlations and p-values.
Customer-consumption and authorized-unbilled-use volumes are unavailable, so
**water loss cannot be calculated** from production alone. Aggregate billing
cannot establish improper individual charges. Population, development,
temperature, drought, and groundwater data have not been joined.

Maintenance cumulative totals can be restated. Use each report's snapshot;
differences between successive cumulative balances are not exact cash flows.

## Development setup

Use an isolated Python environment. The full dependency snapshot in
`requirements.txt` includes notebook/GIS tooling and Windows-specific
`pywinpty`; it is not a minimal cross-platform dashboard dependency list.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For Linux/macOS, a focused environment for the pipeline, analysis, and tests can
be installed without Windows notebook dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pandas numpy scipy matplotlib PyMuPDF
```

The focused installation is not a pinned reproduction of the full Windows
environment. Run all commands below from the repository root.

## Validate and regenerate

The validated SQLite snapshot is tracked at `database/water.db`. A fresh clone
can validate it and regenerate analytical outputs without rerunning extractors:

```sh
python scripts/check_database.py
python -m unittest discover -s tests -v
python analysis/run_exploratory_analysis.py
python dashboard/build_dashboard_data.py
```

The analysis command rewrites result CSVs, figures, and its findings document;
the dashboard builder rewrites `dashboard/data/dashboard.json`. Review generated
diffs before committing. Neither command is a substitute for source validation.

To apply the schema and refresh analytical views explicitly:

```sh
python database/apply_schema.py
```

This command modifies SQLite; it is not required simply to view the dashboard.
The three views are `monthly_system_summary`, `monthly_operations_summary`, and
`monthly_dataset_coverage`. Chemicals remain separate because units differ.

## Source extraction and safeguards

Raw PDFs and extraction-review artifacts are deliberately ignored by Git.
To retrieve the 15 reports using the URLs already in the tracked database:

```sh
python scripts/download_reports.py
```

The downloader writes PDFs under `data/raw/` and updates report download
metadata. For an empty database, schema initialization and
`database/seed_reports.py` must precede downloading. Do not reseed or rebuild the
validated snapshot merely to browse the results.

Extraction follows this sequence: inspect source reports, extract candidates,
validate all 15 reports, load transactionally, then run integrity checks.
Review individual script options and the [project guidance](AGENTS.md) before
running an extractor; some scripts write to SQLite as part of their normal run.
The later extractors expose an explicit `--write-db` load option.

Rules carried through the pipeline:

- Preserve report month, source page, extraction method, units, and notes.
- Never alter a validated source value to make a check pass; missing is `NULL`,
  not zero or a carried-forward observation.
- Production uses the chart's current-year series and its own Y axis:
  `finished_water_mgd` is mean daily MGD, `accord_pond_usage_mg` is total monthly
  MG, and `accord_pond_level_ft` is mean daily feet.
- Chemicals are current-month observations cross-checked against repeated
  history. Do not combine different chemical units. Aluminum sulfate retains
  its unresolved `report-specific` unit; `Dies./gen.` is excluded.
- February 2025 billing and December 2024 90+ receivables use documented chart
  fallbacks. March 2025 aged receivables remain `NULL` because current-month
  values are absent.
- Maintenance paid monthly expense is separate from cumulative estimates of
  work completed but unpaid. Budget minus cumulative expense must reconcile to
  remaining budget; negative balances are preserved. January–March 2025 raster
  transcriptions are guarded by worksheet-image hashes.
- Preserve the source-reported August 2025 work-order decline and 51% estimated
  reads rather than normalizing them away.

## Repository map

| Location | Contents |
|---|---|
| `database/` | Tracked SQLite snapshot, schema, schema application, report seeding |
| `scripts/` | Report downloader, nine dataset extractors, integrity checker |
| `analysis/` | Reproducible analysis script, result CSVs, figures |
| `dashboard/` | Static HTML/CSS/JavaScript, snapshot builder, generated JSON |
| `docs/` | Data dictionary and exploratory findings |
| `tests/` | Extractor, database, analysis, and dashboard regression checks |
| `notebooks/` | Setup and report exploration notebooks |
| `data/raw/` | Downloaded PDFs; ignored, not included in a clone |
| `data/processed/` | Generated source-review artifacts; ignored |

The main pipeline uses Python, PyMuPDF, SQLite, pandas, NumPy, SciPy, and
Matplotlib. The dashboard uses browser-native HTML, CSS, JavaScript, and SVG.

## Completed milestones and future work

- [x] Project setup and official report inventory
- [x] Nine recurring datasets extracted and source-validated across 15 reports
- [x] Transactional loading, integrity checks, and monthly analytical views
- [x] Automated extractor/database/analysis/dashboard tests
- [x] Exploratory report, reproducible figures, correlations, and anomaly flags
- [x] Interactive static dashboard and filtered CSV export
- [ ] Extend report history and select explicit external-data hypotheses
- [ ] Join weather, drought, groundwater, Census, land-use, or permit data with
      documented geographic and temporal alignment
- [ ] Obtain consumption and authorized-unbilled-use records for a water balance
- [ ] Add supported seasonal modeling and forecasting after sufficient history
- [ ] Produce broader executive/technical reporting and reusable municipal tooling

The first-party report pipeline and descriptive dashboard are complete. These
future items are extensions, not claims that causal analysis or water-loss
measurement has already been delivered. Evidence should determine conclusions,
including when it rejects the original hypothesis.

## Contributing

Use `development` for integration and focused feature branches for new work.
Open a pull request for review before changes enter `main`. Keep documentation
and provenance synchronized; do not commit raw PDFs or processed review files.
For changes affecting data or outputs, run the integrity checker and relevant
tests and review the generated diffs. See [AGENTS.md](AGENTS.md) for the full
extraction and repository workflow.
