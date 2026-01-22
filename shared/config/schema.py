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


class CircuitBreakerStageConfig(BaseModel):
    """스테이지별 서킷 브레이커 설정"""

    failure_threshold: int = Field(default=5, description="연속 실패 허용 횟수")
    reset_timeout: float = Field(default=30.0, description="복구 대기 시간 (초)")
    half_open_max_calls: int = Field(default=2, description="반열림 상태 최대 호출 수")


class PipelineIntervalsConfig(BaseModel):
    """파이프라인 스테이지별 인터벌 설정"""

    regime: float = Field(default=300.0, description="Regime 스테이지 간격 (초)")
    entry: float = Field(default=1.0, description="Entry 스테이지 간격 (초)")
    monitoring: float = Field(default=0.1, description="Monitoring 스테이지 간격 (초)")
    exit: float = Field(default=0.5, description="Exit 스테이지 간격 (초)")


class PipelineCircuitBreakersConfig(BaseModel):
    """파이프라인 서킷 브레이커 설정"""

    regime: CircuitBreakerStageConfig = Field(
        default_factory=lambda: CircuitBreakerStageConfig(
            failure_threshold=3, reset_timeout=60.0, half_open_max_calls=2
        )
    )
    entry: CircuitBreakerStageConfig = Field(
        default_factory=lambda: CircuitBreakerStageConfig(
            failure_threshold=5, reset_timeout=30.0, half_open_max_calls=2
        )
    )
    monitoring: CircuitBreakerStageConfig = Field(
        default_factory=lambda: CircuitBreakerStageConfig(
            failure_threshold=5, reset_timeout=30.0, half_open_max_calls=2
        )
    )
    exit: CircuitBreakerStageConfig = Field(
        default_factory=lambda: CircuitBreakerStageConfig(
            failure_threshold=2, reset_timeout=10.0, half_open_max_calls=1
        )
    )


class PipelineRetryConfig(BaseModel):
    """재시도 설정"""

    max_retries: int = Field(default=2, description="최대 재시도 횟수")
    delay: float = Field(default=1.0, description="재시도 간격 (초)")


class PipelineConfig(BaseModel):
    """파이프라인 전체 설정"""

    intervals: PipelineIntervalsConfig = Field(default_factory=PipelineIntervalsConfig)
    circuit_breakers: PipelineCircuitBreakersConfig = Field(
        default_factory=PipelineCircuitBreakersConfig
    )
    retry: PipelineRetryConfig = Field(default_factory=PipelineRetryConfig)


class TradingHoursConfig(BaseModel):
    """거래 시간 설정"""

    open: str = Field(default="09:00", description="거래 시작 시간")
    close: str = Field(default="15:30", description="거래 종료 시간")


class MarketHoursConfig(BaseModel):
    """자산별 시장 시간 설정"""

    regular: TradingHoursConfig = Field(default_factory=TradingHoursConfig)


class MarketScheduleConfig(BaseModel):
    """시장 스케줄 설정"""

    stock: MarketHoursConfig = Field(
        default_factory=lambda: MarketHoursConfig(
            regular=TradingHoursConfig(open="09:00", close="15:30")
        )
    )
    futures: MarketHoursConfig = Field(
        default_factory=lambda: MarketHoursConfig(
            regular=TradingHoursConfig(open="09:00", close="15:45")
        )
    )
    pre_market_buffer: int = Field(default=5, description="장 시작 전 준비 시간 (분)")
    pre_close_buffer: int = Field(default=5, description="장 종료 전 정리 시간 (분)")


class HolidaysConfig(BaseModel):
    """공휴일 설정"""

    holidays: list[str] = Field(default_factory=list, description="휴장일 목록 (YYYY-MM-DD)")

    def to_date_set(self) -> set:
        """date 객체 set으로 변환"""
        from datetime import date as dt_date

        result = set()
        for holiday_str in self.holidays:
            try:
                result.add(dt_date.fromisoformat(holiday_str))
            except ValueError:
                pass  # 잘못된 형식 무시
        return result


# =============================================================================
# Monitoring Config
# =============================================================================


