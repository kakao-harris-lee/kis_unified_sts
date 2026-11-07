# 레거시 제거 계획 — TOS 가 쓰지 않는 코드를 걷어낸다

- 작성: 2026-11-07 · 세션 모델 단독 저작(운영자 지시 2026-09-04)
- **상태: 초안 — 운영자 승인 대기.** 운영자 지시 2026-11-07 「TOS 를 만들기 전의 레거시 코드로 남아 있는 불필요한
  코드들을 제거 정리 계획 진행해」.
- 근거 결정: 레거시 개발 중단(운영자 2026-08-04) · 레거시 paper 컨테이너 18개 정지(운영자 2026-10-08) ·
  저장소 분리 시 «`tos/` 를 옮기지 않고 레거시 런타임을 지운다»(경계 설계
  `docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md` §6.2 — 이 계획은 그 삭제를 분리 전에 미리 한다).
- 손대지 않는 것: `tos/` · `tos-spec/` · `tos-evidence/` · Phase 0 계약 본문 · `data/` 의 시장 데이터(추적 대상 아님).

---

## 0. 한 줄 요약

**«TOS 가 지금 쓰는 것»을 뿌리로 import 폐포를 재고, 거기 닿지 않는 레거시를 PR 7개로 나눠 지운다.**
CP-3 세션은 매일 08:38 에 origin/main 을 새로 체크아웃하므로, 모든 PR 은 장후에 머지하고 다음 거래일
preflight 로 확인한다. 11-12 롤과 11-20 M2 기한 주변은 비운다.

## 1. 실측 (2026-11-07, main `8ffbfc21`)

| 영역 | 파이썬 줄 수 | TOS 가 쓰나 |
| --- | --- | --- |
| `tos/` | 429,573 | — (본체) |
| `shared/` | 109,723 | 일부 (아래) |
| `services/` | 51,071 | dashboard 의 TOS 라우트 1개만 |
| `scripts/` | 44,096 | `scripts/tos/*` · `scripts/test_render_*` 만 |
| `cli/` | 2,850 | `sts tos` (`cli/commands/tos_status.py`) 만 |
| `tests/` | 270,818 | TOS·도구 테스트(`tests/tools/` 의 81개 파일 + `tests/tos_l3/`) 와 남는 `shared` 의 테스트 |
| `strategy-builder-ui/` | (TS) | `/tos` 화면만 |

**import 폐포** (AST, 패키지 `__init__` 포함, 스크래치 스크립트로 측정 — 아래 §5 의 확인 명령이 같은 방법이다):

| 뿌리 | 닿는 레거시 모듈 |
| --- | --- |
| `tos/**` | **0** (방화벽 그대로) |
| `tools/tos_*.py` | **0** |
| `tools/tos_cp3/**` | **240** / 739 |
| `tools/broker_probes/**` | 48 |
| `services/dashboard/**` (현재 전체) | 301 |
| `cli/**` (현재 전체) | 314 |

`tools/tos_cp3` 의 240 은 직접 import 몇 줄에서 나온다. 산 의존은 셋이다.

1. **생산자** `produce_fields.py` — Setup D 필드를 레거시 구현으로 계산한다:
   `shared.backtest.market_context_replay` · `shared.decision.setups.vwap_reversion` ·
   `shared.decision.context` · `shared.strategy.exit.setup_target_exit` · `shared.storage.market_data_store` ·
   `shared.instruments.*` · `shared.determinism.replay`.
2. **B3 대조** `emit_legacy_decisions.py` — §2-1 의 장후 대조가 **레거시 결정과** 비교한다. 레거시 Setup D 구현
   자체가 증인이다.
3. **시세·자격증명** `live_producer/*` · `quote_client.py` · `minute_probe.py` — `shared.kis.auth` ·
   `shared.collector.historical.ohlcv_parser` · `shared.config.dotenv_guard`.

나머지 200여 개는 **패키지 `__init__` 의 부채꼴 import** 가 끌고 온다(예: `shared.strategy` → registry →
`shared.llm` 38개). 직접 쓰는 것이 아니다.

**코드 digest 는 영향 없음:** 세션이 확인하는 `expected_code_digest` 는 `tos` · `tos_runtime` 두 패키지의
`*.py` 만 잰다(`tos_runtime/operations/dependency_admission.py::default_package_roots`). 레거시 파일을 지워도
`release.yaml` 재도출은 필요 없다.

**운영 상태:** 레거시 컨테이너 18개는 10-08 부터 정지(삭제 아님). 살아 있는 것은 `dashboard` ·
`strategy-builder-ui` · `caddy` · `redis` · `prometheus` 다섯 개 — `/tos` 운영자 화면 때문이다.

