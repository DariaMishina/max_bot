"""
Модуль для работы с базой данных PostgreSQL
"""
import logging
from typing import Optional, Dict, Any, List
import asyncpg
from datetime import datetime, timedelta
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
                    update_query = f"""
                        UPDATE {balances_table}
                        SET paid_divinations_remaining = paid_divinations_remaining - 1,
                            total_divinations_used = total_divinations_used + 1,
                            updated_at = NOW()
                        WHERE user_id = $1
                    """
                    await conn.execute(update_query, user_id)
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


async def process_successful_payment(payment_id: str) -> bool:
    """
    Обработать успешный платеж:
    1. Обновить статус платежа
    2. Обновить баланс пользователя (добавить гадания или создать подписку)
    """
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                payments_table = get_table_name("payments")
                subscriptions_table = get_table_name("subscriptions")
                balances_table = get_table_name("user_balances")
                
                # Получаем информацию о платеже
                payment_query = f"""
                    SELECT user_id, package_id, amount, amount_rub
                    FROM {payments_table}
                    WHERE payment_id = $1
                """
                payment = await conn.fetchrow(payment_query, payment_id)
                
                if not payment:
                    logging.error(f"Payment not found: {payment_id}")
                    return False
                
                user_id = payment['user_id']
                package_id = payment['package_id']
                
                # Обновляем статус платежа
                await update_payment_status(payment_id, 'succeeded')
                
                # Обновляем баланс в зависимости от пакета
                if package_id == 'unlimited':
                    # Создаем подписку на 30 дней
                    expires_at = datetime.now() + timedelta(days=30)
                    
                    subscription_query = f"""
                        INSERT INTO {subscriptions_table} (user_id, payment_id, started_at, expires_at, is_active, created_at)
                        VALUES ($1, $2, NOW(), $3, TRUE, NOW())
                        ON CONFLICT DO NOTHING
                    """
                    await conn.execute(subscription_query, user_id, payment_id, expires_at)
                    
                    # Обновляем unlimited_until в балансе
                    balance_query = f"""
                        UPDATE {balances_table}
                        SET unlimited_until = $1,
                            updated_at = NOW()
                        WHERE user_id = $2
                    """
                    await conn.execute(balance_query, expires_at, user_id)
                    
                    logging.info(f"Unlimited subscription activated for user {user_id} until {expires_at}")
                else:
                    # Добавляем платные гадания
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

