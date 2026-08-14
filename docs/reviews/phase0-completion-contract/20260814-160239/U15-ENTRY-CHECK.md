# U15-ENTRY-CHECK — v2.9 판정 하니스 실행 transcript (pre-D0-A · 1단 강제 지점)

- **목적**: 레인 B v2.8 재심 verdict(`20260814-160239`, NOT_PASSED)의 Recommendation —
  "실제 진입 소비자가 stale·미승인 입력에서 **비정상 종료하거나 진입을 차단**하는 실행
  결과" — 의 이행. v2.9(§12.3.4-R)가 재저작한 **판정 하니스**(프로그램이 `d0a_entry_state`
  산출·차단이면 비-0 exit)를 동결 커밋에서 추출해 그대로 실행하고, §12.3.4-T의 양성·
  음성-1·음성-2 3-run 을 U-15-e (1)~(4b) 결속으로 남긴다.
- **생성 시각**: 2026-08-14T08:04:14Z (UTC)
- **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트
- **관련 계약**: U-15 · U-15-e (v2.9 강화판 — (4) 프로그램 산출 상태값+rc·(4b) 하니스
  무결성 결속) · T-81-① · T-81-①-e · §12.3.4-R · §12.3.4-T (동결 커밋 `a6d928c5`)
- **run 요약 — 하니스 stdout 의 해당 행과 rc 를 그대로 옮긴다 (해석 아님)**:

| Run | 실행 지점 | 실행 HEAD | 하니스 산출 (원문) | rc |
| --- | --- | --- | --- | --- |
| A 양성 | 본 저장소 (동결 상태) | `a6d928c5` | `d0a_entry_state=REBINDING_REQUIRED` / `reason=bound_set_digest 불일치` | `harness_rc=1` |
| B 음성-1 | worktree, 변이 커밋 `7801ee07` 후 | `7801ee07` | `d0a_entry_state=REBINDING_REQUIRED` / `reason=bound_set_digest 불일치` | `harness_rc=1` |
| C 음성-2 | worktree, 3-커밋 모의 후 | `a793b0a0` | `d0a_entry_state=APPROVAL_STALE` / `reason=승인 이후 변경: bc057e99…` | `harness_rc=1` |

**세 run 전부 프로그램이 차단 상태값을 산출하고 비-0 으로 종료했다.** 이 transcript 는
`ENTRY_OK` 를 주장하지 않는다 — 본 저장소의 현행 산출은 `REBINDING_REQUIRED`(6e‴
재결속 대기)다.

---

## 1. 하니스 명령 원문 (§12.3.4-R · 생략 없음) + U-15-e (4b) 무결성 결속

- 추출: 동결 커밋 `a6d928c5` 가 HEAD 인 워킹트리 문서에서 §12.3.4-R 의 첫 bash 블록을
  awk 로 verbatim 추출(94행 — `emit()`·`trap EXIT` 포함).
- **(4b) 무결성 결속**: `git show a6d928c5:<계약 문서>` 에서 같은 블록을 독립 재추출해
  **diff 무차이** — 실행본 == 동결본. `bash -n` 문법 검사 통과.
- **sha256(harness.sh) = `a3ae6f9d74a621b7b558f3698caf052b73ba2700fac8393af0a64d76f69978c3`**

