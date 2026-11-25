---
name: ci-workflow
description: "GitHub Actions 워크플로우 작성/수정 절차. 경로 게이팅, gha 캐싱, CI에서 2-pass 테스트 호출, 필수 체크, flaky 잡 재실행. 트리거: CI, GitHub Actions, 워크플로우, 잡, 캐시, 게이팅, 체크."
---

# CI Workflow — CI/CD 워크플로우 작업 절차

`ci-pipeline-engineer`가 `.github/workflows/`를 안전하게 바꾸기 위한 절차.

## 워크플로우 지도
| 파일 | 트리거 | 무엇을 검증 |
|------|--------|-----------|
| `test.yml` | push/PR (tos·docs 경로 제외), weekly | 정식 전체 스위트: 샤딩 병렬 `test-shard` + `test-serial` + 롤업 `test` + `lint` + `type-check` |
| `ruff.yml` | push/PR, 경로 게이팅 없음 | **필수 체크** `ruff` |
| `tos-gate.yml` | push/PR, 경로 게이팅 없음 | **필수 체크** `tos-gate` = `tools/tos_redigest.py --check` |
| `tos-firewall.yml` | push/PR, 경로 게이팅 없음 | **필수 체크** `tos-firewall` — gates(AST + `lint-imports`) · tests · static(mypy) |
| `ui.yml` | 경로 게이트 | 프론트: `npm run lint` · `npm test` · `npm run build` |
| `devcontainer.yml` | 경로 게이트, 주간 cron | `Dockerfile.test` 빌드 + Dev Container 빌드 + unit 스모크 |
| `docker.yml` | tag/release/dispatch | `Dockerfile.dashboard` 빌드·퍼블리시 + 헬스 스모크 |

> **필수 체크 3종(`ruff` · `tos-gate` · `tos-firewall`)은 저장소 룰셋이 이름으로 요구한다.**
> 잡 이름을 바꾸거나 삭제하거나 경로 게이팅을 추가하면 모든 PR 이 오지 않는 체크를 기다린다.
> `test.yml` 이 tos·docs 경로에서 비껴가므로 `ruff` 가 별도 워크플로우로 존재한다.

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
2. 코드 변경과 무관 + 환경/러너 변동(공유 러너 경합, 타임아웃)이면 → flaky로 분류.
3. `gh run rerun <run-id> --failed` 로 재실행해 그린 확인.
4. 진짜 회귀와 구분되도록 근거(로그 발췌)를 남긴다. 반복되면 결정론·격리를
   test-reliability-engineer와 함께 손본다.
5. `gh` 2.45.0 에는 `gh pr checks --json` 이 없다 — 폴링 루프가 조용히 빈다.

## 출력 규칙
- 워크플로우 diff + 트리거/게이트/캐시 근거
- 체크 결과 표(pass/fail+시간), 실패는 근본원인(코드 vs 환경 vs flaky)
- 시크릿은 `${{ secrets.* }}`만, `permissions:` 최소권한
