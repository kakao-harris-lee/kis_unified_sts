# evidence — security lens · 재심 4라운드 (v2.8) · `tools/spikes/phase0_contract/`

```yaml
lens: security
mode: 재심 4라운드 — 해소 / 정직등재 / 부분해소 / 미해소 / 회피 판별
scope: tools/spikes/phase0_contract/{audit_guard.py, proto/*.py, proto/config.yaml, test_contracts.py}
baseline_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd (작업 트리 untracked)
prior_verdict: .omc/review/20260813-123739/verdict.md (codex · needs-attention · 6건)
prior_evidence: .omc/review/20260813-123739/evidence/security.md
runtime: Python 3.14.5 · darwin 25.5.0 · APFS
method: 스크래치패드 사본 실행 뮤테이션 (정적 독해 아님) — 32 뮤테이션 · 전부 실행 출력 인용
verdict: 없음 — 이 문서는 증거다.  판정은 Codex 심판 레인 소관.
disposition: 해소 2 · 정직등재 1 · 부분해소 3 · 미해소 0 · 회피 0
new_findings: 3 (medium 1 / low 2) + 검증 후 기각 1
prototype_modified: NO (12파일 shasum 감사 전후 동일 · __pycache__ 0 · 잔존물 0 · 코퍼스 무변경)
```

## 총평

**회피 신호 0.**  운영자 처분 B 는 정직하게 이행됐고, 대조군은 38 → **39건**, 값 앵커 정의역은
25 → **77항**으로 넓어졌다(둘 다 축소 아님).  #5·#6 은 실질 해소이고, critical 은 **정직등재**다 —
`L-EXIT-ROOT` 노트가 서술한 동작을 **실행으로 재현했고 서술과 정확히 일치했다.**

남는 것은 세 건이고 전부 같은 성격이다: **v2.8 의 교정이 심판이 지목한 정확한 페이로드는 닫았으나,
같은 결함 클래스의 형제 형태가 열려 있다.**

| # | 심판이 지목한 페이로드 | v2.8 이후 | 형제 형태 | 상태 |
|---|---|---|---|---|
| #3 | 전역 `_PROBE_DEPTH` 로 창 남용 | **닫힘** (3층 독립 검출 실측) | `compile(src,"test_contracts.py")` 로 호출 지점 사칭 | 열림 |
| #4 | `_SNEAK = __builtins__['__import__'](…)` | **닫힘** (계수·이름 양층 발화 실측) | 클래스 본문 실행 | 열림 |
| #2 | `__module__` 자기신고 | **닫힘** (`co_filename` 결속) | 판독기 2지점 동시 위조 | 열림 **(저작자가 정확히 그렇게 적었다)** |

---

## 기준선 — 사본이 원본과 등가임을 먼저 고정

```
$ python3 tools/spikes/phase0_contract/test_contracts.py            # 원본 트리
대조군 39건 중 양방향 성립 39건
감사 hook 차단 기록 — 인가된 프로브 창 안(토큰별 열람:쓰기):
  {'t77-audit-battery': (6,2), 't77-cross-thread': (1,0), 't77-reentrant': (1,0), 't77-separation': (1,0)}
  · 인가되지 않은 창 없음 · 대조군 이관(창 밖 의도적) 1건
산문 앵커: 리터럴=5e39cb998947f38c · 방출=d64bb6dd17dde55f · 실행코드=9b29dfdccb8e9262 ·
          소스바이트=1d741553e31d238a · Case산문=a2f8fa2da5d390de
운영 경계 위반(대조군 밖) — exit 결속: 없음 / 앵커 드리프트 — exit 결속: 없음
EXIT=0

$ python3 tools/spikes/phase0_contract/test_contracts.py            # <tmp>/r4/repo 사본
… 앵커 5종 전부 동일 · 39/39 · EXIT=0
```

사본은 `<tmp>/r4/repo/.git`(HEAD·objects·refs) + **디코이 CSV 21,015 바이트**로 상대경로를
보존했다.  실 코퍼스는 읽지 않았다.

---

# 1부 · 직전 6건 처분

## #1 · CRITICAL — 최종 종료 판정이 단일 교체 가능 함수에 귀결된다 → **정직등재**

운영자가 처분 **B**(한계 등재 + 주장 철회)를 선택했으므로 "닫혔는가"가 아니라
**"정직하게 등재됐는가"** 로 본다.  세 축 전부 실측했다.

### ⑴ 등재의 구조적 강제 — 기계 검사가 붙어 있다

```
config.yaml:47   deferred_owner_tracks: L-EXIT-ROOT=Phase 1
config.yaml:36   declared_limit_ids: … ,L-EXIT-ROOT, …
config.py:43     "deferred_owner_tracks" ∈ REQUIRED_KEYS   -> 부재 시 load_config 중단
test_contracts.py:3158-3164
  deferral_problems = [ … for lid, track in sorted(deferrals.items())
                        if not track or lid not in declared_limits ]
```

`SELF-3` 이 ⑴ 대상 노트가 `declared_limit_ids` 에 실제로 있는지 ⑵ track 이 비어 있지 않은지를
fail-closed 로 본다.  **미등재 이연을 누락과 구별한다**는 서술이 코드로 강제된다.

