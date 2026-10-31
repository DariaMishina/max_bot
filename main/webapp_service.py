"""Shared MAX-bot/WebApp operations; all balances live in the bot database.

Operations survive process restarts. Generation, debit and completion commit
atomically. PostgreSQL row locks coordinate chat and WebApp, not browser state.
"""
import asyncio
from datetime import datetime
import hashlib
from pathlib import Path
import json
import logging
import os
import random
import re
import uuid
from zoneinfo import ZoneInfo

from main.database import Database, get_table_name as table
from main.question_validation import validate_question_text

THEMES = {
    'timeline': ('Прошлое', 'Настоящее', 'Будущее'),
    'choice': ('Ситуация', 'Возможность', 'Совет'),
    'relationships': ('Ваши чувства', 'Динамика отношений', 'Совет'),
}


class ServiceError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def decode(value, default=None):
    if value is None:
        return default
    return json.loads(value) if isinstance(value, str) else value


def plain(text):
    from html import unescape
    return unescape(re.sub(r'<[^>]*>', '', text or ''))


async def initialize():
    # Same statements as migrations/20261031_max_webapp.sql. Local runs use unsuffixed max_* tables.
    sql = (Path(__file__).resolve().parents[1] / 'migrations' / '20261031_max_webapp.sql').read_text()
    await Database.execute_query(sql)
    from main.database import ensure_pending_questions_table, ensure_webapp_follow_up_context_table
    await ensure_pending_questions_table()
    await ensure_webapp_follow_up_context_table()


async def ensure_user(user):
    pool = await Database.get_pool()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(f'''INSERT INTO {table('users')}(user_id,first_name,full_name,daily_card_subscribed)
            VALUES($1,$2,$2,false) ON CONFLICT(user_id) DO NOTHING''', user['id'], user.get('first_name') or 'Гость')
        await conn.execute(f'''INSERT INTO {table('user_balances')}(user_id,free_divinations_remaining)
            VALUES($1,3) ON CONFLICT(user_id) DO NOTHING''', user['id'])


def access(balance):
    if balance and balance['unlimited_until'] and balance['unlimited_until'] > datetime.now():
        return 'unlimited'
    if balance and balance['free_divinations_remaining'] > 0:
        return 'free'
    if balance and balance['paid_divinations_remaining'] > 0:
        return 'paid'
    return 'none'


def normalize_request(data):
    from handlers.tarot_cards import TAROT_CARDS
    if not isinstance(data, dict) or not isinstance(data.get('question'), str):
        raise ServiceError('Введите вопрос.')
    question = validate_question_text(data['question'])
    kind = data.get('kind', 'tarot')
    if kind not in ('tarot', 'iching', 'followup'):
        raise ServiceError('Неизвестный тип расклада.')
    if kind == 'followup':
        if type(data.get('reading_id')) is not int:
            raise ServiceError('Укажите расклад для уточнения.')
        return {'kind': kind, 'question': question, 'reading_id': data['reading_id']}
    mode = data.get('mode', 'random')
    if mode not in ('random', 'manual', 'own'):
        raise ServiceError('Неизвестный способ выбора.')
    theme = data.get('theme', 'timeline')
    if theme not in THEMES:
        raise ServiceError('Неизвестная схема расклада.')
    cards = data.get('cards', [])
    if kind == 'tarot' and mode != 'random':
        if not isinstance(cards, list) or len(cards) != 3 or any(not isinstance(c, str) or c not in TAROT_CARDS for c in cards) or len(set(cards)) != 3:
            raise ServiceError('Выберите три разные карты из колоды.')
    else:
        cards = []
    return {'kind': kind, 'question': question, 'mode': mode, 'cards': cards, 'theme': theme}


