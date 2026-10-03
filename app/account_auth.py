"""Confirmed account authentication for the Android app."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
import smtplib
import ssl
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any, Dict, Optional

from app.config import app_config
from app.database import AppDatabase

EMAIL_CODE_TTL_MINUTES = 10
EMAIL_CODE_RESEND_SECONDS = 60
EMAIL_CODE_MAX_ATTEMPTS = 5
TRIAL_DIVINATIONS = 3
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AccountAuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def normalize_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 320 or not _EMAIL_RE.fullmatch(email):
        raise AccountAuthError("invalid_email", "Проверьте адрес электронной почты")
    return email


def _hmac(value: str) -> str:
    secret = app_config.app_jwt_secret.get_secret_value().encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def code_hash(email: str, code: str) -> str:
    return _hmac(f"email-code:{email}:{code}")


def signal_hash(kind: str, value: Optional[str]) -> Optional[str]:
    cleaned = str(value or "").strip()
    return _hmac(f"{kind}:{cleaned}") if cleaned else None


def mask_email(email: str) -> str:
    local, domain = email.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'•' * max(2, len(local) - len(visible))}@{domain}"


async def create_email_challenge(email: str, *, ip: Optional[str], device_signal: Optional[str]) -> tuple[int, str]:
    """Persist a single-use challenge after enforcing email/IP/device limits."""
    email = normalize_email(email)
    ip_hash = signal_hash("ip", ip)
    device_hash = signal_hash("device", device_signal)
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            latest = await conn.fetchrow(
                "SELECT created_at FROM app_email_codes WHERE email = $1 ORDER BY created_at DESC LIMIT 1 FOR UPDATE",
                email,
            )
            now = datetime.now()
            if latest:
                elapsed = (now - latest["created_at"]).total_seconds()
                if elapsed < EMAIL_CODE_RESEND_SECONDS:
                    raise AccountAuthError(
                        "email_cooldown",
                        f"Новый код можно запросить через {int(EMAIL_CODE_RESEND_SECONDS - elapsed) + 1} сек.",
                        429,
                    )
            email_count = await conn.fetchval(
                "SELECT COUNT(*) FROM app_email_codes WHERE email = $1 AND created_at > NOW() - INTERVAL '1 hour'",
                email,
            )
            ip_count = 0 if not ip_hash else await conn.fetchval(
                "SELECT COUNT(*) FROM app_email_codes WHERE request_ip_hash = $1 AND created_at > NOW() - INTERVAL '1 hour'",
                ip_hash,
            )
            device_count = 0 if not device_hash else await conn.fetchval(
                "SELECT COUNT(*) FROM app_email_codes WHERE device_hash = $1 AND created_at > NOW() - INTERVAL '1 hour'",
                device_hash,
            )
            if int(email_count or 0) >= 5 or int(ip_count or 0) >= 10 or int(device_count or 0) >= 10:
                raise AccountAuthError("email_rate_limit", "Слишком много запросов. Попробуйте позже.", 429)

            code = f"{secrets.randbelow(1_000_000):06d}"
            challenge_id = await conn.fetchval(
                """
                INSERT INTO app_email_codes (email, code_hash, request_ip_hash, device_hash, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                email,
                code_hash(email, code),
                ip_hash,
                device_hash,
                now + timedelta(minutes=EMAIL_CODE_TTL_MINUTES),
            )
    return int(challenge_id), code


async def invalidate_email_challenge(challenge_id: int) -> None:
    await AppDatabase.execute(
        "UPDATE app_email_codes SET consumed_at = NOW() WHERE id = $1 AND consumed_at IS NULL",
        challenge_id,
    )


def _send_email_sync(email: str, code: str) -> None:
    host = app_config.app_email_smtp_host.strip()
    sender = app_config.app_email_from.strip()
    password = app_config.app_email_smtp_password
    if not host or not sender:
        raise AccountAuthError("email_unavailable", "Отправка писем ещё не настроена", 503)

    message = EmailMessage()
    message["Subject"] = "Код входа в Сферу Таро"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Код входа: {code}\n\nОн действует {EMAIL_CODE_TTL_MINUTES} минут. "
        "Если вы не запрашивали код, просто проигнорируйте письмо."
    )
    context = ssl.create_default_context()
    if app_config.app_email_smtp_ssl:
        client = smtplib.SMTP_SSL(app_config.app_email_smtp_host, app_config.app_email_smtp_port, context=context, timeout=20)
    else:
        client = smtplib.SMTP(app_config.app_email_smtp_host, app_config.app_email_smtp_port, timeout=20)
        client.starttls(context=context)
    try:
        if app_config.app_email_smtp_user:
            client.login(
                app_config.app_email_smtp_user,
                password.get_secret_value() if password else "",
            )
        client.send_message(message)
    finally:
        client.quit()


