from datetime import datetime, timedelta, timezone
from typing import Literal

from backup_clickhouse_s3 import config


def date_to_epoch_seconds(date: datetime) -> int:
    return int(date.timestamp())


def epoch_to_oid(epoch_seconds: int) -> str:
    return f"{epoch_seconds:08x}0000000000000000"


def strategy_to_query(
        strategy: Literal["FULL", "DAY", "WEEK", "MONTH"],
        table: str,
        ts_column: str,
        ts_format: Literal["OID", "EPOCH", "DT"],
        backup_format: str
) -> str:

    if backup_format not in config.SUPPORTED_FORMATS.keys():
        raise ValueError(f"Unsupported backup format: {backup_format}. Supported formats: {', '.join(config.SUPPORTED_FORMATS.keys())}")

    if strategy == "FULL":
        where_clause = ""
    else:
        if strategy == "DAY":
            # yesterday 00:00 - today 00:00
            start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        elif strategy == "WEEK":
            # last week Monday 00:00 - this week Monday 00:00
            start_date = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday() + 7)).replace(hour=0, minute=0, second=0,
                                                                                                                         microsecond=0)
            end_date = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        elif strategy == "MONTH":
            # last month 1st 00:00 - this month 1st 00:00
            first_of_this_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_of_last_month = first_of_this_month - timedelta(days=1)
            start_date = last_of_last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = first_of_this_month
        else:
            raise ValueError('Supported: DAY, WEEK, MONTH')

        start_epoch: int = date_to_epoch_seconds(start_date)
        end_epoch: int = date_to_epoch_seconds(end_date)

        if ts_format == "OID":
            start = f"'{epoch_to_oid(start_epoch)}'"
            end = f"'{epoch_to_oid(end_epoch)}'"
        elif ts_format == "EPOCH":
            start = start_epoch
            end = end_epoch
        elif ts_format == "DT":
            # Convert into yyyy-mm-dd hh:mm:ss format
            start = "toDateTime('" + start_date.strftime('%Y-%m-%d %H:%M:%S') + "')"
            end = "toDateTime('" + end_date.strftime('%Y-%m-%d %H:%M:%S') + "')"
        else:
            raise ValueError('Supported formats: OID, EPOCH, DT')

        where_clause = f"WHERE {ts_column} >= {start} AND {ts_column} < {end}"

    return f"""
           INSERT INTO FUNCTION
               s3(
                   '{config.MINIO_ENDPOINT}/{config.MINIO_BUCKET}/{config.MINIO_PATH}/{config.CLICKHOUSE_DATABASE}_{table}_{strategy}_{datetime.now().strftime("%Y%M%d_%H%M")}.{config.SUPPORTED_FORMATS.get(backup_format)[1].lower()}',
                   '{config.MINIO_ACCESS_KEY}',
                   '{config.MINIO_SECRET_KEY}',
                   '{config.SUPPORTED_FORMATS.get(backup_format)[0]}'
                )
           SELECT * FROM {config.CLICKHOUSE_DATABASE}.{table} {where_clause}
    """
