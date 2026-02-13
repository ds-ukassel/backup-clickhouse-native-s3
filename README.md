# backup-clickhouse-native-s3
Simple script for backing up clickhouse tables to an S3 (minio) bucket using the native format.

# Configuration

```bash
# Required environment variables
CLICKHOUSE_HOST='http://localhost:9100'
CLICKHOUSE_USER='default'
CLICKHOUSE_PASSWORD='password'
CLICKHOUSE_DATABASE='default'
CLICKHOUSE_TABLES='table1:range:column:format table2'
MINIO_ENDPOINT='http://localhost:9000'
MINIO_ACCESS_KEY='minioadmin'
MINIO_SECRET_KEY='minioadmin'

# Optional variables
CLICKHOUSE_PORT=9000
MINIO_BUCKET='clickhouse-backups'
MINIO_PATH='clickhouse-backups'
RETENTION_PERIOD='7d'
MINIO_COMMAND='mc'
DISCORD_WEBHOOK_URL=''
```

# Description

When running the script, it will connect to the specified clickhouse database, create a backup for each specified table by extracting its contents into a native file format, compress it and upload it to the specified S3 bucket.

It will also remove backups older than the specified number of days.
To disable this feature, leave `RETENTION_PERIOD` empty.

`CLICKHOUSE_TABLES` can be used to specify the tables to back up, separated by spaces.

Backups will be stored under the specified `MINIO_PATH` in the bucket `MINIO_BUCKET`, with filenames in the format `<table>_YYYYMMDD_HHMMSS.native.gz`.

When setting `DISCORD_WEBHOOK_URL`, a notification will be sent to the specified Discord webhook when the backup fails.

## Strategies
The script supports different backup strategies for creating partial backups of specific tables.

The strategies are defined in the `CLICKHOUSE_TABLES` environment variable as a space-separated list of `table:STRATEGY:COLUMN:FORMAT` pairs.
If `STRATEGY` is not specified, a full backup of the table will be created.
If `STRATEGY` is specified, the script will filter the rows and only back up the rows that match the specified strategy.

Supported strategies:
- `full`: full backup of the collection
- `day`: [yesterday 00:00, today 00:00)
- `week`: [Monday of last week 00:00, Monday of this week 00:00)
- `month`: [1st day of last month 00:00, 1st day of this month 00:00)

The `COLUMN` defines the field used for filtering the rows (e.g. `createdAt` as a DateTime)
The `FORMAT` defines the format of the column.

Supported formats:
- `DT`: DateTime (e.g. `2026-02-02 12:00:00`)
- `EPOCH`: Unix timestamp (e.g. `1770988180`)
- `OID`: ObjectId (from MongoDB)