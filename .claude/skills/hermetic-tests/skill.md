---
name: hermetic-tests
description: "테스트 신뢰성/인프라 절차. hermetic(.env 비주입), 병렬/serial 2-pass, fakeredis·redis-test 격리, de-flaking(RNG 시드/순서/시간), conftest 위생. 트리거: flaky, 테스트 깨짐, hermetic, 2-pass, serial, 시드, 결정론, conftest."
---

# Hermetic Tests — 테스트 신뢰성/인프라 절차

`test-reliability-engineer`가 "테스트가 어디서 돌든 동일하게, 결정론적으로
통과"하게 만드는 절차. 기능 테스트 *작성*이 아니라 *환경·실행방식·flakiness*를 다룬다.

## 황금 규칙
1. **테스트는 `.env` 없이 돈다.** `.env.example`(`DASHBOARD_REQUIRE_AUTH=true`,
   `REDIS_HOST=redis`)이 conftest/`cli.main`의 `load_dotenv`로 주입되면 dashboard
   401·Redis 호스트 오류. 온보딩 자동화가 `.env`를 만들지 않게 한다.
2. **serial은 전용 패스에서만.** 공유 Redis DB 1/순서·시간 민감 테스트는
   `@pytest.mark.serial`. `-n auto`나 단일 패스에 섞으면 깨진다.
3. **단위는 fakeredis, 통합은 격리 redis-test.** 실서비스 Redis(비밀번호·paper
   DB 1)는 절대 안 건드린다. live_infra는 `KIS_RUN_LIVE_INFRA_TESTS=1` 없이는 스킵.
4. **비root 가정.** "쓰기 불가" 단정 테스트는 uid 1000에서만 성립.

## 2-pass 실행
```bash
pytest tests/ --ignore=tests/performance -n auto -m "not serial" \
  --timeout=180 --timeout-method=thread -q
pytest tests/ --ignore=tests/performance -m serial \
  --timeout=180 --timeout-method=thread -q
```
markers: `unit`, `integration`, `live_infra`, `slow`, `backtest`, `serial` (`pyproject.toml`).

## de-flaking 절차
### 1. 재현 (결정론 여부 확인)
```bash
# CI 동일 이미지에서 의심 파일 N회 반복
docker compose --profile test run --rm tests bash -lc \
  "for r in 1 2 3 4 5; do pytest <path> -p no:cacheprovider -q | tail -1; done"
```
### 2. 원인 분류
| 증상 | 원인 | 수정 |
|------|------|------|
| 실행마다 단정 결과 변동 | 시드 없는 `np.random.*` | autouse fixture로 `np.random.seed(0)` (테스트마다 재시드) |
| `-n auto`에서만/특정 순서에서 깨짐 | 공유 외부상태·순서 의존 | `@pytest.mark.serial`로 이동 |
| 가끔 401/연결오류 | `.env` 주입 오염 | `.env` 제거(hermetic), 온보딩이 `.env` 생성 안 하게 |
| wall-clock 단정 흔들림 | 시간/타이밍 의존 | 고정 시계, KST 변환 명시, serial 이동 |

### 3. 시드 fixture 예시
```python
class TestSomething:
    @pytest.fixture(autouse=True)
    def _seed_rng(self):
        np.random.seed(0)   # 테스트마다 재시드 → 순서/병렬 무관 결정론
```
### 4. 검증
- 로컬 반복 + CI 동일 이미지(`-n auto`)에서 결정론 확인.
- 전체 2-pass 그린(다른 테스트 회귀 없음) 확인.
- 비결정성 수정은 단정을 느슨하게 푸는 게 아니라 **데이터를 결정론적으로** 만든다.

## conftest 위생 (`tests/conftest.py`)
- 싱글톤/레지스트리 리셋 fixture(ConfigLoader, Prometheus REGISTRY) 유지.
- MLflow는 로컬 sqlite로 고정(override). 외부 서버 의존 금지.
- xdist 워커별 Hypothesis 저장 디렉터리 분리.
- 새 전역 env 강제는 신중히 — 원인이 `.env`면 conftest 땜질보다 `.env` 미생성이 근본 수정.

## 출력 규칙
- flaky 진단: 원인 분류 + 최소 수정 + 반복실행 결정론 증거
- hermetic 위반: 새는 env 키/파일 명시
- 수정의 회귀 영향(전체 2-pass) 확인
