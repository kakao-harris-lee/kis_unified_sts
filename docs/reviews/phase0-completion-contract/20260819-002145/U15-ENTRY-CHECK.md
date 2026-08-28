# U15-ENTRY-CHECK — v2.15 T-81 ⑫⑬⑭⑮⑯⑰⑱⑲ + T-84 ①②③④ 실행 transcript (pre-D0-A · U-15-g-4b 8값·전순서 7단 / U-17 예방 통제)

- **목적**: 레인 B v2.14 재심 verdict(`20260819-002145`, NOT_PASSED — F1 U-17 신설·F2 D 집합 카디널리티·
  F3 blob C_R·F4 회피 S-23)이 소비된 스탬프에 귀속되는 이번 사이클 실행 증거. v2.15(동결 커밋
  `11a56d3e`, HEAD=INDEX 커밋 `9c6e0529`)가 신설한 **U-15-g-1/2 판정 우주 = 집합 `D` · `MULTIPLE_INTRODUCTIONS`
  (전순서 2)** · **U-15-g-4 8값/전순서 7단** · **U-17 예방 통제 활성 증거(U-17-b/c/c2)** 의 대조군
  **T-81 ⑫(양성)·⑬·⑭·⑮·⑯·⑰ⓐⓑⓒ·⑱·⑲(gu/gg/uu 3변종) + H6 경계 2종** 및 **T-84 ①·②(i·ii)·③·④ +
  부속(D=∅ · |D|=2 한쪽만 앞섬)** 을 실행하고 U-15-e (1)(2)(3)(4)(4b)(4c)(4c-2)(4d)(5)(6) 결속으로 남긴다.
  ⑫~⑱ 은 v2.15 8값 실행기로 재실행한 회귀 확인이며, ⑲ 와 T-84 가 v2.15 신설분이다.
- **생성 시각**: 2026-08-18T16:43:21Z (UTC) · 실행 시각은 각 절 원문의 `*_utc=` 라인
- **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트(실행)·조립 에이전트(조립 — 실행 출력을 재실행하지 않고 원문 그대로 수록)
- **동결 결속**: 계약 파일 HEAD blob `fc1553fa`(sha256 `9ef00606bce4536302e486b459e2c569dddc04894a304c018557cfff92bd36ce`) ==
  `git show 11a56d3e:` 내용(워킹트리 clean · `git diff --quiet HEAD -- <계약>` 통과). bound_set_digest 현행
  재계산 `c2bdb682bb81d54f323816718f95091337b05f8e498d1cd6f7ec57f1fe8aa87e` ≠ OQ-11 아티팩트 보유값
  `99118a90…`(v2.14 재결속값) → 본 저장소 현행 하니스 산출 `REBINDING_REQUIRED`(재결속 대기) 정합(§7 원문).
- **하니스 결속 (4b)**: §12.3.4-R 블록을 `git show 11a56d3e:<계약> | sed -n '4503,4603p'` 로 추출, 워킹트리
  동일 범위 재추출과 diff 무차이 · `bash -n` 통과 · **sha256 = `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`
  — v2.10~v2.14 하니스와 byte-동일**(v2.15 도 하니스 원문 불변 선언 그대로 — 실측 일치).
- **실행기 결속**: sha256(u15g-exec215.sh) = `0425800012648f31057b9ac787207ff8f80cd225095a509c9bbf43196e16f987` ·
  sha256(u17-exec.sh) = `e1fe7868099a512b5081af6d2e87e8b739feeecbd70720e00856e08246f20141` ·
  sha256(t81-lib215.sh) = `33f2e6959083585282bad56ce651c7f9888440791654f688114c32f582f213ce` ·
  sha256(t81-v215.sh) = `30afe934c98ed533c3c90e8557321abea6aa2b3847b831b2dd129b997374182c` ·
  sha256(t84.sh) = `bce65fdd1178c2a269915bb5a008416d671544a04e28a15af66f6e58dd647784` (원문 전부 §1~§3·§5 수록).
- **(4c-2) 자기 검증**: 이 파일에서 `^R-0 head=[0-9a-f]{40}$` 행 전체 일치로 열리는 run 은 **12 개**이고 각 run 안의
  `^d0a_entry_state=[A-Z_]+$` 상태 라인은 **정확히 1 개**다(하니스 stdout 원문만이 run 을 연다 — 산문·코드 안의
  부분 문자열은 opener 가 아니며 산문 재서술은 백틱 인용으로만 했다). 검증 명령과 출력은 §9 에 수록.
- **결과 요약 — 실행기 stdout·rc 원문 그대로 (해석 아님)**:

### T-81 (`d0a_entry_provenance_state=` · 8값 실행기)

| 변이 | 구성 (worktree 안) | 방출값 | rc | 기대 (§8 T-81 행 · U-15-g-4) | 대조 |
| --- | --- | --- | --- | --- | --- |
| ⑫ 양성 | 2-커밋 전제 → 하니스 `ENTRY_OK`(head H) → 픽스처 t 확정·SHA → 가드 `bash harness && D0A_FIRST(트레일러 3줄)` → d(parent H) → t 를 d 이후 커밋 | `ENTRY_PROVENANCE_CLEAR` | 0 | CLEAR/0 (\|D\|=1 ∧ CORR 한 원소) | **일치** |
| ⑬ HEAD 이동 | 하니스 통과(X) → 우변 실행 전 무관 커밋(Y) → d(parent Y)·트레일러 정상 | `PARENT_MISMATCH` | 1 | PARENT_MISMATCH(4)/≠0 | **일치** |
| ⑭ 비가드 (v2.13 정의·회귀) | 동결 HEAD 에서 하니스·트레일러 없이 d | `ENTRY_TRAILER_MALFORMED` | 1 | §8 ⑭ 행 현행 리터럴 `ENTRY_TRAILER_MALFORMED`(v2.14 에라타 반영) | **일치** (§8-2) |
| ⑮ 전진-머지 (v2.13 정의·회귀) | parent=`cf9b0295`(기존 transcript R-0 head)·트레일러 없음 → 9c6e0529 머지 | `ENTRY_TRAILER_MALFORMED` | 1 | "red"(값 미특정) | **일치(red)** |
| ⑯ 트레일러 없는 착수 | 전제 → ⓐ 하니스 없이 d(트레일러 0줄) → ⓑ parent(d)에서 하니스 재실행 t′ | `ENTRY_TRAILER_MALFORMED` | 1 | ENTRY_TRAILER_MALFORMED(3)/≠0 | **일치** |
| ⑰ⓐ 1줄 누락 | Run 줄 없음 | `ENTRY_TRAILER_MALFORMED` | 1 | (3)/≠0 | **일치** |
| ⑰ⓑ 같은 줄 2회 | Run 줄 2회 | `ENTRY_TRAILER_MALFORMED` | 1 | (3)/≠0 | **일치** |
| ⑰ⓒ SHA256 불일치 | SHA 000… | `ENTRY_TRAILER_MALFORMED` | 1 | (3)/≠0 | **일치** |
| H6-i 인용 run 부재 | Run: 99 | `TRANSCRIPT_MISSING` | 1 | (6)/≠0 | **일치** |
| H6-ii 인용 경로 부재 | 부재 경로 | `TRANSCRIPT_MISSING` | 1 | (6)/≠0 | **일치** |
| ⑱ 인용 run 차단 상태 | 동결 HEAD 하니스 `REBINDING_REQUIRED` 기록 t → d(parent HEAD)·트레일러 정상 | `TRANSCRIPT_NOT_ENTRY_OK` | 1 | (5)/≠0 | **일치** |
| **⑲ gu** 병렬 도입 (guarded ∥ unguarded) | 전제 H → side1 가드+트레일러 d1 · side2 비가드 d2(내용 상이) → 충돌 해소 머지 M | `MULTIPLE_INTRODUCTIONS` | 1 | **§8 ⑲ 정의 그대로** — \|D\|=2 → MULTIPLE_INTRODUCTIONS(2)/≠0 | **일치** |
| **⑲ uu** 병렬 도입 (unguarded ∥ unguarded) | 전제 H → d1·d2 둘 다 비가드(내용 상이) → 충돌 해소 머지 M | `MULTIPLE_INTRODUCTIONS` | 1 | \|D\|=2 → (2)/≠0 | **일치** |
| **⑲ gg** 병렬 도입 (guarded ∥ guarded) | 전제 H → d1·d2 둘 다 가드+동일 트레일러(**byte-동일 내용**) → 무충돌 머지 M | **`ENTRY_PROVENANCE_CLEAR`** | **0** | (U-15-g-2 극성 논증이 회피하려던 «d1·d2 둘 다 guarded 면 CLEAR») | **계약 결함 후보 — §8-1 보고** (`--diff-filter=A` 이력 단순화가 \|D\|=1 로 접음 · `--full-history` 대조 2건) |
| (본 저장소) | 8값 실행기를 본 저장소에 적용 | `NOT_STARTED` | 0 | 비차단·미착수 (\|D\|=0) | **일치** (§7) |

### T-84 (`prevention_control_state=` · U-17 실행기 — 독립 git 픽스처)

| 변이 | 픽스처 (DAG 는 §5) | 방출값 | rc | 기대 (§8 T-84 행 · U-17-c2) | 대조 |
| --- | --- | --- | --- | --- | --- |
| ① 아티팩트 부재 (d 존재) | seed → d | `PREVENTION_ABSENT` | 1 | ABSENT/≠0 | **일치** |
| ②-i countersign 부재 | seed → P(authority·countersign 0줄) → d | `PREVENTION_UNSIGNED` | 1 | UNSIGNED/≠0 | **일치** |
| ②-ii countersign 형식 위반 (빈 값) | seed → P(`operator_countersign:` 빈 값) → d | `PREVENTION_UNSIGNED` | 1 | UNSIGNED/≠0 | **일치** |
| ③ 양성 — P 뒤 d | seed → P(완비) → d | `PREVENTION_ACTIVE` | 0 | ACTIVE/0 | **일치** |
| ④ d 먼저·P 나중 | seed → d → P | `PREVENTION_LATE` | 1 | **[v2.15 마감]** LATE/≠0 (초안은 ACTIVE 를 냈던 구성) | **일치** |
| 부속 D=∅ | seed → P(완비) | `PREVENTION_ACTIVE` | 0 | U-17-c «비교 대상 없음 — 명시 통과» | **일치** |
| 부속 \|D\|=2 · P 가 한쪽만 앞섬 | side1 d(P 이전) ∥ side2 P→d → M1·M2 | `PREVENTION_LATE` | 1 | ∀d∈D: P ⊰ d 위반 → LATE | **일치** |
| (본 저장소) | U-17 실행기를 본 저장소에 적용 | `PREVENTION_ABSENT` | 1 | §8 T-84 행 «현재 평가는 PREVENTION_ABSENT» | **일치** (§7) |

전 T-81 변이 worktree 한정·T-84 는 scratchpad 독립 저장소·본 저장소 D0-A 미착수 불변(§7). 이 transcript 는
본 저장소의 `ENTRY_OK` 나 `ENTRY_PROVENANCE_CLEAR` 나 `PREVENTION_ACTIVE` 를 주장하지 않는다 — 여기 기록된
`ENTRY_OK` run 들은 전부 worktree 모의 커밋 head 라 어떤 실 저장소 d 의 부모와도 일치하지 않는다.

---

## 1. 하니스 명령 원문 (§12.3.4-R v2.15 = `git show 11a56d3e:<계약> | sed -n '4503,4603p'` · 생략 없음)

