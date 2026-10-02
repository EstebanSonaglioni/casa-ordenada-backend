from datetime import timedelta

import jwt
import pytest

from app.security import (
    create_access_token,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings


def test_password_is_hashed_and_can_be_verified() -> None:
    hashed = hash_password("a-password")

    assert hashed != "a-password"
    assert verify_password("a-password", hashed)
    assert not verify_password("another-password", hashed)


def test_refresh_decoder_rejects_access_tokens() -> None:
    access_token = create_token("user", "access", timedelta(minutes=5))

    with pytest.raises(ValueError, match="Invalid token type"):
        decode_token(access_token, "refresh")


def test_access_token_contains_user_role() -> None:
    token = create_access_token("user", "admin")

    assert decode_token(token, "access")["role"] == "admin"


def test_decoder_rejects_expired_tokens() -> None:
    expired_token = jwt.encode(
        {"sub": "user", "type": "refresh", "exp": 0},
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token, "refresh")
