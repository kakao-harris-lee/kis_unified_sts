# U15-ENTRY-CHECK-V216 — v2.16 U-15-f-1 3단 가드 실행 transcript (G-음성-1 · **G-음성-2 live** · T-81 ⑫ 양성[u17 seam ACTIVE SIMULATED] · ⑬⑯⑲gg 회귀)

> **비규범 부속** — v2.14 재심 스탬프 `20260819-002145` 의 기존 transcript `U15-ENTRY-CHECK.md`(`b453b4e5`)·`U15-ENTRY-CHECK-ADDENDUM.md`(`bf117a8e`)는
> U-15-e (4d) 불변 규율상 편집하지 않으므로 별도 파일이다. **CORR 우주에 관하여**: 계약 U-15-g-3 은 `RUNS = {(t,k): t ∈ 추적 transcript}` 라 적을 뿐
> **파일명 glob(`*/U15-ENTRY-CHECK.md` 등)을 정하지 않으며**, 조건 (4) 가 «d 의 트레일러가 (t,k) 를 지목» 하므로 t 는 트레일러가 이름 짓는 추적 경로다 —
> 따라서 이 파일도 트레일러가 인용하면 우주 안이다(§4 의 모의 d 들이 실제로 이 경로를 인용했다). 그러므로 (4c)(4c-2) 규율을 그대로 지킨다: **하니스 stdout
> 원문만이 run 을 열고**(`^R-0 head=[0-9a-f]{40}$` 행 전체), run 당 `^d0a_entry_state=[A-Z_]+$` 정확히 1개, 산문 재서술은 백틱 인용으로만. u17-verify 의 run 은
> `U17-0 target=…` 라인이 열며(계약 U-15-e (4c-2) 확장) CORR 은 그것을 보지 않는다.
- **생성 시각**: 2026-08-18T17:59:03Z (UTC) · 실행 시각 `t81_v216_utc=` (§4) · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트
- **동결 결속**: 계약 HEAD blob `b246db5c`(sha256 `6e36ea68…`, 6,758행) == `git show eb2805a9:` · 워킹트리 clean(§6). bound_set_digest 는 v2.14 재결속값
  그대로 → 본 저장소 현행 하니스 `REBINDING_REQUIRED`(재결속 대기 · §6 원문).
- **하니스 결속 (4b)**: `git show eb2805a9:<계약> | sed -n '4504,4604p'`(v2.16 에서 블록 시작 행이 4503→4504 로 1행 이동) 추출 = 워킹트리 동일 범위 재추출 =
  v2.10~v2.15 하니스 — **전부 byte-동일 · sha256 `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`** · `bash -n` 통과. v2.16 도 «하니스는
  오프라인·결정적·byte-identical 기준선» 을 유지했음을 실측.
- **실행기 결속**: sha256(u15g-exec215e.sh · 구조 D 8값 실행기 · addendum 과 동일) = `09d542b9db18fac206fc941695112d3cc3994408eaaadcef4a2acafb280dd507` ·
  sha256(u17-verify.sh) = `cd2de1db024f4280a6f67f520e7199d8eee40e7155798063f7a2212fb16f4cad`(원문·독해는 sibling `U17-PREVENTION-CHECK.md` §1) ·
  sha256(t81-lib216.sh) = `4fb1a1fc7864cc1e39b2ba95e9f815d497a964152b07578c414a5daa0548581f` · sha256(t81-v216.sh) =
  `b2e9c08e571655d1fb27780fd8934f57316d75a43711ba2d36451293c6b3c7a1` (원문 §1~§3).
- **(4c-2) 자기 검증**: 이 파일의 `^R-0 head=[0-9a-f]{40}$` opener 는 **10 개**, 각 run 의 상태 라인은 **정확히 1 개**(§8 출력).
- **결과 요약 — 가드 rc·실행기 stdout·rc 원문 그대로 (해석 아님)**:

| 변이 | 구성 (worktree 안 · 3단 `bash 하니스 && bash u17-verify && eval D0A_FIRST`) | u17 responder | guard_rc | 산물 | 실행기 방출값 / rc | 기대 (§12.3.4-G · §8 T-81) | 대조 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **G-음성-1** | 전제 없음(현행 `REBINDING_REQUIRED`) + 아티팩트만 커밋 → 가드 | `gh`(도달 안 함) | 1 | `config/tos_completion.yaml` **부재**·도입 커밋 **부재** | — | 하니스 비-0 → **u17 실행조차 안 됨**: `U17-0 target=` 라인 부재·`+ bash u17-verify` 미출현·`+ eval` 미도달 | **일치** (§4 트레이스: `+ bash harness216.sh` 뒤 바로 `guard_rc=1`) |
| **G-음성-2 (live)** | 2-커밋 전제(ENTRY_OK) + 아티팩트(target=`main`) → 가드 | **`gh` live** | 1 | 파일 **부재**·도입 커밋 **부재** | u17 `PREVENTION_INSUFFICIENT` | «하니스 통과 + u17 차단(현 실측 INSUFFICIENT) → D0A-FIRST 미도달 · guard_rc≠0 · 파일 미생성» — **두 번째 억제 지점, 진짜 음성** | **일치 (인증 live)** — `U17-0 target=` 실재·`+ eval` 미도달 |
| **T-81 ⑫ 양성 (3단)** | 전제 + 아티팩트 → 가드(u17 = seam ACTIVE **SIMULATED**) → d(트레일러 3줄, parent H) → t 를 d 이후 커밋 | `file:seam216/active` | 0 | 파일 **생성**·도입 커밋 `8b2dbb03` | `ENTRY_PROVENANCE_CLEAR` / 0 · `D(structural)=` 1건 | G-양성: guard_rc=0·생성·커밋 · G-부모 `parent(d)==R-0 head`(`63902dec`) · CLEAR/0 | **일치** — 양성은 seam 으로만 구성됨(정직 표기) |
| ⑬ HEAD 이동 (3단) | 가드 좌·중 통과 후 우변 직전 무관 커밋 → d | seam ACTIVE | 0 | 도입 커밋 `e5955992`(parent `d61bef24` ≠ X `07237cff`) | `PARENT_MISMATCH` / 1 | (4)/≠0 | **일치** |
| ⑯ 트레일러 없는 착수 (회귀) | 비가드 d → parent(d) 하니스 재실행 t′ | — | — | 도입 커밋 `d5fca321` | `ENTRY_TRAILER_MALFORMED` / 1 | (3)/≠0 | **일치** |
| ⑲ gg (3단 ∥ 3단) | 두 side 모두 3단 가드(seam ACTIVE)·byte-동일 → 무충돌 머지 | seam ACTIVE | 0·0 | 도입 커밋 2건(`73db3fbb`·`2613ce48`) | `MULTIPLE_INTRODUCTIONS` / 1 · 리터럴 `--diff-filter=A` 는 1건(대조) | (2)/≠0 | **일치** |
| (본 저장소) | 실행기 적용 | — | — | 미착수 | `NOT_STARTED`/0 · u17 `PREVENTION_ABSENT`/1 · 하니스 `REBINDING_REQUIRED`/1 | 비차단 미착수 · 아티팩트 부재 · 재결속 대기 | **일치** (§6) |

전 변이 worktree 한정 · 본 저장소 D0-A 미착수 불변 · 서버 GET-only. 이 transcript 는 본 저장소의 `ENTRY_OK`·`ENTRY_PROVENANCE_CLEAR`·`PREVENTION_ACTIVE`
를 주장하지 않는다 — 기록된 `ENTRY_OK` run 은 전부 worktree 모의 커밋 head 이고, `PREVENTION_ACTIVE` 는 전부 `SIMULATED` seam 이다.

---

## 1. 하니스 명령 원문 (§12.3.4-R v2.16 = `git show eb2805a9:<계약> | sed -n '4504,4604p'` · 생략 없음)

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

## 2. 손 실행기 원문 — `u15g-exec215e.sh` (구조 정의 D · 8값 · sha256 `09d542b9db18fac206fc941695112d3cc3994408eaaadcef4a2acafb280dd507`)

v2.16 은 U-15-g 를 바꾸지 않았다(디프: U-17·U-15-f-1 3단·§12.3.4-G·§8 T-84·§11). addendum(`bf117a8e`) §1 의 실행기·독해 선언 그대로 — 원문 재수록.

```bash
#!/usr/bin/env bash
# U-15-g «손 실행기» — v2.15 에라타(837c35ef) U-15-g-4b 사양 — 8값·전순서 7단 · **D = 구조 정의(E1)**
#   D = { x ⊑ HEAD : path ∈ tree(x) ∧ ∀ p ∈ parents(x): path ∉ tree(p) }   path = config/tos_completion.yaml
#   (머지에서 처음 나타나면 머지 자체가 원소 · 루트는 두 번째 항 공허참 · 구현 플래그(--diff-filter/--full-history) 미사용)
# 산출: stdout 에 d0a_entry_provenance_state=<값> 한 줄 + reason=.  exit 0 = ENTRY_PROVENANCE_CLEAR|NOT_STARTED, 그 외 비-0.
# 사용: bash u15g-exec215e.sh <repo-dir>
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

# ── U-15-g-1 (E1)  판정 우주 D — 구조 정의: x 에 경로 존재 ∧ 모든 부모에 경로 부재 (git rev-list HEAD 전수 순회)
has() { git cat-file -e "$1:$CFG" 2>/dev/null; }
ALL=$(git rev-list HEAD 2>/dev/null) || emit PROVENANCE_UNVERIFIABLE "git rev-list 실패"
D=""
for x in $ALL; do
  has "$x" || continue
  intro=1
  for p in $(git log --format=%P -1 "$x"); do has "$p" && { intro=0; break; }; done
  [ "$intro" = 1 ] && D="$D$x"$'\n'
done
D=$(printf '%s' "$D")
ND=$(printf '%s\n' "$D" | grep -c .); printf 'D(structural)=%s\n' "$(printf '%s\n' "$D" | tr '\n' ' ')"
[ "$ND" -gt 0 ] || emit NOT_STARTED "|D| = 0"
[ "$ND" -eq 1 ] || emit MULTIPLE_INTRODUCTIONS "|D| = $ND — «최초»가 유일하지 않음"
D=$(printf '%s\n' "$D" | head -1)          # |D|=1 확정
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

## 3. 실행 절차 원문 — `t81-lib216.sh` (sha256 `4fb1a1fc7864cc1e39b2ba95e9f815d497a964152b07578c414a5daa0548581f`) · `t81-v216.sh` (sha256 `b2e9c08e571655d1fb27780fd8934f57316d75a43711ba2d36451293c6b3c7a1`)

- lib 는 addendum 의 `t81-lib215e.sh` + **`premise_u17`**(U-17 아티팩트 = 파라미터 선언 `owner_repo/target_branch/tos_gate_check` + E3 countersign, SIMULATED 커밋 P) +
  **`guard3`**(U-15-f-1 3단 · `set -x` 로 `+ bash …`/`+ U17_RESPONDER=…`/`+ eval` 도달 흔적을 남긴다). `T_PATH` = 이 파일의 추적 경로.
- 전제 모의는 post-freeze 2-커밋(C1 재결속·C2 approve) + P(아티팩트). 하니스 R-0 은 `$STAMPS`·`bound_paths`·OQ-11 만 보므로 P 커밋은 R-0 에 무관(실측 ENTRY_OK).
- 저작 측/가드 측 분리·`H → d → commit(t)` 체인·detached side·`sleep 1` 등은 이전 transcript 와 동일.

```bash
# t81-lib216.sh — v2.16(eb2805a9) T-81 3단 가드 변이 공통 (source 용). 전부 scratchpad 하위 detached worktree 안에서만 동작.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
REPO=/Users/harris/Development/private/kis_unified_sts
HARNESS="$SP/harness216.sh"
U17="$SP/u17-verify.sh"
SEAM_ACTIVE="$SP/seam216/active"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
EXEC="$SP/u15g-exec215e.sh"
BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
T_PATH=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md   # 추적 경로 (픽스처 t 의 경로)
AUTHOR_SIDE="$SP/author-side-216"   # §12.3.4-G 의 $REPO(저작 측) 대역 — 가드 worktree 밖에서 t 를 확정한다

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
    echo '- harness: §12.3.4-R (eb2805a9) sha256 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
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