```bash
#!/usr/bin/env bash
# §12.3.4-R  U-15 pre-D0-A 진입 판정 하니스 (v2.10)
# 산출: stdout 에 d0a_entry_state=<값>.  exit 0 = ENTRY_OK, 그 외 전부 비-0.
# **권위 입력(ART·verdict)은 워킹트리가 아니라 HEAD 커밋 내용에서 읽는다.**
set -u -o pipefail

BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
STAMPS=docs/reviews/phase0-completion-contract

EMITTED=0
emit() {                                  # emit <state> <reason>
  EMITTED=1
  printf 'd0a_entry_state=%s\nreason=%s\n' "$1" "$2"
  if [ "$1" = ENTRY_OK ]; then exit 0; fi
  exit 1
}
trap '[ "$EMITTED" -eq 1 ] || { printf "d0a_entry_state=%s\nreason=%s\n" \
      HARNESS_ABORTED "판정 미산출 상태로 종료"; exit 1; }' EXIT

yaml_list() {   # stdin 에서 <key> 의 리스트 원소를 1행씩
  awk -v k="$1" '
    $0 ~ "^"k":" {f=1; next}
    f && /^[[:space:]]*-[[:space:]]/ {
      sub(/^[[:space:]]*-[[:space:]]*/,""); sub(/[[:space:]]*#.*$/,"");
      sub(/[[:space:]]*$/,""); print; next }
    f && /^[^[:space:]]/ { exit }'
}
yaml_scalar() { # stdin 에서 <key> 의 스칼라
  awk -v k="$1" '$0 ~ "^"k":" {
      sub("^"k":[[:space:]]*",""); sub(/[[:space:]]*#.*$/,"");
      sub(/[[:space:]]*$/,""); print; exit }'
}

# ── R-0  실행 시점 결속 + **권위 입력 전부**의 동결 확인
HEAD_SHA=$(git rev-parse HEAD) || emit HARNESS_ABORTED "git rev-parse 실패"
printf 'R-0 head=%s\n' "$HEAD_SHA"
for f in "$BP1" "$BP2"; do
  [ -f "$f" ] || emit HARNESS_ABORTED "입력 부재: $f"
done
DIRTY=$(git status --porcelain -- "$BP1" "$BP2" "$ART" "$STAMPS") \
  || emit HARNESS_ABORTED "git status 실패"
[ -z "$DIRTY" ] || emit FREEZE_VIOLATED "권위 입력 미커밋 변경: $(echo "$DIRTY" | tr '\n' ';')"

# ── R-1  bound_paths 집합 == 계약이 요구하는 그 둘            [U-12 (iii)]
ABODY=$(git show "HEAD:$ART" 2>/dev/null) \
  || emit REBINDING_REQUIRED "아티팩트가 HEAD 에 부재 — U-12 (i)"
WANT=$(printf '%s\n%s\n' "$BP1" "$BP2" | LC_ALL=C sort)
GOT=$(printf '%s\n' "$ABODY" | yaml_list bound_paths | LC_ALL=C sort) \
  || emit HARNESS_ABORTED "yaml_list 실패 — awk 부재·파일 파손"
[ "$GOT" = "$WANT" ] || emit REBINDING_REQUIRED "bound_paths 집합 불일치"

# ── R-2  bound_set_digest 재계산 == 보유값 · disposition 어휘  [U-12 (iv)(ii)]
CALC=$(printf '%s\0' "$BP1" "$BP2" | LC_ALL=C sort -z -u \
       | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1) \
  || emit HARNESS_ABORTED "digest 재계산 실패"
HELD=$(printf '%s\n' "$ABODY" | yaml_scalar bound_set_digest) \
  || emit HARNESS_ABORTED "yaml_scalar 실패 — awk 부재"
[ -n "$HELD" ] || emit REBINDING_REQUIRED "bound_set_digest 미기재"
[ "$CALC" = "$HELD" ] || emit REBINDING_REQUIRED "bound_set_digest 불일치"
DISP=$(printf '%s\n' "$ABODY" | yaml_scalar disposition) \
  || emit HARNESS_ABORTED "yaml_scalar 실패"
case "$DISP" in
  RESOLVED_MAPPING_APPROVED|RESOLVED_MAPPING_REJECTED|DEFERRED_WITH_SCOPE|REFUSED) ;;
  *) emit REBINDING_REQUIRED "disposition 어휘 밖: '$DISP'" ;;
esac

# ── R-3  최신 verdict 스탬프 — **우주는 HEAD 트리다**(워킹트리 나열 아님)
VD=$(git ls-tree --name-only HEAD "$STAMPS/" 2>/dev/null \
     | grep -E '/[0-9]{8}-[0-9]{6}$' | LC_ALL=C sort | tail -1) || VD=""
[ -n "$VD" ] || emit APPROVAL_ABSENT "HEAD 에 verdict 스탬프 없음"
VBODY=$(git show "HEAD:$VD/verdict.md" 2>/dev/null) \
  || emit APPROVAL_ABSENT "verdict.md 가 HEAD 에 부재: $VD"
printf 'R-3 verdict=%s\n' "$VD"

# ── R-4  심판 계열·판정 어휘                                   [U-15-b (1)]
ADJ=$(printf '%s\n' "$VBODY" | yaml_scalar adjudicator) || emit HARNESS_ABORTED "yaml_scalar 실패"
VER=$(printf '%s\n' "$VBODY" | yaml_scalar verdict)     || emit HARNESS_ABORTED "yaml_scalar 실패"
{ [ "$ADJ" = codex ] && [ "$VER" = approve ]; } \
  || emit APPROVAL_NOT_APPROVE "adjudicator='$ADJ' verdict='$VER'"

# ── R-5  심사 범위 == 요구 결속 경로 집합                        [U-15-b (2)]
RGOT=$(printf '%s\n' "$VBODY" | yaml_list reviewed_plan_paths | LC_ALL=C sort) \
  || emit HARNESS_ABORTED "yaml_list 실패"
[ "$RGOT" = "$WANT" ] || emit APPROVAL_SCOPE_MISMATCH "reviewed_plan_paths 불일치"

# ── R-6  reviewed_at_head 가 HEAD 의 조상인가                    [U-15-b (3)]
RH=$(printf '%s\n' "$VBODY" | yaml_scalar reviewed_at_head) || emit HARNESS_ABORTED "yaml_scalar 실패"
[ -n "$RH" ] || emit APPROVAL_PROVENANCE_UNVERIFIABLE "reviewed_at_head 미기재"
git cat-file -e "$RH^{commit}" 2>/dev/null \
  || emit APPROVAL_PROVENANCE_UNVERIFIABLE "커밋 부재 — 얕은 클론·이력 재작성"
git merge-base --is-ancestor "$RH" HEAD \
  || emit APPROVAL_PROVENANCE_UNVERIFIABLE "reviewed_at_head 가 HEAD 의 조상이 아님"

# ── R-7  승인 이후 bound_paths 를 건드린 커밋 — 공집합인가        [U-15-b (4)]
TOUCH=$(git log --format=%H "$RH..HEAD" -- "$BP1" "$BP2") \
  || emit HARNESS_ABORTED "git log 실패"
[ -z "$TOUCH" ] || emit APPROVAL_STALE "승인 이후 변경: $(echo "$TOUCH" | tr '\n' ' ')"

emit ENTRY_OK "R-0~R-7 전부 기대와 일치"
```

---

## 2. 손 실행기 (U-15-g-4b 사양 · v2.15 8값) — 원문 + 독해 선언

**sha256(u15g-exec215.sh) = `0425800012648f31057b9ac787207ff8f80cd225095a509c9bbf43196e16f987`** (v2.14 판 `62338bdb…` 대비 델타 = U-15-g-1/2 집합 `D` 카디널리티 분기 + 전순서 재번호)

독해 선언(계약 정본 기준 · 참고 구현은 참고만):
- **U-15-g-1 판정 우주**: `D` = 계약 리터럴 명령 `git log --format=%H --diff-filter=A -- config/tos_completion.yaml`
  의 출력 **집합** 그대로 — 계약이 적지 않은 플래그(`--full-history` 등)를 **더하지 않았다**(증거 산출기는
  계약보다 느슨해도 안 되지만 계약과 다른 술어를 실행해도 안 된다 — S-15/U-15-g-4b). 그 결과가 ⑲ gg 의 관측(§8-1)이다.
- **U-15-g-2**: `|D|=0` → `NOT_STARTED`(exit 0) · `|D|>1` → `MULTIPLE_INTRODUCTIONS`(exit 1) — **CORR 평가 이전**에 방출.
- **(4c)(4c-2) run 경계**: «`R-0 head=<40hex>` 리터럴 라인이 run 을 연다»를 **행 전체 일치**(`^R-0 head=[0-9a-f]{40}$`)로
  읽는다 — 하니스 `printf 'R-0 head=%s\n'` 가 방출하는 그 행이며, 산문·코드 안의 부분 문자열은 opener 가 아니다.
  상태 라인도 `^d0a_entry_state=[A-Z_]+$` 행 전체. `k` = 1-기반 출현 순서 · run 범위 = 다음 opener 직전까지 ·
  상태 라인 0/2+ = 형식 미충족(→ 6).
- **평가 순서 vs 전순서 7단**: 1 UNVERIFIABLE · 2 MULTIPLE_INTRODUCTIONS · 3 TRAILER_MALFORMED · 4 PARENT_MISMATCH ·
  5 NOT_ENTRY_OK · 6 MISSING · 7 CLEAR. 4·5 는 «인용 run 이 실재»를 전제하므로 인용 대상 부재(경로·run·형식)는
  4·5 앞에서 6 으로 방출한다(H6: 경로 부재는 SHA 계산 불가 → 6). 여러 값이 동시 성립하면 전순서 그대로(⑬ 은
  트레일러 정상이므로 3 이 아닌 4).
- 단일 성공 경로 2곳(`ENTRY_PROVENANCE_CLEAR`·`NOT_STARTED` → exit 0) · 그 외 전부 exit 1 · `trap EXIT` 가 판정 없이
  끝나는 경로를 `PROVENANCE_UNVERIFIABLE` 로 폐쇄 · RUNS 는 (파일, run) 쌍.

