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

import importlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from shared.config import ConfigLoader

if TYPE_CHECKING:
    from shared.strategy.base import (
        EntrySignalGenerator,
        ExitSignalGenerator,
        PositionSizer,
        TradingStrategy,
    )

logger = logging.getLogger(__name__)

T = TypeVar("T")

BuiltinComponentTable = tuple[tuple[str, tuple[tuple[str, str], ...], str], ...]


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


class StrategyFactory:
    """전략 팩토리

    설정 파일로부터 전략 객체 생성.
    YAML 설정만으로 전략이 생성됨.

    Usage:
        # dict에서 생성
        strategy = StrategyFactory.create(strategy_config_dict)

        # 파일에서 생성
        strategy = StrategyFactory.create_from_file("stock", "bb_reversion")

        # 모든 활성 전략 생성
        strategies = StrategyFactory.create_all("stock")
    """

    @classmethod
    def create(cls, config: dict[str, Any]) -> TradingStrategy:
        """설정 dict로부터 전략 생성

        Args:
            config: 전략 설정 dict (YAML 구조)

        Returns:
            TradingStrategy 인스턴스
        """
        from shared.strategy.base import TradingStrategy

        strategy_cfg = config.get("strategy", config)

        # 진입 로직 생성
        entry_cfg = strategy_cfg.get("entry", {})
        entry_type = entry_cfg.get("type", "default")
        entry_params = entry_cfg.get("params", {})

        if not EntryRegistry.is_registered(entry_type):
            raise ComponentNotFoundError(
                f"Entry strategy not found: '{entry_type}'. "
                f"Available: {EntryRegistry.list_all()}"
            )

        # P2-③ T7 fix: get (not pop) — entry_params may reference ConfigLoader's
        # cached dict; mutating it silently disables the gate on subsequent calls.
        gate_yaml = entry_params.get("regime_gate")
        # Filter the gate section out for the entry config (CONFIG_CLASS
        # doesn't accept it). Build a fresh dict — do NOT mutate entry_params.
        entry_params_filtered = {
            k: v for k, v in entry_params.items() if k != "regime_gate"
        }

        entry = EntryRegistry.create(entry_type, entry_params_filtered)

        # Attach GateConfig to the adapter (P2-③ T7).  The hasattr guard
        # preserves backward-compat for entry adapters that don't support gates.
        if hasattr(entry, "_gate_cfg"):
            from shared.strategy.gates.regime_gate import regime_gate_cfg_from_yaml

            entry._gate_cfg = regime_gate_cfg_from_yaml(gate_yaml)

        # 청산 로직 생성
        exit_cfg = strategy_cfg.get("exit", {})
        exit_type = exit_cfg.get("type", "default")
        exit_params = exit_cfg.get("params", {})

        if not ExitRegistry.is_registered(exit_type):
            raise ComponentNotFoundError(
                f"Exit strategy not found: '{exit_type}'. "
                f"Available: {ExitRegistry.list_all()}"
            )

        exit = ExitRegistry.create(exit_type, exit_params)

        # 포지션 사이저 생성
        position_cfg = strategy_cfg.get("position", {})
        position_type = position_cfg.get("type", "fixed")
        position_params = position_cfg.get("params", {})

        if SizerRegistry.is_registered(position_type):
            sizer = SizerRegistry.create(position_type, position_params)
        else:
            # 기본 사이저 사용
            sizer = cls._create_default_sizer(position_params)

        return TradingStrategy(
            name=strategy_cfg.get("name", "unnamed"),
            entry=entry,
            exit=exit,
            position_sizer=sizer,
        )

    @classmethod
    def _create_default_sizer(cls, params: dict[str, Any]) -> PositionSizer:
        """기본 포지션 사이저 생성"""
        from shared.strategy.position import FixedSizer, FixedSizerConfig

        config = FixedSizerConfig.from_dict(params)
        return FixedSizer(config)

    @classmethod
    def create_from_file(cls, asset_class: str, strategy_name: str) -> TradingStrategy:
        """파일 경로로부터 전략 생성

        Args:
            asset_class: 자산 유형 (stock, futures)
            strategy_name: 전략 이름

        Returns:
            TradingStrategy 인스턴스
        """
        config = ConfigLoader.load_strategy(asset_class, strategy_name)
        return cls.create(config)

    @classmethod
    def create_all(
        cls, asset_class: str | None = None, enabled_only: bool = True
    ) -> list[TradingStrategy]:
        """모든 활성화된 전략 생성

        Args:
            asset_class: 자산 유형 필터 (None이면 전체)
            enabled_only: 활성화된 전략만

        Returns:
            TradingStrategy 리스트
        """
        configs = ConfigLoader.load_all_strategies(asset_class, enabled_only)
        strategies = []

        for config in configs:
            try:
                strategy = cls.create(config)
                strategies.append(strategy)
            except Exception as e:
                strategy_name = config.get("strategy", {}).get("name", "unknown")
                logger.warning(f"Failed to create strategy '{strategy_name}': {e}")

        return strategies


