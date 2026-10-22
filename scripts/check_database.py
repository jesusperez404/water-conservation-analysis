import sqlite3
from pathlib import Path


DB_PATH = Path("database/water.db")


TABLES = [
    "reports",
    "precipitation",
    "meter_statistics",
    "operational_events",
    "water_production",
    "chemical_usage",
    "customer_service",
    "billing_collections",
]


def main():
    conn = sqlite3.connect(DB_PATH)

    try:
        print("DATABASE INTEGRITY CHECK")
        print("=" * 72)

        print("\nTABLE COUNTS")
        print("-" * 72)

        for table in TABLES:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table}: {count}")

        print("\nOPERATION EVENT COUNTS")
        print("-" * 72)

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
        print("-" * 72)

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
                END AS operations,

                CASE
                    WHEN w.report_id IS NOT NULL
                    THEN 'YES'
                    ELSE 'NO'
                END AS water_production,

                CASE
                    WHEN c.chemical_count = 8
                    THEN 'YES'
                    ELSE 'NO'
                END AS chemical_usage,

                CASE
                    WHEN cs.report_id IS NOT NULL
                    THEN 'YES'
                    ELSE 'NO'
                END AS customer_service,

                CASE
                    WHEN b.report_id IS NOT NULL
                    THEN 'YES'
                    ELSE 'NO'
                END AS billing_collections

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

            LEFT JOIN water_production w
                ON w.report_id = r.report_id

            LEFT JOIN (
                SELECT report_id, COUNT(*) AS chemical_count
                FROM chemical_usage
                GROUP BY report_id
            ) c
                ON c.report_id = r.report_id

            LEFT JOIN customer_service cs
                ON cs.report_id = r.report_id

            LEFT JOIN billing_collections b
                ON b.report_id = r.report_id

            ORDER BY r.report_month
            """
        ).fetchall()

        coverage_failures = 0

        for (
            month,
            precipitation,
            meter,
            operations,
            water_production,
            chemical_usage,
            customer_service,
            billing_collections,
        ) in rows:
            print(
                f"{month}  "
                f"precipitation={precipitation}  "
                f"meter={meter}  "
                f"operations={operations}  "
                f"water_production={water_production}  "
                f"chemical_usage={chemical_usage}  "
                f"customer_service={customer_service}  "
                f"billing={billing_collections}"
            )

            if "NO" in (
                precipitation,
                meter,
                operations,
                water_production,
                chemical_usage,
                customer_service,
                billing_collections,
            ):
                coverage_failures += 1

        print("\nCHEMICAL USAGE CHECKS")
        print("-" * 72)

        chemical_rows = conn.execute(
            """
            SELECT
                observation_month,
                COUNT(*) AS row_count,
                COUNT(DISTINCT chemical_name) AS chemical_count,
                SUM(CASE WHEN amount IS NULL OR amount < 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN unit IS NULL OR TRIM(unit) = '' THEN 1 ELSE 0 END)
            FROM chemical_usage
            GROUP BY observation_month
            ORDER BY observation_month
            """
        ).fetchall()

        chemical_failures = 0
        for month, row_count, chemical_count, bad_amounts, bad_units in chemical_rows:
            issues = []
            if row_count != 8 or chemical_count != 8:
                issues.append(f"coverage={row_count}/{chemical_count}")
            if bad_amounts:
                issues.append(f"bad_amounts={bad_amounts}")
            if bad_units:
                issues.append(f"bad_units={bad_units}")
            if issues:
                chemical_failures += 1
            print(f"{month}  {'PASS' if not issues else 'FAIL: ' + ', '.join(issues)}")

        print("\nBILLING AND COLLECTIONS CHECKS")
        print("-" * 72)

        billing_rows = conn.execute(
            """
            SELECT
                observation_month,
                revenue_billed_usd,
                revenue_collected_usd,
                aged_accounts_receivable_usd,
                accounts_receivable_90_plus_usd
            FROM billing_collections
            ORDER BY observation_month
            """
        ).fetchall()

        billing_failures = 0
        for month, billed, collected, aged_ar, ar_90_plus in billing_rows:
            issues = []
            if billed is None or billed < 0:
                issues.append("revenue_billed")
            if collected is None or collected < 0:
                issues.append("revenue_collected")
            if month == "2025-03-01":
                if aged_ar is not None or ar_90_plus is not None:
                    issues.append("expected_missing_ar")
            elif aged_ar is None or ar_90_plus is None:
                issues.append("missing_ar")
            elif aged_ar < 0 or ar_90_plus < 0 or ar_90_plus > aged_ar:
                issues.append("invalid_ar")
            if issues:
                billing_failures += 1
            print(f"{month}  {'PASS' if not issues else 'FAIL: ' + ', '.join(issues)}")

        print("\nCUSTOMER SERVICE CHECKS")
        print("-" * 72)

        service_rows = conn.execute(
            """
            SELECT
                observation_month,
                customer_contacts,
                service_level_pct,
                average_speed_seconds
            FROM customer_service
            ORDER BY observation_month
            """
        ).fetchall()

        service_failures = 0
        for month, contacts, service_level, answer_seconds in service_rows:
            issues = []
            if contacts is None or contacts <= 0:
                issues.append("customer_contacts")
            if service_level is None or not 0 <= service_level <= 100:
                issues.append("service_level")
            if answer_seconds is None or answer_seconds < 0:
                issues.append("average_speed")
            if issues:
                service_failures += 1
            print(f"{month}  {'PASS' if not issues else 'FAIL: ' + ', '.join(issues)}")

        print("\nWATER PRODUCTION RANGE CHECKS")
        print("-" * 72)

        water_rows = conn.execute(
            """
            SELECT
                observation_month,
                finished_water_mgd,
                accord_pond_usage_mg,
                accord_pond_level_ft
            FROM water_production
            ORDER BY observation_month
            """
        ).fetchall()

        range_failures = 0

        for (
            month,
            finished_water,
            pond_usage,
            pond_level,
        ) in water_rows:
            issues = []

            if finished_water is None or finished_water <= 0:
                issues.append("finished_water")

            if pond_usage is None or pond_usage < 0:
                issues.append("pond_usage")

            if pond_level is None or not 120 <= pond_level <= 150:
                issues.append("pond_level")

            status = "PASS" if not issues else (
                "FAIL: " + ", ".join(issues)
            )

            if issues:
                range_failures += 1

            print(
                f"{month}  "
                f"finished={finished_water}  "
                f"pond_usage={pond_usage}  "
                f"pond_level={pond_level}  "
                f"{status}"
            )

        print("\nSUMMARY")
        print("-" * 72)

        if (
            coverage_failures == 0
            and range_failures == 0
            and chemical_failures == 0
            and service_failures == 0
            and billing_failures == 0
        ):
            print("PASS: database coverage and dataset sanity checks passed.")
        else:
            print(
                "FAIL: "
                f"{coverage_failures} coverage failure(s), "
                f"{range_failures} water-production range failure(s), "
                f"{chemical_failures} chemical-usage failure(s), "
                f"{service_failures} customer-service failure(s), "
                f"{billing_failures} billing failure(s)."
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
