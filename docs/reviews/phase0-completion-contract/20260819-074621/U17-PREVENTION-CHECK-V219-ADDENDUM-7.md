# U17-PREVENTION-CHECK-V219-ADDENDUM-7 — addendum-6 §4 **철회·대체** (stop-time BLOCK #5 채택: 단일 변수 뮤턴트 + ㉠ 자연 침묵 픽스처로 fail-open 재실증)

> **비규범 부속 · 계약 무변경** — 이 addendum 은 계약을 바꾸지 않는다. **§0 결속은 여전히 에라타 6차 `359f5bc5` 에 대한 것**이며(§6 이 blob 동일성으로 확인), 대체 대상은 **`U17-PREVENTION-CHECK-V219-ADDENDUM-6.md`(`301ca2cd`) 의 §4 주장**이다.
> **addendum-6 은 U-15-e (4d) 불변 규율에 따라 편집하지 않는다** — 이 파일이 그 §4 를 **철회하고 대체**한다.

## 0. 철회 고지 (stop-time Codex BLOCK #5 — 채택)

**심판 지적(요지)**: addendum-6 §4 의 뮤테이션은 **두 변수를 동시에 바꿨다** — 나쁜 `--absolute-git-dir` 결합을 선택하면서 **독립적인 ㉠(구조 재파생) 발화도 제거**했다(대조군 `u17-ctrl-absgitdir-e6.sh`/`u16-ctrl-absgitdir-e6.py`).
그 픽스처는 **자체적으로 ㉠ 불일치를 보고**하고 있었으므로(그 파일 §4 실행 기록의 `㉠ 재파생 대조 … 불일치 1건`), **«나쁜 결합만으로» green 이 난다는 것이 실증되지 않았다.**

**철회한다**:
- addendum-6 §4·§5 의 **«fail-open reproduced»** 주장 — **근거 불충분으로 철회**.
- 같은 파일의 **«[fail-open/차단] 신규 0건»·«arc closed» 결론** — 위 주장에 의존했으므로 **함께 철회**.
- (addendum-5 §5 N-1 의 «fail-closed» 오분류 철회는 addendum-6 §5 M-0 에서 이미 했고 **그 부분은 유효**하다.)

**대체 실증(이 파일 §3·§4)** — 심판이 요구한 두 조건을 «둘 다» 만족한다:
1. **단일 변수 뮤턴트**: 판정 실행기와 뮤턴트의 diff 가 **헤더 주석 1행 + 결합 base 1행**뿐이다(㉠ 발화 **유지**). §3 에 `diff` 원문.
2. **㉠ 자연 침묵 픽스처**: `.git/info/grafts` 로 **후보 우주 «밖» 커밋의 부모만** 재작성해(K-4 정직 경계가 명시한 잔여 축 — 후보 밖 grafts 는 ㉠ 미검사·`--no-replace-objects` 로도 안 꺼짐·**㉡ 이 유일 완화 항 = L-2**) **조상성 판정만 뒤집는다**. ㉠ 후보 집합과 각 원소의 `cat-file` 부모 == `%P` 를 **원문으로** 제시한다(§4 «㉠ 자연 침묵 증명»).

- **생성 시각**: 2026-08-19T04:29:06Z (UTC) · 실행 `t84v219e7_utc=2026-08-19T04:27:18Z` · `t82v219e7_utc=2026-08-19T04:28:18Z` · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트(저작자·심판 아님)
- **결속**: HEAD == `27d1aa33`(문서 커밋) · **계약 blob(HEAD) == blob(`359f5bc5`) == `b5f9b33e`**(`git diff --quiet 359f5bc5 -- <계약>` rc=0) · `359f5bc5..HEAD` 계약 커밋 **0** ·
  하니스 §12.3.4-R `sed -n '4631,4731p'` sha256 **`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`**(워킹트리·`359f5bc5` 동일 · §6).
- **실행기 결속**: 판정 `u17-verify-v219e6.sh` **`174b0c186266f3585b2a592eca8c0a6c0424e57899d9d3d8e40308fae3a920b5`** · 뮤턴트 `u17-mut-absgitdir-e7.sh` **`050b2eb8f3c3c6bcff61b04ad33e06c2098e29d846d58ad3d32c0fe9d14e3db5`** ·
  판정 `u16-full-exec-v219e6.py` **`9db1570934466f5fad7c124e21e174e848a13667674e5453d983cbd591469ea9`** · 뮤턴트 `u16-mut-absgitdir-e7.py` **`e5e1b5609668733be173098c036af3f861d1190ebc082dcf861c24f45b3f8aaa`** ·
  드라이버 `t84v219e7.sh` `26c5aad523fbe5ef894f9f1df6f9f753740b3b3a752326b5b13e4f512bd8bbe6` · `t82v219e7.sh` `f92d2065413bca4b9448b6f2cffb692cd383ecda854ffa2a96a7b46759f24143`.
- **서버 쓰기·설정 변경 0** · 픽스처는 scratchpad 하위 독립 git 저장소(`fx84k/*`·`fx82k/*`) · 저장소 **밖** cwd 에서 실행.

### 결과 요약 (stdout·rc 원문 그대로)

| 축 | 구성 | 실행기 | 방출값 | rc | 판독 |
| --- | --- | --- | --- | --- | --- |
| **U-17** | ㉠-침묵 픽스처 · **grafts 없음**(정직) | 판정기 | **`PREVENTION_LATE`**(6) | 1 | 진실: `P ⋠ d`(`merge-base` rc=1) |
| | 같은 픽스처 · **grafts 주입**(후보 밖 `W` 만) | **단일 변수 뮤턴트** | **`PREVENTION_ACTIVE`**(10) | **0** | **fail-open** — ㉡ 거짓 ABSENT · **㉠ 「남는」 전역 불일치 0건** · 조상성 grafts 따라감(rc 1→0) |
| | 같은 픽스처 · 같은 grafts | 판정기(E15) | **`PREVENTION_UNVERIFIABLE`**(1) | 1 | ㉡ 발화(루트 결합값 present) |
| **U-16** | ㉠-침묵 픽스처 · **grafts 없음**(정직) | 판정기 | **`PROVENANCE_UNVERIFIABLE`**(2) — `g6 C_R=∅` | 1 | 진실: `R ⋠ CN`(rc=1) → `C_R=∅` |
| | 같은 픽스처 · **grafts 주입**(후보 밖 `H0` 만) | **단일 변수 뮤턴트** | **`NO_ROWS_CLEAR`**(12) | **0** | **fail-open** — «모든 간선이 정확히 1행에 덮임» · **㉠ 「남는」 전역 불일치 0건** |
| | 같은 픽스처 · 같은 grafts | 판정기(E15) | **`PROVENANCE_UNVERIFIABLE`**(2) — `[PARENTS-UNTRUSTED] … info/grafts 실재` | 1 | ㉡ 발화 |

**두 축 모두 «판정기 vs 뮤턴트»의 코드 차이는 결합 base 한 줄뿐이고, ㉠ 은 두 실행에서 «동일하게» 침묵한다** — 따라서 green 을 만든 원인은 **결합 base 뿐**이다.

---

## 1. S-24 ① — 계약 무변경 선언

