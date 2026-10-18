-- Apply before deploying the API. Old decisions remain unknown: do not guess.
BEGIN;
ALTER TABLE app_trial_claims ADD COLUMN IF NOT EXISTS decision TEXT NULL;
COMMIT;
