# U15-ENTRY-CHECK — 진입 점검 레시피 실행 transcript (pre-D0-A · 1단 강제 지점)

- **목적**: 레인 B v2.7 재심 verdict(`20260814-110807`) next_steps — "U-15가 D0-A 구현 전에
  실제 진입을 거부하는 실행 증거" — 의 이행. §12.3.4-R 레시피와 §12.3.4-T(T-81-①)를
  문자 그대로 실행해 명령 원문·출력 원문·실행 HEAD·상태값을 U-15-e (1)~(4) 결속으로 남긴다.
- **생성 시각**: 2026-08-14T02:59:16Z (UTC)
- **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트 (레시피 실행 주체 = 절차를 수행하는
  오케스트레이터 레인 — §12.3.4-R "새 소유자 지명 아님")
- **관련 계약**: U-15 · U-15-e · T-81-① · §12.3.4-R · §12.3.4-T
  (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md v2.8)
- **run 요약**:

| Run | 시점 | HEAD | 상태값 | 역할 |
| --- | --- | --- | --- | --- |
| 1 | 동결 전 | `3a9d50d7` | **FREEZE_VIOLATED** (차단) | T-81-⑦(동결 위반) 조건의 실기록 |
| 2 | 동결 전 | `3a9d50d7` (+worktree `bfa4844d`) | 양성: R-7 공집합 / 음성: **APPROVAL_STALE** (거부) | T-81-① 양성·음성 쌍 (뮤테이션 증거) |
| 3 | 동결 후 | `03262ef7` | **REBINDING_REQUIRED** (차단) | 현행 정직 상태 — 6e‴ 재결속 대기 |

이 transcript 는 어느 run 에서도 `ENTRY_OK` 를 주장하지 않는다.

---

## 1. 레시피 명령 원문 (§12.3.4-R · 생략 없음)

- 추출: 계약 문서 §12.3.4-R 의 bash 블록을 sed(행 4191–4226)로 verbatim 추출,
  awk 독립 추출본과 **diff 무차이** 교차 검증.
- 추출 시점은 동결 전 워킹트리였으나, **동결 커밋 `03262ef7` 내 동일 블록과 byte-동일**임을
  `git show 03262ef7:<계약 문서>` 재추출 diff 로 확증 — 실행된 레시피 == 동결된 레시피.
- sha256(recipe.sh) = `4b837351f0a117bcf4918f3e84f67d8b1dd37515553499c62d81839e909bc0b6`

```bash
set -u
BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md

# R-0  실행 시점 결속
git rev-parse HEAD
git status --porcelain -- "$BP1" "$BP2"        # 기대: 출력 없음 (동결 확인)

# R-1  bound_paths 집합이 계약이 요구하는 그 둘인가          [U-12 (iii)]
grep -A3 '^bound_paths:' "$ART"                # 기대: 정확히 BP1·BP2, 더도 덜도 아님

# R-2  bound_set_digest 재계산 == 아티팩트 보유값             [U-12 (iv)]
printf '%s\0' "$BP1" "$BP2" | LC_ALL=C sort -z -u \
  | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1
grep '^bound_set_digest:' "$ART"               # 기대: 두 값 동일
grep '^disposition:' "$ART"                    # 기대: 판정 어휘 4종 중 하나  [U-12 (ii)]

# R-3  최신 verdict 스탬프 확정
VD=$(ls -1d docs/reviews/phase0-completion-contract/2026*/ | LC_ALL=C sort | tail -1)
echo "$VD"

# R-4  승인 어휘·심판 계열                                    [U-15-b (1)]
grep -E '^(adjudicator|verdict):' "$VD/verdict.md"
                                               # 기대: codex / approve

# R-5  심사 범위 == 요구 결속 경로 집합                        [U-15-b (2)]
grep -A3 '^reviewed_plan_paths:' "$VD/verdict.md"
                                               # 기대: 정확히 BP1·BP2

# R-6  reviewed_at_head 가 HEAD 의 조상인가                    [U-15-b (3)]
RH=$(grep '^reviewed_at_head:' "$VD/verdict.md" | awk '{print $2}')
git merge-base --is-ancestor "$RH" HEAD; echo "ancestor_rc=$?"   # 기대: 0

# R-7  승인 이후 bound_paths 를 건드린 커밋 — 공집합인가        [U-15-b (4)]
git log --oneline "$RH"..HEAD -- "$BP1" "$BP2"  # 기대: 출력 없음
```

