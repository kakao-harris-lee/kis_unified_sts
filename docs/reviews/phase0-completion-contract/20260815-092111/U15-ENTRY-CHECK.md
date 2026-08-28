# U15-ENTRY-CHECK — v2.12 실제-행위 억제 transcript (pre-D0-A · U-15-f × D0A-FIRST)

- **목적**: 레인 B v2.11 재심 verdict(`20260815-092111`, NOT_PASSED)의 Recommendation —
  "**실제 D0-A 최초 실행 표면**에서의 억제 증거" — 의 이행. v2.12(동결 커밋
  `cf9b0295`)가 **`D0A-FIRST`** 를 명명(= `config/tos_completion.yaml` **도입 커밋**)하고
  U-15-f 가드 우변을 대리(`touch`)에서 그 실제 행위로 교체했다. §12.3.4-G 절차를
  양방향 실행해 U-15-e (1)~(5)·(4b) 결속으로 남긴다. 대조군 T-81 ⑪·⑫의 v2.12 기대
  (파일 **및** `--diff-filter=A` 도입 커밋 양쪽 관측)의 pre-D0-A 실행이다.
- **생성 시각**: 2026-08-15T01:11:19Z (UTC)
- **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트
- **관련 계약**: D0A-FIRST(§12.1 명명·4축 근거) · U-15-f(f-1 실제-행위 우변·f-3 양방향,
  관측 대상 = 파일 + 도입 커밋) · U-15-e (5) · §12.3.4-R(하니스) · §12.3.4-G(억제 실행
  절차·«전제 차이» 동결-상대화) · T-81 ⑪·⑫ (동결 커밋 `cf9b0295`)
- **레그 요약 — 하니스 stdout·guard_rc·D0A-FIRST 산물 실측을 그대로 옮긴다 (해석 아님)**:

| 레그 | 실행 지점 | 하니스 산출 (원문) | guard_rc | `config/tos_completion.yaml` (파일 / 도입 커밋) |
| --- | --- | --- | --- | --- |
| G-음성 (실제-행위 억제) | worktree `cf9b0295` (현행 차단 상태) | `d0a_entry_state=REBINDING_REQUIRED` / `reason=bound_set_digest 불일치` | `guard_rc=1` | **둘 다 부재** — `ls: … No such file or directory` + `--diff-filter=A` 출력 없음 (우변 미도달) |
| G-양성 (도달) | 같은 worktree, SIMULATED 2-커밋(`8b74f7f4`·`07a16838`) 후 | `d0a_entry_state=ENTRY_OK` / `reason=R-0~R-7 전부 기대와 일치` | `guard_rc=0` | **둘 다 존재** — 도입 커밋 **`1727c441 D0-A: introduce config/tos_completion.yaml`** 1건 (`create mode 100644`) |

**실제 D0-A 최초 실행 표면에서 억제가 양방향으로 실증됐다**: 차단 상태에서 실제 착수
(파일 생성 + 도입 커밋)가 개시되지 않았고(음성), ENTRY_OK 모의에서 같은 우변이 도달해
도입 커밋을 실제로 만들었다(양성 — U-15-f-3). **G-양성의 `ENTRY_OK` 와 도입 커밋은
worktree 안 SIMULATED 전제 하의 관측**이며, 이 transcript 는 본 저장소의 `ENTRY_OK` 도
D0-A 착수도 주장하지 않는다 — 본 저장소는 `REBINDING_REQUIRED`(6e 재결속 대기)이고
`config/tos_completion.yaml` 은 부재 그대로다(§6 실측).

---

## 1. 하니스 명령 원문 (§12.3.4-R v2.12 · 생략 없음) + U-15-e (4b) 무결성 결속

- 추출: `git show cf9b0295:<계약 문서>` 의 §12.3.4-R 첫 bash 블록 verbatim(101행).
  워킹트리 재추출과 **diff 무차이**(동결본 == 현행본 == 실행본) · `bash -n` 통과.
