import datetime
import sys
import traceback
from datetime import timedelta

import clickhouse_connect
import json5
from clickhouse_connect.driver import Client
from clickhouse_connect.driver.exceptions import ClickHouseError
from discord_webhook import DiscordWebhook
from minio import Minio

from backup_clickhouse_s3 import config
from backup_clickhouse_s3.query_generator import strategy_to_query


def webhook(message: str) -> None:
    if config.DISCORD_WEBHOOK_URL:
        DiscordWebhook(url=config.DISCORD_WEBHOOK_URL, rate_limit_retry=True, content=message).execute()

def main() -> None:
    try:

        if not config.CLICKHOUSE_TABLES.strip():
            print("[clickhouse-backup] No tables specified for backup.", file=sys.stderr)
            exit(1)

        # Create Minio Client
        try:
            minio: Minio = Minio(
                endpoint=config.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
                access_key=config.MINIO_ACCESS_KEY,
                secret_key=config.MINIO_SECRET_KEY,
                secure=config.MINIO_SECURE
            )
        except Exception as e:
            print(f"[clickhouse-backup] Failed to create MinIO client: {e}", file=sys.stderr)
            exit(1)

        # Create ClickHouse client
        try:
            clickhouse: Client = clickhouse_connect.get_client(
                host=config.CLICKHOUSE_HOST,
                port=config.CLICKHOUSE_PORT,
                user=config.CLICKHOUSE_USER,
                password=config.CLICKHOUSE_PASSWORD,
                database=config.CLICKHOUSE_DATABASE
            )
        except Exception as e:
            print(f"[clickhouse-backup] Failed to create ClickHouse client: {e}", file=sys.stderr)
            exit(1)

        # Create bucket if it doesn't exist
        if not minio.bucket_exists(config.MINIO_BUCKET):
            minio.make_bucket(config.MINIO_BUCKET)

        try:
            tables = json5.loads(config.CLICKHOUSE_TABLES)
            if not isinstance(tables, list):
                raise ValueError("Must be a JSON array of table entries.")
        except Exception as e:
            print(f"[clickhouse-backup] Error parsing CLICKHOUSE_TABLES: {e}", file=sys.stderr)
            webhook("Backup process failed due to invalid tables configuration.")
            exit(1)

        # Go through all entries
        for entry in tables:
            if not isinstance(entry, dict):
                print(f"[clickhouse-backup] Invalid table entry (not an object): {entry}", file=sys.stderr)
                webhook(f"Backup of entry `{entry}` failed due to invalid configuration.")
                continue

            # Extract settings
            table = entry.get("table", "")
            strategy = entry.get("strategy", "FULL").upper()
            ts_column = entry.get("ts_column", "")
            ts_format = entry.get("ts_format", "").upper()
            backup_format = entry.get("backup_format", config.DEFAULT_BACKUP_FORMAT).upper()

            if not table:
                print(f"[clickhouse-backup] Error: Table name is required in entry: {entry}", file=sys.stderr)
                webhook(f"Backup of entry `{entry}` failed due to missing table name.")
                continue

            if strategy != "FULL" and (not ts_column or not ts_format):
                print(f"[clickhouse-backup] Error: For strategy {strategy} you must specify 'ts_column' and 'ts_format'.", file=sys.stderr)
                webhook(f"Backup of table `{config.CLICKHOUSE_DATABASE}.{table}` failed due to missing settings.")
                continue

            try:
                query, params = strategy_to_query(strategy, table, ts_column, ts_format, backup_format)
            except Exception as e:
                print(f"[clickhouse-backup] Error generating query for table '{table}': {e}", file=sys.stderr)
                webhook(f"Backup of table `{config.CLICKHOUSE_DATABASE}.{table}` failed due to invalid settings.")
                continue

            print(f"[clickhouse-backup] Executing backup for table '{table}' with strategy '{strategy}' and backup format '{backup_format}'...")
            try:
                clickhouse.command(cmd=query, parameters=params)
                print(f"[clickhouse-backup] Backup for table '{table}' completed successfully.")
            except ClickHouseError as e:
                print(f"[clickhouse-backup] Backup for table '{table}' failed with error: {e}", file=sys.stderr)
                webhook(f"Backup of ClickHouse table `{config.CLICKHOUSE_DATABASE}.{table}` failed.")

        if config.RETENTION_PERIOD:
            try:
                retention_date = datetime.datetime.now(datetime.timezone.utc) - timedelta(days=config.RETENTION_PERIOD)
                backups = minio.list_objects(config.MINIO_BUCKET, prefix=f"{config.MINIO_PATH}/", recursive=True)
                for backup in backups:
                    if backup.last_modified < retention_date:
                        minio.remove_object(config.MINIO_BUCKET, backup.object_name)
                        print(f"[clickhouse-backup] Deleted old backup: {backup.object_name}")
            except Exception as e:
                print(f"[clickhouse-backup] Error during retention cleanup: {e}", file=sys.stderr)
                webhook("Retention cleanup failed.")

    except Exception as e:
        print(f"[clickhouse-backup] {type(e).__name__}: {e}", file=sys.stderr)
        webhook(f"Backup process failed.")
        traceback.print_exc()
        exit(1)
