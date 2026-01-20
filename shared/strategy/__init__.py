"""전략 프레임워크

진입/청산/포지션 사이징 전략 추상화 계층.

Usage:
    from shared.strategy import (
        EntrySignalGenerator,
        ExitSignalGenerator,
        StrategyFactory,
        EntryRegistry,
        ExitRegistry,
    )

    # 데코레이터로 등록
    @EntryRegistry.register("my_entry")
    class MyEntry(EntrySignalGenerator):
        ...

    # 팩토리로 전략 생성
    strategy = StrategyFactory.create_from_file("stock", "bb_reversion")
"""

from shared.strategy.base import (
    EntryContext,
    EntrySignalGenerator,
    ExitContext,
    ExitSignalGenerator,
    PositionSizer,
    TradingStrategy,
)
from shared.strategy.registry import (
    ComponentNotFoundError,
    EntryRegistry,
    ExitRegistry,
    RegistryError,
    SizerRegistry,
    StrategyFactory,
    register_builtin_components,
)

__all__ = [
    # Base Classes
    "EntrySignalGenerator",
    "ExitSignalGenerator",
    "PositionSizer",
    "TradingStrategy",
    "EntryContext",
    "ExitContext",
    # Registry
    "EntryRegistry",
    "ExitRegistry",
    "SizerRegistry",
    "StrategyFactory",
    "RegistryError",
    "ComponentNotFoundError",
    "register_builtin_components",
]
