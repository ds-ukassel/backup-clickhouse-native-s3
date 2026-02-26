#!/bin/bash
set -eo pipefail

# Required environment variables
: "${CLICKHOUSE_HOST:?Missing CLICKHOUSE_HOST}"
: "${CLICKHOUSE_USER:?Missing CLICKHOUSE_USER}"
: "${CLICKHOUSE_PASSWORD:?Missing CLICKHOUSE_PASSWORD}"
: "${CLICKHOUSE_DATABASE:?Missing CLICKHOUSE_DATABASE}"
: "${CLICKHOUSE_TABLES:?Missing CLICKHOUSE_TABLES (space-separated list of tables)}"
: "${MINIO_ENDPOINT:?Missing MINIO_ENDPOINT}"
: "${MINIO_ACCESS_KEY:?Missing MINIO_ACCESS_KEY}"
: "${MINIO_SECRET_KEY:?Missing MINIO_SECRET_KEY}"

# Optional variables with defaults
CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-9000}"
MINIO_BUCKET="${MINIO_BUCKET:-clickhouse-backups}"
MINIO_PATH="${MINIO_PATH-clickhouse-backups}"
RETENTION_PERIOD="${RETENTION_PERIOD:-}"
MINIO_COMMAND="${MINIO_COMMAND:-mc}"
CLICKHOUSE_COMMAND="${CLICKHOUSE_COMMAND:-clickhouse-client}"
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"

NOW=$(date +%Y%m%d_%H%M%S)

send_webhook_error() {
  if [ -n "$DISCORD_WEBHOOK_URL" ]; then
    echo "[clickhouse-backup] Sending error notification to Discord webhook..."

    # Remove ':range:column:format' from tables
    local TABLE_LIST=""
    for entry in $CLICKHOUSE_TABLES; do
      table="${entry%%:*}" # Remove everything after first colon
      TABLE_LIST+="$table, "
    done
    TABLE_LIST="${TABLE_LIST%, }" # Remove trailing comma+space

    PAYLOAD="{\"content\": \"Backup of ClickHouse database $CLICKHOUSE_DATABASE (tables: $TABLE_LIST) at $NOW failed!\"}"
    curl -H "Content-Type: application/json" -X POST -d "$PAYLOAD" "$DISCORD_WEBHOOK_URL" || true
  fi
}

trap 'send_webhook_error' ERR

echo "[clickhouse-backup] Starting backup at $NOW..."
$MINIO_COMMAND alias set storage "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"
$MINIO_COMMAND mb -p "storage/$MINIO_BUCKET"

for TABLE_RANGE_COLUMN_FORMAT in $CLICKHOUSE_TABLES; do
  [ -z "$TABLE_RANGE_COLUMN_FORMAT" ] && continue # Skip empty table names

  IFS=':' read -r TABLE RANGE COLUMN FORMAT <<< "$TABLE_RANGE_COLUMN_FORMAT"

  RANGE="${RANGE:-FULL}"
  echo "[clickhouse-backup] Processing table '$TABLE' with range '$RANGE'..."
  if [ "${RANGE^^}" != "FULL" ]; then # RANGE^^ converts to uppercase for case-insensitive comparison
    if [ -z "$COLUMN" ] || [ -z "$FORMAT" ]; then
      echo "[clickhouse-backup] ERROR: COLUMN and FORMAT must be specified when RANGE is not FULL for table '$TABLE'."
      exit 1
    fi

    QUERY="$(query_generator.py "$RANGE" "$CLICKHOUSE_DATABASE" "$TABLE" "$COLUMN" "$FORMAT")"
    echo "[clickhouse-backup] Generated query for table '$TABLE' with range '$RANGE': $QUERY"

  else
    QUERY="SELECT * FROM $CLICKHOUSE_DATABASE.$TABLE FORMAT Native"
  fi

  BACKUP_FILE="${CLICKHOUSE_DATABASE}_${TABLE}_${NOW}.native.gz"

  echo "[clickhouse-backup] Exporting '$CLICKHOUSE_DATABASE.$TABLE' and uploading..."

  $CLICKHOUSE_COMMAND --host="$CLICKHOUSE_HOST" --port="$CLICKHOUSE_PORT" --user="$CLICKHOUSE_USER" --password="$CLICKHOUSE_PASSWORD" --query="$QUERY" \
    | gzip -c \
    | $MINIO_COMMAND pipe "storage/$MINIO_BUCKET/$MINIO_PATH/$BACKUP_FILE"
done

if [ -n "$RETENTION_PERIOD" ]; then
  echo "[clickhouse-backup] Deleting backups older than $RETENTION_PERIOD from MinIO..."
  $MINIO_COMMAND rm --recursive --older-than "$RETENTION_PERIOD" --force "storage/$MINIO_BUCKET/$MINIO_PATH/"
fi

echo "[clickhouse-backup] Backup completed successfully!"