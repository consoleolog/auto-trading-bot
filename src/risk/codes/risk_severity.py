from enum import Enum


class RiskSeverity(Enum):
    """리스크 상태의 심각도"""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"
