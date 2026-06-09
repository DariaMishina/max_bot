"""
Скрипт для ручной отправки сообщений пользователям в Max-боте.
Адаптировано с aiogram (tg_bot) на aiomax.

Ключевые отличия от TG-версии:
- bot.send_message(text, user_id=user_id, keyboard=kb, format='html')
- buttons.KeyboardBuilder + buttons.CallbackButton / buttons.LinkButton
- Нет ForceReply (Max не поддерживает)
- Нет TelegramForbiddenError — ловим общие Exception и проверяем текст ошибки
"""
import asyncio
import logging
import sys
from typing import Optional

import aiohttp
from aiomax import buttons
from main.botdef import bot
from main.database import (
    Database,
    update_user_blocked_status,
    get_all_users,
    get_paid_users,
    is_send_blocked_error,
    get_users_for_div_reminder_broadcast,
    get_users_for_activation_broadcast,
    mark_activation_sent,
    mark_div_reminder_broadcast_sent,
    DIV_REMINDER_SKIP_SEGMENTS,
    DIV_REMINDER_SEGMENT_ACTIVE,
    DIV_REMINDER_SEGMENT_EXPIRED,
    DIV_REMINDER_SEGMENT_PAYWALL,
    DIV_REMINDER_SEGMENT_FREE_RETURN,
)
from main.broadcast_schedule import is_user_due_in_tick, is_same_msk_day

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def send_message_to_user(
    user_id: int,
    text: str,
    format: str = "html",
    keyboard=None
):
    """
    Отправить сообщение одному пользователю в Max.

    Args:
        user_id: Max User ID
        text: Текст сообщения
        format: Формат текста ('html', 'markdown' или None)
        keyboard: KeyboardBuilder (опционально)
    """
    try:
        await bot.send_message(
            text,
            user_id=user_id,
            keyboard=keyboard,
            format=format
        )
        print(f"✅ Сообщение отправлено пользователю {user_id}")
        try:
            await update_user_blocked_status(user_id, False)
        except Exception as db_error:
            logging.warning(f"Failed to update blocked status for user {user_id}: {db_error}")
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "chat not found" in error_msg or "user not found" in error_msg:
            print(f"❌ Пользователь {user_id} не найден или не начинал диалог с ботом")
        elif is_send_blocked_error(e):
            print(f"❌ Пользователь {user_id} заблокировал бота или диалог приостановлен")
            try:
                await update_user_blocked_status(user_id, True)
                print(f"   Статус блокировки обновлен в БД: is_blocked=True")
            except Exception as db_error:
                logging.error(f"Failed to update blocked status for user {user_id}: {db_error}")
        else:
            print(f"❌ Ошибка отправки сообщению пользователю {user_id}: {e}")
        logging.error(f"Error sending message to user {user_id}: {e}", exc_info=True)
        return False


async def send_message_to_multiple_users(
    user_ids: list,
    text: str,
    format: str = "html",
    keyboard=None
):
    """
    Отправить сообщение нескольким пользователям с задержкой между отправками.
    """
    results = {'success': 0, 'failed': 0, 'total': len(user_ids)}
    DELAY = 0.05

    for user_id in user_ids:
        success = await send_message_to_user(user_id, text, format, keyboard)
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
        await asyncio.sleep(DELAY)

    print(f"\n{'='*60}")
    print(f"Итого отправлено: {results['success']}/{results['total']}")
    print(f"Ошибок: {results['failed']}")
    print(f"{'='*60}\n")
    return results


async def send_payment_reminder(user_id: int, stage: str = '10m'):
    """Напоминание об оплате с кнопкой «Оплатить».

    stage: '10m' | '1h' | '3h' — этап автоматической рассылки.
    """
    texts = {
        '10m': (
            "<b>Доступ к раскладам почти открыт — осталось только завершить оплату</b> 👇"
        ),
        '1h': (
            "Кажется, оплата не дошла до конца — бывает 🔮\n\n"
            "Если расклад всё ещё актуален, можешь завершить оплату, "
            "когда будет удобно."
        ),
        '3h': (
            "На всякий случай напоминаем: доступ к раскладам всё ещё можно открыть ✨\n\n"
            "Если сейчас не время — ничего страшного. "
            "Когда захочешь вернуться, нажми «Оплатить» ниже."
        ),
    }
    text = texts.get(stage, texts['10m'])
    kb = buttons.KeyboardBuilder()
    kb.row(buttons.CallbackButton("💳 Оплатить", "remind_pay"))

    print(f"📤 Отправляю напоминание об оплате ({stage}) пользователю {user_id}...")
    return await send_message_to_user(user_id, text, keyboard=kb)


