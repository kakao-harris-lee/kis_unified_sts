# U15-ENTRY-CHECK-ADDENDUM — v2.15 에라타 `837c35ef` 후 재실행 (구조 정의 D — T-81 ⑫·⑲ gg/gu/uu · U-17 countersign 형식 — T-84 ①②③④+부속)

> **에라타 `837c35ef` 후 재실행 — 본 transcript `U15-ENTRY-CHECK.md`(커밋 `b453b4e5`) 는 U-15-e (4d) 불변 규율상 편집하지
> 않으므로 별도 파일이다. 비규범 부속** — 계약이 경로·형식을 규정하지 않은 보충 증거이며, 본 transcript 가 보고한 결함
> 후보 3건(E1 U-15-g-1 `D` 플래그 의존 · E2 §8 T-82 ⑰ⓑ 기대 · E3 U-17-b countersign 형식)이 계약에 반영된 뒤 **그 반영이
> 실행기·대조군에서 실제로 닫히는지**를 같은 절차로 재실측한 기록이다. 판정 우주(RUNS)에 드는 파일이므로 (4c)(4c-2) 형식
> 규율(하니스 stdout 원문만이 run 을 연다·run 당 상태 라인 정확히 1개)을 그대로 지킨다.
- **생성 시각**: 2026-08-18T17:04:18Z (UTC) · 실행 시각은 각 절 원문의 `*_utc=` 라인 · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트
- **동결 결속**: 계약 파일 워킹트리 == `git show 837c35ef:` (6,633행 · `git status --short -- docs/plans` 무출력, §5 원문).
  bound_set_digest 는 v2.14 재결속값 그대로라 본 저장소 현행 하니스 산출 `REBINDING_REQUIRED`(§5 원문) — 재결속 대기 정합.
- **하니스 결속 (4b)**: `git show 837c35ef:<계약> | sed -n '4503,4603p'` 추출 = 워킹트리 동일 범위 재추출 = 본 transcript 의
  `harness215.sh` — **전부 byte-동일 · sha256 `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`** · `bash -n` 통과
  (에라타는 하니스 원문을 건드리지 않았다 — 실측).
- **실행기 결속**: sha256(u15g-exec215e.sh) = `09d542b9db18fac206fc941695112d3cc3994408eaaadcef4a2acafb280dd507` ·
  sha256(u17-exec-e.sh) = `087e49862c0534f0c8da7bf14bf3850d653437bedb25b303603ed57141549039` ·
  sha256(t81-lib215e.sh) = `4335786687e82d65ebcebe7002a1be0fd0a7652d7d50aea6f2b2b2ec92181b1b` ·
  sha256(t81-v215e.sh) = `56c18b45f0486da01e68299d2a45edb7a3141e66d7e74c970fab000e93a1e298` ·
  sha256(t84e.sh) = `9cf53f8e34924098635fa10adb83c942b92ae233d85696e65014f669620a8cac` (원문 전부 §1~§4 수록).
- **(4c-2) 자기 검증**: 이 파일에서 `^R-0 head=[0-9a-f]{40}$` 행 전체 일치로 열리는 run 은 **6 개**, 각 run 의 `^d0a_entry_state=[A-Z_]+$`
  상태 라인은 **정확히 1 개**(검증 출력 §6).
- **결과 요약 — 실행기 stdout·rc 원문 그대로 (해석 아님)**:

### T-81 (`d0a_entry_provenance_state=` · 구조 정의 D 실행기 `u15g-exec215e.sh`)

| 변이 | 구성 (worktree 안) | 방출값 | rc | 기대 (에라타 §8 T-81 ⑲ · U-15-g-1/2) | 대조 | 본 실행(b453b4e5) 대비 |
| --- | --- | --- | --- | --- | --- | --- |
| ⑫ 양성 회귀 | 2-커밋 전제 → 하니스 `ENTRY_OK`(H) → 가드 `bash harness && D0A_FIRST(트레일러)` → d(parent H) → t 를 d 이후 커밋 | `ENTRY_PROVENANCE_CLEAR` · `D(structural)=` 1건 | 0 | 구조 D 에서도 \|D\|=1 → CLEAR/0 | **일치** | 불변 |
| **⑲ gg** (guarded ∥ guarded · byte-동일 내용) | 전제 H → d1·d2 둘 다 가드+동일 트레일러 → **무충돌 머지** M | **`MULTIPLE_INTRODUCTIONS`** · `D(structural)=` 2건 | **1** | 에라타 §8 ⑲ «셋 다 MULTIPLE_INTRODUCTIONS + rc≠0 · gg 가 핵심» | **일치 — red 로 전환** | 본 실행 CLEAR/0 → **red** |
| ⑲ gg 대조 | 같은 worktree | 리터럴 `--diff-filter=A` = **1건**(`9dda9395`) · `--full-history` = 2건 | — | 구정의(리터럴)는 이력 단순화로 1건 — 에라타 E1 의 근거 재현 | **병기** | 동일 관측 |
| ⑲ gu (guarded ∥ unguarded) | 내용 상이 → add/add 충돌 → 해소 머지 | `MULTIPLE_INTRODUCTIONS` · 2건 | 1 | (2)/≠0 | **일치** | 불변 |
| ⑲ uu (unguarded ∥ unguarded) | 내용 상이 → 충돌 → 해소 머지 | `MULTIPLE_INTRODUCTIONS` · 2건 | 1 | (2)/≠0 | **일치** | 불변 |
| (본 저장소) | 구조 D 실행기를 본 저장소에 적용 | `NOT_STARTED` · `D(structural)=` ∅ | 0 | 비차단·미착수 | **일치** (§5) | 불변 |

### T-84 (`prevention_control_state=` · E3 countersign 형식 반영 U-17 실행기 `u17-exec-e.sh` — 독립 git 픽스처 `fx84e/*`)

