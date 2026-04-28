from __future__ import annotations

import os
import secrets
from datetime import timedelta

from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key and os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in production")

    app.config.update(
        SECRET_KEY=secret_key or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    )
    return app
