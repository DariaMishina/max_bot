"""Server-authoritative RuStore billing for the Android application."""
from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import app_config
from app.database import AppDatabase, get_user_balance


@dataclass(frozen=True)
class BillingProduct:
    product_id: str
    name: str
    price_rub: int
    divinations: int = 0
    unlimited_days: int = 0

    @property
    def is_subscription(self) -> bool:
        return self.unlimited_days > 0


PRODUCTS = {
    product.product_id: product
    for product in (
        BillingProduct("3_spreads", "3 расклада", 99, divinations=3),
        BillingProduct("10_spreads", "10 раскладов", 179, divinations=10),
        BillingProduct("20_spreads", "20 раскладов", 289, divinations=20),
        BillingProduct("30_spreads", "30 раскладов", 399, divinations=30),
        BillingProduct("unlimited", "Безлимит на месяц", 599, unlimited_days=31),
    )
}


class BillingError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class RuStoreGateway:
    """Small Public API client. Secrets and validation never reach the APK."""

    def __init__(self) -> None:
        self._jwe: Optional[str] = None
        self._jwe_expires_at = 0.0

    def _configured(self) -> None:
        if not (
            app_config.app_rustore_console_app_id
            and app_config.app_rustore_key_id
            and _secret_present(app_config.app_rustore_private_key)
        ):
            raise BillingError("billing_unavailable", "Платежи RuStore ещё не настроены", 503)

    def _auth_payload(self) -> dict[str, str]:
        self._configured()
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        encoded = app_config.app_rustore_private_key.get_secret_value().strip()
        key_bytes = base64.b64decode(encoded)
        private_key = serialization.load_der_private_key(key_bytes, password=None)
        signature = private_key.sign(
            (app_config.app_rustore_key_id + timestamp).encode(),
            padding.PKCS1v15(),
            hashes.SHA512(),
        )
        return {
            "keyId": app_config.app_rustore_key_id,
            "timestamp": timestamp,
            "signature": base64.b64encode(signature).decode(),
        }

    async def _token(self) -> str:
        if self._jwe and self._jwe_expires_at > time.monotonic() + 30:
            return self._jwe
        base = app_config.app_rustore_api_base_url.rstrip("/")
        timeout = aiohttp.ClientTimeout(total=35)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{base}/public/auth/", json=self._auth_payload()) as response:
                payload = await response.json(content_type=None)
        body = payload.get("body") or {}
        if response.status >= 400 or payload.get("code") != "OK" or not body.get("jwe"):
            raise BillingError("rustore_unavailable", "RuStore временно не отвечает", 503)
        self._jwe = str(body["jwe"])
        self._jwe_expires_at = time.monotonic() + min(int(body.get("ttl", 900)), 900)
        return self._jwe

    async def _get(self, path: str) -> dict[str, Any]:
        token = await self._token()
        base = app_config.app_rustore_api_base_url.rstrip("/")
        timeout = aiohttp.ClientTimeout(total=35)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{base}{path}", headers={"Public-Token": token}) as response:
                payload = await response.json(content_type=None)
        if response.status >= 400 or payload.get("code") != "OK" or not isinstance(payload.get("body"), dict):
            raise BillingError("purchase_not_confirmed", "Покупка пока не подтверждена RuStore", 409)
        return payload["body"]

    async def invoice(self, invoice_id: str, sandbox: bool) -> dict[str, Any]:
        prefix = "/public/sandbox" if sandbox else "/public"
        return await self._get(f"{prefix}/v2/invoices/{quote(invoice_id, safe='')}")

    async def subscription(self, product_id: str, purchase_id: str, sandbox: bool) -> dict[str, Any]:
        prefix = "/public/sandbox" if sandbox else "/public"
        package_name = "ru.tarotsphere.app"
        return await self._get(
            f"{prefix}/v5/subscription/{package_name}/{quote(product_id, safe='')}/{quote(purchase_id, safe='')}"
        )


gateway = RuStoreGateway()


def _secret_present(value: Any) -> bool:
    return bool(value and value.get_secret_value().strip())


