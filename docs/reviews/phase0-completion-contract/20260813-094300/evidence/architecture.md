# 아키텍처 렌즈 **재심** — Phase 0 완료 계약 프로토타입 v2.6

```yaml
lens: architecture
role: 증거 생산 (판정 없음 — verdict 는 Codex 심판 레인 소관)
target: tools/spikes/phase0_contract/{test_contracts.py, audit_guard.py, proto/*}
prior_verdict: .omc/review/20260813-075200/verdict.md (v2.5, needs-attention, critical 1 + high 3)
prior_lens_evidence: .omc/review/20260813-075200/evidence/architecture.md (A-1..A-9)
baseline_run: exit 0 · 대조군 32건 중 양방향 성립 32건 · 앵커 5종 전부 일치
method: 원본 무수정(SHA256 시작=종료 동일). in-process 모듈 속성 교체 + 격리 사본 디스크 편집.
findings: 신규 9 (CRITICAL-class 1 / HIGH 2 / MEDIUM 4 / LOW 2)
```

**무결성 고지.** 감사 전후 원본 12파일 SHA256 **동일**(`원본 SHA256 IDENTICAL`).
감사 도중 내 뮤테이션이 원본 트리에 실물 2건(`__audit_probe_dir`·`__audit_probe_w.tmp`)을
생성한 사고가 1회 있었고 즉시 제거·검증했다 — 그 사고 자체가 아래 **N-4** 의 증거다.
디스크 편집은 전부 `<scratch>/arch-lens/repo/` 격리 사본에서 수행했다(`.git` + 동일
상대경로 보존).

**병렬 렌즈 오염 고지.** 세션 스크래치패드가 4개 렌즈 간 공유되어, 내 첫 사본
(`<scratch>/repo/`)이 형제 렌즈의 편집(`test_contracts.py:96` 에 `__import__("proto.register")`
주입)으로 오염된 것을 발견해 폐기하고 `arch-lens/` 로 격리했다. 아래 수치는 전부 격리
후 재측정값이다.

---

## 요약 — 처분

| 직전 발견 | 처분 | 근거 |
|---|---|---|
| **심판 #1 (critical)** import-before-guard | **해소** | import-time 실 register 열람이 `AuditViolation` 으로 차단됨 (대조군: 가드 밖에서 동일 코드가 93,904 B 읽음) |
| **심판 #2 (high)** 경로 별칭·위치 위조 | **해소** (잔여는 등재됨) | `_io`/`posix`/대소문자 8종 전건 차단 · `.git`+`samefile` · `L-LOCATE-FORGE` 로 등재 |
| **심판 #3 (high)** `mutant_red` 자기충족 | **부분해소** | 방향②가 실제 판정 함수(`self_check_green`)를 통과하도록 바뀜. 그러나 **생산 배선**은 여전히 합성 dict 로 대체되고, 8항 중 2항(`unresolved`·`digest_drift`)은 양성 커버리지 0 → **N-1·N-2** |
| **심판 #4 (high)** 앵커 정의역 구멍 | **해소(디스크) / 부분해소(런타임)** | ⒠ 소스바이트 앵커가 9파일 전 바이트를 묶어 디스크 편집 3종 전부 red. 런타임 대입은 값 앵커 2종만 추가되어 4종이 여전히 침묵 → **N-3** |
| A-1 앵커 정의역 | 해소(디스크)/부분해소(런타임) | 위와 동일 |
| A-2 `FORBIDDEN_ARTIFACTS` | **해소** | `T-77-③` 항목 전수 + `tuple_anchor` 값 앵커 |
| A-3 `REQUIRED_METRICS` | **해소** | `T-67` + `declared_required_metrics` 양방향 등재 |
| A-4 private `_check_*` 직접 호출 | **미해소** | 11개 호출 지점 그대로 (`test_contracts.py:474,498,499,1258,1262,1676,1678,1716,1719,1734,1736`) |
| A-5 `proto/` 안의 뮤테이션 어포던스 | **미해소** | `enforcement.violating_contexts` · `gates.build_reasons_ignoring_blocks_gate` · `floor.use_floor` 전부 그대로 |
| A-6 광고 목록 ↔ 실제 차단 목록 | **부분해소** (심각도 하향) | 디스크 드리프트는 ⒠ 가 본다. 정합 검사는 여전히 없고 런타임 축소는 침묵. **다만 실제 쓰기 탈출은 0** — 실측으로 확인 → **N-3** |
| A-7 ⒜ 잉여 레이어 | **미해소 · 악화** | ⒠ 도입으로 ⒜ 는 이제 **구조적으로 ⒠ 의 진부분집합** → **N-8** |
| A-8 `self_check` 책임 과밀 | **부분해소** | 3개 헬퍼로 분해됐으나 `self_check` 140행 · `t77_boundary` **449행** → **N-9** |
| A-9 "proto 7개" 거짓 주석 | **해소** | `config.yaml:74-76` 이 "proto 6개 · `__init__.py` 는 코드 객체 없음"으로 정정 + ⒠ 가 `__init__.py` 포함 9파일 |

**회피 판정 0건.** 저작자가 닫았다고 주장한 항목 중 실측에서 닫히지 않은 것은
`digest_drift` 소비 배선(N-1)뿐이며, 이는 v2.6 이 새로 만든 표면이지 기존 지적의 회피가 아니다.

---

