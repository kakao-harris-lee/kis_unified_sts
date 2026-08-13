# evidence — security lens · `tools/spikes/phase0_contract/`

```yaml
lens: security
scope: tools/spikes/phase0_contract/{proto/boundary.py, test_contracts.py, proto/config.py, proto/config.yaml}
baseline_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
prior_verdict: .omc/review/20260812-231234/verdict.md (v2.3, needs-attention)
runtime: Python 3.14.5 · darwin 25.5.0 · APFS 대소문자 무시(실측)
verdict: 없음 — 이 문서는 증거다.  판정은 Codex 심판 레인 소관.
findings: 11 (critical 1 / high 5 / medium 3 / low 2)
poc_dir: /private/tmp/claude-503/.../scratchpad/poc/
prototype_modified: NO (repo 내 프로토타입 무편집 · 뮤테이션은 전부 scratchpad 사본)
```

## 기준선 (실측)

```
$ python3 tools/spikes/phase0_contract/test_contracts.py
대조군 30건 중 양방향 성립 30건
OD-3-C 파일 쓰기 시도 기록: 없음
OD-3-A 코퍼스·register 열람 시도 기록: 없음
산문 앵커 대조: 리터럴=5efb40f2c1962a30 · 방출=cada1899362b330b ·
               Case산문=a43e14b843e49a4e · 실행코드=f4ea9b8f2d77b472
EXIT=0
```

**앵커 진본성 — 독립 재계산 (러너 밖 구현):**

```
anchor_limit_text_digest  커밋값=5efb40f2c1962a30  독립계산=5efb40f2c1962a30  일치
  묶인 노트 15개 · declared_limit_ids 11개
  차이 4개(L-BYPASS-1/2/3, L-PROBE) = SELF-1 프로브 픽스처 — 정당한 제외
```

앵커 값 자체는 **진본이다**. 이하의 지적은 값의 위조가 아니라 **앵커가 덮는 표면**에 관한 것이다.

---

## S-1 · CRITICAL — OD-3-A 완전 우회 실증: 코퍼스를 읽으면서 30/30 GREEN · 앵커 4종 불변 · exit 0

- **location**: `proto/boundary.py:83-92` (`READ_GUARDED_ENTRY_POINTS`) + `test_contracts.py:291-315` (`_module_code_parts`)
- **유형**: CWE-693 Protection Mechanism Failure (보호기제 우회) / 불완전 블랙리스트
- **confidence**: 100 (실측)

심판 v2.3 F3 이 경고한 시나리오 — "프로토타입이 실 코퍼스에 접근하면서 T-77 이 OD-3-A 를
clean 으로 보고할 수 있다" — 가 v2.5 의 런타임 열람 가드 도입 **이후에도 그대로 성립한다.**

scratchpad 사본의 `proto/register.py` 말미에 **모듈 레벨 문장만으로** 실 register 열람을 주입:

```python
_x3 = bytes([116,111,115,45,115,112,101,99]).decode()          # 접히지 않는 조립
_x4 = bytes([69,86,73,68,69,78,67,69,45,...]).decode()
_x5 = _x2.sep.join(("/Users/.../kis_unified_sts", _x3, "src",
                    "part-1-foundation", "verification", _x4))
_x6 = _x1.open(_x5, "r", encoding="utf-8")                     # _x1 = _io  (미가드)
EXFILTRATED = _x6.read()
```

실행 결과:

```
EXIT = 0
발견 — 관측된 계약 위반 0건
대조군 30건 중 양방향 성립 30건
OD-3-C 파일 쓰기 시도 기록: 없음
OD-3-A 코퍼스·register 열람 시도 기록: 없음                     <-- 열람이 기록되지 않았다
산문 앵커 대조: 리터럴=5efb40f2c1962a30 · 방출=cada1899362b330b ·
               Case산문=a43e14b843e49a4e · 실행코드=f4ea9b8f2d77b472   <-- 4종 전부 기준선과 동일

탈취된 register 바이트 : 93865
탈취된 첫 줄          : evidence_id,domain,title,primary_adr,criticality,minimum_evidence_level,...
탈취된 데이터 행 수     : 372
```

두 결함의 **합성**이다 — 어느 하나만 고쳐도 성립하지 않는다:
① 열람이 `_io.open`(미가드 진입점)을 지나 가드가 관측하지 못한다 (S-2)
② 주입 코드가 **모듈 레벨**이라 `실행코드` 앵커의 대상이 아니다 (S-6)

