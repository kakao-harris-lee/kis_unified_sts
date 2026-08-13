# 스타일 렌즈 감사 증거 — TOS Phase 0 완료 계약 프로토타입 v2.5

> **이 문서는 증거이지 판정이 아니다.** verdict 는 Codex 심판 레인 소관이다.
> 여기 적힌 severity 는 스타일 렌즈 내부의 상대 순위이며, 게이트 통과/차단을
> 주장하지 않는다.

## 0. 결속 (revision binding)

| 항목 | 값 |
| --- | --- |
| repo HEAD | `2b7b2a209aefb9bd7186949f405f6418fd4902cd` |
| 대상 git 상태 | `?? tools/spikes/phase0_contract/` (**전체 untracked** — diff 기준선 없음) |
| 감사 시각 | 2026-08-13 |

대상 파일 SHA-256 (untracked 이므로 blob id 대신 내용 digest 로 결속한다):

```text
87072455d4a6f253bf84a90079d389f9c7044a7e454b5d5fdff5dc88e40d5889  tools/spikes/phase0_contract/test_contracts.py
6aa7556dca2618bc6fc530a0dfc5b9f3d304b941f42a304a4e1fc5fa00c0b0e1  tools/spikes/phase0_contract/proto/__init__.py
43d8f60510a3ec5b34386db6b969c7b02a62d547f03ee9174ce10a802df0cc2c  tools/spikes/phase0_contract/proto/boundary.py
d55ce22a4e7439ad645a73ce99a4cd30c1cb0bb3810014daedacbf306ab767d7  tools/spikes/phase0_contract/proto/config.py
6633e473cbc903415babf9f44ff0f429c0c497ee3b081a5f25a2e9522dbbac1e  tools/spikes/phase0_contract/proto/enforcement.py
916b53c5a9ce2c45b5fdcdb3e2c9096baa8a7bbadd56cd00a7cef520ee0d78ad  tools/spikes/phase0_contract/proto/floor.py
17e9f8d69fae7a92c278697c15009a34538b64847de077ec3cb27d8b8733a370  tools/spikes/phase0_contract/proto/gates.py
e69d186b2e226b4b149d2c3a5d621d9c37786623bed7d6c12fd395538eb8b065  tools/spikes/phase0_contract/proto/register.py
9377c07c2ad745ff8c58ee18198d90516a431963da47f6feec7d39e8520fe850  tools/spikes/phase0_contract/proto/config.yaml
```

**대상 범위 주의**: 지시된 범위는 `test_contracts.py` · `proto/*.py` · `proto/config.yaml`
이다. 같은 디렉터리의 `blocks_gate_consumption.py`(604행) · `sweep_deprecated_vocabulary.py`(280행)
는 **범위 밖**이며, 도구 출력에 섞여 나온 항목은 §1 에서 분리 표기했다.
(러너 자신도 `L-T77-DOMAIN` 노트에서 이 두 파일을 "스캔 도메인 밖"으로 등재하고 있다 —
스타일 감사 범위와 러너의 자기 스캔 범위가 우연히 일치한다.)

---

## 1. 도구 실측 (verbatim)

### 1.0 도구 버전 · 설정 근거

```text
ruff 0.15.1
black, 26.1.0 (compiled: yes)
Python (CPython) 3.12.0
mypy 2.3.0 (compiled: yes)
```

프로젝트 설정 (`pyproject.toml`):

- `[tool.black] line-length = 88`, `target-version = ["py311","py312"]` (:207-210)
- `[tool.ruff] line-length = 88`, `target-version = "py311"` (:226-228);
  `select = [E,W,F,I,B,C4,UP,ARG,SIM]`, `ignore` 에 `E501` 포함 (:245-254)
- `[tool.ruff.lint.per-file-ignores]` 에 **`tools/**` 항목 없음** (:256-273) —
  `E402` 면제는 `tests/**` · `scripts/**` · `run_*.py` · `verify_*.py` 뿐이다.
- `[tool.mypy] disallow_untyped_defs = true`, `disallow_incomplete_defs = true`,
  `warn_return_any = true`, `check_untyped_defs = true` (:277-286) —
  **프로젝트가 선언한 표준이 strict 계열이다.**

### 1.1 `ruff check` — 위반 0

```console
$ ruff check tools/spikes/phase0_contract/
All checks passed!
```

exit 0. (E501 이 프로젝트 설정에서 ignore 이므로 줄길이는 ruff 가 보지 않는다 —
§4.10 에서 별도 실측했다.)

### 1.2 `black --check --diff` — 2 파일 위반

```console
$ black --check --diff tools/spikes/phase0_contract/
--- .../proto/boundary.py	2026-08-12 20:55:19.734429+00:00
+++ .../proto/boundary.py	2026-08-12 22:53:53.915362+00:00
@@ -336,11 +336,13 @@
                     for sub in ast.walk(target):
                         if isinstance(sub, ast.Name):
                             mark(sub.id, None)
         elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
             mark(node.target.id, node.value)
-        elif isinstance(node, (ast.AugAssign, ast.For, ast.AsyncFor, ast.comprehension)):
+        elif isinstance(
+            node, (ast.AugAssign, ast.For, ast.AsyncFor, ast.comprehension)
+        ):
             target = getattr(node, "target", None)
             for sub in ast.walk(target) if target is not None else ():
                 if isinstance(sub, ast.Name):
                     mark(sub.id, None)
         elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
would reformat .../proto/boundary.py
--- .../test_contracts.py	2026-08-12 21:40:58.916924+00:00
+++ .../test_contracts.py	2026-08-12 22:53:54.153566+00:00
@@ -197,11 +197,13 @@
             if limit.unchk is not None and limit.unchk not in registered:
                 bad.append(f"{limit.lid}: unchk={limit.unchk} 미등재")
         return bad
 
     # --- L2 주차 거부 (v2.5) ----------------------------------------------
-    def parked_limits(self, unchk_ids: Sequence[str], waivers: Sequence[str]) -> list[str]:
+    def parked_limits(
+        self, unchk_ids: Sequence[str], waivers: Sequence[str]
+    ) -> list[str]:
         """결함 어휘를 쓰면서 **green Case 에 주차**한 노트.

Oh no! 💥 💔 💥
2 files would be reformatted, 8 files would be left unchanged.
```

위반 지점: `proto/boundary.py:341` · `test_contracts.py:202`. 둘 다 89/91자 한 줄
초과이며 내용 변경 없는 줄바꿈이다.

### 1.3 `mypy --ignore-missing-imports` — 63 errors / 5 files

