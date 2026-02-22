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
    kb.row(buttons.CallbackButton("👑 Безлимит на месяц — 499₽", "pay_unlimited"))
    kb.row(buttons.CallbackButton("🔥 30 раскладов — 349₽", "pay_30_spreads"))
    kb.row(buttons.CallbackButton("🌟 20 раскладов — 249₽", "pay_20_spreads"))
    kb.row(buttons.CallbackButton("💫 10 раскладов — 149₽", "pay_10_spreads"))
    kb.row(buttons.CallbackButton("🌙 3 расклада — 69₽", "pay_3_spreads"))
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
