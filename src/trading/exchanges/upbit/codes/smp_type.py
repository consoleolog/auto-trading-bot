from enum import Enum


class SelfMatchPreventionType(Enum):
    """
    자전거래 체결 방지(Self-Match Prevention) 모드.

    Attributes:
        CANCEL_MAKER: 메이커 주문(이전 주문)을 취소합니다.
        CANCEL_TAKER: 테이커 주문(신규 주문)을 취소합니다.
        REDUCE: 기존 주문과 신규 주문의 주문 수량을 줄여 체결을 방지합니다. 잔량이 0인 경우 주문을 취소합니다.
    """

    NONE = None
    CANCEL_MAKER = "cancel_maker"
    CANCEL_TAKER = "cancel_taker"
    REDUCE = "reduce"
