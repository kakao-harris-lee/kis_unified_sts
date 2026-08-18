# U17-PREVENTION-CHECK-V218 — v2.18 T-84 ①~⑩ 실행 기록 (u17-verify · 계약 핀 · 서버 파생 app id · 워크플로 정체성 · 아티팩트 사후 편집 · GET-only)

> **비규범 부속** — 계약 v2.18(`5f4b7cfd`)도 U-17 증거 아티팩트의 경로·파일명을 규정하지 않는다. v2.16/v2.17 sibling(`U17-PREVENTION-CHECK.md`·`-V217.md`)은
> (4d) 불변 규율을 준용해 편집하지 않고 새 파일을 둔다. **S-24 결속: 이 증거는 «최종 동결 `5f4b7cfd`» 에 결속된다** — 실행 시점 HEAD == `5f4b7cfd`, 계약 워킹트리 blob
> `e225bc1a` == `git show 5f4b7cfd:` blob(`git diff --quiet 5f4b7cfd -- <계약>` 무차이 · sha256 `e66e9f85e42ca2721133a012460243536043b27436bee74bb408ddcd83936f97`),
> `5f4b7cfd..HEAD` 에 계약 문서 커밋 0(에라타 없음), 하니스 §12.3.4-R 블록 `git show 5f4b7cfd:<계약> | sed -n '4528,4628p'` sha256
> **`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`**(v2.10~v2.17 과 byte-동일 · §5 원문). **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로
> live 조회한다** — 대조용. **서버 쓰기·설정 변경 0**(GET `gh api -i` 만 · 사후 재조회 §5). 픽스처는 scratchpad 독립 git repo(원격 URL 은 로컬 config 만 · push/fetch 0).
- **생성 시각**: 2026-08-18T19:04:53Z (UTC) · 실행 `t84v218_utc=` + 각 캡처 `utc=` · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트
- **실행기 결속**: sha256(u17-verify-v218.sh) = `cfbab4ae95159aba0e0b070749189053bc22538d6d5308cd72aade7ab3e2291f` · sha256(t84v218.sh) =
  `5f04e1c68a67a17ac6104b91c3b98b878ff73eeba6f720a1ad1796de6377ea1e` (원문 §1·§2). 계약 리터럴(실행기 상수): 핀 `github.com/kakao-harris-lee/kis_unified_sts` ·
  워크플로 경로 `.github/workflows/tos-gate.yml` · 하니스 경로 `tools/tos_entry_harness.sh` · 하니스 sha256 `957bf49d…`. 서버 파생 실측(§3 (0)): `apps/github-actions.id` = **15368** ·
  `repos/{pin}.default_branch` = `main` · 본 저장소 `git remote -v` = `origin https://github.com/kakao-harris-lee/kis_unified_sts.git`(핀 일치).
- **U-15 3단 가드**(⑫·G-음성-2)는 v2.18 이 U-15 를 바꾸지 않아 재실행하지 않았다 — sibling `U15-ENTRY-CHECK-V216.md` 유효.
- **결과 요약 — 실행기 stdout·rc 원문 그대로 (해석 아님)** · 실행기는 전 단계를 수집한 뒤 전순서 최소를 방출한다(`U17-fire` 라인 = 수집 원문 · `[수집 N건 중 전순서 최소]` 사유 병기):

| 변이 | 구성 (원격 · 아티팩트 선언 · responder) | 방출값 (`prevention_control_state=`) | rc | 기대 (§8 T-84 10종 · U-17-c 9단) | 대조 |
| --- | --- | --- | --- | --- | --- |
| **① live** | 원격=핀 · 선언 `kakao-harris-lee/kis_unified_sts`@`main` · **`gh`** | **`PREVENTION_INSUFFICIENT`** — `classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]` (현재 required check `test` app_id 15368) | 1 | ① | **일치 (인증 실측)** |
| **⑤-a live** | 선언 target=`mission-critical-trading-operating-system`(비-default) · D=∅ | **`PREVENTION_TARGET_MISMATCH`**(4) — 수집: MISMATCH·INSUFFICIENT(5) | 1 | ⑤ D=∅ 에서도 red | **일치** |
| **⑤-b live** | 선언 owner_repo=`octocat/Hello-World` · D=∅ | **`PREVENTION_TARGET_MISMATCH`** | 1 | ⑤ | **일치** |
| **⑩-a live** | 원격 `https://gitlab.com/kakao-harris-lee/kis_unified_sts.git`(타 host 동일 경로) · 선언은 핀과 일치 | **`PREVENTION_TARGET_MISMATCH`** — `핀과 일치하는 원격 부재 (origin=gitlab.com/kakao-harris-lee/kis_unified_sts)` | 1 | ⑩ «host 를 버리는 정규화는 통과시킨다» | **일치** — 대조 (10)-d: v2.17 host-drop 정규화면 `kakao-harris-lee/kis_unified_sts`==핀 owner/repo → **통과였을 것** |
| **⑩-b live** | 원격 `git@github.com:octocat/kis_unified_sts.git`(타 owner) | **`PREVENTION_TARGET_MISMATCH`** | 1 | ⑩ | **일치** |
| ⑩-c live | 원격 2개(`upstream`=gitlab 동일 경로 · `fork`=핀 ssh 형) | `PREVENTION_INSUFFICIENT` (핀 일치 원격 «존재» → 대조 통과 · 이름 무관) | 1 | 핀 대조는 ∃ | **일치** |
| ② -i seam ACTIVE | checks[tos-gate].app_id=15368 · 선언=핀 · `file:seam218/active` SIMULATED | `PREVENTION_ACTIVE` (D=∅) | 0 | ② — 양성은 운영자 설정 전 실측 불가 | **일치 (모의)** |
| ② -ii/-iii/-iv seam | INSUFFICIENT 형태 / protection 500 / 응답 없음 | `INSUFFICIENT` / `UNVERIFIABLE` / `UNVERIFIABLE`(apps·repos 부터 실패 → `@UNRESOLVED`) | 1/1/1 | ② | **일치** |
| **⑦ seam** | contexts ∋ tos-gate 이나 `checks[tos-gate].app_id=99999` · D=∅ | **`PREVENTION_INSUFFICIENT`** — `checks[tos-gate].app_id=[99999]≠Actions 15368` | 1 | ⑦ (a) 무조건 · D=∅ 에서도 | **일치** — 대조: v2.17 name-only 술어면 `prot_ok=True` |
| **③-0 live 병기** | 미푸시 HEAD `5f4b7cfd` → 422 · 푸시 무-PR `be98f075` → `[]` · PR#636 head `7656259d`: 5 run 전부 app.id 15368·suite `83489483104` · **`actions/runs?check_suite_id=` → 1 run `path='.github/workflows/test.yml'`** · 로컬 `git show 7656259d:.github/workflows/tos-gate.yml` 실패(커밋 미보유) | (원자료) | — | ③ «UNVERIFIED_REVISION» 의 원자료 — tos-gate 이름·정본 path·로컬 blob 어느 축으로도 red | **일치** |
| ③-a mixed | (a) seam ACTIVE · (b) live 422 | `PREVENTION_UNVERIFIABLE`(1 · 수집 후 방출) | 1 | ③ | **일치** |
| ③-b seam (b) 양성 | 픽스처 `seed→P→W(tos-gate.yml, 두 리터럴)→d` · seam: pulls(merged·base main·head=W) · check-run {tos-gate·success·app 15368·head_sha W·suite 777001} · check-suites/777001{head_sha W} · actions/runs?check_suite_id=777001 {path tos-gate.yml, head W} · 로컬 `git show W:tos-gate.yml` grep 2 리터럴 | `PREVENTION_ACTIVE` — `name/conclusion/app.id/head_sha/suite/workflow(path·head)/blob(2 리터럴) 전부 일치` | 0 | (b) 충족 (모의) | **일치 (모의)** |
| **⑥ seam** | check-run app.id=99999 | `PREVENTION_UNVERIFIED_REVISION` | 1 | ⑥ | **일치** |
| **⑧ seam** | app.id 15368 이나 workflow run `path=.github/workflows/test.yml` | **`PREVENTION_UNVERIFIED_REVISION`** — `workflow run path≠.github/workflows/tos-gate.yml` | 1 | ⑧ | **일치** — 대조: v2.17 app-id-only 는 **PASS** |
| ③-c / R2-a / R2-b seam | tos-gate run 부재 / 서버 3중 충족이나 로컬 `<head>:tos-gate.yml` 부재 / 파일은 있으나 두 리터럴 부재(grep 0·0) | `PREVENTION_UNVERIFIED_REVISION` ×3 | 1 | R2 «검사 생략 금지» | **일치** |
| **⑨-a** git 구조 live · 서버 seam | `P_first→W→d→P_edit`(아티팩트 편집) | **`PREVENTION_ARTIFACT_MUTATED`** — `∀d P_first⊰d 이나 P_last=… ⋠ d` | 1 | ⑨ | **일치** |
| **⑨-b** | 편집 후 원복(blob == P_first blob) → P_last=원복 커밋 | **`PREVENTION_ARTIFACT_MUTATED`** | 1 | ⑨ (P_last 는 «마지막 변경») | **일치** — 대조 (9)-c: P_first⊰d 만 보는 v2.17 은 ACTIVE(사후 편집 허용) |
| ⑨-d | `W→d→P`(P_first ⋠ d) | `PREVENTION_LATE`(6 < 7) | 1 | LATE/MUTATED 분리 | **일치** |
| ④ 시퀀스 | t0 seam ACTIVE → t1 404 → t2 약화 → t3 live gh | `ACTIVE`/0 → `ABSENT`/1 → `INSUFFICIENT`/1 → `INSUFFICIENT`/1 | | ④ | **일치** |
| 부속 UNSIGNED / 본 저장소 | countersign 형식 위반 / HEAD `5f4b7cfd` 아티팩트 부재 | `PREVENTION_UNSIGNED` / `PREVENTION_ABSENT`(수집: ABSENT(2)·live INSUFFICIENT(5) → 2) | 1/1 | (c-0) / «현재 평가» | **일치** |

이 파일은 본 저장소의 `PREVENTION_ACTIVE` 를 주장하지 않는다 — live 관측값은 `INSUFFICIENT`·`TARGET_MISMATCH` 뿐이고 `ACTIVE` 는 전부 `SIMULATED` seam 이다.

---

## 1. u17-verify (v2.18) 실행기 — 원문 + 독해 선언 (sha256 `cfbab4ae95159aba0e0b070749189053bc22538d6d5308cd72aade7ab3e2291f`)

독해 선언(계약이 리터럴로 고정하지 않은 자리 · v2.17 실행기 대비 델타):
- **[C3] 핀·원격 대조**: `git remote -v` 의 모든 URL 을 host 보존 정규화(`https://<h>/<o>/<r>(.git)`·`ssh://git@<h>/<o>/<r>`·`git@<h>:<o>/<r>` → `<h>/<o>/<r>`)해 핀과 **일치하는 원격이
  존재**해야 한다(이름 무관·`remote_name` 키는 있어도 무시·기록). (a) 조회 대상 = **핀 repo**(원격과 무관) · target = 핀 repo `.default_branch`. 아티팩트 선언 `owner_repo`(핀 또는
  `<o>/<r>` 형 허용)·`target_branch` 는 **대조** — 불일치 = `TARGET_MISMATCH`.
- **[C2] Actions app id** = `apps/github-actions` `.id`(A00 캡처 · responder 경유). `gate_app_id` 키는 폐지(있어도 무시·`U17-note`). **(a) [C1]**: `checks[]` 의 `<check>` 컨텍스트 `app_id ==`
  Actions id(항목 부재 = 불충족) · 룰셋: `required_status_checks[].integration_id == ` Actions id.
- **(b) 워크플로 정체성**: 후보 run(name·success·app.id·head_sha) → `check-suites/{id}.head_sha == PR head` → `actions/runs?check_suite_id={id}` 의 workflow_runs 중 `head_sha == PR head ∧ path ==
  .github/workflows/tos-gate.yml` → **[R2]** 로컬 `git show <PR head>:.github/workflows/tos-gate.yml` 성공 ∧ 두 리터럴 `grep -F` ≥1 회. 어느 하나 실패 = `UNVERIFIED_REVISION`(부재 포함 · 검사 생략 금지).
- **(c) P_first/P_last**: 후보 `git rev-list --full-history HEAD -- <artifact>` 위 구조 평가 — P_first = 경로 존재 ∧ 모든 부모에 부재인 가장 오래된 커밋 · P_last = 어느 부모와도 blob 이 다른(또는
  부모에 부재) **가장 최근** 커밋. LATE = ∃d P_first⋠d · ARTIFACT_MUTATED = ¬LATE ∧ ∃d P_last⋠d ∨ HEAD blob ≠ blob(P_last).
- **수집 후 방출**: 각 단계는 상태를 «발화(`U17-fire`)»만 하고 끝에 전순서 최소를 방출한다 — (b) 조회 실패(1)가 (c) 의 LATE(6) 등보다 먼저 성립하도록(단계 순서 ≠ 전순서). exit 0 = ACTIVE 만.
- 나머지(E3 countersign 리터럴·(a) 술어 E3 마감 리터럴·(α) 관측·responder seam·trap)는 v2.17 실행기와 동일.