```console
$ mypy --ignore-missing-imports tools/spikes/phase0_contract/
tools/spikes/phase0_contract/blocks_gate_consumption.py:277: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/blocks_gate_consumption.py:284: error: Returning Any from function declared to return "bool"  [no-any-return]
tools/spikes/phase0_contract/blocks_gate_consumption.py:287: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/proto/gates.py:209: error: "object" has no attribute "id"  [attr-defined]
tools/spikes/phase0_contract/proto/gates.py:219: error: "object" has no attribute "id"  [attr-defined]
tools/spikes/phase0_contract/proto/enforcement.py:30: error: Argument 2 to "replace" of "Context" has incompatible type "**dict[str, object]"; expected "Mapping[str, int | str]"  [arg-type]
tools/spikes/phase0_contract/proto/enforcement.py:30: error: Argument 2 to "replace" of "Context" has incompatible type "**dict[str, object]"; expected "tuple[UnchkRow, ...]"  [arg-type]
tools/spikes/phase0_contract/proto/enforcement.py:30: error: Argument 2 to "replace" of "Context" has incompatible type "**dict[str, object]"; expected "tuple[EvidenceRow, ...]"  [arg-type]
tools/spikes/phase0_contract/proto/enforcement.py:30: error: Argument 2 to "replace" of "Context" has incompatible type "**dict[str, object]"; expected "Mapping[str, Gate]"  [arg-type]
tools/spikes/phase0_contract/proto/enforcement.py:30: error: Argument 2 to "replace" of "Context" has incompatible type "**dict[str, object]"; expected "Mapping[str, object]"  [arg-type]
tools/spikes/phase0_contract/proto/enforcement.py:30: error: Argument 2 to "replace" of "Context" has incompatible type "**dict[str, object]"; expected "Evaluation"  [arg-type]
tools/spikes/phase0_contract/proto/enforcement.py:30: error: Argument 2 to "replace" of "Context" has incompatible type "**dict[str, object]"; expected "Mapping[str, int]"  [arg-type]
tools/spikes/phase0_contract/proto/enforcement.py:200: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:287: error: Incompatible types in assignment (expression has type "expr", variable has type "str | None")  [assignment]
tools/spikes/phase0_contract/proto/boundary.py:289: error: Argument 1 to "_const_str" has incompatible type "str | None"; expected "AST"  [arg-type]
tools/spikes/phase0_contract/proto/boundary.py:342: error: Incompatible types in assignment (expression has type "Any | None", variable has type "expr")  [assignment]
tools/spikes/phase0_contract/proto/boundary.py:424: error: Argument 1 to "fsdecode" has incompatible type "object"; expected "str | bytes | PathLike[str] | PathLike[bytes]"  [arg-type]
tools/spikes/phase0_contract/proto/boundary.py:492: error: Function is missing a return type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:527: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:531: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:535: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:539: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:543: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:547: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:551: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:555: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:575: error: Function is missing a return type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:586: error: Function is missing a return type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:590: error: Function is missing a return type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:591: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:608: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:613: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:618: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:623: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/proto/boundary.py:628: error: Function is missing a type annotation  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:330: error: "object" object is not iterable  [misc]
tools/spikes/phase0_contract/test_contracts.py:331: error: Cannot determine type of "label"  [has-type]
tools/spikes/phase0_contract/test_contracts.py:331: error: Cannot determine type of "module"  [has-type]
tools/spikes/phase0_contract/test_contracts.py:380: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:428: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:542: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:604: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:682: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:936: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:971: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:990: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1042: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1102: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1132: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1163: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1204: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1285: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1325: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1361: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1378: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1401: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1419: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1436: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1464: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tools/spikes/phase0_contract/test_contracts.py:1646: error: Incompatible types in assignment (expression has type "str", variable has type "Case | None")  [assignment]
tools/spikes/phase0_contract/test_contracts.py:1648: error: Incompatible types in assignment (expression has type "str", variable has type "Case | None")  [assignment]
tools/spikes/phase0_contract/test_contracts.py:1650: error: Unsupported left operand type for + ("Case")  [operator]
tools/spikes/phase0_contract/test_contracts.py:1650: error: Unsupported left operand type for + ("None")  [operator]
tools/spikes/phase0_contract/test_contracts.py:1650: note: Left operand is of type "Case | None"
pyproject.toml: note: unused section(s): module = ['mlflow.*', 'optuna.*', 'redis.*']
Found 63 errors in 5 files (checked 10 source files)
```

파일별 · 코드별 집계:

| 파일 | errors | 범위 |
| --- | ---: | --- |
| `test_contracts.py` | 29 | 대상 |
| `proto/boundary.py` | 22 | 대상 |
| `proto/enforcement.py` | 8 | 대상 |
| `proto/gates.py` | 2 | 대상 |
| `blocks_gate_consumption.py` | 3 | **범위 밖** |
| **대상 소계** | **61** | |

| error code | 건수 |
| --- | ---: |
| `no-untyped-def` | 42 |
| `arg-type` | 9 |
| `assignment` | 4 |
| `operator` | 2 |
| `has-type` | 2 |
| `attr-defined` | 2 |
| `no-any-return` | 1 (범위 밖) |
| `misc` | 1 |

### 1.4 CI 게이팅 실측 — **이 디렉터리를 막는 게이트는 없다**

severity 부풀림 방지를 위해 실측한다 (`.github/workflows/test.yml`):

```yaml
  lint:
    runs-on: ubuntu-latest
    continue-on-error: true          # ← 잡 레벨
    ...
      - name: Run ruff
        run: ruff check . --output-format=github
        continue-on-error: true      # ← 스텝 레벨 (이중)
      - name: Check formatting with black
        run: black --check --diff .
        continue-on-error: true      # ← 스텝 레벨 (이중)

  type-check:
    continue-on-error: true
      - name: Run mypy
        run: mypy shared/ --ignore-missing-imports --no-error-summary || true
```

- `lint` 잡은 잡·스텝 **양쪽에 `continue-on-error: true`** — 실패해도 차단하지 않는다.
- `type-check` 잡은 **`shared/` 만** 검사하고 `|| true` 까지 붙는다 — `tools/` 는
  애초에 CI mypy 도메인 밖이다.
- `pytest` 는 `testpaths = ["tests"]` (`pyproject.toml:299`) 이므로 기본 실행에서
  이 파일을 수집하지 않는다.

**repo 베이스라인 실측** (git-tracked `*.py` 2,320개 전수):

```console
$ git ls-files '*.py' | tr '\n' '\0' | xargs -0 black --check
399 files would be reformatted, 1921 files would be left unchanged.
```

→ repo 전체가 이미 black-clean 이 아니다(**17.2%** 위반). 이 디렉터리의 2건은
기존 베이스라인과 **정합**하며 회귀가 아니다. §4.11 severity 를 LOW 로 둔 근거다.

### 1.5 부수 실측 — black 교정이 커밋된 앵커를 흔드는가 (**흔들지 않는다**)

`config.yaml` 이 4개 digest 앵커를 고정하고 있으므로, "black 을 돌리면 앵커가
깨져서 못 고친다"는 반론이 가능하다. 스크래치 사본에서 실측했다:

```text
test_contracts limit-literal-anchor: before=5efb40f2c1962a30 after=5efb40f2c1962a30 SAME=True
test_contracts co_consts:            before=e968caac97a35888 after=e968caac97a35888 SAME=True
boundary co_consts:                  before=70de4aaa71a2cfeb after=70de4aaa71a2cfeb SAME=True
raw-text sha (test_contracts):       SAME=False
raw-text sha (boundary):             SAME=False
```

`before` 값 `5efb40f2c1962a30` 은 `proto/config.yaml:33`
`anchor_limit_text_digest: 5efb40f2c1962a30` 과 **정확히 일치**한다 — 재구현이
러너의 `limit_text_anchor()` 와 동치임을 교차 확인한 것이다.

**함의**: `anchor_limit_text_digest`(AST 리터럴 기반)와
`anchor_runner_source_digest`(`co_consts` 기반, v2.5 5차 교정)는 **원시 텍스트를
해시하지 않으므로** 줄바꿈 재포매팅에 불변이다. `raw-text sha` 만 바뀐다.
따라서 §4.11 의 black 2건은 **`config.yaml` 무편집으로 교정 가능**하다.
(4차 교정판이었다면 `read_text()` 를 해시했으므로 앵커 갱신이 필요했을 것이다 —
5차 교정이 부수적으로 포매팅 교정 가능성을 얻었다.)

---

## 2. 발견 요약

| # | severity | 위치 | 요약 | conf |
| --- | --- | --- | --- | ---: |
| S-1 | HIGH | `test_contracts.py:318` | 앵커 경로 함수 `loaded_code_text` 의 타입 힌트가 **틀렸다** (`Sequence[object]` ≠ 실제 `Sequence[tuple[str, object]]`) | 98 |
| S-2 | MEDIUM | `test_contracts.py` 21곳 | `cfg` 파라미터 전수 무타입 — `proto/` 전역에서 쓰는 `Mapping[str, int \| str]` 이 이미 존재 | 97 |
| S-3 | MEDIUM | `test_contracts.py:82-90` | `DEFECT_WORDS` 어휘 목록은 코드, 그 면제(`limit_vocabulary_waivers`)는 설정 — 같은 계약의 두 반쪽이 갈라져 있다 | 88 |
| S-4 | MEDIUM | `proto/boundary.py:96` | `EXPECTED_RUNNER_RELPATH` 앵커만 코드 리터럴 (다른 앵커 9개는 전부 `config.yaml`) | 82 |
| S-5 | MEDIUM | `test_contracts.py:475` | `len(ignoring_detected) == 3` — 3 은 PARTIAL 술어 수이며 레지스트리에서 파생 가능 | 90 |
| S-6 | MEDIUM | `proto/register.py:18,70` | `UNASSIGNED = "미배정"` 과 `NONE = "UNASSIGNED"` — 이름과 값이 교차 배선 | 92 |
| S-7 | MEDIUM | `test_contracts.py` 파일명 | `test_*.py` 인데 pytest 모듈이 아니고, import 만으로 `sys.path`·`sys.dont_write_bytecode` 전역 변경 | 85 |
| S-8 | MEDIUM | `test_contracts.py` 11곳 | 모듈 경계 넘어 `enforcement._check_*` private 함수 직접 호출 | 90 |
| S-9 | MEDIUM | `proto/boundary.py:49,59` | `"tos-"+"spec/"` 와 `"tos-"+"spec"` — 같은 토큰을 **독립 리터럴 쌍 2개**로 조립 (DRY) | 85 |
| S-10 | MEDIUM | `test_contracts.py:1636,1646` | `main()` 안에서 이름 `bound` 를 `Case \| None` 과 표시 문자열 두 용도로 재사용 | 95 |
| S-11 | LOW | `boundary.py:341`, `test_contracts.py:202` | black 위반 2건 (repo 베이스라인 399/2320 과 정합, CI 비차단) | 99 |
| S-12 | LOW | `test_contracts.py:255,258,277,352,374` | digest 절단 자리수 `[:12]` / `[:16]` 이 무명 인라인 리터럴이고 서로 다르다 | 90 |
| S-13 | LOW | `proto/enforcement.py:29-30` | `replaced(**changes: object)` — mypy 63건 중 7건(11%)의 단일 발생원 | 93 |
| S-14 | LOW | `test_contracts.py:127,135,155,1579,1606` 외 | 공개 표면 docstring 누락 (`Report`·`run_all`·`main`·`Finding`·`Context.replaced`) | 95 |
| S-15 | LOW | 전 파일 | Google style `Args:`/`Returns:`/`Raises:` 섹션 0건 (repo `shared/` 는 154/450 사용) | 95 |
| S-16 | LOW | `proto/floor.py:20` | `SURFACE_KINDS` 정의 후 미사용 — 죽은 상수 | 99 |
| S-17 | LOW | `test_contracts.py:1532-1535` | 중첩 f-string + 조건식 4줄이 101~105자, black 도 못 쪼갠다 | 90 |
| S-18 | LOW | `test_contracts.py:799,859` | `recorder2` · `read_rec2` 숫자 접미 변수명 | 88 |
| S-19 | LOW | `test_contracts.py:135-137` | `Report.add` 가 `Case` 를 반환하지만 22개 호출처 전부 반환값 미사용 | 96 |
| S-20 | LOW | `test_contracts.py:406,483-485,1094,1455` | 표시·판정 문자열의 `11` · `4` 매직 리터럴 | 80 |
| S-21 | LOW | `enforcement.py:12-14`, `register.py:14-16` | `from . import X` 와 `from .X import y` 혼용 | 75 |

