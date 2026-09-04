> [재심 스탬프 20260904-001114 안내] 이 증거는 1차 스탬프 .omc/review/20260903-165133/evidence/style.md 의 사본이다 — HEAD b5d2448a(수정 커밋 067ecb2e·2e5edb4a 이전) 기준 관측. 수정된 파일군(tools/tos_completion_status.py · tools/tos_spec_status.py · 두 테스트 파일 · D0-5 7 docstring · 생성물)에 대한 관측은 낡았을 수 있다.

# Style Lens — D0 구현 블록 (HEAD faea9720)

범위: `git diff 28475ca1^ HEAD -- . ':!docs/plans' ':!docs/reviews'` (34파일, +14530/-109).
증거만 산출, 판정 없음. 파일 미편집(read-only).

## ① 요약

- **린터 3종 실측**: black 69파일(전체 71파일 대상 — 계약 문언 "70"과 1건 드리프트,
  in-range 파일 2건은 회귀 아님), mypy(`tos/src/tos`) 8건 전부 사전존재 확인,
  ruff 0건.
- **신규 코드(전체 신규 파일 3종: `tos_completion_status.py`·`tos_contract_index.py`·
  `test_tos_completion_status.py`)는 타입 힌트 100% 완비**(AST 실측, 누락 0) · docstring
  보유 · ruff 위반 0.
- **실질 결함은 소수**: 100줄 상한 초과 함수 4개(신규 코드), `tools/` mypy 확장 실행에서
  드러난 `Any` 전파 1건(사전존재 검사기 의존).
- 나머지는 "관찰"로 분류 — sha 핀 리터럴(설계 의도), raw dict row 접근(주변 코드와 일관),
  PYBIN 절대경로 기본값(사전존재·이미 추적 중인 항목).

## ② 발견 목록

### F-1 [MEDIUM] 100줄 함수 상한 초과 — 신규 코드 4건 (운영자 상시 지침)

AST로 diff 범위 전체 `.py` 순회(`ast.FunctionDef`/`AsyncFunctionDef`, end_lineno 기준)해
100줄 초과 함수를 전수 나열한 뒤, 각 함수를 `git blame`/hunk 대조로 신규-vs-사전존재를
분리했다. 아래 4건은 **diff hunk 안에서 신규 작성된** 함수다(파일 자체가 이번 diff의
신규 파일):

| 위치 | 함수 | 길이 |
|---|---|---|
| `tools/tos_completion_status.py:855` | `check_k5_fwd_metrics` | 103줄 |
| `tools/tos_completion_status.py:1098` | `check_u14` | 110줄 |
| `tools/tos_completion_status.py:3902` | `render_completion_status` | 140줄 |
| `tools/tos_contract_index.py:964` | `render_markdown` | 128줄 |

부차: `tests/tools/test_tos_completion_status.py:661` `write_corpus` 166줄 — 테스트
코퍼스 조립 헬퍼(신규 테스트 파일). 프로덕션 로직이 아니라 심각도는 낮지만 동일 지침
대상.

같은 스캔에서 잡힌 다른 초과 함수(`tos_evidence_run.py`의 `main`(631줄) 등 다수,
`tos_spec_status.py:validate_migration_conformance`, `construction.py:derive_order_size`,
`records.py:send_boundary_context`, `wfcanon-v222.py:blob_layer`,
`test_u17_verify.py:_materialize`)는 **diff hunk 밖의 사전존재 코드**로 확인됨
(blame 커밋 전부 28475ca1 이전, 예: `construction.py`/`records.py`는 이번 diff에서
docstring만 편집되어 508/787행 근방 함수 본문은 무변경). 별도 표기, in-range 아님.

**권고**: `check_u14`/`check_k5_fwd_metrics`류는 이미 `_parse_anchor_distribution` 같은
헬퍼로 부분 분리돼 있어 패턴은 있다 — 조건별 서브체크를 추가로 함수 추출하면 100줄
안으로 수렴 가능. `render_completion_status`/`render_markdown`은 렌더 함수 특성상
섹션 단위 분리가 자연스럽다. 강제 리팩터보다 후속 정리 항목으로 등재 권고.

### F-2 [LOW] mypy `Any` 전파 — `tools/tos_contract_index.py:396` (신규 파일, tools 확장 실행에서만 노출)

