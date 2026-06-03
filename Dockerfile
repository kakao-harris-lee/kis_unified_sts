# KIS Unified Trading Platform Dockerfile
# Python 3.11 기반 FastAPI 애플리케이션

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
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && \
    pip install .

# 애플리케이션 코드 복사
COPY . .

# 비root 사용자 생성 (보안)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# 기본 명령어
CMD ["python", "-m", "uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
