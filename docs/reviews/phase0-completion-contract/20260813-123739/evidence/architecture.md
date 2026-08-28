# 아키텍처 렌즈 **3라운드 재심** — Phase 0 완료 계약 프로토타입 v2.7

```yaml
lens: architecture
role: 증거 생산 (판정 없음 — verdict 는 Codex 심판 레인 소관)
target: tools/spikes/phase0_contract/{test_contracts.py, audit_guard.py, proto/*}
prior_verdict: .omc/review/20260813-094300/verdict.md (v2.6, needs-attention, findings 7)
prior_lens_evidence: .omc/review/20260813-094300/evidence/architecture.md (N-1..N-9)
baseline_run: exit 0 · 대조군 38건 중 양방향 성립 38건 · 앵커 5종 전부 일치
method: 원본 무수정. 격리 사본(<scratch>/arch3/repo/, .git 구조 포함) 위에서
        서브프로세스 in-memory 모듈 속성 교체 40여 종 + 디스크 편집 3종.
findings: 신규 10 (CRITICAL-class 1 / HIGH 2 / MEDIUM 3 / LOW 4)
prior_disposition: 해소 4 / 부분해소 3 / 미해소 0 / 회피 0
```

**무결성 고지.** 감사 전후 원본 12파일 SHA1 **동일** (`원본 12파일 SHA IDENTICAL`).
작업 트리에 `__pycache__`·`__probe*`·`__audit_probe*` 잔존 0. 디스크 편집은 전부
`<scratch>/arch3/repo/tools/spikes/phase0_contract/` 격리 사본에서만 수행했다
(예상 상대경로 + `.git/{HEAD,objects,refs}` 보존 — 사본이 38/38 GREEN 을 내는 것
자체가 `L-LOCATE-FORGE` 가 등재한 잔여와 정확히 일치한다는 실측이다).

```
$ python3 tools/spikes/phase0_contract/test_contracts.py; echo EXIT=$?
EXIT=0 · 대조군 38건 중 양방향 성립 38건
리터럴=b12eac36c30a30fe · 방출=46e56cdd28cc5cdc · 실행코드=4bf9cabe9f9b168f
소스바이트=28e51bd54b576e7e · Case산문=22de3ef00a40597f
```

---

## 1. 직전 7건 처분 — 해소된 것을 먼저 적는다

| # | sev | 직전 지적 | **처분** | 결정적 증거 |
|---|---|---|---|---|
| 1 | critical | SELF-2 가 합성 dict 만 본다 | **부분해소 (7/8 항 해소)** | 실 producer 8종 중 7종이 양성 대조군으로 전환됨. `digest_drift` 1항만 여전히 합성 — 그러나 **정직하게 등재**됨 |
| 2 | high | 가드 기록이 exit 에 닿지 않는다 | **해소** | 3채널 배선 + `T-77-SEPARATION` 이 "삼켜진 위반도 red" 를 실물 관측. 단 통합 지점이 새 초크포인트가 됨 → **N-1** |
| 3 | high | 순서 검사가 pre-hook 실행·동적 로드를 못 본다 | **해소 (잔여 등재)** | pre-hook 실행문 0 (구조 요구) + 동적 로드 34종 fail-closed + 구간 digest 핀. 주입 실측에서 red |
| 4 | high | `_REENTRANT` 프로세스 전역 | **해소** | `threading.local` + 정확일치 타입 화이트리스트. `T-77-REENTRANT` 가 교차 스레드 차단·`__fspath__` hook 밖 호출을 실측 |
| 5 | medium | `.git` 존재만 신뢰 | **해소** | 형태별 구조 검증 + `repository_top_level` 일치. `FsProbe` seam 으로 음성·양성 양방향 |
| 6 | medium | inode 별칭 | **해소 (정책 축소 + 등재)** | 심판이 제시한 선택지 (B) 채택. `T-77-INODE` + `L-INODE-ALIAS` |
| 7 | medium | 런타임 정책값이 앵커 밖 | **부분해소** | 값 앵커 2→25. v2.6 침묵 5종 전부 폐쇄. 그러나 등재 목록이 **실제 잔여보다 좁다** → **N-4**, 결속 자체가 우회 가능 → **N-2** |

