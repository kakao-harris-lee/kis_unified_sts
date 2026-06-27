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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from shared.resilience import CircuitBreaker, CircuitBreakerConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import aiohttp

_T = TypeVar("_T")

logger = logging.getLogger(__name__)

TOKEN_EXPIRED_MSG_CODES = {"EGW00123"}
TOKEN_EXPIRED_MESSAGE_SNIPPETS = (
    "기간이 만료된 token",
    "expired token",
    "token expired",
)


def is_token_expired_error(payload: Any) -> bool:
    """Return True when a KIS response says the access token is expired.

    KIS can reject a token before our local cache timestamp reaches the refresh
    buffer, especially when another process reissues a token for the same app.
    Runtime callers use this helper to invalidate the local cache and retry
    once with a freshly issued token.
    """
    if isinstance(payload, dict):
        msg_cd = str(payload.get("msg_cd") or payload.get("message") or "")
        if msg_cd in TOKEN_EXPIRED_MSG_CODES:
            return True
        text = json.dumps(payload, ensure_ascii=False)
    else:
        text = str(payload or "")

    lowered = text.lower()
    return any(snippet.lower() in lowered for snippet in TOKEN_EXPIRED_MESSAGE_SNIPPETS)


async def retry_once_on_token_expiry(
    request_fn: Callable[[int], Awaitable[_T]],
    auth_manager: Any,
    *,
    is_expired: Callable[[_T], bool],
    context: str = "KIS request",
) -> _T:
    """Run an async KIS request, retrying exactly once on a server-side token expiry.

    Consolidates the invalidate-and-retry orchestration shared by the runtime
    callers (balance inquiry, order execution) so the "retry once" contract is
    defined in one place instead of being copy-pasted per call site.

    Args:
        request_fn: Coroutine factory invoked with the attempt index (``0`` for
            the first call, ``1`` for the retry). It must fetch/build fresh auth
            headers on each call so the reissued token is actually used on retry.
        auth_manager: Object whose cached token is cleared before the retry. The
            retry only fires when it exposes a callable ``invalidate``; otherwise
            resending the same stale token is futile and the first result stands.
        is_expired: Predicate on the request result returning ``True`` when the
            response indicates the access token expired.
        context: Human-readable label used in the warning log line.

    Returns:
        The first result when it is not an expiry or cannot be retried, otherwise
        the result of the single retry.
    """
    result = await request_fn(0)
    if not is_expired(result):
        return result

    invalidate = getattr(auth_manager, "invalidate", None)
    if not callable(invalidate):
        return result

    logger.warning(
        "%s token expired; invalidating cached token and retrying once", context
    )
    invalidate()
    return await request_fn(1)


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
    token_cache_dir: str | None = None
    token_expiry_buffer_seconds: int = 600  # 10분 전 갱신
    request_timeout_seconds: int = 30

    def __post_init__(self):
        # 환경변수 폴백
        if not self.app_key:
            self.app_key = os.getenv("KIS_APP_KEY", "")
        if not self.app_secret:
            self.app_secret = os.getenv("KIS_APP_SECRET", "")
        if not self.token_cache_dir:
            self.token_cache_dir = os.getenv("KIS_TOKEN_CACHE_DIR") or None

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
# Circuit Breaker Exceptions
# =============================================================================


class CircuitOpenError(Exception):
    """Circuit이 열려있어 요청 불가"""

    pass


# =============================================================================
# Secure Token Cache Save
# =============================================================================


def _save_token_cache_secure(cache: TokenCache, cache_path: Path) -> None:
    """토큰 캐시를 안전한 권한으로 atomic하게 저장

    SECURITY: 파일을 default 권한으로 생성한 후 chmod하면
    그 사이 world-readable 상태로 노출되는 race condition 발생.
    os.open()으로 파일 생성과 동시에 0o600 권한 설정.

    Args:
        cache: 저장할 토큰 캐시
        cache_path: 저장 경로

    Raises:
        OSError: 파일 생성/쓰기 실패
    """
    cache_path = Path(cache_path)

    # os.open으로 atomic하게 파일 생성 및 권한 설정
    # O_CREAT: 파일이 없으면 생성
    # O_WRONLY: 쓰기 전용
    # O_TRUNC: 기존 파일 내용 삭제
    # 0o600: owner read/write only (rw-------)
    fd = os.open(str(cache_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

    try:
        # file descriptor를 파일 객체로 변환
        with os.fdopen(fd, "w") as f:
            json.dump(cache.to_dict(), f, indent=2)
    except Exception:
        # 예외 발생 시 file descriptor leak 방지
        try:
            os.close(fd)
        except OSError:
            pass  # 이미 닫혀있을 수 있음
        raise


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
        circuit_breaker: CircuitBreaker | None = None,
        use_singleton: bool = True,
    ):
        """
        Args:
            config: 인증 설정
            circuit_breaker: Circuit Breaker 인스턴스 (선택적)
            use_singleton: 싱글톤 패턴 사용 여부
        """
        self.config = config
        _ = use_singleton
        self._circuit = circuit_breaker
        self._token: str | None = None
        self._expires_at: float = 0
        self._lock = threading.Lock()
        self._async_lock: asyncio.Lock | None = None

        # Async session (lazy init)
        self._async_session: aiohttp.ClientSession | None = None

        # 파일 캐시에서 토큰 로드
        self._load_from_cache()

    @classmethod
    def get_instance(
        cls,
        config: KISAuthConfig,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> KISAuthManager:
        """싱글톤 인스턴스 반환 (app_key + is_real 기준)"""
        key = f"{config.app_key}_{config.is_real}"

        with cls._instance_lock:
            if key not in cls._instances:
                cls._instances[key] = cls(config, circuit_breaker, use_singleton=False)
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
            with open(cache_path) as f:
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

        except (OSError, json.JSONDecodeError, KeyError) as e:
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

            # 보안: os.open으로 파일 생성과 동시에 권한 설정 (atomic)
            _save_token_cache_secure(cache, cache_path)

            logger.debug(f"[KISAuth] Token cached to {cache_path}")

        except OSError as e:
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
            raise CircuitOpenError("Circuit breaker is open, cannot issue token")

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
    app_key: str | None = None,
    app_secret: str | None = None,
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
        circuit = CircuitBreaker(
            name="kis-auth",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                reset_timeout=60.0,
                half_open_max_calls=3,
            ),
        )

    if use_singleton:
        return KISAuthManager.get_instance(config, circuit)

    return KISAuthManager(config, circuit, use_singleton=False)
