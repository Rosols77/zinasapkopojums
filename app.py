from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import html
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import certifi
import feedparser
import requests
from cryptography.fernet import Fernet, InvalidToken
from functools import wraps
from urllib.parse import urlparse, urljoin

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")
USERS_DATA_FILE = os.path.join(BASE_DIR, "users_secure.enc")
USERS_KEY_FILE = os.path.join(BASE_DIR, "users_secure.key")

FEED_REQUEST_HEADERS = {
    # Daudzi ziņu portāli bloķē noklusētos Python/feedparser pieprasījumus.
    # Tāpēc izmantojam parasta pārlūka galvenes un RSS/XML Accept vērtības.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 ZinuApkopojums/1.1"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    "Accept-Language": "lv-LV,lv;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}
FEED_TIMEOUT_SECONDS = 12

# Katram avotam var būt vairākas barotnes. Tas novērš situāciju, kur viena
# vispārīgā RSS adrese mainās vai pazūd un avots vairs nerāda nevienu ziņu.
# LSM adreses ņemtas no oficiālās LSM RSS sadaļas /barotnes/.
DEFAULT_SOURCES = {
    # Latvijas avoti. Vairākiem avotiem ir dotas vairākas alternatīvas RSS adreses,
    # lai viena salūzusi barotne neapturētu visu ziņu ielādi.
    "LSM": [
        "https://www.lsm.lv/rss/zinas/latvija/",
        "https://www.lsm.lv/rss/zinas/pasaule/",
        "https://www.lsm.lv/rss/zinas/ekonomika/",
        "https://www.lsm.lv/rss/kultura/",
        "https://www.lsm.lv/rss/sports/",
        "https://www.lsm.lv/rss/dzive--stils/tehnologijas-un-zinatne/",
        "https://www.lsm.lv/rss/?lang=lv&catid=14",
        "https://www.lsm.lv/rss/?lang=lv&catid=20",
    ],
    "Delfi": [
        "https://www.delfi.lv/rss/",
        "https://www.delfi.lv/rss/news.xml",
        "https://www.delfi.lv/rss/latvia.xml",
        "https://www.delfi.lv/rss/world.xml",
    ],
    "TVNET": [
        "https://www.tvnet.lv/rss",
        "https://www.tvnet.lv/rss/jaunakas-zinas",
        "https://www.tvnet.lv/rss/latvija",
    ],
    "Jauns.lv": [
        "https://jauns.lv/rss",
        "https://jauns.lv/rss/zinas",
    ],
    "Apollo": ["https://www.apollo.lv/rss"],

    # Starptautiski avoti, kas kalpo arī kā rezerves avoti, ja lokālie portāli īslaicīgi
    # maina RSS struktūru vai bloķē pieprasījumus.
    "BBC": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://feeds.bbci.co.uk/sport/rss.xml",
    ],
    "Reuters": [
        "https://feeds.reuters.com/reuters/topNews",
        "https://feeds.reuters.com/Reuters/worldNews",
    ],
    "The Guardian": [
        "https://www.theguardian.com/world/rss",
        "https://www.theguardian.com/technology/rss",
        "https://www.theguardian.com/science/rss",
    ],
    "Euronews": ["https://www.euronews.com/rss?format=mrss"],
    "NPR": ["https://feeds.npr.org/1001/rss.xml"],
    "CNN": ["https://rss.cnn.com/rss/edition.rss"],
    "TechCrunch": ["https://techcrunch.com/feed/"],
    "The Verge": ["https://www.theverge.com/rss/index.xml"],
    "NASA": ["https://www.nasa.gov/rss/dyn/breaking_news.rss"],
    "ScienceDaily": ["https://www.sciencedaily.com/rss/all.xml"],
}

