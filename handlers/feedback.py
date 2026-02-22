"""
Обработчик обратной связи — адаптировано для Max (aiomax).

В Max нет reply_to_message как в Telegram.
Вместо этого используем FSM: после получения обратной связи,
бот переходит в состояние ожидания ответа.
"""
import logging
import aiomax
from aiomax import fsm, filters

from main.botdef import bot
from main.config_reader import config

router = aiomax.Router()

FEEDBACK_PREFIX = "📝 Обратная связь:"


@router.on_command('feedback')
async def cmd_feedback(ctx: aiomax.CommandContext, cursor: fsm.FSMCursor):
    """
    Команда /feedback — просим пользователя оставить обратную связь.
    """
    logging.info(f"cmd_feedback: user_id={ctx.sender.user_id}")
    cursor.change_state('waiting_feedback')
    await ctx.reply(
        f"{FEEDBACK_PREFIX}\n\n"
        "Напишите ваш отзыв, предложение или вопрос.\n"
        "Для отмены нажмите ◀ В меню"
    )


@router.on_message(filters.state('waiting_feedback'))
async def handle_feedback(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Получаем ответ обратной связи"""
    # Проверяем, не команда ли это
    if message.content and message.content.strip().startswith("/"):
        cursor.clear()
        return
    
    answer_text = (message.content or "").strip()
    if not answer_text:
        return
    
    user_name = message.sender.name or "—"
    username = f"@{message.sender.username}" if message.sender.username else "—"
    user_id = message.sender.user_id
    
    logging.info(
        "[FEEDBACK] from=%s (%s, id=%s) answer=%r",
        user_name, username, user_id, answer_text,
    )

    admin_chat_id = config.admin_chat_id
    if admin_chat_id:
        try:
            await bot.send_message(
                f"📩 <b>Обратная связь</b>\n"
                f"👤 {user_name} ({username}, id={user_id})\n\n"
                f"<b>Ответ:</b>\n{answer_text}",
                user_id=admin_chat_id,
                format='html',
            )
        except Exception as e:
            logging.error(f"[FEEDBACK] Failed to notify admin: {e}", exc_info=True)

    try:
        from keyboards.main_menu import make_back_to_menu_kb
        await message.reply("Спасибо! Я записала твою обратную связь 🙏", keyboard=make_back_to_menu_kb())
    except Exception as e:
        logging.warning(f"[FEEDBACK] Failed to ack user: {e}")
    
    cursor.clear()