```bash
#!/usr/bin/env bash
# u17-verify (v2.18) — U-17 «예방 통제 활성 증거» 실행기 (계약 5f4b7cfd §12.3.4 U-17: C3 계약 핀·C1 checks[].app_id·C2 app id 서버 파생+워크플로 정체성 3중·R2 워크플로 blob·C4/R1 P_first/P_last·U-17-c 9값/전순서 9단)
#   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=<owner>/<repo>@<branch>` 라인이 연다. CORR 은 이 run 을 보지 않는다.
#
#   [C3] 계약 핀 canonical_target = github.com/kakao-harris-lee/kis_unified_sts (계약 리터럴 · 아티팩트 파라미터 아님).
#        git remote 는 «대조»: `git remote -v` 의 URL 을 host 보존 정규화(<host>/<owner>/<repo>)해 핀과 일치하는 원격이 «존재» 해야 한다(이름 무관). 부재 = TARGET_MISMATCH.
#        target = 핀 repo 의 `gh api repos/{pin}` .default_branch.  아티팩트 선언값(owner_repo·target_branch)은 «대조 대상» — 핀/파생과 불일치 = TARGET_MISMATCH.
#   [C2] Actions app id 는 서버 파생: `gh api apps/github-actions` .id (gate_app_id 파라미터 폐지 — 아티팩트에 있어도 무시·기록).
#   (a) 술어 = v2.17 + [C1] required_status_checks.checks[] 의 <check> 컨텍스트 app_id == Actions app id (룰셋: required_status_checks[].integration_id == app id).
#   (b) ∀d∈D: pulls → merged ∧ base==target 인 PR head.sha → check-runs 에 name==check ∧ conclusion==success ∧ app.id==Actions ∧ head_sha==PR head 인 run;
#       check-suites/{run.check_suite.id}.head_sha == PR head [E2]; 워크플로 정체성 3중 [C2]: actions/runs?check_suite_id=<id> 의 run 중 head_sha==PR head 이고 path==.github/workflows/tos-gate.yml (계약 리터럴);
#       [R2] `git show <PR head>:.github/workflows/tos-gate.yml` (로컬 저장소) 이 성공하고 두 리터럴 `tools/tos_entry_harness.sh` · `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d` 을 포함. 실패·부재 = UNVERIFIED_REVISION.
#   (c) [C4/R1] P_first(최초 도입)·P_last(마지막 변경) 구조 파생(--full-history 후보 위): LATE = ∃d P_first⋠d · ARTIFACT_MUTATED = ∀d P_first⊰d ∧ ∃d P_last⋠d · ACTIVE 는 ∀d P_last⊰d ∧ HEAD blob == blob(P_last).
#   (c-0) countersign E3 리터럴.  (α) 룰셋 created_at/updated_at 관측(차단 아님).
#   전순서: 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 TARGET_MISMATCH > 5 INSUFFICIENT > 6 LATE > 7 ARTIFACT_MUTATED > 8 UNVERIFIED_REVISION > 9 ACTIVE.
#   ** 전 단계를 먼저 «수집»하고 마지막에 전순서 최소 순위를 방출한다 ** — (b) 의 조회 실패(1)가 (c) 의 LATE(6) 보다 먼저 성립하도록. exit 0 = ACTIVE 만. trap EXIT 폐쇄.
# 사용: bash u17-verify-v218.sh [<repo-dir>]      (env: U17_RESPONDER=gh|file:<dir>|mixed:<dir> · U17_CAPTURE_DIR)
set -u -o pipefail
CANON=github.com/kakao-harris-lee/kis_unified_sts     # 계약 핀 (C3)
WF_PATH=.github/workflows/tos-gate.yml                # 계약 리터럴 (C2)
LIT1=tools/tos_entry_harness.sh                       # 계약 리터럴 (R2-i)
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
EMITTED=0
emit() { EMITTED=1; printf 'prevention_control_state=%s\nreason=%s\n' "$1" "$2"; [ "$1" = PREVENTION_ACTIVE ] && exit 0; exit 1; }
trap '[ "$EMITTED" -eq 1 ] || { printf "prevention_control_state=%s\nreason=%s\n" PREVENTION_UNVERIFIABLE "판정 미산출 상태로 종료(fail-closed)"; exit 1; }' EXIT
cd "${1:-.}" || emit PREVENTION_UNVERIFIABLE "repo 진입 실패"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
CFG=config/tos_completion.yaml
RESP="${U17_RESPONDER:-gh}"
CAP="${U17_CAPTURE_DIR:-$(mktemp -d)}"; mkdir -p "$CAP"
utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
key() { printf '%s' "$1" | tr '/?=&' '____'; }
# 상태 수집기: RANK[상태]=순위 · 발화한 상태와 사유를 모았다가 최소 순위 방출
rank() { case "$1" in PREVENTION_UNVERIFIABLE) echo 1;; PREVENTION_ABSENT) echo 2;; PREVENTION_UNSIGNED) echo 3;; PREVENTION_TARGET_MISMATCH) echo 4;; PREVENTION_INSUFFICIENT) echo 5;; PREVENTION_LATE) echo 6;; PREVENTION_ARTIFACT_MUTATED) echo 7;; PREVENTION_UNVERIFIED_REVISION) echo 8;; *) echo 99;; esac; }
FIRED=""; NF=0; fire() { NF=$((NF+1)); FIRED="$FIRED$1|$2"$'\n'; printf 'U17-fire %s: %s\n' "$1" "$2"; }
finish() { local best="" bestr=99 f s r; while IFS= read -r f; do [ -n "$f" ] || continue; s=${f%%|*}; r=$(rank "$s"); if [ "$r" -lt "$bestr" ]; then bestr=$r; best="$f"; fi; done <<< "$FIRED"
  if [ -n "$best" ]; then emit "${best%%|*}" "${best#*|} [수집 ${NF}건 중 전순서 최소]"; fi; emit PREVENTION_ACTIVE "$1"; }

