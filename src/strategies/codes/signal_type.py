from enum import Enum


class SignalType(Enum):
    """
    기술적 지표에서 발생하는 시그널 종류

    Attributes:
        CROSS_OVER: 교차 시그널 (Golden cross, Dead cross)
        ZERO_CROSS: 0 선을 기준으로 발생하는 교차 시그널 (Golden cross, Dead cross)
        OVER_LINE: 과매도 과매수 시그널 (overbought, oversold)
    """

    CROSS_OVER = "crossover"
    ZERO_CROSS = "zero_cross"
    OVER_LINE = "overline"
