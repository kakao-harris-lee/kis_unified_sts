# U15-ENTRY-CHECK — v2.14 T-81 ⑫⑬⑭⑮⑯⑰⑱ 실행 transcript (pre-D0-A · U-15-f-5 트레일러 / U-15-g CORR(d) 7값·전순서 6단)

- **목적**: 레인 B v2.13 재심 verdict(`20260818-224729`, NOT_PASSED)이 소비된 스탬프에 귀속되는
  이번 사이클 실행 증거. v2.14(동결 커밋 `db19a0e8`, HEAD=INDEX 커밋 `3107d0be`)가 신설한
  **U-15-f-5 트레일러**(`Entry-Transcript`/`-Run`/`-SHA256`)·**CORR(d) 조건 (4)**·**U-15-g-4
  7값 + 전순서 6단**·**U-15-g-4b 손 실행기 규율**의 대조군 **T-81 ⑫(양성)·⑬·⑭·⑮·⑯·⑰ⓐⓑⓒ·⑱ +
  H6 경계 2종**을 실행하고 U-15-e (1)(2)(3)(4)(4b)(4c)(4c-2)(4d)(5)(6) 결속으로 남긴다.
  ⑭⑮(v2.13 변이)는 v2.14 실행기로 재실행한 회귀 확인이다.
- **생성 시각**: 2026-08-18T15:04:12Z (UTC)
- **생성 주체**: 오케스트레이터 지시 하의 실행 에이전트
- **동결 결속**: 지시된 동결 digest `9dbf672549cba4c3fc0ac53b07120133e9afd43108295b398e2d91f5eb07798e` 는
  **bound_set_digest 방식**(두 bound_paths 결합 재계산)으로 재현 일치 확인. 단일 파일 sha 는
  `9e2abf76…`(blob id `964db54a`) — 표기 방식 차이일 뿐 동일 내용. OQ-11 아티팩트 보유값은
  `796ca1e0…`(v2.13 digest) → 현행 하니스 산출 `REBINDING_REQUIRED`(재결속 대기) 정합.
- **하니스 결속 (4b)**: §12.3.4-R 블록을 `git show db19a0e8:` 에서 추출, 워킹트리 재추출과 diff
  무차이 · `bash -n` 통과 · **sha256 = `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`
  — v2.10~v2.13 하니스와 byte-동일**(v2.14 도 하니스 원문 불변 선언 그대로).
- **결과 요약 — 실행기 stdout·rc 원문 그대로 (해석 아님)**:

