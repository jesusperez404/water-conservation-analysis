-- Water Conservation Analysis
-- Initial database schema
--
-- This is a v1 schema. It is intentionally small and will evolve
-- as the source reports are inspected during Phase 2.

PRAGMA foreign_keys = ON;

-- Source documents used by the project.
CREATE TABLE IF NOT EXISTS reports (
    report_id INTEGER PRIMARY KEY,
    report_date DATE NOT NULL,
    source_url TEXT,
    file_path TEXT,
    downloaded_at TIMESTAMP,
    extraction_status TEXT DEFAULT 'pending',
    notes TEXT
);

-- Water production measurements extracted from reports.
CREATE TABLE IF NOT EXISTS water_production (
    production_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    production_date DATE NOT NULL,
    water_produced REAL NOT NULL,
    unit TEXT NOT NULL DEFAULT 'gallons',
    source_system TEXT,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id)
);

-- Water quality measurements, if reported by the source documents.
CREATE TABLE IF NOT EXISTS water_quality (
    quality_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    measurement_date DATE NOT NULL,
    parameter TEXT NOT NULL,
    value REAL,
    unit TEXT,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES reports(report_id)
);

-- Useful indexes for common time-series queries.
CREATE INDEX IF NOT EXISTS idx_reports_date
    ON reports(report_date);

CREATE INDEX IF NOT EXISTS idx_production_date
    ON water_production(production_date);

CREATE INDEX IF NOT EXISTS idx_production_report
    ON water_production(report_id);

CREATE INDEX IF NOT EXISTS idx_quality_date
    ON water_quality(measurement_date);

CREATE INDEX IF NOT EXISTS idx_quality_report
    ON water_quality(report_id);