| 변이 | 픽스처 (아티팩트 원문·DAG 는 §4) | 방출값 | rc | 기대 (§8 T-84 행 · U-17-b ③ E3 · U-17-c2) | 대조 |
| --- | --- | --- | --- | --- | --- |
| ① 아티팩트 부재 (d 존재) | seed → d | `PREVENTION_ABSENT` | 1 | ABSENT/≠0 | **일치** |
| ②-i countersign 부재 | P(`operator_countersign:` 키 0회) → d | `PREVENTION_UNSIGNED`(키 출현 0) | 1 | UNSIGNED/≠0 | **일치** |
| ②-ii 형식 위반 (큰따옴표 없음·ISO-8601 UTC 아님) | P(`operator_countersign: APPROVED 2026-08-19 (…)`) → d | `PREVENTION_UNSIGNED`(값 형식 위반) | 1 | «값이 이 형식이 아님 = UNSIGNED» | **일치** |
| ②-iii 형식 위반 (따옴표 有·날짜만) | P(`"operator 2026-08-19"`) → d | `PREVENTION_UNSIGNED`(값 형식 위반) | 1 | UNSIGNED | **일치** |
| ②-iv 키 2회 | P(키 2행) → d | `PREVENTION_UNSIGNED`(키 출현 2) | 1 | UNSIGNED(정확히 1회 독해) | **일치** |
| ③ 양성 — P 뒤 d | P(E3 형식 `"operator 2026-08-19T00:00:00Z"` + 활성 주장 ①②) → d | `PREVENTION_ACTIVE` | 0 | ACTIVE/0 | **일치** |
| ④ d 먼저·P 나중 | d → P | `PREVENTION_LATE` | 1 | LATE/≠0 | **일치** |
| 부속 D=∅ | P 만 | `PREVENTION_ACTIVE` | 0 | «비교 대상 없음» 명시 통과 | **일치** |
| 부속 \|D\|=2 · P 가 한쪽만 앞섬 | side1 d(P 이전) ∥ side2 P→d → M1·M2 | `PREVENTION_LATE` | 1 | ∀d∈D: P ⊰ d 위반 | **일치** |
| (본 저장소) | 실행기 적용 | `PREVENTION_ABSENT` | 1 | «현재 평가는 PREVENTION_ABSENT» | **일치** (§5) |

- **T-82 ⑰ⓑ (E2)**: 실행 결과 불변 — 본 실행(b453b4e5 `U16-LEDGER-CHECK.md`) 의 `APPROVAL_UNBOUND`/1 이 에라타 §8 ⑰ⓑ 기대값
  `APPROVAL_UNBOUND` 와 이제 리터럴 일치한다(재실행 불요 — 실행기·픽스처 무변경, 계약 문언만 정정).

전 T-81 변이 worktree 한정·T-84 는 scratchpad 독립 저장소·본 저장소 D0-A 미착수 불변(§5). 이 파일은 본 저장소의 `ENTRY_OK`·
`ENTRY_PROVENANCE_CLEAR`·`PREVENTION_ACTIVE` 를 주장하지 않는다 — 기록된 `ENTRY_OK` run 들은 전부 worktree 모의 커밋 head 다.

---

## 1. 구조 정의 D 실행기 `u15g-exec215e.sh` — 원문 + 독해 선언 (sha256 `09d542b9db18fac206fc941695112d3cc3994408eaaadcef4a2acafb280dd507`)

- **본 transcript 실행기(`0425800…`) 대비 델타는 U-15-g-1 D 산출 하나뿐**: 리터럴 `git log --diff-filter=A` → 계약 E1 구조 정의
  `D = { x ⊑ HEAD : path ∈ tree(x) ∧ ∀p∈parents(x): path ∉ tree(p) }` 를 `git rev-list HEAD` 전수 순회 + `git cat-file -e x:path` /
  `p:path` 로 파생(구현 플래그 미사용 · 루트는 두 번째 항 공허참 · 머지에서 처음 나타나면 머지 자체가 원소 — U-16-g6 `C_R` 실행기와
  같은 형태). 나머지(전순서 7단·트레일러·(4c)(4c-2)·H6·성공 경로 2곳·trap EXIT)는 본 transcript §2 독해 선언 그대로.
- 진단 출력 `D(structural)=` 는 산출 우주 원문(공백 구분). `|D|=1` 확정 시 `head -1`(원소가 하나라 순서 무관).

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

## 2. 실행 절차 원문 — `t81-lib215e.sh` (sha256 `4335786687e82d65ebcebe7002a1be0fd0a7652d7d50aea6f2b2b2ec92181b1b`) · `t81-v215e.sh` (sha256 `56c18b45f0486da01e68299d2a45edb7a3141e66d7e74c970fab000e93a1e298`)

- lib 는 본 transcript §3 `t81-lib215.sh` 와 동일 절차(전제 2-커밋 모의·저작 측/가드 측 분리·`H → d → commit(t)` 체인) — 델타는
  `HARNESS`/`EXEC`/`AUTHOR_SIDE` 경로와 **`T_PATH` = 이 파일의 추적 경로**(픽스처 t 가 인용되는 경로), 픽스처 머리의 `(837c35ef)` 표기뿐.
- 드라이버는 ⑫ + ⑲ gg/gu/uu 만 실행한다(⑬~⑱·H6 은 D 산출 이후 경로라 델타 없음 — 본 transcript 결과 유효). ⑲ 에서 리터럴
  `--diff-filter=A` 와 `--full-history` 를 **대조 출력**으로 병기(판정에는 미사용).