async def submit(user_id, request_id, data, *, source='webapp'):
    try:
        request_id = uuid.UUID(str(request_id))
    except ValueError:
        raise ServiceError('Неверный идентификатор запроса.')
    payload = normalize_request(data)
    # The delivery channel is set by the server adapter, never by API input.
    if source in ('chat', 'chat-picker'):
        payload['delivery'] = 'chat'
    if source == 'chat-picker':
        if payload['kind'] != 'tarot' or payload['mode'] != 'manual':
            raise ServiceError('Для вопроса из чата выберите три карты.', 400)
        payload['pending_version'] = str(data.get('pending_version', ''))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    pool = await Database.get_pool()
    async with pool.acquire() as conn, conn.transaction():
        # Serialize submissions without waiting on the long balance transaction.
        await conn.execute('SELECT pg_advisory_xact_lock($1)', user_id)
        existing = await conn.fetchrow(f"SELECT * FROM {table('webapp_operations')} WHERE id=$1", request_id)
        if existing:
            if existing['user_id'] != user_id or existing['fingerprint'] != fingerprint:
                raise ServiceError('Этот идентификатор уже использован для другого запроса.', 409)
            return dict(existing)
        if source == 'chat-picker':
            pending = await conn.fetchrow(f"SELECT question,created_at FROM {table('pending_questions')} WHERE user_id=$1 FOR UPDATE", user_id)
            if not pending or pending['question'] != payload['question'] or pending['created_at'].isoformat() != payload['pending_version']:
                raise ServiceError('Вопрос в чате изменился. Откройте выбор карт заново.', 409)
        active = await conn.fetchrow(f"SELECT * FROM {table('webapp_operations')} WHERE user_id=$1 AND status='queued'", user_id)
        if active:
            raise ServiceError('Предыдущий ответ ещё готовится. Откройте его на главной.', 409)
        await conn.execute(f'''INSERT INTO {table('webapp_operations')}(id,user_id,fingerprint,payload)
            VALUES($1,$2,$3,$4)''', request_id, user_id, fingerprint, encoded)
    return await operation(user_id, request_id)


async def operation(user_id, request_id):
    try:
        uid = uuid.UUID(str(request_id))
    except ValueError:
        raise ServiceError('Операция не найдена.', 404)
    row = await Database.fetch_one(f'SELECT * FROM {table("webapp_operations")} WHERE id=$1 AND user_id=$2', uid, user_id)
    if not row:
        raise ServiceError('Операция не найдена.', 404)
    return dict(row)


async def generate(payload, cards, history=None):
    from handlers.tarot_cards import get_card_info
    from handlers.hexagrams import get_hexagram_info
    from main.llm_divination import call_deepseek
    if os.getenv('WEBAPP_DEMO') == 'true':
        await asyncio.sleep(0.15)
        if payload['kind'] == 'followup':
            return 'Демонстрационный ответ. Обратите внимание на то, что вы можете изменить сейчас: обозначьте свои ожидания и выберите один небольшой следующий шаг.'
        return 'Это демонстрационное толкование для проверки интерфейса.\n\nСитуация\nСейчас полезно остановиться и посмотреть на вопрос с разных сторон. Карты помогают обозначить чувства и возможные действия.\n\nСовет\nВыберите небольшой шаг, который зависит от вас. Решение остаётся за вами.'
    if payload['kind'] == 'followup':
        return await call_deepseek(history + [{'role': 'user', 'content': payload['question']}],
            'Помоги уточнить расклад. Учитывай исходные карты и весь разговор. Отвечай на русском, без HTML.', format_output=False)
    if payload['kind'] == 'iching':
        card = get_hexagram_info(cards[0])
        prompt = f"Вопрос: {payload['question']}\nГексаграмма: {card['name']}. {card['meaning']}"
        system = 'Ты консультант по Ицзин. Объясни гексаграмму применительно к вопросу: ситуация, возможное развитие, совет. На русском, без HTML.'
    else:
        positions = THEMES[payload['theme']]
        headers = [f"{position}: {get_card_info(cid)['name']}" for position, cid in zip(positions, cards)]
        prompt = f"Вопрос: {payload['question']}\n" + '\n'.join(f"{position}: {get_card_info(cid)['name']} — {get_card_info(cid)['meaning']}" for position, cid in zip(positions, cards))
        system = ('Ты опытный таролог. Отвечай на русском, мудро и по существу. '
                  'Сохраняй выбранные позиции: ' + ', '.join(positions) + '. '
                  'Используй ровно эти три заголовка, каждый на отдельной строке: ' + '; '.join(headers) + '. '
                  'Под каждым заголовком напиши 2–3 предложения в контексте вопроса. '
                  'В конце заголовок «Общее толкование:» и 3–4 предложения, включая конкретный совет. '
                  'Всего 4–6 коротких абзацев, без дополнительных разделов, HTML, markdown и списков. '
                  'Не обещай неизбежных событий.')
    system += ' Разделяй ответ на короткие абзацы. Заголовки позиций и разделов пиши на отдельной строке, отделяя пустой строкой от текста.'
    return await call_deepseek([{'role': 'user', 'content': prompt}], system, format_output=False)


