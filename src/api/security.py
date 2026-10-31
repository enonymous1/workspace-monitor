"""Request authentication: resolves a Bearer JWT to a typed identity.

v2.0 passed auth around as a plain ``dict`` (``auth["email"]`` /
``auth["role"]``), so a typo'd key failed at runtime on one
endpoint. v2.1 uses a frozen ``AuthContext`` dataclass instead:
handlers get attribute access, mypy can check it, and identity
cannot be mutated mid-request.

This module also enforces token revocation (v2.1): ``POST
/api/logout`` inserts the token's ``jti`` into ``revoked_tokens``,
and every request checks that table. A token issued before v2.1
has no ``jti``; such tokens are rejected, because they cannot be
revoked — they expire within 8 hours of the upgrade at most.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Header, HTTPException

from api.auth import Role, decode_access_token
from api.database import get_db_connection


@dataclass(frozen=True)
class AuthContext:
    """A verified caller identity, resolved from the database."""

    email: str
    role: Role


def get_current_user(authorization: Optional[str] = Header(None)) -> AuthContext:
    """Validate a Bearer JWT and return the caller's AuthContext.

    The role comes from the database, not the token payload, so a
    role change or suspension takes effect without re-login.
    Revoked tokens (logout) and pre-v2.1 tokens without a ``jti``
    are rejected.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    try:
        payload = decode_access_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    email = payload.get("sub")
    jti = payload.get("jti")
    if not email or not jti:
        raise HTTPException(status_code=401, detail="Invalid token")
    conn = get_db_connection()
    try:
        revoked = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
        if revoked:
            raise HTTPException(status_code=401, detail="Token revoked")
        row = conn.execute(
            "SELECT role, is_suspended FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()
    if row is None or row["is_suspended"]:
        raise HTTPException(status_code=401, detail="Invalid or suspended user")
    return AuthContext(email=email, role=Role.normalize(row["role"]))


# Backwards-compatible alias for any code still importing the v2.0 name.
# New code should use get_current_user.
verify_token = get_current_user
