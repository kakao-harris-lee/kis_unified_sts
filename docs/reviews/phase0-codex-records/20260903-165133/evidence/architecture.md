# Architecture lens — codex-gate 레인 A (D0 구현 블록)

- Repo: /Users/harris/Development/private/kis_unified_sts
- HEAD: `b5d2448a` (= `faea9720` + docs/reviews 기록 커밋 1건)
- 범위: `git diff 28475ca1^ HEAD -- . ':!docs/plans' ':!docs/reviews'` — 34 파일 / +14,530 −109
- 렌즈: architecture (증거만 산출 · 판정 없음 · read-only)
- 상태: **완료** · 발견 high 1 · medium 11 · low 4 · info 1

---

## 진행 로그

- [x] 1. 레이어·의존 방향 · [x] 2. DRY · [x] 3. 설정 구동 · [x] 4. fail-closed 정합
- [x] 5. 하니스 lockstep · [x] 6. CI 구조 · [x] 7. god-object/추상화 누수
- [x] 8. 건전 확인 목록 · [x] 9. 미확인 항목 · [x] 10. 발견 요약
- **완료** (2026-09-03)

---
## 1. 레이어·의존 방향 (tools/ ↔ tos/ ↔ tos-spec/)

### 1-a. tos/src 변경이 docstring-only 인가 — **확인됨 (YES)**

7개 파일 전부 「docstring 을 제거한 AST」가 `28475ca1^` 와 `HEAD` 에서 완전 일치.
스크립트: `ast.NodeTransformer` 로 Module/ClassDef/FunctionDef 의 선두 문자열 상수를 제거한 뒤
`ast.dump(include_attributes=False)` 대조.

```
tos/src/tos/backtest/__init__.py      ast_incl_docstrings_equal=False  ast_docstrings_stripped_equal=True
tos/src/tos/backtest/resolver.py      ast_incl_docstrings_equal=False  ast_docstrings_stripped_equal=True
tos/src/tos/backtest/results.py       ast_incl_docstrings_equal=False  ast_docstrings_stripped_equal=True
tos/src/tos/egressgw/construction.py  ast_incl_docstrings_equal=False  ast_docstrings_stripped_equal=True
tos/src/tos/egressgw/records.py       ast_incl_docstrings_equal=False  ast_docstrings_stripped_equal=True
tos/src/tos/engine/__init__.py        ast_incl_docstrings_equal=False  ast_docstrings_stripped_equal=True
tos/src/tos/marketfeed/__init__.py    ast_incl_docstrings_equal=False  ast_docstrings_stripped_equal=True
EXIT=0
```

주의(정확한 표현): 「docstring-only」가 아니라 **「docstring + 순수 포매팅 only」**다. 코드 토큰이
아니라 코드 **레이아웃**이 두 자리 바뀐다 — `tos/src/tos/backtest/resolver.py:44-48`
(`__all__` 리스트를 한 줄 → 여러 줄로 재배치), `tos/src/tos/backtest/resolver.py:183-185`
(`UncertaintyInterval(...)` 호출 줄바꿈). 둘 다 AST 동치라 런타임 의미 무변경이라는 주장은
성립한다. 「코드 토큰 변화 0」이라는 더 강한 문언은 성립하지 않는다(`__all__` 원소 순서·개수는
동일하나 소스 토큰 배열은 달라짐 — black 재포맷 흔적).
심각도 없음 · 정보 항목.

### 1-b. import-firewall — **위반 없음**

- Layer 1 (AST default-deny): `python tools/tos_firewall_check.py` → `tos-firewall: PASS — no import-firewall violations` (rc 0).
- Layer 2 설정 `.importlinter` 는 이 diff 에서 **무변경** (`git diff --name-only` 에 부재).
  금지 집합(`shared.execution`/`kis`/`streaming`/`llm`/`storage`/`backtest`/`config.secrets`/`services`/`cli`) 불변.
- 방향 실측: `grep -rnE '^\s*(from|import)\s+tools' tos/src shared services cli` → **0 히트**
  (하위 계층이 `tools/` 를 역참조하지 않음).
  `grep -nE '^\s*(from|import)\s+(tos|shared|services|cli)\b'` 를 변경된 5개 tools 파일에 →
  **0 히트** (검사기가 검사 대상 런타임을 import 하지 않음 — 구조 파생을 소스 텍스트/AST 로만
  수행한다는 설계와 정합).

### 1-c. `tools/` 내부 import 규약이 두 벌 — **low**

- `tools/tos_spec_status.py:29` · `tools/tos_evidence_run.py:146`
  → `from tools.tos_profile_census import _profile_null_key_census` (패키지 경로 형식)
- `tools/tos_contract_index.py:47`
  → `import tos_contract_check as tcc  # noqa: E402` (sys.path 조작 뒤 bare 모듈 형식)

같은 디렉터리의 형제 모듈을 두 가지 규약으로 참조한다. 실행 진입점(`python tools/X.py` vs
`python -m tools.X`)에 따라 하나가 깨질 수 있는 구조. 아래 §2 에서 실행 실측으로 확인.

---
## 2. DRY — 파생 로직 중복 저작

계약 §6.3.2 는 「파생 로직 두 벌 저작 0」을 종료조건으로 둔다.

### 2-a. **성공한 추출** — profile null-key census (건전)

`tools/tos_profile_census.py`(101행, 신규)가 `profile_key_universe` / `_profile_null_key_census`
를 단 한 번 저작하고, 세 소비자가 전부 그것을 호출한다. 재저작 사본 0.

```
tools/tos_evidence_run.py:146     from tools.tos_profile_census import _profile_null_key_census
tools/tos_spec_status.py:29       from tools.tos_profile_census import _profile_null_key_census
tools/tos_completion_status.py:3663  census_module.profile_key_universe(doc)   (importlib 부트스트랩)
```

`grep -n 'bounds' tools/tos_spec_status.py tools/tos_evidence_run.py` 에 자체 bounds/limits 워크
잔존 없음 — 실제로 한 벌이다. **이 항목은 건전.**

### 2-b. **REGISTER CSV 헤더 스키마가 두 벌 저작** — medium

같은 정본 파일(`EVIDENCE-REGISTER-002.csv` · `EVIDENCE-REGISTER-DEV.csv`)의 16-필드 헤더가
두 검사기에 각각 독립 리터럴로 저작돼 있다.

- `tools/tos_completion_status.py:106-123` — `REGISTER_FIELDS`
- `tools/tos_spec_status.py:89-106` — `REQUIRED_EVIDENCE_FIELDS`

실측(원소 추출 후 튜플 비교):

```
completion_status.REGISTER_FIELDS n= 16
spec_status.REQUIRED_EVIDENCE_FIELDS n= 16
IDENTICAL: True
```

지금은 일치하지만 **드리프트를 잡는 장치가 없다.** `grep -rn 'REGISTER_FIELDS|REQUIRED_EVIDENCE_FIELDS' tests/tools/`
결과는 각 테스트가 **자기 모듈의 상수만** 참조한다(테스트 파일 두 벌 모두 상대편 상수를 언급조차
하지 않음):