---

## 2. Run 1 — 동결 전 (기대 상태값 FREEZE_VIOLATED 의 실기록)

- 실행 시각: 2026-08-14T02:52:03Z (UTC)
- 실행 HEAD: `3a9d50d71d91061c6ff6315ff954ce44f6b99a53`
- 실행: repo 루트에서 `bash recipe.sh` (exit=0 — exit 코드는 마지막 명령의 것이며 판정은 출력 대조로 한다)

**출력 원문 전문**:

```text
3a9d50d71d91061c6ff6315ff954ce44f6b99a53
 M docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
bound_paths:            # repo 루트 기준 상대경로. `./` 접두 금지 (표기가 digest 에 실린다)
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
requesting_plan_version: v2.7
2e965b119df950837b40aedec3435d58d5b2b16a5f86c1ae9551d5ea010291b0
bound_set_digest: ac515d85d29bd31ea354f8440bd49b324b7ffb5a2c9d1928acb1b5974e47f43e
disposition: RESOLVED_MAPPING_APPROVED
docs/reviews/phase0-completion-contract/20260814-110807/
adjudicator: codex
verdict: needs-attention
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: e270f98707e11deeb2aacf6f07fe32b996d1d3d57edb49b070f84c5ccd89f964
ancestor_rc=0
```

**판정 (fail-closed)**: 상태값 = **FREEZE_VIOLATED (차단)**

- **R-0 비공집합**: ` M docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`
  — bound_paths 에 미커밋 변경(v2.8 설계 문서). 동결되지 않은 내용에 대한 승인은 존재할 수
  없고(O-1), 이 상태로 계산한 R-2 digest 는 어느 커밋 내용도 가리키지 않는다.
- 동시 관측된 차단 축 (기록용 — 상태값은 R-0 이 선행):
  - R-2 불일치: 재계산 `2e965b119df950837b40aedec3435d58d5b2b16a5f86c1ae9551d5ea010291b0`
    ≠ 보유 `ac515d85d29bd31ea354f8440bd49b324b7ffb5a2c9d1928acb1b5974e47f43e` (REBINDING_REQUIRED 축)
  - R-4: `verdict: needs-attention` (`adjudicator: codex` 는 일치 — APPROVAL_NOT_APPROVE 축)
- 기대 일치 항: R-1 bound_paths 정확히 2건 · disposition `RESOLVED_MAPPING_APPROVED` ·
  R-3 최신 스탬프 `20260814-110807` · R-5 reviewed_plan_paths 정확히 BP1·BP2 ·
  R-6 `ancestor_rc=0` · R-7 공집합.

**이 run 의 역할**: T-81-⑦(동결 위반) 대조군 조건 — "bound_paths 에 미커밋 변경을 둔 채
레시피를 실행 → `FREEZE_VIOLATED` 차단" — 이 실제 실행에서 성립함의 실기록이다.
(v2.8 이 이 상태값을 신설한 계기인 "독립 검증자가 실제로 밟은 조건"의 재현이기도 하다.)

---

## 3. Run 2 — T-81-① 실행 절차 (§12.3.4-T · 양성·음성 쌍)

### 3.1 실행 스크립트 결속

- §12.3.4-T bash 블록 verbatim 추출(sed 행 4284–4306, awk 독립 추출 diff 무차이,
  동결 커밋 `03262ef7` 내 블록과 byte-동일 확증).
