"""Authentication for ss-workspaceMonitor v2.

v1's "token" was the literal string ``email:role`` and login took an
email with no password, so any client could forge an Admin token.
v2 issues a signed JWT after verifying a bcrypt password hash, and
every request re-checks the user against the database so a revoked,
suspended, or role-changed account stops working immediately.

The signing secret comes from ``WORKSPACE_MONITOR_SECRET_KEY``. When
it is unset (local demo use) an ephemeral per-process secret is
generated and a warning is logged: tokens then stop working on
restart, which is the safe default. Never ship the demo seed data
with a production secret, and never commit a real secret.
"""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
import jwt

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=8)


class Role(str, Enum):
    """The only role values stored in the database and accepted in tokens."""

    ADMIN = "Admin"
    SUPERVISOR = "Supervisor"
    STANDARD = "Standard"

    @classmethod
    def normalize(cls, value: str | None) -> "Role":
        """Accept any casing of a known role; anything else is Standard.

        v1 compared roles case-sensitively in different places
        (``"admin"`` in some files, ``"Admin"`` in others), which is
        how the admin-only views silently stopped working.
        """
        if value is None:
            return cls.STANDARD
        if isinstance(value, cls):
            return value
        for role in cls:
            # Compare against .value, not str(value): str(Role.ADMIN)
            # is "Role.ADMIN", which would never match "Admin".
            if role.value.lower() == str(value).lower():
                return role
        return cls.STANDARD


def is_privileged(role: Role | str) -> bool:
    """True for Admin and Supervisor: they may read other users' rows."""
    return Role.normalize(role) in (Role.ADMIN, Role.SUPERVISOR)


def _load_secret() -> str:
    secret = os.environ.get("WORKSPACE_MONITOR_SECRET_KEY")
    if secret:
        return secret
    logger.warning(
        "WORKSPACE_MONITOR_SECRET_KEY is not set; using an ephemeral "
        "per-process secret. Set the variable for stable logins."
    )
    return secrets.token_hex(32)


SECRET_KEY = _load_secret()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(email: str, role: Role) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "role": role.value,
        # Per-token id (v2.1): enables server-side revocation on
        # logout — without it, "logout" only cleared the frontend
        # and the token stayed valid until expiry.
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode a token or raise jwt.PyJWTError (expired, forged, malformed)."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
