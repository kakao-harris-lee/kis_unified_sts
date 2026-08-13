# evidence — security lens · 재심 (v2.6) · `tools/spikes/phase0_contract/`

```yaml
lens: security
mode: 재심 (re-audit)
scope: tools/spikes/phase0_contract/{audit_guard.py, proto/*.py, proto/config.yaml, test_contracts.py}
baseline_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
prior_evidence: .omc/review/20260813-075200/evidence/security.md (S-1~S-11)
prior_verdict: .omc/review/20260813-075200/verdict.md (needs-attention · critical 1 / high 3)
runtime: Python 3.14.5 · darwin 25.5.0 · APFS(대소문자 무시)
verdict: 없음 — 이 문서는 증거다.  판정은 Codex 심판 레인 소관.
prior_findings_disposition: 해소 6 · 부분해소 1 · 미해소 2 · 변동없음 2 · 회피 0
new_findings: 8 (high 2 / medium 3 / low 3)
prototype_modified: NO (12개 파일 shasum 감사 전후 동일 · __pycache__ 0 · 코퍼스 무변경)
```

## 총평 — 회피가 아니라 실질 재설계다

**회피 신호(테스트 무력화·조건 완화·표면 이동·문구만 추가)를 4축으로 찾았고 하나도 관측되지 않았다.**
대조군은 30 → **32건으로 증가**했고(축소 아님), 앵커는 4 → **5종으로 확대**됐으며,
직전 CRITICAL PoC 를 **바이트 단위로 그대로 재실행**했을 때 exit 0 → **exit 1** 로 뒤집혔다.
`sys.addaudithook` 이전은 monkeypatch 열거였고 지금은 인터프리터 수준 강제다 — 표면 이동이 아니라
**강제 지점 자체의 층 교체**다.  직전에 뚫렸던 12개 열람 진입점 중 **12개 전부**, 10개 쓰기 진입점 중
**8개**가 닫혔다.

그러나 **강제층(감사 hook)과 검출층(앵커)이 비대칭**이다.  아래 N-1·N-2 는
강제층을 **기록 0건으로** 통과하며, 잡히는 것은 오직 디스크 편집을 보는 소스바이트 앵커다.
즉 v2.6 이 실제로 달성한 것은 *폐쇄*가 아니라 **"디스크에 남는 편집에 한해 가시화"**이고,
러너 자신도 `L-SELF-VISIBILITY` 에서 그렇게 적고 있다.  이 문서의 신규 지적은 그 고지가
**얼마나 넓은 표면을 덮어야 하는지**가 아직 과소 서술돼 있다는 것이다.

---

## 기준선 (실측 · 원본 트리)

```
$ python3 tools/spikes/phase0_contract/test_contracts.py
대조군 32건 중 양방향 성립 32건
감사 hook 차단 기록 — 대조군 프로브 밖: 열람 없음 · 쓰기 없음
감사 hook 차단 기록 — 대조군 프로브 안: 열람 6건 · 쓰기 2건
산문 앵커 대조: 리터럴=c8380b9cc6f85ea2 · 방출=c9eae41098208b40 · 실행코드=9bf6030332fd7604 ·
               소스바이트=63b83b185ad21abd · Case산문=53890d21ae213964
EXIT=0
```

스크래치패드 사본(`<tmp>/repo` + 가짜 `.git`)의 기준선이 **앵커 5종 전부 원본과 동일**함을
먼저 확인한 뒤 모든 뮤테이션을 그 위에서 수행했다.

---

# 1부 · 직전 발견 S-1 ~ S-11 처분

## S-1 · CRITICAL → **해소**

직전 PoC(모듈 레벨 문장 + bytes 조립 경로 + `_io.open`)를 **동일한 형태로 재주입**했다.

```
### 뮤테이션: proto/register.py 말미에 모듈 레벨 열람 주입 (직전과 동일)
stderr : ### EXFIL len= 179  head= FAILED:AuditViolation:코퍼스·register 접근 차단: open:코퍼스 디렉터리 접근: ...
EXIT   = 1                                     (직전: 0)
대조군 32건 중 양방향 성립 30건
미성립: ['T-77-AUDIT', 'SELF-1']               (직전: 미성립 0)
감사 hook 차단 기록 — 대조군 프로브 밖:
  열람 ['open:코퍼스 디렉터리 접근: /Users/.../tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv']
산문 앵커: 소스바이트=97ef20b91219290c!=63b83b185ad21abd · Case산문=5856d4696e557b1b!=53890d21ae213964
탈취 바이트 = 0                                (직전: 93,865)
```