_BUILTIN_ENTRY_COMPONENTS: BuiltinComponentTable = (
    (
        "shared.strategy.entry.stochrsi_trend",
        (("stochrsi_trend", "StochRSITrendEntry"),),
        "StochRSITrendEntry",
    ),
    (
        "shared.strategy.entry.mean_reversion",
        (("mean_reversion", "MeanReversionEntry"),),
        "MeanReversionEntry",
    ),
    (
        "shared.strategy.entry.breakout",
        (("breakout", "BreakoutEntry"),),
        "BreakoutEntry",
    ),
    (
        "shared.strategy.entry.opening_volume_surge",
        (("opening_volume_surge", "OpeningVolumeSurgeEntry"),),
        "OpeningVolumeSurgeEntry",
    ),
    (
        "shared.strategy.entry.volume_accumulation",
        (("volume_accumulation", "VolumeAccumulationBreakoutEntry"),),
        "VolumeAccumulationBreakoutEntry",
    ),
    (
        "shared.strategy.entry.trix_golden",
        (("trix_golden", "TrixGoldenEntry"),),
        "TrixGoldenEntry",
    ),
    (
        "shared.strategy.entry.williams_r",
        (("williams_r", "WilliamsREntry"),),
        "WilliamsREntry",
    ),
    (
        "shared.strategy.entry.macd_ema_crossover",
        (("macd_ema_crossover", "MACDEMACrossoverEntry"),),
        "MACDEMACrossoverEntry",
    ),
    (
        "shared.strategy.entry.builder_strategy",
        (("builder_v1", "BuilderStrategyEntry"),),
        "BuilderStrategyEntry",
    ),
    (
        "shared.strategy.entry.technical_consensus",
        (("technical_consensus", "TechnicalConsensusEntry"),),
        "TechnicalConsensusEntry",
    ),
    (
        "shared.strategy.entry.llm_directed_indicator",
        (("llm_directed_indicator", "LLMDirectedIndicatorEntry"),),
        "LLMDirectedIndicatorEntry",
    ),
    (
        "shared.strategy.entry.trend_pullback",
        (("trend_pullback", "TrendPullbackEntry"),),
        "TrendPullbackEntry",
    ),
    (
        "shared.strategy.entry.momentum_breakout",
        (("momentum_breakout", "MomentumBreakoutEntry"),),
        "MomentumBreakoutEntry",
    ),
    (
        "shared.strategy.entry.trend_continuation_vwap",
        (("trend_continuation_vwap", "TrendContinuationVWAPEntry"),),
        "TrendContinuationVWAPEntry",
    ),
    (
        "shared.strategy.entry.daily_pullback",
        (("daily_pullback", "DailyPullbackEntry"),),
        "DailyPullbackEntry",
    ),
    (
        "shared.strategy.entry.pattern_pullback",
        (("pattern_pullback", "PatternPullbackEntry"),),
        "PatternPullbackEntry",
    ),
    (
        "shared.strategy.entry.setup_adapters",
        (
            ("setup_a_gap_reversion", "SetupAEntryAdapter"),
            ("setup_c_event_reaction", "SetupCEntryAdapter"),
        ),
        "Setup adapters (SetupAEntryAdapter, SetupCEntryAdapter)",
    ),
    (
        "shared.strategy.entry.vr_composite",
        (("vr_composite", "VRCompositeEntry"),),
        "VRCompositeEntry",
    ),
)