CLAUDE.md 계약 문언의 baseline 명령(`mypy tos/src/tos --ignore-missing-imports
--no-error-summary`)은 `tools/`를 커버하지 않는다. 감사 지침에 따라 `tools/` 전체를
별도로 `mypy tools/ --ignore-missing-imports`로 돌리면 **사전존재 구조 문제**로 즉시
중단된다:

```
tools/broker_probes/common.py: error: Source file found twice under different
module names: "broker_probes.common" and "tools.broker_probes.common"
```

(`tools/broker_probes/`는 이번 diff 범위 밖 — `git diff --stat -- tools/broker_probes/`
공백, 최종 수정 `4fbf3618`은 2026-08-07 P-8/N-15 웨이브. `__init__.py` 부재로 인한
사전존재 결함이며 in-range 아님.)

`--explicit-package-bases`로 우회해 전체 스캔하면 신규 파일 중 1건 노출:

```
tools/tos_contract_index.py:396: error: Returning Any from function declared to
return "bool"  [no-any-return]
```

`_is_table_row_definition(doc: tcc.ContractDoc, lineno: int, identifier: str) -> bool`이
`doc.lines[lineno-1]`(사전존재 `tools/tos_contract_check.py`의 `ContractDoc.lines`
속성 — 그 클래스 자체 타입이 약함)에서 파생한 `str`이 사실은 `Any`로 추론돼
`first == identifier` 비교가 `Any`를 반환한다. 신규 코드 자체의 로직 결함은
아니고(항상 `bool`이 될 값), 사전존재 의존 모듈의 타입 약화가 신규 파일로 전파된
케이스. `tools/` 나머지 mypy 위반(`ladder-v222e5.py`·`pagelimb-v222e5.py`·
`spikes/phase0_contract/*`·`tos_contract_check.py`·`broker_probes/*`)은 전부
diff 범위 밖(사전존재)으로 확인.

**권고**: `cast(bool, first == identifier)` 또는 로컬 `# type: ignore[no-any-return]`
with 사유 주석. 사소하나 8건 baseline과 별도로 tools/ mypy를 게이트에 편입할 계획이
있다면 선반영 가치 있음.

### F-3 [observation] black — baseline 문언 "70"과 실측 "69" 1건 드리프트, in-range 파일은 회귀 아님

`black --check tos/src tos/tests tests/tos_l3 tools`(CLAUDE.md 계약이 지정한 정확한
명령) 실측 결과 **69개 파일**이 reformat 대상. 계약 문언은 "black 70파일"이라 1건
차이 — 코드 결함이 아니라 문서 드리프트(과거 측정 이후 어느 파일이 이미 정리됐을
가능성). in-range 34파일 중 reformat 대상은 2건:
`tos/src/tos/egressgw/construction.py`, `tos/src/tos/egressgw/records.py`.

`black --diff`로 정확히 어느 행이 걸리는지 확인한 결과, construction.py의 reformat
훅은 256/592/828행 부근(기존 함수 시그니처/삼항식 줄바꿈) — 이번 diff는 이 파일에서
**29-41행 docstring만** 편집했다(`git diff` 확인). 즉 이번 diff가 새로 black 위반을
만든 게 아니라 **이미 위반 상태였던 파일에 문서만 얹은 것** — 회귀 아님, 사전존재
부채. `records.py`도 동일 패턴(123-134행 docstring 편집, 위반은 다른 행).

### F-4 [건전함 확인] mypy `tos/src/tos` 8건 — 전부 사전존재, in-range 아님

`mypy tos/src/tos --ignore-missing-imports --no-error-summary` 실측 8건, 계약
baseline과 개수 일치:

```
tos/src/tos/capsule/predicates.py:456       unused-ignore
tos/src/tos/staterestore/reload.py:196-200  arg-type ×5
tos/src/tos/egressgw/construction.py:505    operator (Decimal % None)
tos/src/tos/egressgw/gateway.py:939         union-attr
```

`construction.py:505`를 `git blame`으로 확인 — `e5d7be4a0`(2026-07-29), 이번 diff는
이 파일에서 29-41행 docstring만 건드림. 8건 전부 diff hunk 밖. **CLAUDE.md "Phase 0는
mypy baseline을 고치지도 늘리지도 않는다" 준수 확인.**

### F-5 [건전함 확인] ruff — 0건