premise_u17() {  # premise_u17 <wt> [<target-branch>] — U-17 아티팩트(파라미터 선언 + countersign) SIMULATED 커밋 P. 진실 원천은 서버(u17-verify 가 live/seam 조회)
  local WT="$1" T="${2:-main}"
  mkdir -p "$WT/$(dirname "$PC")"
  printf 'owner_repo: kakao-harris-lee/kis_unified_sts\ntarget_branch: %s\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n' "$T" > "$WT/$PC"
  git -C "$WT" add "$PC" && git -C "$WT" commit -q -m 'P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; test fixture only)'
  git -C "$WT" log --oneline -1
}

guard3() {  # guard3 <wt> <responder> [<extra-cmd-before-eval>] — U-15-f-1 3단: 하니스 && u17-verify && D0A-FIRST. set -x 로 도달 흔적(`+ bash …`·`+ eval`)을 남긴다
  local WT="$1" R="$2" PRE="${3:-:}"
  ( set -x; cd "$WT" && bash "$HARNESS" && U17_RESPONDER="$R" U17_CAPTURE_DIR="$(mktemp -d)" bash "$U17" && { eval "$PRE"; eval "$D0A_FIRST"; } ) 2>&1
  echo "guard_rc=$?"
}
```

```bash
#!/usr/bin/env bash
# t81-v216.sh — v2.16(eb2805a9) U-15-f-1 3단 가드(하니스 && u17-verify && D0A-FIRST) 실행 드라이버:
#   G-음성-1(하니스 차단 → u17 미도달) · G-음성-2(하니스 통과 + u17 live INSUFFICIENT → D0A-FIRST 미도달) · T-81 ⑫ 양성(3단·u17 seam ACTIVE SIMULATED) · ⑬·⑯·⑲gg 회귀(3단 하).
# 각 변이 = 독립 detached worktree(scratchpad 하위) · 픽스처 t 는 저작 측($AUTHOR_SIDE)에서 확정 후 d 이후 커밋 · GET-only.
source "$(dirname "$0")/t81-lib216.sh"
mkdir -p "$SP/wt" "$AUTHOR_SIDE"
sec() { printf '\n########## %s ##########\n' "$*"; }
hd()  { git -C "$1" rev-parse HEAD; }
absent_check() {  # D0A-FIRST 산물 부재 실측 (파일 + 도입 커밋)
  ls -la "$1/config/tos_completion.yaml" 2>&1; echo "-- git log --diff-filter=A -- config/tos_completion.yaml --"; git -C "$1" log --oneline --diff-filter=A -- config/tos_completion.yaml; echo "(출력 없음 = 도입 커밋 부재)"; }
D0A_FIRST=$(d0a_first_with_trailer "$T_PATH" 1 0000000000000000000000000000000000000000000000000000000000000000)   # 음성 변이용 자리값(도달하지 않으므로 SHA 는 무관)

# ───────────────────────── G-음성-1 — 하니스 차단(현행 REBINDING_REQUIRED) → u17 미도달 → D0A-FIRST 미도달 ─────────────────────────
sec "G-negative-1 — harness blocks (no premise) → u17-verify not reached → D0A-FIRST not reached"
WT=$(wt_new g1); echo "WT=$WT"; echo "HEAD=$(hd "$WT")"; premise_u17 "$WT" main >/dev/null   # 아티팩트만 두어 «u17 이 돌 수 있었으나 도달하지 않음»을 관측 가능하게 한다
echo "-- guard (3단, responder=gh live) --"; guard3 "$WT" gh
echo "-- 도달 흔적: 'U17-0 target=' 라인 부재 = u17 미도달 (위 출력에서 grep) --"
absent_check "$WT"
wt_rm "$WT"