```
tests/tools/test_tos_spec_status.py:33,54     status.REQUIRED_EVIDENCE_FIELDS
tests/tools/test_tos_completion_status.py:743,744,4187,4204  tcs.REGISTER_FIELDS
```

즉 한쪽만 컬럼을 추가하면 **두 스위트 전부 green 인 채로** 두 검사기가 같은 CSV 의 스키마에
대해 상반된 판정을 내는 상태가 성립한다(한쪽은 헤더 불일치로 fail-closed, 다른 쪽은 통과).
계약이 §6.3.2 에서 금지한 「두 벌 저작」의 교과서 사례이며, census 추출(2-a)이 정확히 이 문제를
푼 방식이 여기엔 적용되지 않았다.
권고: 헤더 튜플을 `tools/tos_profile_census.py` 급의 공유 모듈로 올리거나, 최소한 두 상수가
같음을 단언하는 lockstep 테스트를 추가.

**severity 를 high 가 아니라 medium 으로 적는 이유(정직하게)**: 두 상수는 **현재 일치**하며
지금 잘못된 판정을 내는 것은 없다. 위험은 미래의 편집에 조건부다. 또 §6.3.2 의 문언은
「**파생 로직** 두 벌 저작 0」이고 이것은 로직이 아니라 스키마 상수다 — 계약 문언의 직접
위반이라고 주장하지 않는다.

### 2-c. **register CSV 리더가 세 벌 저작 · fail-closed 강도가 서로 다름** — medium

같은 CSV 를 읽는 리더가 세 개, 전부 독립 저작이고 **행동이 다르다**:

| 사이트 | 헤더 검증 | 값 strip | 잡는 예외 |
| --- | --- | --- | --- |
| `tools/tos_completion_status.py:257` `_load_csv_rows` | 튜플 일치 강제 | **안 함** | `OSError`, `csv.Error` |
| `tools/tos_spec_status.py:354` `_read_csv` | 튜플 일치 강제 | **함** (`(value or "").strip()`) | `FileNotFoundError` 만 |
| `tools/tos_evidence_run.py:1449` `read_register_row` | **없음** | 안 함 | 없음(`is_file()` 선검사만) |

**이 비대칭이 오늘 실제로 판정을 가르는가 — 실측했다. 가르지 않는다.**

```
EVIDENCE-REGISTER-002.csv            rows=  372 whitespace-padded cells=0
EVIDENCE-REGISTER-DEV.csv            rows=  118 whitespace-padded cells=0
PHASE0-UNCHECKABLE-REGISTER.csv      rows=   24 whitespace-padded cells=0
EVIDENCE-REQUIRED-KINDS.csv          rows=  487 whitespace-padded cells=0
EVIDENCE-SURFACE-MAP.csv             rows= 2023 whitespace-padded cells=0
```

5개 정본 CSV 전부에 공백 패딩 셀이 **0** 이므로 strip 유무는 **현재 동치**다.
발견은 «잠재»이며 «현행 오판정»이 아니다 — 그렇게 적는다.
다만 패딩이 한 셀이라도 들어오면 같은 셀을 읽고도 한쪽은 `" PASS "` 를 `PASS` 로,
다른 쪽은 `" PASS "` 로 본다. 어휘 집합 대조가
두 검사기의 핵심 술어(`status not in _AUTHORITY_STATES` 등)이므로 이 비대칭은 판정 차이로
직결될 수 있다. `_read_csv` 가 `csv.Error`·일반 `OSError` 를 잡지 않는 것은 fail-closed 방향
(예외 전파)이라 안전하지만, 세 리더의 처분 방향이 다르다는 사실 자체가 구조 결함.

### 2-d. **어휘 상수 사본 2쌍** — medium (저작자가 등재는 함)

- `tools/tos_completion_status.py:3012` `_AUTHORITY_STATES` ↔ `tools/tos_spec_status.py:45` `AUTHORITY_STATES`
- `tools/tos_completion_status.py:3016-3026` `_EVIDENCE_STATUS_VOCAB` ↔ `tools/tos_spec_status.py:31-42` `EVIDENCE_STATES`

실측: 두 쌍 모두 현재 **집합 동일**(각 10원소 / 2원소, `IDENTICAL: True`).
저작자가 `tools/tos_completion_status.py:3010-3011` 과 `:3015` 에 사본임을 명시 주석으로
등재했다(정직한 등재 — 은닉 아님). 그러나 2-b 와 같은 이유로 **동기화를 강제하는 테스트가
없다**: `grep -rn '_EVIDENCE_STATUS_VOCAB|EVIDENCE_STATES' tests/tools/` → 0 히트.
사본이 «정직하게 등재된 사본»인 것과 «드리프트가 시끄럽게 실패하는 사본»인 것은 다르다.

### 2-e. **공유 모듈을 세 가지 방식으로 로드** — medium

같은 `tools/tos_profile_census.py` 를 세 소비자가 세 규약으로 가져온다:

1. `from tools.tos_profile_census import _profile_null_key_census` (spec_status:29, evidence_run:146)
   — PEP-420 네임스페이스 패키지에 의존. `tools/__init__.py` 는 **없다**(`ls tools/__init__.py` → No such file).
   실측: `.venv/bin/python -c "import tools; print(tools.__path__)"` →
   `_NamespacePath(['/Users/harris/.../tools', ...])` — 리포 루트가 editable 설치(`.pth`)로
   `sys.path` 에 있어서 해결된다. CI 도 `pip install -e . --no-deps`(tos-firewall.yml:56) 를 하므로 성립.
2. `importlib.util.spec_from_file_location` 부트스트랩 (completion_status:3620-3641) — 실행
   컨텍스트 무관. 저작자가 :3623-3629 에서 1번 방식이 editable 설치 없는 인터프리터에서
   깨진다는 이유를 명시한다.
3. `sys.path.insert(0, Path(__file__).parent)` 후 bare import (contract_index:46-47).

**저작자 자신의 근거가 1번을 반증한다.** completion_status 의 주석이 「editable 설치하지 않은
인터프리터에서는 `from tools.X` 가 깨진다」고 정확히 진단해 놓고, 같은 커밋의 spec_status:29 와
evidence_run:146 은 그 깨지는 형태를 쓴다. 실측으로 지금 CI 는 통과하지만, 이는 우연이 아니라
`pip install -e .` 스텝에 의존하는 것이다 — 그 스텝이 없는 실행 경로(운영자 로컬 clean venv,
`uv run`, docker 최소 이미지)에서 spec_status 만 `ModuleNotFoundError` 로 죽는다.
또 하나: 1번은 **private 이름**(`_profile_null_key_census`)을 모듈 경계 너머로 가져오고,
2번은 public 이름(`profile_key_universe`)을 쓴다 — 공유 표면의 공개 경계가 정의돼 있지 않음.
권고: 로드 규약 하나로 통일(2번이 가장 견고), 공유 API 는 `_` 없는 이름으로.

또한 `_load_tos_profile_census_module` 은 `@cache`(:3620) 라 프로세스당 1회 로드 — 반복 호출
비용 문제는 없음(성능 렌즈 소관, 여기서는 구조만 기록).

