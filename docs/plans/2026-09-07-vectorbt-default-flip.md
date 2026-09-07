# 백테스트 엔진 vectorbt 전환 — 운영자 flip 이행

- 날짜: 2026-09-07 · 저자: 세션 모델(단독) · 상태: 운영자 flip 결정(2026-09-07) 이행
- 선행: `docs/plans/2026-07-08-new-architecture-refactoring-plan.md` P3-b/P3-c ·
  parity 리포트 `docs/plans/2026-07-10-vbt-parity-report.md`(PASS) · CI `backtest-extra`
  (main `b0bb74e7` 에서 `TestExperimentSeam` 포함 green)

## 0. 측정 — «기본값만 바꾸면» 무슨 일이 생기는가

`experiment_runner.py:293` 의 기본값은 코드 리터럴 `"legacy"` 이고, `VectorbtRunner`
는 exit 생성기 **parity 증거 허용목록** `EXPRESSIBLE_EXIT_GENERATORS =
{williams_r_exit, atr_dynamic, chandelier_exit}` 밖이면 `NotImplementedError` 로
legacy 에 폴백한다(`vbt_runner.py:105-127`, `_ensure_supported`).

| 활성 주식 전략(CLAUDE.md) | exit | 타임프레임 | flip 후 실제 엔진 |
|---|---|---|---|
| `bb_reversion` | `mean_reversion_exit` | 분봉 | **legacy 폴백**(허용목록 밖) |
| `opening_volume_surge` | `three_stage` | 분봉 | **legacy 영구**(부분 청산 = 표현 불가) |
| `volume_accumulation` | `momentum_decay` | 분봉 | **legacy 폴백**(허용목록 밖) |
| `momentum_breakout` | `atr_dynamic` | 분봉 | vectorbt |
| `williams_r` | `williams_r_exit` | 분봉 | vectorbt |
| `pattern_pullback`·`daily_pullback` | `chandelier_exit` | 일봉 | legacy(DailyBacktestAdapter 경로 parity 미검증) |

즉 기본값 flip 만으로는 활성 3전략 중 0개가 vectorbt 로 돈다. 계획이 «허용목록
확장 선행» 이라 적은 이유다. 또 `optimizer.py:244` 는 seam 없이 `BacktestEngine` 을
직접 만든다(계획 «optimizer 백엔드 교체» 미착수).

## 1. 이번 PR 의 범위

### A. 허용목록 확장(parity 증거 동반) — `mean_reversion_exit`, `momentum_decay`

`tests/unit/backtest/test_vbt_runner.py::TestRealExitParity` 의 `_REAL_EXIT_FACTORIES`
에 두 exit 의 실제 클래스 팩토리(배포 YAML 파라미터 그대로)를 추가하고, 기존
매트릭스(3 시나리오 × 리스크 변형)에서 legacy/vectorbt dual-run 이 트레이드
시퀀스·수익·샤프·MDD 완전 일치할 때만 `EXPRESSIBLE_EXIT_GENERATORS` 에 등재한다.
`test_real_exit_is_exercised_not_vacuous` 가 각 exit 가 실제로 발화했음을 요구한다.
**어느 하나라도 불일치면 등재하지 않고 원인을 보고한다**(계획: «미통과 항목은 원인
규명 전 교체 금지»). `three_stage` 는 영구 제외 — `opening_volume_surge.yaml` 에
`backtest.legacy_exit: true` 를 명시해 의도를 문서화한다(P3-c escape hatch).

### B. 기본값을 코드 리터럴에서 설정으로 — `config/backtest.yaml` 신설

```yaml
backtest:
  # 실험/최적화 경로의 기본 엔진. legacy | vectorbt. 전략 YAML 의
  # strategy.backtest.engine 이 우선한다. 미지원 경로는 러너가 legacy 로 자동 폴백.
  default_engine: ${BACKTEST_DEFAULT_ENGINE:vectorbt}
```

`experiment_runner` 의 `bt.get("engine", "") or "legacy"` 를 이 값으로 대체. 롤백은
env 한 줄(`BACKTEST_DEFAULT_ENGINE=legacy`). 알 수 없는 값은 기존대로 경고+legacy.

### C. optimizer seam — `shared/backtest/optimizer.py`

`experiment_runner.py:288-360` 의 백엔드 결정·폴백 로직을 공용 헬퍼로 추출
(`shared/backtest/backend.py::resolve_backend(bt_cfg, default) -> "legacy"|"vectorbt"`
+ `run_with_backend(strategy_factory, config, data, backend) -> BacktestResult`,
폴백·경고 포함), experiment_runner 와 optimizer 가 둘 다 이를 호출한다(DRY).
optimizer 의 Optuna 루프는 평가마다 이 헬퍼를 부른다. parity 리포트가 «스윕 속도는
현 단계 개선 없음(0.99×)」이라 기록했으므로 속도 주장은 하지 않는다.

### D. parity 게이트 재실행(운영자 flip 필수 게이트)

`PYTHONPATH=. .venv/bin/python scripts/vbt_parity_report.py --out
docs/plans/2026-09-07-vbt-parity-report.md` — vectorbt 1.0.0 로컬 설치 후 실행.
exit code 0 이어야 flip 커밋. 실데이터 섹션은 로컬 parquet 유무에 따라 자동 생략되며
그 사실을 리포트에 그대로 남긴다(CI `backtest-extra` 가 보완).

### E. 문서

계획 2026-07-08 P3-b 체크박스(«미착수» → 이행 SHA), ROADMAP «legacy backtest engine
retirement» 항목을 «기본값 vectorbt · engine.py 는 폴백으로 잔존» 으로 정정.

## 2. 범위 밖(정직 기록)

- **`engine.py` 제거는 불가**: 러너가 선물·ATS·멀티심볼·공매도·regime gate·일봉
  어댑터·three_stage·허용목록 밖 exit 를 전부 legacy 폴백으로 처리한다. 폴백 대상이
  0 이 되기 전엔 제거할 수 없다. 이번 PR 은 «기본값 전환 + 커버리지 확장」이다.
- 일봉 어댑터 경로 parity(pattern_pullback 등)는 별도 트랙.
- 속도 개선은 P1/P2(선언형 조건 사전계산) 소관.

## 3. 검증

허용목록 parity 매트릭스 전건 통과 · `tests/unit/backtest` 전체(vectorbt 설치 상태) ·
`tests/unit` 2-pass(`pipefail` 로 실제 pytest rc 확인) · ruff/black · parity 리포트
rc 0 · 독립 코드 리뷰.
