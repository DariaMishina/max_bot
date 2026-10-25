import time
import unittest

from main.health_monitor import HealthRuntime


class _Connection:
    async def fetchval(self, query):
        if query != "SELECT 1":
            raise AssertionError(query)
        return 1


class _Acquire:
    async def __aenter__(self):
        return _Connection()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Pool:
    def acquire(self):
        return _Acquire()


class _Database:
    @classmethod
    async def get_pool(cls):
        return _Pool()


class _BrokenDatabase:
    @classmethod
    async def get_pool(cls):
        raise ConnectionError("database unavailable")


class HealthRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def healthy_runtime(self):
        runtime = HealthRuntime()
        runtime.service_name = "test_bot"
        runtime.database = _Database
        runtime.polling.success(time.monotonic(), 200)
        runtime.max_auth.success(time.monotonic(), 200)
        runtime.deepseek.success(time.monotonic(), 200)
        runtime.max_send.status = "disabled"
        return runtime

    async def test_ready_runs_real_select_one(self):
        payload, status = await self.healthy_runtime().readiness()
        self.assertEqual(200, status)
        self.assertEqual("ok", payload["checks"]["database"]["status"])

    async def test_database_failure_makes_service_unready(self):
        runtime = self.healthy_runtime()
        runtime.database = _BrokenDatabase
        payload, status = await runtime.readiness()
        self.assertEqual(503, status)
        self.assertIn("database", payload["failures"])

    async def test_two_deepseek_failures_make_service_unready(self):
        runtime = self.healthy_runtime()
        runtime.deepseek.failure(time.monotonic(), "timeout")
        payload, status = await runtime.readiness()
        self.assertEqual(200, status)
        runtime.deepseek.failure(time.monotonic(), "timeout")
        payload, status = await runtime.readiness()
        self.assertEqual(503, status)
        self.assertIn("deepseek", payload["failures"])


if __name__ == "__main__":
    unittest.main()
