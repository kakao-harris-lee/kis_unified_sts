# security 렌즈 — 라운드 5 (v2.9 · 처분 B 등재 검증)

```yaml
lens: security
scope: 등재된 한계 4 종 + SELF-3 후속 정정 1 종의 서술 정확도 (전면 감사 아님)
question: 등재한 한계가 실제 동작을 정확히 예측하는가 · 잔여 과대주장이 있는가
verdict: 내지 않음 (렌즈는 증거만 생산)
method: 스크래치패드 사본에서 동적 재현 (원본 무수정)
baseline: exit 0 · 대조군 39/39 · 앵커 5 종 불변
isolation: /private/tmp/.../scratchpad/repo{,_e3,_e5} + .git/{HEAD,objects,refs}
original_integrity: 16 파일 shasum 전건 일치 · __pycache__ 0 · git status 변화 없음
```

## 요약 표

| 노트 | 판정 | 근거 |
|---|---|---|
| `L-CONFIG-TRUSTPOINT` | **정확** | 재바인딩 1 회로 두 판독기 전환 확인 · 위조 기대값 **정확히 3 개**로 exit 0/39-39 재현 · `foreign` 은 모듈 항에 대해 항등식임을 구조·실측 양방향 확인 |
| `L-AUDIT-PROBE-THREAD` ⓑ | **정확** | `compile` 사칭 창 `sanctioned=True` · 창이 전역 `probe_reads` **객체 자체**를 반환 · 동일 개수 내용 치환 후 게이트 3 종 전부 침묵 · 코퍼스 차단 1 건 소실 |
| `L-AUDIT-BOOTSTRAP` | **정확** (부수 1 건은 과대등재) | pre-hook `ClassDef` 본문에서 15,736 B 실독 · 계수 1 불변 · 동적 이름 findings 0 · 핀 갱신 후 exit 0 재현 |
| `L-POLICY-ANCHOR` | **정확** | 모듈 레벨 클래스 **52 개** 전건이 targets·residual·phantom·excluded 어디에도 없음 · 클래스 속성 런타임 대입 후 앵커 5 종 불변·exit 0 |
| `SELF-3` 후속 정정 | **정확** | 두 줄 동시 이동 → SELF-3 green · 추가 등재 → green · 미끼/문법/미등재 3 형태는 정상 red |

**노트가 실제보다 축소 서술인 사례(= 실제가 더 나쁨)는 0 건.** 잔여 과대주장 1 건은 §7.

---

## 1. `L-CONFIG-TRUSTPOINT` — **정확**

### 1a. 재바인딩 1 회 (`e1a_trustpoint.py`)

위조 설정 = 디스크 `config.yaml` + 마커 키 1 줄, 다른 경로. `config.CONFIG_PATH` **한 번** 재바인딩.

```
### E1a probe
rebindings performed        : 1
primary reader marker       : yes-this-is-not-the-repo-file
independent reader marker   : yes-this-is-not-the-repo-file
both readers on forged file : True
### E1a verdict
main() exit status          : 0
repo config.yaml unchanged  : True
대조군 39건 중 양방향 성립 39건
앵커 드리프트 — exit 결속: 없음
```

### 1b. 물질적 위조 — 기대값 3 개 (`e1b_trustpoint.py`)

라이브 모듈에 신규 정책 상수 `audit_guard.ZZZ_FORGED` 주입(= 노트가 "등재 없이는 red" 라 적은 형태).

- 라운드 1(위조 없음): `exit 1` · 미성립 `['T-79','SELF-1']` · `드리프트=['audit_guard.ZZZ_FORGED=e21ac393e9ca489b!=None']`
- 라운드 3(위조 기대값 3 개: `anchor_policy_values`, `anchor_limit_emitted_digest`, `anchor_case_prose_digest`):

