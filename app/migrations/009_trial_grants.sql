-- Apply to the app database before deploying welcome gift protection.
-- Existing claims (including deleted accounts) must remain intact.
BEGIN;
CREATE INDEX IF NOT EXISTS idx_app_trial_claims_granted_created
    ON app_trial_claims(created_at) WHERE granted_amount > 0;
-- Older code did not save an identity when its device was already claimed.
-- Preserve those existing identities before they can be deleted and recreated.
INSERT INTO app_trial_claims (identity_key, claimed_user_id, granted_amount)
SELECT provider || ':' || provider_user_id, user_id, 0
FROM app_user_identities
ON CONFLICT (identity_key) DO NOTHING;
COMMIT;
