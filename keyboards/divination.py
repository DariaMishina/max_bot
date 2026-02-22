"""
Клавиатура для выбора типа гадания.
В Max используем MessageButton — при нажатии пользователь отправляет текст.
"""
from aiomax import buttons


def make_divination_kb() -> buttons.KeyboardBuilder:
    """
    Создаёт клавиатуру для выбора типа гадания
    """
    kb = buttons.KeyboardBuilder()
    kb.add(buttons.MessageButton("Ицзин"), buttons.MessageButton("Таро"))
    return kb