---
## 3. 설정 구동 (U-14 정본 A/B)

계약 §12.1.2 (`--locate U-14` → `sed -n '4463,4548p' docs/plans/2026-08-12-...design.md`):
정본 A = `config/tos_completion.yaml` 의 앵커 · 정본 B = 검사기가 구조에서 재파생한 값 ·
「문서의 표는 리뷰 사본이며 검사기는 읽지 않는다」. §13.6.4 U-1a: 「임계값 3종의 유일 런타임
소스는 이 파일이다 — 문서도 검사기도 리터럴로 갖지 않는다」.

### 3-a. 앵커의 리터럴 중복 — **없음 (건전)**

```
grep -rn 'EV-L1=81' tools/ tos-spec/src/ config/ tests/
  → config/tos_completion.yaml:49  (유일 히트)
grep -rn 'UNCHK-014' tools/*.py
  → (0 히트)
```

T-76 레벨 분포 26쌍·U-9a closable=NO 집합 모두 config 밖에 사본이 없다. 대조는
`tools/tos_completion_status.py:1105-1141` 에서 register CSV / UNCHECKABLE CSV 재파생값과
집합 비교로 수행된다. **U-14 의 뒤집기가 실제로 구현돼 있다.**

### 3-b. T-71 앵커의 정본 B 는 코드 상수 — 계약이 명시한 약한 축 (정보)

`tools/tos_completion_status.py:1148-1177` — T-71 의 «관측값»은 데이터가 아니라 같은 파일의
`GATE_PREDICATES` 상수에서 `Counter(p.classification ...)` 로 나온다. 즉 사본 대 사본.
저작자가 :1144-1147 주석에 그 사실을 명시했고, 계약 §12.1.2 표가 이 앵커를 **ATTESTED**
(다른 둘은 SUBSTANTIVE)로 강도 하향해 등재한다. **은닉 아님 — 계약과 구현이 일치.**

### 3-c. 임계값 3종 — config 만이 소스 (건전, 단 fallback 리터럴 잔존)

`owner_track_range_max_width` / `phase_min` / `phase_max` 는 `_owner_track_report`
(`tools/tos_completion_status.py:2916-2918`)에서만 읽히고 `_validate_owner_track_value`
(`:2883-2903`)에 인자로 주입된다 — 술어에 리터럴 상한이 없다.

다만 `tools/tos_completion_status.py:2927-2929`:

```python
width: int = raw_width if isinstance(raw_width, int) else 0
phase_min: int = raw_phase_min if isinstance(raw_phase_min, int) else 0
phase_max: int = raw_phase_max if isinstance(raw_phase_max, int) else 0
```

이 `else 0` 세 자리는 **소비 시점에 도달 불가**다(소비는 `elif config_valid:` — `:2950` —
안에서만 일어나고 `config_valid` 는 세 값이 전부 `int` 일 때만 참). 즉 fail-open 은 아니다.
그러나 「기본값 0」이라는 형태는 U-1a 의 "리터럴 없음" 문언과 시각적으로 충돌하고, 술어를
가드 밖으로 한 번만 옮기면 즉시 fail-open 이 되는 배치다(`phase_min=0, phase_max=0, width=0`
→ 모든 range 거부·모든 Phase 거부, 방향은 보수적이나 «검사가 죽은» 상태).
severity **low** · 권고: `config_valid` 가 거짓이면 세 변수를 만들지 말고 조기 반환.

### 3-d. 테스트 픽스처가 config 값을 리터럴 복제 — low

`tests/tools/test_tos_completion_status.py:596-598` 이 `owner_track_range_max_width: 3`,
`phase_min: 0`, `phase_max: 7` 을 합성 코퍼스에 리터럴로 쓴다 — 실 `config/tos_completion.yaml:19-21`
과 같은 값의 두 번째 저작.

계약 U-14-b 는 「폭·범위 음성 대조군(T-62)의 입력은 config 에서 파생한다」고 규정하고, 그
근거로 v2.0 이 `Phase 2-5` 로 겪은 결함(상한이 바뀌면 음성 입력이 유효 입력이 됨)을 든다.
현재 테스트(`:2050-2065`)는 `"Phase 0-7"`·`"Phase 5-2"` 등을 **리터럴 음성 입력**으로 쓴다.

**다만 이것을 위반으로 적지 않는다**: 같은 테스트가 config 도 함께 합성(:596-598)하므로 쌍이
자기 정합적이고, 실 config 의 상한이 바뀌어도 이 테스트의 음성성은 깨지지 않는다 —
U-14-b 가 막으려던 사건(음성 테스트가 유효 입력을 쓰게 됨)은 발생하지 않는다.
남는 것은 **커버리지 공백**이다: 실 `config/tos_completion.yaml` 값 하에서의 음성 대조군은
어디에서도 실행되지 않는다. 실 리포에 대해 도는 테스트는 `:2040`
(`tcs.build_context(_REPO_ROOT)`) 뿐이고 그것은 owner_track 문법 음성 축을 돌지 않는다.
severity **low** · 권고: 픽스처 config 를 실 config 에서 로드하거나, 실 config 값으로
`_validate_owner_track_value` 를 직접 도는 대조군 1건 추가.

---
## 4. fail-closed 설계 정합

### 4-a. 네 상태 기계 — **중립값 없음 · 어휘 크기 계약 일치 (건전)**

AST 로 각 파생 함수의 `return (state, ...)` 리터럴을 전수 열거:

| 기계 | 선언 값 수 | 실제 distinct | 통과값 |
| --- | --- | --- | --- |
| `oq11_raise_state` (`:1485`) | 7 | 7 | `NOT_REQUIRED` 만 (`:1583-1589`) |
| `d0a_entry_state` (`:1875`) | 9 | 9 | `ENTRY_OK` 만 (`:2223`) |
| `d0a_entry_provenance_state` (`:2147`) | 8 | 8 | `ENTRY_PROVENANCE_CLEAR` + `NOT_STARTED` (`:2230`) |
| `closable_no_provenance_state` (`:2846`) | 12 | — (`_U16_RANK` 순서표) | `NO_ROWS_CLEAR` 만 (`:2870`) |

세 기계 모두 **미예기 예외를 통과값이 아닌 차단 상태로 접는다**:
`:1870-1872` → `HARNESS_ABORTED`, `:2857-2860` → `PROVENANCE_UNVERIFIABLE`.
`except Exception` 세 자리 전부 fail-closed 방향이고 `# noqa: BLE001` 로 의도 등재됨.
config 부재도 통과가 아니다 — `_load_yaml_config` (`:237-239`) 가
`Finding("U-14", "config 부재(fail-closed)")` 를 낸다.

`.get(k, <기본값>)` 전수 검사(AST) 결과 **부재를 통과값으로 접는 자리는 없다**:
`:3284-3285`/`:3340`/`:3361-3362` 의 `row.get("status","")` → `""` 는 어휘 밖 →
`NOT_AUTHORIZED`(차단). `:3940`/`:3953` 의 `.get(gate,"NOT_MET")` → 부재는 `NOT_MET`(차단).

