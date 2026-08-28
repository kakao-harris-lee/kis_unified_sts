# U15-ENTRY-CHECK — v2.13 T-81 ⑬⑭⑮ 실행 transcript (pre-D0-A · U-15-f-4 / U-15-g)

- **목적**: 레인 B v2.12 재심 verdict(`20260815-144959`, NOT_PASSED)의 next_steps —
  "U-15 비가드·HEAD 변경 억제를 **실제 소비자 대조군**으로 확인" — 의 이행.
  v2.13(동결 커밋 `8a25c3c0`)이 신설한 **U-15-f-4 부모 결속**과 **U-15-g CORR(d)
  사후 관측 소비 계약**의 대조군 **T-81 ⑬(HEAD 이동)·⑭(비가드 착수)·⑮(전진-머지
  우회)** 를 실행해 U-15-e (1)~(6)·(4b)·(4c) 결속으로 남긴다.
- **생성 시각**: 2026-08-15T06:42:33Z (UTC)
- **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트
- **관련 계약**: U-15-f-4(부모 결속 — transcript 의 `R-0 head=` 소비) · U-15-g
  (CORR(d) 술어 — **판정값까지 소비**·5상태·`NOT_STARTED` 만 비차단) · U-15-e (4c)
  (`R-0 head=<40hex>` 리터럴 + 기록 상태값 = 산출 요건) · §12.3.4-R·G · T-81 ⑬⑭⑮
  (동결 커밋 `8a25c3c0`)
- **run 요약 — 기계 관측 결과를 그대로 옮긴다 (해석 아님)**:

| Run | 구성 | 기계 관측 | 판정 |
| --- | --- | --- | --- |
| ⑬ HEAD 이동 | ENTRY_OK(R-0 head=`e64db5f5`) 후 무관 커밋 `7eff934b` 로 HEAD 이동 → D0A-FIRST `984eeb59` | `parent(d)=7eff934b…` ≠ 하니스 평가 HEAD `e64db5f5…` | **U-15-f-4 위반 = `PARENT_MISMATCH` 기계 관측** (T-81 ⑬ 통과) |
| ⑭ 비가드 착수 | 하니스 미실행 D0A-FIRST(parent=`8a25c3c0`) | 조건 (2) 매치 transcript 0건 → **\|CORR(d)\| = 0** | **`TRANSCRIPT_MISSING`(차단) 실제 도달** — 초안 반증("도달 불가") 봉합 확인 (T-81 ⑭ 통과) |
| ⑮ 전진-머지 우회 | D0A-FIRST(parent=`cf9b0295` — 기존 transcript 의 R-0 head 와 **리터럴 일치**) + 전진 머지 `2ac84bb5` | 조건 (2)는 `20260815-092111` 매치, 조건 (3)에서 그 head 의 기록 상태 전부 `REBINDING_REQUIRED` → **\|CORR(d)\| = 0** | **차단(red) 실측** — 초안 술어라면 `ENTRY_PROVENANCE_CLEAR` 통과였을 구성 (T-81 ⑮ 통과) |

세 관측 모두 **worktree 안 재현**이며, 본 저장소는 D0-A 미착수 불변이다(§7 실측).
이 transcript 는 본 저장소의 `ENTRY_OK` 도 `ENTRY_PROVENANCE_CLEAR` 도 주장하지 않는다 —
본 저장소 현행 하니스 산출은 `REBINDING_REQUIRED`(§2), 사후 관측은 `NOT_STARTED`
(도입 커밋 ∅ — §7)다.

---

## 1. 하니스 명령 원문 (§12.3.4-R v2.13 · 생략 없음) + U-15-e (4b) 무결성 결속

- 추출: `git show 8a25c3c0:<계약 문서>` §12.3.4-R 첫 bash 블록 verbatim(101행).
  워킹트리 재추출과 **diff 무차이** · `bash -n` 통과 · **v2.12(및 v2.11·v2.10)
  하니스와 byte-동일**(v2.13 도 계약 산문만 수정).
- **sha256(harness213.sh) = `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`**
- §12.3.4-G 블록(47행 — **G-부모 단계 포함**)도 verbatim 추출·동결본 일치 확인:
  sha256 = `21f532b31792b332e5a31116a4d644e988bb3ac775f7dc5ec38e8f1a3661409d`
  (Run ⑬의 %P 대조는 이 블록의 G-부모 단계 형태를 따른다)

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

## 2. 전제 실측 («전제 차이» 규칙 적용 — Run ⑬의 ENTRY_OK 전제)

