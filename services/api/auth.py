"""API 인증 모듈

API Key 기반 인증 시스템.

Usage:
    from services.api.auth import verify_api_key, require_trading_permission

    @router.post("/trading/start")
    async def start_trading(api_key: str = Depends(verify_api_key)):
        ...
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Annotated

logger = logging.getLogger(__name__)

# Optional FastAPI imports
try:
    from fastapi import Depends, HTTPException, Security, status
    from fastapi.security import APIKeyHeader

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# API Key 헤더 이름
API_KEY_HEADER = "X-API-Key"

# API Key 보안 스키마
if HAS_FASTAPI:
    api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def get_api_key() -> str | None:
    """환경변수에서 API Key 로드

    Returns:
        API Key 또는 None (미설정 시)
    """
    return os.getenv("API_KEY")


def is_auth_enabled() -> bool:
    """인증 활성화 여부 확인

    API_KEY가 설정되어 있으면 인증 활성화.
    개발 환경에서는 API_KEY를 설정하지 않으면 인증 비활성화.
    """
    return get_api_key() is not None


def validate_api_key(provided_key: str | None) -> bool:
    """API Key 유효성 검증

    Args:
        provided_key: 제공된 API Key

    Returns:
        유효 여부

    Raises:
        RuntimeError: Production 환경에서 API_KEY 미설정 시
    """
    expected_key = get_api_key()

    # 인증 비활성화 상태 체크
    if expected_key is None or expected_key == "":
        environment = os.getenv("ENVIRONMENT", "production").lower()

        if environment == "production":
            raise RuntimeError(
                "API_KEY must be set in production environment. "
                "Set API_KEY environment variable or ENVIRONMENT=development for local development."
            )

        # Development 환경에서는 인증 우회 허용
        logger.warning(
            "API authentication is disabled (API_KEY not set). "
            "This is only allowed in development environment."
        )
        return True

    if provided_key is None:
        return False

    # 타이밍 공격 방지를 위한 상수 시간 비교
    return secrets.compare_digest(provided_key, expected_key)


if HAS_FASTAPI:

    async def verify_api_key(
        api_key: Annotated[str | None, Security(api_key_header)] = None,
    ) -> str | None:
        """API Key 검증 의존성

        FastAPI Depends()로 사용.

        Args:
            api_key: 헤더에서 추출한 API Key

        Returns:
            검증된 API Key

        Raises:
            HTTPException: 인증 실패 시
        """
        if not is_auth_enabled():
            # 인증 비활성화 - 개발 모드
            return None

        if not validate_api_key(api_key):
            logger.warning(f"Invalid API key attempt from header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        return api_key

    async def require_trading_permission(
        api_key: Annotated[str | None, Depends(verify_api_key)] = None,
    ) -> str | None:
        """Trading 엔드포인트 접근 권한 검증

        Trading 관련 엔드포인트 (start, stop, pause, resume)에 사용.

        Args:
            api_key: 검증된 API Key

        Returns:
            API Key
        """
        # 추후 역할 기반 권한 확장 가능
        # 현재는 API Key 검증만 수행
        return api_key


def generate_api_key(length: int = 32) -> str:
    """새 API Key 생성

    개발/테스트 목적으로 새 API Key 생성.

    Args:
        length: Key 길이 (기본 32)

    Returns:
        새로 생성된 API Key
    """
    return secrets.token_urlsafe(length)


# =============================================================================
# CLI 유틸리티
# =============================================================================


def print_auth_status():
    """현재 인증 상태 출력"""
    if is_auth_enabled():
        key = get_api_key()
        masked = f"{key[:4]}...{key[-4:]}" if key and len(key) > 8 else "****"
        print(f"Authentication: ENABLED (key: {masked})")
    else:
        print("Authentication: DISABLED (set API_KEY env var to enable)")


if __name__ == "__main__":
    # 새 API Key 생성 유틸리티
    import stat
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        new_key = generate_api_key()

        # Write to a secure file — atomic creation with 0o600 permissions
        # (avoids TOCTOU race between open() and chmod())
        key_file = ".api_key.secret"
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(new_key)

        masked = f"{new_key[:4]}...{new_key[-4:]}"
        print(f"Generated new authentication key: {masked}")
        print(f"\nKey saved to: {key_file} (with secure 600 permissions)")
        print(f"\nTo use this key:")
        print(f"1. Copy to your .env file: API_KEY=$(cat {key_file})")
        print(f"2. Or export: export API_KEY=$(cat {key_file})")
        print(f"3. Delete {key_file} after copying to your secure location")
    else:
        print_auth_status()
