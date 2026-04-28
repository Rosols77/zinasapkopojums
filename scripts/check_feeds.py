"""Ātra RSS avotu diagnostika.

Lietošana:
    python scripts/check_feeds.py

Ja redzi SSL kļūdu uz macOS, palaid:
    pip install -U certifi requests
vai Python instalācijas mapē: Install Certificates.command
"""
from __future__ import annotations

from app import DEFAULT_SOURCES, iter_feed_urls, parse_feed


def main() -> int:
    total_entries = 0
    failed = 0
    for source, urls in DEFAULT_SOURCES.items():
        source_total = 0
        for url in iter_feed_urls(urls):
            feed = parse_feed(url)
            entries = getattr(feed, "entries", []) or []
            source_total += len(entries)
            status = getattr(feed, "http_status", "-")
            print(f"{source:14} {status!s:>3} {len(entries):>3} {url}")
        if source_total == 0:
            failed += 1
        total_entries += source_total
    print("-" * 80)
    print(f"Kopā atrasti RSS ieraksti: {total_entries}")
    print(f"Avoti bez neviena ieraksta: {failed}")
    return 0 if total_entries > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
