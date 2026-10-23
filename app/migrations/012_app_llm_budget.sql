-- Application-only DeepSeek circuit breaker. This table is never used by the Max bot.
BEGIN;
CREATE TABLE IF NOT EXISTS app_llm_requests (
    id           BIGSERIAL PRIMARY KEY,
    user_id      UUID NULL REFERENCES app_users(user_id) ON DELETE SET NULL,
    operation    VARCHAR(32) NOT NULL CHECK (operation IN ('tarot', 'follow_up')),
    status       VARCHAR(16) NOT NULL DEFAULT 'started'
                 CHECK (status IN ('started', 'succeeded', 'failed')),
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP NULL
);
CREATE INDEX IF NOT EXISTS idx_app_llm_requests_created
    ON app_llm_requests(created_at DESC);
COMMIT;