**회피 판정 0건.** 저작자가 닫았다고 주장한 항목 중 실측에서 열려 있던 것은
`digest_drift` 생산축(#1 잔여) 하나이며, 이는 코드와 노트에 **명시**돼 있다
(`test_contracts.py:2641-2643`, `L-SELF-VISIBILITY`). 은폐가 아니다.

---

### #1 (critical) — SELF-2 producer 실재성: **7/8 해소**

**질문 2의 답: `self_check_probes` 는 실제 producer 를 쓴다.** 표면 이동이 아니다.

`self_check_probes()` (`test_contracts.py:2585-2644`)는 이름마다 **실제 `Report`**
를 만들고 실제 위반을 심은 뒤 `collect_self_checks()` 에 통과시킨다
(`:2687-2689`). producer 를 죽이면 red 가 되는지 8종 전수 실측 — 각 `Report`
메서드를 `[]` 반환으로 교체:

| producer 를 죽인 대상 | SELF-2 결과 | rc |
|---|---|---|
| `Report.unbound_defects` | `producer 생산 7/8 (침묵=['unbound'])` → red | 1 |
| `Report.green_bound_defects` | `침묵=['green_bound']` → red | 1 |
| `Report.undeclared_limits` | `침묵=['undeclared']` → red | 1 |
| `Report.missing_limits` | `침묵=['missing']` → red | 1 |
| `Report.duplicate_limits` | `침묵=['duplicated']` → red | 1 |
| **`Report.unresolved_limit_refs`** | `침묵=['unresolved']` → red | 1 |
| `Report.parked_limits` | `침묵=['parked']` → red | 1 |

특히 `unresolved` — 직전 라운드 **N-2** 가 "8항 중 유일한 **음성** 단언
(`== []`)이라 검출기를 죽여도 참으로 남는다"고 지적한 항 — 이 이번엔 양성으로
전환돼 producer 사망을 잡는다. **N-2 는 해소됐다.**

`collect_self_checks` 가 `digest_drift` 값을 버리도록만 바꿔도 SELF-2 가 잡는다:

```
### M6 collect_self_checks 가 digest_drift 값을 버린다
  rc=1 · 미성립: ['SELF-2']
  [SELF-2] producer 생산 7/8 (침묵=['digest_drift']) · 소비 7/8 (무시=['digest_drift'])
```

**잔여 1항.** `digest_drift` 의 producer 는 인자 자체이므로 그 프로브
(`:2643`)만 합성 문자열이다. 저작자 주장은 "실제 drift 는 `SELF-3` 이 독립
결속한다"인데 — **그 주장은 소비축에 대해서만 참이다**. `SELF-3` 이 검증하는
것은 `anchor_report_failures()` 라는 **소비 함수**이지, `actual != expected` 라는
**비교 그 자체**가 아니다(`:2755-2757` 은 손으로 만든 `"abcd!=efgh"` 문자열을
넣는다). 비교의 기대값 쪽은 무결속이며 그 구멍이 **N-2** 다.

### #2 (high) — 단일 seam / exit 결속: **해소** (질문 1의 답)

**N-1(직전) 이 지적한 `collect_self_checks(..., drift)` 단일 seam 은 실제로
해소됐다.** 앵커 드리프트는 이제 두 경로로 exit 에 닿는다:

- ⑴ `collect_self_checks(...)["digest_drift"]` → `self_check_green` → SELF-1 (기존)
- ⑵ `rep.anchors` (`:2947-2953`) → `anchor_report_failures()` (`:700-713`) →
  `exit_status()` (`main:3092,3116`) — **⑴과 독립**

**결속 절단 실측** — "그 결속 자체를 절단하면 무엇이 잡는가":

```
### M2 anchor_report_failures → 항상 [] (앵커 채널 절단)
  rc=1 · 미성립: ['SELF-3', 'SELF-1']
  [SELF-3] … 앵커 미계산 실패=False · 드리프트 실패=False   ← SELF-3 가 잡았다

### M3 operational_violations → 항상 [] (가드 기록 채널 절단)
  rc=1 · 미성립: ['SELF-1'] · 앵커 드리프트: ['실행코드=6ddb…!=4bf9…']

### M4 guard_record_violations → 항상 []
  rc=1 · 미성립: ['T-77-SEPARATION', 'SELF-1']   ← 실물 대조군이 잡았다

### M5 exit_wiring → 전부 True (SELF-3 배선 관측 위조)
  rc=1 · 미성립: ['SELF-1'] · 앵커 드리프트: ['실행코드=d477…!=4bf9…']
```

**자기참조가 아니다** — M2 는 `SELF-3` 이라는 **다른 Case** 가 잡고, M4 는
`T-77-SEPARATION` 이라는 **실물 프로브**가 잡는다. 그리고 `T-77-SEPARATION`
(`:1747-1800`)은 "대상이 `AuditViolation` 을 삼켜도 게이트가 발화하는가" 를
실제 코퍼스 열람으로 관측한다 — 심판 #2 의 권고가 그대로 이행됐다.

**다만 통합 그 자체가 새 단일 지점을 만들었다 → N-1.**

### #3 (high) — pre-hook 구간: **해소 (잔여 등재)**

`sys.path.insert` 를 **삭제**해 러너·`audit_guard.py` 둘 다 pre-hook 실행문
0개를 **구조 요구사항**으로 만들었다(`test_contracts.py:119-126`), hook 설치를
`audit_guard.py:296` 으로 올렸고, `prehook_analysis()` (`:643-694`)가 ⑴ marker
위치 ⑵ 동적 로드·I/O 이름 34종(`PREHOOK_FORBIDDEN_NAMES` `:566-605`) ⑶ 실행문
목록 ⑷ 구간 `ast.unparse` digest 를 파생한다.

심판이 든 정확한 시나리오를 격리 사본에 디스크 주입:

```
### M19 pre-hook 실행문 2건 주입 (sys.path.insert + __import__("proto.register"))
  rc=1 · 미성립: ['T-77-AUDIT', 'SELF-1']
  앵커 드리프트: ['Case산문=50c4…', '방출=ed49…', '소스바이트=31e3…']
```

**차단이 아니라 검출**이라는 점은 `L-AUDIT-BOOTSTRAP` 이 명시적으로 적는다
("⑶ … 그것은 **차단이 아니라 사후 검출**이다"). 과대주장 없음.

### #4 (high) — 재진입: **해소**

`_REENTRANT = threading.local()` (`audit_guard.py:191`), `_hook` 이
`getattr(_REENTRANT,"active",False)` 로 스레드별 판정 (`:283-289`).
`os.fsdecode` 는 `type(path) in _SAFE_PATH_TYPES` **정확 일치** 뒤에만 호출하고
그 밖은 판정 없이 차단 (`:221-227`, fail-closed). `T-77-REENTRANT` 가
⒜ 교차 스레드 차단 ⒝ 적대적 `PathLike` 차단 ⒞ `__fspath__` 가 hook **안**에서
호출된 횟수 0 을 실측한다. 화이트리스트를 좁히면 fail-loud:

```
### R6 audit_guard._SAFE_PATH_TYPES 축소
  rc=EXC BoundaryViolation: 판정 불가 경로 타입(fail-closed): PosixPath
```

### #5 (medium) — `.git` 의미 검증: **해소**

`git_marker_findings()` (`boundary.py:488-527`)가 디렉터리형은
`GIT_DIR_REQUIRED=('HEAD','objects','refs')`, 파일형은 `gitdir:` 포인터와 대상
`HEAD` 를 요구하고, `repository_top_level()` (`:529-540`)이 실제 top-level 일치도
본다. `L-LOCATE-FORGE` 는 v2.6 서술의 과대주장을 **명시적으로 정정**했다.
본 감사의 격리 사본이 `.git/{HEAD,objects,refs}` 한 벌을 만들어야만 통과했다는
사실이 "비용을 1 파일에서 구조 1 벌로 올린다"는 등재와 정확히 일치한다.

### #6 (medium) — inode 별칭: **해소 (정책 축소)**

심판이 제시한 두 선택지 중 (B)를 골랐고 이유가 구조적으로 타당하다:
canonical identity 집합을 만들려면 코퍼스 디렉터리를 열거해야 하고 **그 열거가
곧 OD-3-A 위반**이다(`audit_guard.py:66-75`). `T-77-INODE` Case + `L-INODE-ALIAS`
등재. 정책을 넓히는 대신 축소해 적는 것은 fail-closed 방향의 정직한 처리다.

### #7 (medium) — 런타임 정책값: **부분해소** (질문 3의 답)

값 앵커 2 → **25** (`policy_value_targets()` `:478-520`), 항목별 삭제·확장
대조군 **208건**. v2.6 에 침묵하던 항목 전수 재확인 — **전부 폐쇄**:

| v2.6 침묵항 | v2.7 결과 | 잡은 층 |
|---|---|---|
| `register.FIXTURE_CLAUSES` +1절 | **잡힘** rc=1 | `T-79` (`드리프트=['register.FIXTURE_CLAUSES=6161…!=81c6…']`) |
| `boundary.FORBIDDEN_SOURCE_TOKENS` 3→2 | **잡힘** rc=1 | `T-79` |
| `config.REQUIRED_KEYS` 23→4 | **잡힘** rc=1 | `T-79` |
| `boundary.FORBIDDEN_ARTIFACTS` 5→1 | **잡힘** rc=1 | `T-79` + `T-77-③` |
| `boundary.TOKEN_DEFINITION_NAMES` 확대 | **잡힘** rc=1 | `T-79` + 방출 앵커 |
| `boundary.GUARDED_ENTRY_POINTS` 34→3 | **잡힘** rc=1 | `T-79` + 방출 앵커 |
| `runner.DEFECT_WORDS` → () | **잡힘** rc=1 | `T-79` + `SELF-2` |
| `runner.PREHOOK_FORBIDDEN_NAMES` → ∅ | **잡힘** rc=1 | `T-79` + 방출 앵커 |
| `audit_guard._PROBE_DEPTH = 1` | **잡힘** rc=1 | 운영 게이트 (`프로브 창이 열린 채 남았다: depth=1`) |
| `audit_guard._READ_ARMED=False` | **잡힘** rc=1 | 운영 게이트 (`열람 정책이 내려갔다`) |
| `audit_guard._WRITE_ARMED=False` | **잡힘** rc=1 | 운영 게이트 (`쓰기 정책이 내려갔다`) |

**직전 라운드 N-3 표의 침묵 5종이 전부 닫혔다.** 이것은 실질 강화다.
잔여 문제는 두 가지이며 아래 **N-2**(결속 자체의 우회)와 **N-4**(등재 목록이
실제 잔여보다 좁음)로 분리해 적는다.

---

## 2. 신규 발견

## N-1 (CRITICAL-class) — #2 교정이 만든 **단일 초크포인트** `exit_status()`. 그것을 절단하면 3채널이 전부 침묵하고, 절단을 관측한 층의 판정도 같은 지점으로 되돌아간다

- **location**: `test_contracts.py:748-758` (`exit_status`), 소비 `:3116`
  (`return exit_status(failed, violations, anchor_failures)`), 관측 `:2748-2753`
  (`SELF-3` 의 `flipped` 계산이 같은 전역을 부른다)
- **위반한 원칙**: 자기참조 없는 강제 · 단일 실패 지점 · 관측층/판정층 분리
- **finding**:
  v2.6 의 `main()` 은 `return 0 if not failed else 1` 이라는 **인라인 식**이었다.
  v2.7 은 그것을 모듈 레벨 함수 하나로 승격하고 3채널을 전부 그리로 보냈다.
  그 결과 **모듈 속성 하나를 교체하면 세 채널이 동시에 죽는다**. 그리고 그
  절단을 유일하게 관측하는 `SELF-3` 의 red 조차 같은 함수를 통해 exit 로 나간다.

  ```
  ### M1 exit_status → 항상 0 (단일 초크포인트 절단)
    rc=0                                        ← 종료 코드 0
    대조군 38건 중 양방향 성립 36건
    미성립: ['SELF-3', 'SELF-1']                ← 두 Case 가 red 인데
    앵커 드리프트 — exit 결속: ['Case산문=37a7…!=22de…', '실행코드=2347…!=4bf9…']
    [SELF-3] … 채널별 판정 반전 0/3 []          ← SELF-3 는 정확히 탐지했다
  ```

  **종단 실증** — 실제 경계 강제까지 전면 해제한 상태:

  ```
  ### M14 exit_status 절단 + 열람·쓰기 정책 전면 해제
    rc=0
    미성립: ['T-77-AUDIT','T-77-REENTRANT','T-77-SEPARATION','SELF-3','SELF-1']
    앵커 드리프트 — exit 결속: ['Case산문=3a9d…','방출=9d71…','실행코드=2347…']
    운영 경계 위반(대조군 밖) — exit 결속: ['열람 정책이 내려갔다','쓰기 정책이 내려갔다']
    [SELF-1] 발견 3건 …
    !! 실물 잔존: ['__audit_probe_dir', '__audit_probe_w.tmp']
  ```

  **5개 Case red · 3개 앵커 드리프트 · 운영 게이트 2건 발화 · 발견 3건 ·
  repo 에 실물 파일 2개 생성 — 그리고 exit 0.** 세 채널이 전부 관측하고 전부
  **출력**했으나 종료 코드에 닿지 못했다. 이것은 심판 #2 가 지적한 결함
  ("가드가 관측·기록해도 exit 0")의 **정확한 재발**이며, 이번에는 그 결함을
  고치려고 만든 통합 지점 자체에서 일어난다.

  `SELF-3` 의 AST 검사(`exit_wiring`, `:761-810`)는 `main()` 의 **소스 텍스트**만
  본다. 소스는 그대로이므로 `exit_status 경유: True` 로 green 을 유지한다 —
  **배선의 실재는 관측하지만 배선된 함수의 동작은 관측하지 않는다.**
- **recommendation**: 종료 코드 결정을 하나의 교체 가능한 이름에 두지 않는다.
  최소 교정은 ⑴ `main()` 이 `exit_status()` 의 결과를 **독립 재계산**과 대조하고
  불일치면 무조건 1 을 반환하거나 ⑵ `exit_status` 를 `Report` 의 프로퍼티 등
  런타임 재바인딩이 불가능한 위치로 옮기거나 ⑶ `SELF-3` 이 `exit_status` 의
  `__code__` digest 를 **설정 핀**과 직접 대조하고 그 대조 실패 시
  `sys.exit(1)` 을 즉시 호출(반환값 경유 없이)하는 것이다.
- **confidence**: 98 (실측 2종, 대조군 4종)

## N-2 (HIGH) — 러너가 **import 로 바인딩한 이름**은 어느 앵커의 정의역에도 없다. 그 구멍으로 앵커 5종 전체의 기대값과 `T-79` 를 동시에 위조할 수 있다

- **location**: `test_contracts.py:134` (`from proto.config import cfg_int, cfg_list,
  cfg_pairs, load_config`); 앵커 정의역 `:368-392` (`_module_code_parts` 의
  `if getattr(obj, "__module__", None) != name: continue`)
- **위반한 원칙**: 앵커 정의역의 완전성 · **구조 파생 > 자기신고** (여기서는
  `__module__` 이라는 **함수 객체의 자기신고 속성**이 정의역을 결정한다)
- **finding**:
  ⒟ 실행코드 앵커는 모듈별로 `dir(module)` 을 돌면서 `obj.__module__` 이 그
  모듈과 같은 것만 묶는다. 그래서 **다른 모듈에서 import 해 온 함수는 러너의
  부분집합에서 제외**되고, 원본 모듈(`proto.config`)에는 원본이 그대로 있으므로
  그쪽 부분집합도 불변이다. 결과: `mod.load_config` / `cfg_list` / `cfg_pairs` /
  `cfg_int` 의 **재바인딩은 어느 앵커도 보지 못한다.**

  ```
  ### M9 load_config 재바인딩 (__module__ = "proto.config")
    rc=0 · 대조군 38건 중 양방향 성립 38건 · 앵커 드리프트: 없음
  ```

  **⒠ 소스바이트 앵커 무력화 실증** — 격리 사본의 `proto/gates.py` 에 주석 한 줄
  추가(오직 ⒠ 만 관측하는 편집):

  ```
  ### M18-a 디스크 주석 편집만 (대조군)
    rc=1 · 미성립: ['SELF-1'] · 앵커 드리프트: ['소스바이트=8d0f…!=28e5…']

  ### M18-b 같은 편집 + load_config 재바인딩 (기대값을 라이브 재계산으로 치환)
    rc=0 · 대조군 38건 중 양방향 성립 38건 · 앵커 드리프트: 없음
  ```

  **디스크가 실제로 편집된 상태에서 38/38 GREEN · exit 0.** 앵커 5종의
  *기대값* 은 전부 `load_config()` 한 곳에서 온다. 그 한 바인딩이 무결속이므로
  **앵커 시스템 전체가 관측되지 않는 단일 지점 위에 서 있다.**

  같은 구멍이 `T-79` 에도 적용된다 — `cfg_pairs` 를 재바인딩하면:

  ```
  ### M11c cfg_pairs 재바인딩 + 정책값 3종 무력화
    (REQUIRED_KEYS 23→4 · REPO_MARKERS 변조 · READ_EVENTS 3→1)
    [T-79] 정책값 25개 ↔ 등재 25개 일치=True · 드리프트=없음 · 미검출 0건
  ```

  `T-79` 가 **완전 green** 이다. 남은 red 는 전부 다른 층(`T-77-④`, 방출 앵커)이
  우연히 겹쳐서 잡은 것이고, `REQUIRED_KEYS` 만 단독으로 건드린 경우
  (`M11d`) `T-79` 는 침묵했고 `Case산문` 앵커가 **변형 개수(208→189)가 detail
  산문에 새어 나온 덕분에** 잡았다 — 설계된 검출이 아니라 부수효과다.

  이것이 **#1 잔여(digest_drift 생산축 무대조군)의 실체**다: 비교의 한쪽 항이
  통째로 위조 가능하므로, 비교 결과가 항상 "드리프트 없음"이 되는 상태를 어떤
  대조군도 관측하지 않는다.
- **recommendation**: ⒟ 의 정의역 판정을 `__module__` **자기신고**에서 구조
  파생으로 바꾼다 — `obj.__code__.co_filename` 이 그 모듈의 `__file__` 과 같은지
  보거나, 러너 네임스페이스의 **모든** callable 을 그 소속과 무관하게 묶는다.
  최소 교정으로는 `load_config`/`cfg_*` 를 러너에서 재바인딩 불가능하게
  (`proto.config.load_config(...)` 형태의 정규화 호출로) 바꾸고, 앵커 기대값을
  읽는 경로 하나를 `T-79` 의 값 앵커 대상에 넣는다.
- **confidence**: 97 (실측 3종 + 구조 증명)

## N-3 (HIGH) — `probe_window()` 의 분류가 이제 **exit 결속을 결정**하는데 창은 프로세스 전역이고, 러너 자신이 그 창 안에서 워커 스레드를 돌린다

- **location**: `audit_guard.py:248-252` (`_record` — `_PROBE_DEPTH>0` 이면
  `probe_reads`), `:358-376` (`probe_window`, `global _PROBE_DEPTH`);
  `test_contracts.py:716-732` (`guard_record_violations` 가 `blocked_*` **만**
  exit 에 싣는다), `:1701-1707` (러너가 창 **안에서** `threading.Thread` 기동)
- **위반한 원칙**: 선언층/평가층 일치 (등재 노트가 v2.6 시점 서술에 멈춰 있다)
- **finding**:
  v2.6 에서 프로브/운영 분류는 **출력 라벨**이었다. v2.7 은 `blocked_reads`/
  `blocked_writes` 를 exit 에 결속했고 `probe_reads`/`probe_writes` 는 결속하지
  않았다. 그 순간 **분류 = exit 결속 여부**가 됐다. 그런데 `L-AUDIT-PROBE-THREAD`
  는 여전히 v2.6 문장을 유지한다:

  > "창이 열린 동안 **다른 스레드의** 차단 기록도 프로브 쪽으로 간다.
  >  **차단 자체는 영향이 없고 분류만 이동한다.**"

  v2.7 에서 이 문장은 거짓이다. 실측:

  ```
  창 밖 위반 후: blocked_reads=1 probe_reads=0
  창 겹침 후:   blocked_reads=0 probe_reads=1
  → guard_record_violations() 상당 = 없음   (exit 결속 이탈)
  ```

  그리고 이 조건은 가정이 아니라 **러너가 스스로 만든다** — `T-77-REENTRANT`
  (`:1701-1707`)가 `with audit_guard.probe_window():` 안에서
  `threading.Thread(target=_cross_thread_probe)` 를 기동한다. 그 창이 열려 있는
  동안 **어느 스레드에서 발생한 진짜 위반이든** 프로브로 분류돼 exit 를 벗어난다.

  `_PROBE_DEPTH` 를 영구히 켠 채로 두는 조악한 우회는 운영 게이트가 잡는다
  (`R18: 프로브 창이 열린 채 남았다: depth=1` → rc=1). 잡지 못하는 것은
  **일시적 창과 겹친 위반**이다.
- **recommendation**: 프로브 창을 스레드 지역으로 만든다 (재진입 상태는 이미
  `threading.local` 로 옮겼다 — 같은 처방이 창에도 필요하다). 또는 프로브 기록을
  창의 깊이가 아니라 **호출 지점 identity** (프로브 자신이 넘긴 토큰)로 분류하고,
  토큰 없는 기록은 전부 운영 채널로 보낸다. 최소한 `L-AUDIT-PROBE-THREAD` 의
  "차단 자체는 영향이 없다"를 "v2.7 부터 분류 이동은 **exit 결속 이탈**이다"로
  정정한다.
- **confidence**: 95 (실측 + 러너 자신의 코드가 조건을 만듦)

## N-4 (MEDIUM) — `L-POLICY-ANCHOR` 의 "표 밖" 열거가 **실제 잔여보다 좁다**. 어디에도 이름이 없는 모듈 레벨 정책값 33종

- **location**: `test_contracts.py:2823-2838` (`L-POLICY-ANCHOR` 본문),
  `:489-492` (`policy_value_targets` docstring: "그 밖의 모듈 레벨 이름은
  `L-POLICY-ANCHOR` 에 미보호로 열거한다")
- **위반한 원칙**: 선언층/평가층 일치 · 전칭 주장의 반례 (`docs` 규율 §2.F)
- **finding**: 8개 앵커 대상 모듈의 모듈 레벨 정책값을 전수 열거해 3분류했다.

```
앵커됨 (policy_value_targets 25개) ............ 25
L-POLICY-ANCHOR 이 "밖" 으로 열거한 이름 ...... 26
*** 어디에도 이름이 없는 잔여 *** ............. 33
```

**미등재 33종의 런타임 대입 실측** (디스크 무편집, 격리 사본):

| 대상 | `file:line` | 결과 | 잡은 층 | 실질 위험 |
|---|---|---|---|---|
| `boundary._NULLARY_STR_METHODS` | `boundary.py:241` | **침묵 rc=0** | — | **있음** — `:289` 에서 라이브 사용. AST 폴딩 범위(`L-AST-FOLD`)가 조용히 축소된다 |
| `audit_guard._READ_EVENT_SET` | `audit_guard.py:151` | 침묵 rc=0 | — | 없음 (로드 후 죽은 상수) |
| `audit_guard.CORPUS_DIRNAME` | `audit_guard.py:116` | 침묵 rc=0 | — | 없음 (import 시점 파생만) |
| `audit_guard.SPEC_DIR` | `audit_guard.py:117` | 침묵 rc=0 | — | 없음 (동일) |
| `boundary._CORPUS_DIR` | `boundary.py:69` | 침묵 rc=0 | — | 없음 (동일) |
| `boundary._REGISTER_PREFIX` | `boundary.py:70` | 침묵 rc=0 | — | 없음 (동일) |
| `boundary._SPEC` | `boundary.py:79` | 침묵 rc=0 | — | 없음 (동일) |
| `boundary._VERIFICATION` | `boundary.py:80` | 침묵 rc=0 | — | 없음 (동일) |
| `audit_guard._WATCHED` | `audit_guard.py:153` | 잡힘 rc=1 | `T-77-AUDIT`·`T-77-REENTRANT`·`T-77-SEPARATION` | — |
| `audit_guard._WRITE_EVENT_SET` | `audit_guard.py:152` | 잡힘 rc=1 | `T-77-AUDIT` | — |
| `audit_guard._CORPUS_FOLDED` | `audit_guard.py:119` | 잡힘 rc=1 | `T-77-①-READ` 외 4건 | — |
| `audit_guard._REGISTER_FOLDED` | `audit_guard.py:120` | 잡힘 rc=1 | `T-77-AUDIT`·`T-77-INODE` | — |
| `audit_guard._SAFE_PATH_TYPES` | `audit_guard.py:159` | fail-loud (`EXC`) | — | `safe_path_types()` 로 앵커에 간접 포함 |
| `gates._G1_PREDICATES` | `gates.py:105` | 잡힘 rc=1 | 7개 Case | — |
| `register.METRIC_SUPERSET` | `register.py:32` | fail-loud (`EXC KeyError`) | — | — |
| `gates.CHECKABLE` | `gates.py:16` | fail-loud (`EXC KeyError`) | — | — |
| `floor.PACKAGE` | `floor.py:14` | 잡힘 rc=1 | Case산문 앵커 (부수효과) | — |
| `audit_guard.blocked_reads` (리스트 교체) | `audit_guard.py:175` | 침묵 rc=0 | — | 없음 (재바인딩 시점이 동일) |
| `audit_guard.sanctioned_reads` | `audit_guard.py:183` | 침묵 rc=0 | — | 없음 |

  **등재된 "밖"** 항목 중 재확인한 침묵 (등재대로 동작 — 결함 아님):
  `boundary._PATH_BLOCKED`→() 침묵 (감사 hook 이 실제 쓰기는 계속 차단),
  `register._CLAUSE_RE`→`.*` 침묵, `runner._INERT_STATEMENTS` 확장 침묵(→ N-8).

  요약: **위험한 미등재 침묵은 1건**(`_NULLARY_STR_METHODS`)이고 나머지는
  무해하거나 다른 층이 덮는다. 그러나 `policy_value_targets` docstring 의
  **전칭 주장은 그대로 거짓**이다 — 33개 이름 중 어느 것도 열거돼 있지 않다.
- **recommendation**: ⑴ `_NULLARY_STR_METHODS` 를 `policy_value_targets()` 에
  넣는다 ⑵ docstring 의 "그 밖의 모듈 레벨 이름은 … 열거한다"를 실제로 참이 되게
  하거나(= 열거를 완성) 문장을 축소한다 ⑶ 더 나은 구조 교정: 열거를 손으로 쓰는
  대신 `policy_value_targets()` 가 **모듈 스캔으로 파생**하고 앵커 대상에서
  제외하는 이름만 명시 예외로 두면(부정 목록 → 긍정 목록 반전) 새 상수가 생길 때
  자동으로 red 가 된다. 지금 구조는 **신규 정책값을 영원히 못 찾는다**
  (하드코딩 census 의 알려진 결함 클래스).
- **confidence**: 95 (전수 열거 + 개별 실측 19종)

## N-5 (MEDIUM) — 직전 라운드 **N-4 미해소**: 쓰기 프로브가 여전히 repo 안 실물이고, 기제가 깨지면 잔존물이 후속 실행을 영구 오염시킨다

- **location**: `test_contracts.py:1615-1617` (`_IO.open(_HERE/"__audit_probe_w.tmp","w")`,
  `_POSIX.mkdir(_HERE/"__audit_probe_dir")`), `:1639` (`audit_leftovers` 관측)
- **위반한 원칙**: 대조군 계층이 피검사 대상(OD-3-C)을 스스로 위반 · 회복 불가능성
- **finding**: 이번 라운드에서도 그대로 재현됐다.

  ```
  ### R1 audit_guard._WATCHED → ∅        !! 실물 잔존: ['__audit_probe_dir','__audit_probe_w.tmp']
  ### R3 audit_guard._WRITE_EVENT_SET→∅  !! 실물 잔존: ['__audit_probe_dir']
  ### M14 exit_status 절단 + 정책 해제     !! 실물 잔존: ['__audit_probe_dir','__audit_probe_w.tmp']
  ```

  그리고 **본 감사에서 실제로 측정을 오염시켰다**: 1차 배치의 정리 스크립트가
  실패해 `__audit_probe_w.tmp` 가 남았고, 이후 R2~R25 **전부**가
  `T-77-AUDIT` red + `Case산문=368395d2024c2d67` 로 수렴하는 **위양성**을 냈다.
  정리 후 재측정하니 R2·R7~R12·R23·R25 는 전부 rc=0 (침묵)이었다 — 즉 오염이
  없었다면 놓쳤을 침묵을 오염이 red 로 덮었다. 탐지는 fail-closed 지만
  **후속 실행의 관측력이 파괴된다.**
- **recommendation**: 직전 권고 그대로 — 쓰기 프로브의 표적을
  `tempfile.gettempdir()` 밑이나 **성공 자체가 불가능한 경로**(부재 디렉터리
  하위)로 옮긴다. 관측 대상은 "hook 이 발화하는가"이지 "쓰기가 성공하는가"가
  아니다.
- **confidence**: 98 (실측 3종 + 본 감사 자체가 피해자)

## N-6 (MEDIUM) — 복잡도 대비 실효: 신규 6 대조군이 **전부 메타**다. 도메인 계약 커버리지는 23건에서 한 건도 늘지 않았다 (질문 4의 답)

- **location**: `test_contracts.py:1160-1970` (`t77_boundary` **811행** —
  v2.6 449행에서 **+81%**), `:2842-2985` (`self_check` 144행)
- **위반한 원칙**: 단일 책임 · 검사기 자신이 검사 대상이 되는 재귀 비용
- **finding**: 실측 규모 (저작자 주장 대조 — 주장이 실제보다 낮다):

  | 항목 | v2.6 | v2.7 주장 | **v2.7 실측** |
  |---|---|---|---|
  | `test_contracts.py` | 2140 | 3060 | **3120** |
  | `audit_guard.py` | 220 | 415 | **418** |
  | 대조군 | 32 | 38 | **38** ✓ |
  | `t77_boundary` | 449행 | — | **811행** |

  **38 대조군의 성격 분해**:

  | 성격 | v2.6 | v2.7 | 증감 |
  |---|---|---|---|
  | 도메인 계약 (T-2·T-11·T-39·T-61·T-62·T-67…·UNCHK-019·U-8b) | 23 | **23** | **0** |
  | 러너 자기검사 (T-77-*·T-79·SELF-*) | 9 | **15** | **+6** |

  신규 6건 — `T-77-④-GIT`·`T-77-REENTRANT`·`T-77-SEPARATION`·`T-77-INODE`·
  `T-79`·`SELF-3` — 은 **전부 러너 자신의 강제 기구를 검사한다.**
  러너 최상위 def/class 2756행 중 **889행(32%)** 이 앵커·SELF·exit 배선·
  pre-hook·정책값 기구, 즉 자기검사 코드다.

  **검사력은 실제로 늘었다** — 위 §1 의 침묵 폐쇄 11종이 그 증거다. 그러나
  **검사 대상도 같은 만큼 늘었고**, N-1·N-2 는 정확히 **새로 늘어난 기구
  안에서** 발생했다: `exit_status`(신규 통합 지점)와 `load_config` 재바인딩
  (⒟ 앵커 정의역이 v2.5 부터 갖고 있던 구멍이 v2.7 에서 5종 앵커 전체의
  기대값을 통과시키는 지렛대가 됨). 즉 **이번 라운드의 CRITICAL·HIGH 2건은
  둘 다 교정이 만든 표면에서 나왔다.**

  구조적으로도 악화됐다: `t77_boundary` 는 Case 10개 + 노트 8개를 한 함수에서
  생산하는 **811행 god-function** 이 됐다.
- **recommendation**: `t77_boundary` 를 Case 경계로 쪼갠다
  (`t77_static_scan` / `t77_write` / `t77_read` / `t77_locate` / `t77_audit` /
  `t77_reentrant` / `t77_separation` / `t77_inode`). 함수 1개 = Case 1개로 만들면
  ⒟ 실행코드 앵커의 해상도도 함께 오른다(현재는 811행이 코드 객체 하나라 어떤
  편집이든 같은 단일 항으로만 나타난다). 그리고 **다음 라운드부터는 자기검사
  기구를 늘리기 전에 그 기구 자신이 어느 앵커의 정의역에 들어가는지를 먼저
  적는다** — 이번 두 HIGH 가 정확히 그 누락이다.
- **confidence**: 95 (전수 계수)

## N-7 (MEDIUM) — 직전 **N-5 미해소**: 두 가드의 예외 계통이 여전히 형제이고, 정본이 대신 막으면 대조군이 관측 대신 크래시한다

- **location**: `audit_guard.py:194` (`class AuditViolation(RuntimeError)`) vs
  `proto/boundary.py:204` (`class BoundaryViolation(RuntimeError)`) — **공통 조상 없음**
- **finding**: v2.7 에서도 그대로다. 심층 방어 목록을 줄이면 정본(감사 hook)이
  대신 막고 `AuditViolation` 이 프로브 루프를 통과해 `run_all()` 이 죽는다:

  ```
  ### R13 boundary._OS_BLOCKED → ()
    rc=EXC AuditViolation: 파일 쓰기 차단: os.rename:…/__probe_a
  ### R14 boundary._SHUTIL_BLOCKED → ()
    rc=EXC AuditViolation: 파일 쓰기 차단: shutil.copyfile:…/test_contracts.py
  ### R22 boundary._WRITE_FLAG_CHARS → ∅
    rc=EXC AuditViolation: 파일 쓰기 차단: open:…/__probe_open.tmp
  ```

  exit 는 비-0(예외)이라 fail-closed 지만 **Case 도 보고도 앵커도 남지 않는다** —
  "두 층 중 어느 쪽이 막았는지 나눠 관측한다"는 설계 의도가 한 방향에서만 성립.
  v2.7 에서 이 문제의 무게가 커졌다: exit 결속 채널 3종이 전부 `main()` 안에
  있으므로, `run_all()` 이 예외로 죽으면 **세 채널 모두 계산조차 되지 않는다.**
- **recommendation**: 공통 기반 `GuardViolation` 을 두고 두 클래스가 상속하게 한
  뒤 프로브 루프가 그것을 잡는다. 어느 층이 막았는지는 예외 타입으로 구별해
  `blocked` 라벨에 실으면 관측력이 오히려 는다. 추가로 `main()` 이 `run_all()` 을
  `try/except BaseException` 으로 감싸고 예외 자체를 네 번째 exit 채널로 결속한다.
- **confidence**: 95 (실측 3종)

## N-8 (LOW) — 교정 #3 이 도입한 정책값 `_INERT_STATEMENTS` 가 교정 #7 이 만든 앵커 표 **밖**에 있다 (형제 `PREHOOK_FORBIDDEN_NAMES` 는 안에 있다)

- **location**: `test_contracts.py:608-615` (`_INERT_STATEMENTS`) vs
  `:566-605` (`PREHOOK_FORBIDDEN_NAMES`, `policy_value_targets():496` 에 등재됨)
- **finding**: 두 상수 모두 v2.7 이 심판 #3 을 닫으려고 새로 만든 정책값이고
  둘 다 `prehook_analysis()` 의 판정을 정의한다. 하나는 앵커에 들어갔고 하나는
  안 들어갔다. 런타임 대입 실측:

  ```
  ### R25 runner._INERT_STATEMENTS 확장 (+ ast.Expr)
    rc=0 · 대조군 38건 중 양방향 성립 38건 · 앵커 드리프트: 없음
  ```

  실질 위험은 제한적이다 — 구간 digest 핀(`anchor_prehook_runner`)이 남아 있어
  새 pre-hook 문장 자체는 여전히 red 가 된다. 그러나 `executable` 목록이라는
  **관측 채널 하나가 조용히 죽는다**. 그리고 이 비대칭 자체가 "정책값을 하나
  추가할 때 앵커 등재를 함께 하는" 규율이 아직 기계 강제가 아니라는 신호다
  (→ N-4 의 구조 권고와 같은 뿌리).
- **recommendation**: `_INERT_STATEMENTS` 를 `policy_value_targets()` 에 추가한다
  (`tuple` of `type` 이므로 `policy_value_text` 의 `repr` 경로로 digest 된다 —
  타입 이름으로 정규화하면 `safe_path_types()` 선례를 그대로 따를 수 있다).
- **confidence**: 92 (실측)

## N-9 (LOW) — `claim_operational_records(1)` — 대조군 이관이 **개수·위치 기반**이고 개수 리터럴이 코드에 박혀 있다

- **location**: `test_contracts.py:1779` (`claimed = audit_guard.claim_operational_records(1)`),
  `audit_guard.py:406-418` (`blocked_reads[:count]` 를 잘라 `sanctioned_reads` 로 이관)
- **finding**: 이관은 identity 가 아니라 **개수 일치 + 앞에서부터 count 개**로
  이뤄진다. 저작자의 fail-closed 논거("개수가 어긋나면 이관이 성립하지 않는다")는
  `outside_before == 0` 을 `clean_green` 에 넣어 보강돼 있어 **단일 스레드에서는
  성립한다**. 그러나 ⑴ N-3 의 다중 스레드 조건에서는 두 측정 사이에 끼어든
  타 스레드 위반이 그대로 세탁되고 ⑵ 이관 개수 `1` 이 코드 리터럴이라 프로브를
  하나 더 추가하는 순간 조용히 어긋난다(설정 구동 원칙과도 어긋난다).
  또 `sanctioned_reads` 는 어떤 exit 채널에도 결속되지 않는 **세 번째 버킷**이다.
- **recommendation**: 이관을 record 문자열 identity (또는 프로브가 발급한 토큰)
  대조로 바꾸고, 개수는 프로브 정의에서 파생한다. `sanctioned_reads` 의 내용이
  프로브가 의도한 것과 정확히 일치하는지도 Case 로 관측한다.
- **confidence**: 88 (구조 실측; ⑴은 N-3 와 결합 조건)

## N-10 (LOW) — 직전 라운드 잔여 4건 그대로

- **A-4 미해소** — 러너가 `enforcement` 의 private 을 직접 호출: **11 지점**
  (`test_contracts.py:868, 892, 893, 2014, 2018, 2432, 2434, 2472, 2475, 2490, 2492`).
  `_check_u11`·`_check_t71`·`_check_u8a`·`_check_u10`·`_check_u9a`.
  (개선: 러너가 `audit_guard`·`boundary`·`floor`·`gates`·`register`·`config` 의
  private 을 건드리는 지점은 **0** 이다 — 이 부분은 깨끗하다.)
- **A-5 미해소** — `proto/` 안의 뮤테이션 어포던스: `enforcement.violating_contexts`
  (`enforcement.py:236`), `gates.build_reasons_ignoring_blocks_gate` (`gates.py:214`).
- **직전 N-8 미해소** — ⒜ 리터럴 앵커는 여전히 ⒠ 의 진부분집합이다
  (`test_contracts.py:2860` `own_source = Path(__file__).read_text()` vs
  `:412-443` 이 같은 파일 전 바이트). ⒜ 단독 red 를 내는 편집은 구조적으로 없다.
  `L-SRC-ANCHOR` 는 8종을 여전히 동격으로 적는다.
- **직전 N-9 미해소** — `proto` 패키지 자족성 없음
  (`spikes/` 에서 `import proto.boundary` → `ModuleNotFoundError`,
  `phase0_contract/` 에서만 성립) · `_patch` 헬퍼가 `boundary.py:643` 과 `:728`
  두 벌.

---

## 3. 레이어 경계 (질문 5의 답)

**순환 없음. 책임 전도 없음. 러너의 타모듈 private 접근은 `enforcement` 하나로 한정.**

```
audit_guard.py       → (stdlib only)                    ← 최하층, 순환 불가
proto/boundary.py    → ['audit_guard']                   ← 상향 의존 1건
proto/register.py    → ['config', 'floor']
proto/enforcement.py → ['config', 'floor']
proto/{config,gates,floor,__init__}.py → (stdlib only)
test_contracts.py    → audit_guard, proto/*
```

- `boundary.py:63 import audit_guard` 는 **패키지 밖 최상위 모듈 의존**이지만
  `audit_guard` 가 stdlib 만 의존하므로 순환은 원리적으로 불가능하다.
  근거(`audit_guard.py:3-12`: `proto/__init__.py` 실행조차 armed 여야 한다)도 타당.
- **DRY 는 오히려 개선됐다** — `boundary.read_violation` (`:450-454`)이
  `audit_guard.path_violation` 에 위임하고, 토큰 정의가 `audit_guard.py` 한 곳으로
  좁아졌으며(`boundary._CORPUS_DIR = audit_guard.CORPUS_DIR` 등 5건),
  `TOKEN_DEFINITION_SITE` 도 그 사실을 반영한다. 두 층의 판정이 드리프트할 수 없다.
- **`FsProbe`/`REAL_FS` seam 은 건전하다** (`boundary.py:467-486`).
  `git_marker_findings(root, fs=REAL_FS)` 의 기본 인자는 정의 시점에 바인딩되므로
  운영 경로는 항상 실제 FS 를 쓰고, 대조군만 주입한다. monkeypatch 를 쓰지 않고
  seam 을 명시한 것은 이전 라운드보다 나은 구조다 — `L-T77-SEAM` 이 그 이유
  ("실물을 만들면 그 행위 자체가 OD-3-B/C 위반")도 정확히 적는다.
- **책임 전도는 없다.** `boundary.py` 가 `audit_guard` 의 **public** 상수만
  읽고 private 은 건드리지 않는다(실측: `boundary.py` 안의 `audit_guard._*` 참조 0).

**남은 구조 부채**: `proto` 패키지 자족성 없음 (N-10). 본 구현(`tos/`)으로 이관하면
import-firewall 규율과 충돌한다 — `audit_guard` 를 **별도 최상위 패키지**로
승격해 상대 import 를 없애야 한다.

---

## 4. 설정 구동 (질문 6의 답)

**신규 키 3종 전부 `REQUIRED_KEYS` 에 있고 fail-closed 다.**

```
config.yaml 키 23 · REQUIRED_KEYS 23 · yaml-required: [] · required-yaml: []

### M16 config.yaml 에서 anchor_policy_values 제거
  rc=EXC ConfigError: 필수 키 누락: ['anchor_policy_values']
### M17 config.yaml 에서 anchor_prehook_runner 제거
  rc=EXC ConfigError: 필수 키 누락: ['anchor_prehook_runner']
```

`anchor_policy_values`·`anchor_prehook_runner`·`anchor_prehook_audit_guard`
(`proto/config.py:32-34`). 심판 #7 의 단서("앵커 값은 `config.yaml` 에 두어야
한다 — 코드에 박으면 그 자체가 위반")가 지켜졌다.

**코드에 남은 정책 하드코딩**:

| 대상 | `file:line` | 성격 |
|---|---|---|
| `claim_operational_records(1)` | `test_contracts.py:1779` | 이관 개수 리터럴 (→ N-9) |
| `GIT_DIR_REQUIRED = ("HEAD","objects","refs")` | `boundary.py:460` | **앵커됨** — 코드 상수지만 `T-79` 결속 |
| `GIT_FILE_PREFIX = "gitdir:"` | `boundary.py:463` | **앵커됨** |
| `TOKEN_DEFINITION_SITE = "audit_guard.py"` | `boundary.py:95` | **앵커됨**. 다만 `Path(audit_guard.__file__).name` 으로 파생 가능한 값을 리터럴로 유지 (직전 N-7 잔여) |
| `_NULLARY_STR_METHODS` | `boundary.py:241` | 미앵커 (→ N-4) |
| `_INERT_STATEMENTS` | `test_contracts.py:608` | 미앵커 (→ N-8) |

목록형 정책 상수가 코드에 남는 것 자체는 **`T-79` 값 앵커로 결속되면 허용
가능**하다는 것이 v2.7 의 입장이고, 25종에 대해서는 실제로 그렇다. 문제는 그
결속의 기대값 경로가 무결속이라는 것(N-2)과 표가 불완전하다는 것(N-4)이다.

---

## 5. 부수 관측 (비물질)

- `SELF-2` 의 `cross_talk` 검사(`:2698-2702`)는 좋은 추가다 — 프로브가 의도한
  항 외의 항을 오염시키면 red. 실측 baseline `교차반응=없음`.
- `T-79` 의 `variants` 총계(208)가 Case detail 산문에 실려 Case산문 앵커가
  **우연히** 정책값 목록의 길이 변화를 잡는다(M11d). 설계된 층이 아니므로
  의존하면 안 된다 — 길이 보존 치환에는 침묵한다.
- `is_hook_install()` 의 docstring (`:622-627`)이 "문자열 검색으로 찾으면 모듈
  docstring 안의 같은 낱말이 먼저 잡혀 구간이 빈 채로 통과한다 (실측: 첫 구현이
  정확히 그렇게 됐다)"라고 적는다 — **저작자가 자기 결함을 실측으로 잡고
  기록했다.** 구조 파생 규율이 실제로 작동한 사례다.
- `L-POLICY-ANCHOR` 이 `_WRITE_FLAG_CHARS` 를 `audit_guard` 의 이웃처럼 적지만
  실재는 `boundary.py:127` 이다. 팬텀은 아니고 소속 표기만 모호하다.
- `SELF-2`/`SELF-3` 을 `SELF-1` **앞**에 배치한 이유(`:3015-3016`)가 코드 주석에
  정확히 적혀 있고 실제 순서와 일치한다.

---

## 6. 재현 절차

```bash
# 베이스라인 (원본 무수정)
python3 tools/spikes/phase0_contract/test_contracts.py; echo "EXIT=$?"
# → EXIT=0 · 대조군 38건 중 양방향 성립 38건
#   리터럴=b12eac36c30a30fe · 방출=46e56cdd28cc5cdc · 실행코드=4bf9cabe9f9b168f
#   소스바이트=28e51bd54b576e7e · Case산문=22de3ef00a40597f
```

격리 사본 + in-memory 뮤테이션 하네스:

- `<scratch>/arch3/repo/` — 예상 상대경로 + `.git/{HEAD,objects,refs}` 보존 사본
  (사본 자체가 38/38 GREEN — `L-LOCATE-FORGE` 등재와 일치)
- `<scratch>/drive.py` — 서브프로세스마다 러너를 `importlib` 로 로드한 뒤
  모듈 속성을 교체하고 `main()` 을 호출. `sys.dont_write_bytecode=True` 선행
  (미설정 시 `__pycache__` 가 실물 쓰기가 된다)
- `<scratch>/enumerate_policy.py` — 모듈 레벨 정책값 전수 열거·3분류
- `<scratch>/thread_probe.py` — probe_window × 스레드 결속 이탈 실증
- `<scratch>/batch2.sh` — 잔여 침묵 배터리 (**매 실행 전후 `__audit_probe*` 제거
  필수** — 안 하면 N-5 로 후속 측정이 전부 오염된다)

**재현자 주의**: `_WRITE_*`·`_WATCHED`·`_READ_ARMED`·`_WRITE_ARMED`·`exit_status`
계열 뮤테이션은 `phase0_contract/` 에 `__audit_probe_dir`·`__audit_probe_w.tmp`
를 **실제로 남긴다**(N-5). 본 감사는 그 함정에 한 번 빠져 R2~R25 24건을
위양성으로 만들었고, 정리 후 전량 재측정했다. 이 문서의 수치는 전부 재측정값이다.

---

## 7. 렌즈 경계 고지

- **판정 없음.** 위 항목은 증거이며 gate 판정은 Codex 심판 레인 소관이다.
- 스타일·네이밍(style-auditor), 성능(performance-auditor), 시크릿·주입
  (security-auditor) 영역은 다루지 않았다. `sys.addaudithook` 의 보안 속성은
  보안 렌즈 소관이며 여기서는 강제 계층의 **설계**로만 평가했다.
- 설계 문서(`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`)
  본문 정합성은 이 렌즈 대상이 아니다 — 프로토타입 코드와 `proto/config.yaml`,
  그리고 러너가 방출하는 21개 한계 노트의 자기 서술만 대조했다.
- **비협상 규칙 대조**: 위 권고 중 CLAUDE.md 8조항과 배치되는 것은 없다.
  N-2·N-4 의 권고는 설정 구동을 **강화**하는 방향이고, N-1·N-3 는 fail-closed
  를 강화하는 방향이다.