### ⑵ 노트 본문이 실제 동작과 일치하는가 — 실행으로 재현

`L-EXIT-ROOT` 주장: *"그 이름을 0 만 돌려주게 재바인딩하면 red Case·운영 경계 위반·앵커
드리프트를 전부 탐지하고 출력한 상태에서도 exit 0 이 된다."*

```
### M1  red 조건 3종 실제 주입 (floor.VERIFIABLE_KINDS 축소 + blocked_reads 1건)
  BASE      EXIT=0
  RED-ONLY  EXIT=1
     대조군 39건 중 양방향 성립 36건
     미성립: ['T-77-SEPARATION', 'T-79', 'SELF-1']
     운영 경계 위반(대조군 밖) — exit 결속: ['감사hook·열람:open:코퍼스 디렉터리 접근: <조작>', …]
     앵커 드리프트 — exit 결속: ['Case산문=c1c7280a8ad473bf!=a2f8fa2da5d390de']
  REBIND    EXIT=0                                   <-- exit_status = lambda …: 0
     미성립: ['T-77-SEPARATION', 'T-79', 'SELF-3', 'SELF-1']
     운영 경계 위반(대조군 밖) — exit 결속: ['감사hook·열람:open:코퍼스 디렉터리 접근: <조작>', …]
     앵커 드리프트 — exit 결속: ['Case산문=49d8…!=a2f8…', '실행코드=b429…!=9b29…']
  ### L-EXIT-ROOT 노트 주장 성립 = True
```

**서술 그대로다.**  4개 Case red · 운영 위반 발화 · 앵커 드리프트 2종 — 전부 탐지되고 출력됐는데
EXIT=0.  노트는 과소도 과대도 아니다.

부수 실측: 노트는 `exit_wiring()` 이 소스 텍스트만 보므로 막지 못한다고 적는데, 실제로는
`SELF-3` 의 **행동 프로브**(`flipped`)가 순진한 재바인딩을 잡는다(`채널별 판정 반전 0/3`).
그러나 그 red 도 같은 함수를 경유하므로 무의미하고, **선택적 재바인딩이면 그 탐지마저 사라진다**:

```
### M1b  n = len(failed)+len(violations)+len(anchors) <= 1 이면 정직 처리, 아니면 0
  SELECTIVE-REBIND  EXIT=0
     [SELF-3] … 채널별 판정 반전 3/3 ['Case','가드 기록','앵커 드리프트']   <-- SELF-3 도 GREEN
     미성립: ['T-77-SEPARATION','T-79','SELF-1']
```

노트가 말한 결함 클래스의 **더 강한 형태**이며 노트의 정의역 안이다.  새 지적으로 올리지 않는다.

### ⑶ 주장 철회 전수 스윕 — 완전한가

`전부 결속`·`전건 결속`·`전수 결속`·`모두 exit`·`자기증명` 계열을 4개 파일 전수 grep 했다:

```
$ grep -n "전수 결속|전부 결속|전건 결속|모두 결속|전부 exit|모두 exit|자기증명" *.py proto/*.py proto/config.yaml
test_contracts.py:111   … `L-EXIT-ROOT` 로 등재하고, **이 러너가 최종 exit 자체까지 자기증명한다는
                            주장을 본문 전체에서 제거했다.**                       <- 부정
test_contracts.py:1098  … Phase 1 트랙으로 이연됐다.  자기증명한다고 적지 않는다.      <- 부정
test_contracts.py:3202  … exit 자체까지 자기증명한다고 주장하지 않는다.**             <- 부정
test_contracts.py:3591  … 이 러너는 최종 exit 을 자기증명하지 않는다.                 <- 부정
test_contracts.py:3601  # **세 발견 채널이 전부 exit 에 닿는다** (주석 · 배선 서술)     <- 참 (M1 RED-ONLY 로 실증)
```

**히트 5건 중 4건이 부정문이고 나머지 1건은 실측으로 참이다.**  잔존 긍정 주장 0.
철회는 6개 표면에 병기돼 있다 — 러너 모듈 docstring(v2.8 절)·`exit_status` docstring·
`SELF-3` docstring·`main()` 출력(`미검사(종단)` 행)·`L-EXIT-ROOT` 노트 본문·
`audit_guard.py` 모듈 docstring(:41-48)·`config.yaml`(:8-11).  `L-SRC-ANCHOR`·`L-AUDIT-PERSIST` ·
`L-POLICY-ANCHOR` 도 각각 "이 앵커/게이트의 판정도 결국 `exit_status()` 를 경유한다"를 병기한다.
v2.4 가 받은 "본문 15곳 stale" 의 재현은 **관측되지 않았다.**

- **처분**: **정직등재** · confidence 100
- **잔존(비지적)**: `deferred_owner_tracks` 의 track 값은 비어 있지 않은 문자열이면 통과한다 —
  `Phase 1` 이 실재 트랙인지는 기계 검사 대상이 아니다.  처분 B 의 내재적 성질이다.

## #2 · HIGH — import 로 복사한 설정 함수가 앵커 정의역에서 빠진다 → **부분해소** (저작자 서술 정확)

