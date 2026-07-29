"""
Модуль для работы с базой данных PostgreSQL
"""
import logging
from typing import Optional, Dict, Any, List
import asyncpg
from datetime import datetime, timedelta, timezone
import json

from main.config_reader import config


def get_table_name(base_name: str) -> str:
    """
    Получить имя таблицы с учетом суффикса из конфига
    
    Args:
        base_name: Базовое имя таблицы (например, "users")
    
    Returns:
        Имя таблицы с суффиксом (например, "users" или "users_test")
    """
    suffix = config.db_table_suffix if hasattr(config, 'db_table_suffix') else ""
    return f"max_{base_name}{suffix}"


class Database:
    """Класс для работы с базой данных"""
    
    _pool: Optional[asyncpg.Pool] = None
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Получить пул подключений к БД"""
        if cls._pool is None:
            try:
                # Получаем значения с защитой (SecretStr требует явного вызова get_secret_value)
                db_user = config.db_user.get_secret_value() if hasattr(config.db_user, 'get_secret_value') else config.db_user
                db_password = config.db_password.get_secret_value() if hasattr(config.db_password, 'get_secret_value') else config.db_password
                
                # Логируем параметры подключения (без пароля и пользователя для безопасности)
                logging.info(f"Connecting to database: host={config.db_host}, port={config.db_port}, database={config.db_name}")
                
                cls._pool = await asyncpg.create_pool(
                    host=config.db_host,
                    port=config.db_port,
                    database=config.db_name,
                    user=db_user,
                    password=db_password,
                    min_size=2,
                    max_size=10,
                    command_timeout=60
                )
                logging.info("Database connection pool created successfully")
            except Exception as e:
                logging.error(f"Error creating database pool: {e}", exc_info=True)
                # Не логируем user и password для безопасности
                logging.error(f"Database config: host={config.db_host}, port={config.db_port}, database={config.db_name}")
                logging.error("Please check that DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD are set correctly in environment variables")
                raise
        return cls._pool
    
    @classmethod
    async def close_pool(cls):
        """Закрыть пул подключений"""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logging.info("Database connection pool closed")
    
    @classmethod
    async def execute_query(cls, query: str, *args) -> Any:
        """Выполнить запрос"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    @classmethod
    async def fetch_one(cls, query: str, *args) -> Optional[asyncpg.Record]:
        """Получить одну запись"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    @classmethod
    async def fetch_all(cls, query: str, *args) -> List[asyncpg.Record]:
        """Получить все записи"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    @classmethod
    async def fetchval(cls, query: str, *args) -> Any:
        """Получить одно значение"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)


# ==================== Пользователи ====================

async def create_or_update_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: str = "",
    last_name: Optional[str] = None,
    language_code: Optional[str] = None,
    is_premium: bool = False,
    client_id: Optional[str] = None,
    phone: Optional[str] = None,
    utm_source: Optional[str] = None,
    utm_campaign: Optional[str] = None,
    utm_content: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_term: Optional[str] = None,
    yclid: Optional[str] = None,
    metrika_client_id: Optional[str] = None
) -> bool:
    """
    Создать или обновить пользователя
    Возвращает True, если пользователь был создан (новый), False если обновлен
    """
    try:
        full_name = f"{first_name} {last_name}".strip() if last_name else first_name
        
        users_table = get_table_name("users")
        query = f"""
            INSERT INTO {users_table} (
                user_id, username, first_name, last_name, full_name, language_code, is_premium,
                client_id, phone, utm_source, utm_campaign, utm_content, utm_medium, utm_term,
                yclid, metrika_client_id,
                created_at, last_active_at, first_visit_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW(), NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                full_name = EXCLUDED.full_name,
                language_code = EXCLUDED.language_code,
                is_premium = EXCLUDED.is_premium,
                last_active_at = NOW(),
                -- Обновляем client_id и UTM только если они не NULL (чтобы не перезаписывать существующие)
                client_id = COALESCE(EXCLUDED.client_id, {users_table}.client_id),
                phone = COALESCE(EXCLUDED.phone, {users_table}.phone),
                utm_source = COALESCE(EXCLUDED.utm_source, {users_table}.utm_source),
                utm_campaign = COALESCE(EXCLUDED.utm_campaign, {users_table}.utm_campaign),
                utm_content = COALESCE(EXCLUDED.utm_content, {users_table}.utm_content),
                utm_medium = COALESCE(EXCLUDED.utm_medium, {users_table}.utm_medium),
                utm_term = COALESCE(EXCLUDED.utm_term, {users_table}.utm_term),
                yclid = COALESCE(EXCLUDED.yclid, {users_table}.yclid),
                metrika_client_id = COALESCE(EXCLUDED.metrika_client_id, {users_table}.metrika_client_id)
            RETURNING (xmax = 0) AS is_new
        """
        
        result = await Database.fetch_one(
            query, user_id, username, first_name, last_name, full_name, language_code, is_premium,
            client_id, phone, utm_source, utm_campaign, utm_content, utm_medium, utm_term,
            yclid, metrika_client_id
        )
        is_new = result['is_new'] if result else False
        
        # Если пользователь новый, создаем баланс
        if is_new:
            await create_user_balance(user_id)
            logging.info(f"New user created: {user_id} ({full_name})")
        else:
            logging.info(f"User updated: {user_id} ({full_name})")
        
        return is_new
    except Exception as e:
        logging.error(f"Error creating/updating user {user_id}: {e}", exc_info=True)
        return False


async def create_user_balance(user_id: int) -> bool:
    """Создать баланс для пользователя (3 бесплатных гадания)"""
    try:
        balances_table = get_table_name("user_balances")
        query = f"""
            INSERT INTO {balances_table} (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
            VALUES ($1, 3, 0, NOW())
            ON CONFLICT (user_id) DO NOTHING
        """
        await Database.execute_query(query, user_id)
        return True
    except Exception as e:
        logging.error(f"Error creating balance for user {user_id}: {e}", exc_info=True)
        return False


async def get_user_balance(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить баланс пользователя"""
    try:
        balances_table = get_table_name("user_balances")
        query = f"""
            SELECT 
                free_divinations_remaining,
                paid_divinations_remaining,
                unlimited_until,
                total_divinations_used
            FROM {balances_table}
            WHERE user_id = $1
        """
        result = await Database.fetch_one(query, user_id)
        if result:
            return {
                'free_divinations_remaining': result['free_divinations_remaining'],
                'paid_divinations_remaining': result['paid_divinations_remaining'],
                'unlimited_until': result['unlimited_until'],
                'total_divinations_used': result['total_divinations_used']
            }
        return None
    except Exception as e:
        logging.error(f"Error getting balance for user {user_id}: {e}", exc_info=True)
        return None


async def can_user_divinate(user_id: int) -> tuple[bool, str]:
    """
    Проверить, может ли пользователь гадать
    Возвращает (может_ли_гадать, тип_доступа)
    Типы доступа: 'unlimited', 'free', 'paid', 'no_balance'
    """
    try:
        balance = await get_user_balance(user_id)
        if not balance:
            return False, 'no_balance'
        
        # Проверяем безлимит
        if balance['unlimited_until'] and balance['unlimited_until'] > datetime.now():
            return True, 'unlimited'
        
        # Проверяем бесплатные
        if balance['free_divinations_remaining'] > 0:
            return True, 'free'
        
        # Проверяем платные
        if balance['paid_divinations_remaining'] > 0:
            return True, 'paid'
        
        return False, 'no_balance'
    except Exception as e:
        logging.error(f"Error checking divination access for user {user_id}: {e}", exc_info=True)
        return False, 'no_balance'


async def use_divination(user_id: int) -> bool:
    """
    Использовать одно гадание (уменьшить баланс)
    Сначала тратятся бесплатные, затем платные
    """
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                balances_table = get_table_name("user_balances")
                # Получаем текущий баланс
                balance_query = f"""
                    SELECT free_divinations_remaining, paid_divinations_remaining, unlimited_until
                    FROM {balances_table}
                    WHERE user_id = $1
                    FOR UPDATE
                """
                balance = await conn.fetchrow(balance_query, user_id)
                
                if not balance:
                    logging.warning(f"Balance not found for user {user_id}")
                    return False
                
                # Если есть безлимит и он не истек
                if balance['unlimited_until'] and balance['unlimited_until'] > datetime.now():
                    # Просто увеличиваем счетчик использованных
                    update_query = f"""
                        UPDATE {balances_table}
                        SET total_divinations_used = total_divinations_used + 1,
                            updated_at = NOW()
                        WHERE user_id = $1
                    """
                    await conn.execute(update_query, user_id)
                    logging.info(f"Divination used (unlimited) for user {user_id}")
                    return True
                
                # Если есть бесплатные, тратим их
                if balance['free_divinations_remaining'] > 0:
                    update_query = f"""
                        UPDATE {balances_table}
                        SET free_divinations_remaining = free_divinations_remaining - 1,
                            total_divinations_used = total_divinations_used + 1,
                            updated_at = NOW()
                        WHERE user_id = $1
                    """
                    await conn.execute(update_query, user_id)
                    logging.info(f"Free divination used for user {user_id}")
                    return True
                
                # Если есть платные, тратим их
                if balance['paid_divinations_remaining'] > 0:
                    last_paid = balance['paid_divinations_remaining'] == 1
                    update_query = f"""
                        UPDATE {balances_table}
                        SET paid_divinations_remaining = paid_divinations_remaining - 1,
                            total_divinations_used = total_divinations_used + 1,
                            access_expired_at = CASE
                                WHEN $2 THEN COALESCE(access_expired_at, NOW())
                                ELSE access_expired_at
                            END,
                            updated_at = NOW()
                        WHERE user_id = $1
                    """
                    await conn.execute(update_query, user_id, last_paid)
                    logging.info(f"Paid divination used for user {user_id}")
                    return True
                
                logging.warning(f"No divinations available for user {user_id}")
                return False
    except Exception as e:
        logging.error(f"Error using divination for user {user_id}: {e}", exc_info=True)
        return False


# ==================== Гадания ====================

async def save_divination(
    user_id: int,
    divination_type: str,
    question: str,
    selected_cards: Optional[List[str]] = None,
    interpretation: Optional[str] = None,
    is_free: bool = True
) -> Optional[int]:
    """
    Сохранить гадание в БД
    Возвращает ID сохраненного гадания
    """
    try:
        divinations_table = get_table_name("divinations")
        query = f"""
            INSERT INTO {divinations_table} (user_id, divination_type, question, selected_cards, interpretation, is_free, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id
        """
        
        selected_cards_json = json.dumps(selected_cards) if selected_cards else None
        
        result = await Database.fetch_one(query, user_id, divination_type, question, selected_cards_json, interpretation, is_free)
        if result:
            divination_id = result['id']
            logging.info(f"Divination saved: id={divination_id}, user={user_id}, type={divination_type}")
            return divination_id
        return None
    except Exception as e:
        logging.error(f"Error saving divination for user {user_id}: {e}", exc_info=True)
        return None


async def get_user_divinations(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Получить историю гаданий пользователя"""
    try:
        divinations_table = get_table_name("divinations")
        query = f"""
            SELECT id, divination_type, question, selected_cards, interpretation, is_free, created_at
            FROM {divinations_table}
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        results = await Database.fetch_all(query, user_id, limit)
        return [
            {
                'id': r['id'],
                'divination_type': r['divination_type'],
                'question': r['question'],
                'selected_cards': json.loads(r['selected_cards']) if r['selected_cards'] else None,
                'interpretation': r['interpretation'],
                'is_free': r['is_free'],
                'created_at': r['created_at']
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Error getting divinations for user {user_id}: {e}", exc_info=True)
        return []


async def update_divination_interpretation(divination_id: int, interpretation: str) -> bool:
    """
    Обновить interpretation гадания (добавить историю диалога)
    """
    try:
        divinations_table = get_table_name("divinations")
        query = f"""
            UPDATE {divinations_table}
            SET interpretation = $1
            WHERE id = $2
        """
        await Database.execute_query(query, interpretation, divination_id)
        logging.info(f"Divination {divination_id} interpretation updated")
        return True
    except Exception as e:
        logging.error(f"Error updating divination {divination_id} interpretation: {e}", exc_info=True)
        return False


# ==================== Платежи ====================

async def create_payment(
    payment_id: str,
    user_id: int,
    package_id: str,
    amount: int,
    amount_rub: float,
    email: Optional[str] = None,
    yookassa_metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Создать запись о платеже"""
    try:
        payments_table = get_table_name("payments")
        query = f"""
            INSERT INTO {payments_table} (payment_id, user_id, package_id, amount, amount_rub, status, email, yookassa_metadata, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, 'pending', $6, $7, NOW(), NOW())
            ON CONFLICT (payment_id) DO NOTHING
        """
        
        metadata_json = json.dumps(yookassa_metadata) if yookassa_metadata else None
        
        await Database.execute_query(query, payment_id, user_id, package_id, amount, amount_rub, email, metadata_json)
        logging.info(f"Payment created: {payment_id} for user {user_id}, package {package_id}")
        return True
    except Exception as e:
        logging.error(f"Error creating payment {payment_id}: {e}", exc_info=True)
        return False


async def update_payment_status(
    payment_id: str,
    status: str,
    yookassa_metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Обновить статус платежа"""
    try:
        payments_table = get_table_name("payments")
        query = f"""
            UPDATE {payments_table}
            SET status = $1::VARCHAR(50),
                updated_at = NOW(),
                completed_at = CASE WHEN $1::VARCHAR(50) = 'succeeded' THEN NOW() ELSE completed_at END,
                yookassa_metadata = COALESCE($2::jsonb, yookassa_metadata)
            WHERE payment_id = $3::VARCHAR(255)
        """
        
        metadata_json = json.dumps(yookassa_metadata) if yookassa_metadata else None
        
        await Database.execute_query(query, status, metadata_json, payment_id)
        logging.info(f"Payment status updated: {payment_id} -> {status}")
        return True
    except Exception as e:
        logging.error(f"Error updating payment status {payment_id}: {e}", exc_info=True)
        return False


async def process_successful_payment(payment_id: str, yookassa_metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Обработать успешный платеж (идемпотентно):
    1. Атомарно перевести статус pending → succeeded (если уже succeeded — пропустить)
    2. Обновить баланс пользователя (добавить гадания или создать подписку)
    """
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                payments_table = get_table_name("payments")
                subscriptions_table = get_table_name("subscriptions")
                balances_table = get_table_name("user_balances")

                # Атомарно: обновляем статус и получаем данные платежа ТОЛЬКО если
                # он ещё не был обработан (status != 'succeeded').
                # FOR UPDATE блокирует строку от параллельных транзакций.
                claim_query = f"""
                    UPDATE {payments_table}
                    SET status = 'succeeded',
                        updated_at = NOW(),
                        completed_at = NOW(),
                        yookassa_metadata = COALESCE($2::jsonb, yookassa_metadata)
                    WHERE payment_id = $1 AND status != 'succeeded'
                    RETURNING user_id, package_id, amount, amount_rub
                """
                metadata_json = json.dumps(yookassa_metadata) if yookassa_metadata else None
                payment = await conn.fetchrow(claim_query, payment_id, metadata_json)

                if not payment:
                    existing = await conn.fetchval(
                        f"SELECT status FROM {payments_table} WHERE payment_id = $1",
                        payment_id
                    )
                    if existing == 'succeeded':
                        logging.info(f"Payment {payment_id} already processed, skipping")
                        return True
                    logging.error(f"Payment not found: {payment_id}")
                    return False

                user_id = payment['user_id']
                package_id = payment['package_id']

                logging.info(f"Payment status updated: {payment_id} -> succeeded")

                # Личная консультация с тарологом: баланс не начисляется,
                # услуга оказывается вручную (пользователь пишет тарологу в MAX).
                if package_id in ('consult_basic', 'consult_detailed'):
                    logging.info(
                        f"Consultation payment for user {user_id}: "
                        f"package={package_id}, no balance update"
                    )
                    return True

                if package_id == 'unlimited':
                    expires_at = datetime.now() + timedelta(days=30)

                    subscription_query = f"""
                        INSERT INTO {subscriptions_table} (user_id, payment_id, started_at, expires_at, is_active, created_at)
                        VALUES ($1, $2, NOW(), $3, TRUE, NOW())
                        ON CONFLICT DO NOTHING
                    """
                    await conn.execute(subscription_query, user_id, payment_id, expires_at)

                    balance_query = f"""
                        UPDATE {balances_table}
                        SET unlimited_until = $1,
                            updated_at = NOW()
                        WHERE user_id = $2
                    """
                    await conn.execute(balance_query, expires_at, user_id)

                    logging.info(f"Unlimited subscription activated for user {user_id} until {expires_at}")
                else:
                    divinations_by_package = {
                        '3_spreads': 3,
                        '10_spreads': 10,
                        '20_spreads': 20,
                        '30_spreads': 30,
                    }
                    divinations_to_add = divinations_by_package.get(package_id, 0)

                    if divinations_to_add > 0:
                        balance_query = f"""
                            UPDATE {balances_table}
                            SET paid_divinations_remaining = paid_divinations_remaining + $1,
                                updated_at = NOW()
                            WHERE user_id = $2
                        """
                        await conn.execute(balance_query, divinations_to_add, user_id)
                        logging.info(f"Added {divinations_to_add} paid divinations for user {user_id}")

                return True
    except Exception as e:
        logging.error(f"Error processing successful payment {payment_id}: {e}", exc_info=True)
        return False


async def get_payment_by_id(payment_id: str) -> Optional[Dict[str, Any]]:
    """Получить информацию о платеже"""
    try:
        payments_table = get_table_name("payments")
        query = f"""
            SELECT id, payment_id, user_id, package_id, amount, amount_rub, status, email, yookassa_metadata, created_at, updated_at, completed_at
            FROM {payments_table}
            WHERE payment_id = $1
        """
        result = await Database.fetch_one(query, payment_id)
        if result:
            return {
                'id': result['id'],
                'payment_id': result['payment_id'],
                'user_id': result['user_id'],
                'package_id': result['package_id'],
                'amount': result['amount'],
                'amount_rub': result['amount_rub'],
                'status': result['status'],
                'email': result['email'],
                'yookassa_metadata': json.loads(result['yookassa_metadata']) if result['yookassa_metadata'] else None,
                'created_at': result['created_at'],
                'updated_at': result['updated_at'],
                'completed_at': result['completed_at']
            }
        return None
    except Exception as e:
        logging.error(f"Error getting payment {payment_id}: {e}", exc_info=True)
        return None


async def get_latest_pending_payment(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить последний pending-платёж пользователя (fallback, если FSM потерял payment_id)"""
    try:
        payments_table = get_table_name("payments")
        query = f"""
            SELECT payment_id, package_id, amount_rub
            FROM {payments_table}
            WHERE user_id = $1 AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
        """
        result = await Database.fetch_one(query, user_id)
        if result:
            return {
                'payment_id': result['payment_id'],
                'package_id': result['package_id'],
                'amount_rub': result['amount_rub'],
            }
        return None
    except Exception as e:
        logging.error(f"Error getting latest pending payment for user {user_id}: {e}", exc_info=True)
        return None


async def get_stale_pending_payments(minutes: int = 15) -> List[Dict[str, Any]]:
    """Получить все pending-платежи старше N минут для сверки с ЮKassa"""
    try:
        payments_table = get_table_name("payments")
        query = f"""
            SELECT payment_id, user_id, package_id, amount_rub, email, created_at
            FROM {payments_table}
            WHERE status = 'pending'
              AND created_at < NOW() - INTERVAL '{int(minutes)} minutes'
            ORDER BY created_at ASC
        """
        results = await Database.fetch_all(query)
        return [
            {
                'payment_id': r['payment_id'],
                'user_id': r['user_id'],
                'package_id': r['package_id'],
                'amount_rub': r['amount_rub'],
                'email': r['email'],
                'created_at': r['created_at'],
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Error getting stale pending payments: {e}", exc_info=True)
        return []


PAYMENT_REMINDER_STAGES = {
    '10m': (10, 'reminder_10m_sent_at'),
    '1h': (60, 'reminder_1h_sent_at'),
    '3h': (180, 'reminder_3h_sent_at'),
    '12h': (720, 'reminder_12h_sent_at'),
    '24h': (1440, 'reminder_24h_sent_at'),
    '48h': (2880, 'reminder_48h_sent_at'),
}

PAYMENT_REMINDER_PREV_SENT = {
    '10m': None,
    '1h': 'reminder_10m_sent_at',
    '3h': 'reminder_1h_sent_at',
    '12h': 'reminder_3h_sent_at',
    '24h': 'reminder_12h_sent_at',
    '48h': 'reminder_24h_sent_at',
}

_payments_reminder_columns_ensured = False


async def ensure_payments_reminder_columns() -> None:
    """Добавить колонки payment reminders с anti-catch-up для новых этапов."""
    global _payments_reminder_columns_ensured
    if _payments_reminder_columns_ensured:
        return

    payments_table = get_table_name("payments")
    try:
        for column in (
            'reminder_10m_sent_at',
            'reminder_1h_sent_at',
            'reminder_3h_sent_at',
            'reminder_24h_sent_at',
        ):
            await _add_timestamp_column_if_missing(payments_table, column)

        await _add_timestamp_column_if_missing(
            payments_table,
            'reminder_12h_sent_at',
            f"""
            UPDATE {payments_table}
            SET reminder_12h_sent_at = NOW(), updated_at = NOW()
            WHERE reminder_12h_sent_at IS NULL
              AND status IN ('pending', 'canceled')
              AND (reminder_24h_sent_at IS NOT NULL
                   OR created_at <= NOW() - INTERVAL '12 hours')
            """,
        )
        await _add_timestamp_column_if_missing(
            payments_table,
            'reminder_48h_sent_at',
            f"""
            UPDATE {payments_table}
            SET reminder_48h_sent_at = NOW(), updated_at = NOW()
            WHERE reminder_48h_sent_at IS NULL
              AND status IN ('pending', 'canceled')
              AND created_at <= NOW() - INTERVAL '48 hours'
            """,
        )
        _payments_reminder_columns_ensured = True
    except Exception as e:
        logging.error(f"Error ensuring payments reminder columns: {e}", exc_info=True)
        raise


async def get_payments_due_for_reminder(stage: str) -> List[Dict[str, Any]]:
    """
    Платежи, которым пора отправить напоминание об оплате.

    Условия:
    - status in (pending, canceled)
    - пользователь не заблокирован
    - прошло >= N минут с created_at
    - напоминание этого этапа ещё не отправлялось
    - нет «связанной» успешной оплаты:
      * оплатил (любой пакет) в любой момент после начала этой попытки — рассылка прекращается,
      * или оплатил в течение 30 мин до начала этой попытки (купил пакет, потом быстро бросил вторую оплату)
    """
    if stage not in PAYMENT_REMINDER_STAGES:
        raise ValueError(f"Unknown reminder stage: {stage}")

    minutes, sent_column = PAYMENT_REMINDER_STAGES[stage]
    prev_sent = PAYMENT_REMINDER_PREV_SENT[stage]
    prev_sent_filter = f"AND p.{prev_sent} IS NOT NULL" if prev_sent else ""
    payments_table = get_table_name("payments")
    users_table = get_table_name("users")
    balances_table = get_table_name("user_balances")
    active_paid = _active_paid_access_sql()

    try:
        await ensure_payments_reminder_columns()
        query = f"""
            SELECT p.payment_id, p.user_id, p.package_id, p.status, p.created_at
            FROM {payments_table} p
            INNER JOIN {users_table} u ON u.user_id = p.user_id
            INNER JOIN {balances_table} ub ON ub.user_id = p.user_id
            WHERE p.status IN ('pending', 'canceled')
              AND u.is_blocked = FALSE
              AND NOT ({active_paid})
              AND p.{sent_column} IS NULL
              AND p.created_at <= NOW() - INTERVAL '{int(minutes)} minutes'
              {prev_sent_filter}
              AND NOT ({_covering_succeeded_payment_sql(payments_table, 'p')})
            ORDER BY p.created_at ASC
        """
        results = await Database.fetch_all(query)
        return [
            {
                'payment_id': r['payment_id'],
                'user_id': r['user_id'],
                'package_id': r['package_id'],
                'status': r['status'],
                'created_at': r['created_at'],
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Error getting payments due for reminder ({stage}): {e}", exc_info=True)
        return []


async def mark_payment_reminder_sent(payment_id: str, stage: str) -> bool:
    """Отметить, что напоминание об оплате на данном этапе отправлено."""
    if stage not in PAYMENT_REMINDER_STAGES:
        raise ValueError(f"Unknown reminder stage: {stage}")

    _, sent_column = PAYMENT_REMINDER_STAGES[stage]
    payments_table = get_table_name("payments")

    try:
        query = f"""
            UPDATE {payments_table}
            SET {sent_column} = NOW(),
                updated_at = NOW()
            WHERE payment_id = $1
              AND {sent_column} IS NULL
        """
        await Database.execute_query(query, payment_id)
        logging.info(f"Payment reminder marked sent: {payment_id} stage={stage}")
        return True
    except Exception as e:
        logging.error(f"Error marking payment reminder sent ({payment_id}, {stage}): {e}", exc_info=True)
        return False


async def get_user_email(user_id: int) -> Optional[str]:
    """Получить email пользователя"""
    try:
        users_table = get_table_name("users")
        query = f"""
            SELECT email
            FROM {users_table}
            WHERE user_id = $1
        """
        result = await Database.fetchval(query, user_id)
        return result if result else None
    except Exception as e:
        logging.error(f"Error getting email for user {user_id}: {e}", exc_info=True)
        return None


async def update_user_email(user_id: int, email: str) -> bool:
    """Обновить email пользователя"""
    try:
        users_table = get_table_name("users")
        query = f"""
            UPDATE {users_table}
            SET email = $1
            WHERE user_id = $2
        """
        await Database.execute_query(query, email, user_id)
        logging.info(f"Email updated for user {user_id}")
        return True
    except Exception as e:
        logging.error(f"Error updating email for user {user_id}: {e}", exc_info=True)
        return False


async def get_all_users(include_blocked: bool = False, include_unsubscribed_daily_card: bool = False) -> List[Dict[str, Any]]:
    """
    Получить список всех пользователей
    
    Args:
        include_blocked: Включать ли заблокированных пользователей
        include_unsubscribed_daily_card: Включать ли отписанных от карты дня пользователей
    """
    try:
        users_table = get_table_name("users")
        query = f"""
            SELECT user_id, username, first_name, last_name, full_name, is_blocked, daily_card_subscribed
            FROM {users_table}
            WHERE 1=1
        """
        if not include_blocked:
            query += " AND is_blocked = FALSE"
        if not include_unsubscribed_daily_card:
            # По умолчанию включаем только подписанных (daily_card_subscribed IS NULL или TRUE)
            query += " AND (daily_card_subscribed IS NULL OR daily_card_subscribed = TRUE)"
        query += " ORDER BY created_at DESC"
        
        results = await Database.fetch_all(query)
        return [
            {
                'user_id': r['user_id'],
                'username': r['username'],
                'first_name': r['first_name'],
                'last_name': r['last_name'],
                'full_name': r['full_name'],
                'is_blocked': r['is_blocked'],
                'daily_card_subscribed': r['daily_card_subscribed'] if r['daily_card_subscribed'] is not None else True
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Error getting all users: {e}", exc_info=True)
        return []


FREE_DIVINATIONS_START = 3

_users_nudge_columns_ensured = False
_paid_inactivity_skipahead_backfill_done = False
_user_balances_nudge_columns_ensured = False


async def _table_has_column(table: str, column: str) -> bool:
    return bool(
        await Database.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = $1
                  AND column_name = $2
            )
            """,
            table,
            column,
        )
    )


async def _add_timestamp_column_if_missing(
    table: str,
    column: str,
    backfill_sql: Optional[str] = None,
) -> bool:
    """Создать колонку и выполнить catch-up backfill только при первом создании."""
    if await _table_has_column(table, column):
        return False

    await Database.execute_query(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} TIMESTAMP NULL"
    )
    if backfill_sql:
        await Database.execute_query(backfill_sql)
        logging.info("Catch-up backfill applied for new column %s.%s", table, column)
    return True


async def ensure_users_nudge_columns() -> None:
    """Добавить колонки max_users; новые этапы безопасно закрыть backfill."""
    global _users_nudge_columns_ensured
    if _users_nudge_columns_ensured:
        return

    users_table = get_table_name("users")
    divinations_table = get_table_name("divinations")
    balances_table = get_table_name("user_balances")
    subscriptions_table = get_table_name("subscriptions")
    try:
        for column in (
            'paid_inactivity_1d_sent_at',
            'paid_inactivity_3d_sent_at',
            'paid_inactivity_5d_sent_at',
            'paid_inactivity_10d_sent_at',
            'free_nudge_c1_1h_sent_at',
            'free_nudge_c1_3h_sent_at',
            'free_nudge_c1_24h_sent_at',
            'free_nudge_c2_3h_sent_at',
            'free_nudge_c2_24h_sent_at',
            'free_nudge_c2_48h_sent_at',
            'free_nudge_c3_1h_sent_at',
            'free_nudge_c3_3h_sent_at',
            'free_nudge_c3_24h_sent_at',
            'free_nudge_c3_48h_sent_at',
            'free_nudge_c4_3d_sent_at',
            'free_nudge_c4_7d_sent_at',
            'paywall_reached_at',
        ):
            await _add_timestamp_column_if_missing(users_table, column)

        new_columns = (
            (
                'paid_inactivity_12h_sent_at',
                f"""
                UPDATE {users_table} u
                SET paid_inactivity_12h_sent_at = NOW()
                FROM {balances_table} ub
                WHERE ub.user_id = u.user_id
                  AND u.paid_inactivity_12h_sent_at IS NULL
                  AND u.last_active_at <= NOW() - INTERVAL '12 hours'
                  AND (
                      ub.unlimited_until > NOW()
                      OR COALESCE(ub.paid_divinations_remaining, 0) > 0
                      OR EXISTS (
                          SELECT 1 FROM {subscriptions_table} s
                          WHERE s.user_id = u.user_id
                            AND s.is_active = TRUE
                            AND s.expires_at > NOW()
                      )
                  )
                  AND EXISTS (
                      SELECT 1 FROM {divinations_table} d
                      WHERE d.user_id = u.user_id
                  )
                """,
            ),
            (
                'paid_inactivity_48h_sent_at',
                f"""
                UPDATE {users_table} u
                SET paid_inactivity_48h_sent_at = NOW()
                FROM {balances_table} ub
                WHERE ub.user_id = u.user_id
                  AND u.paid_inactivity_48h_sent_at IS NULL
                  AND (u.paid_inactivity_3d_sent_at IS NOT NULL
                       OR u.last_active_at <= NOW() - INTERVAL '48 hours')
                  AND (
                      ub.unlimited_until > NOW()
                      OR COALESCE(ub.paid_divinations_remaining, 0) > 0
                      OR EXISTS (
                          SELECT 1 FROM {subscriptions_table} s
                          WHERE s.user_id = u.user_id
                            AND s.is_active = TRUE
                            AND s.expires_at > NOW()
                      )
                  )
                """,
            ),
            (
                'free_nudge_c1_12h_sent_at',
                f"""
                UPDATE {users_table}
                SET free_nudge_c1_12h_sent_at = NOW()
                WHERE free_nudge_c1_12h_sent_at IS NULL
                  AND (free_nudge_c1_24h_sent_at IS NOT NULL
                       OR created_at <= NOW() - INTERVAL '12 hours')
                  AND NOT EXISTS (
                      SELECT 1 FROM {divinations_table} d
                      WHERE d.user_id = {users_table}.user_id
                  )
                """,
            ),
            (
                'free_nudge_c1_48h_sent_at',
                f"""
                UPDATE {users_table}
                SET free_nudge_c1_48h_sent_at = NOW()
                WHERE free_nudge_c1_48h_sent_at IS NULL
                  AND created_at <= NOW() - INTERVAL '48 hours'
                  AND NOT EXISTS (
                      SELECT 1 FROM {divinations_table} d
                      WHERE d.user_id = {users_table}.user_id
                  )
                """,
            ),
            (
                'free_nudge_c2_12h_sent_at',
                f"""
                UPDATE {users_table}
                SET free_nudge_c2_12h_sent_at = NOW()
                WHERE free_nudge_c2_12h_sent_at IS NULL
                  AND (free_nudge_c2_24h_sent_at IS NOT NULL
                       OR free_nudge_c2_48h_sent_at IS NOT NULL
                       OR last_active_at <= NOW() - INTERVAL '12 hours')
                """,
            ),
            (
                'free_nudge_c3_12h_sent_at',
                f"""
                UPDATE {users_table}
                SET free_nudge_c3_12h_sent_at = NOW()
                WHERE free_nudge_c3_12h_sent_at IS NULL
                  AND (free_nudge_c3_24h_sent_at IS NOT NULL
                       OR free_nudge_c3_48h_sent_at IS NOT NULL
                       OR paywall_reached_at <= NOW() - INTERVAL '12 hours')
                """,
            ),
        )
        for column, backfill_sql in new_columns:
            await _add_timestamp_column_if_missing(
                users_table, column, backfill_sql
            )

        await _backfill_paid_inactivity_skipahead(users_table)

        _users_nudge_columns_ensured = True
    except Exception as e:
        logging.error(f"Error ensuring users nudge columns: {e}", exc_info=True)
        raise


async def ensure_user_balances_nudge_columns() -> None:
    """Добавить balance-колонки; новые expiry-этапы закрыть backfill."""
    global _user_balances_nudge_columns_ensured
    if _user_balances_nudge_columns_ensured:
        return

    balances_table = get_table_name("user_balances")
    try:
        for column in (
            'access_expired_at',
            'expired_access_reminder_for_until',
            'expired_access_day0_sent_at',
            'expired_access_day1_sent_at',
            'expired_access_day2_sent_at',
            'expired_access_day3_sent_at',
        ):
            await _add_timestamp_column_if_missing(balances_table, column)

        expiry_at = _expiry_at_expr("")
        for day, column in (
            (4, 'expired_access_day4_sent_at'),
            (5, 'expired_access_day5_sent_at'),
            (6, 'expired_access_day6_sent_at'),
            (7, 'expired_access_day7_sent_at'),
        ):
            await _add_timestamp_column_if_missing(
                balances_table,
                column,
                f"""
                UPDATE {balances_table}
                SET {column} = NOW(), updated_at = NOW()
                WHERE {column} IS NULL
                  AND {expiry_at} IS NOT NULL
                  AND (NOW() AT TIME ZONE 'Europe/Moscow')::date
                      >= ({expiry_at} AT TIME ZONE 'Europe/Moscow')::date + {day}
                """,
            )
        _user_balances_nudge_columns_ensured = True
    except Exception as e:
        logging.error(f"Error ensuring user_balances nudge columns: {e}", exc_info=True)
        raise


ACTIVE_PAYMENT_FUNNEL_HOURS = 48


def _covering_succeeded_payment_sql(
    payments_table: str,
    payment_alias: str = 'p',
) -> str:
    """Есть succeeded, который закрывает конкретную попытку оплаты."""
    return f"""
        EXISTS (
            SELECT 1 FROM {payments_table} s
            WHERE s.user_id = {payment_alias}.user_id
              AND s.status = 'succeeded'
              AND s.completed_at IS NOT NULL
              AND (
                  s.completed_at >= {payment_alias}.created_at
                  OR (
                      s.completed_at <= {payment_alias}.created_at
                      AND s.completed_at >= {payment_alias}.created_at
                          - INTERVAL '30 minutes'
                  )
              )
        )
    """


def _active_payment_funnel_exists_sql(
    payments_table: str,
    *,
    include_canceled: bool = True,
    max_age_hours: int = ACTIVE_PAYMENT_FUNNEL_HOURS,
) -> str:
    """Свежая незавершённая оплата, пока ещё идут payment reminders."""
    status_filter = (
        "p.status IN ('pending', 'canceled')"
        if include_canceled
        else "p.status = 'pending'"
    )
    hours = int(max_age_hours)
    return f"""
        EXISTS (
            SELECT 1 FROM {payments_table} p
            WHERE p.user_id = u.user_id
              AND {status_filter}
              AND p.created_at > NOW() - INTERVAL '{hours} hours'
              AND NOT ({_covering_succeeded_payment_sql(payments_table, 'p')})
        )
    """


def _open_payment_exists_sql(payments_table: str) -> str:
    """Обратная совместимость для старых импортов."""
    return _active_payment_funnel_exists_sql(payments_table)


def _active_paid_access_sql() -> str:
    """SQL-условие: у пользователя есть активный платный доступ."""
    subscriptions_table = get_table_name("subscriptions")
    return f"""
        (
            (ub.unlimited_until IS NOT NULL AND ub.unlimited_until > NOW())
            OR COALESCE(ub.paid_divinations_remaining, 0) > 0
            OR EXISTS (
                SELECT 1 FROM {subscriptions_table} s
                WHERE s.user_id = u.user_id
                  AND s.is_active = TRUE
                  AND s.expires_at > NOW()
            )
        )
    """


def _expiry_at_expr(prefix: str = "ub") -> str:
    """Момент истечения платного доступа (unlimited или последний paid-пакет)."""
    p = f"{prefix}." if prefix else ""
    return f"""
        COALESCE(
            CASE
                WHEN {p}unlimited_until IS NOT NULL AND {p}unlimited_until <= NOW()
                THEN {p}unlimited_until
            END,
            {p}access_expired_at
        )
    """


async def mark_paywall_reached(user_id: int) -> bool:
    """Зафиксировать момент первого попадания на пейволл (исчерпаны бесплатные)."""
    try:
        await ensure_users_nudge_columns()
        users_table = get_table_name("users")
        await Database.execute_query(
            f"""
            UPDATE {users_table}
            SET paywall_reached_at = COALESCE(paywall_reached_at, NOW())
            WHERE user_id = $1
            """,
            user_id,
        )
        return True
    except Exception as e:
        logging.error(f"Error marking paywall reached for user {user_id}: {e}", exc_info=True)
        return False


async def update_user_activity_on_divination(user_id: int) -> bool:
    """Обновить last_active_at и сбросить таймеры nudge после гадания."""
    try:
        await ensure_users_nudge_columns()
        users_table = get_table_name("users")
        await Database.execute_query(
            f"UPDATE {users_table} SET last_active_at = NOW() WHERE user_id = $1",
            user_id,
        )
        await reset_inactivity_nudge_state(user_id)
        return True
    except Exception as e:
        logging.error(f"Error updating divination activity for user {user_id}: {e}", exc_info=True)
        return False


async def reset_inactivity_nudge_state(user_id: int) -> bool:
    """Сбросить sent_at nudge-рассылок при возвращении пользователя."""
    try:
        await ensure_users_nudge_columns()
        await ensure_user_balances_nudge_columns()
        users_table = get_table_name("users")
        balances_table = get_table_name("user_balances")
        await Database.execute_query(
            f"""
            UPDATE {users_table}
            SET paid_inactivity_12h_sent_at = NULL,
                paid_inactivity_1d_sent_at = NULL,
                paid_inactivity_48h_sent_at = NULL,
                paid_inactivity_3d_sent_at = NULL,
                paid_inactivity_5d_sent_at = NULL,
                paid_inactivity_10d_sent_at = NULL,
                free_nudge_c2_3h_sent_at = NULL,
                free_nudge_c2_12h_sent_at = NULL,
                free_nudge_c2_24h_sent_at = NULL,
                free_nudge_c2_48h_sent_at = NULL,
                free_nudge_c4_3d_sent_at = NULL,
                free_nudge_c4_7d_sent_at = NULL
            WHERE user_id = $1
            """,
            user_id,
        )
        await Database.execute_query(
            f"""
            UPDATE {balances_table}
            SET access_expired_at = NULL,
                updated_at = NOW()
            WHERE user_id = $1
              AND (unlimited_until IS NULL OR unlimited_until <= NOW())
              AND COALESCE(free_divinations_remaining, {FREE_DIVINATIONS_START}) > 0
            """,
            user_id,
        )
        return True
    except Exception as e:
        logging.error(f"Error resetting nudge state for user {user_id}: {e}", exc_info=True)
        return False


PAID_INACTIVITY_STAGES = {
    '12h': (12, 'paid_inactivity_12h_sent_at'),
    '1d': (24, 'paid_inactivity_1d_sent_at'),
    '48h': (48, 'paid_inactivity_48h_sent_at'),
    '3d': (72, 'paid_inactivity_3d_sent_at'),
    '5d': (120, 'paid_inactivity_5d_sent_at'),
    '10d': (240, 'paid_inactivity_10d_sent_at'),
}

PAID_INACTIVITY_STAGE_ORDER = tuple(PAID_INACTIVITY_STAGES.keys())

# Младшие этапы для skip-ahead backfill при деплое (см. _backfill_paid_inactivity_skipahead).
PAID_INACTIVITY_SKIPAHEAD_JUNIORS = {
    '1d': ('12h',),
    '48h': ('12h', '1d'),
    '3d': ('12h', '1d', '48h'),
    '5d': ('12h', '1d', '48h', '3d'),
    '10d': ('12h', '1d', '48h', '3d', '5d'),
}


def _paid_inactivity_sent_flags(row: Dict[str, Any]) -> Dict[str, Optional[datetime]]:
    return {
        stage: row.get(column)
        for stage, (_, column) in PAID_INACTIVITY_STAGES.items()
    }


def pick_highest_due_paid_inactivity_stage(
    last_active_at: datetime,
    sent_at_by_stage: Dict[str, Optional[datetime]],
    now: Optional[datetime] = None,
) -> Optional[str]:
    """
    Старший просроченный этап B, который ещё не отправляли в текущем цикле молчания.

    При тишине 25ч и пустых флагах вернёт 1d (не 12h), чтобы не догонять цепочку пачкой.
    """
    if last_active_at is None:
        return None

    now = now or datetime.now(timezone.utc)
    if last_active_at.tzinfo is None:
        anchor = last_active_at.replace(tzinfo=timezone.utc)
    else:
        anchor = last_active_at.astimezone(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    best_stage: Optional[str] = None
    best_hours = -1
    for stage in PAID_INACTIVITY_STAGE_ORDER:
        hours, _ = PAID_INACTIVITY_STAGES[stage]
        if sent_at_by_stage.get(stage) is not None:
            continue
        if anchor <= now - timedelta(hours=hours):
            if hours > best_hours:
                best_stage = stage
                best_hours = hours
    return best_stage


def paid_inactivity_stages_up_to(stage: str) -> tuple[str, ...]:
    """Этапы от 12h до stage включительно."""
    if stage not in PAID_INACTIVITY_STAGES:
        raise ValueError(f"Unknown paid inactivity stage: {stage}")
    idx = PAID_INACTIVITY_STAGE_ORDER.index(stage)
    return PAID_INACTIVITY_STAGE_ORDER[: idx + 1]


async def _backfill_paid_inactivity_skipahead(users_table: str) -> None:
    """
    Одноразовый catch-up при деплое skip-ahead: младшие этапы помечаем sent,
    если пользователь уже прошёл порог старшего — без реальной отправки.
    """
    global _paid_inactivity_skipahead_backfill_done
    if _paid_inactivity_skipahead_backfill_done:
        return

    balances_table = get_table_name("user_balances")
    divinations_table = get_table_name("divinations")
    active_paid = _active_paid_access_sql()
    paid_filters = f"""
        {active_paid}
        AND u.is_blocked = FALSE
        AND u.last_active_at IS NOT NULL
        AND EXISTS (SELECT 1 FROM {divinations_table} d WHERE d.user_id = u.user_id)
    """

    try:
        for stage in reversed(PAID_INACTIVITY_STAGE_ORDER[1:]):
            hours, stage_col = PAID_INACTIVITY_STAGES[stage]
            for junior in PAID_INACTIVITY_SKIPAHEAD_JUNIORS[stage]:
                _, junior_col = PAID_INACTIVITY_STAGES[junior]
                await Database.execute_query(
                    f"""
                    UPDATE {users_table} u
                    SET {junior_col} = NOW()
                    FROM {balances_table} ub
                    WHERE ub.user_id = u.user_id
                      AND {paid_filters}
                      AND u.{junior_col} IS NULL
                      AND u.{stage_col} IS NULL
                      AND u.last_active_at <= NOW() - INTERVAL '{int(hours)} hours'
                    """
                )

        for stage in reversed(PAID_INACTIVITY_STAGE_ORDER[1:]):
            _, stage_col = PAID_INACTIVITY_STAGES[stage]
            for junior in PAID_INACTIVITY_SKIPAHEAD_JUNIORS[stage]:
                _, junior_col = PAID_INACTIVITY_STAGES[junior]
                await Database.execute_query(
                    f"""
                    UPDATE {users_table} u
                    SET {junior_col} = COALESCE(u.{junior_col}, u.{stage_col}, NOW())
                    WHERE u.{junior_col} IS NULL
                      AND u.{stage_col} IS NOT NULL
                    """
                )

        _paid_inactivity_skipahead_backfill_done = True
        logging.info("Paid inactivity skip-ahead catch-up backfill applied")
    except Exception as e:
        logging.error(f"Error in paid inactivity skip-ahead backfill: {e}", exc_info=True)
        raise


FREE_NUDGE_STAGES = {
    'c1': {
        '1h': (1, 'free_nudge_c1_1h_sent_at', 'created_at', 'hours'),
        '3h': (3, 'free_nudge_c1_3h_sent_at', 'created_at', 'hours'),
        '12h': (12, 'free_nudge_c1_12h_sent_at', 'created_at', 'hours'),
        '24h': (24, 'free_nudge_c1_24h_sent_at', 'created_at', 'hours'),
        '48h': (48, 'free_nudge_c1_48h_sent_at', 'created_at', 'hours'),
    },
    'c2': {
        '3h': (3, 'free_nudge_c2_3h_sent_at', 'last_active_at', 'hours'),
        '12h': (12, 'free_nudge_c2_12h_sent_at', 'last_active_at', 'hours'),
        '24h': (24, 'free_nudge_c2_24h_sent_at', 'last_active_at', 'hours'),
        '48h': (48, 'free_nudge_c2_48h_sent_at', 'last_active_at', 'hours'),
    },
    'c3': {
        '1h': (1, 'free_nudge_c3_1h_sent_at', 'paywall_reached_at', 'hours'),
        '3h': (3, 'free_nudge_c3_3h_sent_at', 'paywall_reached_at', 'hours'),
        '12h': (12, 'free_nudge_c3_12h_sent_at', 'paywall_reached_at', 'hours'),
        '24h': (24, 'free_nudge_c3_24h_sent_at', 'paywall_reached_at', 'hours'),
        '48h': (48, 'free_nudge_c3_48h_sent_at', 'paywall_reached_at', 'hours'),
    },
    'c4': {
        '3d': (3, 'free_nudge_c4_3d_sent_at', 'last_active_at', 'days'),
        '7d': (7, 'free_nudge_c4_7d_sent_at', 'last_active_at', 'days'),
    },
}

FREE_NUDGE_PREV_SENT = {
    'c1': {'1h': None, '3h': 'free_nudge_c1_1h_sent_at', '12h': 'free_nudge_c1_3h_sent_at', '24h': 'free_nudge_c1_12h_sent_at', '48h': 'free_nudge_c1_24h_sent_at'},
    'c2': {'3h': None, '12h': 'free_nudge_c2_3h_sent_at', '24h': 'free_nudge_c2_12h_sent_at', '48h': 'free_nudge_c2_24h_sent_at'},
    'c3': {'1h': None, '3h': 'free_nudge_c3_1h_sent_at', '12h': 'free_nudge_c3_3h_sent_at', '24h': 'free_nudge_c3_12h_sent_at', '48h': 'free_nudge_c3_24h_sent_at'},
    'c4': {'3d': None, '7d': 'free_nudge_c4_3d_sent_at'},
}

EXPIRED_ACCESS_REMINDER_STAGES = {
    'day0': (0, 'expired_access_day0_sent_at'),
    'day1': (1, 'expired_access_day1_sent_at'),
    'day2': (2, 'expired_access_day2_sent_at'),
    'day3': (3, 'expired_access_day3_sent_at'),
    'day4': (4, 'expired_access_day4_sent_at'),
    'day5': (5, 'expired_access_day5_sent_at'),
    'day6': (6, 'expired_access_day6_sent_at'),
    'day7': (7, 'expired_access_day7_sent_at'),
}

EXPIRED_ACCESS_PREV_SENT = {
    'day0': None,
    'day1': 'expired_access_day0_sent_at',
    'day2': 'expired_access_day1_sent_at',
    'day3': 'expired_access_day2_sent_at',
    'day4': 'expired_access_day3_sent_at',
    'day5': 'expired_access_day4_sent_at',
    'day6': 'expired_access_day5_sent_at',
    'day7': 'expired_access_day6_sent_at',
}


async def get_users_due_for_paid_inactivity_nudge() -> List[Dict[str, Any]]:
    """Платники (B): не более одного этапа — старший из просроченных в цикле молчания."""
    users_table = get_table_name("users")
    balances_table = get_table_name("user_balances")
    payments_table = get_table_name("payments")
    divinations_table = get_table_name("divinations")
    active_paid = _active_paid_access_sql()
    sent_columns = ", ".join(
        f"u.{column}" for _, column in PAID_INACTIVITY_STAGES.values()
    )

    try:
        await ensure_users_nudge_columns()
        query = f"""
            SELECT u.user_id, u.last_active_at, {sent_columns}
            FROM {users_table} u
            JOIN {balances_table} ub ON ub.user_id = u.user_id
            WHERE u.is_blocked = FALSE
              AND u.last_active_at IS NOT NULL
              AND u.last_active_at <= NOW() - INTERVAL '12 hours'
              AND {active_paid}
              AND EXISTS (
                  SELECT 1 FROM {divinations_table} d WHERE d.user_id = u.user_id
              )
              AND NOT ({_active_payment_funnel_exists_sql(
                  payments_table, include_canceled=False
              )})
            ORDER BY u.user_id
        """
        results = await Database.fetch_all(query)
        due: List[Dict[str, Any]] = []
        for row in results:
            flags = _paid_inactivity_sent_flags(row)
            stage = pick_highest_due_paid_inactivity_stage(
                row['last_active_at'],
                flags,
            )
            if stage is None:
                continue
            due.append(
                {
                    'user_id': row['user_id'],
                    'last_active_at': row['last_active_at'],
                    'stage': stage,
                }
            )
        return due
    except Exception as e:
        logging.error(f"Error getting paid inactivity nudge users: {e}", exc_info=True)
        return []


async def mark_paid_inactivity_nudge_sent(user_id: int, stage: str) -> bool:
    if stage not in PAID_INACTIVITY_STAGES:
        raise ValueError(f"Unknown paid inactivity stage: {stage}")
    try:
        await ensure_users_nudge_columns()
        users_table = get_table_name("users")
        set_parts = [
            f"{PAID_INACTIVITY_STAGES[s][1]} = COALESCE({PAID_INACTIVITY_STAGES[s][1]}, NOW())"
            for s in paid_inactivity_stages_up_to(stage)
        ]
        await Database.execute_query(
            f"UPDATE {users_table} SET {', '.join(set_parts)} WHERE user_id = $1",
            user_id,
        )
        return True
    except Exception as e:
        logging.error(f"Error marking paid inactivity nudge ({stage}) for user {user_id}: {e}", exc_info=True)
        return False


async def get_users_due_for_free_nudge(category: str, stage: str) -> List[Dict[str, Any]]:
    """Бесплатные пользователи для nudge C1–C4."""
    if category not in FREE_NUDGE_STAGES or stage not in FREE_NUDGE_STAGES[category]:
        raise ValueError(f"Unknown free nudge category/stage: {category}/{stage}")

    amount, sent_column, anchor, unit = FREE_NUDGE_STAGES[category][stage]
    interval = f"{int(amount)} {unit}"
    users_table = get_table_name("users")
    balances_table = get_table_name("user_balances")
    payments_table = get_table_name("payments")
    divinations_table = get_table_name("divinations")

    anchor_expr = {
        'created_at': 'u.created_at',
        'last_active_at': 'u.last_active_at',
        'paywall_reached_at': 'u.paywall_reached_at',
    }[anchor]

    category_filter = {
        'c1': f"""
            NOT EXISTS (SELECT 1 FROM {divinations_table} d WHERE d.user_id = u.user_id)
        """,
        'c2': f"""
            EXISTS (SELECT 1 FROM {divinations_table} d WHERE d.user_id = u.user_id)
            AND COALESCE(ub.free_divinations_remaining, {FREE_DIVINATIONS_START}) > 0
        """,
        'c3': f"""
            COALESCE(ub.free_divinations_remaining, 0) = 0
            AND NOT EXISTS (
                SELECT 1 FROM {payments_table} p
                WHERE p.user_id = u.user_id AND p.status = 'succeeded'
            )
            AND u.paywall_reached_at IS NOT NULL
        """,
        'c4': f"""
            EXISTS (SELECT 1 FROM {divinations_table} d WHERE d.user_id = u.user_id)
            AND COALESCE(ub.free_divinations_remaining, {FREE_DIVINATIONS_START}) > 0
        """,
    }[category]

    prev_sent = FREE_NUDGE_PREV_SENT[category].get(stage)
    prev_sent_filter = f"AND u.{prev_sent} IS NOT NULL" if prev_sent else ""
    active_paid = _active_paid_access_sql()

    try:
        await ensure_users_nudge_columns()
        query = f"""
            SELECT u.user_id, {anchor_expr} AS anchor_at
            FROM {users_table} u
            JOIN {balances_table} ub ON ub.user_id = u.user_id
            WHERE u.is_blocked = FALSE
              AND NOT ({active_paid})
              AND u.{sent_column} IS NULL
              AND {anchor_expr} IS NOT NULL
              AND {anchor_expr} <= NOW() - INTERVAL '{interval}'
              AND {category_filter}
              AND NOT ({_active_payment_funnel_exists_sql(
                  payments_table, include_canceled=True
              )})
              {prev_sent_filter}
            ORDER BY u.user_id
        """
        results = await Database.fetch_all(query)
        return [
            {
                'user_id': r['user_id'],
                'anchor_at': r['anchor_at'],
                'category': category,
                'stage': stage,
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Error getting free nudge users ({category}/{stage}): {e}", exc_info=True)
        return []


async def mark_free_nudge_sent(user_id: int, category: str, stage: str) -> bool:
    if category not in FREE_NUDGE_STAGES or stage not in FREE_NUDGE_STAGES[category]:
        raise ValueError(f"Unknown free nudge category/stage: {category}/{stage}")
    _, sent_column, _, _ = FREE_NUDGE_STAGES[category][stage]
    try:
        await ensure_users_nudge_columns()
        users_table = get_table_name("users")
        await Database.execute_query(
            f"UPDATE {users_table} SET {sent_column} = NOW() WHERE user_id = $1 AND {sent_column} IS NULL",
            user_id,
        )
        return True
    except Exception as e:
        logging.error(
            f"Error marking free nudge ({category}/{stage}) for user {user_id}: {e}",
            exc_info=True,
        )
        return False


async def get_users_due_for_expired_access_reminder(stage: str) -> List[Dict[str, Any]]:
    """Платники без доступа — серия day0–day7 после истечения."""
    if stage not in EXPIRED_ACCESS_REMINDER_STAGES:
        raise ValueError(f"Unknown expired access reminder stage: {stage}")

    day_offset, sent_column = EXPIRED_ACCESS_REMINDER_STAGES[stage]
    prev_sent = EXPIRED_ACCESS_PREV_SENT[stage]
    users_table = get_table_name("users")
    balances_table = get_table_name("user_balances")
    payments_table = get_table_name("payments")
    divinations_table = get_table_name("divinations")
    expiry_at = _expiry_at_expr("ub")
    active_paid = _active_paid_access_sql()

    if stage == 'day0':
        stage_extra = f"""
              AND (ub.expired_access_reminder_for_until IS NULL
                   OR ub.expired_access_reminder_for_until != ({expiry_at}))
        """
        sent_filter = ""
    else:
        stage_extra = f"""
              AND ub.expired_access_reminder_for_until = {expiry_at}
              AND ub.{prev_sent} IS NOT NULL
        """
        sent_filter = f"AND ub.{sent_column} IS NULL"

    try:
        await ensure_user_balances_nudge_columns()
        query = f"""
            SELECT
                u.user_id,
                u.last_active_at,
                {expiry_at} AS expiry_at
            FROM {users_table} u
            INNER JOIN {balances_table} ub ON ub.user_id = u.user_id
            WHERE u.is_blocked = FALSE
              AND {expiry_at} IS NOT NULL
              AND NOT ({active_paid})
              AND (NOW() AT TIME ZONE 'Europe/Moscow')::date
                  >= ({expiry_at} AT TIME ZONE 'Europe/Moscow')::date + {int(day_offset)}
              {sent_filter}
              {stage_extra}
              AND EXISTS (
                  SELECT 1 FROM {payments_table} p
                  WHERE p.user_id = u.user_id AND p.status = 'succeeded'
              )
              AND EXISTS (
                  SELECT 1 FROM {divinations_table} d
                  WHERE d.user_id = u.user_id
              )
            ORDER BY u.user_id
        """
        results = await Database.fetch_all(query)
        return [
            {
                'user_id': r['user_id'],
                'last_active_at': r['last_active_at'],
                'expiry_at': r['expiry_at'],
                'stage': stage,
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Error getting expired access reminder users ({stage}): {e}", exc_info=True)
        return []


async def get_expired_access_reminder_stage_for_user(user_id: int) -> Optional[str]:
    """Какой этап expiry-серии сейчас due для пользователя (или None)."""
    for stage in EXPIRED_ACCESS_REMINDER_STAGES:
        due = await get_users_due_for_expired_access_reminder(stage)
        if any(u['user_id'] == user_id for u in due):
            return stage
    return None


async def mark_expired_access_reminder_sent(user_id: int, stage: str) -> bool:
    """Отметить отправку expiry-напоминания на данном этапе."""
    if stage not in EXPIRED_ACCESS_REMINDER_STAGES:
        raise ValueError(f"Unknown expired access reminder stage: {stage}")

    _, sent_column = EXPIRED_ACCESS_REMINDER_STAGES[stage]
    balances_table = get_table_name("user_balances")
    expiry_set = _expiry_at_expr("")

    try:
        await ensure_user_balances_nudge_columns()
        if stage == 'day0':
            query = f"""
                UPDATE {balances_table}
                SET expired_access_reminder_for_until = {expiry_set},
                    expired_access_day0_sent_at = NOW(),
                    expired_access_day1_sent_at = NULL,
                    expired_access_day2_sent_at = NULL,
                    expired_access_day3_sent_at = NULL,
                    expired_access_day4_sent_at = NULL,
                    expired_access_day5_sent_at = NULL,
                    expired_access_day6_sent_at = NULL,
                    expired_access_day7_sent_at = NULL,
                    updated_at = NOW()
                WHERE user_id = $1
                  AND {expiry_set} IS NOT NULL
                  AND (expired_access_reminder_for_until IS NULL
                       OR expired_access_reminder_for_until != {expiry_set})
            """
        else:
            query = f"""
                UPDATE {balances_table}
                SET {sent_column} = NOW(),
                    updated_at = NOW()
                WHERE user_id = $1
                  AND expired_access_reminder_for_until = {expiry_set}
                  AND {sent_column} IS NULL
            """
        await Database.execute_query(query, user_id)
        logging.info(f"Expired access reminder marked sent: user={user_id} stage={stage}")
        return True
    except Exception as e:
        logging.error(
            f"Error marking expired access reminder sent ({user_id}, {stage}): {e}",
            exc_info=True,
        )
        return False


async def get_paid_users() -> List[Dict[str, Any]]:
    """
    Получить список пользователей, у которых есть хотя бы один успешный платёж.
    Исключает заблокированных (is_blocked = TRUE).
    """
    try:
        users_table = get_table_name("users")
        payments_table = get_table_name("payments")
        query = f"""
            SELECT DISTINCT u.user_id, u.username, u.first_name, u.last_name, u.full_name
            FROM {users_table} u
            JOIN {payments_table} p ON u.user_id = p.user_id
            WHERE p.status = 'succeeded'
              AND u.is_blocked = FALSE
            ORDER BY u.user_id
        """
        results = await Database.fetch_all(query)
        return [
            {
                'user_id': r['user_id'],
                'username': r['username'],
                'first_name': r['first_name'],
                'last_name': r['last_name'],
                'full_name': r['full_name'],
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Error getting paid users: {e}", exc_info=True)
        return []


def is_send_blocked_error(exc: Exception) -> bool:
    """Пользователь недоступен для отправки (блок, chat.denied, chat not found и т.д.)."""
    from main.send_errors import is_unreachable_user_error

    return is_unreachable_user_error(exc)


async def update_user_blocked_status(user_id: int, is_blocked: bool) -> bool:
    """Обновить статус блокировки пользователя"""
    try:
        users_table = get_table_name("users")
        query = f"""
            UPDATE {users_table}
            SET is_blocked = $1
            WHERE user_id = $2
        """
        await Database.execute_query(query, is_blocked, user_id)
        logging.info(f"Blocked status updated for user {user_id}: is_blocked={is_blocked}")
        return True
    except Exception as e:
        logging.error(f"Error updating blocked status for user {user_id}: {e}", exc_info=True)
        return False


async def get_user_daily_card_subscription(user_id: int) -> Optional[bool]:
    """
    Получить статус подписки на карту дня пользователя
    Возвращает True если подписан, False если отписан, None если поле не установлено (по умолчанию подписан)
    """
    try:
        users_table = get_table_name("users")
        query = f"""
            SELECT daily_card_subscribed
            FROM {users_table}
            WHERE user_id = $1
        """
        result = await Database.fetchval(query, user_id)
        # Если поле NULL, считаем что пользователь подписан (по умолчанию)
        return result if result is not None else True
    except Exception as e:
        logging.error(f"Error getting daily card subscription for user {user_id}: {e}", exc_info=True)
        return True  # По умолчанию считаем подписанным


async def update_user_daily_card_subscription(user_id: int, subscribed: bool) -> bool:
    """Обновить статус подписки на карту дня пользователя"""
    try:
        users_table = get_table_name("users")
        query = f"""
            UPDATE {users_table}
            SET daily_card_subscribed = $1
            WHERE user_id = $2
        """
        await Database.execute_query(query, subscribed, user_id)
        logging.info(f"Daily card subscription updated for user {user_id}: subscribed={subscribed}")
        return True
    except Exception as e:
        logging.error(f"Error updating daily card subscription for user {user_id}: {e}", exc_info=True)
        return False


# ==================== Подписка на канал ====================

async def has_paid_access(user_id: int) -> bool:
    """
    Проверить, есть ли у пользователя платный доступ (активная подписка или платные гадания).
    Таким пользователям не нужно проверять подписку на канал.
    """
    try:
        balance = await get_user_balance(user_id)
        if not balance:
            return False
        if balance['unlimited_until'] and balance['unlimited_until'] > datetime.now():
            return True
        if balance['paid_divinations_remaining'] > 0:
            return True
        return False
    except Exception as e:
        logging.error(f"Error checking paid access for user {user_id}: {e}", exc_info=True)
        return False


async def mark_channel_subscribed(user_id: int) -> bool:
    """Записать, что пользователь подтвердил подписку на канал."""
    try:
        users_table = get_table_name("users")
        query = f"UPDATE {users_table} SET channel_subscribed_at = NOW() WHERE user_id = $1"
        await Database.execute_query(query, user_id)
        logging.info(f"Channel subscription confirmed for user {user_id}")
        return True
    except Exception as e:
        logging.error(f"Error marking channel subscription for user {user_id}: {e}", exc_info=True)
        return False


async def clear_channel_subscribed(user_id: int) -> bool:
    """Обнулить дату подписки на канал (пользователь отписался)."""
    try:
        users_table = get_table_name("users")
        query = f"UPDATE {users_table} SET channel_subscribed_at = NULL WHERE user_id = $1"
        await Database.execute_query(query, user_id)
        logging.info(f"Channel subscription cleared for user {user_id}")
        return True
    except Exception as e:
        logging.error(f"Error clearing channel subscription for user {user_id}: {e}", exc_info=True)
        return False


# ==================== Pending Questions (for WebApp) ====================

async def ensure_pending_questions_table():
    """Создать таблицу pending_questions если не существует"""
    table = get_table_name("pending_questions")
    query = f"""
        CREATE TABLE IF NOT EXISTS {table} (
            user_id BIGINT PRIMARY KEY,
            question TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """
    try:
        await Database.execute_query(query)
    except Exception as e:
        logging.error(f"Error creating pending_questions table: {e}", exc_info=True)


async def save_pending_question(user_id: int, question: str) -> bool:
    """Сохранить вопрос пользователя перед открытием WebApp"""
    table = get_table_name("pending_questions")
    try:
        await ensure_pending_questions_table()
        query = f"""
            INSERT INTO {table} (user_id, question, created_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (user_id) DO UPDATE SET question = $2, created_at = NOW()
        """
        await Database.execute_query(query, user_id, question)
        return True
    except Exception as e:
        logging.error(f"Error saving pending question for user {user_id}: {e}", exc_info=True)
        return False


async def get_pending_question(user_id: int) -> Optional[str]:
    """Получить сохранённый вопрос пользователя"""
    table = get_table_name("pending_questions")
    try:
        await ensure_pending_questions_table()
        query = f"SELECT question FROM {table} WHERE user_id = $1"
        return await Database.fetchval(query, user_id)
    except Exception as e:
        logging.error(f"Error getting pending question for user {user_id}: {e}", exc_info=True)
        return None


async def delete_pending_question(user_id: int):
    """Удалить pending question после обработки"""
    table = get_table_name("pending_questions")
    try:
        query = f"DELETE FROM {table} WHERE user_id = $1"
        await Database.execute_query(query, user_id)
    except Exception as e:
        logging.error(f"Error deleting pending question for user {user_id}: {e}", exc_info=True)


# ==================== Контекст уточняющих вопросов после WebApp-гадания ====================

async def ensure_webapp_follow_up_context_table():
    """Создать таблицу webapp_follow_up_context если не существует"""
    table = get_table_name("webapp_follow_up_context")
    query = f"""
        CREATE TABLE IF NOT EXISTS {table} (
            user_id BIGINT PRIMARY KEY,
            divination_id INTEGER NOT NULL,
            conversation_history JSONB NOT NULL,
            follow_up_count INTEGER NOT NULL DEFAULT 0,
            is_free BOOLEAN NOT NULL DEFAULT TRUE,
            original_interpretation TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """
    try:
        await Database.execute_query(query)
    except Exception as e:
        logging.error(f"Error creating webapp_follow_up_context table: {e}", exc_info=True)


async def save_webapp_follow_up_context(
    user_id: int,
    divination_id: int,
    conversation_history: List[Dict[str, Any]],
    is_free: bool,
    original_interpretation: str
) -> bool:
    """Сохранить контекст для уточняющих вопросов после WebApp-гадания (FSM недоступен из HTTP)"""
    table = get_table_name("webapp_follow_up_context")
    try:
        await ensure_webapp_follow_up_context_table()
        history_json = json.dumps(conversation_history, ensure_ascii=False)
        query = f"""
            INSERT INTO {table} (user_id, divination_id, conversation_history, follow_up_count, is_free, original_interpretation, created_at)
            VALUES ($1, $2, $3::jsonb, 0, $4, $5, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                divination_id = $2, conversation_history = $3::jsonb, follow_up_count = 0, is_free = $4,
                original_interpretation = $5, created_at = NOW()
        """
        await Database.execute_query(query, user_id, divination_id, history_json, is_free, original_interpretation)
        return True
    except Exception as e:
        logging.error(f"Error saving webapp follow-up context for user {user_id}: {e}", exc_info=True)
        return False


async def get_and_delete_webapp_follow_up_context(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить контекст уточняющих вопросов после WebApp-гадания и удалить запись.
    Возвращает dict: divination_id, conversation_history, follow_up_count, is_free_divination, original_interpretation.
    """
    table = get_table_name("webapp_follow_up_context")
    try:
        await ensure_webapp_follow_up_context_table()
        query = f"""
            DELETE FROM {table} WHERE user_id = $1
            RETURNING divination_id, conversation_history, follow_up_count, is_free, original_interpretation
        """
        row = await Database.fetch_one(query, user_id)
        if not row:
            return None
        return {
            "divination_id": row["divination_id"],
            "conversation_history": row["conversation_history"] if isinstance(row["conversation_history"], list) else json.loads(row["conversation_history"]),
            "follow_up_count": row["follow_up_count"],
            "is_free_divination": row["is_free"],
            "original_interpretation": row["original_interpretation"],
        }
    except Exception as e:
        logging.error(f"Error getting webapp follow-up context for user {user_id}: {e}", exc_info=True)
        return None