```bash
# t81-lib215e.sh — v2.15 에라타(837c35ef) T-81 보충 변이 공통 (source 용). 전부 scratchpad 하위 detached worktree 안에서만 동작.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
REPO=/Users/harris/Development/private/kis_unified_sts
HARNESS="$SP/harness215e.sh"
EXEC="$SP/u15g-exec215e.sh"
BP1=docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
BP2=docs/plans/2026-08-11-tos-completion-development-plan.md
ART=tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md
T_PATH=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-ADDENDUM.md   # 추적 경로 (픽스처 t 의 경로)
AUTHOR_SIDE="$SP/author-side-215e"   # §12.3.4-G 의 $REPO(저작 측) 대역 — 가드 worktree 밖에서 t 를 확정한다

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
    echo '- harness: §12.3.4-R (837c35ef) sha256 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
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
# t81-v215e.sh — v2.15 에라타(837c35ef) 보충: T-81 ⑫ 양성 회귀 + ⑲ gg/gu/uu 재실행 — 구조 정의 D 실행기(u15g-exec215e.sh).
# 각 변이 = 독립 detached worktree(scratchpad 하위) · 픽스처 t 는 저작 측($AUTHOR_SIDE)에서 확정 후 d 이후 커밋.
source "$(dirname "$0")/t81-lib215e.sh"
mkdir -p "$SP/wt" "$AUTHOR_SIDE"
sec() { printf '\n########## %s ##########\n' "$*"; }
hd()  { git -C "$1" rev-parse HEAD; }

# ───────────────────────── ⑫ 양성 회귀 — 구조 D 에서도 |D|=1 → CLEAR/0 ─────────────────────────
sec "T-81 (12) positive regression on structural-D executor"
WT=$(wt_new e12); echo "WT=$WT"; premise "$WT"
H=$(hd "$WT"); echo "H(전제 충족 HEAD)=$H"
(cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/e12-harness-out.txt" 2>&1
cat "$AUTHOR_SIDE/e12-harness-out.txt"
fixture_transcript "$AUTHOR_SIDE/e12-harness-out.txt" "$AUTHOR_SIDE/e12-t.md"
T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/e12-t.md" | cut -d' ' -f1); echo "T_SHA=$T_SHA"
D0A_FIRST=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
( cd "$WT" && bash "$HARNESS" && eval "$D0A_FIRST" ); echo "guard_rc=$?"
D=$(git -C "$WT" log --format=%H --diff-filter=A -1 -- config/tos_completion.yaml); echo "d=$D"; echo "parent(d)=$(git -C "$WT" log --format=%P -1 "$D")"
bring_t_after_d "$WT" "$AUTHOR_SIDE/e12-t.md"
git -C "$WT" log --oneline -3
echo "-- executor --"; run_exec "$WT"
wt_rm "$WT"

# ───────────────────────── ⑲ 병렬 도입 머지 — gg / gu / uu (기대 전부 MULTIPLE_INTRODUCTIONS rc≠0) ─────────────────────────
par19() {  # par19 <label> <mode1> <mode2>   mode ∈ {guarded,unguarded}
  local label="$1" m1="$2" m2="$3"
  sec "T-81 (19) parallel introduction — $label (structural-D executor)"
  WT=$(wt_new "e19-$label"); echo "WT=$WT"; premise "$WT" >/dev/null
  local H; H=$(hd "$WT"); echo "H(전제 충족 HEAD)=$H"
  (cd "$WT" && bash "$HARNESS"; echo "harness_rc=$?") > "$AUTHOR_SIDE/e19-$label-harness-out.txt" 2>&1; cat "$AUTHOR_SIDE/e19-$label-harness-out.txt"
  fixture_transcript "$AUTHOR_SIDE/e19-$label-harness-out.txt" "$AUTHOR_SIDE/e19-$label-t.md"
  local T_SHA; T_SHA=$(shasum -a 256 "$AUTHOR_SIDE/e19-$label-t.md" | cut -d' ' -f1)
  local D0A_G; D0A_G=$(d0a_first_with_trailer "$T_PATH" 1 "$T_SHA")
  intro() {  # intro <label> <mode> — H 에서 «detached» 로 config 도입 (브랜치 ref 를 만들지 않는다)
    git -C "$WT" checkout -q --detach "$H"
    if [ "$2" = guarded ]; then ( cd "$WT" && bash "$HARNESS" >/dev/null && eval "$D0A_G" ); echo "$1 guard_rc=$?"
    else ( cd "$WT" && printf "# D0-A first artifact (%s)\n" "$1" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m "D0-A: introduce config/tos_completion.yaml" ); echo "$1 commit_rc=$?"; fi
    git -C "$WT" rev-parse HEAD
  }
  local B1 B2; B1=$(intro side1 "$m1" | tail -1); sleep 1; B2=$(intro side2 "$m2" | tail -1); echo "side1=$B1 side2=$B2"
  git -C "$WT" checkout -q --detach "$B1"
  git -C "$WT" merge -q --no-ff -m 'M: merge side2 into side1 (SIMULATED test fixture)' "$B2" 2>/dev/null \
    || { (cd "$WT" && printf "# D0-A first artifact (merge-resolved)\n" > config/tos_completion.yaml && git add config/tos_completion.yaml && git commit -q -m 'M: merge side2 into side1 (conflict resolved; SIMULATED test fixture)'); }
  git -C "$WT" log --graph --oneline -6
  echo "[대조] 리터럴 --diff-filter=A (v2.15 U-15-g-1 구정의) ="; git -C "$WT" log --format='  %h %s' --diff-filter=A -- config/tos_completion.yaml
  echo "[대조] --full-history --diff-filter=A ="; git -C "$WT" log --full-history --format='  %h %s' --diff-filter=A -- config/tos_completion.yaml
  bring_t_after_d "$WT" "$AUTHOR_SIDE/e19-$label-t.md"
  echo "-- executor (structural D) --"; run_exec "$WT"
  wt_rm "$WT"
}
par19 gg guarded guarded
par19 gu guarded unguarded
par19 uu unguarded unguarded

sec "worktree list (잔여 확인)"
git -C "$REPO" worktree list
```

## 3. 실행 기록 — T-81 ⑫·⑲ gg/gu/uu (명령·출력 원문 전문 — 하니스/실행기 stdout 그대로)

