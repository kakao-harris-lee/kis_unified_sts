# U17-PREVENTION-CHECK-V217 — v2.17 T-84 ①~⑥ 실행 기록 (u17-verify · target 결속 live TARGET_MISMATCH · app_id 위조 seam · GET-only)

> **비규범 부속** — 계약 v2.17(`a3c95b4f`)도 U-17 증거 아티팩트의 경로·파일명을 규정하지 않는다(규정된 것은 실행기 `u17-verify`·run opener
> `U17-0 target=<owner>/<repo>@<branch>`·verbatim 캡처+UTC·8값/전순서 8단·`responder` 기록). v2.16 사이클의 sibling `U17-PREVENTION-CHECK.md`(`434448b2`)는
> (4d) 불변 규율을 준용해 편집하지 않고 이 파일을 새로 둔다. **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로 live 조회한다**(«진실 원천» 절) — 대조용.
> **서버 쓰기·설정 변경 0** — 전부 `gh api` GET(`-i`)이며 사후 재조회(§5)로 실행 전후 동일을 확인했다. 픽스처는 scratchpad 독립 git repo(원격 `origin` URL 만
> 로컬 config 로 설정 — 파생 원천 재현용, push/fetch 0).
- **생성 시각**: 2026-08-18T18:32:55Z (UTC) · 실행 시각 `t84v217_utc=` + 각 캡처 `utc=` · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트
- **동결 결속**: 계약 HEAD blob `6a0fdef4`(sha256 `7d83b3a3a91abc81a73ff1bab72ef24264124f02f206e0c1bc111fb9177180b3`, 6,864행) == `git show a3c95b4f:` (워킹트리 clean, §5).
  하니스 §12.3.4-R 블록(`git show a3c95b4f:<계약> | sed -n '4516,4616p'`) sha256 `957bf49d…` — v2.10~v2.16 과 byte-동일(본 저장소 현행 산출 `REBINDING_REQUIRED`).
- **실행기 결속**: sha256(u17-verify-v217.sh) = `451f805525078a9bfc30491f7f9f07cee47671656900b0d9d95817b32ea6ec7a` · sha256(t84v217.sh) =
  `663ca126a6281e73e55af579f80711d162f86dfba9083846c1e64da498702eb3` (원문 §1·§2). 파생 원천 실측(§3 (0)): `git remote get-url origin` =
  `https://github.com/kakao-harris-lee/kis_unified_sts.git` → `kakao-harris-lee/kis_unified_sts` · `repos/{o}/{r}.default_branch` = `main` · `apps/github-actions.id` = **15368**(계약 기본 gate_app_id 와 일치).
- **U-15 3단 가드(⑫·G-음성-2)** 는 v2.17 이 U-15 를 바꾸지 않았고(U-17·§8 T-84·§11 참조 전환만) 실행기 델타가 u17 뿐이라 재실행하지 않았다 — sibling `U15-ENTRY-CHECK-V216.md` 유효(한 줄 언급).
- **결과 요약 — 실행기 stdout·rc 원문 그대로 (해석 아님)**:

| 변이 | 구성 (아티팩트 선언 → 파생 대조 · responder) | 방출값 (`prevention_control_state=`) | rc | 기대 (§8 T-84 6종 · U-17-c 8단) | 대조 |
| --- | --- | --- | --- | --- | --- |
| **① live** | 선언 `kakao-harris-lee/kis_unified_sts`@`main` = 파생 · **`gh`** | **`PREVENTION_INSUFFICIENT`** — `classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]` · `U17-T declared-vs-derived: 일치` | 1 | ① «main → INSUFFICIENT» | **일치 (인증 실측)** |
| ① 부속 live 병기 | 작업 브랜치 `mission-critical-trading-operating-system` protection 원자료 | HTTP 404 «Branch not protected» (실행기 밖 raw probe) | — | ① «작업 브랜치 → ABSENT» 의 원자료 — **v2.17 실행기는 파생 target(default) 만 조회하므로 이 값은 u17-verify 로는 재현되지 않는다**(§4-1 보고) | 원자료 일치 |
| **⑤-a live** | 선언 `…@mission-critical-trading-operating-system`(비-default) · gh · D=∅ | **`PREVENTION_TARGET_MISMATCH`** — `target_branch(선언=… ≠ 파생=main)` | 1 | ⑤ «D=∅ 에서도 red» · 전순서 4 (INSUFFICIENT 5 보다 먼저) | **일치 (인증 live)** |
| **⑤-b live** | 선언 `octocat/Hello-World`@main(타 repo) · gh · D=∅ | **`PREVENTION_TARGET_MISMATCH`** — `owner_repo(선언=octocat/Hello-World ≠ 파생=kakao-harris-lee/kis_unified_sts)` | 1 | ⑤ (파생은 origin 에서 온다) | **일치** |
| ⑤-c seam | 선언 비-default + (a) seam ACTIVE | `PREVENTION_TARGET_MISMATCH` | 1 | «임의 대상의 보호만으로 ACTIVE» 차단(v2.16 은 이 구성에서 ACTIVE 였음) | **일치** |
| ② -i seam ACTIVE | 선언=파생 · `file:seam217/active` SIMULATED | `PREVENTION_ACTIVE` (D=∅ → (b)(c) 검증 대상 없음 · target 대조 일치 명시) | 0 | ② — 양성은 운영자 설정 전 실측 불가 | **일치 (모의)** |
| ② -ii/-iii/-iv seam | INSUFFICIENT 형태 / protection 500 / 응답 없음(`repos/{o}/{r}` 부터 실패) | `INSUFFICIENT` / `UNVERIFIABLE` / `UNVERIFIABLE`(opener `…@UNRESOLVED` — default_branch 파생 불가) | 1/1/1 | ② | **일치** |
| **③-0 live 병기** | 미푸시 HEAD `a3c95b4f` → 422 · 푸시 무-PR `be98f075` → `[]` · origin/main `11e382fc` → PR#636 head `7656259d` check-runs 5건(app.id 전부 15368·head_sha==PR head·check_suite `83489483104` → check-suites: head_sha 일치·app.id 15368) **`tos-gate` 없음** | (원자료) | — | ③ «422 → UNVERIFIABLE / tos-gate 부재 → UNVERIFIED_REVISION» 의 원자료 — **계약 #5 정정문(15건·PR head 5건)과 정합** | **일치** |
| ③-a mixed | (a) seam ACTIVE · (b) live: 픽스처 d 는 GitHub 에 없음 | `PREVENTION_UNVERIFIABLE` (`(b) d=… http=422`) | 1 | ③ | **일치** |
| ③-b seam (b) 양성 | pulls → merged PR(base main) · head check-run {tos-gate, success, **app.id 15368**, head_sha==head, check_suite 777001} · check-suites/777001 {head_sha 일치, app.id 15368} | `PREVENTION_ACTIVE` — `name/conclusion/app.id=15368/head_sha/check_suite 전부 일치` | 0 | (b) 충족 (모의) | **일치 (모의)** |
| **⑥ seam app_id 위조** | tos-gate·success 이지만 `app.id=99999`(제3자 앱) | **`PREVENTION_UNVERIFIED_REVISION`** — `app.id=99999≠15368(위조 표면)` | 1 | ⑥ | **일치** — 대조 «이름·결론만 보는 구현»: **PASS(green — 위조 통과)** / app.id view: red |
| ⑥-b seam | head_sha 불일치(다른 커밋의 success 를 끌어옴) | `PREVENTION_UNVERIFIED_REVISION` (`head_sha=2222…≠PR head`) | 1 | (b) `head_sha == PR head.sha` | **일치** |
| ⑥-c seam | check_suite 귀속 불일치(suite 의 head_sha 상이) | `PREVENTION_UNVERIFIED_REVISION` (`check_suite 귀속 불일치`) | 1 | (b) check_suite 귀속 | **일치** |
| **④ stub 시퀀스** | t0 seam ACTIVE → t1 해제 404 → t2 약화 → t3 live gh | `ACTIVE`/0 → `ABSENT`/1 → `INSUFFICIENT`/1 → `INSUFFICIENT`/1 | | ④ | **일치** |
| 부속 LATE / UNSIGNED | d 먼저·P 나중 + seam 충족 / countersign 형식 위반 + 선언 불일치 | `PREVENTION_LATE` / `PREVENTION_UNSIGNED`(전순서 3 < 4 — 선언 불일치보다 먼저) | 1/1 | (c) / (c-0) E3 리터럴 복원 | **일치** |
| (본 저장소) | HEAD `a3c95b4f` — 아티팩트 부재 | `PREVENTION_ABSENT` | 1 | «현재 평가» | **일치** |

이 파일은 본 저장소의 `PREVENTION_ACTIVE` 를 주장하지 않는다 — live 관측값은 `INSUFFICIENT`(선언=파생) 와 `TARGET_MISMATCH`(선언≠파생)뿐이고 `ACTIVE` 는 전부 `SIMULATED` seam 이다.

