import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("USER_DATA_KEY", "dDlsDpt00fRqonsA9wOhvcpuTa6sZwdeZGephG7YJaY=")


def test_lsm_uses_official_category_feeds():
    import app

    lsm_urls = app.DEFAULT_SOURCES["LSM"]
    assert any("catid=14" in url for url in lsm_urls)
    assert any("catid=20" in url for url in lsm_urls)
    assert all("lsm.lv/rss/" in url for url in lsm_urls)


def test_parse_feed_sends_browser_like_headers(monkeypatch):
    import app

    captured = {}

    def fake_parse(url, request_headers=None):
        captured["url"] = url
        captured["headers"] = request_headers
        return type("Feed", (), {"entries": []})()

    monkeypatch.setattr(app.feedparser, "parse", fake_parse)

    app.parse_feed("https://www.lsm.lv/rss/?lang=lv&catid=14")

    assert captured["headers"]["User-Agent"].startswith("Mozilla/5.0")
    assert "application/rss+xml" in captured["headers"]["Accept"]
