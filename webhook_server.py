#!/usr/bin/env python3
"""
Webhook сервер для приема уведомлений от ЮKassa — адаптировано для Max (aiomax).

Ключевые отличия от Telegram-версии:
- FSM: используется bot.storage напрямую (aiomax.fsm.FSMStorage), не aiogram FSMContext
- bot.send_message: user_id= вместо chat_id=, keyboard= вместо reply_markup=, format='html'
"""
import asyncio
import logging
import json
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from main.botdef import bot
from main.config_reader import config
from handlers.pay import PAYMENT_PACKAGES
from keyboards.main_menu import make_back_to_menu_kb
from main.database import (
    update_payment_status, process_successful_payment as db_process_successful_payment,
    Database, can_user_divinate, use_divination, save_divination, get_user_balance,
    get_pending_question, delete_pending_question
)
from main.metrika_mp import send_conversion_event
from main.conversions import save_conversion

# Хранилище обработанных платежей для защиты от дубликатов
processed_payments = set()


async def yookassa_webhook_handler(request: Request) -> Response:
    """Обработчик webhook от ЮKassa"""
    try:
        logging.info("=== YOOKASSA WEBHOOK RECEIVED ===")
        logging.info(f"Request path: {request.path}")
        logging.info(f"Request method: {request.method}")
        logging.info(f"Request headers: {dict(request.headers)}")
        logging.info(f"Request remote: {request.remote}")

        request_body = await request.read()
        logging.info(f"Request body length: {len(request_body)} bytes")

        if not request_body:
            logging.warning("Empty request body received")
            return web.Response(text="Empty body", status=400)

        try:
            data = json.loads(request_body.decode('utf-8'))
        except UnicodeDecodeError as e:
            logging.error(f"Failed to decode request body: {e}")
            return web.Response(text="Invalid encoding", status=400)

        logging.info(f"Webhook data: {json.dumps(data, ensure_ascii=False, indent=2)}")

        event_type = data.get("event")
        payment_object = data.get("object", {})

        if not payment_object:
            logging.warning(f"Payment object not found in webhook data: {data}")
            return web.Response(text="OK", status=200)

        if event_type != "payment.succeeded":
            logging.info(f"Webhook event type: {event_type}, skipping")
            return web.Response(text="OK", status=200)

        payment_id = payment_object.get("id")
        status = payment_object.get("status")
        metadata = payment_object.get("metadata", {})

        if not payment_id:
            logging.error("Payment ID not found in webhook data")
            return web.Response(text="OK", status=200)

        if payment_id in processed_payments:
            logging.info(f"Payment {payment_id} already processed, skipping")
            return web.Response(text="OK", status=200)

        if status != "succeeded":
            logging.info(f"Payment {payment_id} status is {status}, not succeeded")
            return web.Response(text="OK", status=200)

        user_id = metadata.get("user_id")
        package_id = metadata.get("package_id")
        email = metadata.get("email")

        logging.info(
            f"Payment succeeded: payment_id={payment_id}, user_id={user_id}, "
            f"package_id={package_id}, status={status}"
        )

        if not user_id:
            logging.error("User ID not found in payment metadata")
            return web.Response(text="OK", status=200)

        user_id = int(user_id)

        package = None
        if package_id and package_id in PAYMENT_PACKAGES:
            package = PAYMENT_PACKAGES[package_id]

        # Отправляем уведомление пользователю
        try:
            package_description = package.get('description', 'раскладам') if package else 'раскладам'
            email_text = f"Чек отправлен на email: {email}\n\n" if email else ""

            success_text = (
                f"✅ <b>Оплата успешно завершена!</b>\n\n"
                f"Спасибо за покупку! Теперь у тебя есть доступ к {package_description}.\n\n"
                f"{email_text}"
                f"🔮 Можешь начинать гадать! Используй команду /divination или выбери гадание из меню."
            )

            await bot.send_message(
                success_text,
                user_id=user_id,
                keyboard=make_back_to_menu_kb(),
                format='html'
            )

            logging.info(f"Payment notification sent to user {user_id}")

            # Очищаем FSM состояние пользователя после успешной оплаты
            try:
                cursor = bot.storage.get_cursor(user_id)
                current_state = cursor.get_state()
                logging.info(f"Current FSM state for user {user_id} before clear: {current_state}")
                cursor.clear()
                logging.info(f"FSM state cleared for user {user_id} after successful payment")
            except Exception as e:
                logging.error(f"Could not clear FSM state for user {user_id}: {e}", exc_info=True)

            # Обрабатываем успешный платеж в БД
            try:
                await update_payment_status(payment_id, 'succeeded', payment_object)
                await db_process_successful_payment(payment_id)
                logging.info(f"Payment {payment_id} processed successfully in database")

                asyncio.create_task(send_conversion_event(user_id, 'purchase'))
            except Exception as e:
                logging.error(f"Error processing payment {payment_id} in database: {e}", exc_info=True)

            processed_payments.add(payment_id)

            if len(processed_payments) > 1000:
                processed_payments.clear()
                processed_payments.add(payment_id)

        except Exception as e:
            logging.error(f"Error sending payment notification to user {user_id}: {e}", exc_info=True)

        return web.Response(text="OK", status=200)

    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in webhook: {e}")
        try:
            request_body = await request.read()
            if request_body:
                logging.error(f"Request body (first 500 chars): {request_body.decode('utf-8', errors='ignore')[:500]}")
        except Exception:
            pass
        return web.Response(text="Invalid JSON", status=400)
    except Exception as e:
        logging.error(f"Error processing webhook: {e}", exc_info=True)
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return web.Response(text="OK", status=200)