async def send_no_divinations_reminder(
    user_id: int,
    *,
    sent_via: str = 'send_message_script',
    segment: Optional[str] = None,
):
    """Напоминание тем, у кого закончились все гадания + меню оплаты"""
    from keyboards.pay import make_payment_kb
    from main.conversions import save_paywall_conversion

    reminder_text = (
        "✨ Привет! Может, пора сделать новый расклад?\n\n"
        "Карты помогли тебе увидеть то, что было скрыто. "
        "И если сейчас снова нужна ясность — я здесь.\n\n"
        "Выбери свой путь и продолжай находить ответы внутри себя 💫"
    )
    payment_text = _broadcast_payment_text()

    print(f"📤 Отправляю напоминание о закончившихся гаданиях пользователю {user_id}...")
    try:
        metadata = {'reminder_type': 'no_divinations', 'sent_via': sent_via}
        if segment:
            metadata['segment'] = segment
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="no_divinations_reminder",
                metadata=metadata,
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(reminder_text, user_id=user_id, format=None)
        await bot.send_message(payment_text, user_id=user_id, keyboard=make_payment_kb(), format='html')
        print(f"✅ Напоминание и меню оплаты отправлены пользователю {user_id}")
        return True
    except Exception as e:
        _handle_send_error(user_id, e, "напоминания о закончившихся гаданиях")
        return False


def _broadcast_payment_text() -> str:
    return (
        "🔮 <b>Личная консультация с тарологом Дианой</b> — от 500₽\n"
        "Живой расклад и ответ в течение часа (10:00–22:00 МСК).\n\n"
        "<b>🔥 Самый популярный вариант</b>\n"
        "👑 Безлимит на месяц — 599₽\n"
        "Гадай когда угодно и сколько угодно. Полная анонимность.\n\n"
        "Или выбери пакет:\n"
        "🔥 30 раскладов — 399₽\n"
        "🌟 20 раскладов — 289₽\n"
        "💫 10 раскладов — 179₽\n"
        "🌙 3 расклада — 99₽\n\n"
        "👉 Выбрать пакет"
    )


async def send_activation_nudge(user_id: int):
    """Welcome-активация: пользователь заходил, но ещё не сделал расклад."""
    text = (
        "Привет 🔮\n\n"
        "Ты заходил(а), но мы ещё не успели погадать вместе.\n\n"
        "Задай свой первый вопрос — карты уже ждут. "
        "Можно начать с чего-то простого: «Что мне важно знать сегодня?»\n\n"
        "Нажми /start или выбери расклад в меню ✨"
    )
    print(f"📤 Отправляю welcome-активацию пользователю {user_id}...")
    return await send_message_to_user(user_id, text, format=None)


async def send_gentle_nudge(user_id: int):
    """Мягкое напоминание для пользователей с активным платным доступом."""
    text = (
        "Привет 🔮\n\n"
        "Просто напомню — карты здесь, если захочется новый расклад.\n\n"
        "Не обязательно ждать сложного момента. "
        "Можно спросить о делах, отношениях или просто «что важно знать сейчас».\n\n"
        "Я рядом ✨"
    )
    print(f"📤 Отправляю мягкое напоминание пользователю {user_id}...")
    return await send_message_to_user(user_id, text, format=None)


async def send_free_return_nudge(user_id: int):
    """Мягкое напоминание для пользователей с оставшимися бесплатными раскладами."""
    text = (
        "Привет 🔮\n\n"
        "У тебя ещё есть бесплатные расклады — можешь воспользоваться, когда будет удобно.\n\n"
        "Карты помогают увидеть ситуацию с другой стороны. "
        "Загляни, если захочется ясности ✨"
    )
    print(f"📤 Отправляю мягкое напоминание (free return) пользователю {user_id}...")
    return await send_message_to_user(user_id, text, format=None)


async def send_expired_sub_reminder(
    user_id: int,
    *,
    sent_via: str = 'send_message_script',
    segment: Optional[str] = None,
):
    """Напоминание пользователям, у которых закончился платный доступ."""
    from keyboards.pay import make_payment_kb
    from main.conversions import save_paywall_conversion

    reminder_text = (
        "Привет! 💫\n\n"
        "Твои расклады закончились, но вопросы к картам — нет.\n\n"
        "Если снова нужна ясность — я здесь. "
        "Можно вернуться к любой теме, которая сейчас важна ✨"
    )
    payment_text = _broadcast_payment_text()

    print(f"📤 Отправляю напоминание об истёкшем доступе пользователю {user_id}...")
    try:
        metadata = {'reminder_type': 'expired_sub_reminder', 'sent_via': sent_via}
        if segment:
            metadata['segment'] = segment
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="expired_sub_reminder",
                metadata=metadata,
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(reminder_text, user_id=user_id, format=None)
        await bot.send_message(payment_text, user_id=user_id, keyboard=make_payment_kb(), format='html')
        print(f"✅ Напоминание об истёкшем доступе отправлено пользователю {user_id}")
        return True
    except Exception as e:
        _handle_send_error(user_id, e, "напоминания об истёкшем доступе")
        return False


