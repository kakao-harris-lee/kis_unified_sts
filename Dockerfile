# KIS Unified Trading Platform Dockerfile
# Python 3.11 기반 트레이딩 애플리케이션 이미지 (trading loop + CLI).
# 대시보드 API는 별도 Dockerfile.dashboard 를 사용한다.

FROM python:3.11-slim

# 메타데이터
LABEL maintainer="harris"
LABEL description="KIS Unified Trading Platform"

# 환경변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app

# 의존성 파일 복사 및 설치
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install .

# 애플리케이션 코드 복사
COPY . .

# 비root 사용자 생성 (보안)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# 기본 명령어: 트레이딩 루프 (paper 기본; 런타임 인자로 override 가능). 대시보드
# API는 Dockerfile.dashboard 가 services.dashboard.app 을 :8001 로 서빙한다.
CMD ["python", "-m", "cli.main", "trade", "start", "--asset", "stock", "--paper", "--daemon"]
