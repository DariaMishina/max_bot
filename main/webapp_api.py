"""Authenticated, same-origin WebApp API hosted by the existing bot server."""
import asyncio
from datetime import datetime, timezone
from contextlib import suppress
import json
import os
from pathlib import Path
import re
import uuid
from aiohttp import web

from main import webapp_service as service
from main.config_reader import config
from main.database import Database, get_table_name as table
from main.webapp_auth import validate_init_data

ROOT = Path(__file__).resolve().parents[1]
PAYMENT_SLOTS = asyncio.Semaphore(2)


def response(data, status=200):
    return web.json_response(data, status=status, dumps=lambda value: json.dumps(value, ensure_ascii=False, default=str), headers={'Cache-Control': 'no-store'})


LEGACY_WEBAPP_ROUTES = {
    ('GET', '/api/webapp/pending-question'),
    ('POST', '/api/webapp/cards'),
    ('OPTIONS', '/api/webapp/pending-question'),
    ('OPTIONS', '/api/webapp/cards'),
}


@web.middleware
async def security(request, handler):
    if not request.path.startswith('/api/webapp/'):
        return await handler(request)
    if (request.method, request.path) in LEGACY_WEBAPP_ROUTES:
        return await handler(request)
    try:
        if request.method not in ('GET', 'HEAD') and request.headers.get('Origin'):
            origin = request.headers['Origin'].rstrip('/')
            proto = (request.headers.get('X-Forwarded-Proto') or request.scheme or 'http').split(',')[0].strip()
            host = (request.headers.get('X-Forwarded-Host') or request.host or '').split(',')[0].strip()
            allowed = {f'{proto}://{host}'.rstrip('/'), 'http://127.0.0.1:8091', 'http://localhost:8091'}
            if config.service_url:
                allowed.add(config.service_url.rstrip('/'))
            if origin not in allowed:
                raise service.ServiceError('Недопустимый источник запроса.', 403)
        if os.getenv('WEBAPP_DEMO') == 'true':
            # Explicit local preview only. Never expose demo through a tunnel.
            if request.remote not in ('127.0.0.1', '::1') or request.headers.get('X-Forwarded-For') or request.headers.get('CF-Connecting-IP'):
                raise service.ServiceError('Демонстрация доступна только локально.', 403)
            user = {'id': 900000001, 'first_name': 'Гость'}
        else:
            try:
                user = validate_init_data(request.headers.get('X-Max-Init-Data', ''), config.effective_bot_token.get_secret_value())
            except (ValueError, TypeError, KeyError):
                raise service.ServiceError('Откройте приложение заново через MAX.', 401)
            if os.getenv('WEBAPP_LOCAL') == 'true':
                ids = {int(x.strip()) for x in os.getenv('WEBAPP_ALLOWED_IDS', '').split(',') if x.strip()}
                if user['id'] not in ids:
                    raise service.ServiceError('Этот тест доступен только участникам проверки.', 403)
        request['user'] = user
        await service.ensure_user(user)
        return await handler(request)
    except (service.ServiceError, ValueError, TypeError) as error:
        return response({'error': str(error)}, getattr(error, 'status', 400))
    except web.HTTPException:
        raise
    except Exception:
        import logging
        logging.exception('WebApp API error')
        return response({'error': 'Не удалось выполнить запрос. Попробуйте ещё раз.'}, 500)


def uid(request):
    return request['user']['id']


async def body(request):
    try:
        data = await request.json()
    except Exception:
        raise service.ServiceError('Неверный JSON.')
    if not isinstance(data, dict):
        raise service.ServiceError('Ожидается объект JSON.')
    return data


async def catalog(request):
    from handlers.tarot_cards import TAROT_CARDS
    from handlers.hexagrams import HEXAGRAMS, get_hexagram_image_path
    from handlers.pay import PACKAGES
    hexagrams = {}
    for key, value in HEXAGRAMS.items():
        image = get_hexagram_image_path(key)
        hexagrams[key] = {**value, 'image': f"/static/geks/{Path(image).name}" if image else None}
    return response({'cards': TAROT_CARDS, 'hexagrams': hexagrams,
        'themes': service.THEMES, 'packages': list(PACKAGES.values()), 'demo': os.getenv('WEBAPP_DEMO') == 'true',
        'payments_enabled': bool(_shop_secret()),
        'consultation': {'name': config.tarologist_name, 'hours': config.tarologist_work_hours}})


