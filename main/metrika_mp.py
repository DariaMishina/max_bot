"""
Yandex Metrica Measurement Protocol — отправка событий напрямую из бота.

Используется для кампании "Директ -> бот" (без лендинга).
Счётчик: METRIKA_MP_COUNTER_ID (настраивается в .env).

Для кампании с лендингом конверсии прошиваются через JS на сайте —
этот модуль туда НЕ отправляет.

Документация MP: https://yandex.ru/dev/metrika/ru/data-import/measurement-upload
"""
import asyncio
import logging
import time
import random
from typing import Optional
from urllib.parse import quote, urlencode

import aiohttp
import asyncpg

from main.config_reader import config
from main.database import Database, get_table_name

logger = logging.getLogger(__name__)

# Таймаут на запрос к Метрике (секунды)
_REQUEST_TIMEOUT = 5

# URL для сбора данных Measurement Protocol
_COLLECT_URL = "https://mc.yandex.ru/collect/"


def generate_metrika_client_id() -> str:
    """
    Генерирует ClientID для Яндекс Метрики Measurement Protocol.
    Формат: {unix_timestamp_ms}{random_6_digits} — числовая строка.
    """
    ts = int(time.time() * 1000)
    rnd = random.randint(100000, 999999)
    return f"{ts}{rnd}"


async def _send_hit(params: dict) -> bool:
    """
    Отправляет хит в Яндекс Метрику через Measurement Protocol.
    
    Returns:
        True если запрос успешен, False при ошибке.
    """
    counter_id = config.metrika_mp_counter_id
    if not counter_id:
        logger.debug("METRIKA_MP_COUNTER_ID not set, skipping MP hit")
        return False

    token = config.metrika_mp_token
    if not token:
        logger.warning("METRIKA_MP_TOKEN not set, skipping MP hit")
        return False

    params["tid"] = str(counter_id)
    params["ms"] = token

    url = _COLLECT_URL + "?" + urlencode(params)

    try:
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    logger.info(f"MP hit sent: t={params.get('t')}, cid={params.get('cid')}")
                    return True
                else:
                    body = await resp.text()
                    logger.warning(
                        f"MP hit unexpected status {resp.status}: {body[:200]}"
                    )
                    return False
    except asyncio.TimeoutError:
        logger.warning("MP hit timeout")
        return False
    except Exception as e:
        logger.error(f"MP hit error: {e}", exc_info=True)
        return False


async def send_pageview(metrika_client_id: str, yclid: str) -> bool:
    """
    Отправляет событие pageview — создаёт «визит» в Метрике и привязывает yclid.

    Вызывается один раз при первом /start директ-пользователя.
    
    Args:
        metrika_client_id: Сгенерированный нами ClientID.
        yclid: Yclid из макроса Яндекс Директа.
    """
    # URL страницы бота с yclid — именно по нему Метрика свяжет визит с кликом в Директе
    # TODO: обновить URL на актуальный для Max бота
    page_url = f"https://max.ru/gadanie_ai_bot?yclid={yclid}"

    params = {
        "cid": metrika_client_id,
        "t": "pageview",
        "dr": "https://yandex.ru",          # реферер
        "dl": page_url,                      # URL «страницы»
        "dt": "gadanie_ai_bot",              # заголовок
        "et": str(int(time.time())),          # время события
    }

    return await _send_hit(params)


async def send_event(metrika_client_id: str, goal_identifier: str) -> bool:
    """
    Отправляет событие достижения цели в Метрику.

    Args:
        metrika_client_id: Сгенерированный нами ClientID.
        goal_identifier: Идентификатор цели (должен совпадать с настроенной в Метрике).
                         Например: 'registration', 'purchase', 'paywall_reached', 'service_usage'.
    """
    params = {
        "cid": metrika_client_id,
        "t": "event",
        "dl": "https://max.ru/gadanie_ai_bot",
        "ea": goal_identifier,                # идентификатор цели
        "et": str(int(time.time())),
    }

    return await _send_hit(params)


async def send_conversion_event(user_id: int, goal_identifier: str) -> bool:
    """
    Хелпер: проверяет, является ли пользователь директ-пользователем,
    и если да — отправляет событие цели через MP.

    Для лендинг-пользователей (есть client_id, нет metrika_client_id) — ничего не делает,
    их конверсии прошиваются через JS на лендинге.

    Для органических пользователей — тоже ничего не делает.

    Вызывается из хендлеров рядом с save_conversion() — fire-and-forget.
    
    Args:
        user_id: Telegram User ID.
        goal_identifier: Идентификатор цели ('registration', 'purchase', и т.д.).
    """
    try:
        metrika_client_id = await get_user_metrika_client_id(user_id)
        if not metrika_client_id:
            return False

        return await send_event(metrika_client_id, goal_identifier)
    except Exception as e:
        logger.error(f"send_conversion_event error for user {user_id}: {e}", exc_info=True)
        return False


async def get_user_metrika_client_id(user_id: int) -> Optional[str]:
    """
    Получает metrika_client_id пользователя из БД.
    Возвращает None если пользователь не из директ-кампании.
    Если колонки metrika_client_id ещё нет (миграция не применена) — возвращаем None без ошибки,
    как в tg_bot (там колонку добавляют миграцией, см. CONVERSIONS.md).
    """
    try:
        users_table = get_table_name("users")
        query = f"SELECT metrika_client_id FROM {users_table} WHERE user_id = $1"
        result = await Database.fetch_one(query, user_id)
        if result and result['metrika_client_id']:
            return result['metrika_client_id']
        return None
    except asyncpg.exceptions.UndefinedColumnError:
        logger.debug(
            "Column metrika_client_id missing in %s (run migration for MP).",
            get_table_name("users"),
        )
        return None
    except Exception as e:
        logger.error(f"Error getting metrika_client_id for user {user_id}: {e}", exc_info=True)
        return None