DIV_REMINDER_SENDERS = {
    DIV_REMINDER_SEGMENT_ACTIVE: send_gentle_nudge,
    DIV_REMINDER_SEGMENT_EXPIRED: send_expired_sub_reminder,
    DIV_REMINDER_SEGMENT_PAYWALL: send_no_divinations_reminder,
    DIV_REMINDER_SEGMENT_FREE_RETURN: send_free_return_nudge,
}

BROADCAST_SEND_DELAY_SEC = 0.1


def _init_broadcast_results() -> dict:
    return {
        'sent': 0,
        'failed': 0,
        'blocked': 0,
        'skipped': 0,
        'skipped_time': 0,
        'skipped_already_sent': 0,
        'by_segment': {},
    }


async def _send_div_reminder_for_segment(user_id: int, segment: str) -> bool:
    """Отправка по сегменту с metadata для paywall-сценариев."""
    if segment in (DIV_REMINDER_SEGMENT_EXPIRED, DIV_REMINDER_SEGMENT_PAYWALL):
        sender = DIV_REMINDER_SENDERS[segment]
        return await sender(user_id, sent_via='broadcast', segment=segment)
    sender = DIV_REMINDER_SENDERS.get(segment)
    if not sender:
        return False
    return await sender(user_id)


async def send_activation_broadcast() -> dict:
    """
    Welcome-активация: ≥24ч после регистрации, без гаданий.
    Отправка в персональный слот 10:00–20:00 MSK (тик каждые 30 мин).
    """
    results = _init_broadcast_results()
    targets = await get_users_for_activation_broadcast()
    logging.info(f"Activation broadcast tick: {len(targets)} eligible users")

    for target in targets:
        uid = target['user_id']
        last_active_at = target.get('last_active_at')

        if not is_user_due_in_tick(uid, last_active_at):
            results['skipped_time'] += 1
            continue

        try:
            success = await send_activation_nudge(uid)
            if success:
                await mark_activation_sent(uid)
                results['sent'] += 1
            else:
                results['blocked'] += 1
            await asyncio.sleep(BROADCAST_SEND_DELAY_SEC)
        except Exception as e:
            logging.error(f"Error in activation broadcast for user {uid}: {e}", exc_info=True)
            results['failed'] += 1

    if any(v for k, v in results.items() if k != 'by_segment' and v):
        logging.info(f"Activation broadcast tick results: {results}")
    return results


async def send_divination_reminder_broadcast() -> dict:
    """
    Сегментированная рассылка Пн/Чт.
    Отправка в персональный слот 10:00–20:00 MSK (тик каждые 30 мин).
    """
    results = _init_broadcast_results()
    targets = await get_users_for_div_reminder_broadcast()
    logging.info(f"Divination-reminder broadcast tick: {len(targets)} users loaded")

    for target in targets:
        uid = target['user_id']
        segment = target['segment']
        last_active_at = target.get('last_active_at')

        if segment not in results['by_segment']:
            results['by_segment'][segment] = {'sent': 0, 'failed': 0, 'blocked': 0}

        if segment in DIV_REMINDER_SKIP_SEGMENTS:
            results['skipped'] += 1
            continue

        if is_same_msk_day(target.get('last_div_reminder_broadcast_at')):
            results['skipped_already_sent'] += 1
            continue

        if not is_user_due_in_tick(uid, last_active_at):
            results['skipped_time'] += 1
            continue

        if segment not in DIV_REMINDER_SENDERS:
            logging.warning(f"Unknown broadcast segment '{segment}' for user {uid}, skipping")
            results['skipped'] += 1
            continue

        try:
            success = await _send_div_reminder_for_segment(uid, segment)
            if success:
                await mark_div_reminder_broadcast_sent(uid)
                results['sent'] += 1
                results['by_segment'][segment]['sent'] += 1
            else:
                results['blocked'] += 1
                results['by_segment'][segment]['blocked'] += 1
            await asyncio.sleep(BROADCAST_SEND_DELAY_SEC)
        except Exception as e:
            logging.error(
                f"Error in divination-reminder broadcast for user {uid} "
                f"(segment={segment}): {e}",
                exc_info=True,
            )
            results['failed'] += 1
            results['by_segment'][segment]['failed'] += 1

    if any(v for k, v in results.items() if k != 'by_segment' and v) or results['by_segment']:
        logging.info(f"Divination-reminder broadcast tick results: {results}")
    return results


