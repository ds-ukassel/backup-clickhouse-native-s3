import sys
import traceback

import clickhouse_connect
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

        # Go through all entries
        for entry in config.CLICKHOUSE_TABLES.split(" "):

            # Skip empty tables
            if not entry.strip():
                continue

            # Extract settings
            try:
                parts = entry.split(";")
                table = parts[0]
                settings = {}
                for setting in parts[1:]:
                    key, value = setting.split("=")
                    settings[key] = value

                strategy = settings.get("strategy", "FULL").upper()
                ts_column = settings.get("ts_column", "")
                ts_format = settings.get("ts_format", "").upper()
                backup_format = settings.get("backup_format", config.DEFAULT_BACKUP_FORMAT).upper()
            except Exception as e:
                print(f"[clickhouse-backup] Error parsing settings for table {entry}: {e}", file=sys.stderr)
                webhook(f"Backup of entry `{entry}` failed due to invalid settings.")
                continue

            if strategy != "FULL" and (not ts_column or not ts_format):
                print(f"[clickhouse-backup] Error: For strategy {strategy} you must specify 'ts_column' and 'ts_format'.", file=sys.stderr)
                webhook(f"Backup of table `{config.CLICKHOUSE_DATABASE}.{table}` failed due to missing settings.")
                continue

            try:
                query = strategy_to_query(strategy, table, ts_column, ts_format, backup_format)
            except Exception as e:
                print(f"[clickhouse-backup] Error generating query for table {table}: {e}", file=sys.stderr)
                webhook(f"Backup of table `{config.CLICKHOUSE_DATABASE}.{table}` failed due to invalid settings.")
                continue

            print(f"[clickhouse-backup] Executing backup for table {table} with strategy {strategy} and backup format {backup_format}...")
            try:
                clickhouse.command(query)
                print(f"[clickhouse-backup] Backup for table {table} completed successfully.")
            except ClickHouseError as e:
                print(f"[clickhouse-backup] Backup for table {table} failed with error: {e}", file=sys.stderr)
                webhook(f"Backup of ClickHouse table `{config.CLICKHOUSE_DATABASE}.{table}` failed.")

        # TODO: Re-add deletion of old backups

    except Exception as e:
        print(f"[clickhouse-backup] {type(e).__name__}: {e}", file=sys.stderr)
        webhook(f"Backup process failed.")
        traceback.print_exc()
        exit(1)