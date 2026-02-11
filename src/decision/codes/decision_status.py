from enum import Enum


class DecisionStatus(Enum):
    """의사결정 상태.

    트레이딩 의사결정의 승인 및 실행 진행 상태를 추적합니다.
    승인 프로세스가 필요한 경우 각 단계를 관리하는 데 사용됩니다.

    Attributes:
        PENDING: 승인 대기 중인 상태
        APPROVED: 승인되어 실행 가능한 상태
        REJECTED: 승인이 거부된 상태
        EXECUTED: 실행이 완료된 상태
        CANCELLED: 실행 전에 취소된 상태
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