```text
t81_v215e_utc=2026-08-18T16:59:10Z  base_head=837c35ef263213901f84e4bf3095908f3c67f50d
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t81-v215e.sh

########## T-81 (12) positive regression on structural-D executor ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/e12
ee431827 C2: SIMULATED approve verdict (test fixture only)
8c2cbd35 C1: SIMULATED rebinding (test fixture only)
837c35ef docs(tos): phase0 completion contract v2.15 errata — structural D universe, ⑰ⓑ expectation, countersign format
H(전제 충족 HEAD)=ee43182773c157da317f31c2d2c8d209db024e3d
R-0 head=ee43182773c157da317f31c2d2c8d209db024e3d
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
T_SHA=dbf33895bf40ac260825ee77282d8f278201938bfe72e23c2238704c90b1f922
R-0 head=ee43182773c157da317f31c2d2c8d209db024e3d
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
guard_rc=0
d=400ebf87c245753970429bf81f7d223209fd6d7b
parent(d)=ee43182773c157da317f31c2d2c8d209db024e3d
e1a980c9 SIMULATED: transcript commit after d (H -> d -> T chain; test fixture only)
400ebf87 D0-A: introduce config/tos_completion.yaml
ee431827 C2: SIMULATED approve verdict (test fixture only)
-- executor --
D(structural)=400ebf87c245753970429bf81f7d223209fd6d7b 
d=400ebf87c245753970429bf81f7d223209fd6d7b
parent(d)=ee43182773c157da317f31c2d2c8d209db024e3d
trailer: path=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-ADDENDUM.md run=1 sha=dbf33895bf40ac260825ee77282d8f278201938bfe72e23c2238704c90b1f922
transcript runs=1 cited_run=1 head=ee43182773c157da317f31c2d2c8d209db024e3d nstate=1 state=ENTRY_OK
d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR
reason=|CORR(d)|=1 — (t=docs/reviews/phase0-completion-contract/20260819-002145/U15-ENTRY-CHECK-ADDENDUM.md,k=1)
exec_rc=0

########## T-81 (19) parallel introduction — gg (structural-D executor) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/e19-gg
H(전제 충족 HEAD)=43553f47afb529fd3c5ccfe3028a5a36174d17ca
R-0 head=43553f47afb529fd3c5ccfe3028a5a36174d17ca
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
side1=9dda9395ea407dfbb2de64ea92fbc0b30f86be92 side2=1db2ea938c492fd285f014b107a03e6901323e59
*   3eef49ef M: merge side2 into side1 (SIMULATED test fixture)
|\  
| * 1db2ea93 D0-A: introduce config/tos_completion.yaml
* | 9dda9395 D0-A: introduce config/tos_completion.yaml
|/  
* 43553f47 C2: SIMULATED approve verdict (test fixture only)
* 5565b73d C1: SIMULATED rebinding (test fixture only)
* 837c35ef docs(tos): phase0 completion contract v2.15 errata — structural D universe, ⑰ⓑ expectation, countersign format
[대조] 리터럴 --diff-filter=A (v2.15 U-15-g-1 구정의) =
  9dda9395 D0-A: introduce config/tos_completion.yaml
[대조] --full-history --diff-filter=A =
  1db2ea93 D0-A: introduce config/tos_completion.yaml
  9dda9395 D0-A: introduce config/tos_completion.yaml
-- executor (structural D) --
D(structural)=1db2ea938c492fd285f014b107a03e6901323e59 9dda9395ea407dfbb2de64ea92fbc0b30f86be92 
d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS
reason=|D| = 2 — «최초»가 유일하지 않음
exec_rc=1

########## T-81 (19) parallel introduction — gu (structural-D executor) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/e19-gu
H(전제 충족 HEAD)=570b9e075db531dde1b63afa6acf80e51d3ad331
R-0 head=570b9e075db531dde1b63afa6acf80e51d3ad331
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
side1=9958cc6a8131cbe5e1281464c62cbcf24b7979fc side2=029b946a638fe95358804fcf77e8cccd78175ca4
자동 병합: config/tos_completion.yaml
충돌 (추가/추가): config/tos_completion.yaml에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
*   2385e3d5 M: merge side2 into side1 (conflict resolved; SIMULATED test fixture)
|\  
| * 029b946a D0-A: introduce config/tos_completion.yaml
* | 9958cc6a D0-A: introduce config/tos_completion.yaml
|/  
* 570b9e07 C2: SIMULATED approve verdict (test fixture only)
* 9accafb0 C1: SIMULATED rebinding (test fixture only)
* 837c35ef docs(tos): phase0 completion contract v2.15 errata — structural D universe, ⑰ⓑ expectation, countersign format
[대조] 리터럴 --diff-filter=A (v2.15 U-15-g-1 구정의) =
  029b946a D0-A: introduce config/tos_completion.yaml
  9958cc6a D0-A: introduce config/tos_completion.yaml
[대조] --full-history --diff-filter=A =
  029b946a D0-A: introduce config/tos_completion.yaml
  9958cc6a D0-A: introduce config/tos_completion.yaml
-- executor (structural D) --
D(structural)=029b946a638fe95358804fcf77e8cccd78175ca4 9958cc6a8131cbe5e1281464c62cbcf24b7979fc 
d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS
reason=|D| = 2 — «최초»가 유일하지 않음
exec_rc=1

########## T-81 (19) parallel introduction — uu (structural-D executor) ##########
WT=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/wt/e19-uu
H(전제 충족 HEAD)=8755f915c999f63f940f16a2044a1393b6f37ad5
R-0 head=8755f915c999f63f940f16a2044a1393b6f37ad5
R-3 verdict=docs/reviews/phase0-completion-contract/29991231-235959
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
harness_rc=0
side1=578d270b3da6d2ff9e163bca0eaf7a1e09f274c3 side2=e3b059b1fc0da930ee51ec3d30dc3795b42b84f1
자동 병합: config/tos_completion.yaml
충돌 (추가/추가): config/tos_completion.yaml에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
*   1d2bdc24 M: merge side2 into side1 (conflict resolved; SIMULATED test fixture)
|\  
| * e3b059b1 D0-A: introduce config/tos_completion.yaml
* | 578d270b D0-A: introduce config/tos_completion.yaml
|/  
* 8755f915 C2: SIMULATED approve verdict (test fixture only)
* 03b53c7d C1: SIMULATED rebinding (test fixture only)
* 837c35ef docs(tos): phase0 completion contract v2.15 errata — structural D universe, ⑰ⓑ expectation, countersign format
[대조] 리터럴 --diff-filter=A (v2.15 U-15-g-1 구정의) =
  e3b059b1 D0-A: introduce config/tos_completion.yaml
  578d270b D0-A: introduce config/tos_completion.yaml
[대조] --full-history --diff-filter=A =
  e3b059b1 D0-A: introduce config/tos_completion.yaml
  578d270b D0-A: introduce config/tos_completion.yaml
-- executor (structural D) --
D(structural)=e3b059b1fc0da930ee51ec3d30dc3795b42b84f1 578d270b3da6d2ff9e163bca0eaf7a1e09f274c3 
d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS
reason=|D| = 2 — «최초»가 유일하지 않음
exec_rc=1

########## worktree list (잔여 확인) ##########
/Users/harris/Development/private/kis_unified_sts                                               837c35ef [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
(t81-v215e.sh exit=0)
```