**열람 자체가 실패**했고(예외로 대체), 헤드라인 기록에 남았으며, 앵커 2종이 움직였고,
독립 Case 2건이 red 다.  직전 CRITICAL 의 두 구성요소(① `_io.open` 미가드 ② 모듈 레벨이
앵커 밖) 가 **둘 다** 닫혔다.

## S-2 · HIGH → **해소** (열거 밖 6종 전부)

`read_guard` 활성 상태에서 21개 열람 진입점 전수 프로브 (`poc/pocA_read_battery.py`):

```
판정         진입점                                결과
BLOCKED    _io.open                           AuditViolation      <- 직전 BYPASS
BLOCKED    io.FileIO                          AuditViolation      <- 직전 BYPASS
BLOCKED    io.open_code                       AuditViolation      <- 직전 BYPASS
BLOCKED    os.open+os.read                    AuditViolation
BLOCKED    tokenize.open                      AuditViolation      <- 직전 BYPASS
BLOCKED    linecache.getlines                 AuditViolation      <- 직전 BYPASS
BLOCKED    SourceFileLoader.get_data          AuditViolation      <- 직전 BYPASS
BLOCKED    builtins.open                      AuditViolation
BLOCKED    os.listdir / os.scandir / glob      AuditViolation
BLOCKED    _io.open CASE dir / CASE name      AuditViolation      <- 직전 BYPASS
BLOCKED    dotdot relative                    AuditViolation
BLOCKED    mmap(via os.open)                  AuditViolation      <- fd 획득 지점에서 차단
BYPASS     [declared] subprocess cat          evidence_id,domain,title,...
BYPASS     [declared] os.popen                evidence_id,domain,title,...
BYPASS     [declared] ctypes libc.open        evidence_id,domain,title,...
BYPASS     sqlite3.connect(path)              connected:<sqlite3.Connection ...>
BYPASS     os.stat(register)                  size=93904
BYPASS     os.path.exists(corpus)             True
----
BYPASS 6/21 (직전 12/18) · 이 중 3건은 `L-AUDIT-SCOPE` 고지 안 · 3건은 신규 관측(N-7·N-8)
```

**직전에 지적한 "고지 밖" 6종이 전부 BLOCKED 다.**  잔여 BYPASS 중 subprocess·os.popen·ctypes 는
`L-AUDIT-SCOPE` 가 명시 고지한 범위이며 지적이 아니다.  `_io.open` 이 `builtins.open` 과
동일 객체인데 목록에서 빠졌던 문제는 **열거 자체를 폐기**해 소멸했다 — `open` 감사 이벤트
하나가 6개 별칭에서 전부 발화한다.

## S-3 · HIGH → **해소**

```
경로변형                     실재     path_violation   실제열람
정본                       True   차단판정             BLOCKED
디렉터리 대문자 (TOS-SPEC)      True   차단판정             BLOCKED    <- 직전 BYPASS
디렉터리 혼합 (Tos-Spec)       True   차단판정             BLOCKED    <- 직전 BYPASS
register 소문자             True   차단판정             BLOCKED    <- 직전 BYPASS
register 혼합               True   차단판정             BLOCKED    <- 직전 BYPASS
..  경유                    True   차단판정             BLOCKED
./ 중복 슬래시                True   차단판정             BLOCKED
심볼릭링크(디렉터리)             True   차단판정             BLOCKED
심볼릭링크(파일)               True   차단판정             BLOCKED
```

**요청받은 유니코드 정규화 축 — 실측 결과 악용 경로 없음.**  판정 토큰이 `tos-spec` ·
`EVIDENCE-REGISTER-` 로 **순수 ASCII** 이므로 NFC/NFD 이형이 존재하지 않는다.  전각
(`ｔｏｓ-ｓｐｅｃ`)은 casefold 로 접히지 않지만 **디스크에 대응 파일이 없어**(`실재=False`)
열람 자체가 불가능하다.  Kelvin 기호류 호환 문자는 `casefold()` 가 이미 접는다.
`L-CASEFOLD` 의 "유니코드 정규화까지는 접지 않는다"는 정직한 고지이나 **현 토큰 집합에서는
공백이 실현되지 않는다** — 이 축으로는 지적을 만들지 않는다.

## S-4 · HIGH → **부분해소** (10건 중 8건 폐쇄)

