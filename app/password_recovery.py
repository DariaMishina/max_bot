"""Purpose-bound, single-use recovery challenges; never authenticate via email login."""
import asyncio
import hmac
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta

from app.account_auth import AccountAuthError, normalize_email, code_hash, send_login_email
from app.database import AppDatabase
from app.password_auth import normalize_login, validate_password, verify_password, hash_password, _HASH_SLOTS, _throttle


async def start_challenge(*, user_id=None, login=None, email=None, password=None, ip=None):
    purpose = "bind" if user_id else "reset"
    key = str(user_id) if user_id else normalize_login(login)
    email = normalize_email(email)
    await _throttle("recovery-" + purpose + ":" + key, ip, True)
    row = await AppDatabase.fetch_one(
        "SELECT * FROM app_password_credentials WHERE " + ("user_id=$1" if user_id else "login=$1"),
        user_id if user_id else key,
    )
    if purpose == "bind":
        password = validate_password(password)
        async with _HASH_SLOTS:
            valid = await asyncio.to_thread(verify_password, password, row["password_hash"] if row else "")
        if not row or not valid:
            raise AccountAuthError("invalid_credentials", "Неверный пароль", 401)
    challenge_id = uuid.uuid4()
    if not row or (purpose == "reset" and row["recovery_email"] != email):
        return str(challenge_id)  # Identical response; do not disclose an account/email match.
    code = f"{secrets.randbelow(1_000_000):06d}"
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchrow("SELECT * FROM app_password_credentials WHERE user_id=$1 FOR UPDATE", row["user_id"])
            if not current or current["password_hash"] != row["password_hash"] or current["recovery_email"] != row["recovery_email"]:
                raise AccountAuthError("session_changed", "Данные аккаунта изменились. Повторите запрос.", 409)
            await conn.execute("DELETE FROM app_password_challenges WHERE user_id=$1 AND (purpose=$2 OR expires_at < NOW())", row["user_id"], purpose)
            await conn.execute(
                "INSERT INTO app_password_challenges(id,user_id,purpose,email,code_hash,expires_at) VALUES($1,$2,$3,$4,$5,$6)",
                challenge_id, row["user_id"], purpose, email,
                code_hash(str(challenge_id), code), datetime.now() + timedelta(minutes=10),
            )
    try:
        await send_login_email(email, code, purpose=purpose)
    except Exception:
        await AppDatabase.execute("UPDATE app_password_challenges SET consumed_at=NOW() WHERE id=$1", challenge_id)
        logging.warning("Password recovery email delivery failed")
        if purpose == "bind":
            raise AccountAuthError("email_unavailable", "Не удалось отправить письмо. Попробуйте позже.", 503)
        # Public reset response remains neutral even when SMTP fails.
    return str(challenge_id)


async def confirm_challenge(challenge_id, code, *, user_id=None, new_password=None):
    purpose = "bind" if user_id else "reset"
    try:
        challenge_id = uuid.UUID(str(challenge_id))
    except ValueError:
        raise AccountAuthError("invalid_code", "Код недействителен или истёк")
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
        raise AccountAuthError("invalid_code", "Введите шестизначный код")
    encoded = None
    if purpose == "reset":
        new_password = validate_password(new_password)
    pool = await AppDatabase.get_pool()
    valid = False
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Credential first: serializes reset, email changes and parallel confirmation.
            owner = await conn.fetchval("SELECT user_id FROM app_password_challenges WHERE id=$1", challenge_id)
            credentials = await conn.fetchrow("SELECT * FROM app_password_credentials WHERE user_id=$1 FOR UPDATE", owner) if owner else None
            row = await conn.fetchrow("SELECT * FROM app_password_challenges WHERE id=$1 FOR UPDATE", challenge_id)
            if (credentials and row and row["purpose"] == purpose and
                    (user_id is None or row["user_id"] == user_id) and
                    row["consumed_at"] is None and row["expires_at"] > datetime.now() and row["attempts"] < 5 and
                    (purpose == "bind" or credentials["recovery_email"] == row["email"])):
                valid = hmac.compare_digest(row["code_hash"], code_hash(str(challenge_id), code))
                await conn.execute("UPDATE app_password_challenges SET attempts=attempts+1 WHERE id=$1", challenge_id)
                if valid:
                    if purpose == "bind":
                        await conn.execute("UPDATE app_password_credentials SET recovery_email=$2 WHERE user_id=$1", owner, row["email"])
                    else:
                        async with _HASH_SLOTS:
                            encoded = await asyncio.to_thread(hash_password, new_password)
                        await conn.execute("UPDATE app_password_credentials SET password_hash=$2 WHERE user_id=$1", owner, encoded)
                        await conn.execute("UPDATE app_users SET auth_version=auth_version+1 WHERE user_id=$1", owner)
                        await conn.execute("UPDATE app_refresh_tokens SET revoked_at=NOW() WHERE user_id=$1 AND revoked_at IS NULL", owner)
                    await conn.execute("UPDATE app_password_challenges SET consumed_at=NOW() WHERE user_id=$1", owner)
    if not valid:
        raise AccountAuthError("invalid_code", "Код недействителен или истёк")
