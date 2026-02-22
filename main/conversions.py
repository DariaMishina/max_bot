"""
Модуль для работы с конверсиями.

Сохраняет все события воронки в таблицу `conversions` для внутренней аналитики.
Для отправки конверсий в Яндекс Метрику используется Measurement Protocol (main/metrika_mp.py).

Два потока трекинга:
  1. Лендинг → бот: конверсии на лендинге прошиваются через JS (счётчик 106573786).
     В БД сохраняется client_id из Метрики лендинга для аналитики.
  2. Директ → бот: конверсии прошиваются через Measurement Protocol (счётчик 106708199).
     В БД сохраняется yclid + metrika_client_id. Модуль metrika_mp.py отправляет события.

CSV-экспорт (функции generate_csv_*) — legacy, не используется.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
from main.database import Database, get_table_name


async def save_paywall_conversion(
    user_id: int,
    paywall_source: str,
    client_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """
    Сохранить конверсию просмотра пейволла (paywall_reached)
    
    Args:
        user_id: Telegram User ID
        paywall_source: Источник показа пейволла:
            - 'command_pay': пользователь нажал /pay
            - 'text_pay': пользователь нажал "Купить расклады" или "Оплата"
            - 'divination_blocked': попытка гадать, когда закончились бесплатные гадания
            - 'callback_remind_pay': нажал кнопку "Оплатить" в напоминании
            - 'no_divinations_reminder': получил напоминание о закончившихся гаданиях
            - 'balance_view': просмотр баланса, когда нет гаданий
        client_id: ClientID из Яндекс Метрики (может быть None)
        metadata: Дополнительные данные (например, divination_type, balance_info и т.д.)
    
    Returns:
        ID сохраненной конверсии или None при ошибке
    """
    return await save_conversion(
        user_id=user_id,
        conversion_type='paywall_reached',
        client_id=client_id,
        metadata={
            'paywall_source': paywall_source,
            **(metadata or {})
        }
    )


async def save_conversion(
    user_id: int,
    conversion_type: str,
    client_id: Optional[str] = None,
    conversion_value: Optional[float] = None,
    conversion_currency: str = 'RUB',
    package_id: Optional[str] = None,
    divination_type: Optional[str] = None,
    source: Optional[str] = None,
    campaign_id: Optional[str] = None,
    ad_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    conversion_datetime: Optional[datetime] = None
) -> Optional[int]:
    """
    Сохранить конверсию в БД
    
    Args:
        user_id: Telegram User ID
        conversion_type: Тип конверсии ('registration', 'purchase', 'service_usage', 'paywall_reached')
        client_id: ClientID из Яндекс Метрики (может быть None)
        conversion_value: Стоимость конверсии (для покупок)
        conversion_currency: Валюта (по умолчанию 'RUB')
        package_id: ID пакета (для покупок: '3_spreads', '10_spreads', '20_spreads', '30_spreads', 'unlimited')
        divination_type: Тип гадания (для service_usage: 'Таро' или 'Ицзин')
        source: Источник (например, 'yandex_direct', 'organic')
        campaign_id: ID кампании
        ad_id: ID объявления
        metadata: Дополнительные данные в формате JSON
        conversion_datetime: Дата и время конверсии (если None, используется текущее время)
    
    Returns:
        ID сохраненной конверсии или None при ошибке
    """
    try:
        if conversion_datetime is None:
            conversion_datetime = datetime.now()
        
        # Если client_id не передан, пытаемся получить из таблицы users
        if client_id is None:
            users_table = get_table_name("users")
            user_query = f"""
                SELECT client_id FROM {users_table} WHERE user_id = $1
            """
            user_result = await Database.fetch_one(user_query, user_id)
            if user_result and user_result['client_id']:
                client_id = user_result['client_id']
        
        conversions_table = get_table_name("conversions")
        query = f"""
            INSERT INTO {conversions_table} (
                user_id, client_id, conversion_type, conversion_value, conversion_currency,
                package_id, divination_type, conversion_datetime, source, campaign_id, ad_id,
                metadata, exported_to_yandex, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, FALSE, NOW())
            RETURNING id
        """
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        result = await Database.fetch_one(
            query,
            user_id,
            client_id,
            conversion_type,
            conversion_value,
            conversion_currency,
            package_id,
            divination_type,
            conversion_datetime,
            source,
            campaign_id,
            ad_id,
            metadata_json
        )
        
        if result:
            conversion_id = result['id']
            logging.info(
                f"Conversion saved: id={conversion_id}, user={user_id}, "
                f"type={conversion_type}, client_id={client_id}"
            )
            return conversion_id
        return None
    except Exception as e:
        logging.error(f"Error saving conversion for user {user_id}: {e}", exc_info=True)
        return None


async def get_unexported_conversions(limit: int = 1000, only_with_client_id: bool = False) -> List[Dict[str, Any]]:
    """
    [LEGACY] Получить неэкспортированные конверсии для CSV-выгрузки.
    Не используется — конверсии теперь отправляются через Measurement Protocol (metrika_mp.py).
    
    Args:
        limit: Максимальное количество записей
        only_with_client_id: Если True, возвращает только конверсии с ClientID (для Яндекс Директ)
                           Если False, возвращает все конверсии (для внутренней аналитики)
    
    Returns:
        Список конверсий
    """
    try:
        # Фильтруем только конверсии с ClientID для экспорта в Яндекс Директ
        # (без ClientID конверсии не могут быть сопоставлены с визитами)
        client_id_filter = "AND client_id IS NOT NULL" if only_with_client_id else ""
        conversions_table = get_table_name("conversions")
        
        query = f"""
            SELECT 
                id, user_id, client_id, conversion_type, conversion_value, conversion_currency,
                package_id, divination_type, conversion_datetime, source, campaign_id, ad_id,
                metadata, created_at
            FROM {conversions_table}
            WHERE exported_to_yandex = FALSE
            {client_id_filter}
            ORDER BY conversion_datetime ASC
            LIMIT $1
        """
        
        results = await Database.fetch_all(query, limit)
        return [
            {
                'id': r['id'],
                'user_id': r['user_id'],
                'client_id': r['client_id'],
                'conversion_type': r['conversion_type'],
                'conversion_value': float(r['conversion_value']) if r['conversion_value'] else None,
                'conversion_currency': r['conversion_currency'],
                'package_id': r['package_id'],
                'divination_type': r['divination_type'],
                'conversion_datetime': r['conversion_datetime'],
                'source': r['source'],
                'campaign_id': r['campaign_id'],
                'ad_id': r['ad_id'],
                'metadata': json.loads(r['metadata']) if r['metadata'] else None,
                'created_at': r['created_at']
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Error getting unexported conversions: {e}", exc_info=True)
        return []


async def mark_conversions_as_exported(conversion_ids: List[int]) -> bool:
    """
    [LEGACY] Пометить конверсии как экспортированные.
    Не используется — конверсии теперь отправляются через Measurement Protocol (metrika_mp.py).
    
    Args:
        conversion_ids: Список ID конверсий
    
    Returns:
        True если успешно, False при ошибке
    """
    try:
        if not conversion_ids:
            return True
        
        conversions_table = get_table_name("conversions")
        query = f"""
            UPDATE {conversions_table}
            SET exported_to_yandex = TRUE,
                exported_at = NOW()
            WHERE id = ANY($1::int[])
        """
        
        await Database.execute_query(query, conversion_ids)
        logging.info(f"Marked {len(conversion_ids)} conversions as exported")
        return True
    except Exception as e:
        logging.error(f"Error marking conversions as exported: {e}", exc_info=True)
        return False


async def get_conversion_statistics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Получить статистику по конверсиям
    
    Args:
        start_date: Начальная дата (если None, без ограничения)
        end_date: Конечная дата (если None, без ограничения)
    
    Returns:
        Словарь со статистикой
    """
    try:
        conditions = []
        params = []
        param_num = 1
        
        if start_date:
            conditions.append(f"conversion_datetime >= ${param_num}")
            params.append(start_date)
            param_num += 1
        
        if end_date:
            conditions.append(f"conversion_datetime <= ${param_num}")
            params.append(end_date)
            param_num += 1
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        conversions_table = get_table_name("conversions")
        
        query = f"""
            SELECT 
                conversion_type,
                COUNT(*) as count,
                SUM(conversion_value) as total_value,
                COUNT(CASE WHEN exported_to_yandex = TRUE THEN 1 END) as exported_count,
                COUNT(CASE WHEN exported_to_yandex = FALSE THEN 1 END) as unexported_count
            FROM {conversions_table}
            {where_clause}
            GROUP BY conversion_type
        """
        
        results = await Database.fetch_all(query, *params)
        
        stats = {
            'by_type': {},
            'total': 0,
            'exported': 0,
            'unexported': 0,
            'total_value': 0.0
        }
        
        for r in results:
            stats['by_type'][r['conversion_type']] = {
                'count': r['count'],
                'total_value': float(r['total_value']) if r['total_value'] else 0.0,
                'exported': r['exported_count'],
                'unexported': r['unexported_count']
            }
            stats['total'] += r['count']
            stats['exported'] += r['exported_count']
            stats['unexported'] += r['unexported_count']
            if r['total_value']:
                stats['total_value'] += float(r['total_value'])
        
        return stats
    except Exception as e:
        logging.error(f"Error getting conversion statistics: {e}", exc_info=True)
        return {
            'by_type': {},
            'total': 0,
            'exported': 0,
            'unexported': 0,
            'total_value': 0.0
        }