- sha256(치환 전 원문 t81-raw.sh) = `c33b771f8d30a7cbd4a5906b06602274c0f9640f340035dd0afcbc8d15c92243`
- sha256(치환 후 실행본 t81.sh) = `04183e84684b938095224c1c9125eaaf30176d3a4af99f7605e5cbbda486f604`
- 플레이스홀더 치환 (유일한 변경 — 치환 외 diff 0):
  - 치환 전 (15행): `RH=<R-3 에서 얻은 reviewed_at_head>`
  - 치환 후 (15행): `RH=5bd097d791c8d52069c66fdb10c81801a9590eb8`
  - 치환 근거: R-3 최신 스탬프 `docs/reviews/phase0-completion-contract/20260814-110807/verdict.md:7`
    의 `reviewed_at_head: 5bd097d791c8d52069c66fdb10c81801a9590eb8` — 실행 직전 grep 재확인.

**실행본 원문 (t81.sh · 생략 없음)**:

```bash
set -u
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
WT=$(mktemp -d)/t81
REPO=$(git rev-parse --show-toplevel)

# T-81-①-a  분리 HEAD 일회용 worktree (브랜치를 만들지 않는다 — 본 저장소 무영향)
git -C "$REPO" worktree add --detach "$WT" HEAD
git -C "$WT" log -1 --format=%H

# T-81-①-b  P-0 를 대리하는 변이 — 상위 계획(= bound_paths 의 하나)을 편집·커밋
printf '\n<!-- T-81 mutation: P-0 대리 편집 -->\n' >> "$WT/$BP2"
git -C "$WT" commit -am 'T-81-(1) mutation: P-0 proxy edit of upper plan'

# T-81-①-c  같은 승인(R-3 의 스탬프)으로 레시피 R-7 을 재실행
RH=5bd097d791c8d52069c66fdb10c81801a9590eb8
git -C "$WT" log --oneline "$RH"..HEAD -- \
  docs/plans/2026-08-12-tos-phase0-completion-contract-design.md "$BP2"
#   기대: **비공집합** (방금 만든 변이 커밋 1건) → APPROVAL_STALE → **진입 거부**
#   여기서 출력이 비면 T-81-① 실패 = U-15 가 stale 승인을 막지 못한다

# T-81-①-d  정리
git -C "$REPO" worktree remove --force "$WT"
git -C "$REPO" worktree list          # 기대: 잔여 worktree 없음
```

### 3.2 실행 기록 (명령·출력 원문 — 음성 레그는 bash -x 트레이스 전문)

- 실행 시각: 2026-08-14T02:53:20Z (UTC, 치환·기준선 스냅샷) ~ 02:54 (실행·검증)
- 본 저장소 HEAD: `3a9d50d71d91061c6ff6315ff954ce44f6b99a53`

