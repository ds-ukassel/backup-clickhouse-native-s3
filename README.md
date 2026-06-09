# backup-clickhouse-s3
Simple script for backing up clickhouse tables to an S3 (minio) bucket using different formats.

# Configuration

```bash
CLICKHOUSE_HOST='localhost'
CLICKHOUSE_PORT=8123 # HTTP Port
CLICKHOUSE_USER='default'
CLICKHOUSE_PASSWORD='password'
CLICKHOUSE_DATABASE='default'
CLICKHOUSE_TABLES=''

MINIO_ENDPOINT='http://minio:9100'
MINIO_ACCESS_KEY='minioadmin'
MINIO_SECRET_KEY='minioadmin'
MINIO_BUCKET='clickhouse-backups'
MINIO_PATH='clickhouse-backups'
MINIO_SECURE=false # Automatically enabled if the endpoint starts with 'https://'

RETENTION_PERIOD=7d
DISCORD_WEBHOOK_URL=''
DEFAULT_BACKUP_FORMAT='NATIVE'
```

# Description

When running the script, it will connect to the specified clickhouse database, create a backup for each specified table and upload it to the specified S3 bucket.

It will also remove backups older than the specified time period defined by `RETENTION_PERIOD`.
To specify a date, use a string like `1y 1m 1d 12H 30M 10S` (1 year, 1 month, 1 day, 12 hours, 30 minutes and 10 seconds).
A year is considered as 365 days and a month is considered as 30 days.

To disable this feature, leave `RETENTION_PERIOD` empty.

`CLICKHOUSE_TABLES` can be used to specify the tables to back up (see [Backup Settings](#backup-settings)).

Backups will be stored under the specified `MINIO_PATH` in the bucket `MINIO_BUCKET`, with filenames in the format `<database>_<table>_<strategy>_<date>.<extension>`.
The `date` will depend on the strategy and include the timestamp of the backup (for `FULL` strategy) or the start date of the backup (for other strategies).

When setting `DISCORD_WEBHOOK_URL`, a notification will be sent to the specified Discord webhook if the backup fails.

## Backup Settings

The tables and their corresponding backup settings are provided by the `CLICKHOUSE_TABLES` environment variable as a YAML list of objects.
Alternatively you can simply provide the name as a string, which will be treated as a full backup of the table with the default backup format.

```yaml
- table: "table1"
  strategy: "WEEK"
  ts_column: "created_at"
  ts_format: "DT"
  backup_format: "JSONL"

- table: "table2"
  backup_format: "CSV"

- table3
```

For each entry, the `table` field is required.
If `strategy` is not specified, a full backup of the table will be created.
If `strategy` is specified, the script will filter the rows and only back up the rows that match the specified strategy.

Supported strategies:
- `full`: full backup of the collection
- `day`: [yesterday 00:00, today 00:00)
- `week`: [Monday of last week 00:00, Monday of this week 00:00)
- `month`: [1st day of last month 00:00, 1st day of this month 00:00)

The `ts_column` defines the field used for filtering the rows (e.g. `createdAt` as a DateTime)
The `ts_format` defines the format of the column.

Supported formats:
- `DT`: DateTime (e.g. `2026-02-02 12:00:00`)
- `EPOCH`: Unix timestamp (e.g. `1770988180`)
- `OID`: ObjectId (from MongoDB)

The `backup_format` defines the format of the backup file.
Supported formats:
- `CSV` (`.csv`): Comma-separated values
- `JSONL` (`.jsonl`): JSON Lines format
- `TSV` (`.tsv`): Tab-separated values
- `PARQUET` (`.parquet`): Parquet format
- `NATIVE` (`.clickhouse`): ClickHouse Native format

Setting the `backup_format` is optional and will default to `NATIVE` if not specified.
The fallback can be changed by setting the `DEFAULT_BACKUP_FORMAT` environment variable to one of the supported formats.
