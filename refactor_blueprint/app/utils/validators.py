from __future__ import annotations

from typing import Any


def parse_positive_int(value: Any, field_name: str = "id") -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Nederīgs {field_name}.")
    if parsed <= 0:
        raise ValueError(f"Nederīgs {field_name}.")
    return parsed


def sanitize_text(value: str | None, max_length: int = 200) -> str:
    return (value or "").strip()[:max_length]
