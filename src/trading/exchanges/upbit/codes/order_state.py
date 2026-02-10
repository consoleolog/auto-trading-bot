from enum import Enum


class OrderState(Enum):
    """
    주문 상태

    Attributes:
        WAIT: 체결 대기
        WATCH: 예약 주문 대기
        DONE: 체결 완료
        CANCEL: 주문 취소
    """

    WAIT = "wait"
    WATCH = "watch"
    DONE = "done"
    CANCEL = "cancel"
