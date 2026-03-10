#!/usr/bin/env python3

from datetime import datetime, timedelta, timezone


def date_to_epoch_seconds(date) -> int:
    return int(date.timestamp())


def epoch_to_oid(epoch_seconds) -> str:
    return f"{epoch_seconds:08x}0000000000000000"


def strategy_to_query(range, database, table, field, format) -> str:
    if range == "DAY":
        # yesterday 00:00 - today 00:00
        start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    elif range == "WEEK":
        # last week Monday 00:00 - this week Monday 00:00
        start_date = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday() + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif range == "MONTH":
        # last month 1st 00:00 - this month 1st 00:00
        first_of_this_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        start_date = last_of_last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = first_of_this_month
    else:
        raise ValueError('Supported: DAY, WEEK, MONTH')

    start_epoch = date_to_epoch_seconds(start_date)
    end_epoch = date_to_epoch_seconds(end_date)

    if format == "OID":
        start = f"'{epoch_to_oid(start_epoch)}'"
        end = f"'{epoch_to_oid(end_epoch)}'"
    elif format == "EPOCH":
        start = start_epoch
        end = end_epoch
    elif format == "DT":
        # Convert into yyyy-mm-dd hh:mm:ss format
        start = "toDateTime('" + start_date.strftime('%Y-%m-%d %H:%M:%S') + "')"
        end = "toDateTime('" + end_date.strftime('%Y-%m-%d %H:%M:%S') + "')"

    else:
        raise ValueError('Supported formats: OID, EPOCH, DT')

    return f"SELECT * FROM {database}.{table} WHERE {field} >= {start} AND {field} < {end} FORMAT NATIVE"



if __name__ == "__main__":
    import sys

    if len(sys.argv) != 6:
        print("Usage: python query_generator.py <DAY|WEEK|MONTH> <database> <table> <field> <format>", file=sys.stderr)
        sys.exit(1)

    range = sys.argv[1].upper()
    database = sys.argv[2]
    table = sys.argv[3]
    field = sys.argv[4]
    format = sys.argv[5].upper()

    try:
        print(strategy_to_query(range, database, table, field, format))
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)