| 변이 | 구성 (worktree 안) | 방출값 `d0a_entry_provenance_state=` | rc | 기대 | 대조 |
| --- | --- | --- | --- | --- | --- |
| ⑫ 양성 | 2-커밋 전제 → 하니스 `ENTRY_OK`(head H) → 픽스처 t 확정·SHA → 가드 `bash harness && D0A_FIRST(트레일러 3줄)` → d(parent H) → t 를 d 이후 커밋 | `ENTRY_PROVENANCE_CLEAR` | 0 | CLEAR/0 | **일치** |
| ⑬ HEAD 이동 | 하니스 통과(X) → 우변 실행 전 무관 커밋(Y) → d(parent Y)·트레일러 정상 | `PARENT_MISMATCH` | 1 | PARENT_MISMATCH(3)/≠0 | **일치** |
| ⑭ 비가드 (v2.13 정의) | 동결 HEAD 에서 하니스·트레일러 없이 d | `ENTRY_TRAILER_MALFORMED` | 1 | §8 ⑭ 행 리터럴 `TRANSCRIPT_MISSING` / U-15-f-5·전순서·⑯ H1 주 `ENTRY_TRAILER_MALFORMED` | **§8 ⑭ 행 리터럴과 불일치 — §7 보고** |
| ⑮ 전진-머지 (v2.13 정의) | parent=`cf9b0295`(기존 transcript R-0 head)·트레일러 없음 → 3107d0be 머지 | `ENTRY_TRAILER_MALFORMED` | 1 | "red"(값 미특정) | **일치(red)** |
| ⑯ 트레일러 없는 착수 | 전제 → ⓐ 하니스 없이 d(트레일러 0줄) → ⓑ parent(d)에서 하니스 재실행 t′ | `ENTRY_TRAILER_MALFORMED` | 1 | ENTRY_TRAILER_MALFORMED(2)/≠0 | **일치** |
| ⑰ⓐ 1줄 누락 | Run 줄 없음 | `ENTRY_TRAILER_MALFORMED` | 1 | (2)/≠0 | **일치** |
| ⑰ⓑ 같은 줄 2회 | Run 줄 2회 | `ENTRY_TRAILER_MALFORMED` | 1 | (2)/≠0 | **일치** |
| ⑰ⓒ SHA256 불일치 | SHA 000… | `ENTRY_TRAILER_MALFORMED` | 1 | (2)/≠0 | **일치** |
| H6-i 인용 run 부재 | Run: 99 | `TRANSCRIPT_MISSING` | 1 | (5)/≠0 | **일치** |
| H6-ii 인용 경로 부재 | 부재 경로 | `TRANSCRIPT_MISSING` | 1 | (5)/≠0 | **일치** |
| ⑱ 인용 run 차단 상태 | 동결 HEAD 하니스 `REBINDING_REQUIRED` 기록 t → d(parent HEAD)·트레일러 정상 | `TRANSCRIPT_NOT_ENTRY_OK` | 1 | (4)/≠0 | **일치** |
| (본 저장소) | 손 실행기를 본 저장소에 적용 | `NOT_STARTED` | 0 | 비차단·미착수 | **일치** (§6) |

전 변이 worktree 한정·본 저장소 D0-A 미착수 불변(§6). 이 transcript 는 본 저장소의 `ENTRY_OK` 나
`ENTRY_PROVENANCE_CLEAR` 를 주장하지 않는다 — 여기 기록된 `ENTRY_OK` run 들은 전부 worktree 모의
커밋 head 라 어떤 실 저장소 d 의 부모와도 일치하지 않는다.

---

## 1. 하니스 명령 원문 (§12.3.4-R v2.14 · 생략 없음)

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

## 2. 손 실행기 (U-15-g-4b 사양) — 원문 + 독해 선언

**sha256(u15g-exec.sh) = `62338bdbb6b6f0f4ad00868821a67568eb14d71d50f47b80a03ed16a2a7de338`**

독해 선언(계약 정본·참고 구현 `A/corr2.sh` 는 참고만):
- **(4c)(4c-2) run 경계**: «`R-0 head=<40hex>` 리터럴 라인이 run 을 연다»를 **행 전체 일치**
  (`^R-0 head=[0-9a-f]{40}$`)로 읽는다 — 하니스 `printf 'R-0 head=%s\n'` 가 방출하는 그 행이며,
  산문·코드 안의 부분 문자열은 opener 가 아니다. 상태 라인도 `^d0a_entry_state=[A-Z_]+$` 행 전체.
  `k` = 1-기반 출현 순서 · run 범위 = 다음 opener 직전까지 · 상태 라인 0/2+ = 형식 미충족(→ 5).
- **평가 순서 vs 전순서**: 방출값 전순서 6단(1 UNVERIFIABLE · 2 TRAILER_MALFORMED · 3 PARENT_MISMATCH ·
  4 NOT_ENTRY_OK · 5 MISSING · 6 CLEAR)을 따르되, 3·4 는 «인용 run 이 실재» 를 전제하므로 인용
  대상 부재(경로·run·형식)는 3·4 앞에서 5 로 방출한다(H6: 경로 부재는 SHA 계산 불가 → 5). 여러
  값이 동시 성립하는 경우 어느 값을 내는가는 전순서 그대로다(⑬ 은 트레일러 정상이므로 2 가 아닌 3).