```bash
#!/usr/bin/env bash
# U-15-g «손 실행기» — v2.15 U-15-g-4b 사양 (계약 11a56d3e §12.3.4 U-15-g-1/2/3/4/4b·U-15-f-5·U-15-e (4c)(4c-2)) — 8값·전순서 7단
# 산출: stdout 에 d0a_entry_provenance_state=<값> 한 줄 + reason=.  exit 0 = ENTRY_PROVENANCE_CLEAR|NOT_STARTED, 그 외 비-0.
# 사용: bash u15g-exec.sh <repo-dir>
set -u -o pipefail
EMITTED=0
emit() {                                    # emit <state> <reason>
  EMITTED=1
  printf 'd0a_entry_provenance_state=%s\nreason=%s\n' "$1" "$2"
  case "$1" in ENTRY_PROVENANCE_CLEAR|NOT_STARTED) exit 0 ;; esac
  exit 1
}
trap '[ "$EMITTED" -eq 1 ] || { printf "d0a_entry_provenance_state=%s\nreason=%s\n" \
      PROVENANCE_UNVERIFIABLE "판정 미산출 상태로 종료"; exit 1; }' EXIT

cd "${1:?repo-dir}" || emit PROVENANCE_UNVERIFIABLE "repo 진입 실패"
CFG=config/tos_completion.yaml

# ── 전순서 1  이력 파생 불가
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || emit PROVENANCE_UNVERIFIABLE "git 저장소 아님"
[ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "false" ] \
  || emit PROVENANCE_UNVERIFIABLE "얕은 클론 또는 판별 불가"

# ── U-15-g-1/2  판정 우주 = D0A-FIRST 도입 커밋의 «집합» D · 전순서 2 MULTIPLE_INTRODUCTIONS
D=$(git log --format=%H --diff-filter=A -- "$CFG" 2>/dev/null) || emit PROVENANCE_UNVERIFIABLE "git log 실패"
ND=$(printf '%s\n' "$D" | grep -c .); printf 'D=%s\n' "$(printf '%s\n' "$D" | tr '\n' ' ')"
[ "$ND" -gt 0 ] || emit NOT_STARTED "|D| = 0"
[ "$ND" -eq 1 ] || emit MULTIPLE_INTRODUCTIONS "|D| = $ND — «최초»가 유일하지 않음"
D=$(printf '%s\n' "$D" | tail -1)          # |D|=1 확정
PARENT=$(git log --format=%P -1 "$D" | awk '{print $1}')
MSG=$(git log --format=%B -1 "$D")
printf 'd=%s\nparent(d)=%s\n' "$D" "$PARENT"

# ── 전순서 3  트레일러 (U-15-f-5: 3줄 각각 정확히 1회 · 형식 · SHA256)
np=$(printf '%s\n' "$MSG" | grep -c '^Entry-Transcript:')
nr=$(printf '%s\n' "$MSG" | grep -c '^Entry-Transcript-Run:')
ns=$(printf '%s\n' "$MSG" | grep -c '^Entry-Transcript-SHA256:')
{ [ "$np" = 1 ] && [ "$nr" = 1 ] && [ "$ns" = 1 ]; } \
  || emit ENTRY_TRAILER_MALFORMED "트레일러 출현 횟수 path=$np run=$nr sha=$ns (각 1 요구)"
TP=$(printf '%s\n' "$MSG" | sed -n 's/^Entry-Transcript:[[:space:]]*//p')
TR=$(printf '%s\n' "$MSG" | sed -n 's/^Entry-Transcript-Run:[[:space:]]*//p')
TS=$(printf '%s\n' "$MSG" | sed -n 's/^Entry-Transcript-SHA256:[[:space:]]*//p')
case "$TR" in ''|*[!0-9]*) emit ENTRY_TRAILER_MALFORMED "Run 이 양의 정수가 아님: '$TR'" ;; esac
[ "$TR" -ge 1 ] || emit ENTRY_TRAILER_MALFORMED "Run 이 1 미만: $TR"
printf '%s' "$TS" | grep -Eq '^[0-9a-f]{64}$' || emit ENTRY_TRAILER_MALFORMED "SHA256 형식 오류: '$TS'"
printf 'trailer: path=%s run=%s sha=%s\n' "$TP" "$TR" "$TS"

# ── 전순서 6 (H6 경계)  인용 경로 부재 → SHA 계산 불가 → TRANSCRIPT_MISSING
[ -f "$TP" ] || emit TRANSCRIPT_MISSING "인용 transcript 경로 부재: $TP"
ACT=$(shasum -a 256 "$TP" | cut -d' ' -f1)
[ "$ACT" = "$TS" ] || emit ENTRY_TRAILER_MALFORMED "SHA256 불일치: 실제=$ACT"

# ── (4c)(4c-2)  run 경계: `R-0 head=<40hex>` 리터럴 라인(행 전체)이 run 을 연다 · k = 1-기반 출현 순서
#     run 범위 = 그 라인부터 다음 opener 직전 · 안의 `d0a_entry_state=<값>` 리터럴 라인이 상태 (정확히 1개)
read -r HEAD_K NSTATE ST TOTAL <<EOF
$(awk -v K="$TR" '
  /^R-0 head=[0-9a-f]{40}$/ { k++; inr=(k==K); if(inr){h=substr($0,10,40)}; next }
  inr && /^d0a_entry_state=[A-Z_]+$/ { n++; if(n==1) st=substr($0,17) }
  END { print (h==""?"NONE":h), n+0, (st==""?"NONE":st), k+0 }' "$TP")
EOF
printf 'transcript runs=%s cited_run=%s head=%s nstate=%s state=%s\n' "$TOTAL" "$TR" "$HEAD_K" "$NSTATE" "$ST"
[ "$HEAD_K" != NONE ] || emit TRANSCRIPT_MISSING "인용 run $TR 부재 (transcript 내 run 수=$TOTAL)"
[ "$NSTATE" = 1 ]     || emit TRANSCRIPT_MISSING "run $TR 형식 미충족: 상태 라인 $NSTATE 개 (정확히 1 요구)"

# ── 전순서 4  부모 결속 (U-15-f-4)
[ "$HEAD_K" = "$PARENT" ] || emit PARENT_MISMATCH "run $TR head=$HEAD_K ≠ parent(d)=$PARENT"

# ── 전순서 5  인용 run 의 판정값
[ "$ST" = ENTRY_OK ] || emit TRANSCRIPT_NOT_ENTRY_OK "run $TR 상태=$ST"

# ── 전순서 7
emit ENTRY_PROVENANCE_CLEAR "|CORR(d)|=1 — (t=$TP,k=$TR)"
```

---

## 3. 실행 절차 원문 (공통 lib + 드라이버) — 저작 선언

**sha256(t81-lib215.sh) = `33f2e6959083585282bad56ce651c7f9888440791654f688114c32f582f213ce` · sha256(t81-v215.sh) = `30afe934c98ed533c3c90e8557321abea6aa2b3847b831b2dd129b997374182c`**

- 전제 모의는 «전제 차이» 표 post-freeze **2-커밋**(C1 SIMULATED 재결속 · C2 SIMULATED approve, 스탬프
  `29991231-235959`). D0A-FIRST 트레일러 형태·가드 형태·G-부모 대조는 §12.3.4-G 블록 원문 차용(v2.14 와 동일).
- **픽스처 transcript t 의 위치**: 하니스 R-0 은 `$STAMPS` 하위 미커밋 파일을 `??` 로 잡아 `FREEZE_VIOLATED` 를
  낸다(v2.14 transcript §5 프로브 실측·불변). 따라서 저작 측을 scratchpad `author-side-215/` 로, 가드를 detached
  worktree 로 두고, **d 이후에** t 를 추적 경로(`T_PATH` = 이 파일의 경로)에 커밋(정직 체인 `H → d → commit(t)`)해
  실행기가 읽게 했다. 픽스처 t 는 U-15-e (4c)(4c-2) 형식이며 §6 에 원문·sha 수록.
- **⑲ 3변종 저작 주의(드라이버 주석 그대로)**: 두 side 의 도입은 브랜치 ref 를 만들지 않고 detached 로 커밋했다
  (worktree 는 ref 를 본 저장소와 공유한다 — 1차 실행이 만든 `br*`/`side*` 브랜치 오염은 정리 후 재실행, §7 에
  `wc -l = 0` 실측). `sleep 1` 은 동일 트리·부모·메시지의 두 커밋이 같은 초에 만들어지면 **같은 객체**가 되는
  것을 막는다(gg 1차 실측). gg 는 두 side 의 파일 내용이 byte-동일이라 무충돌 머지, gu/uu 는 내용 상이라
  add/add 충돌 → 해소 커밋.

```bash
# t81-lib215.sh — v2.15 T-81 변이 공통 (source 용). 전부 scratchpad 하위 detached worktree 안에서만 동작.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
REPO=/Users/harris/Development/private/kis_unified_sts
HARNESS="$SP/harness215.sh"
EXEC="$SP/u15g-exec215.sh"
BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
T_PATH=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md   # 추적 경로 (픽스처 t 의 경로)
AUTHOR_SIDE="$SP/author-side-215"   # §12.3.4-G 의 $REPO(저작 측) 대역 — 가드 worktree 밖에서 t 를 확정한다

wt_new() {   # wt_new <name> [<commit>]  → detached worktree 생성, 경로 출력
  local d="$SP/wt/$1" c="${2:-HEAD}"
  git -C "$REPO" worktree add --detach "$d" "$c" >/dev/null 2>&1 || return 1
  printf '%s\n' "$d"
}
wt_rm() { git -C "$REPO" worktree remove --force "$1"; }

premise() {  # premise <wt>  — post-freeze 2-커밋 모의 («전제 차이» 표): C1 SIMULATED 재결속 · C2 SIMULATED approve
  local WT="$1" NEW
  NEW=$(cd "$WT" && printf '%s\0' "$BP1" "$BP2" | LC_ALL=C sort -z -u | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
  (cd "$WT" && perl -pi -e "s/^bound_set_digest:.*/bound_set_digest: $NEW/" "$ART")
  git -C "$WT" commit -q -am 'C1: SIMULATED rebinding (test fixture only)'
  local MOCK="$WT/docs/reviews/phase0-completion-contract/29991231-235959"
  mkdir -p "$MOCK"
  cat > "$MOCK/verdict.md" <<EOF
adjudicator: codex
verdict: approve
reviewed_at_head: $(git -C "$WT" rev-parse HEAD)
reviewed_plan_paths:
  - $BP1
  - $BP2
EOF
  git -C "$WT" add -A && git -C "$WT" commit -q -m 'C2: SIMULATED approve verdict (test fixture only)'
  git -C "$WT" log --oneline -3
}

fixture_transcript() {  # fixture_transcript <harness-out-file> <out-path>  — U-15-e 형식(최소) 픽스처 t. run 은 하니스 출력 원문만이 연다
  local OUT="$1" DST="$2"
  mkdir -p "$(dirname "$DST")"
  {
    echo '# U15-ENTRY-CHECK — SIMULATED fixture transcript (test fixture only · worktree-scoped)'
    echo '- harness: §12.3.4-R (11a56d3e) sha256 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
    echo "- generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo '- runs: 아래 각 run 은 `R-0 head=<40hex>` 리터럴 라인으로 열리고 `d0a_entry_state=` 라인 정확히 1개를 가진다 (U-15-e (4c)(4c-2))'
    echo
    echo '## run 1'
    echo '$ bash harness.sh; echo "harness_rc=$?"'
    cat "$OUT"
  } > "$DST"
}

d0a_first_with_trailer() {  # d0a_first_with_trailer <T_PATH> <RUN> <SHA>  → 문자열 (eval 용). §12.3.4-G 원문 그대로
  printf '%s' 'printf "# D0-A first artifact\n" > config/tos_completion.yaml \
           && git add config/tos_completion.yaml \
           && git commit -q -m "D0-A: introduce config/tos_completion.yaml" \
                         -m "Entry-Transcript: '"$1"'" \
                         -m "Entry-Transcript-Run: '"$2"'" \
                         -m "Entry-Transcript-SHA256: '"$3"'"'
}

bring_t_after_d() {  # bring_t_after_d <wt> <fixture-file>  — 정직 체인 H → d → commit(t): d 이후에 t 를 추적 경로에 커밋
  local WT="$1" SRC="$2"
  mkdir -p "$WT/$(dirname "$T_PATH")"
  cp "$SRC" "$WT/$T_PATH"
  git -C "$WT" add "$T_PATH" && git -C "$WT" commit -q -m 'SIMULATED: transcript commit after d (H -> d -> T chain; test fixture only)'
}

run_exec() {  # run_exec <wt>  — 손 실행기 실행 + rc 원문
  bash "$EXEC" "$1"; echo "exec_rc=$?"
}
```