# ───────────────────────── G-음성-2 — 하니스 통과(전제 모의) + u17 live INSUFFICIENT → D0A-FIRST 미도달 ─────────────────────────
sec "G-negative-2 — harness passes (2-commit premise) + u17-verify LIVE (responder=gh, target=main) blocks → D0A-FIRST not reached"
WT=$(wt_new g2); echo "WT=$WT"; premise "$WT"; premise_u17 "$WT" main
echo "-- guard (3단, responder=gh live) --"; guard3 "$WT" gh
absent_check "$WT"
wt_rm "$WT"

# ───────────────────────── T-81 ⑫ 양성 — 3단 가드 · u17 = seam ACTIVE (SIMULATED) ─────────────────────────
sec "T-81 (12) positive — 3-stage guard, u17-verify responder=file:seam216/active (SIMULATED ACTIVE)"
WT=$(wt_new m12); echo "WT=$WT"; premise "$WT"; premise_u17 "$WT" main
H=$(hd "$WT"); echo "H(전제 충족 HEAD)=$H"
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m12-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/m12-harness-out.txt"
fixture_transcript "$AUTHOR_SIDE/m12-harness-out.txt" "$AUTHOR_SIDE/m12-t.md"
T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/m12-t.md" | cut -d' ' -f1); echo "T_SHA=$T_SHA"
D0A_FIRST=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
echo "-- guard (3단) --"; guard3 "$WT" "file:$SEAM_ACTIVE"
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D"; echo "parent(d)=$(git -C "$WT" log --format=%P -1 "$D")  (G-부모: == R-0 head 인가)"
git -C "$WT" log --format=%B -1 "$D" | sed 's/^/  msg| /'
bring_t_after_d "$WT" "$AUTHOR_SIDE/m12-t.md"; git -C "$WT" log --oneline -4
echo "-- executor (structural D) --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑬ HEAD 이동 (3단 하) → PARENT_MISMATCH ─────────────────────────
sec "T-81 (13) HEAD move between guard pass and D0A-FIRST (3-stage, seam ACTIVE)"
WT=$(wt_new m13); echo "WT=$WT"; premise "$WT" >/dev/null; premise_u17 "$WT" main >/dev/null
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m13-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/m13-harness-out.txt"
X=$(grep '^R-0 head=' "$AUTHOR_SIDE/m13-harness-out.txt" | cut -d= -f2); echo "X(하니스 평가 HEAD)=$X"
fixture_transcript "$AUTHOR_SIDE/m13-harness-out.txt" "$AUTHOR_SIDE/m13-t.md"
T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/m13-t.md" | cut -d' ' -f1)
D0A_FIRST=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
echo "-- guard (3단; 우변 직전 무관 커밋으로 HEAD 이동) --"; guard3 "$WT" "file:$SEAM_ACTIVE" "git commit -q --allow-empty -m 'SIMULATED unrelated commit: HEAD move (test fixture only)'"
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D  parent(d)=$(git -C "$WT" log --format=%P -1 "$D")  X=$X"
bring_t_after_d "$WT" "$AUTHOR_SIDE/m13-t.md"
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑯ 트레일러 없는 착수 (회귀) ─────────────────────────
sec "T-81 (16) trailer-less start; harness re-run at parent(d) -> t' (regression)"
WT=$(wt_new m16); echo "WT=$WT"; premise "$WT" >/dev/null; premise_u17 "$WT" main >/dev/null
H=$(hd "$WT"); echo "H=$H"
( cd "$WT" && printf "# D0-A first artifact\n" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m "D0-A: introduce config/tos_completion.yaml" )
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D  parent(d)=$(git -C "$WT" log --format=%P -1 "$D")"
git -C "$WT" checkout -q "$H"; (cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m16-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/m16-harness-out.txt"
fixture_transcript "$AUTHOR_SIDE/m16-harness-out.txt" "$AUTHOR_SIDE/m16-tprime.md"; git -C "$WT" checkout -q "$D"; bring_t_after_d "$WT" "$AUTHOR_SIDE/m16-tprime.md"
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑲ gg — 두 side 모두 3단 가드(seam ACTIVE)·byte-동일 → 구조 D |D|=2 ─────────────────────────
sec "T-81 (19) gg — guarded(3-stage) ∥ guarded(3-stage), byte-identical → MULTIPLE_INTRODUCTIONS"
WT=$(wt_new m19gg); echo "WT=$WT"; premise "$WT" >/dev/null; premise_u17 "$WT" main >/dev/null
H=$(hd "$WT"); echo "H=$H"
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/m19gg-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/m19gg-harness-out.txt"
fixture_transcript "$AUTHOR_SIDE/m19gg-harness-out.txt" "$AUTHOR_SIDE/m19gg-t.md"
T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/m19gg-t.md" | cut -d' ' -f1)
D0A_FIRST=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
side() { git -C "$WT" checkout -q --detach "$H"; ( cd "$WT" && bash "$HARNESS" >/dev/null && U17_RESPONDER="file:$SEAM_ACTIVE" U17_CAPTURE_DIR="$(mktemp -d)" bash "$U17" >/dev/null && eval "$D0A_FIRST" ); echo "$1 guard_rc=$?"; git -C "$WT" rev-parse HEAD; }
O1=$(side side1); echo "$O1" | head -1; B1=$(echo "$O1" | tail -1); sleep 1; O2=$(side side2); echo "$O2" | head -1; B2=$(echo "$O2" | tail -1); echo "side1=$B1 side2=$B2"
git -C "$WT" checkout -q --detach "$B1"; git -C "$WT" merge -q --no-ff -m 'M: merge side2 into side1 (SIMULATED test fixture)' "$B2" 2>/dev/null || echo "(merge conflict — unexpected for gg)"
git -C "$WT" log --graph --oneline -6
echo "[대조] 리터럴 --diff-filter=A ="; git -C "$WT" log --format='  %h %s' --diff-filter=A -- config/tos_completion.yaml
bring_t_after_d "$WT" "$AUTHOR_SIDE/m19gg-t.md"
echo "-- executor (structural D) --"; run_exec "$WT"
wt_rm "$WT"

sec "worktree list (잔여 확인)"
git -C "$REPO" worktree list
```

## 4. 실행 기록 (명령·출력 원문 전문 — 가드 트레이스(`set -x`)·하니스/u17-verify/실행기 stdout 그대로)

```text
t81_v216_utc=2026-08-18T17:53:33Z  base_head=eb2805a910a230583907d560632dd82f71ff403c
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-v216.sh

########## G-negative-1 — harness blocks (no premise) → u17-verify not reached → D0A-FIRST not reached ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/g1
HEAD=eb2805a910a230583907d560632dd82f71ff403c
-- guard (3단, responder=gh live) --
+ cd /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/g1
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness216.sh
R-0 head=785ca09208c8bfc721ce0dd756ac1759a69a33b3
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
guard_rc=1
-- 도달 흔적: 'U17-0 target=' 라인 부재 = u17 미도달 (위 출력에서 grep) --
ls: /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/g1/config/tos_completion.yaml: No such file or directory
-- git log --diff-filter=A -- config/tos_completion.yaml --
(출력 없음 = 도입 커밋 부재)

########## G-negative-2 — harness passes (2-commit premise) + u17-verify LIVE (responder=gh, target=main) blocks → D0A-FIRST not reached ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/g2
1cf41519 C2: SIMULATED approve verdict (test fixture only)
21571f5c C1: SIMULATED rebinding (test fixture only)
eb2805a9 docs(tos): phase0 completion contract v2.16 — U-17 truth source moved to authenticated server evidence
4325fbd9 P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; test fixture only)
-- guard (3단, responder=gh live) --
+ cd /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/g2
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness216.sh
R-0 head=4325fbd949f8d1f01e682df8709fd71056219603
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
+ U17_RESPONDER=gh
++ mktemp -d
+ U17_CAPTURE_DIR=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.97A7pvmwme
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/u17-verify.sh
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=gh params_source=artifact:4325fbd9 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.97A7pvmwme
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:37Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:37Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:38Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T17:53:38Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
guard_rc=1
ls: /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/g2/config/tos_completion.yaml: No such file or directory
-- git log --diff-filter=A -- config/tos_completion.yaml --
(출력 없음 = 도입 커밋 부재)