## 해소된 것 — 반대 방향 증거를 먼저 적는다

### 심판 #1 (critical) — import-before-guard: **해소**

격리 사본의 `proto/register.py` **모듈 레벨**에 바이트 조립 경로로 실제 register 를
읽는 문장을 주입했다(리터럴·AST 스캔에 걸리지 않는 형태 — `bytes([...]).decode()`
는 폴딩 대상 밖이며 실제로 `T-77-①`/`①-AST` 는 발화하지 않았다).

```
=== 심판 critical 재현: import-time 모듈 레벨 실 register 열람 ===
[밀수 결과] 차단됨: AuditViolation: 코퍼스·register 접근 차단: open:코퍼스 디렉터리 접근: /Users/harris/Developm…
대조군 32건 중 양방향 성립 31건
미성립: ['SELF-1']

=== 대조군: 가드 밖 순수 파이썬 ===
[밀수 결과] 93904
```

**93,904 바이트** — 심판이 v2.5 에서 읽어낸 그 수치가 대조군에서 그대로 재현되고,
v2.6 러너 안에서는 `AuditViolation` 으로 차단된다. 두 층이 동시에 발화했다:
런타임 차단(`audit_guard._hook` → `_enforce`, `audit_guard.py:185-217`)과
소스바이트 앵커 드리프트(→ `SELF-1` red). **구조적으로 해소됐다.**

기제: `test_contracts.py:96` 의 `import audit_guard` 가 `:97-98` 의 `proto` import 보다
앞서고, `audit_guard.py:220` 의 `sys.addaudithook(_hook)` 이 모듈 로드 시점에 실행된다.
`T-77-AUDIT`(`:1048-1061`)이 이 순서를 러너 자기 소스의 AST 에서 파생해 관측한다 —
자기신고가 아니다.

### 심판 #2 (high) — 경로 별칭·위치 위조: **해소**

`T-77-AUDIT` 방향②가 `_io.open`·`_io.FileIO`·`posix.listdir`·`posix.scandir` 와
대소문자 변형 2종 + 쓰기 프로브 2종 = **8/8 전건 차단**(baseline 출력).
판정 재료를 뮤테이션해 그 층이 실제로 걸려 있음도 확인했다:

```
[잡힘] _CORPUS_FOLDED → 불일치 값   failed=['SELF-1','T-77-AUDIT','T-77-①-READ']
[잡힘] _REGISTER_FOLDED → 불일치 값 failed=['SELF-1','T-77-AUDIT']
```

구현이 하나로 접힌 것도 확인했다 — `boundary.read_violation`(`boundary.py:443-454`)이
`audit_guard.path_violation` 에 위임하므로 두 층의 판정이 드리프트할 수 없다. **DRY 교정으로 건전하다.**

위치 검사는 `REPO_MARKERS=('.git',)` 로 좁혀졌고 `os.path.samefile` 이 추가됐다
(`boundary.py:476-492`). v2.5 로 되돌리면 잡힌다:

```
[잡힘] boundary.REPO_MARKERS →('.git','pyproject.toml')  failed=['SELF-1','T-77-④']
[잡힘] boundary.EXPECTED_RUNNER_RELPATH 변조             failed=['SELF-1','T-77-④']
```

잔여(`.git` 을 만들고 사본을 예상 상대경로에 두면 통과)는 `L-LOCATE-FORGE` 로
등재돼 있고, 본 감사의 격리 사본이 정확히 그 조건으로 32/32 GREEN 을 냈다 —
**등재된 한계가 실측과 일치한다.**

### 심판 #4 / A-1·A-2·A-3 — 앵커 정의역: 디스크 편집에 대해 **해소**

⒠ `source_bytes_anchor`(`test_contracts.py:389-407`, 대상 `anchor_source_paths()` `:376-386`)
가 러너 + `audit_guard.py` + `proto/*.py`(**`__init__.py` 포함**) **9파일의 정확한
바이트**를 묶는다. 직전 침묵 3종을 격리 사본에서 **디스크 편집**으로 재현:

```
① proto/boundary.py::_PATH_BLOCKED 5개 삭제
   → 31/32 · 미성립 ['SELF-1'] · 소스바이트=c07a14ab8939ab78!=63b83b185ad21abd
② proto/register.py::FIXTURE_CLAUSES +1절
   → 31/32 · 미성립 ['SELF-1'] · 소스바이트=b11245fb30e0dfd8!=63b83b185ad21abd
③ proto/config.py::REQUIRED_KEYS 신규 4키 삭제
   → 31/32 · 미성립 ['SELF-1'] · 소스바이트=92e9ab67d60fb8f3!=63b83b185ad21abd
```

**세 건 전부 red.** `config.yaml:74-76` 과 `:80-81` 의 거짓 주석 2건도 정정됐고
(⒟ 정의역 = "proto 6개, `__init__.py` 는 코드 객체 없음", "어떤 편집이든…도 거짓이었다"),
정정 내용이 실제 코드(`test_contracts.py:1904-1913` 8개 모듈 튜플)와 일치한다.

A-2·A-3 은 **런타임 대입에서도** 닫혔다 — 값 앵커 2종이 추가됐다:

```
[잡힘] M1 boundary.FORBIDDEN_ARTIFACTS 5→1              failed=['SELF-1','T-77-③']
[잡힘] M2 REQUIRED_METRICS -imprecise_owner_track       failed=['SELF-1','T-67']
[잡힘] M2 REQUIRED_METRICS -closable_no_rows            failed=['SELF-1','T-67']
[잡힘] M2 REQUIRED_METRICS -superset_declared_pairs     failed=['SELF-1','T-67','T-73']
[잡힘] M2 REQUIRED_METRICS -blank_normative_ref_rows    failed=['SELF-1','T-39','T-67']
```

`T-77-③`(`:927-955`)은 항목 전수를 표적으로 삼고 각 인덱스 삭제가 앵커를 움직이는지도
본다. `T-67`(`:1376-1411`)은 `sorted(REQUIRED_METRICS)==sorted(declared_metrics)` 양방향
+ 인덱스별 삭제 검출을 본다. **직전 A-2·A-3 권고가 그대로 이행됐다.**

### 설정 커버리지 — fail-closed 유지 (실측)

```
config.yaml 키=20 · REQUIRED_KEYS=20 · yaml-required=∅ · required-yaml=∅
```

신규 4키(`anchor_source_bytes_digest`·`anchor_forbidden_artifacts_digest`·
`declared_self_checks`·`declared_required_metrics`)가 `config.py:31-34` 에 등재돼 있어
부재 시 `load_config` 가 중단한다. **프롬프트 항목 6의 fail-closed 요구는 충족.**

### 의존성 방향 — 순환 없음 (실측)

```
audit_guard.py       → (stdlib only)
proto/boundary.py    → ['audit_guard']
proto/register.py    → ['config', 'floor']
proto/enforcement.py → ['config', 'floor']
proto/{config,gates,floor,__init__}.py → (stdlib only)
```

`audit_guard` 는 stdlib 만 의존하므로 **순환 0**. `proto/` 가 러너를 import 하는 지점도 없다.

---

## 신규 발견

## N-1 (CRITICAL-class) — 앵커 5종 전체가 **단일 미검증 소비 seam** 하나에 걸려 있고, 그 seam 을 끊으면 앵커 자신이 자기 절단을 보지 못한다

- **location**: `test_contracts.py:1958` (`drift` 산출) → `:1976`
  (`checks = collect_self_checks(rep, declared, unchk_ids, waivers, drift)`) → `:1978`
  (`clean_green = self_check_green(checks, names_match)`);
  `collect_self_checks` `:1776-1803`; `SELF-2` `:1840-1858`
- **위반한 원칙**: 자기참조 없는 강제(선언층/평가층 일치) · 대조군 직교성
- **finding**:
  앵커 5종의 불일치는 전부 `drift` 리스트 하나로 접히고, 그 리스트가 exit 에 닿는
  경로는 `collect_self_checks(...)["digest_drift"]` **한 줄뿐**이다. `SELF-2` 는 이 항의
  소비를 **합성 dict 주입**으로만 확인한다(`:1854-1856` — `probe = {key: [] ...}; probe[name] = [...]`),
  즉 `digest_drift` 를 **생산하는** 경로(`:1958` 의 앵커 대조)는 어떤 대조군도 통과하지 않는다.
  `SELF-1` 의 방향②도 `probe_checks` 에 `()` 를 넘기므로(`:2005`) 마찬가지다.

  **실측** — `collect_self_checks` 가 `digest_drift` 를 버리도록만 바꾸면:

  ```
  [침묵] (c)   digest_drift 항을 버린다                    failed=없음 · drift=['실행코드']
  [침묵] (c')  위 + GUARDED_ENTRY_POINTS 34→2             failed=없음 · drift=['방출','실행코드']
  [침묵] (c'') 위 + audit_guard.READ_EVENTS 3→1           failed=없음 · drift=['방출','실행코드']
  [침묵] (c''')위 + TOKEN_DEFINITION_NAMES 면제 확대        failed=없음 · drift=['방출','실행코드']
  ```

  앵커가 **드리프트한 채로 32/32 GREEN · exit 0**. 그리고 이 절단을 검출할 유일한 층이
  바로 절단된 ⒟ 이므로 **자기참조**다. 종단 실증:

  ```
  === 결합: 앵커 소비 절단 + `unresolved` 탐지기 사망 ===
  failed=없음 · 앵커드리프트=['실행코드'] → 러너 exit = 0
  → 탐지기 실사용 확인: unresolved_limit_refs(...) = []      ← 탐지기는 죽어 있다
  === 대조: 앵커 소비만 살아있으면 ===
  failed=['SELF-1'] · 앵커드리프트=['실행코드'] → exit=1
  ```

  이것은 심판 #3 이 지목한 결함 클래스("방향②가 헬퍼의 자기충족성만 본다")가
  **한 층 위로 이동**한 형태다. v2.5 에서는 `mutant_red` 가 `clean_green` 과 독립이었고,
  v2.6 에서는 `SELF-2` 가 **소비 함수는 실제 것을 쓰되 입력은 여전히 합성**이다.
- **recommendation**: `SELF-2` 에 **생산 축** 대조군을 더한다 — 각 검사 이름마다
  `collect_self_checks` 를 실제로 호출해 그 항이 비지 않는 상태를 **실제 입력**
  (미등재 노트·부재 참조·의도적 앵커 불일치)으로 만들고 판정이 False 가 되는지 본다.
  `digest_drift` 는 `anchor_pairs` 에 고의로 틀린 기대값 하나를 끼운 프로브로 생산할 수 있다.
  최소한 `drift` 를 리스트가 아니라 **필수 반환값**으로 만들어 `self_check_green` 의
  시그니처에 올리면 소비 누락이 타입 수준에서 표현 불가능해진다.
