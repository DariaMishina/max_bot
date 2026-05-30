"""
Автоматические напоминания о незавершённой оплате (pending / canceled).

Этапы: 10 минут, 1 час, 3 часа после создания платежа.
"""
import asyncio
import logging

from main.database import (
    PAYMENT_REMINDER_STAGES,
    get_payment_by_id,
    get_payments_due_for_reminder,
    mark_payment_reminder_sent,
)
from send_message import send_payment_reminder

REMINDER_DELAY_SEC = 0.05


async def process_payment_reminders() -> dict:
    """Проверить все этапы и отправить напоминания."""
    results = {'sent': 0, 'skipped': 0, 'failed': 0}

    for stage in PAYMENT_REMINDER_STAGES:
        due = await get_payments_due_for_reminder(stage)
        if not due:
            continue

        logging.info(f"Payment reminders ({stage}): {len(due)} payment(s) due")

        for payment in due:
            payment_id = payment['payment_id']
            user_id = payment['user_id']

            current = await get_payment_by_id(payment_id)
            if not current or current['status'] not in ('pending', 'canceled'):
                results['skipped'] += 1
                continue

            try:
                success = await send_payment_reminder(user_id, stage=stage)
                if success:
                    await mark_payment_reminder_sent(payment_id, stage)
                    results['sent'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                logging.error(
                    f"Payment reminder error ({stage}) payment={payment_id} user={user_id}: {e}",
                    exc_info=True,
                )
                results['failed'] += 1

            await asyncio.sleep(REMINDER_DELAY_SEC)

    if any(results.values()):
        logging.info(f"Payment reminders job finished: {results}")
    return results
