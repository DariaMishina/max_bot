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

import aiohttp
from aiomax import buttons
from main.botdef import bot
from main.database import Database, update_user_blocked_status, get_all_users, is_send_blocked_error

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


async def send_payment_reminder(user_id: int):
    """Напоминание об оплате с кнопкой «Оплатить»"""
    text = "<b>Доступ к раскладам почти открыт — осталось только завершить оплату</b> 👇"
    kb = buttons.KeyboardBuilder()
    kb.row(buttons.CallbackButton("💳 Оплатить", "remind_pay"))

    print(f"📤 Отправляю напоминание об оплате пользователю {user_id}...")
    return await send_message_to_user(user_id, text, keyboard=kb)


async def send_no_divinations_reminder(user_id: int):
    """Напоминание тем, у кого закончились все гадания + меню оплаты"""
    from keyboards.pay import make_payment_kb
    from main.conversions import save_paywall_conversion

    reminder_text = (
        "✨ Привет! Может, пора сделать новый расклад?\n\n"
        "Карты помогли тебе увидеть то, что было скрыто. "
        "И если сейчас снова нужна ясность — я здесь.\n\n"
        "Выбери свой путь и продолжай находить ответы внутри себя 💫"
    )
    payment_text = (
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

    print(f"📤 Отправляю напоминание о закончившихся гаданиях пользователю {user_id}...")
    try:
        try:
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="no_divinations_reminder",
                metadata={'reminder_type': 'no_divinations', 'sent_via': 'send_message_script'}
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
        '', action='store_true',
        help='Рассылать всем пользователям из БД (исключая заблокированных)'
    )

    args = parser.parse_args()
    fmt = args.format if args.format != 'none' else None

    try:
        if args.broadcast:
            all_users = await get_all_users(include_blocked=False)
            args.user_id = [u['user_id'] for u in all_users]
            print(f"📋 Загружено {len(args.user_id)} пользователей для рассылки")

        if not args.user_id:
            print("❌ Ошибка: укажите user_id или используйте --broadcast")
            return

        total = len(args.user_id)

        if args.payment_reminder:
            print(f"🚀 Отправка напоминаний об оплате для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_payment_reminder(uid)
                await asyncio.sleep(0.05)

        elif args.no_divinations:
            print(f"🚀 Отправка напоминаний о закончившихся гаданиях для {total} пользователя(ей)...")
            for uid in args.user_id:
                await send_no_divinations_reminder(uid)
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

        else:
            if not args.text:
                print(
                    "❌ Ошибка: укажите --text или используйте один из флагов: "
                    "--payment-reminder / --no-divinations / --discussion / --restored / --friday13"
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