- **confidence**: 98 (실측, 대조군 포함)

## N-2 (HIGH) — `SELF-1` 방향②의 8항 중 2항이 **양성 커버리지 0** (`unresolved` 는 음성 단언, `digest_drift` 는 항 자체가 없음)

- **location**: `test_contracts.py:2007-2016` (`mutant_red`), 특히 `:2014`
  `and probe.unresolved_limit_refs(unchk_ids) == []`
- **위반한 원칙**: 양방향 대조군 규율(러너 자신의 `:6-7` "한 방향만 확인한 대조군은 무효다")
- **finding**:
  `mutant_red` 의 7개 항 중 6개는 **양성**(검출기가 심은 위반을 실제로 잡는지)인데
  `unresolved` 만 `== []` 라는 **음성** 단언이다. 검출기를 죽여도 이 항은 참으로 남는다.
  `digest_drift` 는 아예 항이 없다.

  **실측** — `collect_self_checks` 의 값만 항상 `[]` 로 만들었을 때
  (이름 집합은 유지 → `names_match` 는 참):

  | 항 | 결과 | 무엇이 잡았나 |
  |---|---|---|
  | `parked` | 잡힘 | ⒟ 실행코드 앵커 |
  | `unresolved` | 잡힘 | ⒟ 실행코드 앵커 |
  | `undeclared` | 잡힘 | ⒟ 실행코드 앵커 |
  | **`digest_drift`** | **침묵 (exit 0)** | — |

  즉 런타임 무력화를 잡는 것은 사실상 ⒟ 앵커 하나이고, `digest_drift` 는 그 ⒟ 를
  소비하는 항이라 자기 자신을 지키지 못한다. 이름 **삭제**는 정상 검출된다
  (`declared_self_checks` 등재 검사가 작동한다 — v2.6 의 목표는 달성):

  ```
  collect_self_checks 에서 'parked'      항 삭제 → failed=['SELF-1','SELF-2']
  collect_self_checks 에서 'unresolved'  항 삭제 → failed=['SELF-1','SELF-2']
  collect_self_checks 에서 'digest_drift'항 삭제 → failed=['SELF-1','SELF-2']
  ```
- **recommendation**: `:2014` 를 양성으로 바꾼다 — `probe` 에 `case=<없는 Case>` /
  `unchk=<미등재>` 노트를 하나 심고 `probe.unresolved_limit_refs(...)` 가 그것을
  **잡는지** 요구한다. `digest_drift` 는 N-1 의 권고와 함께 처리한다.
- **confidence**: 97 (실측)

## N-3 (MEDIUM) — 런타임 대입에 대해 여전히 침묵하는 모듈 레벨 정책 데이터 5종

- **location**: `proto/register.py:29` (`FIXTURE_CLAUSES`) · `proto/boundary.py:190-201`
  (`_PATH_BLOCKED`) · `proto/boundary.py:73-77` (`FORBIDDEN_SOURCE_TOKENS`) ·
  `proto/config.py:13-35` (`REQUIRED_KEYS`) · `audit_guard.py:114` (`_PROBE_DEPTH`)
- **위반한 원칙**: 설정 기반(정책 목록이 코드 상수) · 선언층/평가층 일치
- **finding**: 프롬프트가 요구한 전수 표. **런타임 대입**(디스크 무편집) 기준이다.