- 단일 성공 경로 2곳(`ENTRY_PROVENANCE_CLEAR`·`NOT_STARTED` → exit 0) · 그 외 전부 exit 1 ·
  `trap EXIT` 가 판정 없이 끝나는 경로를 `PROVENANCE_UNVERIFIABLE` 로 폐쇄 · RUNS 는 (파일, run) 쌍.

```bash
#!/usr/bin/env bash
# U-15-g «손 실행기» — v2.14 U-15-g-4b 사양 (계약 db19a0e8 §12.3.4 U-15-g-3/4/4b·U-15-f-5·U-15-e (4c)(4c-2))
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

# ── U-15-g-1/2  판정 우주 = D0A-FIRST 도입 커밋
D=$(git log --format=%H --diff-filter=A -- "$CFG" 2>/dev/null) || emit PROVENANCE_UNVERIFIABLE "git log 실패"
[ -n "$D" ] || emit NOT_STARTED "도입 커밋 ∅"
D=$(printf '%s\n' "$D" | tail -1)          # 최초 도입(1건 기대)
PARENT=$(git log --format=%P -1 "$D" | awk '{print $1}')
MSG=$(git log --format=%B -1 "$D")
printf 'd=%s\nparent(d)=%s\n' "$D" "$PARENT"

# ── 전순서 2  트레일러 (U-15-f-5: 3줄 각각 정확히 1회 · 형식 · SHA256)
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

# ── 전순서 5 (H6 경계)  인용 경로 부재 → SHA 계산 불가 → TRANSCRIPT_MISSING
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

# ── 전순서 3  부모 결속 (U-15-f-4)
[ "$HEAD_K" = "$PARENT" ] || emit PARENT_MISMATCH "run $TR head=$HEAD_K ≠ parent(d)=$PARENT"

# ── 전순서 4  인용 run 의 판정값
[ "$ST" = ENTRY_OK ] || emit TRANSCRIPT_NOT_ENTRY_OK "run $TR 상태=$ST"

# ── 전순서 6
emit ENTRY_PROVENANCE_CLEAR "|CORR(d)|=1 — (t=$TP,k=$TR)"
```

---

## 3. 실행 절차 원문 (공통 lib + 드라이버) — 저작 선언

**sha256(t81-lib.sh) = `0bc4253da4cfc9c7f0755eec1f297bc1c05d30d1fce57a196414a25f86752ea4` · sha256(t81-v214.sh) = `ecc97f796dfc383dfe67ba3299268c59aa7adff54843b4b7f7396d260838ff6b`**

- 전제 모의는 «전제 차이» 표 post-freeze **2-커밋**(C1 SIMULATED 재결속 · C2 SIMULATED approve,
  스탬프 `29991231-235959`). D0A-FIRST 트레일러 형태·가드 형태·G-부모 대조는 §12.3.4-G 블록
  (sha `4a42b90c5c7fee4cc44370bf2293c4d3a99f9ecb55444f779fcab7ed3903ab54`, 동결본 일치) 원문 차용.
- **픽스처 transcript t 의 위치 — 실측 근거**: 하니스 R-0 은 `$STAMPS` 하위 미커밋 파일을 `??` 로
  잡아 `FREEZE_VIOLATED` 를 낸다(§5 프로브 실측). 따라서 §12.3.4-G 의 `T_SHA=$(shasum "$T_PATH")` 는
  cwd=`$REPO`(저작 측)에서 뜨고 가드는 clean `$WT` 에서 도는 것이 정합이다 — 이 실행은 저작 측을
  scratchpad `author-side/` 로, 가드를 detached worktree 로 두고, **d 이후에** t 를 추적 경로에 커밋
  (정직 체인 `H → d → commit(t)`; 계약 «정직 경계» 절이 기술한 흐름)해 실행기가 읽게 했다.
- 픽스처 t 는 U-15-e (4c)(4c-2) 형식(하니스 출력 원문만이 run 을 연다)이며 §5 에 원문·sha 수록.

