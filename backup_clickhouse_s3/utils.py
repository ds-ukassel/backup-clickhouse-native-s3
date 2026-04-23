import re
from datetime import timedelta


TIME_REGEX = r"^(\d+y)?\s*(\d+m)?\s*(\d+d)?\s*(\d+H)?\s*(\d+M)?\s*(\d+S)?$"


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
