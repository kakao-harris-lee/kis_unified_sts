# 아키텍처 렌즈 — v2.8 재심 (4라운드) · 증거

```yaml
lens: architecture
mode: 증거 생산 (판정 없음 — verdict 는 codex-reviewer 소관)
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
prior_verdict: .omc/review/20260813-123739/verdict.md   # Codex, needs-attention, findings 6
prior_lens:    .omc/review/20260813-123739/evidence/architecture.md
method: 인메모리 뮤테이션 26건 + 스크래치패드 사본 디스크 위조 3회
scratch_repo: <tmp>/scratchpad/repo/tools/spikes/phase0_contract  (+ 위조 .git)
```

## 0. 원본 작업 트리 무결성

디스크 편집은 전부 스크래치패드 사본에서 했다. 감사 시작 시점과 종료 시점 해시가 동일하다.

```
$ shasum -a 256 tools/spikes/phase0_contract/test_contracts.py tools/spikes/phase0_contract/audit_guard.py
28200f83de36a1360465f75f8886897b42a380649c170297459c8afe994c0033  test_contracts.py
924d0fedc05ad507b9bd3e1ceb3ec1bf94b16aaa86dba65430959b0b364581af  audit_guard.py
$ find tools/spikes -type f -not -path '*__pycache__*' | sort | xargs shasum -a 256 | shasum -a 256
a7d68f97df0c7287a16c368c422c6601b9f58a0b204185247de12cb0e7b4ad4b  -      # 시작=종료 동일
$ git status --short
 M uv.lock            ?? docs/plans/...   ?? tools/spikes/   ?? tos-spec/src/.../decisions/
```

기준선(원본 트리):

```
$ python3 tools/spikes/phase0_contract/test_contracts.py ; echo EXIT=$?
대조군 39건 중 양방향 성립 39건
발견 — 관측된 계약 위반 0건
앵커 드리프트 — exit 결속: 없음
EXIT=0
```

---

## 1. 직전 6건 처분

| # | sev | 원 지적 | **처분** | 근거 |
|---|---|---|---|---|
| 1 | critical | 최종 exit 이 same-process 단일 함수에 귀결 | **정직등재** | `L-EXIT-ROOT` 신설·22개 노트 등재·`deferred_owner_tracks: L-EXIT-ROOT=Phase 1`·자기증명 주장 4곳 전부 부정형. **단, §2-4·§2-6 의 등재 정합 흠결 2건** |
| 2 | high | import 바인딩이 앵커 정의역 밖 → 기대값 라이브 위조 | **부분해소 · 표면 이동(3연속)** | `__module__` 자기신고 제거·`MODULE_BINDINGS`·`T-80` 은 실측 성립. **그러나 지렛대가 `load_config` 바인딩 → `config.CONFIG_PATH` 로 이동했고 전건 GREEN 위조를 재현했다** (§2-2) |
| 3 | high | 전역 probe_window 가 위반을 exit 비결속 버킷으로 재분류 | **해소** | thread-local·토큰·고정 호출지점·개수 핀 전부 실측 성립. 교차 스레드 위반이 `blocked_*` 로 남는 것을 직접 관측 (§2-3). 잔여 1건은 내용 identity 미결속(신규 N-5) |
| 4 | high | pre-hook 이 실행 가능 대입·문자열 동적 import 동시 누락 | **해소** | 심판이 제시한 정확한 페이로드가 3층 전부에서 검출됨 (§2-5) |
| 5 | medium | 정책값 수동 census 가 실제 판정 우주보다 좁음 | **부분해소** | 자동 census 는 **구조 파생이 맞다**(모듈 레벨 평문 타입 한정). 지목된 `_NULLARY_STR_METHODS` 는 앵커에 편입돼 런타임 축소가 red. **그러나 census 정의역의 *모양* 제약 때문에 클래스 속성 형태는 `targets` 에도 `residual` 에도 안 들어간다** (§2-1) |
| 6 | medium | 쓰기 음성 대조군이 저장소에 실물을 남김 | **해소** | 두 층을 전부 무장 해제한 상태로 완주해도 저장소 내부 신규 엔트리 **0** (§2-6) |

**회피 0.** 6건 모두 코드로 응답했고, 서술 철회도 실물로 이루어졌다(§4).

---

## 2. 실증