## 4. T-84 — E3 반영 U-17 실행기 `u17-exec-e.sh` (sha256 `087e49862c0534f0c8da7bf14bf3850d653437bedb25b303603ed57141549039`) · 드라이버 `t84e.sh` (sha256 `9cf53f8e34924098635fa10adb83c942b92ae233d85696e65014f669620a8cac`) · 실행 기록

독해 선언(본 transcript §5 대비 델타):
- **countersign (E3)**: `operator_countersign:` 키 **정확히 1회** · 값 = `"<운영자 식별> <ISO-8601 UTC>"` — 큰따옴표 안에 «비어 있지 않은
  식별(공백 포함 가능·선행 공백 불가) + 단일 공백 + `YYYY-MM-DDTHH:MM:SSZ`»; 값 뒤 YAML 주석(`# …`)은 값이 아니므로 허용(계약 예시
  행 자체가 주석을 달고 있다). **`authority:` 는 더 이상 요구하지도 검사하지도 않는다**(에라타: 6e 의 `authority` 키를 재사용하지 않는다).
  정규식 원문은 실행기 `CS_RE`. 사전 프로브: 정상값·주석 부가·괄호 포함 식별 → MATCH / 따옴표 없음·날짜만·빈 식별·빈 값 → nomatch.
- **P·D 는 구조 정의**(E1 과 같은 형태 — 경로 존재 ∧ 모든 부모에 부재; `git rev-list HEAD` 전수) — 본 transcript 실행기의 `--diff-filter=A | tail -1` 대체.
- 본 transcript §5 가 정직 표기한 오타(`PREVENENTION_ABSENT`) 교정.
- 픽스처 `art()` 의 countersign 5형(정상 · 부재 · 큰따옴표 없음+비-ISO · 날짜만 · 키 2회) — ② 를 «부재·형식 위반» 양쪽 + 키 중복까지 3분해.

```bash
#!/usr/bin/env bash
# U-17 «예방 통제 활성 증거» 손 실행기 — v2.15 에라타(837c35ef) U-17-b/c/c2 · **E3 countersign 키·값 형식 고정**
#   P = D0A-PREVENTION-CONTROL.md 를 도입한 커밋 · D = config/tos_completion.yaml 도입 커밋 집합 (E1 구조 정의)
#   ACTIVE ⇔ 아티팩트 ∧ countersign(`operator_countersign: "<운영자 식별> <ISO-8601 UTC>"` 정확히 1회 · 형식 일치)
#            ∧ 활성 주장(required_check:·branch_protection: enabled·activated_at_head: <40hex>) ∧ ∀d∈D: P ⊰ d   (D=∅ 는 «비교 대상 없음» 명시 통과)
#   전순서: PREVENTION_ABSENT > PREVENTION_UNSIGNED > PREVENTION_LATE > PREVENTION_ACTIVE.  exit 0 = ACTIVE 만.
# 사용: bash u17-exec-e.sh <repo>
set -u -o pipefail
EMITTED=0
emit() { EMITTED=1; printf 'prevention_control_state=%s\nreason=%s\n' "$1" "$2"; [ "$1" = PREVENTION_ACTIVE ] && exit 0; exit 1; }
trap '[ "$EMITTED" -eq 1 ] || { printf "prevention_control_state=%s\nreason=%s\n" PREVENTION_ABSENT "판정 미산출 상태로 종료(fail-closed)"; exit 1; }' EXIT
cd "${1:?repo}" || emit PREVENTION_ABSENT "repo 진입 실패"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
CFG=config/tos_completion.yaml
# ── ABSENT: 아티팩트가 HEAD 트리에 부재 (커밋-전용 읽기) · P = 아티팩트 도입 커밋(구조 정의 — 경로 존재 ∧ 모든 부모에 부재; 복수면 ABSENT 아님·최초 1건은 rev-list 역순 마지막)
BODY=$(git show "HEAD:$PC" 2>/dev/null) || emit PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"
hasp() { git cat-file -e "$1:$PC" 2>/dev/null; }
P=""
for x in $(git rev-list HEAD); do
  hasp "$x" || continue; intro=1
  for p in $(git log --format=%P -1 "$x"); do hasp "$p" && { intro=0; break; }; done
  [ "$intro" = 1 ] && P="$x"          # rev-list 는 자손→조상 순이므로 마지막 대입 = 가장 오래된 도입 지점
done
[ -n "$P" ] || emit PREVENTION_ABSENT "도입 커밋 P 파생 불가"
printf 'P=%s\n' "$P"
# ── UNSIGNED (E3): `operator_countersign:` 키 정확히 1회 · 값 = "<운영자 식별> <ISO-8601 UTC>" (큰따옴표 · 식별자 비어 있지 않음 · 단일 공백 · YYYY-MM-DDTHH:MM:SSZ)
CS_RE='^operator_countersign:[[:space:]]*"[^"[:space:]][^"]* [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"[[:space:]]*(#.*)?$'   # 값 뒤 YAML 주석(#…)은 값이 아니므로 허용
nk=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:')
[ "$nk" = 1 ] || emit PREVENTION_UNSIGNED "operator_countersign 키 출현 횟수=$nk (정확히 1 요구)"
printf '%s\n' "$BODY" | grep -Eq "$CS_RE" || emit PREVENTION_UNSIGNED "operator_countersign 값 형식 위반: $(printf '%s\n' "$BODY" | grep '^operator_countersign:')"
# ── 활성 주장 필수 내용 ①②
printf '%s\n' "$BODY" | grep -q '^required_check:[[:space:]]*[^[:space:]]' || emit PREVENTION_UNSIGNED "활성 주장 ① 부재(required_check)"
printf '%s\n' "$BODY" | grep -q '^branch_protection:[[:space:]]*enabled' || emit PREVENTION_UNSIGNED "활성 주장 ① 부재(branch_protection: enabled)"
printf '%s\n' "$BODY" | grep -q '^activated_at_head:[[:space:]]*[0-9a-f]\{40\}' || emit PREVENTION_UNSIGNED "활성 주장 ② 부재(activated_at_head)"
# ── LATE: ∀d∈D: P ⊰ d  (D = 구조 정의 — E1)
hasc() { git cat-file -e "$1:$CFG" 2>/dev/null; }
D=""
for x in $(git rev-list HEAD); do
  hasc "$x" || continue; intro=1
  for p in $(git log --format=%P -1 "$x"); do hasc "$p" && { intro=0; break; }; done
  [ "$intro" = 1 ] && D="$D $x"
done
ND=$(printf '%s\n' $D | grep -c .)
printf '|D|=%s D=%s\n' "$ND" "$(printf '%s ' $D)"
if [ "$ND" -eq 0 ]; then emit PREVENTION_ACTIVE "D=∅ — 비교 대상 없음(명시 통과) · 아티팩트+countersign+활성 주장 완비"; fi
for d in $D; do
  { git merge-base --is-ancestor "$P" "$d" && [ "$P" != "$d" ]; } || emit PREVENTION_LATE "P 가 d=$d 의 진 조상이 아님"
done
emit PREVENTION_ACTIVE "∀d∈D: P ⊰ d (|D|=$ND) · 아티팩트+countersign+활성 주장 완비"
```

