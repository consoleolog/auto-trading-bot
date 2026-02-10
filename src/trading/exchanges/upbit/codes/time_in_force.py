from enum import Enum


class TimeInForce(Enum):
    """
    주문 체결 조건.
    IOC(Immediate or Cancel), FOK(Fill or Kill), Post Only와 같은 주문 체결 조건을 설정할 수 있습니다.
    시장가 주문(ord_type 필드가 "limit")인 경우 모든 옵션을 선택적으로 사용할 수 있습니다.
    최유리 지정가 주문(ord_type 필드가 “best”)인 경우 대해 "ioc" 또는 "fok" 중 하나를 필수로 입력합니다.

    Attributes:
        IOC: 지정가 조건으로 체결 가능한 수량만 즉시 부분 체결하고, 잔여 수량은 취소됩니다.
        FOK: 지정가 조건으로 주문량 전량 체결 가능할 때만 주문을 실행하고, 아닌 경우 전량 주문 취소합니다.
        POST_ONLY: 지정가 조건으로 부분 또는 전체에 대해 즉시 체결 가능한 상황인 경우 주문을 실행하지 않고 취소합니다.
                    즉, 메이커(maker)주문으로 생성될 수 있는 상황에서만
                    주문이 생성되며 테이커(taker) 주문으로 체결되는 것을 방지합니다.
    """

    NONE = None
    IOC = "ioc"
    FOK = "fok"
    POST_ONLY = "post_only"