예외 삼킴(`except: continue`) 7자리 — `tools/tos_completion_status.py:756,887,924`,
`tools/tos_spec_status.py:1728,1763,1784`, `tools/tos_contract_index.py:618` — 는 전부
`ValueError`/`UnicodeDecodeError`/`OSError` 의 좁은 포획이며 한 행/한 파일 스킵이다.
**bare `except:` 는 0.**

### 4-b. ⚠ **D-1(D0-5) 처분 파생이 산문 자기신고다 — 7사이트 전부가 이 diff 에서 UNDECIDED → UNBOUND 로 뒤집혔다** — high · in-range

`_derive_d1_disposition` (`tools/tos_completion_status.py:3668-3682`) 의 평가 순서:

```python
if _D1_UNBOUND_RE.search(flat):            # ① 영문 산문 정규식
    return "UNBOUND", "docstring 에 UNBOUND 선언 문언 존재"
if universe is not None:                   # ② 프로파일 키 실재/null 대조
    for candidate in _D1_BACKTICK_RE.findall(docstring): ...
return "UNDECIDED", "키 미공급(잔여)"
```

`_D1_UNBOUND_RE` (`:3591-3595`) 는 `not a profile key` / `no VERIFICATION-PROFILE-002 bound`
류의 **영어 문장**을 찾는다. ①이 ②를 단락(short-circuit)시킨다.

**실측 1 — HEAD 라이브 실행 (`python tools/tos_completion_status.py --check`):**

```
D0-5[backtest__init__]=UNBOUND (docstring 에 UNBOUND 선언 문언 존재)
D0-5[resolver]=UNBOUND        (docstring 에 UNBOUND 선언 문언 존재)
D0-5[results]=UNBOUND         (docstring 에 UNBOUND 선언 문언 존재)
D0-5[construction]=UNBOUND    (docstring 에 UNBOUND 선언 문언 존재)
D0-5[records]=UNBOUND         (docstring 에 UNBOUND 선언 문언 존재)
D0-5[engine]=UNBOUND          (docstring 에 UNBOUND 선언 문언 존재)
D0-5[marketfeed]=UNBOUND      (docstring 에 UNBOUND 선언 문언 존재)
RESULT: GREEN (violations=0)
```

**7/7 이 근거 ① 로 판정된다. 즉 ②(프로파일 키 대조)는 HEAD 에서 단 한 사이트도 도달하지 않는다.**

**실측 2 — 범위 내 전이(같은 검사기로 옛 docstring 을 재평가):**

```
site               28475ca1^    HEAD
backtest__init__   UNDECIDED    UNBOUND   <== FLIPPED
resolver           UNDECIDED    UNBOUND   <== FLIPPED
results            UNDECIDED    UNBOUND   <== FLIPPED
construction       UNDECIDED    UNBOUND   <== FLIPPED
records            UNDECIDED    UNBOUND   <== FLIPPED
engine             UNDECIDED    UNBOUND   <== FLIPPED
marketfeed         UNDECIDED    UNBOUND   <== FLIPPED
```

계약 §7.4(v1.6/v1.8)는 **`UNDECIDED` 가 D0-5 완료를 차단**한다고 규정한다. 이 diff 는
7사이트를 전부 해소했고, **해소의 유일한 기계적 원인은 docstring 에 추가된 영문 문장**이다
(§1-a 실측: 코드 AST 불변).

**실측 3 — 뮤테이션 대조군 (`_derive_d1_disposition` 직접 호출):**

| 대조군 | 결과 |
| --- | --- |
| HEAD `BarTimeProjection` docstring 원본 | `UNBOUND` |
| 인용된 프로파일 키 **6개 전부를 날조 키로 치환** | `UNBOUND` (무변화) |
| 문자열 `"this value is not a profile key"` **한 줄 · 키 0개** | `UNBOUND` |
| UNBOUND 산문만 무력화 · 실제 키 유지 | `VALUED` (`MAX_future_timestamp_tolerance_ms`) |
| UNBOUND 산문 무력화 + 키 날조 | `UNDECIDED` |

②축 자체는 살아 있다(4·5행이 증명). 그러나 ①이 있는 한 **결코 실행되지 않는다.**

**결과적으로 검증되지 않는 실질 주장.** `resolver.py:58-64` docstring 은
`future_tolerance` 가 `MAX_future_timestamp_tolerance_ms` 에, `maximum_consumer_age_ms` 가
`MAX_critical_input_consumer_receipt_age_ms` 에 **1:1 결속**한다고 단언한다. 두 키는 실제로
프로파일에 있고 non-null 이다(독립 실측: 우주 163키 · null 16 · valued 147 · 두 키 모두
`in_universe=True is_null=False`) — 즉 **주장은 참이다.** 그러나 **검사기는 그것을 확인하지
않았다.** 날조 키를 써도 같은 green 이 나온다(대조군 2행).

**왜 이것이 계약 위반인가.** §7.4 v1.4 교정문:
「저작자는 **의존 키만 공급**하고, **처분은 검사기가 파생**한다. **저작자가 처분을 고르면 그
자체가 자기신고**이며, UNDECIDED 가 미착수의 은신처가 된다.」
현 구현에서 저작자는 문장 하나로 처분을 **고른다**. §7.4 가 세 번의 심판 끝에 닫으려 한
바로 그 경로가 열려 있다.

**공정한 반론(기록한다).** 계약의 `UNBOUND` 정의 자체가 「문언 유지 + "이 값은 VER-002
프로파일 키가 아니다" **명시**」이므로, 검사기는 계약의 **문자**에는 부합한다. 또한 코드
주석(`:3585-3590`)이 UNBOUND 우선 순위를 의도로 명시하며, 그 좁은 근거(engine 이
`MAX_dsl_evaluation_ms` 를 **대조용으로만** 인용)는 타당하다. 발견의 요지는 「저작자가
규칙을 어겼다」가 아니라 **「이 규칙은 부정(否定) 주장을 기계로 확인할 수 없고, 그래서
D0-5 의 유일한 살아 있는 입력이 저작자 산문이 됐다」**는 구조적 사실이다.

**권고**: ①과 ②를 순서가 아니라 **양쪽 다** 평가한다 — UNBOUND 산문이 있어도 docstring 이
인용한 backtick 식별자 중 프로파일 우주에 속하는 것이 있으면 그 사이트를 `MIXED`(또는
필드 단위 처분)로 노출하고, 인용된 `MAX_*`/`MIN_*` 형태 식별자가 **우주에 없으면** 날조로
red 를 낸다. 최소 조치로는 「UNBOUND 선언 사이트가 인용한 profile-key 형태 리터럴은 전부
우주 소속이어야 한다」는 부수 불변식 하나만 추가해도 대조군 2행이 red 로 뒤집힌다.

### 4-c. 처분 단위(사이트) ↔ 근거 단위(필드) 불일치 — medium · in-range

