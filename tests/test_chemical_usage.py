from copy import deepcopy
from pathlib import Path
import unittest

from scripts.extract_chemical_usage import (
    CHEMICAL_COLUMNS,
    EXPECTED_CHEMICALS_PER_MONTH,
    EXPECTED_REPORTS,
    build_candidates,
    parse_number,
    report_month,
    validate_repeated_history,
)


def values(seed: float) -> dict[str, float]:
    return {
        column.name: seed + index
        for index, column in enumerate(CHEMICAL_COLUMNS)
    }


def extractions() -> list[dict]:
    result = []
    for index in range(EXPECTED_REPORTS):
        year = 2024 + (9 + index) // 12
        month = (9 + index) % 12 + 1
        observation_month = f"{year:04d}-{month:02d}-01"
        result.append(
            {
                "report_month": observation_month,
                "file_name": f"weir_river_{observation_month[:7]}.pdf",
                "all_rows": [
                    {
                        "observation_month": observation_month,
                        "source_page": 5,
                        "values": values(float(index + 1)),
                    }
                ],
            }
        )
    return result


class ChemicalUsageTests(unittest.TestCase):
    def test_report_month_from_file_name(self) -> None:
        self.assertEqual(
            report_month(Path("weir_river_2025-12.pdf")),
            "2025-12-01",
        )

    def test_parse_number_accepts_commas(self) -> None:
        self.assertEqual(parse_number("19,476.30"), 19476.3)

    def test_parse_number_rejects_invalid_values(self) -> None:
        for text in ("", "Total", "1,2x3", "-1"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_number(text)

    def test_build_candidates_requires_eight_chemicals_for_all_reports(self) -> None:
        candidates = build_candidates(extractions())
        self.assertEqual(
            len(candidates),
            EXPECTED_REPORTS * EXPECTED_CHEMICALS_PER_MONTH,
        )
        self.assertEqual(
            len({row["observation_month"] for row in candidates}),
            EXPECTED_REPORTS,
        )
        self.assertEqual(
            {row["chemical_name"] for row in candidates},
            {column.name for column in CHEMICAL_COLUMNS},
        )

    def test_repeated_history_accepts_matching_values(self) -> None:
        rows = extractions()
        repeated = deepcopy(rows[0]["all_rows"][0])
        rows[1]["all_rows"].append(repeated)
        validate_repeated_history(rows)

    def test_repeated_history_rejects_conflicting_values(self) -> None:
        rows = extractions()
        repeated = deepcopy(rows[0]["all_rows"][0])
        repeated["values"][CHEMICAL_COLUMNS[0].name] += 1
        rows[1]["all_rows"].append(repeated)
        with self.assertRaisesRegex(ValueError, "Repeated historical"):
            validate_repeated_history(rows)


if __name__ == "__main__":
    unittest.main()