```bash
#!/usr/bin/env bash
# t81-v215.sh — v2.15 T-81 변이 ⑫⑬⑭⑮⑯⑰ⓐⓑⓒ⑱⑲(3변종) + H6 경계 실행 드라이버 (8값 실행기).
# 각 변이 = 독립 detached worktree(scratchpad 하위) · 픽스처 t 는 저작 측($AUTHOR_SIDE)에서 확정 후 필요 시 d 이후 커밋.
source "$(dirname "$0")/t81-lib215.sh"
mkdir -p "$SP/wt" "$AUTHOR_SIDE"
sec() { printf '\n########## %s ##########\n' "$*"; }
hd()  { git -C "$1" rev-parse HEAD; }

# ───────────────────────── ⑫ 양성 — §12.3.4-G 양성 흐름 (트레일러 포함) ─────────────────────────
sec "T-81 (12) positive — guard with trailer"
WT=$(wt_new m12); echo "WT=$WT"; premise "$WT"
H=$(hd "$WT"); echo "H(전제 충족 HEAD)=$H"
# 하니스 1회 실행 → 그 출력으로 저작 측에 픽스처 t 확정 (가드 worktree 는 clean 유지)
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m12-harness-out.txt" 2>&1
cat "$AUTHOR_SIDE/m12-harness-out.txt"
fixture_transcript "$AUTHOR_SIDE/m12-harness-out.txt" "$AUTHOR_SIDE/m12-t.md"
T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/m12-t.md" | cut -d' ' -f1); echo "T_SHA=$T_SHA"
D0A_FIRST=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
# 가드 (§12.3.4-G): 좌변 하니스 재실행(clean worktree) && 우변 D0A-FIRST(트레일러 포함)
( cd "$WT" && bash "$HARNESS" && eval "$D0A_FIRST" ); echo "guard_rc=$?"
git -C "$WT" log --oneline --diff-filter=A -- config/tos_completion.yaml
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D"; echo "parent(d)=$(git -C "$WT" log --format=%P -1 "$D")"
git -C "$WT" log --format=%B -1 "$D"
bring_t_after_d "$WT" "$AUTHOR_SIDE/m12-t.md"
git -C "$WT" log --oneline -3
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑬ HEAD 이동 → PARENT_MISMATCH ─────────────────────────
sec "T-81 (13) HEAD move between harness pass and D0A-FIRST"
WT=$(wt_new m13); echo "WT=$WT"; premise "$WT" >/dev/null
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m13-harness-out.txt" 2>&1
cat "$AUTHOR_SIDE/m13-harness-out.txt"
X=$(grep '^R-0 head=' "$AUTHOR_SIDE/m13-harness-out.txt" | cut -d= -f2); echo "X(하니스 평가 HEAD)=$X"
fixture_transcript "$AUTHOR_SIDE/m13-harness-out.txt" "$AUTHOR_SIDE/m13-t.md"
T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/m13-t.md" | cut -d' ' -f1)
D0A_FIRST=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
# 가드 좌변 통과 → 우변 실행 «전에» 무관 커밋으로 HEAD 이동 → D0A-FIRST
( cd "$WT" && bash "$HARNESS" && { git commit -q --allow-empty -m 'SIMULATED unrelated commit: HEAD move (test fixture only)'; eval "$D0A_FIRST"; } ); echo "guard_rc=$?"
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D"; echo "parent(d)=$(git -C "$WT" log --format=%P -1 "$D")  X=$X"
bring_t_after_d "$WT" "$AUTHOR_SIDE/m13-t.md"
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑭ 비가드 착수 (v2.13 정의 그대로 — 전제 없음·하니스 없음·트레일러 없음) ─────────────────────────
sec "T-81 (14) unguarded start at frozen HEAD, no trailer (v2.13 def re-run on v2.14 executor)"
WT=$(wt_new m14); echo "WT=$WT"; echo "HEAD=$(hd "$WT")"
( cd "$WT" && printf "# D0-A first artifact\n" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m "D0-A: introduce config/tos_completion.yaml" ); echo "commit_rc=$?"
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D  parent(d)=$(git -C "$WT" log --format=%P -1 "$D")"
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑮ 전진-머지 우회 (v2.13 정의 — parent = 기존 transcript 20260815-092111 의 R-0 head cf9b0295) ─────────────────────────
sec "T-81 (15) forward-merge bypass (v2.13 def re-run on v2.14 executor)"
WT=$(wt_new m15 cf9b0295ac574b0cb022dd743e42c7aac5113aca); echo "WT=$WT"; echo "HEAD=$(hd "$WT")"
( cd "$WT" && printf "# D0-A first artifact\n" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m "D0-A: introduce config/tos_completion.yaml" )
git -C "$WT" merge -q --no-edit 9c6e052913d907c371efa200f1eaf98b84567345 && git -C "$WT" log --oneline -3
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D  parent(d)=$(git -C "$WT" log --format=%P -1 "$D")"
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑯ 트레일러 없는 착수 (ⓐ 하니스 없이 d · ⓑ parent(d) 에서 하니스 재실행 → t′) ─────────────────────────
sec "T-81 (16) trailer-less start; then harness re-run at parent(d) -> t'"
WT=$(wt_new m16); echo "WT=$WT"; premise "$WT" >/dev/null
H=$(hd "$WT"); echo "H=$H"
( cd "$WT" && printf "# D0-A first artifact\n" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m "D0-A: introduce config/tos_completion.yaml" )   # ⓐ 하니스 없이·트레일러 없이
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D  parent(d)=$(git -C "$WT" log --format=%P -1 "$D")"
git -C "$WT" checkout -q "$H"                                                                     # ⓑ parent(d) 로 이동해 하니스 재실행
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m16-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/m16-harness-out.txt"
fixture_transcript "$AUTHOR_SIDE/m16-harness-out.txt" "$AUTHOR_SIDE/m16-tprime.md"; echo "t' sha=$(shasum -a 256 "$AUTHOR_SIDE/m16-tprime.md" | cut -d' ' -f1)"
git -C "$WT" checkout -q "$D"; bring_t_after_d "$WT" "$AUTHOR_SIDE/m16-tprime.md"                # d 로 복귀 · t′ 를 d 이후 커밋 (d 에는 트레일러 없음)
git -C "$WT" log --oneline -3
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑰ 트레일러 이상 ⓐ 1줄 누락 / ⓑ 같은 줄 2회 / ⓒ SHA256 불일치 · H6 경계 2종 ─────────────────────────
sec "T-81 (17) trailer malformed a/b/c + H6 boundary"
WT=$(wt_new m17); echo "WT=$WT"; premise "$WT" >/dev/null
H=$(hd "$WT"); echo "H=$H"
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m17-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/m17-harness-out.txt"
fixture_transcript "$AUTHOR_SIDE/m17-harness-out.txt" "$AUTHOR_SIDE/m17-t.md"
T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/m17-t.md" | cut -d' ' -f1); echo "T_SHA=$T_SHA"
variant() {  # variant <label> <extra -m args...>  — H 에서 d 커밋(트레일러 변형) → t 커밋 → 실행기 → H 로 복귀
  local label="$1"; shift
  echo "---- (17)$label ----"
  git -C "$WT" checkout -q "$H"
  ( cd "$WT" && printf "# D0-A first artifact\n" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m "D0-A: introduce config/tos_completion.yaml" "$@" )
  D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D  parent(d)=$(git -C "$WT" log --format=%P -1 "$D")"
  git -C "$WT" log --format=%B -1 "$D" | sed 's/^/  msg| /'
  bring_t_after_d "$WT" "$AUTHOR_SIDE/m17-t.md"
  echo "-- executor --"; run_exec "$WT"
}
variant "a: Run line missing"      -m "Entry-Transcript: $T_PATH" -m "Entry-Transcript-SHA256: $T_SHA"
variant "b: Run line twice"        -m "Entry-Transcript: $T_PATH" -m "Entry-Transcript-Run: 1" -m "Entry-Transcript-Run: 1" -m "Entry-Transcript-SHA256: $T_SHA"
variant "c: SHA256 mismatch"       -m "Entry-Transcript: $T_PATH" -m "Entry-Transcript-Run: 1" -m "Entry-Transcript-SHA256: 0000000000000000000000000000000000000000000000000000000000000000"
variant "H6-i: cited run absent"   -m "Entry-Transcript: $T_PATH" -m "Entry-Transcript-Run: 99" -m "Entry-Transcript-SHA256: $T_SHA"
variant "H6-ii: cited path absent" -m "Entry-Transcript: docs/reviews/phase0-completion-contract/20260818-224729/NO-SUCH-FILE.md" -m "Entry-Transcript-Run: 1" -m "Entry-Transcript-SHA256: $T_SHA"
wt_rm "$WT"

# ───────────────────────── ⑱ 인용 run 의 상태 ≠ ENTRY_OK (트레일러 정상·head 일치) ─────────────────────────
sec "T-81 (18) cited run recorded a blocked state"
WT=$(wt_new m18); echo "WT=$WT"; H=$(hd "$WT"); echo "H(동결 HEAD·전제 없음)=$H"
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m18-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/m18-harness-out.txt"
fixture_transcript "$AUTHOR_SIDE/m18-harness-out.txt" "$AUTHOR_SIDE/m18-t.md"
T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/m18-t.md" | cut -d' ' -f1); echo "T_SHA=$T_SHA"
D0A_FIRST=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
( cd "$WT" && eval "$D0A_FIRST" ); echo "commit_rc=$?"          # 가드 없이 직접 커밋(가드였다면 좌변이 막았을 상태) — 트레일러는 정상
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D  parent(d)=$(git -C "$WT" log --format=%P -1 "$D")"
bring_t_after_d "$WT" "$AUTHOR_SIDE/m18-t.md"
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"


# ───────────────────────── ⑲ 병렬 도입 머지 — |D|=2 → MULTIPLE_INTRODUCTIONS (guarded∥unguarded · guarded∥guarded · unguarded∥unguarded) ─────────────────────────
par19() {  # par19 <label> <mode1> <mode2>   mode ∈ {guarded,unguarded}
  local label="$1" m1="$2" m2="$3"
  sec "T-81 (19) parallel introduction — $label"
  WT=$(wt_new "m19-$label"); echo "WT=$WT"; premise "$WT" >/dev/null
  local H; H=$(hd "$WT"); echo "H(전제 충족 HEAD)=$H"
  (cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m19-$label-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/m19-$label-harness-out.txt"
  fixture_transcript "$AUTHOR_SIDE/m19-$label-harness-out.txt" "$AUTHOR_SIDE/m19-$label-t.md"
  local T_SHA; T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/m19-$label-t.md" | cut -d' ' -f1)
  local D0A_G; D0A_G=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
  intro() {  # intro <label> <mode> — H 에서 «detached» 로 config 도입 (브랜치 ref 를 만들지 않는다 — worktree 는 ref 를 본 저장소와 공유한다)
    git -C "$WT" checkout -q --detach "$H"
    if [ "$2" = guarded ]; then ( cd "$WT" && bash "$HARNESS" >/dev/null && eval "$D0A_G" ); echo "$1 guard_rc=$?"
    else ( cd "$WT" && printf "# D0-A first artifact (%s)\n" "$1" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m "D0-A: introduce config/tos_completion.yaml" ); echo "$1 commit_rc=$?"; fi
    git -C "$WT" rev-parse HEAD
  }
  local B1 B2; B1=$(intro side1 "$m1" | tail -1); sleep 1; B2=$(intro side2 "$m2" | tail -1); echo "side1=$B1 side2=$B2"   # sleep: 동일 트리·부모·메시지의 두 커밋이 같은 초에 만들어지면 같은 객체가 된다(gg 실측) — 실제 병렬 브랜치는 시각이 다르다
  git -C "$WT" checkout -q --detach "$B1"
  git -C "$WT" merge -q --no-ff -m 'M: merge side2 into side1 (SIMULATED test fixture)' "$B2" 2>/dev/null \
    || { (cd "$WT" && printf "# D0-A first artifact (merge-resolved)\n" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m 'M: merge side2 into side1 (conflict resolved; SIMULATED test fixture)'); }
  git -C "$WT" log --graph --oneline -6
  echo "D(--diff-filter=A · 계약 U-15-g-1 명령 그대로)="; git -C "$WT" log --format='  %h %s' --diff-filter=A -- config/tos_completion.yaml
  echo "[대조] --full-history --diff-filter=A (이력 단순화 해제) ="; git -C "$WT" log --full-history --format='  %h %s' --diff-filter=A -- config/tos_completion.yaml
  bring_t_after_d "$WT" "$AUTHOR_SIDE/m19-$label-t.md"
  echo "-- executor --"; run_exec "$WT"
  wt_rm "$WT"
}
par19 gu guarded unguarded
par19 gg guarded guarded
par19 uu unguarded unguarded

sec "worktree list (잔여 확인)"
git -C "$REPO" worktree list
```

