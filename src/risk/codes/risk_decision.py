from enum import Enum


class RiskDecision(Enum):
    """리스크 평가 결과 종류"""

    ALLOW = "ALLOW"  # 거래 진행 허용
    REDUCE_SIZE = "REDUCE_SIZE"  # 규모를 축소하여 거래 허용
    FORCE_NO_ACTION = "FORCE_NO_ACTION"  # 거래 차단
    EMERGENCY_STOP = "EMERGENCY_STOP"  # 모든 포지션 청산(Flatten)
