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
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar
from urllib.parse import unquote

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
    Thread-safe: 모든 캐시 및 설정 디렉토리 작업이 thread-safe함.

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
    _ENV_VAR_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}$"
    )

    # Thread-safety locks
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()
    _dir_lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> ConfigLoader:
        if cls._instance is None:
            with cls._instance_lock:
                # Double-check after acquiring lock
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

        Thread-safe: 디렉토리 변경과 캐시 클리어가 원자적으로 수행됨.

        Args:
            path: 새 설정 디렉토리 경로
        """
        with cls._dir_lock:
            cls._config_dir = Path(path)
            # Clear cache when changing directory
            with cls._cache_lock:
                cls._cache.clear()
            logger.info(f"Config directory changed to: {cls._config_dir}")

    @classmethod
    def get_config_dir(cls) -> Path:
        """현재 설정 디렉토리 반환

        Thread-safe: 초기화가 보호됨
        """
        if cls._config_dir is None:
            with cls._dir_lock:
                # Double-check after acquiring lock
                if cls._config_dir is None:
                    cls._initialize_config_dir()
        return cls._config_dir  # type: ignore

    @classmethod
    def clear_cache(cls) -> None:
        """캐시 초기화

        Thread-safe: 다중 스레드가 동시에 호출해도 안전함.
        """
        with cls._cache_lock:
            cls._cache.clear()
        logger.debug("Config cache cleared")

    @classmethod
    def _resolve_env_vars(cls, obj: Any) -> Any:
        """Resolve ${VAR} / ${VAR:default} patterns recursively.

        Notes:
            - Only replaces when the entire string matches the pattern.
            - For ${VAR:default}, ":" introduces a default string if the env var
              is not set. Defaults are treated as raw strings.
        """
        if isinstance(obj, dict):
            return {k: cls._resolve_env_vars(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [cls._resolve_env_vars(v) for v in obj]
        if isinstance(obj, str):
            m = cls._ENV_VAR_PATTERN.match(obj.strip())
            if not m:
                return obj
            var_name = m.group(1)
            default = m.group(2) if m.group(2) is not None else ""
            return os.environ.get(var_name, default)
        return obj

    @classmethod
    def _validate_path(cls, path: str) -> Path:
        """Validate and resolve a path within config directory.

        Args:
            path: Path string to validate

        Returns:
            Resolved Path object within config directory

        Raises:
            ConfigError: If path traversal detected or path resolves outside config directory
        """
        # 1. URL 인코딩 디코드 (..%2F → ../)
        decoded_path = unquote(path)

        # 2. 백슬래시를 슬래시로 정규화 (Windows 경로 대응)
        normalized_path = decoded_path.replace("\\", "/")

        # 3. 경로 정규화 및 검증
        config_dir = cls.get_config_dir().resolve()
        try:
            full_path = (config_dir / normalized_path).resolve()
            # 4. 해결된 경로가 config_dir 내부에 있는지 확인
            full_path.relative_to(config_dir)
        except (ValueError, RuntimeError):
            # ValueError: relative_to() 실패 (경로가 config_dir 외부)
            # RuntimeError: 무한 루프 (심볼릭 링크 순환)
            raise ConfigError(
                f"Path traversal detected: {path} resolves outside config directory"
            )

        return full_path

    @classmethod
    def load(
        cls,
        path: str,
        schema: type[T] | None = None,
        use_cache: bool = True,
    ) -> T | dict[str, Any]:
        """YAML 설정 파일 로드

        Thread-safe: Double-checked locking 패턴 사용.
        Fast path: 캐시된 항목은 lock 없이 반환 (읽기 전용 안전).
        Slow path: 캐시 미스 시 lock으로 보호된 로딩.

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

        # Fast path: Check cache without lock (thread-safe read)
        if use_cache and cache_key in cls._cache:
            logger.debug(f"Config loaded from cache: {path}")
            return cls._cache[cache_key]

        # Slow path: Acquire lock for loading
        with cls._cache_lock:
            # Double-check after acquiring lock
            if use_cache and cache_key in cls._cache:
                logger.debug(f"Config loaded from cache (after lock): {path}")
                return cls._cache[cache_key]

            # Path validation (path traversal 방어)
            full_path = cls._validate_path(path)

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

            # 환경변수 치환 (${VAR} / ${VAR:default})
            data = cls._resolve_env_vars(data)

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

            # 캐시 저장 (still inside lock)
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
        """설정 파일 존재 여부 확인

        Args:
            path: 설정 파일 경로 (config 디렉토리 기준 상대 경로)

        Returns:
            파일 존재 여부

        Note:
            Path traversal 공격이 감지되면 False 반환
        """
        try:
            full_path = cls._validate_path(path)
            return full_path.exists()
        except ConfigError:
            return False

    @classmethod
    def reload(cls, path: str) -> dict[str, Any]:
        """설정 파일 강제 리로드 (캐시 무시)

        Thread-safe: 캐시 invalidation이 원자적으로 수행됨.

        Args:
            path: 설정 파일 경로 (config 디렉토리 기준 상대 경로)

        Returns:
            설정 데이터

        Raises:
            ConfigError: Path traversal 감지 시
        """
        # Path validation (outside lock - no state modification)
        cls._validate_path(path)

        cache_key_prefix = f"{path}:"

        # Invalidate cache entries for this path (inside lock)
        with cls._cache_lock:
            # Create new dict without matching keys (atomic replacement)
            cls._cache = {
                k: v for k, v in cls._cache.items() if not k.startswith(cache_key_prefix)
            }

        # Load will acquire lock again if needed
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