---

## 4. 실행 기록 — T-81 (명령·출력 원문 전문 — 각 변이 worktree · 하니스/실행기 stdout 그대로)

```text
t81_v215_utc=2026-08-18T16:23:52Z  base_head=9c6e052913d907c371efa200f1eaf98b84567345
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-v215.sh

########## T-81 (12) positive — guard with trailer ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m12
4bb9a0a9 C2: SIMULATED approve verdict (test fixture only)
161d3943 C1: SIMULATED rebinding (test fixture only)
9c6e0529 docs(plans): INDEX — phase0 completion contract v2.15 frozen (11a56d3e)
H(전제 충족 HEAD)=4bb9a0a97bf3464998290cf1ab024e2686ce668e
R-0 head=4bb9a0a97bf3464998290cf1ab024e2686ce668e
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
T_SHA=bcfdbbe022cc2ba3b714a0ab9c7d94893efb17e8f9061ffd7cc4bf8c91c448c5
R-0 head=4bb9a0a97bf3464998290cf1ab024e2686ce668e
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
guard_rc=0
8ed3400a D0-A: introduce config/tos_completion.yaml
d=8ed3400a4e78a8731128155ff826217d5848c3bd
parent(d)=4bb9a0a97bf3464998290cf1ab024e2686ce668e
D0-A: introduce config/tos_completion.yaml

Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md

Entry-Transcript-Run: 1

Entry-Transcript-SHA256: bcfdbbe022cc2ba3b714a0ab9c7d94893efb17e8f9061ffd7cc4bf8c91c448c5

7445de08 SIMULATED: transcript commit after d (H -> d -> T chain; test fixture only)
8ed3400a D0-A: introduce config/tos_completion.yaml
4bb9a0a9 C2: SIMULATED approve verdict (test fixture only)
-- executor --
D=8ed3400a4e78a8731128155ff826217d5848c3bd 
d=8ed3400a4e78a8731128155ff826217d5848c3bd
parent(d)=4bb9a0a97bf3464998290cf1ab024e2686ce668e
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md run=1 sha=bcfdbbe022cc2ba3b714a0ab9c7d94893efb17e8f9061ffd7cc4bf8c91c448c5
transcript runs=1 cited_run=1 head=4bb9a0a97bf3464998290cf1ab024e2686ce668e nstate=1 state=ENTRY_OK
d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR
reason=|CORR(d)|=1 — (t=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md,k=1)
exec_rc=0

########## T-81 (13) HEAD move between harness pass and D0A-FIRST ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m13
R-0 head=622eaae5637e1d84a424bb85619d21e4675f0eff
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
X(하니스 평가 HEAD)=622eaae5637e1d84a424bb85619d21e4675f0eff
R-0 head=622eaae5637e1d84a424bb85619d21e4675f0eff
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
guard_rc=0
d=3b19ddf25b8e3953bd1d3e87e4bec8d608117416
parent(d)=4ef93af9f8615c3904004bd1787c97bbd789edea  X=622eaae5637e1d84a424bb85619d21e4675f0eff
-- executor --
D=3b19ddf25b8e3953bd1d3e87e4bec8d608117416 
d=3b19ddf25b8e3953bd1d3e87e4bec8d608117416
parent(d)=4ef93af9f8615c3904004bd1787c97bbd789edea
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md run=1 sha=12f66ba56c465a34c2cc14c2c69f870f2cadcfac3288d94b4e68f0e338834feb
transcript runs=1 cited_run=1 head=622eaae5637e1d84a424bb85619d21e4675f0eff nstate=1 state=ENTRY_OK
d0a_entry_provenance_state=PARENT_MISMATCH
reason=run 1 head=622eaae5637e1d84a424bb85619d21e4675f0eff ≠ parent(d)=4ef93af9f8615c3904004bd1787c97bbd789edea
exec_rc=1

########## T-81 (14) unguarded start at frozen HEAD, no trailer (v2.13 def re-run on v2.14 executor) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m14
HEAD=9c6e052913d907c371efa200f1eaf98b84567345
commit_rc=0
d=8e2d7638d55cbdf463544f6624a9ddf12702a1c6  parent(d)=9c6e052913d907c371efa200f1eaf98b84567345
-- executor --
D=8e2d7638d55cbdf463544f6624a9ddf12702a1c6 
d=8e2d7638d55cbdf463544f6624a9ddf12702a1c6
parent(d)=9c6e052913d907c371efa200f1eaf98b84567345
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=0 run=0 sha=0 (각 1 요구)
exec_rc=1

########## T-81 (15) forward-merge bypass (v2.13 def re-run on v2.14 executor) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m15
HEAD=cf9b0295ac574b0cb022dd743e42c7aac5113aca
6995f194 Merge commit '9c6e052913d907c371efa200f1eaf98b84567345' into HEAD
5c329299 D0-A: introduce config/tos_completion.yaml
9c6e0529 docs(plans): INDEX — phase0 completion contract v2.15 frozen (11a56d3e)
d=5c3292994baf7af9c8355b98243de98de94a9b44  parent(d)=cf9b0295ac574b0cb022dd743e42c7aac5113aca
-- executor --
D=5c3292994baf7af9c8355b98243de98de94a9b44 
d=5c3292994baf7af9c8355b98243de98de94a9b44
parent(d)=cf9b0295ac574b0cb022dd743e42c7aac5113aca
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=0 run=0 sha=0 (각 1 요구)
exec_rc=1

########## T-81 (16) trailer-less start; then harness re-run at parent(d) -> t' ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m16
H=89eb63acbb0046abcb99c8b6e97d6fe80dbde54a
d=be8ccd6e4d2ba1ebe41426f2e68476df106d24e3  parent(d)=89eb63acbb0046abcb99c8b6e97d6fe80dbde54a
R-0 head=89eb63acbb0046abcb99c8b6e97d6fe80dbde54a
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
t' sha=15968117fd832e4ab39aefceebd7230000f10536a53d3523ab8429cc4f9b2192
8ae0eb5b SIMULATED: transcript commit after d (H -> d -> T chain; test fixture only)
be8ccd6e D0-A: introduce config/tos_completion.yaml
89eb63ac C2: SIMULATED approve verdict (test fixture only)
-- executor --
D=be8ccd6e4d2ba1ebe41426f2e68476df106d24e3 
d=be8ccd6e4d2ba1ebe41426f2e68476df106d24e3
parent(d)=89eb63acbb0046abcb99c8b6e97d6fe80dbde54a
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=0 run=0 sha=0 (각 1 요구)
exec_rc=1

########## T-81 (17) trailer malformed a/b/c + H6 boundary ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m17
H=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
R-0 head=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
T_SHA=8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250
---- (17)a: Run line missing ----
d=a4992724a45458ae4b01f5260d612f37519d6f85  parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md
  msg| 
  msg| Entry-Transcript-SHA256: 8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250
  msg| 
-- executor --
D=a4992724a45458ae4b01f5260d612f37519d6f85 
d=a4992724a45458ae4b01f5260d612f37519d6f85
parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=1 run=0 sha=1 (각 1 요구)
exec_rc=1
---- (17)b: Run line twice ----
d=0ca3181e925a4d8e69c7f6c950ed1f3559c32c4a  parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-SHA256: 8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250
  msg| 
-- executor --
D=0ca3181e925a4d8e69c7f6c950ed1f3559c32c4a 
d=0ca3181e925a4d8e69c7f6c950ed1f3559c32c4a
parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=1 run=2 sha=1 (각 1 요구)
exec_rc=1
---- (17)c: SHA256 mismatch ----
d=c2cb37e2f3796eeb30421506cfa49a014989e39c  parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-SHA256: 0000000000000000000000000000000000000000000000000000000000000000
  msg| 
-- executor --
D=c2cb37e2f3796eeb30421506cfa49a014989e39c 
d=c2cb37e2f3796eeb30421506cfa49a014989e39c
parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md run=1 sha=0000000000000000000000000000000000000000000000000000000000000000
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=SHA256 불일치: 실제=8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250
exec_rc=1
---- (17)H6-i: cited run absent ----
d=5528632ff09784be8b64637bf0829c39ee59599f  parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md
  msg| 
  msg| Entry-Transcript-Run: 99
  msg| 
  msg| Entry-Transcript-SHA256: 8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250
  msg| 
-- executor --
D=5528632ff09784be8b64637bf0829c39ee59599f 
d=5528632ff09784be8b64637bf0829c39ee59599f
parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md run=99 sha=8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250
transcript runs=1 cited_run=99 head=NONE nstate=0 state=NONE
d0a_entry_provenance_state=TRANSCRIPT_MISSING
reason=인용 run 99 부재 (transcript 내 run 수=1)
exec_rc=1
---- (17)H6-ii: cited path absent ----
d=9d55fd2e6110ab8faf629a2d8b9a94fe25120102  parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260818-224729/NO-SUCH-FILE.md
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-SHA256: 8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250
  msg| 
-- executor --
D=9d55fd2e6110ab8faf629a2d8b9a94fe25120102 
d=9d55fd2e6110ab8faf629a2d8b9a94fe25120102
parent(d)=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb
trailer: path=docs/reviews/phase0-completion-contract/20260818-224729/NO-SUCH-FILE.md run=1 sha=8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250
d0a_entry_provenance_state=TRANSCRIPT_MISSING
reason=인용 transcript 경로 부재: docs/reviews/phase0-completion-contract/20260818-224729/NO-SUCH-FILE.md
exec_rc=1

########## T-81 (18) cited run recorded a blocked state ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m18
H(동결 HEAD·전제 없음)=9c6e052913d907c371efa200f1eaf98b84567345
R-0 head=9c6e052913d907c371efa200f1eaf98b84567345
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1
T_SHA=7e5fe0b540158903592855cfa834a5262558992121e0aa3a6683955315b691ad
commit_rc=0
d=c5dc73fb724da1d648ca61e255b145354ba088f0  parent(d)=9c6e052913d907c371efa200f1eaf98b84567345
-- executor --
D=c5dc73fb724da1d648ca61e255b145354ba088f0 
d=c5dc73fb724da1d648ca61e255b145354ba088f0
parent(d)=9c6e052913d907c371efa200f1eaf98b84567345
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md run=1 sha=7e5fe0b540158903592855cfa834a5262558992121e0aa3a6683955315b691ad
transcript runs=1 cited_run=1 head=9c6e052913d907c371efa200f1eaf98b84567345 nstate=1 state=REBINDING_REQUIRED
d0a_entry_provenance_state=TRANSCRIPT_NOT_ENTRY_OK
reason=run 1 상태=REBINDING_REQUIRED
exec_rc=1

########## T-81 (19) parallel introduction — gu ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m19-gu
H(전제 충족 HEAD)=1b9f3644ddde4fecd40a37bb970d514e8800fddb
R-0 head=1b9f3644ddde4fecd40a37bb970d514e8800fddb
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
side1=73141ce9eae32b7f38e7e19f72ce7f9b8ed3b4d9 side2=9ecb0dd2176dd26b3f2141d6e022d261c5d8e3e8
자동 병합: config/tos_completion.yaml
충돌 (추가/추가): config/tos_completion.yaml에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
*   1e0da510 M: merge side2 into side1 (conflict resolved; SIMULATED test fixture)
|\  
| * 9ecb0dd2 D0-A: introduce config/tos_completion.yaml
* | 73141ce9 D0-A: introduce config/tos_completion.yaml
|/  
* 1b9f3644 C2: SIMULATED approve verdict (test fixture only)
* fe1767d9 C1: SIMULATED rebinding (test fixture only)
* 9c6e0529 docs(plans): INDEX — phase0 completion contract v2.15 frozen (11a56d3e)
D(--diff-filter=A · 계약 U-15-g-1 명령 그대로)=
  9ecb0dd2 D0-A: introduce config/tos_completion.yaml
  73141ce9 D0-A: introduce config/tos_completion.yaml
[대조] --full-history --diff-filter=A (이력 단순화 해제) =
  9ecb0dd2 D0-A: introduce config/tos_completion.yaml
  73141ce9 D0-A: introduce config/tos_completion.yaml
-- executor --
D=9ecb0dd2176dd26b3f2141d6e022d261c5d8e3e8 73141ce9eae32b7f38e7e19f72ce7f9b8ed3b4d9 
d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS
reason=|D| = 2 — «최초»가 유일하지 않음
exec_rc=1

########## T-81 (19) parallel introduction — gg ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m19-gg
H(전제 충족 HEAD)=9a2d8aa289078d7f1838140cf4a8c0cf50ebe1a6
R-0 head=9a2d8aa289078d7f1838140cf4a8c0cf50ebe1a6
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
side1=1763fd6f92c6415335e99a3e892512c1bc40bc6d side2=c9cc478f62b5acd06792027ec4c26b99f1f46666
*   6abe6530 M: merge side2 into side1 (SIMULATED test fixture)
|\  
| * c9cc478f D0-A: introduce config/tos_completion.yaml
* | 1763fd6f D0-A: introduce config/tos_completion.yaml
|/  
* 9a2d8aa2 C2: SIMULATED approve verdict (test fixture only)
* b6aa159b C1: SIMULATED rebinding (test fixture only)
* 9c6e0529 docs(plans): INDEX — phase0 completion contract v2.15 frozen (11a56d3e)
D(--diff-filter=A · 계약 U-15-g-1 명령 그대로)=
  1763fd6f D0-A: introduce config/tos_completion.yaml
[대조] --full-history --diff-filter=A (이력 단순화 해제) =
  c9cc478f D0-A: introduce config/tos_completion.yaml
  1763fd6f D0-A: introduce config/tos_completion.yaml
-- executor --
D=1763fd6f92c6415335e99a3e892512c1bc40bc6d 
d=1763fd6f92c6415335e99a3e892512c1bc40bc6d
parent(d)=9a2d8aa289078d7f1838140cf4a8c0cf50ebe1a6
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md run=1 sha=b8c4b5094889cf11281aa12b8f0584fc6c93b98d120088fd8fa23f2e62a2a59c
transcript runs=1 cited_run=1 head=9a2d8aa289078d7f1838140cf4a8c0cf50ebe1a6 nstate=1 state=ENTRY_OK
d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR
reason=|CORR(d)|=1 — (t=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK.md,k=1)
exec_rc=0

########## T-81 (19) parallel introduction — uu ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m19-uu
H(전제 충족 HEAD)=26bffbeb35d0819c81be7746b1327a10266624a3
R-0 head=26bffbeb35d0819c81be7746b1327a10266624a3
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
side1=67a379ebe22e12941922b5cfc50ee5f00b011640 side2=745a793bf75106298f8bac9c48b4e4d4c902b227
자동 병합: config/tos_completion.yaml
충돌 (추가/추가): config/tos_completion.yaml에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
*   a4471898 M: merge side2 into side1 (conflict resolved; SIMULATED test fixture)
|\  
| * 745a793b D0-A: introduce config/tos_completion.yaml
* | 67a379eb D0-A: introduce config/tos_completion.yaml
|/  
* 26bffbeb C2: SIMULATED approve verdict (test fixture only)
* f57708da C1: SIMULATED rebinding (test fixture only)
* 9c6e0529 docs(plans): INDEX — phase0 completion contract v2.15 frozen (11a56d3e)
D(--diff-filter=A · 계약 U-15-g-1 명령 그대로)=
  745a793b D0-A: introduce config/tos_completion.yaml
  67a379eb D0-A: introduce config/tos_completion.yaml
[대조] --full-history --diff-filter=A (이력 단순화 해제) =
  745a793b D0-A: introduce config/tos_completion.yaml
  67a379eb D0-A: introduce config/tos_completion.yaml
-- executor --
D=745a793bf75106298f8bac9c48b4e4d4c902b227 67a379ebe22e12941922b5cfc50ee5f00b011640 
d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS
reason=|D| = 2 — «최초»가 유일하지 않음
exec_rc=1

########## worktree list (잔여 확인) ##########
/Users/harris/Development/private/kis_unified_sts                                               9c6e0529 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-v215.sh exit=0)
```

