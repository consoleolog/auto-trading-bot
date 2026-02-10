from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.trading.exchanges.upbit.codes import PriceChangeState


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

    change: PriceChangeState
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

    @classmethod
    def from_response(cls, response):
        return cls(
            market=response["market"],
            trade_date=response["trade_date"],
            trade_time=response["trade_time"],
            trade_date_kst=response["trade_date_kst"],
            trade_time_kst=response["trade_time_kst"],
            trade_timestamp=response["trade_timestamp"],
            opening_price=response["opening_price"],
            high_price=response["high_price"],
            low_price=response["low_price"],
            trade_price=response["trade_price"],
            prev_closing_price=response["prev_closing_price"],
            change=PriceChangeState(response["change"]),
            change_price=response["change_price"],
            change_rate=response["change_rate"],
            signed_change_price=response["signed_change_price"],
            signed_change_rate=response["signed_change_rate"],
            trade_volume=response["trade_volume"],
            acc_trade_price=response["acc_trade_price"],
            acc_trade_price_24h=response["acc_trade_price_24h"],
            acc_trade_volume=response["acc_trade_volume"],
            acc_trade_volume_24h=response["acc_trade_volume_24h"],
            highest_52_week_price=response["highest_52_week_price"],
            highest_52_week_date=response["highest_52_week_date"],
            lowest_52_week_price=response["lowest_52_week_price"],
            lowest_52_week_date=response["lowest_52_week_date"],
            timestamp=response["timestamp"],
        )