########## T-81 (12) positive — 3-stage guard, u17-verify responder=file:seam216/active (SIMULATED ACTIVE) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m12
7d98c796 C2: SIMULATED approve verdict (test fixture only)
04704633 C1: SIMULATED rebinding (test fixture only)
eb2805a9 docs(tos): phase0 completion contract v2.16 — U-17 truth source moved to authenticated server evidence
63902dec P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; test fixture only)
H(전제 충족 HEAD)=63902dec8327ef3218502e835d72cf92990396e0
R-0 head=63902dec8327ef3218502e835d72cf92990396e0
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
T_SHA=105de7457676804f9cf45c33700ed92cbce0b464cfac47edaa29c9187e7e3a2e
-- guard (3단) --
+ cd /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m12
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness216.sh
R-0 head=63902dec8327ef3218502e835d72cf92990396e0
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
+ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active
++ mktemp -d
+ U17_CAPTURE_DIR=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FymbZ9X2W5
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/u17-verify.sh
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active params_source=artifact:63902dec capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FymbZ9X2W5
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:41Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:41Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:41Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=63902dec8327ef3218502e835d72cf92990396e0 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) 만으로 판정)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=0) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active
+ eval :
++ :
+ eval 'printf "# D0-A first artifact\n" > config/tos_completion.yaml \
           && git add config/tos_completion.yaml \
           && git commit -q -m "D0-A: introduce config/tos_completion.yaml" \
                         -m "Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md" \
                         -m "Entry-Transcript-Run: 1" \
                         -m "Entry-Transcript-SHA256: 105de7457676804f9cf45c33700ed92cbce0b464cfac47edaa29c9187e7e3a2e"'
