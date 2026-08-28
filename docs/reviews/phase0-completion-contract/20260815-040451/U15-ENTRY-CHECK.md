# U15-ENTRY-CHECK — v2.11 가드 억제 실행 transcript (pre-D0-A · U-15-f 양방향)

- **목적**: 레인 B v2.10 재심 verdict(`20260815-040451`, NOT_PASSED)의 Recommendation —
  "하니스 비정상 종료 또는 transcript 부재 시 **D0-A 작업이 실행되지 않는** 결과" — 의
  이행. v2.11(동결 커밋 `e582c01a`)이 신설한 **U-15-f 가드된 착수 형식**
  (`bash <하니스> && <D0-A 최초 행위>`)의 억제를 §12.3.4-G 절차로 **양방향 실행**해
  U-15-e (1)~(5)·(4b) 결속으로 남긴다. 대조군 T-81 ⑪(차단 억제)·⑫(모의 도달)의
  pre-D0-A 실행이기도 하다.
- **생성 시각**: 2026-08-14T19:46:42Z (UTC)
- **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트
- **관련 계약**: U-15-f (f-1 가드 형식·f-2 유일 규정 착수 형식·f-3 억제 양방향 증명) ·
  U-15-e (5) 가드 실행 기록 · §12.3.4-R(하니스) · §12.3.4-G(억제 실행 절차) ·
  T-81 ⑪·⑫ (동결 커밋 `e582c01a`)
- **레그 요약 — 하니스 stdout·guard_rc·우변 부작용을 그대로 옮긴다 (해석 아님)**:

| 레그 | 실행 지점 | 하니스 산출 (원문) | guard_rc | 우변 부작용 (`D0A-STARTED`) |
| --- | --- | --- | --- | --- |
| G-음성 (차단 억제) | worktree `e582c01a` (현행 차단 상태) | `d0a_entry_state=REBINDING_REQUIRED` / `reason=bound_set_digest 불일치` | `guard_rc=1` | **부재** — `ls: … No such file or directory` (우변 미도달) |
| G-양성 (모의 도달) | 같은 worktree, SIMULATED 2-커밋(`77bf81f5`·`50dcd5c2`) 후 | `d0a_entry_state=ENTRY_OK` / `reason=R-0~R-7 전부 기대와 일치` | `guard_rc=0` | **존재** — `-rw-r--r-- … 0 … D0A-STARTED` (우변 도달) |

**억제가 양방향으로 실증됐다**: 차단 상태에서 우변이 도달 불가였고(음성), ENTRY_OK 모의에서
우변이 도달했다(양성 — 이것이 없으면 음성은 "우변이 원래 안 되는 것"과 구별되지 않는다,
U-15-f-3). **G-양성의 `ENTRY_OK` 는 worktree 안 SIMULATED 전제 하의 관측**이며, 이
transcript 는 본 저장소의 `ENTRY_OK` 를 주장하지 않는다 — 본 저장소 현행 산출은
`REBINDING_REQUIRED`(6e 재결속 대기)다.

---

## 1. 하니스 명령 원문 (§12.3.4-R v2.11 · 생략 없음) + U-15-e (4b) 무결성 결속

- 추출: `git show e582c01a:<계약 문서>` 의 §12.3.4-R 첫 bash 블록 verbatim(101행).
  워킹트리 재추출과 **diff 무차이**(동결본 == 현행본 == 실행본) · `bash -n` 통과.
- **v2.10 하니스와 byte-동일** — v2.11 은 계약 산문(U-15-f·§12.3.4-G 등)만 추가했고
  하니스 원문은 불변임을 sha 동일성으로 확인.
- **sha256(harness211.sh) = `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`**

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

## 2. G-양성 전제 실측 — «전제 차이» 규칙의 첫 적용

§12.3.4-G 마감 편집이 성문화한 규칙 — *모의 절차를 기술할 때는 "어느 R-단계가 이미
통과하는가"를 먼저 적는다* — 을 실행 전에 적용했다. 문서의 G-양성 블록은 최소 전제
("현행 결속이 유효한 상태")에서 **approve 모의 1-커밋**을 규정하지만, 그 전제가 현
동결 HEAD 에서 성립하는지는 실측 대상이다.

