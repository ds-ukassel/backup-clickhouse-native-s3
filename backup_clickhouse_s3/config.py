import os

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 8123))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "")
CLICKHOUSE_TABLES = os.getenv("CLICKHOUSE_TABLES", "")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "")
MINIO_PATH = os.getenv("MINIO_PATH", "backups")
MINIO_SECURE = (os.getenv("MINIO_SECURE", "False").lower() in ("true", "1", "enabled")) or (MINIO_ENDPOINT or "").startswith("https://")
MINIO_REPLACE_STRATEGY = os.getenv("MINIO_REPLACE_STRATEGY", "ERROR").upper()

RETENTION_PERIOD = os.getenv("RETENTION_PERIOD", "")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

SUPPORTED_FORMATS = {
    "TSV": ("TSVWithNames", "tsv"),
    "CSV": ("CSVWithNames", "csv"),
    "JSONL": ("JSONEachRow", "jsonl"),
    "PARQUET": ("Parquet", "parquet"),
    "NATIVE": ("Native", "clickhouse"),
}

DEFAULT_BACKUP_FORMAT = os.getenv("DEFAULT_BACKUP_FORMAT", "NATIVE").upper()