### 2-1. 자동 census 는 진짜 구조 파생인가 — **대체로 그렇다, 다만 정의역이 *모양*으로 제한된다**

`policy_value_census()` (`test_contracts.py:693-734`) 는 `anchor_modules()` 8개 모듈의
`vars()` 를 전수 훑어 3분류한다. 등재 없이 red 가 되는지 직접 확인했다.

```
$ PYTHONPATH=. python3 census_probe.py
BASE targets=75 excluded=7 residual=27 phantom=0
module tuple                 +targets=['boundary.NEW_POLICY_TUPLE']  +residual=[]
class attr                   +targets=[]  +residual=[]              <-- 어느 분류에도 없음
nested dict(list val)        +targets=[]  +residual=['boundary.NESTED(dict)']
nested dict(dict val)        +targets=[]  +residual=['boundary.NESTED2(dict)']
list of lists                +targets=[]  +residual=['boundary.LL(list)']
func default                 +targets=[]  +residual=[]
int threshold                +targets=[]  +residual=['boundary.MAX_DEPTH(int)']
phantom probe -> ('boundary.DOES_NOT_EXIST',)                       <-- 팬텀 검출 성립
```

전체 실행으로 red/green 을 확인했다.

```
$ for m in none classattr intresidual nesteddict; do python3 silence_probe.py $m; done
### none         EXIT=0  대조군 39/39
### classattr    EXIT=0  대조군 39/39   census 75+2=77 · 잔여 27 · 드리프트=없음   <-- 완전 침묵
### intresidual  EXIT=1  잔여 28 · 앵커 드리프트 ['방출=afd010ec...!=d64bb6dd...']
### nesteddict   EXIT=1  잔여 28 · 앵커 드리프트 ['방출=22480fff...!=d64bb6dd...']
```

관측 결과:

- **평문 타입 모듈 상수는 구조 파생이 성립한다.** 새 tuple 을 넣으면 `targets` 에 자동 편입되고
  `anchor_policy_values` 이름 불일치로 red. 삭제도 같다.
- **잔여 목록도 결속돼 있다.** 잔여가 27→28 이 되면 `L-POLICY-ANCHOR` 노트 본문이 바뀌고
  **방출 앵커**가 드리프트한다. 손 목록이 아니라는 주장은 성립한다.
- **`policy_value_exclusions` 7건에 팬텀 없음**(`phantom=()`), 팬텀 검출기도 작동한다.
- **파생 잔여 27건 목록은 실제와 완전 일치한다.** 방출 노트의 열거와 내가 독립 재계산한 27건이
  이름·타입까지 동일하다(`runner._HERE(PosixPath)` … `register.annotations(_Feature)`).
- **놓치는 종류가 있다** — `callable(value)` 로 스킵하므로(`:719`) **클래스는 통째로 정의역
  밖**이고, `_module_code_parts` 도 클래스 멤버 중 `__code__` 를 가진 것만 본다(`:459-466`).
  따라서 클래스 본문에 든 정책 상수는 `targets`·`residual`·실행코드 앵커 **어디에도 없다**.
  중첩 dict·list·int 는 잔여로 잡히므로(가시) 이 모양만 무음이다.

잔여 27건의 런타임 대입이 실제로 어떻게 되는지도 확인했다 — 대부분은 **앵커가 아니라 도메인
Case 가** 시끄럽게 잡는다:

```
### g1pred     (gates._G1_PREDICATES 축소)   EXIT=1  T-39/T-71/T-2/UNCHK-019 red
### g2pred     (gates._G2_PREDICATES 축소)   EXIT=1  T-39/T-71/UNCHK-019 red
### clauserre  (register._CLAUSE_RE 무력화)  EXIT=1  T-39/UNCHK-019 red
### levelre    (floor._LEVEL_RE 무력화)      EXIT=EXC LevelSyntaxError   (fail-closed)
### nullary    (boundary._NULLARY_STR_METHODS=∅) EXIT=1
      [T-79] 드리프트=['boundary._NULLARY_STR_METHODS=e3b0c442...!=ff359243...']   <-- #5 지목분 폐쇄
```

**예외가 하나 있다: `config.CONFIG_PATH`.** 잔여 목록에 이름은 있으나, 이 이름은 *기대값 자체를
정의*하므로 도메인 Case 도 그것을 잡지 못한다. 다음 절이 그 결과다.

