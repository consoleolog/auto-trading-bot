from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..codes import OrderSide, OrderState, OrderType, SelfMatchPreventionType, TimeInForce


@dataclass
class Order:
    """
    주문 데이터

    Attributes:
        market: 페어(거래쌍)의 코드
        uuid: 주문의 유일 식별자
        side: 주문 방향(매수/매도)
        ord_type: 주문 유형
        price: 주문 단가 또는 총액. 지정가 주문의 경우 단가, 시장가 매수 주문의 경우 매수 총액입니다.
        state: 주문 상태
        created_at: 주문 생성 시각 (KST 기준) [형식] yyyy-MM-ddTHH:mm:ss+09:00
        volume: 주문 요청 수량
        remaining_volume: 체결 후 남은 주문 양
        executed_volume: 체결된 양
        reserved_fee: 수수료로 예약된 비용
        remaining_fee: 남은 수수료
        paid_fee: 사용된 수수료
        locked: 거래에 사용 중인 비용
        trades_count: 해당 주문에 대한 체결 건수
        time_in_force: 주문 체결 옵션
        identifier: 주문 생성시 클라이언트가 지정한 주문 식별자.
        smp_type: 자전거래 체결 방지(Self-Match Prevention) 모드
        prevented_volume: 자전거래 방지로 인해 취소된 수량.
                동일 사용자의 주문 간 체결이 발생하지 않도록 설정(SMP)에 따라 취소된 주문 수량입니다.
        prevented_locked: 자전거래 방지로 인해 해제된 자산.
                자전거래 체결 방지 설정으로 인해 취소된 주문의 잔여 자산입니다.

                매수 주문의 경우: 취소된 금액
                매도 주문의 경우: 취소된 수량
    """

    market: str
    uuid: str
    side: OrderSide
    ord_type: OrderType

    price: Decimal | None

    state: OrderState
    created_at: datetime
    volume: Decimal | None
    remaining_volume: Decimal
    executed_volume: Decimal
    reserved_fee: Decimal
    remaining_fee: Decimal
    paid_fee: Decimal
    locked: Decimal
    trades_count: int

    time_in_force: TimeInForce
    identifier: str
    smp_type: SelfMatchPreventionType
    prevented_volume: Decimal
    prevented_locked: Decimal

    def __post_init__(self):
        for field_name in [
            "volume",
            "remaining_volume",
            "executed_volume",
            "reserved_fee",
            "remaining_fee",
            "paid_fee",
            "locked",
            "prevented_volume",
            "prevented_locked",
        ]:
            value = getattr(self, field_name)
            if isinstance(value, (int, float, str)):
                setattr(self, field_name, Decimal(str(value)))

        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)

    @classmethod
    def from_response(cls, response: dict):
        return cls(
            market=response["market"],
            uuid=response["uuid"],
            side=OrderSide(response["side"]),
            ord_type=OrderType(response["ord_type"]),
            price=response.get("price", Decimal("0.0")),
            state=OrderState(response["state"]),
            created_at=response["created_at"],
            volume=response.get("volume", Decimal("0.0")),
            remaining_volume=response["remaining_volume"],
            executed_volume=response["executed_volume"],
            reserved_fee=response["reserved_fee"],
            remaining_fee=response["remaining_fee"],
            paid_fee=response["paid_fee"],
            locked=response["locked"],
            trades_count=response["trades_count"],
            time_in_force=TimeInForce(response.get("time_in_force")),
            identifier=response.get("identifier", ""),
            smp_type=SelfMatchPreventionType(response.get("smp_type")),
            prevented_volume=response["prevented_volume"],
            prevented_locked=response["prevented_locked"],
        )