**분포**: HIGH 1 · MEDIUM 9 · LOW 11. CRITICAL 0.

> 이 렌즈에서 CRITICAL 은 없다. 스타일 위반이 계약 정합성을 직접 깨는 사례를
> 관측하지 못했다. S-1 만 HIGH 인데, 그것도 "런타임 결함"이 아니라 "앵커 경로의
> 타입 선언이 실제 자료구조와 다르다"는 **선언층/평가층 간극**이기 때문이다 —
> 이 프로토타입 자신이 반복해서 다루는 결함 클래스와 같은 종류라서 올렸다.

---

## 3. 잘 되어 있는 점 (음성 관측)

과잉 지적 방지를 위해 **양방향**으로 적는다. 다음은 실측 결과 문제가 **없는** 축이다:

- **`ruff check` 위반 0** — 미사용 import(F401) 0, 와일드카드 import 0,
  import 정렬(I) 위반 0, bugbear(B) 0, comprehension(C4) 0, pyupgrade(UP) 0.
- **순환 import 없음** — 실측 그래프는 DAG 다:
  `config`·`floor`·`gates`·`boundary` (leaf) → `register`(→gates,config,floor)
  → `enforcement`(→floor,gates,register,config). `boundary` 는 stdlib 만 쓴다.
- **`# noqa: E402` 사용이 정당하다** (`test_contracts.py:73-74`) — `tools/**` 는
  ruff per-file-ignores 에 없으므로 `sys.path` 조작 후 import 에는 실제로 noqa 가
  필요하다. 억제가 아니라 정확한 사용이다.
- **`proto/floor.py`·`proto/register.py`·`proto/config.py` 는 docstring 누락 0**
  (AST 전수 검사). 모듈·클래스·함수 전부 docstring 을 갖는다.
- **`print()` 사용은 `main()` 리포트 출력에 한정** — python-backend 규칙의
  "non-debug output 에 logging" 취지는 서비스 코드 대상이고, 이 러너는 stdout
  리포트가 산출물 자체다. 게다가 `write_guard` 가 `os.write(fd>2)` 만 막고
  stdout/stderr 는 통과시키도록 **의도적으로** 설계됐다(`boundary.py:628-633`).
  지적하지 않는다.
- **`pathlib.Path` 일관 사용** — `os.path` 사용 0. `os` 는 `fsdecode`·`open`·
  `listdir` 등 가드 대상 진입점 패치에만 쓴다.
- **f-string 일관 사용** — `.format()` / `%` 를 문자열 조립에 쓰는 곳은
  `boundary.py:257,293` 뿐이고, 거기는 **AST 폴딩 대상 문법을 구현하는 코드**라
  의도적이다.
- **`config.yaml` 이 임계값을 실제로 구동한다** — `owner_track_range_max_width`
  하드코딩 회귀는 러너 자신이 `T-62-cfg` Case 로 결속해 감시한다
  (`test_contracts.py:643-667`). CLAUDE.md "No Hardcoding" 의 핵심 축은
  **지켜지고 있고 자기 검사까지 붙어 있다.**

---

## 4. 상세 발견

### S-1 (HIGH) 앵커 경로 함수의 타입 힌트가 실제 자료구조와 다르다

- **dimension**: style / 타입 힌트
- **location**: `tools/spikes/phase0_contract/test_contracts.py:318` (사용처 `:330-331`, 호출처 `:1493-1503`)
- **finding**

  ```python
  def loaded_code_text(modules: Sequence[object]) -> str:
      ...
      for label, module in modules:          # :330
          parts.extend(_module_code_parts(label, module))   # :331
  ```

  선언은 `Sequence[object]` 인데 본문은 원소를 **2-튜플로 언패킹**한다. 실제 타입은
  `Sequence[tuple[str, object]]` 이며, 호출처 `:1494-1502` 가 정확히 그 형태로 넘긴다.
  mypy 가 3건으로 잡는다:

  ```text
  test_contracts.py:330: error: "object" object is not iterable  [misc]
  test_contracts.py:331: error: Cannot determine type of "label"  [has-type]
  test_contracts.py:331: error: Cannot determine type of "module"  [has-type]
  ```

  이것이 HIGH 인 이유는 위치다. 이 함수는 v2.5 **5차 교정**이 도입한
  `anchor_runner_source_digest` 계산 경로이고, `config.yaml:49-61` 이 30줄에 걸쳐
  "대상은 실행 중인 코드다 — 디스크 파일이 아니다"라고 정당화한 바로 그 표면이다.
  가장 정밀하게 설계된 경로의 **타입 선언이 자료구조를 잘못 말하고 있다.**
  `_module_code_parts(label: str, module: object)` (:291) 는 올바른 타입을 갖고
  있으므로, 상위 함수만 선언이 뒤처진 형태다.

  또한 `Sequence[object]` 는 문자열도 만족하므로 `loaded_code_text("abc")` 가
  타입 체크를 통과하고 런타임에 언패킹 실패한다 — 선언이 실제 계약보다 넓다.
- **recommendation**: `def loaded_code_text(modules: Sequence[tuple[str, object]]) -> str:`
  로 좁힌다. 한 줄 수정이고 §1.5 실측대로 `co_consts` digest 는 시그니처 문자열을
  담지 않으므로 **앵커 값 변경 없다.**
- **confidence**: 98

---

### S-2 (MEDIUM) `cfg` 파라미터 21곳 전수 무타입

- **dimension**: style / 타입 힌트
- **location**: `test_contracts.py` — 실측 전수 열거:

  ```text
  380:def t75_all_met_reachability(cfg, rep: Report) -> None:
  428:def t2_input_missing_basis(cfg, rep: Report) -> None:
  542:def t69_classification_isolation(cfg, rep: Report) -> None:
  604:def t62_owner_track_grammar(cfg, rep: Report) -> None:
  682:def t77_boundary(cfg, rep: Report) -> None:
  936:def t61_reason_membership_move(cfg, rep: Report) -> None:
  971:def t70_reason_separation(cfg, rep: Report) -> None:
  990:def t68_blocks_gate_target(cfg, rep: Report) -> None:
  1042:def t67_metric_movement(cfg, rep: Report) -> None:
  1102:def fwd_a_0_superset_closure(cfg, rep: Report) -> None:
  1132:def t11_inv_c4(cfg, rep: Report) -> None:
  1163:def t39_enforcement_registry(cfg, rep: Report) -> None:
  1204:def t76_level_raw_anchor(cfg, rep: Report) -> None:
  1285:def unchk_019_registry_omission(cfg, rep: Report) -> None:
  1325:def u8b_kind_exclusion(cfg, rep: Report) -> None:
  1361:def t71_distribution_anchor(cfg, rep: Report) -> None:
  1378:def t72_range_noblock_but_counted(cfg, rep: Report) -> None:
  1401:def t73_metric_exposure(cfg, rep: Report) -> None:
  1419:def t74_closable_transition_anchor(cfg, rep: Report) -> None:
  1436:def floor_parsing_aborts(cfg, rep: Report) -> None:
  1464:def self_check(cfg, rep: Report) -> None:
  ```

  총 **21곳**. mypy `no-untyped-def` 21건이 정확히 여기서 나온다.
