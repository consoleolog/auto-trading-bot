from dataclasses import dataclass, field


@dataclass
class StrategyConfig:
    """전략 설정.

    개별 트레이딩 전략의 설정 정보를 담는 클래스입니다.
    전략의 활성화 여부, 자본 배분, 파라미터 등을 관리합니다.

    Attributes:
        id: 전략 고유 식별자
        name: 전략 이름
        capital_allocation: 이 전략에 할당된 자본 비율 (0.0 ~ 1.0, 기본값: 0.25 = 25%)
        enabled: 전략 활성화 여부 (True: 활성, False: 비활성)
        parameters: 전략별 커스텀 파라미터를 저장하는 딕셔너리
    """

    id: str
    name: str
    capital_allocation: float
    enabled: bool = True
    parameters: dict = field(default_factory=dict)
