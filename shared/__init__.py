"""KIS Unified Trading Platform - Shared Modules

공통 모듈:
- kis: KIS API 어댑터 (인증, 클라이언트, 웹소켓)
- config: 설정 로더 및 스키마
- strategy: 전략 프레임워크
- indicators: 기술적 지표
- models: 데이터 모델
- backtest: 백테스트 엔진
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("kis-unified-sts")
except PackageNotFoundError:
    # 패키지가 설치되지 않은 경우 (개발 모드)
    __version__ = "0.1.0"

__all__ = ["__version__"]