async def perform(operation_id):
    from handlers.tarot_cards import TAROT_CARDS
    pool = await Database.get_pool()
    completed = None
    try:
        async with pool.acquire() as conn, conn.transaction():
            op = await conn.fetchrow(f"SELECT * FROM {table('webapp_operations')} WHERE id=$1 FOR UPDATE SKIP LOCKED", operation_id)
            if not op or op['status'] != 'queued':
                return
            uid = op['user_id']
            payload = decode(op['payload'])
            balance = await conn.fetchrow(f"SELECT * FROM {table('user_balances')} WHERE user_id=$1 FOR UPDATE", uid)
            if payload.get('pending_version'):
                pending = await conn.fetchrow(f"SELECT question,created_at FROM {table('pending_questions')} WHERE user_id=$1 FOR UPDATE", uid)
                if not pending or pending['question'] != payload['question'] or pending['created_at'].isoformat() != payload['pending_version']:
                    raise ServiceError('Вопрос в чате изменился. Откройте выбор карт заново.', 409)
            if payload['kind'] == 'followup':
                reading = await conn.fetchrow(f"SELECT * FROM {table('divinations')} WHERE id=$1 AND user_id=$2", payload['reading_id'], uid)
                if not reading:
                    raise ServiceError('Расклад не найден.', 404)
                followups = await conn.fetch(f"SELECT * FROM {table('webapp_followups')} WHERE reading_id=$1 ORDER BY id", reading['id'])
                if len(followups) >= (2 if reading['is_free'] else 5):
                    raise ServiceError('Все уточнения к этому раскладу использованы.', 409)
                history = [{'role': 'user', 'content': reading['question'] + '\nКарты: ' + str(decode(reading['selected_cards']))}, {'role': 'assistant', 'content': plain(reading['interpretation'])}]
                for item in followups:
                    history.extend([{'role': 'user', 'content': item['question']}, {'role': 'assistant', 'content': item['answer']}])
                answer = await generate(payload, [], history)
                await conn.execute(f"INSERT INTO {table('webapp_followups')}(reading_id,question,answer) VALUES($1,$2,$3)", reading['id'], payload['question'], answer)
                result_id = reading['id']
            else:
                use = access(balance)
                if use == 'none':
                    raise ServiceError('Расклады закончились. Выберите пакет в профиле.', 403)
                cards = payload['cards']
                if payload['kind'] == 'iching':
                    cards = [str(random.randint(1, 64))]
                elif payload['mode'] == 'random':
                    cards = random.sample(list(TAROT_CARDS), 3)
                answer = await generate(payload, cards)
                result_id = await conn.fetchval(f'''INSERT INTO {table('divinations')}
                    (user_id,divination_type,question,selected_cards,interpretation,is_free,webapp_theme)
                    VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id''', uid,
                    'Ицзин' if payload['kind'] == 'iching' else 'Таро', payload['question'], json.dumps(cards), answer, use == 'free', payload['theme'])
                debit = {'free': 'free_divinations_remaining=free_divinations_remaining-1,', 'paid': 'paid_divinations_remaining=paid_divinations_remaining-1,', 'unlimited': ''}[use]
                await conn.execute(f"UPDATE {table('user_balances')} SET {debit} total_divinations_used=total_divinations_used+1,updated_at=now() WHERE user_id=$1", uid)
                if payload.get('delivery') == 'chat':
                    await conn.execute(f"DELETE FROM {table('pending_questions')} WHERE user_id=$1 AND question=$2", uid, payload['question'])
                # Shared persisted follow-up pointer, compatible with the chat router.
                context = json.dumps([{'role': 'user', 'content': payload['question']}, {'role': 'assistant', 'content': answer}])
                if payload.get('delivery') == 'chat':
                    await conn.execute(f'''INSERT INTO {table('webapp_follow_up_context')}
                    (user_id,divination_id,conversation_history,is_free,original_interpretation)
                    VALUES($1,$2,$3,$4,$5) ON CONFLICT(user_id) DO UPDATE SET
                    divination_id=EXCLUDED.divination_id, conversation_history=EXCLUDED.conversation_history,
                    is_free=EXCLUDED.is_free,original_interpretation=EXCLUDED.original_interpretation,
                    follow_up_count=0,created_at=now()''', uid, result_id, context, use == 'free', answer)
            await conn.execute(f"UPDATE {table('webapp_operations')} SET status='completed',result_id=$2,completed_at=now() WHERE id=$1", operation_id, result_id)
            completed = (uid, result_id, payload, answer)
    except asyncio.CancelledError:
        raise  # Transaction rolled back; queued operation will resume after restart.
    except Exception as error:
        message = str(error) if isinstance(error, ServiceError) else 'Не удалось получить ответ. Расклад не списан; попробуйте снова.'
        logging.exception('WebApp operation failed: %s', operation_id)
        await Database.execute_query(f"UPDATE {table('webapp_operations')} SET status='failed',error=$2,completed_at=now() WHERE id=$1 AND status='queued'", operation_id, message)
    if completed and completed[2].get('delivery') == 'chat' and os.getenv('WEBAPP_DEMO') != 'true':
        # Sending to MAX must never roll back a completed reading or debit.
        try:
            from main.botdef import bot
            from keyboards.main_menu import make_back_to_menu_kb
            uid, rid, payload, answer = completed
            if payload['kind'] != 'followup':
                bot.storage.clear(uid)
            from main.webapp_chat_format import chat_message_chunks
            if payload['kind'] == 'tarot':
                from handlers.tarot_cards import send_card_images
                try:
                    await send_card_images(bot, None, cards, user_id=uid, as_media_group=True)
                except Exception:
                    logging.warning('Card images not delivered; text result remains available')
            text = f"{'Уточнение' if payload['kind'] == 'followup' else 'Ваш расклад'}\n\n{payload['question']}\n\n{answer}"
            for chunk in chat_message_chunks(text, [position for positions in THEMES.values() for position in positions]):
                await bot.send_message(chunk, user_id=uid, keyboard=make_back_to_menu_kb(), format='html')
        except Exception:
            logging.warning('Reading saved; MAX delivery unavailable', exc_info=True)