이 addendum 은 **계약을 바꾸지 않는다**. 따라서 절 범위 diff 기계 증명은 **addendum-6 §1 과 동일 리비전(`359f5bc5`)** 에 대한 것이며 재수행하지 않는다 — 대신 §6 이 **계약 blob 동일성**(`blob(HEAD:계약) == blob(359f5bc5:계약) == b5f9b33e` · `git diff --quiet` rc=0 · `359f5bc5..HEAD` 계약 커밋 0)과 **하니스 블록 sha256 `957bf49d…`** 를 원문으로 확인한다.
**비영향 변이**(T-84 ①~⑫ · T-82 ⑮~⑳ · U-17-c · U-16-d · E11 · E12 · E13 · [E15]-2 separate-git-dir · [E15]-3 linked worktree · 극성 감사)는 선행 증거 7건(`90a5ce7d`·`197f4fe4`·`c83e44db`·`d988bd0f`·`4f102c73`·`c8ca0e89`·`301ca2cd`) **그대로 결속**된다 — **철회 대상은 addendum-6 §4 의 «fail-open 재현» 주장과 그에 의존한 결론뿐**이다.

---

## 2. 단일 변수 뮤턴트 — 생성 규칙과 `diff` 원문

판정 실행기에서 **결합 base 한 줄만** 교체한다(㉠ 발화·㉡ 나머지·㉢·E9~E14 전부 **그대로**):

### 2-1. U-17 (`u17-verify-v219e6.sh` → `u17-mut-absgitdir-e7.sh`)

```diff
2c2
< # u17-verify (v2.19 에라타 6차 359f5bc5) — U-17 «예방 통제 활성 증거» 실행기 (계약 359f5bc5 §12.3.4 U-17)
---
> # u17-mut-absgitdir-e7 — [E15 «단일 변수» 뮤턴트] 판정 실행기에서 «결합 base 한 줄»만 --absolute-git-dir 로 바꾼 변형(㉠ 발화 «유지»). 판정용 아님.
70c70
< TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || printf '.')
---
> TOPLEVEL=$(git rev-parse --absolute-git-dir 2>/dev/null || printf '.')   # [뮤턴트] 결합 base 만 교체 (E15 가 철회한 옛 허용 분기)
```

### 2-2. U-16 (`u16-full-exec-v219e6.py` → `u16-mut-absgitdir-e7.py`)

```diff
2c2
< """U-16 «전 규칙» 손 실행기 — v2.19 에라타 6차 (계약 359f5bc5 §13.6.5
---
> """[E15 «단일 변수» 뮤턴트 — 판정용 아님] 결합 base «한 줄»만 --absolute-git-dir 로 교체(㉠ 발화 «유지»).  (계약 359f5bc5 §13.6.5
113c113
<     top = g("rev-parse", "--show-toplevel") or R
---
>     top = g("rev-parse", "--absolute-git-dir") or R   # [뮤턴트] 결합 base 만 교체 (E15 철회 분기)
```

---

## 3. 드라이버 원문

### 3-1. `t84v219e7.sh` (U-17 · sha256 `26c5aad523fbe5ef894f9f1df6f9f753740b3b3a752326b5b13e4f512bd8bbe6`)

