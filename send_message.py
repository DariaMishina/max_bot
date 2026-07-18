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
import os
import ssl
import sys
from typing import Optional

import aiohttp
import aiomax
from aiomax import buttons
from main.botdef import bot
from main.database import (
    Database,
    update_user_blocked_status,
    get_all_users,
    get_paid_users,
    mark_expired_access_reminder_sent,
    get_expired_access_reminder_stage_for_user,
)
from main.send_errors import is_unreachable_user_error, mark_user_unreachable

SendOutcome = tuple[bool, bool]  # (delivered, unreachable_user)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def send_message_to_user(
    user_id: int,
    text: str,
    format: str = "html",
    keyboard=None,
) -> SendOutcome:
    """
    Отправить сообщение одному пользователю в Max.

    Returns:
        (delivered, unreachable_user)
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
        return True, False
    except Exception as e:
        unreachable = is_unreachable_user_error(e)
        if unreachable:
            print(f"❌ Пользователь {user_id} недоступен: {e}")
            await mark_user_unreachable(user_id, e)
        else:
            print(f"❌ Ошибка отправки сообщению пользователю {user_id}: {e}")
            logging.error(f"Error sending message to user {user_id}: {e}", exc_info=True)
        return False, unreachable


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
        success, _ = await send_message_to_user(user_id, text, format, keyboard)
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


async def send_payment_reminder(user_id: int, stage: str = '10m') -> SendOutcome:
    """Напоминание об оплате с кнопкой «Оплатить».

    stage: '10m' | '1h' | '3h' | '24h' — этап автоматической рассылки.
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
        '24h': (
            "Прошли сутки — доступ к раскладам всё ещё можно открыть 🔮\n\n"
            "Если захочешь вернуться, нажми «Оплатить» ниже."
        ),
    }
    text = texts.get(stage, texts['10m'])
    kb = buttons.KeyboardBuilder()
    kb.row(buttons.CallbackButton("💳 Оплатить", "remind_pay"))

    print(f"📤 Отправляю напоминание об оплате ({stage}) пользователю {user_id}...")
    return await send_message_to_user(user_id, text, keyboard=kb)


async def send_paid_inactivity_nudge(user_id: int, stage: str = '1d') -> SendOutcome:
    """Мягкое напоминание платнику, который давно не делал расклад."""
    texts = {
        '1d': (
            "Привет 🔮\n\n"
            "Просто напомню — карты здесь, если захочется новый расклад.\n\n"
            "Можно спросить о чём угодно ✨"
        ),
        '3d': (
            "Давно не раскладывали 🔮\n\n"
            "Если что-то крутится в голове — можешь спросить у карт. Я рядом 💫"
        ),
        '5d': (
            "Привет! Доступ к раскладам активен — можешь вернуться когда удобно.\n\n"
            "Иногда один вопрос стоит целого разговора 🔮"
        ),
        '10d': (
            "Просто заглянула 🔮\n\n"
            "Если захочешь снова спросить у карт — я здесь. Без спешки ✨"
        ),
    }
    text = texts.get(stage, texts['1d'])
    print(f"📤 Отправляю paid inactivity nudge ({stage}) пользователю {user_id}...")
    return await send_message_to_user(user_id, text, format=None)