```bash
# t81-lib.sh — v2.14 T-81 변이 공통 (source 용). 전부 scratchpad 하위 detached worktree 안에서만 동작.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
REPO=/Users/harris/Development/private/kis_unified_sts
HARNESS="$SP/harness214.sh"
EXEC="$SP/u15g-exec.sh"
BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
T_PATH=docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md   # 추적 경로 (픽스처 t 의 경로)
AUTHOR_SIDE="$SP/author-side"   # §12.3.4-G 의 $REPO(저작 측) 대역 — 가드 worktree 밖에서 t 를 확정한다

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
    echo '- harness: §12.3.4-R (db19a0e8) sha256 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
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
# t81-v214.sh — v2.14 T-81 변이 ⑫⑬⑭⑮⑯⑰ⓐⓑⓒ⑱ + H6 경계 실행 드라이버.
# 각 변이 = 독립 detached worktree(scratchpad 하위) · 픽스처 t 는 저작 측($AUTHOR_SIDE)에서 확정 후 필요 시 d 이후 커밋.
source "$(dirname "$0")/t81-lib.sh"
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
git -C "$WT" merge -q --no-edit 3107d0bec047af0005f920a96d7db32ce51f0f9a && git -C "$WT" log --oneline -3
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

sec "worktree list (잔여 확인)"
git -C "$REPO" worktree list
```

---

## 4. 실행 기록 (명령·출력 원문 전문 — 각 변이 worktree · 하니스/실행기 stdout 그대로)

