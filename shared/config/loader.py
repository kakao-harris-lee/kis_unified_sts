"""설정 파일 로더

YAML 설정 파일을 로드하고 Pydantic 모델로 검증.
모든 설정의 단일 진입점.

Usage:
    # 전략 설정 로드
    config = ConfigLoader.load_strategy("stock", "bb_reversion")

    # 일반 설정 로드
    data = ConfigLoader.load("exit/three_stage.yaml")

    # 스키마 검증과 함께 로드
    config = ConfigLoader.load("kis/auth.yaml", KISConfig)
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import yaml

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConfigError(Exception):
    """설정 관련 에러"""

    pass


class ConfigNotFoundError(ConfigError):
    """설정 파일을 찾을 수 없음"""

    pass


class ConfigValidationError(ConfigError):
    """설정 검증 실패"""

    pass


class ConfigLoader:
    """설정 파일 로더 - 모든 설정의 단일 진입점

    Singleton 패턴으로 구현.
    설정 파일 캐싱 지원.

    Usage:
        # 전략 설정 로드
        config = ConfigLoader.load_strategy("stock", "bb_reversion")

        # YAML 파일 로드
        data = ConfigLoader.load("exit/three_stage.yaml")

        # Pydantic 모델로 검증
        from shared.config.schema import StrategyConfig
        config = ConfigLoader.load("strategies/stock/bb_reversion.yaml", StrategyConfig)
    """

    _instance: ConfigLoader | None = None
    _config_dir: Path | None = None
    _cache: dict[str, Any] = {}

    def __new__(cls) -> ConfigLoader:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialize_config_dir()
        return cls._instance

    @classmethod
    def _initialize_config_dir(cls) -> None:
        """설정 디렉토리 초기화"""
        # 환경 변수에서 설정 디렉토리 가져오기
        env_config_dir = os.environ.get("KIS_CONFIG_DIR")
        if env_config_dir:
            cls._config_dir = Path(env_config_dir)
        else:
            # 기본값: 프로젝트 루트/config
            cls._config_dir = cls._find_project_root() / "config"

        if not cls._config_dir.exists():
            logger.warning(f"Config directory not found: {cls._config_dir}")

    @classmethod
    def _find_project_root(cls) -> Path:
        """프로젝트 루트 디렉토리 찾기"""
        # pyproject.toml 또는 CLAUDE.md가 있는 디렉토리를 프로젝트 루트로 간주
        current = Path(__file__).resolve().parent
        markers = ["pyproject.toml", "CLAUDE.md", ".git"]

        while current != current.parent:
            for marker in markers:
                if (current / marker).exists():
                    return current
            current = current.parent

        # 찾지 못하면 현재 작업 디렉토리 사용
        return Path.cwd()

    @classmethod
    def set_config_dir(cls, path: str | Path) -> None:
        """설정 디렉토리 변경 (테스트용)

        Args:
            path: 새 설정 디렉토리 경로
        """
        cls._config_dir = Path(path)
        cls._cache.clear()
        logger.info(f"Config directory changed to: {cls._config_dir}")

    @classmethod
    def get_config_dir(cls) -> Path:
        """현재 설정 디렉토리 반환"""
        if cls._config_dir is None:
            cls._initialize_config_dir()
        return cls._config_dir  # type: ignore

    @classmethod
    def clear_cache(cls) -> None:
        """캐시 초기화"""
        cls._cache.clear()
        logger.debug("Config cache cleared")

    @classmethod
    def load(
        cls,
        path: str,
        schema: type[T] | None = None,
        use_cache: bool = True,
    ) -> T | dict[str, Any]:
        """YAML 설정 파일 로드

        Args:
            path: 설정 파일 경로 (config 디렉토리 기준 상대 경로)
            schema: Pydantic 모델 클래스 (선택)
            use_cache: 캐시 사용 여부

        Returns:
            설정 데이터 (dict 또는 Pydantic 모델)

        Raises:
            ConfigNotFoundError: 파일을 찾을 수 없음
            ConfigValidationError: 스키마 검증 실패

        Usage:
            # dict로 로드
            data = ConfigLoader.load("exit/three_stage.yaml")

            # Pydantic 모델로 로드
            config = ConfigLoader.load("kis/auth.yaml", KISConfig)
        """
        cache_key = f"{path}:{schema.__name__ if schema else 'dict'}"

        # 캐시 확인
        if use_cache and cache_key in cls._cache:
            logger.debug(f"Config loaded from cache: {path}")
            return cls._cache[cache_key]

        # 파일 경로 확인
        full_path = cls.get_config_dir() / path

        if not full_path.exists():
            raise ConfigNotFoundError(f"Config file not found: {full_path}")

        # YAML 로드
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse YAML file: {full_path}") from e

        if data is None:
            data = {}

        # 스키마 검증
        if schema:
            try:
                result = schema(**data)  # type: ignore
            except Exception as e:
                raise ConfigValidationError(
                    f"Config validation failed for {path}: {e}"
                ) from e
        else:
            result = data

        # 캐시 저장
        if use_cache:
            cls._cache[cache_key] = result

        logger.debug(f"Config loaded: {path}")
        return result

    @classmethod
    def load_strategy(
        cls,
        asset_class: str,
        strategy_name: str,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """전략 설정 로드 헬퍼

        Args:
            asset_class: 자산 유형 (stock, futures)
            strategy_name: 전략 이름

        Returns:
            전략 설정 dict

        Usage:
            config = ConfigLoader.load_strategy("stock", "bb_reversion")
            config = ConfigLoader.load_strategy("futures", "microstructure")
        """
        path = f"strategies/{asset_class}/{strategy_name}.yaml"
        return cls.load(path, use_cache=use_cache)  # type: ignore

    @classmethod
    def load_exit(cls, exit_type: str, use_cache: bool = True) -> dict[str, Any]:
        """청산 전략 설정 로드 헬퍼

        Args:
            exit_type: 청산 전략 유형 (three_stage, scalping 등)

        Returns:
            청산 전략 설정 dict
        """
        path = f"exit/{exit_type}.yaml"
        return cls.load(path, use_cache=use_cache)  # type: ignore

    @classmethod
    def load_all_strategies(
        cls,
        asset_class: str | None = None,
        enabled_only: bool = True,
    ) -> list[dict[str, Any]]:
        """모든 전략 설정 로드

        Args:
            asset_class: 자산 유형 필터 (None이면 전체)
            enabled_only: 활성화된 전략만 로드

        Returns:
            전략 설정 리스트
        """
        strategies: list[dict[str, Any]] = []

        # 검색할 디렉토리 목록
        search_dirs: list[Path] = []
        config_dir = cls.get_config_dir()

        if asset_class:
            search_dirs.append(config_dir / "strategies" / asset_class)
        else:
            strategies_dir = config_dir / "strategies"
            if strategies_dir.exists():
                search_dirs.extend(
                    d for d in strategies_dir.iterdir() if d.is_dir()
                )

        # 각 디렉토리에서 YAML 파일 로드
        for dir_path in search_dirs:
            if not dir_path.exists():
                continue

            for yaml_file in dir_path.glob("*.yaml"):
                try:
                    config = cls.load(
                        str(yaml_file.relative_to(config_dir)),
                        use_cache=True,
                    )

                    # enabled 필터
                    if enabled_only:
                        strategy_config = config.get("strategy", {})
                        if not strategy_config.get("enabled", True):
                            continue

                    strategies.append(config)  # type: ignore
                except Exception as e:
                    logger.warning(f"Failed to load strategy config {yaml_file}: {e}")

        return strategies

    @classmethod
    def list_strategies(cls, asset_class: str | None = None) -> list[str]:
        """사용 가능한 전략 이름 목록

        Args:
            asset_class: 자산 유형 필터

        Returns:
            전략 이름 리스트
        """
        strategy_names: list[str] = []
        config_dir = cls.get_config_dir()

        search_dirs: list[Path] = []
        if asset_class:
            search_dirs.append(config_dir / "strategies" / asset_class)
        else:
            strategies_dir = config_dir / "strategies"
            if strategies_dir.exists():
                search_dirs.extend(
                    d for d in strategies_dir.iterdir() if d.is_dir()
                )

        for dir_path in search_dirs:
            if not dir_path.exists():
                continue

            for yaml_file in dir_path.glob("*.yaml"):
                strategy_names.append(yaml_file.stem)

        return sorted(strategy_names)

    @classmethod
    def exists(cls, path: str) -> bool:
        """설정 파일 존재 여부 확인"""
        full_path = cls.get_config_dir() / path
        return full_path.exists()

    @classmethod
    def reload(cls, path: str) -> dict[str, Any]:
        """설정 파일 강제 리로드 (캐시 무시)"""
        cache_key_prefix = f"{path}:"
        # 해당 경로의 캐시 삭제
        cls._cache = {
            k: v for k, v in cls._cache.items() if not k.startswith(cache_key_prefix)
        }
        return cls.load(path, use_cache=True)  # type: ignore


# 편의 함수
def load_config(path: str, schema: type[T] | None = None) -> T | dict[str, Any]:
    """설정 로드 편의 함수"""
    return ConfigLoader.load(path, schema)


def load_strategy_config(asset_class: str, strategy_name: str) -> dict[str, Any]:
    """전략 설정 로드 편의 함수"""
    return ConfigLoader.load_strategy(asset_class, strategy_name)


@lru_cache(maxsize=32)
def get_strategy_names(asset_class: str | None = None) -> tuple[str, ...]:
    """전략 이름 목록 (캐시됨)"""
    return tuple(ConfigLoader.list_strategies(asset_class))