++ printf '# D0-A first artifact\n'
++ git add config/tos_completion.yaml
++ git commit -q -m 'D0-A: introduce config/tos_completion.yaml' -m 'Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md' -m 'Entry-Transcript-Run: 1' -m 'Entry-Transcript-SHA256: 105de7457676804f9cf45c33700ed92cbce0b464cfac47edaa29c9187e7e3a2e'
guard_rc=0
d=8b2dbb0306fb38f11589c069b986ed9bc8856a40
parent(d)=63902dec8327ef3218502e835d72cf92990396e0  (G-부모: == R-0 head 인가)
  msg| D0-A: introduce config/tos_completion.yaml
  msg| 
  msg| Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md
  msg| 
  msg| Entry-Transcript-Run: 1
  msg| 
  msg| Entry-Transcript-SHA256: 105de7457676804f9cf45c33700ed92cbce0b464cfac47edaa29c9187e7e3a2e
  msg| 
d6fcdc56 SIMULATED: transcript commit after d (H -> d -> T chain; test fixture only)
8b2dbb03 D0-A: introduce config/tos_completion.yaml
63902dec P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; test fixture only)
7d98c796 C2: SIMULATED approve verdict (test fixture only)
-- executor (structural D) --
D(structural)=8b2dbb0306fb38f11589c069b986ed9bc8856a40 
d=8b2dbb0306fb38f11589c069b986ed9bc8856a40
parent(d)=63902dec8327ef3218502e835d72cf92990396e0
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md run=1 sha=105de7457676804f9cf45c33700ed92cbce0b464cfac47edaa29c9187e7e3a2e
transcript runs=1 cited_run=1 head=63902dec8327ef3218502e835d72cf92990396e0 nstate=1 state=ENTRY_OK
d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR
reason=|CORR(d)|=1 — (t=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md,k=1)
exec_rc=0

########## T-81 (13) HEAD move between guard pass and D0A-FIRST (3-stage, seam ACTIVE) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m13
R-0 head=07237cffeea4ae65b8289066e3ddf007bc071fc1
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
X(하니스 평가 HEAD)=07237cffeea4ae65b8289066e3ddf007bc071fc1
-- guard (3단; 우변 직전 무관 커밋으로 HEAD 이동) --
+ cd /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m13
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/harness216.sh
R-0 head=07237cffeea4ae65b8289066e3ddf007bc071fc1
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
+ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active
++ mktemp -d
+ U17_CAPTURE_DIR=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.N7SEpn7gFr
+ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/u17-verify.sh
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active params_source=artifact:07237cff capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.N7SEpn7gFr
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:54:21Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:54:21Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:54:21Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=07237cffeea4ae65b8289066e3ddf007bc071fc1 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) 만으로 판정)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=0) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active
+ eval 'git commit -q --allow-empty -m '\''SIMULATED unrelated commit: HEAD move (test fixture only)'\'''
++ git commit -q --allow-empty -m 'SIMULATED unrelated commit: HEAD move (test fixture only)'
+ eval 'printf "# D0-A first artifact\n" > config/tos_completion.yaml \
           && git add config/tos_completion.yaml \
           && git commit -q -m "D0-A: introduce config/tos_completion.yaml" \
                         -m "Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md" \
                         -m "Entry-Transcript-Run: 1" \
                         -m "Entry-Transcript-SHA256: 4188c82a6cdcec7f4e52c34968a711e510094e838611a584bbd29372486036e0"'
++ printf '# D0-A first artifact\n'
++ git add config/tos_completion.yaml
++ git commit -q -m 'D0-A: introduce config/tos_completion.yaml' -m 'Entry-Transcript: docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md' -m 'Entry-Transcript-Run: 1' -m 'Entry-Transcript-SHA256: 4188c82a6cdcec7f4e52c34968a711e510094e838611a584bbd29372486036e0'
guard_rc=0
d=e595599233f3fc0f07c741935149917b60207c9a  parent(d)=d61bef246fc5d9e25952c06e1e28f2fb7c02f918  X=07237cffeea4ae65b8289066e3ddf007bc071fc1
-- executor --
D(structural)=e595599233f3fc0f07c741935149917b60207c9a 
d=e595599233f3fc0f07c741935149917b60207c9a
parent(d)=d61bef246fc5d9e25952c06e1e28f2fb7c02f918
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-V216.md run=1 sha=4188c82a6cdcec7f4e52c34968a711e510094e838611a584bbd29372486036e0
transcript runs=1 cited_run=1 head=07237cffeea4ae65b8289066e3ddf007bc071fc1 nstate=1 state=ENTRY_OK
d0a_entry_provenance_state=PARENT_MISMATCH
reason=run 1 head=07237cffeea4ae65b8289066e3ddf007bc071fc1 ≠ parent(d)=d61bef246fc5d9e25952c06e1e28f2fb7c02f918
exec_rc=1

########## T-81 (16) trailer-less start; harness re-run at parent(d) -> t' (regression) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m16
H=c399be9e58dca124e1108d6e8070ad4586292982
d=d5fca321bffd14fe3b9dd6e0ed3e4fe0a743848c  parent(d)=c399be9e58dca124e1108d6e8070ad4586292982
R-0 head=c399be9e58dca124e1108d6e8070ad4586292982
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
-- executor --
D(structural)=d5fca321bffd14fe3b9dd6e0ed3e4fe0a743848c 
d=d5fca321bffd14fe3b9dd6e0ed3e4fe0a743848c
parent(d)=c399be9e58dca124e1108d6e8070ad4586292982
d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED
reason=트레일러 출현 횟수 path=0 run=0 sha=0 (각 1 요구)
exec_rc=1