async def worker():
    while True:
        try:
            rows = await Database.fetch_all(f"SELECT id FROM {table('webapp_operations')} WHERE status='queued' ORDER BY created_at LIMIT 2")
            if rows:
                await asyncio.gather(*(perform(row['id']) for row in rows))
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception('Operation worker unavailable; retrying')
            await asyncio.sleep(3)
        await asyncio.sleep(0.4)


async def reading(user_id, reading_id):
    row = await Database.fetch_one(f'''SELECT d.*,COALESCE(a.favorite,false) favorite,COALESCE(a.note,'') note
        FROM {table('divinations')} d LEFT JOIN {table('webapp_annotations')} a ON a.reading_id=d.id
        WHERE d.user_id=$1 AND d.id=$2''', user_id, int(reading_id))
    if not row:
        raise ServiceError('Расклад не найден.', 404)
    result = dict(row)
    result['selected_cards'] = decode(result['selected_cards'], [])
    result['interpretation'] = plain(result['interpretation'])
    result['followups'] = [dict(r) for r in await Database.fetch_all(f"SELECT question,answer,created_at FROM {table('webapp_followups')} WHERE reading_id=$1 ORDER BY id", result['id'])]
    result['remaining'] = max(0, (2 if result['is_free'] else 5) - len(result['followups']))
    result['positions'] = THEMES.get(result['webapp_theme'], THEMES['timeline'])
    return result


async def daily(user_id, choice=None, card_id=None):
    from handlers.tarot_cards import TAROT_CARDS
    day = datetime.now(ZoneInfo('Europe/Moscow')).date()
    pool = await Database.get_pool()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(f"INSERT INTO {table('webapp_daily')}(user_id,day,choices) VALUES($1,$2,$3) ON CONFLICT DO NOTHING", user_id, day, json.dumps(random.sample(list(TAROT_CARDS), 3)))
        row = await conn.fetchrow(f"SELECT * FROM {table('webapp_daily')} WHERE user_id=$1 AND day=$2 FOR UPDATE", user_id, day)
        selected = row['selected']
        if not selected and (choice is not None or card_id is not None):
            if card_id is not None:
                if card_id not in TAROT_CARDS:
                    raise ServiceError('Неизвестная карта.')
                selected = card_id
            else:
                if type(choice) is not int or not 0 <= choice < 3:
                    raise ServiceError('Выберите одну из трёх карт.')
                selected = decode(row['choices'])[choice]
            await conn.execute(f"UPDATE {table('webapp_daily')} SET selected=$3 WHERE user_id=$1 AND day=$2", user_id, day, selected)
        return {'day': str(day), 'card_id': selected, 'card': TAROT_CARDS.get(selected) if selected else None}
