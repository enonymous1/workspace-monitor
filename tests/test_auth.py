"""Unit tests for api.auth: hashing, roles, and JWT round-trips."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from api.auth import (
    ALGORITHM,
    SECRET_KEY,
    Role,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("correct horse")
    assert verify_password("correct horse", hashed) is True
    assert verify_password("wrong horse", hashed) is False
    assert verify_password("anything", None) is False


def test_role_normalize_is_case_insensitive():
    # Regression: normalize() once re-stringified a Role enum
    # ("Role.ADMIN") and demoted every privileged user to Standard.
    assert Role.normalize(Role.ADMIN) == Role.ADMIN
    assert Role.normalize("admin") == Role.ADMIN
    assert Role.normalize("ADMIN") == Role.ADMIN
    assert Role.normalize("Supervisor") == Role.SUPERVISOR
    assert Role.normalize("bogus") == Role.STANDARD
    assert Role.normalize(None) == Role.STANDARD


def test_token_roundtrip():
    token = create_access_token("admin@example.com", Role.ADMIN)
    payload = decode_access_token(token)
    assert payload["sub"] == "admin@example.com"
    assert payload["role"] == "Admin"


def test_forged_v1_style_token_fails():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("admin@example.com:Admin")


def test_expired_token_fails():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "Admin",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
