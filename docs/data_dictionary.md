# Water System Report Data Dictionary

## Purpose

This document defines the data fields identified during the review of the 15 Weir River Water System monthly reports covering October 2024 through December 2025.

The data dictionary is intended to serve as the reference for:

- Database schema design
- PDF extraction
- Data validation
- Exploratory analysis
- Future automation

The monthly reports are published by the Town of Hingham and cover operational activity for the Weir River Water System.

---

## Source Reports

| Report Month | Status |
|---|---|
| October 2024 | Reviewed |
| November 2024 | Reviewed |
| December 2024 | Reviewed |
| January 2025 | Reviewed |
| February 2025 | Reviewed |
| March 2025 | Reviewed |
| April 2025 | Reviewed |
| May 2025 | Reviewed |
| June 2025 | Reviewed |
| July 2025 | Reviewed |
| August 2025 | Reviewed |
| September 2025 | Reviewed |
| October 2025 | Reviewed |
| November 2025 | Reviewed |
| December 2025 | Reviewed |

---

# Data Categories

## 1. Water Production

Water production is the primary dataset for the conservation analysis.

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `finished_water_mgd` | Mean of the current-year daily Finished Water MGD chart series | MGD | Monthly | Water Production | Validated chart extraction | High |
| `accord_pond_usage_mg` | Sum of the current-year daily Accord Pond Usage MG chart series | MG | Monthly | Water Production | Validated chart extraction | High |
| `accord_pond_level_ft` | Mean of the current-year daily Accord Pond Level chart series | ft | Monthly | Water Production | Validated chart extraction | High |

### Notes

Water production has been extracted, source-validated, and loaded for all 15
reports covering October 2024 through December 2025.

The extractor identifies each chart's current-year legend series and selects
the Y axis immediately above the corresponding chart legend. It retains daily
chart candidates for review, derives the monthly values using the mappings
above, and modifies SQLite only after all 15 reports pass validation. The final
table rebuild is transactional and records source-page provenance.

---

## 2. Precipitation

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `precipitation` | Total precipitation recorded during the reporting month | inches | Monthly | Precipitation | Text | High |
| `precipitation_comparison` | Reported comparison to normal/average precipitation | qualitative | Monthly | Precipitation | Text | Medium |

### Notes

Precipitation is explicitly reported in the monthly reports and appears suitable for automated text extraction.

This dataset will eventually allow investigation of relationships between precipitation and water production.

---

## 3. Chemical Usage

Chemical usage is reported as a monthly operational table.

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `sodium_hypochlorite` | Sodium hypochlorite used | gallons | Monthly | Chemical Use | Validated table extraction | Medium |
| `aluminum_sulfate` | Aluminum sulfate used | report-specific | Monthly | Chemical Use | Validated table extraction | Medium |
| `zinc_orthophosphate` | Zinc orthophosphate used | gallons | Monthly | Chemical Use | Validated table extraction | Medium |
| `hydrofluorosilic_acid` | Hydrofluorosilic acid used | gallons | Monthly | Chemical Use | Validated table extraction | Medium |
| `potassium_permanganate` | Potassium permanganate used | pounds | Monthly | Chemical Use | Validated table extraction | Medium |
| `calcium_hydroxide` | Calcium hydroxide used | tons | Monthly | Chemical Use | Validated table extraction | Medium |
| `gen_floc_610` | Gen Floc 610 used | pounds | Monthly | Chemical Use | Validated table extraction | Medium |
| `gen_floc_620` | Gen Floc 620 used | pounds | Monthly | Chemical Use | Validated table extraction | Medium |

### Notes

Chemical usage has been extracted, source-validated, and loaded for all 15
reports. The normalized database table stores one row per observation month and
chemical using `chemical_name`, `amount`, and `unit`.

The source table repeats historical months. The extractor cross-validates those
repeated values but loads only the current month from each report, preventing
duplicate observations. It validates all reports before transactionally
rebuilding the 120-row table. `Dies./gen.` is excluded because it is not a
chemical and its unit is not defined by the report.

