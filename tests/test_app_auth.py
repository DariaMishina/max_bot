"""Stage 4.7 account/authentication tests without a real DB or SMTP server."""
import os
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

for key, value in {
    "APP_DB_USER": "test",
    "APP_DB_PASSWORD": "test",
    "APP_JWT_SECRET": "test-only",
    "APP_VK_CLIENT_ID": "54803401",
    "API_KEY": "test",
    "BOT_TOKEN": "test",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "unused_test",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
}.items():
    os.environ[key] = value

import app_api_server as api
from app import account_auth as auth

USER = uuid.uuid4()
EMAIL = "reader@example.test"
CODE = "123456"


def fake_pool(conn):
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


def request(body):
    req = MagicMock()
    req.body_exists = True
    req.json = AsyncMock(return_value=body)
    req.remote = "127.0.0.1"
    req.headers = {}
    return req


class AccountAuthTests(unittest.IsolatedAsyncioTestCase):
    def test_email_normalization_mask_and_hash(self):
        self.assertEqual(auth.normalize_email(" Reader@Example.Test "), EMAIL)
        self.assertEqual(auth.mask_email(EMAIL), "re••••@example.test")
        self.assertEqual(auth.code_hash(EMAIL, CODE), auth.code_hash(EMAIL, CODE))
        self.assertNotEqual(auth.code_hash(EMAIL, CODE), auth.code_hash(EMAIL, "000000"))
        with self.assertRaises(auth.AccountAuthError):
            auth.normalize_email("not-an-email")

    async def test_wrong_code_counts_attempt_without_creating_account(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={
            "id": 7,
            "code_hash": auth.code_hash(EMAIL, CODE),
            "attempts": 0,
            "expires_at": datetime.now() + timedelta(minutes=5),
        })
        conn.execute = AsyncMock()
        with patch.object(auth.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))):
            with self.assertRaises(auth.AccountAuthError) as error:
                await auth.confirm_email_challenge(
                    EMAIL, "000000", current_user_id=None, device_signal="device",
                )
        self.assertEqual(error.exception.code, "invalid_code")
        self.assertIn("attempts = attempts + 1", conn.execute.call_args.args[0])

    async def test_new_email_gets_one_trial_and_confirmed_account(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(side_effect=[
            {
                "id": 7,
                "code_hash": auth.code_hash(EMAIL, CODE),
                "attempts": 0,
                "expires_at": datetime.now() + timedelta(minutes=5),
            },
            None,
        ])
        conn.fetchval = AsyncMock(side_effect=[USER, 99])
        conn.execute = AsyncMock()
        with patch.object(auth.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))):
            result = await auth.confirm_email_challenge(
                EMAIL, CODE, current_user_id=None, device_signal="device",
            )
        self.assertEqual(result, {"user_id": USER, "trial_granted": 3})
        statements = "\n".join(call.args[0] for call in conn.execute.await_args_list)
        self.assertIn("INSERT INTO app_user_identities", statements)
        self.assertIn("free_divinations_remaining = free_divinations_remaining + $2", statements)

    async def test_existing_identity_never_gets_second_trial(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(side_effect=[
            {
                "id": 8,
                "code_hash": auth.code_hash(EMAIL, CODE),
                "attempts": 0,
                "expires_at": datetime.now() + timedelta(minutes=5),
            },
            {"user_id": USER},
        ])
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        with patch.object(auth.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))):
            result = await auth.confirm_email_challenge(
                EMAIL, CODE, current_user_id=None, device_signal="new-device",
            )
        self.assertEqual(result["trial_granted"], 0)
        statements = "\n".join(call.args[0] for call in conn.execute.await_args_list)
        self.assertNotIn("free_divinations_remaining = free_divinations_remaining + $2", statements)

    async def test_staging_guest_is_converted_without_replacing_balance(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(side_effect=[
            {
                "id": 9,
                "code_hash": auth.code_hash(EMAIL, CODE),
                "attempts": 0,
                "expires_at": datetime.now() + timedelta(minutes=5),
            },
            None,
            {"user_id": USER, "is_guest": True},
        ])
        conn.fetchval = AsyncMock(return_value=101)
        conn.execute = AsyncMock()
        with patch.object(auth.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))):
            result = await auth.confirm_email_challenge(
                EMAIL, CODE, current_user_id=USER, device_signal="device",
            )
        self.assertEqual(result, {"user_id": USER, "trial_granted": 0})
        statements = "\n".join(call.args[0] for call in conn.execute.await_args_list)
        self.assertIn("SET is_guest = FALSE", statements)
        self.assertNotIn("free_divinations_remaining = free_divinations_remaining + $2", statements)

    async def test_email_start_has_neutral_response(self):
        with patch.object(api, "create_email_challenge", AsyncMock(return_value=(4, CODE))), \
                patch.object(api, "send_login_email", AsyncMock()) as send:
            response = await api.email_start_handler(request({"email": EMAIL, "device_signal": "device"}))
        self.assertEqual(response.status, 200)
        self.assertEqual(api.json.loads(response.text), {"ok": True, "expires_in": 600, "resend_after": 60})
        send.assert_awaited_once_with(EMAIL, CODE)

    async def test_new_vk_identity_gets_one_trial_after_provider_verification(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetchval = AsyncMock(side_effect=[USER, 102])
        conn.execute = AsyncMock()
        with patch.object(auth, "_fetch_vk_user_id", AsyncMock(return_value="vk-user-42")), \
                patch.object(auth.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))):
            result = await auth.confirm_vk_access_token(
                "provider-token", current_user_id=None, device_signal="device",
            )
        self.assertEqual(result, {"user_id": USER, "trial_granted": 3})
        statements = "\n".join(call.args[0] for call in conn.execute.await_args_list)
        self.assertIn("INSERT INTO app_user_identities", statements)
        self.assertNotIn("provider-token", statements)

    async def test_vk_handler_never_trusts_user_id_from_phone(self):
        result = {"user_id": USER, "trial_granted": 0}
        with patch.object(api, "confirm_vk_access_token", AsyncMock(return_value=result)) as confirm, \
                patch.object(api, "issue_token_pair", AsyncMock(return_value={
                    "access_token": "app-access", "refresh_token": "app-refresh",
                    "token_type": "bearer", "expires_in": 3600, "user_id": str(USER),
                })), \
                patch.object(api, "get_user_balance", AsyncMock(return_value={
                    "free_divinations_remaining": 2,
                    "paid_divinations_remaining": 0,
                    "unlimited_until": None,
                    "total_divinations_used": 1,
                })):
            response = await api.vk_auth_handler(request({
                "access_token": "verified-by-provider",
                "provider_user_id": "attacker-controlled",
                "device_signal": "device",
            }))
        self.assertEqual(response.status, 200)
        confirm.assert_awaited_once_with(
            "verified-by-provider", current_user_id=None, device_signal="device",
        )

    async def test_linking_vk_to_confirmed_account_never_grants_second_trial(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(side_effect=[
            None,
            {"user_id": USER, "is_guest": False},
        ])
        conn.fetchval = AsyncMock(return_value=103)
        conn.execute = AsyncMock()
        with patch.object(auth, "_fetch_vk_user_id", AsyncMock(return_value="vk-user-43")), \
                patch.object(auth.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))):
            result = await auth.confirm_vk_access_token(
                "provider-token", current_user_id=USER, device_signal="device",
            )
        self.assertEqual(result, {"user_id": USER, "trial_granted": 0})
        statements = "\n".join(call.args[0] for call in conn.execute.await_args_list)
        self.assertNotIn("free_divinations_remaining = free_divinations_remaining + $2", statements)

    async def test_linking_vk_owned_by_another_account_is_rejected(self):
        other_user = uuid.uuid4()
        conn = MagicMock()
        conn.fetchrow = AsyncMock(side_effect=[
            {"user_id": other_user},
            {"user_id": USER, "is_guest": False},
        ])
        conn.execute = AsyncMock()
        with patch.object(auth, "_fetch_vk_user_id", AsyncMock(return_value="vk-user-44")), \
                patch.object(auth.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))):
            with self.assertRaises(auth.AccountAuthError) as error:
                await auth.confirm_vk_access_token(
                    "provider-token", current_user_id=USER, device_signal="device",
                )
        self.assertEqual(error.exception.code, "identity_conflict")


if __name__ == "__main__":
    unittest.main()
