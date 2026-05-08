import datetime
import sys
from typing import cast

import clickhouse_connect
import yaml
from clickhouse_connect.driver import Client
from clickhouse_connect.driver.exceptions import ClickHouseError
from minio import Minio

from backup_clickhouse_s3 import config, utils
from backup_clickhouse_s3.query_generator import strategy_to_query, Strategy, TimeStampFormat


def extract_settings(entry: str | dict[str, str]) -> tuple[str, str, str, str, str]:
    if isinstance(entry, str):
        entry = {"table": entry}

    table = entry.get("table", "")
    strategy = entry.get("strategy", "FULL").upper()
    ts_column = entry.get("ts_column", "")
    ts_format = entry.get("ts_format", "").upper()
    backup_format = entry.get("backup_format", config.DEFAULT_BACKUP_FORMAT).upper()

    return table, strategy, ts_column, ts_format, backup_format


def check_entries(clickhouse: Client, entries: list[str | dict[str, str]]) -> bool:
    for entry in entries:

        # Check if table is string or settings object
        if not isinstance(entry, (str, dict)):
            print(f"[clickhouse-backup] Invalid table entry (not an object or table name): {entry}", file=sys.stderr)
            return False

        table, strategy, ts_column, ts_format, backup_format = extract_settings(entry)

        # Check if table is valid and exists
        if not table:
            print(f"[clickhouse-backup] Invalid table entry (missing table name): {entry}", file=sys.stderr)
            return False

        if strategy != "FULL" and (not utils.is_identifier(table) or not utils.is_identifier(ts_column)):
            print(f"[clickhouse-backup] Invalid table or timestamp column name in entry: {entry}.", file=sys.stderr)
            return False

        if not utils.table_exists(clickhouse, config.CLICKHOUSE_DATABASE, table):
            print(f"[clickhouse-backup] Table '{config.CLICKHOUSE_DATABASE}.{table}' does not exist.", file=sys.stderr)
            return False

        # Check if settings are valid for strategy
        if strategy != "FULL" and (not ts_column or not ts_format):
            print(f"[clickhouse-backup] Error: For strategy {strategy} you must specify 'ts_column' and 'ts_format'.", file=sys.stderr)
            return False

        if strategy not in ("FULL", "DAY", "WEEK", "MONTH"):
            print(f"[clickhouse-backup] Unsupported strategy '{strategy}' for table '{table}'.", file=sys.stderr)
            return False

        if ts_format and ts_format not in ("OID", "EPOCH", "DT"):
            print(f"[clickhouse-backup] Unsupported timestamp format '{ts_format}' for table '{table}'. Supported formats are: OID, EPOCH, DT.", file=sys.stderr)
            return False

        if backup_format not in config.SUPPORTED_FORMATS:
            print(f"[clickhouse-backup] Unsupported backup format '{backup_format}' for table '{table}'. Supported formats are: {', '.join(config.SUPPORTED_FORMATS.keys())}.", file=sys.stderr)
            return False

    return True


def main() -> None:
    try:
        # Check if required config options are set
        if not all([config.MINIO_ENDPOINT, config.MINIO_ACCESS_KEY, config.MINIO_SECRET_KEY, config.MINIO_BUCKET]):
            print("[clickhouse-backup] Incomplete MinIO configuration. Check your environment variables.", file=sys.stderr)
            utils.webhook("Backup process failed due to incomplete MinIO configuration.")
            sys.exit(1)

        if not all([config.CLICKHOUSE_HOST, config.CLICKHOUSE_USER, config.CLICKHOUSE_PASSWORD, config.CLICKHOUSE_DATABASE]):
            print("[clickhouse-backup] Incomplete ClickHouse configuration. Check your environment variables.", file=sys.stderr)
            utils.webhook("Backup process failed due to incomplete ClickHouse configuration.")
            sys.exit(1)

        if not config.CLICKHOUSE_TABLES.strip():
            print("[clickhouse-backup] No tables specified for backup.", file=sys.stderr)
            utils.webhook("Backup process stopped due to missing tables configuration.")
            sys.exit(0)

        # Check if database is a valid identifier
        database = config.CLICKHOUSE_DATABASE
        if not utils.is_identifier(database):
            print(f"[clickhouse-backup] Invalid database name: {database}.", file=sys.stderr)
            utils.webhook("Backup process failed due to invalid database name.")
            sys.exit(1)

        # Create Minio Client
        try:
            minio: Minio = Minio(
                endpoint=config.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
                access_key=config.MINIO_ACCESS_KEY,
                secret_key=config.MINIO_SECRET_KEY,
                secure=config.MINIO_SECURE
            )
        except Exception as e:
            print(f"[clickhouse-backup] Failed to create MinIO client. Check your MinIO configuration: {e}", file=sys.stderr)
            utils.webhook("Backup process failed due to invalid MinIO configuration.")
            sys.exit(1)

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
            print(f"[clickhouse-backup] Failed to create ClickHouse client. Check your ClickHouse configuration: {e}", file=sys.stderr)
            utils.webhook("Backup process failed due to invalid ClickHouse configuration.")
            sys.exit(1)

        # Create bucket if it doesn't exist
        try:
            if not minio.bucket_exists(config.MINIO_BUCKET):
                minio.make_bucket(config.MINIO_BUCKET)
        except Exception as e:
            print(f"[clickhouse-backup] Failed to access or create MinIO bucket '{config.MINIO_BUCKET}': {e}", file=sys.stderr)
            utils.webhook("Backup process failed due to MinIO bucket access issues.")
            sys.exit(1)

        # Load table configuration
        try:
            entries = yaml.safe_load(config.CLICKHOUSE_TABLES)
            if not isinstance(entries, list):
                raise ValueError("Must be a YAML array of table entries.")
        except Exception as e:
            print(f"[clickhouse-backup] Failed to parse CLICKHOUSE_TABLES: {e}", file=sys.stderr)
            utils.webhook("Backup process failed due to invalid table configuration.")
            sys.exit(1)

        # Check if tables are valid and exist
        if not check_entries(clickhouse, entries):
            utils.webhook("Backup process failed due to invalid table configuration.") # Webhook is enough, prints are done in check_entries
            sys.exit(1)

        # Go through all entries
        for entry in entries:

            # Get settings from entry
            table, strategy, ts_column, ts_format, backup_format = extract_settings(entry)

            # Generate query (at this point, the settings are checked, so we can cast without issues)
            query, params = strategy_to_query(cast(Strategy, strategy), database, table, ts_column, cast(TimeStampFormat, ts_format), backup_format)

            # Execute backup
            print(f"[clickhouse-backup] Executing backup for table '{table}' with strategy '{strategy}' and backup format '{backup_format}'...")
            try:
                utils.retry_and_wait(function=clickhouse.command, retry_on=ClickHouseError, retries=3, cmd=query, parameters=params)
                print(f"[clickhouse-backup] Backup for table '{table}' completed successfully.")
            except ClickHouseError as e:
                print(f"[clickhouse-backup] Backup for table '{table}' failed with error: {e}", file=sys.stderr)
                utils.webhook(f"Backup of ClickHouse table `{config.CLICKHOUSE_DATABASE}.{table}` failed.")
                sys.exit(1)

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
                utils.webhook("Retention cleanup failed.")

    except Exception as e:
        print(f"[clickhouse-backup] {e}", file=sys.stderr)
        utils.webhook(f"Backup process failed.")
        sys.exit(1)