`boundary.py:27-28` 의 "v2.5 는 강제를 열람 시점의 경로 값으로 옮긴다 … 제시된 3종 우회가
전부 red 가 된다"는 **제시된 3종에 한해서만** 참이다. 강제 지점이 경로 값으로 옮겨졌어도
**그 지점을 지나지 않는 열람 경로**가 남아 있다.

- **recommendation**: 열거(allowlist-of-hooks) 방식으로는 닫히지 않는다.
  (a) `sys.addaudithook` 의 `open`/`os.open`/`exec`/`subprocess.Popen` 이벤트로 강제를 옮기면
  `_io`·C 확장·`subprocess` 가 한 지점에서 관측된다(진입점 열거 불필요).
  (b) 앵커 대상을 로드된 코드 객체가 아니라 **import 된 모듈 소스의 바이트**(`__loader__.get_data`)로
  잡아 모듈 레벨·docstring·데이터를 전부 포함시킨다.
  (c) 최소한 두 결함 각각에 **대조군 Case** 를 붙여 회귀를 관측 가능하게 한다.

---

## S-2 · HIGH — `READ_GUARDED_ENTRY_POINTS` 가 불충분: 18개 경로 중 12개가 실제 코퍼스를 읽어냈다

- **location**: `proto/boundary.py:83-92`, `proto/boundary.py:518-566`
- **유형**: CWE-184 Incomplete List of Disallowed Inputs
- **confidence**: 100 (실측)

PoC-1 (`poc/poc1_read_guard_bypass.py`) — `read_guard()` 활성 상태에서 각 경로가 실제 바이트를
반환하면 BYPASS:

```
판정        진입점                                      결과(선두 70자)
BYPASS    _io.open (builtins.open 의 실체 모듈)         evidence_id,domain,title,primary_adr,...
BYPASS    io.FileIO                                evidence_id,domain,title,primary_adr,...
BYPASS    io.open_code                             evidence_id,domain,title,primary_adr,...
BYPASS    tokenize.open                            evidence_id,domain,title,primary_adr,...
BYPASS    linecache.getlines                       # Preface\n\nThis is the front door to the TOS
BYPASS    가드 진입 전 바인딩된 open                        evidence_id,...
BYPASS    subprocess.run(cat)                      evidence_id,...
BYPASS    os.popen                                 evidence_id,...
BYPASS    mmap (FileIO fd)                         evidence_id,...
BYPASS    os.pread (FileIO fd)                     evidence_id,...
BYPASS    importlib SourceFileLoader.get_data      # Preface\n\n...
BYPASS    register 파일명 대소문자                        evidence_id,...
BLOCKED   Path.glob / Path.iterdir / os.walk       (os.scandir 경유 — 정상 차단)
BLOCKED   codecs.open / fileinput.input            (builtins.open 경유 — 정상 차단)
BLOCKED   경로 대소문자 변형 (TOS-SPEC)                    (파일명 접두 분기가 잡음 — S-3 참조)
----
BYPASS 12/18 · read_guard 기록된 차단 시도: 6건
```

**고지된 한계와 구분한다** (`test_contracts.py:911-918` L-READ-SCOPE):
`subprocess`·`os.popen`·가드 진입 전 바인딩·이미 열린 fd(`mmap`/`os.pread` 의 배후)는
**고지 범위 안**이다 — 이 4종은 지적이 아니다.

**고지 밖**은 다음 5종이며, 전부 호출 시점에 **경로 문자열을 인자로 받는 평범한 표준 라이브러리
진입점** — 즉 가드가 강제한다고 주장하는 바로 그 도메인이다:

| 진입점 | 성질 |
|---|---|
| `_io.open` | **`builtins.open` 과 동일 객체**. 실측: `builtins.open is io.open is _io.open` → `True` |
| `io.FileIO` | 클래스 생성자. 경로 인자 |
| `io.open_code` | 경로 인자 |
| `tokenize.open` | import 시점에 `builtins.open` 을 `_builtin_open` 으로 캡처 → 사후 패치 무효 |
| `importlib.machinery.SourceFileLoader.get_data` | 경로 인자 |
| `linecache.getlines` | `tokenize.open` 경유 |

특히 `_io.open` 은 **목록이 같은 함수를 `builtins.open`·`io.open` 두 이름으로 열거해 놓고
세 번째 이름을 빠뜨린 것**이다. 이것은 범위 고지가 아니라 목록의 오류다.