```text
t81_v214_utc=2026-08-18T14:57:19Z  base_head=3107d0bec047af0005f920a96d7db32ce51f0f9a
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-v214.sh

########## T-81 (12) positive — guard with trailer ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m12
936ff112 C2: SIMULATED approve verdict (test fixture only)
eede24d4 C1: SIMULATED rebinding (test fixture only)
3107d0be docs(plans): INDEX — phase0 completion contract v2.14 frozen (db19a0e8)
H(전제 충족 HEAD)=936ff11210fb141ef3b924aece7fe044353bded4
R-0 head=936ff11210fb141ef3b924aece7fe044353bded4
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
T_SHA=697674d4a0e040838e560c1ee0edf2ddac3e1c3bd11cee6eca1e149f23272b70
R-0 head=936ff11210fb141ef3b924aece7fe044353bded4
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
guard_rc=0
56a3f83d D0-A: introduce config/tos_completion.yaml
d=56a3f83d8b8bc1b928dbc4223f6d3834ea0c63bc
parent(d)=936ff11210fb141ef3b924aece7fe044353bded4
D0-A: introduce config/tos_completion.yaml

Entry-Transcript: docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md

Entry-Transcript-Run: 1

Entry-Transcript-SHA256: 697674d4a0e040838e560c1ee0edf2ddac3e1c3bd11cee6eca1e149f23272b70

a9915976 SIMULATED: transcript commit after d (H -> d -> T chain; test fixture only)
56a3f83d D0-A: introduce config/tos_completion.yaml
936ff112 C2: SIMULATED approve verdict (test fixture only)
-- executor --
d=56a3f83d8b8bc1b928dbc4223f6d3834ea0c63bc
parent(d)=936ff11210fb141ef3b924aece7fe044353bded4
trailer: path=docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md run=1 sha=697674d4a0e040838e560c1ee0edf2ddac3e1c3bd11cee6eca1e149f23272b70
transcript runs=1 cited_run=1 head=936ff11210fb141ef3b924aece7fe044353bded4 nstate=1 state=ENTRY_OK
d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR
reason=|CORR(d)|=1 — (t=docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md,k=1)
exec_rc=0

########## T-81 (13) HEAD move between harness pass and D0A-FIRST ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m13
R-0 head=8ea4679be76e18c869452e203546d9d77d7ce08c
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
X(하니스 평가 HEAD)=8ea4679be76e18c869452e203546d9d77d7ce08c
R-0 head=8ea4679be76e18c869452e203546d9d77d7ce08c
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
guard_rc=0
d=ad324341a1590c4f831913b67ec917ece52118c9
parent(d)=d630fcfc4272bb129294c1f606339f4ec439259c  X=8ea4679be76e18c869452e203546d9d77d7ce08c
-- executor --
d=ad324341a1590c4f831913b67ec917ece52118c9
parent(d)=d630fcfc4272bb129294c1f606339f4ec439259c
trailer: path=docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md run=1 sha=1d9022bdd76550e220290a282a9c1efa1fe7faf5a841617a56b9df51057d429f
transcript runs=1 cited_run=1 head=8ea4679be76e18c869452e203546d9d77d7ce08c nstate=1 state=ENTRY_OK
d0a_entry_provenance_state=PARENT_MISMATCH
reason=run 1 head=8ea4679be76e18c869452e203546d9d77d7ce08c ≠ parent(d)=d630fcfc4272bb129294c1f606339f4ec439259c
exec_rc=1

########## T-81 (14) unguarded start at frozen HEAD, no trailer (v2.13 def re-run on v2.14 executor) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m14
HEAD=3107d0bec047af0005f920a96d7db32ce51f0f9a
commit_rc=0
d=2a0f0e92d669857d05b99c535d5ba06beb33bb9e  parent(d)=3107d0bec047af0005f920a96d7db32ce51f0f9a
-- executor --
d=2a0f0e92d669857d05b99c535d5ba06beb33bb9e
parent(d)=3107d0bec047af0005f920a96d7db32ce51f0f9a
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=0 run=0 sha=0 (각 1 요구)
exec_rc=1

########## T-81 (15) forward-merge bypass (v2.13 def re-run on v2.14 executor) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m15
HEAD=cf9b0295ac574b0cb022dd743e42c7aac5113aca
8a302ba2 Merge commit '3107d0bec047af0005f920a96d7db32ce51f0f9a' into HEAD
3f8f025a D0-A: introduce config/tos_completion.yaml
3107d0be docs(plans): INDEX — phase0 completion contract v2.14 frozen (db19a0e8)
d=3f8f025a226adaf3c290f17fc7e84ac75c92c0e7  parent(d)=cf9b0295ac574b0cb022dd743e42c7aac5113aca
-- executor --
d=3f8f025a226adaf3c290f17fc7e84ac75c92c0e7
parent(d)=cf9b0295ac574b0cb022dd743e42c7aac5113aca
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=0 run=0 sha=0 (각 1 요구)
exec_rc=1

########## T-81 (16) trailer-less start; then harness re-run at parent(d) -> t' ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m16
H=17254a6b4e1b234a9634243a1aca98f8ebfe3b79
d=e5314cac748da2fc8bb29227a35060dd81f1efad  parent(d)=17254a6b4e1b234a9634243a1aca98f8ebfe3b79
R-0 head=17254a6b4e1b234a9634243a1aca98f8ebfe3b79
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
t' sha=f7a2b4c1a48a4040cc072c6042d3c127461149e2323d20792f89420ba65d004c
35b1770f SIMULATED: transcript commit after d (H -> d -> T chain; test fixture only)
e5314cac D0-A: introduce config/tos_completion.yaml
17254a6b C2: SIMULATED approve verdict (test fixture only)
-- executor --
d=e5314cac748da2fc8bb29227a35060dd81f1efad
parent(d)=17254a6b4e1b234a9634243a1aca98f8ebfe3b79
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=0 run=0 sha=0 (각 1 요구)
exec_rc=1

########## T-81 (17) trailer malformed a/b/c + H6 boundary ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m17
H=846fa7796d0b415a095ad6e175bce04fc9a0cd01
R-0 head=846fa7796d0b415a095ad6e175bce04fc9a0cd01
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
T_SHA=d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4
---- (17)a: Run line missing ----
d=a9d055ff4c56400f95a998c1588e678ae163be3d  parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md
  msg| 
  msg| Entry-Transcript-SHA256: d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4
  msg| 
-- executor --
d=a9d055ff4c56400f95a998c1588e678ae163be3d
parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=1 run=0 sha=1 (각 1 요구)
exec_rc=1
---- (17)b: Run line twice ----
d=0cafe8fadb6a6c72309d460a773b72a66cdd3897  parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-SHA256: d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4
  msg| 
-- executor --
d=0cafe8fadb6a6c72309d460a773b72a66cdd3897
parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=1 run=2 sha=1 (각 1 요구)
exec_rc=1
---- (17)c: SHA256 mismatch ----
d=d2e3e387838e6620f1ff44ac92b59237d4d964f3  parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-SHA256: 0000000000000000000000000000000000000000000000000000000000000000
  msg| 
-- executor --
d=d2e3e387838e6620f1ff44ac92b59237d4d964f3
parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
trailer: path=docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md run=1 sha=0000000000000000000000000000000000000000000000000000000000000000
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=SHA256 불일치: 실제=d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4
exec_rc=1
---- (17)H6-i: cited run absent ----
d=dbb6e3c25ce2381ae1ba2d05ccede0f1fbd32100  parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md
  msg| 
  msg| Entry-Transcript-Run: 99
  msg| 
  msg| Entry-Transcript-SHA256: d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4
  msg| 
-- executor --
d=dbb6e3c25ce2381ae1ba2d05ccede0f1fbd32100
parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
trailer: path=docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md run=99 sha=d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4
transcript runs=1 cited_run=99 head=NONE nstate=0 state=NONE
d0a_entry_provenance_state=TRANSCRIPT_MISSING
reason=인용 run 99 부재 (transcript 내 run 수=1)
exec_rc=1
---- (17)H6-ii: cited path absent ----
d=871480bbfdba1a296b89e6000abee8adb713649c  parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260818-224729/NO-SUCH-FILE.md
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-SHA256: d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4
  msg| 
-- executor --
d=871480bbfdba1a296b89e6000abee8adb713649c
parent(d)=846fa7796d0b415a095ad6e175bce04fc9a0cd01
trailer: path=docs/reviews/phase0-completion-contract/20260818-224729/NO-SUCH-FILE.md run=1 sha=d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4
d0a_entry_provenance_state=TRANSCRIPT_MISSING
reason=인용 transcript 경로 부재: docs/reviews/phase0-completion-contract/20260818-224729/NO-SUCH-FILE.md
exec_rc=1

########## T-81 (18) cited run recorded a blocked state ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m18
H(동결 HEAD·전제 없음)=3107d0bec047af0005f920a96d7db32ce51f0f9a
R-0 head=3107d0bec047af0005f920a96d7db32ce51f0f9a
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1
T_SHA=6be2c0c7fa38a60bf5af7c96d139210d3c7410cd0f748ebf536119fe72ec2370
commit_rc=0
d=9b816eb7860b76855e4c32d0bb24e54cdca2338a  parent(d)=3107d0bec047af0005f920a96d7db32ce51f0f9a
-- executor --
d=9b816eb7860b76855e4c32d0bb24e54cdca2338a
parent(d)=3107d0bec047af0005f920a96d7db32ce51f0f9a
trailer: path=docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md run=1 sha=6be2c0c7fa38a60bf5af7c96d139210d3c7410cd0f748ebf536119fe72ec2370
transcript runs=1 cited_run=1 head=3107d0bec047af0005f920a96d7db32ce51f0f9a nstate=1 state=REBINDING_REQUIRED
d0a_entry_provenance_state=TRANSCRIPT_NOT_ENTRY_OK
reason=run 1 상태=REBINDING_REQUIRED
exec_rc=1

########## worktree list (잔여 확인) ##########
/Users/harris/Development/private/kis_unified_sts                                               3107d0be [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-v214.sh exit=0)
```

