# U17-PREVENTION-CHECK — v2.16 T-84 ①②③④ 실행 기록 (u17-verify · live 서버 음성 + seam 양성 · GET-only)

> **비규범 부속** — 계약 v2.16(`eb2805a9`)은 U-17 증거 아티팩트의 경로·파일명을 규정하지 않는다(grep: `U17-PREVENTION`·«증거 경로» 0건;
> 계약이 규정한 것은 실행기 이름 `u17-verify`, run 을 여는 라인 `U17-0 target=<owner>/<repo>@<branch>`, 4 엔드포인트 verbatim 캡처 + UTC,
> 7값·전순서 7단, `responder` 기록뿐). 그래서 v2.14 재심 스탬프(`20260819-002145`)의 sibling 으로 이 이름을 쓴다. **판정 소비자는 이
> 파일의 응답을 신뢰하지 않고 스스로 live 조회한다**(계약 «진실 원천» 절) — 이 파일은 «진입자가 점검했다»는 기록이자 **대조용**이다.
> **서버 쓰기·설정 변경 0** — 전부 `gh api` GET(`-i` 헤더 포함)이며, 사후 재조회(§6)로 실행 전후 서버 상태 동일을 확인했다.
- **생성 시각**: 2026-08-18T17:59:03Z (UTC) · 실행 시각은 각 절 원문의 `*_utc=`·`utc=` · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트
- **동결 결속**: 계약 파일 HEAD blob `b246db5c`(sha256 `6e36ea68905966607cf98864e734605812f12278dad95926b5a7d26d4c0f0809`, 6,758행) ==
  `git show eb2805a9:` (워킹트리 clean · `git status --short -- docs/plans` 무출력 §6). 본 저장소 현행 하니스 `REBINDING_REQUIRED`(재결속 대기).
- **실행기 결속**: sha256(u17-verify.sh) = `cd2de1db024f4280a6f67f520e7199d8eee40e7155798063f7a2212fb16f4cad` · sha256(t84v.sh) =
  `320bb7c2773a26a1e5807e077a83e90f48ef9c204d080686954309e46ad07756` · sha256(t84v3.sh) = `c4a27791750246968a788a2b1dc68d2582ff94dcf6387db349287842deca5251`
  (원문 전부 §1·§2·§4 수록). 대상 저장소 = `origin` 원격 `kakao-harris-lee/kis_unified_sts`(아티팩트가 파라미터로 선언).
- **T-82 ⑰ⓑ·U-15 는 이 파일 밖** — U-15 3단 가드 증거는 sibling `U15-ENTRY-CHECK-V216.md`.
- **결과 요약 — 실행기 stdout·rc 원문 그대로 (해석 아님)**:

| 변이 | 구성 (픽스처 = scratchpad 독립 git repo · 아티팩트 = SIMULATED 파라미터 선언+countersign) | responder | 방출값 (`prevention_control_state=`) | rc | 기대 (§8 T-84 행 · U-17 (a)(b)(c)·U-17-c) | 대조 |
| --- | --- | --- | --- | --- | --- | --- |
| **① -a live** | target=`main` | **`gh`(live)** | **`PREVENTION_INSUFFICIENT`** — `classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]` | 1 | ① «main → INSUFFICIENT» | **일치 (인증 실측)** |
| **① -b live** | target=`mission-critical-trading-operating-system` | **`gh`(live)** | **`PREVENTION_ABSENT`** — `protection 404 ∧ 적용 규칙 0 (룰셋 목록=1)` | 1 | ① «작업 브랜치 → ABSENT(404)» | **일치 (인증 실측)** |
| ② -i seam ACTIVE | 주입: protection 200(contexts∋tos-gate·strict·enforce_admins·force-push/deletion 불허·PR reviews 실재·restrictions 없음)·rules []·rulesets [] | `file:seam216/active` **SIMULATED** | `PREVENTION_ACTIVE` (D=∅ → (b)(c) 검증 대상 없음 명시) | 0 | ② ACTIVE 모의 — **양성은 운영자가 보호를 실제 설정하기 전엔 실측 불가** | **일치 (모의)** |
| ② -ii seam INSUFFICIENT | 주입: 오늘 main 실측 형태(contexts [test]·strict false·enforce_admins false·PR reviews 부재) | `file:…/insufficient` SIMULATED | `PREVENTION_INSUFFICIENT` | 1 | ② | **일치** |
| ② -iii seam UNVERIFIABLE | 주입: protection HTTP 500 | `file:…/unverifiable` SIMULATED | `PREVENTION_UNVERIFIABLE` | 1 | ② (HTTP 오류 → fail-closed) | **일치** |
| ② -iv seam UNVERIFIABLE | 주입 응답 없음(네트워크/도구 오류 모의) | `file:…/neterr` SIMULATED | `PREVENTION_UNVERIFIABLE` | 1 | (네트워크 오류 → fail-closed) | **일치** |
| **③ -0 live 병기** | 본 저장소 실 커밋으로 (b) 원자료 실측: 미푸시 HEAD `eb2805a9` → **422** · 푸시된 무-PR 커밋 `be98f075` → **`[]`** · origin/main `11e382fc`(PR #636 squash 착지) → merged PR → `head.sha=7656259d` → check-runs 5건(`performance`·`lint`·`type-check`·`test`·`backtest-extra`, **`tos-gate` 없음**) | `gh`(live) | (실행기 밖 원자료 — §4) | — | ③ «422 → UNVERIFIABLE / check-run tos-gate 부재 → UNVERIFIED_REVISION» 의 원자료 | **계약 기술과 정합** (+관측 §5-2) |
| ③ -a mixed | (a)=seam ACTIVE(SIMULATED) · (b)=live: 픽스처 d(`175cf33`)는 GitHub 에 없는 sha | `mixed:…/active` | `PREVENTION_UNVERIFIABLE` — `(b) d=… http=422` | 1 | ③ «미푸시 422 → UNVERIFIABLE» | **일치 (b 경로 live)** |
| ③ -b seam (b) 양성 | 주입: pulls → merged PR(base main, head 1111…) · head check-runs ∋ {tos-gate, success} | `file:…/rev-ok` SIMULATED | `PREVENTION_ACTIVE` — `U17-B d=… head=1111…: check-run success 실재` | 0 | (b) 충족 → ACTIVE (모의) | **일치 (모의)** |
| ③ -c seam | 주입: check-runs 에 tos-gate success 부재 | `file:…/rev-nocheck` | `PREVENTION_UNVERIFIED_REVISION` | 1 | ③ | **일치** |
| ③ -d seam | 주입: pulls `[]`(착지 PR 부재) | `file:…/rev-nopr` | `PREVENTION_UNVERIFIED_REVISION` | 1 | ③ | **일치** |
| ③ -e seam | 주입: PR open(merged 아님) | `file:…/rev-open` | `PREVENTION_UNVERIFIED_REVISION` | 1 | ③ | **일치** |
| **④ stub 시퀀스** | 같은 픽스처: t0 seam ACTIVE → t1 보호 해제(404) → t2 보호 약화(strict/체크 해제) → t3 live 재조회 | seam→seam→seam→`gh` | `ACTIVE`/0 → **`ABSENT`**/1 → **`INSUFFICIENT`**/1 → `INSUFFICIENT`/1 | | ④ «한 번 통과가 영원한 통과가 아님» — 완료 판정 시점 재조회가 ABSENT/INSUFFICIENT | **일치** |
| 부속 (c) LATE | d 먼저·P 나중 + seam (a)(b) 충족 | `file:…/rev-ok` | `PREVENTION_LATE` | 1 | U-17-(c) ∀d∈D: P ⊰ d 잔존 | **일치** |
| 부속 UNSIGNED | countersign 형식 위반(`APPROVED (no ISO)`) + seam ACTIVE | `file:…/active` | `PREVENTION_UNSIGNED` | 1 | U-17-c 3 | **일치** |
| (본 저장소) | HEAD `eb2805a9` 에 실행기 적용 — 아티팩트 부재 | (조회 이전) | `PREVENTION_ABSENT` | 1 | «현재 평가» — 아티팩트 부재(전순서 2) | **일치** |

이 파일은 본 저장소의 `PREVENTION_ACTIVE` 를 주장하지 않는다 — live 로 관측된 값은 `INSUFFICIENT`(main)·`ABSENT`(작업 브랜치)뿐이고,
`ACTIVE` 는 전부 `SIMULATED` seam 이다.

---

## 1. u17-verify 실행기 — 원문 + 독해 선언 (sha256 `cd2de1db024f4280a6f67f520e7199d8eee40e7155798063f7a2212fb16f4cad`)

독해 선언(계약이 리터럴로 고정하지 않은 자리):
- **아티팩트 = 파라미터 선언**: `owner_repo:` · `target_branch:` · `tos_gate_check:`(부재 시 계약 기본값 `tos-gate`) · `operator_countersign:` — HEAD 커밋
  내용에서 읽는다(커밋-전용). 아티팩트 부재 → `PREVENTION_ABSENT`(전순서 2) · `owner_repo`/`target_branch` 부재 → 조회 대상을 정할 수 없으므로
  `PREVENTION_UNVERIFIABLE`(전순서 1). **countersign 형식**은 v2.15 에라타 E3 리터럴(`"<식별> <ISO-8601 UTC>"` · 키 정확히 1회)을 그대로 쓴다 —
  **v2.16 본문에는 그 리터럴이 남아 있지 않다**(§5-1 보고).
- **responder seam**: `U17_RESPONDER=gh`(기본 · `gh api -i` — 상태 줄+본문 캡처) | `file:<dir>`(주입 · SIMULATED) | `mixed:<dir>`(주입 있으면 파일, 없으면 gh —
  (a) 모의 + (b) live 조합용, 어느 경로를 탔는지 `U17-seam` 라인으로 기록). 캡처 파일 → 상태값 함수(파서+술어)는 responder 와 무관한 동일 코드 경로.
- **(a) 4 엔드포인트**: `branches/{t}/protection` · `rules/branches/{t}` · `rulesets` · `rulesets/{id}`(rules/branches 가 지목한 id ∪ rulesets 목록의 id 전부 —
  `bypass_actors` 는 여기에만 있다). **술어(클래식)**: `required_status_checks.contexts ∋ check`(`checks[].context` 대체 허용) ∧ `strict==true` ∧
  `enforce_admins.enabled==true` ∧ `allow_force_pushes.enabled==false` ∧ `allow_deletions.enabled==false`(키 부재 = 불충족) ∧ `required_pull_request_reviews`
  키 실재 ∧ (`restrictions` 실재 시 `apps==[]`). **술어(룰셋 동등물)**: 적용 규칙에 `required_status_checks{strict_required_status_checks_policy:true,
  required_status_checks[].context∋check}` ∧ `pull_request` ∧ `non_fast_forward` ∧ `deletion` ∧ 지목된 모든 `rulesets/{id}` 가 `enforcement=="active"` ∧
  `bypass_actors==[]`(키 부재 = 불충족). 판정: 어느 엔드포인트든 ERR/비-2xx·비-404 → UNVERIFIABLE · 클래식 ∨ 룰셋 충족 → ACTIVE-a · protection 404 ∧
  적용 규칙 0 → ABSENT · 그 외 → INSUFFICIENT.
- **(b) ∀d∈D**: `commits/{d}/pulls` → `merged_at≠null ∧ base.ref==target` 인 PR 의 `head.sha` → `commits/{head.sha}/check-runs` 에 `name==check ∧
  conclusion=="success"`. 422/비-2xx → UNVERIFIABLE · PR 부재/미머지/base≠target/체크 부재 → UNVERIFIED_REVISION. **D=∅ → «검증 대상 없음» 명시 통과**((a) 만으로).
- **(c)** `∀d∈D: P ⊰ d`(진 조상). **P·D 는 구조 정의**(경로 존재 ∧ 모든 부모에 부재). 후보 집합만 `git rev-list --full-history HEAD -- path` 로 좁힌다 —
  술어를 만족하는 x 는 모든 부모와 다르므로 후보에 반드시 포함(완전성); 판정은 후보 위 구조 평가. (전수 순회 판은 이 저장소 2,149 커밋에서 run 당 수 분이
  걸려 가드 체인 안에서 실용 불가였다 — 성능 최적화이며 정의 변경이 아님.)
- **전순서**: 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 INSUFFICIENT > 5 LATE > 6 UNVERIFIED_REVISION > 7 ACTIVE — 계약 U-17-c 그대로. exit 0 = ACTIVE 만 ·
  `trap EXIT` 는 판정 없이 끝나는 경로를 UNVERIFIABLE 로 폐쇄. run 은 `U17-0 target=…` 라인이 열고 캡처마다 `U17-A1..A4`/`U17-B1..B2` 라벨 + `utc=` + `http=` 를 단다.

```bash
#!/usr/bin/env bash
# u17-verify — U-17 «예방 통제 활성 증거» 실행기 (계약 v2.16 eb2805a9 §12.3.4 U-17 (a)(b)(c)·U-17-c 7값/전순서 7단·U-15-f-1 3단 가드의 가운데)
#   §12.3.4-R 하니스와 «별도» 실행기 — 하니스는 오프라인·byte-identical, 이 실행기는 인증 서버 live 조회.
#   run 은 stdout 의 `U17-0 target=<owner>/<repo>@<branch>` 라인이 연다 (하니스의 `R-0 head=` 규약 확장). CORR 은 이 run 을 보지 않는다.
#
#   파라미터 원천 = 아티팩트 tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md (HEAD 커밋 내용에서 읽는다 — 워킹트리 아님)
#       owner_repo: <owner>/<repo> · target_branch: <branch> · tos_gate_check: <name>(부재 시 계약 기본값 tos-gate) · operator_countersign: "<식별> <ISO-8601 UTC>"
#   진실 원천 = 서버. responder seam: U17_RESPONDER=gh(기본 · `gh api -i`) | file:<dir>(주입 · SIMULATED — <dir>/<path 의 / → _ 치환>.status/.body)
#       seam 은 «입력»만 바꾼다 — 캡처 파일 → 상태값 함수(파서+술어)는 responder 와 무관하게 동일 코드 경로.
#   (a) live: protection / rules/branches / rulesets / rulesets/{id} 4 엔드포인트 캡처(verbatim + UTC) → 술어 → ACTIVE|ABSENT(404·규칙 0)|INSUFFICIENT|UNVERIFIABLE
#   (b) 리비전: ∀d∈D(구조 정의): commits/{d}/pulls → merged ∧ base==target 인 PR → commits/{head.sha}/check-runs 에 name==check ∧ conclusion==success
#   (c) 기록: countersign 형식 · ∀d∈D: P ⊰ d
#   전순서: 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 INSUFFICIENT > 5 LATE > 6 UNVERIFIED_REVISION > 7 ACTIVE.  exit 0 = ACTIVE 만. trap EXIT 폐쇄.
# 사용: bash u17-verify.sh [<repo-dir>]      (env: U17_RESPONDER · U17_CAPTURE_DIR[캡처 저장 위치, 기본 mktemp])
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

# ── 아티팩트 (전순서 2 ABSENT · 파라미터 선언) — 커밋-전용 읽기
BODY=$(git show "HEAD:$PC" 2>/dev/null) || emit PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"
yv() { printf '%s\n' "$BODY" | sed -n "s/^$1:[[:space:]]*//p" | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//' | head -1; }
OWNER_REPO=$(yv owner_repo); TARGET=$(yv target_branch); CHECK=$(yv tos_gate_check); [ -n "$CHECK" ] || CHECK=tos-gate
case "$OWNER_REPO" in */*) ;; *) emit PREVENTION_UNVERIFIABLE "아티팩트 파라미터 owner_repo 부재·형식 오류: '$OWNER_REPO' — 조회 대상을 정할 수 없다" ;; esac
[ -n "$TARGET" ] || emit PREVENTION_UNVERIFIABLE "아티팩트 파라미터 target_branch 부재 — 조회 대상을 정할 수 없다"
printf 'U17-0 target=%s@%s\n' "$OWNER_REPO" "$TARGET"
printf 'U17-0 check=%s responder=%s params_source=artifact:%s capture_dir=%s\n' "$CHECK" "$RESP" "$(git rev-parse --short HEAD)" "$CAP"

# ── responder seam: respond <api-path> → 캡처 파일 <CAP>/<key>.status/.body, 반환 0 = 응답 있음(HTTP 상태 확보) · 1 = 네트워크/도구 오류
respond() {
  local path="$1" key; key=$(printf '%s' "$1" | tr '/?=&' '____'); local st="$CAP/$key.status" bd="$CAP/$key.body"
  case "$RESP" in
    gh)  local out; out=$(gh api -i "$path" 2>"$CAP/$key.err"); local rc=$?
         printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
         printf '%s\n' "$out" | awk 'f{print} /^\r?$/{f=1}' > "$bd"
         if ! grep -Eq '^[0-9]{3}$' "$st"; then printf 'ERR\n' > "$st"; cat "$CAP/$key.err" > "$bd" 2>/dev/null; return 1; fi
         return 0 ;;
    file:*) local dir="${RESP#file:}"
         if [ -f "$dir/$key.status" ]; then cp "$dir/$key.status" "$st"; cp "$dir/$key.body" "$bd" 2>/dev/null || : > "$bd"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected response for %s\n' "$path" > "$bd"; return 1; fi ;;
    mixed:*) local dir="${RESP#mixed:}"     # 주입 응답이 있으면 파일(SIMULATED), 없으면 gh live — (a) 모의 + (b) live 조합용 (판정 함수는 동일)
         if [ -f "$dir/$key.status" ]; then cp "$dir/$key.status" "$st"; cp "$dir/$key.body" "$bd" 2>/dev/null || : > "$bd"; printf 'U17-seam %s ← file(SIMULATED)\n' "$path"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'U17-seam %s ← gh(live)\n' "$path"; RESP=gh respond "$path"; local r=$?; RESP="mixed:$dir"; return $r; fi ;;
    *) emit PREVENTION_UNVERIFIABLE "알 수 없는 responder: $RESP" ;;
  esac
}
show_capture() {  # show_capture <label> <api-path> — verbatim(원문 그대로) + UTC
  local key; key=$(printf '%s' "$2" | tr '/?=&' '____')
  printf 'U17-%s %s  utc=%s  http=%s\n' "$1" "$2" "$(utc)" "$(cat "$CAP/$key.status")"
  sed 's/^/  | /' "$CAP/$key.body"
}

# ── (a) live 4 엔드포인트 캡처
P_PROT="repos/$OWNER_REPO/branches/$TARGET/protection"
P_RULES="repos/$OWNER_REPO/rules/branches/$TARGET"
P_RSETS="repos/$OWNER_REPO/rulesets"
respond "$P_PROT";  show_capture A1 "$P_PROT"
respond "$P_RULES"; show_capture A2 "$P_RULES"
respond "$P_RSETS"; show_capture A3 "$P_RSETS"
# 룰셋 상세: rules/branches 가 지목한 ruleset_id ∪ /rulesets 목록의 id 전부 (bypass_actors 는 여기에만 있다 — R1) — 넷의 캡처 위에서 평가
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
print(" ".join(sorted(ids)))' "$CAP/$(printf '%s' "$P_RULES" | tr '/?=&' '____').body" "$CAP/$(printf '%s' "$P_RSETS" | tr '/?=&' '____').body" 2>/dev/null)
for id in $RSIDS; do respond "repos/$OWNER_REPO/rulesets/$id"; show_capture A4 "repos/$OWNER_REPO/rulesets/$id"; done
[ -n "$RSIDS" ] || printf 'U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)\n'

# ── 캡처 → (a) 상태값: 결정적 함수 (responder 무관 · 같은 캡처면 같은 값)
A_STATE=$(python3 - "$CAP" "$OWNER_REPO" "$TARGET" "$CHECK" <<'PY'
import json,sys,os
cap,orepo,target,check=sys.argv[1:5]
def key(p): return p.replace('/','_').replace('?','_').replace('=','_').replace('&','_')
def load(p):
    try:
        st=open(os.path.join(cap,key(p)+'.status')).read().strip()
        body=open(os.path.join(cap,key(p)+'.body')).read()
    except Exception:
        return "ERR",None          # 캡처 부재 = 조회 불가로 읽는다 (fail-closed)
    try: js=json.loads(body) if body.strip() else None
    except Exception: js=None
    return st,js
why=[]
st_p,prot=load(f"repos/{orepo}/branches/{target}/protection")
st_r,rules=load(f"repos/{orepo}/rules/branches/{target}")
st_s,rsets=load(f"repos/{orepo}/rulesets")
def unverifiable(st): return st=="ERR" or (st.isdigit() and st!="404" and not st.startswith("2"))
if unverifiable(st_p) or unverifiable(st_r) or unverifiable(st_s):
    print("PREVENTION_UNVERIFIABLE|http/network/auth: protection=%s rules=%s rulesets=%s"%(st_p,st_r,st_s)); sys.exit(0)
# 분기 1: 클래식 브랜치 보호
prot_ok=False
if st_p.startswith("2") and isinstance(prot,dict):
    rsc=prot.get("required_status_checks") or {}
    ctx=rsc.get("contexts") or [c.get("context") for c in (rsc.get("checks") or [])]
    if check not in (ctx or []): why.append(f"contexts∌{check}")
    if rsc.get("strict") is not True: why.append("strict≠true")
    if not (prot.get("enforce_admins") or {}).get("enabled") is True: why.append("enforce_admins≠true")
    if (prot.get("allow_force_pushes") or {}).get("enabled") is not False: why.append("force-push 불허 아님")
    if (prot.get("allow_deletions") or {}).get("enabled") is not False: why.append("deletion 불허 아님")
    if "required_pull_request_reviews" not in prot: why.append("required_pull_request_reviews 키 부재")
    restr=prot.get("restrictions")
    if isinstance(restr,dict) and (restr.get("apps") or []): why.append("restrictions.apps 우회 경로")
    prot_ok = not why
elif st_p=="404": why.append("protection 404")
# 분기 2: 룰셋 동등물 (rules/branches 적용 규칙 + rulesets/{id} 필드)
rs_ok=False; rs_why=[]
applied=rules if isinstance(rules,list) else []
if applied:
    types={r.get("type") for r in applied}
    ids={r.get("ruleset_id") for r in applied}
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
        if rs.get("bypass_actors") not in ([],None) : rs_why.append(f"rulesets/{i}.bypass_actors≠[]")
        if rs.get("bypass_actors") is None: rs_why.append(f"rulesets/{i}.bypass_actors 키 부재(불충족으로 읽음)")
    rs_ok = not rs_why
else:
    rs_why.append("적용 규칙 0")
if prot_ok or rs_ok:
    print("PREVENTION_ACTIVE|(a) 술어 충족: classic=%s ruleset=%s"%(prot_ok,rs_ok)); sys.exit(0)
if st_p=="404" and not applied:
    print("PREVENTION_ABSENT|protection 404 ∧ 적용 규칙 0 (룰셋 목록=%s)"%(len(rsets) if isinstance(rsets,list) else "n/a")); sys.exit(0)
print("PREVENTION_INSUFFICIENT|classic:[%s] ruleset:[%s]"%("; ".join(why),"; ".join(rs_why)))
PY
)
[ -n "$A_STATE" ] || emit PREVENTION_UNVERIFIABLE "(a) 캡처 평가 함수가 값을 내지 못함(파서 오류)"
A_VAL=${A_STATE%%|*}; A_WHY=${A_STATE#*|}
printf 'u17_live_state=%s\nu17_live_reason=%s\n' "$A_VAL" "$A_WHY"
[ "$A_VAL" != PREVENTION_UNVERIFIABLE ] || emit PREVENTION_UNVERIFIABLE "(a) $A_WHY"
[ "$A_VAL" != PREVENTION_ABSENT ]       || emit PREVENTION_ABSENT "(a) $A_WHY"

# ── (c) countersign 형식 (전순서 3 UNSIGNED — E3: `operator_countersign: "<식별> <ISO-8601 UTC>"` 정확히 1회)
CS_RE='^operator_countersign:[[:space:]]*"[^"[:space:]][^"]* [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"[[:space:]]*(#.*)?$'
nk=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:')
[ "$nk" = 1 ] || emit PREVENTION_UNSIGNED "operator_countersign 키 출현 횟수=$nk (정확히 1 요구)"
printf '%s\n' "$BODY" | grep -Eq "$CS_RE" || emit PREVENTION_UNSIGNED "operator_countersign 값 형식 위반: $(printf '%s\n' "$BODY" | grep '^operator_countersign:')"

# ── (a) 불충족 (전순서 4)
[ "$A_VAL" = PREVENTION_ACTIVE ] || emit PREVENTION_INSUFFICIENT "(a) $A_WHY"

# ── (c) 기록 순서 ∀d∈D: P ⊰ d (전순서 5) — P·D 구조 정의(경로 존재 ∧ 모든 부모에 부재)
#   구조 술어 «path ∈ tree(x) ∧ ∀p: path ∉ tree(p)» 를 후보마다 직접 평가한다. 후보 집합은 `git rev-list --full-history HEAD -- path`
#   (그 경로가 «어느 부모와도» 다른 커밋 전부 — 술어를 만족하는 x 는 모든 부모와 다르므로 반드시 포함된다: 완전성) 로 좁힌다.
#   이는 전수 순회의 성능 최적화이며 판정은 후보 위 구조 평가로만 한다(이력 단순화 기본값의 누락 클래스에 걸리지 않는다 — E1 주).
intro_set() { local path="$1" out="" x p intro; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue; intro=1; for p in $(git log --format=%P -1 "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
P=$(intro_set "$PC" | awk '{print $NF}'); D=$(intro_set "$CFG"); ND=$(printf '%s\n' $D | grep -c .)
printf 'P=%s |D|=%s D=%s\n' "$P" "$ND" "$(printf '%s ' $D)"
for d in $D; do { git merge-base --is-ancestor "$P" "$d" && [ "$P" != "$d" ]; } || emit PREVENTION_LATE "P 가 d=$d 의 진 조상이 아님"; done

# ── (b) 리비전 특정 ∀d∈D (전순서 6) — D=∅ 는 «검증 대상 없음»(공허참 아님·명시)
if [ "$ND" -eq 0 ]; then
  printf 'U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) 만으로 판정)\n'
else
  for d in $D; do
    respond "repos/$OWNER_REPO/commits/$d/pulls"; show_capture B1 "repos/$OWNER_REPO/commits/$d/pulls"
    HS=$(python3 - "$CAP" "$OWNER_REPO" "$d" "$TARGET" <<'PY'
import json,sys,os
cap,orepo,d,target=sys.argv[1:5]
k=f"repos/{orepo}/commits/{d}/pulls".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: prs=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|pulls 본문 파싱 실패"); sys.exit(0)
ok=[p for p in prs if isinstance(p,dict) and p.get("merged_at") and (p.get("base") or {}).get("ref")==target]
if not ok: print("UNVERIFIED_REVISION|착지 PR 부재·merged 아님·base≠target (pulls=%d)"%len(prs)); sys.exit(0)
print("HEAD|"+ok[0]["head"]["sha"])
PY
)
    case "$HS" in
      UNVERIFIABLE\|*) emit PREVENTION_UNVERIFIABLE "(b) d=$d ${HS#*|}" ;;
      UNVERIFIED_REVISION\|*) emit PREVENTION_UNVERIFIED_REVISION "(b) d=$d ${HS#*|}" ;;
    esac
    HSHA=${HS#HEAD|}
    respond "repos/$OWNER_REPO/commits/$HSHA/check-runs"; show_capture B2 "repos/$OWNER_REPO/commits/$HSHA/check-runs"
    CR=$(python3 - "$CAP" "$OWNER_REPO" "$HSHA" "$CHECK" <<'PY'
import json,sys,os
cap,orepo,sha,check=sys.argv[1:5]
k=f"repos/{orepo}/commits/{sha}/check-runs".replace('/','_')
st=open(os.path.join(cap,k+'.status')).read().strip()
if st=="ERR" or not st.startswith("2"): print("UNVERIFIABLE|http="+st); sys.exit(0)
try: js=json.load(open(os.path.join(cap,k+'.body')))
except Exception: print("UNVERIFIABLE|check-runs 본문 파싱 실패"); sys.exit(0)
runs=js.get("check_runs") or []
if any(r.get("name")==check and r.get("conclusion")=="success" for r in runs): print("OK|check-run success 실재"); sys.exit(0)
print("UNVERIFIED_REVISION|name==%s ∧ conclusion==success 인 run 부재 (check_runs=%d)"%(check,len(runs)))
PY
)
    case "$CR" in
      UNVERIFIABLE\|*) emit PREVENTION_UNVERIFIABLE "(b) head=$HSHA ${CR#*|}" ;;
      UNVERIFIED_REVISION\|*) emit PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA ${CR#*|}" ;;
    esac
    printf 'U17-B d=%s head=%s: %s\n' "$d" "$HSHA" "${CR#*|}"
  done
fi

emit PREVENTION_ACTIVE "(a) 술어 충족 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=$ND) — responder=$RESP"
```

## 2. 드라이버 원문 — `t84v.sh` (①②④ · sha256 `320bb7c2773a26a1e5807e077a83e90f48ef9c204d080686954309e46ad07756`) · `t84v3.sh` (③ + 부속 · sha256 `c4a27791750246968a788a2b1dc68d2582ff94dcf6387db349287842deca5251`)

- 픽스처 = `scratchpad/fx84v/*` 독립 git repo(seed → P[아티팩트] [→ d]). seam 주입 디렉터리 `scratchpad/seam216/<variant>/` 는 드라이버가 만들며 주입 응답
  원문은 드라이버 원문(heredoc)과 실행 기록의 `U17-A*`/`U17-B*` 캡처에 그대로 있다. 전부 GET-only.

```bash
#!/usr/bin/env bash
# t84v.sh — v2.16 T-84 ①②③④ 드라이버 (u17-verify.sh). GET-only. 픽스처 = scratchpad 독립 git repo(아티팩트만 SIMULATED). 본 저장소 무접촉·설정 변경 0.
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
EX="$SP/u17-verify.sh"; FX="$SP/fx84v"; SEAM="$SP/seam216"; PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
OR=kakao-harris-lee/kis_unified_sts; WB=mission-critical-trading-operating-system
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ # art <repo> <target-branch> — 아티팩트 = 파라미터 선언 + countersign (SIMULATED · 진실 원천 아님)
  mkdir -p "$1/$(dirname $PC)"
  printf 'owner_repo: %s\ntarget_branch: %s\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n' "$OR" "$2" > "$1/$PC"
  git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; truth source = server)"; }
run(){ # run <repo> [responder]
  echo "-- artifact @HEAD --"; git -C "$1" show "HEAD:$PC" | sed 's/^/  | /'
  echo "\$ U17_RESPONDER=${2:-gh} bash u17-verify.sh <fixture>"; U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$1"; echo "u17_rc=$?"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ # inject <dir> <api-path> <status> <body-file-or-literal>
  mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; if [ -f "$4" ]; then cp "$4" "$1/$(k "$2").body"; else printf '%s\n' "$4" > "$1/$(k "$2").body"; fi; }

sec "T-84 (1)-a live — target=main (responder=gh)"
R="$FX/live-main"; mk "$R"; art "$R" main; run "$R" gh
sec "T-84 (1)-b live — target=$WB (responder=gh)"
R="$FX/live-wb"; mk "$R"; art "$R" "$WB"; run "$R" gh

sec "T-84 (2) seam 주입 (SIMULATED) — 응답 원문 준비"
rm -rf "$SEAM"; mkdir -p "$SEAM"
# ACTIVE 응답(모의) — 술어 전건 충족: contexts∋tos-gate · strict · enforce_admins · force-push/deletion 불허 · required_pull_request_reviews 실재 · restrictions 없음
cat > "$SEAM/active-protection.json" <<'EOF'
{"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
EOF
# INSUFFICIENT 응답(모의) = 오늘 main 의 실측 응답 형태(contexts ["test"]·strict false·enforce_admins false·required_pull_request_reviews 부재)
cat > "$SEAM/insufficient-protection.json" <<'EOF'
{"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"required_signatures":{"enabled":false},"enforce_admins":{"enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
EOF
for v in active insufficient; do
  inject "$SEAM/$v" "repos/$OR/branches/main/protection" 200 "$SEAM/$v-protection.json"
  inject "$SEAM/$v" "repos/$OR/rules/branches/main" 200 '[]'
  inject "$SEAM/$v" "repos/$OR/rulesets" 200 '[]'
done
inject "$SEAM/unverifiable" "repos/$OR/branches/main/protection" 500 '{"message":"SIMULATED server error"}'
inject "$SEAM/unverifiable" "repos/$OR/rules/branches/main" 200 '[]'
inject "$SEAM/unverifiable" "repos/$OR/rulesets" 200 '[]'
mkdir -p "$SEAM/neterr"     # 주입 응답 없음 = 네트워크/도구 오류 모의
# 보호 해제 후(④ 용): 404 미보호 응답
inject "$SEAM/released-absent" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection#get-branch-protection","status":"404"}'
inject "$SEAM/released-absent" "repos/$OR/rules/branches/main" 200 '[]'
inject "$SEAM/released-absent" "repos/$OR/rulesets" 200 '[]'
echo "-- 주입 디렉터리 --"; ls -R "$SEAM" | sed 's/^/  /'
R="$FX/seam"; mk "$R"; art "$R" main
sec "T-84 (2)-i seam ACTIVE (SIMULATED)";        run "$R" "file:$SEAM/active"
sec "T-84 (2)-ii seam INSUFFICIENT (SIMULATED)"; run "$R" "file:$SEAM/insufficient"
sec "T-84 (2)-iii seam UNVERIFIABLE — HTTP 500 (SIMULATED)"; run "$R" "file:$SEAM/unverifiable"
sec "T-84 (2)-iv seam UNVERIFIABLE — 응답 없음/네트워크 오류 (SIMULATED)"; run "$R" "file:$SEAM/neterr"

sec "T-84 (4) stub 시퀀스 — countersign 시점 ACTIVE(SIMULATED) → 보호 해제 → 재조회"
R="$FX/seq"; mk "$R"; art "$R" main
echo "== t0: ACTIVE (SIMULATED seam)";           run "$R" "file:$SEAM/active"
echo "== t1: 보호 해제(404) 후 재조회";            run "$R" "file:$SEAM/released-absent"
echo "== t2: 보호 약화(strict/체크 해제) 후 재조회"; run "$R" "file:$SEAM/insufficient"
echo "== t3: live 재조회 (responder=gh · 오늘 실 서버)"; run "$R" gh
```

```bash
#!/usr/bin/env bash
# t84v3.sh — v2.16 T-84 ③ 리비전 특정 (b) + (c) 순서 부속. GET-only. 픽스처 = scratchpad 독립 git repo. 본 저장소 무접촉.
#   ③-0 live 병기: 본 저장소의 실 커밋으로 (b) 경로 원자료 실측 — 미푸시 HEAD → 422 · 푸시된 무-PR 커밋 → [] · origin/main 의 PR 착지 커밋 → pulls → head.sha → check-runs
#   ③-a mixed: (a) 는 seam ACTIVE(SIMULATED) · (b) 는 live — 픽스처 d 는 GitHub 에 없는 sha → 422 → UNVERIFIABLE
#   ③-b/c/d seam(SIMULATED): pulls+check-runs 주입 — 양성 ACTIVE / check-run 부재 → UNVERIFIED_REVISION / PR 부재 → UNVERIFIED_REVISION
#   ⑤ 부속: d 먼저·P 나중 → LATE (seam ACTIVE 하에서도 (c) 가 잡는다)
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad
EX="$SP/u17-verify.sh"; FX="$SP/fx84v"; SEAM="$SP/seam216"; PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
OR=kakao-harris-lee/kis_unified_sts; REPO=/Users/harris/Development/private/kis_unified_sts
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ mkdir -p "$1/$(dirname $PC)"; printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n' "$OR" > "$1/$PC"; git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED)"; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ echo "\$ U17_RESPONDER=$2 bash u17-verify.sh <fixture>"; git -C "$1" log --oneline | sed 's/^/  /'; U17_RESPONDER="$2" U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$1"; echo "u17_rc=$?"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; if [ -f "$4" ]; then cp "$4" "$1/$(k "$2").body"; else printf '%s\n' "$4" > "$1/$(k "$2").body"; fi; }
probe(){ echo "\$ gh api -i $1   # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; gh api -i "$1" 2>&1 | grep -v -E '^[A-Za-z-]+: ' | sed 's/^/  | /'; }

sec "T-84 (3)-0 live 병기 — 본 저장소 실 커밋으로 (b) 원자료 실측 (GET-only)"
H=$(git -C "$REPO" rev-parse HEAD); echo "HEAD(미푸시)=$H  pushed_working=be98f075715521a46c4ae074150cbec2746e7384  origin/main=$(git -C "$REPO" rev-parse origin/main)"
probe "repos/$OR/commits/$H/pulls"
probe "repos/$OR/commits/be98f075715521a46c4ae074150cbec2746e7384/pulls"
OM=$(git -C "$REPO" rev-parse origin/main)
probe "repos/$OR/commits/$OM/pulls"
HS=$(gh api "repos/$OR/commits/$OM/pulls" 2>/dev/null | python3 -c 'import json,sys
try:
    a=json.load(sys.stdin); ok=[p for p in a if p.get("merged_at") and (p.get("base") or {}).get("ref")=="main"]
    print(ok[0]["head"]["sha"] if ok else "")
except Exception: print("")')
if [ -n "$HS" ]; then echo "PR head.sha=$HS"; probe "repos/$OR/commits/$HS/check-runs"; echo "-- check-run 이름·결론 요약 --"; gh api "repos/$OR/commits/$HS/check-runs" 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin); print("  total_count=%s"%j.get("total_count")); [print("  name=%r conclusion=%r"%(r.get("name"),r.get("conclusion"))) for r in j.get("check_runs",[])]'; else echo "(origin/main 커밋에 merged·base=main PR 없음)"; fi
echo "-- 대조: 머지 커밋 자체의 check-runs (계약 #5: check-run 은 머지 커밋이 아니라 PR head 에 붙는다) --"; probe "repos/$OR/commits/$OM/check-runs" | head -12

sec "T-84 (3)-a mixed — (a) seam ACTIVE(SIMULATED) + (b) live: 픽스처 d 는 GitHub 에 없는 sha → 422"
R="$FX/rev-live"; mk "$R"; art "$R"; D=$(d0a "$R"); echo "d=$D"; run "$R" "mixed:$SEAM/active"

sec "T-84 (3)-b seam — (b) 양성(SIMULATED): merged PR(base main) + head.sha check-run tos-gate success"
R="$FX/rev-seam"; mk "$R"; art "$R"; D=$(d0a "$R"); echo "d=$D"; HSHA=1111111111111111111111111111111111111111
S="$SEAM/rev-ok"; rm -rf "$S"; cp -R "$SEAM/active" "$S"
inject "$S" "repos/$OR/commits/$D/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"2026-08-19T00:00:00Z\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$HSHA\"},\"url\":\"SIMULATED\"}]"
inject "$S" "repos/$OR/commits/$HSHA/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\"},{\"name\":\"tos-gate\",\"conclusion\":\"success\"}]}"
run "$R" "file:$S"
sec "T-84 (3)-c seam — check-run 에 tos-gate success 부재 → UNVERIFIED_REVISION"
S="$SEAM/rev-nocheck"; rm -rf "$S"; cp -R "$SEAM/rev-ok" "$S"
inject "$S" "repos/$OR/commits/$HSHA/check-runs" 200 "{\"total_count\":1,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\"}]}"
run "$R" "file:$S"
sec "T-84 (3)-d seam — 착지 PR 부재(pulls []) → UNVERIFIED_REVISION"
S="$SEAM/rev-nopr"; rm -rf "$S"; cp -R "$SEAM/rev-ok" "$S"
inject "$S" "repos/$OR/commits/$D/pulls" 200 "[]"
run "$R" "file:$S"
sec "T-84 (3)-e seam — merged 아님(open PR) → UNVERIFIED_REVISION"
S="$SEAM/rev-open"; rm -rf "$S"; cp -R "$SEAM/rev-ok" "$S"
inject "$S" "repos/$OR/commits/$D/pulls" 200 "[{\"number\":9999,\"state\":\"open\",\"merged_at\":null,\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$HSHA\"}}]"
run "$R" "file:$S"

sec "T-84 (5) 부속 — d 먼저·P 나중 → PREVENTION_LATE (seam ACTIVE 하에서도 (c) 기록 순서가 잡는다)"
R="$FX/late"; mk "$R"; D=$(d0a "$R"); art "$R"; echo "d=$D"; run "$R" "file:$SEAM/rev-ok"
sec "T-84 (5) 부속 — countersign 형식 위반 → PREVENTION_UNSIGNED (seam ACTIVE 하에서도)"
R="$FX/unsigned"; mk "$R"; mkdir -p "$R/$(dirname $PC)"; printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: APPROVED (no ISO)\n' "$OR" > "$R/$PC"; git -C "$R" add -A; git -C "$R" commit -q -m "P: bad countersign"; run "$R" "file:$SEAM/active"
sec "T-84 (5) 부속 — 본 저장소 HEAD 에 실행기 적용 (아티팩트 부재 → ABSENT · 조회 이전)"
echo "\$ bash u17-verify.sh <repo>"; U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO"; echo "u17_rc=$?"
```

## 3. 실행 기록 — T-84 ①②④ (t84v.sh stdout 전문 · 캡처 verbatim + UTC)

```text
t84v_utc=2026-08-18T17:53:43Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t84v.sh

########## T-84 (1)-a live — target=main (responder=gh) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=gh bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=gh params_source=artifact:757da3f capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.BJn6u7lzYl
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:44Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:44Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:45Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T17:53:45Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
u17_rc=1

########## T-84 (1)-b live — target=mission-critical-trading-operating-system (responder=gh) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=gh bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@mission-critical-trading-operating-system
U17-0 check=tos-gate responder=gh params_source=artifact:d494516 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.w2IHkPzk7p
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/mission-critical-trading-operating-system/protection  utc=2026-08-18T17:53:46Z  http=404
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection#get-branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/mission-critical-trading-operating-system  utc=2026-08-18T17:53:46Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:47Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T17:53:47Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
u17_live_state=PREVENTION_ABSENT
u17_live_reason=protection 404 ∧ 적용 규칙 0 (룰셋 목록=1)
prevention_control_state=PREVENTION_ABSENT
reason=(a) protection 404 ∧ 적용 규칙 0 (룰셋 목록=1)
u17_rc=1

########## T-84 (2) seam 주입 (SIMULATED) — 응답 원문 준비 ##########
-- 주입 디렉터리 --
  active
  active-protection.json
  insufficient
  insufficient-protection.json
  neterr
  released-absent
  unverifiable
  
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active:
  repos_kakao-harris-lee_kis_unified_sts_branches_main_protection.body
  repos_kakao-harris-lee_kis_unified_sts_branches_main_protection.status
  repos_kakao-harris-lee_kis_unified_sts_rules_branches_main.body
  repos_kakao-harris-lee_kis_unified_sts_rules_branches_main.status
  repos_kakao-harris-lee_kis_unified_sts_rulesets.body
  repos_kakao-harris-lee_kis_unified_sts_rulesets.status
  
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/insufficient:
  repos_kakao-harris-lee_kis_unified_sts_branches_main_protection.body
  repos_kakao-harris-lee_kis_unified_sts_branches_main_protection.status
  repos_kakao-harris-lee_kis_unified_sts_rules_branches_main.body
  repos_kakao-harris-lee_kis_unified_sts_rules_branches_main.status
  repos_kakao-harris-lee_kis_unified_sts_rulesets.body
  repos_kakao-harris-lee_kis_unified_sts_rulesets.status
  
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/neterr:
  
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/released-absent:
  repos_kakao-harris-lee_kis_unified_sts_branches_main_protection.body
  repos_kakao-harris-lee_kis_unified_sts_branches_main_protection.status
  repos_kakao-harris-lee_kis_unified_sts_rules_branches_main.body
  repos_kakao-harris-lee_kis_unified_sts_rules_branches_main.status
  repos_kakao-harris-lee_kis_unified_sts_rulesets.body
  repos_kakao-harris-lee_kis_unified_sts_rulesets.status
  
  /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/unverifiable:
  repos_kakao-harris-lee_kis_unified_sts_branches_main_protection.body
  repos_kakao-harris-lee_kis_unified_sts_branches_main_protection.status
  repos_kakao-harris-lee_kis_unified_sts_rules_branches_main.body
  repos_kakao-harris-lee_kis_unified_sts_rules_branches_main.status
  repos_kakao-harris-lee_kis_unified_sts_rulesets.body
  repos_kakao-harris-lee_kis_unified_sts_rulesets.status

########## T-84 (2)-i seam ACTIVE (SIMULATED) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active params_source=artifact:2b07b2e capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gHms2xk2Du
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:48Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:48Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:48Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=2b07b2e00ed533afc755316b9a89a22f8f65cc5a |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) 만으로 판정)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=0) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active
u17_rc=0

########## T-84 (2)-ii seam INSUFFICIENT (SIMULATED) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/insufficient bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/insufficient params_source=artifact:2b07b2e capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.II16Jl6Vat
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:48Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"required_signatures":{"enabled":false},"enforce_admins":{"enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:48Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:48Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
u17_rc=1

########## T-84 (2)-iii seam UNVERIFIABLE — HTTP 500 (SIMULATED) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/unverifiable bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/unverifiable params_source=artifact:2b07b2e capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pAKjMi5oj4
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:48Z  http=500
  | {"message":"SIMULATED server error"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:48Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:48Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_UNVERIFIABLE
u17_live_reason=http/network/auth: protection=500 rules=200 rulesets=200
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(a) http/network/auth: protection=500 rules=200 rulesets=200
u17_rc=1

########## T-84 (2)-iv seam UNVERIFIABLE — 응답 없음/네트워크 오류 (SIMULATED) ##########
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/neterr bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/neterr params_source=artifact:2b07b2e capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.RZid8W1wI3
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:48Z  http=ERR
  | SIMULATED responder: no injected response for repos/kakao-harris-lee/kis_unified_sts/branches/main/protection
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:49Z  http=ERR
  | SIMULATED responder: no injected response for repos/kakao-harris-lee/kis_unified_sts/rules/branches/main
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:49Z  http=ERR
  | SIMULATED responder: no injected response for repos/kakao-harris-lee/kis_unified_sts/rulesets
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_UNVERIFIABLE
u17_live_reason=http/network/auth: protection=ERR rules=ERR rulesets=ERR
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(a) http/network/auth: protection=ERR rules=ERR rulesets=ERR
u17_rc=1

########## T-84 (4) stub 시퀀스 — countersign 시점 ACTIVE(SIMULATED) → 보호 해제 → 재조회 ##########
== t0: ACTIVE (SIMULATED seam)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active params_source=artifact:1dcaf32 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.AM1p5FKcdj
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:49Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:49Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:49Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=1dcaf32ea925611dc13fb769d57b779c95dd6b97 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) 만으로 판정)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=0) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active
u17_rc=0
== t1: 보호 해제(404) 후 재조회
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/released-absent bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/released-absent params_source=artifact:1dcaf32 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.EBjNMBgQNT
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:49Z  http=404
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection#get-branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:49Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:49Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ABSENT
u17_live_reason=protection 404 ∧ 적용 규칙 0 (룰셋 목록=0)
prevention_control_state=PREVENTION_ABSENT
reason=(a) protection 404 ∧ 적용 규칙 0 (룰셋 목록=0)
u17_rc=1
== t2: 보호 약화(strict/체크 해제) 후 재조회
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/insufficient bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/insufficient params_source=artifact:1dcaf32 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2dF7rQZ9P6
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:49Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":false,"contexts":["test"],"checks":[{"context":"test","app_id":15368}]},"required_signatures":{"enabled":false},"enforce_admins":{"enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:49Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:49Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
u17_rc=1
== t3: live 재조회 (responder=gh · 오늘 실 서버)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
$ U17_RESPONDER=gh bash u17-verify.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=gh params_source=artifact:1dcaf32 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aiVxLwQu7E
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:53:50Z  http=200
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:53:51Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:53:51Z  http=200
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-18T17:53:51Z  http=200
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
u17_rc=1
(t84v.sh exit=0)
```

## 4. 실행 기록 — T-84 ③ 리비전 특정 + 부속 (t84v3.sh stdout 전문 · live 병기 원자료 포함)

```text
t84v3_utc=2026-08-18T17:53:58Z
$ bash /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/t84v3.sh

########## T-84 (3)-0 live 병기 — 본 저장소 실 커밋으로 (b) 원자료 실측 (GET-only) ##########
HEAD(미푸시)=eb2805a910a230583907d560632dd82f71ff403c  pushed_working=be98f075715521a46c4ae074150cbec2746e7384  origin/main=11e382fc0c9c16d9208a0d59e595d9cf93066be5
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/eb2805a910a230583907d560632dd82f71ff403c/pulls   # utc=2026-08-18T17:53:58Z
  | HTTP/2.0 422 Unprocessable Entity
  | 
  | {"message":"No commit found for SHA: eb2805a910a230583907d560632dd82f71ff403c","documentation_url":"https://docs.github.com/rest/commits/commits#list-pull-requests-associated-with-a-commit","status":"422"}gh: No commit found for SHA: eb2805a910a230583907d560632dd82f71ff403c (HTTP 422)
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/be98f075715521a46c4ae074150cbec2746e7384/pulls   # utc=2026-08-18T17:53:58Z
  | HTTP/2.0 200 OK
  | 
  | []
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/11e382fc0c9c16d9208a0d59e595d9cf93066be5/pulls   # utc=2026-08-18T17:53:59Z
  | HTTP/2.0 200 OK
  | 
  | [{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls/636","id":4192087193,"node_id":"PR_kwDOQ9V_3c753iyZ","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/pull/636","diff_url":"https://github.com/kakao-harris-lee/kis_unified_sts/pull/636.diff","patch_url":"https://github.com/kakao-harris-lee/kis_unified_sts/pull/636.patch","issue_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/636","number":636,"state":"closed","locked":false,"title":"docs(futures): make real-account never-fund directive explicit","user":{"login":"kakao-harris-lee","id":130432481,"node_id":"U_kgDOB8Y94Q","avatar_url":"https://avatars.githubusercontent.com/u/130432481?v=4","gravatar_id":"","url":"https://api.github.com/users/kakao-harris-lee","html_url":"https://github.com/kakao-harris-lee","followers_url":"https://api.github.com/users/kakao-harris-lee/followers","following_url":"https://api.github.com/users/kakao-harris-lee/following{/other_user}","gists_url":"https://api.github.com/users/kakao-harris-lee/gists{/gist_id}","starred_url":"https://api.github.com/users/kakao-harris-lee/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/kakao-harris-lee/subscriptions","organizations_url":"https://api.github.com/users/kakao-harris-lee/orgs","repos_url":"https://api.github.com/users/kakao-harris-lee/repos","events_url":"https://api.github.com/users/kakao-harris-lee/events{/privacy}","received_events_url":"https://api.github.com/users/kakao-harris-lee/received_events","type":"User","user_view_type":"public","site_admin":false},"body":"## What\n\nMakes the operator safety directive **\"the real futures account is never funded with margin\"** explicit in the two canonical, on-`main` sources:\n\n- **`CLAUDE.md`** — new `Non-Negotiable Rules` bullet stating the never-fund policy, and a `### Futures` cross-reference bullet (real-money order probes / P-R5 stage 2 are policy-blocked; paper stays VirtualBroker, real orders 0).\n- **`docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md`** — marks the `2.2 Gate 2 — 소액 실전 준비` gate **VOID** with a banner and strikes the margin-deposit checklist item as policy-void (history preserved for the record).\n\n## Why\n\nOperator safety directive. Dev-stage mis-orders combined with fast-compounding futures losses (losses compound in minutes) make funding a real futures account with margin unacceptable. Real-money futures order paths — the P-R5 stage-2 probe and anything that emits real futures orders — are therefore permanently blocked by policy. A zero-deposit preflight ABORT is a **terminal** verdict, not \"pending funding\". GET-only real reads stay fine; measurements needing a real fill use the mock-derived bound.\n\n## How verified\n\n- `git diff` confirms exactly the two intended files changed (2 files, +5/-1); no `.env*`, secrets, or other files touched.\n- Grep of the phase-5 plan confirms the funding reference (`실계좌 증거금 입금 확인`) is struck through and the VOID banner is present.\n- The probe tests (`tests/tools/test_broker_probes_real_order.py`) assert only the verdict constant `ABORT_ORDER_AVAILABLE_ZERO`, never the ABORT message text — verified on the branch where they live — so the intended message-wording refinement is test-safe when applied there.\n\n## Scope note / deviation\n\nThe task also specified a third edit — refining the `RealOrderAbort(ABORT_ORDER_AVAILABLE_ZERO, ...)` **message string** in `tools/broker_probes/probes_real_order.py`. That file (and its test) exist **only on the unmerged `mission-critical-trading-operating-system` branch, not on `main`**, so the change cannot ride a `--base main` docs PR. Branching this PR off the feature branch instead would pull the entire unmerged probe feature into a `main`-based diff. The probe-message wording change should be applied on `mission-critical-trading-operating-system` (where the file lives) as part of that branch's own PR; the exact replacement string is ready and is test-safe (see above).\n\n## Acceptance checklist\n\n- [x] `CLAUDE.md` never-fund bullet added under `Non-Negotiable Rules`, immediately after the long/short-symmetry bullet.\n- [x] `CLAUDE.md` `### Futures` cross-reference bullet added.\n- [x] Phase-5 plan `Gate 2` VOID banner inserted after the header.\n- [x] Phase-5 plan margin-deposit checklist line struck through and marked policy-void.\n- [x] No `.env*` files or secrets modified; only the two on-`main` docs files changed.\n- [ ] (follow-up, separate branch) probe ABORT message wording applied on `mission-critical-trading-operating-system`.\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n","created_at":"2026-08-03T07:01:22Z","updated_at":"2026-08-03T07:15:36Z","closed_at":"2026-08-03T07:15:34Z","merged_at":"2026-08-03T07:15:34Z","merge_commit_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","assignees":[],"requested_reviewers":[],"requested_teams":[],"labels":[],"milestone":null,"draft":false,"commits_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls/636/commits","review_comments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls/636/comments","review_comment_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls/comments{/number}","comments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/636/comments","statuses_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/statuses/7656259d414c4a855824406bab40bdc5438de171","head":{"label":"kakao-harris-lee:docs/futures-never-fund","ref":"docs/futures-never-fund","sha":"7656259d414c4a855824406bab40bdc5438de171","user":{"login":"kakao-harris-lee","id":130432481,"node_id":"U_kgDOB8Y94Q","avatar_url":"https://avatars.githubusercontent.com/u/130432481?v=4","gravatar_id":"","url":"https://api.github.com/users/kakao-harris-lee","html_url":"https://github.com/kakao-harris-lee","followers_url":"https://api.github.com/users/kakao-harris-lee/followers","following_url":"https://api.github.com/users/kakao-harris-lee/following{/other_user}","gists_url":"https://api.github.com/users/kakao-harris-lee/gists{/gist_id}","starred_url":"https://api.github.com/users/kakao-harris-lee/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/kakao-harris-lee/subscriptions","organizations_url":"https://api.github.com/users/kakao-harris-lee/orgs","repos_url":"https://api.github.com/users/kakao-harris-lee/repos","events_url":"https://api.github.com/users/kakao-harris-lee/events{/privacy}","received_events_url":"https://api.github.com/users/kakao-harris-lee/received_events","type":"User","user_view_type":"public","site_admin":false},"repo":{"id":1138065373,"node_id":"R_kgDOQ9V_3Q","name":"kis_unified_sts","full_name":"kakao-harris-lee/kis_unified_sts","private":false,"owner":{"login":"kakao-harris-lee","id":130432481,"node_id":"U_kgDOB8Y94Q","avatar_url":"https://avatars.githubusercontent.com/u/130432481?v=4","gravatar_id":"","url":"https://api.github.com/users/kakao-harris-lee","html_url":"https://github.com/kakao-harris-lee","followers_url":"https://api.github.com/users/kakao-harris-lee/followers","following_url":"https://api.github.com/users/kakao-harris-lee/following{/other_user}","gists_url":"https://api.github.com/users/kakao-harris-lee/gists{/gist_id}","starred_url":"https://api.github.com/users/kakao-harris-lee/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/kakao-harris-lee/subscriptions","organizations_url":"https://api.github.com/users/kakao-harris-lee/orgs","repos_url":"https://api.github.com/users/kakao-harris-lee/repos","events_url":"https://api.github.com/users/kakao-harris-lee/events{/privacy}","received_events_url":"https://api.github.com/users/kakao-harris-lee/received_events","type":"User","user_view_type":"public","site_admin":false},"html_url":"https://github.com/kakao-harris-lee/kis_unified_sts","description":null,"fork":false,"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts","forks_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/forks","keys_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/keys{/key_id}","collaborators_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/collaborators{/collaborator}","teams_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/teams","hooks_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/hooks","issue_events_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/events{/number}","events_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/events","assignees_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/assignees{/user}","branches_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches{/branch}","tags_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/tags","blobs_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/blobs{/sha}","git_tags_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/tags{/sha}","git_refs_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/refs{/sha}","trees_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/trees{/sha}","statuses_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/statuses/{sha}","languages_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/languages","stargazers_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/stargazers","contributors_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/contributors","subscribers_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/subscribers","subscription_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/subscription","commits_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/commits{/sha}","git_commits_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/commits{/sha}","comments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/comments{/number}","issue_comment_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/comments{/number}","contents_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/contents/{+path}","compare_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/compare/{base}...{head}","merges_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/merges","archive_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/{archive_format}{/ref}","downloads_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/downloads","issues_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues{/number}","pulls_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls{/number}","milestones_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/milestones{/number}","notifications_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/notifications{?since,all,participating}","labels_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/labels{/name}","releases_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/releases{/id}","deployments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/deployments","created_at":"2026-01-20T07:44:13Z","updated_at":"2026-08-03T07:16:06Z","pushed_at":"2026-08-18T15:20:49Z","git_url":"git://github.com/kakao-harris-lee/kis_unified_sts.git","ssh_url":"git@github.com:kakao-harris-lee/kis_unified_sts.git","clone_url":"https://github.com/kakao-harris-lee/kis_unified_sts.git","svn_url":"https://github.com/kakao-harris-lee/kis_unified_sts","homepage":null,"size":23880,"stargazers_count":0,"watchers_count":0,"language":"Python","has_issues":true,"has_projects":true,"has_downloads":false,"has_wiki":false,"has_pages":false,"has_discussions":false,"forks_count":0,"mirror_url":null,"archived":false,"disabled":false,"open_issues_count":2,"license":null,"allow_forking":true,"is_template":false,"web_commit_signoff_required":false,"has_pull_requests":true,"pull_request_creation_policy":"all","topics":[],"visibility":"public","forks":0,"open_issues":2,"watchers":0,"default_branch":"main"}},"base":{"label":"kakao-harris-lee:main","ref":"main","sha":"0b2d3962fc42660181b9b331a6b70e478ecd1594","user":{"login":"kakao-harris-lee","id":130432481,"node_id":"U_kgDOB8Y94Q","avatar_url":"https://avatars.githubusercontent.com/u/130432481?v=4","gravatar_id":"","url":"https://api.github.com/users/kakao-harris-lee","html_url":"https://github.com/kakao-harris-lee","followers_url":"https://api.github.com/users/kakao-harris-lee/followers","following_url":"https://api.github.com/users/kakao-harris-lee/following{/other_user}","gists_url":"https://api.github.com/users/kakao-harris-lee/gists{/gist_id}","starred_url":"https://api.github.com/users/kakao-harris-lee/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/kakao-harris-lee/subscriptions","organizations_url":"https://api.github.com/users/kakao-harris-lee/orgs","repos_url":"https://api.github.com/users/kakao-harris-lee/repos","events_url":"https://api.github.com/users/kakao-harris-lee/events{/privacy}","received_events_url":"https://api.github.com/users/kakao-harris-lee/received_events","type":"User","user_view_type":"public","site_admin":false},"repo":{"id":1138065373,"node_id":"R_kgDOQ9V_3Q","name":"kis_unified_sts","full_name":"kakao-harris-lee/kis_unified_sts","private":false,"owner":{"login":"kakao-harris-lee","id":130432481,"node_id":"U_kgDOB8Y94Q","avatar_url":"https://avatars.githubusercontent.com/u/130432481?v=4","gravatar_id":"","url":"https://api.github.com/users/kakao-harris-lee","html_url":"https://github.com/kakao-harris-lee","followers_url":"https://api.github.com/users/kakao-harris-lee/followers","following_url":"https://api.github.com/users/kakao-harris-lee/following{/other_user}","gists_url":"https://api.github.com/users/kakao-harris-lee/gists{/gist_id}","starred_url":"https://api.github.com/users/kakao-harris-lee/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/kakao-harris-lee/subscriptions","organizations_url":"https://api.github.com/users/kakao-harris-lee/orgs","repos_url":"https://api.github.com/users/kakao-harris-lee/repos","events_url":"https://api.github.com/users/kakao-harris-lee/events{/privacy}","received_events_url":"https://api.github.com/users/kakao-harris-lee/received_events","type":"User","user_view_type":"public","site_admin":false},"html_url":"https://github.com/kakao-harris-lee/kis_unified_sts","description":null,"fork":false,"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts","forks_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/forks","keys_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/keys{/key_id}","collaborators_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/collaborators{/collaborator}","teams_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/teams","hooks_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/hooks","issue_events_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/events{/number}","events_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/events","assignees_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/assignees{/user}","branches_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches{/branch}","tags_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/tags","blobs_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/blobs{/sha}","git_tags_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/tags{/sha}","git_refs_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/refs{/sha}","trees_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/trees{/sha}","statuses_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/statuses/{sha}","languages_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/languages","stargazers_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/stargazers","contributors_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/contributors","subscribers_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/subscribers","subscription_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/subscription","commits_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/commits{/sha}","git_commits_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/commits{/sha}","comments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/comments{/number}","issue_comment_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/comments{/number}","contents_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/contents/{+path}","compare_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/compare/{base}...{head}","merges_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/merges","archive_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/{archive_format}{/ref}","downloads_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/downloads","issues_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues{/number}","pulls_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls{/number}","milestones_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/milestones{/number}","notifications_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/notifications{?since,all,participating}","labels_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/labels{/name}","releases_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/releases{/id}","deployments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/deployments","created_at":"2026-01-20T07:44:13Z","updated_at":"2026-08-03T07:16:06Z","pushed_at":"2026-08-18T15:20:49Z","git_url":"git://github.com/kakao-harris-lee/kis_unified_sts.git","ssh_url":"git@github.com:kakao-harris-lee/kis_unified_sts.git","clone_url":"https://github.com/kakao-harris-lee/kis_unified_sts.git","svn_url":"https://github.com/kakao-harris-lee/kis_unified_sts","homepage":null,"size":23880,"stargazers_count":0,"watchers_count":0,"language":"Python","has_issues":true,"has_projects":true,"has_downloads":false,"has_wiki":false,"has_pages":false,"has_discussions":false,"forks_count":0,"mirror_url":null,"archived":false,"disabled":false,"open_issues_count":2,"license":null,"allow_forking":true,"is_template":false,"web_commit_signoff_required":false,"has_pull_requests":true,"pull_request_creation_policy":"all","topics":[],"visibility":"public","forks":0,"open_issues":2,"watchers":0,"default_branch":"main"}},"_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls/636"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/pull/636"},"issue":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/636"},"comments":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/issues/636/comments"},"review_comments":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls/636/comments"},"review_comment":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls/comments{/number}"},"commits":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/pulls/636/commits"},"statuses":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/statuses/7656259d414c4a855824406bab40bdc5438de171"}},"author_association":"OWNER","auto_merge":null,"assignee":null,"active_lock_reason":null}]
PR head.sha=7656259d414c4a855824406bab40bdc5438de171
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/7656259d414c4a855824406bab40bdc5438de171/check-runs   # utc=2026-08-18T17:54:00Z
  | HTTP/2.0 200 OK
  | 
  | {"total_count":5,"check_runs":[{"id":91617679453,"name":"performance","node_id":"CR_kwDOQ9V_3c8AAAAVVNbYXQ","head_sha":"7656259d414c4a855824406bab40bdc5438de171","external_id":"c28c9acf-14b5-55d7-8666-a44fa89054a7","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679453","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679453","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679453","status":"completed","conclusion":"success","started_at":"2026-08-03T07:01:28Z","completed_at":"2026-08-03T07:02:56Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679453/annotations"},"check_suite":{"id":83489483104},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91617679428,"name":"lint","node_id":"CR_kwDOQ9V_3c8AAAAVVNbYRA","head_sha":"7656259d414c4a855824406bab40bdc5438de171","external_id":"20995e2a-6944-53d3-9539-82aa5d3f7148","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679428","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679428","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679428","status":"completed","conclusion":"success","started_at":"2026-08-03T07:01:28Z","completed_at":"2026-08-03T07:02:24Z","output":{"title":null,"summary":null,"text":null,"annotations_count":5,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679428/annotations"},"check_suite":{"id":83489483104},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91617679411,"name":"type-check","node_id":"CR_kwDOQ9V_3c8AAAAVVNbYMw","head_sha":"7656259d414c4a855824406bab40bdc5438de171","external_id":"d6e6cbac-cd9d-51cb-a385-6cfc84a6b377","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679411","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679411","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679411","status":"completed","conclusion":"success","started_at":"2026-08-03T07:01:28Z","completed_at":"2026-08-03T07:03:08Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679411/annotations"},"check_suite":{"id":83489483104},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91617679398,"name":"test","node_id":"CR_kwDOQ9V_3c8AAAAVVNbYJg","head_sha":"7656259d414c4a855824406bab40bdc5438de171","external_id":"09c9e3d8-6398-5a2e-8b55-f6ff575c3e77","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679398","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679398","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679398","status":"completed","conclusion":"success","started_at":"2026-08-03T07:01:28Z","completed_at":"2026-08-03T07:05:56Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679398/annotations"},"check_suite":{"id":83489483104},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91617679375,"name":"backtest-extra","node_id":"CR_kwDOQ9V_3c8AAAAVVNbYDw","head_sha":"7656259d414c4a855824406bab40bdc5438de171","external_id":"3d556319-b6ee-5521-bdf0-4bce244916eb","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679375","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679375","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792121823/job/91617679375","status":"completed","conclusion":"success","started_at":"2026-08-03T07:01:28Z","completed_at":"2026-08-03T07:03:43Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91617679375/annotations"},"check_suite":{"id":83489483104},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]}]}
-- check-run 이름·결론 요약 --
  total_count=5
  name='performance' conclusion='success'
  name='lint' conclusion='success'
  name='type-check' conclusion='success'
  name='test' conclusion='success'
  name='backtest-extra' conclusion='success'
-- 대조: 머지 커밋 자체의 check-runs (계약 #5: check-run 은 머지 커밋이 아니라 PR head 에 붙는다) --
$ gh api -i repos/kakao-harris-lee/kis_unified_sts/commits/11e382fc0c9c16d9208a0d59e595d9cf93066be5/check-runs   # utc=2026-08-18T17:54:01Z
  | HTTP/2.0 200 OK
  | 
  | {"total_count":15,"check_runs":[{"id":95259896158,"name":"type-check","node_id":"CR_kwDOQ9V_3c8AAAAWLe6pXg","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"c5c1a31b-dae6-54d8-a8b1-b94a4ed6696a","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896158","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896158","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896158","status":"completed","conclusion":"success","started_at":"2026-08-17T01:38:51Z","completed_at":"2026-08-17T01:40:39Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896158/annotations"},"check_suite":{"id":86719603612},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":95259896132,"name":"lint","node_id":"CR_kwDOQ9V_3c8AAAAWLe6pRA","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"f930ab96-f603-506a-9bb9-70c8cca247fa","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896132","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896132","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896132","status":"completed","conclusion":"success","started_at":"2026-08-17T01:38:50Z","completed_at":"2026-08-17T01:39:49Z","output":{"title":null,"summary":null,"text":null,"annotations_count":5,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896132/annotations"},"check_suite":{"id":86719603612},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":95259896092,"name":"performance","node_id":"CR_kwDOQ9V_3c8AAAAWLe6pHA","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"1a71ec03-b512-532f-9870-b2666bcbe0a6","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896092","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896092","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896092","status":"completed","conclusion":"success","started_at":"2026-08-17T01:38:50Z","completed_at":"2026-08-17T01:40:20Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896092/annotations"},"check_suite":{"id":86719603612},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":95259896082,"name":"test","node_id":"CR_kwDOQ9V_3c8AAAAWLe6pEg","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"6989c8ad-7573-51a9-933a-09baf66fae8c","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896082","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896082","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896082","status":"completed","conclusion":"failure","started_at":"2026-08-17T01:38:50Z","completed_at":"2026-08-17T01:43:12Z","output":{"title":null,"summary":null,"text":null,"annotations_count":2,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896082/annotations"},"check_suite":{"id":86719603612},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":95259896042,"name":"backtest-extra","node_id":"CR_kwDOQ9V_3c8AAAAWLe6o6g","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"3f5ef872-f1c1-5c81-bff7-633c3a7d423a","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896042","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896042","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31985570609/job/95259896042","status":"completed","conclusion":"success","started_at":"2026-08-17T01:38:51Z","completed_at":"2026-08-17T01:41:05Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/95259896042/annotations"},"check_suite":{"id":86719603612},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":93336330791,"name":"backtest-extra","node_id":"CR_kwDOQ9V_3c8AAAAVu0diJw","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"d9a89283-b9c3-5e1c-9d39-0b52a75ffd5c","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330791","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330791","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330791","status":"completed","conclusion":"success","started_at":"2026-08-10T02:10:14Z","completed_at":"2026-08-10T02:12:33Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330791/annotations"},"check_suite":{"id":85030677311},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":93336330771,"name":"performance","node_id":"CR_kwDOQ9V_3c8AAAAVu0diEw","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"8631561c-3709-5f09-85b2-9a0b9c830442","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330771","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330771","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330771","status":"completed","conclusion":"success","started_at":"2026-08-10T02:10:21Z","completed_at":"2026-08-10T02:11:49Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330771/annotations"},"check_suite":{"id":85030677311},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":93336330765,"name":"test","node_id":"CR_kwDOQ9V_3c8AAAAVu0diDQ","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"1b25a8cc-d5bf-5166-96bf-19919a4610c9","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330765","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330765","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330765","status":"completed","conclusion":"success","started_at":"2026-08-10T02:10:14Z","completed_at":"2026-08-10T02:15:16Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330765/annotations"},"check_suite":{"id":85030677311},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":93336330754,"name":"lint","node_id":"CR_kwDOQ9V_3c8AAAAVu0diAg","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"be56f7c5-bad5-5b73-b2b0-af2422086750","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330754","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330754","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330754","status":"completed","conclusion":"success","started_at":"2026-08-10T02:10:15Z","completed_at":"2026-08-10T02:11:25Z","output":{"title":null,"summary":null,"text":null,"annotations_count":5,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330754/annotations"},"check_suite":{"id":85030677311},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":93336330729,"name":"type-check","node_id":"CR_kwDOQ9V_3c8AAAAVu0dh6Q","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"f78cf66c-0eca-5f3f-b405-8066d1c2c7bf","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330729","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330729","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/31349045822/job/93336330729","status":"completed","conclusion":"success","started_at":"2026-08-10T02:10:14Z","completed_at":"2026-08-10T02:11:58Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/93336330729/annotations"},"check_suite":{"id":85030677311},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91620300866,"name":"performance","node_id":"CR_kwDOQ9V_3c8AAAAVVP7YQg","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"374ccf43-950b-5c5e-8f15-4ecaf408a914","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300866","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300866","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300866","status":"completed","conclusion":"skipped","started_at":"2026-08-03T07:15:37Z","completed_at":"2026-08-03T07:15:37Z","output":{"title":null,"summary":null,"text":null,"annotations_count":0,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300866/annotations"},"check_suite":{"id":83491806218},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91620300397,"name":"lint","node_id":"CR_kwDOQ9V_3c8AAAAVVP7WbQ","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"5428cfc1-4de0-59f5-9f84-598ee63abc79","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300397","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300397","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300397","status":"completed","conclusion":"success","started_at":"2026-08-03T07:15:40Z","completed_at":"2026-08-03T07:16:40Z","output":{"title":null,"summary":null,"text":null,"annotations_count":5,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300397/annotations"},"check_suite":{"id":83491806218},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91620300358,"name":"type-check","node_id":"CR_kwDOQ9V_3c8AAAAVVP7WRg","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"21196f3b-76b5-5f10-8a5e-cc83d31bd90a","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300358","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300358","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300358","status":"completed","conclusion":"success","started_at":"2026-08-03T07:15:46Z","completed_at":"2026-08-03T07:17:39Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300358/annotations"},"check_suite":{"id":83491806218},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91620300355,"name":"backtest-extra","node_id":"CR_kwDOQ9V_3c8AAAAVVP7WQw","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"9f14d308-169a-5c65-a0d0-18d5838751b4","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300355","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300355","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300355","status":"completed","conclusion":"success","started_at":"2026-08-03T07:15:41Z","completed_at":"2026-08-03T07:18:10Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300355/annotations"},"check_suite":{"id":83491806218},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]},{"id":91620300308,"name":"test","node_id":"CR_kwDOQ9V_3c8AAAAVVP7WFA","head_sha":"11e382fc0c9c16d9208a0d59e595d9cf93066be5","external_id":"2401cec7-69c1-548c-acda-32cdd6276097","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300308","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300308","details_url":"https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/30792992476/job/91620300308","status":"completed","conclusion":"success","started_at":"2026-08-03T07:15:46Z","completed_at":"2026-08-03T07:20:46Z","output":{"title":null,"summary":null,"text":null,"annotations_count":1,"annotations_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/check-runs/91620300308/annotations"},"check_suite":{"id":83491806218},"app":{"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]},"pull_requests":[]}]}

########## T-84 (3)-a mixed — (a) seam ACTIVE(SIMULATED) + (b) live: 픽스처 d 는 GitHub 에 없는 sha → 422 ##########
d=175cf339ffe560ac8608336d979564218d3a31e3
$ U17_RESPONDER=mixed:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active bash u17-verify.sh <fixture>
  175cf33 D0-A: introduce config/tos_completion.yaml
  2c22023 P: D0A-PREVENTION-CONTROL (SIMULATED)
  e88f1e9 seed
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=mixed:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active params_source=artifact:175cf33 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Hc6AzsJL9V
U17-seam repos/kakao-harris-lee/kis_unified_sts/branches/main/protection ← file(SIMULATED)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:54:02Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-seam repos/kakao-harris-lee/kis_unified_sts/rules/branches/main ← file(SIMULATED)
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:54:02Z  http=200
  | []
U17-seam repos/kakao-harris-lee/kis_unified_sts/rulesets ← file(SIMULATED)
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:54:02Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=2c22023122f11b5ad46ef8420fe72bd2971b8fd3 |D|=1 D=175cf339ffe560ac8608336d979564218d3a31e3 
U17-seam repos/kakao-harris-lee/kis_unified_sts/commits/175cf339ffe560ac8608336d979564218d3a31e3/pulls ← gh(live)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/175cf339ffe560ac8608336d979564218d3a31e3/pulls  utc=2026-08-18T17:54:03Z  http=422
  | {"message":"No commit found for SHA: 175cf339ffe560ac8608336d979564218d3a31e3","documentation_url":"https://docs.github.com/rest/commits/commits#list-pull-requests-associated-with-a-commit","status":"422"}
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=(b) d=175cf339ffe560ac8608336d979564218d3a31e3 http=422
u17_rc=1

########## T-84 (3)-b seam — (b) 양성(SIMULATED): merged PR(base main) + head.sha check-run tos-gate success ##########
d=22aa702f02bd010f01793ba2b6f178b82ea9e8f4
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-ok bash u17-verify.sh <fixture>
  22aa702 D0-A: introduce config/tos_completion.yaml
  1f06fc3 P: D0A-PREVENTION-CONTROL (SIMULATED)
  d36b4e8 seed
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-ok params_source=artifact:22aa702 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.VhkSoFOwhS
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:54:03Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:54:03Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:54:03Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=1f06fc314c3e69152edee79d2344077e4f4f7d12 |D|=1 D=22aa702f02bd010f01793ba2b6f178b82ea9e8f4 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/22aa702f02bd010f01793ba2b6f178b82ea9e8f4/pulls  utc=2026-08-18T17:54:03Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1111111111111111111111111111111111111111"},"url":"SIMULATED"}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1111111111111111111111111111111111111111/check-runs  utc=2026-08-18T17:54:03Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success"},{"name":"tos-gate","conclusion":"success"}]}
U17-B d=22aa702f02bd010f01793ba2b6f178b82ea9e8f4 head=1111111111111111111111111111111111111111: check-run success 실재
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족 ∧ countersign 유효 ∧ ∀d∈D: P ⊰ d ∧ (b) 전 리비전 검증(|D|=1) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-ok
u17_rc=0