---

## 1. u17-verify (v2.17) 실행기 — 원문 + 독해 선언 (sha256 `451f805525078a9bfc30491f7f9f07cee47671656900b0d9d95817b32ea6ec7a`)

독해 선언(계약이 리터럴로 고정하지 않은 자리 · v2.16 실행기 대비 델타):
- **[B1] 구조 파생**: `owner_repo` ← `git remote get-url <remote_name>`(아티팩트 키 `remote_name:`, 기본 `origin`) 를 정규화(`https://host/`·`ssh://git@host/`·`git@host:` 접두 제거·`.git` 제거) ·
  `target_branch` ← `repos/{o}/{r}` 의 `.default_branch`(A0 캡처 · responder 경유라 seam 주입 가능). 원격 부재·URL 정규화 실패·A0 실패 → `PREVENTION_UNVERIFIABLE`(조회 대상 미정 · opener 는
  `U17-0 target=<o>/<r>@UNRESOLVED` 로 연다). **아티팩트 선언값(`owner_repo:`·`target_branch:`)은 대조 대상** — `U17-T declared-vs-derived:` 라인에 원문 기록 · 불일치 = `PREVENTION_TARGET_MISMATCH`
  (전순서 4 · D 와 무관 · countersign(3) 뒤·INSUFFICIENT(5) 앞). (a) 4 엔드포인트는 **파생 target** 에 대해 조회한다.
- **(b) 강화**: 후보 run = `name==check ∧ conclusion=="success" ∧ app.id==gate_app_id(아티팩트 키 `gate_app_id:`, 기본 15368) ∧ head_sha==PR head.sha` → 그 run 의 `check_suite.id` 로
  `check-suites/{id}` 를 조회(B3 캡처)해 `head_sha==PR head.sha ∧ app.id==gate_app_id` 일 때만 귀속 일치. 3중 일치(파생 owner_repo·target ∧ PR base==target)는 (b) 의 `base.ref==target` 이 담당.
- **(α)** 룰셋 `created_at/updated_at` 를 `U17-α` 라인으로 기록하고, D≠∅ 이고 merged_at(min D) 가 있으면 UTC 정규화 후 «≤ / >» 를 **관측 기록**으로만 남긴다(차단 아님).
- **(c-0)** E3 리터럴(`operator_countersign: "<식별> <ISO-8601 UTC>"` 정확히 1회) · **(c)** `∀d∈D: P ⊰ d`(P·D 구조 정의 · 후보는 `--full-history` 로 좁힘 — 완전성 논증은 v2.16 sibling §1).
- 술어(a)·responder seam·트랩·성공 경로는 v2.16 실행기와 동일(계약 E3 마감 리터럴 그대로: `allow_force_pushes/allow_deletions` 키 부재 = 불충족 · `restrictions.apps==[]` · `bypass_actors` 키 부재 = 불충족).

```bash
#!/usr/bin/env bash
# u17-verify (v2.17) — U-17 «예방 통제 활성 증거» 실행기 (계약 a3c95b4f §12.3.4 U-17 (a)(b)(c)(c-0)·B1 target 결속·B2 app.id·(α) 룰셋 시각 관측·U-17-c 8값/전순서 8단)
#   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=<owner>/<repo>@<branch>` 라인이 연다. CORR 은 이 run 을 보지 않는다.
#
#   [B1] 진실은 구조 파생: owner_repo = `git remote get-url <remote_name>`(기본 origin) 정규화 · target_branch = `gh api repos/{o}/{r}` 의 .default_branch.
#        아티팩트(tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md · HEAD 커밋 내용) 의 선언값은 «대조 대상» — 불일치 = PREVENTION_TARGET_MISMATCH(전순서 4 · D 와 무관한 무조건 항).
#        아티팩트 키: owner_repo · target_branch · tos_gate_check(기본 tos-gate) · gate_app_id(기본 15368 = GitHub Actions) · remote_name(기본 origin) · operator_countersign
#   responder seam: U17_RESPONDER=gh(기본 · `gh api -i`) | file:<dir>(주입 · SIMULATED) | mixed:<dir>(주입 있으면 파일, 없으면 gh) — 캡처 → 상태값 함수는 responder 무관 동일 코드 경로.
#   (a) live: repos/{o}/{r}(default_branch) · protection · rules/branches · rulesets · rulesets/{id} 캡처(verbatim+UTC) → 술어(E3 리터럴 포함) → ACTIVE|ABSENT|INSUFFICIENT|UNVERIFIABLE
#   (b) ∀d∈D(구조 정의): commits/{d}/pulls → merged ∧ base==target 인 PR → commits/{head.sha}/check-runs 에 name==check ∧ conclusion==success ∧ app.id==gate_app_id ∧ head_sha==PR head.sha
#       ∧ check_suite 귀속(check-suites/{id} 의 head_sha==PR head.sha ∧ app.id==gate_app_id) 인 run 실재.  D=∅ → «검증 대상 없음»(명시).
#   (α) 룰셋 created_at/updated_at 캡처 + merged_at(min D) 대조 «관측 기록»(차단 아님).  (c-0) countersign E3 리터럴.  (c) ∀d∈D: P ⊰ d.
#   전순서: 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 TARGET_MISMATCH > 5 INSUFFICIENT > 6 LATE > 7 UNVERIFIED_REVISION > 8 ACTIVE.  exit 0 = ACTIVE 만. trap EXIT 폐쇄.
# 사용: bash u17-verify-v217.sh [<repo-dir>]      (env: U17_RESPONDER · U17_CAPTURE_DIR)
set -u -o pipefail
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

# ── 아티팩트 (전순서 2 ABSENT · 파라미터/선언값) — 커밋-전용 읽기
BODY=$(git show "HEAD:$PC" 2>/dev/null) || emit PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"
yv() { printf '%s\n' "$BODY" | sed -n "s/^$1:[[:space:]]*//p" | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//' | head -1; }
DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch); CHECK=$(yv tos_gate_check); [ -n "$CHECK" ] || CHECK=tos-gate
APPID=$(yv gate_app_id); [ -n "$APPID" ] || APPID=15368
REMOTE=$(yv remote_name); [ -n "$REMOTE" ] || REMOTE=origin

