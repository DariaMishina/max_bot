-- =============================================================================
-- Инициализация БД Android-приложения «Гадание AI»
--
-- Это НЕ миграция бота max_bot_db. Это отдельная пустая база app_bot_db.
-- Скрипт идемпотентен (CREATE IF NOT EXISTS) — можно запускать повторно.
--
-- Совместимо с PostgreSQL 13+
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Шаг 0. Создать пользователя и базу (один раз, от суперпользователя postgres)
-- Выполнять НЕ внутри app_bot_db, а в psql под postgres:
--
--   sudo -u postgres psql
--
--   CREATE USER app_bot_user WITH PASSWORD 'надёжный_пароль';
--   CREATE DATABASE app_bot_db OWNER app_bot_user;
--   GRANT ALL PRIVILEGES ON DATABASE app_bot_db TO app_bot_user;
--   \q
--
-- Шаг 1. Создать таблицы (под app_bot_user):
--
--   psql -U app_bot_user -d app_bot_db -h localhost -f init_app_db.sql
--
-- С Mac (если PostgreSQL слушает внешние подключения):
--
--   psql -U app_bot_user -d app_bot_db -h 46.16.36.243 -f init_app_db.sql
--
-- Проверка:
--
--   psql -U app_bot_user -d app_bot_db -h localhost -c "\dt app_*"
-- -----------------------------------------------------------------------------

-- 1. app_users — гости и (позже) пользователи с входом
CREATE TABLE IF NOT EXISTS app_users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_guest        BOOLEAN NOT NULL DEFAULT TRUE,
    install_id      VARCHAR(128) NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    last_active_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_install_id
    ON app_users(install_id)
    WHERE install_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_app_users_created_at
    ON app_users(created_at);


-- 2. app_user_balances — баланс раскладов
CREATE TABLE IF NOT EXISTS app_user_balances (
    user_id                     UUID PRIMARY KEY REFERENCES app_users(user_id) ON DELETE CASCADE,
    free_divinations_remaining  INTEGER NOT NULL DEFAULT 3,
    paid_divinations_remaining  INTEGER NOT NULL DEFAULT 0,
    unlimited_until             TIMESTAMP NULL,
    total_divinations_used      INTEGER NOT NULL DEFAULT 0,
    updated_at                  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_user_balances_unlimited_until
    ON app_user_balances(unlimited_until);


-- 3. app_payments — RuStore Pay и ЮKassa
CREATE TABLE IF NOT EXISTS app_payments (
    id                SERIAL PRIMARY KEY,
    payment_id        VARCHAR(255) NOT NULL,
    user_id           UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    package_id        VARCHAR(50) NOT NULL,
    amount            INTEGER NOT NULL,
    amount_rub        DECIMAL(10, 2) NULL,
    status            VARCHAR(50) NOT NULL,
    provider          VARCHAR(32) NOT NULL,
    email             VARCHAR(255) NULL,
    provider_metadata JSONB NULL,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMP NULL,
    UNIQUE (provider, payment_id)
);

CREATE INDEX IF NOT EXISTS idx_app_payments_user_id
    ON app_payments(user_id);

CREATE INDEX IF NOT EXISTS idx_app_payments_status
    ON app_payments(status);

CREATE INDEX IF NOT EXISTS idx_app_payments_created_at
    ON app_payments(created_at);


-- 4. app_subscriptions — безлимит на период
CREATE TABLE IF NOT EXISTS app_subscriptions (
    id          SERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    payment_id  VARCHAR(255) NOT NULL,
    provider    VARCHAR(32) NOT NULL,
    started_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMP NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_subscriptions_user_id
    ON app_subscriptions(user_id);

CREATE INDEX IF NOT EXISTS idx_app_subscriptions_expires_at
    ON app_subscriptions(expires_at);

CREATE INDEX IF NOT EXISTS idx_app_subscriptions_user_active
    ON app_subscriptions(user_id, is_active);


-- 5. app_divinations — история гаданий
CREATE TABLE IF NOT EXISTS app_divinations (
    id               SERIAL PRIMARY KEY,
    user_id          UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    divination_type  VARCHAR(50) NOT NULL,
    question         TEXT NOT NULL,
    selected_cards   JSONB NULL,
    interpretation   TEXT NULL,
    is_free          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_divinations_user_id
    ON app_divinations(user_id);

CREATE INDEX IF NOT EXISTS idx_app_divinations_created_at
    ON app_divinations(created_at);

CREATE INDEX IF NOT EXISTS idx_app_divinations_user_created
    ON app_divinations(user_id, created_at DESC);


-- 6. app_devices — push-токены RuStore (позже)
CREATE TABLE IF NOT EXISTS app_devices (
    id           SERIAL PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    push_token   VARCHAR(512) NOT NULL,
    platform     VARCHAR(32) NOT NULL DEFAULT 'android',
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, push_token)
);

CREATE INDEX IF NOT EXISTS idx_app_devices_user_id
    ON app_devices(user_id);


-- 7. app_conversions — воронка приложения (аналитика)
CREATE TABLE IF NOT EXISTS app_conversions (
    id                  SERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    conversion_type     VARCHAR(50) NOT NULL,
    conversion_value    DECIMAL(10, 2) NULL,
    conversion_currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    package_id          VARCHAR(50) NULL,
    divination_type     VARCHAR(50) NULL,
    pay_provider        VARCHAR(32) NULL,
    metadata            JSONB NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_conversions_user_id
    ON app_conversions(user_id);

CREATE INDEX IF NOT EXISTS idx_app_conversions_type
    ON app_conversions(conversion_type);

CREATE INDEX IF NOT EXISTS idx_app_conversions_created_at
    ON app_conversions(created_at);


-- 8. app_refresh_tokens — JWT refresh (гостевые сессии)
CREATE TABLE IF NOT EXISTS app_refresh_tokens (
    id           SERIAL PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    token_hash   VARCHAR(128) NOT NULL UNIQUE,
    expires_at   TIMESTAMP NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    revoked_at   TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_app_refresh_tokens_user_id
    ON app_refresh_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_app_refresh_tokens_expires_at
    ON app_refresh_tokens(expires_at);


-- app_user_identities (VK / Яндекс / почта) — этап 8, не MVP.
-- Раскомментировать при добавлении входов:
--
-- CREATE TABLE IF NOT EXISTS app_user_identities (
--     id                SERIAL PRIMARY KEY,
--     user_id           UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
--     provider          VARCHAR(32) NOT NULL,
--     provider_user_id  VARCHAR(255) NOT NULL,
--     created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
--     UNIQUE (provider, provider_user_id)
-- );
--
-- CREATE INDEX IF NOT EXISTS idx_app_user_identities_user_id
--     ON app_user_identities(user_id);
-- Apply only to app_bot_db. Safe to re-run; the Max bot database is untouched.
BEGIN;
ALTER TABLE app_divinations ADD COLUMN IF NOT EXISTS request_id UUID NULL;
ALTER TABLE app_divinations ADD COLUMN IF NOT EXISTS follow_ups JSONB NOT NULL DEFAULT '[]'::jsonb;
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_divinations_request
    ON app_divinations(user_id, request_id) WHERE request_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS app_feedback (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    message TEXT NOT NULL CHECK (char_length(message) BETWEEN 1 AND 2000),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_app_feedback_user ON app_feedback(user_id);
COMMIT;
