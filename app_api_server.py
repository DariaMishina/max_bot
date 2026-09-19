#!/usr/bin/env python3
"""
HTTP API Android-приложения «Гадание AI».

Запуск (отдельно от bot.py и webhook_server.py):
  python app_api_server.py

Порт: APP_API_PORT (по умолчанию 8083).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from app.auth_tokens import issue_token_pair, verify_access_token, verify_refresh_token, revoke_refresh_token
from app.config import app_config
from app.database import (
    AppDatabase,
    create_guest,
    get_divination,
    get_user,
    get_user_balance,
    list_divinations,
    touch_user,
    save_feedback,
    delete_user,
)
from app.divination_service import DivinationError, run_tarot, run_follow_up
from handlers.tarot_cards import get_card_info, get_random_cards

ROOT = Path(__file__).resolve().parent
STATIC_IMAGES = ROOT / "static" / "images"

CATALOG_PACKAGES = [
    {"id": "3_spreads", "name": "3 расклада", "price_rub": 99},
    {"id": "10_spreads", "name": "10 раскладов", "price_rub": 179},
    {"id": "20_spreads", "name": "20 раскладов", "price_rub": 289},
    {"id": "30_spreads", "name": "30 раскладов", "price_rub": 399},
    {"id": "unlimited", "name": "Безлимит на месяц", "price_rub": 599, "subscription": True},
]

OPENAPI = {
    "title": "Gadanie AI App API",
    "version": "1.0.0",
    "basePath": "/v1",
    "endpoints": [
        "POST /v1/auth/guest",
        "POST /v1/auth/refresh",
        "GET /v1/me",
        "GET /v1/me/balance",
        "GET /v1/me/history",
        "POST /v1/divinations/tarot",
        "GET /v1/divinations/{id}",
        "GET /v1/catalog",
        "GET /v1/tarot/deck",
        "POST /v1/divinations/{id}/follow-up",
        "POST /v1/me/feedback",
        "DELETE /v1/me",
        "GET /health",
        "GET /static/images/{card_id}.png",
    ],
}


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(type(obj))


def json_response(data: Any, *, status: int = 200) -> Response:
    return web.json_response(data, status=status, dumps=lambda o: json.dumps(o, default=_json_default, ensure_ascii=False))


def error_response(code: str, message: str, *, status: int = 400) -> Response:
    return json_response({"error": code, "message": message}, status=status)


def _balance_payload(balance: Optional[dict]) -> dict:
    if not balance:
        return {
            "free_divinations_remaining": 0,
            "paid_divinations_remaining": 0,
            "unlimited_until": None,
            "total_divinations_used": 0,
        }
    return {
        "free_divinations_remaining": balance["free_divinations_remaining"],
        "paid_divinations_remaining": balance["paid_divinations_remaining"],
        "unlimited_until": balance.get("unlimited_until"),
        "total_divinations_used": balance.get("total_divinations_used", 0),
    }


def _card_payload(card_id: str, request: Request) -> dict:
    info = get_card_info(card_id)
    base = app_config.app_api_public_url.rstrip("/") or f"{request.scheme}://{request.host}"
    return {
        "id": card_id,
        "name": info["name"],
        "image_url": f"{base}/static/images/{card_id}.png",
    }


async def _read_json(request: Request) -> dict:
    if not request.body_exists:
        return {}
    try:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    except json.JSONDecodeError:
        return {}


def _user_id_from_request(request: Request) -> Optional[uuid.UUID]:
    return request.get("app_user_id")


async def health_handler(_request: Request) -> Response:
    return web.Response(text="OK")


async def docs_handler(_request: Request) -> Response:
    return json_response(OPENAPI)


async def guest_auth_handler(request: Request) -> Response:
    body = await _read_json(request)
    install_id = body.get("install_id")
    if install_id is not None:
        install_id = str(install_id).strip() or None
    user_id = await create_guest(install_id=install_id)
    tokens = await issue_token_pair(user_id)
    balance = await get_user_balance(user_id)
    return json_response({
        **tokens,
        "balance": _balance_payload(balance),
    })


async def refresh_auth_handler(request: Request) -> Response:
    body = await _read_json(request)
    raw = (body.get("refresh_token") or "").strip()
    if not raw:
        return error_response("invalid_token", "refresh_token обязателен", status=401)
    user_id = await verify_refresh_token(raw)
    if not user_id:
        return error_response("invalid_token", "Недействительный refresh_token", status=401)
    await revoke_refresh_token(raw)
    tokens = await issue_token_pair(user_id)
    return json_response(tokens)


async def me_handler(request: Request) -> Response:
    user_id = _user_id_from_request(request)
    assert user_id
    user = await get_user(user_id)
    if not user:
        return error_response("not_found", "Пользователь не найден", status=404)
    balance = await get_user_balance(user_id)
    await touch_user(user_id)
    return json_response({
        "user_id": str(user_id),
        "is_guest": user["is_guest"],
        "balance": _balance_payload(balance),
    })


async def me_balance_handler(request: Request) -> Response:
    user_id = _user_id_from_request(request)
    assert user_id
    balance = await get_user_balance(user_id)
    if not balance:
        return error_response("not_found", "Баланс не найден", status=404)
    return json_response(_balance_payload(balance))


async def me_history_handler(request: Request) -> Response:
    user_id = _user_id_from_request(request)
    assert user_id
    try:
        limit = max(1, min(int(request.query.get("limit", "20")), 50))
        before_id = int(request.query["before_id"]) if "before_id" in request.query else None
    except ValueError:
        return error_response("invalid_page", "Некорректная страница истории")
    items = await list_divinations(user_id, limit=limit + 1, before_id=before_id)
    return json_response({"items": items[:limit], "next_before_id": items[limit - 1]["id"] if len(items) > limit else None})


async def tarot_handler(request: Request) -> Response:
    user_id = _user_id_from_request(request)
    assert user_id
    body = await _read_json(request)
    question = body.get("question", "")
    selection = body.get("selection", "manual")
    if not isinstance(question, str) or selection not in ("manual", "random"):
        return error_response("invalid_request", "Проверьте вопрос и способ выбора карт")
    try:
        request_id = uuid.UUID(body["request_id"]) if body.get("request_id") else None
    except (ValueError, TypeError, AttributeError):
        return error_response("invalid_request", "Некорректный request_id")
    card_ids = body.get("card_ids")

    try:
        if selection == "random":
            result = await run_tarot(user_id, question, random_cards=True, request_id=request_id)
        else:
            if not isinstance(card_ids, list):
                return error_response("invalid_cards", "card_ids должен быть массивом из 3 id")
            result = await run_tarot(user_id, question, card_ids=[str(c) for c in card_ids], request_id=request_id)
    except DivinationError as e:
        status = 402 if e.code == "no_balance" else 400
        return error_response(e.code, str(e), status=status)

    free_after = result.balance_after.get("free_divinations_remaining", 0)
    paid_after = result.balance_after.get("paid_divinations_remaining", 0)
    unlimited = result.balance_after.get("unlimited_until")
    paywall = free_after == 0 and paid_after == 0 and not (
        unlimited and unlimited > datetime.now()
    )

    detail = await get_divination(result.divination_id, user_id)
    follow_ups = (detail or {}).get("follow_ups", [])
    return json_response({
        "divination_id": result.divination_id,
        "question": result.question,
        "cards": [_card_payload(cid, request) for cid in result.card_ids],
        "interpretation": result.interpretation,
        "is_free": result.is_free,
        "balance": _balance_payload(result.balance_after),
        "paywall": paywall,
        "created_at": (detail or {}).get("created_at"),
        "follow_ups": follow_ups,
        "follow_ups_remaining": max(0, (2 if result.is_free else 5) - len(follow_ups)),
    })


async def divination_detail_handler(request: Request) -> Response:
    user_id = _user_id_from_request(request)
    assert user_id
    try:
        divination_id = int(request.match_info["id"])
    except (KeyError, ValueError):
        return error_response("invalid_id", "Некорректный id расклада")
    row = await get_divination(divination_id, user_id)
    if not row:
        return error_response("not_found", "Расклад не найден", status=404)
    cards = row.get("selected_cards") or []
    return json_response({
        **row,
        "cards": [_card_payload(cid, request) for cid in cards],
        "follow_ups_remaining": max(0, (2 if row["is_free"] else 5) - len(row.get("follow_ups", []))),
    })


async def catalog_handler(_request: Request) -> Response:
    return json_response({
        "packages": CATALOG_PACKAGES,
        "payment_methods": ["rustore", "yookassa"],
        "consultations": [
            {"id": "consultation_basic", "name": "Базовая консультация", "price_rub": 500},
            {"id": "consultation_detailed", "name": "Подробная консультация", "price_rub": 1500},
        ],
        "tarologist_url": app_config.app_tarologist_profile_url or None,
        "billing_enabled": False,
    })


async def tarot_deck_handler(request: Request) -> Response:
    return json_response({"cards": [_card_payload(cid, request) for cid in get_random_cards(9)]})


async def follow_up_handler(request: Request) -> Response:
    body = await _read_json(request)
    try:
        divination_id = int(request.match_info["id"])
        request_id = uuid.UUID(body.get("request_id", ""))
    except (ValueError, TypeError, AttributeError):
        return error_response("invalid_request", "Некорректный id запроса")
    question = body.get("question", "")
    if not isinstance(question, str):
        return error_response("invalid_request", "Вопрос должен быть текстом")
    try:
        result = await run_follow_up(request["app_user_id"], divination_id, question, request_id)
    except DivinationError as e:
        return error_response(e.code, str(e), status=404 if e.code == "not_found" else 409 if e.code == "follow_up_limit" else 400)
    return json_response(result)


async def feedback_handler(request: Request) -> Response:
    body = await _read_json(request)
    message = body.get("message", "")
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        return error_response("invalid_message", "Сообщение должно содержать от 1 до 2000 символов")
    await save_feedback(request["app_user_id"], message.strip())
    return json_response({"ok": True})


async def delete_me_handler(request: Request) -> Response:
    await delete_user(request["app_user_id"])
    return json_response({"ok": True})


async def static_card_image_handler(request: Request) -> Response:
    card_id = request.match_info.get("card_id", "")
    if ".." in card_id or "/" in card_id:
        raise web.HTTPNotFound()
    path = STATIC_IMAGES / f"{card_id}.png"
    if not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(path)


@web.middleware
async def auth_middleware(request: Request, handler: Callable) -> Response:
    path = request.path
    if path in ("/health", "/v1/docs") or path.startswith("/static/"):
        return await handler(request)
    if path in ("/v1/auth/guest", "/v1/auth/refresh") and request.method == "POST":
        return await handler(request)

    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return error_response("unauthorized", "Требуется Authorization: Bearer …", status=401)
    token = auth[7:].strip()
    user_id = verify_access_token(token)
    if not user_id:
        return error_response("unauthorized", "Недействительный или просроченный токен", status=401)
    if request.method != "DELETE" and not await get_user(user_id):
        return error_response("unauthorized", "Данные гостя удалены", status=401)
    request["app_user_id"] = user_id
    return await handler(request)


@web.middleware
async def logging_middleware(request: Request, handler: Callable) -> Response:
    start = time.time()
    try:
        response = await handler(request)
        logging.info("%s %s -> %s (%.2fs)", request.method, request.path, response.status, time.time() - start)
        return response
    except web.HTTPException as error:
        return error
    except Exception:
        logging.exception("%s %s failed after %.2fs", request.method, request.path, time.time() - start)
        return error_response("internal_error", "Внутренняя ошибка", status=500)


def create_app() -> web.Application:
    app = web.Application(middlewares=[logging_middleware, auth_middleware], client_max_size=32 * 1024)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/v1/docs", docs_handler)
    app.router.add_post("/v1/auth/guest", guest_auth_handler)
    app.router.add_post("/v1/auth/refresh", refresh_auth_handler)
    app.router.add_get("/v1/me", me_handler)
    app.router.add_get("/v1/me/balance", me_balance_handler)
    app.router.add_get("/v1/me/history", me_history_handler)
    app.router.add_post("/v1/divinations/tarot", tarot_handler)
    app.router.add_get(r"/v1/divinations/{id}", divination_detail_handler)
    app.router.add_get("/v1/catalog", catalog_handler)
    app.router.add_get("/v1/tarot/deck", tarot_deck_handler)
    app.router.add_post("/v1/divinations/{id}/follow-up", follow_up_handler)
    app.router.add_post("/v1/me/feedback", feedback_handler)
    app.router.add_delete("/v1/me", delete_me_handler)
    app.router.add_get("/static/images/{card_id}.png", static_card_image_handler)
    return app


async def start_server() -> None:
    port = app_config.app_api_port
    await AppDatabase.get_pool()
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("App API listening on 0.0.0.0:%s", port)


async def _run_forever() -> None:
    await start_server()
    while True:
        await asyncio.sleep(3600)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        asyncio.run(_run_forever())
    except KeyboardInterrupt:
        logging.info("App API stopped")


if __name__ == "__main__":
    main()
