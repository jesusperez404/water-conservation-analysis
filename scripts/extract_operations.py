import re
import sqlite3
from pathlib import Path

import pymupdf


DB_PATH = Path("database/water.db")


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


# ---------------------------------------------------------------------
# SOURCE-VALIDATED EXPECTATIONS
#
# These values were reviewed against the 15 official Hingham
# Water System monthly reports.
#
# They are ONLY used to validate the extraction.
# They are never used to populate the database.
# ---------------------------------------------------------------------

EXPECTED = {
    "2024-10-01": {
        "backflow_tests": 261,
        "surveys": 26,
        "main_breaks": 2,
        "service_line_repairs": 4,
        "hydrant_replacements": None,
        "valve_replacements": 2,
        "dig_safe_markouts": 287,
    },
    "2024-11-01": {
        "backflow_tests": 145,
        "surveys": 22,
        "main_breaks": None,
        "service_line_repairs": 1,
        "hydrant_replacements": None,
        "valve_replacements": None,
        "dig_safe_markouts": 280,
    },
    "2024-12-01": {
        "backflow_tests": 95,
        "surveys": 23,
        "main_breaks": 1,
        "service_line_repairs": 1,
        "hydrant_replacements": None,
        "valve_replacements": None,
        "dig_safe_markouts": 211,
    },
    "2025-01-01": {
        "backflow_tests": 341,
        "surveys": 31,
        "main_breaks": 9,
        "service_line_repairs": 4,
        "hydrant_replacements": None,
        "valve_replacements": None,
        "dig_safe_markouts": 188,
    },
    "2025-02-01": {
        "backflow_tests": 253,
        "surveys": 24,
        "main_breaks": 8,
        "service_line_repairs": None,
        "hydrant_replacements": None,
        "valve_replacements": None,
        "dig_safe_markouts": 163,
    },
    "2025-03-01": {
        "backflow_tests": 246,
        "surveys": 21,
        "main_breaks": 4,
        "service_line_repairs": 2,
        "hydrant_replacements": None,
        "valve_replacements": None,
        "dig_safe_markouts": 337,
    },
    "2025-04-01": {
        "backflow_tests": 194,
        "surveys": 27,
        "main_breaks": 1,
        "service_line_repairs": None,
        "hydrant_replacements": 4,
        "valve_replacements": None,
        "dig_safe_markouts": 473,
    },
    "2025-05-01": {
        "backflow_tests": 81,
        "surveys": 25,
        "main_breaks": 1,
        "service_line_repairs": 6,
        "hydrant_replacements": 5,
        "valve_replacements": None,
        "dig_safe_markouts": 491,
    },
    "2025-06-01": {
        "backflow_tests": 81,
        "surveys": 16,
        "main_breaks": 5,
        "service_line_repairs": 7,
        "hydrant_replacements": None,
        "valve_replacements": None,
        "dig_safe_markouts": 469,
    },
    "2025-07-01": {
        "backflow_tests": 303,
        "surveys": 15,
        "main_breaks": 7,
        "service_line_repairs": 4,
        "hydrant_replacements": None,
        "valve_replacements": None,
        "dig_safe_markouts": 384,
    },
    "2025-08-01": {
        "backflow_tests": 191,
        "surveys": 8,
        "main_breaks": 4,
        "service_line_repairs": 2,
        "hydrant_replacements": None,
        "valve_replacements": 4,
        "dig_safe_markouts": 375,
    },
    "2025-09-01": {
        "backflow_tests": 99,
        "surveys": 1,
        "main_breaks": 1,
        "service_line_repairs": 1,
        "hydrant_replacements": 2,
        "valve_replacements": 3,
        "dig_safe_markouts": 346,
    },
    "2025-10-01": {
        "backflow_tests": 74,
        "surveys": 1,
        "main_breaks": 1,
        "service_line_repairs": 8,
        "hydrant_replacements": 3,
        "valve_replacements": 2,
        "dig_safe_markouts": 449,
    },
    "2025-11-01": {
        "backflow_tests": 25,
        "surveys": 2,
        "main_breaks": 1,
        "service_line_repairs": 7,
        "hydrant_replacements": 3,
        "valve_replacements": None,
        "dig_safe_markouts": 318,
    },
    "2025-12-01": {
        "backflow_tests": 12,
        "surveys": 1,
        "main_breaks": None,
        "service_line_repairs": 3,
        "hydrant_replacements": None,
        "valve_replacements": 1,
        "dig_safe_markouts": 228,
    },
}


