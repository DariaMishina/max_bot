"""Chat adapters for the same persistent service used by the WebApp."""
import asyncio
import uuid
from main import webapp_service as service


async def run(user_id, payload, key):
    op = await service.submit(user_id, key, payload, source='chat')
    await service.perform(op['id'])
    # The HTTP worker may have claimed it first.
    for _ in range(240):
        op = await service.operation(user_id, op['id'])
        if op['status'] == 'failed':
            raise service.ServiceError(op['error'])
        if op['status'] == 'completed':
            return await service.reading(user_id, op['result_id'])
        await asyncio.sleep(.5)
    raise service.ServiceError('Ответ ещё готовится. Откройте его в приложении.')


def request_key(user_id, value):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'max-webapp-chat:{user_id}:{value}')


async def tarot(*, user_id, question, card_ids, cursor, data, **kwargs):
    from main.botdef import bot
    from keyboards.main_menu import make_back_to_menu_kb
    key = data.setdefault('webapp_request_id', str(uuid.uuid4()))
    cursor.change_data(data)
    try:
        result = await run(user_id, {'question': question, 'kind': 'tarot', 'mode': 'own', 'cards': card_ids}, key)
        cursor.change_data({'divination_id': result['id']})
        cursor.change_state('chatting')
        return True
    except service.ServiceError as error:
        await bot.send_message(str(error), user_id=user_id, keyboard=make_back_to_menu_kb())
        return False


async def iching(message, cursor, question, user_id):
    data = cursor.get_data() or {}
    key = data.setdefault('webapp_request_id', str(uuid.uuid4()))
    cursor.change_data(data)
    try:
        result = await run(user_id, {'question': question, 'kind': 'iching'}, key)
        cursor.change_data({'divination_id': result['id']})
        cursor.change_state('chatting')
    except service.ServiceError as error:
        await message.reply(str(error))


async def followup(message, cursor):
    from main.message_routing import NAVIGATION_MESSAGES
    text = (message.content or '').strip()
    if text in NAVIGATION_MESSAGES or text.startswith('/'):
        return
    data = cursor.get_data() or {}
    rid = data.get('divination_id')
    if not rid:
        await message.reply('Откройте расклад из истории приложения.')
        return
    key = request_key(message.sender.user_id, getattr(message, 'id', None) or str(uuid.uuid4()))
    try:
        await run(message.sender.user_id, {'kind':'followup','reading_id':rid,'question':text}, key)
    except (service.ServiceError, ValueError) as error:
        await message.reply(str(error))
