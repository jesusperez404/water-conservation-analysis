import re
import sqlite3
from pathlib import Path

import pymupdf


DB_PATH = Path("database/water.db")
PDF_DIR = Path("data/raw")


def extract_precipitation(pdf_path):
    doc = pymupdf.open(pdf_path)

    for page_number, page in enumerate(doc, start=1):
        text = page.get_text()

        if "3 PRECIPITATION" not in text:
            continue

        match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s+inches\s+during the month",
            text,
            re.IGNORECASE,
        )

        if match:
            precipitation = float(match.group(1))

            comparison = None
            comparison_match = re.search(
                r"Rain fall amounts were\s+(.+?)\s+with",
                text,
                re.IGNORECASE,
            )

            if comparison_match:
                comparison = comparison_match.group(1).strip()

            doc.close()

            return {
                "precipitation_inches": precipitation,
                "comparison_to_average": comparison,
                "source_page": page_number,
                "extraction_method": "regex_text",
            }

    doc.close()
    return None


def main():
    conn = sqlite3.connect(DB_PATH)

    reports = conn.execute(
        """
        SELECT report_id, report_month, file_path
        FROM reports
        ORDER BY report_month
        """
    ).fetchall()

    extracted = 0

    for report_id, report_month, file_path in reports:
        print(f"Processing {report_month}...")

        result = extract_precipitation(file_path)

        if result is None:
            print("  WARNING: precipitation not found")
            continue

        conn.execute(
            """
            INSERT OR REPLACE INTO precipitation (
                report_id,
                observation_month,
                precipitation_inches,
                comparison_to_average,
                extraction_method,
                source_page
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                report_month,
                result["precipitation_inches"],
                result["comparison_to_average"],
                result["extraction_method"],
                result["source_page"],
            ),
        )

        extracted += 1

        print(
            f"  {result['precipitation_inches']} inches "
            f"({result['comparison_to_average']})"
        )

    conn.commit()

    print(f"\nExtracted {extracted} precipitation records.")

    conn.close()


if __name__ == "__main__":
    main()
