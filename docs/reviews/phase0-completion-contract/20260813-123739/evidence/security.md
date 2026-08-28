# evidence — security lens · 재심 3라운드 (v2.7) · `tools/spikes/phase0_contract/`

```yaml
lens: security
mode: 재심 3라운드 — 해소 vs 회피 판별
scope: tools/spikes/phase0_contract/{audit_guard.py, proto/*.py, proto/config.yaml, test_contracts.py}
baseline_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd (작업 트리 untracked)
prior_verdict: .omc/review/20260813-094300/verdict.md (codex · needs-attention · 7건)
prior_evidence: .omc/review/20260813-094300/evidence/security.md
runtime: Python 3.14.5 · darwin 25.5.0 · APFS
method: 스크래치패드 사본 실행 뮤테이션 (정적 독해 아님) — 20 뮤테이션 · 전부 실행 출력 인용
verdict: 없음 — 이 문서는 증거다.  판정은 Codex 심판 레인 소관.
disposition: 해소 5 · 부분해소 1 · 해소(논거 과잉) 1 · 미해소 0 · 회피 0
new_findings: 3 (high 1 / low 2) + 검증 후 기각 1
prototype_modified: NO (12파일 shasum 감사 전후 동일 · __pycache__ 0 · 코퍼스 무변경 · git status 무변화)
```

## 총평 — 회피 신호 0

**4축(대조군 무력화 · 조건 완화 · 표면 이동 · 문구만)으로 찾았고 회피는 하나도 관측되지 않았다.**
대조군은 32 → **38건**으로 늘었고(축소 아님), 직전 CRITICAL 이 지목한 **정확한 뮤테이션 3종이
전부 red 로 뒤집혔으며**, #2 는 "Case 전건 green · 앵커 침묵 · 운영 게이트 단독 발화 → exit 1"
을 **실측으로 재현**했다.  일곱 건 중 다섯은 실질 해소다.

남는 것은 두 가지이고 성격이 다르다:

1. **#3 은 부분해소** — 세 층 중 두 층("pre-hook 실행문 0" · "동적 로드 이름 fail-closed")이
   **하나의 페이로드로 동시에 침묵**했고, 살아남은 것은 설정 핀 digest 하나뿐이다.
2. **#2 의 교정이 인접 우회로를 하나 만들었다 (신규 N-1)** — `probe_window()` 를 열고 위반하면
   새 운영 게이트가 **"열람 없음"** 을 보고하고 exit 0 으로 수렴한다.  v2.6 의 관통 패턴
   ("막는 도구 자체가 새 우회로를 만든다")이 v2.7 에서 한 번 더 재현됐다.

---

## 기준선 — 사본이 원본과 바이트 등가임을 먼저 고정

```
$ python3 tools/spikes/phase0_contract/test_contracts.py          # 원본 트리
대조군 38건 중 양방향 성립 38건
산문 앵커 대조: 리터럴=b12eac36c30a30fe · 방출=46e56cdd28cc5cdc · 실행코드=4bf9cabe9f9b168f ·
               소스바이트=28e51bd54b576e7e · Case산문=22de3ef00a40597f
운영 경계 위반(대조군 밖) — exit 결속: 없음
앵커 드리프트 — exit 결속: 없음
EXIT=0

$ python3 tools/spikes/phase0_contract/test_contracts.py          # <tmp>/repo 사본
… 앵커 5종 전부 동일 · 38/38 · EXIT=0
```

사본은 `<tmp>/repo/.git` + `<tmp>/repo/tos-spec/.../EVIDENCE-REGISTER-002.csv`(**디코이 16,040
바이트** — 실 코퍼스를 읽지 않는다)로 예상 상대경로를 보존했다.  모든 뮤테이션은 이 위에서 수행했다.

**부수 실측 — #5 교정이 즉시 물었다.** 사본 준비 중 `.git` 을 빈 디렉터리로 만들었더니
러너가 곧바로 red 를 냈다:

```
[T-77-④-GIT] 실제 루트 유효=False · top-level 일치=False
[T-77-④] 현위치 이탈=[".git 디렉터리에 git 내부 구조가 없다: 누락 ['HEAD', 'objects', 'refs']", …]
EXIT=1
```

v2.6 의 `exists()` 라면 통과했을 상태다.  의도하지 않은 양성 대조군이 하나 생겼다.

---

# 1부 · 직전 7건 처분

## #1 · CRITICAL — SELF-2 가 합성 dict 만 검증한다 → **해소**

심판이 지목한 **정확한 뮤테이션 3종**을 재주입했다.  이름은 남기고 producer 만 무력화한다.

```
### H1  "parked": rep.parked_limits(unchk_ids, waivers)  ->  "parked": []
  EXIT=1  미성립=['SELF-2', 'SELF-1']
  [SELF-2] … producer 생산 7/8 (침묵=['parked']) · 소비 7/8 (무시=['parked'])

### H2  "undeclared": rep.undeclared_limits(declared_limits)  ->  "undeclared": []
  EXIT=1  미성립=['SELF-2', 'SELF-1']
  [SELF-2] … producer 생산 7/8 (침묵=['undeclared'])

### H2b "digest_drift": list(digest_drift)  ->  "digest_drift": []
  EXIT=1  미성립=['SELF-2']
  [SELF-2] … producer 생산 7/8 (침묵=['digest_drift'])
```

