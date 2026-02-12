from dataclasses import dataclass
from datetime import datetime, timezone
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
    side: OrderSide | None
    ord_type: OrderType | None

    price: Decimal

    state: OrderState | None
    created_at: datetime
    volume: Decimal
    remaining_volume: Decimal
    executed_volume: Decimal
    reserved_fee: Decimal
    remaining_fee: Decimal
    paid_fee: Decimal
    locked: Decimal
    trades_count: int

    time_in_force: TimeInForce | None
    identifier: str
    smp_type: SelfMatchPreventionType | None
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

        if isinstance(self.side, str):
            self.side = OrderSide(self.side)

        if isinstance(self.ord_type, str):
            self.ord_type = OrderType(self.ord_type)

        if isinstance(self.state, str):
            self.state = OrderState(self.state)

        if isinstance(self.time_in_force, str):
            self.time_in_force = TimeInForce(self.time_in_force)

        if isinstance(self.smp_type, str):
            self.smp_type = SelfMatchPreventionType(self.smp_type)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            market=data.get("market", ""),
            uuid=data.get("uuid", ""),
            side=data.get("side"),
            ord_type=data.get("ord_type"),
            price=data.get("price", Decimal("0.0")),
            state=data.get("state"),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
            volume=data.get("volume", Decimal("0.0")),
            remaining_volume=data.get("remaining_volume", Decimal("0.0")),
            executed_volume=data.get("executed_volume", Decimal("0.0")),
            reserved_fee=data.get("reserved_fee", Decimal("0.0")),
            remaining_fee=data.get("remaining_fee", Decimal("0.0")),
            paid_fee=data.get("paid_fee", Decimal("0.0")),
            locked=data.get("locked", Decimal("0.0")),
            trades_count=data.get("trades_count", 0),
            time_in_force=data.get("time_in_force"),
            identifier=data.get("identifier", ""),
            smp_type=data.get("smp_type"),
            prevented_volume=data.get("prevented_volume", Decimal("0.0")),
            prevented_locked=data.get("prevented_locked", Decimal("0.0")),
        )
