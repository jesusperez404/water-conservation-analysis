from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pymupdf


RAW_DIR = Path("data/raw")
DB_PATH = Path("database/water.db")
OUTPUT_DIR = Path("data/processed/chemical_usage_review")
CANDIDATE_CSV = OUTPUT_DIR / "chemical_usage_candidates.csv"

EXPECTED_REPORTS = 15
EXPECTED_CHEMICALS_PER_MONTH = 8

MONTHS = {
    name: number
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


@dataclass(frozen=True)
class ChemicalColumn:
    name: str
    unit: str


# Reading the intact PDF words from left to right avoids a table-detection
# defect that sometimes assigns the last digit of one value to the next cell.
CHEMICAL_COLUMNS = (
    ChemicalColumn("sodium_hypochlorite", "gallons"),
    ChemicalColumn("aluminum_sulfate", "report-specific"),
    ChemicalColumn("zinc_orthophosphate", "gallons"),
    ChemicalColumn("hydrofluorosilic_acid", "gallons"),
    ChemicalColumn("potassium_permanganate", "pounds"),
    ChemicalColumn("calcium_hydroxide", "tons"),
    ChemicalColumn("gen_floc_610", "pounds"),
    ChemicalColumn("gen_floc_620", "pounds"),
)


def report_month(path: Path) -> str:
    match = re.search(r"(\d{4})-(\d{2})", path.stem)
    if not match:
        raise ValueError(f"Could not determine report month from {path.name}")
    return f"{match.group(1)}-{match.group(2)}-01"


def find_chemical_page(doc: pymupdf.Document) -> tuple[pymupdf.Page, int]:
    matches = []
    for page_index, page in enumerate(doc):
        text = page.get_text("text")
        if (
            "CHEMICAL USE DATA" in text.upper()
            and "CHEMICAL USAGE REPORT" in text.upper()
        ):
            matches.append((page, page_index + 1))

    if len(matches) != 1:
        raise ValueError(
            "Expected one chemical-use table page, "
            f"found {len(matches)}"
        )
    return matches[0]


def parse_number(text: str) -> float:
    cleaned = text.replace(",", "").strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
        raise ValueError(f"Invalid numeric value: {text!r}")
    return float(cleaned)


def row_words(words: list[tuple], anchor_y: float) -> list[tuple]:
    return [word for word in words if abs(float(word[1]) - anchor_y) <= 1.5]


def extract_populated_rows(page: pymupdf.Page, source_page: int) -> list[dict]:
    words = page.get_text("words")
    year_words = [
        word
        for word in words
        if 90.0 <= float(word[0]) < 120.0
        and re.fullmatch(r"20\d{2}", str(word[4]))
    ]

    rows = []
    for year_word in year_words:
        same_row = row_words(words, float(year_word[1]))
        month_words = [
            word
            for word in same_row
            if 120.0 <= float(word[0]) < 175.0 and str(word[4]) in MONTHS
        ]
        if len(month_words) != 1:
            raise ValueError(
                f"Expected one month beside year {year_word[4]}, "
                f"found {[word[4] for word in month_words]}"
            )

        numeric_words = sorted(
            [word for word in same_row if float(word[0]) >= 175.0],
            key=lambda word: float(word[0]),
        )
        if not numeric_words:
            continue

        # Every populated row has eight chemical values followed by the
        # separate Dies./gen. field. The latter is intentionally excluded:
        # it is not a chemical and its unit is not specified in the report.
        if len(numeric_words) != EXPECTED_CHEMICALS_PER_MONTH + 1:
            raise ValueError(
                f"Expected nine populated values for {year_word[4]} "
                f"{month_words[0][4]}, found {len(numeric_words)}: "
                f"{[word[4] for word in numeric_words]}"
            )

        year = int(year_word[4])
        month_name = str(month_words[0][4])
        observation_month = date(year, MONTHS[month_name], 1).isoformat()

        values = {}
        for column, word in zip(CHEMICAL_COLUMNS, numeric_words[:8]):
            value = parse_number(str(word[4]))
            if value < 0:
                raise ValueError(f"Negative value for {column.name}: {value}")
            values[column.name] = value
        rows.append(
            {
                "observation_month": observation_month,
                "source_page": source_page,
                "values": values,
            }
        )

    if not rows:
        raise ValueError("No populated chemical-use rows found")
    return rows


def validate_repeated_history(extractions: list[dict]) -> None:
    observed = defaultdict(list)
    for extraction in extractions:
        for row in extraction["all_rows"]:
            for column in CHEMICAL_COLUMNS:
                observed[(row["observation_month"], column.name)].append(
                    (
                        extraction["report_month"],
                        row["values"][column.name],
                    )
                )

    conflicts = []
    for (month, chemical), occurrences in sorted(observed.items()):
        distinct = {value for _, value in occurrences}
        if len(distinct) > 1:
            detail = ", ".join(
                f"{source_month}={value}"
                for source_month, value in occurrences
            )
            conflicts.append(f"{month} {chemical}: {detail}")

    if conflicts:
        raise ValueError(
            "Repeated historical chemical values disagree:\n  "
            + "\n  ".join(conflicts)
        )


def build_candidates(extractions: list[dict]) -> list[dict]:
    candidates = []
    seen_months = set()

    for extraction in sorted(extractions, key=lambda item: item["report_month"]):
        month = extraction["report_month"]
        matching = [
            row
            for row in extraction["all_rows"]
            if row["observation_month"] == month
        ]
        if len(matching) != 1:
            raise ValueError(
                f"{month}: expected one current-month chemical row, "
                f"found {len(matching)}"
            )
        if month in seen_months:
            raise ValueError(f"Duplicate report month: {month}")
        seen_months.add(month)

        row = matching[0]
        for column in CHEMICAL_COLUMNS:
            candidates.append(
                {
                    "report_month": month,
                    "observation_month": month,
                    "chemical_name": column.name,
                    "amount": row["values"][column.name],
                    "unit": column.unit,
                    "source_page": row["source_page"],
                }
            )

    expected_rows = EXPECTED_REPORTS * EXPECTED_CHEMICALS_PER_MONTH
    if len(extractions) != EXPECTED_REPORTS:
        raise ValueError(
            f"Expected {EXPECTED_REPORTS} validated reports, "
            f"got {len(extractions)}"
        )
    if len(candidates) != expected_rows:
        raise ValueError(
            f"Expected {expected_rows} chemical candidates, "
            f"got {len(candidates)}"
        )
    if len(seen_months) != EXPECTED_REPORTS:
        raise ValueError(
            f"Expected {EXPECTED_REPORTS} distinct months, got {len(seen_months)}"
        )
    return candidates


def write_candidates(candidates: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CANDIDATE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(candidates[0]))
        writer.writeheader()
        writer.writerows(candidates)


def load_database(candidates: list[dict]) -> int:
    expected_rows = EXPECTED_REPORTS * EXPECTED_CHEMICALS_PER_MONTH
    if len(candidates) != expected_rows:
        raise ValueError(
            f"Refusing database load: expected {expected_rows} rows, "
            f"got {len(candidates)}"
        )
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
        missing = sorted(
            {row["report_month"] for row in candidates} - set(report_ids)
        )
        if missing:
            raise ValueError(
                "Missing matching report records for: " + ", ".join(missing)
            )

        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM chemical_usage")
        conn.executemany(
            """
            INSERT INTO chemical_usage (
                report_id,
                observation_month,
                chemical_name,
                amount,
                unit,
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
                    row["chemical_name"],
                    row["amount"],
                    row["unit"],
                    "pdf_word_coordinates",
                    row["source_page"],
                    (
                        "Current-month row from the report's Chemical Use Data "
                        "table; repeated historical rows were cross-validated."
                    ),
                )
                for row in candidates
            ],
        )

        count = conn.execute("SELECT COUNT(*) FROM chemical_usage").fetchone()[0]
        distinct_months = conn.execute(
            "SELECT COUNT(DISTINCT observation_month) FROM chemical_usage"
        ).fetchone()[0]
        invalid_months = conn.execute(
            """
            SELECT observation_month, COUNT(*)
            FROM chemical_usage
            GROUP BY observation_month
            HAVING COUNT(*) != ?
            """,
            (EXPECTED_CHEMICALS_PER_MONTH,),
        ).fetchall()

        if count != expected_rows:
            raise ValueError(
                f"Post-load validation expected {expected_rows} rows, found {count}"
            )
        if distinct_months != EXPECTED_REPORTS:
            raise ValueError(
                "Post-load validation expected "
                f"{EXPECTED_REPORTS} months, found {distinct_months}"
            )
        if invalid_months:
            raise ValueError(
                f"Post-load validation found invalid monthly counts: {invalid_months}"
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
    print("CHEMICAL USAGE EXTRACTION")
    print("=" * 72)
    print(f"Reports found: {len(pdfs)}")
    print(f"Database write mode: {'ON' if args.write_db else 'OFF'}")
    if len(pdfs) != EXPECTED_REPORTS:
        raise SystemExit(
            f"Expected {EXPECTED_REPORTS} PDFs, found {len(pdfs)}. "
            "SQLite was NOT modified."
        )

    extractions = []
    failures = []
    for pdf_path in pdfs:
        month = report_month(pdf_path)
        try:
            with pymupdf.open(pdf_path) as doc:
                page, page_number = find_chemical_page(doc)
                rows = extract_populated_rows(page, page_number)
            extractions.append(
                {
                    "report_month": month,
                    "file_name": pdf_path.name,
                    "all_rows": rows,
                }
            )
            print(
                f"{month}  page={page_number}  "
                f"populated_rows={len(rows)}  PASS"
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
        validate_repeated_history(extractions)
        candidates = build_candidates(extractions)
    except Exception as exc:
        raise SystemExit(f"Validation failed: {exc}\nSQLite was NOT modified.")

    write_candidates(candidates)
    print("\nVALIDATION SUMMARY")
    print("=" * 72)
    print(f"Reports passed: {len(extractions)}/{EXPECTED_REPORTS}")
    print(f"Candidate rows: {len(candidates)}")
    print("Repeated historical values: CONSISTENT")
    print(f"Candidate CSV: {CANDIDATE_CSV}")

    if args.write_db:
        loaded = load_database(candidates)
        print(f"Database load complete: {loaded} chemical_usage rows")
    else:
        print("SQLite was NOT modified. Review candidates before --write-db.")


if __name__ == "__main__":
    main()
