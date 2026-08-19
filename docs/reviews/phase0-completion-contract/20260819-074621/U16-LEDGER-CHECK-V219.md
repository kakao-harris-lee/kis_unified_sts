# U16-LEDGER-CHECK-V219 — v2.19 T-82 ⑱(현행 스키마)·⑳ⓐⓑ(형제 동일 행·선-검사 corner) + 회귀(⑪·⑮·⑯·⑰ⓐⓑⓒ·⑲·자인 잔여) 손 실행 기록 (S-23 전 규칙 실행기 · U-16-c 구조 집합 · U-16-d 전순서 12단)

> **비규범 손 실행** — 실제 소비자(`tools/tos_completion_status.py --check`)는 **D0-A 이후**이며, 계약 v2.19(`d5a8302a`)는 U-16 증거 아티팩트의 **경로·형식을 규정하지 않는다**(§13.6.5·§8 T-82 행 어디에도 없음 — 선행 판과 동일). 이 파일은
> v2.18 재심 verdict 스탬프 `docs/reviews/phase0-completion-contract/20260819-074621/` 의 **sibling** 으로 두며, v2.15 sibling(`…/20260819-002145/U16-LEDGER-CHECK.md`)은 U-15-e **(4d) 불변 규율을 준용**해 편집하지 않는다.
> **S-24 결속: 이 증거는 «최종 동결 `d5a8302a`» 에 결속된다** — 실행 시점 HEAD == `d5a8302a` · 계약 워킹트리 blob `a1d52da7` == `git show d5a8302a:<계약>` blob
> (`git diff --quiet d5a8302a -- <계약>` rc=0 · 워킹트리 sha256 `8eba31fa573c34c8f71bae7a3616cc90765e76f25626c48520281c6f5b114f85`) ·
> `d5a8302a..HEAD` 에 계약 문서 커밋 **0**(에라타 없음) · 하니스 §12.3.4-R 블록 `sed -n '4589,4689p'` sha256
> **`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`** — 동결 blob·워킹트리 **byte-동일**(§5 원문).
> **판정 소비자는 이 파일의 방출값을 신뢰하지 않고 스스로 재실행·재파생한다** — 실행기·픽스처 구성 전문을 그대로 수록하는 이유가 그것이다.
> **서버 쓰기 0 · GitHub 조회 0**(U-16 은 순수 in-repo 판정이다) · 픽스처는 scratchpad 하위 **독립 git 저장소**(`fx82z/*` — 본 저장소 무접촉·worktree 미사용).

- **생성 시각**: 2026-08-19T01:15:17Z (UTC) · 실행 `t82v219_utc=2026-08-19T01:14:10Z` · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트(저작자·심판 아님)
- **실행기 결속**:
  - sha256(`u16-full-exec-v219.py`) = **`5692e75d46962e8170db31be79f2678b6070bb6f3770d0c8720f2617dafa60a5`** (원문 §1)
  - sha256(`u16-order-ctrl-g1first.py`) = **`4e9f0bc42b86d5e9f34d5f216df474c0da5a3b655b6fddeecf6a31f8501a51cd`** (**T-82 ⑳ⓑ 대조군** — `EVAL_ORDER` **한 줄만** 다르다. §2 diff. **판정용 아님**)
  - sha256(`t82v219.sh`) = **`b4553c367f91341a2dba235ec4712909bb6dabc03574ce3dc7884a2486ee9a2b`** (픽스처·드라이버 원문 §3)
  - sha256(`u16-full-exec-v215.py`) = **`a0201149b794de7ae438d05e035246d35598a1173ecd5481e1217e647f38e5d0`** (직전 판 부속 — `U16-LEDGER-CHECK.md` §1 원문에서 그대로 추출·재계산 일치. **⑳ⓐ 판별력 대조용**: 그 실행기가 `U16-LEDGER-CHECK.md:37` 에서 «복수면 사전순 최소»를 자체 선언한 그 코드다)
- **관련 계약**: `U-16-a` `EDGES(r)` · `U-16-a2` 전칭 · **`U-16-b` #2 마감 스키마(`edge_seq` 기재 필드 폐지 → 소비자 표시용 파생)** · **`U-16-c` [v2.19 재작성] `c_APP` «구조 집합» + 카디널리티 처분**(계약 `:6917`) · `U-16-f` · `U-16-g`(g1~g6 — g6 = blob 동일성 `C_R(c)` + ∃ 증인 [F3·H4]) · `U-16-h` · **`U-16-d` [v2.19 신설] 전순서 12단 + 선-검사 1~4 → g-단락 5~11**(계약 `:6994`~`:7027`) · **S-23** · §8 T-82 행(**20종**)
- **S-23 — 이 실행기가 실행·방출한 규칙 목록** (각 run 의 `rules_executed=` 라인 원문과 동일 · 실행기가 계약 소비 규칙 집합과의 차집합을 스스로 계산해 `rules_missing=` 로 방출하고, **비어 있지 않으면 `NO_ROWS_CLEAR` 대신 `PARTIAL_EXECUTION` 을 내도록 잠금**):
  `U-16-a(EDGES)` · `U-16-b(edge_seq 표시용 파생·판정 미소비)` · `U-16-c(c_APP 구조 집합·카디널리티·진 조상)` · `g1` · `g2` · `g3` · `g4` · `g5` · `h` · `g6(C_R blob·∃witness)` · `U-16-a2(∀edge∃row)` · `MALFORMED(orphan/double-cover)` · `U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)` — **13 규칙 전부 실행**(전 run 에서 `rules_missing=∅`).
  v2.15 부속은 11 규칙이었고 `U-16-b`·`U-16-d` 를 **실행기 자체 선언**으로 대체했다 — 그 두 자리가 심판 F4 의 지적이며 이번 판의 델타다.

## 0. 결과 요약 — 실행기 stdout·rc 원문 그대로 (해석 아님)

전역 상태 = **모든 행·모든 간선 상태의 전순서 최소**(계약 `:6996`). 방출 라인에 `발화 전체=[...]` 로 수집 원문을 병기한다. **rc 0 = `NO_ROWS_CLEAR` 만.**

계약 U-16-d 전순서: `1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR`

| 변이 | 픽스처 (DAG 는 §4 실행 기록의 `git log --graph`) | 방출값 (`closable_no_provenance_state=`) | rc | 기대 (§8 T-82 행) | 대조 |
| --- | --- | --- | --- | --- | --- |
| **⑱-1 [현행 스키마] 병렬 반복 이력(양성)** | `H0(r1 absent·reviewer digest)` → 형제 `A1`(승인 `ABSENT->NO`·rationale a) ∥ `A2`(승인 `YES->NO`·rationale b) → `MA` merge(원장 합집합) → `e1`(ABSENT->NO) → back to YES → `e2`(YES->NO). **`edge_seq` 기재 없음** | **`NO_ROWS_CLEAR`** — `edge#1 COVERED by c_APP=9d09dd1` · `edge#2 COVERED by c_APP=22424c7` · `edge_seq 표시용 파생=[1,2] · 판정 미소비` · 두 행 `|c_APP|=1` | **0** | ⑱ **기대 `NO_ROWS_CLEAR` + rc=0** · «폐지 필드를 여전히 소비하는 구현은 영구 차단» | **일치** — g5 구 승인 행 불변도 확인(`A1|`·`A2|` 시점 행 == HEAD 행) |
| **⑱-2 [문언 리터럴 «별개 `row_id`»]** | 같은 반복 이력을 `row_id=r1` ∥ `row_id=r1b` 두 승인 행으로 덮는다 | **`APPROVAL_MALFORMED`** — `row[r1b/YES->NO]` 고아(대응 간선 0) · `edge#2 APPROVAL_MISSING(4)` → 전순서 최소 3 | 1 | ⑱ 문언의 «별개 `row_id`» 를 **리터럴로** 구성하면 | **불일치 → §5 결함 후보 D-1** (문언이 지시한 입력이 계약의 g2·간선 대응과 충돌) |
| **⑳ⓐ 동일 승인 행 형제 독립 도입** | `H0` → `X`(승인 행 A) → `CN`(NO 전이) ∥ `Y`(**byte-동일** 승인 행 A) → `M` merge. **사전순 `X < Y`** 가 되도록 nonce 로 구성(사전순 최소 = **조상** 도입) | **`APPROVAL_MALFORMED`** — `row[r1/YES->NO]: |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['e8f5c99','590067c']` · 두 간선도 각각 3 | 1 | ⑳ⓐ **`APPROVAL_MALFORMED` + rc≠0** | **일치** |
| **⑳ⓐ 판별력 대조** | 같은 픽스처를 **직전 판 부속**(`a0201149…`, «복수면 사전순 최소»)으로 | **`NO_ROWS_CLEAR` / rc=0** — `ledger_rows=[('r1','YES->NO','590067c')]`(=조상 도입 `X` 를 골랐다) · 두 간선 COVERED | 0 | ⑳ⓐ «사전순 최소로 임의 보충하는 구현은 조상인 도입을 골라 통과시켜 실패한다» | **일치 — F5 «회피»의 실증** |
| **⑳ⓑ 선-검사 순서 corner** | ⑳ⓐ 픽스처의 **`git clone --depth 1` 얕은 클론**: `shallow_boundary=['2ce323a']` · `rev-list HEAD`=1 · `parents(HEAD)`=∅(경계) ⇒ **`|c_APP|=0`(경계커밋 1) ∧ g1 위배**(원장 `YES->NO` vs 파생 간선 `ABSENT->NO`) 동시 성립 | **`PROVENANCE_UNVERIFIABLE`** — `row[r1/YES->NO]: |c_APP|=0` (전순서 2) · `edge#1 APPROVAL_MISSING(4)` · `발화 전체=['PROVENANCE_UNVERIFIABLE','APPROVAL_MISSING']` | 1 | ⑳ⓑ **`PROVENANCE_UNVERIFIABLE`(전순서 2) + rc≠0** | **일치** |
| **⑳ⓑ 판별력 대조** | 같은 얕은 클론을 **«g1·g4 먼저» 문자 구현**(`4e9f0bc4…`, `EVAL_ORDER` 한 줄 차이)으로 | **`APPROVAL_MALFORMED`** (전순서 3) — `row … 고아 · edge#1 g1 YES->NO≠ABSENT->NO` | 1 | ⑳ⓑ ««g1·g4 먼저»로 문자 구현하면 `APPROVAL_MALFORMED`(3)를 내 **실패**한다» | **일치 — 발산 실증(2 vs 3)** |
| 회귀 **⑯** | `ABSENT->NO->YES->NO` 선형 · 간선별 별도 승인 `A1`·`A2` | **`NO_ROWS_CLEAR`** — edge#1 by `A1` · edge#2 by `A2` | 0 | green(어떤 간선도 무시되지 않음) | **일치** |
| 회귀 **⑰ⓐ** 기존-경로 `B∥A` | `H0`(무관 리뷰) → `B`(digest 삽입) ∥ `A`(aah=B) → `M0` → `M`(NO) | **`APPROVAL_ORDER_INVALID`** — `g6 C_R={3e457f1} 에 c_APP 진 조상 증인 없음` | 1 | `C_R={B}` · `B ⋠ A` → red | **일치** |
| 회귀 **⑰ⓑ** 머지 해소 digest 도입 | `H0` → `B`(digest 없는 편집) ∥ `A`(aah=B) → `M`(해소에서 digest 도입 + NO) | **`APPROVAL_UNBOUND`** (h: digest ∉ blob(aah=B)) · g6 단독 뷰(target=blob(M)) `C_R={…}` → `APPROVAL_ORDER_INVALID` 병기 | 1 | **[E2 v2.15 에라타] `APPROVAL_UNBOUND`** (h 가 g6 보다 먼저) | **일치** |
| 회귀 **⑰ⓒ** 양성 | `B1`·`B2` 독립 동일 blob · `A ⊐ B1` | **`NO_ROWS_CLEAR`** | 0 | green(∃ 양화자) | **일치** |
| 회귀 **⑲** digest 선배치 | `H0`(digest 만 담은 빈 운반자) → `B`(실제 내용·digest 유지) ∥ `A`(aah=B) → `M` | **`APPROVAL_ORDER_INVALID`** · v2.14 토큰 기반 `C_R` 대조는 `witness=YES(green — 선배치 우회 통과)` | 1 | blob 정의에서 red | **일치 — F3 재정의 판별력 유지** |
| 회귀 **⑮** 신규 아티팩트 `R∥A` | `H0`(리뷰 경로 없음) → `R` ∥ `A`(aah=R) → `M0` → `M` | **`APPROVAL_ORDER_INVALID`** | 1 | red | **일치** |
| 회귀 **⑪** transition 불일치 | 원장 `YES->NO` · 실제 파생 간선 `ABSENT->NO` | **`APPROVAL_MALFORMED`** — 고아(대응 간선 0) · edge `APPROVAL_MISSING`(4) → 최소 3 | 1 | MALFORMED 차단 | **일치** |
| 자인 잔여 | 단일 승인 행이 두 간선의 조상 | **`NO_ROWS_CLEAR`** — edge#1·#2 둘 다 같은 `c_APP` 로 COVERED | 0 | 계약 «닫지 못하는 것» 정직 표기 그대로 | **일치(계약 정직 표기와 정합)** |

---

## 1. 전 규칙 실행기 `u16-full-exec-v219.py` — 원문 + 독해 선언 (sha256 `5692e75d46962e8170db31be79f2678b6070bb6f3770d0c8720f2617dafa60a5`)

독해 선언(계약이 리터럴로 고정하지 않은 자리 · **v2.15 부속 대비 델타 중심** — §2-2 에 `diff` 전문):
- **판정 우주** = HEAD 레지스터에서 `closable=NO` 인 모든 행 · `EDGES(r)` = `git rev-list HEAD` 전수에서 `closable(c,r)==NO ∧ closable(p,r)!=NO` 인 `(p→c)`(루트·부모에 행 부재 = `ABSENT->NO`).
- **[F5] `c_APP(a)` = 구조 «집합»**: `{ x ⊑ HEAD : a ∈ rows(x:LEDGER) ∧ ∀p∈parents(x): a ∉ rows(p:LEDGER) }`. **«사전순 최소» 같은 계약 밖 보충을 하지 않는다.** 카디널리티 처분은 `U-16-c` 그대로: `0 → PROVENANCE_UNVERIFIABLE`(2) · `>1 → APPROVAL_MALFORMED`(3) · `1 → 그 «유일 원소»를 U-16-c 조상성·g5·g6 세 소비처가 쓴다`.
  **얕은 클론 경계**(`.git/shallow`)의 커밋은 **부모 집합 «미상»** 이므로 도입 지점으로 **확정하지 않는다** — git 이 경계 커밋을 «부모 없는 커밋»으로 보고해 ∀-부모 항이 공허참이 되는 fail-open 을 막는다(§5 D-2).
