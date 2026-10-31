-- WebApp readings, history annotations, daily card and purchases.
-- Idempotent. Adds tables and one nullable column; existing rows stay in place.
-- Apply manually after init_db.sql and earlier files in migrations/.
-- Do not run against the Android database.

CREATE TABLE IF NOT EXISTS max_webapp_operations (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES max_users(user_id),
    fingerprint TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    result_id INTEGER,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS max_webapp_one_active
    ON max_webapp_operations(user_id) WHERE status = 'queued';

ALTER TABLE max_divinations ADD COLUMN IF NOT EXISTS webapp_theme TEXT DEFAULT 'timeline';

CREATE TABLE IF NOT EXISTS max_webapp_followups (
    id BIGSERIAL PRIMARY KEY,
    reading_id INTEGER NOT NULL REFERENCES max_divinations(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS max_webapp_daily (
    user_id BIGINT NOT NULL REFERENCES max_users(user_id),
    day DATE NOT NULL,
    choices JSONB NOT NULL,
    selected TEXT,
    PRIMARY KEY (user_id, day)
);

CREATE TABLE IF NOT EXISTS max_webapp_annotations (
    reading_id INTEGER PRIMARY KEY REFERENCES max_divinations(id) ON DELETE CASCADE,
    favorite BOOLEAN NOT NULL DEFAULT false,
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS max_webapp_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES max_users(user_id),
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS max_webapp_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES max_users(user_id),
    event TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS max_webapp_purchases (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES max_users(user_id),
    package TEXT NOT NULL,
    email TEXT NOT NULL,
    payment_id TEXT,
    confirmation_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