########## T-84 (3)-c seam — check-run 에 tos-gate success 부재 → UNVERIFIED_REVISION ##########
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-nocheck bash u17-verify.sh <fixture>
  22aa702 D0-A: introduce config/tos_completion.yaml
  1f06fc3 P: D0A-PREVENTION-CONTROL (SIMULATED)
  d36b4e8 seed
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-nocheck params_source=artifact:22aa702 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Bp89Glu15Z
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:54:03Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:54:04Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:54:04Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=1f06fc314c3e69152edee79d2344077e4f4f7d12 |D|=1 D=22aa702f02bd010f01793ba2b6f178b82ea9e8f4 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/22aa702f02bd010f01793ba2b6f178b82ea9e8f4/pulls  utc=2026-08-18T17:54:04Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-19T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1111111111111111111111111111111111111111"},"url":"SIMULATED"}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1111111111111111111111111111111111111111/check-runs  utc=2026-08-18T17:54:04Z  http=200
  | {"total_count":1,"check_runs":[{"name":"test","conclusion":"success"}]}
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=22aa702f02bd010f01793ba2b6f178b82ea9e8f4 head=1111111111111111111111111111111111111111 name==tos-gate ∧ conclusion==success 인 run 부재 (check_runs=1)
u17_rc=1

########## T-84 (3)-d seam — 착지 PR 부재(pulls []) → UNVERIFIED_REVISION ##########
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-nopr bash u17-verify.sh <fixture>
  22aa702 D0-A: introduce config/tos_completion.yaml
  1f06fc3 P: D0A-PREVENTION-CONTROL (SIMULATED)
  d36b4e8 seed
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-nopr params_source=artifact:22aa702 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.uCrXvn39UF
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:54:04Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:54:04Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:54:04Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=1f06fc314c3e69152edee79d2344077e4f4f7d12 |D|=1 D=22aa702f02bd010f01793ba2b6f178b82ea9e8f4 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/22aa702f02bd010f01793ba2b6f178b82ea9e8f4/pulls  utc=2026-08-18T17:54:04Z  http=200
  | []
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=22aa702f02bd010f01793ba2b6f178b82ea9e8f4 착지 PR 부재·merged 아님·base≠target (pulls=0)
u17_rc=1

