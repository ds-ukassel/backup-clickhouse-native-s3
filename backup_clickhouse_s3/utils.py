import re
import sys
from datetime import timedelta
from typing import Callable, Any, Tuple, Type

from clickhouse_connect.driver import Client
from discord_webhook import DiscordWebhook

from backup_clickhouse_s3 import config

TIME_REGEX = r"^(\d+y)?\s*(\d+m)?\s*(\d+d)?\s*(\d+[Hh])?\s*(\d+M)?\s*(\d+[Ss])?$"
CLICKHOUSE_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

def string_to_timedelta(time_str: str) -> timedelta:
    """
    Converts a string consisting of timeunits into seconds.
    :param time_str: The string to convert (e.g. 1y6m, 1d12H, 5M10S, 30M, 1H30M).
    :return: A timedelta object representing the total time.
    :raises ValueError: If the input string is in an invalid format.
    """
    match = re.match(TIME_REGEX, time_str)

    if not match:
        raise ValueError(f"Invalid time format: {time_str}. Expected format like '1y6m', '1d12H', '5M10S', '30M', '1H30M'.")

    years = int(match.group(1)[:-1]) if match.group(1) else 0
    months = int(match.group(2)[:-1]) if match.group(2) else 0
    days = int(match.group(3)[:-1]) if match.group(3) else 0
    hours = int(match.group(4)[:-1]) if match.group(4) else 0
    minutes = int(match.group(5)[:-1]) if match.group(5) else 0
    seconds = int(match.group(6)[:-1]) if match.group(6) else 0

    return timedelta(
        days=years * 365 + months * 30 + days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )

def is_identifier(name: str) -> bool:
    """
    Checks if a given string is a valid ClickHouse identifier (e.g. for table or column names).
    Valid identifiers start with a letter or underscore, followed by letters, digits, underscores, or hyphens.
    :param name: The string to check.
    :return: True if the string is a valid identifier, False otherwise.
    """
    return bool(CLICKHOUSE_IDENTIFIER_REGEX.match(name))

def table_exists(clickhouse: Client, database: str, table: str) -> bool:
    """
    Checks if a given table exists in the ClickHouse database.
    :param clickhouse: An instance of the ClickHouse client.
    :param database: The name of the database.
    :param table: The name of the table to check.
    :return: True if the table exists, False otherwise.
    """
    if not is_identifier(database) or not is_identifier(table):
        raise ValueError(f"Invalid database or table name: {database}.{table}.")

    try:
        return clickhouse.command(f"EXISTS TABLE \"{database}\".\"{table}\"") == 1
    except Exception:
        return False

def retry_and_wait(
        function: Callable[..., Any],
        retries: int = 3,
        retry_on: Tuple[Type[Exception], ...] | Type[Exception] = (Exception,),
        *args,
        **kwargs,
) -> Any:
    """
    Retry a function call with a delay between attempts.
    :param function: The function to be called.
    :param retries: Number of retry attempts. Defaults to 3.
    :param retry_on: A tuple of exception types to catch and retry on. Defaults to all Exceptions.
    :param args: Positional arguments to pass to the function.
    :param kwargs: Keyword arguments to pass to the function.
    :return: The result of the function call.
    :raises: The last exception raised if all retries fail.
    """
    for attempt in range(retries):
        try:
            return function(*args, **kwargs)
        except retry_on:
            if attempt == retries - 1:
                raise

    return function(*args, **kwargs)

def webhook(message: str) -> None:
    if config.DISCORD_WEBHOOK_URL:
        try:
            DiscordWebhook(url=config.DISCORD_WEBHOOK_URL, rate_limit_retry=True, content=message).execute()
        except Exception as e:
            print(f"[clickhouse-backup] Failed to send Discord webhook: {e}", file=sys.stderr)