```text
=== Run 2 양성 레그 (변이 전 · 본 저장소 · HEAD 3a9d50d71d91061c6ff6315ff954ce44f6b99a53) ===
$ git log --oneline 5bd097d791c8d52069c66fdb10c81801a9590eb8..HEAD -- docs/plans/2026-08-12-tos-phase0-completion-contract-design.md docs/plans/2026-08-11-tos-completion-development-plan.md
(exit=0, 출력 행 수: 0)

=== Run 2 음성 레그 (변이 후 · 일회용 분리-HEAD worktree · bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81.sh) ===
+ set -u
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MnxqVkFOTx/t81
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MnxqVkFOTx/t81 HEAD
작업 트리 준비 중 (분리된 HEAD 3a9d50d7)
HEAD의 현재 위치는 3a9d50d7입니다 docs(tos): record lane B v2.7 re-review verdict (NOT_PASSED, 3 residual highs)
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MnxqVkFOTx/t81 log -1 --format=%H
3a9d50d71d91061c6ff6315ff954ce44f6b99a53
+ printf '\n<!-- T-81 mutation: P-0 대리 편집 -->\n'
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MnxqVkFOTx/t81 commit -am 'T-81-(1) mutation: P-0 proxy edit of upper plan'
[HEAD 분리됨 bfa4844d] T-81-(1) mutation: P-0 proxy edit of upper plan
 1 file changed, 2 insertions(+)
+ RH=5bd097d791c8d52069c66fdb10c81801a9590eb8
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MnxqVkFOTx/t81 log --oneline 5bd097d791c8d52069c66fdb10c81801a9590eb8..HEAD -- docs/plans/2026-08-12-tos-phase0-completion-contract-design.md docs/plans/2026-08-11-tos-completion-development-plan.md
bfa4844d T-81-(1) mutation: P-0 proxy edit of upper plan
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MnxqVkFOTx/t81
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               3a9d50d7 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81.sh exit=0)

=== Run 2 사후 검증 (본 저장소 무영향) ===
$ git worktree list  # t81 worktree 잔여 없음 확인 (위 출력과 동일 — futures-risk-hardening-design·orca 2건은 실행 전부터 존재하는 별개 worktree)
/Users/harris/Development/private/kis_unified_sts                                               3a9d50d7 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
 M docs/plans/INDEX.md
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
3a9d50d7 docs(tos): record lane B v2.7 re-review verdict (NOT_PASSED, 3 residual highs)
-- 실행 전 스냅샷과 대조 --
status/HEAD: 실행 전 스냅샷과 byte-동일
-- mktemp 잔여 정리 --
빈 mktemp 부모 디렉터리 제거됨
```

### 3.3 판정

- **양성 레그 (변이 전 · 본 저장소)**: R-7 = **공집합** (출력 0행) — 당시 HEAD `3a9d50d7`
  기준으로 승인 이후 bound_paths 를 건드린 커밋 없음.
- **음성 레그 (변이 후 · 분리-HEAD worktree)**: 상위 계획 편집·커밋 **`bfa4844d`** 후
  같은 RH 로 R-7 재실행 → **비공집합** (`bfa4844d T-81-(1) mutation: P-0 proxy edit of
  upper plan`) = **APPROVAL_STALE = 진입 거부**. 뮤테이션이 실제로 red 를 만든다 —
  §8 이 전 대조군에 요구하는 실행 확인이다.
- **정리·무영향**: `worktree remove --force` 후 `git worktree list` 에 t81 worktree 잔여
  없음 (목록의 `futures-risk-hardening-design`·orca 2건은 실행 전부터 존재하는 별개
  worktree — 본 실행과 무관). 본 저장소 `git status --short`·`git log --oneline -1` 이
  실행 전 스냅샷과 **byte-동일**. 변이 커밋은 분리 HEAD 였으므로 어떤 ref 에도 도달하지
  않는다.

> **정직 노트 — 이 run 은 진입용 transcript 가 아니다.** 이 run 의 HEAD(`3a9d50d7`)는
> 동결 커밋(`03262ef7`) **이전**이고, 동결 커밋 자체가 bound_paths 를 건드리므로
> U-15-e (5) 기준으로 이 run 은 현 시점 진입에 대해 **stale** 이다. 역할은 `ENTRY_OK`
> 주장이 아니라 **T-81 뮤테이션 증거**다. 같은 이유로 양성 레그의 R-7 공집합은
> **동결 커밋 전에만 성립 가능했다** — 동결 커밋 이후 같은 명령은 그 커밋 자체를
> 관측한다 (Run 3 의 R-7 이 그 실측이다).

---

## 4. Run 3 — 동결 후 (현행 정직 상태)

- 실행 시각: 2026-08-14T02:56:34Z (UTC)
- 실행 HEAD: `03262ef71607c5ddad51a25ce2dd569d7a8fec36` (동결 커밋 — v2.8 설계 문서 + INDEX)
- 실행: repo 루트에서 `bash recipe.sh` (exit=0 — 판정은 출력 대조)

**출력 원문 전문**:

```text
03262ef71607c5ddad51a25ce2dd569d7a8fec36
bound_paths:            # repo 루트 기준 상대경로. `./` 접두 금지 (표기가 digest 에 실린다)
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
requesting_plan_version: v2.7
2e965b119df950837b40aedec3435d58d5b2b16a5f86c1ae9551d5ea010291b0
bound_set_digest: ac515d85d29bd31ea354f8440bd49b324b7ffb5a2c9d1928acb1b5974e47f43e
disposition: RESOLVED_MAPPING_APPROVED
docs/reviews/phase0-completion-contract/20260814-110807/
adjudicator: codex
verdict: needs-attention
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: e270f98707e11deeb2aacf6f07fe32b996d1d3d57edb49b070f84c5ccd89f964
ancestor_rc=0
03262ef7 docs(tos): phase0 completion contract v2.8 — entry recipe, DAG uniqueness, approval binding
```

**판정 (fail-closed)**: 상태값 = **REBINDING_REQUIRED (차단)**

- **R-0 공집합**: bound_paths 두 파일에 대해 `git status --porcelain` 출력 없음 — **동결 확인**.
  (워킹트리의 `uv.lock` M 등은 bound_paths 밖이라 R-0 의 관측 대상이 아니다.)
- **R-2 불일치 (상태값 근거)**: 재계산
  `2e965b119df950837b40aedec3435d58d5b2b16a5f86c1ae9551d5ea010291b0` ≠ 보유
  `ac515d85d29bd31ea354f8440bd49b324b7ffb5a2c9d1928acb1b5974e47f43e` → 6e‴ 재결속 대기.
- 동시 관측된 차단 축 (기록용):
  - R-4: `verdict: needs-attention` (APPROVAL_NOT_APPROVE 축) — v2.8 은 아직 재심 전.
  - R-7: **비공집합** — `03262ef7 docs(tos): phase0 completion contract v2.8 — entry
    recipe, DAG uniqueness, approval binding`. **구조상 필연**이다: 동결 커밋 자체가
    bound_paths 를 건드리므로 구 승인(`reviewed_at_head: 5bd097d7`) 기준 APPROVAL_STALE
    축이 성립한다. 이것이 O-6(재결속 규율은 bound_paths 를 건드리는 모든 단계에 적용)의
    실측이며, 재결속·재심으로 새 verdict 가 나오면 RH 가 갱신되어 해소된다.
- 기대 일치 항: R-1 · disposition · R-3(`20260814-110807`) · R-5 · R-6(`ancestor_rc=0`).

**함의**: 현행 상태는 "평가 불가"가 아니라 **평가돼서 거부**다(§12.3.4 v2.8 서술의 실측).
6e‴ 재결속(OQ-11-DISPOSITION 갱신)과 레인 B 재심 `approve` 취득 후, **그 시점 HEAD 에서
레시피를 재실행한 새 transcript** 가 필요하다 — **이 파일은 그 시점의 `ENTRY_OK` 를
주장하지 않으며, 주장할 수도 없다** (U-15-e (5): 이 transcript 의 HEAD 이후 bound_paths
커밋이 생기는 순간 이 transcript 도 stale 이다).

---

## 5. 말미 관측 (레시피 자체에 대한 실행 중 발견 + 배치 연대기)