# ── [B1] 구조 파생 ① owner_repo ← git remote get-url <remote>
URL=$(git remote get-url "$REMOTE" 2>/dev/null) || emit PREVENTION_UNVERIFIABLE "원격 '$REMOTE' 의 URL 을 파생할 수 없다(git remote get-url 실패) — 조회 대상 미정"
OWNER_REPO=$(printf '%s' "$URL" | sed -E 's#^(https?://[^/]+/|ssh://git@[^/]+/|git@[^:]+:)##; s#\.git$##; s#/$##')
case "$OWNER_REPO" in */*) ;; *) emit PREVENTION_UNVERIFIABLE "원격 URL 정규화 실패: '$URL' → '$OWNER_REPO'" ;; esac

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
    j=json.load(open(sys.argv[1]));
    for kk in sys.argv[2].split("."):
        j=j[int(kk)] if isinstance(j,list) else j[kk]
    print(j if not isinstance(j,(dict,list)) else json.dumps(j))
except Exception: print("")' "$CAP/$(key "$1").body" "$2" 2>/dev/null; }

# ── [B1] 구조 파생 ② target_branch ← repos/{o}/{r}.default_branch  (A0)
P_REPO="repos/$OWNER_REPO"
respond "$P_REPO"; ST0=$(cat "$CAP/$(key "$P_REPO").status")
[ "$ST0" != ERR ] && printf '%s' "$ST0" | grep -Eq '^2' || { printf 'U17-0 target=%s@UNRESOLVED\nU17-A0 %s  utc=%s  http=%s\n' "$OWNER_REPO" "$P_REPO" "$(utc)" "$ST0"; sed 's/^/  | /' "$CAP/$(key "$P_REPO").body"; emit PREVENTION_UNVERIFIABLE "repos/{o}/{r} 조회 실패(http=$ST0) — default_branch 파생 불가"; }
TARGET=$(jget "$P_REPO" default_branch); [ -n "$TARGET" ] || { printf 'U17-0 target=%s@UNRESOLVED\n' "$OWNER_REPO"; emit PREVENTION_UNVERIFIABLE "default_branch 파생 불가(응답에 없음)"; }
printf 'U17-0 target=%s@%s\n' "$OWNER_REPO" "$TARGET"
printf 'U17-0 derived: owner_repo=%s (remote=%s url=%s) target_branch=%s (.default_branch) | declared: owner_repo=%s target_branch=%s | check=%s gate_app_id=%s responder=%s artifact@%s capture_dir=%s\n' \
  "$OWNER_REPO" "$REMOTE" "$URL" "$TARGET" "${DECL_OR:-∅}" "${DECL_TB:-∅}" "$CHECK" "$APPID" "$RESP" "$(git rev-parse --short HEAD)" "$CAP"
printf 'U17-A0 %s  utc=%s  http=%s  (.default_branch=%s)\n' "$P_REPO" "$(utc)" "$ST0" "$TARGET"

# ── (a) 4 엔드포인트 캡처 (파생 target 에 대해)
P_PROT="repos/$OWNER_REPO/branches/$TARGET/protection"; P_RULES="repos/$OWNER_REPO/rules/branches/$TARGET"; P_RSETS="repos/$OWNER_REPO/rulesets"
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
for id in $RSIDS; do respond "repos/$OWNER_REPO/rulesets/$id"; show_capture A4 "repos/$OWNER_REPO/rulesets/$id"; done
[ -n "$RSIDS" ] || printf 'U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)\n'
# (α) 룰셋 created_at/updated_at 관측 기록 (차단 아님)
for id in $RSIDS; do printf 'U17-α ruleset %s created_at=%s updated_at=%s enforcement=%s (관측 기록 — merged_at(min D) 대조는 (b) 후)\n' "$id" "$(jget "repos/$OWNER_REPO/rulesets/$id" created_at)" "$(jget "repos/$OWNER_REPO/rulesets/$id" updated_at)" "$(jget "repos/$OWNER_REPO/rulesets/$id" enforcement)"; done

# ── 캡처 → (a) 상태값 (결정적 함수)
A_STATE=$(python3 - "$CAP" "$OWNER_REPO" "$TARGET" "$CHECK" <<'PY'
import json,sys,os
cap,orepo,target,check=sys.argv[1:5]
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
                if p.get("strict_required_status_checks_policy") is True and any(c.get("context")==check for c in p.get("required_status_checks") or []): return True
        return False
    if not rsc_ok(): rs_why.append(f"required_status_checks{{strict,context∋{check}}} 없음")
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
[ -n "$A_STATE" ] || emit PREVENTION_UNVERIFIABLE "(a) 캡처 평가 함수가 값을 내지 못함(파서 오류)"
A_VAL=${A_STATE%%|*}; A_WHY=${A_STATE#*|}
printf 'u17_live_state=%s\nu17_live_reason=%s\n' "$A_VAL" "$A_WHY"
[ "$A_VAL" != PREVENTION_UNVERIFIABLE ] || emit PREVENTION_UNVERIFIABLE "(a) $A_WHY"
[ "$A_VAL" != PREVENTION_ABSENT ]       || emit PREVENTION_ABSENT "(a) $A_WHY"

# ── (c-0) countersign 형식 (전순서 3 UNSIGNED — E3 리터럴 `operator_countersign: "<식별> <ISO-8601 UTC>"` 정확히 1회)
CS_RE='^operator_countersign:[[:space:]]*"[^"[:space:]][^"]* [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"[[:space:]]*(#.*)?$'
nk=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:')
[ "$nk" = 1 ] || emit PREVENTION_UNSIGNED "operator_countersign 키 출현 횟수=$nk (정확히 1 요구)"
printf '%s\n' "$BODY" | grep -Eq "$CS_RE" || emit PREVENTION_UNSIGNED "operator_countersign 값 형식 위반: $(printf '%s\n' "$BODY" | grep '^operator_countersign:')"

# ── [B1] 전순서 4 TARGET_MISMATCH — 선언값 vs 구조 파생값 (D 와 무관한 무조건 항)
MM=""
[ "$DECL_OR" = "$OWNER_REPO" ] || MM="$MM owner_repo(선언=${DECL_OR:-∅} ≠ 파생=$OWNER_REPO)"
[ "$DECL_TB" = "$TARGET" ]     || MM="$MM target_branch(선언=${DECL_TB:-∅} ≠ 파생=$TARGET)"
printf 'U17-T declared-vs-derived: %s\n' "${MM:-일치}"
[ -z "$MM" ] || emit PREVENTION_TARGET_MISMATCH "아티팩트 선언값이 구조 파생값과 불일치:$MM"

# ── (a) 불충족 (전순서 5)
[ "$A_VAL" = PREVENTION_ACTIVE ] || emit PREVENTION_INSUFFICIENT "(a) $A_WHY"

# ── (c) 기록 순서 ∀d∈D: P ⊰ d (전순서 6) — P·D 구조 정의(경로 존재 ∧ 모든 부모에 부재; 후보 = --full-history 로 좁힘, 완전성 논증은 transcript)
intro_set() { local path="$1" out="" x p intro; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue; intro=1; for p in $(git log --format=%P -1 "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
P=$(intro_set "$PC" | awk '{print $NF}'); D=$(intro_set "$CFG"); ND=$(printf '%s\n' $D | grep -c .)
printf 'P=%s |D|=%s D=%s\n' "$P" "$ND" "$(printf '%s ' $D)"
for d in $D; do { git merge-base --is-ancestor "$P" "$d" && [ "$P" != "$d" ]; } || emit PREVENTION_LATE "P 가 d=$d 의 진 조상이 아님"; done

# ── (b) 리비전 특정 ∀d∈D (전순서 7) — D=∅ 는 «검증 대상 없음»(명시)
if [ "$ND" -eq 0 ]; then
  printf 'U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ target 대조 만으로 판정)\n'
else
  MINMERGED=""
  for d in $D; do
    respond "repos/$OWNER_REPO/commits/$d/pulls"; show_capture B1 "repos/$OWNER_REPO/commits/$d/pulls"
    HS=$(python3 - "$CAP" "$OWNER_REPO" "$d" "$TARGET" <<'PY'
import json,sys,os
cap,orepo,d,target=sys.argv[1:5]; k=f"repos/{orepo}/commits/{d}/pulls".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: prs=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|pulls 본문 파싱 실패"); sys.exit(0)
ok=[p for p in prs if isinstance(p,dict) and p.get("merged_at") and (p.get("base") or {}).get("ref")==target]
if not ok: print("UNVERIFIED_REVISION|착지 PR 부재·merged 아님·base≠target(3중 일치 실패) (pulls=%d)"%len(prs)); sys.exit(0)
print("HEAD|%s|%s"%(ok[0]["head"]["sha"],ok[0]["merged_at"]))
PY
)
    case "$HS" in UNVERIFIABLE\|*) emit PREVENTION_UNVERIFIABLE "(b) d=$d ${HS#*|}" ;; UNVERIFIED_REVISION\|*) emit PREVENTION_UNVERIFIED_REVISION "(b) d=$d ${HS#*|}" ;; esac
    HSHA=$(printf '%s' "$HS" | cut -d'|' -f2); MERGED=$(printf '%s' "$HS" | cut -d'|' -f3); [ -z "$MINMERGED" ] || [[ "$MERGED" < "$MINMERGED" ]] && MINMERGED="$MERGED"
    respond "repos/$OWNER_REPO/commits/$HSHA/check-runs"; show_capture B2 "repos/$OWNER_REPO/commits/$HSHA/check-runs"
    # 후보 run: name==check ∧ conclusion==success ∧ app.id==APPID ∧ head_sha==HSHA → 그 check_suite 귀속 확인(check-suites/{id})
    CANDS=$(python3 - "$CAP" "$OWNER_REPO" "$HSHA" "$CHECK" "$APPID" <<'PY'
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
        if str((r.get("app") or {}).get("id"))!=str(appid): why.append("app.id=%s≠%s(위조 표면)"%((r.get("app") or {}).get("id"),appid))
        if r.get("head_sha")!=sha: why.append("head_sha=%s≠PR head"%r.get("head_sha"))
if not good: print("UNVERIFIED_REVISION|%s (check_runs=%d)"%("; ".join(why),len(runs))); sys.exit(0)
print("CAND|"+" ".join(str((r.get("check_suite") or {}).get("id")) for r in good))
PY
)
    case "$CANDS" in UNVERIFIABLE\|*) emit PREVENTION_UNVERIFIABLE "(b) head=$HSHA ${CANDS#*|}" ;; UNVERIFIED_REVISION\|*) emit PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA ${CANDS#*|}" ;; esac
    SUITE_OK=0
    for sid in ${CANDS#CAND|}; do
      [ "$sid" != None ] || continue
      respond "repos/$OWNER_REPO/check-suites/$sid"; show_capture B3 "repos/$OWNER_REPO/check-suites/$sid"
      SST=$(cat "$CAP/$(key "repos/$OWNER_REPO/check-suites/$sid").status")
      printf '%s' "$SST" | grep -Eq '^2' || emit PREVENTION_UNVERIFIABLE "(b) check-suites/$sid http=$SST"
      [ "$(jget "repos/$OWNER_REPO/check-suites/$sid" head_sha)" = "$HSHA" ] && [ "$(jget "repos/$OWNER_REPO/check-suites/$sid" app.id)" = "$APPID" ] && { SUITE_OK=1; break; }
    done
    [ "$SUITE_OK" = 1 ] || emit PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA check_suite 귀속 불일치(head_sha·app.id) 또는 suite 부재"
    printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/check_suite 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
  done
  # (α) 관측: 룰셋 created_at/updated_at vs merged_at(min D) — 기록만
  for id in $RSIDS; do
    python3 - "$id" "$(jget "repos/$OWNER_REPO/rulesets/$id" created_at)" "$(jget "repos/$OWNER_REPO/rulesets/$id" updated_at)" "$MINMERGED" <<'PY'
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

emit PREVENTION_ACTIVE "(a) 술어 충족 ∧ target 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=$ND · app.id=$APPID) — responder=$RESP"
```

## 2. 드라이버 원문 — `t84v217.sh` (sha256 `663ca126a6281e73e55af579f80711d162f86dfba9083846c1e64da498702eb3`)

- 픽스처 = `scratchpad/fx84w/*`(seed → P[아티팩트] [→ d] · `git remote add origin <URL>` 로컬 설정만). seam 주입 디렉터리 `scratchpad/seam217/<variant>/` — 주입 응답 원문은 드라이버
  heredoc/`inject` 인자와 실행 기록의 `U17-A*`/`U17-B*` 캡처에 그대로 있다. 전부 GET-only.

```bash
#!/usr/bin/env bash
# t84v217.sh — v2.17 T-84 ①②③④⑤⑥ + 부속 드라이버 (u17-verify-v217.sh). GET-only. 픽스처 = scratchpad 독립 git repo(원격 origin URL 만 로컬 설정 — 네트워크 쓰기 0). 본 저장소 무접촉·설정 변경 0.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
EX="$SP/u17-verify-v217.sh"; FX="$SP/fx84w"; SEAM="$SP/seam217"; PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
OR=kakao-harris-lee/kis_unified_sts; URL=https://github.com/kakao-harris-lee/kis_unified_sts.git; WB=mission-critical-trading-operating-system; REPO=/Users/harris/Development/private/kis_unified_sts
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "$URL"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ # art <repo> <owner_repo-declared> <target-declared> [extra-yaml-line]
  mkdir -p "$1/$(dirname $PC)"
  { printf 'owner_repo: %s\ntarget_branch: %s\ntos_gate_check: tos-gate\n' "$2" "$3"; [ -n "${4:-}" ] && printf '%s\n' "$4"; printf 'operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n'; } > "$1/$PC"
  git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)"; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ echo "-- artifact @HEAD --"; git -C "$1" show "HEAD:$PC" | sed 's/^/  | /'; echo "\$ U17_RESPONDER=${2:-gh} bash u17-verify-v217.sh <fixture>"; U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$1"; echo "u17_rc=$?"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; if [ -f "$4" ]; then cp "$4" "$1/$(k "$2").body"; else printf '%s\n' "$4" > "$1/$(k "$2").body"; fi; }
probe(){ echo "\$ gh api -i $1   # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; gh api -i "$1" 2>&1 | grep -v -E '^[A-Za-z-]+: ' | tr -d '\r' | sed 's/^/  | /'; }

sec "T-84 (0) live 병기 — 파생 원천·게이트 앱 id 실측 (GET-only)"
echo "\$ git remote get-url origin (본 저장소)"; git -C "$REPO" remote get-url origin
probe "repos/$OR" | head -4; echo "  .default_branch=$(gh api repos/$OR 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["default_branch"])')"
probe "apps/github-actions" | head -4; echo "  apps/github-actions .id=$(gh api apps/github-actions 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')  (계약 기본 gate_app_id=15368)"
echo "-- 참고: 작업 브랜치 $WB 의 protection 은 여전히 404 (v2.16 T-84 ① 의 «작업 브랜치 → ABSENT» 원자료) — v2.17 실행기는 파생 target(default_branch) 만 조회한다"; probe "repos/$OR/branches/$WB/protection" | head -4

sec "T-84 (1) live — 선언 = 파생(origin/$OR · default main) → INSUFFICIENT (responder=gh)"
R="$FX/live-main"; mk "$R"; art "$R" "$OR" main; run "$R" gh

sec "T-84 (5)-a live — 아티팩트가 비-default 브랜치($WB) 선언 → TARGET_MISMATCH (D=∅ 에서도 · 전순서 4 < 5 INSUFFICIENT)"
R="$FX/mm-branch"; mk "$R"; art "$R" "$OR" "$WB"; run "$R" gh
sec "T-84 (5)-b live — 아티팩트가 타 저장소(octocat/Hello-World) 선언 → TARGET_MISMATCH (파생 owner_repo 는 origin 에서 온다)"
R="$FX/mm-repo"; mk "$R"; art "$R" octocat/Hello-World main; run "$R" gh
sec "T-84 (5)-c seam — 선언 불일치 + (a) 는 seam ACTIVE 여도 TARGET_MISMATCH (임의 대상의 보호로 진입 승인 차단)"
rm -rf "$SEAM"; mkdir -p "$SEAM"
cat > "$SEAM/active-protection.json" <<'EOF'
{"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
EOF
cat > "$SEAM/insufficient-protection.json" <<'EOF'
{"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"required_signatures":{"enabled":false},"enforce_admins":{"enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
EOF
base_seam(){ # base_seam <dir> <protection-json|404> — repos/{o}/{r}(default main) + protection + rules [] + rulesets [] 주입
  inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'
  if [ "$2" = 404 ]; then inject "$1" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection#get-branch-protection","status":"404"}'; else inject "$1" "repos/$OR/branches/main/protection" 200 "$2"; fi
  inject "$1" "repos/$OR/rules/branches/main" 200 '[]'; inject "$1" "repos/$OR/rulesets" 200 '[]'; }
base_seam "$SEAM/active" "$SEAM/active-protection.json"; base_seam "$SEAM/insufficient" "$SEAM/insufficient-protection.json"; base_seam "$SEAM/released-absent" 404
base_seam "$SEAM/unverifiable" "$SEAM/active-protection.json"; inject "$SEAM/unverifiable" "repos/$OR/branches/main/protection" 500 '{"message":"SIMULATED server error"}'
mkdir -p "$SEAM/neterr"
R="$FX/mm-seam"; mk "$R"; art "$R" "$OR" "$WB"; run "$R" "file:$SEAM/active"

sec "T-84 (2)-i seam ACTIVE (SIMULATED · 선언=파생)"; R="$FX/seam"; mk "$R"; art "$R" "$OR" main; run "$R" "file:$SEAM/active"
sec "T-84 (2)-ii seam INSUFFICIENT (SIMULATED)"; run "$R" "file:$SEAM/insufficient"
sec "T-84 (2)-iii seam UNVERIFIABLE — protection HTTP 500 (SIMULATED)"; run "$R" "file:$SEAM/unverifiable"
sec "T-84 (2)-iv seam UNVERIFIABLE — 응답 없음(repos/{o}/{r} 부터 실패 → default_branch 파생 불가) (SIMULATED)"; run "$R" "file:$SEAM/neterr"

sec "T-84 (3)-0 live 병기 — (b) 원자료 (미푸시 HEAD 422 · 푸시 무-PR [] · origin/main PR#636 head check-runs: name/conclusion/app.id/head_sha/check_suite)"
H=$(git -C "$REPO" rev-parse HEAD); OM=$(git -C "$REPO" rev-parse origin/main); echo "HEAD(미푸시)=$H origin/main=$OM pushed_no_pr=be98f075715521a46c4ae074150cbec2746e7384"
probe "repos/$OR/commits/$H/pulls" | head -4; probe "repos/$OR/commits/be98f075715521a46c4ae074150cbec2746e7384/pulls" | head -4
HS=$(gh api "repos/$OR/commits/$OM/pulls" 2>/dev/null | python3 -c 'import json,sys
a=json.load(sys.stdin); ok=[p for p in a if p.get("merged_at") and (p.get("base") or {}).get("ref")=="main"]; print(ok[0]["head"]["sha"] if ok else "")')
echo "origin/main pulls → merged·base=main PR head.sha=$HS"
gh api "repos/$OR/commits/$HS/check-runs" 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin); print("  check-runs total=%s"%j.get("total_count")); [print("  name=%r conclusion=%r app.id=%s head_sha=%s check_suite.id=%s"%(r.get("name"),r.get("conclusion"),(r.get("app") or {}).get("id"),r.get("head_sha"),(r.get("check_suite") or {}).get("id"))) for r in j.get("check_runs",[])]'
SID=$(gh api "repos/$OR/commits/$HS/check-runs" 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin); r=j["check_runs"][0]; print(r["check_suite"]["id"])')
gh api "repos/$OR/check-suites/$SID" 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin); print("  check-suites/%s: head_sha=%s app.id=%s status=%s conclusion=%s"%(j["id"],j["head_sha"],(j.get("app") or {}).get("id"),j.get("status"),j.get("conclusion")))'
echo "  ⇒ PR head 의 check-runs 에 name==tos-gate 부재 → (b) UNVERIFIED_REVISION (app.id 는 전부 15368 · head_sha==PR head — 게이트 이름만 없다)"

sec "T-84 (3)-a mixed — (a) seam ACTIVE + (b) live: 픽스처 d 는 GitHub 에 없는 sha → 422 → UNVERIFIABLE"
R="$FX/rev-live"; mk "$R"; art "$R" "$OR" main; D=$(d0a "$R"); echo "d=$D"; run "$R" "mixed:$SEAM/active"

sec "T-84 (3)-b seam — (b) 양성(SIMULATED): merged PR(base main) · head check-run {tos-gate, success, app.id 15368, head_sha==head, check_suite → check-suites/{id} head_sha·app.id 일치}"
R="$FX/rev-seam"; mk "$R"; art "$R" "$OR" main; D=$(d0a "$R"); echo "d=$D"; HSHA=1111111111111111111111111111111111111111; SUITE=777001
S="$SEAM/rev-ok"; rm -rf "$S"; cp -R "$SEAM/active" "$S"
inject "$S" "repos/$OR/commits/$D/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"2026-08-19T00:10:00Z\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$HSHA\"},\"url\":\"SIMULATED\"}]"
inject "$S" "repos/$OR/commits/$HSHA/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$HSHA\",\"check_suite\":{\"id\":$SUITE}},{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$HSHA\",\"check_suite\":{\"id\":$SUITE}}]}"
inject "$S" "repos/$OR/check-suites/$SUITE" 200 "{\"id\":$SUITE,\"head_sha\":\"$HSHA\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"status\":\"completed\",\"conclusion\":\"success\"}"
run "$R" "file:$S"

sec "T-84 (6) seam — app_id 위조: name tos-gate · conclusion success 이지만 app.id=99999 (제3자 앱) → UNVERIFIED_REVISION"
S="$SEAM/rev-forged-app"; rm -rf "$S"; cp -R "$SEAM/rev-ok" "$S"
inject "$S" "repos/$OR/commits/$HSHA/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$HSHA\",\"check_suite\":{\"id\":$SUITE}},{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":99999,\"slug\":\"third-party-forger\"},\"head_sha\":\"$HSHA\",\"check_suite\":{\"id\":777002}}]}"
inject "$S" "repos/$OR/check-suites/777002" 200 "{\"id\":777002,\"head_sha\":\"$HSHA\",\"app\":{\"id\":99999,\"slug\":\"third-party-forger\"},\"status\":\"completed\",\"conclusion\":\"success\"}"
run "$R" "file:$S"
echo "-- 대조: «이름·결론만 보는 구현»(v2.16 (b)) 이 같은 캡처에서 내는 값 --"
python3 - "$S/$(k "repos/$OR/commits/$HSHA/check-runs").body" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); runs=j["check_runs"]
print("  name-only view: %s"%("PASS(green — 위조 통과)" if any(r["name"]=="tos-gate" and r["conclusion"]=="success" for r in runs) else "red"))
print("  app.id view   : %s"%("PASS" if any(r["name"]=="tos-gate" and r["conclusion"]=="success" and (r.get("app") or {}).get("id")==15368 for r in runs) else "red — app.id 불일치"))
PY
sec "T-84 (6)-b seam — head_sha 불일치 (다른 커밋의 tos-gate success 를 끌어옴) → UNVERIFIED_REVISION"
S="$SEAM/rev-wrong-head"; rm -rf "$S"; cp -R "$SEAM/rev-ok" "$S"
inject "$S" "repos/$OR/commits/$HSHA/check-runs" 200 "{\"total_count\":1,\"check_runs\":[{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"2222222222222222222222222222222222222222\",\"check_suite\":{\"id\":$SUITE}}]}"
run "$R" "file:$S"
sec "T-84 (6)-c seam — check_suite 귀속 불일치 (suite 의 head_sha 가 다름) → UNVERIFIED_REVISION"
S="$SEAM/rev-wrong-suite"; rm -rf "$S"; cp -R "$SEAM/rev-ok" "$S"
inject "$S" "repos/$OR/check-suites/$SUITE" 200 "{\"id\":$SUITE,\"head_sha\":\"3333333333333333333333333333333333333333\",\"app\":{\"id\":15368},\"status\":\"completed\",\"conclusion\":\"success\"}"
run "$R" "file:$S"

sec "T-84 (4) stub 시퀀스 — t0 seam ACTIVE → t1 해제(404) → t2 약화 → t3 live 재조회"
R="$FX/seq"; mk "$R"; art "$R" "$OR" main
echo "== t0"; run "$R" "file:$SEAM/active"; echo "== t1 (404)"; run "$R" "file:$SEAM/released-absent"; echo "== t2 (약화)"; run "$R" "file:$SEAM/insufficient"; echo "== t3 (live gh)"; run "$R" gh

sec "T-84 부속 — d 먼저·P 나중 → LATE (seam (a)(b) 충족)"
R="$FX/late"; mk "$R"; D=$(d0a "$R"); art "$R" "$OR" main; echo "d=$D"; S="$SEAM/rev-late"; rm -rf "$S"; cp -R "$SEAM/rev-ok" "$S"; run "$R" "file:$S"
sec "T-84 부속 — countersign 형식 위반 → UNSIGNED (전순서 3 < 4 — 선언 불일치보다 먼저)"
R="$FX/unsigned"; mk "$R"; art "$R" "$OR" "$WB" ; printf 'owner_repo: %s\ntarget_branch: %s\ntos_gate_check: tos-gate\noperator_countersign: APPROVED (no ISO)\n' "$OR" "$WB" > "$R/$PC"; git -C "$R" add -A; git -C "$R" commit -q -m "P2: bad countersign"; run "$R" "file:$SEAM/active"
sec "T-84 부속 — 본 저장소 HEAD 에 실행기 적용 (아티팩트 부재 → ABSENT · 조회 이전)"
echo "\$ bash u17-verify-v217.sh <repo>"; U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO"; echo "u17_rc=$?"
```

## 3. 실행 기록 (t84v217.sh stdout 전문 · 캡처 verbatim + UTC · live 병기 원자료 포함)

```text
t84v217_utc=2026-08-18T18:31:23Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t84v217.sh

########## T-84 (0) live 병기 — 파생 원천·게이트 앱 id 실측 (GET-only) ##########
$ git remote get-url origin (본 저장소)
https://github.com/kakao-harris-lee/kis_unified_sts.git
$ gh api -i repos/kakao-harris-lee/kis_unified_sts   # utc=2026-08-18T18:31:23Z
  | HTTP/2.0 200 OK
  | 
  | {"id":1138065373,"node_id":"R_kgDOQ9V_3Q","name":"kis_unified_sts","full_name":"kakao-harris-lee/kis_unified_sts","private":false,"owner":{"login":"kakao-harris-lee","id":130432481,"node_id":"U_kgDOB8Y94Q","avatar_url":"https://avatars.githubusercontent.com/u/130432481?v=4","gravatar_id":"","url":"https://api.github.com/users/kakao-harris-lee","html_url":"https://github.com/kakao-harris-lee","followers_url":"https://api.github.com/users/kakao-harris-lee/followers","following_url":"https://api.github.com/users/kakao-harris-lee/following{/other_user}","gists_url":"https://api.github.com/users/kakao-harris-lee/gists{/gist_id}","starred_url":"https://api.github.com/users/kakao-harris-lee/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/kakao-harris-lee/subscriptions","organizations_url":"https://api.github.com/users/kakao-harris-lee/orgs","repos_url":"https://api.github.com/users/kakao-harris-lee/repos","events_url":"https://api.github.com/users/kakao-harris-lee/events{/privacy}","received_events_url":"https://api.github.com/users/kakao-harris-lee/received_events","type":"User","user_view_type":"public","site_admin":false},"html_url":"https://github.com/kakao-harris-lee/kis_unified_sts","description":null,"fork":false,"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts","forks_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/forks","keys_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/keys{/key_id}","collaborators_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/collaborators{/collaborator}","teams_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/teams","hooks_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/hooks","issue_events_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/events{/number}","events_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/events","assignees_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/assignees{/user}","branches_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches{/branch}","tags_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/tags","blobs_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/blobs{/sha}","git_tags_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/tags{/sha}","git_refs_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/refs{/sha}","trees_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/trees{/sha}","statuses_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/statuses/{sha}","languages_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/languages","stargazers_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/stargazers","contributors_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/contributors","subscribers_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/subscribers","subscription_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/subscription","commits_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/commits{/sha}","git_commits_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/commits{/sha}","comments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/comments{/number}","issue_comment_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/comments{/number}","contents_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/contents/{+path}","compare_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/compare/{base}...{head}","merges_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/merges","archive_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/{archive_format}{/ref}","downloads_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/downloads","issues_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues{/number}","pulls_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls{/number}","milestones_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/milestones{/number}","notifications_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/notifications{?since,all,participating}","labels_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/labels{/name}","releases_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/releases{/id}","deployments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/deployments","created_at":"2026-01-20T07:44:13Z","updated_at":"2026-08-03T07:16:06Z","pushed_at":"2026-08-18T15:20:49Z","git_url":"git://github.com/kakao-harris-lee/kis_unified_sts.git","ssh_url":"git@github.com:kakao-harris-lee/kis_unified_sts.git","clone_url":"https://github.com/kakao-harris-lee/kis_unified_sts.git","svn_url":"https://github.com/kakao-harris-lee/kis_unified_sts","homepage":null,"size":23880,"stargazers_count":0,"watchers_count":0,"language":"Python","has_issues":true,"has_projects":true,"has_downloads":false,"has_wiki":false,"has_pages":false,"has_discussions":false,"forks_count":0,"mirror_url":null,"archived":false,"disabled":false,"open_issues_count":2,"license":null,"allow_forking":true,"is_template":false,"web_commit_signoff_required":false,"has_pull_requests":true,"pull_request_creation_policy":"all","topics":[],"visibility":"public","forks":0,"open_issues":2,"watchers":0,"default_branch":"main","permissions":{"admin":true,"maintain":true,"push":true,"triage":true,"pull":true},"temp_clone_token":"","allow_squash_merge":true,"allow_merge_commit":true,"allow_rebase_merge":true,"allow_auto_merge":false,"delete_branch_on_merge":false,"allow_update_branch":false,"use_squash_pr_title_as_default":false,"squash_merge_commit_message":"COMMIT_MESSAGES","squash_merge_commit_title":"COMMIT_OR_PR_TITLE","merge_commit_message":"PR_TITLE","merge_commit_title":"MERGE_MESSAGE","security_and_analysis":{"secret_scanning":{"status":"disabled"},"secret_scanning_push_protection":{"status":"disabled"},"dependabot_security_updates":{"status":"disabled"},"secret_scanning_non_provider_patterns":{"status":"disabled"},"secret_scanning_validity_checks":{"status":"disabled"}},"network_count":0,"subscribers_count":0}
  .default_branch=main
$ gh api -i apps/github-actions   # utc=2026-08-18T18:31:24Z
  | HTTP/2.0 200 OK
  | 
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
  apps/github-actions .id=15368  (계약 기본 gate_app_id=15368)
-- 참고: 작업 브랜치 mission-critical-trading-operating-system 의 protection 은 여전히 404 (v2.16 T-84 ① 의 «작업 브랜치 → ABSENT» 원자료) — v2.17 실행기는 파생 target(default_branch) 만 조회한다
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/branches/mission-critical-trading-operating-system/protection   # utc=2026-08-18T18:31:25Z
  | HTTP/2.0 404 Not Found
  | 
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection#get-branch-protection","status":"404"}gh: Branch not protected (HTTP 404)

########## T-84 (1) live — 선언 = 파생(origin/kakao-harris-lee/kis_unified_sts · default main) → INSUFFICIENT (responder=gh) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=gh bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=gh artifact@53063fe capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6qkUAa0MYo
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:26Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:27Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:27Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:28Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T18:31:28Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록 — merged_at(min D) 대조는 (b) 후)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-T declared-vs-derived: 일치
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
u17_rc=1

########## T-84 (5)-a live — 아티팩트가 비-default 브랜치(mission-critical-trading-operating-system) 선언 → TARGET_MISMATCH (D=∅ 에서도 · 전순서 4 < 5 INSUFFICIENT) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=gh bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=mission-critical-trading-operating-system | check=tos-gate gate_app_id=15368 responder=gh artifact@7da1a79 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.PAx6Ppb8LJ
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:29Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:30Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:31Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:31Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T18:31:32Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록 — merged_at(min D) 대조는 (b) 후)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-T declared-vs-derived:  target_branch(선언=mission-critical-trading-operating-system ≠ 파생=main)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 구조 파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 파생=main)
u17_rc=1

########## T-84 (5)-b live — 아티팩트가 타 저장소(octocat/Hello-World) 선언 → TARGET_MISMATCH (파생 owner_repo 는 origin 에서 온다) ##########
-- artifact @HEAD --
  | owner_repo: octocat/Hello-World
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=gh bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=octocat/Hello-World target_branch=main | check=tos-gate gate_app_id=15368 responder=gh artifact@5dbcc05 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.rs8dpZPQIP
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:33Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:33Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:34Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:34Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T18:31:35Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록 — merged_at(min D) 대조는 (b) 후)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-T declared-vs-derived:  owner_repo(선언=octocat/Hello-World ≠ 파생=kakao-harris-lee/kis_unified_sts)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 구조 파생값과 불일치: owner_repo(선언=octocat/Hello-World ≠ 파생=kakao-harris-lee/kis_unified_sts)
u17_rc=1

########## T-84 (5)-c seam — 선언 불일치 + (a) 는 seam ACTIVE 여도 TARGET_MISMATCH (임의 대상의 보호로 진입 승인 차단) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=mission-critical-trading-operating-system | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active artifact@89a3625 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MsVQNQwmwj
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:36Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:36Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:36Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:36Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived:  target_branch(선언=mission-critical-trading-operating-system ≠ 파생=main)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 구조 파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 파생=main)
u17_rc=1

########## T-84 (2)-i seam ACTIVE (SIMULATED · 선언=파생) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active artifact@6af55b6 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pf0vjRRXLY
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:37Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:37Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:37Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:37Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived: 일치
P=6af55b69bba8925e2d710191493791ba3423aff4 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ target 대조 만으로 판정)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족 ∧ target 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=0 · app.id=15368) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active
u17_rc=0

########## T-84 (2)-ii seam INSUFFICIENT (SIMULATED) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/insufficient bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/insufficient artifact@6af55b6 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.sq0OZBV4Py
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:37Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:37Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"required_signatures":{"enabled":false},"enforce_admins":{"enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:37Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:37Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-T declared-vs-derived: 일치
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
u17_rc=1

########## T-84 (2)-iii seam UNVERIFIABLE — protection HTTP 500 (SIMULATED) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/unverifiable bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/unverifiable artifact@6af55b6 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.htLtssgbaO
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:38Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:38Z  http=500
  | {"message":"SIMULATED server error"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:38Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:38Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_UNVERIFIABLE
u17_live_reason=http/network/auth: protection=500 rules=200 rulesets=200
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(a) http/network/auth: protection=500 rules=200 rulesets=200
u17_rc=1

########## T-84 (2)-iv seam UNVERIFIABLE — 응답 없음(repos/{o}/{r} 부터 실패 → default_branch 파생 불가) (SIMULATED) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/neterr bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@UNRESOLVED
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:38Z  http=ERR
  | SIMULATED responder: no injected response for repos/kakao-harris-lee/kis_unified_sts
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=repos/{o}/{r} 조회 실패(http=ERR) — default_branch 파생 불가
u17_rc=1

########## T-84 (3)-0 live 병기 — (b) 원자료 (미푸시 HEAD 422 · 푸시 무-PR [] · origin/main PR#636 head check-runs: name/conclusion/app.id/head_sha/check_suite) ##########
HEAD(미푸시)=a3c95b4f384f7e0c9375163a7d1c631e38c8e863 origin/main=11e382fc0c9c16d9208a0d59e595d9cf93066be5 pushed_no_pr=be98f075715521a46c4ae074150cbec2746e7384
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/a3c95b4f384f7e0c9375163a7d1c631e38c8e863/pulls   # utc=2026-08-18T18:31:38Z
  | HTTP/2.0 422 Unprocessable Entity
  | 
  | {"message":"No commit found for SHA: a3c95b4f384f7e0c9375163a7d1c631e38c8e863","documentation_url":"https://docs.github.com/rest/commits/commits#list-pull-requests-associated-with-a-commit","status":"422"}gh: No commit found for SHA: a3c95b4f384f7e0c9375163a7d1c631e38c8e863 (HTTP 422)
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/be98f075715521a46c4ae074150cbec2746e7384/pulls   # utc=2026-08-18T18:31:38Z
  | HTTP/2.0 200 OK
  | 
  | []
origin/main pulls → merged·base=main PR head.sha=7656259d414c4a855824406bab40bdc5438de171
  check-runs total=5
  name='performance' conclusion='success' app.id=15368 head_sha=7656259d414c4a855824406bab40bdc5438de171 check_suite.id=83489483104
  name='lint' conclusion='success' app.id=15368 head_sha=7656259d414c4a855824406bab40bdc5438de171 check_suite.id=83489483104
  name='type-check' conclusion='success' app.id=15368 head_sha=7656259d414c4a855824406bab40bdc5438de171 check_suite.id=83489483104
  name='test' conclusion='success' app.id=15368 head_sha=7656259d414c4a855824406bab40bdc5438de171 check_suite.id=83489483104
  name='backtest-extra' conclusion='success' app.id=15368 head_sha=7656259d414c4a855824406bab40bdc5438de171 check_suite.id=83489483104
  check-suites/83489483104: head_sha=7656259d414c4a855824406bab40bdc5438de171 app.id=15368 status=completed conclusion=success
  ⇒ PR head 의 check-runs 에 name==tos-gate 부재 → (b) UNVERIFIED_REVISION (app.id 는 전부 15368 · head_sha==PR head — 게이트 이름만 없다)

########## T-84 (3)-a mixed — (a) seam ACTIVE + (b) live: 픽스처 d 는 GitHub 에 없는 sha → 422 → UNVERIFIABLE ##########
d=012ece185e712219b753cfb41edcd396b7758525
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=mixed:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active bash u17-verify-v217.sh <fixture>
U17-seam repos/kakao-harris-lee/kis_unified_sts ← file(SIMULATED)
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=mixed:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active artifact@012ece1 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.d0uvxiq9RA
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:42Z  http=200  (.default_branch=main)
U17-seam repos/kakao-harris-lee/kis_unified_sts/branches/main/protection ← file(SIMULATED)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:42Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-seam repos/kakao-harris-lee/kis_unified_sts/rules/branches/main ← file(SIMULATED)
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:42Z  http=200
  | []
U17-seam repos/kakao-harris-lee/kis_unified_sts/rulesets ← file(SIMULATED)
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:42Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived: 일치
P=77e1ddacdaed2a98147d6f88776af2ffd9aecbcc |D|=1 D=012ece185e712219b753cfb41edcd396b7758525 
U17-seam repos/kakao-harris-lee/kis_unified_sts/commits/012ece185e712219b753cfb41edcd396b7758525/pulls ← gh(live)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/012ece185e712219b753cfb41edcd396b7758525/pulls  utc=2026-08-18T18:31:43Z  http=422
  | {"message":"No commit found for SHA: 012ece185e712219b753cfb41edcd396b7758525","documentation_url":"https://docs.github.com/rest/commits/commits#list-pull-requests-associated-with-a-commit","status":"422"}
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(b) d=012ece185e712219b753cfb41edcd396b7758525 http=422
u17_rc=1

########## T-84 (3)-b seam — (b) 양성(SIMULATED): merged PR(base main) · head check-run {tos-gate, success, app.id 15368, head_sha==head, check_suite → check-suites/{id} head_sha·app.id 일치} ##########
d=1936e23a7e32dcfda24560a5c2d5b240dce80a76
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-ok bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-ok artifact@1936e23 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.sO85jITGMC
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:43Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:43Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:43Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:43Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived: 일치
P=5707b0133fe628fc3b0d16578e390dd98a8c3ef9 |D|=1 D=1936e23a7e32dcfda24560a5c2d5b240dce80a76 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/1936e23a7e32dcfda24560a5c2d5b240dce80a76/pulls  utc=2026-08-18T18:31:44Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"1111111111111111111111111111111111111111"},"url":"SIMULATED"}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1111111111111111111111111111111111111111/check-runs  utc=2026-08-18T18:31:44Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1111111111111111111111111111111111111111","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368},"head_sha":"1111111111111111111111111111111111111111","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T18:31:44Z  http=200
  | {"id":777001,"head_sha":"1111111111111111111111111111111111111111","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B d=1936e23a7e32dcfda24560a5c2d5b240dce80a76 head=1111111111111111111111111111111111111111 merged_at=2026-08-19T00:10:00Z: name/conclusion/app.id=15368/head_sha/check_suite 전부 일치
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족 ∧ target 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=1 · app.id=15368) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-ok
u17_rc=0

########## T-84 (6) seam — app_id 위조: name tos-gate · conclusion success 이지만 app.id=99999 (제3자 앱) → UNVERIFIED_REVISION ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-forged-app bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-forged-app artifact@1936e23 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.8mPZ7XKO79
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:44Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:44Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:44Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:44Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived: 일치
P=5707b0133fe628fc3b0d16578e390dd98a8c3ef9 |D|=1 D=1936e23a7e32dcfda24560a5c2d5b240dce80a76 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/1936e23a7e32dcfda24560a5c2d5b240dce80a76/pulls  utc=2026-08-18T18:31:45Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"1111111111111111111111111111111111111111"},"url":"SIMULATED"}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1111111111111111111111111111111111111111/check-runs  utc=2026-08-18T18:31:45Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1111111111111111111111111111111111111111","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":99999,"slug":"third-party-forger"},"head_sha":"1111111111111111111111111111111111111111","check_suite":{"id":777002}}]}
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=1936e23a7e32dcfda24560a5c2d5b240dce80a76 head=1111111111111111111111111111111111111111 app.id=99999≠15368(위조 표면) (check_runs=2)
u17_rc=1
-- 대조: «이름·결론만 보는 구현»(v2.16 (b)) 이 같은 캡처에서 내는 값 --
  name-only view: PASS(green — 위조 통과)
  app.id view   : red — app.id 불일치

########## T-84 (6)-b seam — head_sha 불일치 (다른 커밋의 tos-gate success 를 끌어옴) → UNVERIFIED_REVISION ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-wrong-head bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-wrong-head artifact@1936e23 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DlvuHWbHig
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:45Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:45Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:45Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:45Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived: 일치
P=5707b0133fe628fc3b0d16578e390dd98a8c3ef9 |D|=1 D=1936e23a7e32dcfda24560a5c2d5b240dce80a76 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/1936e23a7e32dcfda24560a5c2d5b240dce80a76/pulls  utc=2026-08-18T18:31:45Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"1111111111111111111111111111111111111111"},"url":"SIMULATED"}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1111111111111111111111111111111111111111/check-runs  utc=2026-08-18T18:31:46Z  http=200
  | {"total_count":1,"check_runs":[{"name":"tos-gate","conclusion":"success","app":{"id":15368},"head_sha":"2222222222222222222222222222222222222222","check_suite":{"id":777001}}]}
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=1936e23a7e32dcfda24560a5c2d5b240dce80a76 head=1111111111111111111111111111111111111111 head_sha=2222222222222222222222222222222222222222≠PR head (check_runs=1)
u17_rc=1

########## T-84 (6)-c seam — check_suite 귀속 불일치 (suite 의 head_sha 가 다름) → UNVERIFIED_REVISION ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-wrong-suite bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-wrong-suite artifact@1936e23 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.XeXgO4SYjH
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:46Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:46Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:46Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:46Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived: 일치
P=5707b0133fe628fc3b0d16578e390dd98a8c3ef9 |D|=1 D=1936e23a7e32dcfda24560a5c2d5b240dce80a76 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/1936e23a7e32dcfda24560a5c2d5b240dce80a76/pulls  utc=2026-08-18T18:31:46Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:10:00Z","base":{"ref":"main"},"head":{"sha":"1111111111111111111111111111111111111111"},"url":"SIMULATED"}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1111111111111111111111111111111111111111/check-runs  utc=2026-08-18T18:31:46Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1111111111111111111111111111111111111111","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368},"head_sha":"1111111111111111111111111111111111111111","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-18T18:31:46Z  http=200
  | {"id":777001,"head_sha":"3333333333333333333333333333333333333333","app":{"id":15368},"status":"completed","conclusion":"success"}
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=1936e23a7e32dcfda24560a5c2d5b240dce80a76 head=1111111111111111111111111111111111111111 check_suite 귀속 불일치(head_sha·app.id) 또는 suite 부재
u17_rc=1

########## T-84 (4) stub 시퀀스 — t0 seam ACTIVE → t1 해제(404) → t2 약화 → t3 live 재조회 ##########
== t0
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active artifact@c02306d capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7uMWShwVYx
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:47Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:47Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:47Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:47Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived: 일치
P=c02306d99f83b8a1f493daa19dd68295d7ffc502 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ target 대조 만으로 판정)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족 ∧ target 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=0 · app.id=15368) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active
u17_rc=0
== t1 (404)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/released-absent bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/released-absent artifact@c02306d capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2MjWsKIVSW
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:47Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:47Z  http=404
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection#get-branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:48Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:48Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ABSENT
u17_live_reason=protection 404 ∧ 적용 규칙 0 (룰셋 목록=0)
prevention_control_state=PREVENTION_ABSENT
reason=(a) protection 404 ∧ 적용 규칙 0 (룰셋 목록=0)
u17_rc=1
== t2 (약화)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/insufficient bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/insufficient artifact@c02306d capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zrFXzzwY3t
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:48Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:48Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"required_signatures":{"enabled":false},"enforce_admins":{"enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:48Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:48Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-T declared-vs-derived: 일치
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
u17_rc=1
== t3 (live gh)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=gh bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=gh artifact@c02306d capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.mKpofnt654
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:49Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:49Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:50Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:50Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T18:31:51Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α ruleset 17017682 created_at=2026-05-29T15:33:46.629+09:00 updated_at=2026-05-29T15:33:46.662+09:00 enforcement=disabled (관측 기록 — merged_at(min D) 대조는 (b) 후)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-T declared-vs-derived: 일치
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
u17_rc=1

########## T-84 부속 — d 먼저·P 나중 → LATE (seam (a)(b) 충족) ##########
d=29acc9661a4e6ac7d5736030e0978b1ce4b54942
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-late bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/rev-late artifact@39b0add capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1hecd7sBR6
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:52Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:52Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:52Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:52Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
U17-T declared-vs-derived: 일치
P=39b0add02e98b827841a1fd6619663772a49ec98 |D|=1 D=29acc9661a4e6ac7d5736030e0978b1ce4b54942 
prevention_control_state=PREVENTION_LATE
reason=P 가 d=29acc9661a4e6ac7d5736030e0978b1ce4b54942 의 진 조상이 아님
u17_rc=1

########## T-84 부속 — countersign 형식 위반 → UNSIGNED (전순서 3 < 4 — 선언 불일치보다 먼저) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: APPROVED (no ISO)
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active bash u17-verify-v217.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 derived: owner_repo=kakao-harris-lee/kis_unified_sts (remote=origin url=https://github.com/kakao-harris-lee/kis_unified_sts.git) target_branch=main (.default_branch) | declared: owner_repo=kakao-harris-lee/kis_unified_sts target_branch=mission-critical-trading-operating-system | check=tos-gate gate_app_id=15368 responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam217/active artifact@e468508 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.EThGUakxa3
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-18T18:31:53Z  http=200  (.default_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T18:31:53Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T18:31:53Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T18:31:53Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
prevention_control_state=PREVENTION_UNSIGNED
reason=operator_countersign 값 형식 위반: operator_countersign: APPROVED (no ISO)
u17_rc=1

########## T-84 부속 — 본 저장소 HEAD 에 실행기 적용 (아티팩트 부재 → ABSENT · 조회 이전) ##########
$ bash u17-verify-v217.sh <repo>
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1
(t84v217.sh exit=0)
```

픽스처 DAG (조립 시점 재확인 · `git -C $SP/fx84w/<n> log --graph --oneline --all` · origin URL 병기):

```text
== fx84w/live-main  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* 53063fe P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* 7fc1262 seed
== fx84w/mm-branch  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* 7da1a79 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* aadf81e seed
== fx84w/mm-repo  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* 5dbcc05 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* 3a63224 seed
== fx84w/mm-seam  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* 89a3625 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* e11eac4 seed
== fx84w/seam  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* 6af55b6 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* e11eac4 seed
== fx84w/rev-live  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* 012ece1 D0-A: introduce config/tos_completion.yaml
* 77e1dda P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* e447546 seed
== fx84w/rev-seam  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* 1936e23 D0-A: introduce config/tos_completion.yaml
* 5707b01 P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* 733112f seed
== fx84w/seq  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* c02306d P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* 6539bb8 seed
== fx84w/late  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* 39b0add P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* 29acc96 D0-A: introduce config/tos_completion.yaml
* 819295c seed
== fx84w/unsigned  (origin=https://github.com/kakao-harris-lee/kis_unified_sts.git)
* e468508 P2: bad countersign
* 0fd702c P: D0A-PREVENTION-CONTROL (SIMULATED declaration; truth = server + structural derivation)
* e391ffa seed
```

## 4. 관측·정직 기록·계약 결함 후보 (고치지 않는다 — bound_paths 동결)

1. **[계약 문언 정밀화 후보 — S-22] §8 T-84 ① 의 «작업 브랜치 → 404 ABSENT»**: v2.17 이 `target_branch` 를 `.default_branch` 로 **파생**하고 선언값을 대조 대상으로 강등한 뒤에는,
   u17-verify 가 조회하는 대상은 항상 파생 target(=main)이다. 아티팩트가 작업 브랜치를 선언하면 결과는 **`TARGET_MISMATCH`**(⑤-a 실측)이지 `ABSENT` 가 아니고, 작업 브랜치의 404 는
   실행기 경로로 재현되지 않는다(raw probe 병기로만 남긴다 — §3 (0)). ① 행의 그 문장은 v2.16 정의 잔존이며 ⑤ 행과 같은 구성을 다른 값으로 적고 있다. **B1 이 의도한 것이 정확히 이 전환**이므로
   결론은 옳고 문장만 미전파다.
2. **⑤ 는 D=∅ 에서 live 로 red 를 냈다** — (a) 는 파생 target(main) 에 대해 INSUFFICIENT 였지만 전순서 4 가 5 를 앞서 `TARGET_MISMATCH` 로 방출됐다. v2.16 실행기(선언값 그대로 조회)는 같은
   아티팩트에서 «작업 브랜치 404 → ABSENT»(V216 sibling ①-b) 또는 seam ACTIVE 하에서 **ACTIVE** 를 냈을 구성이다(⑤-c 가 그 구성 그대로: v2.17 은 TARGET_MISMATCH).
3. **⑥ 대조**: 같은 캡처에서 «이름·결론만 보는 구현» 은 PASS(green) — app.id 검사 하나가 위조 표면을 닫는다. head_sha·check_suite 귀속 불일치(⑥-b/-c) 도 각각 red. 실측 게이트 앱 id 15368
   (`apps/github-actions`) 는 오늘 main 의 `checks[].app_id`·PR head check-runs 의 `app.id` 와 일치.
4. **(b) 정직 경계 재확인**: ③-0 원자료 — PR#636 head 의 5 check-run 은 전부 GitHub Actions(15368)·head_sha 일치·suite 귀속 일치이나 `tos-gate` 이름이 없다 → CI 에 그 잡이 없다는 계약 정직 표기
   그대로. 미푸시 HEAD 422·푸시 무-PR `[]` 실측 그대로. «보호 off 창에서 체크는 통과한 착지» 는 계약이 «닫지 못한다» 로 적었고 이 실행도 그것을 닫았다고 주장하지 않는다.
5. **(α) 관측**: 룰셋 `protect_main` created_at/updated_at(2026-05-29 KST) 를 `U17-α` 로 기록. 이번 실행은 D≠∅ 인 seam 변이에서 rulesets 를 `[]` 로 주입했으므로 merged_at 대조 라인은 발화하지 않았다
   (코드 경로는 있고 차단 아님).
6. **정밀화 여지(비차단)**: (i) 원격 URL 정규화 규칙(https/ssh/scp 형·`.git` 유무·대소문자)은 계약이 «정규화한 `<owner>/<repo>`» 라고만 적음 — 실행기 규칙을 독해로 선언했다 (ii) `check_suite`
   «귀속 일치» 의 구체(무엇과 무엇의 일치)를 계약이 적지 않아 «suite 의 head_sha==PR head ∧ suite 의 app.id==gate_app_id» 로 읽었다 (iii) `remote_name`·`gate_app_id` 의 아티팩트 키 이름은 실행기 독해.
7. 본 저장소 무접촉·설정 변경 0: worktree 미사용, 픽스처 독립 repo, 서버 GET 만 — §5 사후 재조회로 실행 전후 동일 확인.

## 5. 사후 검증 원문 (repo 무영향 · 서버 설정 무변경 · 본 저장소 NOT_STARTED/PREVENTION_ABSENT/REBINDING_REQUIRED)

```text
=== 사후 검증 (2026-08-18T18:32:17Z) ===
$ git worktree list
/Users/harris/Development/private/kis_unified_sts                                               a3c95b4f [mission-critical-trading-operating-system]
/Users/harris/Development/private/kis_unified_sts/.worktrees/futures-risk-hardening-design      ed7165a7 [docs/futures-risk-hardening-design]
/Users/harris/orca/workspaces/kis_unified_sts/feat-obs-stock-regime-candle-freshness-observabi  7fc95093 [feat/stock-regime-indicator-lag-obs]
$ git status --short
 M uv.lock
?? tools/spikes/
$ git log --oneline -1
a3c95b4f docs(tos): phase0 completion contract v2.17 — U-17 target binding, app_id, honest revision-verification boundary
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
$ bash u17-verify-v217.sh <repo>
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1
$ bash harness217.sh (본 저장소 현행)
R-0 head=a3c95b4f384f7e0c9375163a7d1c631e38c8e863
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
late live-main mm-branch mm-repo mm-seam rev-live rev-seam seam seq unsigned 
(wt/ 비어 있음)
```
