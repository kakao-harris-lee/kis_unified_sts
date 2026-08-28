# 아키텍처 렌즈 — v2.9 동결 검증 (5라운드) · 증거

```yaml
lens: architecture
mode: 증거 생산 (판정 없음 — verdict 는 codex-reviewer 소관)
scope: 좁음 — ① 동결 준수 ② 등재·정정 서술의 실제 일치 ③ 잔여 과대주장
non_goals: 신규 결함 사냥 · 신규 층 신설 권고 (= 동결 위반)
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
prior_verdict: .omc/review/20260813-141625/verdict.md   # Codex, needs-attention, findings 5
prior_lens:    .omc/review/20260813-141625/evidence/architecture.md
method: 3버전 AST/토큰 구조 대조 + 인메모리 뮤테이션 + 스크래치패드 사본 디스크 뮤테이션 6회
scratch: <tmp>/scratchpad/r5/{v28,v29,cur,run_*,m_*}
```

## 0. 원본 작업 트리 무결성

디스크 편집은 전부 스크래치패드 사본. 감사 시작·종료 해시 동일, `__pycache__` 잔존 0.

```
$ shasum -a 256 tools/spikes/phase0_contract/{test_contracts.py,audit_guard.py} \
                tools/spikes/phase0_contract/proto/{config.yaml,config.py}
38facfd788a06ee6bc2bb29fc9e9537c2775b62b24302e9da445960beeaa2f9b  test_contracts.py
09ccb91e59058c14d6986e8d4d5f54438587a17341974e8a68caca1801e0f971  audit_guard.py
5dbf4384e45920592aca87b1d2c7d33a258c6fd346593351d9133e6514dbc559  proto/config.yaml
152f6ae63a04e2f3f61a53dd7650a55cd1f0f26ba50030b6bfd1db9697a6f036  proto/config.py
$ find tools/spikes -type f -not -path '*__pycache__*' | sort | xargs shasum -a 256 | shasum -a 256
e4226648add754a8e3f91a2e43d883a4c6fb495810cbc519a09d0e5938a03c64  -   # 시작=종료
$ find tools/spikes -name __pycache__ -o -name '*.pyc'      # 출력 없음
$ git status --short
 M uv.lock   ?? docs/plans/...   ?? tools/spikes/   ?? tos-spec/src/.../decisions/
```

**대조 기준선 확보.** v2.8 실물(3637행, `28200f83…` — 심판이 기록한 수치·해시와 일치)과
v2.9 중간 스냅샷(3795행, `0ba40563…`)이 스크래치에 남아 있어 **3점 대조**가 가능했다.
세 버전 모두 동일 fake-repo 에서 완주: **exit 0 · 대조군 39/39 · 드리프트 없음**.

---

## ① 동결 검증 — 수치

측정기: `classify3.py` (tokenize+AST 3분류). 각 물리 행을 배타적으로 나눈다.
`LOGIC` = 문자열 아닌 실제 구문 토큰이 있는 행 · `STRTEXT` = 그 행의 실토큰이 문자열
리터럴뿐인 행(사람이 읽는 메시지 본문) · `PROSE` = 공백·주석·docstring 본문.

### 1-1. 대조군 — **동결 준수**

| 지표 | v2.8 | v2.9 | 현재 | Δ | 판정 |
|---|---|---|---|---|---|
| **대조군 총수** | 39 | 39 | **39** | **0** | 동결 |
| **도메인 계약 대조군** | 23 | 23 | **23** | **0** | 동결 (4라운드 불변) |
| 메타 대조군 | 16 | 16 | 16 | 0 | 동결 |
| Case 행 (SELF-1 자기보고) | 39 | 39 | 39 | 0 | 동결 |
| 신규 Case | — | 0 | **0** | 0 | 동결 |

대조군 표(출력 4–43행)를 v2.8 과 현재로 `diff` 한 결과 **행 구성·ID·순서 전부 동일**,
차이는 라벨 텍스트 2건 + 합성 메시지의 행번호 1건뿐이다(`audit_guard.py:534`→`:563`,
가드 파일이 산문 29행 늘어난 부수효과).

