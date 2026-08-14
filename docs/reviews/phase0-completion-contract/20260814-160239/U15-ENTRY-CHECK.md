# U15-ENTRY-CHECK — v2.10 판정 하니스 실행 transcript (pre-D0-A · 1단 강제 지점)

> **Supersession**: 이 파일의 구판(v2.9 하니스 기록 — 사람이 아닌 프로그램 산출이지만
> **미커밋 권위 위조 미봉합 판**)은 커밋 `2b6f5eeb` 에 보존되어 있으며, v2.9 동결 직후
> stop-time 심판이 적발한 **미커밋 권위 위조 결함**("미커밋만으로 ENTRY_OK 위조 가능" —
> v2.10 이 커밋-전용 소비 + R-0 확장으로 봉합, 재동결 `4fb03470`)으로 대체됐다.

- **목적**: 레인 B v2.8 재심 verdict(`20260814-160239`, NOT_PASSED) Recommendation —
  "실제 진입 소비자가 stale·미승인 입력에서 비정상 종료하거나 진입을 차단하는 실행
  결과" — 의 이행을 **v2.10 하니스**로 재생성. §12.3.4-T 의 양성·음성-1·음성-2 에
  **봉합 실증 run(음성-3)** 을 더해 4-run 을 U-15-e (1)~(4b) 결속으로 남긴다.
- **생성 시각**: 2026-08-14T18:57:37Z (UTC)
- **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트
- **관련 계약**: U-15 · U-15-e · T-81-① · T-81-①-e · §12.3.4-R(v2.10 — 권위 입력
  커밋-전용 소비·R-0 확장) · §12.3.4-T (재동결 커밋 `4fb03470`)
- **run 요약 — 하니스 stdout 의 해당 행과 rc 를 그대로 옮긴다 (해석 아님)**:

| Run | 실행 지점 | 실행 HEAD | 하니스 산출 (원문) | rc |
| --- | --- | --- | --- | --- |
| A 양성 | 본 저장소 (동결 상태) | `4fb03470` | `d0a_entry_state=REBINDING_REQUIRED` / `reason=bound_set_digest 불일치` | `harness_rc=1` |
| B 음성-1 | worktree, 변이 커밋 `1065de35` 후 | `1065de35` | `d0a_entry_state=REBINDING_REQUIRED` / `reason=bound_set_digest 불일치` | `harness_rc=1` |
| C 음성-2 | worktree, 3-커밋 모의 후 | `8ae0574b` | `d0a_entry_state=APPROVAL_STALE` / `reason=승인 이후 변경: cbe502cb…` | `harness_rc=1` |
| D 음성-3 (봉합 실증) | worktree, **미커밋** 권위 위조 후 | `4fb03470` (워킹트리 dirty) | `d0a_entry_state=FREEZE_VIOLATED` / `reason=권위 입력 미커밋 변경: M <ART>;?? <가짜 스탬프>/` | `harness_rc=1` |

**네 run 전부 프로그램이 차단 상태값을 산출하고 비-0 으로 종료했다.** 이 transcript 는
`ENTRY_OK` 를 주장하지 않는다 — 본 저장소의 현행 산출은 `REBINDING_REQUIRED`(6e‴
재결속 대기)다.

---

## 1. 하니스 명령 원문 (§12.3.4-R v2.10 · 생략 없음) + U-15-e (4b) 무결성 결속

- 추출: `git show 4fb03470:<계약 문서>` 의 §12.3.4-R 첫 bash 블록을 awk 로 verbatim
  추출(101행 — `emit()`·`trap EXIT`·커밋-전용 읽기 `git show HEAD:`·`git ls-tree HEAD` 포함).
- **(4b) 무결성 결속**: 워킹트리 문서에서 같은 블록을 독립 재추출해 **diff 무차이** —
  동결본 == 현행본 == 실행본. `bash -n` 문법 검사 통과.
- **sha256(harness210.sh) = `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`**

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

## 2. Run A — 양성 (본 저장소 · 동결 상태)

명령·출력 원문 전문:

```text
runA_utc=2026-08-14T18:51:28Z  runA_head=4fb034705821ea6df82544864248341a881f2242
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness210.sh; echo "harness_rc=$?"
R-0 head=4fb034705821ea6df82544864248341a881f2242
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1
```

하니스 산출(위 원문 그대로): `d0a_entry_state=REBINDING_REQUIRED` ·
`reason=bound_set_digest 불일치` · `harness_rc=1`. 아티팩트가 HEAD 커밋 내용 기준으로
직전 판 digest 를 보유하는 현행 상태(6e‴ 재결속 대기)에서 프로그램이 차단을 산출했다.

