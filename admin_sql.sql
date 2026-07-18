-- =============================================================================
-- Admin SQL для Max-бота (max_bot) — гадания / расклады
-- Таблицы prod: max_*
-- Таблицы test: max_*_test (замени имена вручную, если нужно)
--
-- ⚠️  НЕ запускай файл целиком через \i.
--     Копируй один блок между маркерами -- >>> / -- <<< в psql.
--
-- Запуск:
--   psql -U max_bot_user -d max_bot_db -h HOST
--
-- Пакеты (как в handlers/pay.py):
--   3_spreads → +3, 10_spreads → +10, 20_spreads → +20, 30_spreads → +30
--   unlimited → безлимит на 30 дней
-- Стартовый бесплатный баланс: 3 расклада
-- =============================================================================


-- =============================================================================
-- 0. Проверка баланса / подписки
-- =============================================================================

/*
-- >>> COPY 0
SELECT
    u.user_id,
    u.full_name,
    ub.free_divinations_remaining,
    ub.paid_divinations_remaining,
    ub.unlimited_until,
    ub.total_divinations_used,
    s.expires_at AS sub_expires_at,
    s.is_active  AS sub_is_active,
    s.payment_id AS sub_payment_id
FROM max_users u
LEFT JOIN max_user_balances ub ON ub.user_id = u.user_id
LEFT JOIN max_subscriptions s ON s.user_id = u.user_id AND s.is_active = TRUE
WHERE u.user_id = 129045679;
-- <<< COPY 0
*/


-- =============================================================================
-- 1. Безлимитная подписка
-- =============================================================================

-- --- 1a. До 9999 года (одному пользователю) ---

/*
-- >>> COPY 1a
BEGIN;

-- Чинит sequence, если она отстаёт от MAX(id) (иначе duplicate key на id)
SELECT setval(
    pg_get_serial_sequence('max_subscriptions', 'id'),
    COALESCE((SELECT MAX(id) FROM max_subscriptions), 1)
);

UPDATE max_subscriptions
SET is_active = FALSE
WHERE user_id = 129045679
  AND is_active = TRUE;

INSERT INTO max_subscriptions (user_id, payment_id, started_at, expires_at, is_active, created_at)
VALUES (129045679, 'manual_grant_9999', NOW(), '9999-12-31 23:59:59', TRUE, NOW());

INSERT INTO max_user_balances (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
VALUES (129045679, 0, 0, NOW())
ON CONFLICT (user_id) DO NOTHING;

UPDATE max_user_balances
SET unlimited_until = '9999-12-31 23:59:59',
    updated_at = NOW()
WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 1a
*/


-- --- 1b. На 30 дней (как пакет unlimited) ---

/*
-- >>> COPY 1b
BEGIN;

SELECT setval(
    pg_get_serial_sequence('max_subscriptions', 'id'),
    COALESCE((SELECT MAX(id) FROM max_subscriptions), 1)
);

UPDATE max_subscriptions
SET is_active = FALSE
WHERE user_id = 129045679
  AND is_active = TRUE;

INSERT INTO max_subscriptions (user_id, payment_id, started_at, expires_at, is_active, created_at)
VALUES (129045679, 'manual_grant_30d', NOW(), NOW() + INTERVAL '30 days', TRUE, NOW());

INSERT INTO max_user_balances (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
VALUES (129045679, 0, 0, NOW())
ON CONFLICT (user_id) DO NOTHING;

UPDATE max_user_balances
SET unlimited_until = NOW() + INTERVAL '30 days',
    updated_at = NOW()
WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 1b
*/


-- --- 1c. Нескольким пользователям (до 9999) ---

/*
-- >>> COPY 1c
BEGIN;

SELECT setval(
    pg_get_serial_sequence('max_subscriptions', 'id'),
    COALESCE((SELECT MAX(id) FROM max_subscriptions), 1)
);

UPDATE max_subscriptions
SET is_active = FALSE
WHERE user_id IN (3260473, 129045679, 200748988)
  AND is_active = TRUE;

INSERT INTO max_subscriptions (user_id, payment_id, started_at, expires_at, is_active, created_at)
VALUES
    (3260473,   'manual_grant_9999', NOW(), '9999-12-31 23:59:59', TRUE, NOW()),
    (129045679, 'manual_grant_9999', NOW(), '9999-12-31 23:59:59', TRUE, NOW()),
    (200748988, 'manual_grant_9999', NOW(), '9999-12-31 23:59:59', TRUE, NOW());

INSERT INTO max_user_balances (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
SELECT uid, 0, 0, NOW()
FROM unnest(ARRAY[3260473, 129045679, 200748988]::BIGINT[]) AS uid
ON CONFLICT (user_id) DO NOTHING;

UPDATE max_user_balances
SET unlimited_until = '9999-12-31 23:59:59',
    updated_at = NOW()
WHERE user_id IN (3260473, 129045679, 200748988);

COMMIT;
-- <<< COPY 1c
*/


-- --- 1d. Сброс / отзыв подписки ---

/*
-- >>> COPY 1d
BEGIN;

UPDATE max_subscriptions
SET is_active = FALSE
WHERE user_id = 129045679
  AND is_active = TRUE;

UPDATE max_user_balances
SET unlimited_until = NULL,
    updated_at = NOW()
WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 1d
*/


-- =============================================================================
-- 2. Бесплатные расклады
-- =============================================================================

-- --- 2a. Выставить ровно N бесплатных (например 3 — стартовый баланс) ---