```
$ diff <(sed -n '1,60p' out_v28.txt) <(sed -n '1,60p' out_cur.txt)
21c21
< T-77-AUDIT   프로세스 전역 감사 hook (bootstrap 부터 armed)
> T-77-AUDIT   프로세스 전역 감사 hook (범위=L-AUDIT-BOOTSTRAP)
40c40
< T-80         설정 판독 이중화 + 바인딩 출처 결속
> T-80         설정 **파싱** 이중화 + 바인딩 출처 결속
57c57  (…audit_guard.py:534 → :563 …)
```

도메인 23 의 파생(감사 가능하게 명시): 메타 16 = `T-77-①·①-AST·②·③·①-READ·④·④-GIT·
AUDIT·REENTRANT·SEPARATION·INODE` (11) + `T-79·T-80·SELF-1·SELF-2·SELF-3` (5).
나머지 23 = `T-75, T-75/T-71, T-2, T-2-잔여, T-69, T-69-반증, T-62, T-62-cfg, T-61, T-70,
T-68, T-67, FWD-a-0, T-11, T-39, T-76, UNCHK-019, U-8b, T-71, T-72, T-73, T-74, T-47/48`.

> 동결 하에서 도메인 23 이 늘지 않은 것은 **정상**이다. 심판 `next_steps` 는 다음 증분에서
> 이것이 늘어야 한다고 했지 이번 판에서 늘라고 하지 않았다. v2.9 는 고치는 판이 아니다.

### 1-2. 행수 변화 — 실행 vs 산문 (저작자 "+158 중 실행 26" 실측 검증)

| 파일 / 구간 | physical | LOGIC | STRTEXT | PROSE | **ast.stmt** |
|---|---|---|---|---|---|
| 러너 v2.8 | 3637 | 2399 | 146 | 1092 | 1186 |
| 러너 v2.9 | 3795 | 2428 | 196 | 1171 | 1204 |
| 러너 현재 | 3823 | 2430 | 202 | 1191 | 1204 |
| **Δ v2.8→v2.9** | **+158** | **+29** | +50 | +79 | **+18** |
| **Δ v2.9→현재(후속)** | **+28** | **+2** | +6 | +20 | **+0** |
| **Δ v2.8→현재(총)** | **+186** | **+31** | +56 | +99 | **+18** |
| audit_guard 총 Δ | +29 | **+0** | +0 | +29 | **+0** |
| proto/config.py Δ | +4 | **+0** | +0 | +4 | **+0** |

**저작자 보고 대조:**

- **"+158 행" = 정확.** 단, 그것은 **v2.9 레그만**이다. 후속 정정 +28 을 더한 **총 +186** 이
  현재 실물이다. 후속 레그는 `ast.stmt` **+0** — 즉 100% 서술이다(추가 LOGIC 14행은
  전부 f-string 메시지 연결행이며 새 문장을 만들지 않는다).
- **"실행 26 행" = 실증됨, 오히려 보수적.** v2.9 레그의 추가 LOGIC 41행 중 실제 문장을
  나르는 행은 ~24행(나머지는 메시지 문자열 인자행)이고, 구조 측정치인
  **`ast.stmt` 증가는 +18** 이다. 저작자 수치가 실제보다 넓지 않다 — **7라운드 만에
  자기보고가 실제보다 좁은 쪽으로 처음 어긋났다.**
- 추가 문장 +18 의 소재: 전부 **기존 함수 본문 안**이다. `SELF-3` 의 이연 블록 재작성
  (`:3250-3271`, 필수 map 대조 + `classify_owner_track` 재사용), `rep.limit("L-CONFIG-TRUSTPOINT", …)`
  호출 1건, `exit_root_track = config.cfg_pairs(...)` 1건.

### 1-3. 신규 구조물 — 전부 0

```
$ python3 struct.py v28/test_contracts.py cur/test_contracts.py
  top-level CONST  12 -> 12   +[]  -[]
  top-level def    71 -> 71   +[]  -[]
  top-level class   4 ->  4   +[]  -[]
  nested def       17 -> 17   +[]  -[]
$ python3 struct.py v28/audit_guard.py cur/audit_guard.py      # 4항 전부 +[] -[]
$ python3 struct.py v28/proto/config.py cur/proto/config.py    # 4항 전부 +[] -[]
```