```bash
#!/usr/bin/env bash
# t84v219e7.sh — addendum-7 (계약 무변경·에라타 6차 359f5bc5 결속) «영향 변이» 재실행 드라이버 (U-17 축):
#   [E15] **단일 변수 뮤턴트**(결합 base 한 줄만) + **㉠ 자연 침묵 픽스처**(후보 우주 «밖» 커밋만 grafts 재작성 — K-4 잔여 축) 로 fail-open 재실증.
# GET-only(seam 위주·본 저장소 live 1회) · 서버 쓰기·설정 변경 0 · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u17-verify-v219e6.sh"; MUT="$SP/u17-mut-absgitdir-e7.sh"
FX="$SP/fx84k"; SEAM="$SP/seam219e7"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md; WF=.github/workflows/tos-gate.yml
OR=kakao-harris-lee/kis_unified_sts; PINURL=https://github.com/kakao-harris-lee/kis_unified_sts.git
REPO=/Users/harris/Development/private/kis_unified_sts
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
TLAND=2026-08-10T00:00:00Z
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
initrepo(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "$PINURL"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; git -C "$1" rev-parse HEAD; }
artfile(){ mkdir -p "$1/$(dirname $PC)"; printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED%s\n' "$OR" "${2:-}" > "$1/$PC"; }
art(){ artfile "$1" "${2:-}"; git -C "$1" add -A; git -C "$1" commit -q -m "P: artifact${2:+ (variant$2)}"; git -C "$1" rev-parse HEAD; }
wfcontent(){ printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - name: verify harness identity\n        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s\n      - name: run entry harness\n        run: bash tools/tos_entry_harness.sh\n' "$LIT2"; }
wf(){ mkdir -p "$1/.github/workflows"; wfcontent > "$1/$WF"; git -C "$1" add -A; git -C "$1" commit -q -m "W: workflow"; git -C "$1" rev-parse HEAD; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "d: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ git -C "$1" log --oneline --graph --all 2>/dev/null | sed 's/^/  /'
  echo "\$ ${4:-}bash $(basename "${3:-$EX}") <fixture>"
  env ${4:-} U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "${3:-$EX}" "$1" 2>&1 | grep -avE '^U17-(A00|A0 |A1|A2|A3|A4|B1|B2|B3|B4|B5) |^  \| |^U17-H '; echo "u17_rc=${PIPESTATUS[0]}"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; printf '%s\n' "$4" > "$1/$(k "$2").body"; }
seam_ruleset(){ rm -rf "$1"; mkdir -p "$1"
  inject "$1" "apps/github-actions" 200 '{"id":15368,"slug":"github-actions"}'
  inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'
  inject "$1" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","status":"404"}'
  inject "$1" "repos/$OR/rules/branches/main" 200 '[{"type":"required_status_checks","ruleset_id":42,"parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]'
  inject "$1" "repos/$OR/rulesets" 200 '[{"id":42,"name":"protect_main","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]'
  inject "$1" "repos/$OR/rulesets/42" 200 '{"id":42,"enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}'; }
contents_json(){ python3 - "$1" "$2" <<'PY'
import json,sys,base64
t=open(sys.argv[1],'rb').read()
print(json.dumps({"name":"tos-gate.yml","path":sys.argv[2],"sha":"0"*40,"size":len(t),"type":"file","encoding":"base64","content":base64.b64encode(t).decode()+"\n"}))
PY
}
rev_seam(){ local dir="$1" d="$2" h="$3"
  inject "$dir" "repos/$OR/commits/$d/pulls" 200 "[{\"number\":9999,\"merged_at\":\"$TLAND\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$h\"}}]"
  inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"check_runs\":[{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":777001}}]}"
  inject "$dir" "repos/$OR/check-suites/777001" 200 "{\"id\":777001,\"head_sha\":\"$h\"}"
  inject "$dir" "repos/$OR/actions/runs?check_suite_id=777001" 200 "{\"workflow_runs\":[{\"id\":1,\"path\":\"$WF\",\"head_sha\":\"$h\",\"check_suite_id\":777001}]}"
  wfcontent > "$dir/wf.txt"; inject "$dir" "repos/$OR/contents/$WF?ref=$h" 200 "$(contents_json "$dir/wf.txt" "$WF")"; }
tp(){ git -C "$1" --no-replace-objects cat-file commit "$2" 2>/dev/null | awk '/^$/{exit} /^parent /{printf "%s ", $2}'; }
ap(){ env -u GIT_NO_REPLACE_OBJECTS git -C "$1" log --format=%P -1 "$2" 2>/dev/null; }
gp(){ local v; v=$(git -C "$1" rev-parse --git-path "$2"); case "$v" in /*) printf '%s' "$v";; *) printf '%s/%s' "$1" "$v";; esac; }
probe(){ printf '  ㉠ 재파생 cat-file parent = [%s]\n  ㉠ 이력 뷰 %%P            = [%s]\n  ㉡ git replace -l         = [%s]\n  [E13] --git-path info/grafts = %s → %s   |   «리터럴» .git/info/grafts = %s\n  [E13] --git-path shallow     = %s → %s   |   ㉢ is_shallow = %s\n' \
  "$(tp "$1" "$2")" "$(ap "$1" "$2")" "$(git -C "$1" replace -l | tr '\n' ' ')" \
  "$(git -C "$1" rev-parse --git-path info/grafts)" "$( [ -f "$(gp "$1" info/grafts)" ] && echo present || echo ABSENT )" \
  "$( [ -f "$1/.git/info/grafts" ] && echo present || echo ABSENT )" \
  "$(git -C "$1" rev-parse --git-path shallow)" "$( [ -f "$(gp "$1" shallow)" ] && echo "목록=[$(tr '\n' ' ' < "$(gp "$1" shallow)")]" || echo ABSENT )" "$(git -C "$1" rev-parse --is-shallow-repository)"; }

rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"; SM="$SEAM/rs"; seam_ruleset "$SM"
printf 't84v219e7_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u17-verify-v219e6.sh)=%s   (판정 실행기 — 결합 base = --show-toplevel)\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u17-mut-absgitdir-e7.sh)=%s  (**단일 변수 뮤턴트** — 결합 base 한 줄만 --absolute-git-dir · ㉠ 발화 «유지»)\n' "$(shasum -a 256 "$MUT" | cut -d" " -f1)"
printf '드라이버 cwd(= «저장소 밖») = %s\n' "$PWD"
echo "-- 단일 변수 확인: 두 실행기의 diff (헤더 주석 1행 + 결합 base 1행) --"; diff "$EX" "$MUT" | sed 's/^/  /'

########################################################################
sec "픽스처 — ㉠ «자연 침묵» + 조상성 뒤집힘 (후보 우주 «밖» 커밋 W 만 grafts 재작성)"
R="$FX/silent"; SEED=$(initrepo "$R")
WC=$(wf "$R")                     # W: 워크플로만 — 아티팩트·config 경로 «없음» ⇒ 후보 우주 밖
DC=$(d0a "$R")                    # d: config 도입 (D 후보)
git -C "$R" checkout -q --detach "$SEED"; PC2=$(art "$R")   # P: 아티팩트 도입 (P_first/P_last 후보) — seed 의 형제
git -C "$R" checkout -q --detach "$DC"; git -C "$R" merge -q --no-ff -m "M: merge artifact branch" "$PC2"; MC=$(git -C "$R" rev-parse HEAD); git -C "$R" branch -f main HEAD
echo "  seed=$SEED  W=$WC  d=$DC  P=$PC2  M=HEAD=$MC"
git -C "$R" log --oneline --graph --all | sed 's/^/  /'
echo "-- ㉠ 후보 우주 «원문» (실행기와 동일 규칙으로 드라이버가 독립 재계산) --"
cand(){ local path="$1"; for x in $(git -C "$R" rev-list --full-history HEAD -- "$path"); do git -C "$R" cat-file -e "$x:$path" 2>/dev/null && printf '%s ' "$x"; done; }
CA=$(cand "$PC"); CC=$(cand config/tos_completion.yaml)
echo "  후보(아티팩트 경로) = [$CA]"
echo "  후보(config 경로)   = [$CC]"
echo "  W=$WC 가 후보에 있는가? $(printf '%s %s' "$CA" "$CC" | grep -q "$WC" && echo 'YES(실패)' || echo 'NO ← ㉠ 대상 아님')"
echo "-- ㉠ 자연 침묵 증명: 후보 각 원소의 cat-file 부모 vs %P --"
for x in $CA $CC; do
  TP=$(git -C "$R" --no-replace-objects cat-file commit "$x" | awk '/^$/{exit} /^parent /{printf "%s ", $2}')
  AP=$(git -C "$R" log --format=%P -1 "$x")
  printf '  %s : cat-file=[%s] · %%P=[%s] → %s\n' "${x:0:12}" "${TP% }" "$AP" "$( [ "$(printf '%s\n' $TP | sort | tr '\n' ' ')" = "$(printf '%s\n' $AP | sort | tr '\n' ' ')" ] && echo 일치 || echo 불일치)"
done

sec "(대조 A) grafts «없는» 정직 이력 — 판정 실행기 ⇒ PREVENTION_LATE(6) (P ⋠ d)"
rev_seam "$SM" "$DC" "$WC"
echo "  merge-base --is-ancestor P d → rc=$(git -C "$R" merge-base --is-ancestor "$PC2" "$DC"; echo $?)  (1 = 조상 아님 = 정직)"
run "$R" "file:$SM"

sec "grafts 주입 — 후보 우주 «밖» 커밋 W 의 부모만 [seed, P] 로 재작성 (조상성만 뒤집는다)"
mkdir -p "$R/.git/info"; printf '%s %s %s\n' "$WC" "$SEED" "$PC2" > "$R/.git/info/grafts"
echo "\$ cat <fixture>/.git/info/grafts"; sed 's/^/  /' "$R/.git/info/grafts"
echo "  merge-base --is-ancestor P d → rc=$(git -C "$R" merge-base --is-ancestor "$PC2" "$DC" 2>/dev/null; echo $?)  (0 = grafts 가 조상성을 «뒤집었다»)"
echo "  --no-replace-objects 하 → rc=$(git -C "$R" --no-replace-objects merge-base --is-ancestor "$PC2" "$DC" 2>/dev/null; echo $?)  (여전히 0 = grafts 는 무력화로 안 꺼진다·K-4)"
REL=$(git -C "$R" rev-parse --git-path info/grafts); TOP=$(git -C "$R" rev-parse --show-toplevel); AGD=$(git -C "$R" rev-parse --absolute-git-dir)
echo "  --git-path=$REL(상대) · [E15] $TOP/$REL → $( [ -f "$TOP/$REL" ] && echo present || echo ABSENT ) · [뮤턴트] $AGD/$REL → $( [ -f "$AGD/$REL" ] && echo present || echo 'ABSENT ← 거짓 ABSENT' )"

sec "(a) **단일 변수 뮤턴트**(결합 base 만 --absolute-git-dir) ⇒ ㉡ 미발화 · ㉠ 침묵 · 조상성 grafts 따라감 ⇒ green = fail-open"
run "$R" "file:$SM" "$MUT"
sec "(b) **판정 실행기**(결합 base = --show-toplevel) ⇒ ㉡ 발화 ⇒ 차단"
run "$R" "file:$SM"
```

### 3-2. `t82v219e7.sh` (U-16 · sha256 `f92d2065413bca4b9448b6f2cffb692cd383ecda854ffa2a96a7b46759f24143`)

