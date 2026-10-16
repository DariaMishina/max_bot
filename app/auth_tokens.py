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


def create_access_token(user_id: uuid.UUID, auth_version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "auth_version": auth_version,
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


async def create_refresh_token(user_id: uuid.UUID, auth_version: int = 0) -> str:
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_refresh_token(raw)
    expires_at = datetime.now() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    await AppDatabase.execute(
        """
        INSERT INTO app_refresh_tokens (user_id, token_hash, expires_at, auth_version)
        VALUES ($1, $2, $3, $4)
        """,
        user_id,
        token_hash,
        expires_at,
        auth_version,
    )
    return raw


async def verify_refresh_token(raw: str) -> Optional[uuid.UUID]:
    token_hash = _hash_refresh_token(raw)
    row = await AppDatabase.fetch_one(
        """
        SELECT t.user_id, t.expires_at, t.revoked_at
        FROM app_refresh_tokens t JOIN app_users u ON u.user_id=t.user_id
        WHERE t.token_hash = $1 AND t.auth_version=u.auth_version
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


async def rotate_refresh_token(raw: str) -> Dict[str, Any]:
    from app.account_auth import AccountAuthError
    # Atomic consume prevents replay. Epoch comparison also covers a concurrent reset.
    row = await AppDatabase.fetch_one(
        """UPDATE app_refresh_tokens t SET revoked_at=NOW() FROM app_users u
        WHERE t.token_hash=$1 AND t.user_id=u.user_id AND t.auth_version=u.auth_version
          AND t.revoked_at IS NULL AND t.expires_at>NOW()
        RETURNING t.user_id,t.auth_version""", _hash_refresh_token(raw),
    )
    if not row:
        raise AccountAuthError("invalid_token", "Недействительный refresh_token", 401)
    return await issue_token_pair(row["user_id"], expected_version=row["auth_version"])


def token_auth_version(token: str) -> int:
    try:
        return int(json.loads(_b64_decode(token.rsplit(".", 1)[0])).get("auth_version", 0))
    except (ValueError, TypeError, KeyError):
        return -1


async def issue_token_pair(user_id: uuid.UUID, expected_version=None) -> Dict[str, Any]:
    version = await AppDatabase.fetch_one("SELECT auth_version FROM app_users WHERE user_id=$1", user_id)
    if version is None or (expected_version is not None and version["auth_version"] != expected_version):
        from app.account_auth import AccountAuthError
        raise AccountAuthError("session_revoked", "Войдите заново", 401)
    return {
        "access_token": create_access_token(user_id, version["auth_version"]),
        "refresh_token": await create_refresh_token(user_id, version["auth_version"]),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL_SEC,
        "user_id": str(user_id),
    }
