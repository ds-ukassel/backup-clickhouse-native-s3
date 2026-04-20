import os

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 9000))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "default")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")
CLICKHOUSE_TABLES = os.getenv("CLICKHOUSE_TABLES", "")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9100")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "clickhouse-backups")
MINIO_PATH = os.getenv("MINIO_PATH", "backups")
MINIO_SECURE = (os.getenv("MINIO_SECURE", "False").lower() in ("true", "1", "enabled")) or MINIO_ENDPOINT.startswith("https://")

RETENTION_PERIOD = int(os.getenv("RETENTION_PERIOD")) if os.getenv("RETENTION_PERIOD") is not None else None

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

SUPPORTED_FORMATS = {
    "TSV": ("TSVWithNames", "tsv"),
    "CSV": ("CSVWithNames", "csv"),
    "JSONL": ("JSONEachRow", "jsonl"),
    "PARQUET": ("Parquet", "parquet"),
    "NATIVE": ("Native", "clickhouse"),
}

DEFAULT_BACKUP_FORMAT = os.getenv("DEFAULT_BACKUP_FORMAT", "NATIVE").upper()
