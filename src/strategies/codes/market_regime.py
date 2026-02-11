from enum import Enum


class MarketRegime(Enum):
    """시장 국면 분류.

    시장의 현재 상태를 분류하여 적절한 트레이딩 전략을 선택하는 데 사용됩니다.
    각 국면은 가격 움직임의 패턴과 방향성을 기반으로 판단됩니다.

    Attributes:
        BULL: 상승 추세를 특징으로 하는 강세장 국면
        BEAR: 하락 추세를 특징으로 하는 약세장 국면
        SIDEWAYS: 명확한 방향성이 없는 횡보장 국면
        UNKNOWN: 시장 국면을 판단할 수 없거나 데이터가 불충분한 상태
    """

    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"