async def webapp_cards_handler(request: Request) -> Response:
    """Обработчик выбора карт из мини-приложения (WebApp)"""
    try:
        body = await request.read()
        if not body:
            return _json_error("Empty body", 400)

        data = json.loads(body.decode('utf-8'))
        user_id = data.get('user_id')
        selected_cards = data.get('selected_cards', [])

        if not user_id:
            return _json_error("user_id is required", 400)
        if len(selected_cards) != 3:
            return _json_error("Exactly 3 cards required", 400)

        user_id = int(user_id)
        logging.info(f"WebApp card selection: user_id={user_id}, cards={selected_cards}")

        question = await get_pending_question(user_id)
        if not question:
            return _json_error("No question found. Start a divination first.", 400)

        can_div, access_type = await can_user_divinate(user_id)
        if not can_div:
            return _json_error("No divinations remaining", 403)

        asyncio.ensure_future(_process_webapp_divination(user_id, question, selected_cards))

        return web.json_response({"status": "ok"})

    except json.JSONDecodeError:
        return _json_error("Invalid JSON", 400)
    except Exception as e:
        logging.error(f"Error in webapp_cards_handler: {e}", exc_info=True)
        return _json_error(f"Internal error: {type(e).__name__}: {e}", 500)


async def _process_webapp_divination(user_id: int, question: str, card_ids: list):
    """Фоновая обработка гадания по картам из мини-приложения"""
    from handlers.tarot_cards import get_card_info, send_card_images
    from handlers.divination import get_chatgpt_response_with_prompt

    try:
        chat_id = user_id
        await send_card_images(bot, chat_id, card_ids, as_media_group=True)

        cards_info = []
        positions = ["Прошлое", "Настоящее", "Будущее"]
        for i, card_id in enumerate(card_ids):
            card = get_card_info(card_id)
            cards_info.append(f"{positions[i]}: {card['name']} — {card['meaning']}")

        system_prompt = (
            "Ты опытный таролог. Проведи детальное и мистическое толкование расклада из 3 карт Таро. "
            "Карты расположены: 1-я — Прошлое, 2-я — Настоящее, 3-я — Будущее. "
            "Проанализируй каждую карту в контексте вопроса пользователя и дай целостную интерпретацию. "
            "Отвечай на русском языке, будь мудрым и проникновенным."
        )
        chatgpt_question = (
            f"Вопрос пользователя: {question}\n\n"
            f"Выпавшие карты:\n" + "\n".join(cards_info) + "\n\n"
            "Дай детальное толкование этого расклада в контексте вопроса пользователя."
        )

        chatgpt_response = await get_chatgpt_response_with_prompt(chatgpt_question, system_prompt)

        balance_before = await get_user_balance(user_id)
        is_free = balance_before and balance_before['free_divinations_remaining'] > 0 if balance_before else True

        used = await use_divination(user_id)
        if not used:
            await bot.send_message(
                "❌ Ошибка при списании гадания.",
                user_id=user_id, keyboard=make_back_to_menu_kb()
            )
            return

        divination_id = await save_divination(
            user_id=user_id, divination_type="Таро", question=question,
            selected_cards=card_ids, interpretation=chatgpt_response, is_free=is_free
        )

        if divination_id:
            try:
                await save_conversion(
                    user_id=user_id, conversion_type='service_usage', divination_type="Таро",
                    metadata={'divination_id': divination_id, 'card_ids': card_ids, 'is_free': is_free, 'method': 'webapp'}
                )
                asyncio.create_task(send_conversion_event(user_id, 'service_usage'))
            except Exception as e:
                logging.error(f"Error saving conversion: {e}", exc_info=True)

        await delete_pending_question(user_id)

        cards_names = [get_card_info(cid)['name'] for cid in card_ids]
        await bot.send_message(
            f"🃏 <b>Результат гадания на Таро</b>\n\n"
            f"<b>Ваш вопрос:</b> <i>«{question}»</i>\n\n"
            f"<b>Карты:</b> {', '.join(cards_names)}\n\n"
            f"<b>Толкование:</b>\n{chatgpt_response}\n\n"
            "🔮 Новый расклад — нажми ◀ В меню",
            user_id=user_id, keyboard=make_back_to_menu_kb(), format='html'
        )

        logging.info(f"WebApp divination completed for user {user_id}")

    except Exception as e:
        logging.error(f"Error processing webapp divination for user {user_id}: {e}", exc_info=True)
        try:
            await bot.send_message(
                "❌ Ошибка при гадании. Попробуйте ещё раз.",
                user_id=user_id, keyboard=make_back_to_menu_kb()
            )
        except Exception:
            pass


