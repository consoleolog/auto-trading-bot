from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.trading.exchanges.upbit.codes import OrderSide, OrderType, SelfMatchPreventionType, TimeInForce
from src.trading.exchanges.upbit.codes.order_state import OrderState
from src.trading.exchanges.upbit.models import Order

# ============= Fixtures =============

KST = timezone(timedelta(hours=9))


@pytest.fixture
def order():
    """기본 Order 인스턴스를 생성한다."""
    return Order(
        market="KRW-BTC",
        uuid="550e8400-e29b-41d4-a716-446655440000",
        side=OrderSide.BID,
        ord_type=OrderType.LIMIT,
        price=Decimal("50000000"),
        state=OrderState.WAIT,
        created_at=datetime(2025, 6, 24, 13, 56, 53, tzinfo=KST),
        volume=Decimal("0.001"),
        remaining_volume=Decimal("0.001"),
        executed_volume=Decimal("0"),
        reserved_fee=Decimal("25000"),
        remaining_fee=Decimal("25000"),
        paid_fee=Decimal("0"),
        locked=Decimal("50025000"),
        trades_count=0,
        time_in_force=TimeInForce.NONE,
        identifier="my-order-1",
        smp_type=SelfMatchPreventionType.NONE,
        prevented_volume=Decimal("0"),
        prevented_locked=Decimal("0"),
    )


@pytest.fixture
def api_response():
    """업비트 API 주문 응답 데이터를 생성한다."""
    return {
        "market": "KRW-BTC",
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "side": "bid",
        "ord_type": "limit",
        "price": "50000000",
        "state": "wait",
        "created_at": "2025-06-24T13:56:53+09:00",
        "volume": "0.001",
        "remaining_volume": "0.001",
        "executed_volume": "0",
        "reserved_fee": "25000",
        "remaining_fee": "25000",
        "paid_fee": "0",
        "locked": "50025000",
        "trades_count": 0,
        "time_in_force": "ioc",
        "identifier": "my-order-1",
        "smp_type": "cancel_maker",
        "prevented_volume": "0",
        "prevented_locked": "0",
    }


# ============= __post_init__: Decimal 변환 =============


