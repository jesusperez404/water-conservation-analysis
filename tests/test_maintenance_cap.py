import unittest

from scripts.extract_maintenance_cap import (
    RASTER_TRANSCRIPTIONS,
    parse_amount,
    validate_candidates,
)


def valid_rows() -> list[dict]:
    months = [
        "2024-10-01", "2024-11-01", "2024-12-01",
        "2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01",
        "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01",
        "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
    ]
    return [
        {
            "observation_month": month,
            "category": "total",
            "monthly_expenditure_usd": 100.0,
            "cumulative_expenditure_usd": 200.0,
            "annual_budget_usd": 1000.0,
            "remaining_budget_usd": 800.0,
        }
        for month in months
    ]


class MaintenanceCapTests(unittest.TestCase):
    def test_parse_amount_handles_parenthetical_negative(self) -> None:
        self.assertEqual(parse_amount("(252,789.58)"), -252789.58)

    def test_validate_candidates_accepts_complete_reconciled_rows(self) -> None:
        validate_candidates(valid_rows())

    def test_validate_candidates_rejects_budget_mismatch(self) -> None:
        rows = valid_rows()
        rows[0]["remaining_budget_usd"] = 799.0
        with self.assertRaisesRegex(ValueError, "reconciliation failed"):
            validate_candidates(rows)

    def test_raster_fallback_is_limited_to_three_source_months(self) -> None:
        self.assertEqual(
            set(RASTER_TRANSCRIPTIONS),
            {"2025-01-01", "2025-02-01", "2025-03-01"},
        )


if __name__ == "__main__":
    unittest.main()