1. **배치 연대기 — 두 번의 stop-time 심판 적발과 확정 배치**. 두 적발 모두 이 실행
   레인 밖의 **stop-time 심판(자동 게이트)** 이 냈다 — 저작 레인의 자기 점검이 아니다.
   - **(1차 이탈 — 적발됨)** 초기 배치는 R-3 glob(`ls -1d …/2026*/ | tail -1`)과의
     충돌 우려 — verdict.md 없는 디렉터리가 `2026*` 에 걸리면 최신 스탬프로 오인된다 —
     를 이유로 비충돌 이름 `evidence-20260814-u15-entry-check/` 를 발명했다. 그러나
     계약 §12.3.4 와 §12.3.4-T 증거 보존 절이 명시한 경로는
     `docs/reviews/phase0-completion-contract/<ts>/U15-ENTRY-CHECK.md` 이며, stop-time
     심판이 이 이탈을 적발했다("README 의 새 증거 경로가 U-15 계약과 충돌"). 정정
     독해: `<ts>` = **이 증거가 소비한 verdict 의 스탬프**. 이 transcript 는 RH 를
     `20260814-110807/verdict.md` 에서 가져왔으므로 정본은 현 위치다. 스탬프
     디렉터리에는 verdict.md 가 이미 있으므로 R-3 glob 과 충돌하지 않는다 — 우려했던
     "verdict.md 없는 디렉터리"는 이 독해에서 생기지 않는다.
   - **(2차 이탈 — 적발됨)** 1차 정정 때 추적 경로 정본에 더해 **`.omc/review/<ts>/`
     에 byte-동일 미러**를 만들었다(README 의 `diff -r` 불변식을 제외 규칙 없이
     세우려는 발명). stop-time 심판이 재적발했다: codex-gate 의 직전 판정 탐색은
     `ls -1dt .omc/review/*/`(**mtime 순**)이므로 **스탬프 디렉터리에의 사후 쓰기는
     디렉터리 mtime 을 갱신해 탐색 순서를 오염**시킨다 — 이번 대상은 최신 스탬프라
     무해했지만, 관행이 되면 옛 스탬프에의 증거 미러가 그것을 "직전 판정"으로
     승격시킨다. 그리고 **계약이 명시한 보존처는 추적 경로뿐**이다 — `.omc` 사본은
     계약 요구가 아니었다. 미러는 삭제됐고, 오염됐던 `.omc` 스탬프 디렉터리 mtime 은
     그 안의 verdict.md mtime 으로 복원했다(발명값 아님 — 실재 파일에서 파생).
   - **(확정 배치)** 정본 = 계약 경로 그대로, **추적 전용**
     (`docs/reviews/phase0-completion-contract/20260814-110807/U15-ENTRY-CHECK.md`).
     `.omc/review/` 쪽은 codex-gate 가 쓴 것 외에 아무것도 추가하지 않는다. README 의
     diff 불변식은 증거 파일명 명명 제외로 성립한다:
     `diff -r --exclude=README.md --exclude=U15-ENTRY-CHECK.md .omc/review
     docs/reviews/phase0-completion-contract` → 무출력 (실측). 기존 verdict.md 는 어느
     단계에서도 수정되지 않았다 — 스탬프 디렉터리에 sibling 파일을 추가했을 뿐이다.
   - **연대기의 산출 규칙**: ① **`.omc` 스탬프 불가침** — codex-gate 스탬프 디렉터리에
     사후 쓰기 금지(mtime = 탐색 순서 자료이므로 쓰기 자체가 오염이다) ② 계약이
     `<ts>` 의 지시 대상(= 소비된 verdict 스탬프)을 명문으로 못박으면 1차 오독
     클래스가 재발하지 않는다 — 다음 개정 후보로 기록한다.
2. **이 파일 자신의 결속 영향**: 이 파일(`docs/reviews/phase0-completion-contract/
   20260814-110807/U15-ENTRY-CHECK.md`)은 bound_paths(계약 문서·상위 계획) **밖**이므로,
   이 파일의 생성·커밋은 R-0(동결)도 R-7(approval currency)도 깨지 않는다.
3. **재현성**: 본 transcript 의 (1) 명령 원문 + (3) HEAD 로 누구든 같은 커밋에서 같은
   명령을 재실행해 출력을 대조할 수 있다(§5.2.5 `SUBSTANTIVE` — 재파생 소스가 git 이력과
   실재 아티팩트다). Run 2 음성 레그의 worktree 커밋(`bfa4844d`)은 unreachable object 라
   gc 후 재현 시 커밋 해시가 달라질 수 있으나, **비공집합이라는 관측**은 절차 재실행으로
   동일하게 재파생된다.
