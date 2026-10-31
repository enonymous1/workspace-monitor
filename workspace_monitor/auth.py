"""Authentication for workspace-monitor (Flask build).

Passwords are bcrypt hashes. Sessions are server-side Flask
sessions (signed cookie holding only the email); every request
re-checks the user against the database, so a suspended or
role-changed account stops working without waiting for a
session to expire, and logout simply clears the session —
no token revocation table is needed, unlike the v2 JWT build.

The session secret comes from ``WORKSPACE_MONITOR_SECRET_KEY``.
When it is unset (local demo use) an ephemeral per-process
secret is generated and a warning is logged. Never ship the
demo seed data with a production secret, and never commit a
real secret.
"""

from __future__ import annotations

import logging
import os
import secrets
from enum import Enum

import bcrypt

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """The only role values stored in the database."""

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
