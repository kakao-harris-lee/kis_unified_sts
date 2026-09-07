# TOS Phase 1 실행 계획 — 커널 결함 제거와 품질 hard gate

- **상위 계획**: `docs/plans/2026-08-11-tos-completion-development-plan.md` §6 Phase 1
- **운영자 지시 (2026-09-07)**: 「모의투자에서 실측하는 부분 제외하고 Phase 1 부터 진행」
- **저작**: 세션 모델 단독 (운영자 지시 2026-09-04 · 기획 파이프라인 없음)
- **권한**: 이 계획과 그 구현은 어떤 게이트·축·계좌에 대한 권한도 부여하지 않는다.
  G1~G3 판정·ADR acceptance·live authorization 은 별개 축이다.

## 1. 기준선 (2026-09-07 실측 · main `f52ebb8f`)

| 항목 | 값 |
|---|---|
| mypy `tos/src` | 8 errors / 4 files (`staterestore/reload.py` 5 · `egressgw/construction.py:507` · `egressgw/gateway.py:939` · `capsule/predicates.py:456`) |
| Black `tos/` | 69 files would be reformatted |
| Ruff `tos/` | 0 |
| 1,000줄 초과 모듈 | 8 (`sir/predicates.py` 1,681 최대) |
| 크기 budget · 예외 register | 부재 |
| CI (`tos-firewall` 잡) | firewall · import-linter · tos tests · spec/completion/contract 검사기 · governance 배터리 · L3 — **Black·mypy·mdBook 부재** |
| TOS-GAP-001 | `gateway.py:939` 가 `conformance_result=None` 에서 `.value` 접근 → `AttributeError` (mypy union-attr 와 동일 자리) |

## 2. 작업 분해 (Phase 1 작업 1~7 → 레인)

| 작업 | 내용 | 레인 | 표면 |
|---|---|---|---|
| 5 | Black baseline 기계적 커밋 | 직접 (완료 `7da2fa36`) | `tos/**` |
| 1 | `CandidateConstruction` 결합 validator — `command`·`conformance_result`·`numerical_result`·`no_silent_widening_ok`·`denial_reason` 의 허용 조합만 통과 (부분 구성은 구성 시점에 거부) | A | `tos/src/tos/egressgw/records.py` |
| 2 | malformed construction → 예외가 아니라 `UNKNOWN`/`DENIED` + `SEND_REFUSED` evidence 로 귀결되는 테스트 | A | `tos/tests/egressgw/` |
| 4 | mypy 8건 → 0 (실제 결함 vs narrowing 분리 기록) | A (egressgw 2건) · C (staterestore 5 · capsule 1) | 해당 4파일 |
| 3 | `POTENTIALLY_LIVE_OBSERVED` 이후 모든 예외 경로에서 claim 소비 유지 + 종결 evidence 1건 + 재전송 0 불변식 검증 | B (A 이후) | `gateway.py::__call__` step 17~19 · 신규 테스트 파일 |
| 6 | 모듈·함수 크기 configurable budget + 예외 register(owner·분해 순서·만료일) + 검사기 + 테스트 | C | `config/tos_size_budget.yaml` · `tools/tos_size_budget.py` · `tests/tools/test_tos_size_budget.py` |
| 7 | `tos-firewall` 잡에 Black·mypy·크기 budget·mdBook 스텝 추가 (같은 잡의 스텝 — 필수 체크 이름을 늘리지 않는다) | C | `.github/workflows/tos-firewall.yml` |

`.github/workflows/tos-gate.yml`·`tools/tos_entry_harness.sh`·완료 계약 본문은 **건드리지 않는다**
(재핀 라운드·S-26 리셋 축). `tos-firewall.yml` 은 계약 앵커가 아님을 실측(`tools/` 에 참조 0).

## 3. 결정과 기각 대안

- **크기 budget 검사기는 소형 AST 스크립트** (`ast.end_lineno`). 기각: ruff 는 파일 길이 규칙이 없고,
  pylint `C0302/R0915` 는 owner·만료일 register 를 표현하지 못한다. 임계값은 YAML(설정 주도 규칙).
- **기존 초과분은 전부 register 등재 · 분해는 Phase 1 범위 밖**. 등재는 면허가 아니라 가시성이다 —
  만료일 경과 = red. 만료일은 운영자 조정 가능한 설정값이다.
- **CI 는 스텝 추가만**. 필수 체크 지정은 룰셋(저장소 밖 · UNCHK-008 계열)이라 운영자 소관.
- **U-17 `PREVENTION_ACTIVE` 재확인**은 Phase 1 완료 판정 시점에 `bash tools/u17-verify.sh` live 로
  수행 (gh 인증 필요 · 모의투자 아님). 이 계획의 마지막 단계.

## 4. 종료 조건 (상위 계획 그대로)

- focused regression + 전체 `tos/tests` green
- Ruff/Black/mypy 0
- 미등록 budget exception 0
- U-17 `PREVENTION_ACTIVE` 재확인

## 5. 제외 (운영자 지시)

모의투자 서버 실측이 필요한 항목은 없음 — Phase 1 은 전부 로컬·CI 정적/동적 검사다.