---

## 5. T-84 — U-17 «예방 통제 활성 증거» 손 실행기 · 픽스처 · 실행 기록 원문

**sha256(u17-exec.sh) = `e1fe7868099a512b5081af6d2e87e8b739feeecbd70720e00856e08246f20141` · sha256(t84.sh) = `bce65fdd1178c2a269915bb5a008416d671544a04e28a15af66f6e58dd647784`**

독해 선언(U-17-b/c/c2 · 계약이 리터럴로 고정하지 않은 자리를 실행기가 어떻게 읽었는가):
- **P** = `git log --format=%H --diff-filter=A -- <PC> | tail -1`(아티팩트 도입 커밋) · **D** = U-15-g-1 명령 그대로의
  집합. 아티팩트는 **HEAD 트리에서**(커밋-전용 읽기) 읽는다.
- **countersign 형식**: U-17-b ③ «6e 아티팩트와 같은 권위 형식»을 **`authority:` 1행 + `operator_countersign:` 1행,
  각 비어 있지 않음**으로 읽었다 — 6e 아티팩트(`OQ-11-DISPOSITION.md:16`)에 실재하는 것은 `authority:` 뿐이고
  countersign 필드명은 계약이 리터럴로 고정하지 않았으므로 **이 필드명은 실행기의 독해**다(§8-4 보고).
  **활성 주장 ①②** 는 `required_check:`(비어 있지 않음) + `branch_protection: enabled` + `activated_at_head: <40hex>` 로 읽었다.
- **전순서**: ABSENT > UNSIGNED > LATE > ACTIVE(계약 U-17-c2 그대로) · `D=∅` 는 «비교 대상 없음» 명시 통과 ·
  `∀d∈D: P ⊰ d`(진 조상 · 동일 커밋 거부) · exit 0 = ACTIVE 만 · `trap EXIT` 는 판정 없이 끝나는 경로를
  `PREVENTION_ABSENT`(fail-closed)로 폐쇄.
- **정직 표기 — 실행기 원문의 오타**: `cd` 실패 분기의 상태 리터럴이 `PREVENENTION_ABSENT`(철자 오류)다. 이번 실행
  어느 변이도 그 분기에 도달하지 않았고(전부 `cd` 성공), 도달했더라도 `emit` 이 exit 1 을 내므로 극성(차단)은
  보존되나 **상태값 어휘 밖**이다. 실행 후 발견했으며 **실행한 원문을 그대로 수록**한다(재실행하지 않았다 —
  이 파일은 실행 출력의 조립이며, 오타 교정본은 다음 사이클 실행기에 반영할 것).

```bash
#!/usr/bin/env bash
# U-17 «예방 통제 활성 증거» 손 실행기 — v2.15 U-17-b/c/c2 (계약 11a56d3e :4995-5048)
#   P = D0A-PREVENTION-CONTROL.md 를 도입한 커밋 · D = config/tos_completion.yaml 도입 커밋 집합
#   ACTIVE ⇔ 아티팩트 ∧ countersign(6e 권위 형식: authority: + operator_countersign:) ∧ 활성 주장(required_check:·branch_protection: enabled)
#            ∧ ∀d∈D: P ⊰ d   (D=∅ 는 «비교 대상 없음»으로 명시 통과)
#   전순서: PREVENTION_ABSENT > PREVENTION_UNSIGNED > PREVENTION_LATE > PREVENTION_ACTIVE.  exit 0 = ACTIVE 만.
# 사용: bash u17-exec.sh <repo>
set -u -o pipefail
EMITTED=0
emit() { EMITTED=1; printf 'prevention_control_state=%s\nreason=%s\n' "$1" "$2"; [ "$1" = PREVENTION_ACTIVE ] && exit 0; exit 1; }
trap '[ "$EMITTED" -eq 1 ] || { printf "prevention_control_state=%s\nreason=%s\n" PREVENTION_ABSENT "판정 미산출 상태로 종료(fail-closed)"; exit 1; }' EXIT
cd "${1:?repo}" || emit PREVENENTION_ABSENT "repo 진입 실패"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
CFG=config/tos_completion.yaml
# ── ABSENT: 아티팩트가 HEAD 트리에 부재 (커밋-전용 읽기)
BODY=$(git show "HEAD:$PC" 2>/dev/null) || emit PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"
P=$(git log --format=%H --diff-filter=A -- "$PC" | tail -1)
[ -n "$P" ] || emit PREVENTION_ABSENT "도입 커밋 P 파생 불가"
printf 'P=%s\n' "$P"
# ── UNSIGNED: countersign 부재·형식 위반 (6e 아티팩트 권위 형식: authority: 와 operator_countersign: 각 1회·비어 있지 않음) + 활성 주장 필수 내용 ①②
na=$(printf '%s\n' "$BODY" | grep -c '^authority:[[:space:]]*[^[:space:]]'); nc=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:[[:space:]]*[^[:space:]]')
{ [ "$na" = 1 ] && [ "$nc" = 1 ]; } || emit PREVENTION_UNSIGNED "countersign 형식 위반: authority=$na operator_countersign=$nc (각 1 요구)"
printf '%s\n' "$BODY" | grep -q '^required_check:[[:space:]]*[^[:space:]]' || emit PREVENTION_UNSIGNED "활성 주장 ① 부재(required_check)"
printf '%s\n' "$BODY" | grep -q '^branch_protection:[[:space:]]*enabled' || emit PREVENTION_UNSIGNED "활성 주장 ① 부재(branch_protection: enabled)"
printf '%s\n' "$BODY" | grep -q '^activated_at_head:[[:space:]]*[0-9a-f]\{40\}' || emit PREVENTION_UNSIGNED "활성 주장 ② 부재(activated_at_head)"
# ── LATE: ∀d∈D: P ⊰ d
D=$(git log --format=%H --diff-filter=A -- "$CFG"); ND=$(printf '%s\n' "$D" | grep -c .)
printf '|D|=%s D=%s\n' "$ND" "$(printf '%s\n' "$D" | tr '\n' ' ')"
if [ "$ND" -eq 0 ]; then emit PREVENTION_ACTIVE "D=∅ — 비교 대상 없음(명시 통과) · 아티팩트+countersign+활성 주장 완비"; fi
for d in $D; do
  { git merge-base --is-ancestor "$P" "$d" && [ "$P" != "$d" ]; } || emit PREVENTION_LATE "P 가 d=$d 의 진 조상이 아님"
done
emit PREVENTION_ACTIVE "∀d∈D: P ⊰ d (|D|=$ND) · 아티팩트+countersign+활성 주장 완비"
```

