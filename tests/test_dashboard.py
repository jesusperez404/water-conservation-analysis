from __future__ import annotations

import json
import unittest
from pathlib import Path

from dashboard.build_dashboard_data import build_dashboard_data


class DashboardTests(unittest.TestCase):
    def test_dashboard_data_has_complete_validated_coverage(self) -> None:
        data = build_dashboard_data()
        self.assertEqual(data["reporting_period"]["months"], 15)
        self.assertEqual(len(data["monthly"]), 15)
        self.assertEqual(len(data["chemicals"]), 15)
        self.assertEqual(len(data["chemical_units"]), 8)
        self.assertTrue(
            all(sum(row.values()) == 9 for row in [
                {key: value for key, value in coverage.items() if key != "observation_month"}
                for coverage in data["coverage"]
            ])
        )

    def test_tracked_dashboard_json_matches_database(self) -> None:
        tracked = json.loads(
            Path("dashboard/data/dashboard.json").read_text(encoding="utf-8")
        )
        self.assertEqual(tracked, build_dashboard_data())

    def test_dashboard_is_self_contained(self) -> None:
        html = Path("dashboard/index.html").read_text(encoding="utf-8")
        self.assertIn('href="styles.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertIn('href="methodology.html"', html)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)


if __name__ == "__main__":
    unittest.main()