- **recommendation**: `sys.addaudithook`(`open` 이벤트는 `_io`·`io.FileIO`·`os.open`·
  `importlib` 을 단일 지점에서 관측한다)로 이동. 열거를 유지한다면 최소한 `_io` 모듈 자체,
  `io.FileIO`, `io.open_code`, `tokenize._builtin_open` 을 추가하고, **목록의 충분성을
  관측하는 대조군**(현 T-77-①-READ 는 고지된 진입점만 프로브한다)을 추가한다.

---

## S-3 · HIGH — `read_violation()` 이 경로 대소문자를 정규화하지 않는다 — 대소문자 무시 FS(현 개발기)에서 정본 진입점으로도 통과

- **location**: `proto/boundary.py:431-434`
- **유형**: CWE-178 Improper Handling of Case Sensitivity / CWE-41 Path Equivalence
- **confidence**: 100 (실측)

```python
if _CORPUS_DIRNAME in resolved.parts:      # :431  대소문자 정확 일치
if resolved.name.startswith(_REGISTER_PREFIX):   # :433  대소문자 정확 일치
```

실측 (PoC-2):

```
os.path.exists('.../TOS-SPEC/src/preface.md')     = True
samefile(tos-spec, TOS-SPEC)                      = True     <- 대소문자 무시 FS
Path.resolve() 가 케이스를 정규화하는가             : .../TOS-SPEC/src/preface.md   <- 아니오

read_violation() 순수 판정:
  정본 경로               -> 차단
  디렉터리 대문자           -> **통과**
  디렉터리 혼합 케이스        -> **통과**
  register 케이스변형       -> **통과**

read_guard 아래 실제 열람 (Path.read_text — 목록에 있는 정본 진입점):
  판정: **BYPASS** — 코퍼스 4018바이트 획득 / 내용: "# Preface"
  기록된 차단 시도: 0건
```

이 우회는 **진입점 목록과 무관하다.** 가드가 감싸는 `Path.read_text`·`builtins.open` 을 그대로
쓰는데도 판정 술어가 통과시킨다. `boundary.py:8` 이 "해석된 경로 **값**을 I/O 시점에 판정한다 …
문자열을 어떻게 조립했는지와 **무관**하다"고 적은 그 강제층 자체의 결함이다.

두 분기가 서로를 부분적으로 가려 준다(코퍼스 디렉터리 안의 register 파일은 파일명 분기가 잡는다).
그러나 둘 다 케이스 변형하면(`TOS-SPEC/.../evidence-register-002.csv`) 전부 통과한다 — PoC-1 마지막 행.

- **recommendation**: 판정 전에 `os.path.normcase` 적용 + 대소문자 무시 비교. 더 견고하게는
  경로 문자열 비교 대신 `Path.stat().st_dev/st_ino` 로 **대상 아이노드 집합**과 대조한다
  (S-9 의 하드링크도 함께 닫힌다).

---

## S-4 · HIGH — `write_guard()` 12개 중 10개 우회 — OD-3-C "실행 중 파일 쓰기 0" 이 성립하지 않는다

- **location**: `proto/boundary.py:101-136` (`GUARDED_ENTRY_POINTS`), `:138-150` (`_OS_BLOCKED`), `:628-633` (fd 0/1/2 면제)
- **유형**: CWE-184 Incomplete List of Disallowed Inputs
- **confidence**: 100 (실측)

PoC-3 — `write_guard()` 활성 상태에서 실제로 파일이 생성되면 BYPASS:

```
BYPASS    _io.open(w)                              a_io.txt 생성됨 (7B)
BYPASS    io.FileIO(w)                             b_fileio.txt 생성됨 (7B)
BYPASS    가드 진입 전 바인딩된 open(w)                     c_prebound.txt 생성됨 (7B)
BYPASS    os.pwrite (FileIO fd)                    d_pwrite.txt 생성됨 (7B)
BYPASS    os.writev (FileIO fd)                    e_writev.txt 생성됨 (7B)
BYPASS    subprocess sh -c echo >                  f_subproc.txt 생성됨 (8B)
BYPASS    os.ftruncate                             g_ftrunc.txt 생성됨 (3B)
BYPASS    os.mkfifo (노드 생성)                        i_fifo 생성됨 (0B)
BYPASS    os.dup2 + os.write(fd=1) 면제 악용           j_dup2.txt 생성됨 (25B)
BYPASS    os.chmod (메타데이터 변경)                      l_chmod.txt 생성됨 (0B)
BLOCKED   os.removedirs / tempfile.mkstemp         (Path.mkdir·os.open 경유 — 정상 차단)
----
가드 실행 중 실제로 생성된 파일 10개 · write_guard 기록된 차단 시도: 2건
```