### 교정은 실재한다

```
test_contracts.py:477-487  binding_file()  ->  os.path.basename(obj.__code__.co_filename)
test_contracts.py:452-458  _module_code_parts: `__code__` 를 가진 객체는 **소속과 무관하게 전부**
config.yaml:130            runner.MODULE_BINDINGS=754f56f1df5c2d86   (값 앵커 등재)
test_contracts.py:3241-3257  T-80: independent_settings 이중 판독 + 바인딩 출처 대조
```

`__module__` 자기신고는 정의역 판정에서 **완전히 사라졌다**.

### 저작자의 자기 서술이 정확한지 — 위조 지점을 세어 실측

저작자는 `independent_settings` docstring 에 스스로 적었다:
*"**폐쇄가 아니다**: 두 판독기가 같은 프로세스에 있으므로 둘 다 갈아끼우는 변조는 이 층을 지난다.
비용을 1 지점에서 2 지점으로 올릴 뿐이며…"*

실제 정책 축소(`boundary.FORBIDDEN_ARTIFACTS` 를 런타임에 1개로)를 심고 위조 지점을 늘려 갔다:

```
### F0  축소만 (위조 0지점)
  EXIT=1  미성립: ['T-77-③', 'T-79', 'SELF-1']
### F1  위조 1지점 (config.load_config 만)
  EXIT=1  미성립: ['T-77-③', 'T-80', 'SELF-1']      <-- T-79 는 통과했으나 T-80 이 잡는다
### F2  위조 2지점 (+ T.independent_settings)
  EXIT=1  미성립: ['T-77-③', 'SELF-1']              <-- T-79·T-80 둘 다 통과
```

**저작자의 서술이 정확히 맞다.**  1지점이면 `T-80` 이 잡고, 2지점이면 설정 판독 축은 전부 지난다.
과소 서술도 과대 서술도 없다 — 이 종류의 자기 보고가 실측과 일치한 것은 이 감사 4라운드에서
처음이다.

부수 관측(저작자가 공을 주장하지 않은 것): F2 에서도 축소를 잡은 것은 `T-77-③` — 금지
아티팩트를 **항목별로 하나씩 표적** 삼는 실물 대조군이다.  설정 판독 축과 독립인 행동 층이 남아
있다는 사실은 `T-80` 의 서술 범위 밖이며, 저작자는 그것을 자기 공으로 적지 않았다.

- **처분**: **부분해소** (자기신고 제거는 실질 · 잔여는 정확히 고지) · confidence 100

## #3 · HIGH — 전역 probe_window 가 실제 위반을 exit 비결속 버킷으로 재분류 → **부분해소** · 신규 잔여 **미등재**

### 실질 강화 3층 — 전부 실측으로 확인

```
### A3  창 없이 코퍼스 열람 (_io 표면)
  EXIT=1  운영 경계 위반: ['감사hook·열람:open:코퍼스 디렉터리 접근: …']      <-- 운영 게이트
### A4  인가되지 않은 창 (토큰만 맞고 호출 지점 불일치)
  EXIT=1  인가되지 않은 창 ['t77-audit-battery@<string>:_wrapped']         <-- 신규 채널 발화
          + 운영 경계 위반도 동시 발화 (기록이 프로브로 안 감)
### A1  위조 sanctioned 창 · 기록 제거 없음
  EXIT=1  프로브 창 안: {'t77-audit-battery': (7,2), …}
          운영 경계 위반: ['프로브 기록 t77-audit-battery=7:2!=6:2']          <-- 개수 핀 발화
```

세 층이 **독립으로** 잡는다.  v2.7 의 전역 깊이 남용(직전 라운드 N-1 의 G1/G2)은 닫혔다.

### 그러나 호출 지점 identity 가 위조 가능하다 — 실측

```
audit_guard.py:474-476
    frame = sys._getframe(1)
    site = f"{os.path.basename(frame.f_code.co_filename)}:{frame.f_code.co_name}"
```

정의역이 **파일 basename + 함수 이름**이다.  `compile()` 로 `co_filename` 을 지정하면 임의 코드가
그 identity 를 갖는다.  `PROBE_SITES` 는 공개 dict 이므로 유효 토큰 4개가 전부 노출돼 있다.

```
### M3-a  공격자가 proto 쪽에서 co_filename 을 위조
  exec(compile(src, "test_contracts.py", "exec"), ns)   # src 안 함수명 = t77_boundary
  위조 창 sanctioned = True
  unsanctioned_windows = 없음
```

### 개수 핀까지 맞춘 완전 은닉 — 대조군과 **바이트 동일**

`probe_reads` 는 공개 mutable list 이고 `policy_value_exclusions` 로 값 앵커에서 제외돼 있다.
위조 창 안에서 진입 시점 길이를 기억했다가 자기 기록만 정확히 잘라낸다:

```
### C0  대조군 — 같은 monkeypatch, 위반 **없음** (잡음 기준선)
  감사 hook 차단 기록 — 인가된 프로브 창 안: {'t77-audit-battery': (6,2), 't77-cross-thread': (1,0),
                                          't77-reentrant': (1,0), 't77-separation': (1,0)}
                       · 인가되지 않은 창 없음 · 대조군 이관 1건
  운영 경계 위반(대조군 밖) — exit 결속: 없음

### C1  위조 sanctioned 창 + 실제 코퍼스 열람 + 자기 기록만 정확히 제거
  감사 hook 차단 기록 — 인가된 프로브 창 안: {'t77-audit-battery': (6,2), 't77-cross-thread': (1,0),
                                          't77-reentrant': (1,0), 't77-separation': (1,0)}
                       · 인가되지 않은 창 없음 · 대조군 이관 1건
  운영 경계 위반(대조군 밖) — exit 결속: 없음
```

**C1 의 세 관측 채널 출력이 C0(무위반 대조군)과 완전히 동일하다.**  운영 게이트 침묵 ·
`unsanctioned_windows` 공백 · 개수 핀 정확 일치.  남는 것은 디스크 편집을 보는 앵커뿐이며
그것은 1-pass 로 수렴한다.

**한정(정직하게)**: C1 에서도 실제로 읽힌 바이트는 0 이다 — `AuditViolation` 은 그대로 발생하고
차단은 창 안팎이 같다(`L-AUDIT-PERSIST` 서술 그대로).  이것은 **탈취가 아니라 게이트 회피**다.

### 등재 상태 — 이 통로는 어느 노트에도 없다

`L-AUDIT-PROBE-THREAD` 가 적은 잔여는 하나뿐이다:
> "**남는 것**: **인가된 호출 지점의 소스를 고쳐** 그 창 안에서 위반하는 경로는 코드·설정·앵커를
> 함께 고치면 통과한다"

이는 *인가된 지점을 편집*하는 경로다.  **인가된 지점을 건드리지 않고 identity 를 사칭하는 경로**와
**`probe_reads` 가 공개 mutable list 라 핀을 맞출 수 있다는 사실**은 22개 노트 어디에도 없다
(`위조`·`basename`·`co_name`·`프레임` 전수 grep 확인).

- **처분**: **부분해소** (3층 실질 강화 · 신규 잔여 미등재) · confidence 100
- **권고**: ⑴ 호출 지점을 basename 이 아니라 **`co_filename` 절대경로 + 코드 digest**로 결속하고
  `PROBE_SITES` 값에 그 digest 를 넣어라 — `compile()` 위조가 즉시 갈린다.  ⑵ `probe_reads` 에
  기록할 때 **단조 증가 시퀀스 번호**를 함께 실어 개수가 아니라 시퀀스 연속성을 핀으로 삼아라 —
  중간 삭제가 관측된다.  ⑶ `L-AUDIT-PROBE-THREAD` 에 "호출 지점 identity 는 `compile()` 로
  사칭 가능하고 프로브 기록 버킷은 공개 mutable list 다" 를 병기하라.

## #4 · HIGH — pre-hook 검사가 실행 가능한 대입과 문자열 동적 import 를 동시에 놓친다 → **부분해소**

### 심판이 지목한 정확한 페이로드는 닫혔다

`prehook_analysis()` 를 직접 호출해 12종 페이로드를 전수 계측했다(러너 파일 무편집):

```
페이로드                                        실행문계수  dynamic  판정
P1  대입 RHS Call  X = frozenset('a')                 1        0    탐지
P2  walrus  (Y := len('ab'))                          1        0    탐지
P3  _S = __builtins__['__import__']('os')             1        1    탐지   <-- 심판 페이로드 (양층 발화)
P10 f-string 내 호출  S2 = f'{len(chr(65))}'           1        0    탐지
P11 try 블록 안 import                                 1        0    탐지
P12 클래스 본문 dict-subscript import                   0        1    탐지
---------------------------------------------------------------------------
P5  클래스 본문 임의 호출  class F: Q = (lambda: 1)()    0        0    **침묵**
P6  메타클래스 부작용                                    0        0    **침묵**
P7  Attribute 접근                                     0        0    **침묵**
P8  bare-name 데코레이터  @functools.cache               0        0    **침묵**
```

**P3 은 v2.7 에서 두 층을 동시에 침묵시킨 페이로드였고 지금은 둘 다 발화한다.**  교정은 실재한다.

### 그러나 형제 형태가 동일 구조를 재현한다

`_statement_executes(ClassDef)` 는 `decorator_list`·`bases`·`keywords` 만 본다 —
**클래스 본문은 걷지 않는다**.  본문은 클래스 생성 시점에 그대로 실행된다.
금지 이름 34종은 전부 피하고 미등재 I/O 진입점(`io.FileIO`)을 쓴다.

```
### M4  러너 pre-hook 구간에 클래스 본문 페이로드 주입 (경로는 바이트에서 조립 — 리터럴 스캔 회피)
    class _Sneak:
        _p = bytes([116,111,115,45,115,112,101,99]).decode() + "/src/…/" + bytes([69,86,…]).decode() + ".csv"
        _h = _io_early.FileIO(_p, "r");  _d = _h.read();  _h.close();  _n = len(_d)

  실행문계수=1 (핀=test_contracts.py=1)   <-- ⒜ 침묵 (핀과 정확히 일치)
  dynamic=없음                            <-- ⒝ 침묵
  탈취=21015바이트 · hook 설치 전 탈취 완료 = True
  EXIT=1  미성립: ['T-77-AUDIT', 'SELF-1']
  [T-77-AUDIT] pre-hook 구간 문제=['test_contracts.py: pre-hook 구간 digest ebed…!=381a…']  <-- ⒞ 발화
  앵커 드리프트: ['Case산문=…', '소스바이트=…', '실행코드=…']
```

