import re
import sys
import time
from typing import Callable, Any, Tuple, Type

from clickhouse_connect.driver import Client
from discord_webhook import DiscordWebhook

from backup_clickhouse_s3 import config

CLICKHOUSE_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


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

    return clickhouse.command(f"EXISTS TABLE \"{database}\".\"{table}\"") == 1


def retry_and_wait(
        function: Callable[..., Any],
        retries: int = 3,
        delay: Callable[[int], float] = lambda attempt: (2 ** attempt),
        retry_on: Tuple[Type[Exception], ...] | Type[Exception] = (Exception,),
        *args,
        **kwargs,
) -> Any:
    """
    Retry a function call with a delay between attempts.
    :param function: The function to be called.
    :param retries: Number of retry attempts. Defaults to 3.
    :param delay: A callable that takes the attempt number and returns the delay in seconds. Defaults to exponential backoff (2^attempt seconds).
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
            time.sleep(delay(attempt))

    return function(*args, **kwargs)


def webhook(message: str) -> None:
    if config.DISCORD_WEBHOOK_URL:
        try:
            DiscordWebhook(url=config.DISCORD_WEBHOOK_URL, rate_limit_retry=True, content=message).execute()
        except Exception as e:
            print(f"[clickhouse-backup] Failed to send Discord webhook: {e}", file=sys.stderr)
