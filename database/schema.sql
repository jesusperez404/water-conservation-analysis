-- Water Conservation Analysis
-- Database schema v2
--
-- Designed from the 15 monthly Weir River Water System reports
-- covering October 2024 through December 2025.
--
-- The schema prioritizes provenance, monthly observations, and
-- flexibility where report content varies between months.

PRAGMA foreign_keys = ON;

-- ============================================================
-- Source reports
-- ============================================================

CREATE TABLE IF NOT EXISTS reports (
    report_id INTEGER PRIMARY KEY,
    report_month DATE NOT NULL UNIQUE,
    source_url TEXT,
    file_path TEXT,
    downloaded_at TIMESTAMP,
    extraction_status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT
);

-- ============================================================
-- Water production
-- ============================================================

CREATE TABLE IF NOT EXISTS water_production (
    production_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL,
    finished_water_mgd REAL,
    accord_pond_usage_mg REAL,
    accord_pond_level_ft REAL,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id),
    UNIQUE (observation_month)
);

-- ============================================================
-- Precipitation
-- ============================================================

CREATE TABLE IF NOT EXISTS precipitation (
    precipitation_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL,
    precipitation_inches REAL,
    comparison_to_average TEXT,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id),
    UNIQUE (observation_month)
);

-- ============================================================
-- Chemical usage
-- ============================================================

CREATE TABLE IF NOT EXISTS chemical_usage (
    chemical_usage_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL,
    chemical_name TEXT NOT NULL,
    amount REAL,
    unit TEXT,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id),
    UNIQUE (observation_month, chemical_name)
);

-- ============================================================
-- Operations and infrastructure events
-- ============================================================

CREATE TABLE IF NOT EXISTS operational_events (
    event_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL,
    event_type TEXT NOT NULL,
    event_count INTEGER,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id),
    UNIQUE (observation_month, event_type)
);

-- ============================================================
-- Meter statistics
-- ============================================================

CREATE TABLE IF NOT EXISTS meter_statistics (
    meter_stat_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL UNIQUE,
    meters_scheduled INTEGER,
    actual_reads_pct REAL,
    estimated_reads_pct REAL,
    meters_over_10_years_pct REAL,
    meters_changed INTEGER,
    new_meter_installations INTEGER,
    existing_meter_replacements INTEGER,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id)
);

-- ============================================================
-- Customer service
-- ============================================================

CREATE TABLE IF NOT EXISTS customer_service (
    customer_service_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL UNIQUE,
    customer_contacts INTEGER,
    service_level_pct REAL,
    average_speed_seconds INTEGER,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id)
);

-- ============================================================
-- Billing and collections
-- ============================================================

CREATE TABLE IF NOT EXISTS billing_collections (
    billing_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL UNIQUE,
    revenue_billed_usd REAL,
    revenue_collected_usd REAL,
    aged_accounts_receivable_usd REAL,
    accounts_receivable_90_plus_usd REAL,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id)
);

-- ============================================================
-- Field work orders
-- ============================================================

CREATE TABLE IF NOT EXISTS field_work_orders (
    work_order_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL,
    work_order_type TEXT NOT NULL DEFAULT 'total',
    work_order_count INTEGER,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id),
    UNIQUE (observation_month, work_order_type)
);

-- ============================================================
-- Maintenance capital / CAP
-- ============================================================

CREATE TABLE IF NOT EXISTS maintenance_cap (
    maintenance_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    observation_month DATE NOT NULL,
    category TEXT,
    monthly_expenditure_usd REAL,
    cumulative_expenditure_usd REAL,
    annual_budget_usd REAL,
    remaining_budget_usd REAL,
    extraction_method TEXT,
    source_page INTEGER,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id),
    UNIQUE (observation_month, category)
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_reports_month
    ON reports(report_month);

CREATE INDEX IF NOT EXISTS idx_production_month
    ON water_production(observation_month);

CREATE INDEX IF NOT EXISTS idx_production_report
    ON water_production(report_id);

CREATE INDEX IF NOT EXISTS idx_precipitation_month
    ON precipitation(observation_month);

CREATE INDEX IF NOT EXISTS idx_chemical_month
    ON chemical_usage(observation_month);

CREATE INDEX IF NOT EXISTS idx_chemical_name
    ON chemical_usage(chemical_name);

CREATE INDEX IF NOT EXISTS idx_operations_month
    ON operational_events(observation_month);

CREATE INDEX IF NOT EXISTS idx_meter_month
    ON meter_statistics(observation_month);

CREATE INDEX IF NOT EXISTS idx_work_orders_month
    ON field_work_orders(observation_month);

CREATE INDEX IF NOT EXISTS idx_maintenance_month
    ON maintenance_cap(observation_month);

-- ============================================================
-- Analytical views
-- ============================================================

DROP VIEW IF EXISTS monthly_system_summary;
DROP VIEW IF EXISTS monthly_operations_summary;
DROP VIEW IF EXISTS monthly_dataset_coverage;