| 동결 항목 | 실측 | 판정 |
|---|---|---|
| 신규 Case | **0** | 준수 |
| 신규 앵커 **종류** | **0** — `config.yaml` 키 집합 diff 는 `required_deferrals` 1건뿐이고 `anchor_*` 계열 추가 없음. 방출 노트 `L-SRC-ANCHOR` 도 v2.8·v2.9·현재 모두 "앵커는 **8 종**" | 준수 |
| 신규 검사 **계층** | **0** — 신규 함수·클래스·모듈 0. 변경은 기존 `SELF-3` 본문 +18문장. owner-track 문법은 새 검사기를 만들지 않고 **피검사 계약의 `register.classify_owner_track` 을 재사용** | 준수 |
| 신규 **모듈 레벨 상수** | **0** — 러너·가드·config 모두 top-level CONST 증감 0. `config.REQUIRED_KEYS` 는 **원소** 1개 증가(새 이름 아님) | 준수 |
| 신규 한계 노트 | **+1** (`L-CONFIG-TRUSTPOINT`) — 검사층이 아니라 **등재**이며 처분 B 가 지시한 산출물 | 준수 |
| census 정의역 | targets 75+정규화 2=77 · 제외 7 · 잔여 27 — **3버전 전부 동일** | 불변 |

`T-79` 항목별 변형만 436→437 로 +1 이나, 이는 `REQUIRED_KEYS` 원소 1개 증가에서
**파생된** 수치이지 신규 대조군이 아니다.

**① 결론: 동결은 지켜졌다.** 대조군·Case·앵커 종류·모듈 레벨 이름·함수·클래스 전부 Δ0,
코드 증분은 심판이 지목한 `SELF-3` 1건에 국한된 +18문장이며 나머지 +168행은 서술이다.

---

## ② 서술 정확성 — 표본별

### 2-1. `L-POLICY-ANCHOR` 의 "전수" 축소 — **[일치]**

축소 후 서술(`policy_value_census` docstring `:728-733` + 방출 노트): "`callable(value)`/모듈
스킵이 **이름 등록보다 앞**이라 클래스는 `targets` 뿐 아니라 `residual`·`phantom` 에서도
사라진다 — **실측 52 개** 모듈 레벨 클래스 중 어느 하나도 세 분류에 나타나지 않는다."

```
$ python3 probe_census.py                       # run_cur, 라이브 모듈
anchor modules            : ['runner','audit_guard','boundary','config','enforcement','floor','gates','register']
module-level classes found: 52          <-- 서술의 "52 개" 와 일치
census targets            : 75
census residual           : 27
census phantom            : 0
C1/C2 classes in ANY of the three buckets: 0  []      <-- targets·residual·phantom 전부 부재

C3 클래스 속성에 정책 tuple 을 심고 재census:
   +targets=[]  +residual=[]  +phantom=[]
   control (같은 tuple 을 모듈 레벨 NAME 으로): +targets=['boundary._PLANTED_TUPLE']
   exec-code 앵커: 속성 변조로 텍스트 변화? False
```

**대조군이 살아 있음이 확인된 상태**(모듈 레벨 이름은 `+targets` 로 잡힘)에서 클래스 형태만
세 분류 전부에서 무음이다. 내가 직전 라운드 N-2 로 보고한 그것이며, 개수(52)·정의역
(targets·residual·phantom 3분류 전부)·실행코드 앵커 무관성까지 **서술이 실제와 일치한다.**

### 2-2. `L-CONFIG-TRUSTPOINT` — 직전 N-1 의 이전 정확성 — **[일치]**

```
test_contracts.py:3385   independent = independent_settings(config.CONFIG_PATH)
```

방출 노트 본문: "주 판독기 `config.load_config()` 와 이 Case 의 두 번째 판독기
`independent_settings()` 는 파싱 코드가 다르지만 **경로는 둘 다 `config.CONFIG_PATH` 라는
같은 이름에서 온다** … `CONFIG_PATH` 는 값 앵커의 정의역 밖(잔여)이라 재바인딩 자체도
관측되지 않는다 … 이 Case 의 `foreign` 검사는 **모듈 항에 대해 항등식**이다 —
`binding_file(module)` 이 곧 `basename(module.__file__)` 이므로."