```bash
#!/usr/bin/env bash
# t82v219e7.sh — addendum-7 (계약 무변경·에라타 6차 359f5bc5 결속) «영향 변이» 재실행 드라이버 (U-16 축):
#   [E15] **단일 변수 뮤턴트**(결합 base 한 줄만) + **㉠ 자연 침묵 픽스처**(후보 우주 «밖» 커밋 H0 만 grafts 재작성) 로 fail-open 재실증.
# 서버 조회 0(순수 in-repo) · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u16-full-exec-v219e6.py"; MUT="$SP/u16-mut-absgitdir-e7.py"

FX="$SP/fx82k"; REF=reviews/review.md; RAT=rationale/r1.md
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
dig(){ python3 -c "import hashlib,sys; r=dict(id=sys.argv[1],closable=sys.argv[2],owner_track=sys.argv[3]); print(hashlib.sha256(b'\0'.join(f'{k}={r[k]}'.encode() for k in sorted(r))).hexdigest())" "$@"; }
DNO=$(dig r1 NO tos)
reg(){ printf 'id,closable,owner_track\n'; for kv in "$@"; do printf '%s\n' "$kv"; done; }
c(){ git -C "$1" add -A && git -C "$1" commit -q --allow-empty -m "$2" && git -C "$1" rev-parse HEAD; }
row(){ printf 'r1 | %s | %s | %s | %s | %s\n' "$1" "$DNO" "$2" "$REF" "${3:-$RAT}"; }
setNO(){ reg 'other,YES,x' 'r1,NO,tos' > "$1/register.csv"; }
run(){ git -C "$1" log --graph --oneline --all 2>/dev/null | sed 's/^/  /'; echo "\$ ${3:-}python3 $(basename "${2:-$EX}") <fixture>"; env ${3:-} python3 "${2:-$EX}" "$1"; echo "u16_rc=$?"; }
mergeled(){ git -C "$1" merge -q --no-ff -m "$3" "$2" 2>/dev/null || { { echo "## ledger"; git -C "$1" show HEAD:LEDGER.md | tail -n +2; git -C "$1" show "$2":LEDGER.md | tail -n +2; } | awk '!seen[$0]++' > "$1/LEDGER.md"; git -C "$1" add -A; git -C "$1" commit -q -m "$3"; }; }
tp(){ git -C "$1" --no-replace-objects cat-file commit "$2" 2>/dev/null | awk '/^$/{exit} /^parent /{printf "%s ", $2}'; }
ap(){ git -C "$1" log --format=%P -1 "$2" 2>/dev/null; }
gp(){ local v; v=$(git -C "$1" rev-parse --git-path "$2"); case "$v" in /*) printf '%s' "$v";; *) printf '%s/%s' "$1" "$v";; esac; }
probe(){ printf '  ㉠ 재파생=[%s] · ㉠ 이력 뷰 %%P=[%s] · ㉡ replace -l=[%s]\n  [E13] --git-path info/grafts=%s → %s | «리터럴» .git/info/grafts=%s · --git-path shallow=%s → %s · ㉢ is_shallow=%s\n' \
  "$(tp "$1" "$2")" "$(ap "$1" "$2")" "$(git -C "$1" replace -l | tr '\n' ' ')" \
  "$(git -C "$1" rev-parse --git-path info/grafts)" "$( [ -f "$(gp "$1" info/grafts)" ] && echo present || echo ABSENT )" \
  "$( [ -f "$1/.git/info/grafts" ] && echo present || echo ABSENT )" \
  "$(git -C "$1" rev-parse --git-path shallow)" "$( [ -f "$(gp "$1" shallow)" ] && echo "목록=[$(tr '\n' ' ' < "$(gp "$1" shallow)")]" || echo ABSENT )" \
  "$(git -C "$1" rev-parse --is-shallow-repository)"; }

# ⑳ⓐ 픽스처 빌더 (동일 승인 행 형제 독립 도입 · 진실 = APPROVAL_MALFORMED(3))
build20a(){ local R="$1" GDOPT="${2:-}"; rm -rf "$R"; mkdir -p "$R"
  if [ -n "$GDOPT" ]; then rm -rf "$GDOPT"; git init -q -b main --separate-git-dir "$GDOPT" "$R" >/dev/null; else git init -q -b main "$R"; fi
  mkdir -p "$R/reviews" "$R/rationale"
  reg 'other,YES,x' 'r1,YES,tos' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"
  printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; local H0 X CN Y; H0=$(c "$R" "H0: base (r1=YES · reviewer digest)")
  git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$H0" >> "$R/LEDGER.md"; printf 'x\n' > "$R/x.md"; X=$(c "$R" "X: approval row A [side x]")
  setNO "$R"; CN=$(c "$R" "CN: NO transition (child of X)")
  git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$H0" >> "$R/LEDGER.md"; printf 'y\n' > "$R/y.md"; Y=$(c "$R" "Y: approval row A (byte-identical) [side y]")
  git -C "$R" checkout -q --detach "$CN"; mergeled "$R" "$Y" "M: merge sibling identical approval introduction"; git -C "$R" branch -f main HEAD
  printf '%s %s %s %s\n' "$H0" "$X" "$CN" "$Y"; }

rm -rf "$FX"; mkdir -p "$FX"
printf 't82v219e7_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u16-full-exec-v219e6.py)=%s   (판정 실행기 — 결합 base = --show-toplevel)\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u16-mut-absgitdir-e7.py)=%s  (**단일 변수 뮤턴트** — 결합 base 한 줄만 --absolute-git-dir · ㉠ 발화 «유지»)\n' "$(shasum -a 256 "$MUT" | cut -d" " -f1)"
printf '드라이버 cwd(= «저장소 밖») = %s\n' "$PWD"
echo "-- 단일 변수 확인: 두 실행기의 diff --"; diff "$EX" "$MUT" | sed 's/^/  /'

########################################################################
sec "픽스처 — ㉠ «자연 침묵» + 조상성 뒤집힘 (후보 우주 «밖» 커밋 H0 만 grafts 재작성)"
R="$FX/silent"; rm -rf "$R"; git init -q -b main "$R"; mkdir -p "$R/reviews" "$R/rationale"
# S0: 레지스터·원장 헤더·rationale (리뷰어 경로 «없음»)
reg 'other,YES,x' 'r1,YES,tos' > "$R/register.csv"; echo "## ledger" > "$R/LEDGER.md"; echo "rationale for r1 NO" > "$R/$RAT"; S0=$(c "$R" "S0: register/ledger-header/rationale (reviewer 경로 없음)")
# H0: 무관 파일만 — 리뷰어 blob «없음»·원장 행 «없음» ⇒ c_APP/C_R 후보 우주 «밖»
git -C "$R" checkout -q --detach "$S0"; printf 'unrelated\n' > "$R/note.md"; H0=$(c "$R" "H0: unrelated only (reviewer 없음·row 없음) ⇒ 후보 우주 밖")
# R: 리뷰어 아티팩트(digest) — S0 의 «형제»
git -C "$R" checkout -q --detach "$S0"; printf 'independent review of r1 -> NO\n%s\n' "$DNO" > "$R/$REF"; RR=$(c "$R" "R: reviewer artifact (digest)")
# A: 승인 행 (aah=R) — H0 의 자손
git -C "$R" checkout -q --detach "$H0"; row YES-\>NO "$RR" >> "$R/LEDGER.md"; A=$(c "$R" "A: approval row (aah=R)")
setNO "$R"; CN=$(c "$R" "CN: NO transition")
git -C "$R" merge -q --no-ff -m "M: merge reviewer branch" "$RR" 2>/dev/null || { git -C "$R" add -A; git -C "$R" commit -q -m "M: merge reviewer branch"; }
M=$(git -C "$R" rev-parse HEAD); git -C "$R" branch -f main HEAD
echo "  S0=$S0  H0=$H0  R=$RR  A=$A  CN=$CN  M=HEAD=$M"
git -C "$R" log --oneline --graph --all | sed 's/^/  /'
echo "-- ㉠ 후보 우주 «원문» (드라이버가 실행기와 동일 규칙으로 독립 재계산) --"
ROW=$(git -C "$R" show HEAD:LEDGER.md | grep '^r1 ' | head -1)
TGT=$(git -C "$R" rev-parse "$RR:$REF")
CAPP=""; for x in $(git -C "$R" rev-list HEAD); do git -C "$R" show "$x:LEDGER.md" 2>/dev/null | grep -qxF "$ROW" && CAPP="$CAPP $x"; done
CR=""; for x in $(git -C "$R" rev-list "$CN"); do [ "$(git -C "$R" rev-parse -q --verify "$x:$REF" 2>/dev/null)" = "$TGT" ] && CR="$CR $x"; done
echo "  c_APP ㉠-검사 후보(원장 행 보유) = [$CAPP]"
echo "  C_R   ㉠-검사 후보(리뷰어 blob 일치) = [$CR]"
echo "  H0=$H0 가 후보에 있는가? $(printf '%s %s' "$CAPP" "$CR" | grep -q "$H0" && echo 'YES(실패)' || echo 'NO ← ㉠ 대상 아님')"
echo "-- ㉠ 자연 침묵 증명: 후보 각 원소의 cat-file 부모 vs %P --"
for x in $(printf '%s\n' $CAPP $CR | sort -u); do
  TP=$(git -C "$R" --no-replace-objects cat-file commit "$x" | awk '/^$/{exit} /^parent /{printf "%s ", $2}')
  AP=$(git -C "$R" log --format=%P -1 "$x")
  printf '  %s : cat-file=[%s] · %%P=[%s] → %s\n' "${x:0:12}" "${TP% }" "$AP" "$( [ "$(printf '%s\n' $TP | sort | tr '\n' ' ')" = "$(printf '%s\n' $AP | sort | tr '\n' ' ')" ] && echo 일치 || echo 불일치)"
done

sec "(대조 A) grafts «없는» 정직 이력 ⇒ APPROVAL_HEAD_INVALID(8) (aah=R 이 간선 커밋의 조상 아님)"
echo "  merge-base --is-ancestor R CN → rc=$(git -C "$R" merge-base --is-ancestor "$RR" "$CN"; echo $?)  (1 = 조상 아님 = 정직)"
run "$R"

sec "grafts 주입 — 후보 우주 «밖» 커밋 H0 의 부모만 [S0, R] 로 재작성 (조상성만 뒤집는다)"
mkdir -p "$R/.git/info"; printf '%s %s %s\n' "$H0" "$S0" "$RR" > "$R/.git/info/grafts"
echo "\$ cat <fixture>/.git/info/grafts"; sed 's/^/  /' "$R/.git/info/grafts"
echo "  merge-base --is-ancestor R CN → rc=$(git -C "$R" merge-base --is-ancestor "$RR" "$CN" 2>/dev/null; echo $?)  (0 = 뒤집힘)"
echo "  --no-replace-objects 하 → rc=$(git -C "$R" --no-replace-objects merge-base --is-ancestor "$RR" "$CN" 2>/dev/null; echo $?)  (여전히 0 = K-4)"
REL=$(git -C "$R" rev-parse --git-path info/grafts); TOP=$(git -C "$R" rev-parse --show-toplevel); AGD=$(git -C "$R" rev-parse --absolute-git-dir)
echo "  [E15] $TOP/$REL → $( [ -f "$TOP/$REL" ] && echo present || echo ABSENT ) · [뮤턴트] $AGD/$REL → $( [ -f "$AGD/$REL" ] && echo present || echo 'ABSENT ← 거짓 ABSENT' )"

sec "(a) **단일 변수 뮤턴트** ⇒ ㉡ 미발화 · ㉠ 침묵 · 조상성 grafts 따라감 ⇒ green = fail-open"
run "$R" "$MUT"
sec "(b) **판정 실행기** ⇒ ㉡ 발화 ⇒ 차단"
run "$R"
```