계약 §7.4 는 「각 docstring 사이트마다 **정확히 하나**의 처분」을 요구한다. 그런데 이 diff 가
`BarTimeProjection` docstring 에 넣은 분석은 **필드 단위**다 — 9필드가 세 처분으로 갈린다:
2필드 1:1 결속(VALUED 성격) · `delay_bounds` 4키 합성 결속 · `max_age_bound` UNBOUND ·
5필드 구조적 비지배. 사이트 단위 어휘로는 이 상태를 표현할 수 없어 `UNBOUND` 하나로
접힌다(§4-b 실측 1). 계약의 처분 단위가 구현이 실제로 추론하는 단위보다 굵다.
`max_age_bound` 의 잔여는 UNCHK-024 로 등재돼 있으므로 **은닉은 아니다.**
권고: D-1 어휘를 필드 단위로 내리거나, 사이트 처분에 「구성 필드 처분 집합」을 부수 관측으로
인쇄해 접힘을 가시화.

### 4-d. U-1a 문법 축이 config 불량 시 조용히 침묵 — medium

`_owner_track_report` (`tools/tos_completion_status.py:2912-2914`):

```python
if ctx.uncheckable_rows is None or ctx.config is None:
    ctx._owner_track_cache = result      # 빈 결과
    return result
```

및 `:2950` `elif config_valid:` — config 의 세 임계값 중 하나라도 타입이 틀리면 owner_track
**문법 판정 전체가 실행되지 않고**, `_owner_track_report` 는 Finding 0 을 낸다.
전역적으로는 fail-closed 다(같은 config 결함을 `check_u14` `:1180-1191` 이 잡는다).
그러나 **U-1a 렌즈 자체는 「죽은 검사」가 된다** — U-1a 가 green 인데 문법은 한 행도
검사되지 않은 상태가 성립하고, 출력에는 그 사실이 나타나지 않는다(관측 라인
`imprecise_owner_track=0` / `unassigned_owner_rows=0` 이 «위반 없음»과 구별 불가).
addendum-5 A-F5(「(4) 열거 7==7」이 세 자리 중 둘만 보고 green)와 같은 결함 클래스.
권고: config 불량 시 `Finding("U-1a", "config 불량으로 문법 축 미실행")` 를 함께 낸다.

### 4-e. 역방향 census 폴백의 fail-open 판단 (`faea9720`) — medium · **요청된 명시 판정**

`tools/tos_spec_status.py:1697-1731` `_reverse_scan_git_universe` 는 git 실패 시
**조용히 `None`** 을 반환하고(`FileNotFoundError`/`OSError` → `None`, `returncode != 0` → `None`),
`_iter_reverse_scan_sources` (`:1755-1756`)는 `.gitignore` 를 모르는 `os.walk` 로 내려간다.

**판정: 두 소비자 중 하나에 대해 폴백은 fail-open 이다.**

`_iter_reverse_scan_sources` 소비자는 둘이다:

1. `scan_broker_construction_sites` (`:1804`) — 사이트를 **센다**. 무시된 파일이 섞이면
   개수가 늘어 앵커(`broker_sites=9`)와 불일치 → **red**. 방향은 fail-closed(로컬에서 실제로
   그렇게 터졌고 `faea9720` 커밋 메시지가 그 관측을 기록한다).
2. `scan_broker_symbol_definitions` (`:1832`) → `validate_broker_symbols_are_grounded`
   (`:1841-1877`) — 심볼이 **아무 파일에서나** class 로 정의되면 «grounded» 로 통과한다.
   무시된 파일이 섞이면 **더 많은 심볼이 근거를 얻는다** → **fail-open**.

그 함수의 docstring 자신이 이렇게 쓴다: 「a symbol defined **only under a test or under**
`tos/` **fails**, because the anchor tree is deliberately the same tree the census scans …
a decoy symbol that exists nowhere in the repo satisfies all of them and the blocking tier
then enforces a rule about a class that does not exist -- reporting a confident green.」
**gitignore 된 벤더 체크아웃은 이 배제 목록에 없다.** `open-trading-api/` 는 496MB·19k 파일의
KIS SDK 사본(`.gitignore:57-60`)이고, 거기서 정의된 클래스가 decoy 앵커를 근거지을 수 있다.

따라서 `faea9720` 는 **주 경로의 fail-open 을 정확히 닫은 옳은 수정**이다 — 계약 §2:728
기준선 행(`| open-trading-api/ | 미추적 | git ls-files 0건 | 일치 |`)이 이미 `git ls-files` 를
측정자로 삼고 있으므로 census 우주를 같은 측정자에 맞춘 것은 정합적이다.
**남는 결함은 폴백이 조용하다는 것**이다:

- 어느 우주가 쓰였는지 **출력 어디에도 나오지 않는다** (`grep -n 'git_universe' tools/tos_spec_status.py`
  → `:1697,1755,1756,1758` 뿐 · 관측/상태 라인 방출 0).
- 따라서 같은 명령이 두 개의 서로 다른 census 우주로 돌 수 있고, 산출물 형태는 동일하다.
- 폴백이 실제로 도는 조건은 「git work tree 아님 / git 부재 / rc≠0」이며, 테스트의 tmp 가짜
  리포가 여기 해당한다(커밋 메시지가 그렇게 설명). CI 는 git 경로를 탄다.

권고: 폴백 진입 시 관측 라인(`reverse_scan_universe=os_walk_fallback`)을 반드시 인쇄하고,
`--check` 처럼 판정을 내는 모드에서는 폴백을 **차단**(`StatusError`)으로 처분한다 —
합성 코퍼스 테스트만 폴백을 허용하면 된다.

부수(비회귀): `:1765-1771` 의 `except (UnicodeDecodeError, OSError): continue` 는 index 에는
있으나 워크트리에서 읽히지 않는 파일을 조용히 census 에서 뺀다. 저작자가 주석으로 의도를
등재했고 os.walk 경로에도 같은 삼킴이 원래 있었다(`:1784`) — **신규 결함 아님.**

---
## 5. 하니스 lockstep 구조

### 5-a. sha 핀은 **4자리 수동 동기화** — medium

`tools/tos_entry_harness.sh` 의 sha256 은 네 곳에 **리터럴로** 박혀 있고, 어느 것도 파일에서
파생되지 않는다:

```
shasum -a 256 tools/tos_entry_harness.sh
  059e13f22397d53c53211895cc321fef81ab7925135b196e27315e813d723177

.github/workflows/tos-gate.yml:17     059e13f2…   (shasum -c — 유일한 «실측 대조» 자리)
tools/wfcanon-v222.py:93   SHA =      059e13f2…
tools/u17-verify.sh:75     LIT2=      059e13f2…
docs/plans/2026-08-12-…design.md:7873 059e13f2…  (정본 블록)
```

전부 현재 일치함을 실측 확인. 이 diff 는 넷 중 셋을 손으로 고쳤다
(`tos-gate.yml`, `wfcanon-v222.py`, `u17-verify.sh` 각 1줄 · 정본 블록은 별도 커밋).
드리프트 위험은 이론이 아니다 — 프로젝트 기록상 이 아크는 `1817c9ef → 059e13f2` 재핀
이전에 tos-gate 가 8연속 실패했다.
권고: 파생 가능한 자리(`wfcanon`·`u17-verify`)는 실행 시점에 `shasum` 으로 재계산해
대조하거나, 최소한 네 자리가 서로 같음을 강제하는 검사 1건 추가.

