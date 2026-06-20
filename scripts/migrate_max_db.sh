#!/usr/bin/env bash
# =============================================================================
# Миграция таблиц max_* в max_bot_db на 46.16.36.243.
# psy_bot_db не трогаем — перед первым прогоном сделайте бэкап psy (см. docs/MIGRATION_TO_46.16.36.243.md §2.0).
#
# Запуск с Mac:
#   export OLD_DB_PASSWORD='...'
#   export NEW_DB_PASSWORD='...'   # max_bot_user
#   export PSY_DB_PASSWORD='...'   # опционально, psy_bot_user — проверка psy после миграции
#   ./scripts/migrate_max_db.sh [--dry-run] [--final]
# =============================================================================
set -euo pipefail

OLD_HOST="${OLD_HOST:-35.234.89.2}"
NEW_HOST="${NEW_HOST:-46.16.36.243}"
SSH_USER="${SSH_USER:-dariamishina}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_deploy}"

OLD_DB_NAME="${OLD_DB_NAME:-tg_bot_db}"
OLD_DB_USER="${OLD_DB_USER:-tg_bot_user}"

NEW_DB_NAME="${NEW_DB_NAME:-max_bot_db}"
NEW_DB_USER="${NEW_DB_USER:-max_bot_user}"
DB_PORT="${DB_PORT:-5432}"

PSY_DB_USER="${PSY_DB_USER:-psy_bot_user}"
PSY_DB_PASSWORD="${PSY_DB_PASSWORD:-}"

PROJECT_DIR="${PROJECT_DIR:-/home/dariamishina/max_bot}"
DUMP_FILE="${DUMP_FILE:-/tmp/max_bot_tables_$(date +%Y%m%d_%H%M%S).dump}"

# Порядок важен: родительские таблицы раньше дочерних
RESTORE_TABLES=(
  max_users
  max_user_balances
  max_payments
  max_subscriptions
  max_divinations
  max_conversions
  max_pending_questions
  max_webapp_follow_up_context
)

# Отдельная БД max_bot_db — можно очистить все таблицы max_bot
TRUNCATE_TABLES=(
  max_webapp_follow_up_context
  max_pending_questions
  max_conversions
  max_divinations
  max_subscriptions
  max_payments
  max_user_balances
  max_users
)

DRY_RUN=0
FINAL=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --final) FINAL=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "Неизвестный аргумент: $arg" >&2; exit 1 ;;
  esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

require_cmd() {
  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      error "Не найдена команда: $cmd"
      exit 1
    fi
  done
}

require_cmd psql pg_dump pg_restore ssh scp

if [[ -z "${OLD_DB_PASSWORD:-}" ]]; then
  error "Задайте OLD_DB_PASSWORD (tg_bot_user на $OLD_HOST)"
  exit 1
fi
if [[ -z "${NEW_DB_PASSWORD:-}" ]]; then
  error "Задайте NEW_DB_PASSWORD (max_bot_user на $NEW_HOST)"
  exit 1
fi