- **finding**: 같은 시그니처의 `rep: Report` 는 전부 타입이 붙어 있는데 `cfg` 만
  일관되게 빠졌다 — 실수가 아니라 습관으로 굳은 패턴이다. 올바른 타입은 **이미
  프로젝트 안에 존재한다**: `proto/config.py:48 load_config() -> dict[str, int | str]`,
  `proto/enforcement.py:21,191,201`, `proto/register.py:73,115,200,217,239` 가 전부
  `Mapping[str, int | str]` 을 쓴다. `proto/` 는 규율이 서 있는데 러너만 빠졌다.

  `pyproject.toml:281 disallow_untyped_defs = true` 가 프로젝트 표준이고,
  `.github/instructions/python-backend.instructions.md:18` 은 "Type hints on ALL
  function signatures (parameters and return types)" 를 명시한다. 다만 §1.4 실측대로
  CI 가 `tools/` 에 mypy 를 돌리지 않으므로 **차단된 적이 없어 축적된** 형태다.
- **recommendation**: `from collections.abc import Mapping` 을 `:62` 의
  `from collections.abc import Sequence` 에 합치고, 21곳을
  `cfg: Mapping[str, int | str]` 로 일괄 치환한다. 시그니처 문자열은 `co_consts`
  에 들어가지 않으므로 앵커 무영향이다(§1.5).
- **confidence**: 97

---

### S-3 (MEDIUM) 결함 어휘는 코드, 면제는 설정 — 한 계약의 두 반쪽이 갈라져 있다

- **dimension**: style / 하드코딩 (CLAUDE.md 비협상 규칙)
- **location**: `test_contracts.py:82-90` vs `proto/config.yaml:68`
- **finding**

  ```python
  # test_contracts.py:82-90
  DEFECT_WORDS: tuple[str, ...] = (
      "결함", "위반", "반증", "충돌", "우회", "미검출", "통과시킨",
  )
  ```
  ```yaml
  # proto/config.yaml:68
  limit_vocabulary_waivers: L-T77-SEAM
  ```

  L2 주차 거부 계약(`parked_limits`, `:202-224`)은 두 입력을 쓴다: **어휘 목록**과
  **면제 목록**. 면제는 설정에 있고 그 이유를 `config.yaml:63-67` 이
  "면제를 코드가 아니라 여기에 두어 diff 로 드러나게 한다"고 명시한다.
  **같은 논리가 어휘 목록에도 적용되는데 어휘만 코드에 있다.** 어휘에서 단어를
  빼는 편집은 면제를 추가하는 편집과 효과가 같지만(주차가 통과된다) 설정 diff 를
  남기지 않는다.

  CLAUDE.md 비협상 규칙은 "thresholds, symbols, risk values, ports, Redis DBs,
  schedules, and feature gates belong in YAML/env/config files" 다. 닫힌 판정
  어휘는 이 열거의 문자적 항목은 아니지만 `feature gates` 에 가장 가깝다.
- **반론도 기록한다**: 러너 docstring `:76-81` 과 `:36-40` 은 "이 목록은 폐쇄가
  아니다 · 목록을 늘려 폐쇄를 주장하지 않는다 — 그것이 v2.3 이 진 게임이다"라고
  명시하며, 목록 밖 서술은 L1(등재 강제)이 잡는 **이중 구조**다. 즉 어휘 목록의
  완전성에 계약이 의존하지 않으므로, 설정 이동의 실익은 "무결성"이 아니라
  "가시성" 뿐이다. 그래서 HIGH 가 아니라 MEDIUM 이다.
- **recommendation**: `defect_vocabulary:` 키를 `config.yaml` 에 추가하고
  `cfg_list()` 로 읽는다 (`limit_vocabulary_waivers` 와 완전 대칭). 이동 시
  `anchor_runner_source_digest` 는 `co_consts` 에서 7개 문자열이 빠지므로
  **갱신 필요** — 그 갱신 자체가 설계가 의도한 가시화 diff 다.
- **confidence**: 88

---

### S-4 (MEDIUM) 앵커 10개 중 1개만 코드 리터럴

- **dimension**: style / 하드코딩
- **location**: `proto/boundary.py:96`
- **finding**

  ```python
  # boundary.py:94-96
  REPO_MARKERS: tuple[str, ...] = (".git", "pyproject.toml")
  EXPECTED_RUNNER_RELPATH = "tools/spikes/phase0_contract/test_contracts.py"
  ```

  `config.yaml` 은 앵커를 9개 담는다(`anchor_classification_*` 3, `anchor_closable_no_ids`,
  `anchor_enforcement_key_count`, `anchor_limit_text_digest`, `anchor_limit_emitted_digest`,
  `anchor_case_prose_digest`, `anchor_runner_source_digest`, `anchor_evidence_level_distribution`,
  `anchor_level_kinds`). **`EXPECTED_RUNNER_RELPATH` 만 코드에 있다** — 그런데 이것도
  T-77-④(`locate_violation`, `:438-456`)가 red/green 을 가르는 데 쓰는 앵커값이고,
  `config.yaml:1` 이 "프로토타입 임계값 — **전부 여기서 읽는다**"라고 선언한 대상이다.

  결과: 러너를 옮기면서 `boundary.py:96` 을 같이 고치는 편집은 **설정 diff 없이**
  T-77-④ 를 green 으로 유지한다. 다른 9개 앵커는 그럴 수 없다.
- **반론**: `boundary.py` 는 `proto.config` 를 import 하지 않는 유일한 proto 모듈이고
  (§3 import 그래프 참조), 그 독립성 자체가 "경계 강제기가 설정에 의존하지 않는다"는
  설계 성질일 수 있다. 그렇다면 이것은 스타일 일탈이 아니라 **의도된 비대칭**이며,
  다만 그 의도가 어디에도 적혀 있지 않다. 최소한 주석이 필요하다.
- **recommendation**: 둘 중 하나 — ① `config.yaml` 에
  `anchor_expected_runner_relpath` 로 이동하고 `locate_violation(runner, repo_root, cfg)`
  로 주입, 또는 ② 코드에 남기되 `boundary.py:94-96` 에 "이 앵커는 설정 밖이다 —
  경계 강제기는 설정을 읽지 않기 때문이다"를 명시하고, 러너의 한계 노트
  (`declared_limit_ids`)에 등재한다. ②가 이 프로토타입의 기존 규율(가시화)과 정합적이다.
- **confidence**: 82

---

### S-5 (MEDIUM) 구조에서 파생 가능한 값이 리터럴 `3` 으로 박혀 있다

- **dimension**: style / 매직넘버
- **location**: `test_contracts.py:475`
- **finding**

  ```python
  # test_contracts.py:462-475
  ignoring_detected: list[str] = []
  for gid in gates.completion_gates(registry):
      for predicate in registry[gid].predicates:
          if predicate.classification != gates.PARTIAL:
              continue
          ...
  mutant_red = len(ignoring_detected) == 3     # :475
  ```

  `3` 은 PARTIAL 술어의 개수다. 같은 값이 `config.yaml:17
  anchor_classification_partial: 3` 에 앵커로 이미 있고,
  `gates.classification_distribution(registry)[gates.PARTIAL]` 로도 파생 가능하다.
  즉 **동일 사실의 세 번째 사본**이 판정식 안에 무명 리터럴로 들어가 있다.

  이 리포에 축적된 규율("구조 파생 > 자기신고")과 정면으로 어긋나는 지점이고,
  같은 함수의 인접 코드가 이미 파생을 쓴다 — `:1156 len(changed) == len(nmc_pids)`,
  `:1190 len(reds) == len(reg)` 는 전부 파생형이다. **한 파일 안에서 규율이
  일관되지 않다.**

  실패 시나리오: PARTIAL 술어가 3→4로 늘면 `anchor_classification_partial` 는
  T-71 이 red 로 잡지만, `:475` 는 `mutant_red = False` 가 되어 T-2 가 조용히
  red 로 바뀐다. 결과는 red 라 fail-closed 이므로 **위험 방향은 아니다** — 그래서
  MEDIUM 이다. 다만 red 의 원인이 "뮤테이션 미검출"로 오독된다.