---

## 4. 실행 기록 (stdout 전문 · rc 포함)

**픽스처 설계 근거(㉠ 자연 침묵)**: ㉠ 은 «후보 우주»의 커밋만 대조한다 — U-17 은 아티팩트·config **경로를 «보유»한** 커밋(실행기가 `git cat-file -e x:path` 로 먼저 거른다), U-16 은 **원장 행을 보유**하거나 **리뷰어 blob 이 일치**하는 커밋이다.
그래서 **그 경로/내용을 갖지 않는 커밋**(U-17: 워크플로만 있는 `W` · U-16: 리뷰어 파일도 원장 행도 없는 `H0`)은 **㉠ 대상이 아니다**. 그 커밋의 부모만 `.git/info/grafts` 로 재작성하면 **㉠ 은 침묵한 채 조상성 판정만 뒤집힌다** — 이것이 계약 **K-4 정직 경계**(«후보 밖 grafts 는 ㉠ 미검사이고 `--no-replace-objects` 로도 안 꺼진다 → 잔여 실재»)가 명시한 축이고, **㉡ 이 그 유일 완화 항**(L-2)이다.

### 4-1. U-17 축 — `bash t84v219e7.sh`

```text
t84v219e7_utc=2026-08-19T04:27:18Z
sha256(u17-verify-v219e6.sh)=174b0c186266f3585b2a592eca8c0a6c0424e57899d9d3d8e40308fae3a920b5   (판정 실행기 — 결합 base = --show-toplevel)
sha256(u17-mut-absgitdir-e7.sh)=050b2eb8f3c3c6bcff61b04ad33e06c2098e29d846d58ad3d32c0fe9d14e3db5  (**단일 변수 뮤턴트** — 결합 base 한 줄만 --absolute-git-dir · ㉠ 발화 «유지»)
드라이버 cwd(= «저장소 밖») = /Users/harris/Development/private/kis_unified_sts
-- 단일 변수 확인: 두 실행기의 diff (헤더 주석 1행 + 결합 base 1행) --
  2c2
  < # u17-verify (v2.19 에라타 6차 359f5bc5) — U-17 «예방 통제 활성 증거» 실행기 (계약 359f5bc5 §12.3.4 U-17)
  ---
  > # u17-mut-absgitdir-e7 — [E15 «단일 변수» 뮤턴트] 판정 실행기에서 «결합 base 한 줄»만 --absolute-git-dir 로 바꾼 변형(㉠ 발화 «유지»). 판정용 아님.
  70c70
  < TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || printf '.')
  ---
  > TOPLEVEL=$(git rev-parse --absolute-git-dir 2>/dev/null || printf '.')   # [뮤턴트] 결합 base 만 교체 (E15 가 철회한 옛 허용 분기)

########## 픽스처 — ㉠ «자연 침묵» + 조상성 뒤집힘 (후보 우주 «밖» 커밋 W 만 grafts 재작성) ##########
  seed=b0becece68220d2041e568325e47b3a98ca119c3  W=97a1860bf6eea145004f1221642b4aa01dfbe9af  d=465e8aed14031b68dc1da2006ef3fed85a0f18e3  P=a44dbd530acc1c1518776701683cd6c4b1fbab10  M=HEAD=90d40ff8bd4b8bfd45d7279c0be06a91e31ce440
  *   90d40ff M: merge artifact branch
  |\  
  | * a44dbd5 P: artifact
  * | 465e8ae d: introduce config/tos_completion.yaml
  * | 97a1860 W: workflow
  |/  
  * b0becec seed
-- ㉠ 후보 우주 «원문» (실행기와 동일 규칙으로 드라이버가 독립 재계산) --
  후보(아티팩트 경로) = [90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 a44dbd530acc1c1518776701683cd6c4b1fbab10 ]
  후보(config 경로)   = [90d40ff8bd4b8bfd45d7279c0be06a91e31ce440 465e8aed14031b68dc1da2006ef3fed85a0f18e3 ]
  W=97a1860bf6eea145004f1221642b4aa01dfbe9af 가 후보에 있는가? NO ← ㉠ 대상 아님
-- ㉠ 자연 침묵 증명: 후보 각 원소의 cat-file 부모 vs %P --
  90d40ff8bd4b : cat-file=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10] · %P=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10] → 일치
  a44dbd530acc : cat-file=[b0becece68220d2041e568325e47b3a98ca119c3] · %P=[b0becece68220d2041e568325e47b3a98ca119c3] → 일치
  90d40ff8bd4b : cat-file=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10] · %P=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 a44dbd530acc1c1518776701683cd6c4b1fbab10] → 일치
  465e8aed1403 : cat-file=[97a1860bf6eea145004f1221642b4aa01dfbe9af] · %P=[97a1860bf6eea145004f1221642b4aa01dfbe9af] → 일치

########## (대조 A) grafts «없는» 정직 이력 — 판정 실행기 ⇒ PREVENTION_LATE(6) (P ⋠ d) ##########
  merge-base --is-ancestor P d → rc=1  (1 = 조상 아님 = 정직)
  *   90d40ff M: merge artifact branch
  |\  
  | * a44dbd5 P: artifact
  * | 465e8ae d: introduce config/tos_completion.yaml
  * | 97a1860 W: workflow
  |/  
  * b0becec seed
$ bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.45FpBzoBN7
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:27:19Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] |D|=1 D=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_LATE: [E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다
U17-B5x 보조(선택·판정 미소비): 로컬 git show 97a1860bf6eea145004f1221642b4aa01dfbe9af:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=465e8aed14031b68dc1da2006ef3fed85a0f18e3 head=97a1860bf6eea145004f1221642b4aa01dfbe9af merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_LATE
reason=[E9] ∃d∈D: ∀x∈P_first(|1|) x ⋠ d — 그 착지 시점에 경로가 없었다 [수집 1건 중 전순서 최소]
u17_rc=1

########## grafts 주입 — 후보 우주 «밖» 커밋 W 의 부모만 [seed, P] 로 재작성 (조상성만 뒤집는다) ##########
$ cat <fixture>/.git/info/grafts
  97a1860bf6eea145004f1221642b4aa01dfbe9af b0becece68220d2041e568325e47b3a98ca119c3 a44dbd530acc1c1518776701683cd6c4b1fbab10
  merge-base --is-ancestor P d → rc=0  (0 = grafts 가 조상성을 «뒤집었다»)
  --no-replace-objects 하 → rc=0  (여전히 0 = grafts 는 무력화로 안 꺼진다·K-4)
  --git-path=.git/info/grafts(상대) · [E15] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/info/grafts → present · [뮤턴트] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/.git/info/grafts → ABSENT ← 거짓 ABSENT

########## (a) **단일 변수 뮤턴트**(결합 base 만 --absolute-git-dir) ⇒ ㉡ 미발화 · ㉠ 침묵 · 조상성 grafts 따라감 ⇒ green = fail-open ##########
  *   90d40ff M: merge artifact branch
  |\  
  * | 465e8ae d: introduce config/tos_completion.yaml
  * | 97a1860 W: workflow
  |\| 
  | * a44dbd5 P: artifact
  |/  
  * b0becec seed
$ bash u17-mut-absgitdir-e7.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2USmaxXzFW
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:27:22Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
P_first(집합·|1|)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] |D|=1 D=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 97a1860bf6eea145004f1221642b4aa01dfbe9af:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=465e8aed14031b68dc1da2006ef3fed85a0f18e3 head=97a1860bf6eea145004f1221642b4aa01dfbe9af merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs
u17_rc=0

########## (b) **판정 실행기**(결합 base = --show-toplevel) ⇒ ㉡ 발화 ⇒ 차단 ##########
  *   90d40ff M: merge artifact branch
  |\  
  * | 465e8ae d: introduce config/tos_completion.yaml
  * | 97a1860 W: workflow
  |\| 
  | * a44dbd5 P: artifact
  |/  
  * b0becec seed
$ bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219e7/rs capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.0nwCSjrmEC
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/info/grafts(--git-path 파생)=yes · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-fire PREVENTION_UNVERIFIABLE: [PARENTS-UNTRUSTED] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T04:27:25Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
힌트: <GIT_DIR>/info/grafts에 대한 지원은 다음 깃
힌트: 버전에서 제거될 예정입니다.
힌트: 
힌트: 그래프트를 레퍼런스로 전환하려면
힌트: "git replace --convert-graft-file" 명령을
힌트: 사용하십시오.
힌트: 
힌트: 이 메시지를 보지 않으려면
힌트: "git config advice.graftFileDeprecated false"
힌트: 명령을 사용하십시오
P_first(집합·|1|)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] P_last(집합·|1|·blob=762145cfb2a9a719deb125bef8ecea955d7e656e)=[a44dbd530acc1c1518776701683cd6c4b1fbab10 ] |D|=1 D=[465e8aed14031b68dc1da2006ef3fed85a0f18e3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B5x 보조(선택·판정 미소비): 로컬 git show 97a1860bf6eea145004f1221642b4aa01dfbe9af:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=465e8aed14031b68dc1da2006ef3fed85a0f18e3 head=97a1860bf6eea145004f1221642b4aa01dfbe9af merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[PARENTS-UNTRUSTED] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84k/silent/.git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) [수집 1건 중 전순서 최소]
u17_rc=1
```