리터럴 경로를 쓴 1차 시도에서는 `T-77-①`(소스 스캔)이 함께 발화했으나, 바이트 조립으로 그
층도 침묵시켰다 — **미성립이 3건에서 2건으로 줄었다.**

| 층 | 결과 |
|---|---|
| ⒜ pre-hook 실행문 개수 핀 (`anchor_prehook_executable`) | **1건 = 핀 값 — 침묵** |
| ⒝ 동적 로드·I/O 이름 34종 fail-closed | **`dynamic` 비어 있음 — 침묵** |
| `bootstrap_witness()` 스냅샷 | **위반 없음 — 침묵** (`proto` 를 안 건드렸다) |
| `T-77-①` 리터럴·AST 소스 스캔 | **침묵** (바이트 조립) |
| ⒞ 구간 `ast.unparse` digest + 소스 바이트/실행코드 앵커 | **발화 — 유일하게 잡음** |

직전 라운드 F2 와 **같은 구조**다: 하나의 페이로드가 계수·이름 두 층을 동시에 침묵시키고 디스크
편집 앵커만 남는다.  `L-AUDIT-BOOTSTRAP` 은 "실행문 0" 거짓 서술을 정직하게 철회했고 pre-hook
구간이 armed 가 아님도 명시하지만, **등재된 개수가 "코드를 돌리는 문장의 수"가 아니라 여전히
부분 분류라는 사실**은 적지 않는다.

- **처분**: **부분해소** (심판 페이로드 폐쇄 실증 · 형제 형태로 동일 구조 재현) · confidence 100
- **권고**: ⑴ `_statement_executes(ClassDef)` 가 `node.body` 를 `_contains_execution` 에 포함하라
  (클래스 본문은 정의가 아니라 실행이다).  ⑵ 데코레이터는 `_EXECUTING_NODES` 유무와 무관하게
  **존재만으로** 실행으로 세라 — `@name` 도 `name(f)` 호출이다.  ⑶ `PREHOOK_FORBIDDEN_NAMES` 에
  `FileIO`·`open_code`·`getlines`·`input` 을 더하되, 열거 방식의 한계를
  `L-AUDIT-BOOTSTRAP` 에 병기하라.

## #5 · MEDIUM — 정책값 전수 앵커와 잔여 목록이 실제 판정 우주보다 좁다 → **해소**

### census 가 진짜 자동인가 — 신규 상수 3종 전부 red

```
### N0 무변조
  [T-79] census 75+정규화 2=77개 ↔ 등재 77개 일치=True · 의도적 제외 7개(실물 없는 제외=없음)
         · 정의역 타입 밖 잔여 27개 · 드리프트=없음 · 항목별 변형 436건 중 미검출 0건
  EXIT=0
### N1 gates.NEW_POLICY = ('a','b')   (tuple)
  EXIT=1  일치=False · 드리프트=['gates.NEW_POLICY=59b271ae1bbcb1d3!=None']  미성립:['T-79','SELF-1']
### N2 floor.NEW_STR = 'x'            (str)
  EXIT=1  드리프트=['floor.NEW_STR=2d711642b726b044!=None']
### N3 register.NEW_MAP = {'k':'v'}   (dict)
  EXIT=1  드리프트=['register.NEW_MAP=e258d9265368a30b!=None']
### N5 anchor_modules() 를 1개 모듈로 축소 (census 회피 시도)
  EXIT=1  census 7+정규화 2=9개 ↔ 등재 77개 일치=False
```

**정의역 타입 3종 전부에서 신규 상수가 등재 없이 red 가 된다.**  손 목록이 "신규 항목을 영원히
못 찾는다"는 결함 클래스가 실제로 제거됐다.

### 팬텀 제외 — fail-closed 로 잡힌다

```
### N4  policy_value_exclusions 에 존재하지 않는 이름 추가
  EXIT=1  의도적 제외 7개(실물 없는 제외=['audit_guard.NOPE'])
          미성립: ['T-80', 'T-79', 'SELF-1']
```

`T-79` 가 팬텀을 직접 잡고, 그 조작이 `load_config` 경유였으므로 `T-80` 이 **독립으로** 한 번 더 잡는다.

### 현행 7개 제외에 팬텀은 없다 · 심판이 지목한 이름은 표 안으로 들어왔다

```
excluded(7) = _ARMED_SNAPSHOT, blocked_reads, blocked_writes, probe_reads, probe_writes,
              sanctioned_reads, unsanctioned_windows        (실물 없는 제외 = 없음)
config.yaml:130  boundary._NULLARY_STR_METHODS=ff35924357572b8d   <-- 심판 v2.7 #5 의 정확한 반례
                 runner._INERT_STATEMENTS=48915c…, runner._EXECUTING_NODES=4e332b…
잔여 27개는 노트가 전수 열거하고 "런타임 대입은 잡지 못한다"를 명시한다.
항목별 삭제·확장 변형 436건 중 미검출 0건.
```

