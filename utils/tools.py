from __future__ import annotations

from typing import Union

import datetime

MAX_TRACK_LENGTH_MS = 24 * 60 * 60 * 1000  # 24 hours


def parse_duration(duration: Union[int, float]):
    duration = round(duration / 1000) * 1000
    return str(datetime.timedelta(milliseconds=duration))
