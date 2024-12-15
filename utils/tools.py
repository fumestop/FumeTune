from __future__ import annotations

from typing import Union

import datetime


def parse_duration(duration: Union[int, float]):
    duration = round(duration / 1000) * 1000
    return str(datetime.timedelta(milliseconds=duration))


def parse_cooldown(retry_after: Union[int, float]):
    retry_after = int(retry_after)

    hours, remainder = divmod(retry_after, 3600)
    minutes, seconds = divmod(remainder, 60)

    return minutes, seconds
