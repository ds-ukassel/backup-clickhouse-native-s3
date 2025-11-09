#!/bin/bash
set -e

# Required environment variables
: "${CLICKHOUSE_HOST:?Missing CLICKHOUSE_HOST}"
: "${CLICKHOUSE_USER:?Missing CLICKHOUSE_USER}"
: "${CLICKHOUSE_PASSWORD:?Missing CLICKHOUSE_PASSWORD}"
: "${CLICKHOUSE_DATABASE:?Missing CLICKHOUSE_DATABASE}"
: "${CLICKHOUSE_TABLES:?Missing CLICKHOUSE_TABLES (semicolon-separated list of tables)}"
: "${MINIO_ENDPOINT:?Missing MINIO_ENDPOINT}"
: "${MINIO_ACCESS_KEY:?Missing MINIO_ACCESS_KEY}"
: "${MINIO_SECRET_KEY:?Missing MINIO_SECRET_KEY}"

# Optional variables with defaults
CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-9000}"
MINIO_BUCKET="${MINIO_BUCKET:-clickhouse-backups}"
MINIO_PATH="${MINIO_PATH:-clickhouse-backups}"
RETENTION_PERIOD="${RETENTION_PERIOD:-}"
MINIO_COMMAND="${MINIO_COMMAND:-mc}"
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"

NOW=$(date +%Y%m%d_%H%M%S)

send_webhook_error() {
  if [ -n "$DISCORD_WEBHOOK_URL" ]; then
    echo "[clickhouse-backup] Sending error notification to Discord webhook..."
    PAYLOAD="{\"content\": \"Backup of ClickHouse at $NOW failed!\"}"
    curl -H "Content-Type: application/json" -X POST -d "$PAYLOAD" "$DISCORD_WEBHOOK_URL" || true
  fi
}

trap 'send_webhook_error' ERR

CLICKHOUSE_COMMAND="clickhouse-client --host=$CLICKHOUSE_HOST --port=$CLICKHOUSE_PORT --user=$CLICKHOUSE_USER --password=$CLICKHOUSE_PASSWORD"

echo "[clickhouse-backup] Starting backup at $NOW..."
$MINIO_COMMAND alias set storage "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"
$MINIO_COMMAND mb -p "storage/$MINIO_BUCKET"

# Split CLICKHOUSE_TABLES into seperate tables
TABLE_LIST=$(echo "$CLICKHOUSE_TABLES" | tr ';' '\n' | xargs -n 1 echo)

for TABLE in $TABLE_LIST; do
  [ -z "$TABLE" ] && continue # Skip empty table names

  BACKUP_FILE="${CLICKHOUSE_DATABASE}_${TABLE}_${NOW}.native.gz"

  echo "[clickhouse-backup] Exporting '$CLICKHOUSE_DATABASE.$TABLE' and uploading..."

  $CLICKHOUSE_COMMAND --query="SELECT * FROM $CLICKHOUSE_DATABASE.$TABLE FORMAT Native" \
    | gzip -c \
    | $MINIO_COMMAND pipe "storage/$MINIO_BUCKET/$MINIO_PATH/$BACKUP_FILE"
done

if [ -n "$RETENTION_PERIOD" ]; then
  echo "[clickhouse-backup] Deleting backups older than $RETENTION_PERIOD from MinIO..."
  $MINIO_COMMAND rm --recursive --older-than "$RETENTION_PERIOD" --force "storage/$MINIO_BUCKET/$MINIO_PATH/"
fi

echo "[clickhouse-backup] Backup completed successfully!"