### 2-2. #2 는 표면을 다시 옮겼는가 — **옮겼다. `CONFIG_PATH` 재대입 하나로 전건 GREEN 재현**

저작자가 스스로 적은 서술(`test_contracts.py:539-545`)은
"두 판독기가 같은 프로세스에 있으므로 둘 다 갈아끼우는 변조는 이 층을 지난다 —
**비용을 1 지점에서 2 지점으로 올릴 뿐**" 이다. **이 서술이 부정확하다.** 두 판독기는
`config.load_config()` 와 `independent_settings(config.CONFIG_PATH)` 인데, **둘 다 경로를
같은 이름 `config.CONFIG_PATH` 에서 가져온다**(`proto/config.py:11,67` · `test_contracts.py:3242`).
그 이름은 census 가 **잔여**로 분류한 미결속 이름이다. 따라서 비용은 여전히 **1 지점**이다.

재현 — 러너 import 전에 위조 yaml 을 저장소 **밖**에 쓰고, 런타임 대입 1회 + `#5` 지목값
1회 축소:

```python
config.CONFIG_PATH = FORGED                      # 잔여 이름 — 어느 앵커도 안 본다
boundary._NULLARY_STR_METHODS = frozenset()      # 심판 #5 가 지목한 바로 그 값
```

3회 반복(드리프트 보고를 그대로 위조본에 기입)으로 수렴했다.

```
### forge EXIT=0   CONFIG_PATH=<tmp>/scratchpad/forged_config.yaml
  [T-80] 필수 키 27/27 이중 판독 일치=True · 바인딩 출처 이탈=없음 · 위조 판독 검출=True · 외래 코드 검출=True
  [T-79] census 75+정규화 2=77개 ↔ 등재 77개 일치=True · 드리프트=없음 · 항목별 변형 430건 중 미검출 0건
  발견 — 관측된 계약 위반 0건
  대조군 39건 중 양방향 성립 39건
  산문 앵커 대조: 리터럴=5e39cb99… · 방출=d64bb6dd… · 실행코드=9b29dfdc… · 소스바이트=1d741553… (전부 기준선과 동일)
  앵커 드리프트 — exit 결속: 없음
```

**소스 바이트·실행코드 앵커가 기준선과 완전히 동일한 상태**에서, 판정 우주를 정의하는 정책값이
비어 있는 채로 전건 GREEN 이다. T-80 은 "이중 판독 일치=True · 위조 판독 검출=True" 를 출력한다.

`independent_settings` 의 독립성 실측:

| 축 | 독립인가 |
|---|---|
| 판독 **함수** 바인딩 | 독립 O — 러너 자기 코드(`:547-553`), `config.load_config` 교체를 검출 |
| 판독 **경로** | **독립 X** — 둘 다 `config.CONFIG_PATH` 를 역참조 |
| 판독 **알고리즘** | 사실상 동일 — `#` 절단→strip→첫 `:` 분할까지 `proto/config.py:73-78` 의 복제. 파서 자체의 결함(값 안의 `#`)은 양쪽이 같이 틀리므로 이중화가 잡지 못한다 |
| 중복키 처리 | 다름 — `load_config` 는 중단, `independent_settings` 는 마지막 값 채택(`:553`) |

`MODULE_BINDINGS`·`T-80` 자체는 실측 성립한다 — 함수 교체는 잡는다. 다만 **심판의 권고
"앵커 기대값을 읽는 *경로 자체*를 외부 또는 독립 앵커가 검증하게 하라" 중 '경로' 부분이
미이행**이다.

### 2-3. #3 — 해소

```
$ PYTHONPATH=. python3 probe_c6.py
CORPUS_DIR='tos-spec/' REGISTER_PREFIX='EVIDENCE-REGISTER-'
== 창 없음 ==                         blocked_reads=1 probe_reads=0
== 인가창 MAIN, 위반 WORKER 스레드 ==  blocked_reads=1 probe_reads=0
     -> ['open:코퍼스 디렉터리 접근: /private/tmp/tos-spec/EVIDENCE-REGISTER--x.md']   <-- exit 결속 유지
== 인가창 열림, 같은 스레드 위반 ==     blocked_reads=0 probe_reads=1
```

심판이 지목한 정확한 통로(“러너 자신이 창 안에서 워커 스레드를 돌리는 시간대”)가 닫혔다.
게이트 결속도 확인했다.

