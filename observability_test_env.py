"""Simple observability-oriented testing environment for incoming data streams."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable, Any

SENSITIVE_KEYWORDS = {"password", "passwd", "token", "secret", "api_key", "private_key"}


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


@dataclass
class AuthGuard:
    """Simple auth guard for brute-force simulation in tests."""

    max_failures: int = 5
    lockout_seconds: int = 60
    failures: dict[str, int] | None = None
    locked_until: dict[str, datetime] | None = None

    def __post_init__(self) -> None:
        self.failures = self.failures or {}
        self.locked_until = self.locked_until or {}

    def attempt(self, username: str, password: str, expected_password: str, now: datetime) -> dict:
        lock_until = self.locked_until.get(username)
        if lock_until and now < lock_until:
            return {"allowed": False, "reason": "locked"}

        if password == expected_password:
            self.failures[username] = 0
            return {"allowed": True, "reason": "ok"}

        current_failures = self.failures.get(username, 0) + 1
        self.failures[username] = current_failures

        if current_failures >= self.max_failures:
            self.locked_until[username] = now + timedelta(seconds=self.lockout_seconds)
            return {"allowed": False, "reason": "locked"}

        return {"allowed": False, "reason": "invalid_credentials"}


@dataclass
class IpRateLimiter:
    """In-memory IP rate limiter simulation for security tests."""

    max_attempts: int = 5
    window_seconds: int = 10
    attempts: dict[str, list[datetime]] | None = None

    def __post_init__(self) -> None:
        self.attempts = self.attempts or {}

    def allow(self, ip: str, now: datetime) -> bool:
        history = self.attempts.get(ip, [])
        window_start = now - timedelta(seconds=self.window_seconds)
        fresh_history = [stamp for stamp in history if stamp >= window_start]

        allowed = len(fresh_history) < self.max_attempts
        if allowed:
            fresh_history.append(now)

        self.attempts[ip] = fresh_history
        return allowed


def generate_sample_events(now: datetime | None = None) -> list[DataEvent]:
    now = now or datetime.now(timezone.utc)
    return [
        DataEvent("evt-001", "rss", now - timedelta(seconds=15), now - timedelta(seconds=14, milliseconds=600), 512),
        DataEvent("evt-002", "rss", now - timedelta(seconds=12), now - timedelta(seconds=11, milliseconds=100), 256),
        DataEvent("evt-003", "api", now - timedelta(seconds=8), now - timedelta(seconds=7, milliseconds=200), 1024),
        DataEvent("evt-004", "api", now - timedelta(seconds=5), now - timedelta(seconds=4, milliseconds=300), 768),
        DataEvent("evt-005", "manual", now - timedelta(seconds=3), now - timedelta(seconds=2, milliseconds=500), 128, status="warning"),
    ]


def _build_per_source_latency(items: list[DataEvent]) -> dict:
    per_source: dict[str, list[int]] = {}
    for event in items:
        per_source.setdefault(event.source, []).append(event.latency_ms)

    return {
        source: {
            "count": len(latencies),
            "avg_ms": int(mean(latencies)),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
        }
        for source, latencies in per_source.items()
    }


def _build_quality(items: list[DataEvent], now: datetime, oversized_payload_threshold: int = 900) -> dict:
    negative_latency_count = len([event for event in items if event.latency_ms < 0])
    future_sent_count = len([event for event in items if event.sent_at > now])
    oversized_payload_count = len([event for event in items if event.payload_size > oversized_payload_threshold])

    return {
        "negative_latency_count": negative_latency_count,
        "future_sent_count": future_sent_count,
        "oversized_payload_count": oversized_payload_count,
        "oversized_payload_threshold": oversized_payload_threshold,
    }


def _find_sensitive_keys(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []

    if isinstance(value, dict):
        for key, item in value.items():
            key_lower = str(key).lower()
            path = f"{prefix}.{key}" if prefix else str(key)
            if any(keyword in key_lower for keyword in SENSITIVE_KEYWORDS):
                findings.append(path)
            findings.extend(_find_sensitive_keys(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]"
            findings.extend(_find_sensitive_keys(item, prefix=path))

    return findings


def find_sensitive_keys(value: Any) -> list[str]:
    """Public wrapper used by tests to detect sensitive keys in nested structures."""
    return _find_sensitive_keys(value)


def resolve_artifact_path(base_dir: Path, requested_path: str) -> Path:
    """Resolve path safely and block path traversal attempts outside base_dir."""
    base_resolved = base_dir.resolve()
    candidate = (base_resolved / requested_path).resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise PermissionError("Path traversal attempt blocked")
    return candidate


def simulate_bruteforce_guard(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    guard = AuthGuard(max_failures=5, lockout_seconds=60)

    username = "test-user"
    expected_password = "correct-password"

    attempts = []
    for offset in range(5):
        attempts.append(
            guard.attempt(username, password="wrong-password", expected_password=expected_password, now=now + timedelta(seconds=offset))
        )

    # Sixth attempt tries correct password immediately after lockout should still be blocked
    attempts.append(
        guard.attempt(username, password=expected_password, expected_password=expected_password, now=now + timedelta(seconds=6))
    )

    blocked_count = len([item for item in attempts if not item["allowed"]])
    bypass_possible = any(item["allowed"] for item in attempts[-1:])
    lockout_triggered = any(item["reason"] == "locked" for item in attempts)

    return {
        "attempts_total": len(attempts),
        "blocked_attempts": blocked_count,
        "lockout_triggered": lockout_triggered,
        "bypass_possible": bypass_possible,
    }


def simulate_ip_rate_limit(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    limiter = IpRateLimiter(max_attempts=5, window_seconds=10)

    primary_ip = "203.0.113.10"
    secondary_ip = "198.51.100.5"

    primary_results = []
    for offset in range(7):
        primary_results.append(limiter.allow(primary_ip, now + timedelta(seconds=offset)))

    secondary_result = limiter.allow(secondary_ip, now + timedelta(seconds=7))

    return {
        "primary_ip": primary_ip,
        "secondary_ip": secondary_ip,
        "primary_blocked_count": len([result for result in primary_results if not result]),
        "primary_blocked": any(not result for result in primary_results),
        "secondary_allowed": secondary_result,
    }


def simulate_cooldown_recovery(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    guard = AuthGuard(max_failures=3, lockout_seconds=30)
    username = "test-user"
    expected_password = "correct-password"

    for offset in range(3):
        guard.attempt(username, "wrong-password", expected_password, now + timedelta(seconds=offset))

    during_lockout = guard.attempt(username, expected_password, expected_password, now + timedelta(seconds=5))
    after_lockout = guard.attempt(username, expected_password, expected_password, now + timedelta(seconds=33))

    return {
        "during_lockout_allowed": during_lockout["allowed"],
        "after_cooldown_allowed": after_lockout["allowed"],
        "after_cooldown_reason": after_lockout["reason"],
    }


def _build_security(items: list[DataEvent], artifacts_dir: Path) -> dict:
    security_probe_target = "../users_secure.key"

    try:
        resolve_artifact_path(artifacts_dir, security_probe_target)
        path_traversal_blocked = False
    except PermissionError:
        path_traversal_blocked = True

    serialized_events = [event.to_dict() for event in items]
    sensitive_key_findings = _find_sensitive_keys(serialized_events)

    return {
        "path_traversal_probe": security_probe_target,
        "path_traversal_blocked": path_traversal_blocked,
        "sensitive_keys_found": sensitive_key_findings,
        "sensitive_keys_found_count": len(sensitive_key_findings),
        "bruteforce_simulation": simulate_bruteforce_guard(),
        "ip_rate_limit_simulation": simulate_ip_rate_limit(),
        "cooldown_recovery_simulation": simulate_cooldown_recovery(),
    }


def build_report(events: Iterable[DataEvent], slow_threshold_ms: int = 1000, artifacts_dir: Path | None = None) -> dict:
    items = list(events)
    now = datetime.now(timezone.utc)
    artifacts_dir = artifacts_dir or Path("artifacts")

    if not items:
        return {
            "generated_at": now.isoformat(),
            "total_events": 0,
            "sources": {},
            "latency": {"avg_ms": 0, "min_ms": 0, "max_ms": 0, "slow_count": 0, "slow_threshold_ms": slow_threshold_ms},
            "status": {},
            "per_source_latency": {},
            "quality": _build_quality(items, now),
            "security": _build_security(items, artifacts_dir),
            "events": [],
        }

    latencies = [event.latency_ms for event in items]
    sources: dict[str, int] = {}
    statuses: dict[str, int] = {}
    for event in items:
        sources[event.source] = sources.get(event.source, 0) + 1
        statuses[event.status] = statuses.get(event.status, 0) + 1

    return {
        "generated_at": now.isoformat(),
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
        "per_source_latency": _build_per_source_latency(items),
        "quality": _build_quality(items, now),
        "security": _build_security(items, artifacts_dir),
        "events": [event.to_dict() for event in items],
    }