async def send_free_user_nudge(user_id: int, category: str, stage: str) -> SendOutcome:
    """Nudge для бесплатных пользователей (C1–C4)."""
    if category == 'c1':
        from keyboards.main_menu import make_main_menu
        texts = {
            '1h': (
                "Привет 🔮\n\n"
                "Ты заходил(а), но мы ещё не погадали вместе.\n\n"
                "Задай первый вопрос — карты уже ждут ✨"
            ),
            '3h': (
                "Можно начать с простого: «Что мне важно знать сегодня?» 🔮\n\n"
                "Я рядом."
            ),
            '24h': (
                "Если захочешь попробовать — просто нажми «Новый расклад» в меню.\n\n"
                "Я здесь, когда будешь готов(а) 💫"
            ),
        }
        text = texts.get(stage, texts['1h'])
        return await send_message_to_user(user_id, text, keyboard=make_main_menu(), format=None)

    if category == 'c2':
        texts = {
            '3h': (
                "Мы не договорили 🔮\n\n"
                "Хочешь задать ещё один вопрос картам? "
                "У тебя остались бесплатные расклады ✨"
            ),
            '24h': (
                "У тебя ещё есть бесплатные расклады — "
                "можешь использовать, когда будет удобно 💫"
            ),
            '48h': (
                "Просто напоминаю: бесплатные расклады ещё доступны.\n\n"
                "Загляни, если нужна ясность 🔮"
            ),
        }
        text = texts.get(stage, texts['3h'])
        return await send_message_to_user(user_id, text, format=None)

    if category == 'c3':
        from keyboards.pay import make_payment_kb
        texts = {
            '1h': (
                "Бесплатные расклады закончились — но вопросы к картам никуда не делись 🔮\n\n"
                "Выбери пакет и продолжай ✨"
            ),
            '3h': (
                "Если сейчас нужна ясность — доступ можно открыть за пару минут 💫"
            ),
            '24h': (
                "Карты ждут твоего вопроса 🔮\n\n"
                "Нажми «Оплатить» и продолжай раскладывать ✨"
            ),
            '48h': (
                "Последнее: если захочешь вернуться — кнопка ниже.\n\n"
                "Без спешки 💫"
            ),
        }
        text = texts.get(stage, texts['1h'])
        payment_text = _broadcast_payment_text()
        try:
            from main.conversions import save_paywall_conversion
            from main.metrika_mp import send_conversion_event
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="free_nudge_c3",
                metadata={'category': 'c3', 'stage': stage, 'sent_via': 'nudge'},
            )
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)
        try:
            await bot.send_message(text, user_id=user_id, format=None)
            await bot.send_message(payment_text, user_id=user_id, keyboard=make_payment_kb(), format='html')
            try:
                await update_user_blocked_status(user_id, False)
            except Exception as db_error:
                logging.warning(f"Failed to update blocked status for user {user_id}: {db_error}")
            return True, False
        except Exception as e:
            unreachable = is_unreachable_user_error(e)
            if unreachable:
                await mark_user_unreachable(user_id, e)
            else:
                logging.error(f"Error sending free nudge C3 to user {user_id}: {e}", exc_info=True)
            return False, unreachable

    if category == 'c4':
        texts = {
            '3d': (
                "Привет 🔮\n\n"
                "Давно не раскладывали. Если что-то крутится в голове — "
                "можешь спросить у карт ✨"
            ),
            '7d': (
                "Карты здесь, если понадобится ясность.\n\n"
                "Возвращайся, когда будет удобно 💫"
            ),
        }
        text = texts.get(stage, texts['3d'])
        return await send_message_to_user(user_id, text, format=None)

    logging.warning(f"Unknown free nudge category {category} for user {user_id}")
    return False, False