| 대상 | `file:line` | 결과 | 잡은 층 |
|---|---|---|---|
| `boundary.FORBIDDEN_ARTIFACTS` 5→1 | `boundary.py:83-89` | **잡힘** | `T-77-③` + 값 앵커 |
| `register.REQUIRED_METRICS` −1 (4종 전부) | `register.py:36-41` | **잡힘** | `T-67` + `declared_required_metrics` |
| `boundary.GUARDED_ENTRY_POINTS` 34→2 | `boundary.py:130-165` | **잡힘** | ⒝ 방출 앵커(노트 산문) |
| `boundary.READ_GUARDED_ENTRY_POINTS` 8→2 | `boundary.py:107-116` | **잡힘** | ⒝ 방출 앵커 |
| `boundary.REPO_MARKERS` 변경 (2종) | `boundary.py:124` | **잡힘** | ⒞ Case 산문 / `T-77-④` |
| `boundary.EXPECTED_RUNNER_RELPATH` 변조 | `boundary.py:125` | **잡힘** | `T-77-④` |
| `boundary.TOKEN_DEFINITION_NAMES` 확대 | `boundary.py:96-98` | **잡힘** | ⒝ 방출 앵커 |
| `T.DEFECT_WORDS` 7→() | `test_contracts.py:114-122` | **잡힘** | `SELF-1` 프로브(L2) |
| `audit_guard.READ_EVENTS` 3→1 | `audit_guard.py:78` | **잡힘** | ⒝ 방출 앵커 |
| `audit_guard.WRITE_EVENTS` 17→2 | `audit_guard.py:81-99` | **잡힘** | ⒝ 방출 앵커 |
| `audit_guard._WATCHED` →∅ / 열람만 | `audit_guard.py:103` | **잡힘** | `T-77-AUDIT` 실물 프로브 |
| `audit_guard._WRITE_EVENT_SET` →∅ | `audit_guard.py:102` | **잡힘** | `T-77-AUDIT` |
| `audit_guard._READ_ARMED/_WRITE_ARMED=False` | `audit_guard.py:111-112` | **잡힘** | `T-77-AUDIT` + ⒝ |
| `audit_guard._REENTRANT=True` | `audit_guard.py:113` | **잡힘** | `T-77-AUDIT` |
| `audit_guard._CORPUS_FOLDED`/`_REGISTER_FOLDED` | `audit_guard.py:64-65` | **잡힘** | `T-77-AUDIT`·`T-77-①-READ` |
| **`register.FIXTURE_CLAUSES` +2절** | `register.py:29` | **침묵** | — |
| **`boundary._PATH_BLOCKED` 10→2 (및 −5)** | `boundary.py:190-201` | **침묵** | — |
| **`boundary.FORBIDDEN_SOURCE_TOKENS` 3→2** | `boundary.py:73-77` | **침묵** | — |
| **`config.REQUIRED_KEYS` 20→4** | `config.py:13-35` | **침묵** | — |
| **`audit_guard._PROBE_DEPTH=1`** | `audit_guard.py:114` | **침묵** | — |
| `audit_guard._READ_EVENT_SET` →∅ | `audit_guard.py:101` | 침묵(**무해**) | 로드 후 사용처 0 — 죽은 상수 |
| `audit_guard._WRITE_MODE_CHARS` →∅ | `audit_guard.py:67` | 침묵(**무해**) | `_WRITE_FLAGS` 가 중복 방어 |
| `audit_guard._WRITE_FLAGS` →0 | `audit_guard.py:68` | 침묵(**무해**) | `_WRITE_MODE_CHARS` 가 중복 방어 |

  마지막 두 항은 **함께** 무력화하면 잡힌다(`failed=['SELF-1','T-77-AUDIT']`) — 개별 침묵은
  결함이 아니라 실측된 이중화다. 정직하게 기록한다.

  침묵 5종 중 **실제 강제 약화**로 이어지는 것은 3종이다:
  - `FIXTURE_CLAUSES` 확장 → U-9 "해석되는 인용" 우주가 조용히 넓어진다.
  - `FORBIDDEN_SOURCE_TOKENS` 축소 → 정적 소스 스캔(심층 방어)에서 register-DEV 토큰이 빠진다.
  - `_PROBE_DEPTH` 고정 → `main()` 의 헤드라인 신호(`blocked_reads`/`blocked_writes`,
    `test_contracts.py:2125-2129`)가 **영구히 "없음"** 이 된다. 차단 자체는 계속되므로
    탈출은 없지만 **증거 채널이 위조 가능**하다.

  `_PATH_BLOCKED` 는 **실제 쓰기 탈출이 아님**을 실측했다 — 목록을 완전히 비운 뒤
  5종 실물 시도:

  ```
  Path.touch         → 감사 hook 차단 (os.utime)
  Path.mkdir         → monkeypatch 차단 (os.mkdir)
  Path.write_text    → monkeypatch 차단 (builtins.open)
  Path.symlink_to    → monkeypatch 차단 (os.symlink)
  Path.hardlink_to   → monkeypatch 차단 (os.link)
  ```

  따라서 A-6 의 심각도를 **하향**한다: 남은 것은 "광고문과 실제 목록이 두 벌"이라는
  DRY/단일정본 문제이지 탈출 통로가 아니다.
- **recommendation**: 5종을 `config.yaml` 의 값 앵커로 올린다 —
  `anchor_forbidden_artifacts_digest` 가 이미 선례다(`tuple_anchor` `:410-416` 재사용).
  `_PROBE_DEPTH` 는 `probe_window()` 진입/이탈 균형을 `SELF-1` 이 관측하거나,
  프로브 창을 모듈 전역이 아니라 명시적 인자로 넘긴다.
- **confidence**: 95 (실측)

## N-4 (MEDIUM) — `T-77-AUDIT` 의 방향② 프로브가 **실물 쓰기**이며, 기제가 깨지면 러너가 repo 에 파일을 만들고 스스로 지우지 못한다

- **location**: `test_contracts.py:1091-1096` (`_io.open(쓰기 모드)`·`posix.mkdir` 프로브),
  `:1117` (`audit_leftovers` 관측), `:754-763` (`_probe_builtin_open`·`_probe_os_open`)
- **위반한 원칙**: 대조군 계층이 피검사 대상(OD-3-C: 파일 쓰기 0)을 스스로 위반 · 단일 책임
- **finding**:
  본 감사 중 `_WRITE_EVENT_SET`·`_WATCHED`·`_WRITE_ARMED`·`_REENTRANT` 를 무력화한
  뮤테이션에서 **원본 작업 트리에 실물이 생성됐다**:

  ```
  [잡힘] _WRITE_EVENT_SET →∅   !! 실물 잔존 생성됨: ['__audit_probe_dir']
  [잡힘] _WATCHED →∅           !! 실물 잔존 생성됨: ['__audit_probe_dir','__audit_probe_w.tmp']
  [잡힘] _WRITE_ARMED=False    !! 실물 잔존 생성됨: ['__audit_probe_dir','__audit_probe_w.tmp']
  [잡힘] _REENTRANT=True       !! 실물 잔존 생성됨: ['__audit_probe_dir','__audit_probe_w.tmp']
  ```

  탐지는 fail-closed 로 작동한다(`audit_leftovers` 가 방향②를 무너뜨려 `T-77-AUDIT` red).
  문제는 **회복 불가능성**이다: 러너는 자기 정책상 파일을 지울 수 없으므로 잔존물이
  남고, 그 뒤 모든 실행이 `T-77-AUDIT` red + `Case산문` 앵커 드리프트로 **영구 오염**된다
  (본 감사에서 실제로 후속 20여 회 실행이 오염돼 재실행·수동 제거가 필요했다).
  그리고 그 순간 러너 자신이 OD-3-C("실행 중 파일 쓰기 0")를 위반한다.
