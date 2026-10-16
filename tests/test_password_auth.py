"""Password unit tests and opt-in, isolated PostgreSQL/HTTP integration tests.

PASSWORD_TEST_DSN must point at a disposable local PostgreSQL instance.
Every integration test creates and drops only its own random schema.
"""
import asyncio
import os
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

for key, value in {
    "APP_DB_USER": "test", "APP_DB_PASSWORD": "test", "APP_JWT_SECRET": "test-only",
    "API_KEY": "test", "BOT_TOKEN": "test", "DB_HOST": "localhost",
    "DB_PORT": "5432", "DB_NAME": "unused_test", "DB_USER": "test", "DB_PASSWORD": "test",
}.items():
    os.environ[key] = value

import asyncpg
from aiohttp.test_utils import TestClient, TestServer
from app import password_auth as auth
from app.account_auth import AccountAuthError, confirm_email_challenge, create_email_challenge
from app.database import AppDatabase
import app_api_server as api

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
            for name in ("init_app_db.sql", "app/migrations/005_account_auth.sql", "app/migrations/007_password_auth.sql"):
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

    async def register(self, login="reader_1", device="device-1"):
        return await auth.authenticate_password(login, PASSWORD, registering=True, ip="127.0.0.1", device_signal=device)

    async def test_http_register_login_refresh_and_delete(self):
        response = await self.client.post("/v1/auth/password/register", json={
            "login": "Reader_1", "password": PASSWORD, "device_signal": "device-1",
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
        self.assertEqual((await self.register(device="device-2"))["trial_granted"], 0)

    async def test_concurrent_registration_and_device_trial(self):
        results = await asyncio.gather(self.register(), self.register("READER_1"), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual([r.code for r in results if isinstance(r, AccountAuthError)], ["login_taken"])
        self.assertEqual(await self.pool.fetchval("SELECT COUNT(*) FROM app_users"), 1)
        self.assertEqual((await self.register("reader_2"))["trial_granted"], 0)

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