### 4-2. U-16 축 — `bash t82v219e7.sh`

```text
t82v219e7_utc=2026-08-19T04:28:18Z
sha256(u16-full-exec-v219e6.py)=9db1570934466f5fad7c124e21e174e848a13667674e5453d983cbd591469ea9   (판정 실행기 — 결합 base = --show-toplevel)
sha256(u16-mut-absgitdir-e7.py)=e5e1b5609668733be173098c036af3f861d1190ebc082dcf861c24f45b3f8aaa  (**단일 변수 뮤턴트** — 결합 base 한 줄만 --absolute-git-dir · ㉠ 발화 «유지»)
드라이버 cwd(= «저장소 밖») = /Users/harris/Development/private/kis_unified_sts
-- 단일 변수 확인: 두 실행기의 diff --
  2c2
  < """U-16 «전 규칙» 손 실행기 — v2.19 에라타 6차 (계약 359f5bc5 §13.6.5
  ---
  > """[E15 «단일 변수» 뮤턴트 — 판정용 아님] 결합 base «한 줄»만 --absolute-git-dir 로 교체(㉠ 발화 «유지»).  (계약 359f5bc5 §13.6.5
  113c113
  <     top = g("rev-parse", "--show-toplevel") or R
  ---
  >     top = g("rev-parse", "--absolute-git-dir") or R   # [뮤턴트] 결합 base 만 교체 (E15 철회 분기)

########## 픽스처 — ㉠ «자연 침묵» + 조상성 뒤집힘 (후보 우주 «밖» 커밋 H0 만 grafts 재작성) ##########
  S0=c3e310d1a7376fbe4170fa810a58a687f5d6361c  H0=632c2477a95abc9d18fc6a8c94a684d4e738cd31  R=6de2472b98c2905a1d70541e6b7869541452082d  A=cc9f2dbbbcedc3659035b64b2131b8bb04261a41  CN=76f2cad92f79e4f70d5c55096a3ef15ce5c89360  M=HEAD=f05cb2b0c9db0a7d7b5e7b6884b9eae781075452
  *   f05cb2b M: merge reviewer branch
  |\  
  | * 6de2472 R: reviewer artifact (digest)
  * | 76f2cad CN: NO transition
  * | cc9f2db A: approval row (aah=R)
  * | 632c247 H0: unrelated only (reviewer 없음·row 없음) ⇒ 후보 우주 밖
  |/  
  * c3e310d S0: register/ledger-header/rationale (reviewer 경로 없음)
-- ㉠ 후보 우주 «원문» (드라이버가 실행기와 동일 규칙으로 독립 재계산) --
  c_APP ㉠-검사 후보(원장 행 보유) = [ f05cb2b0c9db0a7d7b5e7b6884b9eae781075452 76f2cad92f79e4f70d5c55096a3ef15ce5c89360 cc9f2dbbbcedc3659035b64b2131b8bb04261a41]
  C_R   ㉠-검사 후보(리뷰어 blob 일치) = []
  H0=632c2477a95abc9d18fc6a8c94a684d4e738cd31 가 후보에 있는가? NO ← ㉠ 대상 아님
-- ㉠ 자연 침묵 증명: 후보 각 원소의 cat-file 부모 vs %P --
  76f2cad92f79 : cat-file=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41] · %P=[cc9f2dbbbcedc3659035b64b2131b8bb04261a41] → 일치
  cc9f2dbbbced : cat-file=[632c2477a95abc9d18fc6a8c94a684d4e738cd31] · %P=[632c2477a95abc9d18fc6a8c94a684d4e738cd31] → 일치
  f05cb2b0c9db : cat-file=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d] · %P=[76f2cad92f79e4f70d5c55096a3ef15ce5c89360 6de2472b98c2905a1d70541e6b7869541452082d] → 일치

########## (대조 A) grafts «없는» 정직 이력 ⇒ APPROVAL_HEAD_INVALID(8) (aah=R 이 간선 커밋의 조상 아님) ##########
  merge-base --is-ancestor R CN → rc=1  (1 = 조상 아님 = 정직)
  *   f05cb2b M: merge reviewer branch
  |\  
  | * 6de2472 R: reviewer artifact (digest)
  * | 76f2cad CN: NO transition
  * | cc9f2db A: approval row (aah=R)
  * | 632c247 H0: unrelated only (reviewer 없음·row 없음) ⇒ 후보 우주 밖
  |/  
  * c3e310d S0: register/ledger-header/rationale (reviewer 경로 없음)
$ python3 u16-full-exec-v219e6.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=f05cb2b is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('cc9f2db', '76f2cad', 'YES->NO'), ('6de2472', 'f05cb2b', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['cc9f2db'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 cc9f2db->76f2cad YES->NO]: PROVENANCE_UNVERIFIABLE(2) — g6 C_R=∅ (후보 1 · 대응 1) C_R={}
  · edge#2[r1 6de2472->f05cb2b YES->NO]: APPROVAL_ORDER_INVALID(11) — g6 C_R={6de2472} 에 c_APP 진 조상 증인 없음 (후보 1 · 대응 1) C_R={6de2472}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ edge#1[r1 cc9f2db->76f2cad YES->NO] — g6 C_R=∅ (후보 1 · 대응 1) C_R={} · 발화 전체=['PROVENANCE_UNVERIFIABLE', 'APPROVAL_ORDER_INVALID']
u16_rc=1

########## grafts 주입 — 후보 우주 «밖» 커밋 H0 의 부모만 [S0, R] 로 재작성 (조상성만 뒤집는다) ##########
$ cat <fixture>/.git/info/grafts
  632c2477a95abc9d18fc6a8c94a684d4e738cd31 c3e310d1a7376fbe4170fa810a58a687f5d6361c 6de2472b98c2905a1d70541e6b7869541452082d
  merge-base --is-ancestor R CN → rc=0  (0 = 뒤집힘)
  --no-replace-objects 하 → rc=0  (여전히 0 = K-4)
  [E15] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent/.git/info/grafts → present · [뮤턴트] /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent/.git/.git/info/grafts → ABSENT ← 거짓 ABSENT

########## (a) **단일 변수 뮤턴트** ⇒ ㉡ 미발화 · ㉠ 침묵 · 조상성 grafts 따라감 ⇒ green = fail-open ##########
  *   f05cb2b M: merge reviewer branch
  |\  
  * | 76f2cad CN: NO transition
  * | cc9f2db A: approval row (aah=R)
  * | 632c247 H0: unrelated only (reviewer 없음·row 없음) ⇒ 후보 우주 밖
  |\| 
  | * 6de2472 R: reviewer artifact (digest)
  |/  
  * c3e310d S0: register/ledger-header/rationale (reviewer 경로 없음)
$ python3 u16-mut-absgitdir-e7.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent/.git/.git/info/grafts(--git-path 파생)=ABSENT · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent/.git/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=f05cb2b is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('cc9f2db', '76f2cad', 'YES->NO'), ('6de2472', 'f05cb2b', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['cc9f2db'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · edge#1[r1 cc9f2db->76f2cad YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
  · edge#2[r1 6de2472->f05cb2b YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=NO_ROWS_CLEAR
reason=모든 NO 행의 모든 간선이 정확히 1행에 덮임 · 구조 위반 0
u16_rc=0

########## (b) **판정 실행기** ⇒ ㉡ 발화 ⇒ 차단 ##########
  *   f05cb2b M: merge reviewer branch
  |\  
  * | 76f2cad CN: NO transition
  * | cc9f2db A: approval row (aah=R)
  * | 632c247 H0: unrelated only (reviewer 없음·row 없음) ⇒ 후보 우주 밖
  |\| 
  | * 6de2472 R: reviewer artifact (digest)
  |/  
  * c3e310d S0: register/ledger-header/rationale (reviewer 경로 없음)
$ python3 u16-full-exec-v219e6.py <fixture>
[PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent/.git/info/grafts(--git-path 파생)=present · ㉢ is_shallow=False · shallow 파생 경로=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82k/silent/.git/shallow · 무력화 = git --no-replace-objects (전 호출) · ㉠ 주 판별 = cat-file commit <x> parent 줄 재파싱
HEAD=f05cb2b is_shallow=False .git/shallow=[] EVAL_ORDER=precheck-first  ([E6] 전역 단축 아님 — 경계는 «해당 행/간선의 후보 우주»에 있을 때만 크기 0을 만든다)
NO_rows=['r1']
EDGES(r1)=[('cc9f2db', '76f2cad', 'YES->NO'), ('6de2472', 'f05cb2b', 'YES->NO')]  (edge_seq 표시용 파생=[1, 2] · 판정 미소비)
ledger_rows=[('r1', 'YES->NO', '|c_APP|=1', ['cc9f2db'])]

[사실 수집] 규칙별 측정값 (순서 적용 «전»)
  row r1/YES->NO raw#0: |c_APP|=1 g4_bad=False g2_bad=False 대응간선=2 row_id간선=2
[PARENTS-UNTRUSTED ㉢] [E12] ㉢ 먼저 — 얕은 경계 국소 귀속 0건: []
[PARENTS-UNTRUSTED ㉠] «남는» 전역 불일치 0건: []

[상태 귀속] 계약 U-16-d 순서 적용
  · global: PROVENANCE_UNVERIFIABLE(2) — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)
  · edge#1[r1 cc9f2db->76f2cad YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
  · edge#2[r1 6de2472->f05cb2b YES->NO]: COVERED by c_APP=cc9f2db C_R={6de2472}
rules_executed=U-16-a(EDGES);U-16-b(edge_seq 표시용 파생·판정 미소비);U-16-c(c_APP 구조 집합·카디널리티·진 조상);g1;g2;g3;g4;g5;h;g6(C_R blob·∃witness);U-16-a2(∀edge∃row);MALFORMED(orphan/double-cover);U-16-d(선-검사 1~4 → g-단락 5~11 · 전순서 최소)
rules_missing=∅
closable_no_provenance_state=PROVENANCE_UNVERIFIABLE
reason=전순서 최소 = PROVENANCE_UNVERIFIABLE(2) @ global — [PARENTS-UNTRUSTED] .git/info/grafts 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다) · 발화 전체=['PROVENANCE_UNVERIFIABLE']
u16_rc=1
```