```bash
#!/usr/bin/env bash
# t84e.sh — v2.15 에라타(837c35ef) 보충: T-84 ①②③④ + 부속(D=∅ · |D|=2 한쪽만 앞섬) — E3 countersign 형식 반영 실행기(u17-exec-e.sh). 픽스처 = scratchpad 독립 git repo. 본 저장소 무접촉.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
EX="$SP/u17-exec-e.sh"; FX="$SP/fx84e"; PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ # art <repo> [nosign|badsign|badsign2|twice]  — 예방 아티팩트 도입 커밋 P. countersign 은 E3 형식 `operator_countersign: "<식별> <ISO-8601 UTC>"`
  mkdir -p "$1/$(dirname $PC)"
  { printf 'required_check: tos-entry-harness (CI 필수 잡)\nbranch_protection: enabled\nactivated_at_head: %s\n' "$(git -C "$1" rev-parse HEAD)"
    case "${2:-}" in
      nosign)   ;;
      badsign)  printf 'operator_countersign: APPROVED 2026-08-19 (SIMULATED test fixture)\n' ;;          # 큰따옴표 없음·ISO-8601 UTC 아님
      badsign2) printf 'operator_countersign: "operator 2026-08-19"\n' ;;                                  # 날짜만 · 시각·Z 없음
      twice)    printf 'operator_countersign: "operator 2026-08-19T00:00:00Z"\noperator_countersign: "operator 2026-08-19T00:00:01Z"\n' ;;
      *)        printf 'operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n' ;;
    esac
  } > "$1/$PC"; git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)"; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact%s\n' "${2:-}" > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; }
run(){ git -C "$1" log --graph --oneline --all; echo "-- artifact @HEAD --"; git -C "$1" show "HEAD:$PC" 2>/dev/null | sed 's/^/  | /'; bash "$EX" "$1"; echo "u17_rc=$?"; }

sec "T-84 (1) artifact absent (d exists)"
R="$FX/a1"; mk "$R"; d0a "$R"; run "$R"
sec "T-84 (2)-i countersign absent"
R="$FX/a2i"; mk "$R"; art "$R" nosign; d0a "$R"; run "$R"
sec "T-84 (2)-ii countersign format violation (unquoted · not ISO-8601 UTC)"
R="$FX/a2ii"; mk "$R"; art "$R" badsign; d0a "$R"; run "$R"
sec "T-84 (2)-iii countersign format violation (quoted · date only, no time/Z)"
R="$FX/a2iii"; mk "$R"; art "$R" badsign2; d0a "$R"; run "$R"
sec "T-84 (2)-iv countersign key twice"
R="$FX/a2iv"; mk "$R"; art "$R" twice; d0a "$R"; run "$R"
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

실행 기록 원문 (t84e.sh stdout · 픽스처 DAG · 아티팩트 @HEAD 원문 포함):

```text
t84e_utc=2026-08-18T16:58:59Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t84e.sh

########## T-84 (1) artifact absent (d exists) ##########
* 712ea02 D0-A: introduce config/tos_completion.yaml
* 38dc026 seed
-- artifact @HEAD --
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1

########## T-84 (2)-i countersign absent ##########
* 70dca47 D0-A: introduce config/tos_completion.yaml
* 2e3a5eb P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 38dc026 seed
-- artifact @HEAD --
  | required_check: tos-entry-harness (CI 필수 잡)
  | branch_protection: enabled
  | activated_at_head: 38dc026e5ab932a6615deb12f49bbe929e90207f
P=2e3a5eb1b4967882e60ab0ee6b33e847f8192e48
prevention_control_state=PREVENTION_UNSIGNED
reason=operator_countersign 키 출현 횟수=0 (정확히 1 요구)
u17_rc=1

########## T-84 (2)-ii countersign format violation (unquoted · not ISO-8601 UTC) ##########
* 6c03f0c D0-A: introduce config/tos_completion.yaml
* fd6f10a P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 5be8101 seed
-- artifact @HEAD --
  | required_check: tos-entry-harness (CI 필수 잡)
  | branch_protection: enabled
  | activated_at_head: 5be810175ea5b49eb092d6062751ee3d90d11fbe
  | operator_countersign: APPROVED 2026-08-19 (SIMULATED test fixture)
P=fd6f10a5f5480c45e51d751ddd5a5e2517ab1ed9
prevention_control_state=PREVENTION_UNSIGNED
reason=operator_countersign 값 형식 위반: operator_countersign: APPROVED 2026-08-19 (SIMULATED test fixture)
u17_rc=1

########## T-84 (2)-iii countersign format violation (quoted · date only, no time/Z) ##########
* 137ac36 D0-A: introduce config/tos_completion.yaml
* 85f63c8 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 5be8101 seed
-- artifact @HEAD --
  | required_check: tos-entry-harness (CI 필수 잡)
  | branch_protection: enabled
  | activated_at_head: 5be810175ea5b49eb092d6062751ee3d90d11fbe
  | operator_countersign: "operator 2026-08-19"
P=85f63c852f8acaf212df8066e28dc6f286866301
prevention_control_state=PREVENTION_UNSIGNED
reason=operator_countersign 값 형식 위반: operator_countersign: "operator 2026-08-19"
u17_rc=1

