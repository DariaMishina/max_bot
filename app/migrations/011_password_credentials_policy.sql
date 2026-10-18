-- Expand password-account logins without changing existing credentials.
-- Apply before deploying the API that accepts logins longer than 32 characters.
BEGIN;
ALTER TABLE app_password_credentials ALTER COLUMN login TYPE VARCHAR(64);
COMMIT;
