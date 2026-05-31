-- =============================================================================
-- Миграция: welcome-активация + сегментированная Пн/Чт рассылка
--
-- activation_sent_at              — когда отправлена welcome-активация (1 раз)
-- last_div_reminder_broadcast_at  — когда отправлена последняя Пн/Чт рассылка
--
-- Запуск перед деплоем (prod):
--   psql -U tg_bot_user -d tg_bot_db -f migrations/20260531_broadcasts.sql
--
-- Если используется тестовый суффикс таблиц (DB_TABLE_SUFFIX=_test),
-- замените max_users / max_divinations на max_users_test / max_divinations_test.
-- =============================================================================

ALTER TABLE max_users ADD COLUMN IF NOT EXISTS activation_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS last_div_reminder_broadcast_at TIMESTAMP NULL;

CREATE INDEX IF NOT EXISTS idx_max_users_activation_sent_at
    ON max_users(activation_sent_at)
    WHERE activation_sent_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_max_users_last_div_reminder_broadcast_at
    ON max_users(last_div_reminder_broadcast_at);

-- Anti-spam: не слать активацию «задним числом» пользователям старше 7 дней без гаданий
UPDATE max_users u
SET activation_sent_at = NOW()
WHERE activation_sent_at IS NULL
  AND created_at < NOW() - INTERVAL '7 days'
  AND NOT EXISTS (
      SELECT 1 FROM max_divinations d WHERE d.user_id = u.user_id
  );