```
main() exit status          : 0
repo config.yaml unchanged  : True
대조군 39건 중 양방향 성립 39건
앵커 드리프트 — exit 결속: 없음
[T-79] census 76+정규화 2=78개 ↔ 등재 78개 일치=True · 드리프트=없음 · 항목별 변형 439건 중 미검출 0건
```

노트 본문의 "**새 기대값 세 개**를 담은 위조 설정 … 디스크 `config.yaml` 이 바이트 그대로인 채 exit 0 · 대조군 39/39 · 앵커 드리프트 없음" 과 **개수까지 일치**한다.

### 1c. `foreign` 항등식 (`E1c`)

```
all 8 anchor modules: binding_file(m) == basename(m.__file__) -> True
after replacing runner.config with a decoy module from /somewhere/else:
  T-80 `foreign` list -> EMPTY (axis silent)
function axis (note says this is the one with substance): ast.py vs config.py
```

구조적으로도 항등식이다 — `binding_file(obj)` 는 `__code__` 부재 시 `basename(obj.__file__)` 을 돌려주므로 `test_contracts.py:3397` 의 비교는 `x != x` 다. 노트의 "모듈 항에 대해 항등식", "실질을 갖는 것은 코드가 온 파일이 다른 **함수** 뿐" 둘 다 참.

부수 확인: `config.CONFIG_PATH(PosixPath)` 는 baseline 잔여 27 개 목록에 실제로 들어 있다 → "값 앵커의 정의역 밖(잔여)이라 재바인딩 자체도 관측되지 않는다" 참.

---

## 2. `L-AUDIT-PROBE-THREAD` ⓑ — **정확**

`e2_probe.py`: 정상 `main()` 완주 후 상태에 대해 사칭 → 치환 → 게이트 재판정.

```
### E2 baseline (after a normal main() run)
main() exit                 : 0
probe counts                : {'t77-audit-battery': (6, 2), 't77-cross-thread': (1, 0), 't77-reentrant': (1, 0), 't77-separation': (1, 0)}
unsanctioned_windows        : []
probe_record_violations     : []

### E2 impersonation result   (compile(SRC, "test_contracts.py", "exec") · def t77_boundary)
window.sanctioned           : True
window yielded the real list: True      # __enter__ 가 audit_guard.probe_reads **객체 자체**를 반환
unsanctioned_windows        : []
probe counts (after)        : {'t77-audit-battery': (6, 2), 't77-cross-thread': (1, 0), 't77-reentrant': (1, 0), 't77-separation': (1, 0)}
probe_record_violations     : []
guard_record_violations     : []
```

치환 전/후 기록:

```
before: t77-audit-battery | open:코퍼스 디렉터리 접근: .../repo/tos-spec/src
after : t77-audit-battery | <substituted by impersonated window>
```

노트가 적은 세 성분 — ⑴ 평문 토큰 + `basename:co_name` 만으로 인가 ⑵ 가변 `probe_reads` 반환 ⑶ 토큰별 개수만 계수 — 이 전건 성립하고, "**실제로 기록돼 있던 코퍼스 차단 한 건이 조용히 사라졌다**" 도 그대로 재현된다. 앵커 개수 `(6,2)/(1,0)/(1,0)/(1,0)` 도 노트 본문과 동일.

---

## 3. `L-AUDIT-BOOTSTRAP` — **정확**

`repo_e3` 에서 `import audit_guard` **직전**에 삽입:

```python
import _io  # E3

class _E3PreHookBody:
    _blob = _io.FileIO(str(_HERE / "proto" / "register.py"), "r").readall()
    _decoy = _io.FileIO(".../e3decoy/EVIDENCE-REGISTER-zz.csv", "r").readall()
```

```
### E3 pre-hook class body read 15736 bytes from proto/register.py
### E3 pre-hook class body read 4096 bytes from a guard-blocked name
[T-77-AUDIT] pre-hook 구간 문제=['test_contracts.py: pre-hook 구간 digest 347715bd..!=381ab3fb..']
             · pre-hook 실행문 러너 1건/audit_guard.py 11건(등재 대조)
앵커 드리프트: ['Case산문=..', '소스바이트=f3dcc84d..!=2d2ccad5..', '실행코드=8877cf8e..!=3cdc0fa8..']
```