```text
=== G-양성 전제 실측 (§12.3.4-G «전제 차이» 규칙의 첫 적용: 어느 R-단계가 이미 통과하는가) ===
실측 시각: 2026-08-14T19:44:15Z · HEAD: e582c01aecaf73fa6da665325922d174942fc665

[실측 1] 동결 HEAD 에서 하니스 실행 — 첫 미충족 R-단계의 프로그램 산출:
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness211.sh; echo "harness_rc=$?"
R-0 head=e582c01aecaf73fa6da665325922d174942fc665
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1

[실측 2] R-2 보유값 vs 재계산값:
$ git show HEAD:tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md | grep ^bound_set_digest
bound_set_digest: b0edb769f7229b7377d4454856f06134843900deba7d733d643fa7ab6b0c3e22
$ printf ... | shasum 재계산 (하니스 R-2 와 동일 파이프라인)
06cd99c1fac2b63d97bb26b33a66f25e7a2badbb8f326d906a97de17c420d4f2

[실측 3] R-4 상태 — HEAD 트리의 최신 스탬프와 verdict 어휘:
$ git ls-tree --name-only HEAD docs/reviews/phase0-completion-contract/ | grep -E "/[0-9]{8}-[0-9]{6}$" | LC_ALL=C sort | tail -1
docs/reviews/phase0-completion-contract/20260815-040451
$ git show HEAD:docs/reviews/phase0-completion-contract/20260815-040451/verdict.md | grep -E "^(adjudicator|verdict):"
adjudicator: codex
verdict: needs-attention

[귀결] R-0·R-1 통과(하니스가 R-2 에서 발화) · R-2 미충족(보유 != 재계산 — 6e 재결속 대기) ·
       R-4 미충족(needs-attention) · R-7 은 무변이 시나리오라 공집합 예정.
       => 문서의 최소 전제("현행 결속 유효 + approve 모의 1-커밋")가 성립하지 않는다.
       => 필요한 모의 커밋 = 2 (C1 SIMULATED 재결속 + C2 SIMULATED approve verdict).
```

**귀결(위 실측 그대로)**: R-2 미충족(보유 `b0edb769…` ≠ 재계산 `06cd99c1…`)·R-4
미충족(`needs-attention`)이므로 문서의 1-커밋 최소 전제가 성립하지 않는다 → **SIMULATED
모의 2-커밋**(C1 재결속 + C2 approve verdict)으로 전제를 충족시킨다. C1 의 형태는
§12.3.4-T T-81-①-e C2(성문화된 재결속 모의)를 차용한다.

---

## 3. 실행본 결속 (§12.3.4-G 블록 + 선언된 변경 3건)

- §12.3.4-G bash 블록(33행) verbatim 추출 — 동결본과 diff 무차이.
- sha256(원문 g-block.sh) = `521da692d19f8869034385e8c5a89d52b5776eb47182cdb09c41d3ffea8fad53`
- sha256(실행본 g-run.sh) = `f4434c29cb0234a6732746acf678bf3cdb6fab42f9ffa9736621a2a9fe6b1ffc`
- **선언된 변경 3건과 diff 전문** (그 외 diff 0):

```text
g_block_sha256(원문)=521da692d19f8869034385e8c5a89d52b5776eb47182cdb09c41d3ffea8fad53
g_run_sha256(실행본)=f4434c29cb0234a6732746acf678bf3cdb6fab42f9ffa9736621a2a9fe6b1ffc
선언된 변경 3건: ① 경로 치환 'bash /path/to/harness.sh' -> 'bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness211.sh' (2곳: G-음성·G-양성) ② '# G-양성' 직전에 C1 SIMULATED 재결속 블록 11행 삽입 (전제 실측 귀결) ③ 말미 'git -C $REPO worktree list' 1행 추가 (잔여 확인)
-- 블록 원문 대비 diff 전문 --
7c7
< cd "$WT" && bash /path/to/harness.sh && touch D0A-STARTED
---
> cd "$WT" && bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness211.sh && touch D0A-STARTED
11a12,22
> # [삽입 — 전제 실측 귀결 · «전제 차이» 규칙 적용] C1: SIMULATED 재결속 모의
> #   현행 HEAD 는 R-2 미충족(6e 재결속 대기)이라 문서 최소 전제("현행 결속 유효 +
> #   approve 1-커밋")가 성립하지 않는다. 재결속 모의 형태는 §12.3.4-T T-81-①-e C2 차용.
> BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
> BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
> ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
> NEW=$(cd "$WT" && printf '%s\0' "$BP1" "$BP2" | LC_ALL=C sort -z -u \
>       | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
> (cd "$WT" && perl -pi -e "s/^bound_set_digest:.*/bound_set_digest: $NEW/" "$ART")
> git -C "$WT" commit -am 'C1: SIMULATED rebinding (test fixture only)'
> 
27c38
< cd "$WT" && bash /path/to/harness.sh && touch D0A-STARTED
---
> cd "$WT" && bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness211.sh && touch D0A-STARTED
33a45
> git -C "$REPO" worktree list
```

