from pathlib import Path
import unittest

from scripts.extract_customer_service import (
    EXPECTED_REPORTS,
    report_month,
    validate_candidates,
)


class CustomerServiceTests(unittest.TestCase):
    def test_report_month_from_file_name(self) -> None:
        self.assertEqual(
            report_month(Path("weir_river_2024-10.pdf")),
            "2024-10-01",
        )

    def test_validate_candidates_accepts_fifteen_unique_months(self) -> None:
        rows = [
            {"observation_month": f"2025-{month:02d}-01"}
            for month in range(1, 13)
        ] + [
            {"observation_month": f"2024-{month:02d}-01"}
            for month in range(10, 13)
        ]
        validate_candidates(rows)

    def test_validate_candidates_rejects_duplicates(self) -> None:
        rows = [{"observation_month": "2025-01-01"}] * EXPECTED_REPORTS
        with self.assertRaisesRegex(ValueError, "not unique"):
            validate_candidates(rows)


if __name__ == "__main__":
    unittest.main()
