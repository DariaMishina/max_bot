-- Apply only to app_bot_db. Stage 5: idempotent RuStore entitlements.
BEGIN;

ALTER TABLE app_payments
    ADD COLUMN IF NOT EXISTS invoice_id VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS revoked_amount INTEGER NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX IF NOT EXISTS idx_app_payments_rustore_invoice
    ON app_payments(provider, invoice_id)
    WHERE invoice_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_app_subscriptions_provider_payment
    ON app_subscriptions(provider, payment_id);

CREATE TABLE IF NOT EXISTS app_payment_notifications (
    provider        VARCHAR(32) NOT NULL,
    notification_id VARCHAR(255) NOT NULL,
    received_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (provider, notification_id)
);

COMMIT;
