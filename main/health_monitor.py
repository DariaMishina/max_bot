from __future__ import annotations

import asyncio
import hmac
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MethodType
from typing import Any

import aiohttp
from aiohttp import web


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _safe_error(exc: BaseException | str) -> str:
    text = str(exc).replace("\n", " ").strip()
    return text[:300] or type(exc).__name__


def _version() -> str:
    configured = os.getenv("COMMIT_SHA", "").strip()
    if configured:
        return configured
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@dataclass
class ProbeState:
    status: str = "starting"
    last_check_at: datetime | None = None
    last_success_at: datetime | None = None
    latency_ms: int | None = None
    http_status: int | None = None
    error: str | None = None
    consecutive_failures: int = 0

    def success(self, started: float, http_status: int | None = None) -> None:
        now = _utc_now()
        self.status = "ok"
        self.last_check_at = now
        self.last_success_at = now
        self.latency_ms = round((time.monotonic() - started) * 1000)
        self.http_status = http_status
        self.error = None
        self.consecutive_failures = 0

    def failure(
        self,
        started: float,
        error: BaseException | str,
        http_status: int | None = None,
    ) -> None:
        self.last_check_at = _utc_now()
        self.latency_ms = round((time.monotonic() - started) * 1000)
        self.http_status = http_status
        self.error = _safe_error(error)
        self.consecutive_failures += 1
        self.status = "degraded" if self.consecutive_failures == 1 else "error"

    def payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "last_check_at": _iso(self.last_check_at),
            "last_success_at": _iso(self.last_success_at),
            "latency_ms": self.latency_ms,
            "http_status": self.http_status,
            "error": self.error,
            "consecutive_failures": self.consecutive_failures,
        }


