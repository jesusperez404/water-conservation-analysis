from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path

import pymupdf


RAW_DIR = Path("data/raw")
DB_PATH = Path("database/water.db")
OUTPUT_DIR = Path("data/processed/customer_service_review")
CANDIDATE_CSV = OUTPUT_DIR / "customer_service_candidates.csv"
EXPECTED_REPORTS = 15

MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        start=1,
    )
}

CONTACT_PATTERN = re.compile(
    r"Customer service received a total of\s+([\d,]+)\s+calls\s+"
    r"for the month of\s+([A-Za-z]+)\s+(20\d{2})\.\s+"
    r"Of the total number of calls received\s+([\d,]+)\s+were offered\s+"
    r"to customer service agents.*?"
    r"level of service obtained for this month was\s+([\d.]+)%\s+"
    r"with an average speed of answer of\s+(\d+)\s+Minutes?"
    r"(?:\s+(?:and\s+)?(\d+)\s+Seconds?)?",
    re.IGNORECASE | re.DOTALL,
)


def report_month(path: Path) -> str:
    match = re.search(r"(\d{4})-(\d{2})", path.stem)
    if not match:
        raise ValueError(f"Could not determine report month from {path.name}")
    return f"{match.group(1)}-{match.group(2)}-01"


def extract_report(path: Path) -> dict:
    matches = []
    with pymupdf.open(path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = " ".join(page.get_text("text").split())
            match = CONTACT_PATTERN.search(text)
            if match:
                matches.append((page_number, match))

    if len(matches) != 1:
        raise ValueError(
            f"Expected one customer-service narrative, found {len(matches)}"
        )

    page_number, match = matches[0]
    contacts = int(match.group(1).replace(",", ""))
    month_name = match.group(2).lower()
    year = int(match.group(3))
    offered_calls = int(match.group(4).replace(",", ""))
    service_level = float(match.group(5))
    minutes = int(match.group(6))
    seconds = int(match.group(7) or 0)

    if month_name not in MONTHS:
        raise ValueError(f"Unknown narrative month: {match.group(2)}")
    narrative_month = f"{year:04d}-{MONTHS[month_name]:02d}-01"
    expected_month = report_month(path)
    if narrative_month != expected_month:
        raise ValueError(
            f"Narrative month {narrative_month} does not match {expected_month}"
        )
    if contacts <= 0:
        raise ValueError(f"Invalid customer contact count: {contacts}")
    if not 0 <= offered_calls <= contacts:
        raise ValueError(
            f"Agent-offered calls {offered_calls} exceed total calls {contacts}"
        )
    if not 0 <= service_level <= 100:
        raise ValueError(f"Invalid service level: {service_level}")
    if seconds >= 60:
        raise ValueError(f"Invalid answer-time seconds component: {seconds}")

    return {
        "report_month": expected_month,
        "observation_month": expected_month,
        "customer_contacts": contacts,
        "service_level_pct": service_level,
        "average_speed_seconds": minutes * 60 + seconds,
        "agent_offered_calls": offered_calls,
        "source_page": page_number,
    }


def validate_candidates(rows: list[dict]) -> None:
    if len(rows) != EXPECTED_REPORTS:
        raise ValueError(
            f"Expected {EXPECTED_REPORTS} customer-service rows, got {len(rows)}"
        )
    months = [row["observation_month"] for row in rows]
    if len(set(months)) != EXPECTED_REPORTS:
        raise ValueError("Customer-service report months are not unique")


def write_candidates(rows: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CANDIDATE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_database(rows: list[dict]) -> int:
    validate_candidates(rows)
    if not DB_PATH.exists():
        raise ValueError(f"Database not found: {DB_PATH}")

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
            raise ValueError(
                "Missing matching report records for: " + ", ".join(missing)
            )

        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM customer_service")
        conn.executemany(
            """
            INSERT INTO customer_service (
                report_id,
                observation_month,
                customer_contacts,
                service_level_pct,
                average_speed_seconds,
                extraction_method,
                source_page,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    report_ids[row["report_month"]],
                    row["observation_month"],
                    row["customer_contacts"],
                    row["service_level_pct"],
                    row["average_speed_seconds"],
                    "regex_text",
                    row["source_page"],
                    (
                        "Total monthly calls; average speed of answer normalized "
                        "from reported minutes and seconds. "
                        f"Agent-offered calls reported: {row['agent_offered_calls']}."
                    ),
                )
                for row in rows
            ],
        )

        count = conn.execute("SELECT COUNT(*) FROM customer_service").fetchone()[0]
        distinct_months = conn.execute(
            "SELECT COUNT(DISTINCT observation_month) FROM customer_service"
        ).fetchone()[0]
        if count != EXPECTED_REPORTS or distinct_months != EXPECTED_REPORTS:
            raise ValueError(
                "Post-load validation expected 15 rows and 15 distinct months, "
                f"found {count} rows and {distinct_months} months"
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
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Load SQLite only after all 15 reports pass validation.",
    )
    args = parser.parse_args()

    pdfs = sorted(RAW_DIR.glob("weir_river_*.pdf"))
    print("CUSTOMER SERVICE EXTRACTION")
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
            row = extract_report(path)
            rows.append(row)
            print(
                f"{month}  contacts={row['customer_contacts']}  "
                f"service={row['service_level_pct']}%  "
                f"answer_seconds={row['average_speed_seconds']}  "
                f"page={row['source_page']}  PASS"
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
    print(f"Reports passed: {len(rows)}/{EXPECTED_REPORTS}")
    print(f"Candidate rows: {len(rows)}")
    print(f"Candidate CSV: {CANDIDATE_CSV}")

    if args.write_db:
        loaded = load_database(rows)
        print(f"Database load complete: {loaded} customer_service rows")
    else:
        print("SQLite was NOT modified. Review candidates before --write-db.")


if __name__ == "__main__":
    main()
