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