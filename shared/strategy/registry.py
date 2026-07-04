"""전략 컴포넌트 레지스트리

진입/청산/포지션 사이징 전략을 등록하고 생성하는 레지스트리.
데코레이터 기반 자동 등록 지원.

Usage:
    # 데코레이터로 등록
    @EntryRegistry.register("bb_reversion")
    class BBReversionEntry(EntrySignalGenerator):
        ...

    # 설정으로 생성
    entry = EntryRegistry.create("bb_reversion", config_dict)

    # 팩토리로 전략 생성
    strategy = StrategyFactory.create_from_config(strategy_config)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from shared.strategy.builtin_components import (
    _BUILTIN_ENTRY_COMPONENTS as _BUILTIN_ENTRY_COMPONENTS,
)
from shared.strategy.builtin_components import (
    _BUILTIN_EXIT_COMPONENTS as _BUILTIN_EXIT_COMPONENTS,
)
from shared.strategy.builtin_components import (
    _BUILTIN_SIZER_COMPONENTS as _BUILTIN_SIZER_COMPONENTS,
)
from shared.strategy.builtin_components import (
    BuiltinComponentTable,
    register_builtin_components,
)
from shared.strategy.factory import StrategyFactory

if TYPE_CHECKING:
    from shared.strategy.base import (
        EntrySignalGenerator,
        ExitSignalGenerator,
        PositionSizer,
    )

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RegistryError(Exception):
    """레지스트리 관련 에러"""

    pass


class ComponentNotFoundError(RegistryError):
    """등록되지 않은 컴포넌트"""

    pass


class ComponentRegistry:
    """컴포넌트 레지스트리 기본 클래스

    진입/청산/포지션 사이징 전략을 등록하고 생성.

    Usage:
        @EntryRegistry.register("my_entry")
        class MyEntry(EntrySignalGenerator):
            CONFIG_CLASS = MyEntryConfig
            ...

        entry = EntryRegistry.create("my_entry", {"param1": 1, "param2": 2})
    """

    _components: dict[str, type] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type[T]], type[T]]:
        """데코레이터로 컴포넌트 등록

        Args:
            name: 컴포넌트 등록 이름

        Usage:
            @EntryRegistry.register("bb_reversion")
            class BBReversionEntry(EntrySignalGenerator):
                CONFIG_CLASS = BBReversionConfig
                ...
        """

        def decorator(component_class: type[T]) -> type[T]:
            if name in cls._components:
                logger.warning(
                    f"Overwriting existing component: {name} in {cls.__name__}"
                )
            cls._components[name] = component_class
            logger.debug(f"Registered {cls.__name__} component: {name}")
            return component_class

        return decorator

    @classmethod
    def register_class(cls, name: str, component_class: type) -> None:
        """클래스를 직접 등록

        Args:
            name: 컴포넌트 이름
            component_class: 등록할 클래스
        """
        cls._components[name] = component_class
        logger.debug(f"Registered {cls.__name__} component: {name}")

    @classmethod
    def create(cls, name: str, params: dict[str, Any]) -> Any:
        """이름으로 컴포넌트 생성

        Args:
            name: 등록된 컴포넌트 이름
            params: 설정 파라미터 (dict 또는 config class가 있으면 변환됨)

        Returns:
            생성된 컴포넌트 인스턴스

        Raises:
            ComponentNotFoundError: 등록되지 않은 컴포넌트
        """
        if name not in cls._components:
            available = list(cls._components.keys())
            raise ComponentNotFoundError(
                f"Unknown {cls.__name__} component: '{name}'. "
                f"Available: {available}"
            )

        component_class = cls._components[name]

        # CONFIG_CLASS가 있으면 params를 config 객체로 변환
        if hasattr(component_class, "CONFIG_CLASS"):
            config_class = component_class.CONFIG_CLASS
            if hasattr(config_class, "from_dict"):
                config = config_class.from_dict(params)
            else:
                config = config_class(**params)
            return component_class(config)

        # CONFIG_CLASS가 없으면 params를 직접 전달
        return component_class(params)

    @classmethod
    def get(cls, name: str) -> type:
        """등록된 컴포넌트 클래스 반환"""
        if name not in cls._components:
            raise ComponentNotFoundError(f"Unknown {cls.__name__} component: '{name}'")
        return cls._components[name]

    @classmethod
    def list_all(cls) -> list[str]:
        """등록된 모든 컴포넌트 이름"""
        return list(cls._components.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """컴포넌트 등록 여부 확인"""
        return name in cls._components

    @classmethod
    def clear(cls) -> None:
        """모든 등록 삭제 (테스트용)"""
        cls._components.clear()


class EntryRegistry(ComponentRegistry):
    """진입 전략 레지스트리

    Usage:
        @EntryRegistry.register("bb_reversion")
        class BBReversionEntry(EntrySignalGenerator):
            ...

        entry = EntryRegistry.create("bb_reversion", {"bb_period": 20})
    """

    _components: dict[str, type[EntrySignalGenerator]] = {}


class ExitRegistry(ComponentRegistry):
    """청산 전략 레지스트리

    Usage:
        @ExitRegistry.register("three_stage")
        class ThreeStageExit(ExitSignalGenerator):
            ...

        exit = ExitRegistry.create("three_stage", {"stop_loss_pct": -0.015})
    """

    _components: dict[str, type[ExitSignalGenerator]] = {}


class SizerRegistry(ComponentRegistry):
    """포지션 사이저 레지스트리

    Usage:
        @SizerRegistry.register("risk_based")
        class RiskBasedSizer(PositionSizer):
            ...

        sizer = SizerRegistry.create("risk_based", {"risk_per_trade_pct": 1.0})
    """

    _components: dict[str, type[PositionSizer]] = {}


__all__ = [
    "BuiltinComponentTable",
    "ComponentNotFoundError",
    "ComponentRegistry",
    "EntryRegistry",
    "ExitRegistry",
    "RegistryError",
    "SizerRegistry",
    "StrategyFactory",
    "register_builtin_components",
]
