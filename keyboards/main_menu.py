"""
Главное меню — в Max нет ReplyKeyboard, используем inline-кнопки (CallbackButton)
или MessageButton (которая отправляет текст при нажатии).

make_main_menu()       — полное меню (показывается по кнопке «◀ В меню» и после /start)
make_back_to_menu_kb() — одна кнопка «◀ В меню» (прикрепляется к каждому ответу бота)
"""
from aiomax import buttons


def make_main_menu() -> buttons.KeyboardBuilder:
    kb = buttons.KeyboardBuilder()
    kb.row(buttons.MessageButton("Новый расклад 🃏"))
    kb.row(buttons.MessageButton("Личная консультация 🔮"))
    kb.row(buttons.MessageButton("Карта дня ✨"))
    kb.row(buttons.MessageButton("Мои гадания 🔮"))
    kb.row(buttons.MessageButton("Купить расклады 💎"))
    return kb


def make_back_to_menu_kb() -> buttons.KeyboardBuilder:
    kb = buttons.KeyboardBuilder()
    kb.row(buttons.CallbackButton("◀ В меню", "back_to_menu"))
    return kb