N-1 의 세 성분(① 1지점 ② `CONFIG_PATH` 가 앵커 정의역 밖 ③ 모듈 출처검사 항등식)이 **전부**
옮겨졌고, 내가 재현했던 위조 절차(`ANCHOR_IMPORT_ROOTS` 축소 → `CONFIG_PATH` 1회 재바인딩
→ exit 0 · 39/39 · 드리프트 없음)까지 노트에 그대로 적혀 있다. v2.8 의 "비용을 1 지점에서
2 지점으로 올렸다" 는 `independent_settings` docstring `:558-559` 에서 **"실측 1 지점이므로
거짓이었다"** 로 명시 철회. 함수 docstring 제목도 "**파싱 코드가** 독립인" 으로 한정됐다.

### 2-3. 후속 정정 — `SELF-3` 이 강제하는 명제 — **[일치]**

서술(`self_exit_wiring` docstring `:3226-3235`): "강제하는 것은 ⑴ 두 설정 줄의 상호 일치
⑵ owner-track 문법 ⑶ 대상 노트 등재 — **이 셋뿐**. 처분 값 자체는 강제하지 않는다:
둘 다 `Phase 5` 로 옮겨도 `SELF-3` green — 값을 잡은 것은 **방출 산문 앵커 하나**이고 그
산문도 함께 재기입하면 통과한다. `required_deferrals` 는 **하한** — `L-CASEFOLD` 를
덧붙여도 green."

디스크 뮤테이션 4건(스크래치패드 사본, 각 config.yaml 2줄만 교체):

```
M1  두 줄 함께 Phase 5   SELF-3 → OK      (필수 1건 상호일치=True)   [서술과 일치]
M2  L-CASEFOLD 추가 등재  SELF-3 → OK      (이연 등재 2건, 필수 1건 상호일치=True)  [하한 서술과 일치]
M3  대조군: 두 줄 불일치   SELF-3 → 결함   문제=["필수 이연 불일치 L-EXIT-ROOT='Phase 1' (실제='Phase 5')"]
M4  대조군: 미끼 대체     SELF-3 → 결함   문제=["필수 이연 불일치 L-EXIT-ROOT='Phase 1' (실제='<부재>')"]
```

M3·M4 가 red 이므로 검사는 **공허하지 않다**. 특히 M4 는 심판 v2.8 #5 가 지목한 미끼 대체
그 자체이고 이제 잡힌다 — **#5 는 실제로 교정됐다.**

"값을 잡은 것은 방출 산문 앵커 하나" 도 그대로 재현된다:

```
M1 전체 실행:  EXIT=1 · 39건 중 38건 · 미성립=['SELF-1']
               앵커 드리프트 = ['방출=bb76690b1b65a238!=8ca46af8df2d1623']   <-- 딱 1종
좌표 편집 재현: 그 방출 digest 한 줄만 재기입 → 재실행
               EXIT=0 · 대조군 39/39 · 앵커 드리프트 없음 · SELF-3 OK
               (디스크 config.yaml 은 pristine 과 DIFFERENT — 3줄 편집이 diff 에 남는다)
```

즉 **설정 3줄 편집으로 처분 값이 통과한다** — "처분 값을 고정하는 것은 이 러너가 아니라
판정 기록과 운영자 결정" 이라는 서술이 정확하다. 이 서술은 실제보다 **좁다**(방출 앵커가
무단 변경을 red 로 만드는 사실을 자기 공적으로 세지 않았다) — 과대 아닌 과소 방향이다.

### 2-4. 후속 정정 — `required_deferrals` = 하한 — **[일치]** (M2, 위)

`config.yaml` 주석도 같은 명제를 적는다: "이 map 은 **하한이지 정확 집합이 아니다** …
필수 항을 만족한 채 다른 이연을 **추가로** 등재하면 통과한다." 실측 일치.

### 2-5. 심판 5건이 실제로 **방출 노트**에 등재됐는가 — **[일치]**

코드 주석이 아니라 러너가 stdout 으로 방출하는 노트 본문에 들어갔는지 확인했다
(v2.8 출력에는 해당 문자열 0건).