class MetricsServerConfig(BaseModel):
    """Prometheus 서버 설정"""

    enabled: bool = Field(default=False, description="Prometheus 서버 활성화")
    host: str = Field(default="127.0.0.1", description="바인드 주소")
    port: int = Field(default=9090, description="포트")


class MetricsCollectionConfig(BaseModel):
    """메트릭 수집 설정"""

    interval_seconds: int = Field(default=10, description="수집 간격 (초)")


class MetricsLabelsConfig(BaseModel):
    """메트릭 라벨 설정"""

    environment: str = Field(default="production", description="환경")
    service: str = Field(default="kis-unified-sts", description="서비스명")


class MetricsConfig(BaseModel):
    """Prometheus 메트릭 전체 설정"""

    enabled: bool = Field(default=True)
    server: MetricsServerConfig = Field(default_factory=MetricsServerConfig)
    collection: MetricsCollectionConfig = Field(default_factory=MetricsCollectionConfig)
    labels: MetricsLabelsConfig = Field(default_factory=MetricsLabelsConfig)


class TelegramNotificationConfig(BaseModel):
    """Telegram 알림 설정"""

    enabled: bool = Field(default=True)
    timeout_seconds: int = Field(default=10, description="요청 타임아웃")
    parse_mode: str = Field(default="HTML", description="메시지 포맷")


class NotificationLevelsConfig(BaseModel):
    """알림 레벨별 활성화"""

    info: bool = Field(default=True)
    warning: bool = Field(default=True)
    error: bool = Field(default=True)
    critical: bool = Field(default=True)


class NotificationFiltersConfig(BaseModel):
    """알림 필터링 설정"""

    dedup_window_seconds: int = Field(default=60, description="중복 방지 윈도우")
    max_per_minute: int = Field(default=10, description="분당 최대 알림")


class NotificationEventsConfig(BaseModel):
    """알림 대상 이벤트"""

    trading_start: bool = Field(default=True)
    trading_stop: bool = Field(default=True)
    trading_pause: bool = Field(default=True)
    trade_executed: bool = Field(default=True)
    daily_summary: bool = Field(default=True)
    error_occurred: bool = Field(default=True)
    circuit_breaker_open: bool = Field(default=True)


class NotificationsConfig(BaseModel):
    """알림 전체 설정"""

    enabled: bool = Field(default=True)
    telegram: TelegramNotificationConfig = Field(
        default_factory=TelegramNotificationConfig
    )
    levels: NotificationLevelsConfig = Field(default_factory=NotificationLevelsConfig)
    filters: NotificationFiltersConfig = Field(default_factory=NotificationFiltersConfig)
    events: NotificationEventsConfig = Field(default_factory=NotificationEventsConfig)


class HealthComponentConfig(BaseModel):
    """헬스 체크 컴포넌트 설정"""

    enabled: bool = Field(default=True)
    timeout_seconds: int = Field(default=5)


class HealthComponentsConfig(BaseModel):
    """헬스 체크 컴포넌트들"""

    system: HealthComponentConfig = Field(default_factory=HealthComponentConfig)
    redis: HealthComponentConfig = Field(
        default_factory=lambda: HealthComponentConfig(timeout_seconds=3)
    )
    database: HealthComponentConfig = Field(
        default_factory=lambda: HealthComponentConfig(timeout_seconds=5)
    )
    kis_api: HealthComponentConfig = Field(
        default_factory=lambda: HealthComponentConfig(timeout_seconds=10)
    )


class HealthProbeConfig(BaseModel):
    """헬스 프로브 설정"""

    path: str = Field(description="프로브 경로")
    failure_threshold: int = Field(default=3, description="실패 임계값")


class HealthConfig(BaseModel):
    """헬스 체크 전체 설정"""

    enabled: bool = Field(default=True)
    timeout_seconds: int = Field(default=5, description="체크 타임아웃")
    interval_seconds: int = Field(default=30, description="체크 간격")
    components: HealthComponentsConfig = Field(default_factory=HealthComponentsConfig)


class MonitoringConfig(BaseModel):
    """모니터링 전체 설정"""

    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)


class BaseConfig(BaseModel):
    """기본 설정 (모든 설정 파일의 루트)"""

    kis: KISConfig = Field(default_factory=KISConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    market_schedule: MarketScheduleConfig = Field(default_factory=MarketScheduleConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