**v2.6 에서 H1 은 SELF-2 를 침묵시켰다** (직전 증거 N-5: `미성립=['SELF-1']` — SELF-2 green).
지금은 셋 다 SELF-2 를 직접 red 로 만든다.  심판이 특별히 지목한
"`digest_drift` producer 에는 빈 tuple 을 전달한다" 도 H2b 로 닫혔다.

기전은 표면 이동이 아니라 정의역 확대다: `self_check_probes()` 가 이름마다 **실제 `Report`
위반을 심은 양성 대조군**을 만들고 `collect_self_checks()` 를 **통과시켜** ⒜생산 ⒝소비 ⒞직교성
셋을 동시에 본다.  합성 dict 는 `baseline_green` 확인에만 남는다.

앵커 드리프트의 독립 결속도 성립한다 — `anchor_report_failures(rep.anchors)` 는
`collect_self_checks()` 와 무관하게 `main()` 이 직접 소비하며, 아래 I1 에서 단독 발화를 실측했다.

- **처분**: **해소** · confidence 100

## #2 · HIGH — 대조군 밖 경계 위반이 종료 코드에 반영되지 않는다 → **해소**

### 요구된 재현: "Case 전건 green 인데 exit 1"

`t77_boundary` 는 `run_all()` 의 5번째, `fwd_a_0_superset_closure` 는 11번째다.  후자가 부르는
`floor.countable_kinds` 를 감싸 **T-77-SEPARATION 이 끝난 뒤** 위반을 만들고 **삼켰다**.
그 다음 러너가 인쇄해 준 새 앵커 값을 `config.yaml` 에 되써서 **앵커 채널을 침묵시켰다**.

```
### I1  늦은 삼켜진 위반 (1 pass)
  EXIT=1  대조군=38건 중 양방향 성립 37  미성립=['SELF-1']
  운영 게이트(exit 결속)=['감사hook·열람:open:코퍼스 디렉터리 접근: <REPO>/tools/tos-spec/src']
  앵커 게이트(exit 결속)=['소스바이트=00d1…!=28e5…', '실행코드=7d85…!=4bf9…']
  ### LATE-SWALLOWED AuditViolation

### I2  = I1 + config.yaml 앵커 동반 갱신
  EXIT=1
  대조군=38건 중 양방향 성립 38  미성립=[]        <-- Case 전건 GREEN
  앵커 이동=없음                                  <-- 앵커 채널 침묵
  운영 게이트(exit 결속)=['감사hook·열람:open:코퍼스 디렉터리 접근: <REPO>/tools/tos-spec/src']
  hook 기록 창밖=열람 ['open:코퍼스 디렉터리 접근: …'] · 쓰기 없음
  ### LATE-SWALLOWED AuditViolation
```

**요구된 그림 그대로다.** 38/38 GREEN · 앵커 이동 0 · 그럼에도 EXIT=1, 그리고 그 1 을 만든 것은
**가드 기록 채널 단독**이다.  v2.6 이라면 정확히 여기서 exit 0 이었다.  #2 의 교정은 실재하고
하중을 받는다.

### `claim_operational_records` seam — 시험했고 성립 경로를 찾지 못했다

저작자가 스스로 seam 이라 인정한 지점이다.  "정확히 1건짜리 운영 위반이 대조군 기록을 대체"
하려면 `len(blocked_reads) == 1` 인 채로 그 1건이 **공격자 것**이어야 한다.  두 경우 다 막힌다:

```
### MUT-A  대상이 AuditViolation 을 삼키고 모듈 레벨에서 코퍼스 열람 (창 밖 · 이른 시점)
  EXIT=1  미성립=['T-77-①', 'T-77-SEPARATION', 'SELF-1']
  hook 기록 창안= … 대조군 이관(창 밖 의도적) 0건        <-- 이관 불성립
  운영 게이트=['감사hook·열람:…EVIDENCE-REGISTER-002.csv', '감사hook·열람:…/tos-spec/src']
```

- **이른 위반**: 러너 자신의 대조군 열람이 더해져 `len==2` → `claim(1)` 이 `[]` 를 반환 →
  `len(claimed)==1` 이 거짓 → **T-77-SEPARATION red**.  동시에 `outside_before == 0` 도 거짓이라
  방향①까지 깨진다.  두 겹이 독립으로 잡는다.
- **늦은 위반**: 이관 이후에 쌓이므로 `blocked_reads` 에 그대로 남아 **운영 게이트가 발화**(I2).
- `claim_operational_records` 는 `blocked_reads` 만 이관한다 — `blocked_writes` 는 이관 불가라
  더 엄격하다.  개수 정확일치 요구는 실제로 잉여 위반을 숨기지 못하게 한다.

