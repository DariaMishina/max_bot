-- Apply only to app_bot_db. Stage 4.7: confirmed accounts and one-time trial.
BEGIN;

ALTER TABLE app_user_balances
    ALTER COLUMN free_divinations_remaining SET DEFAULT 0;

CREATE TABLE IF NOT EXISTS app_user_identities (
    id                BIGSERIAL PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    provider          VARCHAR(32) NOT NULL,
    provider_user_id  VARCHAR(320) NOT NULL,
    display_value     VARCHAR(320) NULL,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_user_id),
    UNIQUE (user_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_app_user_identities_user_id
    ON app_user_identities(user_id);

CREATE TABLE IF NOT EXISTS app_email_codes (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(320) NOT NULL,
    code_hash       VARCHAR(64) NOT NULL,
    request_ip_hash VARCHAR(64) NULL,
    device_hash     VARCHAR(64) NULL,
    attempts        SMALLINT NOT NULL DEFAULT 0,
    expires_at      TIMESTAMP NOT NULL,
    consumed_at     TIMESTAMP NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_app_email_codes_lookup
    ON app_email_codes(email, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_email_codes_expiry
    ON app_email_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_app_email_codes_ip_created
    ON app_email_codes(request_ip_hash, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_email_codes_device_created
    ON app_email_codes(device_hash, created_at DESC);

-- Claims deliberately survive account deletion. This prevents delete/re-register
-- from issuing another trial to the same confirmed identity or device.
CREATE TABLE IF NOT EXISTS app_trial_claims (
    id                 BIGSERIAL PRIMARY KEY,
    identity_key       VARCHAR(384) NOT NULL UNIQUE,
    device_hash        VARCHAR(64) NULL UNIQUE,
    claimed_user_id    UUID NULL REFERENCES app_users(user_id) ON DELETE SET NULL,
    granted_amount     SMALLINT NOT NULL DEFAULT 0,
    created_at         TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_app_trial_claims_user_id
    ON app_trial_claims(claimed_user_id);

COMMIT;
