import datetime
import sys

import clickhouse_connect
import yaml
from clickhouse_connect.driver import Client
from clickhouse_connect.driver.exceptions import ClickHouseError
from discord_webhook import DiscordWebhook
from minio import Minio

from backup_clickhouse_s3 import config, utils
from backup_clickhouse_s3.query_generator import strategy_to_query


def webhook(message: str) -> None:
    if config.DISCORD_WEBHOOK_URL:
        try:
            DiscordWebhook(url=config.DISCORD_WEBHOOK_URL, rate_limit_retry=True, content=message).execute()
        except Exception as e:
            print(f"[clickhouse-backup] Failed to send Discord webhook: {e}", file=sys.stderr)

def main() -> None:
    try:

        if not all([config.MINIO_ENDPOINT, config.MINIO_ACCESS_KEY, config.MINIO_SECRET_KEY, config.MINIO_BUCKET]):
            raise ValueError("Incomplete MinIO configuration. Check your environment variables.")

        if not all([config.CLICKHOUSE_HOST, config.CLICKHOUSE_USER, config.CLICKHOUSE_PASSWORD, config.CLICKHOUSE_DATABASE]):
            raise ValueError("Incomplete ClickHouse configuration. Check your environment variables.")

        if not config.CLICKHOUSE_TABLES.strip():
            raise ValueError("No tables specified for backup in CLICKHOUSE_TABLES environment variable.")

        # Create Minio Client
        try:
            minio: Minio = Minio(
                endpoint=config.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
                access_key=config.MINIO_ACCESS_KEY,
                secret_key=config.MINIO_SECRET_KEY,
                secure=config.MINIO_SECURE
            )
        except Exception as e:
            raise ValueError("Failed to create MinIO client. Check your MinIO configuration.") from e

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
            raise ValueError("Failed to create ClickHouse client. Check your ClickHouse configuration.") from e

        # Create bucket if it doesn't exist
        if not minio.bucket_exists(config.MINIO_BUCKET):
            minio.make_bucket(config.MINIO_BUCKET)

        try:
            tables = yaml.safe_load(config.CLICKHOUSE_TABLES)
            if not isinstance(tables, list):
                raise ValueError("Must be a YAML array of table entries.")
        except Exception as e:
            webhook("Backup process failed due to invalid tables configuration.")
            raise ValueError("Invalid CLICKHOUSE_TABLES configuration. Must be a YAML array of table entries.") from e

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

        if config.RETENTION_PERIOD.strip():
            try:
                retention_date = datetime.datetime.now(datetime.timezone.utc) - utils.string_to_timedelta(config.RETENTION_PERIOD)
                backups = minio.list_objects(config.MINIO_BUCKET, prefix=f"{config.MINIO_PATH}/", recursive=True)
                for backup in backups:
                    if backup.last_modified < retention_date:
                        minio.remove_object(config.MINIO_BUCKET, backup.object_name)
                        print(f"[clickhouse-backup] Deleted old backup: {backup.object_name}")
            except Exception as e:
                print(f"[clickhouse-backup] Error during retention cleanup: {e}", file=sys.stderr)
                webhook("Retention cleanup failed.")

    except Exception as e:
        print(f"[clickhouse-backup] {e}", file=sys.stderr)
        webhook(f"Backup process failed.")
        sys.exit(1)
