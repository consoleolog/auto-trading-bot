from enum import Enum


class OrderType(Enum):
    """
    주문 유형
    생성하고자 하는 주문의 유형에 따라 아래 값 중 하나를 입력합니다.

    Attributes:
        LIMIT: 지정가 매수/매도 주문
        PRICE: 시장가 매수 주문
        MARKET: 시장가 매도 주문
        BEST: 최유리 지정가 매수/매도 주문 (time_in_force 필드 설정 필수)
    """

    LIMIT = "limit"
    PRICE = "price"
    MARKET = "market"
    BEST = "best"
