from enum import Enum


class PriceChangeState(Enum):
    """
    가격 변동 상태

    Attributes:
        EVEN: 보합
        RISE: 상승
        FALL: 하락
    """

    EVEN = "EVEN"
    RISE = "RISE"
    FALL = "FALL"
