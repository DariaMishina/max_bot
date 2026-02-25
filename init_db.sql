-- =============================================================================
-- Миграция БД для Max-бота (гадания)
-- Таблицы с префиксом max_ — живут в той же БД tg_bot_db рядом с Telegram-таблицами
-- Совместимо с PostgreSQL 13+
--
-- Запуск:
--   psql -U tg_bot_user -d tg_bot_db -f init_db.sql
-- =============================================================================

-- 1. max_users — профили пользователей Max
CREATE TABLE IF NOT EXISTS max_users (
    user_id         BIGINT PRIMARY KEY,
    username        VARCHAR(255),
    first_name      VARCHAR(255) NOT NULL,
    last_name       VARCHAR(255),
    full_name       VARCHAR(500) NOT NULL,
    email           VARCHAR(255),
    language_code   VARCHAR(10),
    is_premium      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW(),
    last_active_at  TIMESTAMP DEFAULT NOW(),
    is_blocked      BOOLEAN DEFAULT FALSE,
    daily_card_subscribed BOOLEAN NULL,
    client_id       VARCHAR(255) NULL,
    phone           VARCHAR(20) NULL,
    utm_source      VARCHAR(255) NULL,
    utm_campaign    VARCHAR(255) NULL,
    utm_content     VARCHAR(255) NULL,
    utm_medium      VARCHAR(255) NULL,
    utm_term        VARCHAR(255) NULL,
    first_visit_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_max_users_username    ON max_users(username);
CREATE INDEX IF NOT EXISTS idx_max_users_created_at  ON max_users(created_at);
CREATE INDEX IF NOT EXISTS idx_max_users_client_id   ON max_users(client_id);


-- 2. max_user_balances — баланс бесплатных / платных гаданий
CREATE TABLE IF NOT EXISTS max_user_balances (
    user_id                     BIGINT PRIMARY KEY REFERENCES max_users(user_id) ON DELETE CASCADE,
    free_divinations_remaining  INTEGER DEFAULT 3,
    paid_divinations_remaining  INTEGER DEFAULT 0,
    unlimited_until             TIMESTAMP,
    total_divinations_used      INTEGER DEFAULT 0,
    updated_at                  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_max_user_balances_unlimited_until ON max_user_balances(unlimited_until);


-- 3. max_payments — история платежей (ЮKassa)
CREATE TABLE IF NOT EXISTS max_payments (
    id                SERIAL PRIMARY KEY,
    payment_id        VARCHAR(255) UNIQUE NOT NULL,
    user_id           BIGINT NOT NULL REFERENCES max_users(user_id) ON DELETE CASCADE,
    package_id        VARCHAR(50) NOT NULL,
    amount            INTEGER NOT NULL,
    amount_rub        DECIMAL(10,2),
    status            VARCHAR(50) NOT NULL,
    email             VARCHAR(255),
    yookassa_metadata JSONB,
    created_at        TIMESTAMP DEFAULT NOW(),
    updated_at        TIMESTAMP DEFAULT NOW(),
    completed_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_max_payments_payment_id  ON max_payments(payment_id);
CREATE INDEX IF NOT EXISTS idx_max_payments_user_id     ON max_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_max_payments_status      ON max_payments(status);
CREATE INDEX IF NOT EXISTS idx_max_payments_created_at  ON max_payments(created_at);


-- 4. max_subscriptions — безлимитные подписки
CREATE TABLE IF NOT EXISTS max_subscriptions (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES max_users(user_id) ON DELETE CASCADE,
    payment_id  VARCHAR(255) NOT NULL,
    started_at  TIMESTAMP DEFAULT NOW(),
    expires_at  TIMESTAMP NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    auto_renew  BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_max_subscriptions_user_id    ON max_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_max_subscriptions_expires_at ON max_subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_max_subscriptions_is_active  ON max_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_max_subscriptions_user_active ON max_subscriptions(user_id, is_active);


-- 5. max_divinations — история гаданий
CREATE TABLE IF NOT EXISTS max_divinations (
    id               SERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES max_users(user_id) ON DELETE CASCADE,
    divination_type  VARCHAR(50) NOT NULL,
    question         TEXT NOT NULL,
    selected_cards   JSONB,
    interpretation   TEXT,
    is_free          BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_max_divinations_user_id      ON max_divinations(user_id);
CREATE INDEX IF NOT EXISTS idx_max_divinations_type          ON max_divinations(divination_type);
CREATE INDEX IF NOT EXISTS idx_max_divinations_created_at    ON max_divinations(created_at);
CREATE INDEX IF NOT EXISTS idx_max_divinations_user_created  ON max_divinations(user_id, created_at);


-- 6. max_conversions — аналитика воронки (Яндекс Директ + внутренняя)
CREATE TABLE IF NOT EXISTS max_conversions (
    id                    SERIAL PRIMARY KEY,
    user_id               BIGINT NOT NULL REFERENCES max_users(user_id) ON DELETE CASCADE,
    client_id             VARCHAR(255) NULL,
    conversion_type       VARCHAR(50) NOT NULL,
    conversion_value      DECIMAL(10,2) NULL,
    conversion_currency   VARCHAR(10) DEFAULT 'RUB',
    package_id            VARCHAR(50) NULL,
    divination_type       VARCHAR(50) NULL,
    conversion_datetime   TIMESTAMP NOT NULL DEFAULT NOW(),
    source                VARCHAR(255) NULL,
    campaign_id           VARCHAR(255) NULL,
    ad_id                 VARCHAR(255) NULL,
    metadata              JSONB NULL,
    exported_to_yandex    BOOLEAN DEFAULT FALSE,
    exported_at           TIMESTAMP NULL,
    created_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_max_conversions_user_id       ON max_conversions(user_id);
CREATE INDEX IF NOT EXISTS idx_max_conversions_client_id     ON max_conversions(client_id);
CREATE INDEX IF NOT EXISTS idx_max_conversions_type          ON max_conversions(conversion_type);
CREATE INDEX IF NOT EXISTS idx_max_conversions_datetime      ON max_conversions(conversion_datetime);
CREATE INDEX IF NOT EXISTS idx_max_conversions_exported      ON max_conversions(exported_to_yandex);
CREATE INDEX IF NOT EXISTS idx_max_conversions_user_datetime ON max_conversions(user_id, conversion_datetime);


-- Миграция для Яндекс Метрики Measurement Protocol (как в tg_bot, см. CONVERSIONS.md)
-- Добавляет колонки для кампании «Директ → бот». Без них get_user_metrika_client_id возвращает None.
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS yclid VARCHAR(255) NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS metrika_client_id VARCHAR(255) NULL;
CREATE INDEX IF NOT EXISTS idx_max_users_yclid ON max_users(yclid);


-- 7. max_webapp_follow_up_context — контекст уточняющих вопросов после WebApp-гадания (FSM недоступен из HTTP)
CREATE TABLE IF NOT EXISTS max_webapp_follow_up_context (
    user_id                   BIGINT PRIMARY KEY,
    divination_id             INTEGER NOT NULL,
    conversation_history      JSONB NOT NULL,
    follow_up_count           INTEGER NOT NULL DEFAULT 0,
    is_free                   BOOLEAN NOT NULL DEFAULT TRUE,
    original_interpretation   TEXT NOT NULL,
    created_at                TIMESTAMP DEFAULT NOW()
);


-- Готово!
-- Все таблицы создаются с IF NOT EXISTS — скрипт идемпотентен, можно запускать повторно.
-- Таблицы: max_users, max_user_balances, max_payments, max_subscriptions, max_divinations, max_conversions
