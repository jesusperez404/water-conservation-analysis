from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
from pathlib import Path

import pymupdf


RAW_DIR = Path("data/raw")
DB_PATH = Path("database/water.db")
OUTPUT_DIR = Path("data/processed/maintenance_cap_review")
CANDIDATE_CSV = OUTPUT_DIR / "maintenance_cap_candidates.csv"
EXPECTED_REPORTS = 15

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

# January through March 2025 contain the MCAP worksheet as a single raster
# image, so there are no PDF words to parse. These source-validated
# transcriptions are accepted only when the decoded worksheet-image digest
# matches the archived report. A changed source image therefore fails before
# SQLite can be modified.
RASTER_TRANSCRIPTIONS = {
    "2025-01-01": {
        "image_sha256": "9153b309928ccc58202a59ae7f43c429dbda6a85312ab68d3f02ce679e2faff2",
        "monthly_expenditure_usd": 70310.0,
        "estimated_work_not_paid_usd": 4327.0,
        "cumulative_expenditure_usd": 594496.60,
        "annual_budget_usd": 781493.76,
        "remaining_budget_usd": 186997.16,
    },
    "2025-02-01": {
        "image_sha256": "f7c96e9ced91cdee73bd708ce6cde98af77d0afc67510a549e533a77636f0709",
        "monthly_expenditure_usd": 139611.0,
        "estimated_work_not_paid_usd": 800.0,
        "cumulative_expenditure_usd": 706666.45,
        "annual_budget_usd": 781493.76,
        "remaining_budget_usd": 74827.31,
    },
    "2025-03-01": {
        "image_sha256": "24bd135e9213d1bd9f558313b77179b9518dcc3e9750e3a2c922e900d7e74664",
        "monthly_expenditure_usd": 108045.0,
        "estimated_work_not_paid_usd": 86.0,
        "cumulative_expenditure_usd": 813997.87,
        "annual_budget_usd": 781493.76,
        "remaining_budget_usd": -32504.11,
    },
}


def report_month(path: Path) -> str:
    match = re.search(r"(\d{4})-(\d{2})", path.stem)
    if not match:
        raise ValueError(f"Could not determine report month from {path.name}")
    return f"{match.group(1)}-{match.group(2)}-01"


def parse_amount(text: str) -> float:
    value = text.strip().replace("$", "").replace(",", "")
    if value in {"", "-"}:
        return 0.0
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    amount = float(value)
    return -amount if negative else amount


def is_amount_word(text: str) -> bool:
    return bool(re.fullmatch(r"\(?[\d,]+(?:\.\d+)?\)?", text.strip()))


def find_section_page(doc: pymupdf.Document) -> tuple[int, pymupdf.Page]:
    candidates = []
    for page_index, page in enumerate(doc):
        text = " ".join(page.get_text("text").split()).upper()
        if "MAINTENANCE CAP" not in text or "PERSONNEL" not in text:
            continue
        if "TABLE OF CONTENTS" in text:
            continue
        candidates.append((page_index, page))
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one maintenance-CAP section page, found {len(candidates)}"
        )
    return candidates[0]


def words_on_line(words: list[tuple], anchor: tuple, tolerance: float = 1.5) -> list[tuple]:
    return sorted(
        [word for word in words if abs(float(word[1]) - float(anchor[1])) <= tolerance],
        key=lambda word: float(word[0]),
    )


def numeric_words_to_right(line: list[tuple], anchor: tuple) -> list[tuple]:
    return [
        word for word in line
        if float(word[0]) > float(anchor[2]) and is_amount_word(str(word[4]))
    ]


def find_current_month_row(words: list[tuple], month_name: str) -> tuple[tuple, list[tuple]]:
    candidates = []
    for word in words:
        if str(word[4]).lower() != month_name.lower():
            continue
        line = words_on_line(words, word)
        if not any(str(item[4]) == "$" for item in line):
            continue
        numbers = numeric_words_to_right(line, word)
        if numbers:
            candidates.append((word, line))
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one populated {month_name} table row, found {len(candidates)}"
        )
    return candidates[0]


def bottom_summary_amount(
    words: list[tuple], label: str, after_y: float, *, allow_dash: bool = False
) -> float:
    anchors = [
        word for word in words
        if str(word[4]).lower() == label.lower() and float(word[1]) > after_y
    ]
    for anchor in sorted(anchors, key=lambda word: float(word[1]), reverse=True):
        line = words_on_line(words, anchor)
        numbers = numeric_words_to_right(line, anchor)
        if numbers:
            return parse_amount(str(numbers[-1][4]))
        if allow_dash and any(str(word[4]).strip() == "-" for word in line):
            return 0.0
    raise ValueError(f"Bottom summary value for {label!r} not found")


def raster_image_digest(doc: pymupdf.Document, page: pymupdf.Page) -> str:
    images = page.get_images(full=True)
    large_images = [image for image in images if int(image[2]) * int(image[3]) > 1_000_000]
    if len(large_images) != 1:
        raise ValueError(
            f"Expected one raster MCAP worksheet image, found {len(large_images)}"
        )
    pixmap = pymupdf.Pixmap(doc, int(large_images[0][0]))
    return hashlib.sha256(pixmap.samples).hexdigest()