- **[F4] 상태 우선순위 = 계약 `U-16-d` 전순서 12단**(실행기가 순서를 «선언»하지 않는다). 평가 절차는 계약 정정 블록 그대로 **① 선-검사(1~4) → ② g-단락(5~11)** 이며, 그 순서는 모듈 상수 `EVAL_ORDER` **한 줄**로 표현된다(⑳ⓑ 대조군은 그 한 줄만 다르다).
- **`edge_seq`**: `(author date, commit id)` 사전식 **표시용 파생**만 방출하고 **판정 입력에 쓰지 않는다**(`U-16-b` #2 마감 스키마 · 방출 라인에 «판정 미소비» 명기).
- **덮음** ⇔ `g1` ∧ `U-16-c`(`c_APP` 유일 원소가 `c` 의 진 조상 · 동일 커밋 = `APPROVAL_SAME_COMMIT`) ∧ `g2` ∧ `g3` ∧ `g5` ∧ `h` ∧ `g6`, 그리고 행 단위 `g4`·카디널리티·고아 판정. **`g6` `C_R(c)`** = `{ x ⊑ c : blob(x:ref) == blob(aah:ref) ∧ ∀p: blob(p:ref) ≠ 그 blob }`(부모 경로 부재는 `≠` — [H4]) · `C_R=∅` → `PROVENANCE_UNVERIFIABLE` · 요구 `∃x∈C_R: x ⊰ c_APP`.
- **고아** = 구조적 대응(같은 `row_id` ∧ `g1` 일치 간선)이 **하나도 없는** 행. 특정 규칙에서 탈락한 행은 **그 규칙 상태로 귀속**되며 고아가 아니다(§5 D-5).
- **전역 상태** = 모든 «행·간선» 기여의 **전순서 최소**(계약 `:6996`). 방출 라인이 `발화 전체=[...]` 로 수집 원문을 병기한다.
- **S-23 잠금**: `rules_executed=`·`rules_missing=` 방출 후, 차집합이 비지 않는데 `NO_ROWS_CLEAR` 를 내려 하면 **`PARTIAL_EXECUTION`/1** 로 바꾼다. rc 0 = `NO_ROWS_CLEAR` 만 · 예외 경로는 `PROVENANCE_UNVERIFIABLE`/1 로 폐쇄.

```python
#!/usr/bin/env python3
"""U-16 «전 규칙» 손 실행기 — v2.19 (계약 d5a8302a §13.6.5 U-16-a/a2/b/c/d/f/g(g1~g6)/h).

v2.15 부속(`U16-LEDGER-CHECK.md` §1 · sha256 a0201149…) 에서 파생하며 델타는 **심판 F4·F5 처분 두 가지**뿐이다:
  [F5] `c_APP(a)` 를 «구조 집합»으로 파생한다 — v2.15 부속의 «복수면 사전순 최소»(계약 밖 자체 보충)를 폐기하고
       `U-16-c` 카디널리티 처분을 그대로 소비: |c_APP|=0 → PROVENANCE_UNVERIFIABLE · |c_APP|>1 → APPROVAL_MALFORMED ·
       |c_APP|=1 → 그 «유일 원소»를 세 소비처(U-16-c 조상성 · g5 · g6)가 쓴다.
  [F4] 상태 우선순위를 «실행기 자체 선언»에서 **계약 `U-16-d` 전순서 12단**으로 교체하고, 평가 절차를
       **① 선-검사(1~4) → ② g-단락(5~11)** 으로 둔다(계약 U-16-d 정정 블록의 문자 구현).
       `edge_seq` 는 «표시용 파생»으로만 방출하고 판정 입력에 쓰지 않는다(U-16-b #2 마감 스키마).

S-23: 실행한 규칙 목록을 방출하고, 계약 소비 규칙 집합과 차집합이 비지 않으면 green(NO_ROWS_CLEAR) 대신
      PARTIAL_EXECUTION 을 방출한다.

픽스처 형식: register.csv = 'id,closable,owner_track' (헤더 있음) ·
             LEDGER.md 행 = 'row_id | transition | row_content_digest | approved_at_head | reviewer_ref | rationale_ref'
row_content_digest = U-16-f: 레지스터 행 전 열을 LC_ALL=C 열이름 정렬 '<열>=<값>' NUL 결합 sha256.

방출: closable_no_provenance_state=<값> · rules_executed=<목록> · rc 0 = NO_ROWS_CLEAR 만.
"""
import hashlib, subprocess, sys

# ── 계약 U-16-d 전순서 (유일 소스 — 실행기가 순서를 «선언»하지 않는다)
TOTAL_ORDER = ["CONSUMER_ABSENT", "PROVENANCE_UNVERIFIABLE", "APPROVAL_MALFORMED", "APPROVAL_MISSING",
               "APPROVAL_SAME_COMMIT", "APPROVAL_AFTER", "APPROVAL_CONTENT_DRIFT", "APPROVAL_HEAD_INVALID",
               "APPROVAL_ROW_MUTATED", "APPROVAL_UNBOUND", "APPROVAL_ORDER_INVALID", "NO_ROWS_CLEAR"]
TO = {s: i + 1 for i, s in enumerate(TOTAL_ORDER)}

# ── [v2.19 U-16-d 정정] ① 선-검사(1~4) 를 g-규칙 «앞»에 둔다.  대조군(«g1·g4 먼저» 문자 구현)은 이 한 줄만 다르다.
EVAL_ORDER = "precheck-first"          # 대조군 파일: "g1-first"

RULES_CONTRACT = ["U-16-a(EDGES)", "U-16-a2(∀edge∃row)", "U-16-b(edge_seq 표시용 파생·판정 미소비)",
                  "U-16-c(c_APP 구조 집합·카디널리티·진 조상)", "g1", "g2", "g3", "g4", "g5",
                  "g6(C_R blob·∃witness)", "h", "MALFORMED(orphan/double-cover)",
                  "U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)"]
REG, LED = "register.csv", "LEDGER.md"
R = None


def g(*a):
    return subprocess.run(["git", "-C", R, *a], capture_output=True, text=True).stdout.strip()


def ok(*a):
    return subprocess.run(["git", "-C", R, *a], capture_output=True).returncode == 0


def have(commit):
    """커밋 «객체»가 실재하는가 (얕은 클론 경계 판별 — 경로 부재와 구별한다)."""
    return ok("cat-file", "-e", commit + "^{commit}")


def shallow_boundary():
    """얕은 클론 «경계» 커밋 집합(.git/shallow).  이들의 부모 집합은 «부재»가 아니라 «미상»이다 —
    git 은 경계 커밋을 부모 없는 커밋처럼 보고하므로(`%P` 공백), 구조 정의의 ∀-부모 항이
    «공허참»이 되어 임의 커밋이 도입 지점으로 확정된다(fail-open).  그래서 경계를 분리 관측한다."""
    import os
    d = g("rev-parse", "--git-dir")
    p = d if os.path.isabs(d) else os.path.join(R, d)
    try:
        return set(open(os.path.join(p, "shallow")).read().split())
    except Exception:
        return set()


def show(c, p):
    r = subprocess.run(["git", "-C", R, "show", f"{c}:{p}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def blob(c, p):
    return g("rev-parse", "--quiet", "--verify", f"{c}:{p}") or "ABSENT"


def parents(c):
    return g("log", "--format=%P", "-1", c).split()


def strict_anc(a, b):
    return a != b and ok("merge-base", "--is-ancestor", a, b)


def reg_rows(c):
    t = show(c, REG)
    out = {}
    if t is None:
        return out
    lines = [l for l in t.splitlines() if l.strip()]
    if not lines:
        return out
    hdr = lines[0].split(",")
    for l in lines[1:]:
        f = l.split(",")
        out[f[0]] = dict(zip(hdr, f))
    return out


def canon_digest(row):
    return hashlib.sha256(b"\0".join(f"{k}={row[k]}".encode() for k in sorted(row))).hexdigest()


def led_raw(c):
    """커밋 c 시점 원장 blob 의 «정규형» 행 집합 (U-16-c rows(y:LEDGER)) — 경로 부재 = 공집합([H4] 동형)."""
    t = show(c, LED)
    if t is None:
        return set()
    return set(l.strip() for l in t.splitlines() if l.strip() and not l.startswith("#"))


def led_rows(c):
    t = show(c, LED)
    out = []
    if t is None:
        return out
    for l in t.splitlines():
        if not l.strip() or l.startswith("#"):
            continue
        f = [x.strip() for x in l.split("|")]
        if len(f) >= 6:
            out.append(dict(row_id=f[0], transition=f[1], digest=f[2], aah=f[3],
                            reviewer_ref=f[4], rationale_ref=f[5], raw=l.strip()))
    return out


def c_app_set(raw):
    """U-16-c 구조 집합:  c_APP(a) = { x ⊑ HEAD : a ∈ rows(x:LEDGER) ∧ ∀p∈parents(x): a ∉ rows(p:LEDGER) }
    부모 «커밋 객체»가 없으면(얕은 클론 경계) 둘째 항을 평가할 수 없으므로 그 x 를 도입 지점으로 «확정하지 않는다»
    — 부재를 «참»으로 접으면 얕은 클론이 임의 커밋을 도입 지점으로 만들어낸다(fail-open)."""
    cands, boundary = [], []
    BND = shallow_boundary()
    for x in g("rev-list", "HEAD").splitlines():
        if raw not in led_raw(x):
            continue
        if x in BND:                      # 얕은 클론 경계 — 부모 집합 «미상» ⇒ 도입 지점으로 확정하지 않는다
            boundary.append(x)
            continue
        ps = parents(x)
        if any(not have(p) for p in ps):
            boundary.append(x)
            continue
        if all(raw not in led_raw(p) for p in ps):
            cands.append(x)
    return cands, boundary


def c_r_set(c, ref, aah):
    """g6 구조 정의:  C_R(c) = { x ⊑ c : blob(x:ref) == blob(aah:ref) ∧ ∀p∈parents(x): blob(p:ref) ≠ 그 blob }
    부모 경로 부재는 ≠ 로 읽는다([H4])."""
    tgt = blob(aah, ref)
    if tgt == "ABSENT":
        return []
    return [x for x in g("rev-list", c).splitlines()
            if blob(x, ref) == tgt and all(blob(p, ref) != tgt for p in parents(x))]


def emit(state, reason, executed, extra=()):
    for line in extra:
        print(line)
    print("rules_executed=" + ";".join(executed))
    missing = [r for r in RULES_CONTRACT if r not in executed]
    print("rules_missing=" + (";".join(missing) if missing else "∅"))
    if missing and state == "NO_ROWS_CLEAR":
        print("closable_no_provenance_state=PARTIAL_EXECUTION")
        print(f"reason=S-23: 미실행 규칙 {missing} — green 방출 금지")
        sys.exit(1)
    print(f"closable_no_provenance_state={state}")
    print(f"reason={reason}")
    sys.exit(0 if state == "NO_ROWS_CLEAR" else 1)


def main():
    global R
    R = sys.argv[1]
    executed = []
    contributions = []          # (scope, state, why)

    def add(scope, state, why):
        contributions.append((scope, state, why))
        print(f"  · {scope}: {state}({TO[state]}) — {why}")

    if not ok("rev-parse", "--is-inside-work-tree"):
        emit("PROVENANCE_UNVERIFIABLE", "git 작업트리 아님", executed)
    HEAD = g("rev-parse", "HEAD")
    SHALLOW = (g("rev-parse", "--is-shallow-repository") == "true")
    print(f"HEAD={HEAD[:7]} shallow={SHALLOW} shallow_boundary={[x[:7] for x in sorted(shallow_boundary())]} EVAL_ORDER={EVAL_ORDER}")

    # ── 소비자 부재 (전순서 1)
    consumer_absent = (show(HEAD, REG) is None) or (show(HEAD, LED) is None)

    cur = reg_rows(HEAD)
    no_rows = [rid for rid, r in cur.items() if r.get("closable") == "NO"]

    # ── U-16-a: EDGES(r)  (→NO 간선 전부 · 루트/부모 부재는 ABSENT->NO)
    executed.append("U-16-a(EDGES)")
    edges = {}
    for rid in no_rows:
        E = []
        for c in g("rev-list", "HEAD").splitlines():
            if reg_rows(c).get(rid, {}).get("closable") != "NO":
                continue
            ps = parents(c) or [None]
            for p in ps:
                pv = "ABSENT" if p is None or rid not in reg_rows(p) else reg_rows(p)[rid]["closable"]
                if pv != "NO":
                    E.append((p, c, "ABSENT->NO" if pv == "ABSENT" else "YES->NO"))
        E.sort(key=lambda e: (g("log", "--format=%ad", "--date=iso-strict", "-1", e[1]), e[1]))
        edges[rid] = E
    # ── U-16-b: edge_seq 는 «표시용 파생»만 — 판정 입력 아님
    executed.append("U-16-b(edge_seq 표시용 파생·판정 미소비)")
    print(f"NO_rows={no_rows}")
    for rid, E in edges.items():
        print(f"EDGES({rid})={[((p or 'ROOT')[:7], c[:7], t) for p, c, t in E]}  "
              f"(edge_seq 표시용 파생={list(range(1, len(E) + 1))} · 판정 미소비)")

    L = led_rows(HEAD)
    executed.append("U-16-c(c_APP 구조 집합·카디널리티·진 조상)")
    for a in L:
        a["capp"], a["capp_boundary"] = c_app_set(a["raw"])
    print("ledger_rows=" + str([(a["row_id"], a["transition"],
                                 "|c_APP|=%d%s" % (len(a["capp"]),
                                                   "" if not a["capp_boundary"] else "(+경계 %d)" % len(a["capp_boundary"])),
                                 [x[:7] for x in a["capp"]]) for a in L]))

    executed += ["g1", "g2", "g3", "g4", "g5", "h", "g6(C_R blob·∃witness)",
                 "U-16-a2(∀edge∃row)", "MALFORMED(orphan/double-cover)",
                 "U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)"]

    # ── 규칙 사실 수집 (short-circuit 없이 전부 측정한 뒤 순서를 적용한다)
    def g4_bad(a):
        return show(HEAD, a["rationale_ref"]) is None

    def g2_bad(a):
        return a["row_id"] not in cur or canon_digest(cur[a["row_id"]]) != a["digest"]

    def g3_bad(a, c):
        return (not have(a["aah"])) or (not ok("merge-base", "--is-ancestor", a["aah"], c)) \
            or show(a["aah"], a["reviewer_ref"]) is None

    def g5_bad(a, capp):
        return a["raw"] not in led_raw(capp)

    def h_bad(a):
        t = show(a["aah"], a["reviewer_ref"])
        return t is None or a["digest"] not in t

    print("\n[사실 수집] 규칙별 측정값 (순서 적용 «전»)")
    for a in L:
        a["_g4"] = g4_bad(a)
        a["_g2"] = g2_bad(a)
        a["_matching_edges"] = [(rid, e) for rid, E in edges.items() for e in E
                                if rid == a["row_id"] and e[2] == a["transition"]]
        a["_rowid_edges"] = [(rid, e) for rid, E in edges.items() for e in E if rid == a["row_id"]]
        print(f"  row {a['row_id']}/{a['transition']} raw#{L.index(a)}: |c_APP|={len(a['capp'])}"
              f"{'' if not a['capp_boundary'] else ' 경계커밋=' + str([x[:7] for x in a['capp_boundary']])}"
              f" g4_bad={a['_g4']} g2_bad={a['_g2']} 대응간선={len(a['_matching_edges'])} row_id간선={len(a['_rowid_edges'])}")

    print("\n[상태 귀속] 계약 U-16-d 순서 적용")
    if consumer_absent:
        add("global", "CONSUMER_ABSENT", "레지스터·원장 부재")
    # 얕은 클론은 «전역 단축»으로 처리하지 않는다 — 경계 커밋을 도입 지점으로 «확정하지 않음»으로써
    # `|c_APP|=0` 이라는 구조 사실로 드러나고, 그 값이 선-검사 2 에서 소비된다(계약 U-16-d ①).
    # 그래야 «순서» 대조군(g1-first)이 전역 단축에 가려지지 않고 순서만으로 갈린다.

    # ── 행 단위 구조 상태
    def row_state(a):
        pre = []
        if len(a["capp"]) == 0:
            pre.append(("PROVENANCE_UNVERIFIABLE", "|c_APP|=0 (도입 지점 파생 불가)"))
        if len(a["capp"]) > 1:
            pre.append(("APPROVAL_MALFORMED", "|c_APP|=%d>1 (동일 승인 행 병렬 독립 도입) %s"
                        % (len(a["capp"]), [x[:7] for x in a["capp"]])))
        g14 = []
        if a["_g4"]:
            g14.append(("APPROVAL_MALFORMED", "g4 rationale_ref 미해석"))
        if not a["_matching_edges"]:
            g14.append(("APPROVAL_MALFORMED",
                        "고아 — 대응 간선 0 (row_id 간선 %d · g1 transition 전건 불일치)" % len(a["_rowid_edges"])))
        seq = (pre + g14) if EVAL_ORDER == "precheck-first" else (g14 + pre)
        return seq[0] if seq else None

    for a in L:
        st = row_state(a)
        if st:
            add(f"row[{a['row_id']}/{a['transition']}]", st[0], st[1])

    # ── 간선 단위
    def cand_state(a, p, c, kind):
        """한 후보 행 a 가 간선 (p→c) 에 대해 도달하는 상태 (없으면 None = 덮음)."""
        capp1 = a["capp"][0] if len(a["capp"]) == 1 else None
        CR = c_r_set(c, a["reviewer_ref"], a["aah"]) if capp1 else []
        pre = []
        if len(a["capp"]) == 0:
            pre.append(("PROVENANCE_UNVERIFIABLE", "|c_APP|=0"))
        elif capp1 and not CR:
            pre.append(("PROVENANCE_UNVERIFIABLE", "g6 C_R=∅"))
        if len(a["capp"]) > 1:
            pre.append(("APPROVAL_MALFORMED", "|c_APP|>1"))
        if a["_g4"]:
            pre.append(("APPROVAL_MALFORMED", "g4"))
        g1v = [("APPROVAL_MALFORMED", f"g1 {a['transition']}≠{kind}")] if a["transition"] != kind else []
        head = (pre + g1v) if EVAL_ORDER == "precheck-first" else (g1v + pre)
        if head:
            return head[0]
        if capp1 is None:
            return ("PROVENANCE_UNVERIFIABLE", "|c_APP|≠1 — g-단락 진입 불가")
        # ② g-단락 (5~11) — |c_APP|=1 의 «유일 원소»만 쓴다
        if capp1 == c:
            return ("APPROVAL_SAME_COMMIT", f"U-16-c c_APP={capp1[:7]} == 간선 커밋")
        if not strict_anc(capp1, c):
            return ("APPROVAL_AFTER", f"U-16-c c_APP={capp1[:7]} 가 {c[:7]} 의 진 조상 아님")
        if a["_g2"]:
            return ("APPROVAL_CONTENT_DRIFT", "g2 재계산 digest ≠ 원장 보유값")
        if g3_bad(a, c):
            return ("APPROVAL_HEAD_INVALID", "g3 approved_at_head 비조상·그 시점 blob 소비 불가")
        if g5_bad(a, capp1):
            return ("APPROVAL_ROW_MUTATED", "g5 c_APP 시점 행 ≠ 현행 행")
        if h_bad(a):
            return ("APPROVAL_UNBOUND", "h digest ∉ blob(approved_at_head:reviewer_ref)")
        if not any(strict_anc(x, capp1) for x in CR):
            return ("APPROVAL_ORDER_INVALID",
                    "g6 C_R={%s} 에 c_APP 진 조상 증인 없음" % ",".join(x[:7] for x in CR))
        return None

    for rid, E in edges.items():
        for i, (p, c, kind) in enumerate(E, 1):
            cands = [a for a in L if a["row_id"] == rid]
            corr = [a for a in cands if a["transition"] == kind] if EVAL_ORDER == "precheck-first" else cands
            covers, fails = [], []
            for a in corr:
                st = cand_state(a, p, c, kind)
                (covers if st is None else fails).append((a, st))
            tag = f"edge#{i}[{rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}]"
            crs = {tuple(c_r_set(c, a["reviewer_ref"], a["aah"])) for a in corr if len(a["capp"]) == 1}
            crtxt = " C_R=" + "|".join("{" + ",".join(x[:7] for x in cr) + "}" for cr in crs) if crs else ""
            if len(covers) == 1:
                print(f"  · {tag}: COVERED by c_APP={covers[0][0]['capp'][0][:7]}{crtxt}")
            elif len(covers) > 1:
                add(tag, "APPROVAL_MALFORMED",
                    "이중 덮음 %s" % [x[0]["capp"][0][:7] for x in covers])
            elif not fails:
                add(tag, "APPROVAL_MISSING", f"덮는 행 부재 (후보 {len(cands)} · 대응 {len(corr)}){crtxt}")
            else:
                st = min((f[1] for f in fails), key=lambda s: TO[s[0]])
                add(tag, st[0], f"{st[1]} (후보 {len(cands)} · 대응 {len(corr)}){crtxt}")

    if not no_rows:
        emit("NO_ROWS_CLEAR", "closable=NO 행 없음(판정 우주 ∅ — 공허 통과가 아니라 대상 없음)", executed)
    if contributions:
        best = min(contributions, key=lambda t: TO[t[1]])
        allst = sorted({c[1] for c in contributions}, key=lambda s: TO[s])
        emit(best[1], f"전순서 최소 = {best[1]}({TO[best[1]]}) @ {best[0]} — {best[2]} · 발화 전체={allst}", executed)
    emit("NO_ROWS_CLEAR", "모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0", executed)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print("rules_executed=\nrules_missing=(예외)\nclosable_no_provenance_state=PROVENANCE_UNVERIFIABLE")
        print(f"reason=판정 미산출: {e!r}")
        sys.exit(1)
```

## 2. 대조군 실행기 `u16-order-ctrl-g1first.py` — 생성 규칙 + diff (sha256 `4e9f0bc42b86d5e9f34d5f216df474c0da5a3b655b6fddeecf6a31f8501a51cd`)

**판정용이 아니다.** 계약 `U-16-d` 정정 «전» 초안 순서(«g1·g4 먼저» 문자 구현)를 재현한다 — `EVAL_ORDER` **한 줄만** 다르므로 «델타 = 순서»임이 파일 수준에서 증명된다. 생성 명령(재현):

```bash
sed 's/^EVAL_ORDER = "precheck-first".*$/EVAL_ORDER = "g1-first"                 # [대조군] …/' \
    u16-full-exec-v219.py > u16-order-ctrl-g1first.py
```

```diff
30c30
< EVAL_ORDER = "precheck-first"          # 대조군 파일: "g1-first"
---
> EVAL_ORDER = "g1-first"                 # [대조군] «g1·g4 먼저» 문자 구현 (v2.19 정정 «전» 초안 순서) — 판정용 아님
```

### 2-2. `diff u16-full-exec-v215.py u16-full-exec-v219.py` (직전 판 부속 대비 델타 전문)

```diff
2,4c2,16
< """U-16 «전 규칙» 손 실행기 — v2.15 (계약 11a56d3e §13.6.5 U-16-a/a2/c/d/f/g(g1~g6)/h · #2 마감 스키마: edge_seq 없음).
< S-23: 실행한 규칙 목록을 방출하고, 계약 소비 규칙 집합과 차집합이 비지 않으면 green 을 방출하지 않는다.
< 픽스처 형식: register.csv = 'id,closable,owner_track' (헤더 있음) · LEDGER.md 행 = 'row_id | transition | row_content_digest | approved_at_head | reviewer_ref | rationale_ref'
---
> """U-16 «전 규칙» 손 실행기 — v2.19 (계약 d5a8302a §13.6.5 U-16-a/a2/b/c/d/f/g(g1~g6)/h).
> 
> v2.15 부속(`U16-LEDGER-CHECK.md` §1 · sha256 a0201149…) 에서 파생하며 델타는 **심판 F4·F5 처분 두 가지**뿐이다:
>   [F5] `c_APP(a)` 를 «구조 집합»으로 파생한다 — v2.15 부속의 «복수면 사전순 최소»(계약 밖 자체 보충)를 폐기하고
>        `U-16-c` 카디널리티 처분을 그대로 소비: |c_APP|=0 → PROVENANCE_UNVERIFIABLE · |c_APP|>1 → APPROVAL_MALFORMED ·
>        |c_APP|=1 → 그 «유일 원소»를 세 소비처(U-16-c 조상성 · g5 · g6)가 쓴다.
>   [F4] 상태 우선순위를 «실행기 자체 선언»에서 **계약 `U-16-d` 전순서 12단**으로 교체하고, 평가 절차를
>        **① 선-검사(1~4) → ② g-단락(5~11)** 으로 둔다(계약 U-16-d 정정 블록의 문자 구현).
>        `edge_seq` 는 «표시용 파생»으로만 방출하고 판정 입력에 쓰지 않는다(U-16-b #2 마감 스키마).
> 
> S-23: 실행한 규칙 목록을 방출하고, 계약 소비 규칙 집합과 차집합이 비지 않으면 green(NO_ROWS_CLEAR) 대신
>       PARTIAL_EXECUTION 을 방출한다.
> 
> 픽스처 형식: register.csv = 'id,closable,owner_track' (헤더 있음) ·
>              LEDGER.md 행 = 'row_id | transition | row_content_digest | approved_at_head | reviewer_ref | rationale_ref'
6,8c18
< 간선: U-16-a  EDGES(r) = { (p→c) : closable(c,r)==NO ∧ closable(p,r)!=NO } (루트는 p=None → ABSENT->NO). 판정 우주 = HEAD 에서 closable=NO 인 모든 행.
< 덮음(a 가 (p→c) 를 덮는다) ⇔ g1 ∧ U-16-c(c_APP(a) ⊰ c, 동일 커밋 거부) ∧ g2 ∧ g3 ∧ g4 ∧ g5 ∧ h ∧ g6.   판정 = U-16-a2 ∀간선 ∃덮는 행 · 이중 덮음/구조적 고아 행(row_id 무간선·g1 전부 불일치) = MALFORMED · 규칙 탈락 행은 그 규칙 상태로 귀속.
< 상태 우선순위(실행기 선언 — 계약 U-16-d 는 전순서를 두지 않으므로 «전제 붕괴 순서»로 정함): PROVENANCE_UNVERIFIABLE > APPROVAL_MALFORMED > APPROVAL_MISSING > SAME_COMMIT > AFTER > CONTENT_DRIFT > HEAD_INVALID > ROW_MUTATED > UNBOUND > ORDER_INVALID > NO_ROWS_CLEAR
---
> 
12c22,35
< RULES_CONTRACT = ["U-16-a(EDGES)", "U-16-a2(∀edge∃row)", "U-16-c(c_APP⊰c)", "g1", "g2", "g3", "g4", "g5", "g6(C_R blob·∃witness)", "h", "MALFORMED(orphan/double-cover)"]
---
> 
> # ── 계약 U-16-d 전순서 (유일 소스 — 실행기가 순서를 «선언»하지 않는다)
> TOTAL_ORDER = ["CONSUMER_ABSENT", "PROVENANCE_UNVERIFIABLE", "APPROVAL_MALFORMED", "APPROVAL_MISSING",
>                "APPROVAL_SAME_COMMIT", "APPROVAL_AFTER", "APPROVAL_CONTENT_DRIFT", "APPROVAL_HEAD_INVALID",
>                "APPROVAL_ROW_MUTATED", "APPROVAL_UNBOUND", "APPROVAL_ORDER_INVALID", "NO_ROWS_CLEAR"]
> TO = {s: i + 1 for i, s in enumerate(TOTAL_ORDER)}
> 
> # ── [v2.19 U-16-d 정정] ① 선-검사(1~4) 를 g-규칙 «앞»에 둔다.  대조군(«g1·g4 먼저» 문자 구현)은 이 한 줄만 다르다.
> EVAL_ORDER = "precheck-first"          # 대조군 파일: "g1-first"
> 
> RULES_CONTRACT = ["U-16-a(EDGES)", "U-16-a2(∀edge∃row)", "U-16-b(edge_seq 표시용 파생·판정 미소비)",
>                   "U-16-c(c_APP 구조 집합·카디널리티·진 조상)", "g1", "g2", "g3", "g4", "g5",
>                   "g6(C_R blob·∃witness)", "h", "MALFORMED(orphan/double-cover)",
>                   "U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)"]
14d36
< PRIO = ["PROVENANCE_UNVERIFIABLE","APPROVAL_MALFORMED","APPROVAL_MISSING","APPROVAL_SAME_COMMIT","APPROVAL_AFTER","APPROVAL_CONTENT_DRIFT","APPROVAL_HEAD_INVALID","APPROVAL_ROW_MUTATED","APPROVAL_UNBOUND","APPROVAL_ORDER_INVALID","NO_ROWS_CLEAR"]
16,22c38,82
< def g(*a): return subprocess.run(["git","-C",R,*a],capture_output=True,text=True).stdout.strip()
< def ok(*a): return subprocess.run(["git","-C",R,*a],capture_output=True).returncode==0
< def show(c,p):
<     r=subprocess.run(["git","-C",R,"show",f"{c}:{p}"],capture_output=True,text=True); return r.stdout if r.returncode==0 else None
< def blob(c,p): return g("rev-parse","--quiet","--verify",f"{c}:{p}") or "ABSENT"
< def parents(c): return g("log","--format=%P","-1",c).split()
< def strict_anc(a,b): return a!=b and ok("merge-base","--is-ancestor",a,b)
---
> 
> 
> def g(*a):
>     return subprocess.run(["git", "-C", R, *a], capture_output=True, text=True).stdout.strip()
> 
> 
> def ok(*a):
>     return subprocess.run(["git", "-C", R, *a], capture_output=True).returncode == 0
> 
> 
> def have(commit):
>     """커밋 «객체»가 실재하는가 (얕은 클론 경계 판별 — 경로 부재와 구별한다)."""
>     return ok("cat-file", "-e", commit + "^{commit}")
> 
> 
> def shallow_boundary():
>     """얕은 클론 «경계» 커밋 집합(.git/shallow).  이들의 부모 집합은 «부재»가 아니라 «미상»이다 —
>     git 은 경계 커밋을 부모 없는 커밋처럼 보고하므로(`%P` 공백), 구조 정의의 ∀-부모 항이
>     «공허참»이 되어 임의 커밋이 도입 지점으로 확정된다(fail-open).  그래서 경계를 분리 관측한다."""
>     import os
>     d = g("rev-parse", "--git-dir")
>     p = d if os.path.isabs(d) else os.path.join(R, d)
>     try:
>         return set(open(os.path.join(p, "shallow")).read().split())
>     except Exception:
>         return set()
> 
> 
> def show(c, p):
>     r = subprocess.run(["git", "-C", R, "show", f"{c}:{p}"], capture_output=True, text=True)
>     return r.stdout if r.returncode == 0 else None
> 
> 
> def blob(c, p):
>     return g("rev-parse", "--quiet", "--verify", f"{c}:{p}") or "ABSENT"
> 
> 
> def parents(c):
>     return g("log", "--format=%P", "-1", c).split()
> 
> 
> def strict_anc(a, b):
>     return a != b and ok("merge-base", "--is-ancestor", a, b)
> 
> 
24,28c84,91
<     t=show(c,REG); out={}
<     if t is None: return out
<     lines=[l for l in t.splitlines() if l.strip()]
<     if not lines: return out
<     hdr=lines[0].split(",")
---
>     t = show(c, REG)
>     out = {}
>     if t is None:
>         return out
>     lines = [l for l in t.splitlines() if l.strip()]
>     if not lines:
>         return out
>     hdr = lines[0].split(",")
30c93,94
<         f=l.split(","); out[f[0]]=dict(zip(hdr,f))
---
>         f = l.split(",")
>         out[f[0]] = dict(zip(hdr, f))
32c96,109
< def canon_digest(row): return hashlib.sha256(b"\0".join(f"{k}={row[k]}".encode() for k in sorted(row))).hexdigest()
---
> 
> 
> def canon_digest(row):
>     return hashlib.sha256(b"\0".join(f"{k}={row[k]}".encode() for k in sorted(row))).hexdigest()
> 
> 
> def led_raw(c):
>     """커밋 c 시점 원장 blob 의 «정규형» 행 집합 (U-16-c rows(y:LEDGER)) — 경로 부재 = 공집합([H4] 동형)."""
>     t = show(c, LED)
>     if t is None:
>         return set()
>     return set(l.strip() for l in t.splitlines() if l.strip() and not l.startswith("#"))
> 
> 
34,35c111,114
<     t=show(c,LED); out=[]
<     if t is None: return out
---
>     t = show(c, LED)
>     out = []
>     if t is None:
>         return out
37,39c116,121
<         if not l.strip() or l.startswith("#"): continue
<         f=[x.strip() for x in l.split("|")]
<         if len(f)>=6: out.append(dict(row_id=f[0],transition=f[1],digest=f[2],aah=f[3],reviewer_ref=f[4],rationale_ref=f[5],raw=l))
---
>         if not l.strip() or l.startswith("#"):
>             continue
>         f = [x.strip() for x in l.split("|")]
>         if len(f) >= 6:
>             out.append(dict(row_id=f[0], transition=f[1], digest=f[2], aah=f[3],
>                             reviewer_ref=f[4], rationale_ref=f[5], raw=l.strip()))
41,49c123,170
< def c_app(row):  # 도입 지점(구조): raw 행 ∈ blob(x:LED) ∧ ∀p ∉ — 복수면 사전순 최소(픽스처는 단일)
<     cands=[x for x in g("rev-list","HEAD").splitlines() if row["raw"] in (show(x,LED) or "") and all(row["raw"] not in (show(p,LED) or "") for p in parents(x))]
<     return sorted(cands)[0] if cands else None
< def emit(state, reason, executed):
<     print(f"rules_executed={';'.join(executed)}")
<     missing=[r for r in RULES_CONTRACT if r not in executed]
<     if missing and state=="NO_ROWS_CLEAR":
<         print(f"closable_no_provenance_state=PARTIAL_EXECUTION\nreason=S-23: 미실행 규칙 {missing} — green 방출 금지"); sys.exit(1)
<     print(f"closable_no_provenance_state={state}\nreason={reason}"); sys.exit(0 if state=="NO_ROWS_CLEAR" else 1)
---
> 
> 
> def c_app_set(raw):
>     """U-16-c 구조 집합:  c_APP(a) = { x ⊑ HEAD : a ∈ rows(x:LEDGER) ∧ ∀p∈parents(x): a ∉ rows(p:LEDGER) }
>     부모 «커밋 객체»가 없으면(얕은 클론 경계) 둘째 항을 평가할 수 없으므로 그 x 를 도입 지점으로 «확정하지 않는다»
>     — 부재를 «참»으로 접으면 얕은 클론이 임의 커밋을 도입 지점으로 만들어낸다(fail-open)."""
>     cands, boundary = [], []
>     BND = shallow_boundary()
>     for x in g("rev-list", "HEAD").splitlines():
>         if raw not in led_raw(x):
>             continue
>         if x in BND:                      # 얕은 클론 경계 — 부모 집합 «미상» ⇒ 도입 지점으로 확정하지 않는다
>             boundary.append(x)
>             continue
>         ps = parents(x)
>         if any(not have(p) for p in ps):
>             boundary.append(x)
>             continue
>         if all(raw not in led_raw(p) for p in ps):
>             cands.append(x)
>     return cands, boundary
> 
> 
> def c_r_set(c, ref, aah):
>     """g6 구조 정의:  C_R(c) = { x ⊑ c : blob(x:ref) == blob(aah:ref) ∧ ∀p∈parents(x): blob(p:ref) ≠ 그 blob }
>     부모 경로 부재는 ≠ 로 읽는다([H4])."""
>     tgt = blob(aah, ref)
>     if tgt == "ABSENT":
>         return []
>     return [x for x in g("rev-list", c).splitlines()
>             if blob(x, ref) == tgt and all(blob(p, ref) != tgt for p in parents(x))]
> 
> 
> def emit(state, reason, executed, extra=()):
>     for line in extra:
>         print(line)
>     print("rules_executed=" + ";".join(executed))
>     missing = [r for r in RULES_CONTRACT if r not in executed]
>     print("rules_missing=" + (";".join(missing) if missing else "∅"))
>     if missing and state == "NO_ROWS_CLEAR":
>         print("closable_no_provenance_state=PARTIAL_EXECUTION")
>         print(f"reason=S-23: 미실행 규칙 {missing} — green 방출 금지")
>         sys.exit(1)
>     print(f"closable_no_provenance_state={state}")
>     print(f"reason={reason}")
>     sys.exit(0 if state == "NO_ROWS_CLEAR" else 1)
> 
> 
51,55c172,193
<     global R; R=sys.argv[1]; executed=[]
<     if not ok("rev-parse","--is-inside-work-tree") or g("rev-parse","--is-shallow-repository")!="false": emit("PROVENANCE_UNVERIFIABLE","이력 파생 불가",executed)
<     HEAD=g("rev-parse","HEAD"); cur=reg_rows(HEAD)
<     no_rows=[rid for rid,r in cur.items() if r.get("closable")=="NO"]
<     # U-16-a: EDGES(r) for each NO row
---
>     global R
>     R = sys.argv[1]
>     executed = []
>     contributions = []          # (scope, state, why)
> 
>     def add(scope, state, why):
>         contributions.append((scope, state, why))
>         print(f"  · {scope}: {state}({TO[state]}) — {why}")
> 
>     if not ok("rev-parse", "--is-inside-work-tree"):
>         emit("PROVENANCE_UNVERIFIABLE", "git 작업트리 아님", executed)
>     HEAD = g("rev-parse", "HEAD")
>     SHALLOW = (g("rev-parse", "--is-shallow-repository") == "true")
>     print(f"HEAD={HEAD[:7]} shallow={SHALLOW} shallow_boundary={[x[:7] for x in sorted(shallow_boundary())]} EVAL_ORDER={EVAL_ORDER}")
> 
>     # ── 소비자 부재 (전순서 1)
>     consumer_absent = (show(HEAD, REG) is None) or (show(HEAD, LED) is None)
> 
>     cur = reg_rows(HEAD)
>     no_rows = [rid for rid, r in cur.items() if r.get("closable") == "NO"]
> 
>     # ── U-16-a: EDGES(r)  (→NO 간선 전부 · 루트/부모 부재는 ABSENT->NO)
57c195
<     edges={}
---
>     edges = {}
59,62c197,201
<         E=[]
<         for c in g("rev-list","HEAD").splitlines():
<             if reg_rows(c).get(rid,{}).get("closable")!="NO": continue
<             ps=parents(c) or [None]
---
>         E = []
>         for c in g("rev-list", "HEAD").splitlines():
>             if reg_rows(c).get(rid, {}).get("closable") != "NO":
>                 continue
>             ps = parents(c) or [None]
65,70c204,209
<                 if pv!="NO": E.append((p,c,"ABSENT->NO" if pv=="ABSENT" else "YES->NO"))
<         # 표시용 edge_seq 파생: (author date, commit id) 사전식 (U-12 ①-b)
<         E.sort(key=lambda e:(g("log","--format=%ad","--date=iso-strict","-1",e[1]),e[1]))
<         edges[rid]=E
<     L=led_rows(HEAD)
<     for a in L: a["c_APP"]=c_app(a)
---
>                 if pv != "NO":
>                     E.append((p, c, "ABSENT->NO" if pv == "ABSENT" else "YES->NO"))
>         E.sort(key=lambda e: (g("log", "--format=%ad", "--date=iso-strict", "-1", e[1]), e[1]))
>         edges[rid] = E
>     # ── U-16-b: edge_seq 는 «표시용 파생»만 — 판정 입력 아님
>     executed.append("U-16-b(edge_seq 표시용 파생·판정 미소비)")
72,104c211,341
<     for rid,E in edges.items(): print(f"EDGES({rid})={[((p or 'ROOT')[:7],c[:7],t) for p,c,t in E]}  (edge_seq 표시용 파생={list(range(1,len(E)+1))})")
<     print(f"ledger_rows={[(a['row_id'],a['transition'],(a['c_APP'] or '?')[:7]) for a in L]}")
<     def covers(a,p,c,kind):   # → (True,'') | (False,state,why)  — 규칙 순서: g1 → U-16-c → g2 → g3 → g4 → g5 → h → g6
<         if a["row_id"]!=[k for k,E in edges.items() if (p,c,kind) in E][0]: return (False,None,"row_id≠")
<         if a["transition"]!=kind: return (False,"APPROVAL_MALFORMED",f"g1 {a['transition']}≠{kind}")
<         if not a["c_APP"]: return (False,"APPROVAL_MALFORMED","c_APP 파생 불가")
<         if a["c_APP"]==c: return (False,"APPROVAL_SAME_COMMIT","U-16-c c_APP==c")
<         if not strict_anc(a["c_APP"],c): return (False,"APPROVAL_AFTER","U-16-c c_APP⋠c")
<         if canon_digest(cur[a["row_id"]])!=a["digest"]: return (False,"APPROVAL_CONTENT_DRIFT","g2 digest≠재계산")
<         if not ok("merge-base","--is-ancestor",a["aah"],c) or show(a["aah"],a["reviewer_ref"]) is None: return (False,"APPROVAL_HEAD_INVALID","g3")
<         if show(HEAD,a["rationale_ref"]) is None: return (False,"APPROVAL_MALFORMED","g4 rationale_ref 부재")
<         if a["raw"] not in (show(a["c_APP"],LED) or ""): return (False,"APPROVAL_ROW_MUTATED","g5")
<         if a["digest"] not in show(a["aah"],a["reviewer_ref"]): return (False,"APPROVAL_UNBOUND","h digest∉blob(aah)")
<         tgt=blob(a["aah"],a["reviewer_ref"])
<         CR=[x for x in g("rev-list",c).splitlines() if blob(x,a["reviewer_ref"])==tgt and all(blob(pp,a["reviewer_ref"])!=tgt for pp in parents(x))]
<         a.setdefault("_CR",{})[c]=CR
<         if not CR: return (False,"PROVENANCE_UNVERIFIABLE","g6 C_R=∅")
<         if not any(strict_anc(x,a["c_APP"]) for x in CR): return (False,"APPROVAL_ORDER_INVALID",f"g6 C_R={{{','.join(x[:7] for x in CR)}}} 증인 없음")
<         return (True,None,"")
<     executed += ["g1","U-16-c(c_APP⊰c)","g2","g3","g4","g5","h","g6(C_R blob·∃witness)","U-16-a2(∀edge∃row)","MALFORMED(orphan/double-cover)"]
<     worst=[]; covered_by={}
<     for rid,E in edges.items():
<         for i,(p,c,kind) in enumerate(E,1):
<             hits=[]; fails=[]
<             for a in L:
<                 if a["row_id"]!=rid: continue
<                 okc,st,why=covers(a,p,c,kind)
<                 if okc: hits.append(a)
<                 elif st: fails.append((st,why,(a['c_APP'] or '?')[:7])); a["_attributed"]=True if not why.startswith("g1") else a.get("_attributed",False)
<             crs={tuple(a.get('_CR',{}).get(c)) for a in L if a.get('_CR',{}).get(c)}
<             crtxt=" C_R="+"|".join("{"+",".join(x[:7] for x in cr)+"}" for cr in crs) if crs else ""
<             if len(hits)==1: print(f"edge#{i} {rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}: COVERED by c_APP={hits[0]['c_APP'][:7]}{crtxt}"); covered_by.setdefault(id(hits[0]),[]).append(c)
<             elif len(hits)>1: print(f"edge#{i} {rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}: DOUBLE-COVER {[h['c_APP'][:7] for h in hits]}"); worst.append("APPROVAL_MALFORMED")
---
>     for rid, E in edges.items():
>         print(f"EDGES({rid})={[((p or 'ROOT')[:7], c[:7], t) for p, c, t in E]}  "
>               f"(edge_seq 표시용 파생={list(range(1, len(E) + 1))} · 판정 미소비)")
> 
>     L = led_rows(HEAD)
>     executed.append("U-16-c(c_APP 구조 집합·카디널리티·진 조상)")
>     for a in L:
>         a["capp"], a["capp_boundary"] = c_app_set(a["raw"])
>     print("ledger_rows=" + str([(a["row_id"], a["transition"],
>                                  "|c_APP|=%d%s" % (len(a["capp"]),
>                                                    "" if not a["capp_boundary"] else "(+경계 %d)" % len(a["capp_boundary"])),
>                                  [x[:7] for x in a["capp"]]) for a in L]))
> 
>     executed += ["g1", "g2", "g3", "g4", "g5", "h", "g6(C_R blob·∃witness)",
>                  "U-16-a2(∀edge∃row)", "MALFORMED(orphan/double-cover)",
>                  "U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)"]
> 
>     # ── 규칙 사실 수집 (short-circuit 없이 전부 측정한 뒤 순서를 적용한다)
>     def g4_bad(a):
>         return show(HEAD, a["rationale_ref"]) is None
> 
>     def g2_bad(a):
>         return a["row_id"] not in cur or canon_digest(cur[a["row_id"]]) != a["digest"]
> 
>     def g3_bad(a, c):
>         return (not have(a["aah"])) or (not ok("merge-base", "--is-ancestor", a["aah"], c)) \
>             or show(a["aah"], a["reviewer_ref"]) is None
> 
>     def g5_bad(a, capp):
>         return a["raw"] not in led_raw(capp)
> 
>     def h_bad(a):
>         t = show(a["aah"], a["reviewer_ref"])
>         return t is None or a["digest"] not in t
> 
>     print("\n[사실 수집] 규칙별 측정값 (순서 적용 «전»)")
>     for a in L:
>         a["_g4"] = g4_bad(a)
>         a["_g2"] = g2_bad(a)
>         a["_matching_edges"] = [(rid, e) for rid, E in edges.items() for e in E
>                                 if rid == a["row_id"] and e[2] == a["transition"]]
>         a["_rowid_edges"] = [(rid, e) for rid, E in edges.items() for e in E if rid == a["row_id"]]
>         print(f"  row {a['row_id']}/{a['transition']} raw#{L.index(a)}: |c_APP|={len(a['capp'])}"
>               f"{'' if not a['capp_boundary'] else ' 경계커밋=' + str([x[:7] for x in a['capp_boundary']])}"
>               f" g4_bad={a['_g4']} g2_bad={a['_g2']} 대응간선={len(a['_matching_edges'])} row_id간선={len(a['_rowid_edges'])}")
> 
>     print("\n[상태 귀속] 계약 U-16-d 순서 적용")
>     if consumer_absent:
>         add("global", "CONSUMER_ABSENT", "레지스터·원장 부재")
>     # 얕은 클론은 «전역 단축»으로 처리하지 않는다 — 경계 커밋을 도입 지점으로 «확정하지 않음»으로써
>     # `|c_APP|=0` 이라는 구조 사실로 드러나고, 그 값이 선-검사 2 에서 소비된다(계약 U-16-d ①).
>     # 그래야 «순서» 대조군(g1-first)이 전역 단축에 가려지지 않고 순서만으로 갈린다.
> 
>     # ── 행 단위 구조 상태
>     def row_state(a):
>         pre = []
>         if len(a["capp"]) == 0:
>             pre.append(("PROVENANCE_UNVERIFIABLE", "|c_APP|=0 (도입 지점 파생 불가)"))
>         if len(a["capp"]) > 1:
>             pre.append(("APPROVAL_MALFORMED", "|c_APP|=%d>1 (동일 승인 행 병렬 독립 도입) %s"
>                         % (len(a["capp"]), [x[:7] for x in a["capp"]])))
>         g14 = []
>         if a["_g4"]:
>             g14.append(("APPROVAL_MALFORMED", "g4 rationale_ref 미해석"))
>         if not a["_matching_edges"]:
>             g14.append(("APPROVAL_MALFORMED",
>                         "고아 — 대응 간선 0 (row_id 간선 %d · g1 transition 전건 불일치)" % len(a["_rowid_edges"])))
>         seq = (pre + g14) if EVAL_ORDER == "precheck-first" else (g14 + pre)
>         return seq[0] if seq else None
> 
>     for a in L:
>         st = row_state(a)
>         if st:
>             add(f"row[{a['row_id']}/{a['transition']}]", st[0], st[1])
> 
>     # ── 간선 단위
>     def cand_state(a, p, c, kind):
>         """한 후보 행 a 가 간선 (p→c) 에 대해 도달하는 상태 (없으면 None = 덮음)."""
>         capp1 = a["capp"][0] if len(a["capp"]) == 1 else None
>         CR = c_r_set(c, a["reviewer_ref"], a["aah"]) if capp1 else []
>         pre = []
>         if len(a["capp"]) == 0:
>             pre.append(("PROVENANCE_UNVERIFIABLE", "|c_APP|=0"))
>         elif capp1 and not CR:
>             pre.append(("PROVENANCE_UNVERIFIABLE", "g6 C_R=∅"))
>         if len(a["capp"]) > 1:
>             pre.append(("APPROVAL_MALFORMED", "|c_APP|>1"))
>         if a["_g4"]:
>             pre.append(("APPROVAL_MALFORMED", "g4"))
>         g1v = [("APPROVAL_MALFORMED", f"g1 {a['transition']}≠{kind}")] if a["transition"] != kind else []
>         head = (pre + g1v) if EVAL_ORDER == "precheck-first" else (g1v + pre)
>         if head:
>             return head[0]
>         if capp1 is None:
>             return ("PROVENANCE_UNVERIFIABLE", "|c_APP|≠1 — g-단락 진입 불가")
>         # ② g-단락 (5~11) — |c_APP|=1 의 «유일 원소»만 쓴다
>         if capp1 == c:
>             return ("APPROVAL_SAME_COMMIT", f"U-16-c c_APP={capp1[:7]} == 간선 커밋")
>         if not strict_anc(capp1, c):
>             return ("APPROVAL_AFTER", f"U-16-c c_APP={capp1[:7]} 가 {c[:7]} 의 진 조상 아님")
>         if a["_g2"]:
>             return ("APPROVAL_CONTENT_DRIFT", "g2 재계산 digest ≠ 원장 보유값")
>         if g3_bad(a, c):
>             return ("APPROVAL_HEAD_INVALID", "g3 approved_at_head 비조상·그 시점 blob 소비 불가")
>         if g5_bad(a, capp1):
>             return ("APPROVAL_ROW_MUTATED", "g5 c_APP 시점 행 ≠ 현행 행")
>         if h_bad(a):
>             return ("APPROVAL_UNBOUND", "h digest ∉ blob(approved_at_head:reviewer_ref)")
>         if not any(strict_anc(x, capp1) for x in CR):
>             return ("APPROVAL_ORDER_INVALID",
>                     "g6 C_R={%s} 에 c_APP 진 조상 증인 없음" % ",".join(x[:7] for x in CR))
>         return None
> 
>     for rid, E in edges.items():
>         for i, (p, c, kind) in enumerate(E, 1):
>             cands = [a for a in L if a["row_id"] == rid]
>             corr = [a for a in cands if a["transition"] == kind] if EVAL_ORDER == "precheck-first" else cands
>             covers, fails = [], []
>             for a in corr:
>                 st = cand_state(a, p, c, kind)
>                 (covers if st is None else fails).append((a, st))
>             tag = f"edge#{i}[{rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}]"
>             crs = {tuple(c_r_set(c, a["reviewer_ref"], a["aah"])) for a in corr if len(a["capp"]) == 1}
>             crtxt = " C_R=" + "|".join("{" + ",".join(x[:7] for x in cr) + "}" for cr in crs) if crs else ""
>             if len(covers) == 1:
>                 print(f"  · {tag}: COVERED by c_APP={covers[0][0]['capp'][0][:7]}{crtxt}")
>             elif len(covers) > 1:
>                 add(tag, "APPROVAL_MALFORMED",
>                     "이중 덮음 %s" % [x[0]["capp"][0][:7] for x in covers])
>             elif not fails:
>                 add(tag, "APPROVAL_MISSING", f"덮는 행 부재 (후보 {len(cands)} · 대응 {len(corr)}){crtxt}")
106,115c343,359
<                 print(f"edge#{i} {rid} {(p or 'ROOT')[:7]}->{c[:7]} {kind}: UNCOVERED fails={fails}{crtxt}")
<                 worst.append(min((f[0] for f in fails), key=PRIO.index) if fails else "APPROVAL_MISSING")
<     for a in L:   # 고아 = «어떤 간선에도 구조적으로 대응하지 않는 행»(row_id 무간선·g1 전부 불일치). 특정 규칙(U-16-c~g6)에서 탈락한 행은 그 규칙 상태로 귀속되며 고아가 아니다
<         if id(a) not in covered_by and not a.get("_attributed"): print(f"ORPHAN row c_APP={(a['c_APP'] or '?')[:7]} (구조적 비대응)"); worst.append("APPROVAL_MALFORMED")
<     if not no_rows: emit("NO_ROWS_CLEAR","closable=NO 행 없음(판정 우주 ∅ — 공허 통과가 아니라 대상 없음)",executed)
<     if worst: emit(min(worst,key=PRIO.index),f"차단 사유(우선순위 최상): {sorted(set(worst),key=PRIO.index)}",executed)
<     emit("NO_ROWS_CLEAR","모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 고아 0",executed)
< if __name__=="__main__":
<     try: main()
<     except SystemExit: raise
---
>                 st = min((f[1] for f in fails), key=lambda s: TO[s[0]])
>                 add(tag, st[0], f"{st[1]} (후보 {len(cands)} · 대응 {len(corr)}){crtxt}")
> 
>     if not no_rows:
>         emit("NO_ROWS_CLEAR", "closable=NO 행 없음(판정 우주 ∅ — 공허 통과가 아니라 대상 없음)", executed)
>     if contributions:
>         best = min(contributions, key=lambda t: TO[t[1]])
>         allst = sorted({c[1] for c in contributions}, key=lambda s: TO[s])
>         emit(best[1], f"전순서 최소 = {best[1]}({TO[best[1]]}) @ {best[0]} — {best[2]} · 발화 전체={allst}", executed)
>     emit("NO_ROWS_CLEAR", "모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0", executed)
> 
> 
> if __name__ == "__main__":
>     try:
>         main()
>     except SystemExit:
>         raise
117c361,363
<         print(f"rules_executed=\nclosable_no_provenance_state=PROVENANCE_UNVERIFIABLE\nreason=판정 미산출: {e!r}"); sys.exit(1)
---
>         print("rules_executed=\nrules_missing=(예외)\nclosable_no_provenance_state=PROVENANCE_UNVERIFIABLE")
>         print(f"reason=판정 미산출: {e!r}")
>         sys.exit(1)
```

## 3. 픽스처·드라이버 원문 — `t82v219.sh` (sha256 `b4553c367f91341a2dba235ec4712909bb6dabc03574ce3dc7884a2486ee9a2b`)

```bash
#!/usr/bin/env bash
# t82v219.sh — T-82 ⑱(현행 스키마·edge_seq 기재 없음)·⑳ⓐ(형제 동일 행 → |c_APP|=2)·⑳ⓑ(얕은 클론 선-검사 corner)
#              + 회귀 ⑰ⓐⓑⓒ·⑲·⑮·⑯·⑪(transition 불일치)·자인 잔여.  독립 git 픽스처(scratchpad) + 전 규칙 실행기.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u16-full-exec-v219.py"; CTRL="$SP/u16-order-ctrl-g1first.py"; EX215="$SP/u16-full-exec-v215.py"
FX="$SP/fx82z"; REF=reviews/review.md; RAT=rationale/r1.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
dig(){ python3 -c "import hashlib,sys; r=dict(id=sys.argv[1],closable=sys.argv[2],owner_track=sys.argv[3]); print(hashlib.sha256(b'\0'.join(f'{k}={r[k]}'.encode() for k in sorted(r))).hexdigest())" "$@"; }
DNO=$(dig r1 NO tos)     # 승인 대상 = 제안된 NO 행 (id=r1, closable=NO, owner_track=tos)
reg(){ printf 'id,closable,owner_track\n'; for kv in "$@"; do printf '%s\n' "$kv"; done; }
c(){ git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse --short HEAD; }
base(){ rm -rf "$1"; git init -q -b main "$1"; mkdir -p "$1/reviews" "$1/rationale"
  reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; echo "## ledger" > "$1/LEDGER.md"; echo "rationale for r1 NO" > "$1/$RAT"
  echo "rationale (approver a)" > "$1/rationale/r1-a.md"; echo "rationale (approver b)" > "$1/rationale/r1-b.md"
  case "${2:-full}" in full) printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$1/$REF";; carrier) printf '%s\n' "$DNO" > "$1/$REF";; unrelated) printf 'unrelated review text\n' > "$1/$REF";; none) ;; esac
  c "$1" "H0: base (r1=YES; reviewer=${2:-full})"; }
row(){ printf 'r1 | %s | %s | %s | %s | %s\n' "$1" "$DNO" "$2" "$REF" "${3:-$RAT}"; }
setNO(){ reg 'other,YES,x' 'r1,NO,tos' > "$1/register.csv"; }
setYES(){ reg 'other,YES,x' 'r1,YES,tos' > "$1/register.csv"; }
run(){ git -C "$1" log --graph --oneline --all | sed 's/^/  /'; echo "\$ python3 $(basename "${2:-$EX}") <fixture>"; python3 "${2:-$EX}" "$1"; echo "u16_rc=$?"; }
mergeled(){ git -C "$1" merge -q --no-ff -m "$3" "$2" 2>/dev/null || { { echo "## ledger"; git -C "$1" show HEAD:LEDGER.md | tail -n +2; git -C "$1" show "$2":LEDGER.md | tail -n +2; } | awk '!seen[$0]++' > "$1/LEDGER.md"; git -C "$1" add -A; git -C "$1" commit -q -m "$3"; }; }

rm -rf "$FX"; mkdir -p "$FX"
printf 't82v219_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u16-full-exec-v219.py)=%s\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u16-order-ctrl-g1first.py)=%s   (⑳ⓑ 대조군 — EVAL_ORDER 한 줄만 다름)\n' "$(shasum -a 256 "$CTRL" | cut -d" " -f1)"
printf 'sha256(u16-full-exec-v215.py)=%s   (직전 판 부속 — «복수면 사전순 최소» · ⑳ⓐ 판별력 대조용)\n' "$(shasum -a 256 "$EX215" | cut -d" " -f1)"
echo "D_NO(row_content_digest of proposed r1 NO row) = $DNO"
echo "계약 U-16-d 전순서: 1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR"

########################################################################
sec "T-82 ⑱-1 [현행 스키마] 병렬 반복 이력(양성) — ABSENT->NO->YES->NO 두 간선을 «서로 다른 승인 행»이 각각 덮고, 두 도입이 형제 브랜치 → merge · edge_seq 기재 없음 ⇒ NO_ROWS_CLEAR"
R="$FX/18-1"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
echo "rationale (approver a)" > "$R/rationale/r1-a.md"; echo "rationale (approver b)" > "$R/rationale/r1-b.md"
printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent (reviewer artifact with digest)")
# 두 승인 행의 «도입»을 형제 브랜치에 두고 merge (원장만 건드린다 — 레지스터 무변경 · edge_seq 기재 없음)
git -C "$R" checkout -q --detach "$H0"; row ABSENT-\>NO "$H0" rationale/r1-a.md >> "$R/LEDGER.md"; A1=$(c "$R" "A1: approval row (ABSENT->NO, rationale a) [branch a]")
git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$H0" rationale/r1-b.md >> "$R/LEDGER.md"; A2=$(c "$R" "A2: approval row (YES->NO, rationale b) [branch b]")
git -C "$R" checkout -q --detach "$A1"; mergeled "$R" "$A2" "MA: merge sibling approval introductions (union)"
MA=$(git -C "$R" rev-parse --short HEAD)
# 반복 이력: ABSENT->NO (e1) → back to YES → YES->NO (e2)  — 두 간선 모두 MA 의 자손이다
setNO "$R"; E1=$(c "$R" "e1: ABSENT->NO"); setYES "$R"; HY=$(c "$R" "back to YES"); setNO "$R"; E2=$(c "$R" "e2: YES->NO")
git -C "$R" branch -f main HEAD
echo "H0=$H0 A1=$A1 A2=$A2 MA=$MA e1=$E1 e2=$E2"; echo "-- LEDGER@HEAD --"; git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'
echo "-- g5 구 승인 행 불변 확인: A1·A2 도입 시점 행 (HEAD 행과 byte 동일이어야 한다) --"
git -C "$R" show "$A1:LEDGER.md" | tail -n +2 | sed 's/^/  A1| /'; git -C "$R" show "$A2:LEDGER.md" | tail -n +2 | sed 's/^/  A2| /'; run "$R"

sec "T-82 ⑱-2 [문언 리터럴 «별개 row_id»] 같은 반복 이력을 «서로 다른 row_id» 승인 행으로 덮으면? (관측 보고 대상)"
R="$FX/18-2"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent")
git -C "$R" checkout -q --detach "$H0"; printf 'r1 | ABSENT->NO | %s | %s | %s | %s\n' "$DNO" "$H0" "$REF" "$RAT" >> "$R/LEDGER.md"; B1=$(c "$R" "B1: approval row_id=r1")
git -C "$R" checkout -q --detach "$H0"; printf 'r1b | YES->NO | %s | %s | %s | %s\n' "$DNO" "$H0" "$REF" "$RAT" >> "$R/LEDGER.md"; B2=$(c "$R" "B2: approval row_id=r1b (문언 «별개 row_id»)")
git -C "$R" checkout -q --detach "$B1"; mergeled "$R" "$B2" "MB: merge sibling approvals"; MB=$(git -C "$R" rev-parse --short HEAD)
setNO "$R"; c "$R" "e1: ABSENT->NO" >/dev/null; setYES "$R"; c "$R" "back to YES" >/dev/null; setNO "$R"; E2=$(c "$R" "e2: YES->NO")
git -C "$R" branch -f main HEAD
git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

########################################################################
sec "T-82 ⑳ⓐ 동일 승인 행 형제 독립 도입 → |c_APP(a)|=2 ⇒ APPROVAL_MALFORMED(3) + rc≠0"
# X(조상 도입) 가 Y(형제 도입) 보다 «사전순으로 앞서도록» 구성한다 — «복수면 사전순 최소» 구현이 조상을 골라 통과하는 최악 케이스를 실측하기 위함
n=0
while :; do
  R="$FX/20a"; H0=$(base "$R")
  git -C "$R" checkout -q --detach; row YES-\>NO "$H0" >> "$R/LEDGER.md"; X=$(c "$R" "X: approval row A [branch x nonce=$n]")
  setNO "$R"; CN=$(c "$R" "CN: NO transition (child of X)")
  git -C "$R" checkout -q --detach main; row YES-\>NO "$H0" >> "$R/LEDGER.md"; Y=$(c "$R" "Y: approval row A (byte-identical) [branch y nonce=$n]")
  XF=$(git -C "$R" rev-parse "$X"); YF=$(git -C "$R" rev-parse "$Y")
  [ "$XF" \< "$YF" ] && break
  n=$((n+1)); [ "$n" -lt 60 ] || { echo "  (nonce 60회 내 X<Y 구성 실패 — 그대로 진행)"; break; }
done
git -C "$R" checkout -q --detach "$CN"; mergeled "$R" "$Y" "M: merge sibling identical approval introduction"; git -C "$R" branch -f main HEAD
echo "H0=$H0 X=$X(=$XF) CN=$CN Y=$Y(=$YF)  [사전순: $( [ "$XF" \< "$YF" ] && echo 'X < Y — 사전순 최소 = 조상 도입' || echo 'Y < X')]"
echo "-- LEDGER@HEAD (형제 두 도입이 «같은 한 줄» 로 합쳐진다) --"; git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

sec "T-82 ⑳ⓐ 판별력 대조 — 같은 픽스처를 «복수면 사전순 최소» 구현(직전 판 부속 u16-full-exec-v215.py)으로 실행 → 조상 도입을 골라 통과하면 그것이 F5 «회피»의 실증"
run "$R" "$EX215"

########################################################################
sec "T-82 ⑳ⓑ 선-검사 순서 corner — 형제 동일 행 도입을 «얕은 클론»에서 실행: |c_APP|=0 ∧ g1 위배 동시 성립 ⇒ PROVENANCE_UNVERIFIABLE(2) + rc≠0"
SH="$FX/20b-shallow"; rm -rf "$SH"
git clone -q --depth 1 "file://$FX/20a" "$SH" 2>/dev/null
echo "-- 얕은 클론 확인 --"
echo "  is-shallow-repository = $(git -C "$SH" rev-parse --is-shallow-repository)"
echo "  rev-list HEAD 개수    = $(git -C "$SH" rev-list HEAD | wc -l | tr -d ' ')"
echo "  parents(HEAD)         = $(git -C "$SH" log --format=%P -1 HEAD)  (객체 실재? $(for p in $(git -C "$SH" log --format=%P -1 HEAD); do git -C "$SH" cat-file -e "$p^{commit}" 2>/dev/null && echo -n "$p=present " || echo -n "$p=ABSENT "; done))"
echo "-- 원장·레지스터 @HEAD --"; git -C "$SH" show HEAD:LEDGER.md | sed 's/^/  | /'; git -C "$SH" show HEAD:register.csv | sed 's/^/  | /'
run "$SH"

sec "T-82 ⑳ⓑ 판별력 대조 — 같은 얕은 클론을 «g1·g4 먼저» 문자 구현(u16-order-ctrl-g1first.py)으로 실행 → APPROVAL_MALFORMED(3) 이면 «실패»(전순서 최소 = 2)"
run "$SH" "$CTRL"

########################################################################
sec "회귀 ⑯ — ABSENT->NO->YES->NO, 간선별 별도 승인 (선형) ⇒ NO_ROWS_CLEAR"
R="$FX/16"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent")
row ABSENT-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A1=$(c "$R" "A1: approval (ABSENT->NO)"); setNO "$R"; E1=$(c "$R" "e1: ABSENT->NO")
setYES "$R"; H2=$(c "$R" "back to YES")
row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A2=$(c "$R" "A2: approval (YES->NO)"); setNO "$R"; E2=$(c "$R" "e2: YES->NO")
git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

sec "회귀 ⑰ⓐ 기존-경로 B∥A (blob C_R) ⇒ APPROVAL_ORDER_INVALID(11)"
R="$FX/17a"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B=$(c "$R" "B: real review content (digest) into existing path")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B) [parallel to B]")
git -C "$R" merge -q --no-ff -m "M0: merge B" "$B"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"

sec "회귀 ⑰ⓑ 머지 해소에서 digest blob 도입 ⇒ APPROVAL_UNBOUND(10) [v2.15 E2 에라타 기대값]"
R="$FX/17b"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'unrelated review text\nB-side edit (no digest)\n' > "$R/$REF"; B=$(c "$R" "B: reviewer edit without digest")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B — B lacks digest)")
git -C "$R" merge -q --no-commit --no-ff "$B" >/dev/null 2>&1 || true; printf 'independent review of r1 -> NO (introduced in merge resolution)\n%s\n' "$DNO" > "$R/$REF"; setNO "$R"; M=$(c "$R" "M: merge — digest blob introduced in resolution + NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"
echo "-- ⑰ⓑ g6 단독 뷰 (target=blob(M:ref), c=M, c_APP=A) --"
python3 - "$R" "$REF" "$M" "$A" <<'PY'
import subprocess,sys
R,REF,C,CAPP=sys.argv[1:5]
def g(*a): return subprocess.run(["git","-C",R,*a],capture_output=True,text=True).stdout.strip()
def ok(*a): return subprocess.run(["git","-C",R,*a],capture_output=True).returncode==0
def blob(c): return g("rev-parse","--quiet","--verify",f"{c}:{REF}") or "ABSENT"
tgt=blob(C); CR=[x for x in g("rev-list",C).splitlines() if blob(x)==tgt and all(blob(p)!=tgt for p in g("log","--format=%P","-1",x).split())]
print(f"  C_R(target=blob(M))={{{','.join(x[:7] for x in CR)}}}"); w=[x for x in CR if x!=g("rev-parse",CAPP) and ok("merge-base","--is-ancestor",x,CAPP)]
print("  g6_verdict=" + ("OK" if w else "APPROVAL_ORDER_INVALID"))
PY

sec "회귀 ⑰ⓒ 양성 — B1·B2 독립 동일 blob, A ⊐ B1 ⇒ NO_ROWS_CLEAR"
R="$FX/17c"; H0=$(base "$R" unrelated)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B1=$(c "$R" "B1: review content (digest)"); row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval (aah=B1)")
git -C "$R" checkout -q --detach main; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B2=$(c "$R" "B2: independent identical blob")
git -C "$R" checkout -q --detach "$A"; git -C "$R" merge -q --no-ff -m "M0: merge B2" "$B2" 2>/dev/null || { git -C "$R" checkout --theirs "$REF"; git -C "$R" add -A; git -C "$R" commit -q -m "M0: merge B2"; }; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B1=$B1 A=$A B2=$B2 M=$M"; run "$R"

sec "회귀 ⑲ digest 선배치 ⇒ APPROVAL_ORDER_INVALID(11)"
R="$FX/19"; H0=$(base "$R" carrier)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; B=$(c "$R" "B: real review content (digest kept)")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$B")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=B) [parallel]")
git -C "$R" merge -q --no-ff -m "M0: merge B" "$B"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 B=$B A=$A M=$M"; run "$R"
echo "-- ⑲ v2.14 토큰 기반 C_R 대조 --"
python3 - "$R" "$REF" "$M" "$A" "$DNO" <<'PY'
import subprocess,sys
R,REF,C,CAPP,DIG=sys.argv[1:6]
def g(*a): return subprocess.run(["git","-C",R,*a],capture_output=True,text=True).stdout.strip()
def ok(*a): return subprocess.run(["git","-C",R,*a],capture_output=True).returncode==0
def has(c):
    r=subprocess.run(["git","-C",R,"show",f"{c}:{REF}"],capture_output=True,text=True); return r.returncode==0 and DIG in r.stdout
CR=[x for x in g("rev-list",C).splitlines() if has(x) and all(not has(p) for p in g("log","--format=%P","-1",x).split())]
print(f"  token C_R={{{','.join(x[:7] for x in CR)}}}  witness={'YES(green — 선배치 우회 통과)' if any(x!=g('rev-parse',CAPP) and ok('merge-base','--is-ancestor',x,CAPP) for x in CR) else 'NO'}")
PY

sec "회귀 ⑮ 신규 아티팩트 R ∥ A ⇒ APPROVAL_ORDER_INVALID(11)"
R="$FX/15"; H0=$(base "$R" none)
git -C "$R" checkout -q --detach; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; RR=$(c "$R" "R: new reviewer artifact")
git -C "$R" checkout -q --detach main; row YES-\>NO "$(git -C "$R" rev-parse "$RR")" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval (aah=R) [parallel]")
git -C "$R" merge -q --no-ff -m "M0: merge R" "$RR"; setNO "$R"; M=$(c "$R" "M: NO transition"); git -C "$R" branch -f main HEAD
echo "H0=$H0 R=$RR A=$A M=$M"; run "$R"

sec "회귀 ⑪ transition 명세 불일치 (원장 YES->NO · 실제 파생 간선 ABSENT->NO) ⇒ APPROVAL_MALFORMED(3)"
R="$FX/11"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
reg 'other,YES,x' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; H0=$(c "$R" "H0: r1 absent")
row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval claims YES->NO"); setNO "$R"; E=$(c "$R" "e: actual edge is ABSENT->NO")
git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"

sec "자인 잔여 — 단일 행이 두 간선을 덮는다 (계약 «닫지 못하는 것» 정직 표기 그대로)"
R="$FX/one"; H0=$(base "$R")
row YES-\>NO "$(git -C "$R" rev-parse HEAD)" >> "$R/LEDGER.md"; A=$(c "$R" "A: SINGLE approval row"); setNO "$R"; E1=$(c "$R" "e1: YES->NO"); setYES "$R"; c "$R" "back to YES" >/dev/null; setNO "$R"; E2=$(c "$R" "e2: YES->NO (no new approval)")
git -C "$R" show HEAD:LEDGER.md | sed 's/^/  | /'; run "$R"
```

## 4. 실행 기록 (`bash t82v219.sh` stdout 전문 · 픽스처 DAG · EDGES · ledger_rows · 사실 수집 · 상태 귀속 · `rules_executed` · 상태 · rc)

각 run 은 `$ python3 <실행기> <fixture>` 라인이 열고, run 당 상태 라인은 `closable_no_provenance_state=` **정확히 1개**다. 기록은 발행 시점에 확정되고 이후 편집하지 않는다(U-15-e (4d) 준용).
`git merge` 의 한국어 충돌 메시지(«자동 병합이 실패했습니다…»)는 **드라이버가 의도적으로 유발한 원장 합집합 해소**의 stderr 이며(`mergeled()`), 그 직후 합집합 커밋이 만들어진다.

```text
t82v219_utc=2026-08-19T01:14:10Z
sha256(u16-full-exec-v219.py)=5692e75d46962e8170db31be79f2678b6070bb6f3770d0c8720f2617dafa60a5
sha256(u16-order-ctrl-g1first.py)=4e9f0bc42b86d5e9f34d5f216df474c0da5a3b655b6fddeecf6a31f8501a51cd   (⑳ⓑ 대조군 — EVAL_ORDER 한 줄만 다름)
sha256(u16-full-exec-v215.py)=a0201149b794de7ae438d05e035246d35598a1173ecd5481e1217e647f38e5d0   (직전 판 부속 — «복수면 사전순 최소» · ⑳ⓐ 판별력 대조용)
D_NO(row_content_digest of proposed r1 NO row) = 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9
계약 U-16-d 전순서: 1 CONSUMER_ABSENT · 2 PROVENANCE_UNVERIFIABLE · 3 APPROVAL_MALFORMED · 4 APPROVAL_MISSING · 5 SAME_COMMIT · 6 AFTER · 7 CONTENT_DRIFT · 8 HEAD_INVALID · 9 ROW_MUTATED · 10 UNBOUND · 11 ORDER_INVALID · 12 NO_ROWS_CLEAR

########## T-82 ⑱-1 [현행 스키마] 병렬 반복 이력(양성) — ABSENT->NO->YES->NO 두 간선을 «서로 다른 승인 행»이 각각 덮고, 두 도입이 형제 브랜치 → merge · edge_seq 기재 없음 ⇒ NO_ROWS_CLEAR ##########
자동 병합: LEDGER.md
충돌 (내용): LEDGER.md에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
H0=12f0d69 A1=9d09dd1 A2=22424c7 MA=cf5115a e1=f7b5e5f e2=c2b31c9
-- LEDGER@HEAD --
  | ## ledger
  | r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 12f0d69 | reviews/review.md | rationale/r1-a.md
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 12f0d69 | reviews/review.md | rationale/r1-b.md
-- g5 구 승인 행 불변 확인: A1·A2 도입 시점 행 (HEAD 행과 byte 동일이어야 한다) --
  A1| r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 12f0d69 | reviews/review.md | rationale/r1-a.md
  A2| r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 12f0d69 | reviews/review.md | rationale/r1-b.md
  * c2b31c9 e2: YES->NO
  * 427b5bd back to YES
  * f7b5e5f e1: ABSENT->NO
  *   cf5115a MA: merge sibling approval introductions (union)
  |\  
  | * 22424c7 A2: approval row (YES->NO, rationale b) [branch b]
  * | 9d09dd1 A1: approval row (ABSENT->NO, rationale a) [branch a]
  |/  
  * 12f0d69 H0: r1 absent (reviewer artifact with digest)
$ python3 u16-full-exec-v219.py <fixture>
HEAD=c2b31c9 shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('cf5115a', 'f7b5e5f', 'ABSENT->NO'), ('427b5bd', 'c2b31c9', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['9d09dd1']), ('r1', 'YES->NO', '|c_APP|=1', ['22424c7'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 cf5115a->f7b5e5f ABSENT->NO]: COVERED by c_APP=9d09dd1 C_R={12f0d69}
  · edge#2[r1 427b5bd->c2b31c9 YES->NO]: COVERED by c_APP=22424c7 C_R={12f0d69}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## T-82 ⑱-2 [문언 리터럴 «별개 row_id»] 같은 반복 이력을 «서로 다른 row_id» 승인 행으로 덮으면? (관측 보고 대상) ##########
자동 병합: LEDGER.md
충돌 (내용): LEDGER.md에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
  | ## ledger
  | r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 181c2b0 | reviews/review.md | rationale/r1.md
  | r1b | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 181c2b0 | reviews/review.md | rationale/r1.md
  * b2faadb e2: YES->NO
  * 801f2cc back to YES
  * 2143418 e1: ABSENT->NO
  *   0341e4f MB: merge sibling approvals
  |\  
  | * e6aef91 B2: approval row_id=r1b (문언 «별개 row_id»)
  * | 971ec9d B1: approval row_id=r1
  |/  
  * 181c2b0 H0: r1 absent
$ python3 u16-full-exec-v219.py <fixture>
HEAD=b2faadb shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('0341e4f', '2143418', 'ABSENT->NO'), ('801f2cc', 'b2faadb', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['971ec9d']), ('r1b', 'YES->NO', '|c_APP|=1', ['e6aef91'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1b/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=True 대응간선=0 row_id간선=0

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1b/YES->NO]: APPROVAL_MALFORMED(3) — 고아 — 대응 간선 0 (row_id 간선 0 · g1 transition 전건 불일치)
  · edge#1[r1 0341e4f->2143418 ABSENT->NO]: COVERED by c_APP=971ec9d C_R={181c2b0}
  · edge#2[r1 801f2cc->b2faadb YES->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1b/YES->NO] — 고아 — 대응 간선 0 (row_id 간선 0 · g1 transition 전건 불일치) · 발화 전체=['APPROVAL_MALFORMED', 'APPROVAL_MISSING']
u16_rc=1

########## T-82 ⑳ⓐ 동일 승인 행 형제 독립 도입 → |c_APP(a)|=2 ⇒ APPROVAL_MALFORMED(3) + rc≠0 ##########
H0=1ba84bd X=590067c(=590067c13c516c882099b4f3b82b726b3ec82ed6) CN=70ebc84 Y=e8f5c99(=e8f5c99141fc518f89dd0a8f6f86ee2a61b10ff9)  [사전순: X < Y — 사전순 최소 = 조상 도입]
-- LEDGER@HEAD (형제 두 도입이 «같은 한 줄» 로 합쳐진다) --
  | ## ledger
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 1ba84bd | reviews/review.md | rationale/r1.md
  *   2ce323a M: merge sibling identical approval introduction
  |\  
  | * e8f5c99 Y: approval row A (byte-identical) [branch y nonce=0]
  * | 70ebc84 CN: NO transition (child of X)
  * | 590067c X: approval row A [branch x nonce=0]
  |/  
  * 1ba84bd H0: base (r1=YES; reviewer=full)
$ python3 u16-full-exec-v219.py <fixture>
HEAD=2ce323a shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('e8f5c99', '2ce323a', 'YES->NO'), ('590067c', '70ebc84', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=2', ['e8f5c99', '590067c'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=2 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['e8f5c99', '590067c']
  · edge#1[r1 e8f5c99->2ce323a YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
  · edge#2[r1 590067c->70ebc84 YES->NO]: APPROVAL_MALFORMED(3) — |c_APP|>1 (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — |c_APP|=2>1 (동일 승인 행 병렬 독립 도입) ['e8f5c99', '590067c'] · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

########## T-82 ⑳ⓐ 판별력 대조 — 같은 픽스처를 «복수면 사전순 최소» 구현(직전 판 부속 u16-full-exec-v215.py)으로 실행 → 조상 도입을 골라 통과하면 그것이 F5 «회피»의 실증 ##########
  *   2ce323a M: merge sibling identical approval introduction
  |\  
  | * e8f5c99 Y: approval row A (byte-identical) [branch y nonce=0]
  * | 70ebc84 CN: NO transition (child of X)
  * | 590067c X: approval row A [branch x nonce=0]
  |/  
  * 1ba84bd H0: base (r1=YES; reviewer=full)
$ python3 u16-full-exec-v215.py <fixture>
NO_rows=['r1']
EDGES(r1)=[('e8f5c99', '2ce323a', 'YES->NO'), ('590067c', '70ebc84', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2])
ledger_rows=[('r1', 'YES->NO', '590067c')]
edge#1 r1 e8f5c99->2ce323a YES->NO: COVERED by c_APP=590067c C_R={1ba84bd}
edge#2 r1 590067c->70ebc84 YES->NO: COVERED by c_APP=590067c C_R={1ba84bd}
rules_executed=U-16-a(EDGES);g1;U-16-c(c_APP⊰c);g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover)
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 고아 0
u16_rc=0

########## T-82 ⑳ⓑ 선-검사 순서 corner — 형제 동일 행 도입을 «얕은 클론»에서 실행: |c_APP|=0 ∧ g1 위배 동시 성립 ⇒ PROVENANCE_UNVERIFIABLE(2) + rc≠0 ##########
-- 얕은 클론 확인 --
  is-shallow-repository = true
  rev-list HEAD 개수    = 1
  parents(HEAD)         =   (객체 실재? )
-- 원장·레지스터 @HEAD --
  | ## ledger
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 1ba84bd | reviews/review.md | rationale/r1.md
  | id,closable,owner_track
  | other,YES,x
  | r1,NO,tos
  * 2ce323a M: merge sibling identical approval introduction
$ python3 u16-full-exec-v219.py <fixture>
HEAD=2ce323a shallow=True shallow_boundary=['2ce323a'] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('ROOT', '2ce323a', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['2ce323a'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: PROVENANCE_UNVERIFIABLE(2) — |c_APP|=0 (도입 지점 파생 불가)
  · edge#1[r1 ROOT->2ce323a ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ row[r1/YES->NO] — |c_APP|=0 (도입 지점 파생 불가) · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_MISSING']
u16_rc=1

########## T-82 ⑳ⓑ 판별력 대조 — 같은 얕은 클론을 «g1·g4 먼저» 문자 구현(u16-order-ctrl-g1first.py)으로 실행 → APPROVAL_MALFORMED(3) 이면 «실패»(전순서 최소 = 2) ##########
  * 2ce323a M: merge sibling identical approval introduction
$ python3 u16-order-ctrl-g1first.py <fixture>
HEAD=2ce323a shallow=True shallow_boundary=['2ce323a'] EVAL_ORDER=g1-first
NO_rows=['r1']
EDGES(r1)=[('ROOT', '2ce323a', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=0(+경계 1)', [])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=0 경계커밋=['2ce323a'] g4_bad=False g2_bad=False 대응간선=0 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — 고아 — 대응 간선 0 (row_id 간선 1 · g1 transition 전건 불일치)
  · edge#1[r1 ROOT->2ce323a ABSENT->NO]: APPROVAL_MALFORMED(3) — g1 YES->NO≠ABSENT->NO (후보 1 · 대응 1)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — 고아 — 대응 간선 0 (row_id 간선 1 · g1 transition 전건 불일치) · 발화 전체=['APPROVAL_MALFORMED']
u16_rc=1

########## 회귀 ⑯ — ABSENT->NO->YES->NO, 간선별 별도 승인 (선형) ⇒ NO_ROWS_CLEAR ##########
  | ## ledger
  | r1 | ABSENT->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 1271d1ae54c355888fdbf42a52b657e8391e207b | reviews/review.md | rationale/r1.md
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | d5e0588d0da2884a61792d242957b14ee53d0165 | reviews/review.md | rationale/r1.md
  * 123eb3f e2: YES->NO
  * 5380086 A2: approval (YES->NO)
  * d5e0588 back to YES
  * 68a0e8d e1: ABSENT->NO
  * 2a11501 A1: approval (ABSENT->NO)
  * 1271d1a H0: r1 absent
$ python3 u16-full-exec-v219.py <fixture>
HEAD=123eb3f shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('2a11501', '68a0e8d', 'ABSENT->NO'), ('5380086', '123eb3f', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'ABSENT->NO', '|c_APP|=1', ['2a11501']), ('r1', 'YES->NO', '|c_APP|=1', ['5380086'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/ABSENT->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2
  row r1/YES->NO raw#1: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 2a11501->68a0e8d ABSENT->NO]: COVERED by c_APP=2a11501 C_R={1271d1a}
  · edge#2[r1 5380086->123eb3f YES->NO]: COVERED by c_APP=5380086 C_R={1271d1a}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## 회귀 ⑰ⓐ 기존-경로 B∥A (blob C_R) ⇒ APPROVAL_ORDER_INVALID(11) ##########
H0=ad450c1 B=3e457f1 A=f020b85 M=595a67b
  * 595a67b M: NO transition
  *   0277d95 M0: merge B
  |\  
  | * 3e457f1 B: real review content (digest) into existing path
  * | f020b85 A: approval row (aah=B) [parallel to B]
  |/  
  * ad450c1 H0: base (r1=YES; reviewer=unrelated)
$ python3 u16-full-exec-v219.py <fixture>
HEAD=595a67b shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('0277d95', '595a67b', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['f020b85'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 0277d95->595a67b YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={3e457f1} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={3e457f1}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 0277d95->595a67b YES->NO] — g6 C_R={3e457f1} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={3e457f1} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1

########## 회귀 ⑰ⓑ 머지 해소에서 digest blob 도입 ⇒ APPROVAL_UNBOUND(10) [v2.15 E2 에라타 기대값] ##########
H0=e56ee9d B=189c48e A=72c539d M=bdff24c
  *   bdff24c M: merge — digest blob introduced in resolution + NO transition
  |\  
  | * 189c48e B: reviewer edit without digest
  * | 72c539d A: approval row (aah=B — B lacks digest)
  |/  
  * e56ee9d H0: base (r1=YES; reviewer=unrelated)
$ python3 u16-full-exec-v219.py <fixture>
HEAD=bdff24c shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('72c539d', 'bdff24c', 'YES->NO'), ('189c48e', 'bdff24c', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['72c539d'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 72c539d->bdff24c YES->NO]: APPROVAL_UNBOUND(10) — h digest ∉ blob(approved_at_head:reviewer_ref) (후보 1 · 대응 1) C_R={189c48e}
  · edge#2[r1 189c48e->bdff24c YES->NO]: APPROVAL_UNBOUND(10) — h digest ∉ blob(approved_at_head:reviewer_ref) (후보 1 · 대응 1) C_R={189c48e}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_UNBOUND
reason=전순서 최소 = APPROVAL_UNBOUND(10) @ edge#1[r1 72c539d->bdff24c YES->NO] — h digest ∉ blob(approved_at_head:reviewer_ref) (후보 1 · 대응 1) C_R={189c48e} · 발화 전체=['APPROVAL_UNBOUND']
u16_rc=1
-- ⑰ⓑ g6 단독 뷰 (target=blob(M:ref), c=M, c_APP=A) --
  C_R(target=blob(M))={bdff24c}
  g6_verdict=APPROVAL_ORDER_INVALID

########## 회귀 ⑰ⓒ 양성 — B1·B2 독립 동일 blob, A ⊐ B1 ⇒ NO_ROWS_CLEAR ##########
H0=aa8446d B1=62b57e5 A=5600595 B2=3f6e03a M=79c8de3
  * 79c8de3 M: NO transition
  *   a0e7772 M0: merge B2
  |\  
  | * 3f6e03a B2: independent identical blob
  * | 5600595 A: approval (aah=B1)
  * | 62b57e5 B1: review content (digest)
  |/  
  * aa8446d H0: base (r1=YES; reviewer=unrelated)
$ python3 u16-full-exec-v219.py <fixture>
HEAD=79c8de3 shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('a0e7772', '79c8de3', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['5600595'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 a0e7772->79c8de3 YES->NO]: COVERED by c_APP=5600595 C_R={3f6e03a,62b57e5}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## 회귀 ⑲ digest 선배치 ⇒ APPROVAL_ORDER_INVALID(11) ##########
H0=b58c2ef B=c6e1d8c A=cbff6ce M=ec86b5e
  * ec86b5e M: NO transition
  *   c85fd8b M0: merge B
  |\  
  | * c6e1d8c B: real review content (digest kept)
  * | cbff6ce A: approval row (aah=B) [parallel]
  |/  
  * b58c2ef H0: base (r1=YES; reviewer=carrier)
$ python3 u16-full-exec-v219.py <fixture>
HEAD=ec86b5e shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('c85fd8b', 'ec86b5e', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['cbff6ce'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 c85fd8b->ec86b5e YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={c6e1d8c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={c6e1d8c}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 c85fd8b->ec86b5e YES->NO] — g6 C_R={c6e1d8c} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={c6e1d8c} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1
-- ⑲ v2.14 토큰 기반 C_R 대조 --
  token C_R={b58c2ef}  witness=YES(green — 선배치 우회 통과)

########## 회귀 ⑮ 신규 아티팩트 R ∥ A ⇒ APPROVAL_ORDER_INVALID(11) ##########
H0=cdb5d93 R=5967906 A=23ef3e0 M=f70302b
  * f70302b M: NO transition
  *   9d86e01 M0: merge R
  |\  
  | * 5967906 R: new reviewer artifact
  * | 23ef3e0 A: approval (aah=R) [parallel]
  |/  
  * cdb5d93 H0: base (r1=YES; reviewer=none)
$ python3 u16-full-exec-v219.py <fixture>
HEAD=f70302b shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('9d86e01', 'f70302b', 'YES->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['23ef3e0'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=1 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 9d86e01->f70302b YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={5967906} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={5967906}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_ORDER_INVALID
reason=전순서 최소 = APPROVAL_ORDER_INVALID(11) @ edge#1[r1 9d86e01->f70302b YES->NO] — g6 C_R={5967906} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={5967906} · 발화 전체=['APPROVAL_ORDER_INVALID']
u16_rc=1

########## 회귀 ⑪ transition 명세 불일치 (원장 YES->NO · 실제 파생 간선 ABSENT->NO) ⇒ APPROVAL_MALFORMED(3) ##########
  | ## ledger
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 2c82ee0679b189f48f55cfa1b0ffc2b0d84c3e26 | reviews/review.md | rationale/r1.md
  * c579c23 e: actual edge is ABSENT->NO
  * b6279a5 A: approval claims YES->NO
  * 2c82ee0 H0: r1 absent
$ python3 u16-full-exec-v219.py <fixture>
HEAD=c579c23 shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('b6279a5', 'c579c23', 'ABSENT->NO')]  (edge_seq 표시용 파생=[1] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['b6279a5'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=0 row_id간선=1

[상태 귀속] 계약 U-16-d 순서 적용
  · row[r1/YES->NO]: APPROVAL_MALFORMED(3) — 고아 — 대응 간선 0 (row_id 간선 1 · g1 transition 전건 불일치)
  · edge#1[r1 b6279a5->c579c23 ABSENT->NO]: APPROVAL_MISSING(4) — 덮는 행 부재 (후보 1 · 대응 0)
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=APPROVAL_MALFORMED
reason=전순서 최소 = APPROVAL_MALFORMED(3) @ row[r1/YES->NO] — 고아 — 대응 간선 0 (row_id 간선 1 · g1 transition 전건 불일치) · 발화 전체=['APPROVAL_MALFORMED', 'APPROVAL_MISSING']
u16_rc=1

########## 자인 잔여 — 단일 행이 두 간선을 덮는다 (계약 «닫지 못하는 것» 정직 표기 그대로) ##########
  | ## ledger
  | r1 | YES->NO | 81b7ea747a01020e3e410097df27f5953bf6bfde213bc9dac0d8fe74eb753fc9 | 7d3ede65571b33452e693c3629f556ab2e75f267 | reviews/review.md | rationale/r1.md
  * c471397 e2: YES->NO (no new approval)
  * c97a077 back to YES
  * 60aee50 e1: YES->NO
  * 056137d A: SINGLE approval row
  * 7d3ede6 H0: base (r1=YES; reviewer=full)
$ python3 u16-full-exec-v219.py <fixture>
HEAD=c471397 shallow=False shallow_boundary=[] EVAL_ORDER=precheck-first
NO_rows=['r1']
EDGES(r1)=[('056137d', '60aee50', 'YES->NO'), ('c97a077', 'c471397', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['056137d'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 056137d->60aee50 YES->NO]: COVERED by c_APP=056137d C_R={7d3ede6}
  · edge#2[r1 c97a077->c471397 YES->NO]: COVERED by c_APP=056137d C_R={7d3ede6}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0
```

---
## 5. 관측 보고 · 계약 결함 후보 (고치지 않는다 — `bound_paths` 동결 · 에라타 대상)

### D-1 (실질) — `T-82 ⑱` 의 픽스처 지시 «별개 `row_id`» 가 계약의 나머지 규칙과 충돌한다

- **문언**: 계약 `:2927`(§8 T-82 행) ⑱ — «두 «→NO» 간선을 **«서로 다른» 승인 행**(별개 `row_id`·내용)이 각각 덮고» · **기대 `NO_ROWS_CLEAR` + rc=0**.
- **그런데** `U-16-b` «간선 대응»은 승인 행이 간선 `(p→c)` 를 덮는 조건에 **`g2`**(현재 레지스터에서 재계산한 `row_content_digest` 가 원장 보유값과 일치 · 계약 `U-16-g` (g2))를 넣는다. `row_content_digest` 는 **그 레지스터 행 `r` 의 전 열 파생**(`U-16-f`)이므로 **`row_id` 가 다른 승인 행은 `r` 의 간선을 구조적으로 덮을 수 없다**. 게다가 `U-16-d` `APPROVAL_MALFORMED` 는 «고아 `row_id`»(레지스터에 없는 `row_id`)를 명시 차단한다.
- **실측**(§4 ⑱-2): 문언을 **리터럴로** 구성한 픽스처(`row_id=r1` ∥ `row_id=r1b`)는 `APPROVAL_MALFORMED`(고아 행 `r1b` · `edge#2` 는 `APPROVAL_MISSING`) **+ rc=1** 로 **기대와 정반대**다.
- **문언 정합 해석**(⑱-1: **같은 `row_id` · 서로 다른 내용**[transition·`rationale_ref`]·형제 도입→merge)은 **`NO_ROWS_CLEAR` + rc=0** 으로 기대와 일치한다.
- **처분 제안(에라타)**: ⑱ 의 «(별개 `row_id`·내용)» 을 **«(서로 다른 승인 행 — 같은 `row_id`, 서로 다른 `transition`·근거·내용)»** 로 정정. **v2.19 가 이 행을 «현행 스키마»로 재기술하면서 `edge_seq` 폐지는 반영했지만 식별자 문구는 그대로 옮겨졌다** — S-22(정정을 적는 것과 정정을 전파하는 것은 다른 행위) 형태.

### D-2 (실질) — `U-16-c` 구조 정의가 «진짜 루트»와 «얕은 클론 경계»를 구별하지 않는다 ⇒ `T-82 ⑳ⓑ` 의 전제(«얕은 클론에서 `|c_APP|=0`»)가 리터럴 파생으로는 성립하지 않는다

- **문언**: 계약 `:6917`~`:6920` — `c_APP(a) = { x ⊑ HEAD : a ∈ rows(x:LEDGER) ∧ ∀ p ∈ parents(x): a ∉ rows(p:LEDGER) }` · «**루트(부모 없음)는 둘째 항이 공허참이라 자동 포함**».
- **실측**: `git clone --depth 1` 은 경계 커밋의 부모를 **보고하지 않는다**(`git log --format=%P -1 HEAD` → 공백 · §4 ⑳ⓑ 의 «parents(HEAD) = (객체 실재? )» 라인). 따라서 리터럴 파생에서는 경계 커밋이 **«루트»로 읽혀 «자동 포함»** 되고 **`|c_APP| = 1`** 이 된다 — **fail-open**(얕은 클론이 임의 커밋을 «도입 지점»으로 만들어낸다). 이 판의 **첫 실행에서 실제로 `|c_APP|=1` 이 나왔고**, 그 상태로는 ⑳ⓑ 가 요구한 «크기 0» 이 성립하지 않았다.
- **본 실행기의 독해**: `.git/shallow` 의 경계 커밋 집합을 **분리 관측**해 «부모 집합 «미상»» 으로 읽고 **도입 지점으로 확정하지 않는다**(§1 `shallow_boundary()`·`c_app_set()`). 그러면 `|c_APP| = 0` 이 되어 ⑳ⓑ 전제가 성립한다(§4 실측: `shallow_boundary=['2ce323a']` · `|c_APP|=0(+경계 1)`).
- **처분 제안(에라타)**: `U-16-c` 의 «루트(부모 없음)» 문구에 **«단, 얕은 클론 경계 커밋은 «부모 없음»이 아니라 «부모 미상»이며 도입 지점으로 확정하지 않는다(→ `PROVENANCE_UNVERIFIABLE`)»** 를 병기. **`C_R(c)`(g6)·`D`(U-15-g-1)·`P_first`/`P_last`(U-17 (c)) 가 전부 같은 «∀-부모» 형태**라 **동형 정의 전부에 같은 단서가 필요하다**(S-22 동형 규율 — 계약 자신이 `U-16-c` 에 «세 소비처가 같은 집합 정의를 쓰므로 클래스가 재발하지 않는다»고 적은 그 논거의 연장).

### D-3 (문언 공백 — 대조군 구별력에 직결) — 선-검사 2 의 «얕은 클론» 을 «전역 단축»으로 읽으면 `T-82 ⑳ⓑ` 대조군이 구별력을 잃는다

- 계약 `:7015`~`:7018` 은 선-검사 2 를 «`PROVENANCE_UNVERIFIABLE`(얕은 클론 · `c_APP` 크기 0 · `C_R=∅`)» 로 **세 원천의 합**으로 적는다. 이 중 «얕은 클론»을 **전역 단축**(실행 초입 즉시 방출)으로 구현하면, «g1·g4 먼저» 대조군도 그 단축에 먼저 걸려 **둘 다 `PROVENANCE_UNVERIFIABLE`(2)** 를 내고 **⑳ⓑ 가 두 구현을 구별하지 못한다**.
- 본 실행기는 얕음을 전역 단축으로 두지 않고 **`|c_APP|=0` 이라는 구조 사실로 흘려** 순서만으로 갈리게 했다(§1 주석). 그 결과 실측이 **2 vs 3** 으로 갈렸다. **계약 문언은 두 읽기를 구별하지 않으며, 어느 쪽인지에 따라 ⑳ⓑ 의 판별력이 있거나 없다.**

### D-4 (문언 공백) — 한 간선에 «대응 후보 행»이 여럿일 때의 상태 귀속

- 계약 `:6994`~`:6996` 은 «한 행/간선이 여러 상태를 위반하면 전순서 «번호가 작은» 값을 그 행/간선 상태로 하고, 전역 상태는 모든 행·모든 간선 상태의 전순서 최소» 라 적는다. **한 간선에 후보 행이 여럿이고 각 후보가 서로 다른 규칙에서 탈락할 때** 그 간선의 상태를 어느 후보에서 취하는지는 적혀 있지 않다.
- 본 실행기는 **«대응 후보들의 전순서 최소»** 로 읽었다(독해 선언 · §1). 이번 픽스처들은 간선당 대응 후보가 0 또는 1 이라 이 독해가 결과를 바꾸지 않았다.

### D-5 (독해 선언) — «고아»의 구조 정의

- `U-16-d` `APPROVAL_MALFORMED` 는 «어떤 간선도 덮지 않는 고아 승인 행» 과 «고아 `row_id`» 를 둘 다 담고, `U-16-b` 는 «어떤 간선도 «덮지» 않는 고아 승인 행» 이라 적는다. **«덮지 않는다»를 «전 규칙 탈락»으로 읽으면**, `g6` 에서만 탈락한 정상 행도 «고아»가 되어 `ORDER_INVALID`(11)가 `MALFORMED`(3)로 **오귀속**된다(v2.14 `awk` 교훈과 같은 형태).
- 본 실행기는 **구조적 대응**(같은 `row_id` ∧ `g1` transition 일치인 간선이 **하나도 없음**)만 «고아»로 읽고, 특정 규칙에서 탈락한 행은 **그 규칙 상태로 귀속**한다(v2.15 부속과 같은 독해). 계약이 이 구별을 적지 않았다.

### D-6 (관측 — 결함 아님) — `T-82 ⑳ⓐ` 의 판별력이 **실증**됐다

- 직전 판 부속(`a0201149…`)은 `U16-LEDGER-CHECK.md:37` 에서 «복수면 사전순 최소»를 **계약 밖 자체 선언**으로 두었고, ⑳ⓐ 픽스처(사전순 최소 = **조상** 도입이 되도록 nonce 로 구성)에서 **`NO_ROWS_CLEAR` / rc=0** 을 냈다(§4). 계약이 «조상인 도입을 골라 통과시켜 실패한다»고 적은 그대로이며, **F5 «회피» 판정의 근거가 실행으로 재현**됐다.
- 다만 «사전순 최소»는 커밋 id 가 무작위라 **일반적으로는 통과/차단이 갈린다** — 본 픽스처는 **최악 케이스를 의도적으로 구성**(nonce 루프)한 것이며, 그 사실을 숨기지 않는다. 계약의 주장은 «항상 통과»가 아니라 «통과가 가능하다(선택이 관측자 재량)» 이고 실측은 그것을 지지한다.

### D-7 (관측 — 계약 정직 표기와 정합) — 자인 잔여가 그대로 재현된다

- 단일 승인 행(같은 `row_id`·`transition`·`digest`)의 `c_APP` 가 두 간선 모두의 진 조상이면 **한 행이 두 간선을 덮는다**(§4 «자인 잔여» run: `NO_ROWS_CLEAR`/0). 계약 «닫지 못하는 것» 블록(`U-16-b` 하단)이 명시한 그대로이며 **결함이 아니다** — 계약은 «덮였다»까지만 주장하고 잔여를 `UNCHK-012` 축에 남겼다.

---
## 6. 사후 검증 원문 (repo 무영향 · HEAD 불변 · S-24 재확인 · 픽스처 격리 · 서버 쓰기 0)

`U17-PREVENTION-CHECK-V219.md` §6 과 **같은 실행**의 원문이다(두 증거가 같은 세션·같은 HEAD 에서 산출됐다).

```text
post_utc=2026-08-19T01:15:17Z
$ git -C <repo> rev-parse HEAD
d5a8302a6c33d54e58a0556e59b6c85860059847
$ git -C <repo> status --short
 M uv.lock
?? tools/spikes/
$ git -C <repo> diff --quiet d5a8302a -- <계약>  → rc
rc=0
$ git -C <repo> rev-list --count d5a8302a..HEAD -- <계약>
0
$ git -C <repo> show d5a8302a:<계약> | sed -n '4589,4689p' | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ sed -n '4589,4689p' <워킹트리 계약> | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> reflog -n 3
d5a8302a HEAD@{0}: commit: docs(tos): phase0 completion contract v2.19 — continuity consumer, host-bound queries, structural c_APP, U-16-d total order, dev-plan amendment proposal
8a533c5e HEAD@{1}: commit: docs(reviews): record lane B v2.18 re-adjudication — NOT_PASSED (F1/F2/F4 partial · F3 resolved · F5 evaded · new 2)
81d532ff HEAD@{2}: commit: docs(tos): re-binding (current cycle) — OQ-11 disposition bound to frozen v2.18
--- 서버 설정 무변경 재조회 (GET-only · 진입 시점과 동일한가) ---
$ gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts/branches/main/protection   # utc=2026-08-19T01:15:17Z
{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enab
$ gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts/rules/branches/main   # utc=2026-08-19T01:15:18Z
[]
$ gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts/rulesets   # utc=2026-08-19T01:15:18Z
[{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
$ gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682 --jq '{id,enforcement,created_at,updated_at,bypass_actors}'
{"bypass_actors":[],"created_at":"2026-05-29T15:33:46.629+09:00","enforcement":"disabled","id":17017682,"updated_at":"2026-05-29T15:33:46.662+09:00"}
--- 픽스처 격리 확인 ---
$ ls -d /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84z /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82z
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82z
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84z
$ git -C /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84z/host-base remote -v (원격 URL 은 로컬 config 만 — push/fetch 0)
origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
$ find <scratchpad fixtures> -name .git -maxdepth 3 | wc -l
      20
```

**판독**: HEAD `d5a8302a` 불변 · 계약 워킹트리 = 동결 blob(`git diff --quiet` rc=0) · `d5a8302a..HEAD` 계약 커밋 0 · 하니스 블록 sha256 동결/워킹트리 **byte-동일** · 워킹트리 변경은 실행 «전»부터 있던 `uv.lock`·`tools/spikes/` 뿐 · 픽스처 git 저장소 20개는 전부 scratchpad 하위(`fx82z/*`·`fx84z/*`)다. **U-16 실행은 GitHub 조회를 전혀 하지 않는다**(순수 in-repo) — 위 원문의 `gh api` 호출은 U-17 증거의 사후 재조회분이며 전부 GET 이다.
