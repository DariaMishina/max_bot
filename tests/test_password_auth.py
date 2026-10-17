"""Password unit tests and opt-in, isolated PostgreSQL/HTTP integration tests.

PASSWORD_TEST_DSN must point at a disposable local PostgreSQL instance.
Every integration test creates and drops only its own random schema.
"""
import asyncio
import os
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch, AsyncMock

for key, value in {
    "APP_DB_USER": "test", "APP_DB_PASSWORD": "test", "APP_JWT_SECRET": "test-only",
    "API_KEY": "test", "BOT_TOKEN": "test", "DB_HOST": "localhost",
    "DB_PORT": "5432", "DB_NAME": "unused_test", "DB_USER": "test", "DB_PASSWORD": "test",
}.items():
    os.environ[key] = value

import asyncpg
from aiohttp.test_utils import TestClient, TestServer
from app import password_auth as auth
from app.account_auth import AccountAuthError, confirm_email_challenge, create_email_challenge, _confirm_identity
from app.trial_grants import normalize_device_signal
from app.config import app_config
from app.database import AppDatabase
import app_api_server as api
from app import password_recovery as recovery
from app.auth_tokens import issue_token_pair, verify_refresh_token

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "A long test password 123!"


class PasswordTests(unittest.TestCase):
    def test_hash_is_salted_and_verifies_exact_password(self):
        first = auth.hash_password(PASSWORD)
        self.assertNotEqual(first, auth.hash_password(PASSWORD))
        self.assertNotIn(PASSWORD, first)
        self.assertTrue(auth.verify_password(PASSWORD, first))
        self.assertFalse(auth.verify_password(PASSWORD + " ", first))
        self.assertFalse(auth.verify_password(PASSWORD, "broken"))

    def test_device_signal_validation(self):
        self.assertEqual(normalize_device_signal(" A123456789ABCDEF "), "a123456789abcdef")
        self.assertEqual(normalize_device_signal("abc"), "abc")
        for value in (None, "", "   ", 123, [], {}, "device-1", "0", "0000000000000000",
                      "9774d56d682e549c", "x" * 17, "a" * 17, "a\nb"):
            with self.subTest(value=value):
                self.assertIsNone(normalize_device_signal(value))

    def test_validation(self):
        self.assertEqual(auth.normalize_login(" Reader_1 "), "reader_1")
        for value in (None, 12, "short", "a@b.test", "кириллица", "x" * 33):
            with self.assertRaises(AccountAuthError):
                auth.normalize_login(value)
        for value in (None, 12, "short", "x" * 129):
            with self.assertRaises(AccountAuthError):
                auth.validate_password(value)