- **실행문 계수 1 불변** (핀 `test_contracts.py=1` 과 동일) — 노트대로 `ClassDef` 본문이 걸리지 않는다.
- **동적 이름 findings 0** — `pre-hook 구간 문제` 에 digest 만 있고 금지 이름 항이 없다. `FileIO`·`readall` 부재 확인.
- **15,736 바이트** — `proto/register.py` 실제 크기와 정확히 일치(노트 본문 수치와 동일).
- 추가 관측(노트가 명시하지 않은 강화 방향): 같은 구간에서 **가드가 이름으로 차단하는 경로**(`EVIDENCE-REGISTER-*`) 4,096 B 도 읽힌다. 노트의 "이 구간에서 실제 I/O 가 일어나도" 서술 범위 안이다.
- **"고정이지 차단이 아니다" 실증**: 드리프트한 핀 5 개(`anchor_prehook_runner`·`anchor_runner_source_digest`·`anchor_source_bytes_digest`·`anchor_case_prose_digest` ×2 라운드)를 갱신하니

```
exit=0
### E3 pre-hook class body read 15736 bytes from proto/register.py
### E3 pre-hook class body read 4096 bytes from a guard-blocked name
대조군 39건 중 양방향 성립 39건 · 앵커 드리프트 — exit 결속: 없음
[T-77-AUDIT] pre-hook 구간 문제=없음
```

pre-hook 구간에서 실제 I/O 를 하면서 exit 0 · 39/39 가 성립한다.

---

## 4. `L-POLICY-ANCHOR` — **정확**

```
### E4a  class visibility in the automatic census
module-level classes seen   : 52
of those in targets         : none
of those in residual        : none
of those in phantom         : none
of those in excluded        : none

### E4b  runtime class-attribute policy constant
census target count  before : 75  after : 75
census residual      before : 27  after : 27
appears anywhere?           : False
main() exit with class attr : 0
    대조군 39건 중 양방향 성립 39건
    산문 앵커 대조: 리터럴=beba34d736e562d7 · 방출=8ca46af8df2d1623 · 실행코드=3cdc0fa82958477d
                   · 소스바이트=2d2ccad5d27c431d · Case산문=fa00b7f9bb3d156a
    앵커 드리프트 — exit 결속: 없음
```

- 노트 본문(`policy_value_census` docstring)의 "**실측 52 개** 모듈 레벨 클래스 중 어느 하나도 세 분류에 나타나지 않는다" — 개수까지 정확.
- 클래스 속성에 정책 상수(`FsProbe.POLICY_ALLOWLIST`, `UnchkRow.POLICY_ALLOWLIST`)를 **런타임**으로 놓아도 census 3 분류 전건 무변화, 앵커 5 종이 baseline 과 **바이트 동일**, exit 0.
- 개수 정합: 노트의 "77 개" = census 75 + 정규화 2. 잔여 27. 전부 baseline 과 일치하며 "그 축소된 정의역 안의 값" 이라는 단서가 붙어 있다.

---

## 5. `SELF-3` 후속 정정 — **정확** (그리고 이번 라운드 코드 교정은 실제로 작동한다)

`repo_e5`, `proto/config.yaml` 두 줄만 변형:

| 변형 | `deferred_owner_tracks` / `required_deferrals` | SELF-3 | 드리프트한 앵커 |
|---|---|---|---|
| a | `L-EXIT-ROOT=Phase 5` / `L-EXIT-ROOT=Phase 5` | **OK (green)** | 방출 **하나** |
| b | `…Phase 1,L-CASEFOLD=Phase 2` / `L-EXIT-ROOT=Phase 1` | **OK (green)** | Case산문 하나 |
| c | `L-CASEFOLD=Phase 2` / `L-EXIT-ROOT=Phase 1` | **결함 (red)** | — |
| d | `L-EXIT-ROOT=Phase 99` (양쪽) | **결함 (red)** | — |
| e | `L-NOT-DECLARED=Phase 1,L-EXIT-ROOT=Phase 1` / `…` | **결함 (red)** | — |

