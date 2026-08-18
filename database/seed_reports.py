import sqlite3

REPORTS = [
    ("2024-10-01", "https://www.hingham-ma.gov/DocumentCenter/View/23262/October-2024-Monthly-Report"),
    ("2024-11-01", "https://www.hingham-ma.gov/DocumentCenter/View/23264/November-2024-Monthly-Report"),
    ("2024-12-01", "https://www.hingham-ma.gov/DocumentCenter/View/23263/December-2024-Monthly-Report"),
    ("2025-01-01", "https://www.hingham-ma.gov/DocumentCenter/View/23851/January-2025-Monthly-Report"),
    ("2025-02-01", "https://www.hingham-ma.gov/DocumentCenter/View/23852/February-2025-Monthly-Report"),
    ("2025-03-01", "https://www.hingham-ma.gov/DocumentCenter/View/25925/March-2025-Monthly-Report"),
    ("2025-04-01", "https://www.hingham-ma.gov/DocumentCenter/View/25924/April-2025-Monthly-Report"),
    ("2025-05-01", "https://www.hingham-ma.gov/DocumentCenter/View/25927/May-2025-Monthly-Report"),
    ("2025-06-01", "https://www.hingham-ma.gov/DocumentCenter/View/25926/June-2025-Monthly-Report"),
    ("2025-07-01", "https://hingham-ma.gov/DocumentCenter/View/26946/July-2025-Monthly-Report"),
    ("2025-08-01", "https://www.hingham-ma.gov/DocumentCenter/View/26945/August-2025-Monthly-Report"),
    ("2025-09-01", "https://www.hingham-ma.gov/DocumentCenter/View/26948/September-2025-Monthly-Report"),
    ("2025-10-01", "https://www.hingham-ma.gov/DocumentCenter/View/26947/October-2025-Monthly-Report"),
    ("2025-11-01", "https://www.hingham-ma.gov/DocumentCenter/View/27402/November-2025-Monthly-Report"),
    ("2025-12-01", "https://www.hingham-ma.gov/DocumentCenter/View/27403/December-2025-Monthly-Report"),
]


def main():
    conn = sqlite3.connect("database/water.db")

    conn.executemany(
        """
        INSERT OR IGNORE INTO reports (
            report_month,
            source_url,
            extraction_status
        )
        VALUES (?, ?, 'pending')
        """,
        REPORTS,
    )

    conn.commit()

    rows = conn.execute(
        """
        SELECT report_id, report_month, extraction_status
        FROM reports
        ORDER BY report_month
        """
    ).fetchall()

    print(f"Reports in database: {len(rows)}")

    for row in rows:
        print(row)

    conn.close()


if __name__ == "__main__":
    main()