- **v2.11(및 v2.10) 하니스와 byte-동일** — v2.12 도 계약 산문만 수정, 하니스 원문
  불변임을 sha 동일성으로 확인.
- **sha256(harness212.sh) = `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`**

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

## 2. G-양성 전제 실측 — «전제 차이» 표(동결-상대화)의 첫 예측 검증

§12.3.4-G 규칙(*어느 R-단계가 이미 통과하는가를 먼저 적는다*)을 실행 전에 적용했다.
v2.12 마감이 이 표를 **동결-상대화**했고(post-freeze 기본값 = 2-커밋), 현 시점은
동결 직후이므로 표의 post-freeze 열이 적용된다 — 아래 실측이 그 예측과 일치하는지가
이번 실행의 부수 검증점이다.

```text
=== G-양성 전제 실측 (§12.3.4-G 규칙: 어느 R-단계가 이미 통과하는가를 먼저 적는다) ===
실측 시각: 2026-08-15T01:09:08Z · HEAD: cf9b0295ac574b0cb022dd743e42c7aac5113aca

[실측 1] 동결 HEAD 에서 하니스 실행 — 첫 미충족 R-단계의 프로그램 산출:
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness212.sh; echo "harness_rc=$?"
R-0 head=cf9b0295ac574b0cb022dd743e42c7aac5113aca
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1

[실측 2] R-2 보유값 vs 재계산값:
$ git show HEAD:tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md | grep ^bound_set_digest
bound_set_digest: 06cd99c1fac2b63d97bb26b33a66f25e7a2badbb8f326d906a97de17c420d4f2
$ (하니스 R-2 와 동일 파이프라인 재계산)
934516a67b52a9f8724c2516e8bfbccbb6da1a986674e2b540c08ca71853a03f

[실측 3] R-4 상태 — HEAD 트리 최신 스탬프와 verdict 어휘:
$ git ls-tree --name-only HEAD docs/reviews/phase0-completion-contract/ | grep -E "/[0-9]{8}-[0-9]{6}$" | LC_ALL=C sort | tail -1
docs/reviews/phase0-completion-contract/20260815-092111
$ git show HEAD:docs/reviews/phase0-completion-contract/20260815-092111/verdict.md | grep -E "^(adjudicator|verdict):"
adjudicator: codex
verdict: needs-attention

[귀결] R-0·R-1 통과(하니스가 R-2 에서 발화) · R-2 미충족(보유 = 직전 판 digest) ·
       R-4 미충족(needs-attention) · R-7 은 무변이 시나리오라 공집합 예정.
       => «전제 차이» 표의 post-freeze 열이 예측한 그대로 — 미충족 잔여 R-2·R-4 둘,
          필요한 모의 커밋 = 2 (C1 SIMULATED 재결속 + C2 SIMULATED approve verdict).
          동결-상대화(v2.12 마감)가 이 실행에서 처음으로 예측으로 기능했다.
```

**귀결(위 실측 그대로)**: R-2 미충족(보유 `06cd99c1…` = v2.11 digest ≠ 재계산
`934516a6…`)·R-4 미충족(`needs-attention`) → **post-freeze 2-커밋**(C1 재결속 + C2
approve). **«전제 차이» 표의 동결-상대화가 이 실행에서 처음으로 예측으로 기능했다** —
직전 사이클(v2.11)에서는 같은 상황이 문서 기술("1-커밋")과의 불일치로 발견됐고, 이번엔
표가 미리 맞혔다.

---

## 3. 실행본 결속 (§12.3.4-G 블록 + 선언된 변경 3건)

- §12.3.4-G bash 블록(41행 — `D0A_FIRST` 한 줄 표현 포함) verbatim 추출 — 동결본과
  diff 무차이.
- sha256(원문 g-block-212.sh) = `8bbc837d8472841fed8176f7124f82f4e3bd80bcfa5e4d4049110c8efdbe3bd7`
- sha256(실행본 g212-run.sh) = 아래 meta 원문에 기재.
- **선언된 변경 3건과 diff 전문** (그 외 diff 0):