########## T-84 (2)-iv countersign key twice ##########
* d2842d1 D0-A: introduce config/tos_completion.yaml
* a45f259 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 95830c4 seed
-- artifact @HEAD --
  | required_check: tos-entry-harness (CI 필수 잡)
  | branch_protection: enabled
  | activated_at_head: 95830c4cef300b1f1db692d424a8f325b1c5e039
  | operator_countersign: "operator 2026-08-19T00:00:00Z"
  | operator_countersign: "operator 2026-08-19T00:00:01Z"
P=a45f259fbab7f8dd9b8d43c3f6381b4f73d077a4
prevention_control_state=PREVENTION_UNSIGNED
reason=operator_countersign 키 출현 횟수=2 (정확히 1 요구)
u17_rc=1

########## T-84 (3) positive — P then d ##########
* 542f0e0 D0-A: introduce config/tos_completion.yaml
* 68658ea P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 95830c4 seed
-- artifact @HEAD --
  | required_check: tos-entry-harness (CI 필수 잡)
  | branch_protection: enabled
  | activated_at_head: 95830c4cef300b1f1db692d424a8f325b1c5e039
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
P=68658ea7c19f90ee16a15b0528100d93758cba77
|D|=1 D=542f0e0ed5abd96390c6dc1134974c545539b7fd 
prevention_control_state=PREVENTION_ACTIVE
reason=∀d∈D: P ⊰ d (|D|=1) · 아티팩트+countersign+활성 주장 완비
u17_rc=0

########## T-84 (4) d first, P later ##########
* 81d108f P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* a70ead9 D0-A: introduce config/tos_completion.yaml
* 606758d seed
-- artifact @HEAD --
  | required_check: tos-entry-harness (CI 필수 잡)
  | branch_protection: enabled
  | activated_at_head: a70ead90a06ff1f0f877d6b6aef8c771d6e11cc8
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
P=81d108f9b15dbf2ff6142ac46aaf887198a268a4
|D|=1 D=a70ead90a06ff1f0f877d6b6aef8c771d6e11cc8 
prevention_control_state=PREVENTION_LATE
reason=P 가 d=a70ead90a06ff1f0f877d6b6aef8c771d6e11cc8 의 진 조상이 아님
u17_rc=1

########## T-84 aux — D=∅ (artifact only) ##########
* 6a6e873 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 606758d seed
-- artifact @HEAD --
  | required_check: tos-entry-harness (CI 필수 잡)
  | branch_protection: enabled
  | activated_at_head: 606758d596eb6ad1550a8e25e082205d0a2c1232
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
P=6a6e8736b5717ae06f68b72463fbfa5a3ecc8a42
|D|=0 D= 
prevention_control_state=PREVENTION_ACTIVE
reason=D=∅ — 비교 대상 없음(명시 통과) · 아티팩트+countersign+활성 주장 완비
u17_rc=0