class TestPostInitDecimal:
    def test_converts_str_to_decimal(self):
        """문자열 값이 Decimal로 변환된다."""
        order = Order(
            market="KRW-BTC",
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=Decimal("50000000"),
            state=OrderState.WAIT,
            created_at=datetime(2025, 6, 24, 13, 56, 53, tzinfo=KST),
            volume="0.001",
            remaining_volume="0.001",
            executed_volume="0",
            reserved_fee="25000",
            remaining_fee="25000",
            paid_fee="0",
            locked="50025000",
            trades_count=0,
            time_in_force=TimeInForce.NONE,
            identifier="",
            smp_type=SelfMatchPreventionType.NONE,
            prevented_volume="0",
            prevented_locked="0",
        )

        assert isinstance(order.volume, Decimal)
        assert isinstance(order.remaining_volume, Decimal)
        assert isinstance(order.executed_volume, Decimal)
        assert order.volume == Decimal("0.001")

    def test_converts_int_to_decimal(self):
        """int 값이 Decimal로 변환된다."""
        order = Order(
            market="KRW-BTC",
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=Decimal("50000000"),
            state=OrderState.WAIT,
            created_at=datetime(2025, 6, 24, 13, 56, 53, tzinfo=KST),
            volume=Decimal("0.001"),
            remaining_volume=Decimal("0.001"),
            executed_volume=0,
            reserved_fee=25000,
            remaining_fee=25000,
            paid_fee=0,
            locked=50025000,
            trades_count=0,
            time_in_force=TimeInForce.NONE,
            identifier="",
            smp_type=SelfMatchPreventionType.NONE,
            prevented_volume=0,
            prevented_locked=0,
        )

        assert isinstance(order.executed_volume, Decimal)
        assert isinstance(order.reserved_fee, Decimal)
        assert isinstance(order.locked, Decimal)
        assert order.reserved_fee == Decimal("25000")

    def test_converts_float_to_decimal(self):
        """float 값이 Decimal로 변환된다."""
        order = Order(
            market="KRW-BTC",
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=Decimal("50000000"),
            state=OrderState.WAIT,
            created_at=datetime(2025, 6, 24, 13, 56, 53, tzinfo=KST),
            volume=0.001,
            remaining_volume=0.001,
            executed_volume=Decimal("0"),
            reserved_fee=Decimal("25000"),
            remaining_fee=Decimal("25000"),
            paid_fee=Decimal("0"),
            locked=Decimal("50025000"),
            trades_count=0,
            time_in_force=TimeInForce.NONE,
            identifier="",
            smp_type=SelfMatchPreventionType.NONE,
            prevented_volume=Decimal("0"),
            prevented_locked=Decimal("0"),
        )

        assert isinstance(order.volume, Decimal)
        assert isinstance(order.remaining_volume, Decimal)
        assert order.volume == Decimal("0.001")

    def test_keeps_decimal_as_is(self, order: Order):
        """이미 Decimal인 값은 그대로 유지된다."""
        assert order.remaining_volume == Decimal("0.001")
        assert isinstance(order.remaining_volume, Decimal)

    @pytest.mark.parametrize(
        "field_name",
        [
            "volume",
            "remaining_volume",
            "executed_volume",
            "reserved_fee",
            "remaining_fee",
            "paid_fee",
            "locked",
            "prevented_volume",
            "prevented_locked",
        ],
    )
    def test_all_decimal_fields_are_decimal(self, order: Order, field_name: str):
        """모든 수량/금액 필드가 Decimal 타입이다."""
        assert isinstance(getattr(order, field_name), Decimal)


# ============= __post_init__: datetime 변환 =============


class TestPostInitDatetime:
    def test_converts_created_at_from_str(self):
        """created_at 문자열(ISO 8601)이 datetime으로 변환된다."""
        order = Order(
            market="KRW-BTC",
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=Decimal("50000000"),
            state=OrderState.WAIT,
            created_at="2025-06-24T13:56:53+09:00",
            volume=Decimal("0.001"),
            remaining_volume=Decimal("0.001"),
            executed_volume=Decimal("0"),
            reserved_fee=Decimal("25000"),
            remaining_fee=Decimal("25000"),
            paid_fee=Decimal("0"),
            locked=Decimal("50025000"),
            trades_count=0,
            time_in_force=TimeInForce.NONE,
            identifier="",
            smp_type=SelfMatchPreventionType.NONE,
            prevented_volume=Decimal("0"),
            prevented_locked=Decimal("0"),
        )

        assert isinstance(order.created_at, datetime)
        assert order.created_at.year == 2025
        assert order.created_at.month == 6
        assert order.created_at.day == 24
        assert order.created_at.hour == 13
        assert order.created_at.minute == 56
        assert order.created_at.second == 53
        assert order.created_at.tzinfo is not None

    def test_keeps_datetime_as_is(self, order: Order):
        """이미 datetime인 값은 그대로 유지된다."""
        assert isinstance(order.created_at, datetime)
        assert order.created_at == datetime(2025, 6, 24, 13, 56, 53, tzinfo=KST)

    def test_preserves_timezone_info(self):
        """변환된 datetime이 timezone 정보를 유지한다."""
        order = Order(
            market="KRW-BTC",
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=Decimal("50000000"),
            state=OrderState.WAIT,
            created_at="2025-06-24T13:56:53+09:00",
            volume=Decimal("0.001"),
            remaining_volume=Decimal("0.001"),
            executed_volume=Decimal("0"),
            reserved_fee=Decimal("25000"),
            remaining_fee=Decimal("25000"),
            paid_fee=Decimal("0"),
            locked=Decimal("50025000"),
            trades_count=0,
            time_in_force=TimeInForce.NONE,
            identifier="",
            smp_type=SelfMatchPreventionType.NONE,
            prevented_volume=Decimal("0"),
            prevented_locked=Decimal("0"),
        )

        assert order.created_at.utcoffset() == timedelta(hours=9)