고지(`L-T77-WRITE-SCOPE`, `test_contracts.py:904-910`)가 덮는 것: `subprocess`·가드 진입 전 바인딩.
**고지 밖**은 `_io.open`·`io.FileIO`·`os.pwrite`·`os.writev`·`os.ftruncate`·`os.mkfifo`·
`os.chmod`·`os.dup2` — **전부 `os`/`io` 모듈의 평범한 표준 라이브러리 진입점**이며,
고지문이 스스로 범위라고 적은 "Python 표준 라이브러리 진입점" 안에 있다.
`os.truncate` 는 막고 `os.ftruncate` 는 안 막는 식의 인접 누락이 반복된다.

**fd 0/1/2 면제(`:629-632`)는 그 자체가 악용 가능하다.** 고지는 "보고 자체가 막히면 진단이
불가능하다"고 정당화하지만, `os.dup2` 가 미가드이므로 fd 1 을 임의 파일로 **리디렉션한 뒤**
면제된 `os.write(1, ...)` 를 쓰면 디스크에 25바이트가 착지한다(위 `j_dup2.txt`). 면제의 전제
("fd 1 은 콘솔이다")가 강제되지 않는다.

- **recommendation**: `sys.addaudithook`(`open` 이벤트가 flags 를 함께 준다)로 이동.
  열거를 유지한다면 `os.pwrite`/`writev`/`ftruncate`/`mkfifo`/`mknod`/`chmod`/`chown`/
  `dup2`/`removedirs`/`_io` 추가. fd 면제는 fd 번호가 아니라 **진입 시점에 캡처한
  `os.fstat(1)` 의 (st_dev, st_ino)** 와 대조해 리디렉션을 탐지한다.

---

## S-5 · HIGH — `locate_violation()` 이 위조 가능: 빈 `pyproject.toml` 파일 1개로 repo 밖 전건 GREEN 이 복구된다

- **location**: `proto/boundary.py:438-456`, `test_contracts.py:69` (`_REPO_ROOT = _HERE.parents[2]`)
- **유형**: CWE-807 Reliance on Untrusted Inputs in a Security Decision
- **confidence**: 100 (실측)

심판 v2.3 F3 부수 발견("사본을 repo 밖에 두고 실행해도 28/28 GREEN")에 대한 v2.5 의 교정이
④ `locate_violation` 이다. 그런데 이 검사의 두 축 중:

- **상대경로 축**(`:450-455`)은 **동어반복**이다. `repo_root` 가 러너 자신에게서 파생되므로
  (`_HERE.parents[2]`) 사본이 `<임의경로>/tools/spikes/phase0_contract/` 구조만 유지하면
  `rel == EXPECTED_RUNNER_RELPATH` 가 **항상** 참이다.
- **표지 축**(`:446-448`)만이 비동어반복인데, `.git` 또는 `pyproject.toml` 의 **존재만** 본다.

실측:

```
### repo 표지 없음 (대조군)
대조군 30건 중 양방향 성립 28건
미성립: ['T-77-④', 'SELF-1']

### 빈 pyproject.toml 1개 생성  ($ : > fakerepo/pyproject.toml)
$ ls -la fakerepo/
-rw-r--r--  0  pyproject.toml
drwxr-xr-x     tools

대조군 30건 중 양방향 성립 30건
OD-3-A 코퍼스·register 열람 시도 기록: 없음
산문 앵커 대조: 리터럴=5efb40f2c1962a30 · 방출=cada1899362b330b ·
               Case산문=a43e14b843e49a4e · 실행코드=f4ea9b8f2d77b472
EXIT=0
  [T-77-④] 현위치 이탈=없음 · repo 밖 사본 검출=['러너가 repo 루트 밖에 있다: /elsewhere/...']
```

**0바이트 파일 하나가 경계 위치 앵커 전체를 무력화한다.** 그리고 그 상태에서 `forbidden_artifacts_present`
(③)·`read_prototype_sources`(①) 의 기준점도 함께 가짜 루트로 이동하므로, `boundary.py:12-15` 가
경계했던 "①⒝③ 의 기준점이 함께 이동해 경계 검사가 무의미해지는" 상황이 **그대로 재현된다**.
S-1 의 실증은 실제로 이 가짜 루트 위에서 수행됐다.

