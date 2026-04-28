from __future__ import annotations

import os
from cryptography.fernet import Fernet


def load_user_data_key(key_file: str) -> bytes:
    env_key = os.environ.get("USER_DATA_KEY")
    if env_key:
        return env_key.encode("utf-8")
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("USER_DATA_KEY must be set in production")
    if os.path.exists(key_file):
        with open(key_file, "rb") as file:
            return file.read().strip()
    key = Fernet.generate_key()
    with open(key_file, "wb") as file:
        file.write(key)
    return key
