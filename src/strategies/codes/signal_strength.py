from enum import Enum


class SignalStrength(Enum):
    """
    시그널 강도

    Attributes:
        STRONG_BID: 강한 매수 신호
        BID: 일반적인 매수 신호
        NEUTRAL: 아무 신호도 발생하지 않음
        ASK: 일반적인 매도 신호
        STRONG_ASK: 강한 매도 신호
    """

    STRONG_BID = 2
    BID = 1
    NEUTRAL = 0
    ASK = -1
    STRONG_ASK = -2
