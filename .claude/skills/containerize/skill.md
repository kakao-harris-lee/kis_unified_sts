---
name: containerize
description: "컨테이너/개발환경 작업 절차. Dockerfile·docker-compose 프로파일·Dev Container·.dockerignore를 추가/수정하고 빌드+실행으로 검증한다. 트리거: Docker, 이미지, compose 프로파일, devcontainer, dockerignore, 빌드."
---

# Containerize — 컨테이너/개발환경 작업 절차

`container-engineer`가 Docker 이미지·compose 프로파일·Dev Container를 안전하게
바꾸기 위한 절차. 핵심 원칙: **모든 변경은 빌드+실행으로 검증한다.**

## 워크플로우

### 1. 범위 파악
- 무엇을 바꾸나: 런타임 이미지 / 테스트 이미지 / compose 프로파일 / Dev Container / `.dockerignore`
- 영향 받는 파일과 의존 서비스(Redis, Caddy, dashboard) 확인
- 기존 `docker-compose.yml` 앵커(`x-*-env`, `&pipeline-service`) 재사용 여부

### 2. 변경
- **레이어 캐시 우선**: `COPY pyproject.toml README.md` → `pip install` 먼저, `COPY . .` 나중.
- **비root**: `RUN useradd -m -u 1000 <user> && chown -R <user> /app` 후 `USER <user>`.
- **테스트 프로파일**: 무인증·ephemeral `redis-test` + `tests` 서비스
  (`network_mode: "service:redis-test"`로 localhost:6379 공유, sibling `networks:` 금지).
- **Dev Container**: `.devcontainer/{devcontainer.json,docker-compose.yml,post-create.sh}`.
  `post-create.sh`는 `.[dev]` editable 설치만 — **운영지향 `.env`를 만들지 않는다.**

### 3. `.dockerignore` 규칙
```
# 시크릿/대용량은 제외
.env
.env.*
.venv
data
node_modules
# 단, 테스트가 읽는 커밋된 템플릿은 다시 포함
!.env.example
!.env.*.example
```
빌드 컨텍스트에 빠지면 안 되는 파일(테스트가 읽는 `*.example`)이 제외됐는지 항상 확인.

### 4. 검증 (필수)
```bash
docker compose --profile <p> config            # 파싱
docker compose --profile <p> run --build --rm <svc>   # 빌드+실행 (변경 후 --build 필수!)
# 이미지에 파일이 실제로 들어갔는지
docker compose --profile <p> run --rm <svc> bash -lc 'ls -la <path>'
git status --porcelain                          # 호스트 작업트리 오염 0 확인
```
- `docker compose run`은 기본 재빌드 안 함 → 변경 반영하려면 `--build`.
- 끝나면 `docker compose --profile <p> down --remove-orphans`로 정리.

## 자주 쓰는 검증 시나리오
| 변경 | 검증 |
|------|------|
| `Dockerfile.test` 수정 | `docker compose --profile test run --build --rm tests pytest tests/unit -q` |
| compose 프로파일 추가 | `docker compose --profile <p> config --services` |
| Dev Container | `docker compose -f .devcontainer/docker-compose.yml config` + localhost:6379 도달 확인 |
| `.dockerignore` | 재빌드 후 `ls` 로 포함/제외 파일 확인 |

## 출력 규칙
- 변경 diff + 빌드/실행 로그 증거(그린/실패+원인)
- gotcha는 파일 주석으로 "왜"를 남긴다 (재발 방지)
- 포트 정책(`docs/ports.md`)·DRY·설정기반 원칙(`CLAUDE.md`) 위반 0