async def send_no_divinations_broadcast() -> dict:
    """Устаревший alias — используйте send_divination_reminder_broadcast()."""
    logging.warning(
        "send_no_divinations_broadcast() is deprecated; "
        "use send_divination_reminder_broadcast() for scheduled ticks"
    )
    return await send_divination_reminder_broadcast()


async def send_discussion_announcement(user_id: int):
    """Объявление о функции обсуждения расклада + меню оплаты"""
    from keyboards.pay import make_payment_kb
    from main.conversions import save_paywall_conversion

    announcement_text = (
        "✨ <b>Новое в боте!</b>\n\n"
        "Теперь ты можешь <b>обсудить свой расклад</b> со мной 🔮\n\n"
        "Есть вопросы по картам? Хочешь глубже понять значение? "
        "Или нужно уточнить детали?\n\n"
        "Просто ответь на сообщение с раскладом — я помогу разобраться 💫"
    )
    payment_text = (
        "🔮 <b>Личная консультация с тарологом Дианой</b> — от 500₽\n"
        "Живой расклад и ответ в течение часа (10:00–22:00 МСК).\n\n"
        "А если закончились гадания — выбирай себе пакет раскладов:\n\n"
        "<b>🔥 Самый популярный вариант</b>\n"
        "👑 Безлимит на месяц — 599₽\n"
        "Гадай когда угодно и сколько угодно. Полная анонимность.\n\n"
        "Или выбери пакет:\n"
        "🔥 30 раскладов — 399₽\n"
        "🌟 20 раскладов — 289₽\n"
        "💫 10 раскладов — 179₽\n"
        "🌙 3 расклада — 99₽\n\n"
        "👉 Выбрать пакет"
    )

    print(f"📤 Отправляю объявление об обсуждении расклада пользователю {user_id}...")
    try:
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="discussion_announcement",
                metadata={'reminder_type': 'discussion_announcement', 'sent_via': 'send_message_script'}
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(announcement_text, user_id=user_id, format='html')
        await bot.send_message(payment_text, user_id=user_id, keyboard=make_payment_kb(), format='html')
        print(f"✅ Объявление и меню оплаты отправлены пользователю {user_id}")
        return True
    except Exception as e:
        _handle_send_error(user_id, e, "объявления об обсуждении расклада")
        return False


async def send_bot_restored(user_id: int):
    """Сообщение о восстановлении работы бота"""
    text = (
        "Привет! Это <b>Сфера Таро</b> 🔮\n\n"
        "Рады сообщить: бот снова работает в полном режиме!\n\n"
        "Возвращайся — карты ждут твоих вопросов 💫\n\n"
        "Нажми /start чтобы начать"
    )
    print(f"📤 Отправляю сообщение о восстановлении бота пользователю {user_id}...")
    return await send_message_to_user(user_id, text)


async def send_friday13_promo(user_id: int):
    """Промо-рассылка: Пятница 13 — удвоение пакетов гаданий"""
    from keyboards.pay import make_payment_kb
    from main.conversions import save_paywall_conversion

    promo_text = (
        "🌑 <b>Пятница, 13-е… Карты говорят громче обычного.</b>\n\n"
        "Мы видим: в этот день ты особенно чувствуешь связь с Таро. "
        "И это не случайность — тринадцатый аркан не зря считается картой трансформации.\n\n"
        "Сегодня мы хотим поддержать твой путь ✨\n\n"
        "🔮 <b>Только до конца дня: купи любой пакет раскладов — и мы удвоим его.</b>\n\n"
        "А если ты уже купил(а) пакет сегодня — <b>проверь свой баланс</b>. "
        "Мы уже всё удвоили 🪄"
    )
    payment_text = (
        "🔮 <b>Личная консультация с тарологом Дианой</b> — от 500₽\n"
        "Живой расклад и ответ в течение часа (10:00–22:00 МСК).\n\n"
        "Выбирай свой пакет — удвоение произойдёт автоматически:\n\n"
        "<b>🔥 Самый популярный вариант</b>\n"
        "👑 Безлимит на месяц — 599₽\n"
        "Гадай когда угодно и сколько угодно. Полная анонимность.\n\n"
        "Или выбери пакет:\n"
        "🔥 30 → <b>60 раскладов</b> — 399₽\n"
        "🌟 20 → <b>40 раскладов</b> — 289₽\n"
        "💫 10 → <b>20 раскладов</b> — 179₽\n"
        "🌙 3 → <b>6 раскладов</b> — 99₽\n\n"
        "⏳ Предложение действует до полуночи"
    )

    print(f"📤 Отправляю промо «Пятница 13» пользователю {user_id}...")
    try:
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="friday13_promo",
                metadata={'reminder_type': 'friday13_promo', 'sent_via': 'send_message_script'}
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(promo_text, user_id=user_id, format='html')
        await bot.send_message(payment_text, user_id=user_id, keyboard=make_payment_kb(), format='html')
        print(f"✅ Промо «Пятница 13» отправлено пользователю {user_id}")
        return True
    except Exception as e:
        _handle_send_error(user_id, e, "промо «Пятница 13»")
        return False