```bash
#!/usr/bin/env bash
# t84.sh — T-84 ①②③④ + 부속(D=∅ · |D|=2 한쪽만 앞섬) 픽스처(scratchpad 독립 git repo) + U-17 실행기. 본 저장소 무접촉.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
EX="$SP/u17-exec.sh"; FX="$SP/fx84"; PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ # art <repo> [nosign|badsign]  — 예방 아티팩트(6e 권위 형식 countersign) 도입 커밋 P
  mkdir -p "$1/$(dirname $PC)"
  { printf 'required_check: tos-entry-harness (CI 필수 잡)\nbranch_protection: enabled\nactivated_at_head: %s\n' "$(git -C "$1" rev-parse HEAD)"
    case "${2:-}" in nosign) ;; badsign) printf 'authority: 운영자\noperator_countersign:\n' ;; *) printf 'authority: 운영자 (this repository'"'"'s corpus owner)\noperator_countersign: APPROVED 2026-08-19 (SIMULATED test fixture)\n' ;; esac
  } > "$1/$PC"; git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)"; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact%s\n' "${2:-}" > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; }
run(){ git -C "$1" log --graph --oneline --all; bash "$EX" "$1"; echo "u17_rc=$?"; }

sec "T-84 (1) artifact absent (d exists)"
R="$FX/a1"; mk "$R"; d0a "$R"; run "$R"
sec "T-84 (2)-i countersign absent"
R="$FX/a2i"; mk "$R"; art "$R" nosign; d0a "$R"; run "$R"
sec "T-84 (2)-ii countersign format violation (empty value)"
R="$FX/a2ii"; mk "$R"; art "$R" badsign; d0a "$R"; run "$R"
sec "T-84 (3) positive — P then d"
R="$FX/a3"; mk "$R"; art "$R"; d0a "$R"; run "$R"
sec "T-84 (4) d first, P later"
R="$FX/a4"; mk "$R"; d0a "$R"; art "$R"; run "$R"
sec "T-84 aux — D=∅ (artifact only)"
R="$FX/a5"; mk "$R"; art "$R"; run "$R"
sec "T-84 aux — |D|=2, P precedes only one d"
R="$FX/a6"; mk "$R"; H0=$(git -C "$R" rev-parse HEAD)
git -C "$R" checkout -q --detach "$H0"; d0a "$R" " (side1, before P)"; S1=$(git -C "$R" rev-parse HEAD)
git -C "$R" checkout -q --detach "$H0"; art "$R"; d0a "$R" " (side2, after P)"; S2=$(git -C "$R" rev-parse HEAD)
git -C "$R" checkout -q main; git -C "$R" merge -q --no-ff -m M1 "$S1"; git -C "$R" merge -q --no-ff -m M2 "$S2" 2>/dev/null || { printf '# D0-A first artifact (resolved)\n' > "$R/config/tos_completion.yaml"; git -C "$R" add -A; git -C "$R" commit -q -m M2; }
run "$R"
```

실행 기록 원문 (t84.sh stdout · 픽스처 DAG 포함 · 본 저장소 적용 포함):

```text
t84_utc=2026-08-18T16:27:35Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t84.sh

########## T-84 (1) artifact absent (d exists) ##########
* 06c7b36 D0-A: introduce config/tos_completion.yaml
* df4182f seed
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1

########## T-84 (2)-i countersign absent ##########
* 0a96b03 D0-A: introduce config/tos_completion.yaml
* e6d85a0 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* df4182f seed
P=e6d85a0a4a06aabf195ab5ebceeba9d111e64619
prevention_control_state=PREVENTION_UNSIGNED
reason=countersign 형식 위반: authority=0 operator_countersign=0 (각 1 요구)
u17_rc=1

########## T-84 (2)-ii countersign format violation (empty value) ##########
* a59701e D0-A: introduce config/tos_completion.yaml
* b16d255 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* eda545c seed
P=b16d2558f2219b322d200b15a091643d35abfadf
prevention_control_state=PREVENTION_UNSIGNED
reason=countersign 형식 위반: authority=1 operator_countersign=0 (각 1 요구)
u17_rc=1

########## T-84 (3) positive — P then d ##########
* 37d5655 D0-A: introduce config/tos_completion.yaml
* 0421687 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* eda545c seed
P=0421687a71b8684cd0a3f8e775624cfac6d030fb
|D|=1 D=37d565567ed7431f4a3e636c127171039587a5a1 
prevention_control_state=PREVENTION_ACTIVE
reason=∀d∈D: P ⊰ d (|D|=1) · 아티팩트+countersign+활성 주장 완비
u17_rc=0

########## T-84 (4) d first, P later ##########
* 5cc14a8 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 7eb2e4e D0-A: introduce config/tos_completion.yaml
* eda545c seed
P=5cc14a853f051cfa4573ad2bcd58380564f8a5fd
|D|=1 D=7eb2e4e2b573ee398fe7d4f811fceb7c216daaa2 
prevention_control_state=PREVENTION_LATE
reason=P 가 d=7eb2e4e2b573ee398fe7d4f811fceb7c216daaa2 의 진 조상이 아님
u17_rc=1

########## T-84 aux — D=∅ (artifact only) ##########
* b09f5f1 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 87f01aa seed
P=b09f5f1e4118dd5d0c3af3725652ac3876e24cff
|D|=0 D= 
prevention_control_state=PREVENTION_ACTIVE
reason=D=∅ — 비교 대상 없음(명시 통과) · 아티팩트+countersign+활성 주장 완비
u17_rc=0

########## T-84 aux — |D|=2, P precedes only one d ##########
자동 병합: config/tos_completion.yaml
충돌 (추가/추가): config/tos_completion.yaml에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
*   b550758 M2
|\  
| * 0183e75 D0-A: introduce config/tos_completion.yaml
| * b09f5f1 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* |   cdd4a9e M1
|\ \  
| |/  
|/|   
| * 7f7a140 D0-A: introduce config/tos_completion.yaml
|/  
* 87f01aa seed
P=b09f5f1e4118dd5d0c3af3725652ac3876e24cff
|D|=2 D=0183e75738cc912f70ffb3c3172365b9fa2437a4 7f7a140b48329c09f2e502a2fb75bd25e43b8d67 
prevention_control_state=PREVENTION_LATE
reason=P 가 d=7f7a140b48329c09f2e502a2fb75bd25e43b8d67 의 진 조상이 아님
u17_rc=1
(t84.sh exit=0)

########## 본 저장소에 U-17 실행기 적용 ##########
$ bash u17-exec.sh <repo>
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1
```

픽스처 DAG (조립 시점 재확인 · `git -C $SP/fx84/<n> log --graph --oneline --all` — 실행 출력의 DAG 와 동일):

```text
== fx84/a1
* 06c7b36 D0-A: introduce config/tos_completion.yaml
* df4182f seed
== fx84/a2i
* 0a96b03 D0-A: introduce config/tos_completion.yaml
* e6d85a0 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* df4182f seed
== fx84/a2ii
* a59701e D0-A: introduce config/tos_completion.yaml
* b16d255 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* eda545c seed
== fx84/a3
* 37d5655 D0-A: introduce config/tos_completion.yaml
* 0421687 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* eda545c seed
== fx84/a4
* 5cc14a8 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 7eb2e4e D0-A: introduce config/tos_completion.yaml
* eda545c seed
== fx84/a5
* b09f5f1 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 87f01aa seed
== fx84/a6
*   b550758 M2
|\  
| * 0183e75 D0-A: introduce config/tos_completion.yaml
| * b09f5f1 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* |   cdd4a9e M1
|\ \  
| |/  
|/|   
| * 7f7a140 D0-A: introduce config/tos_completion.yaml
|/  
* 87f01aa seed
```

---

## 6. 픽스처 transcript 원문·sha (트레일러가 인용한 t)

- sha256: m12-t `bcfdbbe022cc2ba3b714a0ab9c7d94893efb17e8f9061ffd7cc4bf8c91c448c5` · m13-t `12f66ba56c465a34c2cc14c2c69f870f2cadcfac3288d94b4e68f0e338834feb` ·
  m16-t′ `15968117fd832e4ab39aefceebd7230000f10536a53d3523ab8429cc4f9b2192` · m17-t `8f10724fdf2ff083f24e0fe7f13218b75a71cac83f1e0ed282e9ad9b23b02250` ·
  m18-t `7e5fe0b540158903592855cfa834a5262558992121e0aa3a6683955315b691ad` · m19-gu-t `6e9b5b1b5a86c58279041b48fe61c12e2b8ebd8063b0c7fffd572c11d0fb83f4` ·
  m19-gg-t `b8c4b5094889cf11281aa12b8f0584fc6c93b98d120088fd8fa23f2e62a2a59c` · m19-uu-t `722a947b723fe297e916f28b4122915209fcd2b33dc3838be1ce2278606732ca`
- 아래는 ⑫ 가 인용한 m12-t.md 원문 전문 (다른 픽스처는 run 1 의 하니스 출력·`generated_utc` 만 다르다 — §4 에 각 출력 원문 수록):

```text
# U15-ENTRY-CHECK — SIMULATED fixture transcript (test fixture only · worktree-scoped)
- harness: §12.3.4-R (11a56d3e) sha256 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
- generated_utc: 2026-08-18T16:23:53Z
- runs: 아래 각 run 은 `R-0 head=<40hex>` 리터럴 라인으로 열리고 `d0a_entry_state=` 라인 정확히 1개를 가진다 (U-15-e (4c)(4c-2))

## run 1
$ bash harness.sh; echo "harness_rc=$?"
R-0 head=4bb9a0a97bf3464998290cf1ab024e2686ce668e
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
```

---

## 7. U-15-e (5) 가드 실행 기록 · 정리 · 본 저장소 무영향 (사후 검증 원문)

- **가드 명령 원문 (⑫·⑬·⑲ guarded side, worktree)**: `cd "$WT" && bash <§12.3.4-R 하니스> && eval "$D0A_FIRST"` — `D0A_FIRST` 는
  §12.3.4-G 원문(트레일러 3줄 `-m` 포함). ⑫ `guard_rc=0`, D0A-FIRST 산물 존재: 파일 + 도입 커밋 `8ed3400a`(parent
  `4bb9a0a9` = run 1 head) → 실행기 `ENTRY_PROVENANCE_CLEAR`/0. ⑬ `guard_rc=0`, 도입 커밋 `3b19ddf2`(parent `4ef93af9`
  ≠ X `622eaae5`) → `PARENT_MISMATCH`/1. ⑲ guarded side 는 하니스 stdout 을 `>/dev/null` 로 버렸으므로 그 run 은
  이 transcript 의 run 우주에 들지 않는다(각 변종의 픽스처 t 는 별도 1회 실행 출력).
- **본 저장소에서는 가드 형태의 착수를 실행하지 않았다** — D0A-FIRST 산물 부재(파일·도입 커밋 양쪽, 아래 실측)·
  8값 실행기 `NOT_STARTED`/0 · U-17 실행기 `PREVENTION_ABSENT`/1 · 현행 하니스 `REBINDING_REQUIRED`/1.

