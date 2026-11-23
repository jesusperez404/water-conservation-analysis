from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path

import pymupdf


RAW_DIR = Path("data/raw")
DB_PATH = Path("database/water.db")
OUTPUT_DIR = Path("data/processed/field_work_orders_review")
CANDIDATE_CSV = OUTPUT_DIR / "field_work_order_candidates.csv"
EXPECTED_REPORTS = 15
EXPECTED_TYPES = {"total", "collection_posting"}

MONTHS = {
    name.lower(): index
    for index, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        1,
    )
}

WORK_ORDER_PATTERN = re.compile(
    r"There were\s+([\d,]+)\s+recorded work orders issued for the month of\s+"
    r"([A-Za-z]+)\s+(20\d{2}).*?"
    r"Collection process for non-\s*payment also created\s+([\d,]+)\s+"
    r"field activities for posting",
    re.IGNORECASE | re.DOTALL,
)


def report_month(path: Path) -> str:
    match = re.search(r"(\d{4})-(\d{2})", path.stem)
    if not match:
        raise ValueError(f"Could not determine report month from {path.name}")
    return f"{match.group(1)}-{match.group(2)}-01"


def extract_report(path: Path) -> list[dict]:
    matches = []
    with pymupdf.open(path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = " ".join(page.get_text("text").split())
            match = WORK_ORDER_PATTERN.search(text)
            if match:
                matches.append((page_number, match))
    if len(matches) != 1:
        raise ValueError(f"Expected one work-order narrative, found {len(matches)}")

    page_number, match = matches[0]
    month_name = match.group(2).lower()
    if month_name not in MONTHS:
        raise ValueError(f"Unknown narrative month: {match.group(2)}")
    narrative_month = f"{int(match.group(3)):04d}-{MONTHS[month_name]:02d}-01"
    expected_month = report_month(path)
    if narrative_month != expected_month:
        raise ValueError(
            f"Narrative month {narrative_month} does not match {expected_month}"
        )

    total = int(match.group(1).replace(",", ""))
    collection_posting = int(match.group(4).replace(",", ""))
    if total < 0 or collection_posting < 0:
        raise ValueError("Work-order counts must be nonnegative")
    if collection_posting > total:
        raise ValueError("Collection-posting activities exceed total work orders")

    return [
        {
            "report_month": expected_month,
            "observation_month": expected_month,
            "work_order_type": "total",
            "work_order_count": total,
            "source_page": page_number,
        },
        {
            "report_month": expected_month,
            "observation_month": expected_month,
            "work_order_type": "collection_posting",
            "work_order_count": collection_posting,
            "source_page": page_number,
        },
    ]


def validate_candidates(rows: list[dict]) -> None:
    expected_rows = EXPECTED_REPORTS * len(EXPECTED_TYPES)
    if len(rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows, got {len(rows)}")
    by_month = {}
    for row in rows:
        by_month.setdefault(row["observation_month"], set()).add(
            row["work_order_type"]
        )
    if len(by_month) != EXPECTED_REPORTS:
        raise ValueError(f"Expected {EXPECTED_REPORTS} distinct months")
    invalid = {
        month: types for month, types in by_month.items() if types != EXPECTED_TYPES
    }
    if invalid:
        raise ValueError(f"Invalid work-order type coverage: {invalid}")


def write_candidates(rows: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CANDIDATE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_database(rows: list[dict]) -> int:
    validate_candidates(rows)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        report_ids = {
            str(month): report_id
            for report_id, month in conn.execute(
                "SELECT report_id, report_month FROM reports"
            )
        }
        missing = sorted({row["report_month"] for row in rows} - set(report_ids))
        if missing:
            raise ValueError("Missing report records for: " + ", ".join(missing))

        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM field_work_orders")
        conn.executemany(
            """
            INSERT INTO field_work_orders (
                report_id,
                observation_month,
                work_order_type,
                work_order_count,
                extraction_method,
                source_page,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    report_ids[row["report_month"]],
                    row["observation_month"],
                    row["work_order_type"],
                    row["work_order_count"],
                    "regex_text",
                    row["source_page"],
                    "Reported monthly Field Work Orders narrative value.",
                )
                for row in rows
            ],
        )
        count = conn.execute("SELECT COUNT(*) FROM field_work_orders").fetchone()[0]
        invalid = conn.execute(
            """
            SELECT observation_month, COUNT(*), COUNT(DISTINCT work_order_type)
            FROM field_work_orders
            GROUP BY observation_month
            HAVING COUNT(*) != 2 OR COUNT(DISTINCT work_order_type) != 2
            """
        ).fetchall()
        if count != EXPECTED_REPORTS * 2 or invalid:
            raise ValueError(
                f"Post-load validation found {count} rows; invalid months: {invalid}"
            )
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-db", action="store_true")
    args = parser.parse_args()

    pdfs = sorted(RAW_DIR.glob("weir_river_*.pdf"))
    print("FIELD WORK ORDERS EXTRACTION")
    print("=" * 72)
    print(f"Reports found: {len(pdfs)}")
    print(f"Database write mode: {'ON' if args.write_db else 'OFF'}")
    if len(pdfs) != EXPECTED_REPORTS:
        raise SystemExit(
            f"Expected {EXPECTED_REPORTS} PDFs, found {len(pdfs)}. "
            "SQLite was NOT modified."
        )

    rows = []
    failures = []
    for path in pdfs:
        month = report_month(path)
        try:
            report_rows = extract_report(path)
            rows.extend(report_rows)
            counts = {row["work_order_type"]: row["work_order_count"] for row in report_rows}
            print(
                f"{month}  total={counts['total']}  "
                f"collection_posting={counts['collection_posting']}  PASS"
            )
        except Exception as exc:
            failures.append((month, str(exc)))
            print(f"{month}  FAIL: {exc}")

    if failures:
        print("\nVALIDATION FAILURES")
        for month, message in failures:
            print(f"  {month}: {message}")
        raise SystemExit("SQLite was NOT modified.")

    try:
        validate_candidates(rows)
    except Exception as exc:
        raise SystemExit(f"Validation failed: {exc}\nSQLite was NOT modified.")

    write_candidates(rows)
    print("\nVALIDATION SUMMARY")
    print("=" * 72)
    print(f"Reports passed: {len(rows) // 2}/{EXPECTED_REPORTS}")
    print(f"Candidate rows: {len(rows)}")
    print(f"Candidate CSV: {CANDIDATE_CSV}")

    if args.write_db:
        loaded = load_database(rows)
        print(f"Database load complete: {loaded} field_work_orders rows")
    else:
        print("SQLite was NOT modified. Review candidates before --write-db.")


if __name__ == "__main__":
    main()