```
$ PYTHONPATH=. python3 probe_c.py
C1 핀 일치 상태              -> 없음(green)
C2 인가창 안 기록 +1         -> ['프로브 기록 t77-audit-battery=7:2!=6:2']
C3 개수 동일·내용 교체        -> 없음(green)      <-- 내용 identity 는 결속되지 않는다
C4 미등재 토큰               -> ['프로브 기록 t77-forged=1:0!=미등재']
C5 인가되지 않은 호출 지점     -> ['인가되지 않은 프로브 창: t77-audit-battery@probe_c.py:<module>']
```

C3 이 신규 침묵(N-5)이다. `test_contracts.py:1045` 는 "인가된 프로브 기록의 **identity 와
개수**를 설정 앵커에 결속" 이라 적지만, 결속되는 identity 는 **토큰(=호출 지점)**뿐이고
기록 **내용**은 아니다. 인가된 창 안에서 예상 기록 하나가 다른 위반으로 치환되면 개수가
같아 침묵한다.

### 2-4. B 등재의 구조적 정합 — **SELF-3 의 검증은 참조 무결성뿐, 이연 자체를 요구하지 않는다**

`self_exit_wiring` 의 이연 검사(`test_contracts.py:3158-3164`)는 *등재된 항목마다*
⑴ track 이 비어 있지 않고 ⑵ id 가 `declared_limit_ids` 에 있는지만 본다.
**"L-EXIT-ROOT 가 이연돼 있어야 한다" 는 요구가 없다.**

```
--- F1 미끼 이연 (deferred_owner_tracks: L-CASEFOLD=Phase 1) ---
### EXIT=1
  [SELF-3] … 이연 등재 1건            <-- 문제=[] · SELF-3 green
  앵커 드리프트 — exit 결속: ['방출=01c79c81f296cbea!=d64bb6dd17dde55f']   <-- 유일 검출자
  - **미검사(종단)**: … owner track `Phase 1` 로 이연 등재했다.   <-- 거짓이 된 하드코딩 문장

--- F2 팬텀 id (L-NOT-DECLARED=Phase 1) ---
### EXIT=1  SELF-3 red · 이연 등재 1건 문제=['L-NOT-DECLARED=Phase 1']       <-- 참조 무결성은 성립

--- F3 track 변조 (L-EXIT-ROOT=Phase 9 (whenever)) ---
### EXIT=1  방출 드리프트
  - **미검사(종단)**: … owner track `Phase 1` 로 이연 등재했다.   <-- 여전히 "Phase 1"
```

정리:

- **이연 등재를 지우면 무엇이 잡는가** → `L-EXIT-ROOT` 노트가 `deferrals.get('L-EXIT-ROOT',
  '<미등재>')` 를 삽입하므로(`:3205`) **방출 앵커**가 잡는다. `cfg_pairs` 가 빈 목록을
  거부하므로(`proto/config.py:124-125`) 키를 비울 수도 없다. 이 층은 실재한다.
- **자기참조인가** → SELF-3 의 검사 자체는 자기참조가 아니지만 **범위가 주장보다 좁다.**
  `L-EXIT-ROOT` 의 이연은 SELF-3 이 아니라 노트 삽입값→방출 앵커가 지킨다.
- **하드코딩 불일치 1건** — OD-3 고지의 `test_contracts.py:3590` 과 모듈 docstring `:113`
  이 `Phase 1` 을 **리터럴로** 적는다. F1·F3 에서 설정이 무엇을 말하든 이 문장은 불변이다.
  최종 요약(운영자가 읽는 표면)이 설정 등재와 무관하게 이연을 단언한다.

### 2-5. #4 — 해소

`prehook_analysis` 를 원본 소스에 페이로드를 주입해 직접 호출했다(디스크 무편집).

```
BASE  exec=1 dynamic=[] digest=381ab3fbd5532507  pin={'test_contracts.py':'1','audit_guard.py':'11'}
BASE  executable stmts: ['_HERE = Path(__file__).resolve().parent']

P1 codex exact   _SNEAK = __builtins__['__import__']('proto.register')
                 exec=2(pin=1) dyn=1 ['__import__'] digest_changed=True      <-- 3층 전부 검출
P2 split string  _SNEAK = [__builtins__][0]['__im'+'port__']('proto.register')
                 exec=2(pin=1) dyn=0 [] digest_changed=True                  <-- 이름층 회피, 계수+digest 검출
P3 name indirect _Q='__import__'; _SNEAK=__builtins__[_Q]('proto.register')
                 exec=2(pin=1) dyn=0 [] digest_changed=True
P4 inert const   _Q='__import__'         exec=1 dyn=0 digest_changed=True    <-- digest 만
P5 lambda armed  exec=2 dyn=1 ['__import__'] digest_changed=True
P6 decorator     exec=1 dyn=0 digest_changed=True
```

