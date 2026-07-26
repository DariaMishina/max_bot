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

    # ==================== EVENT-DRIVEN NUDGES ====================
    BROADCAST_CRON_HOURS = '10-20'
    BROADCAST_CRON_MINUTES = '0,30'
    # =============================================================

    async def inactivity_nudges_job():
        """Event-driven nudges: платники (B) + бесплатные (C1–C4)."""
        try:
            from main.inactivity_nudges import process_inactivity_nudges
            await process_inactivity_nudges()
        except Exception as e:
            logging.error(f"Error in inactivity nudges job: {e}", exc_info=True)

    scheduler.add_job(
        inactivity_nudges_job,
        trigger=IntervalTrigger(minutes=2),
        id='inactivity_nudges',
        name='Event-driven nudges (платники + бесплатные)',
        replace_existing=True,
    )

    async def expired_access_reminder_job():
        """Триггер A: серия day0–day7 после истечения платного доступа."""
        try:
            from main.expired_access_reminders import process_expired_access_reminders
            results = await process_expired_access_reminders()
            if any(v for k, v in results.items() if k != 'by_stage' and v) or results.get('by_stage'):
                logging.info(f"Expired access reminders job completed: {results}")
        except Exception as e:
            logging.error(f"Error in expired access reminders job: {e}", exc_info=True)

    scheduler.add_job(
        expired_access_reminder_job,
        trigger=CronTrigger(
            hour=BROADCAST_CRON_HOURS,
            minute=BROADCAST_CRON_MINUTES,
            timezone='Europe/Moscow'
        ),
        id='expired_access_reminders',
        name='Expired access reminders (10:00–20:00 MSK, day0–day7)',
        replace_existing=True
    )

    scheduler.add_job(
        reconcile_pending_payments_job,
        trigger=IntervalTrigger(minutes=10),
        id='reconcile_pending_payments',
        name='Сверка pending-платежей с ЮKassa',
        replace_existing=True
    )

    async def payment_reminders_job():
        """Напоминания об оплате: 10м, 1ч, 3ч, 12ч, 24ч, 48ч."""
        try:
            from main.payment_reminders import process_payment_reminders
            results = await process_payment_reminders()
            if results['sent'] or results['failed']:
                logging.info(f"Payment reminders job completed: {results}")
        except Exception as e:
            logging.error(f"Error in payment reminders job: {e}", exc_info=True)

    scheduler.add_job(
        payment_reminders_job,
        trigger=IntervalTrigger(minutes=2),
        id='payment_reminders',
        name='Напоминания об оплате (10м / 1ч / 3ч / 12ч / 24ч / 48ч)',
        replace_existing=True
    )

    TAROLOGIST_REMINDER_HOUR = 16
    TAROLOGIST_REMINDER_MINUTE = 30

    async def tarologist_reminder_job():
        """Рассылка напоминания о тарологе: ср/вс 16:30 MSK."""
        try:
            from main.tarologist_reminders import process_tarologist_reminders
            results = await process_tarologist_reminders()
            logging.info(f"Tarologist reminder job completed: {results}")
        except Exception as e:
            logging.error(f"Error in tarologist reminder job: {e}", exc_info=True)

    scheduler.add_job(
        tarologist_reminder_job,
        trigger=CronTrigger(
            day_of_week='wed,sun',
            hour=TAROLOGIST_REMINDER_HOUR,
            minute=TAROLOGIST_REMINDER_MINUTE,
            timezone='Europe/Moscow',
        ),
        id='tarologist_reminder',
        name='Напоминание о тарологе Диане (ср/вс 16:30 MSK)',
        replace_existing=True,
    )

    scheduler.start()
    logging.info(f"APScheduler started - daily card will be sent at {DAILY_CARD_HOUR:02d}:{DAILY_CARD_MINUTE:02d} (Moscow time)")
    logging.info("APScheduler: inactivity nudges every 2 minutes (paid + free segments)")
    logging.info(
        f"APScheduler: expired access reminders daily {BROADCAST_CRON_HOURS} MSK "
        f"(every {BROADCAST_CRON_MINUTES} min, day0–day7)"
    )
    logging.info("APScheduler: pending payments reconciliation every 10 minutes")
    logging.info(
        "APScheduler: payment reminders every 2 minutes "
        "(10m / 1h / 3h / 12h / 24h / 48h stages)"
    )
    logging.info(
        f"APScheduler: tarologist reminder Wed/Sun "
        f"{TAROLOGIST_REMINDER_HOUR:02d}:{TAROLOGIST_REMINDER_MINUTE:02d} MSK"
    )

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
