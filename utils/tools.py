from __future__ import annotations
from typing import Union

import datetime


def parse_duration(duration: Union[int, float]):
    days = duration // (24 * 60 * 60 * 1000)
    remaining_milliseconds = duration % (24 * 60 * 60 * 1000)

    seconds = remaining_milliseconds // 1000
    milliseconds = remaining_milliseconds % 1000

    return str(
        datetime.timedelta(days=days, seconds=seconds, milliseconds=milliseconds)
    )


def parse_cooldown(retry_after: Union[int, float]):
    retry_after = int(retry_after)

    hours, remainder = divmod(retry_after, 3600)
    minutes, seconds = divmod(remainder, 60)

    return minutes, seconds
