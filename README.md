# backup-clickhouse-native-s3
Simple script for backing up clickhouse tables to an S3 (minio) bucket using the native format.

# Configuration

```bash
# Required environment variables
CLICKHOUSE_HOST='http://localhost:9100'
CLICKHOUSE_USER='default'
CLICKHOUSE_PASSWORD='password'
CLICKHOUSE_DATABASE='default'
CLICKHOUSE_TABLES='table1;table2'
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

`CLICKHOUSE_TABLES` can be used to specify the tables to back up, separated by semicolons.

Backups will be stored under the specified `MINIO_PATH` in the bucket `MINIO_BUCKET`, with filenames in the format `<table>_YYYYMMDD_HHMMSS.native.gz`.

When setting `DISCORD_WEBHOOK_URL`, a notification will be sent to the specified Discord webhook when the backup fails.

