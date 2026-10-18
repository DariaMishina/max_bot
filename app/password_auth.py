"""Ordinary username/password accounts, with persistent throttling."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets

from app.account_auth import AccountAuthError, _confirm_identity_with_conn, signal_hash
from app.database import AppDatabase

_HASH_SLOTS = asyncio.Semaphore(2)


def normalize_login(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_.@-]{3,64}", value.strip()):
        raise AccountAuthError(
            "invalid_login",
            "Логин: 3–64 латинские буквы, цифры или символы _ . @ -",
        )
    return value.strip().lower()


def validate_password(value: object) -> str:
    if not isinstance(value, str) or not 8 <= len(value) <= 128:
        raise AccountAuthError("invalid_password", "Пароль должен содержать от 8 до 128 символов")
    return value


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=131072, r=8, p=1,
                            maxmem=256 * 1024 * 1024, dklen=32)
    return f"scrypt-v1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, digest = encoded.split("$")
        if algorithm != "scrypt-v1" or len(salt) != 32 or len(digest) != 64:
            return False
        return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)), encoded)
    except (ValueError, TypeError):
        return False


async def _throttle(login: str, ip: str | None, registering: bool) -> None:
    # Consume limits outside the credential transaction: failed attempts persist.
    action = "register" if registering else "login"
    buckets = sorted([
        (signal_hash(f"password-{action}-ip", ip or "unknown"), 5 if registering else 60),
        (signal_hash(f"password-{action}-login", login), 10),
    ])
    pool = await AppDatabase.get_pool()
    blocked = False
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM app_password_limits WHERE expires_at <= NOW()")
            for bucket, maximum in buckets:
                attempts = await conn.fetchval(
                    """INSERT INTO app_password_limits (bucket, attempts, expires_at)
                    VALUES ($1, 1, NOW() + INTERVAL '15 minutes')
                    ON CONFLICT (bucket) DO UPDATE SET
                      attempts = CASE WHEN app_password_limits.expires_at <= NOW() THEN 1
                                      ELSE app_password_limits.attempts + 1 END,
                      expires_at = CASE WHEN app_password_limits.expires_at <= NOW()
                                        THEN NOW() + INTERVAL '15 minutes'
                                        ELSE app_password_limits.expires_at END
                    RETURNING attempts""", bucket,
                )
                blocked = blocked or attempts > maximum
    if blocked:
        raise AccountAuthError("password_rate_limit", "Слишком много попыток. Попробуйте через 15 минут.", 429)


async def authenticate_password(login: object, password: object, *, registering: bool,
                                ip: str | None, device_signal: object = None) -> dict:
    login = normalize_login(login)
    password = validate_password(password)
    await _throttle(login, ip, registering)
    if registering:
        async with _HASH_SLOTS:
            encoded = await asyncio.to_thread(hash_password, password)
        pool = await AppDatabase.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Same lock as identity creation; serialize competing registrations.
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"password:{login}")
                exists = await conn.fetchval("SELECT 1 FROM app_password_credentials WHERE login = $1", login)
                if exists:
                    raise AccountAuthError("login_taken", "Этот логин уже занят", 409)
                result = await _confirm_identity_with_conn(
                    conn, "password", login, login, current_user_id=None, device_signal=device_signal,
                )
                await conn.execute(
                    "INSERT INTO app_password_credentials (login, user_id, password_hash) VALUES ($1, $2, $3)",
                    login, result["user_id"], encoded,
                )
        return result

    row = await AppDatabase.fetch_one(
        "SELECT c.user_id, c.password_hash, u.auth_version FROM app_password_credentials c JOIN app_users u ON u.user_id=c.user_id WHERE c.login = $1", login,
    )
    # Unknown logins perform the same expensive calculation as an incorrect password.
    encoded = row["password_hash"] if row else "scrypt-v1$" + "00" * 16 + "$" + "00" * 32
    async with _HASH_SLOTS:
        valid = await asyncio.to_thread(verify_password, password, encoded)
    if not row or not valid:
        raise AccountAuthError("invalid_credentials", "Неверный логин или пароль", 401)
    await AppDatabase.execute("UPDATE app_users SET last_active_at = NOW() WHERE user_id = $1", row["user_id"])
    return {"user_id": row["user_id"], "trial_granted": 0, "auth_version": row["auth_version"]}