```
a: [SELF-3] … 이연 등재 1건(필수 1건 상호일치=True — 하한 검사이며 처분 값 자체는 강제하지 않는다)
   앵커 드리프트 — exit 결속: ['방출=bb76690b1b65a238!=8ca46af8df2d1623']
   (고지 출력도 함께 이동: "owner track `Phase 5` 로 이연", "owner track = Phase 5, 필수 = Phase 5")
b: 이연 등재 2건(필수 1건 상호일치=True) → SELF-3 green
c: 문제=["필수 이연 불일치 L-EXIT-ROOT='Phase 1' (실제='<부재>')"]
d: 문제=["L-EXIT-ROOT: phase 범위 밖: 'Phase 99'"]
e: 문제=['L-NOT-DECLARED: 미등재 노트']
```

노트가 예측한 대로다:

- "두 줄을 함께 다른 트랙으로 옮기면 `SELF-3` 은 green" → 참.
- "**값을 잡은 것은 방출 산문 앵커 하나**" → 참. 변형 a 에서 드리프트한 앵커는 정확히 `방출` **1 종**뿐이고 나머지 4 종은 불변이다. (`config.yaml` 은 소스 바이트 앵커에서 자기참조로 제외되므로 설정 편집 자체는 앵커를 움직이지 않는다.)
- "`required_deferrals` 는 **하한**이라 추가 이연 등재도 통과" → 참 (변형 b, 노트가 예시로 든 `L-CASEFOLD` 그대로).
- "강제되는 것은 상호 일치·문법·등재 여부 셋뿐" → 변형 c/d/e 가 각각 그 셋에 대응해 red. **미끼 이연은 실제로 잡힌다** — 이번 라운드의 유일한 코드 교정이 주장대로 작동한다.

---

## 6. 원본 무결성

```
=== shasum re-check vs baseline ===
ORIGINAL TREE UNCHANGED (16 files, identical checksums)
=== stray pycache / pyc under original ===
(none)
=== git status of original (spikes only) ===
?? tools/spikes/          # 감사 전과 동일 (untracked 디렉터리)
```

모든 실행은 `sys.dont_write_bytecode = True` 하에 스크래치패드 사본에서만 수행했다.

---

## 7. 잔여 과대주장

### OC-1 — 철회된 "identity 결속" 주장이 호출자 docstring 에 살아 있다 · **HIGH 신뢰**

`tools/spikes/phase0_contract/test_contracts.py:1128-1129`

```
    `T-77-SEPARATION` 이 관측하고, 분리된 쪽의 개수·identity 는
    `probe_record_violations()` 가 설정 앵커에 결속한다 (v2.8).
```

바로 그 `probe_record_violations()` 의 자기 docstring이 **같은 파일 24 줄 위**에서 이 문장을 거짓으로 선언한다:

> `test_contracts.py:1104-1106` — "v2.8 은 이 함수가 "identity 와 개수" 를 결속한다고 적었다. **거짓이었다** — 세는 것은 개수뿐이고 기록 **본문**은 어느 층도 읽지 않는다."

`audit_guard.py:491-497`, `proto/config.yaml:192-194`, `L-AUDIT-PROBE-THREAD` 본문도 전부 "개수만" 으로 정정돼 있는데 **이 한 곳만 v2.8 원문 그대로**다. §2 의 실측이 이 문장이 거짓임을 직접 보인다 (동일 개수 내용 치환 후 `probe_record_violations()` = `[]`).