의도적 프로브와 운영 위반의 분리는 유지되면서도 삼켜진 위반이 새지 않는다.

- **처분**: **해소** · confidence 100
- **단, 이 교정이 만든 인접 우회로가 있다 → 신규 N-1 참조.**

## #3 · HIGH — 로드 순서 검사가 pre-hook 실행과 동적 import 를 보지 못한다 → **부분해소**

### 실제로 개선된 것 (회피 아님)

hook 설치가 `audit_guard.py:296` 으로 올라갔고, 러너의 `sys.path.insert` 가 제거됐으며,
`_ARMED_SNAPSHOT`/`bootstrap_witness()` · 구간 digest 핀 2종 · 금지 이름 34종이 추가됐다.
이 중 `bootstrap_witness` 는 실제 방어다 — 스냅샷 **이전**에 `proto` 를 동적 로드하면 red 가 된다.

### 그러나 "pre-hook 구간 실행문 0" 은 **정의상의 산물**이다

`_INERT_STATEMENTS` 가 `ast.Assign`·`ast.AnnAssign` 을 무조건 inert 로 분류한다.  RHS 가
호출식이어도 실행문으로 세지 않는다.  구간을 직접 계수했다:

```
--- audit_guard.py : 최상위문 39 · 러너가 세는 '실행문' 0 · 구간 내 실제 호출식(ast.Call) 39
       CALL: CORPUS_DIR.rstrip('/')          CALL: CORPUS_DIRNAME.casefold()
       CALL: REGISTER_PREFIX.casefold()      CALL: frozenset('wax+')
       CALL: frozenset(READ_EVENTS)          CALL: frozenset(WRITE_EVENTS)
       CALL: frozenset({str, bytes, Path, …}) CALL: threading.local()
       CALL: frozenset(sys.modules)          … (나머지는 정의 본문 내부)
--- test_contracts.py : 최상위문 14 · 러너가 세는 '실행문' 0 · 구간 내 실제 호출식 2
       CALL: Path(__file__).resolve()        CALL: Path(__file__)
```

모듈 본문 레벨에서 **실제로 실행되는 호출이 audit_guard.py 9건 · 러너 2건** 있는데 러너는
`pre-hook 실행문 0건/audit_guard.py 0건` 이라 인쇄한다.  `L-AUDIT-BOOTSTRAP` 은 이것을
"⒜ 두 파일 모두 pre-hook **실행문 0** 이 **구조 요구사항**" 이라 적는다 — 요구사항이 아니라
분류 규약이다.

### 하나의 페이로드가 세 층 중 두 층을 동시에 침묵시켰다

`_ARMED_SNAPSHOT` **뒤**, `sys.addaudithook` **앞**에 dict-subscript 형태의 동적 import 를 넣었다.
`__builtins__['__import__']` 는 `ast.Name`/`ast.Attribute` 노드를 만들지 않으므로 금지 이름
목록에 잡히지 않고, `ast.Assign` 이므로 실행문으로도 세어지지 않는다.

```
### F2  _SNEAK = __builtins__['getattr'](__builtins__['__import__']('proto.register'), …)
  EXIT=1  미성립=['T-77-AUDIT', 'SELF-1']
  [T-77-AUDIT] import 순서 audit[132]<proto[133,134]=True
               · pre-hook 구간 문제=['audit_guard.py: pre-hook 구간 digest 1a48…!=4e72…']
               · 러너 pre-hook 실행문 0건/audit_guard.py 0건       <-- ⒜ 침묵
               · 설치 스냅샷 위반=없음                             <-- bootstrap_witness 침묵
```

`proto.register` 가 **hook 설치 전에 로드·실행**됐는데:

| 층 | 결과 |
|---|---|
| ⒜ pre-hook 실행문 0 (구조 요구사항이라 주장) | **0건 보고 — 침묵** |
| ⒝ 동적 로드·I/O 이름 34종 fail-closed | **`dynamic` 비어 있음 — 침묵** |
| `bootstrap_witness()` 스냅샷 검증 | **위반 없음 — 침묵** (스냅샷 뒤에 넣었으므로) |
| ⒞ 구간 `ast.unparse` digest 핀 | **발화 — 유일하게 잡음** |

부수 확인(`### E`, 같은 형태를 `_READ_ARMED` 앞에 주입)도 동일하게 digest 만 발화했다.

살아남은 한 층은 `config.yaml:119 anchor_prehook_audit_guard` 라는 **설정 핀**이다 — 아래 N-1 의
1-pass 갱신과 같은 계열이며, `L-SELF-VISIBILITY` 가 스스로 "폐쇄가 아니라 가시화" 라 적은 것이다.

