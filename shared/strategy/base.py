"""전략 기본 인터페이스

모든 진입/청산/포지션 사이징 전략의 추상 기본 클래스.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar

if TYPE_CHECKING:
    from shared.models.position import Position
    from shared.models.signal import ExitSignal, Signal

TConfig = TypeVar("TConfig")


@dataclass
class EntryContext:
    """진입 판단에 필요한 컨텍스트

    Attributes:
        market_data: 시장 데이터 (OHLCV 등)
        indicators: 계산된 지표 값
        current_positions: 현재 보유 포지션 목록
        timestamp: 현재 시간
        metadata: 추가 메타데이터
    """

    market_data: dict[str, Any] = field(default_factory=dict)
    indicators: dict[str, Any] = field(default_factory=dict)
    current_positions: list["Position"] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExitContext:
    """청산 판단에 필요한 컨텍스트

    Attributes:
        position: 청산 대상 포지션
        market_data: 시장 데이터
        indicators: 계산된 지표 값
        timestamp: 현재 시간
        market_state: 시장 상태 (MarketClassifier 결과)
        metadata: 추가 메타데이터
    """

    position: "Position"
    market_data: dict[str, Any] = field(default_factory=dict)
    indicators: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    market_state: Optional[Any] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EntrySignalGenerator(ABC, Generic[TConfig]):
    """진입 시그널 생성기 추상 클래스

    모든 진입 로직은 이 인터페이스를 구현해야 함.
    """

    def __init__(self, config: TConfig):
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self):
        """설정 유효성 검증"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """전략 이름"""
        pass

    @property
    @abstractmethod
    def required_indicators(self) -> list[str]:
        """필요한 지표 목록 반환"""
        pass

    @abstractmethod
    async def generate(self, context: EntryContext) -> Optional["Signal"]:
        """진입 시그널 생성

        Returns:
            Signal if entry condition met, None otherwise
        """
        pass

    def get_config(self) -> dict[str, Any]:
        """설정 반환"""
        if hasattr(self.config, "__dict__"):
            return vars(self.config)
        return {}


class ExitSignalGenerator(ABC, Generic[TConfig]):
    """청산 시그널 생성기 추상 클래스

    모든 청산 로직은 이 인터페이스를 구현해야 함.
    """

    def __init__(self, config: TConfig):
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self):
        """설정 유효성 검증"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """전략 이름"""
        pass

    @property
    def version(self) -> str:
        """전략 버전"""
        return "1.0"

    @abstractmethod
    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional["ExitSignal"]]:
        """청산 여부 판단

        Returns:
            (should_exit: bool, signal: ExitSignal | None)
        """
        pass

    @abstractmethod
    async def scan_positions(
        self,
        positions: list["Position"],
        market_data: dict[str, Any],
        market_state: Optional[Any] = None,
    ) -> list["ExitSignal"]:
        """여러 포지션에 대해 청산 시그널 스캔

        Returns:
            청산 대상 포지션의 ExitSignal 리스트
        """
        pass

    def update_state(self, context: ExitContext):
        """포지션 상태 업데이트 (트레일링 등)"""
        pass

    def get_config(self) -> dict[str, Any]:
        """설정 반환"""
        if hasattr(self.config, "__dict__"):
            return vars(self.config)
        return {}


class PositionSizer(ABC, Generic[TConfig]):
    """포지션 사이징 추상 클래스"""

    def __init__(self, config: TConfig):
        self.config = config

    @abstractmethod
    def calculate(
        self,
        signal: "Signal",
        account_balance: float,
        current_positions: list["Position"],
    ) -> int:
        """포지션 크기 계산

        Returns:
            quantity: 매매 수량
        """
        pass


class TradingStrategy:
    """트레이딩 전략 - 진입/청산/사이징 조합

    이 클래스는 구체적인 로직을 포함하지 않고,
    주입받은 컴포넌트들을 조합하여 사용.
    """

    def __init__(
        self,
        name: str,
        entry: EntrySignalGenerator,
        exit: ExitSignalGenerator,
        position_sizer: PositionSizer,
    ):
        self.name = name
        self.entry = entry
        self.exit = exit
        self.position_sizer = position_sizer

    @property
    def required_indicators(self) -> list[str]:
        """필요한 모든 지표"""
        return self.entry.required_indicators

    async def check_entry(self, context: EntryContext) -> Optional["Signal"]:
        """진입 조건 확인"""
        return await self.entry.generate(context)

    async def check_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional["ExitSignal"]]:
        """청산 조건 확인"""
        return await self.exit.should_exit(context)

    def calculate_position_size(
        self,
        signal: "Signal",
        account_balance: float,
        current_positions: list["Position"],
    ) -> int:
        """포지션 크기 계산"""
        return self.position_sizer.calculate(
            signal, account_balance, current_positions
        )