- **처분**: **해소** (25→77 · 자동 파생 실증 · 팬텀 fail-closed · 반례 이름 편입) · confidence 100

## #6 · MEDIUM — 쓰기 음성 대조군이 실패 시 저장소에 실물을 남긴다 → **해소**

표적이 `_HERE / "__absent_probe_root"`(**만들지 않는 부모**) 밑으로 옮겨졌다.
가드를 단계적으로 깨뜨리며 저장소 전체를 walk 해 실물을 셌다:

```
### W0 무변조            EXIT=0  차단 7/7 · 잔존 파일=없음        repo 내부 실물 = 없음
### W1 _WATCHED=∅       EXIT=1  차단 7/7 (monkeypatch 층 생존)   repo 내부 실물 = 없음
### W2 _WRITE_ARMED=F   EXIT=1  차단 7/7                        repo 내부 실물 = 없음
### W4 감사hook + monkeypatch **두 층 전부 무력화**
  EXIT=1  차단 0/7 · 미차단=['open(w)(OSError)','Path.write_text(OSError)','Path.write_bytes(OSError)',
                            'os.open(OSError)','os.replace(OSError)','shutil.copyfile(OSError)',
                            'shutil.rmtree(OSError)'] · 잔존 파일=없음
  repo 내부 실물 = 없음                                          <-- 음성 시나리오에서도 0
```

**가드가 완전히 죽은 상태에서 7개 진입점이 전부 실제로 시도됐고, 전부 부모 부재로 `OSError` 가
나며 저장소 안에 실물이 하나도 생기지 않았다.**  직전 라운드에서 24건을 위양성으로 만든 오염
함정이 재현되지 않는다.

경계 실측(고지 목적, 지적 아님): 부모 디렉터리를 **out-of-band 로** 미리 만든 뒤 두 층을 깨면
7개 실물이 생긴다(`W5`).  러너 자신은 그 부모를 만들 수 없고(`mkdir` 차단), `leftovers` glob 이
`__absent_probe_root` 를 즉시 잡아 `T-77-②` 를 red 로 만든다.  교정의 결함이 아니다.

- **처분**: **해소** · confidence 100

---

# 2부 · 신규 발견

## N-1 · MEDIUM — 프로브 창 호출 지점 identity 가 사칭 가능하고 그 통로가 미등재

- **location**: `tools/spikes/phase0_contract/audit_guard.py:474-476` (`probe_window`),
  `:211-216` (`PROBE_SITES`), `:197-198` (`probe_reads`), `proto/config.yaml:171`
  (`policy_value_exclusions`), `test_contracts.py:1044-1065` (`probe_record_violations`)
- **유형**: CWE-290 Authentication Bypass by Spoofing / CWE-693 Protection Mechanism Failure
- **confidence**: 100 (결정론적 실측 — C0/C1 출력 동일)
- **악용 시나리오**: 인가 판정이 `basename(co_filename)` + `co_name` 이라는 **위조 가능한 두
  문자열**에만 의존한다.  `PROBE_SITES` 는 공개 dict 이므로 유효 토큰 4종이 전부 노출돼 있고,
  `compile(src, "test_contracts.py", "exec")` 한 줄이면 임의 모듈의 코드가 인가된 identity 를
  갖는다.  그 창 안의 위반은 운영 버킷을 우회해 프로브 버킷으로 가고, 진입 시점 길이를 기억해
  자기 기록만 잘라내면 `anchor_probe_records` 개수 핀까지 정확히 맞는다.  결과는 무위반
  대조군과 **바이트 동일한 게이트 출력**이다(C0=C1 실측).  차단 자체는 유지되므로 탈취가 아니라
  **탐지·보고 회피**다.
- **recommendation**: `PROBE_SITES` 값을 `절대 co_filename + 호출 함수 코드 digest` 로 바꾸고,
  프로브 기록에 단조 증가 시퀀스를 실어 개수가 아니라 연속성을 핀으로 삼아라.
  최소한 `L-AUDIT-PROBE-THREAD` 에 이 통로를 등재하라.

## N-2 · LOW — `policy_value_exclusions` 제외 사유 주석이 4건을 서술하는데 실제는 7건

- **location**: `tools/spikes/phase0_contract/proto/config.yaml:167`
- **confidence**: 100 (실측)

```
config.yaml:167   # 제외 사유: 넷 다 **실행 중 내용이 변하는 관측 버킷**이거나 설치 시점 스냅샷이라
$ grep "^policy_value_exclusions:" proto/config.yaml | tr ',' '\n' | wc -l
7
```

v2.7→v2.8 사이 제외가 4→7로 늘었는데 사유 문장의 수량어가 따라가지 않았다.  방출 노트
`L-POLICY-ANCHOR` 는 `len(census['excluded'])` 로 동적 계산하므로 **런타임 서술은 정확하다** —
설정 주석만 stale 이다.  보상층 서술도 6건까지만 대응한다: `blocked_*` ← 운영 게이트,
`probe_*` ← `anchor_probe_records`, `unsanctioned_windows` ← `probe_record_violations`,
`_ARMED_SNAPSHOT` ← `bootstrap_witness`.  **`sanctioned_reads` 만 대응 층이 `main()` 의 인쇄된
건수뿐이다.**