def extract_vector_table(page: pymupdf.Page, observation_month: str) -> dict:
    page_words = page.get_text("words")
    month_name = MONTHS[int(observation_month[5:7]) - 1]
    month_word, line = find_current_month_row(page_words, month_name)
    row_numbers = numeric_words_to_right(line, month_word)
    monthly_paid = parse_amount(str(row_numbers[0][4]))

    # The estimate column precedes the cumulative column. It is optional and
    # the PDF's absolute column positions vary slightly by report template.
    estimate = 0.0
    if len(row_numbers) >= 2 and float(row_numbers[1][0]) / page.rect.width < 0.55:
        estimate = parse_amount(str(row_numbers[1][4]))

    row_y = float(month_word[1])
    annual_budget = bottom_summary_amount(page_words, "Contract", row_y)
    invoices_paid = bottom_summary_amount(page_words, "Invoices", row_y)
    estimated_exact = bottom_summary_amount(
        page_words, "Estimated", row_y, allow_dash=True
    )
    remaining = bottom_summary_amount(page_words, "Remaining", row_y)
    cumulative = round(invoices_paid + estimated_exact, 2)

    return {
        "monthly_expenditure_usd": monthly_paid,
        "estimated_work_not_paid_usd": estimate,
        "cumulative_expenditure_usd": cumulative,
        "annual_budget_usd": annual_budget,
        "remaining_budget_usd": remaining,
        "extraction_method": "pdf_table_words",
    }


def extract_report(path: Path) -> dict:
    observation_month = report_month(path)
    with pymupdf.open(path) as doc:
        page_index, page = find_section_page(doc)
        page_text = " ".join(page.get_text("text").split())
        expected_heading = (
            f"{MONTHS[int(observation_month[5:7]) - 1]} {observation_month[:4]}"
        )
        if expected_heading not in page_text:
            raise ValueError(
                f"Report heading does not identify {expected_heading}"
            )

        if observation_month in RASTER_TRANSCRIPTIONS:
            values = dict(RASTER_TRANSCRIPTIONS[observation_month])
            expected_digest = values.pop("image_sha256")
            actual_digest = raster_image_digest(doc, page)
            if actual_digest != expected_digest:
                raise ValueError(
                    "Raster MCAP worksheet differs from the validated source image"
                )
            values["extraction_method"] = "source_validated_raster_transcription"
        else:
            if "Total Paid Monthly" not in page_text:
                raise ValueError("Selectable MCAP table heading not found")
            values = extract_vector_table(page, observation_month)

    values.update(
        {
            "report_month": observation_month,
            "observation_month": observation_month,
            "category": "total",
            "source_page": page_index + 1,
        }
    )
    return values


def validate_candidates(rows: list[dict]) -> None:
    if len(rows) != EXPECTED_REPORTS:
        raise ValueError(f"Expected {EXPECTED_REPORTS} rows, got {len(rows)}")
    months = [row["observation_month"] for row in rows]
    if len(set(months)) != EXPECTED_REPORTS:
        raise ValueError("Maintenance-CAP months are not unique")
    if sorted(months) != [
        "2024-10-01", "2024-11-01", "2024-12-01",
        "2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01",
        "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01",
        "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
    ]:
        raise ValueError("Maintenance-CAP month coverage is incomplete")

    for row in rows:
        month = row["observation_month"]
        if row["category"] != "total":
            raise ValueError(f"{month}: unexpected category")
        if row["monthly_expenditure_usd"] < 0:
            raise ValueError(f"{month}: monthly paid expenditure is negative")
        budget = row["annual_budget_usd"]
        cumulative = row["cumulative_expenditure_usd"]
        remaining = row["remaining_budget_usd"]
        if budget <= 0 or cumulative < 0:
            raise ValueError(f"{month}: invalid budget or cumulative expenditure")
        if abs((budget - cumulative) - remaining) > 0.02:
            raise ValueError(
                f"{month}: budget reconciliation failed "
                f"({budget} - {cumulative} != {remaining})"
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
        conn.execute("DELETE FROM maintenance_cap")
        conn.executemany(
            """
            INSERT INTO maintenance_cap (
                report_id,
                observation_month,
                category,
                monthly_expenditure_usd,
                cumulative_expenditure_usd,
                annual_budget_usd,
                remaining_budget_usd,
                extraction_method,
                source_page,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    report_ids[row["report_month"]],
                    row["observation_month"],
                    row["category"],
                    row["monthly_expenditure_usd"],
                    row["cumulative_expenditure_usd"],
                    row["annual_budget_usd"],
                    row["remaining_budget_usd"],
                    row["extraction_method"],
                    row["source_page"],
                    "Monthly expenditure is the current report's Total Paid Monthly "
                    "Maintenance Expenses value. Cumulative expenditure reconciles "
                    "invoices paid plus estimated work completed but not paid; the "
                    f"displayed current-month estimate was "
                    f"${row['estimated_work_not_paid_usd']:,.0f}.",
                )
                for row in rows
            ],
        )
        count = conn.execute("SELECT COUNT(*) FROM maintenance_cap").fetchone()[0]
        failures = conn.execute(
            """
            SELECT observation_month
            FROM maintenance_cap
            WHERE category != 'total'
               OR monthly_expenditure_usd < 0
               OR annual_budget_usd <= 0
               OR cumulative_expenditure_usd < 0
               OR ABS(
                    annual_budget_usd
                    - cumulative_expenditure_usd
                    - remaining_budget_usd
               ) > 0.02
            """
        ).fetchall()
        if count != EXPECTED_REPORTS or failures:
            raise ValueError(
                f"Post-load validation found {count} rows; failures: {failures}"
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
    print("MAINTENANCE CAP EXTRACTION")
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
                f"{month}  paid={row['monthly_expenditure_usd']:.2f}  "
                f"cumulative={row['cumulative_expenditure_usd']:.2f}  "
                f"remaining={row['remaining_budget_usd']:.2f}  PASS"
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
        print(f"Database load complete: {loaded} maintenance_cap rows")
    else:
        print("SQLite was NOT modified. Review candidates before --write-db.")


if __name__ == "__main__":
    main()