async def me(request):
    from main.database import get_user_balance, get_pending_question
    balance = await get_user_balance(uid(request))
    user = await Database.fetch_one(f"SELECT daily_card_subscribed FROM {table('users')} WHERE user_id=$1", uid(request))
    active = await Database.fetch_one(f"SELECT id FROM {table('webapp_operations')} WHERE user_id=$1 AND status='queued' ORDER BY created_at DESC LIMIT 1", uid(request))
    last = await Database.fetch_one(f"SELECT id,question FROM {table('divinations')} WHERE user_id=$1 ORDER BY id DESC LIMIT 1", uid(request))
    pending = await Database.fetch_one(f"SELECT question,created_at FROM {table('pending_questions')} WHERE user_id=$1", uid(request))
    return response({'user': request['user'], 'balance': balance, 'access': service.access(balance),
        'daily_subscribed': bool(user['daily_card_subscribed']), 'pending_question': await get_pending_question(uid(request)),
        'chat_selection': {'question': pending['question'], 'version': pending['created_at'].isoformat()} if pending else None,
        'active_operation': active['id'] if active else None, 'last_reading': dict(last) if last else None})


async def pending(request):
    from main.database import get_pending_question
    return response({'question': await get_pending_question(uid(request))})


async def create(request):
    data = await body(request)
    if os.getenv('WEBAPP_DEMO') != 'true':
        from handlers.common import check_channel_subscription
        if not await check_channel_subscription(uid(request)):
            raise service.ServiceError('Подпишитесь на канал через меню бота.', 403)
    return response(await service.submit(uid(request), data.get('request_id'), data), 202)


async def status(request):
    return response(await service.operation(uid(request), request.match_info['id']))


async def chat_card_reading(request):
    data = await body(request)
    if os.getenv('WEBAPP_DEMO') != 'true':
        from handlers.common import check_channel_subscription
        if not await check_channel_subscription(uid(request)):
            raise service.ServiceError('Подпишитесь на канал через меню бота.', 403)
    data = {**data, 'kind': 'tarot', 'mode': 'manual', 'theme': 'timeline'}
    return response(await service.submit(uid(request), data.get('request_id'), data, source='chat-picker'), 202)


async def detail(request):
    return response(await service.reading(uid(request), request.match_info['id']))


async def history(request):
    before = int(request.query.get('before', '2147483647'))
    query = request.query.get('q', '')[:200]
    kind = request.query.get('kind', '')
    favorite = request.query.get('favorite') == 'true'
    rows = await Database.fetch_all(f'''SELECT d.id,d.question,d.divination_type,d.selected_cards,d.created_at,LEFT(d.interpretation,600) AS preview,
        COALESCE(a.favorite,false) favorite FROM {table('divinations')} d
        LEFT JOIN {table('webapp_annotations')} a ON a.reading_id=d.id
        WHERE d.user_id=$1 AND d.id<$2 AND ($3='' OR d.question ILIKE '%' || $3 || '%')
        AND ($4='' OR d.divination_type=$4) AND (NOT $5 OR a.favorite=true)
        ORDER BY d.id DESC LIMIT 21''', uid(request), before, query, kind, favorite)
    items = [dict(r) for r in rows[:20]]
    for item in items:
        item['selected_cards'] = service.decode(item['selected_cards'], [])
        item['preview'] = service.plain(item['preview'])[:220]
    return response({'items': items, 'next': items[-1]['id'] if len(rows) > 20 else None})


async def annotate(request):
    reading = await service.reading(uid(request), request.match_info['id'])
    data = await body(request)
    if type(data.get('favorite')) is not bool or not isinstance(data.get('note'), str) or len(data['note']) > 4000:
        raise service.ServiceError('Заметка — до 4000 символов.')
    await Database.execute_query(f'''INSERT INTO {table('webapp_annotations')}(reading_id,favorite,note)
        VALUES($1,$2,$3) ON CONFLICT(reading_id) DO UPDATE SET favorite=$2,note=$3''', reading['id'], data['favorite'], data['note'])
    return response({'ok': True})


async def daily(request):
    choice = (await body(request)).get('choice') if request.method == 'POST' else None
    return response(await service.daily(uid(request), choice))


async def settings(request):
    data = await body(request)
    if type(data.get('daily_subscribed')) is not bool:
        raise service.ServiceError('Неверная настройка.')
    await Database.execute_query(f"UPDATE {table('users')} SET daily_card_subscribed=$2 WHERE user_id=$1", uid(request), data['daily_subscribed'])
    return response({'ok': True, 'background_delivery_enabled': os.getenv('ENABLE_BACKGROUND_JOBS') == 'true'})


async def feedback(request):
    data = await body(request)
    text = data.get('text')
    if not isinstance(text, str) or not 3 <= len(text.strip()) <= 2000:
        raise service.ServiceError('Напишите от 3 до 2000 символов.')
    await Database.execute_query(f"INSERT INTO {table('webapp_feedback')}(user_id,text) VALUES($1,$2)", uid(request), text.strip())
    return response({'ok': True})


async def event(request):
    name = (await body(request)).get('event')
    if name not in ('open','question','mode','start','result','followup','history','purchase'):
        raise service.ServiceError('Неизвестное событие.')
    await Database.execute_query(f"INSERT INTO {table('webapp_events')}(user_id,event) VALUES($1,$2)", uid(request), name)
    return response({'ok': True})