- **recommendation**: 표지 존재가 아니라 **동일성**을 본다 — `git rev-parse --show-toplevel`
  결과와 대조하거나, 커밋된 앵커에 repo 루트의 `.git/HEAD` 커밋 해시 또는 `pyproject.toml` 의
  digest 를 넣어 `config.yaml` 값과 대조한다(이 프로토타입의 기존 앵커 규율과 동형).

---

## S-6 · HIGH — `runner_source_anchor` 가 모듈 레벨을 전혀 덮지 않는다 — "소스 전체를 묶는다"가 참이 아니다

- **location**: `test_contracts.py:291-315` (`_module_code_parts`), `:318-332` (`loaded_code_text`), `:335-352`
- **유형**: CWE-1288 Improper Validation of Consistency within Input (무결성 앵커의 커버리지 공백)
- **confidence**: 100 (실측)

`_module_code_parts` 는 `dir(module)` 중 **`__code__` 를 가진 객체**(함수·메서드)만 펼친다.
따라서 다음이 전부 앵커 밖이다:

| 표면 | 규모(실측) |
|---|---|
| 모듈 레벨 문장 | 무제한 — S-1 의 열람 주입이 여기 들어갔다 |
| 모듈 레벨 데이터 대입 | `boundary.py` 만 18개 (`FORBIDDEN_ARTIFACTS`·`READ_GUARDED_ENTRY_POINTS`·`_OS_BLOCKED` 등 **경계 정의 전체**) |
| 모듈 docstring | 러너 1,870자 + `boundary.py` 1,191자 |
| 주석 | 전량 |

**행수 보존 뮤테이션 3종 실측** (scratchpad 사본, 기준선 출력과 전체 diff):

```
### 뮤테이션 C: OD-3-B 감시 대상 1종 무력화
  ("PHASE0-UNCHECKABLE-REGISTER.csv" -> "PHASE0-UNCHECKABLE-REGISTR.csv")
  EXIT=0
  >>> 출력 diff 0 — 30/30 GREEN, 앵커 4종 전부 불변 <<<

### 뮤테이션 F: 두 모듈 docstring 의 강제 범위 주장을 정반대로 개작
  boundary.py : "제시된 3종 우회가 전부 red 가 된다"
             -> "전 경로를 완전히 봉쇄하며 어떤 우회도 남지 않는다.  A·B·C·D·E 전부 기계 강제된다."
  test_contracts.py : "**D·E 에는 기계 검사가 없다.**  강제한다고 쓰지 않는다."
                   -> "**D·E 도 전부 기계 강제된다.**  한계는 남지 않는다."
  EXIT=0
  >>> 출력 diff 0 — 30/30 GREEN, 앵커 4종 전부 불변 <<<
```

뮤테이션 F 가 가장 날카롭다. 앵커 4종은 `config.yaml:28-61` 이 명시하듯 **"산문 통로"를 닫으려고**
5차에 걸쳐 도입됐는데, 프로토타입에서 가장 큰 두 산문 표면(모듈 docstring 3,061자)이
**어느 앵커에도 묶여 있지 않다.** 그리고 그 docstring 은 정확히 강제 범위 주장을 담고 있다.

`test_contracts.py:342` 의 "**소스 전체를 묶는다**"와 `config.yaml:53` 의 "러너의 어떤 편집이든
이 값 갱신을 요구한다"는 **실측으로 반증된다** — 위 3종은 편집이지만 갱신을 요구하지 않았다.

> 부수 관측: 대비 뮤테이션 A(같은 항목을 **행 삭제**로 제거)는 red 가 됐으나, 전체 diff 상
> 유일한 실질 변화는 무관한 AST 진단 문자열의 **행번호**였다(`boundary.py:652` → `:651`).
> 즉 A 를 잡은 것은 의미 검사가 아니라 **행번호 우연**이며, 행수를 보존한 C 는 잡히지 않았다.

- **recommendation**: 앵커 대상을 `mod.__loader__.get_data(mod.__file__)` 의 **모듈 소스 바이트**로
  바꾼다(주석·docstring·모듈 레벨 전부 포함). 4차 교정이 디스크 해시를 버린 이유(런타임 함수 교체)는
  **소스 digest 와 코드 객체 digest 를 둘 다 유지**하면 해소된다 — 하나를 다른 하나로 교체할 이유가 없다.