def generate_csv_for_yandex(conversions: List[Dict[str, Any]]) -> str:
    """
    [LEGACY] Генерирует CSV для Яндекс Директ.
    Не используется — конверсии теперь отправляются через Measurement Protocol (metrika_mp.py).
    """
    import hashlib
    from io import StringIO
    
    output = StringIO()
    
    # Заголовки согласно документации Яндекс Директ
    # Формируем вручную для точного контроля формата
    # COMMENT колонка опциональна, но должна быть в заголовке
    header = 'create_date_time;id;client_uniq_id;client_ids;emails;phones;emails_md5;phones_md5;order_status;revenue;cost;"COMMENT - эта колонка будет проигнорирована, можно удалить"'
    output.write(header + '\n')
    
    for conv in conversions:
        # Форматируем дату и время: DD.MM.YYYY HH:MM:SS
        conv_datetime = conv.get('conversion_datetime')
        if isinstance(conv_datetime, datetime):
            datetime_str = conv_datetime.strftime('%d.%m.%Y %H:%M:%S')
        else:
            datetime_str = str(conv_datetime)
        
        # ID заказа - используем payment_id из metadata или ID конверсии
        order_id = ''
        metadata = conv.get('metadata', {}) or {}
        if isinstance(metadata, dict):
            payment_id = metadata.get('payment_id')
            if payment_id:
                order_id = str(payment_id)
        if not order_id:
            order_id = str(conv.get('id', ''))
        
        # client_uniq_id - используем user_id из Telegram как уникальный идентификатор
        client_uniq_id = str(conv.get('user_id', ''))
        
        # client_ids - ClientID из Яндекс Метрики (может быть пустым)
        client_ids = conv.get('client_id') or ''
        
        # Email и телефон из metadata (если есть)
        email = ''
        phone = ''
        email_md5 = ''
        phone_md5 = ''
        
        if isinstance(metadata, dict):
            email = metadata.get('email', '')
            phone = metadata.get('phone', '')
            
            # Генерируем MD5 хеши если есть данные
            if email:
                email_md5 = hashlib.md5(email.lower().strip().encode()).hexdigest()
            if phone:
                # Нормализуем телефон (только цифры)
                phone_normalized = ''.join(filter(str.isdigit, phone))
                phone_md5 = hashlib.md5(phone_normalized.encode()).hexdigest()
        
        # Статус заказа - используем идентификатор цели из Яндекс Метрики
        # Цель "paid_from_tg" создана в Метрике для отслеживания покупок из Telegram бота
        order_status = 'paid_from_tg' if conv.get('conversion_type') == 'purchase' else ''
        
        # Доход (revenue)
        revenue = ''
        if conv.get('conversion_value'):
            revenue = str(conv.get('conversion_value'))
        
        # Себестоимость (cost) - пока не используем
        cost = ''
        
        # Формируем строку вручную для точного контроля формата
        # Кавычки нужны только если значение содержит точку с запятой, кавычки или запятые
        def escape_value(val):
            if not val:
                return ''
            # Если содержит разделитель, кавычки или запятые - оборачиваем в кавычки
            if ';' in val or '"' in val or ',' in val:
                return '"' + val.replace('"', '""') + '"'
            return val
        
        row = ';'.join([
            escape_value(datetime_str),
            escape_value(order_id),
            escape_value(client_uniq_id),
            escape_value(client_ids),
            escape_value(email),
            escape_value(phone),
            escape_value(email_md5),
            escape_value(phone_md5),
            escape_value(order_status),
            escape_value(revenue),
            escape_value(cost),
            ''  # Пустая колонка COMMENT (опциональна, но разделитель обязателен)
        ])
        
        output.write(row + '\n')
    
    return output.getvalue()


