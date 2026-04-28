from __future__ import annotations

import secrets
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import abort, flash, redirect, request, session, url_for


def is_safe_url(target: str | None) -> bool:
    if not target:
        return False
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in {"http", "https"} and host_url.netloc == redirect_url.netloc


def safe_redirect(default_endpoint: str = "index"):
    return redirect(request.referrer) if is_safe_url(request.referrer) else redirect(url_for(default_endpoint))


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


def validate_csrf() -> None:
    sent_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not sent_token or not secrets.compare_digest(sent_token, session.get("csrf_token", "")):
        abort(400, description="Nederīgs CSRF marķieris.")
