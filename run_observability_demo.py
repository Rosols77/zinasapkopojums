"""CLI demo for observability testing environment."""

from __future__ import annotations

import json
from pathlib import Path

from observability_test_env import build_report, generate_sample_events


if __name__ == "__main__":
    events = generate_sample_events()
    report = build_report(events, slow_threshold_ms=900)

    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    out_path = artifacts_dir / "latest_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Data flow observability report ===")
    print(f"Total events: {report['total_events']}")
    print(f"Sources: {report['sources']}")
    print(f"Latency: {report['latency']}")
    print(f"Status: {report['status']}")
    print(f"Saved JSON report: {out_path}")
