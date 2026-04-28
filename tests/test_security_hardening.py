from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import app as news_app


class SecurityHardeningTests(unittest.TestCase):
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

    def _login(self) -> None:
        with self.client.session_transaction() as session:
            session["user_email"] = "security@example.com"
            session["display_name"] = "Security User"
            session["preferred_theme"] = "light"

    def test_protected_routes_redirect_instead_of_500(self) -> None:
        for path in ["/compare", "/saved", "/important", "/history", "/profile"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_invalid_article_ids_return_safe_redirects(self) -> None:
        self._login()
        for path in ["/save", "/unsave", "/ignore-article"]:
            with self.subTest(path=path):
                response = self.client.post(path, data={"article_id": "not-a-number", "tag": "later"})
                self.assertEqual(response.status_code, 302)

    def test_invalid_saved_search_id_returns_safe_redirect(self) -> None:
        self._login()
        response = self.client.post("/remove-saved-search", data={"search_id": "1 OR 1=1"})
        self.assertEqual(response.status_code, 302)

    def test_csrf_blocks_post_when_not_testing(self) -> None:
        news_app.app.config["TESTING"] = False
        try:
            response = self.client.post("/logout")
            self.assertEqual(response.status_code, 400)
        finally:
            news_app.app.config["TESTING"] = True


if __name__ == "__main__":
    unittest.main()
