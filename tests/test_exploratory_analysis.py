import unittest

from analysis.run_exploratory_analysis import (
    calculate_anomalies,
    calculate_correlations,
    load_data,
)


class ExploratoryAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.monthly, cls.chemicals = load_data()

    def test_analysis_uses_all_validated_months(self) -> None:
        self.assertEqual(len(self.monthly), 15)
        self.assertEqual(len(self.chemicals), 120)

    def test_pond_usage_correlation_is_calculated_from_all_months(self) -> None:
        correlations = calculate_correlations(self.monthly, self.chemicals)
        pond_usage = correlations.loc[
            correlations["feature"] == "accord_pond_usage_mg"
        ].iloc[0]
        self.assertEqual(pond_usage["observations"], 15)
        self.assertGreater(pond_usage["pearson_r"], 0.9)

    def test_anomaly_screen_preserves_known_source_observations(self) -> None:
        anomalies = calculate_anomalies(self.monthly)
        actual = {
            (row.observation_month.strftime("%Y-%m-%d"), row.metric)
            for row in anomalies.itertuples()
        }
        self.assertEqual(
            actual,
            {
                ("2024-11-01", "maintenance_paid_usd"),
                ("2025-08-01", "estimated_reads_pct"),
                ("2025-10-01", "precipitation_inches"),
            },
        )


if __name__ == "__main__":
    unittest.main()
