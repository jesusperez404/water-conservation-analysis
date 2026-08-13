import re
import sqlite3
from pathlib import Path

import pymupdf


DB_PATH = Path("database/water.db")


def extract_meter_statistics(pdf_path):
    doc = pymupdf.open(pdf_path)

    for page_number, page in enumerate(doc):
        text = page.get_text()

        scheduled_match = re.search(
            r"there were\s+([\d,]+)\s+meters scheduled.*?"
            r"(\d+(?:\.\d+)?)%\s+of actual reads.*?"
            r"(\d+(?:\.\d+)?)%\s+of estimated reads",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if not scheduled_match:
            continue

        meters_scheduled = int(
            scheduled_match.group(1).replace(",", "")
        )
        actual_reads_pct = float(scheduled_match.group(2))
        estimated_reads_pct = float(scheduled_match.group(3))

        # Meter age / installation information is normally on the
        # following page.
        following_text = ""

        if page_number + 1 < len(doc):
            following_text = doc[page_number + 1].get_text()

        combined_text = text + "\n" + following_text

        meters_over_10_years_pct = None
        match = re.search(
            r"meters over ten years of age.*?"
            r"(\d+(?:\.\d+)?)%\s+of the entire meter fleet",
            combined_text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:
            meters_over_10_years_pct = float(match.group(1))

        meters_changed = None
        match = re.search(
            r"account for\s+(\d+)\s+meters changed",
            combined_text,
            re.IGNORECASE,
        )

        if match:
            meters_changed = int(match.group(1))

        new_meter_installations = None
        match = re.search(
            r"We had\s+(\d+)\s+meters?\s+for new installations",
            combined_text,
            re.IGNORECASE,
        )

        if match:
            new_meter_installations = int(match.group(1))

        existing_meter_replacements = None
        match = re.search(
            r"and\s+(\d+)\s+for existing premises",
            combined_text,
            re.IGNORECASE,
        )

        if match:
            existing_meter_replacements = int(match.group(1))

        doc.close()

        return {
            "meters_scheduled": meters_scheduled,
            "actual_reads_pct": actual_reads_pct,
            "estimated_reads_pct": estimated_reads_pct,
            "meters_over_10_years_pct": meters_over_10_years_pct,
            "meters_changed": meters_changed,
            "new_meter_installations": new_meter_installations,
            "existing_meter_replacements": existing_meter_replacements,
            "source_page": page_number + 1,
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

        result = extract_meter_statistics(file_path)

        if result is None:
            print("  WARNING: meter statistics not found")
            continue

        conn.execute(
            """
            INSERT OR REPLACE INTO meter_statistics (
                report_id,
                observation_month,
                meters_scheduled,
                actual_reads_pct,
                estimated_reads_pct,
                meters_over_10_years_pct,
                meters_changed,
                new_meter_installations,
                existing_meter_replacements,
                extraction_method,
                source_page
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                report_month,
                result["meters_scheduled"],
                result["actual_reads_pct"],
                result["estimated_reads_pct"],
                result["meters_over_10_years_pct"],
                result["meters_changed"],
                result["new_meter_installations"],
                result["existing_meter_replacements"],
                result["extraction_method"],
                result["source_page"],
            ),
        )

        extracted += 1

        print(
            f"  Scheduled: {result['meters_scheduled']:,}, "
            f"Actual: {result['actual_reads_pct']}%, "
            f"Estimated: {result['estimated_reads_pct']}%, "
            f"Over 10 years: {result['meters_over_10_years_pct']}%, "
            f"Changed: {result['meters_changed']}, "
            f"New: {result['new_meter_installations']}, "
            f"Existing: {result['existing_meter_replacements']}"
        )

    conn.commit()

    print(f"\nExtracted {extracted} meter records.")

    conn.close()


if __name__ == "__main__":
    main()