SSH_OPTS=(-i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

remote() {
  ssh "${SSH_OPTS[@]}" "${SSH_USER}@${NEW_HOST}" "$@"
}

psql_old() {
  PGPASSWORD="$OLD_DB_PASSWORD" PGSSLMODE="${PGSSLMODE:-disable}" \
    psql -h "$OLD_HOST" -p "$DB_PORT" -U "$OLD_DB_USER" -d "$OLD_DB_NAME" "$@"
}

count_query="
SELECT 'max_users' AS t, COUNT(*)::text FROM max_users
UNION ALL SELECT 'max_user_balances', COUNT(*)::text FROM max_user_balances
UNION ALL SELECT 'max_divinations', COUNT(*)::text FROM max_divinations
UNION ALL SELECT 'max_payments', COUNT(*)::text FROM max_payments
UNION ALL SELECT 'max_subscriptions', COUNT(*)::text FROM max_subscriptions
UNION ALL SELECT 'max_conversions', COUNT(*)::text FROM max_conversions
UNION ALL SELECT 'max_pending_questions', COUNT(*)::text FROM max_pending_questions
UNION ALL SELECT 'max_webapp_follow_up_context', COUNT(*)::text FROM max_webapp_follow_up_context
ORDER BY 1;
"

info "=== Проверка SSH ($SSH_USER@$NEW_HOST) ==="
remote "whoami"

info "=== Источник: $OLD_HOST / $OLD_DB_NAME ==="
psql_old -c "SELECT current_database(), current_user;" | head -5
info "Счётчики на старом сервере (эталон):"
psql_old -c "$count_query"

info "=== Назначение: $NEW_HOST / $NEW_DB_NAME ==="
if ! remote "PGPASSWORD='$NEW_DB_PASSWORD' psql -h localhost -p $DB_PORT -U $NEW_DB_USER -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$NEW_DB_NAME'\"" | grep -q 1; then
  error "БД $NEW_DB_NAME не найдена. Создайте: CREATE DATABASE $NEW_DB_NAME OWNER $NEW_DB_USER;"
  exit 1
fi

remote "PGPASSWORD='$NEW_DB_PASSWORD' psql -h localhost -p $DB_PORT -U $NEW_DB_USER -d $NEW_DB_NAME -c \"SELECT current_database(), current_user;\"" \
  || { error "Не удалось подключиться к $NEW_DB_NAME. Проверьте NEW_DB_PASSWORD."; exit 1; }

if [[ "$FINAL" -eq 1 ]]; then
  warn "Режим --final: убедитесь, что max-bot.service остановлен на $OLD_HOST"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  info "Dry-run: дамп/restore пропущены"
  exit 0
fi

warn "Убедитесь, что сделан бэкап psy_bot_db (docs/MIGRATION_TO_46.16.36.243.md §2.0)"

info "=== Дамп max_* со старого сервера ==="
PGPASSWORD="$OLD_DB_PASSWORD" PGSSLMODE="${PGSSLMODE:-disable}" pg_dump \
  -h "$OLD_HOST" -p "$DB_PORT" -U "$OLD_DB_USER" -d "$OLD_DB_NAME" \
  -t 'max_users' \
  -t 'max_user_balances' \
  -t 'max_payments' \
  -t 'max_subscriptions' \
  -t 'max_divinations' \
  -t 'max_conversions' \
  -t 'max_pending_questions' \
  -t 'max_webapp_follow_up_context' \
  --no-owner --no-acl \
  -F c -f "$DUMP_FILE"

info "Дамп: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

info "=== Копирование на $NEW_HOST ==="
scp "${SSH_OPTS[@]}" "$DUMP_FILE" "${SSH_USER}@${NEW_HOST}:/tmp/max_bot_restore.dump"

info "=== init_db.sql + max_pending_questions ==="
remote "mkdir -p '$PROJECT_DIR'"
if ! remote "test -f '$PROJECT_DIR/init_db.sql'"; then
  remote "git clone https://github.com/DariaMishina/max_bot.git '$PROJECT_DIR'"
fi

remote "PGPASSWORD='$NEW_DB_PASSWORD' psql -h localhost -U $NEW_DB_USER -d $NEW_DB_NAME -f '$PROJECT_DIR/init_db.sql'"

remote "PGPASSWORD='$NEW_DB_PASSWORD' psql -h localhost -U $NEW_DB_USER -d $NEW_DB_NAME" <<'EOSQL'
CREATE TABLE IF NOT EXISTS max_pending_questions (
    user_id BIGINT PRIMARY KEY,
    question TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
EOSQL

info "=== Очистка таблиц max_bot в $NEW_DB_NAME ==="
truncate_sql=""
for t in "${TRUNCATE_TABLES[@]}"; do
  truncate_sql+="TRUNCATE TABLE ${t} RESTART IDENTITY CASCADE;"
done
remote "PGPASSWORD='$NEW_DB_PASSWORD' psql -h localhost -U $NEW_DB_USER -d $NEW_DB_NAME -c \"$truncate_sql\""

info "=== Восстановление данных (по таблицам, в порядке FK) ==="
restore_errors=0
for t in "${RESTORE_TABLES[@]}"; do
  info "  → $t"
  if ! remote "PGPASSWORD='$NEW_DB_PASSWORD' pg_restore -h localhost -U $NEW_DB_USER -d $NEW_DB_NAME \
    --no-owner --no-acl --data-only -t '$t' /tmp/max_bot_restore.dump 2>&1"; then
    error "  Ошибка restore для $t"
    restore_errors=$((restore_errors + 1))
  fi
done

if [[ "$restore_errors" -gt 0 ]]; then
  error "Restore завершился с $restore_errors ошибками"
  exit 1
fi

info "=== Синхронизация sequences (pg_restore --data-only не обновляет serial) ==="
remote "PGPASSWORD='$NEW_DB_PASSWORD' psql -h localhost -U $NEW_DB_USER -d $NEW_DB_NAME" <<'EOSQL'
SELECT setval('max_payments_id_seq', COALESCE((SELECT MAX(id) FROM max_payments), 1));
SELECT setval('max_divinations_id_seq', COALESCE((SELECT MAX(id) FROM max_divinations), 1));
SELECT setval('max_conversions_id_seq', COALESCE((SELECT MAX(id) FROM max_conversions), 1));
EOSQL

info "=== Сверка на новом сервере ($NEW_DB_NAME) ==="
remote "PGPASSWORD='$NEW_DB_PASSWORD' psql -h localhost -U $NEW_DB_USER -d $NEW_DB_NAME -c \"$count_query\""

info "=== psy_bot_db не трогали — быстрая проверка psy_max ==="
if [[ -n "$PSY_DB_PASSWORD" ]]; then
  remote "PGPASSWORD='$PSY_DB_PASSWORD' psql -h localhost -U $PSY_DB_USER -d psy_bot_db -c \"
SELECT COUNT(*) AS psy_sessions FROM max_sessions;
\"" || warn "psy_bot_db недоступна — проверьте psy_max вручную"
else
  warn "PSY_DB_PASSWORD не задан — пропускаем проверку psy_bot_db"
fi

info "=== Готово ==="
if [[ "$FINAL" -eq 0 ]]; then
  warn "Пробный перенос. Cutover: stop max-bot на $OLD_HOST → ./scripts/migrate_max_db.sh --final"
fi