`ruff check tos/src tos/tests tests/tos_l3 tools` → `All checks passed!`. 이 프로젝트의
ruff select 세트(`E`/`W`/`F`/`I`/`B`/`C4`/`UP`/`ARG`/`SIM`, `pyproject.toml:263-273`)는
미사용 import(F401)·import 순서(I)·bugbear류를 포함하므로, in-range 34파일에 unused
import·순환/와일드카드 import 징후 없음을 구조적으로 확인.

### F-6 [observation] raw dict row 접근 — 신규 코드, 주변 코드와 일관

`tools/tos_completion_status.py`(신규 4162행)에서 `row["evidence_id"]`류 dict 첨자
접근이 104회. 운영자 상시 지침(원시 dict 남용 금지·Pydantic v2 DTO 선호) 대비 관찰로
등재.

다만 대조군 확인 결과: (a) 이 패턴은 CSV/YAML 파싱 경계(`csv.DictReader`류 산출물)에
한정되고, 검사기 내부 상태·판정 결과는 전부 `@dataclass(frozen=True)`로 모델링됨
(`tos_completion_status.py`에 frozen dataclass 5개 이상 확인); (b) 사전존재
`tools/tos_spec_status.py`도 동일 패턴 46회로 이미 이 코드베이스 `tools/` 검사기군의
관례임(`tos_evidence_run.py` 1회). 즉 이번 diff가 새 패턴을 들여온 게 아니라 기존
`tools/` 관용구를 그대로 따른 것. 운영자 지침은 `shared/`/`domains/` 런타임 도메인
코드를 겨냥한 것으로 읽히며, CSV 행 파싱 경계에 그대로 적용하면 `csv.DictReader`를
매 필드 Pydantic 모델로 감싸는 과잉이 될 수 있다 — 코드 결함으로 올리지 않고 관찰로만
등재.

### F-7 [observation] sha256 핀 리터럴 — 설계 의도, lockstep 검증됨

`tools/u17-verify.sh:75`의 `LIT2=059e13f2...`와 `.github/workflows/tos-gate.yml:17`의
동일 sha256이 이번 diff에서 **함께** `1817c9ef...` → `059e13f2...`로 재핀됨을 확인
(두 diff 동일 신규 값, lockstep 유지). 프로젝트 메모리 기록과도 일치
(`tos-landing-gate-structural-blockers` — "핀 하니스 수정+재핀"). 작업 지침이 명시한 대로
"결함 아님" 확인.

### F-8 [LOW, 사전존재·이미 추적 중] `u17-verify.sh:76` PYBIN 기본값 절대경로 하드코딩

```
PYBIN="${U17_PYBIN:-/Users/harris/Development/private/kis_unified_sts/.venv/bin/python}"
```

`U17_PYBIN` 미설정 시 운영자 로컬 홈 경로가 그대로 fallback. 이번 diff의 hunk는 이
파일에서 sha 리터럴 한 줄만 건드렸고(위 diff 확인), 이 행은 편집되지 않음 — **사전존재,
in-range 아님**. 이미 프로젝트 메모리에 후속 항목으로 등재돼 있음
(`tos-next-work-after-phase0-machine-surface.md`: "⑤ u17-verify PYBIN 절대 경로").
새 결함 아님, 기존 추적 확인만 기록.

### F-9 [건전함 확인] 타입 힌트 — 신규 파일 3종 100% 완비

AST로 `tools/tos_completion_status.py`·`tools/tos_contract_index.py`·
`tools/tos_profile_census.py`(전부 신규 파일)의 모든 함수 매개변수·반환값 어노테이션
존재 여부를 순회 확인 — **누락 0**. (단순 정규식으로 먼저 스캔했을 때 다중행 시그니처를
오탐했으나 AST 재확인으로 오탐 배제.)

### F-10 [건전함 확인] docstring — 모듈/공개 함수 수준 확인

3개 신규 파일 전부 모듈 docstring 보유. 샘플 확인한 `tools/tos_profile_census.py`는
Google 스타일에 가까운 구조(요약행 → 상세 설명 → 케이스 열거)를 일관되게 사용하고,
`tools/tos_completion_status.py`의 `check_u14`류도 목적 한 줄 + 내부 절차 주석 패턴을
파일 전체에서 일관 유지. 한국어 주석이 이 리포의 표준이라는 전제(작업 지침) 하에
문장 단위 언어 혼용은 관찰되지 않음.

