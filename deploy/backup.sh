#!/usr/bin/env bash
# Nightly backup to this server's disk (cron, see docs/07-deploy.md):
#   - a compressed pg_dump of the database, 7 daily + 4 weekly (Sundays) kept by default;
#   - a mirror of the photo bucket. Photos someone deleted leave the mirror too: deleting
#     a private photo has to mean it's gone.
set -euo pipefail
cd "$(dirname "$0")"
# SELFFORGE_ENV_FILE points at another env file (a staging copy); deploy/.env by default.
ENV_FILE="$(realpath "${SELFFORGE_ENV_FILE:-.env}")"
export SELFFORGE_ENV_FILE="$ENV_FILE"
compose() { docker compose --env-file "$ENV_FILE" "$@"; }
set -a; source "$ENV_FILE"; set +a

stamp="$(date +%Y-%m-%d_%H%M)"
daily="$BACKUP_DIR/db/daily"
weekly="$BACKUP_DIR/db/weekly"
mkdir -p "$daily" "$weekly" "$BACKUP_DIR/photos"

dump="$daily/selfforge_$stamp.dump"
compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom >"$dump.part"
# A dump that pg_restore can't list is not a backup.
compose exec -T db pg_restore --list <"$dump.part" >/dev/null
mv "$dump.part" "$dump"
chmod 600 "$dump"

if [[ "$(date +%u)" == "7" ]]; then
  cp "$dump" "$weekly/"
fi

# Keep the newest N dumps in a directory. An empty directory is fine, not an error.
rotate() {
  local dir="$1" keep="$2" old
  shopt -s nullglob
  local dumps=("$dir"/*.dump)
  shopt -u nullglob
  (( ${#dumps[@]} > keep )) || return 0
  while IFS= read -r old; do rm -- "$old"; done < <(ls -1t "${dumps[@]}" | tail -n +"$((keep + 1))")
}
rotate "$daily" "$BACKUP_KEEP_DAILY"
rotate "$weekly" "$BACKUP_KEEP_WEEKLY"

compose exec -T minio sh -c '
  mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null &&
  mc mb --ignore-existing local/'"$S3_PHOTOS_BUCKET"' >/dev/null &&
  mc mirror --quiet --overwrite --remove local/'"$S3_PHOTOS_BUCKET"' /backups/photos' >/dev/null

echo "$(date +%Y-%m-%dT%H:%M:%S%z) backup ok: $(du -h "$dump" | cut -f1) database, $(du -sh "$BACKUP_DIR/photos" | cut -f1) photos"