async def send_tarologist_intro(user_id: int):
    """Представление таролога Дианы и новых услуг «Личная консультация» (+ меню оплаты)"""
    from keyboards.pay import make_payment_kb
    from main.conversions import save_paywall_conversion

    intro_text = (
        "Рады сообщить: у Вас появилась возможность получить "
        "<b>личный расклад от таролога Дианы</b>!\n\n"
        "🔮 Диана — практик с опытом <b>7+ лет</b>. "
        "Помогает через личный контакт и глубину карт.\n\n"
        "Теперь два формата — под вашу задачу и ритм жизни.\n\n"
        "<b>1️⃣ Личная консультация с Дианой (живой таролог)</b>\n"
        "Живой взгляд, энергия, детальная проработка. "
        "Ответ в течение часа (10:00–22:00 МСК).\n\n"
        "✨ <b>Базовый разбор — 500 ₽</b>\n"
        "Расклад на один вопрос. Трактуем вместе: картина "
        "ситуации + совет. Коротко и по делу.\n\n"
        "🔮 <b>Подробный разбор — 1500 ₽</b> (оптимально). "
        "Расклад на ситуацию, до 5 доп. вопросов:\n"
        "— что сейчас\n"
        "— скрытые моменты\n"
        "— к чему идёт\n"
        "— совет карт\n\n"
        "<b>2️⃣ Автоматические гадания от бота</b>\n"
        "Точность та же, всегда под рукой. Мгновенно, "
        "анонимно, без ожидания, 24/7."
    )
    payment_text = (
        "👑 <b>Безлимит на месяц — 599 ₽</b> (самый популярный)\n"
        "Гадай сколько угодно.\n\n"
        "📦 Или пакет:\n"
        "🔥 30 раскладов — 399 ₽\n"
        "🌟 20 — 289 ₽\n"
        "💫 10 — 179 ₽\n"
        "🌙 3 — 99 ₽"
    )

    print(f"📤 Отправляю представление таролога Дианы пользователю {user_id}...")
    try:
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="tarologist_intro",
                metadata={'reminder_type': 'tarologist_intro', 'sent_via': 'send_message_script'}
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(intro_text, user_id=user_id, format='html')
        await bot.send_message(payment_text, user_id=user_id, keyboard=make_payment_kb(), format='html')
        print(f"✅ Представление таролога отправлено пользователю {user_id}")
        return True
    except Exception as e:
        _handle_send_error(user_id, e, "представления таролога Дианы")
        return False


CONSULT_PACKAGE_NAMES = {
    'basic': 'Базовый разбор',
    'detailed': 'Подробный разбор',
}


def _make_consult_diana_contact_kb():
    """Кнопка-ссылка на личные сообщения Дианы (без меню оплаты)."""
    from main.config_reader import config

    kb = buttons.KeyboardBuilder()
    if config.tarologist_profile_url:
        kb.row(buttons.LinkButton("💬 Написать Диане", config.tarologist_profile_url))
    return kb


def _build_consult_diana_contact_text(package_name: str) -> str:
    from main.config_reader import config

    work_hours = config.tarologist_work_hours or "10:00–22:00"
    return (
        "Привет!\n\n"
        f"Видим, что ты оплатила «{package_name}» — спасибо! 🙏\n\n"
        "Чтобы получить консультацию, нажми кнопку ниже — "
        "она откроет личные сообщения с Дианой.\n\n"
        "Напиши ей свой вопрос и укажи, что это оплаченный "
        f"«{package_name}». Диана ответит в течение часа "
        f"(в рабочие часы {work_hours} МСК) ✨"
    )