---

## 3. Run B — 음성-1 (worktree 변이 · 현행 전제)

### 3.1 실행본 결속

- §12.3.4-T 첫 bash 블록(T-81-①-a~d) verbatim 추출 — 동결본과 diff 무차이이며
  **v2.9 판과 byte-동일**(sha256 `6fa32eaed1af4bb6abeb8ad9a8d73630be542daa867e0ae37c19b7817c34b4cd`).
- sha256(실행본 t81-run-210.sh) = `e6da7a23b3a0f7ededaccd916132cbcd52df74b14f2287406c4c2933a8050ed1`
- 치환(유일): 16행 `bash /path/to/recipe.sh` → `bash <스크래치>/harness210.sh`
  (블록 주석 "(§12.3.4-R 블록을 추출해 recipe.sh 로 저장한 뒤)"의 이행). 치환 외 diff 0.

### 3.2 명령·출력 원문 전문 (bash -x 트레이스)

```text
runB_utc=2026-08-14T18:51:43Z  runB_base_head=4fb034705821ea6df82544864248341a881f2242
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-run-210.sh
+ set -u
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.E1eTXd0rWm/t81
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.E1eTXd0rWm/t81 HEAD
작업 트리 준비 중 (분리된 HEAD 4fb03470)
HEAD의 현재 위치는 4fb03470입니다 docs(tos): phase0 completion contract v2.10 — seal uncommitted-authority forgery
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.E1eTXd0rWm/t81 log -1 --format=%H
4fb034705821ea6df82544864248341a881f2242
+ printf '\n<!-- T-81 mutation: P-0 대리 편집 -->\n'
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.E1eTXd0rWm/t81 commit -am 'T-81-(1) mutation: P-0 proxy edit of upper plan'
[HEAD 분리됨 1065de35] T-81-(1) mutation: P-0 proxy edit of upper plan
 1 file changed, 2 insertions(+)
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.E1eTXd0rWm/t81
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness210.sh
R-0 head=1065de355f947bfc5ccf4b41e4feabd8d1e30ce4
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
+ echo harness_rc=1
harness_rc=1
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.E1eTXd0rWm/t81
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               4fb03470 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-run-210.sh exit=0)
```

하니스 산출(위 원문 그대로): `d0a_entry_state=REBINDING_REQUIRED` · `harness_rc=1`.
변이 커밋 `1065de35` 이 있는 worktree 에서 차단 + rc≠0 — §12.3.4-T «우선순위 차폐»
절이 기술한 그대로다(변이는 R-2 결속 만료로 먼저 잡힌다. `APPROVAL_STALE` 특정 관측은
음성-2 소관).

---

## 4. Run C — 음성-2 (T-81-①-e «전제 충족 모의» · APPROVAL_STALE 특정 관측)

### 4.1 실행본 결속

- T-81-①-e bash 블록 verbatim 추출 — 동결본과 diff 무차이이며 v2.9 판과 byte-동일
  (sha256 `6314a3c0cd69daa165b5b7b3e643a44b4281f8103d6e6d9b87ca8b9b1c1a0d8d`).
- sha256(실행본 t81e-run-210.sh) = `18328da592b304eb66a8e702fb81783d2eec210510cd67cd62455225bc2087a3`
- 실행본 구성(선언): 프롤로그 5행(①-a 형태 WT 확보 — ①-e 는 `$WT` 를 전제하는데
  ①-d 가 직전 worktree 를 제거했으므로 같은 분리-HEAD 계열의 새 worktree.
  `BASE` = `4fb03470` = 변이 전 HEAD) + ①-e 블록 verbatim(치환 유일: 32행
  recipe.sh → harness210.sh, 치환 외 diff 0) + 에필로그 2행(①-d 정리).

### 4.2 명령·출력 원문 전문 (bash -x 트레이스)