# ============= from_response =============


class TestFromResponse:
    def test_creates_order_from_response(self, api_response):
        """API 응답으로 Order를 생성한다."""
        order = Order.from_response(api_response)

        assert order.market == "KRW-BTC"
        assert order.uuid == "550e8400-e29b-41d4-a716-446655440000"

    def test_converts_side_to_enum(self, api_response):
        """side 문자열이 OrderSide enum으로 변환된다."""
        order = Order.from_response(api_response)

        assert order.side == OrderSide.BID

    def test_converts_ord_type_to_enum(self, api_response):
        """ord_type 문자열이 OrderType enum으로 변환된다."""
        order = Order.from_response(api_response)

        assert order.ord_type == OrderType.LIMIT

    def test_converts_state_to_enum(self, api_response):
        """state 문자열이 OrderState enum으로 변환된다."""
        order = Order.from_response(api_response)

        assert order.state == OrderState.WAIT

    def test_converts_time_in_force_to_enum(self, api_response):
        """time_in_force 문자열이 TimeInForce enum으로 변환된다."""
        order = Order.from_response(api_response)

        assert order.time_in_force == TimeInForce.IOC

    def test_converts_smp_type_to_enum(self, api_response):
        """smp_type 문자열이 SelfMatchPreventionType enum으로 변환된다."""
        order = Order.from_response(api_response)

        assert order.smp_type == SelfMatchPreventionType.CANCEL_MAKER

    def test_converts_created_at_to_datetime(self, api_response):
        """created_at 문자열이 datetime으로 변환된다."""
        order = Order.from_response(api_response)

        assert isinstance(order.created_at, datetime)
        assert order.created_at.year == 2025
        assert order.created_at.hour == 13

    def test_converts_decimal_fields(self, api_response):
        """숫자 문자열 필드가 Decimal로 변환된다."""
        order = Order.from_response(api_response)

        assert isinstance(order.remaining_volume, Decimal)
        assert isinstance(order.reserved_fee, Decimal)
        assert isinstance(order.locked, Decimal)
        assert order.remaining_volume == Decimal("0.001")

    def test_price_defaults_to_zero_when_missing(self, api_response):
        """price가 없으면 기본값 Decimal('0.0')이 사용된다."""
        del api_response["price"]
        order = Order.from_response(api_response)

        assert order.price == Decimal("0.0")

    def test_volume_defaults_to_zero_when_missing(self, api_response):
        """volume이 없으면 기본값 Decimal('0.0')이 사용된다."""
        del api_response["volume"]
        order = Order.from_response(api_response)

        assert order.volume == Decimal("0.0")

    def test_time_in_force_defaults_to_none_when_missing(self, api_response):
        """time_in_force가 없으면 TimeInForce.NONE이 사용된다."""
        del api_response["time_in_force"]
        order = Order.from_response(api_response)

        assert order.time_in_force == TimeInForce.NONE

    def test_identifier_defaults_to_empty_when_missing(self, api_response):
        """identifier가 없으면 빈 문자열이 사용된다."""
        del api_response["identifier"]
        order = Order.from_response(api_response)

        assert order.identifier == ""

    def test_smp_type_defaults_to_none_when_missing(self, api_response):
        """smp_type이 없으면 SelfMatchPreventionType.NONE이 사용된다."""
        del api_response["smp_type"]
        order = Order.from_response(api_response)

        assert order.smp_type == SelfMatchPreventionType.NONE

    def test_preserves_trades_count_as_int(self, api_response):
        """trades_count가 int로 유지된다."""
        order = Order.from_response(api_response)

        assert isinstance(order.trades_count, int)
        assert order.trades_count == 0
