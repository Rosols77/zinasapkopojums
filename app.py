from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import feedparser
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")

DEFAULT_SOURCES = {
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    "Reuters": "https://feeds.reuters.com/reuters/topNews",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "Fox News": "http://feeds.foxnews.com/foxnews/latest",
    "LSM": "https://www.lsm.lv/rss/",
}

TOPIC_KEYWORDS = {
    "Ukraina": ["ukrain", "kijiv", "kyiv", "donbas", "kriev"],
    "AI": ["ai", "mākslīg", "machine learning", "chatgpt"],
    "Klimats": ["klimat", "climate", "emis", "oglek"],
    "Ekonomika": ["ekonom", "infl", "bank", "market"],
    "Tehnoloģijas": ["tech", "tehnoloģ", "software", "startup"],
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT,
                source TEXT NOT NULL,
                published_at TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                topic TEXT,
                location TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_articles (
                user_id INTEGER NOT NULL,
                article_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, article_id, tag)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ignored_sources (
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY (user_id, source)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ignored_articles (
                user_id INTEGER NOT NULL,
                article_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, article_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def get_or_create_user(name: str) -> int:
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        if existing:
            return int(existing["id"])
        cursor = conn.execute("INSERT INTO users (name) VALUES (?)", (name,))
        return int(cursor.lastrowid)


def current_user_id() -> int:
    if "user_name" not in session:
        session["user_name"] = "demo"
    return get_or_create_user(session["user_name"])


def normalize_text(text: str) -> str:
    return text.lower()


def detect_topic(title: str, summary: str) -> str:
    text = normalize_text(f"{title} {summary}")
    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return topic
    return "Cits"


def parse_published(entry: Any) -> datetime:
    published = entry.get("published_parsed")
    if published:
        return datetime(*published[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def upsert_articles() -> int:
    inserted = 0
    with get_db() as conn:
        for source, feed_url in DEFAULT_SOURCES.items():
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "Bez virsraksta")
                summary = entry.get("summary", "")
                url = entry.get("link", "")
                if not url:
                    continue
                published_at = parse_published(entry).isoformat()
                topic = detect_topic(title, summary)
                location = entry.get("dc_coverage") or entry.get("location")
                try:
                    conn.execute(
                        """
                        INSERT INTO articles (title, summary, source, published_at, url, topic, location)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (title, summary, source, published_at, url, topic, location),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    continue
    return inserted


def record_search(user_id: int, query: str) -> None:
    if not query:
        return
    with get_db() as conn:
        conn.execute(
            "INSERT INTO search_history (user_id, query, created_at) VALUES (?, ?, ?)",
            (user_id, query, datetime.now(timezone.utc).isoformat()),
        )


def fetch_articles(
    user_id: int,
    query: str,
    days: Optional[int],
    source: Optional[str],
) -> List[sqlite3.Row]:
    filters = []
    params: List[Any] = []

    if query:
        filters.append("(title LIKE ? OR summary LIKE ? OR topic LIKE ?)")
        like_query = f"%{query}%"
        params.extend([like_query, like_query, like_query])

    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        filters.append("published_at >= ?")
        params.append(since.isoformat())

    if source:
        filters.append("source = ?")
        params.append(source)

    ignored_sources = get_ignored_sources(user_id)
    ignored_articles = get_ignored_articles(user_id)

    if ignored_sources:
        placeholders = ",".join("?" for _ in ignored_sources)
        filters.append(f"source NOT IN ({placeholders})")
        params.extend(ignored_sources)

    if ignored_articles:
        placeholders = ",".join("?" for _ in ignored_articles)
        filters.append(f"id NOT IN ({placeholders})")
        params.extend(ignored_articles)

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    with get_db() as conn:
        return conn.execute(
            f"""
            SELECT id, title, summary, source, published_at, url, topic, location
            FROM articles
            {where_clause}
            ORDER BY published_at DESC
            """,
            params,
        ).fetchall()


def get_sources() -> List[str]:
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT source FROM articles ORDER BY source").fetchall()
    return [row["source"] for row in rows]


def get_ignored_sources(user_id: int) -> List[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT source FROM ignored_sources WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [row["source"] for row in rows]


def get_ignored_articles(user_id: int) -> List[int]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT article_id FROM ignored_articles WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [int(row["article_id"]) for row in rows]


def get_saved_article_ids(user_id: int, tag: str) -> List[int]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT article_id FROM saved_articles WHERE user_id = ? AND tag = ?",
            (user_id, tag),
        ).fetchall()
    return [int(row["article_id"]) for row in rows]


def get_saved_articles(user_id: int, tag: str) -> List[sqlite3.Row]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.title, a.summary, a.source, a.published_at, a.url, a.topic, a.location
            FROM articles a
            JOIN saved_articles s ON s.article_id = a.id
            WHERE s.user_id = ? AND s.tag = ?
            ORDER BY s.created_at DESC
            """,
            (user_id, tag),
        ).fetchall()
    return rows


def build_topic_counts(articles: Iterable[sqlite3.Row]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for article in articles:
        topic = article["topic"] or "Cits"
        counts[topic] = counts.get(topic, 0) + 1
    return counts


def sort_by_topic_coverage(articles: List[sqlite3.Row]) -> List[sqlite3.Row]:
    counts = build_topic_counts(articles)
    return sorted(articles, key=lambda row: counts.get(row["topic"] or "Cits", 0), reverse=True)


@app.route("/")
def index() -> str:
    user_id = current_user_id()
    query = request.args.get("q", "").strip()
    days_raw = request.args.get("days")
    source = request.args.get("source")
    sort = request.args.get("sort", "time")

    days = int(days_raw) if days_raw and days_raw.isdigit() else None

    record_search(user_id, query)

    articles = fetch_articles(user_id, query, days, source)
    if sort == "coverage":
        articles = sort_by_topic_coverage(articles)

    sources = get_sources()
    saved_later = set(get_saved_article_ids(user_id, "later"))
    saved_important = set(get_saved_article_ids(user_id, "important"))

    topic_counts = build_topic_counts(articles)

    return render_template(
        "index.html",
        articles=articles,
        sources=sources,
        selected_source=source,
        selected_days=days_raw,
        query=query,
        sort=sort,
        saved_later=saved_later,
        saved_important=saved_important,
        topic_counts=topic_counts,
    )


@app.route("/compare")
def compare() -> str:
    user_id = current_user_id()
    topic = request.args.get("topic", "").strip()
    articles = fetch_articles(user_id, topic, None, None)
    grouped: Dict[str, List[sqlite3.Row]] = {}
    for article in articles:
        grouped.setdefault(article["source"], []).append(article)
    return render_template("compare.html", topic=topic, grouped=grouped)


@app.route("/saved")
def saved() -> str:
    user_id = current_user_id()
    articles = get_saved_articles(user_id, "later")
    return render_template("saved.html", articles=articles, title="Lasīt vēlāk")


@app.route("/important")
def important() -> str:
    user_id = current_user_id()
    articles = get_saved_articles(user_id, "important")
    return render_template("saved.html", articles=articles, title="Svarīgie")


@app.route("/history")
def history() -> str:
    user_id = current_user_id()
    with get_db() as conn:
        history_rows = conn.execute(
            """
            SELECT query, created_at
            FROM search_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()
        saved_rows = conn.execute(
            """
            SELECT id, query, created_at
            FROM saved_searches
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return render_template("history.html", history=history_rows, saved=saved_rows)


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            session["user_name"] = name
            current_user_id()
            return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/refresh", methods=["POST"])
def refresh() -> str:
    upsert_articles()
    return redirect(url_for("index"))


@app.route("/save", methods=["POST"])
def save_article() -> str:
    user_id = current_user_id()
    article_id = request.form.get("article_id")
    tag = request.form.get("tag")
    if article_id and tag:
        with get_db() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO saved_articles (user_id, article_id, tag, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, article_id, tag, datetime.now(timezone.utc).isoformat()),
            )
    return redirect(request.referrer or url_for("index"))


@app.route("/unsave", methods=["POST"])
def unsave_article() -> str:
    user_id = current_user_id()
    article_id = request.form.get("article_id")
    tag = request.form.get("tag")
    if article_id and tag:
        with get_db() as conn:
            conn.execute(
                "DELETE FROM saved_articles WHERE user_id = ? AND article_id = ? AND tag = ?",
                (user_id, article_id, tag),
            )
    return redirect(request.referrer or url_for("index"))


@app.route("/ignore-source", methods=["POST"])
def ignore_source() -> str:
    user_id = current_user_id()
    source = request.form.get("source")
    if source:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO ignored_sources (user_id, source) VALUES (?, ?)",
                (user_id, source),
            )
    return redirect(request.referrer or url_for("index"))


@app.route("/ignore-article", methods=["POST"])
def ignore_article() -> str:
    user_id = current_user_id()
    article_id = request.form.get("article_id")
    if article_id:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO ignored_articles (user_id, article_id) VALUES (?, ?)",
                (user_id, article_id),
            )
    return redirect(request.referrer or url_for("index"))


@app.route("/save-search", methods=["POST"])
def save_search() -> str:
    user_id = current_user_id()
    query = request.form.get("query", "").strip()
    if query:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO saved_searches (user_id, query, created_at) VALUES (?, ?, ?)",
                (user_id, query, datetime.now(timezone.utc).isoformat()),
            )
    return redirect(request.referrer or url_for("index"))


@app.route("/remove-saved-search", methods=["POST"])
def remove_saved_search() -> str:
    user_id = current_user_id()
    search_id = request.form.get("search_id")
    if search_id:
        with get_db() as conn:
            conn.execute(
                "DELETE FROM saved_searches WHERE id = ? AND user_id = ?",
                (search_id, user_id),
            )
    return redirect(request.referrer or url_for("history"))


def ensure_seed_data() -> None:
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) as total FROM articles").fetchone()["total"]
    if count == 0:
        upsert_articles()


if __name__ == "__main__":
    ensure_seed_data()
    app.run(debug=True)
