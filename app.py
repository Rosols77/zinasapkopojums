from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import feedparser
from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")
USERS_DATA_FILE = os.path.join(BASE_DIR, "users_secure.enc")
USERS_KEY_FILE = os.path.join(BASE_DIR, "users_secure.key")

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


class SecureUserStore:
    def __init__(self, data_file: str, key_file: str) -> None:
        self.data_file = data_file
        self.key_file = key_file
        self.fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        env_key = os.environ.get("USER_DATA_KEY")
        if env_key:
            return env_key.encode("utf-8")
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as file:
                return file.read().strip()

        key = Fernet.generate_key()
        with open(self.key_file, "wb") as file:
            file.write(key)
        return key

    def _read(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(self.data_file):
            return {}
        with open(self.data_file, "rb") as file:
            encrypted = file.read()
        if not encrypted:
            return {}
        try:
            raw = self.fernet.decrypt(encrypted)
        except InvalidToken:
            return {}
        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}

    def _write(self, data: Dict[str, Dict[str, Any]]) -> None:
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        encrypted = self.fernet.encrypt(raw)
        with open(self.data_file, "wb") as file:
            file.write(encrypted)

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.urlsafe_b64decode(salt.encode("utf-8")),
            200_000,
        )
        return base64.urlsafe_b64encode(digest).decode("utf-8")

    @staticmethod
    def _empty_activity() -> Dict[str, Any]:
        return {
            "viewed_article_ids": [],
            "saved_later_article_ids": [],
            "saved_important_article_ids": [],
            "ignored_article_ids": [],
            "ignored_sources": [],
        }

    @staticmethod
    def _add_unique(values: List[Any], value: Any) -> List[Any]:
        if value not in values:
            values.append(value)
        return values

    @staticmethod
    def _remove_value(values: List[Any], value: Any) -> List[Any]:
        return [item for item in values if item != value]

    def create_user(self, email: str, display_name: str, password: str) -> tuple[bool, str]:
        users = self._read()
        email_normalized = email.strip().lower()
        if email_normalized in users:
            return False, "Šāds e-pasts jau ir reģistrēts."

        salt = base64.urlsafe_b64encode(secrets.token_bytes(16)).decode("utf-8")
        users[email_normalized] = {
            "email": email_normalized,
            "display_name": display_name.strip(),
            "salt": salt,
            "password_hash": self._hash_password(password, salt),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login_at": None,
            "activity": self._empty_activity(),
        }
        self._write(users)
        return True, "Konts veiksmīgi izveidots."

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        users = self._read()
        record = users.get(email.strip().lower())
        if not record:
            return None
        expected = self._hash_password(password, record["salt"])
        if secrets.compare_digest(expected, record["password_hash"]):
            record["last_login_at"] = datetime.now(timezone.utc).isoformat()
            if "activity" not in record or not isinstance(record["activity"], dict):
                record["activity"] = self._empty_activity()
            users[record["email"]] = record
            self._write(users)
            return record
        return None

    def record_activity(self, email: str, action: str, payload: Any) -> None:
        users = self._read()
        email_normalized = email.strip().lower()
        user = users.get(email_normalized)
        if not user:
            return

        if "activity" not in user or not isinstance(user["activity"], dict):
            user["activity"] = self._empty_activity()
        activity = user["activity"]

        if action == "view_article":
            activity["viewed_article_ids"] = self._add_unique(activity.get("viewed_article_ids", []), payload)
        elif action == "save_later":
            activity["saved_later_article_ids"] = self._add_unique(activity.get("saved_later_article_ids", []), payload)
        elif action == "save_important":
            activity["saved_important_article_ids"] = self._add_unique(
                activity.get("saved_important_article_ids", []), payload
            )
        elif action == "unsave_later":
            activity["saved_later_article_ids"] = self._remove_value(activity.get("saved_later_article_ids", []), payload)
        elif action == "unsave_important":
            activity["saved_important_article_ids"] = self._remove_value(
                activity.get("saved_important_article_ids", []), payload
            )
        elif action == "ignore_article":
            activity["ignored_article_ids"] = self._add_unique(activity.get("ignored_article_ids", []), payload)
        elif action == "ignore_source":
            activity["ignored_sources"] = self._add_unique(activity.get("ignored_sources", []), payload)

        user["activity"] = activity
        users[email_normalized] = user
        self._write(users)


user_store = SecureUserStore(USERS_DATA_FILE, USERS_KEY_FILE)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn




def migrate_legacy_users_table(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    required = {"id", "email", "display_name", "created_at"}
    if required.issubset(columns):
        return

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    if "name" in columns:
        legacy_rows = conn.execute("SELECT id, name FROM users ORDER BY id").fetchall()
        for row in legacy_rows:
            legacy_id = int(row["id"])
            display_name = (row["name"] or f"legacy_{legacy_id}").strip()
            email = f"legacy_{legacy_id}@local.invalid"
            conn.execute(
                """
                INSERT OR IGNORE INTO users_new (id, email, display_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (legacy_id, email, display_name, now),
            )

    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")

def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        migrate_legacy_users_table(conn)
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
            CREATE TABLE IF NOT EXISTS viewed_articles (
                user_id INTEGER NOT NULL,
                article_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL,
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


def get_or_create_user(email: str, display_name: str) -> int:
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, existing["id"]))
            return int(existing["id"])
        cursor = conn.execute(
            "INSERT INTO users (email, display_name, created_at) VALUES (?, ?, ?)",
            (email, display_name, datetime.now(timezone.utc).isoformat()),
        )
        return int(cursor.lastrowid)


def current_user_id() -> int:
    email = session.get("user_email")
    display_name = session.get("display_name")
    if not email or not display_name:
        raise PermissionError("Lietotājs nav ielogojies")
    return get_or_create_user(email, display_name)


def current_user_email() -> str:
    email = session.get("user_email")
    if not email:
        raise PermissionError("Lietotājs nav ielogojies")
    return str(email)


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


def record_view(user_id: int, article_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO viewed_articles (user_id, article_id, viewed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, article_id) DO UPDATE SET viewed_at=excluded.viewed_at
            """,
            (user_id, article_id, datetime.now(timezone.utc).isoformat()),
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


def get_viewed_article_ids(user_id: int) -> List[int]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT article_id FROM viewed_articles WHERE user_id = ?",
            (user_id,),
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


def get_recently_viewed(user_id: int, limit: int = 30) -> List[sqlite3.Row]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.title, a.summary, a.source, a.published_at, a.url, a.topic, a.location, v.viewed_at
            FROM viewed_articles v
            JOIN articles a ON a.id = v.article_id
            WHERE v.user_id = ?
            ORDER BY v.viewed_at DESC
            LIMIT ?
            """,
            (user_id, limit),
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


@app.context_processor
def inject_user() -> Dict[str, Any]:
    return {
        "logged_in": "user_email" in session,
        "display_name": session.get("display_name"),
        "user_email": session.get("user_email"),
    }


@app.route("/")
def index() -> str:
    if "user_email" not in session:
        return redirect(url_for("login"))

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
    viewed_ids = set(get_viewed_article_ids(user_id))

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
        viewed_ids=viewed_ids,
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
    viewed_rows = get_recently_viewed(user_id)
    return render_template("history.html", history=history_rows, saved=saved_rows, viewed=viewed_rows)


@app.route("/register", methods=["GET", "POST"])
def register() -> str:
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        password_repeat = request.form.get("password_repeat", "")

        if not email or "@" not in email:
            flash("Ievadi derīgu e-pastu.", "danger")
            return render_template("register.html")

        if not display_name:
            flash("Ievadi lietotājvārdu.", "danger")
            return render_template("register.html")

        if len(password) < 8:
            flash("Parolei jābūt vismaz 8 simboli.", "danger")
            return render_template("register.html")

        if password != password_repeat:
            flash("Paroles nesakrīt.", "danger")
            return render_template("register.html")

        created, message = user_store.create_user(email, display_name, password)
        flash(message, "success" if created else "danger")
        if created:
            session["user_email"] = email
            session["display_name"] = display_name
            get_or_create_user(email, display_name)
            return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = user_store.authenticate(email, password)
        if user:
            session["user_email"] = user["email"]
            session["display_name"] = user["display_name"]
            get_or_create_user(user["email"], user["display_name"])
            return redirect(url_for("index"))
        flash("Nepareizs e-pasts vai parole.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout() -> str:
    session.clear()
    return redirect(url_for("login"))


@app.route("/refresh", methods=["POST"])
def refresh() -> str:
    upsert_articles()
    return redirect(url_for("index"))


@app.route("/article/<int:article_id>")
def open_article(article_id: int) -> str:
    user_id = current_user_id()
    email = current_user_email()
    with get_db() as conn:
        article = conn.execute("SELECT url FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not article:
        abort(404)
    record_view(user_id, article_id)
    user_store.record_activity(email, "view_article", article_id)
    return redirect(article["url"])


@app.route("/save", methods=["POST"])
def save_article() -> str:
    user_id = current_user_id()
    email = current_user_email()
    article_id = request.form.get("article_id")
    tag = request.form.get("tag")
    if article_id and tag:
        article_id_int = int(article_id)
        with get_db() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO saved_articles (user_id, article_id, tag, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, article_id_int, tag, datetime.now(timezone.utc).isoformat()),
            )
        if tag == "later":
            user_store.record_activity(email, "save_later", article_id_int)
        if tag == "important":
            user_store.record_activity(email, "save_important", article_id_int)
    return redirect(request.referrer or url_for("index"))


@app.route("/unsave", methods=["POST"])
def unsave_article() -> str:
    user_id = current_user_id()
    email = current_user_email()
    article_id = request.form.get("article_id")
    tag = request.form.get("tag")
    if article_id and tag:
        article_id_int = int(article_id)
        with get_db() as conn:
            conn.execute(
                "DELETE FROM saved_articles WHERE user_id = ? AND article_id = ? AND tag = ?",
                (user_id, article_id_int, tag),
            )
        if tag == "later":
            user_store.record_activity(email, "unsave_later", article_id_int)
        if tag == "important":
            user_store.record_activity(email, "unsave_important", article_id_int)
    return redirect(request.referrer or url_for("index"))


@app.route("/ignore-source", methods=["POST"])
def ignore_source() -> str:
    user_id = current_user_id()
    email = current_user_email()
    source = request.form.get("source")
    if source:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO ignored_sources (user_id, source) VALUES (?, ?)",
                (user_id, source),
            )
        user_store.record_activity(email, "ignore_source", source)
    return redirect(request.referrer or url_for("index"))


@app.route("/ignore-article", methods=["POST"])
def ignore_article() -> str:
    user_id = current_user_id()
    email = current_user_email()
    article_id = request.form.get("article_id")
    if article_id:
        article_id_int = int(article_id)
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO ignored_articles (user_id, article_id) VALUES (?, ?)",
                (user_id, article_id_int),
            )
        user_store.record_activity(email, "ignore_article", article_id_int)
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
