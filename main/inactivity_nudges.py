"""
Event-driven nudge-рассылки: платники (B) и бесплатные пользователи (C1–C4).

Платники: 1/3/5/10 дней молчания — слот 10:00–20:00 MSK.
Бесплатные: часы/дни от якорного события — без слота, проверка каждые 2 мин.

Защита от catch-up: за один тик каждому пользователю уходит максимум ОДИН этап
на категорию (B / C1 / C2 / C3 / C4). Следующий этап — в следующем тике.
"""
import asyncio
import logging

from main.broadcast_schedule import is_in_broadcast_window, is_user_due_in_tick
from main.database import (
    FREE_NUDGE_STAGES,
    PAID_INACTIVITY_STAGES,
    get_users_due_for_free_nudge,
    get_users_due_for_paid_inactivity_nudge,
    mark_free_nudge_sent,
    mark_paid_inactivity_nudge_sent,
)
from send_message import send_free_user_nudge, send_paid_inactivity_nudge

NUDGE_DELAY_SEC = 0.05


async def process_inactivity_nudges() -> dict:
    """Обработать все event-driven nudge-триггеры."""
    results = {
        'sent': 0,
        'skipped_time': 0,
        'skipped_catchup': 0,
        'failed': 0,
        'blocked': 0,
        'by_type': {},
    }

    paid_due_in_window = is_in_broadcast_window()

    sent_paid_this_run: set[int] = set()

    for stage in PAID_INACTIVITY_STAGES:
        key = f'paid_{stage}'
        results['by_type'][key] = {'sent': 0, 'failed': 0, 'blocked': 0, 'skipped_time': 0}
        if not paid_due_in_window:
            continue

        due = await get_users_due_for_paid_inactivity_nudge(stage)
        if not due:
            continue

        logging.info(f"Paid inactivity nudges ({stage}): {len(due)} user(s) due")
        for target in due:
            user_id = target['user_id']

            if user_id in sent_paid_this_run:
                results['skipped_catchup'] += 1
                continue

            last_active_at = target.get('last_active_at')

            if not is_user_due_in_tick(user_id, anchor_at=last_active_at):
                results['skipped_time'] += 1
                results['by_type'][key]['skipped_time'] += 1
                continue

            try:
                success = await send_paid_inactivity_nudge(user_id, stage=stage)
                if success:
                    await mark_paid_inactivity_nudge_sent(user_id, stage)
                    results['sent'] += 1
                    results['by_type'][key]['sent'] += 1
                    sent_paid_this_run.add(user_id)
                else:
                    results['blocked'] += 1
                    results['by_type'][key]['blocked'] += 1
            except Exception as e:
                logging.error(f"Paid inactivity nudge error ({stage}) user={user_id}: {e}", exc_info=True)
                results['failed'] += 1
                results['by_type'][key]['failed'] += 1

            await asyncio.sleep(NUDGE_DELAY_SEC)

    for category, stages in FREE_NUDGE_STAGES.items():
        sent_this_category: set[int] = set()

        for stage in stages:
            key = f'{category}_{stage}'
            results['by_type'][key] = {'sent': 0, 'failed': 0, 'blocked': 0}

            due = await get_users_due_for_free_nudge(category, stage)
            if not due:
                continue

            logging.info(f"Free nudges ({category}/{stage}): {len(due)} user(s) due")
            for target in due:
                user_id = target['user_id']

                if user_id in sent_this_category:
                    results['skipped_catchup'] += 1
                    continue

                try:
                    success = await send_free_user_nudge(
                        user_id,
                        category=category,
                        stage=stage,
                    )
                    if success:
                        await mark_free_nudge_sent(user_id, category, stage)
                        results['sent'] += 1
                        results['by_type'][key]['sent'] += 1
                        sent_this_category.add(user_id)
                    else:
                        results['blocked'] += 1
                        results['by_type'][key]['blocked'] += 1
                except Exception as e:
                    logging.error(
                        f"Free nudge error ({category}/{stage}) user={user_id}: {e}",
                        exc_info=True,
                    )
                    results['failed'] += 1
                    results['by_type'][key]['failed'] += 1

                await asyncio.sleep(NUDGE_DELAY_SEC)

    if any(v for k, v in results.items() if k != 'by_type' and v) or any(
        t['sent'] or t['failed'] for t in results['by_type'].values()
    ):
        logging.info(f"Inactivity nudges job finished: {results}")
    return results