### F-11 [건전함 확인] DRY 리팩터 — `tools/tos_profile_census.py` 신설

`_is_bound_value`/`_profile_null_key_census`를 `tools/tos_evidence_run.py`에서
`tools/tos_profile_census.py`로 추출하고 `tos_evidence_run.py`는 import로 대체
(`git diff` 확인: 구현 삭제 56행 + import 2행 추가). 모듈 docstring이 추출 이유(DRY,
CLAUDE.md 인용)와 두 소비처(`tos_evidence_run.py`, `tos_spec_status.py`)를 명시.
동작 무변경 주장이 docstring에 있고, 원본 로직과 바이트 비교 시 실질적으로 동일
(fail-closed 형태 검증 규칙 그대로 이전) — 좋은 스타일 사례로 기록.

### F-12 [건전함 확인] 테스트 위생

- `tests/tools/test_tos_completion_status.py`: 테스트 함수 184개. 도메인 관용 네이밍
  `_is_red`(부정 경로, 59개) / `_is_green`(긍정 경로, 7개) + 그 외 fail/invalid/missing류
  네이밍 43개 — happy+negative 균형 확인.
- `tests/tools/test_tos_contract_index.py`: 21개, `_ambiguous`/`_requires_*` 등
  경계조건 네이밍 확인.
- `tests/tools/` 디렉터리에 `conftest.py` 없음 — 각 테스트 파일이 자체 픽스처를 갖는
  기존 관례와 일관(리포 전역 패턴, 이번 diff가 새로 만든 문제 아님).
- `bound_set_digest` 하드코딩 확인 — `test_tos_completion_status.py:88`
  `_bound_set_digest()` 헬퍼가 동적 계산하고, 계약이 명시한 3차 핀 성격의 리터럴은
  헬퍼 함수 결과이지 임의 상수가 아님. 작업 지침이 말한 "결함 아님" 전제 확인.
- `pytest.mark.parametrize` 1건 확인, `-p no:cacheprovider` 등 실행 규약은
  `pytest.ini`/CI 설정 레벨이라 개별 테스트 파일에 없는 것이 정상.

## ③ «점검했고 건전함» (명령·출력)

```
$ .venv/bin/ruff check tos/src tos/tests tests/tos_l3 tools
All checks passed!

$ .venv/bin/mypy tos/src/tos --ignore-missing-imports --no-error-summary
(8 errors — 전부 사전존재, F-4 참조)

$ .venv/bin/python <ast 순회 — 3개 신규 파일 타입 힌트 누락 스캔>
(출력 없음 = 누락 0)
```

- black in-range 2건(F-3) 모두 diff가 손대지 않은 기존 행에서 발생 — 회귀 없음.
- 신규 파일 3종 모듈 docstring 보유, 함수 시그니처 타입 힌트 100%.
- import 위생(F401/순환/와일드카드) — ruff 구조적으로 0건.

## ④ 미확인 항목

- **shellcheck 미실행** — 로컬 환경에 `shellcheck` 바이너리 없음(`which shellcheck` →
  not found). `tools/tos_entry_harness.sh`/`tools/u17-verify.sh` diff는 수동 읽기로만
  확인(F-7 관련 sha 핀, awk `exit`→플래그 전환 로직 — 주석이 Linux CI 실측 근거와
  대조군을 명시해 품질은 양호해 보이나 shellcheck 정적 분석 자체는 못함).
- `tools/tos_completion_status.py`(4162행) 전체 함수 목록 중 100줄 초과 3건만 AST로
  확인했고, 90~99줄 근접 함수(경계 근처)는 전수 나열하지 않음 — 필요하면 임계값을
  낮춰 재스캔 가능.
- CSV 데이터 파일(`EVIDENCE-REQUIRED-KINDS.csv` 등, +2537행)과 `tos-spec/` 마크다운
  산출물은 스타일 렌즈 범위 밖으로 판단해 미검사(구조/내용은 다른 렌즈 소관).
- `config/tos_completion.yaml`(신규 57행)의 스키마/값 적절성은 미검사(스타일 관점에서
  하드코딩 없음만 확인 — `tools/tos_completion_status.py:75`가 이 경로를 config로 읽는
  구조 확인, F-6 참조).