```text
=== 전제 실측 (§12.3.4-G 규칙: 어느 R-단계가 이미 통과하는가를 먼저 적는다) ===
실측 시각: 2026-08-15T06:37:41Z · HEAD: 8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa

[실측 1] 동결 HEAD 에서 하니스 실행:
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness213.sh; echo "harness_rc=$?"
R-0 head=8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1

[실측 2] R-2 보유값 vs 재계산값:
bound_set_digest: 934516a67b52a9f8724c2516e8bfbccbb6da1a986674e2b540c08ca71853a03f
796ca1e0a5b7ff8499e38b5322ff579b63dc643b6af6ec9cf3483dbeacaf6919

[실측 3] R-4 상태 — HEAD 트리 최신 스탬프와 verdict 어휘:
docs/reviews/phase0-completion-contract/20260815-144959
adjudicator: codex
verdict: needs-attention

[귀결] R-0·R-1 통과(하니스가 R-2 에서 발화) · R-2 미충족 · R-4 미충족(needs-attention).
       => post-freeze 2-커밋 모의(C1 SIMULATED 재결속 + C2 SIMULATED approve) — «전제 차이» 표 그대로.
```

---

## 3. Run ⑬ — HEAD 이동 (U-15-f-4 부모 불일치)

### 3.1 실행 스크립트 (저작 선언 — T-81 ⑬ 정의의 이행, sha256 아래)

