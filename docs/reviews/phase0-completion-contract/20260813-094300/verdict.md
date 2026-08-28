# verdict — 레인 A (코드 심판) · v2.6 재심 · **13회 완주 (4회 시도)**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 15회 연속
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_scope_digest: 89be9b0c89b86d2e04696574fb3a909305a4ff6520c5346019960eebb395e11f
reviewed_scope: tools/spikes/phase0_contract/ (전부 untracked — --scope working-tree)
reviewed_version: v2.6 (F1·F3 교정분)
findings: 7                        # critical 1 / high 3 / medium 3
prior_verdict: .omc/review/20260813-075200/verdict.md
mode: A (adversarial-review, --scope working-tree), 약 9분, write=false
method: **정적 독해 한정** (아래 방법 축소 기록)
lens_evidence: .omc/review/20260813-094300/evidence/ (architecture · security)
lens_scope_reduction: performance·style 생략 (아래 기록)
```

리비전 결속: 디스패치 직전 = 심사 종료 후 **동일**. 드리프트 0, 작업 트리 오염 없음.

## ⚠ 방법 축소 기록 — 이번 판정의 독립성 한계

**Codex 는 대상 코드를 실행하지 않고 정적 독해만으로 판정했다.** 이는 도구 제한 때문이며,
저작자가 선택한 것이 아니라 **4회 시도 끝에 도달한 유일한 성립 경로**다.

| 회차 | focus | 결과 | 발화 지점 |
|---|---|---|---|
| 1 | `focus.txt` | 콘텐츠 정책 거부 | 소스 열람 직후 |
| 2 | `focus.txt` | 콘텐츠 정책 거부 | 렌즈 증거 열람 직후 |
| 3 | `focus2.txt` (방어적 재작성) | 콘텐츠 정책 거부 | **11분 심층 분석 후, 런타임 프로브 실행 중** |
| **4** | **`focus3.txt` (정적 독해 한정)** | **판정 성립** | — |

3 회차가 진단을 확정했다: **트리거는 focus text 서술이 아니라 Codex 자신의 동적 프로브 활동**
(`importlib` · `sys.addaudithook` 시험)이었다. focus2 재작성은 초기 분류기를 통과시켰다.

**범위는 축소하지 않았다** — 4 건 해소 판별 · 렌즈 6 건 · 미폐쇄 17 건 대조 · 회피 판별 전부 유지.
**축소된 것은 방법이다.** 그 대가를 명기한다: **Codex 는 렌즈의 실행 결과 주장을 독립적으로
재현하지 못했고**, 그 부분은 코드 독해로만 검증했다. 경험적 재현의 독립성은 이번 판정에 없다.

## 처분

**직전 4 건**: #1 **해소(정적 proto import 한정)** / #2 **해소** / #3 **부분해소 — 표면 이동** /
#4 **부분해소(디스크 해소·런타임 미해소)**.
**렌즈 6 건 전건 성립** (Codex 독립 확인). 30→32·4→5 증가는 실제 커버리지 확대이나
**독립 폐쇄를 뜻하지 않는다.** 저작자 등재 미폐쇄 17 건은 **여전히 실제 잔여보다 좁다** —
pre-hook 실행 · 동적 로드 · inode 별칭 · **audit 기록의 exit 미소비** · producer seam 누락.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Ship 불가. 직전 #1은 정적 proto import에 한해 해소됐고, #2의 _io·casefold·samefile 및 #4의 9파일 소스바이트 앵커는 실질 강화다. 그러나 #3은 SELF-2가 합성 dict만 소비해 producer 결함을 한 층 위로 옮겼고, #4도 런타임 정책값에는 부분해소다. 렌즈 6건은 모두 성립한다: architecture N-1은 critical, security N-1/N-2와 architecture N-6은 high, S-5/S-9는 medium이다. 30→32와 4→5 증가는 실제 커버리지 확대지만 독립 폐쇄를 뜻하지 않는다. 미폐쇄 17건도 pre-hook 실행, 동적 로드, inode 별칭, audit 기록의 exit 미소비, producer seam 등을 빠뜨려 실제 잔여보다 좁다. 대상 실행 없이 정적 독해로 판정했다.

Findings:
- [critical] SELF-2가 실제 producer가 아닌 합성 dict만 검증한다 (tools/spikes/phase0_contract/test_contracts.py:1840-1856)
  SELF-2는 collect_self_checks()의 반환값을 사용하지 않고 키만 가져온 뒤, 각 키에 직접 합성 값을 주입해 self_check_green()이 False인지 확인한다. 특히 digest_drift producer에는 빈 tuple을 전달한다. 따라서 collect_self_checks()가 실제 producer 값을 []로 버려도 SELF-2는 통과한다. 앵커 5종 역시 실제 drift가 line 1802의 단일 항을 통해서만 exit에 닿으므로 그 항을 무력화하면 앵커 불일치가 출력에만 남고 모든 Case가 green이 될 수 있다. 이는 직전 자기충족 결함의 표면 이동이다.
  Recommendation: 각 검사마다 실제 Report 위반 또는 의도적 anchor mismatch를 producer에 넣고 collect_self_checks()를 거쳐 red가 되는 양성 대조군을 추가하라. digest drift는 SELF-1 내부 dict와 독립된 필수 Case 또는 main의 직접 실패 조건으로도 결속하라.
- [high] 대조군 밖 경계 위반 기록이 종료 코드에 반영되지 않는다 (tools/spikes/phase0_contract/test_contracts.py:2116-2136)
  main()은 failed를 Case.ok만으로 계산한다. outer monkeypatch recorder와 audit_guard.blocked_reads/blocked_writes는 출력만 하며 실패 조건에 포함하지 않는다. 대상 코드가 AuditViolation을 잡으면 가드는 위반을 탐지·기록했어도 러너는 exit 0이 될 수 있다. 이는 이 프로토타입의 핵심 계약인 '발견을 종료 코드에 반영'을 직접 위반한다.
  Recommendation: probe_window 밖의 blocked_reads/blocked_writes와 outer read/write recorder 시도를 독립 Case 또는 main의 직접 실패 조건에 포함하라. 의도적 프로브 기록과 운영 위반 기록의 분리를 유지한 채 caught violation 대조군을 추가하라.
- [high] 로드 순서 검사가 pre-hook 실행과 동적 import를 보지 못한다 (tools/spikes/phase0_contract/test_contracts.py:1048-1061)
  order_ok는 정적 ast.Import audit_guard와 ast.ImportFrom proto의 행번호만 비교한다. runner의 lines 84-95는 hook 전에 실행되고, __import__·importlib·exec로 proto를 먼저 로드해도 proto_lines에는 나타나지 않는다. audit_guard 자체도 line 220에서 hook을 설치하므로 그 이전 모듈 본문은 보호되지 않는다. 정확한 직전 proto 정적 import 우회는 닫혔지만 'bootstrap부터 armed'라는 더 넓은 주장은 성립하지 않는다.
  Recommendation: 최소 bootstrap launcher에서 runner와 정책 모듈보다 먼저 hook을 설치하고, 설치 시점의 sys.modules에 proto가 없었음을 기록·검증하라. AST 검사는 hook 전 실행 가능한 문장과 동적 로드 호출도 fail-closed로 다뤄야 한다.
- [high] 프로세스 전역 재진입 플래그가 audit hook 전체를 우회시킨다 (tools/spikes/phase0_contract/audit_guard.py:206-217)
  _REENTRANT는 모듈 전역 boolean이다. 한 스레드가 _enforce 안에 있는 동안 다른 스레드의 모든 watched event가 즉시 return한다. 또한 path_violation의 os.fsdecode는 임의 PathLike.__fspath__를 호출할 수 있어 같은 스레드의 중첩 audit도 플래그에 의해 무시된다. 현재 코드가 단일 스레드라는 산문은 구조적 보장이 아니며 프로세스 전역 강제 주장과 충돌한다.
  Recommendation: 재진입 상태를 thread-local로 격리하고, hook 내부에서는 사용자 콜백을 유발할 수 있는 비원시 path 인자를 fail-closed 처리하라. 동시 스레드와 재진입 PathLike가 모두 차단되는 대조군을 추가하라.
- [medium] repo 루트 검증이 .git의 존재만 신뢰한다 (tools/spikes/phase0_contract/proto/boundary.py:476-491)
  locate_violation()은 .git이 파일인지 디렉터리인지 또는 유효한 gitdir인지 확인하지 않고 exists()만 본다. 예상 상대경로를 보존한 사본에 빈 .git 파일 하나를 두면 samefile 검사도 자기 사본을 비교하므로 통과한다. L-LOCATE-FORGE는 '.git 디렉터리'가 필요하다고 적어 실제 위조 비용도 과대 서술한다. 단순 is_dir 요구는 정상 worktree의 .git 파일을 깨므로 충분한 교정도 아니다.
  Recommendation: 디렉터리형 .git은 내부 구조를, 파일형 .git은 gitdir 포인터를 검증하고 실제 repository top-level이 기대 루트와 같은지 확인하라. 빈 파일과 유효한 worktree gitdir을 각각 음성·양성 대조군으로 추가하라.
- [medium] 보호 대상 판정이 inode 별칭을 놓친다 (tools/spikes/phase0_contract/audit_guard.py:159-166)
  path_violation()은 resolve된 경로 구성요소와 basename만 비교한다. 보호 register의 기존 hardlink가 무해한 이름을 가지면 resolve()로 원본 경로가 복원되지 않아 동일 inode를 읽을 수 있다. os.link를 실행 중 차단하는 것은 이미 준비된 별칭을 막지 못하며, 현재 17개 한계 노트에도 이 경계가 없다.
  Recommendation: 보호 파일의 canonical st_dev/st_ino 집합과 open 대상 identity를 대조하거나, 지원하지 않을 경우 정책을 경로명 차단으로 명확히 축소하고 hardlink 대조군과 한계 ID를 추가하라.
- [medium] 런타임 정책 데이터는 여전히 앵커 정의역 밖이다 (tools/spikes/phase0_contract/test_contracts.py:332-356)
  loaded-code 앵커는 함수와 클래스 메서드의 code object만 수집하고, source-bytes 앵커는 디스크만 본다. 값 앵커는 FORBIDDEN_ARTIFACTS와 REQUIRED_METRICS에만 배선돼 있다. 따라서 FIXTURE_CLAUSES, FORBIDDEN_SOURCE_TOKENS, REQUIRED_KEYS, _PROBE_DEPTH 같은 모듈 정책값의 런타임 대입은 어느 앵커에도 결속되지 않는다. config.yaml의 '런타임 대입은 실행 코드와 값 앵커가 본다'는 설명은 실제보다 넓다.
  Recommendation: 판정 우주와 경계를 정의하는 모든 모듈 정책값을 config의 독립 value anchor에 결속하고 항목별 삭제·확장 대조군을 추가하라. 그렇지 않으면 앵커 주장을 두 값에 한정하고 미보호 값들을 한계 목록에 명시하라.

Next steps:
- SELF-2를 실제 producer 기반 양성 대조군으로 재설계하고 anchor drift와 비-probe guard 기록을 독립적으로 exit에 결속한다.
- audit hook을 runner보다 앞선 최소 bootstrap으로 이동하고 동적 import·pre-hook 실행·재진입을 각각 검증한다.
- repo 의미 검증과 inode 별칭 대조군을 추가해 경로·위치 주장의 실제 정의역을 고정한다.
- 17개 한계 목록을 코드상 잔여와 다시 대조하고, 런타임 정책값 및 쓰기 프로브 실패 시 잔존물 위험까지 명시한다.
```

