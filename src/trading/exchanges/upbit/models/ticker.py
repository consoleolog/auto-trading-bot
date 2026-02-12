from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from ..codes import PriceChangeState


@dataclass
class Ticker:
    """
    현재가(티커) 데이터 모델.

    Attributes:
        market: 페어(거래쌍)의 코드
        trade_date: 최근 체결 일자 (UTC 기준) [형식] yyyyMMdd
        trade_time: 최근 체결 시각 (UTC 기준) [형식] HHmmss
        trade_date_kst: 최근 체결 일자 (KST 기준) [형식] yyyyMMdd
        trade_time_kst: 최근 체결 시각 (KST 기준) [형식] HHmmss
        trade_timestamp: 체결 시각의 밀리초단위 타임스탬프
        opening_price: 시가. 해당 페어의 첫 거래 가격입니다.
        high_price: 고가. 해당 페어의 최고 거래 가격입니다.
        low_price: 저가. 해당 페어의 최저 거래 가격입니다.
        trade_price: 종가. 해당 페어의 현재 가격입니다.
        prev_closing_price: 전일 종가 (UTC 0시 기준)
        change: 가격 변동 상태
        change_price: 전일 종가 대비 가격 변화(절대값) "trade_price" - "prev_closing_price"로 계산됩니다.
        change_rate: 전일 종가 대비 가격 변화 (절대값)
                        ("trade_price" - "prev_closing_price") ÷ "prev_closing_price" 으로 계산됩니다.
        signed_change_price: 전일 종가 대비 가격 변화.
                                "trade_price" - "prev_closing_price"로 계산되며,
                                현재 종가가 전일 종가보다 얼마나 상승 또는 하락했는지를 나타냅니다.

                                양수(+): 현재 종가가 전일 종가보다 상승한 경우
                                음수(-): 현재 종가가 전일 종가보다 하락한 경우
        signed_change_rate: 전일 종가 대비 가격 변화율
                                ("trade_price" - "prev_closing_price") ÷ "prev_closing_price" 으로 계산됩니다.

                                양수(+): 가격 상승
                                음수(-): 가격 하락
                                [예시] 0.015 = 1.5% 상승
        trade_volume: 최근 거래 수량
        acc_trade_price: 누적 거래 금액 (UTC 0시 기준)
        acc_trade_price_24h: 24시간 누적 거래 금액
        acc_trade_volume: 누적 거래량 (UTC 0시 기준)
        acc_trade_volume_24h: 24시간 누적 거래량
        highest_52_week_price: 52주 신고가
        highest_52_week_date: 52주 신고가 달성일 [형식] yyyy-MM-dd
        lowest_52_week_price: 52주 신저가
        lowest_52_week_date: 52주 신저가 달성일 [형식] yyyy-MM-dd
        timestamp: 현재가 정보가 반영된 시각의 타임스탬프(ms)
    """

    market: str

    trade_date: datetime
    trade_time: datetime

    trade_date_kst: datetime
    trade_time_kst: datetime

    trade_timestamp: int

    opening_price: Decimal
    high_price: Decimal
    low_price: Decimal
    trade_price: Decimal

    prev_closing_price: Decimal

    change: PriceChangeState | None
    change_price: Decimal
    change_rate: Decimal

    signed_change_price: Decimal
    signed_change_rate: Decimal

    trade_volume: Decimal

    acc_trade_price: Decimal
    acc_trade_price_24h: Decimal

    acc_trade_volume: Decimal
    acc_trade_volume_24h: Decimal

    highest_52_week_price: Decimal
    highest_52_week_date: datetime

    lowest_52_week_price: Decimal
    lowest_52_week_date: datetime

    timestamp: int

    def __post_init__(self):
        for field_name in [
            "opening_price",
            "high_price",
            "low_price",
            "trade_price",
            "prev_closing_price",
            "change_price",
            "change_rate",
            "signed_change_price",
            "signed_change_rate",
            "trade_volume",
            "acc_trade_price",
            "acc_trade_price_24h",
            "acc_trade_volume",
            "acc_trade_volume_24h",
            "highest_52_week_price",
            "lowest_52_week_price",
        ]:
            value = getattr(self, field_name)
            if isinstance(value, (int, float, str)):
                setattr(self, field_name, Decimal(str(value)))

        _datetime_formats = {
            "trade_date": "%Y%m%d",
            "trade_time": "%H%M%S",
            "trade_date_kst": "%Y%m%d",
            "trade_time_kst": "%H%M%S",
            "highest_52_week_date": "%Y-%m-%d",
            "lowest_52_week_date": "%Y-%m-%d",
        }
        for field_name, fmt in _datetime_formats.items():
            value = getattr(self, field_name)
            if isinstance(value, str):
                setattr(self, field_name, datetime.strptime(value, fmt))

        if isinstance(self.change, str):
            self.change = PriceChangeState(self.change)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            market=data.get("market", ""),
            trade_date=data.get("trade_date", datetime.now(tz=timezone.utc)),
            trade_time=data.get("trade_time", datetime.now(tz=timezone.utc)),
            trade_date_kst=data.get("trade_date_kst", datetime.now(tz=timezone.utc) + timedelta(hours=9)),
            trade_time_kst=data.get("trade_time_kst", datetime.now(tz=timezone.utc) + timedelta(hours=9)),
            trade_timestamp=data.get("trade_timestamp", 0),
            opening_price=data.get("opening_price", Decimal("0.0")),
            high_price=data.get("high_price", Decimal("0.0")),
            low_price=data.get("low_price", Decimal("0.0")),
            trade_price=data.get("trade_price", Decimal("0.0")),
            prev_closing_price=data.get("prev_closing_price", Decimal("0.0")),
            change=data.get("change"),
            change_price=data.get("change_price", Decimal("0.0")),
            change_rate=data.get("change_rate", Decimal("0.0")),
            signed_change_price=data.get("signed_change_price", Decimal("0.0")),
            signed_change_rate=data.get("signed_change_rate", Decimal("0.0")),
            trade_volume=data.get("trade_volume", Decimal("0.0")),
            acc_trade_price=data.get("acc_trade_price", Decimal("0.0")),
            acc_trade_price_24h=data.get("acc_trade_price_24h", Decimal("0.0")),
            acc_trade_volume=data.get("acc_trade_volume", Decimal("0.0")),
            acc_trade_volume_24h=data.get("acc_trade_volume_24h", Decimal("0.0")),
            highest_52_week_price=data.get("highest_52_week_price", Decimal("0.0")),
            highest_52_week_date=data.get("highest_52_week_date", datetime.now(tz=timezone.utc)),
            lowest_52_week_price=data.get("lowest_52_week_price", Decimal("0.0")),
            lowest_52_week_date=data.get("lowest_52_week_date", datetime.now(tz=timezone.utc)),
            timestamp=data.get("timestamp", 0),
        )