---

## 4. 실행 기록 (명령·출력 원문 전문 — bash -x 트레이스)

```text
gRun_utc=2026-08-14T19:45:00Z  gRun_base_head=e582c01aecaf73fa6da665325922d174942fc665
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/g-run.sh
+ set -u
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g HEAD
작업 트리 준비 중 (분리된 HEAD e582c01a)
HEAD의 현재 위치는 e582c01a입니다 docs(tos): phase0 completion contract v2.11 — guarded entry, universal edge judgment, EV-L6 registration
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness211.sh
R-0 head=e582c01aecaf73fa6da665325922d174942fc665
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
+ echo guard_rc=1
guard_rc=1
+ ls -la /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g/D0A-STARTED
ls: /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g/D0A-STARTED: No such file or directory
+ BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
+ ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
++ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g
++ printf '%s\0' docs/plans/2026-08-12-tos-phase0-completion-contract-design.md docs/plans/2026-08-11-tos-completion-development-plan.md
++ LC_ALL=C
++ sort -z -u
++ xargs -0 shasum -a 256
++ shasum -a 256
++ cut '-d ' -f1
+ NEW=06cd99c1fac2b63d97bb26b33a66f25e7a2badbb8f326d906a97de17c420d4f2
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g
+ perl -pi -e 's/^bound_set_digest:.*/bound_set_digest: 06cd99c1fac2b63d97bb26b33a66f25e7a2badbb8f326d906a97de17c420d4f2/' tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g commit -am 'C1: SIMULATED rebinding (test fixture only)'
[HEAD 분리됨 77bf81f5] C1: SIMULATED rebinding (test fixture only)
 1 file changed, 1 insertion(+), 1 deletion(-)
+ MOCK=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g/docs/reviews/phase0-completion-contract/29991231-235959
+ mkdir -p /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g/docs/reviews/phase0-completion-contract/29991231-235959
+ cat
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g rev-parse HEAD
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g add -A
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g commit -m 'SIMULATED approve verdict (test fixture only)'
[HEAD 분리됨 50dcd5c2] SIMULATED approve verdict (test fixture only)
 1 file changed, 6 insertions(+)
 create mode 100644 docs/reviews/phase0-completion-contract/29991231-235959/verdict.md
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness211.sh
R-0 head=50dcd5c22d245ea5ef92181cb9d5e98cc6d97e34
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
+ touch D0A-STARTED
+ echo guard_rc=0
guard_rc=0
+ ls -la /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g/D0A-STARTED
-rw-r--r--@ 1 harris  staff  0  8월 15 04:45 /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g/D0A-STARTED
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9SjKVYAfY8/g
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               e582c01a [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(g-run.sh exit=0)
```

---

## 5. U-15-e (5) 가드 실행 기록 — 판정 (전부 위 원문에서 그대로)

**가드 명령 원문** (두 레그 동일 형태 — U-15-f-1):

```bash
cd "$WT" && bash <§12.3.4-R 하니스> && touch D0A-STARTED
echo "guard_rc=$?"
```

- **G-음성 (T-81 ⑪)**: 하니스 `d0a_entry_state=REBINDING_REQUIRED` → 좌변 rc=1 →
  `guard_rc=1` → **`touch` 미실행** (bash -x 트레이스에 `+ touch` 부재) →
  `ls: …/D0A-STARTED: No such file or directory` — **우변 부작용 부재 실측**.
  차단 상태에서 착수가 개시되지 않았다.
