from __future__ import annotations

from typing import Union

import datetime


def parse_duration(duration: Union[int, float]):
    duration = round(duration / 1000) * 1000
    return str(datetime.timedelta(milliseconds=duration))