심판이 제시한 페이로드는 확실히 잡힌다. **다만 실질 폐쇄자는 v2.7 에도 있던 구간 digest 이고,
v2.8 이 추가한 계수 핀·상수 첨자 검사는 회피 가능한 가시화 층이다**(P2·P3 이 이름층을 통과).
저작자도 그렇게 적었다(`L-AUDIT-BOOTSTRAP`: "고정될 뿐 차단되지 않는다").

부수: `prehook_analysis` docstring `:962` 이 "러너 1 · `audit_guard.py` **9**" 라고 적는데
실제·핀 모두 **11** 이다(`config.yaml:150`). 심판 #4 를 교정한 바로 그 docstring 이 stale.

### 2-6. #6 — 해소

`_WRITE_PROBE_ROOT = _HERE / "__absent_probe_root"` (`:188`) — 부모 부재 경로. 쓰기 프로브
전건이 그 밑을 향한다(`:1495,1502,1618,1622,1628,1635,1640,1982,1986`). `makedirs` 없음.

두 층(감사 hook `_WRITE_ARMED=False` + monkeypatch `write_guard` 무력화)을 전부 내린
**음성 시나리오**로 완주:

```
### disarmed-write run EXIT=1
NEW filesystem entries inside repo subtree: 없음 — 잔존물 0
_WRITE_PROBE_ROOT=<scratch>/__absent_probe_root exists=False
```

원본 트리도 정상 실행 후 잔존물 0(§0 의 `git status` 와 트리 digest 동일).

### 2-7. 주장 철회 스윕의 완전성

```
$ grep -n "자기증명|증명한다|보장" test_contracts.py audit_guard.py proto/*.py proto/config.yaml
test_contracts.py:111   … 자기증명한다는 **주장을 제거**
test_contracts.py:1098  … 자기증명한다고 적지 않는다
test_contracts.py:3202  … 자기증명한다고 주장하지 않는다
test_contracts.py:3591  … 최종 exit 을 자기증명하지 않는다
$ grep -n "폐쇄다|폐쇄한다|완전히|전부 막"  → 남은 것은 전부 부정형(":2229 전부 막았다고 적지 않는다",
                                          "boundary.py:629/711 전부 막았다고 주장하지 않는다")
```

강한 어휘의 과대주장은 남아 있지 않다. 다만 grep 이 아니라 **실측이 반증한 국소 과대주장 3건**이
남는다 — §2-2 의 `:539-545`("1→2 지점"), §2-3 의 `:1045`("identity 와 개수"),
§2-1/`L-POLICY-ANCHOR` 의 "새 상수가 생기면 등재 없이는 자동으로 red"(클래스 속성 형태 반례).
추가로 `L-POLICY-ANCHOR` 는 제외 7종을 "운영 게이트와 `anchor_probe_records` 가 내용으로
판정한다" 고 적는데, **`sanctioned_reads` 는 둘 다 소비하지 않는다**:

```
$ grep -n "sanctioned_reads" test_contracts.py audit_guard.py
audit_guard.py:203  선언   audit_guard.py:531  extend   test_contracts.py:3627  print   ← 소비 끝
```

실제 안전장치는 다른 것이고, 그것은 실측 성립한다(정확-개수 이관, `audit_guard.py:527`):

```
claim(1) with 1 blocked -> ['real-violation-1'] | blocked left: []          (이관 성립)
claim(1) with 2 blocked -> []                    | blocked left: 2건 잔존   (fail-closed=True)
```

### 2-8. 레이어·설정

- **신규 키 4종 전부 `REQUIRED_KEYS`** — `proto/config.py:40-43`
  (`anchor_prehook_executable`·`anchor_probe_records`·`policy_value_exclusions`·
  `deferred_owner_tracks`). 부재 시 `load_config` 중단(fail-closed) 확인.
