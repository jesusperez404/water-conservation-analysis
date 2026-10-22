from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.apply_schema import apply_schema


DATABASE_PATH = Path("database/water.db").resolve()
SCHEMA_PATH = Path("database/schema.sql").resolve()

EXPECTED_COUNTS = {
    "reports": 15,
    "precipitation": 15,
    "meter_statistics": 15,
    "operational_events": 81,
    "water_production": 15,
    "chemical_usage": 120,
    "customer_service": 15,
    "billing_collections": 15,
    "field_work_orders": 30,
    "maintenance_cap": 15,
}

OBSERVATION_TABLES = tuple(EXPECTED_COUNTS)[1:]


class DatabaseIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.conn = sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.close()

    def test_sqlite_and_foreign_key_integrity(self) -> None:
        self.assertEqual(self.conn.execute("PRAGMA quick_check").fetchone()[0], "ok")
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_validated_table_counts(self) -> None:
        actual = {
            table: self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in EXPECTED_COUNTS
        }
        self.assertEqual(actual, EXPECTED_COUNTS)

    def test_observation_months_match_source_reports(self) -> None:
        for table in OBSERVATION_TABLES:
            with self.subTest(table=table):
                mismatch_count = self.conn.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {table} data
                    JOIN reports r ON r.report_id = data.report_id
                    WHERE data.observation_month != r.report_month
                    """
                ).fetchone()[0]
                self.assertEqual(mismatch_count, 0)

    def test_monthly_dataset_coverage_is_complete(self) -> None:
        rows = self.conn.execute(
            "SELECT * FROM monthly_dataset_coverage ORDER BY observation_month"
        ).fetchall()
        self.assertEqual(len(rows), 15)
        self.assertTrue(all(sum(row[1:]) == 9 for row in rows))

    def test_monthly_system_summary_has_one_row_per_month(self) -> None:
        rows = self.conn.execute(
            """
            SELECT observation_month, finished_water_mgd, maintenance_paid_usd
            FROM monthly_system_summary
            ORDER BY observation_month
            """
        ).fetchall()
        self.assertEqual(len(rows), 15)
        self.assertEqual(rows[0][0], "2024-10-01")
        self.assertEqual(rows[-1][0], "2025-12-01")
        self.assertTrue(all(row[1] > 0 and row[2] >= 0 for row in rows))

    def test_domain_and_reconciliation_invariants(self) -> None:
        self.assertEqual(
            self.conn.execute(
                """
                SELECT COUNT(*) FROM meter_statistics
                WHERE actual_reads_pct NOT BETWEEN 0 AND 100
                   OR estimated_reads_pct NOT BETWEEN 0 AND 100
                   OR ABS(actual_reads_pct + estimated_reads_pct - 100) > 0.01
                """
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                """
                SELECT COUNT(*) FROM maintenance_cap
                WHERE ABS(
                    annual_budget_usd
                    - cumulative_expenditure_usd
                    - remaining_budget_usd
                ) > 0.02
                """
            ).fetchone()[0],
            0,
        )

    def test_schema_builds_views_on_a_new_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.db"
            apply_schema(database_path, SCHEMA_PATH)
            conn = sqlite3.connect(database_path)
            try:
                views = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'view'"
                    )
                }
            finally:
                conn.close()
        self.assertEqual(
            views,
            {
                "monthly_dataset_coverage",
                "monthly_operations_summary",
                "monthly_system_summary",
            },
        )


if __name__ == "__main__":
    unittest.main()