---

## S-7 · MEDIUM — `read_violation()` 의 register 접두 분기에 대조군이 없다

- **location**: `proto/boundary.py:433` · 대조군 `test_contracts.py:851-856`
- **유형**: 검사 공백 (test-coverage of a security predicate)
- **confidence**: 95 (실측)

T-77-①-READ 의 방향② 프로브는 `(_REPO_ROOT / <corpus-dir 변형> / "src")` 3종뿐 —
**전부 `_CORPUS_DIRNAME in parts` 분기만 발화시킨다.** 파일명 접두 분기는 한 번도 발화하지 않는다.

행수 보존 뮤테이션 E 실측:

```
### 뮤테이션 E: startswith(_REGISTER_PREFIX) -> startswith(_REGISTER_PREFIX + "Z")
  EXIT=1
  미성립: ['SELF-1']                      <-- T-77-①-READ 는 GREEN 유지
  산문 앵커: ... 실행코드=9789f44731243e24!=f4ea9b8f2d77b472
```

의미 검사(T-77-①-READ)는 **통과시켰고**, 오직 실행코드 앵커만 움직였다 — 그것도 리터럴 `"Z"` 가
함수 `co_consts` 에 들어갔기 때문인 **우연**이다. 코퍼스 디렉터리 **밖**의 register 사본
(S-9 의 하드링크, 또는 다른 위치의 복사본)은 이 분기에만 의존하는데 그 분기에 관측이 없다.

- **recommendation**: T-77-①-READ 방향②에 코퍼스 디렉터리 밖 경로 + register 접두 파일명
  프로브를 추가한다.

---

## S-8 · MEDIUM — OD-3-B 감시 목록 축소가 의미 수준에서 무검출

- **location**: `test_contracts.py:823-839`
- **유형**: 약한 단언 (assertion under-specification)
- **confidence**: 100 (실측)

```python
mutant_artifacts = boundary.forbidden_artifacts_present(lambda path: path == target, _REPO_ROOT)
...  len(mutant_artifacts) == 1
```

`target` 은 `FORBIDDEN_ARTIFACTS[0]` 하나뿐이므로 **목록 길이가 1 이상인 어떤 값이든** 이 단언이
성립한다. "금지 D0 아티팩트 **5종**"이라는 계약의 기수(cardinality)가 어디에서도 관측되지 않는다.
S-6 뮤테이션 C 가 이를 실증한다(5종 중 1종 무력화 → 출력 diff 0, exit 0).

- **recommendation**: `len(boundary.FORBIDDEN_ARTIFACTS) == cfg["anchor_forbidden_artifact_count"]`
  같은 **커밋된 기수 앵커**를 추가한다(T-39 의 `anchor_enforcement_key_count`, T-71 분포 앵커와 동형 —
  이 프로토타입은 이미 그 패턴을 쓴다).

---

## S-9 · MEDIUM — 하드링크가 `read_violation()` 을 통과한다 (경로를 보고 아이노드를 보지 않는다)

- **location**: `proto/boundary.py:414-435`
- **유형**: CWE-59 Improper Link Resolution / CWE-41 Path Equivalence
- **confidence**: 90 (실측 — 단, 사전 준비 필요)

```
하드링크: /var/folders/.../harmless.csv -> inode 41992032 (원본 41992032)
Path.read_text (목록에 있는 정본 진입점) 로 열람:
  판정: **BYPASS** — register 내용 93865바이트 획득
  내용: evidence_id,domain,title,primary_adr,criticality,minimum_evidence_level,...
  기록된 차단 시도: 0건
```

대조 — **심볼릭 링크는 정상 차단된다**(`resolve()` 가 따라가므로). 하드링크는 `resolve()` 로
되돌릴 수 없어 판정이 성립하지 않는다.

**정직한 한정**: 하드링크 생성 자체(`os.link`)는 `write_guard` 가 막으므로 **실행 전에 준비된**
링크여야 한다. 러너를 단독 실행하는 통상 시나리오에서는 즉시 성립하지 않는다. 다만 OD-3 는
"프로토타입이 코퍼스를 열람하지 않는다"를 **작업트리 상태와 무관하게** 보장한다고 주장하므로,
사전 준비된 링크(또는 단순 파일 복사)로 무너지는 것은 보장 범위의 결함이다.