# Ja ārējie avoti nav sasniedzami, lietotne vairs neizskatās “pilnīgi tukša”.
# Šie ieraksti ir skaidri marķēti kā diagnostikas/rezerves ieraksti un palīdz saprast,
# ka problēma ir tīkla/RSS piekļuvē, nevis lapas attēlošanā.
FALLBACK_ARTICLES = [
    {
        "title": "Ziņu avotu pārbaude: RSS šobrīd nav sasniedzams",
        "summary": "Neizdevās ielādēt nevienu ārējo RSS avotu. Pārbaudi interneta savienojumu, DNS, ugunsmūri vai avotu URL. Nospied 'Atjaunot ziņas', kad savienojums ir pieejams.",
        "source": "Sistēma",
        "topic": "Diagnostika",
        "location": "",
        "url": "https://www.lsm.lv/",
        "image_url": "",
    },
]


TOPIC_PATTERNS = {
    "Latvija": [r"\blatvij\w*\b", r"\brīg\w*\b", r"\bsaeim\w*\b", r"\bvaldīb\w*\b", r"\bministr\w*\b", r"\briga\b", r"\blatvia\b"],
    "Kultūra": [r"\bkultūr\w*\b", r"\bculture\b", r"\bkino\b", r"\bfilm\w*\b", r"\bmūzik\w*\b", r"\bmusic\b", r"\bgrāmat\w*\b", r"\bteātr\w*\b", r"\bconcert\w*\b", r"\bart\b"],
    "Ekonomika": [r"\bekonom\w*\b", r"\binflāc\w*\b", r"\binflation\b", r"\bbank\w*\b", r"\btirg\w*\b", r"\bmarket\w*\b", r"\bfinance\b", r"\bnodok\w*\b", r"\bbudžet\w*\b", r"\bprocentu likm\w*\b"],
    "Pasaule": [r"\bpasaule\b", r"\bworld\b", r"\bglobal\w*\b", r"\beirop\w*\b", r"\beurope\b", r"\basia\b", r"\bafrica\b", r"\bamerica\b", r"\busa\b", r"\bfrance\b", r"\bgermany\b", r"\bchina\b"],
    "Ukraina": [r"\bukrain\w*\b", r"\bkijiv\w*\b", r"\bkyiv\b", r"\bdonbas\w*\b", r"\bkriev\w*\b", r"\brussia\w*\b", r"\bputin\b", r"\bzelensky\w*\b"],
    "Cits": [],
    "Sports": [r"\bsport\w*\b", r"\bfootball\b", r"\bfutbol\w*\b", r"\bbasketbol\w*\b", r"\bbasketball\b", r"\btennis\b", r"\bhokej\w*\b", r"\bhockey\b", r"\bolympic\w*\b"],
    "Politika": [r"\bpolit\w*\b", r"\bvēlēšan\w*\b", r"\belection\w*\b", r"\bpresident\w*\b", r"\bparliament\w*\b", r"\bgovernment\b", r"\bdiplom\w*\b"],
    "Bizness": [r"\bbiznes\w*\b", r"\bbusiness\b", r"\bcompany\b", r"\buzņēm\w*\b", r"\binvest\w*\b", r"\bprofit\w*\b", r"\btrade\b", r"\bstartup\w*\b"],
    "Tehnoloģijas": [r"\btech\b", r"\btechnology\b", r"\btehnoloģ\w*\b", r"\bsoftware\b", r"\bprogrammatūr\w*\b", r"\bkiber\w*\b", r"\bcyber\w*\b", r"\binternet\w*\b", r"\bviedtālrun\w*\b", r"\bgadget\w*\b"],
    "Drošība": [r"\bdrošīb\w*\b", r"\bsecurity\b", r"\bcrime\b", r"\bnozieg\w*\b", r"\bpolic\w*\b", r"\battack\w*\b", r"\buzbruk\w*\b", r"\bcyberattack\w*\b"],
    "Zinātne": [r"\bzinātn\w*\b", r"\bscience\b", r"\bresearch\b", r"\bpētījum\w*\b", r"\bspace\b", r"\bnasa\b", r"\bphysics\b", r"\bbiology\b"],
    "Izglītība": [r"\bizglīt\w*\b", r"\bschool\w*\b", r"\bskol\w*\b", r"\buniversity\b", r"\buniversit\w*\b", r"\bstudent\w*\b", r"\bteacher\w*\b"],
    "AI": [r"\bai\b", r"\bmākslīg\w*\s+intelekt\w*\b", r"\bartificial\s+intelligence\b", r"\bmachine\s+learning\b", r"\bchatgpt\b", r"\bopenai\b", r"\bgenerative\s+ai\b", r"\bneural\s+network\w*\b", r"\bliel\w*\s+valod\w*\s+model\w*\b"],
    "Klimats": [r"\bklimat\w*\b", r"\bclimate\b", r"\bemisij\w*\b", r"\bemission\w*\b", r"\boglek\w*\b", r"\bweather\b", r"\bflood\w*\b", r"\bplūd\w*\b", r"\bsustain\w*\b"],
    "Veselība": [r"\bvesel\w*\b", r"\bhealth\b", r"\bmedical\b", r"\bdoctor\w*\b", r"\bhospital\w*\b", r"\bslimn\w*\b", r"\bvīrus\w*\b", r"\bvirus\b", r"\bcovid\b"],
}