## 2. 남길 것 (뿌리)

| 뿌리 | 이유 |
| --- | --- |
| `tos/` · `tos-spec/` · `tos-evidence/` · `tools/tos_*` · `tools/tos_cp3/` · `config/tos_*` | TOS 본체·작업 셋(`tos/CLAUDE.md`) |
| `tools/broker_probes/` · `config/broker_probes/` | 모의 계좌 GET·P-SC 프로브(#948 대기) |
| `scripts/tos/` · `scripts/test_render_*` | tenant 트리 렌더 |
| `cli/main.py` 의 `sts tos` · `cli/commands/tos_status.py` | §2-5 한 장 상태판 |
| `services/dashboard/` 의 앱 골격 + `routes/tos_projection.py` + 인증 미들웨어 | `/tos` 의 BFF |
| `strategy-builder-ui/` 의 `/tos` 화면 + API 프록시 | Product/Operator UI |
| `shared/` 중 위 뿌리의 **폐포** | 생산자·B3 증인·시세 |
| 생산자가 읽는 설정(`config/strategies/futures/` 의 Setup D · 선물 개장 설정 등) | 폐포 측정 때 YAML 참조도 같이 확인 |

**B3 증인 결정 (권장):** 레거시 Setup D 구현(`shared.decision.setups.vwap_reversion` 과 그 의존)은
`TOS_PAPER_READY` 까지 **바이트 그대로** 둔다. 옮기거나 다듬으면 B3 가 «무엇과 비교하는가»가 바뀌어 §2-1 의
연속 기록이 의미를 잃는다. 정리는 그 **주변**(부채꼴 `__init__`)만 한다.

## 3. 지울 것과 순서 — PR 7개

등급은 R1 기준. 실주문 경로 코드를 **지우는** 것은 주문을 만들 수 없으므로 B 로 둔다(운영자가 A 로 올리면 따른다).

| PR | 범위 | 대략 크기 | 등급 |
| --- | --- | --- | --- |
| L1 | 루트 잡동사니(`run_backtest_comparison.py` · `verify_*` · `config_examples.yaml`) · `docker-compose.yml` 의 레거시 서비스 24개(유지: dashboard · strategy-builder-ui · caddy · redis · prometheus · 테스트용 redis-test/tests) 와 그것만 쓰는 Dockerfile 3개(`forecasting` · `mlflow` · `stream_exporter`) · `performance-baseline.yml` 과 `tests/performance/` | 소 | B |
| L2 | `services/` 중 `dashboard` · `monitoring` 을 뺀 25개 디렉터리(`trading` 13k 줄 포함) + 그 테스트 + 그 서비스만 읽는 `config/*.yaml` · `Dockerfile.prod` 와 그것을 빌드하는 `docker.yml` 잡. `services/monitoring` 은 `shared/kis/*` 가 지연 import 하므로 L6 의 폐포 판정에 맡긴다 | 대 | B |
| L3 | `cli/` 의 `tos` 외 명령 · `scripts/` 의 `tos`·render 외 전부 · `jobs/` · `core/` + 테스트 | 중 | B |
| L4 | dashboard 축소 — `app.py` 를 `/tos` 라우트·헬스·인증만 올리게, 나머지 라우트·도메인·웹소켓 삭제 | 중 | B |
| L5 | UI 축소 — `/tos` 외 페이지(루트 Cockpit `page.tsx` · builder · positions · signals · trades · experiments · execute · market · risk · universe · coverage · evidence · event-context) 와 그 lib·테스트 | 대 | B |
| L6 | `shared/` 중 L1~L5 뒤 폐포에 들지 않는 모듈 + 테스트 + `config/strategies/stock/` 등 | 대 | B |
| L7 | 부채꼴 `__init__` 정리 → 2차 폐포 축소(`shared.llm` · `strategy_builder` · `strategy_lab` · `regime` 등이 빠지는지 측정) | 중 | B |

**각 PR 의 삭제 기준:** «폐포 밖» 만 지운다. 폐포 안이지만 쓰지 않아 보이는 것은 L7 의 측정 뒤로 미룬다.
삭제 목록은 PR 본문에 폐포 측정 결과(전·후 모듈 수)로 남긴다.

**L2 부터의 테스트:** 지운 코드의 테스트는 같이 지운다. `test.yml`(레거시 `test` 워크플로) 의 대상이 줄어들 뿐
필수 체크(`tos-gate` · `ruff` · `tos-firewall`)는 그대로다.

**문서·메모리 (각 PR 에 같이):** 지운 런타임을 설명하는 `CLAUDE.md` 절(Current Runtime Architecture · Trading
Runtime Rules 의 stock/futures 레거시 서비스 문단 · Development Commands) 과 런북(`stock-pipeline-cutover-m5d` ·
`futures-pipeline-cutover-f9` · `paper-live-code-separation`) 은 마지막 PR(L6) 에서 한 번에 고친다.
`docs/plans/` 의 과거 계획은 역사 기록이라 남긴다. Non-Negotiable Rules 는 그대로 둔다(Redis·KST·시크릿·실전
선물 미펀딩은 TOS 에도 적용된다).

## 4. 일정 — 세션을 깨지 않는다

| 날짜 | 할 일 |
| --- | --- |
| 11-07 (토) | 이 계획 승인 |
| 11-09 ~ 11-10 | L1 · L2 (장후 머지 → 다음날 preflight) |
| 11-11 ~ 11-13 | **머지 없음** — 11-11 롤 dry-run · 11-12 첫 실롤 · 11-13 A05612 첫 세션 |
| 11-16 ~ 11-18 | L3 · L4 |
| 11-19 | **머지 없음** — 수능일 개장 지연 |
| 11-20 ~ 11-27 | L5 · L6 |
| 11-30 ~ | L7 (M4 10 거래일 창 안이라 하루 B3 확인을 거쳐 머지) |

머지 규칙: **15:50 뒤 ~ 다음날 08:30 전**에만 머지하고, 머지 직후 다음 거래일 LONG·SHORT·STOCK preflight 를
돌린다(`run-cp3-tenant-daily.sh <DIR> --preflight <날짜>`). 다음날 장후 B3 `verdict ok · unresolved 0` 로 닫는다.
설치된 cron 래퍼(`~/.config/kis-probes/run-cp3-tenant-daily.sh`) 는 이 계획이 건드리지 않는다.

## 5. 각 PR 의 확인 (측정으로만)

1. 폐포 재측정: `tools/tos_cp3/**` · `tools/broker_probes/**` · `cli/commands/tos_status.py` ·
   `services/dashboard/routes/tos_projection.py` 를 뿌리로 한 폐포에 **지운 모듈이 0개**.
2. CI 필수 체크 green + 남은 테스트 green.
3. 생산자 import 스모크: `python -c "import tools.tos_cp3.produce_fields, tools.tos_cp3.emit_legacy_decisions"`.
4. 다음 거래일 preflight 3방향 rc 0, 그다음 장후 B3 `verdict ok`.
5. L4·L5: `/tos` 200 과 `/api/health` 응답이 정지 전과 같다(재빌드 뒤 컨테이너로 확인).
6. L7: B3 증인 바이트 동일성 — 지난 5 거래일 창에서 `emit_legacy_decisions` 출력이 정리 전과 **바이트 동일**.

새 검사기·게이트는 만들지 않는다(R5). 폐포 측정은 PR 본문에 결과만 남기는 일회성 명령이다.

## 6. 되돌리기

- 코드: PR 단위 `git revert`. 지운 코드는 git 이력에 남는다.
- 컨테이너: 이 계획은 코드만 지운다. 정지된 컨테이너·이미지·볼륨·Redis 데이터는 그대로다(§7 결정 2).
- 레거시 paper 를 다시 띄울 일이 생기면 L2 전 커밋(태그 `legacy-final` 을 L1 머지 직전에 단다)에서 띄운다.

## 7. 운영자 결정

1. **이 계획 승인** — 위 순서와 일정.
2. **정지된 레거시 컨테이너 18개와 이미지 삭제** (`docker rm` + 이미지 정리). 권장: L2 머지 뒤 한 주 지켜보고
   지운다. 되돌리기는 `legacy-final` 태그에서 재빌드.
3. **B3 증인 보존** (§2) — 권장대로 `TOS_PAPER_READY` 까지 레거시 Setup D 를 바이트 그대로 둔다.
4. **UI 레거시 화면 삭제(L5)** — `/builder`(노코드 전략 빌더) 등 운영자가 아직 여는 화면이 있으면 L5 에서 뺀다.

## 8. 하지 않는 것

- `tos/` 이동·저장소 분리(분리는 라이브 게이트, 경계 설계 §6.2).
- B3 증인 코드의 리팩터링·이동.
- 새 기능·새 가드·새 CI 잡.
- `docs/` 대량 삭제(역사 기록). 지운 런타임을 **현재 규칙처럼** 설명하는 문서만 고친다.
