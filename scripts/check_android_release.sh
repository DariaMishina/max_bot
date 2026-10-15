#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

fail() {
  printf 'release-gate: ERROR: %s\n' "$*" >&2
  exit 1
}

pass() {
  printf 'release-gate: OK: %s\n' "$*"
}

expected_package="ru.tarotsphere.app"
expected_rustore_id="2063751721"
gradle_file="android/app/build.gradle.kts"
properties_file="android/keystore.properties"
env_file=".env"

channel="${1:-}"
api_url="${APP_API_BASE_URL:-${2:-}}"
[[ "$channel" == "alpha" || "$channel" == "production" ]] \
  || fail "usage: $0 alpha|production https://api.example/"

grep -Fq "applicationId = \"$expected_package\"" "$gradle_file" \
  || fail "unexpected Android applicationId"
grep -Fq "namespace = \"$expected_package\"" "$gradle_file" \
  || fail "unexpected Android namespace"
grep -Fq "orElse(\"$expected_rustore_id\")" "$gradle_file" \
  || fail "unexpected RuStore Console Application ID"
pass "package and RuStore Application ID"

[[ -n "$api_url" ]] || fail "pass production API URL as argument or APP_API_BASE_URL"
[[ "$api_url" == https://* ]] || fail "release API URL is not HTTPS"
[[ "$api_url" != *localhost* && "$api_url" != *127.0.0.1* ]] \
  || fail "release API URL points to a local host"
staging_url="$(sed -n 's/.*orElse("\(https:[^"]*\)").*/\1/p' android/data/build.gradle.kts | head -n 1)"
if [[ "$channel" == "alpha" ]]; then
  [[ "${api_url%/}" == "${staging_url%/}" ]] \
    || fail "alpha release must use the configured staging URL"
else
  [[ "${api_url%/}" != "${staging_url%/}" ]] \
    || fail "production release must not use the configured staging URL"
fi
pass "explicit $channel HTTPS API origin: $api_url"

[[ -r "$properties_file" ]] || fail "$properties_file is missing"
[[ -r "$env_file" ]] || fail "$env_file is missing"
store_file="$(sed -n 's/^storeFile=//p' "$properties_file" | head -n 1)"
key_alias="$(sed -n 's/^keyAlias=//p' "$properties_file" | head -n 1)"
[[ -n "$store_file" && -n "$key_alias" ]] || fail "incomplete keystore.properties"
keystore="android/$store_file"
[[ -r "$keystore" ]] || fail "release keystore is missing: $keystore"

store_password="$(sed -n 's/^ANDROID_RELEASE_STORE_PASSWORD=//p' "$env_file" | head -n 1)"
[[ -n "$store_password" ]] || fail "ANDROID_RELEASE_STORE_PASSWORD is missing from local .env"
keytool -list -keystore "$keystore" -storepass "$store_password" -alias "$key_alias" >/dev/null \
  || fail "release keystore or alias cannot be read"
pass "release signing key is readable"

backup="$(find android/signing/backup -type f -name '*.jks' -print -quit 2>/dev/null || true)"
[[ -n "$backup" ]] || fail "keystore backup is missing"
cmp -s "$keystore" "$backup" || fail "keystore backup differs from the active key"
pass "keystore backup is byte-identical"

if git ls-files '*.jks' 'android/keystore.properties' '.env' | grep -q .; then
  fail "a signing secret or private environment file is tracked by Git"
fi
pass "release secrets are not tracked by Git"

if grep -RInE '(APP_RUSTORE_PRIVATE_KEY|APP_RUSTORE_CALLBACK_KEY|ANDROID_RELEASE_(STORE|KEY)_PASSWORD)=[^<[:space:]]+' \
    --exclude='.env' --exclude='check_android_release.sh' --exclude-dir='.git' --exclude-dir='build' . >/dev/null; then
  fail "a populated secret-like variable was found outside .env"
fi
pass "no populated release secrets found in tracked source"

printf 'release-gate: PASS\n'
