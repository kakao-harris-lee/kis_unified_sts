# 레거시 정리 2단계 — 코드 밖에 남은 흔적을 걷어낸다

- 작성: 2026-11-10 · 세션 모델 단독 저작(운영자 지시 2026-09-04)
- **상태: 채택 — 운영자 2026-11-10 «레거시 관련된건 전체적으로 정리 계획을 세워서 진행해».**
- 앞 계획: `docs/plans/2026-11-07-legacy-removal-plan.md`(L1~L7, 2026-11-10 전부 머지, main `8faed56c`).
  그 계획은 **추적되는 코드**만 지웠다. 이 계획은 그 뒤에 남은 의존성·CI 잡·추적 산출물과,
  저장소 밖(호스트 Docker·체크아웃의 미추적 파일·crontab·Redis·GitHub 원격 브랜치)의 흔적을 다룬다.
- 손대지 않는 것: `tos/` · `tos-spec/` · `tos-evidence/` · B3 증인 경로(`shared/decision/setups/vwap_reversion.py`
  와 그 의존) · `shared/execution/executor.py`·`shared/kis/client.py` 와 그 폐포 · `data/market/`(과거 시세
  1.8 GB, TOS 연구 입력) · 콜드 백업(`~/.local/state/tos/*-cold`, TOS 증거 — §6) · 태그 `legacy-final`.

## 1. 실측 (2026-11-10 10:40 KST)