```text
runC_utc=2026-08-14T18:52:06Z  runC_base_head=4fb034705821ea6df82544864248341a881f2242
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81e-run-210.sh
+ set -u
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e HEAD
작업 트리 준비 중 (분리된 HEAD 4fb03470)
HEAD의 현재 위치는 4fb03470입니다 docs(tos): phase0 completion contract v2.10 — seal uncommitted-authority forgery
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e log -1 --format=%H
4fb034705821ea6df82544864248341a881f2242
+ set -u
+ BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
+ ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e rev-parse HEAD
+ BASE=4fb034705821ea6df82544864248341a881f2242
+ printf '\n<!-- T-81 mutation -->\n'
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e commit -am 'C1: P-0 proxy mutation'
[HEAD 분리됨 cbe502cb] C1: P-0 proxy mutation
 1 file changed, 2 insertions(+)
++ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e
++ printf '%s\0' docs/plans/2026-08-12-tos-phase0-completion-contract-design.md docs/plans/2026-08-11-tos-completion-development-plan.md
++ LC_ALL=C
++ sort -z -u
++ xargs -0 shasum -a 256
++ shasum -a 256
++ cut '-d ' -f1
+ NEW=5072f46d9889e7f16a73331fa400346daba1929191f9c17c82a48300fef5140d
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e
+ perl -pi -e 's/^bound_set_digest:.*/bound_set_digest: 5072f46d9889e7f16a73331fa400346daba1929191f9c17c82a48300fef5140d/' tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e commit -am 'C2: SIMULATED rebinding (test fixture only)'
[HEAD 분리됨 7cecaf01] C2: SIMULATED rebinding (test fixture only)
 1 file changed, 1 insertion(+), 1 deletion(-)
+ MOCK=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e/docs/reviews/phase0-completion-contract/29991231-235959
+ mkdir -p /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e/docs/reviews/phase0-completion-contract/29991231-235959
+ cat
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e add -A
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e commit -m 'C3: SIMULATED approve verdict (test fixture only)'
[HEAD 분리됨 8ae0574b] C3: SIMULATED approve verdict (test fixture only)
 1 file changed, 6 insertions(+)
 create mode 100644 docs/reviews/phase0-completion-contract/29991231-235959/verdict.md
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness210.sh
R-0 head=8ae0574b5c5ce7de8f4dee8c440af6ef963b5940
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=APPROVAL_STALE
reason=승인 이후 변경: cbe502cb0831712a2ddbd31efc39b70dc456862d 
+ echo harness_rc=1
harness_rc=1
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2AYMiZov81/t81e
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               4fb03470 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81e-run-210.sh exit=0)
```

하니스 산출(위 원문 그대로): `d0a_entry_state=APPROVAL_STALE` ·
`reason=승인 이후 변경: cbe502cb0831712a2ddbd31efc39b70dc456862d` · `harness_rc=1`.

- 3-커밋 모의: C1 변이 `cbe502cb` / C2 SIMULATED 재결속 `7cecaf01` / C3 SIMULATED
  approve verdict `8ae0574b`(모의 스탬프 `29991231-235959`, `reviewed_at_head` =
  `$BASE` = `4fb03470`). **v2.10 하니스는 권위를 HEAD 커밋에서 읽으므로 C2·C3 가
  커밋이어야 보인다** — T-81-①-e 가 이미 커밋 형태라 그대로 성립했다.
- 출력이 보이는 통과 경로: `R-3 verdict=…/29991231-235959` (`git ls-tree HEAD` 우주에서
  사전순 최후) — R-2(C2 의 digest)·R-4(approve/codex)·R-5·R-6(`4fb03470` 조상) 전부
  통과 후 R-7 이 `$BASE..HEAD` 에서 C1 을 발견해 발화. **커밋-전용 읽기 하에서도
  R-7 은 死코드가 아니다.**

---

## 5. Run D — 음성-3 (신규 · v2.10 봉합 실증 — 미커밋 권위 위조)

### 5.1 실행본 구성 (선언 — 문서에 verbatim 블록이 없는 유일한 run)

§12.3.4-R «권위 입력의 커밋-전용 소비» 절이 기술한 위조 ①②를 **그대로** 구성한다:
① 미커밋으로 아티팩트의 `bound_set_digest` 를 현행 재계산값으로 편집 → (v2.9 라면
R-1·R-2 통과) ② 미커밋으로 가짜 최신 스탬프 + verdict.md(adjudicator: codex /
verdict: approve / 경로 정확 / reviewed_at_head=HEAD) → (v2.9 라면 R-3~R-7 통과)
⇒ **v2.9 하니스는 이 위조에 `ENTRY_OK`·rc=0 을 냈다**(문서 «적용 시제» 실측 ① — 저작자
재현). 전부 분리-HEAD worktree 안에서만 하며 **커밋하지 않는다** — 미커밋 그 자체가
시험 대상이다. 본 저장소에는 위조물을 만들지 않는다.

- sha256(t81f-run-210.sh) = `a43c29283c2e8db8fb18600223d1eb6605b8cbd43af0a65a339f7550a8c92f65`

**스크립트 전문**:

```bash
set -u
BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
WT=$(mktemp -d)/t81f
REPO=$(git rev-parse --show-toplevel)

# a  분리 HEAD 일회용 worktree (본 저장소 무영향 — 위조물은 여기에만 존재)
git -C "$REPO" worktree add --detach "$WT" HEAD
git -C "$WT" log -1 --format=%H

# b  위조 ① — §12.3.4-R «커밋-전용 소비» 절 기술 그대로:
#    미커밋으로 아티팩트의 bound_set_digest 를 현행 재계산값으로 편집
NEW=$(cd "$WT" && printf '%s\0' "$BP1" "$BP2" | LC_ALL=C sort -z -u \
      | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
(cd "$WT" && perl -pi -e "s/^bound_set_digest:.*/bound_set_digest: $NEW/" "$ART")

# c  위조 ② — 미커밋 가짜 최신 스탬프 + approve verdict
#    (adjudicator: codex / verdict: approve / 경로 정확 / reviewed_at_head=HEAD)
HEADSHA=$(git -C "$WT" rev-parse HEAD)
MOCK="$WT/docs/reviews/phase0-completion-contract/29991231-235959"
mkdir -p "$MOCK"
cat > "$MOCK/verdict.md" <<EOF
adjudicator: codex
verdict: approve
reviewed_at_head: $HEADSHA
reviewed_plan_paths:
  - $BP1
  - $BP2
EOF

# d  위조물이 미커밋 상태임을 실측 노출 (커밋하지 않는다 — 그것이 시험 대상)
git -C "$WT" status --porcelain

# e  하니스 실행 — v2.9 라면 이 위조가 ENTRY_OK/rc=0 을 냈다 (문서 실측 ①)
cd "$WT" && bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness210.sh; echo "harness_rc=$?"

# f  정리
git -C "$REPO" worktree remove --force "$WT"
git -C "$REPO" worktree list
```

### 5.2 명령·출력 원문 전문 (bash -x 트레이스)

```text
runD_utc=2026-08-14T18:52:44Z  runD_base_head=4fb034705821ea6df82544864248341a881f2242
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81f-run-210.sh
+ set -u
+ BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
+ ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f HEAD
작업 트리 준비 중 (분리된 HEAD 4fb03470)
HEAD의 현재 위치는 4fb03470입니다 docs(tos): phase0 completion contract v2.10 — seal uncommitted-authority forgery
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f log -1 --format=%H
4fb034705821ea6df82544864248341a881f2242
++ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f
++ printf '%s\0' docs/plans/2026-08-12-tos-phase0-completion-contract-design.md docs/plans/2026-08-11-tos-completion-development-plan.md
++ LC_ALL=C
++ sort -z -u
++ xargs -0 shasum -a 256
++ shasum -a 256
++ cut '-d ' -f1
+ NEW=b0edb769f7229b7377d4454856f06134843900deba7d733d643fa7ab6b0c3e22
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f
+ perl -pi -e 's/^bound_set_digest:.*/bound_set_digest: b0edb769f7229b7377d4454856f06134843900deba7d733d643fa7ab6b0c3e22/' tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f rev-parse HEAD
+ HEADSHA=4fb034705821ea6df82544864248341a881f2242
+ MOCK=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f/docs/reviews/phase0-completion-contract/29991231-235959
+ mkdir -p /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f/docs/reviews/phase0-completion-contract/29991231-235959
+ cat
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f status --porcelain
 M tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
?? docs/reviews/phase0-completion-contract/29991231-235959/
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness210.sh
R-0 head=4fb034705821ea6df82544864248341a881f2242
d0a_entry_state=FREEZE_VIOLATED
reason=권위 입력 미커밋 변경:  M tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md;?? docs/reviews/phase0-completion-contract/29991231-235959/;
+ echo harness_rc=1
harness_rc=1
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ltFczgzR6r/t81f
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               4fb03470 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81f-run-210.sh exit=0)
```

하니스 산출(위 원문 그대로): `d0a_entry_state=FREEZE_VIOLATED` ·
`reason=권위 입력 미커밋 변경:  M tos-spec/…/OQ-11-DISPOSITION.md;?? docs/reviews/…/29991231-235959/;`
· `harness_rc=1`.

- worktree 의 `git status --porcelain` 이 위조물 2건( M ART · ?? 가짜 스탬프)을 실측
  노출했고, **확장된 R-0 이 그 둘을 정확히 열거하며 차단**했다 — 문서 실측 ③(층 1+층 2 =
  `FREEZE_VIOLATED`, 우선순위 2 가 3 을 앞선다)과 일치.