########## T-81 (19) gg — guarded(3-stage) ∥ guarded(3-stage), byte-identical → MULTIPLE_INTRODUCTIONS ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/m19gg
H=8d1174df6b9089d0847e04d9a2c88e616e37b8e8
R-0 head=8d1174df6b9089d0847e04d9a2c88e616e37b8e8
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
side1 guard_rc=0
side2 guard_rc=0
side1=73db3fbb85ebe79ffa23dd2497bf5b0828659bcb side2=2613ce48648142bebb62c95c1b9c9d45db6139ec
*   738568a4 M: merge side2 into side1 (SIMULATED test fixture)
|\  
| * 2613ce48 D0-A: introduce config/tos_completion.yaml
* | 73db3fbb D0-A: introduce config/tos_completion.yaml
|/  
* 8d1174df P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; test fixture only)
* 68628287 C2: SIMULATED approve verdict (test fixture only)
* d9019ea1 C1: SIMULATED rebinding (test fixture only)
[대조] 리터럴 --diff-filter=A =
  73db3fbb D0-A: introduce config/tos_completion.yaml
-- executor (structural D) --
D(structural)=2613ce48648142bebb62c95c1b9c9d45db6139ec 73db3fbb85ebe79ffa23dd2497bf5b0828659bcb 
d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS
reason=|D| = 2 — «최초»가 유일하지 않음
exec_rc=1

########## worktree list (잔여 확인) ##########
/Users/harris/Development/private/kis_unified_sts                                               eb2805a9 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-v216.sh exit=0)
```

## 5. 픽스처 transcript 원문·sha (트레일러가 인용한 t)

- sha256: m12-t `105de7457676804f9cf45c33700ed92cbce0b464cfac47edaa29c9187e7e3a2e` · m13-t `4188c82a6cdcec7f4e52c34968a711e510094e838611a584bbd29372486036e0` ·
  m16-t′ `a3416733c07f0aa4c1fb7c60f5cfaff3bc967082e65df9439a6f97d0ee2fb505` · m19gg-t `d43616736802ed52b6a82486a3f64630499b9b1b81ff3d598af146779d48e868`
- ⑫ 가 인용한 m12-t.md 원문 전문 (다른 픽스처는 run 1 하니스 출력·`generated_utc` 만 다르다 — §4 에 각 출력 원문 수록):

```text
# U15-ENTRY-CHECK — SIMULATED fixture transcript (test fixture only · worktree-scoped)
- harness: §12.3.4-R (eb2805a9) sha256 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
- generated_utc: 2026-08-18T17:53:40Z
- runs: 아래 각 run 은 `R-0 head=<40hex>` 리터럴 라인으로 열리고 `d0a_entry_state=` 라인 정확히 1개를 가진다 (U-15-e (4c)(4c-2))

