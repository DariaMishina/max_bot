-- =============================================================================
-- Миграция: автоматические напоминания о незавершённой оплате (10м / 1ч / 3ч)
--
-- Запуск перед деплоем (prod):
--   psql -U tg_bot_user -d tg_bot_db -f migrations/20260530_payment_reminders.sql
--
-- Если используется тестовый суффикс таблиц (DB_TABLE_SUFFIX=_test),
-- замените max_payments на max_payments_test в командах ниже.
-- =============================================================================

ALTER TABLE max_payments ADD COLUMN IF NOT EXISTS reminder_10m_sent_at TIMESTAMP NULL;
ALTER TABLE max_payments ADD COLUMN IF NOT EXISTS reminder_1h_sent_at  TIMESTAMP NULL;
ALTER TABLE max_payments ADD COLUMN IF NOT EXISTS reminder_3h_sent_at  TIMESTAMP NULL;

-- Старые pending/canceled не должны получить рассылку при первом деплое фичи
UPDATE max_payments
SET reminder_10m_sent_at = COALESCE(reminder_10m_sent_at, NOW()),
    reminder_1h_sent_at  = COALESCE(reminder_1h_sent_at, NOW()),
    reminder_3h_sent_at  = COALESCE(reminder_3h_sent_at, NOW()),
    updated_at = NOW()
WHERE status IN ('pending', 'canceled');

-- Проверка (опционально):
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'max_payments'
--   AND column_name LIKE 'reminder_%';
