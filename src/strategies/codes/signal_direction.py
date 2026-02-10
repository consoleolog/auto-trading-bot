from enum import Enum


class SignalDirection(Enum):
    """트레이딩 신호 방향.

    전략 분석 결과에 따라 생성되는 포지션 진입, 유지, 청산 신호를 정의합니다.
    각 신호는 현재 시장 상황과 전략 조건에 기반하여 결정됩니다.

    Attributes:
        LONG: 매수 포지션 진입 또는 유지 신호
        SHORT: 매도 포지션 진입 또는 유지 신호 (향후 사용 예정)
        CLOSE: 현재 포지션 청산 신호
        HOLD: 변경 없이 현재 포지션 유지 신호
    """

    LONG = "LONG"
    SHORT = "SHORT"  # Future use
    CLOSE = "CLOSE"
    HOLD = "HOLD"