```text
g_block_sha256(원문)=8bbc837d8472841fed8176f7124f82f4e3bd80bcfa5e4d4049110c8efdbe3bd7
g_run_sha256(실행본)=84664836ef50ebf5dd8f40671d339f91b4dc196a299687b7ca0b3f438cb90672
선언된 변경 3건: ① 경로 치환 'bash /path/to/harness.sh' -> 'bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness212.sh' (2곳) ② '# G-양성' 직전 C1 SIMULATED 재결속 블록 11행 삽입 (post-freeze 전제 실측 귀결) ③ 말미 worktree list 1행 추가
-- 블록 원문 대비 diff 전문 --
12c12
< cd "$WT" && bash /path/to/harness.sh && eval "$D0A_FIRST"
---
> cd "$WT" && bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness212.sh && eval "$D0A_FIRST"
18a19,29
> # [삽입 — 전제 실측 귀결 · «전제 차이» 표 post-freeze 열 적용] C1: SIMULATED 재결속 모의
> #   현행 HEAD 는 동결 직후라 R-2 미충족(보유 = 직전 판 digest) — post-freeze 기본값
> #   = 2-커밋. 재결속 모의 형태는 §12.3.4-T T-81-①-e C2 차용.
> BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
> BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
> ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
> NEW=$(cd "$WT" && printf '%s\0' "$BP1" "$BP2" | LC_ALL=C sort -z -u \
>       | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
> (cd "$WT" && perl -pi -e "s/^bound_set_digest:.*/bound_set_digest: $NEW/" "$ART")
> git -C "$WT" commit -am 'C1: SIMULATED rebinding (test fixture only)'
> 
34c45
< cd "$WT" && bash /path/to/harness.sh && eval "$D0A_FIRST"
---
> cd "$WT" && bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness212.sh && eval "$D0A_FIRST"
41a53
> git -C "$REPO" worktree list
```

---

## 4. 실행 기록 (명령·출력 원문 전문 — bash -x 트레이스)