/*
-- >>> COPY 2a
BEGIN;

INSERT INTO max_user_balances (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
VALUES (129045679, 3, 0, NOW())
ON CONFLICT (user_id) DO NOTHING;

UPDATE max_user_balances
SET free_divinations_remaining = 3,  -- ← нужное число
    updated_at = NOW()
WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 2a
*/


-- --- 2b. Добавить +N бесплатных к текущему балансу ---

/*
-- >>> COPY 2b
BEGIN;

INSERT INTO max_user_balances (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
VALUES (129045679, 0, 0, NOW())
ON CONFLICT (user_id) DO NOTHING;

UPDATE max_user_balances
SET free_divinations_remaining = free_divinations_remaining + 3,  -- ← сколько добавить
    updated_at = NOW()
WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 2b
*/


-- --- 2c. Обнулить бесплатные ---

/*
-- >>> COPY 2c
UPDATE max_user_balances
SET free_divinations_remaining = 0,
    updated_at = NOW()
WHERE user_id = 129045679;
-- <<< COPY 2c
*/


-- =============================================================================
-- 3. Платные расклады
-- =============================================================================

-- --- 3a. Добавить пакет (3 / 10 / 20 / 30) ---

/*
-- >>> COPY 3a
BEGIN;

INSERT INTO max_user_balances (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
VALUES (129045679, 0, 0, NOW())
ON CONFLICT (user_id) DO NOTHING;

UPDATE max_user_balances
SET paid_divinations_remaining = paid_divinations_remaining + 10,  -- 3 | 10 | 20 | 30
    updated_at = NOW()
WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 3a
*/


-- --- 3b. Выставить ровно N платных ---

/*
-- >>> COPY 3b
BEGIN;

INSERT INTO max_user_balances (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
VALUES (129045679, 0, 0, NOW())
ON CONFLICT (user_id) DO NOTHING;

UPDATE max_user_balances
SET paid_divinations_remaining = 20,  -- ← нужное число
    updated_at = NOW()
WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 3b
*/


-- --- 3c. Обнулить платные ---

/*
-- >>> COPY 3c
UPDATE max_user_balances
SET paid_divinations_remaining = 0,
    updated_at = NOW()
WHERE user_id = 129045679;
-- <<< COPY 3c
*/


-- --- 3d. Нескольким пользователям добавить платные ---

/*
-- >>> COPY 3d
BEGIN;

INSERT INTO max_user_balances (user_id, free_divinations_remaining, paid_divinations_remaining, updated_at)
SELECT uid, 0, 0, NOW()
FROM unnest(ARRAY[3260473, 129045679]::BIGINT[]) AS uid
ON CONFLICT (user_id) DO NOTHING;

UPDATE max_user_balances
SET paid_divinations_remaining = paid_divinations_remaining + 10,
    updated_at = NOW()
WHERE user_id IN (3260473, 129045679);

COMMIT;
-- <<< COPY 3d
*/


-- =============================================================================
-- 4. Полный сброс доступа (подписка + расклады, профиль остаётся)
-- =============================================================================
-- Обнуляет безлимит, бесплатные и платные. История гаданий/платежей не трогается.

/*
-- >>> COPY 4
BEGIN;

UPDATE max_subscriptions
SET is_active = FALSE
WHERE user_id = 129045679
  AND is_active = TRUE;

UPDATE max_user_balances
SET free_divinations_remaining = 0,
    paid_divinations_remaining = 0,
    unlimited_until = NULL,
    updated_at = NOW()
WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 4
*/


-- =============================================================================
-- 5. Полная очистка пользователя (сброс всего)
-- =============================================================================
-- Удаляет профиль и всю историю. После — /start, пользователь создаётся заново.
-- Замени 129045679 на нужный user_id (везде одно число).
-- test_mode → таблицы max_*_test.

-- >>> COPY 5
BEGIN;

DELETE FROM max_webapp_follow_up_context WHERE user_id = 129045679;
DELETE FROM max_conversions             WHERE user_id = 129045679;
DELETE FROM max_divinations             WHERE user_id = 129045679;
DELETE FROM max_payments                WHERE user_id = 129045679;
DELETE FROM max_subscriptions           WHERE user_id = 129045679;
DELETE FROM max_user_balances           WHERE user_id = 129045679;
DELETE FROM max_users                   WHERE user_id = 129045679;

COMMIT;
-- <<< COPY 5


-- --- 5a. Проверка (все COUNT = 0) ---

-- >>> COPY 5a
SELECT 'max_users' AS tbl, COUNT(*) FROM max_users WHERE user_id = 129045679
UNION ALL SELECT 'max_user_balances', COUNT(*) FROM max_user_balances WHERE user_id = 129045679
UNION ALL SELECT 'max_subscriptions', COUNT(*) FROM max_subscriptions WHERE user_id = 129045679
UNION ALL SELECT 'max_divinations', COUNT(*) FROM max_divinations WHERE user_id = 129045679
UNION ALL SELECT 'max_payments', COUNT(*) FROM max_payments WHERE user_id = 129045679
UNION ALL SELECT 'max_conversions', COUNT(*) FROM max_conversions WHERE user_id = 129045679
UNION ALL SELECT 'max_webapp_follow_up_context', COUNT(*) FROM max_webapp_follow_up_context WHERE user_id = 129045679;
-- <<< COPY 5a


-- =============================================================================
-- 6. Сброс только подписки на канал (чтобы снова спросить подписку)
-- =============================================================================

/*
-- >>> COPY 6
UPDATE max_users
SET channel_subscribed_at = NULL
WHERE user_id = 129045679;
-- <<< COPY 6
*/
