import base64
import json
import os
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

for key, value in {
    "APP_DB_USER": "test", "APP_DB_PASSWORD": "test", "APP_JWT_SECRET": "test-only",
    "API_KEY": "test", "BOT_TOKEN": "test", "DB_HOST": "localhost", "DB_PORT": "5432",
    "DB_NAME": "unused_test", "DB_USER": "test", "DB_PASSWORD": "test",
}.items():
    os.environ[key] = value

from app import billing


USER = uuid.uuid4()


class RuStoreBillingTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_purchase_does_not_credit_balance_again(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        conn.transaction.return_value.__aenter__ = AsyncMock()
        conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch.object(billing.AppDatabase, "get_pool", AsyncMock(return_value=pool)), \
                patch.object(billing, "get_user_balance", AsyncMock(return_value={"paid_divinations_remaining": 3})):
            granted, _ = await billing._grant_product(
                USER, billing.PRODUCTS["3_spreads"], payment_id="purchase-1",
                invoice_id="invoice-1", amount_rub=99, metadata={},
            )
        self.assertFalse(granted)
        conn.execute.assert_not_awaited()

    async def test_verified_invoice_is_granted_with_server_values(self):
        invoice = {
            "appId": 123,
            "appUserId": str(USER),
            "purchaseId": "purchase-1",
            "invoiceStatus": "CONFIRMED",
            "order": {"itemCode": "3_spreads", "currency": "RUB", "amountCurrent": 9900},
        }
        with patch.object(billing.app_config, "app_rustore_console_app_id", 123), \
                patch.object(billing.app_config, "app_rustore_sandbox", True), \
                patch.object(billing.gateway, "invoice", AsyncMock(return_value=invoice)), \
                patch.object(billing, "_grant_product", AsyncMock(return_value=(True, {"paid_divinations_remaining": 3}))) as grant:
            result = await billing.verify_rustore_purchase(
                USER, product_id="3_spreads", invoice_id="invoice-1",
                purchase_id="purchase-1", sandbox=True,
            )
        self.assertTrue(result["granted"])
        grant.assert_awaited_once()

    async def test_client_cannot_change_owner_product_or_price(self):
        valid = {
            "appId": 123,
            "appUserId": str(USER),
            "purchaseId": "purchase-1",
            "invoiceStatus": "CONFIRMED",
            "order": {"itemCode": "3_spreads", "currency": "RUB", "amountCurrent": 9900},
        }
        cases = [
            {**valid, "appUserId": str(uuid.uuid4())},
            {**valid, "order": {**valid["order"], "itemCode": "30_spreads"}},
            {**valid, "order": {**valid["order"], "amountCurrent": 1}},
        ]
        with patch.object(billing.app_config, "app_rustore_console_app_id", 123), \
                patch.object(billing.app_config, "app_rustore_sandbox", True):
            for invoice in cases:
                with patch.object(billing.gateway, "invoice", AsyncMock(return_value=invoice)), \
                        self.assertRaises(billing.BillingError):
                    await billing.verify_rustore_purchase(
                        USER, product_id="3_spreads", invoice_id="invoice-1",
                        purchase_id="purchase-1", sandbox=True,
                    )

    def test_callback_requires_valid_aes_gcm_payload(self):
        key = AESGCM.generate_key(bit_length=256)
        iv = b"0123456789ab"
        event = {"notification_type": "TEST_EVENT", "app_id": 123, "data": "{}"}
        encrypted = iv + AESGCM(key).encrypt(iv, json.dumps(event).encode(), None)
        with patch.object(billing.app_config, "app_rustore_callback_key", type("Secret", (), {"get_secret_value": lambda self: base64.b64encode(key).decode()})()):
            self.assertEqual(billing.decrypt_callback(base64.b64encode(encrypted).decode()), event)
            with self.assertRaises(billing.BillingError):
                billing.decrypt_callback("not-base64")


if __name__ == "__main__":
    unittest.main()
