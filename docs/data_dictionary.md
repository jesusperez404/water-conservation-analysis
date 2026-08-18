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
| `finished_water` | Finished water produced by the system | MGD | Monthly | Water Production | Chart | High |
| `accord_pond_usage` | Water usage from Accord Pond | MG | Monthly | Water Production | Chart | High |
| `accord_pond_level` | Accord Pond water level | ft | Monthly | Water Production | Chart | High |

### Notes

The production values are presented primarily as charts rather than conventional tables. The underlying values will need to be extracted and validated before they can be loaded into the database.

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
| `sodium_hypochlorite` | Sodium hypochlorite used | gallons | Monthly | Chemical Use | Table | Medium |
| `aluminum_sulfate` | Aluminum sulfate used | report-specific | Monthly | Chemical Use | Table | Medium |
| `zinc_orthophosphate` | Zinc orthophosphate used | gallons | Monthly | Chemical Use | Table | Medium |
| `hydrofluosilicic_acid` | Hydrofluosilicic acid used | gallons | Monthly | Chemical Use | Table | Medium |
| `potassium_permanganate` | Potassium permanganate used | pounds | Monthly | Chemical Use | Table | Medium |
| `calcium_hydroxide` | Calcium hydroxide used | tons | Monthly | Chemical Use | Table | Medium |
| `gen_floc_610` | Gen Floc 610 used | pounds | Monthly | Chemical Use | Table | Medium |
| `gen_floc_620` | Gen Floc 620 used | pounds | Monthly | Chemical Use | Table | Medium |

### Notes

The chemical-use table contains historical months in addition to the current reporting month.

The ingestion process must avoid creating duplicate observations when the same month appears in multiple reports.

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
| `customer_contacts` | Customer contacts handled | count | Monthly | Customer Service | Text/Chart | Medium |
| `service_level` | Customer-service performance metric | % / report-specific | Monthly | Customer Service | Text/Chart | Medium |

### Notes

Customer-service measurements are useful for understanding system activity but are secondary to the core conservation analysis.

---

# 7. Billing & Collections

| Field | Description | Unit | Frequency | Source | Extraction | Priority |
|---|---|---|---|---|---|---|
| `revenue_billed` | Revenue billed during reporting period | USD | Monthly | Customer Billing | Text/Chart | Low |
| `revenue_collected` | Revenue collected during reporting period | USD | Monthly | Collections | USD | Low |
| `aged_accounts_receivable` | Total aged accounts receivable | USD | Monthly | Aged Accounts Receivable | Text/Chart | Low |
| `accounts_receivable_90_plus` | Accounts receivable 90+ days outstanding | USD | Monthly | Aged Accounts Receivable | Text/Chart | Low |

### Notes

Financial information is included for operational context but is not currently a primary conservation-analysis dataset.

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

# Initial Priority

The first datasets to implement should be:

1. **Water Production**
2. **Precipitation**
3. **Meter Statistics**
4. **Operational / Infrastructure Events**
5. **Chemical Usage**

Financial and customer-service datasets can be added afterward.

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

**Phase 2 — Report Analysis**

- [x] Identify official monthly report source
- [x] Identify 15 monthly reports
- [x] Review report structure
- [x] Identify recurring datasets
- [x] Identify extraction types
- [x] Identify initial analytical priorities
- [ ] Validate chart extraction
- [ ] Validate fields against all 15 reports programmatically
- [ ] Finalize database schema
- [ ] Build automated ingestion pipeline