| 심판 # | 등재 위치 | 방출 본문에 실린 실측치 |
|---|---|---|
| #1 CONFIG_PATH 단일 신뢰점 | **신규** `L-CONFIG-TRUSTPOINT` | 위조 절차 + exit 0 · 39/39 |
| #2 probe 사칭·개수 치환 | `L-AUDIT-PROBE-THREAD` 확장 | "`unsanctioned_windows` 는 비었고 토큰별 개수는 (6,2)/(1,0)/(1,0)/(1,0) 로 불변 … 차단 한 건이 조용히 사라졌다" |
| #3 ClassDef 본문 실행 | `L-AUDIT-BOOTSTRAP` 확장 | "실행문 개수는 1(핀과 동일)·동적 이름 findings 는 0 인 채로 hook 설치 **전에 15,736 바이트**를 실제로 읽었다" |
| #4 클래스 census 소실 | `L-POLICY-ANCHOR` + `L-SRC-ANCHOR` 축소 | §2-1 |
| #5 미끼 이연 | **코드 교정**(유일) + 하한 서술 | §2-3 |

정정 표지 실측: v2.9 표지 50개(러너 32·yaml 11·가드 7), 정정 형태 42개.
저작자 신고 43(33+10)과 정합(±1, 정규식 경계 차이).

---

## ③ 잔여 과대주장

전수 grep 결과(현재 러너 / v2.8 러너):
`전수 8/13` · `전부 38/38` · `자동 12/14` · `모든 6/6` · `결속 43/42` · `폐쇄 11/12` ·
`독립 9/8` · `강제 33/28` · `요구한다 4/3`.

`폐쇄` 11건은 **전부 부정형**("폐쇄가 아니라 가시화")이거나 도메인 Case 명(`superset 우회 폐쇄`)
이다. `자동` 의 핵심 문장은 `:733` 에서 **"'새 상수가 생기면 자동으로 red' 는 모듈 레벨
비호출 이름에 한해 참이다"** 로 정의역이 명시됐다. `독립` 은 `:551/:559` 에서
"파싱 코드가 독립 / 독립인 것은 파싱 코드뿐" 으로 한정됐다. `전수` 잔존 8건 중 6건은
닫힌 우주가 출력에 함께 찍힌다(`SELF-2` 8/8, `T-79` 437건, `SELF-3` 3/3, `우주 = 레지스트리 키`).

**남은 것 1건.**

### R-1. `_module_code_parts` docstring `:446` — "코드 객체 **전수**" 가 국소 거짓

```
severity: LOW
dimension: architecture
location: tools/spikes/phase0_contract/test_contracts.py:446
confidence: 95   (실측 · 대조군 성립)
```

`"모듈 네임스페이스에 **바인딩된** 코드 객체 전수를 모은다"`. 수집기는
`getattr(obj, "__code__", None)` 로만 판정하므로(`:470`, `:478`) **descriptor 로 감싼 멤버는
`__code__` 를 직접 갖지 않아 정의역 밖**이다. 앵커 대상 8모듈에서 실측 6건:

```
runner.Case.ok                (property)      boundary.ReadRecorder.clean  (property)
boundary.WriteRecorder.clean  (property)      gates.Predicate.pid          (property)
gates.Evaluation.__new__      (staticmethod)  gates.Evaluation._make       (classmethod)
```

대조군 포함 실측:

```
D1 property `Case.ok` 를 교체       -> exec-code 앵커 텍스트 변화? False
D2 대조군: 같은 클래스의 평문 함수 멤버 교체 -> 변화? True        <-- 수집기는 살아 있다
D3 boundary.ReadRecorder.clean(property) 교체 -> False
D4 gates.Evaluation._make(classmethod) 교체   -> False
```

`Case.ok` 는 장식이 아니다 — `return self.clean_green and self.mutant_red`, 즉 **Case 판정
술어 자체**이며 `:3727`(verdict 표기)·`:3792`(`failed = [c for c in rep.cases if not c.ok]`)
가 소비한다. red 를 심어 놓고 이 property 만 바꾸면 Case 채널이 통째로 침묵한다:

```
seeded-red repo (M3), main() 인프로세스 구동
 baseline : main()=1 · 대조군 37/39 · 미성립=['SELF-3','SELF-1']
 patched  : main()=1 · 대조군 39/39 · 미성립=<absent>   <-- Case 채널 침묵
            (exit 1 은 Case산문 digest 가 움직여서일 뿐 — 광고된 실행코드 앵커가 아니다)
```