async def send_expired_access_reminder(
    user_id: int,
    stage: str = 'day0',
    *,
    sent_via: str = 'send_message_script',
) -> SendOutcome:
    """Напоминание пользователям с истёкшим платным доступом — серия day0–day3."""
    from keyboards.pay import make_payment_kb
    from main.conversions import save_paywall_conversion

    texts = {
        'day0': (
            "Привет! 💫\n\n"
            "Твои расклады закончились, но карты всё ещё помнят тебя.\n\n"
            "Если снова нужна ясность — я здесь ✨"
        ),
        'day1': (
            "Карты заметили, что ты давно не задавал(а) вопросов 🔮\n\n"
            "Может, пора?"
        ),
        'day2': (
            "Иногда один расклад помогает увидеть то, что не замечаешь.\n\n"
            "Я рядом, когда будешь готов(а) 💫"
        ),
        'day3': (
            "Последнее: если захочешь вернуться — нажми кнопку ниже.\n\n"
            "Без спешки ✨"
        ),
    }
    reminder_text = texts.get(stage, texts['day0'])
    payment_text = _broadcast_payment_text()

    print(f"📤 Отправляю напоминание об истёкшем доступе ({stage}) пользователю {user_id}...")
    try:
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="expired_access_reminder",
                metadata={
                    'reminder_type': 'expired_access_reminder',
                    'stage': stage,
                    'sent_via': sent_via,
                },
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(reminder_text, user_id=user_id, format=None)
        await bot.send_message(payment_text, user_id=user_id, keyboard=make_payment_kb(), format='html')
        print(f"✅ Напоминание об истёкшем доступе ({stage}) отправлено пользователю {user_id}")
        try:
            await update_user_blocked_status(user_id, False)
        except Exception as db_error:
            logging.warning(f"Failed to update blocked status for user {user_id}: {db_error}")
        return True, False
    except Exception as e:
        unreachable = is_unreachable_user_error(e)
        if unreachable:
            await mark_user_unreachable(user_id, e)
        else:
            logging.error(
                f"Error sending напоминания об истёкшем доступе to user {user_id}: {e}",
                exc_info=True,
            )
        return False, unreachable


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
        await _handle_send_error(user_id, e, "напоминания о закончившихся гаданиях")
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
    from keyboards.main_menu import make_main_menu

    text = (
        "Привет 🔮\n\n"
        "Ты заходил(а), но мы ещё не успели погадать вместе.\n\n"
        "Задай свой первый вопрос — карты уже ждут. "
        "Можно начать с чего-то простого: «Что мне важно знать сегодня?»\n\n"
        "Выбери расклад в меню ниже ✨"
    )
    print(f"📤 Отправляю welcome-активацию пользователю {user_id}...")
    return await send_message_to_user(user_id, text, keyboard=make_main_menu(), format=None)


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
    stage: Optional[str] = None,
):
    """Alias для ручной отправки — делегирует в send_expired_access_reminder."""
    return await send_expired_access_reminder(
        user_id,
        stage=stage or 'day0',
        sent_via=sent_via,
    )


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
        await _handle_send_error(user_id, e, "объявления об обсуждении расклада")
        return False


async def send_own_cards_announcement(user_id: int):
    """Объявление о функции «Написать свои карты»"""
    from keyboards.main_menu import make_main_menu

    text = (
        "✨ <b>Новое в боте!</b>\n\n"
        "Теперь в раскладе Таро можно <b>написать свои карты</b> ✍️\n\n"
        "Если ты уже разложил(а) карты и они лежат перед тобой — "
        "не нужно тянуть их заново в боте.\n\n"
        "<b>Как это работает:</b>\n"
        "1. Нажми <b>Новый расклад 🃏</b>\n"
        "2. Напиши свой вопрос\n"
        "3. Выбери «Таро» → <b>✍️ Написать свои карты</b>\n"
        "4. Отправь три названия через запятую или пробел, например:\n"
        "   <i>Башня, Туз Кубков, Десятка Мечей</i>\n"
        "   или <i>Башня семерка чаш повешенный</i>\n\n"
        "Бот распознает карты и сделает толкование 🔮"
    )
    print(f"📤 Отправляю объявление «Написать свои карты» пользователю {user_id}...")
    return await send_message_to_user(user_id, text, keyboard=make_main_menu())


async def send_bot_restored(user_id: int):
    """Сообщение о восстановлении работы бота"""
    from keyboards.main_menu import make_main_menu

    text = (
        "Привет! Это <b>Сфера Таро</b> 🔮\n\n"
        "Рады сообщить: бот снова работает в полном режиме!\n\n"
        "Выбери действие в меню ниже или напиши свой вопрос в чат 💫"
    )
    print(f"📤 Отправляю сообщение о восстановлении бота пользователю {user_id}...")
    return await send_message_to_user(user_id, text, keyboard=make_main_menu())


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
        await _handle_send_error(user_id, e, "промо «Пятница 13»")
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
        await _handle_send_error(user_id, e, "представления таролога Дианы")
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
        await _handle_send_error(user_id, e, f"контакта Дианы ({package_name})")
        return False