########## T-84 aux — |D|=2, P precedes only one d ##########
자동 병합: config/tos_completion.yaml
충돌 (추가/추가): config/tos_completion.yaml에 병합 충돌
자동 병합이 실패했습니다. 충돌을 바로잡고 결과물을 커밋하십시오.
*   c3b37c5 M2
|\  
| * 94c6e37 D0-A: introduce config/tos_completion.yaml
| * bbce635 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* |   6e3db7b M1
|\ \  
| |/  
|/|   
| * f36ba5e D0-A: introduce config/tos_completion.yaml
|/  
* 0725acc seed
-- artifact @HEAD --
  | required_check: tos-entry-harness (CI 필수 잡)
  | branch_protection: enabled
  | activated_at_head: 0725acc0a7ab16ca02bacece340bc21c6cd5bb6e
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
P=bbce6356d7087e06a4cd7f0d2948e125d41d3470
|D|=2 D=94c6e37ae83d3c32d58efe41a6f285a8142d7ddc f36ba5e0d13aabfdf10fb72c2f5aaeb7a61df11f 
prevention_control_state=PREVENTION_LATE
reason=P 가 d=f36ba5e0d13aabfdf10fb72c2f5aaeb7a61df11f 의 진 조상이 아님
u17_rc=1
(t84e.sh exit=0)
```

픽스처 DAG (조립 시점 재확인 · `git -C $SP/fx84e/<n> log --graph --oneline --all` — 실행 출력의 DAG 와 동일):

```text
== fx84e/a1
* 712ea02 D0-A: introduce config/tos_completion.yaml
* 38dc026 seed
== fx84e/a2i
* 70dca47 D0-A: introduce config/tos_completion.yaml
* 2e3a5eb P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 38dc026 seed
== fx84e/a2ii
* 6c03f0c D0-A: introduce config/tos_completion.yaml
* fd6f10a P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 5be8101 seed
== fx84e/a2iii
* 137ac36 D0-A: introduce config/tos_completion.yaml
* 85f63c8 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 5be8101 seed
== fx84e/a2iv
* d2842d1 D0-A: introduce config/tos_completion.yaml
* a45f259 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 95830c4 seed
== fx84e/a3
* 542f0e0 D0-A: introduce config/tos_completion.yaml
* 68658ea P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 95830c4 seed
== fx84e/a4
* 81d108f P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* a70ead9 D0-A: introduce config/tos_completion.yaml
* 606758d seed
== fx84e/a5
* 6a6e873 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* 606758d seed
== fx84e/a6
*   c3b37c5 M2
|\  
| * 94c6e37 D0-A: introduce config/tos_completion.yaml
| * bbce635 P: D0A-PREVENTION-CONTROL (SIMULATED test fixture)
* |   6e3db7b M1
|\ \  
| |/  
|/|   
| * f36ba5e D0-A: introduce config/tos_completion.yaml
|/  
* 0725acc seed
```

## 5. 사후 검증 원문 — 본 저장소 무영향 · 모의 커밋 unreachable · 본 저장소 NOT_STARTED/PREVENTION_ABSENT/REBINDING_REQUIRED

- 가드 명령 원문(⑫·⑲ guarded side, worktree): `cd "$WT" && bash <§12.3.4-R 하니스> && eval "$D0A_FIRST"` — ⑫ `guard_rc=0`, 도입 커밋
  `400ebf87`(parent `ee431827` = run 1 head) → `ENTRY_PROVENANCE_CLEAR`/0. **본 저장소에서는 가드 형태의 착수를 실행하지 않았다.**
- 도달성 검사는 `bash` 로 명시 실행한 스크립트(`v215e-post-verify.sh`)의 출력이다 — 대화형 셸(zsh)에서 `for c in $MOCK` 는 단어
  분할이 되지 않아 개별 대조가 공허해질 수 있음을 조립 중 실측·교정했고, 같은 이유로 **본 transcript(b453b4e5) §7 의 14건 도달성도
  bash 로 재검**해 아래에 병기한다(결과 0/14 — 본 transcript 의 결론 불변).

```text
=== 사후 검증 (2026-08-18T17:03:24Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               837c35ef [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
837c35ef docs(tos): phase0 completion contract v2.15 errata — structural D universe, ⑰ⓑ expectation, countersign format
$ git branch --list "br*" "side*" | wc -l
       0
-- 실행 전 스냅샷 대조 --
status/HEAD: 실행 전과 byte-동일
-- worktree D0A-FIRST/머지 커밋 도달성 (git rev-list --all 전수): 400ebf87 9dda9395 1db2ea93 3eef49ef 9958cc6a 029b946a 2385e3d5 578d270b e3b059b1 1d2bdc24 --
도달 가능 건수=0 (0 기대)
-- 객체 존재 (unreachable 객체 잔존 = 정상·gc 대상) --
400ebf87:exists 9dda9395:exists 1db2ea93:exists 3eef49ef:exists 9958cc6a:exists 029b946a:exists 2385e3d5:exists 578d270b:exists e3b059b1:exists 1d2bdc24:exists 
-- 본 저장소 D0-A 미착수 불변 --
ls: config/tos_completion.yaml: No such file or directory
(도입 커밋 출력 없음 = 미착수)
$ bash u15g-exec215e.sh <repo>
D(structural)= 
d0a_entry_provenance_state=NOT_STARTED
reason=|D| = 0
exec_rc=0
$ bash u17-exec-e.sh <repo>
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1
$ bash harness215e.sh (본 저장소 현행)
R-0 head=837c35ef263213901f84e4bf3095908f3c67f50d
d0a_entry_state=REBINDING_REQUIRED
reason=bound_set_digest 불일치
harness_rc=1
-- 모의 스탬프·ART·기존 transcript 무변경 --
(2999* 없음)
(출력 없음 = 무변경)
-- scratchpad 픽스처(독립 repo)·worktree 잔여 --
a1 a2i a2ii a2iii a2iv a3 a4 a5 a6 
(wt/ 비어 있음)

=== v2.15 본 실행(b453b4e5 transcript §7) 모의 커밋 도달성 재검 — bash 명시 실행 (2026-08-18T17:04:17Z) ===
도달 가능 건수=0 (0 기대) — 대상 14건 개별 대조
```

## 6. (4c-2) 자기 검증 출력 · 관측 · 소비 조건 · 불변 규율

```text
$ awk '<§1 실행기와 같은 opener/상태 술어 · run 별 head·nstate·state 출력>' U15-ENTRY-CHECK-ADDENDUM.md
run=1 head=ee43182773c157da317f31c2d2c8d209db024e3d nstate=1 state=ENTRY_OK
run=2 head=ee43182773c157da317f31c2d2c8d209db024e3d nstate=1 state=ENTRY_OK
run=3 head=43553f47afb529fd3c5ccfe3028a5a36174d17ca nstate=1 state=ENTRY_OK
run=4 head=570b9e075db531dde1b63afa6acf80e51d3ad331 nstate=1 state=ENTRY_OK
run=5 head=8755f915c999f63f940f16a2044a1393b6f37ad5 nstate=1 state=ENTRY_OK
run=6 head=837c35ef263213901f84e4bf3095908f3c67f50d nstate=1 state=REBINDING_REQUIRED
total_runs=6  (runs with nstate!=1: 0)
```

- **관측 1 — E1 닫힘 실증**: 같은 DAG(gg)에서 리터럴 `--diff-filter=A` 는 1건, 구조 정의는 2건 → 실행기가 `MULTIPLE_INTRODUCTIONS`/1.
  본 실행이 CLEAR/0 을 냈던 바로 그 구성이 red 로 전환됐고 gu/uu·⑫ 는 불변 — **구조 정의가 플래그 의존 클래스를 D 에서 닫았다**.
- **관측 2 — E3 닫힘 실증**: countersign 을 «키 정확히 1회 + 값 형식» 리터럴로 검사하므로 ②-i/ii/iii/iv 가 전부 `UNSIGNED` 로 접히고
  ③ 만 `ACTIVE`. 본 실행기(독해 `authority:`+`operator_countersign:` 각 1회)에서는 ③ 픽스처의 `APPROVED 2026-08-19 (SIMULATED …)` 값이
  통과였으나 **E3 형식에서는 ②-ii 로 red** — 형식 고정이 «구현 간 판정 불일치»를 실제로 제거함을 같은 값으로 보였다.
- **관측 3 — 신규 결함 후보 없음**(이번 재실행 범위). 정밀화 여지 1건만 기록: E3 의 «<운영자 식별>» 이 공백을 포함할 수 있는지(예:
  `"harris.lee (owner) 2026-…Z"`)는 계약이 명시하지 않는다 — 이 실행기는 허용(값 = 큰따옴표 안 «…<단일 공백><ISO>»의 마지막 공백으로
  분리). 식별에 공백을 금지하려면 계약 리터럴 한 줄이면 된다. 판정 극성에는 영향 없음.
- **소비 조건 (U-15-e (6))**: 이 파일의 실 저장소 HEAD 는 `837c35ef`(에라타 재동결). 본 저장소 현행 하니스 `REBINDING_REQUIRED` —
  6e 재결속·레인 B `approve` 후 그 시점 HEAD 의 새 transcript 가 필요하며, U-17 아티팩트(E3 형식 countersign 포함) 도입이 D0-A
  진입 선행 조건이다(`PREVENTION_ABSENT` 현행).
- **불변 규율 (U-15-e (4d))**: 이 파일도 발행 시점에 확정되며 이후 편집하지 않는다. 보정은 새 스탬프의 새 파일로 한다.