---

## 5. 픽스처 transcript 원문·sha (트레일러가 인용한 t) + R-0 프로브

- sha256: m12-t `697674d4a0e040838e560c1ee0edf2ddac3e1c3bd11cee6eca1e149f23272b70` · m13-t `1d9022bdd76550e220290a282a9c1efa1fe7faf5a841617a56b9df51057d429f` · m16-t′ `f7a2b4c1a48a4040cc072c6042d3c127461149e2323d20792f89420ba65d004c` · m17-t `d4f87cd861f9f79a8cfeadf8797c8e957f006358300268f029eb59b9822782f4` · m18-t `6be2c0c7fa38a60bf5af7c96d139210d3c7410cd0f748ebf536119fe72ec2370`
- 아래는 ⑫ 가 인용한 m12-t.md 원문 전문 (다른 픽스처는 run 1 의 하니스 출력만 다르다 — §4 에 각 출력 원문 수록):

```text
# U15-ENTRY-CHECK — SIMULATED fixture transcript (test fixture only · worktree-scoped)
- harness: §12.3.4-R (db19a0e8) sha256 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
- generated_utc: 2026-08-18T14:57:21Z
- runs: 아래 각 run 은 `R-0 head=<40hex>` 리터럴 라인으로 열리고 `d0a_entry_state=` 라인 정확히 1개를 가진다 (U-15-e (4c)(4c-2))

## run 1
$ bash harness.sh; echo "harness_rc=$?"
R-0 head=936ff11210fb141ef3b924aece7fe044353bded4
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
```

