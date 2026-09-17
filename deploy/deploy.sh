#!/usr/bin/env bash
# Build and (re)start the stack: migrations and the reference catalog go in before the API.
# Run from anywhere on the server after `git pull`:  ./deploy/deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

[[ -f "${SELFFORGE_ENV_FILE:-.env}" ]] || {
  echo "deploy/.env is missing: copy .env.example and fill it in" >&2
  exit 1
}
# SELFFORGE_ENV_FILE points at another env file (a staging copy); deploy/.env by default.
ENV_FILE="$(realpath "${SELFFORGE_ENV_FILE:-.env}")"
export SELFFORGE_ENV_FILE="$ENV_FILE"
compose() { docker compose --env-file "$ENV_FILE" "$@"; }
set -a; source "$ENV_FILE"; set +a
for var in SECRET_KEY POSTGRES_PASSWORD S3_SECRET_KEY APP_DOMAIN BACKUP_DIR; do
  [[ -n "${!var:-}" ]] || { echo "$var is empty in deploy/.env" >&2; exit 1; }
done
mkdir -p "$BACKUP_DIR/photos"

echo "→ building images"
compose build --pull

echo "→ starting storage"
compose up -d --wait db redis minio

echo "→ migrating the database and seeding the exercise catalog"
compose run --rm --no-deps api alembic upgrade head
compose run --rm --no-deps api python -m app.seed

echo "→ starting the app"
compose up -d --wait api web

echo "→ checking through the published ports"
curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null
curl -fsS "http://127.0.0.1:${WEB_PORT}/" | grep -q "<title>Self Forge</title>"
echo "✓ up: https://${APP_DOMAIN}"