```text
g212_utc=2026-08-15T01:09:41Z  g212_base_head=cf9b0295ac574b0cb022dd743e42c7aac5113aca
$ bash -x /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/g212-run.sh
+ set -u
++ git rev-parse --show-toplevel
+ REPO=/Users/harris/Development/private/kis_unified_sts
++ mktemp -d
+ WT=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g
+ git -C /Users/harris/Development/private/kis_unified_sts worktree add --detach /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g HEAD
작업 트리 준비 중 (분리된 HEAD cf9b0295)
HEAD의 현재 위치는 cf9b0295입니다 docs(tos): phase0 completion contract v2.12 — D0A-FIRST, universal unification, T-83
+ D0A_FIRST='printf "# D0-A first artifact\n" > config/tos_completion.yaml \
           && git add config/tos_completion.yaml \
           && git commit -m "D0-A: introduce config/tos_completion.yaml"'
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness212.sh
R-0 head=cf9b0295ac574b0cb022dd743e42c7aac5113aca
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
+ echo guard_rc=1
guard_rc=1
+ ls -la /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g/config/tos_completion.yaml
ls: /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g/config/tos_completion.yaml: No such file or directory
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g log --oneline --diff-filter=A -- config/tos_completion.yaml
+ BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+ BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
+ ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
++ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g
++ printf '%s\0' docs/plans/2026-08-12-tos-phase0-completion-contract-design.md docs/plans/2026-08-11-tos-completion-development-plan.md
++ LC_ALL=C
++ sort -z -u
++ xargs -0 shasum -a 256
++ shasum -a 256
++ cut '-d ' -f1
+ NEW=934516a67b52a9f8724c2516e8bfbccbb6da1a986674e2b540c08ca71853a03f
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g
+ perl -pi -e 's/^bound_set_digest:.*/bound_set_digest: 934516a67b52a9f8724c2516e8bfbccbb6da1a986674e2b540c08ca71853a03f/' tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g commit -am 'C1: SIMULATED rebinding (test fixture only)'
[HEAD 분리됨 8b74f7f4] C1: SIMULATED rebinding (test fixture only)
 1 file changed, 1 insertion(+), 1 deletion(-)
+ MOCK=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g/docs/reviews/phase0-completion-contract/29991231-235959
+ mkdir -p /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g/docs/reviews/phase0-completion-contract/29991231-235959
+ cat
++ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g rev-parse HEAD
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g add -A
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g commit -m 'SIMULATED approve verdict (test fixture only)'
[HEAD 분리됨 07a16838] SIMULATED approve verdict (test fixture only)
 1 file changed, 6 insertions(+)
 create mode 100644 docs/reviews/phase0-completion-contract/29991231-235959/verdict.md
+ cd /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness212.sh
R-0 head=07a16838226ad45beec16992c470868c395ca76f
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
+ eval 'printf "# D0-A first artifact\n" > config/tos_completion.yaml \
           && git add config/tos_completion.yaml \
           && git commit -m "D0-A: introduce config/tos_completion.yaml"'
++ printf '# D0-A first artifact\n'
++ git add config/tos_completion.yaml
++ git commit -m 'D0-A: introduce config/tos_completion.yaml'
[HEAD 분리됨 1727c441] D0-A: introduce config/tos_completion.yaml
 1 file changed, 1 insertion(+)
 create mode 100644 config/tos_completion.yaml
+ echo guard_rc=0
guard_rc=0
+ git -C /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g log --oneline --diff-filter=A -- config/tos_completion.yaml
1727c441 D0-A: introduce config/tos_completion.yaml
+ git -C /Users/harris/Development/private/kis_unified_sts worktree remove --force /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tuUlsA9pN8/g
+ git -C /Users/harris/Development/private/kis_unified_sts worktree list
/Users/harris/Development/private/kis_unified_sts                                               cf9b0295 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(g212-run.sh exit=0)
```

---

## 5. U-15-e (5) 가드 실행 기록 — 판정 (전부 위 원문에서 그대로)

**가드 명령 원문** (U-15-f-1 — 우변이 실제 D0A-FIRST):

```bash
D0A_FIRST='printf "# D0-A first artifact\n" > config/tos_completion.yaml \
           && git add config/tos_completion.yaml \
           && git commit -m "D0-A: introduce config/tos_completion.yaml"'
cd "$WT" && bash <§12.3.4-R 하니스> && eval "$D0A_FIRST"
echo "guard_rc=$?"
```

- **G-음성 (T-81 ⑪)**: 하니스 `d0a_entry_state=REBINDING_REQUIRED` → `guard_rc=1` →
  트레이스에 `+ eval` **부재**(우변 미도달) → 실측 양쪽 부재:
  `ls: …/config/tos_completion.yaml: No such file or directory` **및**
  `git log --diff-filter=A -- config/tos_completion.yaml` **출력 없음**(도입 커밋 부재).
  차단 상태에서 **실제 착수**가 개시되지 않았다.
- **G-양성 (T-81 ⑫)**: SIMULATED 2-커밋(C1 `8b74f7f4` 재결속 · C2 `07a16838` approve
  verdict, 스탬프 `29991231-235959`·`reviewed_at_head`=C1) 후 하니스
  `d0a_entry_state=ENTRY_OK` → 트레이스에 `+ eval '…'` 실행 관측 → **도입 커밋
  `1727c441` 생성**(`create mode 100644 config/tos_completion.yaml`) → `guard_rc=0` →
  `--diff-filter=A` 가 도입 커밋 **1건**을 실측. 가드가 "항상 막는 것"이 아님이
  실제 행위로 증명되어 음성 레그가 유의미해진다(T-70 교훈·U-15-f-3).

---

## 6. 정리 · 본 저장소 무영향 · 모의물 누출 방지 · D0-A 미착수 불변