---

## 5. 관측 보고 · 결함 후보 (등급)

### R-0 **[절차 정정 — 철회]** addendum-6 §4 의 뮤테이션은 **2변수**였다

- 대조군이 **결합 base**와 **㉠ 발화 제거**를 동시에 바꿨고, 그 픽스처는 자체적으로 ㉠ 불일치를 보고하고 있었다 ⇒ «나쁜 결합만으로 green» 이 실증되지 않았다. **심판 지적이 정확하다.**
- **교훈(기록)**: 뮤테이션 대조군은 **한 번에 한 변수**여야 하고, 그 변수 «외의» 방어가 그 픽스처에서 **자연히 침묵**함을 **원문으로** 보여야 한다. 이 파일이 그 두 조건을 충족한다(§2 diff 2행 · §4 ㉠ 후보 집합·`cat-file` vs `%P` 전수 일치).
- **이 결함 클래스는 S-15/S-23 계열**(측정 도구·실행기가 계약보다 느슨하면 그 green 은 증거가 아니다)의 **대조군 판**이다.

### R-1 **[fail-open/차단 — 실증됨]** 옛 허용 분기(`--absolute-git-dir` 결합)는 **도달 가능한** fail-open 이다

- U-17: 진실 `PREVENTION_LATE`(6) → 뮤턴트 **`PREVENTION_ACTIVE`/0** · U-16: 진실 `PROVENANCE_UNVERIFIABLE`(2) → 뮤턴트 **`NO_ROWS_CLEAR`/0**. 두 축 모두 **rc=0(green)** 이고, 같은 픽스처에서 판정기(E15)는 차단한다.
- ⇒ **E15 의 철회 조치는 실질적**이며, addendum-6 이 «실증했다»고 적은 것을 **이 파일이 실제로 실증**한다.

