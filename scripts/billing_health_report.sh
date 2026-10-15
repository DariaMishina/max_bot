#!/usr/bin/env bash
set -Eeuo pipefail

project_root="${APP_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
env_file="${APP_ENV_FILE:-$project_root/.env}"
api_health_url="${APP_HEALTH_URL:-http://127.0.0.1:8083/health}"
cd "$project_root"

[[ -r "$env_file" ]] || { printf 'billing-health: cannot read %s\n' "$env_file" >&2; exit 1; }

read_env() {
  awk -v key="$1" 'index($0, key "=") == 1 {sub(/^[^=]*=/, ""); print; exit}' "$env_file"
}

db_host="$(read_env APP_DB_HOST)"
db_port="$(read_env APP_DB_PORT)"
db_name="$(read_env APP_DB_NAME)"
db_user="$(read_env APP_DB_USER)"
db_password="$(read_env APP_DB_PASSWORD)"

curl --fail --silent --show-error --max-time 5 "$api_health_url" | grep -qx 'OK'
printf 'billing-health: api=ok\n'

for required_key in \
  APP_RUSTORE_CONSOLE_APP_ID \
  APP_RUSTORE_KEY_ID \
  APP_RUSTORE_PRIVATE_KEY \
  APP_RUSTORE_CALLBACK_KEY; do
  [[ -n "$(read_env "$required_key")" ]] || {
    printf 'billing-health: missing configuration: %s\n' "$required_key" >&2
    exit 1
  }
done
printf 'billing-health: configuration=enabled\n'

PGPASSWORD="$db_password" psql \
  --host="$db_host" --port="$db_port" --username="$db_user" --dbname="$db_name" \
  --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 <<'SQL'
SELECT 'completed_payments_24h=' || COUNT(*)
FROM app_payments
WHERE provider = 'rustore' AND status = 'completed' AND completed_at >= NOW() - INTERVAL '24 hours';

SELECT 'revoked_payments_24h=' || COUNT(*)
FROM app_payments
WHERE provider = 'rustore' AND status = 'revoked' AND updated_at >= NOW() - INTERVAL '24 hours';

SELECT 'callbacks_24h=' || COUNT(*)
FROM app_payment_notifications
WHERE provider = 'rustore' AND received_at >= NOW() - INTERVAL '24 hours';
SQL

printf 'billing-health: PASS\n'