## run 1
$ bash harness.sh; echo "harness_rc=$?"
R-0 head=63902dec8327ef3218502e835d72cf92990396e0
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
```

## 6. U-15-e (5) 가드 실행 기록 · 사후 검증 원문

- **가드 명령 원문 (전 변이 공통, worktree)**: `( set -x; cd "$WT" && bash <§12.3.4-R 하니스> && U17_RESPONDER=<gh|file:seam216/active> bash <u17-verify> && { eval "$PRE"; eval "$D0A_FIRST"; } )` —
  `D0A_FIRST` 는 §12.3.4-G 원문(트레일러 3줄 `-m`). G-음성-1: `guard_rc=1`·`+ bash harness216.sh` 뒤 u17 미출현·`U17-0 target=` 부재·산물 부재. **G-음성-2(live)**:
  `guard_rc=1`·하니스 `ENTRY_OK`·`+ U17_RESPONDER=gh` `+ bash u17-verify.sh`·`U17-0 target=kakao-harris-lee/kis_unified_sts@main`·`PREVENTION_INSUFFICIENT`·`+ eval` 미도달·
  산물 부재. ⑫: `guard_rc=0`·`+ eval` 도달·파일 생성·도입 커밋 `8b2dbb03`(parent `63902dec` = run 1 head).
- **본 저장소에서는 가드 형태의 착수를 실행하지 않았다** — 산물 부재·`NOT_STARTED`/0·`PREVENTION_ABSENT`/1·`REBINDING_REQUIRED`/1(아래 원문).

```text
=== 사후 검증 (2026-08-18T17:58:06Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               eb2805a9 [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
eb2805a9 docs(tos): phase0 completion contract v2.16 — U-17 truth source moved to authenticated server evidence
-- 실행 전 스냅샷 대조 --
status/HEAD: 실행 전과 byte-동일
-- worktree D0A-FIRST 커밋 도달성 (git rev-list --all 전수): 8b2dbb03 e5955992 d5fca321 73db3fbb 2613ce48 --
도달 가능 건수=0 (0 기대)
-- 본 저장소 D0-A 미착수 불변 --
ls: config/tos_completion.yaml: No such file or directory
(도입 커밋 출력 없음 = 미착수)
-- 본 저장소 U-17 아티팩트 부재 (진실 원천은 서버이나 파라미터 선언·기록은 아티팩트) --
absent (HEAD 트리)
$ bash u15g-exec215e.sh <repo>
d0a_entry_provenance_state=NOT_STARTED
reason=|D| = 0
exec_rc=0
$ bash u17-verify.sh <repo>
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1
$ bash harness216.sh (본 저장소 현행)
R-0 head=eb2805a910a230583907d560632dd82f71ff403c
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1
-- 서버 설정 무변경 확인 (GET-only 재조회 · 실행 전 캡처와 동일 필드) --
  main: strict=False contexts=['test'] enforce_admins=False pr_reviews=False
  rulesets: [('protect_main', 'disabled')]
-- 모의 스탬프·ART·기존 transcript 무변경 --
(2999* 없음)
(출력 없음 = 무변경)
-- scratchpad 픽스처(독립 repo)·worktree 잔여 --
late live-main live-wb rev-live rev-seam seam seq unsigned 
(wt/ 비어 있음)
```

## 7. 관측·계약 결함 후보 (고치지 않는다 — bound_paths 동결)

1. **G-음성-2 가 live 로 성립** — 계약이 «지금 live 로 실행 가능한 진짜 음성» 이라 적은 그대로: 인증 `gh` 조회가 `INSUFFICIENT` 를 냈고 `&&` 가 우변을 막았다.
   가드 체인의 두 번째 억제 지점이 «산문» 이 아니라 트레이스(`+ eval` 부재)와 산물 부재로 관측됐다.
2. **⑫ 양성의 seam 의존(정직)**: 3단 양성은 u17 seam ACTIVE(SIMULATED)로만 구성된다 — 운영자가 보호를 설정하기 전에는 실측 불가(계약 그대로). 하니스·실행기·D0A-FIRST 는
   실물이며 seam 은 u17 의 «입력» 만 바꾼다(sibling `U17-PREVENTION-CHECK.md` §5-4).
3. **계약 결함 후보(공유)**: countersign 형식 리터럴(E3)이 v2.16 본문에서 소실 · «머지 커밋 check-runs 0건» 사실 정정 — sibling `U17-PREVENTION-CHECK.md` §5-1·§5-2.
4. **U-15-g 델타 0**: 구조 D 실행기가 addendum 과 동일 sha 로 같은 값을 냈다(⑫ CLEAR·⑬ PARENT_MISMATCH·⑯ TRAILER_MALFORMED·⑲gg MULTIPLE_INTRODUCTIONS).
5. **성능 주(비차단)**: 구조 D 전수 순회는 이 저장소(2,149 커밋)에서 run 당 ~36 s — u17-verify 는 같은 술어를 `--full-history` 후보 위에서 평가해 <1 s(완전성 논증은
   sibling §1). u15g 실행기도 같은 최적화가 가능하나 이 사이클에서는 addendum 과의 sha 동일성을 위해 손대지 않았다.

## 8. (4c-2) 자기 검증 출력 · 소비 조건 · 불변 규율

```text
$ awk '<§2 실행기와 같은 opener/상태 술어 · run 별 head·nstate·state 출력>' U15-ENTRY-CHECK-V216.md
run=1 head=785ca09208c8bfc721ce0dd756ac1759a69a33b3 nstate=1 state=REBINDING_REQUIRED
run=2 head=4325fbd949f8d1f01e682df8709fd71056219603 nstate=1 state=ENTRY_OK
run=3 head=63902dec8327ef3218502e835d72cf92990396e0 nstate=1 state=ENTRY_OK
run=4 head=63902dec8327ef3218502e835d72cf92990396e0 nstate=1 state=ENTRY_OK
run=5 head=07237cffeea4ae65b8289066e3ddf007bc071fc1 nstate=1 state=ENTRY_OK
run=6 head=07237cffeea4ae65b8289066e3ddf007bc071fc1 nstate=1 state=ENTRY_OK
run=7 head=c399be9e58dca124e1108d6e8070ad4586292982 nstate=1 state=ENTRY_OK
run=8 head=8d1174df6b9089d0847e04d9a2c88e616e37b8e8 nstate=1 state=ENTRY_OK
run=9 head=63902dec8327ef3218502e835d72cf92990396e0 nstate=1 state=ENTRY_OK
run=10 head=eb2805a910a230583907d560632dd82f71ff403c nstate=1 state=REBINDING_REQUIRED
total_runs=10  (runs with nstate!=1: 0)
u17 run opener 라인(`U17-0 target=` 로 시작) 수: 3 (G-음성-2 · ⑫ · ⑬ = 3 — G-음성-1 에는 없음)
```

- **소비 조건 (U-15-e (6))**: 이 파일의 실 저장소 HEAD 는 `eb2805a9`(v2.16 동결). 본 저장소 현행 하니스 `REBINDING_REQUIRED` — 6e 재결속·레인 B `approve` 후 그 시점
  HEAD 의 새 transcript 가 필요하고, D0-A 진입은 3단(하니스 ENTRY_OK ∧ u17-verify **live** ACTIVE ∧ D0A-FIRST)이며 오늘 live 는 `INSUFFICIENT`/`ABSENT` 다.
- **불변 규율 (U-15-e (4d))**: 이 파일도 발행 시점에 확정되며 이후 편집하지 않는다. 보정은 새 스탬프의 새 파일로 한다.
