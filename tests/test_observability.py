from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest

from observability_test_env import (
    DataEvent,
    build_report,
    find_sensitive_keys,
    generate_sample_events,
    resolve_artifact_path,
    simulate_bruteforce_guard,
    simulate_cooldown_recovery,
    simulate_ip_rate_limit,
)


class ObservabilityTests(unittest.TestCase):
    def test_report_contains_source_latency_and_security(self) -> None:
        events = generate_sample_events(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        report = build_report(events, slow_threshold_ms=900)

        self.assertEqual(report["total_events"], 5)
        self.assertIn("rss", report["sources"])
        self.assertIn("api", report["sources"])
        self.assertIn("latency", report)
        self.assertIn("per_source_latency", report)
        self.assertIn("quality", report)
        self.assertIn("security", report)
        self.assertTrue(report["security"]["path_traversal_blocked"])
        self.assertGreaterEqual(report["latency"]["max_ms"], report["latency"]["min_ms"])

    def test_empty_report(self) -> None:
        report = build_report([])
        self.assertEqual(report["total_events"], 0)
        self.assertEqual(report["sources"], {})
        self.assertEqual(report["per_source_latency"], {})

    def test_quality_flags(self) -> None:
        now = datetime.now(timezone.utc)
        events = [
            DataEvent("e1", "api", now + timedelta(seconds=5), now + timedelta(seconds=3), 100),  # negative latency + future sent
            DataEvent("e2", "api", now - timedelta(seconds=3), now - timedelta(seconds=2), 2000),
        ]
        report = build_report(events)

        self.assertEqual(report["quality"]["negative_latency_count"], 1)
        self.assertGreaterEqual(report["quality"]["future_sent_count"], 1)
        self.assertEqual(report["quality"]["oversized_payload_count"], 1)

    def test_path_traversal_is_blocked(self) -> None:
        with self.assertRaises(PermissionError):
            resolve_artifact_path(Path("artifacts"), "../users_secure.key")

    def test_bruteforce_simulation_blocks_access(self) -> None:
        simulation = simulate_bruteforce_guard(now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertTrue(simulation["lockout_triggered"])
        self.assertFalse(simulation["bypass_possible"])
        self.assertGreaterEqual(simulation["blocked_attempts"], 5)

    def test_ip_rate_limit_blocks_one_ip_not_all(self) -> None:
        simulation = simulate_ip_rate_limit(now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertTrue(simulation["primary_blocked"])
        self.assertGreaterEqual(simulation["primary_blocked_count"], 1)
        self.assertTrue(simulation["secondary_allowed"])

    def test_cooldown_recovery_allows_login_after_timeout(self) -> None:
        simulation = simulate_cooldown_recovery(now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertFalse(simulation["during_lockout_allowed"])
        self.assertTrue(simulation["after_cooldown_allowed"])
        self.assertEqual(simulation["after_cooldown_reason"], "ok")

    def test_sensitive_key_detection_finds_nested_secret_fields(self) -> None:
        payload = {
            "meta": {
                "api_key": "hidden",
                "credentials": {
                    "password": "hidden",
                },
            }
        }
        findings = find_sensitive_keys(payload)

        self.assertIn("meta.api_key", findings)
        self.assertIn("meta.credentials.password", findings)


if __name__ == "__main__":
    unittest.main()