- **recommendation**: 쓰기 프로브의 표적을 repo 밖(`tempfile.gettempdir()`)으로 옮기거나,
  경로를 존재 불가능한 것(예: 읽기 전용 FS·부재 디렉터리 하위)으로 잡아 **성공 자체가
  불가능**하게 만든다. 관측하려는 것은 "hook 이 발화하는가"이지 "쓰기가 성공하는가"가 아니다.
- **confidence**: 95 (실측 — 사고로 재현)

## N-5 (MEDIUM) — 두 가드 계층의 **예외 계통이 통합되지 않아** 정본 계층이 막으면 대조군이 관측 대신 크래시한다

- **location**: `test_contracts.py:888-897` (`except boundary.BoundaryViolation` / `except OSError`),
  `:1107-1116` (같은 패턴, `audit_guard.AuditViolation` 만 잡음);
  `audit_guard.py:71-72` (`AuditViolation(RuntimeError)`) vs `proto/boundary.py:204-205`
  (`BoundaryViolation(RuntimeError)`) — **형제 클래스, 공통 조상 없음**
- **위반한 원칙**: 계층 간 계약 · 추상화 누수
- **finding**:
  `T-77-②` 의 프로브 루프는 `BoundaryViolation` 과 `OSError` 만 잡는다. 심층 방어
  (monkeypatch) 목록이 줄어들어 정본(감사 hook)이 대신 막으면 `AuditViolation` 이
  **잡히지 않고 전파**되어 `run_all()` 이 traceback 으로 죽는다. 실측:

  ```
  [예외] boundary._OS_BLOCKED 11→2:     AuditViolation: 파일 쓰기 차단: os.rename:…/__probe_a
  [예외] boundary._SHUTIL_BLOCKED 8→2:  AuditViolation: 파일 쓰기 차단: shutil.rmtree:…/__probe_dir
  ```

  exit code 는 비-0 이라 fail-closed 이지만 **Case 도 보고도 앵커도 남지 않는다** —
  "두 층 중 어느 쪽이 막았는지 나눠서 관측한다"(`:1065-1068` 의 설계 의도)가
  한쪽 방향에서만 성립한다. 심층 방어가 얇아질수록 러너가 관측 불능이 되는 구조다.
- **recommendation**: 공통 기반 예외(`GuardViolation`)를 두고 `AuditViolation`·
  `BoundaryViolation` 이 상속하게 한 뒤 프로브 루프가 그것을 잡는다. 어느 층이
  막았는지는 예외 타입으로 구별해 `blocked` 라벨에 실으면 관측력이 오히려 는다.
- **confidence**: 95 (실측)

## N-6 (HIGH) — 러너 자신의 **가드 이전 창**(`:73-95`)이 열려 있고, `T-77-AUDIT` 의 순서 검사가 그것을 보지 않는다

- **location**: `test_contracts.py:73-95` (import 블록·`sys.path` 조작) vs `:96`
  (`import audit_guard`); 순서 검사 `:1048-1061`
- **위반한 원칙**: 강제 창의 완전성 · 선언층/평가층 일치
- **finding**:
  `order_ok = bool(audit_lines) and bool(proto_lines) and max(audit_lines) < min(proto_lines)`
  (`:1061`)는 **`audit_guard` 가 `proto` 보다 앞인가**만 본다. `audit_guard` **앞에**
  무엇이 실행되는가는 보지 않는다. 격리 사본에서 `:90`(즉 `sys.path.insert` 직후,
  `import audit_guard` 이전)에 열람을 심었다:

  ```
  [가드 이전 밀수] 93904 bytes          ← 읽혔다
  대조군 32건 중 양방향 성립 31건
  미성립: ['SELF-1']
  산문 앵커 대조: … 소스바이트=28965ae0ee96b4f7!=63b83b185ad21abd · Case산문=3ecbf9a8f1f37f9a!=…
  ```

  **런타임 강제는 이 창을 덮지 못하고**, 잡은 것은 ⒠·⒞ 앵커뿐이다. 그리고 그 앵커
  소비 경로가 **N-1** 에서 절단 가능함이 실증됐으므로, 두 발견은 **직교하지 않고 곱해진다**.
  `L-AUDIT-PERSIST`(`:1182-1185`)가 등재한 "bootstrap 이전 창"은 **모듈 import 모드의
  `.pyc` 쓰기**에 한정되며, **스크립트 모드의 열람 창은 등재돼 있지 않다.**
- **recommendation**: `order_ok` 를 `audit_lines == [최초 실행 문장 이후 첫 import]` 로
  강화한다 — 러너 AST 의 `Module.body` 를 순회해 `import audit_guard` **앞에 오는
  실행 문장**(docstring·`from __future__`·순수 stdlib import 를 제외한 전부)을 열거하고
  비어있지 않으면 red. 또는 hook 설치를 `sitecustomize`/`-X importtime` 이전 단계로
  올리고 그 사실을 구조로 관측한다. 최소한 `L-AUDIT-PERSIST` 에 **스크립트 모드의
  `:73-95` 열람 창**을 등재해 가시화한다.