- **recommendation**:
  `expected_partial = gates.classification_distribution(registry)[gates.PARTIAL]`
  를 뽑고 `mutant_red = len(ignoring_detected) == expected_partial` 로 바꾼다.
- **confidence**: 90

---

### S-6 (MEDIUM) `UNASSIGNED` 와 `NONE` 의 이름·값 교차 배선

- **dimension**: style / 네이밍
- **location**: `proto/register.py:18` 과 `proto/register.py:70`
- **finding**

  ```python
  # register.py:18
  UNASSIGNED = "미배정"          # ← 데이터 값 (레지스터 셀에 실제로 들어가는 문자열)
  ...
  # register.py:68-70
  EXACT = "EXACT"
  RANGE = "RANGE"
  NONE = "UNASSIGNED"            # ← 분류 태그 (classify_owner_track 의 반환값)
  ```

  `UNASSIGNED` 라는 이름이 붙은 상수의 값은 `"미배정"` 이고, `"UNASSIGNED"` 라는
  값을 가진 상수의 이름은 `NONE` 이다. 완전히 교차되어 있다. 사용처가 둘 다
  같은 함수 안이라 혼동이 실제로 일어난다:

  ```python
  # register.py:83-84
  if text == "" or text == UNASSIGNED:
      return NONE                # "UNASSIGNED" 를 반환하는데 이름은 NONE
  ```
  ```python
  # register.py:124
  if row.closable == "YES" and kind == NONE:
  ```

  더해서 `NONE` 은 Python 내장 `None` 과 시각적으로 1글자 차이라 `kind is None`
  오타가 조용히 `False` 가 된다. `EXACT` 는 `:109` 에서 반환만 되고 어떤 호출처도
  비교하지 않아 사실상 sentinel 이다 (`RANGE` 는 `:223` 에서, `NONE` 은 `:124` 에서
  실제 비교된다).

  docstring `:74` 은 `"owner_track 을 UNASSIGNED / EXACT / RANGE 로 분류한다"`
  라고 쓰는데, 코드에서 그 첫 항목의 **이름**은 `UNASSIGNED` 가 아니라 `NONE` 이다 —
  docstring 이 값을 말하고 코드가 이름을 말해서 grep 이 어긋난다.
- **recommendation**: 분류 태그를 `TRACK_UNASSIGNED = "UNASSIGNED"` 로,
  데이터 값을 `UNASSIGNED_CELL = "미배정"` 으로 개명한다. 또는 세 분류를
  `enum.StrEnum` 으로 올린다(값은 그대로 유지되어 앵커 무영향).
- **confidence**: 92

---

### S-7 (MEDIUM) `test_*.py` 라는 이름의 비-pytest 모듈 + import 시 전역 부작용

- **dimension**: style / 네이밍 · import 위생
- **location**: `tools/spikes/phase0_contract/test_contracts.py` (파일명), `:66`, `:70-71`
- **finding**: 파일명이 `test_contracts.py` 이고 docstring 첫 줄이
  `"pytest 없이 단독 실행한다"` 다. AST 전수 검사 결과 이 모듈에 `test_` 로
  시작하는 함수는 **0개**이며, 대조군 함수는 `t75_...`, `t2_...`, `self_check` 등이다.

  모듈 최상위에 import-time 전역 부작용이 있다:

  ```python
  # test_contracts.py:66
  sys.dont_write_bytecode = True  # .pyc 쓰기도 파일 쓰기다 (OD-3-C)
  # :70-71
  if str(_HERE) not in sys.path:
      sys.path.insert(0, str(_HERE))
  ```

  `sys.dont_write_bytecode` 는 **인터프리터 전역**이다. pytest 가 이 모듈을 수집하면
  그 세션의 나머지 전부가 .pyc 를 쓰지 않게 된다.

  현재는 안전하다 — `pyproject.toml:299 testpaths = ["tests"]` 가 기본 수집을
  `tests/` 로 한정한다(실측). 그러나 `pytest tools/`, `pytest --co .`,
  또는 누군가 `testpaths` 를 넓히는 순간 수집 대상이 된다. 이름이
  `test_*.py` 인 것이 그 사고를 **초대한다.**
- **recommendation**: `run_contracts.py` 또는 `contract_probe.py` 로 개명한다.
  단 `boundary.py:96 EXPECTED_RUNNER_RELPATH` 와 `config.yaml` 의 4개 digest 앵커가
  **전부 이 파일명·내용에 결속**되어 있으므로, 개명은 앵커 재계산을 동반한다 —
  비용이 실재하므로 "즉시 고쳐라"가 아니라 "D0 승격 시 반드시"로 제안한다.
  즉시 조치가 필요하면 최소한 `conftest.py` 에 `collect_ignore` 를 두거나
  `pyproject.toml` 에 `norecursedirs` 로 `tools/spikes` 를 못 박는다.
- **confidence**: 85

---

### S-8 (MEDIUM) 모듈 경계 넘어 private 함수 11곳 직접 호출

- **dimension**: style / 가독성 · API 위생
- **location**: `test_contracts.py` — 실측 전수:

  ```text
  390:    u11_problems = enforcement._check_u11(ctx)
  414:    base_t71 = enforcement._check_t71(enforcement.build_context(cfg))
  415:    promoted_t71 = enforcement._check_t71(ctx)
  974:    clean = enforcement._check_u8a(ctx)
  978:    mutant = enforcement._check_u8a(broken_ctx)
  1364:    clean = enforcement._check_t71(ctx)
  1366:    mutant = enforcement._check_t71(mutated_ctx)
  1404:    clean = enforcement._check_u10(ctx)
  1407:    mutant = enforcement._check_u10(ctx.replaced(report=stale))
  1422:    clean = enforcement._check_u9a(ctx)
  1424:    mutant = enforcement._check_u9a(mutated)
  ```
- **finding**: `_` 접두는 "모듈 밖에서 쓰지 말라"는 선언인데, 러너가 **주 소비자**다.
  이 12개 검사 함수(`enforcement.py:39-153`)는 `build_registry()` 를 통해 값으로
  공개되고 있으므로(`:156-171`), 접두사가 말하는 비공개성은 이미 사실이 아니다.

  실질 문제 두 가지:
  1. `_check_t76` 은 `getattr(enforcement, "_check_t76", None)` (`:1210`) 로
     **문자열 조회**한다 — private 이름을 문자열로 잡는 것은 리네임에 취약하고,
     이름이 사라져도 `None` 분기로 흘러 "검사 함수 존재=False" 라는 red 는 나오지만
     원인이 리네임인지 삭제인지 구분되지 않는다.
  2. `t76_level_raw_anchor` 는 registry 조회(`reg["T-76"]`)와 속성 조회
     (`getattr(enforcement, "_check_t76")`)를 **둘 다** 하는데(`:1209-1211`),
     둘은 같은 객체다. 한쪽만으로 충분하다.
- **recommendation**: 검사 함수를 `check_u11` 등 공개 이름으로 올리거나
  (`register.py` 는 이미 `check_u1a`·`check_u4` 등 **공개** 이름을 쓴다 — 두 모듈의
  규약이 어긋나 있다), 러너가 `enforcement.build_registry()[key](ctx)` 로 일관
  접근한다. 후자가 T-39 의 "우주 = 레지스트리 키" 원칙과 정합적이다.
- **confidence**: 90

---

### S-9 (MEDIUM) 같은 토큰을 독립 리터럴 쌍 2개로 조립 (DRY)

- **dimension**: style / DRY
- **location**: `proto/boundary.py:49` 와 `proto/boundary.py:59`
- **finding**

  ```python
  # boundary.py:49-50
  _CORPUS_DIR = "tos-" + "spec/"
  _REGISTER_PREFIX = "EVIDENCE-" + "REGISTER-"
  ...
  # boundary.py:59-60
  _SPEC = "tos-" + "spec"
  _VERIFICATION = f"{_SPEC}/src/verification"
  ...
  # boundary.py:80
  _CORPUS_DIRNAME = _CORPUS_DIR.rstrip("/")
  ```

  `_SPEC` 과 `_CORPUS_DIRNAME` 은 **같은 값** `"tos-spec"` 인데 서로 다른 리터럴
  쌍에서 독립적으로 조립된다. `:78-79` 주석은

  > `FORBIDDEN_SOURCE_TOKENS` 와 같은 조각에서 파생하므로 둘이 따로 놀 수 없다.

  라고 쓰는데, 이 보증은 `_CORPUS_DIRNAME` (→ 열람 가드)에만 성립한다.
  `FORBIDDEN_ARTIFACTS` (OD-3-B, `:63-69`)는 `_SPEC`/`_VERIFICATION` 을 거치므로
  **그 보증 밖**이다. 주석이 거짓은 아니지만 독자는 파일 전체에 적용된다고 읽는다.

  조각 분할이 필요한 이유(검사기 자기 스캔 회피)는 `:32-34` 가 설명하지만,
  그 이유는 조각 쌍이 **하나**여야 함을 함의한다 — 둘이면 동기화 부담만 두 배다.
