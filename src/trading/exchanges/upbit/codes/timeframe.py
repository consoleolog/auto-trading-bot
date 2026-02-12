from enum import Enum


class Unit(Enum):
    """
    분(Minute) 캔들 단위
    캔들 단위를 지정하여 캔들 조회를 할 수 있습니다.
    최대 240분(4시간) 캔들까지 조회할 수 있습니다.
    """

    MINUTE_1 = 1
    MINUTE_3 = 3
    MINUTE_5 = 5
    MINUTE_10 = 10
    MINUTE_15 = 15
    HALF_HOUR = 30
    HOUR = 60
    HOUR_4 = 240


class Timeframe(Enum):
    """
    시간 캔들 단위
    """

    SECOND = "seconds"

    MINUTE_1 = f"minutes/{Unit.MINUTE_1.value}"
    MINUTE_3 = f"minutes/{Unit.MINUTE_3.value}"
    MINUTE_5 = f"minutes/{Unit.MINUTE_5.value}"
    MINUTE_10 = f"minutes/{Unit.MINUTE_10.value}"
    MINUTE_15 = f"minutes/{Unit.MINUTE_15.value}"

    HALF_HOUR = f"minutes/{Unit.HALF_HOUR.value}"
    HOUR = f"minutes/{Unit.HOUR.value}"
    HOUR_4 = f"minutes/{Unit.HOUR_4.value}"

    DAY = "days"
    WEEK = "weeks"
    MONTH = "months"
    YEAR = "years"