def _json_error(message: str, status: int) -> Response:
    return web.json_response({"error": message}, status=status)


async def health_check(request: Request) -> Response:
    """Проверка здоровья сервера"""
    try:
        pool = await Database.get_pool()
        if pool:
            return web.Response(text="OK", status=200)
        else:
            return web.Response(text="Database not available", status=503)
    except Exception as e:
        logging.error(f"Health check failed: {e}", exc_info=True)
        return web.Response(text=f"Error: {str(e)}", status=503)


async def root_handler(request: Request) -> Response:
    """Обработчик корневого пути для отладки"""
    if request.method == "POST":
        try:
            body = await request.read()
            data = json.loads(body.decode('utf-8'))
            logging.warning(f"POST request to root path / - data: {json.dumps(data, ensure_ascii=False, indent=2)}")
            logging.warning(f"Webhook URL should be: {request.url.scheme}://{request.host}/webhook/yookassa")
        except Exception:
            logging.warning(f"POST request to root path / - could not parse body")

    return web.Response(
        text="Webhook endpoint is at /webhook/yookassa",
        status=404
    )


async def cors_preflight(request: Request) -> Response:
    """Обработчик CORS preflight (OPTIONS)"""
    return web.Response(
        status=204,
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
    )


def create_webhook_app() -> web.Application:
    """Создание приложения для webhook"""
    app = web.Application()

    app.router.add_post('/webhook/yookassa', yookassa_webhook_handler)
    app.router.add_post('/api/webapp/cards', webapp_cards_handler)
    app.router.add_options('/api/webapp/cards', cors_preflight)
    app.router.add_get('/health', health_check)
    app.router.add_post('/', root_handler)
    app.router.add_get('/', root_handler)

    return app


async def start_webhook_server(port: int = None):
    """Запуск webhook сервера. Порт из PORT (по умолчанию 8081, чтобы не конфликтовать с tg_bot на 8080)."""
    import os

    if port is None:
        port = int(os.environ.get('PORT', 8081))

    service_url = os.environ.get('SERVICE_URL') or os.environ.get('RENDER_EXTERNAL_URL') or 'https://max-bot.onrender.com'

    logging.info(f"Starting webhook server on port {port}")

    try:
        pool = await Database.get_pool()
        if pool:
            logging.info("Database connection pool initialized successfully")
        else:
            logging.warning("Database connection pool is None")
    except Exception as e:
        logging.error(f"Failed to initialize database pool: {e}", exc_info=True)
        logging.warning("Continuing without database pool - will retry on first request")

    app = create_webhook_app()

    @web.middleware
    async def cors_middleware(request, handler):
        import time
        start_time = time.time()
        try:
            response = await handler(request)
            process_time = time.time() - start_time
            logging.info(f"{request.method} {request.path} - {response.status} ({process_time:.3f}s)")
        except Exception as e:
            process_time = time.time() - start_time
            logging.error(f"{request.method} {request.path} - ERROR after {process_time:.3f}s: {e}", exc_info=True)
            response = web.json_response({"error": "Internal server error"}, status=500)
        if request.path.startswith('/api/'):
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    app.middlewares.append(cors_middleware)

    runner = web.AppRunner(app)
    await runner.setup()

    try:
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logging.info(f"Webhook server started successfully on 0.0.0.0:{port}")
        logging.info(f"Webhook URL: {service_url}/webhook/yookassa")
        logging.info(f"Health check: {service_url}/health")
    except Exception as e:
        logging.error(f"Failed to start webhook server: {e}", exc_info=True)
        raise

    return runner


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        runner = None
        try:
            runner = await start_webhook_server()
            logging.info("Webhook server is running. Press Ctrl+C to stop.")
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logging.info("Shutting down webhook server...")
        except Exception as e:
            logging.error(f"Error in webhook server: {e}", exc_info=True)
            raise
        finally:
            if runner:
                await runner.cleanup()
            await Database.close_pool()
            logging.info("Webhook server stopped")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Webhook server stopped by user")