---

# 수용검사 (오케스트레이터 = Claude) — **채택 7 / 기각 0**

기각 가능 사유 3 가지(팬텀 `file:line` · 의도적 silenced · 비협상 규칙 배치) 중
**어느 것도 해당하지 않는다.** 아래 4 건은 직접 실측했다.

| # | severity | `file:line` | 독립 실측 | 처분 |
|---|---|---|---|---|
| 1 | critical | `test_contracts.py:1840-1856` | **확증** | 채택 |
| 2 | high | `test_contracts.py:2116-2136` | **확증** | 채택 |
| 3 | high | `test_contracts.py:1048-1061` | 실재 (렌즈 N-2/N-6 과 일치) | 채택 |
| 4 | high | `audit_guard.py:206-217` | **확증** | 채택 |
| 5 | medium | `boundary.py:476-491` | **직전 라운드에 이미 확증** | 채택 |
| 6 | medium | `audit_guard.py:159-166` | 실재 (렌즈 S-9 와 일치) | 채택 |
| 7 | medium | `test_contracts.py:332-356` | **확증** | 채택 |

## 오케스트레이터 독립 실측

```
#2  failed = [case for case in rep.cases if not case.ok]
    return 0 if not failed else 1
    → blocked_reads / blocked_writes / recorder.attempts 는 **print 만** 된다.
      가드가 위반을 탐지·기록해도 대상이 예외를 잡으면 exit 0.
#1  SELF-2 는 collect_self_checks(...) 를 부르되 digest_drift producer 에 `()` 를 넘기고
    self_check_green(probe, ...) 로 합성 입력만 본다.
#4  _REENTRANT = False (모듈 전역) · global _REENTRANT — 스레드 지역 아님.
#7  tuple_anchor 사용처는 :927 · :932 둘뿐 — FIXTURE_CLAUSES · FORBIDDEN_SOURCE_TOKENS ·
    REQUIRED_KEYS 는 어느 앵커에도 결속되지 않는다.
```

