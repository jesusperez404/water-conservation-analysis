import unittest

from scripts.extract_field_work_orders import (
    EXPECTED_REPORTS,
    EXPECTED_TYPES,
    validate_candidates,
)


class FieldWorkOrderTests(unittest.TestCase):
    def test_validate_candidates_accepts_two_types_per_month(self) -> None:
        months = [f"2025-{month:02d}-01" for month in range(1, 13)] + [
            f"2024-{month:02d}-01" for month in range(10, 13)
        ]
        rows = [
            {"observation_month": month, "work_order_type": work_type}
            for month in months
            for work_type in EXPECTED_TYPES
        ]
        self.assertEqual(len(months), EXPECTED_REPORTS)
        validate_candidates(rows)

    def test_validate_candidates_rejects_missing_type(self) -> None:
        rows = [
            {"observation_month": "2025-01-01", "work_order_type": "total"}
        ] * (EXPECTED_REPORTS * len(EXPECTED_TYPES))
        with self.assertRaises(ValueError):
            validate_candidates(rows)


if __name__ == "__main__":
    unittest.main()