- **의존 방향** — import 순환 없음. 다만 `proto/boundary.py:63` 이 패키지 밖 `audit_guard` 를
  import 하고(v2.6 부터, 토큰 단일 정의 목적·문서화됨), **v2.8 은 여기에 `audit_guard.PROBE_SITES`
  (`audit_guard.py:211-216`)가 최상위 소비자의 파일·함수명을 하드코딩하는 이름 수준 역참조를
  더했다**: `"t77-audit-battery": "test_contracts.py:t77_boundary"`. 최하위 모듈이 최상위
  러너의 내부 함수명을 안다 — 재사용 불가·책임 역전. fail-closed 방향이라 무음은 아니다
  (`t77_boundary` 이름을 바꾸면 unsanctioned window 로 red).
- **설정 기반 원칙 대비** — 그 토큰표는 코드 상수이고 개수만 `config.yaml:158` 에 있다.
  코드/설정 양쪽에 토큰 이름이 이중 기입되며 값 앵커(`audit_guard.PROBE_SITES=3563109d…`)가
  드리프트를 막는다. 강제는 되지만 "정책은 설정에" 원칙에는 어긋난다.
- **god-object / 비대** — 러너 단일 파일 3637행. 100행 초과 함수 5개:
  `t77_boundary` **855행**(`:1507`) · `self_check` 135 · `t2_input_missing_basis` 112 ·
  `main` 101 · `enforcement.violating_contexts` 111.
- **audit_guard 응집도** — 532행에 경로 정책·감사 hook·프로브 capability 발급·창 인가·기록
  버킷·부트스트랩 증인·기록 이관까지 7 책임. **토큰 발급을 맡으면서 비대해진 것이 맞다**
  (v2.7 대비 `PROBE_SITES`·`_ProbeWindow`·`probe_record_counts`·`unsanctioned_windows` 신설).

---

## 3. 복잡도 대비 실효 (지난 라운드 지적의 후속)

| 지표 | v2.7 | v2.8 | Δ |
|---|---|---|---|
| 러너 행수 | 3120 | **3637** | +517 (+16.6%) |
| 대조군 총계 | 38 | **39** | +1 |
| — 도메인 계약 (게이트·floor·register·enforcement) | 23 | **23** | **0 (3라운드 연속 불변)** |
| — 메타 (OD-3 경계 + 러너 자기검사) | 15 | **16** | +1 (`T-80`) |
| 러너 def/class 본문 중 메타 비중 | — | **65.0%** (2047 / 3150행) | — |
| 값 앵커 등재 이름 | 25 (수동) | **77** (census 75 + 정규화 2) | +52 |
| 필수 설정 키 | 23 | **27** | +4 |
| 한계 노트 | 21 | **22** | +1 (`L-EXIT-ROOT`) |

**신규 기구가 검사력을 늘렸는가, 검사 대상을 늘렸는가** — 실측으로는 **둘 다이되 비대칭**이다.

- 검사력 순증(실증): 프로브 재분류 통로 폐쇄(§2-3) · 심판 페이로드 검출(§2-5) · 잔존물 0(§2-6) ·
  `_NULLARY_STR_METHODS` 편입(§2-1) — 이번 라운드에 **닫힌 것이 4건**이다. 앞선 라운드보다
  실효가 높다.
- 검사 대상 순증: 신규 대조군 1개는 전부 메타(`T-80`). 값 앵커 25→77 은 **도메인 계약이 아니라
  러너·가드 자신의 상수**를 재는 것이다(77 중 `runner.*` 7 · `audit_guard.*` 15 · `boundary.*` 16
  = 38 이 자기검사 대상). 러너의 65% 가 메타다.
- **그리고 이번에도 가장 무거운 신규 결함이 새 메타 계층에서 났다** — §2-2 는 #2 교정으로
  만든 `T-80`/`independent_settings` 계층 안에서, §2-1 무음은 #5 교정으로 만든 census
  안에서, §2-4 불일치는 처분 B 등재 자체에서 났다. 관통 패턴은 v2.8 에서도 유지된다.

---

## 4. 신규 침묵·불일치 (표)