```text
=== 사후 검증 (2026-08-18T16:33:14Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               9c6e0529 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
9c6e0529 docs(plans): INDEX — phase0 completion contract v2.15 frozen (11a56d3e)
$ git branch --list "br*" "side*" | wc -l   # ⑲ 1차 실행이 만든 브랜치 오염 정리 확인
       0
status/HEAD: 실행 전과 byte-동일
-- worktree D0A-FIRST 커밋 도달성 (refs 전수): 0ca3181e 1763fd6f 3b19ddf2 5528632f 5c329299 745a793b 8e2d7638 8ed3400a 9d55fd2e 9ecb0dd2 a4992724 be8ccd6e c2cb37e2 c5dc73fb --
도달 가능 건수=0 (0 기대)
-- 본 저장소 D0-A 미착수 불변 --
ls: config/tos_completion.yaml: No such file or directory
(도입 커밋 없음)
$ bash u15g-exec215.sh <repo>
D= 
d0a_entry_provenance_state=NOT_STARTED
reason=|D| = 0
exec_rc=0
$ bash u17-exec.sh <repo>
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1
$ bash harness215.sh (본 저장소 현행)
R-0 head=9c6e052913d907c371efa200f1eaf98b84567345
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1
-- 모의 스탬프·ART·기존 transcript 무변경 --
(2999* 없음)
(출력 없음 = 무변경)
-- scratchpad 픽스처(독립 repo)·worktree 잔여 --
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/fx82:
15
16
17a
17b
17c
18
19
one

/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/fx84:
a1
a2i
a2ii
a3
a4
a5
a6
(wt/ 비어 있음)
```

---

## 8. 기대 밖·계약 불일치·관측 보고 (고치지 않는다 — bound_paths 동결)

1. **[계약 결함 후보] T-81 ⑲ gg — U-15-g-1 `D` 우주의 플래그(이력 단순화) 의존.** U-15-g-1 은 `D` 를 리터럴 명령
   `git log --diff-filter=A -- config/tos_completion.yaml` 로 정의한다. 두 side 가 **byte-동일 내용**으로 파일을 도입하고
   (둘 다 가드 통과·같은 트레일러) 머지하면 머지 커밋이 한쪽 부모와 TREESAME 이라 git 의 **기본 이력 단순화**가 다른
   side 를 건너뛰어 **`|D|=1`** 을 낸다 — 실측 `D(--diff-filter=A)= 1763fd6f` 1건 vs `--full-history` 대조 **2건**
   (`c9cc478f`·`1763fd6f`). 실행기는 계약 명령을 그대로 따랐으므로 **`ENTRY_PROVENANCE_CLEAR`/0** 을 냈다 — 이는
   U-15-g-2 극성 논증이 «∀d 최악값이면 d1·d2 둘 다 guarded 일 때 CLEAR 가 남는다»고 명시적으로 **회피하려던 결과**가
   **카디널리티 산출 단계에서** 재현된 것이다(같은 DAG·같은 계약문인데 플래그 유무로 판정이 정반대 — U-16-g6 [G3]
   가 기록한 결함 클래스와 동형). gu(내용 상이 → add/add 충돌 → 해소 머지)·uu 는 양 side 가 살아 `|D|=2` 로 정상
   차단됐다. §8 ⑲ 행 정의(«한쪽 트레일러 有·한쪽 無» = gu)는 실측 일치이므로 대조군 자체는 통과이나, **`D` 정의를
   구현 플래그에 의존하지 않는 구조 정의(g6 C_R 이 택한 형태 — 예: `x ⊑ HEAD` 이고 `x` 에 경로 존재 ∧ ∀p∈parents(x)
   경로 부재)로 바꾸거나 `--full-history` 를 계약 리터럴에 넣어야** 이 클래스가 닫힌다. **고치지 않고 보고한다.**
   부수: `--full-history` 로만 바꿔도 «TREESAME 부모 쪽 side 의 도입 커밋»이 `D` 에 드는지는 별도 실측이 필요하다
   (여기서는 2건이 나왔으나 그 자체가 «구조 정의»는 아니다).
2. **T-81 ⑭ 기대값 정합 회복**: v2.14 transcript §7-1 이 보고한 «§8 ⑭ 행 리터럴 `TRANSCRIPT_MISSING` vs 실측
   `ENTRY_TRAILER_MALFORMED`» 불일치는 v2.14 에라타로 §8 ⑭ 행이 `ENTRY_TRAILER_MALFORMED` 로 정정되어 있고,
   이번 실측도 `ENTRY_TRAILER_MALFORMED`/1 — **일치**. ⑮ 는 "red" 만 계약하며 실측 `ENTRY_TRAILER_MALFORMED`(3).
3. **H6 경계 2종**: H6-ii 의 부재 경로 리터럴은 직전 스탬프 디렉터리(`20260818-224729/NO-SUCH-FILE.md`)를 가리킨다 —
   부재이기만 하면 되므로 결과에 영향 없음(드라이버 상수 미갱신 — 정직 표기). H6-i(run 99)·H6-ii 모두 6
   `TRANSCRIPT_MISSING` — 3 이 아님(계약 [H6] 그대로).
4. **[계약 정밀화 후보] U-17-b ③ countersign 필드 형식 미고정**: «6e 아티팩트와 같은 권위 형식»이라 적혔으나 6e
   아티팩트에 실재하는 필드는 `authority:` 뿐이고 countersign 자체의 필드명·값 형식은 계약이 고정하지 않았다.
   실행기는 `operator_countersign:` 을 채택했다(독해). 다른 구현이 다른 필드명을 택하면 같은 아티팩트가 한쪽에서
   `PREVENTION_UNSIGNED`, 다른 쪽에서 통과할 수 있다 — 필드명·비어 있지 않음·1회 규칙을 계약 리터럴로 두어야
   T-84 ② 가 구현 독립이 된다. **고치지 않고 보고한다.**
5. **T-84 부속 |D|=2**: U-17 은 `MULTIPLE_INTRODUCTIONS` 를 내지 않고 `∀d∈D: P ⊰ d` 만 본다(계약 U-17-c 그대로) —
   한쪽 d 가 P 를 앞서면 `PREVENTION_LATE`. U-15-g-2 의 `|D|>1` 차단은 별도 축(`d0a_entry_provenance_state`)에서
   나며 §11 은 두 값을 각각 소비하므로 결과적으로 이중 차단이다 — 결함 아님, 관측.
6. **U-17 실행기 오타** (`PREVENENTION_ABSENT`, `cd` 실패 분기) — §5 독해 선언에 정직 표기. 이번 실행 미도달·극성 보존.
7. **⑫ 양성의 의미 한정**: `ENTRY_PROVENANCE_CLEAR`/0 은 worktree 모의 커밋(`8ed3400a`, parent `4bb9a0a9`) 위의 값이며
   본 저장소는 `NOT_STARTED`(§7). 8값 실행기의 «성공 경로 2곳» 이 각각 실제로 도달됨(⑫ CLEAR · 본 저장소 NOT_STARTED)을
   실측했고 나머지 6값 중 `PROVENANCE_UNVERIFIABLE`(얕은 클론) 은 이번 실행에 변이가 없다(T-81 ⑤ 축 — 이 transcript 밖).
8. **§12.3.4-G T_PATH 위치의 함의**(v2.14 transcript §7-2 와 동일 — 독해 주의점, 문서 결함 아님): 가드 worktree 안에
   미커밋 t 를 두면 하니스 R-0 이 `FREEZE_VIOLATED` 를 낸다. 저작 측/가드 측 분리와 `H → d → commit(t)` 체인으로 정합.

---

## 9. (4c-2) 자기 검증 명령·출력 · 직전 transcript 와의 차이 · 소비 조건 · 불변 규율

- **(4c-2) 자기 검증** (이 파일을 대상으로 §2 실행기와 같은 awk 술어를 적용 — 조립 직후 실행, 출력 원문):

```text
$ awk '<§2 실행기와 같은 opener/상태 술어 · run 별 head·nstate·state 출력>' U15-ENTRY-CHECK.md
run=1 head=4bb9a0a97bf3464998290cf1ab024e2686ce668e nstate=1 state=ENTRY_OK
run=2 head=4bb9a0a97bf3464998290cf1ab024e2686ce668e nstate=1 state=ENTRY_OK
run=3 head=622eaae5637e1d84a424bb85619d21e4675f0eff nstate=1 state=ENTRY_OK
run=4 head=622eaae5637e1d84a424bb85619d21e4675f0eff nstate=1 state=ENTRY_OK
run=5 head=89eb63acbb0046abcb99c8b6e97d6fe80dbde54a nstate=1 state=ENTRY_OK
run=6 head=da8adc72ac2698bc1a91e8c505d2b60dc288ebcb nstate=1 state=ENTRY_OK
run=7 head=9c6e052913d907c371efa200f1eaf98b84567345 nstate=1 state=REBINDING_REQUIRED
run=8 head=1b9f3644ddde4fecd40a37bb970d514e8800fddb nstate=1 state=ENTRY_OK
run=9 head=9a2d8aa289078d7f1838140cf4a8c0cf50ebe1a6 nstate=1 state=ENTRY_OK
run=10 head=26bffbeb35d0819c81be7746b1327a10266624a3 nstate=1 state=ENTRY_OK
run=11 head=4bb9a0a97bf3464998290cf1ab024e2686ce668e nstate=1 state=ENTRY_OK
run=12 head=9c6e052913d907c371efa200f1eaf98b84567345 nstate=1 state=REBINDING_REQUIRED
total_runs=12  (runs with nstate!=1: 0)
```

  (검증 출력을 이 파일에 삽입해도 opener·상태 라인 수는 불변이다 — 출력 형식이 두 정규식과 행 전체 일치하지 않는다.)

```text
직전 (v2.14)   7값 실행기 · |D| 카디널리티 가정(«있으면 1건», tail -1 로 접기) · U-17 없음 ·
               T-82 ⑱ 손 실행이 tombstone-graph 만 실행(→ 심판 «회피»).
이 transcript   8값 실행기가 D 를 집합으로 산출·|D|>1 → MULTIPLE_INTRODUCTIONS 를 CORR 이전에 방출(⑲ gu/uu 실측) ·
               U-17 실행기(4값·전순서·∀d∈D: P ⊰ d·D=∅ 명시 통과) T-84 ①②③④+부속 2종 실측 ·
               ⑫~⑱ 회귀 전건 v2.14 와 동일 값 · ⑭ 기대 정합 회복.
               신규 관측: ⑲ gg 가 이력 단순화로 |D|=1 → CLEAR/0 (계약 결함 후보 §8-1).
               T-82 는 sibling U16-LEDGER-CHECK.md — 전 규칙 실행기(S-23 rules_executed 방출)로 ⑱ 양성 재실증.
```

- **소비 조건 (U-15-e (6))**: 이 transcript 의 실 저장소 HEAD 는 `9c6e0529`(동결 `11a56d3e` + INDEX). 이후 `bound_paths`
  를 건드린 커밋이 있으면 stale 이며 진입 거부다. 본 저장소 현행 하니스 산출은 `REBINDING_REQUIRED`(§7) — 6e 재결속·
  레인 B `approve` 후 그 시점 HEAD 의 새 transcript 가 필요하고, U-17 아티팩트(`D0A-PREVENTION-CONTROL.md`) 도입·
  countersign 이 D0-A 진입의 선행 조건이다(`PREVENTION_ABSENT` 현행).
- **불변 규율 (U-15-e (4d))**: 이 파일은 발행 시점에 확정되며 이후 편집하지 않는다(트레일러 SHA 결속의 전제). 보정은
  새 스탬프의 새 파일로 한다.