- **recommendation**: 수량어를 제거하거나 7로 고치고, `sanctioned_reads` 의 보상층을 명시하라.

## N-3 · LOW — 어휘 면제가 이유를 검증하지 않는다 (1→3)

- **location**: `test_contracts.py:parked_limits` (`if limit.lid in waived: continue`),
  `proto/config.yaml:192`
- **confidence**: 100 (실측)

```
### 현행 3 면제는 전부 하중을 받는다 (제거하면 그대로 L2 발화)
  waivers=0 -> parked=['L-T77-SEAM', 'L-AUDIT-PROBE-THREAD', 'L-EXIT-ROOT']
  waivers=1 -> parked=['L-AUDIT-PROBE-THREAD', 'L-EXIT-ROOT']
  waivers=2 -> parked=['L-EXIT-ROOT']
  waivers=3 -> parked=[]

### 면제 표면 남용 시험
  rep.limit("L-REAL", "실제 결함이 여기 있다: 검출기가 이 위반을 통과시킨다", case="G1")  # G1 = green
  waiver 없음 -> parked = ['L-REAL']
  waiver 등재 -> parked = []
```

**정당성 평가**: 세 면제 전부 실재 하중이 있고 위양성이 아니다.  `L-EXIT-ROOT` 의 면제는
**구조적으로 강제된다** — 결속할 red Case 가 원리적으로 존재할 수 없기 때문이며(그 Case 의 red
역시 같은 함수를 경유한다), 이유가 `config.yaml:186-191` 에 문장으로 적혀 있다.
`L-AUDIT-PROBE-THREAD` 는 **과거형 자기 정정 기록**이고 닫힌 어휘 목록이 시제를 구별하지 못해
생긴 위양성이다.  따라서 **"L2 를 설정으로 넓힌 것"이 아니라 등재 표면의 정당한 사용**으로 읽힌다.

남는 사실 하나: 면제는 **id 멤버십만** 본다.  이유 문장은 기계 검사 대상이 아니므로, 임의의 실제
결함 주장도 `limit_vocabulary_waivers` 1줄 + `declared_limit_ids` 1줄 + 앵커 2종 갱신으로 주차할 수
있다.  L2 가 원래 "닫힌 목록이라 불완전하다"고 자기 고지한 층이므로 새 결함이라기보다 그 고지의
정량화이며, `L-SELF-VISIBILITY` 의 "가시화이지 폐쇄가 아니다" 범위 안이다.

- **recommendation**: 면제 항목 수 자체를 설정 앵커에 핀으로 고정해 증가가 diff 가 아니라 red 가
  되게 하라(현재 3).

## 검증 후 기각 — census 잔여 27개는 무탐지 우회가 아니다

`L-POLICY-ANCHOR` 가 잔여를 전수 열거하며 "런타임 대입은 잡지 못한다"고 명시하므로, 실제로
그것이 조용한 우회가 되는지 눌러 봤다.  **되지 않았고 지적으로 제출하지 않는다.**

```
### R1 gates._G1_PREDICATES 를 항상-True 로 교체   -> RAISED AttributeError (fail-loud)
### R2 gates._G2_PREDICATES 교체                  -> RAISED AttributeError
### R3 register._CLAUSE_RE 교체                   -> EXIT=1  미성립:['T-39','UNCHK-019','SELF-1']
### R4 floor._LEVEL_RE 교체                       -> RAISED LevelSyntaxError (fail-loud)
### R5 boundary.REAL_FS 교체 (직전 라운드 seam)     -> EXIT=1  방출 앵커 드리프트로 발화
```

가장 하중이 큰 잔여(게이트 판정 술어)는 `Predicate` 구조 때문에 교체 시 **시끄럽게 실패**하고,
파서 정규식은 행동 대조군이 잡는다.  잔여 목록은 고지대로이며 그 고지가 과소하지 않다.

---

## 이월 — 직전 라운드에서 열린 채 남은 항목 (재확인만, 새 지적 아님)

| 항목 | 상태 | 근거 |
|---|---|---|
| `os.stat` 메타데이터 오라클 (3라운드 이월) | 변동 없음 · `READ_EVENTS` 열거 밖 | `L-AUDIT-SCOPE` 고지 범위 |
| inode 별칭 (`L-INODE-ALIAS`) | 변동 없음 · 정책 축소가 정직 | 3라운드 #6 에서 실측 완료 |
| `sqlite3`/`ctypes`/`subprocess` VFS | 변동 없음 | `L-AUDIT-SCOPE` 고지 범위 |
| 1-pass 앵커 갱신 수렴 | 변동 없음 | M4·C1 에서 러너가 새 앵커 값을 인쇄 |
| `policy()` 자기신고 (직전 N-2) | **해소** | `audit_guard.py:368` `watched` 추가 · 기준선 출력에 `'watched': 20` |