- **처분**: **부분해소** (실질 강화 있음 · 주장 범위가 실제보다 넓음) · confidence 100
- **권고**: ⑴ `_INERT_STATEMENTS` 에서 `Assign`/`AnnAssign` 을 빼고 **RHS 가 `ast.Call` 을
  포함하면 실행문**으로 계수하라(현 구간은 그러면 audit_guard 9 · 러너 2 로 정직해진다).
  ⑵ 금지 이름 판정을 `Name`/`Attribute` 에 더해 **`ast.Constant` 문자열**까지 확장하라 —
  dict-subscript·`getattr` 문자열 경로가 지금 전부 뚫린다.  ⑶ `L-AUDIT-BOOTSTRAP` 의
  "구조 요구사항" 표현을 실측치에 맞게 정정하라.

## #4 · HIGH — 프로세스 전역 재진입 플래그 → **해소**

### 스레드 격리 — v2.6 의 결정론적 PoC 를 그대로 재주입

```
### MUT-C  reentrancy_probe() 로 이 스레드의 재진입을 켠 채 다른 스레드가 코퍼스 열람
  ### THREAD-RESULT {'e': 'AuditViolation'}        <-- BLOCKED
  EXIT=1  미성립=['T-77-①', 'T-77-SEPARATION', 'SELF-1']
```

v2.6 에서 이 형태는 `BYPASS` + 실 register 93,865 바이트 탈취 + `blocked_writes: 0` 이었다.
지금은 다른 스레드가 그대로 무장 상태다.

### 화이트리스트 밖 타입 — 4종 전부 fail-closed

```
### MUT-D  경로 타입 우회 배터리
  ### TYPE str 서브클래스   : AuditViolation      (기록: "판정 불가 경로 타입(fail-closed): S")
  ### TYPE 커스텀 PathLike : AuditViolation
  ### TYPE bytes          : AuditViolation
  ### TYPE Path           : AuditViolation
```

`type(path) in _SAFE_PATH_TYPES` 는 **정확 일치**라 서브클래스가 제외된다 —
`__fspath__`/`__str__` 을 덮어쓴 서브클래스로 hook 안에서 사용자 코드를 돌리는 경로가 닫혔다.
러너의 `T-77-REENTRANT` 는 자기신고가 아니라 구조 파생(`isinstance(_REENTRANT, threading.local)`)
+ 실물(다른 스레드 차단 · 적대적 PathLike · `__fspath__` 총 0회 중 hook 안 0회)로 관측한다.

**남는 것(고지됨)**: `_PROBE_DEPTH` 는 여전히 프로세스 전역이라 창이 열린 동안 다른 스레드의
기록도 프로브 쪽으로 간다 — `L-AUDIT-PROBE-THREAD` 가 등재했고 차단 자체엔 영향이 없다.
다만 아래 N-1 과 결합하면 기록 은닉 표면이 넓어진다.

- **처분**: **해소** · confidence 100

## #5 · MEDIUM — repo 루트 검증이 `.git` 존재만 신뢰한다 → **해소**

빈 `.git` 디렉터리는 앞서(기준선 절) 즉시 red 가 됐다.  **위조 총비용을 실측**했다:

```
=== 디렉터리형 ===  mkdir .git && : > .git/{HEAD,objects,refs}    (0바이트 파일 3개)
  EXIT=0  대조군 38/38  [T-77-④-GIT] 실제 루트 유효=True · top-level 일치=True

=== 파일형 ===      .git = "gitdir: <dir>"  +  <dir>/HEAD (0바이트)
  findings = 없음(통과)
  비용 = .git 파일 1(포인터) + 디렉터리 1 + 0바이트 HEAD 1
```

`GIT_DIR_REQUIRED` 항목은 **존재만** 보므로 0바이트 일반 파일로 충분하다(디렉터리일 필요 없음).
그러나 `L-LOCATE-FORGE` 는 정확히 그렇게 적는다 — "유효한 `.git` 구조 한 벌(**디렉터리형이면
세 항목, 파일형이면 포인터와 `HEAD`**)". 실측과 일치한다.  v2.6 의 과대 서술("`.git` 디렉터리가
필요")도 노트 안에서 **거짓이었다고 명시 정정**했다.  "유효한" 이라는 낱말이 약간 후하다는 것이
유일한 흠이며 괄호 안 열거가 실제 요구를 정확히 말한다.

`repository_top_level` 은 장식이 아니다 — 아래 J1 에서 **실제로 잡는 층**임이 확인됐다.

- **처분**: **해소** (비용 1파일 → 3~4 엔트리 · 고지 정확) · confidence 100

## #6 · MEDIUM — 보호 대상 판정이 inode 별칭을 놓친다 → **해소(정책 축소가 정직) · 논거는 과잉**

### 축소가 서술한 잔여가 정확히 실재한다

하드링크를 **out-of-band 로 준비**한 뒤(실행 중 `os.link` 는 차단되므로) 측정했다:

```
정본                   판정=차단  실열람=BLOCKED            dev=16777232 ino=44553912
하드링크(무해한 이름)      판정=통과  실열람=BYPASS bytes=16040 dev=16777232 ino=44553912
-> 동일 inode: True
```