def parse_number(value):
    """Convert a number word or numeric string to an integer."""

    value = value.strip().lower()

    if value in NUMBER_WORDS:
        return NUMBER_WORDS[value]

    return int(value)


def find_distribution_section(doc):
    """
    Find the actual 1.2 Distribution System section.

    The heading also appears in the Table of Contents, so we search
    all occurrences and only accept one containing actual operational
    content.
    """

    for page_number, page in enumerate(doc, start=1):

        text = page.get_text()

        matches = list(
            re.finditer(
                r"1\.2\s+Distribution\s+System",
                text,
                re.IGNORECASE,
            )
        )

        if not matches:
            continue

        for heading_match in matches:

            section = text[heading_match.end():]

            end_match = re.search(
                r"1\.3\s+MADEP\s+Sampling",
                section,
                re.IGNORECASE,
            )

            if end_match:
                section = section[:end_match.start()]

            # Ignore Table of Contents occurrences.
            content_indicators = [
                "backflow",
                "Dig Safe",
                "main break",
                "service",
                "hydrant",
                "valve",
            ]

            if not any(
                indicator.lower() in section.lower()
                for indicator in content_indicators
            ):
                continue

            return section, page_number

    return None, None


def extract_backflow_and_surveys(section):
    """Extract backflow tests and customer surveys."""

    backflow = None
    surveys = None

    match = re.search(
        r"(\d+)\s+backflow\s+devices?\s+"
        r"(?:were|was)\s+tested",
        section,
        re.IGNORECASE,
    )

    if match:
        backflow = int(match.group(1))

    match = re.search(
        r"(\d+)\s+surveys?\s+"
        r"(?:were|was)\s+performed",
        section,
        re.IGNORECASE,
    )

    if match:
        surveys = int(match.group(1))

    return backflow, surveys