### R-2 **[관측]** U-16 의 «진실» 상태는 `APPROVAL_HEAD_INVALID`(8)가 아니라 `PROVENANCE_UNVERIFIABLE`(2)였다

- 설계 의도는 g3 축(8)이었으나, 정직 이력에서 `R` 이 간선 커밋 `CN` 의 조상이 아니어서 **`C_R` 후보 자체가 공집합**(`g6 C_R=∅`)이 되어 전순서 2 가 먼저 발화했다(§4-2 원문). **극성은 동일(차단)** 이고 뮤턴트 대비(2 → 12)도 그대로 성립하므로 실증에는 영향이 없다 — **설계 의도와 실측의 차이를 숨기지 않고 기록**한다.

### R-3 **[관측]** «arc closed» 는 이 파일도 주장하지 않는다

- 이 파일이 주장하는 것은 **① addendum-6 §4 철회 ② 단일 변수·㉠ 침묵 조건 하의 fail-open 재실증 ③ E15 판정기가 그 구성을 차단** 세 가지뿐이다. **신규 결함 탐색을 전수했다는 주장은 하지 않는다**(그 주장이 BLOCK #5 의 대상이었다).

---

## 6. 사후 검증 원문 (계약 무변경 · HEAD · 본 저장소 관측 · 픽스처 격리)

```text
post_utc=2026-08-19T04:29:06Z
$ git -C <repo> rev-parse HEAD
27d1aa330bbc9c2211cd1d4c7205013b5a0c5304
$ git -C <repo> status --short
 M uv.lock
?? tools/spikes/
--- 계약 «무변경» 확인 (addendum-7 은 계약을 바꾸지 않는다) ---
$ git -C <repo> diff --quiet 359f5bc5 -- <계약> → rc
rc=0
  blob(HEAD:계약) = b5f9b33e8eaa650826c561fb9e3e79254cca7e19
  blob(359f5bc5:계약) = b5f9b33e8eaa650826c561fb9e3e79254cca7e19
$ git -C <repo> rev-list --count 359f5bc5..HEAD -- <계약>
0
$ sed -n '4631,4731p' <워킹트리> | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git show 359f5bc5:<계약> | sed -n '4631,4731p' | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> reflog -n 3
27d1aa33 HEAD@{0}: commit: docs(plans): INDEX — phase0 completion contract v2.19 (errata/addendum ×6 → 359f5bc5/301ca2cd after stop-time BLOCK #4)
301ca2cd HEAD@{1}: commit: docs(tos): record v2.19 errata #6 addendum evidence (S-24 — formerly permitted --absolute-git-dir join mutation-tested · fail-open reproduced then blocked)
359f5bc5 HEAD@{2}: commit: docs(tos): phase0 completion contract v2.19 errata #6 — E15: repository-root join only (retract --absolute-git-dir join = false ABSENT = fail-open)
--- 본 저장소 [PARENTS-UNTRUSTED] 관측 (E15 루트 결합값 기준) ---
  [E15] /Users/harris/Development/private/kis_unified_sts/.git/info/grafts → ABSENT · [옛 분기] /Users/harris/Development/private/kis_unified_sts/.git/.git/info/grafts → ABSENT
  git replace -l = '' · --is-shallow-repository = false
  ㉠ 재파생 = 301ca2cd3bba664a56fe90fd715349c9c320398c · %P = 301ca2cd3bba664a56fe90fd715349c9c320398c
--- 픽스처 격리 ---
       2
```

**판독**: **계약은 무변경**(`git diff --quiet 359f5bc5` rc=0 · blob `b5f9b33e` 동일 · `359f5bc5..HEAD` 계약 커밋 0) · 하니스 블록 `sed -n '4631,4731p'` sha256 이 워킹트리·`359f5bc5` 양쪽에서 **`957bf49d…`** ·
워킹트리 변경은 실행 «전»부터 있던 `uv.lock`·`tools/spikes/` 뿐 · **본 저장소는 [E15] 루트 결합값 기준 `info/grafts` 부재 · `git replace -l` 공집합 · 얕지 않음 · ㉠ 재파생 == `%P`** ⇒ `[PARENTS-UNTRUSTED]` 통과 ·
`grafts` 조작은 **전부 scratchpad 픽스처 안에서만**(2개 저장소) · **서버 접근**: U-17 축은 SIMULATED seam 뿐이고 U-16 축은 GitHub 조회 0 ⇒ **서버 쓰기·설정 변경 0**.
