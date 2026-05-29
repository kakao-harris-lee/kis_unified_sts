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
        entry_params_filtered = {k: v for k, v in entry_params.items() if k != "regime_gate"}

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


def register_builtin_components() -> None:
    """내장 컴포넌트 등록

    애플리케이션 시작 시 호출하여 기본 컴포넌트 등록.
    """
    # Entry 전략 등록
    try:
        from shared.strategy.entry.stochrsi_trend import StochRSITrendEntry

        EntryRegistry.register_class("stochrsi_trend", StochRSITrendEntry)
    except ImportError:
        logger.debug("StochRSITrendEntry not available")

    try:
        from shared.strategy.entry.mean_reversion import MeanReversionEntry

        EntryRegistry.register_class("mean_reversion", MeanReversionEntry)
    except ImportError:
        logger.debug("MeanReversionEntry not available")

    try:
        from shared.strategy.entry.breakout import BreakoutEntry

        EntryRegistry.register_class("breakout", BreakoutEntry)
    except ImportError:
        logger.debug("BreakoutEntry not available")

    try:
        from shared.strategy.entry.opening_volume_surge import OpeningVolumeSurgeEntry

        EntryRegistry.register_class("opening_volume_surge", OpeningVolumeSurgeEntry)
    except ImportError:
        logger.debug("OpeningVolumeSurgeEntry not available")

    try:
        from shared.strategy.entry.volume_accumulation import (
            VolumeAccumulationBreakoutEntry,
        )

        EntryRegistry.register_class(
            "volume_accumulation", VolumeAccumulationBreakoutEntry
        )
    except ImportError:
        logger.debug("VolumeAccumulationBreakoutEntry not available")

    try:
        from shared.strategy.entry.trix_golden import TrixGoldenEntry

        EntryRegistry.register_class("trix_golden", TrixGoldenEntry)
    except ImportError:
        logger.debug("TrixGoldenEntry not available")

    try:
        from shared.strategy.entry.williams_r import WilliamsREntry

        EntryRegistry.register_class("williams_r", WilliamsREntry)
    except ImportError:
        logger.debug("WilliamsREntry not available")

    try:
        from shared.strategy.entry.macd_ema_crossover import MACDEMACrossoverEntry

        EntryRegistry.register_class("macd_ema_crossover", MACDEMACrossoverEntry)
    except ImportError:
        logger.debug("MACDEMACrossoverEntry not available")

    try:
        from shared.strategy.entry.builder_strategy import BuilderStrategyEntry

        EntryRegistry.register_class("builder_v1", BuilderStrategyEntry)
    except ImportError:
        logger.debug("BuilderStrategyEntry not available")

    try:
        from shared.strategy.entry.technical_consensus import TechnicalConsensusEntry

        EntryRegistry.register_class("technical_consensus", TechnicalConsensusEntry)
    except ImportError:
        logger.debug("TechnicalConsensusEntry not available")

    try:
        from shared.strategy.entry.llm_directed_indicator import (
            LLMDirectedIndicatorEntry,
        )

        EntryRegistry.register_class(
            "llm_directed_indicator", LLMDirectedIndicatorEntry
        )
    except ImportError:
        logger.debug("LLMDirectedIndicatorEntry not available")

    try:
        from shared.strategy.entry.trend_pullback import TrendPullbackEntry

        EntryRegistry.register_class("trend_pullback", TrendPullbackEntry)
    except ImportError:
        logger.debug("TrendPullbackEntry not available")

    try:
        from shared.strategy.entry.momentum_breakout import MomentumBreakoutEntry

        EntryRegistry.register_class("momentum_breakout", MomentumBreakoutEntry)
    except ImportError:
        logger.debug("MomentumBreakoutEntry not available")

    try:
        from shared.strategy.entry.trend_continuation_vwap import (
            TrendContinuationVWAPEntry,
        )

        EntryRegistry.register_class(
            "trend_continuation_vwap", TrendContinuationVWAPEntry
        )
    except ImportError:
        logger.debug("TrendContinuationVWAPEntry not available")

    try:
        from shared.strategy.entry.daily_pullback import DailyPullbackEntry

        EntryRegistry.register_class("daily_pullback", DailyPullbackEntry)
    except ImportError:
        logger.debug("DailyPullbackEntry not available")

    try:
        from shared.strategy.entry.pattern_pullback import PatternPullbackEntry

        EntryRegistry.register_class("pattern_pullback", PatternPullbackEntry)
    except ImportError:
        logger.debug("PatternPullbackEntry not available")

    try:
        from shared.strategy.entry.rl_mppo import RLMPPOEntry

        EntryRegistry.register_class("rl_mppo", RLMPPOEntry)
    except ImportError:
        logger.debug("RLMPPOEntry not available")

    try:
        from shared.strategy.entry.setup_adapters import (
            SetupAEntryAdapter,
            SetupCEntryAdapter,
        )

        EntryRegistry.register_class("setup_a_gap_reversion", SetupAEntryAdapter)
        EntryRegistry.register_class("setup_c_event_reaction", SetupCEntryAdapter)
    except ImportError:
        logger.debug(
            "Setup adapters (SetupAEntryAdapter, SetupCEntryAdapter) not available"
        )

    # Exit 전략 등록
    try:
        from shared.strategy.exit.three_stage import ThreeStageExit

        ExitRegistry.register_class("three_stage", ThreeStageExit)
    except ImportError:
        logger.debug("ThreeStageExit not available")

    try:
        from shared.strategy.exit.momentum_decay import MomentumDecayExit

        ExitRegistry.register_class("momentum_decay", MomentumDecayExit)
    except ImportError:
        logger.debug("MomentumDecayExit not available")

    try:
        from shared.strategy.exit.builder_strategy_exit import BuilderStrategyExit

        ExitRegistry.register_class("builder_v1_exit", BuilderStrategyExit)
    except ImportError:
        logger.debug("BuilderStrategyExit not available")

    try:
        from shared.strategy.exit.rl_mppo_exit import RLMPPOExit

        ExitRegistry.register_class("rl_mppo_exit", RLMPPOExit)
    except ImportError:
        logger.debug("RLMPPOExit not available")

    try:
        from shared.strategy.exit.trix_golden_exit import TrixGoldenExit

        ExitRegistry.register_class("trix_golden_exit", TrixGoldenExit)
    except ImportError:
        logger.debug("TrixGoldenExit not available")

    try:
        from shared.strategy.exit.williams_r_exit import WilliamsRExit

        ExitRegistry.register_class("williams_r_exit", WilliamsRExit)
    except ImportError:
        logger.debug("WilliamsRExit not available")

    try:
        from shared.strategy.exit.llm_directed_indicator_exit import (
            LLMDirectedIndicatorExit,
        )

        ExitRegistry.register_class(
            "llm_directed_indicator_exit", LLMDirectedIndicatorExit
        )
    except ImportError:
        logger.debug("LLMDirectedIndicatorExit not available")

    try:
        from shared.strategy.exit.mean_reversion_exit import MeanReversionExit

        ExitRegistry.register_class("mean_reversion_exit", MeanReversionExit)
    except ImportError:
        logger.debug("MeanReversionExit not available")

    try:
        from shared.strategy.exit.atr_dynamic import ATRDynamicExit

        ExitRegistry.register_class("atr_dynamic", ATRDynamicExit)
    except ImportError:
        logger.debug("ATRDynamicExit not available")

    try:
        from shared.strategy.exit.chandelier_exit import ChandelierExit

        ExitRegistry.register_class("chandelier_exit", ChandelierExit)
    except ImportError:
        logger.debug("ChandelierExit not available")

    try:
        from shared.strategy.exit.technical_consensus_exit import TechnicalConsensusExit

        ExitRegistry.register_class("technical_consensus_exit", TechnicalConsensusExit)
    except ImportError:
        logger.debug("TechnicalConsensusExit not available")

    try:
        from shared.strategy.entry.vr_composite import VRCompositeEntry

        EntryRegistry.register_class("vr_composite", VRCompositeEntry)
    except ImportError:
        logger.debug("VRCompositeEntry not available")

    try:
        from shared.strategy.exit.vr_composite_exit import VRCompositeExit

        ExitRegistry.register_class("vr_composite_exit", VRCompositeExit)
    except ImportError:
        logger.debug("VRCompositeExit not available")

    # Position Sizer 등록
    try:
        from shared.strategy.position import FixedSizer, RiskBasedSizer

        SizerRegistry.register_class("fixed", FixedSizer)
        SizerRegistry.register_class("risk_based", RiskBasedSizer)
    except ImportError:
        logger.debug("Position sizers not available")

    try:
        from shared.strategy.position.llm_adaptive_sizer import LLMAdaptiveSizer

        SizerRegistry.register_class("llm_adaptive", LLMAdaptiveSizer)
    except ImportError:
        logger.debug("LLMAdaptiveSizer not available")

    logger.info(
        f"Registered components - "
        f"Entry: {EntryRegistry.list_all()}, "
        f"Exit: {ExitRegistry.list_all()}, "
        f"Sizer: {SizerRegistry.list_all()}"
    )