COMPILED_TOPIC_PATTERNS = {
    topic: [re.compile(pattern, re.IGNORECASE | re.UNICODE) for pattern in patterns]
    for topic, patterns in TOPIC_PATTERNS.items()
}

ALLOWED_SAVE_TAGS = {"later", "important"}
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 60
LOGIN_ATTEMPTS: Dict[str, int] = {}
LOGIN_LOCKED_UNTIL: Dict[str, datetime] = {}

app = Flask(__name__)
_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key and os.environ.get("FLASK_ENV") == "production":
    raise RuntimeError("SECRET_KEY must be set in production")
app.config["SECRET_KEY"] = _secret_key or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


class SecureUserStore:
    def __init__(self, data_file: str, key_file: str) -> None:
        self.data_file = data_file
        self.key_file = key_file
        self.fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        env_key = os.environ.get("USER_DATA_KEY")
        if env_key:
            return env_key.encode("utf-8")
        if os.environ.get("FLASK_ENV") == "production":
            raise RuntimeError("USER_DATA_KEY must be set in production")
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

    @staticmethod
    def _normalize_username(display_name: str) -> str:
        return " ".join(display_name.strip().casefold().split())

    def username_exists(self, display_name: str) -> bool:
        requested = self._normalize_username(display_name)
        if not requested:
            return False
        users = self._read()
        return any(self._normalize_username(str(user.get("display_name", ""))) == requested for user in users.values())

    def create_user(self, email: str, display_name: str, password: str) -> tuple[bool, str]:
        users = self._read()
        email_normalized = email.strip().lower()
        display_name_clean = " ".join(display_name.strip().split())
        if email_normalized in users:
            return False, "Šāds e-pasts jau ir reģistrēts."
        if self.username_exists(display_name_clean):
            return False, "Šāds lietotājvārds jau ir aizņemts. Izvēlies citu."

        salt = base64.urlsafe_b64encode(secrets.token_bytes(16)).decode("utf-8")
        users[email_normalized] = {
            "email": email_normalized,
            "display_name": display_name_clean,
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
    required = {"id", "email", "display_name", "created_at", "preferred_theme"}
    if required.issubset(columns):
        return

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            created_at TEXT NOT NULL,
            preferred_theme TEXT NOT NULL DEFAULT 'light'
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
                INSERT OR IGNORE INTO users_new (id, email, display_name, created_at, preferred_theme)
                VALUES (?, ?, ?, ?, ?)
                """,
                (legacy_id, email, display_name, now, "light"),
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
                display_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TEXT NOT NULL,
                preferred_theme TEXT NOT NULL DEFAULT 'light'
            )
            """
        )
        migrate_legacy_users_table(conn)
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "preferred_theme" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN preferred_theme TEXT NOT NULL DEFAULT 'light'")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_display_name_unique ON users(LOWER(display_name))"
        )
        article_columns = {row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
        if article_columns and "image_url" not in article_columns:
            conn.execute("ALTER TABLE articles ADD COLUMN image_url TEXT")
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
                location TEXT,
                image_url TEXT
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


def is_display_name_available(display_name: str, exclude_email: str | None = None) -> bool:
    cleaned = " ".join(display_name.strip().split())
    if not cleaned:
        return False
    with get_db() as conn:
        if exclude_email:
            row = conn.execute(
                "SELECT id FROM users WHERE LOWER(display_name) = LOWER(?) AND email != ?",
                (cleaned, exclude_email.strip().lower()),
            ).fetchone()
        else:
            row = conn.execute("SELECT id FROM users WHERE LOWER(display_name) = LOWER(?)", (cleaned,)).fetchone()
    return row is None


def get_or_create_user(email: str, display_name: str) -> int:
    email = email.strip().lower()
    display_name = " ".join(display_name.strip().split())
    with get_db() as conn:
        existing = conn.execute("SELECT id, preferred_theme FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            # Lietotājvārdu nemainām automātiski uz jau aizņemtu vērtību.
            if is_display_name_available(display_name, exclude_email=email):
                conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, existing["id"]))
            return int(existing["id"])
        cursor = conn.execute(
            "INSERT INTO users (email, display_name, created_at, preferred_theme) VALUES (?, ?, ?, ?)",
            (email, display_name, datetime.now(timezone.utc).isoformat(), "light"),
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


def is_safe_url(target: str | None) -> bool:
    if not target:
        return False
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in {"http", "https"} and host_url.netloc == redirect_url.netloc


def safe_redirect(default_endpoint: str = "index"):
    target = request.referrer
    if is_safe_url(target):
        return redirect(target)
    return redirect(url_for(default_endpoint))


def parse_positive_int(value: Any, field_name: str = "id") -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Nederīgs {field_name}.")
    if parsed <= 0:
        raise ValueError(f"Nederīgs {field_name}.")
    return parsed


def sanitize_text(value: str | None, max_length: int = 350) -> str:
    """Pārvērš RSS aprakstus drošā, īsā tekstā bez HTML.

    Daļa RSS avotu, īpaši The Guardian, NPR un daži Latvijas portāli, summary laukā
    atdod pilnu HTML fragmentu ar <p>, <a>, <ul> u.c. tagiem. Ja to saglabājam kā
    tekstu, lapā parādās "<p>..." un noformējums kļūst nesalasāms. Šeit noņemam
    skriptus/stilus, pārējos tagus un liekās atstarpes.
    """
    text = str(value or "")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", " ", text)
    text = re.sub(r"(?is)</p\s*>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            flash("Lūdzu, pieslēdzies, lai turpinātu.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def enforce_basic_request_security() -> None:
    session.permanent = True
    if request.method == "POST" and not app.config.get("TESTING"):
        sent_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not sent_token or not secrets.compare_digest(sent_token, session.get("csrf_token", "")):
            abort(400, description="Nederīgs CSRF marķieris.")


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


def normalize_text(text: str) -> str:
    return html.unescape(str(text or "")).lower()


def detect_topic(title: str, summary: str) -> str:
    """Nosaka tēmu ar precīzāku punktu skaitīšanu, nevis substring meklēšanu."""
    text = normalize_text(f"{title} {summary}")
    scores: Dict[str, int] = {}
    for topic, patterns in COMPILED_TOPIC_PATTERNS.items():
        if not patterns:
            continue
        score = 0
        for pattern in patterns:
            matches = pattern.findall(text)
            if matches:
                score += min(len(matches), 3)
        if score:
            scores[topic] = score

    if not scores:
        return "Cits"

    topic_order = {topic: index for index, topic in enumerate(COMPILED_TOPIC_PATTERNS)}
    return sorted(scores.items(), key=lambda item: (-item[1], topic_order.get(item[0], 999)))[0][0]


def extract_image_url(entry: Any) -> Optional[str]:
    media_content = entry.get("media_content") or []
    if media_content and isinstance(media_content, list):
        first = media_content[0]
        if isinstance(first, dict) and first.get("url"):
            return str(first["url"])

    media_thumbnail = entry.get("media_thumbnail") or []
    if media_thumbnail and isinstance(media_thumbnail, list):
        first = media_thumbnail[0]
        if isinstance(first, dict) and first.get("url"):
            return str(first["url"])

    enclosure = entry.get("enclosures") or []
    if enclosure and isinstance(enclosure, list):
        first = enclosure[0]
        if isinstance(first, dict) and first.get("href"):
            return str(first["href"])

    # Daži RSS avoti attēlu neliek media_* laukos, bet ievieto HTML aprakstā.
    html_fields = [
        entry.get("summary", ""),
        entry.get("description", ""),
        entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "",
    ]
    for fragment in html_fields:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(fragment), flags=re.I)
        if match:
            return html.unescape(match.group(1))

    return None


def parse_published(entry: Any) -> datetime:
    published = entry.get("published_parsed")
    if published:
        return datetime(*published[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def parse_feed(feed_url: str) -> Any:
    """Ielasa RSS/Atom ar ``requests`` un ``certifi`` sertifikātu komplektu.

    macOS Python instalācijās bieži parādās ``CERTIFICATE_VERIFY_FAILED``, ja
    Python nav piesaistīts sistēmas sertifikātiem. Iepriekšējā versija izmantoja
    ``urllib``/``feedparser.parse(URL)``, kas paļāvās uz lokālās Python vides
    sertifikātu iestatījumiem un tāpēc nestrādāja visiem RSS avotiem.

    Šeit HTTP lejupielāde notiek ar ``requests`` un ``certifi.where()``, tātad
    tiek izmantots uzticams CA sertifikātu fails no Python pakotnes. Tikai pēc
    tam saturs tiek padots ``feedparser``.
    """
    insecure_ssl = os.environ.get("ALLOW_INSECURE_SSL_FOR_FEEDS", "false").lower() == "true"
    try:
        response = requests.get(
            feed_url,
            headers=FEED_REQUEST_HEADERS,
            timeout=FEED_TIMEOUT_SECONDS,
            verify=False if insecure_ssl else certifi.where(),
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if not response.content.strip():
            raise ValueError("RSS response is empty")

        feed = feedparser.parse(response.content)
        setattr(feed, "source_url", feed_url)
        setattr(feed, "http_status", response.status_code)
        setattr(feed, "content_type", content_type)

        if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
            raise ValueError(f"RSS parse error: {getattr(feed, 'bozo_exception', 'unknown error')}")

        return feed
    except requests.exceptions.SSLError as exc:
        print(
            "RSS SSL certificate failed: "
            f"{feed_url} -> {exc}. "
            "Palaid `pip install -U certifi requests` vai macOS `Install Certificates.command`."
        )
    except requests.exceptions.RequestException as exc:
        print(f"RSS fetch failed: {feed_url} -> {exc}")
    except Exception as exc:
        print(f"RSS parse failed: {feed_url} -> {exc}")

    return {"entries": []}


def iter_feed_urls(feed_urls: Any) -> Iterable[str]:
    if isinstance(feed_urls, str):
        yield feed_urls
        return
    for feed_url in feed_urls:
        if feed_url:
            yield str(feed_url)


def normalize_article_url(feed_url: str, article_url: str) -> str:
    article_url = str(article_url or "").strip()
    if not article_url:
        return ""
    return urljoin(feed_url, article_url)


def upsert_articles() -> int:
    inserted = 0
    seen_urls: set[str] = set()
    with get_db() as conn:
        for source, feed_urls in DEFAULT_SOURCES.items():
            source_inserted = 0
            for feed_url in iter_feed_urls(feed_urls):
                feed = parse_feed(feed_url)
                entries = getattr(feed, "entries", []) or []
                for entry in entries[:30]:
                    title = sanitize_text(entry.get("title", "Bez virsraksta"), 300) or "Bez virsraksta"
                    summary = sanitize_text(
                        entry.get("summary") or entry.get("description") or entry.get("subtitle") or "",
                        700,
                    )
                    url = normalize_article_url(feed_url, entry.get("link", ""))
                    if not url or not urlparse(url).scheme.startswith("http") or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    published_at = parse_published(entry).isoformat()
                    topic = detect_topic(title, summary)
                    location = sanitize_text(entry.get("dc_coverage") or entry.get("location"), 100)
                    image_url = extract_image_url(entry)
                    try:
                        conn.execute(
                            """
                            INSERT INTO articles (title, summary, source, published_at, url, topic, location, image_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (title, summary, source, published_at, url, topic, location, image_url),
                        )
                        inserted += 1
                        source_inserted += 1
                    except sqlite3.IntegrityError:
                        continue
                if source_inserted >= 40:
                    break

        # Ja pilnīgi visi ārējie avoti atgrieza 0 ierakstus, ieliekam skaidru
        # diagnostikas ierakstu, nevis atstājam lietotāju ar tukšu lapu.
        if inserted == 0:
            for item in FALLBACK_ARTICLES:
                try:
                    conn.execute(
                        """
                        INSERT INTO articles (title, summary, source, published_at, url, topic, location, image_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["title"],
                            item["summary"],
                            item["source"],
                            datetime.now(timezone.utc).isoformat(),
                            item["url"],
                            item["topic"],
                            item.get("location"),
                            item.get("image_url"),
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass
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
            SELECT id, title, summary, source, published_at, url, topic, location, image_url
            FROM articles
            {where_clause}
            ORDER BY published_at DESC
            """,
            params,
        ).fetchall()



def fetch_articles_by_topic(user_id: int, topic: str) -> List[sqlite3.Row]:
    """Atgriež tikai precīzās tēmas rakstus salīdzinājuma skatam."""
    filters = ["topic = ?"]
    params: List[Any] = [topic]

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

    with get_db() as conn:
        return conn.execute(
            f"""
            SELECT id, title, summary, source, published_at, url, topic, location, image_url
            FROM articles
            WHERE {' AND '.join(filters)}
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
            SELECT a.id, a.title, a.summary, a.source, a.published_at, a.url, a.topic, a.location, a.image_url
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
            SELECT a.id, a.title, a.summary, a.source, a.published_at, a.url, a.topic, a.location, a.image_url, v.viewed_at
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


def get_user_profile_data(user_id: int) -> sqlite3.Row:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, email, display_name, created_at, preferred_theme FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise PermissionError("Lietotājs nav atrasts")
    return row


def set_user_theme(user_id: int, theme: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE users SET preferred_theme = ? WHERE id = ?", (theme, user_id))


def get_user_stats(user_id: int) -> Dict[str, int]:
    with get_db() as conn:
        stats = {
            "saved_later": conn.execute(
                "SELECT COUNT(*) AS c FROM saved_articles WHERE user_id = ? AND tag = 'later'",
                (user_id,),
            ).fetchone()["c"],
            "saved_important": conn.execute(
                "SELECT COUNT(*) AS c FROM saved_articles WHERE user_id = ? AND tag = 'important'",
                (user_id,),
            ).fetchone()["c"],
            "ignored_articles": conn.execute(
                "SELECT COUNT(*) AS c FROM ignored_articles WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"],
            "ignored_sources": conn.execute(
                "SELECT COUNT(*) AS c FROM ignored_sources WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"],
            "viewed_articles": conn.execute(
                "SELECT COUNT(*) AS c FROM viewed_articles WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"],
        }
    return {k: int(v) for k, v in stats.items()}


@app.context_processor
def inject_user() -> Dict[str, Any]:
    return {
        "logged_in": "user_email" in session,
        "display_name": session.get("display_name"),
        "user_email": session.get("user_email"),
        "preferred_theme": session.get("preferred_theme", "light"),
    }


@app.route("/")
def index() -> str:
    if "user_email" not in session:
        return redirect(url_for("login"))

    user_id = current_user_id()
    upsert_articles()
    query = sanitize_text(request.args.get("q", ""), 200)
    days_raw = request.args.get("days")
    source = sanitize_text(request.args.get("source"), 100) or None
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
@login_required
def compare() -> str:
    user_id = current_user_id()
    topic = sanitize_text(request.args.get("topic", ""), 200)
    articles = fetch_articles_by_topic(user_id, topic)
    grouped: Dict[str, List[sqlite3.Row]] = {}
    for article in articles:
        grouped.setdefault(article["source"], []).append(article)
    return render_template("compare.html", topic=topic, grouped=grouped)


@app.route("/saved")
@login_required
def saved() -> str:
    user_id = current_user_id()
    articles = get_saved_articles(user_id, "later")
    return render_template("saved.html", articles=articles, title="Lasīt vēlāk")


@app.route("/important")
@login_required
def important() -> str:
    user_id = current_user_id()
    articles = get_saved_articles(user_id, "important")
    return render_template("saved.html", articles=articles, title="Svarīgie")


@app.route("/history")
@login_required
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
        email = sanitize_text(request.form.get("email", ""), 254).lower()
        display_name = sanitize_text(request.form.get("display_name", ""), 80)
        password = request.form.get("password", "")
        password_repeat = request.form.get("password_repeat", "")

        if not email or "@" not in email:
            flash("Ievadi derīgu e-pastu.", "danger")
            return render_template("register.html")

        if not display_name:
            flash("Ievadi lietotājvārdu.", "danger")
            return render_template("register.html")

        if user_store.username_exists(display_name) or not is_display_name_available(display_name):
            flash("Šāds lietotājvārds jau ir aizņemts. Izvēlies citu.", "danger")
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
            user_id = get_or_create_user(email, display_name)
            session["preferred_theme"] = get_user_profile_data(user_id)["preferred_theme"]
            return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    if request.method == "POST":
        email = sanitize_text(request.form.get("email", ""), 254).lower()
        password = request.form.get("password", "")
        now = datetime.now(timezone.utc)

        lock_until = LOGIN_LOCKED_UNTIL.get(email)
        if lock_until and now < lock_until:
            remaining = max(1, int((lock_until - now).total_seconds()))
            flash(f"Pārāk daudz mēģinājumu. Mēģini vēlreiz pēc {remaining} sek.", "danger")
            return render_template("login.html")

        if lock_until and now >= lock_until:
            LOGIN_LOCKED_UNTIL.pop(email, None)
            LOGIN_ATTEMPTS.pop(email, None)

        user = user_store.authenticate(email, password)
        if user:
            LOGIN_ATTEMPTS.pop(email, None)
            LOGIN_LOCKED_UNTIL.pop(email, None)
            session["user_email"] = user["email"]
            session["display_name"] = user["display_name"]
            user_id = get_or_create_user(user["email"], user["display_name"])
            session["preferred_theme"] = get_user_profile_data(user_id)["preferred_theme"]
            return redirect(url_for("index"))

        failures = LOGIN_ATTEMPTS.get(email, 0) + 1
        LOGIN_ATTEMPTS[email] = failures
        if failures >= LOGIN_MAX_FAILURES:
            LOGIN_LOCKED_UNTIL[email] = now + timedelta(seconds=LOGIN_LOCKOUT_SECONDS)
            flash("Pārāk daudz neveiksmīgu mēģinājumu. Konts īslaicīgi bloķēts.", "danger")
            return render_template("login.html")

        flash("Nepareizs e-pasts vai parole.", "danger")
    return render_template("login.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile() -> str:
    user_id = current_user_id()
    allowed_themes = {"light", "dark", "barbie", "rave", "vacation", "shakespeare"}

    if request.method == "POST":
        display_name = sanitize_text(request.form.get("display_name", ""), 80)
        selected_theme = request.form.get("preferred_theme", "light")

        if selected_theme not in allowed_themes:
            selected_theme = "light"

        if display_name:
            with get_db() as conn:
                conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))
            session["display_name"] = display_name

        set_user_theme(user_id, selected_theme)
        session["preferred_theme"] = selected_theme
        flash("Profils atjaunināts.", "success")
        return redirect(url_for("profile"))

    profile_row = get_user_profile_data(user_id)
    stats = get_user_stats(user_id)
    return render_template("profile.html", profile=profile_row, stats=stats)


@app.route("/logout", methods=["POST"])
@login_required
def logout() -> str:
    session.clear()
    return redirect(url_for("login"))


@app.route("/refresh", methods=["POST"])
@login_required
def refresh() -> str:
    upsert_articles()
    return redirect(url_for("index"))


@app.route("/article/<int:article_id>")
@login_required
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
@login_required
def save_article() -> str:
    user_id = current_user_id()
    email = current_user_email()
    article_id = request.form.get("article_id")
    tag = request.form.get("tag")
    if not article_id or not tag:
        return safe_redirect("index")

    if tag not in ALLOWED_SAVE_TAGS:
        flash("Nederīgs saglabāšanas tips.", "warning")
        return safe_redirect("index")

    try:
        article_id_int = parse_positive_int(article_id, "raksta identifikators")
    except ValueError:
        flash("Nederīgs raksta identifikators.", "warning")
        return safe_redirect("index")

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
    return safe_redirect("index")


@app.route("/unsave", methods=["POST"])
@login_required
def unsave_article() -> str:
    user_id = current_user_id()
    email = current_user_email()
    article_id = request.form.get("article_id")
    tag = request.form.get("tag")
    if article_id and tag:
        if tag not in ALLOWED_SAVE_TAGS:
            flash("Nederīgs saglabāšanas tips.", "warning")
            return safe_redirect("index")
        try:
            article_id_int = parse_positive_int(article_id, "raksta identifikators")
        except ValueError:
            flash("Nederīgs raksta identifikators.", "warning")
            return safe_redirect("index")
        with get_db() as conn:
            conn.execute(
                "DELETE FROM saved_articles WHERE user_id = ? AND article_id = ? AND tag = ?",
                (user_id, article_id_int, tag),
            )
        if tag == "later":
            user_store.record_activity(email, "unsave_later", article_id_int)
        if tag == "important":
            user_store.record_activity(email, "unsave_important", article_id_int)
    return safe_redirect("index")


@app.route("/ignore-source", methods=["POST"])
@login_required
def ignore_source() -> str:
    user_id = current_user_id()
    email = current_user_email()
    source = sanitize_text(request.form.get("source"), 100)
    if source:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO ignored_sources (user_id, source) VALUES (?, ?)",
                (user_id, source),
            )
        user_store.record_activity(email, "ignore_source", source)
    return safe_redirect("index")


@app.route("/ignore-article", methods=["POST"])
@login_required
def ignore_article() -> str:
    user_id = current_user_id()
    email = current_user_email()
    article_id = request.form.get("article_id")
    if article_id:
        try:
            article_id_int = parse_positive_int(article_id, "raksta identifikators")
        except ValueError:
            flash("Nederīgs raksta identifikators.", "warning")
            return safe_redirect("index")
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO ignored_articles (user_id, article_id) VALUES (?, ?)",
                (user_id, article_id_int),
            )
        user_store.record_activity(email, "ignore_article", article_id_int)
    return safe_redirect("index")


@app.route("/save-search", methods=["POST"])
@login_required
def save_search() -> str:
    user_id = current_user_id()
    query = sanitize_text(request.form.get("query", ""), 200)
    if query:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO saved_searches (user_id, query, created_at) VALUES (?, ?, ?)",
                (user_id, query, datetime.now(timezone.utc).isoformat()),
            )
    return safe_redirect("index")


@app.route("/remove-saved-search", methods=["POST"])
@login_required
def remove_saved_search() -> str:
    user_id = current_user_id()
    search_id = request.form.get("search_id")
    if search_id:
        try:
            search_id_int = parse_positive_int(search_id, "meklēšanas identifikators")
        except ValueError:
            flash("Nederīgs meklēšanas identifikators.", "warning")
            return safe_redirect("history")
        with get_db() as conn:
            conn.execute(
                "DELETE FROM saved_searches WHERE id = ? AND user_id = ?",
                (search_id_int, user_id),
            )
    return safe_redirect("history")


def cleanup_existing_article_summaries() -> None:
    """Notīra vecos RSS HTML fragmentus un pārrēķina tēmas esošajā data.db."""
    with get_db() as conn:
        rows = conn.execute("SELECT id, title, summary, topic FROM articles").fetchall()
        for row in rows:
            cleaned = sanitize_text(row["summary"], 700)
            topic = detect_topic(row["title"], cleaned)
            if cleaned != (row["summary"] or "") or topic != (row["topic"] or ""):
                conn.execute(
                    "UPDATE articles SET summary = ?, topic = ? WHERE id = ?",
                    (cleaned, topic, row["id"]),
                )


def ensure_seed_data() -> None:
    init_db()
    cleanup_existing_article_summaries()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) as total FROM articles").fetchone()["total"]
    if count == 0:
        upsert_articles()


if __name__ == "__main__":
    ensure_seed_data()
    app.run(debug=os.environ.get("FLASK_ENV") == "development")