- **recommendation**: S-3 과 동일 — 경로 문자열이 아니라 `(st_dev, st_ino)` 집합 대조.

---

## S-10 · LOW — 일반 보안 항목: 관측된 결함 없음

- **confidence**: 95

| 항목 | 실측 |
|---|---|
| 역직렬화 | `pickle`·`yaml.load`·`marshal` 사용 0건. `config.yaml` 은 YAML 파서를 쓰지 않고 `proto/config.py:58-70` 의 자체 `key: value` 한 줄 파서로 읽는다 — 역직렬화 표면 없음 |
| `eval`/`exec`/`__import__` | 사용 0건 (`grep` 히트는 전부 산문 안의 `subprocess` 언급) |
| `os.system`/쉘 | 사용 0건 |
| 시크릿 | KIS API key/secret/계좌번호·OpenAI/KRX/DART 키 패턴 0건. 이 프로토타입은 자격증명을 다루지 않는다 |
| 외부 입력 | 러너는 `argv`·환경변수·stdin 을 **전혀 읽지 않는다**. 유일한 외부 입력은 `proto/config.yaml`(repo 내) |
| 파싱 실패 처리 | fail-closed 가 일관된다 — `config.py:41,55,63,67,69,74,82,90,102,106,108,111` 전부 `ConfigError` 중단이며 기본값 폴백 0건. `scan_sources_ast` 의 `SyntaxError` 도 조용한 통과가 아니라 findings 로 보고(`boundary.py:394-396`) |
| 경로 순회 | `load_config(path)` 가 임의 경로를 받지만 호출자는 기본값만 쓴다(`test_contracts.py:1580`). 외부 입력에서 도달 가능한 순회 경로 없음 |

`read_violation` 의 `except (TypeError, ValueError): return None`(`:425-426`) 은 형식상 fail-open 이나,
`os.fsdecode` 가 실패하는 인자는 실 `open()` 도 거부하므로 악용 경로가 관측되지 않는다 — 지적하지 않는다.

---

## S-11 · LOW — 스캔 도메인 밖 형제 도구: 확인 결과 OD-3-A 위반 없음

- **location**: `test_contracts.py:924-930` (`L-T77-DOMAIN`)
- **confidence**: 100 (실측)

스캔 도메인은 9개 파일(`proto/*.py` 7 + `proto/config.yaml` + 러너)이고, 같은 디렉터리의
`blocks_gate_consumption.py`·`sweep_deprecated_vocabulary.py` 는 **도메인 밖**이다(고지됨).
이 둘이 실제로 코퍼스를 읽는지 확인했다:

```
blocks_gate_consumption.py:66   DOC = "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"
sweep_deprecated_vocabulary.py:49  DOCS = [ ... docs/plans/... ]
```

둘 다 `docs/plans/` 만 읽는다 — **코퍼스·register 열람 없음.** 고지된 도메인 공백이 현재
실제 위반으로 실현되어 있지는 않다. 회귀 위험만 남는다(도메인 확장 시 자동 편입되지 않음).

---

## 추측과 실측의 구분

- **전부 실측**: S-1 ~ S-9, S-11 은 PoC 실행 출력 또는 뮤테이션 전체 diff 를 그대로 인용했다.
- **추측 없음**: 실행으로 확인하지 못한 지적은 이 문서에 싣지 않았다.
- **정직한 한정 표기**: S-9 는 사전 준비가 필요함을 본문에 명시했다. S-2/S-4 는 **고지된 한계**와
  **고지 밖 결함**을 표로 분리했다.

## 재현

```bash
S=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/\
2ed2dc33-ef7f-4f31-b91f-b5258c17c8dd/scratchpad
python3 $S/poc/poc1_read_guard_bypass.py      # S-2, S-3
python3 $S/poc/poc2_read_violation_logic.py   # S-3, S-9
python3 $S/poc/poc3_write_guard_bypass.py     # S-4
# S-1/S-5/S-6/S-7/S-8: $S/fakerepo 사본 + 본문의 뮤테이션 지시
```

**repo 내 프로토타입은 편집하지 않았다.** 모든 뮤테이션은 `$S/fakerepo/` 사본에서 수행했고,
PoC 실행으로 생긴 `proto/__pycache__/` 는 감사 종료 시 제거했다. `git status --porcelain tools/spikes/`
= `?? tools/spikes/` (감사 시작 시점과 동일).