`L-INODE-ALIAS` 는 이것을 정확히 적는다 — 경로명 순수 함수라는 것, `resolve()` 로 복원되지
않는다는 것, **"실행 중 `os.link` 차단은 이미 준비된 별칭을 막지 못한다"**, bind mount 도
정의역 밖이라는 것까지.  과소 서술이 없다.  `T-77-INODE` 가 구조(AST 로 `stat`/`st_ino`/`samefile`
미사용 확인)와 값(보호 이름 차단 · 무해한 이름 통과) 양쪽에서 축소를 관측한다.

### 다만 "(A) 는 불가능하다" 는 논거가 자기 강제 경계보다 강하다

주장: *"보호 대상 identity 집합을 만들려면 코퍼스 디렉터리를 열거해야 하고 그 열거 자체가
OD-3-A 위반이다."*  실측:

```
os.stat(코퍼스 register) = BYPASS (감사 이벤트 없음) size=16040 ino=44553912
러너가 실제로 여는 코퍼스 경로: <REPO>/tos-spec/src   (T-77-SEPARATION 이 매 실행 연다)
T-77-AUDIT 프로브가 여는 register 접두 이름: EVIDENCE-REGISTER-002.csv 형태
```

⑴ 자기 가드는 `os.stat` 을 **접근으로 보지 않고**(`READ_EVENTS` 에 없음), ⑵ 러너 자신이 매 실행
코퍼스 경로를 구성해 열고 있다.  따라서 "identity 관련 작업 = OD-3-A 위반" 은 자기 강제
경계보다 넓은 진술이다.  **좁은 형태의 주장(완전한 canonical 집합에는 `listdir` 이 필요하다)은
참**이므로 (B) 선택 자체는 정당하고, 이것은 회피가 아니라 **논거 과대**다.

### 부수 관측 — 대조군이 약점을 고정한다 (J2)

(A) 를 실제로 구현해 보았다 (`path_violation` 에 `(st_dev, st_ino)` 대조 한 겹 추가):

```
### J2  (A) inode 대조를 실제로 구현
  EXIT=1  미성립=['T-77-AUDIT', 'T-77-INODE', 'SELF-1']
  [T-77-INODE] … inode 동일성 조회 사용=True …          <-- 방향① 이 `not identity_used` 를 요구
```

`T-77-INODE` 의 방향①이 **inode 조회의 부재**를 요구하므로, 완화책을 넣는 순간 대조군이 red 가
된다.  앵커형 Case 로서 의도된 설계이나(정책 정의역 핀), 결과적으로 **완화 구현이 대조군 + 설정
동시 편집을 요구하는 변경**이 됐다는 사실은 기록해 둘 가치가 있다.

- **처분**: **해소(축소 정직)** · 논거 과대 1건 · confidence 100
- **권고**: `L-INODE-ALIAS` 의 (A) 불가론을 "**완전한** canonical 집합 구성에는 열거가 필요하다"
  로 좁히고, `os.stat` 이 판정 대상이 아니라는 사실(메타데이터 오라클)을 같은 노트에 병기하라.

## #7 · MEDIUM — 런타임 정책 데이터가 앵커 정의역 밖 → **해소**

`T-79` 가 25개 이름을 `config.yaml:109 anchor_policy_values` 에 digest 로 결속하고 항목별
변형 208건을 전수 관측한다.  심판이 지목한 세 이름(`FIXTURE_CLAUSES`·`FORBIDDEN_SOURCE_TOKENS`·
`REQUIRED_KEYS`)이 전부 표 안에 있다.  **값을 라이브 모듈에서 읽으므로 런타임 대입도 잡힌다**는
주장을 두 뮤테이션으로 확인했다:

```
### H3  proto/register.py 에서 floor.VERIFIABLE_KINDS 를 런타임 대입
  EXIT=1  미성립=['T-79', 'SELF-1']
  [T-79] … 드리프트=['floor.VERIFIABLE_KINDS=94ee…!=4540…']

### H5  audit_guard.READ_EVENTS / WRITE_EVENTS 를 런타임 대입
  EXIT=1  미성립=['T-79', 'SELF-1']
  [T-79] … 드리프트=['audit_guard.READ_EVENTS=2348…!=eab2…', 'audit_guard.WRITE_EVENTS=e3b0…!=dbce…']
```

표 **밖**이라고 고지한 이름도 실제로 밖인지 확인했고, 고지대로 다른 층이 받는다:

```
### H6  _WATCHED = frozenset()  (L-POLICY-ANCHOR 가 표 밖이라 명시한 계열)
  EXIT=1  미성립=['T-77-AUDIT', 'T-77-REENTRANT', 'T-77-SEPARATION', 'SELF-1']
  [T-79]        드리프트=없음                       <-- 값 앵커는 침묵 (고지대로)
  [T-77-AUDIT]  hook 단독 차단 0/8                  <-- 실물 프로브가 잡는다
  hook 기록 창안=열람 0건 · 쓰기 0건
```