---

# 4. Operations & Infrastructure

Operational activity is primarily reported as narrative bullet points containing quantitative counts.

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `main_breaks` | Water main breaks reported | count | Monthly | Operations Update | Text | High |
| `service_line_repairs` | Water service line repairs/replacements | count | Monthly | Operations Update | Text | High |
| `hydrant_replacements` | Hydrants replaced | count | Monthly | Operations Update | Text | Medium |
| `valve_replacements` | Valves replaced/repaired | count | Monthly | Operations Update | Text | Medium |
| `backflow_tests` | Backflow devices tested | count | Monthly | Operations Update | Text | Medium |
| `dig_safe_markouts` | Dig Safe mark-outs | count | Monthly | Operations Update | Text | Medium |

### Notes

The operations section contains additional activities that may vary from month to month. The fields above represent recurring or analytically useful measurements identified during report review.

Additional operational metrics may be added after extraction testing.

---

# 5. Meter Statistics

Metering data is one of the most potentially valuable conservation datasets.

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `meters_scheduled` | Meters scheduled for reading | count | Monthly | Meter Reading | Text | High |
| `actual_reads_pct` | Percentage of meters receiving actual reads | % | Monthly | Meter Reading | Text | High |
| `estimated_reads_pct` | Percentage of meters receiving estimated reads | % | Monthly | Meter Reading | Text | High |
| `meters_over_10_years_pct` | Percentage of meter fleet over 10 years old | % | Monthly | Meter Reading | Text | High |
| `meters_changed` | Total meters changed | count | Monthly | Meter Reading | Text | Medium |
| `new_meter_installations` | New meter installations | count | Monthly | Meter Reading | Text | Medium |
| `existing_meter_replacements` | Existing-premise meter replacements | count | Monthly | Meter Reading | Text | Medium |

### Notes

Meter statistics may provide useful context when investigating consumption measurement quality and system-wide conservation.

Estimated reads may be particularly important when evaluating data reliability.

---

# 6. Customer Service

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `customer_contacts` | Total calls received | count | Monthly | Customer Contact | Validated text extraction | Medium |
| `service_level_pct` | Reported customer-service level | % | Monthly | Customer Contact | Validated text extraction | Medium |
| `average_speed_seconds` | Average speed of answer, normalized to seconds | seconds | Monthly | Customer Contact | Validated text extraction | Medium |

### Notes

Customer service has been extracted, source-validated, and loaded for all 15
reports. The extractor verifies that the month named in the narrative matches
the report month, validates agent-offered calls against total calls, and
normalizes the reported minutes and seconds to `average_speed_seconds`.

---

# 7. Billing & Collections

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `revenue_billed_usd` | Revenue billed during reporting period | USD | Monthly | Customer Billing | Validated text/chart extraction | Low |
| `revenue_collected_usd` | Revenue collected during reporting period | USD | Monthly | Collections | Validated text extraction | Low |
| `aged_accounts_receivable_usd` | Total aged accounts receivable | USD | Monthly | Aged Accounts Receivable | Validated text extraction | Low |
| `accounts_receivable_90_plus_usd` | Accounts receivable 90+ days outstanding | USD | Monthly | Aged Accounts Receivable | Validated text/chart extraction | Low |

### Notes

Billing and collections has been extracted, source-validated, and loaded for all
15 reports. February 2025 billed revenue is the sum of the report's FIRE and
WATER service-chart values because its narrative repeats January. December 2024
90+ receivables is the sum of the Over-180 and 91–180 chart values because the
narrative uses ambiguous punctuation. March 2025 aged-receivables values are
`NULL`: both the narrative and chart stop at February.

---

# 8. Field Work Orders

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `field_work_orders` | Total field work orders/activities recorded | count | Monthly | Field Work Orders | Text | Medium |

### Notes

The reports provide additional categorization of field activities. These categories should be evaluated during extraction before determining whether they warrant separate database fields.

---

