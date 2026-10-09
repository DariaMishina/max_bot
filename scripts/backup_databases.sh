#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

readonly SCRIPT_NAME="${0##*/}"
readonly DEFAULT_PROJECT_ROOT="/home/dariamishina/max_bot"
readonly DEFAULT_PSY_ENV="/home/dariamishina/psy_max/.env"
readonly DEFAULT_GIRL_ENV="/home/dariamishina/girl_max/.env"

success=0
run_dir=""

log() {
  printf '%s [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SCRIPT_NAME" "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

on_error() {
  local exit_code=$1
  local line=$2
  log "Backup failed at line $line (exit $exit_code)"
  if [[ -n "${BACKUP_FAILURE_HEARTBEAT_URL:-}" ]]; then
    curl --fail --silent --show-error --max-time 15 \
      "${BACKUP_FAILURE_HEARTBEAT_URL}" >/dev/null || true
  fi
  exit "$exit_code"
}

cleanup() {
  if [[ -z "$run_dir" || ! -d "$run_dir" ]]; then
    return
  fi

  if [[ "$success" -eq 1 ]]; then
    find "$run_dir" -type f -delete
    rmdir "$run_dir"
  else
    log "Failed run retained for inspection: $run_dir"
  fi
}

trap 'on_error $? $LINENO' ERR
trap cleanup EXIT

require_command() {
  local command_name
  for command_name in "$@"; do
    command -v "$command_name" >/dev/null 2>&1 \
      || fail "Required command not found: $command_name"
  done
}

require_variable() {
  local variable_name=$1
  [[ -n "${!variable_name:-}" ]] || fail "Required variable is empty: $variable_name"
}

read_env_value() {
  local env_file=$1
  local key=$2
  local value

  [[ -r "$env_file" ]] || fail "Cannot read environment file: $env_file"
  value="$({
    awk -v wanted="$key" '
      index($0, wanted "=") == 1 {
        sub(/^[^=]*=/, "")
        sub(/\r$/, "")
        print
        found = 1
        exit
      }
      END { if (!found) exit 1 }
    ' "$env_file"
  } 2>/dev/null)" || fail "Variable $key not found in $env_file"

  [[ -n "$value" ]] || fail "Variable $key is empty in $env_file"
  printf '%s' "$value"
}

dump_database() {
  local env_file=$1
  local prefix=$2
  local expected_name=$3
  local name user password host port dump_file

  if [[ "$prefix" == "DB" ]]; then
    name="$(read_env_value "$env_file" DB_NAME)"
    user="$(read_env_value "$env_file" DB_USER)"
    password="$(read_env_value "$env_file" DB_PASSWORD)"
    host="$(read_env_value "$env_file" DB_HOST)"
    port="$(read_env_value "$env_file" DB_PORT)"
  else
    name="$(read_env_value "$env_file" APP_DB_NAME)"
    user="$(read_env_value "$env_file" APP_DB_USER)"
    password="$(read_env_value "$env_file" APP_DB_PASSWORD)"
    host="$(read_env_value "$env_file" APP_DB_HOST)"
    port="$(read_env_value "$env_file" APP_DB_PORT)"
  fi

  [[ "$name" == "$expected_name" ]] \
    || fail "Expected database $expected_name in $env_file, found $name"

  dump_file="$run_dir/${name}.dump"
  log "Creating dump for $name"
  PGPASSWORD="$password" pg_dump \
    --host="$host" \
    --port="$port" \
    --username="$user" \
    --dbname="$name" \
    --format=custom \
    --no-owner \
    --no-acl \
    --file="$dump_file"

  pg_restore --list "$dump_file" >/dev/null
}

upload_and_verify() {
  local local_file=$1
  local object_key=$2
  local local_size remote_size

  local_size="$(stat --format='%s' "$local_file")"
  log "Uploading $object_key ($local_size bytes)"
  aws --endpoint-url "$BACKUP_S3_ENDPOINT" s3 cp \
    "$local_file" "s3://${BACKUP_S3_BUCKET}/${object_key}" \
    --only-show-errors

  remote_size="$(
    aws --endpoint-url "$BACKUP_S3_ENDPOINT" s3api head-object \
      --bucket "$BACKUP_S3_BUCKET" \
      --key "$object_key" \
      --query ContentLength \
      --output text
  )"
  [[ "$remote_size" == "$local_size" ]] \
    || fail "Size mismatch for $object_key: local=$local_size remote=$remote_size"
}

main() {
  local project_root max_env psy_env girl_env work_root timestamp date_path
  local manifest dump_file encrypted_file database_name object_key

  require_command pg_dump pg_restore age aws sha256sum stat awk curl
  require_variable BACKUP_S3_ENDPOINT
  require_variable BACKUP_S3_BUCKET
  require_variable BACKUP_AGE_RECIPIENT
  require_variable AWS_ACCESS_KEY_ID
  require_variable AWS_SECRET_ACCESS_KEY

  project_root="${BACKUP_PROJECT_ROOT:-$DEFAULT_PROJECT_ROOT}"
  max_env="${BACKUP_MAX_ENV_FILE:-$project_root/.env}"
  psy_env="${BACKUP_PSY_ENV_FILE:-$DEFAULT_PSY_ENV}"
  girl_env="${BACKUP_GIRL_ENV_FILE:-$DEFAULT_GIRL_ENV}"
  work_root="${BACKUP_WORK_DIR:-/var/lib/max-bot-backup}"

  mkdir -p "$work_root"
  chmod 0700 "$work_root"

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  date_path="$(date -u +%Y/%m/%d)"
  run_dir="$(mktemp -d "$work_root/run-${timestamp}-XXXXXXXX")"
  manifest="$run_dir/MANIFEST.txt"

  dump_database "$max_env" DB max_bot_db
  dump_database "$max_env" APP_DB app_bot_db
  dump_database "$psy_env" DB psy_bot_db
  dump_database "$girl_env" DB girl_bot_db

  {
    printf 'created_at_utc=%s\n' "$timestamp"
    printf 'postgres_client=%s\n' "$(pg_dump --version)"
    printf 'format=PostgreSQL custom archive\n'
    printf '\nsha256  bytes  file\n'
    for dump_file in "$run_dir"/*.dump; do
      printf '%s  %s  %s\n' \
        "$(sha256sum "$dump_file" | awk '{print $1}')" \
        "$(stat --format='%s' "$dump_file")" \
        "${dump_file##*/}"
    done
  } >"$manifest"

  for dump_file in "$run_dir"/*.dump; do
    encrypted_file="${dump_file}.age"
    age --recipient "$BACKUP_AGE_RECIPIENT" \
      --output "$encrypted_file" "$dump_file"
    database_name="${dump_file##*/}"
    database_name="${database_name%.dump}"
    object_key="${BACKUP_S3_PREFIX:-daily}/${database_name}/${date_path}/${database_name}-${timestamp}.dump.age"
    upload_and_verify "$encrypted_file" "$object_key"
  done

  encrypted_file="${manifest}.age"
  age --recipient "$BACKUP_AGE_RECIPIENT" \
    --output "$encrypted_file" "$manifest"
  object_key="${BACKUP_S3_PREFIX:-daily}/manifests/${date_path}/manifest-${timestamp}.txt.age"
  upload_and_verify "$encrypted_file" "$object_key"

  success=1
  if [[ -n "${BACKUP_SUCCESS_HEARTBEAT_URL:-}" ]]; then
    curl --fail --silent --show-error --max-time 15 \
      "${BACKUP_SUCCESS_HEARTBEAT_URL}" >/dev/null
  fi
  log "Backup completed successfully: $timestamp"
}

main "$@"
