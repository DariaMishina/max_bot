-- Apply to the app database before deploying password authentication.
BEGIN;
CREATE TABLE IF NOT EXISTS app_password_credentials (
    login VARCHAR(32) PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE REFERENCES app_users(user_id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS app_password_limits (
    bucket VARCHAR(64) PRIMARY KEY,
    attempts INTEGER NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_password_limits_expiry ON app_password_limits(expires_at);
COMMIT;