def _shop_secret():
    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        return ''
    shop = config.yookassa_shop_id.get_secret_value().strip()
    secret = config.yookassa_secret_key.get_secret_value().strip()
    return secret if shop and secret else ''


async def purchase(request):
    from handlers.pay import PACKAGES_BY_ID, create_yookassa_payment
    from main.database import create_payment
    if not _shop_secret():
        raise service.ServiceError('Оплата пока не подключена.', 503)
    data = await body(request)
    request_id = uuid.UUID(str(data.get('request_id')))
    package = PACKAGES_BY_ID.get(data.get('package'))
    email = data.get('email', '')
    if not package or not isinstance(email, str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
        raise service.ServiceError('Выберите пакет и укажите email для чека.')
    pool = await Database.get_pool()
    # Persist the provider idempotency key before the network call.
    await Database.execute_query(f"INSERT INTO {table('webapp_purchases')}(id,user_id,package,email) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING", request_id, uid(request), package['id'], email)
    async with PAYMENT_SLOTS, pool.acquire() as conn, conn.transaction():
        saved = await conn.fetchrow(f"SELECT * FROM {table('webapp_purchases')} WHERE id=$1 FOR UPDATE", request_id)
        if saved['user_id'] != uid(request) or saved['package'] != package['id'] or saved['email'] != email:
            raise service.ServiceError('Запрос покупки уже использован.', 409)
        if saved['payment_id']:
            return response(dict(saved))
        if (datetime.now(timezone.utc) - saved['created_at']).total_seconds() > 23 * 3600:
            raise service.ServiceError('Срок повторного создания платежа истёк. Обратитесь к администратору теста для сверки.', 409)
        result = await create_yookassa_payment(package['amount_rub'], package['name'], email, uid(request), package['id'], idempotence_key=str(request_id))
        url = result['confirmation']['confirmation_url']
        if not url.startswith('https://'):
            raise service.ServiceError('Некорректная ссылка оплаты.', 502)
        if not await create_payment(result['id'], uid(request), package['id'], package['amount'], package['amount_rub'], email):
            raise service.ServiceError('Не удалось сохранить платёж. Повторите запрос.', 503)
        await conn.execute(f"UPDATE {table('webapp_purchases')} SET payment_id=$2,confirmation_url=$3 WHERE id=$1", request_id, result['id'], url)
        return response({'payment_id': result['id'], 'confirmation_url': url})


async def payment_status(request):
    from handlers.pay import check_payment_status
    from main.database import process_successful_payment
    row = await Database.fetch_one(f"SELECT * FROM {table('payments')} WHERE payment_id=$1 AND user_id=$2", request.match_info['id'], uid(request))
    if not row:
        raise service.ServiceError('Платёж не найден.', 404)
    data = await check_payment_status(row['payment_id'])
    from decimal import Decimal
    if data.get('id') != row['payment_id'] or data.get('metadata', {}).get('user_id') != str(uid(request)) or data.get('metadata', {}).get('package_id') != row['package_id'] or Decimal(data['amount']['value']) != row['amount_rub'] or data['amount'].get('currency') != 'RUB':
        raise service.ServiceError('Данные платежа не совпадают.', 502)
    if data['status'] == 'succeeded':
        if not await process_successful_payment(row['payment_id']):
            raise service.ServiceError('Платёж подтверждён, повторите проверку начисления.', 503)
    return response({'status': data['status'], 'contact': config.tarologist_profile_url if data['status'] == 'succeeded' and row['package_id'].startswith('consult_') else None})


async def index(request):
    return web.FileResponse(ROOT / 'webapp/index.html', headers={'Cache-Control': 'no-cache'})


async def lifecycle(app):
    await service.initialize()
    task = asyncio.create_task(service.worker())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def install(app, *, include_index=False):
    app.middlewares.append(security)
    app.cleanup_ctx.append(lifecycle)
    routes = [web.get('/api/webapp/catalog', catalog), web.get('/api/webapp/me', me),
        web.post('/api/webapp/readings', create),
        web.get('/api/webapp/operations/{id}', status), web.get('/api/webapp/history', history),
        web.get('/api/webapp/readings/{id}', detail), web.post('/api/webapp/readings/{id}/annotation', annotate),
        web.post('/api/webapp/chat-card-readings', chat_card_reading),
        web.get('/api/webapp/daily', daily), web.post('/api/webapp/daily', daily),
        web.post('/api/webapp/settings', settings), web.post('/api/webapp/feedback', feedback),
        web.post('/api/webapp/events', event), web.post('/api/webapp/payments', purchase),
        web.get('/api/webapp/payments/{id}', payment_status)]
    if include_index:
        routes.append(web.get('/', index))
    app.add_routes(routes)
    app.router.add_static('/assets/', ROOT / 'webapp', show_index=False)
    app.router.add_static('/static/', ROOT / 'static', show_index=False)
