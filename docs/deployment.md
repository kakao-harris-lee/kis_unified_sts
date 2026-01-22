# Deployment Guide

KIS Unified Trading Platform 배포 가이드

## 목차

1. [사전 요구사항](#사전-요구사항)
2. [로컬 개발 환경](#로컬-개발-환경)
3. [Docker 배포](#docker-배포)
4. [프로덕션 배포](#프로덕션-배포)
5. [모니터링 설정](#모니터링-설정)
6. [문제 해결](#문제-해결)

---

## 사전 요구사항

### 소프트웨어

| 요구사항 | 최소 버전 | 권장 버전 |
|----------|-----------|-----------|
| Python | 3.11 | 3.12 |
| Docker | 24.0 | 25.0+ |
| Docker Compose | 2.20 | 2.24+ |
| Redis | 7.0 | 7.2 |

### 하드웨어 (프로덕션)

| 리소스 | 최소 | 권장 |
|--------|------|------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Storage | 20 GB | 50 GB SSD |

### 네트워크

- 한국투자증권 API 접속을 위한 인터넷 연결
- 포트: 8000 (API), 8001 (Dashboard), 3000 (Grafana), 9090 (Prometheus)

---

## 로컬 개발 환경

### 1. 저장소 클론

```bash
git clone https://github.com/kakao-harris-lee/kis-unified-sts.git
cd kis-unified-sts
```

### 2. 가상환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 활성화
source venv/bin/activate  # Linux/macOS
# 또는
venv\Scripts\activate     # Windows

# 의존성 설치
pip install -e ".[dev]"
```

### 3. 환경 변수 설정

```bash
# 예제 파일 복사
cp .env.example .env

# 필수 값 설정
nano .env  # 또는 선호하는 편집기
```

**.env 필수 설정:**

```bash
# KIS API
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_IS_REAL=false  # 모의투자

# API Authentication
API_KEY=your_secure_api_key_here
```

### 4. 테스트 실행

```bash
# 전체 테스트
pytest tests/ -v

# 빠른 테스트
pytest tests/ -q
```

### 5. 로컬 서버 실행

```bash
# API 서버
uvicorn services.api.app:app --reload --port 8000

# Dashboard 서버 (별도 터미널)
uvicorn services.dashboard.app:create_app --factory --reload --port 8001
```

---

## Docker 배포

### 1. 환경 설정

```bash
# 프로덕션용 환경 파일 생성
cp .env.production.example .env

# 환경 변수 편집
nano .env
```

### 2. 서비스 시작

```bash
# 시작 스크립트 사용
./scripts/docker-start.sh

# 또는 직접 실행
docker compose up -d
```

### 3. 상태 확인

```bash
# 헬스 체크
./scripts/docker-health.sh

# 로그 확인
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f app
```

### 4. 서비스 중지

```bash
./scripts/docker-stop.sh
# 또는
docker compose down
```

### Docker Compose 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| app | 8000 | Trading API |
| dashboard | 8001 | Dashboard API |
| redis | 6379 | 캐시/메시지 큐 |
| prometheus | 9090 | 메트릭 수집 |
| grafana | 3000 | 대시보드 |

---

## 프로덕션 배포

### 프로덕션용 Docker 이미지 빌드

```bash
# 프로덕션 이미지 빌드
docker build -f Dockerfile.prod -t kis-unified:latest .

# Dashboard 이미지 빌드
docker build -f Dockerfile.dashboard -t kis-unified-dashboard:latest .
```

### 보안 설정

#### 1. 환경 변수 보호

```bash
# .env 파일 권한 설정
chmod 600 .env

# 또는 Docker secrets 사용
docker secret create kis_app_key ./secrets/app_key.txt
```

#### 2. API 키 생성

```bash
# 강력한 API 키 생성
openssl rand -hex 32
```

#### 3. 네트워크 보안

```yaml
# docker-compose.prod.yml
services:
  app:
    networks:
      - internal
      - external
    ports:
      - "127.0.0.1:8000:8000"  # 로컬만 노출

networks:
  internal:
    internal: true
  external:
```

### Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/kis-trading
server {
    listen 443 ssl http2;
    server_name trading.example.com;

    ssl_certificate /etc/ssl/certs/trading.crt;
    ssl_certificate_key /etc/ssl/private/trading.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Systemd 서비스

```ini
# /etc/systemd/system/kis-trading.service
[Unit]
Description=KIS Unified Trading Platform
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/kis-unified-sts
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화
sudo systemctl enable kis-trading
sudo systemctl start kis-trading
```

---

## 모니터링 설정

### Grafana 설정

1. http://localhost:3000 접속
2. 기본 로그인: admin / admin
3. 비밀번호 변경

#### Prometheus 데이터 소스 추가

1. Configuration > Data Sources
2. Add data source > Prometheus
3. URL: `http://prometheus:9090`
4. Save & Test

#### 대시보드 임포트

1. Create > Import
2. JSON 파일 업로드: `config/grafana/dashboards/trading.json`

### Prometheus 알림 규칙

```yaml
# config/prometheus/alerts.yml
groups:
  - name: trading
    rules:
      - alert: HighErrorRate
        expr: rate(trading_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected

      - alert: ServiceDown
        expr: up{job="trading-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: Trading API is down
```

### Telegram 알림 설정

1. BotFather로 봇 생성
2. Chat ID 확인
3. .env에 설정:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 백업 및 복구

### 데이터 백업

```bash
# Redis 데이터 백업
docker compose exec redis redis-cli BGSAVE
docker cp kis-redis:/data/dump.rdb ./backups/redis-$(date +%Y%m%d).rdb

# 설정 파일 백업
tar -czvf backups/config-$(date +%Y%m%d).tar.gz config/
```

### 복구

```bash
# Redis 복구
docker cp ./backups/redis-backup.rdb kis-redis:/data/dump.rdb
docker compose restart redis
```

---

## 문제 해결

### 일반적인 문제

#### 1. Docker 컨테이너 시작 실패

```bash
# 로그 확인
docker compose logs app

# 컨테이너 상태 확인
docker compose ps

# 재시작
docker compose restart app
```

#### 2. Redis 연결 실패

```bash
# Redis 상태 확인
docker compose exec redis redis-cli ping

# 연결 테스트
docker compose exec app python -c "import redis; r = redis.from_url('redis://redis:6379'); print(r.ping())"
```

#### 3. KIS API 인증 실패

```bash
# 환경 변수 확인
docker compose exec app env | grep KIS

# 토큰 갱신
docker compose exec app python -c "from shared.kis.auth import KISAuth; auth = KISAuth(); print(auth.get_token())"
```

#### 4. 메모리 부족

```bash
# 메모리 사용량 확인
docker stats

# 컨테이너 메모리 제한 설정
# docker-compose.yml
services:
  app:
    deploy:
      resources:
        limits:
          memory: 2G
```

### 로그 레벨 변경

```bash
# .env에서 설정
LOG_LEVEL=DEBUG

# 또는 런타임에 변경
docker compose exec app python -c "import logging; logging.getLogger().setLevel(logging.DEBUG)"
```

### 헬스 체크 엔드포인트

| 엔드포인트 | 설명 |
|------------|------|
| `GET /health/live` | 컨테이너 생존 확인 |
| `GET /health/ready` | 서비스 준비 상태 |
| `GET /metrics` | Prometheus 메트릭 |

---

## 업그레이드

### 1. 백업

```bash
./scripts/backup.sh
```

### 2. 코드 업데이트

```bash
git pull origin main
```

### 3. 이미지 재빌드

```bash
docker compose build --no-cache
```

### 4. 서비스 재시작

```bash
docker compose down
docker compose up -d
```

### 5. 검증

```bash
./scripts/docker-health.sh
```

---

## 체크리스트

### 배포 전 체크리스트

- [ ] .env 파일 설정 완료
- [ ] KIS API 키 유효성 확인
- [ ] 테스트 통과
- [ ] Docker 이미지 빌드 성공
- [ ] 헬스 체크 통과

### 프로덕션 체크리스트

- [ ] SSL 인증서 설정
- [ ] 방화벽 규칙 설정
- [ ] 모니터링 알림 설정
- [ ] 백업 스케줄 설정
- [ ] 로그 로테이션 설정