- **G-양성 (T-81 ⑫)**: SIMULATED 2-커밋(C1 `77bf81f5` 재결속 · C2 `50dcd5c2` approve
  verdict, 모의 스탬프 `29991231-235959`·`reviewed_at_head`=C1) 후 하니스
  `d0a_entry_state=ENTRY_OK` → 트레이스에 `+ touch D0A-STARTED` **실행 관측** →
  `guard_rc=0` → `ls` 가 파일 존재를 실측 — **우변 도달**. 가드가 "항상 막는 것"이
  아님이 증명되어 음성 레그의 증거가 유의미해진다(T-70 공집합 위양성 교훈의 이행).

---

## 6. 정리 · 본 저장소 무영향 · 모의물 누출 방지

```text
=== 사후 검증 (2026-08-14T19:45:27Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               e582c01a [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
e582c01a docs(tos): phase0 completion contract v2.11 — guarded entry, universal edge judgment, EV-L6 registration
-- 실행 전 스냅샷 대조 --
status: 실행 전과 byte-동일
-- SIMULATED 커밋 도달성 (refs 전수) --
$ git log --all --format=%H | grep -c -e 77bf81f5 -e 50dcd5c2
0
= 2건 전부 어떤 ref 에서도 도달 불가
-- 본 저장소 모의 스탬프·ART 무변경 --
$ ls docs/reviews/phase0-completion-contract/ | grep 2999
(출력 없음 = 부재)
$ git status --porcelain -- tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
(출력 없음 = 무변경)
-- 본 저장소에 D0A-STARTED 부재 --
ls: /Users/harris/Development/private/kis_unified_sts/D0A-STARTED: No such file or directory
-- mktemp 잔여 정리 (본 임무 소유분만) --
tmp.9SjKVYAfY8 제거
잔존 없음 확인
```

- worktree 제거 완료·잔여 없음(목록의 2건은 실행 전부터 존재하는 별개 worktree).
  본 저장소 status(` M uv.lock`/`?? tools/spikes/` — 이전부터 존재)·HEAD(`e582c01a`)
  실행 전 스냅샷과 byte-동일. SIMULATED 커밋 2건 refs 전수 대조 도달 불가.
  본 저장소에 `29991231-*` 스탬프·ART 변경·`D0A-STARTED` 전부 부재.

---

## 7. 직전 transcript(`20260814-160239/U15-ENTRY-CHECK.md`, v2.10 4-run)와의 차이

```text
직전 (v2.10)   하니스를 실행하고 d0a_entry_state 와 harness_rc 를 기록했다 —
               "하니스가 거부한다"까지의 증거다. 심판(v2.10 재심 #1)은 그 rc 를
               무시하거나 하니스를 생략하고 착수하는 경로가 막히지 않음을 지적했다
               (T-81 도 하니스만 돌릴 뿐 착수 억제를 실행하지 않았다).

이 transcript   가드 형태(bash <하니스> && <최초 행위>)를 실제로 실행해
               **착수 대리 행위(touch D0A-STARTED)의 억제/도달을 파일 존재로
               실측**했다 — "하니스가 거부한다"에서 "착수가 막힌다/열린다"로
               관측량이 이동했고(U-15-e (5) 신설 항목의 첫 수록), 그것이 심판
               Recommendation("D0-A 작업이 실행되지 않는 결과")의 직접 이행이다.
               부수: «전제 차이» 규칙의 첫 적용(전제 실측 → 문서 최소 전제 불성립
               확인 → 2-커밋 모의로 정정 구성)을 §2 에 기록했다.
```

**소비 조건(U-15-e 소비 조건) 자기 기록**: 이 transcript 의 HEAD 는 `e582c01a` 다.
진입 시점에 그 이후 `bound_paths` 를 건드린 커밋이 있으면 이 transcript 는 stale 이며
진입 거부다. 본 저장소 현행 산출이 `REBINDING_REQUIRED` 이므로, 6e 재결속과 레인 B
`approve` 취득 후 **그 시점 HEAD 에서 하니스·가드를 재실행한 새 transcript** 가
필요하다 — 이 파일은 그 시점의 `ENTRY_OK` 를 주장하지 않는다. **D0-A 실제 착수는
U-15-f-2 에 따라 가드 형태로만 개시되며, 그 실행의 U-15-e (5) 기록이 이 파일의
후속 transcript 에 남아야 한다.**