- **recommendation**: `_SPEC = _CORPUS_DIR.rstrip("/")` 로 파생시키고 `:59` 의
  독립 리터럴 쌍을 제거한다. `TOKEN_DEFINITION_NAMES` (`:74-76`) 에서 `_SPEC` 을
  빼도 되는지는 AST 면제 대조군(`test_contracts.py:736-742` 의 `mutant_narrow`)이
  판정하므로 회귀는 관측된다.
- **confidence**: 85

---

### S-10 (MEDIUM) 한 함수 안에서 같은 이름을 두 타입으로 재사용

- **dimension**: style / 가독성
- **location**: `test_contracts.py:1636` 과 `test_contracts.py:1646`
- **finding**

  ```python
  # main() 내부, :1634-1640
  index = rep.case_index()
  for found in rep.defects:
      bound = index.get(found.tid)          # :1636  → Case | None
      state = ("Case 없음" if bound is None else ("red" if not bound.ok else "GREEN"))
  ...
  # 같은 함수, :1645-1651
  for limit in rep.limits:
      bound = ""                            # :1646  → str
      if limit.case is not None:
          bound = f" [case={limit.case}]"   # :1648
      if limit.unchk is not None:
          bound += f" [unchk={limit.unchk}]"  # :1650
  ```

  `bound` 가 앞 루프에서 `Case | None`, 뒤 루프에서 표시 문자열이다. mypy 가 4건으로
  잡는다 (`:1646 assignment`, `:1648 assignment`, `:1650 operator` ×2). 런타임에는
  루프가 분리되어 있어 문제가 없지만, 두 루프가 24줄 간격이라 읽는 사람이
  같은 개념으로 착각한다 — 실제로 뒤쪽 `bound` 는 "Case 결속"이 아니라 "표시 접미"다.
- **recommendation**: 뒤쪽을 `suffix` 로 개명한다. `main()` 은 표시 함수이므로
  앵커(`case_prose_anchor`)는 `Case.detail` 만 해시하고 `main()` 출력은
  해시 대상이 아니다 — 앵커 무영향이다.
- **confidence**: 95

---

### S-11 (LOW) black 위반 2건

- **dimension**: style / 포매팅
- **location**: `proto/boundary.py:341` (89자) · `test_contracts.py:202` (91자)
- **finding**: §1.2 verbatim diff 참조. 둘 다 내용 변경 없는 줄바꿈이다.
- **severity 를 LOW 로 두는 근거 (실측)**:
  - CI `lint` 잡은 잡·스텝 양쪽 `continue-on-error: true` — 차단하지 않는다 (§1.4).
  - repo 베이스라인이 이미 **399/2320 (17.2%)** 위반이다 — 이 2건은 회귀가 아니다.
  - §1.5 실측대로 교정해도 `config.yaml` 앵커 4개가 전부 불변이므로 **비용이 0에
    가깝다** — 즉 "고치기 어려워서 남은 것"이 아니라 "돌린 적이 없어서 남은 것"이다.
- **recommendation**: `black tools/spikes/phase0_contract/` 1회 실행.
  §1.5 가 앵커 불변을 실측했으므로 `config.yaml` 은 건드리지 않는다.
- **confidence**: 99

---

### S-12 (LOW) digest 절단 자리수가 무명 인라인 리터럴이고 불일치한다

- **dimension**: style / 매직넘버
- **location**: `test_contracts.py:255, 258, 277, 352, 374`
- **finding**

  ```text
  255:        digest = hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()[:12]
  258:    combined = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
  277:    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
  352:    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
  374:    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
  ```

  `[:12]` 가 1곳, `[:16]` 이 4곳. `:255` 만 12인 이유는 그것이 **노트별 중간 digest**
  이고 `:258` 이 그것들을 다시 묶기 때문으로 보이지만, 어디에도 적혀 있지 않다.
  독자는 오타인지 의도인지 구분할 수 없다.
- **설정으로 옮겨야 하는가 — 판단 근거**: **옮기지 않는 편이 낫다.** 이유:
  자리수는 CLAUDE.md 가 열거한 "thresholds / risk values / ports / schedules"
  어디에도 해당하지 않는 **알고리즘 상수**이고, 설정으로 옮기면 자리수를 줄여
  충돌 저항을 낮추는 편집이 `config.yaml` 한 줄로 가능해진다 — 앵커 강도를
  설정 표면에 노출하는 것은 이 프로토타입의 위협 모델에서 **역방향**이다.
  (반면 앵커 **값**이 설정에 있는 것은 옳다 — 값 변경은 diff 로 드러나야 한다.)
- **recommendation**: 설정 이동이 아니라 **명명**이다. python-backend 규칙
  "Constants in UPPER_SNAKE_CASE at module level" 에 따라
  `_NOTE_DIGEST_CHARS = 12` · `_ANCHOR_DIGEST_CHARS = 16` 을 모듈 최상위에 두고,
  둘이 다른 이유를 한 줄 주석으로 적는다. 값이 그대로이므로 앵커 무영향
  (단 `co_consts` 에 정수 상수는 들어가지만 `_code_prose` 는 `isinstance(const, str)`
  만 수집하므로 — `test_contracts.py:285` — digest 불변이다).
- **confidence**: 90

---

### S-13 (LOW) `replaced(**changes: object)` 가 mypy 오류 7건의 단일 발생원

- **dimension**: style / 타입 힌트
- **location**: `proto/enforcement.py:29-30`
- **finding**

  ```python
  def replaced(self, **changes: object) -> Context:
      return replace(self, **changes)
  ```

  `**changes: object` 는 `dataclasses.replace` 의 필드별 타입과 맞지 않아 mypy 가
  **한 줄에서 7건**을 낸다 (§1.3 의 `enforcement.py:30` ×7). 대상 파일 mypy 오류
  61건 중 11%가 이 한 줄이다.

  런타임 위험은 없다 — `Context` 가 `frozen=True` 이고 `replace` 가 필드명을 검증한다.
  다만 호출처(`test_contracts.py:1407 ctx.replaced(report=stale)`,
  `enforcement.py:294 partial_ctx.replaced(evaluation=...)`)에서 **타입 검사가
  전혀 걸리지 않는다** — `ctx.replaced(report="틀린타입")` 이 통과한다.
- **recommendation**: 실무적으로는 `# type: ignore[arg-type]` 한 줄 + 사유 주석,
  또는 사용처가 2곳뿐이므로 `replaced` 를 없애고 호출처에서
  `dataclasses.replace(ctx, report=stale)` 를 직접 쓴다. 후자면 mypy 가 필드
  타입을 실제로 검사한다.
- **confidence**: 93

---

### S-14 (LOW) 공개 표면 docstring 누락 — 형제 심볼과 불일치

- **dimension**: style / docstring
- **location** (AST 전수 검사 결과 중 **공개 표면**만 발췌):

  | 위치 | 심볼 | 형제 대조 |
  | --- | --- | --- |
  | `test_contracts.py:127` | `class Report` | `Case`(:94) · `Defect`(:109) · `Limit`(:117) 는 전부 있다 |
  | `test_contracts.py:135` | `Report.add` | 같은 클래스의 `defect`(:139) · `limit`(:151) 는 있다 |
  | `test_contracts.py:155` | `Report.case_index` | 인접 `unbound_defects`(:158) 등 6개는 전부 있다 |
  | `test_contracts.py:1579` | `run_all` | 공개 진입점 |
  | `test_contracts.py:1606` | `main` | 공개 진입점 (주석은 있으나 docstring 아님) |
  | `proto/enforcement.py:34` | `class Finding` | 같은 파일 `Context`(:18) 는 있다 |
  | `proto/enforcement.py:29` | `Context.replaced` | 공개 메서드 |
  | `proto/boundary.py:482` | `_is_write_mode` | private 이나 판정 로직 보유 |

  파일별 누락 총계 (지역 클로저·property 포함):
  `test_contracts.py` 7 · `boundary.py` 23 · `enforcement.py` 10 · `gates.py` 1 ·
  `floor.py` 0 · `register.py` 0 · `config.py` 0.

  `boundary.py` 의 23건 중 20건은 `read_guard`/`write_guard` 내부의 지역 클로저
  (`guarded_open` 등)이며, **지적하지 않는다** — 지역 함수이고 감싸는 context
  manager 의 docstring 이 범위를 충분히 설명한다.
  `enforcement.py` 의 10건 중 8건은 `_check_u1a`~`_check_u10` 의 1줄 위임 함수로,
  위임 대상(`register.check_u1a` 등)이 docstring 을 갖는다 — 역시 약하게만 지적한다.
