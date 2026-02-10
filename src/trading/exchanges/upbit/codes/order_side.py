from enum import Enum


class OrderSide(Enum):
    """
    주문 방향 (매수/매도)
    매수 주문을 생성하는 경우 `bid`, 매도 주문을 생성하는 경우 `ask` 로 지정합니다.

    Attributes:
        ASK: 매도
        BID: 매수
    """

    ASK = "ask"
    BID = "bid"