### 5-b. ⚠ `u17-verify.sh` 의 `LIT1`/`LIT2` 는 **읽히지 않는 죽은 리터럴** — medium · in-range

```
grep -n 'LIT1\|LIT2' tools/u17-verify.sh
  74:LIT1=tools/tos_entry_harness.sh                     # 계약 리터럴 (R2-i)
  75:LIT2=059e13f22397…                                  # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
count LIT2: 1   count LIT1: 1
```

대조군(같은 파일의 살아 있는 리터럴): `GATE_JOB` 2회 · `WF_PATH` 12회 · `CANON` 11회.
**`LIT1`·`LIT2` 는 할당 1회 · 참조 0회.** 즉 R2-i/R2-ii 로 라벨된 두 «계약 핀»은 이 실행기
안에서 아무것도 핀하지 못한다 — 어떤 값을 넣어도 판정이 바뀌지 않는다.

실질 강제는 `wfcanon-v222.py:93` 의 `SHA` 로 이관돼 있다(`CANON_B` 를 그 리터럴로 조립해
`:456` `canon_step(s1, STEP_VER, CANON_B, …)` 에서 워크플로 스텝 본문과 byte 대조).
따라서 **검사 자체가 빠진 것은 아니고, `LIT1/LIT2` 는 이관 후 남은 잔재**다.

**그러나 이 diff 는 그 죽은 리터럴을 «갱신»했다**(`u17-verify.sh:75`, `1817c9ef→059e13f2`).
핀을 고쳤다고 읽히지만 기계적으로는 무동작이다. 다음 재핀 때 여기만 고치고 `wfcanon` 을
빠뜨리면 그 사실이 조용히 지나간다.
권고: `LIT1`/`LIT2` 삭제(강제는 wfcanon 소관임을 주석으로 명시), 또는 실제로 소비.

### 5-c. 하니스(bash) ↔ 검사기(Python) 이중 저작 — **lockstep 통제가 실재함 (건전)**

`tools/tos_completion_status.py:1861` 이 스스로 밝히듯 `_derive_d0a_entry_state_inner` 는
「`tools/tos_entry_harness.sh` R-0~R-7 의 **Python 복제**」다 — 같은 8단 상태 기계의 두 벌 저작.
이것만 보면 §2 의 DRY 결함과 같은 클래스지만, **여기에는 대조군이 있다**:

- `tests/tools/test_tos_completion_status.py:218-236` `_harness_entry_state` /
  `_assert_harness_parity` — 실제 `bash tools/tos_entry_harness.sh` 를 돌려 stdout 의
  `d0a_entry_state=` 를 파싱해 Python 파생값과 대조.
- 파생 상태별 커버리지(파서로 계수): `APPROVAL_ABSENT` 1 · `APPROVAL_NOT_APPROVE` 2 ·
  `APPROVAL_PROVENANCE_UNVERIFIABLE` 1 · `APPROVAL_SCOPE_MISMATCH` 1 · `APPROVAL_STALE` 1 ·
  `FREEZE_VIOLATED` 1 · `HARNESS_ABORTED` 1 · `REBINDING_REQUIRED` 2 = **8상태**.
  나머지 `ENTRY_OK` 는 실코퍼스 패리티 테스트(`:2169-2185`)가 rc·값 둘 다 대조.
  → **9값 전부가 두 구현 사이에서 결속돼 있다.** 이중 저작이되 «사이좋게 틀릴» 수 없다.

### 5-d. 하니스 본문 변경의 성격 (정보)

`tools/tos_entry_harness.sh:22-40` — `awk` 의 조기 `exit` 를 `done` 플래그로 교체.
근거가 주석에 실측으로 등재됨: 조기 exit → 상류 `printf` 에 EPIPE → `-o pipefail` 이 141 을
올려 `HARNESS_ABORTED` 오발화, macOS 에서는 재현 안 됨(「환경이 판정을 가른다」).
**판정 하니스에서 플랫폼 의존 판정을 제거한 수정** — 구조적으로 옳은 방향.
동작 동치(«첫 키만») 보존 주장은 `yaml_scalar` 의 `!done &&` 가드와 `yaml_list` 의
`done { next }` 로 성립한다.

---

## 6. CI 구조

### 6-a. tos-firewall Layer 4 를 «스텝»으로 둔 결정 — **근거 명시 · 타당**

`.github/workflows/tos-firewall.yml:96-101` 주석: 별도 잡이면 브랜치 보호의 필수 체크
«이름»이 하나 늘고 그 설정 표면이 이 아크의 통증이었다. 이 워크플로는 경로 게이팅 없이
모든 PR·main push 에서 돌므로(`:14-18` `on: push[main] + pull_request`, 헤더 주석 `:1-8`)
계약 문서만 고치는 PR 도 반드시 통과한다. **필수 체크 이름을 늘리지 않으면서 전수 적용을
얻는 배치** — 구조적으로 건전.

이 diff 가 같은 잡에 추가한 두 스텝(`:82-89`)도 동일 논리를 따른다:
`tos_spec_status.py --check` · `tos_completion_status.py --check`.
`fetch-depth: 0`(`:40`) 이 전제임을 주석이 명시하고, 그것은 실재한다.

### 6-b. ⚠ `tos-gate.yml` 이 `pull_request` 전용 — main push 에서 미실행 — medium

`.github/workflows/tos-gate.yml:2` → `on: [pull_request]`. `push: branches: [main]` 이 없다.
같은 리포의 `tos-firewall.yml:15-18` 은 둘 다 갖는다.

