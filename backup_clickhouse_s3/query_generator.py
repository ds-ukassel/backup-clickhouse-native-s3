from datetime import datetime, timedelta, timezone
from typing import Literal, Tuple, Dict, Any

from backup_clickhouse_s3 import config

Strategy = Literal["FULL", "DAY", "WEEK", "MONTH"]
TimeStampFormat = Literal["OID", "EPOCH", "DT"]

def date_to_epoch_seconds(date: datetime) -> int:
    return int(date.timestamp())


def epoch_to_oid(epoch_seconds: int) -> str:
    return f"{epoch_seconds:08x}0000000000000000"


def _resolve_date_range(strategy: Strategy) -> Tuple[datetime, datetime] | None:
    now = datetime.now(timezone.utc)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    match strategy:

        case "DAY":
            return today_midnight - timedelta(days=1), today_midnight

        case "WEEK":
            monday = today_midnight - timedelta(days=today_midnight.weekday())
            last_monday = monday - timedelta(days=7)
            return last_monday, monday

        case "MONTH":
            first_this_month = today_midnight.replace(day=1)
            last_prev_month = first_this_month - timedelta(days=1)
            start = last_prev_month.replace(day=1)
            return start, first_this_month

        case "FULL":
            return None

    raise ValueError(f"Unsupported strategy: {strategy}.")


def _format_bounds(ts_format: TimeStampFormat, start: datetime, end: datetime) -> Tuple[Any, Any, str]:
    start_epoch = date_to_epoch_seconds(start)
    end_epoch = date_to_epoch_seconds(end)

    match ts_format:
        case "OID":
            return epoch_to_oid(start_epoch), epoch_to_oid(end_epoch), "String"

        case "EPOCH":
            return start_epoch, end_epoch, "UInt32"

        case "DT":
            return start, end, "DateTime"

    raise ValueError(f"Unsupported timestamp format: {ts_format}.")


def strategy_to_query(strategy: Strategy, database: str, table: str, ts_column: str, ts_format: TimeStampFormat, backup_format: str) -> Tuple[str, Dict[str, Any]]:
    output_format = config.SUPPORTED_FORMATS[backup_format][0]
    file_extension = config.SUPPORTED_FORMATS[backup_format][1].lower()

    backup_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    prefix = "" if (config.MINIO_ENDPOINT.startswith("https://") or config.MINIO_ENDPOINT.startswith("http://")) else ("https://" if config.MINIO_SECURE else "http://")
    minio_uri = f"{prefix}{config.MINIO_ENDPOINT}/{config.MINIO_BUCKET}/{config.MINIO_PATH}/{database}_{table}_{strategy}_{backup_timestamp}.{file_extension}"

    params = {
        "minio_uri": minio_uri,
        "strategy": strategy,
        "backup_timestamp": backup_timestamp,
        "access_key": config.MINIO_ACCESS_KEY,
        "secret_key": config.MINIO_SECRET_KEY,
        "output_format": output_format,
    }

    query = f"""
            INSERT INTO FUNCTION s3(
                {{minio_uri: String}},
                {{access_key: String}},
                {{secret_key: String}},
                {{output_format: String}}
            )
            SELECT *
            FROM "{database}"."{table}"
            """

    if strategy != "FULL":
        start_datetime, end_datetime = _resolve_date_range(strategy)
        start_timestamp, end_timestamp, timestamp_type = _format_bounds(ts_format, start_datetime, end_datetime)

        params.update({
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
        })

        where_clause = f" WHERE \"{ts_column}\" >= {{start_timestamp: {timestamp_type}}} AND \"{ts_column}\" < {{end_timestamp: {timestamp_type}}}"
        return query + where_clause, params

    return query, params