# ── responder seam
respond() {
  local path="$1" k; k=$(key "$1"); local st="$CAP/$k.status" bd="$CAP/$k.body"
  case "$RESP" in
    gh)  local out; out=$(gh api -i "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
         printf '%s\n' "$out" | awk 'f{print} /^\r?$/{f=1}' | tr -d '\r' > "$bd"
         if ! grep -Eq '^[0-9]{3}$' "$st"; then printf 'ERR\n' > "$st"; cat "$CAP/$k.err" > "$bd" 2>/dev/null; return 1; fi; return 0 ;;
    file:*) local dir="${RESP#file:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected response for %s\n' "$path" > "$bd"; return 1; fi ;;
    mixed:*) local dir="${RESP#mixed:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; printf 'U17-seam %s ← file(SIMULATED)\n' "$path"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'U17-seam %s ← gh(live)\n' "$path"; local save="$RESP"; RESP=gh; respond "$path"; local r=$?; RESP="$save"; return $r; fi ;;
    *) emit PREVENTION_UNVERIFIABLE "알 수 없는 responder: $RESP" ;;
  esac
}
show_capture() { local k; k=$(key "$2"); printf 'U17-%s %s  utc=%s  http=%s\n' "$1" "$2" "$(utc)" "$(cat "$CAP/$k.status")"; sed 's/^/  | /' "$CAP/$k.body"; }
jget() { python3 -c 'import json,sys
try:
    j=json.load(open(sys.argv[1]))
    for kk in sys.argv[2].split("."):
        j=j[int(kk)] if isinstance(j,list) else j[kk]
    print(j if not isinstance(j,(dict,list)) else json.dumps(j))
except Exception: print("")' "$CAP/$(key "$1").body" "$2" 2>/dev/null; }
http_of() { cat "$CAP/$(key "$1").status" 2>/dev/null; }
ok2xx() { printf '%s' "$1" | grep -Eq '^2'; }

# ── [C3] 핀·원격 대조 (host 보존 정규화)
PIN_OR=${CANON#*/}
norm_url() { printf '%s' "$1" | sed -E 's#^https?://([^/]+)/(.+)$#\1/\2#; s#^ssh://git@([^/]+)/(.+)$#\1/\2#; s#^git@([^:]+):(.+)$#\1/\2#; s#\.git$##; s#/$##'; }
REMOTES=$(git remote -v 2>/dev/null | awk '{print $1" "$2}' | sort -u)
MATCH_REMOTE=""; NORMED=""
while read -r rn ru; do [ -n "${ru:-}" ] || continue; n=$(norm_url "$ru"); NORMED="$NORMED $rn=$n"; [ "$n" = "$CANON" ] && MATCH_REMOTE="$rn"; done <<< "$REMOTES"

# ── [C2] Actions app id 서버 파생 · [C3] target = 핀 repo default_branch  (A00·A0)
respond "apps/github-actions"; ST_APP=$(http_of "apps/github-actions"); APPID=$(jget "apps/github-actions" id)
respond "repos/$PIN_OR";       ST0=$(http_of "repos/$PIN_OR");          TARGET=$(jget "repos/$PIN_OR" default_branch)
printf 'U17-0 target=%s@%s\n' "$PIN_OR" "${TARGET:-UNRESOLVED}"
printf 'U17-0 pin=%s remotes:%s match=%s | actions_app_id=%s (apps/github-actions http=%s) | responder=%s capture_dir=%s\n' "$CANON" "${NORMED:- (none)}" "${MATCH_REMOTE:-∅}" "${APPID:-∅}" "$ST_APP" "$RESP" "$CAP"
show_capture A00 "apps/github-actions"; printf 'U17-A0 repos/%s  utc=%s  http=%s  (.default_branch=%s)\n' "$PIN_OR" "$(utc)" "$ST0" "${TARGET:-∅}"
{ ok2xx "$ST_APP" && [ -n "$APPID" ]; } || fire PREVENTION_UNVERIFIABLE "apps/github-actions 조회 실패(http=$ST_APP) — Actions app id 파생 불가"
{ ok2xx "$ST0" && [ -n "$TARGET" ]; }   || fire PREVENTION_UNVERIFIABLE "repos/$PIN_OR 조회 실패(http=$ST0) — default_branch 파생 불가"
[ -n "$MATCH_REMOTE" ] || fire PREVENTION_TARGET_MISMATCH "계약 핀 $CANON 과 일치하는 원격 부재 (git remote -v 정규화:${NORMED:- none})"

# ── 아티팩트 (전순서 2 ABSENT · 대조값·countersign)  — 커밋-전용 읽기
BODY=$(git show "HEAD:$PC" 2>/dev/null) || { fire PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"; BODY=""; }
yv() { printf '%s\n' "$BODY" | sed -n "s/^$1:[[:space:]]*//p" | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//' | head -1; }
DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch); CHECK=$(yv tos_gate_check); [ -n "$CHECK" ] || CHECK=tos-gate
[ -z "$(yv gate_app_id)" ] || printf 'U17-note 아티팩트에 gate_app_id 키가 있으나 v2.18 은 폐지(무시) — 서버 파생값 %s 사용\n' "$APPID"
[ -z "$(yv remote_name)" ]  || printf 'U17-note 아티팩트에 remote_name 키가 있으나 v2.18 은 폐지(무시) — 핀 대조는 원격 이름을 묻지 않는다\n'
if [ -n "$BODY" ]; then
  MM=""
  case "$DECL_OR" in "$CANON"|"$PIN_OR") ;; *) MM="$MM owner_repo(선언=${DECL_OR:-∅} ≠ 핀=$CANON)";; esac
  [ -n "$TARGET" ] && [ "$DECL_TB" != "$TARGET" ] && MM="$MM target_branch(선언=${DECL_TB:-∅} ≠ 핀 repo default=$TARGET)"
  printf 'U17-T declared-vs-pin: %s\n' "${MM:-일치}"
  [ -z "$MM" ] || fire PREVENTION_TARGET_MISMATCH "아티팩트 선언값이 계약 핀/파생값과 불일치:$MM"
  CS_RE='^operator_countersign:[[:space:]]*"[^"[:space:]][^"]* [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"[[:space:]]*(#.*)?$'
  nk=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:')
  if [ "$nk" != 1 ]; then fire PREVENTION_UNSIGNED "operator_countersign 키 출현 횟수=$nk (정확히 1 요구)"
  elif ! printf '%s\n' "$BODY" | grep -Eq "$CS_RE"; then fire PREVENTION_UNSIGNED "operator_countersign 값 형식 위반: $(printf '%s\n' "$BODY" | grep '^operator_countersign:')"; fi
fi

# ── (a) 4 엔드포인트 (핀 repo · 파생 target)
if [ -n "$TARGET" ]; then
P_PROT="repos/$PIN_OR/branches/$TARGET/protection"; P_RULES="repos/$PIN_OR/rules/branches/$TARGET"; P_RSETS="repos/$PIN_OR/rulesets"
respond "$P_PROT";  show_capture A1 "$P_PROT"
respond "$P_RULES"; show_capture A2 "$P_RULES"
respond "$P_RSETS"; show_capture A3 "$P_RSETS"
RSIDS=$(python3 -c 'import json,sys
ids=set()
for f in sys.argv[1:]:
    try:
        a=json.load(open(f))
        for r in a if isinstance(a,list) else []:
            if isinstance(r,dict):
                if r.get("ruleset_id") is not None: ids.add(str(r["ruleset_id"]))
                elif r.get("id") is not None and "enforcement" in r: ids.add(str(r["id"]))
    except Exception: pass
print(" ".join(sorted(ids)))' "$CAP/$(key "$P_RULES").body" "$CAP/$(key "$P_RSETS").body" 2>/dev/null)
for id in $RSIDS; do respond "repos/$PIN_OR/rulesets/$id"; show_capture A4 "repos/$PIN_OR/rulesets/$id"; printf 'U17-α ruleset %s created_at=%s updated_at=%s enforcement=%s (관측 기록)\n' "$id" "$(jget "repos/$PIN_OR/rulesets/$id" created_at)" "$(jget "repos/$PIN_OR/rulesets/$id" updated_at)" "$(jget "repos/$PIN_OR/rulesets/$id" enforcement)"; done
[ -n "$RSIDS" ] || printf 'U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)\n'
A_STATE=$(python3 - "$CAP" "$PIN_OR" "$TARGET" "$CHECK" "${APPID:-}" <<'PY'
import json,sys,os
cap,orepo,target,check,appid=sys.argv[1:6]
def key(p): return p.replace('/','_').replace('?','_').replace('=','_').replace('&','_')
def load(p):
    try:
        st=open(os.path.join(cap,key(p)+'.status')).read().strip(); body=open(os.path.join(cap,key(p)+'.body')).read()
    except Exception: return "ERR",None
    try: js=json.loads(body) if body.strip() else None
    except Exception: js=None
    return st,js
def unverifiable(st): return st=="ERR" or (st.isdigit() and st!="404" and not st.startswith("2"))
st_p,prot=load(f"repos/{orepo}/branches/{target}/protection"); st_r,rules=load(f"repos/{orepo}/rules/branches/{target}"); st_s,rsets=load(f"repos/{orepo}/rulesets")
if unverifiable(st_p) or unverifiable(st_r) or unverifiable(st_s):
    print("PREVENTION_UNVERIFIABLE|http/network/auth: protection=%s rules=%s rulesets=%s"%(st_p,st_r,st_s)); sys.exit(0)
why=[]; prot_ok=False
if st_p.startswith("2") and isinstance(prot,dict):
    rsc=prot.get("required_status_checks") or {}
    ctx=rsc.get("contexts") or [c.get("context") for c in (rsc.get("checks") or [])]
    if check not in (ctx or []): why.append(f"contexts∌{check}")
    else:
        # [C1] checks[] 의 그 컨텍스트 app_id == Actions app id (이름은 정체성이 아니다)
        cks=[c for c in (rsc.get("checks") or []) if c.get("context")==check]
        if not cks: why.append(f"checks[] 에 {check} 항목 부재(app_id 확인 불가)")
        elif not any(str(c.get("app_id"))==str(appid) for c in cks): why.append(f"checks[{check}].app_id={[c.get('app_id') for c in cks]}≠Actions {appid}")
    if rsc.get("strict") is not True: why.append("strict≠true")
    if (prot.get("enforce_admins") or {}).get("enabled") is not True: why.append("enforce_admins≠true")
    if (prot.get("allow_force_pushes") or {}).get("enabled") is not False: why.append("allow_force_pushes.enabled≠false(부재 포함)")
    if (prot.get("allow_deletions") or {}).get("enabled") is not False: why.append("allow_deletions.enabled≠false(부재 포함)")
    if "required_pull_request_reviews" not in prot: why.append("required_pull_request_reviews 키 부재")
    restr=prot.get("restrictions")
    if isinstance(restr,dict) and (restr.get("apps") or []): why.append("restrictions.apps≠[]")
    prot_ok = not why
elif st_p=="404": why.append("protection 404")
rs_ok=False; rs_why=[]; applied=rules if isinstance(rules,list) else []
if applied:
    types={r.get("type") for r in applied}; ids={r.get("ruleset_id") for r in applied}
    def rsc_ok():
        for r in applied:
            if r.get("type")=="required_status_checks":
                p=r.get("parameters") or {}
                if p.get("strict_required_status_checks_policy") is True and any(c.get("context")==check and str(c.get("integration_id"))==str(appid) for c in p.get("required_status_checks") or []): return True
        return False
    if not rsc_ok(): rs_why.append(f"required_status_checks{{strict,context∋{check},integration_id=={appid}}} 없음")
    for t in ("pull_request","non_fast_forward","deletion"):
        if t not in types: rs_why.append(f"rule {t} 없음")
    for i in ids:
        st_i,rs=load(f"repos/{orepo}/rulesets/{i}")
        if unverifiable(st_i): print("PREVENTION_UNVERIFIABLE|rulesets/%s http=%s"%(i,st_i)); sys.exit(0)
        if not isinstance(rs,dict): rs_why.append(f"rulesets/{i} 본문 없음"); continue
        if rs.get("enforcement")!="active": rs_why.append(f"rulesets/{i}.enforcement={rs.get('enforcement')}")
        if "bypass_actors" not in rs: rs_why.append(f"rulesets/{i}.bypass_actors 키 부재(불충족)")
        elif rs.get("bypass_actors")!=[]: rs_why.append(f"rulesets/{i}.bypass_actors≠[]")
    rs_ok = not rs_why
else: rs_why.append("적용 규칙 0")
if prot_ok or rs_ok: print("PREVENTION_ACTIVE|(a) 술어 충족: classic=%s ruleset=%s"%(prot_ok,rs_ok)); sys.exit(0)
if st_p=="404" and not applied: print("PREVENTION_ABSENT|protection 404 ∧ 적용 규칙 0 (룰셋 목록=%s)"%(len(rsets) if isinstance(rsets,list) else "n/a")); sys.exit(0)
print("PREVENTION_INSUFFICIENT|classic:[%s] ruleset:[%s]"%("; ".join(why),"; ".join(rs_why)))
PY
)
[ -n "$A_STATE" ] || A_STATE="PREVENTION_UNVERIFIABLE|(a) 캡처 평가 함수가 값을 내지 못함(파서 오류)"
A_VAL=${A_STATE%%|*}; A_WHY=${A_STATE#*|}
printf 'u17_live_state=%s\nu17_live_reason=%s\n' "$A_VAL" "$A_WHY"
[ "$A_VAL" = PREVENTION_ACTIVE ] || fire "$A_VAL" "(a) $A_WHY"
fi

# ── (c) P_first / P_last · D  (구조 정의 · 후보 = --full-history)
intro_set() { local path="$1" out="" x p intro; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue; intro=1; for p in $(git log --format=%P -1 "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
last_change() { local path="$1" x p b bp changed; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue; b=$(git rev-parse "$x:$path"); changed=0; ps=$(git log --format=%P -1 "$x"); [ -n "$ps" ] || changed=1; for p in $ps; do bp=$(git rev-parse -q --verify "$p:$path" 2>/dev/null || echo ABSENT); [ "$bp" != "$b" ] && changed=1; done; [ "$changed" = 1 ] && { printf '%s' "$x"; return; }; done; }
if [ -n "$BODY" ]; then P_FIRST=$(intro_set "$PC" | awk '{print $NF}'); P_LAST=$(last_change "$PC"); else P_FIRST=""; P_LAST=""; fi
D=$(intro_set "$CFG"); ND=$(printf '%s\n' $D | grep -c .)
printf 'P_first=%s P_last=%s |D|=%s D=%s\n' "${P_FIRST:-∅}" "${P_LAST:-∅}" "$ND" "$(printf '%s ' $D)"
if [ -n "$BODY" ] && [ "$ND" -gt 0 ]; then
  LATE=0; MUT=0
  for d in $D; do { git merge-base --is-ancestor "$P_FIRST" "$d" && [ "$P_FIRST" != "$d" ]; } || LATE=1; done
  if [ "$LATE" = 1 ]; then fire PREVENTION_LATE "∃d∈D: P_first=$P_FIRST ⋠ d — 기록이 착수보다 늦다"
  else for d in $D; do { git merge-base --is-ancestor "$P_LAST" "$d" && [ "$P_LAST" != "$d" ]; } || MUT=1; done
       [ "$MUT" = 0 ] || fire PREVENTION_ARTIFACT_MUTATED "∀d P_first⊰d 이나 ∃d∈D: P_last=$P_LAST ⋠ d — 착수 «후» 아티팩트 변경"; fi
  [ "$(git rev-parse HEAD:$PC)" = "$(git rev-parse "$P_LAST:$PC")" ] || fire PREVENTION_ARTIFACT_MUTATED "소비 blob(HEAD) ≠ P_last 시점 blob"
fi

# ── (b) 리비전 특정 ∀d∈D (전순서 8) — D=∅ 는 «검증 대상 없음»(명시)
if [ "$ND" -eq 0 ]; then
  printf 'U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)\n'
elif [ -n "$TARGET" ]; then
  MINMERGED=""
  for d in $D; do
    respond "repos/$PIN_OR/commits/$d/pulls"; show_capture B1 "repos/$PIN_OR/commits/$d/pulls"
    HS=$(python3 - "$CAP" "$PIN_OR" "$d" "$TARGET" <<'PY'
import json,sys,os
cap,orepo,d,target=sys.argv[1:5]; k=f"repos/{orepo}/commits/{d}/pulls".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: prs=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|pulls 본문 파싱 실패"); sys.exit(0)
ok=[p for p in prs if isinstance(p,dict) and p.get("merged_at") and (p.get("base") or {}).get("ref")==target]
if not ok: print("UNVERIFIED_REVISION|착지 PR 부재·merged 아님·base≠target (pulls=%d)"%len(prs)); sys.exit(0)
print("HEAD|%s|%s"%(ok[0]["head"]["sha"],ok[0]["merged_at"]))
PY
)
    case "$HS" in UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b) d=$d ${HS#*|}"; continue ;; UNVERIFIED_REVISION\|*) fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d ${HS#*|}"; continue ;; esac
    HSHA=$(printf '%s' "$HS" | cut -d'|' -f2); MERGED=$(printf '%s' "$HS" | cut -d'|' -f3); { [ -z "$MINMERGED" ] || [[ "$MERGED" < "$MINMERGED" ]]; } && MINMERGED="$MERGED"
    respond "repos/$PIN_OR/commits/$HSHA/check-runs"; show_capture B2 "repos/$PIN_OR/commits/$HSHA/check-runs"
    CANDS=$(python3 - "$CAP" "$PIN_OR" "$HSHA" "$CHECK" "$APPID" <<'PY'
import json,sys,os
cap,orepo,sha,check,appid=sys.argv[1:6]; k=f"repos/{orepo}/commits/{sha}/check-runs".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: js=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|check-runs 본문 파싱 실패"); sys.exit(0)
runs=js.get("check_runs") or []
named=[r for r in runs if r.get("name")==check and r.get("conclusion")=="success"]
good=[r for r in named if str((r.get("app") or {}).get("id"))==str(appid) and r.get("head_sha")==sha]
why=[]
if not named: why.append("name==%s ∧ conclusion==success 인 run 부재"%check)
else:
    for r in named:
        if str((r.get("app") or {}).get("id"))!=str(appid): why.append("app.id=%s≠Actions %s(위조 표면)"%((r.get("app") or {}).get("id"),appid))
        if r.get("head_sha")!=sha: why.append("head_sha=%s≠PR head"%r.get("head_sha"))
if not good: print("UNVERIFIED_REVISION|%s (check_runs=%d)"%("; ".join(why),len(runs))); sys.exit(0)
print("CAND|"+" ".join(str((r.get("check_suite") or {}).get("id")) for r in good))
PY
)
    case "$CANDS" in UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b) head=$HSHA ${CANDS#*|}"; continue ;; UNVERIFIED_REVISION\|*) fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA ${CANDS#*|}"; continue ;; esac
    IDENT_OK=0; IDENT_WHY=""
    for sid in ${CANDS#CAND|}; do
      [ "$sid" != None ] || { IDENT_WHY="$IDENT_WHY check_suite.id 부재;"; continue; }
      respond "repos/$PIN_OR/check-suites/$sid"; show_capture B3 "repos/$PIN_OR/check-suites/$sid"
      SST=$(http_of "repos/$PIN_OR/check-suites/$sid"); ok2xx "$SST" || { fire PREVENTION_UNVERIFIABLE "(b) check-suites/$sid http=$SST"; continue; }
      [ "$(jget "repos/$PIN_OR/check-suites/$sid" head_sha)" = "$HSHA" ] || { IDENT_WHY="$IDENT_WHY suite $sid head_sha≠PR head;"; continue; }
      # [C2-①②] 워크플로 run: actions/runs?check_suite_id=<sid> → head_sha==PR head ∧ path==WF_PATH
      Q="repos/$PIN_OR/actions/runs?check_suite_id=$sid"; respond "$Q"; show_capture B4 "$Q"
      QST=$(http_of "$Q"); ok2xx "$QST" || { fire PREVENTION_UNVERIFIABLE "(b) $Q http=$QST"; continue; }
      WFOK=$(python3 - "$CAP/$(key "$Q").body" "$HSHA" "$WF_PATH" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); sha,wf=sys.argv[2],sys.argv[3]
runs=j.get("workflow_runs") or []
hit=[r for r in runs if r.get("head_sha")==sha and r.get("path")==wf]
print("OK" if hit else "NO|paths=%s"%[(r.get("path"),r.get("head_sha","")[:7]) for r in runs])
PY
)
      [ "$WFOK" = OK ] || { IDENT_WHY="$IDENT_WHY workflow run path≠$WF_PATH ∨ head_sha≠PR head (${WFOK#NO|});"; continue; }
      IDENT_OK=1; break
    done
    [ "$IDENT_OK" = 1 ] || { fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA 워크플로 정체성 불충족:${IDENT_WHY:- 후보 없음}"; continue; }
    # [R2-③] 그 head_sha 시점의 워크플로 blob (로컬 저장소) — 부재 = UNVERIFIED_REVISION · 두 리터럴 grep
    if WF=$(git show "$HSHA:$WF_PATH" 2>/dev/null); then
      printf 'U17-B5 git show %s:%s  (blob %s)\n' "$HSHA" "$WF_PATH" "$(git rev-parse -q --verify "$HSHA:$WF_PATH")"; printf '%s\n' "$WF" | sed 's/^/  | /'
      L1=$(printf '%s\n' "$WF" | grep -cF -- "$LIT1"); L2=$(printf '%s\n' "$WF" | grep -cF -- "$LIT2")
      printf 'U17-B5 grep: %s → %s회 · %s → %s회\n' "$LIT1" "$L1" "$LIT2" "$L2"
      { [ "$L1" -ge 1 ] && [ "$L2" -ge 1 ]; } || { fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA 워크플로 blob 에 리터럴 부재 (harness path=$L1 sha256=$L2)"; continue; }
    else fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA git show <head>:$WF_PATH 실패(파일 부재·커밋 부재) — 검사 생략 금지"; continue; fi
    printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/blob(2 리터럴) 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
  done
  for id in ${RSIDS:-}; do
    python3 - "$id" "$(jget "repos/$PIN_OR/rulesets/$id" created_at)" "$(jget "repos/$PIN_OR/rulesets/$id" updated_at)" "$MINMERGED" <<'PY'
import sys,datetime
i,ca,ua,mm=sys.argv[1:5]
def p(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(datetime.timezone.utc)
    except Exception: return None
c,u,m=p(ca),p(ua),p(mm)
if None in (c,u,m): print(f"U17-α ruleset {i}: 시각 파싱 불가(created_at={ca} updated_at={ua} merged_at(minD)={mm}) — 관측 기록"); sys.exit(0)
print(f"U17-α ruleset {i}: created_at={c.isoformat()} {'≤' if c<=m else '> (착수 후 생성)'} merged_at(minD)={m.isoformat()} · updated_at={u.isoformat()} {'> merged_at (착수 후 변경됨)' if u>m else '≤ merged_at'} (관측 기록·차단 아님)")
PY
  done
fi

finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=$ND · app/suite/workflow path/blob 2 리터럴) — responder=$RESP"
```

## 2. 드라이버 원문 — `t84v218.sh` (sha256 `5f04e1c68a67a17ac6104b91c3b98b878ff73eeba6f720a1ad1796de6377ea1e`)

- 픽스처 = `scratchpad/fx84x/*`(seed → P → [W: `.github/workflows/tos-gate.yml` SIMULATED, 두 리터럴 포함] → [d] · 원격 URL 은 로컬 config 만). seam 주입 `scratchpad/seam218/<variant>/` — 응답 원문은
  드라이버(`ACT`/`ACT_BADAPP`/`INSUF`/`base_seam`/`rev_seam`)와 실행 기록의 `U17-A*`/`U17-B*` 캡처에 그대로. 전부 GET-only.

```bash
#!/usr/bin/env bash
# t84v218.sh — v2.18 T-84 ①~⑩ + 부속 드라이버 (u17-verify-v218.sh). GET-only. 픽스처 = scratchpad 독립 git repo(원격 URL 은 로컬 config 만). 본 저장소 무접촉·설정 변경 0.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
EX="$SP/u17-verify-v218.sh"; FX="$SP/fx84x"; SEAM="$SP/seam218"; PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md; WF=.github/workflows/tos-gate.yml
OR=kakao-harris-lee/kis_unified_sts; PINURL=https://github.com/kakao-harris-lee/kis_unified_sts.git; WB=mission-critical-trading-operating-system; REPO=/Users/harris/Development/private/kis_unified_sts
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "${2:-$PINURL}"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ # art <repo> <owner_repo-declared> <target-declared> [msg]
  mkdir -p "$1/$(dirname $PC)"; printf 'owner_repo: %s\ntarget_branch: %s\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n' "$2" "$3" > "$1/$PC"
  git -C "$1" add -A; git -C "$1" commit -q -m "${4:-P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)}"; git -C "$1" rev-parse HEAD; }
wf(){ # wf <repo> [nolit] — 정본 워크플로 파일(두 리터럴 포함) 커밋 W (SIMULATED · 실제 CI 잡이 아님)
  mkdir -p "$1/.github/workflows"
  if [ "${2:-}" = nolit ]; then printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo no-harness-here\n' > "$1/$WF"
  else printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - name: verify harness identity\n        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s\n      - name: run entry harness\n        run: bash tools/tos_entry_harness.sh\n' "$LIT2" > "$1/$WF"; fi
  git -C "$1" add -A; git -C "$1" commit -q -m "W: add $WF (SIMULATED workflow with harness path + sha256 literals)"; git -C "$1" rev-parse HEAD; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ echo "-- remotes --"; git -C "$1" remote -v | sed 's/^/  | /'; echo "-- artifact @HEAD --"; git -C "$1" show "HEAD:$PC" 2>/dev/null | sed 's/^/  | /'; git -C "$1" log --oneline --graph | sed 's/^/  /'; echo "\$ U17_RESPONDER=${2:-gh} bash u17-verify-v218.sh <fixture>"; U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$1"; echo "u17_rc=$?"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; if [ -f "$4" ]; then cp "$4" "$1/$(k "$2").body"; else printf '%s\n' "$4" > "$1/$(k "$2").body"; fi; }
probe(){ echo "\$ gh api -i $1   # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; gh api -i "$1" 2>&1 | grep -v -E '^[A-Za-z-]+: ' | tr -d '\r' | sed 's/^/  | /'; }
ACT='{"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
ACT_BADAPP='{"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":99999}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
INSUF='{"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"enforce_admins":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
base_seam(){ # base_seam <dir> <protection-json|404>
  inject "$1" "apps/github-actions" 200 '{"id":15368,"slug":"github-actions","name":"GitHub Actions"}'
  inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'
  if [ "$2" = 404 ]; then inject "$1" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","status":"404"}'; else inject "$1" "repos/$OR/branches/main/protection" 200 "$2"; fi
  inject "$1" "repos/$OR/rules/branches/main" 200 '[]'; inject "$1" "repos/$OR/rulesets" 200 '[]'; }
rev_seam(){ # rev_seam <dir> <d> <head> <suite> [app|path|nocr]  — (b) 양성 주입 (+변형)
  local dir="$1" d="$2" h="$3" s="$4" v="${5:-}"; local app=15368 path=.github/workflows/tos-gate.yml
  [ "$v" = app ] && app=99999; [ "$v" = path ] && path=.github/workflows/test.yml
  inject "$dir" "repos/$OR/commits/$d/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"2026-08-19T00:10:00Z\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$h\"}}]"
  if [ "$v" = nocr ]; then inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"total_count\":1,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}}]}"
  else inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}},{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":$app,\"slug\":\"$([ $app = 15368 ] && echo github-actions || echo third-party-forger)\"},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}}]}"; fi
  inject "$dir" "repos/$OR/check-suites/$s" 200 "{\"id\":$s,\"head_sha\":\"$h\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"status\":\"completed\",\"conclusion\":\"success\"}"
  inject "$dir" "repos/$OR/actions/runs?check_suite_id=$s" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":424242,\"name\":\"tos-gate\",\"path\":\"$path\",\"head_sha\":\"$h\",\"check_suite_id\":$s,\"conclusion\":\"success\"}]}"; }
rm -rf "$SEAM"; mkdir -p "$SEAM/neterr"; base_seam "$SEAM/active" "$ACT"; base_seam "$SEAM/badapp" "$ACT_BADAPP"; base_seam "$SEAM/insufficient" "$INSUF"; base_seam "$SEAM/released-absent" 404
base_seam "$SEAM/unverifiable" "$ACT"; inject "$SEAM/unverifiable" "repos/$OR/branches/main/protection" 500 '{"message":"SIMULATED server error"}'

sec "T-84 (0) live 병기 — 핀·파생 원천 실측 (GET-only): 본 저장소 원격 · repos/{pin}.default_branch · apps/github-actions.id"
echo "\$ git remote -v (본 저장소)"; git -C "$REPO" remote -v | sed 's/^/  | /'
probe "apps/github-actions" | head -4; echo "  .id=$(gh api apps/github-actions 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
probe "repos/$OR" | head -3; echo "  .default_branch=$(gh api repos/$OR 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["default_branch"])')"
echo "-- 참고(raw probe 관측·상태값 기대 아님): 비-default 브랜치 $WB 의 protection --"; probe "repos/$OR/branches/$WB/protection" | head -4

sec "T-84 (1) live — 원격 == 핀 · 선언 == 핀/default(main) → INSUFFICIENT (responder=gh)"
R="$FX/live-main"; mk "$R"; art "$R" "$OR" main >/dev/null; run "$R" gh

sec "T-84 (5)-a live — 아티팩트가 비-default 브랜치($WB) 선언 (D=∅) → TARGET_MISMATCH"
R="$FX/mm-branch"; mk "$R"; art "$R" "$OR" "$WB" >/dev/null; run "$R" gh
sec "T-84 (5)-b live — 아티팩트가 타 저장소(octocat/Hello-World) 선언 (D=∅) → TARGET_MISMATCH"
R="$FX/mm-repo"; mk "$R"; art "$R" octocat/Hello-World main >/dev/null; run "$R" gh

sec "T-84 (10)-a live — 원격이 타 host 동일 경로 (gitlab.com/kakao-harris-lee/kis_unified_sts) · 선언은 핀과 일치 → TARGET_MISMATCH (host 보존 정규화)"
R="$FX/host-gitlab"; mk "$R" https://gitlab.com/kakao-harris-lee/kis_unified_sts.git; art "$R" "$OR" main >/dev/null; run "$R" gh
sec "T-84 (10)-b live — 원격이 타 owner (github.com/octocat/kis_unified_sts) → TARGET_MISMATCH"
R="$FX/host-owner"; mk "$R" git@github.com:octocat/kis_unified_sts.git; art "$R" "$OR" main >/dev/null; run "$R" gh
sec "T-84 (10)-c live — 원격 2개(upstream=gitlab 동일 경로 · fork=핀 ssh 형) → 핀과 일치하는 원격 «존재» 이므로 대조 통과 → (a) INSUFFICIENT"
R="$FX/host-two"; mk "$R" https://gitlab.com/kakao-harris-lee/kis_unified_sts.git; git -C "$R" remote rename origin upstream; git -C "$R" remote add fork git@github.com:kakao-harris-lee/kis_unified_sts.git; art "$R" "$OR" main >/dev/null; run "$R" gh
sec "T-84 (10)-d 대조 — host 를 버리는 정규화(v2.17 규칙)라면 (10)-a 를 통과시켰을 것 (같은 URL 로 두 정규화 병기)"
python3 - <<'PY'
import re
u="https://gitlab.com/kakao-harris-lee/kis_unified_sts.git"
v217=re.sub(r'^(https?://[^/]+/|ssh://git@[^/]+/|git@[^:]+:)','',u); v217=re.sub(r'\.git$','',v217)
v218=re.sub(r'^https?://([^/]+)/(.+)$',r'\1/\2',u); v218=re.sub(r'\.git$','',v218)
print(f"  url={u}\n  v2.17 host-drop → {v217}  == pin owner/repo? {v217=='kakao-harris-lee/kis_unified_sts'} (통과였을 것)\n  v2.18 host-keep → {v218}  == pin? {v218=='github.com/kakao-harris-lee/kis_unified_sts'} (MISMATCH)")
PY

sec "T-84 (2)-i seam ACTIVE (SIMULATED · checks[tos-gate].app_id=15368)"; R="$FX/seam"; mk "$R"; art "$R" "$OR" main >/dev/null; run "$R" "file:$SEAM/active"
sec "T-84 (2)-ii seam INSUFFICIENT"; run "$R" "file:$SEAM/insufficient"
sec "T-84 (2)-iii seam UNVERIFIABLE — protection 500"; run "$R" "file:$SEAM/unverifiable"
sec "T-84 (2)-iv seam UNVERIFIABLE — 응답 없음(apps/github-actions·repos/{pin} 부터 실패)"; run "$R" "file:$SEAM/neterr"
sec "T-84 (7) seam — contexts ∋ tos-gate 이나 checks[tos-gate].app_id=99999(타 앱 고정) → INSUFFICIENT (D=∅ 에서도 · (a) 무조건)"; run "$R" "file:$SEAM/badapp"
echo "-- 대조: contexts 이름만 보는 v2.17 (a) 술어라면 이 캡처는 prot_ok=True 였다 --"
python3 - "$SEAM/badapp/$(k "repos/$OR/branches/main/protection").body" <<'PY'
import json,sys; p=json.load(open(sys.argv[1])); rsc=p["required_status_checks"]
print("  name-only (v2.17): contexts∋tos-gate=%s ∧ strict=%s ∧ enforce_admins=%s ∧ PR reviews=%s → prot_ok=%s"%("tos-gate" in rsc["contexts"], rsc["strict"], p["enforce_admins"]["enabled"], "required_pull_request_reviews" in p, True))
print("  identity  (v2.18): checks[tos-gate].app_id=%s == Actions 15368? %s → INSUFFICIENT"%([c["app_id"] for c in rsc["checks"] if c["context"]=="tos-gate"], any(c["app_id"]==15368 for c in rsc["checks"] if c["context"]=="tos-gate")))
PY

sec "T-84 (3)-0 live 병기 — (b) 원자료: 미푸시 HEAD 422 · 푸시 무-PR [] · PR#636 head check-runs + actions/runs?check_suite_id + 로컬 git show <head>:$WF"
H=$(git -C "$REPO" rev-parse HEAD); OM=$(git -C "$REPO" rev-parse origin/main); echo "HEAD(미푸시)=$H origin/main=$OM"
probe "repos/$OR/commits/$H/pulls" | head -4; probe "repos/$OR/commits/be98f075715521a46c4ae074150cbec2746e7384/pulls" | head -4
HS=$(gh api "repos/$OR/commits/$OM/pulls" 2>/dev/null | python3 -c 'import json,sys
a=json.load(sys.stdin); ok=[p for p in a if p.get("merged_at") and (p.get("base") or {}).get("ref")=="main"]; print(ok[0]["head"]["sha"] if ok else "")')
echo "PR#636 head.sha=$HS"
gh api "repos/$OR/commits/$HS/check-runs" 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin); [print("  run name=%r conclusion=%r app.id=%s head_sha=%s suite=%s"%(r["name"],r["conclusion"],(r.get("app") or {}).get("id"),r["head_sha"][:7],(r.get("check_suite") or {}).get("id"))) for r in j.get("check_runs",[])]'
SID=$(gh api "repos/$OR/commits/$HS/check-runs" 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin); print(j["check_runs"][0]["check_suite"]["id"])')
probe "repos/$OR/actions/runs?check_suite_id=$SID" | head -3; gh api "repos/$OR/actions/runs?check_suite_id=$SID" 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin); [print("  workflow_run id=%s name=%r path=%r head_sha=%s"%(r["id"],r["name"],r["path"],r["head_sha"][:7])) for r in j.get("workflow_runs",[])]'
echo "\$ git -C <repo> show $HS:$WF"; git -C "$REPO" show "$HS:$WF" 2>&1 | head -3; echo "  (rc=$? — 로컬 저장소에 그 head 커밋/파일이 없으면 R2 규약상 UNVERIFIED_REVISION)"
echo "\$ git -C <repo> cat-file -e $HS^{commit}"; git -C "$REPO" cat-file -e "$HS^{commit}" 2>&1 && echo "  commit present" || echo "  commit absent locally(squash 착지 — PR head 는 fetch 되지 않음)"
echo "  ⇒ 실 저장소 (b): tos-gate 이름 부재·정본 워크플로 path 부재·로컬 blob 부재 — 어느 축으로도 UNVERIFIED_REVISION"

sec "T-84 (3)-a mixed — (a) seam ACTIVE + (b) live: 픽스처 d 는 GitHub 에 없는 sha → 422 → UNVERIFIABLE (전순서 1 · 수집 후 방출)"
R="$FX/rev-live"; mk "$R"; art "$R" "$OR" main >/dev/null; W=$(wf "$R"); D=$(d0a "$R"); echo "W=$W d=$D"; run "$R" "mixed:$SEAM/active"

sec "T-84 (3)-b seam — (b) 양성(SIMULATED 서버 · 워크플로 blob 은 픽스처 커밋 W 에 실재): 전 조건 충족 → ACTIVE"
R="$FX/rev-seam"; mk "$R"; art "$R" "$OR" main >/dev/null; W=$(wf "$R"); D=$(d0a "$R"); echo "W(PR head)=$W d=$D"
S="$SEAM/rev-ok"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001; run "$R" "file:$S"
sec "T-84 (6) seam — check-run app.id=99999 (tos-gate·success) → UNVERIFIED_REVISION"
S="$SEAM/rev-app"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001 app; run "$R" "file:$S"
sec "T-84 (8) seam — same-app wrong-workflow: app.id 15368 이나 workflow run path=.github/workflows/test.yml → UNVERIFIED_REVISION"
S="$SEAM/rev-path"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001 path; run "$R" "file:$S"
echo "-- 대조: app id 만 보는 구현(v2.17 (b)) 은 같은 캡처에서 통과 --"
python3 - "$S/$(k "repos/$OR/commits/$W/check-runs").body" "$S/$(k "repos/$OR/actions/runs?check_suite_id=777001").body" <<'PY'
import json,sys; cr=json.load(open(sys.argv[1]))["check_runs"]; wr=json.load(open(sys.argv[2]))["workflow_runs"]
print("  app-id-only (v2.17): tos-gate∧success∧app.id==15368 → %s (PASS)"%any(r["name"]=="tos-gate" and r["conclusion"]=="success" and r["app"]["id"]==15368 for r in cr))
print("  workflow-identity (v2.18): run path=%r == .github/workflows/tos-gate.yml? %s → UNVERIFIED_REVISION"%(wr[0]["path"], wr[0]["path"]==".github/workflows/tos-gate.yml"))
PY
sec "T-84 (3)-c seam — check-run 부재(tos-gate 없음) → UNVERIFIED_REVISION"
S="$SEAM/rev-nocr"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001 nocr; run "$R" "file:$S"
sec "T-84 (R2)-a seam — 서버 3중은 충족이나 로컬 <head>:$WF 부재 (PR head = 워크플로 없는 커밋) → UNVERIFIED_REVISION (검사 생략 금지)"
R2="$FX/rev-nowf"; mk "$R2"; art "$R2" "$OR" main >/dev/null; H0=$(git -C "$R2" rev-parse HEAD); D2=$(d0a "$R2"); echo "PR head(워크플로 없음)=$H0 d=$D2"
S="$SEAM/rev-nowf"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D2" "$H0" 777001; run "$R2" "file:$S"
sec "T-84 (R2)-b seam — 워크플로 파일은 있으나 두 리터럴 부재 → UNVERIFIED_REVISION"
R2="$FX/rev-nolit"; mk "$R2"; art "$R2" "$OR" main >/dev/null; W2=$(wf "$R2" nolit); D2=$(d0a "$R2"); echo "W(리터럴 없음)=$W2 d=$D2"
S="$SEAM/rev-nolit"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D2" "$W2" 777001; run "$R2" "file:$S"

sec "T-84 (9)-a — P_first → W → d → 아티팩트 편집(P_last 가 d 이후) → ARTIFACT_MUTATED (서버는 seam 전 조건 충족 · git 구조는 live)"
R="$FX/mut"; mk "$R"; PF=$(art "$R" "$OR" main); W=$(wf "$R"); D=$(d0a "$R")
printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\nnote: post-start edit (SIMULATED)\n' "$OR" > "$R/$PC"; git -C "$R" add -A; git -C "$R" commit -q -m "P-edit: artifact edited AFTER D0-A start"; PL=$(git -C "$R" rev-parse HEAD)
echo "P_first=$PF W=$W d=$D P_edit=$PL"; S="$SEAM/rev-mut"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001; run "$R" "file:$S"
sec "T-84 (9)-b — 편집 후 원복(내용은 P_first 와 동일) → P_last = 원복 커밋(d 이후) → ARTIFACT_MUTATED"
git -C "$R" checkout -q "$PF" -- "$PC"; git -C "$R" commit -q -am "P-revert: restore artifact content (still after d)"; PR=$(git -C "$R" rev-parse HEAD); echo "P_revert=$PR (blob == P_first blob: $([ "$(git -C "$R" rev-parse "$PF:$PC")" = "$(git -C "$R" rev-parse "$PR:$PC")" ] && echo yes || echo no))"; run "$R" "file:$S"
sec "T-84 (9)-c 대조 — «최초 도입 P 만 보는 구현»(v2.17) 은 (9)-a/b 를 통과시킨다"
echo "  P_first=$PF ⊰ d=$D ? $(git -C "$R" merge-base --is-ancestor "$PF" "$D" && echo yes) → v2.17: (c) 통과 → ACTIVE (사후 편집 허용) / v2.18: P_last=$PR ⋠ d → ARTIFACT_MUTATED"
sec "T-84 (9)-d — P_first ⋠ d (W → d → P) → LATE (전순서 6 < 7)"
R="$FX/late"; mk "$R"; W=$(wf "$R"); D=$(d0a "$R"); PF=$(art "$R" "$OR" main); echo "W=$W d=$D P_first=$PF"; S="$SEAM/rev-late"; rm -rf "$S"; cp -R "$SEAM/active" "$S"; rev_seam "$S" "$D" "$W" 777001; run "$R" "file:$S"

sec "T-84 (4) stub 시퀀스 — t0 seam ACTIVE → t1 해제(404) → t2 약화 → t3 live gh"
R="$FX/seq"; mk "$R"; art "$R" "$OR" main >/dev/null; echo "== t0"; run "$R" "file:$SEAM/active"; echo "== t1"; run "$R" "file:$SEAM/released-absent"; echo "== t2"; run "$R" "file:$SEAM/insufficient"; echo "== t3"; run "$R" gh

sec "T-84 부속 — countersign 형식 위반 → UNSIGNED (전순서 3; seam ACTIVE 하)"
R="$FX/unsigned"; mk "$R"; mkdir -p "$R/$(dirname $PC)"; printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: APPROVED (no ISO)\n' "$OR" > "$R/$PC"; git -C "$R" add -A; git -C "$R" commit -q -m "P: bad countersign"; run "$R" "file:$SEAM/active"
sec "T-84 부속 — 본 저장소 HEAD 에 실행기 적용 (원격 == 핀 · 아티팩트 부재 → ABSENT · (a) 는 live INSUFFICIENT 도 수집되나 전순서 2 가 5 를 앞선다)"
echo "\$ bash u17-verify-v218.sh <repo>"; U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO"; echo "u17_rc=$?"
```

## 3. 실행 기록 (t84v218.sh stdout 전문 · 캡처 verbatim + UTC · live 병기 원자료 포함)

```text
t84v218_utc=2026-08-18T19:02:27Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t84v218.sh

########## T-84 (0) live 병기 — 핀·파생 원천 실측 (GET-only): 본 저장소 원격 · repos/{pin}.default_branch · apps/github-actions.id ##########
$ git remote -v (본 저장소)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
$ gh api -i apps/github-actions   # utc=2026-08-18T19:02:27Z
  | HTTP/2.0 200 OK
  | 
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
  .id=15368
$ gh api -i repos/kakao-harris-lee/kis_unified_sts   # utc=2026-08-18T19:02:28Z
  | HTTP/2.0 200 OK
  | 
  .default_branch=main
-- 참고(raw probe 관측·상태값 기대 아님): 비-default 브랜치 mission-critical-trading-operating-system 의 protection --
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/branches/mission-critical-trading-operating-system/protection   # utc=2026-08-18T19:02:29Z
  | HTTP/2.0 404 Not Found
  | 
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection#get-branch-protection","status":"404"}gh: Branch not protected (HTTP 404)

########## T-84 (1) live — 원격 == 핀 · 선언 == 핀/default(main) → INSUFFICIENT (responder=gh) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * c2942b9 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 2234031 seed
$ U17_RESPONDER=gh bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6v5gpE2IIy
U17-A00 apps/github-actions  utc=2026-08-18T19:02:31Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:31Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:32Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:32Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:33Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:02:34Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=c2942b9837cf522e33e945238c287155e0c7849f P_last=c2942b9837cf522e33e945238c287155e0c7849f |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (5)-a live — 아티팩트가 비-default 브랜치(mission-critical-trading-operating-system) 선언 (D=∅) → TARGET_MISMATCH ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * ca02767 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * c270e44 seed
$ U17_RESPONDER=gh bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.nhXb44tNDf
U17-A00 apps/github-actions  utc=2026-08-18T19:02:35Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:35Z  http=200  (.default_branch=main)
U17-T declared-vs-pin:  target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main)
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:36Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:36Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:37Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:02:38Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=ca02767a5081c768ec8b3a08baa06f30680cfd73 P_last=ca02767a5081c768ec8b3a08baa06f30680cfd73 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) [수집 2건 중 전순서 최소]
u17_rc=1

########## T-84 (5)-b live — 아티팩트가 타 저장소(octocat/Hello-World) 선언 (D=∅) → TARGET_MISMATCH ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: octocat/Hello-World
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 19a9d77 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 4c76a83 seed
$ U17_RESPONDER=gh bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.RLMnCBPLNy
U17-A00 apps/github-actions  utc=2026-08-18T19:02:39Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:40Z  http=200  (.default_branch=main)
U17-T declared-vs-pin:  owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts)
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:40Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:41Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:41Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:02:42Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=19a9d772ed0fc90a1feaec74dbc6aff73d1166eb P_last=19a9d772ed0fc90a1feaec74dbc6aff73d1166eb |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 계약 핀/파생값과 불일치: owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## T-84 (10)-a live — 원격이 타 host 동일 경로 (gitlab.com/kakao-harris-lee/kis_unified_sts) · 선언은 핀과 일치 → TARGET_MISMATCH (host 보존 정규화) ##########
-- remotes --
  | origin	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * c199f35 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * c681b53 seed
$ U17_RESPONDER=gh bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=gitlab.com/kakao-harris-lee/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GcGQ85LmCM
U17-A00 apps/github-actions  utc=2026-08-18T19:02:43Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:43Z  http=200  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:44Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:45Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:45Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:02:46Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=c199f35cecb90c34295da1047e787376a9f25d4b P_last=c199f35cecb90c34295da1047e787376a9f25d4b |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## T-84 (10)-b live — 원격이 타 owner (github.com/octocat/kis_unified_sts) → TARGET_MISMATCH ##########
-- remotes --
  | origin	git@github.com:octocat/kis_unified_sts.git (fetch)
  | origin	git@github.com:octocat/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * ed7a1e7 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 72e7c32 seed
$ U17_RESPONDER=gh bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/octocat/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.8FMXh5bN3B
U17-A00 apps/github-actions  utc=2026-08-18T19:02:48Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:48Z  http=200  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=github.com/octocat/kis_unified_sts)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:48Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:49Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:49Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:02:50Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=ed7a1e7461d6e46a43c3fe7770ba5add0afecae1 P_last=ed7a1e7461d6e46a43c3fe7770ba5add0afecae1 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=github.com/octocat/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## T-84 (10)-c live — 원격 2개(upstream=gitlab 동일 경로 · fork=핀 ssh 형) → 핀과 일치하는 원격 «존재» 이므로 대조 통과 → (a) INSUFFICIENT ##########
-- remotes --
  | fork	git@github.com:kakao-harris-lee/kis_unified_sts.git (fetch)
  | fork	git@github.com:kakao-harris-lee/kis_unified_sts.git (push)
  | upstream	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | upstream	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 6a372f0 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 50992e0 seed
$ U17_RESPONDER=gh bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: fork=github.com/kakao-harris-lee/kis_unified_sts upstream=gitlab.com/kakao-harris-lee/kis_unified_sts match=fork | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.8j94aRw8GU
U17-A00 apps/github-actions  utc=2026-08-18T19:02:52Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:52Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:52Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:53Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:53Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:02:54Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=6a372f02f5fba12967c2b0457a16e4d818099b54 P_last=6a372f02f5fba12967c2b0457a16e4d818099b54 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (10)-d 대조 — host 를 버리는 정규화(v2.17 규칙)라면 (10)-a 를 통과시켰을 것 (같은 URL 로 두 정규화 병기) ##########
  url=https://gitlab.com/kakao-harris-lee/kis_unified_sts.git
  v2.17 host-drop → kakao-harris-lee/kis_unified_sts  == pin owner/repo? True (통과였을 것)
  v2.18 host-keep → gitlab.com/kakao-harris-lee/kis_unified_sts  == pin? False (MISMATCH)

########## T-84 (2)-i seam ACTIVE (SIMULATED · checks[tos-gate].app_id=15368) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * c5b9f94 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * c2dc6f4 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.g6ovsmKmkh
U17-A00 apps/github-actions  utc=2026-08-18T19:02:55Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:55Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:55Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:55Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:55Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=c5b9f94164c24abfba70e6eeaeab12f8973c7439 P_last=c5b9f94164c24abfba70e6eeaeab12f8973c7439 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=0 · app/suite/workflow path/blob 2 리터럴) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active
u17_rc=0

########## T-84 (2)-ii seam INSUFFICIENT ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * c5b9f94 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * c2dc6f4 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/insufficient bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/insufficient capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kKmP6RBxYi
U17-A00 apps/github-actions  utc=2026-08-18T19:02:55Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:55Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:56Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"enforce_admins":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:56Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:56Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=c5b9f94164c24abfba70e6eeaeab12f8973c7439 P_last=c5b9f94164c24abfba70e6eeaeab12f8973c7439 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (2)-iii seam UNVERIFIABLE — protection 500 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * c5b9f94 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * c2dc6f4 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/unverifiable bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/unverifiable capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.jzdBPbn4qe
U17-A00 apps/github-actions  utc=2026-08-18T19:02:56Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:56Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:56Z  http=500
  | {"message":"SIMULATED server error"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:56Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:56Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_UNVERIFIABLE
u17_live_reason=http/network/auth: protection=500 rules=200 rulesets=200
U17-fire PREVENTION_UNVERIFIABLE: (a) http/network/auth: protection=500 rules=200 rulesets=200
P_first=c5b9f94164c24abfba70e6eeaeab12f8973c7439 P_last=c5b9f94164c24abfba70e6eeaeab12f8973c7439 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(a) http/network/auth: protection=500 rules=200 rulesets=200 [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (2)-iv seam UNVERIFIABLE — 응답 없음(apps/github-actions·repos/{pin} 부터 실패) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * c5b9f94 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * c2dc6f4 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/neterr bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@UNRESOLVED
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=∅ (apps/github-actions http=ERR) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/neterr capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.4sjOucH4pd
U17-A00 apps/github-actions  utc=2026-08-18T19:02:57Z  http=ERR
  | SIMULATED responder: no injected response for apps/github-actions
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:57Z  http=ERR  (.default_branch=∅)
U17-fire PREVENTION_UNVERIFIABLE: apps/github-actions 조회 실패(http=ERR) — Actions app id 파생 불가
U17-fire PREVENTION_UNVERIFIABLE: repos/kakao-harris-lee/kis_unified_sts 조회 실패(http=ERR) — default_branch 파생 불가
U17-T declared-vs-pin: 일치
P_first=c5b9f94164c24abfba70e6eeaeab12f8973c7439 P_last=c5b9f94164c24abfba70e6eeaeab12f8973c7439 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=apps/github-actions 조회 실패(http=ERR) — Actions app id 파생 불가 [수집 2건 중 전순서 최소]
u17_rc=1

########## T-84 (7) seam — contexts ∋ tos-gate 이나 checks[tos-gate].app_id=99999(타 앱 고정) → INSUFFICIENT (D=∅ 에서도 · (a) 무조건) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * c5b9f94 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * c2dc6f4 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/badapp bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/badapp capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Z4Xej9vI2j
U17-A00 apps/github-actions  utc=2026-08-18T19:02:58Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:02:58Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:02:58Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":99999}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:02:58Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:02:58Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[checks[tos-gate].app_id=[99999]≠Actions 15368] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[checks[tos-gate].app_id=[99999]≠Actions 15368] ruleset:[적용 규칙 0]
P_first=c5b9f94164c24abfba70e6eeaeab12f8973c7439 P_last=c5b9f94164c24abfba70e6eeaeab12f8973c7439 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[checks[tos-gate].app_id=[99999]≠Actions 15368] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1
-- 대조: contexts 이름만 보는 v2.17 (a) 술어라면 이 캡처는 prot_ok=True 였다 --
  name-only (v2.17): contexts∋tos-gate=True ∧ strict=True ∧ enforce_admins=True ∧ PR reviews=True → prot_ok=True
  identity  (v2.18): checks[tos-gate].app_id=[99999] == Actions 15368? False → INSUFFICIENT

########## T-84 (3)-0 live 병기 — (b) 원자료: 미푸시 HEAD 422 · 푸시 무-PR [] · PR#636 head check-runs + actions/runs?check_suite_id + 로컬 git show <head>:.github/workflows/tos-gate.yml ##########
HEAD(미푸시)=5f4b7cfd66215d0ddeea56733b24855674a1807b origin/main=11e382fc0c9c16d9208a0d59e595d9cf93066be5
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/5f4b7cfd66215d0ddeea56733b24855674a1807b/pulls   # utc=2026-08-18T19:02:58Z
  | HTTP/2.0 422 Unprocessable Entity
  | 
  | {"message":"No commit found for SHA: 5f4b7cfd66215d0ddeea56733b24855674a1807b","documentation_url":"https://docs.github.com/rest/commits/commits#list-pull-requests-associated-with-a-commit","status":"422"}gh: No commit found for SHA: 5f4b7cfd66215d0ddeea56733b24855674a1807b (HTTP 422)
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/be98f075715521a46c4ae074150cbec2746e7384/pulls   # utc=2026-08-18T19:02:59Z
  | HTTP/2.0 200 OK
  | 
  | []
PR#636 head.sha=7656259d414c4a855824406bab40bdc5438de171
  run name='performance' conclusion='success' app.id=15368 head_sha=7656259 suite=83489483104
  run name='lint' conclusion='success' app.id=15368 head_sha=7656259 suite=83489483104
  run name='type-check' conclusion='success' app.id=15368 head_sha=7656259 suite=83489483104
  run name='test' conclusion='success' app.id=15368 head_sha=7656259 suite=83489483104
  run name='backtest-extra' conclusion='success' app.id=15368 head_sha=7656259 suite=83489483104
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=83489483104   # utc=2026-08-18T19:03:01Z
  | HTTP/2.0 200 OK
  | 
  workflow_run id=30792121823 name='Tests' path='.github/workflows/test.yml' head_sha=7656259
$ git -C <repo> show 7656259d414c4a855824406bab40bdc5438de171:.github/workflows/tos-gate.yml
fatal: path '.github/workflows/tos-gate.yml' does not exist in '7656259d414c4a855824406bab40bdc5438de171'
  (rc=0 — 로컬 저장소에 그 head 커밋/파일이 없으면 R2 규약상 UNVERIFIED_REVISION)
$ git -C <repo> cat-file -e 7656259d414c4a855824406bab40bdc5438de171^{commit}
fatal: Not a valid object name 7656259d414c4a855824406bab40bdc5438de171^{commit}
  commit absent locally(squash 착지 — PR head 는 fetch 되지 않음)
  ⇒ 실 저장소 (b): tos-gate 이름 부재·정본 워크플로 path 부재·로컬 blob 부재 — 어느 축으로도 UNVERIFIED_REVISION

########## T-84 (3)-a mixed — (a) seam ACTIVE + (b) live: 픽스처 d 는 GitHub 에 없는 sha → 422 → UNVERIFIABLE (전순서 1 · 수집 후 방출) ##########
W=1d4291191acff3eef708f4a37e52082b406dfb39 d=bbe23969474c2e458c651f0546d96243a4d1fc2c
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bbe2396 D0-A: introduce config/tos_completion.yaml
  * 1d42911 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * 4b2a1e4 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * c65c82a seed
$ U17_RESPONDER=mixed:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active bash u17-verify-v218.sh <fixture>
U17-seam apps/github-actions ← file(SIMULATED)
U17-seam repos/kakao-harris-lee/kis_unified_sts ← file(SIMULATED)
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=mixed:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.0RuusaWVR5
U17-A00 apps/github-actions  utc=2026-08-18T19:03:03Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:03Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-seam repos/kakao-harris-lee/kis_unified_sts/branches/main/protection ← file(SIMULATED)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:03Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-seam repos/kakao-harris-lee/kis_unified_sts/rules/branches/main ← file(SIMULATED)
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:03Z  http=200
  | []
U17-seam repos/kakao-harris-lee/kis_unified_sts/rulesets ← file(SIMULATED)
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:03Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=4b2a1e4d995ce037404011eecdf975d8178f8182 P_last=4b2a1e4d995ce037404011eecdf975d8178f8182 |D|=1 D=bbe23969474c2e458c651f0546d96243a4d1fc2c 
U17-seam repos/kakao-harris-lee/kis_unified_sts/commits/bbe23969474c2e458c651f0546d96243a4d1fc2c/pulls ← gh(live)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bbe23969474c2e458c651f0546d96243a4d1fc2c/pulls  utc=2026-08-18T19:03:04Z  http=422
  | {"message":"No commit found for SHA: bbe23969474c2e458c651f0546d96243a4d1fc2c","documentation_url":"https://docs.github.com/rest/commits/commits#list-pull-requests-associated-with-a-commit","status":"422"}
U17-fire PREVENTION_UNVERIFIABLE: (b) d=bbe23969474c2e458c651f0546d96243a4d1fc2c http=422
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(b) d=bbe23969474c2e458c651f0546d96243a4d1fc2c http=422 [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (3)-b seam — (b) 양성(SIMULATED 서버 · 워크플로 blob 은 픽스처 커밋 W 에 실재): 전 조건 충족 → ACTIVE ##########
W(PR head)=8b244a7a6631caa087d9868180d8778a726682fd d=0863c2d41ef94c59cb14fe83a19a92672ae5ff91
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0863c2d D0-A: introduce config/tos_completion.yaml
  * 8b244a7 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * d6f1f9e P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * cd635de seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-ok bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-ok capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.rg8bWXYcC3
U17-A00 apps/github-actions  utc=2026-08-18T19:03:05Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:05Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:05Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:05Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:05Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=d6f1f9e8dc50451cf4cbe126fc1b1cfd69a8dd2c P_last=d6f1f9e8dc50451cf4cbe126fc1b1cfd69a8dd2c |D|=1 D=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0863c2d41ef94c59cb14fe83a19a92672ae5ff91/pulls  utc=2026-08-18T19:03:05Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"8b244a7a6631caa087d9868180d8778a726682fd"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/8b244a7a6631caa087d9868180d8778a726682fd/check-runs  utc=2026-08-18T19:03:05Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:03:06Z  http=200
  | {"id":777001,"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:03:06Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 git show 8b244a7a6631caa087d9868180d8778a726682fd:.github/workflows/tos-gate.yml  (blob 0aefd2ab57db63d19548f877328f66bef3a45100)
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: verify harness identity
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  |       - name: run entry harness
  |         run: bash tools/tos_entry_harness.sh
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B d=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 head=8b244a7a6631caa087d9868180d8778a726682fd merged_at=2026-08-19T00:10:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob(2 리터럴) 전부 일치
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1 · app/suite/workflow path/blob 2 리터럴) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-ok
u17_rc=0

########## T-84 (6) seam — check-run app.id=99999 (tos-gate·success) → UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0863c2d D0-A: introduce config/tos_completion.yaml
  * 8b244a7 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * d6f1f9e P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * cd635de seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-app bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-app capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.wc0Xjn28YY
U17-A00 apps/github-actions  utc=2026-08-18T19:03:06Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:06Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:06Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:06Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:06Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=d6f1f9e8dc50451cf4cbe126fc1b1cfd69a8dd2c P_last=d6f1f9e8dc50451cf4cbe126fc1b1cfd69a8dd2c |D|=1 D=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0863c2d41ef94c59cb14fe83a19a92672ae5ff91/pulls  utc=2026-08-18T19:03:07Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"8b244a7a6631caa087d9868180d8778a726682fd"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/8b244a7a6631caa087d9868180d8778a726682fd/check-runs  utc=2026-08-18T19:03:07Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":99999,"slug":"third-party-forger"},"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite":{"id":777001}}]}
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 head=8b244a7a6631caa087d9868180d8778a726682fd app.id=99999≠Actions 15368(위조 표면) (check_runs=2)
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 head=8b244a7a6631caa087d9868180d8778a726682fd app.id=99999≠Actions 15368(위조 표면) (check_runs=2) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (8) seam — same-app wrong-workflow: app.id 15368 이나 workflow run path=.github/workflows/test.yml → UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0863c2d D0-A: introduce config/tos_completion.yaml
  * 8b244a7 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * d6f1f9e P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * cd635de seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-path bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-path capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.BLMFaELuX7
U17-A00 apps/github-actions  utc=2026-08-18T19:03:07Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:07Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:07Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:08Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:08Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=d6f1f9e8dc50451cf4cbe126fc1b1cfd69a8dd2c P_last=d6f1f9e8dc50451cf4cbe126fc1b1cfd69a8dd2c |D|=1 D=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0863c2d41ef94c59cb14fe83a19a92672ae5ff91/pulls  utc=2026-08-18T19:03:08Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"8b244a7a6631caa087d9868180d8778a726682fd"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/8b244a7a6631caa087d9868180d8778a726682fd/check-runs  utc=2026-08-18T19:03:08Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:03:08Z  http=200
  | {"id":777001,"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:03:08Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/test.yml","head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite_id":777001,"conclusion":"success"}]}
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 head=8b244a7a6631caa087d9868180d8778a726682fd 워크플로 정체성 불충족: workflow run path≠.github/workflows/tos-gate.yml ∨ head_sha≠PR head (paths=[('.github/workflows/test.yml', '8b244a7')]);
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 head=8b244a7a6631caa087d9868180d8778a726682fd 워크플로 정체성 불충족: workflow run path≠.github/workflows/tos-gate.yml ∨ head_sha≠PR head (paths=[('.github/workflows/test.yml', '8b244a7')]); [수집 1건 중 전순서 최소]
u17_rc=1
-- 대조: app id 만 보는 구현(v2.17 (b)) 은 같은 캡처에서 통과 --
  app-id-only (v2.17): tos-gate∧success∧app.id==15368 → True (PASS)
  workflow-identity (v2.18): run path='.github/workflows/test.yml' == .github/workflows/tos-gate.yml? False → UNVERIFIED_REVISION

########## T-84 (3)-c seam — check-run 부재(tos-gate 없음) → UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0863c2d D0-A: introduce config/tos_completion.yaml
  * 8b244a7 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * d6f1f9e P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * cd635de seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-nocr bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-nocr capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.S7bAoSTcMZ
U17-A00 apps/github-actions  utc=2026-08-18T19:03:09Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:09Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:09Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:09Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:09Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=d6f1f9e8dc50451cf4cbe126fc1b1cfd69a8dd2c P_last=d6f1f9e8dc50451cf4cbe126fc1b1cfd69a8dd2c |D|=1 D=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/0863c2d41ef94c59cb14fe83a19a92672ae5ff91/pulls  utc=2026-08-18T19:03:09Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"8b244a7a6631caa087d9868180d8778a726682fd"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/8b244a7a6631caa087d9868180d8778a726682fd/check-runs  utc=2026-08-18T19:03:09Z  http=200
  | {"total_count":1,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"8b244a7a6631caa087d9868180d8778a726682fd","check_suite":{"id":777001}}]}
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 head=8b244a7a6631caa087d9868180d8778a726682fd name==tos-gate ∧ conclusion==success 인 run 부재 (check_runs=1)
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=0863c2d41ef94c59cb14fe83a19a92672ae5ff91 head=8b244a7a6631caa087d9868180d8778a726682fd name==tos-gate ∧ conclusion==success 인 run 부재 (check_runs=1) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (R2)-a seam — 서버 3중은 충족이나 로컬 <head>:.github/workflows/tos-gate.yml 부재 (PR head = 워크플로 없는 커밋) → UNVERIFIED_REVISION (검사 생략 금지) ##########
PR head(워크플로 없음)=bf4153c10f1ebf8d53c6219de98457b0399fdbe6 d=5cad142092d2ce53e9b2429b6ce3667433346047
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 5cad142 D0-A: introduce config/tos_completion.yaml
  * bf4153c P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 85194dd seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-nowf bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-nowf capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.CbWg4ZAYbt
U17-A00 apps/github-actions  utc=2026-08-18T19:03:10Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:10Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:10Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:10Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:10Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=bf4153c10f1ebf8d53c6219de98457b0399fdbe6 P_last=bf4153c10f1ebf8d53c6219de98457b0399fdbe6 |D|=1 D=5cad142092d2ce53e9b2429b6ce3667433346047 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/5cad142092d2ce53e9b2429b6ce3667433346047/pulls  utc=2026-08-18T19:03:11Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"bf4153c10f1ebf8d53c6219de98457b0399fdbe6"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/bf4153c10f1ebf8d53c6219de98457b0399fdbe6/check-runs  utc=2026-08-18T19:03:11Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"bf4153c10f1ebf8d53c6219de98457b0399fdbe6","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"bf4153c10f1ebf8d53c6219de98457b0399fdbe6","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:03:11Z  http=200
  | {"id":777001,"head_sha":"bf4153c10f1ebf8d53c6219de98457b0399fdbe6","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:03:11Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"bf4153c10f1ebf8d53c6219de98457b0399fdbe6","check_suite_id":777001,"conclusion":"success"}]}
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=5cad142092d2ce53e9b2429b6ce3667433346047 head=bf4153c10f1ebf8d53c6219de98457b0399fdbe6 git show <head>:.github/workflows/tos-gate.yml 실패(파일 부재·커밋 부재) — 검사 생략 금지
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=5cad142092d2ce53e9b2429b6ce3667433346047 head=bf4153c10f1ebf8d53c6219de98457b0399fdbe6 git show <head>:.github/workflows/tos-gate.yml 실패(파일 부재·커밋 부재) — 검사 생략 금지 [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (R2)-b seam — 워크플로 파일은 있으나 두 리터럴 부재 → UNVERIFIED_REVISION ##########
W(리터럴 없음)=7ad82f37fc454d597fd638c11d2dc27793cf30fd d=2ed94c97519c59fa29f0a001f49bddafebe2d48d
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 2ed94c9 D0-A: introduce config/tos_completion.yaml
  * 7ad82f3 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * 9e4b1ef P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 78e10dc seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-nolit bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-nolit capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.oMPHDcz9lm
U17-A00 apps/github-actions  utc=2026-08-18T19:03:12Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:12Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:12Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:12Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:12Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=9e4b1ef2969dfabcadae957d596678fcfe7d7a33 P_last=9e4b1ef2969dfabcadae957d596678fcfe7d7a33 |D|=1 D=2ed94c97519c59fa29f0a001f49bddafebe2d48d 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/2ed94c97519c59fa29f0a001f49bddafebe2d48d/pulls  utc=2026-08-18T19:03:12Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"7ad82f37fc454d597fd638c11d2dc27793cf30fd"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/7ad82f37fc454d597fd638c11d2dc27793cf30fd/check-runs  utc=2026-08-18T19:03:12Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"7ad82f37fc454d597fd638c11d2dc27793cf30fd","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"7ad82f37fc454d597fd638c11d2dc27793cf30fd","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:03:13Z  http=200
  | {"id":777001,"head_sha":"7ad82f37fc454d597fd638c11d2dc27793cf30fd","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:03:13Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"7ad82f37fc454d597fd638c11d2dc27793cf30fd","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 git show 7ad82f37fc454d597fd638c11d2dc27793cf30fd:.github/workflows/tos-gate.yml  (blob bc3683291a33533abe0125fab2687e9620bf756e)
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - run: echo no-harness-here
U17-B5 grep: tools/tos_entry_harness.sh → 0회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 0회
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=2ed94c97519c59fa29f0a001f49bddafebe2d48d head=7ad82f37fc454d597fd638c11d2dc27793cf30fd 워크플로 blob 에 리터럴 부재 (harness path=0 sha256=0)
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=2ed94c97519c59fa29f0a001f49bddafebe2d48d head=7ad82f37fc454d597fd638c11d2dc27793cf30fd 워크플로 blob 에 리터럴 부재 (harness path=0 sha256=0) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (9)-a — P_first → W → d → 아티팩트 편집(P_last 가 d 이후) → ARTIFACT_MUTATED (서버는 seam 전 조건 충족 · git 구조는 live) ##########
P_first=2cb7ae2885a653a400b3053a4949e3211db38341 W=c8d735b8776a82976ca9f9107e50c5c733295002 d=773257252d928719909efa4e6b0ded38b5734e89 P_edit=ff6f496459ef52359956badd0762bc5433283763
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  | note: post-start edit (SIMULATED)
  * ff6f496 P-edit: artifact edited AFTER D0-A start
  * 7732572 D0-A: introduce config/tos_completion.yaml
  * c8d735b W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * 2cb7ae2 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 49b7080 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-mut bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-mut capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.f3z6kBAuNM
U17-A00 apps/github-actions  utc=2026-08-18T19:03:14Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:14Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:14Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:14Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:14Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=2cb7ae2885a653a400b3053a4949e3211db38341 P_last=ff6f496459ef52359956badd0762bc5433283763 |D|=1 D=773257252d928719909efa4e6b0ded38b5734e89 
U17-fire PREVENTION_ARTIFACT_MUTATED: ∀d P_first⊰d 이나 ∃d∈D: P_last=ff6f496459ef52359956badd0762bc5433283763 ⋠ d — 착수 «후» 아티팩트 변경
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/773257252d928719909efa4e6b0ded38b5734e89/pulls  utc=2026-08-18T19:03:14Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"c8d735b8776a82976ca9f9107e50c5c733295002"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c8d735b8776a82976ca9f9107e50c5c733295002/check-runs  utc=2026-08-18T19:03:14Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c8d735b8776a82976ca9f9107e50c5c733295002","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c8d735b8776a82976ca9f9107e50c5c733295002","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:03:14Z  http=200
  | {"id":777001,"head_sha":"c8d735b8776a82976ca9f9107e50c5c733295002","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:03:14Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c8d735b8776a82976ca9f9107e50c5c733295002","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 git show c8d735b8776a82976ca9f9107e50c5c733295002:.github/workflows/tos-gate.yml  (blob 0aefd2ab57db63d19548f877328f66bef3a45100)
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: verify harness identity
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  |       - name: run entry harness
  |         run: bash tools/tos_entry_harness.sh
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B d=773257252d928719909efa4e6b0ded38b5734e89 head=c8d735b8776a82976ca9f9107e50c5c733295002 merged_at=2026-08-19T00:10:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob(2 리터럴) 전부 일치
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=∀d P_first⊰d 이나 ∃d∈D: P_last=ff6f496459ef52359956badd0762bc5433283763 ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (9)-b — 편집 후 원복(내용은 P_first 와 동일) → P_last = 원복 커밋(d 이후) → ARTIFACT_MUTATED ##########
P_revert=4902f37876d6e35925aeade6fe6a00af46c4f561 (blob == P_first blob: yes)
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 4902f37 P-revert: restore artifact content (still after d)
  * ff6f496 P-edit: artifact edited AFTER D0-A start
  * 7732572 D0-A: introduce config/tos_completion.yaml
  * c8d735b W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * 2cb7ae2 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 49b7080 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-mut bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-mut capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.0Thp4MhBKe
U17-A00 apps/github-actions  utc=2026-08-18T19:03:15Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:15Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:15Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:15Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:15Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=2cb7ae2885a653a400b3053a4949e3211db38341 P_last=4902f37876d6e35925aeade6fe6a00af46c4f561 |D|=1 D=773257252d928719909efa4e6b0ded38b5734e89 
U17-fire PREVENTION_ARTIFACT_MUTATED: ∀d P_first⊰d 이나 ∃d∈D: P_last=4902f37876d6e35925aeade6fe6a00af46c4f561 ⋠ d — 착수 «후» 아티팩트 변경
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/773257252d928719909efa4e6b0ded38b5734e89/pulls  utc=2026-08-18T19:03:16Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"c8d735b8776a82976ca9f9107e50c5c733295002"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c8d735b8776a82976ca9f9107e50c5c733295002/check-runs  utc=2026-08-18T19:03:16Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c8d735b8776a82976ca9f9107e50c5c733295002","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c8d735b8776a82976ca9f9107e50c5c733295002","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:03:16Z  http=200
  | {"id":777001,"head_sha":"c8d735b8776a82976ca9f9107e50c5c733295002","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:03:16Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c8d735b8776a82976ca9f9107e50c5c733295002","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 git show c8d735b8776a82976ca9f9107e50c5c733295002:.github/workflows/tos-gate.yml  (blob 0aefd2ab57db63d19548f877328f66bef3a45100)
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: verify harness identity
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  |       - name: run entry harness
  |         run: bash tools/tos_entry_harness.sh
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B d=773257252d928719909efa4e6b0ded38b5734e89 head=c8d735b8776a82976ca9f9107e50c5c733295002 merged_at=2026-08-19T00:10:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob(2 리터럴) 전부 일치
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=∀d P_first⊰d 이나 ∃d∈D: P_last=4902f37876d6e35925aeade6fe6a00af46c4f561 ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (9)-c 대조 — «최초 도입 P 만 보는 구현»(v2.17) 은 (9)-a/b 를 통과시킨다 ##########
  P_first=2cb7ae2885a653a400b3053a4949e3211db38341 ⊰ d=773257252d928719909efa4e6b0ded38b5734e89 ? yes → v2.17: (c) 통과 → ACTIVE (사후 편집 허용) / v2.18: P_last=4902f37876d6e35925aeade6fe6a00af46c4f561 ⋠ d → ARTIFACT_MUTATED

########## T-84 (9)-d — P_first ⋠ d (W → d → P) → LATE (전순서 6 < 7) ##########
W=bd689e05065b8ba1af0e0a24b885706d37389ec8 d=b5dbf8f776cdd13c4c5d24d02a5a9783a4eb8f16 P_first=0bc65e2a6dd9f5268cdacbf1164d617ce7083467
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0bc65e2 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * b5dbf8f D0-A: introduce config/tos_completion.yaml
  * bd689e0 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
  * 25b346d seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-late bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/rev-late capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.A8PLgSZxer
U17-A00 apps/github-actions  utc=2026-08-18T19:03:17Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:17Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:17Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:17Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:17Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=0bc65e2a6dd9f5268cdacbf1164d617ce7083467 P_last=0bc65e2a6dd9f5268cdacbf1164d617ce7083467 |D|=1 D=b5dbf8f776cdd13c4c5d24d02a5a9783a4eb8f16 
U17-fire PREVENTION_LATE: ∃d∈D: P_first=0bc65e2a6dd9f5268cdacbf1164d617ce7083467 ⋠ d — 기록이 착수보다 늦다
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/b5dbf8f776cdd13c4c5d24d02a5a9783a4eb8f16/pulls  utc=2026-08-18T19:03:18Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"bd689e05065b8ba1af0e0a24b885706d37389ec8"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/bd689e05065b8ba1af0e0a24b885706d37389ec8/check-runs  utc=2026-08-18T19:03:18Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"bd689e05065b8ba1af0e0a24b885706d37389ec8","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"bd689e05065b8ba1af0e0a24b885706d37389ec8","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T19:03:18Z  http=200
  | {"id":777001,"head_sha":"bd689e05065b8ba1af0e0a24b885706d37389ec8","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-18T19:03:18Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"bd689e05065b8ba1af0e0a24b885706d37389ec8","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 git show bd689e05065b8ba1af0e0a24b885706d37389ec8:.github/workflows/tos-gate.yml  (blob 0aefd2ab57db63d19548f877328f66bef3a45100)
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: verify harness identity
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  |       - name: run entry harness
  |         run: bash tools/tos_entry_harness.sh
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B d=b5dbf8f776cdd13c4c5d24d02a5a9783a4eb8f16 head=bd689e05065b8ba1af0e0a24b885706d37389ec8 merged_at=2026-08-19T00:10:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob(2 리터럴) 전부 일치
prevention_control_state=PREVENTION_LATE
reason=∃d∈D: P_first=0bc65e2a6dd9f5268cdacbf1164d617ce7083467 ⋠ d — 기록이 착수보다 늦다 [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 (4) stub 시퀀스 — t0 seam ACTIVE → t1 해제(404) → t2 약화 → t3 live gh ##########
== t0
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 5a53fa1 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 18e0c1d seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.kkMd3Q9Lsa
U17-A00 apps/github-actions  utc=2026-08-18T19:03:19Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:19Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:19Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:19Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:19Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=5a53fa1d502e397c43440d42b1ef4d5445b4752f P_last=5a53fa1d502e397c43440d42b1ef4d5445b4752f |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=0 · app/suite/workflow path/blob 2 리터럴) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active
u17_rc=0
== t1
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 5a53fa1 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 18e0c1d seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/released-absent bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/released-absent capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OH5swo0q0i
U17-A00 apps/github-actions  utc=2026-08-18T19:03:19Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:19Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:19Z  http=404
  | {"message":"Branch not protected","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:19Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:19Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ABSENT
u17_live_reason=protection 404 ∧ 적용 규칙 0 (룰셋 목록=0)
U17-fire PREVENTION_ABSENT: (a) protection 404 ∧ 적용 규칙 0 (룰셋 목록=0)
P_first=5a53fa1d502e397c43440d42b1ef4d5445b4752f P_last=5a53fa1d502e397c43440d42b1ef4d5445b4752f |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_ABSENT
reason=(a) protection 404 ∧ 적용 규칙 0 (룰셋 목록=0) [수집 1건 중 전순서 최소]
u17_rc=1
== t2
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 5a53fa1 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 18e0c1d seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/insufficient bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/insufficient capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.vzqYmJxriF
U17-A00 apps/github-actions  utc=2026-08-18T19:03:20Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:20Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:20Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"enforce_admins":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:20Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:20Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=5a53fa1d502e397c43440d42b1ef4d5445b4752f P_last=5a53fa1d502e397c43440d42b1ef4d5445b4752f |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1
== t3
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 5a53fa1 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
  * 18e0c1d seed
$ U17_RESPONDER=gh bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.LjoVzT7b3t
U17-A00 apps/github-actions  utc=2026-08-18T19:03:22Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:22Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:22Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:23Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:23Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:03:24Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=5a53fa1d502e397c43440d42b1ef4d5445b4752f P_last=5a53fa1d502e397c43440d42b1ef4d5445b4752f |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 부속 — countersign 형식 위반 → UNSIGNED (전순서 3; seam ACTIVE 하) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: APPROVED (no ISO)
  * 4dbc1c7 P: bad countersign
  * d5a66de seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active bash u17-verify-v218.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam218/active capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.HVfG1Cdmeg
U17-A00 apps/github-actions  utc=2026-08-18T19:03:25Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:25Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치
U17-fire PREVENTION_UNSIGNED: operator_countersign 값 형식 위반: operator_countersign: APPROVED (no ISO)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:25Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:25Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:25Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=4dbc1c78b98f80a7f7900a916fb4be802ff841a0 P_last=4dbc1c78b98f80a7f7900a916fb4be802ff841a0 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_UNSIGNED
reason=operator_countersign 값 형식 위반: operator_countersign: APPROVED (no ISO) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 부속 — 본 저장소 HEAD 에 실행기 적용 (원격 == 핀 · 아티팩트 부재 → ABSENT · (a) 는 live INSUFFICIENT 도 수집되나 전순서 2 가 5 를 앞선다) ##########
$ bash u17-verify-v218.sh <repo>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gYZnEeD4ni
U17-A00 apps/github-actions  utc=2026-08-18T19:03:27Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:03:27Z  http=200  (.default_branch=main)
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:03:27Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:03:28Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:03:28Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:03:29Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=∅ P_last=∅ |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1
(t84v218.sh exit=0)
```

픽스처 DAG (조립 시점 재확인 · `git -C $SP/fx84x/<n> log --graph --oneline --all` · 원격 병기):

```text
== fx84x/live-main  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* c2942b9 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* 2234031 seed
== fx84x/mm-branch  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* ca02767 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* c270e44 seed
== fx84x/mm-repo  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 19a9d77 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* 4c76a83 seed
== fx84x/host-gitlab  (remotes: origin=https://gitlab.com/kakao-harris-lee/kis_unified_sts.git )
* c199f35 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* c681b53 seed
== fx84x/host-owner  (remotes: origin=git@github.com:octocat/kis_unified_sts.git )
* ed7a1e7 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* 72e7c32 seed
== fx84x/host-two  (remotes: fork=git@github.com:kakao-harris-lee/kis_unified_sts.git upstream=https://gitlab.com/kakao-harris-lee/kis_unified_sts.git )
* 6a372f0 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* 50992e0 seed
== fx84x/seam  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* c5b9f94 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* c2dc6f4 seed
== fx84x/rev-live  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* bbe2396 D0-A: introduce config/tos_completion.yaml
* 1d42911 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
* 4b2a1e4 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* c65c82a seed
== fx84x/rev-seam  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 0863c2d D0-A: introduce config/tos_completion.yaml
* 8b244a7 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
* d6f1f9e P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* cd635de seed
== fx84x/rev-nowf  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 5cad142 D0-A: introduce config/tos_completion.yaml
* bf4153c P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* 85194dd seed
== fx84x/rev-nolit  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 2ed94c9 D0-A: introduce config/tos_completion.yaml
* 7ad82f3 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
* 9e4b1ef P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* 78e10dc seed
== fx84x/mut  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 4902f37 P-revert: restore artifact content (still after d)
* ff6f496 P-edit: artifact edited AFTER D0-A start
* 7732572 D0-A: introduce config/tos_completion.yaml
* c8d735b W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
* 2cb7ae2 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* 49b7080 seed
== fx84x/late  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 0bc65e2 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* b5dbf8f D0-A: introduce config/tos_completion.yaml
* bd689e0 W: add .github/workflows/tos-gate.yml (SIMULATED workflow with harness path + sha256 literals)
* 25b346d seed
== fx84x/seq  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 5a53fa1 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + contract pin)
* 18e0c1d seed
== fx84x/unsigned  (remotes: origin=https://github.com/kakao-harris-lee/kis_unified_sts.git )
* 4dbc1c7 P: bad countersign
* d5a66de seed
```

## 4. 관측·정직 기록·계약 결함 후보 (고치지 않는다 — bound_paths 동결)

1. **⑤ 와 U-17 서술의 긴장(정밀화 후보)**: C3 는 «canonical_target 은 아티팩트 파라미터가 아니다 — 아티팩트는 이것을 선언하지 않는다» 라 적고, 같은 U-17 머리(5055-5058)와 §8 ⑤ 는 아티팩트가
   owner/repo·대상 브랜치를 «선언» 하고 그 선언이 핀과 다르면 `TARGET_MISMATCH` 라 적는다. 실행기는 후자로 읽어 선언값을 «대조 대상» 으로 두었고(부재 시 ∅ ≠ 핀 → MISMATCH), ⑤-a/b 가 그대로 red 다.
   «선언 키를 두는가/필수인가» 를 계약 리터럴 한 줄로 고정하면 구현 독립이 된다.
2. **⑩ 원격 «존재» 대조의 범위**: 핀 일치 원격이 하나라도 있으면 통과(⑩-c 는 gitlab 동일 경로 `upstream` + 핀 ssh 형 `fork` 로 통과). 계약이 «존재» 라 적었으므로 그대로 읽었다 — 비-핀 원격의 «공존» 을
   금지하려면 별도 문언이 필요하다(현재는 관측만).
3. **R2 로컬 blob 검사의 전제**: PR head 커밋이 판정 저장소에 «있어야» 한다. 실 저장소 실측(③-0): PR#636 head `7656259d` 는 squash 착지라 로컬에 없다(`git show` 가 «path does not exist» 문구를 내지만
   `cat-file -e` 는 객체 부재 — 어느 쪽이든 rc≠0 → UNVERIFIED_REVISION). 정직한 착지에서도 판정 저장소가 PR head 를 fetch 하지 않으면 red 가 된다 — 계약은 «부재 = UNVERIFIED_REVISION(검사 생략 금지)» 라
   적었으므로 극성은 계약 그대로이나, **운영 절차상 «PR head 커밋 보유»가 판정 전제**임을 문언으로 두는 편이 정직하다(정밀화 후보).
4. **⑦ 대조·⑧ 대조·⑨-c 대조·⑩-d 대조**: 각각 v2.17 술어(name-only / app-id-only / P_first-only / host-drop)로 같은 캡처를 재평가한 값을 병기했다 — 넷 다 v2.17 은 통과, v2.18 은 red. 이것이 이 판이 닫은 표면이다.
5. **live 음성·seam 양성 성격 불변**: ①·⑤·⑩·④-t3 는 인증 실 조회, ACTIVE 는 전부 SIMULATED. 워크플로 blob 은 픽스처 커밋에 «실재» 하나 그 CI 잡이 서버에서 돌지는 않았다(seam). 룰셋 `protect_main` disabled 관측 그대로.
6. **수집 후 방출의 관측**: ⑤·⑩·본 저장소 run 에서 하위 순위 상태(INSUFFICIENT)도 `U17-fire` 로 함께 기록되고 방출은 전순서 최소 — 운영자가 «다음에 무엇이 남는가»를 같은 run 에서 본다(부수 효과).
7. 본 저장소 무접촉·설정 변경 0·worktree 미사용 — §5 사후 재조회로 실행 전후 동일 확인. **S-24**: 최종 동결 `5f4b7cfd` 에 결속(§5 원문 — 워킹트리 blob == 5f4b7cfd blob · 후속 계약 커밋 0 · 하니스 `957bf49d…`).

## 5. 사후 검증 원문 (repo 무영향 · 서버 설정 무변경 · S-24 결속 · 본 저장소 NOT_STARTED/PREVENTION_ABSENT/REBINDING_REQUIRED)

```text
=== 사후 검증 (2026-08-18T19:04:12Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               5f4b7cfd [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
5f4b7cfd docs(tos): phase0 completion contract v2.18 — contract-pinned target, derived Actions app id, workflow identity, artifact blob binding
-- 실행 전 스냅샷 대조 --
status/HEAD: 실행 전과 byte-동일
-- 이 사이클은 worktree 미사용(픽스처 = scratchpad 독립 repo) — 본 저장소에 모의 커밋 0 --
       3
-- 본 저장소 D0-A 미착수 불변 --
ls: config/tos_completion.yaml: No such file or directory
(도입 커밋 출력 없음 = 미착수)
-- 본 저장소 U-17 아티팩트 부재 (진실 원천은 서버이나 파라미터 선언·기록은 아티팩트) --
absent (HEAD 트리)
$ bash u15g-exec215e.sh <repo>
d0a_entry_provenance_state=NOT_STARTED
reason=|D| = 0
exec_rc=0
$ bash u17-verify-v218.sh <repo>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ynmpYCRB58
U17-A00 apps/github-actions  utc=2026-08-18T19:04:49Z  http=200
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T19:04:49Z  http=200  (.default_branch=main)
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T19:04:49Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T19:04:50Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T19:04:50Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T19:04:51Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=∅ P_last=∅ |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1
$ bash harness218.sh (본 저장소 현행)
R-0 head=5f4b7cfd66215d0ddeea56733b24855674a1807b
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
host-gitlab host-owner host-two late live-main mm-branch mm-repo mut rev-live rev-nolit rev-nowf rev-seam seam seq unsigned 
(wt/ 비어 있음)
-- S-24 결속: 계약 워킹트리 == 최종 동결 5f4b7cfd blob · 하니스 블록 byte-동일 --
  HEAD=5f4b7cfd66215d0ddeea56733b24855674a1807b  contract blob(HEAD)=e225bc1ad6499f2225644f9c87ffdee28634f8ef  contract blob(5f4b7cfd)=e225bc1ad6499f2225644f9c87ffdee28634f8ef
  git diff --quiet 5f4b7cfd -- <계약>: 무차이 (워킹트리 == 5f4b7cfd)
  sha256(워킹트리 계약)=e66e9f85e42ca2721133a012460243536043b27436bee74bb408ddcd83936f97
  하니스 블록: git show 5f4b7cfd:<계약> | sed -n '4528,4628p' | shasum -a 256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  5f4b7cfd..HEAD 에 계약 문서 커밋 0 (에라타 없음 — 증거가 최종 동결에 결속)
```
