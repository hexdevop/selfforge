#!/usr/bin/env bash
# Restore the database from a dump made by backup.sh, and optionally the photos mirror.
#   ./deploy/restore.sh /var/backups/selfforge/db/daily/selfforge_2026-09-17_0330.dump [--photos]
# Replaces what's in the database now — it asks before doing anything.
set -euo pipefail
cd "$(dirname "$0")"
# SELFFORGE_ENV_FILE points at another env file (a staging copy); deploy/.env by default.
ENV_FILE="$(realpath "${SELFFORGE_ENV_FILE:-.env}")"
export SELFFORGE_ENV_FILE="$ENV_FILE"
compose() { docker compose --env-file "$ENV_FILE" "$@"; }
set -a; source "$ENV_FILE"; set +a

dump="${1:?path to a .dump file}"
[[ -f "$dump" ]] || { echo "no such file: $dump" >&2; exit 1; }

read -r -p "Replace the current database with $(basename "$dump")? Type yes: " answer
[[ "$answer" == "yes" ]] || { echo "cancelled"; exit 1; }

compose stop api
compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner <"$dump"

if [[ "${2:-}" == "--photos" ]]; then
  compose exec -T minio sh -c '
    mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null &&
    mc mb --ignore-existing local/'"$S3_PHOTOS_BUCKET"' &&
    mc mirror --overwrite /backups/photos local/'"$S3_PHOTOS_BUCKET"
fi

compose up -d --wait api
echo "✓ restored from $(basename "$dump")"