def billing_enabled() -> bool:
    return bool(
        app_config.app_rustore_console_app_id
        and app_config.app_rustore_key_id
        and _secret_present(app_config.app_rustore_private_key)
    )


def _matches_int(value: Any, expected: int) -> bool:
    try:
        return int(value) == expected
    except (TypeError, ValueError):
        return False


def catalog_packages() -> list[dict[str, Any]]:
    return [
        {
            "id": product.product_id,
            "rustore_product_id": product.product_id,
            "name": product.name,
            "price_rub": product.price_rub,
            "subscription": product.is_subscription,
        }
        for product in PRODUCTS.values()
    ]


async def _grant_product(
    user_id: uuid.UUID,
    product: BillingProduct,
    *,
    payment_id: str,
    invoice_id: Optional[str],
    amount_rub: int,
    metadata: dict[str, Any],
    expires_at: Optional[datetime] = None,
) -> tuple[bool, dict[str, Any]]:
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            inserted = await conn.fetchrow(
                """
                INSERT INTO app_payments (
                    payment_id, invoice_id, user_id, package_id, amount, amount_rub,
                    status, provider, provider_metadata, completed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, 'completed', 'rustore', $7::jsonb, NOW())
                ON CONFLICT (provider, payment_id) DO NOTHING
                RETURNING id
                """,
                payment_id,
                invoice_id,
                user_id,
                product.product_id,
                product.divinations,
                amount_rub,
                json.dumps(metadata, ensure_ascii=False),
            )
            if inserted:
                if product.is_subscription:
                    if expires_at is None:
                        raise BillingError("invalid_purchase", "RuStore не вернул срок подписки", 409)
                    await conn.execute(
                        """
                        INSERT INTO app_subscriptions (user_id, payment_id, provider, expires_at, is_active)
                        VALUES ($1, $2, 'rustore', $3, TRUE)
                        ON CONFLICT (provider, payment_id) DO UPDATE
                        SET expires_at = EXCLUDED.expires_at, is_active = TRUE
                        """,
                        user_id, payment_id, expires_at,
                    )
                    await conn.execute(
                        """
                        UPDATE app_user_balances
                        SET unlimited_until = GREATEST(COALESCE(unlimited_until, $2), $2), updated_at = NOW()
                        WHERE user_id = $1
                        """,
                        user_id, expires_at,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE app_user_balances
                        SET paid_divinations_remaining = paid_divinations_remaining + $2, updated_at = NOW()
                        WHERE user_id = $1
                        """,
                        user_id, product.divinations,
                    )
    return bool(inserted), (await get_user_balance(user_id) or {})


async def verify_rustore_purchase(
    user_id: uuid.UUID,
    *,
    product_id: str,
    invoice_id: Optional[str],
    purchase_id: str,
    sandbox: bool,
) -> dict[str, Any]:
    product = PRODUCTS.get(product_id)
    if not product or not purchase_id:
        raise BillingError("invalid_purchase", "Неизвестный товар RuStore")
    if sandbox != app_config.app_rustore_sandbox:
        raise BillingError("invalid_environment", "Покупка сделана не в текущем контуре", 409)

    if product.is_subscription:
        data = await gateway.subscription(product_id, purchase_id, sandbox)
        if data.get("externalAccountId") != str(user_id):
            raise BillingError("purchase_owner_mismatch", "Покупка принадлежит другому аккаунту", 403)
        if data.get("paymentState") not in (1, 2):
            raise BillingError("purchase_not_confirmed", "Подписка пока не активна", 409)
        if data.get("priceCurrencyCode") != "RUB" or not _matches_int(data.get("priceAmountMicros"), product.price_rub * 1_000_000):
            raise BillingError("purchase_mismatch", "Параметры покупки не совпадают", 409)
        try:
            expires_at = datetime.fromtimestamp(int(data["expiryTimeMillis"]) / 1000, tz=timezone.utc).replace(tzinfo=None)
        except (KeyError, TypeError, ValueError, OSError):
            raise BillingError("invalid_purchase", "RuStore не вернул срок подписки", 409)
        granted, balance = await _grant_product(
            user_id, product, payment_id=purchase_id, invoice_id=invoice_id,
            amount_rub=product.price_rub, metadata=data, expires_at=expires_at,
        )
    else:
        if not invoice_id:
            raise BillingError("invalid_purchase", "invoice_id обязателен")
        data = await gateway.invoice(invoice_id, sandbox)
        order = data.get("order") or {}
        if not _matches_int(data.get("appId"), app_config.app_rustore_console_app_id):
            raise BillingError("purchase_mismatch", "Покупка сделана для другого приложения", 409)
        if data.get("appUserId") != str(user_id):
            raise BillingError("purchase_owner_mismatch", "Покупка принадлежит другому аккаунту", 403)
        if str(data.get("purchaseId")) != purchase_id or order.get("itemCode") != product_id:
            raise BillingError("purchase_mismatch", "Параметры покупки не совпадают", 409)
        if str(data.get("invoiceStatus") or "").upper() != "CONFIRMED":
            raise BillingError("purchase_not_confirmed", "Оплата пока не подтверждена RuStore", 409)
        if order.get("currency") != "RUB" or not _matches_int(order.get("amountCurrent"), product.price_rub * 100):
            raise BillingError("purchase_mismatch", "Цена покупки не совпадает", 409)
        granted, balance = await _grant_product(
            user_id, product, payment_id=purchase_id, invoice_id=invoice_id,
            amount_rub=product.price_rub, metadata=data,
        )
    return {"status": "completed", "granted": granted, "purchase_id": purchase_id, "balance": balance}


def decrypt_callback(payload: str) -> dict[str, Any]:
    if not _secret_present(app_config.app_rustore_callback_key):
        raise BillingError("callback_unavailable", "RuStore callback не настроен", 503)
    try:
        raw = base64.b64decode(payload, validate=True)
        key = base64.b64decode(app_config.app_rustore_callback_key.get_secret_value(), validate=True)
        decoded = AESGCM(key).decrypt(raw[:12], raw[12:], None)
        result = json.loads(decoded)
    except Exception as error:
        raise BillingError("invalid_callback", "Некорректное уведомление RuStore") from error
    if not isinstance(result, dict):
        raise BillingError("invalid_callback", "Некорректное уведомление RuStore")
    return result


async def process_rustore_callback(notification_id: str, encrypted_payload: str) -> None:
    event = decrypt_callback(encrypted_payload)
    if not _matches_int(event.get("app_id"), app_config.app_rustore_console_app_id):
        raise BillingError("invalid_callback", "Уведомление для другого приложения")
    notification_type = str(event.get("notification_type", ""))
    if notification_type in {"TEST_EVENT", "TEST_EVENT_SANDBOX"}:
        return
    try:
        data = json.loads(event.get("data", "{}"))
    except json.JSONDecodeError as error:
        raise BillingError("invalid_callback", "Некорректные данные уведомления") from error
    payment_id = str(data.get("purchase_id") or "")
    payment = await AppDatabase.fetch_one(
        """SELECT id, user_id, package_id, amount, status FROM app_payments
           WHERE provider = 'rustore' AND payment_id = $1""",
        payment_id,
    )
    # A callback may win the race with the authenticated client verification.
    # Ask RuStore to retry instead of acknowledging and losing the event.
    if not payment:
        raise BillingError("payment_not_ready", "Покупка ещё не зарегистрирована", 503)

    subscription_event = notification_type.startswith("SUBSCRIPTION_EVENT")
    event_status = data.get("subscription_event_type") if subscription_event else data.get("status_new")
    status = str(event_status or "").upper()
    subscription_status = str(data.get("status_new") or "").upper()
    refreshed_subscription: Optional[tuple[datetime, dict[str, Any]]] = None
    product = PRODUCTS.get(payment["package_id"])
    if product and product.is_subscription and status in {"ACTIVATED", "RENEWED", "RESUMED"}:
        sandbox = notification_type.endswith("_SANDBOX")
        subscription = await gateway.subscription(product.product_id, payment_id, sandbox)
        if subscription.get("externalAccountId") != str(payment["user_id"]):
            raise BillingError("invalid_callback", "Подписка принадлежит другому аккаунту", 403)
        try:
            expiry = datetime.fromtimestamp(int(subscription["expiryTimeMillis"]) / 1000, tz=timezone.utc).replace(tzinfo=None)
        except (KeyError, TypeError, ValueError, OSError) as error:
            raise BillingError("invalid_callback", "RuStore не вернул срок подписки", 503) from error
        refreshed_subscription = (expiry, subscription)

    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            fresh = await conn.fetchrow(
                """INSERT INTO app_payment_notifications (provider, notification_id)
                   VALUES ('rustore', $1) ON CONFLICT DO NOTHING RETURNING notification_id""",
                notification_id,
            )
            if not fresh:
                return
            payment = await conn.fetchrow(
                """SELECT id, user_id, package_id, amount, status FROM app_payments
                   WHERE provider = 'rustore' AND payment_id = $1 FOR UPDATE""",
                payment_id,
            )
            if not payment:
                raise BillingError("payment_not_ready", "Покупка ещё не зарегистрирована", 503)
            if refreshed_subscription:
                expiry, subscription = refreshed_subscription
                await conn.execute(
                    """UPDATE app_subscriptions SET expires_at = $2, is_active = TRUE
                       WHERE provider = 'rustore' AND payment_id = $1""",
                    payment_id, expiry,
                )
                await conn.execute(
                    """UPDATE app_user_balances
                       SET unlimited_until = GREATEST(COALESCE(unlimited_until, $2), $2), updated_at = NOW()
                       WHERE user_id = $1""",
                    payment["user_id"], expiry,
                )
                await conn.execute(
                    """UPDATE app_payments SET provider_metadata = $2::jsonb, updated_at = NOW()
                       WHERE id = $1""",
                    payment["id"], json.dumps(subscription, ensure_ascii=False),
                )
            terminal = status in {"REFUNDED", "REVERSED", "CLOSED", "TERMINATED"}
            terminal = terminal or (subscription_event and subscription_status in {"PAUSED", "CLOSED", "TERMINATED"})
            if terminal and payment["status"] != "revoked":
                product = PRODUCTS.get(payment["package_id"])
                if product and product.is_subscription:
                    await conn.execute(
                        "UPDATE app_subscriptions SET is_active = FALSE WHERE provider = 'rustore' AND payment_id = $1",
                        payment_id,
                    )
                    latest = await conn.fetchval(
                        """SELECT MAX(expires_at) FROM app_subscriptions
                           WHERE user_id = $1 AND is_active = TRUE AND expires_at > NOW()""",
                        payment["user_id"],
                    )
                    await conn.execute(
                        "UPDATE app_user_balances SET unlimited_until = $2, updated_at = NOW() WHERE user_id = $1",
                        payment["user_id"], latest,
                    )
                elif product:
                    current = await conn.fetchval(
                        "SELECT paid_divinations_remaining FROM app_user_balances WHERE user_id = $1 FOR UPDATE",
                        payment["user_id"],
                    ) or 0
                    revoked = min(int(current), int(payment["amount"]))
                    await conn.execute(
                        """UPDATE app_user_balances SET paid_divinations_remaining = paid_divinations_remaining - $2,
                           updated_at = NOW() WHERE user_id = $1""",
                        payment["user_id"], revoked,
                    )
                    await conn.execute("UPDATE app_payments SET revoked_amount = $2 WHERE id = $1", payment["id"], revoked)
                await conn.execute(
                    "UPDATE app_payments SET status = 'revoked', updated_at = NOW() WHERE id = $1",
                    payment["id"],
                )
            else:
                await conn.execute(
                    "UPDATE app_payments SET status = $2, updated_at = NOW() WHERE id = $1 AND status <> 'completed'",
                    payment["id"], status.lower(),
                )