- **R-0 프로브 실측** (§3 독해의 근거 — 미커밋 t 가 `$STAMPS` 하위에 있을 때 하니스):

```text
$ (worktree @3107d0be) echo x > docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md
$ git status --porcelain -- docs/reviews/phase0-completion-contract
?? docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md
$ bash harness214.sh; echo rc=$?
R-0 head=3107d0bec047af0005f920a96d7db32ce51f0f9a
d0a_entry_state=FREEZE_VIOLATED
reason=권위 입력 미커밋 변경: ?? docs/reviews/phase0-completion-contract/20260818-224729/U15-ENTRY-CHECK.md;
rc=1
```

---

## 6. U-15-e (5) 가드 실행 기록 · 정리 · 본 저장소 무영향

- **가드 명령 원문 (⑫·⑬, worktree)**: `cd "$WT" && bash <§12.3.4-R 하니스> && eval "$D0A_FIRST"` — `D0A_FIRST` 는
  §12.3.4-G 원문(트레일러 3줄 `-m` 포함). ⑫ `guard_rc=0`, D0A-FIRST 산물 존재: 파일 + 도입 커밋
  `56a3f83d`(parent `936ff112` = run 1 head) → 실행기 `ENTRY_PROVENANCE_CLEAR`/0. ⑬ `guard_rc=0`, 도입
  커밋 `ad324341`(parent `d630fcfc` ≠ X `8ea4679b`) → `PARENT_MISMATCH`/1.
- **본 저장소에서는 가드 형태의 착수를 실행하지 않았다** — D0A-FIRST 산물 부재(파일·도입 커밋 양쪽,
  아래 실측)·손 실행기 `NOT_STARTED`/0.

```text
=== 사후 검증 (2026-08-18T15:02:00Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               3107d0be [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
3107d0be docs(plans): INDEX — phase0 completion contract v2.14 frozen (db19a0e8)
-- 실행 전 스냅샷 대조 --
status/HEAD: 실행 전과 byte-동일
-- worktree D0A-FIRST 커밋 도달성 (refs 전수): 0cafe8fa 2a0f0e92 3f8f025a 56a3f83d 871480bb 9b816eb7 a9d055ff ad324341 d2e3e387 dbb6e3c2 e5314cac --
도달 가능 건수=0 (0 기대)
-- 본 저장소 D0-A 미착수 불변 --
ls: config/tos_completion.yaml: No such file or directory
(도입 커밋 출력 없음 = NOT_STARTED)
$ bash u15g-exec.sh <repo>   # 본 저장소에 손 실행기 적용
d0a_entry_provenance_state=NOT_STARTED
reason=도입 커밋 ∅
exec_rc=0
-- 모의 스탬프·ART·기존 transcript 무변경 --
(2999* 없음)
(출력 없음 = 무변경)
-- scratchpad 픽스처 repo (독립·본 저장소 무관) --
15
17a
17b
17c
18
h52.json
iii.json
(wt/ 비어 있음 = worktree 잔여 없음)
```