class HealthRuntime:
    def __init__(self) -> None:
        self.service_name = "unknown"
        self.version = _version()
        self.started_at = _utc_now()
        self.started_monotonic = time.monotonic()
        self.bot = None
        self.database = None
        self.deepseek_api_key = ""
        self.deepseek_model = "deepseek-flash"
        self.max_test_user_id: int | None = None
        self.max_auth = ProbeState()
        self.max_send = ProbeState(status="disabled")
        self.deepseek = ProbeState()
        self.polling = ProbeState()
        self._tasks: list[asyncio.Task] = []
        self._polling_probe_installed = False

    def configure(
        self,
        *,
        service_name: str,
        bot,
        database,
        deepseek_api_key: str,
        deepseek_model: str = "deepseek-flash",
    ) -> None:
        self.service_name = service_name
        self.bot = bot
        self.database = database
        self.deepseek_api_key = deepseek_api_key
        self.deepseek_model = deepseek_model
        test_user = os.getenv("HEALTH_MAX_TEST_USER_ID", "").strip()
        self.max_test_user_id = int(test_user) if test_user else None
        if self.max_test_user_id is None:
            self.max_send.status = "disabled"
        self._install_polling_probe()

    def _install_polling_probe(self) -> None:
        if self._polling_probe_installed or self.bot is None:
            return
        original_get_updates = self.bot.get_updates
        runtime = self

        async def tracked_get_updates(_bot, *args, **kwargs):
            started = time.monotonic()
            try:
                result = await original_get_updates(*args, **kwargs)
            except Exception as exc:
                runtime.polling.failure(started, exc)
                raise
            else:
                runtime.polling.success(started, 200)
                return result

        self.bot.get_updates = MethodType(tracked_get_updates, self.bot)
        self._polling_probe_installed = True

    def start(self) -> None:
        if self._tasks:
            return
        self._tasks = [
            asyncio.create_task(self._max_auth_loop(), name="health:max-auth"),
            asyncio.create_task(self._max_send_loop(), name="health:max-send"),
            asyncio.create_task(self._deepseek_loop(), name="health:deepseek"),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _max_auth_loop(self) -> None:
        while True:
            ok = await self.check_max_auth()
            delay = 30 if not ok and self.max_auth.consecutive_failures == 1 else 300
            await asyncio.sleep(delay)

    async def _max_send_loop(self) -> None:
        if self.max_test_user_id is None:
            return
        while True:
            ok = await self.check_max_send()
            delay = 30 if not ok and self.max_send.consecutive_failures == 1 else 1800
            await asyncio.sleep(delay)

    async def _deepseek_loop(self) -> None:
        while True:
            ok = await self.check_deepseek()
            # The normal synthetic check is hourly. A single failure is retried
            # once after a minute before it can make readiness fail.
            delay = 60 if not ok and self.deepseek.consecutive_failures == 1 else 3600
            await asyncio.sleep(delay)

    async def check_max_auth(self) -> bool:
        started = time.monotonic()
        if self.bot is None or self.bot.session is None:
            self.max_auth.failure(started, "MAX polling session is not initialized")
            return False
        try:
            async def request() -> int:
                response = await self.bot.session.get("me")
                status = response.status
                await response.read()
                return status

            status = await asyncio.wait_for(request(), timeout=10)
            if status != 200:
                self.max_auth.failure(started, f"MAX /me returned HTTP {status}", status)
                return False
            self.max_auth.success(started, status)
            return True
        except Exception as exc:
            self.max_auth.failure(started, exc)
            return False

    async def check_max_send(self) -> bool:
        started = time.monotonic()
        if self.max_test_user_id is None:
            self.max_send.status = "disabled"
            return True
        if self.bot is None or self.bot.session is None:
            self.max_send.failure(started, "MAX polling session is not initialized")
            return False
        try:
            async def request() -> tuple[int, dict[str, Any]]:
                response = await self.bot.session.post(
                    "messages",
                    params={"user_id": self.max_test_user_id},
                    json={
                        "text": f"🩺 {self.service_name}: техническая проверка отправки",
                        "notify": False,
                    },
                )
                status = response.status
                try:
                    payload = await response.json(content_type=None)
                except Exception:
                    await response.read()
                    payload = {}
                return status, payload

            status, payload = await asyncio.wait_for(request(), timeout=10)
            if status not in range(200, 300) or not payload.get("success", True):
                code = payload.get("code") or payload.get("message") or "send failed"
                self.max_send.failure(
                    started, f"MAX send returned HTTP {status}: {code}", status
                )
                return False
            self.max_send.success(started, status)
            return True
        except Exception as exc:
            self.max_send.failure(started, exc)
            return False

    async def check_deepseek(self) -> bool:
        started = time.monotonic()
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        completion = {
            "model": self.deepseek_model,
            "messages": [
                {
                    "role": "user",
                    "content": "Ответь только словом OK.",
                }
            ],
            "max_tokens": 8,
            "temperature": 0,
            "thinking": {"type": "disabled"},
        }
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://api.deepseek.com/v1/models", headers=headers
                ) as response:
                    models_status = response.status
                    if models_status != 200:
                        await response.read()
                        self.deepseek.failure(
                            started,
                            f"DeepSeek /models returned HTTP {models_status}",
                            models_status,
                        )
                        return False
                    models = await response.json(content_type=None)
                model_ids = {
                    str(item.get("id")) for item in models.get("data", []) if item
                }
                if self.deepseek_model not in model_ids:
                    self.deepseek.failure(
                        started, f"DeepSeek model {self.deepseek_model!r} is unavailable"
                    )
                    return False
                async with session.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=completion,
                ) as response:
                    completion_status = response.status
                    if completion_status != 200:
                        await response.read()
                        self.deepseek.failure(
                            started,
                            f"DeepSeek completion returned HTTP {completion_status}",
                            completion_status,
                        )
                        return False
                    result = await response.json(content_type=None)
                choices = result.get("choices") or []
                content = (
                    ((choices[0].get("message") or {}).get("content") or "").strip()
                    if choices
                    else ""
                )
                if not content:
                    self.deepseek.failure(started, "DeepSeek completion returned empty content")
                    return False
            self.deepseek.success(started, 200)
            return True
        except Exception as exc:
            self.deepseek.failure(started, exc)
            return False

    async def _database_payload(self) -> tuple[dict[str, Any], bool]:
        started = time.monotonic()
        try:
            async def query() -> Any:
                pool = await self.database.get_pool()
                async with pool.acquire() as connection:
                    return await connection.fetchval("SELECT 1")

            value = await asyncio.wait_for(query(), timeout=3)
            if value != 1:
                raise RuntimeError(f"SELECT 1 returned {value!r}")
            latency = round((time.monotonic() - started) * 1000)
            return {"status": "ok", "latency_ms": latency, "error": None}, True
        except Exception as exc:
            latency = round((time.monotonic() - started) * 1000)
            return {
                "status": "error",
                "latency_ms": latency,
                "error": _safe_error(exc),
            }, False

    def _polling_payload(self) -> tuple[dict[str, Any], bool]:
        payload = self.polling.payload()
        if self.polling.last_success_at is None:
            age = None
            healthy = time.monotonic() - self.started_monotonic <= 180
            if not healthy:
                payload["status"] = "error"
                payload["error"] = "polling has never completed successfully"
        else:
            age = max(0, int((_utc_now() - self.polling.last_success_at).total_seconds()))
            healthy = age <= 180
            if not healthy:
                payload["status"] = "error"
                payload["error"] = f"last successful polling request was {age}s ago"
        payload["last_success_age_seconds"] = age
        return payload, healthy

    async def readiness(self) -> tuple[dict[str, Any], int]:
        database, database_ok = await self._database_payload()
        polling, polling_ok = self._polling_payload()
        checks = {
            "database": database,
            "polling": polling,
            "max_auth": self.max_auth.payload(),
            "max_send": self.max_send.payload(),
            "deepseek": self.deepseek.payload(),
        }
        failures = []
        if not database_ok:
            failures.append("database")
        if not polling_ok:
            failures.append("polling")
        if self.max_auth.status in {"starting", "error"}:
            failures.append("max_auth")
        if self.max_send.status in {"starting", "error"}:
            failures.append("max_send")
        if self.deepseek.status == "error":
            failures.append("deepseek")
        status_code = 503 if failures else 200
        return {
            "status": "error" if failures else "ok",
            "service": self.service_name,
            "version": self.version,
            "failures": failures,
            "checks": checks,
        }, status_code

    def live_payload(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": self.service_name,
            "version": self.version,
            "uptime_seconds": int(time.monotonic() - self.started_monotonic),
        }


health_runtime = HealthRuntime()


async def live_handler(_: web.Request) -> web.Response:
    return web.json_response(health_runtime.live_payload())


async def ready_handler(_: web.Request) -> web.Response:
    payload, status = await health_runtime.readiness()
    return web.json_response(payload, status=status)


async def details_handler(request: web.Request) -> web.Response:
    token = os.getenv("HEALTH_DETAILS_TOKEN", "").strip()
    supplied = request.headers.get("Authorization", "")
    if not token:
        return web.json_response({"error": "details endpoint is disabled"}, status=503)
    if not hmac.compare_digest(supplied, f"Bearer {token}"):
        return web.json_response({"error": "unauthorized"}, status=401)
    payload, _ = await health_runtime.readiness()
    payload["uptime_seconds"] = int(time.monotonic() - health_runtime.started_monotonic)
    return web.json_response(payload)