async def send_consult_diana_contact(user_id: int, package: str = 'detailed'):
    """
    Помощь после оплаты консультации: инструкция + кнопка «Написать Диане».
    package: basic | detailed
    """
    package_key = package if package in CONSULT_PACKAGE_NAMES else 'detailed'
    package_name = CONSULT_PACKAGE_NAMES[package_key]
    text = _build_consult_diana_contact_text(package_name)
    kb = _make_consult_diana_contact_kb()

    print(
        f"📤 Отправляю контакт Дианы ({package_name}) пользователю {user_id}..."
    )
    try:
        await bot.send_message(text, user_id=user_id, keyboard=kb, format=None)
        print(f"✅ Контакт Дианы отправлен пользователю {user_id}")
        return True
    except Exception as e:
        _handle_send_error(user_id, e, f"контакта Дианы ({package_name})")
        return False


async def send_tarologist_reminder(user_id: int):
    """Повторное напоминание о тарологе Диане — для тех, кто уже видел представление."""
    from keyboards.pay import make_consultation_kb
    from main.conversions import save_paywall_conversion

    reminder_text = (
        "Что происходит в отношениях на самом деле? 💗\n"
        "Стоит ли менять работу или подождать? 🤔\n"
        "Какой шаг сейчас приблизит тебя к цели? 💫\n\n"
        "Если хочется скорее получить ответ — "
        "<b>таролог Диана</b> разберёт твою ситуацию через карты. "
        "Лично, развёрнуто, без общих фраз ✨\n\n"
        "<b>Два формата:</b>\n\n"
        "✨ <b>Базовый разбор — 500 ₽</b>\n"
        "Один вопрос — картина ситуации и совет. Коротко и по делу.\n\n"
        "🔮 <b>Подробный разбор — 1500 ₽</b> (оптимально)\n"
        "Расклад на ситуацию, до 5 доп. вопросов:\n"
        "— что сейчас\n"
        "— скрытые моменты\n"
        "— к чему идёт\n"
        "— совет карт\n\n"
        "Ответ в течение часа (10:00–22:00 МСК) 🔮"
    )

    print(f"📤 Отправляю напоминание о тарологе Диане пользователю {user_id}...")
    try:
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="tarologist_reminder",
                metadata={'reminder_type': 'tarologist_reminder', 'sent_via': 'send_message_script'}
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(reminder_text, user_id=user_id, keyboard=make_consultation_kb(), format='html')
        print(f"✅ Напоминание о тарологе отправлено пользователю {user_id}")
        return True
    except Exception as e:
        _handle_send_error(user_id, e, "напоминания о тарологе Диане")
        return False


async def send_full_moon_promo(user_id: int):
    """Промо-рассылка: полнолуние — удвоение пакетов раскладов"""
    from keyboards.pay import make_payment_kb
    from main.conversions import save_paywall_conversion

    promo_text = (
        "🌕 <b>Полнолуние — время ясности и силы.</b>\n\n"
        "В такие ночи граница между вопросом и ответом тоньше обычного. "
        "Мы хотим, чтобы у тебя было больше пространства для раскладов ✨\n\n"
        "🔮 <b>Сегодня: купи любой пакет раскладов — и мы удвоим его в честь полнолуния.</b>\n\n"
        "А если ты уже оплатил(а) сегодня — <b>проверь баланс</b>: "
        "мы уже удвоили твои расклады 🪄"
    )
    payment_text = (
        "🔮 <b>Личная консультация с тарологом Дианой</b> — от 500₽\n"
        "Живой расклад и ответ в течение часа (10:00–22:00 МСК).\n\n"
        "Выбирай пакет — удвоение произойдёт автоматически:\n\n"
        "<b>🔥 Самый популярный вариант</b>\n"
        "👑 Безлимит на месяц — 599₽\n"
        "Гадай когда угодно и сколько угодно. Полная анонимность.\n\n"
        "Или выбери пакет:\n"
        "🔥 30 → <b>60 раскладов</b> — 399₽\n"
        "🌟 20 → <b>40 раскладов</b> — 289₽\n"
        "💫 10 → <b>20 раскладов</b> — 179₽\n"
        "🌙 3 → <b>6 раскладов</b> — 99₽\n\n"
        "⏳ Предложение действует до полуночи"
    )

    print(f"📤 Отправляю промо «Полнолуние» пользователю {user_id}...")
    try:
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="full_moon_promo",
                metadata={'reminder_type': 'full_moon_promo', 'sent_via': 'send_message_script'}
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(promo_text, user_id=user_id, format='html')
        await bot.send_message(payment_text, user_id=user_id, keyboard=make_payment_kb(), format='html')
        print(f"✅ Промо «Полнолуние» отправлено пользователю {user_id}")
        return True
    except Exception as e:
        _handle_send_error(user_id, e, "промо «Полнолуние»")
        return False


