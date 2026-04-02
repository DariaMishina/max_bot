"""
Главный entry point для Max-бота — адаптировано с aiogram на aiomax.

Ключевые отличия:
- aiomax.Bot является главным роутером (вместо aiogram.Dispatcher)
- Роутеры добавляются через bot.add_router(router) вместо dp.include_routers()
- Запуск через await bot.start_polling() вместо await dp.start_polling(bot)
- @bot.on_ready() для действий при запуске (регистрация команд и т.д.)
"""
import asyncio
import logging
import os
from typing import Optional, List

import aiomax
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from handlers import common, feedback, divination, pay, daily_card
from main.botdef import bot
from main.database import Database


async def main():
    logging.basicConfig(filename="bot.log", encoding="utf-8", level=logging.INFO)

    # Добавляем роутеры к боту
    # Порядок важен: common — первый (обрабатывает /start, /cancel),
    # feedback — рано (до unknown_command),
    # pay — перед divination (приоритет обработчиков оплаты)
    bot.add_router(common.router)
    bot.add_router(feedback.router)
    bot.add_router(pay.router)
    bot.add_router(divination.router)
    bot.add_router(daily_card.router)

    # ==================== НАСТРОЙКА ОТПРАВКИ КАРТЫ ДНЯ ====================
    DAILY_CARD_USER_IDS: Optional[List[int]] = None
    DAILY_CARD_HOUR = 9
    DAILY_CARD_MINUTE = 25
    # ======================================================================

    # Настраиваем APScheduler для отправки карты дня
    scheduler = AsyncIOScheduler()

    async def send_daily_card_job():
        """Задача для отправки карты дня пользователям"""
        try:
            from handlers.daily_card import send_daily_card_to_all_users

            user_ids = DAILY_CARD_USER_IDS

            if user_ids:
                logging.info(f"Sending daily card to {len(user_ids)} specified users")
            else:
                logging.info("Sending daily card to all users from database")

            results = await send_daily_card_to_all_users(user_ids)
            logging.info(f"Daily card job completed: {results}")
        except Exception as e:
            logging.error(f"Error in daily card job: {e}", exc_info=True)

    scheduler.add_job(
        send_daily_card_job,
        trigger=CronTrigger(
            hour=DAILY_CARD_HOUR,
            minute=DAILY_CARD_MINUTE,
            timezone='Europe/Moscow'
        ),
        id='daily_card_morning',
        name='Отправка карты дня утром',
        replace_existing=True
    )

    async def reconcile_pending_payments_job():
        """Сверка pending-платежей с ЮKassa: если оплачен — зачисляем баланс."""
        try:
            from main.config_reader import config as cfg
            if not cfg.yookassa_shop_id or not cfg.yookassa_secret_key:
                return

            from main.database import (
                get_stale_pending_payments,
                update_payment_status,
                process_successful_payment as db_process,
            )
            from handlers.pay import check_payment_status, PACKAGES_BY_ID

            stale = await get_stale_pending_payments(minutes=15)
            if not stale:
                return

            logging.info(f"Reconciliation: checking {len(stale)} stale pending payment(s)")
            for p in stale:
                pid = p['payment_id']
                try:
                    info = await check_payment_status(pid)
                    actual_status = info.get('status')

                    if actual_status == 'succeeded':
                        await db_process(pid, yookassa_metadata=info)
                        logging.info(f"Reconciliation: payment {pid} -> succeeded, balance updated")
                    elif actual_status == 'canceled':
                        await update_payment_status(pid, 'canceled')
                        logging.info(f"Reconciliation: payment {pid} -> canceled")
                except Exception as e:
                    logging.error(f"Reconciliation error for {pid}: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Error in reconcile_pending_payments_job: {e}", exc_info=True)

    scheduler.add_job(
        reconcile_pending_payments_job,
        trigger=IntervalTrigger(minutes=10),
        id='reconcile_pending_payments',
        name='Сверка pending-платежей с ЮKassa',
        replace_existing=True
    )

    scheduler.start()
    logging.info(f"APScheduler started - daily card will be sent at {DAILY_CARD_HOUR:02d}:{DAILY_CARD_MINUTE:02d} (Moscow time)")
    logging.info("APScheduler: pending payments reconciliation every 10 minutes")

    # Запускаем webhook сервер для ЮKassa (если настроены ключи)
    webhook_runner = None
    try:
        from main.config_reader import config
        from webhook_server import start_webhook_server
        if config.yookassa_shop_id and config.yookassa_secret_key:
            port = int(os.environ.get('PORT', 8081))
            webhook_runner = await start_webhook_server(port)
            logging.info(f"Webhook server started for YooKassa notifications on port {port}")
        else:
            logging.info("YooKassa keys not configured, webhook server not started")
    except Exception as e:
        logging.warning(f"Could not start webhook server: {e}")

    # Запускаем бота (long polling)
    try:
        await bot.start_polling()
    finally:
        scheduler.shutdown()
        logging.info("APScheduler stopped")
        await Database.close_pool()
        if webhook_runner:
            await webhook_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