| ID | sev | dimension | location | finding | recommendation | conf |
|---|---|---|---|---|---|---|
| N-1 | **HIGH** | architecture | `tools/spikes/phase0_contract/test_contracts.py:535-554`, `:3242` · `proto/config.py:11,67` | 앵커 기대값의 **판독 경로**가 여전히 단일 지점(`config.CONFIG_PATH`)이며 그 이름은 census 가 잔여로 분류한 미결속 이름이다. 런타임 대입 1회 + 저장소 밖 위조 파일로 전건 GREEN·39/39·드리프트 0 을 재현했고, 그때 T-80 은 "이중 판독 일치=True · 위조 판독 검출=True" 를 출력한다. #2 의 지렛대가 `load_config` 바인딩에서 경로로 이동한 것 | 설정 경로를 러너 내부 상수(리터럴 상대경로)로 재-파생하거나 `CONFIG_PATH` 를 값 앵커 정의역에 편입해 잔여에서 빼라. 최소한 `:539-545` 의 "1→2 지점" 서술을 실측에 맞춰 정정하라 | 96 |
| N-2 | MEDIUM | architecture | `test_contracts.py:719`, `:693-734`, `:459-466`, `L-POLICY-ANCHOR :3334-3350` | census 가 `callable(value)` 로 클래스를 통째로 스킵하고 실행코드 앵커는 클래스 멤버 중 `__code__` 보유분만 본다. 그래서 **클래스 본문의 정책 상수는 `targets`·`residual`·실행코드 앵커 어디에도 나타나지 않는다** — 런타임 주입 실측 EXIT=0·39/39·잔여 27 불변. "새 상수가 생기면 등재 없이는 자동 red" 는 이 모양에 대해 거짓 | 클래스 속성도 census 정의역에 넣거나(권장), 최소한 잔여 열거에 클래스·함수 기본값 모양을 명시해 "정의역 밖" 이 전수임을 유지하라 | 92 |
| N-3 | MEDIUM | architecture | `test_contracts.py:3590`, `:113` | OD-3 고지(최종 요약)와 모듈 docstring 이 `owner track \`Phase 1\`` 을 **리터럴**로 단언한다. `deferred_owner_tracks` 를 미끼로 바꾸거나(F1) track 값을 바꿔도(F3) 이 문장은 불변 — 처분 B 등재의 선언층↔평가층 간극 | `:3205` 처럼 `deferrals` 에서 삽입값으로 파생하라 | 95 |
| N-4 | MEDIUM | architecture | `test_contracts.py:3158-3164` | SELF-3 의 이연 검증은 *등재된 항목의 참조 무결성*만 본다. `L-EXIT-ROOT` 자체가 이연돼 있어야 한다는 요구가 없어, 미끼 이연으로 바꿔도 SELF-3 은 green("이연 등재 1건", 문제=[]) 이고 검출은 방출 앵커 단독 | `deferral_problems` 에 "노트가 방출됐는데 이연 등재가 없다" 조건을 추가하라 (`rep.limit` 방출 id ↔ `deferred_owner_tracks` 대조) | 90 |
| N-5 | MEDIUM | architecture | `test_contracts.py:1044-1065` · `audit_guard.py:479-490` | 인가된 프로브 기록의 결속은 **토큰별 개수**뿐이다. 개수가 같은 내용 치환은 침묵(C3 실측). `:1045` 의 "identity 와 개수를 결속" 은 토큰 identity 만을 뜻하며 기록 identity 가 아니다 | 기록 텍스트의 정규화 digest를 토큰별로 함께 핀하거나, 서술을 "토큰 identity 와 개수" 로 정정하라 | 88 |
| N-6 | LOW | architecture | `test_contracts.py:3343-3345` vs `:3627`, `audit_guard.py:203,527,531` | `L-POLICY-ANCHOR` 는 제외 7종이 "운영 게이트와 `anchor_probe_records` 가 내용으로 판정한다" 고 적지만 `sanctioned_reads` 는 둘 다 소비하지 않는다(유일 소비 = 요약 `print`). 실제 안전장치는 정확-개수 이관이며 그것은 성립(fail-closed 실측) | 노트에 `sanctioned_reads` 의 실제 근거(정확-개수 이관)를 적어 근거-대상 대응을 맞춰라 | 92 |
| N-7 | LOW | architecture | `test_contracts.py:962` | #4 를 교정한 docstring 이 pre-hook 실행문을 "audit_guard.py **9**" 로 적는다. 실제·설정 핀 모두 **11**(`config.yaml:150`) | 값을 파생하거나 11 로 정정 | 99 |
| N-8 | LOW | architecture | `audit_guard.py:211-216` vs `config.yaml:158` | 최하위 가드 모듈이 최상위 러너의 파일·함수명(`test_contracts.py:t77_boundary` 등 4건)을 하드코딩한다. 레이어 역전 + 코드/설정 이중 기입(토큰 이름은 코드, 개수는 설정). fail-closed 라 무음은 아니나 재사용 불가 | 인가 표를 설정으로 올리고 가드는 표를 주입받게 하라(생성자·`sanction()` API) | 85 |
| N-9 | LOW | architecture | `test_contracts.py:1507` (855행), `:3355`, `:1248`, `:3533` · `proto/enforcement.py:236` | 100행 초과 함수 5개, `t77_boundary` 855행. 러너 단일 파일 3637행 중 메타 65% | OD-3 배터리를 `t77_*` 서브함수로 분해(순수 구조 변경, 앵커 재기입 필요) | 90 |
| N-10 | LOW | architecture | `test_contracts.py:704`, `:3320` | 잔여를 "정의역 타입 **밖**" 이라 라벨하지만 `dict`/`list` 는 정의역 타입인데 원소 타입 때문에 잔여로 간다(`boundary.NESTED(dict)` 실측). 라벨이 분류 근거를 잘못 서술 | "정의역 타입 밖 **또는 원소 타입 미지원**" 으로 정정 | 96 |