_BUILTIN_EXIT_COMPONENTS: BuiltinComponentTable = (
    (
        "shared.strategy.exit.three_stage",
        (("three_stage", "ThreeStageExit"),),
        "ThreeStageExit",
    ),
    (
        "shared.strategy.exit.momentum_decay",
        (("momentum_decay", "MomentumDecayExit"),),
        "MomentumDecayExit",
    ),
    (
        "shared.strategy.exit.builder_strategy_exit",
        (("builder_v1_exit", "BuilderStrategyExit"),),
        "BuilderStrategyExit",
    ),
    (
        "shared.strategy.exit.trix_golden_exit",
        (("trix_golden_exit", "TrixGoldenExit"),),
        "TrixGoldenExit",
    ),
    (
        "shared.strategy.exit.williams_r_exit",
        (("williams_r_exit", "WilliamsRExit"),),
        "WilliamsRExit",
    ),
    (
        "shared.strategy.exit.llm_directed_indicator_exit",
        (("llm_directed_indicator_exit", "LLMDirectedIndicatorExit"),),
        "LLMDirectedIndicatorExit",
    ),
    (
        "shared.strategy.exit.mean_reversion_exit",
        (("mean_reversion_exit", "MeanReversionExit"),),
        "MeanReversionExit",
    ),
    (
        "shared.strategy.exit.atr_dynamic",
        (("atr_dynamic", "ATRDynamicExit"),),
        "ATRDynamicExit",
    ),
    (
        "shared.strategy.exit.setup_target_exit",
        (("setup_target_exit", "SetupTargetExit"),),
        "SetupTargetExit",
    ),
    (
        "shared.strategy.exit.track_a_exit",
        (("track_a_exit", "TrackAExit"),),
        "TrackAExit",
    ),
    (
        "shared.strategy.exit.chandelier_exit",
        (("chandelier_exit", "ChandelierExit"),),
        "ChandelierExit",
    ),
    (
        "shared.strategy.exit.technical_consensus_exit",
        (("technical_consensus_exit", "TechnicalConsensusExit"),),
        "TechnicalConsensusExit",
    ),
    (
        "shared.strategy.exit.vr_composite_exit",
        (("vr_composite_exit", "VRCompositeExit"),),
        "VRCompositeExit",
    ),
)

_BUILTIN_SIZER_COMPONENTS: BuiltinComponentTable = (
    (
        "shared.strategy.position.sizers",
        (("fixed_fractional_futures", "FixedFractionalFuturesSizer"),),
        "FixedFractionalFuturesSizer",
    ),
    (
        "shared.strategy.position",
        (
            ("fixed", "FixedSizer"),
            ("risk_based", "RiskBasedSizer"),
        ),
        "Position sizers",
    ),
    (
        "shared.strategy.position.llm_adaptive_sizer",
        (("llm_adaptive", "LLMAdaptiveSizer"),),
        "LLMAdaptiveSizer",
    ),
)


def _register_builtin_table(
    registry: type[ComponentRegistry], table: BuiltinComponentTable
) -> None:
    for module_path, registrations, debug_label in table:
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            logger.debug("%s not available", debug_label)
            continue

        try:
            component_classes = [
                (name, getattr(module, class_name))
                for name, class_name in registrations
            ]
        except AttributeError:
            logger.debug("%s not available", debug_label)
            continue

        for name, component_class in component_classes:
            registry.register_class(name, component_class)


def register_builtin_components() -> None:
    """내장 컴포넌트 등록

    애플리케이션 시작 시 호출하여 기본 컴포넌트 등록.
    """
    _register_builtin_table(EntryRegistry, _BUILTIN_ENTRY_COMPONENTS)
    _register_builtin_table(ExitRegistry, _BUILTIN_EXIT_COMPONENTS)
    _register_builtin_table(SizerRegistry, _BUILTIN_SIZER_COMPONENTS)

    logger.info(
        f"Registered components - "
        f"Entry: {EntryRegistry.list_all()}, "
        f"Exit: {ExitRegistry.list_all()}, "
        f"Sizer: {SizerRegistry.list_all()}"
    )