def generate_csv_for_yandex_metrika(conversions: List[Dict[str, Any]], include_paywall: bool = False) -> str:
    """
    [LEGACY] Генерирует CSV для Яндекс Метрики (офлайн конверсии).
    Не используется — конверсии теперь отправляются через Measurement Protocol (metrika_mp.py).
    """
    from io import StringIO
    
    output = StringIO()
    
    # Заголовки согласно образцу Яндекс Метрики
    # Разделитель - запятая
    header = 'ClientId,Target,DateTime,Price,Currency'
    output.write(header + '\n')
    
    for conv in conversions:
        # ClientId из Яндекс Метрики (обязателен для офлайн конверсий)
        client_id = conv.get('client_id') or ''
        
        # Пропускаем конверсии без ClientID (они не могут быть сопоставлены с визитами)
        if not client_id:
            continue
        
        # Target - идентификатор цели из Яндекс Метрики
        # Все конверсии отправляются с единой целью go_to_tg
        conversion_type = conv.get('conversion_type', '')
        
        # Пропускаем paywall_reached если не включен флаг include_paywall
        if conversion_type == 'paywall_reached' and not include_paywall:
            continue
        
        # Все типы конверсий используют единую цель go_to_tg
        target = 'go_to_tg'
        
        # DateTime - Unix Time Stamp в секундах
        conv_datetime = conv.get('conversion_datetime')
        if isinstance(conv_datetime, datetime):
            unix_timestamp = int(conv_datetime.timestamp())
        else:
            # Если это строка, пытаемся преобразовать
            try:
                if isinstance(conv_datetime, str):
                    dt = datetime.fromisoformat(conv_datetime.replace('Z', '+00:00'))
                    unix_timestamp = int(dt.timestamp())
                else:
                    unix_timestamp = int(datetime.now().timestamp())
            except:
                unix_timestamp = int(datetime.now().timestamp())
        
        # Price - доход (необязателен, только для purchase)
        price = ''
        if conv.get('conversion_value'):
            price = str(conv.get('conversion_value'))
        
        # Currency - код валюты ISO 4217 (необязателен)
        currency = conv.get('conversion_currency', 'RUB')
        
        # Формируем строку с разделителем запятая (как в образце)
        row = ','.join([
            client_id,
            target,
            str(unix_timestamp),
            price,
            currency
        ])
        
        output.write(row + '\n')
    
    return output.getvalue()

