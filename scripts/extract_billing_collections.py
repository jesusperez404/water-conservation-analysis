from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path

import pymupdf


RAW_DIR = Path("data/raw")
DB_PATH = Path("database/water.db")
OUTPUT_DIR = Path("data/processed/billing_collections_review")
CANDIDATE_CSV = OUTPUT_DIR / "billing_collections_candidates.csv"
EXPECTED_REPORTS = 15
EXPECTED_MISSING_AR_MONTHS = {"2025-03-01"}

MONTH_NAMES = (
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
)
MONTH_NUMBERS = {name.lower(): index for index, name in enumerate(MONTH_NAMES, 1)}
MONTH_LABELS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "aug.": 8,
    "sep": 9,
    "sept.": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

BILLING_PATTERN = re.compile(
    r"Revenue Billed for the month of\s+([A-Za-z]+)\s+(20\d{2})\s+"
    r"is\s+\$([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
COLLECTIONS_PATTERN = re.compile(
    r"Revenues collected amounted to\s+\$([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
AR_PATTERN = re.compile(
    r"Aged Accounts Receivable as of\s+([A-Za-z]+)\s+(20\d{2})\s+"
    r"is at\s+\$([\d,]+(?:\.\d{1,3})?).*?"
    r"90 days and over is at\s+\$([\d,]+(?:\.\d{1,3})?)",
    re.IGNORECASE | re.DOTALL,
)


def report_month(path: Path) -> str:
    match = re.search(r"(\d{4})-(\d{2})", path.stem)
    if not match:
        raise ValueError(f"Could not determine report month from {path.name}")
    return f"{match.group(1)}-{match.group(2)}-01"


def parse_money(text: str) -> float:
    cleaned = text.replace("$", "").replace(",", "").strip().rstrip(".")
    if not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", cleaned):
        raise ValueError(f"Invalid or ambiguous monetary value: {text!r}")
    return float(cleaned)


def narrative_month(name: str, year: str) -> str:
    number = MONTH_NUMBERS.get(name.lower())
    if number is None:
        raise ValueError(f"Unknown narrative month: {name}")
    return f"{int(year):04d}-{number:02d}-01"


def normalized_lines(page: pymupdf.Page) -> list[str]:
    return [line.strip() for line in page.get_text("text").splitlines() if line.strip()]


def numeric_series(lines: list[str], label: str) -> tuple[list[int], list[float]]:
    label_index = next(
        (index for index, line in enumerate(lines) if line.casefold() == label.casefold()),
        None,
    )
    if label_index is None:
        raise ValueError(f"Chart series {label!r} not found")

    months = []
    index = label_index - 1
    while index >= 0 and lines[index].lower() in MONTH_LABELS:
        months.append(MONTH_LABELS[lines[index].lower()])
        index -= 1
    months.reverse()
    if not months:
        raise ValueError(f"Month labels for chart series {label!r} not found")

    values = []
    for line in lines[label_index + 1 :]:
        try:
            values.append(parse_money(line))
        except ValueError:
            if values:
                break
            continue
        if len(values) == len(months):
            break
    if len(values) != len(months):
        raise ValueError(
            f"Chart series {label!r} expected {len(months)} values, "
            f"found {len(values)}"
        )
    return months, values


def values_after_label(lines: list[str], label: str, count: int) -> list[float]:
    label_index = next(
        (index for index, line in enumerate(lines) if line.casefold() == label.casefold()),
        None,
    )
    if label_index is None:
        raise ValueError(f"Chart series {label!r} not found")
    values = []
    for line in lines[label_index + 1 :]:
        try:
            values.append(parse_money(line))
        except ValueError:
            if values:
                break
            continue
        if len(values) == count:
            break
    if len(values) != count:
        raise ValueError(
            f"Chart series {label!r} expected {count} values, found {len(values)}"
        )
    return values


def value_for_month(
    months: list[int], values: list[float], label: str, month_number: int
) -> float:
    matches = [value for month, value in zip(months, values) if month == month_number]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one {label!r} chart value for month {month_number}, "
            f"found {len(matches)}"
        )
    return matches[0]


def billing_chart_fallback(doc: pymupdf.Document, month_number: int) -> tuple[float, int]:
    candidates = []
    for page_number, page in enumerate(doc, start=1):
        text = " ".join(page.get_text("text").split())
        if "Revenue Billed By Service" not in text:
            continue
        lines = normalized_lines(page)
        months, fire_values = numeric_series(lines, "FIRE")
        water_values = values_after_label(lines, "WATER", len(months))
        fire = value_for_month(months, fire_values, "FIRE", month_number)
        water = value_for_month(months, water_values, "WATER", month_number)
        candidates.append((fire + water, page_number))
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one billing chart fallback, found {len(candidates)}"
        )
    return candidates[0]


