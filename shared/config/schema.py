"""설정 스키마 (Pydantic)

YAML 설정 파일의 Pydantic 검증 스키마.
모든 설정 값은 이 스키마를 통해 검증됨.
"""

from __future__ import annotations

import os
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class KISAuthSchema(BaseModel):
    """KIS API 인증 설정 스키마"""

    app_key: str = Field(default="", description="KIS API 앱 키")
    app_secret: str = Field(default="", description="KIS API 앱 시크릿")
    is_real: bool = Field(default=True, description="실전투자 여부")
    token_cache_dir: Optional[str] = Field(
        default=None, description="토큰 캐시 디렉토리"
    )
    token_expiry_buffer_seconds: int = Field(
        default=600, description="토큰 만료 전 갱신 버퍼 (초)"
    )
    request_timeout_seconds: int = Field(
        default=30, description="API 요청 타임아웃 (초)"
    )

    @field_validator("app_key", "app_secret", mode="before")
    @classmethod
    def resolve_env_var(cls, v: str) -> str:
        """환경변수 참조 해석 (${VAR_NAME} 형식)"""
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            return os.getenv(env_var, "")
        return v


class CircuitBreakerSchema(BaseModel):
    """Circuit Breaker 설정 스키마"""

    enabled: bool = Field(default=False, description="Circuit Breaker 활성화")
    failure_threshold: int = Field(default=5, description="연속 실패 임계값")
    recovery_timeout_seconds: int = Field(
        default=60, description="복구 대기 시간 (초)"
    )
    half_open_max_calls: int = Field(
        default=3, description="Half-open 상태 허용 호출 수"
    )


class KISConfig(BaseModel):
    """KIS API 전체 설정

    Example YAML:
        kis:
          auth:
            app_key: ${KIS_APP_KEY}
            app_secret: ${KIS_APP_SECRET}
            is_real: true
            token_cache_dir: .cache
            token_expiry_buffer_seconds: 600
          circuit_breaker:
            enabled: true
            failure_threshold: 5
    """

    auth: KISAuthSchema = Field(default_factory=KISAuthSchema)
    circuit_breaker: CircuitBreakerSchema = Field(
        default_factory=CircuitBreakerSchema
    )


class AssetClass(BaseModel):
    """자산 클래스 설정"""

    type: Literal["stock", "futures"] = Field(description="자산 유형")
    market: str = Field(description="시장 (KOSPI, KOSDAQ, KOSPI200F 등)")


class BaseConfig(BaseModel):
    """기본 설정 (모든 설정 파일의 루트)"""

    kis: KISConfig = Field(default_factory=KISConfig)
