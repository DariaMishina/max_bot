"""JWT access-токены и refresh-токены для гостей приложения."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from app.config import app_config
from app.database import AppDatabase

ACCESS_TOKEN_TTL_SEC = 60 * 60  # 1 час
REFRESH_TOKEN_TTL_DAYS = 30


def _secret() -> str:
    return app_config.app_jwt_secret.get_secret_value()


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_access_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": int(time.time()) + ACCESS_TOKEN_TTL_SEC,
    }
    body = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_access_token(token: str) -> Optional[uuid.UUID]:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64_decode(body))
        if payload.get("type") != "access":
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return uuid.UUID(payload["sub"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def _hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh_token(user_id: uuid.UUID) -> str:
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_refresh_token(raw)
    expires_at = datetime.now() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    await AppDatabase.execute(
        """
        INSERT INTO app_refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, $3)
        """,
        user_id,
        token_hash,
        expires_at,
    )
    return raw


async def verify_refresh_token(raw: str) -> Optional[uuid.UUID]:
    token_hash = _hash_refresh_token(raw)
    row = await AppDatabase.fetch_one(
        """
        SELECT user_id, expires_at, revoked_at
        FROM app_refresh_tokens
        WHERE token_hash = $1
        """,
        token_hash,
    )
    if not row or row["revoked_at"]:
        return None
    if row["expires_at"] < datetime.now():
        return None
    return row["user_id"]


async def revoke_refresh_token(raw: str) -> None:
    token_hash = _hash_refresh_token(raw)
    await AppDatabase.execute(
        """
        UPDATE app_refresh_tokens
        SET revoked_at = NOW()
        WHERE token_hash = $1 AND revoked_at IS NULL
        """,
        token_hash,
    )


async def issue_token_pair(user_id: uuid.UUID) -> Dict[str, Any]:
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": await create_refresh_token(user_id),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL_SEC,
        "user_id": str(user_id),
    }