async def send_tarologist_reminder(
    user_id: int,
    *,
    sent_via: str = 'send_message_script',
):
    """Повторное напоминание о тарологе Диане — для тех, кто уже видел представление."""
    from keyboards.pay import make_consultation_kb
    from main.conversions import save_paywall_conversion

    reminder_text = (
        "Иногда хочется просто спросить — и услышать понятный, тёплый ответ 💗\n\n"
        "Что тебя ждёт в любви?\n"
        "Какие возможности откроются в финансах? 🫣\n"
        "Что происходит на работе — и куда двигаться дальше? 💼\n"
        "Как наладить отношения с родными, когда всё кажется запутанным? 🏡\n"
        "На что обратить внимание, чтобы не упустить важное? 💫\n\n"
        "Если эти вопросы откликаются — "
        "<b>таролог Диана</b> с радостью разберёт твою ситуацию через карты. "
        "Лично, бережно и без общих фраз — так, чтобы стало спокойнее и яснее ✨\n\n"
        "<b>Два формата на выбор:</b>\n\n"
        "✨ <b>Базовый разбор — 500 ₽</b>\n"
        "Один вопрос — картина ситуации и совет. Коротко, по делу и с заботой.\n\n"
        "🔮 <b>Подробный разбор — 1500 ₽</b> (оптимально)\n"
        "Расклад на ситуацию, до 5 доп. вопросов:\n"
        "— что сейчас\n"
        "— скрытые моменты\n"
        "— к чему идёт\n"
        "— совет карт\n\n"
        "Диана ответит в течение часа (10:00–22:00 МСК) — ты не останешься с вопросами одна 🔮"
    )

    print(f"📤 Отправляю напоминание о тарологе Диане пользователю {user_id}...")
    try:
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="tarologist_reminder",
                metadata={'reminder_type': 'tarologist_reminder', 'sent_via': sent_via}
            )
            from main.metrika_mp import send_conversion_event
            await send_conversion_event(user_id, 'paywall')
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

        await bot.send_message(reminder_text, user_id=user_id, keyboard=make_consultation_kb(), format='html')
        print(f"✅ Напоминание о тарологе отправлено пользователю {user_id}")
        return True
    except Exception as e:
        await _handle_send_error(user_id, e, "напоминания о тарологе Диане")
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
        await _handle_send_error(user_id, e, "промо «Полнолуние»")
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


async def _handle_send_error(user_id: int, error: Exception, action_desc: str) -> bool:
    """Общая обработка ошибок отправки. Returns unreachable."""
    if is_unreachable_user_error(error):
        print(f"❌ Пользователь {user_id} недоступен ({action_desc})")
        await mark_user_unreachable(user_id, error)
        return True
    print(f"❌ Ошибка отправки {action_desc} пользователю {user_id}: {error}")
    logging.error(f"Error sending {action_desc} to user {user_id}: {error}", exc_info=True)
    return False


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
        '--activation', action='store_true',
        help='Welcome-активация: заходил, но ещё не сделал расклад (+ меню)'
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
        '--own-cards', action='store_true',
        help='Объявление о функции «Написать свои карты» (+ главное меню)'
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

        elif args.activation:
            print(f"📤 Отправка welcome-активации для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_activation_nudge(uid)
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
                stage = await get_expired_access_reminder_stage_for_user(uid) or 'day0'
                success, _ = await send_expired_access_reminder(uid, stage=stage)
                if success:
                    await mark_expired_access_reminder_sent(uid, stage)
                await asyncio.sleep(0.05)

        elif args.discussion:
            print(f"🚀 Отправка объявлений об обсуждении расклада для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_discussion_announcement(uid)
                await asyncio.sleep(0.05)

        elif args.own_cards:
            print(f"✍️ Отправка объявлений «Написать свои карты» для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_own_cards_announcement(uid)
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
                    "--payment-reminder / --no-divinations / --activation / --gentle-nudge / "
                    "--free-return / "
                    "--expired-sub / --discussion / --own-cards / --restored / "
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
    # aiomax 2.12.5+: API-методы используют относительные пути + base_url,
    # для platform-api2 нужен сертификат Минцифры.
    connector = None
    if bot.use_certificate:
        cert = os.path.join(
            os.path.dirname(aiomax.__file__), "russian_trusted_root_ca.cer"
        )
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.load_verify_locations(cafile=cert)
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(
        headers={"Authorization": bot.access_token},
        connector=connector,
        base_url=bot.api_url,
    ) as session:
        bot.session = session
        await main()


if __name__ == "__main__":
    asyncio.run(run())