- **이것이 봉합 실증이다**: 같은 위조가 v2.9 에서는 `ENTRY_OK`·rc=0(문서 실측 ① — 독립
  검증이 재현했던 형태), v2.10 에서는 `FREEZE_VIOLATED`·rc=1. `ENTRY_OK` 또는 rc=0 이
  나왔다면 봉합 실패로 보고했을 것이다 — 나오지 않았다.

---

## 6. 정리 · 본 저장소 무영향 · 모의물/위조물 누출 방지

```text
=== 사후 검증 (2026-08-14T18:53:12Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               4fb03470 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
4fb03470 docs(tos): phase0 completion contract v2.10 — seal uncommitted-authority forgery
-- 실행 전 스냅샷 대조 --
status: 실행 전과 byte-동일
-- worktree 커밋(변이·모의) 도달성 — refs 전수 대조 --
$ git log --all --format=%H | grep -c -e 1065de35 -e cbe502cb -e 7cecaf01 -e 8ae0574b
0
= 4건(1065de35·cbe502cb·7cecaf01·8ae0574b) 전부 어떤 ref 에서도 도달 불가
-- 본 저장소 위조물·모의 스탬프 부재 --
$ ls docs/reviews/phase0-completion-contract/ | grep 2999
(출력 없음 = 부재)
$ git status --porcelain -- tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
(출력 없음 = ART 무변경)
-- mktemp 잔여 정리 --
본 임무의 mktemp 부모 3건(tmp.E1eTXd0rWm=Run B · tmp.2AYMiZov81=Run C · tmp.ltFczgzR6r=Run D)
전부 제거 확인 (ls: 없음). [정정 기록] 최초 정리 명령이 글롭(tmp.*/)으로 시스템 임시
디렉터리 전체를 rmdir 대상으로 삼는 실수가 있었다 — rmdir 은 빈 디렉터리만 제거하므로
타 프로세스의 비어 있지 않은 디렉터리에는 실해가 없고(전부 잔존 확인), 본 임무 소유
3건의 제거는 개별 ls 로 재확인했다. 잔존 tmp.* 는 본 임무와 무관한 기존 항목이다.
```

- worktree 3건(t81·t81e·t81f) 전부 `remove --force` 완료 — `git worktree list` 잔여
  없음(목록의 `futures-risk-hardening-design`·orca 2건은 실행 전부터 존재하는 별개
  worktree). 본 저장소 status(` M uv.lock` / `?? tools/spikes/` — 이전부터 존재)·HEAD
  (`4fb03470`) 실행 전 스냅샷과 byte-동일.
- worktree 커밋 4건(`1065de35`·`cbe502cb`·`7cecaf01`·`8ae0574b`) refs 전수 대조 0건 —
  어떤 ref 에서도 도달 불가. 본 저장소에 `29991231-*` 스탬프 부재·ART 무변경.
  Run D 의 위조물은 미커밋이었고 worktree 제거와 함께 소멸했다.

---

## 7. v2.9 transcript(커밋 2b6f5eeb 보존분) 와의 차이

```text
v2.9 transcript   3-run (A 양성 / B 음성-1 / C 음성-2).  상태값·rc 는 프로그램 산출
                  이었으나, 하니스가 권위 입력(ART·verdict)을 워킹트리에서 읽어
                  **미커밋 위조로 ENTRY_OK·rc=0 을 만들 수 있는 판**의 기록이었다
                  (stop-time 적발 — 실행 당시에는 그 위조를 시험하지 않았으므로
                  세 run 의 관측 자체는 유효하되, 하니스의 부정 보증이 불완전했다).

이 transcript     v2.10 하니스(커밋-전용 소비 + R-0 확장)로 4-run 재생성.
                  A·B·C 는 v2.9 와 같은 상태값·rc 를 재산출(봉합이 정상 경로를
                  바꾸지 않음을 겸증)했고, **신규 Run D 가 그 위조 자체를 실행해
                  FREEZE_VIOLATED·rc=1 로 차단됨을 실증**했다 — "위조 가능"의
                  적발을 "위조가 차단된다"의 실행 증거로 닫는 run 이 추가된 것이
                  핵심 차이다.
```

**소비 조건(U-15-e (5)) 자기 기록**: 이 transcript 의 HEAD 는 `4fb03470` 이다. 진입
시점에 그 이후 `bound_paths` 를 건드린 커밋이 있으면 이 transcript 는 stale 이며 진입
거부다. 현행 산출이 `REBINDING_REQUIRED` 이므로, 6e‴ 재결속과 레인 B `approve` 취득 후
**그 시점 HEAD 에서 하니스를 재실행한 새 transcript** 가 필요하다 — 이 파일은 그 시점의
`ENTRY_OK` 를 주장하지 않는다.