```bash
#!/usr/bin/env bash
# §12.3.4-R  U-15 pre-D0-A 진입 판정 하니스 (v2.9)
# 산출: stdout 에 d0a_entry_state=<값>.  exit 0 = ENTRY_OK, 그 외 전부 비-0.
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
# 예상 밖 종료(명령 부재·시그널·미포착 오류)도 판정 없이 끝나지 않는다
trap '[ "$EMITTED" -eq 1 ] || { printf "d0a_entry_state=%s\nreason=%s\n" \
      HARNESS_ABORTED "판정 미산출 상태로 종료"; exit 1; }' EXIT

yaml_list() {   # yaml_list <file> <key>  → 리스트 원소를 1행씩
  awk -v k="$2" '
    $0 ~ "^"k":" {f=1; next}
    f && /^[[:space:]]*-[[:space:]]/ {
      sub(/^[[:space:]]*-[[:space:]]*/,""); sub(/[[:space:]]*#.*$/,"");
      sub(/[[:space:]]*$/,""); print; next }
    f && /^[^[:space:]]/ { exit }' "$1"
}
yaml_scalar() { # yaml_scalar <file> <key>
  awk -v k="$2" '$0 ~ "^"k":" {
      sub("^"k":[[:space:]]*",""); sub(/[[:space:]]*#.*$/,"");
      sub(/[[:space:]]*$/,""); print; exit }' "$1"
}

# ── R-0  실행 시점 결속 + 동결 확인
HEAD_SHA=$(git rev-parse HEAD) || emit HARNESS_ABORTED "git rev-parse 실패"
printf 'R-0 head=%s\n' "$HEAD_SHA"
for f in "$BP1" "$BP2" "$ART"; do
  [ -f "$f" ] || emit HARNESS_ABORTED "입력 부재: $f"
done
DIRTY=$(git status --porcelain -- "$BP1" "$BP2") || emit HARNESS_ABORTED "git status 실패"
[ -z "$DIRTY" ] || emit FREEZE_VIOLATED "bound_paths 미커밋 변경: $(echo "$DIRTY" | tr '\n' ';')"

# ── R-1  bound_paths 집합 == 계약이 요구하는 그 둘            [U-12 (iii)]
WANT=$(printf '%s\n%s\n' "$BP1" "$BP2" | LC_ALL=C sort)
GOT=$(yaml_list "$ART" bound_paths | LC_ALL=C sort) \
  || emit HARNESS_ABORTED "yaml_list 실패 — awk 부재·파일 파손"
[ "$GOT" = "$WANT" ] || emit REBINDING_REQUIRED "bound_paths 집합 불일치"

# ── R-2  bound_set_digest 재계산 == 보유값 · disposition 어휘  [U-12 (iv)(ii)]
CALC=$(printf '%s\0' "$BP1" "$BP2" | LC_ALL=C sort -z -u \
       | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1) \
  || emit HARNESS_ABORTED "digest 재계산 실패"
HELD=$(yaml_scalar "$ART" bound_set_digest) \
  || emit HARNESS_ABORTED "yaml_scalar 실패 — awk 부재"
[ -n "$HELD" ] || emit REBINDING_REQUIRED "bound_set_digest 미기재"
[ "$CALC" = "$HELD" ] || emit REBINDING_REQUIRED "bound_set_digest 불일치"
DISP=$(yaml_scalar "$ART" disposition) || emit HARNESS_ABORTED "yaml_scalar 실패"
case "$DISP" in
  RESOLVED_MAPPING_APPROVED|RESOLVED_MAPPING_REJECTED|DEFERRED_WITH_SCOPE|REFUSED) ;;
  *) emit REBINDING_REQUIRED "disposition 어휘 밖: '$DISP'" ;;
esac

# ── R-3  최신 verdict 스탬프
VD=$(ls -1d "$STAMPS"/[0-9]*/ 2>/dev/null | LC_ALL=C sort | tail -1)
{ [ -n "$VD" ] && [ -f "$VD/verdict.md" ]; } || emit APPROVAL_ABSENT "verdict 아티팩트 부재"
printf 'R-3 verdict=%s\n' "$VD"

# ── R-4  심판 계열·판정 어휘                                   [U-15-b (1)]
ADJ=$(yaml_scalar "$VD/verdict.md" adjudicator) || emit HARNESS_ABORTED "yaml_scalar 실패"
VER=$(yaml_scalar "$VD/verdict.md" verdict) || emit HARNESS_ABORTED "yaml_scalar 실패"
{ [ "$ADJ" = codex ] && [ "$VER" = approve ]; } \
  || emit APPROVAL_NOT_APPROVE "adjudicator='$ADJ' verdict='$VER'"

# ── R-5  심사 범위 == 요구 결속 경로 집합                        [U-15-b (2)]
RGOT=$(yaml_list "$VD/verdict.md" reviewed_plan_paths | LC_ALL=C sort) \
  || emit HARNESS_ABORTED "yaml_list 실패"
[ "$RGOT" = "$WANT" ] || emit APPROVAL_SCOPE_MISMATCH "reviewed_plan_paths 불일치"

# ── R-6  reviewed_at_head 가 HEAD 의 조상인가                    [U-15-b (3)]
RH=$(yaml_scalar "$VD/verdict.md" reviewed_at_head) || emit HARNESS_ABORTED "yaml_scalar 실패"
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

## 2. Run A — 양성 (본 저장소 · 동결 상태)

- 실행 시각: 2026-08-14T08:00:29Z (UTC) · 실행 HEAD: `a6d928c58df9e59dd1737613290598846ad04c90`
- 명령·출력 원문 전문:

```text
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness.sh; echo "harness_rc=$?"
R-0 head=a6d928c58df9e59dd1737613290598846ad04c90
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1
```

하니스 산출(위 원문 그대로): `d0a_entry_state=REBINDING_REQUIRED` ·
`reason=bound_set_digest 불일치` · `harness_rc=1`. 아티팩트 보유 digest 가 재계산값과
불일치하는 현행 상태(6e‴ 재결속 대기)에서 **프로그램이 차단을 산출하고 비-0 으로
종료**했다.

---

## 3. Run B — 음성-1 (worktree 변이 · 현행 전제)

### 3.1 실행본 결속

- §12.3.4-T 첫 bash 블록(T-81-①-a~d) verbatim 추출, 동결본과 diff 무차이.
- sha256(원문 t81-block.sh) = `6fa32eaed1af4bb6abeb8ad9a8d73630be542daa867e0ae37c19b7817c34b4cd`
- sha256(실행본 t81-run.sh) = `b6315305c8637ba4de0481ba7b40fd9d177241c11e8859294af05a56836d3575`
- 치환(유일 — 블록 주석 "(§12.3.4-R 블록을 추출해 recipe.sh 로 저장한 뒤)"의 이행):
  16행 `bash /path/to/recipe.sh` → `bash <스크래치>/harness.sh`. 치환 외 diff 0.

### 3.2 명령·출력 원문 전문 (bash -x 트레이스)

```text
runB_utc=2026-08-14T08:00:56Z  runB_base_head=a6d928c58df9e59dd1737613290598846ad04c90
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-run.sh
+ set -u
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuISmumFhm/t81
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuISmumFhm/t81 HEAD
작업 트리 준비 중 (분리된 HEAD a6d928c5)
HEAD의 현재 위치는 a6d928c5입니다 docs(tos): phase0 completion contract v2.9 — judgment harness, temporal blob binding
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuISmumFhm/t81 log -1 --format=%H
a6d928c58df9e59dd1737613290598846ad04c90
+ printf '\n<!-- T-81 mutation: P-0 대리 편집 -->\n'
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuISmumFhm/t81 commit -am 'T-81-(1) mutation: P-0 proxy edit of upper plan'
[HEAD 분리됨 7801ee07] T-81-(1) mutation: P-0 proxy edit of upper plan
 1 file changed, 2 insertions(+)
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuISmumFhm/t81
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness.sh
R-0 head=7801ee0700ab4eee8406e5e0a8eb3a059e8b5a35
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
+ echo harness_rc=1
harness_rc=1
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuISmumFhm/t81
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               a6d928c5 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-run.sh exit=0)
```

하니스 산출(위 원문 그대로): `d0a_entry_state=REBINDING_REQUIRED` · `harness_rc=1`.
변이 커밋 `7801ee07` 이 있는 worktree 에서 **차단 상태값 + rc≠0** — §12.3.4-T 의
«우선순위 차폐» 절이 기술한 그대로다(변이는 R-2 결속 만료로 먼저 잡히며, 그것이
더 강한 차단이다. `APPROVAL_STALE` 특정 관측은 음성-2 소관).

---

## 4. Run C — 음성-2 (T-81-①-e «전제 충족 모의» · APPROVAL_STALE 특정 관측)

### 4.1 실행본 결속

- T-81-①-e bash 블록 verbatim 추출, 동결본과 diff 무차이.
- sha256(원문 t81e-block.sh) = `6314a3c0cd69daa165b5b7b3e643a44b4281f8103d6e6d9b87ca8b9b1c1a0d8d`
- sha256(실행본 t81e-run.sh) = `8b2486efca93593bdeb1f2b00d8a980bfe1d85adf0f3a0c7137ac2e345507c2b`
- 실행본 구성(선언): **프롤로그 5행**(①-a 형태의 WT 확보 — ①-e 블록은 `$WT` 를
  전제하는데 ①-d 가 직전 worktree 를 이미 제거했으므로, 같은 분리-HEAD 계열
  (`a6d928c5`)의 새 worktree 를 확보한다. 그 결과 `BASE` = `a6d928c5` = 변이 전 HEAD
  로, 블록의 `BASE` 정의와 정합) + **①-e 블록 verbatim**(치환 유일: 32행
  `bash /path/to/recipe.sh` → `bash <스크래치>/harness.sh`, 치환 외 diff 0) +
  **에필로그 2행**(①-d 정리).

### 4.2 명령·출력 원문 전문 (bash -x 트레이스)

```text
runC_utc=2026-08-14T08:01:42Z  runC_base_head=a6d928c58df9e59dd1737613290598846ad04c90
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81e-run.sh
+ set -u
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e HEAD
작업 트리 준비 중 (분리된 HEAD a6d928c5)
HEAD의 현재 위치는 a6d928c5입니다 docs(tos): phase0 completion contract v2.9 — judgment harness, temporal blob binding
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e log -1 --format=%H
a6d928c58df9e59dd1737613290598846ad04c90
+ set -u
+ BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
+ ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e rev-parse HEAD
+ BASE=a6d928c58df9e59dd1737613290598846ad04c90
+ printf '\n<!-- T-81 mutation -->\n'
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e commit -am 'C1: P-0 proxy mutation'
[HEAD 분리됨 bc057e99] C1: P-0 proxy mutation
 1 file changed, 2 insertions(+)
++ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e
++ printf '%s\0' docs/plans/2026-08-12-tos-phase0-completion-contract-design.md docs/plans/2026-08-11-tos-completion-development-plan.md
++ LC_ALL=C
++ sort -z -u
++ xargs -0 shasum -a 256
++ shasum -a 256
++ cut '-d ' -f1
+ NEW=c9a0c1c32a79471353dd5c892add1b8142adca19719d408f54cfbd6ddbaf285f
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e
+ perl -pi -e 's/^bound_set_digest:.*/bound_set_digest: c9a0c1c32a79471353dd5c892add1b8142adca19719d408f54cfbd6ddbaf285f/' tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e commit -am 'C2: SIMULATED rebinding (test fixture only)'
[HEAD 분리됨 ac4079ef] C2: SIMULATED rebinding (test fixture only)
 1 file changed, 1 insertion(+), 1 deletion(-)
+ MOCK=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e/docs/reviews/phase0-completion-contract/29991231-235959
+ mkdir -p /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e/docs/reviews/phase0-completion-contract/29991231-235959
+ cat
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e add -A
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e commit -m 'C3: SIMULATED approve verdict (test fixture only)'
[HEAD 분리됨 a793b0a0] C3: SIMULATED approve verdict (test fixture only)
 1 file changed, 6 insertions(+)
 create mode 100644 docs/reviews/phase0-completion-contract/29991231-235959/verdict.md
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness.sh
R-0 head=a793b0a08c297eb3ed6146291777e96da927463a
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959/
d0a_entry_state=APPROVAL_STALE
reason=승인 이후 변경: bc057e99ca8824ac2df6657888541881db8f8bcb 
+ echo harness_rc=1
harness_rc=1
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.M7X1xzcmn9/t81e
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               a6d928c5 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81e-run.sh exit=0)
```

하니스 산출(위 원문 그대로): `d0a_entry_state=APPROVAL_STALE` ·
`reason=승인 이후 변경: bc057e99ca8824ac2df6657888541881db8f8bcb` · `harness_rc=1`.

- 3-커밋 모의: C1 변이 `bc057e99` / C2 SIMULATED 재결속 `ac4079ef` / C3 SIMULATED
  approve verdict `a793b0a0`(모의 스탬프 `29991231-235959`, `reviewed_at_head` =
  `$BASE` = `a6d928c5`).
- 출력이 보이는 통과 경로: `R-3 verdict=…/29991231-235959/` (모의 스탬프가 사전순
  최후로 선택됨) — R-2(C2 가 채운 digest 일치)·R-4(approve/codex)·R-5(경로 집합
  일치)·R-6(`a6d928c5` 는 HEAD 의 조상) 를 **전부 통과한 뒤** R-7 이
  `$BASE..HEAD` 에서 C1 을 발견해 발화했다. **R-7 은 死코드가 아니다** — 이것이
  음성-2 가 존재하는 이유다(§12.3.4-T: "음성-2 가 없으면 R-7 이 死코드인지 알 수 없다").

---

## 5. 정리 · 본 저장소 무영향 · 모의물 누출 방지

```text
=== 사후 검증 (2026-08-14T08:02:08Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               a6d928c5 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
a6d928c5 docs(tos): phase0 completion contract v2.9 — judgment harness, temporal blob binding
-- 실행 전(runB-pre) 스냅샷 대조 --
status: byte-동일
-- SIMULATED 모의물 누출 확인 --
$ git log --all --grep=SIMULATED --oneline
a6d928c5 docs(tos): phase0 completion contract v2.9 — judgment harness, temporal blob binding
(출력 없음 = 도달 가능한 이력에 모의 커밋 없음)
$ ls docs/reviews/phase0-completion-contract/ | grep 2999
(출력 없음 = 모의 스탬프 없음)
-- mktemp 잔여 정리 --
빈 mktemp 부모 2건 제거

-- SIMULATED grep 매치 판별 (위 매치는 누출이 아니다) --
$ git show -s --format=%B a6d928c5 | grep -n SIMULATED
16:  simulation (3 SIMULATED worktree commits, unreachable stamp) so
= 매치는 동결 커밋 a6d928c5 자신의 메시지 본문(§12.3.4-T 절차 서술)이다.
$ git log --all --format=%H | grep -c -e 7801ee07 -e bc057e99 -e ac4079ef -e a793b0a0
0
= worktree 커밋 4건(7801ee07·bc057e99·ac4079ef·a793b0a0) 전부 어떤 ref 에서도 도달 불가 — 누출 0건
```

- worktree 2건(t81·t81e) 전부 `remove --force` 완료 — `git worktree list` 에 잔여 없음
  (목록의 `futures-risk-hardening-design`·orca 2건은 실행 전부터 존재하는 별개 worktree).
- 본 저장소 `git status --short`(` M uv.lock` / `?? tools/spikes/` — 본 실행 이전부터
  존재)·HEAD(`a6d928c5`) 실행 전 스냅샷과 byte-동일.
- `git log --all --grep=SIMULATED` 의 유일 매치는 **동결 커밋 자신의 메시지 본문**
  (§12.3.4-T 절차를 서술한 16행)이며, worktree 커밋 4건(`7801ee07`·`bc057e99`·
  `ac4079ef`·`a793b0a0`)은 **어떤 ref 에서도 도달 불가**(refs 전수 대조 0건) —
  모의 스탬프 `29991231-*` 도 본 저장소에 부재. **누출 0건.**

---

## 6. v2.8 transcript 와의 차이 — 심판 지적의 직접 이행

```text
v2.8 (20260814-110807/U15-ENTRY-CHECK.md)
     명령 나열을 실행하고 rc=0 으로 끝났으며, 상태값은 **사람이 출력을 읽고
     판정 규칙에 대입해 적었다** ("판정은 출력 대조로 한다" — transcript 자인).
     심판(v2.8 재심 #1)이 이것을 "비교·분기·비정상 종료가 어디에도 없다"로 적발.

v2.9 (이 transcript)
     상태값은 **하니스 프로그램이 stdout 으로 산출**했고(`d0a_entry_state=` 행),
     차단이므로 **`harness_rc=1` (비-0)** 로 종료했다. 이 문서의 상태값·rc 는
     전부 §2~§4 의 출력 원문에서 **그대로 옮긴 것**이며, 해석을 적는 자리가
     없다(U-15-e (4) v2.9 강화). 세 run 모두 "stale·미승인 입력 → 비정상 종료·
     진입 차단"의 실행 결과다 — Recommendation 이 요구한 형태 그 자체.
```

**소비 조건(U-15-e (5)) 자기 기록**: 이 transcript 의 HEAD 는 `a6d928c5` 다. 진입
시점에 그 이후 `bound_paths` 를 건드린 커밋이 있으면 이 transcript 는 stale 이며
진입 거부다. 현행 산출이 `REBINDING_REQUIRED` 이므로, 6e‴ 재결속과 레인 B `approve`
취득 후 **그 시점 HEAD 에서 하니스를 재실행한 새 transcript** 가 필요하다 — 이
파일은 그 시점의 `ENTRY_OK` 를 주장하지 않는다.
