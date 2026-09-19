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
