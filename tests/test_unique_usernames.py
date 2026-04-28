import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("USER_DATA_KEY", "dDlsDpt00fRqonsA9wOhvcpuTa6sZwdeZGephG7YJaY=")


def test_secure_user_store_rejects_duplicate_display_names(tmp_path):
    from app import SecureUserStore

    store = SecureUserStore(str(tmp_path / "users.enc"), str(tmp_path / "users.key"))

    created, _ = store.create_user("first@example.com", "Karlis", "password123")
    assert created is True

    created, message = store.create_user("second@example.com", "  karlis  ", "password123")
    assert created is False
    assert "lietotājvārds" in message.lower()
