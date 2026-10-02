import unittest

from ktb_rtd_monitor import _metrics
from analyze_snapshots import analyze


class MetricTests(unittest.TestCase):
    def test_metrics_reverse_excel_ask_order(self):
        row = _metrics("x", [104.75, 104.74, 104.73, 104.72, 104.71], [99, 103, 163, 106, 87],
                       [104.80, 104.79, 104.78, 104.77, 104.76], [26, 17, 14, 10, 1])
        self.assertEqual(row["x_best_bid"], 104.75)
        self.assertEqual(row["x_best_ask"], 104.76)
        self.assertAlmostEqual(row["x_mid"], 104.755)
        self.assertAlmostEqual(row["x_microprice"], 104.7599)
        self.assertGreater(row["x_obi"], 0)
        self.assertGreater(row["x_weighted_obi"], 0)

    def test_relative_value_analysis(self):
        rows = [{"timestamp_utc": "t1", "3y_mid": 100.0, "10y_mid": 100.0},
                {"timestamp_utc": "t2", "3y_mid": 100.1, "10y_mid": 100.4},
                {"timestamp_utc": "t3", "3y_mid": 100.2, "10y_mid": 100.8}]
        result = analyze(rows, window=2, beta=2.0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["latest_rv_change"], 0.2)


if __name__ == "__main__":
    unittest.main()
