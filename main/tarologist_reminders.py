"""
Рассылка напоминания о тарологе Диане: среда и воскресенье после обеда.
"""
import asyncio
import logging

from main.database import get_all_users
from send_message import send_tarologist_reminder
from main.outbound_messages import profile_circuit_is_open

REMINDER_DELAY_SEC = 0.05


async def process_tarologist_reminders() -> dict:
    """Отправить tarologist_reminder всем незаблокированным пользователям."""
    results = {'sent': 0, 'failed': 0, 'total': 0}
    if profile_circuit_is_open():
        return results

    users = await get_all_users(include_blocked=False, include_unsubscribed_daily_card=True)
    results['total'] = len(users)
    logging.info(f"Tarologist reminder broadcast: {results['total']} user(s)")

    for user in users:
        user_id = user['user_id']
        try:
            ok = await send_tarologist_reminder(
                user_id,
                sent_via='scheduler',
            )
            if ok:
                results['sent'] += 1
            else:
                results['failed'] += 1
        except Exception as e:
            logging.error(f"Tarologist reminder error user={user_id}: {e}", exc_info=True)
            results['failed'] += 1

        await asyncio.sleep(REMINDER_DELAY_SEC)
        if profile_circuit_is_open():
            logging.warning("Tarologist reminders stopped: MAX profile circuit opened")
            return results

    logging.info(f"Tarologist reminder broadcast finished: {results}")
    return results