def ar_chart_90_plus(page: pymupdf.Page, month_number: int) -> float:
    lines = normalized_lines(page)
    months, over_180_values = numeric_series(lines, "Over 180")
    days_91_to_180_values = values_after_label(lines, "91-180", len(months))
    over_180 = value_for_month(
        months, over_180_values, "Over 180", month_number
    )
    days_91_to_180 = value_for_month(
        months, days_91_to_180_values, "91-180", month_number
    )
    return over_180 + days_91_to_180


def extract_report(path: Path) -> dict:
    expected_month = report_month(path)
    year, month_number, _ = map(int, expected_month.split("-"))

    billing_matches = []
    collection_matches = []
    ar_matches = []
    ar_pages = []

    with pymupdf.open(path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = " ".join(page.get_text("text").split())
            billing_matches.extend(
                (page_number, match) for match in BILLING_PATTERN.finditer(text)
            )
            collection_matches.extend(
                (page_number, match) for match in COLLECTIONS_PATTERN.finditer(text)
            )
            for match in AR_PATTERN.finditer(text):
                ar_matches.append((page_number, match))
            if "Over 180" in page.get_text("text") and "91-180" in page.get_text("text"):
                ar_pages.append((page_number, page))

        current_billing = [
            (page_number, match)
            for page_number, match in billing_matches
            if narrative_month(match.group(1), match.group(2)) == expected_month
        ]
        if len(current_billing) == 1:
            billing_page, billing_match = current_billing[0]
            revenue_billed = parse_money(billing_match.group(3))
            billing_method = "narrative_text"
        elif expected_month == "2025-02-01":
            revenue_billed, billing_page = billing_chart_fallback(doc, month_number)
            billing_method = "service_chart_sum"
        else:
            raise ValueError(
                f"Expected one current-month billing value, found {len(current_billing)}"
            )

        if len(collection_matches) != 1:
            raise ValueError(
                f"Expected one collections value, found {len(collection_matches)}"
            )
        collections_page, collections_match = collection_matches[0]
        revenue_collected = parse_money(collections_match.group(1))

        current_ar = [
            (page_number, match)
            for page_number, match in ar_matches
            if narrative_month(match.group(1), match.group(2)) == expected_month
        ]
        if len(current_ar) == 1:
            ar_page, ar_match = current_ar[0]
            aged_receivables = parse_money(ar_match.group(3))
            raw_90_plus = ar_match.group(4)
            if re.fullmatch(r"\d{3}\.\d{3}", raw_90_plus):
                matching_pages = [page for _, page in ar_pages]
                if len(matching_pages) != 1:
                    raise ValueError(
                        "Ambiguous 90+ value and no unique chart fallback"
                    )
                receivables_90_plus = ar_chart_90_plus(
                    matching_pages[0], month_number
                )
                ar_method = "narrative_and_chart_sum"
            else:
                receivables_90_plus = parse_money(raw_90_plus)
                ar_method = "narrative_text"
        elif expected_month in EXPECTED_MISSING_AR_MONTHS:
            ar_page = None
            aged_receivables = None
            receivables_90_plus = None
            ar_method = "not_reported"
        else:
            raise ValueError(
                f"Expected one current-month aged-receivables value, "
                f"found {len(current_ar)}"
            )

    if min(revenue_billed, revenue_collected) < 0:
        raise ValueError("Billing and collections values must be nonnegative")
    if aged_receivables is not None and aged_receivables < 0:
        raise ValueError("Aged receivables must be nonnegative")
    if receivables_90_plus is not None:
        if receivables_90_plus < 0:
            raise ValueError("90+ receivables must be nonnegative")
        if receivables_90_plus > aged_receivables:
            raise ValueError("90+ receivables exceed total aged receivables")

    source_pages = sorted(
        {page for page in (billing_page, collections_page, ar_page) if page is not None}
    )
    return {
        "report_month": expected_month,
        "observation_month": expected_month,
        "revenue_billed_usd": revenue_billed,
        "revenue_collected_usd": revenue_collected,
        "aged_accounts_receivable_usd": aged_receivables,
        "accounts_receivable_90_plus_usd": receivables_90_plus,
        "billing_method": billing_method,
        "ar_method": ar_method,
        "source_pages": ",".join(str(page) for page in source_pages),
        "primary_source_page": billing_page,
    }


def validate_candidates(rows: list[dict]) -> None:
    if len(rows) != EXPECTED_REPORTS:
        raise ValueError(f"Expected {EXPECTED_REPORTS} rows, got {len(rows)}")
    months = {row["observation_month"] for row in rows}
    if len(months) != EXPECTED_REPORTS:
        raise ValueError("Billing and collections months are not unique")
    missing_ar = {
        row["observation_month"]
        for row in rows
        if row["aged_accounts_receivable_usd"] is None
        and row["accounts_receivable_90_plus_usd"] is None
    }
    if missing_ar != EXPECTED_MISSING_AR_MONTHS:
        raise ValueError(
            f"Unexpected missing aged-receivables months: {sorted(missing_ar)}"
        )


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
        conn.execute("DELETE FROM billing_collections")
        conn.executemany(
            """
            INSERT INTO billing_collections (
                report_id,
                observation_month,
                revenue_billed_usd,
                revenue_collected_usd,
                aged_accounts_receivable_usd,
                accounts_receivable_90_plus_usd,
                extraction_method,
                source_page,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    report_ids[row["report_month"]],
                    row["observation_month"],
                    row["revenue_billed_usd"],
                    row["revenue_collected_usd"],
                    row["aged_accounts_receivable_usd"],
                    row["accounts_receivable_90_plus_usd"],
                    "validated_text_and_chart",
                    row["primary_source_page"],
                    (
                        f"Source PDF pages: {row['source_pages']}. "
                        f"Billing method: {row['billing_method']}; "
                        f"aged-receivables method: {row['ar_method']}. "
                        "Missing source values are NULL."
                    ),
                )
                for row in rows
            ],
        )
        count = conn.execute("SELECT COUNT(*) FROM billing_collections").fetchone()[0]
        distinct_months = conn.execute(
            "SELECT COUNT(DISTINCT observation_month) FROM billing_collections"
        ).fetchone()[0]
        if count != EXPECTED_REPORTS or distinct_months != EXPECTED_REPORTS:
            raise ValueError(
                f"Post-load validation found {count} rows and "
                f"{distinct_months} distinct months"
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
    print("BILLING AND COLLECTIONS EXTRACTION")
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
                f"{month}  billed={row['revenue_billed_usd']}  "
                f"collected={row['revenue_collected_usd']}  "
                f"aged_ar={row['aged_accounts_receivable_usd']}  "
                f"ar_90_plus={row['accounts_receivable_90_plus_usd']}  PASS"
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
        print(f"Database load complete: {loaded} billing_collections rows")
    else:
        print("SQLite was NOT modified. Review candidates before --write-db.")


if __name__ == "__main__":
    main()
