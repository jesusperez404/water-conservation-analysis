# AGENTS.md

## Project

This repository is a reproducible data engineering and analytics project for the
Weir River Water System serving Hingham, Hull, and North Cohasset, Massachusetts.

The initial source dataset is 15 official Town of Hingham monthly reports covering
October 2024 through December 2025.

Read `README.md`, `docs/data_dictionary.md`, and `database/schema.sql` before making
structural changes.

## Git workflow

- The active integration branch is `development`.
- Base project work on `development` unless the user explicitly requests otherwise.
- Do not merge to `main` unless explicitly requested.
- Keep commits focused on one extraction/data-engineering milestone.
- Do not commit generated review artifacts or raw source PDFs.

## Data handling

- `data/raw/*` contains downloaded source PDFs and is intentionally ignored.
- `data/processed/*` contains generated extraction/review artifacts and is ignored.
- `database/water.db` is currently tracked and represents the validated project DB.
- Do not silently change source-derived values.
- Preserve provenance: report month, source page, extraction method, and notes where
  supported by the schema.

## Extraction workflow

Work on one metric or report section at a time.

Required workflow:

1. Inspect the official source report structure.
2. Implement extraction.
3. Run against all 15 reports.
4. Compare extracted values against the source.
5. Treat missing source information as `NULL`, not zero, unless the report explicitly
   establishes zero.
6. If validation fails for even one report, do not modify the target DB table.
7. Only after all expected reports pass validation, load/rebuild the target table in a
   transaction.
8. Run `python scripts/check_database.py`.

Do not weaken validation or alter expected source values merely to make a test pass.

## Script convention

Metric scripts named `scripts/extract_*.py` should own both extraction and the final
validated database load.

Do not create a separate one-off loader when the extractor can safely validate first
and load afterward.

Prefer:

- `pathlib.Path`
- explicit validation failures
- SQLite transactions / rollback
- deterministic output
- source-page tracking
- full-table rebuild only after complete validation when that is the established
  pattern for the metric

Keep scripts usable on both Windows and Linux where practical.

## Completed validated datasets

The following datasets have been implemented and validated across the 15 reports:

- precipitation
- meter statistics
- operational events
- water production
- chemical usage
- customer service
- billing and collections
- field work orders
- maintenance capital

### Water production

`water_production` is chart-derived.

The extractor reconstructs the current-year daily chart series and derives monthly
values using this project convention:

- `finished_water_mgd` = mean of extracted daily Finished Water MGD
- `accord_pond_usage_mg` = sum of extracted daily Accord Pond Usage MG
- `accord_pond_level_ft` = mean of extracted daily Accord Pond Level feet

Daily chart candidates are generated under
`data/processed/water_production_review/` and are not committed.

Do not replace this mapping without documenting and validating the new analytical
definition.

### Chemical usage

`chemical_usage` contains eight normalized chemical observations per report month.
The extractor selects only the current report month for loading and cross-validates
values repeated in later reports before transactionally rebuilding the table.

`Dies./gen.` is not loaded as chemical usage because the reports do not define its
unit and the data dictionary does not classify it as a chemical.

### Customer service

`customer_service` contains the monthly total calls, reported service-level
percentage, and average speed of answer normalized to seconds. The source narrative's
agent-offered call count is retained in notes as supporting validation context.

### Billing and collections

`billing_collections` contains monthly billed revenue, collected revenue, aged
receivables, and 90+ receivables. February 2025 billed revenue and December 2024
90+ receivables use explicit chart fallbacks because their narrative values are stale
or malformed. March 2025 aged-receivables fields are `NULL` because the report repeats
February and provides no March chart values.

### Field work orders

`field_work_orders` contains two recurring measures per report month: `total` and
`collection_posting`. The August 2025 decline in reported total work orders is
preserved exactly as published.

### Maintenance capital

`maintenance_cap` contains one current-month `total` observation per report.
Monthly expenditure is the table's paid-maintenance value. Cumulative
expenditure includes reported estimated work not yet paid and reconciles to the
annual budget and remaining balance. January through March 2025 use
source-validated raster transcriptions guarded by worksheet-image hashes; the
other reports use selectable PDF table words.

## Current next target

Recurring report datasets represented by the schema are complete. Automated
database tests, monthly analytical views, and exploratory analysis are also
complete. The interactive dashboard is complete. The core first-party project is
therefore complete; external-data integration remains optional and must preserve
the same provenance standards.

## Useful commands

From the repository root:

```powershell
python scripts\extract_precipitation.py
python scripts\extract_meter_statistics.py
python scripts\extract_operations.py
python scripts\extract_water_production.py
python scripts\extract_chemical_usage.py --write-db
python scripts\extract_customer_service.py --write-db
python scripts\extract_billing_collections.py --write-db
python scripts\extract_field_work_orders.py --write-db
python scripts\extract_maintenance_cap.py --write-db
python database\apply_schema.py
python analysis\run_exploratory_analysis.py
python dashboard\build_dashboard_data.py
python -m http.server 8000 -d dashboard
python -m unittest discover -s tests -v
python scripts\check_database.py
```

## Repository documentation

Keep these synchronized as milestones are completed:

- `README.md`
- `docs/data_dictionary.md`
- `database/schema.sql` when schema changes

The README should accurately reflect dataset coverage and current extraction status.

## Working style

- Prefer inspecting and editing the repository directly over asking the user to move
  data between tools.
- When a source PDF is publicly available, use the official Town of Hingham source for
  validation where possible.
- Make concrete changes and run checks rather than repeatedly proposing speculative
  diagnostic snippets.
- When modifying a script, provide/commit the complete coherent change rather than
  leaving partial patch instructions.
- No emojis in repository documentation.