`_PROBE_DEPTH`·`_READ_ARMED`·`_WRITE_ARMED` 는 값이 아니라 상태라 표에서 빼고
`guard_record_violations()` 가 종료 시점에 셋 다 직접 확인한다(`audit_guard.py:724-731`) —
고지와 코드가 일치한다.  값 앵커가 **코드가 아니라 `config.yaml` 에 있다**는 점도 확인했다
(오케스트레이터가 직전 라운드에 붙인 설정 구동 제약 충족).

- **처분**: **해소** · confidence 100

---

# 2부 · 신규 발견

## N-1 · HIGH — `probe_window()` 가 #2 의 새 운영 게이트를 통째로 우회시킨다

- **location**: `tools/spikes/phase0_contract/audit_guard.py:358-377` (`probe_window`),
  `:248-252` (`_record`), `test_contracts.py:716-732` (`guard_record_violations`)
- **유형**: CWE-693 Protection Mechanism Failure (관측 채널 분기 남용) / 탐지 회피
- **confidence**: 100 (결정론적 실측 · 1-pass 수렴)

`_record()` 는 `_PROBE_DEPTH > 0` 이면 기록을 `probe_reads`/`probe_writes` 로 보낸다.
`guard_record_violations()` 는 `blocked_reads`/`blocked_writes` **만** 소비한다.
`probe_window()` 는 `audit_guard` 의 공개 API 이고 `proto/*` 어디서나 import 가능하다.
`probe_reads`/`probe_writes` 의 건수를 묶는 **설정 앵커는 존재하지 않는다** (`config.yaml` 전수 확인:
`anchor_*` 22키 중 프로브 기록 관련 0건).

리터럴·AST-fold 스캔까지 피하려고 토큰을 바이트 디코드로 조립한 페이로드를 `probe_window()`
안에서 실행했다:

```
### G1  probe_window 안 코퍼스 접근 (완전 난독화) — 1 pass
  EXIT=1  대조군=38건 중 양방향 성립 37  미성립=['SELF-1']
  운영 게이트(exit 결속)=없음                     <-- #2 가 만든 채널이 침묵
  앵커 게이트=['소스바이트=ea03…!=28e5…', '실행코드=6017…!=4bf9…']
  hook 기록 창밖=열람 없음 · 쓰기 없음             <-- 운영자가 읽는 헤드라인이 깨끗하다
  hook 기록 창안=열람 10건 (기준선 9건)            <-- 실제 기록은 여기로 샜다
  ### G-ATTEMPT-BLOCKED AuditViolation target= EVIDENCE-REGISTER-002.csv
  러너가 인쇄해 준 새 앵커 값: {'실행코드': '60179a3daaa52bf0', '소스바이트': 'ea0355c43a198e65'}

### G2  = G1 + config.yaml 앵커 동반 갱신 (러너가 인쇄한 값을 그대로 되씀)
  EXIT=0
  대조군=38건 중 양방향 성립 38  미성립=[]
  앵커 이동=없음
  운영 게이트(exit 결속)=없음
  hook 기록 창밖=열람 없음 · 쓰기 없음
  ### G-ATTEMPT-BLOCKED AuditViolation target= EVIDENCE-REGISTER-002.csv
```

**전건 GREEN · exit 0 · 헤드라인 "프로브 밖: 열람 없음"** 인데 그 실행 중 실제 register 파일에
대한 접근 시도가 있었고 가드가 그것을 탐지·차단·기록했다.  쓰기도 같다:

```
### B3  probe_window 안 os.mkdir
  EXIT=1  미성립=['SELF-1']            <-- Case 는 SELF-1(앵커) 하나뿐
  운영 게이트=없음 · hook 기록 창밖 쓰기 없음
  hook 기록 창안=… 쓰기 3건 (기준선 2건)
```

**중요한 한정**: `probe_window()` 는 **기록만** 분리하고 차단은 유지한다 — G1/G2 에서 실제
바이트는 0 이며 `AuditViolation` 이 그대로 났다.  따라서 이것은 **탈취 경로가 아니라 게이트
회피**다.  그러나 #2 의 교정이 주장하는 것이 정확히 "창 밖 `blocked_reads`/`blocked_writes` 가
독립적으로 exit 1 을 만든다" 이므로, 공격자는 **자기 위반을 '창 밖'이 아니게 만들기만 하면**
그 채널을 무력화한다.  남는 층은 디스크 편집을 보는 앵커뿐이고 그것은 **1-pass 로 수렴**하며
필요한 값은 러너가 친절하게 인쇄해 준다.