T-81 ⑬ 정의("하니스를 통과시킨 뒤 가드 우변 실행 전에 무관한 커밋을 하나 올려 HEAD 를
옮기고 D0A-FIRST 를 커밋 → `git log --format=%P -1` 이 transcript 의 `R-0 head=` 와
달라야 한다")를 절차화했다. 전제 모의는 «전제 차이» 표 post-freeze 2-커밋, D0A-FIRST
형태와 %P 대조는 §12.3.4-G 블록 차용. 무관 커밋은 빈 커밋(SIMULATED 표기 — 아무
파일도 건드리지 않아 "무관"이 구조적으로 보장된다).
sha256(t81-13.sh) = `104cf5b931174aa91427893f9f7df55165088905207b6238d3c10dd795c91129`

```bash
set -u
BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
WT=$(mktemp -d)/t13
REPO=$(git rev-parse --show-toplevel)
git -C "$REPO" worktree add --detach "$WT" HEAD
git -C "$WT" log -1 --format=%H

# [전제 충족 — post-freeze 2-커밋 모의 («전제 차이» 표)]
NEW=$(cd "$WT" && printf '%s\0' "$BP1" "$BP2" | LC_ALL=C sort -z -u \
      | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
(cd "$WT" && perl -pi -e "s/^bound_set_digest:.*/bound_set_digest: $NEW/" "$ART")
git -C "$WT" commit -am 'C1: SIMULATED rebinding (test fixture only)'
MOCK="$WT/docs/reviews/phase0-completion-contract/29991231-235959"
mkdir -p "$MOCK"
cat > "$MOCK/verdict.md" <<EOF
adjudicator: codex
verdict: approve
reviewed_at_head: $(git -C "$WT" rev-parse HEAD)
reviewed_plan_paths:
  - $BP1
  - $BP2
EOF
git -C "$WT" add -A && git -C "$WT" commit -m 'SIMULATED approve verdict (test fixture only)'

# T-81 (13)-a  하니스 통과 — R-0 head 를 X 로 포착
cd "$WT" && bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness213.sh | tee /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t13-harness-out.txt
echo "harness_rc=${PIPESTATUS[0]}"
X=$(grep '^R-0 head=' /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t13-harness-out.txt | cut -d= -f2)
echo "X(하니스 평가 HEAD)=$X"

# T-81 (13)-b  가드 우변 실행 전에 HEAD 이동 — 무관 커밋
git -C "$WT" commit --allow-empty -m 'SIMULATED unrelated commit: HEAD move (test fixture only)'
Y=$(git -C "$WT" rev-parse HEAD)
echo "Y(이동 후 HEAD)=$Y"

# T-81 (13)-c  D0A-FIRST 커밋 — 판정 대상과 다른 커밋 위에서
cd "$WT" && printf "# D0-A first artifact\n" > config/tos_completion.yaml \
  && git add config/tos_completion.yaml \
  && git commit -m "D0-A: introduce config/tos_completion.yaml"

# T-81 (13)-d  U-15-f-4 대조 (G-부모 단계 형태)
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml)
P=$(git -C "$WT" log --format=%P -1 "$D")
echo "d(도입 커밋)=$D"
echo "parent(d)=$P"
echo "X(하니스 평가 HEAD)=$X"
if [ "$P" = "$X" ]; then
  echo "U-15-f-4: parent(d) == X — 위반 미관측 = T-81 (13) 실패"
else
  echo "U-15-f-4: parent(d) != X — PARENT_MISMATCH 위반이 기계 관측됨 = T-81 (13) 통과"
fi

git -C "$REPO" worktree remove --force "$WT"
git -C "$REPO" worktree list
```

### 3.2 명령·출력 원문 전문 (bash -x)

```text
run13_utc=2026-08-15T06:39:14Z  base_head=8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-13.sh
+ set -u
+ BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
+ ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 HEAD
작업 트리 준비 중 (분리된 HEAD 8a25c3c0)
HEAD의 현재 위치는 8a25c3c0입니다 docs(tos): phase0 completion contract v2.13 — parent binding, ancestry order, edge ledger
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 log -1 --format=%H
8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
++ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13
++ printf '%s\0' docs/plans/2026-08-12-tos-phase0-completion-contract-design.md docs/plans/2026-08-11-tos-completion-development-plan.md
++ LC_ALL=C
++ sort -z -u
++ xargs -0 shasum -a 256
++ shasum -a 256
++ cut '-d ' -f1
+ NEW=796ca1e0a5b7ff8499e38b5322ff579b63dc643b6af6ec9cf3483dbeacaf6919
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13
+ perl -pi -e 's/^bound_set_digest:.*/bound_set_digest: 796ca1e0a5b7ff8499e38b5322ff579b63dc643b6af6ec9cf3483dbeacaf6919/' tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 commit -am 'C1: SIMULATED rebinding (test fixture only)'
[HEAD 분리됨 a72b833a] C1: SIMULATED rebinding (test fixture only)
 1 file changed, 1 insertion(+), 1 deletion(-)
+ MOCK=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13/docs/reviews/phase0-completion-contract/29991231-235959
+ mkdir -p /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13/docs/reviews/phase0-completion-contract/29991231-235959
+ cat
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 rev-parse HEAD
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 add -A
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 commit -m 'SIMULATED approve verdict (test fixture only)'
[HEAD 분리됨 e64db5f5] SIMULATED approve verdict (test fixture only)
 1 file changed, 6 insertions(+)
 create mode 100644 docs/reviews/phase0-completion-contract/29991231-235959/verdict.md
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness213.sh
+ tee /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t13-harness-out.txt
R-0 head=e64db5f599e4517eb4866a75ef4a3fc14246193c
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
+ echo harness_rc=0
harness_rc=0
++ grep '^R-0 head=' /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t13-harness-out.txt
++ cut -d= -f2
+ X=e64db5f599e4517eb4866a75ef4a3fc14246193c
+ echo 'X(하니스 평가 HEAD)=e64db5f599e4517eb4866a75ef4a3fc14246193c'
X(하니스 평가 HEAD)=e64db5f599e4517eb4866a75ef4a3fc14246193c
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 commit --allow-empty -m 'SIMULATED unrelated commit: HEAD move (test fixture only)'
[HEAD 분리됨 7eff934b] SIMULATED unrelated commit: HEAD move (test fixture only)
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 rev-parse HEAD
+ Y=7eff934b49628516b9b5014f3f7518e7d1d81252
+ echo 'Y(이동 후 HEAD)=7eff934b49628516b9b5014f3f7518e7d1d81252'
Y(이동 후 HEAD)=7eff934b49628516b9b5014f3f7518e7d1d81252
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13
+ printf '# D0-A first artifact\n'
+ git add config/tos_completion.yaml
+ git commit -m 'D0-A: introduce config/tos_completion.yaml'
[HEAD 분리됨 984eeb59] D0-A: introduce config/tos_completion.yaml
 1 file changed, 1 insertion(+)
 create mode 100644 config/tos_completion.yaml
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml
+ D=984eeb5997b4e278d6275a3bf69f5fc15e8348ff
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13 log --format=%P -1 984eeb5997b4e278d6275a3bf69f5fc15e8348ff
+ P=7eff934b49628516b9b5014f3f7518e7d1d81252
+ echo 'd(도입 커밋)=984eeb5997b4e278d6275a3bf69f5fc15e8348ff'
d(도입 커밋)=984eeb5997b4e278d6275a3bf69f5fc15e8348ff
+ echo 'parent(d)=7eff934b49628516b9b5014f3f7518e7d1d81252'
parent(d)=7eff934b49628516b9b5014f3f7518e7d1d81252
+ echo 'X(하니스 평가 HEAD)=e64db5f599e4517eb4866a75ef4a3fc14246193c'
X(하니스 평가 HEAD)=e64db5f599e4517eb4866a75ef4a3fc14246193c
+ '[' 7eff934b49628516b9b5014f3f7518e7d1d81252 = e64db5f599e4517eb4866a75ef4a3fc14246193c ']'
+ echo 'U-15-f-4: parent(d) != X — PARENT_MISMATCH 위반이 기계 관측됨 = T-81 (13) 통과'
U-15-f-4: parent(d) != X — PARENT_MISMATCH 위반이 기계 관측됨 = T-81 (13) 통과
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.qhH2ZoUNFR/t13
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               8a25c3c0 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-13.sh exit=0)
```

**판정(위 원문 그대로)**: 하니스가 `R-0 head=e64db5f5…`(= X)에서 `ENTRY_OK`/rc=0 을
산출했고, HEAD 이동(`7eff934b`) 후 커밋된 D0A-FIRST `984eeb59` 의
`parent(d)=7eff934b…` ≠ X — **U-15-f-4 위반이 `%P` 대조로 기계 관측됐다**
(= U-15-g 의 `PARENT_MISMATCH` 차단 사유). `&&` 의 시간 순서만으로는 잠기지 않는
"판정 대상 ≠ 착수 대상" 창이 실제로 열리고, 부모 결속이 그것을 잡는다.

---

## 4. Run ⑭ — 비가드 착수 (CORR(d) = ∅ → TRANSCRIPT_MISSING)

### 4.1 실행 스크립트 + 출력 원문

sha256(t81-14.sh) = `f23095ef9bb1facc141ec9da13b2bbd055de9e738e22c3f5fbb03eb572424793`

```bash
set -u
WT=$(mktemp -d)/t14
REPO=$(git rev-parse --show-toplevel)
git -C "$REPO" worktree add --detach "$WT" HEAD
git -C "$WT" log -1 --format=%H
# 하니스를 아예 돌리지 않고 D0A-FIRST 커밋 (비가드 착수 재현)
cd "$WT" && printf "# D0-A first artifact\n" > config/tos_completion.yaml \
  && git add config/tos_completion.yaml \
  && git commit -m "D0-A: introduce config/tos_completion.yaml"
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml)
P=$(git -C "$WT" log --format=%P -1 "$D")
echo "d(도입 커밋)=$D"
echo "parent(d)=$P"
git -C "$REPO" worktree remove --force "$WT"
git -C "$REPO" worktree list
```

```text
run14_utc=2026-08-15T06:39:33Z  base_head=8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-14.sh
+ set -u
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zsiaz9RQst/t14
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zsiaz9RQst/t14 HEAD
작업 트리 준비 중 (분리된 HEAD 8a25c3c0)
HEAD의 현재 위치는 8a25c3c0입니다 docs(tos): phase0 completion contract v2.13 — parent binding, ancestry order, edge ledger
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zsiaz9RQst/t14 log -1 --format=%H
8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zsiaz9RQst/t14
+ printf '# D0-A first artifact\n'
+ git add config/tos_completion.yaml
+ git commit -m 'D0-A: introduce config/tos_completion.yaml'
[HEAD 분리됨 7a68ed67] D0-A: introduce config/tos_completion.yaml
 1 file changed, 1 insertion(+)
 create mode 100644 config/tos_completion.yaml
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zsiaz9RQst/t14 log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml
+ D=7a68ed67f802f926074e93fedfb13523a34af8f4
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zsiaz9RQst/t14 log --format=%P -1 7a68ed67f802f926074e93fedfb13523a34af8f4
+ P=8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
+ echo 'd(도입 커밋)=7a68ed67f802f926074e93fedfb13523a34af8f4'
d(도입 커밋)=7a68ed67f802f926074e93fedfb13523a34af8f4
+ echo 'parent(d)=8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa'
parent(d)=8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zsiaz9RQst/t14
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               8a25c3c0 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-14.sh exit=0)
```

### 4.2 CORR(d) 손 실행 전문 (parent(d) = `8a25c3c0…`)

```text
corr14_utc=2026-08-15T06:39:34Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/corr-exec.sh 8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
== U-15-g-3 CORR(d) 손 실행 — parent(d)=8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa ==
-- 추적 transcript 우주 --
docs/reviews/phase0-completion-contract/20260814-110807/U15-ENTRY-CHECK.md
docs/reviews/phase0-completion-contract/20260814-160239/U15-ENTRY-CHECK.md
docs/reviews/phase0-completion-contract/20260815-040451/U15-ENTRY-CHECK.md
docs/reviews/phase0-completion-contract/20260815-092111/U15-ENTRY-CHECK.md

-- 각 transcript 의 (R-0 head, d0a_entry_state) 쌍 전수 추출 --
   (행-앵커 리터럴만: '^R-0 head=' 뒤 '^d0a_entry_state=' — U-15-e (4c) 산출 요건 라인)
[docs/reviews/phase0-completion-contract/20260814-110807/U15-ENTRY-CHECK.md]
[docs/reviews/phase0-completion-contract/20260814-160239/U15-ENTRY-CHECK.md]
  (4fb034705821ea6df82544864248341a881f2242, REBINDING_REQUIRED)
  (1065de355f947bfc5ccf4b41e4feabd8d1e30ce4, REBINDING_REQUIRED)
  (8ae0574b5c5ce7de8f4dee8c440af6ef963b5940, APPROVAL_STALE)
  (4fb034705821ea6df82544864248341a881f2242, FREEZE_VIOLATED)
[docs/reviews/phase0-completion-contract/20260815-040451/U15-ENTRY-CHECK.md]
  (e582c01aecaf73fa6da665325922d174942fc665, REBINDING_REQUIRED)
  (e582c01aecaf73fa6da665325922d174942fc665, REBINDING_REQUIRED)
  (50dcd5c22d245ea5ef92181cb9d5e98cc6d97e34, ENTRY_OK)
[docs/reviews/phase0-completion-contract/20260815-092111/U15-ENTRY-CHECK.md]
  (cf9b0295ac574b0cb022dd743e42c7aac5113aca, REBINDING_REQUIRED)
  (cf9b0295ac574b0cb022dd743e42c7aac5113aca, REBINDING_REQUIRED)
  (07a16838226ad45beec16992c470868c395ca76f, ENTRY_OK)

-- 조건 (2): R-0 head 리터럴 == parent(d) 보유 transcript --
(없음)

-- 조건 (2) AND (3): (head==parent(d), state==ENTRY_OK) 쌍 보유 transcript = CORR(d) --
|CORR(d)| = 0
```

**판정(위 원문 그대로)**: 조건 (2)(`R-0 head` 리터럴 == parent(d)) 매치 transcript
**0건** → **|CORR(d)| = 0 → `TRANSCRIPT_MISSING`(차단)**. **v2.13 초안 반증 ①**("기존
transcript 가 여럿이라 «존재한다»가 항상 참 — `TRANSCRIPT_MISSING` 도달 불가")이
교정된 술어에서는 성립하지 않음을 실행으로 확인 — **선언된 상태에 실제로 도달했다.**

---

## 5. Run ⑮ — 전진-머지 우회 재현 (봉합 후 red 확인)

### 5.1 실행 스크립트 + 출력 원문

검증자 구성 그대로: `cf9b0295`(기존 transcript `20260815-092111` 이 기록한 `R-0 head`
리터럴)를 부모로 D0A-FIRST 를 커밋하고 동결 HEAD `8a25c3c0` 를 전진 머지.
sha256(t81-15.sh) = `7aca2a799ead757b8157d55c01456ef8507051977637f99c67d419687505ab93`

```bash
set -u
WT=$(mktemp -d)/t15
REPO=$(git rev-parse --show-toplevel)
# 검증자 구성 그대로: 기존 transcript(20260815-092111)가 기록한 R-0 head = cf9b0295 를 부모로
git -C "$REPO" worktree add --detach "$WT" cf9b0295ac574b0cb022dd743e42c7aac5113aca
git -C "$WT" log -1 --format=%H
cd "$WT" && printf "# D0-A first artifact\n" > config/tos_completion.yaml \
  && git add config/tos_completion.yaml \
  && git commit -m "D0-A: introduce config/tos_completion.yaml"
# 전진 머지 — d 를 현행 동결 HEAD 계열로 끌어올린다
git -C "$WT" merge --no-edit 8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
git -C "$WT" log --oneline -3
# 판정 우주 (U-15-g-1): 머지 후 HEAD 에서 도입 커밋 파생
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml)
P=$(git -C "$WT" log --format=%P -1 "$D")
echo "d(도입 커밋)=$D"
echo "parent(d)=$P"
git -C "$REPO" worktree remove --force "$WT"
git -C "$REPO" worktree list
```

```text
run15_utc=2026-08-15T06:40:00Z  base_head=8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-15.sh
+ set -u
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15 cf9b0295ac574b0cb022dd743e42c7aac5113aca
작업 트리 준비 중 (분리된 HEAD cf9b0295)
HEAD의 현재 위치는 cf9b0295입니다 docs(tos): phase0 completion contract v2.12 — D0A-FIRST, universal unification, T-83
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15 log -1 --format=%H
cf9b0295ac574b0cb022dd743e42c7aac5113aca
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15
+ printf '# D0-A first artifact\n'
+ git add config/tos_completion.yaml
+ git commit -m 'D0-A: introduce config/tos_completion.yaml'
[HEAD 분리됨 53edd51d] D0-A: introduce config/tos_completion.yaml
 1 file changed, 1 insertion(+)
 create mode 100644 config/tos_completion.yaml
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15 merge --no-edit 8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa
Merge made by the 'ort' strategy.
 ...-08-12-tos-phase0-completion-contract-design.md | 284 ++++++++++++---
 docs/plans/INDEX.md                                |  18 +-
 .../20260815-092111/U15-ENTRY-CHECK.md             | 399 +++++++++++++++++++++
 .../20260815-102037/verdict.md                     |  63 ++++
 .../20260815-144959/verdict.md                     | 102 ++++++
 docs/reviews/phase0-completion-contract/README.md  |  24 +-
 .../decisions/OQ-11-DISPOSITION.md                 |  28 +-
 7 files changed, 855 insertions(+), 63 deletions(-)
 create mode 100644 docs/reviews/phase0-completion-contract/20260815-092111/U15-ENTRY-CHECK.md
 create mode 100644 docs/reviews/phase0-completion-contract/20260815-102037/verdict.md
 create mode 100644 docs/reviews/phase0-completion-contract/20260815-144959/verdict.md
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15 log --oneline -3
2ac84bb5 Merge commit '8a25c3c089e9a3b475e0d957e8e6a7e3cddbe2fa' into HEAD
53edd51d D0-A: introduce config/tos_completion.yaml
8a25c3c0 docs(tos): phase0 completion contract v2.13 — parent binding, ancestry order, edge ledger
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15 log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml
+ D=53edd51d1ac2652dea73f4a241d9eaffceae39fe
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15 log --format=%P -1 53edd51d1ac2652dea73f4a241d9eaffceae39fe
+ P=cf9b0295ac574b0cb022dd743e42c7aac5113aca
+ echo 'd(도입 커밋)=53edd51d1ac2652dea73f4a241d9eaffceae39fe'
d(도입 커밋)=53edd51d1ac2652dea73f4a241d9eaffceae39fe
+ echo 'parent(d)=cf9b0295ac574b0cb022dd743e42c7aac5113aca'
parent(d)=cf9b0295ac574b0cb022dd743e42c7aac5113aca
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9JeFrgTXFn/t15
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               8a25c3c0 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-15.sh exit=0)
```

### 5.2 CORR(d) 손 실행 전문 (parent(d) = `cf9b0295…`) + 초안 술어 대조

```text
corr15_utc=2026-08-15T06:40:02Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/corr-exec.sh cf9b0295ac574b0cb022dd743e42c7aac5113aca
== U-15-g-3 CORR(d) 손 실행 — parent(d)=cf9b0295ac574b0cb022dd743e42c7aac5113aca ==
-- 추적 transcript 우주 --
docs/reviews/phase0-completion-contract/20260814-110807/U15-ENTRY-CHECK.md
docs/reviews/phase0-completion-contract/20260814-160239/U15-ENTRY-CHECK.md
docs/reviews/phase0-completion-contract/20260815-040451/U15-ENTRY-CHECK.md
docs/reviews/phase0-completion-contract/20260815-092111/U15-ENTRY-CHECK.md

-- 각 transcript 의 (R-0 head, d0a_entry_state) 쌍 전수 추출 --
   (행-앵커 리터럴만: '^R-0 head=' 뒤 '^d0a_entry_state=' — U-15-e (4c) 산출 요건 라인)
[docs/reviews/phase0-completion-contract/20260814-110807/U15-ENTRY-CHECK.md]
[docs/reviews/phase0-completion-contract/20260814-160239/U15-ENTRY-CHECK.md]
  (4fb034705821ea6df82544864248341a881f2242, REBINDING_REQUIRED)
  (1065de355f947bfc5ccf4b41e4feabd8d1e30ce4, REBINDING_REQUIRED)
  (8ae0574b5c5ce7de8f4dee8c440af6ef963b5940, APPROVAL_STALE)
  (4fb034705821ea6df82544864248341a881f2242, FREEZE_VIOLATED)
[docs/reviews/phase0-completion-contract/20260815-040451/U15-ENTRY-CHECK.md]
  (e582c01aecaf73fa6da665325922d174942fc665, REBINDING_REQUIRED)
  (e582c01aecaf73fa6da665325922d174942fc665, REBINDING_REQUIRED)
  (50dcd5c22d245ea5ef92181cb9d5e98cc6d97e34, ENTRY_OK)
[docs/reviews/phase0-completion-contract/20260815-092111/U15-ENTRY-CHECK.md]
  (cf9b0295ac574b0cb022dd743e42c7aac5113aca, REBINDING_REQUIRED)
  (cf9b0295ac574b0cb022dd743e42c7aac5113aca, REBINDING_REQUIRED)
  (07a16838226ad45beec16992c470868c395ca76f, ENTRY_OK)

-- 조건 (2): R-0 head 리터럴 == parent(d) 보유 transcript --
docs/reviews/phase0-completion-contract/20260815-092111/U15-ENTRY-CHECK.md

-- 조건 (2) AND (3): (head==parent(d), state==ENTRY_OK) 쌍 보유 transcript = CORR(d) --
|CORR(d)| = 0

-- [대조] v2.13 초안 술어 (조건 (1)(2)만 — 판정값 미소비) 하의 결과 --
$ grep -l "^R-0 head=cf9b0295ac574b0cb022dd743e42c7aac5113aca" docs/reviews/phase0-completion-contract/*/U15-ENTRY-CHECK.md
docs/reviews/phase0-completion-contract/20260815-092111/U15-ENTRY-CHECK.md
= 초안 술어라면 위 transcript 가 «대응 transcript 존재 + head 리터럴 일치»를 충족해
  ENTRY_PROVENANCE_CLEAR 로 통과했을 구성이다 — 하니스 미실행·그 transcript 의
  기록 상태는 차단(REBINDING_REQUIRED)이었는데도. 교정 술어(조건 3)가 이를 차단한다.
```

**판정(위 원문 그대로)**: 조건 (2)는 `20260815-092111` transcript 가 충족(리터럴
일치)하나, 그 transcript 의 `cf9b0295` head 쌍은 전부 `REBINDING_REQUIRED` — 조건 (3)
`ENTRY_OK` 쌍이 없어 **CORR 에 들어오지 못한다 → |CORR(d)| = 0 → 차단**(U-15-g-4 의
`TRANSCRIPT_MISSING` — "차단 상태 transcript 로 착수" 절). **초안 술어(판정값
미소비)라면 `ENTRY_PROVENANCE_CLEAR` 로 통과했을 구성이 봉합 후 red 다** — "차단
기록이 통행증이 되던" 반증 ②의 봉합이 실행으로 확인됐다. 하니스는 이 run 에서 한
번도 실행되지 않았다.

---

## 6. CORR(d) 손 실행의 선언된 독해 (실행기 원문 포함)

U-15-g-3 은 «t 가 기록한 `R-0 head=` 값·`d0a_entry_state`» 를 t 단위로 말하지만,
추적 transcript 는 **다중-run**(한 파일에 하니스 실행 여러 건)이다. 손 실행은 이를
**(head, state) 쌍 단위**로 독해했다: 출력 원문 블록의 **행-앵커 리터럴**(`^R-0 head=`
… `^d0a_entry_state=`, U-15-e (4c) 산출 요건 라인)만을 실행 순서대로 짝지어, 조건
(2)+(3)은 "**같은 하니스 실행**에서 head==parent(d) 이고 state==ENTRY_OK" 로
평가한다. 산문·표 안의 재서술(backtick 인용)은 앵커에 걸리지 않으므로 소비되지
않는다 — (4c)가 "요약·재서술하면 착수를 정당화하지 못한다"고 정한 그대로다.

- 관측 노트 1: `20260814-110807`(v2.8판 transcript)은 쌍 **0건** — v2.8 레시피는
  `R-0 head=` 접두도 프로그램 산출 상태 행도 없던 판이라 **(4c) 형식 미충족 = 애초에
  CORR 후보가 아니다**(계약의 "기존 transcript 는 소급 무효화되지 않는다" 노트와 정합
  — 그것들은 진입 정당화용으로 작성된 적이 없다).
- 관측 노트 2: `ENTRY_OK` 쌍은 2건 존재하나(`50dcd5c2…`·`07a16838…`) 둘 다 worktree
  모의 커밋(unreachable) head 라 **실 저장소의 어떤 parent(d) 와도 일치할 수 없다**.

sha256(corr-exec.sh) = `e9932522cd50de0e2a8ba9d68330ccb8c518f63372dbba552e706a2075116f9b`

```bash
set -u
PD=$1
echo "== U-15-g-3 CORR(d) 손 실행 — parent(d)=$PD =="
echo "-- 추적 transcript 우주 --"
ls docs/reviews/phase0-completion-contract/*/U15-ENTRY-CHECK.md
echo ""
echo "-- 각 transcript 의 (R-0 head, d0a_entry_state) 쌍 전수 추출 --"
echo "   (행-앵커 리터럴만: '^R-0 head=' 뒤 '^d0a_entry_state=' — U-15-e (4c) 산출 요건 라인)"
for t in docs/reviews/phase0-completion-contract/*/U15-ENTRY-CHECK.md; do
  echo "[$t]"
  awk '/^R-0 head=/{h=substr($0,10)} /^d0a_entry_state=/{print "  ("h", "substr($0,17)")"}' "$t"
done
echo ""
echo "-- 조건 (2): R-0 head 리터럴 == parent(d) 보유 transcript --"
grep -l "^R-0 head=$PD" docs/reviews/phase0-completion-contract/*/U15-ENTRY-CHECK.md || echo "(없음)"
echo ""
echo "-- 조건 (2) AND (3): (head==parent(d), state==ENTRY_OK) 쌍 보유 transcript = CORR(d) --"
CORR=0
for t in docs/reviews/phase0-completion-contract/*/U15-ENTRY-CHECK.md; do
  if awk -v pd="$PD" '
      /^R-0 head=/{h=substr($0,10)}
      /^d0a_entry_state=/{if(h==pd && substr($0,17)=="ENTRY_OK") found=1}
      END{exit !found}' "$t"; then
    echo "  IN CORR: $t"; CORR=$((CORR+1))
  fi
done
echo "|CORR(d)| = $CORR"
```

---

## 7. 정리 · 본 저장소 무영향 · 모의물 누출 방지 · D0-A 미착수 불변

```text
=== 사후 검증 (2026-08-15T06:40:31Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               8a25c3c0 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
8a25c3c0 docs(tos): phase0 completion contract v2.13 — parent binding, ancestry order, edge ledger
-- 실행 전 스냅샷 대조 --
status: 실행 전과 byte-동일
-- worktree 커밋 도달성 (refs 전수) — 3-run 전 커밋 --
$ git log --all --format=%H | grep -c -e a72b833a -e e64db5f5 -e 7eff934b -e 984eeb59 -e 7a68ed67 -e 53edd51d -e 2ac84bb5
0
= 7건(⑬:4·⑭:1·⑮:2) 전부 어떤 ref 에서도 도달 불가
-- 본 저장소: D0-A 미착수 불변 --
ls: config/tos_completion.yaml: No such file or directory
(출력 없음 = 도입 커밋 부재)
-- 모의 스탬프·ART·기존 transcript 무변경 --
(출력 없음 = 부재)
(출력 없음 = ART·기존 transcript 4건 전부 무변경 — CORR 는 읽기만 했다)

-- mktemp 잔여 정리 (본 임무 소유분 3건: tmp.qhH2ZoUNFR=⑬ · tmp.zsiaz9RQst=⑭ · tmp.9JeFrgTXFn=⑮) --
tmp.qhH2ZoUNFR 제거
tmp.qhH2ZoUNFR 잔존 없음 확인
tmp.zsiaz9RQst 제거
tmp.zsiaz9RQst 잔존 없음 확인
tmp.9JeFrgTXFn 제거
tmp.9JeFrgTXFn 잔존 없음 확인
```

## 8. U-15-e (5) 가드 실행 기록

**본 저장소에서 U-15-f 가드 형태의 착수는 실행되지 않았다** — 이 transcript 는 T-81
변이 실행 기록이며, 위 세 run 의 하니스·D0A-FIRST 는 전부 분리-HEAD worktree 안이다.
본 저장소의 D0A-FIRST 산물 부재(파일·도입 커밋 양쪽)는 §7 에 실측으로 기록돼 있다.
(U-15-f-2: 실제 착수가 일어난다면 가드 형태 + 그 U-15-e (5) 기록이 별도 transcript 로
남아야 하며, 이 파일은 그 기록이 아니다.)

## 9. 직전 transcript(`20260815-092111`, v2.12 실제-행위 억제)와의 차이 · 소비 조건

```text
직전 (v2.12)   가드 우변을 실제 D0A-FIRST 로 교체하고 억제/도달을 파일+도입 커밋으로
               실측했다 — "무엇을 억제하는가"가 실제가 됐다. 그러나 하니스 통과와
               착수 사이의 HEAD 이동, 그리고 가드 자체를 생략한 착수는 관측 밖이었다.

이 transcript   ⑬ 부모 결속(U-15-f-4)이 "판정 대상 == 착수 대상"을 %P 대조로 잠그고,
               ⑭⑮ 사후 관측(U-15-g)이 transcript 의 **판정값까지 소비**해 비가드
               착수·전진-머지 우회를 차단함을 실측했다 — 대리→실제에 이어
               **부모 결속 + 판정값 소비**로 진화했고, ⑮는 "차단 기록이 통행증이
               되던" v2.13 초안 반증 구성이 봉합 후 red 임을 확인한 run 이다.
               발견이지 예방이 아니라는 경계(UNCHK-008 소관)는 계약 그대로다.
```

**소비 조건(U-15-e (6)) 자기 기록**: 이 transcript 의 HEAD 는 `8a25c3c0` 다. 진입
시점에 그 이후 `bound_paths` 를 건드린 커밋이 있으면 이 transcript 는 stale 이며 진입
거부다. 본 저장소 현행 산출이 `REBINDING_REQUIRED` 이므로, 6e 재결속과 레인 B
`approve` 취득 후 그 시점 HEAD 에서 하니스·가드를 재실행한 새 transcript 가 필요하다
— 이 파일은 그 시점의 `ENTRY_OK` 를 주장하지 않으며, 이 파일이 기록한 `ENTRY_OK`
쌍(`e64db5f5…`)은 worktree 모의 head 라 어떤 실 저장소 착수도 정당화하지 못한다.