- 유형: 국소 과대주장 (v2.8 에서 철회된 명제의 잔존)
- 완화: `개수·identity` → `토큰별 개수` 로 정정. 정정 시 소스 바이트·실행코드 앵커가 함께 움직인다.

### OC-2 — 검출 층 열거가 실측보다 **좁다** (= 과대등재, 노트가 실제보다 비관적) · MEDIUM 신뢰

`tools/spikes/phase0_contract/audit_guard.py:46-47`

```
    그 형태를 잡는 층은 함께 갱신 가능한 구간 digest 와 소스 바이트
    앵커뿐이며, 그것은 차단이 아니라 고정이다.
```

§3 실측에서는 **실행코드 앵커도** 드리프트했다(`8877cf8e..!=3cdc0fa8..`). 러너 쪽 같은 취지의 노트(`test_contracts.py:2360-2361`)는 "구간 digest 와 소스 바이트·**실행코드** 앵커뿐" 으로 3 종을 적는다 — 두 파일이 갈린다. 방향은 **약화가 아니라 과대등재**(실제 검출 층이 등재보다 많음)이므로 안전 쪽 오류지만, 두 문장이 같은 형태를 다르게 서술한다.

- 완화: `audit_guard.py:46` 에 실행코드 앵커를 추가하거나, 러너 노트를 정본으로 참조.

### OC-3 — docstring 요약 한 줄이 `L-CONFIG-TRUSTPOINT` 보다 넓다 · LOW 신뢰

`tools/spikes/phase0_contract/test_contracts.py:3363`

```
    """T-80 — 앵커 **기대값 판독 경로**의 이중화 + 소비 바인딩 구조 결속 (v2.8).
```

이중화된 것은 **파싱 코드**뿐이고 "판독 경로" 는 단일 신뢰점이다. 같은 docstring 이 13 줄 뒤(`:3376-3382`)에서 정확히 그렇게 정정하고, **출력되는 Case 이름**(`:3409`)은 이미 "설정 **파싱** 이중화" 로 좁혀져 있다. 독자가 요약 줄에서 멈출 때만 성립하는 국소 잔여다.

- 완화: 요약 줄을 "설정 **파싱** 이중화" 로 통일.

### 판정: 참으로 남는 절대어

전수(10) · 전부(45) · 자동(13) · 모든(6) · 결속(58) · 폐쇄(12) · 독립(9) · 강제(37) · 요구한다(8) 전건을 훑었고, 위 3 건 외에는 **등재 이후에도 참**이다. 특히:

- "새 상수가 생기면 등재 없이는 red 가 된다" — 항상 "**모듈 레벨 비호출 이름**일 때만" 단서가 붙어 있다 (`test_contracts.py:733,3507-3508`, `config.yaml:5-8`). §4 의 클래스 반례가 그 단서 밖이다.
- "폐쇄가 아니라 가시화" 계열 12 곳 — §1b·§3 이 실증한 "설정 diff 를 함께 내면 지난다" 와 정합.
- `config.yaml:16` — "이 파일의 어떤 주석도 '설정을 고치지 않고는 통과할 수 없다' 를 절대 명제로 뜻하지 않는다" 는 §1a(설정 무편집 통과)와 정합.
- `test_contracts.py:1223` "러너의 **어떤 편집이든** 설정 갱신을 요구한다" — 소스 바이트 앵커 정의역(9 파일 정확 바이트) 안에서 참이며, `config.yaml` 자기참조 제외는 같은 docstring 이 명시한다.

---

## 8. 범위 밖으로 남겨둔 것 (동결 준수)

심판 `next_steps` 의 "메타 하네스 확장 동결" 에 따라 **새 검사 층 신설 권고는 하지 않는다.** OC-1/2/3 은 전부 산문 정정이며 신규 코드 층을 요구하지 않는다. 도메인 계약 대조군(23 건 불변)에 대한 판단은 이 렌즈의 이번 라운드 범위 밖이다.
