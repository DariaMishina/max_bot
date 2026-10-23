"""Production rate-limit and application-only LLM budget checks."""
import json
import os
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

for key, value in {
    "APP_DB_USER": "test", "APP_DB_PASSWORD": "test", "APP_JWT_SECRET": "test-only",
    "API_KEY": "test", "BOT_TOKEN": "test", "DB_HOST": "localhost", "DB_PORT": "5432",
    "DB_NAME": "unused_test", "DB_USER": "test", "DB_PASSWORD": "test",
}.items():
    os.environ.setdefault(key, value)

import app_api_server as api
from app import divination_service as service
from app import llm_budget
from app.rate_limits import SlidingWindowLimiter, client_ip


def fake_pool(conn):
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


class SlidingWindowTests(unittest.TestCase):
    def test_window_expires_and_zero_disables_limit(self):
        now = [100.0]
        limiter = SlidingWindowLimiter(clock=lambda: now[0])
        self.assertTrue(limiter.allow("api", "key", 2, 60))
        self.assertTrue(limiter.allow("api", "key", 2, 60))
        self.assertFalse(limiter.allow("api", "key", 2, 60))
        now[0] = 161.0
        self.assertTrue(limiter.allow("api", "key", 2, 60))
        self.assertTrue(limiter.allow("off", "key", 0, 60))

    def test_forwarded_address_only_trusted_from_loopback(self):
        self.assertEqual(client_ip("127.0.0.1", "203.0.113.7"), "203.0.113.7")
        self.assertEqual(client_ip("198.51.100.2", "203.0.113.7"), "198.51.100.2")
        self.assertEqual(client_ip("127.0.0.1", "not-an-ip"), "127.0.0.1")


class LlmBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_reservation_is_atomic_and_fail_closed_at_limit(self):
        user_id = uuid.uuid4()
        conn = MagicMock()
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(side_effect=[499, 42])
        with patch.object(llm_budget.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))), \
                patch.object(llm_budget.app_config, "app_deepseek_daily_request_limit", 500):
            self.assertEqual(await llm_budget.reserve_llm_request(user_id, "tarot"), 42)
        self.assertIn("pg_advisory_xact_lock", conn.execute.await_args.args[0])

        conn.fetchval = AsyncMock(return_value=500)
        with patch.object(llm_budget.AppDatabase, "get_pool", AsyncMock(return_value=fake_pool(conn))), \
                patch.object(llm_budget.app_config, "app_deepseek_daily_request_limit", 500):
            with self.assertRaises(llm_budget.AppLlmBudgetExceeded):
                await llm_budget.reserve_llm_request(user_id, "tarot")

    async def test_failed_provider_call_consumes_reserved_slot(self):
        call = AsyncMock(side_effect=RuntimeError("provider down"))
        finish = AsyncMock()
        with patch.object(service, "reserve_llm_request", AsyncMock(return_value=9)), \
                patch.object(service, "finish_llm_request", finish):
            with self.assertRaises(RuntimeError):
                await service._budgeted_llm_call(uuid.uuid4(), "tarot", call)
        finish.assert_awaited_once_with(9, succeeded=False)

    async def test_budget_exhaustion_has_safe_public_error(self):
        with patch.object(service, "reserve_llm_request", AsyncMock(side_effect=llm_budget.AppLlmBudgetExceeded)):
            with self.assertRaises(service.DivinationError) as raised:
                await service._budgeted_llm_call(uuid.uuid4(), "tarot", AsyncMock())
        self.assertEqual(raised.exception.code, "service_budget_exhausted")


class MiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_rate_limit_returns_429_without_calling_handler(self):
        request = MagicMock()
        request.path = "/v1/auth/email/start"
        request.remote = "127.0.0.1"
        request.headers = {}
        handler = AsyncMock(return_value=api.json_response({"ok": True}))
        limiter = MagicMock()
        limiter.allow.side_effect = [True, False]
        with patch.object(api, "RATE_LIMITER", limiter), \
                patch.object(api.app_config, "app_api_ip_requests_per_minute", 10), \
                patch.object(api.app_config, "app_auth_ip_requests_per_15_minutes", 5):
            response = await api.rate_limit_middleware(request, handler)
        self.assertEqual(response.status, 429)
        self.assertEqual(json.loads(response.text)["error"], "rate_limited")
        self.assertEqual(response.headers["Retry-After"], "900")
        handler.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