async def send_feedback_request(user_id: int):
    """Запрос обратной связи у купившего пользователя с кнопкой «Оставить отзыв»."""
    text = (
        "Привет! Ты уже пользуешься раскладами — и нам важно знать, "
        "как тебе опыт.\n\n"
        "Расскажи, пожалуйста:\n"
        "— Что нравится?\n"
        "— Что хочется улучшить?\n"
        "— Может, чего-то не хватает?\n\n"
        "🎁 За подробный отзыв — 3 бесплатных расклада в подарок!\n\n"
        "Нажми кнопку ниже — и просто напиши свои мысли 💬"
    )
    kb = buttons.KeyboardBuilder()
    kb.row(buttons.CallbackButton("📝 Оставить отзыв", "leave_feedback_paid"))

    print(f"📤 Отправляю запрос обратной связи пользователю {user_id}...")
    return await send_message_to_user(user_id, text, format=None, keyboard=kb)


def _handle_send_error(user_id: int, error: Exception, action_desc: str):
    """Общая обработка ошибок отправки — логирование и обновление статуса блокировки."""
    error_msg = str(error).lower()
    if "chat not found" in error_msg or "user not found" in error_msg:
        print(f"❌ Пользователь {user_id} не найден или не начинал диалог с ботом")
    elif is_send_blocked_error(error):
        print(f"❌ Пользователь {user_id} заблокировал бота или диалог приостановлен")
        try:
            asyncio.get_event_loop().run_until_complete(update_user_blocked_status(user_id, True))
        except Exception:
            pass
    else:
        print(f"❌ Ошибка отправки {action_desc} пользователю {user_id}: {error}")
    logging.error(f"Error sending {action_desc} to user {user_id}: {error}", exc_info=True)


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Отправить сообщение пользователю(ам) в Max-боте'
    )
    parser.add_argument(
        'user_id', type=int, nargs='*', default=[],
        help='Max User ID (несколько через пробел). Для --broadcast берутся из БД'
    )
    parser.add_argument(
        '--text', type=str,
        help='Текст сообщения (обязателен, если не указан специальный флаг)'
    )
    parser.add_argument(
        '--format', type=str, default='html', choices=['html', 'markdown', 'none'],
        help='Формат текста (по умолчанию: html)'
    )
    parser.add_argument(
        '--payment-reminder', action='store_true',
        help='Отправить напоминание об оплате с кнопкой «Оплатить»'
    )
    parser.add_argument(
        '--no-divinations', action='store_true',
        help='Напоминание тем, у кого закончились гадания (+ меню оплаты)'
    )
    parser.add_argument(
        '--gentle-nudge', action='store_true',
        help='Мягкое напоминание платникам (без paywall)'
    )
    parser.add_argument(
        '--free-return', action='store_true',
        help='Мягкое напоминание пользователям с бесплатными раскладами'
    )
    parser.add_argument(
        '--expired-sub', action='store_true',
        help='Напоминание об истёкшем доступе (+ меню оплаты)'
    )
    parser.add_argument(
        '--discussion', action='store_true',
        help='Объявление о функции обсуждения расклада (+ меню оплаты)'
    )
    parser.add_argument(
        '--restored', action='store_true',
        help='Сообщение о восстановлении работы бота'
    )
    parser.add_argument(
        '--friday13', action='store_true',
        help='Промо «Пятница 13»: удвоение пакетов гаданий (+ меню оплаты)'
    )
    parser.add_argument(
        '--fullmoon', action='store_true',
        help='Промо «Полнолуние»: удвоение пакетов раскладов (+ меню оплаты)'
    )
    parser.add_argument(
        '--tarologist-intro', action='store_true',
        help='Представление таролога Дианы и услуг «Личная консультация» (+ меню оплаты)'
    )
    parser.add_argument(
        '--tarologist-reminder', action='store_true',
        help='Напоминание о тарологе Диане (повторная рассылка, + меню оплаты)'
    )
    parser.add_argument(
        '--consult-diana-contact', action='store_true',
        help='Инструкция + кнопка «Написать Диане» после оплаты консультации'
    )
    parser.add_argument(
        '--consult-package', type=str, default='detailed',
        choices=['basic', 'detailed'],
        help='Пакет консультации для --consult-diana-contact (по умолчанию: detailed)'
    )
    parser.add_argument(
        '--feedback-request', action='store_true',
        help='Запрос обратной связи у купивших пользователей (автоматически берёт из БД)'
    )
    parser.add_argument(
        '--broadcast', action='store_true',
        help='Рассылать всем пользователям из БД (исключая заблокированных)'
    )

    args = parser.parse_args()
    fmt = args.format if args.format != 'none' else None

    try:
        if args.feedback_request and not args.user_id:
            paid = await get_paid_users()
            args.user_id = [u['user_id'] for u in paid]
            print(f"📋 Загружено {len(args.user_id)} купивших пользователей для запроса отзыва")
        elif args.broadcast:
            all_users = await get_all_users(include_blocked=False, include_unsubscribed_daily_card=True)
            args.user_id = [u['user_id'] for u in all_users]
            print(f"📋 Загружено {len(args.user_id)} пользователей для рассылки")

        if not args.user_id:
            print("❌ Ошибка: укажите user_id или используйте --broadcast / --feedback-request")
            return

        total = len(args.user_id)

        if args.feedback_request:
            print(f"📝 Отправка запроса обратной связи для {total} купивших пользователя(ей)...")
            for uid in args.user_id:
                await send_feedback_request(uid)
                await asyncio.sleep(0.05)

        elif args.payment_reminder:
            print(f"🚀 Отправка напоминаний об оплате для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_payment_reminder(uid)
                await asyncio.sleep(0.05)

        elif args.no_divinations:
            print(f"🚀 Отправка напоминаний о закончившихся гаданиях для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_no_divinations_reminder(uid)
                await asyncio.sleep(0.05)

        elif args.gentle_nudge:
            print(f"🚀 Отправка мягких напоминаний для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_gentle_nudge(uid)
                await asyncio.sleep(0.05)

        elif args.free_return:
            print(f"🚀 Отправка free-return напоминаний для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_free_return_nudge(uid)
                await asyncio.sleep(0.05)

        elif args.expired_sub:
            print(f"🚀 Отправка напоминаний об истёкшем доступе для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_expired_sub_reminder(uid)
                await asyncio.sleep(0.05)

        elif args.discussion:
            print(f"🚀 Отправка объявлений об обсуждении расклада для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_discussion_announcement(uid)
                await asyncio.sleep(0.05)

        elif args.restored:
            print(f"🔮 Отправка сообщений о восстановлении бота для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_bot_restored(uid)
                await asyncio.sleep(0.05)

        elif args.friday13:
            print(f"🌑 Отправка промо «Пятница 13» для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_friday13_promo(uid)
                await asyncio.sleep(0.05)

        elif args.fullmoon:
            print(f"🌕 Отправка промо «Полнолуние» для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_full_moon_promo(uid)
                await asyncio.sleep(0.05)

        elif args.tarologist_intro:
            print(f"🔮 Отправка представления таролога Дианы для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_tarologist_intro(uid)
                await asyncio.sleep(0.05)

        elif args.tarologist_reminder:
            print(f"🔮 Отправка напоминания о тарологе Диане для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_tarologist_reminder(uid)
                await asyncio.sleep(0.05)

        elif args.consult_diana_contact:
            pkg = CONSULT_PACKAGE_NAMES[args.consult_package]
            print(
                f"💬 Отправка контакта Дианы ({pkg}) для {total} пользователя(ей)..."
            )
            for uid in args.user_id:
                await send_consult_diana_contact(uid, package=args.consult_package)
                await asyncio.sleep(0.05)

        else:
            if not args.text:
                print(
                    "❌ Ошибка: укажите --text или используйте один из флагов: "
                    "--payment-reminder / --no-divinations / --gentle-nudge / --free-return / "
                    "--expired-sub / --discussion / --restored / "
                    "--friday13 / --fullmoon / --tarologist-intro / --tarologist-reminder / "
                    "--consult-diana-contact / --feedback-request"
                )
                return

            if total == 1:
                await send_message_to_user(args.user_id[0], args.text, fmt)
            else:
                await send_message_to_multiple_users(args.user_id, args.text, fmt)

        print("✅ Отправка завершена")
    finally:
        await Database.close_pool()
        if bot.session:
            await bot.session.close()


async def run():
    """Обёртка: создаём aiohttp-сессию для бота и запускаем main()."""
    async with aiohttp.ClientSession() as session:
        bot.session = session
        await main()


if __name__ == "__main__":
    asyncio.run(run())