**왜 과대주장인가 (등재 이후 기준):** 방출 노트 `L-SRC-ANCHOR` 는 같은 사실을 **정확히**
적는다 — "묶이는 것은 그 클래스의 `__code__` 를 가진 멤버뿐". 그리고 같은 노트가 "디스크를
건드리지 않는 **런타임 대입**은 소스 바이트가 보지 못하고 **실행 코드 앵커**와 정책값 앵커가
본다" 고 그 층을 광고한다. 즉 노트는 맞고 **docstring 의 `전수` 한 단어만 노트와 어긋난다.**
v2.8 에서 "잔여 27 전수" 가 심판에게 지적된 것과 **동일한 어휘 실패 클래스**의 재발이다.

**권장 조치 (동결 준수 — 코드 층 신설 아님):** `:446` 의 `전수` 를 `L-SRC-ANCHOR` 가 이미
쓰는 표현("`__code__` 를 **직접** 가진 객체")으로 좁히고, descriptor 6건이 정의역 밖이라는
사실을 `L-SRC-ANCHOR` 본문에 한 줄 등재한다. **서술 교정만이며 새 검사층·새 앵커·새
대조군을 요구하지 않는다.**

### 참고 (과대주장 아님으로 판정한 경계 사례)

- `:1223` "러너의 **어떤 편집이든** 설정 갱신을 요구한다" — `runner_source_anchor(source: str)`
  docstring 이며 입력이 파일 텍스트라 문맥상 **디스크 편집** 한정이고, 소스바이트 앵커가
  9파일 정확 바이트를 묶으므로 그 정의역에서 참이다. `config.yaml:130` 이 v2.5 의 같은
  문구를 "거짓이었다 — ⒠ 를 더한 지금은 참이다" 로 이미 이력 정정했다. 런타임 재바인딩까지
  포함해 읽힐 여지는 있으나 국소 문맥이 이를 배제한다 — **불일치로 세지 않는다.**
- `L-EXIT-ROOT`·`L-SELF-VISIBILITY` 는 same-process 재바인딩 전반을 구조적 한계로 이미
  등재한다. R-1 이 그 범주에 완전히 흡수되지는 않는다 — R-1 의 대상은 **그 회귀를 덮으라고
  광고된 층 자신의 구멍**이고, 그 사실이 어느 노트에도 적혀 있지 않기 때문이다.

---

## 4. 요약 (판정 아님 — 관측)

- **① 동결은 지켜졌다.** 대조군 39·도메인 23·Case 39·앵커 8종·모듈 레벨 이름·함수·클래스
  전부 Δ0. 코드 증분은 `SELF-3` 1건에 국한된 `ast.stmt` **+18**, 후속 레그는 **+0**.
  가드·config.py 는 실행 Δ0(산문만). "다음 증분은 도메인 대조군 증가로 제한" 이라는 심판
  지시의 **전제 조건**(메타 확장 정지)이 충족된 상태다.
- **② 표본 4건 전부 [일치].** `L-POLICY-ANCHOR`(52개 클래스·3분류 전부 부재),
  `L-CONFIG-TRUSTPOINT`(1지점·앵커 정의역 밖·항등식 3성분 전부), `SELF-3` 강제 명제
  (Phase 5 이동 green, 잡는 것은 방출 앵커 1종, 재기입으로 통과), `required_deferrals`
  하한 — 서술이 지목한 뮤테이션을 그대로 실행했고 **전부 서술대로 거동했다.**
  대조군(M3·M4·census 통제군·D2)이 전부 반대 방향으로 반응하므로 공허한 일치가 아니다.
- **③ 잔여 과대주장 1건**(R-1, `:446` 의 `전수`). v2.8 의 15곳 정정 후 남았던 국소
  과대주장이 이번엔 **1건까지 줄었고**, 그 1건조차 같은 파일의 방출 노트가 이미 올바른
  표현을 쓰고 있어 어휘 통일 문제다.
- **자기보고 정확도**: 6라운드 연속 "실제보다 넓던" 저작자 서술이 이번에는 실측과
  일치하거나 **좁은** 쪽이었다(§1-2, §2-3). 다만 "+158" 은 v2.9 레그만이고 실물 총증분은
  **+186** 이라는 점은 보고에 없었다.
```