이것이 심판이 정식화한 관통 패턴의 14번째 재현이다 — **막는 도구(#2 의 새 관측 채널)가
자기 옆에 우회로(`probe_window`)를 하나 만들었다.**

- **recommendation**: ⑴ `probe_reads`/`probe_writes` 의 **기대 건수를 `config.yaml` 앵커로 고정**
  하라(현재 기준선 열람 9 · 쓰기 2 · 이관 1).  창 남용은 즉시 카운트 드리프트로 red 가 된다.
  ⑵ 더 나은 형태: `probe_window()` 가 **호출자 소스 위치**(`sys._getframe`)를 기록하고, 러너 자신의
  고정된 호출 지점 목록 밖에서 열린 창은 그 자체로 `guard_record_violations()` findings 가 되게
  하라 — 그러면 정당한 프로브와 남용이 구조로 갈린다.  ⑶ `L-AUDIT-PERSIST` 의
  "`probe_window()` 는 기록만 분리하고 차단은 창 안팎이 같다" 에 **"따라서 창을 여는 코드는
  운영 게이트에서 자기 기록을 감출 수 있다"** 를 병기하라 — 현재 어느 노트도 이 통로를 적지 않는다.

## N-2 · LOW — `policy()` 자기신고가 실제 강제 변수(`_WATCHED`)를 여전히 보고하지 않는다

- **location**: `audit_guard.py:301-310` (`policy()`), `:153` (`_WATCHED`), `:281`
- **confidence**: 100 (실측 · 직전 라운드 N-4 에서 변동 없음)

```
policy() 키 = ['probe_depth', 'read_armed', 'read_events', 'reentrancy', 'write_armed', 'write_events']
_WATCHED 보고 여부 = False
```

`_hook` 의 조기 필터는 `_WATCHED` 이고 `policy()` 는 그것을 보지 않는다.  H6 에서 확인했듯
`_WATCHED` 를 비우면 강제가 전면 해제되는데 `policy()` 는 계속 `armed=True` 를 인쇄하고
방출 노트도 움직이지 않는다.  **실물 프로브(`hook 단독 차단 0/8`)가 잡으므로 exit 결속에는
공백이 없다** — 자기신고 정확성 문제로만 남는다.  `L-POLICY-ANCHOR` 가 `_WATCHED` 계열을 표 밖
이라고 명시했으므로 미고지도 아니다.

- **recommendation**: `policy()` 가 `_WATCHED` 를 함께 보고하거나, `_WATCHED` 를
  `READ_EVENTS`/`WRITE_EVENTS` 에서 매 이벤트 파생하게 하면 괴리가 소멸한다(1행).

## N-3 · LOW — 앵커형 Case 가 완화책 구현을 red 로 만든다 (`T-77-INODE`)

- **location**: `test_contracts.py:1826-1836`
- **confidence**: 100 (J2 실측)

`T-77-INODE` 방향①이 `judge_fn is not None and not identity_used` 다.  즉 **`path_violation` 이
inode 동일성을 보지 *않는다*는 사실**을 성립 조건으로 삼는다.  #6 의 (A) 를 구현하면
그 자체로 대조군이 red 가 된다(J2 실측).  정책 정의역을 핀으로 고정하려는 의도는 이해되나,
결과적으로 완화 구현이 "코드 + 대조군 + 설정" 3곳 동시 편집을 요구하게 됐다.

- **recommendation**: 방향①을 `identity_used` 의 **부재**가 아니라 **선언된 정책 모드와의 일치**
  (`config.yaml` 의 `policy_domain: pathname|identity`)로 바꾸면, 정의역 핀은 유지하면서 완화
  구현이 정상 경로(설정 1줄 변경)가 된다.

## 검증 후 기각 — `FsProbe` seam 은 무탐지 우회가 아니다

요청받은 축이라 시험했고 **지적으로 제출하지 않는다.**  `boundary.REAL_FS` 재바인딩은
기본 인자가 정의 시점에 결속되므로 무효였고, `__defaults__` 를 직접 교체해 항상-통과로 만들면
`git_marker_findings` 는 뚫리지만 `repository_top_level` 이 즉시 어긋난다:

```
  boundary.REAL_FS 재바인딩 후 = ['repo 루트 표지(.git) 부재: …']   <- 무효
  git_marker_findings.__defaults__ 교체 후 = 없음(통과)             <- seam 주입은 성립

### J1  러너 안에서 __defaults__ 교체
  EXIT=1  미성립=['T-77-④', 'T-77-④-GIT', 'SELF-1']
  [T-77-④-GIT] 실제 루트 유효=True · top-level 일치=False          <- 실물 음성 대조군이 잡는다
```

`repository_top_level(_HERE)` 가 "무엇이든 통과" 상태에서 `_HERE` 자신을 루트로 반환해
기대 루트와 어긋난다.  **seam 은 있으나 그 seam 을 눌렀을 때 red 를 내는 실물 층이 존재한다.**
`probe_depth`·`bootstrap_witness`·`reentrancy_probe`·`claim_operational_records` 도 각각
위(#2·#3·#4)에서 눌러 봤고 새 공격면으로 성립한 것은 `probe_window`(N-1) 하나다.

---

## 이월 — 직전 라운드에서 열린 채 남은 항목 (재확인만, 새 지적 아님)

| 항목 | 상태 | 근거 |
|---|---|---|
| `os.stat` 메타데이터 오라클 (직전 N-7) | **여전히 열림** · 미고지 | `os.stat(register)` BYPASS size=16040 ino=44553912. #6 의 (A) 불가론이 이 사실과 충돌하므로 이번엔 논거 정정 근거로도 쓰인다 |
| `sqlite3`/`ctypes`/`subprocess` VFS (직전 N-8) | 변동 없음 | `L-AUDIT-SCOPE` 고지 범위 — 지적 아님 |
| `os.mkfifo`/`os.mknod` 잔존물 (직전 S-4) | 변동 없음 | 감사 이벤트 없음 · 내용 반출 능력 없음 |
| 2-pass 앵커 갱신 자기참조 (직전 N-3) | 변동 없음 · **1-pass 수렴 재확인** | G2·I2 에서 각각 1회 갱신으로 수렴. `L-SELF-VISIBILITY` 는 "3곳" 이라 적지만 실측은 **코드 1 + 설정 1 = 2곳** |

## 시크릿·인젝션·역직렬화 축 — 결함 0 유지

`eval`/`exec`/`pickle`/`marshal`/`yaml.load`/`os.system`/`__import__` grep 히트 0건
(러너의 `PREHOOK_FORBIDDEN_NAMES` 리터럴 정의는 제외).  KIS API 키·계좌·OpenAI/KRX/DART 자격증명
0건 — 이 프로토타입은 자격증명을 다루지 않는다.  외부 입력은 repo 내 `proto/config.yaml` 하나이며
`config.py` 의 자체 `key: value` 한 줄 파서로 읽는다(YAML 파서 미사용).  `argv`·환경변수·stdin 미사용.

---

## 추측과 실측의 구분

- **전부 실측**: #1~#7 처분과 N-1·N-2·N-3 은 모두 뮤테이션 실행 출력을 그대로 인용했다.
  총 20 뮤테이션(A·B·B2·B3·C·D·E·F·F2·G1·G2·H1·H2·H2b·H3·H5·H6·I1·I2·J1·J2) + 4 직접 프로브.
- **탈취 능력의 정직한 한정**: N-1 의 G1/G2 에서 **실제로 읽힌 바이트는 0** 이다(`AuditViolation`
  그대로 발생).  게이트 회피이지 탈취가 아니라고 본문에 명시했다.  #6 의 하드링크만이 실제
  16,040 바이트를 읽었고 그것은 **out-of-band 준비물**을 요구한다(본문 명시).
- **디코이 사용**: 모든 탈취 시험은 스크래치패드의 디코이 CSV(16,040 B)를 대상으로 했다.
  실 코퍼스 `EVIDENCE-REGISTER-002.csv` 는 읽지 않았고 shasum 무변경을 확인했다.
- **요청받았으나 지적하지 않은 축**: `FsProbe` seam(위 "검증 후 기각"), `claim_operational_records`
  seam(성립 경로 미발견 — #2 본문에 시험 내용 기록).  렌즈를 채우려고 만들지 않았다.

## 재현

```bash
S=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/\
2ed2dc33-ef7f-4f31-b91f-b5258c17c8dd/scratchpad
python3 $S/poc/mut.py            # A(삼킴) B(창) C(스레드) D(타입)
python3 $S/poc/mut2.py           # B2 B3 E F  + pre-hook 구간 정적 계수
python3 $S/poc/mut3.py           # G1 G2  (N-1 · 1-pass 수렴)
python3 $S/poc/mut4.py           # H1 H2 …  (#1 producer 양성 대조군)
```

## 원본 작업 트리 무편집 확인 (감사 종료 시점)

```
$ find tools/spikes/phase0_contract -type f \( -name '*.py' -o -name '*.yaml' \) | sort | xargs shasum
f892e575…  audit_guard.py          028ea8ab…  proto/__init__.py
9d263568…  blocks_gate_consumption.py  51cefa94…  proto/boundary.py
70439afa…  proto/config.py         840fc8eb…  proto/config.yaml
f800f8b9…  proto/enforcement.py    dfdb2f56…  proto/floor.py
6a098c87…  proto/gates.py          c70e4fef…  proto/register.py
a25203d8…  sweep_deprecated_vocabulary.py  e0224cbd…  test_contracts.py
   -> diff (시작 12행 vs 종료 12행) = 없음.  12개 파일 전부 동일.

$ find tools/spikes/phase0_contract -name '__pycache__' -o -name '*.pyc' | wc -l     # 0
$ git status --porcelain -- tools/spikes/ tos-spec/                                  # ?? tools/spikes/
                                                                                     # ?? tos-spec/…/decisions/
                                                                                     #    (시작과 동일)
$ shasum tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv
  3fe05c50139d1ac6801aa33b5dd3a4f5db3027c3     # 코퍼스 무변경
$ python3 tools/spikes/phase0_contract/test_contracts.py                             # EXIT=0 · 38/38
   앵커 5종 전부 감사 시작 시점과 동일
$ ls <repo>/__probe* <repo>/benign* <repo>/__fakeroot                                # 없음
```

모든 뮤테이션·하드링크·가짜 `.git` 준비물은 `<tmp>/repo/` 사본 안에서만 만들었고 종료 시 제거했다.