```text
=== 사후 검증 (2026-08-15T01:10:09Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               cf9b0295 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
cf9b0295 docs(tos): phase0 completion contract v2.12 — D0A-FIRST, universal unification, T-83
-- 실행 전 스냅샷 대조 --
status: 실행 전과 byte-동일
-- worktree 커밋(모의 2건 + D0A-FIRST 1건) 도달성 (refs 전수) --
$ git log --all --format=%H | grep -c -e 8b74f7f4 -e 07a16838 -e 1727c441
0
= 3건 전부 어떤 ref 에서도 도달 불가
-- 본 저장소: D0-A 미착수 불변 --
$ ls config/tos_completion.yaml
ls: config/tos_completion.yaml: No such file or directory
$ git log --oneline --diff-filter=A -- config/tos_completion.yaml
(출력 없음 = 도입 커밋 부재 — 본 저장소 D0-A 미착수 그대로)
-- 모의 스탬프·ART 무변경 --
(출력 없음 = 부재)
(출력 없음 = 무변경)
-- mktemp 잔여 정리 (본 임무 소유분: tmp.tuUlsA9pN8) --
tmp.tuUlsA9pN8 제거
잔존 없음 확인
```

- worktree 제거·잔여 없음(목록 2건은 기존 별개). status(` M uv.lock`/`?? tools/spikes/`
  — 이전부터 존재)·HEAD(`cf9b0295`) 실행 전과 byte-동일. worktree 커밋 3건(모의 2 +
  D0A-FIRST 1) refs 전수 대조 도달 불가 — **G-양성의 도입 커밋 `1727c441` 도 분리-HEAD
  worktree 산물이라 본 저장소 이력에 없다.** 본 저장소에 `config/tos_completion.yaml`
  파일·도입 커밋 양쪽 부재 = **D0-A 미착수 불변**(v2.12 관측면 그대로 — 이 파일이
  U-15-e transcript 없이 이력에 나타나면 그 출현 자체가 위반 증거).

---

## 7. 직전 transcript(`20260815-040451/U15-ENTRY-CHECK.md`, v2.11 가드 억제)와의 차이

```text
직전 (v2.11)   가드 우변이 대리 행위(touch D0A-STARTED)였다 — 억제 증거의 형태는
               성립했으나 심판(v2.11 재심 #1)이 "증거의 우변이 대리면 증거도
               대리"로 판정했다. 실제 D0-A 최초 행위는 계약에 명명돼 있지 않았다.

이 transcript   v2.12 가 D0A-FIRST 를 명명(config/tos_completion.yaml 도입 커밋 —
               4축 근거)했고, 가드 우변이 그 **실제 행위**다. 음성 레그는 실제
               착수의 부재를 파일·도입 커밋 **양쪽**으로 실측했고, 양성 레그는
               같은 우변이 실제 도입 커밋(1727c441)을 만드는 것까지 도달시켰다 —
               "대리를 실제로"가 심판 Recommendation("실제 D0-A 최초 실행
               표면에서의 억제 증거")의 직접 이행이다.
               부수: «전제 차이» 표의 동결-상대화(post-freeze 2-커밋)가 예측으로
               기능한 첫 사례를 §2 에 기록했다.
```

**소비 조건(U-15-e 소비 조건) 자기 기록**: 이 transcript 의 HEAD 는 `cf9b0295` 다.
진입 시점에 그 이후 `bound_paths` 를 건드린 커밋이 있으면 이 transcript 는 stale 이며
진입 거부다. 본 저장소 현행 산출이 `REBINDING_REQUIRED` 이므로, 6e 재결속과 레인 B
`approve` 취득 후 **그 시점 HEAD 에서 하니스·가드를 재실행한 새 transcript** 가
필요하다 — 이 파일은 그 시점의 `ENTRY_OK` 를 주장하지 않는다. **D0-A 실제 착수는
U-15-f-2 에 따라 가드 형태(`bash <하니스> && <D0A-FIRST>`)로만 개시되며, 그 실행의
U-15-e (5) 기록이 후속 transcript 에 남아야 한다.**
