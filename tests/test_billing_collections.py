import unittest

from scripts.extract_billing_collections import (
    EXPECTED_MISSING_AR_MONTHS,
    EXPECTED_REPORTS,
    numeric_series,
    parse_money,
    validate_candidates,
    values_after_label,
)


class BillingCollectionsTests(unittest.TestCase):
    def test_parse_money(self) -> None:
        self.assertEqual(parse_money("$1,182,432.68"), 1182432.68)

    def test_parse_money_rejects_ambiguous_thousands_punctuation(self) -> None:
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            parse_money("990.575")

    def test_chart_series_share_month_headers(self) -> None:
        lines = ["Jan", "Feb", "FIRE", "10", "20", "WATER", "100", "200"]
        months, fire = numeric_series(lines, "FIRE")
        water = values_after_label(lines, "WATER", len(months))
        self.assertEqual(months, [1, 2])
        self.assertEqual(fire, [10.0, 20.0])
        self.assertEqual(water, [100.0, 200.0])

    def test_validate_candidates_requires_documented_missing_month(self) -> None:
        months = [f"2025-{month:02d}-01" for month in range(1, 13)] + [
            f"2024-{month:02d}-01" for month in range(10, 13)
        ]
        rows = [
            {
                "observation_month": month,
                "aged_accounts_receivable_usd": (
                    None if month in EXPECTED_MISSING_AR_MONTHS else 100.0
                ),
                "accounts_receivable_90_plus_usd": (
                    None if month in EXPECTED_MISSING_AR_MONTHS else 50.0
                ),
            }
            for month in months
        ]
        self.assertEqual(len(rows), EXPECTED_REPORTS)
        validate_candidates(rows)


if __name__ == "__main__":
    unittest.main()