| 영역 | 남은 것 | 크기 |
| --- | --- | --- |
| `pyproject.toml` | `mlflow` · `optuna` · `optuna-dashboard` · `backtesting` · `[backtest]`(vectorbt) — L7 뒤 import 하는 코드 0 | 설치 의존성 |
| CI | `test.yml::backtest-extra`(권고 잡, 지운 vectorbt 경로 검증) | 잡 1개 |
| 추적 산출물 | `artifacts/`(117 파일 · 레거시 OVS 튜닝·뉴스 평가·데이터셋 차트) · `reports/`(16 파일 · optuna·counterfactual·검증) | 29 MB + 49 MB |
| 체크아웃 미추적 | `models/` 971 MB · `output/` 156 MB · `results/` 115 MB · `core/` · `jobs/` · `scripts/cron/` · `mlruns/` · `mlflow.db` · `pids/` · `exports/` · `trading_reports/` · `coverage.xml` · `test_results.log` · `config/strategies/built/` | ≈ 1.25 GB |
| Docker 이미지 | 레거시 프로젝트 `kis_dev-*` · `kis_live-*` · `kis_unified_sts-*`/`_*` · `kis_paper-{trader,app,mlflow}` · `kis-dashboard` · `kis-trade-mcp`(5개월 전 종료된 컨테이너 1개) | ≈ 40 GB |
| Docker 볼륨 | `kis_dev_*` 4 · `kis_unified_sts_*` 4 (쓰는 컨테이너 없음) | — |
| crontab | 주석 처리된 레거시 줄 39 (`scripts/cron/*` 등, 대상 파일은 L3 에서 삭제) | — |
| Redis(호스트 DB 1) | 레거시 키 8개(`futures:monitor:positions` · `signal.*.stock` · `order.fill.stock` · `forecast:vol:model` · `test-key` · `trading:*:equity_timeline`) — 6개는 TTL 없음 | — |
| GitHub 원격 | `origin/feat/cp3-pr1-minute-probe`(#894 머지됨) | 브랜치 1 |

살아 있는 것(건드리지 않음): 컨테이너 `kis_paper-{dashboard,strategy-builder-ui,caddy,redis,prometheus}` 와
그 이미지·볼륨(`kis_paper_*`), crontab 의 활성 줄 27(CP-3 tenant · 상주 paper · 콜드 백업 · 다른 프로젝트).

## 2. 단계

| 단계 | 범위 | 방식 | 등급 |
| --- | --- | --- | --- |
| **C1** | 호스트 Docker — 위 레거시 이미지·볼륨·종료 컨테이너 삭제 | 호스트 작업(PR 없음) | — |
| **C2** | 체크아웃 미추적 파일 — `~/.local/state/kis/legacy-archive-20261110.tar.xz` 로 묶은 뒤 삭제 | 호스트 작업 | — |
| **C3** | crontab 주석 레거시 줄 39 삭제 · 호스트 Redis DB 1 레거시 키 8개 삭제 · 원격 브랜치 1 삭제 | 호스트 작업(백업 먼저) | — |
| **C4** | 저장소 — 의존성 5종 · `backtest-extra` 잡 · `uv.lock` 재생성 · `mlflow.db` 참조(`pyproject` 주석 · `tests/conftest.py`) · 추적 `artifacts/` · 경로 참조 없는 `reports/` 파일 · `.gitignore` 의 죽은 줄 | PR 1개 | B |

C1~C3 은 세션에 닿지 않는다(CP-3 세션은 `measure/wt-*` 워크트리와 `.venv` 만 쓰고, 지우는 이미지는 어떤 실행 중
컨테이너도 쓰지 않는다). 그래서 장중에도 한다. C4 는 `.venv` 와 설치 의존성을 바꾸므로 L 계획과 같은 머지 규칙을 따른다:
**15:50 뒤 ~ 다음날 08:30 전**, 11-11~11-13 과 11-19 는 머지 없음, 머지 뒤 다음 거래일 preflight 3방향.

## 3. 각 단계의 확인 (측정으로만)

- **C1:** 지우기 전 `docker ps -a` 로 각 이미지를 쓰는 컨테이너가 없음을 확인. 지운 뒤 `/tos` 200 · `/health` 200 ·
  살아 있는 컨테이너 5개 healthy. 회수량은 `docker system df` 전·후로 적는다.
- **C2:** 묶음의 `tar -tJf` 목록 = 지운 경로 목록. 지운 뒤 `git status` 가 바뀌지 않음(미추적·무시 파일만 지운다).
  `.env*` · `.kis_token_*` · `.venv` · `.claude/` · `.omc/` · `data/` 는 대상 아님.
- **C3:** `crontab -l` 백업 파일을 남기고, 전·후 `diff` 가 주석 줄 삭제뿐인지 확인. 활성 줄 수 불변.
  Redis 는 지울 키 8개의 값을 `DUMP` 로 백업 디렉터리에 남긴다.
- **C4:** CI 필수 체크 green · 남은 테스트 green · `python -c "import tools.tos_cp3.produce_fields,
  tools.tos_cp3.emit_legacy_decisions"` · B3 증인 11-02~11-06 LONG `cmp` 동일(sha `8c8093e6…`) — 의존성 해석이
  바뀌면 numpy/pandas 버전이 움직일 수 있으므로 이 비교가 C4 의 핵심 확인이다. 생산자 `lineage.json` 의
  numpy/pandas/pyarrow 버전이 전·후 같아야 한다. 다르면 C4 는 그 의존성을 고정한 채 다시 한다.

새 검사기·게이트는 만들지 않는다(R5).

## 4. 되돌리기

- C1: 이미지는 `legacy-final` 체크아웃에서 다시 빌드할 수 있다. 볼륨 안 데이터(레거시 Redis·Prometheus)는
  2026-10-08 정지 이후 쓰이지 않았다.
- C2: `legacy-archive-20261110.tar.xz` 를 풀면 된다.
- C3: crontab 백업 · Redis `DUMP` 파일로 `RESTORE`.
- C4: PR `git revert`.

## 5. 일정

| 시각 | 할 일 |
| --- | --- |
| 11-10 장중 | C1 · C2 · C3 (세션 무관) · C4 PR 작성·리뷰 |
| 11-10 15:50 뒤 | 장후 B3 로 L7 닫기 → C4 머지 |
| 11-11 08:30 전 | C4 머지 후 preflight 3방향 (머지가 늦으면 11-16 이후) |

## 6. 이 계획 밖 — 따로 결정할 것

- **콜드 백업의 비압축 세대 디렉터리.** `~/.local/state/tos/{paper-cold,cp3-setup-d-*-cold}/A056xx/backups/genN/`
  은 같은 세대의 검증된 `archives/genN.set.tar.xz` 옆에 남은 **비압축 사본**이다. 합계 63.0 GB, 세대마다
  최신 1개만 남기면 **56.4 GB** 회수(최신 4개 6.6 GB 유지). 레거시가 아니라 TOS 증거이고, 다음 세대 번호를
  기존 디렉터리에서 세는지(`tos_runtime/evidence/backup.py`) 확인이 먼저다. 증거 퍼지 계획
  `docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md` §2 A3 는 «라이브 파일은 건드리지 않는다»만
  정했고 비압축 세대의 보존은 정하지 않았다 — 운영자 결정 사항.
- `docs/` 의 레거시 런북·과거 계획은 역사 기록이라 남긴다(앞 계획 §3 과 같은 판단).
- 메모리의 «레거시» 절은 이미 «레거시» 표시가 붙어 있다. 지우지 않는다.