- **confidence**: 95 (실측)

## N-7 (MEDIUM) — 정책 데이터가 여전히 **코드 상수**다: `config.yaml` 20키 중 정책 목록 앵커는 2개뿐

- **location**: `proto/boundary.py:124-125` (`REPO_MARKERS`·`EXPECTED_RUNNER_RELPATH`),
  `:95` (`TOKEN_DEFINITION_SITE = "audit_guard.py"` — 교차 모듈 파일명 리터럴),
  `:130-201`, `audit_guard.py:78-99`, `proto/register.py:29`, `proto/config.py:13-35`
- **위반한 원칙**: CLAUDE.md 비협상 — "thresholds, symbols, risk values … belong in
  YAML/env/config files, not hardcoded branches" (목록형 정책도 같은 범주)
- **finding**:
  v2.6 은 `declared_required_metrics`(`config.yaml:37`)와
  `anchor_forbidden_artifacts_digest`(`:43`)로 **패턴을 세웠지만 두 상수에만 적용**했다.
  경계를 정의하는 나머지 정책 목록 — 차단 진입점 3종, 감사 이벤트 2종, repo 표지,
  예상 러너 경로, 금지 소스 토큰, 픽스처 절, 필수 설정 키 — 은 전부 코드에 남아 있다.
  `TOKEN_DEFINITION_SITE` 는 특히 `Path(audit_guard.__file__).name` 으로 **파생 가능한
  값을 리터럴로 박은** 지점이다(모듈 참조는 이미 `boundary.py:63` 에 있다).

  직전 심판이 finding #4 권고를 이행할 때 "앵커 값은 `config.yaml` 에 두어야 한다"고
  단서를 달았고 — 값 앵커 2종은 그 단서를 지켰다. 나머지가 남았다.
- **recommendation**: `tuple_anchor` 를 재사용해 `anchor_write_entry_points_digest`,
  `anchor_read_entry_points_digest`, `anchor_audit_events_digest`,
  `anchor_forbidden_tokens_digest`, `anchor_fixture_clauses_digest`,
  `anchor_required_keys_digest` 를 `config.yaml` 에 추가하고 `REQUIRED_KEYS` 에 등재한다.
  `TOKEN_DEFINITION_SITE` 는 `Path(audit_guard.__file__).name` 으로 파생시킨다.
- **confidence**: 92 (구조 실측)

## N-8 (LOW) — ⒜ 리터럴 앵커는 이제 ⒠ 의 **진부분집합**이라 단독 검출 표면이 존재할 수 없다

- **location**: `test_contracts.py:259-291` (`limit_text_anchor`), `:1897-1899`
  (`own_source = Path(__file__).read_text()` → ⒜) vs `:376-407` (⒠, 같은 파일 바이트 포함)
- **위반한 원칙**: DRY · 잉여 레이어
- **finding**:
  ⒜ 의 입력은 `Path(__file__).read_text()` 의 **순수 함수**이고, ⒠ 는 같은 파일의
  **전 바이트**를 묶는다. 따라서 ⒜ 값이 변하려면 러너의 디스크 바이트가 변해야 하고,
  그러면 ⒠ 는 **반드시** 함께 변한다 — ⒜ 가 단독으로 red 를 내는 편집은 **구조적으로
  존재하지 않는다**. 직전 A-7 은 "⒜ ⊆ ⒟ 로 관측된다(실측 27/27)"였는데, ⒠ 도입으로
  이제 포함 관계가 **증명 가능**해졌다. 실측 정합: `config.yaml:88-97` 의 ⒠ 설명은
  이 사실을 언급하지 않고 5종을 동격으로 적는다(`L-SRC-ANCHOR`, `:1935`).
- **recommendation**: ⒜ 를 폐기해 4종으로 줄이고 `declared_limit_ids`/⒝ 로 노트 규율을
  유지한다. 유지한다면 `L-SRC-ANCHOR` 와 `config.yaml:45-50` 에 "⒜ 는 ⒠ 의 부분집합이며
  진단 세분화 목적"이라고 정직하게 적는다.
- **confidence**: 90 (구조 증명 + 디스크 편집 실측)

## N-9 (LOW) — `t77_boundary` 449행 god-function · `_patch` 헬퍼 중복 · `proto` 패키지 경계 누수

- **location**: `test_contracts.py:766-1214` (449행, Case 6개 + 노트 9개 생산),
  `:1879-2018` (`self_check` 140행); `proto/boundary.py:550-554` 와 `:635-639`
  (동일 `_patch` 두 벌); `proto/boundary.py:63` (`import audit_guard`)
