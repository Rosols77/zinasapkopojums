from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as news_app


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_path = Path(tempfile.mkdtemp())

        self.original_db_path = news_app.DB_PATH
        self.original_users_data_file = news_app.USERS_DATA_FILE
        self.original_users_key_file = news_app.USERS_KEY_FILE
        self.original_user_store = news_app.user_store

        news_app.DB_PATH = str(self.temp_path / "data.db")
        news_app.USERS_DATA_FILE = str(self.temp_path / "users_secure.enc")
        news_app.USERS_KEY_FILE = str(self.temp_path / "users_secure.key")
        news_app.user_store = news_app.SecureUserStore(news_app.USERS_DATA_FILE, news_app.USERS_KEY_FILE)

        news_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        news_app.init_db()
        self.client = news_app.app.test_client()

    def tearDown(self) -> None:
        news_app.DB_PATH = self.original_db_path
        news_app.USERS_DATA_FILE = self.original_users_data_file
        news_app.USERS_KEY_FILE = self.original_users_key_file
        news_app.user_store = self.original_user_store

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(news_app.DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()

    def _login_session(self, email: str = "test@example.com", display_name: str = "Tester") -> int:
        user_id = news_app.get_or_create_user(email, display_name)
        with self.client.session_transaction() as session:
            session["user_email"] = email
            session["display_name"] = display_name
            session["preferred_theme"] = "light"
        return user_id

    def _seed_article(self, title: str, source: str, url: str, summary: str = "Summary") -> int:
        with self._db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO articles (title, summary, source, published_at, url, topic, location, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, summary, source, datetime.now(timezone.utc).isoformat(), url, "AI", None, None),
            )
            return int(cursor.lastrowid)

    def test_index_redirects_to_login_when_not_authenticated(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_register_login_and_load_index(self) -> None:
        register_response = self.client.post(
            "/register",
            data={
                "email": "alice@example.com",
                "display_name": "Alice",
                "password": "strongpass1",
                "password_repeat": "strongpass1",
            },
        )

        self.assertEqual(register_response.status_code, 302)
        self.assertTrue(register_response.headers["Location"].endswith("/"))

        logout_response = self.client.post("/logout")
        self.assertEqual(logout_response.status_code, 302)

        login_response = self.client.post(
            "/login",
            data={"email": "alice@example.com", "password": "strongpass1"},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertTrue(login_response.headers["Location"].endswith("/"))

        with patch("app.upsert_articles", return_value=0):
            index_response = self.client.get("/")

        self.assertEqual(index_response.status_code, 200)

    def test_refresh_ingests_and_deduplicates_articles(self) -> None:
        self._login_session()

        fake_feed = SimpleNamespace(
            entries=[
                {
                    "title": "First",
                    "summary": "A",
                    "link": "https://example.com/shared",
                    "published_parsed": datetime(2026, 1, 1, tzinfo=timezone.utc).timetuple(),
                },
                {
                    "title": "Second duplicate link",
                    "summary": "B",
                    "link": "https://example.com/shared",
                    "published_parsed": datetime(2026, 1, 1, tzinfo=timezone.utc).timetuple(),
                },
            ]
        )

        with patch("app.DEFAULT_SOURCES", {"Mock": "https://example.com/rss"}), patch(
            "app.feedparser.parse", return_value=fake_feed
        ):
            response = self.client.post("/refresh")

        self.assertEqual(response.status_code, 302)

        with self._db() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
        self.assertEqual(int(count), 1)

    def test_save_and_unsave_article_updates_saved_articles(self) -> None:
        user_id = self._login_session()
        article_id = self._seed_article("Save me", "BBC", "https://example.com/save")

        save_response = self.client.post("/save", data={"article_id": article_id, "tag": "later"})
        self.assertEqual(save_response.status_code, 302)

        with self._db() as conn:
            saved_count = conn.execute(
                "SELECT COUNT(*) AS c FROM saved_articles WHERE user_id = ? AND article_id = ? AND tag = 'later'",
                (user_id, article_id),
            ).fetchone()["c"]
        self.assertEqual(int(saved_count), 1)

        unsave_response = self.client.post("/unsave", data={"article_id": article_id, "tag": "later"})
        self.assertEqual(unsave_response.status_code, 302)

        with self._db() as conn:
            saved_count_after = conn.execute(
                "SELECT COUNT(*) AS c FROM saved_articles WHERE user_id = ? AND article_id = ? AND tag = 'later'",
                (user_id, article_id),
            ).fetchone()["c"]
        self.assertEqual(int(saved_count_after), 0)

    def test_ignore_source_hides_source_articles_from_index(self) -> None:
        self._login_session()
        self._seed_article("Alpha News", "SourceA", "https://example.com/a")
        self._seed_article("Beta News", "SourceB", "https://example.com/b")

        ignore_response = self.client.post("/ignore-source", data={"source": "SourceA"})
        self.assertEqual(ignore_response.status_code, 302)

        with patch("app.upsert_articles", return_value=0):
            index_response = self.client.get("/")

        body = index_response.data.decode("utf-8")
        self.assertNotIn("Alpha News", body)
        self.assertIn("Beta News", body)

    def test_ignore_article_hides_specific_article_from_index(self) -> None:
        self._login_session()
        article_id = self._seed_article("Hide This One", "SourceA", "https://example.com/hide")
        self._seed_article("Keep This One", "SourceA", "https://example.com/keep")

        ignore_response = self.client.post("/ignore-article", data={"article_id": article_id})
        self.assertEqual(ignore_response.status_code, 302)

        with patch("app.upsert_articles", return_value=0):
            index_response = self.client.get("/")

        body = index_response.data.decode("utf-8")
        self.assertNotIn("Hide This One", body)
        self.assertIn("Keep This One", body)

    def test_open_article_redirects_and_marks_viewed(self) -> None:
        user_id = self._login_session()
        article_id = self._seed_article("Read Full", "SourceA", "https://example.com/full")

        response = self.client.get(f"/article/{article_id}")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://example.com/full")

        with self._db() as conn:
            viewed_count = conn.execute(
                "SELECT COUNT(*) AS c FROM viewed_articles WHERE user_id = ? AND article_id = ?",
                (user_id, article_id),
            ).fetchone()["c"]
        self.assertEqual(int(viewed_count), 1)

    def test_search_history_and_saved_search_lifecycle(self) -> None:
        user_id = self._login_session()
        self._seed_article("Climate Update", "SourceA", "https://example.com/climate", summary="climate summary")

        with patch("app.upsert_articles", return_value=0):
            index_response = self.client.get("/?q=climate")
        self.assertEqual(index_response.status_code, 200)

        with self._db() as conn:
            history_count = conn.execute(
                "SELECT COUNT(*) AS c FROM search_history WHERE user_id = ? AND query = ?",
                (user_id, "climate"),
            ).fetchone()["c"]
        self.assertGreaterEqual(int(history_count), 1)

        save_response = self.client.post("/save-search", data={"query": "climate"})
        self.assertEqual(save_response.status_code, 302)

        with self._db() as conn:
            saved_row = conn.execute(
                "SELECT id FROM saved_searches WHERE user_id = ? AND query = ? ORDER BY id DESC LIMIT 1",
                (user_id, "climate"),
            ).fetchone()
        self.assertIsNotNone(saved_row)

        remove_response = self.client.post("/remove-saved-search", data={"search_id": int(saved_row["id"])})
        self.assertEqual(remove_response.status_code, 302)

        with self._db() as conn:
            remaining = conn.execute(
                "SELECT COUNT(*) AS c FROM saved_searches WHERE user_id = ? AND query = ?",
                (user_id, "climate"),
            ).fetchone()["c"]
        self.assertEqual(int(remaining), 0)

    def test_profile_update_persists_display_name_and_theme(self) -> None:
        user_id = self._login_session(email="profile@example.com", display_name="Before")

        response = self.client.post(
            "/profile",
            data={"display_name": "After", "preferred_theme": "rave"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/profile", response.headers["Location"])

        with self._db() as conn:
            row = conn.execute(
                "SELECT display_name, preferred_theme FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

        self.assertEqual(row["display_name"], "After")
        self.assertEqual(row["preferred_theme"], "rave")


if __name__ == "__main__":
    unittest.main()