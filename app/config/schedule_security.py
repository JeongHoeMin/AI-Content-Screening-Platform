from __future__ import annotations

import hashlib
import hmac
import os
import time
from base64 import urlsafe_b64encode

from app.config.errors import ConfigurationError

SCHEDULE_SESSION_COOKIE: str = "schedule_settings_session"
_SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 8


def load_schedule_settings_password() -> str:
    """Load the server-only password for the schedule settings session."""
    password: str = os.environ.get("SCHEDULE_SETTINGS_PASSWORD", "").strip()
    if len(password) < 32:
        raise ConfigurationError(
            "SCHEDULE_SETTINGS_PASSWORD must be configured with at least 32 characters"
        )
    return password


def schedule_cookie_uses_secure_transport() -> bool:
    """Keep the session cookie HTTPS-only unless an explicit local override is set."""
    value: str = os.environ.get("SCHEDULE_COOKIE_SECURE", "true").strip().lower()
    return value not in {"0", "false", "no"}


def passwords_match(candidate: str, expected: str) -> bool:
    """Compare unlogged passwords without timing differences."""
    return hmac.compare_digest(candidate, expected)


def issue_schedule_session(password: str, now: int | None = None) -> str:
    """Create a short-lived signed session; password rotation invalidates it."""
    expires_at: int = (now if now is not None else int(time.time())) + _SESSION_MAX_AGE_SECONDS
    payload: bytes = str(expires_at).encode("ascii")
    signature: bytes = hmac.new(password.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{expires_at}.{urlsafe_b64encode(signature).decode('ascii').rstrip('=')}"


def has_valid_schedule_session(
    session: str | None,
    password: str,
    now: int | None = None,
) -> bool:
    """Verify expiry and signature without exposing why authentication failed."""
    if not session:
        return False
    expires_text, separator, signature_text = session.partition(".")
    if not separator or not expires_text.isdecimal() or not signature_text:
        return False
    expires_at: int = int(expires_text)
    if expires_at < (now if now is not None else int(time.time())):
        return False
    expected: str = issue_schedule_session(
        password,
        now=expires_at - _SESSION_MAX_AGE_SECONDS,
    )
    return hmac.compare_digest(session, expected)