```
판정         진입점                                결과
BLOCKED    _io.open(w)                        AuditViolation      <- 직전 BYPASS
BLOCKED    io.FileIO(w)                       AuditViolation      <- 직전 BYPASS
BLOCKED    가드 이전 바인딩 open(w)                 AuditViolation      <- 직전 BYPASS
BLOCKED    os.pwrite / os.writev / os.ftruncate  AuditViolation    <- 직전 BYPASS ×3
BLOCKED    os.dup2 + os.write(1) 면제악용         AuditViolation      <- 직전 BYPASS
BLOCKED    os.chmod                           AuditViolation      <- 직전 BYPASS
BLOCKED    os.truncate / link / symlink / rename / mkdir / utime / remove / shutil.copyfile
BLOCKED    import -> .pyc 쓰기                  AuditViolation
BYPASS     os.mkfifo                          i_fifo 생성됨 (0B)   <- 잔존
BYPASS     os.mknod(S_IFIFO)                  i2_mknod 생성됨 (0B) <- 잔존
BYPASS     [declared] subprocess sh -c >      f_subproc.txt (3B)
----
BYPASS 3/21 (직전 10/12)
```

- **fd 면제 악용이 근원에서 닫혔다**: `os.dup2` 자체엔 감사 이벤트가 없지만, 쓰기용 fd 를
  얻는 `os.open(O_CREAT|O_WRONLY)` 가 `open` 이벤트로 차단되므로 후속 `os.pwrite`/`writev`/
  `ftruncate`/`dup2` 가 전부 도달 불능이 됐다.  직전 권고("fd 번호가 아니라 진입 시점
  `os.fstat` 대조")보다 나은 해법이다.
- **잔존**: `os.mkfifo` · `os.mknod` 는 감사 이벤트가 없어 0바이트 특수 노드가 착지한다.
  `os.mknod(S_IFREG)` 는 macOS 에서 비특권 프로세스에 `PermissionError` 라 **일반 파일은
  만들 수 없다**.  내용 반출·코퍼스 변조 능력은 없고 잔존물 스윕 범위(`_HERE.glob("__probe_*")`)
  밖이다.  → **LOW**, 권고: `WRITE_EVENTS` 가 아니라 종료 시 `_HERE` 잔존물 전수 스윕을 추가.

## S-5 · HIGH → **미해소** (고지됨 · 다만 고지보다 싸다)

```
### M7  `.git` 표지 없음 (대조군)
  EXIT=1  미성립=['T-77-④', 'SELF-1']
### M7b `.git` 를 **0바이트 일반 파일**로 생성
  EXIT=0  대조군=('32','32')  미성립=[]  앵커 이동=없음
```

`locate_violation` 은 `(repo_root / marker).exists()` 를 쓴다 — **디렉터리일 필요가 없다.**
`os.path.samefile(expected, runner)` 축은 서브트리를 통째로 복사하면 자동 성립하므로
(사본의 러너가 곧 예상 상대경로의 실물이다) **위조 총비용 = 0바이트 파일 하나**다.
`L-LOCATE-FORGE` 는 "`.git` **디렉터리**를 만들고 러너 사본을 예상 상대경로에 두면"이라
적어 실제보다 비싸게 서술했다.  덧붙여 `.git` **파일**은 git worktree·submodule 이 쓰는
정상 아티팩트라 이 위조는 이례적 준비물이 아니다.
→ 심각도 유지(**MEDIUM**, 직전 HIGH 에서 하향 — 두 겹이 추가돼 *이동* 관측은 실제로 강해졌다).
권고는 직전과 동일: `git rev-parse --show-toplevel` 동일성 또는 `.git/HEAD` digest 앵커.

## S-6 · HIGH → **해소**

행수 보존 뮤테이션 3종 전부 red 로 뒤집혔다.

```
### M1 FORBIDDEN_ARTIFACTS 5->1 (행수 보존, 4항목 주석화)
  EXIT=1  미성립=['T-77-③', 'SELF-1']   앵커 이동=['소스바이트','Case산문']
### M2 REQUIRED_METRICS 4->2 (행수 보존)
  EXIT=1  미성립=['T-67','T-39','SELF-1'] 앵커 이동=['소스바이트','Case산문']
### M3 모듈 docstring 개작 ("v9.9 는 전 경로를 완전 봉쇄하며 어떤 우회도 없다")
  EXIT=1  미성립=['SELF-1']             앵커 이동=['소스바이트']
```

직전 뮤테이션 C·F(둘 다 출력 diff 0 · 앵커 4종 불변)가 **정확히 반전**됐다.
`anchor_source_paths()` 가 `proto/__init__.py` 를 포함한 9개 파일의 **정확한 바이트**를
파일명과 함께 묶으므로 모듈 레벨 데이터·주석·docstring 이 전부 정의역 안에 들어왔고,
`config.yaml:70-97` 은 직전 주석의 "proto 7개"·"어떤 편집이든"이 **거짓이었다고 명시 정정**했다.
잔여(런타임 대입)는 `tuple_anchor` 값 앵커와 실행코드 앵커가 받는다 — 실측으로 확인(M5).

## S-7 · MEDIUM → **해소**

`T-77-AUDIT` 방향② 프로브에 **코퍼스 디렉터리 밖의 register 접두 파일명**이 들어왔다
(`test_contracts.py:1071-1078`):

```python
("_io.FileIO(register)", lambda: _IO.FileIO(str(_HERE / register_name))),
("_io.open(register 대소문자 변형)", lambda: _IO.open(str(_HERE / register_name.lower()))),
```

`_HERE` 는 스파이크 디렉터리이므로 `_CORPUS_DIRNAME in parts` 분기가 아니라
**파일명 접두 분기만** 발화한다 — 직전에 한 번도 관측되지 않던 분기다.

## S-8 · MEDIUM → **해소**

`test_contracts.py:927-928` 이 `tuple_anchor(boundary.FORBIDDEN_ARTIFACTS)` 를
`config.yaml:43 anchor_forbidden_artifacts_digest` 와 대조한다.  기수뿐 아니라 **값 전체**를
묶으므로 직전 권고보다 강하다.  M1 실측에서 `T-77-③` 이 red 로 발화했다.
`declared_required_metrics`(`config.yaml:37`)도 동형으로 추가됐고 M2 가 `T-67`·`T-39` 를
red 로 만들었다.

## S-9 · MEDIUM → **미해소**

```
경로변형                     path_violation   실제열람     비고
하드링크(무해한 이름)             통과판정          BYPASS    evidence_id,domain,title,primary_adr,crit
사본(복사본)                   통과판정          BYPASS    evidence_id,domain,title,primary_adr,crit

inode 대조:  정본     dev=16777232 ino=41992032 size=93904
             하드링크  dev=16777232 ino=41992032 size=93904      <- 동일 아이노드
```

판정이 여전히 **경로 문자열**만 본다.  심볼릭 링크는 `resolve()` 가 접어 차단되지만
하드링크는 되돌릴 수 없다.  **정직한 한정**은 직전과 동일 — `os.link`·`shutil.copyfile` 이
이제 감사 hook 으로 차단되므로 링크·사본은 **실행 전 out-of-band 준비물**이어야 한다.
다만 `L-CASEFOLD`·`L-AUDIT-SCOPE` 어느 노트도 **아이노드 별칭**을 언급하지 않는다 —
고지 목록의 공백이다.  권고: `path_violation` 에 `(st_dev, st_ino)` 집합 대조를 한 겹 추가.

## S-10 · LOW → **변동 없음 (결함 0 유지)**

| 항목 | 실측 (신규 `audit_guard.py` 포함) |
|---|---|
| `eval`/`exec`/`pickle`/`marshal`/`yaml.load`/`os.system`/`__import__` | grep 히트 **0건** |
| 시크릿 (KIS key/secret/계좌·OpenAI/KRX/DART) | **0건** — 이 프로토타입은 자격증명을 다루지 않는다 |
| 외부 입력 | `argv`·환경변수·stdin 미사용.  유일한 입력은 repo 내 `proto/config.yaml` |
| 역직렬화 | `config.py` 의 자체 `key: value` 한 줄 파서 — YAML 파서 미사용, 표면 없음 |
| fail-closed | `audit_guard.path_violation:156,160` 의 `except` 는 fail-open 형태이나, `os.fsdecode` 가 거부하는 인자는 실 `open()` 도 거부하고 `resolve()` 실패 시엔 **미해석 원문으로 폴백해 계속 판정**한다 — 악용 경로 미관측 |

## S-11 · LOW → **변동 없음**

`blocks_gate_consumption.py` · `sweep_deprecated_vocabulary.py` 에 `tos-spec` ·
`EVIDENCE-REGISTER` grep 히트 **0건**.  둘 다 `docs/plans/` 만 읽는다.  스캔 도메인은
9 → **10개**로 늘었고(`audit_guard.py` 편입) 두 형제 도구는 여전히 밖이다(고지됨).

---

# 2부 · 신규 발견 — 감사 hook 자체가 새 공격면이다

## N-1 · HIGH — 재진입 가드가 스레드 지역이 아니어서 **정본 강제층이 기록 0건으로 뚫린다**

- **location**: `tools/spikes/phase0_contract/audit_guard.py:113` (`_REENTRANT = False`), `:206-217` (`_hook`)
- **유형**: CWE-367 TOCTOU / CWE-693 Protection Mechanism Failure (재진입 창)
- **confidence**: 100 (결정론적 실측)

`_hook` 은 모듈 전역 `_REENTRANT` 로 재진입을 막는다.  스레드 지역이 아니므로 **한 스레드가
`_enforce` 안에 있는 동안 다른 모든 스레드의 hook 이 조기 return** 한다.  `sys.audit()` 을
Python 레벨에서 직접 부르면 인자가 변환 없이 전달되어 `os.fsdecode(arg)` → `__fspath__` 가
**hook 안에서** 실행되므로 이 창을 **결정론적으로** 열 수 있다.

```
$ python3 poc/pocD2_reentrancy.py
=== 대조: 창 없이 ===
  열람: BLOCKED
=== 창을 연 상태 (다른 스레드) ===
    [thief] _REENTRANT = True
  탈취 스레드 열람 : ('BYPASS', '﻿evidence_id,domain,title,primary_adr,critic')
  탈취 스레드 쓰기 : ('BYPASS', '디렉터리 생성됨')
  blocked_reads    : 1        <- 창을 연 정상 경로 1건뿐
  blocked_writes   : 0        <- 탈취는 기록 0
```

러너 안에서의 실측(`M6`/`N3` — 리터럴·AST 스캔을 회피한 난독화 형태):

```
### N3 난독화 스레드 탈취 (리터럴/AST 회피)
  EXIT=1  대조군=('32','31')  미성립=['SELF-1']
  앵커 이동=['실행코드','소스바이트']
  hook 기록(프로브 밖)=열람 없음 · 쓰기 없음        <-- 정본 강제층은 아무것도 보지 못했다
  stderr= ### N3-EXFIL bytes= 93865 '﻿evidence_id,domain,title,primary_adr,criticality,minimu'
```

**실 register 93,865 바이트가 읽혔고 `T-77-AUDIT` 은 green 을 유지했다.**  red 를 낸 것은
오직 디스크 편집을 보는 소스바이트/실행코드 앵커다.

`L-AUDIT-PERSIST` 는 "재진입 가드는 스레드 지역이 아니며 **이 러너는 단일 스레드다**"라고
적는다.  그러나 ⑴ 단일 스레드임을 **기계로 확인하는 검사가 없고**, ⑵ 이 문장은 *현재 상태*
서술이지 구조적 보장이 아니며, ⑶ `L-AUDIT-SCOPE` 의 "덮지 못하는 것" 목록(fd·mmap·ctypes·
subprocess)에 **재진입 창이 빠져 있다**.  강제층 고지가 실제 잔여보다 좁다.

- **recommendation**: `_REENTRANT` 를 `threading.local()` 로 옮긴다(1행).  더하여
  `threading.active_count()` 또는 `threading.enumerate()` 를 `T-77-AUDIT` 방향① 에 넣어
  "단일 스레드"를 **자기신고가 아니라 관측**으로 바꾸고, `L-AUDIT-SCOPE` 목록에 재진입 창을
  등재한다.

## N-2 · HIGH — `import audit_guard` **순서 검사가 정적 AST 노드만** 봐서 pre-guard 창이 그대로 재개방된다

- **location**: `tools/spikes/phase0_contract/test_contracts.py:1049-1058` (`audit_lines`/`proto_lines` AST 파생), `:96-97`
- **유형**: CWE-693 Protection Mechanism Failure (불완전 술어)
- **confidence**: 100 (실측)

`order_ok` 는 `ast.Import`(alias `audit_guard`) 와 `ast.ImportFrom`(module `proto*`) 의
**행번호만** 비교한다.  동적 import 는 어느 노드도 아니므로 술어에 보이지 않는다.

```
### P1  `__import__("proto.register")` 를 `import audit_guard` 바로 앞에 삽입
  EXIT=1  대조군=('32','31')  미성립=['SELF-1']
  앵커 이동=['소스바이트','Case산문']
  hook 기록(프로브 밖)=열람 없음 · 쓰기 없음
  stderr= ### EARLY-EXFIL bytes= 93865 '﻿evidence_id,domain,title,primary_adr,criticality,'
```

`T-77-AUDIT` 은 **green 이다** — `order_ok` 가 여전히 True 이기 때문이다(정적 `import
audit_guard` 는 :96, 정적 `from proto import ...` 는 :97 로 그대로 남아 있다).
러너 주석(`:92-95`)이 "**이 두 줄의 순서가 F3 교정의 전부다**"라고 적은 바로 그 술어가,
직전 F3 critical 과 **같은 결함 클래스**(관측하지 않는 실행 경로)로 우회된다.

- **recommendation**: 순서 술어를 "정적 노드 비교"가 아니라 **구조 파생**으로 바꾼다 —
  `audit_guard` 모듈 객체가 존재하는 시점에 `sys.modules` 에 `proto*` 가 하나도 없었는지를
  `audit_guard` 자신이 import 시점에 기록하고(`_MODULES_AT_BOOTSTRAP`), `T-77-AUDIT` 이
  그 기록을 관측한다.  현재 술어는 `__import__`·`importlib.import_module`·`exec` 를 전부 놓친다.

## N-3 · MEDIUM — 2-pass 앵커 동반 갱신으로 **탈취를 유지한 채 전건 GREEN 복귀** (기계적)

- **location**: `proto/config.yaml:50-97` (앵커 5종) · `test_contracts.py` 앵커 대조 출력
- **유형**: CWE-807 Reliance on Untrusted Inputs in a Security Decision
- **confidence**: 100 (실측)

N-1 의 탈취 페이로드를 그대로 둔 채, 러너가 **스스로 출력한** 새 앵커 값을
`config.yaml` 에 되쓰는 것만으로 green 이 복구된다.

```
  N3 가 요구한 새 앵커 값: {'실행코드': 'f201829a670fc994', '소스바이트': '31d97894690a7cad'}

### N4 = N3 + config.yaml 앵커 동반 갱신 (1차)
  EXIT=0  대조군=('32','32')  미성립=[]  앵커 이동=없음
  hook 기록(프로브 밖)=열람 없음 · 쓰기 없음
  stderr= ### N3-EXFIL bytes= 93865 '﻿evidence_id,domain,title,primary_adr,criticality,minimu'
```

**1회 반복으로 수렴**했다(앵커 상호참조가 발산하지 않는다).  이것은 `L-SELF-VISIBILITY` 가
고지한 잔여와 **동일 클래스**이므로 새 결함 주장이 아니라 **잔여의 정량화**로 제출한다:
비용은 "코드·설정 2곳 diff + 러너 1회 재실행"이고, 필요한 값은 러너가 친절하게 인쇄해 준다.
`declared_self_checks` 조차 건드릴 필요가 없었다(고지문은 그것까지 고쳐야 한다고 적는다).

- **recommendation**: 이 프로토타입 범위에서 기계적으로 닫을 수는 없다(자기참조).  대신
  고지문을 실측 비용에 맞춰 정정하고(“3곳” → “2곳, 1-pass 수렴, 값은 러너가 출력”),
  실제 폐쇄는 **앵커를 러너 밖**(커밋 해시·CI 아티팩트)에 두는 D 층에서만 가능함을 명시한다.

## N-4 · MEDIUM — `_WATCHED` 런타임 대입 시 `policy()` 가 **armed=True 라고 거짓 보고**한다

- **location**: `audit_guard.py:103` (`_WATCHED`), `:117-124` (`policy()`), `:208`
- **유형**: CWE-doubt / 자기신고와 실제 강제의 괴리
- **confidence**: 100 (실측)

```
  _READ_ARMED=False 후 열람      : ('BYPASS', 'evidence_id,domain,title,...')
  policy() 자기신고              : False                      <- 정직

  _WATCHED=frozenset() 후 열람   : ('BYPASS', 'evidence_id,domain,title,...')
  policy() 자기신고              : {'read_armed': True, 'write_armed': True, ...}
  ^ 열람·쓰기 강제가 **둘 다** 꺼진 상태에서 policy() 는 armed=True 를 보고한다
```

`policy()` 는 `_READ_ARMED`/`_WRITE_ARMED` 만 보고하는데 실제 조기 필터는 `_WATCHED` 다.
`_WATCHED` 를 비우면 **모든 이벤트가 hook 첫 줄에서 return** 되어 강제가 전면 해제되는데
자기신고는 변하지 않고, 방출 노트(`L-AUDIT-PERSIST` 의 `True/True`)도 변하지 않아
**방출 앵커가 움직이지 않는다**.

다만 `T-77-AUDIT` 의 **실물 프로브**가 이를 잡는다 — 이것이 v2.6 설계의 강점이다:

```
### M5  런타임 무장해제 `_WATCHED=frozenset()` (모듈 레벨)
  EXIT=1  미성립=['T-77-AUDIT','SELF-1']   앵커 이동=['소스바이트','Case산문']
### M5b 런타임 무장해제 `_READ_ARMED=False`
  EXIT=1  미성립=['T-77-AUDIT','SELF-1']   앵커 이동=['방출','소스바이트','Case산문']
```

- **recommendation**: `policy()` 가 `_WATCHED` 도 함께 보고하도록 하고(자기신고를 실제
  강제 변수에서 파생), 문서의 "정책은 `_READ_ARMED`/`_WRITE_ARMED` 다"를 정정한다.
  `_WATCHED` 를 `READ_EVENTS`/`WRITE_EVENTS` 에서 **매 이벤트마다 파생**하면 괴리가 소멸한다.

## N-5 · MEDIUM — `SELF-2` 는 **판정 배선**을 전수 검증하지만 **producer** 는 보지 않는다

- **location**: `test_contracts.py:1829-1880` (`self_check_consumption`), `:1795-1804` (`collect_self_checks`)
- **유형**: 검사 공백 (assertion domain)
- **confidence**: 100 (실측)

직전 HIGH(“`mutant_red` 가 자기충족적”)는 **실질 해소**다 — `self_check_green(checks,
names_match)` 라는 **단일 판정 지점**을 SELF-1 방향① 과 SELF-2 프로브가 공유하므로
소비 항을 지우면 `names_match` 가 깨진다:

```
### N2 `parked` 항 통째 삭제
  EXIT=1  미성립=['SELF-2','SELF-1']   앵커 이동=['실행코드','소스바이트','Case산문']
```

그러나 **이름은 남기고 producer 만 무력화**하면 SELF-2 는 침묵한다:

```
### N1 `"parked": rep.parked_limits(unchk_ids, waivers)` -> `"parked": []`
  EXIT=1  미성립=['SELF-1']            <- SELF-2 는 green
  앵커 이동=['실행코드','소스바이트']
```

SELF-2 는 `probe[name] = ["<주입>"]` 라는 **합성 값**을 넣어 판정이 뒤집히는지만 본다 —
그 이름의 producer 가 실제로 무언가를 계산하는지는 정의역 밖이다.  red 를 낸 것은 앵커뿐이다.
직전 결함 클래스(“헬퍼가 합성 입력에 기대값을 반환하는지만 본다”)가 **한 층 안쪽으로 이동**했다.

- **recommendation**: 각 producer 에 대해 **실제 위반을 주입**하는 뮤턴트를 추가한다
  (예: 미등재 노트 1건을 넣고 `undeclared` 가 비지 않는지, 주차 노트 1건을 넣고 `parked` 가
  비지 않는지).  현재는 `digest_drift` 만 실입력으로 구동된다.

## N-6 · LOW — `probe_window()` 는 차단을 유지한다 (저작자 주장 **검증됨**) · 기록 은닉만 남는다

- **location**: `audit_guard.py:127-141`, `:178-182`
- **confidence**: 100 (실측)

```
=== D2 — probe_window(): 기록만 분리되고 차단은 유지되는가
  창 안 열람 결과                : ('BLOCKED', 'AuditViolation')
  blocked_reads 증가             : 0
  probe_reads   증가             : 1
  창을 영구히 열어둔 뒤 열람       : ('BLOCKED', 'AuditViolation')
  blocked_reads 증가(누적)       : 0
```

**저작자 주장("기록만 분리하고 차단은 창 안팎이 동일")은 참이다.**  창을 닫지 않고 영구히
열어둬도 차단이 유지된다 — 탈취 경로가 아니다.  남는 것은 **탐지 회피**뿐이다:

```
### M8 probe_window 를 열어 차단 기록 은닉
  EXIT=1  미성립=['T-77-①','SELF-1']  hook 기록(프로브 밖)=열람 없음
```

헤드라인 신호(`프로브 밖: 열람 없음`)는 깨끗한 채로 남고 `프로브 안` 카운트만 6 → 7 로
증가하는데, **그 카운트는 어떤 Case 에도 소비되지 않는다.**  실 탈취 능력이 없으므로 LOW.
- **recommendation**: `probe_reads` 기대 건수를 `config.yaml` 앵커로 고정하면 창 남용이 red 가 된다.

## N-7 · LOW — 코퍼스 **메타데이터 오라클**이 열려 있다

- **location**: `audit_guard.py:78` (`READ_EVENTS` 에 `os.stat` 부재)
- **confidence**: 100 (실측)

```
BYPASS     os.stat(register)                  size=93904
BYPASS     os.path.exists(corpus)             True
```

내용은 못 읽지만 **존재·크기·mtime** 이 새어 나간다.  OD-3-A 를 "코퍼스를 열람하지 않는다"로
읽으면 경계선이고, "내용을 읽지 않는다"로 읽으면 범위 밖이다.  `L-AUDIT-SCOPE` 는 어느 쪽인지
말하지 않는다.  프로토타입이 register 행 수 같은 값을 크기로 추정하는 데 쓸 수 있는 통로다.
- **recommendation**: `os.stat` 를 `READ_EVENTS` 에 넣거나, 고지문에 "메타데이터 조회는
  판정 대상이 아니다"를 **명시**한다(현재는 침묵).

## N-8 · LOW — `sqlite3.connect(path)` 는 `open` 감사 이벤트를 발화시키지 않는다

- **location**: `audit_guard.py:78`
- **confidence**: 95 (실측 — 연결 성립 확인, 내용 반출은 미실증)

```
BYPASS     sqlite3.connect(path)              connected:<sqlite3.Connection object at 0x107e748b0>
```

SQLite VFS 가 libc `open()` 을 직접 부르므로 `open` 이벤트가 나지 않는다.  코퍼스는 CSV/MD 라
실제 내용 반출은 실증하지 못했다 — **결함 클래스의 존재 증명**으로만 제출한다:
"`open` 하나가 전부를 덮는다"는 `L-AUDIT-SCOPE` 의 근거가 **C 확장이 자체 VFS 를 쓰는 경로에는
성립하지 않는다.**  `ctypes` 와 같은 계열이며 그쪽은 고지돼 있다.
- **recommendation**: `L-AUDIT-SCOPE` 의 ctypes 항에 "자체 VFS 를 쓰는 C 확장(`sqlite3` 등)"을 병기.

---

## 추측과 실측의 구분

- **전부 실측**: S-1~S-9, S-11, N-1~N-7 은 PoC 실행 출력 또는 뮤테이션 대조 결과를 그대로 인용했다.
- **한정 표기**: N-8 은 연결 성립만 실측했고 내용 반출은 실증하지 못했음을 본문에 명시했다.
  S-9 는 out-of-band 준비가 필요함을 명시했다.  S-3 의 유니코드 축은 **악용 경로 없음**으로
  정직하게 닫았다 — 요청받은 축이라도 실현되지 않으면 지적하지 않는다.
- **고지된 한계와 결함의 분리**: subprocess·os.popen·ctypes·fd 표면은 `L-AUDIT-SCOPE` 안이므로
  BYPASS 표에 `[declared]` 로 표시하고 지적하지 않았다.

## 재현

```bash
S=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/\
2ed2dc33-ef7f-4f31-b91f-b5258c17c8dd/scratchpad
python3 $S/poc/pocA_read_battery.py     # S-2, S-3, N-7, N-8
python3 $S/poc/pocB_write_battery.py    # S-4
python3 $S/poc/pocC_path_equiv.py       # S-3, S-9
python3 $S/poc/pocD_hook_surface.py     # N-4, N-6, sys.audit/hook 제거
python3 $S/poc/pocD2_reentrancy.py      # N-1 (결정론적)
python3 $S/poc/mutate.py  all           # S-1, S-5, S-6, M5/M5b/M7/M7b/M8/M9
python3 $S/poc/mutate2.py               # N-1(N3), N-3(N4), N-5(N1/N2)
```

**원본 작업 트리 무편집 확인 (감사 종료 시점):**

```
$ find tools/spikes/phase0_contract -name '*.py' -o -name '*.yaml' | sort | xargs shasum -a 256
58bf1a94...  audit_guard.py          6aa7556d...  proto/__init__.py
c3ef1ec1...  proto/boundary.py       a4d22258...  proto/config.py
6e472103...  proto/config.yaml       6633e473...  proto/enforcement.py
916b53c5...  proto/floor.py          17e9f8d6...  proto/gates.py
e69d186b...  proto/register.py       bf39f94c...  test_contracts.py
   -> 감사 시작 시점 값과 12개 전부 동일
$ find tools/spikes/phase0_contract -name '__pycache__' -o -name '*.pyc'      # 0건
$ git status --porcelain tools/spikes/                                        # ?? tools/spikes/ (시작과 동일)
$ shasum -a256 tos-spec/.../EVIDENCE-REGISTER-002.csv                         # 코퍼스 무변경
```

모든 뮤테이션은 `<tmp>/repo/tools/spikes/phase0_contract/` 사본에서 수행했고,
`<tmp>/repo/.git` 을 만들어 예상 상대경로를 보존했다(그 사본의 기준선 앵커 5종이 원본과
동일함을 먼저 확인).
