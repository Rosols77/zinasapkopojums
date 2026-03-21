from datetime import datetime, timezone
import unittest

from observability_test_env import build_report, generate_sample_events


class ObservabilityTests(unittest.TestCase):
    def test_report_contains_source_and_latency(self) -> None:
        events = generate_sample_events(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        report = build_report(events, slow_threshold_ms=900)

        self.assertEqual(report["total_events"], 5)
        self.assertIn("rss", report["sources"])
        self.assertIn("api", report["sources"])
        self.assertIn("latency", report)
        self.assertGreaterEqual(report["latency"]["max_ms"], report["latency"]["min_ms"])

    def test_empty_report(self) -> None:
        report = build_report([])
        self.assertEqual(report["total_events"], 0)
        self.assertEqual(report["sources"], {})


if __name__ == "__main__":
    unittest.main()
