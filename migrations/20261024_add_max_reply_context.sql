CREATE TABLE IF NOT EXISTS max_reply_context (
    user_id BIGINT PRIMARY KEY,
    chat_id BIGINT NULL,
    last_user_message_id TEXT NULL,
    last_user_message_at TIMESTAMP NULL,
    last_conversation_message_id TEXT NULL,
    last_conversation_message_at TIMESTAMP NULL,
    last_callback_message_id TEXT NULL,
    last_callback_at TIMESTAMP NULL,
    last_bot_message_id TEXT NULL,
    last_bot_message_at TIMESTAMP NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
ALTER TABLE max_reply_context
    ADD COLUMN IF NOT EXISTS last_conversation_message_id TEXT NULL;
ALTER TABLE max_reply_context
    ADD COLUMN IF NOT EXISTS last_conversation_message_at TIMESTAMP NULL;

CREATE TABLE IF NOT EXISTS max_outbound_deliveries (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    user_id BIGINT NOT NULL,
    touch_type VARCHAR(80) NOT NULL,
    touch_stage VARCHAR(40) NULL,
    reply_message_id TEXT NULL,
    reply_source VARCHAR(32) NOT NULL,
    sent_as_reply BOOLEAN NOT NULL DEFAULT FALSE,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    api_result VARCHAR(80) NULL,
    error_code VARCHAR(80) NULL,
    outbound_message_id TEXT NULL,
    attempt SMALLINT NOT NULL DEFAULT 1,
    circuit_open BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_max_outbound_deliveries_created_at
    ON max_outbound_deliveries(created_at DESC);

ALTER TABLE max_payments ADD COLUMN IF NOT EXISTS reply_message_id TEXT NULL;
ALTER TABLE max_payments ADD COLUMN IF NOT EXISTS reply_source VARCHAR(32) NULL;
ALTER TABLE max_payments ADD COLUMN IF NOT EXISTS reply_context_at TIMESTAMP NULL;