########## T-84 (3)-e seam — merged 아님(open PR) → UNVERIFIED_REVISION ##########
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-open bash u17-verify.sh <fixture>
  22aa702 D0-A: introduce config/tos_completion.yaml
  1f06fc3 P: D0A-PREVENTION-CONTROL (SIMULATED)
  d36b4e8 seed
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-open params_source=artifact:22aa702 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.YvzlLXl3YZ
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:54:05Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:54:05Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:54:05Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=1f06fc314c3e69152edee79d2344077e4f4f7d12 |D|=1 D=22aa702f02bd010f01793ba2b6f178b82ea9e8f4 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/22aa702f02bd010f01793ba2b6f178b82ea9e8f4/pulls  utc=2026-08-18T17:54:05Z  http=200
  | [{"number":9999,"state":"open","merged_at":null,"base":{"ref":"main"},"head":{"sha":"1111111111111111111111111111111111111111"}}]
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=22aa702f02bd010f01793ba2b6f178b82ea9e8f4 착지 PR 부재·merged 아님·base≠target (pulls=1)
u17_rc=1

########## T-84 (5) 부속 — d 먼저·P 나중 → PREVENTION_LATE (seam ACTIVE 하에서도 (c) 기록 순서가 잡는다) ##########
d=aa31f381803c7bd0f936b92e7b4ca01bd8ba0f99
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-ok bash u17-verify.sh <fixture>
  fd3f1e7 P: D0A-PREVENTION-CONTROL (SIMULATED)
  aa31f38 D0-A: introduce config/tos_completion.yaml
  fcbcffb seed
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/rev-ok params_source=artifact:fd3f1e7 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.vwR3wJSDcZ
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:54:05Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:54:05Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:54:05Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P=fd3f1e7ea4fda32a64d25bace342c91c4bf82fb6 |D|=1 D=aa31f381803c7bd0f936b92e7b4ca01bd8ba0f99 
prevention_control_state=PREVENTION_LATE
reason=P 가 d=aa31f381803c7bd0f936b92e7b4ca01bd8ba0f99 의 진 조상이 아님
u17_rc=1

