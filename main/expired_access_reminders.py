"""
Автоматические напоминания об истёкшем платном доступе: day0–day7.

Отправка в персональный слот 10:00–20:00 MSK (тик каждые 30 мин).
Слот привязан к моменту истечения. day0 отправляется без слота (grace period).
"""
import asyncio
import logging

from main.broadcast_delivery import finalize_broadcast_send
from main.broadcast_schedule import is_in_broadcast_window, is_user_due_in_tick
from main.database import (
    EXPIRED_ACCESS_REMINDER_STAGES,
    get_users_due_for_expired_access_reminder,
    mark_expired_access_reminder_sent,
)
from send_message import send_expired_access_reminder

REMINDER_DELAY_SEC = 0.1


async def process_expired_access_reminders() -> dict:
    """Проверить все этапы и отправить expiry-напоминания."""
    results = {
        'sent': 0,
        'skipped_time': 0,
        'skipped_catchup': 0,
        'failed': 0,
        'blocked': 0,
        'by_stage': {},
    }

    if not is_in_broadcast_window():
        return results

    processed_this_run: set[int] = set()

    for stage in EXPIRED_ACCESS_REMINDER_STAGES:
        due = await get_users_due_for_expired_access_reminder(stage)
        if not due:
            continue

        results['by_stage'][stage] = {'sent': 0, 'failed': 0, 'blocked': 0, 'skipped_time': 0}
        logging.info(f"Expired access reminders ({stage}): {len(due)} user(s) due")

        for target in due:
            user_id = target['user_id']
            expiry_at = target.get('expiry_at')

            if user_id in processed_this_run:
                results['skipped_catchup'] += 1
                continue

            if stage != 'day0' and not is_user_due_in_tick(user_id, anchor_at=expiry_at):
                results['skipped_time'] += 1
                results['by_stage'][stage]['skipped_time'] += 1
                continue

            try:
                success, unreachable = await send_expired_access_reminder(user_id, stage=stage)
                outcome = await finalize_broadcast_send(
                    success,
                    unreachable,
                    lambda uid=user_id, st=stage: mark_expired_access_reminder_sent(uid, st),
                )
                if outcome == 'sent':
                    results['sent'] += 1
                    results['by_stage'][stage]['sent'] += 1
                    processed_this_run.add(user_id)
                elif outcome == 'blocked':
                    results['blocked'] += 1
                    results['by_stage'][stage]['blocked'] += 1
                    processed_this_run.add(user_id)
                else:
                    results['failed'] += 1
                    results['by_stage'][stage]['failed'] += 1
            except Exception as e:
                logging.error(
                    f"Expired access reminder error ({stage}) user={user_id}: {e}",
                    exc_info=True,
                )
                results['failed'] += 1
                results['by_stage'][stage]['failed'] += 1

            await asyncio.sleep(REMINDER_DELAY_SEC)

    if any(v for k, v in results.items() if k != 'by_stage' and v) or results['by_stage']:
        logging.info(f"Expired access reminders job finished: {results}")
    return results