**#2 가 이번 판정의 헤드라인이다.** 이 프로토타입의 존재 이유가 "발견을 종료 코드에 결속한다"인데,
**가드가 관측한 실제 경계 위반이 그 결속 밖에 있다.** F1 이 노트 채널에 대해 지적한 바로 그 결함이
**가드 기록 채널에서 재현**됐다 — 저작자도 렌즈도 4 라운드 동안 보지 못한 표면이다.

## 비협상 규칙 대조 — 위반 0

8 조항 전건 대조. 7 개 finding 모두 **강제를 강화하는 방향**이며 배치되는 권고 없음.
다만 #7 이행 시 **값 앵커는 `config.yaml` 에 두어야 한다**(설정 구동) — 코드에 박으면 그 자체가 위반.

## 포워더 인과 주장에 대한 정정

포워더는 1~3 회차의 절단 잔여물을 `launchctl remove` 조작의 산물로 추정했다.
**그 추정은 1~3 회차에 대해 성립하지 않는다** — `launchctl remove`-직후-제거는 4 회차에
오케스트레이터가 지시한 절차이고, 3 회차 stderr 에는 **콘텐츠 정책 거부 원문이 verbatim 으로
기록**돼 있다. 제거 조작은 4 회차 1 차 시도의 즉사를 설명할 뿐, 1~3 회차의 거부를 설명하지 않는다.
다만 **"뜬 직후 label 제거" 지시가 잘못이었다는 지적은 옳다** — 그 절차는 오케스트레이터 오류이며,
포워더가 래퍼 자체 정리 방식으로 교정한 것이 맞다.

## 관통 패턴 — 14 번째

| 층 | 형태 |
|---|---|
| v1.3.8~v2.1 | 문서 안 선언↔평가 간극 (10 회) |
| v2.2 | 증거 도구로 전이 |
| v2.3 | 증거 도구의 교정에도 같은 간극 |
| v2.5 | 교정의 **잔여 목록**으로 전이 |
| **v2.6** | **가드 기록 채널로 전이** — 위반을 관측·기록하고도 exit 에 결속하지 않았다 (#2) |

v2.6 의 형태가 가장 날카롭다. F1 은 "노트로 빠져나가는 통로"를 막는 작업이었는데,
**그 작업이 만든 새 관측 채널(가드 기록)이 정확히 같은 통로가 됐다.**
막은 옆에 우회로가 남은 것이 아니라 **막는 도구 자체가 새 우회로를 만들었다.**

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립 (15회 연속)
```

**P-0 및 모든 D0 구현 착수 차단 유지.**