CREATE VIEW monthly_operations_summary AS
SELECT
    r.report_month AS observation_month,
    MAX(CASE WHEN o.event_type = 'main_breaks' THEN o.event_count END)
        AS main_breaks,
    MAX(CASE WHEN o.event_type = 'service_line_repairs' THEN o.event_count END)
        AS service_line_repairs,
    MAX(CASE WHEN o.event_type = 'hydrant_replacements' THEN o.event_count END)
        AS hydrant_replacements,
    MAX(CASE WHEN o.event_type = 'valve_replacements' THEN o.event_count END)
        AS valve_replacements,
    MAX(CASE WHEN o.event_type = 'backflow_tests' THEN o.event_count END)
        AS backflow_tests,
    MAX(CASE WHEN o.event_type = 'dig_safe_markouts' THEN o.event_count END)
        AS dig_safe_markouts,
    MAX(CASE WHEN o.event_type = 'surveys' THEN o.event_count END)
        AS surveys
FROM reports r
LEFT JOIN operational_events o
    ON o.report_id = r.report_id
GROUP BY r.report_id, r.report_month;

CREATE VIEW monthly_dataset_coverage AS
SELECT
    r.report_month AS observation_month,
    CASE WHEN p.report_id IS NOT NULL THEN 1 ELSE 0 END AS precipitation,
    CASE WHEN m.report_id IS NOT NULL THEN 1 ELSE 0 END AS meter_statistics,
    CASE WHEN o.report_id IS NOT NULL THEN 1 ELSE 0 END AS operational_events,
    CASE WHEN w.report_id IS NOT NULL THEN 1 ELSE 0 END AS water_production,
    CASE WHEN c.row_count = 8 THEN 1 ELSE 0 END AS chemical_usage,
    CASE WHEN cs.report_id IS NOT NULL THEN 1 ELSE 0 END AS customer_service,
    CASE WHEN b.report_id IS NOT NULL THEN 1 ELSE 0 END AS billing_collections,
    CASE WHEN f.row_count = 2 THEN 1 ELSE 0 END AS field_work_orders,
    CASE WHEN mc.report_id IS NOT NULL THEN 1 ELSE 0 END AS maintenance_cap
FROM reports r
LEFT JOIN precipitation p ON p.report_id = r.report_id
LEFT JOIN meter_statistics m ON m.report_id = r.report_id
LEFT JOIN (
    SELECT DISTINCT report_id FROM operational_events
) o ON o.report_id = r.report_id
LEFT JOIN water_production w ON w.report_id = r.report_id
LEFT JOIN (
    SELECT report_id, COUNT(*) AS row_count
    FROM chemical_usage
    GROUP BY report_id
) c ON c.report_id = r.report_id
LEFT JOIN customer_service cs ON cs.report_id = r.report_id
LEFT JOIN billing_collections b ON b.report_id = r.report_id
LEFT JOIN (
    SELECT report_id, COUNT(*) AS row_count
    FROM field_work_orders
    GROUP BY report_id
) f ON f.report_id = r.report_id
LEFT JOIN maintenance_cap mc ON mc.report_id = r.report_id;

CREATE VIEW monthly_system_summary AS
SELECT
    r.report_month AS observation_month,
    p.precipitation_inches,
    m.meters_scheduled,
    m.actual_reads_pct,
    m.estimated_reads_pct,
    m.meters_over_10_years_pct,
    m.meters_changed,
    m.new_meter_installations,
    m.existing_meter_replacements,
    w.finished_water_mgd,
    w.accord_pond_usage_mg,
    w.accord_pond_level_ft,
    ops.main_breaks,
    ops.service_line_repairs,
    ops.hydrant_replacements,
    ops.valve_replacements,
    ops.backflow_tests,
    ops.dig_safe_markouts,
    ops.surveys,
    cs.customer_contacts,
    cs.service_level_pct,
    cs.average_speed_seconds,
    b.revenue_billed_usd,
    b.revenue_collected_usd,
    b.aged_accounts_receivable_usd,
    b.accounts_receivable_90_plus_usd,
    MAX(CASE WHEN f.work_order_type = 'total' THEN f.work_order_count END)
        AS total_work_orders,
    MAX(CASE WHEN f.work_order_type = 'collection_posting' THEN f.work_order_count END)
        AS collection_posting_work_orders,
    mc.monthly_expenditure_usd AS maintenance_paid_usd,
    mc.cumulative_expenditure_usd AS maintenance_cumulative_usd,
    mc.annual_budget_usd AS maintenance_annual_budget_usd,
    mc.remaining_budget_usd AS maintenance_remaining_budget_usd
FROM reports r
LEFT JOIN precipitation p ON p.report_id = r.report_id
LEFT JOIN meter_statistics m ON m.report_id = r.report_id
LEFT JOIN water_production w ON w.report_id = r.report_id
LEFT JOIN monthly_operations_summary ops
    ON ops.observation_month = r.report_month
LEFT JOIN customer_service cs ON cs.report_id = r.report_id
LEFT JOIN billing_collections b ON b.report_id = r.report_id
LEFT JOIN field_work_orders f ON f.report_id = r.report_id
LEFT JOIN maintenance_cap mc ON mc.report_id = r.report_id
GROUP BY r.report_id, r.report_month;
