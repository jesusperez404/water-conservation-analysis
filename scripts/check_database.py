import sqlite3
from pathlib import Path


DB_PATH = Path("database/water.db")


TABLES = [
    "reports",
    "precipitation",
    "meter_statistics",
    "operational_events",
]


conn = sqlite3.connect(DB_PATH)

try:
    print("DATABASE INTEGRITY CHECK")
    print("=" * 60)

    print("\nTABLE COUNTS")
    print("-" * 60)

    for table in TABLES:
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"{table}: {count}")

    print("\nOPERATION EVENT COUNTS")
    print("-" * 60)

    rows = conn.execute(
        """
        SELECT event_type, COUNT(*)
        FROM operational_events
        GROUP BY event_type
        ORDER BY event_type
        """
    ).fetchall()

    for event_type, count in rows:
        print(f"{event_type}: {count} rows")

    print("\nMONTH COVERAGE")
    print("-" * 60)

    rows = conn.execute(
        """
        SELECT
            r.report_month,

            CASE
                WHEN p.report_id IS NOT NULL
                THEN 'YES'
                ELSE 'NO'
            END AS precipitation,

            CASE
                WHEN m.report_id IS NOT NULL
                THEN 'YES'
                ELSE 'NO'
            END AS meter_statistics,

            CASE
                WHEN o.report_id IS NOT NULL
                THEN 'YES'
                ELSE 'NO'
            END AS operations

        FROM reports r

        LEFT JOIN precipitation p
            ON p.report_id = r.report_id

        LEFT JOIN meter_statistics m
            ON m.report_id = r.report_id

        LEFT JOIN (
            SELECT DISTINCT report_id
            FROM operational_events
        ) o
            ON o.report_id = r.report_id

        ORDER BY r.report_month
        """
    ).fetchall()

    for month, precipitation, meter, operations in rows:
        print(
            f"{month}  "
            f"precipitation={precipitation}  "
            f"meter={meter}  "
            f"operations={operations}"
        )

finally:
    conn.close()