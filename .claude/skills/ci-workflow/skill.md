---
name: ci-workflow
description: "GitHub Actions 워크플로우 작성/수정 절차. 경로 게이팅, gha 캐싱, CI에서 2-pass 테스트 호출, 필수 체크, flaky 잡 재실행. 트리거: CI, GitHub Actions, 워크플로우, 잡, 캐시, 게이팅, 체크."
---

# CI Workflow — CI/CD 워크플로우 작업 절차

`ci-pipeline-engineer`가 `.github/workflows/`를 안전하게 바꾸기 위한 절차.

## 워크플로우 지도
| 파일 | 트리거 | 무엇을 검증 |
|------|--------|-----------|
| `test.yml` | push/PR, weekly | 정식 전체 스위트(2-pass) + lint + type-check + performance |
| `devcontainer.yml` | 경로 게이트 | `Dockerfile.test` 빌드 + Dev Container 빌드 + unit 스모크 |
| `docker.yml` | tag/release/dispatch | 이미지 빌드·퍼블리시 + 헬스 스모크 |

## 새 잡/워크플로우 추가 절차

### 1. 중복 회피
- `test.yml`이 이미 전체 스위트를 호스트에서 돈다. 컨테이너/Dev Container 잡은
  **스모크만**(예: `tests/unit` 2-pass) — 전체를 또 돌리지 않는다.

### 2. 경로 게이팅 (인프라 잡)
```yaml
on:
  push:
    branches: [main, develop]
    paths: &paths
      - '.devcontainer/**'
      - 'Dockerfile.test'
      - 'docker-compose.yml'
      - 'Makefile'
      - 'pyproject.toml'
      - '.github/workflows/devcontainer.yml'
  pull_request:
    branches: [main]
    paths: *paths
```

### 3. CI에서 테스트 호출 (2-pass 필수)
```yaml
run: |
  docker compose --profile test run --build --rm tests bash -lc "\
    pytest tests/unit -n auto -m 'not serial' --timeout=180 --timeout-method=thread -q && \
    pytest tests/unit -m serial --timeout=180 --timeout-method=thread -q"
```
- 단일 패스 금지(serial 테스트가 깨진다).
- 호스트 잡(`test.yml`)은 Redis 사이드카 서비스 + `REDIS_URL=redis://localhost:6379/1`.

### 4. 캐싱·백스톱
- pip: `actions/setup-python` `cache: 'pip'`. Docker: `cache-from/to: type=gha`.
- `timeout-minutes`(잡) + `--timeout=180 --timeout-method=thread`(테스트).

### 5. 검증
```bash
python -c "import yaml; d=yaml.safe_load(open('.github/workflows/<f>.yml')); print(list(d['jobs']))"
# 푸시 후
gh pr checks <PR>
gh run view --job <id> --log-failed
```

## flaky 잡 운영
1. 실패 잡 로그 확인: `gh run view --job <id> --log-failed`.
2. 코드 변경과 무관 + 환경/러너 변동이면(예: `performance`가 전부 개선인데
   "1 regression", "Test not found in current results") → flaky로 분류.
3. `gh run rerun <run-id> --failed` 로 재실행해 그린 확인.
4. 진짜 회귀와 구분되도록 근거(로그 발췌)를 남긴다. 반복되면 baseline/threshold나
   수집 안정성을 test-reliability-engineer와 함께 손본다.

## 출력 규칙
- 워크플로우 diff + 트리거/게이트/캐시 근거
- 체크 결과 표(pass/fail+시간), 실패는 근본원인(코드 vs 환경 vs flaky)
- 시크릿은 `${{ secrets.* }}`만, `permissions:` 최소권한
