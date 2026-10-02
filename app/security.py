from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.config import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    role: str | None = None,
) -> str:
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "exp": expires_at,
    }
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def create_access_token(username: str, role: str = "member") -> str:
    return create_token(
        username,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        role,
    )


def create_refresh_token(username: str, role: str = "member") -> str:
    return create_token(
        username,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
        role,
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise ValueError("Invalid token type")
    return payload