- **finding 요지**: 절대량이 아니라 **불일치**다. `floor.py`·`register.py`·
  `config.py` 는 누락 0으로 규율이 완벽한데 같은 패키지의 다른 파일이 새고,
  한 클래스 안에서 3개 메서드는 있고 2개는 없다.
- **recommendation**: 위 표의 8개 공개 심볼에만 1줄 docstring 을 추가한다.
  Report 클래스는 특히 — 이 파일의 핵심 자료구조이고 `anchors` 필드(:133)만
  주석으로 설명되어 있다.
- **confidence**: 95

---

### S-15 (LOW) Google style 섹션(`Args:`/`Returns:`/`Raises:`) 0건

- **dimension**: style / docstring
- **location**: 대상 7개 파일 전부
- **finding**: `.github/instructions/python-backend.instructions.md:19` 는
  "Docstrings on all public functions and classes (**Google style**)" 을 요구한다.
  대상 파일에는 `Args:` / `Returns:` / `Raises:` 섹션이 **하나도 없다.**

  repo 실측 비교:

  | 대상 | `Args:` 사용 파일 | 전체 | 비율 |
  | --- | ---: | ---: | ---: |
  | `shared/` | 154 | 450 | 34% |
  | `tools/` | 2 | 24 | 8% |
  | 이 프로토타입 | 0 | 7 | 0% |
- **판단**: 형식 위반은 맞지만 **실익이 낮다.** 이 파일들의 docstring 은 오히려
  repo 평균보다 훨씬 정보 밀도가 높다 — `boundary.py:20-34` 는 v2.3 우회가 뚫린
  경위와 v2.5 의 강제 지점 이동을 15줄로 설명하고, `config.yaml:49-61` 은 4차→5차
  교정의 근거를 담는다. `Args: sources (Mapping[str, str]): 소스 맵.` 같은 boilerplate
  를 추가하는 것은 타입 힌트와 중복이며 정보를 늘리지 않는다.
  게다가 `tools/` 의 기존 관행(8%)과는 오히려 정합적이다.
- **recommendation**: 전면 개조를 권하지 않는다. 다만 **`Raises:` 만은 값이 있다** —
  이 코드베이스는 fail-closed 규율상 예외 발생이 계약의 일부다
  (`ConfigError`·`OwnerTrackSyntaxError`·`LevelSyntaxError`·`ProfileDependentError`·
  `BoundaryViolation`·`EvaluationError` 6종). 예외를 던지는 공개 함수
  (`config.load_config`·`cfg_int`·`cfg_list`·`cfg_pairs`,
  `register.classify_owner_track`, `floor.parse_levels`·`floor.floor`)에
  `Raises:` 섹션 추가를 제안한다. 산문 본문에 이미 서술은 있으나 기계 판독이 안 된다.
- **confidence**: 95

---

### S-16 (LOW) 죽은 상수 `SURFACE_KINDS`