---

## 7. 기대 밖·계약 불일치 보고 (고치지 않는다 — bound_paths 동결)

1. **T-81 ⑭ 기대값 — §8 T-81 행(:2903) 리터럴 vs 전순서**: §8 ⑭ 정의는 «`CORR(d)` 공집합 →
   `TRANSCRIPT_MISSING` 으로 red» 라 적혀 있으나(v2.13 마감 문언 잔존), v2.14 U-15-f-5 «3줄 각각 정확히
   1회» + U-15-g-4 전순서(2 가 5 를 앞선다) + ⑯ H1 주(«0회는 `ENTRY_TRAILER_MALFORMED`»)에 따라 트레일러
   0줄인 비가드 d 의 방출값은 **`ENTRY_TRAILER_MALFORMED`** 다(실측). 극성(차단·rc≠0)은 동일하며 계약
   자신이 ⑯ 에서 같은 시나리오의 값을 정정해 두었으므로 §8 ⑭ 행의 문언만 미전파된 것으로 본다
   (S-20 계열). ⑮ 행은 "red" 로만 적혀 있어 값 충돌 없음(실측 `ENTRY_TRAILER_MALFORMED`).
2. **§12.3.4-G T_PATH 위치의 함의(실측 §5)**: G-양성 스니펫을 «가드 worktree 안에 t 를 두고» 읽으면
   하니스 R-0 이 `FREEZE_VIOLATED` 를 내 양성이 성립하지 않는다. 스니펫의 cwd 구조(`T_SHA` 는 `$REPO`,
   가드는 `$WT`)로 읽으면 정합 — 문서 결함이 아니라 **독해 주의점**으로 기록한다(계약 «정직 경계» 절의
   `H → d → commit(t)` 서술과 일치). 다음 개정에서 스니펫 주석으로 명시하면 오독 클래스가 닫힌다.

---

## 8. 직전 transcript(`20260815-144959`, v2.13 ⑬⑭⑮)와의 차이 · 소비 조건 · 불변 규율

```text
직전 (v2.13)   손 실행기가 |CORR|=0 만 방출하고 상태값·red 는 산문 판정 · (4c) 형식 검증 없음 ·
               파일당 접기 — U-15-g-4b 가 그 셋을 결함으로 명시했다.
이 transcript   실행기가 7값 중 하나를 프로그램 방출 + rc 극성 + trap EXIT + (4c)(4c-2) 형식 검증 +
               (파일, run) 쌍 전개. 신설 조건 (4)(트레일러·SHA 결속)로 양성 ⑫ 가 CLEAR/0 에
               실제 도달했고, ⑬⑯⑰⑱ + H6 가 전순서 3·2·2·4·5 를 서로 다른 값으로 고정했다.
               ⑭⑮ 회귀는 v2.14 에서 트레일러 축(2)으로 먼저 잡힘을 실측(§7-1).
```

- **소비 조건 (U-15-e (6))**: 이 transcript 의 실 저장소 HEAD 는 `3107d0be`(동결 `db19a0e8` + INDEX).
  이후 `bound_paths` 를 건드린 커밋이 있으면 stale 이며 진입 거부다. 본 저장소 현행 하니스 산출은
  `REBINDING_REQUIRED` — 6e 재결속·레인 B `approve` 후 그 시점 HEAD 의 새 transcript 가 필요하다.
- **불변 규율 (U-15-e (4d))**: 이 파일은 발행 시점에 확정되며 이후 편집하지 않는다(트레일러 SHA 결속의
  전제). 보정은 새 스탬프의 새 파일로 한다.