async def send_login_email(email: str, code: str) -> None:
    await asyncio.to_thread(_send_email_sync, email, code)


async def confirm_email_challenge(
    email: str,
    code: str,
    *,
    current_user_id: Optional[uuid.UUID],
    device_signal: Optional[str],
) -> Dict[str, Any]:
    email = normalize_email(email)
    code = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        raise AccountAuthError("invalid_code", "Введите шестизначный код")

    device_hash = signal_hash("device", device_signal)
    identity_key = f"email:{email}"
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            challenge = await conn.fetchrow(
                """
                SELECT id, code_hash, attempts, expires_at
                FROM app_email_codes
                WHERE email = $1 AND consumed_at IS NULL
                ORDER BY created_at DESC LIMIT 1
                FOR UPDATE
                """,
                email,
            )
            if not challenge or challenge["expires_at"] < datetime.now():
                raise AccountAuthError("code_expired", "Код истёк. Запросите новый.")
            if challenge["attempts"] >= EMAIL_CODE_MAX_ATTEMPTS:
                raise AccountAuthError("code_attempts", "Слишком много попыток. Запросите новый код.", 429)
            if not hmac.compare_digest(challenge["code_hash"], code_hash(email, code)):
                await conn.execute("UPDATE app_email_codes SET attempts = attempts + 1 WHERE id = $1", challenge["id"])
                raise AccountAuthError("invalid_code", "Неверный код")
            await conn.execute("UPDATE app_email_codes SET consumed_at = NOW() WHERE id = $1", challenge["id"])

            identity = await conn.fetchrow(
                "SELECT user_id FROM app_user_identities WHERE provider = 'email' AND provider_user_id = $1",
                email,
            )
            converted_guest = False
            if identity:
                user_id = identity["user_id"]
            else:
                guest = None
                if current_user_id:
                    guest = await conn.fetchrow(
                        "SELECT user_id FROM app_users WHERE user_id = $1 AND is_guest = TRUE FOR UPDATE",
                        current_user_id,
                    )
                if guest:
                    user_id = guest["user_id"]
                    converted_guest = True
                    await conn.execute("UPDATE app_users SET is_guest = FALSE, last_active_at = NOW() WHERE user_id = $1", user_id)
                else:
                    user_id = await conn.fetchval(
                        "INSERT INTO app_users (is_guest, install_id) VALUES (FALSE, NULL) RETURNING user_id"
                    )
                    await conn.execute(
                        "INSERT INTO app_user_balances (user_id, free_divinations_remaining) VALUES ($1, 0)",
                        user_id,
                    )
                await conn.execute(
                    """
                    INSERT INTO app_user_identities (user_id, provider, provider_user_id, display_value)
                    VALUES ($1, 'email', $2, $3)
                    """,
                    user_id,
                    email,
                    mask_email(email),
                )

            granted = 0
            claim = await conn.fetchval(
                """
                INSERT INTO app_trial_claims (identity_key, device_hash, claimed_user_id, granted_amount)
                VALUES ($1, $2, $3, 0)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                identity_key,
                device_hash,
                user_id,
            )
            if claim and not converted_guest:
                granted = TRIAL_DIVINATIONS
                await conn.execute(
                    """
                    UPDATE app_user_balances
                    SET free_divinations_remaining = free_divinations_remaining + $2, updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                    granted,
                )
                await conn.execute(
                    "UPDATE app_trial_claims SET granted_amount = $2 WHERE id = $1",
                    claim,
                    granted,
                )
            await conn.execute("UPDATE app_users SET last_active_at = NOW() WHERE user_id = $1", user_id)
    return {"user_id": user_id, "trial_granted": granted}


async def list_identities(user_id: uuid.UUID) -> list[Dict[str, Any]]:
    rows = await AppDatabase.fetch_all(
        """
        SELECT provider, display_value, created_at
        FROM app_user_identities WHERE user_id = $1 ORDER BY created_at
        """,
        user_id,
    )
    return [dict(row) for row in rows]