- **dimension**: style / 죽은 코드
- **location**: `proto/floor.py:20`
- **finding**

  ```python
  SURFACE_KINDS = frozenset({PACKAGE, TEST, REVIEWER, FAULT, RUNTIME})
  ```

  전 디렉터리 grep 결과 **정의 1건 외 참조 0건**:

  ```console
  $ grep -rn "SURFACE_KINDS" --include="*.py" .
  proto/floor.py:20:SURFACE_KINDS = frozenset({PACKAGE, TEST, REVIEWER, FAULT, RUNTIME})
  ```

  바로 아래 `VERIFIABLE_KINDS`(:23)는 `countable_kinds`(:94)가 실제로 쓴다.
  `SURFACE_KINDS` 는 "표면 kind 5종의 우주"를 선언하지만 아무도 검증에 쓰지 않는다 —
  `EvidenceRow.required_kinds` 가 이 집합 안에 있는지 확인하는 코드가 없다.
  (그것이 결함인지는 계약 정합성 렌즈 소관이다. 스타일 렌즈에서는 "선언되고
  소비되지 않는 상수"로만 보고한다.)
- **recommendation**: 삭제하거나, `EvidenceRow` 생성/파싱 지점에서
  `required_kinds <= SURFACE_KINDS` 검증에 실제로 쓴다. `_code_prose` 가
  문자열 상수만 모으고 `frozenset` 은 `co_consts` 에 str 로 안 들어가므로
  삭제해도 `anchor_runner_source_digest` 는 불변일 가능성이 높다 — 다만
  **미실측**이므로 교정 시 재계산 확인이 필요하다.
- **confidence**: 99

---

### S-17 (LOW) black 도 못 쪼개는 중첩 f-string 4줄 (101~105자)

- **dimension**: style / 가독성
- **location**: `test_contracts.py:1532-1535`
- **finding**

  ```python
  rep.anchors = {
      "리터럴": f"{actual_digest}{'' if actual_digest == expected_digest else f'!={expected_digest}'}",
      "방출": f"{actual_emitted}{'' if actual_emitted == expected_emitted else f'!={expected_emitted}'}",
      "Case산문": f"{actual_prose}{'' if actual_prose == expected_prose else f'!={expected_prose}'}",
      "실행코드": f"{actual_source}{'' if actual_source == expected_source else f'!={expected_source}'}",
  }
  ```

  실측 길이: 102 · 105 · 101 · 103자 (line-length 88). black 은 f-string 내부
  중첩 f-string + 조건식을 분해하지 못해 `--check` 통과하지만, 읽기는 어렵다.
  4줄이 동일 패턴의 복붙이라 `expected_prose` 자리에 `expected_emitted` 를 넣는
  복붙 오류가 눈에 띄지 않는다.

  대상 파일 전체의 88자 초과 실측:
  `test_contracts.py` 5건(202, 1532-1535) · `boundary.py` 1건(341) ·
  나머지 5개 파일 **0건**.
- **recommendation**: 헬퍼로 추출한다.

  ```python
  def _anchor_cell(actual: str, expected: str) -> str:
      return actual if actual == expected else f"{actual}!={expected}"
  ```

  네 항목이 `_anchor_cell(actual_digest, expected_digest)` 형태가 되어 복붙 오류가
  드러난다. **주의**: 이 변경은 `co_consts` 의 문자열 구성을 바꾸므로
  `anchor_runner_source_digest` 갱신이 필요하다 — S-11/S-12 와 달리 앵커 비용이 있다.
- **confidence**: 90

---

### S-18 (LOW) 숫자 접미 변수명

- **dimension**: style / 네이밍
- **location**: `test_contracts.py:799`, `:859`
- **finding**

  ```text
  779:    with boundary.write_guard() as recorder:      # clean 방향
  799:    with boundary.write_guard() as recorder2:     # 프로브 방향
  843:    with boundary.read_guard() as read_rec:       # clean 방향
  859:    with boundary.read_guard() as read_rec2:      # 조립 우회 방향
  ```

  `recorder`/`recorder2`, `read_rec`/`read_rec2` 는 "무엇이 다른가"를 이름이
  말하지 않는다. 실제로는 **양방향 대조군의 방향① 과 방향②** 라는 이 파일의
  핵심 개념이고, 파일 전체가 `clean_*` / `mutant_*` 접두로 그 구분을 표현한다
  (`clean_scan`/`mutant_scan`, `clean_ast`/`mutant_ast`, `clean_write_ok`, ...).
  가드 recorder 만 그 규약에서 벗어났다.
- **recommendation**: `clean_recorder` / `probe_recorder`,
  `clean_read_rec` / `assembled_read_rec` 로 개명해 파일 규약에 맞춘다.
  지역 변수명은 `co_varnames` 이고 `_code_prose` 는 `co_name` + str `co_consts`
  만 모으므로 — `test_contracts.py:283-288` — **앵커 무영향**이다.
- **confidence**: 88

---

### S-19 (LOW) `Report.add` 반환값을 아무도 쓰지 않는다

- **dimension**: style / 죽은 코드
- **location**: `test_contracts.py:135-137`
- **finding**

  ```python
  def add(self, case: Case) -> Case:
      self.cases.append(case)
      return case
  ```

  grep 결과 `= rep.add(` · `= probe.add(` 형태의 호출 **0건**. 전 호출처가
  `rep.add(Case(...))` 로 반환을 버린다. 반환 타입이 fluent 사용을 암시하지만
  실제 사용 패턴이 없다.
- **recommendation**: `-> None` 로 바꾸거나 그대로 두되 의도(체이닝 여지)를
  docstring 에 적는다 — S-14 가 이 메서드의 docstring 누락을 이미 지적한다.
- **confidence**: 96

---

### S-20 (LOW) 표시·판정 문자열의 `11` · `4` 리터럴

- **dimension**: style / 매직넘버
- **location**: `test_contracts.py:406, 483-485, 1094, 1455`
- **finding**

  ```text
  406:            f"11/11 MET={all_met} verdict={ctx.evaluation.verdict} "
  483:            f"basis 관측 {len(observable_by_basis)}/11 · "
  484:            f"value 관측 {len(observable_by_value)}/11 · "
  485:            f"구성 불가(NMC) {len(unconstructible)}/11 · 실패 {failures}",
  1094:            len(moved) == 4 and not cross_talk,
  1455:            aborted == 4,
  ```

  - `11` 4건: 술어 총수. `len(gates.predicate_domain(registry))` 로 파생 가능.
    분모만 고정이라 술어가 12개로 늘면 `"12/11"` 같은 출력이 나온다.
  - `:1094` 의 `4`: `len(register.REQUIRED_METRICS)` (= `:1083` 이 바로 위에서
    참조하는 그 튜플). 파생 가능.
  - `:1455` 의 `4`: `:1440` 의 지역 튜플 `("EV-L9","EV-L","언젠가","")` 길이.
    튜플을 변수로 뽑으면 `len(bad_levels)` 로 파생 가능하고, 같은 함수의
    `:622,630` (`len(accepted_positive) == len(positives)`)이 이미 그 패턴을 쓴다.
- **severity 근거**: `11` 은 표시 문자열이므로 판정에 영향 없음. `4` 두 건은
  판정식이지만 어긋나면 red 방향(fail-closed)이다. S-5 와 같은 결함 클래스이나
  영향이 더 작아 LOW 로 분리했다.
- **recommendation**: `4` 두 건은 파생으로 바꾼다(값 불변이므로 `co_consts` 의
  정수만 바뀌고 `_code_prose` 는 str 만 모으므로 앵커 무영향). `11` 은 표시
  문자열 안이라 바꾸면 `co_consts` 문자열이 바뀌어 앵커 갱신이 필요하다 —
  D0 승격 시로 미루는 것이 합리적이다.
- **confidence**: 80

---

### S-21 (LOW) `from . import X` 와 `from .X import y` 혼용

- **dimension**: style / import 위생
- **location**: `proto/enforcement.py:12-14`, `proto/register.py:14-16`
- **finding**

  ```python
  # enforcement.py:12-14
  from . import floor, gates, register
  from .config import cfg_int, cfg_list, cfg_pairs
  from .floor import EvidenceRow, fwd_a_0_failures     # ← floor 를 두 방식으로 import
  ```
  ```python
  # register.py:14-16
  from . import gates
  from .config import cfg_int, cfg_list
  from .floor import EvidenceRow, superset_declared_pairs
  ```

  `enforcement.py` 는 `floor` 를 모듈로도(`:12`) 심볼로도(`:14`) 가져온다.
  본문에서 `floor.LEVEL_KINDS`(:139)와 `fwd_a_0_failures`(:152)가 섞여 쓰인다.
  ruff `I`(isort)는 통과한다 — 정렬 문제가 아니라 **일관성** 문제다.
- **판단**: `gates`·`register` 는 모듈 접근만, `config` 는 심볼만 — 각각은 일관되다.
  `floor` 만 혼용이고, `EvidenceRow` 를 심볼로 뽑은 이유는 타입 힌트에서
  `floor.EvidenceRow` 를 반복하지 않으려는 것으로 보인다. 정당한 이유가 있으므로
  **약한 지적**이다. nitpick 경계선에 있으나, 리뷰어가 `floor.fwd_a_0_failures` 를
  찾을 때 grep 이 어긋나므로 기록한다.
- **recommendation**: 조치 불요 판단도 합리적이다. 통일한다면 `floor` 도
  모듈 접근으로 일원화하고 `EvidenceRow` 만 심볼로 남긴다(타입 힌트 가독성).
- **confidence**: 75

---

## 5. 감사 방법 · 한계 (이 증거의 범위)

**수행한 것**
- `ruff check` · `black --check --diff` · `mypy --ignore-missing-imports` 를 repo
  루트에서 대상 경로 지정으로 **실제 실행**하고 전체 출력을 §1 에 verbatim 첨부.
- CI 게이팅 여부를 `.github/workflows/test.yml` 실측으로 확인하고 severity 근거로 사용.
- repo 전체 black 베이스라인을 git-tracked 2,320 파일 전수로 실측(399 위반).
- docstring 누락은 육안이 아니라 `ast.get_docstring` 전수 검사로 산출.
- 죽은 코드 후보 14개 심볼을 grep 전수 대조(정의 건수 vs 참조 건수).
- black 교정의 앵커 영향을 스크래치 사본에서 **실행 검증**하고, 재구현 digest 가
  `config.yaml:33` 의 커밋된 값과 일치함을 교차 확인(§1.5).

**하지 않은 것 / 한계**
- **러너를 실행하지 않았다.** 지시가 읽기 전용이었고, 21개 대조군의 red/green
  실측은 계약 정합성 렌즈 소관이다. 따라서 `config.yaml` 의 4개 digest 앵커가
  **현재 코드와 실제로 일치하는지는 이 증거가 말하지 않는다.**
  (§1.5 에서 `anchor_limit_text_digest` 1개만 우연히 교차 확인됐다 — 일치했다.)
- **diff 기준선이 없다.** 대상 전체가 untracked 이므로 "변경 라인 집중 vs 기존
  위반" 분리가 불가능하다. 모든 발견을 신규로 취급했다.
- `blocks_gate_consumption.py` · `sweep_deprecated_vocabulary.py` 는 지시된
  범위 밖이라 감사하지 않았다 (mypy 출력에서만 분리 표기).
- **앵커 영향 표기의 신뢰도 차이**: S-11/S-12/S-18 의 "앵커 무영향"은
  `_code_prose` 가 str `co_consts` 만 수집한다는 코드 근거(`:283-288`) + §1.5
  실측에 기반한다. S-16 의 "불변일 가능성이 높다"는 **미실측 추정**이며 그렇게 표기했다.
  S-3/S-17/S-20(`11`)은 앵커 갱신이 **필요하다**고 명시했다.
- 성능·보안·아키텍처 축은 이 렌즈 밖이다. 특히 `SURFACE_KINDS` 미소비(S-16)와
  `_SPEC` 이중 조립(S-9)이 **계약상 결함인지**는 판단하지 않았다 — 스타일
  관측만 제출한다.

---

## 6. 종합 (판정 아님)

- **도구 3종 중 ruff 는 완전 통과**, black 은 2건(줄바꿈만), mypy 는 61건.
  mypy 61건 중 **42건(69%)이 단일 원인** — `no-untyped-def`, 그 중 21건이
  `cfg` 파라미터 하나다.
- **CLAUDE.md 비협상 "No Hardcoding" 의 핵심 축은 지켜지고 있다.** 임계값
  (`owner_track_range_max_width`·`phase_min`·`phase_max`)과 앵커 9개가 전부
  `config.yaml` 에 있고, 하드코딩 회귀를 러너가 `T-62-cfg` Case 로 자기 감시한다.
  남은 하드코딩 지적(S-3·S-4·S-5·S-12·S-20)은 **주변부**이며, 그 중 S-12 는
  설정 이동을 오히려 반대한다.
- **스타일 렌즈가 계약 정합성에 대해 말할 수 있는 것은 S-1 하나다** — 앵커 계산
  경로 함수의 타입 선언이 실제 자료구조와 다르고, 그것은 이 프로토타입이 반복해서
  다뤄온 "선언층/평가층 간극" 결함 클래스와 같은 종류다. 나머지 20건은 위생이다.
- 교정 비용 관점: **S-11·S-12·S-18·S-2·S-1·S-10 은 `config.yaml` 무편집으로
  교정 가능**하다(§1.5 실측 근거). S-3·S-17·S-20(부분)·S-7 은 앵커 재계산을
  동반하므로 묶어서 처리하는 편이 낫다.

*— style-auditor, 2026-08-13*
