"""Simple observability-oriented testing environment for incoming data streams."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Iterable


@dataclass
class DataEvent:
    event_id: str
    source: str
    sent_at: datetime
    received_at: datetime
    payload_size: int
    status: str = "ok"

    @property
    def latency_ms(self) -> int:
        return int((self.received_at - self.sent_at).total_seconds() * 1000)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sent_at"] = self.sent_at.isoformat()
        data["received_at"] = self.received_at.isoformat()
        data["latency_ms"] = self.latency_ms
        return data


def generate_sample_events(now: datetime | None = None) -> list[DataEvent]:
    now = now or datetime.now(timezone.utc)
    return [
        DataEvent("evt-001", "rss", now - timedelta(seconds=15), now - timedelta(seconds=14, milliseconds=600), 512),
        DataEvent("evt-002", "rss", now - timedelta(seconds=12), now - timedelta(seconds=11, milliseconds=100), 256),
        DataEvent("evt-003", "api", now - timedelta(seconds=8), now - timedelta(seconds=7, milliseconds=200), 1024),
        DataEvent("evt-004", "api", now - timedelta(seconds=5), now - timedelta(seconds=4, milliseconds=300), 768),
        DataEvent("evt-005", "manual", now - timedelta(seconds=3), now - timedelta(seconds=2, milliseconds=500), 128, status="warning"),
    ]


def build_report(events: Iterable[DataEvent], slow_threshold_ms: int = 1000) -> dict:
    items = list(events)
    if not items:
        return {
            "total_events": 0,
            "sources": {},
            "latency": {"avg_ms": 0, "min_ms": 0, "max_ms": 0, "slow_count": 0},
            "status": {},
            "events": [],
        }

    latencies = [event.latency_ms for event in items]
    sources: dict[str, int] = {}
    statuses: dict[str, int] = {}
    for event in items:
        sources[event.source] = sources.get(event.source, 0) + 1
        statuses[event.status] = statuses.get(event.status, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": len(items),
        "sources": sources,
        "latency": {
            "avg_ms": int(mean(latencies)),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "slow_count": len([ms for ms in latencies if ms > slow_threshold_ms]),
            "slow_threshold_ms": slow_threshold_ms,
        },
        "status": statuses,
        "events": [event.to_dict() for event in items],
    }