def extract_main_breaks(section):
    """
    Extract explicit water main breaks.

    Do not count:
      - hydrant branch breaks
      - emergency main leaks
      - leak-detection leaks
    """

    match = re.search(
        r"(\d+)\s+main\s+breaks?\s+"
        r"(?:were|was)\s+repaired",
        section,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    match = re.search(
        r"repaired\s+(\d+)\s+"
        r"water\s+main\s+breaks?",
        section,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    # December 2024:
    # "repaired broken 6” water main..."
    match = re.search(
        r"repaired\s+(?:a\s+)?broken\s+"
        r"\d+\s*[\"'”]?\s+water\s+main\b",
        section,
        re.IGNORECASE,
    )

    if match:
        return 1

    return None


def extract_service_line_repairs(section):
    """
    Extract explicit service/service-line repair activity.

    Missing activity remains NULL.

    Recognizes the wording variations found in the 15 reports,
    including September 2025:
        "relayed and relocated a 1” service line"
    """

    total = 0
    found = False

    # ---------------------------------------------------------------
    # Numeric service wording.
    #
    # Examples:
    #   4 services were relayed/repaired
    #   6 water services were repaired/replaced
    #   7 water services were repaired/replaced
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\b"
        r"(\d+)\s+"
        r"(?:water\s+)?"
        r"services?"
        r"\s+(?:were|was)\s+"
        r"(?:relayed/repaired|"
        r"repaired/replaced(?:/installed)?|"
        r"repaired|"
        r"relayed|"
        r"replaced)"
        r"\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += int(match.group(1))
        found = True

    # ---------------------------------------------------------------
    # Number-word wording:
    #
    # "eight service lines were relayed and relocated"
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\b"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"\s+service\s+lines?"
        r"\s+(?:were|was)\s+"
        r"relayed\s+and\s+relocated\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += parse_number(match.group(1))
        found = True

    # ---------------------------------------------------------------
    # September 2025:
    #
    # "relayed and relocated a 1” service line"
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\brelayed\s+and\s+relocated\s+"
        r"(?:a\s+)?"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"\s*[\"'”]?\s+"
        r"(?:water\s+)?"
        r"service\s+lines?\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += parse_number(match.group(1))
        found = True

    # ---------------------------------------------------------------
    # Reverse wording:
    #
    # "repaired/replaced 2 water services"
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\b"
        r"(?:repaired/replaced|"
        r"replaced/repaired|"
        r"relayed/repaired)"
        r"\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"\s+"
        r"(?:water\s+)?"
        r"(?:services?|service\s+lines?)"
        r"\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += parse_number(match.group(1))
        found = True

    # ---------------------------------------------------------------
    # December 2024:
    #
    # "Relayed service at 10 Weston"
    # ---------------------------------------------------------------

    if re.search(
        r"\brelayed\s+service\b",
        section,
        re.IGNORECASE,
    ):

        total += 1
        found = True

    # ---------------------------------------------------------------
    # November 2024:
    #
    # "1 leaking service"
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\b"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"\s+leaking\s+service\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += parse_number(match.group(1))
        found = True

    return total if found else None


def extract_hydrant_replacements(section):
    """
    Count actual hydrant replacements.

    Painting, inspection, and installation do not count.
    """

    total = 0
    found = False

    pattern = re.compile(
        r"\breplaced\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"\s+"
        r"(?:old\s+)?"
        r"(?:out\s+of\s+service\s+)?"
        r"hydrants?\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += parse_number(match.group(1))
        found = True

    return total if found else None


def extract_valve_replacements(section):
    """
    Count actual valve replacements.

    Do not count:
      - installed valves
      - insertion valves that were installed
      - valve nuts
      - valve boxes
      - removed valves
    """

    total = 0
    found = False

    # ---------------------------------------------------------------
    # Numbered replacement statements.
    #
    # Examples:
    #   "replaced one broken valve"
    #   "replaced two broken 6” gate valves"
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\breplaced\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"\s+"
        r"(?:broken\s+)?"
        r"(?:closed\s+)?"
        r"(?:(?:\d+)\s*[\"'”]\s+)?"
        r"(?:gate\s+)?"
        r"valves?\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += parse_number(match.group(1))
        found = True

    # ---------------------------------------------------------------
    # Additional valve group in the same sentence.
    #
    # Example:
    #   "... two broken 6” gate valves in Hingham and two 2” valves
    #       in Hull"
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\band\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"\s+"
        r"(?:\d+\s*[\"'”]\s+)"
        r"(?:gate\s+)?"
        r"valves?\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += parse_number(match.group(1))
        found = True

    # ---------------------------------------------------------------
    # Singular replacement.
    #
    # Examples:
    #   "replaced a 12” valve"
    #   "replaced a broken 4” gate valve"
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\breplaced\s+a\s+"
        r"(?:broken\s+)?"
        r"(?:closed\s+)?"
        r"(?:(?:\d+)\s*[\"'”]\s+)?"
        r"(?:gate\s+)?"
        r"valve\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(section):

        total += 1
        found = True

    return total if found else None


def extract_dig_safe(section):
    """Extract completed Dig Safe mark outs."""

    match = re.search(
        r"(\d+)\s+Dig\s+Safe\s+"
        r"mark\s+outs?\s+"
        r"(?:were\s+)?completed",
        section,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    return None


def extract_operations(pdf_path):
    """Extract all operational metrics from one report."""

    doc = pymupdf.open(pdf_path)

    try:

        section, source_page = find_distribution_section(doc)

        if section is None:
            return None

        backflow, surveys = (
            extract_backflow_and_surveys(section)
        )

        return {
            "backflow_tests": backflow,
            "surveys": surveys,
            "main_breaks": extract_main_breaks(section),
            "service_line_repairs": (
                extract_service_line_repairs(section)
            ),
            "hydrant_replacements": (
                extract_hydrant_replacements(section)
            ),
            "valve_replacements": (
                extract_valve_replacements(section)
            ),
            "dig_safe_markouts": extract_dig_safe(section),
            "source_page": source_page,
            "extraction_method": "regex_source_validated",
        }

    finally:

        doc.close()


def validate_result(report_month, result):
    """Validate extracted data against source-reviewed expectations."""

    expected = EXPECTED.get(report_month)

    if expected is None:
        return True

    fields = [
        "backflow_tests",
        "surveys",
        "main_breaks",
        "service_line_repairs",
        "hydrant_replacements",
        "valve_replacements",
        "dig_safe_markouts",
    ]

    errors = []

    for field in fields:

        actual = result.get(field)
        target = expected.get(field)

        if actual != target:

            errors.append(
                f"{field}: expected {target}, got {actual}"
            )

    if errors:

        print("  VALIDATION FAILED:")

        for error in errors:
            print(f"    - {error}")

        return False

    print("  Validation: PASS")

    return True


def main():

    conn = sqlite3.connect(DB_PATH)

    try:

        reports = conn.execute(
            """
            SELECT report_id, report_month, file_path
            FROM reports
            ORDER BY report_month
            """
        ).fetchall()

        if len(reports) != 15:

            print(
                f"WARNING: Expected 15 reports, "
                f"found {len(reports)}."
            )

        extracted_results = []
        validation_failures = 0

        # -------------------------------------------------------------
        # PHASE 1
        #
        # Extract and validate all reports before touching the DB.
        # -------------------------------------------------------------

        for report_id, report_month, file_path in reports:

            print(
                f"Processing {report_month}..."
            )

            result = extract_operations(file_path)

            if result is None:

                print(
                    "  ERROR: Actual Distribution System "
                    "section not found."
                )

                validation_failures += 1
                continue

            print(
                f"  Backflow: {result['backflow_tests']}, "
                f"Surveys: {result['surveys']}, "
                f"Main breaks: {result['main_breaks']}, "
                f"Service lines: {result['service_line_repairs']}, "
                f"Hydrants: {result['hydrant_replacements']}, "
                f"Valves: {result['valve_replacements']}, "
                f"Dig Safe: {result['dig_safe_markouts']}"
            )

            if not validate_result(
                report_month,
                result,
            ):

                validation_failures += 1

            extracted_results.append(
                (
                    report_id,
                    report_month,
                    result,
                )
            )

        print()

        # -------------------------------------------------------------
        # SAFETY CHECK
        #
        # If even one report fails, do not modify operational_events.
        # -------------------------------------------------------------

        if validation_failures > 0:

            print(
                f"STOPPED: {validation_failures} "
                f"validation failure(s) detected."
            )

            print(
                "The operational_events table was NOT modified."
            )

            return

        # -------------------------------------------------------------
        # PHASE 2
        #
        # All reports passed. Rebuild operational_events.
        # -------------------------------------------------------------

        conn.execute(
            "DELETE FROM operational_events"
        )

        for report_id, report_month, result in extracted_results:

            operation_rows = [
                (
                    "backflow_tests",
                    result["backflow_tests"],
                ),
                (
                    "surveys",
                    result["surveys"],
                ),
                (
                    "main_breaks",
                    result["main_breaks"],
                ),
                (
                    "service_line_repairs",
                    result["service_line_repairs"],
                ),
                (
                    "hydrant_replacements",
                    result["hydrant_replacements"],
                ),
                (
                    "valve_replacements",
                    result["valve_replacements"],
                ),
                (
                    "dig_safe_markouts",
                    result["dig_safe_markouts"],
                ),
            ]

            for event_type, event_count in operation_rows:

                # NULL means the report did not explicitly report
                # that activity. Do not convert NULL to zero.

                if event_count is None:
                    continue

                conn.execute(
                    """
                    INSERT INTO operational_events (
                        report_id,
                        observation_month,
                        event_type,
                        event_count,
                        extraction_method,
                        source_page
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_id,
                        report_month,
                        event_type,
                        event_count,
                        result["extraction_method"],
                        result["source_page"],
                    ),
                )

        conn.commit()

        print(
            f"Extracted operations from "
            f"{len(extracted_results)} reports."
        )

        print(
            "ALL 15 SOURCE-VALIDATED OPERATIONS CHECKS PASSED."
        )

        print(
            "operational_events table updated successfully."
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


if __name__ == "__main__":
    main()