함의:
- main 에 **직접 push** 되거나 **bypass 로 머지**된 커밋은 tos-gate 를 통과한 적이 없는 상태로
  main 에 앉는다. 이 아크는 실제로 1회 bypass 머지를 사용했다(PR #638).
- main 의 `d0a_entry_state` 회귀는 **다음 PR 이 열릴 때까지** 검출되지 않는다.
- 다만 `tos-firewall.yml` 이 main push 에서 `tos_completion_status.py --check` 를 돌고,
  그 검사기가 U-15 로 같은 9값 상태 기계를 파생한다(§5-c). 따라서 **상태 축 자체는 main 에서도
  덮인다** — 덮이지 않는 것은 하니스 **본문 sha 대조**(`shasum -c`)와 하니스 실행 자체다.
  즉 「main 에서 하니스 파일이 변조되어도 다음 PR 까지 sha 대조가 돌지 않는다」가 정확한 잔여.
권고: `on:` 에 `push: branches: [main]` 추가. 비용은 잡 하나(2스텝)이고 필수 체크 이름은
늘지 않는다.

### 6-c. `test.yml` 변경 — 두 항목, 근거 모두 실측 등재 (건전)

1. `fetch-depth: 0` 추가(`:35-43`) — `tests/tools/test_u17_verify.py` 등 조상성 파생
   검사기가 얕은 클론에서 `PROVENANCE_UNVERIFIABLE` 로 fail-closed 하는 것을 해소.
   `tos-firewall.yml:28-40` 의 동일 근거를 인용하며 실 CI 관측(PR #637/#638)을 든다.
2. yq v4.48.1 핀 스텝(`:57-89`) — `wfcanon-v222.py` [M-4] 가 파서를 `mikefarah v4.48.x` 로
   핀하고 그 밖은 `WF-P0 PREVENTION_UNVERIFIABLE` 로 fail-closed 하므로, ubuntu-latest 의
   선설치 yq(신버전)를 덮어써야 한다.
   **주목할 만한 구조적 정확성**: 주석이 `/usr/local/bin` 이 아니라 `/usr/bin` 에 설치해야 하는
   이유를 테스트의 리터럴 PATH(`/usr/bin` 이 첫째, `/usr/local/bin` 이 마지막)로부터 도출해
   등재했다. 「관례적 선택이 조용히 no-op 이 되는」 함정을 명시적으로 배제한 사례.
   체크섬 검증(`sha256sum -c`) 있음 — 공급망 관점에서도 fail-closed.

**범위 밖 관측(pre-existing, 비차단)**: 세 워크플로가 `fetch-depth: 0` 과 그 근거 주석을
**각자 저작**한다(`test.yml:35-43`, `tos-firewall.yml:28-40`, `tos-gate.yml:12`).
`test.yml` 은 `tos-firewall.yml:28-40` 을 인용하는 형태라 드리프트 시 인용이 낡는다.
composite action 이나 재사용 워크플로로 뽑을 후보 — 이 diff 의 결함은 아니다.

---
## 7. god-object / 추상화 누수 (구조적 분해 관점만 — 함수 길이 계수는 스타일 렌즈 소관, 중복 계수 안 함)

### 7-a. `tools/tos_completion_status.py` = 사실상 패키지가 한 파일에 들어 있다 — medium

측정(AST):

| 지표 | 값 |
| --- | --- |
| 행 | 4,162 (160KB) |
| 최상위 def/class | 128 |
| 함수 | 132 |
| 클래스 | 7 |
| 모듈 수준 할당 | 74 |
| 배너 구획(`# ---- / # 제목`) | 23 |

23개 구획은 이미 «모듈 경계»다. 구획별 규모 상위:

```
 637 lines  U-16        (6개 하위 구획: 격리 스냅샷 기층 · 원장/레지스터 blob 파싱 ·
                         구조 파생 EDGES/c_APP/C_R · 후보 행 평가 g1~g6 · 최상위 오케스트레이션)
 498 lines  강제 검사들
 381 lines  U-12
 350 lines  INV-C5
 301 lines  C3          (TOS-COMPLETION-STATUS 생성기)
 268 lines  U-15-g
 259 lines  D0-5b
 257 lines  D0-4b
 234 lines  U-15
```

U-16 하나가 637행·6구획으로 **자족적인 하위 시스템**(격리 git 스냅샷 생성 → blob 파싱 →
그래프 파생 → 전순서 평가 → 12값 판정)이고, 외부와의 접점은 `derive_u16_state(ctx)` 하나다.
C3 생성기(301행)와 INV-C5(350행)도 «검사»가 아니라 «렌더링/어휘 검사»로 책임 축이 다르다.
분해 비용이 낮고(경계가 이미 그어져 있다) 이득이 큰 배치.

**분해를 막는 실재 제약이 하나 있다**: `tests/tools/test_tos_completion_status.py:25-26` 과
`tools/tos_completion_status.py:3620-3641` 이 둘 다 `importlib.util.spec_from_file_location`
으로 **단일 파일**을 로드한다. 패키지로 쪼개면 그 부트스트랩이 바뀌어야 한다(§2-e 의
로드 규약 통일과 같은 작업). 즉 이것은 «못 하는» 것이 아니라 «§2-e 와 묶어서 해야 하는» 것.
권고: `tools/tos_completion/` 패키지로 승격 — 최소한 U-16(637행)과 C3 렌더러(301행)를
먼저 뽑으면 본체가 3,200행대로 내려간다.

### 7-b. `CheckContext` 의 private 필드를 외부 함수가 직접 읽고 쓴다 — low

`tools/tos_completion_status.py:182` 가 `_owner_track_cache` 를 dataclass 필드로 선언하고,
자유 함수 `_owner_track_report` 가 `:2908-2909`(읽기) · `:2913`·`:2975`(쓰기) 에서
직접 조작한다. 캐시 무효화 규칙이 클래스 밖에 있어 `CheckContext` 만 보고는 불변식을
알 수 없다. 다른 12개 필드는 전부 public 인데 이 하나만 `_` 접두라 경계가 일관되지도 않다.
권고: `CheckContext.owner_track_report()` 메서드로 캐시를 내부화하거나,
`functools.cache` 를 쓰는 자유 함수로 바꿔 `ctx` 에서 상태를 떼어낸다.

### 7-c. 「검사기가 검사 대상을 import 하지 않는다」는 경계는 지켜짐 (건전)

§1-b 실측: 변경된 5개 tools 파일 중 `tos`/`shared`/`services`/`cli` 를 import 하는 것은 0.
D0-5 의 docstring 소비도 `ast.parse` + `ast.get_docstring`(`:3599-3617`)로 **소스 텍스트에서**
파생하며 모듈을 실행하지 않는다 — import-firewall 과 정합하고, 검사 대상의 import 부작용이
검사기 판정에 새어 들어오지 않는다.

---

## 8. «점검했고 건전함» 목록 (Codex 독립 재검증용)

| 항목 | 명령 / 방법 | 결과 |
| --- | --- | --- |
| tos/src 가 런타임 의미 무변경 | docstring 제거 AST dump 대조 (`ast.NodeTransformer`) 7파일 | 7/7 동일 (§1-a) |
| import-firewall layer 1 | `.venv/bin/python tools/tos_firewall_check.py` | `PASS — no violations` rc 0 |
| import-firewall layer 2 설정 | `git diff --name-only 28475ca1^ HEAD -- .importlinter` | 무변경 |
| 하위→상위 역참조 | `grep -rnE '^\s*(from\|import)\s+tools' tos/src shared services cli` | 0 히트 |
| 검사기가 런타임 import 안 함 | `grep -nE '^\s*(from\|import)\s+(tos\|shared\|services\|cli)\b' <5 tools>` | 0 히트 |
| census 단일 저작 | `grep -n 'profile_key_universe\|_profile_null_key_census' tools/*.py` | 저작 1 · 소비 3 |
| 앵커 리터럴 중복 | `grep -rn 'EV-L1=81' tools/ tos-spec/src/ config/ tests/` | config 1히트만 |
| 앵커 리터럴 중복 (U-9a) | `grep -rn 'UNCHK-014' tools/*.py` | 0 히트 |
| 상태 기계 어휘 크기 | AST 로 `return (state,…)` 리터럴 전수 열거 | 7/9/8 — 계약 선언과 일치 |
| bare except | AST `ExceptHandler.type is None` | **0** |
| `.get(k, default)` fail-open | AST 전수 + 각 자리 독해 | 부재→통과값 자리 **0** |
| 프로파일 우주 실측 | `_load_profile_universe(repo_root)` 직접 호출 | 163키 · null 16 · valued 147 |
| resolver docstring 의 키 주장 진위 | 위 우주에서 6키 조회 | 전부 존재 · 전부 non-null (**주장은 참**) |
| 하니스 sha 4자리 일치 | `shasum -a 256` + 4자리 grep | 4/4 `059e13f2…` 일치 |
| bash↔Python 상태 기계 패리티 | `_assert_harness_parity` 계수 + 실코퍼스 테스트 | 9값 전부 결속 |
| 검사기 라이브 판정 | `python tools/tos_completion_status.py --check` | `RESULT: GREEN (violations=0)` |
| tools 스크립트 진입점 | `python tools/{spec_status,contract_index,completion_status}.py --help` | 3/3 rc 0 |
| `tools` 네임스페이스 패키지 해결 | `python -c "import tools; print(tools.__path__)"` | PEP-420 · editable `.pth` 경유 |

---

## 9. 미확인 항목 (**«미발견»을 «없음»으로 적지 않는다**)

1. **`tools/tos_contract_check.py` (7,474행) 내부는 감사하지 않았다.** 이 diff 의 변경
   파일이 아니고 범위 밖이다. tos-firewall Layer 4 와 self-test 가 그 파일을 부르지만,
   그 검사기의 fail-open 여부는 **이 렌즈가 확인하지 않았다.**
2. **`--self-test` 뮤테이션 배터리를 실행하지 않았다.** `tos-firewall.yml:107-108` 이
   `tools/tos_contract_check.py --self-test` 를 돌린다. 프로젝트 기록상 이 self-test 는
   과거 rc 2 로 연속 실패한 이력이 있다. 이번 감사에서 **실행 여부를 확인하지 않았다.**
3. **`tools/u17-verify.sh` (80KB) 의 전체 판정 경로를 읽지 않았다.** `LIT1/LIT2` 사용처
   유무만 grep 으로 확정했다. 나머지 10단 전순서의 fail-open 여부는 미확인.
4. **`tools/tos_evidence_run.py` 의 변경분(+52/−?) 을 구조적으로만 훑었다.** census import
   경로와 `read_register_row` 만 확인했고 나머지 diff 는 미독해.
5. **CSV 데이터 3종(EVIDENCE-REQUIRED-KINDS 488행 · EVIDENCE-SURFACE-MAP 2,024행 ·
   PHASE0-UNCHECKABLE-REGISTER 25행)의 내용은 검증하지 않았다** — 아키텍처 렌즈 밖이며,
   행 단위 정합은 검사기 자신의 소관이다.
6. **`tos/tests/spg/test_spg_replay_substrate.py` (291행 신규) 를 읽지 않았다.** 테스트
   렌즈 소관으로 남긴다.
7. **§2-e 의 「editable 설치 없는 인터프리터에서 spec_status 가 깨진다」를 실제로
   재현하지 않았다.** 저작자 주석의 진단과 `tools/__init__.py` 부재라는 구조 사실로
   추론했다. clean venv 재현은 미실행.
8. **CI 에서의 실제 동작을 관측하지 않았다.** 모든 실측은 로컬 워크트리(HEAD `b5d2448a`)
   에서 수행했다. `tos-gate` 의 `pull_request` 전용 트리거가 main 회귀를 놓치는지는
   워크플로 문언에서 파생한 것이지 CI 로그에서 관측한 것이 아니다.

---

## 10. 발견 요약

| # | severity | 항목 | 위치 | 범위 |
| --- | --- | --- | --- | --- |
| 1 | **high** | D-1 처분이 산문 자기신고 · 7사이트 전부 UNDECIDED→UNBOUND 전이 · 키 대조축 도달 0 | `tools/tos_completion_status.py:3668-3682`, `:3591-3595` | in-range |
| 2 | medium | REGISTER CSV 16필드 스키마 두 벌 저작 · 드리프트 잠금 테스트 0 (현재 값은 일치) | `tools/tos_completion_status.py:106-123` ↔ `tools/tos_spec_status.py:89-106` | in-range |
| 3 | medium | 처분 단위(사이트) ↔ 근거 단위(필드) 불일치 | `tools/tos_completion_status.py:3668-3682` · `tos/src/tos/backtest/resolver.py:55-90` | in-range |
| 4 | medium | U-1a 문법 축이 config 불량 시 조용히 침묵 | `tools/tos_completion_status.py:2912-2914`, `:2950` | in-range |
| 5 | medium | 역방향 census 폴백이 조용함 · grounding 축에 fail-open | `tools/tos_spec_status.py:1697-1731`, `:1755-1756` | in-range |
| 6 | medium | register CSV 리더 3벌 · strip/예외 처분 비대칭 (오늘은 잠재 — 패딩 셀 0 실측) | `:257` ↔ `:354` ↔ `tools/tos_evidence_run.py:1449` | in-range |
| 7 | medium | 어휘 상수 사본 2쌍 · 동기화 강제 없음 | `tools/tos_completion_status.py:3012`, `:3016-3026` | in-range |
| 8 | medium | 공유 모듈 로드 규약 3벌 · private 이름이 공유 API | `:3620-3641` ↔ `tos_spec_status.py:29` ↔ `tos_contract_index.py:46-47` | in-range |
| 9 | medium | sha 핀 4자리 수동 동기화 · 파생 없음 | `tos-gate.yml:17`, `wfcanon-v222.py:93`, `u17-verify.sh:75`, 계약 `:7873` | in-range |
| 10 | medium | `u17-verify.sh` `LIT1`/`LIT2` = 죽은 리터럴(참조 0) · 이 diff 가 갱신함 | `tools/u17-verify.sh:74-75` | in-range |
| 11 | medium | `tos-gate.yml` `pull_request` 전용 — main push 미실행 | `.github/workflows/tos-gate.yml:2` | in-range |
| 12 | medium | 4,162행 단일 파일 = 사실상 패키지 (U-16 637행 등 분해 후보) | `tools/tos_completion_status.py` | in-range |
| 13 | low | `else 0` fallback 리터럴 (현재 도달 불가) | `tools/tos_completion_status.py:2927-2929` | in-range |
| 14 | low | 테스트 픽스처가 실 config 값을 리터럴 복제 · 실 config 음성 대조군 공백 | `tests/tools/test_tos_completion_status.py:596-598` | in-range |
| 15 | low | `tools/` 내부 import 규약 2벌 | `tos_spec_status.py:29` ↔ `tos_contract_index.py:47` | in-range |
| 16 | low | `CheckContext._owner_track_cache` 를 외부 자유 함수가 조작 | `tools/tos_completion_status.py:182`, `:2908-2975` | in-range |
| — | info | `fetch-depth: 0` 근거 주석 3워크플로 각자 저작 | `test.yml:35`, `tos-firewall.yml:28`, `tos-gate.yml:12` | pre-existing |

계: **high 1 · medium 11 · low 4 · info 1**

유일한 high(#1)는 뮤테이션 대조군으로 «현행 상태에서 축이 죽어 있음»을 실증한 건이다.
나머지는 전부 조건부·잠재 위험이거나 구조적 부채다.
