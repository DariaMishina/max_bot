#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

usage() {
  cat <<'EOF'
Usage:
  restore_database_backup.sh --archive FILE --target-db NAME --confirm NAME [options]

Options:
  --archive FILE       Local .dump or .dump.age archive.
  --target-db NAME     Existing, preferably empty, PostgreSQL database.
  --confirm NAME       Must exactly match --target-db.
  --host HOST          PostgreSQL host (default: localhost).
  --port PORT          PostgreSQL port (default: 5432).
  --user USER          PostgreSQL user (default: current OS user).
  --identity FILE      age private identity for encrypted archives.
  --clean              Drop matching objects before restore (destructive).
  --help               Show this help.

The password is read by PostgreSQL from PGPASSWORD or ~/.pgpass. Production
database names are refused unless BACKUP_ALLOW_PRODUCTION_RESTORE=true.
EOF
}

fail() {
  printf 'restore_database_backup.sh: %s\n' "$*" >&2
  exit 1
}

archive=""
target_db=""
confirmation=""
db_host="localhost"
db_port="5432"
db_user="${USER:-}"
identity_file="${BACKUP_AGE_IDENTITY_FILE:-}"
clean=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive) archive=${2:-}; shift 2 ;;
    --target-db) target_db=${2:-}; shift 2 ;;
    --confirm) confirmation=${2:-}; shift 2 ;;
    --host) db_host=${2:-}; shift 2 ;;
    --port) db_port=${2:-}; shift 2 ;;
    --user) db_user=${2:-}; shift 2 ;;
    --identity) identity_file=${2:-}; shift 2 ;;
    --clean) clean=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

[[ -r "$archive" ]] || fail "Archive is not readable: $archive"
[[ -n "$target_db" ]] || fail "--target-db is required"
[[ "$confirmation" == "$target_db" ]] \
  || fail "--confirm must exactly match --target-db"
[[ -n "$db_user" ]] || fail "--user is required when USER is empty"

case "$target_db" in
  max_bot_db|app_bot_db|psy_bot_db|girl_bot_db)
    [[ "${BACKUP_ALLOW_PRODUCTION_RESTORE:-false}" == "true" ]] \
      || fail "Refusing production target $target_db"
    ;;
esac

command -v pg_restore >/dev/null 2>&1 || fail "pg_restore is not installed"

temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/db-restore-XXXXXXXX")"
trap 'find "$temp_dir" -type f -delete; rmdir "$temp_dir"' EXIT

dump_file="$archive"
if [[ "$archive" == *.age ]]; then
  command -v age >/dev/null 2>&1 || fail "age is not installed"
  [[ -r "$identity_file" ]] || fail "An age identity is required for encrypted archives"
  dump_file="$temp_dir/restore.dump"
  age --decrypt --identity "$identity_file" --output "$dump_file" "$archive"
fi

pg_restore --list "$dump_file" >/dev/null

restore_args=(
  --exit-on-error
  --no-owner
  --no-acl
  --host="$db_host"
  --port="$db_port"
  --username="$db_user"
  --dbname="$target_db"
)
if [[ "$clean" -eq 1 ]]; then
  restore_args+=(--clean --if-exists)
fi

pg_restore "${restore_args[@]}" "$dump_file"
printf 'Restore completed successfully into %s\n' "$target_db"