- **위반한 원칙**: 단일 책임 · DRY · 패키지 자족성
- **finding**:
  A-8 은 부분해소됐지만(`collect_self_checks`/`self_check_green`/`self_check_consumption`
  추출) `t77_boundary` 는 `T-77-AUDIT` 추가로 **449행**이 되어 러너 최대 함수다.
  `_patch` 는 여전히 두 벌이다(본문 동일).

  레이어 방향은 **순환 없음**이 확인됐고 `audit_guard` 를 `proto/` 밖에 두는 근거
  (`audit_guard.py:11-14`: `proto/__init__.py` 실행조차 armed 여야 한다)는 **타당하다**.
  다만 부수효과로 `proto` 가 자족적 패키지가 아니게 됐다:

  ```
  spikes/ 를 cwd 로 `import proto.boundary` → rc=1  ModuleNotFoundError: No module named 'proto'
  phase0_contract/ 를 cwd 로               → rc=0
  ```

  `proto` 는 `phase0_contract/` 자체가 `sys.path` 에 있을 때만 import 되고, 그때
  `proto/boundary.py` 가 **상위 디렉터리의 비-패키지 모듈**을 import 한다. 폐기 예정
  스파이크 한 디렉터리 안이므로 실질 위험은 낮으나, 이 패턴을 `tos/` 본 구현으로
  옮기면 import-firewall 규율과 충돌한다.
- **recommendation**: `t77_boundary` 를 `t77_static_scan`/`t77_write`/`t77_read`/
  `t77_locate`/`t77_audit` 5개로 쪼갠다(각 Case 가 함수 1개 = ⒟ 앵커 해상도도 오른다).
  `_patch` 는 모듈 레벨 헬퍼로 올린다. 본 구현 이관 시에는 `audit_guard` 를
  `proto` **밖**이 아니라 **별도 최상위 패키지**로 승격해 상대 import 를 없앤다.
- **confidence**: 88 (실측 + 구조 판단)

---

## 부수 관측 (비물질)

- `audit_guard._READ_EVENT_SET`(`:101`)은 `:103` 에서 `_WATCHED` 를 만드는 데만 쓰이고
  `_enforce`(`:185-203`)는 참조하지 않는다 — 로드 후 **죽은 상수**. 실제 열람 판정은
  `_WATCHED` 안의 **모든** 이벤트 인자에 대해 수행되므로(초집합) 강제 손실은 0 이다.
  `_WRITE_EVENT_SET` 은 살아 있다(`:197`). 이름의 대칭이 동작의 대칭을 시사하는데
  실제로는 비대칭이라 다음 드리프트의 자리가 될 수 있다.
- 형제 스파이크 도구(`blocks_gate_consumption.py`·`sweep_deprecated_vocabulary.py`)는
  `proto`/`audit_guard` 를 import 하지 않고 금지 토큰 적중도 0 이다 — 현재 무해하며
  `L-T77-DOMAIN` 이 도메인 밖임을 등재한다. 다만 ⒠ 의 대상 목록(`:382-386`)도 같은
  열거이므로, **러너가 import 하는 새 형제 모듈이 생기면 스캔과 앵커 양쪽에서 동시에
  빠진다**. 등재는 스캔에 대해서만 돼 있다.
- `probe_window()`(`audit_guard.py:127-141`)의 docstring 이 "창을 열어 기록을 숨기는
  경로가 남지만 소스 바이트 앵커가 묶는다"고 적는데, **런타임 `_PROBE_DEPTH` 대입은
  소스를 건드리지 않는다**(N-3 표). 자기 서술이 한 칸 넓다.
- `main()`(`:2059`)이 `run_all()` 전체를 monkeypatch 가드로 감싸는 배선은 유지됐고,
  감사 hook 은 그보다 넓은 창(프로세스 전역)을 덮는다 — 이중화 자체는 건전하다.

---

## 재현 절차

```bash
# 베이스라인 (원본 무수정)
python3 tools/spikes/phase0_contract/test_contracts.py; echo "EXIT=$?"
# → EXIT=0 · 대조군 32건 중 양방향 성립 32건
#   리터럴=c8380b9cc6f85ea2 · 방출=c9eae41098208b40 · 실행코드=9bf6030332fd7604
#   소스바이트=63b83b185ad21abd · Case산문=53890d21ae213964
```

인메모리 프로브 4종(원본 무수정) — `<scratch>/probe_v26.py`(직전 침묵 4종 + 정책 데이터
전수) · `<scratch>/probe_v26b.py`(잔존물 격리 재실행 + SELF-2 배선) ·
`<scratch>/probe_layer.py`(레이어·설정·쓰기 탈출 실측) · 인라인 heredoc(항 삭제 vs 값 무력화).
디스크 편집 4종은 `<scratch>/arch-lens/repo/` 격리 사본에서만 수행했다.

**주의(재현자에게)**: `_WRITE_*`/`_WATCHED`/`_REENTRANT` 계열을 무력화하는 뮤테이션은
`tools/spikes/phase0_contract/` 에 `__audit_probe_dir`·`__audit_probe_w.tmp` 를 **실제로
남긴다**(N-4). 매 뮤테이션 뒤 제거하지 않으면 이후 모든 실행이 `T-77-AUDIT` red 로
오염된다.

## 렌즈 경계 고지

- **판정 없음.** 위 항목은 증거이며 gate 판정은 Codex 심판 레인 소관이다.
- 스타일·네이밍(style-auditor), 성능(performance-auditor), 시크릿·주입(security-auditor)
  영역은 다루지 않았다. `sys.addaudithook` 의 보안 속성(해제 불가·감사 우회)은 보안
  렌즈 소관이며 여기서는 강제 계층의 **설계**로만 평가했다.
- 설계 문서(`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`) 본문의
  정합성은 이 렌즈 대상이 아니다 — 프로토타입 코드와 `proto/config.yaml` 의 자기 서술만 대조했다.