---

## 5. 재현 스크립트

전부 `<tmp>/scratchpad/` 에 있고 `<tmp>/scratchpad/repo/tools/spikes/phase0_contract` 에서
`PYTHONPATH=$PWD python3 <script>` 로 실행했다.

| 파일 | 목적 | §  |
|---|---|---|
| `drv.py <mut>` | 잔여 이름 런타임 대입 배터리 | 2-1 |
| `census_probe.py` | census 3분류 델타·팬텀·잔여 전수 재대조 | 2-1 |
| `silence_probe.py <mode>` | 클래스속성/중첩dict/int/함수기본값 무음 실증 | 2-1 |
| `kwdef_probe.py`, `kw2.py` | `__defaults__`/`__kwdefaults__` 변조 (전부 도메인 Case 가 검출 → 침묵 아님) | 2-1 |
| `forge.py <ov.json>` | `CONFIG_PATH` 재대입 + 위조 설정 수렴 | 2-2 |
| `probe_c.py`, `probe_c6.py` | 프로브 창 인가·개수·교차 스레드 | 2-3 |
| `probe_f.py '<json>'` | 이연 등재 미끼·팬텀·track 변조 | 2-4 |
| `probe_d.py` | pre-hook 페이로드 6종 | 2-5 |
| `probe_e.py` | 쓰기 두 층 무장 해제 후 잔존물 검사 | 2-6 |
| `probe_g.py` | 정확-개수 이관 fail-closed | 2-7 |

---

## 6. 렌즈 소견 (판정 아님)

- 이번 라운드는 앞선 세 라운드와 달리 **실제로 닫힌 항목이 4건**(#3·#4·#6 + #5 의 지목분)이고,
  critical 은 운영자 처분 B 에 따라 **등재·철회 형태로 정직하게 이행됐다** — 노트·고지·docstring
  4곳 전부 부정형이고, 이연 트랙이 설정 키로 존재하며, 지우면 방출 앵커가 잡는다.
- 남은 무게는 **#2 계열 한 줄기**다. `T-80` 은 함수 바인딩 축을 닫았지만 **경로 축을 열어 둔 채로
  "1→2 지점" 이라 적었고**, 실측은 여전히 1 지점이다(§2-2, EXIT=0 재현). 이것이 이번 라운드
  최대 관측이며, 심판이 v2.7 에서 지목한 "앵커 기대값을 읽는 경로 자체" 의 미이행분이다.
- §2-4·§2-1 의 두 건은 **처분 B 등재와 census 정의역 자체의 정합 흠결**이다 — 폐쇄 요구가
  아니라 등재·서술을 실측에 맞추는 문제다.
- 아키텍처 관점 부채는 방향이 일정하다: 자기검사 계층이 러너의 65% 를 차지하고, 가드가 소비자
  identity 를 하드코딩하며, 도메인 계약 수는 3라운드째 23 으로 고정이다. 구조가 **검사하는 대상보다
  검사기 자신을 더 많이 검사**하는 상태다.