## 시크릿·인젝션·역직렬화 축 — 결함 0 유지

`eval`/`exec`/`pickle`/`marshal`/`yaml.load`/`os.system` 실사용 히트 0건
(러너의 `PREHOOK_FORBIDDEN_NAMES` 리터럴 정의와 본 감사의 스크래치패드 PoC 는 제외).
KIS API 키·계좌번호·OpenAI/KRX/DART 자격증명 0건 — 이 프로토타입은 자격증명을 다루지 않는다.
외부 입력은 repo 내 `proto/config.yaml` 하나이며 `config.py` 의 자체 `key: value` 한 줄 파서로
읽는다(YAML 파서 미사용, `_parse_scalar` 는 `int()` 아니면 `str` 만 낸다).
`argv`·환경변수·stdin·네트워크 미사용.  경로 순회 표면은 `path_violation` 의 `Path.resolve()` +
casefold 정규화가 fail-closed 로 덮는다.

---

## 추측과 실측의 구분

- **전부 실측**: #1~#6 처분과 N-1·N-2·N-3 은 모두 뮤테이션 실행 출력을 그대로 인용했다.
  총 32 뮤테이션(M1·M1b·W0·W1·W2·W3·W4·W5·A1·A2·A3·A4·C0·C1·M3-a·M3-b·M3-c·
  P1~P12·N0~N5·F0·F1·F2·R1~R5·M4·M4b) + 정적 계측 2종.
- **탈취 능력의 정직한 한정**: 실제 바이트가 읽힌 것은 **M4b 하나뿐**(21,015 B, hook 설치 전
  pre-hook 구간)이며 대상은 디코이다.  N-1 의 C1 은 읽힌 바이트 0 — 게이트 회피이지 탈취가
  아니라고 본문에 명시했다.
- **디코이 사용**: 모든 열람 시험은 스크래치패드의 디코이 CSV(21,015 B)를 대상으로 했다.
  실 코퍼스 `EVIDENCE-REGISTER-002.csv`(3fe05c50…)는 읽지 않았고 shasum 무변경을 확인했다.
- **요청받았으나 지적하지 않은 축**: census 잔여 27개(위 "검증 후 기각"), `MODULE_BINDINGS`·
  `T-80`·`independent_settings`(새 공격면 아님 — F0/F1/F2 로 오히려 검출력 증가 실측),
  `L-EXIT-ROOT` 선택적 재바인딩(등재된 결함 클래스의 부분집합).  렌즈를 채우려고 만들지 않았다.

## 재현

```bash
S=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/\
2ed2dc33-ef7f-4f31-b91f-b5258c17c8dd/scratchpad/r4
python3 $S/poc/m6_write.py     # W0 W1 W2 W3   (#6 쓰기 프로브 잔존물)
python3 $S/poc/m6b.py          # W4 W5         (#6 두 층 무력화 · out-of-band 부모)
python3 $S/poc/m3b.py          # A1 A2 A3 A4   (#3 토큰·창 3층)
python3 $S/poc/m3c.py          # C0 C1         (N-1 완전 은닉 · 대조군 동일)
python3 $S/poc/m5.py           # N0~N5         (#5 census 자동성·팬텀)
python3 $S/poc/m2.py           # F0 F1 F2      (#2 위조 지점 계수)
python3 $S/poc/m7.py           # R1~R5         (census 잔여 압박)
```

## 원본 작업 트리 무편집 확인 (감사 종료 시점)

```
$ find tools/spikes/phase0_contract -type f \( -name '*.py' -o -name '*.yaml' \) | sort | xargs shasum
330232d9…  audit_guard.py             028ea8ab…  proto/__init__.py
9d263568…  blocks_gate_consumption.py ec95f96c…  proto/boundary.py
b9a92d5b…  proto/config.py            b7b38d99…  proto/config.yaml
f800f8b9…  proto/enforcement.py       dfdb2f56…  proto/floor.py
6a098c87…  proto/gates.py             c70e4fef…  proto/register.py
a25203d8…  sweep_deprecated_vocabulary.py  fa0b4192…  test_contracts.py
   -> 감사 시작 12행 vs 종료 12행 = **완전 동일**.

$ find tools/spikes/phase0_contract \( -name '__pycache__' -o -name '*.pyc' \) | wc -l     # 0
$ find . -maxdepth 4 \( -name '__*probe*' -o -name '__absent*' \) -not -path './.git/*'    # (없음)
$ git status --porcelain -- tools/spikes/ tos-spec/
?? tools/spikes/
?? tos-spec/src/part-1-foundation/decisions/                    # 시작과 동일
$ shasum tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv
3fe05c50139d1ac6801aa33b5dd3a4f5db3027c3                        # 코퍼스 무변경
$ python3 tools/spikes/phase0_contract/test_contracts.py
   대조군 39/39 · 앵커 5종 전부 감사 시작 시점과 동일 · EXIT=0
```

모든 뮤테이션·페이로드 주입·가짜 `.git`·디코이 CSV 는 `<tmp>/r4/{repo,mut,mut2}/` 사본 안에서만
만들었다.  원본 작업 트리는 읽기만 했다.