@unittest.skipUnless(os.environ.get("PASSWORD_TEST_DSN"), "set PASSWORD_TEST_DSN for isolated PostgreSQL tests")
class PasswordDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.schema = "password_test_" + uuid.uuid4().hex
        self.admin = await asyncpg.connect(os.environ["PASSWORD_TEST_DSN"])
        await self.admin.execute(f'CREATE SCHEMA "{self.schema}"')
        self.pool = await asyncpg.create_pool(
            os.environ["PASSWORD_TEST_DSN"], min_size=1, max_size=5,
            server_settings={"search_path": self.schema},
        )
        async with self.pool.acquire() as conn:
            for name in ("init_app_db.sql", "app/migrations/005_account_auth.sql", "app/migrations/007_password_auth.sql", "app/migrations/008_password_recovery.sql", "app/migrations/009_trial_grants.sql"):
                await conn.execute((ROOT / name).read_text())
        self.pool_patch = patch.object(AppDatabase, "get_pool", return_value=self.pool)
        self.pool_patch.start()
        self.client = TestClient(TestServer(api.create_app()))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.pool_patch.stop()
        await self.pool.close()
        await self.admin.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        await self.admin.close()

    async def register(self, login="reader_1", device="a123456789abcdef"):
        return await auth.authenticate_password(login, PASSWORD, registering=True, ip="127.0.0.1", device_signal=device)

    async def test_http_register_login_refresh_and_delete(self):
        response = await self.client.post("/v1/auth/password/register", json={
            "login": "Reader_1", "password": PASSWORD, "device_signal": "a123456789abcdef",
        })
        self.assertEqual(response.status, 200, await response.text())
        registered = await response.json()
        response = await self.client.post("/v1/auth/password/login", json={"login": "reader_1", "password": PASSWORD})
        self.assertEqual(response.status, 200, await response.text())
        logged_in = await response.json()
        self.assertEqual(registered["user_id"], logged_in["user_id"])
        self.assertEqual(logged_in["trial_granted"], 0)
        headers = {"Authorization": "Bearer " + logged_in["access_token"]}
        response = await self.client.get("/v1/me", headers=headers)
        self.assertEqual(response.status, 200)
        self.assertFalse((await response.json())["is_guest"])
        response = await self.client.post("/v1/auth/refresh", json={"refresh_token": logged_in["refresh_token"]})
        self.assertEqual(response.status, 200)
        response = await self.client.delete("/v1/me", headers=headers)
        self.assertEqual(response.status, 200, await response.text())
        self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_password_credentials"), 0)
        response = await self.client.post("/v1/auth/password/login", json={"login": "reader_1", "password": PASSWORD})
        self.assertEqual(response.status, 401)
        self.assertEqual((await self.register(device="b123456789abcdef"))["trial_granted"], 0)

    async def test_concurrent_registration_and_device_trial(self):
        results = await asyncio.gather(self.register(), self.register("READER_1"), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual([r.code for r in results if isinstance(r, AccountAuthError)], ["login_taken"])
        self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_users"), 1)
        self.assertEqual((await self.register("reader_2"))["trial_granted"], 0)

    async def identity(self, provider, identity, device):
        return await _confirm_identity(provider, identity, identity,
                                       current_user_id=None, device_signal=device)

    async def test_invalid_devices_cannot_get_gifts_through_any_provider(self):
        for provider in ("password", "email", "vk"):
            for index, device in enumerate((None, "   ", {}, "not-an-android-id", "0")):
                result = await self.identity(provider, f"{provider}-{index}", device)
                self.assertEqual(result["trial_granted"], 0)
        self.assertEqual(await self.pool.fetchval("SELECT SUM(granted_amount) FROM app_trial_claims"), 0)
        self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_trial_claims"), 15)

    async def test_http_whitespace_device_registers_without_gift(self):
        response = await self.client.post("/v1/auth/password/register", json={
            "login": "reader_1", "password": PASSWORD, "device_signal": "   ",
        })
        self.assertEqual(response.status, 200, await response.text())
        body = await response.json()
        self.assertEqual(body["trial_granted"], 0)
        self.assertEqual(body["balance"]["free_divinations_remaining"], 0)
        self.assertTrue(body["access_token"])

    async def test_denied_identity_survives_deletion_and_device_change(self):
        first = await self.register()
        denied = await self.register("reader_2")
        self.assertEqual(denied["trial_granted"], 0)
        await self.pool.execute("DELETE FROM app_users WHERE user_id = $1", denied["user_id"])
        retry = await self.register("reader_2", "b123456789abcdef")
        self.assertEqual(retry["trial_granted"], 0)
        self.assertEqual(await self.pool.fetchval(
            "SELECT free_divinations_remaining FROM app_user_balances WHERE user_id=$1", first["user_id"]), 3)

    async def test_deleted_account_cannot_get_new_identity_gift_on_same_device(self):
        first = await self.register()
        await self.pool.execute("DELETE FROM app_users WHERE user_id=$1", first["user_id"])
        self.assertEqual((await self.register("reader_2"))["trial_granted"], 0)

    async def test_concurrent_link_and_login_preserve_balance(self):
        first = await self.identity("vk", "reader", "abc")
        results = await asyncio.wait_for(asyncio.gather(
            self.identity("vk", "reader", "def"),
            _confirm_identity("email", "reader@example.test", "reader@example.test",
                current_user_id=first["user_id"], device_signal="abc"),
        ), timeout=5)
        self.assertTrue(all(row["trial_granted"] == 0 for row in results))
        self.assertEqual(await self.pool.fetchval(
            "SELECT free_divinations_remaining FROM app_user_balances WHERE user_id=$1", first["user_id"]), 3)

    async def test_concurrent_providers_share_one_device_gift(self):
        results = await asyncio.gather(*(
            self.identity(provider, f"account-{i}", "a123456789abcdef")
            for i, provider in enumerate(("password", "email", "vk", "email", "vk", "password"))
        ))
        self.assertEqual(sum(row["trial_granted"] for row in results), 3)
        self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_trial_claims"), 6)
        self.assertEqual(await self.pool.fetchval("SELECT SUM(free_divinations_remaining) FROM app_user_balances"), 3)

    async def test_global_budget_is_atomic_and_rolls_over_without_resetting_old_claims(self):
        with patch.object(app_config, "app_trial_daily_limit", 2):
            results = await asyncio.gather(*(
                self.identity("vk" if i % 2 else "email", f"account-{i}", f"{i + 1:016x}")
                for i in range(8)
            ))
            self.assertEqual(sum(row["trial_granted"] for row in results), 6)
            self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_users"), 8)
            await self.pool.execute("UPDATE app_trial_claims SET created_at = NOW() - INTERVAL '25 hours'")
            self.assertEqual((await self.identity("email", "account-0", "abc"))["trial_granted"], 0)
            self.assertEqual((await self.identity("email", "fresh", "def"))["trial_granted"], 3)

    async def test_zero_budget_preserves_paid_balance_and_login(self):
        first = await self.register()
        await self.pool.execute("UPDATE app_user_balances SET paid_divinations_remaining=7 WHERE user_id=$1", first["user_id"])
        with patch.object(app_config, "app_trial_daily_limit", 0):
            self.assertEqual((await self.register("reader_2", "b123456789abcdef"))["trial_granted"], 0)
            login = await auth.authenticate_password("reader_1", PASSWORD, registering=False, ip="127.0.0.1")
            self.assertEqual(login["user_id"], first["user_id"])
        balance = await self.pool.fetchrow("SELECT * FROM app_user_balances WHERE user_id=$1", first["user_id"])
        self.assertEqual(balance["paid_divinations_remaining"], 7)
        self.assertEqual(balance["free_divinations_remaining"], 3)

    async def test_migration_backfills_legacy_denied_identities_idempotently(self):
        first = await self.register()
        denied = await self.register("reader_2")
        await self.pool.execute("DELETE FROM app_trial_claims WHERE claimed_user_id=$1", denied["user_id"])
        migration = (ROOT / "app/migrations/009_trial_grants.sql").read_text()
        await self.pool.execute(migration)
        await self.pool.execute(migration)
        self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_trial_claims"), 2)
        self.assertEqual(await self.pool.fetchval(
            "SELECT granted_amount FROM app_trial_claims WHERE claimed_user_id=$1", first["user_id"]), 3)
        await self.pool.execute("DELETE FROM app_users WHERE user_id=$1", denied["user_id"])
        self.assertEqual((await self.register("reader_2", "b123456789abcdef"))["trial_granted"], 0)

    async def test_account_transaction_rollback_does_not_consume_gift(self):
        from app.account_auth import _confirm_identity_with_conn
        async with self.pool.acquire() as conn:
            with self.assertRaisesRegex(RuntimeError, "simulate failure"):
                async with conn.transaction():
                    await _confirm_identity_with_conn(conn, "vk", "rollback", "VK ID",
                        current_user_id=None, device_signal="abc")
                    raise RuntimeError("simulate failure")
        self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_trial_claims"), 0)
        self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_users"), 0)
        self.assertEqual((await self.identity("vk", "rollback", "abc"))["trial_granted"], 3)

    async def test_legacy_existing_identity_without_claim_cannot_receive_new_gift(self):
        first = await self.identity("vk", "legacy", "abc")
        await self.pool.execute("DELETE FROM app_trial_claims")
        self.assertEqual((await self.identity("vk", "legacy", "def"))["trial_granted"], 0)
        self.assertEqual(await self.pool.fetchval(
            "SELECT free_divinations_remaining FROM app_user_balances WHERE user_id=$1", first["user_id"]), 3)

    async def test_wrong_password_and_unknown_login_have_same_error_and_limit_persists(self):
        await self.register()
        for login in ("reader_1", "unknown1"):
            with self.assertRaises(AccountAuthError) as caught:
                await auth.authenticate_password(login, "wrong password 123", registering=False, ip="127.0.0.1")
            self.assertEqual(caught.exception.code, "invalid_credentials")
        for _ in range(9):
            with self.assertRaises(AccountAuthError):
                await auth.authenticate_password("reader_1", "wrong password 123", registering=False, ip="127.0.0.1")
        with self.assertRaises(AccountAuthError) as caught:
            await auth.authenticate_password("reader_1", PASSWORD, registering=False, ip="127.0.0.1")
        self.assertEqual(caught.exception.status, 429)
        await self.pool.execute("UPDATE app_password_limits SET expires_at = NOW() - INTERVAL '1 second'")
        result = await auth.authenticate_password("reader_1", PASSWORD, registering=False, ip="127.0.0.1")
        self.assertEqual(result["trial_granted"], 0)

    async def test_failed_email_attempts_are_committed(self):
        challenge, code = await create_email_challenge("reader@example.test", ip=None, device_signal=None)
        wrong = "000000" if code != "000000" else "111111"
        for expected in range(1, 6):
            with self.assertRaises(AccountAuthError):
                await confirm_email_challenge("reader@example.test", wrong, current_user_id=None, device_signal=None)
            self.assertEqual(await self.pool.fetchval("SELECT attempts FROM app_email_codes WHERE id=$1", challenge), expected)
        with self.assertRaises(AccountAuthError) as caught:
            await confirm_email_challenge("reader@example.test", code, current_user_id=None, device_signal=None)
        self.assertEqual(caught.exception.code, "code_attempts")

    async def bind_email(self, user_id, email="reader@example.test"):
        with patch.object(recovery, "send_login_email", AsyncMock()) as send:
            challenge = await recovery.start_challenge(user_id=user_id, email=email, password=PASSWORD, ip="127.0.0.1")
            code = send.await_args.args[1]
        await recovery.confirm_challenge(challenge, code, user_id=user_id)
        return challenge, code

    async def reset_code(self):
        with patch.object(recovery, "send_login_email", AsyncMock()) as send:
            challenge = await recovery.start_challenge(login="reader_1", email="reader@example.test", ip="127.0.0.1")
            return challenge, send.await_args.args[1]

    async def test_recovery_http_flow_revokes_access_refresh_and_old_password(self):
        account = await self.register()
        user_id = account["user_id"]
        tokens = await issue_token_pair(user_id)
        headers = {"Authorization": "Bearer " + tokens["access_token"]}
        with patch.object(recovery, "send_login_email", AsyncMock()) as send:
            response = await self.client.post("/v1/me/recovery-email/start", headers=headers,
                json={"email": "reader@example.test", "password": PASSWORD})
            self.assertEqual(response.status, 200, await response.text())
            bind = (await response.json())["challenge_id"]
            code = send.await_args.args[1]
        response = await self.client.post("/v1/me/recovery-email/confirm", headers=headers,
            json={"challenge_id": bind, "code": code})
        self.assertEqual(response.status, 200)
        with patch.object(recovery, "send_login_email", AsyncMock()) as send:
            response = await self.client.post("/v1/auth/password/reset/start",
                json={"login": "reader_1", "email": "reader@example.test"})
            reset = (await response.json())["challenge_id"]
            code = send.await_args.args[1]
        payload = {"challenge_id": reset, "code": code, "password": "New long password 456!"}
        response = await self.client.post("/v1/auth/password/reset/confirm", json=payload)
        self.assertEqual(response.status, 200, await response.text())
        response = await self.client.get("/v1/me", headers=headers)
        self.assertEqual(response.status, 401)
        response = await self.client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(response.status, 401)
        response = await self.client.post("/v1/auth/password/login", json={"login": "reader_1", "password": PASSWORD})
        self.assertEqual(response.status, 401)
        response = await self.client.post("/v1/auth/password/reset/confirm", json=payload)
        self.assertEqual(response.status, 400)
        response = await self.client.post("/v1/auth/password/login", json={"login": "reader_1", "password": payload["password"]})
        self.assertEqual(response.status, 200)
        fresh = await response.json()
        self.assertEqual(fresh["user_id"], str(user_id))
        response = await self.client.get("/v1/me", headers={"Authorization": "Bearer " + fresh["access_token"]})
        self.assertEqual(response.status, 200)
        self.assertEqual(fresh["trial_granted"], 0)

    async def test_reset_unknown_email_neutral_and_delivery_failure_invalidates(self):
        account = await self.register()
        await self.bind_email(account["user_id"])
        with patch.object(recovery, "send_login_email", AsyncMock()) as send:
            for login, email in (("unknown1", "reader@example.test"), ("reader_1", "wrong@example.test")):
                response = await self.client.post("/v1/auth/password/reset/start", json={"login": login, "email": email})
                self.assertEqual(response.status, 200)
                self.assertEqual(set(await response.json()), {"ok", "challenge_id"})
            send.assert_not_awaited()
        with patch.object(recovery, "send_login_email", AsyncMock(side_effect=RuntimeError("smtp failed"))):
            challenge = await recovery.start_challenge(login="reader_1", email="reader@example.test", ip="127.0.0.1")
        self.assertIsNotNone(await self.pool.fetchval("SELECT consumed_at FROM app_password_challenges WHERE id=$1", uuid.UUID(challenge)))

    async def test_challenge_owner_purpose_expiry_attempts_and_resend(self):
        account = await self.register()
        other = await self.register("reader_2", "b123456789abcdef")
        with self.assertRaises(AccountAuthError):
            await recovery.start_challenge(user_id=account["user_id"], email="reader@example.test", password="wrong password 123")
        with patch.object(recovery, "send_login_email", AsyncMock()) as send:
            bind = await recovery.start_challenge(user_id=account["user_id"], email="reader@example.test", password=PASSWORD)
            code = send.await_args.args[1]
        with self.assertRaises(AccountAuthError):
            await recovery.confirm_challenge(bind, code, user_id=other["user_id"])
        with self.assertRaises(AccountAuthError):
            await recovery.confirm_challenge(bind, code, new_password=PASSWORD)
        await recovery.confirm_challenge(bind, code, user_id=account["user_id"])
        old, old_code = await self.reset_code()
        new, code = await self.reset_code()
        with self.assertRaises(AccountAuthError):
            await recovery.confirm_challenge(old, old_code, new_password=PASSWORD)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            with self.assertRaises(AccountAuthError):
                await recovery.confirm_challenge(new, wrong, new_password=PASSWORD)
        self.assertEqual(await self.pool.fetchval("SELECT attempts FROM app_password_challenges WHERE id=$1", uuid.UUID(new)), 5)
        with self.assertRaises(AccountAuthError):
            await recovery.confirm_challenge(new, code, new_password=PASSWORD)
        expired, code = await self.reset_code()
        await self.pool.execute("UPDATE app_password_challenges SET expires_at=NOW()-INTERVAL '1 second' WHERE id=$1", uuid.UUID(expired))
        with self.assertRaises(AccountAuthError):
            await recovery.confirm_challenge(expired, code, new_password=PASSWORD)

    async def test_epoch_rejects_token_issuance_and_refresh_created_after_reset(self):
        from app.auth_tokens import create_refresh_token
        account = await self.register()
        await self.bind_email(account["user_id"])
        challenge, code = await self.reset_code()
        await recovery.confirm_challenge(challenge, code, new_password=PASSWORD)
        with self.assertRaises(AccountAuthError):
            await issue_token_pair(account["user_id"], expected_version=0)
        late = await create_refresh_token(account["user_id"], auth_version=0)
        self.assertIsNone(await verify_refresh_token(late))