# 9. Maintenance Capital / CAP

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `maintenance_budget` | Maintenance capital budget | USD | Reporting period | Maintenance CAP | Table | Medium |
| `maintenance_expenditure` | Maintenance capital expenditure | USD | Monthly | Maintenance CAP | Table | Medium |
| `maintenance_cumulative_expenditure` | Cumulative expenditure | USD | Reporting period | Maintenance CAP | Table | Medium |
| `maintenance_remaining_budget` | Remaining budget | USD | Reporting period | Maintenance CAP | Table | Medium |

### Notes

Maintenance CAP data may eventually allow infrastructure spending to be compared against operational events and system performance.

---

# Extraction Classification

The reports contain three primary types of data.

## Text

Generally suitable for automated PDF text extraction.

Examples:

- Precipitation
- Meter statistics
- Main breaks
- Service repairs
- Work-order totals

## Tables

Generally suitable for structured table extraction.

Examples:

- Chemical usage
- Maintenance CAP
- Some financial data

## Charts

Require specialized extraction or reconstruction.

Examples:

- Finished Water
- Accord Pond Usage
- Accord Pond Level
- Some customer-service metrics
- Some meter/customer activity metrics

---

# Data Quality Considerations

## Historical Repetition

Some tables contain multiple historical months.

A report for a given month may therefore contain observations that originated in earlier reports.

The ingestion pipeline must prevent duplicate records.

## Chart-Based Measurements

Important production metrics are embedded in charts.

Chart extraction must be validated before being treated as authoritative numerical data.

## Changing Report Content

Although the overall report structure is highly consistent, individual operational activities and metrics may appear or disappear depending on the month.

The parser should therefore tolerate missing optional fields.

## Units

Units must be stored explicitly rather than inferred later.

Where a report-specific or ambiguous unit is encountered, the raw value should not be silently converted.

## Provenance

Every extracted observation should be traceable back to:

1. The source report
2. The report page/section
3. The extraction method
4. The original value

---

# Extraction Priority

The first seven priority datasets are complete and validated across all 15
reports:

1. **Water Production** — Complete
2. **Precipitation** — Complete
3. **Meter Statistics** — Complete
4. **Operational / Infrastructure Events** — Complete
5. **Chemical Usage** — Complete
6. **Customer Service** — Complete
7. **Billing and Collections** — Complete

The next extraction target is **Field Work Orders**. Maintenance data remains a
later target.

---

# Planned Analytical Questions

The extracted data should support investigation of:

- How does water production vary over time?
- Are there seasonal patterns in water production?
- How does precipitation relate to water production?
- How does Accord Pond usage relate to finished-water production?
- How does pond level change over time?
- Does chemical usage scale with water production?
- Are there trends in estimated versus actual meter reads?
- Does meter age correlate with estimated reads?
- Do infrastructure events coincide with changes in system production?
- Are there anomalous periods of unusually high or low production?

---

# Status

**Phase 3 — Data Extraction**

- [x] Identify official monthly report source
- [x] Identify 15 monthly reports
- [x] Review report structure
- [x] Identify recurring datasets
- [x] Identify extraction types
- [x] Identify initial analytical priorities
- [x] Extract and validate precipitation across all 15 reports
- [x] Extract and validate meter statistics across all 15 reports
- [x] Extract and validate operational events across all 15 reports
- [x] Extract and validate water production across all 15 reports
- [x] Validate current-year chart extraction and chart-specific Y-axis selection
- [x] Load validated water-production results transactionally
- [x] Extract and validate chemical usage across all 15 reports
- [x] Cross-validate repeated historical chemical-use values
- [x] Load validated chemical usage transactionally
- [x] Extract and validate customer service across all 15 reports
- [x] Normalize average speed of answer to seconds
- [x] Load validated customer service transactionally
- [x] Extract and validate billing and collections across all 15 reports
- [x] Preserve unreported March 2025 aged-receivables values as `NULL`
- [x] Load validated billing and collections transactionally
- [ ] Extract and validate field work orders