########## T-84 (5) 부속 — countersign 형식 위반 → PREVENTION_UNSIGNED (seam ACTIVE 하에서도) ##########
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active bash u17-verify.sh <fixture>
  0c2cbc4 P: bad countersign
  1c4bb5c seed
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 check=tos-gate responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/772f4b3f-210a-411d-85f1-d093ab20d09f/scratchpad/seam216/active params_source=artifact:0c2cbc4 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FMQR6zkZZN
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-18T17:54:06Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"required_linear_history":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-18T17:54:06Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-18T17:54:06Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
prevention_control_state=PREVENTION_UNSIGNED
reason=operator_countersign 값 형식 위반: operator_countersign: APPROVED (no ISO)
u17_rc=1

########## T-84 (5) 부속 — 본 저장소 HEAD 에 실행기 적용 (아티팩트 부재 → ABSENT · 조회 이전) ##########
$ bash u17-verify.sh <repo>
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
u17_rc=1
(t84v3.sh exit=0)
```

픽스처 DAG (조립 시점 재확인 · `git -C $SP/fx84v/<n> log --graph --oneline --all`):

```text
== fx84v/live-main
* 757da3f P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; truth source = server)
* 20ac606 seed
== fx84v/live-wb
* d494516 P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; truth source = server)
* aed51cc seed
== fx84v/seam
* 2b07b2e P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; truth source = server)
* 0b4dd82 seed
== fx84v/seq
* 1dcaf32 P: D0A-PREVENTION-CONTROL (SIMULATED parameter declaration; truth source = server)
* cfb9729 seed
== fx84v/rev-live
* 175cf33 D0-A: introduce config/tos_completion.yaml
* 2c22023 P: D0A-PREVENTION-CONTROL (SIMULATED)
* e88f1e9 seed
== fx84v/rev-seam
* 22aa702 D0-A: introduce config/tos_completion.yaml
* 1f06fc3 P: D0A-PREVENTION-CONTROL (SIMULATED)
* d36b4e8 seed
== fx84v/late
* fd3f1e7 P: D0A-PREVENTION-CONTROL (SIMULATED)
* aa31f38 D0-A: introduce config/tos_completion.yaml
* fcbcffb seed
== fx84v/unsigned
* 0c2cbc4 P: bad countersign
* 1c4bb5c seed
```

## 5. 관측·정직 기록·계약 결함 후보 (고치지 않는다 — bound_paths 동결)

1. **[계약 결함 후보] countersign 형식 리터럴 소실**: v2.15 에라타 E3 가 고정한 `operator_countersign: "<운영자 식별> <ISO-8601 UTC>"` 리터럴이 v2.16 U-17
   재작성 본문에 없다(`grep operator_countersign` → U-17-c 상태표의 «부재·형식 위반» 1건뿐). «형식 위반» 이 다시 미정의가 되어 E3 가 닫은 «구현 간 판정
   불일치» 클래스가 재개방된다. 이 실행기는 E3 리터럴을 그대로 적용했고(독해 선언), 부속 UNSIGNED 변이가 그 형식으로 red 를 냈다. **문언 복원 한 줄이면 닫힌다.**
2. **[계약 사실 정정 후보] «머지 커밋 check-runs 0건»**: 계약 #5 근거 문장(«이 저장소의 머지 커밋 check-runs 0건·pulls 공집합·미푸시 422»)을 live 재측정하면
   **origin/main 착지 커밋 `11e382fc` 의 check-runs 는 15건**(push 트리거 워크플로 — `test`·`lint`·`type-check`·`performance`·`backtest-extra`; PR head
   `7656259d` 는 5건)이고 pulls 는 PR #636 1건(merged·base main)이다. 결론(**조회 SHA 는 PR head.sha** — check-run 의 귀속 지점이 다르다)은 그대로 옳지만
   «0건» 은 이 커밋에서는 거짓이다 — 근거를 «머지 커밋의 check-runs 는 PR 게이트가 아니라 push 트리거 실행이라 (b) 의 증거가 아니다»로 교체하면 정합.
   미푸시 HEAD 422 · 푸시된 무-PR 커밋 `be98f075` → `[]` 는 계약 기술 그대로 실측됐다.
3. **live 음성의 성격**: ①-a/①-b·④-t3 은 인증된 실 조회(`responder=gh`)이며 모의가 아니다. **양성(ACTIVE)은 전부 seam(`SIMULATED`)** — 운영자가 `main` 보호에
   `tos-gate` 컨텍스트·strict·enforce_admins·PR reviews 를 설정하고 CI 에 `tos-gate` 잡을 두기 전에는 실측 불가(계약 정직 표기 그대로).
   룰셋 `protect_main` 은 실재하나 `enforcement=disabled`(rules `deletion`·`non_fast_forward` 만·`bypass_actors=[]`) — 적용 규칙 0 이라 룰셋 동등물 아님.
4. **seam 이 판정을 우회하지 않는 근거(실측)**: ②-ii 주입 본문은 오늘 main 실측 응답과 같은 필드값이고 실행기가 같은 사유 문자열로 INSUFFICIENT 를 냈다 —
   파서·술어가 동일 코드 경로. 진정성은 별개 축이며 계약 «진실 원천 = 판정 소비자 자신의 조회» 로 닫힌다(이 파일은 대조용).
5. **D=∅ 처리**: ②-i·④-t0 의 ACTIVE 는 `U17-B D=∅ — (b)(c) 검증 대상 없음` 을 명시하고 (a) 만으로 판정(계약 #6). 공허참에 기댄 것이 아니라 «비교 대상 없음» 을
   출력에 적었다.
6. **정밀화 여지(비차단)**: (i) 술어의 `allow_force_pushes`/`allow_deletions` 키 부재를 «불충족» 으로 읽었다(계약은 «불허» 만 적음) (ii) `restrictions` 우회 경로를
   `apps≠[]` 로 읽었다(users/teams 는 push 제한이므로 우회가 아니라고 봄) (iii) `rulesets/{id}` 의 `bypass_actors` 키 부재를 불충족으로 읽었다 — 셋 다
   fail-closed 방향이며 계약이 한 줄씩 고정하면 구현 독립이 된다.
7. 본 저장소 무접촉·설정 변경 0: 픽스처는 scratchpad 독립 repo, worktree 미사용(이 파일 범위), 서버는 GET 만 — §6 사후 재조회로 실행 전후 동일 확인.

## 6. 사후 검증 원문 (repo 무영향 · 서버 설정 무변경 · 본 저장소 NOT_STARTED/PREVENTION_ABSENT/REBINDING_REQUIRED)

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
