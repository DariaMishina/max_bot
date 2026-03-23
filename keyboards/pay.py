"""
Клавиатуры для оплаты.
В Max используем CallbackButton для inline-кнопок с payload.
"""
from aiomax import buttons


def make_payment_kb() -> buttons.KeyboardBuilder:
    """
    Создаёт клавиатуру с вариантами оплаты.
    Используем CallbackButton чтобы получать payload при нажатии.
    """
    kb = buttons.KeyboardBuilder()
    kb.row(buttons.CallbackButton("👑 Безлимит на месяц — 599₽", "pay_unlimited"))
    kb.row(buttons.CallbackButton("🔥 30 раскладов — 399₽", "pay_30_spreads"))
    kb.row(buttons.CallbackButton("🌟 20 раскладов — 289₽", "pay_20_spreads"))
    kb.row(buttons.CallbackButton("💫 10 раскладов — 179₽", "pay_10_spreads"))
    kb.row(buttons.CallbackButton("🌙 3 расклада — 99₽", "pay_3_spreads"))
    kb.row(buttons.CallbackButton("◀ В меню", "back_to_menu"))
    return kb


def make_email_confirmation_kb() -> buttons.KeyboardBuilder:
    """
    Создаёт клавиатуру для подтверждения email
    """
    kb = buttons.KeyboardBuilder()
    kb.add(
        buttons.CallbackButton("✅ Все верно", "email_confirm"),
        buttons.CallbackButton("❌ Исправить", "email_edit")
    )
    return kb
