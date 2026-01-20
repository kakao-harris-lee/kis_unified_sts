"""
KIS API 인증 관리 모듈 (통합)

quant_moment_sts와 kospi_mini_sts의 인증 로직을 통합.
- 주식/선물 모두 지원
- Sync/Async 모두 지원
- 파일 기반 토큰 캐싱 (24시간 재사용)
- 실전/모의 환경 지원
- 설정 기반 (하드코딩 금지)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

if TYPE_CHECKING:
    import aiohttp
    import requests

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class KISAuthConfig:
    """KIS API 인증 설정

    YAML 설정 파일에서 로드되는 인증 관련 설정.

    Attributes:
        app_key: KIS API 앱 키
        app_secret: KIS API 앱 시크릿
        is_real: 실전투자 여부 (False: 모의투자)
        token_cache_dir: 토큰 캐시 파일 저장 디렉토리
        token_expiry_buffer_seconds: 토큰 만료 전 갱신 버퍼 (초)
        request_timeout_seconds: API 요청 타임아웃 (초)
    """

    app_key: str = ""
    app_secret: str = ""
    is_real: bool = True
    token_cache_dir: Optional[str] = None
    token_expiry_buffer_seconds: int = 600  # 10분 전 갱신
    request_timeout_seconds: int = 30

    def __post_init__(self):
        # 환경변수 폴백
        if not self.app_key:
            self.app_key = os.getenv("KIS_APP_KEY", "")
        if not self.app_secret:
            self.app_secret = os.getenv("KIS_APP_SECRET", "")

    @property
    def base_url(self) -> str:
        """API 기본 URL (실전/모의 환경에 따라 다름)"""
        if self.is_real:
            return "https://openapi.koreainvestment.com:9443"
        return "https://openapivts.koreainvestment.com:29443"

    @property
    def token_cache_path(self) -> Path:
        """토큰 캐시 파일 경로"""
        if self.token_cache_dir:
            cache_dir = Path(self.token_cache_dir)
        else:
            # 기본값: 현재 작업 디렉토리
            cache_dir = Path.cwd()

        # 실전/모의 구분하여 별도 파일 사용
        suffix = "real" if self.is_real else "mock"
        return cache_dir / f".kis_token_{suffix}"


# =============================================================================
# Token Cache
# =============================================================================


@dataclass
class TokenCache:
    """토큰 캐시 데이터"""

    app_key: str
    token: str
    expires_at: float  # Unix timestamp
    issued_at: str  # ISO format datetime

    def is_valid(self, buffer_seconds: int = 60) -> bool:
        """토큰이 유효한지 확인 (버퍼 시간 고려)"""
        return time.time() < (self.expires_at - buffer_seconds)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "app_key": self.app_key,
            "token": self.token,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenCache:
        """딕셔너리에서 생성"""
        return cls(
            app_key=data.get("app_key", ""),
            token=data.get("token", ""),
            expires_at=data.get("expires_at", 0),
            issued_at=data.get("issued_at", ""),
        )


# =============================================================================
# Circuit Breaker (Optional)
# =============================================================================


@dataclass
class CircuitBreakerConfig:
    """Circuit Breaker 설정"""

    failure_threshold: int = 5  # 연속 실패 임계값
    recovery_timeout_seconds: int = 60  # 복구 대기 시간
    half_open_max_calls: int = 3  # Half-open 상태에서 허용 호출 수


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """간단한 Circuit Breaker 구현"""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._get_state()

    def _get_state(self) -> str:
        """현재 상태 계산 (락 필요)"""
        if self._state == CircuitState.OPEN:
            # 복구 타임아웃 지났으면 Half-Open으로 전환
            if (
                self._last_failure_time
                and time.time() - self._last_failure_time
                > self.config.recovery_timeout_seconds
            ):
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def record_success(self):
        """성공 기록"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            else:
                self._failure_count = 0

    def record_failure(self):
        """실패 기록"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker opened after {self._failure_count} failures"
                )

    def can_execute(self) -> bool:
        """실행 가능 여부"""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True
        return False


class CircuitOpenError(Exception):
    """Circuit이 열려있어 요청 불가"""

    pass


# =============================================================================
# KIS Auth Manager
# =============================================================================


class KISAuthManager:
    """KIS API 인증 관리자 (통합)

    주식/선물 모두 지원하는 통합 인증 관리자.

    Features:
        - Sync/Async 모두 지원
        - 파일 기반 토큰 캐싱 (24시간 재사용)
        - 실전/모의 환경 지원
        - app_key 검증으로 잘못된 캐시 사용 방지
        - Circuit Breaker 패턴 지원 (선택적)

    Usage (Sync):
        >>> config = KISAuthConfig(app_key="...", app_secret="...")
        >>> auth = KISAuthManager(config)
        >>> token = auth.get_token()
        >>> headers = auth.get_auth_headers()

    Usage (Async):
        >>> async with KISAuthManager(config) as auth:
        ...     token = await auth.get_token_async()
        ...     headers = await auth.get_auth_headers_async()
    """

    _instances: dict[str, KISAuthManager] = {}
    _instance_lock = threading.Lock()

    def __init__(
        self,
        config: KISAuthConfig,
        circuit_breaker: Optional[CircuitBreaker] = None,
        use_singleton: bool = True,
    ):
        """
        Args:
            config: 인증 설정
            circuit_breaker: Circuit Breaker 인스턴스 (선택적)
            use_singleton: 싱글톤 패턴 사용 여부
        """
        self.config = config
        self._circuit = circuit_breaker
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._lock = threading.Lock()
        self._async_lock: Optional[asyncio.Lock] = None

        # Async session (lazy init)
        self._async_session: Optional[aiohttp.ClientSession] = None

        # 파일 캐시에서 토큰 로드
        self._load_from_cache()

    @classmethod
    def get_instance(
        cls,
        config: KISAuthConfig,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> KISAuthManager:
        """싱글톤 인스턴스 반환 (app_key + is_real 기준)"""
        key = f"{config.app_key}_{config.is_real}"

        with cls._instance_lock:
            if key not in cls._instances:
                cls._instances[key] = cls(
                    config, circuit_breaker, use_singleton=False
                )
            return cls._instances[key]

    @classmethod
    def clear_instances(cls):
        """모든 싱글톤 인스턴스 초기화 (테스트용)"""
        with cls._instance_lock:
            cls._instances.clear()

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    def _load_from_cache(self) -> bool:
        """파일 캐시에서 토큰 로드"""
        cache_path = self.config.token_cache_path

        if not cache_path.exists():
            return False

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)

            cache = TokenCache.from_dict(data)

            # app_key 검증 (다른 계정 토큰 사용 방지)
            if cache.app_key != self.config.app_key:
                logger.debug("Token cache app_key mismatch, ignoring")
                return False

            # 유효성 검증
            if not cache.is_valid(self.config.token_expiry_buffer_seconds):
                logger.debug("Token cache expired, will refresh")
                return False

            self._token = cache.token
            self._expires_at = cache.expires_at

            remaining = int(cache.expires_at - time.time())
            logger.info(
                f"[KISAuth] Loaded token from cache "
                f"(expires in {remaining}s, ~{remaining // 3600}h)"
            )
            return True

        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.warning(f"[KISAuth] Failed to load token cache: {e}")
            return False

    def _save_to_cache(self):
        """토큰을 파일 캐시에 저장"""
        cache_path = self.config.token_cache_path

        try:
            cache = TokenCache(
                app_key=self.config.app_key,
                token=self._token or "",
                expires_at=self._expires_at,
                issued_at=datetime.now().isoformat(),
            )

            # 디렉토리 생성
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            with open(cache_path, "w") as f:
                json.dump(cache.to_dict(), f, indent=2)

            # 보안을 위해 파일 권한 설정 (소유자만 읽기/쓰기)
            os.chmod(cache_path, 0o600)

            logger.debug(f"[KISAuth] Token cached to {cache_path}")

        except IOError as e:
            logger.warning(f"[KISAuth] Failed to save token cache: {e}")

    def invalidate(self):
        """토큰 무효화 (재발급 강제)"""
        with self._lock:
            self._token = None
            self._expires_at = 0

            cache_path = self.config.token_cache_path
            if cache_path.exists():
                cache_path.unlink()
                logger.info("[KISAuth] Token invalidated")

    # -------------------------------------------------------------------------
    # Token Validation
    # -------------------------------------------------------------------------

    def _is_token_valid(self) -> bool:
        """현재 토큰이 유효한지 확인"""
        if not self._token:
            return False
        return time.time() < (
            self._expires_at - self.config.token_expiry_buffer_seconds
        )

    def _check_circuit(self):
        """Circuit Breaker 상태 확인"""
        if self._circuit and not self._circuit.can_execute():
            raise CircuitOpenError(
                "Circuit breaker is open, cannot issue token"
            )

    # -------------------------------------------------------------------------
    # Sync API
    # -------------------------------------------------------------------------

    def get_token(self) -> str:
        """토큰 반환 (필요시 동기 갱신)

        Returns:
            유효한 액세스 토큰

        Raises:
            ValueError: 인증 정보 누락 또는 토큰 발급 실패
            CircuitOpenError: Circuit이 열려있어 요청 불가
        """
        with self._lock:
            if self._is_token_valid():
                return self._token  # type: ignore

            return self._issue_token_sync()

    def _issue_token_sync(self) -> str:
        """토큰 동기 발급"""
        import requests

        self._check_circuit()

        if not self.config.app_key or not self.config.app_secret:
            raise ValueError("KIS_APP_KEY and KIS_APP_SECRET must be set")

        url = f"{self.config.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=self.config.request_timeout_seconds,
            )
            data = resp.json()

            if "access_token" not in data:
                raise ValueError(f"Token issue failed: {data}")

            self._token = data["access_token"]
            expires_in = int(data.get("expires_in", 86400))  # 기본 24시간
            self._expires_at = time.time() + expires_in

            logger.info(
                f"[KISAuth] Token issued (expires in {expires_in}s, "
                f"~{expires_in // 3600}h)"
            )

            # 캐시 저장
            self._save_to_cache()

            if self._circuit:
                self._circuit.record_success()

            return self._token

        except Exception as e:
            if self._circuit:
                self._circuit.record_failure()
            logger.error(f"[KISAuth] Token issue failed: {e}")
            raise

    def get_auth_headers(self) -> dict[str, str]:
        """인증 헤더 반환 (Sync)

        Returns:
            API 요청에 필요한 인증 헤더 딕셔너리
        """
        token = self.get_token()
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
        }

    # -------------------------------------------------------------------------
    # Async API
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> KISAuthManager:
        """Async context manager 진입"""
        await self._ensure_async_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager 종료"""
        await self.close_async()

    async def _ensure_async_session(self):
        """Async 세션 보장"""
        if self._async_session is None:
            import aiohttp

            self._async_session = aiohttp.ClientSession()
            logger.debug("[KISAuth] Async session created")

        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

    async def close_async(self):
        """Async 리소스 정리"""
        if self._async_session:
            await self._async_session.close()
            self._async_session = None
            logger.debug("[KISAuth] Async session closed")

    async def get_token_async(self) -> str:
        """토큰 반환 (필요시 비동기 갱신)

        Returns:
            유효한 액세스 토큰

        Raises:
            ValueError: 인증 정보 누락 또는 토큰 발급 실패
            CircuitOpenError: Circuit이 열려있어 요청 불가
        """
        await self._ensure_async_session()

        async with self._async_lock:  # type: ignore
            if self._is_token_valid():
                return self._token  # type: ignore

            return await self._issue_token_async()

    async def _issue_token_async(self) -> str:
        """토큰 비동기 발급"""
        self._check_circuit()

        if not self.config.app_key or not self.config.app_secret:
            raise ValueError("KIS_APP_KEY and KIS_APP_SECRET must be set")

        url = f"{self.config.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
        }

        try:
            async with self._async_session.post(  # type: ignore
                url,
                json=payload,
                timeout=self.config.request_timeout_seconds,
            ) as resp:
                data = await resp.json()

                if "access_token" not in data:
                    raise ValueError(f"Token issue failed: {data}")

                self._token = data["access_token"]
                expires_in = int(data.get("expires_in", 86400))
                self._expires_at = time.time() + expires_in

                logger.info(
                    f"[KISAuth] Token issued (expires in {expires_in}s, "
                    f"~{expires_in // 3600}h)"
                )

                # 캐시 저장
                self._save_to_cache()

                if self._circuit:
                    self._circuit.record_success()

                return self._token

        except Exception as e:
            if self._circuit:
                self._circuit.record_failure()
            logger.error(f"[KISAuth] Token issue failed: {e}")
            raise

    async def get_auth_headers_async(self) -> dict[str, str]:
        """인증 헤더 반환 (Async)

        Returns:
            API 요청에 필요한 인증 헤더 딕셔너리
        """
        token = await self.get_token_async()
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
        }


# =============================================================================
# Factory Functions
# =============================================================================


def create_auth_manager(
    app_key: Optional[str] = None,
    app_secret: Optional[str] = None,
    is_real: bool = True,
    use_circuit_breaker: bool = False,
    use_singleton: bool = True,
) -> KISAuthManager:
    """KISAuthManager 팩토리 함수

    Args:
        app_key: KIS API 앱 키 (환경변수 폴백)
        app_secret: KIS API 앱 시크릿 (환경변수 폴백)
        is_real: 실전투자 여부
        use_circuit_breaker: Circuit Breaker 사용 여부
        use_singleton: 싱글톤 패턴 사용 여부

    Returns:
        KISAuthManager 인스턴스
    """
    config = KISAuthConfig(
        app_key=app_key or "",
        app_secret=app_secret or "",
        is_real=is_real,
    )

    circuit = None
    if use_circuit_breaker:
        circuit = CircuitBreaker(CircuitBreakerConfig())

    if use_singleton:
        return KISAuthManager.get_instance(config, circuit)

    return KISAuthManager(config, circuit, use_singleton=False)
